from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import Order, Product, User
from app.schemas import DashboardStats, OrderOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenant_id = user.tenant_id

    new_orders = (
        db.query(func.count(Order.id)).filter(Order.tenant_id == tenant_id, Order.status == "new").scalar() or 0
    )
    confirmed = (
        db.query(func.count(Order.id))
        .filter(Order.tenant_id == tenant_id, Order.status == "confirmed")
        .scalar() or 0
    )
    total_revenue = (
        db.query(func.coalesce(func.sum(Order.price * Order.quantity), 0))
        .filter(Order.tenant_id == tenant_id, Order.status.in_(["confirmed", "delivered"]))
        .scalar() or 0
    )
    low_stock = (
        db.query(func.count(Product.id))
        .filter(Product.tenant_id == tenant_id, Product.stock > 0, Product.stock <= 5)
        .scalar() or 0
    )
    by_wilaya = [
        {"wilaya": w, "count": c}
        for w, c in db.query(Order.wilaya, func.count(Order.id))
        .filter(Order.tenant_id == tenant_id)
        .group_by(Order.wilaya)
        .order_by(func.count(Order.id).desc())
        .all()
    ]
    recent = (
        db.query(Order)
        .filter(Order.tenant_id == tenant_id)
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