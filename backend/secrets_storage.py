"""Encrypt/decrypt secrets stored in SQLite (OAuth tokens, webhook secrets).

Uses Fernet (symmetric AEAD). When ENCRYPTION_KEY is unset, values pass through
unchanged so existing deployments keep working until you add a key and run
migrate_encrypt_secrets.py.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from config import ENCRYPTION_KEY

FERNET: Fernet | None = None

if ENCRYPTION_KEY:
    try:
        FERNET = Fernet(ENCRYPTION_KEY.encode())
    except Exception as e:
        raise RuntimeError(
            "ENCRYPTION_KEY is set but invalid — must be a Fernet key "
            "(run: python -c \"from cryptography.fernet import Fernet; "
            'print(Fernet.generate_key().decode())\")'
        ) from e


def encrypt_for_storage(plaintext: str | None) -> str | None:
    """Encrypt for DB persistence; returns plaintext unchanged if ENCRYPTION_KEY unset."""
    if plaintext is None:
        return None
    if not FERNET:
        return plaintext
    return FERNET.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_from_storage(stored: str | None) -> str | None:
    """Decrypt after loading from DB; if key unset or value is legacy plaintext, returns as-is."""
    if stored is None:
        return None
    if not FERNET:
        return stored
    try:
        return FERNET.decrypt(stored.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return stored
