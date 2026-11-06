"""Browser acceptance for the live MANUAL checkout (customer pays by Telebirr/CBE, sends proof on Telegram).

Fictional data only. Never pays, never contacts an order system. Replaces the old walkthrough test for the
public page; the old API-flow test (preview_checkout_gate_acceptance.py) is kept for a future backend checkout.
"""
import re
import shutil
from urllib.parse import unquote
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8765"
TELEGRAM = "https://t.me/ParentWiseEthiopia"
METHODS = (("telebirr", "0912910693"), ("bank", "1000220596536"))
NAME, PHONE = "Test Parent", "0911000000"


def no_overflow(page, where):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), f"horizontal scroll at {where}"


STAGE = {"where": "start"}


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            channel="chrome" if shutil.which("google-chrome") else None,
            executable_path=shutil.which("chromium") if not shutil.which("google-chrome") else None,
        )
        for width in (320, 360, 390, 768, 1280):
            context = browser.new_context(viewport={"width": width, "height": 860})
            page = context.new_page()
            requested = []
            page.on("request", lambda req: requested.append(req.url))
            STAGE["where"] = f"{width}px"
            page.goto(BASE + "/order.html")
            expect(page.locator("#details-section")).to_be_visible()
            expect(page.locator("#payment-section")).to_be_hidden()
            expect(page.locator("#telegram-section")).to_be_hidden()
            no_overflow(page, f"{width}px step 1")
            page.fill("#customer-name", NAME)
            page.fill("#customer-mobile", PHONE)
            for method, number in METHODS:
                STAGE["where"] = f"{width}px {method}"
                page.check(f"input[name=payment][value={method}]")
                page.click("#continue-payment")
                expect(page.locator("#payment-section")).to_be_visible()
                shown = re.sub(r"\D", "", page.locator("#recipient-number").inner_text())
                assert shown == number, f"{method}: recipient {shown} != approved {number}"
                assert "1,500" in page.locator("#payment-section").inner_text(), "amount 1,500 not shown"
                expect(page.locator("#change-method")).to_have_text("Edit")
                expect(page.locator("#paid-action")).to_be_visible()
                no_overflow(page, f"{width}px payment ({method})")
                page.click("#paid-action")
                expect(page.locator("#telegram-section")).to_be_visible()
                href = page.locator("#telegram-handoff").get_attribute("href")
                assert href.startswith(TELEGRAM), f"Telegram link goes elsewhere: {href[:80]}"
                prefilled = unquote(href.split("?text=", 1)[1]) if "?text=" in href else ""
                assert NAME in prefilled and PHONE in prefilled and "Payment method" in prefilled, \
                    "Telegram message should be prefilled with the buyer's name, phone and payment method"
                no_overflow(page, f"{width}px telegram ({method})")
                page.click("#back-telegram")
                expect(page.locator("#payment-section")).to_be_visible()
                page.click("#back-payment")
                expect(page.locator("#details-section")).to_be_visible()
            stored = page.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)])")
            assert NAME not in stored and PHONE not in stored, "buyer details must not be stored in the browser"
            foreign = [u for u in requested if not u.startswith(BASE) and not u.startswith("data:")]
            assert not foreign, f"unexpected outside requests: {foreign[:3]}"
            assert not any("/api/" in u for u in requested), "manual checkout must not call any order API"
            context.close()
        browser.close()


try:
    main()
except Exception as error:  # published as an annotation so the reason is visible in GitHub
    message = (type(error).__name__ + ": " + str(error)).replace("\n", " ")[:900]
    print("::error title=MANUAL CHECKOUT ACCEPTANCE FAILED (" + STAGE["where"] + ")::" + message)
    raise
print("PASS: manual checkout works at 320/360/390/768/1280, approved recipients only, no order API call, nothing stored")
