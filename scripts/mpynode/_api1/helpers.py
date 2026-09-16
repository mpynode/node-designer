"""Mpynode._api1.helpers \u2014 API 1.0 helpers for the API 1 plugin.

Mirror of ``_api2/helpers.py`` but using ``maya.OpenMaya`` (API 1.0).
Used by mPyObjectSet, mPyIkSolver, mPyField, mPyEmitter.

API 1 differences from API 2:
  * Modules are ``maya.OpenMaya`` / ``maya.OpenMayaMPx`` /
    ``maya.OpenMayaAnim``
  * Attribute creation: ``attr_fn = MFnNumericAttribute(); plug =
    attr_fn.create(...)`` returns an MObject (works the same as API 2)
  * Flag setters use methods: ``attr_fn.setStorable(True)`` instead
    of ``attr_fn.storable = True``
  * MPxNode subclasses go in ``maya.OpenMayaMPx``
"""

from __future__ import annotations

import json
import sys

import maya.OpenMaya as om
import maya.OpenMayaMPx as ommpx  # noqa: F401  (re-exported by callers)
import numpy as np


def make_internal_string_attr(
    long_name:  str,
    short_name: str,
    default:    str  = "",
    storable:   bool = True,
):
    """Build an internal hidden string attribute (API 1.0). Returns MObject.

    ``storable=False`` keeps the attribute out of
    the.ma. Used for the profile + watch snapshot data plugs.
    """
    str_data    = om.MFnStringData()
    default_obj = str_data.create(default)
    fn          = om.MFnTypedAttribute()
    obj         = fn.create(long_name, short_name, om.MFnData.kString, default_obj)
    fn.setConnectable(False)
    fn.setReadable(False)
    fn.setWritable(True)
    fn.setStorable(bool(storable))
    fn.setInternal(True)
    fn.setKeyable(False)
    fn.setHidden(True)
    return obj


def make_expression_attr():
    """Connectable + keyable internal string attr for the user expression."""
    str_data    = om.MFnStringData()
    default_obj = str_data.create("None")
    fn          = om.MFnTypedAttribute()
    obj         = fn.create("_computeSource", "_computeSource", om.MFnData.kString, default_obj)
    fn.setConnectable(True)
    fn.setReadable(True)
    fn.setWritable(True)
    fn.setStorable(True)
    fn.setInternal(True)
    fn.setKeyable(True)
    fn.setHidden(True)
    return obj


def make_bool_attr(
    long_name:  str,
    short_name: str,
    default:    bool = False,
    storable:   bool = True,
):
    """Hidden framework-toggle bool attribute.

    Used for the ``debug_mode`` + profile / deep_profile / watch
    toggles. These are framework instrumentation switches the Node
    Designer's Profile + Watch tabs flip via ``cmds.setAttr`` --
    they must NOT appear in the Attribute Editor or Channel Box,
    where they could be accidentally keyed or look like part of the
    user-authored attribute surface. ``cmds.setAttr`` / ``getAttr``
    still work on hidden attrs, so the UI hookups are unaffected.

    ``storable=False`` keeps the attribute value out of the .ma so
    it always reverts to ``default`` on file open (used for the
    profile / watch toggles -- avoids ever shipping a scene with the
    profiler accidentally left on).
    """
    fn  = om.MFnNumericAttribute()
    obj = fn.create(long_name, short_name, om.MFnNumericData.kBoolean, default)
    fn.setConnectable(False)
    fn.setStorable(bool(storable))
    fn.setKeyable(False)
    # Hide from Attribute Editor + Channel Box. The framework UI
    # reaches these via cmds.setAttr/getAttr which ignore visibility.
    fn.setHidden(True)
    fn.setChannelBox(False)
    return obj


