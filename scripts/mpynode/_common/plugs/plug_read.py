"""Plug read helpers — split out of ``plug_proxy.py`` (behavior unchanged).

Scalar readers (numeric / unit / matrix / typed) + the small read-support
helpers (attr-mobject lookup, data-handle fetch, typed-data mobject pull).
Geometry-typed reads live in the sibling ``plug_geometry`` module; the typed
dispatcher below reaches into it (see the explicit sibling import).
"""

from __future__ import annotations

from typing import Any, Optional

import maya.cmds as mc
import maya.OpenMaya as om

# Cross-module: the typed-plug dispatcher falls through to the geometry reader
# for geometry attr types. That reader now lives in a sibling module, so import
# it by name (bare-name lookup would fail after the split).
from .plug_geometry import _read_geometry_plug


# ---- Helpers ----


def _attr_mobject_for_name(
    node_mobject: "om.MObject", name: str
) -> Optional["om.MObject"]:
    """Return the MObject for the attribute called ``name`` on the
    given node, or None if it doesn't exist."""
    try:
        fn   = om.MFnDependencyNode(node_mobject)
        attr = fn.attribute(name)
        if attr.isNull():
            return None
        return attr
    except Exception:
        return None


def _data_handle_for_plug(plug, data_block):
    """Return the live ``MDataHandle`` for ``plug`` from
    ``data_block.inputValue(plug)`` -- this routes through Maya's
    canonical compute-time read path (DG-aware, EM-safe, no DG
    re-entry, never stale).

    Returns ``None`` when:
      * ``data_block`` is None (init-time / outside compute),
      * the plug is not addressable via the datablock (e.g. some
        compound children or array-element plugs that need the
        ``inputArrayValue``/``builder`` chain),
      * any Maya exception (kInvalidParameter, etc.).

    Callers should fall back to the legacy ``plug.asXXX()`` path on
    None return.
    """
    if data_block is None:
        return None
    try:
        return data_block.inputValue(plug)
    except Exception:
        return None


# ---- Scalar readers (numeric / unit / matrix / typed) ----


def _read_numeric_plug(
    plug: "om.MPlug", attr_mobject: "om.MObject", *, data_block=None
) -> Any:
    """Read a kNumericAttribute plug. Dispatches on the numeric subtype.

    architecture decision:
      * ``plug.asXXX()`` is the canonical API 1.0 read path. It works
        for BOTH static (class-declared) attrs AND dynamic
        (instance-added) attrs, and it pulls upstream connections
        correctly. This is the primary path.
      * ``data_block.inputValue(plug).asXXX()`` is the canonical
        compute-time path for STATIC attrs in shipping plug-ins, but
        for DYNAMIC attrs (the ones ``add_input_attr`` creates per
        instance) the datablock has no entry and returns
        uninitialized memory. So it's NOT a safe primary -- offered
        only as a secondary fallback for cases where the plug-side
        path raises.
      * ``cmds.getAttr`` is the MEL escape hatch and a true
        anti-pattern inside compute() (DG re-entry, EM unsafe). It's
        now restricted to init-time only (``data_block is None``).
    """
    fn_num = om.MFnNumericAttribute(attr_mobject)
    nt     = fn_num.unitType()

    try:
        if nt in (om.MFnNumericData.kBoolean,):
            try:
                return plug.asBool()
            except Exception:
                pass
            handle = _data_handle_for_plug(plug, data_block)
            if handle is not None:
                try:
                    return handle.asBool()
                except Exception:
                    pass
        if nt in (
            om.MFnNumericData.kChar,
            om.MFnNumericData.kByte,
            om.MFnNumericData.kShort,
            om.MFnNumericData.kLong,
            om.MFnNumericData.kInt,
        ):
            try:
                return plug.asInt()
            except Exception:
                pass
            handle = _data_handle_for_plug(plug, data_block)
            if handle is not None:
                try:
                    return handle.asLong()
                except Exception:
                    try:
                        return handle.asInt()
                    except Exception:
                        pass
        if nt in (
            om.MFnNumericData.kFloat,
            om.MFnNumericData.k2Float,
            om.MFnNumericData.k3Float,
        ):
            try:
                return plug.asFloat()
            except Exception:
                pass
            handle = _data_handle_for_plug(plug, data_block)
            if handle is not None:
                try:
                    return handle.asFloat()
                except Exception:
                    pass
        if nt in (
            om.MFnNumericData.kDouble,
            om.MFnNumericData.k2Double,
            om.MFnNumericData.k3Double,
            om.MFnNumericData.k4Double,
        ):
            try:
                return plug.asDouble()
            except Exception:
                pass
            handle = _data_handle_for_plug(plug, data_block)
            if handle is not None:
                try:
                    return handle.asDouble()
                except Exception:
                    pass
    except Exception:
        pass

    # Init-time only fallback. In compute (data_block is not None) we
    # refuse to call cmds.getAttr -- it causes DG re-entry and is
    # unsafe under EM. Return None so the caller can decide what to
    # do with it.
    if data_block is None:
        try:
            return mc.getAttr(plug.name())
        except Exception:
            return None
    return None


