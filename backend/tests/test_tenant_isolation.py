"""Tenant isolation: cross-tenant access must be impossible.

These tests are the security core: a user from tenant A must never see or
mutate tenant B data, regardless of IDs passed.
"""


def test_orders_are_tenant_scoped(client, auth_headers, order_a, order_b):
    r = client.get("/api/v1/orders", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    ids = [o["id"] for o in body["items"]]
    assert order_a.id in ids
    assert order_b.id not in ids, "tenant B order leaked into tenant A list"


def test_cannot_fetch_other_tenant_order(client, auth_headers, order_b):
    r = client.get(f"/api/v1/orders/{order_b.id}", headers=auth_headers)
    assert r.status_code == 404


def test_cannot_update_other_tenant_order_status(client, auth_headers, order_b):
    r = client.patch(
        f"/api/v1/orders/{order_b.id}/status",
        headers=auth_headers,
        json={"status": "shipped"},
    )
    assert r.status_code == 404


def test_cannot_confirm_other_tenant_order(client, auth_headers, order_b):
    r = client.post(f"/api/v1/orders/{order_b.id}/confirm", headers=auth_headers)
    assert r.status_code == 404


def test_customers_are_tenant_scoped(client, auth_headers, tenant_a, tenant_b, db):
    from app.models import Customer

    db.add(Customer(tenant_id=tenant_a.id, phone="0100000001", name="A Customer"))
    db.add(Customer(tenant_id=tenant_b.id, phone="0100000002", name="B Customer"))
    db.commit()

    r = client.get("/api/v1/customers", headers=auth_headers)
    assert r.status_code == 200
    phones = [c["phone"] for c in r.json()["items"]]
    assert "0100000001" in phones
    assert "0100000002" not in phones, "tenant B customer leaked"


def test_cannot_fetch_other_tenant_customer(client, auth_headers, tenant_b, db):
    from app.models import Customer

    c = Customer(tenant_id=tenant_b.id, phone="0100000003", name="B Customer")
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.get(f"/api/v1/customers/{c.id}", headers=auth_headers)
    assert r.status_code == 404


def test_products_are_tenant_scoped(client, auth_headers, product_a, product_b):
    r = client.get("/api/v1/products", headers=auth_headers)
    assert r.status_code == 200
    names = [p["name"] for p in r.json()["items"]]
    assert product_a.name in names
    assert product_b.name not in names, "tenant B product leaked"


def test_cannot_fetch_other_tenant_product(client, auth_headers, product_b):
    r = client.get(f"/api/v1/products/{product_b.id}", headers=auth_headers)
    assert r.status_code == 404


def test_inventory_is_tenant_scoped(client, auth_headers, product_a, product_b):
    r = client.get("/api/v1/inventory", headers=auth_headers)
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert product_a.name in names
    assert product_b.name not in names, "tenant B inventory leaked"


def test_cannot_update_other_tenant_stock(client, auth_headers, product_b):
    r = client.patch(f"/api/v1/inventory/{product_b.id}/stock", headers=auth_headers, json={"quantity": 999, "reason": "set"})
    assert r.status_code == 404


def test_dashboard_stats_are_tenant_scoped(client, auth_headers, order_a, order_b):
    r = client.get("/api/v1/dashboard/stats", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    ids = [o["id"] for o in body["recent_orders"]]
    assert order_a.id in ids
    assert order_b.id not in ids, "tenant B order leaked into dashboard"


def test_audit_logs_are_tenant_scoped(client, auth_headers, tenant_a, tenant_b, db):
    from app.models import AuditLog

    db.add(AuditLog(tenant_id=tenant_a.id, action="test.a"))
    db.add(AuditLog(tenant_id=tenant_b.id, action="test.b"))
    db.commit()

    r = client.get("/api/v1/audit-logs", headers=auth_headers)
    assert r.status_code == 200
    actions = [a["action"] for a in r.json()]
    assert "test.a" in actions
    assert "test.b" not in actions, "tenant B audit log leaked"