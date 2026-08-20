from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.database import get_db
from app.models import AuditLog, InventoryEvent, Order, OrderStatusHistory, User
from app.schemas import (
    ConfirmOrderResponse,
    OrderDetail,
    OrderListResponse,
    OrderOut,
    OrderStatusUpdate,
)
from app.services.writeback import WritebackService

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_to_out(order: Order) -> OrderOut:
    return OrderOut.model_validate(order)


@router.get("", response_model=OrderListResponse)
def list_orders(
    status: str | None = Query(None),
    wilaya: str | None = Query(None),
    channel: str | None = Query(None),
    search: str | None = Query(None),
    product: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at:desc"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = tenant_query(db, Order, user.tenant_id)
    if status:
        q = q.filter(Order.status == status)
    if wilaya:
        q = q.filter(Order.wilaya == wilaya)
    if channel:
        q = q.filter(Order.source_channel == channel)
    if product:
        q = q.filter(Order.product.ilike(f"%{product}%"))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Order.name.ilike(like), Order.phone.ilike(like), Order.order_id.ilike(like)))
    if date_from:
        q = q.filter(Order.created_at >= date_from)
    if date_to:
        q = q.filter(Order.created_at <= date_to)

    field, _, direction = sort.partition(":")
    col = getattr(Order, field, Order.created_at)
    order = col.desc() if direction == "desc" else col.asc()
    total = q.count()
    items = q.order_by(order).offset((page - 1) * limit).limit(limit).all()
    return OrderListResponse(
        items=[_order_to_out(o) for o in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    detail = OrderDetail.model_validate(order)
    detail.status_history = [
        {"from": h.from_status, "to": h.to_status, "at": h.changed_at} for h in order.status_history
    ]
    return detail


@router.post("/{order_id}/confirm", response_model=ConfirmOrderResponse)
def confirm_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.confirm")),
):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "confirmed":
        raise HTTPException(status_code=409, detail="Order already confirmed")
    if order.status != "new":
        raise HTTPException(status_code=409, detail=f"Cannot confirm order in status '{order.status}'")

    wb = WritebackService(db, user.tenant_id)
    result = wb.confirm_order(order, actor_id=user.id)
    if result is None:
        raise HTTPException(status_code=409, detail="Insufficient stock to confirm this order")

    order_out = _order_to_out(order)
    return ConfirmOrderResponse(order=order_out, stock_after=result, message="Order confirmed")


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.update_status")),
):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")

    from_status = order.status
    order.status = payload.status
    db.add(OrderStatusHistory(
        order_id=order.id,
        from_status=from_status,
        to_status=payload.status,
        changed_by=user.id,
    ))
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        actor=user.id,
        action="order.status.update",
        entity_type="order",
        entity_id=str(order.order_id or order.id),
        payload={"from": from_status, "to": payload.status, "note": payload.note},
    ))
    db.commit()
    db.refresh(order)
    return _order_to_out(order)