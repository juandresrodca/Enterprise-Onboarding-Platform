"""Server-side validation and identity derivation for onboarding batches.

Fills in missing identity fields (display name, sAMAccountName, UPN, email)
following the naming convention, then checks the batch for duplicates,
directory collisions, unknown OUs/groups/managers/licenses, password policy
and required fields. Returns normalized users + a flat list of issues.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from app.config import Settings
from app.models.user import NewUserSpec, ValidationIssue, ValidationResult
from app.services.provider import IdentityProvider

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _normalize_name_part(value: str) -> str:
    """'Àrià O'Connor' -> 'ariaoconnor' (ASCII letters/digits only)."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_only.lower())


class Validator:
    def __init__(self, provider: IdentityProvider, settings: Settings):
        self._provider = provider
        self._settings = settings
        self._naming = re.compile(settings.sam_naming_regex)

    async def validate(self, users: list[NewUserSpec]) -> ValidationResult:
        issues: list[ValidationIssue] = []
        normalized: list[NewUserSpec] = []
        taken_sams: set[str] = set()
        taken_upns: set[str] = set()
        taken_emails: set[str] = set()

        # License availability is checked across the whole batch.
        license_pool = {
            l["sku_part_number"]: max(l["total"] - l["assigned"], 0)
            for l in await self._provider.list_licenses()
        }

        for i, user in enumerate(users):
            user = user.model_copy(deep=True)

            def issue(field: str, code: str, message: str, severity: str = "error") -> None:
                issues.append(ValidationIssue(
                    index=i, field=field, code=code, severity=severity, message=message
                ))

            # --- required fields ------------------------------------------------
            if not user.first_name.strip():
                issue("first_name", "required", "First name is required")
            if not user.last_name.strip():
                issue("last_name", "required", "Last name is required")
            if not user.ou:
                issue("ou", "required", "Target organizational unit is required")

            # --- identity derivation --------------------------------------------
            if not user.display_name:
                user.display_name = f"{user.first_name} {user.last_name}".strip()

            explicit_sam = bool(user.sam_account_name)
            if not user.sam_account_name:
                first = _normalize_name_part(user.first_name)
                last = _normalize_name_part(user.last_name)
                base = f"{first}.{last}"[:20].rstrip(".") or "user"
                candidate, n = base, 1
                while candidate in taken_sams or await self._provider.user_exists(sam=candidate):
                    n += 1
                    suffix = str(n)
                    candidate = f"{base[: 20 - len(suffix)]}{suffix}"
                if candidate != base:
                    issue("sam_account_name", "suffix_applied",
                          f"Username '{base}' is taken; '{candidate}' was assigned",
                          severity="warning")
                user.sam_account_name = candidate
            sam = user.sam_account_name

            if not self._naming.match(sam):
                issue("sam_account_name", "naming_convention",
                      f"'{sam}' violates the naming convention "
                      f"({self._settings.sam_naming_regex})")

            if not user.user_principal_name:
                user.user_principal_name = f"{sam}@{self._settings.upn_suffix}"
            if not user.email and user.create_mailbox:
                user.email = user.user_principal_name

            # --- duplicates: batch ------------------------------------------------
            if sam in taken_sams:
                issue("sam_account_name", "duplicate_in_batch",
                      f"Username '{sam}' appears more than once in this batch")
            upn = user.user_principal_name.lower()
            if upn in taken_upns:
                issue("user_principal_name", "duplicate_in_batch",
                      f"UPN '{upn}' appears more than once in this batch")
            email = (user.email or "").lower()
            if email and email in taken_emails:
                issue("email", "duplicate_in_batch",
                      f"Email '{email}' appears more than once in this batch")
            taken_sams.add(sam)
            taken_upns.add(upn)
            if email:
                taken_emails.add(email)

            # --- duplicates: directory ---------------------------------------------
            if explicit_sam and await self._provider.user_exists(sam=sam):
                issue("sam_account_name", "duplicate_username",
                      f"Username '{sam}' already exists in the directory")
            if await self._provider.user_exists(upn=upn):
                issue("user_principal_name", "duplicate_upn",
                      f"UPN '{upn}' already exists in the directory")
            if email and await self._provider.user_exists(email=email):
                issue("email", "duplicate_email",
                      f"Email '{email}' already exists in the directory")
            if not _EMAIL_RE.match(upn):
                issue("user_principal_name", "invalid_format", f"'{upn}' is not a valid UPN")
            if email and not _EMAIL_RE.match(email):
                issue("email", "invalid_format", f"'{email}' is not a valid email address")

            # --- directory references ------------------------------------------------
            if user.ou and not await self._provider.ou_exists(user.ou):
                issue("ou", "invalid_ou", f"OU does not exist: {user.ou}")
            if user.manager:
                resolved = await self._provider.resolve_manager(user.manager)
                if not resolved:
                    issue("manager", "invalid_manager",
                          f"Manager '{user.manager}' was not found in the directory")
                else:
                    user.manager = resolved["sam_account_name"]
            missing = await self._provider.missing_groups(user.groups)
            for g in missing:
                issue("groups", "invalid_group", f"Group does not exist: {g}")

            # --- licenses ---------------------------------------------------------
            for sku in user.licenses:
                if sku not in license_pool:
                    issue("licenses", "unknown_license", f"Unknown license SKU: {sku}")
                elif license_pool[sku] <= 0:
                    issue("licenses", "license_exhausted",
                          f"No '{sku}' licenses remain for this batch", severity="warning")
                else:
                    license_pool[sku] -= 1

            # --- password -------------------------------------------------------------
            if not user.password.generate:
                if not user.password.value:
                    issue("password", "required",
                          "Provide a password or enable password generation")
                else:
                    from app.services.passwords import validate_password
                    problems = validate_password(
                        user.password.value,
                        self._settings.password_policy,
                        [user.first_name, user.last_name, sam.split(".")[0]],
                    )
                    for p in problems:
                        issue("password", "password_policy", f"Password {p}")

            # --- misc -----------------------------------------------------------------
            if user.account_expiration and user.account_expiration <= date.today():
                issue("account_expiration", "expired",
                      "Account expiration date must be in the future")
            if user.employee_id and await self._provider.employee_id_exists(user.employee_id):
                issue("employee_id", "duplicate_employee_id",
                      f"Employee ID '{user.employee_id}' is already in use",
                      severity="warning")
            if user.home_folder.enabled and not user.home_folder.base_path:
                user.home_folder.base_path = self._settings.default_home_base_path

            normalized.append(user)

        valid = not any(i.severity == "error" for i in issues)
        return ValidationResult(valid=valid, issues=issues, users=normalized)
