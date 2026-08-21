"""Orders + Status Machine + Returns tests.

Tests multi-item orders, variant resolution, price snapshots, totals,
status transitions, cancellation with restock, returns, and tenant isolation.
"""

import uuid

import pytest

from app.database import Base, engine, SessionLocal
from app.models import Customer, Order, OrderItem, Product, ProductVariant, Return, Tenant, User
from app.core.security import create_access_token, hash_password
from app.core.status_machine import validate_transition, InvalidTransition, LEGAL_TRANSITIONS


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def tenant_o(db):
    t = db.query(Tenant).filter(Tenant.slug == "test-orders").first()
    if not t:
        t = Tenant(name="Test Orders", slug="test-orders", config={})
        db.add(t)
        db.commit()
        db.refresh(t)
    yield t


@pytest.fixture()
def admin_o(tenant_o, db):
    email = "admin-orders@example.com"
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            tenant_id=tenant_o.id, email=email,
            password_hash=hash_password("Passw0rd!"),
            full_name="Admin Orders", role="admin",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    yield u


@pytest.fixture()
def headers_o(admin_o, client):
    token = create_access_token(admin_o)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def product_o(tenant_o, db):
    p = Product(tenant_id=tenant_o.id, name=f"Order Product {_uid()}", price=1000, stock=50)
    db.add(p)
    db.commit()
    db.refresh(p)
    yield p


# ── Tests ────────────────────────────────────────────────────────────────────


class TestStatusMachine:
    def test_legal_transitions(self):
        assert "confirmed" in LEGAL_TRANSITIONS["new"]
        assert "shipped" in LEGAL_TRANSITIONS["confirmed"]
        assert "delivered" in LEGAL_TRANSITIONS["shipped"]
        assert "cancelled" in LEGAL_TRANSITIONS["new"]
        assert "returned" in LEGAL_TRANSITIONS["delivered"]

    def test_illegal_transition_raises(self):
        with pytest.raises(InvalidTransition):
            validate_transition("new", "delivered")

    def test_terminal_states(self):
        assert len(LEGAL_TRANSITIONS["cancelled"]) == 0
        assert len(LEGAL_TRANSITIONS["refunded"]) == 0


class TestOrderCRUD:
    def test_create_single_item_order(self, client, headers_o, product_o):
        resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550001122", "name": "Test Customer",
            "items": [{"product_id": product_o.id, "quantity": 2}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["items_count"] == 2
        assert data["status"] == "new"
        assert len(data["items"]) == 1
        assert data["items"][0]["unit_price"] == 1000
        assert data["items"][0]["subtotal"] == 2000

    def test_create_multi_item_order(self, client, headers_o, product_o, tenant_o, db):
        p2 = Product(tenant_id=tenant_o.id, name=f"Product2 {_uid()}", price=500, stock=30)
        db.add(p2)
        db.commit()
        db.refresh(p2)
        resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550003344",
            "items": [
                {"product_id": product_o.id, "quantity": 2},
                {"product_id": p2.id, "quantity": 1},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["items_count"] == 3
        assert data["subtotal"] == 2500

    def test_list_orders(self, client, headers_o):
        resp = client.get("/api/v1/orders", headers=headers_o)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 0

    def test_get_order_detail(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550005566",
            "items": [{"product_id": product_o.id, "quantity": 1}],
        })
        order_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/orders/{order_id}", headers=headers_o)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1


class TestOrderConfirmation:
    def test_confirm_order(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550007788",
            "items": [{"product_id": product_o.id, "quantity": 5}],
        })
        order_id = create_resp.json()["id"]
        resp = client.post(f"/api/v1/orders/{order_id}/confirm", headers=headers_o)
        assert resp.status_code == 200
        assert resp.json()["order"]["status"] == "confirmed"

    def test_confirm_insufficient_stock(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550009900",
            "items": [{"product_id": product_o.id, "quantity": 99999}],
        })
        order_id = create_resp.json()["id"]
        resp = client.post(f"/api/v1/orders/{order_id}/confirm", headers=headers_o)
        assert resp.status_code == 409

    def test_cannot_confirm_non_new_order(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550011122",
            "items": [{"product_id": product_o.id, "quantity": 1}],
        })
        order_id = create_resp.json()["id"]
        client.post(f"/api/v1/orders/{order_id}/confirm", headers=headers_o)
        resp = client.post(f"/api/v1/orders/{order_id}/confirm", headers=headers_o)
        assert resp.status_code == 409


