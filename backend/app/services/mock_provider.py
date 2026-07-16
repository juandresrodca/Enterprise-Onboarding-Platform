"""In-memory demo identity provider.

Behaves like a small AD/Entra tenant: it enforces the same failure modes the
PowerShell provider surfaces (duplicate accounts, unknown OU/groups, exhausted
licenses) so the UI and job engine can be exercised realistically. State is
persisted to a JSON file so demo data survives restarts; delete the file to
reset the demo.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.exceptions import ConflictError, NotFoundError, ProviderError
from app.services import seed_demo
from app.services.provider import IdentityProvider

log = logging.getLogger(__name__)

# Small artificial latency so progress bars and live logs are visible in demos.
_LATENCY = 0.25


def _summary(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "sam_account_name": u["sam_account_name"],
        "display_name": u["display_name"],
        "user_principal_name": u["user_principal_name"],
        "email": u.get("email"),
        "department": u.get("department"),
        "job_title": u.get("job_title"),
        "office": u.get("office"),
        "ou": u.get("ou"),
        "manager": u.get("manager"),
        "enabled": u.get("enabled", True),
        "created_at": u.get("created_at"),
        "source": u.get("source", "seed"),
        "employee_type": u.get("employee_type"),
    }


def _walk_ous(nodes: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for n in nodes:
        out.append(n["dn"])
        out.extend(_walk_ous(n.get("children", [])))
    return out


class MockProvider(IdentityProvider):
    def __init__(self, state_path: Path | None = None):
        self._state_path = state_path
        self._lock = asyncio.Lock()
        self._state = self._load()

    # --- persistence ----------------------------------------------------------
    def _load(self) -> dict[str, Any]:
        if self._state_path and self._state_path.exists():
            try:
                state = json.loads(self._state_path.read_text(encoding="utf-8"))
                if state.get("version") == 1:
                    log.info("Loaded demo directory state from %s", self._state_path)
                    return state
            except (json.JSONDecodeError, OSError):
                log.warning("Demo state file unreadable; reseeding")
        return seed_demo.build_state()

    def _save(self) -> None:
        if self._state_path:
            self._state_path.write_text(
                json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    def reset(self) -> None:
        self._state = seed_demo.build_state()
        self._save()

    # --- helpers ----------------------------------------------------------------
    @property
    def _users(self) -> list[dict[str, Any]]:
        return self._state["users"]

    def _find(self, sam: str) -> dict[str, Any] | None:
        sam = (sam or "").lower()
        return next((u for u in self._users if u["sam_account_name"] == sam), None)

    def _find_required(self, sam: str) -> dict[str, Any]:
        user = self._find(sam)
        if not user:
            raise NotFoundError(f"User '{sam}' not found in directory")
        return user

    def _license_assigned_count(self, sku: str) -> int:
        return sum(1 for u in self._users if sku in u.get("licenses", []))

    # --- read -------------------------------------------------------------------
    async def list_users(
        self, query: str = "", limit: int = 50, recent_first: bool = False
    ) -> list[dict[str, Any]]:
        await asyncio.sleep(_LATENCY / 5)
        q = (query or "").lower().strip()
        users = self._users
        if q:
            users = [
                u for u in users
                if q in u["display_name"].lower()
                or q in u["sam_account_name"]
                or q in (u.get("email") or "")
                or q in (u.get("department") or "").lower()
                or q in (u.get("job_title") or "").lower()
            ]
        if recent_first:
            users = sorted(users, key=lambda u: u.get("created_at") or "", reverse=True)
        return [_summary(u) for u in users[:limit]]

    async def get_user(self, sam: str, expand: bool = True) -> dict[str, Any] | None:
        await asyncio.sleep(_LATENCY / 5)
        user = self._find(sam)
        if not user:
            return None
        detail = dict(user)
        if expand:
            cats = {g["name"]: g["category"] for g in self._state["groups"]}
            detail["group_detail"] = [
                {"name": g, "category": cats.get(g, "security")} for g in user.get("groups", [])
            ]
            skus = {l["sku_part_number"]: l["display_name"] for l in self._state["licenses"]}
            detail["license_detail"] = [
                {"sku_part_number": s, "display_name": skus.get(s, s)}
                for s in user.get("licenses", [])
            ]
        return detail

    async def user_exists(self, sam: str = "", upn: str = "", email: str = "") -> bool:
        sam, upn, email = sam.lower(), upn.lower(), email.lower()
        for u in self._users:
            if sam and u["sam_account_name"] == sam:
                return True
            if upn and u["user_principal_name"].lower() == upn:
                return True
            if email and (u.get("email") or "").lower() == email:
                return True
            if email and any(
                p.lower().removeprefix("smtp:") == email for p in u.get("proxy_addresses", [])
            ):
                return True
        return False

    async def resolve_manager(self, ref: str) -> dict[str, Any] | None:
        ref = (ref or "").lower().strip()
        for u in self._users:
            if ref in (u["sam_account_name"], u["user_principal_name"].lower()):
                return _summary(u)
        return None

    async def list_ous(self) -> list[dict[str, Any]]:
        return self._state["ou_tree"]

    async def ou_exists(self, dn: str) -> bool:
        return dn in _walk_ous(self._state["ou_tree"])

    async def list_groups(
        self, search: str = "", category: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        q = (search or "").lower().strip()
        member_counts: dict[str, int] = {}
        for u in self._users:
            for g in u.get("groups", []):
                member_counts[g] = member_counts.get(g, 0) + 1
        out = []
        for g in self._state["groups"]:
            if category and g["category"] != category:
                continue
            if q and q not in g["name"].lower() and q not in g["description"].lower():
                continue
            out.append({**g, "member_count": member_counts.get(g["name"], 0)})
        return out[:limit]

    async def missing_groups(self, names: list[str]) -> list[str]:
        known = {g["name"].lower() for g in self._state["groups"]}
        return [n for n in names if n.lower() not in known]

    async def list_licenses(self) -> list[dict[str, Any]]:
        return [
            {**l, "assigned": self._license_assigned_count(l["sku_part_number"])}
            for l in self._state["licenses"]
        ]

    async def list_shared_mailboxes(self) -> list[dict[str, Any]]:
        return self._state["shared_mailboxes"]

    async def employee_id_exists(self, employee_id: str) -> bool:
        return any(u.get("employee_id") == employee_id for u in self._users)

    async def stats(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        recent = [
            u for u in self._users
            if u.get("created_at")
            and (now - datetime.fromisoformat(u["created_at"])).days <= 7
        ]
        licenses = await self.list_licenses()
        return {
            "total_users": len(self._users),
            "enabled_users": sum(1 for u in self._users if u.get("enabled", True)),
            "created_last_7_days": len(recent),
            "contractors": sum(
                1 for u in self._users if u.get("employee_type") == "Contractor"
            ),
            "groups": len(self._state["groups"]),
            "licenses": licenses,
            "recent_users": [
                _summary(u)
                for u in sorted(
                    self._users, key=lambda u: u.get("created_at") or "", reverse=True
                )[:8]
            ],
        }

    # --- write -----------------------------------------------------------------
    async def create_user(self, spec: dict[str, Any], password: str) -> dict[str, Any]:
        async with self._lock:
            await asyncio.sleep(_LATENCY)
            sam = spec["sam_account_name"].lower()
            if self._find(sam):
                raise ConflictError(f"sAMAccountName '{sam}' already exists")
            if await self.user_exists(upn=spec["user_principal_name"]):
                raise ConflictError(f"UPN '{spec['user_principal_name']}' already exists")
            if not await self.ou_exists(spec["ou"]):
                raise ProviderError(f"Target OU does not exist: {spec['ou']}")

            record = {
                **{k: spec.get(k) for k in (
                    "first_name", "last_name", "display_name", "user_principal_name",
                    "email", "ou", "department", "company", "office", "office_location",
                    "job_title", "employee_id", "employee_type", "cost_center",
                    "description", "manager", "phone", "mobile", "country", "city",
                    "state", "address", "postal_code", "account_expiration",
                )},
                "sam_account_name": sam,
                "enabled": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": "onboarding",
                "groups": [],
                "licenses": [],
                "mailbox": False,
                "shared_mailboxes": [],
                "proxy_addresses": list(spec.get("proxy_addresses") or []),
                "extension_attributes": dict(spec.get("extension_attributes") or {}),
                "home_folder": None,
                "profile": {},
                # Simulated only - a real directory stores a hash, never the value.
                "must_change_password": spec.get("force_change_at_logon", True),
                "password_never_expires": spec.get("password_never_expires", False),
            }
            self._users.append(record)
            self._save()
            return _summary(record)

    async def add_to_groups(self, sam: str, groups: list[str]) -> list[str]:
        async with self._lock:
            await asyncio.sleep(_LATENCY / 2)
            user = self._find_required(sam)
            missing = await self.missing_groups(groups)
            if missing:
                raise ProviderError(f"Groups not found: {', '.join(missing)}")
            added = []
            for g in groups:
                if g not in user["groups"]:
                    user["groups"].append(g)
                    added.append(g)
            self._save()
            return added

    async def assign_licenses(self, sam: str, skus: list[str]) -> list[str]:
        async with self._lock:
            await asyncio.sleep(_LATENCY / 2)
            user = self._find_required(sam)
            known = {l["sku_part_number"]: l for l in self._state["licenses"]}
            assigned = []
            for sku in skus:
                if sku not in known:
                    raise ProviderError(f"Unknown license SKU: {sku}")
                if self._license_assigned_count(sku) >= known[sku]["total"]:
                    raise ProviderError(
                        f"No '{known[sku]['display_name']}' licenses available "
                        f"({known[sku]['total']} of {known[sku]['total']} assigned)"
                    )
                if sku not in user["licenses"]:
                    user["licenses"].append(sku)
                    assigned.append(sku)
            self._save()
            return assigned

    async def create_mailbox(self, sam: str) -> dict[str, Any]:
        async with self._lock:
            await asyncio.sleep(_LATENCY)
            user = self._find_required(sam)
            user["mailbox"] = True
            primary = f"SMTP:{user['user_principal_name']}"
            if primary not in user["proxy_addresses"]:
                user["proxy_addresses"].insert(0, primary)
            user["email"] = user["user_principal_name"]
            self._save()
            return {"email": user["email"], "type": "UserMailbox"}

    async def add_shared_mailbox_access(self, sam: str, mailboxes: list[str]) -> list[str]:
        async with self._lock:
            await asyncio.sleep(_LATENCY / 2)
            user = self._find_required(sam)
            known = {m["email"].lower() for m in self._state["shared_mailboxes"]}
            granted = []
            for mb in mailboxes:
                if mb.lower() not in known:
                    raise ProviderError(f"Shared mailbox not found: {mb}")
                if mb not in user["shared_mailboxes"]:
                    user["shared_mailboxes"].append(mb)
                    granted.append(mb)
            self._save()
            return granted

    async def create_home_folder(self, sam: str, path: str, drive: str) -> dict[str, Any]:
        async with self._lock:
            await asyncio.sleep(_LATENCY / 2)
            user = self._find_required(sam)
            user["home_folder"] = {"path": path, "drive": drive}
            self._save()
            return user["home_folder"]

    async def apply_profile(self, sam: str, profile: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            await asyncio.sleep(_LATENCY / 2)
            user = self._find_required(sam)
            user["profile"] = {k: v for k, v in profile.items() if v}
            self._save()
            return user["profile"]
