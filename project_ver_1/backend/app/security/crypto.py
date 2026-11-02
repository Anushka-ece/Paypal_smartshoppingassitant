import base64
import hashlib
import os
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import TOKEN_ENCRYPTION_KEY


def _get_aesgcm(key: Optional[str] = None) -> AESGCM:
    """Derives a 256-bit AES key using SHA-256 from the provided key or configured secret."""
    secret = key if key is not None else TOKEN_ENCRYPTION_KEY
    if not secret:
        raise ValueError("TOKEN_ENCRYPTION_KEY must be configured before encrypting PayPal tokens.")
    if key is None and (
        len(secret.encode("utf-8")) < 32
        or secret.startswith(("generate-", "default-dev", "your_", "change-me"))
    ):
        raise ValueError("TOKEN_ENCRYPTION_KEY must be a non-placeholder value of at least 32 bytes.")
    key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
    return AESGCM(key_bytes)


def encrypt_token(raw: str, key: Optional[str] = None) -> str:
    """
    Encrypts a plaintext string using AES-256-GCM authenticated encryption.
    
    Returns a URL-safe base64 string combining the 12-byte nonce, ciphertext, and authentication tag.
    """
    if raw is None:
        raise ValueError("Cannot encrypt None")
    aesgcm = _get_aesgcm(key)
    nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
    data = raw.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_token(cipher: str, key: Optional[str] = None) -> str:
    """
    Decrypts an AES-256-GCM encrypted token string.
    
    Expects a URL-safe base64 string containing a 12-byte nonce followed by ciphertext and tag.
    Raises ValueError if base64 decoding fails, nonce is missing, or authentication fails.
    """
    if cipher is None:
        raise ValueError("Cannot decrypt None")
    try:
        raw_bytes = base64.urlsafe_b64decode(cipher.encode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    if len(raw_bytes) < 12:
        raise ValueError("Ciphertext too short: missing 12-byte nonce")

    nonce = raw_bytes[:12]
    ciphertext = raw_bytes[12:]
    aesgcm = _get_aesgcm(key)

    try:
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed: authentication failure or invalid key: {e}") from e
