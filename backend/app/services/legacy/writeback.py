"""Legacy write-back: dashboard-initiated changes mirrored to Google Sheets.

All sheet mutations go through this service so they are serialized and
idempotent. It is part of the temporary legacy compatibility layer. Only two
cells are ever written: the order `status` cell and the product `stock` cell.
PostgreSQL is the source of truth; these are mirrors for the existing n8n
system only.
"""

import hashlib
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditLog, InventoryEvent, Order, OrderStatusHistory, Product
from app.services.sheets import COLUMNS_ORDERS, COLUMNS_PRODUCTS, SheetsClient

logger = logging.getLogger(__name__)
settings = get_settings()


class WritebackService:
    def __init__(self, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self.sheets = SheetsClient()

    def _order_column_index(self, column: str) -> int:
        return COLUMNS_ORDERS.index(column)

    def _product_column_index(self, column: str) -> int:
        return COLUMNS_PRODUCTS.index(column)

    def _read_fresh_stock(self, product: Product) -> int:
        """Read the current stock straight from the Product sheet (legacy read)."""
        rows = self.sheets.read_all(settings.SHEETS_PRODUCTS_ID, settings.SHEETS_PRODUCTS_TAB)
        header = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
        stock_idx = header.index("stock") if "stock" in header else None
        if stock_idx is None:
            raise RuntimeError("Product sheet has no 'stock' column")
        row = rows[product.sheet_row] if product.sheet_row and product.sheet_row < len(rows) else None
        if row is None:
            raise RuntimeError("Product sheet row not found")
        try:
            return int(float(row[stock_idx] or 0))
        except (ValueError, IndexError):
            return 0

    def _write_order_status(self, order: Order, status: str):
        if not order.sheet_row:
            logger.warning("Order %s has no sheet_row; cannot write status to sheet", order.order_id)
            return
        col = self._order_column_index("status")
        range_name = f"{settings.SHEETS_ORDERS_TAB}!{self._col_letter(col)}{order.sheet_row}"
        self.sheets.write_range(settings.SHEETS_ORDERS_ID, range_name, [[status]])

    def _write_product_stock(self, product: Product, stock: int):
        if not product.sheet_row:
            logger.warning("Product %s has no sheet_row; cannot write stock to sheet", product.name)
            return
        col = self._product_column_index("stock")
        range_name = f"{settings.SHEETS_PRODUCTS_TAB}!{self._col_letter(col)}{product.sheet_row}"
        self.sheets.write_range(settings.SHEETS_PRODUCTS_ID, range_name, [[stock]])

    @staticmethod
    def _col_letter(index: int) -> str:
        result = ""
        index += 1
        while index:
            index, rem = divmod(index - 1, 26)
            result = chr(65 + rem) + result
        return result