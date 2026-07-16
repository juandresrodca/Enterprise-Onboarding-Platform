"""Request/response models for user onboarding."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PasswordSpec(BaseModel):
    """Password handling for a new account.

    When generate=True the platform creates a policy-compliant random password
    and returns it exactly once in the job results; it is never persisted.
    """

    generate: bool = True
    value: str | None = None
    force_change_at_logon: bool = True
    never_expires: bool = False


class HomeFolderSpec(BaseModel):
    enabled: bool = False
    base_path: str | None = None  # defaults to settings.default_home_base_path
    drive_letter: str = Field(default="H", pattern=r"^[D-Z]$")


class ProfileSpec(BaseModel):
    roaming_profile_path: str | None = None
    logon_script: str | None = None


class NewUserSpec(BaseModel):
    """One user to onboard. Identity fields left empty are derived server-side
    (sam = first.last, upn/email = sam@upn-suffix, display name = First Last)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    display_name: str | None = None
    sam_account_name: str | None = Field(default=None, max_length=20)
    user_principal_name: str | None = None
    email: str | None = None

    ou: str | None = None  # distinguishedName of target OU
    department: str | None = None
    company: str | None = None
    office: str | None = None
    office_location: str | None = None
    job_title: str | None = None
    employee_id: str | None = None
    employee_type: str | None = None
    cost_center: str | None = None
    description: str | None = None
    manager: str | None = None  # sAMAccountName or UPN of the manager

    phone: str | None = None
    mobile: str | None = None
    country: str | None = None
    city: str | None = None
    state: str | None = None
    address: str | None = None
    postal_code: str | None = None

    account_expiration: date | None = None

    groups: list[str] = Field(default_factory=list)
    licenses: list[str] = Field(default_factory=list)  # SKU part numbers
    create_mailbox: bool = True
    shared_mailboxes: list[str] = Field(default_factory=list)
    proxy_addresses: list[str] = Field(default_factory=list)
    extension_attributes: dict[str, str] = Field(default_factory=dict)

    home_folder: HomeFolderSpec = Field(default_factory=HomeFolderSpec)
    profile: ProfileSpec = Field(default_factory=ProfileSpec)
    password: PasswordSpec = Field(default_factory=PasswordSpec)

    @field_validator("sam_account_name", "user_principal_name", "email")
    @classmethod
    def _lowercase(cls, v: str | None) -> str | None:
        return v.lower() if v else v


class CreateUsersRequest(BaseModel):
    users: list[NewUserSpec] = Field(min_length=1, max_length=200)


class CloneOptions(BaseModel):
    """Which attribute families to copy from the source user.

    Protected attributes (SID, GUID, password, username, email, employeeID,
    displayName and other personal identity fields) are never copied.
    """

    ou: bool = True
    organization: bool = True  # department, company, office, job title, cost center
    manager: bool = True
    address: bool = True  # street, city, state, country, postal code
    phones: bool = True  # office phone only; mobile is personal and never copied
    groups: bool = True  # security + distribution + M365 groups
    licenses: bool = True
    shared_mailboxes: bool = True
    proxy_address_pattern: bool = True  # secondary smtp domains, re-templated
    extension_attributes: bool = True
    home_folder: bool = True
    logon_script: bool = True


class CloneRequest(BaseModel):
    source_sam: str = Field(min_length=1)
    options: CloneOptions = Field(default_factory=CloneOptions)
    users: list[NewUserSpec] = Field(min_length=1, max_length=50)


class ValidationIssue(BaseModel):
    index: int  # position in the submitted batch
    field: str
    code: str
    severity: Literal["error", "warning"]
    message: str


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue]
    users: list[NewUserSpec]  # normalized users with derived identity fields


class PlanAction(BaseModel):
    kind: str
    summary: str
    details: list[str] = Field(default_factory=list)


class UserPlan(BaseModel):
    display_name: str
    sam_account_name: str
    user_principal_name: str
    email: str | None
    ou: str
    manager: str | None
    actions: list[PlanAction]
    warnings: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    summary: str
    total_users: int
    total_actions: int
    users: list[UserPlan]
    issues: list[ValidationIssue] = Field(default_factory=list)
