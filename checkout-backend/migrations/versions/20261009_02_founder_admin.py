"""Founder-only read-only QA administrative sessions and security audit.

Revision ID: 20261009_02
Revises: 20261009_01
"""
from alembic import op
import sqlalchemy as sa

revision = '20261009_02'
down_revision = '20261009_01'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('admin_sessions',
        sa.Column('session_hash', sa.String(64), primary_key=True),
        sa.Column('credentials_version', sa.String(64), nullable=False),
        sa.Column('user_agent_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_admin_sessions_expires_at','admin_sessions',['expires_at'])
    op.create_table('admin_totp_state',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('last_accepted_step', sa.BigInteger, nullable=False, server_default='0'),
        sa.CheckConstraint('id = 1',name='ck_one_founder'))
    op.execute('INSERT INTO admin_totp_state (id, last_accepted_step) VALUES (1, 0)')
    op.create_table('admin_audit',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event', sa.String(50), nullable=False),
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('order_code', sa.String(40), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_admin_audit_created_at','admin_audit',['created_at'])


def downgrade():
    op.drop_index('ix_admin_audit_created_at',table_name='admin_audit')
    op.drop_table('admin_audit')
    op.drop_table('admin_totp_state')
    op.drop_index('ix_admin_sessions_expires_at',table_name='admin_sessions')
    op.drop_table('admin_sessions')