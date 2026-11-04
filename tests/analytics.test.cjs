const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const script = fs.readFileSync('site-preview/analytics.js', 'utf8');
function run({enabled, consent, query = '', store = new Map(), path = '/index.html'}) {
  if (consent) store.set('pw-analytics-consent', 'yes');
  const sent = [], listeners = {};
  const context = {crypto, URLSearchParams, location:{pathname:path, search:query}, window:{innerWidth:390},
    sessionStorage:{getItem:k => store.get(k) || null, setItem:(k,v) => store.set(k,v)},
    document:{addEventListener:(name,handler) => {listeners[name]=handler;}},
    fetch:(url,options) => {sent.push(JSON.parse(options.body));return Promise.resolve();}};
  const source = script.replace('const TRACKING_ENABLED = false;', `const TRACKING_ENABLED = ${enabled};`)
    .replace("const CAMPAIGNS = ['pw-parenting-01'];", "const CAMPAIGNS = ['synthetic-campaign'];")
    .replace("const CREATIVES = ['pw-video-01', 'pw-image-01'];", "const CREATIVES = ['synthetic-creative'];");
  vm.runInNewContext(source, context);
  return {sent, store, listeners, api:context.window.parentwiseAnalytics};
}
assert.equal(run({enabled:false,consent:true}).sent.length, 0);
assert.equal(run({enabled:true,consent:false}).sent.length, 0);
const first=run({enabled:true,consent:true,query:'?utm_source=facebook&utm_medium=cpc&utm_campaign=synthetic-campaign&utm_content=synthetic-creative'});
assert.equal(first.sent[0].event,'sales_view');
assert.equal(first.sent[0].source,'facebook');
assert.equal(first.sent[0].campaign,'synthetic-campaign');
assert.equal(first.sent[0].creative,'synthetic-creative');
assert.equal(first.sent[0].paid_traffic,true);
first.listeners.click({target:{closest:() => ({})}});
assert.equal(first.sent[1].event,'buy_click');
const checkout=run({enabled:true,consent:true,store:first.store,path:'/order.html',query:'?utm_source=google'});
assert.equal(checkout.sent[0].event,'checkout_view');
assert.equal(checkout.sent[0].session_id,first.sent[0].session_id);
assert.equal(checkout.sent[0].source,'facebook');
for (const event of ['details_completed','payment_view','paid_clicked','proof_view','telegram_open']) checkout.api.track(event);
assert.deepEqual(checkout.sent.map(x=>x.event),['checkout_view','details_completed','payment_view','paid_clicked','proof_view','telegram_open']);
const unknown=run({enabled:true,consent:true,query:'?utm_source=private-value&utm_campaign=private-value&utm_content=private-value'}).sent[0];
assert.equal(unknown.source,'other');assert.equal(unknown.campaign,'');assert.equal(unknown.creative,'');assert.equal(unknown.paid_traffic,false);
assert(!JSON.stringify(unknown).includes('private-value'));
console.log('PASS: disabled and consent gates, allowlisted attribution, first touch, funnel events, and unknown-value privacy');
