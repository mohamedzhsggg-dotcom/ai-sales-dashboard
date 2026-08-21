from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.database import get_db
from app.models import Customer, Order, User
from app.schemas import (
    CustomerDetail,
    CustomerListResponse,
    CustomerOut,
    OrderOut,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
def list_customers(
    search: str | None = Query(None),
    wilaya: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    q = tenant_query(db, Customer, user.tenant_id)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Customer.name.ilike(like), Customer.phone.ilike(like)))
    if wilaya:
        q = q.filter(Customer.wilaya == wilaya)

    total = q.count()
    customers = q.order_by(Customer.updated_at.desc()).offset((page - 1) * limit).limit(limit).all()

    customer_ids = [c.id for c in customers]
    order_counts = dict(
        db.query(Order.customer_id, func.count(Order.id))
        .filter(Order.tenant_id == user.tenant_id, Order.customer_id.in_(customer_ids))
        .group_by(Order.customer_id)
        .all()
    )
    total_spent = dict(
        db.query(Order.customer_id, func.coalesce(func.sum(Order.price * Order.quantity), 0))
        .filter(Order.tenant_id == user.tenant_id, Order.customer_id.in_(customer_ids),
                Order.status.in_(["confirmed", "delivered"]))
        .group_by(Order.customer_id)
        .all()
    )
    last_orders = dict(
        db.query(Order.customer_id, func.max(Order.created_at))
        .filter(Order.tenant_id == user.tenant_id, Order.customer_id.in_(customer_ids))
        .group_by(Order.customer_id)
        .all()
    )

    items = []
    for c in customers:
        out = CustomerOut.model_validate(c)
        out.order_count = order_counts.get(c.id, 0)
        out.total_spent = total_spent.get(c.id, 0)
        out.last_order_at = last_orders.get(c.id)
        items.append(out)
    return CustomerListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    customer = db.get(Customer, customer_id)
    if not ensure_tenant(customer, user.tenant_id):
        raise HTTPException(status_code=404, detail="Customer not found")
    detail = CustomerDetail.model_validate(customer)
    orders = list(
        tenant_query(db, Order, user.tenant_id)
        .filter(Order.customer_id == customer.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    detail.orders = [OrderOut.model_validate(o) for o in orders]
    detail.order_count = len(orders)
    detail.total_spent = sum(
        o.price * o.quantity for o in orders if o.status in ("confirmed", "delivered")
    )
    if orders:
        detail.last_order_at = max(o.created_at for o in orders)
    return detail