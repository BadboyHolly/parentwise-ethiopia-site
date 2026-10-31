'use strict';
(() => {
  const newUUID=()=>{if(crypto.randomUUID)return crypto.randomUUID();const b=crypto.getRandomValues(new Uint8Array(16));b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;const h=Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);};
  const LIVE = false; // Public review pages never connect to private APIs.
  const API = '/api/v1/founder';
  const $ = id => document.getElementById(id);
  const fmt = n => Number(n || 0).toLocaleString('en-US');
  const date = v => new Date(v).toLocaleString('en-GB', {timeZone:'Africa/Addis_Ababa',dateStyle:'medium',timeStyle:'short'});
  const el = (tag, cls, text) => {const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  const empty = (title, text) => {const d=el('div','empty');d.append(el('strong','',title),el('span','',text));return d;};
  const button = (label, fn, cls='text-button') => {const b=el('button',cls,label);b.type='button';b.onclick=fn;return b;};
  const labels={AWAITING_PAYMENT:'No payment statement',UNDER_REVIEW:'Proof to verify',PAYMENT_CONFIRMED:'Payment verified',PAYMENT_REJECTED:'Rejected'};
  let currentOrder=null,workspaceVersion=0,ordersVersion=0;
  let csrf='', active='overview', report=null, rows=[], offset=0, hasMore=false, emptyDemo=false, requestVersion=0;
  const titles={marketing:['Advertising results','Turn spend and verified sales into useful decisions.'],overview:['Overview','See what is happening. Know what needs you.'],website:['Website analytics','Understand the journey from first visit to checkout.'],orders:['Orders','Find a parent, check their order and see what comes next.'],payments:['Payment review','Match the actual transaction before approving payment.'],delivery:['Delivery','Verified payments waiting for their five PDF guides.']};
  const minutesAgo=n=>new Date(Date.now()-n*60000).toISOString();
  const demoState=Array.from({length:8},(_,i)=>({code:'DEMO-00'+(i+1),customer_name:'Example parent '+String.fromCharCode(65+i),mobile_e164:'+25190000000'+i,method:i%2?'bank':'telebirr',amount_etb:1500,environment:'production',source:['facebook','instagram','telegram','direct','facebook','unattributed','instagram','facebook'][i],created_at:minutesAgo(60+i*10),fulfillment_status:'LOCKED',payment_status:'AWAITING_PAYMENT'}));
  Object.assign(demoState[0],{payment_status:'UNDER_REVIEW',claim_id:'demo-claim-1',proof_recorded_at:minutesAgo(14),waiting_since:minutesAgo(14)});
  Object.assign(demoState[1],{payment_status:'UNDER_REVIEW',claim_id:'demo-claim-2',proof_recorded_at:minutesAgo(6),waiting_since:minutesAgo(6),evidence_id:'demo-evidence-2',observed_amount_etb:1500,payer_mismatch:true});
  Object.assign(demoState[2],{payment_claimed_at:minutesAgo(22),waiting_since:minutesAgo(22)});
  [4,5,6,7].forEach((i,j)=>Object.assign(demoState[i],{payment_status:'PAYMENT_CONFIRMED',fulfillment_status:'READY_TO_DOWNLOAD',verified_at:minutesAgo(j+2),waiting_since:minutesAgo(j+2),...(j>1?{delivered_at:minutesAgo(1)}:{})}));
  const demoOrders=()=>emptyDemo||$('environment').value==='preview'?[]:demoState;
  const demoNotes=new Map();
  const statusOf=r=>r.delivered_at?'Delivered':r.payment_status==='AWAITING_PAYMENT'&&r.payment_claimed_at?'Says paid · proof not recorded':labels[r.payment_status];
  function waitText(r){
    const start=r.payment_status==='PAYMENT_CONFIRMED'?r.verified_at:r.payment_status==='UNDER_REVIEW'?r.proof_recorded_at:r.payment_claimed_at||r.created_at;
    const mins=Math.max(0,Math.floor((Date.now()-new Date(start))/60000));
    const age=mins<1?'just now':mins<60?mins+'m':mins<1440?Math.floor(mins/60)+'h '+mins%60+'m':Math.floor(mins/1440)+'d';
    if(r.delivered_at)return 'Delivered '+date(r.delivered_at);
    if(r.payment_status==='PAYMENT_CONFIRMED')return 'Delivery waiting · '+age;
    if(r.payment_status==='UNDER_REVIEW')return 'Proof waiting · '+age;
    if(r.payment_claimed_at)return 'Payment statement · '+age;
    return 'Order created · '+age;
  }
  function demoReport(){
    const values=demoOrders().length?[1240,42,8,7,6]:[0,0,0,0,0];
    const data=demoOrders(),verified=data.filter(r=>r.payment_status==='PAYMENT_CONFIRMED'),delivered=verified.filter(r=>r.delivered_at);
    return {mode:'demo',environment:$('environment').value,generated_at:new Date().toISOString(),actions_enabled:false,
      business:demoBusiness(data),
      metrics:{sessions:data.length?1240:0,orders_created:data.length,verified_payments:verified.length,verified_revenue_etb:verified.length*1500,
      under_review:data.filter(r=>r.payment_status==='UNDER_REVIEW').length,claimed_no_proof:data.filter(r=>r.payment_status==='AWAITING_PAYMENT'&&r.payment_claimed_at).length,
      delivery_due:verified.length-delivered.length,delivered:delivered.length,awaiting_payment:data.filter(r=>r.payment_status==='AWAITING_PAYMENT'&&!r.payment_claimed_at).length},
      funnel:['sales_view','checkout_view','payment_view','proof_view','telegram_open'].map((event,i)=>({event,sessions:values[i]})),
      sources:data.length?['facebook','instagram','telegram','direct','unattributed'].map(source=>{const group=data.filter(r=>r.source===source);return {source,campaign:source==='facebook'?'parents-demo':'',sessions:({facebook:740,instagram:280,telegram:140,direct:80,unattributed:0})[source],orders:group.length,verified:group.filter(r=>r.payment_status==='PAYMENT_CONFIRMED').length,revenue_etb:group.filter(r=>r.payment_status==='PAYMENT_CONFIRMED').length*1500};}):[],
      daily:!data.length?[]:Array.from({length:14},(_,i)=>({day:new Date(Date.now()-(13-i)*86400000).toISOString().slice(0,10),sessions:[42,68,51,78,64,88,74,112,94,106,120,97,125,121][i]}))};
  }
  function clearPrivate(){report=null;rows=[];document.querySelectorAll('.tab-panel').forEach(p=>p.replaceChildren());$('order-dialog').close();$('detail-body').replaceChildren();location.reload();}
  async function api(path, options={}){
    const r=await fetch(API+path,{credentials:'same-origin',cache:'no-store',...options,headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{}),...options.headers}});
    if(r.status===401){if(path!='/session')clearPrivate();throw Error('Session expired. Sign in again.');}
    if(!r.ok){let detail='Request failed. No success was recorded.';try{const j=await r.json();if(typeof j.detail==='string')detail=j.detail;else if(Array.isArray(j.detail))detail=j.detail.slice(0,2).map(x=>x.msg||'Check the entered details').join(' ');}catch{}throw Error(detail);}
    return r.status===204?null:r.json();
  }
  function switchTab(tab,queue){
    if(!titles[tab])return;active=tab;document.body.classList.toggle('operations',['orders','payments','delivery'].includes(tab));
    document.querySelectorAll('.tab-panel').forEach(p=>p.hidden=p.id!=='panel-'+tab);
    document.querySelectorAll('nav [data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-current',b.dataset.tab===tab?'page':'false');});
    $('period-filter').hidden=['orders','payments','delivery'].includes(tab);
    $('page-title').textContent=titles[tab][0];$('page-subtitle').textContent=titles[tab][1];
    if(tab==='marketing')loadSpendDate();
    if(['orders','payments','delivery'].includes(tab)) {offset=0;renderOrdersShell();if(queue)$('order-status').value=queue;loadOrders();}
    history.replaceState(null,'','#'+tab);window.scrollTo({top:0,behavior:'instant'});
  }
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>switchTab(b.dataset.tab));
  function metric(label,value,foot,featured=false){const c=el('div','metric'+(featured?' featured':''));c.append(el('div','metric-label',label),el('strong','',value),el('small','',foot));return c;}
  function funnel(target){
    const host=$(target);host.replaceChildren();const data=report.funnel;
    if(!data.length||!data[0].sessions){host.append(empty('No journey data yet',LIVE?'No recorded sales-page sessions in this period.':'Example empty state · tracking is not connected.'));return;}
    const names={sales_view:'Sales page viewed',checkout_view:'Checkout opened',payment_view:'Payment details viewed',proof_view:'Proof screen reached',telegram_open:'Telegram link tapped'};
    const losses=data.slice(0,-1).map((s,i)=>Math.max(0,s.sessions-data[i+1].sessions));const biggest=Math.max(...losses);
    data.forEach((s,i)=>{const row=el('div','funnel-row'+(losses[i]===biggest&&biggest?' biggest-loss':'')),l=el('div','funnel-label'),track=el('div','funnel-track'),fill=el('div','funnel-fill');l.append(el('span','',names[s.event]),el('b','',fmt(s.sessions)));fill.style.width=(100*s.sessions/data[0].sessions)+'%';track.append(fill);row.append(l,track);
      if(i<data.length-1){const loss=Math.max(0,s.sessions-data[i+1].sessions);const lossLabel=el('div','loss',fmt(loss)+' had no recorded next stage · '+(s.sessions?Math.round(100*loss/s.sessions):0)+'%');if(loss===biggest)lossLabel.append(el('b','',' · Largest loss'));row.append(lossLabel);}host.append(row);});
  }
  function table(headers, data){const t=el('table'),head=el('thead'),tr=el('tr');headers.forEach(h=>tr.append(el('th','',h)));head.append(tr);t.append(head);const body=el('tbody');data.forEach(cells=>{const row=el('tr');cells.forEach(c=>{const td=el('td');td.append(c instanceof Node?c:document.createTextNode(String(c)));row.append(td);});body.append(row);});t.append(body);return t;}
  function renderReport(){
    const m=report.metrics;$('metric-grid').replaceChildren(metric('Browser sessions',fmt(m.sessions),'Website · session-start period'),metric('Orders created',fmt(m.orders_created),'Orders · created in period'),metric('Verified revenue',fmt(m.verified_revenue_etb)+' ETB','Verified in period · before refunds',true),metric('Verified payments',fmt(m.verified_payments),'Verified in period · not button taps'));
    $('review-count').textContent=fmt(m.under_review+(m.claimed_no_proof||0));$('delivery-count').textContent=fmt(m.delivery_due);
    $('updated').textContent=(LIVE?'Updated ':'Example data · ')+date(report.generated_at);$('traffic-env').textContent=$('environment').value==='production'?'Production':'Preview / QA';
    document.title='('+fmt(m.under_review+(m.claimed_no_proof||0))+' review · '+fmt(m.delivery_due)+' delivery) ParentWise';
    const acts=$('action-list');acts.replaceChildren();
    [[m.claimed_no_proof||0,'Payment statements to match','Customer says paid; proof not recorded.','payments','Match →'],[m.under_review,'Proofs to verify','Check your Telebirr / CBE records.','payments','Review →'],[m.delivery_due,'Parents waiting for guides','Payment verified; delivery not recorded.','delivery','Send guides →']].forEach(([n,title,sub,tab,cta])=>{const r=el('div','action-row'),d=el('div');d.append(el('b','',title),el('p','',sub));r.append(el('span','action-number',fmt(n)),d,button(cta,()=>switchTab(tab,title==='Payment statements to match'?'CLAIMED_NO_PROOF':undefined)));acts.append(r);});
    funnel('overview-funnel');funnel('full-funnel');
    const src=$('overview-sources');src.replaceChildren();
    const sourceGroups=new Map();report.sources.forEach(s=>{const g=sourceGroups.get(s.source)||{source:s.source,sessions:0,verified:0};g.sessions+=Number(s.sessions);g.verified+=Number(s.verified);sourceGroups.set(s.source,g);});
    [...sourceGroups.values()].forEach(s=>{const r=el('div','source-row'),d=el('div','source-name',s.source);d.append(el('small','',fmt(s.verified)+' payments verified in period'));r.append(d,el('b','',fmt(s.sessions)+' sessions'));src.append(r);});
    if(!report.sources.length)src.append(empty('No source data yet','Orders without tracking stay unattributed.'));
    const st=$('source-table');st.replaceChildren(report.sources.length?table(['Source','Campaign','Sessions','Orders','Verified','Gross ETB'],report.sources.map(s=>[s.source,s.campaign||'—',fmt(s.sessions),fmt(s.orders),fmt(s.verified),fmt(s.revenue_etb)])):empty('No attributed sessions','Add approved campaign tags when tracking is activated.'));
    renderTrend();renderBusiness();
  }
  const money=n=>n===null||n===undefined?'—':fmt(Number(n).toFixed(2))+' ETB';
  const percent=n=>n===null||n===undefined?'—':Number(n).toFixed(2)+'%';
  const multiple=n=>n===null||n===undefined?'—':Number(n).toFixed(2)+'×';
  const duration=n=>n===null||n===undefined?'—':Number(n)<60?Math.round(n)+' sec':Math.round(Number(n)/60)+' min';
  const localDay=()=>{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Africa/Addis_Ababa',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const part=k=>parts.find(x=>x.type===k).value;return part('year')+'-'+part('month')+'-'+part('day');};
  const demoSpend=new Map();
  function demoBusiness(data){
    const verified=data.filter(r=>r.payment_status==='PAYMENT_CONFIRMED'),n=verified.length,days=Number($('days').value),coverage=days===1&&demoSpend.has(localDay())&&data.length?1:0;
    const spend=coverage?demoSpend.get(localDay()).amount_etb:null,complete=coverage===days;
    return {aov_etb:n?1500:null,session_conversion_pct:data.length?Number((n/1240*100).toFixed(2)):null,converted_sessions:n,cohort_sessions:data.length?1240:0,
      active_sessions_5m:data.length?2:0,median_verification_seconds:n?150:null,median_delivery_seconds:n?45:null,previous:{sales:0,revenue:0},revenue_change_pct:null,
      order_cohort:{orders:data.length,paid_claimed:data.filter(r=>r.payment_claimed_at).length,proof_recorded:data.filter(r=>r.claim_id||r.payment_status==='PAYMENT_CONFIRMED').length,verified:n,delivered:data.filter(r=>r.delivered_at).length},
      daily_sales:n?[{day:localDay(),verified_sales:n,revenue_etb:n*1500}]:[],
      devices:{viewport:data.length?[{label:'mobile',sessions:1166},{label:'desktop',sessions:74}]:[],browser_kind:data.length?[{label:'facebook_in_app',sessions:740},{label:'instagram_in_app',sessions:280},{label:'other',sessions:220}]:[]},
      creatives:[...new Set(verified.map(r=>r.source))].map(source=>({source,campaign:source==='facebook'?'parents-demo':'',creative:source==='facebook'?'example-video-a':'',verified_sales:verified.filter(r=>r.source===source).length,revenue_etb:verified.filter(r=>r.source===source).length*1500})),
      spend:{reported_etb:spend,covered_days:coverage,period_days:days,complete,blended_cost_per_sale_etb:complete&&n?spend/n:null,
        blended_revenue_multiple:complete&&spend?n*1500/spend:null,tagged_period_roas:complete&&spend?verified.filter(r=>r.source==='facebook').length*1500/spend:null}};
  }
  function renderBusiness(){
    const b=report.business;if(!b)return;
    $('business-metrics').replaceChildren(metric('Session → verified sale',percent(b.session_conversion_pct),'Tracked session-start cohort · '+fmt(b.converted_sessions)+' / '+fmt(b.cohort_sessions)),metric('Average verified sale',money(b.aov_etb),'Gross revenue ÷ verified payments'),metric('Active sessions · 5 min',fmt(b.active_sessions_5m),'Recorded activity now · not people'),metric('Median delivery wait',duration(b.median_delivery_seconds),'Verified → marked sent · recorded'));
    $('period-comparison').textContent=b.revenue_change_pct===null?'Previous period: '+money(b.previous.revenue)+' · no percentage baseline':(Number(b.revenue_change_pct)>=0?'+':'')+percent(b.revenue_change_pct)+' revenue vs previous equal-length period · today partial';
    $('daily-sales').replaceChildren(b.daily_sales.length?table(['Date · Addis','Verified sales','Gross ETB'],b.daily_sales.map(r=>[r.day,fmt(r.verified_sales),fmt(r.revenue_etb)])):empty('No verified sales','Daily revenue appears after payment verification.'));
    const ledger=$('ledger-funnel');ledger.replaceChildren();const labels={orders:'Orders created',paid_claimed:'Customer says paid',proof_recorded:'Proof recorded',verified:'Payment verified',delivered:'Guides marked sent'};
    Object.entries(labels).forEach(([key,label])=>{const row=el('div','source-row');row.append(el('span','',label),el('b','',fmt(b.order_cohort[key])));ledger.append(row);});
    ledger.append(el('p','caption','Median recorded proof → verification: '+duration(b.median_verification_seconds)+'. Stages can be skipped; a missing customer statement does not prove non-payment.'));
    for(const [id,key]of [['device-split','viewport'],['browser-split','browser_kind']]){const host=$(id);host.replaceChildren();const ds=b.devices[key];if(!ds.length)host.append(empty('No breakdown yet','Appears after live collection is connected.'));ds.forEach(r=>{const row=el('div','source-row');row.append(el('span','',r.label.replaceAll('_',' ')),el('b','',fmt(r.sessions)+' · '+percent(b.cohort_sessions?r.sessions/b.cohort_sessions*100:null)));host.append(row);});}
    const cost=b.spend;$('ad-metrics').replaceChildren(metric('Reported ad spend',money(cost.reported_etb),'Manual totals · selected period'),metric('Cost / verified sale',money(cost.blended_cost_per_sale_etb),'Blended · includes organic sales'),metric('Tagged period ROAS',multiple(cost.tagged_period_roas),'Paid-tagged revenue ÷ ad spend'),metric('Revenue / ad spend',multiple(cost.blended_revenue_multiple),'Blended · revenue, not profit'));
    $('spend-coverage').textContent=cost.complete?'Spend recorded for every date in this period. Today and its ratios are provisional; refunds and other costs are excluded.':fmt(cost.covered_days)+' of '+fmt(cost.period_days)+' dates recorded. Add missing daily totals, including 0 on no-spend days. Cost and ROAS stay unavailable until coverage is complete.';
    $('creative-table').replaceChildren(b.creatives.length?table(['Source','Campaign','Creative','Verified sales','Gross ETB'],b.creatives.map(r=>[r.source,r.campaign||'—',r.creative||'Unspecified',fmt(r.verified_sales),fmt(r.revenue_etb)])):empty('No creative sales yet','Approved campaign and creative tags connect visits to verified orders.'));
  }
  let spendVersion=0,spendRevision=null,spendRequest=null;
  async function loadSpendDate(){
    const day=$('spend-date').value;if(!day)return;const version=++spendVersion;$('spend-save').disabled=true;$('spend-entry-status').textContent='Loading this date…';spendRequest=null;
    try{const r=LIVE?await api('/ad-spend/'+day+'?environment='+$('environment').value):{entry:demoSpend.get(day)||null};if(version!==spendVersion)return;
      spendRevision=r.entry?.id||null;$('spend-currency').value=r.entry?.currency||'ETB';$('spend-amount').value=r.entry?.amount??'';$('spend-fx').value=r.entry?.etb_per_unit??'';setSpendCurrency();
      $('spend-entry-status').textContent=r.entry?'Existing total: '+money(r.entry.amount_etb)+'. Saving replaces this date’s total; it does not add to it.':'No spend entered for this date. Blank is not zero.';
      $('spend-save').disabled=LIVE&&!report?.actions_enabled;
    }catch(e){if(version===spendVersion)$('spend-entry-status').textContent=e.message;}
  }
  function setSpendCurrency(){const usd=$('spend-currency').value==='USD';$('spend-fx-label').hidden=!usd;$('spend-fx').required=usd;}
  $('spend-date').value=localDay();$('spend-date').max=localDay();$('spend-date').onchange=loadSpendDate;$('spend-currency').onchange=setSpendCurrency;
  $('spend-form').onsubmit=async e=>{e.preventDefault();if(LIVE&&!report?.actions_enabled)return;const day=$('spend-date').value,currency=$('spend-currency').value;
    const payload={environment:$('environment').value,spend_date:day,currency,amount:$('spend-amount').value,etb_per_unit:currency==='ETB'?'1':$('spend-fx').value,expected_revision:spendRevision};const fingerprint=JSON.stringify(payload);
    if(spendRequest?.fingerprint!==fingerprint)spendRequest={fingerprint,id:newUUID()};$('spend-save').disabled=true;
    try{if(LIVE)await api('/ad-spend',{method:'POST',body:JSON.stringify({...payload,request_id:spendRequest.id})});else demoSpend.set(day,{id:(spendRevision||0)+1,...payload,amount_etb:Number(payload.amount)*Number(payload.etb_per_unit)});
      await loadReport();await loadSpendDate();$('spend-entry-status').textContent=(LIVE?'Saved. ':'Example saved. ')+"This date's total was replaced. Choose Today to inspect today's ratios.";
    }catch(err){$('spend-entry-status').textContent=err.message+' Reload the date to check what was recorded.';$('spend-save').disabled=false;}
  };
  $('export-business').onclick=()=>{
    if(!report?.business)return;const b=report.business,m=report.metrics,c=b.spend;
    const rows=[['ParentWise analytics',LIVE?'Connected report':'FICTIONAL PREVIEW'],['Environment',report.environment],['Period days',$('days').value],['Verified revenue ETB',m.verified_revenue_etb],['Verified payments',m.verified_payments],['Session cohort conversion %',b.session_conversion_pct??'Unavailable'],['Average verified sale ETB',b.aov_etb??'Unavailable'],['Reported ad spend ETB',c.reported_etb??'Not entered'],['Spend coverage',c.covered_days+'/'+c.period_days],['Blended cost per verified sale ETB',c.blended_cost_per_sale_etb??'Unavailable'],['Tagged period ROAS',c.tagged_period_roas??'Unavailable'],['Note','Gross revenue; refunds, fees and other costs excluded. Not profit.']];
    const quote=v=>'"'+String(v).replaceAll('"','""')+'"';const blob=new Blob(['\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='parentwise-'+(LIVE?'analytics':'example')+'-'+localDay()+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  function renderTrend(){
    const host=$('trend');host.replaceChildren();if(!report.daily.length){host.append(empty('No activity recorded','A real trend appears after collection is connected.'));return;}
    const start=new Date(report.start||report.daily[0].day);const count=LIVE?Number($('days').value):14;
    const map=new Map(report.daily.map(d=>[String(d.day).slice(0,10),Number(d.sessions)]));
    const vals=Array.from({length:count},(_,i)=>{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Africa/Addis_Ababa',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(start.getTime()+i*86400000));const part=k=>parts.find(p=>p.type===k).value;const key=part('year')+'-'+part('month')+'-'+part('day');return map.get(key)||0;});
    // Date key generation is explicit to avoid locale-dependent string formats.
    if(!LIVE)report.daily.forEach((d,i)=>vals[i]=Number(d.sessions));
    const max=Math.max(1,...vals),NS='http://www.w3.org/2000/svg',svg=document.createElementNS(NS,'svg');svg.setAttribute('viewBox','0 0 480 160');svg.setAttribute('class','chart');svg.setAttribute('role','img');svg.setAttribute('aria-label','Daily browser sessions, maximum '+fmt(max));
    const title=document.createElementNS(NS,'title');title.textContent=report.daily.map(d=>d.day+': '+d.sessions+' sessions').join('; ');svg.append(title);
    [20,75,130].forEach(y=>{const l=document.createElementNS(NS,'line');for(const [k,v]of Object.entries({x1:0,x2:480,y1:y,y2:y,stroke:'#e8ede4'}))l.setAttribute(k,v);svg.append(l);});
    const points=vals.map((v,i)=>(i*480/Math.max(1,vals.length-1))+','+(135-110*v/max)).join(' '),poly=document.createElementNS(NS,'polyline');for(const[k,v]of Object.entries({points,fill:'none',stroke:'#1f4d3a','stroke-width':2.5,'stroke-linejoin':'round'}))poly.setAttribute(k,v);svg.append(poly);host.append(svg);
    const labs=el('div','chart-labels');labs.append(el('span','',report.daily[0].day),el('span','',report.daily.at(-1).day));host.append(labs);
  }
  async function loadReport(){
    const version=++requestVersion;$('load-status').className='notice';$('load-status').textContent=LIVE?'Loading reports…':'Preview only · sample data, not your website performance.';
    try{const r=LIVE?await api('/report?days='+$('days').value+'&environment='+$('environment').value):demoReport();if(version!==requestVersion)return;report=r;renderReport();$('connection-label').textContent=LIVE?'Private connection':'Design preview';$('load-status').textContent=LIVE?(r.collection_enabled?'Collection connected. ':'Visitor collection is OFF. ')+ 'Production and test orders are separated. Revenue uses verification time. Queues show all dates in this workspace.':'Fictional examples · try an order from proof to delivery. Nothing is sent or paid. Dates are illustrative, not performance targets.';}
    catch(e){if(version!==requestVersion)return;$('load-status').className='notice error';$('load-status').textContent=e.message+' Last displayed data, if any, is stale.';}
  }
  function renderOrdersShell(){
    const host=$('panel-'+active);host.replaceChildren();const panel=el('section','panel');
    panel.append(el('h2','',active==='payments'?'Your payment queue':active==='delivery'?'Guides waiting to be sent':'Your order book'),el('p','caption','Oldest first · waiting time starts at the relevant event, not always at order creation.'));
    const form=el('form','toolbar');form.id='search-form';const l=el('label','','Find an order'),input=el('input');input.id='order-search';input.placeholder='Name, phone or order number';input.maxLength=100;l.append(input);const sl=el('label','','Queue'),sel=el('select');sel.id='order-status';
    const options=active==='payments'?[['UNDER_REVIEW','Proofs to verify'],['CLAIMED_NO_PROOF','Says paid · proof not recorded'],['AWAITING_PAYMENT','No payment statement'],['PAYMENT_REJECTED','Rejected']]:active==='delivery'?[['DELIVERY_DUE','Payment verified · to deliver'],['DELIVERED','Delivered']]:[['all','All orders'],['CLAIMED_NO_PROOF','Says paid · proof not recorded'],...Object.entries(labels)];
    options.forEach(([v,t])=>{const o=el('option','',t);o.value=v;sel.append(o);});sl.append(sel);const submit=el('button','secondary','Search');submit.type='submit';form.append(l,sl,submit);form.onsubmit=e=>{e.preventDefault();offset=0;loadOrders();};sel.onchange=()=>{offset=0;loadOrders();};panel.append(form);
    const body=el('div');body.id='order-table';panel.append(body);const pager=el('div','pager');pager.id='pager';panel.append(pager);host.append(panel);
  }
  function matchesQueue(r,status){return status==='all'||(status==='DELIVERED'?!!r.delivered_at:status==='DELIVERY_DUE'?r.payment_status==='PAYMENT_CONFIRMED'&&!r.delivered_at:status==='CLAIMED_NO_PROOF'?r.payment_status==='AWAITING_PAYMENT'&&!!r.payment_claimed_at:status==='AWAITING_PAYMENT'?r.payment_status==='AWAITING_PAYMENT'&&!r.payment_claimed_at:r.payment_status===status);}
  function badgeFor(r){return el('span','status '+(r.delivered_at||r.payment_status==='PAYMENT_CONFIRMED'?'good':r.payment_status==='PAYMENT_REJECTED'?'issue':'pending'),statusOf(r));}
  async function loadOrders(){
    if(!$('order-search'))return;
    const version=++ordersVersion,tab=active,q=$('order-search').value,status=$('order-status').value;
    $('order-table').replaceChildren(el('p','caption','Loading orders…'));
    try{
      const result=LIVE?await api('/orders?q='+encodeURIComponent(q)+'&status='+status+'&environment='+$('environment').value+'&offset='+offset):{orders:demoOrders().filter(r=>matchesQueue(r,status)&&(!q||(r.customer_name+' '+r.mobile_e164+' '+r.code).toLowerCase().includes(q.toLowerCase()))).sort((a,b)=>new Date(a.waiting_since||a.created_at)-new Date(b.waiting_since||b.created_at)),has_more:false};
      if(active!==tab||version!==ordersVersion)return;rows=result.orders;hasMore=result.has_more;
      const host=$('order-table');host.replaceChildren();
      if(!rows.length)host.append(empty('Nothing waiting here',LIVE?'Try another queue or search.':'No example orders match this queue. Switch to Production or show sample data.'));
      else{
        const desktop=el('div','table-wrap desktop-orders');desktop.append(table(['Parent / order','Payment','Status','Waiting time',''],rows.map(r=>{const person=el('div');person.append(el('strong','',r.customer_name),el('small','',r.mobile_e164),el('small','',r.code));const pay=el('div','',fmt(r.amount_etb)+' ETB');pay.append(el('small','',r.method==='bank'?'CBE':'Telebirr'));return [person,pay,badgeFor(r),el('span','wait'+(r.payment_status==='PAYMENT_CONFIRMED'&&!r.delivered_at?' delivery':''),waitText(r)),button('Review order →',()=>openOrder(r))];})));host.append(desktop);
        const cards=el('div','order-cards');rows.forEach(r=>{const card=el('article','order-card'),head=el('div','order-card-head'),person=el('div');person.append(el('strong','',r.customer_name),el('p','',r.mobile_e164));head.append(person,badgeFor(r));card.append(head,el('p','',fmt(r.amount_etb)+' ETB · '+(r.method==='bank'?'CBE':'Telebirr')),el('p','',r.code));const bottom=el('div','order-card-bottom');bottom.append(el('span','wait'+(r.payment_status==='PAYMENT_CONFIRMED'&&!r.delivered_at?' delivery':''),waitText(r)),button('Review →',()=>openOrder(r),'secondary'));card.append(bottom);cards.append(card);});host.append(cards);
      }
      $('pager').replaceChildren(button('← Previous',()=>{offset=Math.max(0,offset-50);loadOrders();},'secondary'),el('span','','Page '+(1+offset/50)),button('Next →',()=>{offset+=50;loadOrders();},'secondary'));$('pager').firstChild.disabled=offset===0;$('pager').lastChild.disabled=!hasMore;
    }catch(e){if(active===tab&&version===ordersVersion)$('order-table').replaceChildren(empty('Orders unavailable',e.message));}
  }
  function field(form,label,name,type='text',value='',required=true){const l=el('label','',label),input=el('input');input.name=name;input.type=type;input.value=value;input.required=required;l.append(input);form.append(l);return input;}
  function check(form,label,name){const l=el('label','check'),input=el('input');input.type='checkbox';input.name=name;input.required=true;l.append(input,el('span','',label));form.append(l);}
  const post=(path,data)=>api(path,{method:'POST',body:JSON.stringify(data)});
  async function refreshWorkspace(code,message){
    const result=LIVE?await api('/orders/'+encodeURIComponent(code)):{order:demoState.find(r=>r.code===code)};
    if(!$('order-dialog').open||currentOrder?.code!==code)return;
    await openOrder(result.order,message);
    await loadReport();await loadOrders();
  }
  function actionForm(title,cta,handler,simulate){
    const form=el('form','action-form');form.append(el('h3','',title));const submit=el('button','primary',(LIVE?'':'Try: ')+cta);submit.type='submit';form.finish=()=>form.append(submit);
    form.onsubmit=async e=>{
      e.preventDefault();if(LIVE&&!report?.actions_enabled)return;
      const code=currentOrder.code,r=currentOrder;$('action-error').textContent='';
      $('detail-body').querySelectorAll('button').forEach(b=>b.disabled=true);
      try{if(LIVE)await handler(new FormData(form));else await simulate?.(new FormData(form),r);
        try{await refreshWorkspace(code,(LIVE?'Saved. ':'Example updated. ')+cta+'.');}catch{ $('action-error').textContent='Action saved, but the latest order could not be loaded. Refresh before continuing.';return; }
      }catch(err){if(currentOrder?.code!==code||!$('order-dialog').open)return;$('action-error').textContent=err.message;submit.disabled=false; // no automatic mutation retry
        if(LIVE)try{const latest=(await api('/orders/'+encodeURIComponent(code))).order;if(latest.evidence_id!==r.evidence_id||latest.payment_status!==r.payment_status||latest.delivered_at!==r.delivered_at)await openOrder(latest,'The server has a saved change. Review the current state before continuing.');}catch{}
      }finally{if(form.isConnected)$('detail-body').querySelectorAll('button').forEach(b=>b.disabled=LIVE&&!report?.actions_enabled);}
    };return form;
  }
  const details=(label)=>{const d=el('details','disclosure');d.append(el('summary','',label));return d;};
  async function openOrder(r,message=''){
    const version=++workspaceVersion;currentOrder=r;
    $('detail-title').textContent=r.customer_name;$('action-error').textContent='';const host=$('detail-body');host.replaceChildren();
    if(message)host.append(el('p','inline-success',message));
    if(!LIVE)host.append(el('p','notice','Simulation only · no actual payment is approved and no guides are sent. Changes reset on reload.'));
    else if(!report?.actions_enabled)host.append(el('p','notice','Payment and delivery actions are disabled by server configuration.'));
    const progress=el('div','workspace-progress');
    const stage=r.delivered_at?4:r.payment_status==='PAYMENT_CONFIRMED'?3:r.evidence_id?2:r.claim_id?1:0;
    ['Proof','Check transaction','Verify payment','Deliver guides'].forEach((t,i)=>progress.append(el('span',i<stage?'done':i===stage?'current':'',(i<stage?'✓ ':'')+t)));
    host.append(progress);
    const grid=el('div','detail-grid');[['Order',r.code],['Checkout phone',r.mobile_e164],['Expected payment',fmt(r.amount_etb)+' ETB · '+(r.method==='bank'?'CBE':'Telebirr')],['Status',statusOf(r)],['Waiting time',waitText(r)],['Created · Addis Ababa',date(r.created_at)]].forEach(([a,b])=>{const d=el('div');d.append(el('small','',a),el('strong','',b));grid.append(d);});host.append(grid);
    if(['AWAITING_PAYMENT','PAYMENT_REJECTED'].includes(r.payment_status)){
      const form=actionForm('Record the proof received in Telegram','Record proof',d=>post('/telegram-proof',{order_id:r.code,transaction_reference:d.get('reference')}),(d,row)=>Object.assign(row,{payment_status:'UNDER_REVIEW',claim_id:'example-claim',proof_recorded_at:new Date().toISOString(),waiting_since:new Date().toISOString()}));
      field(form,'Transaction reference on the receipt','reference');check(form,'The Telegram name and checkout phone match this order.','matched');form.finish();host.append(form);
    }
    if(r.payment_status==='UNDER_REVIEW'&&!r.evidence_id){
      const form=actionForm('Check your actual Telebirr / CBE records','Save transaction check',d=>post('/settlements',{order_id:r.code,claim_id:r.claim_id,observed_reference:d.get('reference'),payment_method:r.method,amount_etb:Number(d.get('amount')),currency:'ETB',recipient_confirmed:d.has('recipient'),manual_reconciliation_completed:d.has('reconciled'),payer_mobile:d.get('payer'),evidence_source:r.method==='bank'?'BANK_STATEMENT':'TELEBIRR_PORTAL',settled_at:new Date(d.get('settled')+':00+03:00').toISOString(),note:d.get('note')||''}),(d,row)=>Object.assign(row,{evidence_id:'example-evidence',observed_amount_etb:Number(d.get('amount')),payer_mismatch:d.get('payer')!==row.mobile_e164,settled_at:new Date(d.get('settled')+':00+03:00').toISOString()}));
      form.append(el('p','form-help','Enter what you actually see in your payment records. Expected values above are for comparison only.'));
      const fg=el('div','form-grid');form.append(fg);
      const ref=field(fg,'Actual transaction reference','reference');ref.placeholder='From your own transaction records';
      const amount=field(fg,'Actual amount received (ETB)','amount','number');amount.min='0';amount.step='1';amount.placeholder='Enter received amount';
      const payer=field(fg,'Actual payer phone (+251…)','payer','tel');payer.pattern='\\+251[97][0-9]{8}';payer.placeholder='+251…';
      field(fg,'Settlement time · Addis Ababa','settled','datetime-local');
      const warning=el('p','field-warning');warning.setAttribute('role','status');form.append(warning);
      const validate=()=>{const msgs=[];amount.setCustomValidity('');
        if(amount.value&&Number(amount.value)!==r.amount_etb){msgs.push('Amount does not match '+fmt(r.amount_etb)+' ETB. This order cannot be verified.');amount.setCustomValidity('Received amount must match this order.');}
        if(payer.value&&payer.value!==r.mobile_e164)msgs.push('Payer differs from checkout phone. A documented third-party payer exception will be required before verification.');warning.textContent=msgs.join(' ');};amount.oninput=validate;payer.oninput=validate;
      form.append(el('p','form-help','If the provider does not show the full payer phone, stop here. Do not copy the checkout phone as a substitute. This workflow needs the existing identity check; alternate evidence is not yet supported.'));
      check(form,'Recipient name and number match the configured business account.','recipient');check(form,'I checked the reference, amount, time and payer in my own payment records.','reconciled');form.finish();host.append(form);
    }
    if(r.payment_status==='UNDER_REVIEW'&&r.evidence_id){
      host.append(el('p','expected-line','Recorded amount: '+fmt(r.observed_amount_etb)+' ETB'+(r.settled_at?' · Settlement: '+date(r.settled_at):'')+'. The next action records your final verification decision.'));
      if(r.payer_mismatch&&!r.third_party_exception_id){
        const ex=actionForm('The payer differs from the buyer','Save payer exception',d=>post('/third-party-exceptions',{order_id:r.code,claim_id:r.claim_id,evidence_id:r.evidence_id,relationship:d.get('relationship'),rationale:d.get('rationale')}),(d,row)=>row.third_party_exception_id='example-exception');
        const rl=el('label','','Relationship'),rs=el('select');rs.name='relationship';[['SPOUSE','Spouse'],['RELATIVE','Relative'],['OTHER','Other']].forEach(([v,t])=>{const o=el('option','',t);o.value=v;rs.append(o);});rl.append(rs);ex.append(rl);const note=field(ex,'Explain how this payment belongs to this buyer','rationale');note.minLength=10;ex.finish();host.append(ex);
      }
      if(Number(r.observed_amount_etb)!==r.amount_etb)host.append(el('p','field-warning','Recorded amount does not match this order. Verification is blocked. Record a support note or reject the claim.'));
      if(Number(r.observed_amount_etb)===r.amount_etb&&(!r.payer_mismatch||r.third_party_exception_id)){
        const form=actionForm('Verify payment','Verify payment',d=>post('/approve',{order_id:r.code,claim_id:r.claim_id,evidence_id:r.evidence_id,reason:d.get('reason'),third_party_exception_id:r.third_party_exception_id||null}),(d,row)=>Object.assign(row,{payment_status:'PAYMENT_CONFIRMED',fulfillment_status:'READY_TO_DOWNLOAD',verified_at:new Date().toISOString(),waiting_since:new Date().toISOString()}));
        const note=field(form,'Your decision note','reason');note.placeholder='Write why this transaction is a confirmed match';note.minLength=10;check(form,'The actual transaction is verified. Record this as a sale.','confirm');form.finish();host.append(form);
      }
    }
    if(r.payment_status==='UNDER_REVIEW'){
      const reject=details('Payment does not match?');
      const form=actionForm('Record rejection','Reject payment',d=>post('/reject',{order_id:r.code,claim_id:r.claim_id,reason:d.get('reason')}),(d,row)=>Object.assign(row,{payment_status:'PAYMENT_REJECTED',claim_id:null,evidence_id:null}));const reason=field(form,'Reason for rejection','reason');reason.minLength=10;form.finish();reject.append(form);host.append(reject);
    }
    if(r.payment_status==='PAYMENT_CONFIRMED'&&!r.delivered_at&&r.fulfillment_status!=='REVOKED'){
      const form=actionForm('Send the five PDFs in the matched Telegram chat','Mark guides delivered',()=>post('/manual-delivery',{order_id:r.code,all_five_pdfs_sent:true}),(_,row)=>row.delivered_at=new Date().toISOString());
      form.append(el('p','form-help','This action records delivery. It does not send files for you.'));check(form,'I have sent all five PDFs to this customer in Telegram.','sent');form.finish();host.append(form);
    }
    if(r.delivered_at)host.append(el('p','notice success','All five guides marked sent · '+date(r.delivered_at)));
    const support=details('Order notes & support');const notesBox=el('div');support.append(notesBox);
    const noteForm=actionForm('Add an internal note','Save note',d=>post('/orders/'+encodeURIComponent(r.code)+'/notes',{note:d.get('note')}),(d,row)=>{const list=demoNotes.get(row.code)||[];list.unshift({text:d.get('note'),created_at:new Date().toISOString()});demoNotes.set(row.code,list);});const note=field(noteForm,'Support issue or matching information','note');note.maxLength=1000;note.placeholder='For example: wrong phone or Telegram chat identity';noteForm.finish();support.append(noteForm);host.append(support);
    const history=details('Payment & delivery history');const histBox=el('div');history.append(histBox);host.append(history);
    const foot=$('workspace-footer');foot.replaceChildren(el('p','caption',LIVE?'Changes are saved individually with an audit record.':'Example order · safe to explore.'));
    foot.append(button('Next order →',()=>{const next=rows.find(x=>x.code!==r.code);if(next)openOrder(next);else $('order-dialog').close();},'secondary'));
    if(LIVE&&!report?.actions_enabled)host.querySelectorAll('form input,form button,form select').forEach(e=>e.disabled=true);
    if(!$('order-dialog').open)$('order-dialog').showModal();
    if(LIVE){
      const results=await Promise.allSettled([api('/orders/'+encodeURIComponent(r.code)+'/notes'),api('/orders/'+encodeURIComponent(r.code)+'/history')]);
      if(version!==workspaceVersion||!$('order-dialog').open)return;
      const n=results[0],h=results[1];if(n.status==='fulfilled')renderNotes(notesBox,n.value.notes);else notesBox.append(el('p','caption','Notes unavailable.'));
      if(h.status==='fulfilled')h.value.events.forEach(e=>{const item=el('div','history-item',e.event_type.replaceAll('_',' '));item.append(el('small','',date(e.occurred_at)+' · '+e.actor_type));histBox.append(item);});else histBox.append(el('p','caption','History unavailable.'));
    }else{renderNotes(notesBox,demoNotes.get(r.code)||[]);histBox.append(el('p','caption','This is a simulated order. Live event history appears only after connection.'));}
  }
  function renderNotes(host,notes){if(!notes.length)host.append(el('p','caption','No notes yet.'));notes.forEach(n=>{const item=el('div','note-item',n.text);item.append(el('small','',date(n.created_at)));host.append(item);});}
  $('close-dialog').onclick=()=>$('order-dialog').close();
  $('days').onchange=loadReport;$('environment').onchange=()=>{loadReport();if(active==='marketing')loadSpendDate();if(['orders','payments','delivery'].includes(active)){offset=0;loadOrders();}};$('refresh').onclick=()=>{loadReport();if(['orders','payments','delivery'].includes(active))loadOrders();};
  $('demo-toggle').onclick=()=>{emptyDemo=!emptyDemo;$('demo-toggle').textContent=emptyDemo?'Show sample data':'Show empty state';loadReport();if(['orders','payments','delivery'].includes(active))loadOrders();};
  $('logout-top').onclick=async()=>{try{await api('/session',{method:'DELETE'});clearPrivate();}catch(e){$('load-status').textContent=e.message;}};
  $('login-form').onsubmit=async e=>{e.preventDefault();$('login-error').textContent='';const b=e.target.querySelector('button');b.disabled=true;try{const d=new FormData(e.target),res=await api('/session',{method:'POST',body:JSON.stringify(Object.fromEntries(d))});csrf=res.csrf_token;e.target.reset();await start();}catch(err){$('login-error').textContent=err.message;}finally{b.disabled=false;}};
  async function start(){ document.body.classList.toggle('demo-mode',!LIVE);$('login').hidden=true;$('workspace').hidden=false;$('preview-banner').hidden=LIVE;$('logout-top').hidden=false;$('logout-top').disabled=!LIVE;$('spend-save').textContent=LIVE?'Save daily spend':'Try: Save daily spend';await loadReport();switchTab(location.hash.slice(1)||'overview'); }
  async function init(){if(LIVE){try{const s=await api('/session');csrf=s.csrf_token;}catch{$('login').hidden=false;return;}}await start();}
  init();
})();
