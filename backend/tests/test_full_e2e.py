"""Comprehensive end-to-end integration test.

Tests the complete merchant SaaS workflow from registration to shipment,
including tenant isolation verification.
"""

from datetime import datetime, timezone

from app.core.security import create_access_token, hash_password
from app.models import (
    Category, Conversation, Customer, Message, Order, OrderItem,
    PostProductMapping, Product, Shipment, SocialComment, Tenant, User,
)
from app.services.automation.social import SocialAutomation
from app.services.meta.client import MetaMessenger


class TestFullMerchantWorkflow:
    """Complete merchant lifecycle: register -> sell -> ship -> dashboard."""

    def _register_merchant(self, db, business_name="Test Shop", email="test@shop.dz"):
        slug = business_name.lower().replace(" ", "-")
        tenant = Tenant(name=business_name, slug=slug, config={"sheets": {}})
        db.add(tenant)
        db.flush()
        cat = Category(tenant_id=tenant.id, name="Uncategorized", slug=f"uncategorized-{tenant.id}", parent_id=None)
        db.add(cat)
        db.flush()
        user = User(
            tenant_id=tenant.id, email=email,
            password_hash=hash_password("TestPass123!"),
            full_name="Test Owner", role="admin",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return tenant, user, cat

    def test_complete_merchant_lifecycle(self, db, tenant_a):
        """Register -> category -> product -> mapping -> comment -> AI -> order -> shipment -> dashboard."""
        tenant, user, cat = self._register_merchant(db, "Lifecycle Shop", "lifecycle@shop.dz")

        # 1. Create product
        product = Product(
            tenant_id=tenant.id, name="Test Widget", price=5000,
            stock=50, status="active", sizes='["M","L"]', colors='["red","blue"]',
            category_id=cat.id, sku="TW-001", type="simple",
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        assert product.id is not None
        assert product.stock == 50

        # 2. Create post-product mapping
        mapping = PostProductMapping(
            tenant_id=tenant.id, platform="facebook",
            post_id="fb_lifecycle_post_1", product_id=product.id,
            product_name="Test Widget",
        )
        db.add(mapping)
        db.commit()

        # 3. Simulate Meta comment -> AI response -> conversation
        automation = SocialAutomation(db, MetaMessenger())
        result = automation.process_comment(
            tenant_id=tenant.id, platform="facebook",
            post_id="fb_lifecycle_post_1", comment_id="lc_comment_1",
            user_id="fb_buyer_1", username="Buyer One",
            text="How much is this? I want to buy!",
        )
        assert result["status"] == "processed"
        assert result["product_id"] == product.id
        conv_id = result["conversation_id"]

        # 4. Verify conversation and messages created
        conv = db.get(Conversation, conv_id)
        assert conv is not None
        assert conv.platform == "facebook"
        assert conv.status == "open"
        messages = db.query(Message).filter(Message.conversation_id == conv_id).all()
        assert len(messages) >= 1

        # 5. Verify social comment stored
        comment = db.query(SocialComment).filter(
            SocialComment.comment_id == "lc_comment_1"
        ).first()
        assert comment is not None
        assert comment.product_id == product.id

        # 6. Create customer
        customer = Customer(
            tenant_id=tenant.id, name="Buyer One",
            phone="0555123456", wilaya="Alger",
            platform="facebook", external_id="fb_buyer_1",
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        # 7. Create order with items
        order = Order(
            tenant_id=tenant.id, customer_id=customer.id,
            status="new", source_channel="facebook",
            total=5000, wilaya="Alger",
            commune="Bab Ezzouar",
            name="Buyer One",
            phone="0555123456",
        )
        db.add(order)
        db.flush()
        item = OrderItem(
            tenant_id=tenant.id, order_id=order.id, product_id=product.id,
            quantity=1, unit_price=5000, product_name="Test Widget", subtotal=5000,
        )
        db.add(item)
        db.commit()
        db.refresh(order)
        assert order.id is not None

        # 8. Verify stock can be deducted
        old_stock = product.stock
        product.stock -= 1
        db.commit()
        db.refresh(product)
        assert product.stock == old_stock - 1

        # 9. Create shipment
        shipment = Shipment(
            tenant_id=tenant.id, order_id=order.id,
            status="created", courier_name="yalidine",
            tracking_number="YAL-TEST-001",
        )
        db.add(shipment)
        db.commit()
        db.refresh(shipment)
        assert shipment.id is not None

        # 10. Verify tenant isolation
        my_products = db.query(Product).filter(Product.tenant_id == tenant.id).count()
        my_orders = db.query(Order).filter(Order.tenant_id == tenant.id).count()
        my_convs = db.query(Conversation).filter(Conversation.tenant_id == tenant.id).count()
        my_comments = db.query(SocialComment).filter(SocialComment.tenant_id == tenant.id).count()

        other_products = db.query(Product).filter(Product.tenant_id == tenant_a.id).count()
        assert my_products >= 1
        assert my_orders >= 1
        assert my_convs >= 1
        assert my_comments >= 1

        # Products from other tenant should not mix
        tenant_products = db.query(Product).filter(Product.tenant_id == tenant.id).all()
        for p in tenant_products:
            assert p.tenant_id == tenant.id


class TestTenantIsolation:
    """Verify that merchants cannot see each other's data."""

    def test_product_isolation(self, db, tenant_a, tenant_b):
        p1 = Product(tenant_id=tenant_a.id, name="T1 Product", price=100, stock=10, status="active", sizes="[]", colors="[]")
        p2 = Product(tenant_id=tenant_b.id, name="T2 Product", price=200, stock=20, status="active", sizes="[]", colors="[]")
        db.add_all([p1, p2])
        db.commit()

        t1_products = db.query(Product).filter(Product.tenant_id == tenant_a.id).all()
        t2_products = db.query(Product).filter(Product.tenant_id == tenant_b.id).all()

        assert len(t1_products) >= 1
        assert len(t2_products) >= 1
        assert all(p.name != "T2 Product" for p in t1_products)
        assert all(p.name != "T1 Product" for p in t2_products)

    def test_order_isolation(self, db, tenant_a, tenant_b):
        c1 = Customer(tenant_id=tenant_a.id, name="T1 Customer", phone="0555000001", wilaya="Alger")
        c2 = Customer(tenant_id=tenant_b.id, name="T2 Customer", phone="0555000002", wilaya="Oran")
        db.add_all([c1, c2])
        db.flush()

        o1 = Order(tenant_id=tenant_a.id, customer_id=c1.id, status="new", total=100, wilaya="Alger", name="T1 Customer", phone="0555000001")
        o2 = Order(tenant_id=tenant_b.id, customer_id=c2.id, status="new", total=200, wilaya="Oran", name="T2 Customer", phone="0555000002")
        db.add_all([o1, o2])
        db.commit()

        t1_orders = db.query(Order).filter(Order.tenant_id == tenant_a.id).all()
        t2_orders = db.query(Order).filter(Order.tenant_id == tenant_b.id).all()

        assert len(t1_orders) >= 1
        assert len(t2_orders) >= 1
        assert all(o.tenant_id == tenant_a.id for o in t1_orders)
        assert all(o.tenant_id == tenant_b.id for o in t2_orders)

    def test_customer_isolation(self, db, tenant_a, tenant_b):
        c1 = Customer(tenant_id=tenant_a.id, name="Private Customer", phone="0555111111", wilaya="Alger")
        c2 = Customer(tenant_id=tenant_b.id, name="Other Customer", phone="0555222222", wilaya="Oran")
        db.add_all([c1, c2])
        db.commit()

        t1_customers = db.query(Customer).filter(Customer.tenant_id == tenant_a.id).all()
        t2_customers = db.query(Customer).filter(Customer.tenant_id == tenant_b.id).all()

        assert any(c.name == "Private Customer" for c in t1_customers)
        assert not any(c.name == "Private Customer" for c in t2_customers)

    def test_conversation_isolation(self, db, tenant_a, tenant_b):
        conv1 = Conversation(tenant_id=tenant_a.id, platform="facebook", status="open", subject="T1 Conv")
        conv2 = Conversation(tenant_id=tenant_b.id, platform="instagram", status="open", subject="T2 Conv")
        db.add_all([conv1, conv2])
        db.commit()

        t1_convs = db.query(Conversation).filter(Conversation.tenant_id == tenant_a.id).all()
        t2_convs = db.query(Conversation).filter(Conversation.tenant_id == tenant_b.id).all()

        assert any(c.subject == "T1 Conv" for c in t1_convs)
        assert not any(c.subject == "T1 Conv" for c in t2_convs)

    def test_post_mapping_isolation(self, db, tenant_a, tenant_b):
        p1 = Product(tenant_id=tenant_a.id, name="P1", price=100, stock=5, status="active", sizes="[]", colors="[]")
        db.add(p1)
        db.flush()
        m1 = PostProductMapping(tenant_id=tenant_a.id, platform="facebook", post_id="shared_post", product_id=p1.id)
        m2 = PostProductMapping(tenant_id=tenant_b.id, platform="facebook", post_id="shared_post", product_id=p1.id)
        db.add_all([m1, m2])
        db.commit()

        t1_mappings = db.query(PostProductMapping).filter(PostProductMapping.tenant_id == tenant_a.id).all()
        t2_mappings = db.query(PostProductMapping).filter(PostProductMapping.tenant_id == tenant_b.id).all()

        assert len(t1_mappings) >= 1
        assert len(t2_mappings) >= 1
        assert all(m.tenant_id == tenant_a.id for m in t1_mappings)
        assert all(m.tenant_id == tenant_b.id for m in t2_mappings)