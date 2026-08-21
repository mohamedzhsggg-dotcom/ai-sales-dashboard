"""Social comment automation service.

Handles the full workflow:
Comment → Post resolution → Product lookup → AI response → Reply → Conversation
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.context import tenant_query
from app.models import (
    Conversation,
    Customer,
    Message,
    PostProductMapping,
    Product,
    SocialComment,
)
from app.services.ai.assistant import AIAssistant
from app.services.meta.client import MetaMessenger

logger = logging.getLogger(__name__)


class SocialAutomation:
    def __init__(self, db: Session, messenger: Optional[MetaMessenger] = None):
        self.db = db
        self.messenger = messenger or MetaMessenger()
        self.ai = AIAssistant(db)

    def _resolve_product(self, tenant_id: int, platform: str, post_id: str) -> Optional[Product]:
        mapping = tenant_query(self.db, PostProductMapping, tenant_id).filter(
            PostProductMapping.platform == platform,
            PostProductMapping.post_id == post_id,
        ).first()
        if mapping and mapping.product_id:
            return self.db.get(Product, mapping.product_id)
        return None

    def _find_or_create_customer(
        self, tenant_id: int, platform: str, user_id: str, username: str
    ) -> Customer:
        customer = tenant_query(self.db, Customer, tenant_id).filter(
            Customer.platform == platform,
            Customer.external_id == user_id,
        ).first()
        if not customer:
            customer = Customer(
                tenant_id=tenant_id,
                platform=platform,
                external_id=user_id,
                name=username,
            )
            self.db.add(customer)
            self.db.flush()
        return customer

    def _find_or_create_conversation(
        self, tenant_id: int, customer_id: int, platform: str, post_id: Optional[str] = None
    ) -> Conversation:
        conv = tenant_query(self.db, Conversation, tenant_id).filter(
            Conversation.customer_id == customer_id,
            Conversation.platform == platform,
            Conversation.status == "open",
        ).first()
        if not conv:
            conv = Conversation(
                tenant_id=tenant_id,
                customer_id=customer_id,
                platform=platform,
                subject=f"Comment on post {post_id}" if post_id else None,
                status="open",
            )
            self.db.add(conv)
            self.db.flush()
        return conv

    def process_comment(
        self,
        tenant_id: int,
        platform: str,
        post_id: str,
        comment_id: str,
        user_id: str,
        username: str,
        text: str,
    ) -> dict:
        existing = self.db.query(SocialComment).filter(
            SocialComment.comment_id == comment_id,
        ).first()
        if existing:
            return {"status": "duplicate", "comment_id": comment_id}

        product = self._resolve_product(tenant_id, platform, post_id)
        customer = self._find_or_create_customer(tenant_id, platform, user_id, username)
        conversation = self._find_or_create_conversation(tenant_id, customer.id, platform, post_id)

        comment = SocialComment(
            tenant_id=tenant_id,
            platform=platform,
            post_id=post_id,
            comment_id=comment_id,
            external_user_id=user_id,
            external_username=username,
            comment_text=text,
            product_id=product.id if product else None,
            resolved=product is not None,
        )
        self.db.add(comment)

        msg = Message(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            direction="inbound",
            content=text,
            platform_message_id=comment_id,
            external_user_id=user_id,
        )
        self.db.add(msg)

        ai_response = self.ai.process_message(
            tenant_id=tenant_id,
            content=text,
            conversation_id=conversation.id,
            customer_id=customer.id,
            platform=platform,
        )

        if ai_response.text:
            reply_msg = Message(
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                direction="outbound",
                content=ai_response.text,
                external_user_id=user_id,
            )
            self.db.add(reply_msg)
            conversation.last_message_at = datetime.now(timezone.utc)
            comment.replied = True
            comment.reply_text = ai_response.text

            if platform == "facebook":
                self.messenger.send_comment_reply(comment_id, ai_response.text)
            elif platform == "instagram":
                self.messenger.send_comment_reply(comment_id, ai_response.text)

        comment.processed_at = datetime.now(timezone.utc)
        self.db.commit()

        return {
            "status": "processed",
            "comment_id": comment_id,
            "product_id": product.id if product else None,
            "conversation_id": conversation.id,
            "ai_action": ai_response.action,
            "ai_confidence": ai_response.confidence,
        }

    def process_dm(
        self,
        tenant_id: int,
        platform: str,
        sender_id: str,
        message_text: str,
        message_id: Optional[str] = None,
    ) -> dict:
        customer = tenant_query(self.db, Customer, tenant_id).filter(
            Customer.platform == platform,
            Customer.external_id == sender_id,
        ).first()
        if not customer:
            customer = Customer(
                tenant_id=tenant_id,
                platform=platform,
                external_id=sender_id,
            )
            self.db.add(customer)
            self.db.flush()

        conversation = self._find_or_create_conversation(tenant_id, customer.id, platform)

        msg = Message(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            direction="inbound",
            content=message_text,
            platform_message_id=message_id,
            external_user_id=sender_id,
        )
        self.db.add(msg)

        ai_response = self.ai.process_message(
            tenant_id=tenant_id,
            content=message_text,
            conversation_id=conversation.id,
            customer_id=customer.id,
            platform=platform,
        )

        if ai_response.text:
            reply_msg = Message(
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                direction="outbound",
                content=ai_response.text,
                external_user_id=sender_id,
            )
            self.db.add(reply_msg)
            conversation.last_message_at = datetime.now(timezone.utc)
            self.messenger.send_private_message(sender_id, ai_response.text)

        self.db.commit()

        return {
            "status": "processed",
            "conversation_id": conversation.id,
            "ai_action": ai_response.action,
            "ai_confidence": ai_response.confidence,
        }
