"""Role-based access control.

Roles are ordered from least to most privileged. Permissions are explicit
grants; a role only gets what is listed for it (no implicit inheritance),
which keeps the matrix auditable.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    HELPDESK = "helpdesk"
    HR = "hr"
    ADMIN = "admin"
    GLOBAL_ADMIN = "global_admin"


ROLE_LABELS: dict[Role, str] = {
    Role.HELPDESK: "Helpdesk",
    Role.HR: "HR",
    Role.ADMIN: "Administrator",
    Role.GLOBAL_ADMIN: "Global Admin",
}

_ALL = {Role.HELPDESK, Role.HR, Role.ADMIN, Role.GLOBAL_ADMIN}
_HR_UP = {Role.HR, Role.ADMIN, Role.GLOBAL_ADMIN}
_ADMIN_UP = {Role.ADMIN, Role.GLOBAL_ADMIN}

PERMISSIONS: dict[str, set[Role]] = {
    "dashboard:read": _ALL,
    "users:read": _ALL,
    "users:create": _HR_UP,
    "users:bulk": _HR_UP,
    "users:clone": _ADMIN_UP,
    "directory:read": _ALL,
    "jobs:read": _ALL,
    "logs:read": _ALL,
    "logs:export": _ADMIN_UP,
    "settings:read": _ADMIN_UP,
    "settings:write": {Role.GLOBAL_ADMIN},
}


def role_has(role: Role, permission: str) -> bool:
    allowed = PERMISSIONS.get(permission)
    return allowed is not None and role in allowed


def permissions_for(role: Role) -> list[str]:
    return sorted(p for p, roles in PERMISSIONS.items() if role in roles)
