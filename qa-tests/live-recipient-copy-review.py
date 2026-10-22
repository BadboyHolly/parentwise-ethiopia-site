"""Browser checks for the intended public preview with founder-directed payment details.

The site has NO order database. This test must never initiate a transfer or send a Telegram message.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:8765"
OUT=Path("qa-artifacts/real-payment-copy")
OUT.mkdir(parents=True, exist_ok=True)
WARNINGS=("DEMO ONLY","No orders","QA TEST ONLY","የሙከራ ገጽ","እውነተኛ ክፍያ አይፈጽሙ","ገንዘብ አይላኩ","Visual-only preview","QA-CBE-ONLY","QA-TELEBIRR-ONLY")
def check(browser,width):
  context=browser.new_context(viewport={"width":width,"height":850},device_scale_factor=1,is_mobile=width<=390,has_touch=width<=390)
  page=context.new_page()
  page.add_init_script("""
    window.__clipboardWrites = [];
    Object.defineProperty(navigator, 'clipboard', {
      configurable:true, value: {writeText: async v => window.__clipboardWrites.push(v)}
    });
  """)
  writes=[]
  page.on("request", lambda r: writes.append((r.method,r.url)) if r.method not in ("GET","HEAD") else None)
  page.goto(BASE+"/",wait_until="domcontentloaded",timeout=45000)
  assert "ParentWise Ethiopia" in page.title()
  assert page.locator("#hero").count()==1
  assert "QA TEST ONLY" not in page.locator("body").inner_text()
  assert page.locator(".pw10x-cta").count()>0
  assert page.locator(".pw10x-cta").evaluate_all("(els)=>els.every(x=>x.getAttribute('href')==='order.html')")
  assert page.evaluate("(w)=>document.documentElement.scrollWidth <= w+1",width)
  page.locator(".pw10x-cta").first.click(timeout=30000)
  page.wait_for_url("**/order.html")
  assert page.locator("#checkout-form").is_visible()
  assert page.locator("#payment-section").is_hidden()
  assert page.locator("a.brand").get_attribute("href")=="./"
  text=page.locator("body").inner_text()
  assert all(term not in text for term in WARNINGS),[x for x in WARNINGS if x in text]
  page.locator("#customer-name").fill("QA Owner Test")
  page.locator("#customer-mobile").fill("0912345678")
  page.locator("#continue-payment").click()
  assert page.locator("#payment-section").is_visible()
  assert page.locator("#recipient-number").inner_text()=="0912910693"
  assert page.locator("#recipient-holder").inner_text()=="KIDUS ELIAS"
  page.locator("#copy-recipient").click()
  assert page.evaluate("window.__clipboardWrites.at(-1)")=="0912910693"
  assert "አይላኩ" not in page.locator("#copy-status").inner_text()
  page.locator("#change-method").click()
  page.locator('input[name="payment"][value="bank"]').check()
  page.locator("#continue-payment").click()
  assert page.locator("#recipient-number").inner_text()=="1000223019327"
  assert page.locator("#recipient-holder").inner_text()=="KIDUS ELIAS"
  page.locator("#copy-recipient").click()
  assert page.evaluate("window.__clipboardWrites.at(-1)")=="1000223019327"
  page.locator("#paid-action").click()
  assert page.locator("#telegram-section").is_visible()
  assert "QA Owner Test" in page.locator("#confirmation-message").inner_text()
  assert "0912345678" in page.locator("#confirmation-message").inner_text()
  assert "CBE Bank" in page.locator("#confirmation-message").inner_text()
  assert page.locator("#telegram-handoff").get_attribute("href")=="https://t.me/ParentWiseEthiopia"
  page.locator("#copy-confirmation").click()
  assert "QA Owner Test" in page.evaluate("window.__clipboardWrites.at(-1)")
  assert page.evaluate("(w)=>document.documentElement.scrollWidth <= w+1",width)
  assert not writes, writes
  if width in (390,1280):
    page.screenshot(path=str(OUT/f"account-checkout-{width}.png"),animations="disabled",full_page=False)
  context.close()
  print(f"PASS {width}px sales > checkout > correct Telebirr/CBE > Telegram copy, no network writes",flush=True)
if __name__=="__main__":
  with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width in (320,360,390,768,1280): check(browser,width)
    browser.close()
  print("PASS real account display and removal of visible QA warning text; static checkout only",flush=True)
