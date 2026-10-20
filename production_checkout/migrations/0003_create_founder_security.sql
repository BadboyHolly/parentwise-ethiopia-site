-- Founder authentication and replay-safe sessions. Apply after migrations 0001/0002.
CREATE TABLE production_founder_auth_control (
    singleton_id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (singleton_id = 1),
    last_totp_step BIGINT NOT NULL DEFAULT -1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO production_founder_auth_control(singleton_id) VALUES (1);

CREATE TABLE production_founder_sessions (
    session_hash CHAR(64) PRIMARY KEY,
    founder_id VARCHAR(80) NOT NULL,
    csrf_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT ck_founder_session_expiry CHECK (expires_at > created_at),
    CONSTRAINT ck_founder_session_founder CHECK (length(founder_id) BETWEEN 1 AND 80)
);
CREATE INDEX ix_founder_session_expiry ON production_founder_sessions(expires_at)
  WHERE revoked_at IS NULL;

CREATE TABLE production_founder_rate_limits (
    bucket_hash CHAR(64) PRIMARY KEY,
    window_started_at TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL CHECK (attempts >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE production_founder_security_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(40) NOT NULL,
    founder_id VARCHAR(80),
    source_hash CHAR(64),
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_founder_security_event CHECK
      (event_type IN ('LOGIN_SUCCEEDED','LOGIN_FAILED','SESSION_EXPIRED','LOGOUT',
                      'MFA_REPLAY_BLOCKED','ENROLLMENT_ROTATED','RECOVERY_LOCKOUT'))
);
CREATE INDEX ix_founder_security_events_time
  ON production_founder_security_events(occurred_at);

CREATE FUNCTION production_reject_founder_security_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'founder security audit events are append-only' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER trg_founder_security_audit_append_only
BEFORE UPDATE OR DELETE ON production_founder_security_events
FOR EACH ROW EXECUTE FUNCTION production_reject_founder_security_mutation();

COMMENT ON TABLE production_founder_sessions IS 'Opaque, expiring, server-side founder sessions; only keyed hashes are stored.';
COMMENT ON TABLE production_founder_auth_control IS 'Global TOTP replay counter; a TOTP step may only be consumed once.';
COMMENT ON TABLE production_founder_security_events IS 'Append-only, non-secret founder authentication audit events.';

