# R2 private PDF delivery — immutable release and connection runbook

**Status:** adapter and mock-backed staging integration only. R2 access is not configured or exercised. This document does not enable production intake, payment verification, or delivery.

## R2 compatibility decision

Cloudflare's [S3 API compatibility table](https://developers.cloudflare.com/r2/api/s3/api/) marks `GetBucketVersioning` and `PutBucketVersioning` unsupported. It documents `GetObject`, but does not document retrieval of a particular S3 object `VersionId`. We therefore do not use bucket versioning, `VersionId`, or version-specific permissions. The code reads a key with ordinary `GetObject` and verifies its complete contents against the approved SHA-256 manifest before returning bytes.

Cloudflare documents conditional `PutObject` with `If-None-Match: *` as atomic against committed state: only one concurrent create succeeds, and a later create of the same key is rejected. The publisher uses this condition. A precondition failure is treated as a permanent conflict; it never retries with an unconditional write.

## Storage boundary and configuration

The bucket is supplied through server-side configuration only:

- `R2_ENDPOINT_URL`: account-scoped HTTPS S3 endpoint. For this account, the value to enter in the production secret manager later is `https://ac17290060a2cbf0e81499b1f29489eb.r2.cloudflarestorage.com`.
- `R2_BUCKET`: `parentwise-ethiopia-private-pdfs`.
- `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`: later-issued delivery-only credentials. Never place values in Git, this document, browser JavaScript, CI variables, issue comments, or chat.
- `PRODUCT_PDF_MANIFEST_JSON`: exactly five rows with `release_id`, integer parts 1–5, canonical release keys, and lowercase SHA-256 digests. It has no object version IDs and contains no credentials.
- `R2_MAX_OBJECT_BYTES`: optional server-side cap; default 25 MiB per PDF, hard maximum 250 MiB.

Use a fresh immutable release ID for every approved content release, for example `approved-2026-10-19-a1b2c3`. The canonical object keys are `releases/{release_id}/part-1.pdf` through `part-5.pdf`. A manifest rejects missing/extra parts, duplicate parts, unsafe release IDs, keys outside the release, and malformed checksums.

The delivery adapter is explicitly constructed from server-side configuration and staging never reads the configured bucket. It makes bounded-timeout ordinary `GetObject` requests, closes response bodies, enforces size limits, and checks SHA-256 before returning bytes. Missing objects, timeouts, provider errors, oversize content, and checksum mismatches return a generic no-store 503. The adapter never emits pre-signed URLs.

The staging download route uses generated mock PDFs in memory. Before every read it rechecks the private order bearer token, approved delivery state, and active/non-revoked grant. It returns bytes through an authenticated FastAPI response with `Cache-Control: private, no-store`.

## Safe publishing

1. A founder approves a specific release ID and the exact five source files. Publishing credentials are separate from delivery credentials and are not configured in the application.
2. Calculate SHA-256 and file size locally. Independently review the checksums and ensure each file is within the configured cap.
3. Publish each canonical key using `PutObject` with `If-None-Match: *`, PDF content type and private/no-store cache metadata. The publisher verifies the expected digest before sending. Never retry a 412/precondition conflict without changing to a new release ID.
4. Read back the five objects using a restricted verifier identity or controlled publishing session, recompute each SHA-256, and compare with the proposed manifest. This is a one-time release verification, not a production read permission.
5. Review and approve the exact manifest as a deployment secret/config value. Keep the prior manifest available for rollback; a rollback changes the active manifest to a prior release ID and does not overwrite objects.
6. Do not enable delivery until per-request authorization, grant migrations, backup/restore acceptance, and founder release gates are complete.

No release object is overwritten. If content changes, publish a new release ID. Do not delete old release objects as part of routine rollback; retention/deletion requires a separately approved and audited process.

## Protected backup and restore

Backups must be independent of the delivery path: copy each approved release into a separate private bucket in a separate account or provider, with encryption at rest, restricted administrator access, MFA, and audit logs. Backup credentials must not be present in the delivery service. Use a backup identity that can create new backup objects but cannot change production release objects. Where the chosen backup system supports immutable retention, enable it; do not rely on R2 S3 bucket versioning for this property.

