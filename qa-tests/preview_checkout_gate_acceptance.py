"""Isolated, fictional checkout acceptance. Never exercises real payment rails."""
import json
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE="http://127.0.0.1:8765"
API="https://orders.parentwise.invalid"
HTML=Path("site-preview/order.html").read_text(encoding="utf-8")
ORDER_ID="PW-0123456789ABCDEF01234567"
TOKEN="x"*43
NUMBERS={"telebirr":"0000000000","bank":"0000000000000"}
assert "CHECKOUT_OPEN = false" in HTML
assert "ORDER_API_ORIGIN = ''" in HTML
assert all(x not in HTML for x in ("0912910693","1000223019327","10002230019327","QA-CBE-ONLY","QA-TELEBIRR-ONLY","DEMO RECIPIENT"))
LIVE_FIXTURE=HTML.replace("CHECKOUT_OPEN = false","CHECKOUT_OPEN = true").replace(
    "ORDER_API_ORIGIN = ''",f"ORDER_API_ORIGIN = '{API}'"
)

def payload(method):
    return {"order":{"order_id":ORDER_ID,"status":"AWAITING_PAYMENT",
                     "amount_etb":1500,"currency":"ETB","payment_method":method,
                     "payment_instructions":{"name":("Telebirr" if method=="telebirr" else "Commercial Bank of Ethiopia"),
                                             "number":NUMBERS[method],"holder":"FICTIONAL TEST HOLDER",
                                             "amount_etb":1500,"currency":"ETB"}},
            "access_token":TOKEN}

def response_headers():
    return {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type, Idempotency-Key, Authorization",
            "Access-Control-Allow-Methods":"GET,POST,OPTIONS","Cache-Control":"no-store"}

def fake_api(route, requests, failure=False):
    req=route.request
    if req.method=="OPTIONS":
        route.fulfill(status=204,headers=response_headers())
        return
    requests.append({"url":req.url,"method":req.method,"idempotency":req.headers.get("idempotency-key")})
    method="telebirr"
    if req.method=="POST":
        method=json.loads(req.post_data)["payment_method"]
        if failure:
            route.fulfill(status=503,headers=response_headers(),body='{"error":"unavailable"}')
            return
    elif req.method=="GET":
        method="bank" if requests[0].get("method")=="bank" else "telebirr"
    route.fulfill(status=201 if req.method=="POST" else 200, headers=response_headers(),
                  content_type="application/json",body=json.dumps(payload(method)))

