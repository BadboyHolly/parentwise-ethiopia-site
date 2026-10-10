"""Non-invasive public QA admin browser/security smoke test.

No founder password, OTP, cookies, login submissions, or account records are used.
Only anonymous 401/404 responses and the public empty login form are checked.
"""
import json
from playwright.sync_api import sync_playwright

BASE = "https://parentwise-orders-api-qa.onrender.com"


def require(cond, label):
    if not cond:
        raise AssertionError(label)
    print("PASS " + label, flush=True)


with sync_playwright() as p:
    req = p.request.new_context(timeout=45000, extra_http_headers={"Accept": "application/json"})
    health = req.get(BASE + "/healthz")
    require(health.status == 200 and health.json().get("payments_enabled") is False,
            "LIVE health=200, payments disabled")
    ready = req.get(BASE + "/readyz")
    require(ready.status == 200 and ready.json().get("database") == "ready",
            "LIVE PostgreSQL ready=200")
    for route in ("/admin/api/session", "/admin/api/overview", "/admin/api/orders",
                  "/admin/api/orders?page=1&page_size=2",
                  "/admin/api/orders/PW-QA-000000000000000000000000"):
        response = req.get(BASE + route)
        require(response.status == 401, "LIVE anonymous " + route + " -> 401")
        require(response.headers.get("cache-control") == "no-store",
                "LIVE protected no-store " + route)
    no_admin = req.get(BASE + "/admin/api/orders", headers={"Authorization": "Bearer fictional-customer-recovery-code"})
    require(no_admin.status == 401, "LIVE customer bearer cannot access founder order listing")
    require(req.post(BASE + "/admin/api/register", data={}).status == 404,
            "LIVE no public founder account registration")
    for action in ("paid", "refund", "deliver"):
        path = "/admin/api/orders/PW-QA-000000000000000000000000/" + action
        require(req.post(BASE + path, data={}).status == 404,
                "LIVE no order mutation action " + action)

    # Phase 4: all simulated payment mutations must reject anonymous clients.
    # Requests use only fictional references; no founder login, cookies, money,
    # payment evidence, or customer details are submitted.
    fictional_order = "PW-QA-" + "0" * 24
    guarded = [
        ("/admin/api/qa-ledger", {"method": "bank", "amount_etb": 1500}),
        ("/admin/api/orders/" + fictional_order + "/proof",
         {"test_reference": "QA-BK-" + "0" * 16, "reported_amount_etb": 1500, "currency": "ETB"}),
        ("/admin/api/orders/" + fictional_order + "/check", {}),
        ("/admin/api/orders/" + fictional_order + "/confirm", {"confirm_simulated_match": True}),
        ("/admin/api/orders/" + fictional_order + "/reject", {"reason": "Fictional rejection test"}),
        ("/admin/api/orders/" + fictional_order + "/cancel", {"reason": "Fictional cancellation test"}),
    ]
    for route, body in guarded:
        result = req.post(BASE + route, data=body, headers={"Origin": BASE})
        require(result.status == 401, "LIVE anonymous mutation blocked " + route.split("/")[-1])
        require(result.headers.get("cache-control") == "no-store",
                "LIVE mutation denial not cacheable " + route.split("/")[-1])

    # No customer data or new test orders: confirm refreshed static QA checkout
    # contains the Phase 4 status recovery compatibility change.
    checkout_script = req.get("https://parentwise-ethiopia-qa.onrender.com/checkout-qa.js")
    require(checkout_script.status == 200, "LIVE checkout integration JavaScript HTTP 200")
    script = checkout_script.text()
    for state in ("PROOF_SUBMITTED", "VERIFYING", "VERIFIED_PAID", "CANCELLED"):
        require(state in script, "LIVE customer accepts simulated QA state " + state)
    require("No real payment has been requested, received, or verified" in script,
            "LIVE customer screen disclaims all real payments")

    browser = p.chromium.launch(headless=True)
    for label, size in (("desktop", {"width": 1280, "height": 900}),
                        ("mobile", {"width": 390, "height": 844})):
        ctx = browser.new_context(viewport=size, color_scheme="light")
        page = ctx.new_page()
        response = page.goto(BASE + "/admin", wait_until="domcontentloaded", timeout=90000)
        require(response is not None and response.status == 200,
                "LIVE " + label + " admin document HTTP 200")
        page.locator("#signin").wait_for(state="visible", timeout=30000)
        require(page.locator("#username").is_visible() and
                page.locator("#password").is_visible() and
                page.locator("#otp").is_visible(), "LIVE " + label + " founder login controls visible")
        require(not page.locator("#dashboard").is_visible(),
                "LIVE " + label + " dashboard hidden without founder session")
        require(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"),
                "LIVE " + label + " no horizontal overflow")
        page.locator("#username").focus()
        page.keyboard.press("Tab")
        require(page.evaluate("document.activeElement.id") == "password",
                "LIVE " + label + " keyboard focus moves from username to password")
        require(not ctx.cookies(BASE),
                "LIVE " + label + " no founder cookies without login")
        headers = response.headers
        require("default-src 'none'" in headers.get("content-security-policy", ""),
                "LIVE " + label + " restrictive admin CSP")
        require(headers.get("cache-control") == "no-store",
                "LIVE " + label + " HTML not cacheable")
        ctx.close()
    browser.close()
    req.dispose()
print("LIVE ADMIN ANONYMOUS SECURITY + MOBILE BROWSER ACCEPTANCE PASS", flush=True)
