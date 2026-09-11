"""Auto_dirty -- user-input auto-dirty propagation (DG-callback edition).

PROBLEM
-------
Maya's standard ``attributeAffects`` only operates on class-level
attribute relationships declared at ``node_initializer`` time. For
attributes added dynamically via ``MPyNode.add_input_attr``,
there is no way to declare ``attributeAffects`` after the fact -- so
Maya does not know the new attr affects any output. When something
upstream changes (e.g. a locator's translate moves), Maya's DG
optimizer **stops dirty propagation at the deformer's matrix input**
because no class-level affects relationship exists. The deformer's
``outputGeometry`` stays "clean", the viewport reads cached data,
and the deformer never re-runs.

SOLUTION
--------
NO scriptJobs (per project policy -- scriptJobs are reserved for UI
lifecycle only). We use Maya DG callbacks exclusively:

 * **On the DESTINATION (deformer) node**: install
 ``MNodeMessage.addAttributeChangedCallback`` filtered to user
 inputs. Catches the case where the user does ``setAttr`` directly
 on a user input (e.g. dragging a falloff slider in the channel
 box).

 * **On each SOURCE node** that is connected to one of our user
 inputs: install ``MNodeMessage.addNodeDirtyPlugCallback``. When
 ANY plug on the source becomes dirty (e.g. locator.translateX
 keyframe / interactive drag), our callback dgdirty's the
 destination and runs a per-type touch to flush the cache. We
 hook the source side because Maya DOES properly propagate dirty
 through class-level affects relationships within the source's
 own tree -- it's only the cross-node hop into our dynamic attr
 that Maya can't trace.

 * **One global ``MDGMessage.addConnectionCallback``** per node type
 detects future connections made/broken to user inputs, and
 installs / tears down the per-source callbacks as needed.

Installation:

 * ``add_input_attr`` (on ``MPyNode``) calls ``refresh_for_node``
 after adding the new attr so it gets coverage immediately.
 * ``install_for_type`` (called from each plug-in's
 ``initializePlugin``) sweeps existing nodes + adds an
 ``MDGMessage.addNodeAddedCallback`` so future nodes get coverage.

All callbacks are tracked via:data:`CALLBACK_MANAGER` so they unload
cleanly with the plug-in.

This module installs ZERO scriptJobs.
"""

from __future__ import annotations

import sys
import threading

import maya.OpenMaya as om
from mpynode._common.io import serialization
from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_SHARED


# Re-entry guard -- dgdirty / touch we issue from inside a callback
# shouldn't re-trigger us in turn.
_in_callback = threading.local()


# ---- Touch functions: per-node-type "force re-eval" callbacks ----


def touch_envelope(node_name: str) -> None:
    """Touch envelope -- works for any MPxGeometryFilter descendant.
    Tiny perturb-and-restore so Maya registers a real value change
    (Maya optimizes away ``setAttr same_value`` in interactive
    contexts).

    ALSO explicitly dgdirty the output multi.
    ``cmds.dgdirty(node)`` alone doesn't reliably mark
    array-element output plugs as dirty in interactive Maya, so
    when a user-setAttr fires this callback the downstream mesh
    shape pull misses the change. The explicit
    ``dgdirty(outputGeometry)`` closes that gap.

    DO NOT call dgeval here. dgeval triggers
    compute, compute reads the user's driverMatrix plug, which
    pulls the source locator and fires the source-side dirty
    callback again. Maya 2026 with EM parallel can dispatch the
    inner callback on a worker thread, where the thread-local
    ``_in_callback`` guard isn't set -- producing unbounded
    recursion (notably triggered by importing a second copy of
    a deformer scene)."""
    try:
        from maya import cmds

        env = cmds.getAttr(node_name + ".envelope")
        cmds.setAttr(node_name + ".envelope", env + 1e-9)
        cmds.setAttr(node_name + ".envelope", env)
        try:
            cmds.dgdirty(node_name + ".outputGeometry")
        except Exception:
            pass
    except Exception:
        pass


def _live_node_name(node_obj: "om.MObject") -> str:
    """Resolve a node's CURRENT name, preferring a UNIQUE DAG path.

    ``MFnDependencyNode.name()`` returns the short node name, which is NOT
    unique across the DAG. Two nodes sharing a short name -- e.g. after the
    shipped Node Duplicate feature clones a DNET rig into a second
    ``dnetLinkAim0`` under a different parent -- make every subsequent
    name-based ``cmds`` query raise "More than one object matches name". In the
    flush path that ambiguity would make :func:`free_translate_channel` fall
    through to its ``translateX`` fallback (the very tension-source channel the
    flush must avoid), reintroducing the DNET P0 on duplicated rigs; and
    ``_dispatch_dirty_now``'s ``nodeType`` / matrix-``dgdirty`` calls would
    silently no-op. A ``partialPathName`` (shortest unique DAG path) keeps
    every downstream ``cmds`` call unambiguous. Non-DAG nodes (deformers,
    geometry) have globally-unique names already, so fall back to the
    dependency name for them.
    """
    try:
        if node_obj.hasFn(om.MFn.kDagNode):
            name = om.MFnDagNode(node_obj).partialPathName()
            if name:
                return name
    except Exception:
        pass
    return om.MFnDependencyNode(node_obj).name()


