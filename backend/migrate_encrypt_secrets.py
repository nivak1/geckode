#!/usr/bin/env python3
"""One-time migration: encrypt plaintext github_user.access_token and connected_repo.webhook_secret.

Prerequisites:
  - Set ENCRYPTION_KEY in .env (same key the app will use at runtime).
  - Generate once: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Rows already encrypted with this key are skipped (decrypt succeeds).
Legacy plaintext rows are encrypted in place.

Usage (from the testings directory):
  python migrate_encrypt_secrets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cryptography.fernet import InvalidToken
from sqlmodel import Session, select

from db import engine, init_db
from models import ConnectedRepo, User
from secrets_storage import FERNET


def _maybe_reencrypt(stored: str) -> tuple[str, bool]:
    """If stored is already Fernet ciphertext for the current key, return unchanged."""
    if not FERNET:
        raise RuntimeError("FERNET not configured")
    try:
        FERNET.decrypt(stored.encode("ascii"))
        return stored, False
    except InvalidToken:
        new_val = FERNET.encrypt(stored.encode("utf-8")).decode("ascii")
        return new_val, True


def main() -> None:
    if not FERNET:
        print(
            "Set ENCRYPTION_KEY in .env to a Fernet key.\n"
            "Generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"",
            file=sys.stderr,
        )
        sys.exit(1)

    init_db()

    users_updated = 0
    repos_updated = 0

    with Session(engine) as session:
        for u in session.exec(select(User)).all():
            old = u.access_token
            new_val, changed = _maybe_reencrypt(old)
            if changed:
                u.access_token = new_val
                session.add(u)
                users_updated += 1

        for r in session.exec(select(ConnectedRepo)).all():
            old = r.webhook_secret
            new_val, changed = _maybe_reencrypt(old)
            if changed:
                r.webhook_secret = new_val
                session.add(r)
                repos_updated += 1

        session.commit()

    print(f"Done. Encrypted users: {users_updated}, connected repos: {repos_updated}.")


if __name__ == "__main__":
    main()