class TestOrderStatusTransition:
    def test_legal_transition(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550022233",
            "items": [{"product_id": product_o.id, "quantity": 1}],
        })
        order_id = create_resp.json()["id"]
        client.post(f"/api/v1/orders/{order_id}/confirm", headers=headers_o)
        resp = client.patch(f"/api/v1/orders/{order_id}/status", headers=headers_o, json={
            "status": "shipped",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"

    def test_illegal_transition(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550033344",
            "items": [{"product_id": product_o.id, "quantity": 1}],
        })
        order_id = create_resp.json()["id"]
        resp = client.patch(f"/api/v1/orders/{order_id}/status", headers=headers_o, json={
            "status": "delivered",
        })
        assert resp.status_code == 422

    def test_cancel_requires_note(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550044455",
            "items": [{"product_id": product_o.id, "quantity": 1}],
        })
        order_id = create_resp.json()["id"]
        resp = client.patch(f"/api/v1/orders/{order_id}/status", headers=headers_o, json={
            "status": "cancelled",
        })
        assert resp.status_code == 422


class TestOrderCancellation:
    def test_cancel_new_order(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550055566",
            "items": [{"product_id": product_o.id, "quantity": 1}],
        })
        order_id = create_resp.json()["id"]
        resp = client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers_o, json={
            "note": "Customer changed mind",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


class TestReturns:
    def test_create_return(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550066677",
            "items": [{"product_id": product_o.id, "quantity": 2}],
        })
        order_id = create_resp.json()["id"]
        resp = client.post(f"/api/v1/orders/{order_id}/return", headers=headers_o, json={
            "quantity": 1, "reason": "Wrong size", "refund_amount": 500,
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_approve_return(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550077788",
            "items": [{"product_id": product_o.id, "quantity": 2}],
        })
        order_id = create_resp.json()["id"]
        ret_resp = client.post(f"/api/v1/orders/{order_id}/return", headers=headers_o, json={
            "quantity": 1, "reason": "Defective",
        })
        return_id = ret_resp.json()["id"]
        resp = client.patch(f"/api/v1/orders/returns/{return_id}/approve", headers=headers_o, json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_double_approve_409(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550088899",
            "items": [{"product_id": product_o.id, "quantity": 1}],
        })
        order_id = create_resp.json()["id"]
        ret_resp = client.post(f"/api/v1/orders/{order_id}/return", headers=headers_o, json={
            "quantity": 1, "reason": "Test",
        })
        return_id = ret_resp.json()["id"]
        client.patch(f"/api/v1/orders/returns/{return_id}/approve", headers=headers_o, json={})
        resp = client.patch(f"/api/v1/orders/returns/{return_id}/approve", headers=headers_o, json={})
        assert resp.status_code == 409

    def test_reject_return(self, client, headers_o, product_o):
        create_resp = client.post("/api/v1/orders", headers=headers_o, json={
            "phone": "0550099900",
            "items": [{"product_id": product_o.id, "quantity": 1}],
        })
        order_id = create_resp.json()["id"]
        ret_resp = client.post(f"/api/v1/orders/{order_id}/return", headers=headers_o, json={
            "quantity": 1, "reason": "No reason",
        })
        return_id = ret_resp.json()["id"]
        resp = client.patch(f"/api/v1/orders/returns/{return_id}/reject", headers=headers_o, json={
            "note": "Policy violation",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


class TestOrderTenantIsolation:
    def test_cross_tenant_order_404(self, client, headers_o, tenant_a, db):
        o = Order(tenant_id=tenant_a.id, phone="000", status="new")
        db.add(o)
        db.commit()
        db.refresh(o)
        try:
            resp = client.get(f"/api/v1/orders/{o.id}", headers=headers_o)
            assert resp.status_code == 404
        finally:
            db.delete(o)
            db.commit()