def build_internal_attrs(cls):
    """Same shape as ``_api2.helpers.build_internal_attrs`` but uses
    API 1.0. Returns a dict of {convenience_name: MObject}.

    also adds the profile + watch plugs (3 toggles +
    2 internal data strings) so every API 1 node type gets the same
    instrumentation surface as API 2 nodes.
    """
    plugs = {
        "_computeSource": make_expression_attr(),
        "inputs":         make_internal_string_attr("_inputAttrs", "_inputAttrs"),
        "outputs":        make_internal_string_attr("_outputAttrs", "_outputAttrs"),
        "stored_vars_list": make_internal_string_attr(
            "_storedVarNames", "_storedVarNames"
        ),
        "stored_vars_data": make_internal_string_attr(
            "_storedVarsData", "_storedVarsData"
        ),
        "debug_mode": make_bool_attr("debug_mode", "dbgm"),
        # profile + watch toggles (visible in channel box). storable=False so
        # they are always OFF on file open.
        "profile_enabled": make_bool_attr("profile_enabled", "prfen", storable=False),
        "deep_profile_enabled": make_bool_attr(
            "deep_profile_enabled", "dprfen", storable=False
        ),
        "watch_enabled": make_bool_attr("watch_enabled", "wtcen", storable=False),
        # snapshot data plugs.
        # storable=False (transient).
        "profile_snapshot_data": make_internal_string_attr(
            "_profileSnapshotData", "_profileSnapshotData", storable=False
        ),
        "watch_vars_data": make_internal_string_attr(
            "_watchVarsData", "_watchVarsData", storable=False
        ),
    }
    for plug in plugs.values():
        cls.addAttribute(plug)
    return plugs


def ensure_expr_code(node_mpx, expr_attr: str = "_computeSource"):
    """Reconcile ``node_mpx._expr_str`` / ``._expr_code`` with the live
    ``_computeSource`` plug, returning the compiled code object (API 1.0).

    Mirror of ``_api2.helpers.ensure_expr_code``. Every mpynode node
    compiles its expression in ``setInternalValue`` and caches it on the
    instance, but Maya does NOT route through ``setInternalValue`` when it
    DUPLICATES a node -- the plug value is copied directly. So a duplicated
    deformer / skin / blend carries the source text yet keeps the fresh
    instance's empty ``_expr_code`` and silently no-ops (the same class of
    bug the api2 locator/gizmo hit). Calling this at the top of the
    compute / deform path makes duplication (and any out-of-band plug edit)
    robust. Cheap: recompiles only when the source string actually changed.
    """
    try:
        fn = om.MFnDependencyNode(node_mpx.thisMObject())
    except Exception:
        return getattr(node_mpx, "_expr_code", None)
    try:
        cur = fn.findPlug(expr_attr, True).asString() or ""
    except Exception:
        return getattr(node_mpx, "_expr_code", None)
    if cur != getattr(node_mpx, "_expr_str", None):
        from mpynode._common.compute.expression import (
            compile_expression,
            safe_compile_expression,
        )

        node_mpx._expr_str = cur
        code = safe_compile_expression(
            cur, node_name=fn.name(), filename="<mpynode-expression>"
        )
        node_mpx._expr_code = code if code is not None else compile_expression("")
    return node_mpx._expr_code


# ===========================================================================
# IK solver bridge
# ===========================================================================


def _walk_joint_chain(start_joint: str, effector: str) -> list[str]:
    """Walk the joint chain from ``start_joint`` down through joint
    children, picking the joint child that leads toward ``effector``.

    Returns a list of joint names in order from base to tip.

    FIX (carried forward from old branch): Don't break early
    when a SIBLING of the next joint is the effector. The effector
    itself is NOT a joint and is NOT in the chain; including it (or
    stopping when we see it as a sibling) drops the last joint of
    3+ joint chains.
    """
    from maya import cmds

    chain = [start_joint]
    cur   = start_joint
    seen  = {cur}

    # Safety cap to prevent infinite loops on bad scene state.
    for _ in range(100):
        children = cmds.listRelatives(cur, children=True, type="joint") or []
        # Filter out joints we've already visited (cycle protection).
        candidates = [c for c in children if c not in seen]
        if not candidates:
            break
        # Take the first joint child not yet seen.
        nxt = candidates[0]
        chain.append(nxt)
        seen.add(nxt)
        cur = nxt

    return chain


def _np4(flat):
    """cmds.getAttr matrix payload (flat 16 or nested) -> (4, 4) numpy."""
    return np.asarray(flat, dtype=np.float64).reshape(4, 4)


