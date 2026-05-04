"""GitHub webhook HMAC-SHA256 verification (X-Hub-Signature-256)."""

import hashlib
import hmac


def verify_github_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Return True if `signature_header` matches HMAC SHA256 of raw_body using secret."""
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected_hex = signature_header.removeprefix("sha256=")
    try:
        expected = bytes.fromhex(expected_hex)
    except ValueError:
        return False
    mac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    return hmac.compare_digest(mac, expected)
