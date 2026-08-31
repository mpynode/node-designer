"""Interpreted adapters for mPySkinCluster's blessed skinning methods.

Bound onto ``self`` by the SelfProxy blessed-method tier. Every operand is an
EXPLICIT argument -- the method reads nothing off ``self`` -- and it delegates to
the canonical Maya-free math in ``skin_blend``, the SAME functions the native
compiler's blessed ``Transpile`` lowering transpiles, so interpreted == compiled
by construction. The caller (the Compute expression) passes the node's own plugs
explicitly, e.g. ``self.linear_blend(rest, self.weightList, self.matrix,
self.bindPreMatrix)``, so the plug dependencies are visible at the call site
rather than hidden inside the method.
"""
from __future__ import annotations

import numpy as np

from mpynode._common.methods import skin_blend


def linear_blend(self, rest, weights, joint, bind):
    """self.linear_blend(rest, weights, joint, bind) -> (N, 3) LBS points."""
    return skin_blend.linear_blend(
        np.asarray(rest),
        np.asarray(weights),
        np.asarray(joint),
        np.asarray(bind),
    )


def dual_quaternion(self, rest, weights, joint, bind):
    """self.dual_quaternion(rest, weights, joint, bind) -> (N, 3) DQS points."""
    return skin_blend.dual_quaternion(
        np.asarray(rest),
        np.asarray(weights),
        np.asarray(joint),
        np.asarray(bind),
    )


def twist_swing(self, rest, weights, joint, bind, twist_axis=0):
    """self.twist_swing(rest, weights, joint, bind, twist_axis) -> (N, 3) points:
    DQS twist about the bone-local axis (0=X/1=Y/2=Z, default X) + LBS swing (bend)."""
    return skin_blend.twist_swing(
        np.asarray(rest),
        np.asarray(weights),
        np.asarray(joint),
        np.asarray(bind),
        int(twist_axis),
    )


def twist_swing_dual(self, rest, twist_weights, swing_weights, joint, bind,
                     twist_axis=0):
    """self.twist_swing_dual(rest, twist_weights, swing_weights, joint, bind,
    twist_axis) -> (N, 3) points: DQS twist using ``twist_weights`` about the
    bone-local axis (0=X/1=Y/2=Z, default X) + LBS swing using ``swing_weights``
    (two independent weight sets on one node)."""
    return skin_blend.twist_swing_dual(
        np.asarray(rest),
        np.asarray(twist_weights),
        np.asarray(swing_weights),
        np.asarray(joint),
        np.asarray(bind),
        int(twist_axis),
    )


def _marshal_main_thread(fn):
    """Run ``fn`` on the MAIN thread: synchronously in batch/mayapy (no idle
    loop, single-threaded DG -> observable), DEFERRED in interactive Maya or on
    any worker thread (never a worker-thread DG mutation, which SIGSEGVs). Shared
    by ``update_weights`` and ``sync_paint`` -- both stage a plug for the paint UI
    and MUST obey the same EM-safe marshalling rule."""
    import threading
    import maya.OpenMaya as om1
    on_main = threading.current_thread() is threading.main_thread()
    try:
        interactive = om1.MGlobal.mayaState() == om1.MGlobal.kInteractive
    except Exception:
        interactive = False
    if on_main and not interactive:
        fn()
    else:
        from maya.utils import executeDeferred
        executeDeferred(fn)


def _dense_weight_list(mc, name):
    """Read this skinCluster's ``weightList`` into a dense ``(N, J)`` array (0 for
    absent influence columns). J is the influence (``matrix``) count so the shape
    matches the deform operands even when a vertex omits a zero-weight column."""
    import numpy as np
    verts = mc.getAttr(name + ".weightList", size=True) or 0
    infl = len(mc.getAttr(name + ".matrix", multiIndices=True) or [])
    W = np.zeros((verts, infl), dtype=np.float64)
    for v in range(verts):
        idx = mc.getAttr("%s.weightList[%d].weights" % (name, v),
                         multiIndices=True) or []
        for j in idx:
            jj = int(j)
            if jj < infl:
                W[v, jj] = float(mc.getAttr(
                    "%s.weightList[%d].weights[%d]" % (name, v, jj)))
    return W