def _read_unit_plug(
    plug: "om.MPlug", attr_mobject: "om.MObject", *, data_block=None
) -> Any:
    """Read a kUnitAttribute plug (kAngle / kDistance / kTime).

    ``plug.asXXX()`` is the primary path (works for static
    + dynamic). ``data_block.inputValue()`` is a secondary fallback.
    ``cmds.getAttr`` is restricted to init-time."""
    fn_unit = om.MFnUnitAttribute(attr_mobject)
    try:
        ut = fn_unit.unitType()
        if ut == om.MFnUnitAttribute.kAngle:
            try:
                return plug.asMAngle().asRadians()
            except Exception:
                pass
            handle = _data_handle_for_plug(plug, data_block)
            if handle is not None:
                try:
                    return handle.asMAngle().asRadians()
                except Exception:
                    pass
        if ut == om.MFnUnitAttribute.kDistance:
            try:
                return plug.asMDistance().asCentimeters()
            except Exception:
                pass
            handle = _data_handle_for_plug(plug, data_block)
            if handle is not None:
                try:
                    return handle.asMDistance().asCentimeters()
                except Exception:
                    pass
        if ut == om.MFnUnitAttribute.kTime:
            from mpynode._common.plugs.promoted_types import TimeFloat
            try:
                return TimeFloat(plug.asMTime().asUnits(om.MTime.uiUnit()))
            except Exception:
                pass
            handle = _data_handle_for_plug(plug, data_block)
            if handle is not None:
                try:
                    return TimeFloat(
                        handle.asMTime().asUnits(om.MTime.uiUnit())
                    )
                except Exception:
                    pass
    except Exception:
        pass
    if data_block is None:
        try:
            return mc.getAttr(plug.name())
        except Exception:
            return None
    return None


def _read_matrix_plug(plug, *, data_block=None):
    """Read a kMatrix plug (matrix-attr or matrix-typed). return an ``MatrixView`` per the Section 4 type
    promotion table -- never a raw ``MMatrix``. Use ``.asMatrix()`` to
    drop down to ``MMatrix`` for raw 4x4 multiplication, or
    ``.asNumpy()`` for a ``(4, 4) float64`` ndarray.

    ``plug.asMObject() -> MFnMatrixData.matrix()`` is the
    primary path -- it correctly pulls upstream connections for both
    static and dynamic attrs. ``data_block.inputValue().asMatrix()``
    is a secondary fallback for cases where the plug-side path fails.
    ``cmds.getAttr`` is restricted to init-time.

    bug fix: ``MFnMatrixData(mobj).matrix()`` returns a
    reference to internal storage that becomes invalidated when the
    local ``MFnMatrixData`` instance goes out of scope -- yielding
    spurious zeros in caller code. We **copy** into a fresh
    ``MMatrix`` (via the 16-float marshal) to detach from the
    short-lived MFnMatrixData.
    """
    from mpynode._common.plugs.promoted_types import MatrixView

    def _copy_mmatrix(src_mm):
        """Copy the 4x4 values into a fresh MMatrix that outlives
        the (transient) MFnMatrixData wrapper that produced ``src_mm``."""
        out = om.MMatrix()
        try:
            flat = [src_mm(r, c) for r in range(4) for c in range(4)]
            om.MScriptUtil.createMatrixFromList(flat, out)
        except Exception:
            return src_mm  # best-effort: return the (possibly transient) ref
        return out

    mm = None
    try:
        mobj = plug.asMObject()
        mm   = _copy_mmatrix(om.MFnMatrixData(mobj).matrix())
    except Exception:
        mm = None

    if mm is None:
        handle = _data_handle_for_plug(plug, data_block)
        if handle is not None:
            try:
                mm = _copy_mmatrix(handle.asMatrix())
            except Exception:
                mm = None

    if mm is None and data_block is None:
        try:
            vals = mc.getAttr(plug.name()) or []
            mm   = om.MMatrix()
            if len(vals) == 16:
                om.MScriptUtil.createMatrixFromList(vals, mm)
        except Exception:
            mm = None

    if mm is None:
        mm = om.MMatrix()
    else:
        # An all-zeros matrix means the plug is unconnected and the
        # attribute had no explicit default (Maya zero-fills the
        # storage for user-added matrix attrs). Return identity to
        # match stock Maya matrix-plug semantics. Identity is also
        # the only value of MMatrix() that the api1 default
        # constructor produces, so the fallback above is consistent.
        all_zero = True
        for _i in range(4):
            for _j in range(4):
                if mm(_i, _j) != 0.0:
                    all_zero = False
                    break
            if not all_zero:
                break
        if all_zero:
            mm = om.MMatrix()
    return MatrixView(mm)


