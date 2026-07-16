"""User onboarding endpoints: list/detail, validate, preview, create, bulk, clone."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse

from app.api.deps import (
    client_ip, get_jobs, get_provider, get_validator, require,
)
from app.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.models.auth import CurrentUser
from app.models.user import (
    CloneRequest, CreateUsersRequest, ExecutionPlan, ValidationResult,
)
from app.services import clone as clone_svc
from app.services import importer, preview
from app.services.jobs import JobManager
from app.services.provider import IdentityProvider
from app.services.validation import Validator

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(
    query: str = "",
    limit: int = 50,
    recent: bool = False,
    _: CurrentUser = Depends(require("users:read")),
    provider: IdentityProvider = Depends(get_provider),
):
    users = await provider.list_users(query=query, limit=min(limit, 500), recent_first=recent)
    return {"users": users, "count": len(users)}


@router.get("/template.csv", response_class=PlainTextResponse)
async def bulk_template(_: CurrentUser = Depends(require("users:bulk"))):
    return PlainTextResponse(
        importer.build_template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=onboarding-template.csv"},
    )


@router.get("/{sam}")
async def get_user(
    sam: str,
    _: CurrentUser = Depends(require("users:read")),
    provider: IdentityProvider = Depends(get_provider),
):
    user = await provider.get_user(sam, expand=True)
    if not user:
        raise NotFoundError(f"User '{sam}' not found")
    return {"user": user}


@router.post("/validate", response_model=ValidationResult)
async def validate_users(
    body: CreateUsersRequest,
    _: CurrentUser = Depends(require("users:read")),
    validator: Validator = Depends(get_validator),
):
    return await validator.validate(body.users)


@router.post("/preview", response_model=ExecutionPlan)
async def preview_users(
    body: CreateUsersRequest,
    _: CurrentUser = Depends(require("users:read")),
    validator: Validator = Depends(get_validator),
    settings: Settings = Depends(get_settings),
):
    result = await validator.validate(body.users)
    return preview.build_plan(result.users, settings, issues=result.issues)


@router.post("/create", status_code=202)
async def create_users(
    body: CreateUsersRequest,
    request: Request,
    user: CurrentUser = Depends(require("users:create")),
    validator: Validator = Depends(get_validator),
    jobs: JobManager = Depends(get_jobs),
):
    result = await validator.validate(body.users)
    if not result.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validation failed; nothing was executed.",
                "issues": [i.model_dump() for i in result.issues],
            },
        )
    job = await jobs.submit("onboard", result.users, user, source_ip=client_ip(request))
    return {"job_id": job.id, "status": job.status.value, "total": job.total}


@router.post("/bulk")
async def bulk_parse(
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require("users:bulk")),
    validator: Validator = Depends(get_validator),
):
    """Parse an uploaded CSV/XLSX/JSON file and run full validation.

    Execution is a separate, explicit step: the client reviews the parsed
    users + issues, then submits them through POST /users/create.
    """
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(status_code=413, detail="File exceeds the 5 MB limit")
    rows = importer.parse_upload(file.filename or "", content)
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="A batch may contain at most 200 users")
    users, parse_issues = importer.rows_to_specs(rows)
    result = await validator.validate(users)
    all_issues = [*parse_issues, *result.issues]
    return {
        "filename": file.filename,
        "rows": len(rows),
        "valid": result.valid and not parse_issues,
        "issues": [i.model_dump() for i in all_issues],
        "users": [u.model_dump(mode="json") for u in result.users],
    }


@router.post("/clone", status_code=202)
async def clone_user(
    body: CloneRequest,
    request: Request,
    execute: bool = False,
    user: CurrentUser = Depends(require("users:clone")),
    provider: IdentityProvider = Depends(get_provider),
    validator: Validator = Depends(get_validator),
    settings: Settings = Depends(get_settings),
    jobs: JobManager = Depends(get_jobs),
):
    """Copy attribute families from an existing user onto one or more new users.

    With execute=false (default) this returns the merged users, validation
    issues and an execution plan for review. With execute=true it queues the
    onboarding job.
    """
    source = await clone_svc.load_source(provider, body.source_sam)
    merged = [clone_svc.apply_clone(source, body.options, u) for u in body.users]
    result = await validator.validate(merged)

    if not execute:
        plan = preview.build_plan(result.users, settings, issues=result.issues,
                                  job_type="clone")
        return {
            "source": {
                "sam_account_name": source["sam_account_name"],
                "display_name": source["display_name"],
            },
            "valid": result.valid,
            "issues": [i.model_dump() for i in result.issues],
            "users": [u.model_dump(mode="json") for u in result.users],
            "plan": plan.model_dump(mode="json"),
        }

    if not result.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validation failed; nothing was executed.",
                "issues": [i.model_dump() for i in result.issues],
            },
        )
    job = await jobs.submit("clone", result.users, user, source_ip=client_ip(request))
    return {"job_id": job.id, "status": job.status.value, "total": job.total}
