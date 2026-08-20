"""Idempotency: replaying an Idempotency-Key must not re-execute."""

IDEM_KEY = "test-idem-status-1"


def test_idempotent_status_update(client, auth_headers, order_a):
    h = {**auth_headers, "Idempotency-Key": IDEM_KEY}
    r1 = client.patch(f"/api/v1/orders/{order_a.id}/status", headers=h, json={"status": "confirmed"})
    assert r1.status_code == 200
    assert r1.json()["status"] == "confirmed"

    # Replay with same key and a different desired status: stored response wins.
    r2 = client.patch(f"/api/v1/orders/{order_a.id}/status", headers=h, json={"status": "shipped"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "confirmed", "replay must return stored response, not re-execute"


def test_different_key_executes(client, auth_headers, order_a):
    r1 = client.patch(
        f"/api/v1/orders/{order_a.id}/status",
        headers={**auth_headers, "Idempotency-Key": "idem-a"},
        json={"status": "confirmed"},
    )
    r2 = client.patch(
        f"/api/v1/orders/{order_a.id}/status",
        headers={**auth_headers, "Idempotency-Key": "idem-b"},
        json={"status": "shipped"},
    )
    assert r1.json()["status"] == "confirmed"
    assert r2.json()["status"] == "shipped", "a new key must execute normally"


def test_no_key_executes_normally(client, auth_headers, order_a):
    r = client.patch(f"/api/v1/orders/{order_a.id}/status", headers=auth_headers, json={"status": "confirmed"})
    assert r.status_code == 200


def test_get_requests_ignore_idempotency(client, auth_headers, order_a):
    # Idempotency-Key on a GET must not interfere.
    r = client.get(f"/api/v1/orders/{order_a.id}", headers={**auth_headers, "Idempotency-Key": IDEM_KEY})
    assert r.status_code == 200