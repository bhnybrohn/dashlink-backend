"""AES-256 field-level encryption for PII fields (addresses, phone numbers)."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


def _get_key() -> bytes:
    """Derive a 32-byte AES key from the configured encryption key."""
    key = settings.encryption_key.encode("utf-8")
    # Pad or truncate to exactly 32 bytes
    return key.ljust(32, b"\0")[:32]


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext with nonce prefix."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Prefix nonce to ciphertext, then base64 encode
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_value(encrypted: str) -> str:
    """Decrypt a base64-encoded value. Returns plaintext string."""
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted.encode("utf-8"))
    nonce = raw[:12]
    ciphertext = raw[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
