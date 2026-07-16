"""Structured JSON logging.

Every record is emitted as one JSON object per line to both stderr and a
rotating file under the project logs/ directory, so log shippers (Sentinel,
Splunk, ELK) can ingest them without parsing rules.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "context", None)
        if extra:
            entry["context"] = extra
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if any(getattr(h, "_eio_handler", False) for h in root.handlers):
        return  # already configured (e.g. test re-entry)
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(JsonFormatter())
    console._eio_handler = True  # type: ignore[attr-defined]
    root.addHandler(console)

    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "backend.jsonl", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())
    file_handler._eio_handler = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
