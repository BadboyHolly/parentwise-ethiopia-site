# Visit analytics (anonymous, first-party)

Counts anonymous browser sessions on the sales page and checkout so the founder dashboard can show
where visitors come from and where they stop. **Off by default. Nothing is collected until every step below is done.**

## What is and is not stored
Stored per event: an HMAC of a random per-tab id, one of five fixed event names
(`sales_view`, `checkout_view`, `payment_view`, `proof_view`, `telegram_open`), a lowercase source label
(e.g. `facebook`), an optional campaign label, a coarse device class and a coarse in-app-browser class, and a timestamp.

Never stored or sent: IP address, user agent, cookies, names, phone numbers, order codes, payment references.
The browser respects Do Not Track and Global Privacy Control. Counts are sessions, not people.

## Turning it on (all steps are yours to do; no secret goes in chat, GitHub or email)
1. Apply `migrations/0005_create_analytics_events.sql` to the production database (rollback: `0005_rollback_analytics_events.sql`).
2. On the API service set `ANALYTICS_ENABLED=true` and a private random `ANALYTICS_HASH_KEY` (32+ characters).
   Optional: `ANALYTICS_MAX_PER_MINUTE` (default 300, clamped 30 to 3000).
3. Make sure the sales site's address is in `ALLOWED_ORIGINS` (HTTPS only; already required).
4. In `site-preview/index.html` and `site-preview/order.html`, add to `<head>`:
   `<meta name="pw-events-endpoint" content="https://YOUR-API-HOST/api/v1/events">`
   Without this tag the tracker does nothing.
5. Read-only report for the dashboard: `GET /api/v1/founder/report?days=30` (requires the founder session).

## Known limits
- Orders and verified revenue are not yet attributed per source; the report returns sessions only for sources.
- The founder dashboard preview still shows sample data (`LIVE=false`); wiring it to this report is a separate step.
- Ad blockers and cross-device visits are not recoverable. A tab that is closed starts a new session.
