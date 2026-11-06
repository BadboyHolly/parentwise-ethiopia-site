# ParentWise Ethiopia — production readiness plan (founder is sole operator, non-developer)

Status date: 2026-11-06. Everything below is a **recommendation for the founder to approve**. Nothing here has been
approved, deployed or switched on. Figures marked *(assumption)* are estimates, not facts. Prices were looked up on
2026-11-06 from public pages and must be re-checked before buying anything.

## 0. Recommendation in one paragraph
**Launch with the manual process now. Build and switch on the custom system afterwards, in stages.** The manual
checkout is live, costs nothing extra, and carries the least new risk. The custom system is real and mostly built, but it
has not run on a real production database with current code, has no production server, and has unapproved policies.
Finishing it first would delay launch by weeks, add a recurring cost and a maintenance job, and protect against a
problem (many orders to handle by hand) that you do not have yet.

## 1. What is proven, and what is not
**Real-database test (run 2026-11-06 in GitHub Actions on a throwaway PostgreSQL 18; no real or hosted database touched)**
Run: https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/42185081664 (branch `ci/pg-full-validation`, current code).

| Check | Result |
|---|---|
| All 5 migrations (0001–0005) apply in order | **Passed** |
| Full production backend suite: orders, payment state, founder login/authenticator/CSRF/sessions, approve/reject, customer delivery, private storage, analytics | **80 passed, 0 failed, 0 skipped** |
| Roll back migrations 0005→0002 one by one, check orders survive, re-apply | **Passed** |
| Backup (`pg_dump`) restored into a second empty database | **Passed** (14 production tables found) |

**Not proven**
- The **AletCloud test database was not touched** (no credentials were shared and none should be). Its app returned HTTP 503 on 2026-11-06, so its current state is unknown. Its own backup-and-restore still has to be run by you; the drill above proves the *method*, not that platform.
- No real Telebirr/CBE transfer, no real Telegram message, no real private storage bucket (none exists yet), no real production server.
- The dashboard has not been run against a live API.
- Two project release-guard workflows are **red on the live deploy branch**: *checkout gate five-width acceptance* (step "Verify homepage stays at approved Git blob": the homepage was redesigned) and *Verify deployed full website* (step "Validate full content and no real-payment settings": manual mode now shows real recipient details by design). They are out of date with the decisions you made and must be updated or retired, otherwise they will keep failing. Two older QA workflows on `main` (admin security, phase 4) also fail; they concern the old QA site.
- The older database workflows ran only on their own October branches; this run is the first to run everything together on current code.

## 2. Hosting and cost
**What exists today**
| Part | Where | State |
|---|---|---|
| Website (static pages) | Render static site | Live, manual deploy |
| Test order API and test PostgreSQL | AletCloud (Pro) | Test only. `/healthz` and `/readyz` returned HTTP 503 on 2026-11-06. Backup-and-restore never completed. Price and backup features **unknown** (no public pricing page found) — need your invoice/plan page. |
| Private PDF storage | Not created | Code supports Cloudflare R2 |

**Prices found (verify before buying)**
- Render: Starter web service about **$7/month**; paid PostgreSQL from about **$6–7/month** (sources disagree); a Render
  article estimates about **$13/month** for one small always-on service plus one small database, before extra storage and
  bandwidth. Sources: render.com articles and docs (2026).
- Cloudflare R2: **$0.015 per GB-month**, first **10 GB-month free**, no charge for downloads (egress). Five PDFs are
  far below 10 GB, so storage should cost about **$0** *(assumption: total PDF size under a few hundred MB)*.
- AletCloud: **unknown**. Please read the amount and the backup/restore features from your own plan page.

**Recommendation *(assumption-based)*:** do not buy anything yet. When the time comes, put the API and database on **one
provider with managed backups**. Render is the default choice (you already use it, one dashboard, about $13–15/month).
Choose AletCloud instead only if its Pro plan already includes automatic backups **and** a restore has been tested.
Keep the current test environment strictly separate from production.

| Monthly cost | Low | Likely | High |
|---|---|---|---|
| API + database | $13 | $15 | $25 (bigger database / backup add-on) |
| PDF storage (R2) | $0 | $0 | $1 |
| Uptime monitor (free tier) | $0 | $0 | $0–7 |
| **Total** | **about $13** | **about $15** | **about $33** |

