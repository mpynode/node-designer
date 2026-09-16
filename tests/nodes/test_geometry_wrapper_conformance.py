"""Conformance matrix for the unified geometry I/O wrapper.

Turns "geometry I/O should be universal" into "provably universal": for every
node type a user can add geometry attributes to, assert that a geometry INPUT
(single AND array) arrives as a usable wrapper (``.points`` works) and a
geometry OUTPUT (single AND array) accepts and writes a wrapper -- for mesh,
NURBS curve, and NURBS surface.

Coverage:
  * mPyNode (the general node): the FULL matrix -- {mesh, curve, surface} x
    {single, array} x {input, output}.
  * mPyConstraint / mPyFile (other api2 general nodes): mesh input + output.
  * mPyMesh / mPyNurbsCurve / mPyNurbsSurface (generators): geometry INPUT.
  * mPyDeformer (api1 family): a geometry INPUT arrives as the wrapper AND the
    deformed handle exposes the same ``.points`` surface (in-place edit).

If a future base regresses the universality contract, a cell here fails.
"""
from __future__ import annotations

import unittest

from tests._setup import ensure_plugins_loaded, standalone_init

standalone_init()

import maya.cmds as mc
import maya.api.OpenMaya as om
import numpy as np


def ensure_plugins():
    ensure_plugins_loaded()


# geo_kind -> (input attr_type, source-shape builder -> shape, output plug on the
# source used to feed a typed geo input, count-expression, min expected count)
def _make_cube():
    x = mc.polyCube(sx=2, sy=2, sz=2, ch=False)[0]
    return mc.listRelatives(x, s=True, f=True)[0]


def _make_circle():
    x = mc.circle(ch=False, s=8)[0]
    return mc.listRelatives(x, s=True, f=True)[0]


def _make_sphere():
    x = mc.sphere(ch=False, sections=4, spans=4)[0]
    return mc.listRelatives(x, s=True, f=True)[0]


GEO = {
    "mesh": {
        "type":       "mesh",
        "make":       _make_cube,
        "src_plug":   ".worldMesh[0]",
        "count_expr": "int(g.points.shape[0])",
        "min":        8,
    },
    "nurbsCurve": {
        "type":       "nurbsCurve",
        "make":       _make_circle,
        "src_plug":   ".worldSpace[0]",
        "count_expr": "int(g.points.shape[0])",
        "min":        3,
    },
    "nurbsSurface": {
        "type":       "nurbsSurface",
        "make":       _make_sphere,
        "src_plug":   ".worldSpace[0]",
        "count_expr": "int(g.num_u * g.num_v)",
        "min":        4,
    },
}

# geo_kind -> (data function set, count getter) for reading an output plug.
_OUT_READERS = {
    "mesh":         (om.MFnMesh, lambda fn: fn.numVertices),
    "nurbsCurve":   (om.MFnNurbsCurve, lambda fn: fn.numCVs),
    "nurbsSurface": (om.MFnNurbsSurface, lambda fn: fn.numCVsInU * fn.numCVsInV),
}


def _read_geo_output_count(node, plug, kind, index=None):
    # force the output geometry to evaluate: an unevaluated typed-geo output
    # plug raises kFailure on asMObject, the quirk plug_geometry.py handles.
    plug_name = "%s.%s[%d]" % (node, plug, index) if index is not None else "%s.%s" % (node, plug)
    try:
        mc.dgeval(plug_name)
    except Exception:
        pass
    dep = om.MFnDependencyNode(om.MSelectionList().add(node).getDependNode(0))
    p   = dep.findPlug(plug, False)
    if index is not None:
        p = p.elementByLogicalIndex(index)
    try:
        mobj = p.asMObject()
    except RuntimeError:
        return 0
    if mobj.isNull():
        return 0
    fn_cls, getter = _OUT_READERS[kind]
    return int(getter(fn_cls(mobj)))


