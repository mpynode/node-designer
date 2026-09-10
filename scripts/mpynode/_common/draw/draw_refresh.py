"""Auto-refresh timer for MPyLocator (Qt-free helper).

By default Maya only calls MPxDrawOverride.prepareForDraw when a node
is dirty -- which for a vanilla mPyLocator means "on selection state
change" (the only event that invalidates the locator's draw cache
when nothing about the DG is changing). Camera tumble, mouse hover,
frame change without a time-input plug -- none of those re-evaluate
the expression. The sphere "doesn't pulse" because the expression
never re-runs.

This module enables an OPT-IN idle-refresh service: ONE shared 30 fps
timer that calls ``MRenderer.setGeometryDrawDirty(node_obj)`` for every
enabled locator on each tick it lets through. The expression then re-runs
and the gizmo animates smoothly.

Throttle (measured in a live session, 2026-09):

 An unthrottled request every 33 ms forces a FULL viewport redraw 30x/s
 while Maya is idle. Ten interpreted Animated Text locators took 93% of
 the main thread doing nothing; a hundred compiled ones took 98% at 7.8
 fps, forever. The tick itself is the meter: a timer due every 33 ms
 arrives LATE by however long the main thread was busy -- with idle
 redraws the only work, that lateness IS the redraw's cost. The service
 remembers the worst late tick since its last request and never asks for
 the next redraw until ``2 x`` that has passed (``throttle_step``), so
 idle animation stays at or under ~half of the main thread however many
 locators are enabled, and the full tick rate is kept whenever no tick
 runs late (a cheap redraw). One timer for all nodes (not one per node
 as before) so N locators produce one dirty pass per tick, not N
 interleaved ones.

Crash safety (the user hit a crash on file->new with a naive
implementation -- the timer kept firing on a dangling MObject):

 Layer 1: ``MObjectHandle.isValid()`` guard inside every per-node
 tick body. No-op if the node was deleted (defense-in-depth
 fallback if the teardown callbacks lag).
 Layer 2: per-node ``kNodeAboutToDelete`` callback drops THIS
 node's record when the node itself is deleted.
 Layer 3: scene-event ``kBeforeNew`` / ``kBeforeOpen`` /
 ``kMayaExiting`` callbacks tear down ALL records + the shared
 timer + per-node callbacks before the scene-wide MObject
 invalidation pass.

Verified in headless mayapy via the crash repro script: V3 strategy
(layers 1 + 2 + 3) survives file->new with zero crashes. Layer 3 is
the key -- the scene event fires BEFORE the MObjects dangle, so we
get clean removeCallback before the danger window.

Parent-transform world-cache flush (the DNET aim bug):

 When the auto-refresh locator is a shape CHILD of an ``mPyTransform`` (e.g.
 the DNET link line gizmo, reparented under its aim), the tick ALSO writes the
 parent's ``translateX`` to its own current value via the raw api2 ``MPlug``.
 An mPyTransform authors its worldMatrix via ``asMatrix()`` IGNORING its TRS
 channels, so Maya's DAG world-matrix cache -- which it invalidates ONLY on a
 genuine TRS-channel write on the node -- goes STALE when the transform's
 matrix INPUTS change (a spring-solved aim whose knot matrices relax).
 Dirty-propagation callbacks reach only the aim wired to the moved knot; the
 rest freeze until a related knot is manually moved. ``cmds.dgdirty`` does NOT
 flush this cache (verified empirically), so the per-tick fix is a real TRS
 write: setting ``translateX`` to itself is a no-op on the (asMatrix-authored)
 output but forces Maya to recompute the world matrix, reaching EVERY such aim
 each frame so the whole network relaxes live and the aim pivots track. Done
 through ``MPlug.setDouble`` rather than ``cmds.setAttr``, it runs on the main
 thread from the timer, is non-undoable, and adds nothing to the undo queue.

Public API:
 * ``enable(node_obj)`` -- start auto-refresh for this locator
 * ``disable(node_obj)`` -- stop auto-refresh for this locator
 * ``is_enabled(node_obj)`` -- query state
 * ``active_count()`` -- diagnostic: how many locators are enabled
 * ``refresh_stale_parents()`` -- flush all recorded parent transforms once
   (test/diagnostic seam; production flushes happen per node in the tick)
 * ``throttle_step(state, now)`` -- the pure gate the shared tick applies
"""

from __future__ import annotations

import time

import maya.api.OpenMaya as om
import maya.api.OpenMayaRender as omr


