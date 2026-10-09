"""Single-founder QA admin credentials, TOTP, session-cookie & request security.

Credentials are provisioned out-of-band in the host environment, never in DB or Git.
"""
import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

import struct
from argon2 import PasswordHasher, exceptions as argon_errors
from fastapi import HTTPException, Request

COOKIE_NAME = '__Host-pw_admin_session'
SESSION_ABSOLUTE_SECONDS = 8 * 3600
SESSION_IDLE_SECONDS = 20 * 60
MAX_LOGIN_PER_WINDOW = 8
_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


@dataclass(frozen=True)
class FounderSettings:
    username: str
    password_hash: str
    totp_secret: str
    origin: str
    version: str


def config() -> FounderSettings:
    # Founder explicitly enables access only after credentials and DB tests.
    if os.getenv('FOUNDER_ADMIN_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Founder console not enabled')
    username = os.getenv('FOUNDER_USERNAME', '').strip()
    password_hash = os.getenv('FOUNDER_PASSWORD_HASH', '').strip()
    secret = os.getenv('FOUNDER_TOTP_SECRET', '').strip().replace(' ', '')
    origin = os.getenv('ADMIN_ORIGIN', 'https://parentwise-orders-api-qa.onrender.com').rstrip('/')
    if (not username or len(username) > 100 or not password_hash.startswith('$argon2id$')
            or not secret or len(secret) < 32 or not origin.startswith('https://')):
        raise HTTPException(503, 'Founder authentication has not been configured')
    try:
        valid = base64.b32decode(secret.upper(), casefold=True)
        if len(valid) < 20:
            raise ValueError('TOTP secret too short')
    except Exception:
        raise HTTPException(503, 'Founder authentication has not been configured') from None
    version = hashlib.sha256((username + ':' + password_hash + ':' + secret).encode()).hexdigest()
    return FounderSettings(username, password_hash, secret, origin, version)


def verified_password(candidate: str, expected_hash: str) -> bool:
    try:
        return _password_hasher.verify(expected_hash, candidate)
    except (argon_errors.VerifyMismatchError, argon_errors.VerificationError,
            argon_errors.InvalidHashError, ValueError):
        return False


def accepted_totp_step(secret: str, supplied: str, last_step: int, at=None):
    if not supplied.isascii() or len(supplied) != 6 or not supplied.isdecimal():
        return None
    now = int(datetime.now(timezone.utc).timestamp()) if at is None else int(at)
    current = now // 30
    key = base64.b32decode(secret.upper(), casefold=True)
    for step in (current, current - 1, current + 1):
        if step <= last_step:
            continue
        digest = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
        offset = digest[-1] & 15
        code = (int.from_bytes(digest[offset:offset + 4], 'big') & 0x7fffffff) % 1000000
        if hmac.compare_digest(f'{code:06d}', supplied):
            return step
    return None


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hashed_token(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def csrf_token(session: str, version: str) -> str:
    # Derived, not stored as a second client cookie. Only available after login.
    # The confidential session cookie is 256-bit and never exposed to JS.
    raw = hmac.new(session.encode(), ('parentwise-admin-csrf:' + version).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def check_origin(request: Request, cfg: FounderSettings):
    if request.headers.get('origin', '') != cfg.origin:
        raise HTTPException(403, 'Request origin not permitted')
    if request.headers.get('sec-fetch-site', 'same-origin') not in ('same-origin', 'none'):
        raise HTTPException(403, 'Request origin not permitted')


def check_csrf(request: Request, raw_session: str, cfg: FounderSettings):
    expected = csrf_token(raw_session, cfg.version)
    actual = request.headers.get('x-csrf-token', '')
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(403, 'CSRF check failed')


def agent_fingerprint(request: Request) -> str:
    # Weak additional binding; not a substitute for a secret cookie.
    return hashed_token(request.headers.get('user-agent', '')[:300])