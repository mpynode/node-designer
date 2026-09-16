"""Compute -- the generic compute path., condensed:

 run_generic_compute(node_obj, datablock, output_plug, *,
 geom_iter=None, multi_index=None,
 node_class=None) -> bool

 1. Build SelfProxy(node_obj, datablock=datablock,
 geom_iter=geom_iter, compute_ctx={...}).
 2. Allocate writable output handles for each output geometry plug
 (eager copy from corresponding input -- Section 5.1).
 3. Read the node's _expression code object (cached, compiled).
 4. Read the node's _initSource namespace from the registry.
 5. exec(code, namespace={"__builtins__":..., "self": sp,
 **init_ns}).
 6. Commit phase:
 a. For each touched output handle: push via setAllPositions /
 setMObject (Section 5.3).
 b. For each dirty numeric/string/enum writable plug: push via
 MDataBlock.outputValue.set...(value).
 c. Diff user storage; if dirty, write _storedVarsData via
 cmds.setAttr.
 7. Return True on success; False with stderr + log_bus message
 on exception.

Per-node-type plug-tree specs (Section 9) are read from
``OUTPUT_GEOMETRY_PLUG`` and ``INPUT_GEOMETRY_PLUG`` class-level
attributes on the MPx subclass, OR from a passed-in ``node_class``
argument when the per-class attrs aren't yet declared.

only wires mPyDeformer; the remaining 12 node types still
go through their legacy compute paths until F.1+ migrates them.
"""

from __future__ import annotations

import sys
import traceback
from typing import Optional

import maya.OpenMaya as om
import maya.OpenMayaMPx as ommpx

from mpynode._common.plugs.mfn_handles import (
    MFnMeshHandle,
    MFnNurbsCurveHandle,
    MFnNurbsSurfaceHandle,
    MFnLatticeHandle,
    allocate_writable_mesh_from_source,
    allocate_writable_curve_from_source,
    allocate_writable_surface_from_source,
    allocate_writable_lattice_from_source,
)


# ---- Output-handle allocation (Section 5.1) ----


def _read_input_geometry_data(block, multi_index):
    """Return the source geometry MObject from the deformer family's
    input[multi_index].inputGeometry plug, plus a label like 'mesh'/
    'curve'/'surface'/'lattice'/'unknown'.
    """
    input_attr      = ommpx.cvar.MPxGeometryFilter_input
    input_geom_attr = ommpx.cvar.MPxGeometryFilter_inputGeom

    try:
        in_array = block.outputArrayValue(input_attr)
        in_array.jumpToElement(int(multi_index))
        in_handle   = in_array.outputValue()
        geom_handle = in_handle.child(input_geom_attr)
    except Exception:
        return None, "unknown"

    # Try mesh first.
    try:
        mesh = geom_handle.asMesh()
        if mesh is not None and not mesh.isNull():
            return mesh, "mesh"
    except Exception:
        pass
    try:
        crv = geom_handle.asNurbsCurve()
        if crv is not None and not crv.isNull():
            return crv, "curve"
    except Exception:
        pass
    try:
        srf = geom_handle.asNurbsSurface()
        if srf is not None and not srf.isNull():
            return srf, "surface"
    except Exception:
        pass
    # API 1.0 MDataHandle has no asLattice / asLatticeData -- go generic.
    try:
        mobj = geom_handle.data()
        if mobj is not None and not mobj.isNull():
            if mobj.hasFn(om.MFn.kLatticeData):
                return mobj, "lattice"
            if mobj.hasFn(om.MFn.kMeshData):
                return mobj, "mesh"
            if mobj.hasFn(om.MFn.kNurbsCurveData):
                return mobj, "curve"
            if mobj.hasFn(om.MFn.kNurbsSurfaceData):
                return mobj, "surface"
    except Exception:
        pass
    return None, "unknown"


