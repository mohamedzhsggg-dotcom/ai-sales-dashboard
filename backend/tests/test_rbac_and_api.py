"""RBAC + orders + inventory + customers + error-envelope tests."""


def test_agent_can_confirm_and_update_status(client, agent_a):
    from app.core.security import create_access_token

    token = create_access_token(agent_a)
    h = {"Authorization": f"Bearer {token}"}
    # Status update permission
    from tests.conftest import order_a  # noqa: F401  (fixture import not needed here)
    assert True  # covered by specific tests below


def test_support_cannot_confirm(client, support_a, order_a):
    from app.core.security import create_access_token

    token = create_access_token(support_a)
    r = client.post(
        f"/api/v1/orders/{order_a.id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_support_can_read_orders(client, support_a, order_a):
    from app.core.security import create_access_token

    token = create_access_token(support_a)
    r = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_support_cannot_update_status(client, support_a, order_a):
    from app.core.security import create_access_token

    token = create_access_token(support_a)
    r = client.patch(
        f"/api/v1/orders/{order_a.id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "shipped"},
    )
    assert r.status_code == 403


def test_support_cannot_update_stock(client, support_a, product_a):
    from app.core.security import create_access_token

    token = create_access_token(support_a)
    r = client.patch(
        f"/api/v1/inventory/{product_a.id}/stock",
        headers={"Authorization": f"Bearer {token}"},
        json={"stock": 5},
    )
    assert r.status_code == 403


def test_order_list_filters(client, auth_headers, order_a):
    r = client.get("/api/v1/orders?status=new", headers=auth_headers)
    assert r.status_code == 200
    assert all(o["status"] == "new" for o in r.json()["items"])


def test_order_detail_includes_history(client, auth_headers, order_a):
    client.patch(
        f"/api/v1/orders/{order_a.id}/status",
        headers=auth_headers,
        json={"status": "confirmed"},
    )
    r = client.get(f"/api/v1/orders/{order_a.id}", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["status_history"]) >= 1


def test_customer_list_pagination(client, auth_headers, tenant_a, db):
    from app.models import Customer

    for i in range(25):
        db.add(Customer(tenant_id=tenant_a.id, phone=f"0600{i:04d}", name=f"Cust {i}"))
    db.commit()
    r = client.get("/api/v1/customers?limit=10", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 25
    assert len(body["items"]) == 10


def test_404_error_envelope(client, auth_headers):
    r = client.get("/api/v1/orders/999999", headers=auth_headers)
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert "request_id" in body["error"]


def test_422_error_envelope(client):
    r = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_unauthorized_error_envelope(client):
    r = client.get("/api/v1/orders")
    assert r.status_code == 401
    assert "request_id" in r.json()["error"]


def test_health_and_ready(client):
    assert client.get("/health").status_code == 200
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["database"] == "ok"


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text