# Tick interval in seconds. 30 fps = 33ms is Maya's standard animation rate --
# what playback would deliver if we had a time1 connection.
_REFRESH_INTERVAL_SEC = 1.0 / 30.0

# A tick this much later than the period is read as "the main thread was busy
# with a redraw". Below it is Maya's own cadence, not work: under any redraw
# load the 33 ms timer actually fires every ~47 ms (21 ticks/s measured with
# ten cheap locators), so a threshold under ~1.5 periods throttles scenes that
# could run at full rate. Redraws shorter than this stay invisible (the tick
# arrives on time) and keep the full tick rate.
_LATE_FACTOR = 2.0

# Wait this many times the last redraw's duration before requesting the next
# idle redraw -> idle animation takes at most ~1/_BACKOFF of the main thread.
_BACKOFF = 2.0


# Module state: dict[hash_code, dict(handle, removal_cb_id, parent_handle)]
# Hash code from MObjectHandle.hashCode() is the stable per-node key.
_TIMERS: dict[int, dict] = {}


def _fresh_throttle_state():
    """monotonic seconds, None = never. ``last_redraw`` is the cost applied to
    the current wait; ``pending_max`` the worst late gap seen since the last
    request (becomes ``last_redraw`` at the next one)."""
    return {"last_tick": None, "last_dirty": None, "last_redraw": 0.0, "pending_max": 0.0}


# The ONE shared timer + throttle clocks.
_SHARED: dict = dict(timer_id=None, **_fresh_throttle_state())


# Scene-event callback IDs (registered once on first enable()).
_SCENE_CB_IDS: list = []


# Node-type name whose stale worldMatrix cache the per-tick flush targets when
# an auto-refresh locator is parented under one (see module docstring).
_MPYTRANSFORM_TYPENAME = "mPyTransform"


# ---- Throttle (pure) ----


def throttle_step(state, now, period=_REFRESH_INTERVAL_SEC,
                  late_factor=_LATE_FACTOR, backoff=_BACKOFF):
    """One tick of the throttle: should it request an idle redraw now?

    ``state`` is a dict from :func:`_fresh_throttle_state` (mutated in place).
    A tick that arrives more than ``late_factor x period`` after the previous
    one was held up by a redraw, and the gap IS that redraw's duration (the
    timer can only fire once the main thread is free again). Every tick is
    measured and the WORST late gap since the last request is remembered,
    because Maya may run the tick due right after a request either before or
    after the redraw it triggered -- only one of those two ticks carries the
    cost, and which one is not ours to choose. At the next request that worst
    gap becomes the redraw cost, and the request after it waits ``backoff x``
    that long (never less than one period): an expensive redraw takes at most
    ~1/backoff of the main thread, a cheap one (no late tick seen) resets the
    cost to zero and keeps the full tick rate.
    """
    gap = (now - state["last_tick"]) if state["last_tick"] is not None else period
    state["last_tick"] = now
    if gap > late_factor * period:
        state["pending_max"] = max(state["pending_max"], gap)
    wait = max(period, backoff * state["last_redraw"])
    if state["last_dirty"] is not None and (now - state["last_dirty"]) < wait:
        return False
    state["last_redraw"] = state["pending_max"]
    state["pending_max"] = 0.0
    state["last_dirty"] = now
    return True


# ---- Internal callbacks ----


def _resolve_mpytransform_parent(node_obj: "om.MObject"):
    """If ``node_obj`` (an mPyLocator shape) is a shape child of an
    ``mPyTransform``, return an ``MObjectHandle`` to that parent transform;
    else None. See the module docstring for why the parent needs a per-tick
    world-cache flush."""
    try:
        dag = om.MFnDagNode(node_obj)
        if dag.parentCount() == 0:
            return None
        parent = dag.parent(0)
        if parent.isNull():
            return None
        # NOTE: api2 MFnDependencyNode.typeName is a PROPERTY, not a method --
        # calling it as .typeName() raises "'str' object is not callable",
        # which (swallowed below) previously made EVERY parent resolve to None.
        if om.MFnDependencyNode(parent).typeName == _MPYTRANSFORM_TYPENAME:
            return om.MObjectHandle(parent)
    except Exception:
        pass
    return None


