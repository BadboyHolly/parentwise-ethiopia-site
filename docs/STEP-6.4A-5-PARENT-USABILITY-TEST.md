# STEP 6.4A.4 — Final Five-Parent Usability Test Protocol

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

1. Ask the participant to enter synthetic details, review the 1,500 ETB total, choose Telebirr or CBE, and create an order.
2. In the payment stage, ask them to locate the order number and private recovery code. Have them use the single Copy Order Details action, then save the block privately by their preferred safe method. Ask whether copying proves the block was saved.
3. Ask them to select Continue to Payment, copy the fictional payment number, and explain what happened to the clipboard. Have them switch to a separate fictional payment-app simulation and return to the checkout.
4. Reload or close the browser tab. Ask them to recover the order by pasting the complete saved block into one field. Do not help them split it unless they choose the separate-field fallback.
5. Explain a fictional transfer scenario. Ask where the transaction reference can be found, then submit a synthetic claim. Ask whether that reference confirms payment.
6. Show the pending state and ask what they would do next. Present an unmatched/rejected claim separately. Confirm they understand not to pay again if they already transferred money and can return later with their saved details.
7. Run an approved scenario using the synthetic founder console and simulated settlement. Ask them to refresh status and find all five authorized downloads, starting with 00 — ከዚህ ይጀምሩ.
8. Ask where the downloaded file appears on Android. Check that the facilitator confirms a completed browser download before calling it downloaded.
9. Simulate a failed claim request, brief network interruption, duplicate Continue tap, and a revoked/unavailable download. Ask them what they would do.
10. Ask them to locate optional official Telegram support. Do not require them to contact support or leave a real message.

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
