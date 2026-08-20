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
class ProductOut(BaseModel):
    id: int
    name: str
    price: Optional[int] = None
    sizes: list[Any] = []
    colors: list[Any] = []
    image_url: Optional[str] = None
    stock: int
    fb_post_id: Optional[str] = None
    ig_post_id: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


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