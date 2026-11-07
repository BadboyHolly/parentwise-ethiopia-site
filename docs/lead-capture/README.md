# Lead capture for ParentWise checkout: findings, design, review wording

> **UPDATE 2026-11-08 (supersedes the "no tick box" decision below).** Order contact (a small notice) and promotional follow-up (a separate, optional, unticked opt-in that can be stopped) are now separate. The first release collects only name, phone, checkout progress and follow-up preferences; child age groups, challenge tags and notes are switched off. Retention has no default and is a proposal only. See **OPT-IN-WORDING-FOR-REVIEW.md** (this folder) and, in the backend repository, **RETENTION-AND-PURGE-PROPOSAL.md**, **PRODUCTION-PLAN.md** and **CONCURRENCY-RESULTS.md**. Where this older text disagrees, the newer documents win.

Status: **built and tested, not deployed, switched off.** Nothing here changes the live site or stores customer data until you
switch it on (see "Before real customer data").

## 1. What happens today (inspected 2026-11-07)

Live checkout: `site-preview/order.html` (manual Telebirr/CBE + Telegram flow, order system closed).

| Customer action | What happens today |
|---|---|
| Enters name + phone, presses **Continue** | The values are checked in the browser, kept only in the page's memory, and shown on the payment screen. **Nothing is sent or saved anywhere.** |
| Reloads the page | The page returns to step 1. The typed name and phone are gone. |
| Returns later | You have no record of them. |
| Abandons at any step | You never know. The only trace is the anonymous visit counter (`pw-track.js`), which by design carries no name or phone, and it is switched off unless an endpoint is configured. |
| Presses the Telegram button | The browser opens a Telegram link with a pre-filled message (name, phone, method, amount). Whether the customer actually presses *send* is unknown to you and to the site. |

The backend (`production_checkout`) already has an order API (`POST /api/v1/orders`) that would store name and phone, but it is **closed**
(`ORDER_INTAKE_ENABLED=false`, answers 503) and creates an *order*, which is the wrong object for a lead. It was not touched or opened.

## 2. What was built (smallest secure version)

**A separate lead record, with its own switch.** `POST /api/v1/leads`, closed unless `LEAD_CAPTURE_ENABLED=true`. It creates no order,
no payment state and no revenue. `ORDER_INTAKE_ENABLED` and payments stay `false`.

- **Saved when:** the customer continues from the details step (details pass validation and the payment page opens).
- **Matching:** the phone is normalised (`0911…`, `+251911…`, `251 911…`, `0911 22 33 44`, `00251…`, Arabic-Indic digits, spaces/dashes) and matched with a keyed hash,
  so repeat submissions update one lead. Every visit is stored as a separate **attempt**; reloads/double-clicks of the same attempt are ignored.
- **Progress, never going backwards:** 1 details submitted, 2 saw payment page, 3 pressed "I have paid" (not verified), 4 saw proof page, 5 pressed the Telegram button.
- **Returned:** a new attempt 30+ minutes after the last activity counts as "came back".
- **Contacted us:** a Telegram click is stored as a click only. "The customer contacted us" is recorded **only when you tick it** in the dashboard.
- **Verified buyer:** derived at read time from founder-approved orders with the same phone. Leads, orders and revenue stay in separate tables; a verified buyer can come back and buy again
  (the dashboard shows "verified repeat buyer"), and a lead never changes revenue.
- **Protection:** name and phone are AES-256-GCM encrypted (field-bound); only a keyed hash is searchable; origin check, 2 KB size cap, rate limits per IP, attempt and phone;
  the public answer never reveals whether a number was already known; no cookies; later steps carry no personal data.
- **Follow-up notice (decided: no tick box):** checkout shows one small line under the details form saying we will contact the customer about their order with this information, with a link to the details. The lead records that the line was shown. Without that record the dashboard refuses to move a lead to *contacted / in conversation / interested* unless you first record that **the customer contacted us**. *Do not contact* cannot be undone.
  *contacted / in conversation / interested* unless you first record that **the customer contacted us**. *Do not contact* cannot be undone.
- **Your control:** the Founder dashboard has a **Leads** tab: search by phone, status (new, contacted, in conversation, interested, not interested, do not contact), next follow-up time,
  "left checkout" (no activity for 2 hours and not a buyer), funnel counts, and **Erase lead** (permanent, keeps only a person-free proof row). Expired leads (12 months by default) can be purged.
