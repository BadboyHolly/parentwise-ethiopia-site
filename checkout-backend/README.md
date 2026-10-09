# ParentWise Ethiopia QA — checkout backend and launch gate

Status: NOT OPERATIONAL. This directory currently documents the future server-side schema. The static `order.html` is a **test-mode walkthrough**, not a payment or order-processing service.

## Verified infrastructure (9 October 2026)
- Existing Render QA service: **static_site**. A static page cannot persist orders, verify payments, manage operator authorization or deliver restricted PDF files.
- Separate Render QA PostgreSQL free-tier instance provisioned: `parentwise-qa-orders`. Not yet connected to an API. Free-tier database expires **2026-11-08** unless retained through a supported plan.
- No previously deployed web API or persistent order system found.
- Real Telebirr and bank recipient details, support hours, operator identity, secure distribution method and written refund terms are **not approved**.

## Required production architecture
1. A separate Render web service providing HTTPS API endpoints, with secrets only in Render environment variables. Origin restriction is not authentication.
2. QA PostgreSQL for structured orders, a transaction reconciliation ledger, and immutable operator audit records. Use migrations and unique constraints from `schema.sql`.
3. POST `/api/orders`: validate name, Ethiopian mobile and method; create cryptographically random UUID + non-sequential public order code; enforce an idempotency key for re-submission/refresh; persist `PENDING_PAYMENT`. Return public code; do not accept price from browser.
4. POST `/api/orders/{code}/proof-notice`: accept a minimal non-sensitive proof-received notification and change status to `PROOF_SUBMITTED`, never verified/paid. Actual screenshots should be submitted through the official Telegram conversation, not public APIs/URLs.
5. Authenticated operator interface (SSO or MFA preferred). Do not treat knowing the order code as authorization. Fetch and review pending orders through authenticated server endpoints.
6. Operator checks actual Telebirr or bank transaction against the screenshot, verifies payer/amount/reference/recipient, and creates an atomic reconciliation record with unique `(payment_method, provider_reference)`. Only then can an order become `VERIFIED_PAID`.
7. Actual delivery must be an authorized action after verification, e.g. an expiring one-time signed private file link recorded against the order with recipient/delivery audit. Do not use publicly accessible paid PDF links or treat clicking a button as delivery.
8. Controlled `DELIVERED`, `REFUNDED`, `CANCELLED` and `EXPIRED` transitions, with operator identity, reason and timestamps. Refund action must be corroborated against the real refund transaction.
9. HTTP-only secure session cookies, CSRF protection, role-based authorization, parameterized SQL, request rate limits, HTTP 4xx validation, protected secret configuration, no PII in logs/URLs, backups, and retention controls.
10. PageView/BuyClick/FormStart/OrderCreated/ProofReceived/PaymentVerified/ProductDelivered events should be attributable to campaigns without sending raw names, numbers, or payment proof to analytics.

## Required owner approvals before activation
- Legal payee/recipient name and **confirmed** Telebirr identifier.
- Legal payee/recipient name, bank name and **confirmed** account number.
- Real support hours and realistic verification SLA based on staffed coverage.
- Operator account(s), access policy, access recovery and who actually reconciles payments.
- Private product delivery location/workflow and product version.
- Written 30-day guarantee/refund policy, eligibility, process, support contact and owner approval.
- Customer privacy notice, retention periods, consent and applicable legal/compliance review.
- Paid Render database/web-service plan and monitoring once QA is validated.

## Required end-to-end QA tests
- Valid/invalid Ethiopian numbers; form requirements; exact 1,500 ETB server enforced.
- Concurrent order requests, repeated taps and refreshes: only one order per idempotency key.
- Cryptographic public-code collision handling; persistent order records after server restarts.
- Both payment methods with TEST-only, nonpayable account details.
- Copy controls, Telegram URI, fallback support if app does not open.
- Non-owner proof notice cannot mark verified/paid.
- Unauthenticated status changes return 401/403 and are audited when appropriate.
- Duplicate transaction references refused across orders.
- Incorrect recipient/amount/reference refused; only independent provider verification allows paid.
- No delivery before verified paid, private file access only to authorized recipients, delivery audit.
- Cancellation, expiration, and refunds follow controlled transitions.
- Mobile 360–430 px and desktop browser tests; recovery after network errors.

## QA-only safety rule
Until the secure API and the owner-approved production configuration are in place, **no real payments may be accepted on this QA site**. The checkout preview must never manufacture an order ID, show a potentially payable recipient or pretend proof submission has verified funds.
