# ParentWise Ethiopia — isolated order-intake prototype

**Code-only development build. No public production service is deployed. No real payment processing or product delivery.**

The approved QA orders API is under `checkout-backend/`; this independent package does not import it, query its database, or accept its synthetic ledger proof.

## What is implemented

- POST `/api/v1/orders`: validated Ethiopian name/mobile + `telebirr` or `bank` method; server-enforced product, price (1500 ETB), currency and recipient. A secure 43-character `Idempotency-Key` ensures retries of a request don't create multiple orders. Success returns new order code `PW-...`, private recovery token, and selected account information.
- GET `/api/v1/orders/{code}`: requires the separate bearer token. Code alone cannot reveal an order. No customer name or mobile returned.
- Data model only allows `AWAITING_PAYMENT`; it cannot record a paid transaction. No public payment-proof or payment-verification route exists.
- POST route starts closed unless `ORDER_INTAKE_ENABLED=true`. This flag controls **order intake only**, not any payment action.
- CI tests run disposable SQLite + PostgreSQL, including concurrency, constraints, authorization, restart persistence, CORS, and input rejection.

## Deploy gate and environment

**Not ready for release.** Service implementation intentionally has no per-client abuse/rate limiting, provider-backed independent settlement verification, operational approved refund policy, paid product private storage, recipient authentication, disaster recovery/monitoring acceptance or production secrets.

For an approved *separate* environment only, run:
```sh
pip install -r production_checkout/requirements.txt
# Apply production_checkout/migrations/0001_create_orders.sql ONCE against
# a newly provisioned independent PostgreSQL database.
APP_MODE=production PAYMENTS_ENABLED=false \
ORDER_INTAKE_ENABLED=false \
DATABASE_URL=postgresql+psycopg://... \
ORDER_TOKEN_KEY=... \
ALLOWED_ORIGINS=https://approved-frontend.example \
uvicorn production_checkout.app:from_environment --factory
```
Never use the existing QA `DATABASE_URL`, secrets, or `PW-QA-` identifiers. Configure secrets privately in the service manager rather than pasting them into GitHub, ChatGPT or a public chat. Database migration and a real backup/restore test must precede intake activation. Keep `ORDER_INTAKE_ENABLED=false` until rate limiting/abuse protection and the verified customer flow have been implemented and accepted.

## Why the preview can be interactive without handling money

The separate checkout design preview provides a **browser-only review step**. It validates entered name/mobile and payment selection, shows a confirmation summary, then returns to the form; no POST, no persisted order, no paid state. This is safe for UX review but is **not** the production customer order endpoint.

## Before creating real orders

1. Require founder-approved payment/refund and delivery terms.
2. Implement abuse control with a verified proxy trust boundary and tested rate limiting; protect PII at rest with retention/access limits.
3. Build signed release migrations, monitoring, database backup and restoration; verify production database identity and secret rotation.
4. Connect UI to this API only after a separate full-stack acceptance using controlled data and checked CORS.
5. Test provider settlement verification and buyer identity binding before accepting payment proofs or enabling final delivery.

Full founder release contract: [PRODUCTION-CHECKOUT-CONTRACT.md](../checkout-backend/PRODUCTION-CHECKOUT-CONTRACT.md).
