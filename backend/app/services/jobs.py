"""Asynchronous onboarding/offboarding job engine.

Jobs are queued and processed by a fixed pool of workers so bulk batches never
block the API. Progress, live logs and per-user results stream to the frontend
over Server-Sent Events. Every side effect is written to the audit store.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable

from app.config import Settings
from app.core.exceptions import OnboardingError
from app.models.auth import CurrentUser
from app.models.job import Job, JobLogEntry, JobStatus, UserResult
from app.models.offboard import OffboardOptions, OffboardResolvedUser
from app.models.user import NewUserSpec
from app.services.audit import AuditStore
from app.services.passwords import generate_password
from app.services.provider import IdentityProvider

log = logging.getLogger(__name__)

_MAX_JOBS_KEPT = 200

_Payload = list[NewUserSpec] | list[OffboardResolvedUser]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobManager:
    def __init__(self, provider: IdentityProvider, audit: AuditStore, settings: Settings):
        self._provider = provider
        self._audit = audit
        self._settings = settings
        self.jobs: OrderedDict[str, Job] = OrderedDict()
        self._payloads: dict[str, _Payload] = {}
        self._offboard_options: dict[str, OffboardOptions] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._workers: list[asyncio.Task] = []

    # --- lifecycle -------------------------------------------------------------
    async def start(self) -> None:
        for i in range(self._settings.job_workers):
            self._workers.append(asyncio.create_task(self._worker(), name=f"job-worker-{i}"))

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    # --- public API -------------------------------------------------------------
    async def submit(
        self, job_type: str, users: list[NewUserSpec], actor: CurrentUser,
        source_ip: str = "",
    ) -> Job:
        job = await self._enqueue(
            job_type, len(users),
            [u.display_name or f"{u.first_name} {u.last_name}" for u in users],
            actor, source_ip,
        )
        self._payloads[job.id] = users
        await self._queue.put(job.id)
        return job

    async def submit_offboard(
        self, targets: list[OffboardResolvedUser], options: OffboardOptions,
        actor: CurrentUser, source_ip: str = "",
    ) -> Job:
        job = await self._enqueue(
            "offboard", len(targets), [u.display_name for u in targets], actor, source_ip,
        )
        self._payloads[job.id] = targets
        self._offboard_options[job.id] = options
        await self._queue.put(job.id)
        return job

    async def _enqueue(
        self, job_type: str, total: int, names: list[str], actor: CurrentUser, source_ip: str,
    ) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:12],
            type=job_type,
            created_by=actor.username,
            created_at=_now(),
            total=total,
            payload_summary={"users": names},
        )
        self.jobs[job.id] = job
        while len(self.jobs) > _MAX_JOBS_KEPT:
            old_id, _ = self.jobs.popitem(last=False)
            self._payloads.pop(old_id, None)
            self._offboard_options.pop(old_id, None)
            self._subscribers.pop(old_id, None)
        await self._audit.record(
            actor=actor.username, actor_role=actor.role.value, action="job.submit",
            target=job.id, source_ip=source_ip, details={"type": job_type, "users": total},
        )
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def list(self, limit: int = 50) -> list[Job]:
        return list(reversed(list(self.jobs.values())))[:limit]

    def pending_count(self) -> int:
        return sum(
            1 for j in self.jobs.values()
            if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
        )

    async def events(self, job_id: str) -> AsyncIterator[dict[str, Any]]:
        """SSE event stream for one job: snapshot, then live updates."""
        job = self.jobs.get(job_id)
        if not job:
            yield {"type": "error", "message": "job not found"}
            return
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[job_id].append(queue)
        try:
            yield {"type": "snapshot", "job": job.public(include_passwords=True)}
            if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                yield {"type": "done", "job": job.public(include_passwords=True)}
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"type": "ping"}
                    continue
                yield event
                if event.get("type") == "done":
                    return
        finally:
            try:
                self._subscribers[job_id].remove(queue)
            except ValueError:
                pass

    # --- internals ------------------------------------------------------------
    def _emit(self, job: Job, event: dict[str, Any]) -> None:
        for queue in self._subscribers.get(job.id, []):
            queue.put_nowait(event)

    def _log(self, job: Job, level: str, message: str) -> None:
        entry = JobLogEntry(ts=_now(), level=level, message=message)
        job.logs.append(entry)
        self._emit(job, {"type": "log", "entry": entry.model_dump(mode="json")})

    async def _worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await self._run(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Job %s crashed", job_id)
                job = self.jobs.get(job_id)
                if job:
                    job.status = JobStatus.FAILED
                    job.finished_at = _now()
                    self._emit(job, {"type": "done", "job": job.public(include_passwords=True)})
            finally:
                self._queue.task_done()

    async def _run(self, job_id: str) -> None:
        job = self.jobs[job_id]
        payload = self._payloads.pop(job_id, [])
        job.status = JobStatus.RUNNING
        job.started_at = _now()
        self._emit(job, {"type": "status", "status": job.status.value})
        self._log(job, "info", f"Job started: {job.total} user(s) to process")

        if job.type == "offboard":
            options = self._offboard_options.pop(job_id, OffboardOptions())
            for target in payload:  # type: ignore[assignment]
                await self._process_item(
                    job, sam=target.sam_account_name, upn=target.user_principal_name,
                    display=target.display_name, audit_action="user.offboard",
                    handler=lambda t=target: self._offboard_user(job, t, options),
                )
        else:
            for spec in payload:  # type: ignore[assignment]
                await self._process_item(
                    job, sam=spec.sam_account_name or "", upn=spec.user_principal_name or "",
                    display=spec.display_name or f"{spec.first_name} {spec.last_name}",
                    audit_action="user.create",
                    handler=lambda s=spec: self._onboard_user(job, s),
                )

        if job.errors == 0:
            job.status = JobStatus.COMPLETED
        elif job.errors < job.total:
            job.status = JobStatus.COMPLETED_WITH_ERRORS
        else:
            job.status = JobStatus.FAILED
        job.finished_at = _now()
        self._log(
            job,
            "success" if job.errors == 0 else "warning",
            f"Job finished: {job.total - job.errors} succeeded, {job.errors} failed",
        )
        await self._audit.record(
            actor=job.created_by, actor_role="", action="job.complete", target=job.id,
            status="success" if job.errors == 0 else "warning",
            details={"succeeded": job.total - job.errors, "failed": job.errors},
        )
        self._emit(job, {"type": "done", "job": job.public(include_passwords=True)})

    async def _process_item(
        self, job: Job, *, sam: str, upn: str, display: str, audit_action: str,
        handler: Callable[[], Awaitable[UserResult]],
    ) -> None:
        """Shared per-item try/log/audit/emit envelope for both onboarding and
        offboarding: a single item's failure never aborts the batch."""
        try:
            result = await handler()
        except OnboardingError as exc:
            job.errors += 1
            result = UserResult(
                sam_account_name=sam, user_principal_name=upn, display_name=display,
                status="error", message=exc.message,
            )
            self._log(job, "error", f"{display}: {exc.message}")
            await self._audit.record(
                actor=job.created_by, actor_role="", action=audit_action,
                target=sam or display, status="error",
                details={"error": exc.message, "job": job.id},
            )
        except Exception as exc:  # defensive: never kill the batch
            log.exception("Unexpected failure processing item in job %s", job.id)
            job.errors += 1
            result = UserResult(
                sam_account_name=sam, user_principal_name=upn, display_name=display,
                status="error", message=f"Unexpected error: {exc}",
            )
            self._log(job, "error", f"{display}: unexpected error: {exc}")
        job.results.append(result)
        job.done += 1
        self._emit(job, {
            "type": "progress", "done": job.done, "total": job.total, "errors": job.errors,
            "result": result.model_dump(mode="json"),
        })

    async def _onboard_user(self, job: Job, spec: NewUserSpec) -> UserResult:
        display = spec.display_name or f"{spec.first_name} {spec.last_name}"
        sam = spec.sam_account_name or ""
        warnings: list[str] = []

        generated = None
        if spec.password.generate or not spec.password.value:
            generated = generate_password(self._settings.password_policy)
            password = generated
        else:
            password = spec.password.value

        # 1. Account -----------------------------------------------------------
        self._log(job, "info", f"Creating account '{sam}' in {spec.ou}")
        payload: dict[str, Any] = spec.model_dump(mode="json", exclude={"password"})
        payload["force_change_at_logon"] = spec.password.force_change_at_logon
        payload["password_never_expires"] = spec.password.never_expires
        await self._provider.create_user(payload, password)
        self._log(job, "success", f"Account created: {spec.user_principal_name}")
        await self._audit.record(
            actor=job.created_by, actor_role="", action="user.create", target=sam,
            details={"upn": spec.user_principal_name, "ou": spec.ou,
                     "display_name": display, "job": job.id},
        )

        # 2. Groups -------------------------------------------------------------
        if spec.groups:
            try:
                added = await self._provider.add_to_groups(sam, spec.groups)
                self._log(job, "success", f"Added '{sam}' to {len(added)} group(s)")
                await self._audit.record(
                    actor=job.created_by, actor_role="", action="group.assign",
                    target=sam, details={"groups": added, "job": job.id},
                )
            except OnboardingError as exc:
                warnings.append(f"groups: {exc.message}")
                self._log(job, "warning", f"Group assignment issue for '{sam}': {exc.message}")

        # 3. Licenses --------------------------------------------------------------
        if spec.licenses:
            try:
                assigned = await self._provider.assign_licenses(sam, spec.licenses)
                self._log(job, "success", f"Assigned license(s): {', '.join(assigned)}")
                await self._audit.record(
                    actor=job.created_by, actor_role="", action="license.assign",
                    target=sam, details={"skus": assigned, "job": job.id},
                )
            except OnboardingError as exc:
                warnings.append(f"licenses: {exc.message}")
                self._log(job, "warning", f"License issue for '{sam}': {exc.message}")
                await self._audit.record(
                    actor=job.created_by, actor_role="", action="license.assign",
                    target=sam, status="warning", details={"error": exc.message, "job": job.id},
                )

        # 4. Mailboxes ---------------------------------------------------------------
        if spec.create_mailbox:
            try:
                mailbox = await self._provider.create_mailbox(sam)
                self._log(job, "success", f"Mailbox provisioned: {mailbox.get('email')}")
                await self._audit.record(
                    actor=job.created_by, actor_role="", action="mailbox.create",
                    target=sam, details={**mailbox, "job": job.id},
                )
            except OnboardingError as exc:
                warnings.append(f"mailbox: {exc.message}")
                self._log(job, "warning", f"Mailbox issue for '{sam}': {exc.message}")
        if spec.shared_mailboxes:
            try:
                granted = await self._provider.add_shared_mailbox_access(
                    sam, spec.shared_mailboxes
                )
                self._log(job, "success",
                          f"Shared mailbox access granted: {', '.join(granted)}")
            except OnboardingError as exc:
                warnings.append(f"shared mailboxes: {exc.message}")
                self._log(job, "warning", f"Shared mailbox issue for '{sam}': {exc.message}")

        # 5. Home folder ----------------------------------------------------------------
        if spec.home_folder.enabled:
            base = spec.home_folder.base_path or self._settings.default_home_base_path
            path = f"{base}\\{sam}"
            try:
                await self._provider.create_home_folder(sam, path, spec.home_folder.drive_letter)
                self._log(job, "success",
                          f"Home folder created: {path} ({spec.home_folder.drive_letter}:)")
                await self._audit.record(
                    actor=job.created_by, actor_role="", action="homefolder.create",
                    target=sam, details={"path": path, "job": job.id},
                )
            except OnboardingError as exc:
                warnings.append(f"home folder: {exc.message}")
                self._log(job, "warning", f"Home folder issue for '{sam}': {exc.message}")

        # 6. Profile ------------------------------------------------------------------------
        if spec.profile.roaming_profile_path or spec.profile.logon_script:
            try:
                await self._provider.apply_profile(sam, spec.profile.model_dump())
                self._log(job, "success", f"Profile configured for '{sam}'")
            except OnboardingError as exc:
                warnings.append(f"profile: {exc.message}")
                self._log(job, "warning", f"Profile issue for '{sam}': {exc.message}")

        message = "Onboarded successfully"
        if warnings:
            message = "Onboarded with warnings: " + "; ".join(warnings)
        return UserResult(
            sam_account_name=sam,
            user_principal_name=spec.user_principal_name or "",
            display_name=display,
            status="success",
            message=message,
            generated_password=generated,
        )

    async def _offboard_user(
        self, job: Job, target: OffboardResolvedUser, options: OffboardOptions,
    ) -> UserResult:
        sam = target.sam_account_name
        display = target.display_name
        warnings: list[str] = []

        if not target.enabled:
            # Flagged as a warning at validation time; skip cleanly rather
            # than erroring the whole batch over a stale directory read.
            self._log(job, "info", f"'{sam}' is already disabled - skipping")
            return UserResult(
                sam_account_name=sam, user_principal_name=target.user_principal_name,
                display_name=display, status="success", message="Already disabled - skipped",
            )

        # 1. Disable account --------------------------------------------------------
        self._log(job, "info",
                  f"Disabling account '{sam}'" + (f" ({target.reason})" if target.reason else ""))
        await self._provider.disable_user(
            sam, move_to_ou=options.move_to_ou, reset_password=options.reset_password
        )
        self._log(job, "success", f"Account disabled: {sam}")
        await self._audit.record(
            actor=job.created_by, actor_role="", action="user.offboard", target=sam,
            details={"reason": target.reason, "moved_to_ou": options.move_to_ou, "job": job.id},
        )

        # 2. Groups -------------------------------------------------------------
        if options.remove_from_groups:
            try:
                removed = await self._provider.remove_from_groups(
                    sam, keep_distribution_lists=options.keep_distribution_lists
                )
                self._log(job, "success", f"Removed '{sam}' from {len(removed)} group(s)")
                await self._audit.record(
                    actor=job.created_by, actor_role="", action="group.remove",
                    target=sam, details={"groups": removed, "job": job.id},
                )
            except OnboardingError as exc:
                warnings.append(f"groups: {exc.message}")
                self._log(job, "warning", f"Group removal issue for '{sam}': {exc.message}")

        # 3. Licenses --------------------------------------------------------------
        if options.revoke_licenses:
            try:
                revoked = await self._provider.revoke_licenses(sam)
                if revoked:
                    self._log(job, "success", f"Revoked license(s): {', '.join(revoked)}")
                    await self._audit.record(
                        actor=job.created_by, actor_role="", action="license.revoke",
                        target=sam, details={"skus": revoked, "job": job.id},
                    )
            except OnboardingError as exc:
                warnings.append(f"licenses: {exc.message}")
                self._log(job, "warning", f"License revocation issue for '{sam}': {exc.message}")

        # 4. Mailbox ------------------------------------------------------------------------
        if options.convert_mailbox_to_shared:
            try:
                mailbox = await self._provider.convert_mailbox_to_shared(
                    sam, grant_access_to=options.grant_mailbox_access_to
                )
                self._log(job, "success", f"Mailbox converted to shared: {mailbox.get('email')}")
                if mailbox.get("access_granted_to"):
                    self._log(job, "success",
                              f"Handover access granted to {mailbox['access_granted_to']}")
                await self._audit.record(
                    actor=job.created_by, actor_role="", action="mailbox.convert",
                    target=sam, details={**mailbox, "job": job.id},
                )
            except OnboardingError as exc:
                warnings.append(f"mailbox: {exc.message}")
                self._log(job, "warning", f"Mailbox conversion issue for '{sam}': {exc.message}")

        message = "Offboarded successfully"
        if warnings:
            message = "Offboarded with warnings: " + "; ".join(warnings)
        return UserResult(
            sam_account_name=sam, user_principal_name=target.user_principal_name,
            display_name=display, status="success", message=message,
        )
