-- QA/staging-only sidecar tables. Apply only to the disposable staging database.
-- production_orders is created first by production_checkout/migrations/0001_create_orders.sql.
CREATE TABLE staging_order_states (
  order_id VARCHAR(36) PRIMARY KEY REFERENCES production_orders(id) ON DELETE CASCADE,
  order_code VARCHAR(32) NOT NULL UNIQUE,
  status VARCHAR(32) NOT NULL CHECK (status IN ('AWAITING_PAYMENT','UNDER_REVIEW','PAYMENT_CONFIRMED','READY_TO_DOWNLOAD')),
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE staging_payment_claims (
  id VARCHAR(36) PRIMARY KEY,
  order_id VARCHAR(36) NOT NULL REFERENCES production_orders(id) ON DELETE CASCADE,
  reference VARCHAR(48) NOT NULL UNIQUE CHECK (reference ~ '^SIM-[A-Z0-9]{8,40}$'),
  payment_method VARCHAR(16) NOT NULL CHECK (payment_method IN ('telebirr','bank')),
  reported_amount_etb INTEGER NOT NULL CHECK (reported_amount_etb > 0),
  currency VARCHAR(3) NOT NULL CHECK (currency = 'ETB'),
  state VARCHAR(24) NOT NULL CHECK (state IN ('SUBMITTED','MATCHED','DISCREPANCY','REJECTED')),
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_staging_claims_order_created ON staging_payment_claims(order_id, created_at);
CREATE TABLE staging_simulated_settlements (
  reference VARCHAR(48) PRIMARY KEY CHECK (reference ~ '^SIM-[A-Z0-9]{8,40}$'),
  payment_method VARCHAR(16) NOT NULL CHECK (payment_method IN ('telebirr','bank')),
  amount_etb INTEGER NOT NULL CHECK (amount_etb > 0),
  currency VARCHAR(3) NOT NULL CHECK (currency = 'ETB'),
  recipient_code VARCHAR(40) NOT NULL CHECK (recipient_code LIKE 'QA-%'),
  payer_mobile VARCHAR(16) NOT NULL,
  recorded_by VARCHAR(100) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE staging_download_grants (
  order_id VARCHAR(36) PRIMARY KEY REFERENCES production_orders(id) ON DELETE CASCADE,
  active BOOLEAN NOT NULL,
  package_version VARCHAR(32) NOT NULL CHECK (package_version LIKE 'QA-%'),
  issued_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ
);
CREATE TABLE staging_audit_events (
  id VARCHAR(36) PRIMARY KEY,
  order_id VARCHAR(36) REFERENCES production_orders(id) ON DELETE CASCADE,
  actor VARCHAR(100) NOT NULL,
  action VARCHAR(64) NOT NULL,
  details TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_staging_audit_order_time ON staging_audit_events(order_id, created_at);
CREATE TABLE staging_founder_sessions (
  token_hash VARCHAR(64) PRIMARY KEY,
  csrf_hash VARCHAR(64) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ
);
CREATE TABLE staging_rate_windows (
  bucket_key VARCHAR(64) PRIMARY KEY,
  count INTEGER NOT NULL CHECK (count > 0),
  reset_at TIMESTAMPTZ NOT NULL
);
