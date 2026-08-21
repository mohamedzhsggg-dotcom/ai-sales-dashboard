"""AI Assistant API.

Provides endpoints for AI-powered sales assistance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.rbac import require_permission
from app.database import get_db
from app.models import User
from app.services.ai.assistant import AIAssistant

router = APIRouter(prefix="/ai", tags=["ai"])


class AIProcessRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    conversation_id: int | None = None
    customer_id: int | None = None
    platform: str | None = None


class AIProcessResponse(BaseModel):
    text: str
    action: str | None = None
    action_data: dict | None = None
    confidence: float = 0.0


@router.post("/process", response_model=AIProcessResponse)
def process_message(
    payload: AIProcessRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    assistant = AIAssistant(db)
    result = assistant.process_message(
        tenant_id=user.tenant_id,
        content=payload.content,
        conversation_id=payload.conversation_id,
        customer_id=payload.customer_id,
        platform=payload.platform,
    )
    return AIProcessResponse(
        text=result.text,
        action=result.action,
        action_data=result.action_data,
        confidence=result.confidence,
    )
