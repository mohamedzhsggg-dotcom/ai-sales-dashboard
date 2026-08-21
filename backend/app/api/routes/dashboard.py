from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.context import tenant_query
from app.core.rbac import require_permission
from app.database import get_db
from app.models import AuditLog, Order, Product, User
from app.schemas import DashboardStats, OrderOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), user: User = Depends(require_permission("dashboard.read"))):
    tenant_id = user.tenant_id

    new_orders = (
        tenant_query(db, Order, tenant_id).filter(Order.status == "new").count()
    )
    confirmed = (
        tenant_query(db, Order, tenant_id).filter(Order.status == "confirmed").count()
    )
    shipped = (
        tenant_query(db, Order, tenant_id).filter(Order.status == "shipped").count()
    )
    delivered = (
        tenant_query(db, Order, tenant_id).filter(Order.status == "delivered").count()
    )
    cancelled = (
        tenant_query(db, Order, tenant_id).filter(Order.status == "cancelled").count()
    )
    returned = (
        tenant_query(db, Order, tenant_id).filter(Order.status == "returned").count()
    )
    total_revenue = (
        db.query(func.coalesce(func.sum(Order.price * Order.quantity), 0))
        .filter(Order.tenant_id == tenant_id, Order.status.in_(["confirmed", "delivered"]))
        .scalar() or 0
    )
    total_products = tenant_query(db, Product, tenant_id).count()
    low_stock = (
        tenant_query(db, Product, tenant_id)
        .filter(Product.stock > 0, Product.stock <= 5)
        .count()
    )
    by_wilaya = [
        {"wilaya": w, "count": c}
        for w, c in tenant_query(db, Order, tenant_id)
        .with_entities(Order.wilaya, func.count(Order.id))
        .group_by(Order.wilaya)
        .order_by(func.count(Order.id).desc())
        .all()
    ]
    recent = (
        tenant_query(db, Order, tenant_id)
        .order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )
    activity = (
        tenant_query(db, AuditLog, tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(15)
        .all()
    )
    return DashboardStats(
        new_orders=new_orders,
        confirmed_orders=confirmed,
        shipped_orders=shipped,
        delivered_orders=delivered,
        cancelled_orders=cancelled,
        returned_orders=returned,
        total_revenue=total_revenue,
        total_products=total_products,
        low_stock_count=low_stock,
        by_wilaya=by_wilaya,
        recent_orders=[OrderOut.model_validate(o) for o in recent],
        recent_activity=[
            {
                "id": a.id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activity
        ],
    )