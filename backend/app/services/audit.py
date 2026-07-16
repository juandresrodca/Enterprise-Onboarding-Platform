"""SQLite-backed audit trail.

Records who did what, when, from where, with structured detail. SQLite keeps
the platform dependency-free; the store is small and swappable (the interface
is async, so a Postgres implementation can drop in behind it).
"""

from __future__ import annotations

import asyncio
import json
import socket
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.models.audit import AuditEntry, AuditQuery

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    actor_role TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'success',
    computer TEXT NOT NULL DEFAULT '',
    source_ip TEXT NOT NULL DEFAULT '',
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit (ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit (actor);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit (action);
"""


class AuditStore:
    def __init__(self, db_path: Path):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        self._computer = socket.gethostname()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- write ------------------------------------------------------------------
    async def record(
        self, *, actor: str, actor_role: str, action: str, target: str = "",
        status: str = "success", source_ip: str = "", details: dict[str, Any] | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._record_sync, actor, actor_role, action, target, status, source_ip, details
        )

    def _record_sync(
        self, actor: str, actor_role: str, action: str, target: str,
        status: str, source_ip: str, details: dict[str, Any] | None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit (ts, actor, actor_role, action, target, status,"
                " computer, source_ip, details) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(), actor, actor_role, action,
                    target, status, self._computer, source_ip,
                    json.dumps(details, ensure_ascii=False, default=str) if details else None,
                ),
            )
            self._conn.commit()

    # --- read -------------------------------------------------------------------
    async def query(self, q: AuditQuery) -> tuple[list[AuditEntry], int]:
        return await asyncio.to_thread(self._query_sync, q)

    def _query_sync(self, q: AuditQuery) -> tuple[list[AuditEntry], int]:
        clauses, params = [], []
        if q.actor:
            clauses.append("actor LIKE ?")
            params.append(f"%{q.actor}%")
        if q.action:
            clauses.append("action = ?")
            params.append(q.action)
        if q.status:
            clauses.append("status = ?")
            params.append(q.status)
        if q.target:
            clauses.append("target LIKE ?")
            params.append(f"%{q.target}%")
        if q.date_from:
            clauses.append("ts >= ?")
            params.append(q.date_from.isoformat())
        if q.date_to:
            clauses.append("ts <= ?")
            params.append(q.date_to.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM audit {where}", params
            ).fetchone()[0]
            rows = self._conn.execute(
                f"SELECT * FROM audit {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                [*params, q.limit, q.offset],
            ).fetchall()

        entries = [
            AuditEntry(
                id=r["id"], ts=datetime.fromisoformat(r["ts"]), actor=r["actor"],
                actor_role=r["actor_role"], action=r["action"], target=r["target"],
                status=r["status"], computer=r["computer"], source_ip=r["source_ip"],
                details=json.loads(r["details"]) if r["details"] else None,
            )
            for r in rows
        ]
        return entries, total

    async def distinct_actions(self) -> list[str]:
        def _sync() -> list[str]:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT DISTINCT action FROM audit ORDER BY action"
                ).fetchall()
            return [r[0] for r in rows]
        return await asyncio.to_thread(_sync)

    async def error_count_last_24h(self) -> int:
        def _sync() -> int:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            with self._lock:
                return self._conn.execute(
                    "SELECT COUNT(*) FROM audit WHERE status='error' AND ts >= ?",
                    (cutoff,),
                ).fetchone()[0]
        return await asyncio.to_thread(_sync)
