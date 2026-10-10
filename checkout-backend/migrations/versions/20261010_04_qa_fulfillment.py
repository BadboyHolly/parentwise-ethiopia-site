"""QA-only dummy fulfillment schema. No real product access.
Revision ID: 20261010_04
Revises: 20261010_03
"""
from alembic import op
import sqlalchemy as sa
revision='20261010_04'
down_revision='20261010_03'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('qa_fulfillments',
      sa.Column('id',sa.String(36),primary_key=True),
      sa.Column('order_id',sa.String(36),sa.ForeignKey('orders.id'),unique=True,nullable=False),
      sa.Column('qa_review_id',sa.String(36),sa.ForeignKey('qa_payment_reviews.id'),unique=True,nullable=False),
      sa.Column('package_version',sa.String(40),nullable=False),
      sa.Column('delivery_channel',sa.String(50),nullable=False),
      sa.Column('state',sa.String(24),nullable=False),
      sa.Column('attempt_count',sa.Integer,nullable=False,server_default='0'),
      sa.Column('qa_ack_reference',sa.String(23),unique=True),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('sent_at',sa.DateTime(timezone=True)),
      sa.Column('delivered_at',sa.DateTime(timezone=True)),
      sa.Column('failure_at',sa.DateTime(timezone=True)),
      sa.CheckConstraint("state IN ('PENDING_FULFILLMENT','PREPARING','SENT','DELIVERED','DELIVERY_FAILED')",name='ck_qa_fulfillment_state'),
      sa.CheckConstraint("package_version = 'QA-DEMO-2026.10-v1'",name='ck_qa_dummy_version'),
      sa.CheckConstraint("delivery_channel = 'TELEGRAM_FOUNDER_ASSISTED_QA_SIMULATION'",name='ck_qa_dummy_channel'),
      sa.CheckConstraint('attempt_count >= 0',name='ck_qa_attempt_positive'))
    op.create_index('ix_qa_fulfillments_state_created','qa_fulfillments',['state','created_at'])
    op.create_table('qa_fulfillment_events',
      sa.Column('id',sa.String(36),primary_key=True),
      sa.Column('fulfillment_id',sa.String(36),sa.ForeignKey('qa_fulfillments.id'),nullable=False),
      sa.Column('order_id',sa.String(36),sa.ForeignKey('orders.id'),nullable=False),
      sa.Column('action',sa.String(60),nullable=False),
      sa.Column('from_state',sa.String(24),nullable=False),
      sa.Column('to_state',sa.String(24),nullable=False),
      sa.Column('actor',sa.String(24),nullable=False),
      sa.Column('note',sa.String(300)),
      sa.Column('qa_ack_reference',sa.String(23)),
      sa.Column('happened_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_qa_fulfillment_events_fulfillment','qa_fulfillment_events',['fulfillment_id','happened_at'])
    if op.get_bind().dialect.name=='postgresql':
        op.execute("""CREATE FUNCTION qa_fulfillment_event_write_block()
                  RETURNS trigger LANGUAGE plpgsql AS $$
                  BEGIN RAISE EXCEPTION 'QA fulfillment events are append-only'; END; $$""")
        op.execute("""CREATE TRIGGER qa_fulfillment_events_append_only BEFORE UPDATE OR DELETE
                  ON qa_fulfillment_events FOR EACH ROW EXECUTE FUNCTION qa_fulfillment_event_write_block()""")
        # Migrate prior QA-verified orders ONLY if synthetic ledger, review and
        # attributed credit all independently agree. No real-money implications.
        op.execute("""INSERT INTO qa_fulfillments
          (id,order_id,qa_review_id,package_version,delivery_channel,state,attempt_count,created_at,updated_at)
          SELECT gen_random_uuid()::text, o.id, r.id, 'QA-DEMO-2026.10-v1',
          'TELEGRAM_FOUNDER_ASSISTED_QA_SIMULATION','PENDING_FULFILLMENT',0,
          CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
          FROM orders o JOIN qa_payment_reviews r ON r.order_id=o.id
          JOIN qa_simulated_ledger l ON l.credited_order_id=o.id
          AND l.test_reference=r.test_reference AND l.payment_method=r.payment_method
          WHERE o.status='VERIFIED_PAID' AND o.amount_etb=1500 AND o.currency='ETB'
          AND r.state='VERIFIED_PAID' AND r.independent_check='MATCHED'
          AND r.reported_amount_etb=1500 AND r.currency='ETB'
          AND l.amount_etb=1500 AND l.currency='ETB'
          ON CONFLICT (order_id) DO NOTHING""")
        op.execute("""INSERT INTO qa_fulfillment_events
          (id,fulfillment_id,order_id,action,from_state,to_state,actor,note,happened_at)
          SELECT gen_random_uuid()::text,f.id,f.order_id,'qa_backfill_simulated_credit',
          'NONE','PENDING_FULFILLMENT','qa_system',
          'Synthetic credited ledger only; no real payment or file authorization',CURRENT_TIMESTAMP
          FROM qa_fulfillments f""")

def downgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.execute('DROP TRIGGER qa_fulfillment_events_append_only ON qa_fulfillment_events')
        op.execute('DROP FUNCTION qa_fulfillment_event_write_block()')
    op.drop_index('ix_qa_fulfillment_events_fulfillment',table_name='qa_fulfillment_events')
    op.drop_table('qa_fulfillment_events')
    op.drop_index('ix_qa_fulfillments_state_created',table_name='qa_fulfillments')
    op.drop_table('qa_fulfillments')