def free_translate_channel(node_name: str) -> str:
    """Pick a translate channel safe to write for a worldMatrix-cache flush.

    A flush is a real TRS write of a channel to its OWN value. The channel must
    be:

      * **not locked** -- ``setDouble`` on a locked plug is rejected;
      * **not an OUTGOING-connection source** -- this is the load-bearing part.
        An aim mPyTransform's ``translateX`` is wired to the solver's
        ``tension[e]``. Writing ``translateX`` therefore fans the dirty BACK
        into the solver, which re-dirties every sibling knot proxy WHILE the
        ``_in_callback`` re-entry guard is armed -- so those siblings' own flush
        callbacks no-op and their worldMatrix caches stay stale (the DNET
        "half the link aims never re-orient" P0). A channel with no outgoing
        connection flushes the cache without touching the solver;
      * **not INCOMING-driven** -- a connected/animated channel can't be
        written (the connection overrides it) and a re-write is pointless.

    Prefers ``translateX`` (backward-compatible with the common case where it is
    free); falls back to ``translateX`` only if every translate channel is
    connected -- degenerate, and no worse than the previous unconditional
    behaviour.
    """
    try:
        from maya import cmds

        for ch in ("translateX", "translateY", "translateZ"):
            full = node_name + "." + ch
            try:
                if cmds.getAttr(full, lock=True):
                    continue
                if cmds.listConnections(full, source=False, destination=True):
                    continue
                if cmds.listConnections(full, source=True, destination=False):
                    continue
            except Exception:
                continue
            return ch
    except Exception:
        pass
    return "translateX"


def touch_translateX(node_name: str) -> None:
    """Flush an mPyTransform's cached worldMatrix after an interactive edit.

    Maya invalidates a DAG transform's WORLD-matrix cache ONLY on a genuine
    TRS-channel write -- NOT by ``cmds.dgdirty`` (verified: whole node or any
    matrix plug leaves it frozen) and NOT by appending ``worldMatrix`` in
    setDependentsDirty. An mPyTransform authors its local matrix from
    ``asMatrix()`` ignoring TRS, so its cached worldMatrix stays stale when its
    matrix INPUTS relax. We therefore write a FREE translate channel (see
    :func:`free_translate_channel`) to its OWN current value via the raw api2
    ``MPlug`` -- a real TRS write that flushes the cache and propagates the
    fresh local matrix to downstream consumers (DAG children, constraints, line
    gizmos).

    Writing a NON-source channel (not necessarily ``translateX``) is essential:
    an aim transform's ``translateX`` feeds the solver's ``tension``, so writing
    it re-solves the network and -- inside the re-entry guard -- starves every
    sibling aim's flush, leaving half the DNET link aims frozen. A free channel
    (``translateY``/``translateZ`` on such aims) flushes the same cache without
    the solver feedback.

    This is NON-undoable, by design. The previous implementation "touched"
    ``translateX`` with a no-op ``cmds.setAttr`` re-write (tx+1e-9 then tx),
    which pushed spurious UNDOABLE entries onto the undo queue on every
    interactive edit -- so a single knot move left several undo steps and
    Ctrl-Z reverted the invisible flush instead of the user's move.
    ``MPlug.setDouble`` bypasses the command engine and leaves the undo queue
    untouched. (``_dispatch_dirty_now`` dirties the node's MATRIX OUTPUTS before
    calling this for downstream propagation; this write is what actually flushes
    the world cache.)"""
    try:
        import maya.api.OpenMaya as om2

        ch  = free_translate_channel(node_name)
        sel = om2.MSelectionList()
        sel.add(node_name)
        node_obj = sel.getDependNode(0)
        dep      = om2.MFnDependencyNode(node_obj)
        plug     = om2.MPlug(node_obj, dep.attribute(ch))
        plug.setDouble(plug.asDouble())
    except Exception:
        pass


def touch_outMesh(node_name: str) -> None:
    """Dirty outMesh -- mPyMesh."""
    try:
        from maya import cmds

        cmds.dgdirty(node_name + ".outMesh")
    except Exception:
        pass


def touch_outCurve(node_name: str) -> None:
    """Dirty outCurve -- mPyNurbsCurve."""
    try:
        from maya import cmds

        cmds.dgdirty(node_name + ".outCurve")
    except Exception:
        pass


def touch_outSurface(node_name: str) -> None:
    """Dirty outSurface -- mPyNurbsSurface."""
    try:
        from maya import cmds

        cmds.dgdirty(node_name + ".outSurface")
    except Exception:
        pass


def touch_dgdirty_only(node_name: str) -> None:
    """No extra action."""
    pass


# Per-type touch dispatch -- looked up by ``cmds.nodeType(node_name)``.
# mPyTransform is intentionally ABSENT: under the flush-free re-arch it installs
# no auto-dirty coverage at all (the plugin dropped it from its install_for_type
# loop). A user-input change dirties the input plug -> setDependentsDirty appends
# _outLocalFlat -> the fourByFourMatrix relay recomputes offsetParentMatrix ->
# worldMatrix, all by native DG propagation. ``touch_translateX`` (a spurious TRS
# write) was the flush hack this architecture removes.
TOUCH_BY_TYPE: dict = {
    "mPyDeformer":     touch_envelope,
    "mPySkinCluster":  touch_envelope,
    "mPyBlendShape":   touch_envelope,
    "mPyMesh":         touch_outMesh,
    "mPyNurbsCurve":   touch_outCurve,
    "mPyNurbsSurface": touch_outSurface,
}


# ---- Bookkeeping ----


# (dest_node_uuid, src_node_uuid) -> source-node callback id. Indexed so we can
# uninstall when a connection is broken.
_source_callbacks: dict = {}

# dest_node_uuids that already have an addAttributeChangedCallback.
_dest_callbacks: set = set()

