"""Geometry-typed plug readers — split out of ``plug_proxy.py`` (behavior
unchanged).

Resolves geometry-typed plugs (mesh / nurbs / subd / lattice) to MFn wrappers
of the connected upstream source. Self-contained: the functions below reference
only each other, so no sibling-module imports are needed.
"""

from __future__ import annotations

from typing import Any

import maya.cmds as mc
import maya.OpenMaya as om


# ---- E2: geometry plug readers ----


def _read_geometry_plug(plug: "om.MPlug", attr_type) -> Any:
    """Resolve a geometry-typed plug to an MFn wrapper.

    Walks any incoming connection to find the source's geometry data
    so the user can call ``getPoints()`` / ``numVertices()`` etc.
    Returns None if no geometry is present.

    Note: many deformer-style geometry plugs (e.g.
    ``deformer.input[*].inputGeometry``) declare ``attrType() ==
    kInvalid`` because they accept ANY geometry type — the actual
    type is determined at runtime by the connected data. So we
    dispatch on the DATA's apiType, not the attribute's declared
    type.
    """
    # Try to find the source of an incoming connection.
    target_plug = plug
    try:
        sources = om.MPlugArray()
        plug.connectedTo(sources, True, False)  # asDst=True
        if sources.length() > 0:
            target_plug = sources[0]
    except Exception:
        pass

    # Pull the data MObject: kMeshData for an output geometry plug, maybe kNull
    # for an unconnected input. On an unevaluated deformer output (e.g.
    # originalGeometry[0] before any compute) asMObject can raise "Unexpected
    # Internal Failure", so force a dgeval and retry.
    try:
        geom_mobj = target_plug.asMObject()
    except Exception:
        geom_mobj = None
        try:
            mc.dgeval(target_plug.name())
            geom_mobj = target_plug.asMObject()
        except Exception:
            geom_mobj = None

    if geom_mobj is not None and not geom_mobj.isNull():
        # Dispatch on the actual data's apiType (robust to
        # generic attribute declarations).
        wrapped = _mfn_wrap_data_by_runtime_type(geom_mobj)
        if wrapped is not None:
            return wrapped
        # Fallthrough: data exists but isn't a known geometry type;
        # also try wrapping via declared attrType.
        wrapped = _mfn_wrap_data(geom_mobj, attr_type)
        if wrapped is not geom_mobj:
            return wrapped

    # Deformer-specific fallback: originalGeometry[i] on a custom
    # MPxDeformerNode subclass isn't readable via MPlug.asMObject()
    # outside a compute() context (Maya quirk, verified in 2024+2026
    # mayapy). The data is logically identical to input[i].inputGeometry
    # at deformer attach time, so fall back to walking that connection.
    try:
        plug_partial = plug.partialName(False, False, False, False, False, True)
    except Exception:
        plug_partial = ""
    if "originalGeometry" in plug_partial:
        try:
            # Extract the logical index from "originalGeometry[N]".
            import re
            m = re.search(r"originalGeometry\[(\d+)\]", plug_partial)
            if m:
                idx = int(m.group(1))
                node_mobj = plug.node()
                fn_node = om.MFnDependencyNode(node_mobj)
                input_plug = fn_node.findPlug("input", True)
                input_elem = input_plug.elementByLogicalIndex(idx)
                input_geom = input_elem.child(0)  # input[N].inputGeometry
                sources = om.MPlugArray()
                input_geom.connectedTo(sources, True, False)
                if sources.length() > 0:
                    src_mobj = sources[0].asMObject()
                    if src_mobj is not None and not src_mobj.isNull():
                        wrapped = _mfn_wrap_data_by_runtime_type(src_mobj)
                        if wrapped is not None:
                            return wrapped
        except Exception:
            pass

    # Last resort: walk to the source node + try to find a shape.
    try:
        src_node = target_plug.node()
        return _mfn_wrap_node(src_node)
    except Exception:
        return geom_mobj if (geom_mobj is not None and not geom_mobj.isNull()) else None


