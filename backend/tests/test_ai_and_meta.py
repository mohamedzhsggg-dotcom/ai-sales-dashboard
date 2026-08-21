"""Tests for AI Sales Assistant, Meta webhooks, and social comment automation."""

import json
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.services.ai.assistant import (
    AIAssistant, AIContext, AIResponse, MockAIProvider, OpenAIProvider, get_ai_provider
)
from app.services.meta.client import (
    MetaConfig, MetaMessenger, verify_webhook, verify_webhook_signature, parse_webhook_event
)


class TestMockAIProvider:
    def test_price_query(self):
        provider = MockAIProvider()
        ctx = AIContext(tenant_id=1)
        result = provider.chat([{"role": "user", "content": "What is the price?"}], ctx)
        parsed = json.loads(result)
        assert parsed["action"] == "lookup_product"

    def test_order_intent(self):
        provider = MockAIProvider()
        ctx = AIContext(tenant_id=1)
        result = provider.chat([{"role": "user", "content": "I want to order this"}], ctx)
        parsed = json.loads(result)
        assert parsed["action"] == "collect_order_info"

    def test_stock_query(self):
        provider = MockAIProvider()
        ctx = AIContext(tenant_id=1)
        result = provider.chat([{"role": "user", "content": "Is this in stock?"}], ctx)
        parsed = json.loads(result)
        assert parsed["action"] == "check_stock"

    def test_general_reply(self):
        provider = MockAIProvider()
        ctx = AIContext(tenant_id=1)
        result = provider.chat([{"role": "user", "content": "Hello there"}], ctx)
        parsed = json.loads(result)
        assert parsed["action"] == "reply"

    def test_french_price(self):
        provider = MockAIProvider()
        ctx = AIContext(tenant_id=1)
        result = provider.chat([{"role": "user", "content": "C'est le prix?"}], ctx)
        parsed = json.loads(result)
        assert parsed["action"] == "lookup_product"

    def test_arabic_order(self):
        provider = MockAIProvider()
        ctx = AIContext(tenant_id=1)
        result = provider.chat([{"role": "user", "content": "أريد أن أطلب هذا المنتج"}], ctx)
        parsed = json.loads(result)
        assert parsed["action"] == "collect_order_info"


class TestAIAssistant:
    def test_process_message(self, db: Session):
        assistant = AIAssistant(db, provider=MockAIProvider())
        result = assistant.process_message(
            tenant_id=1,
            content="What is the price of the jacket?",
            platform="facebook",
        )
        assert isinstance(result, AIResponse)
        assert result.action is not None
        assert result.confidence > 0

    def test_process_message_with_context(self, db: Session):
        assistant = AIAssistant(db, provider=MockAIProvider())
        result = assistant.process_message(
            tenant_id=1,
            content="I want to order",
            conversation_id=1,
            customer_id=1,
            platform="instagram",
        )
        assert isinstance(result, AIResponse)
        assert result.action == "collect_order_info"

    def test_provider_factory(self):
        provider = get_ai_provider()
        assert isinstance(provider, (MockAIProvider, OpenAIProvider))


class TestWebhookVerification:
    def test_verify_success(self):
        assert verify_webhook("subscribe", "test_token", "challenge123", "test_token") == "challenge123"

    def test_verify_wrong_mode(self):
        assert verify_webhook("unsubscribe", "test_token", "challenge123", "test_token") is None

    def test_verify_wrong_token(self):
        assert verify_webhook("subscribe", "wrong_token", "challenge123", "test_token") is None

    def test_signature_valid(self):
        payload = b'{"test": "data"}'
        secret = "my_secret"
        import hmac, hashlib
        expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(expected, payload, secret) is True

    def test_signature_invalid(self):
        assert verify_webhook_signature("sha256=invalid", b'{"test": "data"}', "secret") is False

    def test_signature_empty(self):
        assert verify_webhook_signature("", b'test', "secret") is False


class TestParseWebhookEvent:
    def test_parse_message_event(self):
        body = {
            "entry": [{
                "id": "123",
                "messaging": [{
                    "sender": {"id": "user123"},
                    "message": {"text": "Hello", "mid": "msg123"},
                }]
            }]
        }
        events = parse_webhook_event(body)
        assert len(events) == 1
        assert events[0]["type"] == "message"
        assert events[0]["sender_id"] == "user123"
        assert events[0]["message_text"] == "Hello"

    def test_parse_comment_event(self):
        body = {
            "entry": [{
                "id": "123",
                "changes": [{
                    "field": "comments",
                    "value": {
                        "post_id": "post123",
                        "comment_id": "comment123",
                        "text": "Nice product!",
                        "from": {"id": "user456", "name": "John"},
                    }
                }]
            }]
        }
        events = parse_webhook_event(body)
        assert len(events) == 1
        assert events[0]["type"] == "comment"
        assert events[0]["comment_id"] == "comment123"
        assert events[0]["text"] == "Nice product!"

    def test_parse_multiple_entries(self):
        body = {
            "entry": [
                {
                    "id": "123",
                    "messaging": [{"sender": {"id": "u1"}, "message": {"text": "Hi"}}],
                },
                {
                    "id": "456",
                    "changes": [{
                        "field": "comments",
                        "value": {"post_id": "p1", "comment_id": "c1", "text": "Hey", "from": {"id": "u2", "name": "A"}},
                    }],
                },
            ]
        }
        events = parse_webhook_event(body)
        assert len(events) == 2
        assert events[0]["type"] == "message"
        assert events[1]["type"] == "comment"

    def test_parse_empty_entry(self):
        body = {"entry": []}
        events = parse_webhook_event(body)
        assert len(events) == 0


class TestMetaConfig:
    def test_from_env_defaults(self):
        with patch.dict("os.environ", {}, clear=False):
            config = MetaConfig.from_env()
            assert isinstance(config, MetaConfig)

    def test_config_fields(self):
        config = MetaConfig(app_secret="s", verify_token="t", page_access_token="p", ig_account_id="ig")
        assert config.app_secret == "s"
        assert config.verify_token == "t"
