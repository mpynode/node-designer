"""Plug write helpers — split out of ``plug_proxy.py`` (behavior unchanged).

Compute-time (MDataBlock) + init-time (cmds.setAttr) writers, matrix / array
coercion helpers, and the deformer geom_iter push. The compute-time writer
reaches ``_attr_short_or_long_name`` which now lives in the sibling
``plug_read`` module, so it is imported by name below.
"""

from __future__ import annotations

from typing import Any, Optional

import maya.cmds as mc
import maya.OpenMaya as om

# The compute-time writer detects a deformer ``outputGeometry`` plug by attr
# name; that helper moved to ``plug_read``, so it must be imported explicitly.
from .plug_read import _attr_short_or_long_name


# Geometry typed-attr types the ``_api2`` marshallers can build a data object
# for, mapped to the attr-type name ``_geo_value_to_data`` dispatches on.
# kSubdSurface / kLattice are deliberately absent: no marshaller exists.
_GEO_ATTR_KINDS = {
    om.MFnData.kMesh: "mesh",
    om.MFnData.kNurbsCurve: "nurbsCurve",
    om.MFnData.kNurbsSurface: "nurbsSurface",
}


def _api2_plug(plug: "om.MPlug"):
    """Re-resolve this api1 ``MPlug`` as the api2 plug for the SAME attribute.

    The geometry marshallers live in ``_api2`` and hand back api2 ``MFn*Data``
    MObjects, which api1's ``MPlug.setMObject`` rejects outright ("argument 2 of
    type 'MObject const &'") -- the two APIs' MObjects are different Python
    types. Rebuilding the data with api1 function sets would be a second copy of
    the marshaller, so the WRITE moves to the api2 side instead.

    The bridge is by NAME, and a DAG plug's ``name()`` is the node's SHORT name,
    which two shapes under different parents can share -- resolving that would
    silently pick one of them. The full DAG path is used so the write can never
    land on the wrong node.
    """
    import maya.api.OpenMaya as om2

    node = plug.node()
    if node.hasFn(om.MFn.kDagNode):
        node_name = om.MFnDagNode(node).fullPathName()
    else:
        node_name = om.MFnDependencyNode(node).name()
    # full attribute path, array indices kept, long names.
    attr_path = plug.partialName(False, True, True, False, True, True)
    sel = om2.MSelectionList()
    sel.add("%s.%s" % (node_name, attr_path))
    return sel.getPlug(0)


# ---- Writes (E3 init-time / E4 compute-time) ----


def _write_plug(
    plug: "om.MPlug",
    attr_mobject: "om.MObject",
    value: Any,
    datablock=None,
    geom_iter=None,
    compute_ctx=None,
) -> None:
    """Dispatch write to compute-time (DataBlock) or init-time
    (cmds.setAttr) path based on whether a DataBlock is present."""
    if datablock is not None:
        _write_plug_compute_time(
            plug, attr_mobject, value, datablock, geom_iter,
            compute_ctx=compute_ctx,
        )
    else:
        _write_plug_init_time(plug, attr_mobject, value)


