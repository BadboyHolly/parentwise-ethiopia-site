DROP TRIGGER IF EXISTS trg_founder_security_audit_append_only ON production_founder_security_events;
DROP FUNCTION IF EXISTS production_reject_founder_security_mutation();
DROP TABLE IF EXISTS production_founder_security_events;
DROP TABLE IF EXISTS production_founder_rate_limits;
DROP TABLE IF EXISTS production_founder_sessions;
DROP TABLE IF EXISTS production_founder_auth_control;

