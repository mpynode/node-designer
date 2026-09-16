"""MPyTransform (API 1.0) -- expression-driven custom transform.

Inherits from MPxTransform (NOT exposed in API 2.0). The node behaves like a
SINGLE-JOINT IK solver: the expression publishes a desired LOCAL matrix plus
per-channel ``apply_*`` gates, and the node rides that result on
``offsetParentMatrix`` (so descendants track it) while un-gated channels fall
back to the live TRS (bind offset == identity).

User expression namespace -- GATED LOCAL-MATRIX contract (four WRITE slots +
five always-present per-channel READS; access via ``self.X``):

 * ``self.translate``       -- READ: this node's own live translate channel as a
 ``(3,)`` float64 numpy (tx, ty, tz).
 * ``self.rotate``          -- READ: the live rotate channel as ``(3,)`` float64
 numpy in **RADIANS** (rx, ry, rz).
 * ``self.scale``           -- READ: the live scale channel as ``(3,)`` float64.
 * ``self.shear``           -- READ: the live shear channel as ``(3,)`` float64
 (shearXY, shearXZ, shearYZ).
 * ``self.rotate_order``    -- READ: the rotate-order enum as an ``int`` 0..5
 (0 == xyz, matching the ``.rotateOrder`` plug).
 (Any change to a channel above re-evaluates the node -- they are the built-in
 transform inputs. Read a WORLD or a DRIVER matrix by adding a matrix INPUT
 attr, e.g. ``self.matrix0``.)
 * ``self.local_matrix``    -- numpy (4, 4) float64 or ``None`` (default). The
 desired LOCAL (parent-relative) matrix.
 * ``self.apply_rotate``    -- bool (default ``True``) -- gate: take rotation
 from the matrix (set ``False`` to keep the live TRS rotation).
 * ``self.apply_translate`` -- bool (default ``True``) -- gate: take translate.
 * ``self.apply_scale``     -- bool (default ``True``) -- gate: take scale.

Dispatch: ``local_matrix`` ``None`` -> nothing applied (plain Maya transform,
regardless of the gates -- the "no matrix set" case is checked first). Otherwise
a gate left ``True`` takes that channel from the matrix, a gate set ``False``
keeps the live TRS value.

Read this node's OWN live channels via ``self.translate`` / ``self.rotate``
(RADIANS) / ``self.scale`` / ``self.shear`` / ``self.rotate_order`` (above).
Read EXTERNAL / world driver values through matrix INPUT attrs -- e.g. the aim
template connects two ``worldMatrix`` plugs into ``matrix0`` / ``matrix1`` and
reads them via ``self.matrix0.asNumpy()``. To place the node in WORLD space, feed
the parent world through a CONNECTED matrix input and set ``self.local_matrix =
worldDesired @ inv(parentWorld)``. The node NEVER reads its own DAG parent -- an
imperative parent read is not DG-tracked and would go stale on a parent move,
which is why world-space is opt-in through a tracked input instead.

Maya stores matrices ROW-MAJOR with translation in the LAST ROW (row 3,
columns 0..2), per the OpenMaya MMatrix convention. To lift the transform up
by Y=2 units in local space:

 import numpy as np
 m = np.eye(4)
 m[3, 1] = 2.0
 self.local_matrix = m         # gates default True -> all channels driven;
                               # set e.g. self.apply_rotate = False to keep
                               # the live rotation.

design decisions and Maya quirks discovered:

 * Use the paired MPxTransform + MPxTransformationMatrix pattern (Maya
 devkit ``rockingTransform`` example).
 * FLUSH-FREE (R1-double): ``asMatrix()`` returns the PLAIN TRS -- the
 expression runs in ``_run_expression`` (the desired-local hook), and the
 transform's ``compute()`` authors ``opm = inv(L) @ D`` into a hidden
 ``_outLocalFlat`` double[16] output. A stock ``fourByFourMatrix`` relay
 (auto-wired per node) rebuilds that into ``offsetParentMatrix``, so
 ``world = L @ opm @ parent = D @ parent``. A matrix output straight off
 ``compute()`` segfaults in Maya 2026, hence the flat double[] carrier.
 * The WORLD dispatch reads the TRUE DAG parent world (``MDagPath.pop()`` +
 inclusiveMatrix), NOT ``parentMatrix`` (which already folds in our own
 ``offsetParentMatrix`` and would feed the output back).
 * **Time-driven matrix invalidation requires a process-wide
 ``MEventMessage.timeChange`` callback** that ``dgdirty``-s every
 mPyTransform on every frame change. ``setDependentsDirty`` fires
 only the FIRST time the connection ``time1.outTime -> _timeIn``
 propagates (Maya caches the dependency graph after that), and the
 matrix plug stays clean across subsequent time changes. Verified
 empirically in Maya 2026 mayapy. The callback is registered in the
 plug-in's ``initializePlugin`` via the shared ``CALLBACK_MANAGER``.
 * Fail-safe error mode: expression error -> return standard Maya TRS
 matrix (transform behaves as a normal Maya transform; children stay
 in place; viewport doesn't break).
 * MTypeId 0x00135717 (node), 0x00135718 (matrix). Sequential from
 mPyDeformer's 0x00135716.
"""

from __future__ import annotations

import sys

import maya.OpenMaya as om
import maya.OpenMayaMPx as ommpx
import numpy as np
from mpynode._api1 import helpers
from mpynode._common.compute.expression import compile_expression
from mpynode._common.plugs.promoted_types import TimeFloat


# ===========================================================================
# Matrix conversion helpers
# ===========================================================================


def _mmatrix_to_np(mm: om.MMatrix) -> np.ndarray:
    """Convert an API 1.0 ``MMatrix`` to a ``(4, 4)`` float64 ndarray.

    MMatrix stores values row-major with element access via ``mm(r, c)``.
    """
    out = np.empty((4, 4), dtype=np.float64)
    for r in range(4):
        for c in range(4):
            out[r, c] = mm(r, c)
    return out