def _write_plug_compute_time(
    plug: "om.MPlug",
    attr_mobject: "om.MObject",
    value: Any,
    datablock,
    geom_iter=None,
    compute_ctx=None,
) -> None:
    """E4 compute-time write via MDataBlock.

    Special case: writes to a deformer's ``outputGeometry[i]`` are
    routed to ``geom_iter.setAllPositions(...)`` when a ``geom_iter``
    is available. MPxDeformerNode doesn't write outputGeometry
    directly — it mutates points via MItGeometry. So we never try
    to setMObject on a deformer's outputGeometry plug.
    """
    plug_name = plug.name()

    # --- deformer fast path: outputGeometry[i] = ndarray/MPointArray ---
    if (
        geom_iter is not None
        and _attr_short_or_long_name(attr_mobject) == "outputGeometry"
    ):
        _write_via_geom_iter(geom_iter, value, compute_ctx=compute_ctx)
        try:
            datablock.setClean(plug)
        except Exception:
            pass
        return

    # --- generic DataBlock write ---
    try:
        handle = datablock.outputValue(plug)
    except Exception as exc:
        raise AttributeError(
            f"datablock.outputValue({plug_name!r}) failed: {exc}; "
            "is this an output plug?"
        )

    # ---- numeric ----
    if attr_mobject.hasFn(om.MFn.kNumericAttribute):
        fn_num = om.MFnNumericAttribute(attr_mobject)
        try:
            nt = fn_num.unitType()
        except Exception:
            nt = None
        try:
            if nt in (om.MFnNumericData.kBoolean,):
                handle.setBool(bool(value))
            elif nt in (
                om.MFnNumericData.kChar, om.MFnNumericData.kByte,
                om.MFnNumericData.kShort, om.MFnNumericData.kLong,
                om.MFnNumericData.kInt,
            ):
                handle.setInt(int(value))
            elif nt in (om.MFnNumericData.kFloat,):
                handle.setFloat(float(value))
            elif nt in (om.MFnNumericData.kDouble,):
                handle.setDouble(float(value))
            elif nt in (
                om.MFnNumericData.k2Float, om.MFnNumericData.k3Float,
                om.MFnNumericData.k2Double, om.MFnNumericData.k3Double,
                om.MFnNumericData.k4Double,
            ):
                # Compound numeric: use MFnNumericData wrapping.
                if nt in (om.MFnNumericData.k2Float, om.MFnNumericData.k2Double):
                    n_comp = 2
                elif nt in (om.MFnNumericData.k3Float, om.MFnNumericData.k3Double):
                    n_comp = 3
                else:
                    n_comp = 4
                data_obj = om.MFnNumericData().create(nt)
                fn_data = om.MFnNumericData(data_obj)
                if nt in (om.MFnNumericData.k2Float, om.MFnNumericData.k3Float):
                    if n_comp == 2:
                        fn_data.setData2Float(float(value[0]), float(value[1]))
                    else:
                        fn_data.setData3Float(
                            float(value[0]), float(value[1]), float(value[2])
                        )
                else:
                    if n_comp == 2:
                        fn_data.setData2Double(float(value[0]), float(value[1]))
                    elif n_comp == 3:
                        fn_data.setData3Double(
                            float(value[0]), float(value[1]), float(value[2])
                        )
                    else:
                        fn_data.setData4Double(
                            float(value[0]), float(value[1]),
                            float(value[2]), float(value[3]),
                        )
                handle.setMObject(data_obj)
            else:
                handle.setDouble(float(value))
        except Exception as exc:
            raise AttributeError(
                f"compute-time numeric write to {plug_name!r} failed: {exc}"
            )

    # ---- unit (angle/distance/time) ----
    elif attr_mobject.hasFn(om.MFn.kUnitAttribute):
        fn_unit = om.MFnUnitAttribute(attr_mobject)
        try:
            ut = fn_unit.unitType()
            if ut == om.MFnUnitAttribute.kAngle:
                handle.setMAngle(om.MAngle(float(value), om.MAngle.kRadians))
            elif ut == om.MFnUnitAttribute.kDistance:
                handle.setMDistance(
                    om.MDistance(float(value), om.MDistance.kCentimeters)
                )
            elif ut == om.MFnUnitAttribute.kTime:
                handle.setMTime(om.MTime(float(value), om.MTime.kSeconds))
            else:
                handle.setDouble(float(value))
        except Exception as exc:
            raise AttributeError(
                f"compute-time unit write to {plug_name!r} failed: {exc}"
            )

    # ---- matrix ----
    elif attr_mobject.hasFn(om.MFn.kMatrixAttribute):
        try:
            arr = _coerce_to_4x4_numpy(value)
            if arr is None:
                raise ValueError(
                    f"cannot coerce {type(value).__name__} to 4x4 matrix"
                )
            mtx = om.MMatrix()
            om.MScriptUtil.createMatrixFromList(arr.flatten().tolist(), mtx)
            data_obj = om.MFnMatrixData().create(mtx)
            handle.setMObject(data_obj)
        except Exception as exc:
            raise AttributeError(
                f"compute-time matrix write to {plug_name!r} failed: {exc}"
            )

    # ---- typed (string / matrix / arrays / geometry) ----
    elif attr_mobject.hasFn(om.MFn.kTypedAttribute):
        fn_typed = om.MFnTypedAttribute(attr_mobject)
        try:
            attr_type = fn_typed.attrType()
        except Exception:
            attr_type = None
        try:
            if attr_type == om.MFnData.kString:
                handle.setString(str(value))
            elif attr_type == om.MFnData.kMatrix:
                arr = _coerce_to_4x4_numpy(value)
                if arr is None:
                    raise ValueError(
                        f"cannot coerce {type(value).__name__} to 4x4 matrix"
                    )
                mtx = om.MMatrix()
                om.MScriptUtil.createMatrixFromList(arr.flatten().tolist(), mtx)
                data_obj = om.MFnMatrixData().create(mtx)
                handle.setMObject(data_obj)
            elif attr_type in (
                om.MFnData.kPointArray, om.MFnData.kVectorArray,
                om.MFnData.kFloatArray, om.MFnData.kDoubleArray,
                om.MFnData.kIntArray, om.MFnData.kStringArray,
            ):
                data_obj = _build_array_data_mobject(attr_type, value)
                if data_obj is not None:
                    handle.setMObject(data_obj)
            elif attr_type == om.MFnData.kMesh and isinstance(
                value, om.MFnMesh
            ):
                # User wrote a fresh MFnMesh — push its data.
                mesh_data = om.MFnMeshData().create()
                # MFnMesh.copy(...) builds a new mesh into mesh_data
                # backed by the same geometry as `value`.
                value.copy(value.object(), mesh_data)
                handle.setMObject(mesh_data)
            else:
                raise NotImplementedError(
                    f"compute-time write to typed attr {plug_name!r} "
                    f"(attrType={attr_type}) not supported"
                )
        except NotImplementedError:
            raise
        except Exception as exc:
            raise AttributeError(
                f"compute-time typed write to {plug_name!r} failed: {exc}"
            )

    # ---- enum ----
    elif attr_mobject.hasFn(om.MFn.kEnumAttribute):
        try:
            handle.setInt(int(value))
        except Exception as exc:
            raise AttributeError(
                f"compute-time enum write to {plug_name!r} failed: {exc}"
            )

    else:
        raise NotImplementedError(
            f"compute-time write to attribute type "
            f"{attr_mobject.apiTypeStr()} not supported "
            f"(plug {plug_name!r})"
        )

    # Mark the plug clean so the EM doesn't ask us to recompute.
    try:
        datablock.setClean(plug)
    except Exception:
        pass


