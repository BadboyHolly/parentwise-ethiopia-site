"""ParentWise static preview: full three-step demo (NO real orders, payments, backend)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8765/order.html"
OUT = Path("qa-artifacts/checkout-preview")
OUT.mkdir(parents=True, exist_ok=True)

def check_page(page, width):
    requests = []
    page.on("request", lambda r: requests.append((r.method, r.url)) if r.method not in ("GET", "HEAD") else None)
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    assert page.locator("#order-form").is_visible()
    assert page.locator("#staging-payment").is_hidden()
    assert page.locator(".statusbar").inner_text().count("DEMO") >= 1
    assert "እውነተኛ ክፍያ አይፈጽሙ" in page.locator(".statusbar").inner_text()
    assert page.locator("#customer-name").input_value() == "Demo Parent"
    assert page.locator("#customer-mobile").input_value() == "0900000000"
    assert page.evaluate("(w)=>document.documentElement.scrollWidth<=w+1",width)
    page.screenshot(path=str(OUT / f"demo-{width}-01-details.png"), full_page=True)
    page.locator("#continue-order-button").click()
    assert page.locator("#stage-recovery-code-panel").is_visible()
    assert page.locator("#payment-details").is_hidden()
    details = page.locator("#stage-order-recovery").input_value()
    assert "Order number: PW-" in details
    assert "Private recovery code: " in details
    page.locator("#stage-hide-recovery").click()
    assert page.locator("#stage-order-recovery").input_value() == ""
    assert page.locator("#stage-show-recovery").is_visible()
    page.locator("#stage-show-recovery").click()
    assert page.locator("#stage-order-recovery").input_value() == details
    page.screenshot(path=str(OUT / f"demo-{width}-02-save.png"), full_page=True)
    page.locator("#stage-continue-payment").click()
    assert page.locator("#payment-details").is_visible()
    assert page.locator("#account-number").inner_text() == "QA-TELEBIRR-ONLY"
    assert page.locator("#account-holder").inner_text().startswith("DEMO ONLY")
    page.screenshot(path=str(OUT / f"demo-{width}-02-pay.png"), full_page=True)
    page.locator("#stage-ive-paid").click()
    assert page.locator("#stage-claim-form").is_visible()
    assert page.locator("#stage-reference").input_value() == "SIM-DEMO-123"
    page.locator("#stage-claim-form button[type=submit]").click()
    assert page.locator("#demo-approve").is_visible()
    assert "Under Review" in page.locator("#stage-status").inner_text()
    page.screenshot(path=str(OUT / f"demo-{width}-02-pending.png"), full_page=True)
    page.locator("#demo-approve").click()
    assert page.locator("#stage-download-panel").is_visible()
    assert page.locator("#staging-payment-title").inner_text().startswith("03")
    assert page.locator("#stage-download-list button").count() == 5
    assert page.locator(".steps .step.current").inner_text().startswith("03")
    page.screenshot(path=str(OUT / f"demo-{width}-03-guides.png"), full_page=True)
    with page.expect_download() as dl:
        page.locator("#stage-download-list button").first.click()
    download = dl.value
    assert download.suggested_filename == "PARENTWISE-DEMO-00.pdf"
    dest = OUT / f"demo-{width}-00.pdf"
    download.save_as(dest)
    assert dest.read_bytes().startswith(b"%PDF-1.4")
    assert b"DEMO ONLY" in dest.read_bytes()
    assert page.evaluate("(w)=>document.documentElement.scrollWidth<=w+1",width)
    assert requests == [], f"Unexpected non-GET network requests: {requests}"
    print(f"PASS {width}px: all 3 stages, fictional recipient, pending, five guides, demo PDF, no requests", flush=True)

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for width in (320,360,390,768,1280):
            context = browser.new_context(viewport={"width":width,"height":850},accept_downloads=True,
                                          is_mobile=width<=390,has_touch=width<=390)
            check_page(context.new_page(),width)
            context.close()
        browser.close()
    print("PASS demo preview; no actual orders, payment, or API requests", flush=True)

if __name__ == "__main__":
    main()
