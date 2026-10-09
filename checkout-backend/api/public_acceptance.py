"""Opt-in black-box QA verification through Render's PUBLIC HTTPS endpoint.

No customer records or access tokens are logged. Generates only fictional test
orders; only runs with QA_EXTERNAL_ACCEPTANCE=true + payments disabled.
Temporary diagnostic: disable the environment toggle after one successful run.
"""
import json
import logging
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOG = logging.getLogger("uvicorn.error")
PUBLIC_API = "https://parentwise-orders-api-qa.onrender.com"
DATA = {"customer_name": "QA Fictional Parent", "mobile": "0912345678", "payment_method": "telebirr"}
FORGED = [
    {},
    {"X-Forwarded-For": "198.51.100.10"},
    {"X-Real-IP": "203.0.113.21"},
    {"Forwarded": "for=192.0.2.32"},
    {"X-Forwarded-For": "198.51.100.71, 192.0.2.18",
     "X-Real-IP": "203.0.113.59", "Forwarded": "for=198.51.100.78"}
]


def call(method, path, *, body=None, headers=None, timeout=22):
    reqheaders = {"Accept": "application/json"}
    if body is not None:
        reqheaders["Content-Type"] = "application/json"
    reqheaders.update(headers or {})
    req = Request(PUBLIC_API + path,
                  data=json.dumps(body).encode() if body is not None else None,
                  headers=reqheaders, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(16000)
            return response.status, json.loads(raw or b"{}")
    except HTTPError as error:
        # Never log errors containing secrets or user input.
        error.read(16000)
        return error.code, {}


def create(key=None, forged=None, body=None):
    token = key or secrets.token_urlsafe(32)
    headers = {"Idempotency-Key": token}
    headers.update(forged or {})
    return call("POST", "/api/v1/orders", body=body or DATA, headers=headers)


def assert_status(observed, expected, label):
    if observed != expected:
        raise AssertionError(f"{label}: expected {expected}, got {observed}")


def verify_public_api():
    if os.getenv("APP_MODE") != "qa" or os.getenv("PAYMENTS_ENABLED", "false") != "false":
        raise RuntimeError("External acceptance requires payment-disabled QA")
    if int(os.getenv("CREATE_RATE_LIMIT", "12")) != 12:
        raise RuntimeError("External acceptance expects a quota of 12")
    # Wait until HTTPS public routing targets *this* new deployment.
    for _ in range(45):
        try:
            status, payload = call("GET", "/healthz", timeout=7)
            ready, result = call("GET", "/readyz", timeout=7)
            if (status == 200 and payload.get("rate_policy") == "global-v3-atomic"
                    and payload.get("payments_enabled") is False
                    and ready == 200 and result.get("database") == "ready"):
                break
        except (URLError, TimeoutError, ValueError, OSError):
            pass
        time.sleep(3)
    else:
        raise AssertionError("Public API readiness or revision identity not confirmed")
    LOG.info("PUBLIC QA acceptance: health=200 ready=200 payments_disabled=true")

    first_key = secrets.token_urlsafe(32)
    first_status, first = create(first_key)
    assert_status(first_status, 201, "first order")
    original = first["order"]
    secret = first["access_token"]
    assert original["amount_etb"] == 1500 and original["status"] == "PENDING_PAYMENT"
    assert original["test_mode"] is True
    assert "mobile" not in first and "customer_name" not in first

    # Ten initial new orders (first plus nine), varied peer-forwarding headers.
    seq = [first_status]
    for i in range(9):
        status, _ = create(forged=FORGED[i % len(FORGED)])
        seq.append(status)
    assert seq == [201] * 10, seq
    LOG.info("PUBLIC QA acceptance: initial_new_orders=%s", seq)

    # At 10/12 quota, concurrent *first-use* requests with one idempotency key
    # must ALL receive the same order, consuming exactly one quota slot.
    race_key = secrets.token_urlsafe(32)
    with ThreadPoolExecutor(max_workers=8) as pool:
        race = list(pool.map(lambda i: create(race_key, FORGED[i % len(FORGED)]), range(8)))
    codes = [x[0] for x in race]
    assert codes == [201] * 8, codes
    race_ids = {x[1]["order"]["order_id"] for x in race}
    assert len(race_ids) == 1
    LOG.info("PUBLIC QA acceptance: concurrent_first_use_retry=%s unique_order_count=%s",
             codes, len(race_ids))

    last_code, _ = create(forged=FORGED[3])
    assert_status(last_code, 201, "twelfth unique order")

    blocked = [create(forged=h)[0] for h in FORGED]
    assert blocked == [429] * len(FORGED), blocked
    with ThreadPoolExecutor(max_workers=7) as pool:
        concurrent_block = list(pool.map(lambda i: create(forged=FORGED[i % len(FORGED)])[0], range(7)))
    assert concurrent_block == [429] * 7, concurrent_block
    LOG.info("PUBLIC QA acceptance: quota=12 after_exhaustion=%s concurrent_new=%s",
             blocked, concurrent_block)

    # Successful retries must bypass exhausted *creation* quota, including concurrency.
    retry_code, retry = create(first_key, FORGED[4])
    assert_status(retry_code, 201, "retry after quota exhaustion")
    assert retry["order"]["order_id"] == original["order_id"]
    assert retry["access_token"] == secret
    with ThreadPoolExecutor(max_workers=7) as pool:
        retry_race = list(pool.map(lambda i: create(race_key, FORGED[i % len(FORGED)]), range(7)))
    assert [r[0] for r in retry_race] == [201] * 7
    assert {r[1]["order"]["order_id"] for r in retry_race} == race_ids

    oid = original["order_id"]
    auth, result = call("GET", "/api/v1/orders/" + oid,
                        headers={"Authorization": "Bearer " + secret})
    assert_status(auth, 200, "authorized retrieval")
    assert result["order"]["order_id"] == oid
    unauth, _ = call("GET", "/api/v1/orders/" + oid)
    wrong, _ = call("GET", "/api/v1/orders/" + oid,
                    headers={"Authorization": "Bearer " + secrets.token_urlsafe(32)})
    assert [unauth, wrong] == [404, 404]

    manipulated = dict(DATA, amount_etb=1)
    invalid, _ = create(body=manipulated)
    payment_route, _ = call("POST", "/api/v1/payments/verify", body={})
    assert [invalid, payment_route] == [422, 404]
    LOG.info("PUBLIC QA acceptance: retry=201 concurrent_retry=%s authorized_get=200 "
             "unauthorized_get=[404,404] price_tamper=422 payment_route=404",
             [r[0] for r in retry_race])
    LOG.info("PUBLIC QA ACCEPTANCE PASSED: exactly_12_unique_orders (no real payments)")


def run_in_background():
    try:
        verify_public_api()
    except Exception as error:
        LOG.error("PUBLIC QA ACCEPTANCE FAILED: %s: %s",
                  type(error).__name__, str(error)[:260])


def launch_public_qa_acceptance():
    if os.getenv("QA_EXTERNAL_ACCEPTANCE", "false").lower() != "true":
        return
    # One daemon thread; requests reach the configured PUBLIC HTTPS hostname.
    threading.Thread(target=run_in_background, name="qa-public-acceptance",
                     daemon=True).start()
