# ParentWise Ethiopia — manual launch operating checklist (draft for the founder)

Status: DRAFT, 2026-11-06. Times are estimates until real orders are timed. No secret, password, token or database
credential belongs in this file, in chat, in the order log, or in Telegram.

## 1. Roles
| Role | Who | Does |
|---|---|---|
| **Business operator** | You (initially) | Payments, Telegram replies, PDF delivery, order log, refunds, customer support |
| **Technical recovery owner** | **NOT YET ASSIGNED — appoint a named person before any backend stores real data** | Backups, restore tests, updates, security incidents, rotating secrets |
| **Assistant (Codex/Claude)** | — | Prepares fixes, tests, checklists and explanations from logs you share (secrets removed). Cannot sign in to your accounts or rotate secrets |
| **Lawyer** | To be engaged | Reviews the items marked ⚖ in the policy drafts |

You should not be the only person able to recover the system, and you should not handle a security incident alone.

## 2. Daily business checklist (manual launch)
Estimate: payment checks 5–15 min/day (2.5–7.5 h per 30-day month) **plus** conversations, deliveries and problems *(estimate)*.
1. Open Telegram. Reply to every new message. Note the time of the first message and your reply (for the promise you will publish).
2. For each person who says they paid: open your **Telebirr / CBE record** yourself and confirm the **amount (1,500 ብር), date/time and the payer** match.
   Never rely on a screenshot alone.
3. If it matches: send the **five PDFs** in the same chat; check the reply shows they received them; **write the order log row** (section 4).
4. If it does not match or cannot be found: do not send the files; reply politely, ask for the transaction number, record "pending" in the log.
5. Check the log for anything "pending" older than 24 hours and follow up.
6. Refund requests (policy: request days 31–37; review within 3 working days; refund within 5 working days): log them with dates and decide against the written refund conditions.

## 3. Technical checklist (starts when a backend/dashboard holds real data)
| When | Task | Owner | Time *(estimate)* |
|---|---|---|---|
| Weekly | Hosting dashboard: backup shows "succeeded"; no error emails; uptime monitor green | Operator | 15–20 min |
| Monthly | **Restore drill**: restore the newest backup into a *separate scratch database*, check recent orders appear, then delete the scratch copy | Technical owner (assistant prepares) | 1–1.5 h |
| Monthly | Apply security updates; run the tests; deploy only after tests pass | Technical owner | 1 h |
| Quarterly | Rotate founder password and keys; re-run the manual-fallback rehearsal | Technical owner + operator | 2 h |
| Before any real data | Rotate the AletCloud **test** database credential (it appeared in captured output) | Technical owner | 15 min |

## 4. Order log (simple, access-controlled)
**Where:** one spreadsheet or table with sharing set to "only me" (and the technical owner if needed), two-step sign-in on the account,
no public link. **Do not store** receipt images, passwords, card numbers or full bank statements in it. Back it up monthly to a second private place.

| Column | Example / rule |
|---|---|
| Order no. | Simple running number you assign (`M-0001`) |
| Date/time first message | when they wrote |
| Name | as given |
| Phone | as given |
| Method | Telebirr / CBE |
| Amount | 1,500 |
| Payment checked? | yes/no + **date/time you checked** + your initials |
| Bank/Telebirr transaction ref | the reference from *your own* record |
| Files sent? | yes + date/time + which chat |
| Status | pending / delivered / refund requested / refunded |
| Support notes | short, no medical or child details |
| Delete-by date | per the approved retention period |

## 5. Controlled purchase rehearsal (the next milestone)
Use a **second Telegram account** and a **small real payment you control**. Fill in the times; use the result to set the support promise.

