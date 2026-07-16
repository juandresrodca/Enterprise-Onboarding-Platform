"""Directory reads: OU tree, groups, licenses, shared mailboxes, manager search."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_provider, require
from app.models.auth import CurrentUser
from app.services.provider import IdentityProvider

router = APIRouter(tags=["directory"])


@router.get("/ou")
async def ou_tree(
    _: CurrentUser = Depends(require("directory:read")),
    provider: IdentityProvider = Depends(get_provider),
):
    return {"tree": await provider.list_ous()}


@router.get("/groups")
async def groups(
    search: str = "",
    category: str | None = None,
    limit: int = 100,
    _: CurrentUser = Depends(require("directory:read")),
    provider: IdentityProvider = Depends(get_provider),
):
    items = await provider.list_groups(search=search, category=category,
                                       limit=min(limit, 500))
    return {"groups": items, "count": len(items)}


@router.get("/licenses")
async def licenses(
    _: CurrentUser = Depends(require("directory:read")),
    provider: IdentityProvider = Depends(get_provider),
):
    return {"licenses": await provider.list_licenses()}


@router.get("/shared-mailboxes")
async def shared_mailboxes(
    _: CurrentUser = Depends(require("directory:read")),
    provider: IdentityProvider = Depends(get_provider),
):
    return {"mailboxes": await provider.list_shared_mailboxes()}


@router.get("/managers")
async def managers(
    query: str = "",
    limit: int = 10,
    _: CurrentUser = Depends(require("directory:read")),
    provider: IdentityProvider = Depends(get_provider),
):
    users = await provider.list_users(query=query, limit=min(limit, 25))
    return {"managers": users}
