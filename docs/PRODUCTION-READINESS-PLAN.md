# ParentWise Ethiopia — readiness plan (revision 2, 2026-11-06)

Supersedes the first version. Companion documents:
- `docs/MANUAL-OPERATIONS-CHECKLIST.md` — who does what, daily/weekly/monthly checklists, incident first steps, order log, support scripts, rehearsal sheet, fallback.
- `docs/CUSTOMER-DATA-AND-POLICY-DRAFTS.md` — data inventory and **draft** privacy, refund and support text for your review.

**Nothing in these documents is an approved decision.** Retention periods, refund terms, reply times and policy wording are
proposals. Items marked ⚖ need Ethiopian legal review. Figures marked *(estimate)* are to be replaced by measured numbers.
No credential appears here, and none should ever be pasted into chat.

## 0. Decision
1. **Launch with the manual Telegram process.** Prove one complete controlled order *before spending on ads*.
2. **Test the Founder dashboard separately** in its own repository and test database. Public order intake and payment
   processing stay **off**. The dashboard becomes useful for recording Telegram sales only after its own database,
   backup/restore, migration, login and approval tests pass.
3. Build automation only when measured handling time, errors, conversion and support load justify it.

## 1. What is proven — and where (two different repositories)

| | Website repository (`BadboyHolly/parentwise-ethiopia-site`) | AletCloud backend repository (`ParentwiseEthiopia/parentwise-aletcloud-deploy`, private) |
|---|---|---|
| Role | Sales pages and checkout (manual) + an older **divergent copy** of the order backend | The backend actually built for AletCloud (Dockerfile, startup, migration runner, Founder admin UI) |
| What was tested | 80/80 backend tests on a disposable PostgreSQL 18, migrations 0001–0005, rollback of 0002–0005 and re-apply, `pg_dump`/restore drill. Tested commit `07ec550` (run: <https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/42185081664>) | **Nothing tested by me.** Not fetchable from this computer (see below) |
| What that proves | Only that **the website repository's copy** works on PostgreSQL | — |
| What it does *not* prove | Anything about the AletCloud backend, the Founder dashboard candidate, migration 0008 or the AletCloud database | — |

**The two backends have drifted apart** (checked by comparing the folders): the AletCloud copy has `manual_fulfillment.py`,
`migrate.py`, `startup*.py`, the Founder admin UI and a different migration `0004_manual_telegram_fulfillment`; the website
copy has `customer_delivery.py`, `analytics.py` and migrations `0004_create_customer_rate_limits` and `0005_create_analytics_events`.
Even same-named files (`app.py`, `founder_security.py`, `payment_state.py`, migration `0003`) differ. **Consequence:**
the visit-analytics code I wrote lives only in the website copy. It must not be merged into the AletCloud backend as-is
(migration numbers collide and the code is built on a different base). If analytics is wanted later it must be re-based
on the backend, with new migration numbers, and re-tested there. Treat the website copy as a reference, not the release.

**The dashboard candidate (`codex/founder-dashboard-test-20261105`, migration 0008) — status: not identified, not tested.**
- It is not on this computer. The local clones are at `main` (`41e5c0b`, 4 Nov; a second copy on the Desktop is older, `3f9b59b`),
  neither containing that branch or a migration 0008 (the newest local backend migration is 0004).
- `git fetch` on the backend repository fails with "Repository not found": the GitHub login saved on this computer cannot
  see that private repository (it is under the account `ParentwiseEthiopia`; this computer is signed in as a different account).
- So **the exact release commit cannot be named yet, and no tests have been run on it.** No skips or failures to report because
  nothing ran.

**To test the candidate properly (what is needed, and the order):**
1. You give me the exact commit SHA (from GitHub → the branch → latest commit) and make the code reachable here: either run
   `git fetch origin codex/founder-dashboard-test-20261105` in `Documents\parentwise-aletcloud-deploy` after signing in to the
   correct GitHub account, or copy the branch's folder to this computer. (No password or token is ever shared with me.)
2. Run the **complete applicable suite** on a **disposable** PostgreSQL (not the AletCloud database): all migrations 0001→0008 in
   order, every test file in `production_checkout/tests` (orders, payment state, founder security, private storage, startup,
   AletCloud runtime, migration runner, Founder admin browser test), rollback of each migration where a rollback exists,
   and a dump-and-restore drill. Report every skip and failure by name. Fix confirmed failures before calling it ready.
3. Where: preferably in the backend repository's own GitHub Actions (service container PostgreSQL, as the website repo does)
   or a throw-away local PostgreSQL. This computer has neither PostgreSQL nor Docker, and a Python-embedded PostgreSQL
   package is unavailable for this Python version; installing a portable PostgreSQL would be a ~300 MB download and is
   **not done without your OK**.

