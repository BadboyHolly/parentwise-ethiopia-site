-- Roll back only migration 0002. Never drops or alters production_orders.
DROP TRIGGER IF EXISTS trg_production_audit_no_update_delete ON production_payment_audit_events;
DROP FUNCTION IF EXISTS production_reject_audit_mutation();
DROP TRIGGER IF EXISTS trg_guard_production_download_grant ON production_download_grants;
DROP FUNCTION IF EXISTS production_guard_download_grant();
DROP TRIGGER IF EXISTS trg_guard_production_payment_state ON production_payment_fulfillment_state;
DROP FUNCTION IF EXISTS production_guard_payment_state();
DROP TRIGGER IF EXISTS trg_production_seed_payment_state ON production_orders;
DROP FUNCTION IF EXISTS production_seed_payment_state();
DROP TABLE IF EXISTS production_payment_audit_events;
DROP TABLE IF EXISTS production_download_grants;
DROP TABLE IF EXISTS production_founder_approval_decisions;
DROP TABLE IF EXISTS production_third_party_payer_exceptions;
DROP TABLE IF EXISTS production_settlement_evidence;
DROP TABLE IF EXISTS production_payment_claims;
DROP TABLE IF EXISTS production_payment_fulfillment_state;
COMMENT ON TABLE production_orders IS 'Stage 1 unverified customer orders. No paid states permitted here.';
