"""Browser acceptance for isolated staging checkout; synthetic data only."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, text
from staging_checkout.security import totp_code

BASE = os.getenv("STAGING_BROWSER_URL", "https://127.0.0.1:8443")
ORIGIN = BASE
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


def login_founder(page):
    page.locator("#founder-user").fill(USERNAME)
    page.locator("#founder-pass").fill(PASSWORD)
    page.locator("#founder-totp").fill(totp_code(TOTP_SECRET))
    page.locator("#founder-login button[type=submit]").click()
    page.get_by_text("Synthetic founder session authenticated.").wait_for()


def new_order(page, method="telebirr"):
    page.locator("#customer-name").fill("QA Parent Example")
    page.locator("#customer-mobile").fill("0900000000")
    page.locator("#payment-method").select_option(method)
    page.locator("#customer-form button[type=submit]").click()
    page.locator("#order-panel").wait_for(state="visible")
    assert page.locator("#recipient").inner_text() == (
        "QA-TELEBIRR-ONLY" if method == "telebirr" else "QA-CBE-ONLY"
    )
    return page.locator("#order-id").inner_text()


@pytest.mark.parametrize("width,height,label", [
    (320, 800, "320"),
    (360, 800, "360"),
    (390, 844, "390"),
    (1440, 1000, "desktop"),
])
def test_browser_complete_customer_founder_and_five_download_journey(width, height, label):
    reset_database()
    OUT.mkdir(exist_ok=True)
    (OUT / "screenshots").mkdir(exist_ok=True)
    (OUT / "downloads").mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height},
                                ignore_https_errors=True, accept_downloads=True)
        page.goto(BASE + "/staging/checkout", wait_until="networkidle")
        assert "STAGING TEST" in page.locator("header").inner_text()
        assert await_no_horizontal_overflow(page, width)
        code = new_order(page)
        # The repeated order submission reuses the same request identity and returns the same order.
        page.locator("#customer-form button[type=submit]").click()
        page.get_by_text("Order created. These fictional details are for simulation only.").wait_for()
        assert page.locator("#order-id").inner_text() == code
        ref = "SIM-BROWSER" + label.upper().replace("DESKTOP", "DESK")
        page.locator("#reference").fill(ref)
        page.locator("#claim-form button[type=submit]").click()
        page.get_by_text("Under Review", exact=True).wait_for()
        # Duplicate customer claim is refused and cannot be treated as payment confirmation.
        page.locator("#claim-form button[type=submit]").click()
        page.get_by_text("already under review", exact=False).wait_for()
        page.locator("#refresh-status").click()
        assert page.locator("#customer-status").inner_text() == "Under Review"

        auth_state = page.evaluate("""() => JSON.parse(sessionStorage.getItem('parentwise-stage-order-v1'))""")
        denied = page.evaluate("""async (v) => {
          const r = await fetch('/api/v1/orders/' + v.code + '/downloads/part-1',
            {headers:{Authorization:'Bearer ' + v.token}});
          return r.status;
        }""", auth_state)
        assert denied == 403
        wrong = page.evaluate("""async (v) => {
          const r = await fetch('/api/v1/orders/' + v.code + '/downloads/part-1',
            {headers:{Authorization:'Bearer ' + 'Z'.repeat(43)}});
          return r.status;
        }""", auth_state)
        assert wrong == 404

        page.locator("#settlement-reference").fill(ref)
        page.locator("#settlement-method").select_option("telebirr")
        page.locator("#settlement-payer").fill("+251900000000")
        login_founder(page)
        page.locator("#record-settlement").click()
        page.get_by_text("Fictional settlement evidence recorded.").wait_for()
        page.locator("#verify-settlement").click()
        page.get_by_text("Founder approval is still required.").wait_for()
        page.locator("#refresh-status").click()
        assert page.locator("#customer-status").inner_text() == "Under Review"
        page.locator("#approve-order").click()
        page.locator("#customer-status").get_by_text("Ready to Download").wait_for()
        assert await_no_horizontal_overflow(page, width)

        # Keep review screenshots free of synthetic founder credentials and the test console.
        page.locator("#founder-panel").evaluate("(node) => node.style.display='none'")
        await page.screenshot(path=str(OUT / "screenshots" / ("checkout-" + label + "-ready.png")),
                              full_page=True)
        page.reload(wait_until="networkidle")
        assert page.locator("#customer-status").inner_text() == "Ready to Download"
        for part in range(1, 6):
            with page.expect_download() as info:
                page.locator("#download-list button").nth(part - 1).click()
            download = info.value
            path = OUT / "downloads" / (label + "-part-" + str(part) + ".pdf")
            download.save_as(str(path))
            data = path.read_bytes()
            assert data.startswith(b"%PDF-1.4")
            assert b"QA DEMO ONLY" in data
            assert b"NOT A PAID PARENTWISE PRODUCT" in data

        # Revocation takes effect on the next authorized download request.
        page.locator("#revoke-access").click()
        page.get_by_text("Dummy download access revoked.").wait_for()
        assert page.locator("#customer-status").inner_text() == "Payment Confirmed"
        assert page.evaluate("""async (v) => (await fetch('/api/v1/orders/' + v.code +
          '/downloads/part-1', {headers:{Authorization:'Bearer ' + v.token}})).status""",
          auth_state) == 403
        browser.close()


def await_no_horizontal_overflow(page, width):
    # Waiting is intentional: it lets the viewport and responsive styles settle.
    page.wait_for_timeout(50)
    return page.evaluate("(w) => document.documentElement.scrollWidth <= w", width)


def test_interrupted_order_creation_retries_same_key_and_body():
    reset_database()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(ignore_https_errors=True)
        attempts = []
        def fail_first(route):
            request = route.request
            attempts.append((request.headers.get("idempotency-key"), request.post_data))
            if len(attempts) == 1:
                route.abort("failed")
            else:
                route.continue_()
        page.route("**/api/v1/orders", fail_first)
        page.goto(BASE + "/staging/checkout", wait_until="networkidle")
        page.locator("#customer-name").fill("QA Parent Example")
        page.locator("#customer-mobile").fill("0900000000")
        page.locator("#create-order").click()
        page.get_by_text("You can retry with the same saved details.").wait_for()
        page.locator("#create-order").click()
        page.locator("#order-panel").wait_for(state="visible")
        assert len(attempts) == 2
        assert attempts[0] == attempts[1]
        browser.close()


def test_founder_rejection_allows_corrected_claim_and_recovery():
    reset_database()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(ignore_https_errors=True)
        page.goto(BASE + "/staging/checkout", wait_until="networkidle")
        new_order(page)
        page.locator("#reference").fill("SIM-REJECTRETRY01")
        page.locator("#claim-form button[type=submit]").click()
        page.get_by_text("Under Review", exact=True).wait_for()
        login_founder(page)
        page.locator("#reject-order").click()
        page.get_by_text("Claim rejected. Customer can submit a corrected fictional reference.").wait_for()
        page.locator("#refresh-status").click()
        assert page.locator("#customer-status").inner_text() == "Awaiting Payment"
        page.locator("#reference").fill("SIM-CORRECTRETRY01")
        page.locator("#claim-form button[type=submit]").click()
        page.get_by_text("Under Review", exact=True).wait_for()
        page.locator("#settlement-reference").fill("SIM-CORRECTRETRY01")
        page.locator("#settlement-method").select_option("telebirr")
        page.locator("#settlement-payer").fill("+251900000000")
        page.locator("#record-settlement").click()
        page.get_by_text("Fictional settlement evidence recorded.").wait_for()
        page.locator("#verify-settlement").click()
        page.get_by_text("Founder approval is still required.").wait_for()
        page.locator("#approve-order").click()
        assert page.locator("#customer-status").inner_text() == "Ready to Download"
        browser.close()
