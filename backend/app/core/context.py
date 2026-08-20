"""Central tenant isolation helpers.

Every tenant-scoped query must go through `tenant_query()` so a missed filter
cannot silently leak data across tenants. The tenant_id is always taken from the
authenticated user (JWT claim / DB row), never from request input.
"""

from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Query

from app.core.security import get_current_user
from app.models import User

# Models that carry a tenant_id column and are scoped per tenant.
# New tenant-scoped models MUST be added here or tenant_query() refuses them.
TENANT_SCOPED_MODELS = (
    "SheetConfig",
    "Customer",
    "Product",
    "Order",
    "OrderStatusHistory",
    "InventoryEvent",
    "AuditLog",
    "SyncRun",
)


def tenant_query(db, model: Any, tenant_id: int) -> Query:
    """Return a tenant-scoped SQLAlchemy query for the given model.

    Raises ValueError for models not registered as tenant-scoped so a new model
    cannot accidentally bypass isolation.
    """
    if model.__name__ not in TENANT_SCOPED_MODELS:
        raise ValueError(f"{model.__name__} is not registered as a tenant-scoped model")
    return db.query(model).filter(model.tenant_id == tenant_id)


def ensure_tenant(instance: Any, tenant_id: int) -> bool:
    """Return True if the instance belongs to the tenant, else False."""
    return instance is not None and getattr(instance, "tenant_id", None) == tenant_id


def get_current_tenant_user(user: User = Depends(get_current_user)) -> User:
    """Dependency exposing the authenticated, tenant-bound user."""
    return user