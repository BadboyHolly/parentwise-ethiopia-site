# ParentWise Ethiopia — independent checkout architecture

**Code-only development prototype. No public production service is deployed. Real order intake, payment verification, and final PDF delivery remain disabled.**

The independent order API in this directory is separate from `checkout-backend/`. It does not use the QA service or its database at runtime.

## Order intake

- `POST /api/v1/orders` creates a server-priced 1,500 ETB order in `AWAITING_PAYMENT` and returns a private recovery token.
- `GET /api/v1/orders/{code}` requires that token. Order code alone does not reveal an order.
- Production startup requires `APP_MODE=production` and `PAYMENTS_ENABLED=false`; `ORDER_INTAKE_ENABLED` defaults to false.
- Order state is intentionally constrained to unverified. A customer payment reference is not payment confirmation.

## Fulfillment architecture

Production payment claims, founder verification, customer authorization, and download delivery are separate modules and tables, isolated from order intake state. Customer claims remain unverified until a founder independently matches settlement records and explicitly approves. Approval creates a revocable grant. The website is the primary secure delivery channel; Telegram is support and documented fallback only.

## Isolated staging integration

The new `staging_checkout/` package composes the independent order API with staging-only payment-claim, founder-verification, authorization, download, audit and abuse-control modules. It uses the same disposable staging PostgreSQL instance, with separate `staging_*` sidecar tables. It has no runtime dependency on the QA backend or QA database.

Staging requires `APP_MODE=staging`, `PAYMENTS_ENABLED=false`, `STAGING_ORDER_INTAKE_ENABLED=true`, a disposable PostgreSQL URL, synthetic founder factors and an explicit HTTPS origin allowlist. It injects only fictional QA recipient codes. It generates five marked dummy PDFs at request time; no PDF asset is stored under this repository’s public/static paths. GitHub Actions is the only execution environment for the acceptance journey; no public staging service is configured.

The staging extension is not a production activation path. It must not be imported by `from_environment()` or mounted by production startup. Keep production intake, claims, founder approval and downloads closed until every founder release gate is accepted.

## Operations and release blockers

Production requires separate, reviewed migrations and private PostgreSQL; high-entropy order-token keys; founder MFA and recovery; rate limiting at a verified proxy boundary; private versioned PDF storage; revocable per-request authorization; privacy and retention rules; monitoring; tested backups/restoration; and founder-approved payment, identity, refund and support policies.

See [the production checkout contract](../checkout-backend/PRODUCTION-CHECKOUT-CONTRACT.md) for the complete journey and release gates.


## Private PDF storage preparation

`private_storage.py` defines a S3-compatible Cloudflare R2 reader using immutable release-specific keys and an exact-five-file SHA-256 manifest. It does not depend on bucket versioning or VersionId support. It is not constructed by production startup, does not hold credentials or final PDFs, and has no public/presigned URL flow. The isolated staging download endpoint uses generated in-memory QA PDFs through the mock storage implementation; it revalidates the customer token, approval state, and grant for every request. The R2 adapter has mock-only tests and is not connected to the named bucket.

Publishing uses conditional create-only writes. Separate protected backups and a checksum-verified restore rehearsal are required before launch. See [R2 secure delivery runbook](R2-SECURE-DELIVERY.md). Production payment/grant state and route wiring, private bucket credentials, final files, real-provider backup/restore acceptance, and production acceptance remain release blockers.
