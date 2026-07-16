"""Validation engine: duplicates, references, naming, passwords, derivation."""

from tests.conftest import VALID_OU, login, user_payload


def _codes(result: dict) -> set[str]:
    return {issue["code"] for issue in result["issues"]}


def test_identity_derivation(client):
    headers = login(client)
    response = client.post(
        "/api/users/validate",
        json={"users": [user_payload(first_name="Élodie", last_name="O'Brien")]},
        headers=headers,
    )
    body = response.json()
    assert body["valid"] is True
    user = body["users"][0]
    assert user["sam_account_name"] == "elodie.obrien"
    assert user["user_principal_name"] == "elodie.obrien@northwind.com"
    assert user["display_name"] == "Élodie O'Brien"


def test_duplicate_username_gets_suffix_with_warning(client):
    headers = login(client)
    # john.smith already exists in the seed directory.
    response = client.post(
        "/api/users/validate",
        json={"users": [user_payload(first_name="John", last_name="Smith")]},
        headers=headers,
    )
    body = response.json()
    assert body["valid"] is True  # warning, not error
    assert "suffix_applied" in _codes(body)
    assert body["users"][0]["sam_account_name"] == "john.smith2"


def test_explicit_duplicate_username_is_an_error(client):
    headers = login(client)
    response = client.post(
        "/api/users/validate",
        json={"users": [user_payload(sam_account_name="john.smith")]},
        headers=headers,
    )
    body = response.json()
    assert body["valid"] is False
    assert "duplicate_username" in _codes(body)


def test_invalid_ou_manager_and_group(client):
    headers = login(client)
    response = client.post(
        "/api/users/validate",
        json={"users": [user_payload(
            ou="OU=DoesNotExist,DC=northwind,DC=local",
            manager="ghost.user",
            groups=["SG-Nonexistent"],
        )]},
        headers=headers,
    )
    body = response.json()
    assert body["valid"] is False
    codes = _codes(body)
    assert {"invalid_ou", "invalid_manager", "invalid_group"} <= codes


def test_duplicates_within_batch(client):
    headers = login(client)
    response = client.post(
        "/api/users/validate",
        json={"users": [
            user_payload(sam_account_name="new.person"),
            user_payload(first_name="Other", sam_account_name="new.person"),
        ]},
        headers=headers,
    )
    body = response.json()
    assert body["valid"] is False
    assert "duplicate_in_batch" in _codes(body)


def test_weak_manual_password_rejected(client):
    headers = login(client)
    response = client.post(
        "/api/users/validate",
        json={"users": [user_payload(
            password={"generate": False, "value": "janedoe1"},
        )]},
        headers=headers,
    )
    body = response.json()
    assert body["valid"] is False
    assert "password_policy" in _codes(body)


def test_unknown_license_and_naming_violation(client):
    headers = login(client)
    response = client.post(
        "/api/users/validate",
        json={"users": [user_payload(
            sam_account_name="UPPER CASE!!",
            licenses=["NOT_A_SKU"],
        )]},
        headers=headers,
    )
    body = response.json()
    assert body["valid"] is False
    codes = _codes(body)
    assert "naming_convention" in codes
    assert "unknown_license" in codes


def test_preview_plan_reflects_actions(client):
    headers = login(client)
    response = client.post(
        "/api/users/preview", json={"users": [user_payload()]}, headers=headers
    )
    plan = response.json()
    assert plan["total_users"] == 1
    kinds = [a["kind"] for a in plan["users"][0]["actions"]]
    assert {"create", "groups", "licenses", "mailbox", "home_folder"} <= set(kinds)
    assert plan["users"][0]["ou"] == VALID_OU


def test_top_level_aliases(client):
    headers = login(client)
    assert client.post(
        "/api/validate", json={"users": [user_payload()]}, headers=headers
    ).status_code == 200
    assert client.post(
        "/api/preview", json={"users": [user_payload()]}, headers=headers
    ).status_code == 200
