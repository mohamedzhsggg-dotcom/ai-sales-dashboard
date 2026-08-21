"""Tests for post-product resolution and post mappings API."""

from app.models import PostProductMapping, Product


class TestPostMappingAPI:
    def test_create_mapping(self, db, tenant_a, client, auth_headers):
        product = Product(
            tenant_id=tenant_a.id, name="Mapping Product", price=1500,
            stock=10, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.commit()

        resp = client.post(
            "/api/v1/post-mappings",
            json={"platform": "facebook", "post_id": "fb_post_123", "product_id": product.id},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["platform"] == "facebook"
        assert data["post_id"] == "fb_post_123"
        assert data["product_id"] == product.id

    def test_duplicate_mapping_rejected(self, db, tenant_a, client, auth_headers):
        product = Product(
            tenant_id=tenant_a.id, name="Dup Product", price=1000,
            stock=5, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.commit()

        client.post(
            "/api/v1/post-mappings",
            json={"platform": "facebook", "post_id": "dup_post", "product_id": product.id},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/v1/post-mappings",
            json={"platform": "facebook", "post_id": "dup_post", "product_id": product.id},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    def test_list_mappings(self, db, tenant_a, client, auth_headers):
        product = Product(
            tenant_id=tenant_a.id, name="List Product", price=1000,
            stock=5, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.flush()

        mapping = PostProductMapping(
            tenant_id=tenant_a.id, platform="instagram", post_id="ig_post_1", product_id=product.id,
        )
        db.add(mapping)
        db.commit()

        resp = client.get("/api/v1/post-mappings", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_delete_mapping(self, db, tenant_a, client, auth_headers):
        mapping = PostProductMapping(
            tenant_id=tenant_a.id, platform="facebook", post_id="del_post",
        )
        db.add(mapping)
        db.commit()
        mapping_id = mapping.id

        resp = client.delete(f"/api/v1/post-mappings/{mapping_id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_resolve_post(self, db, tenant_a, client, auth_headers):
        product = Product(
            tenant_id=tenant_a.id, name="Resolve Product", price=2000,
            stock=8, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.flush()

        mapping = PostProductMapping(
            tenant_id=tenant_a.id, platform="facebook", post_id="resolve_post", product_id=product.id,
        )
        db.add(mapping)
        db.commit()

        resp = client.get(
            "/api/v1/resolve-post?platform=facebook&post_id=resolve_post",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert data["product_id"] == product.id
        assert data["product_name"] == "Resolve Product"

    def test_resolve_unknown_post(self, db, tenant_a, client, auth_headers):
        resp = client.get(
            "/api/v1/resolve-post?platform=facebook&post_id=unknown",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is False

    def test_filter_by_platform(self, db, tenant_a, client, auth_headers):
        product = Product(
            tenant_id=tenant_a.id, name="Filter Product", price=1000,
            stock=5, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.flush()

        db.add(PostProductMapping(tenant_id=tenant_a.id, platform="facebook", post_id="fb1", product_id=product.id))
        db.add(PostProductMapping(tenant_id=tenant_a.id, platform="instagram", post_id="ig1", product_id=product.id))
        db.commit()

        resp = client.get("/api/v1/post-mappings?platform=facebook", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(m["platform"] == "facebook" for m in items)

    def test_tenant_isolation(self, db, tenant_a, client, auth_headers):
        product = Product(
            tenant_id=tenant_a.id, name="Iso Product", price=1000,
            stock=5, status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.flush()

        db.add(PostProductMapping(tenant_id=tenant_a.id, platform="facebook", post_id="iso_post", product_id=product.id))
        db.commit()

        resp = client.get("/api/v1/post-mappings", headers=auth_headers)
        items = resp.json()["items"]
        assert all(m["tenant_id"] == tenant_a.id for m in items)
