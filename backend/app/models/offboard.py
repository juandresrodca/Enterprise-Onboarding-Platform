"""Request/response models for offboarding existing users.

Reuses ValidationIssue and PlanAction from app.models.user - both are
already generic (field/code/severity/message and kind/summary/details) and
apply just as well to deactivation as to account creation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import PlanAction, ValidationIssue


class OffboardOptions(BaseModel):
    """Batch-wide choices; applied identically to every target in the request."""

    revoke_licenses: bool = True
    remove_from_groups: bool = True
    keep_distribution_lists: bool = True
    convert_mailbox_to_shared: bool = True
    grant_mailbox_access_to: str | None = None  # manager sAMAccountName, for handover
    move_to_ou: str | None = None  # e.g. the "Disabled Users" OU distinguishedName
    reset_password: bool = True  # randomize the password even though the account is disabled


class OffboardTarget(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sam_account_name: str = Field(min_length=1)
    reason: str | None = None  # e.g. "Resigned", "Terminated", "Contract ended" - audit only


class OffboardRequest(BaseModel):
    users: list[OffboardTarget] = Field(min_length=1, max_length=50)
    options: OffboardOptions = Field(default_factory=OffboardOptions)


class OffboardResolvedUser(BaseModel):
    """A target enriched with the directory's current record, used to build
    the plan and to drive the job (so the job never has to re-look-up the
    user mid-execution)."""

    sam_account_name: str
    display_name: str
    user_principal_name: str
    email: str | None
    ou: str | None
    enabled: bool
    reason: str | None = None


class OffboardValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue]
    users: list[OffboardResolvedUser]


class OffboardUserPlan(BaseModel):
    sam_account_name: str
    display_name: str
    user_principal_name: str
    email: str | None
    ou: str | None
    actions: list[PlanAction]
    warnings: list[str] = Field(default_factory=list)


class OffboardExecutionPlan(BaseModel):
    summary: str
    total_users: int
    total_actions: int
    users: list[OffboardUserPlan]
    issues: list[ValidationIssue] = Field(default_factory=list)
