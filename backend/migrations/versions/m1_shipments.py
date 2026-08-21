"""add shipments tables and order courier fields

Revision ID: m1_shipments
Revises: m1_order_items
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "m1_shipments"
down_revision = "m1_order_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("courier_name", sa.String(50), nullable=True))
    op.add_column("orders", sa.Column("tracking_number", sa.String(100), nullable=True))
    op.add_column("orders", sa.Column("shipped_at", sa.DateTime(), nullable=True))
    op.add_column("orders", sa.Column("delivered_at", sa.DateTime(), nullable=True))
    op.create_index("ix_orders_tracking_number", "orders", ["tracking_number"])

    op.create_table(
        "shipments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("courier_name", sa.String(50), nullable=False, index=True),
        sa.Column("tracking_number", sa.String(100), nullable=True, index=True),
        sa.Column("status", sa.String(50), server_default="pending", nullable=False, index=True),
        sa.Column("cod_amount", sa.Integer(), server_default="0"),
        sa.Column("shipping_fee", sa.Integer(), server_default="0"),
        sa.Column("delivery_method", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("shipped_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "shipment_tracking",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("shipment_id", sa.Integer(), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("courier_raw_status", sa.String(100), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("shipment_tracking")
    op.drop_table("shipments")
    op.drop_index("ix_orders_tracking_number", table_name="orders")
    op.drop_column("orders", "delivered_at")
    op.drop_column("orders", "shipped_at")
    op.drop_column("orders", "tracking_number")
    op.drop_column("orders", "courier_name")
