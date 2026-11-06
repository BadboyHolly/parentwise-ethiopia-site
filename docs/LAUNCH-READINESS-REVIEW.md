# Manual-launch readiness review — what would change on the live site (branch `launch/manual-sale-ready`)

Scope: the website only. The AletCloud backend and the Founder dashboard repository are **not** touched. Public backend order
intake and automatic payment processing stay **off**; the manual Telebirr/CBE + Telegram flow is unchanged.
**Nothing here is merged or deployed.** Prepared 2026-11-06 for your review.

## 1. What is live now, and what would change
Live deploy branch `deploy/parentwise-full-site-preview-20261021` is at `4a6adb5` (the version you deployed on Render).
This branch is built on top of the current working branch. Everything that would change **on the site (files under `site-preview/`)**:

| File | Change | Why |
|---|---|---|
| `index.html` | Added page description, share-card tags (Telegram/Facebook preview) and favicon tags. **Favicon = your colour family mark (green and red) on white.** **Share image = the footer family picture with your logo**; new title and description: «ልጅዎ «እምቢ» ሲል ምን ማድረግ እንዳለብዎት ይወቁ — ParentWise Ethiopia» / «ሳይጮኹና ሳይቆጡ በቤትዎ የሚደጋገሙ ጭቅጭቆችን ለመቀነስ የሚረዳ ግልጽ መመሪያ። የንግግር ምሳሌዎች፣ የተግባር ቅጾችና የ30 ቀን እቅድ — አምስት PDF መመሪያዎች በ1,500 ብር።» | Links shared in Telegram/Facebook currently show as a bare address; browsers show no icon |
| `index.html` | Price label «አንድ ጊዜ የሚከፈል ዋጋ» → «ዋጋ» | Removes the "one-time" wording you avoid |
| `index.html` | Telebirr and CBE logos in the payment-options card now load from **local copies**; they used to load from `ethiotelecom.et`, GitHub's raw file server and Wikimedia | A third-party host being slow or blocked would break the logos at the moment of payment, and those hosts saw each visitor's address. Same look, plus the names "telebirr" and "CBE" under the logos |
| `order.html` | The AletCloud **test address** removed from the page (`ORDER_API_ORIGIN = ''`); favicon/theme-colour tags | The test address was an unnecessary exposure while checkout is closed |
| `order.html` (Telegram screen) | One added line: «በማንኛውም ሰዓት ይላኩ — ማስረጃው እንደደረሰን በ10 ደቂቃ ውስጥ ለማረጋገጥ እንሠራለን።» | Your decision: payment proof can be sent at any time; target 10 minutes. **Needs native-speaker review before deploy** |
| `policies/payment-delivery.html` §4, `policies/terms.html` §5 | Delivery-time sentences replaced with the any-time / 10-minute / immediately-after-verification wording (see `POLICY-APPROVAL-NEEDED.md` item 2). The other three policy pages: favicon tags only | The old text said the time "will be stated on the checkout page" and "may vary". **Needs native-speaker/⚖ review before deploy** |
| New files | `favicon.ico`, `assets/icons/*` (favicons), `assets/og/parentwise-share.jpg` (share image) | Built from your own logo and method illustration |
| **Removed** | `pay-options.html` | A public test page with a fake account number and name ("Sample Holder Name") |
| **Moved out of the site** | `founder/` and `founder-preview/` → `design-previews/` (still in the repository, no longer published) | Customers should not be able to reach an internal dashboard design (even with sample data); the real dashboard is built separately. Nothing linked to them |

**Not changed (on purpose):** the hero video placeholder («በቅርቡ», as you asked), `noindex` and `robots.txt` (the site stays hidden from
search until you decide), all policy wording, the payment flow and recipients, the dormant visit tracker.
Files outside `site-preview/` (tests, workflows, documents) do not affect the live site.

## 2. Checks run
| Check | Result |
|---|---|
| Static release safety checks (order system closed; **no backend address**; approved recipients and price only; no external scripts, **images** or form posts; submission gate present; "subscription" absent) | **Pass** on the real pages; self-tested against 12 deliberately broken copies (all caught) |
| Manual checkout in a browser at **320 px** (Telebirr and CBE): approved recipient shown, 1,500 ብር, "Edit" button, pay button in view, back navigation, Telegram link prefilled, no horizontal scroll, nothing stored | **Pass** |
| Sales page at 375 px: share/favicon tags present, hero and video placeholder intact, payment-logo cards, no horizontal scroll | **Pass** |
| Automated browser test of the manual checkout at 320/360/390/768/1280 px, both methods (GitHub) | **Pass** (run <https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/42199880960>, commit `4023e4d`; the backend manual-journey regression job also passed) |

Not tested: a real payment, real Telegram delivery, the share preview inside Telegram/Facebook (needs the deployed address), iPhone Safari.

## 3. Things to know before selling
1. **Share image address:** the share tags point to the current Render preview address. When you move to the final domain, update those two lines.
2. **Search visibility:** the site is still marked `noindex`. That is right while you test; remove it (and `Disallow: /` in `robots.txt`, and the matching "preview" lines in the check) only when you want Google to find the site.
3. **Founder preview pages** were moved out of the published folder (see the table); they remain in `design-previews/` for reference.
4. **The five PDFs** still need your confirmation (see `CONTROLLED-TEST-ORDER.md`): newest files carry `DRAFT`/`HOLD`/`TRIAL` in their names.
5. **Policy wording** needing your approval is in `POLICY-APPROVAL-NEEDED.md`. Nothing was edited.

## 4. To go live (you, after reviewing)
1. Say "merge": I merge this branch into the deploy branch and push.
2. You click **Manual Deploy → Deploy latest commit** on Render (<https://dashboard.render.com/static/srv-dbcbiemq1p3s73ctil80>).
3. I run the live-site check (it should now pass, including the "deployed site" workflow) and look at the live pages on a phone width.
4. Then run the controlled test order (`CONTROLLED-TEST-ORDER.md`).
