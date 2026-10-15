"""Native dynamic-attr dirty propagation for the API 2.0 MPy* nodes.

PROBLEM
-------
Maya's static ``attributeAffects`` can only relate attributes declared at
``initialize`` time. User inputs/outputs are added dynamically (``addAttr``),
so Maya doesn't know a user input affects a user output -- it leaves the
output "clean" when the input changes, and the node never recomputes.

The old workaround (``auto_dirty``) installed an ``MNodeMessage`` dirty-plug
callback on the SOURCE node and called ``cmds.dgdirty`` from inside it. That
runs DURING dirty propagation and, under the Maya 2026 Evaluation Manager,
crashes (SIGSEGV in ``TdgDirtyAction``).

SOLUTION
--------
Declare the dynamic affects the proper way, from each node's
``setDependentsDirty`` override (which Maya calls during propagation,
on the main thread, and where appending to the affected-plug array is the
sanctioned, crash-free API). :func:`declare_user_affects` appends every
user OUTPUT plug to ``affected_plugs`` whenever a user INPUT plug is the one
being dirtied -- so Maya propagates input->output natively and immediately,
in both DG and EM. No ``cmds``, no worker-thread DG ops, no crash.

The (input-roots, output-names) pair is cached per node and invalidated when
the schema changes (``add_input_attr`` / delete / rename -> ``setInternalValue``)
and wholesale on scene change.
"""

from __future__ import annotations

import maya.api.OpenMaya as om
from mpynode._common.io import serialization

# node hashCode -> (frozenset[input_root_names], tuple[output_names])
_io_cache: dict = {}


def invalidate(node_mobject) -> None:
    """Drop the cached schema for one node (call when its in/out schema
    changes)."""
    try:
        _io_cache.pop(om.MObjectHandle(node_mobject).hashCode(), None)
    except Exception:
        pass


def invalidate_all() -> None:
    """Drop every cached schema (call on scene new/open)."""
    _io_cache.clear()
    _api1_trigger_memo.clear()


# api1 node hashCode -> (raw _inputAttrs string, tuple[user input names]).
#
# SEPARATE from _io_cache on purpose. That cache is keyed by an api2
# MObjectHandle hash; an api1 MObject cannot even be handed to api2 (it raises
# ``TypeError: argument 1 of type 'MObject &'``), and every api2 call in
# _io_names sits inside a bare except -- so routing an api1 node through it
# would return an EMPTY name set and cache nothing, silently dropping every
# user input out of the deformer's dirty triggers.
_api1_trigger_memo: dict = {}


# Cached on the node INSTANCE (``node._mpy_dirty_gate``) as
# {"suspended": bool, "names": frozenset}. DROPPED, not updated, when the
# nodeState / _inputAttrs plug passes through, so the next call re-reads the
# committed value rather than whatever the plug holds mid-set.
_GATE_ATTR = "_mpy_dirty_gate"


def _api1_node_suspended(node_mobject) -> bool:
    """``nodeState`` != Normal, read off the static ``MPxNode::state`` attribute
    (API 1.0). Never raises; an unreadable state reads as live."""
    try:
        import maya.OpenMaya as om1
        import maya.OpenMayaMPx as ommpx

        return om1.MPlug(node_mobject, ommpx.cvar.MPxNode_state).asShort() != 0
    except Exception:
        return False


def api1_dirty_gate(node, plug_name: str):
    """The cheap front of an api1 deformer's ``setDependentsDirty``.

    Returns ``None`` when the node is SUSPENDED (``nodeState`` Has No Effect /
    Blocking -- Convert to C++ sets it on the idle Python node, a user may set
    it by hand): a node that does not evaluate has no user-input dirtiness to
    forward, so the override returns at once. Otherwise returns the frozenset
    of user input names off ``_inputAttrs``.

    Both facts are cached ON THE NODE INSTANCE, so the hot path reads no plug
    at all. Maya passes the ``nodeState`` and ``_inputAttrs`` plugs through
    this very override when they change (measured: a ``setAttr`` on either
    arrives here under that name), and that is when the cache is dropped -- to
    be rebuilt on the next call, once the new value is committed. An instance
    attribute dies with its node, so a reused MObject hash cannot hand a new
    node a stale set, which is the staleness that kept
    :func:`api1_user_input_names` re-reading the plug on every call.

    Why it matters: on the Combo Correctives demo (1306 verts, 167 targets)
    the three overrides ran ~3,800 times a frame in DG mode and ~8,900 in
    Parallel, at ~21 us each -- ~100 ms/frame on a converted node that did
    ZERO deforms, and ~45 of the 79 ms/frame of the live Python node. Through
    the gate a call costs about a microsecond.
    """
    if plug_name == "nodeState" or plug_name == "_inputAttrs":
        try:
            setattr(node, _GATE_ATTR, None)
        except Exception:
            pass
        return frozenset()
    cache = getattr(node, _GATE_ATTR, None)
    if cache is None:
        try:
            mobject = node.thisMObject()
            cache = {"suspended": _api1_node_suspended(mobject),
                     "names": frozenset(api1_user_input_names(mobject))}
        except Exception:
            cache = {"suspended": False, "names": frozenset()}
        try:
            setattr(node, _GATE_ATTR, cache)
        except Exception:
            pass
    if cache["suspended"]:
        return None
    return cache["names"]


