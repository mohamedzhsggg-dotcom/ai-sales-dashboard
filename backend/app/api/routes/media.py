"""Product Media API.

Handles upload, list, update, and delete of product images/videos.
Uses LocalStorage by default; S3Storage available via config.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.database import get_db
from app.models import Product, ProductMedia, User
from app.schemas import ProductMediaOut, ProductMediaUpdate
from app.services.media import (
    ALLOWED_TYPES,
    MAX_FILE_SIZE,
    StorageError,
    get_storage,
)

router = APIRouter(prefix="/products/{product_id}/media", tags=["media"])


def _media_to_out(m: ProductMedia) -> ProductMediaOut:
    return ProductMediaOut(
        id=m.id,
        tenant_id=m.tenant_id,
        product_id=m.product_id,
        variant_id=m.variant_id,
        kind=m.kind,
        url=m.url,
        filename=m.filename,
        mime_type=m.mime_type,
        size_bytes=m.size_bytes,
        alt_text=m.alt_text,
        sort_order=m.sort_order,
        is_primary=m.is_primary,
        created_at=m.created_at,
    )


@router.get("", response_model=list[ProductMediaOut])
def list_media(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")
    items = tenant_query(db, ProductMedia, user.tenant_id).filter(
        ProductMedia.product_id == product_id
    ).order_by(ProductMedia.sort_order.asc(), ProductMedia.created_at.asc()).all()
    return [_media_to_out(m) for m in items]


@router.post("", response_model=ProductMediaOut, status_code=201)
async def upload_media(
    product_id: int,
    file: UploadFile = File(...),
    alt_text: Optional[str] = Form(None),
    variant_id: Optional[int] = Form(None),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("media.manage")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail=f"File type '{content_type}' not allowed. Use image/jpeg, image/png, image/webp, image/gif, or video/mp4.")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB.")

    kind = "video" if content_type.startswith("video/") else "image"
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    safe_filename = f"{uuid.uuid4().hex}.{ext}"

    storage = get_storage()
    try:
        import io
        url = storage.put(user.tenant_id, product_id, safe_filename, io.BytesIO(data), content_type)
    except StorageError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if is_primary:
        tenant_query(db, ProductMedia, user.tenant_id).filter(
            ProductMedia.product_id == product_id, ProductMedia.is_primary == True
        ).update({"is_primary": False})

    media = ProductMedia(
        tenant_id=user.tenant_id,
        product_id=product_id,
        variant_id=variant_id,
        kind=kind,
        url=url,
        filename=safe_filename,
        mime_type=content_type,
        size_bytes=len(data),
        alt_text=alt_text,
        sort_order=0,
        is_primary=is_primary,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return _media_to_out(media)


@router.patch("/{media_id}", response_model=ProductMediaOut)
def update_media(
    product_id: int,
    media_id: int,
    payload: ProductMediaUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("media.manage")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    media = db.get(ProductMedia, media_id)
    if not ensure_tenant(media, user.tenant_id) or media.product_id != product_id:
        raise HTTPException(status_code=404, detail="Media not found")

    update_data = payload.model_dump(exclude_unset=True)

    if update_data.get("is_primary"):
        tenant_query(db, ProductMedia, user.tenant_id).filter(
            ProductMedia.product_id == product_id,
            ProductMedia.is_primary == True,
            ProductMedia.id != media_id,
        ).update({"is_primary": False})

    for field, value in update_data.items():
        setattr(media, field, value)

    db.commit()
    db.refresh(media)
    return _media_to_out(media)


@router.delete("/{media_id}", status_code=204)
def delete_media(
    product_id: int,
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("media.manage")),
):
    product = db.get(Product, product_id)
    if not ensure_tenant(product, user.tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")

    media = db.get(ProductMedia, media_id)
    if not ensure_tenant(media, user.tenant_id) or media.product_id != product_id:
        raise HTTPException(status_code=404, detail="Media not found")

    storage = get_storage()
    try:
        storage.delete(user.tenant_id, product_id, media.filename)
    except Exception:
        pass

    db.delete(media)
    db.commit()
