"""Inventory API.

Stock adjustment, movement ledger, summary, stock counts, and reconciliation.
All mutations are transactional and go through StockService.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.database import get_db
from app.models import InventoryEvent, Product, ProductVariant, StockCount, User
from app.schemas import (
    InventoryItem,
    InventorySummary,
    StockAdjust,
    StockCountCreate,
    StockCountOut,
    StockCountReconcile,
    StockMovementOut,
    ProductOut,
)
from app.services.stock import StockService, InsufficientStock, StockError

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryItem])
def list_inventory(
    low_stock: Optional[bool] = None,
    out_of_stock: Optional[bool] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.read")),
):
    q = tenant_query(db, Product, user.tenant_id).filter(Product.status == "active")
    if category_id is not None:
        q = q.filter(Product.category_id == category_id)
    products = q.order_by(Product.stock.asc()).all()
    items = []
    for p in products:
        threshold = p.low_stock_threshold or 5
        total = p.stock or 0
        low = 0 < total <= threshold
        if low_stock and not low:
            continue
        if out_of_stock and total != 0:
            continue
        item = InventoryItem.model_validate(p)
        item.low_stock = low
        items.append(item)
    return items


@router.get("/movements", response_model=list[StockMovementOut])
def list_movements(
    product_id: Optional[int] = Query(None),
    reason: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.read")),
):
    q = tenant_query(db, InventoryEvent, user.tenant_id)
    if product_id is not None:
        q = q.filter(InventoryEvent.product_id == product_id)
    if reason:
        q = q.filter(InventoryEvent.reason == reason)
    events = q.order_by(InventoryEvent.created_at.desc()).offset(
        (page - 1) * limit
    ).limit(limit).all()
    return [
        StockMovementOut(
            id=e.id, tenant_id=e.tenant_id, product_id=e.product_id,
            product_variant_id=e.product_variant_id, delta=e.delta,
            reason=e.reason, order_id=e.order_id, actor=e.actor,
            reference=e.reference, data=e.data, qty_after=e.qty_after,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/summary", response_model=InventorySummary)
def inventory_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.read")),
):
    products = tenant_query(db, Product, user.tenant_id).filter(Product.status == "active").all()
    total_stock = sum(p.stock or 0 for p in products)
    return InventorySummary(
        total_products=len(products),
        total_stock=total_stock,
        low_stock_count=sum(1 for p in products if 0 < (p.stock or 0) <= (p.low_stock_threshold or 5)),
        out_of_stock_count=sum(1 for p in products if (p.stock or 0) == 0),
    )


@router.patch("/{product_id}/stock", response_model=ProductOut)
def set_stock(
    product_id: int,
    payload: StockAdjust,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.adjust")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    svc = StockService(db, user.tenant_id)
    try:
        if payload.reason == "set":
            new_stock = svc.set_manual(
                product_id=product.id, new_stock=payload.quantity,
                reason="manual", actor_id=user.id,
            )
        elif payload.quantity > 0:
            new_stock = svc.add(
                product_id=product.id, quantity=payload.quantity,
                reason=payload.reason or "adjustment", actor_id=user.id,
            )
        else:
            new_stock = svc.deduct(
                product_id=product.id, quantity=abs(payload.quantity),
                reason=payload.reason or "adjustment", actor_id=user.id,
            )
    except InsufficientStock as e:
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient stock: available {e.available}, requested {e.requested}",
        )
    except StockError as e:
        raise HTTPException(status_code=422, detail=str(e))
    db.commit()
    db.refresh(product)
    from app.schemas import ProductOut as PO
    return PO(
        id=product.id, tenant_id=product.tenant_id, name=product.name,
        type=product.type or "simple", sku=product.sku, description=product.description,
        status=product.status or "active", category_id=product.category_id,
        price=product.price, sizes=product.sizes or [], colors=product.colors or [],
        image_url=product.image_url, stock=product.stock or 0,
        low_stock_threshold=product.low_stock_threshold or 5,
        is_dashboard_managed=product.is_dashboard_managed or False,
        fb_post_id=product.fb_post_id, ig_post_id=product.ig_post_id,
        variant_count=0, total_stock=product.stock or 0,
        low_stock=0 < (product.stock or 0) <= (product.low_stock_threshold or 5),
        created_at=product.created_at, updated_at=product.updated_at,
    )


# ── Stock Counts ─────────────────────────────────────────────────────────────


@router.post("/stock-counts", response_model=StockCountOut, status_code=201)
def create_stock_count(
    payload: StockCountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.adjust")),
):
    if payload.variant_id:
        variant = db.get(ProductVariant, payload.variant_id)
        if not ensure_tenant(variant, user.tenant_id):
            raise HTTPException(status_code=404, detail="Variant not found")
        expected = variant.stock or 0
    else:
        product = db.get(Product, payload.product_id)
        if not ensure_tenant(product, user.tenant_id):
            raise HTTPException(status_code=404, detail="Product not found")
        expected = product.stock or 0

    sc = StockCount(
        tenant_id=user.tenant_id,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        expected_quantity=expected,
        counted_quantity=payload.counted_quantity,
        delta=(payload.counted_quantity - expected) if payload.counted_quantity is not None else None,
        counted_by=user.id,
        note=payload.note,
    )
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return StockCountOut(
        id=sc.id, tenant_id=sc.tenant_id, product_id=sc.product_id,
        variant_id=sc.variant_id, expected_quantity=sc.expected_quantity,
        counted_quantity=sc.counted_quantity, delta=sc.delta,
        counted_by=sc.counted_by, counted_at=sc.counted_at,
        note=sc.note, reconciled=sc.reconciled, created_at=sc.created_at,
    )


@router.post("/stock-counts/{count_id}/reconcile", response_model=StockCountOut)
def reconcile_stock_count(
    count_id: int,
    payload: StockCountReconcile,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory.adjust")),
):
    sc = db.get(StockCount, count_id)
    if not ensure_tenant(sc, user.tenant_id):
        raise HTTPException(status_code=404, detail="Stock count not found")
    if sc.reconciled:
        raise HTTPException(status_code=409, detail="Already reconciled")

    svc = StockService(db, user.tenant_id)
    delta = (sc.counted_quantity or 0) - sc.expected_quantity
    if delta != 0:
        if delta > 0:
            svc.add(
                product_id=sc.product_id, variant_id=sc.variant_id,
                quantity=abs(delta), reason="stock_take", actor_id=user.id,
            )
        else:
            svc.deduct(
                product_id=sc.product_id, variant_id=sc.variant_id,
                quantity=abs(delta), reason="stock_take", actor_id=user.id,
            )

    sc.reconciled = True
    sc.counted_at = sc.counted_at or __import__("datetime").datetime.utcnow()
    db.commit()
    db.refresh(sc)
    return StockCountOut(
        id=sc.id, tenant_id=sc.tenant_id, product_id=sc.product_id,
        variant_id=sc.variant_id, expected_quantity=sc.expected_quantity,
        counted_quantity=sc.counted_quantity, delta=sc.delta,
        counted_by=sc.counted_by, counted_at=sc.counted_at,
        note=sc.note, reconciled=sc.reconciled, created_at=sc.created_at,
    )
