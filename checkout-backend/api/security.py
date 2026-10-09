"""Never log or put access secrets in URLs. HMAC token derives from a secret and a 256-bit client nonce.
A retry with the same idempotency key returns the same token without storing the token plaintext.
The idempotency key is itself a secret and must not be placed in query strings.
"""
import base64
import hashlib
import hmac
import secrets
import uuid


def validate_idempotency_key(key: str) -> str:
    # 256-bit URL-safe random, encoded in 43 characters. A UUID is deliberately too short here.
    if not isinstance(key, str) or len(key) != 43:
        raise ValueError('Generate a new secure idempotency key for this request')
    try:
        payload = base64.urlsafe_b64decode(key + '=')
    except (ValueError, TypeError):
        raise ValueError('Invalid idempotency key') from None
    if len(payload) != 32 or base64.urlsafe_b64encode(payload).decode().rstrip('=') != key:
        raise ValueError('Invalid idempotency key')
    return key


def issue_idempotency_key() -> str:
    return secrets.token_urlsafe(32)


def keyed_token(secret: str, idem_key: str) -> str:
    digest = hmac.new(secret.encode(), ('order-token-v1:' + idem_key).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip('=')


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def order_code() -> str:
    return 'PW-QA-' + secrets.token_hex(12).upper()


def order_id() -> str:
    return str(uuid.uuid4())


def equal_hash(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)