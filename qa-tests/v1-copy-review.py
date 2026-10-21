"""Copy-only sales-to-checkout review: synthetic data and no payment writes."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = "http://127.0.0.1:8765"
OUT = Path("qa-artifacts/v1-copy-review")
OUT.mkdir(parents=True, exist_ok=True)

def run(browser, width):
    context = browser.new_context(viewport={"width":width,"height":870},device_scale_factor=1,
                                  is_mobile=width<=390,has_touch=width<=390)
    page = context.new_page()
    non_reads = []
    page.on("request",lambda r: non_reads.append(f"{r.method} {r.url}") if r.method not in ("GET","HEAD") else None)
    page.goto(ROOT+"/index.html",wait_until="domcontentloaded",timeout=45000)
    assert page.title().startswith("ParentWise Ethiopia")
    assert page.locator("#hero").count() == 1
    for i in range(2,12):
        assert page.locator(f"#section-{i:02}").count() == 1, i
    assert page.locator(".pw10x-cta").get_attribute("href") == "order.html"
    assert page.locator("#section-10").inner_text().count("የትዕዛዝ ቁጥር") == 0
    assert page.locator("#section-11").inner_text().count("የትዕዛዝ ቁጥር") == 0
    assert "የ30 ቀን የልምምድ እቅድ" in page.locator("#section-10").inner_text()
    assert "የከፈሉትን 1,500 ብር ሙሉ በሙሉ" not in page.locator("#section-10").inner_text()
    assert "እውነተኛ የባለሙያ ግምገማ አይደለም" in page.locator("#section-09").inner_text()
    assert "ዶ/ር ሜሮን" not in page.locator("#section-09").inner_text()
    assert "ዶ/ር ዮሐንስ" not in page.locator("#section-09").inner_text()
    assert page.evaluate("(w)=>document.documentElement.scrollWidth <= w+1",width)
    if width == 390:
        page.screenshot(path=str(OUT/"sales-390-offer.png"),full_page=False,animations="disabled")
    page.locator(".pw10x-cta").click(timeout=30000)
    page.wait_for_url("**/order.html",timeout=30000)
    assert page.locator("#checkout-form").is_visible()
    assert page.get_by_text("DEMO ONLY",exact=False).count() >= 1
    assert page.locator("#payment-section").is_hidden()
    assert page.locator("#customer-name").input_value() == ""
    assert page.locator("#customer-mobile").input_value() == ""
    assert page.locator('input[name="payment"]').count() == 2
    if width<=390:
        assert page.locator(".product-mobile").is_visible()
    page.screenshot(path=str(OUT/f"checkout-{width}-details.png"),full_page=False,animations="disabled")
    page.locator("#continue-payment").click()
    assert page.locator("#validation-error").is_visible()
    page.locator("#customer-name").fill("QA Test Parent")
    page.locator("#customer-mobile").fill("0912345678")
    page.locator('input[name="payment"][value="bank"]').check()
    page.locator("#continue-payment").click()
    assert page.locator("#payment-section").is_visible()
    assert page.locator("#recipient-number").inner_text() == "QA-CBE-ONLY"
    assert page.locator("#recipient-holder").inner_text() == "DEMO RECIPIENT — NOT REAL"
    assert page.locator("#review-customer-name").inner_text() == "QA Test Parent"
    assert page.locator("#review-customer-phone").inner_text() == "0912345678"
    assert page.locator("#paid-action").is_enabled()
    page.screenshot(path=str(OUT/f"checkout-{width}-bank.png"),full_page=False,animations="disabled")
    page.locator("#change-method").click()
    page.locator('input[name="payment"][value="telebirr"]').check()
    page.locator("#continue-payment").click()
    assert page.locator("#recipient-number").inner_text() == "QA-TELEBIRR-ONLY"
    page.locator("#paid-action").click()
    assert page.locator("#telegram-section").is_visible()
    assert page.locator("#telegram-handoff").get_attribute("href") == "https://t.me/ParentWiseEthiopia"
    assert "QA Test Parent" in page.locator("#confirmation-message").inner_text()
    assert "0912345678" in page.locator("#confirmation-message").inner_text()
    assert "1,500 ETB" in page.locator("#confirmation-message").inner_text()
    assert page.evaluate("(w)=>document.documentElement.scrollWidth <= w+1",width)
    page.screenshot(path=str(OUT/f"checkout-{width}-telegram.png"),full_page=False,animations="disabled")
    assert not non_reads, non_reads
    context.close()
    print(f"PASS {width}px sales -> checkout -> payment -> Telegram copy, no write requests",flush=True)

if __name__ == "__main__":
    sale=Path("index.html").read_text(encoding="utf-8")
    checkout=Path("order.html").read_text(encoding="utf-8")
    assert len(sale)>2000000
    assert "QA TEST ONLY" in sale
    assert "የትዕዛዝ ቁጥር ይሰጥዎታል" not in sale
    assert "የከፈሉትን 1,500 ብር ሙሉ በሙሉ" not in sale
    assert "QA-TELEBIRR-ONLY" in checkout and "QA-CBE-ONLY" in checkout
    assert "0912910693" not in sale+checkout
    assert "1000223019327" not in sale+checkout
    assert "10002230019327" not in sale+checkout
    assert "fetch(" not in checkout and "XMLHttpRequest" not in checkout
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        for width in (320,390,768,1280):
            run(browser,width)
        browser.close()
    print("PASS review only — no real accounts, no real orders, no production activation",flush=True)