# node-type name -> owner of that type's one global addConnectionCallback. The
# callback is plugin-owned and removed on EVERY unload, so its latch must be
# cleared on every unload too (not just last-plugin-out) -- otherwise a reload
# with the sibling plugin still loaded skips re-registering it. See forget_owner.
_connection_callbacks_installed: dict = {}


# Clear the per-MObject-hash dedup sets on scene change. `_install_dest_callback`
# dedups on ``MObjectHandle.hashCode()``; after a ``file -new`` Maya may reuse the
# same memory slot for a freshly-loaded mPy node, so the same hash comes back and
# the dedup short-circuits the new install -- leaving that node with no
# AttributeChanged callback and user-setAttr edits not dirtying its output.
_scene_change_clear_installed = False


def _install_scene_change_clear() -> None:
    """Subscribe ``kBeforeNew`` / ``kBeforeOpen`` /
    ``kAfterOpen`` to wipe the per-MObject-hash dedup caches so
    stale entries from a previous scene don't block fresh
    installs."""
    global _scene_change_clear_installed
    if _scene_change_clear_installed:
        return
    _scene_change_clear_installed = True

    def _on_scene_change(_client):
        _dest_callbacks.clear()
        _source_callbacks.clear()
        try:
            from mpynode._common.plugs import dirty_affects

            dirty_affects.invalidate_all()
        except Exception:
            pass

    for event_name in ("kBeforeNew", "kBeforeOpen"):
        evt = getattr(om.MSceneMessage, event_name, None)
        if evt is None:
            continue
        try:
            cb_id = om.MSceneMessage.addCallback(evt, _on_scene_change)
            CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_SHARED
            )
        except Exception:
            pass


def _node_uuid(node_name: str) -> str:
    """UUID-based stable key for a node (survives renames)."""
    try:
        from maya import cmds

        uuids = cmds.ls(node_name, uuid=True)
        if uuids:
            return uuids[0]
    except Exception:
        pass
    return node_name


def _dispatch_dirty(dest_node_name: str) -> None:
    """Schedule the shared 'dirty + touch' action on the main-thread idle.

    CRITICAL: this MUST NOT touch the DG synchronously. It is invoked
    from inside ``MNodeMessage`` dirty-plug callbacks -- i.e. DURING DG
    dirty propagation -- which under the Maya 2026 Evaluation Manager
    can fire on a WORKER THREAD (e.g. when an animCurve drives a plug
    that feeds a user input, on currentTime change). Calling
    ``cmds.dgdirty`` / ``setAttr`` in that context crashes Maya outright
    (SIGSEGV in TdgDirtyAction during setDependentsDirty).

    ``maya.utils.executeDeferred`` is thread-safe and runs the work on
    the main thread once the DG is safe to touch, which both prevents
    the crash and the unbounded-recursion the old thread-local guard
    couldn't catch on worker threads."""
    # Safe synchronous path: the DESTINATION-side (setAttr / attributeChanged)
    # and connection callbacks fire OUTSIDE DG dirty propagation, so touching the
    # DG here is legal, stays immediate, and works in batch with no idle loop.
    _dispatch_dirty_now(dest_node_name)


def _dispatch_dirty_deferred(dest_node_name: str) -> None:
    """SOURCE-side (NodeDirtyPlug) path. This callback fires DURING DG
    dirty propagation (e.g. an animCurve dirties a plug that feeds a user
    input on currentTime change). Touching the DG synchronously here --
    even on the main thread -- re-enters ``TdgDirtyAction`` and crashes
    Maya (SIGSEGV) under the 2026 Evaluation Manager. Defer the work to
    the main-thread idle, where the DG is safe to touch. Under EM the
    dependent node is normally already scheduled for evaluation, so this
    is a safety net rather than the primary update mechanism."""
    try:
        from maya.utils import executeDeferred

        executeDeferred(_dispatch_dirty_now, dest_node_name)
    except Exception:
        pass


def _dispatch_dirty_now(dest_node_name: str) -> None:
    """Do the actual dirty + touch. Only ever called on the main thread
    (via the deferred scheduler in :func:`_dispatch_dirty`)."""
    if getattr(_in_callback, "active", False):
        return
    _in_callback.active = True
    try:
        try:
            from maya import cmds as _cmds_nt

            ntype = _cmds_nt.nodeType(dest_node_name)
        except Exception:
            ntype = None
        # A SUSPENDED destination -- nodeState Has No Effect / Blocking, which
        # Convert to C++ sets on the idle Python node and a user may set by
        # hand -- does not evaluate, so there is nothing to flush. Dirtying it
        # anyway was the converted Combo Correctives node's remaining per-frame
        # cost: 42 dispatches a frame in Parallel, each re-dirtying the whole
        # node (~8,900 setDependentsDirty calls a frame) for zero deforms. The
        # source callbacks stay installed, so un-suspending resumes at once.
        try:
            if _cmds_nt.getAttr(dest_node_name + ".nodeState"):
                return
        except Exception:
            pass
        try:
            from maya import cmds

            if ntype == "mPyTransform":
                # MATRIX OUTPUTS only -- NOT the whole node. ``dgdirty(node)``
                # also dirties ``translateX``, which on an aim mPyTransform feeds
                # the solver's ``tension[e]``; that fans the dirty back into the
                # solver and re-dirties every sibling knot proxy WHILE the
                # re-entry guard is armed, so their flush callbacks no-op and
                # their worldMatrix caches stay stale (the DNET "half the link
                # aims never re-orient" P0). Matrix outputs are all a downstream
                # consumer needs; ``touch_translateX`` flushes the world cache.
                for _mp in (
                    ".matrix",
                    ".worldMatrix",
                    ".inverseMatrix",
                    ".worldInverseMatrix",
                ):
                    try:
                        cmds.dgdirty(dest_node_name + _mp)
                    except Exception:
                        pass
            else:
                cmds.dgdirty(dest_node_name)
        except Exception:
            pass
        touch = TOUCH_BY_TYPE.get(ntype, touch_dgdirty_only)
        try:
            touch(dest_node_name)
        except Exception:
            pass
    finally:
        _in_callback.active = False


