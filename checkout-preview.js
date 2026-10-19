/* Isolated design-review preview only. No API calls or real orders. */
(() => {
  'use strict';
  const byId = (id) => document.getElementById(id);
  const form = byId('qaOrder');
  const result = byId('testPreview');
  const feedback = byId('checkout-feedback');
  const showMessage = (message) => {
    feedback.hidden = false;
    feedback.dataset.kind = 'info';
    feedback.textContent = message;
  };
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    showMessage('ይህ የንድፍ ማሳያ ብቻ ነው። ምንም ትዕዛዝ አልተፈጠረም፤ የግል መረጃ ወደ ሰርቨር አልተላከም።');
  });
  const demo = document.createElement('button');
  demo.type = 'button';
  demo.className = 'qa-secondary';
  demo.style.cssText = 'width:100%;margin-top:12px';
  demo.textContent = 'የትዕዛዝ ማረጋገጫ ማሳያን ይመልከቱ';
  form.after(demo);
  demo.addEventListener('click', () => {
    byId('order-id').textContent = 'ማሳያ ብቻ — እውነተኛ መለያ የለም';
    byId('order-product').textContent = 'ParentWise Ethiopia — የወላጆች መመሪያ';
    byId('order-method').textContent = 'Telebirr · ለሙከራ ብቻ';
    byId('order-status').textContent = 'የንድፍ ማሳያ · ክፍያ የለም';
    form.hidden = true;
    demo.hidden = true;
    result.hidden = false;
    byId('copy-order-id').disabled = true;
    byId('copy-recovery').disabled = true;
    showMessage('ይህ ማረጋገጫ ለዕይታ ብቻ ነው። ትዕዛዝ አልተፈጠረም፣ ክፍያ አልተቀበለም።');
    result.focus();
  });
  byId('start-new-order').addEventListener('click', () => {
    result.hidden = true;
    form.hidden = false;
    demo.hidden = false;
    feedback.hidden = true;
    form.reset();
    byId('name').focus();
  });
  const toggle = byId('recover-toggle');
  const panel = byId('recovery-panel');
  toggle.addEventListener('click', () => {
    panel.hidden = !panel.hidden;
    if (!panel.hidden) byId('recover-order-id').focus();
  });
  byId('recover-form').addEventListener('submit', (event) => {
    event.preventDefault();
    showMessage('ይህ የንድፍ ማሳያ ብቻ ነው። የትዕዛዝ መመለስ አይሠራም።');
  });
})();