def _np_to_mmatrix(arr) -> om.MMatrix:
    """Convert a ``(4, 4)`` numpy array to an API 1.0 ``MMatrix``.

    Uses ``MScriptUtil.createMatrixFromList`` which is the canonical
    bridge for API 1.0 matrix construction.
    """
    if arr is None or not hasattr(arr, "shape") or arr.shape != (4, 4):
        return om.MMatrix()
    flat = np.asarray(arr, dtype=np.float64).flatten().tolist()
    out  = om.MMatrix()
    om.MScriptUtil.createMatrixFromList(flat, out)
    return out


def _read_double3(cmds, node_name, attr_name, default):
    """Deprecation note: replaced inside ``_run_expression``
    by ``_read_compound_via_plug``. Kept here for legacy callers /
    introspection (the function is part of the module surface a few
    tests historically grep).

    Read a compound 3-tuple via cmds. Returns ``np.ndarray(3,)`` of
    float64; falls back to ``default`` on any failure."""
    try:
        val = cmds.getAttr(node_name + "." + attr_name)
        if isinstance(val, list) and len(val) == 1 and hasattr(val[0], "__len__"):
            val = val[0]
        if val is None or not hasattr(val, "__len__") or len(val) != 3:
            return np.array([default] * 3, dtype=np.float64)
        return np.array(val, dtype=np.float64)
    except Exception:
        return np.array([default] * 3, dtype=np.float64)


def _read_compound_via_plug(plug_proxy, name, default):
    """Pull a Double3 compound plug as ``(3,) float64``
    numpy via ``PlugProxy.<name>.asNumpy()`` (the
    CompoundPlugProxy numpy bridge). Falls back to a 3-vector of
    ``default`` on any access failure.

    This replaces the ``cmds.getAttr`` based ``_read_double3`` calls
    inside transform/constraint compute paths -- no DG re-entry, no
    EM-unsafety, no MEL dispatch cost."""
    try:
        sub = getattr(plug_proxy, name)
        if hasattr(sub, "asNumpy"):
            arr = sub.asNumpy()
            if arr.shape == (3,):
                return arr
        # Some plugs may already be a numpy array.
        if hasattr(sub, "shape") and getattr(sub, "shape", None) == (3,):
            return np.asarray(sub, dtype=np.float64)
    except Exception:
        pass
    return np.array([default] * 3, dtype=np.float64)


def _read_transform_components(mtx):
    """Read this node's OWN live channels off the paired MPxTransformationMatrix
    accessors -- the SAME fresh source the compiled ``desiredLocal`` binds to.

    Maya populates the transformation matrix from the (manual OR connected)
    channel plugs before ``compute`` runs, so these accessors track every
    evaluation. A ``PlugProxy`` / bare ``MPlug`` read is stale-by-one inside this
    custom-output compute (see ``_pull_inputs_through_datablock``), which would
    freeze ``self.translate`` etc. at the previous value.

    Returns ``(translate, rotate, scale, shear, rotate_order)``:
      * translate / scale / shear -> ``(3,)`` float64 (Maya internal units;
        translate in cm), rotate -> ``(3,)`` float64 in RADIANS,
      * rotate_order -> ``int`` 0..5 (0 == xyz). ``rotationOrder()`` is 1-based
        (kXYZ == 1), so subtract 1 to match the ``.rotateOrder`` plug enum.
    """
    sp = om.MSpace.kTransform

    def _vec(v):
        return np.array([v.x, v.y, v.z], dtype=np.float64)

    try:
        t = _vec(mtx.translation(sp))
    except Exception:
        t = np.zeros(3, dtype=np.float64)
    try:
        r = _vec(mtx.eulerRotation(sp))
    except Exception:
        r = np.zeros(3, dtype=np.float64)
    try:
        sc = _vec(mtx.scale(sp))
    except Exception:
        sc = np.ones(3, dtype=np.float64)
    try:
        sh = _vec(mtx.shear(sp))
    except Exception:
        sh = np.zeros(3, dtype=np.float64)
    try:
        ro = max(0, min(5, int(mtx.rotationOrder()) - 1))
    except Exception:
        ro = 0
    return t, r, sc, sh, ro


# ===========================================================================
# Gated local-matrix contract (mirrors mPyIkSolver, single joint) -- resolve
# the desired LOCAL matrix D from self.local_matrix + apply_* gates
# ===========================================================================


def _coerce_mat4(val):
    """Coerce a harvested matrix slot to a ``(4, 4)`` float64 ndarray, or
    ``None``. Accepts numpy / MatrixView / MMatrix / nested list; anything that
    is not a 4x4 -> ``None`` (treated as "not set")."""
    if val is None:
        return None
    if hasattr(val, "asNumpy"):
        try:
            val = val.asNumpy()
        except Exception:
            return None
    try:
        return np.asarray(val, dtype=np.float64).reshape(4, 4)
    except Exception:
        return None


