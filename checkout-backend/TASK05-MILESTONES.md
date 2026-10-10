# Task 05 — Website & Funnel Milestones

| Milestone | Status |
|---|---|
| Phase 1 — Persistent Order API | QA ACCEPTED, preserved |
| Phase 2 — Checkout integration | QA ACCEPTED, preserved |
| Phase 3 — Founder administration | QA ACCEPTED, preserved |
| Phase 4 — Simulated payment reconciliation | QA ACCEPTED, preserved |
| Phase 5 — Dummy fulfillment | **QA ACCEPTED — 10 October 2026** |
| Phase 6 — Final end-to-end QA | **QA ACCEPTED — 10 October 2026** |
| Production launch | **NOT APPROVED** |

## Phase 6 acceptance record

All 15 required QA gates passed. Final accepted code/test revision: `21f06fab5b284bf4ce763786bca4032daad2fc21`.

- [Final Phase 6 run 38060295826](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38060295826): three successful jobs, 65 regression tests, complete synthetic desktop/mobile customer/founder journey, actual audit edit rejection, transaction rollback/retry, migration preservation and complete disposable PostgreSQL backup/restore.
- [Phase 5 regression after the fix](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38060295868): successful; original [Phase 5 acceptance](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38058300716) preserved.
- P6-01 private recovery with denied clipboard: fixed and retested on desktop/mobile; hidden readonly manual-copy fallback with explicit clearing.
- QA frontend deployment `dep-db54rsp42hec73fnq4j0` is LIVE; canonical checkout verified in Chrome. Existing backend deployment `dep-db5310favr4c73f9e0mg` unchanged and healthy.
- No new live QA orders, real payments/refunds, Telegram sends, paid PDFs, hosting changes or production activation.
- [Phase 6 evidence and boundaries](README-PHASE6.md). Production launch remains NOT APPROVED.

## Completed Phase 6 execution scope

Continue this repository and existing services. Keep APP_MODE=qa and PAYMENTS_ENABLED=false. Preserve accepted founder evidence and do not ask the founder to repeat it.

1. Completed: built a disposable disposable PostgreSQL end-to-end acceptance journey from the actual sales page and checkout files. Use synthetic founder factors and customer data; preserve the private token only inside the test session.
2. Completed: covered order creation at 1,500 ETB, interruption/recovery, mismatched and matching synthetic ledger credit, explicit verification, enrollment, dummy dispatch, receipt, failure and retry. Check backend, founder dashboard and customer status consistency at each stage.
3. Completed: asserted no public response includes customer personal data, founder notes, financial reference or internal audit entries; prove cross-order token denial and no founder privileges from customer tokens.
4. Completed: exercised session revocation, idle/absolute expiry, CSRF and origin checks. Test PostgreSQL duplicate actions and migration constraints, including attempts to UPDATE/DELETE an audit event in an isolated fully migrated schema.
5. Completed: tested desktop and mobile, keyboard navigation, validation/error focus, accessible status announcements, slow/unavailable API responses and safe idempotent retry. Verify absence of real payment collection, Telegram operations and paid file access.
6. Completed: ran relevant Phases 1–5 regressions and preserve sanitized logs/screenshots. Use non-invasive live probes. Create at most one live fictional order only if a remaining deployment-specific question requires it; do not rerun quota-consuming workflows casually.
7. Completed: recorded a separate Phase 6 QA ACCEPTED decision. Production-only recovery, availability, money and delivery gates remain outside QA acceptance.

Production work remains separate: independently verified real payment controls, purchaser/recipient identity binding, private versioned PDFs, actual Telegram operating procedures, refunds/terms/privacy approvals, final Amharic resources and genuine review claims, durable database hosting/backups/restoration, production rate limiting and final-environment acceptance. No production activation is authorized by this report.

## Next milestone — separately authorized production readiness

Founder decisions: (1) real payment verification and refund/terms ownership, (2) final versioned Amharic product and recipient/Telegram delivery policy, (3) durable hosting/database/backup budget and recovery targets, (4) explicit authorization for production implementation and final acceptance. Do not request repetition of accepted QA tests or activate real payments/delivery on the strength of this tracker.
