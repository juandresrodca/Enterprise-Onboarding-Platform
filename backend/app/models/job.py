from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class JobLogEntry(BaseModel):
    ts: datetime
    level: str  # info | success | warning | error
    message: str


class UserResult(BaseModel):
    sam_account_name: str
    user_principal_name: str
    display_name: str
    status: str  # success | error
    message: str = ""
    generated_password: str | None = None  # shown once, never persisted


class Job(BaseModel):
    id: str
    type: str  # onboard | clone
    status: JobStatus = JobStatus.QUEUED
    created_by: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total: int = 0
    done: int = 0
    errors: int = 0
    logs: list[JobLogEntry] = Field(default_factory=list)
    results: list[UserResult] = Field(default_factory=list)
    payload_summary: dict[str, Any] = Field(default_factory=dict)

    def public(self, include_passwords: bool = False) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        if not include_passwords:
            for r in data["results"]:
                r.pop("generated_password", None)
        return data
