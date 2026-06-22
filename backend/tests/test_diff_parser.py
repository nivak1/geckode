"""Tests for unified-diff parsing: position mapping and budget filtering.

These cover the trickiest correctness logic in the codebase — inline review
comments are anchored by diff position, so a wrong map posts comments on the
wrong lines (or triggers GitHub 422s).
"""

from __future__ import annotations

import unittest

from diff_parser import (
    build_position_map,
    filter_diff,
    should_skip_file,
    split_diff_by_file,
)

# A small, realistic single-file diff: one context line, one deletion,
# two additions, one trailing context line.
SINGLE_FILE_DIFF = """diff --git a/foo.py b/foo.py
index 1234567..89abcde 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 line1
-old2
+new2
+new3
 line4
"""


class BuildPositionMapTests(unittest.TestCase):
    def test_maps_added_lines_to_diff_positions(self) -> None:
        # new-file line -> diff position. Position counts the @@ header and
        # every non-empty content line (context/+/-); added lines are mapped.
        result = build_position_map(SINGLE_FILE_DIFF)
        self.assertEqual(result, {"foo.py": {2: 4, 3: 5}})

    def test_deletions_and_context_are_not_mapped(self) -> None:
        result = build_position_map(SINGLE_FILE_DIFF)["foo.py"]
        # Only the two '+' lines (new-file lines 2 and 3) are keys.
        self.assertEqual(sorted(result.keys()), [2, 3])

    def test_two_files_are_kept_separate(self) -> None:
        two = SINGLE_FILE_DIFF + (
            "diff --git a/bar.py b/bar.py\n"
            "index aaa..bbb 100644\n"
            "--- a/bar.py\n"
            "+++ b/bar.py\n"
            "@@ -10,0 +11,1 @@\n"
            "+added_in_bar\n"
        )
        result = build_position_map(two)
        self.assertIn("foo.py", result)
        self.assertIn("bar.py", result)
        # bar.py: @@ header -> position 1, '+added_in_bar' -> position 2,
        # at new-file line 11 (from the +11 in the hunk header).
        self.assertEqual(result["bar.py"], {11: 2})

    def test_empty_diff_is_empty_map(self) -> None:
        self.assertEqual(build_position_map(""), {})


class FilterDiffTests(unittest.TestCase):
    def test_generated_files_are_dropped(self) -> None:
        lock = (
            "diff --git a/package-lock.json b/package-lock.json\n"
            "--- a/package-lock.json\n"
            "+++ b/package-lock.json\n"
            "@@ -1 +1 @@\n"
            "+lots of generated noise\n"
        )
        assembled, skipped = filter_diff(SINGLE_FILE_DIFF + lock, max_chars=100_000)
        self.assertIn("foo.py", assembled)
        self.assertNotIn("package-lock.json", assembled)
        self.assertTrue(any("package-lock.json" in s for s in skipped))

    def test_largest_file_dropped_when_over_budget(self) -> None:
        small = (
            "diff --git a/small.py b/small.py\n"
            "--- a/small.py\n"
            "+++ b/small.py\n"
            "@@ -1 +1 @@\n"
            "+x\n"
        )
        big = (
            "diff --git a/big.py b/big.py\n"
            "--- a/big.py\n"
            "+++ b/big.py\n"
            "@@ -1 +1 @@\n"
            "+" + ("y" * 500) + "\n"
        )
        assembled, skipped = filter_diff(small + big, max_chars=120)
        # The big file is dropped first; the small one survives.
        self.assertIn("small.py", assembled)
        self.assertTrue(any("big.py" in s for s in skipped))

    def test_single_oversized_file_is_truncated_not_lost(self) -> None:
        big = (
            "diff --git a/big.py b/big.py\n"
            "--- a/big.py\n"
            "+++ b/big.py\n"
            "@@ -1 +1 @@\n"
            "+" + ("y" * 500) + "\n"
        )
        assembled, skipped = filter_diff(big, max_chars=80)
        self.assertIn("truncated", assembled)
        self.assertTrue(any("big.py" in s for s in skipped))

    def test_all_generated_returns_empty(self) -> None:
        lock = (
            "diff --git a/yarn.lock b/yarn.lock\n"
            "--- a/yarn.lock\n"
            "+++ b/yarn.lock\n"
            "@@ -1 +1 @@\n"
            "+noise\n"
        )
        assembled, skipped = filter_diff(lock, max_chars=100_000)
        self.assertEqual(assembled, "")
        self.assertTrue(any("yarn.lock" in s for s in skipped))


class SplitAndSkipTests(unittest.TestCase):
    def test_split_by_file(self) -> None:
        files = split_diff_by_file(SINGLE_FILE_DIFF)
        self.assertEqual(list(files.keys()), ["foo.py"])
        self.assertIn("@@ -1,3 +1,4 @@", files["foo.py"])

    def test_should_skip_file(self) -> None:
        self.assertTrue(should_skip_file("frontend/package-lock.json"))
        self.assertTrue(should_skip_file("a/node_modules/b.js"))
        self.assertTrue(should_skip_file("api/v1_pb2.py"))
        self.assertFalse(should_skip_file("backend/server.py"))


if __name__ == "__main__":
    unittest.main()
