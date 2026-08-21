"""Shipments + courier provider tests."""

import pytest
from app.models import Customer, Order, OrderItem, Product, Shipment, ShipmentTracking, Tenant, User
from app.core.security import create_access_token, hash_password
from app.services.couriers.mock import MockCourierProvider
from app.services.couriers.registry import register_provider, get_provider


_uid_counter = 0


def _uid():
    global _uid_counter
    _uid_counter += 1
    return f"ship-{_uid_counter}"


@pytest.fixture()
def tenant_s(db):
    t = db.query(Tenant).filter(Tenant.slug == "test-ship").first()
    if not t:
        t = Tenant(name="Test Shipments", slug="test-ship", config={})
        db.add(t)
        db.commit()
        db.refresh(t)
    yield t


@pytest.fixture()
def admin_s(tenant_s, db):
    email = f"admin-ship-{_uid()}@example.com"
    u = User(
        tenant_id=tenant_s.id, email=email,
        password_hash=hash_password("Passw0rd!"),
        full_name="Admin Ship", role="admin",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    yield u


@pytest.fixture()
def headers_s(admin_s):
    token = create_access_token(admin_s)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def mock_courier():
    mock = MockCourierProvider()
    register_provider(mock)
    yield mock


@pytest.fixture()
def product_s(tenant_s, db):
    p = Product(tenant_id=tenant_s.id, name=f"Ship Product {_uid()}", price=1500, stock=100)
    db.add(p)
    db.commit()
    db.refresh(p)
    yield p


@pytest.fixture()
def customer_s(tenant_s, db):
    c = Customer(tenant_id=tenant_s.id, phone=f"0550{_uid().replace('-','')}", name="Ship Customer")
    db.add(c)
    db.commit()
    db.refresh(c)
    yield c


@pytest.fixture()
def confirmed_order_s(tenant_s, customer_s, product_s, db):
    o = Order(
        tenant_id=tenant_s.id,
        customer_id=customer_s.id,
        phone=customer_s.phone,
        name=customer_s.name,
        wilaya="Alger",
        commune="Bab Ezzouar",
        product=product_s.name,
        quantity=2,
        price=1500,
        status="confirmed",
        delivery_method="home",
        subtotal=3000,
        total=3000,
        items_count=2,
    )
    db.add(o)
    db.flush()
    item = OrderItem(
        tenant_id=tenant_s.id,
        order_id=o.id,
        product_id=product_s.id,
        product_name=product_s.name,
        quantity=2,
        unit_price=1500,
        subtotal=3000,
    )
    db.add(item)
    db.commit()
    db.refresh(o)
    yield o


@pytest.fixture()
def new_order_s(tenant_s, customer_s, product_s, db):
    o = Order(
        tenant_id=tenant_s.id,
        customer_id=customer_s.id,
        phone=customer_s.phone,
        name=customer_s.name,
        wilaya="Oran",
        product=product_s.name,
        quantity=1,
        price=1500,
        status="new",
        subtotal=1500,
        total=1500,
        items_count=1,
    )
    db.add(o)
    db.flush()
    item = OrderItem(
        tenant_id=tenant_s.id,
        order_id=o.id,
        product_id=product_s.id,
        product_name=product_s.name,
        quantity=1,
        unit_price=1500,
        subtotal=1500,
    )
    db.add(item)
    db.commit()
    db.refresh(o)
    yield o


class TestCourierProviders:
    def test_registry(self):
        mock = MockCourierProvider()
        register_provider(mock)
        assert get_provider("mock") is mock
        assert get_provider() is mock

    def test_mock_create(self):
        mock = MockCourierProvider()
        from app.services.couriers.base import ShipmentRequest
        result = mock.create_shipment(ShipmentRequest(
            order_id=1, tenant_id=1, phone="055", name="Test",
            wilaya="Alger",
        ))
        assert result.success
        assert result.tracking_number.startswith("MOCK-")
        assert result.status == "pending"

    def test_mock_track(self):
        mock = MockCourierProvider()
        from app.services.couriers.base import ShipmentRequest
        result = mock.create_shipment(ShipmentRequest(
            order_id=1, tenant_id=1, phone="055", name="Test",
            wilaya="Alger",
        ))
        tracked = mock.track_shipment(result.tracking_number)
        assert tracked.success
        assert tracked.status == "pending"

    def test_mock_advance_status(self):
        mock = MockCourierProvider()
        from app.services.couriers.base import ShipmentRequest
        result = mock.create_shipment(ShipmentRequest(
            order_id=1, tenant_id=1, phone="055", name="Test",
            wilaya="Alger",
        ))
        mock.advance_status(result.tracking_number, "delivered")
        tracked = mock.track_shipment(result.tracking_number)
        assert tracked.status == "delivered"

    def test_mock_cancel(self):
        mock = MockCourierProvider()
        from app.services.couriers.base import ShipmentRequest
        result = mock.create_shipment(ShipmentRequest(
            order_id=1, tenant_id=1, phone="055", name="Test",
            wilaya="Alger",
        ))
        cancelled = mock.cancel_shipment(result.tracking_number)
        assert cancelled.success
        assert cancelled.status == "cancelled"

    def test_mock_track_not_found(self):
        mock = MockCourierProvider()
        result = mock.track_shipment("FAKE-123")
        assert not result.success

    def test_mock_cancel_not_found(self):
        mock = MockCourierProvider()
        result = mock.cancel_shipment("FAKE-123")
        assert not result.success


class TestShipmentAPI:
    def test_create_shipment(self, client, headers_s, confirmed_order_s, mock_courier):
        resp = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id,
            "courier_name": "mock",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["courier_name"] == "mock"
        assert data["tracking_number"].startswith("MOCK-")
        assert data["status"] == "pending"
        assert data["order_id"] == confirmed_order_s.id

    def test_create_shipment_for_new_order(self, client, headers_s, new_order_s, mock_courier):
        resp = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": new_order_s.id,
            "courier_name": "mock",
        })
        assert resp.status_code == 201

    def test_create_shipment_duplicate_409(self, client, headers_s, confirmed_order_s, mock_courier):
        resp1 = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id, "courier_name": "mock",
        })
        assert resp1.status_code == 201
        resp2 = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id, "courier_name": "mock",
        })
        assert resp2.status_code == 409

    def test_list_shipments(self, client, headers_s, confirmed_order_s, mock_courier):
        client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id, "courier_name": "mock",
        })
        resp = client.get("/api/v1/shipments", headers=headers_s)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_get_shipment_detail(self, client, headers_s, confirmed_order_s, mock_courier):
        create_resp = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id, "courier_name": "mock",
        })
        sid = create_resp.json()["id"]
        resp = client.get(f"/api/v1/shipments/{sid}", headers=headers_s)
        assert resp.status_code == 200
        assert resp.json()["tracking_number"].startswith("MOCK-")

    def test_refresh_tracking(self, client, headers_s, confirmed_order_s, mock_courier):
        create_resp = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id, "courier_name": "mock",
        })
        sid = create_resp.json()["id"]
        resp = client.post(f"/api/v1/shipments/{sid}/refresh", headers=headers_s)
        assert resp.status_code == 200

    def test_cancel_shipment(self, client, headers_s, confirmed_order_s, mock_courier):
        create_resp = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id, "courier_name": "mock",
        })
        sid = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/shipments/{sid}", headers=headers_s)
        assert resp.status_code == 204

    def test_cancel_delivered_409(self, client, headers_s, confirmed_order_s, mock_courier, db):
        create_resp = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id, "courier_name": "mock",
        })
        sid = create_resp.json()["id"]
        tn = create_resp.json()["tracking_number"]
        mock_courier.advance_status(tn, "delivered")
        shipment = db.get(Shipment, sid)
        shipment.status = "delivered"
        db.commit()
        resp = client.delete(f"/api/v1/shipments/{sid}", headers=headers_s)
        assert resp.status_code == 409

    def test_unknown_courier_400(self, client, headers_s, confirmed_order_s):
        resp = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": confirmed_order_s.id, "courier_name": "nonexistent",
        })
        assert resp.status_code == 400

    def test_order_not_found_404(self, client, headers_s, mock_courier):
        resp = client.post("/api/v1/shipments", headers=headers_s, json={
            "order_id": 99999, "courier_name": "mock",
        })
        assert resp.status_code == 404
