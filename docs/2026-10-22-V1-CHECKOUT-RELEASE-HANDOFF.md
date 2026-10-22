# ParentWise Ethiopia — 22 October 2026 checkout release handoff

**Status:** TESTING / non-payable preview staged in GitHub. **Public sale: BLOCKED.**

## Authoritative homepage
- Approved source: `main/index.html`, Git blob `abfc68887cd0d129e11f2a09512879d2feda0546`.
- Full-site publish file: `site-preview/index.html` — same exact blob, never edited during checkout implementation.
- Do not merge V4 text from PR #13 or PR #16 into the approved homepage.

## Checkout changes only
- `site-preview/order.html`: existing premium three-step checkout visual preserved; fictional labels removed; public prelaunch lockout explicitly shown.
- Payment account details only come from a successful server-priced `POST /api/v1/orders` pending-order response.
- Disabled default: `CHECKOUT_OPEN = false`, `ORDER_API_ORIGIN = ''` (both must be explicitly configured after full acceptance).
- Customer sees *no account number* until a successful persisted order and matching server method/amount response.
- Client idempotent retry, Ethiopian phone and Amharic-name validation, one selected payment method, clipboard, order-reference Telegram message, and session-tab recovery implemented.
- `production_checkout/app.py` now returns the configured recipient on authorized GET recovery and rejects malformed production account lengths.
- `qa-tests/preview_checkout_gate_acceptance.py` covers 320/360/390/768/1280 widths, synthetic account cases, Amharic names, copy, Telegram preparation, reload, simulated API failure and retry. No transfer, live Telegram messaging, or real PDFs were tested.

## Deployment state and blockers
1. **Render manually deployed static service**: `srv-dbcbiemq1p3s73ctil80`, branch `deploy/parentwise-full-site-preview-20261021`; `autoDeploy=no`. The Render connector requires the founder to explicitly select a workspace before triggering deployment. Do not assume a Git push changes the live deployment.
2. **CTA-routing conflict**: locked homepage HTML contains two anchors to `https://parentwise-ethiopia-qa.onrender.com/order.html`, not to the updated preview checkout. No external script is loaded to redirect them without changing the frozen HTML. Founder decision needed: approve exactly two href-only edits and a new locked blob, or accept old-QA routing. Never silently rewrite the approved HTML.
3. **Production API**: No real intake service/database was provisioned in this work. Use isolated production PostgreSQL, not QA. Ensure migrations, origin allowlist, durable secrets, abuse protection and backup/restore acceptance before enabling.
4. **Real recipient config**: Required private service variables `TELEBIRR_ACCOUNT_NUMBER`, `TELEBIRR_ACCOUNT_HOLDER`, `CBE_ACCOUNT_NUMBER`, `CBE_ACCOUNT_HOLDER`. No real numbers or recipient names committed to client/repository. Confirm both recipient names in the financial apps independently.
5. **Telegram DM**: `https://t.me/ParentWiseEthiopia` is configured as the destination but accepting private customer messages is not verified. Test a real private message from a second account, confirm reply capability and a support fallback.
6. **Founder settlement and fulfillment**: test a synthetic receipt against a synthetic settlement, repeated transaction reference rejection, audit record, founder MFA and delivery of all five final PDFs on Android in the same private chat. Do not rely on a screenshot as evidence of settled funds.
7. **Commercial content and policies**: founder approval is required for guarantee/refunds, delivery/support SLAs, privacy/retention and authenticity of any professional testimonials already shown in the locked page.

## Release instructions
- Keep static Render preview non-payable and indexed `noindex`.
- Never deploy `v1_checkout/ci_server.py` publicly or use the QA database for customer records.
- After explicit workspace selection and passing tests, trigger the existing static service deploy and verify the actual Render commit and pages.
- Resolve exactly two homepage CTAs through explicit founder exception approval; do not alter the rest of the frozen design/copy.
- Provision a *separate* production API/database privately and run real-origin staging acceptance using synthetic customers and zero money transfers.
- Enable public orders only after all operational checks and explicit founder authorization. Connect official domain last.

**Rollback:** Prior known live Render commit `70f95e81e085ccfb1ed2ced65037b7a1d6713e3f`. Preserve before any deployment.

**Owner:** Developer for gated source/CI and deploy verification; founder for workspace selection, link exception, recipient ownership, Telegram, policies and fulfillment rehearsal.
