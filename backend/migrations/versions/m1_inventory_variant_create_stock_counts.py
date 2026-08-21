"""create stock_counts table

Revision ID: m1_inventory_variant
Revises: m1_product_media
Create Date: 2026-08-21

Additive migration: creates stock_counts table for physical stock takes
and reconciliation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1_inventory_variant"
down_revision: Union[str, None] = "m1_product_media"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stock_counts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("expected_quantity", sa.Integer(), nullable=False),
        sa.Column("counted_quantity", sa.Integer(), nullable=True),
        sa.Column("delta", sa.Integer(), nullable=True),
        sa.Column("counted_by", sa.Integer(), nullable=True),
        sa.Column("counted_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reconciled", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.ForeignKeyConstraint(["counted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_counts_tenant_id", "stock_counts", ["tenant_id"], unique=False)
    op.create_index("ix_stock_counts_product_id", "stock_counts", ["product_id"], unique=False)
    op.create_index("ix_stock_counts_variant_id", "stock_counts", ["variant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stock_counts_variant_id", table_name="stock_counts")
    op.drop_index("ix_stock_counts_product_id", table_name="stock_counts")
    op.drop_index("ix_stock_counts_tenant_id", table_name="stock_counts")
    op.drop_table("stock_counts")
