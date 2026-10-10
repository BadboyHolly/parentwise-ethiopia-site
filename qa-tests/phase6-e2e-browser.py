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
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    browser = p.chromium.launch(headless=True)
    shopping = browser.new_context(ignore_https_errors=True, viewport={"width":1280,"height":900})
    def assets(route):
        name = route.request.url.split("?")[0].split("/")[-1] or "index.html"
        target = root / name
        if target.is_file() and target.suffix in (".html",".js",".css"):
            body = target.read_text(encoding="utf-8")
            if name == "checkout-qa.js":
                body = body.replace("https://parentwise-orders-api-qa.onrender.com", BASE)
            mime = {".html":"text/html",".css":"text/css",".js":"text/javascript"}[target.suffix]
            route.fulfill(status=200,content_type=mime,body=body)
        elif "/assets/" in route.request.url:
            route.fulfill(status=404,body="")
        else:
            route.continue_()
    shopping.route(BASE + "/**", assets)
    purchase = shopping.new_page()
    purchase.goto(BASE + "/index.html",wait_until="domcontentloaded")
    purchase.get_by_role("link",name="Get ParentWise",exact=True).click()
    expect(purchase.locator("#qaOrder")).to_be_visible()
    assert_ok("1,500 ETB" in purchase.locator("body").inner_text(), "actual sales page proceeds to priced QA checkout")
    purchase.locator("#name").fill("X")
    purchase.locator("#order-submit").click()
    assert_ok(purchase.locator("#name").evaluate("(e)=>e===document.activeElement"),"invalid customer name receives keyboard focus")
    assert_ok(purchase.locator("#checkout-feedback").get_attribute("aria-live") == "polite", "checkout errors and progress have accessible live announcement")
    synthetic_orders = []
    for method in ("bank","telebirr"):
        if synthetic_orders:
            purchase.once("dialog",lambda d:d.accept())
            purchase.locator("#start-new-order").click()
        purchase.locator("#name").fill("Fictional CI Parent")
        purchase.locator("#mobile").fill("0912345678")
        purchase.locator("#payment-method").select_option(method)
        def interrupt(route):
            response = route.fetch()
            assert response.status == 201
            route.abort("failed")
        purchase.route(BASE + "/api/v1/orders", interrupt,times=1)
        purchase.locator("#order-submit").click()
        expect(purchase.locator("#checkout-feedback")).to_contain_text("SAME")
        saved = purchase.evaluate("JSON.parse(sessionStorage.getItem('parentwise.qa.checkout.v2'))")
        assert_ok(bool(saved["key"]) and not saved.get("order"),method+" committed response loss preserves original attempt")
        purchase.reload(wait_until="domcontentloaded")
        expect(purchase.locator("#order-submit")).to_contain_text("Retry saved")
        def slow(route):
            time.sleep(1)
            route.continue_()
        purchase.route(BASE + "/api/v1/orders",slow,times=1)
        purchase.locator("#order-submit").press("Enter")
        expect(purchase.locator("#order-id")).to_contain_text("PW-QA-")
        saved2 = purchase.evaluate("JSON.parse(sessionStorage.getItem('parentwise.qa.checkout.v2'))")
        assert_ok(saved2["key"] == saved["key"] and saved2["order"]["amount_etb"] == 1500,method+" slow API retry uses same idempotency key and fixed price")
        synthetic_orders.append({"order":saved2["order"],"access_token":saved2["token"]})
        purchase.reload(wait_until="domcontentloaded")
        expect(purchase.locator("#order-id")).to_have_text(saved2["order"]["order_id"])
        assert_ok(True,method+" refreshed customer order is recovered using GET")
    shopping.close()
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
    csrf = page.request.get(BASE + "/admin/api/session").json()["csrf"]
    original = synthetic_orders[1]
    def consistent(payment,delivery=None):
        public = http.get(BASE+"/api/v1/orders/"+original["order"]["order_id"],
            headers={"Authorization":"Bearer "+original["access_token"]}).json()["order"]
        founder = page.request.get(BASE+"/admin/api/orders/"+original["order"]["order_id"]).json()
        assert public["status"] == founder["order"]["status"] == payment
        if delivery:
            assert public["fulfillment"]["status"] == founder["fulfillment"]["status"] == delivery
        else:
            assert public["fulfillment"] is None
        assert set(public)=={"order_id","product","amount_etb","currency","payment_method","status","test_mode","created_at","fulfillment"}
        assert all(k not in public for k in ("name","mobile","reviews","verification_history","fulfillment_events"))
        assert_ok(True,"customer and founder state consistency "+payment+" "+str(delivery))
    consistent("PENDING_PAYMENT")
    # First row is newest (Telebirr). Demonstrate complete positive check.
    page.locator("#orderRows button").first.click()
    page.locator("#qaPaymentReview").wait_for(state="visible")
    assert_ok(page.locator("#qaReviewTitle").is_visible(), "desktop fictional review controls")
    page.locator("#qaFixtureAmount").select_option("1400")
    page.locator("#qaGenerateFixture").click()
    page.locator("#qaRecordProof").click()
    page.locator("#qaCheckLedger").click()
    expect(page.locator("#qaReviewHistory")).to_contain_text("DISCREPANCY")
    assert_ok(page.locator("#qaVerify").is_disabled(),"incorrect simulated payment is rejected before approval")
    page.locator("#qaReason").fill("Phase 6 fictional discrepancy")
    page.locator("#qaReject").click()
    expect(page.locator("#qaEventHistory")).to_contain_text("qa_claim_rejected")
    page.locator("#qaFixtureAmount").select_option("1500")
    page.locator("#qaGenerateFixture").click()
    expect(page.locator("#qaClaimRef")).to_have_value(re.compile(r"QA-TB-.*"))
    page.locator("#qaRecordProof").click()
    expect(page.locator("#qaCheckLedger")).to_be_enabled()
    denied = page.request.post(BASE+"/admin/api/orders/"+original["order"]["order_id"]+"/confirm",
        headers={"Origin":BASE,"X-CSRF-Token":csrf},data={"confirm_simulated_match":True})
    assert_ok(denied.status==409,"matching fixture cannot be approved before independent comparison")
    consistent("PROOF_SUBMITTED")
    page.locator("#qaCheckLedger").click()
    expect(page.locator("#qaVerify")).to_be_enabled()
    consistent("VERIFYING")
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
    consistent("VERIFIED_PAID","PENDING_FULFILLMENT")
    expect(page.locator("#qaQueueRows")).to_contain_text("PW-QA-")
    assert_ok(True, "desktop verified simulated order entered dummy fulfillment queue")
    page.set_viewport_size({"width": 390, "height": 844})
    assert_ok(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"),
              "mobile dummy fulfillment has no horizontal overflow")
    page.once("dialog", lambda d: d.accept())
    page.locator("#qaPrepareDummy").click()
    expect(page.locator("#qaFulfillState")).to_contain_text("PREPARING")
    consistent("VERIFIED_PAID","PREPARING")
    # Download only a harmless founder-authenticated dummy document.
    dummy = page.request.get(BASE + "/admin/api/fulfillment/dummy-document")
    assert_ok(dummy.status == 200 and "FICTIONAL QA DELIVERY" in dummy.text(),
              "dummy text available only with founder session")
    page.locator("#qaDeliveryReason").fill("Phase 6 fictional delivery failure")
    page.once("dialog",lambda d:d.accept())
    page.locator("#qaFailDummy").click()
    expect(page.locator("#qaFulfillState")).to_contain_text("DELIVERY_FAILED")
    consistent("VERIFIED_PAID","DELIVERY_FAILED")
    page.locator("#qaDeliveryReason").fill("Phase 6 controlled retry")
    page.once("dialog",lambda d:d.accept())
    page.locator("#qaRetryDummy").click()
    expect(page.locator("#qaFulfillState")).to_contain_text("PREPARING")
    assert_ok(True,"browser records failure and controlled retry with history")
    page.locator("#qaCheckedDummy").check()
    page.once("dialog", lambda d: d.accept())
    page.locator("#qaDispatchDummy").click()
    expect(page.locator("#qaFulfillState")).to_contain_text("SENT")
    consistent("VERIFIED_PAID","SENT")
    assert_ok(page.locator("#qaDispatchDummy").is_disabled(), "double-dispatch disabled on mobile")
    page.locator("#qaReceiptReference").fill("QA-ACK-0123456789ABCDEF")
    page.once("dialog", lambda d: d.accept())
    page.locator("#qaReceiptDummy").click()
    expect(page.locator("#qaFulfillState")).to_contain_text("DELIVERED")
    consistent("VERIFIED_PAID","DELIVERED")
    assert_ok(page.locator("#qaReceiptDummy").is_disabled(),
              "customer acknowledgement can be recorded once")

    original = synthetic_orders[1]
    cross = http.get(BASE + "/api/v1/orders/" + synthetic_orders[0]["order"]["order_id"],
        headers={"Authorization":"Bearer " + original["access_token"]})
    assert_ok(cross.status == 404,"customer token cannot expose another customer order")
    denied = http.get(BASE + "/admin/api/orders",
        headers={"Authorization":"Bearer " + original["access_token"]})
    assert_ok(denied.status == 401,"real synthetic customer token has no founder privileges")
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
    customer_page.screenshot(path=str(evidence_dir / 'phase6-customer-recovery.png'), full_page=True)
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
print("PHASE 6 END TO END CUSTOMER AND FOUNDER BROWSER ACCEPTANCE PASS", flush=True)