# ---- Destination-side callback (catches direct setAttr to user inputs) ----


def _install_dest_callback(node_obj: om.MObject) -> None:
    """Install MNodeMessage.addAttributeChangedCallback on a destination
    node. Filters to user inputs. Fires on:

      * ``kAttributeSet``    -- direct setAttr on the user input.
      * ``kOtherPlugSet``    -- the connected source pushed a new value.
      * ``kIncomingDirectionChanged`` -- connection made/broken.
    """
    uuid = None
    try:
        uuid = om.MObjectHandle(node_obj).hashCode()
    except Exception:
        pass
    if uuid is not None and uuid in _dest_callbacks:
        return

    relevant_mask = om.MNodeMessage.kAttributeSet | om.MNodeMessage.kIncomingDirection
    if hasattr(om.MNodeMessage, "kOtherPlugSet"):
        relevant_mask |= om.MNodeMessage.kOtherPlugSet

    def _cb(msg, plug, other_plug, _client):
        if not (msg & relevant_mask):
            return
        try:
            attr_name = om.MFnAttribute(plug.attribute()).name()
        except Exception:
            return
        try:
            fn        = om.MFnDependencyNode(node_obj)
            node_name = _live_node_name(node_obj)
            ia_str    = fn.findPlug("_inputAttrs", True).asString()
            if not ia_str:
                return
            user_inputs = set(serialization.decode_attr_map(ia_str).keys())
        except Exception:
            return
        if attr_name not in user_inputs:
            return
        _dispatch_dirty(node_name)

    try:
        cb_id = om.MNodeMessage.addAttributeChangedCallback(node_obj, _cb)
        CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback)
        if uuid is not None:
            _dest_callbacks.add(uuid)
    except Exception as exc:
        sys.stderr.write(f"[auto_dirty] dest callback install failed: {exc}\n")


# ---- Source-side callback (catches upstream-driven changes) ----


def _install_source_callback(source_node_obj: om.MObject, dest_node_obj: om.MObject) -> None:
    """Install MNodeMessage.addNodeDirtyPlugCallback on a SOURCE node.
    When any plug on the source becomes dirty, dispatch dirty to the
    destination.

    This is the critical piece for the "drag the locator and the
    deformer follows" case -- Maya's DG correctly propagates dirty
    within the locator's tree (translate -> matrix -> worldMatrix)
    because those are all class-level attributeAffects. We just need
    to bridge the gap from the source to our destination.

    ``dest_node_obj`` is now an **MObject**, NOT a
    name string. Previously the closure captured the dest name at
    install time -- which is wrong during import (Maya wires the
    connection BEFORE applying the namespace/suffix rename, so the
    closure pointed at a stale name). MObjects survive renames,
    so resolving the name at fire time always produces the live
    destination.
    """
    try:
        src_uuid = om.MObjectHandle(source_node_obj).hashCode()
    except Exception:
        src_uuid = None

    try:
        dest_uuid = om.MObjectHandle(dest_node_obj).hashCode()
    except Exception:
        dest_uuid = None

    key = (dest_uuid, src_uuid)
    if dest_uuid is not None and key in _source_callbacks:
        return  # already installed

    # Taken while the destination is known to exist. Its ``isValid()`` is the
    # only safe question to ask about the destination at fire time: the source
    # keeps this callback after the destination is deleted (nothing removes
    # it), and with undo off the node is gone for real -- the first source
    # dirty after `delete` then took mayapy down in MFnDependencyNode::name
    # (access violation) resolving the stale MObject's name.
    dest_handle = om.MObjectHandle(dest_node_obj)

    def _cb(_src_node, _plug, _client):
        try:
            if not dest_handle.isValid():
                return
        except Exception:
            return
        # Resolve dest NAME at fire time, as a UNIQUE DAG path: an ambiguous
        # short name (duplicated rig) would route the flush to the harmful
        # ``translateX`` fallback. See :func:`_live_node_name`.
        try:
            current_name = _live_node_name(dest_node_obj)
        except Exception:
            return
        if not current_name:
            return
        # Source-side dirty fires DURING DG propagation, forcing a choice:
        #   * synchronous -> INTERACTIVE (deformer follows the driver live mid
        #     drag), but re-enters TdgDirtyAction and SIGSEGVs on the scenario
        #     that crashed bug2.ma: a KEYFRAMED driver evaluated during SCENE
        #     LOAD, and under the 2026 EM on worker threads.
        #   * executeDeferred -> crash-safe, but runs on the main-thread idle,
        #     which doesn't tick mid drag -- mesh updates only on mouse RELEASE.
        # So gate on the actual crash context: sync only on the main thread and
        # outside file I/O; defer otherwise, which is where the crash lives.
        on_main    = threading.current_thread() is threading.main_thread()
        in_file_io = False
        try:
            in_file_io = om.MFileIO.isReadingFile() or om.MFileIO.isOpeningFile()
        except Exception:
            in_file_io = False
        if on_main and not in_file_io:
            _dispatch_dirty_now(current_name)
        else:
            _dispatch_dirty_deferred(current_name)

    try:
        cb_id                  = om.MNodeMessage.addNodeDirtyPlugCallback(source_node_obj, _cb)
        token                  = CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback)
        _source_callbacks[key] = (cb_id, token)
    except Exception as exc:
        sys.stderr.write(f"[auto_dirty] source callback install failed: {exc}\n")


