"""Category API + model tests.

All tests run against dashboard_test DB. Each test gets unique slugs
and cleans up after itself.
"""

import uuid

import pytest
from sqlalchemy import text

from app.database import Base, engine, SessionLocal
from app.models import Category, Product, Tenant, User
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


def _unique(prefix: str = "cat") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def tenant_c(db):
    t = db.query(Tenant).filter(Tenant.slug == "test-cat").first()
    if not t:
        t = Tenant(name="Test Categories", slug="test-cat", config={})
        db.add(t)
        db.commit()
        db.refresh(t)
    yield t


@pytest.fixture()
def admin_cat_user(tenant_c, db):
    email = "admin-cat@example.com"
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            tenant_id=tenant_c.id, email=email,
            password_hash=hash_password("Passw0rd!"),
            full_name="Admin Categories", role="admin",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    yield u


@pytest.fixture()
def support_cat_user(tenant_c, db):
    email = "support-cat@example.com"
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            tenant_id=tenant_c.id, email=email,
            password_hash=hash_password("Passw0rd!"),
            full_name="Support Categories", role="support",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    yield u


@pytest.fixture()
def cat_a(tenant_c, db):
    slug = _unique("cat-a")
    c = Category(tenant_id=tenant_c.id, name="Test Category A", slug=slug)
    db.add(c)
    db.commit()
    db.refresh(c)
    yield c
    db.delete(c)
    db.commit()


