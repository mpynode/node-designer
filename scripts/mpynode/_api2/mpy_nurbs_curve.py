"""MPyNurbsCurve (API 2.0) -- expression-driven NURBS curve generator (DG node).

Mirrors ``mPyMesh`` -- a plain DG node (NOT a DAG shape).
Maya's canonical curve generators (``rebuildCurve``, ``offsetCurve``,
``circle``, ``curveFromMeshEdge``,...) are all DG nodes whose
``outputCurve`` plug feeds a real ``nurbsCurve`` shape's ``create``
plug. We use the long name ``outCurve`` to match the existing
``rebuildCurve.outCurve`` convention.

User expression namespace (``self.X``, ``SelfProxy`` +
``compute_locals`` contract):

Read-only inputs (pre-populated):
 * ``self.time`` -- TimeFloat, current frame (auto-wired from
 ``time1.outTime``). Carries the scene fps:
 ``self.time.fps`` / ``self.time.asSeconds()``.

Write outputs (REQUIRED for non-empty curve):
 * ``self.cvs`` -- np.ndarray(N, 3) float64 CV positions.

Write outputs (optional, with defaults):
 * ``self.degree`` -- int in (1, 2, 3, 5, 7); default 3.
 * ``self.form`` -- "open" / "closed" / "periodic"; default "open".
 * ``self.knots`` -- np.ndarray(K,) float64; default uniform.

Harvested but NOT applied:
 * ``self.rational`` -- bool; default False. The bridge reads it, but
 ``build_default_output`` takes only (cvs, knots, degree, form), so
 setting it is inert. Still seeded (and reserved) because dropping the
 seed would turn writes into persisted stored vars on old scenes.

Failure mode: any expression error -> empty curve
shipped (no crash). Bridge logs to stderr + log_bus.

MTypeId 0x0013571D.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import maya.api.OpenMaya as om
import numpy as np
from mpynode._api2 import geometry
from mpynode._api2 import helpers
from mpynode._common.compute import output_defaults
from mpynode._common.io import serialization
from mpynode._common.storedvars import stored_var_store as _svstore
from mpynode._common.plugs.promoted_types import TimeFloat
from mpynode._common.compute.expression import (
    compile_expression,
    exec_with_profile_watch,
    safe_compile_expression,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _to_points_array(arr):
    if arr is None:
        return None
    try:
        out = np.asarray(arr, dtype=np.float64)
    except Exception:
        return None
    if out.ndim!= 2 or out.shape[1]!= 3:
        sys.stderr.write(f"[mPyNurbsCurve] cvs must be (N, 3); got shape {out.shape}\n")
        return None
    return out


def build_default_output(cvs, knots, degree, form):
    """Default mPyNurbsCurve output marshaller (back-compat shim).

    Now a thin delegate to :func:`mpynode._api2.geometry.build_curve_data`
    -- the single curve-marshalling implementation. ``form`` (a string
    ``"open"``/``"closed"``/``"periodic"`` or an ``MFnNurbsCurve`` form int)
    is passed through so the ``closed`` form the periodic-only
    :class:`~mpynode._api2.geometry.NurbsCurve` can't express stays reachable;
    the periodic knot count is now correct (was ``num_cvs + 2*degree - 1``,
    which Maya rejected -- it wants ``num_cvs + degree - 1`` for both forms).

    Kept PUBLIC by design: the Output Builder's older auto-seeded text imports
    it from this module, so every existing caller keeps working. New nodes
    should construct ``geometry.NurbsCurve(...)`` directly.

    The leading-underscore alias ``_build_curve_data_object`` is kept for
    back-compat with any code that imported the old name.
    """
    return geometry.build_curve_data(
        SimpleNamespace(points=cvs, degree=degree, kv=knots, form=form)
    )


_build_curve_data_object = build_default_output  # legacy same-object alias


def _looks_like_curve_data(obj) -> bool:
    """Safety check. The user's Compute
    expression writes ``self.outCurve = <something>``. If
    ``<something>`` isn't a valid ``kNurbsCurveData`` MObject (e.g.
    they wrote ``self.outCurve = 42`` by mistake), pushing it into
    ``data_block.outputValue(...).setMObject(...)`` would crash. We
    sniff the type cheaply here and ask compute() to fall back to
    the framework marshaller if anything looks off.

    Accepts both api1 + api2 MObjects -- the user's code can call
    either ``build_default_output`` (returns api2) or some custom
    api1-flavoured helper. Both render correctly through
    ``setMObject`` because the data block accepts both.
    """
    if obj is None:
        return False
    # Try api2 first (build_default_output's actual return type).
    try:
        import maya.api.OpenMaya as _om2
        if isinstance(obj, _om2.MObject):
            return not obj.isNull() and obj.hasFn(_om2.MFn.kNurbsCurveData)
    except Exception:
        pass
    try:
        import maya.OpenMaya as _om1
        if isinstance(obj, _om1.MObject):
            return not obj.isNull() and obj.hasFn(_om1.MFn.kNurbsCurveData)
    except Exception:
        pass
    return False


# ===========================================================================
# MPyNurbsCurve (DG node)
# ===========================================================================


class MPyNurbsCurve(om.MPxNode):
    NODE_NAME = "mPyNurbsCurve"
    NODE_ID = om.MTypeId(0x0013571D)

    # Per-class MObject slots (filled by initializer).
    _expression_attr = om.MObject.kNullObj
    _input_attrs_attr = om.MObject.kNullObj
    _output_attrs_attr = om.MObject.kNullObj
    _stored_vars_list_attr = om.MObject.kNullObj
    _stored_vars_data_attr = om.MObject.kNullObj
    _debug_mode_attr = om.MObject.kNullObj
    _profile_enabled_attr = om.MObject.kNullObj
    _deep_profile_enabled_attr = om.MObject.kNullObj
    _watch_enabled_attr = om.MObject.kNullObj
    _profile_snapshot_data_attr = om.MObject.kNullObj
    _watch_vars_data_attr = om.MObject.kNullObj
    _time_in_attr = om.MObject.kNullObj
    _out_curve_attr = om.MObject.kNullObj

    def __init__(self):
        super().__init__()
        self._expr_str: str = ""
        self._expr_code = compile_expression("")
        # Lazy-cached api1 MObject, populated by setDependentsDirty (always
        # main thread). SelfProxy + PlugProxy hand an api1 MObject to api1
        # MFnDependencyNode; calling the api1 ctor with an api2 MObject is
        # undefined behaviour -- TypeError in mayapy, SIGSEGV under Maya 2026
        # GUI EM-parallel when reading ``self.<user_dynamic_attr>``.
        self._api1_mobject = None

    # ------------------------------------------------------------------
    # Required statics for MFnPlugin.registerNode
    # ------------------------------------------------------------------

    @staticmethod
    def creator():
        return MPyNurbsCurve()

    @staticmethod
    def initializer():
        plugs = helpers.build_internal_attrs(MPyNurbsCurve)
        MPyNurbsCurve._expression_attr = plugs["_computeSource"]
        MPyNurbsCurve._input_attrs_attr = plugs["inputs"]
        MPyNurbsCurve._output_attrs_attr = plugs["outputs"]
        MPyNurbsCurve._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyNurbsCurve._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyNurbsCurve._debug_mode_attr = plugs["debug_mode"]
        MPyNurbsCurve._profile_enabled_attr = plugs["profile_enabled"]
        MPyNurbsCurve._deep_profile_enabled_attr = plugs["deep_profile_enabled"]
        MPyNurbsCurve._watch_enabled_attr = plugs["watch_enabled"]
        MPyNurbsCurve._profile_snapshot_data_attr = plugs["profile_snapshot_data"]
        MPyNurbsCurve._watch_vars_data_attr = plugs["watch_vars_data"]

        time_fn = om.MFnUnitAttribute()
        MPyNurbsCurve._time_in_attr = time_fn.create(
            "_timeIn", "_tin", om.MFnUnitAttribute.kTime, 0.0
        )
        time_fn.storable = True
        time_fn.keyable = False
        time_fn.readable = False
        time_fn.writable = True
        time_fn.hidden = True
        MPyNurbsCurve.addAttribute(MPyNurbsCurve._time_in_attr)

        # The canonical NURBS-curve output plug (matches rebuildCurve etc).
        curve_fn = om.MFnTypedAttribute()
        MPyNurbsCurve._out_curve_attr = curve_fn.create(
            "outCurve", "oc", om.MFnData.kNurbsCurve
        )
        curve_fn.storable = False
        curve_fn.writable = False
        curve_fn.readable = True
        curve_fn.hidden = False
        MPyNurbsCurve.addAttribute(MPyNurbsCurve._out_curve_attr)

        for src in (
            MPyNurbsCurve._time_in_attr,
            MPyNurbsCurve._expression_attr,
            MPyNurbsCurve._stored_vars_data_attr,
            MPyNurbsCurve._input_attrs_attr,
            MPyNurbsCurve._output_attrs_attr,
        ):
            try:
                MPyNurbsCurve.attributeAffects(src, MPyNurbsCurve._out_curve_attr)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # MPxNode hooks
    # ------------------------------------------------------------------

    def setInternalValue(self, plug, data_handle):
        try:
            attr = plug.attribute()
            if attr == MPyNurbsCurve._expression_attr:
                new_src = data_handle.asString()
                self._expr_str = new_src
                node_name = ""
                try:
                    node_name = om.MFnDependencyNode(self.thisMObject()).name()
                except Exception:
                    pass
                code = safe_compile_expression(
                    new_src,
                    node_name=node_name,
                    filename="<mpycurve-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        return False

    def setDependentsDirty(self, plug, affected_plugs):
        """Lazy-cache an api1 MObject
        for this node on the main thread. ``setDependentsDirty`` is
        documented main-thread-only by Maya, so calling
        ``MFnDependencyNode.name()`` + ``MSelectionList.add(name)``
        here is safe -- whereas doing the same bridge inside
        ``compute()`` (which Maya 2026 EM-parallel may dispatch on a
        worker thread) is not.

        The cached api1 MObject is then handed to SelfProxy in
        ``_run_expression`` / ``_run_output_builder`` so PlugProxy's
        api1 ``MFnDependencyNode(node_obj).attribute(name)`` call
        succeeds when the user expression reads a dynamic attr like
        ``self.offset``."""
        if self._api1_mobject is None:
            try:
                import maya.api.OpenMaya as _om2
                import maya.OpenMaya as _om1
                name = _om2.MFnDependencyNode(self.thisMObject()).name()
                sel = _om1.MSelectionList()
                sel.add(name)
                m = _om1.MObject()
                sel.getDependNode(0, m)
                if not m.isNull():
                    self._api1_mobject = m
            except Exception:
                # Cache stays None; SelfProxy will fall back to its
                # name-bridge (also main-thread-safe).
                pass
        from mpynode._common.plugs import dirty_affects

        dirty_affects.declare_user_affects(
            self.thisMObject(),
            plug,
            affected_plugs,
            type(self)._input_attrs_attr,
            type(self)._output_attrs_attr,
        )
        return None

    def compute(self, plug, data_block):
        # C1: defer while a scene is being READ -- the EM can pull an output
        # mid-load, before this node's dynamic attrs are restored, making the
        # expression raise a spurious "self has no plug named ..." error.
        # Returning leaves the plug dirty so Maya recomputes once whole.
        try:
            import maya.OpenMaya as _om1

            if _om1.MFileIO.isReadingFile():
                return
        except Exception:
            pass

        try:
            attr = plug.attribute()
        except Exception:
            return None
        try:
            out_name = om.MFnAttribute(attr).name
        except Exception:
            out_name = ""
        try:
            _outs = om.MFnDependencyNode(self.thisMObject()).findPlug(
                MPyNurbsCurve._output_attrs_attr, True).asString()
            output_map = serialization.decode_attr_map(_outs) if _outs else {}
        except Exception:
            output_map = {}
        # outCurve OR any USER output (pulling one must run compute + write it).
        if attr != MPyNurbsCurve._out_curve_attr and out_name not in output_map:
            return None

        # Read time from the DG data block, not ``cmds.currentTime`` -- cmds is
        # documented main-thread-only, while data_block is bound to the current
        # evaluation context on whichever thread compute is dispatched.
        try:
            time_value = float(
                data_block.inputValue(MPyNurbsCurve._time_in_attr).asTime().value
            )
        except Exception:
            time_value = 0.0

        result = self._run_expression(
            time_value=time_value, data_block=data_block,
        )

        # If the Compute expression wrote ``self.outCurve = <data_obj>``, use
        # it. That write landed in compute_locals because ``outCurve: None`` is
        # pre-seeded there, so SelfProxy.__setattr__ takes the locals path
        # rather than the plug-write path (which crashes on the api1/api2
        # datablock mismatch). Otherwise fall back to the framework marshaller,
        # the same safety net used when Compute errors out.
        #
        # Three-tier resolution (mirrors mPyMesh):
        #   1. finished kNurbsCurveData MObject -> use as-is
        #   2. NurbsCurve dataclass / any object with .points -> marshal
        #   3. flat self.cvs/knots/degree/form buffers -> build_default_output
        user_curve = result.get("outCurve")
        if user_curve is not None and _looks_like_curve_data(user_curve):
            curve_data = user_curve
        elif geometry.is_curve_like(user_curve):
            curve_data = geometry.build_curve_data(user_curve)
        else:
            curve_data = build_default_output(
                result["cvs"],
                result["knots"],
                result["degree"],
                result["form"],
            )

        try:
            handle = data_block.outputValue(MPyNurbsCurve._out_curve_attr)
            handle.setMObject(curve_data)
            data_block.setClean(plug)
        except Exception as exc:
            sys.stderr.write(f"[mPyNurbsCurve.compute] outputValue write failed: {exc}\n")

        # Commit any USER-added outputs the expression set (outCurve was
        # already written above).
        try:
            helpers.write_user_outputs(
                data_block, self.thisMObject(), output_map,
                result.get("locals_out", {}), skip=("outCurve",),
            )
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Output Builder bridge
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # User expression bridge
    # ------------------------------------------------------------------

    def _run_expression(self, time_value: float, data_block=None) -> dict:
        _EMPTY = {
            "cvs": None,
            "knots": None,
            "degree": 3,
            "form": "open",
            "rational": False,
        }
        if self._expr_code is None:
            return dict(_EMPTY)

        # Prefer the api1 MObject cached by setDependentsDirty (main thread) so
        # PlugProxy's api1 MFnDependencyNode call inside ``self.<dynamic_attr>``
        # lookups avoids the api1-ctor-with-api2-arg crash. Falling back to the
        # api2 MObject is safe: _ensure_api1_mobject bridges it on the main
        # thread, or short-circuits on a worker thread.
        node_obj_for_proxy = (
            self._api1_mobject if self._api1_mobject is not None
            else self.thisMObject()
        )
        node_obj = self.thisMObject()  # for findPlug below
        fn_node = om.MFnDependencyNode(node_obj)

        stored_vars = {}
        try:
            # Reading the stored-vars plug via api2 findPlug is documented
            # safe inside compute() (the MPxNode reference is to ``this``).
            sv_str = fn_node.findPlug(MPyNurbsCurve._stored_vars_data_attr, True).asString()
            stored_vars = _svstore.load_for_compute(node_obj, sv_str)
        except Exception:
            stored_vars = {}

        from mpynode._common.compute.self_proxy import SelfProxy

        # ``time`` is scene-clock state -- a ``TimeFloat`` carrying the scene
        # fps. The hidden ``_timeIn`` plug is private dirty-propagation
        # bookkeeping.
        #
        # The data_block is passed to SelfProxy/PlugProxy so dynamic user-input
        # reads route through ``data_block.inputValue(plug)`` (the EM-safe path)
        # rather than ``MPlug.asXxx`` / ``cmds.getAttr``. USER inputs are seeded
        # DENSELY so ``self.<input>`` is a numpy array / primitive, the same
        # contract mPyNode / mPyLocator / mPyConstraint honor: without it a
        # vector-array input falls through to PlugListProxy and
        # ``np.asarray(...)`` sees a ragged ``(index, value)`` sequence
        # ("inhomogeneous shape"). The build-param / output slots below layer ON
        # TOP so reserved names (cvs/knots/degree/form/rational/outCurve) keep
        # their semantics while a plain input survives as dense numpy.
        try:
            _in = fn_node.findPlug(
                MPyNurbsCurve._input_attrs_attr, True).asString()
            _input_map = serialization.decode_attr_map(_in) if _in else {}
        except Exception:
            _input_map = {}
        input_values = helpers.read_user_inputs_dict(
            node_obj, _input_map, data_block=data_block,
        )
        _compute_locals = dict(input_values)
        _compute_locals.update({
            "time": TimeFloat(time_value),
            "cvs": None,
            "knots": None,
            "degree": 3,
            "form": "open",
            "rational": False,
            # Pre-seeding ``outCurve`` routes a user's
            # ``self.outCurve = ...`` write into compute_locals via
            # SelfProxy.__setattr__ Tier 1, NOT the plug-tree write path -- that
            # path calls ``data_block.outputValue(api1_plug)``, the api1/api2
            # mismatch that crashes Maya. This is what makes
            # ``self.outCurve = build_default_output(...)`` safe in Compute.
            "outCurve": None,
        })
        # Seed USER-added outputs for the same reason (mirrors mPyFile). Seed =
        # the base-contract default (C5): a scalar, or a PRE-SIZED ``(N, ...)``
        # buffer for an array output so ``self.<out>[i] = v`` works in place
        # instead of raising on a bare ``None``.
        try:
            _uo = fn_node.findPlug(MPyNurbsCurve._output_attrs_attr, True).asString()
            _user_out_map = serialization.decode_attr_map(_uo) if _uo else {}
        except Exception:
            _user_out_map = {}
        for _out_name, _out_seed in output_defaults.seed_user_output_defaults_api2(
                fn_node, _user_out_map).items():
            _compute_locals.setdefault(_out_name, _out_seed)
        self_proxy = SelfProxy(
            node_obj_for_proxy,
            datablock=data_block,
            user_storage=stored_vars,
            compute_locals=_compute_locals,
            # The PURE write-only buffers (None-seeded) are output-scratch, so
            # a user-added INPUT of the same name is READABLE via
            # ``self.<name>`` (a real plug wins on read) while
            # ``self.<name> = ...`` still feeds the slot. The build-param
            # DEFAULTS (degree/form/rational) are deliberately NOT scratch --
            # that would create a read != build split where self.degree reads an
            # input while the curve builds at the unwritten default. ``time`` is
            # context (no backing plug) and stays a Tier-1 read.
            output_scratch_keys={
                "cvs",
                "knots",
                "outCurve",
            },
            node_type_label="MPyNurbsCurve",
        )

        import builtins as _builtins

        namespace = {
            "__builtins__": _builtins,
            "self": self_proxy,
        }

        # Sync compiled code with the _computeSource plug so a DUPLICATED
        # node runs its expression (see helpers.ensure_expr_code).
        helpers.ensure_expr_code(self, type(self)._expression_attr)

        captured: list = []

        def _on_err(msg):
            captured.append(msg)

        ok = exec_with_profile_watch(
            self._expr_code,
            namespace,
            log_event_name="<mpycurve-expression>",
            on_error=_on_err,
            node_obj=node_obj,
        )
        if not ok:
            if captured:
                # Base-contract policy (C10): suppress the benign transient
                # missing-plug error (declared-but-unresolved plug pulled mid
                # scene-load), surface everything else.
                from mpynode._common.compute.base_contract import broadcast_compute_error

                broadcast_compute_error(
                    "mPyNurbsCurve",
                    captured[0],
                    declared_names=set(_input_map) | set(_user_out_map),
                )
            return dict(_EMPTY)

        # Stored-var write-back goes to the in-memory store (thread-safe, no DG
        # access), so it needs no main-thread gate. Flushed to the plug on save.
        storage_diff = self_proxy.diff_storage()
        if storage_diff:
            new_stored = dict(stored_vars)
            for k, v in storage_diff.items():
                if v is None:
                    new_stored.pop(k, None)
                else:
                    new_stored[k] = v
            _svstore.set_for_compute(node_obj, new_stored)

        locals_out = self_proxy.get_compute_locals()
        return {
            "cvs": _to_points_array(locals_out.get("cvs")),
            "knots": locals_out.get("knots"),
            "degree": locals_out.get("degree", 3),
            "form": locals_out.get("form", "open"),
            "rational": bool(locals_out.get("rational", False)),
            # Surface any ``self.outCurve = ...`` the Compute expression wrote
            # so compute() can use it. None = fall back to the marshaller.
            "outCurve": locals_out.get("outCurve"),
            # Expose for compute()'s write_user_outputs (USER output commit).
            "locals_out": locals_out,
            "namespace": namespace,
        }


# ===========================================================================
# Process-wide time-change callback -- forces outCurve re-eval on frame change
# ===========================================================================


def _on_time_change(_unused_client_data):
    """Dirty TIME-DRIVEN mPyNurbsCurve outCurve plugs on every frame change.

    Same mayapy caching workaround as mPyMesh: Maya caches typed-data
    plugs across consecutive getAttr queries; an explicit dgdirty on
    timeChanged forces a fresh compute the next time the plug is read.

    Time is opt-in, so this only touches instances that actually have an
    incoming time connection. Static curves are skipped to avoid a
    per-frame re-evaluation they don't need.
    """
    try:
        from maya import cmds

        for node in cmds.ls(type=MPyNurbsCurve.NODE_NAME) or []:
            try:
                # Only dirty TIME-DRIVEN instances (an incoming connection from
                # a time node). A static curve doesn't depend on the frame, so
                # re-evaluating it every frame is wasted work.
                if cmds.listConnections(
                    node, source=True, destination=False, type="time"
                ):
                    cmds.dgdirty(node + ".outCurve")
            except Exception:
                pass
    except Exception:
        pass


def register_time_change_callback() -> int:
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API2

        cb_id = om.MEventMessage.addEventCallback("timeChanged", _on_time_change)
        return CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, OWNER_API2)
    except Exception as exc:
        sys.stderr.write(f"[mPyNurbsCurve] failed to register time-change callback: {exc}\n")
        return -1
