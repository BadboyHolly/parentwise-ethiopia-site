"""Create isolated QA order persistence (no payment mutations).
Revision ID: 20261009_01
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '20261009_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('orders',
      sa.Column('id', sa.String(36), primary_key=True),
      sa.Column('order_code', sa.String(40), nullable=False, unique=True),
      sa.Column('customer_name', sa.String(100), nullable=False),
      sa.Column('mobile_e164', sa.String(16), nullable=False),
      sa.Column('payment_method', sa.String(16), nullable=False),
      sa.Column('amount_etb', sa.Integer(), nullable=False, server_default='1500'),
      sa.Column('currency', sa.String(3), nullable=False, server_default='ETB'),
      sa.Column('status', sa.String(24), nullable=False, server_default='PENDING_PAYMENT'),
      sa.Column('idempotency_hash', sa.String(64), nullable=False, unique=True),
      sa.Column('request_fingerprint', sa.String(64), nullable=False),
      sa.Column('access_token_hash', sa.String(64), nullable=False),
      sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
      sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
      sa.CheckConstraint('amount_etb = 1500', name='ck_order_price'),
      sa.CheckConstraint("currency = 'ETB'", name='ck_order_currency'),
      sa.CheckConstraint("payment_method IN ('telebirr','bank')", name='ck_payment_method'),
      sa.CheckConstraint("status = 'PENDING_PAYMENT'", name='ck_qa_pending_only'))
    op.create_index('ix_orders_created_at','orders',['created_at'])
    op.create_table('api_rate_windows',
      sa.Column('key', sa.String(64), primary_key=True),
      sa.Column('count', sa.Integer(), nullable=False, server_default='0'),
      sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('api_rate_windows')
    op.drop_index('ix_orders_created_at',table_name='orders')
    op.drop_table('orders')