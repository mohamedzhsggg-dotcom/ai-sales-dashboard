"""Social Comments API.

Process and manage social media comments with deterministic post→product resolution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.database import get_db
from app.models import PostProductMapping, Product, SocialComment, User
from app.schemas import (
    PostProductMappingCreate,
    PostProductMappingListResponse,
    PostProductMappingOut,
    SocialCommentCreate,
    SocialCommentListResponse,
    SocialCommentOut,
)

router = APIRouter(tags=["social"])


def _resolve_product_for_post(
    db: Session, tenant_id: int, platform: str, post_id: str
) -> Optional[Product]:
    """Deterministically resolve a product from a social media post.

    Uses the post_product_mappings table, NOT AI guessing.
    """
    mapping = tenant_query(db, PostProductMapping, tenant_id).filter(
        PostProductMapping.platform == platform,
        PostProductMapping.post_id == post_id,
    ).first()
    if mapping and mapping.product_id:
        return db.get(Product, mapping.product_id)
    return None


# ---- Post Product Mappings ----
@router.get("/post-mappings", response_model=PostProductMappingListResponse)
def list_post_mappings(
    platform: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    q = tenant_query(db, PostProductMapping, user.tenant_id)
    if platform:
        q = q.filter(PostProductMapping.platform == platform)
    total = q.count()
    items = q.order_by(PostProductMapping.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return PostProductMappingListResponse(
        items=[PostProductMappingOut.model_validate(m) for m in items],
        total=total, page=page, limit=limit,
    )


@router.post("/post-mappings", response_model=PostProductMappingOut, status_code=201)
def create_post_mapping(
    payload: PostProductMappingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
):
    existing = tenant_query(db, PostProductMapping, user.tenant_id).filter(
        PostProductMapping.platform == payload.platform,
        PostProductMapping.post_id == payload.post_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Mapping already exists for this post")

    mapping = PostProductMapping(
        tenant_id=user.tenant_id,
        platform=payload.platform,
        post_id=payload.post_id,
        product_id=payload.product_id,
        product_name=payload.product_name,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return PostProductMappingOut.model_validate(mapping)


@router.delete("/post-mappings/{mapping_id}", status_code=204)
def delete_post_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
):
    mapping = db.get(PostProductMapping, mapping_id)
    if not ensure_tenant(mapping, user.tenant_id):
        raise HTTPException(status_code=404, detail="Mapping not found")
    db.delete(mapping)
    db.commit()


@router.get("/resolve-post")
def resolve_post_product(
    platform: str = Query(..., max_length=20),
    post_id: str = Query(..., max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.read")),
):
    product = _resolve_product_for_post(db, user.tenant_id, platform, post_id)
    if product:
        return {
            "resolved": True,
            "product_id": product.id,
            "product_name": product.name,
            "price": product.price,
            "stock": product.stock,
            "status": product.status,
        }
    return {"resolved": False, "product_id": None, "product_name": None}


# ---- Social Comments ----
@router.get("/comments", response_model=SocialCommentListResponse)
def list_comments(
    platform: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    replied: Optional[bool] = Query(None),
    post_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    q = tenant_query(db, SocialComment, user.tenant_id)
    if platform:
        q = q.filter(SocialComment.platform == platform)
    if resolved is not None:
        q = q.filter(SocialComment.resolved == resolved)
    if replied is not None:
        q = q.filter(SocialComment.replied == replied)
    if post_id:
        q = q.filter(SocialComment.post_id == post_id)
    total = q.count()
    items = q.order_by(SocialComment.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    result = []
    for c in items:
        out = SocialCommentOut.model_validate(c)
        if c.product_id:
            product = db.get(Product, c.product_id)
            out.product_name = product.name if product else None
        result.append(out)
    return SocialCommentListResponse(
        items=result, total=total, page=page, limit=limit,
    )


@router.post("/comments", response_model=SocialCommentOut, status_code=201)
def create_comment(
    payload: SocialCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    existing = db.query(SocialComment).filter(
        SocialComment.comment_id == payload.comment_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Comment already exists")

    product = _resolve_product_for_post(db, user.tenant_id, payload.platform, payload.post_id)

    comment = SocialComment(
        tenant_id=user.tenant_id,
        platform=payload.platform,
        post_id=payload.post_id,
        comment_id=payload.comment_id,
        external_user_id=payload.external_user_id,
        external_username=payload.external_username,
        comment_text=payload.comment_text,
        product_id=product.id if product else None,
        resolved=product is not None,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    out = SocialCommentOut.model_validate(comment)
    out.product_name = product.name if product else None
    return out


@router.patch("/comments/{comment_id}/reply", response_model=SocialCommentOut)
def reply_to_comment(
    comment_id: int,
    reply_text: str = Query(..., min_length=1, max_length=5000),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    comment = db.query(SocialComment).filter(SocialComment.id == comment_id).first()
    if not ensure_tenant(comment, user.tenant_id):
        raise HTTPException(status_code=404, detail="Comment not found")
    comment.replied = True
    comment.reply_text = reply_text
    comment.processed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)

    out = SocialCommentOut.model_validate(comment)
    if comment.product_id:
        product = db.get(Product, comment.product_id)
        out.product_name = product.name if product else None
    return out
