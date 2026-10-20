# Manual settlement reconciliation — production founder procedure

This procedure is required before a founder records settlement evidence or approves a claim. A customer-entered reference, receipt, screenshot, email, or chat message is only a claim and is never proof of settlement.

## Reconciliation steps

1. Sign in directly to the official Telebirr business/recipient account or CBE account/statement using a separately secured device and MFA. Do not open a customer-supplied link, use a screenshot, or rely on a forwarded statement.
2. Locate the actual posted transaction in the provider ledger. Confirm it is settled/credited (not pending, reversed, failed, or merely initiated).
3. Compare the transaction reference character-for-character with the customer's claim. Check the payment method, exact configured recipient, amount **1,500 ETB**, currency **ETB**, and settlement date/time.
4. Compare payer identity only when the provider exposes it reliably. If it is unavailable, unclear, or mismatched, do not assert a match. Leave the claim pending or reject it. A third-party payer can proceed only through the separate documented exception workflow; that exception does not waive any other settlement check.
5. In the founder console, record the values observed in the official ledger and attest that this entire manual procedure is complete. This attestation records the founder's observation; it does not replace explicit approval.
6. Review the server-computed comparison result and approve only when the reference, method, recipient, amount, currency, and required payer identity all match. A claim or evidence record alone must not create a download grant.

If the official ledger cannot be accessed or any required field cannot be reliably confirmed, stop. Do not approve based on customer-provided material or memory. Reconcile later or reject with a clear reason.

## System enforcement

The settlement HTTP request requires `manual_reconciliation_completed=true`, a founder session, CSRF token, allowed Origin, a supported evidence source, a timezone-aware settlement time, and an explicit payer mobile. False or unavailable payer identity cannot be represented as verified. Server-side approval separately matches the submitted claim and founder-observed settlement against the order and protected expected recipient. An identity mismatch requires a founder-documented third-party exception followed by an independent approval action.

The attestation is an operational control, not cryptographic proof that a human viewed a provider ledger. Before launch, the founder must adopt this procedure, protect direct provider access with MFA, and review the audit trail.
