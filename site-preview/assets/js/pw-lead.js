/* ParentWise checkout lead capture (dormant by default).
   Active only when <meta name="pw-leads-endpoint" content="https://.../api/v1/leads"> is present.
   What it sends: the name and phone the customer typed when they continue from the details step (plus whether
   they ticked the optional follow-up box), then four content-free step events (payment page viewed, "I have
   paid" pressed, proof page viewed, Telegram button pressed). A random attempt id ties the steps together.
   What it never does: create an order, read payment details, block or delay checkout, or claim that a Telegram
   message was sent. Failures are silent and checkout continues. Read-only with respect to the order code.

   Delivery (so a lead is not silently lost):
   * Every event is first written to a small queue in this browser (localStorage) and removed only after the server
     accepts it. A reload, a closed tab or a dropped connection therefore does not lose it; it is sent on the next
     page load, when the connection comes back, or when the tab becomes visible again.
   * Every change to the shared queue (adding, removing, expiring) runs inside a Web Lock, so two tabs can never overwrite
     each other's additions. The queue carries a version number; if the browser refuses a write (storage full or blocked) the
     newer copy kept in memory is used instead of an older stored one.
   * Only ONE tab sends at a time (a second Web Lock, or a lease in localStorage where Web Locks do not exist; the lease is renewed
     for as long as a request is in flight), one event at a time and in order.
   * Time. The page asks the server for its clock (GET <endpoint>/clock: server time plus the server's signature) and works out every
     answer time in SERVER time, so a phone whose clock is fast or slow cannot make an answer look newer or older than it was. The
     stamp travels with the details event; the server applies an answer only if it is newer than the last STOP, withdrawal or erasure it
     knows of. If the clock cannot be fetched the details are still sent, but without a stamp: the server then treats the answer time as
     unverified (an un-tick still counts, a tick does not, and nobody erased is recreated).
   * Busy server (429/5xx) or no network: wait and try again with a growing pause (about 1.5s up to 30s, giving up after 6 sends
     in a row per page visit); the queue is kept and sent again at the next trigger. 409 (the server has not seen the details yet):
     the details are sent first, once, then the event. Other 4xx answers are final and the event is dropped.
   * If the customer changes the follow-up box or their name after the details were sent, the updated details are queued
     again for the same attempt, after a short pause (0.6 s); an update that has not been accepted yet replaces the older
     one, so a quick tick and un-tick is never sent as two answers.
   * The queue keeps up to 100 events. If it is ever full, step events are dropped before details events, oldest first, and
     the number dropped is kept in localStorage ("parentwise-lead-dropped-v1") instead of disappearing without a trace.

   Personal data in this browser (only what the customer typed on this page):
   * The name and phone sit in the queue only until the server accepts them. Step events never copy them.
   * The attempt record in this tab (sessionStorage) holds them only while the attempt is in progress. It is cleared when the Telegram
     step has been accepted (by this tab, or by another tab: that tab signals this one through a localStorage event) and 24 hours after
     THE ATTEMPT BEGAN (a timer is set for each attempt, and the age is also checked on every page load and every send). Queued events
     older than 24 hours are discarded without being sent.
   * Limit: if a customer's details were never accepted and they never open a ParentWise page again, they stay in that
     customer's own browser until they clear it, because a page script cannot run when no page is open.

   Test hooks (set by the browser checks before the script runs; never set on the live site): window.__pwLeadMaxAgeMs and
   window.__pwLeadLeaseMs shorten the 24-hour and 20-second periods so they can be tested in seconds. */
