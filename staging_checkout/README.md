# Isolated checkout integration (CI only)

This package extends the independent order-intake API for **staging tests only**. It does not import, call, or connect to the existing QA service or database. It must never be deployed publicly.

## Safety boundary

The app refuses to start unless `APP_MODE=staging`, `PAYMENTS_ENABLED=false`, `STAGING_ORDER_INTAKE_ENABLED=true`, a PostgreSQL URL, synthetic founder credentials, and a HTTPS allowlist are supplied. The CI workflow creates a fresh disposable PostgreSQL service and synthetic founder username/password/TOTP and order-token secrets. There are no production credentials or payment-provider calls.

Staging injects only `QA-TELEBIRR-ONLY` / `QA-CBE-ONLY` recipient codes. It rejects references outside the `SIM-...` namespace. The customer claim and simulated settlement evidence are distinct records; matching checks reference, saved order method, 1,500 ETB, currency, fake recipient code and fictional payer identity.

Founder check and approve are separate. Only explicit approval issues a grant. Status, claim, founder session, verification, audit, download-grant and rate-limit state is held in isolated `staging_*` tables. The underlying order row remains `AWAITING_PAYMENT`. Every download rechecks the original private order token and grant. Five QA PDFs are generated in memory, marked as demos, and returned with `Cache-Control: private, no-store`.

## Test and migration

CI applies `production_checkout/migrations/0001_create_orders.sql` and then `staging_checkout/migrations/0001_stage_sidecar.sql` to disposable databases. It runs the independent order API's SQLite/PostgreSQL acceptance suite and the staging journey tests. The stage workflow has a push trigger restricted to `staging/secure-website-delivery-20261019`; it never deploys or contacts Render.

To run locally, use only an empty disposable PostgreSQL database and synthetic values. Never use the production or existing QA database, real customer data, real provider references, or final product PDFs.
