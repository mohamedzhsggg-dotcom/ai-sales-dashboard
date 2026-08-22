"""create core schema tables

Revision ID: m0_core_schema
Revises: e8f677f4ce06
Create Date: 2026-08-22

Creates all core application tables that are referenced by later migrations
but were never explicitly created. This restores the baseline schema that
was missing from the empty af76afcbe9b5 migration.

Tables created here have only the columns that exist BEFORE later migrations
add their enrichment columns (e.g. products gets type/sku/description later
via m1_products_enrich, orders gets subtotal/shipping_fee etc. via m1_order_items).

Tables NOT created here (created by later migrations):
- post_product_mappings (m1_post_mappings)
- categories (m1_categories)
- product_variants (m1_products_enrich)
- product_media (m1_product_media)
- stock_counts (m1_inventory_variant)
- order_items, returns (m1_order_items)
- shipments, shipment_tracking (m1_shipments)
- conversations, messages, social_comments (a649b1f9eabf)

Tables NOT created here (created by app via create_all or not needed for FK chain):
- inventory_events (has FK to product_variants which doesn't exist yet)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'm0_core_schema'
down_revision: Union[str, None] = 'e8f677f4ce06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- tenants ----
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True)

    # ---- users (base columns — phone added later by a649b1f9eabf) ----
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=True, server_default='agent'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'], unique=False)

    # ---- customers (base columns — external_id added later by 171e93498769) ----
    op.create_table('customers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('wilaya', sa.String(length=100), nullable=True),
        sa.Column('commune', sa.String(length=100), nullable=True),
        sa.Column('platform', sa.String(length=20), nullable=True),
        sa.Column('sender_ids', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('synced_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_customers_id', 'customers', ['id'], unique=False)
    op.create_index('ix_customers_phone', 'customers', ['phone'], unique=False)
    op.create_index('ix_customers_tenant_id', 'customers', ['tenant_id'], unique=False)

    # ---- products (base columns — category_id added by m1_categories, type/sku/description/status/low_stock_threshold/is_dashboard_managed added by m1_products_enrich) ----
    op.create_table('products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('sheet_row', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('price', sa.Integer(), nullable=True),
        sa.Column('sizes', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('colors', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('stock', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('fb_post_id', sa.String(length=100), nullable=True),
        sa.Column('ig_post_id', sa.String(length=100), nullable=True),
        sa.Column('synced_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_products_id', 'products', ['id'], unique=False)
    op.create_index('ix_products_name', 'products', ['name'], unique=False)
    op.create_index('ix_products_tenant_id', 'products', ['tenant_id'], unique=False)

    # ---- orders (base columns — subtotal/shipping_fee/total/currency/items_count/notes/cancel_reason/cancel_note/has_return added by m1_order_items, courier_name/tracking_number/shipped_at/delivered_at added by m1_shipments, product_id added by m1_fix_orders_product_id) ----
    op.create_table('orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.String(length=100), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('wilaya', sa.String(length=100), nullable=True),
        sa.Column('commune', sa.String(length=100), nullable=True),
        sa.Column('product', sa.String(length=255), nullable=True),
        sa.Column('color', sa.String(length=100), nullable=True),
        sa.Column('size', sa.String(length=50), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('price', sa.Integer(), nullable=True),
        sa.Column('delivery_method', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='new'),
        sa.Column('source_channel', sa.String(length=20), nullable=True),
        sa.Column('sheet_row', sa.Integer(), nullable=True),
        sa.Column('synced_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_orders_id', 'orders', ['id'], unique=False)
    op.create_index('ix_orders_order_id', 'orders', ['order_id'], unique=False)
    op.create_index('ix_orders_phone', 'orders', ['phone'], unique=False)
    op.create_index('ix_orders_status', 'orders', ['status'], unique=False)
    op.create_index('ix_orders_tenant_id', 'orders', ['tenant_id'], unique=False)

    # ---- order_status_history ----
    op.create_table('order_status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(length=50), nullable=True),
        sa.Column('to_status', sa.String(length=50), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_order_status_history_order_id', 'order_status_history', ['order_id'], unique=False)

    # ---- sessions ----
    op.create_table('sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('refresh_token_hash'),
    )
    op.create_index('ix_sessions_refresh_token_hash', 'sessions', ['refresh_token_hash'], unique=True)
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'], unique=False)

    # ---- sheet_configs ----
    op.create_table('sheet_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('sheet_type', sa.String(length=50), nullable=False),
        sa.Column('spreadsheet_id', sa.String(length=255), nullable=False),
        sa.Column('tab', sa.String(length=255), nullable=False),
        sa.Column('column_map', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ---- audit_logs ----
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('actor', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.String(length=100), nullable=True),
        sa.Column('payload', postgresql.JSONB(), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['actor'], ['users.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'], unique=False)

    # ---- sync_runs ----
    op.create_table('sync_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('sheet_type', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('rows_processed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='running'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sync_runs_tenant_id', 'sync_runs', ['tenant_id'], unique=False)

    # ---- idempotency_keys ----
    op.create_table('idempotency_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('response_json', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index('ix_idempotency_keys_key', 'idempotency_keys', ['key'], unique=True)

    # NOTE: inventory_events is NOT created here because it has a FK to
    # product_variants which is created later by m1_products_enrich.
    # The app's auth/setup route calls Base.metadata.create_all() which
    # will create inventory_events after all migrations complete.


def downgrade() -> None:
    op.drop_index('ix_idempotency_keys_key', table_name='idempotency_keys')
    op.drop_table('idempotency_keys')
    op.drop_index('ix_sync_runs_tenant_id', table_name='sync_runs')
    op.drop_table('sync_runs')
    op.drop_index('ix_audit_logs_tenant_id', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_table('sheet_configs')
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_index('ix_sessions_refresh_token_hash', table_name='sessions')
    op.drop_table('sessions')
    op.drop_index('ix_order_status_history_order_id', table_name='order_status_history')
    op.drop_table('order_status_history')
    op.drop_index('ix_orders_tenant_id', table_name='orders')
    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_phone', table_name='orders')
    op.drop_index('ix_orders_order_id', table_name='orders')
    op.drop_index('ix_orders_id', table_name='orders')
    op.drop_table('orders')
    op.drop_index('ix_products_tenant_id', table_name='products')
    op.drop_index('ix_products_name', table_name='products')
    op.drop_index('ix_products_id', table_name='products')
    op.drop_table('products')
    op.drop_index('ix_customers_tenant_id', table_name='customers')
    op.drop_index('ix_customers_phone', table_name='customers')
    op.drop_index('ix_customers_id', table_name='customers')
    op.drop_table('customers')
    op.drop_index('ix_users_tenant_id', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    op.drop_index('ix_tenants_slug', table_name='tenants')
    op.drop_table('tenants')
