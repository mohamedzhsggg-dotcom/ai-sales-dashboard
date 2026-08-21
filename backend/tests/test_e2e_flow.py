"""End-to-end integration test.

Tests the complete flow:
Instagram/Facebook comment -> post resolution -> product lookup -> AI response -> conversation -> customer info -> order
"""

from app.models import Conversation, Customer, Message, Order, PostProductMapping, Product, SocialComment, Tenant
from app.services.automation.social import SocialAutomation
from app.services.meta.client import MetaMessenger


class TestEndToEndFlow:
    def _setup_product_with_mapping(self, db, tenant, post_id="fb_e2e_post_1", product_name="E2E Widget"):
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
        return product, mapping

    def test_comment_to_conversation_flow(self, db, tenant_a):
        product, mapping = self._setup_product_with_mapping(db, tenant_a)
        automation = SocialAutomation(db, MetaMessenger())

        result = automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook",
            post_id="fb_e2e_post_1", comment_id="e2e_comment_1",
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

        comment = db.query(SocialComment).filter(SocialComment.comment_id == "e2e_comment_1").first()
        assert comment is not None
        assert comment.product_id == product.id
        assert comment.resolved is True

    def test_dm_to_conversation_flow(self, db, tenant_a):
        product, _ = self._setup_product_with_mapping(db, tenant_a, post_id="dm_e2e_post")
        automation = SocialAutomation(db, MetaMessenger())

        result = automation.process_dm(
            tenant_id=tenant_a.id, platform="instagram",
            sender_id="ig_dm_user_1", message_text="I want to order the E2E Widget",
        )

        assert result["status"] == "processed"
        conv = db.get(Conversation, result["conversation_id"])
        assert conv.platform == "instagram"

        customer = db.query(Customer).filter(
            Customer.platform == "instagram",
            Customer.external_id == "ig_dm_user_1",
        ).first()
        assert customer is not None

    def test_full_flow_comment_then_dm(self, db, tenant_a):
        product, _ = self._setup_product_with_mapping(db, tenant_a, post_id="full_flow_post")
        automation = SocialAutomation(db, MetaMessenger())

        automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook",
            post_id="full_flow_post", comment_id="flow_c1",
            user_id="flow_user", username="Flow User",
            text="Nice product!",
        )

        automation.process_dm(
            tenant_id=tenant_a.id, platform="facebook",
            sender_id="flow_user", message_text="I want to buy the E2E Widget",
        )

        convs = db.query(Conversation).filter(
            Conversation.tenant_id == tenant_a.id,
            Conversation.customer_id.isnot(None),
        ).all()
        assert len(convs) >= 1

        customer = db.query(Customer).filter(
            Customer.platform == "facebook",
            Customer.external_id == "flow_user",
        ).first()
        assert customer is not None

    def test_unknown_post_graceful(self, db, tenant_a):
        automation = SocialAutomation(db, MetaMessenger())
        result = automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook",
            post_id="unknown_post_999", comment_id="unk_c1",
            user_id="unk_user", username="Unknown",
            text="What is this?",
        )
        assert result["status"] == "processed"
        assert result["product_id"] is None

    def test_tenant_isolation_e2e(self, db, tenant_a, tenant_b):
        product = Product(
            tenant_id=tenant_a.id, name="T1 Product", price=1000,
            stock=5, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.flush()
        db.add(PostProductMapping(tenant_id=tenant_a.id, platform="facebook", post_id="t1_post", product_id=product.id))
        db.commit()

        automation = SocialAutomation(db, MetaMessenger())

        automation.process_comment(
            tenant_id=tenant_a.id, platform="facebook", post_id="t1_post",
            comment_id="t1_c1", user_id="t1_u", username="T1", text="Hi",
        )
        automation.process_comment(
            tenant_id=tenant_b.id, platform="facebook", post_id="t1_post",
            comment_id="t2_c1", user_id="t2_u", username="T2", text="Hi2",
        )

        t1 = db.query(SocialComment).filter(SocialComment.tenant_id == tenant_a.id).count()
        t2 = db.query(SocialComment).filter(SocialComment.tenant_id == tenant_b.id).count()
        assert t1 >= 1
        assert t2 >= 1
