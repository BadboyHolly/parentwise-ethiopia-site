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
        print("::error::" + " ".join(str(message).split())[:900])


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


QUEUE = "parentwise-lead-queue-v2"


def scripted_api(context, decide):
    """Fake lead endpoint. decide(body, n) -> HTTP status, or None to drop the connection. Every request is logged as (body, status)."""
    log = []

    def handle(route):
        request = route.request
        if request.method == "OPTIONS":
            return route.fulfill(status=204, headers=CORS)
        body = json.loads(request.post_data or "{}")
        status = decide(body, len(log))
        log.append((body, status))
        if status is None:
            return route.abort()
        route.fulfill(status=status, headers=CORS, body="")

    context.route(ENDPOINT, handle)
    return log


def queued(page):
    return page.evaluate(f"JSON.parse(localStorage.getItem('{QUEUE}') || '[]')")


def set_promo(page, value):
    """Change the optional follow-up box the way the customer does (the box may be scrolled out of the details form by then)."""
    page.evaluate("""(v) => { const c = document.getElementById('lead-promo'); c.checked = v; c.dispatchEvent(new Event('change', {bubbles: true})); }""", value)


def accepted(log, step=None):
    return [b for b, st in log if st is not None and 200 <= st < 300 and (step is None or b["step"] == step)]


