"""Production identity provider backed by PowerShell 7 scripts.

Each method maps 1:1 to a script in powershell/scripts/ (see docs/POWERSHELL.md
for the JSON contract). Read paths hit AD via the ActiveDirectory module; cloud
operations (licenses, mailboxes, M365 groups) go through Microsoft Graph and
Exchange Online inside the scripts.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.services.powershell import PowerShellRunner
from app.services.provider import IdentityProvider


class PowerShellProvider(IdentityProvider):
    def __init__(self, settings: Settings, runner: PowerShellRunner | None = None):
        self._settings = settings
        self._runner = runner or PowerShellRunner(settings)

    async def startup(self) -> None:
        # Fail fast if the AD module / domain is unreachable.
        await self._runner.run("Connect-AD.ps1", {})

    # --- read -----------------------------------------------------------------
    async def list_users(
        self, query: str = "", limit: int = 50, recent_first: bool = False
    ) -> list[dict[str, Any]]:
        data = await self._runner.run(
            "Get-Users.ps1", {"query": query, "limit": limit, "recentFirst": recent_first}
        )
        return data.get("users", [])

    async def get_user(self, sam: str, expand: bool = True) -> dict[str, Any] | None:
        data = await self._runner.run("Get-User.ps1", {"sam": sam, "expand": expand})
        return data.get("user")

    async def user_exists(self, sam: str = "", upn: str = "", email: str = "") -> bool:
        data = await self._runner.run(
            "Validation.ps1",
            {"check": "identity", "sam": sam, "upn": upn, "email": email},
        )
        return bool(data.get("exists"))

    async def resolve_manager(self, ref: str) -> dict[str, Any] | None:
        data = await self._runner.run("Validation.ps1", {"check": "manager", "manager": ref})
        return data.get("manager")

    async def list_ous(self) -> list[dict[str, Any]]:
        data = await self._runner.run("Get-OUTree.ps1", {})
        return data.get("tree", [])

    async def ou_exists(self, dn: str) -> bool:
        data = await self._runner.run("Validation.ps1", {"check": "ou", "ou": dn})
        return bool(data.get("exists"))

    async def list_groups(
        self, search: str = "", category: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        data = await self._runner.run(
            "Get-Groups.ps1", {"search": search, "category": category, "limit": limit}
        )
        return data.get("groups", [])

    async def missing_groups(self, names: list[str]) -> list[str]:
        if not names:
            return []
        data = await self._runner.run("Validation.ps1", {"check": "groups", "groups": names})
        return data.get("missing", [])

    async def list_licenses(self) -> list[dict[str, Any]]:
        data = await self._runner.run("Assign-Licenses.ps1", {"action": "list"})
        return data.get("licenses", [])

    async def list_shared_mailboxes(self) -> list[dict[str, Any]]:
        data = await self._runner.run("Create-Mailbox.ps1", {"action": "list-shared"})
        return data.get("mailboxes", [])

    async def employee_id_exists(self, employee_id: str) -> bool:
        data = await self._runner.run(
            "Validation.ps1", {"check": "employeeId", "employeeId": employee_id}
        )
        return bool(data.get("exists"))

    async def stats(self) -> dict[str, Any]:
        return await self._runner.run("Get-Stats.ps1", {})

    # --- write ----------------------------------------------------------------
    async def create_user(self, spec: dict[str, Any], password: str) -> dict[str, Any]:
        data = await self._runner.run(
            "Create-ADUser.ps1",
            {"user": spec, "password": password, "domain": self._settings.domain_dns},
        )
        return data.get("user", {})

    async def add_to_groups(self, sam: str, groups: list[str]) -> list[str]:
        data = await self._runner.run("Assign-Groups.ps1", {"sam": sam, "groups": groups})
        return data.get("added", [])

    async def assign_licenses(self, sam: str, skus: list[str]) -> list[str]:
        data = await self._runner.run(
            "Assign-Licenses.ps1", {"action": "assign", "sam": sam, "skus": skus}
        )
        return data.get("assigned", [])

    async def create_mailbox(self, sam: str) -> dict[str, Any]:
        data = await self._runner.run("Create-Mailbox.ps1", {"action": "create", "sam": sam})
        return data.get("mailbox", {})

    async def add_shared_mailbox_access(self, sam: str, mailboxes: list[str]) -> list[str]:
        data = await self._runner.run(
            "Create-Mailbox.ps1", {"action": "grant-shared", "sam": sam, "mailboxes": mailboxes}
        )
        return data.get("granted", [])

    async def create_home_folder(self, sam: str, path: str, drive: str) -> dict[str, Any]:
        data = await self._runner.run(
            "Create-HomeFolder.ps1", {"sam": sam, "path": path, "drive": drive}
        )
        return data.get("homeFolder", {})

    async def apply_profile(self, sam: str, profile: dict[str, Any]) -> dict[str, Any]:
        data = await self._runner.run("Create-Profile.ps1", {"sam": sam, **profile})
        return data.get("profile", {})
