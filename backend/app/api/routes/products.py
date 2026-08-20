from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import Product, User
from app.schemas import ProductListResponse, ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Product).filter(Product.tenant_id == user.tenant_id)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Product.name.ilike(like), Product.fb_post_id.ilike(like), Product.ig_post_id.ilike(like)))
    total = q.count()
    items = q.order_by(Product.name.asc()).offset((page - 1) * limit).limit(limit).all()
    return ProductListResponse(
        items=[ProductOut.model_validate(p) for p in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = db.get(Product, product_id)
    if not product or product.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.model_validate(product)