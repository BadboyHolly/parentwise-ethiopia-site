# STEP 6.4B — R2 and Founder Operations Rehearsal Runbook

**Status:** Prepared for later founder approval. This document authorizes no Cloudflare, financial-provider, production, or customer-data action.

**Scope:** A later private R2 compatibility rehearsal using only non-final test files, followed by founder MFA and manual settlement-reconciliation rehearsals. Keep the public site and approved Amharic checkout unchanged.

## Entry conditions

Before starting a provider exercise, obtain separate founder authorization for the specific Cloudflare account, bucket, credential scope, test window, and cleanup. This step has not created credentials or contacted R2. Do not use final product PDFs, real transaction information, or customer records.

Use a synthetic release identifier such as `qa-<date>-<random>`. Prepare five small, visibly watermarked dummy PDFs containing no ParentWise product text beyond “QA DEMO ONLY — NOT A PAID PRODUCT.” Generate a manifest containing the release ID, exact five part numbers, immutable object keys, byte lengths, and SHA-256 checksums. Store that manifest with the test evidence.

R2's S3 compatibility table currently marks `GetBucketVersioning` and `PutBucketVersioning` unsupported. Do not rely on S3 `VersionId` or bucket-versioning behavior. The documented `PutObject` conditional headers include `If-None-Match`; Cloudflare documents atomic evaluation of `If-None-Match: *`, where only one concurrent write to an absent key succeeds. Use both a unique immutable release key and conditional create; never retry by overwriting. See [R2 S3 API compatibility](https://developers.cloudflare.com/r2/api/s3/api/).

## Credential separation and minimum permission

Create no single key that serves both customer downloads and publishing.

| Identity | Minimum documented parent-token permission | Scope and use |
|---|---|---|
| Delivery | **Object Read only**, restricted to the one bucket | Backend reads approved immutable release objects. The app should call only `GetObject` and, if needed, `HeadObject`; it must not list, write, delete, or change bucket configuration. Cloudflare documents that the parent Object Read only permission includes read and list. |
| Publishing | **Object Read & Write**, restricted to the one bucket | A temporary, human-controlled publish session for dummy test objects only. Use only object operations needed for the test. This permission also includes list/read/write, so do not put it in the running delivery service. |
| Cleanup | Separate short-lived publishing session or a separately authorized cleanup identity | Delete only the known dummy keys after verification. Revoke the publishing credential immediately after cleanup. |

Cloudflare's token docs describe bucket-scoped Object Read only and Object Read & Write permissions and note that these object permissions are for the S3-compatible API. The supported S3 temporary-credential flow can narrow operations; its action list supports `GetObject`/`HeadObject` for reading and `PutObject`/`DeleteObject` for writing/cleanup. Action-level temporary credentials currently require local signing, so keep the parent secret in a trusted operator environment and do not put it in a browser, checkout, issue, CI log, or repository. See [R2 token permissions](https://developers.cloudflare.com/r2/api/tokens/) and [R2 temporary credentials](https://developers.cloudflare.com/r2/api/s3/temporary-credentials/).

Do not grant Admin Read & Write, account-wide access, bucket creation/configuration, public access, or Cloudflare dashboard access to the application. The bucket must remain private.

## Controlled upload and read rehearsal

1. Record the authorized bucket and endpoint in the approval record. Confirm endpoint jurisdiction matches the bucket. Do not paste secrets or full account identifiers into a public issue or commit.
2. Start with the synthetic manifest and local dummy PDFs. Independently compute each file's SHA-256 and byte length. Reject any file not exactly one of parts 1–5 or beyond the already agreed production size limit.
3. Obtain the approved short-lived publishing credential through the founder-authorized channel. Put it only into a temporary secret store or environment scoped to the isolated Work session. Disable shell tracing; do not pass secret values as command-line arguments; never echo environment values.
4. Upload to `qa/<release-id>/part-<n>.pdf` using `PutObject` with `If-None-Match: *`. A `412 PreconditionFailed` means the key already exists: stop and generate a new release ID. Do not remove the condition and retry.
5. Read the object back using the separate delivery identity, not the publishing identity. Verify exact bytes, content length and SHA-256 against the local manifest. Verify the key is not reachable through a public URL, website endpoint, or unauthenticated request.
6. Run the adapter against those dummy objects from an isolated local test harness. Verify all five exact keys, integrity failures, missing-object behavior, timeouts, authenticated backend delivery, `Cache-Control: private, no-store`, and revocation. Do not issue a customer-facing or permanent/presigned URL.
7. Capture sanitized evidence: release ID, object keys, checksums, test outcome, permission summary, timestamps, and cleanup result. Exclude access keys, secret keys, session tokens, TOTP values, customer data, and raw private order tokens.

## Backup and restore rehearsal

R2 S3 bucket versioning is not a supported recovery plan for this workflow. Maintain a separate protected backup copy in an independently controlled private location. Keep its credentials separate from both the delivery and publishing identities. Do not make backups public.

