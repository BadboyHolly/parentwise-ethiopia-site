-- ParentWise Ethiopia — QA checkout schema (not yet connected to the QA site)
-- Requires server-side PostgreSQL and server-only credentials.
CREATE TABLE IF NOT EXISTS orders (
  id UUID PRIMARY KEY,
  order_code VARCHAR(32) UNIQUE NOT NULL,
  customer_name VARCHAR(100) NOT NULL,
  mobile_e164 VARCHAR(16) NOT NULL,
  payment_method VARCHAR(16) NOT NULL CHECK(payment_method IN ('telebirr','bank')),
  amount_etb INTEGER NOT NULL DEFAULT 1500 CHECK(amount_etb=1500),
  currency CHAR(3) NOT NULL DEFAULT 'ETB' CHECK(currency='ETB'),
  status VARCHAR(24) NOT NULL DEFAULT 'PENDING_PAYMENT'
    CHECK(status IN ('PENDING_PAYMENT','PROOF_SUBMITTED','VERIFYING','VERIFIED_PAID','DELIVERED','CANCELLED','EXPIRED','REFUNDED')),
  idempotency_key UUID NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  verified_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ,
  refunded_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS payment_reconciliations (
  id UUID PRIMARY KEY,
  order_id UUID NOT NULL REFERENCES orders(id),
  payment_method VARCHAR(16) NOT NULL,
  provider_reference VARCHAR(128) NOT NULL,
  amount_etb INTEGER NOT NULL CHECK(amount_etb > 0),
  confirmed_at TIMESTAMPTZ NOT NULL,
  verified_by UUID NOT NULL,
  UNIQUE (payment_method,provider_reference),
  UNIQUE (order_id)
);
CREATE TABLE IF NOT EXISTS operator_audit (
  id UUID PRIMARY KEY,
  order_id UUID NOT NULL REFERENCES orders(id),
  operator_id UUID NOT NULL,
  old_status VARCHAR(24),
  new_status VARCHAR(24) NOT NULL,
  action VARCHAR(64) NOT NULL,
  note VARCHAR(600),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS orders_created_idx ON orders(created_at DESC);
-- Deployment requirement:
-- Place this schema and operator mutations behind a protected server-side API.
-- Never expose the DB or operator credentials in JavaScript/HTML.
