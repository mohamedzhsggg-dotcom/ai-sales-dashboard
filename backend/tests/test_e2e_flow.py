"""End-to-end integration test.

Tests the complete flow:
Instagram/Facebook comment -> post resolution -> product lookup -> AI response -> conversation -> customer info -> order
"""

import uuid

from app.models import Conversation, Customer, Message, Order, PostProductMapping, Product, SocialComment, Tenant
from app.services.automation.social import SocialAutomation
from app.services.meta.client import MetaMessenger


class TestEndToEndFlow:
    def _setup_product_with_mapping(self, db, tenant, post_id=None, product_name=None):
        uid = uuid.uuid4().hex[:8]
        post_id = post_id or f"fb_e2e_{uid}"
        product_name = product_name or f"E2E Widget {uid}"

        product = Product(
            tenant_id=tenant.id, name=product_name, price=3000,
            stock=20, status="active", sizes='["S","M","L"]', colors='["red","blue"]',
        )
        db.add(product)
        db.flush()

        mapping = PostProductMapping(
            tenant_id=tenant.id, platform="facebook",
            post_id=post_id, product_id=product.id,
            product_name=product_name,
        )
        db.add(mapping)
        db.commit()
        return product, mapping, post_id

    def test_comment_to_conversation_flow(self, db, tenant_a):
        product, mapping, post_id = self._setup_product_with_mapping(db, tenant_a)
        automation = SocialAutomation(db, MetaMessenger())

        result = automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook",
            post_id=post_id, comment_id=f"e2e_c_{uuid.uuid4().hex[:8]}",
            user_id="fb_user_e2e", username="E2E Customer",
            text="Is this available? How much?",
        )

        assert result["status"] == "processed"
        assert result["product_id"] == product.id
        conv_id = result["conversation_id"]

        conv = db.get(Conversation, conv_id)
        assert conv is not None
        assert conv.platform == "facebook"
        assert conv.status == "open"

        messages = db.query(Message).filter(Message.conversation_id == conv_id).all()
        assert len(messages) >= 1
        inbound = [m for m in messages if m.direction == "inbound"]
        outbound = [m for m in messages if m.direction == "outbound"]
        assert len(inbound) == 1
        assert inbound[0].content == "Is this available? How much?"

        comment = db.query(SocialComment).filter(SocialComment.comment_id == result["comment_id"]).first()
        assert comment is not None
        assert comment.product_id == product.id
        assert comment.resolved is True

    def test_dm_to_conversation_flow(self, db, tenant_a):
        product, _, _ = self._setup_product_with_mapping(db, tenant_a)
        automation = SocialAutomation(db, MetaMessenger())
        sender_id = f"ig_dm_{uuid.uuid4().hex[:8]}"

        result = automation.process_dm(
            tenant_id=tenant_a.id, platform="instagram",
            sender_id=sender_id, message_text="I want to order the E2E Widget",
        )

        assert result["status"] == "processed"
        conv = db.get(Conversation, result["conversation_id"])
        assert conv.platform == "instagram"

        customer = db.query(Customer).filter(
            Customer.platform == "instagram",
            Customer.external_id == sender_id,
        ).first()
        assert customer is not None

    def test_full_flow_comment_then_dm(self, db, tenant_a):
        product, _, post_id = self._setup_product_with_mapping(db, tenant_a)
        automation = SocialAutomation(db, MetaMessenger())
        uid = uuid.uuid4().hex[:8]

        automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook",
            post_id=post_id, comment_id=f"flow_c_{uid}",
            user_id=f"flow_user_{uid}", username="Flow User",
            text="Nice product!",
        )

        automation.process_dm(
            tenant_id=tenant_a.id, platform="facebook",
            sender_id=f"flow_user_{uid}", message_text="I want to buy the E2E Widget",
        )

        convs = db.query(Conversation).filter(
            Conversation.tenant_id == tenant_a.id,
            Conversation.customer_id.isnot(None),
        ).all()
        assert len(convs) >= 1

        customer = db.query(Customer).filter(
            Customer.platform == "facebook",
            Customer.external_id == f"flow_user_{uid}",
        ).first()
        assert customer is not None

    def test_unknown_post_graceful(self, db, tenant_a):
        automation = SocialAutomation(db, MetaMessenger())
        result = automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook",
            post_id=f"unknown_post_{uuid.uuid4().hex[:8]}", comment_id=f"unk_c_{uuid.uuid4().hex[:8]}",
            user_id="unk_user", username="Unknown",
            text="What is this?",
        )
        assert result["status"] == "processed"
        assert result["product_id"] is None

    def test_tenant_isolation_e2e(self, db, tenant_a, tenant_b):
        uid = uuid.uuid4().hex[:8]
        product = Product(
            tenant_id=tenant_a.id, name=f"T1 Product {uid}", price=1000,
            stock=5, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.flush()
        db.add(PostProductMapping(tenant_id=tenant_a.id, platform="facebook", post_id=f"t1_post_{uid}", product_id=product.id))
        db.commit()

        automation = SocialAutomation(db, MetaMessenger())

        automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook", post_id=f"t1_post_{uid}",
            comment_id=f"t1_c_{uid}", user_id=f"t1_u_{uid}", username="T1", text="Hi",
        )
        automation.process_comment(
            tenant_id=tenant_b.id, platform="facebook", post_id=f"t1_post_{uid}",
            comment_id=f"t2_c_{uid}", user_id=f"t2_u_{uid}", username="T2", text="Hi2",
        )

        t1 = db.query(SocialComment).filter(SocialComment.tenant_id == tenant_a.id).count()
        t2 = db.query(SocialComment).filter(SocialComment.tenant_id == tenant_b.id).count()
        assert t1 >= 1
        assert t2 >= 1
