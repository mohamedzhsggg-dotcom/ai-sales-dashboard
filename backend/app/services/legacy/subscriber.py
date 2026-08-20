"""Legacy Sheets subscriber - mirrors a minimal set of cells from PostgreSQL.

Registered from `app.main` (the documented deletion point). Removable entirely
with the legacy layer; core business logic never publishes directly to Sheets.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.core.events import ORDER_STATUS_CHANGED, STOCK_CHANGED, bus

logger = logging.getLogger(__name__)


def _on_order_status_changed(event: str, payload: dict) -> None:
    if not get_settings().SHEETS_COMPAT_MODE:
        return
    from app.database import SessionLocal
    from app.models import Order
    from app.services.legacy.sheet_adapter import SheetAdapter

    with SessionLocal() as db:
        order = db.get(Order, payload.get("order_id"))
        if order is None:
            return
        SheetAdapter(db, order.tenant_id).update_order_status(order, payload.get("status"))


def _on_stock_changed(event: str, payload: dict) -> None:
    if not get_settings().SHEETS_COMPAT_MODE:
        return
    from app.database import SessionLocal
    from app.models import Product
    from app.services.legacy.sheet_adapter import SheetAdapter

    with SessionLocal() as db:
        product = db.get(Product, payload.get("product_id"))
        if product is None:
            return
        SheetAdapter(db, product.tenant_id).update_product_stock(product, payload.get("stock"))


def register_legacy_subscribers() -> None:
    bus.subscribe(ORDER_STATUS_CHANGED, _on_order_status_changed)
    bus.subscribe(STOCK_CHANGED, _on_stock_changed)