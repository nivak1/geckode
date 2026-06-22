"""Tests for per-dimension review config parsing, merging, and heuristics."""

from __future__ import annotations

import unittest

from review_dimensions import (
    DEFAULT_REVIEW_DIMENSIONS,
    diff_suggests_security_scrutiny,
    dimensions_to_json,
    estimate_diff_tokens,
    merge_dimensions,
    parse_dimensions_json,
)


class ParseDimensionsTests(unittest.TestCase):
    def test_none_and_empty_return_defaults(self) -> None:
        self.assertEqual(parse_dimensions_json(None), DEFAULT_REVIEW_DIMENSIONS)
        self.assertEqual(parse_dimensions_json("   "), DEFAULT_REVIEW_DIMENSIONS)

    def test_invalid_json_returns_defaults(self) -> None:
        self.assertEqual(parse_dimensions_json("{not json"), DEFAULT_REVIEW_DIMENSIONS)
        self.assertEqual(parse_dimensions_json("[1,2,3]"), DEFAULT_REVIEW_DIMENSIONS)

    def test_valid_levels_applied(self) -> None:
        out = parse_dimensions_json('{"security":"high","performance":"off"}')
        self.assertEqual(out["security"], "high")
        self.assertEqual(out["performance"], "off")
        self.assertEqual(out["maintainability"], "normal")  # untouched -> default

    def test_bogus_level_is_ignored(self) -> None:
        out = parse_dimensions_json('{"security":"ludicrous"}')
        self.assertEqual(out["security"], "normal")


class MergeDimensionsTests(unittest.TestCase):
    def test_none_override_returns_base(self) -> None:
        base = dict(DEFAULT_REVIEW_DIMENSIONS)
        self.assertEqual(merge_dimensions(base, None), base)

    def test_override_applies_valid_only(self) -> None:
        out = merge_dimensions(
            dict(DEFAULT_REVIEW_DIMENSIONS),
            {"security": "low", "performance": "bogus"},
        )
        self.assertEqual(out["security"], "low")
        self.assertEqual(out["performance"], "normal")  # bogus ignored

    def test_json_round_trip(self) -> None:
        d = parse_dimensions_json('{"security":"high","performance":"low","maintainability":"off"}')
        self.assertEqual(parse_dimensions_json(dimensions_to_json(d)), d)


class SecurityHeuristicTests(unittest.TestCase):
    def test_marker_triggers(self) -> None:
        self.assertTrue(diff_suggests_security_scrutiny("user.password = sneaky"))
        self.assertTrue(diff_suggests_security_scrutiny("subprocess.run(cmd, shell=True)"))

    def test_path_hint_triggers(self) -> None:
        self.assertTrue(diff_suggests_security_scrutiny("+++ b/app/auth/login.py"))

    def test_innocuous_diff_does_not_trigger(self) -> None:
        self.assertFalse(diff_suggests_security_scrutiny("def add(a, b):\n    return a + b\n"))

    def test_estimate_tokens_floor(self) -> None:
        self.assertEqual(estimate_diff_tokens(""), 1)
        self.assertEqual(estimate_diff_tokens("abcd"), 1)
        self.assertEqual(estimate_diff_tokens("a" * 400), 100)


if __name__ == "__main__":
    unittest.main()