def api1_user_input_names(node_mobject) -> tuple:
    """User INPUT names off an api1 node's ``_inputAttrs``, memoized.

    The three api1 deformer ``setDependentsDirty`` overrides
    (mPyDeformer / mPySkinCluster / mPyBlendShape) each re-read and re-decode
    this map on EVERY re-entry, and Maya re-enters them several times per plug
    write. Measured on a 12-input mPyDeformer (713-char map): findPlug+asString
    2.7 us + json decode 3.7 us = 6.7 us per re-entry, 6 re-entries per setAttr.

    The memo is keyed on the RAW STRING as well as the node, so it is
    SELF-INVALIDATING and adds no staleness class of its own: undo/redo, scene
    load, import and a hand-edited map all change the string and re-decode, and
    an MObject hash reused by a different node is harmless -- if the string also
    matches, the decoded names are by definition the same. Only the json decode
    is skipped (6.7 -> 2.7 us, 59%). Skipping the plug read too would be faster
    still (0.13 us) but would have to trust a handle key, which goes stale on
    undo with no error -- and a stale trigger set means the deformer silently
    stops re-evaluating.

    Returns ``()`` on any failure, so a caller's trigger set degrades to its
    static literals exactly as it did when the decode was inline.

    The three overrides no longer call this per re-entry: they go through
    :func:`api1_dirty_gate`, which caches the names on the node INSTANCE and
    only comes back here when Maya has passed the ``_inputAttrs`` plug through
    the override -- so the per-call plug read this memo still pays is now paid
    once per edit of the map, not once per dirty propagation.
    """
    import maya.OpenMaya as om1
    try:
        raw = om1.MFnDependencyNode(node_mobject).findPlug(
            "_inputAttrs", True).asString()
    except Exception:
        return ()
    if not raw:
        return ()
    try:
        key = om1.MObjectHandle(node_mobject).hashCode()
    except Exception:
        key = None
    hit = _api1_trigger_memo.get(key)
    if hit is not None and hit[0] == raw:
        return hit[1]
    try:
        names = tuple(serialization.decode_attr_map(raw).keys())
    except Exception:
        return ()
    if key is not None:
        _api1_trigger_memo[key] = (raw, names)
    return names


def _io_names(node_mobject, in_attr, out_attr):
    try:
        key = om.MObjectHandle(node_mobject).hashCode()
    except Exception:
        key = None
    if key is not None and key in _io_cache:
        return _io_cache[key]
    in_names:  frozenset = frozenset()
    out_names: tuple = ()
    try:
        fn        = om.MFnDependencyNode(node_mobject)
        in_str    = fn.findPlug(in_attr, True).asString()
        out_str   = fn.findPlug(out_attr, True).asString()
        in_map    = serialization.decode_attr_map(in_str) if in_str else {}
        out_map   = serialization.decode_attr_map(out_str) if out_str else {}
        in_names  = frozenset(in_map.keys())
        out_names = tuple(out_map.keys())
    except Exception:
        pass
    if key is not None:
        _io_cache[key] = (in_names, out_names)
    return in_names, out_names


def _leaves_suspension(state_plug) -> bool:
    """True when the ``nodeState`` change now passing through
    ``setDependentsDirty`` leaves a suspended state.

    There the plug still holds the state being left, not the new one
    (measured 2026-10-15 for setAttr, undo and redo), so a non-zero value
    means the node was suspended. A connected ``nodeState`` is not read, since
    the read would evaluate its source in the middle of the propagation: it
    counts as leaving, which costs one extra compute that returns at once.
    Never raises; an unreadable plug counts as leaving."""
    try:
        if state_plug.isDestination:
            return True
        return state_plug.asShort() != 0
    except Exception:
        return True


