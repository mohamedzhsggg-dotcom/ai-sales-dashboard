"""Products & Variants API tests.

Tests CRUD, variable products, variants, price inheritance, SKU uniqueness,
tenant isolation, archive behavior, and low stock indicators.
"""

import uuid

import pytest
from sqlalchemy import text

from app.database import Base, engine, SessionLocal
from app.models import Category, Product, ProductVariant, Tenant, User
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
def tenant_p(db):
    t = db.query(Tenant).filter(Tenant.slug == "test-prod").first()
    if not t:
        t = Tenant(name="Test Products", slug="test-prod", config={})
        db.add(t)
        db.commit()
        db.refresh(t)
    yield t


@pytest.fixture()
def admin_p(tenant_p, db):
    email = "admin-prod@example.com"
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            tenant_id=tenant_p.id, email=email,
            password_hash=hash_password("Passw0rd!"),
            full_name="Admin Products", role="admin",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    yield u


@pytest.fixture()
def headers_p(admin_p, client):
    token = create_access_token(admin_p)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def simple_product(tenant_p, db):
    slug = _uid()
    p = Product(
        tenant_id=tenant_p.id, name=f"Simple {slug}", type="simple",
        sku=f"SIM-{slug}", price=1000, stock=20, status="active",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    yield p
    db.delete(p)
    db.commit()


@pytest.fixture()
def variable_product(tenant_p, db):
    slug = _uid()
    p = Product(
        tenant_id=tenant_p.id, name=f"Variable {slug}", type="variable",
        price=2000, stock=0, status="active",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    yield p
    db.delete(p)
    db.commit()


@pytest.fixture()
def variant_a(tenant_p, variable_product, db):
    v = ProductVariant(
        tenant_id=tenant_p.id, product_id=variable_product.id,
        sku=f"VAR-{_uid()}", options={"color": "Red", "size": "M"},
        price=2200, stock=10,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    yield v
    db.delete(v)
    db.commit()


# ── Tests ────────────────────────────────────────────────────────────────────


class TestProductCRUD:
    def test_list_products(self, client, headers_p):
        resp = client.get("/api/v1/products", headers=headers_p)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 0

    def test_create_simple_product(self, client, headers_p):
        sku = f"SIM-{_uid()}"
        resp = client.post("/api/v1/products", headers=headers_p, json={
            "name": "New Simple", "type": "simple", "sku": sku,
            "price": 1500, "stock": 10,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Simple"
        assert data["type"] == "simple"
        assert data["sku"] == sku
        assert data["stock"] == 10
        assert data["variant_count"] == 0

    def test_create_variable_product(self, client, headers_p):
        resp = client.post("/api/v1/products", headers=headers_p, json={
            "name": "New Variable", "type": "variable", "price": 3000,
        })
        assert resp.status_code == 201
        assert resp.json()["type"] == "variable"

    def test_get_product_detail(self, client, headers_p, simple_product):
        resp = client.get(f"/api/v1/products/{simple_product.id}", headers=headers_p)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == simple_product.name
        assert data["price"] == 1000

    def test_update_product(self, client, headers_p, simple_product):
        resp = client.patch(f"/api/v1/products/{simple_product.id}", headers=headers_p, json={
            "name": "Updated Name", "price": 1200,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["price"] == 1200

    def test_archive_product(self, client, headers_p, tenant_p, db):
        p = Product(tenant_id=tenant_p.id, name=f"To Archive {_uid()}", stock=5)
        db.add(p)
        db.commit()
        db.refresh(p)
        resp = client.delete(f"/api/v1/products/{p.id}", headers=headers_p)
        assert resp.status_code == 204
        db.refresh(p)
        assert p.status == "archived"

    def test_404_nonexistent(self, client, headers_p):
        resp = client.get("/api/v1/products/999999", headers=headers_p)
        assert resp.status_code == 404


class TestProductSKU:
    def test_dup_sku_same_tenant_409(self, client, headers_p, simple_product):
        resp = client.post("/api/v1/products", headers=headers_p, json={
            "name": "Dup SKU", "sku": simple_product.sku,
        })
        assert resp.status_code == 409

    def test_same_sku_different_tenant_ok(self, client, headers_p, tenant_p, db, tenant_a):
        sku = f"SHARED-{_uid()}"
        p = Product(tenant_id=tenant_a.id, name="Other Tenant", sku=sku, stock=1)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.post("/api/v1/products", headers=headers_p, json={
                "name": "Same SKU Different Tenant", "sku": sku,
            })
            assert resp.status_code == 201
        finally:
            db.delete(p)
            db.commit()

    def test_update_sku_to_existing_409(self, client, headers_p, tenant_p, db):
        p1 = Product(tenant_id=tenant_p.id, name=f"P1 {_uid()}", sku=f"SKU-A-{_uid()}", stock=1)
        db.add(p1)
        db.commit()
        db.refresh(p1)
        p2 = Product(tenant_id=tenant_p.id, name=f"P2 {_uid()}", sku=f"SKU-B-{_uid()}", stock=1)
        db.add(p2)
        db.commit()
        db.refresh(p2)
        try:
            resp = client.patch(f"/api/v1/products/{p2.id}", headers=headers_p, json={
                "sku": p1.sku,
            })
            assert resp.status_code == 409
        finally:
            db.delete(p2)
            db.delete(p1)
            db.commit()


class TestProductTenantIsolation:
    def test_cross_tenant_404(self, client, headers_p, tenant_a, db):
        p = Product(tenant_id=tenant_a.id, name="Cross Tenant", stock=1)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.get(f"/api/v1/products/{p.id}", headers=headers_p)
            assert resp.status_code == 404
        finally:
            db.delete(p)
            db.commit()

    def test_cross_tenant_update_404(self, client, headers_p, tenant_a, db):
        p = Product(tenant_id=tenant_a.id, name="Cross Tenant Upd", stock=1)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.patch(f"/api/v1/products/{p.id}", headers=headers_p, json={"name": "Hijack"})
            assert resp.status_code == 404
        finally:
            db.delete(p)
            db.commit()


class TestProductArchive:
    def test_archived_excluded_from_list(self, client, headers_p, tenant_p, db):
        p = Product(tenant_id=tenant_p.id, name=f"Archived {_uid()}", status="archived", stock=1)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.get("/api/v1/products", headers=headers_p)
            ids = [item["id"] for item in resp.json()["items"]]
            assert p.id not in ids
        finally:
            db.delete(p)
            db.commit()

    def test_archived_can_be_fetched_by_id(self, client, headers_p, tenant_p, db):
        p = Product(tenant_id=tenant_p.id, name=f"Archived2 {_uid()}", status="archived", stock=1)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.get(f"/api/v1/products/{p.id}", headers=headers_p)
            assert resp.status_code == 200
        finally:
            db.delete(p)
            db.commit()


class TestProductCategory:
    def test_assign_category(self, client, headers_p, tenant_p, db):
        cat = Category(tenant_id=tenant_p.id, name=f"Cat {_uid()}", slug=f"cat-{_uid()}")
        db.add(cat)
        db.commit()
        db.refresh(cat)
        p = Product(tenant_id=tenant_p.id, name=f"With Cat {_uid()}", stock=1)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.patch(f"/api/v1/products/{p.id}", headers=headers_p, json={
                "category_id": cat.id,
            })
            assert resp.status_code == 200
            assert resp.json()["category_id"] == cat.id
        finally:
            db.delete(p)
            db.delete(cat)
            db.commit()

    def test_invalid_category_404(self, client, headers_p, simple_product):
        resp = client.patch(f"/api/v1/products/{simple_product.id}", headers=headers_p, json={
            "category_id": 99999,
        })
        assert resp.status_code == 404


class TestVariantCRUD:
    def test_create_variant(self, client, headers_p, variable_product):
        resp = client.post(f"/api/v1/products/{variable_product.id}/variants", headers=headers_p, json={
            "options": {"color": "Blue", "size": "L"},
            "price": 2500, "stock": 5,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["options"]["color"] == "Blue"
        assert data["stock"] == 5

    def test_list_variants(self, client, headers_p, variable_product, variant_a):
        resp = client.get(f"/api/v1/products/{variable_product.id}/variants", headers=headers_p)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_variant(self, client, headers_p, variable_product, variant_a):
        resp = client.patch(
            f"/api/v1/products/{variable_product.id}/variants/{variant_a.id}",
            headers=headers_p, json={"stock": 15},
        )
        assert resp.status_code == 200
        assert resp.json()["stock"] == 15

    def test_delete_variant(self, client, headers_p, variable_product, variant_a):
        resp = client.delete(
            f"/api/v1/products/{variable_product.id}/variants/{variant_a.id}",
            headers=headers_p,
        )
        assert resp.status_code == 204


class TestVariantPriceInheritance:
    def test_effective_price_inherits_parent(self, client, headers_p, variable_product, variant_a):
        resp = client.get(f"/api/v1/products/{variable_product.id}", headers=headers_p)
        assert resp.status_code == 200
        variant_data = next(v for v in resp.json()["variants"] if v["id"] == variant_a.id)
        assert variant_data["effective_price"] == 2200

    def test_effective_price_override(self, client, headers_p, tenant_p, db):
        p = Product(tenant_id=tenant_p.id, name=f"PriceTest {_uid()}", type="variable", price=1000, stock=0)
        db.add(p)
        db.commit()
        db.refresh(p)
        v = ProductVariant(
            tenant_id=tenant_p.id, product_id=p.id,
            options={"color": "Green"}, price=None, stock=5,
        )
        db.add(v)
        db.commit()
        db.refresh(v)
        try:
            resp = client.get(f"/api/v1/products/{p.id}", headers=headers_p)
            variant_data = next(vd for vd in resp.json()["variants"] if vd["id"] == v.id)
            assert variant_data["effective_price"] == 1000
        finally:
            db.delete(v)
            db.delete(p)
            db.commit()


class TestVariantSKU:
    def test_dup_variant_sku_409(self, client, headers_p, variable_product, variant_a):
        resp = client.post(
            f"/api/v1/products/{variable_product.id}/variants",
            headers=headers_p, json={"sku": variant_a.sku, "options": {"color": "Green"}},
        )
        assert resp.status_code == 409


class TestVariantOptions:
    def test_get_options(self, client, headers_p, variable_product, variant_a):
        resp = client.get(f"/api/v1/products/{variable_product.id}/variants/options", headers=headers_p)
        assert resp.status_code == 200
        data = resp.json()
        assert "color" in data
        assert "Red" in data["color"]


class TestProductLowStock:
    def test_low_stock_indicator(self, client, headers_p, tenant_p, db):
        p = Product(tenant_id=tenant_p.id, name=f"Low {_uid()}", stock=3, low_stock_threshold=5)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.get(f"/api/v1/products/{p.id}", headers=headers_p)
            assert resp.json()["low_stock"] is True
        finally:
            db.delete(p)
            db.commit()

    def test_zero_stock_not_low(self, client, headers_p, tenant_p, db):
        p = Product(tenant_id=tenant_p.id, name=f"Zero {_uid()}", stock=0, low_stock_threshold=5)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.get(f"/api/v1/products/{p.id}", headers=headers_p)
            assert resp.json()["low_stock"] is False
        finally:
            db.delete(p)
            db.commit()

    def test_variant_stock_includes_in_total(self, client, headers_p, variable_product, variant_a):
        resp = client.get(f"/api/v1/products/{variable_product.id}", headers=headers_p)
        assert resp.json()["total_stock"] >= 10


class TestProductRBAC:
    def test_support_user_cannot_create(self, client, tenant_p, db):
        email = "support-prod@example.com"
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                tenant_id=tenant_p.id, email=email,
                password_hash=hash_password("Passw0rd!"),
                full_name="Support Products", role="support",
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        token = create_access_token(u)
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/products", headers=headers, json={"name": "Forbidden"})
        assert resp.status_code == 403