def _walk_user_input_sources(dest_node_name: str):
    """Yield (source_node_name, source_plug_name) for every connection
    feeding a user input on dest_node_name."""
    try:
        from maya import cmds

        if not cmds.objExists(dest_node_name):
            return
        ia_str = cmds.getAttr(dest_node_name + "._inputAttrs") or ""
        if not ia_str:
            return
        try:
            user_inputs = list(serialization.decode_attr_map(ia_str).keys())
        except Exception:
            return
        for attr_name in user_inputs:
            plug = dest_node_name + "." + attr_name
            try:
                srcs = (
                    cmds.listConnections(
                        plug, source=True, destination=False, plugs=True
                    )
                    or []
                )
            except Exception:
                srcs = []
            for src in srcs:
                src_node = src.split(".")[0]
                yield (src_node, src)
    except Exception:
        return


# ---- Top-level entrypoint ----


def refresh_for_node(node_name: str) -> None:
    """Install/refresh user-input handlers for ``node_name``.

    Installs:
      * Destination-side AttributeChanged callback (idempotent).
      * Source-side NodeDirtyPlug callback for each currently-connected
        source feeding a user input (idempotent).

    Call this from:
      * ``MPyNode.add_input_attr`` (after adding the attr).
      * The plug-in's per-type ``MDGMessage.addNodeAddedCallback``
        (so file-loaded and newly-created nodes get coverage).

    The plug-in's per-type ``MDGMessage.addConnectionCallback`` handles
    later connections (those made after refresh_for_node has run).
    """
    try:
        from maya import cmds

        if not cmds.objExists(node_name):
            return
        try:
            sel = om.MSelectionList()
            sel.add(node_name)
            dest_obj = om.MObject()
            sel.getDependNode(0, dest_obj)
            _install_dest_callback(dest_obj)
        except Exception:
            pass
        # Source-side callbacks for existing connections. Re-resolve the dest
        # MObject so the closure binds to something rename-stable (import
        # applies its namespace/suffix AFTER wiring the connection).
        try:
            sel_dest = om.MSelectionList()
            sel_dest.add(node_name)
            dest_obj_for_src = om.MObject()
            sel_dest.getDependNode(0, dest_obj_for_src)
        except Exception:
            dest_obj_for_src = None
        if dest_obj_for_src is not None:
            for src_node, _src_plug in _walk_user_input_sources(node_name):
                try:
                    sel2 = om.MSelectionList()
                    sel2.add(src_node)
                    src_obj = om.MObject()
                    sel2.getDependNode(0, src_obj)
                    _install_source_callback(src_obj, dest_obj_for_src)
                except Exception:
                    pass
    except Exception:
        pass


# ---- Type-level installation (called from each plug-in's initializePlugin) ----


def install_for_type(type_name: str, touch=None, owner: str = OWNER_SHARED) -> int:
    """Install user-input auto-dirty coverage for ``type_name``.

    Sweeps existing nodes + installs:
      * ``MDGMessage.addNodeAddedCallback`` so future nodes get
        ``refresh_for_node`` called on creation.
      * ``MDGMessage.addConnectionCallback`` so future connections to
        user inputs trigger a fresh ``refresh_for_node`` (to install
        the new source-side callback).

    ``touch`` is ignored (kept for backward compat); the per-type
    touch is now looked up via:data:`TOUCH_BY_TYPE`.

    ``owner`` tags the per-type structural callbacks (node-added /
    connection / scene-open-sweep) so the OWNING plug-in's unload removes
    exactly them -- not the other plug-in's, and not the shared
    scene-change-clear (which stays ``shared``). Each plug-in passes its
    own ``PLUGIN_NAME``. This keeps a single-plugin unload from killing the
    co-loaded plugin's coverage AND prevents a duplicate node-added
    callback when the same plug-in is unloaded then reloaded.
    """

    def _do_install():
        # Once, so stale MObject-hash dedup entries don't block fresh installs.
        _install_scene_change_clear()
        from maya import cmds

        # If this type's plug-in isn't registered yet, cmds.ls(type=...) and
        # addNodeAddedCallback(type) print a spurious "Unknown object type"
        # warning. Skip them; the scene-open sweep below still catches a
        # late-loading type.
        try:
            _registered = type_name in (cmds.allNodeTypes() or [])
        except Exception:
            _registered = True  # permissive if the query itself fails

        # Cover existing nodes.
        if _registered:
            try:
                for n in cmds.ls(type=type_name) or []:
                    try:
                        refresh_for_node(n)
                    except Exception:
                        pass
            except Exception:
                pass

        # Cover future nodes via addNodeAddedCallback.
        def _on_node_added(node_obj, _client):
            try:
                fn = om.MFnDependencyNode(node_obj)
                refresh_for_node(fn.name())
            except Exception:
                pass

        if _registered:
            try:
                cb_id = om.MDGMessage.addNodeAddedCallback(
                    _on_node_added, type_name
                )
                CALLBACK_MANAGER.register(
                    cb_id, om.MMessage.removeCallback, owner
                )
            except Exception as exc:
                sys.stderr.write(
                    f"[auto_dirty] addNodeAddedCallback failed for "
                    f"{type_name!r}: {exc}; falling back to scene-open sweep.\n"
                )
                _install_scene_open_sweep(type_name, owner)
        # ALWAYS, even when addNodeAddedCallback succeeded: that callback is
        # supposed to fire for file-loaded nodes but in practice (Maya 2026,
        # interactive) it races the file load and misses nodes created before
        # our deferred install finishes. The sweep is idempotent, so cheap.
        _install_scene_open_sweep(type_name, owner)

        # Cover future connections via addConnectionCallback (global). It uses
        # the src_plug argument directly -- DO NOT use listConnections here, the
        # connection may not be visible in the DG yet when the callback fires.
        if type_name in _connection_callbacks_installed:
            return
        _connection_callbacks_installed[type_name] = owner

        def _on_connection(src_plug, dest_plug, made, _client):
            if not made:
                return
            try:
                dest_node_obj  = dest_plug.node()
                fn             = om.MFnDependencyNode(dest_node_obj)
                dest_node_name = fn.name()
                from maya import cmds

                if cmds.nodeType(dest_node_name)!= type_name:
                    return
                # Only user inputs.
                try:
                    attr_name = om.MFnAttribute(dest_plug.attribute()).name()
                except Exception:
                    return
                try:
                    ia_str = fn.findPlug("_inputAttrs", True).asString()
                    user_inputs = (
                        set(serialization.decode_attr_map(ia_str).keys())
                        if ia_str
                        else set()
                    )
                except Exception:
                    user_inputs = set()
                if attr_name not in user_inputs:
                    return
                # Pass the dest as an MObject so the closure resolves the live
                # name at fire time, not the stale import-time name.
                src_node_obj = src_plug.node()
                _install_source_callback(src_node_obj, dest_node_obj)
            except Exception:
                pass

        try:
            cb_id2 = om.MDGMessage.addConnectionCallback(_on_connection)
            CALLBACK_MANAGER.register(cb_id2, om.MMessage.removeCallback, owner)
        except Exception as exc:
            sys.stderr.write(f"[auto_dirty] addConnectionCallback failed: {exc}\n")

    try:
        from maya import cmds

        cmds.evalDeferred(_do_install, lowestPriority=True)
        return 0
    except Exception:
        _do_install()
        return 0


