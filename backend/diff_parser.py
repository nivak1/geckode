"""Parse unified diffs into structures the rest of the bot can use.

The key concept here is "diff position" — a 1-indexed line number within
each file's diff section, counting the @@ header, context, additions, and
removals. GitHub's review API requires this rather than file line numbers.
"""

import re

from config import SKIP_FILE_PATTERNS

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_DIFF_GIT_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def should_skip_file(path: str) -> bool:
    """True if the file is generated/vendored and not worth reviewing."""
    return any(pat in path for pat in SKIP_FILE_PATTERNS)


def split_diff_by_file(diff_text: str) -> dict[str, str]:
    """Split a multi-file unified diff into {filename: per_file_diff_text}."""
    files: dict[str, str] = {}
    current_file: str | None = None
    current_lines: list[str] = []

    for line in diff_text.splitlines(keepends=True):
        m = _DIFF_GIT_RE.match(line.rstrip("\n"))
        if m:
            if current_file is not None:
                files[current_file] = "".join(current_lines)
            current_file = m.group(2)
            current_lines = [line]
        elif current_file is not None:
            current_lines.append(line)

    if current_file is not None:
        files[current_file] = "".join(current_lines)
    return files


def filter_diff(diff_text: str, max_chars: int) -> tuple[str, list[str]]:
    """Drop generated files, then drop whole files (largest first) until under budget.

    Avoids mid-file truncation so line numbers in the LLM context stay aligned
    with GitHub's full PR diff for position mapping.

    Returns (filtered_diff, list_of_skipped_reasons).
    """
    files = split_diff_by_file(diff_text)
    skipped: list[str] = []

    candidates: dict[str, str] = {}
    for path, chunk in files.items():
        if should_skip_file(path):
            skipped.append(f"{path} (generated/vendored)")
        else:
            candidates[path] = chunk

    if not candidates:
        return "", skipped

    active = set(candidates.keys())

    def total_len() -> int:
        return sum(len(candidates[p]) for p in active)

    while total_len() > max_chars and len(active) > 1:
        largest = max(active, key=lambda p: len(candidates[p]))
        active.remove(largest)
        skipped.append(f"{largest} (excluded: diff budget)")

    # Original git diff order (split_diff_by_file iteration order).
    ordered_paths = [p for p in files if p in active]
    assembled = "".join(candidates[p] for p in ordered_paths)

    if len(assembled) > max_chars and ordered_paths:
        path = ordered_paths[0]
        chunk = candidates[path]
        omitted = len(chunk) - max_chars
        assembled = chunk[:max_chars] + f"\n[... {omitted} chars truncated ...]\n"
        skipped.append(f"{path} (truncated — file exceeds budget alone)")

    return assembled, skipped


def build_position_map(diff_text: str) -> dict[str, dict[int, int]]:
    """Map {filename: {new_file_line: diff_position}} for a unified diff."""
    result: dict[str, dict[int, int]] = {}
    current_file: str | None = None
    position = 0
    new_line = 0

    for line in diff_text.splitlines():
        m_file = _DIFF_GIT_RE.match(line)
        if m_file:
            current_file = m_file.group(2)
            result.setdefault(current_file, {})
            position = 0
            new_line = 0
            continue

        if line.startswith((
            "--- ", "+++ ",
            "index ", "new file", "deleted file",
            "rename ", "similarity ", "copy ",
            "Binary files",
        )):
            continue

        if current_file is None:
            continue

        m_hunk = _HUNK_RE.match(line)
        if m_hunk:
            new_line = int(m_hunk.group(1))
            position += 1
            continue

        if not line:
            continue

        position += 1
        tag = line[0]
        if tag == "+":
            result[current_file][new_line] = position
            new_line += 1
        elif tag == " ":
            new_line += 1
        elif tag == "-":
            pass

    return result
