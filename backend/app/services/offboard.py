"""Validation and execution-plan building for offboarding batches.

Mirrors app.services.validation + app.services.preview but for deactivating
existing users instead of creating new ones: same normalize-then-check shape,
same "nothing runs without an approved plan" contract.
"""

from __future__ import annotations

from app.models.offboard import (
    OffboardExecutionPlan, OffboardOptions, OffboardResolvedUser, OffboardTarget,
    OffboardUserPlan, OffboardValidationResult,
)
from app.models.user import PlanAction, ValidationIssue
from app.services.provider import IdentityProvider


async def validate_offboard(
    provider: IdentityProvider, targets: list[OffboardTarget], options: OffboardOptions,
) -> OffboardValidationResult:
    issues: list[ValidationIssue] = []
    resolved: list[OffboardResolvedUser] = []
    seen_sams: set[str] = set()

    # Batch-wide option checks apply identically to every target, so resolve
    # them once and attach to each index rather than re-querying per user.
    global_issues: list[tuple[str, str, str]] = []
    if options.move_to_ou and not await provider.ou_exists(options.move_to_ou):
        global_issues.append(
            ("move_to_ou", "invalid_ou", f"Target OU does not exist: {options.move_to_ou}")
        )
    if options.grant_mailbox_access_to:
        manager = await provider.resolve_manager(options.grant_mailbox_access_to)
        if not manager:
            global_issues.append((
                "grant_mailbox_access_to", "invalid_manager",
                f"Handover recipient '{options.grant_mailbox_access_to}' was not found",
            ))

    for i, target in enumerate(targets):
        sam = target.sam_account_name.strip().lower()

        def issue(field: str, code: str, message: str, severity: str = "error") -> None:
            issues.append(ValidationIssue(
                index=i, field=field, code=code, severity=severity, message=message
            ))

        for field, code, message in global_issues:
            issue(field, code, message)

        if sam in seen_sams:
            issue("sam_account_name", "duplicate_in_batch",
                  f"'{sam}' appears more than once in this batch")
        seen_sams.add(sam)

        if (
            options.grant_mailbox_access_to
            and options.grant_mailbox_access_to.strip().lower() == sam
        ):
            issue("grant_mailbox_access_to", "self_reference",
                  "A user cannot receive handover access to their own mailbox")

        user = await provider.get_user(sam, expand=False)
        if not user:
            issue("sam_account_name", "not_found", f"User '{sam}' was not found in the directory")
            continue
        if not user.get("enabled", True):
            issue("sam_account_name", "already_disabled",
                  f"'{sam}' is already disabled and will be skipped", severity="warning")

        resolved.append(OffboardResolvedUser(
            sam_account_name=user["sam_account_name"],
            display_name=user["display_name"],
            user_principal_name=user["user_principal_name"],
            email=user.get("email"),
            ou=user.get("ou"),
            enabled=user.get("enabled", True),
            reason=target.reason,
        ))

    valid = not any(i.severity == "error" for i in issues)
    return OffboardValidationResult(valid=valid, issues=issues, users=resolved)


def build_offboard_plan(
    users: list[OffboardResolvedUser], options: OffboardOptions,
    issues: list[ValidationIssue] | None = None,
) -> OffboardExecutionPlan:
    plans: list[OffboardUserPlan] = []
    total_actions = 0

    for i, u in enumerate(users):
        actions: list[PlanAction] = []
        warnings = [
            iss.message for iss in (issues or [])
            if iss.index == i and iss.severity == "warning"
        ]

        details = ["Account will no longer be able to sign in"]
        if options.reset_password:
            details.append("Password will be randomized")
        actions.append(PlanAction(kind="disable", summary="Disable Active Directory account",
                                  details=details))

        if options.remove_from_groups:
            scope = (
                "all groups except distribution lists"
                if options.keep_distribution_lists else "all groups"
            )
            actions.append(PlanAction(kind="groups", summary=f"Remove from {scope}"))
        if options.revoke_licenses:
            actions.append(PlanAction(
                kind="licenses", summary="Revoke all Microsoft 365 licenses"))
        if options.convert_mailbox_to_shared:
            det = ["Mailbox becomes a shared mailbox (preserves mail history)"]
            if options.grant_mailbox_access_to:
                det.append(f"Full Access granted to: {options.grant_mailbox_access_to}")
            actions.append(PlanAction(kind="mailbox", summary="Convert mailbox to shared",
                                      details=det))
        if options.move_to_ou:
            actions.append(PlanAction(kind="move_ou", summary="Move to disabled-users OU",
                                      details=[f"New OU: {options.move_to_ou}"]))
        if u.reason:
            actions.append(PlanAction(kind="reason", summary=f"Offboarding reason: {u.reason}"))

        total_actions += len(actions)
        plans.append(OffboardUserPlan(
            sam_account_name=u.sam_account_name, display_name=u.display_name,
            user_principal_name=u.user_principal_name, email=u.email, ou=u.ou,
            actions=actions, warnings=warnings,
        ))

    return OffboardExecutionPlan(
        summary=f"{len(users)} user(s) will be offboarded with {total_actions} total actions",
        total_users=len(users), total_actions=total_actions, users=plans,
        issues=issues or [],
    )
