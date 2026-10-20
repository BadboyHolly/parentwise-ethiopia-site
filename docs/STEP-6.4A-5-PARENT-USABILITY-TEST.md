# STEP 6.4A.2 — Final Five-Parent Usability Test Protocol

**Status:** Prepared only. No parent sessions have been conducted. Do not claim real-parent validation until all five sessions occur, are documented and reviewed.

## Objective

Test whether five Ethiopian parents buying a digital product for the first time can complete the existing three-step checkout, protect their order recovery details while switching to a payment app, understand manual settlement review, recover after losing browser state, and find the five downloaded files.

## Setup and participant privacy

- Use an isolated staging copy, fictional Telebirr/CBE recipients, synthetic founder MFA, disposable PostgreSQL and five dummy PDFs.
- Test on phones at 320–390 CSS px where possible; capture 768 and 1280 desktop/tablet behavior in automated tests.
- Do not use a real transfer, provider account, customer record, phone number, notification, SMS or final PDF.
- Use a separate fictional payment-app simulation page. Never open Telebirr/CBE.
- Obtain consent for anonymous facilitator notes. Do not record faces, voices, real notifications, screens containing personal data or recovery secrets.
- Use only labels P1–P5. Do not place any names, phone numbers, account details or recovery codes in the report.
- Have founder and native Amharic reviewers approve all temporary English meanings and the final Amharic wording before sessions use that copy.

## Session script

1. Ask the participant to enter synthetic details and create the order.
2. Before payment, ask them to save the order number and recovery code using their preferred private method.
3. Have them copy both together, then copy the fictional payment number. Ask them what changed and whether the copy message proves the details were saved.
4. Ask them to switch to the fictional payment-app simulation and return to the browser.
5. Close or reload browser state. Ask them to recover the pending order with the saved order number and recovery code before continuing.
6. Present a fictional transfer-completed scenario. Ask them where they would find the transaction reference, then submit a synthetic claim.
7. Ask whether the submitted reference means payment is confirmed. Run pending, rejected/not-matched, and founder-approved scenarios separately.
8. After approval, ask them to download guides 00–04, starting with 00 — ከዚህ ይጀምሩ. Ask where they would find the first file on Android.
9. Simulate a brief network interruption and retry the status refresh. Then explain a revoked or unavailable download.
10. Ask them to find optional official Telegram support.

## Observe and record

For each task, record completion, elapsed time, assistance, pauses, repeated taps, errors, recovery success, accessibility barriers and any low-bandwidth issues. Note whether the participant:

- Understands that a reference is a claim, not confirmation.
- Understands the account-number copy replaces previously copied order details.
- Saves and reenters both recovery details after losing page state.
- Knows not to pay again while a submitted claim is pending or not matched.
- Finds all five guide downloads and locates a downloaded PDF.
- Can identify the support path and explain a revoked-access message.

## Acceptance targets

- At least 4 of 5 complete the simulated journey without facilitator assistance.
- All 5 understand that a submitted reference is not payment confirmation.
- All 5 save and recover an order after page state is lost, and find support.
- No critical privacy, payment or authorization misunderstanding.
- Record every failure and assistance honestly; fix critical problems and retest before claiming usability acceptance.

This study does not verify provider behavior, payment reconciliation, production security, native copy quality outside the reviewed version or production readiness.