def _root_parent_world(root_name):
    """True world matrix of the chain root's DAG parent (identity if the root is
    under the world). Unlike ``root.parentInverseMatrix``, this EXCLUDES the
    root's own ``offsetParentMatrix`` -- a node's ``.parentMatrix`` folds in its
    own offset, so seeding an offset-free bind chain from ``parentInverseMatrix``
    would pick up the previous solve's offset and drift. The DAG parent is above
    the chain (not IK-driven), so its world is stable across solves.
    """
    from maya import cmds

    try:
        parents = cmds.listRelatives(root_name, parent=True, fullPath=True)
    except Exception:
        parents = None
    if parents:
        try:
            return _np4(cmds.getAttr(parents[0] + ".worldMatrix[0]"))
        except Exception:
            pass
    return np.eye(4, dtype=np.float64)


def _gate_mix_world(w_base, w_target, gate_r, gate_t, gate_s):
    """Row-vector (Maya) 4x4 mix: take the rotation / translate / scale of
    ``w_target`` where the matching gate is True, else keep it from ``w_base``.

    Rotation and scale are split by the upper-3x3 row norms (per-axis scale =
    row length; rotation = normalized rows). This assumes negligible shear,
    which holds for joint chains. Shear, if any, follows the rotation source.
    """
    def _decomp(mat):
        m     = np.asarray(mat, dtype=np.float64).reshape(4, 4)
        rows  = m[:3, :3].copy()
        scale = np.linalg.norm(rows, axis=1)
        safe  = np.where(scale < 1e-12, 1.0, scale)
        rot   = rows / safe[:, None]
        return rot, scale, m[3, :3].copy()

    rot_b, scale_b, trans_b = _decomp(w_base)
    rot_t, scale_t, trans_t = _decomp(w_target)
    rot         = rot_t if gate_r else rot_b
    scale       = scale_t if gate_s else scale_b
    trans       = trans_t if gate_t else trans_b
    out         = np.eye(4, dtype=np.float64)
    out[:3, :3] = rot * scale[:, None]
    out[3, :3]  = trans
    return out


# Hidden plug persisting the per-joint BIND offset: the joint's
# ``offsetParentMatrix`` captured on the FIRST solve, before the solver ever
# writes it -- the "neutral" that unset joints are restored to and ungated
# channels are mixed from. JSON: 16-float rows aligned to the walked chain.
_BIND_OFFSETS_ATTR = "_jointBindOffsets"


def _load_bind_offsets(node_name, n):
    """Return the persisted per-joint bind offsets as a list of (4, 4) numpy,
    or ``None`` if unset / stale (length != ``n`` / unreadable)."""
    from maya import cmds

    try:
        s = cmds.getAttr(node_name + "." + _BIND_OFFSETS_ATTR)
    except Exception:
        return None
    if not s:
        return None
    try:
        data = json.loads(s)
    except Exception:
        return None
    if not isinstance(data, list) or len(data) != n:
        return None
    try:
        return [np.asarray(m, dtype=np.float64).reshape(4, 4) for m in data]
    except Exception:
        return None


def _save_bind_offsets(node_name, offsets):
    """Persist per-joint bind offsets (list of (4, 4) numpy) as JSON."""
    from maya import cmds

    try:
        payload = json.dumps([o.flatten().tolist() for o in offsets])
        cmds.setAttr(node_name + "." + _BIND_OFFSETS_ATTR, payload, type="string")
    except Exception:
        pass


def _capture_bind_offsets(node_name, joint_names):
    """Return per-joint bind offsets, capturing + persisting them from the
    joints' CURRENT ``offsetParentMatrix`` the first time (or after a re-bind).

    MUST be called BEFORE any writeback this solve: on the first solve the
    joints are still at rest, so the current offset IS the neutral. It is then
    locked + persisted (so it is stable across solves and survives save/reload);
    a re-bind clears the plug so the next solve re-captures the current pose as
    the new neutral ('set current as rest')."""
    from maya import cmds

    stored = _load_bind_offsets(node_name, len(joint_names))
    if stored is not None:
        return stored
    offsets = []
    for name in joint_names:
        try:
            offsets.append(_np4(cmds.getAttr(name + ".offsetParentMatrix")))
        except Exception:
            offsets.append(np.eye(4, dtype=np.float64))
    _save_bind_offsets(node_name, offsets)
    return offsets


