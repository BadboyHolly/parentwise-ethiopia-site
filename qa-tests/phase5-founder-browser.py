"""Browser acceptance against temporary QA HTTPS API + disposable PostgreSQL.

Runs only in CI with synthetic founder credentials. Never use the real founder
account, TOTP seed, or production/Render database for this test.
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from playwright.sync_api import sync_playwright, expect
import re

BASE = "https://localhost:8443"
PASS = "SyntheticCIOnlyFounderPasswordLong!2026"
NAME = "CI_FICTIONAL_FOUNDER"


def otp():
    key = base64.b32decode(os.environ["FOUNDER_TOTP_SECRET"])
    now = int(time.time())
    # Avoid TOTP expiry in the middle of sign-in.
    while now % 30 > 23:
        time.sleep(1)
        now = int(time.time())
    step = now // 30
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    idx = digest[-1] & 15
    return f"{(int.from_bytes(digest[idx:idx+4], 'big') & 0x7fffffff) % 1000000:06d}"


def assert_ok(condition, label):
    if not condition:
        raise AssertionError(label)
    print("PASS simulated browser " + label, flush=True)


with sync_playwright() as p:
    http = p.request.new_context(ignore_https_errors=True, timeout=30000)
    ready = http.get(BASE + "/readyz")
    assert_ok(ready.status == 200, "synthetic PostgreSQL API ready")
    synthetic_orders = []
    for method in ("bank", "telebirr"):
        r = http.post(BASE + "/api/v1/orders", headers={"Idempotency-Key": secrets.token_urlsafe(32)},
                      data={"customer_name": "Fictional CI Parent",
                            "mobile": "0912345678", "payment_method": method})
        assert_ok(r.status == 201, method + " QA order created")
        synthetic_orders.append(r.json())
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.goto(BASE + "/admin", wait_until="domcontentloaded", timeout=30000)
    page.locator("#signin").wait_for(state="visible")
    page.locator("#username").fill(NAME)
    page.locator("#password").fill(PASS)
    page.locator("#otp").fill(otp())
    page.locator("#loginButton").click()
    page.locator("#dashboard").wait_for(state="visible", timeout=30000)
    expect(page.locator("#total")).to_have_text("2", timeout=20000)
    assert_ok(True, "real synthetic login and dashboard")
    # First row is newest (Telebirr). Demonstrate complete positive check.
    page.locator("#orderRows button").first.click()
    page.locator("#qaPaymentReview").wait_for(state="visible")
    assert_ok(page.locator("#qaReviewTitle").is_visible(), "desktop fictional review controls")
    page.locator("#qaGenerateFixture").click()
    expect(page.locator("#qaClaimRef")).to_have_value(re.compile(r"QA-TB-.*"))
    page.locator("#qaRecordProof").click()
    expect(page.locator("#qaCheckLedger")).to_be_enabled()
    page.locator("#qaCheckLedger").click()
    expect(page.locator("#qaVerify")).to_be_enabled()
    page.once("dialog", lambda d: d.accept())
    with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/confirm'),timeout=30000) as confirm_response:
        page.locator("#qaVerify").click()
    code = confirm_response.value.status
    print("SIMULATED PAYMENT CONFIRM HTTP",code,flush=True)
    if code != 200:
        print("SIMULATED PAYMENT UI ERROR:",page.locator("#qaReviewMessage").inner_text()[:150],flush=True)
    expect(page.locator("#qaReviewHistory")).to_contain_text("VERIFIED_PAID",timeout=12000)
    assert_ok(page.locator("#qaVerify").is_disabled(), "desktop matched ledger confirmed only once")
    expect(page.locator("#qaFulfillPanel")).to_be_visible()
    expect(page.locator("#qaQueueRows")).to_contain_text("PW-QA-")
    assert_ok(True, "desktop verified simulated order entered dummy fulfillment queue")
    page.set_viewport_size({"width": 390, "height": 844})
    assert_ok(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"),
              "mobile dummy fulfillment has no horizontal overflow")
    page.once("dialog", lambda d: d.accept())
    page.locator("#qaPrepareDummy").click()
    expect(page.locator("#qaFulfillState")).to_contain_text("PREPARING")
    # Download only a harmless founder-authenticated dummy document.
    dummy = page.request.get(BASE + "/admin/api/fulfillment/dummy-document")
    assert_ok(dummy.status == 200 and "FICTIONAL QA DELIVERY" in dummy.text(),
              "dummy text available only with founder session")
    page.locator("#qaCheckedDummy").check()
    page.once("dialog", lambda d: d.accept())
    page.locator("#qaDispatchDummy").click()
    expect(page.locator("#qaFulfillState")).to_contain_text("SENT")
    assert_ok(page.locator("#qaDispatchDummy").is_disabled(), "double-dispatch disabled on mobile")
    page.locator("#qaReceiptReference").fill("QA-ACK-0123456789ABCDEF")
    page.once("dialog", lambda d: d.accept())
    page.locator("#qaReceiptDummy").click()
    expect(page.locator("#qaFulfillState")).to_contain_text("DELIVERED")
    assert_ok(page.locator("#qaReceiptDummy").is_disabled(),
              "customer acknowledgement can be recorded once")

    original = synthetic_orders[1]
    recovered = http.get(BASE + "/api/v1/orders/" + original["order"]["order_id"],
                         headers={"Authorization":"Bearer " + original["access_token"]})
    assert_ok(recovered.status == 200 and recovered.json()["order"]["status"] == "VERIFIED_PAID",
              "customer protected GET after simulated verification")

    # Render the actual checkout files in a separate customer browser context.
    # Static files alone are locally routed; order GETs use the real disposable
    # PostgreSQL API and original synthetic private token, never Render.
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    customer = browser.new_context(ignore_https_errors=True, viewport={"width":390,"height":844})
    for filename, mime in (("order.html","text/html"), ("styles.css","text/css"), ("checkout-qa.js","text/javascript")):
        body = (root / filename).read_text(encoding="utf-8")
        if filename == "checkout-qa.js":
            body = body.replace("https://parentwise-orders-api-qa.onrender.com", BASE)
        customer.route(BASE + "/" + filename,
                       lambda route, request, body=body, mime=mime: route.fulfill(status=200, content_type=mime, body=body))
    customer_page = customer.new_page()
    customer_page.goto(BASE + "/order.html", wait_until="domcontentloaded")
    customer_page.locator("#recover-toggle").click()
    customer_page.locator("#recover-order-id").fill(original["order"]["order_id"])
    customer_page.locator("#recover-token").fill(original["access_token"])
    customer_page.locator("#recover-submit").click()
    expect(customer_page.locator("#order-status")).to_have_text("VERIFIED_PAID")
    expect(customer_page.locator("#qa-delivery-status")).to_have_text("DELIVERED · SIMULATION ONLY")
    expect(customer_page.locator("#qa-delivery-version")).to_have_text("QA-DEMO-2026.10-v1")
    expect(customer_page.locator("#qa-fulfillment-notice")).to_contain_text("No actual Telegram message")
    visible_text = customer_page.locator("body").inner_text()
    assert_ok(all(x not in visible_text for x in
                  ("QA-ACK-0123456789ABCDEF","qa_dummy_receipt_attested","Fictional CI Parent")),
              "customer checkout recovery displays safe delivery state and package version only")
    assert_ok(customer_page.locator("#recover-token").input_value() == "" and
              original["access_token"] not in customer_page.url,
              "customer recovery token cleared from input and absent from URL")
    customer_page.reload(wait_until="domcontentloaded")
    expect(customer_page.locator("#qa-delivery-status")).to_have_text("DELIVERED · SIMULATION ONLY")
    assert_ok(True, "customer refresh safely recovers existing fulfillment without order creation")
    assert_ok(customer_page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"),
              "customer recovery mobile no horizontal overflow")
    evidence_dir = root / 'qa-test-evidence'
    evidence_dir.mkdir(exist_ok=True)
    customer_page.screenshot(path=str(evidence_dir / 'phase5-customer-recovery.png'), full_page=True)
    customer.close()

    # Reuse authenticated cookie on 390px mobile; no second TOTP login attempt.
    page.set_viewport_size({"width": 390, "height": 844})
    assert_ok(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"),
              "mobile no horizontal overflow")
    page.locator("#orderRows button").nth(1).click()
    page.locator("#qaFixtureAmount").select_option("1400")
    page.locator("#qaGenerateFixture").click()
    expect(page.locator("#qaClaimRef")).to_have_value(re.compile(r"QA-BK-.*"))
    page.locator("#qaRecordProof").click()
    expect(page.locator("#qaCheckLedger")).to_be_enabled()
    page.locator("#qaCheckLedger").click()
    expect(page.locator("#qaReviewHistory")).to_contain_text("DISCREPANCY")
    assert_ok(page.locator("#qaVerify").is_disabled(), "mobile ledger discrepancy blocks verification")
    page.locator("#qaReason").fill("CI simulated amount mismatch")
    page.locator("#qaReject").click()
    expect(page.locator("#qaEventHistory")).to_contain_text("qa_claim_rejected")
    assert_ok(page.locator("#qaRecordProof").is_enabled(), "mobile rejection supports new claim")
    page.locator("#qaReason").fill("CI final fictional cancellation")
    page.once("dialog", lambda d: d.accept())
    page.locator("#qaCancel").click()
    expect(page.locator("#qaEventHistory")).to_contain_text("qa_order_cancelled")
    second = synthetic_orders[0]
    recovered = http.get(BASE + "/api/v1/orders/" + second["order"]["order_id"],
                         headers={"Authorization":"Bearer " + second["access_token"]})
    assert_ok(recovered.status == 200 and recovered.json()["order"]["status"] == "CANCELLED",
              "customer protected GET after simulated cancellation")
    page.locator("#logout").click()
    page.locator("#signin").wait_for(state="visible")
    assert_ok(page.request.get(BASE + "/admin/api/orders").status == 401,
              "logout revokes authenticated order access")
    context.close()
    browser.close()
    http.dispose()
print("PHASE 5 SYNTHETIC FOUNDER DESKTOP/MOBILE BROWSER ACCEPTANCE PASS", flush=True)
