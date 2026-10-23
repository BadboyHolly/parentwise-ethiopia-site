-- V1 manual Telegram fulfillment. This is separate from deferred web-download grants.
CREATE TABLE production_manual_deliveries (
    order_id VARCHAR(36) PRIMARY KEY REFERENCES production_orders(id) ON DELETE RESTRICT,
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    updated_by VARCHAR(80) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    CONSTRAINT ck_manual_delivery_status CHECK (status IN
      ('PENDING','PREPARING','SENT','DELIVERED','FAILED')),
    CONSTRAINT ck_manual_delivery_actor CHECK (length(updated_by) BETWEEN 1 AND 80),
    CONSTRAINT ck_manual_delivery_timestamps CHECK
      ((status NOT IN ('SENT','DELIVERED') OR sent_at IS NOT NULL) AND
       (status <> 'DELIVERED' OR delivered_at IS NOT NULL))
);
CREATE INDEX ix_manual_delivery_status_updated
    ON production_manual_deliveries(status, updated_at DESC);

CREATE TABLE production_manual_delivery_events (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL REFERENCES production_orders(id) ON DELETE RESTRICT,
    old_status VARCHAR(16),
    new_status VARCHAR(16) NOT NULL,
    actor_id VARCHAR(80) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_manual_delivery_event_status CHECK
      (new_status IN ('PENDING','PREPARING','SENT','DELIVERED','FAILED')),
    CONSTRAINT ck_manual_delivery_event_actor CHECK (length(actor_id) BETWEEN 1 AND 80)
);
CREATE INDEX ix_manual_delivery_events_order_time
    ON production_manual_delivery_events(order_id, occurred_at);

CREATE FUNCTION production_guard_manual_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE payment_state VARCHAR(24);
BEGIN
  SELECT payment_status INTO payment_state
    FROM production_payment_fulfillment_state WHERE order_id=NEW.order_id FOR UPDATE;
  IF payment_state <> 'PAYMENT_CONFIRMED' OR NOT EXISTS (
      SELECT 1 FROM production_founder_approval_decisions d
       WHERE d.order_id=NEW.order_id AND d.decision='APPROVE'
  ) THEN
    RAISE EXCEPTION 'manual delivery requires founder-approved payment' USING ERRCODE='23514';
  END IF;
  IF TG_OP='INSERT' THEN
    IF NEW.status <> 'PENDING' THEN
      RAISE EXCEPTION 'manual delivery must start pending' USING ERRCODE='23514';
    END IF;
  ELSE
    IF NEW.order_id <> OLD.order_id OR NOT (
       (OLD.status='PENDING' AND NEW.status='PREPARING') OR
       (OLD.status='PREPARING' AND NEW.status IN ('SENT','FAILED')) OR
       (OLD.status='SENT' AND NEW.status IN ('DELIVERED','FAILED')) OR
       (OLD.status='FAILED' AND NEW.status='PREPARING')
    ) THEN
      RAISE EXCEPTION 'invalid manual delivery transition' USING ERRCODE='23514';
    END IF;
    NEW.updated_at=now();
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER trg_guard_manual_delivery
BEFORE INSERT OR UPDATE ON production_manual_deliveries
FOR EACH ROW EXECUTE FUNCTION production_guard_manual_delivery();

CREATE FUNCTION production_reject_manual_delivery_event_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'manual delivery history is append-only' USING ERRCODE='23514';
END;
$$;
CREATE TRIGGER trg_manual_delivery_events_append_only
BEFORE UPDATE OR DELETE ON production_manual_delivery_events
FOR EACH ROW EXECUTE FUNCTION production_reject_manual_delivery_event_mutation();

COMMENT ON TABLE production_manual_deliveries IS
  'V1 founder-recorded Telegram delivery state; no Telegram API integration or website download is implied.';
COMMENT ON TABLE production_manual_delivery_events IS
  'Append-only founder actions for manual delivery; contains no message body, customer PII, or payment evidence.';
