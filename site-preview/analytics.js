/* Disabled until consent wording and operational safeguards are approved. */
(() => {
  'use strict';
  const TRACKING_ENABLED = false;
  const API_ORIGIN = 'https://parentwise-isolated-test.app.aletcloud.com';
  // Public identifiers only. Match these to the backend allowlists before activation.
  const CAMPAIGNS = ['pw-parenting-01'];
  const CREATIVES = ['pw-video-01', 'pw-image-01'];
  const EVENTS = {sales_view:'sales', buy_click:'sales', checkout_view:'checkout',
    details_completed:'checkout', payment_view:'checkout', paid_clicked:'checkout',
    proof_view:'checkout', telegram_open:'checkout'};
  let sessionId, denied = false;
  function permitted() {
    try { return TRACKING_ENABLED && !denied && sessionStorage.getItem('pw-analytics-consent') === 'yes'; }
    catch { return false; }
  }
  function session() {
    if (!permitted() || !crypto.randomUUID) return '';
    try {
      if (!sessionId) {
        sessionId = sessionStorage.getItem('pw-analytics-session') || crypto.randomUUID();
        sessionStorage.setItem('pw-analytics-session', sessionId);
      }
      return sessionId;
    } catch { return ''; }
  }
  function track(event) {
    try {
      const id = session();
      if (!id || !EVENTS[event]) return;
      let attribution;
      try { attribution = JSON.parse(sessionStorage.getItem('pw-analytics-attribution') || 'null'); } catch {}
      if (!attribution) {
        const params = new URLSearchParams(location.search);
        const source = (params.get('utm_source') || '').toLowerCase();
        const medium = (params.get('utm_medium') || '').toLowerCase();
        const campaign = params.get('utm_campaign') || '';
        const creative = params.get('utm_content') || '';
        attribution = {
          source: ['direct','facebook','instagram','telegram','google'].includes(source) ? source : 'other',
          campaign: CAMPAIGNS.includes(campaign) ? campaign : '',
          creative: CREATIVES.includes(creative) ? creative : '',
          paid_traffic: CAMPAIGNS.includes(campaign) && ['paid','cpc','paid_social'].includes(medium)
        };
        sessionStorage.setItem('pw-analytics-attribution', JSON.stringify(attribution));
      }
      const width = window.innerWidth;
      const payload = {event_id:crypto.randomUUID(), session_id:id, event,
        page:EVENTS[event], ...attribution,
        viewport:width < 768 ? 'mobile' : width < 1024 ? 'tablet' : 'desktop',
        browser_kind:'unknown'};
      fetch(API_ORIGIN + '/api/v1/analytics/events', {method:'POST', mode:'cors',
        credentials:'omit', cache:'no-store', keepalive:true,
        headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).catch(() => {});
    } catch { /* Analytics must never interrupt checkout. */ }
  }
  window.parentwiseAnalytics = {track, session};
  const page = location.pathname.endsWith('/order.html') ? 'checkout' : 'sales';
  const viewEvent = page === 'sales' ? 'sales_view' : 'checkout_view';
  track(viewEvent);
  if (page === 'sales') document.addEventListener('click', e => {
    if (e.target.closest('a[href="order.html"]')) track('buy_click');
  });
  // Consent prompt removed by founder request. Keep analytics disabled until a privacy approach is reviewed.
})();
