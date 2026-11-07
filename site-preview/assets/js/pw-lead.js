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
   * Events go out one at a time, in order, so a later answer to the follow-up box can never overtake an earlier one.
   * Busy server (429/5xx) or no network: wait and try again with a growing pause (about 1.5s up to 30s, giving up after 6 sends
     in a row per page visit); the queue is kept and sent again at the next trigger. 409 (server has not seen the details yet): the
     details are sent first, once, then the event. Other 4xx answers are final and the event is dropped.
   * If the customer changes the follow-up box or their name after the details were sent, the updated details are queued
     again for the same attempt (an update that has not left the browser yet replaces the older one).
   * Queued events older than 24 hours are discarded. The queue holds only what the customer typed on this page. */
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
    var MAX_AGE = 24 * 3600 * 1000, MAX_QUEUE = 24, PAUSES = [1500, 3000, 6000, 12000, 30000];
    var memAttempt = null, memQueue = [];

    function store(kind) { try { return window[kind]; } catch (e) { return null; } }
    function readJSON(kind, key, fallback) {
      try { var s = store(kind); var raw = s && s.getItem(key); return raw ? JSON.parse(raw) : fallback; } catch (e) { return fallback; }
    }
    function writeJSON(kind, key, value) {
      try { var s = store(kind); if (s) s.setItem(key, JSON.stringify(value)); } catch (e) { /* storage may be restricted: memory copy still works */ }
    }
    function readAttempt() { return readJSON('sessionStorage', ATTEMPT_KEY, null) || memAttempt; }
    function writeAttempt(record) { memAttempt = record; writeJSON('sessionStorage', ATTEMPT_KEY, record); }
    function readQueue() {
      var q = readJSON('localStorage', QUEUE_KEY, null);
      return Array.isArray(q) ? q : memQueue;
    }
    function writeQueue(q) { memQueue = q; writeJSON('localStorage', QUEUE_KEY, q); }

    function newId() {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
      var b = new Uint8Array(16); crypto.getRandomValues(b);
      b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
      var h = Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
      return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
    }
    function digits(value) { return String(value || '').replace(/[^0-9]/g, '').slice(-9); }
    function field(id) { var el = document.getElementById(id); return el ? el.value.trim() : ''; }
    function method() {
      var el = document.querySelector('input[name="payment"]:checked');
      return el && (el.value === 'bank' || el.value === 'telebirr') ? el.value : undefined;
    }

    // ---------------------------------------------------------------- the queue
    var busy = false, timer = null, failures = 0, uid = 0;
    function enqueue(body, details) {
      var q = readQueue();
      var item = { uid: Date.now().toString(36) + (uid++) + Math.random().toString(36).slice(2, 6), at: Date.now(), body: body, details: details || null };
      if (body.step === 'details_submitted') {
        // A newer answer replaces an older details event for this attempt that has not left the browser yet (never the one in flight).
        for (var i = 0; i < q.length; i++) {
          if (q[i].body.attempt_id === body.attempt_id && q[i].body.step === 'details_submitted' && !(busy && i === 0)) { q[i] = item; item = null; break; }
        }
      }
      if (item) q.push(item);
      while (q.length > MAX_QUEUE) q.shift();
      writeQueue(q);
      flush();
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
    function flush() {
      if (busy) return;
      var q = readQueue().filter(function (x) { return x && x.body && Date.now() - x.at < MAX_AGE; });
      if (q.length !== readQueue().length) writeQueue(q);
      if (!q.length) { failures = 0; return; }
      var item = q[0];
      busy = true;
      send(item.body).then(function (status) {
        busy = false;
        if (status >= 200 && status < 300) {
          failures = 0; removeItem(item.uid); flush();
        } else if (status === 409 && item.body.step !== 'details_submitted' && item.details && !item.resent) {
          // The server never saw the details for this attempt: send them first (once), then this event again.
          var again = readQueue().map(function (x) { if (x.uid === item.uid) x.resent = true; return x; });
          again.unshift({ uid: item.uid + 'd', at: Date.now(), body: item.details, details: null });
          writeQueue(again); flush();
        } else if (status === 0 || status === 429 || status >= 500) {
          failures += 1; schedule();                   // keep it: busy server or no network
        } else {
          removeItem(item.uid); flush();               // a final answer (403, 413, 422, a second 409): drop this event only
        }
      });
    }
    function trigger() { failures = 0; flush(); }
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

    // Details step: called when the payment page opens, i.e. when the customer's details passed validation.
    function details() {
      var name = field('customer-name'), phone = field('customer-mobile');
      if (!name || !phone) return;
      var key = digits(phone);
      var record = readAttempt();
      if (!record || record.phoneKey !== key) {
        record = { id: newId(), phoneKey: key, phone: phone, enqueued: {}, details: null };
      }
      var body = detailsBody(record, name);
      if (!sameAnswer(record.details, body)) {   // first time, or the name / follow-up box changed since the last copy
        record.details = body;
        record.enqueued.details_submitted = true;
        writeAttempt(record);
        enqueue(body, null);
      } else {
        writeAttempt(record);
      }
    }
    // The customer changes the follow-up box or the name after the details were queued, in the same attempt: queue the update.
    function answerChanged() {
      var record = readAttempt();
      if (!record || !record.details) return;
      var name = field('customer-name');
      if (name.length < 2 || !/[A-Za-zሀ-፿]/.test(name)) return;
      // The phone stays the one this attempt started with; a different phone becomes a new attempt when the payment page opens.
      if (digits(field('customer-mobile')) !== record.phoneKey) return;
      var body = detailsBody(record, name);
      if (sameAnswer(record.details, body)) return;
      record.details = body; writeAttempt(record);
      enqueue(body, null);
    }
    function step(name) {
      var record = readAttempt();
      if (!record || !record.id || !record.details || record.enqueued[name]) return;
      record.enqueued[name] = true; writeAttempt(record);
      enqueue({ attempt_id: record.id, step: name, payment_method: method() }, record.details);
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

    flush();   // anything left from an earlier page load or a failed send
  } catch (e) { /* the lead script must never affect checkout */ }
})();