def rebind_ik_solver(node_name):
    """Clear a solver's persisted bind offsets so the NEXT solve re-captures the
    joints' current offsets as the new neutral ('set current pose as rest').
    Works on interpreted (string plug) and compiled (matrixArray plug) solvers.
    Returns True if the plug was cleared."""
    from maya import cmds

    attr = node_name + "." + _BIND_OFFSETS_ATTR
    if not cmds.objExists(attr):
        return False
    try:
        plug_type = cmds.getAttr(attr, type=True)
    except Exception:
        plug_type = "string"
    try:
        if plug_type == "matrixArray":
            cmds.setAttr(attr, 0, type="matrixArray")
        else:
            cmds.setAttr(attr, "", type="string")
        return True
    except Exception:
        return False


def _normalize_matrix_list(val, n):
    """Coerce a harvested matrix output into a per-joint list of length ``n``
    whose entries are matrix-like (numpy / MatrixView / list / MMatrix) or
    ``None``. Accepts a list/tuple (padded / truncated to ``n``) or an
    ``(n, 4, 4)`` numpy stack (rebind). Anything else -> all ``None``."""
    if val is None:
        return [None] * n
    if isinstance(val, (list, tuple)):
        return [val[i] if i < len(val) else None for i in range(n)]
    try:
        arr = np.asarray(val, dtype=np.float64)
        if arr.ndim == 3 and arr.shape[1:] == (4, 4):
            return [arr[i] if i < arr.shape[0] else None for i in range(n)]
    except Exception:
        pass
    return [None] * n


def _normalize_gate(val, n, default):
    """Coerce a gate output into a per-joint list of bools of length ``n``. A
    scalar bool broadcasts to the whole chain; a sequence is taken per joint
    with missing entries falling back to ``default`` (forgiving on ragged
    arrays)."""
    if val is None:
        return [default] * n
    if isinstance(val, (bool, int, float, np.bool_, np.integer, np.floating)):
        return [bool(val)] * n
    try:
        seq = list(val)
    except Exception:
        return [bool(val)] * n
    return [bool(seq[i]) if i < len(seq) else default for i in range(n)]


def _apply_joint_solve(joints, local_mats, world_mats,
                       gates_r, gates_t, gates_s, bind_offsets):
    """Apply the solve to the chain via ``offsetParentMatrix``, walking
    root -> tip, dispatching per joint: WORLD matrix > LOCAL matrix >
    restore-bind. Returns the number of joints written.

    The offset sits between the joint's own local and its parent
    (``world == local @ offsetParentMatrix @ parentWorld``), so the joint's own
    T/R/S channels AND ``jointOrient`` are always left untouched -- the solver
    owns ONLY ``offsetParentMatrix``; animator FK stacks on top.

    * WORLD (``world_mats[i]``): desired ABSOLUTE frame ``W``. Gate-mix ungated
      channels from the joint's rest world (``local @ bindOffset @ parentWorld``)
      then ``offset = inv(local) @ Wmixed @ inv(parentWorld)``.
    * LOCAL (``local_mats[i]``): desired PARENT-RELATIVE frame ``L``. Gate-mix
      against the rest parent-relative (``local @ bindOffset``) then
      ``offset = inv(local) @ Lmixed`` (no parentWorld term -- it cancels).
    * NEITHER: restore ``bindOffset`` (the joint returns to rest; the write is
      idempotent so a joint driven then released snaps back cleanly).

    Parent world is THREADED (each child uses the world we just computed for its
    parent) rather than read back via ``parentInverseMatrix``: mid-solve the DAG
    has not propagated our fresh offsets, so a read-back would use the parent's
    PRE-update world. Gates are per-joint (see ``_normalize_gate``)."""
    from maya import cmds

    n = len(joints)
    if n <= 0:
        return 0

    def _set(name, offset):
        try:
            cmds.setAttr(name + ".offsetParentMatrix",
                         *offset.flatten().tolist(), type="matrix")
            return True
        except Exception:
            return False

    parent_world = _root_parent_world(joints[0]["name"])
    written      = 0
    warned       = False
    for i in range(n):
        name = joints[i]["name"]
        try:
            local = _np4(cmds.getAttr(name + ".matrix"))
        except Exception:
            local = np.eye(4, dtype=np.float64)
        bind_off = bind_offsets[i] if i < len(bind_offsets) else np.eye(4)
        gr       = gates_r[i] if i < len(gates_r) else True
        gt       = gates_t[i] if i < len(gates_t) else False
        gs       = gates_s[i] if i < len(gates_s) else False
        w        = world_mats[i] if i < len(world_mats) else None
        l        = local_mats[i] if i < len(local_mats) else None

        if w is not None:
            if l is not None and not warned:
                warned = True
                sys.stderr.write(
                    "[mPyIkSolver] joint %r has both a local and a world "
                    "matrix set; using world.\n" % name)
            try:
                W = np.asarray(w, dtype=np.float64).reshape(4, 4)
            except Exception:
                W = None
            if W is None:
                _set(name, bind_off)
                parent_world = local @ bind_off @ parent_world
                continue
            rest_world = local @ bind_off @ parent_world
            w_mixed    = _gate_mix_world(rest_world, W, gr, gt, gs)
            try:
                offset = (np.linalg.inv(local) @ w_mixed
                          @ np.linalg.inv(parent_world))
            except np.linalg.LinAlgError:
                offset, w_mixed = bind_off, rest_world
            if _set(name, offset):
                written += 1
            parent_world = w_mixed
        elif l is not None:
            try:
                L = np.asarray(l, dtype=np.float64).reshape(4, 4)
            except Exception:
                L = None
            if L is None:
                _set(name, bind_off)
                parent_world = local @ bind_off @ parent_world
                continue
            rest_pr = local @ bind_off
            l_mixed = _gate_mix_world(rest_pr, L, gr, gt, gs)
            try:
                offset = np.linalg.inv(local) @ l_mixed
            except np.linalg.LinAlgError:
                offset, l_mixed = bind_off, rest_pr
            if _set(name, offset):
                written += 1
            parent_world = l_mixed @ parent_world
        else:
            _set(name, bind_off)
            parent_world = local @ bind_off @ parent_world
    return written


