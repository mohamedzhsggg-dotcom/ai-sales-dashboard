"""StockService - the single authoritative writer of stock in PostgreSQL.

Core business logic lives here, purely against PostgreSQL. It never imports or
knows about Google Sheets. Every stock change records an InventoryEvent and
publishes a `stock.changed` domain event that the legacy Sheets subscriber may
mirror. Stock for simple products lives on `products.stock`; for variable
products it lives per-variant on `product_variants.stock`.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.events import STOCK_CHANGED, bus
from app.models import InventoryEvent, Product

logger = logging.getLogger(__name__)


class StockError(Exception):
    pass


class InsufficientStock(StockError):
    def __init__(self, product_id: Optional[int] = None, variant_id: Optional[int] = None,
                 available: int = 0, requested: int = 0):
        self.product_id = product_id
        self.variant_id = variant_id
        self.available = available
        self.requested = requested
        super().__init__("Insufficient stock")


def _resolve_target(db: Session, tenant_id: int, product_id=None, variant_id=None):
    """Return (target_row, is_variant). Raises StockError for missing/cross-tenant rows."""
    if variant_id is not None:
        from app.models import ProductVariant  # lazy: table added in a later migration

        variant = db.get(ProductVariant, variant_id)
        if variant is None or variant.tenant_id != tenant_id:
            raise StockError("Variant not found")
        return variant, True
    product = db.get(Product, product_id)
    if product is None or product.tenant_id != tenant_id:
        raise StockError("Product not found")
    return product, False


class StockService:
    def __init__(self, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id

    def current(self, product_id=None, variant_id=None) -> int:
        target, _ = _resolve_target(self.db, self.tenant_id, product_id, variant_id)
        return target.stock or 0

    def deduct(self, *, product_id=None, variant_id=None, quantity: int, reason: str,
               order_id=None, actor_id=None, metadata: Optional[dict] = None) -> int:
        if quantity <= 0:
            raise StockError("quantity must be positive")
        target, is_variant = _resolve_target(self.db, self.tenant_id, product_id, variant_id)
        if (target.stock or 0) < quantity:
            raise InsufficientStock(
                product_id=product_id if not is_variant else None,
                variant_id=variant_id if is_variant else None,
                available=target.stock or 0,
                requested=quantity,
            )
        new_stock = (target.stock or 0) - quantity
        target.stock = new_stock
        self._record(target, is_variant, -quantity, reason, order_id, actor_id, metadata, new_stock)
        return new_stock

    def add(self, *, product_id=None, variant_id=None, quantity: int, reason: str,
            order_id=None, actor_id=None, metadata: Optional[dict] = None) -> int:
        if quantity <= 0:
            raise StockError("quantity must be positive")
        target, is_variant = _resolve_target(self.db, self.tenant_id, product_id, variant_id)
        new_stock = (target.stock or 0) + quantity
        target.stock = new_stock
        self._record(target, is_variant, quantity, reason, order_id, actor_id, metadata, new_stock)
        return new_stock

    def set_manual(self, *, product_id=None, variant_id=None, new_stock: int, reason: str = "manual",
                   actor_id=None, metadata: Optional[dict] = None) -> int:
        if new_stock < 0:
            raise StockError("stock cannot be negative")
        target, is_variant = _resolve_target(self.db, self.tenant_id, product_id, variant_id)
        delta = new_stock - (target.stock or 0)
        target.stock = new_stock
        self._record(target, is_variant, delta, reason, None, actor_id, metadata, new_stock)
        return new_stock

    def _record(self, target, is_variant: bool, delta: int, reason: str,
                order_id, actor_id, metadata, new_stock: int) -> None:
        self.db.add(InventoryEvent(
            tenant_id=self.tenant_id,
            product_id=None if is_variant else target.id,
            product_variant_id=target.id if is_variant else None,
            delta=delta,
            reason=reason,
            order_id=order_id,
            actor=actor_id,
            data=metadata,
            qty_after=new_stock,
        ))
        self.db.flush()
        bus.publish(STOCK_CHANGED, {
            "tenant_id": self.tenant_id,
            "product_id": None if is_variant else target.id,
            "variant_id": target.id if is_variant else None,
            "stock": new_stock,
            "reason": reason,
        })