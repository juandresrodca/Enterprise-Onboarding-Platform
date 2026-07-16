"""Identity provider abstraction.

The API layer and job engine only ever talk to this interface. Two
implementations exist:

* MockProvider     - in-memory demo directory (DEMO_MODE), fully functional.
* PowerShellProvider - drives PowerShell 7 scripts against AD / Entra ID.

This is the seam that lets every feature be developed and tested without a
domain controller, and swapped to production without touching callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IdentityProvider(ABC):
    """All methods raise app.core.exceptions.ProviderError on failure and
    return JSON-serializable dicts/lists."""

    # --- read ---------------------------------------------------------------
    @abstractmethod
    async def list_users(
        self, query: str = "", limit: int = 50, recent_first: bool = False
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_user(self, sam: str, expand: bool = True) -> dict[str, Any] | None:
        """Full detail including groups, licenses, mailboxes, proxy addresses,
        extension attributes. Used by the Clone feature."""

    @abstractmethod
    async def user_exists(self, sam: str = "", upn: str = "", email: str = "") -> bool: ...

    @abstractmethod
    async def resolve_manager(self, ref: str) -> dict[str, Any] | None:
        """Resolve a sAMAccountName or UPN to a user summary, or None."""

    @abstractmethod
    async def list_ous(self) -> list[dict[str, Any]]:
        """OU tree: [{name, dn, children: [...]}]."""

    @abstractmethod
    async def ou_exists(self, dn: str) -> bool: ...

    @abstractmethod
    async def list_groups(
        self, search: str = "", category: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def missing_groups(self, names: list[str]) -> list[str]: ...

    @abstractmethod
    async def list_licenses(self) -> list[dict[str, Any]]:
        """[{sku_part_number, display_name, total, assigned}]"""

    @abstractmethod
    async def list_shared_mailboxes(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def employee_id_exists(self, employee_id: str) -> bool: ...

    @abstractmethod
    async def stats(self) -> dict[str, Any]:
        """Dashboard counters: total_users, enabled_users, recent list, etc."""

    # --- write --------------------------------------------------------------
    @abstractmethod
    async def create_user(self, spec: dict[str, Any], password: str) -> dict[str, Any]:
        """Create the account with all directory attributes. Returns summary."""

    @abstractmethod
    async def add_to_groups(self, sam: str, groups: list[str]) -> list[str]:
        """Returns the list of groups actually added."""

    @abstractmethod
    async def assign_licenses(self, sam: str, skus: list[str]) -> list[str]: ...

    @abstractmethod
    async def create_mailbox(self, sam: str) -> dict[str, Any]: ...

    @abstractmethod
    async def add_shared_mailbox_access(self, sam: str, mailboxes: list[str]) -> list[str]: ...

    @abstractmethod
    async def create_home_folder(self, sam: str, path: str, drive: str) -> dict[str, Any]: ...

    @abstractmethod
    async def apply_profile(self, sam: str, profile: dict[str, Any]) -> dict[str, Any]: ...

    # --- lifecycle ------------------------------------------------------------
    async def startup(self) -> None:  # pragma: no cover - optional hook
        return

    async def shutdown(self) -> None:  # pragma: no cover - optional hook
        return