def compute_ik_doSolve(node_self, log_event_name: str = "<mpyiksolver-solve>"):
    """Bridge MPxIkSolverNode::doSolve to the user expression.

    Walks the active handle group, extracts the joint chain + end
    effector via API 1.0 MFnIkHandle, builds the per-joint dict the
    user expression mutates, executes the expression, then writes the
    resulting joint rotations back via cmds.xform.
    """
    try:
        import maya.OpenMayaAnim as oma
        from maya import cmds
    except Exception:
        return

    try:
        hg = node_self.handleGroup()
    except Exception:
        return
    try:
        n_handles = hg.handleCount()
    except Exception:
        return
    if n_handles <= 0:
        return

    try:
        handle_obj = hg.handle(0)
        fn_handle  = oma.MFnIkHandle(handle_obj)
    except Exception:
        return

    try:
        sj_path = om.MDagPath()
        fn_handle.getStartJoint(sj_path)
        ee_path = om.MDagPath()
        fn_handle.getEffector(ee_path)
        start_joint_name = sj_path.partialPathName()
        effector_name    = ee_path.partialPathName()
    except Exception:
        return

    joint_names = _walk_joint_chain(start_joint_name, effector_name)
    if not joint_names:
        return

    # Solver node name (for the persisted bind-offset plug + snapshot).
    try:
        node_name = om.MFnDependencyNode(node_self.thisMObject()).name()
    except Exception:
        node_name = ""

    from mpynode._common.plugs.promoted_types import MatrixView

    # Per-joint BIND offset: captured (root->tip) on the first solve from the
    # joints' current offsetParentMatrix, then locked + persisted. This is the
    # neutral the solver restores unset joints to, and the rest ungated channels
    # are mixed from. Captured HERE, before any writeback this solve.
    bind_offsets = _capture_bind_offsets(node_name, joint_names)

    # REST world per joint: thread the joints' local matrices AND bind offsets
    # from the chain root's true DAG parent (row-vector Maya:
    # world = local @ offsetParentMatrix @ parentWorld). A STABLE reference pose
    # -- invariant across solves because the bind offsets are locked -- that the
    # matrix solve reads for each joint's rest position + orientation. Since the
    # writeback drives offsetParentMatrix, reading the live (freshly-solved)
    # world instead would drift by the previous offset and never converge.
    _pw = _root_parent_world(joint_names[0])

    joints = []
    for i, name in enumerate(joint_names):
        try:
            local_rot = cmds.xform(name, q=True, ws=False, ro=True) or [0.0, 0.0, 0.0]
        except Exception:
            local_rot = [0.0, 0.0, 0.0]
        try:
            local_mat = _np4(cmds.getAttr(name + ".matrix"))
        except Exception:
            local_mat = np.eye(4, dtype=np.float64)
        bind_off  = bind_offsets[i] if i < len(bind_offsets) else np.eye(4)
        world_mat = local_mat @ bind_off @ _pw
        _pw       = world_mat
        joints.append(
            {
                "name":           name,
                "world_position": world_mat[3, :3].copy(),
                "rotation":       np.array(local_rot, dtype=np.float64),
                # local (parent-relative, offset-free) matrix -- the base to
                # build a self.local_matrices (LOCAL) result from.
                "matrix": MatrixView(local_mat),
                # REST world matrix (4x4, row-vector Maya; includes the bind
                # offset). The base to build a self.world_matrices (WORLD)
                # result from; jointOrient-agnostic + stable across solves.
                "world_matrix": MatrixView(world_mat),
            }
        )

    # end_effector is the IK HANDLE's world position (the user's "puppet
    # string"), NOT the effector's, which is the chain's slave tip.
    handle_name_for_target = ""
    try:
        handle_name_for_target = om.MFnDependencyNode(handle_obj).name()
    except Exception:
        pass
    end_effector = [0.0, 0.0, 0.0]
    if handle_name_for_target:
        try:
            end_effector = cmds.xform(
                handle_name_for_target, q=True, ws=True, t=True
            ) or [0.0, 0.0, 0.0]
        except Exception:
            pass
    if end_effector == [0.0, 0.0, 0.0]:
        try:
            end_effector = cmds.xform(effector_name, q=True, ws=True, t=True) or [
                0.0,
                0.0,
                0.0,
            ]
        except Exception:
            end_effector = [0.0, 0.0, 0.0]

    pole_vector = [0.0, 0.0, 0.0]
    twist       = 0.0
    if handle_name_for_target:
        try:
            pv_x        = cmds.getAttr(f"{handle_name_for_target}.poleVectorX")
            pv_y        = cmds.getAttr(f"{handle_name_for_target}.poleVectorY")
            pv_z        = cmds.getAttr(f"{handle_name_for_target}.poleVectorZ")
            pole_vector = [pv_x, pv_y, pv_z]
            twist       = float(cmds.getAttr(f"{handle_name_for_target}.twist"))
        except Exception:
            pass

    (local_mats, world_mats,
     gates_r, gates_t, gates_s) = compute_ik_user_solve(
        node_self, joints, end_effector, pole_vector, twist, log_event_name
    )

    if local_mats is None:  # sentinel: expression error / empty -> skip this tick
        return

    # JSON snapshot so the Solver Context panel can read live values.
    try:
        from mpynode._common.nodes.snapshot import write_solver_context_snapshot

        write_solver_context_snapshot(
            node_self.thisMObject(),
            handle_name_for_target,
            joints,
            end_effector,
            pole_vector,
            twist,
        )
    except Exception:
        pass

    # Apply via ``offsetParentMatrix`` only: per joint, WORLD > LOCAL >
    # restore-bind, with per-joint rotate/translate/scale gating. The joint's own
    # T/R/S and jointOrient are always untouched, so animator FK stacks on top.
    _apply_joint_solve(joints, local_mats, world_mats,
                       gates_r, gates_t, gates_s, bind_offsets)