class GeometryWrapperConformance(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins()

    # ------------------------------------------------------------------
    # Generic cell drivers
    # ------------------------------------------------------------------
    def _make_node(self, node_type):
        """Return (wrapper, node_name). Supports the api2 general node types."""
        if node_type == "mPyNode":
            from mpynode.wrappers._mpy_node import MPyNode
            w = MPyNode.create(name="conf_node")
        elif node_type == "mPyConstraint":
            from mpynode._node_registry import wrap_node
            n = mc.createNode("mPyConstraint", name="conf_con")
            w = wrap_node(n, "mPyConstraint")
        elif node_type == "mPyFile":
            from mpynode.wrappers.mpy_file import MPyFile
            w = MPyFile.create(name="conf_file")
        elif node_type == "mPyMesh":
            from mpynode.wrappers.mpy_mesh import MPyMesh
            w = MPyMesh.create(name="conf_mesh")
        elif node_type == "mPyNurbsCurve":
            from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
            w = MPyNurbsCurve.create(name="conf_curve")
        elif node_type == "mPyNurbsSurface":
            from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface
            w = MPyNurbsSurface.create(name="conf_surf")
        else:
            raise ValueError(node_type)
        return w, w.get_name()

    def check_input(self, node_type, kind, array):
        """A geo INPUT (single/array) arrives as a usable wrapper (.points)."""
        g = GEO[kind]
        w, node = self._make_node(node_type)
        w.add_input_attr("inGeo", g["type"], is_array=array)
        w.add_output_attr("cnt", "int")
        if array:
            expr = (
                "L = [x for x in self.inGeo if x is not None]\n"
                "self.cnt = sum(%s for g in L)\n" % g["count_expr"]
            )
        else:
            expr = (
                "g = self.inGeo\n"
                "self.cnt = (%s) if g is not None else -1\n" % g["count_expr"]
            )
        w.set_compute_expression(expr)
        n_src = 3 if array else 1
        for i in range(n_src):
            shp = g["make"]()
            if array:
                mc.connectAttr(shp + g["src_plug"], "%s.inGeo[%d]" % (node, i), force=True)
            else:
                mc.connectAttr(shp + g["src_plug"], node + ".inGeo", force=True)
        got = mc.getAttr(node + ".cnt")
        self.assertGreaterEqual(
            got, g["min"] * (n_src if array else 1),
            msg="%s %s %s INPUT: wrapper unusable (cnt=%s)"
            % (node_type, kind, "array" if array else "single", got),
        )

    def check_output(self, node_type, kind, array):
        """A geo OUTPUT (single/array) accepts + writes a wrapper (copy of an
        input, scaled) -- proving assignment marshals + writes on this node."""
        g = GEO[kind]
        w, node = self._make_node(node_type)
        w.add_input_attr("inGeo", g["type"], is_array=array)
        w.add_output_attr("outGeo", g["type"], is_array=array)
        if array:
            expr = (
                "out = []\n"
                "for x in self.inGeo:\n"
                "    if x is None:\n"
                "        continue\n"
                "    c = x.copy(); c.points = c.points * 2.0; out.append(c)\n"
                "self.outGeo = out\n"
            )
        else:
            expr = (
                "g = self.inGeo\n"
                "if g is not None:\n"
                "    c = g.copy(); c.points = c.points * 2.0; self.outGeo = c\n"
            )
        w.set_compute_expression(expr)
        n_src = 3 if array else 1
        for i in range(n_src):
            shp = g["make"]()
            if array:
                mc.connectAttr(shp + g["src_plug"], "%s.inGeo[%d]" % (node, i), force=True)
            else:
                mc.connectAttr(shp + g["src_plug"], node + ".inGeo", force=True)
        for i in range(n_src):
            oc = _read_geo_output_count(node, "outGeo", kind, index=i if array else None)
            self.assertGreater(
                oc, 0,
                msg="%s %s %s OUTPUT: nothing written (count=%s)"
                % (node_type, kind, "array" if array else "single", oc),
            )

    # ------------------------------------------------------------------
    # mPyNode: the FULL matrix
    # ------------------------------------------------------------------
    def test_mpynode_full_matrix(self):
        for kind in ("mesh", "nurbsCurve", "nurbsSurface"):
            for array in (False, True):
                with self.subTest(kind=kind, array=array, dir="in"):
                    self.check_input("mPyNode", kind, array)
                with self.subTest(kind=kind, array=array, dir="out"):
                    self.check_output("mPyNode", kind, array)

    # ------------------------------------------------------------------
    # Other api2 general node types: mesh in + out (single)
    # ------------------------------------------------------------------
    def test_other_api2_nodes_mesh_io(self):
        for node_type in ("mPyConstraint", "mPyFile"):
            with self.subTest(node=node_type, dir="in"):
                self.check_input(node_type, "mesh", False)
            with self.subTest(node=node_type, dir="out"):
                self.check_output(node_type, "mesh", False)

    # ------------------------------------------------------------------
    # Generators: a geometry INPUT is usable (they already have native geo out)
    # ------------------------------------------------------------------
    def test_generators_geo_input(self):
        for node_type, kind in (
            ("mPyMesh", "mesh"),
            ("mPyNurbsCurve", "nurbsCurve"),
            ("mPyNurbsSurface", "nurbsSurface"),
        ):
            with self.subTest(node=node_type, kind=kind):
                self.check_input(node_type, kind, False)

    # ------------------------------------------------------------------
    # Deformer (api1 family): geo input wrapper + unified deformed handle
    # ------------------------------------------------------------------
    def test_deformer_input_wrapper_and_handle_points(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        box  = mc.polyCube(sx=1, sy=1, sz=1, ch=False, name="confDefBox")[0]
        bshp = mc.listRelatives(box, s=True, f=True)[0]
        rest = np.array(om.MFnMesh(om.MSelectionList().add(bshp).getDagPath(0))
                        .getPoints(om.MSpace.kObject), dtype=np.float64)[:, :3]
        col  = mc.polySphere(sx=6, sy=6, r=1.0, ch=False, name="confCollider")[0]
        cshp = mc.listRelatives(col, s=True, f=True)[0]
        d    = MPyDeformer.create_on(box)
        d.add_input_attr("collider", "mesh")
        # Drive the deform from the collider's OBJECT-space vertex data (top
        # Y ~= radius). Object space is transform-independent, so this proves
        # the geo-input wrapper's .points carries real per-vertex data into
        # the api1 deformer without relying on worldMesh transform-baking,
        # which does not propagate through a plug read in headless mayapy.
        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "col = self.collider\n"
            "if col is not None:\n"
            "    dy = float(col.points[:, 1].max()) * 6.0\n"  # wrapper .points -> real vtx data
            "    p = mesh.points\n"                           # unified handle .points (read)
            "    p[:, 1] = p[:, 1] + dy\n"
            "    mesh.points = p\n"                           # in-place commit
        )
        mc.connectAttr(cshp + ".worldMesh[0]", d.get_name() + ".collider", force=True)
        mc.currentTime(10)  # distinct from the file-new default (1) -> forces eval
        out = np.array(om.MFnMesh(om.MSelectionList().add(bshp).getDagPath(0))
                       .getPoints(om.MSpace.kObject), dtype=np.float64)[:, :3]
        # collider top-Y ~= 1.0 -> every vert shifts up uniformly by ~6.0.
        self.assertTrue(np.allclose(out[:, 1] - rest[:, 1], out[0, 1] - rest[0, 1]))
        self.assertGreater(float(np.mean(out[:, 1] - rest[:, 1])), 4.0)


if __name__ == "__main__":
    unittest.main()
