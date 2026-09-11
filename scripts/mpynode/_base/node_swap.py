"""Shared Python->C++ node-swap primitives (single source of truth).

Lifted from ``tools/harness/build_demo_compiled.py`` so the shipped
"Convert to C++" command and the demo-build harness share ONE implementation.
Maya-cmds only: NO wrapper / identity / undo coupling -- the command layer owns
those. The two ``copyAttr(values=True)`` workarounds are MANDATORY: it silently
drops dynamic scalar inputs AND carries no multi-array element values.
"""

from __future__ import annotations


# Typed ARRAY data attributes. These are neither scalars/compounds (so
# ``copyAttr(values=True)`` and the per-attr scalar copy skip them) nor MULTIs
# (so ``copy_multi_values`` skips them too) -- they fell through BOTH paths and
# arrived EMPTY on the compiled sibling. For a blendShape whose baked tables are
# the entire deform that is silent, total corruption: the convert reported only
# the dropped ``targetGeometry`` edges while ``targetDeltas`` went 319044 -> 0
# and every vertex moved. 10 of the 37 shipped compiled types own one of these
# (the three skinClusters' ``paintWeights``, ``twoBoneIK``'s matrixArray, the
# locators' ``ghostFrames``).
#
# Two setAttr shapes, established by measurement: the flat numeric arrays take
# the whole list as ONE argument, while the tuple/matrix-valued ones need an
# explicit count followed by the unpacked elements.
_ARRAY_FLAT = frozenset({"Int32Array", "doubleArray", "floatArray"})
_ARRAY_COUNTED = frozenset({"vectorArray", "pointArray", "stringArray",
                            "matrixArray"})
_ARRAY_TYPES = _ARRAY_FLAT | _ARRAY_COUNTED


def _array_value(plug, typ):
    """Read a typed-array plug. ``cmds.getAttr`` returns ``None`` for
    ``matrixArray`` however it was set, so that one is read through the API --
    a READ, which is free of the undo chunk (only the write has to be an
    undoable command).

    It has to be the DATA HANDLE. Measured on a plug holding two matrices:
    ``cmds.getAttr`` -> None, ``MPlug.asMObject()`` -> 0 matrices (whether the
    plug came from an MSelectionList or findPlug), ``asMDataHandle().data()``
    -> 2. The first two fail silently, which is how an empty copy would sail
    straight through the caller's ``except``.
    """
    import maya.cmds as mc

    if typ != "matrixArray":
        return mc.getAttr(plug)
    import maya.api.OpenMaya as om2

    sel = om2.MSelectionList()
    sel.add(plug)
    p = sel.getPlug(0)
    handle = p.asMDataHandle()
    try:
        return [list(m) for m in om2.MFnMatrixArrayData(handle.data()).array()]
    finally:
        p.destructHandle(handle)


def _set_array_value(dp, typ, val):
    """Write a typed-array plug with the form its type accepts. An EMPTY source
    array writes nothing: the destination default is already empty, and some of
    these types reject a zero-length setAttr."""
    import maya.cmds as mc

    if not val:
        return
    if typ in _ARRAY_FLAT:
        mc.setAttr(dp, val, type=typ)
    else:
        mc.setAttr(dp, len(val), *val, type=typ)


def copy_values(src, dst):
    """Copy scalar / compound / typed-array static values from ``src`` to ``dst``.

    ``copyAttr(values=True)`` carries most values but SILENTLY DROPS some dynamic
    scalar inputs, so the bulk copy is ALWAYS followed by an explicit per-attr
    copy of every writable, non-connected scalar/compound/array."""
    import maya.cmds as mc

    try:
        mc.copyAttr(src, dst, values=True)
    except Exception:
        pass
    for at in (mc.listAttr(src, write=True, visible=True) or []):
        base = at.split(".")[0]
        if not mc.attributeQuery(base, node=dst, exists=True):
            continue
        sp, dp = src + "." + at, dst + "." + at
        try:
            if mc.getAttr(sp, lock=True):
                continue
            if mc.listConnections(sp, s=True, d=False, plugs=True):
                continue
            typ = mc.getAttr(sp, type=True)
            if typ in _ARRAY_TYPES:
                _set_array_value(dp, typ, _array_value(sp, typ))
                continue
            val = mc.getAttr(sp)
            if typ in ("double3", "float3"):
                mc.setAttr(dp, *val[0], type=typ)
            elif typ == "string":
                mc.setAttr(dp, val if val is not None else "", type="string")
            elif typ == "matrix":
                mc.setAttr(dp, *val, type="matrix")
            elif isinstance(val, (int, float, bool)):
                mc.setAttr(dp, val)
        except Exception:
            pass


