'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = { csrf: '', page: 1, hasMore: false, activeOrder: null, activeMethod: null, activeStatus: null, queuePage:1, queueMore:false };
  function display(id, show){ $(id).hidden = !show; }
  function error(message, target='dashError') { $(target).textContent = message; display(target, Boolean(message)); }
  async function api(path, options={}) {
    const controller = new AbortController();
    const timeout = setTimeout(()=>controller.abort(),20000);
    try {
      const res = await fetch(path, {credentials:'same-origin',cache:'no-store',signal:controller.signal,...options});
      const data = await res.json().catch(()=>({}));
      if (res.status===401 && path!=='/admin/api/login') { state.csrf=''; display('dashboard',false); display('signin',true); error('Founder session expired. Sign in again.','loginError'); }
      if (!res.ok) throw Object.assign(new Error(data.detail || 'Request failed. Try again.'),{status:res.status});
      return data;
    } catch(e) { if(e.name==='AbortError') throw new Error('Request timed out. Check your connection and retry.'); throw e; }
    finally {clearTimeout(timeout);}
  }
  function setText(id,value){ $(id).textContent = String(value); }
  function formatDate(date){ return date ? new Date(date).toLocaleString('en-GB',{timeZone:'UTC',dateStyle:'short',timeStyle:'short'}) : '—'; }
  function cell(row,value){ const td=document.createElement('td');td.textContent=String(value??'—');row.append(td);return td; }
  function showDashboard(){ display('loading',false);display('signin',false);display('dashboard',true); }
  function showLogin(){ display('loading',false);display('dashboard',false);display('signin',true); }
  async function overview() {
    const d=await api('/admin/api/overview');
    ['total','pending'].forEach(k=>setText(k,d[k]));
    setText('telebirr',d.methods.telebirr);setText('bank',d.methods.bank);
  }
  async function list(){
    const params=new URLSearchParams({page:String(state.page),page_size:'15'});
    const filters={order_id:$('search').value.trim(),method:$('method').value,status:$('status').value,from_date:$('fromDate').value,to_date:$('toDate').value};
    Object.entries(filters).forEach(([k,v])=>{if(v)params.set(k,v)});
    const d=await api('/admin/api/orders?'+params);
    state.hasMore=d.has_more; $('prev').disabled=state.page===1; $('next').disabled=!d.has_more;
    setText('pageInfo',`Page ${state.page} · ${d.total} matching QA orders`);
    const tbody=$('orderRows');tbody.replaceChildren();
    if(!d.items.length){ const tr=document.createElement('tr');const td=cell(tr,'No QA orders match these filters.');td.colSpan=6;tbody.append(tr);return; }
    d.items.forEach(o=>{
      const tr=document.createElement('tr');cell(tr,formatDate(o.created_at));cell(tr,o.order_id);cell(tr,o.method);cell(tr,o.amount_etb+' ETB');cell(tr,o.status);
      const td=document.createElement('td');const btn=document.createElement('button');btn.type='button';btn.className='text-link';btn.textContent='View';btn.addEventListener('click',()=>detail(o.order_id));td.append(btn);tr.append(td);tbody.append(tr);
    });
  }
  async function detail(code){
    try {
      error('');const d=await api('/admin/api/orders/'+encodeURIComponent(code));
      state.activeOrder=code;state.activeMethod=d.order.method;state.activeStatus=d.order.status;
      const container=$('detailItems');container.replaceChildren();
      Object.entries(d.order).forEach(([key,value])=>{
        const wrapper=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');
        dt.textContent=key.replace(/_/g,' ');dd.textContent=String(value);wrapper.append(dt,dd);container.append(wrapper);
      });
      const list=$('timeline');list.replaceChildren();
      d.timeline.forEach(e=>{const li=document.createElement('li');li.textContent=e.status+' · '+formatDate(e.at);list.append(li)});
      d.audit.forEach(e=>{const li=document.createElement('li');li.textContent='Audit: '+e.event+' · '+formatDate(e.at);list.append(li)});
      renderQaReconciliation(d);
      renderQaFulfillment(d);
      display('detail',true);$('detail').scrollIntoView({behavior:'smooth'});
    } catch(e){error(e.message)}
  }

  function renderQaReconciliation(data) {
    const o=data.order, reviews=data.reviews||[], events=data.verification_history||[];
    const active=reviews.find(r=>['PROOF_SUBMITTED','VERIFYING'].includes(r.state));
    $('qaRecordProof').disabled=o.status!=='PENDING_PAYMENT';
    $('qaCheckLedger').disabled=o.status!=='PROOF_SUBMITTED';
    $('qaVerify').disabled=o.status!=='VERIFYING'||!active||active.independent_check!=='MATCHED';
    $('qaReject').disabled=!['PROOF_SUBMITTED','VERIFYING'].includes(o.status);
    $('qaCancel').disabled=!['PENDING_PAYMENT','PROOF_SUBMITTED','VERIFYING'].includes(o.status);
    $('qaGenerateFixture').disabled=!['PENDING_PAYMENT','PROOF_SUBMITTED','VERIFYING'].includes(o.status);
    const claims=$('qaReviewHistory');claims.replaceChildren();
    reviews.forEach(r=>{const li=document.createElement('li');
      li.textContent=r.test_reference+' · '+r.reported_amount_etb+' ETB · '+r.state+
        ' · ledger check: '+r.independent_check+(r.decision_reason?' · reason: '+r.decision_reason:'');
      claims.append(li);
    });
    if(!reviews.length){const li=document.createElement('li');li.textContent='No fictional proof recorded.';claims.append(li);}
    const history=$('qaEventHistory');history.replaceChildren();
    events.forEach(e=>{const li=document.createElement('li');
      li.textContent=e.event+' · '+e.before+' → '+e.after+' · '+formatDate(e.at)+
        (e.reason?' · '+e.reason:'');history.append(li);
    });
    if(!events.length){const li=document.createElement('li');li.textContent='No review decisions yet.';history.append(li);}
  }
  function qaMessage(message) {
    $('qaReviewMessage').textContent=message;
    $('qaReviewMessage').hidden=!message;
  }
  let mutating=false;
  async function qaMutation(path, payload, success) {
    if(mutating || !state.activeOrder)return;
    mutating=true;qaMessage('Updating fictional QA review…');
    try{
      const r=await api(path,{method:'POST',headers:{
        'Content-Type':'application/json','X-CSRF-Token':state.csrf
      },body:JSON.stringify(payload)});
      qaMessage(success);
      await detail(state.activeOrder);
      await load();
      return r;
    }catch(e){qaMessage(e.message);throw e;}
    finally{mutating=false;}
  }
  $('qaGenerateFixture').addEventListener('click',async()=>{
    try{
      const r=await qaMutation('/admin/api/qa-ledger',{
        method:state.activeMethod,amount_etb:Number($('qaFixtureAmount').value)
      },'A new internal QA ledger fixture was created. No bank transaction occurred.');
      if(r){$('qaClaimRef').value=r.test_reference;
        $('qaFixtureResult').textContent='FICTIONAL ONLY: '+r.test_reference+' · '+r.amount_etb+' ETB';
      }
    }catch(e){}
  });
  $('qaRecordProof').addEventListener('click',async()=>{
    if(!state.activeOrder)return;
    try{await qaMutation('/admin/api/orders/'+encodeURIComponent(state.activeOrder)+'/proof',{
      test_reference:$('qaClaimRef').value.trim().toUpperCase(),
      reported_amount_etb:Number($('qaClaimAmount').value),currency:'ETB'
    },'Fictional proof recorded. No money verified.');}catch(e){}
  });
  $('qaCheckLedger').addEventListener('click',async()=>{
    try{await qaMutation('/admin/api/orders/'+encodeURIComponent(state.activeOrder)+'/check',{},
        'Comparison complete against the simulated internal test ledger. Review the result below.');}catch(e){}
  });
  $('qaVerify').addEventListener('click',async()=>{
    if(!window.confirm('Confirm this is a SIMULATED QA ledger match only? This does NOT mean ParentWise received real money.'))return;
    try{await qaMutation('/admin/api/orders/'+encodeURIComponent(state.activeOrder)+'/confirm',
        {confirm_simulated_match:true},
        'SIMULATED VERIFIED_PAID status recorded. No real payment received and no product delivered.');}catch(e){}
  });
  $('qaReject').addEventListener('click',async()=>{
    const reason=$('qaReason').value.trim();
    if(reason.length<8){qaMessage('Enter a rejection reason (at least 8 characters).');return;}
    try{await qaMutation('/admin/api/orders/'+encodeURIComponent(state.activeOrder)+'/reject',
        {reason},'Fictional claim rejected. Order returned to PENDING_PAYMENT.');}catch(e){}
  });
  $('qaCancel').addEventListener('click',async()=>{
    const reason=$('qaReason').value.trim();
    if(reason.length<8){qaMessage('Enter a cancellation reason (at least 8 characters).');return;}
    if(!window.confirm('Cancel this TEST order? It cannot be reactivated in Phase 4.'))return;
    try{await qaMutation('/admin/api/orders/'+encodeURIComponent(state.activeOrder)+'/cancel',
        {reason},'QA test order cancelled. No refund or real payment action occurred.');}catch(e){}
  });


  async function fulfillmentQueue(){
    const params=new URLSearchParams({page:String(state.queuePage),page_size:'15'});
    if($('qaFulfillmentFilter').value) params.set('state',$('qaFulfillmentFilter').value);
    const data=await api('/admin/api/fulfillment/queue?'+params);
    state.queueMore=data.has_more;
    $('qaQueuePrev').disabled=state.queuePage===1;
    $('qaQueueNext').disabled=!data.has_more;
    setText('qaQueuePageInfo','Page '+state.queuePage+' · '+data.total+' dummy QA fulfillments');
    const rows=$('qaQueueRows');rows.replaceChildren();
    if(!data.items.length){
      const tr=document.createElement('tr');const td=cell(tr,'No simulated fulfillments match.');td.colSpan=7;rows.append(tr);
    }
    data.items.forEach(x=>{
      const tr=document.createElement('tr');
      cell(tr,x.order_id);cell(tr,x.payment_state+' (synthetic)');
      cell(tr,x.status);cell(tr,x.package_version);
      cell(tr,'Founder Telegram · NOT sent');cell(tr,formatDate(x.updated_at));
      const td=document.createElement('td'),btn=document.createElement('button');
      btn.type='button';btn.className='text-link';btn.textContent='Open';
      btn.addEventListener('click',()=>detail(x.order_id));td.append(btn);tr.append(td);rows.append(tr);
    });
  }
  function renderQaFulfillment(data){
    const f=data.fulfillment;
    display('qaFulfillPanel',!!f);
    if(!f)return;
    setText('qaFulfillState',f.status+' · SIMULATED ONLY');
    setText('qaFulfillVersion',f.package_version);
    setText('qaFulfillChannel','Founder-assisted Telegram (simulation only)');
    setText('qaFulfillAttempts',f.attempt_count);
    const st=f.status;
    $('qaPrepareDummy').disabled=st!=='PENDING_FULFILLMENT';
    $('qaDispatchDummy').disabled=st!=='PREPARING';
    $('qaReceiptDummy').disabled=st!=='SENT';
    $('qaFailDummy').disabled=!['PREPARING','SENT'].includes(st);
    $('qaRetryDummy').disabled=st!=='DELIVERY_FAILED';
    const history=$('qaFulfillEvents');history.replaceChildren();
    (data.fulfillment_events||[]).forEach(x=>{
      const li=document.createElement('li');
      li.textContent=x.action+' · '+x.before+' → '+x.after+' · '+formatDate(x.at)+
        (x.note?' · '+x.note:'')+(x.qa_ack_reference?' · dummy ACK '+x.qa_ack_reference:'');
      history.append(li);
    });
  }
  function fillMessage(msg){
    $('qaFulfillFeedback').textContent=msg;display('qaFulfillFeedback',!!msg);
  }
  async function fulfillmentAction(action,payload,message){
    if(mutating||!state.activeOrder)return;
    mutating=true;
    fillMessage('Saving fictional fulfillment event…');
    try{
      await api('/admin/api/orders/'+encodeURIComponent(state.activeOrder)+'/fulfillment/'+action,
        {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},
         body:JSON.stringify(payload)});
      fillMessage(message);
      await detail(state.activeOrder);
      await fulfillmentQueue();
      await overview();
    }catch(e){fillMessage(e.message)}
    finally{mutating=false;}
  }
  $('qaQueueReload').addEventListener('click',()=>fulfillmentQueue().catch(e=>error(e.message)));
  $('qaFulfillmentFilter').addEventListener('change',()=>{state.queuePage=1;fulfillmentQueue().catch(e=>error(e.message))});
  $('qaQueuePrev').addEventListener('click',()=>{if(state.queuePage>1){state.queuePage--;fulfillmentQueue().catch(e=>error(e.message))}});
  $('qaQueueNext').addEventListener('click',()=>{if(state.queueMore){state.queuePage++;fulfillmentQueue().catch(e=>error(e.message))}});
  $('qaPrepareDummy').addEventListener('click',()=>{
    if(confirm('Start preparing the fictional QA dummy package? NO real product will be sent.'))
      fulfillmentAction('prepare',{confirm_qa_action:true},'Dummy preparation recorded.');
  });
  $('qaDispatchDummy').addEventListener('click',()=>{
    if(!$('qaCheckedDummy').checked){fillMessage('Inspect the harmless dummy document and tick the confirmation first.');return;}
    if(confirm('Record hypothetical dispatch ONLY? This does not send a Telegram message or any paid file.'))
      fulfillmentAction('dispatch',{confirm_qa_action:true,dummy_document_checked:true},
        'Hypothetical dummy dispatch recorded, NO Telegram send occurred.');
  });
  $('qaReceiptDummy').addEventListener('click',()=>{
    const ack=$('qaReceiptReference').value.trim().toUpperCase();
    if(!/^QA-ACK-[A-F0-9]{16}$/.test(ack)){
      fillMessage('Enter a fictional QA-ACK- reference; never paste real customer evidence.');return;
    }
    if(confirm('Record a FICTIONAL customer receipt acknowledgement? This is not evidence Telegram delivered a file.'))
      fulfillmentAction('receipt',{confirm_qa_action:true,source:'QA_SIMULATED_CUSTOMER_ACK',qa_ack_reference:ack},
        'Simulated customer acknowledgement recorded; NO real delivery confirmed.');
  });
  for(const [id,action] of [['qaFailDummy','failure'],['qaRetryDummy','retry']]){
    $(id).addEventListener('click',()=>{
      const reason=$('qaDeliveryReason').value.trim();
      if(reason.length<8){fillMessage('Provide a fictional reason of at least eight characters.');return;}
      if(confirm('Record this strictly QA-only '+action+' action?'))
        fulfillmentAction(action,{reason},'QA-only '+action+' recorded.');
    });
  }

  async function load(){ try {await Promise.all([overview(),list(),fulfillmentQueue()]);}catch(e){error(e.message)} }
  async function initialize(){
    try{ const data=await api('/admin/api/session');state.csrf=data.csrf;showDashboard();await load(); }
    catch(e){ if(e.status===503) error('Founder access not configured yet.','loginError');showLogin(); }
  }
  $('signinForm').addEventListener('submit',async event=>{
    event.preventDefault();error('','loginError');$('loginButton').disabled=true;
    try{
      const data=await api('/admin/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        username:$('username').value,password:$('password').value,totp_code:$('otp').value
      })});
      state.csrf=data.csrf;$('password').value='';$('otp').value='';showDashboard();await load();
    }catch(e){error(e.message,'loginError')}
    finally{$('loginButton').disabled=false}
  });
  $('logout').addEventListener('click',async()=>{
    try{await api('/admin/api/logout',{method:'POST',headers:{'X-CSRF-Token':state.csrf}});state.csrf='';showLogin();}
    catch(e){error(e.message)}
  });
  $('filterForm').addEventListener('submit',async e=>{e.preventDefault();state.page=1;try{error('');await list()}catch(e){error(e.message)}});
  $('prev').addEventListener('click',async()=>{if(state.page>1){state.page--;try{await list()}catch(e){error(e.message)}}});
  $('next').addEventListener('click',async()=>{if(state.hasMore){state.page++;try{await list()}catch(e){error(e.message)}}});
  $('closeDetail').addEventListener('click',()=>display('detail',false));
  initialize();
})();