"""Authentication: local demo accounts + Microsoft Entra ID (OIDC auth-code).

Demo mode ships four local accounts (see seed_demo.DEMO_ACCOUNTS). In
production, local login is disabled and sign-in goes through Entra ID; app
roles configured on the Entra app registration map to platform roles.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import client_ip, get_audit, get_current_user
from app.config import Settings, get_settings
from app.core.rbac import ROLE_LABELS, Role, permissions_for
from app.core.security import (
    create_session_token, generate_csrf_token, verify_password,
)
from app.models.auth import CurrentUser, LoginRequest, SessionInfo
from app.services.audit import AuditStore

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# OIDC state -> (msal auth-code flow, created_monotonic)
_auth_flows: dict[str, tuple[dict, float]] = {}


def _failures(request: Request) -> dict[str, tuple[int, float]]:
    """Per-app-instance map of username|ip -> (failure_count, first_failure)."""
    if not hasattr(request.app.state, "login_failures"):
        request.app.state.login_failures = {}
    return request.app.state.login_failures


def _set_session_cookies(
    response: Response, settings: Settings, *, username: str, display_name: str,
    role: str, auth_source: str,
) -> tuple[str, str]:
    """Returns (expires_iso, csrf_token). The CSRF token is also mirrored in
    the response body so cross-site frontends (which cannot read this origin's
    cookies) can send it back in the X-CSRF-Token header."""
    token, expires = create_session_token(
        secret=settings.secret_key, username=username, display_name=display_name,
        role=role, timeout_minutes=settings.session_timeout_minutes,
        auth_source=auth_source,
    )
    max_age = settings.session_timeout_minutes * 60
    samesite = settings.cookie_samesite
    csrf = generate_csrf_token()
    response.set_cookie(
        settings.cookie_name, token, max_age=max_age, httponly=True,
        secure=settings.cookie_secure, samesite=samesite, path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name, csrf, max_age=max_age,
        httponly=False, secure=settings.cookie_secure, samesite=samesite, path="/",
    )
    return expires.isoformat(), csrf


def _check_lockout(failures: dict, key: str, settings: Settings) -> None:
    entry = failures.get(key)
    if not entry:
        return
    count, first = entry
    window = settings.login_lockout_minutes * 60
    if time.monotonic() - first > window:
        failures.pop(key, None)
        return
    if count >= settings.login_max_attempts:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in "
                   f"{settings.login_lockout_minutes} minutes.",
        )


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    audit: AuditStore = Depends(get_audit),
):
    accounts: dict = request.app.state.local_accounts
    if not accounts:
        raise HTTPException(
            status_code=403,
            detail="Local login is disabled. Sign in with Microsoft Entra ID.",
        )
    ip = client_ip(request)
    key = f"{body.username.lower()}|{ip}"
    failures = _failures(request)
    _check_lockout(failures, key, settings)

    account = accounts.get(body.username.lower())
    if not account or not verify_password(body.password, account["password_hash"]):
        count, first = failures.get(key, (0, time.monotonic()))
        failures[key] = (count + 1, first)
        await audit.record(
            actor=body.username, actor_role="", action="auth.login", status="error",
            source_ip=ip, details={"reason": "invalid credentials"},
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    failures.pop(key, None)
    expires, csrf = _set_session_cookies(
        response, settings, username=account["username"],
        display_name=account["display_name"], role=account["role"], auth_source="local",
    )
    await audit.record(
        actor=account["username"], actor_role=account["role"], action="auth.login",
        source_ip=ip,
    )
    role = Role(account["role"])
    return SessionInfo(
        username=account["username"], display_name=account["display_name"], role=role,
        role_label=ROLE_LABELS[role], permissions=permissions_for(role),
        expires_at=expires, demo_mode=settings.demo_mode, auth_source="local",
        csrf_token=csrf,
    )


@router.get("/me")
async def me(
    request: Request,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> SessionInfo:
    # Sliding session: touching /me refreshes the cookie.
    expires, csrf = _set_session_cookies(
        response, settings, username=user.username, display_name=user.display_name,
        role=user.role.value, auth_source=user.auth_source,
    )
    return SessionInfo(
        username=user.username, display_name=user.display_name, role=user.role,
        role_label=ROLE_LABELS[user.role], permissions=permissions_for(user.role),
        expires_at=expires, demo_mode=settings.demo_mode, auth_source=user.auth_source,
        csrf_token=csrf,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    audit: AuditStore = Depends(get_audit),
    user: CurrentUser = Depends(get_current_user),
):
    response.delete_cookie(settings.cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    await audit.record(
        actor=user.username, actor_role=user.role.value, action="auth.logout",
        source_ip=client_ip(request),
    )
    return {"detail": "Signed out"}


# --- Microsoft Entra ID (OIDC authorization-code flow via MSAL) ----------------

def _msal_app(settings: Settings):
    import msal

    return msal.ConfidentialClientApplication(
        settings.entra_client_id,
        client_credential=settings.entra_client_secret,
        authority=f"https://login.microsoftonline.com/{settings.entra_tenant_id}",
    )


@router.get("/entra/login")
async def entra_login(settings: Settings = Depends(get_settings)):
    if not settings.entra_enabled:
        raise HTTPException(status_code=404, detail="Entra ID sign-in is not configured")
    app = _msal_app(settings)
    state = uuid.uuid4().hex
    flow = app.initiate_auth_code_flow(
        scopes=["User.Read"], redirect_uri=settings.entra_redirect_uri, state=state,
    )
    now = time.monotonic()
    _auth_flows[state] = (flow, now)
    for s, (_, created) in list(_auth_flows.items()):  # prune flows older than 10 min
        if now - created > 600:
            _auth_flows.pop(s, None)
    return RedirectResponse(flow["auth_uri"], status_code=302)


@router.get("/entra/callback")
async def entra_callback(
    request: Request,
    settings: Settings = Depends(get_settings),
    audit: AuditStore = Depends(get_audit),
):
    if not settings.entra_enabled:
        raise HTTPException(status_code=404, detail="Entra ID sign-in is not configured")
    params = dict(request.query_params)
    stored = _auth_flows.pop(params.get("state", ""), None)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid or expired sign-in state")

    app = _msal_app(settings)
    try:
        result = app.acquire_token_by_auth_code_flow(stored[0], params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Sign-in failed: {exc}") from None
    if "error" in result:
        raise HTTPException(
            status_code=401,
            detail=result.get("error_description", "Entra ID sign-in failed"),
        )

    claims = result.get("id_token_claims", {})
    username = claims.get("preferred_username") or claims.get("upn") or claims.get("oid")
    display_name = claims.get("name") or username
    app_roles = claims.get("roles") or []
    mapped = [settings.entra_role_map[r] for r in app_roles if r in settings.entra_role_map]
    if not mapped:
        await audit.record(
            actor=username, actor_role="", action="auth.login", status="error",
            source_ip=client_ip(request), details={"reason": "no app role assigned"},
        )
        raise HTTPException(
            status_code=403,
            detail="Your account has no onboarding role assigned in Entra ID.",
        )
    # Highest-privilege assigned role wins.
    order = ["global_admin", "admin", "hr", "helpdesk"]
    role = next(r for r in order if r in mapped)

    frontend = settings.cors_origins[0] if settings.cors_origins else "/"
    response = RedirectResponse(frontend, status_code=302)
    _set_session_cookies(
        response, settings, username=username, display_name=display_name,
        role=role, auth_source="entra",
    )
    await audit.record(
        actor=username, actor_role=role, action="auth.login",
        source_ip=client_ip(request), details={"source": "entra"},
    )
    return response
