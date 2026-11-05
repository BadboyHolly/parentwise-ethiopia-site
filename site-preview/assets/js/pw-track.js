/* ParentWise first-party visit counter.
   Sends only: a random per-tab id, one of five fixed event names, a coarse source and campaign
   label, a coarse device class and a coarse in-app-browser class. No cookies, no IP, no user agent,
   no names, phone numbers, order codes or payment details are read or sent.
   Dormant unless <meta name="pw-events-endpoint" content="https://.../api/v1/events"> is present.
   Respects Do Not Track and Global Privacy Control. Read-only: never touches the order or payment code. */
(function () {
  'use strict';
  try {
    var meta = document.querySelector('meta[name="pw-events-endpoint"]');
    var endpoint = meta && meta.content;
    if (!endpoint || !/^https:\/\//.test(endpoint)) return;
    if (navigator.doNotTrack === '1' || navigator.globalPrivacyControl === true) return;
    var store = {};
    function get(k) { try { return sessionStorage.getItem(k); } catch (e) { return store[k] || null; } }
    function set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { store[k] = v; } }
    function clean(v, re, max) { v = String(v || '').toLowerCase().replace(re, '').slice(0, max); return v; }

    var sid = get('pw_sid');
    if (!sid) {
      var b = new Uint8Array(32), s = '';
      (window.crypto || window.msCrypto).getRandomValues(b);
      for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
      sid = btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '').slice(0, 43);
      set('pw_sid', sid);
    }

    var q = new URLSearchParams(location.search);
    var source = get('pw_src'), campaign = get('pw_cmp');
    if (source === null) {
      source = clean(q.get('utm_source'), /[^a-z0-9_-]/g, 32);
      campaign = clean(q.get('utm_campaign'), /[^a-z0-9_.-]/g, 48);
      if (!source && document.referrer) {
        var host = '';
        try { host = new URL(document.referrer).hostname.toLowerCase(); } catch (e) {}
        if (host && host !== location.hostname) {
          source = /(^|\.)(facebook|fb)\.com$|(^|\.)fb\.me$/.test(host) ? 'facebook'
            : /(^|\.)instagram\.com$/.test(host) ? 'instagram'
            : /(^|\.)(t\.me|telegram\.org|telegram\.me)$/.test(host) ? 'telegram'
            : /(^|\.)tiktok\.com$/.test(host) ? 'tiktok'
            : /(^|\.)(google|bing)\./.test(host) ? 'search'
            : /(^|\.)youtube\.com$/.test(host) ? 'youtube' : 'other';
        }
      }
      set('pw_src', source); set('pw_cmp', campaign);
    }

    var w = window.innerWidth || 0;
    var device = w < 768 ? 'mobile' : w < 1100 ? 'tablet' : 'desktop';
    var ua = navigator.userAgent || '';
    var browser = /FBAN|FBAV|FB_IAB|FBIOS/.test(ua) ? 'facebook_in_app'
      : /Instagram/.test(ua) ? 'instagram_in_app'
      : /Telegram/.test(ua) ? 'telegram_in_app'
      : /musical_ly|BytedanceWebview|TikTok/i.test(ua) ? 'tiktok_in_app' : 'other';

    function track(event) {
      if (get('pw_ev_' + event)) return;
      set('pw_ev_' + event, '1');
      try {
        fetch(endpoint, {
          method: 'POST', mode: 'cors', credentials: 'omit', keepalive: true,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sid: sid, event: event, source: event === 'sales_view' ? source : '',
            campaign: event === 'sales_view' ? campaign : '', device: device, browser: browser })
        }).catch(function () {});
      } catch (e) {}
    }

    function onVisible(id, event) {
      var el = document.getElementById(id);
      if (!el) return;
      function check() { if (!el.hidden && el.offsetParent !== null) { track(event); mo.disconnect(); } }
      var mo = new MutationObserver(check);
      mo.observe(el, { attributes: true, attributeFilter: ['hidden', 'class', 'style'] });
      check();
    }

    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest && e.target.closest('a[href*="t.me/"]');
      if (a) track('telegram_open');
    }, true);

    var onCheckout = /order(\.html)?$/.test(location.pathname);
    if (onCheckout) {
      track('checkout_view');
      onVisible('payment-section', 'payment_view');
      onVisible('telegram-section', 'proof_view');
    } else if (!/\/policies\//.test(location.pathname)) {
      track('sales_view');
    }
  } catch (e) { /* analytics must never break the page */ }
})();
