# AletCloud deployment preparation (non-payable)

This is a preparation and acceptance procedure, not authorization to provision or deploy. It does not change the approved public website or checkout. Keep every production gate closed.

## Runtime configuration

- Runtime: Python 3.12; install from the repository root with `python -m pip install -r production_checkout/requirements.txt`.
- Working directory: repository root (so `production_checkout.app` imports correctly).
- Startup command: copy `aletcloud/START-COMMAND.txt` into the AletCloud app command field. It uses the FastAPI factory and Uvicorn ASGI server, one worker, a concurrency cap of four, and five-second keep-alive. Confirm AletCloud's actual port variable is `$PORT` before using the command.
- Health checks: `GET /healthz` for liveness and `GET /readyz` for database/schema readiness. The readiness check must return 503 on missing database/table. Never use `/readyz` as a liveness-only probe.
- Memory: the 512 MiB plan has not been measured yet. Keep one worker, at most four concurrent requests (including Argon2 login work), a two-connection pool, and zero overflow. Acceptance requires sustained and burst test RSS below 410 MiB with no restart/OOM. If not met, stop and profile rather than increasing concurrency.

## Private environment variables

Use `aletcloud/nonpayable.env.example` only as a list of names and safe false gates. The recipient entries are explicit synthetic values and must never be used for a real transfer. Store all values in AletCloud's private environment-variable mechanism; do not commit a populated `.env` file.

Required for app startup: `APP_MODE=production`, `PAYMENTS_ENABLED=false`, `DATABASE_URL`, `ORDER_TOKEN_KEY` (random, high entropy, at least 32 characters), `ALLOWED_ORIGINS` (exact HTTPS origin), `TELEBIRR_ACCOUNT_NUMBER`, `TELEBIRR_ACCOUNT_HOLDER`, `CBE_ACCOUNT_NUMBER`, and `CBE_ACCOUNT_HOLDER`. Use synthetic recipient strings that pass validation in the private test environment. Keep `ORDER_INTAKE_ENABLED=false`, `FOUNDER_AUTH_ENABLED=false`, `FOUNDER_APPROVAL_ENABLED=false`, `CUSTOMER_PAYMENT_CLAIMS_ENABLED=false`, and `SECURE_PDF_DELIVERY_ENABLED=false`.

`DB_POOL_SIZE` defaults to 2 and is restricted to 1–4; `DB_POOL_TIMEOUT_SECONDS` defaults to 5 and is restricted to 1–30. The engine always uses `max_overflow=0`. Do not set an unbounded pool or add Uvicorn workers without repeating the connection and memory test.

## Database preparation and migration ordering

Use a new, empty PostgreSQL 16+ database, dedicated credentials, private connectivity, and a non-superuser runtime role. Prefer a distinct migration owner if AletCloud supports it. `readyz` expects the order table and never runs schema creation. Configure a protected libpq service entry (for example `PGSERVICEFILE`/`PGSERVICE`) through AletCloud's private shell facility so credentials are not embedded in commands/history. Apply the reviewed SQL once, in order:

```sh
psql "service=parentwise_test" -v ON_ERROR_STOP=1 -f production_checkout/migrations/0001_create_orders.sql
psql "service=parentwise_test" -v ON_ERROR_STOP=1 -f production_checkout/migrations/0002_create_payment_delivery_state.sql
psql "service=parentwise_test" -v ON_ERROR_STOP=1 -f production_checkout/migrations/0003_create_founder_security.sql
psql "service=parentwise_test" -v ON_ERROR_STOP=1 -f production_checkout/migrations/0004_manual_telegram_fulfillment.sql
```

Record each applied filename, checksum, timestamp, and operator in an access-controlled deployment record. These SQL files are not an automatically managed Alembic chain. Never re-run an applied migration blindly. Confirm table/function privileges with the runtime role and keep the migration role separate where possible.

## V1 fulfillment boundary

The founder approval route explicitly calls `approve_payment(..., fulfillment_mode="manual_telegram")`. This confirms only independently matched settlement, leaves the website-download fulfillment state `LOCKED`, creates no active download grant, and creates a `PENDING` manual delivery record. Founder delivery transitions are `PENDING → PREPARING → SENT → DELIVERED`, with retry through `FAILED → PREPARING`. Every action is authenticated, CSRF-protected, founder-attributed, and stored in append-only delivery history. Telegram is not called by the application; the founder performs and records the manual send.

The existing `website_download` service mode remains only as a separately gated deferred path. Do not call it from V1 routes or enable customer claims, R2 access, or secure downloads for the Telegram pilot. The two paths must not share an implicit default at an HTTP boundary.

Founder reporting is exposed only under the authenticated founder router. Verified revenue sums only `PAYMENT_CONFIRMED` 1,500 ETB orders. Claims, evidence, pending orders, and delivery counts do not count as revenue.

## Backup, restore, and application rollback

Before schema changes or any future public release, use AletCloud's documented managed backup facility. Confirm retention, encryption, access controls, point-in-time recovery capability, and RPO/RTO in writing. Store backups outside the application filesystem and separate from runtime credentials.

For an authorized isolated test, a protected operator shell can exercise a logical backup/restore without printing the URL or password:

```sh
pg_dump --format=custom --no-owner --no-privileges "service=parentwise_test" --file=/secure-temp/parentwise-test.dump
createdb parentwise_restore_test
pg_restore --exit-on-error --no-owner --no-privileges --dbname="service=parentwise_restore_test" /secure-temp/parentwise-test.dump
```

Run the production checkout synthetic suite against the restored database and verify table constraints, manual-delivery history, founder sessions, readiness, and expected synthetic counts. Then delete the temporary dump/database through the provider's approved procedure. Do not put credentials on command lines or shell history on shared hosts; use the provider's protected connection method.

Application rollback is to the last accepted code release while keeping schema additive. Migration `0004_rollback_manual_telegram_fulfillment.sql` intentionally refuses to drop the delivery schema when rows exist; with data present, prefer forward repair or a protected restore, not destructive rollback. Never restore production-like customer data to CI.

## Acceptance gates before considering a public release

1. Confirm AletCloud startup, `PORT`, environment injection, HTTPS and ingress restrictions on a private test service.
2. Apply all four migrations to disposable PostgreSQL 16+, run CI, and rehearse provider backup/restore.
3. Confirm liveness/readiness, closed-order behavior, no payment endpoints, and no website connection.
4. Load test within the 512 MiB limit; record peak RSS and DB connections under four concurrent requests including two synthetic founder logins.
5. Verify founder login/MFA replay prevention, CSRF/origin enforcement, unique transaction references, independent evidence match, single approval, no website grant in Telegram mode, delivery transitions, and reporting arithmetic.
6. Verify exact route/schema compatibility with the separately maintained founder UI before enabling any founder feature gate.
7. Keep all production gates closed until separate founder release approval. Nothing in this document authorizes opening orders, accepting money, or deploying publicly.