def _install_scene_open_sweep(type_name: str, owner: str = OWNER_SHARED) -> int:
    """Fallback: after any scene-open event, sweep all existing nodes
    of the given type and refresh their callbacks. ``owner`` tags the
    callback for the owning plug-in's unload sweep."""

    def _on_scene_open(_client):
        try:
            from maya import cmds

            for n in cmds.ls(type=type_name) or []:
                try:
                    refresh_for_node(n)
                except Exception:
                    pass
        except Exception:
            pass

    try:
        cb_id = om.MSceneMessage.addCallback(
            om.MSceneMessage.kAfterOpen, _on_scene_open
        )
        return CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, owner)
    except Exception as exc:
        sys.stderr.write(
            f"[auto_dirty] scene-open fallback failed for {type_name!r}: {exc}\n"
        )
        return -1


def forget_owner(owner) -> None:
    """Clear the connection-callback install latch entries owned by ``owner``.

    Called from a plug-in's ``uninitializePlugin`` on EVERY unload (right after
    ``CALLBACK_MANAGER.remove_for_owner(PLUGIN_NAME)``). The per-type
    ``addConnectionCallback`` is plugin-owned, so it is deregistered on every
    single-plugin unload -- its latch must therefore be cleared on every unload
    too, or a reload while the sibling plug-in stays loaded would hit the stale
    latch in ``install_for_type`` and skip re-registering the connection
    callback (new connections to that plugin's nodes would then never get a
    source-side dirty callback). ``reset_install_state`` (last-plugin-out) clears
    the whole latch; this clears just one owner's slice for the non-final case.
    """
    for t in [t for t, o in _connection_callbacks_installed.items() if o == owner]:
        del _connection_callbacks_installed[t]


def reset_install_state() -> None:
    """Reset the install guards + per-node dedup caches so a later plugin
    reload re-installs cleanly.

    Called by the last-plugin-out teardown AFTER the shared/owned callbacks
    have been deregistered. Without this:
      * ``_scene_change_clear_installed`` stays latched -> the dedup-clear
        callback is never re-subscribed on reload;
      * ``_connection_callbacks_installed`` keeps stale type names ->
        ``install_for_type`` skips re-installing the connection callback;
      * ``_dest_callbacks`` / ``_source_callbacks`` keep stale MObject-hash
        keys -> ``refresh_for_node`` short-circuits and never re-installs.
    """
    global _scene_change_clear_installed, _native_discovery_sweep_installed
    _scene_change_clear_installed     = False
    _native_discovery_sweep_installed = False
    _connection_callbacks_installed.clear()
    _dest_callbacks.clear()
    _source_callbacks.clear()


# ---- Native (compiled) geo-node coverage ----
#
# Compiled C++ plug-ins have NO ``_inputAttrs`` plug, so the interpreted
# discovery above installs nothing for them. They also hit the underlying Maya
# quirk in its harshest form: a cross-node dirty does NOT propagate when only
# the SUB-DATA of a connected geometry changes. Moving UVs leaves every vertex
# position untouched, so ``worldMesh -> inMesh`` never dirties and the compiled
# node's ``outMesh`` stays stale until the next time change. A topology edit
# DOES propagate -- which is why delete-face works but UV-move does not
# (_tests/test_native_geo_uv_dirty.py is the standing regression for it).
#
# The fix mirrors the interpreted SOURCE-side bridge but discovers the inputs to
# watch by DATA TYPE (geometry-typed incoming connections) rather than by
# ``_inputAttrs`` name. Everything downstream is the same hardened machinery.


