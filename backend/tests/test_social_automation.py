"""Tests for social comment automation and conversation flows."""

from datetime import datetime, timezone

from app.models import Conversation, Customer, Message, PostProductMapping, Product, SocialComment
from app.services.automation.social import SocialAutomation
from app.services.meta.client import MetaMessenger


class TestSocialAutomation:
    def _setup_product(self, db, tenant):
        product = Product(
            tenant_id=tenant.id, name="Test Widget", price=1500,
            stock=10, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.flush()
        return product

    def _setup_mapping(self, db, tenant, platform, post_id, product_id):
        mapping = PostProductMapping(
            tenant_id=tenant.id, platform=platform,
            post_id=post_id, product_id=product_id,
        )
        db.add(mapping)
        db.flush()
        return mapping

    def test_process_comment_with_product(self, db, tenant_a):
        product = self._setup_product(db, tenant_a)
        self._setup_mapping(db, tenant_a, "facebook", "post_abc", product.id)

        automation = SocialAutomation(db, MetaMessenger())
        result = automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook", post_id="post_abc",
            comment_id="comment_1", user_id="user_fb_1",
            username="Test User", text="How much is this?",
        )
        assert result["status"] == "processed"
        assert result["product_id"] == product.id
        assert result["conversation_id"] is not None

        comment = db.query(SocialComment).filter(SocialComment.comment_id == "comment_1").first()
        assert comment is not None
        assert comment.product_id == product.id
        assert comment.resolved is True

    def test_process_comment_without_product(self, db, tenant_a):
        automation = SocialAutomation(db, MetaMessenger())
        result = automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook", post_id="unknown_post",
            comment_id="comment_2", user_id="user_fb_2",
            username="Another User", text="Nice!",
        )
        assert result["status"] == "processed"
        assert result["product_id"] is None

        comment = db.query(SocialComment).filter(SocialComment.comment_id == "comment_2").first()
        assert comment.resolved is False

    def test_duplicate_comment_rejected(self, db, tenant_a):
        self._setup_product(db, tenant_a)
        automation = SocialAutomation(db, MetaMessenger())
        automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook", post_id="post_dup",
            comment_id="dup_1", user_id="u1", username="U1", text="Hi",
        )
        result = automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook", post_id="post_dup",
            comment_id="dup_1", user_id="u1", username="U1", text="Hi again",
        )
        assert result["status"] == "duplicate"

    def test_process_dm_creates_conversation(self, db, tenant_a):
        automation = SocialAutomation(db, MetaMessenger())
        result = automation.process_dm(
            tenant_id=tenant_a.id, platform="instagram",
            sender_id="ig_user_1", message_text="Hello!",
        )
        assert result["status"] == "processed"
        assert result["conversation_id"] is not None

        conv = db.get(Conversation, result["conversation_id"])
        assert conv is not None
        assert conv.platform == "instagram"
        assert conv.status == "open"

    def test_dm_message_persisted(self, db, tenant_a):
        automation = SocialAutomation(db, MetaMessenger())
        result = automation.process_dm(
            tenant_id=tenant_a.id, platform="facebook",
            sender_id="fb_user_1", message_text="Test message",
        )
        conv_id = result["conversation_id"]
        messages = db.query(Message).filter(Message.conversation_id == conv_id).all()
        assert len(messages) >= 1
        inbound = [m for m in messages if m.direction == "inbound"]
        assert len(inbound) == 1
        assert inbound[0].content == "Test message"

    def test_tenant_isolation_comments(self, db, tenant_a, tenant_b):
        self._setup_product(db, tenant_a)
        automation = SocialAutomation(db, MetaMessenger())

        automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook", post_id="post_iso",
            comment_id="iso_1", user_id="u1", username="U1", text="Hi",
        )
        automation.process_comment(
            tenant_id=tenant_b.id, platform="facebook", post_id="post_iso",
            comment_id="iso_2", user_id="u2", username="U2", text="Hi2",
        )

        t1_comments = db.query(SocialComment).filter(SocialComment.tenant_id == tenant_a.id).count()
        t2_comments = db.query(SocialComment).filter(SocialComment.tenant_id == tenant_b.id).count()
        assert t1_comments >= 1
        assert t2_comments >= 1