def _write_via_geom_iter(geom_iter, value, compute_ctx=None) -> None:
    """Push ``value`` (numpy (N, 3) or MPointArray or list of triples)
    to the deformer's geom_iter via setAllPositions. Records the write
    by setting ``compute_ctx["geometry_committed"]``; nothing reads that
    sentinel today -- its consumer was the legacy ``self.deformed``
    fast-path, which was deleted with the rest of the internal-vars
    deformer schema (see the migration note in ``_api1.mpy_deformer``)."""
    if isinstance(value, om.MPointArray):
        geom_iter.setAllPositions(value)
    elif hasattr(value, "shape") and len(value.shape) == 2 and value.shape[1] == 3:
        n = int(value.shape[0])
        pa = om.MPointArray(n)
        for i in range(n):
            pa.set(
                om.MPoint(
                    float(value[i, 0]),
                    float(value[i, 1]),
                    float(value[i, 2]),
                ),
                i,
            )
        geom_iter.setAllPositions(pa)
    else:
        pa = om.MPointArray()
        for triple in value:
            pa.append(
                om.MPoint(
                    float(triple[0]),
                    float(triple[1]),
                    float(triple[2]),
                )
            )
        geom_iter.setAllPositions(pa)
    if compute_ctx is not None:
        compute_ctx["geometry_committed"] = True


