"""End-to-end onboarding flows in demo mode: create, clone, bulk import."""

import io

from tests.conftest import VALID_OU, login, user_payload, wait_for_job


def test_create_user_end_to_end(client):
    headers = login(client)
    response = client.post(
        "/api/users/create", json={"users": [user_payload()]}, headers=headers
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    job = wait_for_job(client, job_id)
    assert job["status"] == "completed"
    result = job["results"][0]
    assert result["status"] == "success"
    assert result["sam_account_name"] == "jane.doe"
    assert result["generated_password"]  # shown once in results
    assert any("Account created" in entry["message"] for entry in job["logs"])

    # The user is now in the directory with everything applied.
    detail = client.get("/api/users/jane.doe").json()["user"]
    assert detail["ou"] == VALID_OU
    assert "SG-Finance-Users" in detail["groups"]
    assert detail["licenses"] == ["SPE_E3"]
    assert detail["mailbox"] is True
    assert detail["home_folder"]["path"].endswith("jane.doe")

    # Audit trail records the creation.
    logs = client.get("/api/logs", params={"action": "user.create"}).json()
    assert any(entry["target"] == "jane.doe" for entry in logs["entries"])


def test_validation_failure_blocks_execution(client):
    headers = login(client)
    response = client.post(
        "/api/users/create",
        json={"users": [user_payload(ou="OU=Nope,DC=northwind,DC=local")]},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["issues"]


def test_clone_preview_and_execute(client):
    headers = login(client)  # admin has users:clone
    body = {
        "source_sam": "john.smith",
        "options": {"groups": True, "licenses": True, "organization": True},
        "users": [{"first_name": "Nova", "last_name": "Reed"}],
    }
    preview = client.post("/api/users/clone", json=body, headers=headers)
    assert preview.status_code == 202
    data = preview.json()
    assert data["source"]["display_name"] == "John Smith"
    merged = data["users"][0]
    # Copied families.
    assert merged["ou"] == VALID_OU
    assert merged["department"] == "Finance"
    assert "SG-Finance-Approvers" in merged["groups"]
    assert "SPE_E3" in merged["licenses"]
    # Never copied: identity is the new person's own.
    assert merged["sam_account_name"] == "nova.reed"
    assert merged["employee_id"] is None
    assert merged["mobile"] is None

    execute = client.post("/api/users/clone?execute=true", json=body, headers=headers)
    assert execute.status_code == 202
    job = wait_for_job(client, execute.json()["job_id"])
    assert job["status"] == "completed"

    detail = client.get("/api/users/nova.reed").json()["user"]
    assert "SG-FileShare-Finance-RW" in detail["groups"]
    assert detail["manager"] == "marcus.thorne"


def test_bulk_csv_template_and_import(client):
    headers = login(client, "hr")
    template = client.get("/api/users/template.csv")
    assert template.status_code == 200
    assert "first_name" in template.text.splitlines()[0]

    # DN values contain commas, so the OU column must be quoted.
    csv_content = (
        "First Name,Last Name,OU,Department,Groups,Licenses,Manager\n"
        f'Rex,Storm,"{VALID_OU}",Finance,SG-Finance-Users;DL-Finance,SPE_E3,john.smith\n'
        f'Luna,Vale,"{VALID_OU}",Finance,SG-Finance-Users,SPE_E3,john.smith\n'
    ).encode()
    response = client.post(
        "/api/users/bulk",
        files={"file": ("import.csv", io.BytesIO(csv_content), "text/csv")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rows"] == 2
    assert body["valid"] is True
    assert body["users"][0]["sam_account_name"] == "rex.storm"
    assert body["users"][0]["groups"] == ["SG-Finance-Users", "DL-Finance"]

    # Execute the parsed batch through the normal create endpoint.
    create = client.post(
        "/api/users/create", json={"users": body["users"]}, headers=headers
    )
    assert create.status_code == 202
    job = wait_for_job(client, create.json()["job_id"])
    assert job["status"] == "completed"
    assert {r["sam_account_name"] for r in job["results"]} == {"rex.storm", "luna.vale"}


def test_bulk_json_import(client):
    headers = login(client, "hr")
    payload = b'{"users": [{"first_name": "Kai", "last_name": "Frost", "ou": "%s"}]}' % (
        VALID_OU.encode()
    )
    response = client.post(
        "/api/users/bulk",
        files={"file": ("import.json", io.BytesIO(payload), "application/json")},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["users"][0]["sam_account_name"] == "kai.frost"


def test_directory_endpoints(client):
    login(client, "helpdesk")
    tree = client.get("/api/ou").json()["tree"]
    assert tree[0]["name"] == "Company"
    assert any(child["name"] == "Finance" for child in tree[0]["children"])

    groups = client.get("/api/groups", params={"search": "finance"}).json()["groups"]
    assert any(g["name"] == "SG-Finance-Users" for g in groups)

    licenses = client.get("/api/licenses").json()["licenses"]
    e3 = next(l for l in licenses if l["sku_part_number"] == "SPE_E3")
    assert e3["total"] >= e3["assigned"] >= 1

    managers = client.get("/api/managers", params={"query": "smith"}).json()["managers"]
    assert any(m["sam_account_name"] == "john.smith" for m in managers)
