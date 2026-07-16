"""Application configuration.

All settings can be overridden via environment variables prefixed with EIO_
(e.g. EIO_DEMO_MODE=false) or a .env file next to the backend package.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class PasswordPolicy(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EIO_PWD_")

    min_length: int = 12
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_symbol: bool = True
    disallow_name_parts: bool = True
    generated_length: int = 16
    max_age_days: int = 90


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EIO_", env_file=BACKEND_DIR / ".env", extra="ignore"
    )

    # --- General -----------------------------------------------------------
    app_name: str = "Enterprise Identity Onboarding"
    environment: str = "demo"  # demo | production
    demo_mode: bool = True
    api_prefix: str = "/api"

    # --- Security ----------------------------------------------------------
    # Auto-generated key means sessions do not survive restarts; set a stable
    # EIO_SECRET_KEY in production.
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    session_timeout_minutes: int = 30
    cookie_secure: bool = False  # set True behind HTTPS
    # "lax" when frontend and API share an origin (default). Set "none" (plus
    # cookie_secure=true) when the frontend is hosted cross-site, e.g. GitHub
    # Pages calling a Render-hosted API.
    cookie_samesite: str = "lax"
    cookie_name: str = "eio_session"
    csrf_cookie_name: str = "eio_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    cors_origins: list[str] = ["http://localhost:4321", "http://127.0.0.1:4321"]
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # --- Microsoft Entra ID (OIDC) ------------------------------------------
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_redirect_uri: str = "http://localhost:8000/api/auth/entra/callback"
    # Maps Entra app-role values -> platform roles.
    entra_role_map: dict[str, str] = {
        "Onboarding.GlobalAdmin": "global_admin",
        "Onboarding.Administrator": "admin",
        "Onboarding.HR": "hr",
        "Onboarding.Helpdesk": "helpdesk",
    }

    @property
    def entra_enabled(self) -> bool:
        return bool(self.entra_tenant_id and self.entra_client_id and self.entra_client_secret)

    # --- Directory ----------------------------------------------------------
    domain_dns: str = "northwind.local"
    domain_netbios: str = "NORTHWIND"
    upn_suffix: str = "northwind.com"
    # SAMAccountName naming convention (first.last, optional digits suffix).
    sam_naming_regex: str = r"^[a-z][a-z0-9\-_.]{1,18}[a-z0-9]$"
    default_home_base_path: str = r"\\FS01\Home"
    default_home_drive: str = "H"

    # --- PowerShell execution ------------------------------------------------
    powershell_executable: str = "pwsh"
    powershell_fallback: str = "powershell"
    scripts_dir: Path = PROJECT_DIR / "powershell" / "scripts"
    script_timeout_seconds: int = 180
    max_concurrent_scripts: int = 4

    # --- Jobs / audit / storage ----------------------------------------------
    job_workers: int = 2
    data_dir: Path = BACKEND_DIR / "data"
    logs_dir: Path = PROJECT_DIR / "logs"

    password_policy: PasswordPolicy = Field(default_factory=PasswordPolicy)

    @property
    def audit_db_path(self) -> Path:
        return self.data_dir / "audit.sqlite3"

    @property
    def demo_state_path(self) -> Path:
        return self.data_dir / "demo_state.json"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings
