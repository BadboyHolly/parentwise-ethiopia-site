# ParentWise Ethiopia — independent checkout architecture

**Code-only development prototype. No public production service is deployed. Real order intake, payment verification, and final PDF delivery remain disabled.**

The independent order API in this directory is separate from `checkout-backend/`. It does not use the QA service or its database at runtime.

## V1 business decision — 21 October 2026 (implementation pending)

The founder has locked a **manual Telegram fulfillment pilot**: collect full name + Ethiopian phone + chosen method; show selected Telebirr/CBE transfer instructions **once**; buyer submits receipt or transaction reference to the official private Telegram conversation; founder independently matches settled funds, records the reviewed transfer, and then sends all five PDFs manually in that same private conversation. Explain the Telegram requirement and a viable non-Telegram alternative **before** requesting payment. Agree on support hours/delivery window before launch. Screenshot alone never proves payment, and duplicate references must not be fulfilled twice. This is a business process decision, **not** production activation.

The historical secure website delivery design below is **retained as deferred infrastructure**. It does not override the locked V1 manual Telegram delivery plan. The existing staging/production code still implements portions of the earlier design and must not be treated as V1-ready by changing account numbers alone.

### Confirmed payment recipient configuration — pending deployment

The founder confirmed exact Telebirr and CBE recipient details and a shared account-holder name on 21 October 2026. **Do not commit live recipient numbers to this repository, its static website, preview branch, CI logs, test fixtures, screenshots or QA/staging environment.** Keep all public preview recipients fictional and obvious. Do not use the earlier superseded CBE account number.

The production order API already supports **private environment variables** supplied to `production_checkout.app.from_environment()`:

| Payment method | Production setting | Purpose |
|---|---|---|
| Telebirr | `TELEBIRR_ACCOUNT_NUMBER` | Founder-confirmed Telebirr number |
| Telebirr | `TELEBIRR_ACCOUNT_HOLDER` | Founder-confirmed account holder |
| CBE | `CBE_ACCOUNT_NUMBER` | Founder-confirmed bank account |
| CBE | `CBE_ACCOUNT_HOLDER` | Founder-confirmed account holder |

The production operator must enter the four actual values privately in the eventual production service settings, independently check recipient ownership in the corresponding financial apps, and verify their correct pairing in a private pre-launch acceptance test. The holder must match what the payment app actually displays; if it differs, **stop**, do not collect money. `APP_MODE=production`, `PAYMENTS_ENABLED=false`, `ORDER_INTAKE_ENABLED=false`, `CUSTOMER_PAYMENT_CLAIMS_ENABLED=false`, `FOUNDER_APPROVAL_ENABLED=false` and `SECURE_PDF_DELIVERY_ENABLED=false` remain the safe default. **Do not activate any gate or deploy a production service from this branch.**

### Release validation required for the manual Telegram V1

Confirm the official Telegram destination accepts private messages; rehearse the Meta/Facebook in-app browser → payment app → Telegram return; match one synthetic claim to one independent synthetic settlement record; reject reused references; log founder verification; test all five PDF documents received and reopened on typical Android phones; define refund, privacy/consent, support and delivery policies. Store customer names and phone numbers only in an authorized secure backend with an approved retention plan, not analytics or public query strings. No live transaction may proceed before an approved release decision.

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

Production requires separate, reviewed migrations and private PostgreSQL; high-entropy order-token keys; founder MFA and recovery; rate limiting at a verified proxy boundary; private immutable-release PDF storage; revocable per-request authorization; privacy and retention rules; monitoring; tested backups/restoration; and founder-approved payment, identity, refund and support policies.

See [the production checkout contract](../checkout-backend/PRODUCTION-CHECKOUT-CONTRACT.md) for the complete journey and release gates.


## Private PDF storage preparation

`private_storage.py` defines a S3-compatible Cloudflare R2 reader using immutable release-specific keys and an exact-five-file SHA-256 manifest. It does not depend on bucket versioning or VersionId support. It is not constructed by production startup, does not hold credentials or final PDFs, and has no public/presigned URL flow. The isolated staging download endpoint uses generated in-memory QA PDFs through the mock storage implementation; it revalidates the customer token, approval state, and grant for every request. The R2 adapter has mock-only tests and is not connected to the named bucket.

Publishing uses conditional create-only writes. Separate protected backups and a checksum-verified restore rehearsal are required before launch. See [R2 secure delivery runbook](R2-SECURE-DELIVERY.md). Production payment/grant state and route wiring, private bucket credentials, final files, real-provider backup/restore acceptance, and production acceptance remain release blockers.


## Production payment and delivery state foundation

`payment_state.py` and migration `0002_create_payment_delivery_state.sql` add separate production claim, settlement evidence, approval, exception, state, grant and audit structures without changing order intake. State transitions and private download authorization are implemented as unmounted service functions. They do not enable payment processing, founder decisions, delivery routes, or real orders.

See [Payment state foundation](PAYMENT-STATE-FOUNDATION.md) and [Founder verification](FOUNDER-VERIFICATION.md). Founder MFA, CSRF-protected review routes, managed AES-GCM field encryption and session controls are implemented behind disabled feature gates. Secret provisioning, live settlement operations, independent security review, STEP 6.3 delivery integration and production launch remain outstanding.
