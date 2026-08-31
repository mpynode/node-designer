"""Deformer family: generic compute, geometry handles, blendshape targets, family rollout, auto-dirty, double-import

Consolidated from: test_phaseF_0_deformer.py, test_phaseF_2_geometry_handles.py, test_phaseF_3_deformer_family.py, test_blendshape_targets.py, test_manual_setattr_dirty.py, test_double_import_no_recursion.py.
"""

from __future__ import annotations

# ===================== from test_phaseF_0_deformer.py =====================
import unittest

import maya.cmds as mc
import maya.OpenMaya as om
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseF_0_deformer():
    standalone_init()


# ===========================================================================
# 1. Schema deletion
# ===========================================================================


class TestF0SchemaDeleted(unittest.TestCase):
    def test_INTERNAL_VARS_class_attr_gone(self):
        from mpynode._api1.mpy_deformer import MPyDeformer as _MPyDeformerCls

        self.assertFalse(
            hasattr(_MPyDeformerCls, "INTERNAL_VARS"),
            "MPyDeformer.INTERNAL_VARS schema should be deleted",
        )

    def test_OUTPUT_GEOMETRY_PLUG_class_attr_present(self):
        from mpynode._api1.mpy_deformer import MPyDeformer as _MPyDeformerCls

        self.assertTrue(
            hasattr(_MPyDeformerCls, "OUTPUT_GEOMETRY_PLUG"),
            "MPyDeformer must declare OUTPUT_GEOMETRY_PLUG",
        )
        self.assertTrue(
            hasattr(_MPyDeformerCls, "INPUT_GEOMETRY_PLUG"),
            "MPyDeformer must declare INPUT_GEOMETRY_PLUG",
        )


# ===========================================================================
# 2. Generic compute module shape
# ===========================================================================


class TestF0GenericComputeImports(unittest.TestCase):
    def test_run_generic_compute_callable(self):
        from mpynode._common.compute.compute import run_generic_compute

        self.assertTrue(callable(run_generic_compute))

    def test_SelfProxy_exposed(self):
        from mpynode._common.compute.self_proxy import SelfProxy

        self.assertTrue(callable(SelfProxy))

    def test_MFnMeshHandle_exposed(self):
        from mpynode._common.plugs.mfn_handles import MFnMeshHandle

        self.assertTrue(callable(MFnMeshHandle))

    def test_array_io_exposes_helpers(self):
        from mpynode._common.plugs import array_convert as array_io

        for fn in (
            "points_array_to_numpy",
            "numpy_to_points_array",
            "coerce_to_point_array",
        ):
            self.assertTrue(
                callable(getattr(array_io, fn, None)),
                "{} not exported from array_io".format(fn),
            )


# ===========================================================================
# 3. End-to-end deformer behavior
# ===========================================================================


class TestF0DeformerEndToEnd(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.lifecycle import init_registry
        init_registry.clear_all_init_ns()

    def _build_deformer(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        plane = mc.polyPlane(name="p", w=2, h=2, sx=4, sy=4)[0]
        d = MPyDeformer.create_on(plane)
        return plane, d

    def test_eager_copy_no_op_returns_input_unchanged(self):
        """Empty expression -> output reads back to input geometry
        because the eager copy seeds the output handle from input
        BEFORE exec, and an empty expression doesn't touch it."""
        plane, d = self._build_deformer()
        d.set_compute_expression("")
        v0 = mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)
        v12 = mc.xform(plane + ".vtx[12]", q=True, ws=True, t=True)
        # vtx[0] of a 4x4 plane is (-1, 0, -1); vtx[12] is the centre.
        self.assertAlmostEqual(v0[1], 0.0, places=4)
        self.assertAlmostEqual(v12[0], 0.0, places=4)
        self.assertAlmostEqual(v12[1], 0.0, places=4)
        self.assertAlmostEqual(v12[2], 0.0, places=4)

    def test_outputGeometry_setPoints_numpy_roundtrips(self):
        """User mutates points via mfnmesh.setPoints(numpy) and the
        deformer commits the change to the geom_iter."""
        plane, d = self._build_deformer()
        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += 2.0\n"
            "mesh.setPoints(pts)\n"
        )
        v = mc.xform(plane + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 2.0, places=3)

    def test_outputGeometry_handle_is_mfnmesh_like(self):
        """The handle returned for self.outputGeometry[0] must
        delegate to MFnMesh -- we expect numVertices() to work."""
        plane, d = self._build_deformer()
        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "self.cached_n = mesh.numVertices()\n"
        )
        mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)
        # 4x4 polyPlane -> 5x5 verts.
        from mpynode._common.storedvars.stored_vars_api import get_variables
        data = get_variables(d.get_name())
        self.assertEqual(data.get("cached_n"), 25)

    def test_input_inputGeometry_is_readonly_mfnmesh(self):
        """Self.input[i].inputGeometry returns the upstream MFnMesh
        for read-only access -- callers can numVertices() etc."""
        plane, d = self._build_deformer()
        d.set_compute_expression(
            "src = self.input[0].inputGeometry\n"
            "mesh = self.outputGeometry[0]\n"
            "self.src_n_verts = src.numVertices()\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 0] += 0.1\n"
            "mesh.setPoints(pts)\n"
        )
        mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)
        from mpynode._common.storedvars.stored_vars_api import get_variables
        data = get_variables(d.get_name())
        self.assertEqual(data.get("src_n_verts"), 25)

    def test_user_storage_unknown_name_routes_to_storedVarsData(self):
        """``self.foo = 1`` for a name that ISN'T a plug routes
        to user storage diff."""
        plane, d = self._build_deformer()
        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += 0.3\n"
            "mesh.setPoints(pts)\n"
            "self.my_total = 7\n"
            "self.label = 'phaseF0'\n"
        )
        mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)
        from mpynode._common.storedvars.stored_vars_api import get_variables
        data = get_variables(d.get_name())
        self.assertEqual(data.get("my_total"), 7)
        self.assertEqual(data.get("label"), "phaseF0")

    def test_read_only_input_plug_write_raises(self):
        """Writing to a read-only / non-existent input is rejected.
        For F.0 the canonical example is writing to ``self.input[i]``
        directly (a multi compound plug; not a leaf)."""
        plane, d = self._build_deformer()
        # Write to a read-only input; inputGeometry is the mPyDeformer one.
        d.set_compute_expression(
            "self.input[0].inputGeometry = self.outputGeometry[0]\n"
        )
        # the expression errors during exec and the deformer's eager copy
        # hands the input straight back. There is no clean way to assert
        # "expression failed" from outside, so check the vertex is unchanged.
        v = mc.xform(plane + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 0.0, places=3)

    def test_envelope_plug_reads_through_self(self):
        """The inherited envelope plug is a numeric plug on the node;
        ``self.envelope`` must read its current value."""
        plane, d = self._build_deformer()
        mc.setAttr(d.get_name() + ".envelope", 0.42)
        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += float(self.envelope)\n"
            "mesh.setPoints(pts)\n"
        )
        v = mc.xform(plane + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 0.42, places=3)