_GEO_DATA_TYPES = None

# node-added-once + scene-open discovery latch (cleared by reset_install_state).
_native_discovery_sweep_installed = False

# Fixed geometry OUTPUT plug names codegen always emits (native/compiler/
# emit_geo.py), paired with the flush that dirties them.
_NATIVE_GEO_OUTPUTS = (
    ("outMesh", touch_outMesh),
    ("outCurve", touch_outCurve),
    ("outSurface", touch_outSurface),
)

# Built-in interpreted geo types -- already covered by install_for_type; the
# native discovery sweep must skip them so it doesn't double-install.
_BUILTIN_MPY_GEO_TYPES = frozenset(
    ("mPyMesh", "mPyNurbsCurve", "mPyNurbsSurface"))

# mpy_type (from a build manifest) -> output flush.
_TOUCH_BY_MPY_TYPE = {
    "mPyMesh":         touch_outMesh,
    "mPyNurbsCurve":   touch_outCurve,
    "mPyNurbsSurface": touch_outSurface,
}


def _geo_data_types():
    """Cache the ``MFnData`` geometry type constants this Maya exposes
    (mesh / nurbsCurve / nurbsSurface)."""
    global _GEO_DATA_TYPES
    if _GEO_DATA_TYPES is None:
        vals = []
        for nm in ("kMesh", "kNurbsCurve", "kNurbsSurface"):
            v = getattr(om.MFnData, nm, None)
            if v is not None:
                vals.append(v)
        _GEO_DATA_TYPES = tuple(vals)
    return _GEO_DATA_TYPES


def _attr_is_geo(attr_obj) -> bool:
    """True if a plug's attribute MObject is a typed GEOMETRY attribute
    (mesh / nurbsCurve / nurbsSurface). Needs no plug data, so it is safe to
    call the instant a connection is made."""
    try:
        if attr_obj.hasFn(om.MFn.kTypedAttribute):
            return om.MFnTypedAttribute(attr_obj).attrType() in _geo_data_types()
    except Exception:
        pass
    return False


def _plug_is_geo(plug_name: str) -> bool:
    """Name-based variant of :func:`_attr_is_geo` for the connection walk."""
    try:
        sel = om.MSelectionList()
        sel.add(plug_name)
        plug = om.MPlug()
        sel.getPlug(0, plug)
        return _attr_is_geo(plug.attribute())
    except Exception:
        return False


def _walk_native_geo_sources(dest_node_name: str):
    """Yield (source_node, source_plug) for every GEOMETRY-typed incoming
    connection on a compiled node -- the analogue of
    :func:`_walk_user_input_sources` that keys off data TYPE, not the
    ``_inputAttrs`` plug (which compiled nodes lack)."""
    try:
        from maya import cmds

        if not cmds.objExists(dest_node_name):
            return
        conns = (
            cmds.listConnections(
                dest_node_name, source=True, destination=False,
                connections=True, plugs=True,
            )
            or []
        )
        # listConnections(connections=True) -> [dest, src, dest, src, ...].
        for i in range(0, len(conns) - 1, 2):
            dest_plug, src_plug = conns[i], conns[i + 1]
            if not _plug_is_geo(dest_plug):
                continue
            yield (src_plug.split(".")[0], src_plug)
    except Exception:
        return


def _refresh_native_node(node_name: str) -> None:
    """Install source-side dirty callbacks for every geometry-typed incoming
    connection on ``node_name`` (a compiled geo node). Idempotent (the source
    callback dedups on the (dest, src) MObject-hash pair)."""
    try:
        sel_dest = om.MSelectionList()
        sel_dest.add(node_name)
        dest_obj = om.MObject()
        sel_dest.getDependNode(0, dest_obj)
    except Exception:
        return
    for src_node, _src_plug in _walk_native_geo_sources(node_name):
        try:
            sel2 = om.MSelectionList()
            sel2.add(src_node)
            src_obj = om.MObject()
            sel2.getDependNode(0, src_obj)
            _install_source_callback(src_obj, dest_obj)
        except Exception:
            pass