def geometry_data_mobject(plug: "om.MPlug") -> Any:
    """The raw geometry-DATA MObject feeding ``plug`` (walking any incoming
    connection to the source's data), or None.

    Mirrors the primary resolution of :func:`_read_geometry_plug` but returns the
    DATA MObject instead of an MFn wrapper -- so callers can read component tags
    (``MFnGeometryData``) off the SAME data ``self.<geo>`` exposes. This is
    Evaluation-Manager-safe ONLY when ``plug`` is built on the LIVE compute node
    MObject (as ``PlugProxy`` does, ``om.MPlug(self._mobject, attr)``): a plug
    resolved by name via ``MSelectionList`` is not scheduled by the EM and reads
    empty inside ``compute``. Never raises."""
    try:
        if plug.isArray():
            plug = plug.elementByLogicalIndex(0)
    except Exception:
        pass
    target_plug = plug
    try:
        sources = om.MPlugArray()
        plug.connectedTo(sources, True, False)  # asDst -> sources
        if sources.length() > 0:
            target_plug = sources[0]
    except Exception:
        pass
    try:
        geom_mobj = target_plug.asMObject()
    except Exception:
        geom_mobj = None
    if geom_mobj is not None and not geom_mobj.isNull():
        return geom_mobj
    return None


def _mfn_wrap_data_by_runtime_type(geom_mobj: "om.MObject") -> Any:
    """Wrap a geometry data MObject based on its runtime apiType
    (not the attribute's declared type). Returns None if the data
    isn't one of the known geometry data types."""
    try:
        if geom_mobj.hasFn(om.MFn.kMeshData):
            return om.MFnMesh(geom_mobj)
        if geom_mobj.hasFn(om.MFn.kNurbsCurveData):
            return om.MFnNurbsCurve(geom_mobj)
        if geom_mobj.hasFn(om.MFn.kNurbsSurfaceData):
            return om.MFnNurbsSurface(geom_mobj)
        if geom_mobj.hasFn(om.MFn.kSubdSurfaceData):
            return om.MFnSubd(geom_mobj)
        if geom_mobj.hasFn(om.MFn.kLatticeData):
            try:
                import maya.OpenMayaAnim as oma

                return oma.MFnLattice(geom_mobj)
            except Exception:
                return geom_mobj
    except Exception:
        pass
    return None


def _mfn_wrap_data(geom_mobj: "om.MObject", attr_type) -> Any:
    """Wrap a geometry data MObject (kMeshData, kNurbsCurveData, etc.)
    in the appropriate MFn type."""
    try:
        if attr_type == om.MFnData.kMesh:
            return om.MFnMesh(geom_mobj)
        if attr_type == om.MFnData.kNurbsCurve:
            return om.MFnNurbsCurve(geom_mobj)
        if attr_type == om.MFnData.kNurbsSurface:
            return om.MFnNurbsSurface(geom_mobj)
        if attr_type == om.MFnData.kSubdSurface:
            return om.MFnSubd(geom_mobj)
        if attr_type == om.MFnData.kLattice:
            # Lattice geometry — MFnLattice isn't in OpenMaya 1.0 for
            # all Maya versions. Return raw data.
            try:
                import maya.OpenMayaAnim as oma

                return oma.MFnLattice(geom_mobj)
            except Exception:
                return geom_mobj
    except Exception:
        pass
    # Unknown geometry type — return the raw MObject for advanced use.
    return geom_mobj


def _mfn_wrap_node(node_mobj: "om.MObject") -> Any:
    """Best-effort: if ``node_mobj`` is a shape, wrap it in the right
    MFn class so the user can read geometry from it."""
    try:
        if node_mobj.hasFn(om.MFn.kMesh):
            return om.MFnMesh(node_mobj)
        if node_mobj.hasFn(om.MFn.kNurbsCurve):
            return om.MFnNurbsCurve(node_mobj)
        if node_mobj.hasFn(om.MFn.kNurbsSurface):
            return om.MFnNurbsSurface(node_mobj)
        if node_mobj.hasFn(om.MFn.kSubdiv):
            return om.MFnSubd(node_mobj)
        if node_mobj.hasFn(om.MFn.kLattice):
            try:
                import maya.OpenMayaAnim as oma

                return oma.MFnLattice(node_mobj)
            except Exception:
                pass
    except Exception:
        pass
    return node_mobj
