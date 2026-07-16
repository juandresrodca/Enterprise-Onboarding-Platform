"""Demo directory seed data for the fictional company "Northwind Dynamics".

Every name here is fantasy data for demonstrations only. The structure mirrors
what the PowerShell provider returns from a real AD/Entra tenant, so the
frontend and job engine behave identically in both modes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

DOMAIN_DN = "DC=northwind,DC=local"
COMPANY = "Northwind Dynamics"
UPN_SUFFIX = "northwind.com"

_NOW = datetime.now(timezone.utc)


def _dn(*ous: str) -> str:
    return ",".join([f"OU={o}" for o in ous] + [DOMAIN_DN])


OU_TREE: list[dict[str, Any]] = [
    {
        "name": "Company",
        "dn": _dn("Company"),
        "children": [
            {"name": "Users", "dn": _dn("Users", "Company"), "children": []},
            {"name": "Finance", "dn": _dn("Finance", "Company"), "children": []},
            {"name": "HR", "dn": _dn("HR", "Company"), "children": []},
            {
                "name": "IT",
                "dn": _dn("IT", "Company"),
                "children": [
                    {"name": "Helpdesk", "dn": _dn("Helpdesk", "IT", "Company"), "children": []},
                ],
            },
            {"name": "Sales", "dn": _dn("Sales", "Company"), "children": []},
            {"name": "Contractors", "dn": _dn("Contractors", "Company"), "children": []},
            {"name": "Executives", "dn": _dn("Executives", "Company"), "children": []},
        ],
    },
    {"name": "Service Accounts", "dn": _dn("Service Accounts"), "children": []},
]


def _group(name: str, category: str, description: str, scope: str = "Global") -> dict[str, Any]:
    return {
        "name": name,
        "category": category,  # security | distribution | m365
        "scope": scope,
        "description": description,
        "dn": f"CN={name},OU=Groups,{DOMAIN_DN}",
    }


GROUPS: list[dict[str, Any]] = [
    _group("SG-AllStaff", "security", "All permanent staff"),
    _group("SG-VPN-Access", "security", "Remote VPN access"),
    _group("SG-MFA-Enforced", "security", "Conditional Access MFA enforcement"),
    _group("SG-Finance-Users", "security", "Finance department baseline"),
    _group("SG-Finance-Approvers", "security", "Invoice approval rights"),
    _group("SG-FileShare-Finance-RW", "security", "\\\\FS01\\Finance read/write"),
    _group("SG-HR-Users", "security", "HR department baseline"),
    _group("SG-HR-Confidential", "security", "HR case files access"),
    _group("SG-IT-Admins", "security", "Tier-1 IT administration"),
    _group("SG-IT-Helpdesk", "security", "Helpdesk toolset access"),
    _group("SG-Sales-Users", "security", "Sales department baseline"),
    _group("SG-Contractors", "security", "Contractor restrictions baseline"),
    _group("DL-All-Company", "distribution", "Company-wide announcements"),
    _group("DL-Finance", "distribution", "Finance team mail"),
    _group("DL-HR", "distribution", "HR team mail"),
    _group("DL-Sales", "distribution", "Sales team mail"),
    _group("M365-Project-Phoenix", "m365", "Project Phoenix workspace (Teams/SharePoint)"),
    _group("M365-Leadership", "m365", "Leadership team workspace"),
    _group("M365-Innovation-Guild", "m365", "Cross-team innovation community"),
]

LICENSES: list[dict[str, Any]] = [
    {"sku_part_number": "SPE_E5", "display_name": "Microsoft 365 E5", "total": 40},
    {"sku_part_number": "SPE_E3", "display_name": "Microsoft 365 E3", "total": 120},
    {"sku_part_number": "EXCHANGESTANDARD", "display_name": "Exchange Online (Plan 1)", "total": 50},
    {"sku_part_number": "POWER_BI_PRO", "display_name": "Power BI Pro", "total": 25},
    {"sku_part_number": "PROJECTPROFESSIONAL", "display_name": "Project Plan 3", "total": 10},
]

SHARED_MAILBOXES: list[dict[str, Any]] = [
    {"name": "Finance Invoices", "email": f"finance-invoices@{UPN_SUFFIX}"},
    {"name": "Accounts Payable", "email": f"ap@{UPN_SUFFIX}"},
    {"name": "IT Support", "email": f"support@{UPN_SUFFIX}"},
    {"name": "HR Cases", "email": f"hr-cases@{UPN_SUFFIX}"},
    {"name": "Sales Leads", "email": f"sales-leads@{UPN_SUFFIX}"},
]

_CITIES = {
    "Seattle": {"country": "US", "state": "WA", "address": "700 Rainier Ave", "postal_code": "98101"},
    "Madrid": {"country": "ES", "state": "Madrid", "address": "Calle de la Luna 42", "postal_code": "28004"},
    "London": {"country": "GB", "state": "London", "address": "12 Fenchurch St", "postal_code": "EC3M 3BD"},
}

_seq = 1000


def _user(
    first: str,
    last: str,
    ou: str,
    department: str,
    job_title: str,
    manager: str | None,
    groups: list[str],
    licenses: list[str],
    city: str = "Seattle",
    employee_type: str = "Employee",
    cost_center: str = "",
    days_ago: int = 400,
    shared_mailboxes: list[str] | None = None,
    extension_attributes: dict[str, str] | None = None,
    extra_smtp: str | None = None,
) -> dict[str, Any]:
    global _seq
    _seq += 1
    sam = f"{first}.{last}".lower()
    upn = f"{sam}@{UPN_SUFFIX}"
    loc = _CITIES[city]
    proxy = [f"SMTP:{upn}"]
    if extra_smtp:
        proxy.append(f"smtp:{extra_smtp}")
    created = (_NOW - timedelta(days=days_ago)).isoformat()
    return {
        "sam_account_name": sam,
        "user_principal_name": upn,
        "email": upn,
        "first_name": first,
        "last_name": last,
        "display_name": f"{first} {last}",
        "ou": ou,
        "department": department,
        "company": COMPANY,
        "office": f"{city} HQ" if city == "Seattle" else f"{city} Office",
        "office_location": f"{city} - Floor {(_seq % 5) + 1}",
        "job_title": job_title,
        "employee_id": f"EMP-{_seq}",
        "employee_type": employee_type,
        "cost_center": cost_center or f"CC-{department[:3].upper()}-01",
        "description": f"{job_title}, {department}",
        "manager": manager,
        "phone": f"+1 206 555 {_seq:04d}"[:16],
        "mobile": f"+1 425 555 {_seq:04d}"[:16],
        "country": loc["country"],
        "city": city,
        "state": loc["state"],
        "address": loc["address"],
        "postal_code": loc["postal_code"],
        "enabled": True,
        "created_at": created,
        "source": "seed",
        "groups": groups,
        "licenses": licenses,
        "mailbox": True,
        "shared_mailboxes": shared_mailboxes or [],
        "proxy_addresses": proxy,
        "extension_attributes": extension_attributes or {},
        "home_folder": {"path": f"\\\\FS01\\Home\\{sam}", "drive": "H"},
        "profile": {"roaming_profile_path": None, "logon_script": "logon.bat"},
        "account_expiration": None,
    }


def build_seed_users() -> list[dict[str, Any]]:
    OU = {n["name"]: n["dn"] for n in OU_TREE[0]["children"]}
    exec_ou = OU["Executives"]
    base = ["SG-AllStaff", "SG-MFA-Enforced", "DL-All-Company"]

    users = [
        # --- Executives -----------------------------------------------------
        _user("Aria", "Blackwood", exec_ou, "Executive", "Chief Executive Officer", None,
              base + ["M365-Leadership", "SG-VPN-Access"], ["SPE_E5"], days_ago=2200),
        _user("Marcus", "Thorne", exec_ou, "Finance", "Chief Financial Officer", "aria.blackwood",
              base + ["M365-Leadership", "SG-Finance-Users", "SG-Finance-Approvers", "DL-Finance"],
              ["SPE_E5", "POWER_BI_PRO"], days_ago=2000),
        _user("Selene", "Vega", exec_ou, "IT", "Chief Information Officer", "aria.blackwood",
              base + ["M365-Leadership", "SG-IT-Admins", "SG-VPN-Access"], ["SPE_E5"],
              city="Madrid", days_ago=1900),
        # --- Finance ----------------------------------------------------------
        _user("John", "Smith", OU["Finance"], "Finance", "Finance Manager", "marcus.thorne",
              base + ["SG-Finance-Users", "SG-Finance-Approvers", "SG-FileShare-Finance-RW",
                      "SG-VPN-Access", "DL-Finance", "M365-Project-Phoenix"],
              ["SPE_E3", "POWER_BI_PRO"], days_ago=1500,
              shared_mailboxes=[f"finance-invoices@{UPN_SUFFIX}", f"ap@{UPN_SUFFIX}"],
              extension_attributes={"extensionAttribute1": "FIN-COSTGRP-100",
                                    "extensionAttribute5": "PAYROLL-A"},
              extra_smtp=f"j.smith@{UPN_SUFFIX}"),
        _user("Priya", "Sharma", OU["Finance"], "Finance", "Senior Accountant", "john.smith",
              base + ["SG-Finance-Users", "SG-FileShare-Finance-RW", "DL-Finance"],
              ["SPE_E3"], days_ago=900, shared_mailboxes=[f"ap@{UPN_SUFFIX}"]),
        _user("Diego", "Fuentes", OU["Finance"], "Finance", "Financial Analyst", "john.smith",
              base + ["SG-Finance-Users", "DL-Finance"], ["SPE_E3", "POWER_BI_PRO"],
              city="Madrid", days_ago=420),
        _user("Ingrid", "Halvorsen", OU["Finance"], "Finance", "Accounts Payable Clerk", "john.smith",
              base + ["SG-Finance-Users", "DL-Finance"], ["SPE_E3"], days_ago=200,
              shared_mailboxes=[f"ap@{UPN_SUFFIX}"]),
        # --- HR ---------------------------------------------------------------
        _user("Rosa", "Delgado", OU["HR"], "HR", "HR Director", "aria.blackwood",
              base + ["SG-HR-Users", "SG-HR-Confidential", "DL-HR", "M365-Leadership"],
              ["SPE_E5"], city="Madrid", days_ago=1700),
        _user("Amara", "Okafor", OU["HR"], "HR", "HR Business Partner", "rosa.delgado",
              base + ["SG-HR-Users", "SG-HR-Confidential", "DL-HR"], ["SPE_E3"], days_ago=800,
              shared_mailboxes=[f"hr-cases@{UPN_SUFFIX}"]),
        _user("Tomas", "Novak", OU["HR"], "HR", "Recruiter", "rosa.delgado",
              base + ["SG-HR-Users", "DL-HR"], ["SPE_E3"], city="London", days_ago=350),
        # --- IT ---------------------------------------------------------------
        _user("Elena", "Moreau", OU["IT"], "IT", "Infrastructure Lead", "selene.vega",
              base + ["SG-IT-Admins", "SG-VPN-Access", "M365-Project-Phoenix"], ["SPE_E5"],
              days_ago=1200),
        _user("Kenji", "Watanabe", OU["IT"], "IT", "Systems Engineer", "elena.moreau",
              base + ["SG-IT-Admins", "SG-VPN-Access"], ["SPE_E3"], days_ago=600),
        _user("Fatima", "Zahra", OU["IT"], "IT", "Security Analyst", "elena.moreau",
              base + ["SG-IT-Admins", "SG-VPN-Access", "M365-Innovation-Guild"], ["SPE_E5"],
              city="London", days_ago=500),
        _user("Lars", "Bergman", _dn("Helpdesk", "IT", "Company"), "IT", "Helpdesk Technician",
              "elena.moreau", base + ["SG-IT-Helpdesk"], ["SPE_E3"], days_ago=250,
              shared_mailboxes=[f"support@{UPN_SUFFIX}"]),
        _user("Nadia", "Petrova", _dn("Helpdesk", "IT", "Company"), "IT", "Helpdesk Technician",
              "elena.moreau", base + ["SG-IT-Helpdesk"], ["SPE_E3"], days_ago=90,
              shared_mailboxes=[f"support@{UPN_SUFFIX}"]),
        # --- Sales ------------------------------------------------------------
        _user("Gabriel", "Santos", OU["Sales"], "Sales", "Sales Director", "aria.blackwood",
              base + ["SG-Sales-Users", "DL-Sales", "M365-Leadership"], ["SPE_E5"], days_ago=1400),
        _user("Chloe", "Dubois", OU["Sales"], "Sales", "Account Executive", "gabriel.santos",
              base + ["SG-Sales-Users", "DL-Sales"], ["SPE_E3"], city="London", days_ago=700,
              shared_mailboxes=[f"sales-leads@{UPN_SUFFIX}"]),
        _user("Ravi", "Patel", OU["Sales"], "Sales", "Account Executive", "gabriel.santos",
              base + ["SG-Sales-Users", "DL-Sales", "M365-Innovation-Guild"], ["SPE_E3"],
              days_ago=450),
        _user("Sofia", "Lindqvist", OU["Sales"], "Sales", "Sales Operations Analyst",
              "gabriel.santos", base + ["SG-Sales-Users", "DL-Sales"],
              ["SPE_E3", "POWER_BI_PRO"], days_ago=150),
        # --- Contractors --------------------------------------------------------
        _user("Milo", "Vance", OU["Contractors"], "IT", "Contract Developer", "elena.moreau",
              ["SG-Contractors", "SG-MFA-Enforced"], ["EXCHANGESTANDARD"],
              employee_type="Contractor", days_ago=60),
        _user("Yuki", "Tanaka", OU["Contractors"], "Finance", "Contract Auditor", "john.smith",
              ["SG-Contractors", "SG-MFA-Enforced"],
              ["EXCHANGESTANDARD"], employee_type="Contractor", days_ago=30),
        # --- Recently onboarded (for the dashboard) ------------------------------
        _user("Omar", "Haddad", OU["Users"], "Operations", "Facilities Coordinator",
              "rosa.delgado", base, ["SPE_E3"], days_ago=5),
        _user("Greta", "Muller", OU["Users"], "Operations", "Office Manager", "rosa.delgado",
              base, ["SPE_E3"], city="Madrid", days_ago=2),
    ]
    return users


# Demo login accounts (DEMO_MODE only; production uses Microsoft Entra ID).
# Password for every demo account: Demo!Pass123
DEMO_PASSWORD = "Demo!Pass123"
DEMO_ACCOUNTS: list[dict[str, str]] = [
    {"username": "gadmin", "display_name": "Grace Admin (Global Admin)", "role": "global_admin"},
    {"username": "admin", "display_name": "Adam Ops (Administrator)", "role": "admin"},
    {"username": "hr", "display_name": "Hanna Reyes (HR)", "role": "hr"},
    {"username": "helpdesk", "display_name": "Henry Desk (Helpdesk)", "role": "helpdesk"},
]


def build_state() -> dict[str, Any]:
    return {
        "version": 1,
        "company": COMPANY,
        "domain_dn": DOMAIN_DN,
        "upn_suffix": UPN_SUFFIX,
        "ou_tree": OU_TREE,
        "groups": GROUPS,
        "licenses": LICENSES,
        "shared_mailboxes": SHARED_MAILBOXES,
        "users": build_seed_users(),
    }