def declare_user_affects(node_mobject, plug, affected_plugs, in_attr, out_attr,
                         expression_attr=None, extra_trigger_names=(),
                         extra_outputs=(), state_outputs=()):
    """If ``plug`` is a TRIGGER, append every user OUTPUT plug to
    ``affected_plugs``. Coarse but correct: any input can feed any output
    via the user expression, so any input change must dirty every output.

    This is the single sanctioned ``setDependentsDirty`` body for the API 2.0
    MPy* nodes -- routing every node through it means none can re-introduce the
    ``return om.MPxNode.setDependentsDirty(...)`` super-return bug (the
    super-return silently defeats the in-place append, so Maya never recomputes
    the dirtied user outputs). It returns ``None``; callers ``return`` nothing
    after it.

    A plug is a TRIGGER when it is (part of) a user INPUT, OR it is the
    ``expression_attr`` (so editing the Compute source re-dirties outputs), OR
    its root name is in ``extra_trigger_names`` (e.g. MPyConstraint's preset
    inputs), OR the file-read sweep is replaying the node
    (:func:`dirty_file_read_outputs`), OR it is a ``nodeState`` change that
    leaves a suspended state (:func:`_leaves_suspension`). On trigger, each
    MObject in ``extra_outputs`` is appended too
    (native outputs like MPyFile's outColor/outAlpha) -- this happens even when
    the node has no user outputs. On that ``nodeState`` change, so is each
    MObject in ``state_outputs``.

    Leaving a suspended state replays a user-input change. While the node is
    suspended nothing dirties its outputs: :func:`api2_dirty_gate` drops every
    user-input change, and Maya itself stops dirtying outMesh / outCurve /
    outSurface for a changed dynamic input (measured 2026-10-15). A read in
    the meantime leaves the plug clean at its last value, because the
    suspended compute returns None. So the first read after nodeState went
    back to Normal kept that value, and with a connected input the node never
    recovered: the input, never read, stayed dirty, and a dirty plug stops
    every later propagation. ``state_outputs`` carries the native geometry
    output, which a user input reaches through Maya and not through this
    function.

    Entering a suspended state dirties nothing. Under the Evaluation Manager
    a Blocking node's outputs dirtied on the way in stayed dirty while the EM
    cleaned a downstream reader at its old value, and the dirtying on the way
    out then stopped at those outputs (procrustesTags read through a
    decomposeMatrix: stale after resuming). One such case remains: leave
    Blocking and re-enter it with nothing evaluated in between, change an
    input, leave again; under parallel evaluation the first read through the
    downstream node keeps the old value (1 of 1080 probe reads, 2026-10-15),
    while the compiled twin computes it.

    Safe to call from ``setDependentsDirty``: pure plug-array append, no
    ``cmds`` / no DG mutation.
    """
    try:
        in_names, out_names = _io_names(node_mobject, in_attr, out_attr)
        # Normalise compound children / array elements to the root attr
        # name (e.g. "vec.vecX" -> "vec", "arr[3]" -> "arr").
        try:
            pname = plug.partialName(useLongNames=True)
        except Exception:
            pname = None
        root = pname.split(".")[0].split("[")[0] if pname is not None else None

        def _matches(names):
            # Direct hit: a plain input, the compound parent itself, or an array
            # element whose root is the key. OR a compound vector CHILD whose long
            # name carries the axis suffix (e.g. "vecX" / "targetTranslateX") --
            # Maya delivers children to setDependentsDirty with NO parent prefix,
            # so map them back to the parent key. Mirrors the pre-helper detection
            # (MFnAttribute.name + rstrip("XYZ")).
            if root is None:
                return False
            if root in names or pname in names:
                return True
            stripped = root.rstrip("XYZ")
            return stripped != root and stripped in names

        is_user_input = _matches(in_names)
        is_expression = False
        if expression_attr is not None:
            try:
                is_expression = (
                    not expression_attr.isNull()
                    and plug.attribute() == expression_attr
                )
            except Exception:
                is_expression = False
        is_extra_trigger = _matches(extra_trigger_names)
        # Leaving a suspended state replays the user-input changes the node
        # dropped while suspended (see the docstring).
        is_state = pname == "nodeState" and _leaves_suspension(plug)
        # The file-read sweep replays, through this very path, the user-input
        # change the file reader skipped (see dirty_file_read_outputs).
        is_replay = is_state
        if _replaying and not is_replay:
            try:
                is_replay = (om.MObjectHandle(node_mobject).hashCode()
                             in _replaying)
            except Exception:
                is_replay = False

        if not (is_user_input or is_expression or is_extra_trigger
                or is_replay):
            return

        # Native (non-user) outputs the caller wants dirtied alongside the
        # user outputs (e.g. MPyFile's outColor/outAlpha). Appended even when
        # the node has no user outputs.
        natives = tuple(extra_outputs)
        if is_state:
            natives += tuple(state_outputs)
        for out_mobj in natives:
            try:
                if out_mobj is None or out_mobj.isNull():
                    continue
                affected_plugs.append(om.MPlug(node_mobject, out_mobj))
            except Exception:
                pass

        fn = om.MFnDependencyNode(node_mobject)
        for out_name in out_names:
            try:
                out_plug = fn.findPlug(out_name, True)
                affected_plugs.append(out_plug)
                # ARRAY outputs: also dirty each existing element plug, else a
                # downstream node wired to out[i] reads stale (appending only
                # the array parent doesn't propagate to the elements).
                elems = [out_plug]
                if out_plug.isArray:
                    elems = [out_plug.elementByPhysicalIndex(ei)
                             for ei in range(out_plug.numElements())]
                    for e in elems:
                        affected_plugs.append(e)
                # COMPOUND outputs: and each CHILD, for the same reason --
                # dirtying the parent leaves outX / outColorR clean, so a pull
                # on the child alone never reached compute and read the old
                # value (bug 7; the compiled node's attributeAffects reach
                # the children).
                for e in elems:
                    if e.isCompound:
                        for ci in range(e.numChildren()):
                            affected_plugs.append(e.child(ci))
            except Exception:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# File-read sweep. The file reader restores every input value without calling
