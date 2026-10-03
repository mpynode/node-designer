"""Distance attr types: ``doubleLinear`` and ``position``.

``doubleLinear`` is Maya's distance (like translateX); ``position`` is a
double3 whose X/Y/Z children are doubleLinear (like translate). Both read and
write Maya's INTERNAL centimetres whatever the scene's linear unit, exactly as
``doubleAngle`` / ``euler`` read radians, and both wire to and from translate
with no unitConversion node. Every scene check runs at linear unit m AND cm;
the unit is restored afterwards.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QApplication must exist BEFORE standalone.initialize for the dialog tests.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = (_QApplication.instance()
             or _QApplication(["mayapy-distance-types-test"]))

import maya.cmds as mc  # noqa: E402
import numpy as np  # noqa: E402

from tests._setup import ensure_plugins_loaded, standalone_init  # noqa: E402


def setUpModule():
    standalone_init()


# Centimetres in one UI unit.
_CM_PER_UNIT = {"m": 100.0, "cm": 1.0}


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401
        return True
    except Exception:
        return False


def _as_double(plug):
    """The plug's value in internal units (cm for a distance)."""
    import maya.api.OpenMaya as om

    sel = om.MSelectionList()
    sel.add(plug)
    return sel.getPlug(0).asDouble()


class _UnitCase(unittest.TestCase):
    """Restores the scene's linear unit after every test."""

    def setUp(self):
        self._unit = mc.currentUnit(query=True, linear=True)

    def tearDown(self):
        mc.currentUnit(linear=self._unit)

    def _new_scene(self, unit):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        mc.currentUnit(linear=unit)
        self.assertEqual(mc.currentUnit(query=True, linear=True), unit)

    def _node(self, name):
        from mpynode.wrappers._mpy_node import MPyNode

        return MPyNode.create(name=name)


class TestPlugsCreated(_UnitCase):

    def test_position_is_double3_of_doubleLinear(self):
        for unit in _CM_PER_UNIT:
            with self.subTest(unit=unit):
                self._new_scene(unit)
                n = self._node("pos")
                n.add_input_attr("p", "position")
                n.add_output_attr("q", "position")
                n.add_input_attr("pa", "position", is_array=True)
                nm = n.get_name()
                for attr in ("p", "q", "pa"):
                    self.assertEqual(
                        mc.attributeQuery(attr, node=nm, attributeType=True),
                        "double3")
                    kids = mc.attributeQuery(attr, node=nm, listChildren=True)
                    self.assertEqual(
                        kids, [attr + "X", attr + "Y", attr + "Z"])
                    for kid in kids:
                        self.assertEqual(
                            mc.attributeQuery(kid, node=nm,
                                              attributeType=True),
                            "doubleLinear")
                amap = n.get_input_attr_map()
                self.assertEqual(amap["p"]["attr_type"], "position")

    def test_doubleLinear_is_doubleLinear(self):
        self._new_scene("cm")
        n = self._node("dl")
        n.add_input_attr("d", "doubleLinear")
        n.add_output_attr("o", "doubleLinear")
        nm = n.get_name()
        self.assertEqual(mc.attributeQuery("d", node=nm, attributeType=True),
                         "doubleLinear")
        self.assertEqual(mc.attributeQuery("o", node=nm, attributeType=True),
                         "doubleLinear")
        self.assertEqual(n.get_output_attr_map()["o"]["attr_type"],
                         "doubleLinear")

    def test_rename_renames_position_children(self):
        self._new_scene("cm")
        n = self._node("posRn")
        n.add_input_attr("p", "position")
        n.rename_input_attr("p", "where")
        nm = n.get_name()
        for axis in ("X", "Y", "Z"):
            self.assertFalse(mc.attributeQuery("p" + axis, node=nm,
                                               exists=True))
            self.assertEqual(
                mc.attributeQuery("where" + axis, node=nm, attributeType=True),
                "doubleLinear")


