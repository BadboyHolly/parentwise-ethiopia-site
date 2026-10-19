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
    deliveryVersionLabel: $('qa-delivery-version-label'), deliveryVersion: $('qa-delivery-version'),
    copyId: $('copy-order-id'), copyRecovery: $('copy-recovery'),
    copyFallback: $('recovery-copy-fallback'), privateCode: $('private-recovery-code'),
    hidePrivate: $('hide-private-recovery'),
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
      throw new Error('ይህ አሳሽ ደህንነቱ የተጠበቀ የሙከራ ትዕዛዝ መፍጠርን አይደግፍም። የተዘመነ አሳሽ ይጠቀሙ።');
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
    elements.submit.textContent = label || (value ? 'በደህና እየተሠራ ነው…' : 'የሙከራ ትዕዛዝ ፍጠር — ክፍያ የለም');
    elements.recoverSubmit.textContent = value ? 'እየተፈተሸ ነው…' : 'የሙከራ ትዕዛዝን መልስ';
    form.setAttribute('aria-busy', String(value));
  }
  function validate() {
    const name = elements.name.value.trim();
    const mobile = elements.mobile.value.trim();
    const payment = elements.method.value;
    elements.name.setCustomValidity('');
    elements.mobile.setCustomValidity('');
    if (name.length < 2 || name.length > 100 || !/[\p{L}]/u.test(name) || /[\x00-\x1f\x7f]/.test(name)) {
      elements.name.setCustomValidity('ለሙከራ የተፈጠረ ስም ያስገቡ (ከ2 እስከ 100 ቁምፊዎች)።');
      elements.name.reportValidity(); return null;
    }
    if (!/^(?:0[97][0-9]{8}|\+251[97][0-9]{8})$/.test(mobile)) {
      elements.mobile.setCustomValidity('ትክክለኛ ቅርጽ ይጠቀሙ፦ 09XXXXXXXX፣ 07XXXXXXXX ወይም +2519XXXXXXXX። ለሙከራ የተፈጠረ ቁጥር ብቻ ያስገቡ።');
      elements.mobile.reportValidity(); return null;
    }
    if (!payment) { elements.method.setCustomValidity('Telebirr ወይም ባንክ ይምረጡ (ለሙከራ ብቻ)።'); elements.method.reportValidity(); return null; }
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
  // Presentation-only status labels. API status codes remain unchanged.
  const statusLabels = {
    PENDING_PAYMENT: 'ትዕዛዝ ተቀምጧል · ክፍያ የለም (QA)',
    PROOF_SUBMITTED: 'የሙከራ ማስረጃ ገብቷል',
    VERIFYING: 'በማረጋገጥ ላይ (ሙከራ)',
    VERIFIED_PAID: 'በሙከራ ውስጥ ክፍያ ተረጋግጧል (እውነተኛ አይደለም)',
    CANCELLED: 'ተሰርዟል (ሙከራ)',
    PENDING_FULFILLMENT: 'ማድረስ በመጠባበቅ ላይ (ሙከራ)',
    PREPARING: 'በማዘጋጀት ላይ (ሙከራ)',
    SENT: 'ተልኳል (የሙከራ ሁኔታ)',
    DELIVERED: 'ደርሷል (የሙከራ ሁኔታ)',
    DELIVERY_FAILED: 'ማድረስ አልተሳካም (ሙከራ)'
  };
  function statusLabel(code) {
    return statusLabels[code] || code;
  }
  function hidePrivateCode() {
    elements.copyFallback.hidden = true;
    elements.privateCode.value = '';
  }
  function showOrder(summary, token) {
    if (!checkSummary(summary)) throw new Error('ከሙከራ ስርዓቱ ያልተጠበቀ ምላሽ መጥቷል። ትዕዛዙ አልታየም። በዚያው የተቀመጠ ሙከራ እንደገና ይሞክሩ።');
    hidePrivateCode();
    record.order = summary;
    record.token = token;
    saveSession();
    elements.orderId.textContent = summary.order_id;
    elements.orderProduct.textContent = 'የParentWise የልጆች ባህሪና የሥነ-ሥርዓት አስተዳደግ መመሪያ';
    elements.orderPrice.textContent = '1,500 ETB';
    elements.orderMethod.dataset.method = summary.payment_method;
    elements.orderMethod.textContent = summary.payment_method === 'telebirr' ? 'Telebirr · ለሙከራ ብቻ' : 'የኢትዮጵያ ባንክ · ለሙከራ ብቻ';
    elements.orderStatus.dataset.status = summary.status;
    elements.orderStatus.textContent = statusLabel(summary.status);
    const simulated = summary.fulfillment;
    const visible = !!(simulated && simulated.simulated_only === true &&
      ['PENDING_FULFILLMENT','PREPARING','SENT','DELIVERED','DELIVERY_FAILED'].includes(simulated.status));
    elements.deliveryLabel.hidden = !visible;
    elements.deliveryStatus.hidden = !visible;
    elements.deliveryNotice.hidden = !visible;
    elements.deliveryVersionLabel.hidden = !visible;
    elements.deliveryVersion.hidden = !visible;
    if (visible) {
      elements.deliveryStatus.textContent = statusLabel(simulated.status) + ' · ለሙከራ ብቻ';
      elements.deliveryVersion.textContent = simulated.package_version || 'አይገኝም';
      elements.deliveryNotice.textContent =
        'ይህ የሙከራ ማድረስ ማሳያ ብቻ ነው። እውነተኛ የTelegram መልእክት ወይም የተከፈለበት የParentWise ሰነድ አልተላከም። ' +
        'በቀጣይ በእውነተኛ ክፍያ ከተረጋገጠ በኋላ ማድረሱ በኦፊሴላዊ Telegram በሰው ድጋፍ ይከናወናል። ' +
        'ወዲያውኑ ማድረስ አይጠበቅም። ኦፊሴላዊ ድጋፍ፦ t.me/ParentWiseEthiopia።';
    }
    elements.result.hidden = false;
    form.hidden = true;
    feedback('ይህ የQA ሙከራ ብቻ ነው። የሚታየው ሁኔታ ምንም ይሁን ምን፣ እውነተኛ ክፍያ አልተጠየቀም፣ አልተቀበለም ወይም አልተረጋገጠም።', 'success');
    elements.result.focus();
  }
  function failMessage(err, context = '') {
    if (err && err.name === 'AbortError') return 'የሙከራ ስርዓቱ ምላሽ እየዘገየ ነው። ትዕዛዙ ተፈጥሮ ሊሆን ይችላል። አዲስ ትዕዛዝ ከመጀመር ይልቅ የተቀመጠውን ሙከራ ብቻ እንደገና ይሞክሩ።';
    return context || 'የሙከራ ስርዓቱ አሁን አይገናኝም። እየተነሳ ሊሆን ይችላል። ትንሽ ቆይተው የተቀመጠውን ሙከራ እንደገና ይሞክሩ።';
  }
  async function createOrder() {
    if (busy) return;
    const body = validate();
    if (!body) return;
    if (record?.order) { showOrder(record.order, record.token); return; }
    if (record && !sameBody(record.body, body)) {
      restoreForm(record.body);
      feedback('የቀድሞ ሙከራ ተቀምጧል። የመጀመሪያው መረጃ ተመልሷል። ድግግሞሽ እንዳይፈጠር በዚያው ይሞክሩ፤ ሌላ ትዕዛዝ ከፈለጉ «አዲስ የሙከራ ትዕዛዝ ጀምር» ይምረጡ።', 'error');
      return;
    }
    if (!record) {
      try { record = { version: 2, key: makeKey(), body }; }
      catch (error) { feedback(error.message, 'error'); return; }
      saveSession(); // Persist BEFORE making a network request.
    }
    setBusy(true, 'ከሙከራ ስርዓቱ ጋር እየተገናኘ ነው…');
    feedback('የተቀመጠው የሙከራ ትዕዛዝ እየተፈጠረ ወይም እየቀጠለ ነው። ነፃ አስተናጋጁ ለመነሳት እስከ አንድ ደቂቃ ሊወስድ ይችላል።');
    try {
      const { response, data } = await apiRequest('/api/v1/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': record.key },
        body: JSON.stringify(record.body)
      });
      if (response.status === 201) {
        if (!data?.access_token || !/^[A-Za-z0-9_-]{43}$/.test(data.access_token)) throw new Error('ከሙከራ ስርዓቱ የተላከው መልስ አልተሟላም። የተቀመጠውን ሙከራ እንደገና ይሞክሩ።');
        showOrder(data.order, data.access_token);
      } else if (response.status === 429) {
        feedback('የጋራ የQA ገደብ ተሞልቷል፦ በ10 ደቂቃ ውስጥ እስከ 12 አዲስ የሙከራ ትዕዛዝ ብቻ ይፈቀዳል። ቆይተው የተቀመጠውን ሙከራ ይድገሙ። የቀድሞ ትዕዛዝ እንደገና መሞከር ሊሠራ ይችላል።', 'error');
      } else if (response.status === 409) {
        feedback('ይህ መረጃ ከመጀመሪያው ጥያቄ የተለየ ነው። የተቀመጠውን ሙከራ እንደገና ይሞክሩ። መረጃውን ለመቀየር አዲስ የሙከራ ትዕዛዝ ይጀምሩ።', 'error');
      } else if (response.status === 422 || response.status === 400) {
        feedback('የሙከራ ስርዓቱ ያስገቡትን መረጃ አልተቀበለም። ስም፣ የኢትዮጵያ ስልክ ቁጥር ቅርጽና የተመረጠ ዘዴ ያረጋግጡ። የቀድሞ ሙከራ ለመቀየር አዲስ ትዕዛዝ ይጀምሩ።', 'error');
      } else if (response.status >= 500) {
        feedback('የሙከራ ትዕዛዝ ማስቀመጫው ለጊዜው አይሠራም። ምንም ክፍያ አልተከፈለም። የተቀመጠውን ሙከራ እንደገና ይሞክሩ።', 'error');
      } else {
        feedback('የQA ስርዓቱ ያልተጠበቀ ምላሽ ሰጥቷል (' + response.status + ')። የተቀመጠውን ሙከራ እንደገና ይሞክሩ።', 'error');
      }
    } catch (error) {
      feedback(failMessage(error, error instanceof Error && /Incomplete|Unexpected/.test(error.message) ? error.message : ''), 'error');
    } finally { setBusy(false); }
  }
  async function retrieve(id, token, silent = false) {
    if (busy) return;
    if (!/^PW-QA-[A-F0-9]{24}$/.test(id) || !/^[A-Za-z0-9_-]{43}$/.test(token)) {
      feedback('ትክክለኛ የQA ትዕዛዝ መለያ እና 43 ቁምፊ ያለው የግል መመለሻ ቁልፍ ያስገቡ።', 'error'); return;
    }
    setBusy(true, 'የሙከራ ትዕዛዝ እየተመለሰ ነው…');
    if (!silent) feedback('የሙከራ ትዕዛዝዎ በደህና እየተፈተሸ ነው…');
    try {
      const { response, data } = await apiRequest('/api/v1/orders/' + encodeURIComponent(id), {
        method: 'GET', headers: { Authorization: 'Bearer ' + token }
      });
      if (response.status === 200) {
        if (!data?.order || data.order.order_id !== id) throw new Error('የሙከራ ትዕዛዝ ምላሹ ትክክል አይደለም።');
        if (!record || record.order?.order_id !== id) record = { version: 2, key: makeKey(), body: {}, order: data.order, token };
        showOrder(data.order, token);
        elements.recoveryPanel.hidden = true;
      } else if (response.status === 404) {
        if (silent) { record = null; saveSession(); elements.result.hidden = true; form.hidden = false; }
        feedback('ትዕዛዙ አልተገኘም ወይም የግል ቁልፉ ትክክል አይደለም። ሁለቱንም ያረጋግጡ። የደንበኛ መረጃ አልታየም።', 'error');
      } else {
        feedback('ትዕዛዝ መመለስ ለጊዜው አይቻልም (' + response.status + ')። የግል መመለሻ ኮዱን ያስቀምጡና እንደገና ይሞክሩ።', 'error');
      }
    } catch (error) {
      feedback(failMessage(error), 'error');
    } finally { setBusy(false); }
  }
  async function copy(text, successText, privateCode = false) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('unavailable');
      await navigator.clipboard.writeText(text);
      hidePrivateCode();
      feedback(successText, 'success');
    } catch (_) {
      if (privateCode) {
        elements.privateCode.value = text;
        elements.copyFallback.hidden = false;
        elements.privateCode.focus();
        elements.privateCode.select();
        feedback('ወደ ቅጂ ማስቀመጫ መዳረስ አልተፈቀደም። የግል መመለሻ ኮዱ ከታች ተመርጧል። በእጅ ወደ ደህንነቱ የተጠበቀ ማስታወሻ ይቅዱት፣ ከዚያ «የግል ኮዱን ደብቅ» ይምረጡ። በውይይት፣ በስክሪንሾት ወይም በURL አያጋሩት።', 'error');
      } else {
        feedback('ወደ ቅጂ ማስቀመጫ መዳረስ አልተፈቀደም። የትዕዛዝ መለያውን በእጅ ይምረጡና ይቅዱ፤ ወይም ሌላ አሳሽ ይሞክሩ።', 'error');
      }
    }
  }
  form.addEventListener('submit', (event) => { event.preventDefault(); createOrder(); });
  elements.copyId.addEventListener('click', () => { if (record?.order) copy(record.order.order_id, 'የQA ትዕዛዝ መለያ ተቀድቷል። ይህ የክፍያ ማስረጃ አይደለም።'); });
  elements.copyRecovery.addEventListener('click', () => {
    if (record?.order && record?.token) {
      copy(record.order.order_id + '\n' + record.token,
        'የግል መመለሻ ኮድ ተቀድቷል። በደህና ማስታወሻ ወይም በይለፍ ቃል ማስቀመጫ ያስቀምጡት፤ በይፋዊ ውይይት አያጋሩት። ኮዱን ያለው ሰው የQA ትዕዛዙን ማጠቃለያ ማየት ይችላል።', true);
    }
  });
  elements.hidePrivate.addEventListener('click', () => { hidePrivateCode(); elements.copyRecovery.focus(); });
  elements.newOrder.addEventListener('click', () => {
    if (busy || !window.confirm('አዲስ የሙከራ ትዕዛዝ ይጀምሩ? ይህ በአሳሹ የተቀመጠውን የመመለሻ መረጃ ያጠፋል፣ ነገር ግን ቀደም ሲል የተፈጠረ የQA ትዕዛዝን አይሰርዝም። መጀመሪያ የግል መመለሻ ኮዱን ያስቀምጡ።')) return;
    hidePrivateCode();
    record = null; saveSession(); form.hidden = false; elements.result.hidden = true;
    elements.recoveryPanel.hidden = true; form.reset(); feedback('አዲስ የሙከራ ትዕዛዝ ለመፍጠር ዝግጁ ነው።'); elements.name.focus();
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
    feedback('ገጹን ካደሱ በኋላ የቀድሞ ሙከራዎ ተመልሷል። የዚያኑ ትዕዛዝ እንደገና ለመሞከር «የተቀመጠውን ሙከራ ደግም» ይጫኑ።', 'info');
    elements.submit.textContent = 'የተቀመጠውን ሙከራ ደግም — ክፍያ የለም';
  }
})();