| Step | What to do | Minutes (fill in) | OK? |
|---|---|---|---|
| 1 | Open the live site on a phone; read to the order page; start checkout at 320–390 px | | |
| 2 | Enter name/phone, choose Telebirr (then repeat once with CBE), reach the Telegram screen | | |
| 3 | From the second account message @ParentWiseEthiopia as the screen instructs; note whether the message arrives and when | | |
| 4 | Pay the amount (or a small test amount) from the second person's account | | |
| 5 | **You** confirm the payment in *your own* record (not from the screenshot) | | |
| 6 | Send the five PDFs in the same chat | | |
| 7 | The second person opens **each PDF on Android and on iPhone**; the **correct five files** open and are readable | | |
| 8 | Write the log row | | |
| 9 | Total time first message → files received | | |

Record failures (message not delivered, file will not open, wrong file, confusing screen). **Set the support promise from step 9**, with
a margin, not from a guess. Do not publish "immediately" unless it was measured.

## 6. Support scripts (plain wording; adapt to your voice)
- **Lost a file:** confirm the name/phone against the log; resend the five files in the same chat; record it. If they ask repeatedly or the chat is new, ask for the transaction reference first.
- **File will not open:** ask the phone type; ask them to open with a PDF viewer; resend; if still failing, send a download via another method **or** a different file size; record it.
- **Wrong or missing file:** check the log; resend the correct set; apologise once; record it.
- **Paid but no files:** ask for transaction reference and time; check your record; if found, deliver and log; if not found, say what you checked and ask for the bank/Telebirr confirmation.
- **Refund request:** check the written conditions; reply within the published review time; log dates; refund to the **same account** that paid.
- **Customer asks to see/correct/delete their data:** see `docs/CUSTOMER-DATA-AND-POLICY-DRAFTS.md` section 5.
- **A PDF appears shared publicly:** note where; do not accuse; ask the sharer to remove it; consult the technical owner and lawyer before acting.

## 7. Fallback (if a backend checkout is introduced later)
Today the manual Telegram flow is the live sales path. **No automatic fallback and no recovery time is promised** until implemented and rehearsed.
Proposed method (to be rehearsed, then timed):
1. **Before** any backend checkout goes live, create a git tag on the exact manual-site commit (for example `manual-launch-baseline`) so the known-good page is one named version.
2. To go back: in the website repository check out that tag's content into the deploy branch, push it, then click **Manual Deploy** on Render, then run the live-site check.
3. In the same moment, stop sending customers to any backend flow (page change) and keep delivering manually.
4. Rehearse once with the backend stopped; **write down the real time it took**; only then publish a recovery time internally.
Keep the manual process documented and practised so it never depends on the backend.

## 8. AletCloud test database: backup and restore test (separate task)
Goal: prove the **platform's** backup and restore, not just our method. Use a **fresh, empty** database (not the test one that holds a leaked credential).
1. In the AletCloud dashboard, note the plan, backup schedule and retention (written down, with date).
2. Create a new empty database; confirm it is empty by counting tables *outside* the `public` system schema (the earlier check was inconclusive because it counted `public`).
3. Apply migrations 0001 → latest using the repository's migration runner; record the output.
4. Insert clearly fake rows (names like `TEST-ONLY`).
5. Trigger a backup (or wait for the scheduled one); restore it **into a second new database**; check the fake rows are there.
6. Delete both databases. Record the date, the steps, the times and any problem.
7. Only after this passes may that platform be considered for real data.
Do **not** paste connection strings or passwords into chat; the technical owner or the assistant works from output you have cleaned.

## 9. If you suspect a security problem (first steps)
1. **Stay calm; do not delete anything** (logs and messages are evidence).
2. Write down what you saw, when, and what you clicked or shared.
3. **Stop** the affected thing: if a backend checkout exists, take it down by switching to the manual page (section 7); change the password of the affected account from a clean device.
4. Contact the **technical recovery owner** immediately. Contact the hosting provider's support. **Do not send secrets to anyone by chat or email.**
5. Rotate the exposed credential only with the technical owner's guidance.
6. If customer data may have been exposed: **talk to the lawyer before deciding what to tell customers** ⚖.
7. Afterwards: write a short note of what happened and what changed.