# ``setDependentsDirty``, so no restored input dirties a DYNAMIC user output:
# after an open, import or reference the interpreted node read each user
# output's default until an input changed, while the compiled twin, whose
# outputs are static attributes, computed (measured 2026-10-15 on every
# mPyNode, mPyConstraint, mPyFile, mPyMesh, mPyNurbsCurve and mPyNurbsSurface
# user output).
#
# ``dgdirty`` cannot repair it: on an output no propagation has ever reached it
# has no effect at all (measured: plug, node, -a and -p alike), and it never
# calls ``setDependentsDirty``. So the sweep replays the skipped propagation:
# a same-value write to the node's ``_profileSnapshotData`` plug makes Maya
# call ``setDependentsDirty`` at once, and :func:`declare_user_affects` treats
# that call as a user-input change, appending exactly what one would dirty.
# The plug is static on every family here (``helpers.build_internal_attrs``),
# internal and not storable: the write sets no modified flag, adds no undo
# entry and records no reference edit (measured on an opened and a referenced
# node). Nothing computes: each output computes on its first pull.
# ---------------------------------------------------------------------------
_REPLAY_PLUG = "_profileSnapshotData"
# MObjectHandles of the nodes built by the file read in progress.
_file_read_nodes: list = []
# hashCodes of the nodes whose setDependentsDirty is being replayed.
_replaying: set = set()


def note_file_read_node(node) -> None:
    """``postConstructor`` hook: queue ``node`` when the file reader is
    building it. Never raises."""
    try:
        import maya.OpenMaya as om1

        if om1.MFileIO.isReadingFile():
            _file_read_nodes.append(om.MObjectHandle(node.thisMObject()))
    except Exception:
        pass


def forget_file_read_nodes() -> None:
    """Drop the queue (kBeforeOpen / kBeforeNew: its nodes are going away)."""
    del _file_read_nodes[:]


