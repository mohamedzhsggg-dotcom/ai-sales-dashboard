"""add categories table, products.category_id, seed Uncategorized per tenant

Revision ID: m1_categories
Revises: m1_post_mappings
Create Date: 2026-08-21

Additive migration: creates new tables/columns only. No existing data is
dropped or truncated. Downgrade is the exact inverse (drops what was added).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1_categories"
down_revision: Union[str, None] = "m1_post_mappings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- categories table ----
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_categories_tenant_slug"),
    )
    op.create_index(op.f("ix_categories_name"), "categories", ["name"], unique=False)
    op.create_index(op.f("ix_categories_parent_id"), "categories", ["parent_id"], unique=False)
    op.create_index(op.f("ix_categories_slug"), "categories", ["slug"], unique=False)
    op.create_index(op.f("ix_categories_tenant_id"), "categories", ["tenant_id"], unique=False)

    # ---- products.category_id (nullable) ----
    op.add_column("products", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"], unique=False)
    op.create_foreign_key(
        "fk_products_category_id",
        "products",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ---- seed: one "Uncategorized" per existing tenant (skip in offline mode) ----
    conn = op.get_bind()
    if conn is not None:
        tenants = conn.execute(sa.text("SELECT id FROM tenants WHERE is_active = true")).fetchall()
        for (tid,) in tenants:
            conn.execute(
                sa.text(
                    "INSERT INTO categories (tenant_id, name, slug, sort_order, is_active, created_at, updated_at) "
                    "VALUES (:tid, 'Uncategorized', 'uncategorized', 0, true, now(), now())"
                ),
                {"tid": tid},
            )
            conn.execute(
                sa.text(
                    "UPDATE products SET category_id = "
                    "(SELECT id FROM categories WHERE tenant_id = :tid AND slug = 'uncategorized' LIMIT 1) "
                    "WHERE tenant_id = :tid AND category_id IS NULL"
                ),
                {"tid": tid},
            )


def downgrade() -> None:
    # Drop foreign key, index, column on products first.
    op.drop_constraint("fk_products_category_id", "products", type_="foreignkey")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_column("products", "category_id")

    # Drop categories (seeded rows cascade away).
    op.drop_index(op.f("ix_categories_tenant_id"), table_name="categories")
    op.drop_index(op.f("ix_categories_slug"), table_name="categories")
    op.drop_index(op.f("ix_categories_parent_id"), table_name="categories")
    op.drop_index(op.f("ix_categories_name"), table_name="categories")
    op.drop_table("categories")
