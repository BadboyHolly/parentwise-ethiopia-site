# STEP 6.4A.2 — Payment Reconciliation Feasibility and Blockers

**Status: BLOCKED pending a separately authorized provider-record exercise.** No Telebirr/CBE account, live settlement record, provider credential, or customer payment was accessed during this work. This document reports what the checked-in production code requires; it does not claim those fields are available in either provider interface.

## Fields required by production code

Reviewed at this branch baseline in:

- production_checkout/founder_security.py — SettlementInput and settlement route
- production_checkout/founder_security.py — founder configuration and private recipient construction
- production_checkout/payment_state.py — record_settlement_evidence and approve_payment

The founder settlement request requires:

| Field | Code requirement | Independent source needed |
|---|---|---|
| Order and claim | Existing order ID and claim ID | Founder console's pending claim record |
| Transaction reference | observed_reference; normalized/HMAC-digested and globally unique | Telebirr transaction details/portal or CBE bank statement/transaction record |
| Payment method | telebirr or bank and equal to both order and claim | Provider record / statement |
| Amount and currency | amount must match 1,500 ETB on the order and claim; currency ETB | Settled transaction entry |
| Recipient | recipient_confirmed must be true; code hashes the protected configured recipient string | Confirmed destination account/number and account-holder name |
| Payer identity | payer_mobile is required in Ethiopian E.164 form | Provider record that identifies payer, or a separately documented third-party exception |
| Settlement state and time | evidence_source is TELEBIRR_PORTAL or BANK_STATEMENT; settled_at must include timezone and cannot be future-dated | Record showing completed/settled status and transaction date/time |
| Manual checks | manual_reconciliation_completed must be true | Founder follows and attests to the independent checklist |
| Notes | Optional note, encrypted before storage | Short audit rationale; provider statement images/files are not accepted by this route |

Production configuration joins recipient number and holder name into a canonical server-side value before hashing it. Approval compares the recorded recipient digest to this protected expected value. The approval routine also compares claim and settlement reference digests, payment methods, exact amount, currency and payer identity.

For payer identity, the normal rule is an exact match between the independently observed payer mobile and the buyer phone stored on the order. A mismatch requires a documented founder exception tied to the same order, claim and evidence; the exception is limited to identity mismatch. It cannot waive reference, method, amount, currency, recipient or settlement-state checks. The code requires a payer mobile even for third-party payment. If the payer cannot be reliably identified, approval must remain blocked.

## Limits in the current implementation

- The route accepts founder-entered observations plus boolean attestations recipient_confirmed and manual_reconciliation_completed. It does not query a provider API or independently validate provider data.
- There is no structured observed account-holder field. The recipient digest binds the configured account number and holder, while recipient_confirmed is an authenticated founder attestation that the record showed the expected recipient. The present implementation does not preserve a separately verifiable provider-returned beneficiary name.
- There is no provider statement or receipt file upload. Only a source enum, transaction fields, timestamp and encrypted short note are stored. This avoids storing receipts but means the system does not retain the underlying statement.
- We have not verified whether Telebirr or CBE records expose payer phone reliably, whether a CBE payer account can be mapped to the buyer mobile, or how either provider labels pending, reversed, failed, settled or corrected transactions.
- We have not verified whether transaction references are stable and unique across account types, channels, reversals or days, nor whether provider timestamps have a reliable timezone.
- Staging uses simulated settlements and fictional recipient codes. It cannot demonstrate provider record visibility or reconciliation accuracy.

## Questions for the separately authorized provider exercise

For each payment method, founder should use a read-only provider record or approved statement and answer:

1. Can the record identify an unambiguously completed/settled credit, separately from pending, failed, reversed or refunded entries?
2. Does it show the full transaction reference exactly as the customer sees it?
3. Does it show amount, currency, recipient number/account and recipient/account-holder name?
4. Does it show payer identity in a form that can be compared reliably with the checkout phone? If not, what trustworthy identity is exposed and can it support the existing documented exception process?
5. Does it show a settlement timestamp and timezone, and can corrections or reversals be tracked to the original entry?
6. Can two entries share a reference across Telebirr/CBE, channels, dates or reversals?
7. Can the founder perform a written manual checklist while keeping credentials and customer records out of logs, screenshots, analytics and support chats?

The exercise must use only provider access and records specifically authorized by the founder for that exercise. Record the answers and sanitized field names, not credentials, full account numbers, customer data or statement images.

## Acceptance outcome

**BLOCKED:** Provider-specific field availability, payer identity reliability, settled-versus-reversed status semantics, and manual evidence traceability have not been demonstrated. Keep payment approval and delivery feature gates disabled until the authorized exercise validates these fields and the founder approves any required operational procedure. Do not relax payer matching or third-party exception controls to work around unavailable provider fields.