class TestTranslateWiring(_UnitCase):
    """translate <-> position and translateX <-> doubleLinear, at m and cm."""

    def _wired(self, unit):
        self._new_scene(unit)
        n = self._node("wire")
        n.add_input_attr("pIn", "position")
        n.add_input_attr("dIn", "doubleLinear")
        n.add_output_attr("pOut",   "position")
        n.add_output_attr("pTwice", "position")
        n.add_output_attr("dOut",   "doubleLinear")
        n.add_output_attr("seenX",  "double")
        n.add_output_attr("seenD",  "double")
        n.set_compute_expression(
            "self.pOut = self.pIn\n"
            "self.pTwice = self.pIn * 2\n"
            "self.dOut = self.dIn\n"
            "self.seenX = self.pIn[0]\n"
            "self.seenD = self.dIn\n")
        nm  = n.get_name()
        src = mc.createNode("transform", name="src")
        dst = mc.createNode("transform", name="dst")
        two = mc.createNode("transform", name="two")
        mc.setAttr(src + ".translate", 1.0, 2.0, 3.0)
        mc.connectAttr(src + ".translate",  nm + ".pIn")
        mc.connectAttr(src + ".translateX", nm + ".dIn")
        mc.connectAttr(nm + ".pOut",        dst + ".translate")
        mc.connectAttr(nm + ".pTwice",      two + ".translate")
        mc.connectAttr(nm + ".dOut",        dst + ".rotatePivotX")
        return nm, src, dst, two

    def test_no_unitConversion_node_at_any_unit(self):
        for unit in _CM_PER_UNIT:
            with self.subTest(unit=unit):
                self._wired(unit)
                self.assertEqual(mc.ls(type="unitConversion"), [])

    def test_translate_into_position_reads_cm(self):
        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                nm, _src, _dst, _two = self._wired(unit)
                # 1 UI unit of translateX reads 1 m -> 100.0 / 1 cm -> 1.0.
                self.assertAlmostEqual(mc.getAttr(nm + ".seenX"), 1.0 * cm)
                self.assertAlmostEqual(mc.getAttr(nm + ".seenD"), 1.0 * cm)

    def test_position_output_round_trips_to_translate(self):
        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                _nm, _src, dst, two = self._wired(unit)
                self.assertEqual(
                    [round(v, 9) for v in mc.getAttr(dst + ".translate")[0]],
                    [1.0, 2.0, 3.0])
                self.assertEqual(
                    [round(v, 9) for v in mc.getAttr(two + ".translate")[0]],
                    [2.0, 4.0, 6.0])
                self.assertAlmostEqual(_as_double(dst + ".translateZ"),
                                       3.0 * cm)

    def test_doubleLinear_output_round_trips(self):
        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                _nm, _src, dst, _two = self._wired(unit)
                self.assertAlmostEqual(mc.getAttr(dst + ".rotatePivotX"), 1.0)
                self.assertAlmostEqual(_as_double(dst + ".rotatePivotX"),
                                       1.0 * cm)

    def test_arrays_read_and_write_cm(self):
        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                self._new_scene(unit)
                n = self._node("arr")
                n.add_input_attr("pArr", "position", is_array=True)
                n.add_input_attr("dArr", "doubleLinear", is_array=True)
                n.add_output_attr("pArrOut", "position", is_array=True)
                n.add_output_attr("dArrOut", "doubleLinear", is_array=True)
                n.add_output_attr("seen", "string")
                n.set_compute_expression(
                    "self.pArrOut = self.pArr\n"
                    "self.dArrOut = self.dArr\n"
                    "self.seen = repr((self.pArr.shape, self.pArr.tolist(),"
                    " self.dArr.tolist()))\n")
                nm  = n.get_name()
                src = mc.createNode("transform", name="asrc")
                mc.setAttr(src + ".translate", 1.0, 2.0, 3.0)
                mc.connectAttr(src + ".translate", nm + ".pArr[1]")
                mc.connectAttr(src + ".translateY", nm + ".dArr[1]")
                dst = mc.createNode("transform", name="adst")
                mc.connectAttr(nm + ".pArrOut[1]", dst + ".translate")
                self.assertEqual(
                    [round(v, 9) for v in mc.getAttr(dst + ".translate")[0]],
                    [1.0, 2.0, 3.0])
                shape, pts, ds = eval(mc.getAttr(nm + ".seen"))
                self.assertEqual(shape, (2, 3))
                self.assertEqual(pts, [[0.0, 0.0, 0.0],
                                       [1.0 * cm, 2.0 * cm, 3.0 * cm]])
                self.assertEqual(ds, [0.0, 2.0 * cm])
                self.assertAlmostEqual(_as_double(nm + ".dArrOut[1]"),
                                       2.0 * cm)
                self.assertEqual(mc.ls(type="unitConversion"), [])


