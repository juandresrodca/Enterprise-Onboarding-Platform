"""Unit tests: password engine, importer mapping, exporters."""

from datetime import datetime, timezone

from app.config import PasswordPolicy
from app.models.audit import AuditEntry
from app.services import exporter
from app.services.importer import rows_to_specs
from app.services.passwords import generate_password, validate_password


def test_generated_passwords_comply_with_policy():
    policy = PasswordPolicy()
    for _ in range(50):
        password = generate_password(policy)
        assert validate_password(password, policy) == []
        assert len(password) >= policy.generated_length


def test_validate_password_reports_each_violation():
    policy = PasswordPolicy()
    problems = validate_password("short", policy)
    assert any("12 characters" in p for p in problems)
    assert any("uppercase" in p for p in problems)
    assert any("digit" in p for p in problems)
    assert any("symbol" in p for p in problems)


def test_validate_password_rejects_name_parts():
    policy = PasswordPolicy()
    problems = validate_password("Xy9!JaneDoe#Pass", policy, ["Jane", "Doe"])
    assert any("jane" in p for p in problems)


def test_importer_maps_hr_system_headers():
    rows = [{
        "Given Name": "Ana", "Surname": "Silva", "Title": "Engineer",
        "Organizational Unit": "OU=IT,OU=Company,DC=northwind,DC=local",
        "MemberOf": "SG-IT-Admins|SG-VPN-Access", "License Type": "SPE_E3",
        "Reports To": "elena.moreau", "Zip": "98101", "Mailbox": "yes",
        "Expiration": "31/01/2027",
    }]
    users, issues = rows_to_specs(rows)
    assert not issues
    user = users[0]
    assert user.first_name == "Ana"
    assert user.job_title == "Engineer"
    assert user.groups == ["SG-IT-Admins", "SG-VPN-Access"]
    assert user.licenses == ["SPE_E3"]
    assert user.manager == "elena.moreau"
    assert user.postal_code == "98101"
    assert user.create_mailbox is True
    assert str(user.account_expiration) == "2027-01-31"


def test_importer_reports_bad_rows_with_row_numbers():
    users, issues = rows_to_specs([{"first_name": "OnlyFirst"}])
    assert not users
    assert issues and issues[0].code == "parse_error"
    assert "Row 2" in issues[0].message


def _entries() -> list[AuditEntry]:
    return [AuditEntry(
        id=1, ts=datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc), actor="admin",
        actor_role="admin", action="user.create", target="jane.doe",
        status="success", computer="APP01", source_ip="10.0.0.5",
        details={"ou": "OU=Finance"},
    )]


def test_export_csv_json_pdf():
    entries = _entries()
    csv_bytes = exporter.to_csv(entries)
    assert b"jane.doe" in csv_bytes

    json_bytes = exporter.to_json(entries)
    assert b'"action": "user.create"' in json_bytes

    pdf_bytes = exporter.to_pdf(entries)
    assert pdf_bytes.startswith(b"%PDF")
