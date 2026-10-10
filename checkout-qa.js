/* ParentWise QA checkout: real test orders, NO REAL PAYMENTS.
   Customer secrets stay in the current tab's sessionStorage, never URLs or analytics.
   Reopen recovery is explicitly opt-in via a user-held private code. */
(() => {
  'use strict';
  const API = 'https://parentwise-orders-api-qa.onrender.com';
  const SESSION_KEY = 'parentwise.qa.checkout.v2';
  const form = document.getElementById('qaOrder');
  if (!form) return;
  const $ = (id) => document.getElementById(id);
  const elements = {
    name: $('name'), mobile: $('mobile'), method: $('payment-method'),
    submit: $('order-submit'), feedback: $('checkout-feedback'),
    result: $('testPreview'), orderId: $('order-id'), orderProduct: $('order-product'),
    orderPrice: $('order-price'), orderMethod: $('order-method'), orderStatus: $('order-status'),
    deliveryLabel: $('qa-delivery-label'), deliveryStatus: $('qa-delivery-status'),
    deliveryNotice: $('qa-fulfillment-notice'),
    copyId: $('copy-order-id'), copyRecovery: $('copy-recovery'),
    newOrder: $('start-new-order'), recoveryPanel: $('recovery-panel'),
    recoverToggle: $('recover-toggle'), recoverForm: $('recover-form'),
    recoverId: $('recover-order-id'), recoverToken: $('recover-token'),
    recoverSubmit: $('recover-submit'), sessionNotice: $('session-storage-notice')
  };
  let record = null;
  let busy = false;
  let storageAvailable = true;
  const timeoutMs = 90000; // Cold starts may take time on free hosting.

  function loadSession() {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data || data.version !== 2 || typeof data.key !== 'string' ||
          !/^[A-Za-z0-9_-]{43}$/.test(data.key) || !data.body) return null;
      return data;
    } catch (_) { storageAvailable = false; return null; }
  }
  function saveSession() {
    try {
      if (record) sessionStorage.setItem(SESSION_KEY, JSON.stringify(record));
      else sessionStorage.removeItem(SESSION_KEY);
    } catch (_) { storageAvailable = false; }
    if (!storageAvailable) elements.sessionNotice.hidden = false;
  }
  function makeKey() {
    if (!window.crypto || typeof crypto.getRandomValues !== 'function') {
      throw new Error('Your browser does not support secure order creation. Use an updated browser.');
    }
    const bytes = new Uint8Array(32);
    crypto.getRandomValues(bytes);
    let binary = '';
    bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  function feedback(message, kind = 'info') {
    elements.feedback.hidden = !message;
    elements.feedback.textContent = message || '';
    elements.feedback.dataset.kind = kind;
  }
  function setBusy(value, label) {
    busy = value;
    elements.submit.disabled = value;
    elements.recoverSubmit.disabled = value;
    elements.submit.textContent = label || (value ? 'Working securely…' : 'Create TEST order — no payment');
    elements.recoverSubmit.textContent = value ? 'Checking…' : 'Recover QA order';
    form.setAttribute('aria-busy', String(value));
  }
  function validate() {
    const name = elements.name.value.trim();
    const mobile = elements.mobile.value.trim();
    const payment = elements.method.value;
    elements.name.setCustomValidity('');
    elements.mobile.setCustomValidity('');
    if (name.length < 2 || name.length > 100 || !/[\p{L}]/u.test(name) || /[\x00-\x1f\x7f]/.test(name)) {
      elements.name.setCustomValidity('Enter a fictional test name (2–100 characters).');
      elements.name.reportValidity(); return null;
    }
    if (!/^(?:0[97][0-9]{8}|\+251[97][0-9]{8})$/.test(mobile)) {
      elements.mobile.setCustomValidity('Use a valid format: 09XXXXXXXX, 07XXXXXXXX or +2519XXXXXXXX. Test data only.');
      elements.mobile.reportValidity(); return null;
    }
    if (!payment) { elements.method.setCustomValidity('Choose Telebirr or bank (simulation only).'); elements.method.reportValidity(); return null; }
    elements.method.setCustomValidity('');
    return { customer_name: name, mobile, payment_method: payment };
  }
  function sameBody(a, b) {
    // API normalizes phone numbers, so after reload use saved exact body rather than recomputing.
    return !!a && !!b && a.customer_name === b.customer_name && a.mobile === b.mobile && a.payment_method === b.payment_method;
  }
  function restoreForm(data) {
    if (!data) return;
    elements.name.value = data.customer_name || '';
    elements.mobile.value = data.mobile || '';
    elements.method.value = data.payment_method || '';
  }
  function clearInvalid() { this.setCustomValidity(''); }
  elements.name.addEventListener('input', clearInvalid);
  elements.mobile.addEventListener('input', clearInvalid);
  elements.method.addEventListener('change', clearInvalid);

  async function apiRequest(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(API + path, {
        ...options,
        signal: controller.signal,
        cache: 'no-store',
        referrerPolicy: 'no-referrer'
      });
      let data;
      try { data = await response.json(); } catch (_) { data = null; }
      return { response, data };
    } finally { clearTimeout(timer); }
  }
  function checkSummary(summary) {
    return summary && typeof summary.order_id === 'string' && /^PW-QA-[A-F0-9]{24}$/.test(summary.order_id) &&
      summary.amount_etb === 1500 && summary.currency === 'ETB' &&
      ['bank', 'telebirr'].includes(summary.payment_method) &&
      ['PENDING_PAYMENT','PROOF_SUBMITTED','VERIFYING','VERIFIED_PAID','CANCELLED'].includes(summary.status) && summary.test_mode === true &&
      summary.product === 'ParentWise Child Behavior & Discipline System';
  }
  function showOrder(summary, token) {
    if (!checkSummary(summary)) throw new Error('Unexpected API response. The test order was not displayed. Retry with the same attempt.');
    record.order = summary;
    record.token = token;
    saveSession();
    elements.orderId.textContent = summary.order_id;
    elements.orderProduct.textContent = summary.product;
    elements.orderPrice.textContent = '1,500 ETB';
    elements.orderMethod.textContent = summary.payment_method === 'telebirr' ? 'Telebirr · simulation only' : 'Ethiopian bank · simulation only';
    elements.orderStatus.textContent = summary.status;
    const simulated = summary.fulfillment;
    const visible = !!(simulated && simulated.simulated_only === true &&
      ['PENDING_FULFILLMENT','PREPARING','SENT','DELIVERED','DELIVERY_FAILED'].includes(simulated.status));
    elements.deliveryLabel.hidden = !visible;
    elements.deliveryStatus.hidden = !visible;
    elements.deliveryNotice.hidden = !visible;
    if (visible) {
      elements.deliveryStatus.textContent = simulated.status + ' · SIMULATION ONLY';
      elements.deliveryNotice.textContent =
        'QA DUMMY FULFILLMENT ONLY. No actual Telegram message or paid ParentWise document was sent. ' +
        'Production fulfillment will be founder-assisted through official Telegram after independently confirmed real payment. ' +
        'No instant delivery is promised. Official support: t.me/ParentWiseEthiopia.';
    }
    elements.result.hidden = false;
    form.hidden = true;
    feedback('This is a QA simulation only. No real payment has been requested, received, or verified, regardless of the displayed test status.', 'success');
    elements.result.focus();
  }
  function failMessage(err, context = '') {
    if (err && err.name === 'AbortError') return 'The API is taking longer than expected. The order may already exist. Retry the SAME saved attempt; do not start a new one.';
    return context || 'Cannot reach the QA API right now. It may be waking from sleep. Wait a moment and retry the SAME attempt.';
  }
  async function createOrder() {
    if (busy) return;
    const body = validate();
    if (!body) return;
    if (record?.order) { showOrder(record.order, record.token); return; }
    if (record && !sameBody(record.body, body)) {
      restoreForm(record.body);
      feedback('A test attempt is already saved. Its original details were restored. Retry it to avoid duplicate orders, or choose “Start a new test order” explicitly.', 'error');
      return;
    }
    if (!record) {
      try { record = { version: 2, key: makeKey(), body }; }
      catch (error) { feedback(error.message, 'error'); return; }
      saveSession(); // Persist BEFORE making a network request.
    }
    setBusy(true, 'Contacting QA API…');
    feedback('Creating or resuming the same test order. Free hosting can take up to a minute to wake.');
    try {
      const { response, data } = await apiRequest('/api/v1/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': record.key },
        body: JSON.stringify(record.body)
      });
      if (response.status === 201) {
        if (!data?.access_token || !/^[A-Za-z0-9_-]{43}$/.test(data.access_token)) throw new Error('Incomplete API response. Retry the same attempt.');
        showOrder(data.order, data.access_token);
      } else if (response.status === 429) {
        feedback('Shared QA limit reached: at most 12 NEW test orders per 10 minutes across all testers. Wait and retry this SAME attempt. An existing order retry may still succeed.', 'error');
      } else if (response.status === 409) {
        feedback('These details differ from the original request. Retry the original saved attempt. If necessary, explicitly start a new test order.', 'error');
      } else if (response.status === 422 || response.status === 400) {
        feedback('The API rejected these test details. Check the name, Ethiopian phone format and method. To change a previously submitted attempt, explicitly start a new test order.', 'error');
      } else if (response.status >= 500) {
        feedback('Test-order storage is temporarily unavailable. Nothing was charged. Retry the SAME saved attempt.', 'error');
      } else {
        feedback('The QA API returned an unexpected response (' + response.status + '). Retry the SAME saved attempt.', 'error');
      }
    } catch (error) {
      feedback(failMessage(error, error instanceof Error && /Incomplete|Unexpected/.test(error.message) ? error.message : ''), 'error');
    } finally { setBusy(false); }
  }
  async function retrieve(id, token, silent = false) {
    if (busy) return;
    if (!/^PW-QA-[A-F0-9]{24}$/.test(id) || !/^[A-Za-z0-9_-]{43}$/.test(token)) {
      feedback('Enter a valid QA Order ID and its separate 43-character private recovery token.', 'error'); return;
    }
    setBusy(true, 'Retrieving QA order…');
    if (!silent) feedback('Checking your QA order securely…');
    try {
      const { response, data } = await apiRequest('/api/v1/orders/' + encodeURIComponent(id), {
        method: 'GET', headers: { Authorization: 'Bearer ' + token }
      });
      if (response.status === 200) {
        if (!data?.order || data.order.order_id !== id) throw new Error('Invalid API order response');
        if (!record || record.order?.order_id !== id) record = { version: 2, key: makeKey(), body: {}, order: data.order, token };
        showOrder(data.order, token);
        elements.recoveryPanel.hidden = true;
      } else if (response.status === 404) {
        if (silent) { record = null; saveSession(); elements.result.hidden = true; form.hidden = false; }
        feedback('Order not found or the private token is incorrect. Check both values. No customer details were exposed.', 'error');
      } else {
        feedback('Order recovery is temporarily unavailable (' + response.status + '). Keep your private recovery code and try again.', 'error');
      }
    } catch (error) {
      feedback(failMessage(error), 'error');
    } finally { setBusy(false); }
  }
  async function copy(text, successText) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('unavailable');
      await navigator.clipboard.writeText(text);
      feedback(successText, 'success');
    } catch (_) {
      feedback('Clipboard permission was denied. Select and copy the Order ID manually, or try another supported browser.', 'error');
    }
  }
  form.addEventListener('submit', (event) => { event.preventDefault(); createOrder(); });
  elements.copyId.addEventListener('click', () => { if (record?.order) copy(record.order.order_id, 'QA Order ID copied. This is not proof of payment.'); });
  elements.copyRecovery.addEventListener('click', () => {
    if (record?.order && record?.token) {
      copy(record.order.order_id + '\n' + record.token,
        'Private recovery code copied. Store it in a secure note or password manager, not a public chat. Anyone with this code can view the QA order summary.');
    }
  });
  elements.newOrder.addEventListener('click', () => {
    if (busy || !window.confirm('Start a NEW test order? This removes the current session recovery details but does not cancel any previously created QA order. Save its private recovery code first.')) return;
    record = null; saveSession(); form.hidden = false; elements.result.hidden = true;
    elements.recoveryPanel.hidden = true; form.reset(); feedback('Ready for a new fictional test order.'); elements.name.focus();
  });
  elements.recoverToggle.addEventListener('click', () => {
    elements.recoveryPanel.hidden = !elements.recoveryPanel.hidden;
    if (!elements.recoveryPanel.hidden) elements.recoverId.focus();
  });
  elements.recoverForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const id = elements.recoverId.value.trim().toUpperCase();
    let token = elements.recoverToken.value.trim();
    // A copied two-line code can be pasted into either field.
    const pasted = (elements.recoverId.value + '\n' + elements.recoverToken.value).match(/PW-QA-[A-F0-9]{24}\s+([A-Za-z0-9_-]{43})/);
    if (pasted) token = pasted[1];
    const finalId = pasted ? pasted[0].slice(0, 30).trim() : id;
    elements.recoverToken.value = '';
    retrieve(finalId, token);
  });
  // Refresh: the session is scoped to this tab, and no automatic POST is sent.
  record = loadSession();
  if (!storageAvailable) elements.sessionNotice.hidden = false;
  if (record?.order?.order_id && record?.token) {
    // Only GET. It cannot create a second order.
    retrieve(record.order.order_id, record.token, true);
  } else if (record?.key && record.body?.customer_name) {
    restoreForm(record.body);
    feedback('Your previous attempt was restored after refresh. Press “Retry saved test attempt” to safely retry the SAME Order ID request.', 'info');
    elements.submit.textContent = 'Retry saved test attempt — no payment';
  }
})();