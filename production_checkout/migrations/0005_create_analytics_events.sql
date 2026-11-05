-- Privacy-preserving first-party visit analytics (anonymous browser sessions).
-- sid_hash is an HMAC of a random per-tab id; no IP address, user agent, cookie,
-- name, phone number, order code or payment data is stored.
CREATE TABLE production_analytics_events (
    id BIGSERIAL PRIMARY KEY,
    sid_hash CHAR(64) NOT NULL CHECK (sid_hash ~ '^[a-f0-9]{64}$'),
    event VARCHAR(16) NOT NULL
        CHECK (event IN ('sales_view','checkout_view','payment_view','proof_view','telegram_open')),
    source VARCHAR(32) NOT NULL DEFAULT '' CHECK (source ~ '^[a-z0-9_-]*$'),
    campaign VARCHAR(48) NOT NULL DEFAULT '' CHECK (campaign ~ '^[a-z0-9_.-]*$'),
    device VARCHAR(8) NOT NULL CHECK (device IN ('mobile','tablet','desktop')),
    browser VARCHAR(16) NOT NULL
        CHECK (browser IN ('facebook_in_app','instagram_in_app','telegram_in_app','tiktok_in_app','other')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_prod_analytics_sid_event UNIQUE (sid_hash, event)
);
CREATE INDEX ix_prod_analytics_created ON production_analytics_events (created_at);