def _resolve_desired_local(local_np, local_matrix, g_r, g_t, g_s):
    """Resolve the desired LOCAL matrix ``D`` from the gated ``local_matrix`` slot.

    MPyTransform is, conceptually, a single-"joint" mPyIkSolver with the bind
    offset pinned to identity: the rest/base for un-gated channels is the node's
    own live pose ``L``, so a vanilla node behaves exactly like a normal Maya
    transform. The expression publishes a desired PARENT-RELATIVE matrix via
    ``self.local_matrix`` plus the per-channel ``apply_*`` gates, mixed through
    the shared ``helpers._gate_mix_world``.

    ``_author_opm_flat`` turns ``D`` into ``opm = inv(L) @ D``, so ``D = L_mixed``
    -> ``opm = inv(L) @ L_mixed`` and ``world = L @ opm @ parent = D @ parent``.
    To place the node in WORLD space, read the parent world through a CONNECTED
    matrix input (DG-tracked) and set ``self.local_matrix = worldDesired @
    inv(parentWorld)``; the node itself never reads its DAG parent (an imperative
    parent read is not DG-tracked and would go stale on a parent move), so
    world-space is opt-in and cycle-free.

    Returns a ``(4, 4)`` ndarray, or ``None`` for a no-op (identity opm).
    """
    lm = _coerce_mat4(local_matrix)
    # No-op: no matrix set, or every gate closed -> identity opm.
    if lm is None or not (g_r or g_t or g_s):
        return None
    L = np.asarray(local_np, dtype=np.float64).reshape(4, 4)
    return helpers._gate_mix_world(L, lm, g_r, g_t, g_s)


# Hidden double[16] array output carrying the desired offsetParentMatrix. A
# matrix-typed output from MPxTransform.compute() segfaults in Maya 2026; a
# double[] does not. A paired stock ``fourByFourMatrix`` relay rebuilds these
# into the matrix wired to offsetParentMatrix.
_OPM_FLAT_ATTR       = "_outLocalFlat"
_OPM_FLAT_ATTR_SHORT = "_olf"
# Name of the paired relay node's connection target on the transform.
_RELAY_NODE_SUFFIX = "_opmRelay"

# Internal plugs whose change must invalidate the matrix outputs.
_MATRIX_DIRTY_TRIGGERS = frozenset(
    {
        "_computeSource",
        "_storedVarsData",
        "_inputAttrs",
        "_outputAttrs",
        "_timeIn",  # time1.outTime -> _timeIn invalidates matrix
    }
)

# Built-in transform channels the expression reads (``self.translate`` etc.). A
# change to any alters the desired local matrix and must re-dirty the
# ``_outLocalFlat`` opm output; these are ALSO pulled through the datablock
# during compute (_pull_inputs_through_datablock) so Maya re-dirties them
# natively. NOTE: ``parentMatrix`` is intentionally NOT here -- the node no
# longer reads its DAG parent (world placement is opt-in via a CONNECTED matrix
# input, a trigger on the user-input path), so an ancestor move just carries the
# node natively without a re-eval.
_BUILTIN_MATRIX_INPUT_NAMES = frozenset(
    {"translate", "rotate", "scale", "shear", "rotateOrder"}
)


def _is_matrix_dirty_trigger(plug_name, root_name, input_attrs_json):
    """Decide whether a dirtied plug must invalidate the matrix outputs.

    A plug is a trigger when it is one of the internal driver plugs
    (``_computeSource`` etc.) OR a user-declared INPUT attribute, since user
    inputs feed the compute expression that produces the desired matrix.
    User inputs were historically omitted, so an mPyTransform aimed by
    connected matrix inputs never declared its input->matrix-output dependency.

    Args:
        plug_name: the dirtied attribute's ``MFnAttribute.name()``.
        root_name: the plug's ROOT long name (compound/array child resolved).
        input_attrs_json: the node's serialized ``_inputAttrs`` map (may be "").

    Returns:
        bool -- True if the matrix outputs should be dirtied.
    """
    if plug_name in _MATRIX_DIRTY_TRIGGERS:
        return True
    if root_name in _MATRIX_DIRTY_TRIGGERS:
        return True
    # Built-in transform channels the expression may read (translateX resolves
    # to root ``translate``; parentMatrix arrives when an ancestor moves).
    if root_name in _BUILTIN_MATRIX_INPUT_NAMES:
        return True
    if plug_name in _BUILTIN_MATRIX_INPUT_NAMES:
        return True
    if not input_attrs_json:
        return False
    try:
        from mpynode._common.io import serialization as _serialization

        input_map = _serialization.decode_attr_map(input_attrs_json)
    except Exception:
        return False
    return root_name in input_map or plug_name in input_map


# ===========================================================================
# MPxTransformationMatrix subclass -- the actual matrix-output hook
# ===========================================================================


