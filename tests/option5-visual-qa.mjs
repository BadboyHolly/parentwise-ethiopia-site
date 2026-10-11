import { chromium } from 'playwright';
import fs from 'node:fs';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const report={screenshots:[],errors:[],checks:[],date:new Date().toISOString()};
const base='http://127.0.0.1:8765/';
fs.mkdirSync('design-qa',{recursive:true});
for(const width of [320,360,375,390,414,430,768,1440]){
 const page=await browser.newPage({viewport:{width,height:880},deviceScaleFactor:1,reducedMotion:'reduce'});
 const err=[];page.on('pageerror',e=>err.push(e.message));
 await page.goto(base,{waitUntil:'domcontentloaded',timeout:45000});
 await page.waitForTimeout(1200);
 const data=await page.evaluate(()=>({
  clientWidth:document.documentElement.clientWidth,
  scrollWidth:document.documentElement.scrollWidth,
  problems:document.querySelectorAll('.challenge-card').length,
  method:document.querySelectorAll('.method-step').length,
  faq:document.querySelectorAll('.faq-list details').length,
  links:document.querySelectorAll('a[href="order.html"]').length,
  refs:document.querySelectorAll('.reference-list a').length,
  pdfPreviews:document.querySelectorAll('[data-product-preview]').length,
  sections:document.querySelectorAll('main > section').length,
  hasOldCards:document.querySelectorAll('.problem-grid,.credibility-layer,.use-grid').length,
  video:!!document.getElementById('option5-intro-player'),
  overflowElements:[...document.querySelectorAll('body *')].map(e=>({el:e,box:e.getBoundingClientRect()})).filter(x=>x.box.right>innerWidth+1 && x.box.width>0 && getComputedStyle(x.el).position!=='absolute').slice(0,15).map(x=>({tag:x.el.tagName,cl:String(x.el.className).slice(0,80),text:x.el.textContent?.trim().slice(0,35),right:Math.round(x.box.right),width:Math.round(x.box.width)})),
  primaryHeading:document.querySelector('h1')?.textContent?.trim()
 }));
 if(data.scrollWidth>width+1)err.push('HORIZONTAL_OVERFLOW: '+data.scrollWidth+' > '+width);
 if(data.problems!==6||data.method!==6||data.faq!==9||data.refs!==9||data.pdfPreviews!==4||data.hasOldCards!==0)err.push('CONTENT_INTEGRITY_FAILED '+JSON.stringify(data));
 if(width===390){
  await page.screenshot({path:'design-qa/mobile-390-full.png',fullPage:true});
  for(const [name,sel] of [['hero','.hero'],['challenges','.familiar'],['advice','.advice'],['ways','.now-later'],['research','.evidence'],['buying','.buying'],['faq','.faq']]){
   await page.locator(sel).screenshot({path:'design-qa/mobile-390-'+name+'.png'});
  }
  // Test menu and Esc close
  await page.locator('.menu-button').click();
  if(await page.locator('#mobile-menu').isHidden())err.push('MENU_DID_NOT_OPEN');
  await page.keyboard.press('Escape');
  if(await page.locator('#mobile-menu').isVisible())err.push('MENU_DID_NOT_CLOSE');
  // Dialog fallback, never pretend playback
  await page.locator('#option5-intro-open').click();
  if(!await page.locator('#option5-intro-dialog').isVisible())err.push('VIDEO_DIALOG_MISSING');
  if(!await page.locator('#option5-video-unavailable').isVisible())err.push('MISSING_VIDEO_DISCLOSURE');
  await page.locator('[data-intro-close]').click();
  if(await page.locator('#option5-intro-dialog').isVisible())err.push('VIDEO_DIALOG_CLOSE_FAILED');
  // Existing product dialog support
  await page.locator('[data-product-preview]').first().click();
  if(!await page.locator('#product-preview-dialog').isVisible())err.push('PRODUCT_DIALOG_MISSING');
  await page.locator('[data-close-product-preview]').click();
  if(await page.locator('#product-preview-dialog').isVisible())err.push('PRODUCT_DIALOG_CLOSE_FAILED');
 }
 if(width===1440)await page.screenshot({path:'design-qa/desktop-1440-full.png',fullPage:true});
 report.checks.push({width,data,errors:err});
 report.errors.push(...err.map(x=>width+': '+x));
 await page.close();
}
await browser.close();
fs.writeFileSync('design-qa/report.json',JSON.stringify(report,null,2));
console.log(JSON.stringify({pass:report.errors.length===0,checks:report.checks,errors:report.errors},null,2));
if(report.errors.length)process.exitCode=1;