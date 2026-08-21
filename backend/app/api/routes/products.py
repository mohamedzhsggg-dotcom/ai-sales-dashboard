"""Products API.

Full CRUD for products (simple + variable), variant management,
category assignment, archive, and stock display.
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.database import get_db
from app.models import Category, Product, ProductVariant, User
from app.schemas import (
    ProductCreate,
    ProductDetail,
    ProductListResponse,
    ProductOut,
    ProductUpdate,
    ProductVariantOut,
    VariantCreate,
    VariantUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


def _variant_effective_price(variant: ProductVariant, product: Product) -> int | None:
    """Return variant's own price if set, else inherit from product."""
    if variant.price is not None:
        return variant.price
    return product.price


def _product_to_out(p: Product) -> ProductOut:
    variants = p.variants if hasattr(p, "variants") and p.variants else []
    active_variants = [v for v in variants if v.is_active]
    total_stock = (p.stock or 0) + sum(v.stock or 0 for v in active_variants)
    low_stock = total_stock > 0 and total_stock <= (p.low_stock_threshold or 5)
    return ProductOut(
        id=p.id,
        tenant_id=p.tenant_id,
        name=p.name,
        type=p.type or "simple",
        sku=p.sku,
        description=p.description,
        status=p.status or "active",
        category_id=p.category_id,
        price=p.price,
        sizes=p.sizes or [],
        colors=p.colors or [],
        image_url=p.image_url,
        stock=p.stock or 0,
        low_stock_threshold=p.low_stock_threshold or 5,
        is_dashboard_managed=p.is_dashboard_managed or False,
        fb_post_id=p.fb_post_id,
        ig_post_id=p.ig_post_id,
        variant_count=len(active_variants),
        total_stock=total_stock,
        low_stock=low_stock,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _variant_to_out(v: ProductVariant, product: Product) -> ProductVariantOut:
    return ProductVariantOut(
        id=v.id,
        tenant_id=v.tenant_id,
        product_id=v.product_id,
        sku=v.sku,
        options=v.options or {},
        price=v.price,
        stock=v.stock or 0,
        is_active=v.is_active,
        effective_price=_variant_effective_price(v, product),
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


@router.get("", response_model=ProductListResponse)
def list_products(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(active|archived)$"),
    category_id: Optional[int] = Query(None),
    type: Optional[str] = Query(None, pattern="^(simple|variable)$"),
    low_stock: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    q = tenant_query(db, Product, user.tenant_id)
    if status:
        q = q.filter(Product.status == status)
    else:
        q = q.filter(Product.status != "archived")
    if category_id is not None:
        q = q.filter(Product.category_id == category_id)
    if type:
        q = q.filter(Product.type == type)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Product.name.ilike(like), Product.sku.ilike(like)))
    total = q.count()
    items = q.options(joinedload(Product.variants)).order_by(Product.name.asc()).offset(
        (page - 1) * limit
    ).limit(limit).all()
    return ProductListResponse(
        items=[_product_to_out(p) for p in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
):
    if payload.sku:
        existing = tenant_query(db, Product, user.tenant_id).filter(Product.sku == payload.sku).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Product SKU '{payload.sku}' already exists")

    if payload.category_id is not None:
        cat = db.get(Category, payload.category_id)
        if not ensure_tenant(cat, user.tenant_id):
            raise HTTPException(status_code=404, detail="Category not found")

    product = Product(
        tenant_id=user.tenant_id,
        name=payload.name,
        type=payload.type,
        sku=payload.sku,
        description=payload.description,
        status=payload.status,
        category_id=payload.category_id,
        price=payload.price,
        sizes=payload.sizes,
        colors=payload.colors,
        image_url=payload.image_url,
        stock=payload.stock,
        low_stock_threshold=payload.low_stock_threshold,
        is_dashboard_managed=payload.is_dashboard_managed,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _product_to_out(product)


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    product = db.query(Product).options(joinedload(Product.variants)).filter(Product.id == product_id).first()
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    out = _product_to_out(product)
    return ProductDetail(
        **out.model_dump(),
        variants=[_variant_to_out(v, product) for v in product.variants],
    )


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "sku" in update_data and update_data["sku"] is not None:
        dup = tenant_query(db, Product, user.tenant_id).filter(
            Product.sku == update_data["sku"], Product.id != product_id
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Product SKU '{update_data['sku']}' already exists")

    if "category_id" in update_data and update_data["category_id"] is not None:
        cat = db.get(Category, update_data["category_id"])
        if not ensure_tenant(cat, user.tenant_id):
            raise HTTPException(status_code=404, detail="Category not found")

    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return _product_to_out(product)


@router.delete("/{product_id}", status_code=204)
def archive_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")
    product.status = "archived"
    db.commit()


# ── Variants ─────────────────────────────────────────────────────────────────


@router.get("/{product_id}/variants", response_model=list[ProductVariantOut])
def list_variants(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")
    variants = tenant_query(db, ProductVariant, user.tenant_id).filter(
        ProductVariant.product_id == product_id
    ).order_by(ProductVariant.id.asc()).all()
    return [_variant_to_out(v, product) for v in variants]


@router.post("/{product_id}/variants", response_model=ProductVariantOut, status_code=201)
def create_variant(
    product_id: int,
    payload: VariantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.sku:
        existing = tenant_query(db, ProductVariant, user.tenant_id).filter(
            ProductVariant.sku == payload.sku
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Variant SKU '{payload.sku}' already exists")

    variant = ProductVariant(
        tenant_id=user.tenant_id,
        product_id=product_id,
        sku=payload.sku,
        options=payload.options,
        price=payload.price,
        stock=payload.stock,
        is_active=payload.is_active,
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return _variant_to_out(variant, product)


@router.patch("/{product_id}/variants/{variant_id}", response_model=ProductVariantOut)
def update_variant(
    product_id: int,
    variant_id: int,
    payload: VariantUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    variant = db.get(ProductVariant, variant_id)
    if not ensure_tenant(variant, user.tenant_id) or variant.product_id != product_id:
        raise HTTPException(status_code=404, detail="Variant not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "sku" in update_data and update_data["sku"] is not None:
        dup = tenant_query(db, ProductVariant, user.tenant_id).filter(
            ProductVariant.sku == update_data["sku"], ProductVariant.id != variant_id
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Variant SKU '{update_data['sku']}' already exists")

    for field, value in update_data.items():
        setattr(variant, field, value)

    db.commit()
    db.refresh(variant)
    return _variant_to_out(variant, product)


@router.delete("/{product_id}/variants/{variant_id}", status_code=204)
def delete_variant(
    product_id: int,
    variant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    variant = db.get(ProductVariant, variant_id)
    if not ensure_tenant(variant, user.tenant_id) or variant.product_id != product_id:
        raise HTTPException(status_code=404, detail="Variant not found")

    db.delete(variant)
    db.commit()


@router.get("/{product_id}/variants/options")
def get_variant_options(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    variants = tenant_query(db, ProductVariant, user.tenant_id).filter(
        ProductVariant.product_id == product_id, ProductVariant.is_active == True
    ).all()

    options: dict[str, set] = {}
    for v in variants:
        for key, val in (v.options or {}).items():
            options.setdefault(key, set()).add(str(val))

    return {k: sorted(v) for k, v in options.items()}
