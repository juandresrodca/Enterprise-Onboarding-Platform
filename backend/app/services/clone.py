"""Copy-existing-user (template user) logic.

Merges attribute families from a source user into new user specs according to
CloneOptions. Explicit values on the new user always win over copied values.

Never copied, by design: SID, GUID, password, sAMAccountName, UPN, email,
employeeID, displayName, and personal data (mobile phone, personal address is
copied only as *office* address which is organizational).
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.models.user import CloneOptions, NewUserSpec
from app.services.provider import IdentityProvider


async def load_source(provider: IdentityProvider, source_sam: str) -> dict[str, Any]:
    source = await provider.get_user(source_sam, expand=True)
    if not source:
        raise NotFoundError(f"Source user '{source_sam}' not found")
    return source


def _proxy_domains(source: dict[str, Any]) -> list[str]:
    """Secondary smtp domains of the source (the primary comes from the UPN)."""
    domains = []
    for proxy in source.get("proxy_addresses", []):
        if proxy.startswith("smtp:") and "@" in proxy:  # lowercase smtp: = secondary
            domain = proxy.split("@", 1)[1].lower()
            if domain not in domains:
                domains.append(domain)
    return domains


def apply_clone(
    source: dict[str, Any], options: CloneOptions, user: NewUserSpec
) -> NewUserSpec:
    """Return a new spec with source attribute families merged in."""
    u = user.model_copy(deep=True)

    def take(field: str, value: Any) -> None:
        if value not in (None, "", []) and getattr(u, field) in (None, "", []):
            setattr(u, field, value)

    if options.ou:
        take("ou", source.get("ou"))
    if options.organization:
        for f in ("department", "company", "office", "office_location",
                  "job_title", "cost_center", "employee_type"):
            take(f, source.get(f))
    if options.manager:
        take("manager", source.get("manager"))
    if options.address:
        for f in ("address", "city", "state", "country", "postal_code"):
            take(f, source.get(f))
    if options.phones:
        take("phone", source.get("phone"))  # mobile is personal: never copied

    if options.groups:
        merged = list(dict.fromkeys([*source.get("groups", []), *u.groups]))
        u.groups = merged
    if options.licenses:
        u.licenses = list(dict.fromkeys([*source.get("licenses", []), *u.licenses]))
    if options.shared_mailboxes:
        u.shared_mailboxes = list(
            dict.fromkeys([*source.get("shared_mailboxes", []), *u.shared_mailboxes])
        )
    if options.extension_attributes and source.get("extension_attributes"):
        u.extension_attributes = {
            **source["extension_attributes"], **u.extension_attributes
        }
    if options.proxy_address_pattern:
        # Re-template secondary addresses for the new person: f.lastname@domain
        first = (u.first_name or "x").strip().lower()
        last = "".join(c for c in (u.last_name or "").lower() if c.isalnum()) or "user"
        for domain in _proxy_domains(source):
            alias = f"smtp:{first[0]}.{last}@{domain}"
            if alias not in u.proxy_addresses:
                u.proxy_addresses.append(alias)
    if options.home_folder and source.get("home_folder"):
        u.home_folder.enabled = True
        src_path = source["home_folder"].get("path") or ""
        if not u.home_folder.base_path and "\\" in src_path:
            u.home_folder.base_path = src_path.rsplit("\\", 1)[0]
        u.home_folder.drive_letter = source["home_folder"].get("drive") or u.home_folder.drive_letter
    if options.logon_script and source.get("profile"):
        if not u.profile.logon_script:
            u.profile.logon_script = source["profile"].get("logon_script")

    u.create_mailbox = True if source.get("mailbox") else u.create_mailbox
    return u
