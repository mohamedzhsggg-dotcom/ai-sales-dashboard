"""add post_product_mappings table

Revision ID: m1_post_mappings
Revises: e8f677f4ce06
Create Date: 2026-08-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'm1_post_mappings'
down_revision: Union[str, None] = 'm0_core_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('post_product_mappings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('fb_post_id', sa.String(length=100), nullable=True),
    sa.Column('ig_post_id', sa.String(length=100), nullable=True),
    sa.Column('product_name', sa.String(length=255), nullable=True),
    sa.Column('synced_hash', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_product_mappings_fb_post_id'), 'post_product_mappings', ['fb_post_id'], unique=False)
    op.create_index(op.f('ix_post_product_mappings_ig_post_id'), 'post_product_mappings', ['ig_post_id'], unique=False)
    op.create_index(op.f('ix_post_product_mappings_tenant_id'), 'post_product_mappings', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_post_product_mappings_tenant_id'), table_name='post_product_mappings')
    op.drop_index(op.f('ix_post_product_mappings_ig_post_id'), table_name='post_product_mappings')
    op.drop_index(op.f('ix_post_product_mappings_fb_post_id'), table_name='post_product_mappings')
    op.drop_table('post_product_mappings')