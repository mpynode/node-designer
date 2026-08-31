"""Attribute types: angle/euler/enum, python/geometry, time

Consolidated from: test_phase18_7.py, test_phase18_8.py, test_phase18_9.py.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QApplication must exist BEFORE standalone.initialize for the widget tests.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-attr-types-test"])

# ===================== from test_phase18_7.py =====================
import unittest

import maya.cmds as mc
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase18_7():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Wrapper-level: add_input_attr/add_output_attr for angle/euler/enum
# ===========================================================================


class TestNewAttrTypes(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_angle_input(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ang1")
        n.add_input_attr("a", "angle")
        self.assertEqual(mc.getAttr(n.get_name() + ".a", type=True), "doubleAngle")
        self.assertIn("a", n.get_input_attr_map())
        self.assertEqual(n.get_input_attr_map()["a"]["attr_type"], "angle")

    def test_euler_input_creates_xyz_doubleAngle_children(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="eu1")
        n.add_input_attr("rot", "euler")
        self.assertEqual(mc.getAttr(n.get_name() + ".rot", type=True), "double3")
        for axis in ("X", "Y", "Z"):
            self.assertTrue(mc.attributeQuery("rot" + axis, node=n.get_name(), exists=True))
            self.assertEqual(
                mc.getAttr(n.get_name() + ".rot" + axis, type=True),
                "doubleAngle",
            )

    def test_enum_input_default_false_true(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="en1")
        n.add_input_attr("e", "enum")  # no enum_names
        listed = mc.attributeQuery("e", node=n.get_name(), listEnum=True)
        self.assertEqual(listed, ["False:True"])
        self.assertEqual(n.get_input_attr_map()["e"]["enum_names"], ["False", "True"])

    def test_enum_input_custom_names(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="en2")
        n.add_input_attr("mode", "enum", enum_names=["off", "on", "standby"])
        listed = mc.attributeQuery("mode", node=n.get_name(), listEnum=True)
        self.assertEqual(listed, ["off:on:standby"])
        self.assertEqual(
            n.get_input_attr_map()["mode"]["enum_names"],
            ["off", "on", "standby"],
        )

    def test_enum_output(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="en3")
        n.add_output_attr("state", "enum", enum_names=["idle", "active"])
        listed = mc.attributeQuery("state", node=n.get_name(), listEnum=True)
        self.assertEqual(listed, ["idle:active"])

    def test_enum_input_default_value_sets_initial_index(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="en_dv")
        n.add_input_attr("mode", "enum",
                         enum_names=["off", "on", "standby"], default_value=2)
        nm = n.get_name()
        # The bare plug value AND the attr's stored default index are the default.
        self.assertEqual(mc.getAttr(nm + ".mode"), 2)
        self.assertEqual(mc.addAttr(nm + ".mode", q=True, defaultValue=True), 2)
        self.assertEqual(n.get_input_attr_map()["mode"].get("default_value"), 2)

    def test_enum_input_default_value_omitted_is_zero(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="en_dv0")
        n.add_input_attr("mode", "enum", enum_names=["off", "on", "standby"])
        nm = n.get_name()
        self.assertEqual(mc.getAttr(nm + ".mode"), 0)
        # No default recorded when not supplied (keeps specs byte-identical).
        self.assertNotIn("default_value", n.get_input_attr_map()["mode"])

    def test_enum_default_survives_mpn_round_trip(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io.mpn_io import deserialize_node, serialize_node

        n = MPyNode.create(name="en_rt")
        n.add_input_attr("mode", "enum",
                         enum_names=["a", "b", "c"], default_value=2)
        payload = serialize_node(n, include_persistent=False)
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        n2 = deserialize_node(payload, restore_persistent=False)
        self.assertEqual(mc.getAttr(n2.get_name() + ".mode"), 2)
        self.assertEqual(
            n2.get_input_attr_map()["mode"].get("default_value"), 2)

    def test_euler_output_xyz_children(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="eu_out")
        n.add_output_attr("rot", "euler")
        for axis in ("X", "Y", "Z"):
            self.assertEqual(
                mc.getAttr(n.get_name() + ".rot" + axis, type=True),
                "doubleAngle",
            )

    def test_euler_rename_renames_xyz_children(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="eu_rn")
        n.add_input_attr("rot", "euler")
        n.rename_input_attr("rot", "rotation")
        for axis in ("X", "Y", "Z"):
            self.assertFalse(mc.attributeQuery("rot" + axis, node=n.get_name(), exists=True))
            self.assertTrue(
                mc.attributeQuery("rotation" + axis, node=n.get_name(), exists=True)
            )


# ===========================================================================
# Compute-side type contract (read_user_inputs_dict)
# ===========================================================================


class TestComputeSideTypes(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _probe(self, attr_name: str, attr_type: str, expression: str) -> str:
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=f"probe_{attr_name}")
        n.add_input_attr(attr_name, attr_type)
        n.add_output_attr("type_name", "string")
        n.set_compute_expression(expression)
        return mc.getAttr(n.get_name() + ".type_name") or ""

    def test_angle_returns_float(self):
        result = self._probe("ang", "angle", "self.type_name = type(self.ang).__name__")
        self.assertEqual(result, "float")

    def test_euler_returns_ndarray_3(self):
        result = self._probe(
            "rot",
            "euler",
            "self.type_name = type(self.rot).__name__ + ' ' + str(self.rot.shape)",
        )
        self.assertEqual(result, "ndarray (3,)")

    def test_enum_returns_int(self):
        # An enum reads as EnumInt, an int subclass whose .name() is the field
        # label (docs/node_types/_input_type_contract.md). Same contract as the
        # plug-proxy path in test_plug_proxy.test_kEnum_returns_EnumInt.
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="enum_type")
        n.add_input_attr("mode", "enum", enum_names=["off", "on", "standby"])
        n.add_output_attr("type_name", "string")
        n.set_compute_expression(
            "self.type_name = str(isinstance(self.mode, int)) + ' ' + self.mode.name()"
        )
        result = mc.getAttr(n.get_name() + ".type_name") or ""
        # default enum value 0 -> "off", and it is still an int.
        self.assertEqual(result, "True off")

    def test_enum_value_matches_setAttr(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="enval")
        n.add_input_attr("mode", "enum", enum_names=["off", "on", "standby"])
        n.add_output_attr("idx", "int")
        n.set_compute_expression("self.idx = self.mode")
        self.assertEqual(mc.getAttr(n.get_name() + ".idx"), 0)
        mc.setAttr(n.get_name() + ".mode", 2)
        self.assertEqual(mc.getAttr(n.get_name() + ".idx"), 2)


# ===========================================================================
# Add command pass-through of enum_names
# ===========================================================================


class TestAddCommandsEnumNames(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_add_input_command_takes_enum_names(self):
        from mpynode._base.commands import _AddInputAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cmd1")
        run_undoable(
            _AddInputAttrCommand(n, "mode", "enum", False, enum_names=["a", "b", "c"])
        )
        listed = mc.attributeQuery("mode", node=n.get_name(), listEnum=True)
        self.assertEqual(listed, ["a:b:c"])
        mc.undo()
        self.assertNotIn("mode", n.get_input_attr_map())

    def test_add_output_command_takes_enum_names(self):
        from mpynode._base.commands import _AddOutputAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cmd2")
        run_undoable(
            _AddOutputAttrCommand(n, "out", "enum", False, enum_names=["zero", "one"])
        )
        listed = mc.attributeQuery("out", node=n.get_name(), listEnum=True)
        self.assertEqual(listed, ["zero:one"])


# ===========================================================================
# Dialog UI shape (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestAddAttrDialogPhase18_7(unittest.TestCase):
    def test_all_attr_types_includes_angle_euler_enum(self):
        from mpynode.ui.dialogs.add_attr import ALL_ATTR_TYPES

        self.assertIn("angle", ALL_ATTR_TYPES)
        self.assertIn("euler", ALL_ATTR_TYPES)
        self.assertIn("enum", ALL_ATTR_TYPES)

    def test_subframe_router_routes_angle_to_numeric(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._make_subframe)
        self.assertIn('"angle"', src)
        self.assertIn("_make_numeric_subframe", src)

    def test_enum_subframe_uses_editable_items(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._make_enum_subframe)
        self.assertIn("QListWidgetItem", src)
        self.assertIn("ItemIsEditable", src)
        self.assertIn('"False"', src)
        self.assertIn('"True"', src)
        self.assertIn('"+"', src)

    def test_enum_subframe_plus_button_focuses_for_inline_edit(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._enum_add_blank)
        self.assertIn("editItem", src)

    def test_on_add_clicked_passes_enum_names(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._on_add_clicked)
        self.assertIn("enum_names=", src)


# ===================== from test_phase18_8.py =====================
import base64
import pickle
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase18_8():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Wrapper-level: add_input_attr / add_output_attr for the new types
# ===========================================================================


class TestNewTypesAddable(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_python_input_lands_as_string(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="py1")
        n.add_input_attr("cfg", "python")
        # python is backed by a string plug.
        self.assertEqual(mc.getAttr(n.get_name() + ".cfg", type=True), "string")
        self.assertEqual(n.get_input_attr_map()["cfg"]["attr_type"], "python")

    def test_mesh_input_lands_as_mesh_plug(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="me1")
        n.add_input_attr("inMesh", "mesh")
        self.assertTrue(mc.attributeQuery("inMesh", node=n.get_name(), exists=True))
        self.assertEqual(n.get_input_attr_map()["inMesh"]["attr_type"], "mesh")

    def test_nurbsCurve_input_lands(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="nc1")
        n.add_input_attr("inCurve", "nurbsCurve")
        self.assertTrue(mc.attributeQuery("inCurve", node=n.get_name(), exists=True))

    def test_nurbsSurface_input_lands(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ns1")
        n.add_input_attr("inSurf", "nurbsSurface")
        self.assertTrue(mc.attributeQuery("inSurf", node=n.get_name(), exists=True))

    def test_python_output_lands(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="pyo1")
        n.add_output_attr("outData", "python")
        self.assertEqual(mc.getAttr(n.get_name() + ".outData", type=True), "string")


# ===========================================================================
# multi (array) OUTPUT write path through compute(): write_multi_plug_value
# must populate plug elements for every scalar/compound type.
#
# Expressions use ``for`` loops, not list comprehensions: exec(code, globals,
# locals) doesn't expose locals inside a listcomp body. range(...) args are
# fine, they evaluate in the outer scope.
# ===========================================================================


class TestMultiOutputWrite(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _build(self, name: str, attr_type: str, expr: str):
        """Build an mPyNode test fixture.

        prepend ``import numpy as np`` so existing tests
        that use ``np.eye()`` etc. continue to work after the namespace
        contract change (no more auto-imports).
        """
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=name)
        n.add_input_attr("count", "int")
        n.add_output_attr("out", attr_type, is_array=True)
        n.set_compute_expression("import numpy as np\n" + expr)
        return n

    def test_multi_float_output(self):
        n = self._build(
            "mfloat",
            "float",
            "self.out = []\nfor i in range(self.count):\n    self.out.append(float(i) * 0.5)",
        )
        mc.setAttr(n.get_name() + ".count", 4)
        # Force fresh compute by re-touching the input.
        mc.setAttr(n.get_name() + ".count", 4)
        for i in range(4):
            self.assertAlmostEqual(mc.getAttr(f"{n.get_name()}.out[{i}]"), float(i) * 0.5)

    def test_multi_double_output(self):
        n = self._build(
            "mdouble",
            "double",
            "self.out = []\nfor i in range(self.count):\n    self.out.append(float(i) * 1.5)",
        )
        mc.setAttr(n.get_name() + ".count", 3)
        mc.setAttr(n.get_name() + ".count", 3)
        for i in range(3):
            self.assertAlmostEqual(mc.getAttr(f"{n.get_name()}.out[{i}]"), float(i) * 1.5)

    def test_multi_int_output(self):
        n = self._build(
            "mint",
            "int",
            "self.out = []\nfor i in range(self.count):\n    self.out.append(i * 7)",
        )
        mc.setAttr(n.get_name() + ".count", 4)
        mc.setAttr(n.get_name() + ".count", 4)
        for i in range(4):
            self.assertEqual(mc.getAttr(f"{n.get_name()}.out[{i}]"), i * 7)

    def test_multi_bool_output(self):
        n = self._build(
            "mbool",
            "bool",
            "self.out = []\nfor i in range(self.count):\n    self.out.append(bool(i % 2))",
        )
        mc.setAttr(n.get_name() + ".count", 4)
        mc.setAttr(n.get_name() + ".count", 4)
        self.assertFalse(mc.getAttr(f"{n.get_name()}.out[0]"))
        self.assertTrue(mc.getAttr(f"{n.get_name()}.out[1]"))
        self.assertFalse(mc.getAttr(f"{n.get_name()}.out[2]"))
        self.assertTrue(mc.getAttr(f"{n.get_name()}.out[3]"))

    def test_multi_string_output(self):
        n = self._build(
            "mstr",
            "string",
            "self.out = []\nfor i in range(self.count):\n    self.out.append('item_' + str(i))",
        )
        mc.setAttr(n.get_name() + ".count", 3)
        mc.setAttr(n.get_name() + ".count", 3)
        for i in range(3):
            self.assertEqual(mc.getAttr(f"{n.get_name()}.out[{i}]"), f"item_{i}")

    def test_multi_vector_output(self):
        n = self._build(
            "mvec",
            "vector",
            "self.out = []\n"
            "for i in range(self.count):\n"
            "    self.out.append([float(i), float(i*2), float(i*3)])",
        )
        mc.setAttr(n.get_name() + ".count", 3)
        mc.setAttr(n.get_name() + ".count", 3)
        for i in range(3):
            v = mc.getAttr(f"{n.get_name()}.out[{i}]")[0]
            self.assertAlmostEqual(v[0], float(i))
            self.assertAlmostEqual(v[1], float(i * 2))
            self.assertAlmostEqual(v[2], float(i * 3))

    def test_multi_matrix_output(self):
        n = self._build(
            "mmat",
            "matrix",
            "self.out = []\n"
            "for i in range(self.count):\n"
            "    self.out.append(np.eye(4) * float(i + 1))",
        )
        mc.setAttr(n.get_name() + ".count", 2)
        mc.setAttr(n.get_name() + ".count", 2)
        m0 = mc.getAttr(f"{n.get_name()}.out[0]")
        m1 = mc.getAttr(f"{n.get_name()}.out[1]")
        # diagonal entries
        for d_idx in (0, 5, 10, 15):
            self.assertAlmostEqual(m0[d_idx], 1.0)
            self.assertAlmostEqual(m1[d_idx], 2.0)

    def test_multi_python_output(self):
        n = self._build(
            "mpy",
            "python",
            "self.out = []\n"
            "for i in range(self.count):\n"
            "    self.out.append({'index': i, 'doubled': i * 2})",
        )
        mc.setAttr(n.get_name() + ".count", 3)
        mc.setAttr(n.get_name() + ".count", 3)
        # Decode the base64+pickle envelope per element.
        import base64
        import pickle

        for i in range(3):
            raw = mc.getAttr(f"{n.get_name()}.out[{i}]")
            decoded = pickle.loads(base64.b64decode(raw.encode("ascii")))
            self.assertEqual(decoded, {"index": i, "doubled": i * 2})

    def test_multi_geometry_output_writes(self):
        """A MULTI mesh output now writes a ``list`` of geometry objects to
        ``output[i]`` (unified-wrapper Phase 3) -- it no longer raises. Each
        element is marshalled via the shared per-element writer."""
        import maya.api.OpenMaya as om
        import numpy as np
        from mpynode.wrappers._mpy_node import MPyNode

        srcs = []
        for i in range(3):
            s = mc.polySphere(r=1.0 + i, sx=4, sy=4, ch=False, name="gmIn%d" % i)[0]
            srcs.append(mc.listRelatives(s, s=True, f=True)[0])
        w = MPyNode.create(name="gmMultiWriter")
        node = w.get_name()
        w.add_input_attr("inMeshes", "mesh", is_array=True)
        w.add_output_attr("outMeshes", "mesh", is_array=True)
        w.set_compute_expression(
            "out = []\n"
            "for m in self.inMeshes:\n"
            "    if m is None:\n"
            "        continue\n"
            "    c = m.copy(); c.points = c.points * 2.0; out.append(c)\n"
            "self.outMeshes = out\n"
        )
        for i, shp in enumerate(srcs):
            mc.connectAttr(shp + ".worldMesh[0]", "%s.inMeshes[%d]" % (node, i), force=True)
        # Pulling each output element runs compute + writes the marshalled data.
        dep = om.MFnDependencyNode(om.MSelectionList().add(node).getDependNode(0))
        for i, shp in enumerate(srcs):
            outm = dep.findPlug("outMeshes", False).elementByLogicalIndex(i).asMObject()
            self.assertFalse(outm.isNull())
            src_mobj = (om.MFnDependencyNode(om.MSelectionList().add(shp).getDependNode(0))
                        .findPlug("worldMesh", False).elementByLogicalIndex(0).asMObject())
            src_pts = np.array(om.MFnMesh(src_mobj).getPoints(om.MSpace.kObject),
                               dtype=np.float64)[:, :3]
            got = np.array(om.MFnMesh(outm).getPoints(om.MSpace.kObject),
                           dtype=np.float64)[:, :3]
            self.assertEqual(got.shape[0], src_pts.shape[0])
            self.assertTrue(np.allclose(got, src_pts * 2.0))

    def test_multi_geometry_output_helper_no_longer_raises(self):
        """The low-level ``write_multi_plug_value`` no longer rejects geometry
        types outright (it marshals per element instead)."""
        from mpynode._api2 import helpers
        import inspect

        src = inspect.getsource(helpers.write_multi_plug_value)
        self.assertNotIn("writing multi", src)  # the old NotImplementedError text

    def test_multi_output_handles_none_value(self):
        """Tolerates ``out = None`` by writing zero elements (no crash)."""
        n = self._build(
            "mnone",
            "float",
            "out = None\n",
        )
        mc.setAttr(n.get_name() + ".count", 2)
        mc.setAttr(n.get_name() + ".count", 2)
        # no elements added; index 0 either reads a default or errors. Either
        # way, all we want to know is that compute didn't crash.
        try:
            mc.getAttr(f"{n.get_name()}.out[0]")
        except Exception:
            pass  # acceptable \u2014 the multi may be empty

    def test_constraint_node_multi_output_works(self):
        """The change consolidated MPyConstraint's inline write path
        onto the same helpers, so multi output write should also work
        on MPyConstraint, not just MPyNode."""
        cn_name = mc.createNode("mPyConstraint", name="mc_multi")
        from mpynode._node_registry import wrap_node

        cn = wrap_node(cn_name, "mPyConstraint")
        cn.add_input_attr("count", "int")
        cn.add_output_attr("out", "float", is_array=True)
        cn.set_compute_expression(
            "self.out = []\nfor i in range(self.count):\n    self.out.append(float(i) * 11.0)"
        )
        mc.setAttr(cn.get_name() + ".count", 3)
        mc.setAttr(cn.get_name() + ".count", 3)
        for i in range(3):
            self.assertAlmostEqual(mc.getAttr(f"{cn.get_name()}.out[{i}]"), float(i) * 11.0)


# ===========================================================================
# python attr round-trip via expressions (read + write)
# ===========================================================================


class TestPythonAttrRoundTrip(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _set_python_input(self, n, attr_name, value):
        """Manually pickle+base64 + setAttr, mimicking what an upstream
        node's compute would do via write_plug_value."""
        payload = base64.b64encode(pickle.dumps(value)).decode("ascii")
        mc.setAttr(f"{n.get_name()}.{attr_name}", payload, type="string")

    def test_python_input_dict_via_expression(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="pyrt1")
        n.add_input_attr("cfg", "python")
        n.add_output_attr("got_a", "int")
        n.set_compute_expression("self.got_a = self.cfg['a']")
        self._set_python_input(n, "cfg", {"a": 42, "b": "hello"})
        self.assertEqual(mc.getAttr(n.get_name() + ".got_a"), 42)

    def test_python_input_list(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="pyrt2")
        n.add_input_attr("items", "python")
        n.add_output_attr("count", "int")
        n.set_compute_expression("self.count = len(self.items)")
        self._set_python_input(n, "items", [1, 2, 3, 4, 5])
        self.assertEqual(mc.getAttr(n.get_name() + ".count"), 5)

    def test_python_input_none_when_empty_string(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="pyrt3")
        n.add_input_attr("maybe", "python")
        n.add_output_attr("is_none", "bool")
        n.set_compute_expression("self.is_none = (self.maybe is None)")
        # Default empty plug \u2192 should read as None.
        self.assertTrue(mc.getAttr(n.get_name() + ".is_none"))

    def test_python_output_round_trip_through_compute(self):
        """Compute writes a dict; read_plug_value (via getAttr decoded
        manually) recovers the same dict."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="pyout1")
        n.add_output_attr("out", "python")
        n.set_compute_expression("self.out = {'k': 'v', 'n': 7}")
        # Reading the raw string plug forces compute; write_plug_value
        # encoded the dict.
        raw = mc.getAttr(n.get_name() + ".out") or ""
        self.assertNotEqual(raw, "")
        decoded = pickle.loads(base64.b64decode(raw.encode("ascii")))
        self.assertEqual(decoded, {"k": "v", "n": 7})

    def test_python_node_to_node_communication(self):
        """Two mPyNodes share a Python dict via DG connection."""
        from mpynode.wrappers._mpy_node import MPyNode

        producer = MPyNode.create(name="producer")
        producer.add_output_attr("out", "python")
        producer.set_compute_expression("self.out = {'msg': 'hello world', 'count': 3}")

        consumer = MPyNode.create(name="consumer")
        consumer.add_input_attr("in_data", "python")
        consumer.add_output_attr("got", "string")
        consumer.set_compute_expression("self.got = self.in_data['msg']")

        mc.connectAttr(producer.get_name() + ".out", consumer.get_name() + ".in_data")
        self.assertEqual(
            mc.getAttr(consumer.get_name() + ".got"),
            "hello world",
        )

    def test_python_corrupted_payload_raises(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="pybad")
        n.add_input_attr("cfg", "python")
        n.add_output_attr("ok", "bool")
        n.set_compute_expression("ok = (cfg is not None)")
        mc.setAttr(n.get_name() + ".cfg", "not_valid_base64!!!", type="string")
        import maya.api.OpenMaya as om

        # Maya swallows the compute-side ValueError, so assert on the
        # decoder directly instead.
        from mpynode._api2.helpers import read_plug_value

        sel = om.MSelectionList()
        sel.add(n.get_name() + ".cfg")
        plug = sel.getPlug(0)
        with self.assertRaises(ValueError):
            read_plug_value(plug, "python")


# ===========================================================================
# Typed Maya geometry inputs (mesh / nurbsCurve / nurbsSurface)
# ===========================================================================


class TestTypedGeometryInputs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_mesh_input_returns_Mesh_wrapper(self):
        """Connect a polyCube's outMesh; the expression sees the unified
        ``Mesh`` wrapper (attached mode). Backward compat is preserved by
        delegation (``self.inMesh.numVertices`` forwards to the live MFnMesh),
        and the new numpy surface (``.points``) is available."""
        from mpynode.wrappers._mpy_node import MPyNode

        cube_xform = mc.polyCube(name="cubeM", constructionHistory=False)[0]
        cube_shape = mc.listRelatives(cube_xform, shapes=True)[0]
        n = MPyNode.create(name="meshprobe")
        n.add_input_attr("inMesh", "mesh")
        n.add_output_attr("type_name", "string")
        n.add_output_attr("nverts", "int")
        n.add_output_attr("npoints", "int")
        n.set_compute_expression(
            "self.type_name = type(self.inMesh).__name__\n"
            "self.nverts = self.inMesh.numVertices if self.inMesh is not None else -1\n"
            "self.npoints = int(self.inMesh.points.shape[0]) if self.inMesh is not None else -1"
        )
        # First read \u2014 nothing connected yet.
        self.assertEqual(mc.getAttr(n.get_name() + ".nverts"), -1)
        mc.connectAttr(cube_shape + ".outMesh", n.get_name() + ".inMesh", force=True)
        self.assertEqual(mc.getAttr(n.get_name() + ".type_name"), "Mesh")
        self.assertEqual(mc.getAttr(n.get_name() + ".nverts"), 8)   # delegation
        self.assertEqual(mc.getAttr(n.get_name() + ".npoints"), 8)  # numpy surface

    def test_nurbsCurve_input_returns_NurbsCurve_wrapper(self):
        from mpynode.wrappers._mpy_node import MPyNode

        curve_xform = mc.curve(d=1, p=[(0, 0, 0), (1, 0, 0), (2, 0, 0)])
        curve_shape = mc.listRelatives(curve_xform, shapes=True)[0]
        n = MPyNode.create(name="curveprobe")
        n.add_input_attr("inCurve", "nurbsCurve")
        n.add_output_attr("type_name", "string")
        n.add_output_attr("ncvs", "int")
        n.set_compute_expression(
            "self.type_name = type(self.inCurve).__name__ if self.inCurve is not None else 'None'\n"
            "self.ncvs = self.inCurve.numCVs if self.inCurve is not None else -1"
        )
        mc.connectAttr(curve_shape + ".local", n.get_name() + ".inCurve", force=True)
        self.assertEqual(mc.getAttr(n.get_name() + ".type_name"), "NurbsCurve")
        self.assertEqual(mc.getAttr(n.get_name() + ".ncvs"), 3)   # delegation

    def test_nurbsSurface_input_returns_NurbsSurface_wrapper(self):
        from mpynode.wrappers._mpy_node import MPyNode

        surf_xform, _ = mc.nurbsPlane(name="surfP")
        surf_shape = mc.listRelatives(surf_xform, shapes=True)[0]
        n = MPyNode.create(name="surfprobe")
        n.add_input_attr("inSurf", "nurbsSurface")
        n.add_output_attr("type_name", "string")
        n.add_output_attr("ncvsU", "int")
        n.set_compute_expression(
            "self.type_name = type(self.inSurf).__name__ if self.inSurf is not None else 'None'\n"
            "self.ncvsU = self.inSurf.numCVsInU if self.inSurf is not None else -1"
        )
        mc.connectAttr(surf_shape + ".local", n.get_name() + ".inSurf", force=True)
        self.assertEqual(mc.getAttr(n.get_name() + ".type_name"), "NurbsSurface")
        self.assertGreater(mc.getAttr(n.get_name() + ".ncvsU"), 0)   # delegation

    def test_mesh_input_unconnected_returns_None(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="emptymesh")
        n.add_input_attr("inMesh", "mesh")
        n.add_output_attr("is_none", "bool")
        n.set_compute_expression("self.is_none = (self.inMesh is None)")
        self.assertTrue(mc.getAttr(n.get_name() + ".is_none"))

    def test_typed_geometry_output_writes(self):
        """Writing a mesh from an expression IS now supported (unified-wrapper
        Phase 3): assigning a ``Mesh`` (or a ``copy()`` of an input) to a mesh
        output marshals it and writes the geometry -- on ANY node type, not just
        the geometry generators."""
        import maya.api.OpenMaya as om
        import numpy as np
        from mpynode.wrappers._mpy_node import MPyNode

        sph = mc.polySphere(r=1.0, sx=6, sy=6, ch=False, name="geoOutSrc")[0]
        sshp = mc.listRelatives(sph, s=True, f=True)[0]
        n = MPyNode.create(name="meshout")
        n.add_input_attr("inMesh", "mesh")
        n.add_output_attr("outMesh", "mesh")
        n.set_compute_expression(
            "m = self.inMesh\n"
            "if m is not None:\n"
            "    out = m.copy(); out.points = out.points * 3.0; self.outMesh = out\n"
        )
        mc.connectAttr(sshp + ".worldMesh[0]", n.get_name() + ".inMesh", force=True)
        dep = om.MFnDependencyNode(om.MSelectionList().add(n.get_name()).getDependNode(0))
        outm = dep.findPlug("outMesh", False).asMObject()
        self.assertFalse(outm.isNull())
        src_mobj = (om.MFnDependencyNode(om.MSelectionList().add(sshp).getDependNode(0))
                    .findPlug("worldMesh", False).elementByLogicalIndex(0).asMObject())
        src_pts = np.array(om.MFnMesh(src_mobj).getPoints(om.MSpace.kObject),
                           dtype=np.float64)[:, :3]
        got = np.array(om.MFnMesh(outm).getPoints(om.MSpace.kObject),
                       dtype=np.float64)[:, :3]
        self.assertEqual(got.shape[0], src_pts.shape[0])
        self.assertTrue(np.allclose(got, src_pts * 3.0))


# ===========================================================================
# Dialog UI shape (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestDialogShapePhase18_8(unittest.TestCase):
    def test_all_attr_types_includes_python_and_geometry(self):
        from mpynode.ui.dialogs.add_attr import ALL_ATTR_TYPES

        for t in ("python", "mesh", "nurbsCurve", "nurbsSurface"):
            self.assertIn(t, ALL_ATTR_TYPES)

    def test_array_checkbox_enabled_for_every_type(self):
        """matrix used to disable the Array checkbox.
        It (and every other attr type) should be multi-able \u2014 the wrapper
        round-trips ``matrix[]`` as ``list[np.ndarray(4,4)]``, which is
        documented in ``_api2.helpers.read_user_inputs_dict``."""
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._on_type_changed)
        self.assertNotIn(
            'type_name not in ("matrix",)',
            src,
            "Matrix must not be excluded from multi-array support.",
        )
        self.assertIn("setEnabled(True)", src)

    def test_wrapper_creates_multi_matrix_attr(self):
        """End-to-end wrapper sanity: matrix INPUT and OUTPUT both accept
        is_array=True. Catches any future regression that re-introduces a
        type-specific gate downstream of the dialog."""
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

        n = MPyNode.create(name="multi_matrix_check")
        n.add_input_attr("mats_in", "matrix", is_array=True)
        n.add_output_attr("mats_out", "matrix", is_array=True)

        in_meta = n.get_input_attr_map()["mats_in"]
        out_meta = n.get_output_attr_map()["mats_out"]
        self.assertTrue(in_meta["is_array"])
        self.assertTrue(out_meta["is_array"])

        m_id = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        for idx in range(3):
            mc.setAttr(f"multi_matrix_check.mats_in[{idx}]", *m_id, type="matrix")
        self.assertEqual(mc.getAttr("multi_matrix_check.mats_in", size=True), 3)

    def test_helpers_imports_pickle_and_base64(self):
        import inspect

        from mpynode._api2 import helpers

        src = inspect.getsource(helpers)
        self.assertIn("import pickle", src)
        self.assertIn("import base64", src)

    def test_read_plug_value_handles_all_new_types(self):
        import inspect

        from mpynode._api2.helpers import read_plug_value

        src = inspect.getsource(read_plug_value)
        for t in ('"python"', '"mesh"', '"nurbsCurve"', '"nurbsSurface"'):
            self.assertIn(t, src)
        self.assertIn("MFnMesh", src)
        self.assertIn("MFnNurbsCurve", src)
        self.assertIn("MFnNurbsSurface", src)

    def test_write_plug_value_handles_python(self):
        """per-type write logic moved to
        ``_write_value_to_handle`` (shared by scalar + multi paths).
        Inspect that helper for the python-attr branches."""
        import inspect

        from mpynode._api2.helpers import _write_value_to_handle

        src = inspect.getsource(_write_value_to_handle)
        self.assertIn('"python"', src)
        self.assertIn("pickle.dumps", src)
        self.assertIn("base64.b64encode", src)


# ===================== from test_phase18_9.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase18_9():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Wrapper-level: add_input_attr for time
# ===========================================================================


class TestTimeAttrType(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_time_input_lands_as_time_plug(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="t1")
        n.add_input_attr("currTime", "time", auto_connect_time=False)
        self.assertEqual(
            mc.getAttr(n.get_name() + ".currTime", type=True),
            "time",
        )
        self.assertEqual(n.get_input_attr_map()["currTime"]["attr_type"], "time")

    def test_time_output_lands_as_time_plug(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="t1out")
        n.add_output_attr("outTime", "time")
        self.assertEqual(
            mc.getAttr(n.get_name() + ".outTime", type=True),
            "time",
        )

    def test_time_input_default_auto_connects_to_time1(self):
        """Default auto_connect_time=True \u2192 time1.outTime is wired in."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="t_auto")
        n.add_input_attr("currTime", "time")  # default auto_connect_time=True

        sources = (
            mc.listConnections(
                n.get_name() + ".currTime", source=True, destination=False, plugs=True
            )
            or []
        )
        self.assertIn("time1.outTime", sources)

    def test_time_input_opt_out_no_connection(self):
        """Auto_connect_time=False \u2192 plug stays disconnected."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="t_optout")
        n.add_input_attr("bareTime", "time", auto_connect_time=False)

        sources = (
            mc.listConnections(
                n.get_name() + ".bareTime", source=True, destination=False, plugs=True
            )
            or []
        )
        self.assertEqual(sources, [])

    def test_time_input_array_does_NOT_auto_connect(self):
        """Auto_connect_time only triggers for non-array time inputs."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="t_arr")
        n.add_input_attr("times", "time", is_array=True)  # default True

        sources = (
            mc.listConnections(
                n.get_name() + ".times", source=True, destination=False, plugs=True
            )
            or []
        )
        self.assertEqual(sources, [])

    def test_time1_created_if_missing(self):
        """Brand-new scene: time1 is created on demand."""
        from mpynode.wrappers._mpy_node import MPyNode

        # Maya usually creates time1 already; delete it to exercise the
        # create-on-demand path.
        if mc.objExists("time1"):
            try:
                mc.delete("time1")
            except Exception:
                pass

        n = MPyNode.create(name="t_create")
        n.add_input_attr("currTime", "time")

        # Either time1 was created by us, or by Maya during connection.
        self.assertTrue(mc.objExists("time1"))
        sources = (
            mc.listConnections(
                n.get_name() + ".currTime", source=True, destination=False, plugs=True
            )
            or []
        )
        self.assertIn("time1.outTime", sources)


