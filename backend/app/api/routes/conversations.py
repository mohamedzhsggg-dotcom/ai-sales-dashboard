"""Conversations API.

Manage customer conversations and messages across platforms.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.context import ensure_tenant, tenant_query
from app.core.rbac import require_permission
from app.database import get_db
from app.models import Conversation, Customer, Message, User
from app.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationListResponse,
    ConversationOut,
    MessageCreate,
    MessageOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _conversation_to_out(c: Conversation) -> ConversationOut:
    return ConversationOut(
        id=c.id, tenant_id=c.tenant_id, customer_id=c.customer_id,
        platform=c.platform,
        external_conversation_id=c.external_conversation_id,
        external_user_id=c.external_user_id,
        subject=c.subject, status=c.status,
        last_message_at=c.last_message_at,
        created_at=c.created_at, updated_at=c.updated_at,
    )


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    status: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    q = tenant_query(db, Conversation, user.tenant_id)
    if status:
        q = q.filter(Conversation.status == status)
    if platform:
        q = q.filter(Conversation.platform == platform)
    if search:
        like = f"%{search}%"
        q = q.filter(Conversation.subject.ilike(like))
    total = q.count()
    items = q.order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return ConversationListResponse(
        items=[_conversation_to_out(c) for c in items],
        total=total, page=page, limit=limit,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    c = db.query(Conversation).options(
        joinedload(Conversation.messages),
        joinedload(Conversation.customer),
    ).filter(Conversation.id == conversation_id).first()
    if not ensure_tenant(c, user.tenant_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetail(
        **_conversation_to_out(c).model_dump(),
        messages=[
            MessageOut(
                id=m.id, tenant_id=m.tenant_id, conversation_id=m.conversation_id,
                direction=m.direction, content=m.content,
                platform_message_id=m.platform_message_id,
                external_user_id=m.external_user_id,
                extra_data=m.extra_data, created_at=m.created_at,
            )
            for m in sorted(c.messages, key=lambda x: x.created_at or datetime.min)
        ],
        customer_name=c.customer.name if c.customer else None,
        customer_phone=c.customer.phone if c.customer else None,
    )


@router.post("", response_model=ConversationDetail, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    conv = Conversation(
        tenant_id=user.tenant_id,
        platform=payload.platform,
        external_conversation_id=payload.external_conversation_id,
        external_user_id=payload.external_user_id,
        customer_id=payload.customer_id,
        subject=payload.subject,
        status="open",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationDetail(
        **_conversation_to_out(conv).model_dump(),
        messages=[],
    )


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=201)
def add_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    conv = db.get(Conversation, conversation_id)
    if not ensure_tenant(conv, user.tenant_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg = Message(
        tenant_id=user.tenant_id,
        conversation_id=conv.id,
        direction=payload.direction,
        content=payload.content,
        platform_message_id=payload.platform_message_id,
        external_user_id=payload.external_user_id,
        extra_data=payload.extra_data,
    )
    db.add(msg)

    conv.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    return MessageOut(
        id=msg.id, tenant_id=msg.tenant_id, conversation_id=msg.conversation_id,
        direction=msg.direction, content=msg.content,
        platform_message_id=msg.platform_message_id,
        external_user_id=msg.external_user_id,
        extra_data=msg.extra_data, created_at=msg.created_at,
    )


@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: int,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    conv = db.get(Conversation, conversation_id)
    if not ensure_tenant(conv, user.tenant_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    if status:
        conv.status = status
    db.commit()
    db.refresh(conv)
    return _conversation_to_out(conv)