## 3. Operations for a sole, non-technical operator
| When | What you do | AI assistant (Codex/Claude) helps | Needs a professional? | Time |
|---|---|---|---|---|
| Every day | Check pending payments in the dashboard and Telegram; approve or reject | — | No | 5–15 min |
| Every week | Open the hosting dashboard: backup shown as "succeeded", no error emails, uptime monitor green | Explains anything unclear | No | 15–20 min |
| Every month | Restore drill: restore last backup into a scratch database and check recent orders appear. Approve and deploy pending security updates | Prepares the update, runs tests, writes the checklist, reads the restore result | Only if the drill fails twice | 1–1.5 h |
| Every quarter | Rehearse the manual fallback and one test order; rotate the founder password and keys | Walks you through, never sees secrets | No | 2 h |
| Once, before real customers | — | Prepares everything | **Yes: a security review of the finished setup and a lawyer's check of privacy/refund wording** (a few hours each) | one-off |
| If something breaks | Switch to the manual fallback (see 5); tell the assistant the symptom | Diagnoses from logs you share (secrets removed), proposes the fix | Data leak, lost data, or repeated failures: yes | varies |

**Monitoring (simple):** a free uptime monitor that checks `/healthz` and `/readyz` every 5 minutes and messages you on
Telegram or email. Hosting alerts for failed deploys. Total setup about 30 minutes.
**Expected workload:** about **2–3 hours/month** when nothing is wrong.

## 4. Privacy and policies (proposals, not decisions)
**What the system would store**
| Data | Stored where | Who can read it | Proposed retention (needs your approval and a local-law check) |
|---|---|---|---|
| Customer name, mobile number, payment method, amount, order code, timestamps | Production PostgreSQL | Founder only (login + authenticator code); hosting staff can technically access the server | Orders and payment records: 24 months, then delete or anonymise *(assumption; accounting rules may require longer)* |
| Payment reference the customer reports | Same database, **encrypted**; a one-way digest is used to catch duplicates | Founder only | Same as the order |
| Settlement evidence you record (digests, encrypted note) | Same database | Founder only | Same as the order |
| Approval decisions, audit log | Same database | Founder only | 24 months |
| Founder login sessions | Same database | System | 8 hours, then expire; clear old rows monthly |
| Anonymous visit counts (hashed tab id, source, device) | Same database | Founder only | 13 months |
| Download links | Same database + private R2 storage | The customer holding a valid link | Link lifetime see 6; records 24 months |
| **Receipts, screenshots, chat messages** | **Telegram** (not our system) | Founder and Telegram | Delete receipts you no longer need after the payment is verified, e.g. after 30 days *(proposal)* |
| Backups | Provider backup storage | Provider/founder | 30 days *(assumption; depends on plan)* |

Not stored by the proposed system: payment-app passwords, card numbers, the receipt image itself, IP addresses (rate
limits use one-way hashes), cookies for visit counting.

**Decisions you must make before any real customer data is stored**
1. Approve the retention periods above, after a local lawyer confirms what Ethiopian law and accounting rules require.
2. Approve a customer-facing privacy notice (what is collected, why, who sees it, how to ask for deletion).
3. Finalise the 30-day guarantee: who qualifies, what proof, refund method, and how many days to refund.
4. Finalise support: channel, hours, and a promise you can keep.
5. Confirm the payment account holder shown to customers and how you explain whose account it is.
6. Decide whether payments from someone other than the customer are accepted (the system has an exception log).

**Draft recommendations (for you to edit)**
- *Refunds:* "If, after following the 30-day plan and keeping your practice log, you see no visible improvement, message
  us on Telegram within 7 days after day 30. We refund the full 1,500 ብር to the same Telebirr/CBE account within 5
  working days after we confirm." *(wording and time limits are placeholders)*
- *Support:* one channel (Telegram), stated hours (e.g. Mon–Sat, 09:00–18:00 Addis time), reply within 24 hours.
- *Delivery promise:* replace "immediately" with a time you can meet, for example "within 2 hours during support hours".

## 5. Fallback (manual checkout stays the launch fallback)
**The manual flow:** customer pays by Telebirr or CBE, sends proof on Telegram, you verify and send the PDFs by hand.
It is already live. A complete real-payment-to-PDF test has **not** been confirmed.

**Proposed design (needs building and testing):**
1. Keep the manual path in the page permanently. If the order API is unreachable or returns an error, the checkout
   falls back to the manual screens automatically, so the customer is never stuck.
