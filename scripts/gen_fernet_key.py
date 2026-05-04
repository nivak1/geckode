#!/usr/bin/env python3
"""Print one Fernet key — paste into .env as ENCRYPTION_KEY=..."""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    print(Fernet.generate_key().decode())
