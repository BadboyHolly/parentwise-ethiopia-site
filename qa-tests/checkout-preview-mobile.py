"""Visual and safety acceptance for the *isolated* ParentWise checkout preview.

Runs against locally served checkout branch contents, NOT the QA API.
No order is created and no real banking or payment operation is attempted.
"""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.environ.get("CHECKOUT_PREVIEW_URL", "http://127.0.0.1:8765/order.html")
ARTIFACTS = Path(os.environ.get("CHECKOUT_PREVIEW_ARTIFACTS", "qa-artifacts/checkout-preview"))
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ACCOUNTS = {"telebirr": "0912910693", "bank": "10002230019327"}


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def evaluate_layout(page, width):
    """Detect CSS overflow, unusable controls and missing source assets."""
    page.wait_for_load_state("domcontentloaded")
    page.locator("#account-number").wait_for(state="visible")
    page.locator(".method-logo").first.wait_for(state="visible")
    page.locator(".method-logo-cbe").wait_for(state="visible")
    check(page.locator('html').get_attribute("lang") == "am", "Amharic lang missing")
    check("ParentWise" in page.title(), "Checkout title missing")
    check(page.get_by_role("heading", name="ትዕዛዝዎን ያጠናቅቁ.").count() == 1, "Customer heading missing")
    check(not page.locator(".microtrust").count(), "Removed promotional strip is present")
    check(page.locator("#copy-label").inner_text() == "Copy", "Copy label must be English")
    check(page.locator(".checkoutaction").is_disabled(), "Production order button unexpectedly enabled")
    check(ACCOUNTS["telebirr"] == page.locator("#account-number").inner_text(), "Telebirr account incorrect")
    check(page.locator("#account-holder").inner_text() == "Kidus Elias", "Account holder incorrect")
    check("ገንዘብ አይላኩ" in page.locator(".statusbar").inner_text(), "No-payment guard missing")
    images = page.locator(".method-logo")
    check(images.count() == 2, "Expected two authentic method marks")
    for i in range(2):
        image = images.nth(i)
        image.evaluate("(el) => el.decode()")
        check(image.evaluate("(el) => el.naturalWidth > 0 && el.naturalHeight > 0"), f"Brand image {i} not loaded")
    overflow = page.evaluate("""() => {
      const html = document.documentElement;
      const pageWidth = Math.max(html.scrollWidth, document.body.scrollWidth);
      return {width:innerWidth, scrollWidth:pageWidth, difference:pageWidth-innerWidth};
    }""")
    check(overflow["difference"] <= 1, f"Horizontal overflow at {width}px: {overflow}")
    check(page.locator("#customer-name").is_visible(), "Name field missing")
    check(page.locator("#customer-mobile").is_visible(), "Mobile field missing")
    print(f"PASS {width}px layout, branding, disabled-order safety", flush=True)


def verify_interactions(page):
    """Account selection must change numbers/logos without hitting any order API."""
    posted = []
    page.on("request", lambda req: posted.append(req.url) if req.method == "POST" else None)
    page.locator('input[name="payment"][value="bank"]').check()
    check(page.locator("#account-number").inner_text() == ACCOUNTS["bank"], "CBE number not updated")
    check(page.locator("#account-method").inner_text() == "CBE ባንክ", "CBE label mismatch")
    check(page.locator("#account-logo").get_attribute("src") == "assets/cbe-bank-logo.png", "CBE mark not updated")
    check(page.locator("#account-holder").inner_text() == "Kidus Elias", "CBE holder mismatch")
    page.locator('input[name="payment"][value="telebirr"]').check()
    check(page.locator("#account-number").inner_text() == ACCOUNTS["telebirr"], "Telebirr number not restored")
    check(page.locator("#account-logo").get_attribute("src") == "assets/telebirr-mark.svg", "Telebirr mark not restored")
    check(page.locator("#copy-label").inner_text() == "Copy", "Copy label after method change incorrect")
    check(page.locator(".checkoutaction").is_disabled(), "Order gate was bypassed")
    check(not posted, f"Unexpected POST requests: {posted}")
    print("PASS account selection, brand-switching, no POST", flush=True)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for width in [320, 360, 390, 768, 1280]:
            context = browser.new_context(
                viewport={"width": width, "height": 850},
                is_mobile=width <= 390,
                has_touch=width <= 390,
                device_scale_factor=2 if width <= 390 else 1,
            )
            page = context.new_page()
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            evaluate_layout(page, width)
            verify_interactions(page)
            if width in (360, 390, 1280):
                page.locator('input[name="payment"][value="bank"]').check()
                page.screenshot(path=str(ARTIFACTS / f"checkout-{width}px.png"), full_page=True, animations="disabled")
            context.close()
        browser.close()
        print("RESULT: Checkout preview visual/safety acceptance PASS", flush=True)


if __name__ == "__main__":
    main()
