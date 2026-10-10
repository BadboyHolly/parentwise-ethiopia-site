# Task 05 — Website & Funnel Milestones

| Milestone | Status |
|---|---|
| Phase 1 — Persistent Order API | QA ACCEPTED, preserved |
| Phase 2 — Checkout integration | QA ACCEPTED, preserved |
| Phase 3 — Founder administration | QA ACCEPTED, preserved |
| Phase 4 — Simulated payment reconciliation | QA ACCEPTED, preserved |
| Phase 5 — Dummy fulfillment | **QA ACCEPTED — 10 October 2026** |
| Phase 6 — Final end-to-end QA | **PENDING EXECUTION; handoff ready** |
| Production launch | **NOT APPROVED** |

## Phase 6 execution handoff

Continue this repository and existing services. Keep APP_MODE=qa and PAYMENTS_ENABLED=false. Preserve accepted founder evidence and do not ask the founder to repeat it.

1. Build a single disposable PostgreSQL end-to-end acceptance journey from the actual sales page and checkout files. Use synthetic founder factors and customer data; preserve the private token only inside the test session.
2. Cover order creation at 1,500 ETB, interruption/recovery, mismatched and matching synthetic ledger credit, explicit verification, enrollment, dummy dispatch, receipt, failure and retry. Check backend, founder dashboard and customer status consistency at each stage.
3. Assert no public response includes customer personal data, founder notes, financial reference or internal audit entries; prove cross-order token denial and no founder privileges from customer tokens.
4. Exercise session revocation, idle/absolute expiry, CSRF and origin checks. Test PostgreSQL duplicate actions and migration constraints, including attempts to UPDATE/DELETE an audit event in an isolated fully migrated schema.
5. Test desktop and mobile, keyboard navigation, validation/error focus, accessible status announcements, slow/unavailable API responses and safe idempotent retry. Verify absence of real payment collection, Telegram operations and paid file access.
6. Run relevant Phases 1–5 regressions and preserve sanitized logs/screenshots. Use non-invasive live probes. Create at most one live fictional order only if a remaining deployment-specific question requires it; do not rerun quota-consuming workflows casually.
7. Produce a separate Phase 6 acceptance decision. Any required failing/blocked check keeps Phase 6 unaccepted.

Production work remains separate: independently verified real payment controls, purchaser/recipient identity binding, private versioned PDFs, actual Telegram operating procedures, refunds/terms/privacy approvals, final Amharic resources and genuine review claims, durable database hosting/backups/restoration, production rate limiting and final-environment acceptance. No production activation is authorized by this report.
