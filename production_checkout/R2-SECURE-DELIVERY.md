# R2 private PDF delivery — implementation and connection runbook

**Status:** adapter and mock-backed staging integration only. R2 access is not configured or exercised. This document does not enable production intake, payment verification, or delivery.

## Storage boundary

The bucket is supplied through server-side configuration only:

- `R2_ENDPOINT_URL`: account-scoped HTTPS S3 endpoint. For this account, the value to enter in the production secret manager later is `https://ac17290060a2cbf0e81499b1f29489eb.r2.cloudflarestorage.com`.
- `R2_BUCKET`: `parentwise-ethiopia-private-pdfs`.
- `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`: later-issued delivery-only credentials. Never place values in Git, this document, browser JavaScript, CI variables, issue comments, or chat.
- `PRODUCT_PDF_MANIFEST_JSON`: five entries, each with integer `part` (1–5), private `key`, immutable `version_id`, and lowercase SHA-256 hex digest. It contains metadata, not credentials.
- `R2_MAX_OBJECT_BYTES`: optional server-side cap; default 25 MiB per PDF, hard maximum 250 MiB.

No credential or object key is compiled into the public checkout. `R2PrivateObjectStore.from_environment()` is an explicit constructor; importing the module does not connect. It refuses to construct without the bucket, HTTPS account endpoint, and credentials. It sets bounded connect/read timeouts and SDK retries. Each read uses the manifest's exact object version, closes the response body, enforces a size limit, and checks the downloaded bytes against the manifest checksum. The application returns a generic no-store 503 on missing objects, timeout, provider error, oversize content, or checksum mismatch.

The staging download route uses generated mock PDFs in memory. It never creates an R2 client. Before every read it rechecks the private order bearer token, approved delivery state, and active/non-revoked grant. It returns bytes through the authenticated FastAPI response with `Cache-Control: private, no-store`; it does not generate a pre-signed URL.

## Manifest and object layout

Use a fixed key convention such as `final/v1/part-1.pdf` through `final/v1/part-5.pdf`. Upload a new key/version for every content revision; never overwrite a published version. Generate and independently verify each SHA-256 digest before approving a manifest. The manifest must contain exactly the five ordered parts, distinct safe keys, non-empty version IDs, and valid digests. Unknown, public, unversioned, or sixth objects are not deliverable.

Before first delivery, verify that versioning is enabled on the bucket and that all five object version IDs can be fetched by the delivery-only identity. The bucket's private/no-public-access posture must remain enforced. Keep old versions private for rollback and retention. Application revocation disables the grant in the database; each future HTTP request rechecks it. Previously downloaded files cannot be recalled from a customer's device.

## Minimum permissions

Create two distinct R2 API tokens/credentials, each limited to this bucket. Do not reuse account-wide credentials.

| Identity | Minimum capability | Explicitly exclude |
|---|---|---|
| Delivery service | Bucket-scoped R2 **Object Read**. The code makes version-specific `GetObject` requests and never lists objects. If the permission interface supports actions, grant `GetObjectVersion` only for the five final PDF object keys (or the narrow release prefix); grant `GetObject` only if the provider requires it for versioned reads. | Object Write, PutObject, DeleteObject, ListBucket, public access, account administration |
| Publisher, used only by the controlled publishing procedure | Bucket-scoped Object Write for the release prefix and read-back of the uploaded versions to verify them. Prefer `PutObject` plus `GetObjectVersion` scoped to the release prefix. | DeleteObject, public access, account administration, delivery runtime use |

The publisher identity is not configured in the web service. If object removal is ever required, use a separate time-limited, audited break-glass administrator process. A provider permission UI that cannot narrow by prefix should still be limited to the single bucket and must not receive account-wide permissions.

## Download request behavior

1. Accept only one of the five integer part numbers.
2. Validate the original private order token in the Authorization header; order code alone is not authority.
3. Read order/payment state and grant state from the server-side database on each request. Require independently verified/approved payment and an active grant.
4. Read exactly the manifest key and version, verify size and checksum before responding.
5. Return PDF bytes from the backend, attachment filename, `nosniff`, no referrer, and `private, no-store`. Do not redirect, expose bucket/key URLs, or accept a storage key from the customer.
6. Missing, mismatched, corrupt, oversized, or timed-out objects return a generic retryable error with no provider detail. Do not log tokens or credentials.
7. If revocation commits between requests, the next request is denied before object access. Existing in-flight responses may complete; previously saved copies remain with the customer.

The independent production order schema still has only `AWAITING_PAYMENT`; it does not yet have production payment-approval or download-grant state. Do not mount or enable the delivery route for production until those production modules, migrations, and per-request checks are separately implemented and accepted. The staging route proves the authorization pattern with mock storage, not a live R2 or production-payment acceptance.

## Secure connection steps through Work

Perform these later, after the founder approves the production host, payment operations, final PDFs, and launch gates:

1. Create a dedicated R2 token in Cloudflare with only Object Read, resource limited to `parentwise-ethiopia-private-pdfs`. Do not create it in this implementation task. Confirm bucket versioning/private access in the dashboard.
2. In the production service's secret manager accessed through Work, set `R2_ENDPOINT_URL`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `PRODUCT_PDF_MANIFEST_JSON`, and a reviewed object-size cap. Never paste credential values into the conversation or a repository file.
3. Configure the service to require an explicit feature gate such as `PRIVATE_PDF_DELIVERY_ENABLED=false` by default. Add separate opt-in only after app integration, payment/grant migrations, and tests are approved.
4. Validate configuration without exposing secrets; check the masked setting names and endpoint/bucket only. With delivery disabled, perform a read-only canary of a non-product test object under a private test prefix if the founder authorizes the connection.
5. Upload only the five founder-approved final PDFs using the separate publisher identity after separate approval. Capture exact version IDs and SHA-256 checksums. Populate and review the manifest; verify downloads through the authenticated backend on a non-public staging environment.
6. Test unauthorized token, pending payment, inactive/revoked grant, each part, missing version, wrong checksum, timeout, max-size rejection, backup/restore, and subsequent-request revocation. Confirm no-store response headers.
7. Revoke the publisher credential after publishing or store it outside runtime. Rotate the delivery token on schedule and on suspected exposure. Keep order intake, payments, and delivery disabled until explicit founder go/no-go approval.

The existing public checkout and V4.14 sales page must remain unchanged. No R2 connection, upload, or service deployment is part of this branch preparation.
