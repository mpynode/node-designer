"""PlugProxy / promoted-type read+write surface

Consolidated from: test_phaseE_plug_proxy.py, test_phaseF_1_type_promotion.py, test_phaseE3_writes.py, test_phaseK_0_datablock_reads.py, test_phaseJ_1_plug_tree_inherited.py.
"""

from __future__ import annotations

# ===================== from test_phaseE_plug_proxy.py =====================
import unittest

import maya.cmds as mc
import maya.OpenMaya as om

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseE_plug_proxy():
    standalone_init()


# ===========================================================================
# Module exports
# ===========================================================================


class TestPlugProxyExports(unittest.TestCase):
    def test_module_exposes_PlugProxy(self):
        from mpynode._common.plugs import plug_proxy

        self.assertTrue(hasattr(plug_proxy, "PlugProxy"))
        self.assertTrue(hasattr(plug_proxy, "CompoundPlugProxy"))
        self.assertTrue(hasattr(plug_proxy, "PlugListProxy"))
        self.assertTrue(hasattr(plug_proxy, "make_node_proxy_for_name"))


# ===========================================================================
# E1: scalar reads (numeric / unit / bool / string)
# ===========================================================================


class TestE1ScalarReads(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _make_xform(self) -> str:
        tf, _ = mc.polyPlane(name="testPlane", w=2, h=2, sx=4, sy=4)
        mc.setAttr(tf + ".translateX", 5.0)
        mc.setAttr(tf + ".rotateY", 45.0)
        return tf

    def test_numeric_float(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        n = make_node_proxy_for_name(self._make_xform())
        self.assertAlmostEqual(n.translateX, 5.0, places=5)

    def test_unit_angle_returns_radians(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        n = make_node_proxy_for_name(self._make_xform())
        # 45° → 0.7853981...
        self.assertAlmostEqual(n.rotateY, 0.7853981633974483, places=5)

    def test_bool(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        n = make_node_proxy_for_name(self._make_xform())
        self.assertIs(n.visibility, True)

    def test_string(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf = self._make_xform()
        mc.addAttr(tf, longName="myStringAttr", dataType="string")
        mc.setAttr(tf + ".myStringAttr", "hello world", type="string")
        n = make_node_proxy_for_name(tf)
        self.assertEqual(n.myStringAttr, "hello world")


# ===========================================================================
# E1: compound + multi traversal
# ===========================================================================


class TestE1CompoundAndMulti(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_compound_translate(self):
        from mpynode._common.plugs.plug_proxy import (
            CompoundPlugProxy,
            make_node_proxy_for_name,
        )

        tf, _ = mc.polyPlane(name="p")
        mc.setAttr(tf + ".translate", 1.0, 2.0, 3.0, type="double3")
        n = make_node_proxy_for_name(tf)
        self.assertIsInstance(n.translate, CompoundPlugProxy)
        self.assertAlmostEqual(n.translate.translateX, 1.0, places=5)
        self.assertAlmostEqual(n.translate.translateY, 2.0, places=5)
        self.assertAlmostEqual(n.translate.translateZ, 3.0, places=5)

    def test_multi_worldMatrix(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        from mpynode._common.plugs.promoted_types import MatrixArrayView, MatrixView

        tf, _ = mc.polyPlane(name="p")
        sh = mc.listRelatives(tf, shapes=True)[0]
        n = make_node_proxy_for_name(sh)
        # A matrix multi is the unified (lazy plug-backed) MatrixArrayView.
        self.assertIsInstance(n.worldMatrix, MatrixArrayView)
        # kMatrix plugs return MatrixView (element 0 resolves lazily).
        wm = n.worldMatrix[0]
        self.assertIsInstance(wm, MatrixView)
        # And callers can still drop down to a raw MMatrix (api2-backed).
        import maya.api.OpenMaya as om2
        self.assertIsInstance(wm.asMatrix(), om2.MMatrix)
        # Or to a (4, 4) float64 numpy.
        import numpy as np
        arr = wm.asNumpy()
        self.assertEqual(arr.shape, (4, 4))
        self.assertEqual(arr.dtype, np.float64)

    def test_compound_repr_lists_children(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        n = make_node_proxy_for_name(tf)
        r = repr(n.translate)
        self.assertIn("translateX", r)
        self.assertIn("translateY", r)
        self.assertIn("translateZ", r)


# ===========================================================================
# E2: geometry MFn wrappers
# ===========================================================================


class TestE2GeometryWrappers(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_mesh_outMesh_returns_MFnMesh(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p", w=2, h=2, sx=4, sy=4)
        sh = mc.listRelatives(tf, shapes=True)[0]
        n = make_node_proxy_for_name(sh)
        m = n.outMesh
        self.assertIsInstance(m, om.MFnMesh)
        self.assertEqual(m.numVertices(), 25)
        self.assertEqual(m.numPolygons(), 16)

    def test_deformer_inputGeometry_returns_MFnMesh(self):
        """Generic geometry plug — attrType() is kInvalid; must
        dispatch on runtime data apiType."""
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        tf, _ = mc.polyPlane(name="p", w=2, h=2, sx=4, sy=4)
        d = MPyDeformer.create_on(tf)
        n = make_node_proxy_for_name(d.get_name())

        m = n.input[0].inputGeometry
        self.assertIsInstance(m, om.MFnMesh)
        self.assertEqual(m.numVertices(), 25)

    def test_deformer_originalGeometry_returns_MFnMesh(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        tf, _ = mc.polyPlane(name="p", w=2, h=2, sx=4, sy=4)
        d = MPyDeformer.create_on(tf)
        n = make_node_proxy_for_name(d.get_name())

        orig = n.originalGeometry[0]
        self.assertIsInstance(orig, om.MFnMesh)
        self.assertEqual(orig.numVertices(), 25)

    def test_nurbs_curve_geometry(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        crv = mc.curve(name="testCrv", p=[(0, 0, 0), (1, 0, 0), (2, 0, 0)], d=1)
        sh = mc.listRelatives(crv, shapes=True)[0]
        n = make_node_proxy_for_name(sh)
        c = n.worldSpace[0]
        self.assertIsInstance(c, om.MFnNurbsCurve)


# ===========================================================================
# Errors
# ===========================================================================


class TestPlugProxyErrors(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_missing_attr_raises_AttributeError(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        n = make_node_proxy_for_name(tf)
        with self.assertRaises(AttributeError):
            _ = n.thisAttrDoesNotExist

    def test_write_succeeds_E3(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        n = make_node_proxy_for_name(tf)
        # E3: writes are now implemented for numeric (and many other
        # types — see test_phaseE3_writes.py for full coverage).
        n.translateX = 17.5
        self.assertAlmostEqual(
            mc.getAttr(tf + ".translateX"), 17.5, places=5
        )

    def test_multi_non_int_index_raises_TypeError(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        sh = mc.listRelatives(tf, shapes=True)[0]
        n = make_node_proxy_for_name(sh)
        with self.assertRaises(TypeError):
            _ = n.worldMatrix["bogus"]


# ===========================================================================
# Introspection helpers
# ===========================================================================


class TestPlugProxyIntrospection(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_dir_returns_real_plug_names(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        n = make_node_proxy_for_name(tf)
        names = dir(n)
        self.assertIn("translateX", names)
        self.assertIn("rotateY", names)
        self.assertIn("visibility", names)
        # Should include MANY (transforms have ~200+ attrs)
        self.assertGreater(len(names), 50)

    def test_repr_includes_node_name_and_type(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="introspectTest")
        n = make_node_proxy_for_name(tf)
        r = repr(n)
        self.assertIn("introspectTest", r)
        self.assertIn("kTransform", r)


# ===================== from test_phaseF_1_type_promotion.py =====================
import unittest

import maya.cmds as mc
import maya.OpenMaya as om
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseF_1_type_promotion():
    standalone_init()


# ===========================================================================
# Promoted type imports
# ===========================================================================


class TestPromotedTypeImports(unittest.TestCase):
    def test_promoted_types_exposed(self):
        from mpynode._common.plugs.promoted_types import (
            MatrixView,
            TimeFloat,
            EnumInt,
        )
        self.assertTrue(callable(MatrixView))
        self.assertTrue(callable(TimeFloat))
        self.assertTrue(callable(EnumInt))


# ===========================================================================
# Read promotions on a scaffolded test node
# ===========================================================================


class TestReadPromotions(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_kMatrix_returns_MatrixView(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        from mpynode._common.plugs.promoted_types import MatrixView

        tf, _ = mc.polyPlane(name="p")
        sh = mc.listRelatives(tf, shapes=True)[0]
        n = make_node_proxy_for_name(sh)
        self.assertIsInstance(n.worldMatrix[0], MatrixView)

    def test_kMatrix_asMatrix_is_MMatrix(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        import maya.api.OpenMaya as om2

        tf, _ = mc.polyPlane(name="p")
        sh = mc.listRelatives(tf, shapes=True)[0]
        n = make_node_proxy_for_name(sh)
        self.assertIsInstance(n.worldMatrix[0].asMatrix(), om2.MMatrix)

    def test_kMatrix_asNumpy_is_4x4_float64(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        sh = mc.listRelatives(tf, shapes=True)[0]
        n = make_node_proxy_for_name(sh)
        arr = n.worldMatrix[0].asNumpy()
        self.assertEqual(arr.shape, (4, 4))
        self.assertEqual(arr.dtype, np.float64)

    def test_kEnum_returns_EnumInt(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        from mpynode._common.plugs.promoted_types import EnumInt

        # rotateOrder is a kEnum on every transform.
        tf, _ = mc.polyPlane(name="p")
        n = make_node_proxy_for_name(tf)
        ro = n.rotateOrder
        self.assertIsInstance(ro, EnumInt)
        self.assertEqual(int(ro), 0)
        # rotateOrder field 0 is "xyz" in Maya.
        self.assertEqual(ro.name(), "xyz")

    def test_kTime_returns_TimeFloat(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        from mpynode._common.plugs.promoted_types import TimeFloat

        # time1.outTime is a kTime plug.
        n = make_node_proxy_for_name("time1")
        out = n.outTime
        self.assertIsInstance(out, TimeFloat)
        # asFrame() must be callable.
        self.assertEqual(out.asFrame(), float(out.asFrame()))

    def test_kPointArray_returns_numpy(self):
        # polyPlane has no built-in kPointArray plug, so add one to a transform.
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        mc.addAttr(tf, longName="testPts", dataType="pointArray")
        # Build (3, 3) sample.
        sample = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]
        n = make_node_proxy_for_name(tf)
        # Set via PlugProxy (E3 init-time write).
        n.testPts = sample
        arr = n.testPts
        self.assertIsInstance(arr, np.ndarray)
        self.assertEqual(arr.shape, (3, 3))
        self.assertEqual(arr.dtype, np.float64)
        self.assertAlmostEqual(arr[1, 1], 5.0)

    def test_kDoubleArray_returns_numpy(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        mc.addAttr(tf, longName="testDoubles", dataType="doubleArray")
        n = make_node_proxy_for_name(tf)
        n.testDoubles = [1.5, 2.5, 3.5, 4.5]
        arr = n.testDoubles
        self.assertIsInstance(arr, np.ndarray)
        self.assertEqual(arr.shape, (4,))
        self.assertEqual(arr.dtype, np.float64)

    def test_kIntArray_returns_numpy_int32(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        mc.addAttr(tf, longName="testInts", dataType="Int32Array")
        n = make_node_proxy_for_name(tf)
        n.testInts = [1, 2, 3, 4, 5]
        arr = n.testInts
        self.assertIsInstance(arr, np.ndarray)
        self.assertEqual(arr.shape, (5,))
        self.assertEqual(arr.dtype, np.int32)

    def test_kVectorArray_returns_numpy(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        mc.addAttr(tf, longName="testVecs", dataType="vectorArray")
        n = make_node_proxy_for_name(tf)
        n.testVecs = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        arr = n.testVecs
        self.assertIsInstance(arr, np.ndarray)
        self.assertEqual(arr.shape, (2, 3))
        self.assertEqual(arr.dtype, np.float64)

    def test_kString_returns_str(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        mc.addAttr(tf, longName="testStr", dataType="string")
        n = make_node_proxy_for_name(tf)
        n.testStr = "hello"
        self.assertEqual(n.testStr, "hello")
        self.assertIsInstance(n.testStr, str)

    def test_numeric_scalar_returns_python_float(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        tf, _ = mc.polyPlane(name="p")
        n = make_node_proxy_for_name(tf)
        # translateX is float
        n.translate.translateX = 1.5
        v = n.translate.translateX
        # Either int or float ok depending on plug subtype, but it's
        # NOT an MFn / numpy / proxy.
        self.assertTrue(isinstance(v, (int, float)))


# ===================== from test_phaseE3_writes.py =====================
import unittest

import maya.cmds as mc
import maya.OpenMaya as om

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseE3_writes():
    standalone_init()


# ===========================================================================
# E3: scalar writes
# ===========================================================================


class TestE3ScalarWrites(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        tf, _ = mc.polyPlane(name="p", sx=4, sy=4)
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        self.tf = tf
        self.n = make_node_proxy_for_name(tf)

    def test_numeric_float(self):
        self.n.translateX = 7.5
        self.assertAlmostEqual(
            mc.getAttr(self.tf + ".translateX"), 7.5, places=5
        )

    def test_unit_angle_in_degrees(self):
        self.n.rotateY = 90.0
        self.assertAlmostEqual(
            mc.getAttr(self.tf + ".rotateY"), 90.0, places=3
        )

    def test_bool(self):
        self.n.visibility = False
        self.assertIs(mc.getAttr(self.tf + ".visibility"), False)

    def test_enum(self):
        mc.addAttr(self.tf, longName="myEnum",
                   attributeType="enum", enumName="a:b:c")
        self.n.myEnum = 2
        self.assertEqual(mc.getAttr(self.tf + ".myEnum"), 2)

    def test_string(self):
        mc.addAttr(self.tf, longName="myString", dataType="string")
        self.n.myString = "hello world"
        self.assertEqual(mc.getAttr(self.tf + ".myString"), "hello world")

    def test_matrix(self):
        mc.addAttr(self.tf, longName="myMatrix", attributeType="matrix")
        identity = om.MMatrix()
        self.n.myMatrix = identity
        m = mc.getAttr(self.tf + ".myMatrix")
        self.assertEqual(len(m), 16)
        # Identity: diag entries = 1.0, off-diagonal = 0.
        self.assertAlmostEqual(m[0], 1.0)   # [0][0]
        self.assertAlmostEqual(m[5], 1.0)   # [1][1]
        self.assertAlmostEqual(m[1], 0.0)   # [0][1]


# ===========================================================================
# E3: compound writes
# ===========================================================================


class TestE3CompoundWrites(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        tf, _ = mc.polyPlane(name="p", sx=4, sy=4)
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        self.tf = tf
        self.n = make_node_proxy_for_name(tf)

    def test_compound_child(self):
        """``node.translate.translateY = 3.14``"""
        self.n.translate.translateY = 3.14
        self.assertAlmostEqual(
            mc.getAttr(self.tf + ".translateY"), 3.14, places=5
        )

    def test_compound_parent_unpacks_to_children(self):
        """``node.translate = (1, 2, 3)``"""
        self.n.translate = (1.5, 2.5, 3.5)
        t = mc.getAttr(self.tf + ".translate")[0]
        self.assertAlmostEqual(t[0], 1.5, places=5)
        self.assertAlmostEqual(t[1], 2.5, places=5)
        self.assertAlmostEqual(t[2], 3.5, places=5)


# ===========================================================================
# E3: multi writes
# ===========================================================================


class TestE3MultiWrites(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        tf, _ = mc.polyPlane(name="p", sx=4, sy=4)
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        self.tf = tf
        self.n = make_node_proxy_for_name(tf)

    def test_multi_assignment_creates_sparse_elements(self):
        mc.addAttr(self.tf, longName="myMulti",
                   attributeType="long", multi=True)
        self.n.myMulti[0] = 42
        self.n.myMulti[3] = 99
        self.assertEqual(mc.getAttr(self.tf + ".myMulti[0]"), 42)
        self.assertEqual(mc.getAttr(self.tf + ".myMulti[3]"), 99)

    def test_multi_index_must_be_int(self):
        mc.addAttr(self.tf, longName="myMulti",
                   attributeType="long", multi=True)
        with self.assertRaises(TypeError):
            self.n.myMulti["bogus"] = 1


# ===========================================================================
# E3: array writes
# ===========================================================================


class TestE3ArrayWrites(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        tf, _ = mc.polyPlane(name="p", sx=4, sy=4)
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        self.tf = tf
        self.n = make_node_proxy_for_name(tf)

    def test_doubleArray(self):
        mc.addAttr(self.tf, longName="myDA", dataType="doubleArray")
        self.n.myDA = [1.5, 2.5, 3.5]
        self.assertEqual(mc.getAttr(self.tf + ".myDA"), [1.5, 2.5, 3.5])

    def test_floatArray(self):
        mc.addAttr(self.tf, longName="myFA", dataType="floatArray")
        self.n.myFA = [0.5, 1.5]
        result = mc.getAttr(self.tf + ".myFA")
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0], 0.5, places=5)

    def test_intArray(self):
        mc.addAttr(self.tf, longName="myIA", dataType="Int32Array")
        self.n.myIA = [10, 20, 30]
        self.assertEqual(mc.getAttr(self.tf + ".myIA"), [10, 20, 30])

    def test_pointArray(self):
        mc.addAttr(self.tf, longName="myPA", dataType="pointArray")
        self.n.myPA = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        pts = mc.getAttr(self.tf + ".myPA")
        # cmds returns each point as a 4-tuple (x, y, z, w)
        self.assertEqual(len(pts), 2)
        self.assertAlmostEqual(pts[0][0], 1.0)
        self.assertAlmostEqual(pts[1][2], 6.0)


# ===========================================================================
# E3: errors
# ===========================================================================


class TestE3WriteErrors(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        tf, _ = mc.polyPlane(name="p", sx=4, sy=4)
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        self.tf = tf
        self.n = make_node_proxy_for_name(tf)

    def test_missing_attribute_raises_AttributeError(self):
        with self.assertRaises(AttributeError):
            self.n.thisDoesNotExist = 1


# ===========================================================================
# E3: read-back via proxy after writes
# ===========================================================================


class TestE3WriteThenRead(unittest.TestCase):
    def test_read_back_through_proxy_sees_write(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        tf, _ = mc.polyPlane(name="p", sx=4, sy=4)
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        n = make_node_proxy_for_name(tf)
        n.translateX = 11.5
        self.assertAlmostEqual(n.translateX, 11.5, places=5)


# ===================== from test_phaseK_0_datablock_reads.py =====================
import unittest

import maya.cmds as mc
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseK_0_datablock_reads():
    standalone_init()


class TestLiveMatrixRead(unittest.TestCase):
    """Drive an upstream worldMatrix, fire compute via the deformer's
    output query, assert ``self.<dynamic_matrix_attr>.asNumpy()``
    returned the LIVE value (not the cached identity)."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=4.0, h=2.0, sx=4, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="td")
        self.deformer.add_input_attr("driverMatrixA", "matrix")
        self.driver = mc.createNode("transform", name="drv")
        mc.connectAttr(
            self.driver + ".worldMatrix[0]",
            self.deformer.get_name() + ".driverMatrixA",
        )
        mc.setAttr(self.deformer.get_name() + ".envelope", 1.0)
        self.plane = plane

        expr = (
            "import numpy as np\n"
            "mat = self.driverMatrixA.asNumpy()\n"
            "ty = float(mat[3, 1])  # Maya layout: translation at row 3\n"
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += ty\n"
            "mesh.setPoints(pts)\n"
        )
        self.deformer.set_compute_expression(expr)

    def test_static_driver_y_pulls_through(self):
        mc.setAttr(self.driver + ".translateY", 3.0)
        mc.dgdirty(self.deformer.get_name())
        ws = mc.xform(self.plane + ".vtx[0]", q=True, ws=True, t=True)
        self.assertAlmostEqual(ws[1], 3.0, places=3,
            msg="K.0: self.driverMatrixA must return live driven value")

    def test_post_change_drive_pulls_through(self):
        # First evaluate at translateY=2
        mc.setAttr(self.driver + ".translateY", 2.0)
        mc.dgdirty(self.deformer.get_name())
        ws_at_2 = mc.xform(self.plane + ".vtx[0]", q=True, ws=True, t=True)
        self.assertAlmostEqual(ws_at_2[1], 2.0, places=3)
        # Then drive to 5 and re-evaluate
        mc.setAttr(self.driver + ".translateY", 5.0)
        mc.dgdirty(self.deformer.get_name())
        ws_at_5 = mc.xform(self.plane + ".vtx[0]", q=True, ws=True, t=True)
        self.assertAlmostEqual(ws_at_5[1], 5.0, places=3,
            msg="K.0: live propagation must follow upstream changes")


class TestCompoundAsNumpy(unittest.TestCase):
    """CompoundPlugProxy.as_numpy() collapses Double3-style
    compound plugs into a flat (N,) numpy array. np.asarray(...) works
    via __array__."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="td2")
        self.deformer.add_input_attr("amplitude", "vector")
        mc.setAttr(self.deformer.get_name() + ".amplitude", 1.5, 2.5, 3.5, type="double3")

    def test_as_numpy_returns_3_floats(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        proxy = make_node_proxy_for_name(self.deformer.get_name())
        arr = proxy.amplitude.as_numpy()
        self.assertEqual(arr.shape, (3,))
        np.testing.assert_array_almost_equal(arr, [1.5, 2.5, 3.5], decimal=4)

    def test_np_asarray_works(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        proxy = make_node_proxy_for_name(self.deformer.get_name())
        arr = np.asarray(proxy.amplitude)
        self.assertEqual(arr.shape, (3,))

    def test_iter_works(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        proxy = make_node_proxy_for_name(self.deformer.get_name())
        vals = [float(v) for v in proxy.amplitude]
        self.assertEqual(len(vals), 3)
        self.assertAlmostEqual(vals[0], 1.5, places=4)


@unittest.skip(
    "The lattice-style deformer demo was retired; the no-cmds.getAttr-in-wrappers "
    "guarantee is now covered by test_phaseM_3_no_cmds_getattr_in_wrappers."
)
class TestNoCmdsGetAttrInDemo(unittest.TestCase):
    """Source-grep: the lattice demo must not call
    ``cmds.getAttr`` inside the Expression -- that's anti-pattern eliminated."""

    def test_demo_expression_has_no_cmds_getattr(self):
        import re
        import inspect
        from mpynode._demos import build_mpyLatticeStyleDeformer as mod

        src = inspect.getsource(mod)
        expr_marker = "_EXPRESSION = "
        idx = src.index(expr_marker)
        end_idx = src.index('"""', src.index('"""', idx) + 3) + 3
        expr_block = src[idx:end_idx]
        # Match an actual function CALL: cmds.getAttr( (with paren).
        # The comment "cmds.getAttr workarounds" in docstring is OK.
        self.assertIsNone(
            re.search(r"cmds\.getAttr\s*\(", expr_block),
            "K.2: demo expression must NOT call cmds.getAttr(...) (the "
            "anti-pattern). Use self.<attr>.asNumpy() / "
            ".as_numpy() instead.",
        )


# ===================== from test_phaseJ_1_plug_tree_inherited.py =====================
import unittest

import maya.cmds as mc
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseJ_1_plug_tree_inherited():
    standalone_init()


class TestInheritedDeformerPlugs(unittest.TestCase):
    """MPyDeformer exposes every inherited MPxDeformerNode plug on
    ``self.X`` through the live plug tree -- no wrapper-side curation."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(name="P", w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="testDef")
        self.plane = plane

    def test_envelope_is_reachable_as_float(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        proxy = make_node_proxy_for_name(self.deformer.get_name())
        env = proxy.envelope
        self.assertIsInstance(env, float)
        self.assertAlmostEqual(env, 1.0, places=4)

    def test_outputGeometry_is_a_multi(self):
        """``self.outputGeometry`` is the inherited multi -- the user
        addresses ``self.outputGeometry[0]`` etc. We don't construct an
        MFn handle here (that requires a live compute), but we DO check
        the plug tree exposes the name."""
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        proxy = make_node_proxy_for_name(self.deformer.get_name())
        og = proxy.outputGeometry
        # Whatever proxy type the multi resolves to, the name must
        # have resolved -- attr-error means the plug tree filtered it.
        self.assertIsNotNone(og)

    def test_input_multi_compound_reachable(self):
        """``self.input[0].inputGeometry`` -- proves nested compound
        children of inherited multis are reachable."""
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        proxy = make_node_proxy_for_name(self.deformer.get_name())
        # ``input`` is the inherited deformer multi compound. Just
        # touching it must not raise.
        input_multi = proxy.input
        self.assertIsNotNone(input_multi)


class TestUserAddedPlugsRideAlongside(unittest.TestCase):
    """User-added attrs (the ffd1-style internals the artist adds via
    the UI) ride on the same self.X plug tree as inherited plugs."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(name="P2", w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="testDef2")
        # Add the lattice-style user inputs.
        self.deformer.add_input_attr("driverMatrixA", "matrix")
        self.deformer.add_input_attr("amplitude", "vector")

    def test_user_added_matrix_resolves_as_mtmview(self):
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name
        from mpynode._common.plugs.promoted_types import MatrixView

        proxy = make_node_proxy_for_name(self.deformer.get_name())
        m = proxy.driverMatrixA
        self.assertIsInstance(
            m,
            MatrixView,
            f"user-added matrix attr should promote to "
            f"MatrixView (the non-numerical native "
            f"contract); got {type(m).__name__}",
        )
        # Convert through init_helpers and check identity at rest.
        from mpynode._common.lifecycle import init_helpers as ih

        arr = ih.mtm_to_numpy(m)
        self.assertEqual(arr.shape, (4, 4))
        np.testing.assert_array_almost_equal(arr, np.eye(4), decimal=4)

    def test_user_added_vector_resolves_via_compound_children(self):
        """User-added ``vector`` attr (Double3) becomes a Compound on
        the plug tree. Access scalar children via.amplitudeX/Y/Z.

        Reaching all three children at once is a opportunity
        (amend so Double3 -> (3,) numpy). For now the user's
        own Init tab does the numpy conversion in one line via
        cmds.getAttr or a helper."""
        from mpynode._common.plugs.plug_proxy import make_node_proxy_for_name

        proxy = make_node_proxy_for_name(self.deformer.get_name())
        mc.setAttr(self.deformer.get_name() + ".amplitude", 1.5, 2.5, 3.5, type="double3")
        amp = proxy.amplitude
        # CompoundPlugProxy: walk children by attribute short/long name.
        ax = amp.amplitudeX
        ay = amp.amplitudeY
        az = amp.amplitudeZ
        self.assertAlmostEqual(float(ax), 1.5, places=4)
        self.assertAlmostEqual(float(ay), 2.5, places=4)
        self.assertAlmostEqual(float(az), 3.5, places=4)


class TestTransformDroppedSlotsStillReachable(unittest.TestCase):
    """The transform's ``self.translate`` resolves to a numpy (3,)
    via the KEEP-callback compute_locals slot (per Section 3.4 of
    PHASE_J_DESIGN.md). This pins the user-facing contract:
    `self.translate * weight` works as a numpy vector op."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyTransform")
        mc.setAttr(self.node + ".translate", 4.0, 5.0, 6.0, type="double3")

    def test_translate_via_selfproxy_in_expression(self):
        """End-to-end pin: a user expression on the transform reads
        ``self.translate`` and writes its sum into ``output_matrix``.
        The matrix's translation column should reflect the input."""
        expr = (
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 0] = float(self.translate[0])\n"
            "m[3, 1] = float(self.translate[1])\n"
            "m[3, 2] = float(self.translate[2])\n"
            "self.output_matrix = m\n"
        )
        mc.setAttr(self.node + "._computeSource", expr, type="string")
        m = mc.getAttr(self.node + ".matrix")
        self.assertAlmostEqual(m[12], 4.0, places=4)
        self.assertAlmostEqual(m[13], 5.0, places=4)
        self.assertAlmostEqual(m[14], 6.0, places=4)


def setUpModule():
    _setUpModule__phaseE_plug_proxy()
    _setUpModule__phaseF_1_type_promotion()
    _setUpModule__phaseE3_writes()
    _setUpModule__phaseK_0_datablock_reads()
    _setUpModule__phaseJ_1_plug_tree_inherited()


if __name__ == "__main__":
    import unittest
    unittest.main()