def _write_plug_init_time(
    plug: "om.MPlug",
    attr_mobject: "om.MObject",
    value: Any,
) -> None:
    """Write ``value`` to ``plug`` using cmds.setAttr (init-time path).

    Dispatch on the attribute type to pick the right setAttr signature.
    Raises a clear AttributeError if the write isn't supported.
    """
    plug_name = plug.name()

    # ---- numeric attribute ----
    if attr_mobject.hasFn(om.MFn.kNumericAttribute):
        fn_num = om.MFnNumericAttribute(attr_mobject)
        try:
            nt = fn_num.unitType()
        except Exception:
            nt = None
        # Compound numerics (k2/3/4 Float/Double): value must be unpacked.
        if nt in (
            om.MFnNumericData.k2Float,
            om.MFnNumericData.k3Float,
            om.MFnNumericData.k2Double,
            om.MFnNumericData.k3Double,
            om.MFnNumericData.k4Double,
        ):
            try:
                mc.setAttr(plug_name, *value)
                return
            except Exception as exc:
                raise AttributeError(f"setAttr({plug_name!r}, {value!r}) failed: {exc}")
        # Scalar numeric.
        try:
            mc.setAttr(plug_name, value)
            return
        except Exception as exc:
            raise AttributeError(f"setAttr({plug_name!r}, {value!r}) failed: {exc}")

    # ---- unit attribute (angle/distance/time) ----
    if attr_mobject.hasFn(om.MFn.kUnitAttribute):
        try:
            mc.setAttr(plug_name, value)
            return
        except Exception as exc:
            raise AttributeError(f"setAttr({plug_name!r}, {value!r}) failed: {exc}")

    # ---- matrix attribute ----
    if attr_mobject.hasFn(om.MFn.kMatrixAttribute):
        flat = _matrix_to_flat_list(value)
        if flat is None:
            raise AttributeError(
                f"cannot write {value!r} to matrix plug {plug_name!r} "
                "(expected MMatrix or 16-element list)"
            )
        try:
            mc.setAttr(plug_name, flat, type="matrix")
            return
        except Exception as exc:
            raise AttributeError(f"setAttr({plug_name!r}, <matrix>) failed: {exc}")

    # ---- enum attribute ----
    if attr_mobject.hasFn(om.MFn.kEnumAttribute):
        try:
            mc.setAttr(plug_name, int(value))
            return
        except Exception as exc:
            raise AttributeError(f"setAttr({plug_name!r}, {value!r}) failed: {exc}")

    # ---- typed attribute (string/matrix/point-array/geometry) ----
    if attr_mobject.hasFn(om.MFn.kTypedAttribute):
        fn_typed = om.MFnTypedAttribute(attr_mobject)
        try:
            attr_type = fn_typed.attrType()
        except Exception:
            attr_type = None

        if attr_type == om.MFnData.kString:
            try:
                mc.setAttr(plug_name, str(value), type="string")
                return
            except Exception as exc:
                raise AttributeError(f"setAttr({plug_name!r},...) failed: {exc}")

        if attr_type == om.MFnData.kMatrix:
            flat = _matrix_to_flat_list(value)
            if flat is None:
                raise AttributeError(
                    f"cannot write {value!r} to matrix plug {plug_name!r}"
                )
            try:
                mc.setAttr(plug_name, flat, type="matrix")
                return
            except Exception as exc:
                raise AttributeError(f"setAttr({plug_name!r}, <matrix>) failed: {exc}")

        # Point/Vector/Float/Double/Int array typed attrs — these go
        # through MFnXArrayData wrappers + MPlug.setMObject.
        if attr_type in (
            om.MFnData.kPointArray,
            om.MFnData.kVectorArray,
            om.MFnData.kFloatArray,
            om.MFnData.kDoubleArray,
            om.MFnData.kIntArray,
            om.MFnData.kStringArray,
        ):
            try:
                data_mobj = _build_array_data_mobject(attr_type, value)
                if data_mobj is not None:
                    plug.setMObject(data_mobj)
                    return
            except Exception as exc:
                raise AttributeError(f"write to array plug {plug_name!r} failed: {exc}")

        # Geometry typed attrs that HAVE a marshaller (kMesh / kNurbsCurve /
        # kNurbsSurface): build the data object with the SAME _api2 marshaller
        # the compute-time path uses, then push it on the api2 side (see
        # _api2_plug for why the write cannot happen on this api1 plug).
        if attr_type in _GEO_ATTR_KINDS:
            from mpynode._api2.helpers import _geo_value_to_data

            kind = _GEO_ATTR_KINDS[attr_type]
            data_mobj = _geo_value_to_data(kind, value)
            if data_mobj is None:
                raise AttributeError(
                    f"cannot write {type(value).__name__} to {kind} plug "
                    f"{plug_name!r}; expected a Mesh / NurbsCurve / "
                    "NurbsSurface, anything exposing to_mobject(), or a value "
                    "bucket carrying that kind's required arrays"
                )
            try:
                _api2_plug(plug).setMObject(data_mobj)
                return
            except Exception as exc:
                raise AttributeError(
                    f"write to geometry plug {plug_name!r} failed: {exc}")

        # kSubdSurface / kLattice have no marshaller on EITHER path, so there is
        # nothing to build a data object from.
        if attr_type in (
            om.MFnData.kSubdSurface,
            om.MFnData.kLattice,
        ):
            raise NotImplementedError(
                f"writing geometry to {plug_name!r} via init-time "
                "cmds.setAttr is not supported. Use a compute-time "
                "hook with the DataBlock to push geometry data."
            )

        # Generic/unknown typed — best-effort.
        try:
            mc.setAttr(plug_name, value)
            return
        except Exception as exc:
            raise AttributeError(f"setAttr({plug_name!r}, {value!r}) failed: {exc}")

    # ---- compound attribute (k3Compound etc.) ----
    if attr_mobject.hasFn(om.MFn.kCompoundAttribute):
        # E3: writing to a compound directly (e.g. node.translate = (1,2,3))
        # is treated as: unpack value across children. Defer to leaf
        # writes (called by CompoundPlugProxy.__setattr__ when user
        # writes node.translate.translateX directly). Users wanting
        # `node.translate = (1,2,3)` style should call
        # ``mc.setAttr(plug, *value)`` themselves, OR set each child.
        try:
            mc.setAttr(plug_name, *value)
            return
        except Exception as exc:
            raise AttributeError(
                f"compound setAttr({plug_name!r}, {value!r}) failed: "
                f"{exc} (try writing each child individually)"
            )

    # ---- last-resort generic ----
    try:
        mc.setAttr(plug_name, value)
    except Exception as exc:
        raise AttributeError(
            f"setAttr({plug_name!r}, {value!r}) failed for "
            f"attribute type {attr_mobject.apiTypeStr()}: {exc}"
        )