**AletCloud database `parentwise-console-test-pro` — status:** stopped; identity confirmed through the test app; the
empty-database check was inconclusive (it counted the default `public` schema); **no migrations applied; no backup or restore
test done.** The test app at `parentwise-isolated-test.app.aletcloud.com` returned HTTP 503 on 2026-11-06.
The restore test on AletCloud itself is a separate, still-open task (steps in the operations checklist, section 8).
The website-repo drill proves a *method*, not the AletCloud platform.

**A credential for the test database appeared in captured output.** Decision so far: continue isolated testing, rotate later.
**Rotate it before any real customer data or production use** (and treat that database as test-only until then). The credential
is not reproduced in any of these documents.

## 2. Hosting and cost
**AletCloud published prices (provided by you; planning estimate, not confirmation that these sizes suffice):**

| Item | Per month |
|---|---|
| Pro database (backups included) | 150 ETB |
| Pro app plan | 360 ETB |
| **Always-on app + database** | **510 ETB before VAT** |
| If wallet top-ups carry 15 % VAT | about 586 ETB (510 × 1.15) *(estimate)* |
| Private PDF storage (only needed for automatic links, not for manual delivery) | not needed at launch |

Other facts for comparison: Render about US$13–15/month for a small always-on service plus a small database (published pages,
sources disagree on the database price; no exchange rate was verified, so no conversion is shown); Cloudflare R2 storage is
US$0.015/GB-month with 10 GB free and no download charge, i.e. about nothing for five PDFs.

**Operational needs that decide the host (check against the plan sizes before paying):** always-on (no sleeping), database
size for years of orders (small), automatic backups with a **tested** restore, ability to run the container and the migration
runner, logs, an alert when the app is down, and a person who can recover it. **Recommendation:** the backend repository is
already built for AletCloud (Dockerfile, startup diagnostics, migration runner), so **AletCloud is the natural production host
if the dashboard test and the backup/restore test pass and its sizes suffice.** If they do not, re-evaluate before spending.
**To start manual sales we need no new infrastructure: extra monthly cost = 0.**

## 3. Operations and ownership
Two separate jobs; do not mix their time estimates.

| Job | Who | Estimate *(until real orders are timed)* |
|---|---|---|
| **A. Daily business work:** verify payments in Telebirr/CBE records, reply on Telegram, deliver PDFs, update the order log, answer support | You (initial operator) | Payment checks alone: 5–15 min/day = **2.5–7.5 h per 30-day month**, before conversations, deliveries and problems |
| **B. Technical work:** backups, restore tests, updates, monitoring, incident response | Assistant prepares and explains; **a named technical contact recovers** | About 2–3 h/month when nothing is wrong |

**Technical recovery owner:** *not yet assigned.* Appoint one named person (a freelance developer or technical friend) before
the backend stores real data. **Do not assume you can handle a security incident alone.** The assistant can diagnose from logs
you share (secrets removed) and prepare fixes, but cannot access your accounts or rotate your secrets. Incident first steps and
who to call are in the checklist. Professional help is needed for: a data leak or suspected breach, lost or corrupted data,
a failed restore, and the legal questions marked ⚖.

## 4. Privacy, support and refunds
Drafts, a data inventory (backend vs Telegram vs payment apps), retention proposals, access, and the customer help/deletion
process are in `docs/CUSTOMER-DATA-AND-POLICY-DRAFTS.md`. The manual process already handles customer data today (names, phone
numbers, receipts in Telegram; payment records in your banking apps), so those decisions matter now, not only after the backend.

## 5. Fallback
Today's sales path **is** the manual Telegram flow; there is nothing to fall back *to* yet. If a backend checkout is introduced
later, return to the manual flow by redeploying the tagged manual page (method and rehearsal in the checklist, section 7).
**No automatic fallback and no recovery time is promised** until it is implemented and rehearsed.

**The two red release checks — investigated and updated (branch `ci/release-checks`):**
- *Checkout gate:* it pinned the homepage to one exact file fingerprint (obsolete after the redesign) and expected the old
  walkthrough. **Replaced** by `qa-tests/verify_static_release.py` and a new browser test of the live manual flow
  (`qa-tests/manual_checkout_acceptance.py`, five widths). **Kept** the meaningful rules: order system closed, **no backend
  address in the page**, no external scripts or form posts, only the approved price and **only the two approved recipient
  numbers** (any change fails on purpose), forbidden wording absent, order-submission gate present. The old API-flow test is kept
  in the repository for a future backend checkout.
- *Verify deployed site:* it expected a 2 MB homepage and old review-mode texts and treated any real payment number as an
  error. It now runs the same shared script against the deployed pages.