def _flush_parent_transform(parent_handle) -> bool:
    """Flush the recorded parent mPyTransform's stale worldMatrix cache.

    Maya invalidates a DAG transform's WORLD-matrix cache ONLY on a genuine
    TRS-channel write -- verified empirically, ``cmds.dgdirty`` (whole node or
    any matrix plug) does NOT flush it. We therefore write a FREE translate
    channel to its OWN current value through the raw api2 ``MPlug``: a real TRS
    write that flushes the cache without going through the command engine, so it
    is NON-undoable and safe from a timer tick (main thread, adds nothing to the
    undo queue).

    The channel is a NON-source one (``auto_dirty.free_translate_channel``): on
    an aim transform whose ``translateX`` drives the solver's ``tension``,
    writing ``translateX`` would re-solve the whole network on every 30fps tick.
    Returns True if a live parent was flushed."""
    if parent_handle is None or not parent_handle.isValid():
        return False
    try:
        node_obj = parent_handle.object()
        dep = om.MFnDependencyNode(node_obj)
        ch = "translateX"
        try:
            from mpynode._common.plugs.auto_dirty import free_translate_channel

            # Resolve a UNIQUE DAG path: on a duplicated rig two mPyTransforms
            # can share a short name, and an ambiguous ``dep.name()`` makes
            # every ``cmds`` query in ``free_translate_channel`` raise and fall
            # back to ``translateX`` -- the tension source, which re-solves the
            # whole net every tick. Avoiding that is the point of this flush.
            try:
                node_name = om.MFnDagNode(node_obj).partialPathName() or dep.name()
            except Exception:
                node_name = dep.name()
            ch = free_translate_channel(node_name)
        except Exception:
            ch = "translateX"
        plug = om.MPlug(node_obj, dep.attribute(ch))
        plug.setDouble(plug.asDouble())
        return True
    except Exception:
        pass
    return False


def _timer_tick(handle: "om.MObjectHandle", parent_handle=None, *_unused) -> None:
    """Per-node body of a shared tick that the throttle let through.

    Defense layer 1: validate the handle is still good. If the node
    was deleted between scheduling and firing, no-op silently. The
    kNodeAboutToDelete or scene-event callback will reap us shortly.

    If this locator is a shape child of an mPyTransform, ALSO flush that
    parent's stale worldMatrix cache (see module docstring) so a spring-solved
    aim's pivot -- and this gizmo's placement -- track every frame.

    ORDER MATTERS: flush the parent's world cache FIRST, then raise the VP2
    draw-dirty flag. ``setGeometryDrawDirty`` schedules the redraw that will
    call prepareForDraw; if it ran before the flush, that redraw would sample
    the still-stale world matrix and the freshly-flushed value would only be
    picked up on the NEXT tick's redraw -- a systematic one-tick (~33ms)
    latency penalty on the DNET link gizmos. Flushing first lets the redraw
    this tick triggers pick up the fresh matrix immediately.
    """
    try:
        if not handle.isValid():
            return
        _flush_parent_transform(parent_handle)
        omr.MRenderer.setGeometryDrawDirty(handle.object())
    except Exception:
        # Swallow any Maya-API exception. Crashing the timer would
        # crash the entire Maya event loop.
        pass


def _shared_tick(*_unused) -> None:
    """The ONE MTimerMessage callback: apply the throttle, then run every
    enabled node's tick body. Never adds or removes callbacks itself."""
    try:
        if not throttle_step(_SHARED, time.monotonic()):
            return
        for rec in list(_TIMERS.values()):
            _timer_tick(rec["handle"], rec.get("parent_handle"))
    except Exception:
        pass


def _ensure_shared_timer() -> None:
    if _SHARED["timer_id"] is not None:
        return
    _SHARED.update(_fresh_throttle_state())
    _SHARED["timer_id"] = om.MTimerMessage.addTimerCallback(
        _REFRESH_INTERVAL_SEC, _shared_tick)


def _stop_shared_timer() -> None:
    tid = _SHARED["timer_id"]
    _SHARED["timer_id"] = None
    if tid is None:
        return
    try:
        om.MMessage.removeCallback(tid)
    except Exception:
        pass


def _on_node_pre_removal(hash_code: int, *_unused) -> None:
    """Per-node pre-removal callback. Drops THIS node's record when the
    node itself is deleted (e.g. user-initiated delete); the shared timer
    stops with the last record.
    """
    rec = _TIMERS.pop(hash_code, None)
    if rec is None:
        return
    # The removal_cb is firing right now; MMessage releases it on return, so
    # don't remove it manually.
    if not _TIMERS:
        _stop_shared_timer()