(function () {
  'use strict';
  try {
    var meta = document.querySelector('meta[name="pw-leads-endpoint"]');
    var endpoint = meta && meta.content;
    var notice = document.getElementById('lead-notice');
    var promoRow = document.getElementById('lead-promo-row');
    if (!endpoint || !/^https:\/\/[a-z0-9.-]+(:443)?\/api\/v1\/leads$/i.test(endpoint)) return;
    if (notice) notice.hidden = false;
    if (promoRow) promoRow.hidden = false;

    var ATTEMPT_KEY = 'parentwise-lead-attempt-v1';   // this tab: the current attempt (survives reload in the same tab)
    var QUEUE_KEY = 'parentwise-lead-queue-v3';       // this browser: events waiting to be accepted by the server ({v, items})
    var DROPPED_KEY = 'parentwise-lead-dropped-v1';   // this browser: how many events were ever dropped because the queue was full
    var LEASE_KEY = 'parentwise-lead-lease-v1';       // this browser: who is sending, where Web Locks are not available
    var DONE_KEY = 'parentwise-lead-done-v1';         // this browser: "this attempt finished" signal for the tab that owns its record
    var SEND_LOCK = 'parentwise-lead-flush', QUEUE_LOCK = 'parentwise-lead-queue';
    var MAX_AGE = (window.__pwLeadMaxAgeMs | 0) || 24 * 3600 * 1000;
    var LEASE_MS = (window.__pwLeadLeaseMs | 0) || 20000;
    var MAX_QUEUE = 100, PAUSES = [1500, 3000, 6000, 12000, 30000];
    var memAttempt = null, memQueue = { v: 0, items: [] };

    function store(kind) { try { return window[kind]; } catch (e) { return null; } }
    function readJSON(kind, key, fallback) {
      try { var s = store(kind); var raw = s && s.getItem(key); return raw ? JSON.parse(raw) : fallback; } catch (e) { return fallback; }
    }
    function writeJSON(kind, key, value) {
      try { var s = store(kind); if (s) s.setItem(key, JSON.stringify(value)); } catch (e) { /* storage may be restricted: memory copy still works */ }
    }
    function removeKey(kind, key) { try { var s = store(kind); if (s) s.removeItem(key); } catch (e) { /* ignore */ } }

    function newId() {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
      var b = new Uint8Array(16); crypto.getRandomValues(b);
      b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
      var h = Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
      return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
    }
    var TAB = newId();
    function hasLocks() { return !!(window.navigator && navigator.locks && navigator.locks.request); }

    // ---------------------------------------------------------------- the attempt record (this tab) and its cleanup
    var expiryTimer = null;
    function cleared(record) {
      // Everything personal is gone; only what is needed to avoid re-sending the same steps stays.
      return { id: record.id, at: record.at, enqueued: record.enqueued || {}, done: true };
    }
    function scheduleExpiry(record) {
      clearTimeout(expiryTimer);
      if (!record || record.done || !record.at) return;
      expiryTimer = setTimeout(function () { readAttempt(); }, Math.max(0, record.at + MAX_AGE - Date.now()) + 500);   // from when THIS attempt began
    }
    function readAttempt() {
      var record = readJSON('sessionStorage', ATTEMPT_KEY, null) || memAttempt;
      if (record && !record.done && record.at && Date.now() - record.at > MAX_AGE) { record = cleared(record); writeAttempt(record); }
      return record;
    }
    function writeAttempt(record) {
      memAttempt = record; writeJSON('sessionStorage', ATTEMPT_KEY, record);
      scheduleExpiry(record);
    }
    // Another tab accepted the Telegram step of the attempt this tab holds: clear this tab's copy too.
    window.addEventListener('storage', function (e) {
      if (e.key !== DONE_KEY || !e.newValue) return;
      try {
        var done = JSON.parse(e.newValue), record = readAttempt();
        if (record && !record.done && record.id === done.id) writeAttempt(cleared(record));
      } catch (err) { /* ignore */ }
    });

    // ---------------------------------------------------------------- the queue: versioned, changed only inside a lock
    function parseQueue(raw) {
      try {
        var value = JSON.parse(raw);
        if (Array.isArray(value)) return { v: 0, items: value };
        if (value && Array.isArray(value.items) && typeof value.v === 'number') return value;
      } catch (e) { /* unreadable */ }
      return null;
    }
    function readQueue() {
      var persisted = null;
      try { var s = store('localStorage'); persisted = parseQueue(s && s.getItem(QUEUE_KEY)); } catch (e) { persisted = null; }
      return persisted && persisted.v >= memQueue.v ? persisted : memQueue;   // a refused write leaves the newer copy in memory
    }
    function writeQueue(q) {
      memQueue = q;
      try { var s = store('localStorage'); if (s) s.setItem(QUEUE_KEY, JSON.stringify(q)); } catch (e) { /* the memory copy is the newer one now */ }
    }
    function mutate(change) {   // change(items) returns the new items; runs under the queue lock so two tabs cannot overwrite each other
      function run() { var q = readQueue(); var items = change(q.items.slice()); writeQueue({ v: q.v + 1, items: items }); return items; }
      if (hasLocks()) return navigator.locks.request(QUEUE_LOCK, function () { return run(); });
      return Promise.resolve(run());   // no Web Locks: best effort
    }
    function noteDropped(count) { writeJSON('localStorage', DROPPED_KEY, (readJSON('localStorage', DROPPED_KEY, 0) || 0) + count); }
    function digits(value) { return String(value || '').replace(/[^0-9]/g, '').slice(-9); }
    function field(id) { var el = document.getElementById(id); return el ? el.value.trim() : ''; }
    function method() {
      var el = document.querySelector('input[name="payment"]:checked');
      return el && (el.value === 'bank' || el.value === 'telebirr') ? el.value : undefined;
    }

    var busy = false, timer = null, recheck = null, rechecks = 0, failures = 0, uid = 0;
    var settle = null, SETTLE = 600;
    function enqueue(body, pause) {
      var item = { uid: Date.now().toString(36) + (uid++) + Math.random().toString(36).slice(2, 6), at: Date.now(), body: body };
      return mutate(function (items) {
        if (body.step === 'details_submitted') {
          // A newer answer replaces an older details event of this attempt that the server has not accepted yet.
          for (var i = 0; i < items.length; i++) {
            if (items[i].body.attempt_id === body.attempt_id && items[i].body.step === 'details_submitted') { items[i] = item; item = null; break; }
          }
        }
        if (item) items.push(item);
        var dropped = 0;
        while (items.length > MAX_QUEUE) {
          var victim = -1;
          for (var j = 0; j < items.length; j++) { if (items[j].body.step !== 'details_submitted') { victim = j; break; } }   // step events first, oldest first
          items.splice(victim < 0 ? 0 : victim, 1); dropped += 1;
        }
        if (dropped) noteDropped(dropped);
        return items;
      }).then(function () {
        // A change the customer makes to their own answer waits a moment before it is sent, so a quick change of mind
        // (tick, then un-tick) replaces the first answer instead of reaching the server as two.
        if (pause) { clearTimeout(settle); settle = setTimeout(flush, SETTLE); } else flush();
      });
    }
    function removeItem(id) { return mutate(function (items) { return items.filter(function (x) { return x.uid !== id; }); }); }
    function schedule() {
      if (timer || failures > PAUSES.length) return;   // after 5 failed tries in a row wait for the next trigger
      var pause = PAUSES[Math.min(failures, PAUSES.length) - 1] || PAUSES[0];
      timer = setTimeout(function () { timer = null; flush(); }, pause + Math.random() * 1000);
    }
    function send(body) {
      return fetch(endpoint, {
        method: 'POST', mode: 'cors', credentials: 'omit', cache: 'no-store', keepalive: true,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      }).then(function (response) { return response.status; }, function () { return 0; });
    }

    // One sender across all tabs of this browser.
    function holdSender(task) {
      if (hasLocks()) {
        return navigator.locks.request(SEND_LOCK, { ifAvailable: true }, function (lock) { return lock ? task().then(function () { return true; }) : false; })
          .then(function (ran) { return ran === true; }, function () { return false; });
      }
      // Fallback: a lease in localStorage, renewed while a request is in flight (best effort; Web Locks are in every current browser).
      var lease = readJSON('localStorage', LEASE_KEY, null);
      if (lease && lease.owner !== TAB && lease.until > Date.now()) return Promise.resolve(false);
      writeJSON('localStorage', LEASE_KEY, { owner: TAB, until: Date.now() + LEASE_MS });
      var mine = readJSON('localStorage', LEASE_KEY, null);
      if (!mine || mine.owner !== TAB) return Promise.resolve(false);
      return task().then(function () { removeKey('localStorage', LEASE_KEY); return true; }, function () { removeKey('localStorage', LEASE_KEY); return true; });
    }
    function renewLease() { if (!hasLocks()) writeJSON('localStorage', LEASE_KEY, { owner: TAB, until: Date.now() + LEASE_MS }); }

    function afterAccepted(item) {
      if (item.body.step === 'telegram_opened') {   // the last step: nothing personal is needed any more, in this tab or in the one that owns the record
        var record = readAttempt();
        if (record && record.id === item.body.attempt_id) writeAttempt(cleared(record));
        writeJSON('localStorage', DONE_KEY, { id: item.body.attempt_id, at: Date.now() });
      }
    }
    function drain() {
      return new Promise(function (resolve) {
        var renew = setInterval(renewLease, Math.max(200, Math.floor(LEASE_MS / 3)));   // keeps the fallback lease alive through a slow request
        function finish() { clearInterval(renew); resolve(); }
        (function next() {
          var all = readQueue().items;
          var fresh = all.filter(function (x) { return x && x.body && Date.now() - x.at < MAX_AGE; });
          (fresh.length === all.length ? Promise.resolve() : mutate(function (items) {
            return items.filter(function (x) { return x && x.body && Date.now() - x.at < MAX_AGE; });
          })).then(function () {
            var items = readQueue().items;
            if (!items.length) { failures = 0; return finish(); }
            var item = items[0];
            renewLease();
            send(item.body).then(function (status) {
              if (status >= 200 && status < 300) {
                failures = 0;
                removeItem(item.uid).then(function () { afterAccepted(item); next(); });
              } else if (status === 409 && item.body.step !== 'details_submitted' && !item.resent) {
                // The server never saw the details for this attempt: send them first (once), then this event again.
                var record = readAttempt();
                var details = record && record.id === item.body.attempt_id && record.details && record.details.answered_at ? record.details : null;
                mutate(function (list) {
                  if (!details) return list.filter(function (x) { return x.uid !== item.uid; });   // the details are no longer kept in this tab: nothing to resend from here
                  list = list.map(function (x) { if (x.uid === item.uid) x.resent = true; return x; });
                  list.unshift({ uid: item.uid + 'd', at: Date.now(), body: details });
                  return list;
                }).then(next);
              } else if (status === 0 || status === 429 || status >= 500) {
                failures += 1; schedule(); finish();    // keep it: busy server or no network
              } else {
                removeItem(item.uid).then(next);        // a final answer (403, 413, 422, a second 409): drop this event only
              }
            });
          });
        })();
      });
    }
    function flush() {
      if (busy) return;
      busy = true;
      holdSender(drain).then(function (ran) {
        busy = false;
        if (!ran && readQueue().items.length && rechecks < 5 && !recheck) {
          // Another tab is sending. Look again shortly in case that tab was closed in the middle of it.
          rechecks += 1;
          recheck = setTimeout(function () { recheck = null; flush(); }, 3000 + Math.random() * 2000);
        } else if (ran) { rechecks = 0; }
      });
    }
    function trigger() { failures = 0; rechecks = 0; flush(); }
    window.addEventListener('online', trigger);
    window.addEventListener('pageshow', trigger);
    window.addEventListener('pagehide', function () { flush(); });
    document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') trigger(); });

    // ---------------------------------------------------------------- the server's clock
    var clock = null, clockPending = null;
    function fetchClock() {
      if (clockPending) return clockPending;
      var t0 = performance.now();
      clockPending = fetch(endpoint + '/clock', { method: 'GET', mode: 'cors', credentials: 'omit', cache: 'no-store' })
        .then(function (response) { return response.ok ? response.json() : Promise.reject(new Error('clock')); })
        .then(function (data) {
          var t1 = performance.now();
          if (data && typeof data.now_ms === 'number' && typeof data.sig === 'string') clock = { ms: data.now_ms, sig: data.sig, mid: (t0 + t1) / 2 };
        })
        .then(function () { clockPending = null; }, function () { clockPending = null; });   // an unreachable clock is not an error: the answer is then unverified
      return clockPending;
    }
    function ensureClock() {
      var stale = !clock || performance.now() - clock.mid > 30 * 60 * 1000;
      if (!stale) return Promise.resolve();
      return Promise.race([fetchClock(), new Promise(function (resolve) { setTimeout(resolve, 1500); })]);   // never hold anything up for long
    }
    function clockFields(acted) {   // acted: performance.now() at the moment the customer acted
      if (!clock) return { answered_at: Date.now() };   // no stamp: the server treats this time as unverified
      return { answered_at: Math.max(clock.ms, Math.round(clock.ms + (acted - clock.mid))), clock_ms: clock.ms, clock_sig: clock.sig };
    }

    // ---------------------------------------------------------------- what is queued, and when
    var pending = Promise.resolve();   // everything that is queued goes through here, in the order the customer did it
    function after(task) { pending = pending.then(task, task).catch(function () { /* never interrupt checkout */ }); return pending; }
    function detailsBody(record, name) {
      // The small checkout line ("we will contact you about your order with this information") is on screen whenever capture is on.
      var noticeShown = !!(notice && !notice.hidden);
      // Separate, optional and unticked by default: only a customer's own tick allows promotional follow-up.
      var promoOptIn = !!(document.getElementById('lead-promo') || {}).checked;
      return { attempt_id: record.id, step: 'details_submitted', name: name, phone: record.phone, payment_method: method(), order_contact_notice: noticeShown, promo_opt_in: promoOptIn };
    }
    function sameAnswer(a, b) { return !!a && a.name === b.name && a.promo_opt_in === b.promo_opt_in; }
    function finishAnswer(record, body, acted, pause) {   // adds the server-time answer and queues it
      return ensureClock().then(function () {
        var fields = clockFields(acted);
        var latest = readAttempt();
        var base = latest && latest.id === record.id ? latest : record;
        fields.answered_at = Math.max(fields.answered_at, (base.lastAnswer || 0) + 1);   // strictly increasing within the attempt
        for (var k in fields) body[k] = fields[k];
        base.lastAnswer = fields.answered_at; base.details = body;
        writeAttempt(base);
        return enqueue(body, pause);
      });
    }

    // Details step: called when the payment page opens, i.e. when the customer's details passed validation.
    function details() {
      var name = field('customer-name'), phone = field('customer-mobile');
      if (!name || !phone) return Promise.resolve();
      var acted = performance.now();
      var key = digits(phone);
      var record = readAttempt();
      if (!record || record.done || record.phoneKey !== key) {
        record = { id: newId(), at: Date.now(), phoneKey: key, phone: phone, enqueued: {}, details: null };
      }
      var body = detailsBody(record, name);
      if (sameAnswer(record.details, body)) { writeAttempt(record); return Promise.resolve(); }   // first time, or the name / follow-up box changed since the last copy
      record.details = body;
      record.enqueued.details_submitted = true;
      writeAttempt(record);
      return after(function () { return finishAnswer(record, body, acted, false); });
    }
    // The customer changes the follow-up box or the name after the details were queued, in the same attempt: queue the update.
    function answerChanged() {
      var record = readAttempt();
      if (!record || record.done || !record.details) return;
      var name = field('customer-name');
      if (name.length < 2 || !/[A-Za-zሀ-፿]/.test(name)) return;
      // The phone stays the one this attempt started with; a different phone becomes a new attempt when the payment page opens.
      if (digits(field('customer-mobile')) !== record.phoneKey) return;
      var acted = performance.now();
      var body = detailsBody(record, name);
      if (sameAnswer(record.details, body)) return;
      record.details = body; writeAttempt(record);
      after(function () { return finishAnswer(record, body, acted, true); });
    }
    function step(name) {
      var record = readAttempt();
      if (!record || !record.id || record.done || !record.details || record.enqueued[name]) return;
      record.enqueued[name] = true; writeAttempt(record);
      var body = { attempt_id: record.id, step: name, payment_method: method() };   // no personal data is copied into a step event
      after(function () { return enqueue(body); });
    }

    function watch(id, onShow) {
      var el = document.getElementById(id);
      if (!el || !window.MutationObserver) return;
      var wasHidden = el.hidden;
      new MutationObserver(function () {
        if (wasHidden && !el.hidden) onShow();
        wasHidden = el.hidden;
      }).observe(el, { attributes: true, attributeFilter: ['hidden'] });
    }
    watch('payment-section', function () { details(); step('payment_viewed'); });
    watch('telegram-section', function () { step('proof_viewed'); });

    var promo = document.getElementById('lead-promo');
    if (promo) promo.addEventListener('change', answerChanged);
    var nameField = document.getElementById('customer-name');
    if (nameField) nameField.addEventListener('change', answerChanged);

    var paid = document.getElementById('paid-action');
    if (paid) paid.addEventListener('click', function () { step('paid_clicked'); }, true);
    var telegram = document.getElementById('telegram-handoff');
    // A click on the Telegram button is recorded as a click only. It does not prove a message was sent.
    if (telegram) telegram.addEventListener('click', function () { step('telegram_opened'); }, true);

    fetchClock();            // measure the server's clock early, so it is ready when the customer acts
    var oldDone = readJSON('localStorage', DONE_KEY, null);
    if (oldDone && Date.now() - oldDone.at > MAX_AGE) removeKey('localStorage', DONE_KEY);
    scheduleExpiry(readAttempt());   // clears an attempt that is older than a day, and sets its timer
    flush();                 // anything left from an earlier page load or a failed send
  } catch (e) { /* the lead script must never affect checkout */ }
})();
