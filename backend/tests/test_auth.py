"""Authentication, sessions, CSRF and login lockout."""

from tests.conftest import DEMO_PASSWORD, login


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_rejects_bad_credentials(client):
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_success_sets_session_and_returns_role(client):
    response = client.post(
        "/api/auth/login", json={"username": "gadmin", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "global_admin"
    assert "settings:write" in body["permissions"]
    assert client.cookies.get("eio_session")
    assert client.cookies.get("eio_csrf")


def test_me_requires_session(client):
    assert client.get("/api/auth/me").status_code == 401
    login(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_csrf_required_on_mutations(client):
    login(client)
    # No CSRF header -> rejected even with a valid session.
    response = client.post("/api/users/validate", json={"users": [{
        "first_name": "A", "last_name": "B",
    }]})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_logout_clears_session(client):
    headers = login(client)
    response = client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_login_lockout_after_failed_attempts(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "hr", "password": "nope"})
    response = client.post(
        "/api/auth/login", json={"username": "hr", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 429
