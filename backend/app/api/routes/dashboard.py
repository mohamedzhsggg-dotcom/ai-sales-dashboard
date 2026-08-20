from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.context import tenant_query
from app.core.security import get_current_user
from app.database import get_db
from app.models import Order, Product, User
from app.schemas import DashboardStats, OrderOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenant_id = user.tenant_id

    new_orders = (
        tenant_query(db, Order, tenant_id)
        .filter(Order.status == "new")
        .count()
    )
    confirmed = (
        tenant_query(db, Order, tenant_id)
        .filter(Order.status == "confirmed")
        .count()
    )
    total_revenue = (
        db.query(func.coalesce(func.sum(Order.price * Order.quantity), 0))
        .filter(Order.tenant_id == tenant_id, Order.status.in_(["confirmed", "delivered"]))
        .scalar() or 0
    )
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
    return DashboardStats(
        new_orders=new_orders,
        confirmed_orders=confirmed,
        total_revenue=total_revenue,
        low_stock_count=low_stock,
        by_wilaya=by_wilaya,
        recent_orders=[OrderOut.model_validate(o) for o in recent],
    )