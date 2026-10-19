# ParentWise Ethiopia — production checkout implementation contract

**19 October 2026 — production intake, payments, and delivery remain disabled.** This document defines the release architecture and contract; it does not authorize a production service or real transactions.

## Preserved starting point

- Approved V4.14 sales page and the Amharic checkout preview remain unchanged.
- Independent order-intake prototype remains in `production_checkout/`; it creates `AWAITING_PAYMENT` orders and returns a private recovery token. Its status constraint remains unverified until settlement approval.
- The existing QA backend remains isolated. It contains fabricated ledger data and QA-only fulfillment; it is not used by the independent checkout or the staging integration at runtime.
- Staging integration is code/CI only. It is not publicly deployed.

## Customer journey and delivery decision

1. Collect only the approved minimum customer details and payment method. Show the fixed offer and founder-approved terms before order submission.
2. Create an order first through the independent order API. The server fixes amount/currency and returns an order identifier and private bearer recovery token. Retries use the same idempotency key and payload.
3. Show payment instructions only after order creation. A customer transaction reference is a **claim**, never proof or confirmation of payment.
4. Store a claim in an unverified state. Enforce one globally unique claimed transaction reference, one order association, saved server-side payment method, fixed amount/currency, claim attempt limits, and audited state transitions.
5. A founder authenticates with MFA, independently matches actual settled funds against the payment provider’s records, account, method, reference, amount, currency and buyer identity. Only an explicit founder approval can transition the order to paid.
6. After approval, issue an auditable, revocable download grant. **Secure website delivery of the five approved PDF parts is the primary fulfillment method.** Every download request rechecks the private order authorization, approved payment state and active grant; files are private, versioned and outside the public/static tree. Responses use `Cache-Control: private, no-store`.
7. Telegram is **support and fallback only**. It may help a customer recover access or be used for a documented manual delivery fallback; it is not the normal delivery path and must never receive a private order token or OTP.

The production order table remains limited to `AWAITING_PAYMENT` until the production settlement and approval modules are separately designed, migrated and accepted. Payment/fulfillment state belongs in separate modules/tables with explicit transitions and audit history.

## Independent architecture

- Keep order intake, payment claims, founder verification, authorization, and secure delivery in the independent `production_checkout` architecture. Use separate modules and a private PostgreSQL database; do not import or call the QA service and do not reuse its database, auth, ledger, secrets, order namespace or migrations.
- Customer claim endpoints may record an unverified claim only. Customer endpoints must never write a paid state or issue a download grant.
- Founder routes require a separate HTTPS origin, MFA-backed session, CSRF protection, least privilege, explicit check and approve actions, and append-only audit events.
- Download authorization requires the original private order token on every request. Store token hashes, never place tokens in URLs, analytics, logs or referrers. Revoke grants immediately; do not use public URLs or long-lived bearer URLs.
- Keep final PDFs in private, versioned storage. Staging dummy files are generated in memory or an ephemeral CI directory and are not committed or uploaded as public artifacts.
- Payment references are unique across all claims. Store the minimum data required, redact logs, encrypt sensitive values at rest, set retention limits, and use a trusted proxy boundary before deriving production abuse-control keys.
- Fail closed: `ORDER_INTAKE_ENABLED=false`, `PAYMENTS_ENABLED=false`, founder verification disabled, and delivery disabled unless each separate production release gate is explicitly approved.

## Staging contract

- The staging integration runs only with `APP_MODE=staging`, `PAYMENTS_ENABLED=false`, explicit staging order-intake opt-in, synthetic founder factors, fictional recipient codes and a disposable PostgreSQL database.
- It creates orders through the independent order API. Its claims, synthetic settlement evidence, founder sessions, audit events, grants and rate windows live in isolated staging sidecar tables in the disposable staging database.
- Fictional settlement evidence is created independently from a customer claim and must match reference, order payment method, 1,500 ETB, ETB currency, fictional recipient code and fictional payer identity.
- Staging supports exactly five generated dummy PDFs. It cannot read final product files or real recipient instructions.
- No CI job contacts Render, payment providers, production databases, real accounts or customer-facing preview services.

## Release blockers and founder decisions

- Independently confirm the settlement-account ownership and actual provider reconciliation procedure.
- Approve buyer-to-payer identity binding, including whether the private recovery token alone is sufficient or an additional verified phone step is required.
- Select private storage and retention/restore controls for the final versioned Amharic PDFs; approve file hashes and replacement/revocation procedure.
- Approve the founder MFA/session provisioning and recovery process, refund/guarantee terms, privacy notice, retention periods and incident process.
- Select production host/database, trusted-proxy boundary, rate limits, monitoring, backup/restore targets, domain and CORS allowlist.
- Complete separate production-equivalent security, abuse, migration, backup and recovery acceptance; then make an explicit launch decision.

**No merge, deployment, live order intake, real payment, or final PDF delivery is authorized by this contract or staging results.**