def _set_scalar_value(sp, dp):
    """Copy ONE leaf scalar/compound/typed-array value from ``sp`` to ``dp``."""
    import maya.cmds as mc

    typ = mc.getAttr(sp, type=True)
    if typ in _ARRAY_TYPES:
        _set_array_value(dp, typ, _array_value(sp, typ))
        return
    val = mc.getAttr(sp)
    if typ == "matrix":
        mc.setAttr(dp, *val, type="matrix")
    elif typ in ("double3", "float3"):
        mc.setAttr(dp, *val[0], type=typ)
    elif typ == "string":
        mc.setAttr(dp, val if val is not None else "", type="string")
    elif isinstance(val, (int, float, bool)):
        mc.setAttr(dp, val)


def _copy_multi_elements(node_src, node_dst, leaf, src_plug, dst_plug):
    """Recursively copy NON-connected element values of the multi attr at
    ``src_plug`` onto ``dst_plug`` (same logical indices). ``leaf`` is the attr's
    short name, used to introspect compound children. Recurses into compound
    elements so nested multis (e.g. skinCluster ``weightList[i].weights[j]``) are
    NOT silently dropped."""
    import maya.cmds as mc

    for i in (mc.getAttr(src_plug, multiIndices=True) or []):
        se = "%s[%d]" % (src_plug, i)
        de = "%s[%d]" % (dst_plug, i)
        try:
            is_compound = mc.getAttr(se, type=True) == "TdataCompound"
        except Exception:
            is_compound = False
        if is_compound:
            for child in (mc.attributeQuery(
                    leaf, node=node_src, listChildren=True) or []):
                if not mc.attributeQuery(child, node=node_dst, exists=True):
                    continue
                # listChildren returns a DOTTED path ("weightList.weights") on
                # cluster/blendShape/softMod and a BARE name ("weights") on
                # skinCluster and addAttr-built compounds. `se`/`de` already
                # carry the ancestors, so only the LAST segment appends --
                # but attributeQuery still needs `child` verbatim, since the
                # bare name is not recognized on the dotted types.
                name = child.rsplit(".", 1)[-1]
                scp, dcp = se + "." + name, de + "." + name
                if mc.attributeQuery(child, node=node_src, multi=True):
                    _copy_multi_elements(node_src, node_dst, child, scp, dcp)
                    continue
                try:
                    if mc.listConnections(scp, s=True, d=False, plugs=True):
                        continue
                    if not mc.getAttr(dcp, settable=True):
                        continue
                    _set_scalar_value(scp, dcp)
                except Exception:
                    pass
            continue
        try:
            if mc.listConnections(se, s=True, d=False, plugs=True):
                continue
            if not mc.getAttr(de, settable=True):
                continue
            _set_scalar_value(se, de)
        except Exception:
            pass


def copy_multi_values(src, dst):
    """Transfer NON-connected MULTI-array element VALUES by LOGICAL index.

    ``copyAttr(values=True)`` copies scalar/compound values but does NOT carry
    multi-array element values, so topology authored with plain ``setAttr`` is
    otherwise LOST on the swap. Connection-driven elements are handled by
    ``rewire`` (skipped here)."""
    import maya.cmds as mc

    for at in (mc.listAttr(src) or []):
        if "." in at or "[" in at:
            continue
        try:
            if not mc.attributeQuery(at, node=src, multi=True):
                continue
            if not mc.attributeQuery(at, node=dst, exists=True):
                continue
        except Exception:
            continue
        _copy_multi_elements(src, dst, at, src + "." + at, dst + "." + at)


