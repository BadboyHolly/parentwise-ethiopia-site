"""Playwright browser acceptance of the approved Amharic staging checkout."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, text
from staging_checkout.security import totp_code

BASE = os.getenv("STAGING_BROWSER_URL", "https://127.0.0.1:8443")
OUT = Path("artifacts")
PASSWORD = os.environ["STAGING_FOUNDER_PASSWORD"]
USERNAME = os.environ["STAGING_FOUNDER_USERNAME"]
TOTP_SECRET = os.environ["STAGING_FOUNDER_TOTP_SECRET"]


def reset_database():
    engine = create_engine(os.environ["STAGING_DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text("""TRUNCATE staging_audit_events, staging_download_grants,
            staging_simulated_settlements, staging_payment_claims, staging_order_states,
            staging_founder_sessions, staging_rate_windows, production_orders CASCADE"""))
    engine.dispose()


def founder_login(page):
    page.locator("#stage-founder-user").fill(USERNAME)
    page.locator("#stage-founder-password").fill(PASSWORD)
    page.locator("#stage-founder-totp").fill(totp_code(TOTP_SECRET))
    page.locator("#stage-founder-login button[type=submit]").click()
    page.locator("#stage-founder-actions").wait_for(state="visible")


def enter_review(page, method="telebirr"):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.set_default_timeout(5_000)
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.on("console", lambda msg: page_errors.append("console:" + msg.text) if msg.type == "error" else None)
    page.goto(BASE + "/staging/checkout", wait_until="domcontentloaded")
    assert page.locator("html").get_attribute("lang") == "am"
    page.locator("#customer-name").fill("QA Parent Example")
    page.locator("#customer-mobile").fill("0900000000")
    page.locator("label.method").nth(0 if method == "telebirr" else 1).click()
    assert page.locator("#payment-details").is_hidden()
    page.locator("#review-order-button").click()
    review = page.locator("#checkout-review")
    try:
        review.wait_for(state="visible", timeout=3_000)
    except Exception as exc:
        details = page.evaluate("""() => ({
          formPresent: !!document.getElementById("order-form"),
          formHidden: document.getElementById("order-form")?.hidden,
          reviewHidden: document.getElementById("checkout-review")?.hidden,
          name: document.getElementById("customer-name")?.value,
          mobile: document.getElementById("customer-mobile")?.value,
          error: document.getElementById("form-error")?.textContent,
          scriptCount: document.scripts.length,
          ready: document.readyState
        })""")
        page.screenshot(path=str(OUT / "screenshots" / "am-checkout-debug.png"), full_page=True)
        raise AssertionError(f"Review step did not open; details={details!r}; page_errors={page_errors!r}") from exc
    assert page.locator("#review-method").inner_text() == ("Telebirr" if method == "telebirr" else "CBE ባንክ")


def create_staging_order(page):
    page.locator("#create-staging-order").click()
    page.locator("#staging-payment").wait_for(state="visible")
    return page.locator("#stage-order-code").inner_text()


def order_through_review(page, method="telebirr", label="review"):
    enter_review(page, method)
    (OUT / "screenshots").mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / "screenshots" / ("am-checkout-" + label + "-review.png")), full_page=True)
    return create_staging_order(page)


def set_reference_and_claim(page, reference):
    page.locator("#stage-reference").fill(reference)
    page.locator("#stage-claim-form button[type=submit]").click()
    page.get_by_text("Under Review", exact=True).wait_for()


def no_horizontal_overflow(page, width):
    page.wait_for_timeout(100)
    return page.evaluate("(w) => document.documentElement.scrollWidth <= w", width)


@pytest.mark.parametrize("width,height,label", [
    (320, 800, "320"),
    (360, 800, "360"),
    (390, 844, "390"),
    (768, 1024, "768"),
    (1280, 900, "1280"),
])
def test_amharic_checkout_complete_order_to_five_dummy_downloads(width, height, label):
    reset_database()
    (OUT / "screenshots").mkdir(parents=True, exist_ok=True)
    (OUT / "downloads").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height},
                                ignore_https_errors=True, accept_downloads=True)
        code = order_through_review(page, label=label)
        assert page.locator("#stage-recipient").inner_text() == "QA-TELEBIRR-ONLY"
        assert "0912910693" not in page.content()
        assert "10002230019327" not in page.content()
        assert "Kidus Elias" not in page.content()
        assert no_horizontal_overflow(page, width), page.evaluate("""() => ({viewport: innerWidth, document: document.documentElement.scrollWidth, offenders: [...document.querySelectorAll("*")].map(e => ({tag:e.tagName,id:e.id,cls:typeof e.className==="string"?e.className:"",left:Math.round(e.getBoundingClientRect().left),right:Math.round(e.getBoundingClientRect().right),width:Math.round(e.getBoundingClientRect().width)})).filter(x => x.right > innerWidth + 1 || x.left < -1).slice(0,20)})""")

        # Authorization is retained in memory only; customers reenter it after reload.
        recovery_code = page.locator("#stage-recovery-code").input_value()
        assert len(recovery_code) == 43
        assert recovery_code not in page.url
        assert page.evaluate("sessionStorage.length + localStorage.length") == 0
        customer = {"code": code, "token": recovery_code}
        page.evaluate("""() => Object.defineProperty(navigator, "clipboard", {
          configurable: true, value: {writeText: () => Promise.reject(new Error("denied"))}
        })""")
        page.locator("#stage-copy-recovery").click()
        assert "Clipboard unavailable" in page.locator("#stage-recovery-save-message").inner_text()
        assert page.locator("#stage-recovery-code").evaluate(
            "(el) => el.selectionStart === 0 && el.selectionEnd === el.value.length"
        )
        reference = "SIM-BROWSER" + label
        set_reference_and_claim(page, reference)
        duplicate_claim = page.evaluate("""async ({ref, order}) => {
          const r=await fetch("/api/v1/orders/"+order.code+"/payment-claims",{method:"POST",
            headers:{Authorization:"Bearer "+order.token,"Content-Type":"application/json"},
            body:JSON.stringify({test_reference:ref,reported_amount_etb:1500,currency:"ETB"})});
          return r.status;
        }""", {"ref": reference, "order": customer})
        assert duplicate_claim == 409
        page.locator("#stage-refresh").click()
        assert page.locator("#stage-status").inner_text() == "Under Review"
        assert page.evaluate("""async (s) => (await fetch('/api/v1/orders/' + s.code +
          '/downloads/part-1',{headers:{Authorization:'Bearer '+s.token}})).status""", customer) == 403
        assert page.evaluate("""async (s) => (await fetch('/api/v1/orders/' + s.code +
          '/downloads/part-1',{headers:{Authorization:'Bearer '+'Z'.repeat(43)}})).status""",
          customer) == 404

        founder_login(page)
        page.locator("#stage-settlement-ref").fill(reference)
        page.locator("#stage-settlement-payer").fill("+251900000000")
        page.locator("#stage-record").click()
        page.get_by_text("Fictional settlement recorded.").wait_for()
        page.locator("#stage-verify").click()
        page.get_by_text("Founder approval is still required.").wait_for()
        page.locator("#stage-refresh").click()
        assert page.locator("#stage-status").inner_text() == "Under Review"
        page.locator("#staging-founder").evaluate("(node) => node.style.display='none'")
        page.locator("#stage-recovery-code-panel").evaluate("(node) => node.hidden=true")
        page.screenshot(path=str(OUT / "screenshots" / ("am-checkout-" + label + "-pending.png")),
                              full_page=True)
        page.locator("#staging-founder").evaluate("(node) => node.style.display=''")
        page.locator("#stage-approve").click()
        page.get_by_text("Ready to Download", exact=True).wait_for()
        assert no_horizontal_overflow(page, width)
        page.locator("#staging-founder").evaluate("(node) => node.style.display='none'")
        page.locator("#stage-recovery-code-panel").evaluate("(node) => node.hidden=true")
        page.screenshot(path=str(OUT / "screenshots" / ("am-checkout-" + label + "-ready.png")),
                              full_page=True)
        page.locator("#staging-founder").evaluate("(node) => node.style.display=''")
        page.locator("#stage-recovery-code-panel").evaluate("(node) => node.hidden=true")
        page.reload(wait_until="domcontentloaded")
        assert page.evaluate("sessionStorage.length + localStorage.length") == 0
        page.locator("#stage-recovery-code-panel").wait_for(state="hidden")
        page.locator("#stage-recovery-order").fill(code)
        page.locator("#stage-recovery-code-input").fill(recovery_code)
        page.locator("#stage-recovery-form button[type=submit]").click()
        page.get_by_text("Ready to Download", exact=True).wait_for()

        for part in range(1, 6):
            with page.expect_download() as event:
                page.get_by_role("button", name="Download dummy PDF " + str(part)).click()
            download = event.value
            path = OUT / "downloads" / (label + "-part-" + str(part) + ".pdf")
            download.save_as(str(path))
            data = path.read_bytes()
            assert data.startswith(b"%PDF-1.4")
            assert b"QA DEMO ONLY" in data
            assert b"NOT A PAID PARENTWISE PRODUCT" in data

        page.locator("#stage-revoke").click()
        page.get_by_text("Payment Confirmed", exact=True).wait_for()
        assert page.evaluate("""async (s) => (await fetch('/api/v1/orders/' + s.code +
          '/downloads/part-1',{headers:{Authorization:'Bearer '+s.token}})).status""",
          customer) == 403
        browser.close()


def test_cbe_card_uses_only_fictional_recipient_details():
    reset_database()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(ignore_https_errors=True)
        order_through_review(page, method="bank", label="cbe")
        assert page.locator("#stage-recipient").inner_text() == "QA-CBE-ONLY"
        assert page.locator("#stage-settlement-method").input_value() == "bank"
        assert "10002230019327" not in page.content()
        assert "Kidus Elias" not in page.content()
        browser.close()


def test_interrupted_order_creation_retries_same_key_and_payload():
    reset_database()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(ignore_https_errors=True)
        requests = []
        def fail_first(route):
            request = route.request
            requests.append((request.headers.get("idempotency-key"), request.post_data))
            if len(requests) == 1:
                route.abort("failed")
            else:
                route.continue_()
        page.route("**/api/v1/orders", fail_first)
        enter_review(page)
        page.locator("#create-staging-order").click()
        page.get_by_text("Retry with the same details.", exact=False).wait_for()
        page.locator("#create-staging-order").click()
        page.locator("#staging-payment").wait_for(state="visible")
        assert len(requests) == 2
        assert requests[0] == requests[1]
        browser.close()


def test_third_party_payer_mismatch_is_denied_then_claim_can_be_rejected():
    reset_database()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(ignore_https_errors=True)
        order_through_review(page, label="third-party")
        reference = "SIM-THIRDPARTY01"
        set_reference_and_claim(page, reference)
        founder_login(page)
        page.locator("#stage-settlement-ref").fill(reference)
        page.locator("#stage-settlement-payer").fill("+251911111111")
        page.locator("#stage-record").click()
        page.get_by_text("Fictional settlement recorded.").wait_for()
        page.locator("#stage-verify").click()
        page.get_by_text("Settlement did not match.", exact=False).wait_for()
        assert page.locator("#stage-status").inner_text() == "Under Review"
        assert page.locator("#stage-download-panel").is_hidden()
        page.locator("#stage-reject").click()
        page.get_by_text("Awaiting Payment", exact=True).wait_for()
        browser.close()

def test_keyboard_can_reach_primary_checkout_controls():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 360, "height": 800},
                                ignore_https_errors=True)
        page.goto(BASE + "/staging/checkout", wait_until="domcontentloaded")
        focused = set()
        for _ in range(40):
            page.keyboard.press("Tab")
            focused.add(page.evaluate("document.activeElement.id"))
            if {"customer-name", "customer-mobile", "review-order-button"} <= focused:
                break
        assert {"customer-name", "customer-mobile", "review-order-button"} <= focused
        assert page.locator('label[for="customer-name"]').count() == 1
        assert page.locator('label[for="customer-mobile"]').count() == 1
        browser.close()
