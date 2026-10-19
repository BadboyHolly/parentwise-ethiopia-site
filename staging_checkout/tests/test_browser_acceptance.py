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
    page.goto(BASE + "/staging/checkout", wait_until="domcontentloaded")
    assert page.locator("html").get_attribute("lang") == "am"
    page.locator("#customer-name").fill("QA Parent Example")
    page.locator("#customer-mobile").fill("0900000000")
    page.locator('input[name="payment"][value="' + method + '"]').check()
    assert page.locator("#payment-details").is_hidden()
    page.locator("#review-order-button").click()
    page.locator("#checkout-review").wait_for(state="visible")
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
        assert no_horizontal_overflow(page, width)

        # Same key and same payload must resolve to the same unique order.
        duplicate = page.evaluate("""async () => {
          const key=sessionStorage.getItem('pw-stage-idem');
          const body=sessionStorage.getItem('pw-stage-payload');
          const r=await fetch('/api/v1/orders',{method:'POST',
            headers:{'Content-Type':'application/json','Idempotency-Key':key},body});
          return {status:r.status,data:await r.json()};
        }""")
        assert duplicate["status"] in (200, 201)
        assert duplicate["data"]["order"]["order_id"] == code

        reference = "SIM-BROWSER" + label
        set_reference_and_claim(page, reference)
        page.locator("#stage-claim-form button[type=submit]").click()
        page.get_by_text("already under review", exact=False).wait_for()
        page.locator("#stage-refresh").click()
        assert page.locator("#stage-status").inner_text() == "Under Review"
        customer = page.evaluate("() => JSON.parse(sessionStorage.getItem('pw-stage-checkout-am-v1'))")
        assert page.evaluate("""async (s) => (await fetch('/api/v1/orders/' + s.code +
          '/downloads/part-1',{headers:{Authorization:'Bearer '+s.token}})).status""", customer) == 403
        assert page.evaluate("""async (s) => (await fetch('/api/v1/orders/' + s.code +
          '/downloads/part-1',{headers:{Authorization:'Bearer '+'Z'.repeat(43)}})).status""",
          customer) == 404

        page.locator("#stage-settlement-ref").fill(reference)
        page.locator("#stage-settlement-payer").fill("+251900000000")
        founder_login(page)
        page.locator("#stage-record").click()
        page.get_by_text("Fictional settlement recorded.").wait_for()
        page.locator("#stage-verify").click()
        page.get_by_text("Founder approval is still required.").wait_for()
        page.locator("#stage-refresh").click()
        assert page.locator("#stage-status").inner_text() == "Under Review"
        page.locator("#staging-founder").evaluate("(node) => node.style.display='none'")
        page.screenshot(path=str(OUT / "screenshots" / ("am-checkout-" + label + "-pending.png")),
                              full_page=True)
        page.locator("#staging-founder").evaluate("(node) => node.style.display=''")
        page.locator("#stage-approve").click()
        page.get_by_text("Ready to Download", exact=True).wait_for()
        assert no_horizontal_overflow(page, width)
        page.locator("#staging-founder").evaluate("(node) => node.style.display='none'")
        page.screenshot(path=str(OUT / "screenshots" / ("am-checkout-" + label + "-ready.png")),
                              full_page=True)
        page.locator("#staging-founder").evaluate("(node) => node.style.display=''")
        page.reload(wait_until="domcontentloaded")
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
        page.locator("#stage-settlement-ref").fill(reference)
        page.locator("#stage-settlement-payer").fill("+251911111111")
        founder_login(page)
        page.locator("#stage-record").click()
        page.get_by_text("Fictional settlement recorded.").wait_for()
        page.locator("#stage-verify").click()
        page.get_by_text("Settlement did not match.", exact=False).wait_for()
        assert page.locator("#stage-status").inner_text() == "Under Review"
        assert page.locator("#stage-download-panel").is_hidden()
        page.locator("#stage-reject").click()
        page.get_by_text("Awaiting Payment", exact=True).wait_for()
        browser.close()
