# ParentWise Ethiopia — independent checkout architecture

**Code-only development prototype. No public production service is deployed. Real order intake, payment verification, and final PDF delivery remain disabled.**

The independent order API in this directory is separate from `checkout-backend/`. It does not use the QA service or its database at runtime.

## Order intake

- `POST /api/v1/orders` creates a server-priced 1,500 ETB order in `AWAITING_PAYMENT` and returns a private recovery token.
- `GET /api/v1/orders/{code}` requires that token. Order code alone does not reveal an order.
- Production startup requires `APP_MODE=production` and `PAYMENTS_ENABLED=false`; `ORDER_INTAKE_ENABLED` defaults to false.
- Order state is intentionally constrained to unverified. A customer payment reference is not payment confirmation.

## Fulfillment architecture

The locked V1 path is **order → independent settlement verification → authenticated founder approval → manual Telegram delivery → founder-recorded delivery status**. Evidence recording is not approval. The production founder router is mounted only when `FOUNDER_AUTH_ENABLED=true`; state-changing decisions additionally require `FOUNDER_APPROVAL_ENABLED=true`, session authentication, CSRF and exact HTTPS Origin checks. Both gates remain false for deployment preparation.

An approved V1 Telegram decision leaves the website fulfillment state `LOCKED`, creates no download grant, and creates a separate `PENDING` row in `production_manual_deliveries`. Delivery statuses are `PENDING`, `PREPARING`, `SENT`, `DELIVERED`, and `FAILED`; delivery history is append-only. The founder performs the actual Telegram send outside this application.

Website download and R2 storage remain deferred. The legacy `website_download` service mode and download-grant checks remain available only for a separately reviewed future release. The V1 founder HTTP route explicitly selects `manual_telegram`, so approval cannot accidentally authorize those downloads. No production R2 bucket, credentials, PDFs, or download route are configured here.

## Isolated staging integration

The new `staging_checkout/` package composes the independent order API with staging-only payment-claim, founder-verification, authorization, download, audit and abuse-control modules. It uses the same disposable staging PostgreSQL instance, with separate `staging_*` sidecar tables. It has no runtime dependency on the QA backend or QA database.

Staging requires `APP_MODE=staging`, `PAYMENTS_ENABLED=false`, `STAGING_ORDER_INTAKE_ENABLED=true`, a disposable PostgreSQL URL, synthetic founder factors and an explicit HTTPS origin allowlist. It injects only fictional QA recipient codes. It generates five marked dummy PDFs at request time; no PDF asset is stored under this repository’s public/static paths. GitHub Actions is the only execution environment for the acceptance journey; no public staging service is configured.

The staging extension is not a production activation path. It must not be imported by `from_environment()` or mounted by production startup. Keep production intake, claims, founder approval and downloads closed until every founder release gate is accepted.

## Operations and release blockers

Production requires separate, reviewed migrations and private PostgreSQL; high-entropy order-token keys; founder MFA and recovery; rate limiting at a verified proxy boundary; private immutable-release PDF storage; revocable per-request authorization; privacy and retention rules; monitoring; tested backups/restoration; and founder-approved payment, identity, refund and support policies.

See [the production checkout contract](../checkout-backend/PRODUCTION-CHECKOUT-CONTRACT.md) for the complete journey and release gates.

For AletCloud's 512 MiB App Pro preparation, bounded PostgreSQL pools, startup command, health checks, migration sequence and synthetic backup/restore procedure, see [AletCloud deployment preparation](ALETCLOUD-DEPLOYMENT.md). PostgreSQL 16+ is the tested target; all feature gates remain closed.


## Private PDF storage preparation

`private_storage.py` defines a S3-compatible Cloudflare R2 reader using immutable release-specific keys and an exact-five-file SHA-256 manifest. It does not depend on bucket versioning or VersionId support. It is not constructed by production startup, does not hold credentials or final PDFs, and has no public/presigned URL flow. The isolated staging download endpoint uses generated in-memory QA PDFs through the mock storage implementation; it revalidates the customer token, approval state, and grant for every request. The R2 adapter has mock-only tests and is not connected to the named bucket.

Publishing uses conditional create-only writes. Separate protected backups and a checksum-verified restore rehearsal are required before launch. See [R2 secure delivery runbook](R2-SECURE-DELIVERY.md). Production payment/grant state and route wiring, private bucket credentials, final files, real-provider backup/restore acceptance, and production acceptance remain release blockers.


## Production payment and delivery state

`payment_state.py` and migrations `0002_create_payment_delivery_state.sql` and `0003_create_founder_security.sql` add separate claim, settlement evidence, decision, exception, session and audit structures without changing order intake. Migration `0004_manual_telegram_fulfillment.sql` adds Telegram delivery records and append-only state history. These are private operational records, not payment integrations or Telegram API calls.

Founder MFA, CSRF-protected review/approval routes, managed AES-GCM field encryption, session controls, delivery transitions, and verified-payment reporting are implemented behind disabled feature gates. The separate website-download route path remains deferred and must not be enabled for V1. Secret provisioning, AletCloud acceptance, UI integration, manual fulfillment rehearsal, independent security review, and production launch remain outstanding.

The production founder API also supports an authenticated exact order lookup at `GET /api/v1/founder/orders/search?q=PW-…` and a Telegram-reported claim at `POST /api/v1/founder/claims/telegram`. The claim route requires founder session, CSRF/origin validation, and the existing founder approval gate; it stores the transaction reference using the same AES-GCM envelope and global HMAC duplicate constraint as customer claims. It records a `PAYMENT_CLAIM_RECORDED_TELEGRAM` append-only audit event, then exposes the claim to `/claims/pending` for the existing independent settlement evidence and approve/reject workflow. The response explicitly says `UNDER_REVIEW_NOT_PAYMENT_CONFIRMATION`; it creates no revenue, settlement evidence, approval, delivery row, or download grant.

The deployed production package contains an API, not a founder HTML/JS admin interface. `checkout-backend/api/admin-ui.html` and `admin-ui.js` belong to the separate QA backend and are not production-compatible routes. The separately developed production founder UI must use the route contract above and existing `/claims/pending`, `/settlements`, `/approve`, `/reject`, `/deliveries/pending`, and `/deliveries/status` endpoints; UI integration remains a release acceptance item.
