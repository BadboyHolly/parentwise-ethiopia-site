-- Production payment/delivery foundation. Apply only after 0001 in the isolated production checkout database.
-- This migration adds side tables and triggers; production_orders remains AWAITING_PAYMENT-only.
CREATE TABLE production_payment_fulfillment_state (
    order_id VARCHAR(36) PRIMARY KEY REFERENCES production_orders(id) ON DELETE RESTRICT,
    payment_status VARCHAR(24) NOT NULL DEFAULT 'AWAITING_PAYMENT',
    fulfillment_status VARCHAR(24) NOT NULL DEFAULT 'LOCKED',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_prod_payment_state CHECK (payment_status IN
      ('AWAITING_PAYMENT','UNDER_REVIEW','PAYMENT_REJECTED','PAYMENT_CONFIRMED')),
    CONSTRAINT ck_prod_fulfillment_state CHECK (fulfillment_status IN
      ('LOCKED','READY_TO_DOWNLOAD','REVOKED')),
    CONSTRAINT ck_prod_fulfillment_requires_approval CHECK
      (fulfillment_status = 'LOCKED' OR payment_status = 'PAYMENT_CONFIRMED')
);
CREATE INDEX ix_prod_payment_state_status ON production_payment_fulfillment_state(payment_status);

CREATE TABLE production_payment_claims (
    id UUID PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL REFERENCES production_orders(id) ON DELETE RESTRICT,
    payment_method VARCHAR(16) NOT NULL,
    amount_etb INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL,
    reference_digest CHAR(64) NOT NULL UNIQUE,
    reference_ciphertext TEXT NOT NULL,
    claim_status VARCHAR(24) NOT NULL DEFAULT 'SUBMITTED',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_prod_claim_method CHECK (payment_method IN ('telebirr','bank')),
    CONSTRAINT ck_prod_claim_amount CHECK (amount_etb = 1500),
    CONSTRAINT ck_prod_claim_currency CHECK (currency = 'ETB'),
    CONSTRAINT ck_prod_claim_reference_digest CHECK (reference_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_prod_claim_ciphertext CHECK (length(reference_ciphertext) BETWEEN 1 AND 4096),
    CONSTRAINT ck_prod_claim_status CHECK
      (claim_status IN ('SUBMITTED','EVIDENCE_RECORDED','APPROVED','REJECTED')),
    CONSTRAINT uq_prod_claim_id_order UNIQUE (id, order_id)
);
CREATE INDEX ix_prod_payment_claims_order_time ON production_payment_claims(order_id, submitted_at DESC);

CREATE TABLE production_settlement_evidence (
    id UUID PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL REFERENCES production_orders(id) ON DELETE RESTRICT,
    claim_id UUID NOT NULL,
    reference_digest CHAR(64) NOT NULL UNIQUE,
    payment_method VARCHAR(16) NOT NULL,
    amount_etb INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL,
    recipient_digest CHAR(64) NOT NULL,
    payer_identity_digest CHAR(64) NOT NULL,
    evidence_source VARCHAR(32) NOT NULL,
    evidence_note_ciphertext TEXT NOT NULL DEFAULT '',
    settled_at TIMESTAMPTZ NOT NULL,
    observed_by VARCHAR(80) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_prod_evidence_claim_order FOREIGN KEY (claim_id, order_id)
      REFERENCES production_payment_claims(id, order_id) ON DELETE RESTRICT,
    CONSTRAINT uq_prod_evidence_id_order UNIQUE (id, order_id),
    CONSTRAINT uq_prod_evidence_id_order_claim UNIQUE (id, order_id, claim_id),
    CONSTRAINT ck_prod_evidence_method CHECK (payment_method IN ('telebirr','bank')),
    CONSTRAINT ck_prod_evidence_amount CHECK (amount_etb > 0),
    CONSTRAINT ck_prod_evidence_currency CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_prod_evidence_reference_digest CHECK (reference_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_prod_evidence_recipient_digest CHECK (recipient_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_prod_evidence_payer_digest CHECK (payer_identity_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_prod_evidence_source CHECK (evidence_source IN ('TELEBIRR_PORTAL','BANK_STATEMENT')),
    CONSTRAINT ck_prod_evidence_observer CHECK (length(observed_by) BETWEEN 1 AND 80),
    CONSTRAINT uq_prod_evidence_claim UNIQUE (claim_id)
);
CREATE INDEX ix_prod_evidence_order_time ON production_settlement_evidence(order_id, observed_at DESC);

CREATE TABLE production_third_party_payer_exceptions (
    id UUID PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL,
    claim_id UUID NOT NULL,
    evidence_id UUID NOT NULL UNIQUE,
    relationship VARCHAR(16) NOT NULL,
    rationale TEXT NOT NULL,
    documented_by VARCHAR(80) NOT NULL,
    documented_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_prod_exception_claim_order FOREIGN KEY (claim_id, order_id)
      REFERENCES production_payment_claims(id, order_id) ON DELETE RESTRICT,
    CONSTRAINT fk_prod_exception_evidence_order_claim FOREIGN KEY (evidence_id, order_id, claim_id)
      REFERENCES production_settlement_evidence(id, order_id, claim_id) ON DELETE RESTRICT,
    CONSTRAINT ck_prod_exception_relationship CHECK (relationship IN ('SPOUSE','RELATIVE','OTHER')),
    CONSTRAINT ck_prod_exception_rationale CHECK (length(btrim(rationale)) BETWEEN 10 AND 1000),
    CONSTRAINT ck_prod_exception_documenter CHECK (length(documented_by) BETWEEN 1 AND 80)
);

CREATE TABLE production_founder_approval_decisions (
    id UUID PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL,
    claim_id UUID NOT NULL,
    evidence_id UUID,
    decision VARCHAR(8) NOT NULL,
    founder_id VARCHAR(80) NOT NULL,
    reason TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_prod_decision_claim_order FOREIGN KEY (claim_id, order_id)
      REFERENCES production_payment_claims(id, order_id) ON DELETE RESTRICT,
    CONSTRAINT fk_prod_decision_evidence_order FOREIGN KEY (evidence_id, order_id)
      REFERENCES production_settlement_evidence(id, order_id) ON DELETE RESTRICT,
    CONSTRAINT uq_prod_decision_id_order_kind UNIQUE (id, order_id, decision),
    CONSTRAINT ck_prod_decision_type CHECK (decision IN ('APPROVE','REJECT')),
    CONSTRAINT ck_prod_decision_reason CHECK (length(btrim(reason)) BETWEEN 10 AND 1000),
    CONSTRAINT ck_prod_decision_founder CHECK (length(founder_id) BETWEEN 1 AND 80),
    CONSTRAINT ck_prod_decision_evidence CHECK (decision <> 'APPROVE' OR evidence_id IS NOT NULL),
    CONSTRAINT uq_prod_decision_per_claim UNIQUE (claim_id)
);
CREATE UNIQUE INDEX uq_prod_one_approval_per_order
  ON production_founder_approval_decisions(order_id) WHERE decision = 'APPROVE';

CREATE TABLE production_download_grants (
    id UUID PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL UNIQUE REFERENCES production_orders(id) ON DELETE RESTRICT,
    approval_decision_id UUID NOT NULL UNIQUE,
    approval_kind VARCHAR(8) NOT NULL DEFAULT 'APPROVE',
    grant_status VARCHAR(8) NOT NULL DEFAULT 'ACTIVE',
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    revoked_by VARCHAR(80),
    revoke_reason TEXT,
    CONSTRAINT fk_prod_grant_approval FOREIGN KEY
      (approval_decision_id, order_id, approval_kind)
      REFERENCES production_founder_approval_decisions(id, order_id, decision) ON DELETE RESTRICT,
    CONSTRAINT ck_prod_grant_approval_kind CHECK (approval_kind = 'APPROVE'),
    CONSTRAINT ck_prod_grant_status CHECK (grant_status IN ('ACTIVE','REVOKED')),
    CONSTRAINT ck_prod_grant_revocation CHECK
      ((grant_status = 'ACTIVE' AND revoked_at IS NULL AND revoked_by IS NULL AND revoke_reason IS NULL)
       OR (grant_status = 'REVOKED' AND revoked_at IS NOT NULL
           AND revoked_by IS NOT NULL AND length(btrim(revoke_reason)) BETWEEN 10 AND 1000))
);

CREATE TABLE production_payment_audit_events (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL REFERENCES production_orders(id) ON DELETE RESTRICT,
    event_type VARCHAR(48) NOT NULL,
    actor_type VARCHAR(12) NOT NULL,
    actor_id VARCHAR(80),
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_prod_audit_actor_type CHECK (actor_type IN ('CUSTOMER','FOUNDER','SYSTEM')),
    CONSTRAINT ck_prod_audit_event_type CHECK (length(event_type) BETWEEN 1 AND 48)
);
CREATE INDEX ix_prod_payment_audit_order_time ON production_payment_audit_events(order_id, occurred_at);

CREATE FUNCTION production_seed_payment_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO production_payment_fulfillment_state(order_id)
  VALUES (NEW.id) ON CONFLICT (order_id) DO NOTHING;
  RETURN NEW;
END;
$$;
INSERT INTO production_payment_fulfillment_state(order_id)
SELECT id FROM production_orders ON CONFLICT (order_id) DO NOTHING;
CREATE TRIGGER trg_production_seed_payment_state
AFTER INSERT ON production_orders FOR EACH ROW EXECUTE FUNCTION production_seed_payment_state();

CREATE FUNCTION production_guard_payment_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.order_id <> OLD.order_id THEN
    RAISE EXCEPTION 'order state identity is immutable' USING ERRCODE = '23514';
  END IF;
  IF NEW.payment_status <> OLD.payment_status AND NOT (
      (OLD.payment_status IN ('AWAITING_PAYMENT','PAYMENT_REJECTED') AND NEW.payment_status = 'UNDER_REVIEW')
      OR (OLD.payment_status = 'UNDER_REVIEW' AND NEW.payment_status IN ('PAYMENT_CONFIRMED','PAYMENT_REJECTED'))
  ) THEN
    RAISE EXCEPTION 'unauthorized payment state transition' USING ERRCODE = '23514';
  END IF;
  IF NEW.payment_status = 'PAYMENT_CONFIRMED' AND NOT EXISTS (
      SELECT 1 FROM production_founder_approval_decisions d
      WHERE d.order_id = NEW.order_id AND d.decision = 'APPROVE'
  ) THEN
    RAISE EXCEPTION 'payment confirmation requires founder approval' USING ERRCODE = '23514';
  END IF;
  IF NEW.payment_status = 'PAYMENT_REJECTED' AND NOT EXISTS (
      SELECT 1 FROM production_founder_approval_decisions d
      WHERE d.order_id = NEW.order_id AND d.decision = 'REJECT'
  ) THEN
    RAISE EXCEPTION 'payment rejection requires founder decision' USING ERRCODE = '23514';
  END IF;
  IF NEW.fulfillment_status <> OLD.fulfillment_status AND NOT (
      (OLD.fulfillment_status = 'LOCKED' AND NEW.fulfillment_status = 'READY_TO_DOWNLOAD'
       AND NEW.payment_status = 'PAYMENT_CONFIRMED')
      OR (OLD.fulfillment_status = 'READY_TO_DOWNLOAD' AND NEW.fulfillment_status = 'REVOKED')
  ) THEN
    RAISE EXCEPTION 'unauthorized fulfillment state transition' USING ERRCODE = '23514';
  END IF;
  IF NEW.fulfillment_status = 'READY_TO_DOWNLOAD' AND NOT EXISTS (
      SELECT 1 FROM production_founder_approval_decisions d
      WHERE d.order_id = NEW.order_id AND d.decision = 'APPROVE'
  ) THEN
    RAISE EXCEPTION 'download state requires founder approval' USING ERRCODE = '23514';
  END IF;
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;
CREATE TRIGGER trg_guard_production_payment_state
BEFORE UPDATE ON production_payment_fulfillment_state
FOR EACH ROW EXECUTE FUNCTION production_guard_payment_state();

CREATE FUNCTION production_guard_download_grant() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_status VARCHAR(24);
BEGIN
  SELECT fulfillment_status INTO current_status
    FROM production_payment_fulfillment_state WHERE order_id = NEW.order_id FOR UPDATE;
  IF TG_OP = 'INSERT' THEN
    IF NEW.grant_status <> 'ACTIVE' OR current_status <> 'READY_TO_DOWNLOAD' THEN
      RAISE EXCEPTION 'active grant requires approved ready order' USING ERRCODE = '23514';
    END IF;
  ELSE
    IF OLD.grant_status <> 'ACTIVE' OR NEW.grant_status <> 'REVOKED'
       OR current_status <> 'REVOKED'
       OR NEW.order_id <> OLD.order_id
       OR NEW.approval_decision_id <> OLD.approval_decision_id THEN
      RAISE EXCEPTION 'grant may only be revoked once after state revocation' USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER trg_guard_production_download_grant
BEFORE INSERT OR UPDATE ON production_download_grants
FOR EACH ROW EXECUTE FUNCTION production_guard_download_grant();

CREATE FUNCTION production_reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'payment audit events are append-only' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER trg_production_audit_no_update_delete
BEFORE UPDATE OR DELETE ON production_payment_audit_events
FOR EACH ROW EXECUTE FUNCTION production_reject_audit_mutation();

COMMENT ON TABLE production_orders IS 'Server-priced intake only. Status remains AWAITING_PAYMENT; payment and fulfillment are separate.';
COMMENT ON TABLE production_payment_fulfillment_state IS 'Separate guarded payment and fulfillment state. Production routes remain feature-gated off.';
COMMENT ON TABLE production_payment_claims IS 'Private customer claim; reference is encrypted separately and never constitutes payment confirmation.';
COMMENT ON TABLE production_settlement_evidence IS 'Founder-recorded independent settlement observation; not itself payment approval.';
COMMENT ON TABLE production_third_party_payer_exceptions IS 'Documented founder exception required when payer identity differs from buyer.';
COMMENT ON TABLE production_founder_approval_decisions IS 'Explicit authenticated founder approval/rejection with independent evidence linkage.';
COMMENT ON TABLE production_download_grants IS 'One revocable grant per order, requiring an APPROVE decision and ready state.';
COMMENT ON TABLE production_payment_audit_events IS 'Append-only event history for payment, exception, approval and fulfillment transitions.';