class MPyTransformMatrix(ommpx.MPxTransformationMatrix):
    """Custom matrix paired with MPyTransform.

    Maya invokes ``asMatrix()`` whenever the transform's local matrix is
    needed. We run the user expression here and return the result.

    Sync state (populated by the parent MPyTransform during ``compute``
    and ``setInternalValueInContext``):
        * ``_transform_mobject`` -- back-ref to the owning transform node
        * ``_expr_str``          -- raw expression text
        * ``_expr_code``         -- compiled expression code object
    """

    NODE_ID = om.MTypeId(0x00135718)

    def __init__(self):
        super().__init__()
        # Synced from the parent MPyTransform every compute tick.
        self._transform_mobject = None
        self._expr_str: str = ""
        self._expr_code = compile_expression("")
        # Re-entrancy guard for asMatrix() -- see the guard block there.
        self._in_as_matrix   = False
        self._reentry_warned = False

    @staticmethod
    def matrix_creator():
        return ommpx.asMPxPtr(MPyTransformMatrix())

    def asMatrix(self, *args):
        """Return the plain default TRS-composed local matrix.

        FLUSH-FREE re-arch: the user expression NO LONGER runs here. Authoring
        the local matrix from asMatrix() froze descendant DAG world caches
        (requiring the old per-frame timeChanged flush hack). The expression now
        runs in ``MPyTransform.compute()`` (reusing :meth:`_run_expression`) and
        its result is delivered through ``offsetParentMatrix`` via a paired
        ``fourByFourMatrix`` relay, which propagates to worldMatrix + descendants
        natively. The local ``matrix`` therefore stays the honest TRS composition
        and the world result is unchanged (world = matrix x opm x parent ==
        expression's desired local x parent).
        """
        try:
            return super().asMatrix(*args)
        except Exception:
            return om.MMatrix()

    # ------------------------------------------------------------------
    # User expression bridge (SelfProxy pattern)
    # ------------------------------------------------------------------

    def _run_expression(self, default_np):
        """Execute the user expression. Return ``(4, 4)`` ndarray or
        ``None`` on error / no-op.

        namespace contract: the gated LOCAL-matrix write slots + the
        per-channel READS via ``self.X``, ``__builtins__`` only, no
        auto-imported modules.

        Live TRS / rotate-order reads come off the paired
        ``MPxTransformationMatrix`` accessors
        (``_read_transform_components``), fresh every compute and identical
        to the compiled ``desiredLocal`` source, so interpreted and compiled
        stay at parity (a ``cmds.getAttr`` / ``PlugProxy`` read would be
        stale-by-one inside this custom-output compute). The node NEVER reads
        its own DAG parent -- WORLD placement is a connected-parent expression
        (``local_matrix = world @ inv(parent)``), so there is no parent read to
        go stale and no feedback loop.
        """
        if self._expr_code is None:
            return None

        from maya import cmds
        from mpynode._common.io import serialization as _serialization
        from mpynode._common.storedvars import stored_var_store as _svstore
        from mpynode._common.compute.self_proxy import SelfProxy

        # Look up the owning node's name from the cached MObject.
        try:
            fn_node   = om.MFnDependencyNode(self._transform_mobject)
            node_name = fn_node.name()
        except Exception:
            return None

        # Stored vars.
        stored_vars: dict = {}
        try:
            sv_str      = fn_node.findPlug("_storedVarsData", True).asString()
            stored_vars = _svstore.load_for_compute(self._transform_mobject, sv_str)
        except Exception:
            stored_vars = {}

        # Pre-seed ARRAY user outputs as mutable (N, ...) buffers so the
        # expression can slice-assign them in place (e.g.
        # ``self.outMatrices[:, 3, :3] = ...``). Scalar user outputs keep
        # the direct plug-write path; these are harvested back after exec.
        from mpynode._common.compute.output_defaults import (
            harvest_array_outputs_api1,
            seed_array_outputs_api1,
        )

        seeded_array_outputs = seed_array_outputs_api1(self._transform_mobject)

        # GATED LOCAL-MATRIX CONTRACT (mirrors mPyIkSolver, single joint). The
        # expression writes the parent-relative ``local_matrix`` 4x4 + per-
        # channel gates, all defaulting to a no-op so a vanilla node is a plain
        # transform. ``local_matrix`` is the SOLE channel to
        # ``offsetParentMatrix``; for WORLD placement read the parent via a
        # CONNECTED matrix input and set ``local_matrix = world @ inv(parent)``.
        # READ slots come off the paired MPxTransformationMatrix accessors --
        # fresh every compute and identical to the compiled desiredLocal's
        # source, so interpreted/compiled stay at parity. rotate is RADIANS,
        # rotate_order the 0-based enum. Cycle-safe: the local channels never
        # depend on the authored opm.
        srt_t, srt_r, srt_sc, srt_sh, srt_ro = _read_transform_components(self)
        compute_locals = {
            "translate":    srt_t,
            "rotate":       srt_r,
            "scale":        srt_sc,
            "shear":        srt_sh,
            "rotate_order": srt_ro,
            "local_matrix": None,
            # Gates default TRUE. With local_matrix None the dispatch is still a
            # no-op (it checks "no matrix set" first), so a vanilla node stays a
            # plain transform -- but setting local_matrix then drives ALL
            # channels without also opening gates. Close one explicitly
            # (self.apply_scale = False) to leave that channel live.
            "apply_rotate":    True,
            "apply_translate": True,
            "apply_scale":     True,
        }
        compute_locals.update(seeded_array_outputs)
        # C2 (base contract): seed USER inputs DENSELY so ``self.<input>`` is a
        # numpy value (e.g. a vector array -> (N, 3)) instead of the ragged
        # live plug proxy that breaks ``np.asarray(self.<input>)``. setdefault
        # never clobbers a curated internal (local_matrix / apply_*).
        from mpynode._common.compute.user_input_seed import seed_user_inputs_into_locals

        seed_user_inputs_into_locals(self._transform_mobject, compute_locals)
        self_proxy = SelfProxy(
            self._transform_mobject,
            datablock       = None,
            user_storage    = stored_vars,
            compute_locals  = compute_locals,
            node_type_label = "MPyTransform",
        )

        import builtins as _builtins

        namespace = {
            "__builtins__": _builtins,
            "self":         self_proxy,
        }

        from mpynode._common.compute.expression import exec_with_profile_watch as _exec

        captured: list[str] = []

        def _on_err(msg):
            captured.append(msg)

        ok = _exec(
            self._expr_code,
            namespace,
            log_event_name = "<mpytransform-expression>",
            on_error       = _on_err,
            node_obj       = self._transform_mobject,
        )
        if not ok:
            if captured:
                # Base-contract policy (C10): suppress the benign transient
                # missing-plug error (declared-but-unresolved plug pulled mid
                # scene-load / graph rebuild), surface everything else.
                # Declared names = the seeded compute locals (TRS / array
                # outputs) plus any user-added input/output attr.
                declared = set(compute_locals)
                for _attr_plug in ("_inputAttrs", "_outputAttrs"):
                    try:
                        _s = fn_node.findPlug(_attr_plug, True).asString()
                        if _s:
                            declared.update(
                                _serialization.decode_attr_map(_s).keys()
                            )
                    except Exception:
                        pass
                from mpynode._common.compute.base_contract import broadcast_compute_error

                broadcast_compute_error(
                    "mPyTransform", captured[0], declared_names=declared
                )
            return None

        # Commit stored vars.
        storage_diff = self_proxy.diff_storage()
        if storage_diff:
            new_stored = dict(stored_vars)
            for k, v in storage_diff.items():
                if v is None:
                    new_stored.pop(k, None)
                else:
                    new_stored[k] = v
            _svstore.set_for_compute(self._transform_mobject, new_stored)

        # Harvest seeded ARRAY user outputs back to their plugs (writes
        # the slice-assigned buffer element-by-element via the plug tree).
        if seeded_array_outputs:
            harvest_array_outputs_api1(
                self_proxy.get_plug_proxy(),
                self_proxy.get_compute_locals(),
                seeded_array_outputs.keys(),
            )

        # Harvest the gated local-matrix slot and resolve the desired LOCAL
        # matrix ``D``. ``_author_opm_flat`` authors ``opm = inv(L) @ D``; a
        # ``None`` return is a no-op (identity opm -> plain transform).
        locals_out = self_proxy.get_compute_locals()
        return _resolve_desired_local(
            default_np,
            locals_out.get("local_matrix"),
            bool(locals_out.get("apply_rotate", False)),
            bool(locals_out.get("apply_translate", False)),
            bool(locals_out.get("apply_scale", False)),
        )


