"""Per-instance running stats + throttle policy for the instrumentation package.

Split out of the former ``instrumentation.py`` module (behavior unchanged).
Holds ``_INSTANCE_STATS`` (module-level dict keyed by MObject hash) and its
mutators plus the throttle-period constants and ``should_write_snapshot``.
"""

from __future__ import annotations


# Throttle periods.
DEFAULT_THROTTLE_PERIOD = 30
# Watch is a LIVE debugging surface -- the user has it open specifically to
# see values track interactive edits (scrubbing the timeline, dragging a
# driver). Flush its snapshot on EVERY compute (period 1) so it's real-time.
# (Profile stays at 30: its running averages don't need a per-frame flush.)
# The Watch panel reconciles its tree in place, so frequent writes are cheap.
WATCH_THROTTLE_PERIOD = 1


# ---- Per-instance running stats (module-level dict keyed by MObject hash) ----

# Each entry holds the MObjectHandle so we can validate liveness after
# ``file(new=True)`` (Maya recycles hash codes for new nodes; without
# the validation, fresh nodes inherit stale stats from prior nodes).
# {hash(node_obj): {last_us, avg_us, min_us, max_us, count, deep_table?,
#                   _handle, _prev_profile_on, _prev_watch_on}}
_INSTANCE_STATS: dict[int, dict] = {}


def _get_node_handle(node_obj):
    """Build an MObjectHandle for a Maya MObject (works on API 1 + API 2).

    Returns None if neither API can wrap the object.
    """
    try:
        import maya.api.OpenMaya as om2

        return om2.MObjectHandle(node_obj)
    except Exception:
        pass
    try:
        import maya.OpenMaya as om1

        return om1.MObjectHandle(node_obj)
    except Exception:
        pass
    return None


def _get_node_hash(node_obj) -> int:
    """Return a stable hash for a Maya MObject (works on API 1 + API 2)."""
    handle = _get_node_handle(node_obj)
    if handle is not None:
        try:
            return int(handle.hashCode())
        except Exception:
            pass
    # Fallback (only used in tests where node_obj is a sentinel).
    return id(node_obj)


def _handle_alive(handle) -> bool:
    """Check whether a stored MObjectHandle still references a live MObject."""
    if handle is None:
        return True  # Can't validate; assume OK (tests use sentinels).
    try:
        return bool(handle.isAlive()) and bool(handle.isValid())
    except Exception:
        return False


def get_or_create_stats(node_obj) -> dict:
    """Lookup or initialize the running-stats dict for a node.

    Validates that any cached entry is still tracking the same live
    MObject. If Maya recycled the hash code (e.g. after ``file(new=True)``
    or node deletion), the stale entry is evicted before the lookup.
    """
    h = _get_node_hash(node_obj)
    stats = _INSTANCE_STATS.get(h)
    if stats is not None:
        stored_handle = stats.get("_handle")
        if not _handle_alive(stored_handle):
            # Stale: the MObject the stats were tracking is dead.
            _INSTANCE_STATS.pop(h, None)
            stats = None
    if stats is None:
        stats = {
            "last_us": 0.0,
            "avg_us": 0.0,
            "min_us": 0.0,
            "max_us": 0.0,
            "count": 0,
            "deep_table": None,
            # Internal book-keeping for transition detection.
            "_prev_profile_on": False,
            "_prev_deep_on": False,
            "_prev_watch_on": False,
            "_handle": _get_node_handle(node_obj),
        }
        _INSTANCE_STATS[h] = stats
    return stats


def reset_stats(node_obj) -> None:
    """Reset (clear) running stats for a node. Used by the Reset button."""
    h = _get_node_hash(node_obj)
    _INSTANCE_STATS.pop(h, None)


def update_stats(stats: dict, elapsed_us: float) -> None:
    """Update running stats given a new elapsed time (microseconds).

    Uses cumulative running mean so we never overflow on long sessions.
    First sample initializes min/max/avg to that sample.
    """
    n = stats["count"]
    stats["last_us"] = float(elapsed_us)
    if n == 0:
        stats["avg_us"] = float(elapsed_us)
        stats["min_us"] = float(elapsed_us)
        stats["max_us"] = float(elapsed_us)
    else:
        stats["avg_us"] = (stats["avg_us"] * n + elapsed_us) / (n + 1)
        if elapsed_us < stats["min_us"]:
            stats["min_us"] = float(elapsed_us)
        if elapsed_us > stats["max_us"]:
            stats["max_us"] = float(elapsed_us)
    stats["count"] = n + 1


# ---- Throttle policy ----


def should_write_snapshot(count: int, period: int = DEFAULT_THROTTLE_PERIOD) -> bool:
    """Decide whether to flush a snapshot for this compute count.

    Always writes on count==1 (first compute after toggle-on, so the panel
    sees data immediately), then every ``period``-th frame thereafter.
    Returns False for count<=0.
    """
    if count <= 0:
        return False
    if count == 1:
        return True
    return (count % max(1, period)) == 0
