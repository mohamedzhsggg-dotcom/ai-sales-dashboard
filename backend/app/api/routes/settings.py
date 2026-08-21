"""Merchant settings API.

Manage tenant configuration, social account settings, and courier configuration.
API credentials are never exposed in responses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.context import ensure_tenant
from app.core.rbac import require_permission
from app.database import get_db
from app.models import Tenant, User
from app.schemas import UserOut

router = APIRouter(prefix="/settings", tags=["settings"])


class TenantSettingsOut(BaseModel):
    business_name: str
    slug: str
    has_sheets_config: bool = False
    has_meta_config: bool = False
    has_courier_config: bool = False


class UpdateSettingsRequest(BaseModel):
    business_name: str | None = None
    meta_config: dict | None = None
    courier_config: dict | None = None


@router.get("", response_model=TenantSettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dashboard.read")),
):
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    config = tenant.config or {}
    return TenantSettingsOut(
        business_name=tenant.name,
        slug=tenant.slug,
        has_sheets_config=bool(config.get("sheets")),
        has_meta_config=bool(config.get("meta_config")),
        has_courier_config=bool(config.get("courier_config")),
    )


@router.patch("", response_model=TenantSettingsOut)
def update_settings(
    payload: UpdateSettingsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dashboard.manage")),
):
    tenant = db.get(Tenant, user.tenant_id)
    if not ensure_tenant(tenant, user.tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found")
    if payload.business_name:
        tenant.name = payload.business_name
    config = tenant.config or {}
    if payload.meta_config is not None:
        config["meta_config"] = payload.meta_config
    if payload.courier_config is not None:
        config["courier_config"] = payload.courier_config
    tenant.config = config
    db.commit()
    db.refresh(tenant)
    return TenantSettingsOut(
        business_name=tenant.name,
        slug=tenant.slug,
        has_sheets_config=bool(config.get("sheets")),
        has_meta_config=bool(config.get("meta_config")),
        has_courier_config=bool(config.get("courier_config")),
    )
