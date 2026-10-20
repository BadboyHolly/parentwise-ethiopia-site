# STEP 6.2 — Founder authentication and manual settlement review

This module is a production-code prototype only. It does not change the public
site, Amharic checkout, payment provider, or existing order price. Feature gates
default off: `FOUNDER_AUTH_ENABLED=false` and `FOUNDER_APPROVAL_ENABLED=false`.
`PAYMENTS_ENABLED` must remain false; it continues to reject provider payment
processing. Delivery routes are not added here.

## Authentication design

- A single founder username and Argon2id PHC password hash are supplied from a
  managed server secret store. Startup rejects non-Argon2id hashes and weak
  minimum parameters. Passwords and TOTP values are never logged or stored in
  the database.
- TOTP is RFC 6238, 6 digits / 30 seconds. A row lock and one global accepted
  step prevent replay across sessions. The accepted interval permits one step
  of clock skew. Use a synchronized device clock.
- Session IDs and CSRF tokens are random high-entropy values. Only keyed
  HMAC-SHA-256 digests are stored. Sessions expire after eight hours and are
  revocable server-side. Cookies are `HttpOnly; Secure; SameSite=Strict`, scoped
  to `/api/v1/founder`; every response is `no-store`.
- State-changing requests require the authenticated session, a matching
  `X-CSRF-Token`, and an exact allowlisted HTTPS Origin. Caller-supplied founder
  IDs are rejected by strict request schemas; the service gets identity only
  from the authenticated session.
- Login attempts are limited to five per 15-minute username/IP bucket. The IP
  is HMACed before storage; `X-Forwarded-For` is ignored. Keep an ingress-level
  limit as a second boundary before public launch.
- Authentication and security events are append-only. Password, TOTP seed,
  session cookie, CSRF token, raw IP and evidence text are excluded.

## Sensitive evidence encryption

Payment references, settlement notes and third-party exception rationale use
AES-256-GCM with a fresh 96-bit nonce per value. The envelope is
`enc:v1:<key-id>:<nonce>:<ciphertext-and-tag>` and associated data binds the
field type, order code and claim ID. A bad tag, wrong key or changed context
fails closed. The active key ID and base64url keyring come from server-side
managed secrets; they are never accepted from requests or database rows.

Rotation: introduce a new key ID and 32-byte key while retaining old decrypt
keys; set the new active ID; verify a read of old and new records; re-encrypt
records in a controlled, audited maintenance job with compare-and-swap; then
remove the old key only after a full inventory confirms no ciphertext references
it and protected backups are also rotated. Never overwrite key material under
an existing key ID.

No customer-facing claim route is added in STEP 6.2. A future claim endpoint
must call `encrypt_claim_reference` before persistence; it must not accept an
`enc:` envelope supplied by a customer. Password provisioning must enforce at
least 12 characters and store only the resulting Argon2id hash.

## Review and approval sequence

1. Founder signs in with password and TOTP.
2. Founder reviews a pending claim and its decrypted reference in the private
   founder API.
3. Founder independently checks the Telebirr portal or CBE statement. The
   expected recipient is derived from the same protected account number and
   holder values used by the order API. The founder must affirm recipient
   match; the request cannot provide a recipient number/name.
4. Founder records the observed reference, payment method, amount, currency,
   payer mobile where visible, and source record. Evidence recording does not
   approve a claim.
5. Explicit approval rechecks reference digest, recipient digest, payment
   method, 1,500 ETB, ETB currency, and payer identity against the buyer phone.
   A third-party exception can resolve only an identity mismatch, and is bound
   to the exact order/claim/evidence. Other mismatches cannot be excepted.
6. The existing transaction locks, constraints, explicit decision, grant and
   append-only payment audit remain authoritative. Customer screenshots and
   claims cannot unlock files.

When payer identity is absent or cannot be independently established, do not
approve. Keep the order pending while requesting reliable evidence or reject it
with a reason. Do not treat a screenshot or customer reference as settlement.

## MFA enrollment and recovery — no approval bypass

Initial enrollment is a controlled operator bootstrap, not a public endpoint:

1. On a trusted workstation, generate a random Base32 TOTP seed and Argon2id
   password hash. Transfer them directly into the managed secret store over its
   authenticated console. Never put secrets in Git, tickets, email, shell
   history, CI variables, or logs. Give the founder the `otpauth` URI through an
   in-person or otherwise authenticated handoff and verify a successful login.
2. Keep a sealed, access-controlled recovery copy of the TOTP seed in the
   organization's approved offline vault. Restrict vault access and audit every
   checkout. This is the only MFA recovery factor; it cannot authorize a
   payment by itself.
3. For a lost device, first set `FOUNDER_APPROVAL_ENABLED=false` and verify
   payment decisions return 503. Revoke all sessions, rotate the founder
   password hash and TOTP seed in the secret store, then restart. Enroll the
   replacement device and verify a new login. Do not reset the global TOTP
   replay counter backwards.
4. If the founder cannot access the vault, use the infrastructure owner's
   identity-verified account recovery with two-person review to rotate secrets.
   Keep approvals disabled for the entire recovery. No recovery code, support
   operator, password-only login, or database edit can approve or release a
   payment. Re-enable approval only after the founder independently confirms
   access and a separate release review.

This is a documented provisioning procedure, not an in-app self-service reset.
No MFA enrollment endpoint exposes a seed, and no recovery route bypasses TOTP.

## Required configuration (all server-side)

`FOUNDER_AUTH_ENABLED`, `FOUNDER_APPROVAL_ENABLED`, `FOUNDER_USERNAME`,
`FOUNDER_PASSWORD_HASH`, `FOUNDER_TOTP_SECRET`, `FOUNDER_SESSION_KEY`,
`FOUNDER_RATE_LIMIT_KEY`, `PAYMENT_DATA_KEYRING`,
`PAYMENT_DATA_ACTIVE_KEY_ID`, `ORDER_TOKEN_KEY`,
`PAYMENT_REFERENCE_HASH_KEY`, `PAYER_IDENTITY_HASH_KEY`,
`PAYMENT_RECIPIENT_HASH_KEY`, and `FOUNDER_ALLOWED_ORIGINS`. Recipient values
are derived from the server-only Telebirr/CBE account number and account-holder
configuration already consumed by order instructions.

Do not set these values in this branch or GitHub Actions. Production order
intake, founder approval and download delivery remain disabled. The test suite
uses disposable credentials and data only.

## Remaining security gates

- Review whether the founder console should be served same-origin; current API
  uses strict same-site cookies and exact Origin matching.
- Validate trusted proxy and network restrictions at the hosting ingress.
- Confirm a managed KMS/secret store, key custody and backup procedure.
- Independently review manual settlement evidence procedures and retention.
- Complete STEP 6.3 private PDF delivery only after founder authentication and
  approval controls receive separate acceptance.

