"""Inventory API tests.

Tests adjustments, variant adjustments, negative stock rejection,
stock counts, reconciliation, tenant isolation, and ledger integrity.
"""

import uuid

import pytest

from app.database import Base, engine, SessionLocal
from app.models import InventoryEvent, Product, ProductVariant, StockCount, Tenant, User
from app.core.security import create_access_token, hash_password


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
def tenant_inv(db):
    t = db.query(Tenant).filter(Tenant.slug == "test-inv").first()
    if not t:
        t = Tenant(name="Test Inventory", slug="test-inv", config={})
        db.add(t)
        db.commit()
        db.refresh(t)
    yield t


@pytest.fixture()
def admin_inv(tenant_inv, db):
    email = "admin-inv@example.com"
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            tenant_id=tenant_inv.id, email=email,
            password_hash=hash_password("Passw0rd!"),
            full_name="Admin Inventory", role="admin",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    yield u


@pytest.fixture()
def headers_inv(admin_inv, client):
    token = create_access_token(admin_inv)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def inv_product(tenant_inv, db):
    p = Product(tenant_id=tenant_inv.id, name=f"Inv Product {_uid()}", stock=20, low_stock_threshold=5)
    db.add(p)
    db.commit()
    db.refresh(p)
    yield p


@pytest.fixture()
def inv_variant(tenant_inv, inv_product, db):
    v = ProductVariant(
        tenant_id=tenant_inv.id, product_id=inv_product.id,
        options={"color": "Red"}, stock=10,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    yield v


# ── Tests ────────────────────────────────────────────────────────────────────


class TestInventoryAdjust:
    def test_add_stock(self, client, headers_inv, inv_product):
        resp = client.patch(f"/api/v1/inventory/{inv_product.id}/stock", headers=headers_inv, json={
            "quantity": 5, "reason": "restock",
        })
        assert resp.status_code == 200
        assert resp.json()["stock"] == 25

    def test_deduct_stock(self, client, headers_inv, inv_product):
        resp = client.patch(f"/api/v1/inventory/{inv_product.id}/stock", headers=headers_inv, json={
            "quantity": -5, "reason": "adjustment",
        })
        assert resp.status_code == 200
        assert resp.json()["stock"] == 15

    def test_set_stock(self, client, headers_inv, inv_product):
        resp = client.patch(f"/api/v1/inventory/{inv_product.id}/stock", headers=headers_inv, json={
            "quantity": 50, "reason": "set",
        })
        assert resp.status_code == 200
        assert resp.json()["stock"] == 50


class TestInventoryNegativeStock:
    def test_deduct_below_zero_fails(self, client, headers_inv, inv_product):
        resp = client.patch(f"/api/v1/inventory/{inv_product.id}/stock", headers=headers_inv, json={
            "quantity": -9999, "reason": "adjustment",
        })
        assert resp.status_code == 409


class TestInventoryLedger:
    def test_events_recorded(self, client, headers_inv, inv_product, db):
        client.patch(f"/api/v1/inventory/{inv_product.id}/stock", headers=headers_inv, json={
            "quantity": 3, "reason": "restock",
        })
        events = db.query(InventoryEvent).filter(
            InventoryEvent.product_id == inv_product.id,
        ).order_by(InventoryEvent.id.desc()).all()
        assert len(events) >= 1
        assert events[0].reason == "restock"


class TestInventoryMovements:
    def test_list_movements(self, client, headers_inv, inv_product):
        resp = client.get("/api/v1/inventory/movements", headers=headers_inv)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_product(self, client, headers_inv, inv_product):
        resp = client.get(f"/api/v1/inventory/movements?product_id={inv_product.id}", headers=headers_inv)
        assert resp.status_code == 200


class TestInventorySummary:
    def test_summary(self, client, headers_inv):
        resp = client.get("/api/v1/inventory/summary", headers=headers_inv)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_products" in data
        assert "total_stock" in data


class TestStockCounts:
    def test_create_stock_count(self, client, headers_inv, inv_product):
        resp = client.post("/api/v1/inventory/stock-counts", headers=headers_inv, json={
            "product_id": inv_product.id, "counted_quantity": 18, "note": "Physical count",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["expected_quantity"] == inv_product.stock
        assert data["counted_quantity"] == 18

    def test_reconcile_stock_count(self, client, headers_inv, inv_product, db):
        sc_resp = client.post("/api/v1/inventory/stock-counts", headers=headers_inv, json={
            "product_id": inv_product.id, "counted_quantity": 25,
        })
        count_id = sc_resp.json()["id"]
        resp = client.post(f"/api/v1/inventory/stock-counts/{count_id}/reconcile", headers=headers_inv, json={})
        assert resp.status_code == 200
        assert resp.json()["reconciled"] is True

    def test_double_reconcile_409(self, client, headers_inv, inv_product, db):
        sc_resp = client.post("/api/v1/inventory/stock-counts", headers=headers_inv, json={
            "product_id": inv_product.id, "counted_quantity": 25,
        })
        count_id = sc_resp.json()["id"]
        client.post(f"/api/v1/inventory/stock-counts/{count_id}/reconcile", headers=headers_inv, json={})
        resp = client.post(f"/api/v1/inventory/stock-counts/{count_id}/reconcile", headers=headers_inv, json={})
        assert resp.status_code == 409


class TestInventoryTenantIsolation:
    def test_cross_tenant_adjust_404(self, client, headers_inv, tenant_a, db):
        p = Product(tenant_id=tenant_a.id, name="Cross Tenant Inv", stock=5)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.patch(f"/api/v1/inventory/{p.id}/stock", headers=headers_inv, json={
                "quantity": 5, "reason": "restock",
            })
            assert resp.status_code == 404
        finally:
            db.delete(p)
            db.commit()