def copy_aliases(src, dst):
    """Re-apply ``src``'s attribute ALIASES on ``dst``. Returns the dropped ones.

    ``copyAttr(values=True)`` carries values, never aliases -- so a swapped
    blendShape would keep its weight VALUES but lose every ``weight[i]`` ->
    target-name mapping, and the channel box would show raw indices where the
    interpreted node showed ``browUp``. An alias whose underlying attribute does
    not exist on ``dst`` is reported, not forced.

    Each aliased element also has its ``keyable`` state carried over. Array
    inputs are deliberately non-keyable at both chokepoints (``add_input_attr``
    and the C++ codegen) so numeric multis do not flood the channel box -- but an
    ALIASED element is, by definition, a channel the user named on purpose, and
    that is the one case where the rule is backwards. Copying the flag rather
    than forcing it keeps the exception exactly as narrow as the source node
    made it.

    Call AFTER :func:`copy_multi_values`: aliasing an element of a multi that
    has no values yet would instantiate an empty index.
    """
    import maya.cmds as mc

    flat = mc.aliasAttr(src, query=True) or []
    dropped = []
    for i in range(0, len(flat) - 1, 2):
        alias, plug = flat[i], flat[i + 1]
        base = plug.split(".")[0].split("[")[0]
        desc = "alias %s -> %s" % (alias, plug)
        try:
            if not mc.attributeQuery(base, node=dst, exists=True):
                dropped.append(desc)
                continue
            dplug = "%s.%s" % (dst, plug)
            mc.aliasAttr(alias, dplug)
            try:
                if mc.getAttr("%s.%s" % (src, plug), keyable=True):
                    mc.setAttr(dplug, keyable=True)
            except Exception:
                dropped.append(desc + " (keyable state)")
        except Exception:
            dropped.append(desc)
    return dropped


def rewire(src, dst):
    """Move every connection on ``src`` onto ``dst`` (same attr paths).

    Returns a list of human-readable descriptions of the connections that could
    NOT be moved because the local attribute does not exist on ``dst`` (or the
    reconnect raised) -- so callers can report them instead of silently dropping.
    """
    import maya.cmds as mc

    conns = mc.listConnections(src, connections=True, plugs=True,
                               source=True, destination=True) or []
    dropped = []
    for i in range(0, len(conns), 2):
        local, remote = conns[i], conns[i + 1]
        if "." not in local:
            continue
        attr = local.split(".", 1)[1]
        newlocal = dst + "." + attr
        try:
            is_src = mc.isConnected(local, remote)
        except Exception:
            is_src = False
        desc = ("%s -> %s" % (local, remote)) if is_src else (
            "%s -> %s" % (remote, local))
        try:
            if not mc.objExists(newlocal):
                dropped.append(desc)
                continue
            if is_src:
                mc.connectAttr(newlocal, remote, force=True)
            else:
                mc.connectAttr(remote, newlocal, force=True)
        except Exception:
            dropped.append(desc)
    return dropped


# Infrastructure plugs that must NEVER be rerouted by the coexist convert:
# shading-group membership (instObjGroups/dagSetMembers), containers
# (hyperLayout), and our own link attrs. Matched on the BASE attr name so
# element/child plugs (instObjGroups[0].objectGroups[0]) are caught. Everything
# else on an eligible node is a genuine output or driven input, so a DENYLIST
# never misses a real edge -- unlike an ALLOWLIST, which would silently drop an
# unlisted output and leave the idle Python node driving downstream.
#
# `message` is deliberately NOT here: it is judged by its DESTINATION instead
# (see :func:`_is_message_registry_slot`), because it carries both registry
# plumbing and genuine functional references.
_INFRA_PLUGS = frozenset({
    "instObjGroups", "hyperLayout", "dagSetMembers",
    "mpyCompiledLink", "mpyInterpretedLink",
})


def _is_infra(local_plug):
    """True if ``local_plug`` (``node.attr[...]...``) is an infrastructure plug
    that must NOT be rerouted. A bare node name (no ``.``) is treated as infra
    (nothing to reroute)."""
    if "." not in local_plug:
        return True
    base = local_plug.split(".", 1)[1].split(".")[0].split("[")[0]
    return base in _INFRA_PLUGS


