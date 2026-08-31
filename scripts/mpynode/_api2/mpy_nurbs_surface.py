"""MPyNurbsSurface (API 2.0) -- expression-driven NURBS surface generator
(DG node).

Mirrors ``mPyMesh`` / ``mPyNurbsCurve`` -- a plain DG node, NOT a DAG
shape. Maya\'s canonical surface generators (``loft``, ``revolve``,
``birail`` etc.) all output an ``outputSurface`` plug whose data is
consumed by a downstream ``nurbsSurface`` shape\'s ``create`` plug.
We follow ``loft``\'s convention and use the short long-name
``outSurface``.

User expression namespace (``self.X``; SelfProxy + compute_locals contract):

Read-only inputs (pre-populated):
  * ``self.time``  -- TimeFloat, current frame; carries the scene fps
    (``self.time.fps`` / ``self.time.asSeconds()``).

Write outputs (REQUIRED for non-empty surface):
  * ``self.cvs`` -- either
        - ``np.ndarray(num_cvs_u, num_cvs_v, 3)`` (preferred), OR
        - ``np.ndarray(num_cvs_u * num_cvs_v, 3)`` flat, plus
          ``self.num_cvs_u`` + ``self.num_cvs_v``.
    Flat ordering is **u-fastest, then v** (row-major in u).

Write outputs (optional, with defaults):
  * ``self.degree_u`` / ``self.degree_v`` -- int (1, 2, 3, 5, 7);
    default 3 each.
  * ``self.form_u`` / ``self.form_v`` -- "open" / "closed" /
    "periodic"; default "open" each.
  * ``self.knots_u`` / ``self.knots_v`` -- np.ndarray(K,) float64;
    default uniform.

Failure mode: any expression error -> empty surface (framework default).

MTypeId 0x0013571E.
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


# / merged-compute back-compat shim + public marshaller.
def build_default_output(
    cvs, num_cvs_u, num_cvs_v,
    knots_u=None, knots_v=None,
    degree_u=3, degree_v=3,
    form_u="open", form_v="open",
):
    """Default mPyNurbsSurface output marshaller (back-compat shim).

    Now a thin delegate to :func:`mpynode._api2.geometry.build_surface_data`
    -- the single surface-marshalling implementation. ``cvs`` may be a
    ``(n_u, n_v, 3)`` grid or a ``(n_u*n_v, 3)`` flat array (num_cvs_u /
    num_cvs_v required for the flat form). ``form_u`` / ``form_v`` (string or
    ``MFnNurbsSurface`` form int) pass through so the ``closed`` form the
    periodic-only :class:`~mpynode._api2.geometry.NurbsSurface` can't express
    stays reachable; the periodic knot count is now correct.

    Kept PUBLIC by design: the Output Builder's older auto-seeded text imports
    it from this module, so every existing caller keeps working. New nodes
    should construct ``geometry.NurbsSurface(...)`` directly.
    """
    return geometry.build_surface_data(SimpleNamespace(
        points=cvs, num_u=num_cvs_u, num_v=num_cvs_v,
        kv_u=knots_u, kv_v=knots_v,
        degree_u=degree_u, degree_v=degree_v,
        form_u=form_u, form_v=form_v,
    ))


# Legacy same-object aliases (tests + old imports reference these names).
_build_surface_data_object = build_default_output
_build_default_surface_output = build_default_output


def _looks_like_surface_data(obj) -> bool:
    """Safety check -- validates a user write
    to ``self.outSurface`` is a kNurbsSurfaceData MObject. Same shape
    as mPyNurbsCurve._looks_like_curve_data."""
    if obj is None:
        return False
    try:
        import maya.api.OpenMaya as _om2
        if isinstance(obj, _om2.MObject):
            return not obj.isNull() and obj.hasFn(_om2.MFn.kNurbsSurfaceData)
    except Exception:
        pass
    try:
        import maya.OpenMaya as _om1
        if isinstance(obj, _om1.MObject):
            return not obj.isNull() and obj.hasFn(_om1.MFn.kNurbsSurfaceData)
    except Exception:
        pass
    return False


# ===========================================================================
# MPyNurbsSurface (DG node)
# ===========================================================================


class MPyNurbsSurface(om.MPxNode):
    NODE_NAME = "mPyNurbsSurface"
    NODE_ID = om.MTypeId(0x0013571E)

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
    _out_surface_attr = om.MObject.kNullObj

    def __init__(self):
        super().__init__()
        self._expr_str: str = ""
        self._expr_code = compile_expression("")
        # Lazy-cached api1 MObject, populated by setDependentsDirty (always
        # main thread). Mirrors mPyNurbsCurve -- avoids the api1
        # MFnDependencyNode(api2 MObject) crash when expressions read dynamic
        # input attrs on EM worker threads.
        self._api1_mobject = None

    @staticmethod
    def creator():
        return MPyNurbsSurface()

    @staticmethod
    def initializer():
        plugs = helpers.build_internal_attrs(MPyNurbsSurface)
        MPyNurbsSurface._expression_attr = plugs["_computeSource"]
        MPyNurbsSurface._input_attrs_attr = plugs["inputs"]
        MPyNurbsSurface._output_attrs_attr = plugs["outputs"]
        MPyNurbsSurface._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyNurbsSurface._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyNurbsSurface._debug_mode_attr = plugs["debug_mode"]
        MPyNurbsSurface._profile_enabled_attr = plugs["profile_enabled"]
        MPyNurbsSurface._deep_profile_enabled_attr = plugs["deep_profile_enabled"]
        MPyNurbsSurface._watch_enabled_attr = plugs["watch_enabled"]
        MPyNurbsSurface._profile_snapshot_data_attr = plugs["profile_snapshot_data"]
        MPyNurbsSurface._watch_vars_data_attr = plugs["watch_vars_data"]

        time_fn = om.MFnUnitAttribute()
        MPyNurbsSurface._time_in_attr = time_fn.create(
            "_timeIn", "_tin", om.MFnUnitAttribute.kTime, 0.0
        )
        time_fn.storable = True
        time_fn.keyable = False
        time_fn.readable = False
        time_fn.writable = True
        time_fn.hidden = True
        MPyNurbsSurface.addAttribute(MPyNurbsSurface._time_in_attr)

        surf_fn = om.MFnTypedAttribute()
        MPyNurbsSurface._out_surface_attr = surf_fn.create(
            "outSurface", "os", om.MFnData.kNurbsSurface
        )
        surf_fn.storable = False
        surf_fn.writable = False
        surf_fn.readable = True
        surf_fn.hidden = False
        MPyNurbsSurface.addAttribute(MPyNurbsSurface._out_surface_attr)

        for src in (
            MPyNurbsSurface._time_in_attr,
            MPyNurbsSurface._expression_attr,
            MPyNurbsSurface._stored_vars_data_attr,
            MPyNurbsSurface._input_attrs_attr,
            MPyNurbsSurface._output_attrs_attr,
        ):
            try:
                MPyNurbsSurface.attributeAffects(src, MPyNurbsSurface._out_surface_attr)
            except Exception:
                pass

    def setInternalValue(self, plug, data_handle):
        try:
            attr = plug.attribute()
            if attr == MPyNurbsSurface._expression_attr:
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
                    filename="<mpysurface-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        return False

    def setDependentsDirty(self, plug, affected_plugs):
        """Lazy-cache an api1 MObject
        on the main thread so PlugProxy reads on dynamic user attrs
        don't crash on EM worker threads. Mirrors mPyNurbsCurve."""
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
                MPyNurbsSurface._output_attrs_attr, True).asString()
            output_map = serialization.decode_attr_map(_outs) if _outs else {}
        except Exception:
            output_map = {}
        # outSurface OR any USER output (pulling one must run compute + write).
        if attr != MPyNurbsSurface._out_surface_attr and out_name not in output_map:
            return None

        # Read time from the data block, not ``cmds.currentTime``.
        try:
            time_value = float(
                data_block.inputValue(MPyNurbsSurface._time_in_attr).asTime().value
            )
        except Exception:
            time_value = 0.0

        result = self._run_expression(
            time_value=time_value, data_block=data_block,
        )

        # Use any ``self.outSurface = ...`` the Compute expression wrote; else
        # fall back to the framework marshaller over the cvs / shape fields.
        # Three-tier resolution (mirrors mPyMesh / mPyNurbsCurve):
        #   1. finished kNurbsSurfaceData MObject -> use as-is
        #   2. NurbsSurface dataclass / any object with .points -> marshal
        #   3. flat self.cvs/knots/degree/form buffers -> build_default_output
        user_surface = result.get("outSurface")
        if user_surface is not None and _looks_like_surface_data(user_surface):
            surface_data = user_surface
        elif geometry.is_surface_like(user_surface):
            surface_data = geometry.build_surface_data(user_surface)
        else:
            surface_data = build_default_output(
                result["cvs"], result.get("num_cvs_u"), result.get("num_cvs_v"),
                result.get("knots_u"), result.get("knots_v"),
                result.get("degree_u", 3), result.get("degree_v", 3),
                result.get("form_u", "open"), result.get("form_v", "open"),
            )

        try:
            handle = data_block.outputValue(MPyNurbsSurface._out_surface_attr)
            handle.setMObject(surface_data)
            data_block.setClean(plug)
        except Exception as exc:
            sys.stderr.write(f"[mPyNurbsSurface.compute] outputValue write failed: {exc}\n")

        # Commit any USER-added outputs the expression set (outSurface was
        # already written above).
        try:
            helpers.write_user_outputs(
                data_block, self.thisMObject(), output_map,
                result.get("locals_out", {}), skip=("outSurface",),
            )
        except Exception:
            pass
        return None

    def _run_expression(self, time_value: float, data_block=None) -> dict:
        _EMPTY = {
            "cvs": None,
            "num_cvs_u": None,
            "num_cvs_v": None,
            "knots_u": None,
            "knots_v": None,
            "degree_u": 3,
            "degree_v": 3,
            "form_u": "open",
            "form_v": "open",
        }
        if self._expr_code is None:
            return dict(_EMPTY)

        node_obj = self.thisMObject()
        fn_node = om.MFnDependencyNode(node_obj)

        stored_vars = {}
        try:
            sv_str = fn_node.findPlug(MPyNurbsSurface._stored_vars_data_attr, True).asString()
            stored_vars = _svstore.load_for_compute(node_obj, sv_str)
        except Exception:
            stored_vars = {}

        from mpynode._common.compute.self_proxy import SelfProxy

        # ``time`` is scene-clock state, a ``TimeFloat`` carrying the scene fps;
        # ``_timeIn`` is private dirty-propagation bookkeeping.
        node_obj_for_proxy = (
            self._api1_mobject if self._api1_mobject is not None
            else node_obj
        )
        # Read USER inputs DENSELY so ``self.<input>`` is a numpy array /
        # primitive inside the expression, the same contract mPyNode /
        # mPyLocator / mPyConstraint honor. Without it a vector-array input
        # falls through to PlugListProxy and ``np.asarray(...)`` sees a ragged
        # ``(index, value)`` sequence ("inhomogeneous shape"). The build-param /
        # output slots below layer ON TOP so reserved names keep their meaning.
        try:
            _in = fn_node.findPlug(
                MPyNurbsSurface._input_attrs_attr, True).asString()
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
            "num_cvs_u": None,
            "num_cvs_v": None,
            "knots_u": None,
            "knots_v": None,
            "degree_u": 3,
            "degree_v": 3,
            "form_u": "open",
            "form_v": "open",
            # Pre-populating outSurface routes a user's
            # ``self.outSurface = ...`` write through SelfProxy's locals Tier-1
            # path instead of the unsafe plug-tree write path.
            "outSurface": None,
        })
        # Seed USER-added outputs for the same reason (mirrors mPyFile). Seed =
        # the base-contract default (C5): a scalar, or a PRE-SIZED ``(N, ...)``
        # buffer for an array output so ``self.<out>[i] = v`` works in place.
        try:
            _uo = fn_node.findPlug(MPyNurbsSurface._output_attrs_attr, True).asString()
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
            # The PURE write-only buffers (None-seeded) are output-scratch so a
            # user-added INPUT of the same name is READABLE via
            # ``self.<name>`` (a real plug wins on read) while
            # ``self.<name> = ...`` still feeds the slot. The build-param
            # DEFAULTS (degree_u/v, form_u/v) are deliberately NOT scratch --
            # see mpy_nurbs_curve.py. ``time`` is context and stays Tier-1.
            output_scratch_keys={
                "cvs",
                "num_cvs_u",
                "num_cvs_v",
                "knots_u",
                "knots_v",
                "outSurface",
            },
            node_type_label="MPyNurbsSurface",
        )

        import builtins as _builtins

        namespace = {"__builtins__": _builtins, "self": self_proxy}

        # Sync compiled code with the _computeSource plug so a DUPLICATED
        # node runs its expression (see helpers.ensure_expr_code).
        helpers.ensure_expr_code(self, type(self)._expression_attr)

        captured: list = []

        def _on_err(msg):
            captured.append(msg)

        ok = exec_with_profile_watch(
            self._expr_code,
            namespace,
            log_event_name="<mpysurface-expression>",
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
                    "mPyNurbsSurface",
                    captured[0],
                    declared_names=set(_input_map) | set(_user_out_map),
                )
            return dict(_EMPTY)

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
            "cvs": locals_out.get("cvs"),
            "num_cvs_u": locals_out.get("num_cvs_u"),
            "num_cvs_v": locals_out.get("num_cvs_v"),
            "knots_u": locals_out.get("knots_u"),
            "knots_v": locals_out.get("knots_v"),
            "degree_u": locals_out.get("degree_u", 3),
            "degree_v": locals_out.get("degree_v", 3),
            "form_u": locals_out.get("form_u", "open"),
            "form_v": locals_out.get("form_v", "open"),
            # (merged-compute) surface output channel.
            "outSurface": locals_out.get("outSurface"),
            # Expose for compute()'s write_user_outputs (USER output commit).
            "locals_out": locals_out,
            "namespace": namespace,
        }


# ===========================================================================
# Process-wide time-change callback
# ===========================================================================


def _on_time_change(_unused_client_data):
    """Dirty TIME-DRIVEN mPyNurbsSurface outSurface plugs on frame change.

    Time is opt-in, so only instances with an incoming time connection
    are dirtied; static surfaces are skipped."""
    try:
        from maya import cmds

        for node in cmds.ls(type=MPyNurbsSurface.NODE_NAME) or []:
            try:
                # Only dirty TIME-DRIVEN instances: time is opt-in, so a node
                # with no incoming time connection is static.
                if not cmds.listConnections(
                    node, source=True, destination=False, type="time"
                ):
                    continue
                cmds.dgdirty(node + ".outSurface")
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
        sys.stderr.write(f"[mPyNurbsSurface] failed to register time-change callback: {exc}\n")
        return -1
