# Adding the visit counter and the "how did you hear" question to the LIVE static site

The live site (`parentwiseethiopia.com`, repo `ParentwiseEthiopia/parentwise-site`, branch `main`) is on a different history from the branch this kit came from (`claude/clean-analytics-20261109`). Do not merge or cherry-pick that branch. Copy three small things instead. Nothing here has been applied to the live repo.

## What is in this folder
- `pw-track.js`: the finished visit counter, one file. It does nothing at all until the page carries the endpoint tag (step 2).
- `order-heard-question.patch`: the six small changes to `order.html` that add the required "ParentWiseን ከየት ሰሙ?" question and put the answer into the Telegram message the parent already sends. Paths in the patch start with `site-preview/`; in the live repo drop that prefix (`git apply -p2 --directory=` or make the six edits by hand, they are listed at the end).

## Why the content-security rule matters
The live pages set their rules in a `<meta http-equiv="Content-Security-Policy">` tag and cannot send server headers. Today `connect-src` is `'self'`, so the browser blocks any request to another address. The counter sends to the admin server (a different address), so that one word must change. Inline scripts are already allowed; the counter is an ordinary file from the site itself (`script-src 'self'`), so it needs nothing more.

## The steps, in order (after the admin server is live and working)
1. **Copy** `pw-track.js` to the live repo's `assets/js/pw-track.js` (replace the old file). Both `index.html` and `order.html` should already include `<script src="assets/js/pw-track.js" defer></script>`.
2. **Tell the pages where to send**, in the `<head>` of `index.html` and `order.html`:
   `<meta name="pw-events-endpoint" content="https://admin.parentwiseethiopia.com/api/v1/analytics/events">`
3. **Allow that one address** in each page's content-security meta tag: change `connect-src 'self'` to `connect-src 'self' https://admin.parentwiseethiopia.com`. Change nothing else in the rule.
4. **On the server**, in AletCloud's variables: `ANALYTICS_ENABLED=true`, `ALLOWED_ORIGINS` containing exactly the site's address (`https://parentwiseethiopia.com`, and the `www` address if it is used), `ANALYTICS_ENVIRONMENT=production`, and `ANALYTICS_CAMPAIGNS` listing the campaign names you will put in ad links. Browsers send a quick permission check before the first visit; the server already answers it for the allowed address.
5. **Apply the checkout question** (the patch). This is a visible change for parents, so decide it separately from the counter. The question has four fixed answers; the Amharic wording is a draft that needs a native read.
6. **Update the privacy policy** to say the site keeps a simple visit counter (no cookies, no address, no name or phone) and asks how the parent heard of ParentWise. That wording is your decision.
7. **Check it works:** open the live site in a private window, wait three seconds, and look in the browser's network list for one request to `/api/v1/analytics/events` answering 204. Then open the site once on each of your own devices with `?pw_exclude=1` at the end of the address so your own visits are never counted (use `?pw_exclude=0` to count a device again).

## What the counter does and does not do
- Counts a visit only after the page has been open for 2 seconds, or the visitor scrolls, taps or types. Link-preview robots and automation never count.
- Sends only a random per-tab id, one of five fixed event names, a coarse source and campaign, and a device class. No cookies, no address, no name, no phone, no order code.
- Respects Do Not Track. If the server does not know a campaign name it retries once without it, so the visit is not lost.
- Tested without a browser: `node qa-tests/pw_track_check.js` (10 checks) and `node qa-tests/checkout_message_check.js`.

## The six order.html edits, if you apply them by hand
1. After the phone-format help line, add the required `<select id="heard-from" name="heard">` with the empty choice and `ad`, `telegram`, `friend`, `other`.
2. Add a `#checkout-form select` style that matches the text fields.
3. Add `heard:''` to the `data` object.
4. Before the payment method is read, refuse to continue with the existing `error(...)` helper if the question is empty.
5. Set `data.heard` next to both places that set `data.name` and `data.phone`.
6. Add one line to `buildMessage()` so the Telegram message carries the answer, for example `ከየት ሰሙ: ጓደኛ ወይም ቤተሰብ [friend]`.
