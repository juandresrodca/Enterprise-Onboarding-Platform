"""Dashboard aggregation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_audit, get_jobs, get_provider, require
from app.models.audit import AuditQuery
from app.models.auth import CurrentUser
from app.services.audit import AuditStore
from app.services.jobs import JobManager
from app.services.provider import IdentityProvider

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(
    _: CurrentUser = Depends(require("dashboard:read")),
    provider: IdentityProvider = Depends(get_provider),
    jobs: JobManager = Depends(get_jobs),
    audit: AuditStore = Depends(get_audit),
):
    stats = await provider.stats()
    recent_audit, _total = await audit.query(AuditQuery(limit=12))
    return {
        "stats": stats,
        "pending_jobs": jobs.pending_count(),
        "recent_jobs": [j.public() for j in jobs.list(limit=6)],
        "errors_24h": await audit.error_count_last_24h(),
        "recent_activity": [e.model_dump(mode="json") for e in recent_audit],
    }
