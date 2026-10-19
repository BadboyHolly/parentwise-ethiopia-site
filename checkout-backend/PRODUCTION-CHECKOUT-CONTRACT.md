# ParentWise Ethiopia — production checkout implementation contract

**19 October 2026 — PRODUCTION NOT ENABLED.** This contract is a design and implementation gate, not an approval, live payment connector, or implementation of live order endpoints. Do not deploy the QA code as production by toggling settings.

## Preserved, verified starting state

- Approved V4.14 sales page remains at `main` and is unchanged.
- The separate approved-looking checkout **preview** runs on Render from `preview/checkout-amharic-review-20261019` with no checkout API, no POST and a disabled completion button.
- Preview visual browser acceptance at 320 / 360 / 390 / 768 / 1280 px: GitHub Actions run `39208196371` PASS; this is only client UI and simulated interaction verification.
- Existing backend `checkout-backend/api/main.py` explicitly rejects `APP_MODE != qa` or `PAYMENTS_ENABLED != false`.
- `checkout-backend/api/payment_review.py` deals in **fabricated QA ledger records** and requires founder login. It is not a Telebirr/CBE funds-settlement verification service.
- QA payment/fulfillment reports are accepted for synthetic flows, not real money, buyer identity or product delivery.

## Fixed offer and payment details

- Product: ParentWise Ethiopia digital parenting system, **one-time 1,500 ETB**. Enforce amount and currency on the server. Reject client-supplied amount, coupon or item fields unless a separate audited offer is authorized.
- Telebirr: `0912910693`, beneficiary **Kidus Elias**.
- Commercial Bank of Ethiopia: `10002230019327`, beneficiary **Kidus Elias**.
- Deliverable: five approved, versioned Amharic resources. Maintain a separate secured release artifact with hashes and authorizations; no public static file URLs for paid documents.
- Public support: `https://t.me/ParentWiseEthiopia`.
- Do not claim either bank account has been independently verified by a provider merely because numbers were supplied by the founder.

## Customer journey — required server-trusted sequence

1. Customer opens checkout from the approved sales page, enters name and Ethiopian mobile, and selects payment method. Customer sees final amount and refund terms before committing.
2. **Create a real order first.** Backend issues a unique order ID, persists sanitized minimal PII, amount 1500 ETB, currency ETB, selected method and `AWAITING_PAYMENT` status. Retain an idempotency key so double clicks/network retries cannot charge or create duplicate orders.
3. Only **after** the server acknowledges the real order, show payee and selected payment instructions with the authoritative amount and unique order ID; explain that payment itself occurs externally in official Telebirr/CBE, not inside this website.
4. Buyer makes external payment independently. They may send a screenshot/payment reference through the official Telegram channel with order ID, but **never** send their private order-recovery token or OTP. Do not treat a screenshot as proof that funds settled.
5. Associate each customer payment **claim** with exactly one order; limit attempts; reject reused transaction references globally, mismatched method or currency, invalid data, and unexpected state transitions. Upload of image files is optional and requires approved malware/file/privacy controls; Telegram screenshot alone is preferred for launch unless an audited secure upload is implemented.
6. Founder authenticates with password + TOTP and independently views settled credit in the actual Telebirr or CBE **provider records**, matching recipient account, reference, settled amount **1,500 ETB**, date, payer context and currency. Only the founder may mark `VERIFIED_PAID`; record an append-only audit with checks, who/when/reason and a unique payment reference. Do not allow customer-visible API requests to set paid states.
7. Before any PDF fulfillment, independently **bind purchaser to recipient** (prefer OTP to the purchased phone with abuse limits; otherwise document an approved alternative). Telegram username and screenshots are not sufficient proof of purchase.
8. Deliver the approved private PDF package manually using the official Telegram support channel, recording genuine dispatch and acknowledgment. Failed delivery must be retryable without duplicating a paid credit.
9. Handle cancellations and the advertised 30-day guarantee under written founder-approved policy. Expose that policy unambiguously before accepting payment.

## Production architecture: isolated, not a QA config toggle

- New production FastAPI deployment and private durable PostgreSQL database; new migrations and secrets; separate domain, CORS allowlist and founder credentials. Never reuse the QA database, synthetic ledger, QA test references or order-code namespace.
- Creation endpoint accepts only `customer_name`, `mobile`, `payment_method` plus a high-entropy `Idempotency-Key`. Server computes product/amount; writes orders atomically with rate limit and unique request fingerprint; returns an authenticated, non-PII summary plus private recovery token.
- Public status endpoint requires a separate bearer token (not order ID alone). Customer cannot enumerate orders, payment references or phone numbers, and cannot perform founder actions.
- Separate founder-origin HTTPS console with secure sessions, MFA, CSRF, least-privilege, independent real-world payment checks and immutable financial/fulfillment event logs. No secrets in URLs, localStorage, analytics, third-party pixels or logs.
- If a claim endpoint is deployed, it can record **unverified claims only**; it cannot mark paid, trigger delivery or accept a claim as settled based on the customer screenshot.
- Abuse controls: trusted-boundary source-IP verification (or equivalent privacy-conscious client identification), per-client limits, per-order proof limits, global incident circuit breaker and unique payment reference checks. The QA global 12/10-minute bucket is not production-ready.
- HTTPS and encrypted secrets/DB; an approved privacy notice, retention limits for parent/child data and screenshots, monitored errors, managed backup + restoration and incident recovery procedures.

## Explicit release gates (all must pass)

- [ ] Approve exact 30-day guarantee/refund eligibility, procedure, response times and dispute process.
- [ ] Independently confirm founder ownership/access to both settlement accounts and evidence review procedure.
- [ ] Approve who can review real payment records, founder login MFA provisioning and access revocation.
- [ ] Choose and verify buyer phone/recipient binding or written approved fallback.
- [ ] Approve versioned Amharic package, private delivery/receipt steps and no-public-link policy.
- [ ] Confirm durable production hosting/PostgreSQL, tested offsite backups/restore, monitoring and domain/CORS.
- [ ] Implement production data model, endpoints, independent funds review and immutable audit in **separate** modules.
- [ ] Test concurrent idempotency, 429 abuse controls, duplicate refs, partial settlement, wrong account/amount, replay, identity mismatch and no premature delivery against disposable production-equivalent database.
- [ ] Test real founder workflow with controlled **authorized** transactions and manual bank/provider reconciliation, then issue an explicit production go/no-go.
- [ ] Deploy the real checkout behind an off-by-default server rollout gate. Monitor readiness, audit, rollback and backup recovery; never reuse the demo preview URL as payment authorization evidence.

## Work that is safe before release approval

- Leave current preview, QA site, QA API, founder-admin defaults and `PAYMENTS_ENABLED=false` unchanged.
- Build and test new production modules on an isolated feature branch against disposable test data.
- Add responsive browser acceptance and correct source assets for the production form.
- Keep the real checkout button and payment initiation **disabled** until production backend, independent verification, operational policy and buyer-binding gates are passed.

**Do not** remove the no-payment warning merely to make the page look live. **Do not** point the preview form at the QA order API while advertising it as a real customer checkout.
