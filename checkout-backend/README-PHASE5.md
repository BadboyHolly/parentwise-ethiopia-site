# ParentWise Ethiopia — Phase 5 QA Dummy Fulfillment

**Status: TEST MODE ONLY.** The API rejects all non-QA configuration and
requires PAYMENTS_ENABLED=false. This workflow **never** sends Telegram
messages, accesses actual bank transactions, uploads real paid PDFs, or
generates public product links.

**QA acceptance: QA ACCEPTED — 10 October 2026.**
Founder completed the live dummy success and failure/retry walkthroughs.
Remaining customer recovery/privacy and access checks passed against disposable
PostgreSQL and synthetic browsers in [run 38058300716](https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/38058300716).
Chrome confirmed live logout and the deployed checkout version fields.
No new live orders were created; no real payment or delivery occurred.
See [Task 05 milestones and Phase 6 handoff](TASK05-MILESTONES.md).

## What the founder can test

1. Sign in with the existing founder password and TOTP.
2. Locate a fictional order with a fully matched and credited internal
   simulated-ledger record. The simulated payment confirmation enrolls the
   order in the **Dummy fulfillment queue**, in PENDING_FULFILLMENT state.
3. Open its details, confirm QA-only preparation, and download the
   founder-authenticated `QA_DUMMY_DELIVERY.txt` text file. It is **not** the
   ParentWise product.
4. Tick the dummy-document inspection acknowledgment and explicitly confirm
   a **hypothetical** dispatch. The database records SENT, not a real
   Telegram action or proof a user received the file.
5. Enter a fictional `QA-ACK-` plus 16 uppercase hexadecimal characters,
   representing an explicitly simulated recipient acknowledgment; confirm.
   The database records DELIVERED **simulation**, never actual Telegram proof.
6. On a second fictional verified order, prepare, record DELIVERY_FAILED with
   a reason, retry into PREPARING, and record another simulated dispatch.
   Duplicate state transitions are rejected.
7. Reopen the order with a customer-specific recovery token. Customer-facing
   output includes only a safe simulated delivery state and version. Founder
   notes, receipt reference and audit entries are not exposed to customers.
8. Log out; the founder's same-origin session is revoked.

The package version is **QA-DEMO-2026.10-v1** and the channel is
`TELEGRAM_FOUNDER_ASSISTED_QA_SIMULATION`.

The real product will eventually contain:
00 Start Here; 01 Core Guide; 02 Action Workbook;
03 Quick Help & Parent Scripts; 04 30-Day Practice Program.
**None of these paid PDFs are stored or downloadable in this QA workflow.**

## Database and authorization

Migration `20261010_04` adds `qa_fulfillments` (one per order) and
`qa_fulfillment_events`. It backfills only older QA-verified orders with an
actual matching internal synthetic ledger record credited to that order,
never orders based on status alone. Database CHECK and UNIQUE constraints
enforce version, channel, states, attempts, and acknowledgment uniqueness.
PostgreSQL FOR UPDATE on order and fulfillment rows serializes concurrent
actions. State and audit event are committed together. An UPDATE/DELETE
trigger enforces append-only PostgreSQL event history.

GET `/admin/api/fulfillment/queue` requires founder session and paginates
eligible QA orders. GET `/admin/api/orders/{code}/fulfillment` requires
founder session. The harmless text download also requires founder login.
All POST mutation routes additionally enforce the original same-origin and
CSRF protections. None of these are customer-accessible.

### Acceptable transitions (dummy-only)

| Before | Action | After |
|---|---|---|
| QA-verified credit | enroll | PENDING_FULFILLMENT |
| PENDING_FULFILLMENT | prepare | PREPARING |
| PREPARING | hypothetical dispatch + dummy check | SENT |
| SENT | explicitly recorded fictional acknowledgment | DELIVERED |
| PREPARING or SENT | recorded failure + reason | DELIVERY_FAILED |
| DELIVERY_FAILED | retry + reason | PREPARING |

A duplicate action, incorrect reference, unverified order, or unauthorized
request is rejected. No resending happens automatically.

## Production buyer identity check — NOT IMPLEMENTED

Telegram usernames, payment screenshots, or possession of an order ID are
**insufficient evidence** that a person is the purchaser. Never ask a parent
to submit the private order-recovery access token in a Telegram conversation.

Before real delivery, establish a separate verified, buyer-bound identity
challenge (for example a rate-limited OTP to the purchasing phone number,
with approved provider and anti-abuse controls). Founder should compare the
actual Telebirr/bank transaction *from provider records* to the order and
confirm an authorized recipient independently. Only after those approvals
should the founder manually send the five versioned PDFs via the official
`https://t.me/ParentWiseEthiopia` channel, and record actual send/receipt
evidence separately. No production delivery code has been written.

## QA acceptance and remaining blockers

CI `.github/workflows/qa-phase5.yml` runs disposable PostgreSQL 18,
existing Phase 1–4 backend regressions, Phase 5 authorization and
concurrency, authenticated synthetic founder Chromium at desktop and
390px mobile, and non-invasive public admin checks. Do **not** automate
real founder login, collect real payment evidence, or burn the shared
12-new-order QA rate limit unnecessarily.

The founder's required live dummy walkthrough is complete, with original
records preserved. Phases 5 and 6 are accepted for QA; see [Phase 6 evidence](README-PHASE6.md).
Production is separately blocked
by independently verified real payment controls, secure buyer-binding,
versioned private product storage, Telegram operations, refunds/terms,
customer privacy, durable PostgreSQL backups, and recipient approval.