def _bulk_set_weights(mc, name, W):
    """Write the whole ``(nv, jj)`` block with ONE ``MFnSkinCluster.setWeights``.

    True if it was written, False if this node/geometry cannot be served safely
    -- the caller then falls back to the per-element loop, so no path changes
    behaviour. setWeights is only taken when it provably lands the SAME values in
    the SAME columns as that loop:

      * ONE deformed mesh, and ``nv`` covers every vertex -- setWeights needs an
        MDagPath plus a component MObject, and a weightList row index is only
        unambiguous with a single geometry;
      * ``matrix[]`` dense ``0..jj-1`` -- setWeights indexes influences
        PHYSICALLY while this codebase's weight columns are LOGICAL matrix
        indices. ``_wire_joints`` builds them dense so the two coincide, but an
        influence detached by hand leaves a gap and they diverge;
      * ``normalize=False`` -- the setAttr loop does no normalization, and the
        default is True;
      * the LAST influence column carries a nonzero somewhere. setWeights does
        not store zero weights, where the setAttr loop created an element for
        every column. A pruned MIDDLE column is harmless (both weightList
        readers zero-fill gaps and size J from the MAX painted influence index),
        but a pruned TRAILING column lowers that max and shrinks J -- which
        breaks the skin_blend matmul against ``matrix`` (sized from
        ``matrix[]``'s own max logical index). Measured: writing a block whose
        columns 1..3 are all zero leaves ``weightList[0].weights`` with the
        single index ``[0]`` instead of ``[0,1,2,3]``.
    """
    try:
        import maya.OpenMaya as om1
        import maya.OpenMayaAnim as oma1
    except Exception:
        return False

    nv, jj = int(W.shape[0]), int(W.shape[1])
    if nv <= 0 or jj <= 0:
        return False
    # An all-zero LAST column would be pruned away and shrink J (see above).
    if not W[:, jj - 1].any():
        return False
    try:
        geo = mc.deformer(name, q=True, geometry=True) or []
        if len(geo) != 1 or mc.nodeType(geo[0]) != "mesh":
            return False
        if int(mc.polyEvaluate(geo[0], vertex=True) or -1) != nv:
            return False
        midx = list(mc.getAttr(name + ".matrix", multiIndices=True) or [])
        if midx != list(range(jj)):
            return False
    except Exception:
        return False

    try:
        sel = om1.MSelectionList()
        sel.add(name)
        sc_obj = om1.MObject()
        sel.getDependNode(0, sc_obj)
        fn_skin = oma1.MFnSkinCluster(sc_obj)

        sel2 = om1.MSelectionList()
        sel2.add(geo[0])
        dag = om1.MDagPath()
        sel2.getDagPath(0, dag)

        comp_fn = om1.MFnSingleIndexedComponent()
        comp = comp_fn.create(om1.MFn.kMeshVertComponent)
        comp_fn.setCompleteData(nv)

        inf_ids = om1.MIntArray()
        for j in range(jj):
            inf_ids.append(j)
        w_arr = om1.MDoubleArray()
        for x in W.ravel():
            w_arr.append(float(x))

        # normalize=False: preserve the setAttr loop's exact values.
        fn_skin.setWeights(dag, comp, inf_ids, w_arr, False)
    except Exception:
        return False
    return True


def _write_weight_list(mc, name, W):
    """Stage a dense ``(nv, jj)`` block into ``weightList[v].weights[j]``.

    Shared by ``sync_paint``'s ``_load`` and ``update_weights``' ``_apply`` --
    both write the SAME plug from the same dense layout. One
    ``mc.setAttr`` per weight is the fallback: a 20k-vertex, 8-influence skin is
    160,000 commands, so the bulk path above is tried first."""
    if _bulk_set_weights(mc, name, W):
        return
    nv, jj = int(W.shape[0]), int(W.shape[1])
    for v in range(nv):
        for j in range(jj):
            mc.setAttr("%s.weightList[%d].weights[%d]" % (name, v, j),
                       float(W[v, j]))


def sync_paint(self, mode):
    """self.sync_paint(mode) -> None. Interactive paint machinery for the
    two-weight-set twist/swing skin (a ``NativeSideEffect`` blessed method).

    The node carries TWO dense weight sets as declared array input plugs --
    ``twistWeights`` (DQS twist pass) and ``swingWeights`` (LBS swing/bend pass),
    each a flattened ``N*J`` ``double`` multi. ``weightList`` is only the Paint
    Skin Weights scratchpad. ``skinMode`` selects the interaction:

      * 0 Paint LBS (Swing) -> the ACTIVE set is ``swingWeights``
      * 1 Paint DQS (Twist) -> the ACTIVE set is ``twistWeights``
      * 2 Live Result       -> not painting; this method does nothing

    On ENTERING a paint mode (a ``_paintMode`` session latch detects the switch)
    the active set is loaded into ``weightList`` so the Paint tool shows it. On a
    settled same-mode eval the painted ``weightList`` is BANKED back into the
    active set plug so edits persist (survive save/reload AND feed the compiled
    node, which reads the plugs). The bank is GUARDED -- it writes the plug only
    when ``weightList`` actually differs -- so a steady (unpainted) eval performs
    no plug write and cannot spin a dirty/recompute loop.

    Compiled: there is no paint session, so a bare ``self.sync_paint(mode)``
    statement lowers to NOTHING (see ``api_methods.NativeSideEffect``). The
    compiled deform reads the two plugs directly, so omitting the scratchpad
    staging is faithful. All plug writes obey the EM-safe main-thread marshalling
    in ``_marshal_main_thread``.
    """
    import numpy as np
    import maya.OpenMaya as om1

    try:
        if om1.MFileIO.isReadingFile():
            return
    except Exception:
        pass

    mode = int(mode)
    prev = getattr(self, "_paintMode", None)
    switched = prev != mode
    self._paintMode = mode
    if mode not in (0, 1):
        return                                  # Live Result: nothing to stage

    # the active set plug for this paint mode (0 -> swing, 1 -> twist).
    active_name = "swingWeights" if mode == 0 else "twistWeights"
    active_flat = getattr(self, active_name, None)

    mobj = self._psp_mobject
    handle = om1.MObjectHandle(mobj)

    if switched:
        # entering the paint mode: load the active set plug INTO weightList so
        # Paint Skin Weights edits the right buffer.
        if active_flat is None:
            return
        flat = np.asarray(active_flat, dtype=np.float64).ravel()

        def _load():
            from maya import cmds as mc
            if not handle.isValid() or not handle.isAlive():
                return
            name = om1.MFnDependencyNode(mobj).name()
            infl = len(mc.getAttr(name + ".matrix", multiIndices=True) or [])
            verts = mc.getAttr(name + ".weightList", size=True) or 0
            if not infl or not verts or flat.size < verts * infl:
                return
            W = flat[:verts * infl].reshape(verts, infl)
            _write_weight_list(mc, name, W)
        _marshal_main_thread(_load)
        return

    # settled same-mode eval: bank painted weightList back into the active plug
    # (guarded: only write when it actually changed, so no steady-state loop).
    prev_flat = (np.asarray(active_flat, dtype=np.float64).ravel()
                 if active_flat is not None else None)

    def _bank():
        from maya import cmds as mc
        if not handle.isValid() or not handle.isAlive():
            return
        name = om1.MFnDependencyNode(mobj).name()
        W = _dense_weight_list(mc, name)          # (N, J) dense from weightList
        flat = W.ravel()
        if prev_flat is not None and prev_flat.size == flat.size \
                and np.allclose(prev_flat, flat, atol=1e-9):
            return                                # unchanged -> no plug write
        for i in range(flat.size):
            mc.setAttr("%s.%s[%d]" % (name, active_name, i), float(flat[i]))
    _marshal_main_thread(_bank)


