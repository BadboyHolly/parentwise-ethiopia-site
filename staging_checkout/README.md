# Isolated checkout integration (CI only)

This package extends the independent order-intake API for **staging tests only**. It does not import, call, or connect to the existing QA service or database. It must never be deployed publicly.

## Safety boundary

The app refuses to start unless `APP_MODE=staging`, `PAYMENTS_ENABLED=false`, `STAGING_ORDER_INTAKE_ENABLED=true`, a PostgreSQL URL, synthetic founder credentials, and a HTTPS allowlist are supplied. The CI workflow creates a fresh disposable PostgreSQL service and synthetic founder username/password/TOTP and order-token secrets. There are no production credentials or payment-provider calls.

Staging injects only `QA-TELEBIRR-ONLY` / `QA-CBE-ONLY` recipient codes. It rejects references outside the `SIM-...` namespace. The customer claim and simulated settlement evidence are distinct records; matching checks reference, saved order method, 1,500 ETB, currency, fake recipient code and fictional payer identity.

Founder check and approve are separate. Only explicit approval issues a grant. Status, claim, founder session, verification, audit, download-grant and rate-limit state is held in isolated `staging_*` tables. The underlying order row remains `AWAITING_PAYMENT`. Every download rechecks the original private order token and grant. Five QA PDFs are generated in memory, marked as demos, and returned with `Cache-Control: private, no-store`.

## Test and migration

CI applies `production_checkout/migrations/0001_create_orders.sql` and then `staging_checkout/migrations/0001_stage_sidecar.sql` to disposable databases. It runs the independent order API's SQLite/PostgreSQL acceptance suite and the staging journey tests. The stage workflow has a push trigger restricted to `staging/secure-website-delivery-20261019`; it never deploys or contacts Render.

To run locally, use only an empty disposable PostgreSQL database and synthetic values. Never use the production or existing QA database, real customer data, real provider references, or final product PDFs.


## Amharic browser acceptance

The isolated browser copy at `staging_checkout/ui/checkout.html` is copied from the authoritative visual-review source `preview/checkout-amharic-review-20261019` (source head `4253b937a3c2c005ab1b0b605c80a533a0b00b40`). Existing Amharic wording, SurGraphics font references, approved visual design, and official logos are retained. The staging copy strips real recipient account/name values and uses QA-only recipient codes after order creation. New flow/status/founder-console strings are visibly marked temporary English staging placeholders for founder review.

CI runs Playwright against HTTPS localhost and the disposable PostgreSQL service at 320, 360, 390, 768, and 1280px. It captures review, pending, and ready screenshots; exercises retries, reference claims, founder verification, five dummy downloads, access denial, and revocation; then uploads screenshots, synthetic dummy downloads, and logs as a short-lived workflow artifact. It does not contact the public Amharic preview or Render.
