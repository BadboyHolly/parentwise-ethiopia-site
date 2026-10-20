-- Privacy-preserving abuse throttling for production customer endpoints.
-- Bucket keys are HMACs; no IP address, order token, or raw reference is stored.
CREATE TABLE production_customer_rate_limits (
    bucket_hash CHAR(64) PRIMARY KEY
        CHECK (bucket_hash ~ '^[a-f0-9]{64}$'),
    window_started_at TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL CHECK (attempts > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_production_customer_rate_limits_updated
    ON production_customer_rate_limits (updated_at);
