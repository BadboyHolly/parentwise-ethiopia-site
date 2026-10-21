# ParentWise Ethiopia — V1 sales-to-checkout copy consistency acceptance

**21 October 2026** · REVIEW BRANCH ONLY · **NOT APPROVED FOR PUBLIC SALES**

## Source and scope

- Original source: `main` at `4250e3c669a51b4d464cd026020549d5e9329cd4`, root `index.html` (V4.14 QA sales page), and `preview/checkout-amharic-review-20261019` for the locked V1 manual-Telegram checkout UX.
- Cross-checked with `ParentWise_Ethiopia_Sales_Page_Amharic_V4_UXUI_Copy.md` (V4 design-stage handoff; it specifically says Sections 09–11 are not publication-approved), the current QA sales-page HTML, and the V1 checkout implementation.
- Frozen: approved visual composition/CSS, Sections 01–08 messaging including the six-step method, 1,500 ETB one-time five-guide offer, and the checkout’s three-screen UX.
- Allowed scope: purchaser-facing text in Sections 09–11, QA copy safety, and checkout display/instructions. NO production deployments or payment settings are authorized.

## Findings and copy corrections made on this review branch

1. **Wrong order-code promise:** Sales page formerly said buyers are given and must submit an order number. Locked V1 does not expose one. Section 10 now describes name + Ethiopian phone + method, then transfer, then Telegram proof/reference; Section 11 tells a buyer who has paid but not received files to provide the name, phone, and reference/receipt instead of sending money again.
2. **Incorrect fulfillment implication:** Sales page now states that five PDFs are sent in the **same private Telegram conversation only after independent settlement verification**; the checkout now consistently distinguishes a payment claim from verification. An “I’ve Paid” click is not a sale.
3. **Unapproved refund guarantee:** The old live QA sales-page content stated a 30-day full 1,500 ETB refund, even though the policy remains unapproved. The current review version preserves the original panel’s visual structure but describes the **30-day practice program**, not a refund promise. No new refund policy is invented.
4. **Unverified professional testimonials:** The QA page showed named expert claims and portraits that are not independently authenticated and did not match the V4 copy handoff. Review HTML replaces names, claims and portraits with explicitly labeled design placeholders while retaining the same visual slots. **Do not publish placeholders as live credibility proof.** Replace with authenticated written approvals or remove the module at launch.
5. **QA CTA mismatch:** The sales-page purchase button in the review branch targets the **relative** `order.html`, so the staged sales page can be tested with its corresponding locked V1 checkout. In the published QA site, `main` still targets the QA-only order page; nothing was changed there. Public checkout remains non-payable with fictional recipients.
6. **Pre-payment Telegram requirement:** Copy makes Telegram confirmation and manual guide delivery clear before purchase; buyers without Telegram need an agreed functioning alternative before any real payment is accepted.
7. **Copy hygiene:** Do not claim instant delivery, guaranteed behavior change, expert endorsement, app approval, or automatic settlement. Retain the existing medical/development disclaimer.

## Acceptance evidence

- Github Actions workflow `V1 sales and checkout copy review — isolated synthetic browser acceptance` (latest run `39582945249`): **PASS**.
- Viewports: **320 / 360 / 390 / 768 / 1280 px**. Tests cover CTA handoff, form validation, Telebirr/CBE selection, recipient-to-method matching, both payment-recipient copy buttons, customer review, prepared Telegram confirmation copy, and no non-GET requests. The workflow saved responsive screenshots as artifact `parentwise-v1-copy-review-screenshots` (ID `12344276425`, available for seven days).
- Both selected logos loaded from local static assets. Real recipient numbers do not appear in review `index.html` or `order.html`.
- Production branch `main` remained unchanged at `4250e3c669a51b4d464cd026020549d5e9329cd4` when checked. No Render deployments, production modifications, real payments or order writes.

## Release blockers (not solved by copy)

- Native Amharic review and final sign-off for the new purchaser-facing instructions.
- **Actual, private Telegram messaging test** and approved non-Telegram fulfillment channel.
- Define realistic support/fulfillment hours and notify buyers before payment.
- Approve and publish a clear refund/support policy; no unconditional “30-day refund guarantee” until verifiable.
- Authenticate any professional endorsements and obtain scope/permission, or remove the testimonial section from public-sale release.
- Independently verify recipient ownership inside Telebirr/CBE apps and configure accounts through private production environment; the QA copy branch must NEVER include real recipient numbers.
- Secure pending order persistence from name, phone and method *before* enabling payment instructions. Do not store buyer PII only in browser state, analytics, Telegram URLs or public pages.
- Founder-only verified settlement matching, duplicate-reference prevention, audit trail, and successful test of manual sending/reopening all five finalized PDFs.
- Test closed-browser/changed-device buyer recovery and a buyer without Telegram.
- The final Amharic PDF content and preview thumbnails/page references need approval.

## Next workstream: STEP 2 — checkout integration (NOT ACTIVATED)

**Status:** BUILDING. **Owner:** Developer and founder. **Dependency:** This copy alignment passing and founder operational decisions above.

1. Branch from an explicitly reviewed source; keep the approved `main` and existing Render preview untouched.
2. Wire the V1 customer form to a *separate isolated development/test environment* with secure server-priced 1,500 ETB pending order records; use fictional data/accounts only.
3. Ensure idempotent retries, no duplicate orders, secure PII storage, and a server-generated internal reference that does not burden the buyer.
4. Preserve payment and founder approval OFF. “I’ve Paid” must never produce a verified-paid state or trigger PDF delivery.
5. Simulate account selection and Telegram message preparation, then independently approve a synthetic settlement and simulate five document deliveries. Founder verifies actual transfer manually when launch is approved.

**Pass gate:** 100% of critical test cases pass: no data loss, duplicate payment match, unverified claim, customer app-switch interruption, Telegram failure and manual delivery audit. No actual money, live recipient details or real user data in tests.

## Central decision log entry

Date: 2026-10-21. Decision: freeze V4.14 visual layout, align V1 manual-Telegram buyer instructions, hold unsupported guarantees and testimonials; do not modify production. Rationale: prevent purchase confusion and misleading claims. Evidence: source comparison + Playwright synthetic acceptance run. Owner: founder/developer. Affected: 01 Master Business Strategy, 05 Website & Funnel, checkout implementation, credibility and fulfillment. Review trigger: native Amharic approval, verified messaging, founder policy approval, secure end-to-end acceptance.