2. A single, documented switch (`CHECKOUT_OPEN` / API address in `order.html`) turns the API path off by hand.
3. A written rehearsal: with the API deliberately stopped on a staging copy, run one order through the manual path and
   time it end to end.

I will **not** state how fast the switch is until step 3 has actually been run and timed.

## 6. PDF delivery and support
| | Manual Telegram delivery (now) | Automatic private links (built, not live) |
|---|---|---|
| Build effort | None | Needs production storage, approvals and testing |
| Your time per order | 2–4 min *(assumption)* | About 1 min (approve) |
| Speed | As fast as you reply | Seconds after approval |
| Expired or lost link | Resend the file | Re-issue a link from the dashboard after checking name/phone/order |
| Delivery failure | Resend | Fall back to Telegram |
| Leaked PDF | Cannot revoke what was forwarded | Can revoke the link, but not copies already saved |

**Recommendation for launch:** keep **manual Telegram delivery**, with a simple order log. Add automatic links later,
once there are enough orders for hand-delivery to hurt. **No option can fully prevent leaks.** Reduce the damage with
terms that say the PDFs are for the buyer's family, limited-lifetime links later, and, as a later improvement,
putting the order code in a footer of each customer's copy so a leaked copy can be traced.

## 7. Time, stages and uncertainty
A "working session" below means about 2 hours of work with the assistant, not counting waiting for you.

| Stage | What | Sessions | Notes |
|---|---|---|---|
| **A. Already built and tested** | Order intake, payment-state, founder login/approval, secure PDF delivery, analytics (14 tests on SQLite). Older database tests passed on their own October branches | done | Re-proven on current code in section 1 (80/80 on PostgreSQL) |
| **B. Needs testing or fixing** | Two failing release-guard workflows; AletCloud backup/restore; dashboard against live API | 3–5 | The failing guards must be updated or retired |
| **C. Essential for first (manual) launch** | Real end-to-end test order; Telegram check; order log; reply promise; page fixes (share preview, favicon, alt text, video, "ዋጋ" wording); policy decisions | 3–4 (6–10 h) plus your tasks | Your decisions and one real payment test are the slow parts |
| **D. Essential to go live with the custom system** | Hosting, secrets, staging rehearsal, wire dashboard, fallback rehearsal, security review | 10–16 (20–35 h) | **±50 %**: unknown test failures, AletCloud facts, waiting on approvals |
| **E. Can wait** | Automatic links, revenue per traffic source, scroll analytics, payment gateway, watermarking | later | Only after real orders show the need |

## 8. Decision
| | Finish custom system first | **Launch manual, build after (recommended)** |
|---|---|---|
| Time to launch | Weeks (stage D) | Days (stage C) |
| Extra monthly cost | About $13–33 from day one | $0 until you build |
| Your workload | 2–3 h/month ops, plus setup | Orders by hand, about 5–15 min/day at low volume |
| Main risk | Switching on untested money/data handling; no revenue meanwhile | Slow replies and mistakes if orders grow; no order records beyond Telegram |
| What you gain | Order list, dashboard, tracking from day one | Revenue and real customer feedback sooner; the real shape of the problem before you build |

**Choose: launch manual, then build.** Switch to building sooner if you expect more than about **10 orders per day**, or
if replies to customers regularly take longer than your promise.

## 9. Next concrete steps
1. *(You)* Run one real test order: pay a small amount, send proof, receive the PDFs. Time each step.
2. *(You)* Test that @ParentWiseEthiopia can receive and answer messages from a second account.
3. *(You)* Decide your reply promise and approve or edit the draft refund and support wording in section 4.
4. *(Assistant)* Quick page fixes: share preview and favicon, alt text, "ዋጋ" wording, hero video decision, and remove the search block at launch.
5. *(Assistant)* Update or retire the two failing release-guard workflows so the project's own checks match the manual launch.
6. *(You)* Open your AletCloud plan page and send the monthly price and whether backups are included (no passwords).
7. *(Assistant)* Build the automatic fallback in the checkout and write the rehearsal script (stage D, begins after launch).
8. After about 20–30 real orders, review volume and decide whether to start stage D.

## 10. Questions that would change this decision
1. What does your AletCloud Pro plan cost, and does it include backups? (If it is cheap and backed up, hosting there is viable.)
2. How many orders per day do you expect in the first month? (Above about 10 per day, build sooner.)
3. Can you reliably answer Telegram within your promised time? (If not, the automatic path matters more.)
