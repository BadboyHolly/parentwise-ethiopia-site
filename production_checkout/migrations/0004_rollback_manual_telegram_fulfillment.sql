DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM production_manual_delivery_events) OR
     EXISTS (SELECT 1 FROM production_manual_deliveries) THEN
    RAISE EXCEPTION 'manual delivery data exists; use forward recovery or restore a protected backup';
  END IF;
END;
$$;
DROP TRIGGER IF EXISTS trg_manual_delivery_events_append_only ON production_manual_delivery_events;
DROP TRIGGER IF EXISTS trg_guard_manual_delivery ON production_manual_deliveries;
DROP FUNCTION IF EXISTS production_reject_manual_delivery_event_mutation();
DROP FUNCTION IF EXISTS production_guard_manual_delivery();
DROP TABLE IF EXISTS production_manual_delivery_events;
DROP TABLE IF EXISTS production_manual_deliveries;