# ===========================================================================
# MPxTransform subclass
# ===========================================================================


class MPyTransform(ommpx.MPxTransform):
    NODE_NAME = "mPyTransform"
    NODE_ID   = om.MTypeId(0x00135717)

    # No INTERNAL_VARS schema: the gated local-matrix write slots (local_matrix
    # / apply_*) are seeded straight into the compute locals and harvested by
    # name, with no separate validation table.

    _expression_attr       = None
    _input_attrs_attr      = None
    _output_attrs_attr     = None
    _stored_vars_list_attr = None
    _stored_vars_data_attr = None
    _debug_mode_attr       = None
    _time_in_attr          = None
    _out_local_flat_attr   = None

    def __init__(self):
        super().__init__()
        self._expr_str: str = ""
        self._expr_code = compile_expression("")

    @staticmethod
    def node_creator():
        return ommpx.asMPxPtr(MPyTransform())

    @staticmethod
    def node_initializer():
        plugs                               = helpers.build_internal_attrs(MPyTransform)
        MPyTransform._expression_attr       = plugs["_computeSource"]
        MPyTransform._input_attrs_attr      = plugs["inputs"]
        MPyTransform._output_attrs_attr     = plugs["outputs"]
        MPyTransform._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyTransform._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyTransform._debug_mode_attr       = plugs["debug_mode"]
        # NOTE: translate, rotate, scale, shear, rotateOrder, parentMatrix
        # are INHERITED from Maya's built-in transform base class. Don't
        # re-add them.

        # Hidden time input. The wrapper auto-connects time1.outTime on create()
        # so Maya's DG marks the matrix dirty on every frame change. Without it
        # time-driven expressions appear frozen during playback, because Maya
        # caches the local matrix.
        time_fn   = om.MFnUnitAttribute()
        time_attr = time_fn.create("_timeIn", "_tin", om.MFnUnitAttribute.kTime, 0.0)
        time_fn.setStorable(True)
        time_fn.setKeyable(False)
        time_fn.setReadable(False)
        time_fn.setWritable(True)
        time_fn.setHidden(True)
        MPyTransform.addAttribute(time_attr)
        MPyTransform._time_in_attr = time_attr

        # FLUSH-FREE: the expression result reaches descendants through
        # ``offsetParentMatrix`` -- a genuine input-plug write that propagates to
        # worldMatrix + descendant DAG caches natively -- NOT by authoring the
        # local matrix in asMatrix(), which froze descendants and needed the
        # per-frame timeChanged flush hack. compute() writes the 16 row-major
        # floats of the DESIRED opm into this hidden array output; a paired stock
        # ``fourByFourMatrix`` relay (auto-created per node) rebuilds them into
        # the matrix wired to offsetParentMatrix. A *matrix* output from
        # MPxTransform.compute() SEGFAULTS in Maya 2026 -- a double[] does not.
        flat_fn = om.MFnNumericAttribute()
        flat_attr = flat_fn.create(
            _OPM_FLAT_ATTR, _OPM_FLAT_ATTR_SHORT, om.MFnNumericData.kDouble, 0.0
        )
        flat_fn.setWritable(False)
        flat_fn.setStorable(False)
        flat_fn.setReadable(True)
        flat_fn.setArray(True)
        flat_fn.setUsesArrayDataBuilder(True)
        flat_fn.setHidden(True)
        MPyTransform.addAttribute(flat_attr)
        MPyTransform._out_local_flat_attr = flat_attr

        # Time re-dirties the opm output every frame (static edge -> full
        # transitive cascade to worldMatrix + descendants). Dynamic user inputs
        # can't use attributeAffects (type-level only); they append this output
        # in setDependentsDirty instead.
        MPyTransform.attributeAffects(time_attr, flat_attr)

    # ------------------------------------------------------------------
    # Sync helpers -- push state to the paired matrix
    # ------------------------------------------------------------------

    def _sync_to_matrix(self):
        """Push expression + back-ref to the paired matrix instance.

        Called from compute() and setInternalValueInContext to keep the
        matrix's state current. The matrix uses this state in its
        ``asMatrix()`` override.
        """
        try:
            # Duplication robustness: Maya does NOT call
            # setInternalValueInContext when it DUPLICATES a node (the plug
            # value is copied directly), so a duplicated transform's cached
            # _expr_code is empty and its expression never runs. Reconcile
            # against the live _computeSource plug before pushing to the matrix;
            # cheap, since it recompiles only when the source actually changed.
            from maya import cmds as _cmds

            try:
                _name = om.MFnDependencyNode(self.thisMObject()).name()
                _cur  = _cmds.getAttr(_name + "._computeSource") or ""
            except Exception:
                _name, _cur = "", self._expr_str
            if _cur != self._expr_str:
                from mpynode._common.compute.expression import safe_compile_expression

                self._expr_str = _cur
                _code = safe_compile_expression(
                    _cur, node_name=_name, filename="<mpytransform-expression>"
                )
                if _code is not None:
                    self._expr_code = _code

            mtx_ptr = self.transformationMatrixPtr()
            if isinstance(mtx_ptr, MPyTransformMatrix):
                if mtx_ptr._transform_mobject is None:
                    mtx_ptr._transform_mobject = self.thisMObject()
                mtx_ptr._expr_str  = self._expr_str
                mtx_ptr._expr_code = self._expr_code
        except Exception:
            pass

    # ------------------------------------------------------------------
    # MPxNode / MPxTransform overrides
    # ------------------------------------------------------------------

    def compute(self, plug, data_block):
        """Author the flush-free ``_outLocalFlat`` opm output, else delegate.

        When Maya pulls ``_outLocalFlat`` (through the paired fourByFourMatrix
        relay wired to offsetParentMatrix), run the user expression to get the
        desired LOCAL matrix ``D`` and write ``opm = inv(L) x D`` (row-major
        flat) so that ``world = matrix x opm x parent == D x parent`` -- exactly
        the old asMatrix-authored semantics, but delivered through an input plug
        so descendants + world caches track natively (no timeChanged flush).
        """
        try:
            attr    = plug.attribute()
            is_flat = attr == MPyTransform._out_local_flat_attr
            if not is_flat and plug.isElement():
                try:
                    is_flat = (
                        plug.array().attribute()
                        == MPyTransform._out_local_flat_attr
                    )
                except Exception:
                    is_flat = False
            if is_flat:
                self._author_opm_flat(plug, data_block)
                return
        except Exception:
            pass
        # No custom output being pulled -- keep the paired matrix state fresh
        # (duplication robustness) and delegate to the transform base.
        self._sync_to_matrix()
        return super().compute(plug, data_block)

    def _pull_inputs_through_datablock(self, data_block):
        """Read every expression input THROUGH ``data_block`` so Maya marks the
        plug clean and re-dirties it on the next change.

        The expression reads TRS / time / parentMatrix / user inputs via cmds +
        PlugProxy (OUTSIDE the datablock). Maya only re-runs ``setDependentsDirty``
        for a plug that is CLEAN when a new dirty arrives; a plug that compute
        never pulls stays perpetually dirty, so the SECOND time/input change is
        silently dropped and the transform freezes after its first evaluation.
        Pulling each input here (a cheap handle read) establishes the genuine DG
        dependency that makes native per-change re-evaluation work -- this is
        what REPLACES the removed timeChanged callback + auto-dirty touch hacks.
        """
        fn_node = None
        try:
            fn_node = om.MFnDependencyNode(self.thisMObject())
        except Exception:
            return

        # (1) Time: pull through the datablock. This CLEANS ``_timeIn`` so Maya
        # re-dirties it on the next frame -- the value itself comes from
        # cmds.currentTime in the expression, so only the clean-state matters.
        try:
            if MPyTransform._time_in_attr is not None:
                data_block.inputValue(MPyTransform._time_in_attr)
        except Exception:
            pass

        # (2) Connected inputs (TRS / parentMatrix / user matrix0..N): FORCE a
        # fresh DG evaluation via cmds.getAttr. Measured in Maya 2026 mayapy (DG
        # mode): inside this custom-output compute neither the api1 datablock
        # (returns identity for a transform's dynamic connected input) nor a bare
        # api2 MPlug read (returns the PREVIOUS evaluation -- stale by one) is
        # fresh. Only cmds.getAttr pulls the live upstream value, and priming it
        # here syncs the shared DG core so the expression's later PlugProxy reads
        # see the current value. Main-thread only: cmds is unsafe on EM worker
        # threads, where the scheduler pre-populates the datablock instead.
        on_main = True
        try:
            import threading as _threading

            on_main = _threading.current_thread() is _threading.main_thread()
        except Exception:
            on_main = True
        if not on_main:
            return
        try:
            from maya import cmds as _cmds

            node_name = fn_node.name()
        except Exception:
            return
        primed = list(_BUILTIN_MATRIX_INPUT_NAMES)
        try:
            input_json = fn_node.findPlug("_inputAttrs", True).asString()
            if input_json:
                from mpynode._common.io import serialization as _serialization

                primed.extend(_serialization.decode_attr_map(input_json).keys())
        except Exception:
            pass
        for name in primed:
            plug = node_name + "." + name
            try:
                if not _cmds.objExists(plug):
                    continue
                # Only pay for CONNECTED inputs (a static local channel is read
                # fine by the expression + can't have gone stale-by-one).
                if name in _BUILTIN_MATRIX_INPUT_NAMES and not _cmds.listConnections(
                    plug, source=True, destination=False
                ):
                    continue
                _cmds.getAttr(plug)
            except Exception:
                pass

    def _author_opm_flat(self, plug, data_block):
        """Run the expression + write the 16 row-major floats of the desired
        ``offsetParentMatrix`` into the ``_outLocalFlat`` array output."""
        # CRITICAL: pull every expression input THROUGH the datablock so Maya
        # marks the plug clean and re-dirties it on the next change. The
        # expression reads TRS / time / user inputs via cmds + PlugProxy
        # (OUTSIDE the datablock); without this pull those plugs are never
        # cleaned, so Maya's dirty-propagation optimisation SKIPS
        # setDependentsDirty for an already-dirty plug and the transform freezes
        # after its first evaluation. This dependency REPLACES the old per-frame
        # timeChanged callback + auto-dirty "touch" hacks.
        self._pull_inputs_through_datablock(data_block)
        # Push expr code + owning MObject to the paired matrix so
        # _run_expression can read live plug state (and stays duplication-safe).
        self._sync_to_matrix()
        mtx = self.transformationMatrixPtr()

        # L = the plain default TRS-composed local matrix (asMatrix no longer
        # runs the expression, so this does not recurse).
        try:
            local_mm = mtx.asMatrix()
        except Exception:
            local_mm = om.MMatrix()
        local_np = _mmatrix_to_np(local_mm)

        # C1 (base contract): defer the expression while a scene is being READ --
        # the DG/EM may pull our opm before inputs resolve. Author an identity
        # opm now; the kAfterOpen sweep + the next evaluation recompute it once
        # the scene is whole.
        reading = False
        try:
            reading = om.MFileIO.isReadingFile()
        except Exception:
            reading = False

        # D = the expression's desired LOCAL matrix, resolved from the gated
        # local-matrix slot (self.local_matrix + apply_*).
        desired_np = None
        if not reading and isinstance(mtx, MPyTransformMatrix):
            try:
                desired_np = mtx._run_expression(local_np)
            except Exception as exc:
                sys.stderr.write(f"[mPyTransform._author_opm_flat] {exc}\n")
                desired_np = None
        if desired_np is None:
            desired_np = local_np  # read / error / no-op -> standard transform

        # opm = inv(L) * D  (row-vector Maya: world = L * opm * parent = D * parent)
        desired_mm = _np_to_mmatrix(desired_np)
        try:
            opm_mm = local_mm.inverse() * desired_mm
        except Exception:
            opm_mm = om.MMatrix()
        opm_flat = _mmatrix_to_np(opm_mm).flatten()

        arr      = data_block.outputArrayValue(MPyTransform._out_local_flat_attr)
        builder  = arr.builder()
        for i in range(16):
            builder.addElement(i).setDouble(float(opm_flat[i]))
        arr.set(builder)
        data_block.setClean(plug)
        try:
            data_block.setClean(MPyTransform._out_local_flat_attr)
        except Exception:
            pass

    def setInternalValueInContext(self, plug, data_handle, _ctx):
        try:
            attr = plug.attribute()
            if attr == MPyTransform._expression_attr:
                data           = om.MFnStringData(data_handle.data())
                self._expr_str = data.string()
                from mpynode._common.compute.expression import safe_compile_expression

                node_name = ""
                try:
                    node_name = om.MFnDependencyNode(self.thisMObject()).name()
                except Exception:
                    pass
                code = safe_compile_expression(
                    self._expr_str,
                    node_name = node_name,
                    filename  = "<mpytransform-expression>",
                )
                if code is not None:
                    self._expr_code = code
                # Push immediately so the next asMatrix call sees it.
                self._sync_to_matrix()
        except Exception:
            pass
        return False

    def setDependentsDirty(self, plug, affected_plugs):
        """Mark the matrix outputs dirty when user-side inputs change.

        MPxTransform doesn't auto-propagate dirtiness from our user attrs
        (expression, _storedVarsData, etc.) to the matrix outputs.
        Without this, ``set_compute_expression(...)`` wouldn't trigger
        re-evaluation of the transform pipeline.
        """
        try:
            attr_obj  = plug.attribute()
            attr_fn   = om.MFnAttribute(attr_obj)
            plug_name = attr_fn.name()
        except Exception:
            return

        # The plug's ROOT long name, so array/compound children (matrix0,
        # tension[3], translateY -> translate) resolve to the declared
        # attribute. ``useFullAttributePath=True`` is LOAD-BEARING: it yields
        # "translate.translateY", not the leaf "translateY", so a channel-box
        # edit of a single TRS child still counts as a matrix trigger. Without
        # it only setAttr on the whole compound re-triggered, and setting
        # .translateY froze the node after its first evaluation.
        try:
            root_name = plug.partialName(
                False, False, False, False, True, True
            ).split(".")[0].split("[")[0]
        except Exception:
            root_name = plug_name

        # Read the declared user inputs so a CONNECTED user input attr (matrix0,
        # tension, ...) also counts as a trigger. MPxTransform only auto-
        # propagates from the built-in TRS channels, so without this an aim
        # transform driven by matrix inputs never declares its
        # inputs->matrix-output dependency.
        input_attrs_json = ""
        try:
            input_attrs_json = om.MFnDependencyNode(
                self.thisMObject()
            ).findPlug("_inputAttrs", True).asString()
        except Exception:
            input_attrs_json = ""

        if not _is_matrix_dirty_trigger(plug_name, root_name, input_attrs_json):
            return

        # Dirty the ``_outLocalFlat`` opm output so the paired fourByFourMatrix
        # relay recomputes -> offsetParentMatrix -> worldMatrix -> descendants.
        # Dynamic user inputs, the internal driver plugs and the time input all
        # route through here (an array output can't rely on attributeAffects).
        #
        # We MUST append the 16 ELEMENT plugs (_outLocalFlat[0..15]), not just
        # the array root: the relay reads the elements, and a root-only append
        # dirties the array node without re-dirtying already-computed element
        # plugs -- so after the first evaluation every later change was silently
        # dropped and the transform froze (verified in mayapy: root-only ->
        # correct on first pull, stale forever after; element append -> tracks
        # every frame). ``elementByLogicalIndex`` materialises the element plug
        # if the builder hasn't run yet.
        try:
            fn_node   = om.MFnDependencyNode(self.thisMObject())
            flat_plug = fn_node.findPlug(_OPM_FLAT_ATTR, True)
            affected_plugs.append(flat_plug)
            for i in range(16):
                try:
                    affected_plugs.append(flat_plug.elementByLogicalIndex(i))
                except Exception:
                    pass
        except Exception:
            pass


