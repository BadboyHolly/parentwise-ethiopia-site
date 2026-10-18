"""Private QA-only customer download grants; never paid product access."""
from alembic import op
import sqlalchemy as sa

revision = '20261018_05'
down_revision = '20261010_04'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('qa_simulated_ledger', sa.Column('customer_order_id', sa.String(36), nullable=True))
    op.create_index('uq_qa_customer_transfer_order', 'qa_simulated_ledger', ['customer_order_id'], unique=True)
    op.create_table('qa_download_grants',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('review_id', sa.String(36), sa.ForeignKey('qa_payment_reviews.id'), nullable=False),
        sa.Column('package_version', sa.String(40), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('order_id', name='uq_qa_download_order'),
        sa.CheckConstraint("package_version = 'QA-DEMO-2026.10-v1'", name='ck_qa_download_dummy_version'))
    op.create_index('ix_qa_download_grants_order', 'qa_download_grants', ['order_id'])

def downgrade():
    op.drop_index('ix_qa_download_grants_order', table_name='qa_download_grants')
    op.drop_table('qa_download_grants')
    op.drop_index('uq_qa_customer_transfer_order', table_name='qa_simulated_ledger')
    op.drop_column('qa_simulated_ledger', 'customer_order_id')
