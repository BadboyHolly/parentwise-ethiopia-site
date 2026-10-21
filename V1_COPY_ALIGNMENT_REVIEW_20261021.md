# ParentWise Ethiopia — isolated V1 copy alignment (21 Oct 2026)

**Status: REVIEW ONLY. No production deployment, order intake, real payments or PDF delivery authorized.**

## Original source conflicts resolved in review branch

1. Sales Section 10 promised buyers a customer-facing order number; locked V1 checkout does not give them one. Replaced with name, phone and selected payment method.
2. Sales purchase Step 03 and FAQ #3 required this missing order number. Both now request name, phone and payment receipt / transfer reference for Telegram reconciliation.
3. Sales Section 10 stated a 30-day money-back guarantee and unconditional-looking full-refund copy, despite the V4 handoff explicitly labeling terms unapproved. Replaced the offer-area copy with **30-day practice plan**, leaving the approved brand layout and text outside the transaction section unchanged.
4. Sales Step 04 lacked the exact delivery channel. It now states that all **five PDF guides** are sent in the **same Telegram private chat** only after independent payment verification.
5. Payment-method note now tells prospective customers to check private Telegram messaging before paying and contact ParentWise to arrange an alternative first if they do not have Telegram.
6. The isolated checkout review branch `review/v1-checkout-copy-consistency-20261021` aligns key form, payment, errors and Telegram confirmation copy to Amharic-first behavior without changing customer workflow, URLs, DOM structure, branding or payment safety. Public preview recipients stay fictional.

## Source protection / evidence

- Sales root `index.html` and `public/index.html` have identical new Git blobs on this review branch.
- Source `main` and all Render services remain unchanged.
- Sales HTML element tag count unchanged; changes are limited to exact text replacements.
- Checkout branch passed isolated Playwright checks for 320, 360, 390, 768, 1280 px; no non-GET data transfers, fictional account codes remain, Telegram link stays https://t.me/ParentWiseEthiopia.

## Open publication blockers (not safe to invent)

- Confirm and document professional review identity, credentials, original quotations and permissions before public use.
- Replace source-reference English PDF previews with final verified Amharic pages where required.
- Approve refund eligibility, channel, deadlines and processing timeline before restoring any money-back guarantee.
- Validate Telegram actually receives private messages from unfamiliar customer accounts; implement a functional alternative delivery option and communicate genuine response hours.
- Verify real bank-side recipient ownership, duplicate-claim reconciliation, secured order data retention, founder verification and manual delivery before accepting funds.
- Have a native Amharic reviewer confirm every newly introduced customer-facing sentence.

## Next development step

**STEP 2 — Secure pending order + founder manual reconciliation (synthetic tests first).** Keep live payment/order feature switches disabled until a separately authorized production release.
