"""Shipments API.

Create, track, and manage courier shipments for orders.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.database import get_db
from app.models import Order, Shipment, ShipmentTracking, User
from app.schemas import (
    ShipmentCreate,
    ShipmentDetail,
    ShipmentListResponse,
    ShipmentOut,
)
from app.services.couriers.base import ShipmentRequest
from app.services.couriers.registry import get_provider

router = APIRouter(prefix="/shipments", tags=["shipments"])


def _shipment_to_out(s: Shipment) -> ShipmentOut:
    return ShipmentOut(
        id=s.id, tenant_id=s.tenant_id, order_id=s.order_id,
        courier_name=s.courier_name, tracking_number=s.tracking_number,
        status=s.status, cod_amount=s.cod_amount or 0,
        shipping_fee=s.shipping_fee or 0,
        delivery_method=s.delivery_method,
        notes=s.notes,
        created_at=s.created_at, updated_at=s.updated_at,
        shipped_at=s.shipped_at, delivered_at=s.delivered_at,
    )


@router.get("", response_model=ShipmentListResponse)
def list_shipments(
    status: Optional[str] = Query(None),
    courier_name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("shipments.read")),
):
    q = tenant_query(db, Shipment, user.tenant_id)
    if status:
        q = q.filter(Shipment.status == status)
    if courier_name:
        q = q.filter(Shipment.courier_name == courier_name)
    total = q.count()
    items = q.order_by(Shipment.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return ShipmentListResponse(
        items=[_shipment_to_out(s) for s in items],
        total=total, page=page, limit=limit,
    )


@router.get("/{shipment_id}", response_model=ShipmentDetail)
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("shipments.read")),
):
    s = db.query(Shipment).options(
        joinedload(Shipment.tracking_events)
    ).filter(Shipment.id == shipment_id).first()
    if not ensure_tenant(s, user.tenant_id):
        raise HTTPException(status_code=404, detail="Shipment not found")
    return ShipmentDetail(
        **_shipment_to_out(s).model_dump(),
        tracking_events=[
            {
                "id": ev.id, "status": ev.status,
                "description": ev.description,
                "location": ev.location,
                "courier_raw_status": ev.courier_raw_status,
                "recorded_at": ev.recorded_at,
            }
            for ev in s.tracking_events
        ],
    )


@router.post("", response_model=ShipmentDetail, status_code=201)
def create_shipment(
    payload: ShipmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
):
    order = db.get(Order, payload.order_id)
    if not ensure_tenant(order, user.tenant_id):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("new", "confirmed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot create shipment for order in '{order.status}' status",
        )

    existing = tenant_query(db, Shipment, user.tenant_id).filter(
        Shipment.order_id == order.id,
        Shipment.status.notin_(["cancelled", "returned"]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Order already has an active shipment (#{existing.id})",
        )

    settings = get_settings()
    if not settings.SHIPMENTS_ENABLED:
        raise HTTPException(status_code=503, detail="Shipments feature is disabled")

    courier = payload.courier_name or "yalidine"
    provider = get_provider(courier)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Unknown courier: {courier}")

    items_desc = ", ".join(
        f"{it.product_name} x{it.quantity}" for it in (order.items or [])
    ) or order.product or ""

    req = ShipmentRequest(
        order_id=order.id,
        tenant_id=user.tenant_id,
        phone=order.phone or "",
        name=order.name or "",
        wilaya=order.wilaya or "",
        commune=order.commune,
        product_description=items_desc,
        cod_amount=order.total or 0,
        shipping_fee=order.shipping_fee or 0,
        delivery_method=payload.delivery_method or order.delivery_method or "home",
        notes=payload.notes,
        items=[
            {"product_name": it.product_name, "quantity": it.quantity, "unit_price": it.unit_price}
            for it in (order.items or [])
        ],
    )

    result = provider.create_shipment(req)
    if not result.success:
        raise HTTPException(status_code=502, detail=f"Courier error: {result.error}")

    shipment = Shipment(
        tenant_id=user.tenant_id,
        order_id=order.id,
        courier_name=courier,
        tracking_number=result.tracking_number,
        status=result.status,
        cod_amount=order.total or 0,
        shipping_fee=order.shipping_fee or 0,
        delivery_method=req.delivery_method,
        notes=req.notes,
        raw_response=result.raw,
    )
    db.add(shipment)
    db.flush()

    if result.tracking_number:
        order.tracking_number = result.tracking_number
        order.courier_name = courier

    db.commit()
    db.refresh(shipment)

    return ShipmentDetail(
        **_shipment_to_out(shipment).model_dump(),
        tracking_events=[],
    )


@router.post("/{shipment_id}/refresh", response_model=ShipmentDetail)
def refresh_tracking(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
):
    shipment = db.query(Shipment).options(
        joinedload(Shipment.tracking_events)
    ).filter(Shipment.id == shipment_id).first()
    if not ensure_tenant(shipment, user.tenant_id):
        raise HTTPException(status_code=404, detail="Shipment not found")
    if not shipment.tracking_number:
        raise HTTPException(status_code=409, detail="No tracking number available")

    provider = get_provider(shipment.courier_name)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Unknown courier: {shipment.courier_name}")

    result = provider.track_shipment(shipment.tracking_number)
    if not result.success:
        raise HTTPException(status_code=502, detail=f"Courier error: {result.error}")

    from datetime import datetime, timezone

    if result.status != shipment.status:
        event = ShipmentTracking(
            tenant_id=user.tenant_id,
            shipment_id=shipment.id,
            status=result.status,
            description=f"Status updated to {result.status}",
            courier_raw_status=result.status,
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(event)

        shipment.status = result.status
        if result.status == "shipped":
            shipment.shipped_at = datetime.now(timezone.utc)
        elif result.status == "delivered":
            shipment.delivered_at = datetime.now(timezone.utc)

        if shipment.order:
            shipment.order.status = result.status

    db.commit()
    db.refresh(shipment)

    return ShipmentDetail(
        **_shipment_to_out(shipment).model_dump(),
        tracking_events=[
            {
                "id": ev.id, "status": ev.status,
                "description": ev.description,
                "location": ev.location,
                "courier_raw_status": ev.courier_raw_status,
                "recorded_at": ev.recorded_at,
            }
            for ev in shipment.tracking_events
        ],
    )


@router.delete("/{shipment_id}", status_code=204)
def cancel_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not ensure_tenant(shipment, user.tenant_id):
        raise HTTPException(status_code=404, detail="Shipment not found")
    if shipment.status in ("delivered", "cancelled", "returned"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel shipment in '{shipment.status}' status",
        )

    provider = get_provider(shipment.courier_name)
    if provider and shipment.tracking_number:
        provider.cancel_shipment(shipment.tracking_number)

    shipment.status = "cancelled"
    db.commit()
