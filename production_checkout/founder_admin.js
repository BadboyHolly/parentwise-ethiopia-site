(() => {
  'use strict';
  const root = '/api/v1/founder';
  const state = { csrf: null, page: 0, pageSize: 25, total: 0, claim: null, evidenceId: null, reviewed: false };
  const $ = (id) => document.getElementById(id);
  const node = (tag, className, value) => { const el = document.createElement(tag); if (className) el.className = className; if (value !== undefined && value !== null) el.textContent = String(value); return el; };
  const money = (n) => `${new Intl.NumberFormat('en-ET', {maximumFractionDigits:0}).format(Number(n || 0))} ETB`;
  const date = (v) => { if (!v) return '—'; const d = new Date(v); return Number.isNaN(d.valueOf()) ? '—' : d.toLocaleString(); };
  function message(text, kind = 'error') { const box = $('global-message'); if (!box) return; box.textContent = text; box.classList.toggle('visible', Boolean(text)); box.dataset.kind = kind; }
  function clearSensitive() { state.csrf = null; state.claim = null; state.evidenceId = null; }
  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set('Accept', 'application/json');
    if (options.body !== undefined) headers.set('Content-Type', 'application/json');
    if (options.method && options.method !== 'GET' && state.csrf) headers.set('X-CSRF-Token', state.csrf);
    const response = await fetch(root + path, { ...options, headers, credentials: 'same-origin', cache: 'no-store', redirect: 'error' });
    if (response.status === 401 && document.body.dataset.view === 'dashboard') { clearSensitive(); window.location.replace(`${root}/ui/login`); }
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new Error(body?.detail || `Request failed (${response.status})`);
    return body;
  }
  function setCsrf(token) { state.csrf = token; }
  function statusName(s) { return ({AWAITING_PAYMENT:'Awaiting payment',UNDER_REVIEW:'Under review',PAYMENT_REJECTED:'Rejected',PAYMENT_CONFIRMED:'Payment confirmed',PENDING:'Pending',PREPARING:'Preparing',SENT:'Sent',FAILED:'Failed',DELIVERED:'Completed · founder-recorded'})[s] || s || '—'; }
  function empty(container, text) { container.replaceChildren(node('div', 'empty-state', text)); }
  function showEvidence(evidence) {
    const panel=$('evidence-summary'); panel.replaceChildren(); panel.hidden=!evidence;
    if(!evidence)return;
    const method = evidence.payment_method === 'bank' ? 'CBE' : 'Telebirr';
    const source = evidence.source === 'BANK_STATEMENT' ? 'CBE account statement' : 'Telebirr account history';
    panel.append(node('strong', '', 'Independently recorded settlement facts'));
    panel.append(node('p', '', `${method} · ${money(evidence.amount_etb)} ${evidence.currency} · ${source}`));
    panel.append(node('p', '', `Settlement time ${date(evidence.settled_at)} · observed ${date(evidence.observed_at)}`));
    panel.append(node('p', evidence.payer_matches_customer ? 'evidence-match' : 'evidence-mismatch', evidence.payer_matches_customer ? 'Payer identity matches the order customer.' : 'Payer differs from the order customer; a documented exception is required. Transaction references and encrypted notes are intentionally not displayed here.'));
  }
  async function loginInit() {
    const form = $('login-form'); if (!form) return;
    form.addEventListener('submit', async (event) => {
      event.preventDefault(); const button = form.querySelector('button[type=submit]'); button.disabled = true; $('login-message').textContent = '';
      try {
        await api('/session', { method:'POST', body:JSON.stringify({ username:$('username').value.trim(), password:$('password').value, totp:$('totp').value }) });
        form.reset(); window.location.replace(`${root}/ui`);
      } catch (error) { $('login-message').textContent = error.message === 'Request failed (401)' ? 'Sign-in details were not accepted.' : error.message; }
      finally { button.disabled = false; }
    });
  }

  async function loadMetrics() {
    const report = await api('/metrics');
    $('metric-revenue').textContent = money(report.verified_revenue_etb);
    $('metric-paid').textContent = new Intl.NumberFormat().format(report.payment_verified || 0);
    $('metric-awaiting').textContent = new Intl.NumberFormat().format(report.awaiting_payment || 0);
    $('metric-claims').textContent = new Intl.NumberFormat().format(report.under_review || 0);
    $('metric-deliveries').textContent = new Intl.NumberFormat().format(report.delivery_pending || 0);
    const chart = $('revenue-chart'); chart.replaceChildren();
    const series = Array.isArray(report.revenue_trend) ? report.revenue_trend : [];
    const max = Math.max(1, ...series.map((x) => Number(x.revenue_etb || 0)));
    if (!series.length) { empty(chart, 'No verified revenue recorded yet.'); return; }
    series.forEach((item) => {
      const col = node('div','chart-column'); const value = Number(item.revenue_etb || 0);
      const label = node('span','chart-value', money(value));
      const wrap = node('div','chart-bar-wrap'); const bucket = value ? Math.max(1,Math.min(10,Math.ceil((value/max)*10))) : 0; const bar = node('div',`chart-bar chart-bar-${bucket}`); bar.title = money(value); wrap.append(bar);
      col.append(label,wrap,node('span','chart-month',item.month)); chart.append(col);
    });
  }
  function orderRow(order) {
    const tr = document.createElement('tr');
    const cells = [order.order_id, `${order.customer_name}\n${order.mobile_e164}`, statusName(order.payment_status), money(order.amount_etb), statusName(order.delivery_status || order.fulfillment_status), date(order.created_at)];
    cells.forEach((value, i) => { const td = document.createElement('td'); td.textContent = value || '—'; if (i === 0) { const strong=node('strong','',value); td.replaceChildren(strong); } tr.append(td); });
    return tr;
  }
  async function loadOrders() {
    const params = new URLSearchParams({limit:String(state.pageSize),offset:String(state.page*state.pageSize),q:$('order-query').value.trim()});
    if ($('order-status').value) params.set('status',$('order-status').value);
    if ($('order-method').value) params.set('payment_method',$('order-method').value);
    const result = await api(`/orders?${params}`); state.total=result.total; const body=$('orders-body'); body.replaceChildren();
    result.orders.forEach((order) => body.append(orderRow(order)));
    if (!result.orders.length) { const tr=document.createElement('tr'); const td=node('td','','No orders found.'); td.colSpan=6; tr.append(td); body.append(tr); }
    $('orders-count').textContent = `${result.total} order${result.total===1?'':'s'} · page ${state.page+1}`;
    $('orders-prev').disabled = state.page===0; $('orders-next').disabled=(state.page+1)*state.pageSize>=state.total;
  }
  async function lookupOrder(code) { return api(`/orders/search?q=${encodeURIComponent(code)}`); }
  async function loadClaims() {
    const container=$('claims-list');
    try {
      const result=await api('/claims/pending'); container.replaceChildren();
      if (!result.claims.length) { empty(container,'No claims awaiting review.'); return; }
      result.claims.forEach((claim) => {
        const card=node('article','claim-card'); const head=node('div','claim-card-head'); const details=node('div'); details.append(node('strong','',claim.order_id),node('p','',`${claim.customer_name} · ${claim.mobile}`));
        head.append(details,node('span','status-pill',statusName(claim.claim_status)));
        const p=node('p','',`${claim.payment_method==='bank'?'CBE':'Telebirr'} · ${money(claim.amount_etb)} · claimed ref ${claim.claimed_reference} · ${date(claim.submitted_at)}`);
        const btn=node('button','button button-light','Review independently'); btn.type='button'; btn.addEventListener('click',()=>selectClaim(claim)); card.append(head,p,btn); container.append(card);
      });
    } catch(error) { empty(container,error.message); throw error; }
  }
  async function selectClaim(claim) {
    state.claim=claim; state.evidenceId=claim.evidence_id||null; state.exceptionId=claim.exception_id||null; state.reviewed=false;
    $('claim-review').hidden=false; $('review-heading').textContent=`${claim.order_id} · ${claim.customer_name}`;
    $('review-subtitle').textContent=`${claim.payment_method==='bank'?'CBE':'Telebirr'} claim · ${money(claim.amount_etb)} · claimed reference ${claim.claimed_reference}`;
    showEvidence(claim.evidence);
    $('evidence-method').value=claim.payment_method; $('evidence-amount').value=String(claim.amount_etb); $('evidence-currency').value='ETB'; $('settled-at').value=new Date().toISOString().slice(0,16);
    $('settlement-form').hidden=Boolean(state.evidenceId);
    $('observed-reference').value=''; $('payer-mobile').value=claim.mobile; $('recipient-confirmed').checked=false; $('evidence-note').value=''; $('decision-reason').value=''; $('decision-form').hidden=false; $('approve-payment').disabled=!state.evidenceId || Boolean(claim.evidence && !claim.evidence.payer_matches_customer && !state.exceptionId); $('evidence-state').textContent=state.evidenceId?'Evidence already recorded.':'Evidence does not approve payment.';
    $('exception-form').hidden=!(claim.evidence_id && claim.evidence && !claim.evidence.payer_matches_customer && !state.exceptionId); $('exception-state').textContent=state.exceptionId?'Payer exception already documented.':''; $('decision-state').textContent=state.evidenceId?'Review evidence before approval.':'Record independent settlement evidence before approving.';
    $('claim-review').scrollIntoView({behavior:'smooth',block:'start'});
  }
  async function recordClaim(event) {
    event.preventDefault(); const code=$('claim-order').value.trim().toUpperCase(); const btn=event.submitter; btn.disabled=true;
    try {
      const found=await lookupOrder(code); const order=found.order;
      if (order.payment_status!=='AWAITING_PAYMENT' && order.payment_status!=='UNDER_REVIEW') throw new Error('This order is not eligible for a new claim.');
      if (order.payment_method!==$('claim-method').value) throw new Error('Selected payment method does not match the order.');
      const result=await api('/claims/telegram',{method:'POST',body:JSON.stringify({order_id:code,payment_method:$('claim-method').value,transaction_reference:$('claim-reference').value.trim()})});
      $('claim-reference').value=''; message(`Claim recorded for ${result.order_id}. This is not payment confirmation.`, 'success'); await Promise.all([loadClaims(),loadMetrics(),loadOrders()]);
    } catch(error) { message(error.message); }
    finally {btn.disabled=false;}
  }
  async function saveEvidence(event) {
    event.preventDefault(); if(!state.claim)return; const btn=event.submitter; btn.disabled=true;
    try {
      const result=await api('/settlements',{method:'POST',body:JSON.stringify({order_id:state.claim.order_id,claim_id:state.claim.claim_id,observed_reference:$('observed-reference').value.trim(),payment_method:$('evidence-method').value,amount_etb:Number($('evidence-amount').value),currency:$('evidence-currency').value.trim().toUpperCase(),recipient_confirmed:$('recipient-confirmed').checked,payer_mobile:$('payer-mobile').value.trim(),evidence_source:$('evidence-source').value,settled_at:new Date($('settled-at').value).toISOString(),note:$('evidence-note').value.trim()})});
      state.evidenceId=result.evidence_id; state.claim.evidence={payment_method:$('evidence-method').value,amount_etb:Number($('evidence-amount').value),currency:$('evidence-currency').value.toUpperCase(),source:$('evidence-source').value,settled_at:new Date($('settled-at').value).toISOString(),observed_at:new Date().toISOString(),payer_matches_customer:result.payer_matches_customer}; showEvidence(state.claim.evidence); $('settlement-form').hidden=true; $('approve-payment').disabled=!result.payer_matches_customer; $('evidence-state').textContent='Settlement evidence recorded. Approval remains a separate founder decision.'; $('decision-state').textContent=result.payer_matches_customer?'Confirm the independent account record, then approve or reject.':'Document the verified third-party payer relationship before approval.'; $('exception-form').hidden=result.payer_matches_customer; message('Independent settlement evidence recorded. No sale is counted until approval.','success'); await loadClaims();
    } catch(error) { $('evidence-state').textContent=error.message; message(error.message); }
    finally {btn.disabled=false;}
  }
  async function documentException(event) {
    event.preventDefault(); if(!state.claim||!state.evidenceId)return;
    try { const result=await api('/third-party-exceptions',{method:'POST',body:JSON.stringify({order_id:state.claim.order_id,claim_id:state.claim.claim_id,evidence_id:state.evidenceId,relationship:$('exception-relationship').value,rationale:$('exception-rationale').value.trim()})}); state.exceptionId=result.exception_id; $('exception-state').textContent='Payer exception documented for founder review.'; $('approve-payment').disabled=false; message('Payer exception documented; it does not approve payment.','success'); }
    catch(error){$('exception-state').textContent=error.message;message(error.message);}
  }
  async function decision(approve) {
    if(!state.claim)return; const reason=$('decision-reason').value.trim(); if(reason.length<10){message('Add an audit reason of at least 10 characters.');return;}
    if(approve&&!state.evidenceId){message('Independent settlement evidence is required.');return;}
    const btn=$(approve?'approve-payment':'reject-payment'); btn.disabled=true;
    try {
      const body={order_id:state.claim.order_id,claim_id:state.claim.claim_id,evidence_id:approve?state.evidenceId:null,reason}; if(approve&&state.exceptionId)body.third_party_exception_id=state.exceptionId;
      const result=await api(approve?'/approve':'/reject',{method:'POST',body:JSON.stringify(body)});
      message(approve?`Payment approved after independent verification. Delivery remains ${result.delivery_status||'pending'} and must be recorded manually.`:'Claim rejected and decision recorded.','success');
      state.claim=null; state.evidenceId=null; $('claim-review').hidden=true; await Promise.all([loadMetrics(),loadClaims(),loadDeliveries(),loadOrders()]);
    } catch(error){message(error.message);}
    finally {btn.disabled=false;}
  }
  async function loadDeliveries() {
    const container=$('deliveries-list'); const result=await api('/deliveries/pending'); container.replaceChildren();
    if(!result.deliveries.length){empty(container,'No manual deliveries are pending.');return;}
    result.deliveries.forEach((item)=>{
      const card=node('article','delivery-card'); const info=node('div'); info.append(node('strong','',`${item.order_id} · ${item.customer_name}`),node('p','',`${item.mobile} · ${statusName(item.status)} · updated ${date(item.updated_at)}`));
      const actions=node('div','delivery-actions');
      const allowed={PENDING:['PREPARING'],PREPARING:['SENT','FAILED'],SENT:['DELIVERED','FAILED'],FAILED:['PREPARING']}[item.status]||[];
      allowed.forEach((next)=>{const btn=node('button',`button ${next==='DELIVERED'?'button-primary':'button-light'}`,next==='DELIVERED'?'Mark completed · founder-recorded':`Mark ${statusName(next).toLowerCase()}`);btn.type='button';btn.addEventListener('click',async()=>{btn.disabled=true;try{await api('/deliveries/status',{method:'POST',body:JSON.stringify({order_id:item.order_id,status:next})});message(`Delivery marked ${statusName(next).toLowerCase()}. Completion is founder-recorded, not customer-confirmed.`,'success');await Promise.all([loadDeliveries(),loadMetrics()]);}catch(error){message(error.message);btn.disabled=false;}});actions.append(btn);});
      const history=node('button','text-button','View history');history.type='button';history.addEventListener('click',()=>loadHistory(item.order_id));actions.append(history);card.append(info,actions);container.append(card);
    });
  }
  async function loadHistory(orderId){try{const result=await api(`/deliveries/${encodeURIComponent(orderId)}/history`);$('history-order').textContent=`${result.order_id} · founder-recorded delivery history`;const list=$('history-list');list.replaceChildren();result.history.forEach((event)=>{const li=node('li','',`${statusName(event.old_status)} → ${statusName(event.new_status)}`);li.append(node('small','',`${event.actor_id} · ${date(event.occurred_at)}`));list.append(li);});if(!result.history.length)empty(list,'No delivery changes recorded.');$('delivery-history').hidden=false;$('delivery-history').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){message(error.message);}}
  function switchSection(name) { document.querySelectorAll('.page-section').forEach((section)=>section.classList.toggle('active',section.id===`section-${name}`));document.querySelectorAll('.nav-item').forEach((button)=>button.classList.toggle('active',button.dataset.section===name));$('page-title').textContent=({overview:'Overview',orders:'Orders',payments:'Payment review',delivery:'Telegram delivery'})[name]||'Overview';message(''); }
  async function dashboardInit(){
    try { const session=await api('/session'); setCsrf(session.csrf_token); $('founder-name').textContent=session.founder_id; $('founder-initial').textContent=(session.founder_id||'F').slice(0,1).toUpperCase(); await Promise.all([loadMetrics(),loadOrders(),loadClaims(),loadDeliveries()]); }
    catch(error){if(error.message!=='Request failed (401)')message(error.message);return;}
    document.querySelectorAll('.nav-item').forEach((button)=>button.addEventListener('click',()=>switchSection(button.dataset.section)));
    $('order-filter').addEventListener('submit',async(e)=>{e.preventDefault();state.page=0;try{await loadOrders();}catch(err){message(err.message);}});
    $('orders-prev').addEventListener('click',async()=>{state.page=Math.max(0,state.page-1);try{await loadOrders();}catch(e){message(e.message);}});
    $('orders-next').addEventListener('click',async()=>{state.page++;try{await loadOrders();}catch(e){message(e.message);}});
    $('telegram-claim-form').addEventListener('submit',recordClaim);
    $('lookup-order').addEventListener('click',async()=>{try{const result=await lookupOrder($('claim-order').value.trim().toUpperCase());const order=result.order;$('claim-order-summary').hidden=false;$('claim-order-summary').textContent=`${order.customer_name} · ${order.mobile_e164} · ${order.payment_method==='bank'?'CBE':'Telebirr'} · ${money(order.amount_etb)} · ${statusName(order.payment_status)}`;$('claim-method').value=order.payment_method;}catch(error){$('claim-order-summary').hidden=false;$('claim-order-summary').textContent=error.message;}});
    $('refresh-claims').addEventListener('click',()=>loadClaims().catch(e=>message(e.message)));
    $('settlement-form').addEventListener('submit',saveEvidence);$('exception-form').addEventListener('submit',documentException);
    $('approve-payment').addEventListener('click',()=>decision(true));$('reject-payment').addEventListener('click',()=>decision(false));
    $('close-review').addEventListener('click',()=>{$('claim-review').hidden=true;state.claim=null;state.evidenceId=null;});
    $('refresh-deliveries').addEventListener('click',()=>loadDeliveries().catch(e=>message(e.message)));
    $('close-history').addEventListener('click',()=>$('delivery-history').hidden=true);
    $('refresh-all').addEventListener('click',async()=>{try{await Promise.all([loadMetrics(),loadOrders(),loadClaims(),loadDeliveries()]);message('Dashboard refreshed.','success');}catch(e){message(e.message);}});
    async function logout(){try{await api('/session',{method:'DELETE'});}catch(_){}finally{clearSensitive();window.location.replace(`${root}/ui/login`);}}
    $('logout').addEventListener('click',logout);$('logout-mobile').addEventListener('click',logout);
    window.addEventListener('pageshow',(event)=>{if(event.persisted){clearSensitive();window.location.reload();}});
  }
  if(document.body.dataset.view==='login')loginInit(); else if(document.body.dataset.view==='dashboard')dashboardInit();
})();
