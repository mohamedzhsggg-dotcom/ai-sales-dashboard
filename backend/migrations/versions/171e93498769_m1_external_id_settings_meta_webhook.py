"""m1_external_id_settings_meta_webhook

Revision ID: 171e93498769
Revises: a649b1f9eabf
Create Date: 2026-08-21 16:15:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '171e93498769'
down_revision: Union[str, None] = 'a649b1f9eabf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.create_index('ix_customers_external_id', 'customers', ['external_id'])


def downgrade() -> None:
    op.drop_index('ix_customers_external_id', 'customers')
    op.drop_column('customers', 'external_id')