- The check found one genuine issue: the checkout page contained the AletCloud **test address** (harmless while closed, but an
  unnecessary exposure). It was removed (`ORDER_API_ORIGIN = ''`); this changes nothing for customers.
- Self-test: 11 deliberately broken copies (checkout opened, extra/swapped recipient, external script, second price, "subscription",
  form post, removed gate, opened robots…) were **all caught**. Preview-only rules (noindex, robots `Disallow`) are marked "remove at launch".

## 6. PDF delivery
**First sales: manual Telegram delivery plus a simple, access-controlled order log.** Handling of lost files, files that will
not open, and support requests is in the checklist (section 6). Automatic links are added **only when** measured volume,
handling time, error rate and support load justify them. No option can fully prevent leaks.

## 7. Timeline and launch criteria *(rough estimates, not commitments)*
**Next immediate milestone — one complete, controlled purchase rehearsal:** a second Telegram account reaches
@ParentWiseEthiopia, a small payment is **independently verified** in the banking record, the **correct five PDFs** are delivered
in the same chat, and the transaction is **recorded** in the log. Time each step (rehearsal sheet in the checklist) and use the
result to set the support promise.

**Manual launch criteria (all required before spending on ads):**
1. Rehearsal passed and timed; the five PDFs open on Android and iPhone.
2. Telegram can receive from a stranger's account and you can reply.
3. Order log exists, access-controlled, and one test row recorded.
4. Interim privacy notice and refund/support wording **approved by you** (⚖ legal review of the wording; use plain interim text until then).
5. Reply promise set from measured times, not guessed.
6. Page fixes done: share preview and favicon, alt text, "ዋጋ" wording, hero video decision; preview-only search block removed *at launch*.
7. Release checks green on the deploy branch.

**Dashboard-use criteria (separate; all required before it holds real customer data):** exact commit identified and its complete
suite passes on disposable PostgreSQL with skips explained; AletCloud backup **and restore** test passed; migrations 0001→0008
applied on a clean database and rolled back where possible; login with authenticator code and approval flow tested; test
credential **rotated**; policies approved; a technical recovery owner named; public order intake and payments still off.

| Piece | Rough effort *(estimate)* |
|---|---|
| Already built and tested (website repo copy only) | done |
| Identify and test dashboard candidate; AletCloud restore test | 2–4 sessions after access is sorted |
| Manual launch essentials (rehearsal, log, wording, page fixes) | 3–4 sessions plus your decisions |
| Backend checkout live (hosting, secrets, staging rehearsal, security review, fallback rehearsal) | 10–16 sessions, ±50 % |
| Can wait | automatic links, revenue per traffic source, scroll analytics, gateways, watermarking |

The "about 10 orders per day" figure is a **question to investigate, not a proven threshold.** Decide on automation from
measured minutes per order, errors, conversion and support load.

## 8. Recommended choice
**Manual launch first, dashboard tested separately, automation later.** Time to first sale: days. Extra monthly cost: 0.
Your workload: real daily work (section 3A). Main risks: slow replies, human error in matching payments, thin records beyond
Telegram and the log. What you gain: revenue and real customer evidence before spending on infrastructure.

## 9. Exact next actions
**Manual launch**
1. *(You)* Do the controlled rehearsal (checklist, section 5) and send me the timings.
2. *(You)* Confirm @ParentWiseEthiopia receives and answers from a second account.
3. *(You)* Review the policy drafts; send them to a lawyer (⚖); approve interim wording and the reply promise.
4. *(Assistant)* Quick page fixes, once you say go.
5. *(You)* Deploy the website on Render when ready; after the next deploy the live-site check should be green.
6. Do **not** spend on ads until steps 1–3 are done.

**Dashboard test (separate; no public intake, no payments)**
1. *(You)* Give me the exact commit SHA and make the branch reachable here (or tell me to proceed another way).
2. *(You)* Decide whether I may download a portable PostgreSQL (~300 MB) for local runs, or whether the test runs in the backend repo's GitHub Actions.
3. *(Assistant)* Run the complete applicable suite on a disposable PostgreSQL; report passes, skips, failures; fix confirmed failures.
4. *(You, with the assistant's checklist)* AletCloud backup-and-restore test on a **fresh** empty database; then rotate the test credential.
5. *(You)* Name the technical recovery owner.
6. Only then: decide whether the dashboard records real Telegram orders.

## 10. Questions that would change this
1. Can you make the dashboard branch reachable here (exact SHA, correct GitHub login), and is a portable PostgreSQL download acceptable?
2. Who will be the named technical recovery contact?
3. What reply time can you keep during the rehearsal? (Set the promise from the measured result.)
