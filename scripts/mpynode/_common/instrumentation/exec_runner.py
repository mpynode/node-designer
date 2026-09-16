"""High-level orchestrator + scene-wide toggle scrub for the instrumentation
package.

Split out of the former ``instrumentation.py`` module (behavior unchanged).
The functions below call low-level helpers that now live in sibling modules;
those are imported explicitly (bare-name lookup would fail after the split).
"""

from __future__ import annotations

import time

# Sibling imports. These were same-module globals before the split.
from .stats import (
    DEFAULT_THROTTLE_PERIOD,
    WATCH_THROTTLE_PERIOD,
    get_or_create_stats,
    should_write_snapshot,
    update_stats,
)
from .cprofile_encode import encode_cprofile_stats
from .watch import (
    WATCH_FRAMEWORK_KEY,
    collect_framework_vars,
    filter_watch_vars,
)
from .snapshot_io import (
    DEEP_PROFILE_ENABLED_ATTR_NAME,
    PROFILE_ENABLED_ATTR_NAME,
    WATCH_ENABLED_ATTR_NAME,
    read_toggles,
    write_profile_snapshot,
    write_watch_vars,
)


# ---- High-level orchestrator — called from exec_with_profile_watch ----


def run_instrumented_exec(
    code,
    namespace: dict,
    node_obj,
    *,
    period:    int  = DEFAULT_THROTTLE_PERIOD,
) -> tuple[bool, BaseException | None]:
    """Execute the user code with timing / cProfile / watch instrumentation
    when the corresponding toggles are on. Always increments per-instance
    stats and writes throttled snapshots.

    signature simplified to a SINGLE ``namespace`` dict (was
    separate ``exec_globals`` + ``exec_locals``). Listcomps now see the
    full namespace.

    Returns ``(success, captured_exception)`` so the caller can decide
    whether to skip writing outputs. Toggles are read from the node's
    bool plugs; missing plugs => disabled.
    """
    profile_on, deep_on, watch_on = read_toggles(node_obj)

    # Hot-path: nothing instrumented.
    if not (profile_on or watch_on):
        try:
            exec(code, namespace)
            return True, None
        except BaseException as exc:
            return False, exc

    stats = get_or_create_stats(node_obj)

    # A toggle flipping on resets stats, for a fresh baseline.
    if profile_on and not stats.get("_prev_profile_on", False):
        # New profile session — reset numerics.
        stats["last_us"]    = 0.0
        stats["avg_us"]     = 0.0
        stats["min_us"]     = 0.0
        stats["max_us"]     = 0.0
        stats["count"]      = 0
        stats["deep_table"] = None
    elif watch_on and not stats.get("_prev_watch_on", False):
        # Reset the throttle so the next compute (count==1) writes a snapshot
        # immediately. Otherwise an already-computed node waits until the 30th
        # eval, which reads as "Watch isn't updating".
        stats["count"] = 0
    stats["_prev_profile_on"] = profile_on
    stats["_prev_deep_on"]    = deep_on
    stats["_prev_watch_on"]   = watch_on

    # cProfile setup.
    profiler = None
    if profile_on and deep_on:
        try:
            import cProfile

            profiler = cProfile.Profile()
        except Exception:
            profiler = None

    # Always wall-clock (ns): cProfile adds overhead, and the user sees walls.
    t0 = time.perf_counter_ns() if profile_on else 0

    success = True
    captured: BaseException | None = None
    try:
        if profiler is not None:
            profiler.enable()
            try:
                exec(code, namespace)
            finally:
                profiler.disable()
        else:
            exec(code, namespace)
    except BaseException as exc:
        success  = False
        captured = exc

    if profile_on:
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0  # ns → µs
        update_stats(stats, elapsed_us)
        deep_table = None
        if profiler is not None:
            deep_table = encode_cprofile_stats(profiler)
        # Always store the latest table so the snapshot reflects current
        # state (None when deep_profile is off after being on earlier).
        stats["deep_table"] = deep_table
        if should_write_snapshot(stats["count"], period):
            write_profile_snapshot(node_obj, stats, deep_table)

    if watch_on:
        # Bump count if profile didn't (so throttle still fires for
        # watch-only mode).
        if not profile_on:
            stats["count"] = int(stats.get("count", 0)) + 1
        # Watch flushes every compute (WATCH_THROTTLE_PERIOD == 1) so the
        # panel updates in real time, NOT on the coarse profile cadence.
        if should_write_snapshot(stats["count"], WATCH_THROTTLE_PERIOD):
            watch_dict = filter_watch_vars(namespace)
            # The wrapper's self.X surface rides along under a reserved key --
            # it is already in memory on the SelfProxy, so this costs no
            # evaluation and no plug read.
            framework = collect_framework_vars(namespace)
            if framework:
                watch_dict[WATCH_FRAMEWORK_KEY] = framework
            write_watch_vars(node_obj, watch_dict)

    return success, captured


# ---- scrub instrumentation toggles scene-wide ----


# All mPy* native type names that have the 3 instrumentation toggle attrs
# (declared by api1/api2 helpers.build_internal_attrs).
_MPY_NATIVE_TYPES = (
    "mPyNode",
    "mPyLocator",
    "mPyConstraint",
    "mPyDeformer",
    "mPyIkSolver",
)


def disable_all_instrumentation_toggles_in_scene() -> int:
    """Walk every mPy* node in the current scene and set
    ``profile_enabled``, ``deep_profile_enabled``, and
    ``watch_enabled`` to False.

    Called from NDMainWindow.closeEvent so that closing the Designer
    UI leaves no background instrumentation work running in Maya's
    DG eval. The toggle attrs are declared ``storable=False`` so
    they don't survive ``mc.file -save`` either -- this is the
    in-memory equivalent for the still-loaded session.

    Returns:
        Total number of (node, attr) pairs that were touched.
    """
    import maya.cmds as mc

    touched = 0
    for native_type in _MPY_NATIVE_TYPES:
        nodes = mc.ls(type=native_type) or []
        for node in nodes:
            for attr in (
                PROFILE_ENABLED_ATTR_NAME,
                DEEP_PROFILE_ENABLED_ATTR_NAME,
                WATCH_ENABLED_ATTR_NAME,
            ):
                full = f"{node}.{attr}"
                try:
                    if not mc.objExists(full):
                        continue
                    if mc.getAttr(full):
                        mc.setAttr(full, False)
                        touched += 1
                except Exception:
                    # Locked/connected attr -- skip silently. Better
                    # to leak one toggle than crash the close.
                    pass
    return touched