class TestLimitsAreCentimetres(_UnitCase):

    def test_min_max_default_land_in_cm(self):
        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                self._new_scene(unit)
                n = self._node("lim")
                n.add_input_attr("d", "doubleLinear", min_value=-500.0,
                                 max_value=500.0, default_value=150.0)
                nm = n.get_name()
                # addAttr stores internal cm; attributeQuery reports UI units.
                self.assertAlmostEqual(
                    mc.addAttr(nm + ".d", query=True, defaultValue=True),
                    150.0)
                self.assertAlmostEqual(_as_double(nm + ".d"), 150.0)
                self.assertAlmostEqual(
                    mc.attributeQuery("d", node=nm, minimum=True)[0],
                    -500.0 / cm)
                self.assertAlmostEqual(
                    mc.attributeQuery("d", node=nm, maximum=True)[0],
                    500.0 / cm)
                self.assertAlmostEqual(mc.getAttr(nm + ".d"), 150.0 / cm)
                meta = n.get_input_attr_map()["d"]
                self.assertEqual((meta["min_value"], meta["max_value"],
                                  meta["default_value"]),
                                 (-500.0, 500.0, 150.0))

    def test_array_gap_reads_the_default_in_cm(self):
        for unit in _CM_PER_UNIT:
            with self.subTest(unit=unit):
                self._new_scene(unit)
                n = self._node("gap")
                n.add_input_attr("dArr", "doubleLinear", is_array=True,
                                 default_value=25.0)
                n.add_output_attr("seen", "string")
                n.set_compute_expression(
                    "self.seen = repr(self.dArr.tolist())\n")
                nm = n.get_name()
                mc.setAttr(nm + ".dArr[2]", 1.0)
                cm = _CM_PER_UNIT[unit]
                self.assertEqual(eval(mc.getAttr(nm + ".seen")),
                                 [25.0, 25.0, 1.0 * cm])


