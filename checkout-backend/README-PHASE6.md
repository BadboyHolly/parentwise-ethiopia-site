# Phase 6 — Final End-to-End QA Acceptance

**QA ACCEPTED — 10 October 2026. Production NOT APPROVED.**

Continued the accepted Phase 1–5 project. All 15 required Phase 6 gates passed against actual sales/checkout assets, a disposable PostgreSQL 18 API, ephemeral synthetic founder credentials and desktop/mobile Chromium. Chrome also verified the deployed sales-to-checkout path and canonical checkout release. No real founder credentials or new live QA orders were needed.

## Reproducible evidence

- [Final accepted Phase 6 run 38060295826](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38060295826) — SUCCESS on `21f06fab5b284bf4ce763786bca4032daad2fc21`.
- [Full Phase 1–5 regression and PostgreSQL concurrency](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38060295826/job/114237022689): 12 reconciliation, 8 fulfillment, 16 founder, 25 order and 4 PostgreSQL quota tests, **65 passed**. The existing order suite uses disposable SQLite; the browser/race/rollback coverage additionally exercises actual PostgreSQL.
- [Customer/founder journey and database restoration](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38060295826/job/114237022484): actual checkout creation for bank and Telebirr, injected 503, committed response loss, refresh/idempotent recovery, private manual copy, discrepancy rejection, independent comparison/explicit approval, eligible queue, prepare/failure/retry/dispatch/receipt, customer/founder consistency, cross-customer privacy and logout.
- Same job: actual UPDATE/DELETE rejection on migrated payment/fulfillment audits; price/currency/version/state constraints; transaction rollback plus quota preservation; concurrent duplicate requests; safe repeated and populated Phase 1 migrations; pg_dump/pg_restore exact per-table row/hash comparison and restored triggers.
- [Live anonymous security and desktop/mobile browser](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38060295826/job/114237022657): health/readiness 200, protected access denied, no-store, CSP, keyboard focus and layout.
- [Sanitized screenshot and database manifest](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38060295826/artifacts/11672906456), retained until 9 November 2026.
- [Phase 5 regression after the fix](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38060295868) — SUCCESS; [original acceptance](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38058300716) preserved.

## Acceptance gates

| Gate | Result |
|---|---|
| Sales page to checkout; fictional 1,500 ETB order | PASS |
| Refresh/interruption, duplicate submissions and private recovery | PASS |
| Incorrect payments rejected; independent ledger comparison and explicit approval | PASS |
| Eligible queue; dummy preparation, hypothetical dispatch and simulated receipt | PASS |
| Delivery failure and controlled retry | PASS |
| Customer/founder state and package-version consistency | PASS |
| Customer token privacy, cross-order denial and no founder privileges | PASS |
| Authentication, CSRF/origin, expiry/revocation, replay and concurrency | PASS |
| Database constraints and immutable reconciliation/fulfillment audit history | PASS |
| Desktop/mobile accessibility basics and safe errors | PASS |
| No real payment/refund/Telegram send/paid PDF access in QA | PASS |
| Additional migrations, transaction rollback and disposable backup restoration | PASS |

## Resolved defect P6-01

Clipboard denial previously left customers unable to manually save the separate private recovery token. The explicit Copy PRIVATE recovery code action now exposes a readonly selected manual-copy field only if clipboard access fails. It is initially empty/hidden; Hide private code clears it and restores focus. Order changes clear the visible code. The token never enters a URL or public response. Desktop/mobile tests force denial and verify the exact private code without logging it.

[Fix commit 21f06fab](https://github.com/BadboyHolly/parentwise-ethiopia-site/commit/21f06fab5b284bf4ce763786bca4032daad2fc21).

QA frontend `srv-dav78a59fdbs73bkroa0`: deployment `dep-db54rsp42hec73fnq4j0` LIVE on the fix commit; finished 14:38:54 UTC / 17:38:54 Addis Ababa.
QA backend `srv-db4e2ajl550s73bf20m0`: existing deployment `dep-db5310favr4c73f9e0mg` LIVE on `8a67ff004e29a674252335c1d124ac864ba2c5b8`. Backend runtime and migrations were unchanged; no redeploy needed.

## Boundaries and production gaps

No unresolved required QA gate remains. APP_MODE=qa and PAYMENTS_ENABLED=false remain mandatory. No live data backup/restore, hosting purchase/migration, real financial action, Telegram send, paid PDF delivery or production configuration change occurred.

Disposable restoration is proven; managed Render recovery/PITR, operational encrypted off-site retention, long-term availability and production capacity remain unvalidated. Render documents [free-service limitations](https://render.com/docs/free) and [backup limitations](https://render.com/docs/postgresql-backups). The actual database tier/expiry date was not independently read in this task.

Production requires actual settled-payment verification and reference uniqueness; buyer/recipient identity binding; private final versioned Amharic files; approved Telegram dispatch/receipt/failure operations; refund, terms and privacy approval; durable database/hosting/backups; monitoring, least-privilege access, comprehensive security audit protection, dependency management and separate final-environment acceptance. Login audit records do not have the same DB append-only trigger as financial/delivery events. Functional Chromium accessibility checks do not claim complete WCAG or multi-browser certification.

Founder decisions next: payment/refund policy; final product and delivery authorization; durability/recovery budget; separate production implementation authorization. No repeat of accepted QA tests is required.

See [Task 05 milestone tracker](TASK05-MILESTONES.md).