def _is_message_registry_slot(remote_plug):
    """True when ``remote_plug`` -- the DESTINATION of a ``.message`` edge -- is a
    REGISTRY / membership slot rather than a functional reference.

    ``message`` is overloaded. Maya uses it both to enrol a node in bookkeeping
    lists and to let one node NAME another as a functional dependency, and a
    coexist convert must treat those opposites differently: membership belongs to
    the node that is a member (leave it), while a functional reference has to
    follow the compiled sibling (move it) or the sibling is inert -- an ikSolver
    has no other output at all.

    The two are told apart by ARITY, which is what the semantics actually reduce
    to: a registry ACCUMULATES members, so its slot is a multi element
    (``defaultShaderList.shaders[6]``, ``objectSet.dnSetMembers[0]``,
    ``postProcessList.postProcesses[2]``, ``hyperLayout.hyperPosition[0].dependNode``,
    ``ikSystem.ikSolver[1]``), whereas a functional reference names exactly ONE
    node in a single plug (``ikHandle.ikSolver``, ``ikHandle.startJoint``).

    Nothing cheaper works. ``ikSystem.ikSolver[1]`` and ``ikHandle.ikSolver``
    share an attr NAME with opposite meanings, so an attr denylist misfires; and
    ``ikHandle`` is itself an ``isAType`` ``containerBase``, so a destination-type
    denylist would deny the one edge that must move. Arity also degrades
    gracefully for plug-in registries nobody has enumerated.
    """
    return "[" in remote_plug


def _is_movable_output(local_plug, remote_plug):
    """True when the outgoing edge ``local_plug -> remote_plug`` is one a coexist
    convert relocates onto the sibling. Shared by :func:`_transfer_edges` and
    :func:`downstream_dependents` so the "what moved" and "what did not" reports
    can never disagree."""
    if "." not in local_plug or _is_infra(local_plug):
        return False
    base = local_plug.split(".", 1)[1].split(".")[0].split("[")[0]
    if base == "message":
        return not _is_message_registry_slot(remote_plug)
    return True


def _transfer_edges(src, dst, incoming, skip_remote=None):
    """Shared per-edge reroute. ``incoming=True`` DUPLICATES the edges driving
    ``src`` onto ``dst`` (``remote -> dst.attr``; ``src`` keeps its edge, since a
    new destination does not disturb the old one). ``incoming=False`` MOVES the
    edges ``src`` drives onto ``dst`` (``dst.attr -> remote`` with ``force`` --
    which steals ``remote``'s incoming, breaking ``src``'s edge).

    Per-EDGE direction (via ``listConnections(connections=True)``, whose first of
    each pair is always the plug ON ``src``) -- NOT per-plug -- so a dual-role
    passthrough plug is classified correctly (the D1 lesson). Infrastructure
    plugs (see :data:`_INFRA_PLUGS`) are skipped. Multi/compound element edges are
    force-connected (the index is ALLOCATED on ``dst``), never pre-skipped on
    ``objExists`` of an un-instantiated element. Edges whose far end is
    ``skip_remote`` are left alone. Returns the list of edges that could not be
    transferred (base attr missing on ``dst``, or the connect raised)."""
    import maya.cmds as mc

    conns = mc.listConnections(
        src, connections=True, plugs=True,
        source=incoming, destination=not incoming) or []
    dropped = []
    for i in range(0, len(conns), 2):
        local, remote = conns[i], conns[i + 1]
        if skip_remote is not None and _same_node(remote, skip_remote):
            continue
        if incoming:
            if "." not in local or _is_infra(local):
                continue
        elif not _is_movable_output(local, remote):
            continue
        attr = local.split(".", 1)[1]
        newlocal = dst + "." + attr
        base = attr.split(".")[0].split("[")[0]
        desc = ("%s -> %s" % (remote, local)) if incoming else (
            "%s -> %s" % (local, remote))
        try:
            if not mc.attributeQuery(base, node=dst, exists=True):
                dropped.append(desc)
                continue
            if incoming:
                mc.connectAttr(remote, newlocal, force=True)
            else:
                mc.connectAttr(newlocal, remote, force=True)
        except Exception:
            dropped.append(desc)
    return dropped