# ===========================================================================
# Compute-side: time reads as float
# ===========================================================================


class TestTimeComputeSide(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_time_returns_float_in_expression(self):
        """Auto-connected time input \u2192 expression sees the current frame
        as a float."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="t_expr")
        n.add_input_attr("currTime", "time")  # auto-connected to time1
        n.add_output_attr("type_name", "string")
        n.add_output_attr("frame_doubled", "float")
        n.set_compute_expression(
            "self.type_name = type(self.currTime).__name__\nself.frame_doubled = self.currTime * 2.0"
        )
        mc.currentTime(0)
        self.assertEqual(mc.getAttr(n.get_name() + ".type_name"), "float")
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".frame_doubled"), 0.0)

        mc.currentTime(7)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".frame_doubled"), 14.0)

    def test_time_output_writable(self):
        """Compute-side write of time should land back at the plug."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="t_out")
        n.add_input_attr("trigger", "float")
        n.add_output_attr("computed_time", "time")
        n.set_compute_expression("self.computed_time = self.trigger * 24.0")
        mc.setAttr(n.get_name() + ".trigger", 2.5)
        # Time plugs report back as MTime in current units; with default
        # film/24fps the value is just the raw written number.
        result = mc.getAttr(n.get_name() + ".computed_time")
        self.assertAlmostEqual(result, 60.0, places=2)


# ===========================================================================
# _AddInputAttrCommand passes auto_connect_time through
# ===========================================================================


class TestAddCommandAutoConnectTime(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_command_default_auto_connects(self):
        from mpynode._base.commands import _AddInputAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cmd_t1")
        run_undoable(_AddInputAttrCommand(n, "currTime", "time"))
        sources = (
            mc.listConnections(n.get_name() + ".currTime", source=True, plugs=True) or []
        )
        self.assertIn("time1.outTime", sources)

    def test_command_opt_out(self):
        from mpynode._base.commands import _AddInputAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cmd_t2")
        run_undoable(
            _AddInputAttrCommand(
                n,
                "bareTime",
                "time",
                False,
                enum_names=None,
                auto_connect_time=False,
            )
        )
        sources = (
            mc.listConnections(n.get_name() + ".bareTime", source=True, plugs=True) or []
        )
        self.assertEqual(sources, [])


# ===========================================================================
# Dialog UI shape (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestDialogShapePhase18_9(unittest.TestCase):
    def test_time_in_all_attr_types(self):
        from mpynode.ui.dialogs.add_attr import ALL_ATTR_TYPES

        self.assertIn("time", ALL_ATTR_TYPES)

    def test_time_subframe_has_auto_connect_checkbox(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._make_time_subframe)
        self.assertIn("Auto-connect to time1", src)
        self.assertIn("setChecked(True)", src)
        self.assertIn("_auto_connect_check", src)

    def test_subframe_router_routes_time(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._make_subframe)
        self.assertIn('"time"', src)
        self.assertIn("_make_time_subframe", src)

    def test_on_add_clicked_passes_auto_connect_time(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._on_add_clicked)
        self.assertIn("auto_connect_time", src)
        self.assertIn("_auto_connect_check.isChecked()", src)


# ===========================================================================
# quaternion (compound of 4 doubles X/Y/Z/W, identity [0,0,0,1]) +
# color (float3 usedAsColor, R/G/B).
# ===========================================================================


class TestQuaternionColorAuthoring(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_quaternion_input_creates_xyzw_double_children(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_in")
        n.add_input_attr("q", "quaternion")
        for axis in ("X", "Y", "Z", "W"):
            self.assertTrue(
                mc.attributeQuery("q" + axis, node=n.get_name(), exists=True)
            )
            self.assertEqual(
                mc.getAttr(n.get_name() + ".q" + axis, type=True), "double"
            )
        self.assertEqual(n.get_input_attr_map()["q"]["attr_type"], "quaternion")

    def test_quaternion_default_is_identity(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_id")
        n.add_input_attr("q", "quaternion")
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".qW"), 1.0)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".qX"), 0.0)

    def test_color_input_creates_rgb_float_children_used_as_color(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c_in")
        n.add_input_attr("col", "color")
        for axis in ("R", "G", "B"):
            self.assertTrue(
                mc.attributeQuery("col" + axis, node=n.get_name(), exists=True)
            )
            self.assertEqual(
                mc.getAttr(n.get_name() + ".col" + axis, type=True), "float"
            )
        self.assertTrue(
            mc.attributeQuery("col", node=n.get_name(), usedAsColor=True)
        )
        self.assertEqual(mc.getAttr(n.get_name() + ".col", type=True), "float3")
        self.assertEqual(n.get_input_attr_map()["col"]["attr_type"], "color")

    def test_quaternion_output_children(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_out")
        n.add_output_attr("q", "quaternion")
        for axis in ("X", "Y", "Z", "W"):
            self.assertEqual(
                mc.getAttr(n.get_name() + ".q" + axis, type=True), "double"
            )

    def test_color_output_used_as_color(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c_out")
        n.add_output_attr("col", "color")
        self.assertTrue(
            mc.attributeQuery("col", node=n.get_name(), usedAsColor=True)
        )

    def test_quaternion_rename_renames_xyzw(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_rn")
        n.add_input_attr("q", "quaternion")
        n.rename_input_attr("q", "quat")
        for axis in ("X", "Y", "Z", "W"):
            self.assertFalse(
                mc.attributeQuery("q" + axis, node=n.get_name(), exists=True)
            )
            self.assertTrue(
                mc.attributeQuery("quat" + axis, node=n.get_name(), exists=True)
            )

    def test_color_rename_renames_rgb(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c_rn")
        n.add_output_attr("col", "color")
        n.rename_output_attr("col", "tint")
        for axis in ("R", "G", "B"):
            self.assertFalse(
                mc.attributeQuery("col" + axis, node=n.get_name(), exists=True)
            )
            self.assertTrue(
                mc.attributeQuery("tint" + axis, node=n.get_name(), exists=True)
            )

    def test_both_in_valid_types(self):
        from mpynode.wrappers._mpy_node import (
            VALID_INPUT_TYPES,
            VALID_OUTPUT_TYPES,
        )

        for t in ("quaternion", "color"):
            self.assertIn(t, VALID_INPUT_TYPES)
            self.assertIn(t, VALID_OUTPUT_TYPES)


class TestQuaternionColorCompute(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_quaternion_input_reads_as_ndarray_4(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_rd")
        n.add_input_attr("q", "quaternion")
        n.add_output_attr("type_name", "string")
        n.set_compute_expression(
            "self.type_name = type(self.q).__name__ + ' ' + str(self.q.shape)"
        )
        self.assertEqual(mc.getAttr(n.get_name() + ".type_name"), "ndarray (4,)")

    def test_quaternion_input_value_roundtrip(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_val")
        n.add_input_attr("q", "quaternion")
        n.add_output_attr("s", "float")
        n.set_compute_expression("self.s = float(self.q[0]) + float(self.q[3])")
        mc.setAttr(n.get_name() + ".qX", 0.25)
        mc.setAttr(n.get_name() + ".qW", 0.5)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".s"), 0.75)

    def test_quaternion_output_write(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_wr")
        n.add_output_attr("q", "quaternion")
        n.set_compute_expression("self.q = [0.1, 0.2, 0.3, 0.4]")
        # Read the parent compound: a direct child getAttr does NOT trigger
        # compute on any compound output (vector/euler behave the same).
        got = mc.getAttr(n.get_name() + ".q")[0]
        for v, exp in zip(got, (0.1, 0.2, 0.3, 0.4)):
            self.assertAlmostEqual(v, exp)

    def test_color_input_reads_as_ndarray_3(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c_rd")
        n.add_input_attr("col", "color")
        n.add_output_attr("type_name", "string")
        n.set_compute_expression(
            "self.type_name = type(self.col).__name__ + ' ' + str(self.col.shape)"
        )
        self.assertEqual(mc.getAttr(n.get_name() + ".type_name"), "ndarray (3,)")

    def test_color_output_write(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c_wr")
        n.add_output_attr("col", "color")
        n.set_compute_expression("self.col = [0.5, 0.6, 0.7]")
        got = mc.getAttr(n.get_name() + ".col")[0]
        for v, exp in zip(got, (0.5, 0.6, 0.7)):
            self.assertAlmostEqual(v, exp, places=5)

    def test_multi_quaternion_output(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_marr")
        n.add_input_attr("count", "int")
        n.add_output_attr("out", "quaternion", is_array=True)
        n.set_compute_expression(
            "self.out = []\n"
            "for i in range(self.count):\n"
            "    self.out.append([float(i), float(i) * 0.1, float(i) * 0.2, 1.0])"
        )
        mc.setAttr(n.get_name() + ".count", 3)
        mc.setAttr(n.get_name() + ".count", 3)
        for i in range(3):
            vals = mc.getAttr("%s.out[%d]" % (n.get_name(), i))[0]
            self.assertAlmostEqual(vals[0], float(i))
            self.assertAlmostEqual(vals[3], 1.0)

    def test_multi_color_output(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c_marr")
        n.add_input_attr("count", "int")
        n.add_output_attr("out", "color", is_array=True)
        n.set_compute_expression(
            "self.out = []\n"
            "for i in range(self.count):\n"
            "    self.out.append([float(i) * 0.1, float(i) * 0.2, float(i) * 0.3])"
        )
        mc.setAttr(n.get_name() + ".count", 3)
        mc.setAttr(n.get_name() + ".count", 3)
        for i in range(3):
            vals = mc.getAttr("%s.out[%d]" % (n.get_name(), i))[0]
            self.assertAlmostEqual(vals[0], float(i) * 0.1, places=5)
            self.assertAlmostEqual(vals[2], float(i) * 0.3, places=5)

    def test_multi_quaternion_input_shape(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="q_min")
        n.add_input_attr("qin", "quaternion", is_array=True)
        n.add_output_attr("shape", "string")
        n.set_compute_expression("self.shape = str(self.qin.shape)")
        for i in range(2):
            for ax in "XYZW":
                mc.setAttr("%s.qin[%d].qin%s" % (n.get_name(), i, ax), 0.0)
        self.assertEqual(mc.getAttr(n.get_name() + ".shape"), "(2, 4)")


class TestColorInputDefaultValue(unittest.TestCase):
    """A ``color`` input can carry a real per-channel DEFAULT.

    Without one, a node that wants a sensible starting colour has to fake it in
    the compute -- "all zeros means unset, substitute a constant" -- which makes
    an explicitly dialled BLACK unreachable and puts a number in the Attribute
    Editor that is not the colour on screen. The default is the honest
    mechanism: a fresh node reads the seeded colour, and 0 means 0."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _node(self, name, **kw):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=name)
        n.add_input_attr("tint", "color", **kw)
        return n.get_name()

    def test_default_reaches_every_channel(self):
        nm = self._node("c_def", default_value=(0.25, 0.5, 0.95))
        r, g, b = mc.getAttr(nm + ".tint")[0]
        self.assertAlmostEqual(r, 0.25, places=6)
        self.assertAlmostEqual(g, 0.50, places=6)
        self.assertAlmostEqual(b, 0.95, places=6)

    def test_it_is_a_real_default_not_just_a_set_value(self):
        # must survive a reset-to-default, so it is the ATTRIBUTE's default
        nm = self._node("c_reset", default_value=(0.25, 0.5, 0.95))
        got = [mc.addAttr(nm + ".tint" + a, q=True, defaultValue=True)
               for a in "RGB"]
        self.assertEqual([round(v, 6) for v in got], [0.25, 0.5, 0.95])

    def test_an_explicit_zero_still_sticks(self):
        # the whole point: dialling black must give black
        nm = self._node("c_zero", default_value=(0.25, 0.5, 0.95))
        mc.setAttr(nm + ".tint", 0.0, 0.0, 0.0, type="double3")
        self.assertEqual([round(v, 6) for v in mc.getAttr(nm + ".tint")[0]],
                         [0.0, 0.0, 0.0])

    def test_no_default_still_starts_at_zero(self):
        # unchanged behaviour for every existing caller
        nm = self._node("c_none")
        self.assertEqual([round(v, 6) for v in mc.getAttr(nm + ".tint")[0]],
                         [0.0, 0.0, 0.0])

    def test_a_malformed_default_is_ignored_not_fatal(self):
        nm = self._node("c_bad", default_value=(0.5, 0.5))
        self.assertEqual([round(v, 6) for v in mc.getAttr(nm + ".tint")[0]],
                         [0.0, 0.0, 0.0])

    def test_a_scalar_default_is_ignored_not_broadcast(self):
        nm = self._node("c_scalar", default_value=0.5)
        self.assertEqual([round(v, 6) for v in mc.getAttr(nm + ".tint")[0]],
                         [0.0, 0.0, 0.0])

    def test_the_default_is_recorded_in_the_serialized_attr_map(self):
        # The plug-level default above is not enough on its own: .mpn templates
        # rebuild the attr from this JSON meta, so a default missing HERE is
        # applied at create time and then lost forever on save.
        from mpynode._common.io.mpn_io import serialize_node
        from mpynode._node_registry import wrap_node

        nm = self._node("c_ser", default_value=(0.25, 0.5, 0.95))
        payload = serialize_node(wrap_node(nm), include_persistent=False)
        meta = payload["input_attrs"]["tint"]
        self.assertIn("default_value", meta)
        self.assertEqual([round(v, 6) for v in meta["default_value"]],
                         [0.25, 0.5, 0.95])

    def test_no_default_records_nothing(self):
        # An untouched caller must keep a byte-identical payload, or every
        # colour-bearing node's port-cache key churns for no reason.
        from mpynode._common.io.mpn_io import serialize_node
        from mpynode._node_registry import wrap_node

        nm = self._node("c_ser_none")
        payload = serialize_node(wrap_node(nm), include_persistent=False)
        self.assertNotIn("default_value", payload["input_attrs"]["tint"])

    def test_the_default_survives_a_full_mpn_round_trip(self):
        # The end-to-end claim: a node rebuilt from its template comes back with
        # the colour it was authored with. This is the hop that was silently
        # dropping it -- the live plug had the default, the payload did not, so
        # every deserialized template read all-zero.
        from mpynode._common.io.mpn_io import deserialize_node, serialize_node
        from mpynode._node_registry import wrap_node

        nm = self._node("c_rt", default_value=(0.25, 0.5, 0.95))
        payload = serialize_node(wrap_node(nm), include_persistent=False)
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        back = deserialize_node(payload, restore_persistent=False)
        bn = back.get_name()
        self.assertEqual(
            [round(mc.addAttr(bn + ".tint" + a, q=True, defaultValue=True), 6)
             for a in "RGB"], [0.25, 0.5, 0.95])
        self.assertEqual([round(v, 6) for v in mc.getAttr(bn + ".tint")[0]],
                         [0.25, 0.5, 0.95])


class TestColorDefaultReachesTheSpec(unittest.TestCase):
    """spec_extractor's locator default-capture skipped every compound, so a
    colour default never reached codegen -- and ``_loc_color_inputs`` /
    ``_loc_color_default`` on the C++ side, which already emit
    ``nAttr.setDefault(r,g,b)``, were being handed None forever."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _spec(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.native.spec import spec_extractor

        w = MPyLocator.create(name="colDefLoc")
        w.add_input_attr("tint", "color", default_value=(0.25, 0.5, 0.95))
        w.set_compute_expression("self.draw = None\n")
        return spec_extractor.extract_spec(w.get_name())

    def test_the_spec_carries_the_colour_default(self):
        dv = self._spec()["inputs"]["tint"].get("default_value")
        self.assertIsNotNone(dv, "colour default was dropped by the extractor")
        self.assertEqual([round(float(v), 6) for v in dv], [0.25, 0.5, 0.95])

    def test_it_is_unwrapped_not_the_raw_getattr_nesting(self):
        # mc.getAttr on a colour returns [(r, g, b)] -- a 1-tuple of a triple.
        # Emitting that shape would make _loc_color_default produce garbage.
        dv = self._spec()["inputs"]["tint"]["default_value"]
        self.assertEqual(len(dv), 3)
        self.assertTrue(all(isinstance(v, float) for v in dv), dv)

    def test_it_becomes_setdefault_in_the_generated_cpp(self):
        # values compared numerically, not as literals: the plug is float32, so
        # 0.95 round-trips as 0.949999988079071 and an exact-string assert would
        # be testing float formatting rather than the wiring.
        import re
        from mpynode.native import compiler as codegen

        cpp = codegen._generate_locator_cpp(self._spec(), for_port=True)
        m = re.search(r"nAttr\.setDefault\(([-\d.e]+)f, ([-\d.e]+)f, "
                      r"([-\d.e]+)f\);", cpp)
        self.assertIsNotNone(m, "no nAttr.setDefault for the colour input")
        for got, want in zip(m.groups(), (0.25, 0.50, 0.95)):
            self.assertAlmostEqual(float(got), want, places=6)

        m = re.search(r"float\s+in_tint\[3\] = \{([-\d.e]+)f, ([-\d.e]+)f, "
                      r"([-\d.e]+)f\};", cpp)
        self.assertIsNotNone(m, "Inputs seed did not carry the colour default")
        for got, want in zip(m.groups(), (0.25, 0.50, 0.95)):
            self.assertAlmostEqual(float(got), want, places=6)

    def test_a_colour_with_no_default_stays_absent(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.native.spec import spec_extractor

        w = MPyLocator.create(name="colNoDef")
        w.add_input_attr("plain", "color")
        w.set_compute_expression("self.draw = None\n")
        spec = spec_extractor.extract_spec(w.get_name())
        dv = spec["inputs"]["plain"].get("default_value")
        self.assertIn(dv, (None, [0.0, 0.0, 0.0]))

    def test_non_colour_compounds_are_still_skipped(self):
        # the guard exists for a reason -- only `color` is being let through
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.native.spec import spec_extractor

        w = MPyLocator.create(name="quatLoc")
        w.add_input_attr("q", "quaternion")
        w.set_compute_expression("self.draw = None\n")
        spec = spec_extractor.extract_spec(w.get_name())
        self.assertNotIn("default_value", spec["inputs"]["q"])


class TestQuaternionColorDefaults(unittest.TestCase):
    def test_scalar_defaults(self):
        from mpynode._common.compute.output_defaults import scalar_default

        self.assertEqual(scalar_default("quaternion"), [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(scalar_default("color"), [0.0, 0.0, 0.0])

    def test_array_defaults(self):
        from mpynode._common.compute.output_defaults import array_default

        q = array_default("quaternion", 2)
        self.assertEqual(q.shape, (2, 4))
        self.assertTrue((q[:, 3] == 1.0).all())
        self.assertTrue((q[:, :3] == 0.0).all())
        c = array_default("color", 3)
        self.assertEqual(c.shape, (3, 3))


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestQuaternionColorUI(unittest.TestCase):
    def test_all_attr_types_includes_quaternion_color(self):
        from mpynode.ui.dialogs.add_attr import ALL_ATTR_TYPES

        self.assertIn("quaternion", ALL_ATTR_TYPES)
        self.assertIn("color", ALL_ATTR_TYPES)

    def test_attr_colors_have_quaternion_color(self):
        from mpynode.ui.widgets.icons import ATTR_TYPE_COLORS

        self.assertIn("quaternion", ATTR_TYPE_COLORS)
        self.assertIn("color", ATTR_TYPE_COLORS)

    def test_watch_reshape_quaternion_is_4(self):
        from mpynode.ui.widgets.watch import reshape_plug_value

        r = reshape_plug_value(
            [(0.1, 0.2, 0.3, 0.4)], {"attr_type": "quaternion"}
        )
        self.assertEqual(tuple(np.asarray(r).shape), (4,))

    def test_watch_reshape_color_is_3(self):
        from mpynode.ui.widgets.watch import reshape_plug_value

        r = reshape_plug_value([(0.1, 0.2, 0.3)], {"attr_type": "color"})
        self.assertEqual(tuple(np.asarray(r).shape), (3,))


class TestQuaternionColorAI(unittest.TestCase):
    def test_llm_tools_attr_types(self):
        from mpynode.ui.llm.tools import _ATTR_TYPES

        self.assertIn("quaternion", _ATTR_TYPES)
        self.assertIn("color", _ATTR_TYPES)

    def test_system_prompt_advertises_quaternion_and_color(self):
        from mpynode.ui.llm.system_prompt import build_system_prompt

        p = build_system_prompt()
        self.assertIn("quaternion", p)
        self.assertIn("color -> numpy (3,)", p)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestAttrTypeGrouping(unittest.TestCase):
    def test_groups_flatten_to_all_types(self):
        from mpynode.ui.dialogs.add_attr import (
            ALL_ATTR_TYPES, _ATTR_TYPE_GROUPS)

        flat = tuple(t for g in _ATTR_TYPE_GROUPS for t in g)
        self.assertEqual(flat, ALL_ATTR_TYPES)
        self.assertEqual(len(set(flat)), len(flat))
        self.assertEqual(len(_ATTR_TYPE_GROUPS), 5)

    def test_type_combo_grouped_no_separators_no_color(self):
        import sys

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog
        from mpynode.wrappers._mpy_node import VALID_INPUT_TYPES

        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import Qt
        except ImportError:
            from PySide2.QtWidgets import QApplication
            from PySide2.QtCore import Qt

        app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841

        class _Fake:
            def get_name(self):
                return "fakeNode"

            def list_valid_input_types(self):
                return list(VALID_INPUT_TYPES)

            def list_valid_output_types(self):
                return list(VALID_INPUT_TYPES)

        dlg = NDAddAttrDialog(None, _Fake(), "input")
        try:
            combo = dlg._type_combo
            n = combo.count()
            # no separators, no background colour: every item is a plain
            # selectable type, in family-group order.
            seps = [
                i for i in range(n)
                if combo.itemData(i, Qt.AccessibleDescriptionRole)
                == "separator"
            ]
            self.assertEqual(seps, [])
            items = [combo.itemText(i) for i in range(n)]
            self.assertEqual(
                items,
                [
                    "float", "int", "bool", "angle",
                    "vector", "euler", "matrix", "quaternion", "color",
                    "string", "enum", "hex", "python",
                    "mesh", "nurbsCurve", "nurbsSurface", "time",
                ],
            )
            for i in range(n):
                self.assertIsNone(
                    combo.itemData(i, Qt.BackgroundRole),
                    "item %d should have no background colour" % i)
        finally:
            dlg.deleteLater()

    def test_remembers_last_selected_type_across_dialogs(self):
        import sys

        from mpynode.ui.dialogs import add_attr
        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog
        from mpynode.wrappers._mpy_node import VALID_INPUT_TYPES

        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PySide2.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841

        class _Fake:
            def get_name(self):
                return "fakeNode"

            def list_valid_input_types(self):
                return list(VALID_INPUT_TYPES)

            def list_valid_output_types(self):
                return list(VALID_INPUT_TYPES)

        saved = add_attr._LAST_SELECTED_TYPE
        try:
            add_attr._LAST_SELECTED_TYPE = None
            dlg1 = NDAddAttrDialog(None, _Fake(), "input")
            try:
                i = dlg1._type_combo.findText("matrix")
                self.assertGreaterEqual(i, 0)
                dlg1._type_combo.setCurrentIndex(i)
                self.assertEqual(add_attr._LAST_SELECTED_TYPE, "matrix")
            finally:
                dlg1.deleteLater()

            # A freshly-opened dialog starts on the remembered type.
            dlg2 = NDAddAttrDialog(None, _Fake(), "input")
            try:
                self.assertEqual(dlg2._type_combo.currentText(), "matrix")
            finally:
                dlg2.deleteLater()
        finally:
            add_attr._LAST_SELECTED_TYPE = saved


def setUpModule():
    _setUpModule__phase18_7()
    _setUpModule__phase18_8()
    _setUpModule__phase18_9()


if __name__ == "__main__":
    import unittest
    unittest.main()
