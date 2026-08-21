from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    config = Column(JSONB, nullable=False, server_default="{}")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="tenant")
    sheet_configs = relationship("SheetConfig", back_populates="tenant")


class SheetConfig(Base):
    __tablename__ = "sheet_configs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    sheet_type = Column(String(50), nullable=False)  # orders | products | posts
    spreadsheet_id = Column(String(255), nullable=False)
    tab = Column(String(255), nullable=False)
    column_map = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="sheet_configs")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="agent")  # admin | agent | support
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    refresh_token_hash = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    ip = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    phone = Column(String(50), index=True)
    name = Column(String(255))
    wilaya = Column(String(100))
    commune = Column(String(100))
    platform = Column(String(20))  # facebook | instagram
    sender_ids = Column(JSONB, nullable=False, server_default="{}")
    synced_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        sa.Index("ix_products_tenant_sku", "tenant_id", "sku", unique=True,
                 postgresql_where="sku IS NOT NULL"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    sheet_row = Column(Integer)
    name = Column(String(255), index=True)
    type = Column(String(20), default="simple", index=True)  # simple | variable
    sku = Column(String(100), index=True)
    description = Column(Text)
    status = Column(String(20), default="active", index=True)  # active | archived
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    price = Column(Integer)
    sizes = Column(JSONB, nullable=False, server_default="[]")
    colors = Column(JSONB, nullable=False, server_default="[]")
    image_url = Column(Text)
    stock = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=5)
    is_dashboard_managed = Column(Boolean, default=False, index=True)
    fb_post_id = Column(String(100))
    ig_post_id = Column(String(100))
    synced_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    variants = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )
    category = relationship("Category", foreign_keys=[category_id])


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        sa.Index("ix_variants_tenant_sku", "tenant_id", "sku", unique=True,
                 postgresql_where="sku IS NOT NULL"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(100), index=True)
    options = Column(JSONB, nullable=False, server_default="{}")
    price = Column(Integer)
    stock = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="variants")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "slug", name="uq_categories_tenant_slug"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    order_id = Column(String(100), index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    phone = Column(String(50), index=True)
    name = Column(String(255))
    wilaya = Column(String(100))
    commune = Column(String(100))
    product = Column(String(255))
    color = Column(String(100))
    size = Column(String(50))
    quantity = Column(Integer, default=1)
    price = Column(Integer)
    delivery_method = Column(String(50))  # home | office
    status = Column(String(50), default="new", index=True)
    source_channel = Column(String(20))
    sheet_row = Column(Integer)
    synced_hash = Column(String(64))
    subtotal = Column(Integer, default=0)
    shipping_fee = Column(Integer, default=0)
    total = Column(Integer, default=0)
    currency = Column(String(10), default="DZD")
    items_count = Column(Integer, default=1)
    notes = Column(Text)
    cancel_reason = Column(Text)
    cancel_note = Column(Text)
    has_return = Column(Boolean, default=False)
    # Courier / shipment fields
    courier_name = Column(String(50))
    tracking_number = Column(String(100), index=True)
    shipped_at = Column(DateTime)
    delivered_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")
    status_history = relationship("OrderStatusHistory", back_populates="order")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    shipments = relationship("Shipment", back_populates="order", cascade="all, delete-orphan")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    from_status = Column(String(50))
    to_status = Column(String(50), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"))
    changed_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="status_history")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name = Column(String(255))
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)
    variant_options = Column(JSONB)
    sku = Column(String(100))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)
    subtotal = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="items")


class Return(Base):
    __tablename__ = "returns"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    reason = Column(Text)
    refund_amount = Column(Integer, default=0)
    status = Column(String(50), default="pending", index=True)
    note = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)


class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    product_variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True, index=True)
    delta = Column(Integer, nullable=False)
    reason = Column(String(50))  # initial|restock|manual|adjustment|correction|order_confirmed|order_cancelled|order_returned|stock_take
    order_id = Column(Integer, ForeignKey("orders.id"))
    actor = Column(Integer, ForeignKey("users.id"))
    reference = Column(String(255))
    data = Column(JSONB)
    qty_after = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    actor = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(String(100))
    payload = Column(JSONB)
    ip = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    sheet_type = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    rows_processed = Column(Integer, default=0)
    status = Column(String(50), default="running")


class PostProductMapping(Base):
    __tablename__ = "post_product_mappings"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    fb_post_id = Column(String(100), index=True)
    ig_post_id = Column(String(100), index=True)
    product_name = Column(String(255))
    synced_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductMedia(Base):
    __tablename__ = "product_media"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    kind = Column(String(20), nullable=False)  # image | video
    url = Column(Text, nullable=False)
    filename = Column(String(255))
    mime_type = Column(String(100))
    size_bytes = Column(Integer)
    alt_text = Column(String(500))
    sort_order = Column(Integer, default=0)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    response_json = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


class StockCount(Base):
    __tablename__ = "stock_counts"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True, index=True)
    expected_quantity = Column(Integer, nullable=False)
    counted_quantity = Column(Integer, nullable=True)
    delta = Column(Integer, nullable=True)
    counted_by = Column(Integer, ForeignKey("users.id"))
    counted_at = Column(DateTime, nullable=True)
    note = Column(Text)
    reconciled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255))


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True)
    role = Column(String(50), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False, index=True)


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    courier_name = Column(String(50), nullable=False, index=True)
    tracking_number = Column(String(100), index=True)
    status = Column(String(50), default="pending", index=True)
    cod_amount = Column(Integer, default=0)
    shipping_fee = Column(Integer, default=0)
    delivery_method = Column(String(50))
    notes = Column(Text)
    raw_response = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    shipped_at = Column(DateTime)
    delivered_at = Column(DateTime)

    order = relationship("Order", back_populates="shipments")
    tracking_events = relationship("ShipmentTracking", back_populates="shipment", cascade="all, delete-orphan")


class ShipmentTracking(Base):
    __tablename__ = "shipment_tracking"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    description = Column(Text)
    location = Column(String(255))
    courier_raw_status = Column(String(100))
    recorded_at = Column(DateTime, default=datetime.utcnow)

    shipment = relationship("Shipment", back_populates="tracking_events")