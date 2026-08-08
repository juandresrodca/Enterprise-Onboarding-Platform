"""Offboarding endpoints: preview and execute deactivation of existing users."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import client_ip, get_jobs, get_provider, require
from app.models.auth import CurrentUser
from app.models.offboard import OffboardExecutionPlan, OffboardRequest
from app.services import offboard as offboard_svc
from app.services.jobs import JobManager
from app.services.provider import IdentityProvider

router = APIRouter(prefix="/offboard", tags=["offboard"])


@router.post("/preview", response_model=OffboardExecutionPlan)
async def preview_offboard(
    body: OffboardRequest,
    _: CurrentUser = Depends(require("users:offboard")),
    provider: IdentityProvider = Depends(get_provider),
):
    result = await offboard_svc.validate_offboard(provider, body.users, body.options)
    return offboard_svc.build_offboard_plan(result.users, body.options, issues=result.issues)


@router.post("", status_code=202)
async def execute_offboard(
    body: OffboardRequest,
    request: Request,
    user: CurrentUser = Depends(require("users:offboard")),
    provider: IdentityProvider = Depends(get_provider),
    jobs: JobManager = Depends(get_jobs),
):
    """Re-validates (defense in depth - the client always previews first,
    but the directory may have changed since) and, if still valid, queues
    the deactivation job."""
    result = await offboard_svc.validate_offboard(provider, body.users, body.options)
    if not result.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validation failed; nothing was executed.",
                "issues": [i.model_dump() for i in result.issues],
            },
        )
    targets = [u for u in result.users if u.enabled]  # already-disabled users are skipped
    if not targets:
        raise HTTPException(
            status_code=422,
            detail={"message": "Every targeted user is already disabled; nothing to do."},
        )
    job = await jobs.submit_offboard(
        targets, body.options, user, source_ip=client_ip(request)
    )
    return {"job_id": job.id, "status": job.status.value, "total": job.total}
