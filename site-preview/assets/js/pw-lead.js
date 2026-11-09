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
   * Only ONE tab sends at a time (a Web Lock, or a short lease in localStorage where Web Locks do not exist), one event at a
     time and in order, so two open tabs never send the same event twice and an older answer cannot overtake a newer one.
   * Every details event carries answered_at, the moment the customer gave that answer (strictly increasing within an attempt).
     The server applies an answer only if it is newer than the last STOP, withdrawal or erasure it knows of, so a request that
     waited in the queue can never undo something that happened later.
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
   * The attempt record in this tab (sessionStorage) holds them only while the attempt is in progress: it is cleared when the
     Telegram step has been accepted, and after 24 hours (checked on every page load, on every send, and by a timer while the
     page stays open). Queued events older than 24 hours are discarded without being sent.
   * Limit: if a customer's details were never accepted and they never open a ParentWise page again, they stay in that
     customer's own browser until they clear it, because a page script cannot run when no page is open. */
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
    var QUEUE_KEY = 'parentwise-lead-queue-v2';       // this browser: events waiting to be accepted by the server
    var DROPPED_KEY = 'parentwise-lead-dropped-v1';   // this browser: how many events were ever dropped because the queue was full
    var LEASE_KEY = 'parentwise-lead-lease-v1';       // this browser: who is sending, where Web Locks are not available
    var LOCK_NAME = 'parentwise-lead-flush';
    var MAX_AGE = 24 * 3600 * 1000, MAX_QUEUE = 100, PAUSES = [1500, 3000, 6000, 12000, 30000], LEASE_MS = 20000;
    var memAttempt = null, memQueue = [];

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

    // ---------------------------------------------------------------- the attempt record (this tab) and its cleanup
    function cleared(record) {
      // Everything personal is gone; only what is needed to avoid re-sending the same steps stays.
      return { id: record.id, at: record.at, enqueued: record.enqueued || {}, done: true };
    }
    function readAttempt() {
      var record = readJSON('sessionStorage', ATTEMPT_KEY, null) || memAttempt;
      if (record && !record.done && record.at && Date.now() - record.at > MAX_AGE) { record = cleared(record); writeAttempt(record); }
      return record;
    }
    function writeAttempt(record) { memAttempt = record; writeJSON('sessionStorage', ATTEMPT_KEY, record); }
    setTimeout(function () { readAttempt(); }, MAX_AGE + 1000);   // a tab left open for a day clears its own copy

    // ---------------------------------------------------------------- the queue
    function readQueue() {
      var q = readJSON('localStorage', QUEUE_KEY, null);
      return Array.isArray(q) ? q : memQueue;
    }
    function writeQueue(q) { memQueue = q; writeJSON('localStorage', QUEUE_KEY, q); }
    function noteDropped(count) {
      writeJSON('localStorage', DROPPED_KEY, (readJSON('localStorage', DROPPED_KEY, 0) || 0) + count);
    }
    function digits(value) { return String(value || '').replace(/[^0-9]/g, '').slice(-9); }
    function field(id) { var el = document.getElementById(id); return el ? el.value.trim() : ''; }
    function method() {
      var el = document.querySelector('input[name="payment"]:checked');
      return el && (el.value === 'bank' || el.value === 'telebirr') ? el.value : undefined;
    }

    var busy = false, timer = null, recheck = null, rechecks = 0, failures = 0, uid = 0;
    var settle = null, SETTLE = 600;
    function enqueue(body, pause) {
      var q = readQueue();
      var item = { uid: Date.now().toString(36) + (uid++) + Math.random().toString(36).slice(2, 6), at: Date.now(), body: body };
      if (body.step === 'details_submitted') {
        // A newer answer replaces an older details event of this attempt that the server has not accepted yet.
        for (var i = 0; i < q.length; i++) {
          if (q[i].body.attempt_id === body.attempt_id && q[i].body.step === 'details_submitted') { q[i] = item; item = null; break; }
        }
      }
      if (item) q.push(item);
      if (q.length > MAX_QUEUE) {
        var dropped = 0;
        while (q.length > MAX_QUEUE) {
          var victim = -1;
          for (var j = 0; j < q.length; j++) { if (q[j].body.step !== 'details_submitted') { victim = j; break; } }   // step events first, oldest first
          q.splice(victim < 0 ? 0 : victim, 1); dropped += 1;
        }
        noteDropped(dropped);
      }
      writeQueue(q);
      // A change the customer makes to their own answer waits a moment before it is sent, so a quick change of mind
      // (tick, then un-tick) replaces the first answer instead of reaching the server as two.
      if (pause) { clearTimeout(settle); settle = setTimeout(flush, SETTLE); } else flush();
    }
    function removeItem(id) {
      writeQueue(readQueue().filter(function (x) { return x.uid !== id; }));
    }
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
      if (window.navigator && navigator.locks && navigator.locks.request) {
        return navigator.locks.request(LOCK_NAME, { ifAvailable: true }, function (lock) { return lock ? task().then(function () { return true; }) : false; })
          .then(function (ran) { return ran === true; }, function () { return false; });
      }
      // Fallback: a short lease in localStorage (best effort; Web Locks are in every current browser).
      var lease = readJSON('localStorage', LEASE_KEY, null);
      if (lease && lease.owner !== TAB && lease.until > Date.now()) return Promise.resolve(false);
      writeJSON('localStorage', LEASE_KEY, { owner: TAB, until: Date.now() + LEASE_MS });
      var mine = readJSON('localStorage', LEASE_KEY, null);
      if (!mine || mine.owner !== TAB) return Promise.resolve(false);
      return task().then(function () { removeKey('localStorage', LEASE_KEY); return true; }, function () { removeKey('localStorage', LEASE_KEY); return true; });
    }
    function renewLease() { if (!(window.navigator && navigator.locks)) writeJSON('localStorage', LEASE_KEY, { owner: TAB, until: Date.now() + LEASE_MS }); }

    function afterAccepted(item) {
      if (item.body.step === 'telegram_opened') {   // the last step: nothing personal is needed any more
        var record = readAttempt();
        if (record && record.id === item.body.attempt_id) writeAttempt(cleared(record));
      }
    }
    function drain() {
      return new Promise(function (resolve) {
        (function next() {
          var all = readQueue();
          var q = all.filter(function (x) { return x && x.body && Date.now() - x.at < MAX_AGE; });
          if (q.length !== all.length) writeQueue(q);
          if (!q.length) { failures = 0; return resolve(); }
          var item = q[0];
          renewLease();
          send(item.body).then(function (status) {
            if (status >= 200 && status < 300) {
              failures = 0; removeItem(item.uid); afterAccepted(item); next();
            } else if (status === 409 && item.body.step !== 'details_submitted' && !item.resent) {
              // The server never saw the details for this attempt: send them first (once), then this event again.
              var record = readAttempt();
              var q2 = readQueue().map(function (x) { if (x.uid === item.uid) x.resent = true; return x; });
              if (record && record.id === item.body.attempt_id && record.details) {
                q2.unshift({ uid: item.uid + 'd', at: Date.now(), body: record.details });
                writeQueue(q2); next();
              } else {
                removeItem(item.uid); next();          // the details are no longer kept in this tab: nothing to resend from here
              }
            } else if (status === 0 || status === 429 || status >= 500) {
              failures += 1; schedule(); resolve();    // keep it: busy server or no network
            } else {
              removeItem(item.uid); next();            // a final answer (403, 413, 422, a second 409): drop this event only
            }
          });
        })();
      });
    }
    function flush() {
      if (busy) return;
      busy = true;
      holdSender(drain).then(function (ran) {
        busy = false;
        if (!ran && readQueue().length && rechecks < 5 && !recheck) {
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

    // ---------------------------------------------------------------- what is queued, and when
    function detailsBody(record, name) {
      // The small checkout line ("we will contact you about your order with this information") is on screen whenever capture is on.
      var noticeShown = !!(notice && !notice.hidden);
      // Separate, optional and unticked by default: only a customer's own tick allows promotional follow-up.
      var promoOptIn = !!(document.getElementById('lead-promo') || {}).checked;
      return { attempt_id: record.id, step: 'details_submitted', name: name, phone: record.phone, payment_method: method(), order_contact_notice: noticeShown, promo_opt_in: promoOptIn };
    }
    function sameAnswer(a, b) { return !!a && a.name === b.name && a.promo_opt_in === b.promo_opt_in; }
    function stamp(record) {   // when the customer gave this answer; strictly increasing within the attempt
      var at = Math.max(Date.now(), (record.lastAnswer || 0) + 1);
      record.lastAnswer = at;
      return at;
    }

    // Details step: called when the payment page opens, i.e. when the customer's details passed validation.
    function details() {
      var name = field('customer-name'), phone = field('customer-mobile');
      if (!name || !phone) return;
      var key = digits(phone);
      var record = readAttempt();
      if (!record || record.done || record.phoneKey !== key) {
        record = { id: newId(), at: Date.now(), phoneKey: key, phone: phone, enqueued: {}, details: null };
      }
      var body = detailsBody(record, name);
      if (!sameAnswer(record.details, body)) {   // first time, or the name / follow-up box changed since the last copy
        body.answered_at = stamp(record);
        record.details = body;
        record.enqueued.details_submitted = true;
        writeAttempt(record);
        enqueue(body);
      } else {
        writeAttempt(record);
      }
    }
    // The customer changes the follow-up box or the name after the details were queued, in the same attempt: queue the update.
    function answerChanged() {
      var record = readAttempt();
      if (!record || record.done || !record.details) return;
      var name = field('customer-name');
      if (name.length < 2 || !/[A-Za-zሀ-፿]/.test(name)) return;
      // The phone stays the one this attempt started with; a different phone becomes a new attempt when the payment page opens.
      if (digits(field('customer-mobile')) !== record.phoneKey) return;
      var body = detailsBody(record, name);
      if (sameAnswer(record.details, body)) return;
      body.answered_at = stamp(record);
      record.details = body; writeAttempt(record);
      enqueue(body, true);
    }
    function step(name) {
      var record = readAttempt();
      if (!record || !record.id || record.done || !record.details || record.enqueued[name]) return;
      record.enqueued[name] = true; writeAttempt(record);
      enqueue({ attempt_id: record.id, step: name, payment_method: method() });   // no personal data is copied into a step event
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

    readAttempt();   // clears an attempt that is older than a day
    flush();         // anything left from an earlier page load or a failed send
  } catch (e) { /* the lead script must never affect checkout */ }
})();
