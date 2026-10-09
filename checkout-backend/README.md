# ParentWise Ethiopia — portable QA order API (Phase 1)

This backend **creates and retrieves test orders only**. It does not accept real payments, verify receipts, provide any operator endpoints, or deliver product files. `APP_MODE` must be `qa` and `PAYMENTS_ENABLED` must be `false` or startup fails.

## Runtime and hosting

- Python 3.11+ and PostgreSQL 14+ (SQLAlchemy 2, psycopg 3, FastAPI).
- Any provider running Python + PostgreSQL is suitable; no Render-specific SDK or services.
- Environment: `DATABASE_URL`, `ORDER_TOKEN_KEY` (random >=32 chars; persist across restarts), `APP_MODE=qa`, `PAYMENTS_ENABLED=false`, `ALLOWED_ORIGINS` (explicit browser origin), `CREATE_RATE_LIMIT` (optional).
- Create PostgreSQL database separately. Never put secrets into GitHub.
- From this directory: `pip install -r requirements.txt`; `alembic upgrade head`; then `uvicorn api.main:app --host 0.0.0.0 --port "$PORT" --no-access-log` (or use a provider-specific PORT default).
- Use `GET /healthz` for process health, `GET /readyz` for database health.
- Do not allow traffic before migrations are applied. Migrations must run as a controlled release job, not automatically on every worker startup.
- Configure TLS and database credentials with provider secret environment settings. Turn off HTTP access logs containing sensitive query/body data; these endpoints never accept secrets in URLs.

## HTTP API

**POST /api/v1/orders**
- `Content-Type: application/json`, `Idempotency-Key: <43-character CSPRNG 256-bit base64url token>`.
- Request: `{"customer_name":"QA Test Parent","mobile":"0912345678","payment_method":"telebirr"}` (use fictitious test identities only).
- Response 201: `{"order":{"order_id":"PW-QA-...","product":"...","amount_etb":1500,"currency":"ETB","payment_method":"telebirr","status":"PENDING_PAYMENT","test_mode":true,"created_at":"..."},"access_token":"..."}`.
- Access token derived from HMAC secret + idempotency key; **never stored in plaintext**. Treat both the key and access token as private secrets. Store the key only in temporary browser session state, not URLs, logs or analytics; persist the returned access token in encrypted secure server storage or offer it as a user-held recovery code if necessary. Never include PII or tokens in URLs.
- Retry the *same* body with the same key: same order and token. Reusing the key with different data returns 409. A different key creates a new order.

**GET /api/v1/orders/{order_id}**
- `Authorization: Bearer <access_token>`; returns only the non-PII order summary.
- Missing, invalid or another customer's access token returns the same 404 response. Order ID alone confers no access.

**GET /healthz**, **GET /readyz** are non-sensitive. No order listing, payment approval, operator status changes or file delivery routes exist.

## Model and migrations

Alembic migration `migrations/versions/20261009_01_qa_orders.py` creates `orders` and DB-backed `api_rate_windows`. Order code and idempotency hash have uniqueness constraints; amount, currency, payment method and QA-only status have database-level CHECK constraints. Old `schema.sql` was a draft for a future operator workflow and is **not** used by this Phase 1 deployment; keep Phase 1 separate from any payment reconciliation schema.

## Tests

Run `pytest -q` with a disposable SQLite file (FastAPI/SQLAlchemy integration; **not** PostgreSQL integration). The tests exercise real HTTP requests through TestClient, SQL persistence and migration, retries, input validation, failed DB, and unauthorized access. A local PostgreSQL container or a credentialed disposable PostgreSQL instance is required to confirm PostgreSQL-specific behavior. Do not call Phase 1 complete without full **deployed API + PostgreSQL** integration tests, restart persistence and idempotency under concurrency.

## Before connecting real customers

Deploy a QA API with protected PostgreSQL `DATABASE_URL`; set a durable secret; configure rate limit per worker/proxy topology; add monitoring/backup/retention policy. Only change the existing QA checkout from its mock form after successful remote tests. Production payment methods and recipient accounts remain disabled and unspecified.

## October 2026 QA rate-limit security fix (not production ready)

Render places Cloudflare and load balancers in front of the API. The previous
`request.client.host`-based bucket sometimes represented a proxy address,
which could vary between requests; simply trusting user-supplied
`X-Forwarded-For` or `CF-Connecting-IP` without a verified boundary would
introduce header-spoofing risk.

**QA-only mitigation:** All *new* test-order creations share one PostgreSQL
bucket (`qa-global-order-create:v2`, salted/hashed with `ORDER_TOKEN_KEY`).
`CREATE_RATE_LIMIT=12` therefore means **12 new QA test orders per 10 minutes
across all testers**. A request that sees 429 will not be followed by a 201
for another new order in the same window, even if requests traverse different
proxy addresses or include forged forwarding headers. Successfully created
orders remain retrievable with their access token; idempotent retries check
the existing record first, do not create extra orders and do not consume the
creation quota. PostgreSQL UPSERT keeps counters atomic under concurrency.

**Tradeoff:** One user can exhaust the global 12-order allowance and block
other QA testers. This is acceptable only during controlled QA; replace it
with a verified trusted-proxy/client-identity strategy and multi-layer
per-client/abuse limits before enabling production. Do not reduce the global
limit without coordinating tests.

**PostgreSQL-only regressions:** `tests/test_rate_postgres.py` includes
sequential over-limit, concurrent atomic UPSERT, reset-after-expiry and
proxy-header-independence assertions. These tests **skip without explicit
opt-in**: `QA_PG_TESTS=1 APP_MODE=qa PAYMENTS_ENABLED=false` plus
`DATABASE_URL` pointing to the QA PostgreSQL database. They create only
temporary hashed rate keys and clean up their own rows. Do not use a
production database.

**On-service PostgreSQL self-check:** Temporarily set
`QA_RATE_SELFTEST=true` on the isolated QA service before a restart.
The startup hook tests actual PostgreSQL sequential and concurrent rate
windows with unique temporary rows, logs only pass/fail counts, and removes
those rows. This is a DB-level check, **not a substitute for external HTTP
spoof-header or fully deployed request-flow testing**. Disable this option
after verification to avoid unnecessary startup work.

The order page and actual payments remain disabled and unchanged.