def allocate_deformer_output_handle(
    block, multi_index, plug_short_name="outputGeometry"
):
    """Eager-copy the deformer's input geometry into a fresh MObject
    and wrap it in the matching ``MFn*Handle``.

    dispatches on input geometry apiType to support mesh,
    NURBS curve, NURBS surface, and lattice geometries.

    Returns ``(handle, fresh_mobject, vert_count)``. ``vert_count`` is
    the input geometry's element count (verts / CVs / lattice points)
    -- the commit phase uses this to detect topology mismatches.
    """
    src_mobject, kind = _read_input_geometry_data(block, multi_index)

    if kind == "mesh":
        fresh_mfn, fresh_data = allocate_writable_mesh_from_source(src_mobject)
        handle = MFnMeshHandle(
            fresh_mfn, fresh_data,
            plug_name=plug_short_name, plug_index=int(multi_index),
        )
        try:
            vcount = int(fresh_mfn.numVertices())
        except Exception:
            vcount = 0
        return handle, fresh_data, vcount

    if kind == "curve":
        fresh_mfn, fresh_data = allocate_writable_curve_from_source(src_mobject)
        handle = MFnNurbsCurveHandle(
            fresh_mfn, fresh_data,
            plug_name=plug_short_name, plug_index=int(multi_index),
        )
        try:
            vcount = int(fresh_mfn.numCVs())
        except Exception:
            vcount = 0
        return handle, fresh_data, vcount

    if kind == "surface":
        fresh_mfn, fresh_data = allocate_writable_surface_from_source(src_mobject)
        handle = MFnNurbsSurfaceHandle(
            fresh_mfn, fresh_data,
            plug_name=plug_short_name, plug_index=int(multi_index),
        )
        try:
            u      = int(fresh_mfn.numCVsInU())
            v      = int(fresh_mfn.numCVsInV())
            vcount = u * v
        except Exception:
            vcount = 0
        return handle, fresh_data, vcount

    if kind == "lattice":
        fresh_mfn, fresh_data = allocate_writable_lattice_from_source(src_mobject)
        if fresh_mfn is None:
            # No lattice support in this Maya build -- fall back to an empty
            # mesh handle so the compute path doesn't crash.
            fresh_mfn, fresh_data = allocate_writable_mesh_from_source(None)
            handle = MFnMeshHandle(
                fresh_mfn, fresh_data,
                plug_name=plug_short_name, plug_index=int(multi_index),
            )
            return handle, fresh_data, 0
        handle = MFnLatticeHandle(
            fresh_mfn, fresh_data,
            plug_name=plug_short_name, plug_index=int(multi_index),
        )
        try:
            vcount = int(fresh_mfn.numLatticePoints())
        except Exception:
            try:
                vcount = int(fresh_mfn.numPoints())
            except Exception:
                vcount = 0
        return handle, fresh_data, vcount

    # Unknown / no input -- empty mesh handle as a safe default.
    fresh_mfn, fresh_data = allocate_writable_mesh_from_source(None)
    handle = MFnMeshHandle(
        fresh_mfn, fresh_data,
        plug_name=plug_short_name, plug_index=int(multi_index),
    )
    return handle, fresh_data, 0


# ---- Commit phase (Section 5.3) ----


def _handle_actual_count(handle):
    """Return the current point/CV count on a handle, dispatching on
    the underlying MFn type."""
    try:
        if isinstance(handle, MFnMeshHandle):
            return int(handle.numVertices())
        if isinstance(handle, MFnNurbsCurveHandle):
            return int(handle.numCVs())
        if isinstance(handle, MFnNurbsSurfaceHandle):
            return int(handle.numCVsInU()) * int(handle.numCVsInV())
        if isinstance(handle, MFnLatticeHandle):
            try:
                return int(handle._mfn.numLatticePoints())
            except Exception:
                return int(handle._mfn.numPoints())
    except Exception:
        return 0
    return 0


def _handle_collect_points(handle):
    """Return an MPointArray of all current points on the handle."""
    if isinstance(handle, MFnMeshHandle):
        pa = om.MPointArray()
        handle._mfn.getPoints(pa, om.MSpace.kObject)
        return pa
    if isinstance(handle, MFnNurbsCurveHandle):
        pa = om.MPointArray()
        handle._mfn.getCVs(pa, om.MSpace.kObject)
        return pa
    if isinstance(handle, MFnNurbsSurfaceHandle):
        pa = om.MPointArray()
        handle._mfn.getCVs(pa, om.MSpace.kObject)
        return pa
    if isinstance(handle, MFnLatticeHandle):
        # Walk lattice points into an MPointArray.
        try:
            n = int(handle._mfn.numLatticePoints())
        except Exception:
            try:
                n = int(handle._mfn.numPoints())
            except Exception:
                n = 0
        pa = om.MPointArray(n)
        for i in range(n):
            try:
                p = handle._mfn.point(i)
            except Exception:
                try:
                    p = handle._mfn.getPoint(i)
                except Exception:
                    p = om.MPoint()
            pa.set(p, i)
        return pa
    return om.MPointArray()


