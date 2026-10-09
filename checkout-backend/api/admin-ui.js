'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = { csrf: '', page: 1, hasMore: false };
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
      const container=$('detailItems');container.replaceChildren();
      Object.entries(d.order).forEach(([key,value])=>{
        const wrapper=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');
        dt.textContent=key.replace(/_/g,' ');dd.textContent=String(value);wrapper.append(dt,dd);container.append(wrapper);
      });
      const list=$('timeline');list.replaceChildren();
      d.timeline.forEach(e=>{const li=document.createElement('li');li.textContent=e.status+' · '+formatDate(e.at);list.append(li)});
      d.audit.forEach(e=>{const li=document.createElement('li');li.textContent='Audit: '+e.event+' · '+formatDate(e.at);list.append(li)});
      display('detail',true);$('detail').scrollIntoView({behavior:'smooth'});
    } catch(e){error(e.message)}
  }
  async function load(){ try {await Promise.all([overview(),list()]);}catch(e){error(e.message)} }
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