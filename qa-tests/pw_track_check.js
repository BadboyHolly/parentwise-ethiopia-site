// Checks for assets/js/pw-track.js without a browser: node qa-tests/pw_track_check.js
// A small fake page runs the real script. It must match the founder server's collector and count only real visitors.
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('assert');
const code = fs.readFileSync(path.join(__dirname, '..', 'site-preview', 'assets', 'js', 'pw-track.js'), 'utf8');
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const ENDPOINT = 'https://founder.example/api/v1/analytics/events';

function page(opts = {}) {
  const o = Object.assign({ meta: ENDPOINT, url: 'https://site.example/', referrer: '', ua: 'Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile Safari/537.36', dnt: null, webdriver: false, local: {}, status: [] }, opts);
  const sent = [], timers = [], listeners = { window: {}, document: {} }, observers = [];
  const make = (init) => { const s = Object.assign({}, init); return { getItem: (k) => (k in s ? s[k] : null), setItem: (k, v) => { s[k] = String(v); }, removeItem: (k) => { delete s[k]; }, _s: s }; };
  const local = make(o.local), session = make({});
  const u = new URL(o.url);
  const els = {};
  (o.elements || []).forEach((id) => { els[id] = { hidden: true, offsetParent: null }; });
  const sandbox = {
    URL, URLSearchParams, Promise, console, Date, Uint8Array, JSON, Array, String, Boolean,
    navigator: { userAgent: o.ua, doNotTrack: o.dnt, webdriver: o.webdriver, globalPrivacyControl: false },
    localStorage: local, sessionStorage: session,
    location: { pathname: u.pathname, search: u.search, hostname: u.hostname },
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; }, clearTimeout: (id) => { if (timers[id - 1]) timers[id - 1].fn = null; },
    fetch: (url, init) => { const body = JSON.parse(init.body); const status = o.status.length ? o.status.shift() : 204; sent.push({ url, body, init }); return Promise.resolve({ status }); },
    MutationObserver: function (cb) { this.observe = () => observers.push(cb); this.disconnect = () => {}; },
    window: null, document: null
  };
  sandbox.window = { innerWidth: 390, crypto: { randomUUID: () => 'xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx'.replace(/x/g, () => Math.floor(Math.random() * 16).toString(16)) },
    addEventListener: (n, f) => { listeners.window[n] = f; }, removeEventListener: (n) => { delete listeners.window[n]; } };
  sandbox.document = { hidden: false, referrer: o.referrer, querySelector: (sel) => (sel === 'meta[name="pw-events-endpoint"]' && o.meta ? { content: o.meta } : null),
    getElementById: (id) => els[id] || null, addEventListener: (n, f) => { listeners.document[n] = f; } };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);
  return { sent, timers, listeners, local, session, els, observers,
    wait: async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setImmediate(r)); },
    runTimers: () => { timers.splice(0).forEach((t) => t.fn && t.fn()); } };
}
const settle = async (p) => { await p.wait(); return p; };
let n = 0;
async function check(name, fn) { await fn(); n++; console.log('ok  ' + name); }

