"""Audit log queries and CSV/JSON/PDF export."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import client_ip, get_audit, require
from app.models.audit import AuditQuery
from app.models.auth import CurrentUser
from app.services import exporter
from app.services.audit import AuditStore

router = APIRouter(prefix="/logs", tags=["logs"])


def _parse_query(
    actor: str | None = None,
    action: str | None = None,
    status: str | None = None,
    target: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AuditQuery:
    return AuditQuery(
        actor=actor, action=action, status=status, target=target,
        date_from=date_from, date_to=date_to, limit=min(limit, 500), offset=offset,
    )


@router.get("")
async def query_logs(
    q: AuditQuery = Depends(_parse_query),
    _: CurrentUser = Depends(require("logs:read")),
    audit: AuditStore = Depends(get_audit),
):
    entries, total = await audit.query(q)
    return {
        "entries": [e.model_dump(mode="json") for e in entries],
        "total": total,
        "actions": await audit.distinct_actions(),
    }


@router.get("/export")
async def export_logs(
    request: Request,
    format: str = "csv",
    q: AuditQuery = Depends(_parse_query),
    user: CurrentUser = Depends(require("logs:export")),
    audit: AuditStore = Depends(get_audit),
):
    if format not in exporter.CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="format must be csv, json or pdf")
    q.limit = 10_000
    entries, _total = await audit.query(q)
    content_type, render = exporter.CONTENT_TYPES[format]
    payload = render(entries)
    await audit.record(
        actor=user.username, actor_role=user.role.value, action="logs.export",
        source_ip=client_ip(request), details={"format": format, "entries": len(entries)},
    )
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return Response(
        content=payload,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=audit-{stamp}.{format}"
        },
    )
