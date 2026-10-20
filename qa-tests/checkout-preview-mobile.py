"""Visual and interaction acceptance for locked Telegram-first checkout V1 preview.

Tests are strictly synthetic: no payments, orders, data capture, or PDF downloads.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8765/order.html"
OUTPUT = Path("qa-artifacts/checkout-preview")
OUTPUT.mkdir(parents=True, exist_ok=True)

def check_viewport(page, width):
    writes = []
    page.on("request", lambda request: writes.append((request.method, request.url)) if request.method not in ("GET","HEAD") else None)
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    assert page.locator("html").get_attribute("lang") == "am"
    assert page.locator("#details-section").is_visible()
    assert page.locator("#payment-section").is_hidden()
    assert page.locator("#telegram-section").is_hidden()
    assert page.get_by_text("DEMO ONLY", exact=False).count() >= 1
    assert page.locator("#prepay-telegram").get_attribute("href") == "https://t.me/ParentWiseEthiopia"
    assert page.locator("#prepay-telegram").get_attribute("target") == "_blank"
    assert page.locator("#customer-name").input_value() == ""
    assert page.locator("#customer-mobile").input_value() == ""
    assert page.locator("#recipient-number").is_hidden()
    assert page.evaluate("(w) => document.documentElement.scrollWidth <= w + 1", width)
    for path in ["assets/logo-reversed.webp", "assets/telebirr-mark.svg", "assets/cbe-bank-logo.png", "assets/product-workbook.webp"]:
        img=page.locator('img[src="'+path+'"]').first
        img.evaluate("(el) => el.decode()")
        assert img.evaluate("(el) => el.naturalWidth > 0"), f"Missing asset: {path}"
    page.screenshot(path=str(OUTPUT / f"v1-{width}-01-details.png"), full_page=True, animations="disabled")
    page.locator("#continue-payment").click()
    assert page.locator("#validation-error").is_visible()
    page.locator("#customer-name").fill("Demo Parent")
    page.locator("#customer-mobile").fill("0900000000")
    page.locator('input[name="payment"][value="bank"]').check()
    page.locator("#continue-payment").click()
    assert page.locator("#payment-section").is_visible()
    assert page.locator("#details-section").is_hidden()
    assert page.locator("#recipient-number").inner_text() == "QA-CBE-ONLY"
    assert page.locator("#selected-method").inner_text() == "CBE Bank"
    assert page.locator("#recipient-holder").inner_text() == "DEMO RECIPIENT — NOT REAL"
    assert page.locator("#paid-action").is_enabled()
    page.screenshot(path=str(OUTPUT / f"v1-{width}-02-cbe-payment.png"), full_page=True, animations="disabled")
    page.locator("#change-method").click()
    assert page.locator("#customer-name").input_value() == "Demo Parent"
    assert page.locator("#customer-mobile").input_value() == "0900000000"
    page.locator('input[name="payment"][value="telebirr"]').check()
    page.locator("#continue-payment").click()
    assert page.locator("#recipient-number").inner_text() == "QA-TELEBIRR-ONLY"
    assert page.locator("#selected-method").inner_text() == "Telebirr"
    page.screenshot(path=str(OUTPUT / f"v1-{width}-02-telebirr-payment.png"), full_page=True, animations="disabled")
    page.locator("#paid-action").click()
    assert page.locator("#telegram-section").is_visible()
    assert page.locator("#payment-section").is_hidden()
    assert page.locator("#label-telegram").get_attribute("class") == "active"
    note=page.locator("#confirmation-message").inner_text()
    assert "Demo Parent" in note and "0900000000" in note
    assert "Telebirr" in note and "1,500 ETB" in note
    assert "[attach or add here]" in note
    assert page.locator("#telegram-handoff").get_attribute("href") == "https://t.me/ParentWiseEthiopia"
    assert page.locator("#telegram-handoff").get_attribute("target") == "_blank"
    assert page.locator("#telegram-handoff").get_attribute("rel") == "noopener noreferrer"
    assert page.locator("#copy-confirmation").is_enabled()
    page.screenshot(path=str(OUTPUT / f"v1-{width}-03-telegram.png"), full_page=True, animations="disabled")
    assert page.evaluate("(w) => document.documentElement.scrollWidth <= w + 1", width)
    assert not writes, f"Unexpected data transfer in visual preview: {writes}"
    print(f"PASS {width}px: validated details, method switch, one recipient, Telegram handoff, no network writes", flush=True)

def main():
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        for width in (320, 360, 390, 768, 1280):
            context=browser.new_context(viewport={"width":width,"height":850},is_mobile=width<=390,has_touch=width<=390,device_scale_factor=2 if width<=390 else 1)
            check_viewport(context.new_page(),width)
            context.close()
        browser.close()
    print("PASS ParentWise V1 Telegram manual fulfillment preview",flush=True)

if __name__ == "__main__":
    main()
