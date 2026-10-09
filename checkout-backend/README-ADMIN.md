# ParentWise Ethiopia · Phase 3 Founder-only QA console

**Code-stage only: the founder account must be privately provisioned and tested before deployment.** Existing payments remain disabled; no operator state changes exist. The dashboard is on the FastAPI service's own HTTPS origin (`https://parentwise-orders-api-qa.onrender.com/admin`), not the sales page origin.

## Security design

- Exactly one founder username configured with `FOUNDER_USERNAME` (no registration or staff accounts). Password verification uses Argon2id from `argon2-cffi`. One-time codes use RFC 6238 TOTP (30-second SHA-1 six digits, ±30 seconds drift), with DB-backed replay prevention using a row-level lock in PostgreSQL.
- Generate a fresh 256-bit random session ID after successful password + TOTP; store only SHA-256 digest in PostgreSQL. `__Host-pw_admin_session` cookie has `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, no Domain. Absolute expiry 8 hours; inactivity expiry 20 minutes; logout revokes it. A credential rotation invalidates sessions through credentials versioning. Browser user-agent fingerprint is a modest additional check, not full defense against session theft.
- Same-origin `Origin` and `Sec-Fetch-Site` checks on login/logout, server-derived session CSRF header on logout. Read-only GET endpoints never mutate order business state. The admin frontend uses same-origin requests, no cross-origin credentials, `Cache-Control: no-store`, frame denial and a restrictive CSP.
- Global QA login attempt rate limit of 8 per 10 minutes backed by atomic PostgreSQL updates. This is deliberately strict and can permit denial-of-service by exhausting the shared QA quota; production needs additional abuse controls. Admin access logs event name and timestamp only, never passwords, OTPs, tokens or phone numbers. Orders are accessible only after server-side session verification.
- No admin listing, status mutation, registration, payment, receipt, refund or file-download endpoints are exposed without authentication (and no business state-changing endpoint is implemented in this phase).

## Founder provisioning — do this only on a trusted computer

**Do not paste any secret into ChatGPT, GitHub, Telegram or email.** Use a password manager for the password and recovery material. An authenticator app supporting six-digit RFC 6238 codes is needed.

1. Install Python and the hash library locally: `python -m pip install "argon2-cffi>=23.1"`.
2. Run this script from your **own terminal** to generate an Argon2id hash and a new TOTP secret. It will prompt for the founder password without echoing it. Generated secrets stay in your terminal; never save output in the public repository:

   ```python
   import getpass, secrets
   from argon2 import PasswordHasher
   password = getpass.getpass('New founder password (unique, >=16 characters): ')
   if len(password) < 16: raise SystemExit('Use at least 16 characters')
   print('FOUNDER_PASSWORD_HASH:', PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2).hash(password))
   print('FOUNDER_TOTP_SECRET:', __import__('base64').b32encode(secrets.token_bytes(20)).decode().rstrip('='))
   ```
3. In the **Render Dashboard → `parentwise-orders-api-qa` → Environment**, add `FOUNDER_USERNAME` (your privately chosen login name), `FOUNDER_PASSWORD_HASH` (the hash from step 2), and `FOUNDER_TOTP_SECRET` (Base32 string). Set `ADMIN_ORIGIN=https://parentwise-orders-api-qa.onrender.com`. **Keep** `DATABASE_URL`, `ORDER_TOKEN_KEY`, `APP_MODE=qa`, `PAYMENTS_ENABLED=false`, and `CREATE_RATE_LIMIT=12` unchanged. Do not log or share values. The TOTP secret must be added manually to your authenticator app using its “Enter setup key” option, SHA1 / six-digit / 30 second. Keep offline backup recovery material secured.
4. Apply migration to QA PostgreSQL using the existing service's startup `alembic upgrade head`. Test access only after checking server-side authorization, login, logout, TOTP replay protection, CSRF/cookie behavior, and order listing against live QA PostgreSQL. Do not make the console publicly accessible for use until tests pass.
5. To recover from loss of an authenticator, use authenticated Render account access to rotate both `FOUNDER_PASSWORD_HASH` and `FOUNDER_TOTP_SECRET` after verifying your identity out of band. All existing sessions are automatically rejected because the credential version changes. There is deliberately no public reset-password route or bypass code.

## QA routes

- `GET /admin`: same-origin dashboard shell; no private data in HTML.
- `GET /admin/ui.js`, `GET /admin/ui.css`: public static console assets, contain no secrets or order records.
- `POST /admin/api/login`: founder credentials + TOTP; sets secure, revocable cookie.
- `GET /admin/api/session`: auth required; session metadata and CSRF token.
- `POST /admin/api/logout`: auth + same-origin and CSRF verification.
- `GET /admin/api/overview`: auth required; counts, methods and recent 6 orders.
- `GET /admin/api/orders`: auth required; paginated, filterable list (max 50 items).
- `GET /admin/api/orders/{order_code}`: auth required; order detail + timeline and relevant audit events.

All administrative API data are QA only. The existing customer recovery token can **never** replace a founder session cookie.

## Test and rollout gates

- Run `pytest -q` from `checkout-backend` on a disposable database.
- Perform real PostgreSQL integration against QA before passing this phase: login with founder-supplied factors, auth failures, session expiry, logout, CSRF, replay prevention, pagination, filtering, order detail and account count.
- Perform desktop and mobile browser testing using fictitious QA orders; capture only mock/nonsensitive screenshot data.
- Re-run accepted Phase 1/2 tests. No real payments, status transitions or delivery should be activated.