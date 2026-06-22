"""Tests for parsing the `/review` trigger comment."""

from __future__ import annotations

import unittest

from review_instructions import parse_review_trigger


class ParseReviewTriggerTests(unittest.TestCase):
    def test_bare_trigger(self) -> None:
        self.assertEqual(parse_review_trigger("/review"), (True, ""))

    def test_trigger_with_instructions(self) -> None:
        self.assertEqual(
            parse_review_trigger("/review focus on the auth changes"),
            (True, "focus on the auth changes"),
        )

    def test_surrounding_whitespace(self) -> None:
        self.assertEqual(parse_review_trigger("   /review   extra   "), (True, "extra"))

    def test_non_trigger(self) -> None:
        self.assertEqual(parse_review_trigger("looks good to me"), (False, ""))

    def test_empty(self) -> None:
        self.assertEqual(parse_review_trigger(""), (False, ""))


if __name__ == "__main__":
    unittest.main()