def duplicate_inputs(src, dst):
    """DUPLICATE every incoming (upstream-driven) edge on ``src`` onto ``dst``,
    leaving ``src``'s inputs connected (the C++ sibling fans off the same
    upstream). Skips infrastructure plugs. Returns a ``dropped`` list.

    ``src``'s PRIVATE relay (see :func:`_opm_relay`) is excluded: it is not
    upstream authoring, it is ``src``'s own output fed back to itself. ``dst``
    builds its own on creation, and force-duplicating ``src``'s would DISPLACE
    it -- leaving the sibling mirroring ``src``'s matrix instead of computing its
    own, and orphaning the relay it just built."""
    return _transfer_edges(src, dst, incoming=True, skip_remote=_opm_relay(src))


def move_outputs(src, dst):
    """MOVE every outgoing edge on ``src`` onto ``dst`` (downstream now reads the
    C++ result; ``src``'s outputs end up disconnected). Skips infrastructure
    plugs. Returns a ``dropped`` list."""
    return _transfer_edges(src, dst, incoming=False)


def moves_outputs(src):
    """True when a coexist convert of ``src`` MOVES its output edges onto the
    sibling; False when it duplicates the INPUTS only.

    A DAG transform is the inputs-only case. Its consumers are not all edges: its
    DAG CHILDREN follow PARENTAGE, which cannot be duplicated onto a sibling. A
    full convert would hand ``worldMatrix`` to the compiled node while the
    children kept following the interpreted one -- a silently HALF-converted
    scene. So the sibling is built, valued and fed, downstream is left exactly as
    it was, and the caller reports what did not get rewired (see
    :func:`downstream_dependents`) for the user to decide about. This is an
    interactive development step, not a production swap."""
    import maya.cmds as mc

    try:
        return not bool(mc.objectType(src, isAType="transform"))
    except Exception:
        return True


def _same_node(a, b):
    """True when plug/node names ``a`` and ``b`` denote the SAME node (UUID, so
    short vs full DAG paths compare correctly)."""
    import maya.cmds as mc

    def uid(n):
        got = mc.ls(n.split(".")[0], uuid=True) or []
        return got[0] if got else n

    return uid(a) == uid(b)


def _opm_relay(node):
    """``node``'s PRIVATE ``offsetParentMatrix`` relay, or ``None``.

    ``mPyTransform`` auto-builds a stock ``fourByFourMatrix`` that takes its flat
    ``_outLocalFlat`` output and drives its own ``offsetParentMatrix``. That is
    private wiring, not user downstream: it must be excluded from the
    "what will not be rewired" report, and deleted along with the compiled
    sibling -- ``delete(cpp)`` orphans it, so a convert/revert cycle would leak
    one relay each time and leave ``_outLocalFlat`` cross-wired into it.

    Found the SAME way ``ensure_opm_relay`` tests for it (the driver of
    ``offsetParentMatrix``), then CONFIRMED exclusive to ``node``: it must both
    drive and be driven by ``node``, and connect to nothing else. A relay shared
    with the interpreted node, or a plain user-authored ``offsetParentMatrix``
    input (which only drives, never reads back), therefore never qualifies -- so
    nothing the user owns is ever deleted."""
    import maya.cmds as mc

    try:
        plug = node + ".offsetParentMatrix"
        if not mc.objExists(plug):
            return None
        drivers = mc.listConnections(plug, source=True, destination=False) or []
        if not drivers:
            return None
        relay = drivers[0]
        ups = mc.listConnections(relay, source=True, destination=False) or []
        downs = mc.listConnections(relay, source=False, destination=True) or []
        if not ups or not downs:
            return None
        if any(not _same_node(n, node) for n in ups + downs):
            return None
        return relay
    except Exception:
        return None


