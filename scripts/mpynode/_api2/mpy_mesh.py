"""MPyMesh (API 2.0) -- expression-driven polygon geometry generator (DG node).

A plain dependency-graph node (NOT a DAG shape). Matches Maya's
canonical pattern for polygon geometry generators -- ``polyCube``,
``polySplit``, ``polyAppend``, ``polyBevel`` are all DG nodes that
output mesh data via an ``outMesh`` plug. To make the geometry visible
in the viewport, connect ``outMesh`` to a real ``mesh`` shape's
``inMesh``.

This is the architectural pivot from mPyShape -> mPyMesh:
since the node doesn't render itself, there's no reason to inherit
from ``MPxSurfaceShape`` (which forces it into the DAG under an
auto-created transform). ``MPxNode`` is the right base class for a
DG geometry generator. The conversion removed:
 * the auto-created parent transform Maya makes for every shape
 * the ``isBounded`` / ``boundingBox`` overrides
 * the ``kSurfaceShape`` parent-class registration arg
 * the DAG-only attrs Maya inherited from MPxSurfaceShape

User expression namespace (contract -- access via ``self.X``):

Read-only inputs:
 * ``self.time`` -- TimeFloat, current frame (auto-wired from
 ``time1.outTime``). Carries the scene fps:
 ``self.time.fps`` / ``self.time.asSeconds()``.

Write outputs (REQUIRED for non-empty mesh):
 * ``self.points`` -- np.ndarray(N, 3) float64.
 * ``self.counts`` -- np.ndarray(F,) int (>= 3 per face).
 * ``self.indices`` -- np.ndarray(sum(counts),) int.

Write outputs (optional):
 * ``self.colors`` -- np.ndarray(N, 3|4) per-vertex RGB/RGBA color, OR
 (with ``self.color_indices``) np.ndarray(K, 3|4) palette indexed per
 face-vertex, OR None.
 * ``self.color_indices`` -- np.ndarray(sum(counts),) int; when set,
 ``self.colors`` is a palette and colors are per-face-vertex.
 * ``self.normals`` -- np.ndarray(N, 3) per-vertex normals, OR (with
 ``self.normal_indices``) np.ndarray(K, 3) per-face-vertex, OR None
 for Maya-computed smooth normals.
 * ``self.normal_indices`` -- np.ndarray(sum(counts),) int; when set,
 ``self.normals`` is per-face-vertex indexed.

 Colors/normals are marshalled by :mod:`mpynode._api2.geometry`; the same
 rules apply when assigning a ``geometry.Mesh`` (or any duck-typed object) to
 ``self.outMesh``.

Failure mode: any expression error -> empty mesh
shipped (no crash). Bridge logs to stderr + log_bus.

MTypeId 0x00135719 (retained from mPyShape).
"""

from __future__ import annotations

import sys

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


def _to_int_array(arr, name: str):
    """Best-effort coerce ``arr`` to a 1D int32 ndarray. Returns None
    if ``arr`` is None, empty, or unconvertible."""
    if arr is None:
        return None
    try:
        out = np.asarray(arr, dtype=np.int32).flatten()
    except Exception as exc:
        sys.stderr.write(f"[mPyMesh] {name} not int-coercible: {exc}\n")
        return None
    return out


def _to_points_array(arr):
    """Best-effort coerce ``arr`` to (N, 3) float64. Returns None
    if invalid."""
    if arr is None:
        return None
    try:
        out = np.asarray(arr, dtype=np.float64)
    except Exception:
        return None
    if out.ndim!= 2 or out.shape[1]!= 3:
        sys.stderr.write(f"[mPyMesh] points must be (N, 3); got shape {out.shape}\n")
        return None
    return out


# / merged-compute back-compat shim + public marshaller.
def build_default_output(points, counts, indices, colors=None, normals=None):
    """Default mPyMesh output marshaller (back-compat shim).

    Now a thin delegate to :class:`mpynode._api2.geometry.Mesh` -- the single
    marshalling implementation. Kept PUBLIC by design: the Output Builder's
    older auto-seeded text imports it from this module, so every existing
    caller (demos, templates, embedded ``.ma`` payloads, dnet) keeps working.
    New nodes should construct ``geometry.Mesh(...)`` directly.

    ``colors`` / ``normals``: optional per-vertex ``(N, 3|4)`` / ``(N, 3)``
    arrays (or face-vertex indexed via the dataclass). Applied by the shared
    marshaller; skipped + logged if malformed. Returns an empty data MObject
    on any failure or empty input.
    """
    return geometry.Mesh(
        points=points, counts=counts, indices=indices,
        colors=colors, normals=normals,
    ).to_mobject()


