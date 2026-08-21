"""enrich orders, create order_items and returns tables

Revision ID: m1_order_items
Revises: m1_inventory_variant
Create Date: 2026-08-21

Additive migration: adds enrichment columns to orders, creates order_items
and returns tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1_order_items"
down_revision: Union[str, None] = "m1_inventory_variant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- enrich orders ----
    op.add_column("orders", sa.Column("subtotal", sa.Integer(), server_default="0"))
    op.add_column("orders", sa.Column("shipping_fee", sa.Integer(), server_default="0"))
    op.add_column("orders", sa.Column("total", sa.Integer(), server_default="0"))
    op.add_column("orders", sa.Column("currency", sa.String(length=10), server_default="DZD"))
    op.add_column("orders", sa.Column("items_count", sa.Integer(), server_default="1"))
    op.add_column("orders", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("cancel_note", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("has_return", sa.Boolean(), server_default="false"))

    # ---- order_items ----
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("variant_options", sa.JSON(), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_items_tenant_id", "order_items", ["tenant_id"], unique=False)
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)

    # ---- returns ----
    op.create_table(
        "returns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("refund_amount", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(length=50), server_default="pending"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_returns_tenant_id", "returns", ["tenant_id"], unique=False)
    op.create_index("ix_returns_order_id", "returns", ["order_id"], unique=False)
    op.create_index("ix_returns_status", "returns", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_returns_status", table_name="returns")
    op.drop_index("ix_returns_order_id", table_name="returns")
    op.drop_index("ix_returns_tenant_id", table_name="returns")
    op.drop_table("returns")

    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_index("ix_order_items_tenant_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_column("orders", "has_return")
    op.drop_column("orders", "cancel_note")
    op.drop_column("orders", "cancel_reason")
    op.drop_column("orders", "notes")
    op.drop_column("orders", "items_count")
    op.drop_column("orders", "currency")
    op.drop_column("orders", "total")
    op.drop_column("orders", "shipping_fee")
    op.drop_column("orders", "subtotal")
