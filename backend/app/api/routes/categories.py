"""Categories API.

Provides CRUD for product categories, plus a tree view. All endpoints are
tenant-scoped. Deletion is soft (sets is_active=false); a category with
children or products cannot be deactivated until they are moved or removed.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.database import get_db
from app.models import Category, Product, User
from app.schemas import (
    CategoryIn,
    CategoryListResponse,
    CategoryNode,
    CategoryOut,
    CategoryUpdate,
)

router = APIRouter(prefix="/categories", tags=["categories"])


def _to_out(cat: Category, product_count: int = 0) -> CategoryOut:
    return CategoryOut(
        id=cat.id,
        tenant_id=cat.tenant_id,
        name=cat.name,
        slug=cat.slug,
        parent_id=cat.parent_id,
        sort_order=cat.sort_order,
        is_active=cat.is_active,
        product_count=product_count,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
    )


def _build_tree(cats: list[Category]) -> list[CategoryNode]:
    by_parent: dict[Optional[int], list[Category]] = defaultdict(list)
    for c in cats:
        by_parent[c.parent_id].append(c)
    for siblings in by_parent.values():
        siblings.sort(key=lambda x: (x.sort_order, x.name))

    def _node(cat: Category) -> CategoryNode:
        return CategoryNode(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            parent_id=cat.parent_id,
            sort_order=cat.sort_order,
            is_active=cat.is_active,
            children=[_node(child) for child in by_parent.get(cat.id, [])],
        )

    return [_node(c) for c in by_parent.get(None, [])]


@router.get("/tree", response_model=list[CategoryNode])
def get_category_tree(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    cats = tenant_query(db, Category, user.tenant_id).all()
    return _build_tree(cats)


@router.get("", response_model=CategoryListResponse)
def list_categories(
    parent_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    q = tenant_query(db, Category, user.tenant_id)
    if active_only:
        q = q.filter(Category.is_active == True)  # noqa: E712
    if parent_id is not None:
        q = q.filter(Category.parent_id == parent_id)
    if search:
        like = f"%{search}%"
        q = q.filter(Category.name.ilike(like))
    total = q.count()
    cats = q.order_by(Category.sort_order.asc(), Category.name.asc()).offset(
        (page - 1) * limit
    ).limit(limit).all()

    # Product counts for the returned categories.
    cat_ids = [c.id for c in cats]
    counts = dict(
        db.query(Product.category_id, func.count(Product.id))
        .filter(Product.tenant_id == user.tenant_id, Product.category_id.in_(cat_ids))
        .group_by(Product.category_id)
        .all()
    ) if cat_ids else {}

    return CategoryListResponse(
        items=[_to_out(c, counts.get(c.id, 0)) for c in cats],
        total=total,
    )


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("categories.manage")),
):
    slug = payload.slug or re.sub(r"[^a-z0-9]+", "-", payload.name.strip().lower()).strip("-")
    if not slug:
        raise HTTPException(status_code=422, detail="Slug cannot be empty")

    existing = tenant_query(db, Category, user.tenant_id).filter(Category.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Category slug '{slug}' already exists")

    if payload.parent_id is not None:
        parent = db.get(Category, payload.parent_id)
        if not ensure_tenant(parent, user.tenant_id):
            raise HTTPException(status_code=404, detail="Parent category not found")
        if parent and not parent.is_active:
            raise HTTPException(status_code=422, detail="Cannot add to inactive parent category")

    cat = Category(
        tenant_id=user.tenant_id,
        name=payload.name,
        slug=slug,
        parent_id=payload.parent_id,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _to_out(cat)


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    cat = db.get(Category, category_id)
    if not ensure_tenant(cat, user.tenant_id):
        raise HTTPException(status_code=404, detail="Category not found")

    product_count = (
        tenant_query(db, Product, user.tenant_id)
        .filter(Product.category_id == category_id)
        .count()
    )
    return _to_out(cat, product_count)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("categories.manage")),
):
    cat = db.get(Category, category_id)
    if not ensure_tenant(cat, user.tenant_id):
        raise HTTPException(status_code=404, detail="Category not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "name" in update_data:
        cat.name = update_data["name"]
    if "parent_id" in update_data:
        new_parent_id = update_data["parent_id"]
        if new_parent_id == category_id:
            raise HTTPException(status_code=422, detail="Category cannot be its own parent")
        if new_parent_id is not None:
            parent = db.get(Category, new_parent_id)
            if not ensure_tenant(parent, user.tenant_id):
                raise HTTPException(status_code=404, detail="Parent category not found")
            if parent and not parent.is_active:
                raise HTTPException(status_code=422, detail="Cannot assign inactive parent category")
        cat.parent_id = new_parent_id
    if "slug" in update_data:
        new_slug = update_data["slug"]
        dup = tenant_query(db, Category, user.tenant_id).filter(
            Category.slug == new_slug, Category.id != category_id
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Category slug '{new_slug}' already exists")
        cat.slug = new_slug
    if "sort_order" in update_data:
        cat.sort_order = update_data["sort_order"]
    if "is_active" in update_data:
        cat.is_active = update_data["is_active"]

    db.commit()
    db.refresh(cat)
    product_count = (
        tenant_query(db, Product, user.tenant_id)
        .filter(Product.category_id == category_id)
        .count()
    )
    return _to_out(cat, product_count)


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("categories.manage")),
):
    cat = db.get(Category, category_id)
    if not ensure_tenant(cat, user.tenant_id):
        raise HTTPException(status_code=404, detail="Category not found")

    if cat.slug == "uncategorized":
        raise HTTPException(status_code=403, detail="Cannot deactivate the Uncategorized category")

    children = tenant_query(db, Category, user.tenant_id).filter(
        Category.parent_id == category_id, Category.is_active == True  # noqa: E712
    ).count()
    if children > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot deactivate: {children} active subcategories still reference this category",
        )

    product_count = (
        tenant_query(db, Product, user.tenant_id)
        .filter(Product.category_id == category_id)
        .count()
    )
    if product_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot deactivate: {product_count} products still reference this category",
        )

    cat.is_active = False
    db.commit()
