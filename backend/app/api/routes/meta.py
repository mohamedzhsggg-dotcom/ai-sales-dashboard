"""Meta webhook endpoints for Facebook and Instagram.

Handles webhook verification, comment ingestion, DM processing,
and provides API for sending replies.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.rbac import require_permission
from app.database import get_db
from app.models import User
from app.services.meta.client import MetaConfig, MetaMessenger, parse_webhook_event, verify_webhook, verify_webhook_signature
from app.services.automation.social import SocialAutomation

logger = logging.getLogger(__name__)

router = APIRouter(tags=["meta"])


class WebhookPayload(BaseModel):
    object: Optional[str] = None
    entry: list[dict] = []


class SendReplyRequest(BaseModel):
    recipient_id: str
    message: str
    platform: str = "facebook"


@router.get("/webhooks/meta")
async def meta_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    config = MetaConfig.from_env()
    challenge = verify_webhook(hub_mode, hub_token, hub_challenge, config.verify_token)
    if challenge:
        return {"challenge": challenge}
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/meta")
async def meta_webhook_handler(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    config = MetaConfig.from_env()
    if config.app_secret and not verify_webhook_signature(signature, body, config.app_secret):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = WebhookPayload.model_validate_json(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    automation = SocialAutomation(db, MetaMessenger(config))
    results = []

    for entry in payload.entry:
        page_id = entry.get("id")
        tenant_id = _resolve_tenant_for_page(db, page_id)
        if not tenant_id:
            logger.warning("No tenant found for page %s", page_id)
            continue

        events = parse_webhook_event({"entry": [entry]})
        for event in events:
            if event["type"] == "comment":
                result = automation.process_comment(
                    tenant_id=tenant_id,
                    platform="facebook",
                    post_id=event.get("post_id", ""),
                    comment_id=event.get("comment_id", ""),
                    user_id=event.get("user_id", ""),
                    username=event.get("username", ""),
                    text=event.get("text", ""),
                )
                results.append(result)
            elif event["type"] == "message":
                result = automation.process_dm(
                    tenant_id=tenant_id,
                    platform="facebook",
                    sender_id=event.get("sender_id", ""),
                    message_text=event.get("message_text", ""),
                    message_id=event.get("message_id"),
                )
                results.append(result)

    return {"status": "ok", "processed": len(results)}


@router.post("/meta/reply")
def send_reply(
    payload: SendReplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("customers.read")),
):
    config = MetaConfig.from_env()
    messenger = MetaMessenger(config)
    if payload.platform == "facebook":
        success = messenger.send_private_message(payload.recipient_id, payload.message)
    else:
        success = messenger.send_private_message(payload.recipient_id, payload.message)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send message")
    return {"status": "sent"}


def _resolve_tenant_for_page(db: Session, page_id: Optional[str]) -> Optional[int]:
    if not page_id:
        return None
    from app.models import Tenant
    tenant = db.query(Tenant).filter(
        Tenant.config["meta_pages"].astext.contains(page_id)
    ).first()
    if tenant:
        return tenant.id
    tenant = db.query(Tenant).first()
    return tenant.id if tenant else None