def dirty_file_read_outputs() -> int:
    """Dirty the user outputs of every node the last file read queued, as a
    change of each node's user inputs would, then empty the queue. Returns the
    number of nodes.

    Called from the after-open / import / reference callbacks. A read nested
    in another (a reference loading during an open) leaves the queue to the
    outer read's after-event, so nothing is touched before the scene is
    whole. A suspended node is skipped: it forwards no dirtiness
    (:func:`api2_dirty_gate`), and returning it to Normal dirties its outputs
    (:func:`declare_user_affects`).

    Each node gets its own modifier, so a write that fails spoils only its
    own node: one modifier for the whole queue stopped at the first failed
    write and left every node queued after it at its defaults. A node whose
    replay plug has an incoming connection refuses the write, so it is not
    tried; it and any other node whose write fails keep their defaults until
    an input changes, and are named in one warning. Never raises.
    """
    try:
        import maya.OpenMaya as om1

        if om1.MFileIO.isReadingFile():
            return 0
    except Exception:
        pass
    queued = list(_file_read_nodes)
    del _file_read_nodes[:]
    done    = 0
    skipped = []
    for handle in queued:
        name = None
        try:
            if not handle.isValid():
                continue
            node_mobject = handle.object()
            if api2_node_suspended(node_mobject):
                continue
            fn   = om.MFnDependencyNode(node_mobject)
            name = fn.name()
            # Re-read the schema: the reader set it without passing here.
            invalidate(node_mobject)
            plug = fn.findPlug(_REPLAY_PLUG, False)
            if plug.isDestination:
                skipped.append(name)
                continue
            key      = handle.hashCode()
            modifier = om.MDGModifier()
            modifier.newPlugValueString(plug, plug.asString())
        except Exception:
            if name is not None:
                skipped.append(name)
            continue
        _replaying.add(key)
        try:
            modifier.doIt()
            done += 1
        except Exception:
            skipped.append(name)
        finally:
            _replaying.discard(key)
    if skipped:
        _warn_not_dirtied(skipped)
    return done


def _warn_not_dirtied(names) -> None:
    """Name the nodes :func:`dirty_file_read_outputs` could not dirty, on
    stderr and in the log panel. Never raises."""
    import sys

    msg = ("[dirty_affects] after the file read, %d node(s) keep their user "
           "outputs' defaults until an input changes (the %s write failed "
           "or the plug is connected): %s"
           % (len(names), _REPLAY_PLUG, ", ".join(names)))
    try:
        sys.stderr.write(msg + "\n")
    except Exception:
        pass
    try:
        from mpynode._common.util.log_bus import log as _log

        _log(msg, level="warning")
    except Exception:
        pass


def declare_user_affects_api1(node_mobject, plug, affected_plugs, in_attr, out_attr):
    """API 1.0 twin of :func:`declare_user_affects`.

    For the api1 MPx subclasses (``mPyIkSolver`` and friends) whose
    ``setDependentsDirty`` receives ``maya.OpenMaya`` (API 1.0) ``MPlug`` /
    ``MPlugArray`` objects. Same contract: any user INPUT plug change
    dirties every user OUTPUT plug. Pure plug-array append; no ``cmds``.

    Uses its own (non-cached) schema read because the api1 ``MObject`` hash
    space is distinct from the api2 cache keys; the per-call decode is cheap
    relative to a solve and avoids cross-API cache collisions.
    """
    try:
        import maya.OpenMaya as om1
    except Exception:
        return
    try:
        fn = om1.MFnDependencyNode(node_mobject)
        try:
            in_str  = fn.findPlug(in_attr, True).asString()
            out_str = fn.findPlug(out_attr, True).asString()
        except Exception:
            return
        in_map    = serialization.decode_attr_map(in_str) if in_str else {}
        out_map   = serialization.decode_attr_map(out_str) if out_str else {}
        in_names  = set(in_map.keys())
        out_names = list(out_map.keys())
        if not in_names or not out_names:
            return
        try:
            pname = plug.partialName(False, False, False, False, False, True)
        except Exception:
            return
        root = pname.split(".")[0].split("[")[0]
        if root not in in_names and pname not in in_names:
            return
        for out_name in out_names:
            try:
                out_plug = fn.findPlug(out_name, True)
                affected_plugs.append(out_plug)
                # ARRAY outputs: also dirty each existing element plug (api1
                # MPlug uses method-style isArray()/numElements()).
                elems = [out_plug]
                if out_plug.isArray():
                    elems = [out_plug.elementByPhysicalIndex(ei)
                             for ei in range(out_plug.numElements())]
                    for e in elems:
                        affected_plugs.append(e)
                # COMPOUND outputs: and each child, as in the api2 twin.
                for e in elems:
                    if e.isCompound():
                        for ci in range(e.numChildren()):
                            affected_plugs.append(e.child(ci))
            except Exception:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# API 2.0 suspension gate -- the twin of ``api1_dirty_gate`` for the MPy* nodes
# registered through maya.api (mPyNode, mPyMesh, mPyConstraint, mPyFile,
# mPyLocator, mPyNurbsCurve, mPyNurbsSurface). ``MPxNode.state`` is API 1.0
# only, so the plug is found by name.
# ---------------------------------------------------------------------------
_STATE_ATTR_CACHE = "_mpy_state_attr"


