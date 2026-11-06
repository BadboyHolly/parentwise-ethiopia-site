# ParentWise Ethiopia — customer data inventory and DRAFT policies for founder review

Status: **DRAFT, 2026-11-06. None of this is approved.** Retention periods, refund terms and reply times below are **proposals**.
Items marked ⚖ need review by an Ethiopian lawyer before use (data-protection, consumer-protection, e-commerce, tax and
record-keeping rules; I am not giving legal advice). The manual process already handles customer data today, so these decisions
matter for it now. The new backend must not store real customer data until you approve them.

## 1. What customer information exists, where, who can see it
| # | Data | Where it lives | Who can access | In the manual process now? | In the backend (later)? |
|---|---|---|---|---|---|
| 1 | Name and phone typed on the order page | **Not saved by the website** (checked in an automated browser test: nothing is stored in the browser and no order server is contacted). On the last screen they are placed in the **prefilled Telegram message link** that opens Telegram (sent to Telegram only when the customer taps send) | The customer; Telegram once sent | Yes | Yes, in the database |
| 2 | Name, phone, messages, **receipt screenshots**, payer details | **Telegram** (your chat; Telegram's servers) | You; Telegram as provider; anyone with your phone/account | **Yes** | No (stays in Telegram) |
| 3 | The payment itself: amount, time, payer, transaction reference | **Telebirr and CBE records** (your accounts) | You; Telebirr/CBE | **Yes** | Reference stored encrypted/hashed |
| 4 | **Order log** (section 4 of the checklist) | One access-controlled spreadsheet | You (+ named technical owner) | **Yes (to create)** | Replaced by the dashboard |
| 5 | Backend: order record (name, phone, amount, status, time) | AletCloud PostgreSQL | You via the founder login | No | Yes |
| 6 | Backend: payment-claim reference (encrypted), approval decisions, audit log | Same database | Founder only | No | Yes |
| 7 | Backend: founder login sessions | Same database | System | No | Yes (expire after hours) |
| 8 | Backups of the database | The host's backup storage | Host staff technically; you/technical owner | No | Yes |
| 9 | Website visit counters (anonymous) | **Not active** (the tracker is switched off) | — | No | Optional later |
| 10 | Website host's access logs (may include IP address) | Render (static host) | Render | **Yes (provider-side)** | AletCloud for the app |
| 11 | The five PDFs and delivery | Your device/Telegram; later private storage | You; the buyer | Yes | Optional later |

Not collected: payment-app passwords, OTP codes, card numbers, the child's name/photo/health information.
**Check:** the existing privacy page mentions collecting IP address and "payment service" providers; in the manual launch you do not use a
payment service, and IP logging is done by the host. The text should be made to match reality ⚖.

## 2. Proposed retention *(not approved; ⚖ confirm minimums required by law, e.g. accounting/tax records)*
| Category | Proposed period | Then |
|---|---|---|
| Order log rows and payment confirmations | 24 months after purchase *(accounting rules may require longer)* | Delete/anonymise |
| Telegram chats with customers | Keep while support/refund may be needed; **delete receipt screenshots 30 days after the refund window closes** | Delete the images, keep the log row |
| Refund requests and decisions | 24 months | Delete |
| Backend order data and audit log | Same as the order log | Delete/anonymise |
| Database backups | 30 days of history *(depends on the host plan)* | Auto-expire |
| Founder sessions | 8 hours | Auto-expire |
| Anonymous visit data (if ever enabled) | 13 months | Delete |

## 3. Who can access what (proposal)
Only you (and a named technical recovery owner, when appointed) may open the order log, the dashboard and the database. Telegram and the banking
apps are protected by your own phone and account security: **use two-step verification on Telegram, Telebirr, the email account and the log's account,
and a screen lock on the phone.** Hosting staff can technically reach stored data; the policy should say so plainly ⚖.

## 4. DRAFT customer wording (plain English; translate to Amharic and have a native speaker and the lawyer review ⚖)

**Privacy summary (to sit above the full policy)**
> "To sell you ParentWise we collect your name and phone number and the payment confirmation you send us. We use them only to confirm your payment, send your PDFs,
> help you, and process a refund if you ask. We never ask for your bank password or a one-time code. We keep your information only as long as we need it
> (we propose up to 24 months for purchase records; receipt images are deleted sooner). Your messages and receipts are in Telegram and your payment is in your
> bank/Telebirr, which have their own rules. You can ask us to show, correct or delete your information by messaging us on Telegram."

**How to ask for help or deletion**
> "Message @ParentWiseEthiopia with your name and phone number and say what you need: a copy of your details, a correction, or deletion. We will confirm who you are
> (by replying from the same number/account), reply within *[X working days — to be set]*, and tell you what we delete and what we must keep, and for how long."

**Refunds (summary; the full conditions are already on the refund page)**
> "The 30-day practice guarantee: follow the conditions on the refund page, request a refund between day 31 and day 37, and send your practice notes. We review within
> 3 working days and, if approved, refund within 5 working days to the account you paid from."
> *(these numbers are already published on the refund page; the operator must be able to keep them — see "Checks" below)*

**Support**
> "Message @ParentWiseEthiopia on Telegram. Support hours: *[e.g. Monday–Saturday 09:00–18:00, Addis time — to be set]*. We aim to reply within *[time from the rehearsal]*.
> After you pay, we check the payment ourselves, then send the five PDFs in the same chat within *[time from the rehearsal]* during support hours."

## 5. Customer requests (process the operator follows)
1. Verify the requester by the same Telegram account/phone number used to order.
2. **Show/correct:** read out the log row and any notes; correct errors.
3. **Delete:** delete the log row's personal fields (keep an anonymous count if useful), delete receipt screenshots and the chat if the customer asks, and
   keep only what the law or an open refund requires ⚖. Tell the customer what was kept and until when.
4. Record the request and date in a private "requests" note (no sensitive detail).

## 6. Gaps found in the published policy pages (for the lawyer and you) ⚖
1. **Delivery time:** the payment/delivery and terms pages say the delivery time "will be stated on the checkout page"; the checkout does say delivery is **immediately after payment verification**, but gives no verification window. Add one, set from the test order (see POLICY-APPROVAL-NEEDED.md, item 2).
2. **"One-time payment" wording:** the payment/delivery page and the terms page say "ይህ የአንድ ጊዜ ክፍያ" (this is a one-time payment); your brand rule avoids that phrase. Reword (e.g. "ወርሃዊ ክፍያ የለም").
3. **Privacy page, third parties:** mentions payment-service providers and IP address collection; the manual flow uses neither as a provider you control. Make it match reality (Telegram, Telebirr/CBE, the website host).
4. **Privacy page, retention and rights:** the right to ask for access, correction and deletion **is** stated (section 8), but without how or how fast, and retention is only "as long as needed" with no periods (POLICY-APPROVAL-NEEDED.md, items 6 and 7).
5. **Overseas processing:** the privacy page says some providers may host data outside Ethiopia; keep, but have the lawyer confirm the required wording ⚖.
6. **Refund page promises:** review within 3 working days and refund within 5 working days. These are commitments you must be able to keep while operating alone.
7. **Delivery promise "immediately"** on the page: replace with the measured promise.
8. **Practice-log evidence:** the refund conditions require daily practice notes; decide how customers send them (Telegram) and how long you keep them (data about a child's behaviour: keep minimal) ⚖.
9. **Translations:** all customer-facing legal text must be reviewed in Amharic by a native speaker and the lawyer.

## 7. Decisions you must make (nothing is approved until you decide)
1. Retention periods (section 2) after the lawyer confirms legal minimums.
2. The privacy summary and the deletion/help process (sections 4 and 5).
3. Refund terms, including whether the 3-/5-working-day promises are realistic for one operator.
4. Support hours and the reply time (set from the rehearsal measurements).
5. The delivery promise (set from the rehearsal measurements).
6. Who is the named technical recovery owner, and who may see the order log.
7. Whether payments from someone other than the customer are accepted.
8. How the account holder shown on the checkout is explained to customers.
