# STEP 6.4A — Five-Parent Usability Test Protocol

**Status:** Prepared only. No participant research has been performed. Do not describe the checkout as user-tested until five sessions have been completed and recorded.

## Purpose

Check whether first-time Ethiopian digital-product buyers can understand and complete the fictional checkout on a phone, understand manual payment review, save/reenter the recovery code, and locate the downloaded dummy files.

## Participants and setup

- Recruit five Ethiopian parents who have not bought a digital product through this checkout before.
- Test in a language the participant is comfortable using. Do not ask them to evaluate Amharic wording that has not passed native review.
- Use a local isolated staging build, fictional Telebirr/CBE recipients, synthetic founder MFA, disposable PostgreSQL and dummy PDFs.
- Use a test Android phone at 320–390 CSS px where possible; record device/browser and network conditions. No participant should use a real account, phone number, payment, or personal recovery code.
- Obtain consent to observe the task and record anonymized notes. Do not capture faces, voice, phone notifications, personal payment screens, or identifiable data.
- One facilitator reads each task verbatim, then stays quiet. Do not coach unless the participant asks; note any help given.

## Tasks

1. “Please order this guide using the fictional payment option shown. Tell me what you would do next.”
2. “You have sent the fictional transfer. Show me where you would find its reference and what you would submit.”
3. “The page says it is checking your reference. Tell me whether payment is confirmed.”
4. “Save the recovery code in a way you trust. Now reload the page and find this order again.”
5. “After approval appears, download all five guides. Show me where you would find one of them on this phone.”
6. “If you become stuck, show me where you would get help.”

Use a scripted fictional settlement in the founder simulator. Do not solicit any real transfer.

## Record for each participant

- Completion without assistance (yes/no) and total elapsed time.
- Every hesitation, backtrack, repeated click, error, or request for help.
- Whether the participant can explain that submitting a reference is only a claim and payment remains pending.
- Whether the recovery code is saved and successfully reentered after reload, without storing it in browser storage.
- Whether all five downloads complete and the participant can find/open a PDF.
- Whether the participant can find official Telegram support.
- Any accessibility barrier, lost connection or low-bandwidth problem.

Use participant labels P1–P5. Do not include names, phone numbers, account details, actual recovery codes or recordings in the report.

## Acceptance targets

- At least 4 of 5 finish the simulated purchase without assistance.
- All 5 correctly understand that a submitted reference does not confirm payment.
- All 5 find the support option.
- No critical security or payment-understanding failure.
- Record download and recovery success separately; unresolved failures require a fix and retest.

Report results as observed, including failures and assistance. Do not adjust the record to meet the target. A usability pass does not replace security testing, native Amharic approval, payment reconciliation, or production readiness.
