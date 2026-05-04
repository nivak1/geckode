"""Parse `/review` issue-comment bodies for optional trailing instructions."""


def parse_review_trigger(body: str) -> tuple[bool, str]:
    """Return (should_run_review, extra_instructions_after_/review)."""
    stripped = (body or "").strip()
    if not stripped.startswith("/review"):
        return False, ""
    rest = stripped[len("/review") :].strip()
    return True, rest