# Error sentinel for compute_ik_user_solve: matches the 5-tuple return arity
# (local_mats, world_mats, gates_rotate, gates_translate, gates_scale).
# local_mats=None signals "skip this solve tick".
_IK_SOLVE_ERR = (None, None, None, None, None)


def compute_ik_user_solve(
    node_self,
    joints,
    end_effector,
    pole_vector,
    twist,
    log_event_name: str = "<mpyiksolver-solve>",
):
    """Run the user expression with the IK context. Returns the 5-tuple
    ``(local_mats, world_mats, gates_rotate, gates_translate, gates_scale)`` --
    ``local_mats`` / ``world_mats`` are per-joint lists (len n) of 4x4 matrices
    (or None per slot), and each gate is a per-joint list of bools (len n). On
    error the sentinel ``_IK_SOLVE_ERR`` (local_mats=None) is returned.

    namespace contract: the IK locals are exposed via ``self.X``, NOT as bare
    names. The solver writes ONLY ``offsetParentMatrix``, so the joint's own
    T/R/S channels and ``jointOrient`` always stay untouched. Two matrix outputs
    (each a per-joint list of Nones; assign a slot to drive that joint):

        # WORLD (absolute) frame -- e.g. from an aim / goal solve:
        self.world_matrices[0] = root_world_mat   # 4x4 numpy / MatrixView
        # LOCAL (parent-relative) frame -- e.g. from a local bend:
        self.local_matrices[1] = knee_local_mat
        # per-joint dispatch is WORLD > LOCAL > follow-rest.

    ``MatrixView`` is injected into the namespace and each joint exposes
    ``joints[i]["matrix"]`` (local) + ``joints[i]["world_matrix"]`` (rest world)
    as MatrixViews, so a non-matrix user can copy + mutate one::

        m = joints[1]["world_matrix"]; m.setRotation([rx, ry, rz])  # radians
        self.world_matrices[1] = m

    Channel gates select which components of the desired matrix drive the joint;
    ungated channels come from the joint's rest pose (so rotate-only reorients in
    place, preserving bone lengths). Each gate is a scalar bool (broadcast to the
    whole chain) OR a per-joint list of bools (ragged -> default-filled)::

        self.apply_rotate = True             # default True  (whole chain)
        self.apply_translate = False         # default False
        self.apply_scale = False             # default False
        # self.apply_translate = [False, False, True]  # only the tip may slide

    A slot left None (in both matrix lists) leaves the joint at its rest offset.
    """
    fn_node = om.MFnDependencyNode(node_self.thisMObject())
    try:
        expr_plug = fn_node.findPlug("_computeSource", True)
        expr_str  = expr_plug.asString()
    except Exception:
        return _IK_SOLVE_ERR
    if not expr_str or expr_str == "None":
        return _IK_SOLVE_ERR

    # Compile via the SHARED safe_compile_expression so a syntax error surfaces
    # to the script editor AND stderr exactly as the base mPyNode does.
    # MPxIkSolverNode never routes setAttr through setInternalValue, so this
    # solve-time compile is the node's ONLY chance to surface a bad expression;
    # a hand-rolled compile() here would diverge from the base contract.
    from mpynode._common.compute.expression import safe_compile_expression

    node_name_for_msg = ""
    try:
        node_name_for_msg = fn_node.name()
    except Exception:
        pass
    code = safe_compile_expression(
        expr_str,
        node_name = node_name_for_msg,
        filename  = "<mpyiksolver-expression>",
    )
    if code is None:
        # Syntax error already surfaced by safe_compile_expression; skip
        # this solve tick (the node keeps its last-known-good pose).
        return _IK_SOLVE_ERR

    n = len(joints)

    # Read stored vars for this node so the user can use ``self.X``.
    from mpynode._common.io import serialization as _serialization
    from mpynode._common.storedvars import stored_var_store as _svstore

    # The expression reads the IK context via ``self.X`` (joints, end_effector,
    # pole_vector, twist) and writes its matrix results back through the same
    # surface; the bridge harvests them via ``get_compute_locals()``.
    from mpynode._common.compute.self_proxy import SelfProxy

    # Bind the node identity FIRST: it keys the stored-var cache for both the
    # load here and the writeback below. This assignment used to live AFTER the
    # load, so ``node_obj`` was referenced before assignment; the resulting
    # UnboundLocalError was swallowed by a bare except, stored vars loaded as {}
    # on EVERY solve, and the writeback then overwrote persisted state (data
    # loss).
    try:
        node_obj = node_self.thisMObject()
    except Exception:
        node_obj = None

    stored_vars = {}
    if node_obj is not None:
        try:
            sv_str      = fn_node.findPlug("_storedVarsData", True).asString()
            stored_vars = _svstore.load_for_compute(node_obj, sv_str)
        except RuntimeError:
            # genuine plug-read failure (missing/garbage plug); start empty.
            # NOT a bare except -- a bare one is exactly what hid this bug.
            stored_vars = {}

    # Two matrix output buffers, each a per-joint list of ``None``. In-place
    # ``self.local_matrices[i] = M`` and a full rebind both round-trip via
    # get_compute_locals(); a ``None`` slot leaves that joint at its rest offset.
    # local_matrices holds LOCAL (parent-relative) frames, world_matrices holds
    # WORLD (absolute). The apply is CHANNEL-GATED (default: rotate only).
    local_matrices_buf = [None] * n
    world_matrices_buf = [None] * n

    ik_compute_locals = {
        "joints":       joints,
        "end_effector": np.asarray(end_effector, dtype=np.float64),
        "pole_vector":  np.asarray(pole_vector, dtype=np.float64),
        "twist":        float(twist),
        # per-joint desired LOCAL (parent-relative) matrices.
        "local_matrices": local_matrices_buf,
        # per-joint desired WORLD (absolute) matrices.
        "world_matrices": world_matrices_buf,
        # Channel gates: which components of each desired matrix drive the
        # joint. Ungated components come from the rest pose, so rotate-only
        # reorients in place and preserves bone lengths. A scalar broadcasts; a
        # per-joint list gates individual joints.
        "apply_rotate":    True,
        "apply_translate": False,
        "apply_scale":     False,
    }
    # C2 (base contract): seed USER inputs DENSELY so ``self.<input>`` is a
    # numpy value instead of the ragged live plug proxy that breaks
    # ``np.asarray(...)``. setdefault never clobbers a curated IK internal.
    if node_obj is not None:
        from mpynode._common.compute.user_input_seed import seed_user_inputs_into_locals

        seed_user_inputs_into_locals(node_obj, ik_compute_locals)

    self_proxy = SelfProxy(
        node_obj,
        datablock      = None,
        user_storage   = stored_vars,
        compute_locals = ik_compute_locals,
        # local_matrices / world_matrices are in-place-mutated output buffers,
        # left UNMARKED so ``self.local_matrices[i] = ...`` keeps mutating the
        # seeded list. joints / end_effector / pole_vector / twist are decoded
        # type-promoted reads and must stay Tier-1 wins -- NOT scratch.
        output_scratch_keys = set(),
        node_type_label     = type(node_self).__name__,
    )

    # Single namespace dict -- only __builtins__ auto-injected; the IK
    # names are not bare, they live under ``self.X``.
    import builtins as _builtins

    from mpynode._common.plugs.promoted_types import MatrixView

    namespace: dict = {
        "__builtins__": _builtins,
        "self":         self_proxy,
        # Convenience: build/mutate a matrix result via MatrixView
        # (setRotation / setTranslation in RADIANS, chainable).
        "MatrixView": MatrixView,
    }

    # Route through exec_with_profile_watch so the IK node also gets timing /
    # cProfile / watch instrumentation.
    from mpynode._common.compute.expression import exec_with_profile_watch as _exec

    captured: list[str] = []

    def _on_err(msg):
        captured.append(msg)

    ok = _exec(
        code,
        namespace,
        log_event_name = log_event_name,
        on_error       = _on_err,
        node_obj       = node_obj,
    )
    if not ok:
        if captured:
            sys.stderr.write(captured[0])
            # Also broadcast to the UI Log panel via the Qt-free log_bus
            # (no-op when no subscribers are alive).
            from mpynode._common.util.log_bus import log as _log_bus

            _log_bus(f"[mPyIkSolver] {captured[0]}", level="error")
        return _IK_SOLVE_ERR

    # commit any stored-var changes via SelfProxy diff.
    storage_diff = self_proxy.diff_storage()
    if storage_diff:
        new_stored = dict(stored_vars)
        for k, v in storage_diff.items():
            if v is None:
                new_stored.pop(k, None)
            else:
                new_stored[k] = v
        _svstore.set_for_compute(node_obj, new_stored)

    # Harvest the two matrix output lists + the three gates from the
    # compute_locals snapshot, normalised to per-joint lists of length n.
    locals_out = self_proxy.get_compute_locals()
    local_mats = _normalize_matrix_list(locals_out.get("local_matrices"), n)
    world_mats = _normalize_matrix_list(locals_out.get("world_matrices"), n)
    gates_r    = _normalize_gate(locals_out.get("apply_rotate", True),     n, True)
    gates_t    = _normalize_gate(locals_out.get("apply_translate", False), n, False)
    gates_s    = _normalize_gate(locals_out.get("apply_scale", False),     n, False)
    return (local_mats, world_mats, gates_r, gates_t, gates_s)
