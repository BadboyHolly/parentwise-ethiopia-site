/* Isolated ParentWise checkout prototype. QA-only fixtures; no real payment integration. */
(() => {
  'use strict';
  const API = 'https://parentwise-orders-api-qa.onrender.com';
  const STORAGE = 'parentwise.qa.checkout.v3';
  const $ = id => document.getElementById(id);
  const model = { method: 'telebirr', order: null, token: null, key: null, body: null, attemptMethod: null, busy: false };
  const names = ['A gentle start', 'Understanding big feelings', 'Calm boundaries', 'Everyday routines', 'Growing together'];
  const recipients = {
    telebirr: ['Telebirr QA ID', 'QA-TELEBIRR-RECIPIENT-001'],
    bank: ['CBE QA account', 'QA-CBE-ACCOUNT-001']
  };

  function announce(message, error = false) {
    const box = model.order ? $('feedback') : $('create-feedback'); box.textContent = message; box.classList.toggle('hidden', !message);
    box.classList.toggle('error', error);
  }
  function key() {
    if (!crypto?.getRandomValues) throw new Error('Secure browser support is required. Please update your browser.');
    const b = new Uint8Array(32); crypto.getRandomValues(b);
    return btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  async function request(path, init = {}) {
    const c = new AbortController(), timer = setTimeout(() => c.abort(), 90000);
    try {
      const response = await fetch(API + path, { ...init, signal: c.signal, cache: 'no-store', referrerPolicy: 'no-referrer' });
      const data = response.headers.get('content-type')?.includes('json') ? await response.json() : null;
      return { response, data };
    } finally { clearTimeout(timer); }
  }
  function headers(json = false) {
    const h = { Authorization: 'Bearer ' + model.token };
    if (json) h['Content-Type'] = 'application/json';
    return h;
  }
  function save() {
    try { sessionStorage.setItem(STORAGE, JSON.stringify({ order: model.order, token: model.token, key: model.key, body: model.body, attemptMethod: model.attemptMethod })); }
    catch (_) { announce('Browser session storage is unavailable. Copy your private recovery code before leaving this tab.', true); }
  }
  function syncMethod(method) {
    if (!Object.hasOwn(recipients, method)) throw new Error('Unexpected payment method in QA order.');
    model.method = method;
    document.querySelectorAll('.method').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.method === method));
      button.disabled = Boolean(model.order || model.attemptMethod);
    });
    const [label, value] = recipients[method];
    $('recipient-label').textContent = label;
    $('recipient-value').textContent = value;
  }
  function display(summary) {
    if (!summary || !/^PW-QA-[A-F0-9]{24}$/.test(summary.order_id) || summary.amount_etb !== 1500 || summary.test_mode !== true) {
      throw new Error('Unexpected QA response. Refresh using your saved recovery code.');
    }
    if (!Object.hasOwn(recipients, summary.payment_method)) throw new Error('Unexpected payment method in QA order.');
    model.order = summary; model.attemptMethod = null; syncMethod(summary.payment_method); save();
    $('order-panel').classList.remove('hidden');
    $('order-id').textContent = summary.order_id;
    $('order-method').textContent = summary.payment_method === 'telebirr' ? 'Telebirr · QA simulation' : 'CBE · QA simulation';
    $('customer-status').textContent = summary.customer_status || 'Awaiting Payment';
    const status = summary.customer_status || 'Awaiting Payment';
    document.querySelectorAll('.steps span').forEach((step, i) => step.classList.toggle('on',
      i === 0 ? status === 'Awaiting Payment' : i === 1 ? status === 'Under Review' : ['Payment Confirmed', 'Ready to Download'].includes(status)));
    $('status-message').textContent = status === 'Awaiting Payment' ? 'Create a fictional transfer reference, then submit it as a claim.' :
      status === 'Under Review' ? 'Your reference is with the founder for independent QA review. A submitted reference is not payment confirmation.' :
      status === 'Payment Confirmed' ? 'The simulated review is complete. QA sample access is temporarily unavailable.' :
      status === 'Ready to Download' ? 'Your simulated approval is complete. Download the five QA samples below.' :
      'This QA order is closed. Contact support if you need help recovering your test order.';
    $('payment-claim').classList.toggle('hidden', summary.status !== 'PENDING_PAYMENT');
    $('payment-instructions').classList.toggle('hidden', summary.status !== 'PENDING_PAYMENT');
    $('download-area').classList.toggle('hidden', !summary.downloads_ready);
    if (summary.downloads_ready) renderDownloads();
    if (summary.status === 'PROOF_SUBMITTED' || summary.status === 'VERIFYING') announce('Reference received. It is a claim only and is not a payment confirmation.');
    else if (summary.status === 'VERIFIED_PAID') announce('QA simulation approved. This does not mean real payment was received.');
  }
  function renderDownloads() {
    const list = $('download-list'); list.replaceChildren();
    names.forEach((name, i) => {
      const button = document.createElement('button'); button.type = 'button';
      button.textContent = `Download QA sample ${i + 1} · ${name}`;
      button.addEventListener('click', () => download(i + 1, button)); list.append(button);
    });
  }
  async function download(n, button) {
    button.disabled = true; button.textContent = `Preparing QA sample ${n}…`;
    try {
      const res = await fetch(`${API}/api/v1/orders/${encodeURIComponent(model.order.order_id)}/downloads/part-${n}`, {
        headers: headers(), cache: 'no-store', referrerPolicy: 'no-referrer'
      });
      if (!res.ok) throw new Error(res.status === 403 ? 'Access is unavailable or was revoked. Contact QA support.' : 'Download failed. Check your connection and retry.');
      const blob = await res.blob(), url = URL.createObjectURL(blob), a = document.createElement('a');
      a.href = url; a.download = `ParentWise_QA_DEMO_Part_${n}.pdf`; document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 15000); announce(`QA sample ${n} downloaded. It is a fictional demo PDF.`);
    } catch (e) { announce(e.message || 'Download failed. Please retry.', true); }
    finally { button.disabled = false; button.textContent = `Download QA sample ${n} · ${names[n - 1]}`; }
  }
  async function refresh() {
    const { response, data } = await request('/api/v1/orders/' + encodeURIComponent(model.order.order_id) + '/checkout-status', { headers: headers() });
    if (!response.ok) throw new Error(response.status === 404 ? 'Order not found or private recovery code is incorrect.' : 'Order status is temporarily unavailable. Try again.');
    display(data.order);
  }
  async function create() {
    if (model.busy) return;
    model.busy = true; $('create-order').disabled = true; $('create-order').textContent = 'Creating QA order…';
    try {
      if (!model.key) {
        model.key = key();
        model.attemptMethod = model.method;
        // Backend contract retained with synthetic values only; no customer PII is requested.
        model.body = { customer_name: 'QA Sample Parent', mobile: '0911111111', payment_method: model.attemptMethod };
        syncMethod(model.attemptMethod);
        save();
      }
      // An interrupted request is ambiguous: retry its original method and key so it cannot
      // create a second order or silently submit the previously saved body under a new choice.
      if (!model.attemptMethod || model.body?.payment_method !== model.attemptMethod || model.method !== model.attemptMethod) {
        throw new Error('This QA order attempt is still being checked. Retry using its original payment method.');
      }
      const { response, data } = await request('/api/v1/orders', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': model.key }, body: JSON.stringify(model.body) });
      if (!response.ok) throw new Error(response.status === 429 ? 'Shared QA order limit reached. Wait briefly and retry this same attempt.' : 'Could not create the QA order. Please retry the same attempt.');
      if (!/^[A-Za-z0-9_-]{43}$/.test(data.access_token || '')) throw new Error('The QA API returned an incomplete recovery code. Retry the saved attempt.');
      model.token = data.access_token; display({ ...data.order, customer_status: 'Awaiting Payment', downloads_ready: false });
      refresh().catch(e => announce(e.message, true)); announce('QA order created. No money was requested or taken.');
      $('order-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      const message = model.key && !model.order
        ? 'We could not confirm whether this QA order was created. Retry with this same payment method to check the existing attempt safely.'
        : e.message || 'The QA service is unavailable. Please retry.';
      announce(message, true);
    }
    finally { model.busy = false; $('create-order').disabled = false; $('create-order').textContent = model.key && !model.order ? 'Retry QA order' : 'Create QA order'; }
  }
  async function simulateTransfer() {
    try {
      const { response, data } = await request(`/api/v1/orders/${encodeURIComponent(model.order.order_id)}/simulate-transfer`, { method: 'POST', headers: headers() });
      if (!response.ok) throw new Error('Could not create a fictional QA reference. Try again.');
      $('reference').value = data.reference; announce('Fictional reference generated. No transfer occurred. You can edit or copy this QA reference.');
    } catch (e) { announce(e.message || 'The QA service is unavailable.', true); }
  }
  async function submitClaim() {
    const ref = $('reference').value.trim().toUpperCase();
    if (!/^QA-(TB|BK)-[A-F0-9]{16}$/.test(ref)) { announce('Enter a fictional QA reference in the format shown. Do not enter a real transaction reference.', true); return; }
    try {
      const { response, data } = await request(`/api/v1/orders/${encodeURIComponent(model.order.order_id)}/payment-claim`, {
        method: 'POST', headers: headers(true), body: JSON.stringify({ test_reference: ref, reported_amount_etb: 1500, currency: 'ETB' })
      });
      if (!response.ok) throw new Error(response.status === 409 ? 'This reference is already claimed. Generate a new QA reference.' : 'Could not submit the QA claim. Check the reference and retry.');
      announce('Claim submitted for founder review. The reference alone is not payment confirmation.'); await refresh();
    } catch (e) { announce(e.message || 'The QA service is unavailable.', true); }
  }
  async function recover() {
    const raw = $('recovery-code').value.trim();
    const match = raw.match(/(PW-QA-[A-F0-9]{24})\s+([A-Za-z0-9_-]{43})/);
    if (!match) { announce('Paste both the Order ID and private token from your saved recovery code.', true); return; }
    model.order = { order_id: match[1] }; model.token = match[2];
    try { await refresh(); save(); $('recovery-code').value = ''; $('order-recovery').open = false; announce('QA order recovered securely.'); }
    catch (e) { $('recovery-code').value = ''; announce(e.message, true); model.order = null; model.token = null; }
  }
  async function copy(value, label, privateCode = false) {
    try { await navigator.clipboard.writeText(value); announce(`${label} copied.`); }
    catch (_) {
      if (privateCode) {
        const fallback = $('private-code-fallback'), field = $('private-recovery-code');
        field.value = value; fallback.classList.remove('hidden');
        field.focus(); field.select(); field.setSelectionRange(0, field.value.length);
        announce('Clipboard access was denied. Your complete private recovery code is selected below. Save it securely, then hide it.', true);
        fallback.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else announce('Clipboard access was denied. Select the value and copy it manually.', true);
    }
  }
  document.querySelectorAll('.method').forEach(button => button.addEventListener('click', () => {
    if (model.order) return;
    if (model.attemptMethod) {
      syncMethod(model.attemptMethod);
      announce('This QA order attempt may still be processing. Retry the same payment method to avoid creating a duplicate order.', true);
      return;
    }
    syncMethod(button.dataset.method);
  }));
  $('copy-recipient').addEventListener('click', () => copy($('recipient-value').textContent, 'Fictional QA recipient'));
  $('copy-amount').addEventListener('click', () => copy('1500', 'Amount'));
  $('create-order').addEventListener('click', create);
  $('simulate-transfer').addEventListener('click', simulateTransfer);
  $('submit-claim').addEventListener('click', submitClaim);
  $('copy-order').addEventListener('click', () => model.order && copy(model.order.order_id, 'Order ID'));
  $('copy-recovery').addEventListener('click', () => model.order && model.token && copy(model.order.order_id + '\n' + model.token, 'Private recovery code', true));
  $('hide-private-code').addEventListener('click', () => {
    const field = $('private-recovery-code'); field.value = ''; $('private-code-fallback').classList.add('hidden');
    announce('Private recovery code hidden from the page.'); $('copy-recovery').focus();
  });
  $('refresh-status').addEventListener('click', () => refresh().then(() => announce('Order status refreshed securely.')).catch(e => announce(e.message, true)));
  $('recover').addEventListener('click', recover);
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE) || 'null');
    if (saved?.token && saved?.order?.order_id) {
      model.order = saved.order; model.token = saved.token; model.key = saved.key; model.body = saved.body;
      if (Object.hasOwn(recipients, saved.order.payment_method)) syncMethod(saved.order.payment_method);
      refresh().catch(e => announce(e.message, true));
    }
    else if (saved?.key) {
      model.key = saved.key; model.body = saved.body;
      model.attemptMethod = saved.attemptMethod || saved.body?.payment_method || null;
      if (Object.hasOwn(recipients, model.attemptMethod)) syncMethod(model.attemptMethod);
      $('create-order').textContent = 'Retry QA order';
    }
  } catch (_) { announce('No saved tab session is available. Use the private recovery code if you have it.', true); }
})();