def update_weights(self, weights):
    """self.update_weights(weights) -> None.

    GENERIC side-effecting blessed method: write a dense ``(N, J)`` weight array
    into this skinCluster's ``weightList`` plug, so Maya's Paint Skin Weights /
    Component Editor shows + edits it. Nothing is hardcoded -- pass ANY buffer
    (``self.swingWeights``, ``self.buffers[k]``, a freshly computed array); the
    method neither knows nor cares which set it is or how many sets exist.

    Typically called from Compute to load a persistent weight buffer into the
    paint scratchpad (e.g. when a paint-mode enum changes). The deform reads the
    persistent buffers directly, so writing ``weightList`` never affects the
    current deform -- it is purely the interactive paint scratchpad.

    Thread-safety: the plug mutation (``_apply``) runs ONLY on the MAIN thread
    via ``_marshal_main_thread`` -- synchronous in batch/mayapy (observable),
    deferred in interactive Maya or on any worker thread (no worker-thread DG
    mutation, which SIGSEGVs in TdgDirtyAction). ``self`` is the compute
    SelfProxy: the node MObject is ``self._psp_mobject``.
    """
    import maya.OpenMaya as om1

    # Never touch the DG while a scene is being read (mirror the compute guard).
    try:
        if om1.MFileIO.isReadingFile():
            return
    except Exception:
        pass

    if weights is None:
        return
    W = np.asarray(weights)
    if W.ndim != 2:
        return

    # Snapshot the array + MObject so a later mutation cannot race a pending
    # deferred write. The node NAME is resolved INSIDE _apply so the
    # (thread-unsafe) api1 MFnDependencyNode lookup never runs on a worker
    # thread -- _apply only ever executes on the main thread.
    buf = W.copy()
    mobj = self._psp_mobject
    # Handle to detect deletion: a deferred write can fire long after it is
    # scheduled (interactive path), by which point the node -- or the whole
    # scene (File > New) -- may be gone. MFnDependencyNode on a freed MObject
    # is undefined behaviour, so _apply must verify liveness first.
    handle = om1.MObjectHandle(mobj)

    def _apply():
        from maya import cmds as mc
        if not handle.isValid() or not handle.isAlive():
            return
        name = om1.MFnDependencyNode(mobj).name()
        nv, jj = buf.shape
        # Clamp to the node's REAL dimensions so a mis-sized buffer (the generic
        # contract accepts ANY array) never spawns phantom weightList influence
        # columns / vertex rows -- those would show garbage in the Paint tool and
        # a later np.asarray(self.weightList) read-back would reshape to a wrong J
        # that breaks the skin_blend matmul. Extra rows/cols are simply dropped.
        try:
            infl = len(mc.getAttr(name + ".matrix", multiIndices=True) or [])
            verts = mc.getAttr(name + ".weightList", size=True)
        except Exception:
            infl, verts = 0, 0
        if infl:
            jj = min(jj, infl)
        if verts:
            nv = min(nv, verts)
        # Clamped view -- the write must honour nv/jj, not buf's raw shape.
        _write_weight_list(mc, name, buf[:nv, :jj])

    # Marshal the write to the main thread (deferred in interactive Maya / on any
    # worker thread; synchronous only for a batch main-thread call).
    _marshal_main_thread(_apply)
