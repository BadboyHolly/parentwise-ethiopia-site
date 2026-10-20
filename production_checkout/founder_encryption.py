"""Field-bound AES-256-GCM wrappers for payment data stored by the API."""
from __future__ import annotations

from .founder_security import FounderConfig, decrypt_sensitive, encrypt_sensitive


def encrypt_claim_reference(reference: str, cfg: FounderConfig, order_code: str) -> str:
    return encrypt_sensitive(reference, keyring=cfg.encryption_keys,
                             key_id=cfg.active_encryption_key_id,
                             aad=f"parentwise:claim-reference:v1:{order_code}")


def decrypt_claim_reference(envelope: str, cfg: FounderConfig, order_code: str) -> str:
    return decrypt_sensitive(envelope, keyring=cfg.encryption_keys,
                             aad=f"parentwise:claim-reference:v1:{order_code}")


def encrypt_evidence_note(note: str, cfg: FounderConfig, order_code: str, claim_id: str) -> str:
    return encrypt_sensitive(note, keyring=cfg.encryption_keys,
                             key_id=cfg.active_encryption_key_id,
                             aad=f"parentwise:settlement-note:v1:{order_code}:{claim_id}")


def encrypt_exception_note(note: str, cfg: FounderConfig, order_code: str, claim_id: str) -> str:
    return encrypt_sensitive(note, keyring=cfg.encryption_keys,
                             key_id=cfg.active_encryption_key_id,
                             aad=f"parentwise:third-party-exception:v1:{order_code}:{claim_id}")