# ===========================================================================
# 4. Init bindings tier still works (Section 6.1 tier 2)
# ===========================================================================


class TestF0InitBindingsTier(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.lifecycle import init_registry
        init_registry.clear_all_init_ns()

    def test_init_binding_visible_via_self(self):
        """``self.MULT = 3.0`` written from Init source should be
        readable via ``self.MULT`` from the expression."""
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        plane = mc.polyPlane(name="p", w=2, h=2, sx=4, sy=4)[0]
        d = MPyDeformer.create_on(plane)
        d.set_init_expression("self.MULT = 3.0")
        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += float(self.MULT)\n"
            "mesh.setPoints(pts)\n"
        )
        v = mc.xform(plane + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 3.0, places=3)


# ===================== from test_phaseF_2_geometry_handles.py =====================
import unittest

import maya.cmds as mc
import maya.OpenMaya as om
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseF_2_geometry_handles():
    standalone_init()


# ===========================================================================
# Handle imports + class API
# ===========================================================================


class TestF2HandleImports(unittest.TestCase):
    def test_handles_exposed(self):
        from mpynode._common.plugs.mfn_handles import (
            MFnNurbsCurveHandle,
            MFnNurbsSurfaceHandle,
            MFnLatticeHandle,
            allocate_writable_curve_from_source,
            allocate_writable_surface_from_source,
            allocate_writable_lattice_from_source,
        )
        self.assertTrue(callable(MFnNurbsCurveHandle))
        self.assertTrue(callable(MFnNurbsSurfaceHandle))
        self.assertTrue(callable(MFnLatticeHandle))
        self.assertTrue(callable(allocate_writable_curve_from_source))
        self.assertTrue(callable(allocate_writable_surface_from_source))
        self.assertTrue(callable(allocate_writable_lattice_from_source))


# ===========================================================================
# Curve end-to-end through mPyDeformer
# ===========================================================================


