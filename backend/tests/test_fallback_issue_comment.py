"""Tests for Geckode 422 fallback issue-comment parsing."""

from __future__ import annotations

import unittest

from fallback_issue_comment import (
    looks_like_geckode_fallback_aggregate,
    parse_geckode_fallback_issue_body,
)


class ParseFallbackIssueBodyTests(unittest.TestCase):
    def test_two_blocks(self) -> None:
        body = """🤖 Summary

**`src/a.py` (line 10)**

Fix the bug here.

**`src/b.py` (line 3)**

Also wrong.

"""
        items = parse_geckode_fallback_issue_body(body)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["path"], "src/a.py")
        self.assertEqual(items[0]["line"], 10)
        self.assertIn("bug", items[0]["body"])
        self.assertEqual(items[1]["path"], "src/b.py")
        self.assertEqual(items[1]["line"], 3)

    def test_looks_like_aggregate(self) -> None:
        bad = "random discussion"
        good = "🤖 hi\n\n**`x.py` (line 1)**\nfoo"
        self.assertFalse(looks_like_geckode_fallback_aggregate(bad))
        self.assertTrue(looks_like_geckode_fallback_aggregate(good))


if __name__ == "__main__":
    unittest.main()