def _on_scene_event(*_unused) -> None:
    """Scene-event callback. Tears down ALL records, the shared timer and
    the per-node callbacks BEFORE the scene-wide MObject invalidation
    pass that happens during file->new / file->open.

    This is the critical layer -- it fires while MObjects are still
    valid, so the removeCallback path is safe. Without it, the
    timer would keep firing on dangling MObjects in the window
    between scene-tear-down and the next tick's isValid() check.
    """
    for hash_code, rec in list(_TIMERS.items()):
        removal_cb_id = rec.get("removal_cb_id")
        if removal_cb_id is not None:
            try:
                om.MMessage.removeCallback(removal_cb_id)
            except Exception:
                pass
    _TIMERS.clear()
    _stop_shared_timer()


def _ensure_scene_callbacks_registered() -> None:
    """Register scene-event callbacks once. Idempotent."""
    if _SCENE_CB_IDS:
        return
    for event in (
        om.MSceneMessage.kBeforeNew,
        om.MSceneMessage.kBeforeOpen,
        om.MSceneMessage.kMayaExiting,
    ):
        try:
            cb_id = om.MSceneMessage.addCallback(event, _on_scene_event)
            _SCENE_CB_IDS.append(cb_id)
        except Exception:
            # If we can't register, the system degrades to layer-1
            # safety only (still no-crash thanks to MObjectHandle).
            pass


# ---- Public API ----


def enable(node_obj: "om.MObject") -> None:
    """Start idle redraws for this locator (shared throttled 30 fps timer).

    Idempotent: calling enable() on an already-enabled node is a no-op.
    Safe to call from any callback, including the locator's bridge.

    Crash-safe: scene-event + per-node teardown callbacks are
    registered automatically. file->new, file->open, Maya-exit, and
    per-node delete all clean up cleanly.
    """
    _ensure_scene_callbacks_registered()

    handle = om.MObjectHandle(node_obj)
    code = handle.hashCode()
    if code in _TIMERS:
        return  # already running for this node

    # Record an mPyTransform parent so the tick can flush its stale worldMatrix
    # cache (see module docstring). Resolved once here: prepareForDraw calls
    # enable() AFTER any reparenting, so this is already final.
    parent_handle = _resolve_mpytransform_parent(node_obj)

    # Per-node pre-removal callback (layer 2).
    removal_cb_id = None
    try:
        removal_cb_id = om.MNodeMessage.addNodePreRemovalCallback(
            node_obj,
            lambda *_a: _on_node_pre_removal(code),
        )
    except Exception:
        # Plug-in unloaded or node type not removable. Continue
        # with layers 1 + 3 only.
        pass

    _TIMERS[code] = {
        "handle": handle,
        "removal_cb_id": removal_cb_id,
        "parent_handle": parent_handle,
    }
    _ensure_shared_timer()


def disable(node_obj: "om.MObject") -> None:
    """Stop idle redraws for this locator. No-op if not currently enabled;
    the shared timer stops with the last enabled node.
    """
    handle = om.MObjectHandle(node_obj)
    code = handle.hashCode()
    rec = _TIMERS.pop(code, None)
    if rec is None:
        return
    removal_cb_id = rec.get("removal_cb_id")
    if removal_cb_id is not None:
        try:
            om.MMessage.removeCallback(removal_cb_id)
        except Exception:
            pass
    if not _TIMERS:
        _stop_shared_timer()


def is_enabled(node_obj: "om.MObject") -> bool:
    """Return True if auto-refresh is currently running for this node."""
    handle = om.MObjectHandle(node_obj)
    return handle.hashCode() in _TIMERS


def active_count() -> int:
    """Diagnostic: how many locators are currently enabled (they share one
    timer). Useful for leak detection in tests."""
    return len(_TIMERS)


def refresh_stale_parents() -> int:
    """Flush every recorded parent mPyTransform's worldMatrix cache once --
    equivalent to one shared tick's worth of per-node parent flushes.
    Returns the number of parents flushed.

    Production flushes happen per node inside :func:`_timer_tick`; this is the
    deterministic seam a headless test drives (no Qt idle loop ticks the timer
    in batch) to exercise the same flush the interactive tick performs."""
    n = 0
    for rec in list(_TIMERS.values()):
        if _flush_parent_transform(rec.get("parent_handle")):
            n += 1
    return n


def _reset_all_for_tests() -> None:
    """Test-only: tear down ALL state (records, shared timer, scene
    callbacks, bookkeeping). Real production code should never call this."""
    _on_scene_event()
    for cb_id in _SCENE_CB_IDS:
        try:
            om.MMessage.removeCallback(cb_id)
        except Exception:
            pass
    _SCENE_CB_IDS.clear()
