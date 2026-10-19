-- Deploy ONLY into the new, empty production PostgreSQL database.
-- This order intake has no payment-verification or delivery transitions.
CREATE TABLE production_orders (
    id VARCHAR(36) PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    customer_name VARCHAR(100) NOT NULL,
    mobile_e164 VARCHAR(16) NOT NULL,
    method VARCHAR(16) NOT NULL,
    amount_etb INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(24) NOT NULL,
    idempotency_hash VARCHAR(64) NOT NULL UNIQUE,
    request_fingerprint VARCHAR(64) NOT NULL,
    access_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_prod_order_amount CHECK (amount_etb = 1500),
    CONSTRAINT ck_prod_order_currency CHECK (currency = 'ETB'),
    CONSTRAINT ck_prod_order_method CHECK (method IN ('telebirr', 'bank')),
    CONSTRAINT ck_prod_order_unverified CHECK (status = 'AWAITING_PAYMENT')
);
CREATE INDEX ix_production_orders_created ON production_orders (created_at);
COMMENT ON TABLE production_orders IS 'Stage 1 unverified customer orders. No paid states permitted here.';
