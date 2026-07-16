"""Job status and Server-Sent Events progress stream."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_jobs, require
from app.core.exceptions import NotFoundError
from app.models.auth import CurrentUser
from app.services.jobs import JobManager

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    limit: int = 50,
    _: CurrentUser = Depends(require("jobs:read")),
    jobs: JobManager = Depends(get_jobs),
):
    return {"jobs": [j.public() for j in jobs.list(limit=min(limit, 200))]}


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    _: CurrentUser = Depends(require("jobs:read")),
    jobs: JobManager = Depends(get_jobs),
):
    job = jobs.get(job_id)
    if not job:
        raise NotFoundError(f"Job '{job_id}' not found")
    # Generated passwords are only exposed on the live stream / this detail
    # endpoint to the authenticated session that can read jobs; they are never
    # persisted anywhere.
    return {"job": job.public(include_passwords=True)}


@router.get("/{job_id}/events")
async def job_events(
    job_id: str,
    _: CurrentUser = Depends(require("jobs:read")),
    jobs: JobManager = Depends(get_jobs),
):
    async def stream():
        async for event in jobs.events(job_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
