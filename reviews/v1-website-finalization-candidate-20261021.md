# ParentWise Ethiopia — V1 Website Finalization Candidate

**Status:** Technical synthetic acceptance PASSED; **PUBLIC SALES BLOCKED**.
**Date:** 21 October 2026. This branch is for review only.

## Frozen approved customer journey
Meta ad → approved V4 sales page → name and Ethiopian phone → Telebirr/CBE → saved pending order → fictional payment instruction display → “I've Paid” Telegram message preparation → founder manual verification → manual five-PDF delivery. Production flow remains disabled.

## Completed in this branch
1. Combined exact reviewed sales copy from PR #13 with approved V1 static checkout preview; no approved CSS changes.
2. Synchronized root and `public/index.html` to eliminate outdated duplicate copy.
3. Preserved an isolated synthetic checkout at `v1_checkout/ci-only-order.html` with canonical 43-character secure idempotency keys and server-priced ETB 1,500 pending orders.
4. CI-only localhost routes test a single real browser journey from the *reviewed sales CTA* into the synthetic pending-order endpoint and the Telegram handoff, without shipping that test routing to public hosting.
5. Added two independent CI browser suites covering static-only source and database-backed synthetic orders at 320, 360, 390, 768 and 1280 px.

## Acceptance evidence
**PASS:** https://github.com/BadboyHolly/parentwise-ethiopia-site/actions/runs/39602154027
- Static copy and checkout workflow PASS at all five widths, no write requests and no real recipients.
- Synthetic pending order / idempotent retry PASS at all five widths.
- Full sales-page CTA → pending-order API → Telegram message preparation PASS at 390 px.
- Forced API / storage outage correctly blocks payment screen.
- QA accounts only; no real transfers, verification, Telegram send, or file delivery.

## Explicit launch gates not met
- Founder signoff on new Amharic customer copy, final guarantee/refund wording, support/delivery SLA and non-Telegram alternative.
- Real private Telegram DM tested (link syntax checks do not prove DM works).
- Verified recipient ownership within Telebirr/CBE; privately configure actual account values in future production service (never in this repo).
- Production-only order intake on isolated PostgreSQL with migration, secrets, backup/restore and proper rate/abuse controls; prevent lost order after switching apps.
- Founder-only MFA-backed manual settlement match, duplicate-reference prevention, audit trail, third-party payer handling.
- Final approved five-file manual fulfillment rehearsal (outside this website task).
- Remove unauthenticated endorsements/portraits or publish independently verified endorsements with consent.
- Rehearse end-to-end customer recovery and alternative delivery.
- Founder explicitly authorizes release only when these gates pass.

## Branch protection and intent
Do **NOT** merge directly into main: main currently serves an independent QA checkout; this branch integrates a release candidate and must preserve that QA environment. Do not deploy or activate real payments. All testing is fictional; the CI server is hard-gated and must never be deployed.

## Owner and review
Founder: validate Telegram DM, refund/support decisions and endorsement release decisions.
Developer: finish secure production-equivalent integration and acceptance.
Review trigger: founder-approved customer journey and production security acceptance.