def _coerce_to_4x4_numpy(value):
    """Coerce ``value`` into a (4, 4) numpy float64 matrix. API-agnostic.

    Accepted shapes / types:
      * ``om.MMatrix`` (api1 or api2) -- read element-by-element.
      * ``om.MTransformationMatrix`` (api1 or api2) -- call ``.asMatrix()``
        then recurse.
      * flat 16-iterable (list / tuple / 1D numpy).
      * 4x4 nested iterable / 2D numpy.
      * 3x3 nested iterable / 2D numpy -- expanded to 4x4 with zero
        translate (the rotation/scale block sits in the upper-left;
        translate row is [0, 0, 0, 1]).

    Returns the numpy (4, 4) on success, ``None`` if no shape matches.
    The api-flavor caller wraps the result in its own MMatrix.
    """
    import numpy as _np

    # MTransformationMatrix (any api): unwrap via .asMatrix() then recurse.
    if hasattr(value, "asMatrix") and callable(getattr(value, "asMatrix", None)):
        try:
            return _coerce_to_4x4_numpy(value.asMatrix())
        except Exception:
            pass

    # MMatrix (api1 or api2): read via callable element-access.
    cls_name = type(value).__name__
    if cls_name == "MMatrix":
        out = _np.zeros((4, 4), dtype=_np.float64)
        try:
            # api1 MMatrix: callable(i, j) returns float.
            for i in range(4):
                for j in range(4):
                    out[i, j] = float(value(i, j))
            return out
        except Exception:
            pass
        try:
            # api2 MMatrix: indexable as [i * 4 + j] (single-index flat
            # access). 16-iterable also works via list().
            flat = list(value)
            if len(flat) == 16:
                return _np.asarray(flat, dtype=_np.float64).reshape(4, 4)
        except Exception:
            pass

    # numpy / iterable shapes.
    try:
        arr = _np.asarray(value, dtype=_np.float64)
        if arr.shape == (4, 4):
            return arr.copy()
        if arr.shape == (16,):
            return arr.reshape(4, 4).copy()
        if arr.shape == (3, 3):
            out = _np.eye(4, dtype=_np.float64)
            out[:3, :3] = arr
            return out
    except Exception:
        pass
    return None


