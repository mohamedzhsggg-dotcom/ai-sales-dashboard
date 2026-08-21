"""enrich products table, create product_variants table

Revision ID: m1_products_enrich
Revises: m1_categories
Create Date: 2026-08-21

Additive migration: adds new columns to products, creates product_variants
table with tenant-scoped SKU uniqueness. No existing data is modified.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1_products_enrich"
down_revision: Union[str, None] = "m1_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- enrich products table ----
    op.add_column("products", sa.Column("type", sa.String(length=20), server_default="simple"))
    op.add_column("products", sa.Column("sku", sa.String(length=100), nullable=True))
    op.add_column("products", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("status", sa.String(length=20), server_default="active"))
    op.add_column("products", sa.Column("low_stock_threshold", sa.Integer(), server_default="5"))
    op.add_column("products", sa.Column("is_dashboard_managed", sa.Boolean(), server_default="false"))

    op.create_index("ix_products_type", "products", ["type"], unique=False)
    op.create_index("ix_products_status", "products", ["status"], unique=False)
    op.create_index("ix_products_tenant_sku", "products", ["tenant_id", "sku"], unique=True,
                     postgresql_where="sku IS NOT NULL")

    # ---- product_variants table ----
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("options", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("stock", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_variants_tenant_id", "product_variants", ["tenant_id"], unique=False)
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"], unique=False)
    op.create_index("ix_product_variants_sku", "product_variants", ["sku"], unique=False)
    op.create_index("ix_variants_tenant_sku", "product_variants", ["tenant_id", "sku"], unique=True,
                     postgresql_where="sku IS NOT NULL")


def downgrade() -> None:
    op.drop_index("ix_variants_tenant_sku", table_name="product_variants")
    op.drop_index("ix_product_variants_sku", table_name="product_variants")
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_index("ix_product_variants_tenant_id", table_name="product_variants")
    op.drop_table("product_variants")

    op.drop_index("ix_products_tenant_sku", table_name="products")
    op.drop_index("ix_products_status", table_name="products")
    op.drop_index("ix_products_type", table_name="products")
    op.drop_column("products", "is_dashboard_managed")
    op.drop_column("products", "low_stock_threshold")
    op.drop_column("products", "status")
    op.drop_column("products", "description")
    op.drop_column("products", "sku")
    op.drop_column("products", "type")
