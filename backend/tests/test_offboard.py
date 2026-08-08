"""Offboarding flow: preview/execute, RBAC, validation, provider side effects."""

from tests.conftest import login, wait_for_job

CONTRACTORS_OU = "OU=Contractors,OU=Company,DC=northwind,DC=local"


def _codes(result: dict) -> set[str]:
    return {issue["code"] for issue in result["issues"]}


def test_offboard_preview_shows_full_plan(client):
    headers = login(client)  # admin has users:offboard
    response = client.post(
        "/api/offboard/preview",
        json={"users": [{"sam_account_name": "priya.sharma"}]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["total_users"] == 1
    kinds = [a["kind"] for a in plan["users"][0]["actions"]]
    assert {"disable", "groups", "licenses", "mailbox"} <= set(kinds)


def test_offboard_execute_end_to_end(client):
    headers = login(client)
    body = {
        "users": [{"sam_account_name": "priya.sharma", "reason": "Resigned"}],
        "options": {"grant_mailbox_access_to": "john.smith"},
    }
    response = client.post("/api/offboard", json=body, headers=headers)
    assert response.status_code == 202, response.text
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "completed"
    result = job["results"][0]
    assert result["status"] == "success"
    assert "Offboarded" in result["message"]

    detail = client.get("/api/users/priya.sharma").json()["user"]
    assert detail["enabled"] is False
    assert detail["licenses"] == []
    assert "SG-Finance-Users" not in detail["groups"]
    # Distribution lists are kept by default (continuity during handover).
    assert "DL-Finance" in detail["groups"]

    logs = client.get("/api/logs", params={"action": "user.offboard"}).json()
    assert any(entry["target"] == "priya.sharma" for entry in logs["entries"])
    mailbox_logs = client.get("/api/logs", params={"action": "mailbox.convert"}).json()
    assert any(entry["target"] == "priya.sharma" for entry in mailbox_logs["entries"])


def test_offboard_helpdesk_and_hr_denied(client):
    for role in ("helpdesk", "hr"):
        headers = login(client, role)
        response = client.post(
            "/api/offboard/preview",
            json={"users": [{"sam_account_name": "diego.fuentes"}]},
            headers=headers,
        )
        assert response.status_code == 403


def test_offboard_unknown_user_is_an_error(client):
    headers = login(client)
    response = client.post(
        "/api/offboard/preview",
        json={"users": [{"sam_account_name": "ghost.user"}]},
        headers=headers,
    )
    body = response.json()
    assert "not_found" in _codes(body)


def test_offboard_manager_self_reference_rejected(client):
    headers = login(client)
    response = client.post(
        "/api/offboard/preview",
        json={
            "users": [{"sam_account_name": "diego.fuentes"}],
            "options": {"grant_mailbox_access_to": "diego.fuentes"},
        },
        headers=headers,
    )
    assert "self_reference" in _codes(response.json())


def test_offboard_invalid_move_ou_rejected(client):
    headers = login(client)
    response = client.post(
        "/api/offboard/preview",
        json={
            "users": [{"sam_account_name": "diego.fuentes"}],
            "options": {"move_to_ou": "OU=DoesNotExist,DC=northwind,DC=local"},
        },
        headers=headers,
    )
    assert "invalid_ou" in _codes(response.json())


def test_offboard_move_to_ou_relocates_user(client):
    headers = login(client)
    body = {
        "users": [{"sam_account_name": "ingrid.halvorsen"}],
        "options": {"move_to_ou": CONTRACTORS_OU, "convert_mailbox_to_shared": False},
    }
    response = client.post("/api/offboard", json=body, headers=headers)
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "completed"
    detail = client.get("/api/users/ingrid.halvorsen").json()["user"]
    assert detail["ou"] == CONTRACTORS_OU


def test_offboard_already_disabled_is_rejected_on_execute(client):
    headers = login(client)
    body = {"users": [{"sam_account_name": "yuki.tanaka"}]}
    first = client.post("/api/offboard", json=body, headers=headers)
    wait_for_job(client, first.json()["job_id"])

    second = client.post("/api/offboard", json=body, headers=headers)
    assert second.status_code == 422
    assert "already disabled" in second.json()["detail"]["message"]
