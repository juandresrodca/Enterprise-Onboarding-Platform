from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.rbac import Role


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class CurrentUser(BaseModel):
    username: str
    display_name: str
    role: Role
    auth_source: str = "local"


class SessionInfo(BaseModel):
    username: str
    display_name: str
    role: Role
    role_label: str
    permissions: list[str]
    expires_at: datetime
    demo_mode: bool
    auth_source: str
    # Mirrored CSRF token for cross-site frontends (e.g. GitHub Pages) that
    # cannot read the csrf cookie of the API origin. Same value as the cookie.
    csrf_token: str | None = None