def commit_deformer_output(handle, geom_iter, expected_vert_count, plug_label=""):
    """Push the user-mutated points on a writable MFn handle back to
    the deformer's geom_iter.

    dispatches on the handle's MFn type -- mesh, NURBS
    curve, NURBS surface, or lattice -- to read the current points
    and push them via ``geom_iter.setAllPositions`` (one C call).

    Topology change clamp:
      * If the handle's element count matches the input element
        count, the commit fires.
      * Otherwise log a stderr warning and skip -- output drops back
        to input unchanged (Section 5.3).
    """
    actual = _handle_actual_count(handle)
    if actual!= int(expected_vert_count):
        sys.stderr.write(
            "[mpynode][compute] {}: element count changed "
            "({} -> {}); skipping deformer commit -- output "
            "drops back to input unchanged.\n".format(
                plug_label or "outputGeometry",
                expected_vert_count, actual,
            )
        )
        return False

    pa = _handle_collect_points(handle)
    geom_iter.setAllPositions(pa)
    return True


# ---- Storage diff commit (Section 8.6c) ----


def commit_user_storage(node_obj, sp):
    """Diff the SelfProxy's user storage against its construction
    snapshot and persist any changes via ``cmds.setAttr`` on the
    ``_storedVarsData`` plug. No-op if nothing changed."""
    try:
        diff = sp.diff_storage()
    except Exception:
        return
    if not diff:
        return

    from mpynode._common.io import serialization as _serialization
    from mpynode._common.storedvars import stored_var_store as _svstore
    from maya import cmds

    fn_node   = om.MFnDependencyNode(node_obj)
    node_name = fn_node.name()
    try:
        sv_str   = fn_node.findPlug("_storedVarsData", True).asString()
        existing = _svstore.load_for_compute(node_obj, sv_str)
    except Exception:
        existing = {}

    new_stored = dict(existing)
    for k, v in diff.items():
        if v is None:
            new_stored.pop(k, None)
        else:
            new_stored[k] = v
    _svstore.set_for_compute(node_obj, new_stored)


# ---- Top-level entry point ----


