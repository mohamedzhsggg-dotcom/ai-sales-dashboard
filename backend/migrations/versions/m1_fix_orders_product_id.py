"""add missing product_id FK to orders table

Revision ID: m1_fix_orders_product_id
Revises: m1_shipments
Create Date: 2026-08-21

The product_id FK was added to the Order model but never to a migration.
This migration adds it retroactively.
"""

from alembic import op
import sqlalchemy as sa

revision = "m1_fix_orders_product_id"
down_revision = "m1_shipments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("product_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "orders_product_id_fkey", "orders", "products", ["product_id"], ["id"]
    )
    op.create_index("ix_orders_product_id", "orders", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_product_id", table_name="orders")
    op.drop_constraint("orders_product_id_fkey", "orders", type_="foreignkey")
    op.drop_column("orders", "product_id")
