"""
AES-256-CFB secret encryption with random IVs, plus an HMAC fingerprint for
ciphertext-free lookups.
"""

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import hashlib
import hmac
import os
import logging

logger = logging.getLogger(__name__)

_V2_PREFIX = "v2:"
_IV_LEN = 16


def _read_key_env_var(key_env_var: str) -> str:
    """Read raw AES/HMAC key material from the named environment variable."""
    value = os.getenv(key_env_var)
    if not value:
        raise ValueError(f"{key_env_var} not found in environment")
    return value


def _derive_key(key_env_var: str) -> bytes:
    return _read_key_env_var(key_env_var).encode().ljust(32, b'0')[:32]


def _legacy_iv(key: bytes) -> bytes:
    """Deterministic IV used by the pre-fingerprint legacy format."""
    return hashlib.sha256(key).digest()[:_IV_LEN]


def _build_cipher(key: bytes, iv: bytes) -> Cipher:
    return Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())


def encrypt_secret(plaintext: str, key_env_var: str = "NEXTAUTH_SECRET") -> str:
    """Encrypt ``plaintext`` and return ``v2:<urlsafe_b64(iv || ciphertext)>``.

    ``key_env_var`` is the **name of the environment variable** that holds the
    AES key material (default ``NEXTAUTH_SECRET``) — not the name/label of the
    secret being encrypted.
    """
    try:
        key = _derive_key(key_env_var)
        iv = os.urandom(_IV_LEN)
        cipher = _build_cipher(key, iv)
        encryptor = cipher.encryptor()
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
        body = base64.urlsafe_b64encode(iv + ciphertext).decode('ascii')
        return f"{_V2_PREFIX}{body}"
    except Exception as e:
        raise ValueError(f"Encryption failed: {str(e)}")


def fingerprint_secret(plaintext: str, key_env_var: str = "NEXTAUTH_SECRET") -> str:
    """HMAC-SHA256(plaintext) hex digest, keyed with the env-var key material.

    Deterministic and indexable. Use as the equality lookup column for stored
    secrets whose ciphertext is randomized (e.g. ``access_tokens.fingerprint``).
    Brute-force resistant for high-entropy plaintexts (issued tokens use
    ``secrets.token_urlsafe(32)``, i.e. 256 bits).

    ``key_env_var`` is the **name of the environment variable** that holds the
    HMAC key material — not the name/label of the value being fingerprinted.
    """
    key = _derive_key(key_env_var)
    return hmac.new(key, plaintext.encode('utf-8'), hashlib.sha256).hexdigest()


def _decrypt_v2(payload: str, key_env_var: str) -> str:
    raw = base64.urlsafe_b64decode(payload.encode('ascii'))
    if len(raw) < _IV_LEN:
        raise ValueError("v2 payload too short to contain IV")
    iv, ciphertext = raw[:_IV_LEN], raw[_IV_LEN:]
    key = _derive_key(key_env_var)
    decryptor = _build_cipher(key, iv).decryptor()
    decrypted_bytes = decryptor.update(ciphertext) + decryptor.finalize()
    return decrypted_bytes.decode('utf-8', errors='strict')


def _decrypt_legacy(payload: str, key_env_var: str) -> str:
    key = _derive_key(key_env_var)
    iv = _legacy_iv(key)
    decryptor = _build_cipher(key, iv).decryptor()
    ciphertext = base64.urlsafe_b64decode(payload.encode('ascii'))
    decrypted_bytes = decryptor.update(ciphertext) + decryptor.finalize()
    return decrypted_bytes.decode('utf-8', errors='strict')


def decrypt_secret(encrypted_secret: str | None, key_env_var: str = "NEXTAUTH_SECRET") -> str | None:
    """Decrypt a value written by :func:`encrypt_secret` (or legacy v1).

    ``key_env_var`` is the **name of the environment variable** that holds the
    AES key material — not the name/label of the value being decrypted.
    """
    if encrypted_secret is None:
        return None
    try:
        if encrypted_secret.startswith(_V2_PREFIX):
            return _decrypt_v2(encrypted_secret[len(_V2_PREFIX):], key_env_var)
        return _decrypt_legacy(encrypted_secret, key_env_var)
    except UnicodeDecodeError as e:
        raise ValueError(f"Decryption resulted in invalid UTF-8 data: {str(e)}")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")