def _is_matrix_attr(attr_mobject) -> bool:
    """True if ``attr_mobject`` is a matrix attribute -- either a fixed
    ``MFnMatrixAttribute`` (kMatrixAttribute) or a typed ``kMatrix`` data
    attribute."""
    try:
        if attr_mobject.hasFn(om.MFn.kMatrixAttribute):
            return True
        if attr_mobject.hasFn(om.MFn.kTypedAttribute):
            return om.MFnTypedAttribute(attr_mobject).attrType() == om.MFnData.kMatrix
    except Exception:
        pass
    return False


def _read_typed_plug(
    plug: "om.MPlug", attr_mobject: "om.MObject", *, data_block=None
) -> Any:
    """Read a kTypedAttribute plug. Dispatch on attrType:

    * kString      → str
    * kMatrix      → MMatrix
    * kPointArray  → MPointArray
    * kMesh        → MFnMesh
    * kNurbsCurve  → MFnNurbsCurve
    * kNurbsSurface→ MFnNurbsSurface
    * kSubdSurface → MFnSubd
    * kLattice     → MFnLattice (if available)
    * kFloatArray  → MFloatArray
    * kDoubleArray → MDoubleArray
    * kIntArray    → MIntArray
    * <other>      → raw plug name string (best-effort)

    ``data_block`` is threaded through to the matrix branch
    (matrix-typed attrs in this dispatch fall to ``_read_matrix_plug``).
    Typed-data arrays (kPointArray etc.) still read via
    ``plug.asMObject()`` because there is no canonical
    ``MDataHandle.asPointArray()``; for production deformers the
    array-data path is fine because Maya pulls these through the
    datablock's data MObject pointer, which Maya keeps current as
    long as the affects relationship is declared.
    """
    fn_typed = om.MFnTypedAttribute(attr_mobject)
    try:
        attr_type = fn_typed.attrType()
    except Exception:
        attr_type = None

    if attr_type == om.MFnData.kString:
        try:
            return plug.asString() or ""
        except Exception:
            pass
        handle = _data_handle_for_plug(plug, data_block)
        if handle is not None:
            try:
                return handle.asString() or ""
            except Exception:
                pass
        if data_block is None:
            try:
                return mc.getAttr(plug.name()) or ""
            except Exception:
                return ""
        return ""

    if attr_type == om.MFnData.kMatrix:
        return _read_matrix_plug(plug, data_block=data_block)

    # type promotions: typed array attrs return numpy.
    # when data_block is available, pull the data MObject
    # through the datahandle so the values reflect live propagation.
    if attr_type == om.MFnData.kPointArray:
        try:
            from mpynode._common.plugs.array_convert import points_array_to_numpy
            mobj = _typed_data_mobject(plug, data_block)
            return points_array_to_numpy(om.MFnPointArrayData(mobj).array())
        except Exception:
            return None

    if attr_type == om.MFnData.kVectorArray:
        try:
            from mpynode._common.plugs.array_convert import vector_array_to_numpy
            mobj = _typed_data_mobject(plug, data_block)
            return vector_array_to_numpy(om.MFnVectorArrayData(mobj).array())
        except Exception:
            return None

    if attr_type == om.MFnData.kFloatArray:
        try:
            from mpynode._common.plugs.array_convert import float_array_to_numpy
            mobj = _typed_data_mobject(plug, data_block)
            return float_array_to_numpy(om.MFnFloatArrayData(mobj).array())
        except Exception:
            return None

    if attr_type == om.MFnData.kDoubleArray:
        try:
            from mpynode._common.plugs.array_convert import double_array_to_numpy
            mobj = _typed_data_mobject(plug, data_block)
            return double_array_to_numpy(om.MFnDoubleArrayData(mobj).array())
        except Exception:
            return None

    if attr_type == om.MFnData.kIntArray:
        try:
            from mpynode._common.plugs.array_convert import int_array_to_numpy
            mobj = _typed_data_mobject(plug, data_block)
            return int_array_to_numpy(om.MFnIntArrayData(mobj).array())
        except Exception:
            return None

    # E2: geometry types → MFn wrappers.
    return _read_geometry_plug(plug, attr_type)


def _typed_data_mobject(plug, data_block):
    """Pull the typed-data MObject for ``plug``. Prefers
    ``plug.asMObject()`` (canonical API 1.0 read, works for both
    static and dynamic attrs). Falls back to
    ``data_block.inputValue(plug).data()`` if the plug-side path
    raises."""
    try:
        return plug.asMObject()
    except Exception:
        pass
    if data_block is not None:
        try:
            handle = data_block.inputValue(plug)
            return handle.data()
        except Exception:
            pass
    return None


def _attr_short_or_long_name(attr_mobject) -> str:
    try:
        fn = om.MFnAttribute(attr_mobject)
        return fn.name()
    except Exception:
        return ""
