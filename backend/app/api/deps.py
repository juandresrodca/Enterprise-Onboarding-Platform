"""FastAPI dependencies: DI accessors, authentication, RBAC enforcement."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.config import Settings, get_settings
from app.core.rbac import Role, role_has
from app.core.security import decode_session_token
from app.models.auth import CurrentUser
from app.services.audit import AuditStore
from app.services.jobs import JobManager
from app.services.provider import IdentityProvider
from app.services.validation import Validator


def get_provider(request: Request) -> IdentityProvider:
    return request.app.state.provider


def get_audit(request: Request) -> AuditStore:
    return request.app.state.audit


def get_jobs(request: Request) -> JobManager:
    return request.app.state.jobs


def get_validator(
    provider: IdentityProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings),
) -> Validator:
    return Validator(provider, settings)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


async def get_current_user(
    request: Request, settings: Settings = Depends(get_settings)
) -> CurrentUser:
    token = request.cookies.get(settings.cookie_name)
    payload = decode_session_token(token, settings.secret_key) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        role = Role(payload.get("role", ""))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session role") from None
    return CurrentUser(
        username=payload["sub"],
        display_name=payload.get("name", payload["sub"]),
        role=role,
        auth_source=payload.get("src", "local"),
    )


def require(permission: str):
    """Dependency factory: authenticated user with the given permission."""

    async def dependency(
        request: Request,
        user: CurrentUser = Depends(get_current_user),
        audit: AuditStore = Depends(get_audit),
    ) -> CurrentUser:
        if not role_has(user.role, permission):
            await audit.record(
                actor=user.username, actor_role=user.role.value, action="auth.denied",
                target=f"{request.method} {request.url.path}", status="warning",
                source_ip=client_ip(request), details={"permission": permission},
            )
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role.value}' lacks permission '{permission}'",
            )
        return user

    return dependency