# ===========================================================================
# Flush-free opm relay -- fourByFourMatrix rebuild of the authored offset
# parent matrix, wired automatically for every mPyTransform
# ===========================================================================
#
# This replaces a process-wide per-frame ``timeChanged`` callback and its
# non-undoable TRS-write "cache flush". ``compute`` authors the desired
# offset-parent matrix as 16 plain doubles on ``_outLocalFlat`` (a MATRIX output
# from ``MPxTransform.compute`` segfaults on read; a ``double[]`` does not), and
# a stock ``fourByFourMatrix`` relay reassembles it to drive
# ``offsetParentMatrix``. Travelling through a genuine DG connection means
# Maya's world-matrix cache invalidates natively on every input change -- static
# or time-driven, in DG, EM-parallel and Cached Playback -- so no manual flush
# is ever needed.


def ensure_opm_relay(node_name, force=False):
    """Idempotently create + wire the paired ``fourByFourMatrix`` relay that
    rebuilds ``node_name``'s authored offsetParentMatrix from its flat
    ``_outLocalFlat`` double[16] output (row-major ``in00``..``in33``).

    Idempotent: if ``offsetParentMatrix`` already has an incoming connection
    (a relay restored from a saved scene, or wired by a prior call) the node is
    left untouched and the existing driver is returned. ``force`` re-wires
    regardless. Returns the relay node name, or ``None`` on any failure
    (swallowed -- never raises, so it is safe inside a nodeAdded callback).
    """
    try:
        from maya import cmds
    except Exception:
        return None
    try:
        if not cmds.objExists(node_name):
            return None
        opm      = node_name + ".offsetParentMatrix"
        existing = cmds.listConnections(opm, source=True, destination=False)
        if existing and not force:
            return existing[0]
        # ``fourByFourMatrix`` lives in the stock ``matrixNodes`` plugin.
        try:
            if not cmds.pluginInfo("matrixNodes", q=True, loaded=True):
                cmds.loadPlugin("matrixNodes", quiet=True)
        except Exception:
            pass
        relay_base = node_name.split("|")[-1].split(":")[-1] + _RELAY_NODE_SUFFIX
        relay = cmds.createNode(
            "fourByFourMatrix", name=relay_base, skipSelect=True
        )
        for i in range(16):
            src = "%s.%s[%d]" % (node_name, _OPM_FLAT_ATTR, i)
            dst = "%s.in%d%d" % (relay, i // 4, i % 4)
            cmds.connectAttr(src, dst, force=True)
        cmds.connectAttr(relay + ".output", opm, force=True)
        return relay
    except Exception as exc:
        sys.stderr.write(
            "[mPyTransform] ensure_opm_relay(%s) failed: %s\n" % (node_name, exc)
        )
        return None


def _on_transform_added(node_obj, _client_data):
    """``nodeAdded`` hook for ``mPyTransform``: wire the opm relay for a freshly
    created transform.

    Skipped during file read -- a saved scene already carries its relay + the
    16 element connections, and the ``kAfterOpen`` sweep is the backstop for any
    legacy transform that predates this architecture. Wired INLINE (not
    deferred) so a bare ``createNode('mPyTransform')`` -- pervasive in tests,
    .mpn import, and templates -- has a live relay immediately, including in
    ``mayapy`` batch where the idle loop a deferred call needs never ticks. The
    relay reads only ``_outLocalFlat`` (no dependency on any attr the caller
    sets AFTER createNode), so inline wiring is safe.
    """
    try:
        if om.MFileIO.isReadingFile():
            return
    except Exception:
        pass
    try:
        name = om.MFnDependencyNode(node_obj).name()
    except Exception:
        return
    try:
        ensure_opm_relay(name)
    except Exception:
        pass


def _on_after_open(_client_data):
    """After a scene opens (or imports), ensure every mPyTransform has its opm
    relay. New scenes carry the relay already (``ensure_opm_relay``
    short-circuits); legacy scenes authored before the flush-free
    re-architecture get theirs built now. Idempotent backstop for the
    nodeAdded race on file load."""
    try:
        from maya import cmds

        for node in cmds.ls(type=MPyTransform.NODE_NAME, long=True) or []:
            try:
                ensure_opm_relay(node)
            except Exception:
                pass
    except Exception:
        pass


def register_relay_callbacks() -> int:
    """Install the nodeAdded + scene-open callbacks that auto-wire the
    fourByFourMatrix opm relay for every mPyTransform. Tracked via
    CALLBACK_MANAGER (OWNER_API1) so they tear down cleanly on plugin unload.
    Also sweeps any mPyTransform already in the scene at registration time.

    Returns 0 on success, -1 on failure.
    """
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API1
        from maya import cmds
    except Exception as exc:
        sys.stderr.write(
            "[mPyTransform] failed to register relay callbacks: %s\n" % exc
        )
        return -1

    # Sweep pre-existing nodes (e.g. plugin (re)loaded into a populated scene).
    try:
        for node in cmds.ls(type=MPyTransform.NODE_NAME, long=True) or []:
            ensure_opm_relay(node)
    except Exception:
        pass

    try:
        added_id = om.MDGMessage.addNodeAddedCallback(
            _on_transform_added, MPyTransform.NODE_NAME
        )
        CALLBACK_MANAGER.register(added_id, om.MMessage.removeCallback, OWNER_API1)
    except Exception as exc:
        sys.stderr.write(
            "[mPyTransform] node-added relay hook failed: %s\n" % exc
        )

    # addNodeAddedCallback can race a file load and miss nodes; the kAfterOpen /
    # kAfterImport sweeps are the idempotent backstop.
    for evt_name in ("kAfterOpen", "kAfterImport"):
        try:
            evt = getattr(om.MSceneMessage, evt_name, None)
            if evt is None:
                continue
            open_id = om.MSceneMessage.addCallback(evt, _on_after_open)
            CALLBACK_MANAGER.register(
                open_id, om.MMessage.removeCallback, OWNER_API1
            )
        except Exception:
            pass
    return 0