with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True,channel="chrome" if shutil.which("google-chrome") else None,executable_path=shutil.which("chromium") if not shutil.which("google-chrome") else None)
    for width in (320,360,390,768,1280):
        context=browser.new_context(viewport={"width":width,"height":860},permissions=["clipboard-read","clipboard-write"])
        page=context.new_page()
        # PUBLIC visual review: complete all three steps without saving an
        # order, displaying a payable account, or contacting an order API.
        outgoing=[]
        page.on("request",lambda req:outgoing.append(req.url) if "/api/v1/orders" in req.url else None)
        page.goto(BASE+"/order.html")
        expect(page.locator("#continue-payment")).to_be_enabled()
        expect(page.locator("#payment-section")).to_be_hidden()
        expect(page.locator("#recipient-number")).to_have_text("—")
        assert page.locator("#checkout-availability").count()==0
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        page.locator("#continue-payment").click()
        expect(page.locator("#validation-error")).to_be_visible()
        page.locator("#customer-name").fill("አባት አለሙ")
        page.locator("#customer-mobile").fill("0911111111")
        choice="bank" if width in (360,768) else "telebirr"
        if choice=="bank": page.locator('input[name="payment"][value="bank"]').check()
        page.locator("#continue-payment").click()
        expect(page.locator("#payment-section")).to_be_visible()
        expect(page.locator("#recipient-number")).to_have_text("•••••••••9327" if choice=="bank" else "••••••0693")
        expect(page.locator("#copy-recipient")).to_be_disabled()
        expect(page.locator("#walkthrough-payment-note")).to_be_visible()
        assert "No order was saved" in page.locator("#walkthrough-payment-note").inner_text()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        # Both directions must work, preserving name, phone and selected rail.
        page.locator("#back-payment").click()
        expect(page.locator("#details-section")).to_be_visible()
        expect(page.locator("#payment-section")).to_be_hidden()
        expect(page.locator("#customer-name")).to_have_value("አባት አለሙ")
        expect(page.locator("#customer-mobile")).to_have_value("0911111111")
        if choice=="bank": expect(page.locator('input[name="payment"][value="bank"]')).to_be_checked()
        page.locator("#continue-payment").click()
        expect(page.locator("#payment-section")).to_be_visible()
        page.locator("#paid-action").click()
        expect(page.locator("#telegram-section")).to_be_visible()
        page.locator("#back-telegram").click()
        expect(page.locator("#payment-section")).to_be_visible()
        expect(page.locator("#telegram-section")).to_be_hidden()
        page.locator("#paid-action").click()
        expect(page.locator("#telegram-section")).to_be_visible()
        expect(page.locator("#walkthrough-telegram-note")).to_be_visible()
        assert "Order: Not created" in page.locator("#confirmation-message").inner_text()
        assert "Payment: Not requested" in page.locator("#confirmation-message").inner_text()
        assert "PW-" not in page.locator("#confirmation-message").inner_text()
        assert page.locator("#telegram-handoff").get_attribute("href")=="https://t.me/ParentWiseEthiopia"
        page.locator("#copy-confirmation").click()
        expect(page.locator("#confirmation-status")).to_contain_text("copied locally")
        assert not outgoing, "Public review must not send an order-API request"
        assert page.evaluate("sessionStorage.length")==0, "Public review must not persist buyer data"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        context.close()

        # ISOLATED: exact HTML under test, only the two explicit release flags changed.
        context=browser.new_context(viewport={"width":width,"height":860},permissions=["clipboard-read","clipboard-write"])
        page=context.new_page()
        page.route("**/order.html",lambda route: route.fulfill(status=200,content_type="text/html",body=LIVE_FIXTURE))
        requests=[]
        method="bank" if width in (360,768) else "telebirr"
        def route_api(route):
            if route.request.method=="POST":
                # Record method only in local test memory, never personal data.
                requests.insert(0,{"method":json.loads(route.request.post_data)["payment_method"]})
            fake_api(route,requests)
        page.route(API+"/**",route_api)
        page.goto(BASE+"/order.html")
        page.locator("#customer-name").fill("Synthetic Parent")
        page.locator("#customer-mobile").fill("0911111111")
        if method=="bank":page.locator('input[name="payment"][value="bank"]').check()
        page.locator("#continue-payment").click()
        expect(page.locator("#payment-section")).to_be_visible(timeout=10000)
        expect(page.locator("#recipient-number")).to_have_text(NUMBERS[method])
        expect(page.locator("#recipient-holder")).to_have_text("FICTIONAL TEST HOLDER")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        page.locator("#copy-recipient").click()
        expect(page.locator("#copy-account-label")).to_have_text("Copied")
        page.locator("#back-payment").click()
        expect(page.locator("#details-section")).to_be_visible()
        expect(page.locator("#customer-name")).to_have_value("Synthetic Parent")
        if method=="bank": expect(page.locator('input[name="payment"][value="bank"]')).to_be_checked()
        page.locator("#continue-payment").click()
        expect(page.locator("#payment-section")).to_be_visible()
        page.locator("#paid-action").click()
        expect(page.locator("#telegram-section")).to_be_visible()
        assert ORDER_ID in page.locator("#confirmation-message").inner_text()
        assert page.locator("#telegram-handoff").get_attribute("href")=="https://t.me/ParentWiseEthiopia"
        assert TOKEN not in page.locator("#confirmation-message").inner_text()
        page.locator("#back-telegram").click()
        expect(page.locator("#payment-section")).to_be_visible()
        page.locator("#paid-action").click()
        expect(page.locator("#telegram-section")).to_be_visible()
        # Mobile payment-app return: reload the same tab; token-based GET restores order.
        page.reload()
        expect(page.locator("#payment-section")).to_be_visible(timeout=10000)
        expect(page.locator("#recipient-number")).to_have_text(NUMBERS[method])
        assert any(entry.get("method")=="GET" for entry in requests)
        context.close()

    # Simulated order API outage never reveals a recipient or advances step 2.
    context=browser.new_context(viewport={"width":390,"height":800})
    page=context.new_page()
    page.route("**/order.html",lambda route: route.fulfill(status=200,content_type="text/html",body=LIVE_FIXTURE))
    errors=[]
    page.route(API+"/**",lambda route:fake_api(route,errors,failure=True))
    page.goto(BASE+"/order.html")
    page.locator("#customer-name").fill("Synthetic Parent")
    page.locator("#customer-mobile").fill("0911111111")
    page.locator("#continue-payment").click()
    expect(page.locator("#validation-error")).to_be_visible()
    expect(page.locator("#payment-section")).to_be_hidden()
    page.locator("#continue-payment").click()
    expect(page.locator("#validation-error")).to_be_visible()
    # A browser restart during a timed-out POST must not duplicate a pending order.
    page.reload()
    expect(page.locator("#customer-name")).to_have_value("Synthetic Parent")
    expect(page.locator("#customer-mobile")).to_have_value("0911111111")
    expect(page.locator("#payment-section")).to_be_hidden()
    page.locator("#continue-payment").click()
    expect(page.locator("#validation-error")).to_be_visible()
    keys=[x["idempotency"] for x in errors if x.get("method")=="POST"]
    assert len(keys)==3 and len(keys[0])==43 and len(set(keys))==1, "Cross-reload retry must reuse the original key"
    context.close()
    browser.close()
print("PASS: all 5 widths; review/live back-forward navigation, both methods, zero real payments, clipboard, Telegram, recovery, outage, duplicate-request prevention")
