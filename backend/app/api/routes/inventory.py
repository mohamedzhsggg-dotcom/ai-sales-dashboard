from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.database import get_db
from app.models import InventoryEvent, Product, User
from app.schemas import InventoryItem, InventorySummary, ProductOut, StockUpdate
from app.services.writeback import WritebackService

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryItem])
def list_inventory(
    low_stock: bool | None = None,
    out_of_stock: bool | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Product).filter(Product.tenant_id == user.tenant_id)
    if low_stock:
        q = q.filter(Product.stock > 0, Product.stock <= 5)
    if out_of_stock:
        q = q.filter(Product.stock == 0)
    products = q.order_by(Product.stock.asc()).all()
    items = []
    for p in products:
        item = InventoryItem.model_validate(p)
        item.low_stock = 0 < (p.stock or 0) <= 5
        items.append(item)
    return items


@router.get("/summary", response_model=InventorySummary)
def inventory_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    products = db.query(Product).filter(Product.tenant_id == user.tenant_id).all()
    total_stock = sum(p.stock or 0 for p in products)
    return InventorySummary(
        total_products=len(products),
        total_stock=total_stock,
        low_stock_count=sum(1 for p in products if 0 < (p.stock or 0) <= 5),
        out_of_stock_count=sum(1 for p in products if (p.stock or 0) == 0),
    )


@router.patch("/{product_id}/stock", response_model=ProductOut)
def update_stock(
    product_id: int,
    payload: StockUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "agent")),
):
    product = db.get(Product, product_id)
    if not product or product.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Product not found")

    old_stock = product.stock or 0
    wb = WritebackService(db, user.tenant_id)
    wb.set_stock(product, payload.stock, actor_id=user.id, reason="manual")

    db.add(InventoryEvent(
        tenant_id=user.tenant_id,
        product_id=product.id,
        delta=payload.stock - old_stock,
        reason="manual",
        actor=user.id,
    ))
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)