"""Tests for GitHub webhook HMAC-SHA256 signature verification.

Security-critical: this is the only thing standing between a forged POST and
the review pipeline, so the negative cases matter as much as the positive one.
"""

from __future__ import annotations

import hashlib
import hmac
import unittest

from webhook_security import verify_github_signature

SECRET = "s3cr3t-webhook-token"
BODY = b'{"action":"created","issue":{"number":7}}'


def _sign(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


class VerifyGithubSignatureTests(unittest.TestCase):
    def test_valid_signature_passes(self) -> None:
        self.assertTrue(verify_github_signature(BODY, _sign(BODY, SECRET), SECRET))

    def test_wrong_secret_fails(self) -> None:
        self.assertFalse(
            verify_github_signature(BODY, _sign(BODY, SECRET), "different-secret")
        )

    def test_tampered_body_fails(self) -> None:
        good_sig = _sign(BODY, SECRET)
        self.assertFalse(verify_github_signature(b"tampered-payload", good_sig, SECRET))

    def test_missing_header_fails(self) -> None:
        self.assertFalse(verify_github_signature(BODY, None, SECRET))
        self.assertFalse(verify_github_signature(BODY, "", SECRET))

    def test_empty_secret_fails(self) -> None:
        self.assertFalse(verify_github_signature(BODY, _sign(BODY, SECRET), ""))

    def test_wrong_algorithm_prefix_fails(self) -> None:
        # GitHub's legacy sha1 header (or anything not 'sha256=') is rejected.
        mac = hmac.new(SECRET.encode(), BODY, hashlib.sha1).hexdigest()
        self.assertFalse(verify_github_signature(BODY, f"sha1={mac}", SECRET))

    def test_non_hex_signature_fails(self) -> None:
        self.assertFalse(verify_github_signature(BODY, "sha256=not-hex-zzzz", SECRET))


if __name__ == "__main__":
    unittest.main()
