"""Browser checks for checkout lead capture (no backend, no real network, no order API, no payment).

The lead script is dormant in the site as shipped. This test serves two copies of the site:
  * the shipped copy  - proves nothing is sent and the lead wording stays hidden;
  * a patched copy    - the lead endpoint is a fake host intercepted inside the browser, to prove what is sent,
                        when, and that checkout still works if the endpoint fails.
Run: python qa-tests/lead_capture_checkout.py
"""
import functools
import http.server
import json
import shutil
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1] / "site-preview"
ENDPOINT = "https://leads.example.invalid/api/v1/leads"
CORS = {"access-control-allow-origin": "*", "access-control-allow-headers": "content-type",
        "access-control-allow-methods": "POST, OPTIONS"}
failures = []


def check(condition, message):
    if not condition:
        failures.append(message)
        print("FAIL:", message)


def serve(directory, port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def install_fake_api(context, status=204):
    seen = []

    def handle(route):
        request = route.request
        if request.method == "OPTIONS":
            return route.fulfill(status=204, headers=CORS)
        seen.append(json.loads(request.post_data or "{}"))
        route.fulfill(status=status, headers=CORS, body="")

    context.route(ENDPOINT, handle)
    return seen


def fill_details(page, name="Hanna Bekele", phone="0911223344", method="telebirr", promo=False):
    page.fill("#customer-name", name)
    page.fill("#customer-mobile", phone)
    page.check(f'input[name="payment"][value="{method}"]')
    if promo:
        page.check("#lead-promo")
    page.click("#continue-payment")


def walk_to_telegram(page):
    expect(page.locator("#payment-section")).to_be_visible()
    page.click("#paid-action")
    expect(page.locator("#telegram-section")).to_be_visible()
    page.click("#telegram-handoff", modifiers=[])  # opens a new tab; the click is what is recorded


def main():
    work = Path(tempfile.mkdtemp(prefix="pw-lead-"))
    enabled_dir = work / "enabled"
    shutil.copytree(ROOT, enabled_dir)
    order = enabled_dir / "order.html"
    html = order.read_text(encoding="utf-8")
    assert '<meta name="pw-leads-endpoint" content="">' in html, "dormant meta tag missing"
    order.write_text(html.replace('<meta name="pw-leads-endpoint" content="">',
                                  f'<meta name="pw-leads-endpoint" content="{ENDPOINT}">'), encoding="utf-8")
    shipped, enabled = serve(ROOT, 8771), serve(enabled_dir, 8772)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            channel="chrome" if shutil.which("google-chrome") else None,
            executable_path=shutil.which("chromium") if not shutil.which("google-chrome") else None)

        # 1. As shipped: dormant. No request, no lead wording.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        page = context.new_page()
        requested = []
        page.on("request", lambda r: requested.append(r.url))
        page.goto("http://127.0.0.1:8771/order.html")
        expect(page.locator("#lead-notice")).to_be_hidden()
        check(page.locator("#lead-consent-row").count() == 0, "no order-notice tick box exists")
        expect(page.locator("#lead-promo-row")).to_be_hidden()
        fill_details(page)
        expect(page.locator("#payment-section")).to_be_visible()
        check(not [u for u in requested if "/api/v1/" in u], "dormant checkout must not contact any API")
        context.close()

        # 2. Enabled: wording visible at 375px, sequence and payloads.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        seen = install_fake_api(context)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        expect(page.locator("#lead-notice")).to_be_visible()
        check(page.locator("#lead-consent").count() == 0, "no tick box for the order notice")
        expect(page.locator("#lead-promo-row")).to_be_visible()
        check(not page.locator("#lead-promo").is_checked(), "the promotional box must start unticked")
        box = page.locator("#lead-notice").bounding_box()
        check(box["height"] <= 48, f"the notice must stay small, got {box['height']}px")
        check(page.evaluate("parseFloat(getComputedStyle(document.getElementById('lead-notice')).fontSize)") <= 13, "notice text must be small")
        check(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "no horizontal scroll at 375px")
        fill_details(page, phone="0911 22 33 44", method="bank")  # spaces are accepted and tidied to 0911223344
        expect(page.locator("#payment-section")).to_be_visible()
        page.wait_for_timeout(300)
        check([e["step"] for e in seen] == ["details_submitted", "payment_viewed"], f"after details: {[e['step'] for e in seen]}")
        first = seen[0]
        check(first["phone"] == "0911223344" and first["name"] == "Hanna Bekele" and first["order_contact_notice"] is True and first["promo_opt_in"] is False
              and first["payment_method"] == "bank", "details payload")
        page.click("#paid-action")
        expect(page.locator("#telegram-section")).to_be_visible()
        with context.expect_page() as popup:
            page.click("#telegram-handoff")
        popup.value.close()
        page.wait_for_timeout(300)
        steps = [e["step"] for e in seen]
        check(steps == ["details_submitted", "payment_viewed", "paid_clicked", "proof_viewed", "telegram_opened"], f"sequence: {steps}")
        check(len({e["attempt_id"] for e in seen}) == 1, "one attempt id for the whole checkout")
        check(all("name" not in e and "phone" not in e for e in seen[1:]), "later steps carry no personal data")
        check(not any("Telegram" in json.dumps(e) and "sent" in json.dumps(e) for e in seen), "no 'message sent' claim is made")
        attempt = seen[0]["attempt_id"]

        # 3. Reload and go through again with the same phone typed differently: same attempt, no duplicate details.
        page.reload()
        fill_details(page, phone="+251911223344")
        expect(page.locator("#payment-section")).to_be_visible()
        page.wait_for_timeout(300)
        check({e["attempt_id"] for e in seen} == {attempt}, "same phone in a new format keeps the same attempt in this tab")
        check(sum(1 for e in seen if e["step"] == "details_submitted") == 1, "details are not re-sent for the same attempt")

        # 4. Editing to a different phone starts a new attempt.
        page.click("#change-method")
        fill_details(page, name="Sara Tesfaye", phone="0922334455")
        expect(page.locator("#payment-section")).to_be_visible()
        page.wait_for_timeout(300)
        check(len({e["attempt_id"] for e in seen}) == 2, "a different phone is a different attempt")
        check(seen[-2]["step"] == "details_submitted" and seen[-2]["name"] == "Sara Tesfaye", "second person details")
        context.close()

        # 4b. Ticking the optional promotional box is the only way promo_opt_in becomes true.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        seen = install_fake_api(context)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page, phone="0944556677", promo=True)
        expect(page.locator("#payment-section")).to_be_visible()
        page.wait_for_timeout(300)
        check(seen[0]["promo_opt_in"] is True and seen[0]["order_contact_notice"] is True, "ticked box is sent as promo_opt_in")
        context.close()

        # 5. Invalid details never send anything.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        seen = install_fake_api(context)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page, phone="12345")
        page.wait_for_timeout(300)
        check(seen == [], "invalid phone must not be sent")
        expect(page.locator("#payment-section")).to_be_hidden()
        context.close()

        # 6. A failing endpoint never blocks checkout.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        context.route(ENDPOINT, lambda route: route.abort())
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page)
        expect(page.locator("#payment-section")).to_be_visible()
        page.click("#paid-action")
        expect(page.locator("#telegram-section")).to_be_visible()
        check(not errors, f"page errors when the endpoint fails: {errors}")
        context.close()

        # 7. A 409 (server never saw the details) triggers one resend of the details, then the step.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        log = []
        state = {"first": True}

        def flaky(route):
            request = route.request
            if request.method == "OPTIONS":
                return route.fulfill(status=204, headers=CORS)
            body = json.loads(request.post_data or "{}")
            log.append(body["step"])
            if body["step"] == "payment_viewed" and state["first"]:
                state["first"] = False
                return route.fulfill(status=409, headers=CORS, body="")
            route.fulfill(status=204, headers=CORS, body="")

        context.route(ENDPOINT, flaky)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page)
        expect(page.locator("#payment-section")).to_be_visible()
        page.wait_for_timeout(1200)
        check(log.count("details_submitted") == 2 and log.count("payment_viewed") == 2, f"409 recovery: {log}")
        context.close()
        browser.close()
    shipped.shutdown(); enabled.shutdown()
    shutil.rmtree(work, ignore_errors=True)
    if failures:
        raise SystemExit(f"{len(failures)} lead capture check(s) failed")
    print("PASS: lead capture checkout checks")


if __name__ == "__main__":
    main()
