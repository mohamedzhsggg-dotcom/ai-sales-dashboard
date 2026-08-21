"""m1_conversations_comments_enhancements

Revision ID: a649b1f9eabf
Revises: m1_fix_orders_product_id
Create Date: 2026-08-21 15:49:58.189857
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a649b1f9eabf'
down_revision: Union[str, None] = 'm1_fix_orders_product_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Conversations table
    op.create_table('conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('external_conversation_id', sa.String(length=255), nullable=True),
        sa.Column('external_user_id', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_id', 'conversations', ['id'])
    op.create_index('ix_conversations_tenant_id', 'conversations', ['tenant_id'])
    op.create_index('ix_conversations_customer_id', 'conversations', ['customer_id'])
    op.create_index('ix_conversations_external_conversation_id', 'conversations', ['external_conversation_id'])
    op.create_index('ix_conversations_external_user_id', 'conversations', ['external_user_id'])
    op.create_index('ix_conversations_status', 'conversations', ['status'])

    # Messages table
    op.create_table('messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('direction', sa.String(length=10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('platform_message_id', sa.String(length=255), nullable=True),
        sa.Column('external_user_id', sa.String(length=255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_id', 'messages', ['id'])
    op.create_index('ix_messages_tenant_id', 'messages', ['tenant_id'])
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'])

    # Social comments table
    op.create_table('social_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('post_id', sa.String(length=100), nullable=False),
        sa.Column('comment_id', sa.String(length=100), nullable=False),
        sa.Column('external_user_id', sa.String(length=255), nullable=True),
        sa.Column('external_username', sa.String(length=255), nullable=True),
        sa.Column('comment_text', sa.Text(), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True),
        sa.Column('replied', sa.Boolean(), nullable=True),
        sa.Column('reply_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id')
    )
    op.create_index('ix_social_comments_id', 'social_comments', ['id'])
    op.create_index('ix_social_comments_tenant_id', 'social_comments', ['tenant_id'])
    op.create_index('ix_social_comments_platform', 'social_comments', ['platform'])
    op.create_index('ix_social_comments_post_id', 'social_comments', ['post_id'])
    op.create_index('ix_social_comments_product_id', 'social_comments', ['product_id'])
    op.create_index('ix_social_comments_external_user_id', 'social_comments', ['external_user_id'])
    op.create_index('ix_social_comments_resolved', 'social_comments', ['resolved'])

    # Enhance post_product_mappings with platform/post_id/product_id
    op.add_column('post_product_mappings', sa.Column('platform', sa.String(length=20), nullable=False, server_default='facebook'))
    op.add_column('post_product_mappings', sa.Column('post_id', sa.String(length=100), nullable=False, server_default=''))
    op.add_column('post_product_mappings', sa.Column('product_id', sa.Integer(), nullable=True))
    op.create_index('ix_post_product_mappings_platform', 'post_product_mappings', ['platform'])
    op.create_index('ix_post_product_mappings_post_id', 'post_product_mappings', ['post_id'])
    op.create_index('ix_post_product_mappings_product_id', 'post_product_mappings', ['product_id'])
    op.create_unique_constraint('uq_post_product_mapping', 'post_product_mappings', ['tenant_id', 'platform', 'post_id'])
    op.create_foreign_key(None, 'post_product_mappings', 'products', ['product_id'], ['id'])

    # Users phone
    op.add_column('users', sa.Column('phone', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'phone')
    op.drop_constraint('uq_post_product_mapping', 'post_product_mappings', type_='unique')
    op.drop_constraint(None, 'post_product_mappings', type_='foreignkey')
    op.drop_index('ix_post_product_mappings_product_id', 'post_product_mappings')
    op.drop_index('ix_post_product_mappings_post_id', 'post_product_mappings')
    op.drop_index('ix_post_product_mappings_platform', 'post_product_mappings')
    op.drop_column('post_product_mappings', 'product_id')
    op.drop_column('post_product_mappings', 'post_id')
    op.drop_column('post_product_mappings', 'platform')
    op.drop_index('ix_social_comments_resolved', 'social_comments')
    op.drop_index('ix_social_comments_external_user_id', 'social_comments')
    op.drop_index('ix_social_comments_product_id', 'social_comments')
    op.drop_index('ix_social_comments_post_id', 'social_comments')
    op.drop_index('ix_social_comments_platform', 'social_comments')
    op.drop_index('ix_social_comments_tenant_id', 'social_comments')
    op.drop_index('ix_social_comments_id', 'social_comments')
    op.drop_table('social_comments')
    op.drop_index('ix_messages_conversation_id', 'messages')
    op.drop_index('ix_messages_tenant_id', 'messages')
    op.drop_index('ix_messages_id', 'messages')
    op.drop_table('messages')
    op.drop_index('ix_conversations_status', 'conversations')
    op.drop_index('ix_conversations_external_user_id', 'conversations')
    op.drop_index('ix_conversations_external_conversation_id', 'conversations')
    op.drop_index('ix_conversations_customer_id', 'conversations')
    op.drop_index('ix_conversations_tenant_id', 'conversations')
    op.drop_index('ix_conversations_id', 'conversations')
    op.drop_table('conversations')
