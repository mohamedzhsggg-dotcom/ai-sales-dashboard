"""create product_media table

Revision ID: m1_product_media
Revises: m1_products_enrich
Create Date: 2026-08-21

Additive migration: creates product_media table for product images and videos.
Backfills existing image_url into product_media where present.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1_product_media"
down_revision: Union[str, None] = "m1_products_enrich"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.String(length=500), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_primary", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_media_tenant_id", "product_media", ["tenant_id"], unique=False)
    op.create_index("ix_product_media_product_id", "product_media", ["product_id"], unique=False)

    # Backfill existing image_url into product_media
    conn = op.get_bind()
    if conn is not None:
        conn.execute(
            sa.text(
                "INSERT INTO product_media (tenant_id, product_id, kind, url, is_primary, sort_order, created_at) "
                "SELECT tenant_id, id, 'image', image_url, true, 0, now() "
                "FROM products WHERE image_url IS NOT NULL AND image_url != ''"
            )
        )


def downgrade() -> None:
    op.drop_index("ix_product_media_product_id", table_name="product_media")
    op.drop_index("ix_product_media_tenant_id", table_name="product_media")
    op.drop_table("product_media")
