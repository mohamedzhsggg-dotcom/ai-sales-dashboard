"""Meta (Facebook/Instagram) integration service.

Handles webhook verification, event processing, and message/comment sending.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

META_GRAPH_URL = "https://graph.facebook.com/v18.0"


@dataclass
class MetaConfig:
    app_secret: str = ""
    verify_token: str = ""
    page_access_token: str = ""
    ig_account_id: str = ""

    @classmethod
    def from_env(cls) -> "MetaConfig":
        from app.config import get_settings
        settings = get_settings()
        return cls(
            app_secret=settings.META_APP_SECRET,
            verify_token=settings.META_VERIFY_TOKEN,
            page_access_token=settings.META_PAGE_ACCESS_TOKEN,
            ig_account_id=settings.META_IG_ACCOUNT_ID,
        )


def verify_webhook_signature(signature: str, payload: bytes, app_secret: str) -> bool:
    if not signature or not app_secret:
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def verify_webhook(mode: str, token: str, challenge: str, verify_token: str) -> Optional[str]:
    if mode == "subscribe" and token == verify_token:
        return challenge
    return None


def parse_webhook_event(body: dict) -> list[dict]:
    events = []
    for entry in body.get("entry", []):
        page_id = entry.get("id")
        for messaging in entry.get("messaging", []):
            events.append({
                "type": "message",
                "page_id": page_id,
                "sender_id": messaging.get("sender", {}).get("id"),
                "message_text": messaging.get("message", {}).get("text", ""),
                "message_id": messaging.get("message", {}).get("mid"),
            })
        for change in entry.get("changes", []):
            field = change.get("field")
            value = change.get("value", {})
            if field == "comments":
                events.append({
                    "type": "comment",
                    "page_id": page_id,
                    "post_id": value.get("post_id"),
                    "comment_id": value.get("comment_id"),
                    "text": value.get("text", ""),
                    "user_id": value.get("from", {}).get("id"),
                    "username": value.get("from", {}).get("name", ""),
                })
            elif field == "feed":
                events.append({
                    "type": "feed",
                    "page_id": page_id,
                    "post_id": value.get("post_id"),
                    "verb": value.get("verb"),
                    "text": value.get("message", ""),
                })
    return events


class MetaMessenger:
    def __init__(self, config: Optional[MetaConfig] = None):
        self.config = config or MetaConfig.from_env()

    def send_comment_reply(self, comment_id: str, message: str) -> bool:
        if not self.config.page_access_token:
            logger.warning("No page access token configured, cannot send comment reply")
            return False
        try:
            resp = httpx.post(
                f"{META_GRAPH_URL}/{comment_id}/comments",
                params={"access_token": self.config.page_access_token},
                json={"message": message},
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("Failed to send comment reply: %s", e)
            return False

    def send_private_message(self, recipient_id: str, message: str) -> bool:
        if not self.config.page_access_token:
            logger.warning("No page access token configured, cannot send DM")
            return False
        try:
            resp = httpx.post(
                f"{META_GRAPH_URL}/me/messages",
                params={"access_token": self.config.page_access_token},
                json={"recipient": {"id": recipient_id}, "message": {"text": message}},
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("Failed to send private message: %s", e)
            return False

    def send_text_message(self, recipient_id: str, message: str) -> bool:
        return self.send_private_message(recipient_id, message)
