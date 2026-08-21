"""Shared pytest fixtures.

Uses a dedicated `dashboard_test` database. The app engine is built from the
env DATABASE_URL at import time, so we set it before importing app modules.
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://dashboard:dashboard@localhost:5432/dashboard_test",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.database import Base, SessionLocal, engine
from app.models import Order, Product, Tenant, User


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db() -> Session:
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def tenant_a(db: Session) -> Tenant:
    t = db.query(Tenant).filter(Tenant.slug == "test-a").first()
    if not t:
        t = Tenant(name="Test A", slug="test-a", config={})
        db.add(t)
        db.commit()
        db.refresh(t)
    return t


@pytest.fixture()
def tenant_b(db: Session) -> Tenant:
    t = db.query(Tenant).filter(Tenant.slug == "test-b").first()
    if not t:
        t = Tenant(name="Test B", slug="test-b", config={})
        db.add(t)
        db.commit()
        db.refresh(t)
    return t


def _make_user(db: Session, tenant: Tenant, email: str, role: str) -> User:
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("Passw0rd!"),
            full_name=email,
            role=role,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    return u


@pytest.fixture()
def admin_a(db: Session, tenant_a: Tenant) -> User:
    return _make_user(db, tenant_a, "admin-a@example.com", "admin")


@pytest.fixture()
def agent_a(db: Session, tenant_a: Tenant) -> User:
    return _make_user(db, tenant_a, "agent-a@example.com", "agent")


@pytest.fixture()
def support_a(db: Session, tenant_a: Tenant) -> User:
    return _make_user(db, tenant_a, "support-a@example.com", "support")


@pytest.fixture()
def admin_b(db: Session, tenant_b: Tenant) -> User:
    return _make_user(db, tenant_b, "admin-b@example.com", "admin")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app_module())


def app_module():
    # Imported lazily so env DATABASE_URL is set before app/engine init.
    from app.main import app

    return app


@pytest.fixture()
def auth_headers(client: TestClient, admin_a: User) -> dict:
    token = create_access_token(admin_a)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def order_a(db: Session, tenant_a: Tenant) -> Order:
    o = Order(tenant_id=tenant_a.id, order_id="T-A-1", status="new", name="Alice", phone="0550000001", quantity=1)
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


@pytest.fixture()
def order_b(db: Session, tenant_b: Tenant) -> Order:
    o = Order(tenant_id=tenant_b.id, order_id="T-B-1", status="new", name="Bob", phone="0770000001", quantity=1)
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


@pytest.fixture()
def product_a(db: Session, tenant_a: Tenant) -> Product:
    p = Product(tenant_id=tenant_a.id, name="Test Product A", stock=10)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture()
def product_b(db: Session, tenant_b: Tenant) -> Product:
    p = Product(tenant_id=tenant_b.id, name="Test Product B", stock=5)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p