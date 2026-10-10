"""QA simulated claim reconciliation only; no real financial integrations.
Revision ID: 20261010_03
Revises: 20261009_02
"""
from alembic import op
import sqlalchemy as sa

revision = '20261010_03'
down_revision = '20261009_02'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_qa_pending_only', 'orders', type_='check')
    op.create_check_constraint('ck_qa_order_state', 'orders',
         "status IN ('PENDING_PAYMENT','PROOF_SUBMITTED','VERIFYING','VERIFIED_PAID','CANCELLED')")
    op.create_table('qa_simulated_ledger',
      sa.Column('id',sa.String(36),primary_key=True),
      sa.Column('test_reference',sa.String(22),nullable=False),
      sa.Column('payment_method',sa.String(16),nullable=False),
      sa.Column('amount_etb',sa.Integer,nullable=False),
      sa.Column('currency',sa.String(3),nullable=False),
      sa.Column('generated_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('credited_order_id',sa.String(36),sa.ForeignKey('orders.id'),unique=True),
      sa.UniqueConstraint('payment_method','test_reference',name='uq_qa_ledger_ref'),
      sa.CheckConstraint('amount_etb > 0',name='ck_qa_ledger_positive'),
      sa.CheckConstraint("currency = 'ETB'",name='ck_qa_ledger_currency'))
    op.create_table('qa_payment_reviews',
      sa.Column('id',sa.String(36),primary_key=True),
      sa.Column('order_id',sa.String(36),sa.ForeignKey('orders.id'),nullable=False),
      sa.Column('payment_method',sa.String(16),nullable=False),
      sa.Column('test_reference',sa.String(22),nullable=False),
      sa.Column('reported_amount_etb',sa.Integer,nullable=False),
      sa.Column('currency',sa.String(3),nullable=False),
      sa.Column('state',sa.String(24),nullable=False),
      sa.Column('independent_check',sa.String(16),nullable=False),
      sa.Column('evidence_received_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('checked_at',sa.DateTime(timezone=True)),
      sa.Column('decided_at',sa.DateTime(timezone=True)),
      sa.Column('decision_reason',sa.String(320)),
      sa.UniqueConstraint('payment_method','test_reference',name='uq_qa_claim_reference'),
      sa.CheckConstraint('reported_amount_etb > 0',name='ck_qa_claim_positive'),
      sa.CheckConstraint("currency = 'ETB'",name='ck_qa_claim_currency'),
      sa.CheckConstraint("state IN ('PROOF_SUBMITTED','VERIFYING','VERIFIED_PAID','REJECTED')",name='ck_qa_claim_state'),
      sa.CheckConstraint("independent_check IN ('NOT_CHECKED','MATCHED','DISCREPANCY')",name='ck_qa_claim_independent'))
    op.create_index('ix_qa_reviews_order','qa_payment_reviews',['order_id'])
    op.create_table('qa_payment_events',
      sa.Column('id',sa.String(36),primary_key=True),
      sa.Column('order_id',sa.String(36),sa.ForeignKey('orders.id'),nullable=False),
      sa.Column('review_id',sa.String(36),sa.ForeignKey('qa_payment_reviews.id')),
      sa.Column('actor',sa.String(20),nullable=False),
      sa.Column('action',sa.String(50),nullable=False),
      sa.Column('previous_status',sa.String(24),nullable=False),
      sa.Column('new_status',sa.String(24),nullable=False),
      sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('reason',sa.String(400)))
    op.create_index('ix_qa_events_order','qa_payment_events',['order_id','occurred_at'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("""CREATE FUNCTION qa_block_event_edit() RETURNS trigger LANGUAGE plpgsql AS $$
                   BEGIN RAISE EXCEPTION 'QA audit events are append-only'; END; $$""")
        op.execute("""CREATE TRIGGER qa_payment_events_append_only BEFORE UPDATE OR DELETE
                   ON qa_payment_events FOR EACH ROW EXECUTE FUNCTION qa_block_event_edit()""")


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP TRIGGER qa_payment_events_append_only ON qa_payment_events')
        op.execute('DROP FUNCTION qa_block_event_edit()')
    op.drop_index('ix_qa_events_order',table_name='qa_payment_events')
    op.drop_table('qa_payment_events')
    op.drop_index('ix_qa_reviews_order',table_name='qa_payment_reviews')
    op.drop_table('qa_payment_reviews')
    op.drop_table('qa_simulated_ledger')
    op.drop_constraint('ck_qa_order_state','orders',type_='check')
    op.create_check_constraint('ck_qa_pending_only','orders',"status = 'PENDING_PAYMENT'")