_build_mesh_data_object = build_default_output  # legacy internal-name alias
_build_mesh_data_object_public = build_default_output  # alt alias


def _looks_like_mesh_data(obj) -> bool:
    """Safety check -- validates a user write
    to ``self.outMesh`` is a kMeshData MObject."""
    if obj is None:
        return False
    try:
        import maya.api.OpenMaya as _om2
        if isinstance(obj, _om2.MObject):
            return not obj.isNull() and obj.hasFn(_om2.MFn.kMeshData)
    except Exception:
        pass
    try:
        import maya.OpenMaya as _om1
        if isinstance(obj, _om1.MObject):
            return not obj.isNull() and obj.hasFn(_om1.MFn.kMeshData)
    except Exception:
        pass
    return False


# ===========================================================================
# MPyMesh (DG node)
# ===========================================================================


class MPyMesh(om.MPxNode):
    NODE_NAME = "mPyMesh"
    NODE_ID = om.MTypeId(0x00135719)

    # No INTERNAL_VARS schema: the expression reaches plug-tree state through
    # ``self.X``, and the bridge populates the write-back slots (points /
    # counts / indices / ...) by name.

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
    _out_mesh_attr = om.MObject.kNullObj

    def __init__(self):
        super().__init__()
        self._expr_str: str = ""
        self._expr_code = compile_expression("")

    # ------------------------------------------------------------------
    # Required statics for MFnPlugin.registerNode
    # ------------------------------------------------------------------
        # Lazy-cached api1 MObject, populated by setDependentsDirty (main
        # thread). Mirrors mPyNurbsCurve -- avoids the api1
        # MFnDependencyNode(api2 MObject) crash on Maya 2026 EM-parallel.
        self._api1_mobject = None

    @staticmethod
    def creator():
        return MPyMesh()

    @staticmethod
    def initializer():
        plugs = helpers.build_internal_attrs(MPyMesh)
        MPyMesh._expression_attr = plugs["_computeSource"]
        MPyMesh._input_attrs_attr = plugs["inputs"]
        MPyMesh._output_attrs_attr = plugs["outputs"]
        MPyMesh._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyMesh._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyMesh._debug_mode_attr = plugs["debug_mode"]
        MPyMesh._profile_enabled_attr = plugs["profile_enabled"]
        MPyMesh._deep_profile_enabled_attr = plugs["deep_profile_enabled"]
        MPyMesh._watch_enabled_attr = plugs["watch_enabled"]
        MPyMesh._profile_snapshot_data_attr = plugs["profile_snapshot_data"]
        MPyMesh._watch_vars_data_attr = plugs["watch_vars_data"]

        # Hidden time input. Wrapper auto-connects time1.outTime to it.
        time_fn = om.MFnUnitAttribute()
        MPyMesh._time_in_attr = time_fn.create(
            "_timeIn", "_tin", om.MFnUnitAttribute.kTime, 0.0
        )
        time_fn.storable = True
        time_fn.keyable = False
        time_fn.readable = False
        time_fn.writable = True
        time_fn.hidden = True
        MPyMesh.addAttribute(MPyMesh._time_in_attr)

        # Output mesh plug -- the canonical mesh-data output for a Maya
        # polygon generator (matches polyCube.outMesh etc.).
        mesh_fn = om.MFnTypedAttribute()
        MPyMesh._out_mesh_attr = mesh_fn.create("outMesh", "om", om.MFnData.kMesh)
        mesh_fn.storable = False
        mesh_fn.writable = False
        mesh_fn.readable = True
        mesh_fn.hidden = False
        MPyMesh.addAttribute(MPyMesh._out_mesh_attr)

        for src in (
            MPyMesh._time_in_attr,
            MPyMesh._expression_attr,
            MPyMesh._stored_vars_data_attr,
            MPyMesh._input_attrs_attr,
            MPyMesh._output_attrs_attr,
        ):
            try:
                MPyMesh.attributeAffects(src, MPyMesh._out_mesh_attr)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # MPxNode hooks
    # ------------------------------------------------------------------

    def setInternalValue(self, plug, data_handle):
        try:
            attr = plug.attribute()
            if attr == MPyMesh._expression_attr:
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
                    filename="<mpypoly-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        return False

    def setDependentsDirty(self, plug, affected_plugs):
        """Lazy-cache api1 MObject on main
        thread. Mirrors mPyNurbsCurve."""
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
                MPyMesh._output_attrs_attr, True).asString()
            output_map = serialization.decode_attr_map(_outs) if _outs else {}
        except Exception:
            output_map = {}
        # outMesh OR any USER output (pulling one must run compute + write it).
        if attr != MPyMesh._out_mesh_attr and out_name not in output_map:
            return None

        # read time from data block.
        try:
            time_value = float(
                data_block.inputValue(MPyMesh._time_in_attr).asTime().value
            )
        except Exception:
            time_value = 0.0

        result = self._run_expression(
            time_value=time_value, data_block=data_block,
        )

        # Resolve the mesh data object in three tiers:
        #   1. a finished kMeshData MObject -> use as-is
        #   2. a Mesh dataclass / any object with points/counts/indices ->
        #      marshal structurally
        #   3. the flat self.points/counts/indices buffers (+ optional
        #      normals/colors and index maps) via the same geometry.Mesh path.
        user_mesh = result.get("outMesh")
        if user_mesh is not None and _looks_like_mesh_data(user_mesh):
            mesh_data = user_mesh
        elif geometry.is_mesh_like(user_mesh):
            mesh_data = geometry.build_mesh_data(user_mesh)
        else:
            mesh_data = geometry.Mesh(
                points=result["points"],
                counts=result["counts"],
                indices=result["indices"],
                normals=result.get("normals"),
                normal_indices=result.get("normal_indices"),
                colors=result.get("colors"),
                color_indices=result.get("color_indices"),
            ).to_mobject()

        try:
            handle = data_block.outputValue(MPyMesh._out_mesh_attr)
            handle.setMObject(mesh_data)
            data_block.setClean(plug)
        except Exception as exc:
            sys.stderr.write(f"[mPyMesh.compute] outputValue write failed: {exc}\n")

        # Commit any USER-added outputs the expression set (outMesh was
        # already written above).
        try:
            helpers.write_user_outputs(
                data_block, self.thisMObject(), output_map,
                result.get("locals_out", {}), skip=("outMesh",),
            )
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # User expression bridge (SelfProxy pattern)
    # ------------------------------------------------------------------

    def _run_expression(self, time_value: float, data_block=None) -> dict:
        """Run the user expression. Returns a dict with the mesh output
        keys (points, counts, indices, normals, normal_indices, colors,
        color_indices). On error, returns empty mesh defaults.
        """
        _EMPTY = {
            "points": None,
            "counts": None,
            "indices": None,
            "colors": None,
            "color_indices": None,
            "normals": None,
            "normal_indices": None,
        }
        if self._expr_code is None:
            return dict(_EMPTY)

        node_obj = self.thisMObject()
        fn_node = om.MFnDependencyNode(node_obj)

        stored_vars = {}
        try:
            sv_str = fn_node.findPlug(MPyMesh._stored_vars_data_attr, True).asString()
            stored_vars = _svstore.load_for_compute(node_obj, sv_str)
        except Exception:
            stored_vars = {}

        from mpynode._common.compute.self_proxy import SelfProxy

        # Pre-populated compute_locals keys give the expression a writable
        # namespace for self.points / counts / indices / colors / normals.
        # ``time`` is scene-clock state, a ``TimeFloat`` carrying the scene fps;
        # the hidden ``_timeIn`` plug is private dirty-propagation bookkeeping.
        node_obj_for_proxy = (
            self._api1_mobject if self._api1_mobject is not None
            else node_obj
        )
        # Read USER inputs DENSELY so ``self.<input>`` is a numpy array /
        # primitive inside the expression, the same contract mPyNode /
        # mPyLocator / mPyConstraint honor. Without it a vector-array input
        # falls through to PlugListProxy and ``np.asarray(...)`` sees a ragged
        # ``(index, value)`` sequence ("inhomogeneous shape"). The build-param /
        # output slots below layer ON TOP so the reserved buffer names keep
        # their write-only semantics.
        try:
            _in = fn_node.findPlug(
                MPyMesh._input_attrs_attr, True).asString()
            _input_map = serialization.decode_attr_map(_in) if _in else {}
        except Exception:
            _input_map = {}
        input_values = helpers.read_user_inputs_dict(
            node_obj, _input_map, data_block=data_block,
        )
        _compute_locals = dict(input_values)
        _compute_locals.update({
            "time": TimeFloat(time_value),
            "points": None,
            "counts": None,
            "indices": None,
            "colors": None,
            "color_indices": None,
            "normals": None,
            "normal_indices": None,
            # (merged-compute) -- pre-populate outMesh slot.
            "outMesh": None,
        })
        # Seed USER-added outputs so ``self.<out> = v`` lands in compute_locals
        # (harvested by write_user_outputs) instead of a compute-time plug
        # write, which crashes for dynamic outputs. Seed = the base-contract
        # default (C5): a scalar, or a PRE-SIZED ``(N, ...)`` buffer for an
        # array output so ``self.<out>[i] = v`` works in place.
        try:
            _uo = fn_node.findPlug(MPyMesh._output_attrs_attr, True).asString()
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
            # The mesh buffers are WRITE-only slots, marked output-scratch so a
            # user-added INPUT of the same name (a ``colors`` vector input) is
            # READABLE via ``self.<name>`` (a real plug wins on read) while
            # ``self.<name> = ...`` still feeds the buffer. ``time`` is context
            # (no backing plug) and stays a Tier-1 read.
            output_scratch_keys={
                "points",
                "counts",
                "indices",
                "colors",
                "color_indices",
                "normals",
                "normal_indices",
                "outMesh",
            },
            node_type_label="MPyMesh",
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
            log_event_name="<mpypoly-expression>",
            on_error=_on_err,
            node_obj=node_obj,
        )
        if not ok:
            if captured:
                # Base-contract policy (C10): suppress the benign transient
                # missing-plug error (EM pull during scene load / graph rebuild
                # before a declared plug resolves) exactly as base mPyNode and
                # the deformer family do, rather than spamming only this type.
                from mpynode._common.compute.base_contract import broadcast_compute_error

                broadcast_compute_error(
                    "mPyMesh",
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

        # harvest from compute_locals snapshot.
        locals_out = self_proxy.get_compute_locals()
        points = _to_points_array(locals_out.get("points"))
        counts = _to_int_array(locals_out.get("counts"), "counts")
        indices = _to_int_array(locals_out.get("indices"), "indices")

        return {
            "points": points,
            "counts": counts,
            "indices": indices,
            "colors": locals_out.get("colors"),
            "color_indices": locals_out.get("color_indices"),
            "normals": locals_out.get("normals"),
            "normal_indices": locals_out.get("normal_indices"),
            # (merged-compute) mesh output channel.
            "outMesh": locals_out.get("outMesh"),
            # Expose for compute()'s write_user_outputs (USER output commit).
            "locals_out": locals_out,
            "namespace": namespace,
        }


# ===========================================================================
# Process-wide time-change callback -- forces outMesh re-eval on frame change
# ===========================================================================


def _on_time_change(_unused_client_data):
    """Fired by Maya whenever the current time changes (timeline scrub
    or playback). For every TIME-DRIVEN mPyMesh (one with an incoming
    time connection), dirty the outMesh plug so the next consumer
    re-runs compute() and the user expression rebuilds the mesh. Time
    is opt-in, so static meshes are skipped.

    Same pattern as mPyTransform: even with ``attributeAffects(_timeIn,
    outMesh)`` declared, Maya's mesh-data plug caches across
    consecutive getAttr queries in mayapy. A direct dgdirty bypass
    forces freshness.

    Safe in any context -- failures are swallowed per-node.
    """
    try:
        from maya import cmds

        for node in cmds.ls(type=MPyMesh.NODE_NAME) or []:
            try:
                # Only dirty TIME-DRIVEN instances: time is opt-in, so a node
                # with no incoming time connection is static.
                if not cmds.listConnections(
                    node, source=True, destination=False, type="time"
                ):
                    continue
                cmds.dgdirty(node + ".outMesh")
            except Exception:
                pass
    except Exception:
        pass


def register_time_change_callback() -> int:
    """Install the time-change callback. Tracked via CALLBACK_MANAGER
    so it's removed cleanly on plugin unload."""
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API2

        cb_id = om.MEventMessage.addEventCallback("timeChanged", _on_time_change)
        return CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, OWNER_API2)
    except Exception as exc:
        sys.stderr.write(f"[mPyMesh] failed to register time-change callback: {exc}\n")
        return -1
