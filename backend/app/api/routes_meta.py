"""Health check and platform settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app import __version__
from app.api.deps import client_ip, get_audit, require
from app.config import Settings, get_settings
from app.models.auth import CurrentUser
from app.services.audit import AuditStore

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "version": __version__,
        "demo_mode": settings.demo_mode,
    }


def _settings_view(settings: Settings) -> dict:
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "demo_mode": settings.demo_mode,
        "entra_enabled": settings.entra_enabled,
        "domain_dns": settings.domain_dns,
        "upn_suffix": settings.upn_suffix,
        "sam_naming_regex": settings.sam_naming_regex,
        "session_timeout_minutes": settings.session_timeout_minutes,
        "default_home_base_path": settings.default_home_base_path,
        "password_policy": settings.password_policy.model_dump(),
    }


@router.get("/settings")
async def read_settings(
    _: CurrentUser = Depends(require("settings:read")),
    settings: Settings = Depends(get_settings),
):
    return _settings_view(settings)


class SettingsUpdate(BaseModel):
    min_length: int | None = Field(default=None, ge=8, le=64)
    require_uppercase: bool | None = None
    require_lowercase: bool | None = None
    require_digit: bool | None = None
    require_symbol: bool | None = None
    generated_length: int | None = Field(default=None, ge=12, le=64)
    max_age_days: int | None = Field(default=None, ge=0, le=730)
    sam_naming_regex: str | None = None


@router.put("/settings")
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    user: CurrentUser = Depends(require("settings:write")),
    settings: Settings = Depends(get_settings),
    audit: AuditStore = Depends(get_audit),
):
    changes = body.model_dump(exclude_none=True)
    if "sam_naming_regex" in changes:
        import re
        try:
            re.compile(changes["sam_naming_regex"])
        except re.error as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=f"Invalid regex: {exc}") from None
        settings.sam_naming_regex = changes.pop("sam_naming_regex")
    for key, value in changes.items():
        setattr(settings.password_policy, key, value)
    await audit.record(
        actor=user.username, actor_role=user.role.value, action="settings.update",
        source_ip=client_ip(request), details=body.model_dump(exclude_none=True),
    )
    return _settings_view(settings)