def api2_node_suspended(node_mobject) -> bool:
    """``nodeState`` != Normal for an API 2.0 node. Never raises; an unreadable
    state reads as live."""
    try:
        return (om.MFnDependencyNode(node_mobject)
                .findPlug("nodeState", False).asShort() != 0)
    except Exception:
        return False


def api2_dirty_gate(node, plug) -> bool:
    """The cheap front of an API 2.0 node's ``setDependentsDirty``.

    Returns ``True`` when the node is SUSPENDED (``nodeState`` Has No Effect /
    Blocking -- Convert to C++ sets it on the idle Python node, a user may set
    it by hand): a node that does not evaluate has no dirtiness to forward, so
    the override returns at once and the Evaluation Manager never schedules its
    user outputs. Without this the EM evaluated every user output an animated
    input dirtied, whether or not anything read it: Mesh Maze's converted
    Python node kept running its whole expression (60 ms) every frame for its
    int ``solutionSteps`` until BOTH its animated inputs were unplugged, while
    Voxelize -- no user output -- idled at once.

    The fact is cached ON THE NODE INSTANCE, so the hot path reads no plug.
    Maya passes the ``nodeState`` and ``_inputAttrs`` plugs through the
    override when they change; that is when the cache is dropped, to be rebuilt
    on the next call once the new value is committed. Both return False, so
    the override goes on: when ``nodeState`` leaves a suspended state,
    :func:`declare_user_affects` dirties the outputs the node let go stale.

    Never while the Evaluation Manager builds its graph
    (:func:`_em_building_graph`): the graph keeps the affects this override
    declares until the topology changes, and a nodeState change is not one.
    A graph built while the node was suspended had no edge from a user input
    to a user output, so after nodeState went back to Normal an animated input
    no longer reached the outputs: under parallel evaluation a keyed input
    froze the output from the second frame on (mPyNode, mPyConstraint;
    measured 2026-10-15), until ``evaluationManager -invalidate``. The
    compiled twin declares the same edges with ``attributeAffects`` whatever
    its state. A suspended node in the graph is scheduled, and its compute
    returns at once (:func:`api2_suspended_in_block`): Mesh Maze suspended,
    seed and solutionSteps keyed, graph built while suspended, paid 0.35
    ms/frame where it paid 0.31, and ran no expression.
    """
    try:
        pname = plug.partialName(useLongNames=True)
    except Exception:
        pname = ""
    if pname == "nodeState" or pname == "_inputAttrs":
        try:
            setattr(node, _GATE_ATTR, None)
        except Exception:
            pass
        return False
    cache = getattr(node, _GATE_ATTR, None)
    if cache is None:
        try:
            cache = {"suspended": api2_node_suspended(node.thisMObject())}
        except Exception:
            cache = {"suspended": False}
        try:
            setattr(node, _GATE_ATTR, cache)
        except Exception:
            pass
    return bool(cache.get("suspended")) and not _em_building_graph()


def _em_building_graph() -> bool:
    """True while the Evaluation Manager builds its graph, which it does by
    propagating dirtiness through every ``setDependentsDirty``. Read through
    API 1.0, the only one with ``MEvaluationManager``. Never raises; an
    unreadable state reads as not building."""
    try:
        import maya.OpenMaya as om1

        return bool(om1.MEvaluationManager.graphConstructionActive())
    except Exception:
        return False


def api2_suspended_in_block(node, data_block) -> bool:
    """``nodeState`` != Normal read off the DATA BLOCK inside ``compute()`` --
    the one read the Evaluation Manager allows on a worker thread. The
    attribute handle is cached on the node's class (``nodeState`` is a static
    MPxNode attribute, one per type). Never raises; unreadable reads as live.

    Belt and braces with :func:`api2_dirty_gate`: a node suspended BY HAND
    while its outputs are still wired is still asked to compute by whatever
    reads them, and Blocking means "not evaluated"."""
    cls  = type(node)
    attr = getattr(cls, _STATE_ATTR_CACHE, None)
    if attr is None:
        try:
            attr = om.MFnDependencyNode(node.thisMObject()).attribute("nodeState")
        except Exception:
            return False
        try:
            setattr(cls, _STATE_ATTR_CACHE, attr)
        except Exception:
            pass
    try:
        return data_block.inputValue(attr).asShort() != 0
    except Exception:
        return False
