"""Sync worker: mirrors Google Sheets into PostgreSQL.

This is the read side. It polls the three sheets on a cadence, detects changes
by content-hash, and upserts rows into the database so the dashboard can query
fast, indexed data without hitting Google Sheets per request.

Write side (dashboard -> sheets) is handled by WritebackService, never here.
"""

import hashlib
import json
import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import Customer, Order, Product, SyncRun, Tenant
from app.services.sheets import SheetsClient, sheets_rows_to_dicts

logger = logging.getLogger(__name__)
settings = get_settings()

ORDERS_COLUMNS = {
    "order_id": "Order ID",
    "name": "name",
    "wilaya": "wilaya",
    "commune": "commune",
    "phone": "phone",
    "product": "product",
    "size": "size",
    "color": "color",
    "price": "price",
    "quantity": "quantity",
    "delivery_method": "delivery_method",
    "status": "status",
}

PRODUCTS_COLUMNS = {
    "name": "name",
    "price": "price",
    "sizes": "sizes",
    "colors": "colors",
    "image_url": "image_url",
    "stock": "stock",
    "fb_post_id": "facebook post id",
    "ig_post_id": "instagram post id",
}

POSTS_COLUMNS = {
    "fb_post_id": "facebook post id",
    "ig_post_id": "instagram post id",
    "product_name": "product name",
}


def _hash_row(values: list) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, default=str).encode()).hexdigest()


def _to_int(value) -> int | None:
    try:
        return int(float(str(value).replace("DA", "").replace("دج", "").strip()))
    except (TypeError, ValueError):
        return None


class SyncWorker:
    def __init__(self):
        self.sheets = SheetsClient()

    def run_orders_once(self, tenant: Tenant, db: Session) -> int:
        rows = self.sheets.read_all(settings.SHEETS_ORDERS_ID, settings.SHEETS_ORDERS_TAB)
        if len(rows) < 2:
            return 0
        header = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
        idx = {name: i for i, name in enumerate(header)}
        count = 0
        for row_index, row in enumerate(rows[1:], start=2):
            h = _hash_row(row)
            order_id = row[idx["Order ID"]] if "Order ID" in idx and len(row) > idx["Order ID"] else None
            if not order_id:
                continue
            phone = row[idx["phone"]] if "phone" in idx and len(row) > idx["phone"] else None

            customer = None
            if phone:
                customer = (
                    db.query(Customer)
                    .filter(Customer.tenant_id == tenant.id, Customer.phone == str(phone))
                    .first()
                )
                if customer is None:
                    customer = Customer(
                        tenant_id=tenant.id,
                        phone=str(phone),
                        name=row[idx["name"]] if "name" in idx and len(row) > idx["name"] else None,
                        wilaya=row[idx["wilaya"]] if "wilaya" in idx and len(row) > idx["wilaya"] else None,
                        commune=row[idx["commune"]] if "commune" in idx and len(row) > idx["commune"] else None,
                    )
                    db.add(customer)
                    db.flush()

            order = (
                db.query(Order)
                .filter(Order.tenant_id == tenant.id, Order.order_id == str(order_id))
                .first()
            )
            if order is None:
                order = Order(
                    tenant_id=tenant.id,
                    order_id=str(order_id),
                    customer_id=customer.id if customer else None,
                    sheet_row=row_index,
                    status="new",
                )
                db.add(order)
            if order.synced_hash == h:
                continue
            order.sheet_row = row_index
            order.synced_hash = h
            if customer:
                order.customer_id = customer.id
            for field, col in ORDERS_COLUMNS.items():
                if col in idx and len(row) > idx[col]:
                    value = row[idx[col]]
                    if field == "price":
                        order.price = _to_int(value)
                    elif field == "quantity":
                        order.quantity = _to_int(value) or 1
                    else:
                        setattr(order, field, value)
            # status default: sheet may not have the column yet
            if "status" not in idx or not order.status:
                order.status = "new"
            db.flush()
            count += 1
        db.commit()
        return count

    def run_products_once(self, tenant: Tenant, db: Session) -> int:
        rows = self.sheets.read_all(settings.SHEETS_PRODUCTS_ID, settings.SHEETS_PRODUCTS_TAB)
        if len(rows) < 2:
            return 0
        header = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
        idx = {name: i for i, name in enumerate(header)}
        count = 0
        for row_index, row in enumerate(rows[1:], start=2):
            h = _hash_row(row)
            name = row[idx["name"]] if "name" in idx and len(row) > idx["name"] else None
            if not name:
                continue
            product = (
                db.query(Product)
                .filter(Product.tenant_id == tenant.id, Product.name == str(name))
                .first()
            )
            if product is None:
                product = Product(tenant_id=tenant.id, name=str(name), sheet_row=row_index, stock=0)
                db.add(product)
            if product.synced_hash == h:
                continue
            product.sheet_row = row_index
            product.synced_hash = h
            for field, col in PRODUCTS_COLUMNS.items():
                if col in idx and len(row) > idx[col]:
                    value = row[idx[col]]
                    if field == "price":
                        product.price = _to_int(value)
                    elif field == "stock":
                        product.stock = _to_int(value) or 0
                    elif field in ("sizes", "colors"):
                        setattr(product, field, _parse_list(value))
                    else:
                        setattr(product, field, value)
            db.flush()
            count += 1
        db.commit()
        return count

    def run_posts_once(self, tenant: Tenant, db: Session) -> int:
        rows = self.sheets.read_all(settings.SHEETS_POSTS_ID, settings.SHEETS_POSTS_TAB)
        if len(rows) < 2:
            return 0
        header = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
        idx = {name: i for i, name in enumerate(header)}
        mapping = {}
        for row in rows[1:]:
            rec = {}
            for field, col in POSTS_COLUMNS.items():
                if col in idx and len(row) > idx[col]:
                    rec[field] = row[idx[col]]
            if rec.get("fb_post_id") or rec.get("ig_post_id"):
                mapping[rec.get("fb_post_id")] = rec.get("product_name")
                mapping[rec.get("ig_post_id")] = rec.get("product_name")
        # Store mapping on tenant config for the comment path to use
        tenant.config = {**(tenant.config or {}), "post_product_map": mapping}
        db.commit()
        return len(mapping)

    def run_all(self):
        with SessionLocal() as db:
            tenants = db.query(Tenant).filter(Tenant.is_active == True).all()  # noqa: E712
            for tenant in tenants:
                run = SyncRun(tenant_id=tenant.id, sheet_type="all")
                db.add(run)
                db.flush()
                processed = 0
                processed += self.run_orders_once(tenant, db)
                processed += self.run_products_once(tenant, db)
                processed += self.run_posts_once(tenant, db)
                run.rows_processed = processed
                run.status = "done"
                run.finished_at = datetime.utcnow()
                db.commit()
                logger.info("Synced tenant=%s rows=%s", tenant.slug, processed)

    def loop(self):
        logger.info("Sync worker started")
        while True:
            try:
                self.run_all()
            except Exception:
                logger.exception("Sync cycle failed")
            time.sleep(settings.SYNC_ORDERS_INTERVAL_SECONDS)


def _parse_list(value) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, list) else [text]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    SyncWorker().loop()