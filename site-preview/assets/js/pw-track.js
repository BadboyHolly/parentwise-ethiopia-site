/* ParentWise first-party visit counter.
   Speaks the founder server's collector: POST <endpoint> with one allowed event, a random per-tab session id (UUID), a coarse source,
   campaign and device class. No cookies, no IP, no user agent, no names, phone numbers, order codes or payment details are read or sent.
   Dormant unless <meta name="pw-events-endpoint" content="https://.../api/v1/analytics/events"> is present.
   Respects Do Not Track and Global Privacy Control. Never touches the order or payment code.
   A visit counts only when a person is there: the page stays open and visible for 2 seconds, or the visitor scrolls, taps or types.
   Link-preview robots and automation never count. To leave your own visits out, open the site once on each of your devices with
   ?pw_exclude=1 (and ?pw_exclude=0 to count this device again). The flag lives on the device, never an IP address. */
(function () {
  'use strict';
  try {
    var meta = document.querySelector('meta[name="pw-events-endpoint"]');
    var endpoint = meta && meta.content;
    if (!endpoint || !/^https:\/\//.test(endpoint)) return;
    if (navigator.doNotTrack === '1' || navigator.globalPrivacyControl === true) return;

    var q = new URLSearchParams(location.search);
    try {
      if (q.get('pw_exclude') === '1') localStorage.setItem('pw_exclude', '1');
      if (q.get('pw_exclude') === '0') localStorage.removeItem('pw_exclude');
      if (localStorage.getItem('pw_exclude') === '1') return;
    } catch (e) { /* storage blocked: the visit is counted normally */ }
    var ua = navigator.userAgent || '';
    if (navigator.webdriver || /bot|crawler|spider|preview|headless|lighthouse|facebookexternalhit|facebot|whatsapp[/]|slurp|yandex|python-requests|curl[/]|wget[/]/i.test(ua)) return;

    var store = {};
    function get(k) { try { return sessionStorage.getItem(k); } catch (e) { return store[k] || null; } }
    function set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { store[k] = v; } }
    function clean(v, re, max) { return String(v || '').toLowerCase().replace(re, '').slice(0, max); }
    function uuid() {
      var c = window.crypto || window.msCrypto;
      if (c && c.randomUUID) return c.randomUUID();
      var b = new Uint8Array(16); c.getRandomValues(b); b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
      var h = Array.prototype.map.call(b, function (x) { return (x + 256).toString(16).slice(1); }).join('');
      return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
    }

    var sid = get('pw_sid');
    if (!sid) { sid = uuid(); set('pw_sid', sid); }

    // Where the visit came from, reduced to the server's fixed list: direct, facebook, instagram, telegram, google, other.
    var source = get('pw_src'), campaign = get('pw_cmp'), creative = get('pw_crv'), paid = get('pw_paid');
    if (source === null) {
      var name = clean(q.get('utm_source'), /[^a-z0-9_-]/g, 32);
      campaign = clean(q.get('utm_campaign'), /[^a-z0-9_.-]/g, 48);
      creative = clean(q.get('utm_content'), /[^a-z0-9_.-]/g, 48);
      paid = campaign && /^(paid|cpc|ads?|paid_social|paidsocial)$/.test(clean(q.get('utm_medium'), /[^a-z_]/g, 20)) ? '1' : '';
      var host = '';
      if (document.referrer) { try { host = new URL(document.referrer).hostname.toLowerCase(); } catch (e) { host = ''; } }
      if (host === location.hostname) host = '';
      var probe = name || host;
      source = !probe ? 'direct'
        : /(^|\.)(facebook|fb)\.(com|me)$|^fb$|^facebook$/.test(probe) ? 'facebook'
        : /instagram/.test(probe) ? 'instagram'
        : /(^|\.)(t\.me|telegram\.org|telegram\.me)$|^telegram$/.test(probe) ? 'telegram'
        : /(^|\.)(google|bing)\.|^google$|^bing$/.test(probe) ? 'google' : 'other';
      set('pw_src', source); set('pw_cmp', campaign); set('pw_crv', creative); set('pw_paid', paid);
    }

    var w = window.innerWidth || 0;
    var viewport = w < 768 ? 'mobile' : w < 1100 ? 'tablet' : 'desktop';
    var browserKind = /FBAN|FBAV|FB_IAB|FBIOS/.test(ua) ? 'facebook_in_app' : /Instagram/.test(ua) ? 'instagram_in_app' : 'other';
    var PAGE = { sales_view: 'sales', checkout_view: 'checkout', payment_view: 'checkout', proof_view: 'checkout', telegram_open: 'checkout' };

    var queue = Promise.resolve();
    function post(body) {
      return fetch(endpoint, { method: 'POST', mode: 'cors', credentials: 'omit', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    }
    function send(event) {
      if (get('pw_ev_' + event) || !PAGE[event]) return;
      set('pw_ev_' + event, '1');
      var body = { event_id: uuid(), session_id: sid, event: event, page: PAGE[event], source: source, campaign: campaign || '', creative: creative || '',
                   viewport: viewport, browser_kind: browserKind, paid_traffic: Boolean(paid && campaign) };
      // Events go one after another so the funnel stays in order. A campaign the server does not know (422) is retried without it.
      queue = queue.then(function () {
        return post(body).then(function (r) {
          if (r && r.status === 422 && (body.campaign || body.creative)) {
            body.event_id = uuid(); body.campaign = ''; body.creative = ''; body.paid_traffic = false; return post(body);
          }
        });
      }).catch(function () {});
    }

    // A page view counts only when a person is present: 2 seconds visible, or the first scroll, tap or key press.
    var viewEvent = /order(\.html)?$/.test(location.pathname) ? 'checkout_view' : /\/policies\//.test(location.pathname) ? null : 'sales_view';
    var counted = false, remaining = 2000, started = 0, timer = null;
    function count() {
      if (counted) return;
      counted = true; clearTimeout(timer);
      ['scroll', 'pointerdown', 'keydown', 'touchstart'].forEach(function (n) { window.removeEventListener(n, count, true); });
      if (viewEvent) send(viewEvent);
    }
    function startTimer() { if (counted || document.hidden) return; started = Date.now(); timer = setTimeout(count, remaining); }
    function pauseTimer() { if (timer) { clearTimeout(timer); timer = null; remaining = Math.max(0, remaining - (Date.now() - started)); } }
    ['scroll', 'pointerdown', 'keydown', 'touchstart'].forEach(function (n) { window.addEventListener(n, count, { capture: true, passive: true }); });
    document.addEventListener('visibilitychange', function () { if (document.hidden) pauseTimer(); else startTimer(); });
    startTimer();

    function onVisible(id, event) {
      var el = document.getElementById(id);
      if (!el) return;
      function check() { if (!el.hidden && el.offsetParent !== null) { count(); send(event); mo.disconnect(); } }
      var mo = new MutationObserver(check);
      mo.observe(el, { attributes: true, attributeFilter: ['hidden', 'class', 'style'] });
      check();
    }
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest && e.target.closest('a[href*="t.me/"]');
      if (a) { count(); send('telegram_open'); }
    }, true);
    if (/order(\.html)?$/.test(location.pathname)) {
      onVisible('payment-section', 'payment_view');
      onVisible('telegram-section', 'proof_view');
    }
  } catch (e) { /* analytics must never break the page */ }
})();
