"""SheetAdapter - the ONLY write path to Google Sheets (legacy, removable).

Mirrors exactly two cells that the existing n8n system reads:
- the order `status` cell
- the product `stock` cell (dashboard-managed simple products only)

No new business logic, columns, tables, tabs or workflows are ever added here.
Inert when SHEETS_COMPAT_MODE is False.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.models import Order, Product

logger = logging.getLogger(__name__)


class SheetAdapter:
    def __init__(self, db, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self._enabled = get_settings().SHEETS_COMPAT_MODE

    @property
    def enabled(self) -> bool:
        return self._enabled

    def update_order_status(self, order: Order, status: str) -> None:
        if not self._enabled or not order.sheet_row:
            return
        try:
            from app.services.legacy.writeback import WritebackService

            WritebackService(self.db, self.tenant_id)._write_order_status(order, status)
        except Exception:
            logger.exception("Legacy sheet status mirror failed for order %s", getattr(order, "order_id", order.id))

    def update_product_stock(self, product: Product, stock: int) -> None:
        if not self._enabled:
            return
        if product.is_dashboard_managed and product.type == "simple" and product.sheet_row:
            try:
                from app.services.legacy.writeback import WritebackService

                WritebackService(self.db, self.tenant_id)._write_product_stock(product, stock)
            except Exception:
                logger.exception("Legacy sheet stock mirror failed for product %s", getattr(product, "name", product.id))