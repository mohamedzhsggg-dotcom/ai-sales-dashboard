"""Orders API.

Multi-item order management with status machine, confirmation
(stock deduction), cancellation, and returns.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.core.status_machine import validate_transition, needs_reason, InvalidTransition
from app.database import get_db
from app.models import Customer, Order, OrderItem, OrderStatusHistory, Product, ProductVariant, Return, User
from app.schemas import (
    ConfirmOrderResponse,
    OrderCreate,
    OrderDetail,
    OrderItemOut,
    OrderListResponse,
    OrderOut,
    OrderStatusUpdate,
    ReturnAction,
    ReturnCreate,
    ReturnOut,
)
from app.services.stock import StockService, InsufficientStock, StockError

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_to_out(o: Order) -> OrderOut:
    return OrderOut(
        id=o.id, tenant_id=o.tenant_id, order_id=o.order_id,
        phone=o.phone, name=o.name, wilaya=o.wilaya, commune=o.commune,
        product=o.product, color=o.color, size=o.size,
        quantity=o.quantity, price=o.price,
        delivery_method=o.delivery_method, status=o.status,
        source_channel=o.source_channel,
        subtotal=o.subtotal or 0, shipping_fee=o.shipping_fee or 0,
        total=o.total or 0, currency=o.currency or "DZD",
        items_count=o.items_count or 1, notes=o.notes,
        has_return=o.has_return or False,
        created_at=o.created_at, updated_at=o.updated_at,
    )


def _resolve_customer(db: Session, tenant_id: int, phone: str, name: Optional[str]) -> Customer:
    customer = db.query(Customer).filter(
        Customer.tenant_id == tenant_id, Customer.phone == phone
    ).first()
    if not customer:
        customer = Customer(tenant_id=tenant_id, phone=phone, name=name)
        db.add(customer)
        db.flush()
    elif name and not customer.name:
        customer.name = name
    return customer


@router.get("", response_model=OrderListResponse)
def list_orders(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.read")),
):
    q = tenant_query(db, Order, user.tenant_id)
    if status:
        q = q.filter(Order.status == status)
    if search:
        like = f"%{search}%"
        from sqlalchemy import or_
        q = q.filter(or_(
            Order.name.ilike(like), Order.phone.ilike(like),
            Order.order_id.ilike(like),
        ))
    total = q.count()
    items = q.order_by(Order.created_at.desc()).offset(
        (page - 1) * limit
    ).limit(limit).all()
    return OrderListResponse(
        items=[_order_to_out(o) for o in items],
        total=total, page=page, limit=limit,
    )


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.read")),
):
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    out = _order_to_out(order)
    return OrderDetail(
        **out.model_dump(),
        customer_id=order.customer_id,
        items=[
            OrderItemOut(
                id=it.id, product_id=it.product_id, product_name=it.product_name,
                variant_id=it.variant_id, variant_options=it.variant_options,
                sku=it.sku, quantity=it.quantity, unit_price=it.unit_price,
                subtotal=it.subtotal,
            )
            for it in order.items
        ],
        cancel_reason=order.cancel_reason,
        cancel_note=order.cancel_note,
    )


@router.post("", response_model=OrderDetail, status_code=201)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.create")),
):
    customer = _resolve_customer(db, user.tenant_id, payload.phone, payload.name)
    order_items = []
    subtotal = 0

    for item_in in payload.items:
        product = None
        variant = None
        product_name = None
        sku = None
        unit_price = item_in.unit_price or 0

        if item_in.product_id:
            product = db.get(Product, item_in.product_id)
            if not ensure_tenant(product, user.tenant_id):
                raise HTTPException(status_code=404, detail=f"Product {item_in.product_id} not found")
            product_name = product.name
            sku = product.sku

        if item_in.variant_id:
            variant = db.get(ProductVariant, item_in.variant_id)
            if not ensure_tenant(variant, user.tenant_id):
                raise HTTPException(status_code=404, detail=f"Variant {item_in.variant_id} not found")
            if variant.product_id != item_in.product_id:
                raise HTTPException(status_code=422, detail="Variant does not belong to product")
            sku = variant.sku
            if item_in.unit_price is None:
                unit_price = variant.price if variant.price is not None else (product.price if product else 0)
        elif product and item_in.unit_price is None:
            unit_price = product.price or 0

        line_subtotal = unit_price * item_in.quantity
        subtotal += line_subtotal

        order_items.append(OrderItem(
            tenant_id=user.tenant_id,
            product_id=item_in.product_id,
            product_name=product_name,
            variant_id=item_in.variant_id,
            variant_options=variant.options if variant else None,
            sku=sku,
            quantity=item_in.quantity,
            unit_price=unit_price,
            subtotal=line_subtotal,
        ))

    order = Order(
        tenant_id=user.tenant_id,
        customer_id=customer.id,
        phone=customer.phone,
        name=customer.name,
        wilaya=payload.wilaya,
        commune=payload.commune,
        delivery_method=payload.delivery_method,
        source_channel=payload.source_channel,
        notes=payload.notes,
        status="new",
        subtotal=subtotal,
        total=subtotal + (0),
        items_count=sum(it.quantity for it in order_items),
        product=order_items[0].product_name if order_items else None,
        quantity=order_items[0].quantity if order_items else 1,
        price=order_items[0].unit_price if order_items else 0,
    )
    db.add(order)
    db.flush()

    for it in order_items:
        it.order_id = order.id
        db.add(it)

    db.commit()
    db.refresh(order)
    out = _order_to_out(order)
    return OrderDetail(
        **out.model_dump(),
        customer_id=order.customer_id,
        items=[
            OrderItemOut(
                id=it.id, product_id=it.product_id, product_name=it.product_name,
                variant_id=it.variant_id, variant_options=it.variant_options,
                sku=it.sku, quantity=it.quantity, unit_price=it.unit_price,
                subtotal=it.subtotal,
            )
            for it in order.items
        ],
    )


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.update_status")),
):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = payload.status
    try:
        validate_transition(order.status, new_status)
    except InvalidTransition as e:
        raise HTTPException(status_code=422, detail=str(e))

    if needs_reason(new_status) and not payload.note:
        raise HTTPException(status_code=422, detail=f"Note required for transition to '{new_status}'")

    history = OrderStatusHistory(
        order_id=order.id, from_status=order.status,
        to_status=new_status, changed_by=user.id,
    )
    db.add(history)

    if new_status == "cancelled":
        order.cancel_reason = payload.note

    order.status = new_status
    db.commit()
    db.refresh(order)
    return _order_to_out(order)


@router.post("/{order_id}/confirm", response_model=ConfirmOrderResponse)
def confirm_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.confirm")),
):
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "new":
        raise HTTPException(status_code=409, detail=f"Order is '{order.status}', not 'new'")

    svc = StockService(db, user.tenant_id)
    shortages = []

    for item in order.items:
        if item.product_id:
            current = svc.current(product_id=item.product_id, variant_id=item.variant_id)
            if current < item.quantity:
                shortages.append({
                    "product_id": item.product_id,
                    "variant_id": item.variant_id,
                    "product_name": item.product_name,
                    "available": current,
                    "requested": item.quantity,
                })

    if shortages:
        raise HTTPException(status_code=409, detail={"shortages": shortages})

    for item in order.items:
        if item.product_id:
            svc.deduct(
                product_id=item.product_id, variant_id=item.variant_id,
                quantity=item.quantity, reason="order_confirmed",
                order_id=order.id, actor_id=user.id,
            )

    order.status = "confirmed"
    history = OrderStatusHistory(
        order_id=order.id, from_status="new",
        to_status="confirmed", changed_by=user.id,
    )
    db.add(history)
    db.commit()
    db.refresh(order)
    return ConfirmOrderResponse(order=_order_to_out(order), message="Order confirmed, stock deducted")


@router.patch("/{order_id}", response_model=OrderOut)
def update_order(
    order_id: int,
    payload: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.edit")),
):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "new":
        raise HTTPException(status_code=409, detail="Can only edit orders in 'new' status")

    order.phone = payload.phone
    order.name = payload.name
    order.wilaya = payload.wilaya
    order.commune = payload.commune
    order.delivery_method = payload.delivery_method
    order.source_channel = payload.source_channel
    order.notes = payload.notes
    db.commit()
    db.refresh(order)
    return _order_to_out(order)


# ── Returns ──────────────────────────────────────────────────────────────────


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    payload: ReturnAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.cancel")),
):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        validate_transition(order.status, "cancelled")
    except InvalidTransition as e:
        raise HTTPException(status_code=422, detail=str(e))

    if order.status in ("confirmed", "shipped"):
        items = tenant_query(db, OrderItem, user.tenant_id).filter(
            OrderItem.order_id == order.id
        ).all()
        svc = StockService(db, user.tenant_id)
        for item in items:
            if item.product_id:
                svc.add(
                    product_id=item.product_id, variant_id=item.variant_id,
                    quantity=item.quantity, reason="order_cancelled",
                    order_id=order.id, actor_id=user.id,
                )

    order.status = "cancelled"
    order.cancel_reason = payload.note
    history = OrderStatusHistory(
        order_id=order.id, from_status=order.status,
        to_status="cancelled", changed_by=user.id,
    )
    db.add(history)
    db.commit()
    db.refresh(order)
    return _order_to_out(order)


@router.post("/{order_id}/return", response_model=ReturnOut, status_code=201)
def create_return(
    order_id: int,
    payload: ReturnCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.return")),
):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")

    ret = Return(
        tenant_id=user.tenant_id,
        order_id=order_id,
        order_item_id=payload.order_item_id,
        variant_id=payload.variant_id,
        quantity=payload.quantity,
        reason=payload.reason,
        refund_amount=payload.refund_amount,
        status="pending",
        note=payload.note,
        created_by=user.id,
    )
    db.add(ret)
    order.has_return = True
    db.commit()
    db.refresh(ret)
    return ReturnOut(
        id=ret.id, tenant_id=ret.tenant_id, order_id=ret.order_id,
        order_item_id=ret.order_item_id, variant_id=ret.variant_id,
        quantity=ret.quantity, reason=ret.reason,
        refund_amount=ret.refund_amount, status=ret.status,
        note=ret.note, created_by=ret.created_by,
        created_at=ret.created_at, processed_at=ret.processed_at,
    )


@router.get("/{order_id}/returns", response_model=list[ReturnOut])
def list_order_returns(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.read")),
):
    order = db.get(Order, order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    returns = tenant_query(db, Return, user.tenant_id).filter(
        Return.order_id == order_id
    ).all()
    return [
        ReturnOut(
            id=r.id, tenant_id=r.tenant_id, order_id=r.order_id,
            order_item_id=r.order_item_id, variant_id=r.variant_id,
            quantity=r.quantity, reason=r.reason,
            refund_amount=r.refund_amount, status=r.status,
            note=r.note, created_by=r.created_by,
            created_at=r.created_at, processed_at=r.processed_at,
        )
        for r in returns
    ]


@router.get("/returns/all", response_model=list[ReturnOut])
def list_all_returns(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.return")),
):
    q = tenant_query(db, Return, user.tenant_id)
    if status:
        q = q.filter(Return.status == status)
    returns = q.order_by(Return.created_at.desc()).limit(100).all()
    return [
        ReturnOut(
            id=r.id, tenant_id=r.tenant_id, order_id=r.order_id,
            order_item_id=r.order_item_id, variant_id=r.variant_id,
            quantity=r.quantity, reason=r.reason,
            refund_amount=r.refund_amount, status=r.status,
            note=r.note, created_by=r.created_by,
            created_at=r.created_at, processed_at=r.processed_at,
        )
        for r in returns
    ]


@router.patch("/returns/{return_id}/approve", response_model=ReturnOut)
def approve_return(
    return_id: int,
    payload: ReturnAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.return")),
):
    ret = db.get(Return, return_id)
    if not ensure_tenant(ret, user.tenant_id):
        raise HTTPException(status_code=404, detail="Return not found")
    if ret.status != "pending":
        raise HTTPException(status_code=409, detail=f"Return is '{ret.status}', not 'pending'")

    svc = StockService(db, user.tenant_id)
    if ret.variant_id or ret.order_item_id:
        item = db.get(OrderItem, ret.order_item_id) if ret.order_item_id else None
        product_id = item.product_id if item else None
        svc.add(
            product_id=product_id, variant_id=ret.variant_id,
            quantity=ret.quantity, reason="order_returned",
            order_id=ret.order_id, actor_id=user.id,
        )

    ret.status = "completed"
    ret.processed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ret)
    return ReturnOut(
        id=ret.id, tenant_id=ret.tenant_id, order_id=ret.order_id,
        order_item_id=ret.order_item_id, variant_id=ret.variant_id,
        quantity=ret.quantity, reason=ret.reason,
        refund_amount=ret.refund_amount, status=ret.status,
        note=ret.note, created_by=ret.created_by,
        created_at=ret.created_at, processed_at=ret.processed_at,
    )


@router.patch("/returns/{return_id}/reject", response_model=ReturnOut)
def reject_return(
    return_id: int,
    payload: ReturnAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders.return")),
):
    ret = db.get(Return, return_id)
    if not ensure_tenant(ret, user.tenant_id):
        raise HTTPException(status_code=404, detail="Return not found")
    if ret.status != "pending":
        raise HTTPException(status_code=409, detail=f"Return is '{ret.status}', not 'pending'")

    ret.status = "rejected"
    ret.note = payload.note or ret.note
    ret.processed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ret)
    return ReturnOut(
        id=ret.id, tenant_id=ret.tenant_id, order_id=ret.order_id,
        order_item_id=ret.order_item_id, variant_id=ret.variant_id,
        quantity=ret.quantity, reason=ret.reason,
        refund_amount=ret.refund_amount, status=ret.status,
        note=ret.note, created_by=ret.created_by,
        created_at=ret.created_at, processed_at=ret.processed_at,
    )