For the rehearsal, copy the five dummy objects plus the signed/approved manifest to a separate private backup destination. Verify the backup checksums independently. Simulate loss of one QA release by removing only that dummy release, then restore into a *new* immutable release ID and key prefix. Validate the restored manifest and all five SHA-256 digests before marking the new release usable. Never restore by replacing an existing key. Record who initiated, reviewed, and validated the rehearsal, and document retention/deletion policy. Do not configure production lifecycle, replication, or backup settings during this test.

## Cleanup and revocation

1. Stop the test service and remove temporary credentials from the isolated environment.
2. Using the authorized cleanup identity, delete only the recorded dummy test keys and the dummy backup copies.
3. Verify each exact test key returns not-found using an authorized object read/head request; do not infer deletion solely from a failed prior write.
4. Revoke the publish/cleanup credential and any derived temporary credentials. Confirm the delivery identity remains read-only and bucket-scoped.
5. Remove temporary local files and secret-store entries. Preserve only sanitized manifests, checksums, audit evidence, and the final cleanup report.
6. Report any object that could not be deleted or any credential that could not be revoked as a blocker. Do not begin another test run until it is resolved.

## Founder MFA enrollment and recovery rehearsal

Production founder authentication and all approval/delivery gates must remain disabled during this exercise. Use a synthetic founder in staging and a separate disposable database.

1. Confirm the founder identity through an out-of-band process and record who authorized enrollment. Do not accept identity from a request field or customer claim.
2. Enroll TOTP on the founder-controlled device through the approved server-side enrollment process. Store the seed only in the managed secret store; display it once over the protected enrollment channel. Never put it in source control, chat, logs, screenshots, or shared test output.
3. Verify a current TOTP, then verify replay is rejected. Test expired session, logout, CSRF rejection, Origin rejection, throttling and reauthentication before any approval action.
4. Prepare a recovery process with no approval bypass: temporarily disable founder approvals, require independent identity confirmation by the designated operator, revoke all sessions, rotate the TOTP secret in the secret manager, enroll the replacement device, verify it, and restore the approval gate only after a second reviewer confirms the audit record.
5. Do not use a help-desk password reset, founder-ID request parameter, direct database edit, shared backup code, or customer support channel as a way around MFA. If recovery cannot be completed securely, keep approval disabled and escalate to the repository/service owner.

## Manual settlement-reconciliation rehearsal

Use staging's synthetic settlement simulator only. No live Telebirr/CBE portal or account is accessed in this runbook.

1. Create one synthetic order with the server-controlled 1,500 ETB amount and a fictional recipient.
2. Submit a fictional customer reference and confirm the customer status is Under Review. A reference or screenshot alone never confirms payment.
3. In the founder-only session, compare independently observed simulator evidence to the order: exact reference, recipient, payment method, amount, currency, settlement state/time, and payer identity if reliably available.
4. Simulate wrong reference, wrong recipient, wrong method, wrong amount/currency, pending/unavailable settlement, and an identity mismatch. Every mismatch remains unapproved. A spouse/relative exception may address identity mismatch only and requires documented relationship and rationale; it cannot bypass any other check.
5. Record the settlement observation, then perform explicit approval as a separate action. Confirm a grant is created only after approval and the audit trail identifies the authenticated founder.
6. Test rejection, retry rules, duplicate references, concurrent approvals, grant revocation, and post-revocation download denial. Verify an unauthorized user cannot inspect claims or act for the founder.
7. Preserve sanitized test evidence only. Never use customer-submitted evidence as independent settlement proof.

## Privacy, support and recovery controls

- Do not put private order tokens in URLs, analytics, referrers, browser history, server logs, screenshots, or persistent browser storage.
- The browser holds the code only in memory. The customer must save it privately and reenter it after closing/reloading the tab. Do not promise recovery from a name or phone number alone.
- Before launch, approve a lost-code process that does not grant access based on caller ID or order details alone. If identity proofing is not ready, support can explain that a new secure recovery path is unavailable; do not bypass authorization.
- Collect only name, phone, selected payment method, transaction claim and strictly needed audit information. Set an approved retention and deletion schedule for claims and evidence.
- Approve customer-facing Amharic copy for claim status, rejection, recovery, security notices and support escalation before production.
- Define refund eligibility, processing timelines, refund evidence, escalation owner, Telegram support hours and response target. Do not make a refund promise in the UI until the founder approves policy and copy.

## Exit report and next authorization

The rehearsal report must state the exact test release ID, sanitized manifest hash, whether every dummy object was read and checksum-verified, backup/restore results, deletion results, credential revocation result, MFA tests, settlement mismatch tests and any remaining defects.

Only after this runbook is reviewed should the founder authorize a separate STEP 6.4B provider test that explicitly names the bucket, test files, temporary permission profile, credential handling method, backup destination, test window, and cleanup owner. This runbook itself does not grant that authorization.
