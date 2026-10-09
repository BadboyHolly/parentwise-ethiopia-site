"""One-time real Render HTTPS QA checkout acceptance; fictitious data only.
Do not enable for production. No order IDs, tokens, or customer PII are logged.
"""
from __future__ import annotations

import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

SITE = 'https://parentwise-ethiopia-qa.onrender.com/order.html'
READY = 'https://parentwise-ethiopia-qa.onrender.com/checkout-qa.js'
API_HOST = 'https://parentwise-orders-api-qa.onrender.com'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def wait_for_updated_static(max_seconds=360):
    start = time.monotonic()
    while time.monotonic() - start < max_seconds:
        try:
            with urlopen(READY, timeout=12) as response:
                data = response.read(30000)
                if response.status == 200 and b'parentwise.qa.checkout.v2' in data:
                    print('PASS deployed frontend script is available', flush=True)
                    return
        except Exception:
            pass
        time.sleep(9)
    raise AssertionError('Updated static checkout was not deployed in time')


def new_page(browser, width=1280, touch=False):
    context = browser.new_context(
        viewport={'width': width, 'height': 844},
        is_mobile=touch, has_touch=touch,
        permissions=['clipboard-read', 'clipboard-write'],
    )
    page = context.new_page()
    page.set_default_timeout(125000)
    page.goto(SITE, wait_until='domcontentloaded', timeout=125000)
    page.locator('#qaOrder').wait_for(state='visible')
    require('TEST MODE' in page.locator('.qa-warning').first.inner_text(), 'QA notice missing')
    require('1,500 ETB' in page.locator('.qa-details').inner_text(), 'Price display incorrect')
    return context, page


def fill(page, method):
    page.locator('#name').fill('QA Fictional Parent')
    page.locator('#mobile').fill('0912345678')
    page.locator('#payment-method').select_option(method)


def created(page, expected_method):
    page.locator('#testPreview').wait_for(state='visible', timeout=125000)
    oid = page.locator('#order-id').inner_text()
    require(oid.startswith('PW-QA-') and len(oid) == 30, 'Unexpected order format')
    require(page.locator('#order-price').inner_text() == '1,500 ETB', 'Server price not displayed')
    require(page.locator('#order-status').inner_text() == 'PENDING_PAYMENT', 'Order status incorrect')
    require(expected_method in page.locator('#order-method').inner_text(), 'Method not shown')
    return oid


def main():
    wait_for_updated_static()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        desktop, page = new_page(browser)
        sends = []
        page.on('request', lambda request: sends.append(1) if request.method == 'POST' and request.url == API_HOST + '/api/v1/orders' else None)
        fill(page, 'telebirr')
        page.locator('#order-submit').click()
        original_id = created(page, 'Telebirr')
        require(len(sends) == 1, 'Desktop unexpectedly sent multiple orders')
        print('PASS desktop actual HTTP POST -> saved QA order; one request', flush=True)

        page.reload(wait_until='domcontentloaded')
        page.locator('#testPreview').wait_for(state='visible', timeout=125000)
        require(page.locator('#order-id').inner_text() == original_id, 'Refresh retrieved a different order')
        require(len(sends) == 1, 'Refresh incorrectly sent a POST')
        print('PASS real protected GET after refresh; no duplicate order', flush=True)

        page.locator('#copy-order-id').click()
        require(page.evaluate('navigator.clipboard.readText()') == original_id, 'Order ID copy failed')
        page.locator('#copy-recovery').click()
        code = page.evaluate('navigator.clipboard.readText()')
        lines = code.splitlines()
        require(len(lines) == 2 and lines[0] == original_id and len(lines[1]) == 43, 'Recovery code malformed')
        print('PASS browser clipboard Order ID and separate recovery token', flush=True)

        # A new browser session has no sessionStorage. Private recovery remains usable.
        reopened, page2 = new_page(browser)
        page2.locator('#recover-toggle').click()
        page2.locator('#recover-order-id').fill(lines[0])
        page2.locator('#recover-token').fill(lines[1])
        page2.locator('#recover-submit').click()
        require(created(page2, 'Telebirr') == original_id, 'Reopen token recovery failed')
        print('PASS manual recovery in a fresh browser session', flush=True)
        reopened.close()

        invalid, invalid_page = new_page(browser)
        fill(invalid_page, 'bank')
        invalid_page.locator('#mobile').fill('0812345678')
        invalid_page.locator('#order-submit').click()
        require(not invalid_page.locator('#mobile').evaluate('(x)=>x.validity.valid'), 'Invalid phone was accepted')
        print('PASS invalid Ethiopian phone blocked client-side', flush=True)
        invalid.close()

        denied, denied_page = new_page(browser)
        denied_page.locator('#recover-toggle').click()
        denied_page.locator('#recover-order-id').fill(lines[0])
        denied_page.locator('#recover-token').fill('A' * 43)
        denied_page.locator('#recover-submit').click()
        denied_page.get_by_text('Order not found or the private token is incorrect', exact=False).wait_for(timeout=125000)
        require(denied_page.locator('#testPreview').is_hidden(), 'Unauthorized user saw order')
        print('PASS wrong token rejected without exposing order', flush=True)
        denied.close()

        mobile, phone = new_page(browser, width=390, touch=True)
        mobile_posts = []
        phone.on('request', lambda request: mobile_posts.append(1) if request.method == 'POST' and request.url == API_HOST + '/api/v1/orders' else None)
        fill(phone, 'bank')
        phone.evaluate("() => {document.querySelector('#order-submit').click(); document.querySelector('#order-submit').click()}")
        created(phone, 'Ethiopian bank')
        require(len(mobile_posts) == 1, 'Double-click produced duplicate HTTP orders')
        require(not phone.evaluate('document.documentElement.scrollWidth > innerWidth + 1'), '390px horizontal overflow')
        print('PASS mobile 390px real API order, double-click guard, no overflow', flush=True)
        mobile.close()
        desktop.close()
        browser.close()
        print('RESULT: LIVE FRONTEND/API CHECKOUT ACCEPTANCE PASS', flush=True)


if __name__ == '__main__':
    main()