- **Later hand-off to an agent:** each lead has an `assigned_to` field and a status history ready for that.

Not built on purpose: automatic messaging, automatic Telegram/SMS sending, exporting lists, any marketing/ad-platform sharing.

## 3. Wording for your review (not live)

The checkout shows this only when lead capture is switched on. **Amharic drafts need a native reader.**

**Small line above the "continue to payment" button** (shown only when capture is on):
> ስለ ትዕዛዝዎ በዚህ መረጃ እናገኝዎታለን። ዝርዝር

English meaning: *We will contact you about your order using this information. Details* (the last word links to the privacy policy).

**No tick box.** Nothing for the customer to tick; the line above is the only addition.

**Proposed additions to `policies/privacy-policy.html`** (draft; not applied):
- §2 *What we collect*: "The name and phone number you enter at checkout, saved when you continue, even if you do not finish your order."
- §3 *Why we use it*: "To help you finish your order, verify your payment, and to contact you about your order by Telegram or phone using the details you gave."
- §4 *Sharing*: "We do not sell your details." (confirm this is true for every provider you use before publishing)
- §7 *How long we keep it*: "Details from unfinished checkouts are kept for up to 12 months, then deleted. You can ask us to delete yours at any time through Telegram."
- Also state who is responsible for the data and how to ask for access or deletion.

Decided: no tick box, a short notice only. Still open: (a) retention (default 365 days, configurable 30 to 1,095); (b) confirm with a lawyer that a notice without a tick is enough for contacting people who did not buy (the box is the safer route if the lawyer says no); (c) have the wording and the legal basis checked against Ethiopia's personal data protection law (Proclamation No. 1321/2024 as I understand it; I am not a lawyer).
(c) have the wording and the legal basis checked against Ethiopia's personal data protection law (Proclamation No. 1321/2024 as I understand it; I am not a lawyer).

## 4. Tests that pass

Backend (SQLite, 37 tests; PostgreSQL run in CI): phone formats and rejections, encryption at rest, reload/double-click, same phone in different formats, return after a break,
different people, same attempt id with another phone, notice never silently removed, forward-only steps, Telegram click is not contact, rate limiting/origin/size/disabled gate,
leads never create orders, verified buyer and repeat purchase derivation, follow-up rules and audit, erasure, retention purge.
Browser (`qa-tests/lead_capture_checkout.py`, CI): dormant by default, exact payloads and order of events, one attempt per phone per tab, reload, edited phone, invalid details send nothing,
a failing endpoint never blocks checkout, a 409 triggers one resend of details, no horizontal scroll at 375 px.

## 5. Before real customer data can be stored

1. Your approval of the wording above and of the retention period; native Amharic review; legal check.
2. Database migration `0009_create_lead_capture.sql` applied on the target database (with a verified backup), using the existing migration runner.
3. Settings (names only): `LEAD_CAPTURE_ENABLED=true`, `LEAD_HASH_KEY` (random, 32+ characters), the existing `PAYMENT_DATA_KEYRING` / `PAYMENT_DATA_ACTIVE_KEY_ID`, `ALLOWED_ORIGINS` = the website's exact https origin,
   `ORDER_ENVIRONMENT=production`. Keep `ORDER_INTAKE_ENABLED=false` and `PAYMENTS_ENABLED=false`.
4. A production backend with its own address (the dashboard cookie needs the app at the root of its own address) and a restricted `FORWARDED_ALLOW_IPS`; fresh secrets (the test ones were exposed).
5. On the website: set `<meta name="pw-leads-endpoint" content="https://<backend>/api/v1/leads">` in `order.html` and deploy (a separate, deliberate step).
6. Publish the privacy-policy changes at the same time as the switch. Decide who may open the Leads tab (today: the founder login only).
7. A routine for retention (the purge button/endpoint is manual until a scheduled job exists) and for deletion requests.

Limits to know: phone numbers can be mistyped or belong to someone else (a lead is a claim, not an identity); a customer who clears their browser data or uses another device starts a new attempt,
but is matched to the same lead by phone; blocked or failed requests mean some leads will be missed (checkout is never blocked on purpose).