def downstream_dependents(node):
    """What depends on ``node`` and would NOT be rewired by an inputs-only
    convert. Returns ``(edges, children)``.

    ``edges`` are exactly the outgoing edges :func:`move_outputs` WOULD have
    moved (same predicate, so the warning can never disagree with the behaviour),
    minus the node's own private relay wiring. ``children`` are its DAG children,
    which are not edges at all and are the reason the transform case exists."""
    import maya.cmds as mc

    relay = _opm_relay(node)
    edges = []
    conns = mc.listConnections(node, connections=True, plugs=True,
                               source=False, destination=True) or []
    for i in range(0, len(conns), 2):
        local, remote = conns[i], conns[i + 1]
        if not _is_movable_output(local, remote):
            continue
        if relay is not None and _same_node(remote, relay):
            continue
        edges.append((local, remote))
    return edges, (mc.listRelatives(node, children=True, fullPath=True) or [])


def _ensure_link(py, cpp):
    """Idempotently link ``py`` (interpreted) to ``cpp`` (compiled) via a
    ``py.mpyCompiledLink -> cpp.mpyInterpretedLink`` message connection. Reuses
    existing attrs so a Convert->Revert->Convert cycle never double-``addAttr``s."""
    import maya.cmds as mc

    if not mc.attributeQuery("mpyCompiledLink", node=py, exists=True):
        mc.addAttr(py, longName="mpyCompiledLink", attributeType="message")
    if not mc.attributeQuery("mpyInterpretedLink", node=cpp, exists=True):
        mc.addAttr(cpp, longName="mpyInterpretedLink", attributeType="message")
    src_plug, dst_plug = py + ".mpyCompiledLink", cpp + ".mpyInterpretedLink"
    if not mc.isConnected(src_plug, dst_plug):
        mc.connectAttr(src_plug, dst_plug, force=True)


def _snapshot_lod(py):
    """Locator idle-safety: snapshot ``py.lodVisibility`` into a hidden
    ``mpyPreConvertLodVis`` long attr, then zero ``lodVisibility`` so the idle
    Python locator stops drawing (only the C++ locator draws). Returns ``True``
    when the locator was hidden, ``False`` when ``lodVisibility`` is not settable
    (connected or locked): in that case NO snapshot attr is written (there is
    nothing to restore) so the caller can report that the idle Python locator
    still draws instead of leaving a misleading snapshot behind."""
    import maya.cmds as mc

    plug = py + ".lodVisibility"
    try:
        cur = mc.getAttr(plug)
    except Exception:
        return False
    if not mc.getAttr(plug, settable=True):
        return False
    if not mc.attributeQuery("mpyPreConvertLodVis", node=py, exists=True):
        mc.addAttr(py, longName="mpyPreConvertLodVis", attributeType="long",
                   hidden=True)
    try:
        mc.setAttr(py + ".mpyPreConvertLodVis", int(cur))
        mc.setAttr(plug, 0)
    except Exception:
        if mc.attributeQuery("mpyPreConvertLodVis", node=py, exists=True):
            try:
                mc.deleteAttr(py + ".mpyPreConvertLodVis")
            except Exception:
                pass
        return False
    return True


def _restore_lod(py):
    """Restore ``py.lodVisibility`` from ``mpyPreConvertLodVis`` (if present) and
    remove the snapshot attr. No-op when the attr is absent (DG nodes)."""
    import maya.cmds as mc

    if not mc.attributeQuery("mpyPreConvertLodVis", node=py, exists=True):
        return
    try:
        mc.setAttr(py + ".lodVisibility",
                   int(mc.getAttr(py + ".mpyPreConvertLodVis")))
    except Exception:
        pass
    try:
        mc.deleteAttr(py + ".mpyPreConvertLodVis")
    except Exception:
        pass


