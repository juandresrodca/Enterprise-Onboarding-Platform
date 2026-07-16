"""Builds the human-readable execution plan shown before approval.

Nothing is executed here; the plan is a faithful projection of exactly what
the job engine will do for each user.
"""

from __future__ import annotations

from app.config import Settings
from app.models.user import (
    ExecutionPlan, NewUserSpec, PlanAction, UserPlan, ValidationIssue,
)


def build_plan(
    users: list[NewUserSpec],
    settings: Settings,
    issues: list[ValidationIssue] | None = None,
    job_type: str = "onboard",
) -> ExecutionPlan:
    plans: list[UserPlan] = []
    total_actions = 0

    for i, u in enumerate(users):
        actions: list[PlanAction] = []
        warnings = [
            iss.message for iss in (issues or [])
            if iss.index == i and iss.severity == "warning"
        ]

        attr_count = sum(
            1 for f in (
                u.department, u.company, u.office, u.office_location, u.job_title,
                u.employee_id, u.employee_type, u.cost_center, u.description,
                u.phone, u.mobile, u.country, u.city, u.state, u.address,
                u.postal_code,
            ) if f
        )
        details = [f"OU: {u.ou}"]
        if u.job_title:
            details.append(f"Title: {u.job_title}")
        if u.department:
            details.append(f"Department: {u.department}")
        if u.manager:
            details.append(f"Manager: {u.manager}")
        if u.account_expiration:
            details.append(f"Account expires: {u.account_expiration.isoformat()}")
        details.append(f"{attr_count} directory attributes will be set")
        pw = ("Generate secure password" if u.password.generate else "Use provided password")
        if u.password.force_change_at_logon:
            pw += " · user must change at first logon"
        details.append(pw)
        actions.append(PlanAction(kind="create", summary="Create Active Directory account",
                                  details=details))

        if u.groups:
            actions.append(PlanAction(
                kind="groups", summary=f"Add to {len(u.groups)} group(s)", details=u.groups))
        if u.licenses:
            actions.append(PlanAction(
                kind="licenses", summary=f"Assign {len(u.licenses)} license(s)",
                details=u.licenses))
        if u.create_mailbox:
            actions.append(PlanAction(
                kind="mailbox", summary="Provision Exchange Online mailbox",
                details=[f"Primary SMTP: {u.email or u.user_principal_name}"]))
        if u.shared_mailboxes:
            actions.append(PlanAction(
                kind="shared_mailboxes",
                summary=f"Grant access to {len(u.shared_mailboxes)} shared mailbox(es)",
                details=u.shared_mailboxes))
        if u.proxy_addresses:
            actions.append(PlanAction(
                kind="proxy", summary=f"Set {len(u.proxy_addresses)} proxy address(es)",
                details=u.proxy_addresses))
        if u.extension_attributes:
            actions.append(PlanAction(
                kind="extensions",
                summary=f"Set {len(u.extension_attributes)} extension attribute(s)",
                details=[f"{k} = {v}" for k, v in u.extension_attributes.items()]))
        if u.home_folder.enabled:
            base = u.home_folder.base_path or settings.default_home_base_path
            actions.append(PlanAction(
                kind="home_folder", summary="Create home folder + map network drive",
                details=[f"{base}\\{u.sam_account_name} -> {u.home_folder.drive_letter}:"]))
        if u.profile.roaming_profile_path or u.profile.logon_script:
            det = []
            if u.profile.roaming_profile_path:
                det.append(f"Roaming profile: {u.profile.roaming_profile_path}")
            if u.profile.logon_script:
                det.append(f"Logon script: {u.profile.logon_script}")
            actions.append(PlanAction(kind="profile", summary="Configure user profile",
                                      details=det))

        total_actions += len(actions)
        plans.append(UserPlan(
            display_name=u.display_name or f"{u.first_name} {u.last_name}",
            sam_account_name=u.sam_account_name or "",
            user_principal_name=u.user_principal_name or "",
            email=u.email,
            ou=u.ou or "",
            manager=u.manager,
            actions=actions,
            warnings=warnings,
        ))

    verb = "cloned from template" if job_type == "clone" else "onboarded"
    return ExecutionPlan(
        summary=f"{len(users)} user(s) will be {verb} with {total_actions} total actions",
        total_users=len(users),
        total_actions=total_actions,
        users=plans,
        issues=issues or [],
    )
