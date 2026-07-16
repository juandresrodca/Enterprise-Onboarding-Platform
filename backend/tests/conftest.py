"""Shared fixtures: a demo-mode app instance with isolated temp storage."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

DEMO_PASSWORD = "Demo!Pass123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EIO_DEMO_MODE", "true")
    monkeypatch.setenv("EIO_SECRET_KEY", "test-secret-key-for-pytest-only-0123456789")
    monkeypatch.setenv("EIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EIO_LOGS_DIR", str(tmp_path / "logs"))

    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def login(client: TestClient, username: str = "admin") -> dict[str, str]:
    """Log in and return the CSRF header required for mutating requests."""
    response = client.post(
        "/api/auth/login", json={"username": username, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": client.cookies.get("eio_csrf")}


def wait_for_job(client: TestClient, job_id: str, timeout: float = 60.0) -> dict:
    """Poll a job until it reaches a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200, response.text
        job = response.json()["job"]
        if job["status"] in ("completed", "completed_with_errors", "failed"):
            return job
        time.sleep(0.3)
    raise AssertionError(f"Job {job_id} did not finish within {timeout}s")


VALID_OU = "OU=Finance,OU=Company,DC=northwind,DC=local"


def user_payload(**overrides) -> dict:
    base = {
        "first_name": "Jane",
        "last_name": "Doe",
        "ou": VALID_OU,
        "department": "Finance",
        "company": "Northwind Dynamics",
        "job_title": "Financial Analyst",
        "manager": "john.smith",
        "groups": ["SG-Finance-Users", "DL-Finance"],
        "licenses": ["SPE_E3"],
        "create_mailbox": True,
        "home_folder": {"enabled": True, "drive_letter": "H"},
    }
    base.update(overrides)
    return base
