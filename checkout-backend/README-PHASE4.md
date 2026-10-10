# ParentWise Ethiopia — Phase 4 simulated reconciliation (QA ONLY)

**Hard guard:** APP_MODE=qa and PAYMENTS_ENABLED=false. No real recipient details,
bank/Telebirr APIs, payment screenshots, real refunds, PDF links, or delivery.
Founder must authenticate by existing password + TOTP and every mutation
requires existing Secure HttpOnly session cookie, strict Origin, and CSRF header.

## Founder simulator (not real financial verification)

Open https://parentwise-orders-api-qa.onrender.com/admin and view a **fictional
QA order**. In the order detail:

1. **A:** Create a server-generated **fictional ledger credit** for the order's
   method. Choose 1,500 ETB for the positive path or 1,400 ETB for discrepancy.
   This is local synthetic test data, not an independently verified external
   provider record or proof of real funds.
2. **B:** Record a simulated customer claim with the generated QA reference and
   reported amount. Only QA-TB- or QA-BK- plus 16 uppercase hex digits accepted.
3. **C:** Start the server-side independent check. It reads the **separate
   internal simulated-ledger row** and checks reference, method, amount,
   currency, and unused status. It does not accept client supplied `MATCHED`.
4. **D:** Review the history and explicitly confirm via the second confirmation
   prompt. Confirmation requires a server-side MATCHED record and atomically
   credits the ledger fixture to a single order. No money has moved and no
   product will be delivered.
5. For discrepancies, use **Reject simulated claim** with a reason. The
   order returns to PENDING_PAYMENT and may receive a **new fictional ref**.
   References already submitted remain globally reserved. Use **Cancel test
   order** for a terminal cancellation before verification.

Status flow:
PENDING_PAYMENT -> PROOF_SUBMITTED -> VERIFYING -> VERIFIED_PAID.
Reject: PROOF_SUBMITTED/VERIFYING -> PENDING_PAYMENT.
Cancel: PENDING_PAYMENT/PROOF_SUBMITTED/VERIFYING -> CANCELLED.
Never transition a simulated paid order to a real payment or deliver any PDFs.

## Database

Alembic revision `20261010_03` changes the previous pending-only check and
creates `qa_simulated_ledger`, `qa_payment_reviews`, `qa_payment_events`.
Unique (payment_method, reference) constraints prevent cross-order credit;
credited_order_id is unique. Founder mutations lock order/review/ledger rows
via PostgreSQL FOR UPDATE and commit decision + audit in one transaction.
PostgreSQL trigger blocks UPDATE/DELETE of reconciliation events.

The single-founder `admin_audit` security log remains intact. The new
reconciliation history is separate and append-only. Historical claims remain
even after rejection.

## Test evidence

CI `.github/workflows/qa-phase4.yml` runs migrations on disposable PG18,
synthetic-founder backend verification races, customer API regressions, live
anonymous admin/checkout browser checks, and isolated authenticated
desktop/mobile browser interaction with synthetic credentials.

These tests are not substitutes for a final manual **live founder** walkthrough
of the new actions. No login automation may use the real founder's password,
TOTP code, secret, or live login quota.

## Owner acceptance gate (after deployed migration)

Sign in normally with existing credentials. Choose a **fictional QA order**,
create test ledger fixture, record proof, check, explicitly confirm; verify
the order moves to VERIFIED_PAID and customer recovery shows the **simulated**
status. Repeat on a second fictional order with a 1,400 ETB ledger fixture,
confirm VERIFY is disabled, reject it, and check event history. Then log out.
Never enter actual transaction references or send any money.

**Production blockers:** real recipient approval; independent financial
statement checking against provider records; verified transaction ownership;
order and session retention; database durability and backup; payment terms,
refund workflow, protected delivery, and legally reviewed customer disclosures.
