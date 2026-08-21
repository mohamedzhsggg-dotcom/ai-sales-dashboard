"""SHEETS_COMPAT_MODE=false must leave all business functionality fully
operational using PostgreSQL only, even for sheet-backed records."""

import pytest

from app.config import get_settings
from app.models import InventoryEvent, Order


@pytest.fixture()
def _sheet_backed_product(db, tenant_a):
    from app.models import Product

    p = Product(
        tenant_id=tenant_a.id,
        name="Sheet-Backed Widget",
        sheet_row=2,               # looks like a legacy sheet product
        is_dashboard_managed=False,
        type="simple",
        stock=50,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_legacy_guard_is_noop_when_compat_off(monkeypatch, db, tenant_a, _sheet_backed_product):
    from app.services.legacy.guard import legacy_confirm_guard

    monkeypatch.setenv("SHEETS_COMPAT_MODE", "false")
    get_settings.cache_clear()
    try:
        # Would try to read Google Sheets if compat were on; must be a no-op now.
        legacy_confirm_guard(db, tenant_a.id, [{"product_id": _sheet_backed_product.id, "quantity": 999}])
    finally:
        get_settings.cache_clear()


def test_confirm_flow_works_pg_only_when_compat_off(monkeypatch, client, db, admin_a, tenant_a, _sheet_backed_product):
    from app.core.security import create_access_token

    order = Order(
        tenant_id=tenant_a.id,
        order_id="COMPAT-OFF-1",
        product_id=_sheet_backed_product.id,
        product="Sheet-Backed Widget",
        name="Compat",
        phone="0551111111",
        quantity=2,
        price=100,
        status="new",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    monkeypatch.setenv("SHEETS_COMPAT_MODE", "false")
    get_settings.cache_clear()
    try:
        token = create_access_token(admin_a)
        r = client.post(
            f"/api/v1/orders/{order.id}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["stock_after"] == 48
    finally:
        get_settings.cache_clear()

    db.refresh(_sheet_backed_product)
    assert _sheet_backed_product.stock == 48
    events = db.query(InventoryEvent).filter(
        InventoryEvent.product_id == _sheet_backed_product.id
    ).all()
    assert sum(e.delta for e in events) == -2


def test_stock_update_works_pg_only_when_compat_off(monkeypatch, client, admin_a, tenant_a, _sheet_backed_product):
    from app.core.security import create_access_token

    monkeypatch.setenv("SHEETS_COMPAT_MODE", "false")
    get_settings.cache_clear()
    try:
        token = create_access_token(admin_a)
        r = client.patch(
            f"/api/v1/inventory/{_sheet_backed_product.id}/stock",
            headers={"Authorization": f"Bearer {token}"},
            json={"quantity": 33, "reason": "set"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["stock"] == 33
    finally:
        get_settings.cache_clear()