"""Per-dimension review intensity: security, performance, maintainability."""

from __future__ import annotations

import json
from typing import Literal, TypedDict

DimensionLevel = Literal["off", "low", "normal", "high"]

SPECIALIST_KEYS = ("security", "performance", "maintainability")


class ReviewDimensions(TypedDict):
    security: DimensionLevel
    performance: DimensionLevel
    maintainability: DimensionLevel


DEFAULT_REVIEW_DIMENSIONS: ReviewDimensions = {
    "security": "normal",
    "performance": "normal",
    "maintainability": "normal",
}


def parse_dimensions_json(raw: str | None) -> ReviewDimensions:
    if not raw or not raw.strip():
        return dict(DEFAULT_REVIEW_DIMENSIONS)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return dict(DEFAULT_REVIEW_DIMENSIONS)
    if not isinstance(data, dict):
        return dict(DEFAULT_REVIEW_DIMENSIONS)
    out: ReviewDimensions = dict(DEFAULT_REVIEW_DIMENSIONS)
    for key in SPECIALIST_KEYS:
        v = data.get(key)
        if v in ("off", "low", "normal", "high"):
            out[key] = v  # type: ignore[assignment]
    return out


def merge_dimensions(
    base: ReviewDimensions,
    override: dict[str, str] | None,
) -> ReviewDimensions:
    if not override:
        return base
    out: ReviewDimensions = dict(base)
    for key in SPECIALIST_KEYS:
        v = override.get(key)
        if v in ("off", "low", "normal", "high"):
            out[key] = v  # type: ignore[assignment]
    return out


def dimensions_to_json(d: ReviewDimensions) -> str:
    return json.dumps({k: d[k] for k in SPECIALIST_KEYS}, separators=(",", ":"))


def diff_suggests_security_scrutiny(diff_text: str) -> bool:
    """Heuristic: auth/crypto/secrets or risky APIs → bias toward stronger security model."""
    lower = diff_text.lower()
    markers = (
        "password",
        "secret",
        "token",
        "oauth",
        "authorization",
        "bearer ",
        "cookie",
        "session",
        "sql injection",
        "exec(",
        "eval(",
        "pickle",
        "subprocess",
        "shell=true",
        "__import__",
        "deserialize",
    )
    path_hints = (
        "/auth",
        "auth/",
        "middleware",
        "webhook",
        "crypto",
        "cipher",
        "jwt",
        ".pem",
        "helm/",
    )
    if any(m in lower for m in markers):
        return True
    return any(h in diff_text for h in path_hints)


def estimate_diff_tokens(diff_text: str) -> int:
    return max(1, len(diff_text) // 4)
