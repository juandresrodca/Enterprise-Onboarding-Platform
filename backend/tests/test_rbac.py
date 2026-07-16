"""Role-based access control enforcement."""

from tests.conftest import login, user_payload


def test_helpdesk_cannot_create_users(client):
    headers = login(client, "helpdesk")
    response = client.post(
        "/api/users/create", json={"users": [user_payload()]}, headers=headers
    )
    assert response.status_code == 403
    assert "users:create" in response.json()["detail"]


def test_helpdesk_can_read_users_and_logs(client):
    login(client, "helpdesk")
    assert client.get("/api/users").status_code == 200
    assert client.get("/api/logs").status_code == 200
    assert client.get("/api/dashboard").status_code == 200


def test_hr_can_create_but_not_clone(client):
    headers = login(client, "hr")
    validate = client.post(
        "/api/users/validate", json={"users": [user_payload()]}, headers=headers
    )
    assert validate.status_code == 200

    clone = client.post(
        "/api/users/clone",
        json={"source_sam": "john.smith", "users": [user_payload()]},
        headers=headers,
    )
    assert clone.status_code == 403


def test_admin_cannot_write_settings_but_global_admin_can(client):
    headers = login(client, "admin")
    assert client.get("/api/settings").status_code == 200
    assert client.put(
        "/api/settings", json={"min_length": 14}, headers=headers
    ).status_code == 403

    headers = login(client, "gadmin")
    response = client.put("/api/settings", json={"min_length": 14}, headers=headers)
    assert response.status_code == 200
    assert response.json()["password_policy"]["min_length"] == 14


def test_helpdesk_cannot_export_logs(client):
    login(client, "helpdesk")
    assert client.get("/api/logs/export?format=csv").status_code == 403


def test_denied_access_is_audited(client):
    headers = login(client, "helpdesk")
    client.post("/api/users/create", json={"users": [user_payload()]}, headers=headers)
    logs = client.get("/api/logs", params={"action": "auth.denied"}).json()
    assert logs["total"] >= 1
    assert logs["entries"][0]["actor"] == "helpdesk"