def install_for_native_type(type_name, touch, owner: str = OWNER_SHARED,
                            defer: bool = False) -> int:
    """Install geometry auto-dirty coverage for a COMPILED node type.

    Like :func:`install_for_type` but for compiled C++ nodes that lack the
    ``_inputAttrs`` plug: the inputs to watch are discovered by DATA TYPE
    (geometry-typed incoming connections). ``touch`` is the per-type output
    flush (e.g. :func:`touch_outMesh`) and is registered in
    :data:`TOUCH_BY_TYPE` so the shared dispatch flushes the right output.

    ``defer`` runs the structural install on the deferred idle (matching
    :func:`install_for_type`) when True; callers that invoke this AFTER the
    plug-in + scene are ready (scene-open sweep, post-compile load, tests) pass
    the default False for immediate, deterministic coverage -- also required in
    batch/mayapy, where the idle queue may never tick.

    Idempotent: re-invoking for the same type re-refreshes existing instances
    (cheap, dedup-guarded) but installs the structural node-added / connection /
    latch callbacks only once (gated by ``_connection_callbacks_installed``)."""
    # Register the touch synchronously so _dispatch_dirty_now flushes the right
    # output even if the structural install below is deferred.
    if touch is not None:
        TOUCH_BY_TYPE[type_name] = touch

    def _do_install():
        _install_scene_change_clear()
        from maya import cmds

        try:
            _registered = type_name in (cmds.allNodeTypes() or [])
        except Exception:
            _registered = True

        # Always refresh existing instances (idempotent).
        if _registered:
            try:
                for n in cmds.ls(type=type_name) or []:
                    try:
                        _refresh_native_node(n)
                    except Exception:
                        pass
            except Exception:
                pass

        # Structural callbacks -- install once per type.
        if type_name in _connection_callbacks_installed:
            return
        _connection_callbacks_installed[type_name] = owner

        def _on_node_added(node_obj, _client):
            try:
                fn = om.MFnDependencyNode(node_obj)
                _refresh_native_node(fn.name())
            except Exception:
                pass

        if _registered:
            try:
                cb_id = om.MDGMessage.addNodeAddedCallback(_on_node_added, type_name)
                CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, owner)
            except Exception as exc:
                sys.stderr.write(
                    f"[auto_dirty] native addNodeAddedCallback failed for "
                    f"{type_name!r}: {exc}\n"
                )

        def _on_connection(src_plug, dest_plug, made, _client):
            if not made:
                return
            try:
                dest_node_obj  = dest_plug.node()
                fn             = om.MFnDependencyNode(dest_node_obj)
                dest_node_name = fn.name()
                from maya import cmds

                if cmds.nodeType(dest_node_name) != type_name:
                    return
                if not _attr_is_geo(dest_plug.attribute()):
                    return
                src_node_obj = src_plug.node()
                _install_source_callback(src_node_obj, dest_node_obj)
            except Exception:
                pass

        try:
            cb_id2 = om.MDGMessage.addConnectionCallback(_on_connection)
            CALLBACK_MANAGER.register(cb_id2, om.MMessage.removeCallback, owner)
        except Exception as exc:
            sys.stderr.write(
                f"[auto_dirty] native addConnectionCallback failed: {exc}\n"
            )

    if defer:
        try:
            from maya import cmds

            cmds.evalDeferred(_do_install, lowestPriority=True)
            return 0
        except Exception:
            _do_install()
            return 0
    _do_install()
    return 0


def install_native_geo_coverage(owner: str = OWNER_SHARED) -> int:
    """Discover COMPILED geo node types present in the current scene and install
    native auto-dirty coverage for each. A compiled geo node is identified by a
    PLUGIN-provided node type that carries a fixed geometry OUTPUT plug
    (``outMesh`` / ``outCurve`` / ``outSurface`` -- the names codegen always
    emits). Stock Maya ``mesh`` shapes also expose ``outMesh`` but are NOT
    plugin-provided, so the plugin filter excludes them; the built-in
    interpreted mPy* geo types are excluded too. Returns the count of types
    covered."""
    from maya import cmds

    plugin_types = set()
    try:
        for p in cmds.pluginInfo(query=True, listPlugins=True) or []:
            try:
                for t in cmds.pluginInfo(p, query=True, dependNode=True) or []:
                    plugin_types.add(t)
            except Exception:
                pass
    except Exception:
        pass

    covered = 0
    for t in plugin_types:
        if t in _BUILTIN_MPY_GEO_TYPES:
            continue
        try:
            insts = cmds.ls(type=t) or []
        except Exception:
            continue
        if not insts:
            continue
        inst = insts[0]
        for out_attr, touch in _NATIVE_GEO_OUTPUTS:
            try:
                exists = cmds.objExists(inst + "." + out_attr)
            except Exception:
                exists = False
            if exists:
                install_for_native_type(t, touch=touch, owner=owner, defer=False)
                covered += 1
                break
    return covered


def install_native_geo_coverage_from_manifest(manifest_path: str,
                                              owner: str = OWNER_SHARED) -> int:
    """Install native geo coverage for the compiled node types recorded in a
    build ``manifest.json`` (written by native/toolchain/compile_controller.py).
    Used by the compile->load flow, where the plug-in is loaded but no instances
    exist yet (so instance-based discovery can't see it) -- this arms coverage
    before the user creates the first node. Returns the count of types covered.
    """
    import json
    import os

    covered = 0
    try:
        if not manifest_path or not os.path.isfile(manifest_path):
            return 0
        with open(manifest_path) as fh:
            data = json.load(fh)
        for node in data.get("nodes", []) or []:
            type_name = node.get("type_name")
            spec      = node.get("spec") or {}
            mpy_type  = spec.get("mpy_type") or node.get("mpy_type")
            touch     = _TOUCH_BY_MPY_TYPE.get(mpy_type)
            if type_name and touch is not None:
                install_for_native_type(type_name, touch=touch, owner=owner,
                                        defer=False)
                covered += 1
    except Exception:
        pass
    return covered


def install_native_scene_sweep(owner: str = OWNER_SHARED) -> int:
    """Register a one-time scene-open/import/reference sweep that re-discovers
    compiled geo types (via :func:`install_native_geo_coverage`) so a saved
    scene's compiled mesh/curve/surface nodes get the source-side UV-dirty
    bridge on load. Idempotent (latched by ``_native_discovery_sweep_installed``,
    cleared on last-plugin-out). Returns the count of scene events hooked."""
    global _native_discovery_sweep_installed
    if _native_discovery_sweep_installed:
        return 0

    def _on_open(_client):
        try:
            install_native_geo_coverage(owner=owner)
        except Exception:
            pass

    hooked = 0
    for evt_name in ("kAfterOpen", "kAfterImport", "kAfterReference"):
        evt = getattr(om.MSceneMessage, evt_name, None)
        if evt is None:
            continue
        try:
            cb_id = om.MSceneMessage.addCallback(evt, _on_open)
            CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, owner)
            hooked += 1
        except Exception:
            pass
    _native_discovery_sweep_installed = True
    return hooked
