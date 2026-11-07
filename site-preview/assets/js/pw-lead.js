/* ParentWise checkout lead capture (dormant by default).
   Active only when <meta name="pw-leads-endpoint" content="https://.../api/v1/leads"> is present.
   What it sends: the name and phone the customer typed when they continue from the details step (plus whether
   they ticked the optional follow-up box), then four content-free step events (payment page viewed, "I have
   paid" pressed, proof page viewed, Telegram button pressed). A random attempt id ties the steps together.
   What it never does: create an order, read payment details, block or delay checkout, or claim that a Telegram
   message was sent. Failures are silent and checkout continues. Read-only with respect to the order code. */
(function () {
  'use strict';
  try {
    var meta = document.querySelector('meta[name="pw-leads-endpoint"]');
    var endpoint = meta && meta.content;
    var notice = document.getElementById('lead-notice');
    var consentRow = document.getElementById('lead-consent-row');
    if (!endpoint || !/^https:\/\/[a-z0-9.-]+(:443)?\/api\/v1\/leads$/i.test(endpoint)) return;
    if (notice) notice.hidden = false;
    if (consentRow) consentRow.hidden = false;

    var KEY = 'parentwise-lead-attempt-v1';
    var memory = null;
    function read() {
      try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) { return memory; }
    }
    function write(record) {
      memory = record;
      try { sessionStorage.setItem(KEY, JSON.stringify(record)); } catch (e) { /* storage may be restricted */ }
    }
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

    function post(body, retry) {
      try {
        fetch(endpoint, {
          method: 'POST', mode: 'cors', credentials: 'omit', cache: 'no-store', keepalive: true,
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
        }).then(function (response) {
          // 409: the server has not seen the details step for this attempt (it failed earlier). Send it again once.
          if (response.status === 409 && !retry) {
            var current = read();
            if (current && current.id === body.attempt_id && current.details) {
              post(current.details, true);
              setTimeout(function () { post(body, true); }, 400);
            }
          }
        }).catch(function () { /* never interrupt checkout */ });
      } catch (e) { /* never interrupt checkout */ }
    }

    // Details step: called when the payment page opens, i.e. when the customer's details passed validation.
    function details() {
      var name = field('customer-name'), phone = field('customer-mobile');
      if (!name || !phone) return;
      var key = digits(phone);
      var record = read();
      if (!record || record.phoneKey !== key) {
        record = { id: newId(), phoneKey: key, sent: {}, details: null };
      }
      var consent = !!(document.getElementById('lead-consent') || {}).checked;
      var body = { attempt_id: record.id, step: 'details_submitted', name: name, phone: phone, payment_method: method(), follow_up_consent: consent };
      record.details = body;
      if (!record.sent.details_submitted) { record.sent.details_submitted = true; post(body); }
      write(record);
    }
    function step(name) {
      var record = read();
      if (!record || !record.id || record.sent[name]) return;
      record.sent[name] = true; write(record);
      post({ attempt_id: record.id, step: name, payment_method: method() });
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

    var paid = document.getElementById('paid-action');
    if (paid) paid.addEventListener('click', function () { step('paid_clicked'); }, true);
    var telegram = document.getElementById('telegram-handoff');
    // A click on the Telegram button is recorded as a click only. It does not prove a message was sent.
    if (telegram) telegram.addEventListener('click', function () { step('telegram_opened'); }, true);
  } catch (e) { /* the lead script must never affect checkout */ }
})();
