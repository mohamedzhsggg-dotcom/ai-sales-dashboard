"""Legacy confirm guard: fresh sheet-stock check for UNMANAGED simple products.

Only active when SHEETS_COMPAT_MODE is on. Keeps today's oversell protection
for products whose stock is still written by the n8n workflow directly in the
sheet. Lives in the removable legacy layer - core never reads sheets.
"""

from __future__ import annotations

from app.config import get_settings
from app.models import Product


def legacy_confirm_guard(db, tenant_id: int, items: list[dict]) -> None:
    """items: list of {product_id, variant_id|None, quantity}.

    Raises app.services.stock.InsufficientStock when a legacy (unmanaged,
    simple, sheet-backed) product's fresh sheet stock is below the requested
    quantity. No-op when SHEETS_COMPAT_MODE is off.
    """
    if not get_settings().SHEETS_COMPAT_MODE:
        return
    from app.services.legacy.writeback import WritebackService
    from app.services.stock import InsufficientStock

    wb = WritebackService(db, tenant_id)
    for item in items:
        if item.get("variant_id"):
            continue  # variants are PostgreSQL-only, never present in sheets
        product = db.get(Product, item["product_id"])
        if product is None or product.tenant_id != tenant_id:
            continue
        if product.is_dashboard_managed or product.type != "simple" or not product.sheet_row:
            continue
        fresh = wb._read_fresh_stock(product)
        if fresh < item["quantity"]:
            raise InsufficientStock(product_id=product.id, available=fresh, requested=item["quantity"])