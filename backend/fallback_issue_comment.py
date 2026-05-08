"""Parse Geckode 422 fallback issue comments (aggregate PR comments, not inline reviews)."""

from __future__ import annotations

import re
from typing import Any

# Matches headers emitted by review_service 422 fallback:
# **`path/to/file.py` (line 42)**
# Matches: **`path/to.py` (line 42)** — same as review_service f"**`{path}` (line {ln})**"
_HEADER_RE = re.compile(
    r"\*\*`([^`]+)`\s*\(\s*line\s+(\d+|[?])\s*\)\*\*",
    re.IGNORECASE,
)


def looks_like_geckode_fallback_aggregate(body: str) -> bool:
    """True if body resembles our fallback blob (bot emoji + path/line headers)."""
    if "🤖" not in body:
        return False
    return bool(_HEADER_RE.search(body))


def parse_geckode_fallback_issue_body(body: str, *, max_items: int = 50) -> list[dict[str, Any]]:
    """Extract path/line/body blocks from a fallback issue comment."""
    items: list[dict[str, Any]] = []
    matches = list(_HEADER_RE.finditer(body))
    for i, m in enumerate(matches):
        path = m.group(1).strip()
        line_raw = m.group(2)
        try:
            line_int: int | None = int(line_raw)
        except ValueError:
            line_int = None
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[start:end].strip()
        items.append({"path": path, "line": line_int, "body": chunk})
        if len(items) >= max_items:
            break
    return items