Store a signed or access-controlled backup manifest containing release ID, five canonical part numbers, backup object identifiers, byte sizes, and SHA-256 checksums. Alert on backup failure and retain an independently protected copy of the manifest.

Restore rehearsal (required before launch and at least quarterly):
1. Restore the five objects and manifest into an isolated private restore bucket/prefix that is not mounted by the checkout.
2. Confirm exactly five files, expected sizes, and SHA-256 checksums against the separately protected manifest.
3. Run the authorization integration checks against a disposable database: invalid token, unapproved payment, inactive/revoked grant and allowed customer; only the allowed customer may retrieve bytes.
4. Measure restore time, record operator, date, checksums and outcome, then destroy the isolated restore copy under the approved retention policy.
5. Investigate any mismatch; never switch production to a restored release until a founder reviews the evidence and explicitly approves the manifest change.

CI tests the checksum-verified restore procedure with two independent in-memory stores. This is a logic check only; it does not establish R2 behavior or replace a real-provider restore rehearsal.

## Minimum permissions

Create distinct credentials, each limited to the named bucket. Scope object prefixes if Cloudflare's permission interface supports it.

| Identity | Minimum capability | Explicitly exclude |
|---|---|---|
| Delivery service | Bucket-scoped Object Read sufficient for ordinary `GetObject` on `releases/*`. No listing is needed. | Object Write, delete, bucket listing, public access, account administration |
| Publisher | Used only by a controlled publishing procedure. `PutObject` on `releases/*`, with conditional create-only requests. | Delivery runtime use, DeleteObject, public access, account administration |
| Backup writer | Create objects only in the separate backup destination; never used by the web service. | Read or write access to production bucket unless a separately approved backup job requires read, delete, public access, account administration |

If the provider cannot scope permissions by prefix, restrict to the single bucket and omit account-wide access. Any delete action requires a separate time-limited, audited break-glass process.

## Download request behavior

1. Accept only one of the five integer part numbers.
2. Validate the original private order token in the Authorization header; order code alone is not authority.
3. Read order/payment state and grant state from the server-side database on each request. Require independently verified/approved payment and an active grant.
4. Read exactly the key in the active five-file manifest, verify size and SHA-256 before responding. Do not accept keys or release IDs from customers.
5. Return PDF bytes from the backend with `private, no-store`, attachment filename, `nosniff` and no referrer. Do not redirect or expose bucket/key URLs.
6. Missing, corrupt, oversized, or timed-out objects return a generic retryable error with no provider detail. Do not log tokens or credentials.
7. If revocation commits between requests, the next request is denied before object access. Existing in-flight responses may complete; previously saved copies remain with the customer.

The independent production order schema still has only `AWAITING_PAYMENT`; production payment-approval and download-grant state are not yet implemented. Do not mount or enable the delivery route for production until those modules, migrations, and per-request checks are separately implemented and accepted.

## Secure connection steps through Work

Perform these later, only after founder approval of the production host, payment operations, final PDFs, backup policy, and launch gates:

1. Create a dedicated R2 token in Cloudflare with only bucket-scoped Object Read. Do not create it as part of this branch work. Confirm the bucket remains private.
2. In the production service's secret manager accessed through Work, set the endpoint, bucket, delivery credentials, manifest, and reviewed size cap. Never paste credential values into chat or repository files.
3. Keep `PRIVATE_PDF_DELIVERY_ENABLED=false` by default. Do not add a real production opt-in until app integration, payment/grant migrations, restore rehearsal, and tests are approved.
4. Validate masked setting names and non-secret endpoint/bucket configuration only. No live R2 canary is part of this branch.
5. Upload only the five founder-approved final PDFs with the separate publisher identity after separate approval. Use a new release ID and create-only writes. Verify read-back bytes and checksums, then review the manifest.
6. Exercise authorization, missing file, checksum mismatch, timeout, size rejection, revocation, backup/restore, and no-store behavior in a non-public production-like environment.
7. Revoke or lock away publishing credentials after release. Rotate delivery credentials on schedule and on suspected exposure. Keep intake, payments and delivery disabled until explicit founder go/no-go approval.

The approved sales page and public Amharic checkout must remain unchanged. No R2 connection, upload, merge, or service deployment is part of this branch.