def _snapshot_state(py):
    """Idle-safety for EVERY converted node: snapshot ``py.nodeState`` into a
    hidden ``mpyPreConvertNodeState`` attr, then SUSPEND the node -- Has No
    Effect for a deformer (Maya refuses Blocking on a geometryFilter), Blocking
    otherwise (``commands._eval_block_state``).

    Moving the output wiring is not enough. The Evaluation Manager evaluates a
    node whose inputs animate whether or not anything reads its outputs:
    measured on the Combo Correctives demo (1306 verts, 167 targets), the
    converted mPyBlendShape still deformed 8 frames of 8 in Parallel mode --
    the same 142 ms/frame as before the convert -- while DG mode showed 0.
    Playback runs under the EM, so the convert bought nothing until the node
    was suspended.

    Returns ``True`` when suspended, ``False`` when ``nodeState`` is not
    settable (connected / locked): then NO snapshot is written (there is
    nothing to restore) so the caller can report that the idle node still
    evaluates instead of leaving a misleading snapshot behind."""
    import maya.cmds as mc
    from mpynode._base.commands import _eval_block_state

    plug = py + ".nodeState"
    try:
        cur = mc.getAttr(plug)
    except Exception:
        return False
    if not mc.getAttr(plug, settable=True):
        return False
    if not mc.attributeQuery("mpyPreConvertNodeState", node=py, exists=True):
        mc.addAttr(py, longName="mpyPreConvertNodeState", attributeType="long",
                   hidden=True)
    try:
        mc.setAttr(py + ".mpyPreConvertNodeState", int(cur))
        mc.setAttr(plug, _eval_block_state(py))
    except Exception:
        if mc.attributeQuery("mpyPreConvertNodeState", node=py, exists=True):
            try:
                mc.deleteAttr(py + ".mpyPreConvertNodeState")
            except Exception:
                pass
        return False
    return True


def _restore_state(py):
    """Restore ``py.nodeState`` from ``mpyPreConvertNodeState`` (if present) and
    remove the snapshot attr. No-op when the attr is absent: a transform's
    inputs-only convert never suspends, and a convert made before suspension
    existed left the node at whatever state it had."""
    import maya.cmds as mc

    if not mc.attributeQuery("mpyPreConvertNodeState", node=py, exists=True):
        return
    try:
        mc.setAttr(py + ".nodeState",
                   int(mc.getAttr(py + ".mpyPreConvertNodeState")))
    except Exception:
        pass
    try:
        mc.deleteAttr(py + ".mpyPreConvertNodeState")
    except Exception:
        pass


def attach_compiled(src, compiled_type):
    """Coexist-convert ``src`` (interpreted) to a hidden ``compiled_type`` C++
    sibling WITHOUT deleting ``src``. Snapshots static values, DUPLICATES the
    input wiring (both nodes fan off the same upstream), MOVES the output wiring
    onto the C++ node (downstream now reads the compiled result), links the two
    with a message attr, and ``lockNode``s the C++ node against casual deletion.
    A DAG ``src`` gets its sibling under the SAME parent (a co-located gizmo for
    a locator, a sibling in place for a transform). A locator is further handled
    specially: the idle Python locator is hidden via ``lodVisibility``
    (snapshotted for exact revert). The snapshot + hide happen AFTER
    ``copy_values`` so the C++ locator inherits the ORIGINAL (visible)
    ``lodVisibility``, not the zeroed one.

    A DAG TRANSFORM gets an INPUTS-ONLY convert -- the outputs are deliberately
    left driving downstream, because its children follow parentage rather than an
    edge (see :func:`moves_outputs`).

    Every node whose outputs DID move is then SUSPENDED (``nodeState``: Has No
    Effect for a deformer, Blocking otherwise; snapshotted for exact revert),
    because the Evaluation Manager keeps evaluating an idle node whose inputs
    animate -- see :func:`_snapshot_state`. Returns ``(cpp_name, dropped)``."""
    import maya.cmds as mc

    _freeze_live_state(src)
    is_locator = bool(mc.objectType(src, isAType="locator"))
    is_dag = bool(mc.objectType(src, isAType="dagNode"))
    if is_dag:
        parent = (mc.listRelatives(src, parent=True, fullPath=True)
                  or [None])[0]
        cpp = mc.createNode(compiled_type, parent=parent) if parent \
            else mc.createNode(compiled_type)
    else:
        cpp = mc.createNode(compiled_type)
    copy_values(src, cpp)
    copy_multi_values(src, cpp)
    dropped = copy_aliases(src, cpp)
    dropped += duplicate_inputs(src, cpp)
    if moves_outputs(src):
        dropped += move_outputs(src, cpp)
    _ensure_link(src, cpp)
    if is_locator:
        # after copy_values: cpp keeps original lodVisibility
        if not _snapshot_lod(src):
            dropped.append(
                src + ".lodVisibility (not settable -- idle Python locator "
                "still draws; hide it manually)")
    if moves_outputs(src):
        # Disconnected outputs do NOT idle the node under the Evaluation
        # Manager (see _snapshot_state). A transform keeps driving its
        # children through parentage, so its inputs-only convert stays live.
        if not _snapshot_state(src):
            dropped.append(
                src + ".nodeState (not settable -- the idle Python node still "
                "evaluates; set it to Has No Effect / Blocking by hand)")
    try:
        mc.lockNode(cpp, lock=True)
    except Exception:
        pass
    return cpp, dropped


