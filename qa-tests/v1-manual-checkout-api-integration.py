"""Synthetic V1 buyer form -> isolated API -> pending order; NO money or real customers."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = "http://127.0.0.1:8765"
DB = Path("v1_checkout/temporary-ci-v1-orders.sqlite3")
OUT = Path("qa-artifacts/v1-pending-intake")
OUT.mkdir(parents=True, exist_ok=True)


def count_orders():
    with sqlite3.connect(DB) as con:
        return con.execute("SELECT count(*) FROM production_orders").fetchone()[0]


def check(browser, width):
    context = browser.new_context(viewport={"width": width, "height": 850}, is_mobile=width < 500,
                                  has_touch=width < 500, device_scale_factor=1)
    page = context.new_page()
    page_errors=[]
    browser_warnings=[]
    api_responses=[]
    page.on("pageerror",lambda exc: page_errors.append(str(exc)))
    page.on("console",lambda event: browser_warnings.append(event.text) if event.type in ("warning","error") else None)
    page.on("response",lambda response: api_responses.append((response.status,response.url)) if "/api/v1/orders" in response.url else None)
    writes = []
    page.on("request", lambda r: writes.append((r.method, r.url)) if r.method not in ("GET", "HEAD") else None)
    page.goto(ROOT+"/v1_checkout/ci-only-order.html", wait_until="domcontentloaded", timeout=45000)
    assert page.locator("#checkout-form").is_visible()
    assert "CI DEMO ONLY" in page.locator(".demo-alert").inner_text()
    assert page.locator("#payment-section").is_hidden()
    before = count_orders()
    page.locator("#customer-name").fill("Synthetic Parent")
    page.locator("#customer-mobile").fill("0912345678")
    page.locator('input[value="telebirr"]').check()
    page.locator("#continue-payment").click()
    try:
        page.locator("#payment-section").wait_for(state="visible",timeout=10000)
    except Exception:
        print("PAYMENT STAGE ERROR:", page.locator("#validation-error").inner_text() if page.locator("#validation-error").is_visible() else "No visible form error", flush=True)
        print("JS ERRORS:",page_errors,"WARNINGS:",browser_warnings[:8],"API:",api_responses,"POSTs:",writes,"URL:",page.url,"DB_COUNT:",count_orders(),flush=True)
        print("Form HTML:",page.locator("#checkout-form").evaluate("(e)=>e.outerHTML.slice(0,400)"),flush=True)
        raise
    assert page.locator("#recipient-number").inner_text() == "QA-TELEBIRR-ONLY"
    assert page.locator("#recipient-holder").inner_text() == "DEMO RECIPIENT — NOT REAL"
    assert count_orders() == before + 1
    page.locator("#change-method").click()
    page.locator("#continue-payment").click()
    try:
        page.locator("#payment-section").wait_for(state="visible",timeout=10000)
    except Exception:
        print("PAYMENT STAGE ERROR:", page.locator("#validation-error").inner_text() if page.locator("#validation-error").is_visible() else "No visible form error", flush=True)
        raise
    assert count_orders() == before + 1, "An unchanged retry must not create another order"
    page.locator("#paid-action").click()
    assert page.locator("#telegram-section").is_visible()
    msg = page.locator("#confirmation-message").inner_text()
    assert "Synthetic Parent" in msg and "0912345678" in msg
    assert "Order reference: PW-" in msg
    assert "access_token" not in msg and "Bearer" not in msg
    assert page.locator("#telegram-handoff").get_attribute("href") == "https://t.me/ParentWiseEthiopia"
    assert page.evaluate("(w)=>document.documentElement.scrollWidth<=w+1",width)
    assert len(writes)==2 and all(m=="POST" and u.endswith("/api/v1/orders") for m,u in writes), writes
    page.screenshot(path=str(OUT/f"v1-ci-{width}-telegram.png"),full_page=False,animations="disabled")
    context.close()
    print(f"PASS {width}px: persisted synthetic order, idempotent retry, private Telegram handoff",flush=True)


def check_sales_to_api(browser):
    """Exercise a reviewed sales CTA through a real synthetic saved order."""
    context=browser.new_context(viewport={"width":390,"height":850},
                                is_mobile=True,has_touch=True,device_scale_factor=1)
    page=context.new_page()
    writes=[]
    page.on("request",lambda req: writes.append((req.method,req.url))
            if req.method not in ("GET","HEAD") else None)
    page.goto(ROOT+"/index.html",wait_until="domcontentloaded",timeout=45000)
    assert page.locator("#hero").count()==1
    assert page.locator(".pw10x-cta").count()>0
    page.locator(".pw10x-cta").first.click(timeout=30000)
    page.wait_for_url("**/order.html",timeout=30000)
    assert "CI DEMO ONLY" in page.locator(".demo-alert").inner_text()
    before=count_orders()
    page.locator("#customer-name").fill("Synthetic CTA Parent")
    page.locator("#customer-mobile").fill("0972345678")
    page.locator('input[value="bank"]').check()
    page.locator("#continue-payment").click()
    page.locator("#payment-section").wait_for(state="visible",timeout=10000)
    assert page.locator("#recipient-number").inner_text()=="QA-CBE-ONLY"
    assert count_orders()==before+1
    page.locator("#paid-action").click()
    assert page.locator("#telegram-section").is_visible()
    message=page.locator("#confirmation-message").inner_text()
    assert "Synthetic CTA Parent" in message
    assert "Order reference: PW-" in message
    assert "access_token" not in message
    assert page.locator("#telegram-handoff").get_attribute("href")=="https://t.me/ParentWiseEthiopia"
    assert writes==[("POST",ROOT+"/api/v1/orders")], writes
    page.screenshot(path=str(OUT/"v1-sales-to-order-390.png"),
                    full_page=False,animations="disabled")
    context.close()
    print("PASS 390px reviewed sales CTA -> isolated pending order -> Telegram handoff",flush=True)


def check_failure(browser):
    context=browser.new_context(viewport={"width":390,"height":850})
    page=context.new_page()
    page.route("**/api/v1/orders",lambda route: route.fulfill(status=503,body='{\"detail\":\"Unavailable\"}',content_type="application/json"))
    page.goto(ROOT+"/v1_checkout/ci-only-order.html",wait_until="domcontentloaded")
    page.locator("#customer-name").fill("Synthetic Parent")
    page.locator("#customer-mobile").fill("0912345678")
    page.locator("#continue-payment").click()
    # Network failure is handled asynchronously; wait for the visible result.
    page.locator("#validation-error").wait_for(state="visible", timeout=10000)
    assert page.locator("#payment-section").is_hidden(), "Never show payable instructions without saved order"
    assert not page.locator("#continue-payment").is_disabled(), "Retry must remain possible"
    context.close()
    print("PASS simulated DB/API failure blocks payment instructions",flush=True)


if __name__ == "__main__":
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for width in (320,360,390,768,1280):
            check(browser,width)
        check_sales_to_api(browser)
        check_failure(browser)
        browser.close()
    with sqlite3.connect(DB) as db:
        rows=db.execute("SELECT status, amount_etb, currency FROM production_orders").fetchall()
        assert len(rows)==6
        assert all(status=="AWAITING_PAYMENT" and amount==1500 and currency=="ETB" for status,amount,currency in rows)
    print("PASS isolated V1 pending-order integration; no real payments or delivery",flush=True)