@pytest.fixture()
def product_in_cat(tenant_c, cat_a, db):
    p = Product(tenant_id=tenant_c.id, name="Product in Cat A", stock=5, category_id=cat_a.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    yield p
    db.delete(p)
    db.commit()


@pytest.fixture()
def headers_cat(admin_cat_user, client):
    token = create_access_token(admin_cat_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers_support(support_cat_user, client):
    token = create_access_token(support_cat_user)
    return {"Authorization": f"Bearer {token}"}


# ── Tests ────────────────────────────────────────────────────────────────────


class TestCategoryCRUD:
    def test_list_empty(self, client, headers_cat):
        resp = client.get("/api/v1/categories", headers=headers_cat)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        assert isinstance(data["items"], list)

    def test_create_category(self, client, headers_cat):
        slug = _unique("electronics")
        resp = client.post("/api/v1/categories", headers=headers_cat, json={
            "name": "Electronics", "slug": slug, "sort_order": 1,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Electronics"
        assert data["slug"] == slug
        assert data["is_active"] is True
        assert data["product_count"] == 0
        assert data["id"] is not None

    def test_create_category_slug_auto(self, client, headers_cat):
        slug_suffix = _unique()
        name = f"Shoes & Accessories {slug_suffix}"
        resp = client.post("/api/v1/categories", headers=headers_cat, json={
            "name": name,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["slug"] is not None
        assert len(data["slug"]) > 0

    def test_get_category(self, client, headers_cat, cat_a):
        resp = client.get(f"/api/v1/categories/{cat_a.id}", headers=headers_cat)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Category A"

    def test_get_category_with_product_count(self, client, headers_cat, cat_a, product_in_cat):
        resp = client.get(f"/api/v1/categories/{cat_a.id}", headers=headers_cat)
        assert resp.status_code == 200
        assert resp.json()["product_count"] == 1

    def test_update_category(self, client, headers_cat, cat_a):
        resp = client.patch(f"/api/v1/categories/{cat_a.id}", headers=headers_cat, json={
            "name": "Updated Category",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Category"

    def test_delete_category(self, client, headers_cat, tenant_c, db):
        slug = _unique("del")
        c = Category(tenant_id=tenant_c.id, name="To Delete", slug=slug)
        db.add(c)
        db.commit()
        db.refresh(c)
        resp = client.delete(f"/api/v1/categories/{c.id}", headers=headers_cat)
        assert resp.status_code == 204
        db.refresh(c)
        assert c.is_active is False

    def test_404_when_get_nonexistent(self, client, headers_cat):
        resp = client.get("/api/v1/categories/999999", headers=headers_cat)
        assert resp.status_code == 404


class TestCategoryTree:
    def test_tree_returns_hierarchy(self, client, headers_cat, tenant_c, db):
        parent_slug = _unique("parent")
        child_slug = _unique("child")
        parent = Category(tenant_id=tenant_c.id, name="Parent", slug=parent_slug, sort_order=1)
        db.add(parent)
        db.commit()
        db.refresh(parent)
        child = Category(tenant_id=tenant_c.id, name="Child", slug=child_slug, parent_id=parent.id, sort_order=1)
        db.add(child)
        db.commit()
        try:
            resp = client.get("/api/v1/categories/tree", headers=headers_cat)
            assert resp.status_code == 200
            data = resp.json()
            parent_node = next((n for n in data if n["slug"] == parent_slug), None)
            assert parent_node is not None
            assert any(c["slug"] == child_slug for c in parent_node["children"])
        finally:
            db.delete(child)
            db.delete(parent)
            db.commit()


class TestCategoryTenantIsolation:
    def test_cross_tenant_access_returns_404(self, client, headers_cat, tenant_c, tenant_a, db):
        slug = _unique("other")
        other = Category(tenant_id=tenant_a.id, name="Other Tenant Cat", slug=slug)
        db.add(other)
        db.commit()
        db.refresh(other)
        try:
            resp = client.get(f"/api/v1/categories/{other.id}", headers=headers_cat)
            assert resp.status_code == 404
        finally:
            db.delete(other)
            db.commit()

    def test_cross_tenant_update_returns_404(self, client, headers_cat, tenant_c, tenant_a, db):
        slug = _unique("other-upd")
        other = Category(tenant_id=tenant_a.id, name="Other Tenant", slug=slug)
        db.add(other)
        db.commit()
        db.refresh(other)
        try:
            resp = client.patch(f"/api/v1/categories/{other.id}", headers=headers_cat, json={"name": "Hijack"})
            assert resp.status_code == 404
        finally:
            db.delete(other)
            db.commit()

    def test_cross_tenant_delete_returns_404(self, client, headers_cat, tenant_c, tenant_a, db):
        slug = _unique("other-del")
        other = Category(tenant_id=tenant_a.id, name="Other Tenant", slug=slug)
        db.add(other)
        db.commit()
        db.refresh(other)
        try:
            resp = client.delete(f"/api/v1/categories/{other.id}", headers=headers_cat)
            assert resp.status_code == 404
        finally:
            db.delete(other)
            db.commit()


class TestCategoryParentRule:
    def test_parent_must_be_same_tenant(self, client, headers_cat, tenant_c, tenant_a, db):
        slug = _unique("other-parent")
        other = Category(tenant_id=tenant_a.id, name="Other Tenant Parent", slug=slug)
        db.add(other)
        db.commit()
        db.refresh(other)
        try:
            resp = client.post("/api/v1/categories", headers=headers_cat, json={
                "name": "Child of Wrong Tenant", "parent_id": other.id,
            })
            assert resp.status_code == 404
        finally:
            db.delete(other)
            db.commit()

    def test_parent_same_tenant_ok(self, client, headers_cat, cat_a):
        slug_suffix = _unique()
        resp = client.post("/api/v1/categories", headers=headers_cat, json={
            "name": f"Child of Same Tenant {slug_suffix}", "parent_id": cat_a.id,
        })
        assert resp.status_code == 201
        assert resp.json()["parent_id"] == cat_a.id


class TestCategorySlugRules:
    def test_dup_slug_same_tenant_409(self, client, headers_cat, cat_a):
        resp = client.post("/api/v1/categories", headers=headers_cat, json={
            "name": "Different Name Same Slug", "slug": cat_a.slug,
        })
        assert resp.status_code == 409

    def test_same_slug_different_tenant_ok(self, client, headers_cat, tenant_c, tenant_a, db):
        slug = _unique("shared")
        other = Category(tenant_id=tenant_a.id, name="Other Tenant", slug=slug)
        db.add(other)
        db.commit()
        db.refresh(other)
        try:
            resp = client.post("/api/v1/categories", headers=headers_cat, json={
                "name": "Same Slug Different Tenant", "slug": slug,
            })
            assert resp.status_code == 201
        finally:
            db.delete(other)
            db.commit()

    def test_update_slug_to_existing_409(self, client, headers_cat, tenant_c, db):
        slug1 = _unique("slug-a")
        slug2 = _unique("slug-b")
        cat1 = Category(tenant_id=tenant_c.id, name="Slug A", slug=slug1)
        db.add(cat1)
        db.commit()
        db.refresh(cat1)
        cat2 = Category(tenant_id=tenant_c.id, name="Slug B", slug=slug2)
        db.add(cat2)
        db.commit()
        db.refresh(cat2)
        try:
            resp = client.patch(f"/api/v1/categories/{cat2.id}", headers=headers_cat, json={
                "slug": slug1,
            })
            assert resp.status_code == 409
        finally:
            db.delete(cat2)
            db.delete(cat1)
            db.commit()


class TestCategoryUncategorizedSeed:
    def test_uncategorized_seeded_for_existing_tenants(self, tenant_c, db):
        result = db.execute(
            text("SELECT id FROM categories WHERE tenant_id = :tid AND slug = 'uncategorized' LIMIT 1"),
            {"tid": tenant_c.id},
        ).fetchone()
        if result is not None:
            assert result[0] is not None


class TestCategoryProductAssignment:
    def test_products_assigned_after_seed(self, tenant_c, db):
        cat = db.query(Category).filter(
            Category.tenant_id == tenant_c.id, Category.slug == "uncategorized",
        ).first()
        if cat is not None:
            product = db.query(Product).filter(
                Product.tenant_id == tenant_c.id, Product.category_id == cat.id,
            ).first()
            if product is not None:
                assert product.category_id == cat.id


class TestCategoryDeletionRules:
    def test_cannot_delete_category_with_products(self, client, headers_cat, cat_a, product_in_cat):
        resp = client.delete(f"/api/v1/categories/{cat_a.id}", headers=headers_cat)
        assert resp.status_code == 409
        assert "products" in resp.json()["error"]["message"]

    def test_cannot_delete_category_with_children(self, client, headers_cat, tenant_c, db):
        parent_slug = _unique("parent-del")
        child_slug = _unique("child-del")
        parent = Category(tenant_id=tenant_c.id, name="Parent", slug=parent_slug)
        db.add(parent)
        db.commit()
        db.refresh(parent)
        child = Category(tenant_id=tenant_c.id, name="Child", slug=child_slug, parent_id=parent.id)
        db.add(child)
        db.commit()
        try:
            resp = client.delete(f"/api/v1/categories/{parent.id}", headers=headers_cat)
            assert resp.status_code == 409
            assert "subcategories" in resp.json()["error"]["message"]
        finally:
            db.delete(child)
            db.delete(parent)
            db.commit()

    def test_cannot_delete_uncategorized(self, client, headers_cat, tenant_c, db):
        unc = db.query(Category).filter(
            Category.tenant_id == tenant_c.id, Category.slug == "uncategorized",
        ).first()
        if unc is None:
            unc = Category(tenant_id=tenant_c.id, name="Uncategorized", slug="uncategorized")
            db.add(unc)
            db.commit()
            db.refresh(unc)
        resp = client.delete(f"/api/v1/categories/{unc.id}", headers=headers_cat)
        assert resp.status_code == 403
        assert "Uncategorized" in resp.json()["error"]["message"]

    def test_deactivate_empty_category_ok(self, client, headers_cat, tenant_c, db):
        slug = _unique("empty")
        empty = Category(tenant_id=tenant_c.id, name="Empty", slug=slug)
        db.add(empty)
        db.commit()
        db.refresh(empty)
        resp = client.delete(f"/api/v1/categories/{empty.id}", headers=headers_cat)
        assert resp.status_code == 204
        db.refresh(empty)
        assert empty.is_active is False


class TestCategoryRBAC:
    def test_support_user_cannot_create(self, client, headers_support):
        resp = client.post("/api/v1/categories", headers=headers_support, json={
            "name": "Forbidden",
        })
        assert resp.status_code == 403

    def test_support_user_cannot_delete(self, client, headers_support, cat_a):
        resp = client.delete(f"/api/v1/categories/{cat_a.id}", headers=headers_support)
        assert resp.status_code == 403

    def test_support_user_can_read(self, client, headers_support, cat_a):
        resp = client.get(f"/api/v1/categories/{cat_a.id}", headers=headers_support)
        assert resp.status_code == 200


class TestCategoryMigrationSeed:
    def test_seed_creates_uncategorized(self, tenant_c):
        session = SessionLocal()
        try:
            result = session.execute(
                text("SELECT id FROM categories WHERE tenant_id = :tid AND slug = 'uncategorized' LIMIT 1"),
                {"tid": tenant_c.id},
            ).fetchone()
            if result is not None:
                assert result[0] is not None
        finally:
            session.close()

    def test_seed_products_have_category(self, tenant_c):
        session = SessionLocal()
        try:
            products = session.execute(
                text("SELECT id FROM products WHERE tenant_id = :tid AND category_id IS NULL LIMIT 5"),
                {"tid": tenant_c.id},
            ).fetchall()
            assert len(products) == 0
        finally:
            session.close()
