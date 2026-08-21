"""Product Media API tests.

Tests upload, invalid MIME, oversized file, primary exclusivity,
deletion, tenant isolation.
"""

import io
import uuid

import pytest

from app.database import Base, engine, SessionLocal
from app.models import Product, ProductMedia, Tenant, User
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
def tenant_m(db):
    t = db.query(Tenant).filter(Tenant.slug == "test-media").first()
    if not t:
        t = Tenant(name="Test Media", slug="test-media", config={})
        db.add(t)
        db.commit()
        db.refresh(t)
    yield t


@pytest.fixture()
def admin_m(tenant_m, db):
    email = "admin-media@example.com"
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            tenant_id=tenant_m.id, email=email,
            password_hash=hash_password("Passw0rd!"),
            full_name="Admin Media", role="admin",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    yield u


@pytest.fixture()
def headers_m(admin_m, client):
    token = create_access_token(admin_m)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def media_product(tenant_m, db):
    p = Product(tenant_id=tenant_m.id, name=f"Media Product {_uid()}", stock=5)
    db.add(p)
    db.commit()
    db.refresh(p)
    yield p
    db.delete(p)
    db.commit()


@pytest.fixture()
def existing_media(tenant_m, media_product, db):
    m = ProductMedia(
        tenant_id=tenant_m.id, product_id=media_product.id,
        kind="image", url="/media/test.jpg", filename="test.jpg",
        mime_type="image/jpeg", size_bytes=1024, is_primary=True,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    yield m
    db.delete(m)
    db.commit()


def _jpeg_bytes() -> bytes:
    """Minimal valid JPEG header for upload test."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


# ── Tests ────────────────────────────────────────────────────────────────────


class TestMediaUpload:
    def test_upload_image(self, client, headers_m, media_product):
        resp = client.post(
            f"/api/v1/products/{media_product.id}/media",
            headers=headers_m,
            files={"file": ("test.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
            data={"alt_text": "Test image"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["kind"] == "image"
        assert data["mime_type"] == "image/jpeg"
        assert data["alt_text"] == "Test image"

    def test_upload_invalid_mime(self, client, headers_m, media_product):
        resp = client.post(
            f"/api/v1/products/{media_product.id}/media",
            headers=headers_m,
            files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
        assert resp.status_code == 422

    def test_upload_oversized_file(self, client, headers_m, media_product):
        big_data = b"\x00" * (11 * 1024 * 1024)
        resp = client.post(
            f"/api/v1/products/{media_product.id}/media",
            headers=headers_m,
            files={"file": ("big.jpg", io.BytesIO(big_data), "image/jpeg")},
        )
        assert resp.status_code == 422


class TestMediaPrimary:
    def test_primary_exclusivity(self, client, headers_m, media_product, existing_media):
        resp = client.post(
            f"/api/v1/products/{media_product.id}/media",
            headers=headers_m,
            files={"file": ("second.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
            data={"is_primary": "true"},
        )
        assert resp.status_code == 201
        new_media_id = resp.json()["id"]

        from app.database import SessionLocal as SL
        s = SL()
        try:
            old = s.query(ProductMedia).filter(ProductMedia.id == existing_media.id).first()
            assert old.is_primary is False
            new = s.query(ProductMedia).filter(ProductMedia.id == new_media_id).first()
            assert new.is_primary is True
        finally:
            s.close()


class TestMediaUpdate:
    def test_update_alt_text(self, client, headers_m, media_product, existing_media):
        resp = client.patch(
            f"/api/v1/products/{media_product.id}/media/{existing_media.id}",
            headers=headers_m, json={"alt_text": "Updated alt"},
        )
        assert resp.status_code == 200
        assert resp.json()["alt_text"] == "Updated alt"


class TestMediaDelete:
    def test_delete_media(self, client, headers_m, media_product, existing_media):
        resp = client.delete(
            f"/api/v1/products/{media_product.id}/media/{existing_media.id}",
            headers=headers_m,
        )
        assert resp.status_code == 204


class TestMediaTenantIsolation:
    def test_cross_tenant_upload_404(self, client, headers_m, tenant_a, db):
        p = Product(tenant_id=tenant_a.id, name="Cross Tenant Media", stock=1)
        db.add(p)
        db.commit()
        db.refresh(p)
        try:
            resp = client.post(
                f"/api/v1/products/{p.id}/media",
                headers=headers_m,
                files={"file": ("test.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
            )
            assert resp.status_code == 404
        finally:
            db.delete(p)
            db.commit()

    def test_cross_tenant_list_empty(self, client, headers_m, media_product, tenant_a, db):
        m = ProductMedia(
            tenant_id=tenant_a.id, product_id=media_product.id,
            kind="image", url="/other.jpg", filename="other.jpg",
            mime_type="image/jpeg", is_primary=True,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        try:
            resp = client.get(f"/api/v1/products/{media_product.id}/media", headers=headers_m)
            assert resp.status_code == 200
            ids = [item["id"] for item in resp.json()]
            assert m.id not in ids
        finally:
            db.delete(m)
            db.commit()
