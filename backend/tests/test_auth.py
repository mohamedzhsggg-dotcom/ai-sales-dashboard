"""Auth tests: login, refresh, me, logout, disabled users, token types."""

import pytest


def test_login_success(client, admin_a):
    r = client.post("/api/v1/auth/login", json={"email": admin_a.email, "password": "Passw0rd!"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_bad_password(client, admin_a):
    r = client.post("/api/v1/auth/login", json={"email": admin_a.email, "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_login_unknown_user(client):
    r = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Passw0rd!"})
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_returns_user(client, admin_a):
    token = __import__("app.core.security", fromlist=["create_access_token"]).create_access_token(admin_a)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == admin_a.email
    assert r.json()["tenant_id"] == admin_a.tenant_id


def test_disabled_user_cannot_login(client, admin_a, db):
    admin_a.is_active = False
    db.commit()
    try:
        r = client.post("/api/v1/auth/login", json={"email": admin_a.email, "password": "Passw0rd!"})
        assert r.status_code == 403
    finally:
        admin_a.is_active = True
        db.commit()


def test_refresh_flow(client, admin_a):
    login = client.post("/api/v1/auth/login", json={"email": admin_a.email, "password": "Passw0rd!"})
    refresh_token = login.json()["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_access_token_rejected_as_refresh(client, admin_a):
    from app.core.security import create_access_token

    access = create_access_token(admin_a)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401


def test_logout_revokes_refresh(client, admin_a):
    login = client.post("/api/v1/auth/login", json={"email": admin_a.email, "password": "Passw0rd!"})
    refresh_token = login.json()["refresh_token"]
    assert client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token}).status_code == 200
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 401


def test_setup_blocked_when_users_exist(client):
    r = client.post("/api/v1/auth/setup", json={"email": "x@y.z", "password": "Passw0rd!"})
    assert r.status_code == 400