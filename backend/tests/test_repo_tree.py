"""Tests for the bounded ASCII path-tree appendix."""

from __future__ import annotations

import unittest

from repo_tree import build_tree_appendix


class BuildTreeAppendixTests(unittest.TestCase):
    def test_builds_nested_tree(self) -> None:
        out = build_tree_appendix(["a/b.py", "a/c.py", "d.py"], max_chars=1000)
        for token in ("a", "b.py", "c.py", "d.py"):
            self.assertIn(token, out)
        # uses box-drawing branch characters
        self.assertTrue("└──" in out or "├──" in out)

    def test_generated_paths_filtered_out(self) -> None:
        out = build_tree_appendix(["node_modules/x.js", "src/app.py"], max_chars=1000)
        self.assertNotIn("node_modules", out)
        self.assertIn("src", out)
        self.assertIn("app.py", out)

    def test_empty_after_filtering(self) -> None:
        self.assertEqual(
            build_tree_appendix(["node_modules/x.js"], max_chars=1000),
            "(no paths after filtering)",
        )

    def test_truncates_to_budget(self) -> None:
        paths = [f"dir{i}/file{i}.py" for i in range(200)]
        out = build_tree_appendix(paths, max_chars=120)
        self.assertIn("truncated", out)
        self.assertLessEqual(len(out), 200)


if __name__ == "__main__":
    unittest.main()