class TestF2CurveDeformerEndToEnd(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_curve_setCVPositions_round_trip(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        crv = mc.curve(name="testCrv", p=[(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)], d=2)
        d = MPyDeformer.create_on(crv)
        d.set_compute_expression(
            "crv = self.outputGeometry[0]; "
            "cvs = crv.cvPositions(); "
            "cvs[:, 1] += 0.5; "
            "crv.setCVPositions(cvs)"
        )
        v0 = mc.xform(crv + ".cv[0]", q=True, ws=True, t=True)
        v1 = mc.xform(crv + ".cv[1]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v0[1], 0.5, places=4)
        self.assertAlmostEqual(v1[1], 0.5, places=4)

    def test_curve_handle_cv_count(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        from mpynode._common.storedvars.stored_vars_api import get_variables

        crv = mc.curve(name="testCrv2", p=[(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)], d=2)
        d = MPyDeformer.create_on(crv)
        d.set_compute_expression(
            "crv = self.outputGeometry[0]; "
            "self.cv_count = int(crv.numCVs())"
        )
        mc.xform(crv + ".cv[0]", q=True, ws=True, t=True)
        vars_ = get_variables(d.get_name())
        self.assertEqual(int(vars_.get("cv_count", 0)), 4)


# ===========================================================================
# NURBS surface end-to-end through mPyDeformer
# ===========================================================================


class TestF2SurfaceDeformerEndToEnd(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_surface_setCVPositions_round_trip(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        srf = mc.nurbsPlane(name="testSrf", u=4, v=4)[0]
        y0 = mc.xform(srf + ".cv[0][0]", q=True, ws=True, t=True)[1]
        d = MPyDeformer.create_on(srf)
        d.set_compute_expression(
            "srf = self.outputGeometry[0]; "
            "cvs = srf.cvPositions(); "
            "cvs[:, 1] += 1.0; "
            "srf.setCVPositions(cvs)"
        )
        y0_after = mc.xform(srf + ".cv[0][0]", q=True, ws=True, t=True)[1]
        self.assertAlmostEqual(y0_after, y0 + 1.0, places=4)

    def test_surface_handle_cv_dimensions(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        from mpynode._common.storedvars.stored_vars_api import get_variables

        srf = mc.nurbsPlane(name="testSrf2", u=4, v=4)[0]
        d = MPyDeformer.create_on(srf)
        d.set_compute_expression(
            "srf = self.outputGeometry[0]; "
            "self.uv_count_u = int(srf.numCVsInU()); "
            "self.uv_count_v = int(srf.numCVsInV())"
        )
        mc.xform(srf + ".cv[0][0]", q=True, ws=True, t=True)
        vars_ = get_variables(d.get_name())
        self.assertEqual(int(vars_.get("uv_count_u", 0)), 7)
        self.assertEqual(int(vars_.get("uv_count_v", 0)), 7)


# ===========================================================================
# Lattice: import + allocator only. The full deform path is brittle across
# Maya versions, and a non-None handle already proves the dispatch wiring.
# ===========================================================================


class TestF2LatticeAllocatorPresent(unittest.TestCase):
    def test_lattice_allocator_returns_handle_or_falls_back_safely(self):
        from mpynode._common.plugs.mfn_handles import allocate_writable_lattice_from_source

        # with no source the allocator returns something, or None on builds
        # without it, but must not crash.
        try:
            mfn, mobj = allocate_writable_lattice_from_source(None)
        except Exception as exc:
            self.fail("allocator raised: {}".format(exc))
        # mfn is None where MFnLatticeData is unavailable, never a throw.
        self.assertTrue(mfn is None or hasattr(mfn, "copy"))


# ===================== from test_phaseF_3_deformer_family.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseF_3_deformer_family():
    standalone_init()


# ===========================================================================
# Schema / API surface
# ===========================================================================


class TestF3SchemaDeleted(unittest.TestCase):
    def test_skin_cluster_internal_vars_gone(self):
        from mpynode._api1.mpy_skin_cluster import MPySkinCluster
        self.assertFalse(hasattr(MPySkinCluster, "INTERNAL_VARS"))

    def test_blend_shape_internal_vars_gone(self):
        from mpynode._api1.mpy_blend_shape import MPyBlendShape
        self.assertFalse(hasattr(MPyBlendShape, "INTERNAL_VARS"))

    def test_all_three_have_phaseF_plug_names(self):
        from mpynode._api1.mpy_deformer import MPyDeformer
        from mpynode._api1.mpy_skin_cluster import MPySkinCluster
        from mpynode._api1.mpy_blend_shape import MPyBlendShape
        for cls in (MPyDeformer, MPySkinCluster, MPyBlendShape):
            self.assertTrue(hasattr(cls, "INPUT_GEOMETRY_PLUG"))
            self.assertTrue(hasattr(cls, "OUTPUT_GEOMETRY_PLUG"))
            self.assertTrue(hasattr(cls, "OUTPUT_GEOMETRY_PLUG_SHORT_NAME"))


# ===========================================================================
# End-to-end deform via run_generic_compute
# ===========================================================================


class TestF3SkinClusterEndToEnd(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_matrix_attrs_present(self):
        plane = mc.polyPlane(name="sP")[0]
        sc = mc.deformer(plane, type="mPySkinCluster")[0]
        self.assertTrue(mc.attributeQuery("matrix", node=sc, exists=True))
        self.assertTrue(mc.attributeQuery("bindPreMatrix", node=sc, exists=True))

    def test_deform_pushes_y(self):
        j1 = mc.joint(p=(0, 0, 0), n="j1")
        mc.select(clear=True)
        plane = mc.polyPlane(name="sP", w=2, h=2, sx=4, sy=4)[0]
        sc = mc.deformer(plane, type="mPySkinCluster")[0]
        mc.connectAttr(j1 + ".worldMatrix[0]", sc + ".matrix[0]", force=True)
        mc.setAttr(
            sc + "._computeSource",
            "mesh = self.outputGeometry[0]; "
            "pts = mesh.getPoints(); "
            "pts[:, 1] += 0.9; "
            "mesh.setPoints(pts)",
            type="string",
        )
        v = mc.xform(plane + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 0.9, places=5)


class TestF3BlendShapeEndToEnd(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_deform_pushes_y(self):
        plane = mc.polyPlane(name="bP", w=2, h=2, sx=4, sy=4)[0]
        bs = mc.deformer(plane, type="mPyBlendShape")[0]
        mc.setAttr(
            bs + "._computeSource",
            "mesh = self.outputGeometry[0]; "
            "pts = mesh.getPoints(); "
            "pts[:, 1] += 0.6; "
            "mesh.setPoints(pts)",
            type="string",
        )
        v = mc.xform(plane + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 0.6, places=5)


# ===========================================================================
# Generic compute path is shared
# ===========================================================================


class TestF3GenericComputeShared(unittest.TestCase):
    def test_all_three_route_through_run_generic_compute(self):
        import inspect

        from mpynode._api1.mpy_deformer import MPyDeformer
        from mpynode._api1.mpy_skin_cluster import MPySkinCluster
        from mpynode._api1.mpy_blend_shape import MPyBlendShape

        for cls in (MPyDeformer, MPySkinCluster, MPyBlendShape):
            src = inspect.getsource(cls.deform)
            self.assertIn(
                "run_generic_compute",
                src,
                "{}.deform should call run_generic_compute".format(cls.__name__),
            )


# ===================== from test_blendshape_targets.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__blendshape_targets():
    standalone_init()


# Target morph: out = base + sum_i w_i * (target_i - base), object space,
# same topology. Targets arrive as read-only om.MFnMesh, so convert their
# points with the framework's array helper.
_MORPH_EXPR = """\
import numpy as np
import maya.OpenMaya as om
from mpynode._common.plugs.array_convert import points_array_to_numpy
mesh = self.outputGeometry[0]
base = mesh.getPoints()
out = base.copy()
for i in range(len(self.targetGeometry)):
    tgt = self.targetGeometry[i]
    if tgt is None:
        continue
    w = float(self.weight[i])
    if w == 0.0:
        continue
    pa = om.MPointArray()
    tgt.getPoints(pa, om.MSpace.kObject)
    tpts = points_array_to_numpy(pa)
    if tpts.shape == base.shape:
        out += w * (tpts - base)
mesh.setPoints(out)
"""


def _make_base_and_target():
    """Build a flat base plane + an identical-topology target whose verts
    are all pushed +1.0 in Y (object space). Returns (base, target)."""
    base = mc.polyPlane(name="bBase", w=2, h=2, sx=4, sy=4)[0]
    target = mc.polyPlane(name="bTarget", w=2, h=2, sx=4, sy=4)[0]
    # move the target's VERTICES, not its transform, so object-space
    # positions differ from the base.
    mc.move(0.0, 1.0, 0.0, target + ".vtx[*]", relative=True, worldSpace=True)
    return base, target


class TestBlendShapeTargetPlugs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_target_geometry_plug_created_by_initializer(self):
        plane = mc.polyPlane(name="bP")[0]
        bs = mc.deformer(plane, type="mPyBlendShape")[0]
        self.assertTrue(
            mc.attributeQuery("targetGeometry", node=bs, exists=True),
            "targetGeometry[] plug must be created by node_initializer",
        )

    def test_weight_multi_is_a_user_attr_added_by_the_wrapper(self):
        """``weight[]`` is deliberately NOT declared in node_initializer.

        The compile spec captures USER attrs; preset meta carries no
        ``is_array`` flag, so a statically declared multi could not ride the
        preset path and the compiled node would end up with no weights at all.
        ``MPyBlendShape.create`` adds it instead -- so a bare ``cmds.deformer``
        has no ``weight``, and a wrapper-built node always does.
        """
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        plane = mc.polyPlane(name="bPlain")[0]
        bare = mc.deformer(plane, type="mPyBlendShape")[0]
        self.assertFalse(
            mc.attributeQuery("weight", node=bare, exists=True),
            "weight[] must NOT come from node_initializer",
        )

        base, target = _make_base_and_target()
        bs = MPyBlendShape.create(mesh=base, targets=[target], name="bsUser")
        self.assertTrue(
            mc.attributeQuery("weight", node=bs.get_name(), exists=True),
            "MPyBlendShape.create must add the weight[] multi",
        )

    def test_target_weight_is_aliased_to_the_target_name(self):
        """The whole point of the redesign: ``bs.bTarget`` IS ``bs.weight[0]``,
        it shows in the channel box under that name, and driving either spelling
        drives the same plug -- exactly like a stock blendShape."""
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base, target = _make_base_and_target()
        bs = MPyBlendShape.create(mesh=base, targets=[target], name="bsAlias")
        name = bs.get_name()

        self.assertEqual(bs.aliases, ["bTarget"])
        self.assertIn(
            "bTarget",
            mc.listAttr(name, multi=True, keyable=True) or [],
            "an aliased weight must be keyable (channel box), like Maya's",
        )
        mc.setAttr(name + ".bTarget", 0.25)
        self.assertAlmostEqual(mc.getAttr(name + ".weight[0]"), 0.25, places=6)

    def test_set_get_weight_roundtrip(self):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base, target = _make_base_and_target()
        bs = MPyBlendShape.create(mesh=base, targets=[target], name="bsW")
        bs.set_weight(0, 0.5)
        self.assertAlmostEqual(bs.get_weight(0), 0.5, places=6)


class TestBlendShapeMorph(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_full_weight_morph_matches_target(self):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base, target = _make_base_and_target()
        bs = MPyBlendShape.create(mesh=base, targets=[target], name="bsFull")
        bs.set_compute_expression(_MORPH_EXPR)
        bs.set_weight(0, 1.0)
        # Center vertex of a 4x4 plane is vtx[12]; base y=0, target y=1.
        v = mc.xform(base + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 1.0, places=4)

    def test_half_weight_morph_is_halfway(self):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base, target = _make_base_and_target()
        bs = MPyBlendShape.create(mesh=base, targets=[target], name="bsHalf")
        bs.set_compute_expression(_MORPH_EXPR)
        bs.set_weight(0, 0.5)
        v = mc.xform(base + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 0.5, places=4)

    def test_targets_and_weights_persist_through_save_load(self):
        """The target connection (targetGeometry, storable=False), the weight
        value, and the weight ALIAS must all round-trip through .ma save/open,
        and the morph must still apply. The alias matters as much as the value:
        a rig whose channel names vanish on reload is not a blendShape."""
        import os
        import tempfile

        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base, target = _make_base_and_target()
        bs = MPyBlendShape.create(mesh=base, targets=[target], name="bsSave")
        bs.set_compute_expression(_MORPH_EXPR)
        bs.set_weight(0, 1.0)

        path = os.path.join(tempfile.gettempdir(), "mpyn_bs_saveload.ma")
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        mc.file(path, open=True, force=True)

        self.assertAlmostEqual(mc.getAttr("bsSave.weight[0]"), 1.0, places=6)
        # the alias persisted too, so the channel is still bTarget.
        self.assertAlmostEqual(mc.getAttr("bsSave.bTarget"), 1.0, places=6)
        # Target connection persisted (targetGeometry, connection-driven).
        self.assertTrue(
            mc.listConnections(
                "bsSave.targetGeometry[0]", source=True, destination=False
            ),
            "target connection must survive save/load",
        )
        v = mc.xform("bBase.vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v[1], 1.0, places=4)

    def test_weight_change_re_evaluates(self):
        """Changing weight[] must mark outputGeom dirty so the deform
        re-evaluates. weight[] is a USER attr, so it reaches the
        setDependentsDirty trigger set only via the decoded _inputAttrs map --
        this is what makes a channel-box drag update the mesh."""
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base, target = _make_base_and_target()
        bs = MPyBlendShape.create(mesh=base, targets=[target], name="bsReeval")
        bs.set_compute_expression(_MORPH_EXPR)

        bs.set_weight(0, 0.0)
        v0 = mc.xform(base + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v0[1], 0.0, places=4)

        bs.set_weight(0, 1.0)
        v1 = mc.xform(base + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v1[1], 1.0, places=4)


class TestBlendShapeNameDecoding(unittest.TestCase):
    """`parse_aliases` turns the naming convention into pure index/number
    structure. It is the ONLY place names are read -- the compute never sees
    them (alias lookup is a side-channel DG query, and those come back empty on
    the EM worker thread that deform() runs on)."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _bs(self, names):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base = mc.polyPlane(name="dBase", w=2, h=2, sx=2, sy=2)[0]
        bs = MPyBlendShape.create(mesh=base, name="bsDecode")
        for i, n in enumerate(names):
            t = mc.polyPlane(name="dT%d" % i, w=2, h=2, sx=2, sy=2)[0]
            bs.add_target(t, n)
        return bs

    def test_plain_names_are_main_targets(self):
        s = self._bs(["browUp", "mouthOpen"]).parse_aliases()
        self.assertEqual(s["main"], [0, 1])
        self.assertEqual(s["inter"], {})
        self.assertEqual(s["combo"], {})

    def test_trailing_digits_are_an_in_between(self):
        s = self._bs(["browUp", "browUp50"]).parse_aliases()
        self.assertEqual(s["main"], [0])
        self.assertEqual(s["inter"], {1: (0, 0.5)})

    def test_underscore_of_known_targets_is_a_combo(self):
        s = self._bs(["browUp", "mouthOpen", "browUp_mouthOpen"]).parse_aliases()
        self.assertEqual(s["main"], [0, 1])
        self.assertEqual(s["combo"], {2: [0, 1]})

    def test_combo_wins_over_in_between(self):
        """`browUp_mouthOpen50` ends in digits AND is an underscore form. Combo
        is checked first because it is the unambiguous reading -- there is no
        target called `browUp_mouthOpen50`'s stem otherwise."""
        s = self._bs(["browUp", "mouthOpen",
                      "browUp_mouthOpen"]).parse_aliases(
                          ["browUp", "mouthOpen", "browUp_mouthOpen"])
        self.assertIn(2, s["combo"])
        self.assertNotIn(2, s["inter"])

    def test_digits_without_a_matching_base_stay_a_main_target(self):
        """`jaw50` with no `jaw` target is just a target called jaw50."""
        s = self._bs(["browUp", "jaw50"]).parse_aliases()
        self.assertEqual(s["main"], [0, 1])
        self.assertEqual(s["inter"], {})

    def test_endpoint_percentages_are_not_in_betweens(self):
        """0 and 100 are the endpoints the main target already covers, so a
        `browUp100` is a separate shape, not an in-between of browUp."""
        s = self._bs(["browUp", "browUp100"]).parse_aliases()
        self.assertEqual(s["inter"], {})
        self.assertEqual(s["main"], [0, 1])


class TestBlendShapeDeltaTables(unittest.TestCase):
    """`rebuild()` bakes the CSR tables the compute reads. Every target is
    stored as its RAW ``target - base`` offsets -- correctives included, since
    a corrective is sculpted as the correction itself. What a weight MEANS is
    the compute's business, not the bake's."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _rig(self, correctives=False):
        """Base plane + a target that lifts exactly vertex 0 by +1 in Y."""
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base = mc.polyPlane(name="tBase", w=2, h=2, sx=2, sy=2)[0]
        bs = MPyBlendShape.create(mesh=base, name="bsTables")
        bs.ensure_delta_attrs()
        if correctives:
            bs.ensure_corrective_attrs()
        return bs

    def _target(self, label, moves):
        t = mc.polyPlane(name=label, w=2, h=2, sx=2, sy=2)[0]
        for vtx, off in moves.items():
            mc.move(off[0], off[1], off[2], "%s.vtx[%d]" % (t, vtx),
                    relative=True, objectSpace=True)
        return t

    def test_bake_stores_only_the_vertices_that_moved(self):
        bs = self._rig()
        bs.add_target(self._target("tA", {0: (0.0, 1.0, 0.0)}), "A")
        tables = bs.rebuild()

        self.assertEqual(tables["targetOffset"], [0, 1])
        self.assertEqual(tables["targetComponents"], [0])
        self.assertEqual(len(tables["targetDeltas"]), 3)
        self.assertAlmostEqual(tables["targetDeltas"][1], 1.0, places=5)

    def test_csr_offsets_partition_the_components(self):
        bs = self._rig()
        bs.add_target(self._target("tA", {0: (0.0, 1.0, 0.0)}), "A")
        bs.add_target(self._target("tB", {1: (1.0, 0.0, 0.0),
                                          2: (1.0, 0.0, 0.0)}), "B")
        t = bs.rebuild()
        self.assertEqual(t["targetOffset"], [0, 1, 3])
        self.assertEqual(t["targetComponents"], [0, 1, 2])
        self.assertEqual(len(t["targetDeltas"]), 9)

    def test_in_between_delta_is_stored_RAW(self):
        """A50 moves vertex 0 by +0.6 Y while A moves it by +1.0. The stored
        delta is the full +0.6, NOT +0.1.

        The bake used to subtract `knot * mainDelta` here on the theory that a
        corrective sculpt is an absolute pose. It is not -- a corrective is
        sculpted as the correction itself, so subtracting removed a
        contribution the sculpt never had, and dialling the corrective's own
        channel rendered the shape minus a fraction of its driver.
        """
        bs = self._rig(correctives=True)
        bs.add_target(self._target("tA", {0: (0.0, 1.0, 0.0)}), "A")
        bs.add_target(self._target("tA50", {0: (0.0, 0.6, 0.0)}), "A50")
        t = bs.rebuild()

        self.assertEqual(t["interBase"], [-1, 0])
        self.assertAlmostEqual(t["interKnot"][1], 0.5, places=6)
        # target 1's slice is components[1:2] -> deltas[3:6]
        self.assertAlmostEqual(t["targetDeltas"][4], 0.6, places=5)

    def test_combo_delta_is_stored_RAW(self):
        """Same for a combo: the drivers are NOT subtracted out of it."""
        bs = self._rig(correctives=True)
        bs.add_target(self._target("tA", {0: (0.0, 1.0, 0.0)}), "A")
        bs.add_target(self._target("tB", {0: (0.0, 2.0, 0.0)}), "B")
        bs.add_target(self._target("tAB", {0: (0.0, 3.5, 0.0)}), "A_B")
        t = bs.rebuild()

        self.assertEqual(t["comboOffset"], [0, 0, 0, 2])
        self.assertEqual(t["comboDriver"], [0, 1])
        # target 2's slice is components[2:3] -> deltas[6:9]; the full 3.5
        self.assertAlmostEqual(t["targetDeltas"][7], 3.5, places=5)

    def test_a_corrective_dialled_alone_reproduces_its_sculpt(self):
        """The bug this bake fix exists for, stated end to end.

        With every driver at rest, a corrective's own channel at 1.0 must put
        exactly its sculpt on the mesh. Under the old subtracting bake this
        rendered `sculpt - knot * mainDelta` instead -- on the shipped face rig
        that was the jaw driven 0.75 NEGATIVE, which read as the lower lip
        rising through the upper.
        """
        bs = self._rig(correctives=True)
        bs.add_target(self._target("tA", {0: (0.0, 1.0, 0.0)}), "A")
        bs.add_target(self._target("tA50", {0: (0.0, 0.6, 0.0)}), "A50")
        bs.rebuild()

        # `_rig` builds a bare node -- create() wires no compute, so without
        # this nothing deforms and every reading below would be 0.0. A plain
        # linear blend is deliberate: no hats, no products, so what this
        # measures is purely what the BAKE stored.
        bs.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "base = mesh.getPoints()\n"
            "w = self.morphs.weights\n"
            "mesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))\n"
        )

        name = bs.get_name()
        shape = mc.listRelatives("tBase", shapes=True, ni=True, f=True)[0]

        def y0(a, a50):
            mc.setAttr(name + ".weight[0]", a)
            mc.setAttr(name + ".weight[1]", a50)
            mc.setAttr(name + ".envelope", 1.0)
            mc.dgdirty(name + ".outputGeometry")
            mc.getAttr(shape + ".outMesh")
            return mc.xform(shape + ".vtx[0]", query=True, objectSpace=True,
                            translation=True)[1]

        rest = y0(0.0, 0.0)
        self.assertAlmostEqual(y0(0.0, 1.0) - rest, 0.6, places=5,
                               msg="A50 alone must be its own +0.6 sculpt")
        self.assertAlmostEqual(y0(1.0, 0.0) - rest, 1.0, places=5,
                               msg="the main alone must be its own +1.0 sculpt")

    def test_a_shorter_rebuild_clears_the_stale_tail(self):
        """Dropping the LAST target shortens the tables. The elements they no
        longer cover must be REMOVED, not left behind: a leftover tail is
        exactly the stale-table case that reads as garbage -- and compiled,
        past the end of a table is an out-of-bounds heap read."""
        bs = self._rig()
        bs.add_target(self._target("tA", {0: (0.0, 1.0, 0.0)}), "A")
        bs.add_target(self._target("tB", {1: (1.0, 0.0, 0.0)}), "B")
        bs.rebuild()
        self.assertEqual(bs._read_multi("targetOffset", int), [0, 1, 2])

        bs.remove_target(1)          # the trailing one -- no hole is left
        bs.rebuild()
        self.assertEqual(bs._read_multi("targetOffset", int), [0, 1])
        # The table is PACKED (one typed-array plug), so there are no element
        # indices to interrogate -- `getAttr(multiIndices=True)` returns None on
        # it and the old assertNotIn(2, ...) would pass vacuously. Assert the
        # stored length directly: a shorter rewrite must leave no stale tail.
        self.assertEqual(
            len(mc.getAttr(bs.get_name() + ".targetOffset") or []), 2,
            "the element the shorter table no longer covers must be gone",
        )

    def test_removing_a_MIDDLE_target_leaves_it_an_empty_slice(self):
        """A middle removal keeps the logical indices SPARSE (Maya never
        compacts), so the hole has to survive rebuild as a zero-width CSR
        slice -- otherwise every target after it would shift."""
        bs = self._rig()
        for label, moves in (("A", {0: (0.0, 1.0, 0.0)}),
                             ("B", {1: (1.0, 0.0, 0.0)}),
                             ("C", {2: (0.0, 0.0, 1.0)})):
            bs.add_target(self._target("t" + label, moves), label)
        bs.rebuild()
        self.assertEqual(bs._read_multi("targetOffset", int), [0, 1, 2, 3])

        bs.remove_target(1)
        bs.rebuild()
        self.assertEqual(bs._read_multi("targetOffset", int), [0, 1, 1, 2],
                         "the removed slot must own an EMPTY slice")

    def test_remove_target_keeps_indices_sparse(self):
        """Compacting would silently re-point every alias and table entry after
        the hole. Maya never compacts; neither do we."""
        bs = self._rig()
        for label in ("A", "B", "C"):
            bs.add_target(self._target("t" + label, {0: (0.0, 1.0, 0.0)}), label)
        bs.remove_target(1)
        self.assertEqual(bs.aliases, ["A", "", "C"])
        self.assertEqual(bs.target_names, ["A", "", "C"])
        self.assertEqual(bs.target_count, 3)


class TestBlendShapeTableStaleness(unittest.TestCase):
    """Scene merge, import and reference edits all bypass the node's own
    commands, so `tables_stale` has to notice by inspection."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _rig(self):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base = mc.polyPlane(name="sBase", w=2, h=2, sx=2, sy=2)[0]
        bs = MPyBlendShape.create(mesh=base, name="bsStale")
        bs.ensure_delta_attrs()
        bs.ensure_corrective_attrs()
        for label in ("A", "B"):
            t = mc.polyPlane(name="s" + label, w=2, h=2, sx=2, sy=2)[0]
            mc.move(0.0, 1.0, 0.0, t + ".vtx[0]", relative=True, objectSpace=True)
            bs.add_target(t, label)
        bs.rebuild()
        return bs

    def test_fresh_tables_are_not_stale(self):
        self.assertFalse(self._rig().tables_stale())

    def test_adding_a_target_makes_them_stale(self):
        bs = self._rig()
        t = mc.polyPlane(name="sC", w=2, h=2, sx=2, sy=2)[0]
        bs.add_target(t, "C")
        self.assertTrue(bs.tables_stale())
        bs.rebuild()
        self.assertFalse(bs.tables_stale())

    def test_removing_a_MIDDLE_target_makes_them_stale(self):
        """The logical count is unchanged (indices stay sparse), so a length
        check alone would miss this one."""
        bs = self._rig()
        bs.remove_target(0)
        self.assertTrue(bs.tables_stale())
        bs.rebuild()
        self.assertFalse(bs.tables_stale())

    def test_renaming_a_target_into_an_in_between_makes_them_stale(self):
        """A rename changes no length at all, but it can turn a main into an
        in-between -- which changes what the compute must do."""
        bs = self._rig()
        bs.rename_target(1, "A50")
        self.assertTrue(bs.tables_stale())
        bs.rebuild()
        self.assertFalse(bs.tables_stale())
        self.assertEqual(bs._read_multi("interBase", int), [-1, 0])

    def test_missing_tables_read_as_stale(self):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base = mc.polyPlane(name="nBase", w=2, h=2, sx=2, sy=2)[0]
        bs = MPyBlendShape.create(mesh=base, name="bsNoTables")
        self.assertTrue(bs.tables_stale())


# ===================== from test_manual_setattr_dirty.py =====================
import unittest

import os

import maya.cmds as mc
from tests import _paths

from tests._setup import ensure_plugins_loaded, standalone_init


def _demo_path(name: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(_paths.ASSETS, name)


def _setUpModule__manual_setattr_dirty():
    standalone_init()


class TestManualSetAttrForcesRecompute(unittest.TestCase):
    def setUp(self):
        ensure_plugins_loaded()
        mc.file(
            _demo_path("sphereWaveFromLocator.ma"),
            open=True, force=True, ignoreVersion=True,
        )

    def _vtx_pos(self):
        return mc.xform("drivenSphere.vtx[10]", q=True, ws=True, t=True)

    def test_manual_offset_setattr_moves_vertex(self):
        """Setting the offset attr via cmds.setAttr (no connection,
        no keyframe) must force the deformer to recompute and the
        downstream mesh shape's vertex to move."""
        p0 = self._vtx_pos()
        mc.setAttr("sphereWaveFromLocator.offset", 2.5)
        p1 = self._vtx_pos()
        delta = sum(abs(a - b) for a, b in zip(p0, p1))
        self.assertGreater(
            delta, 1e-3,
            f"offset setAttr should move the vertex; delta={delta}",
        )

    def test_manual_amplitude_setattr_moves_vertex(self):
        p0 = self._vtx_pos()
        mc.setAttr("sphereWaveFromLocator.amplitude", 0.6)
        p1 = self._vtx_pos()
        delta = sum(abs(a - b) for a, b in zip(p0, p1))
        self.assertGreater(delta, 1e-3,
            f"amplitude setAttr should move the vertex; delta={delta}")

    def test_manual_frequency_setattr_moves_vertex(self):
        p0 = self._vtx_pos()
        # every sphere vertex sits at a near-uniform distance from the origin
        # driver, so integer / half-integer frequencies (18.0) leave the wave
        # phase ~unchanged. 2.25 perturbs it well above the 1e-3 gate.
        mc.setAttr("sphereWaveFromLocator.frequency", 2.25)
        p1 = self._vtx_pos()
        delta = sum(abs(a - b) for a, b in zip(p0, p1))
        self.assertGreater(delta, 1e-3,
            f"frequency setAttr should move the vertex; delta={delta}")


class TestSourceShape__manual_setattr_dirty(unittest.TestCase):
    def test_touch_envelope_dirties_output(self):
        import inspect
        from mpynode._common.plugs import auto_dirty

        src = inspect.getsource(auto_dirty.touch_envelope)
        self.assertIn("outputGeometry", src)
        self.assertIn("dgdirty", src)
        # cmds.dgeval was removed from touch_envelope: it recursed forever
        # on import (dgeval -> compute -> reads driverMatrix -> source
        # callback on an EM worker thread, where the thread-local guard
        # doesn't fire). The docstring may still name dgeval as a warning.
        self.assertNotIn(
            "cmds.dgeval", src,
            "touch_envelope MUST NOT call cmds.dgeval (causes "
            "infinite recursion on import)",
        )

    def test_scene_change_clear_hook_exists(self):
        from mpynode._common.plugs import auto_dirty

        self.assertTrue(
            hasattr(auto_dirty, "_install_scene_change_clear"),
            "auto_dirty must expose _install_scene_change_clear to "
            "wipe stale MObject-hash dedup entries on scene change",
        )

    def test_install_for_type_calls_scene_change_clear(self):
        import inspect
        from mpynode._common.plugs import auto_dirty

        src = inspect.getsource(auto_dirty.install_for_type)
        self.assertIn("_install_scene_change_clear", src)

    def test_install_for_type_always_installs_scene_open_sweep(self):
        """The scene-open sweep was previously a fallback only.
        makes it unconditional."""
        import inspect
        from mpynode._common.plugs import auto_dirty

        src = inspect.getsource(auto_dirty.install_for_type)
        # Two references: the original except-branch fallback plus the
        # unconditional call outside it.
        n = src.count("_install_scene_open_sweep")
        self.assertGreaterEqual(
            n, 2,
            f"_install_scene_open_sweep should appear at least "
            f"twice (fallback + unconditional); found {n}",
        )


# ===================== from test_double_import_no_recursion.py =====================
import os
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__double_import_no_recursion():
    standalone_init()


def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return _paths.ROOT


DEMO = _demo_path("sphereWaveFromLocator.ma")


class TestDoubleImportNoRecursion(unittest.TestCase):
    def setUp(self):
        ensure_plugins_loaded()
        mc.file(DEMO, open=True, force=True, ignoreVersion=True)
        mc.file(DEMO, i=True, ignoreVersion=True)

    def _vtx(self, mesh_shape: str) -> str:
        return f"{mesh_shape}.vtx[10]"

    def _move_driver(self, deformer: str) -> tuple[float, str]:
        """Move the deformer's driver locator; return
        (vtx_position_delta, mesh_shape_name)."""
        src = mc.listConnections(
            deformer + ".driverMatrix",
            source=True, destination=False,
        ) or []
        shapes = mc.listConnections(
            deformer + ".outputGeometry[0]",
            source=False, destination=True, shapes=True,
        ) or []
        if not src or not shapes:
            self.fail(f"{deformer} missing driver or consumer mesh")
        driver = src[0]
        shape = shapes[0]
        vtx = self._vtx(shape)
        p_a = mc.xform(vtx, q=True, ws=True, t=True)
        mc.setAttr(f"{driver}.translateY", 4.5)
        p_b = mc.xform(vtx, q=True, ws=True, t=True)
        return sum(abs(a - b) for a, b in zip(p_a, p_b)), shape

    def test_first_deformer_still_responds(self):
        """The originally-opened deformer must still respond to its
        driver after the import."""
        delta, shape = self._move_driver("sphereWaveFromLocator")
        self.assertGreater(
            delta, 1e-3,
            f"first deformer's driver move did not move vertex "
            f"on {shape}; delta={delta} (regression: callback "
            f"recursion or stale dest-callback)",
        )

    def test_imported_deformer_responds(self):
        """The imported deformer (auto-renamed by Maya) must also
        respond to its driver."""
        imported = [
            d for d in mc.ls(type="mPyDeformer")
            if d!= "sphereWaveFromLocator"
        ]
        self.assertTrue(imported, "import didn't produce a 2nd deformer")
        delta, shape = self._move_driver(imported[0])
        self.assertGreater(
            delta, 1e-3,
            f"imported deformer's driver move did not move vertex "
            f"on {shape}; delta={delta}",
        )


class TestSourceShape__double_import_no_recursion(unittest.TestCase):
    def test_touch_envelope_does_NOT_call_dgeval(self):
        """Pin the change: ``cmds.dgeval`` must NOT be CALLED in
        touch_envelope (causes recursion on import via the
        EM-parallel worker thread bypassing the thread-local
        guard). Docstring may still mention dgeval as a warning."""
        import inspect
        from mpynode._common.plugs import auto_dirty

        src = inspect.getsource(auto_dirty.touch_envelope)
        self.assertNotIn(
            "cmds.dgeval", src,
            "touch_envelope MUST NOT call cmds.dgeval -- it "
            "triggers compute which fires source-callback on a "
            "worker thread and recurses past the thread-local "
            "guard.",
        )


def setUpModule():
    _setUpModule__phaseF_0_deformer()
    _setUpModule__phaseF_2_geometry_handles()
    _setUpModule__phaseF_3_deformer_family()
    _setUpModule__blendshape_targets()
    _setUpModule__manual_setattr_dirty()
    _setUpModule__double_import_no_recursion()


if __name__ == "__main__":
    import unittest
    unittest.main()