class TestOtherReadPaths(_UnitCase):

    def test_datablock_path_reads_and_writes_cm(self):
        # mPyFile reads through read_user_inputs_dict_from_datablock (the
        # worker-thread-safe handle reads).
        from mpynode.wrappers.mpy_file import MPyFile

        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                self._new_scene(unit)
                p = MPyFile.create(name="fDist", seed_defaults=False)
                p.add_input_attr("pIn", "position")
                p.add_input_attr("dIn", "doubleLinear")
                p.add_input_attr("pArr", "position", is_array=True)
                p.add_output_attr("pOut", "position")
                p.add_output_attr("seen", "double3")
                p.set_compute_expression(
                    "self.pOut = self.pIn\n"
                    "self.seen = [self.dIn, self.pArr[1][2],"
                    " float(self.pArr.shape[0])]\n")
                nm  = p.get_name()
                src = mc.createNode("transform", name="fsrc")
                mc.setAttr(src + ".translate", 1.0, 2.0, 3.0)
                mc.connectAttr(src + ".translate",  nm + ".pIn")
                mc.connectAttr(src + ".translateX", nm + ".dIn")
                mc.connectAttr(src + ".translate",  nm + ".pArr[1]")
                dst = mc.createNode("transform", name="fdst")
                mc.connectAttr(nm + ".pOut", dst + ".translate")
                loc = mc.spaceLocator(name="fseen")[0]
                mc.connectAttr(nm + ".seen", loc + ".scale")
                self.assertEqual(
                    [round(v, 9) for v in mc.getAttr(dst + ".translate")[0]],
                    [1.0, 2.0, 3.0])
                self.assertEqual(
                    [round(v, 9) for v in mc.getAttr(loc + ".scale")[0]],
                    [1.0 * cm, 3.0 * cm, 2.0])

    def test_api1_transform_reads_cm(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                self._new_scene(unit)
                t  = MPyTransform.create(name="txDist")
                nm = t.get_name()
                t.add_input_attr("pIn", "position")
                src = mc.createNode("transform", name="tsrc")
                mc.setAttr(src + ".translate", 1.0, 2.0, 3.0)
                mc.connectAttr(src + ".translate", nm + ".pIn")
                t.set_compute_expression(
                    "import numpy as np\n"
                    "m = np.eye(4)\n"
                    "m[3, :3] = np.asarray(self.pIn, dtype=float)\n"
                    "self.local_matrix = m\n"
                    "self.apply_translate = True\n")
                # A matrix is internal units: the cm the expression read.
                wm = mc.getAttr(nm + ".worldMatrix[0]")
                self.assertEqual([round(v, 6) for v in wm[12:15]],
                                 [1.0 * cm, 2.0 * cm, 3.0 * cm])
                self.assertEqual(mc.ls(type="unitConversion"), [])

    def test_api1_transform_writes_cm(self):
        # mPyTransform runs its expression with no datablock, so its outputs
        # go out through cmds.setAttr, which takes UI units.
        from mpynode.wrappers.mpy_transform import MPyTransform

        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                self._new_scene(unit)
                t  = MPyTransform.create(name="txOut")
                nm = t.get_name()
                t.add_input_attr("pIn", "position")
                t.add_input_attr("dIn", "doubleLinear")
                t.add_output_attr("pOut", "position")
                t.add_output_attr("dOut", "doubleLinear")
                t.add_output_attr("pArrOut", "position", is_array=True)
                src = mc.createNode("transform", name="txSrc")
                mc.setAttr(src + ".translate", 1.0, 2.0, 3.0)
                mc.connectAttr(src + ".translate", nm + ".pIn")
                mc.connectAttr(src + ".translateX", nm + ".dIn")
                t.set_compute_expression(
                    "import numpy as np\n"
                    "self.pOut = self.pIn\n"
                    "self.dOut = self.dIn\n"
                    "self.pArrOut = np.asarray([self.pIn, self.pIn * 2])\n")
                dst = mc.createNode("transform", name="txDst")
                mc.connectAttr(nm + ".pOut", dst + ".translate")
                mc.connectAttr(nm + ".dOut", dst + ".rotatePivotX")
                # The transform's own matrix pull runs the expression.
                mc.getAttr(nm + ".worldMatrix[0]")
                self.assertEqual(
                    [round(v, 9) for v in mc.getAttr(dst + ".translate")[0]],
                    [1.0, 2.0, 3.0])
                for axis, want in zip("XYZ", (1.0, 2.0, 3.0)):
                    self.assertAlmostEqual(_as_double(nm + ".pOut" + axis),
                                           want * cm)
                self.assertAlmostEqual(_as_double(nm + ".dOut"), 1.0 * cm)
                self.assertAlmostEqual(_as_double(dst + ".rotatePivotX"),
                                       1.0 * cm)
                self.assertAlmostEqual(
                    _as_double(nm + ".pArrOut[1].pArrOutZ"), 6.0 * cm)
                self.assertEqual(mc.ls(type="unitConversion"), [])

    def test_setattr_writer_converts_user_distances_only(self):
        # The writer behind every api1 plug-proxy write with no datablock
        # (mPyTransform / mPyIkSolver outputs, the Init tab). A user distance
        # attr (dynamic) takes internal cm; a built-in distance plug keeps
        # setAttr's UI units, unchanged by the distance types.
        import maya.OpenMaya as om1

        from mpynode._common.plugs.plug_write import _write_plug_init_time

        def write(path, value):
            sel = om1.MSelectionList()
            sel.add(path)
            plug = om1.MPlug()
            sel.getPlug(0, plug)
            _write_plug_init_time(plug, plug.attribute(), value)

        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                self._new_scene(unit)
                nm = mc.createNode("transform", name="wDst")
                mc.addAttr(nm, longName="len", attributeType="doubleLinear")
                mc.addAttr(nm, longName="pos", attributeType="double3")
                for axis in "XYZ":
                    mc.addAttr(nm, longName="pos" + axis,
                               attributeType="doubleLinear", parent="pos")
                write(nm + ".len",        250.0)
                write(nm + ".pos",        (100.0, 200.0, 300.0))
                write(nm + ".translateX", 5.0)
                write(nm + ".scale",      (2.0, 3.0, 4.0))
                self.assertEqual(_as_double(nm + ".len"), 250.0)
                self.assertEqual(
                    [_as_double(nm + ".pos" + a) for a in "XYZ"],
                    [100.0, 200.0, 300.0])
                self.assertAlmostEqual(
                    _as_double(nm + ".translateX"), 5.0 * cm)
                self.assertEqual(list(mc.getAttr(nm + ".scale")[0]),
                                 [2.0, 3.0, 4.0])

    def test_watch_shows_cm(self):
        from mpynode.ui.widgets.watch import reshape_plug_value

        for unit, cm in _CM_PER_UNIT.items():
            with self.subTest(unit=unit):
                self._new_scene(unit)
                np.testing.assert_allclose(
                    reshape_plug_value([(1.0, 2.0, 3.0)],
                                       {"attr_type": "position"}),
                    [1.0 * cm, 2.0 * cm, 3.0 * cm])
                self.assertAlmostEqual(
                    reshape_plug_value(1.5, {"attr_type": "doubleLinear"}),
                    1.5 * cm)

    def test_output_seeds(self):
        from mpynode._common.compute.output_defaults import (array_default,
                                                             scalar_default)

        self.assertEqual(scalar_default("doubleLinear"),         0.0)
        self.assertEqual(scalar_default("position"),             [0.0, 0.0, 0.0])
        self.assertEqual(array_default("doubleLinear", 2).shape, (2,))
        self.assertEqual(array_default("position", 2).shape,     (2, 3))
        self.assertFalse(array_default("position", 2).any())


class TestTheTable(unittest.TestCase):

    def test_rows(self):
        from mpynode._common import attr_types

        dl  = attr_types.BY_NAME["doubleLinear"]
        pos = attr_types.BY_NAME["position"]
        self.assertEqual(dl.add_attr,    {"at": "doubleLinear"})
        self.assertEqual(dl.artist,      "distance")
        self.assertEqual(dl.description, "doubleLinear (cm)")
        self.assertEqual(pos.add_attr,   {"at": "double3"})
        self.assertEqual(pos.artist,     "position")
        self.assertEqual(pos.description,
                         "double3 of doubleLinear (cm)")
        self.assertIn("doubleLinear", attr_types.ASSISTANT_NAMES)
        self.assertIn("position", attr_types.ASSISTANT_NAMES)

    def test_groups(self):
        from mpynode._common import attr_types

        numbers, compounds = attr_types.DIALOG_GROUPS[:2]
        self.assertEqual(numbers.index("doubleLinear"),
                         numbers.index("doubleAngle") + 1)
        # position leads the 3-vectors, before vector and euler.
        self.assertEqual(compounds[:3], ("position", "double3", "euler"))

    def test_both_prompts_give_the_shapes_and_the_rule(self):
        from mpynode.ui.llm.system_prompt import (build_payload_system_prompt,
                                                  build_system_prompt)

        for p in (build_system_prompt(), build_payload_system_prompt()):
            self.assertIn("distance (doubleLinear) -> float (cm)", p)
            self.assertIn("position -> numpy (3,) cm", p)
            flat = " ".join(p.split())
            self.assertIn('"position" for anything wired to or from translate '
                          'or a point', flat)
            self.assertIn('"euler" for rotate', flat)
            self.assertIn('"vector" (double3) for a unitless 3-vector '
                          'such as a direction or scale', flat)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestDialog(unittest.TestCase):

    def _dialog(self):
        import sys

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

        return NDAddAttrDialog(None, _Fake(), "input")

    def test_offers_both_in_their_groups(self):
        from mpynode._common import attr_types
        from mpynode.ui.dialogs.add_attr import _ATTR_TYPE_GROUPS

        self.assertIn("doubleLinear", _ATTR_TYPE_GROUPS[0])
        self.assertIn("position", _ATTR_TYPE_GROUPS[1])
        dlg = self._dialog()
        try:
            combo = dlg._type_combo
            names = [combo.itemData(i) for i in range(combo.count())]
            self.assertEqual(names.index("doubleLinear"),
                             names.index("doubleAngle") + 1)
            # position opens the 3-vector family, right after its separator.
            self.assertIsNone(names[names.index("position") - 1])
            self.assertEqual(names.index("double3"),
                             names.index("position") + 1)
            self.assertEqual(combo.itemText(names.index("doubleLinear")),
                             "distance - doubleLinear (cm)")
            self.assertEqual(combo.itemText(names.index("position")),
                             attr_types.dialog_label("position"))
        finally:
            dlg.deleteLater()

    def test_numeric_labels_carry_the_unit(self):
        dlg = self._dialog()
        try:
            want = {
                "doubleAngle": ("Min (radians):", "Max (radians):",
                                "Default (radians):"),
                "doubleLinear": ("Min (cm):", "Max (cm):", "Default (cm):"),
                "double":       ("Min:", "Max:", "Default:"),
                "float":        ("Min:", "Max:", "Default:"),
                "long":         ("Min:", "Max:", "Default:"),
            }
            for attr_type, labels in want.items():
                sub = dlg._make_subframe(attr_type)
                try:
                    self.assertEqual(
                        (sub._min_label.text(), sub._max_label.text(),
                         sub._default_label.text()),
                        labels, attr_type)
                finally:
                    sub.deleteLater()
            # position is a compound: no numeric subframe.
            sub = dlg._make_subframe("position")
            self.assertFalse(hasattr(sub, "_min_edit"))
            sub.deleteLater()
        finally:
            dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