def until(page, condition, timeout=8000):
    """Poll instead of sleeping, so a slow machine only makes the test wait longer, never fail."""
    waited = 0
    while waited < timeout:
        if condition():
            return True
        page.wait_for_timeout(100)
        waited += 100
    return condition()


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
        chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
        browser = playwright.chromium.launch(
            headless=True,
            channel="chrome" if shutil.which("google-chrome") else None,
            executable_path=str(chrome) if chrome.exists() else (shutil.which("chromium") if not shutil.which("google-chrome") else None))

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

        # 8. A busy server (503) or a dropped request is retried once, quietly, and the visitor never notices.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        tries = []

        def busy_then_ok(route):
            request = route.request
            if request.method == "OPTIONS":
                return route.fulfill(status=204, headers=CORS)
            body = json.loads(request.post_data or "{}")
            tries.append(body["step"])
            if tries.count("details_submitted") == 1 and body["step"] == "details_submitted":
                return route.fulfill(status=503, headers=CORS, body="")
            route.fulfill(status=204, headers=CORS, body="")

        context.route(ENDPOINT, busy_then_ok)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page)
        expect(page.locator("#payment-section")).to_be_visible()
        page.wait_for_timeout(3500)
        check(tries.count("details_submitted") == 2, f"one retry after a 503: {tries}")
        context.close()

        # 9. A failed submission is not lost: it waits in the browser and is delivered on the next page load.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        state = {"down": True}
        log = scripted_api(context, lambda body, n: 503 if state["down"] else 204)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page, name="Hanna Bekele", phone="0911223344", promo=True)
        expect(page.locator("#payment-section")).to_be_visible()
        until(page, lambda: len(queued(page)) == 2)
        check(accepted(log) == [], "nothing is accepted while the server is down")
        waiting = queued(page)
        check([i["body"]["step"] for i in waiting] == ["details_submitted", "payment_viewed"], f"events wait in the browser: {[i['body']['step'] for i in waiting]}")
        check(waiting[0]["body"]["promo_opt_in"] is True, "the waiting details keep the customer's tick")
        state["down"] = False
        page.reload()
        until(page, lambda: len(accepted(log)) >= 2 and queued(page) == [])
        steps = [b["step"] for b in accepted(log)]
        first_seen = [x for i, x in enumerate(steps) if x not in steps[:i]]
        check(first_seen == ["details_submitted", "payment_viewed"], f"delivered after the reload, in order (identical repeats allowed): {steps}")
        check(len({b["attempt_id"] for b in accepted(log)}) == 1, "the delivered events keep the original attempt id")
        check(queued(page) == [], "the queue is empty once the server accepted everything")
        context.close()

        # 9b. Closing the tab entirely and coming back later (a new tab in the same browser) also delivers it.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        state = {"down": True}
        log = scripted_api(context, lambda body, n: 503 if state["down"] else 204)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page, name="Sara Tesfaye", phone="0922334455")
        expect(page.locator("#payment-section")).to_be_visible()
        until(page, lambda: len(log) >= 1 and len(queued(page)) == 2)
        page.close()
        state["down"] = False
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        until(page, lambda: len(accepted(log, "details_submitted")) >= 1)
        sent = accepted(log, "details_submitted")
        check(len(sent) == 1 and sent[0]["name"] == "Sara Tesfaye" and sent[0]["phone"] == "0922334455", f"details delivered from a new tab: {sent}")
        context.close()

        # 10. A dropped connection is retried when the connection comes back (online) and when the tab is shown again (visibility).
        for label, fire in (("online", "window.dispatchEvent(new Event('online'))"),
                            ("visibility", "document.dispatchEvent(new Event('visibilitychange'))")):
            context = browser.new_context(viewport={"width": 375, "height": 860})
            state = {"down": True}
            log = scripted_api(context, lambda body, n: None if state["down"] else 204)
            page = context.new_page()
            page.goto("http://127.0.0.1:8772/order.html")
            fill_details(page)
            expect(page.locator("#payment-section")).to_be_visible()
            until(page, lambda: len(log) >= 1 and len(queued(page)) == 2)
            state["down"] = False
            page.evaluate(fire)
            until(page, lambda: len(accepted(log)) >= 2, timeout=1200)  # well under the 1.5 s timer: the trigger did it
            check([b["step"] for b in accepted(log)] == ["details_submitted", "payment_viewed"], f"{label}: delivered without waiting for the timer: {[b['step'] for b, _ in log]}")
            context.close()

        # 11. Retries are bounded: a server that stays busy is not hammered, and the events are kept.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        log = scripted_api(context, lambda body, n: 503)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page)
        expect(page.locator("#payment-section")).to_be_visible()
        page.wait_for_timeout(7000)
        attempts = len(log)
        check(2 <= attempts <= 4, f"bounded backoff: {attempts} sends in 7s while the server is busy")
        check(len(queued(page)) == 2, "events are kept while the server stays busy")
        context.close()

        # 12. Ticking then un-ticking the follow-up box while the server is down: only the customer's final answer is ever sent.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        state = {"down": True}
        log = scripted_api(context, lambda body, n: 503 if state["down"] else 204)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page)
        expect(page.locator("#payment-section")).to_be_visible()
        until(page, lambda: len(log) >= 1)                 # the first send was refused ...
        page.wait_for_timeout(300)                         # ... and has fully finished; the retry timer is 1.5 s or more away
        set_promo(page, True)
        set_promo(page, False)
        waiting = [i for i in queued(page) if i["body"]["step"] == "details_submitted"]
        check(len(waiting) == 1 and waiting[0]["body"]["promo_opt_in"] is False, f"one waiting details event carrying the final answer: {[i['body']['promo_opt_in'] for i in waiting]}")
        state["down"] = False
        page.reload()
        until(page, lambda: len(accepted(log)) >= 2 and queued(page) == [])
        flags = [b["promo_opt_in"] for b in accepted(log, "details_submitted")]
        check(flags and set(flags) == {False}, f"the server never sees a tick the customer took back: {flags} log={[(b['step'], b.get('promo_opt_in'), st) for b, st in log]}")
        context.close()

        # 13. Changing the box during the same attempt: each answer is sent, in order, under the same attempt id.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        log = scripted_api(context, lambda body, n: 204)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page)
        expect(page.locator("#payment-section")).to_be_visible()
        until(page, lambda: len(accepted(log)) >= 2 and queued(page) == [])
        for value in (True, False, True):
            before = len(accepted(log, "details_submitted"))
            set_promo(page, value)
            until(page, lambda: len(accepted(log, "details_submitted")) > before and queued(page) == [])
        page.click("#paid-action")
        expect(page.locator("#telegram-section")).to_be_visible()
        until(page, lambda: len(accepted(log)) >= 7 and queued(page) == [])
        details_events = accepted(log, "details_submitted")
        check([b["promo_opt_in"] for b in details_events] == [False, True, False, True], f"answers in order: {[b['promo_opt_in'] for b in details_events]}")
        check(len({b["attempt_id"] for b in accepted(log)}) == 1, "all answers belong to the same attempt")
        check(sum(1 for b in accepted(log) if b["step"] == "payment_viewed") == 1, "steps are not repeated by an answer change")
        # changing the name in the same attempt is sent too; the phone is the attempt's own
        page.evaluate("""() => { const n = document.getElementById('customer-name'); n.value = 'Hanna B. Bekele'; n.dispatchEvent(new Event('change', {bubbles: true})); }""")
        until(page, lambda: accepted(log, "details_submitted")[-1]["name"] == "Hanna B. Bekele")
        check(accepted(log, "details_submitted")[-1]["name"] == "Hanna B. Bekele", "a changed name is sent for the same attempt")
        context.close()

        # 14. A final refusal (422) drops only that event: later events are still delivered and nothing retries forever.
        context = browser.new_context(viewport={"width": 375, "height": 860})
        log = scripted_api(context, lambda body, n: 422 if body["step"] == "details_submitted" else 204)
        page = context.new_page()
        page.goto("http://127.0.0.1:8772/order.html")
        fill_details(page)
        expect(page.locator("#payment-section")).to_be_visible()
        page.click("#paid-action")
        until(page, lambda: len(accepted(log)) >= 3 and queued(page) == [])
        page.wait_for_timeout(2500)  # long enough for any (wrong) retry of the refused event
        check(sum(1 for b, _ in log if b["step"] == "details_submitted") == 1, "a refused event is not retried")
        check([b["step"] for b in accepted(log)] == ["payment_viewed", "paid_clicked", "proof_viewed"], f"later events still go out: {[b['step'] for b in accepted(log)]}")
        check(queued(page) == [], "nothing is left waiting after a final refusal")
        context.close()
        browser.close()
    shipped.shutdown(); enabled.shutdown()
    shutil.rmtree(work, ignore_errors=True)
    if failures:
        raise SystemExit(f"{len(failures)} lead capture check(s) failed")
    print("PASS: lead capture checkout checks")


if __name__ == "__main__":
    main()
