"""In-process TTL cache for Bearer GitHub OAuth token → internal user id.

Avoids GitHub GET /user on every Next.js API request. Not shared across workers.
"""

from __future__ import annotations

import hashlib
import os
import time

# Seconds before re-validating token against GitHub + DB (plan: 60–120).
BEARER_CACHE_TTL_SEC = float(os.environ.get("BEARER_CACHE_TTL_SEC", "90"))

_CACHE: dict[str, tuple[int, float]] = {}


def _key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_cached_bearer_uid(token: str) -> int | None:
    k = _key(token)
    entry = _CACHE.get(k)
    if entry is None:
        return None
    uid, until = entry
    if time.monotonic() > until:
        del _CACHE[k]
        return None
    return uid


def set_cached_bearer_uid(token: str, uid: int) -> None:
    _CACHE[_key(token)] = (uid, time.monotonic() + BEARER_CACHE_TTL_SEC)