(async () => {
  await check('does nothing without the endpoint tag', async () => {
    const p = page({ meta: '' }); p.runTimers(); await p.wait(); assert.strictEqual(p.sent.length, 0); assert.strictEqual(p.timers.length, 0);
  });
  await check('does nothing for an insecure endpoint, Do Not Track, bots and automation', async () => {
    for (const o of [{ meta: 'http://founder.example/x' }, { dnt: '1' }, { ua: 'TelegramBot (like TwitterBot)' }, { ua: 'facebookexternalhit/1.1' }, { ua: 'WhatsApp/2.23' }, { webdriver: true }]) {
      const p = page(o); p.runTimers(); await p.wait(); assert.strictEqual(p.sent.length, 0, JSON.stringify(o));
    }
  });
  await check('a visit is counted only after 2 seconds, never before', async () => {
    const p = page(); await p.wait(); assert.strictEqual(p.sent.length, 0);
    assert.strictEqual(p.timers.length, 1); assert.strictEqual(p.timers[0].ms, 2000);
    p.runTimers(); await p.wait(); assert.strictEqual(p.sent.length, 1); assert.strictEqual(p.sent[0].body.event, 'sales_view');
  });
  await check('a scroll or a tap counts the visit at once, and only once', async () => {
    const p = page(); p.listeners.window.scroll(); p.listeners.window.pointerdown && p.listeners.window.pointerdown(); p.runTimers(); await p.wait();
    assert.strictEqual(p.sent.length, 1);
  });
  await check('the payload matches the server collector exactly', async () => {
    const p = page({ url: 'https://site.example/?utm_source=facebook&utm_campaign=Launch_1&utm_content=Video-A&utm_medium=paid' }); p.runTimers(); await p.wait();
    const b = p.sent[0].body;
    assert.deepStrictEqual(Object.keys(b).sort(), ['browser_kind', 'campaign', 'creative', 'event', 'event_id', 'page', 'paid_traffic', 'session_id', 'source', 'viewport']);
    assert.match(b.event_id, UUID); assert.match(b.session_id, UUID);
    assert.deepStrictEqual([b.event, b.page, b.source, b.campaign, b.creative, b.paid_traffic, b.viewport, b.browser_kind], ['sales_view', 'sales', 'facebook', 'launch_1', 'video-a', true, 'mobile', 'other']);
    assert.strictEqual(p.sent[0].url, ENDPOINT); assert.strictEqual(p.sent[0].init.credentials, 'omit');
    assert.ok(!/(customer|phone|mobile|order|payment|name)/i.test(JSON.stringify(Object.keys(b))));   // no personal or payment field exists in the payload
  });
  await check('sources are reduced to the fixed list', async () => {
    const cases = [['', 'direct'], ['https://t.me/ParentWiseEthiopia', 'telegram'], ['https://l.facebook.com/l.php', 'facebook'], ['https://www.instagram.com/', 'instagram'], ['https://www.google.com/', 'google'], ['https://www.tiktok.com/', 'other'], ['https://site.example/', 'direct']];
    for (const [ref, want] of cases) { const p = page({ referrer: ref }); p.runTimers(); await p.wait(); assert.strictEqual(p.sent[0].body.source, want, ref); }
  });
  await check('an unconfigured campaign (422) is retried once without it, so the visit is not lost', async () => {
    const p = page({ url: 'https://site.example/?utm_source=facebook&utm_campaign=typo&utm_medium=paid', status: [422, 204] }); p.runTimers(); await p.wait();
    assert.strictEqual(p.sent.length, 2); assert.strictEqual(p.sent[1].body.campaign, ''); assert.strictEqual(p.sent[1].body.paid_traffic, false); assert.notStrictEqual(p.sent[0].body.event_id, p.sent[1].body.event_id);
  });
  await check('the exclude link keeps this device out, until switched off', async () => {
    const p = page({ url: 'https://site.example/?pw_exclude=1' }); p.runTimers(); await p.wait();
    assert.strictEqual(p.sent.length, 0); assert.strictEqual(p.local.getItem('pw_exclude'), '1');
    const later = page({ local: { pw_exclude: '1' } }); later.runTimers(); await later.wait(); assert.strictEqual(later.sent.length, 0);
    const back = page({ url: 'https://site.example/?pw_exclude=0', local: { pw_exclude: '1' } }); back.runTimers(); await back.wait();
    assert.strictEqual(back.sent.length, 1); assert.strictEqual(back.local.getItem('pw_exclude'), null);
  });
  await check('the checkout counts the visit first, then payment and proof steps in order', async () => {
    const p = page({ url: 'https://site.example/order.html', elements: ['payment-section', 'telegram-section'] });
    p.els['payment-section'].hidden = false; p.els['payment-section'].offsetParent = {}; p.observers.forEach((cb) => cb()); await p.wait();
    p.els['telegram-section'].hidden = false; p.els['telegram-section'].offsetParent = {}; p.observers.forEach((cb) => cb()); await p.wait();
    assert.deepStrictEqual(p.sent.map((s) => s.body.event), ['checkout_view', 'payment_view', 'proof_view']);
    assert.ok(p.sent.every((s) => s.body.page === 'checkout'));
  });
  await check('policy pages count nothing; opening Telegram counts once', async () => {
    const policy = page({ url: 'https://site.example/policies/privacy-policy.html' }); policy.runTimers(); await policy.wait(); assert.strictEqual(policy.sent.length, 0);
    const p = page(); const link = { closest: () => ({}) };
    p.listeners.document.click({ target: link }); p.listeners.document.click({ target: link }); await p.wait();
    assert.deepStrictEqual(p.sent.map((s) => s.body.event), ['sales_view', 'telegram_open']);
  });
  console.log('\nall ' + n + ' tracker checks passed');
})().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
