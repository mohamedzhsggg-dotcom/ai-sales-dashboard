from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class SetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    tenant_id: int

    class Config:
        from_attributes = True


# ---------- Orders ----------
class OrderOut(BaseModel):
    id: int
    order_id: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    wilaya: Optional[str] = None
    commune: Optional[str] = None
    product: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[int] = None
    delivery_method: Optional[str] = None
    status: str
    source_channel: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderDetail(OrderOut):
    customer_id: Optional[int] = None
    sheet_row: Optional[int] = None
    status_history: list[Any] = []


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="new | confirmed | shipped | delivered | cancelled")
    note: Optional[str] = None


class ConfirmOrderResponse(BaseModel):
    order: OrderOut
    stock_after: int
    message: str


class OrderListResponse(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    limit: int


# ---------- Customers ----------
class CustomerOut(BaseModel):
    id: int
    phone: Optional[str] = None
    name: Optional[str] = None
    wilaya: Optional[str] = None
    commune: Optional[str] = None
    platform: Optional[str] = None
    created_at: datetime
    order_count: Optional[int] = 0

    class Config:
        from_attributes = True


class CustomerDetail(CustomerOut):
    orders: list[OrderOut] = []


class CustomerListResponse(BaseModel):
    items: list[CustomerOut]
    total: int
    page: int
    limit: int


# ---------- Products / Inventory ----------
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field("simple", pattern="^(simple|variable)$")
    sku: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    status: str = Field("active", pattern="^(active|archived)$")
    category_id: Optional[int] = None
    price: Optional[int] = None
    sizes: list[Any] = []
    colors: list[Any] = []
    image_url: Optional[str] = None
    stock: int = Field(0, ge=0)
    low_stock_threshold: int = Field(5, ge=0)
    is_dashboard_managed: bool = False


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, pattern="^(simple|variable)$")
    sku: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|archived)$")
    category_id: Optional[int] = None
    price: Optional[int] = None
    sizes: Optional[list[Any]] = None
    colors: Optional[list[Any]] = None
    image_url: Optional[str] = None
    stock: Optional[int] = Field(None, ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    is_dashboard_managed: Optional[bool] = None


class ProductVariantOut(BaseModel):
    id: int
    tenant_id: int
    product_id: int
    sku: Optional[str] = None
    options: dict = {}
    price: Optional[int] = None
    stock: int = 0
    is_active: bool = True
    effective_price: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VariantCreate(BaseModel):
    sku: Optional[str] = Field(None, max_length=100)
    options: dict = {}
    price: Optional[int] = None
    stock: int = Field(0, ge=0)
    is_active: bool = True


class VariantUpdate(BaseModel):
    sku: Optional[str] = Field(None, max_length=100)
    options: Optional[dict] = None
    price: Optional[int] = None
    stock: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    type: str = "simple"
    sku: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"
    category_id: Optional[int] = None
    price: Optional[int] = None
    sizes: list[Any] = []
    colors: list[Any] = []
    image_url: Optional[str] = None
    stock: int = 0
    low_stock_threshold: int = 5
    is_dashboard_managed: bool = False
    fb_post_id: Optional[str] = None
    ig_post_id: Optional[str] = None
    variant_count: int = 0
    total_stock: int = 0
    low_stock: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductDetail(ProductOut):
    variants: list[ProductVariantOut] = []


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    limit: int


class StockUpdate(BaseModel):
    stock: int = Field(..., ge=0)


class InventoryItem(ProductOut):
    low_stock: bool = False


class InventorySummary(BaseModel):
    total_products: int
    total_stock: int
    low_stock_count: int
    out_of_stock_count: int


class StockAdjust(BaseModel):
    quantity: int = Field(..., description="Positive to add, negative to deduct")
    reason: Optional[str] = Field(None, pattern="^(manual|adjustment|restock|correction|set)$")


class StockMovementOut(BaseModel):
    id: int
    tenant_id: int
    product_id: Optional[int] = None
    product_variant_id: Optional[int] = None
    delta: int
    reason: Optional[str] = None
    order_id: Optional[int] = None
    actor: Optional[int] = None
    reference: Optional[str] = None
    data: Optional[dict] = None
    qty_after: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StockCountCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    counted_quantity: Optional[int] = None
    note: Optional[str] = None


class StockCountReconcile(BaseModel):
    note: Optional[str] = None


class StockCountOut(BaseModel):
    id: int
    tenant_id: int
    product_id: int
    variant_id: Optional[int] = None
    expected_quantity: int
    counted_quantity: Optional[int] = None
    delta: Optional[int] = None
    counted_by: Optional[int] = None
    counted_at: Optional[datetime] = None
    note: Optional[str] = None
    reconciled: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Dashboard ----------
class DashboardStats(BaseModel):
    new_orders: int
    confirmed_orders: int
    total_revenue: int
    low_stock_count: int
    by_wilaya: list[dict] = []
    recent_orders: list[OrderOut] = []


# ---------- Audit ----------
class AuditLogOut(BaseModel):
    id: int
    actor: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    payload: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Categories ----------
class CategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    parent_id: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    slug: str
    parent_id: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True
    product_count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryNode(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True
    children: list["CategoryNode"] = []

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    items: list[CategoryOut]
    total: int


# ---------- Product Media ----------
class ProductMediaOut(BaseModel):
    id: int
    tenant_id: int
    product_id: int
    variant_id: Optional[int] = None
    kind: str
    url: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    alt_text: Optional[str] = None
    sort_order: int = 0
    is_primary: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ProductMediaUpdate(BaseModel):
    alt_text: Optional[str] = None
    sort_order: Optional[int] = None
    is_primary: Optional[bool] = None
    variant_id: Optional[int] = None