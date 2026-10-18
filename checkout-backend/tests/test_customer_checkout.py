from sqlalchemy import select
pytest_plugins = ['test_admin', 'test_payment_review']
from api import customer_downloads, fulfillment
from api.models import Order, QaDownloadGrant, PaymentEvent
from api.security import hash_value
from test_payment_review import review_env, code, post, check, confirm

TOKEN = 'T' * 43

def customer_headers():
    return {'Authorization': 'Bearer ' + TOKEN}

def setup_order(env, index=0):
    client, maker, headers = env
    order_code = code(index)
    with maker.begin() as db:
        order = db.scalar(select(Order).where(Order.order_code == order_code))
        order.access_token_hash = hash_value(TOKEN)
    fulfillment.mount_fulfillment(client.app, maker)
    customer_downloads.mount_customer_downloads(client.app, maker)
    return client, maker, headers, order_code

def test_customer_claim_requires_private_token_and_is_not_confirmation(review_env):
    client, maker, founder_headers, order_code = setup_order(review_env)
    path = f'/api/v1/orders/{order_code}'
    assert client.post(path + '/simulate-transfer').status_code == 404
    fake = client.post(path + '/simulate-transfer', headers=customer_headers())
    assert fake.status_code == 201 and fake.json()['simulated_only'] is True
    ref = fake.json()['reference']
    claim = client.post(path + '/payment-claim', headers=customer_headers(), json={
        'test_reference': ref, 'reported_amount_etb': 1500, 'currency': 'ETB'})
    assert claim.status_code == 201 and claim.json()['customer_status'] == 'Under Review'
    summary = client.get(path + '/checkout-status', headers=customer_headers()).json()['order']
    assert summary['customer_status'] == 'Under Review'
    assert summary['downloads_ready'] is False
    assert client.get(path + '/downloads/part-1', headers=customer_headers()).status_code == 403
    duplicate = client.post(path + '/payment-claim', headers=customer_headers(), json={
        'test_reference': ref, 'reported_amount_etb': 1500, 'currency': 'ETB'})
    assert duplicate.status_code == 409
    checked = check(client, founder_headers, 0)
    assert checked.json()['independent_check'] == 'MATCHED'
    assert confirm(client, founder_headers, 0).status_code == 200
    summary = client.get(path + '/checkout-status', headers=customer_headers()).json()['order']
    assert summary['customer_status'] == 'Ready to Download'

def test_private_five_pdf_downloads_and_revocation(review_env):
    client, maker, founder_headers, order_code = setup_order(review_env)
    path = f'/api/v1/orders/{order_code}'
    assert client.get(path + '/downloads/part-1', headers=customer_headers()).status_code == 403
    ref = client.post(path + '/simulate-transfer', headers=customer_headers()).json()['reference']
    assert client.post(path + '/payment-claim', headers=customer_headers(), json={
        'test_reference': ref, 'reported_amount_etb': 1500, 'currency': 'ETB'}).status_code == 201
    assert check(client, founder_headers, 0).status_code == 200
    assert confirm(client, founder_headers, 0).status_code == 200
    for i in range(1, 6):
        response = client.get(f'{path}/downloads/part-{i}', headers=customer_headers())
        assert response.status_code == 200 and response.headers['content-type'] == 'application/pdf'
        assert response.content.startswith(b'%PDF-1.4')
        assert b'QA DEMO ONLY' in response.content and b'NOT A PAID PARENTWISE PRODUCT' in response.content
        assert 'no-store' in response.headers['cache-control']
    assert client.get(path + '/downloads/part-6', headers=customer_headers()).status_code == 404
    detail = client.get('/admin/api/orders/' + order_code)
    assert detail.status_code == 200 and detail.json()['qa_downloads']['active'] is True
    revoked = post(client, f'/admin/api/orders/{order_code}/downloads/revoke', founder_headers)
    assert revoked.status_code == 200
    assert client.get(path + '/downloads/part-1', headers=customer_headers()).status_code == 403
    assert client.get(path + '/checkout-status', headers=customer_headers()).json()['order']['customer_status'] == 'Payment Confirmed'
    with maker() as db:
        grant = db.scalar(select(QaDownloadGrant).where(QaDownloadGrant.order_id == '0'))
        assert grant is not None and grant.revoked_at is not None
        events = db.scalars(select(PaymentEvent).where(PaymentEvent.order_id == '0')).all()
        assert any(e.actor == 'qa_customer' and e.action == 'fictional_payment_claim_submitted' for e in events)

def test_checkout_ui_requests_no_personal_details_or_receipts():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    page = root / 'order.html'
    js = root / 'checkout-qa.js'
    html = page.read_text(encoding='utf-8')
    script = js.read_text(encoding='utf-8')
    assert 'type="file"' not in html
    assert 'id="name"' not in html and 'id="mobile"' not in html
    assert 'QA-TELEBIRR-RECIPIENT-001' in script and 'QA-CBE-ACCOUNT-001' in script
    assert 'Fictional QA recipient' in html