def _matrix_to_flat_list(value: Any):
    """Coerce ``value`` (MMatrix or 16-element iterable) to a 16-list
    of floats. Returns None if it can't be coerced."""
    if isinstance(value, om.MMatrix):
        out = [0.0] * 16
        for i in range(4):
            for j in range(4):
                out[i * 4 + j] = float(value(i, j))
        return out
    try:
        flat = list(value)
        if len(flat) == 16:
            return [float(x) for x in flat]
        # Nested 4x4
        if len(flat) == 4 and all(len(row) == 4 for row in flat):
            return [float(flat[i][j]) for i in range(4) for j in range(4)]
    except Exception:
        pass
    return None


def _build_array_data_mobject(attr_type, value) -> Optional["om.MObject"]:
    """Build an MObject of the appropriate FnXArrayData type wrapping
    ``value`` (an iterable). Returns None on failure."""
    # Most array types take an MXArray; we coerce value into the
    # appropriate MX array first.
    if attr_type == om.MFnData.kPointArray:
        pa = om.MPointArray()
        for v in value:
            pa.append(om.MPoint(*[float(c) for c in v]))
        return om.MFnPointArrayData().create(pa)
    if attr_type == om.MFnData.kVectorArray:
        va = om.MVectorArray()
        for v in value:
            va.append(om.MVector(*[float(c) for c in v]))
        return om.MFnVectorArrayData().create(va)
    if attr_type == om.MFnData.kFloatArray:
        fa = om.MFloatArray()
        for v in value:
            fa.append(float(v))
        return om.MFnFloatArrayData().create(fa)
    if attr_type == om.MFnData.kDoubleArray:
        da = om.MDoubleArray()
        for v in value:
            da.append(float(v))
        return om.MFnDoubleArrayData().create(da)
    if attr_type == om.MFnData.kIntArray:
        ia = om.MIntArray()
        for v in value:
            ia.append(int(v))
        return om.MFnIntArrayData().create(ia)
    if attr_type == om.MFnData.kStringArray:
        sa = om.MStringArray()
        for v in value:
            sa.append(str(v))
        return om.MFnStringArrayData().create(sa)
    return None
