"""Bounded path-tree appendix for LLM prompts (layout / hierarchy awareness)."""

from __future__ import annotations

from diff_parser import should_skip_file


class _TrieNode:
    __slots__ = ("children",)

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}


def _insert(root: _TrieNode, parts: list[str], max_depth: int) -> None:
    node = root
    for i, seg in enumerate(parts[:max_depth]):
        if seg not in node.children:
            node.children[seg] = _TrieNode()
        node = node.children[seg]
        if i == len(parts) - 1:
            break


def _render(node: _TrieNode, prefix: str, lines: list[str], depth: int, max_depth: int) -> None:
    if depth > max_depth:
        return
    keys = sorted(node.children.keys())
    for i, name in enumerate(keys):
        is_last = i == len(keys) - 1
        branch = "└── " if is_last else "├── "
        lines.append(f"{prefix}{branch}{name}")
        child = node.children[name]
        ext = "    " if is_last else "│   "
        _render(child, prefix + ext, lines, depth + 1, max_depth)


def build_tree_appendix(
    paths: list[str],
    *,
    max_chars: int,
    max_depth: int = 14,
) -> str:
    """Build a compact ASCII tree from file paths; skips generated/vendor paths."""
    filtered = sorted({p for p in paths if p and not should_skip_file(p)})
    if not filtered:
        return "(no paths after filtering)"

    root = _TrieNode()
    for p in filtered:
        parts = [x for x in p.replace("\\", "/").split("/") if x]
        if not parts:
            continue
        _insert(root, parts, max_depth)

    lines: list[str] = []
    _render(root, "", lines, 0, max_depth)
    body = "\n".join(lines)
    if len(body) <= max_chars:
        return body

    acc: list[str] = []
    size = 0
    for line in lines:
        add = line + "\n"
        if size + len(add) > max_chars - 40:
            acc.append("[... tree truncated to token budget ...]")
            break
        acc.append(line)
        size += len(add)
    return "\n".join(acc)