def _freeze_live_state(src):
    """Bake anything a node type follows LIVE into the plugs the copy carries.

    Only mPyBlendShape needs this today. Its interpreted deform reads the
    CONNECTED target meshes directly, so a target sculpted since the last bake
    shows up without ever touching ``targetDeltas``. A compiled node has no such
    path -- it reads the baked tables -- so converting without this would copy
    STALE tables and the sibling would silently snap back to the pre-sculpt
    shape.

    Must run BEFORE ``copy_multi_values``, which is what actually carries the
    tables across.

    Best-effort: a convert must not fail because the freeze could not run. The
    cost of that is the stale-table behaviour, not a broken node."""
    import maya.cmds as mc

    try:
        if mc.nodeType(src) != "mPyBlendShape":
            return
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
        MPyBlendShape(src).resync_targets()
    except Exception:
        pass


def detach_compiled(cpp, py):
    """Coexist-REVERT: unlock ``cpp``, move its output wiring back onto ``py``,
    drop the link attr, and delete ``cpp`` (plus its private relay) -- restoring
    ``py`` to its exact pre-convert state (``py`` kept its inputs throughout).
    Returns ``dropped`` (output edges whose Python-side attr is missing -- schema
    drift -- reported, not silently lost).

    The revert MIRRORS the convert: when ``py`` got an inputs-only convert, the
    outputs are not moved BACK either. ``move_outputs`` here would graft the
    sibling's private relay wiring onto ``py``, which never had it."""
    import maya.cmds as mc

    try:
        mc.lockNode(cpp, lock=False)
    except Exception:
        pass
    # Resolve BEFORE the delete -- afterwards the relay is unreachable (and
    # orphaned, which is exactly the leak this removes).
    relay = _opm_relay(cpp)
    dropped = move_outputs(cpp, py) if moves_outputs(py) else []
    _restore_lod(py)    # restores lodVisibility + removes the snapshot (locators)
    _restore_state(py)  # restores nodeState + removes the snapshot (every convert)
    if mc.attributeQuery("mpyCompiledLink", node=py, exists=True):
        try:
            mc.deleteAttr(py + ".mpyCompiledLink")
        except Exception:
            pass
    mc.delete(cpp)
    if relay is not None and mc.objExists(relay):
        try:
            mc.delete(relay)
        except Exception:
            pass
    return dropped


def swap_node(src, compiled_type):
    """Replace ``src`` with a new ``compiled_type`` node, preserving values,
    multi-array topology, and connections. Returns ``(new_name, dropped)`` where
    ``dropped`` is the list from :func:`rewire`. Reparent-aware for DAG nodes."""
    import maya.cmds as mc

    parent = (mc.listRelatives(src, parent=True, fullPath=True) or [None])[0]
    dst = mc.createNode(compiled_type, parent=parent) if parent \
        else mc.createNode(compiled_type)
    copy_values(src, dst)
    copy_multi_values(src, dst)
    dropped = copy_aliases(src, dst)
    dropped += rewire(src, dst)
    for kid in (mc.listRelatives(src, children=True, fullPath=True) or []):
        try:
            mc.parent(kid, dst)
        except Exception:
            dropped.append("child %s (not reparented)" % kid)
    short = src.split("|")[-1]
    mc.delete(src)
    try:
        dst = mc.rename(dst, short)
    except Exception:
        pass
    return dst, dropped
