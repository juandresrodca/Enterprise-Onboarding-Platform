"""Application factory and middleware wiring.

Run locally:   uvicorn app.main:app --reload --port 8000
Production:    see docs/DEPLOYMENT.md (uvicorn behind TLS, Entra ID auth)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import (
    routes_auth, routes_dashboard, routes_directory, routes_jobs, routes_logs,
    routes_meta, routes_users,
)
from app.config import get_settings
from app.core.exceptions import OnboardingError
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.services.audit import AuditStore
from app.services.jobs import JobManager
from app.services.mock_provider import MockProvider

log = logging.getLogger(__name__)


def _build_local_accounts(demo_mode: bool) -> dict:
    """Demo-mode login accounts. Empty in production: Entra ID is the IdP."""
    if not demo_mode:
        return {}
    from app.services.seed_demo import DEMO_ACCOUNTS, DEMO_PASSWORD

    pw_hash = hash_password(DEMO_PASSWORD)
    return {
        a["username"]: {**a, "password_hash": pw_hash}
        for a in DEMO_ACCOUNTS
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.logs_dir)

    if settings.demo_mode:
        provider = MockProvider(settings.demo_state_path)
        log.info("DEMO MODE: using in-memory Northwind Dynamics directory")
    else:
        from app.services.ps_provider import PowerShellProvider

        provider = PowerShellProvider(settings)
    await provider.startup()

    audit = AuditStore(settings.audit_db_path)
    jobs = JobManager(provider, audit, settings)
    await jobs.start()

    app.state.provider = provider
    app.state.audit = audit
    app.state.jobs = jobs
    app.state.local_accounts = _build_local_accounts(settings.demo_mode)

    log.info("%s v%s started (environment=%s)",
             settings.app_name, __version__, settings.environment)
    try:
        yield
    finally:
        await jobs.stop()
        await provider.shutdown()
        audit.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", settings.csrf_header_name],
    )

    _CSRF_EXEMPT = {
        f"{settings.api_prefix}/auth/login",
        f"{settings.api_prefix}/auth/entra/login",
        f"{settings.api_prefix}/auth/entra/callback",
    }

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # CSRF: double-submit cookie on every state-changing API call.
        if (
            request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith(settings.api_prefix)
            and request.url.path not in _CSRF_EXEMPT
        ):
            cookie = request.cookies.get(settings.csrf_cookie_name)
            header = request.headers.get(settings.csrf_header_name)
            if not cookie or not header or cookie != header:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing or invalid"},
                )
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if settings.cookie_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

    @app.exception_handler(OnboardingError)
    async def onboarding_error_handler(_request: Request, exc: OnboardingError):
        return JSONResponse(
            status_code=exc.http_status,
            content={"detail": exc.message, "code": exc.code, "details": exc.details},
        )

    prefix = settings.api_prefix
    app.include_router(routes_meta.router, prefix=prefix)
    app.include_router(routes_auth.router, prefix=prefix)
    app.include_router(routes_users.router, prefix=prefix)
    app.include_router(routes_directory.router, prefix=prefix)
    app.include_router(routes_jobs.router, prefix=prefix)
    app.include_router(routes_logs.router, prefix=prefix)
    app.include_router(routes_dashboard.router, prefix=prefix)

    # Spec-mandated top-level aliases (POST /validate, POST /preview) that
    # share the /users handlers.
    app.add_api_route(
        f"{prefix}/validate", routes_users.validate_users, methods=["POST"],
        tags=["users"],
    )
    app.add_api_route(
        f"{prefix}/preview", routes_users.preview_users, methods=["POST"],
        tags=["users"],
    )
    return app


app = create_app()
