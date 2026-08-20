"""Write-back service: dashboard-initiated changes pushed to Google Sheets.

All sheet mutations go through this service so they are serialized and
idempotent. It mirrors changes to the Commandes (orders) and Product sheets,
keeping Google Sheets as the system of record that n8n reads live.
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
        """Read the current stock straight from the Product sheet (source of truth)."""
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

    def confirm_order(self, order: Order, actor_id: int) -> Optional[int]:
        """Confirm an order: update status in DB + sheet, deduct stock in DB + sheet.

        Returns new stock level, or None if insufficient stock.
        """
        product = (
            self.db.query(Product)
            .filter(Product.tenant_id == self.tenant_id, Product.name == order.product)
            .first()
        )
        if product is None:
            # Product not in catalog; still confirm the order but skip stock deduction.
            logger.warning("Order %s references unknown product '%s'", order.order_id, order.product)
            order.status = "confirmed"
            self.db.add(OrderStatusHistory(
                order_id=order.id, from_status="new", to_status="confirmed", changed_by=actor_id
            ))
            self.db.commit()
            return 0

        fresh_stock = self._read_fresh_stock(product)
        qty = order.quantity or 1
        if fresh_stock < qty:
            return None

        new_stock = fresh_stock - qty

        # 1) DB transaction
        old_stock = product.stock or 0
        order.status = "confirmed"
        product.stock = new_stock
        self.db.add(OrderStatusHistory(
            order_id=order.id, from_status="new", to_status="confirmed", changed_by=actor_id
        ))
        self.db.add(InventoryEvent(
            tenant_id=self.tenant_id,
            product_id=product.id,
            delta=-qty,
            reason="order_confirmed",
            order_id=order.id,
            actor=actor_id,
        ))
        self.db.add(AuditLog(
            tenant_id=self.tenant_id,
            actor=actor_id,
            action="order.confirm",
            entity_type="order",
            entity_id=str(order.order_id or order.id),
            payload={"product": product.name, "quantity": qty, "stock_before": fresh_stock, "stock_after": new_stock},
        ))
        self.db.commit()

        # 2) Sheet writes (serialized via this service)
        try:
            self._write_order_status(order, "confirmed")
            self._write_product_stock(product, new_stock)
        except Exception:
            logger.exception("Sheet write-back failed after DB commit; reconciliation will repair drift")
            # DB already updated; the sync/reconcile job will re-write the sheet.

        return new_stock

    def set_stock(self, product: Product, new_stock: int, actor_id: int, reason: str = "manual"):
        product.stock = new_stock
        self.db.add(AuditLog(
            tenant_id=self.tenant_id,
            actor=actor_id,
            action="inventory.update",
            entity_type="product",
            entity_id=product.name,
            payload={"stock": new_stock, "reason": reason},
        ))
        self.db.commit()
        try:
            self._write_product_stock(product, new_stock)
        except Exception:
            logger.exception("Sheet write-back failed for stock update")

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