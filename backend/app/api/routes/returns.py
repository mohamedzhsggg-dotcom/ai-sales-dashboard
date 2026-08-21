"""Returns API.

Manage order returns with stock restoration and refund tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.context import ensure_tenant, tenant_query
from app.core.events import bus
from app.core.rbac import require_permission
from app.database import get_db
from app.models import Order, OrderItem, Product, ProductVariant, Return, User
from app.schemas import ReturnAction, ReturnCreate, ReturnOut

router = APIRouter(prefix="/returns", tags=["returns"])


def _return_to_out(r: Return) -> ReturnOut:
    return ReturnOut(
        id=r.id, tenant_id=r.tenant_id, order_id=r.order_id,
        order_item_id=r.order_item_id, variant_id=r.variant_id,
        quantity=r.quantity, reason=r.reason, refund_amount=r.refund_amount,
        status=r.status, note=r.note, created_by=r.created_by,
        created_at=r.created_at, processed_at=r.processed_at,
    )


@router.get("", response_model=list[ReturnOut])
def list_returns(
    status: Optional[str] = Query(None),
    order_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.read")),
):
    q = tenant_query(db, Return, user.tenant_id)
    if status:
        q = q.filter(Return.status == status)
    if order_id:
        q = q.filter(Return.order_id == order_id)
    returns = q.order_by(Return.created_at.desc()).limit(limit).all()
    return [_return_to_out(r) for r in returns]


@router.get("/{return_id}", response_model=ReturnOut)
def get_return(
    return_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.read")),
):
    ret = db.get(Return, return_id)
    if not ensure_tenant(ret, user.tenant_id):
        raise HTTPException(status_code=404, detail="Return not found")
    return _return_to_out(ret)


@router.post("", response_model=ReturnOut, status_code=201)
def create_return(
    order_id: int,
    payload: ReturnCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.manage")),
):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("delivered", "confirmed"):
        raise HTTPException(status_code=409, detail=f"Cannot return order with status '{order.status}'")

    if payload.order_item_id:
        item = db.get(OrderItem, payload.order_item_id)
        if not item or item.order_id != order.id:
            raise HTTPException(status_code=400, detail="Order item does not belong to this order")
        if payload.quantity > item.quantity:
            raise HTTPException(status_code=400, detail="Return quantity exceeds ordered quantity")

    ret = Return(
        tenant_id=user.tenant_id,
        order_id=order.id,
        order_item_id=payload.order_item_id,
        variant_id=payload.variant_id,
        quantity=payload.quantity,
        reason=payload.reason,
        refund_amount=payload.refund_amount,
        note=payload.note,
        created_by=user.id,
        status="pending",
    )
    db.add(ret)
    db.commit()
    db.refresh(ret)

    bus.publish("return_created", {"return_id": ret.id, "order_id": order.id, "tenant_id": user.tenant_id})
    return _return_to_out(ret)


@router.patch("/{return_id}/approve", response_model=ReturnOut)
def approve_return(
    return_id: int,
    payload: ReturnAction = ReturnAction(),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.manage")),
):
    ret = db.get(Return, return_id)
    if not ensure_tenant(ret, user.tenant_id):
        raise HTTPException(status_code=404, detail="Return not found")
    if ret.status != "pending":
        raise HTTPException(status_code=409, detail=f"Cannot approve return with status '{ret.status}'")

    ret.status = "approved"
    ret.processed_at = datetime.now(timezone.utc)
    if payload.note:
        ret.note = payload.note

    # Restore stock
    if ret.order_item_id:
        item = db.get(OrderItem, ret.order_item_id)
        if item and item.product_id:
            product = db.get(Product, item.product_id)
            if product:
                product.stock += ret.quantity

    db.commit()
    db.refresh(ret)
    bus.publish("return_approved", {"return_id": ret.id, "order_id": ret.order_id, "tenant_id": user.tenant_id})
    return _return_to_out(ret)


@router.patch("/{return_id}/reject", response_model=ReturnOut)
def reject_return(
    return_id: int,
    payload: ReturnAction = ReturnAction(),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.manage")),
):
    ret = db.get(Return, return_id)
    if not ensure_tenant(ret, user.tenant_id):
        raise HTTPException(status_code=404, detail="Return not found")
    if ret.status != "pending":
        raise HTTPException(status_code=409, detail=f"Cannot reject return with status '{ret.status}'")

    ret.status = "rejected"
    ret.processed_at = datetime.now(timezone.utc)
    if payload.note:
        ret.note = payload.note

    db.commit()
    db.refresh(ret)
    bus.publish("return_rejected", {"return_id": ret.id, "order_id": ret.order_id, "tenant_id": user.tenant_id})
    return _return_to_out(ret)
