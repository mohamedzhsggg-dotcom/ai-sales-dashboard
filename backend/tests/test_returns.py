"""Tests for returns API."""

from app.models import Order, OrderItem, Product, Return


def _create_order_with_item(db, tenant):
    product = Product(
        tenant_id=tenant.id, name="Return Test Product", price=2000,
        stock=5, status="active", sizes="[]", colors="[]",
    )
    db.add(product)
    db.flush()

    order = Order(
        tenant_id=tenant.id, phone="0555000111", name="Return Tester",
        wilaya="Alger", commune="Bab Ezzouar", product="Return Test Product",
        quantity=2, price=2000, status="delivered",
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        tenant_id=tenant.id, order_id=order.id, product_id=product.id,
        product_name="Return Test Product", quantity=2, unit_price=2000, subtotal=4000,
    )
    db.add(item)
    db.commit()

    return order, item, product


class TestReturnsAPI:
    def test_create_return(self, db, tenant_a, client, auth_headers):
        order, item, product = _create_order_with_item(db, tenant_a)

        resp = client.post(
            f"/api/v1/returns?order_id={order.id}",
            json={"order_item_id": item.id, "quantity": 1, "reason": "Wrong size"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["quantity"] == 1

    def test_list_returns(self, db, tenant_a, client, auth_headers):
        order, item, _ = _create_order_with_item(db, tenant_a)

        client.post(
            f"/api/v1/returns?order_id={order.id}",
            json={"order_item_id": item.id, "quantity": 1},
            headers=auth_headers,
        )
        resp = client.get("/api/v1/returns", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_approve_return_restores_stock(self, db, tenant_a, client, auth_headers):
        order, item, product = _create_order_with_item(db, tenant_a)
        initial_stock = product.stock

        resp = client.post(
            f"/api/v1/returns?order_id={order.id}",
            json={"order_item_id": item.id, "quantity": 2},
            headers=auth_headers,
        )
        return_id = resp.json()["id"]

        resp = client.patch(f"/api/v1/returns/{return_id}/approve", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        db.refresh(product)
        assert product.stock == initial_stock + 2

    def test_reject_return(self, db, tenant_a, client, auth_headers):
        order, item, _ = _create_order_with_item(db, tenant_a)

        resp = client.post(
            f"/api/v1/returns?order_id={order.id}",
            json={"order_item_id": item.id, "quantity": 1, "reason": "Changed mind"},
            headers=auth_headers,
        )
        return_id = resp.json()["id"]

        resp = client.patch(
            f"/api/v1/returns/{return_id}/reject",
            json={"note": "Not eligible"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_cannot_return_new_order(self, db, tenant_a, client, auth_headers):
        product = Product(
            tenant_id=tenant_a.id, name="P", price=100, stock=5,
            status="active", sizes="[]", colors="[]",
        )
        db.add(product)
        db.flush()
        order = Order(
            tenant_id=tenant_a.id, phone="0555", name="T", wilaya="Alger",
            product="P", quantity=1, price=100, status="new",
        )
        db.add(order)
        db.commit()

        resp = client.post(
            f"/api/v1/returns?order_id={order.id}",
            json={"quantity": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    def test_cannot_approve_nonexistent_return(self, db, tenant_a, client, auth_headers):
        resp = client.patch("/api/v1/returns/99999/approve", headers=auth_headers)
        assert resp.status_code == 404

    def test_double_approve_rejected(self, db, tenant_a, client, auth_headers):
        order, item, _ = _create_order_with_item(db, tenant_a)

        resp = client.post(
            f"/api/v1/returns?order_id={order.id}",
            json={"order_item_id": item.id, "quantity": 1},
            headers=auth_headers,
        )
        return_id = resp.json()["id"]

        client.patch(f"/api/v1/returns/{return_id}/approve", headers=auth_headers)
        resp = client.patch(f"/api/v1/returns/{return_id}/approve", headers=auth_headers)
        assert resp.status_code == 409
