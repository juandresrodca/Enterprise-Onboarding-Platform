"""Async PowerShell script runner.

Contract with the scripts in powershell/scripts/:
  * Parameters are passed as a single JSON document on stdin (never on the
    command line, so secrets don't leak into process listings or event logs).
  * The script prints exactly one JSON object on stdout:
      { "success": bool, "data": {...}, "error": {"code","message"}, "logs": [...] }
  * Human/diagnostic output goes to stderr or the module's log file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.exceptions import ScriptExecutionError

log = logging.getLogger(__name__)


class PowerShellRunner:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_scripts)
        self._exe = self._resolve_executable()

    def _resolve_executable(self) -> str:
        for candidate in (self._settings.powershell_executable, self._settings.powershell_fallback):
            path = shutil.which(candidate)
            if path:
                if candidate != self._settings.powershell_executable:
                    log.warning(
                        "PowerShell 7 (%s) not found; falling back to %s. "
                        "Production requires PowerShell 7+.",
                        self._settings.powershell_executable, candidate,
                    )
                return path
        raise ScriptExecutionError(
            "No PowerShell executable found. Install PowerShell 7+ (pwsh)."
        )

    def script_path(self, name: str) -> Path:
        path = (self._settings.scripts_dir / name).resolve()
        # Guard against path traversal in script names.
        if path.parent != self._settings.scripts_dir.resolve() or path.suffix != ".ps1":
            raise ScriptExecutionError(f"Invalid script name: {name}")
        if not path.exists():
            raise ScriptExecutionError(f"Script not found: {path}")
        return path

    async def run(self, script: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a script and return its `data` payload. Raises ScriptExecutionError."""
        path = self.script_path(script)
        stdin_payload = json.dumps(params or {}, ensure_ascii=False, default=str).encode("utf-8")

        async with self._semaphore:
            proc = await asyncio.create_subprocess_exec(
                self._exe,
                "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(stdin_payload),
                    timeout=self._settings.script_timeout_seconds,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise ScriptExecutionError(
                    f"{script} timed out after {self._settings.script_timeout_seconds}s"
                )

        return self._parse_result(script, proc.returncode, stdout, stderr)

    def _parse_result(
        self, script: str, returncode: int | None, stdout: bytes, stderr: bytes
    ) -> dict[str, Any]:
        text = stdout.decode("utf-8", errors="replace").strip()
        result: dict[str, Any] | None = None
        # The JSON document is the last non-empty line (scripts may emit
        # module-load noise on some hosts despite -NoProfile).
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if result is None:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise ScriptExecutionError(
                f"{script} produced no JSON result (exit={returncode}). stderr: {err[:800]}"
            )

        for entry in result.get("logs") or []:
            log.info("ps:%s %s", script, entry)

        if not result.get("success"):
            error = result.get("error") or {}
            raise ScriptExecutionError(
                error.get("message", f"{script} failed"),
                code=error.get("code", "script_error"),
                details=error,
            )
        return result.get("data") or {}
