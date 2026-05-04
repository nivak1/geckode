"""Best-effort dedup of identical GitHub webhook deliveries (X-GitHub-Delivery).

Runs a TTL sweep only periodically (not on every delivery) to avoid O(N) work
per request when N grows. If the store still exceeds ``_MAX_ENTRIES`` after
removing expired ids, oldest entries are dropped — rare; may allow a duplicate
GitHub redelivery to be processed twice if under extreme memory pressure.
"""

from __future__ import annotations

import time

_TTL_SEC = 600
_MAX_ENTRIES = 50_000
# Run full expiry sweep at most once per this many calls (amortized cleanup).
_CLEANUP_INTERVAL = 64

_store: dict[str, float] = {}
_calls_since_cleanup = 0


def _purge_expired(now: float) -> None:
    cutoff = now - _TTL_SEC
    dead = [k for k, t in _store.items() if t < cutoff]
    for k in dead:
        del _store[k]


def _evict_oldest_until(max_len: int) -> None:
    """Remove lowest-timestamp entries until len(_store) <= max_len."""
    excess = len(_store) - max_len
    if excess <= 0:
        return
    sorted_items = sorted(_store.items(), key=lambda kv: kv[1])
    for k, _ in sorted_items[:excess]:
        del _store[k]


def should_skip_duplicate(delivery_id: str | None) -> bool:
    """Return True if this delivery id was seen recently."""
    if not delivery_id:
        return False

    global _calls_since_cleanup
    now = time.time()

    _calls_since_cleanup += 1
    if _calls_since_cleanup >= _CLEANUP_INTERVAL or len(_store) > _MAX_ENTRIES:
        _calls_since_cleanup = 0
        _purge_expired(now)
        if len(_store) > _MAX_ENTRIES:
            _evict_oldest_until(int(_MAX_ENTRIES * 0.9))

    if delivery_id in _store:
        return True

    _store[delivery_id] = now

    if len(_store) > _MAX_ENTRIES:
        _evict_oldest_until(_MAX_ENTRIES)

    return False
