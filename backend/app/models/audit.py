from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntry(BaseModel):
    id: int | None = None
    ts: datetime
    actor: str
    actor_role: str
    action: str
    target: str = ""
    status: str = "success"  # success | warning | error
    computer: str = ""
    source_ip: str = ""
    details: dict[str, Any] | None = None


class AuditQuery(BaseModel):
    actor: str | None = None
    action: str | None = None
    status: str | None = None
    target: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = 100
    offset: int = 0