def run_generic_compute(
    node_obj,
    datablock,
    *,
    geom_iter              = None,
    multi_index            = None,
    output_plug_short_name = "outputGeometry",
    family                 = "deformer",
    expression_code        = None,
):
    """Run the generic compute path for one tick.

    Args:
        node_obj: The MPx node's ``thisMObject()``.
        datablock: The MDataBlock for this compute.
        geom_iter: MItGeometry (deformer family only).
        multi_index: Output multi index being computed (deformer family).
        output_plug_short_name: Output geometry plug short name (default
            ``"outputGeometry"``).
        family: ``"deformer"`` for F.0. F.4+ adds ``"generator"``,
            ``"transform"`` etc.
        expression_code: Pre-compiled code object (cached on the node).
            If None, compute reads the node's ``_computeSource`` plug and
            compiles inline (slower; debug fallback).

    Returns True on success, False on user-expression error.
    """
    from mpynode._common.io import serialization as _serialization
    from mpynode._common.storedvars import stored_var_store as _svstore
    from mpynode._common.compute.expression import (
        compile_expression,
        exec_with_profile_watch,
    )
    from mpynode._common.compute.self_proxy import SelfProxy

    fn_node = om.MFnDependencyNode(node_obj)

    # ---- C1: defer while a scene is being READ / OPENED ----
    # The EM can pull this output mid-load, before the node's dynamic inputs and
    # _inputAttrs/_outputAttrs schema plugs are restored, making the expression
    # raise a spurious "'self' has no plug ... named X". It re-evaluates once the
    # scene is whole. Mirrors the api2 base compute() guard. Returning True is a
    # no-op: the output MItGeometry already holds the input copy.
    try:
        if om.MFileIO.isReadingFile():
            return True
    except Exception:
        pass

    # ---- allocate output handle (Section 5.1) ----
    handle              = None
    fresh_mobject       = None
    expected_vert_count = 0
    output_handles      = {}

    if family == "deformer":
        if multi_index is None:
            sys.stderr.write(
                "[mpynode][compute] run_generic_compute(family='deformer') "
                "requires multi_index\n"
            )
            return False
        try:
            handle, fresh_mobject, expected_vert_count = (
                allocate_deformer_output_handle(
                    datablock, multi_index,
                    plug_short_name=output_plug_short_name,
                )
            )
            output_handles[(output_plug_short_name, int(multi_index))] = handle
        except Exception as exc:
            sys.stderr.write(
                "[mpynode][compute] allocate_deformer_output_handle failed: "
                "{}\n".format(exc)
            )
            traceback.print_exc(file=sys.stderr)
            return False

    # ---- load + compile expression ----
    if expression_code is None:
        try:
            expr_str = fn_node.findPlug("_computeSource", True).asString() or ""
        except Exception:
            expr_str = ""
        try:
            expression_code = compile_expression(
                expr_str, filename="<{}-expression>".format(fn_node.name())
            )
        except Exception as exc:
            sys.stderr.write(
                "[mpynode][compute] compile failed for {}: {}\n".format(
                    fn_node.name(), exc
                )
            )
            return False

    # ---- load user storage ----
    try:
        sv_str = fn_node.findPlug("_storedVarsData", True).asString()
        user_storage = (
            _svstore.load_for_compute(node_obj, sv_str)
        )
    except Exception:
        user_storage = {}

    # ---- pre-seed ARRAY user outputs ----
    # Array user outputs get a mutable, pre-sized (N, ...) buffer so the
    # expression can slice-assign in place (e.g.
    # ``self.outMatrices[:, 3, :3] = ...``); harvested back after exec.
    # Scalar user outputs keep the direct plug-write path.
    from mpynode._common.compute.output_defaults import (
        harvest_array_outputs_api1,
        seed_array_outputs_api1,
    )

    seeded_array_outputs = seed_array_outputs_api1(node_obj)
    # Snapshot the ARRAY-OUTPUT names BEFORE seeding user inputs below. Only
    # these get harvested back to their plugs after exec; user inputs must NEVER
    # be written back (harvesting an input plug during a deformer deform() calls
    # handle.setMObject on an input and hard-crashes Maya).
    array_output_names = list(seeded_array_outputs.keys())

    # ---- C2 (base contract): seed USER inputs DENSELY ----
    # So ``self.<input>`` is a numpy value (vector array -> (N, 3)) instead of
    # the ragged live plug proxy that breaks ``np.asarray(self.<input>)``. This
    # is the api1 deformer-family analogue of the api2 own-path input seeding.
    # Inputs share the compute_locals dict (so ``self.<input>`` reads dense) but
    # are EXCLUDED from harvest via array_output_names above. setdefault never
    # clobbers a pre-sized array output already seeded.
    from mpynode._common.compute.user_input_seed import seed_user_inputs_into_locals

    seed_user_inputs_into_locals(node_obj, seeded_array_outputs)

    # ---- build SelfProxy + namespace ----
    compute_ctx = {
        "datablock":      datablock,
        "geom_iter":      geom_iter,
        "multi_index":    multi_index,
        "output_handles": output_handles,
    }

    sp = SelfProxy(
        node_obj,
        datablock       = datablock,
        geom_iter       = geom_iter,
        compute_ctx     = compute_ctx,
        user_storage    = user_storage,
        output_handles  = output_handles,
        node_type_label = fn_node.typeName(),
        compute_locals  = seeded_array_outputs,
    )

    import builtins as _builtins
    namespace = {
        "__builtins__": _builtins,
        "self":         sp,
    }

    # ---- exec ----
    captured = []

    def _on_err(msg):
        captured.append(msg)

    ok = exec_with_profile_watch(
        expression_code,
        namespace,
        log_event_name = "<{}-expression>".format(fn_node.name()),
        on_error       = _on_err,
        node_obj       = node_obj,
        compute_ctx    = compute_ctx,
    )
    if not ok:
        if captured:
            # C10: suppress the benign missing-plug transient (a DECLARED
            # input not yet resolvable during scene load / graph rebuild)
            # and broadcast every genuine error to stderr + the Qt-free
            # log_bus. Shared policy via base_contract so the deformer
            # family matches the api2 base compute() exactly.
            declared = set()
            try:
                for _schema_key in ("_inputAttrs", "_outputAttrs"):
                    _schema_str = fn_node.findPlug(_schema_key, True).asString()
                    if _schema_str:
                        declared |= set(
                            _serialization.decode_attr_map(_schema_str)
                        )
            except Exception:
                pass
            from mpynode._common.compute.base_contract import broadcast_compute_error

            broadcast_compute_error(
                fn_node.typeName(), captured[0], declared_names=declared
            )
        return False

    # ---- harvest seeded ARRAY user outputs back to their plugs ----
    # Restricted to array_output_names (snapshot before input seeding) so a
    # seeded user INPUT is never written back to its plug.
    if array_output_names:
        harvest_array_outputs_api1(
            sp.get_plug_proxy(),
            sp.get_compute_locals(),
            array_output_names,
        )

    # ---- commit output handle (deformer family) ----
    if family == "deformer" and handle is not None and geom_iter is not None:
        try:
            commit_deformer_output(
                handle, geom_iter, expected_vert_count,
                plug_label="{}[{}]".format(
                    output_plug_short_name, multi_index
                ),
            )
        except Exception as exc:
            sys.stderr.write(
                "[mpynode][compute] commit failed for {}[{}]: {}\n".format(
                    output_plug_short_name, multi_index, exc
                )
            )
            traceback.print_exc(file=sys.stderr)
            return False

    # ---- commit user storage diff ----
    try:
        commit_user_storage(node_obj, sp)
    except Exception as exc:
        sys.stderr.write(
            "[mpynode][compute] storage commit failed: {}\n".format(exc)
        )

    return True
