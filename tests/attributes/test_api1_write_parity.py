"""An api1 write lands in the units and encoding the same type READS as.

Reads are the reference: an angle reads in radians, a distance in centimetres,
a ``time`` in the UI time unit (frames), a ``hex`` as decoded text and a
``pickle`` as the unpickled object. An expression that copies an input to an
output of the same type must therefore produce an output that reads back the
same value, whatever the scene's units.

The api1 writers covered here:

* ``plug_write._write_plug_init_time`` -- ``cmds.setAttr``, which takes UI
  units. It is the output path of mPyTransform and mPyIkSolver.
* ``plug_write._write_plug_compute_time`` -- the datablock path of the
  deformer family (mPyDeformer / mPyBlendShape / mPySkinCluster).

The thread-safe datablock READ of mPyFile is checked against the plug read of
mPyNode at the end.
"""

from __future__ import annotations

import base64
import json
import os
import pickle
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import maya.cmds as mc  # noqa: E402

from tests._setup import ensure_plugins_loaded, standalone_init  # noqa: E402


def setUpModule():
    standalone_init()


def _plug2(path):
    import maya.api.OpenMaya as om

    sel = om.MSelectionList()
    sel.add(path)
    return sel.getPlug(0)


def _read(path, attr_type):
    """The reference read: what an expression sees for this plug."""
    from mpynode._api2.helpers import read_plug_value

    return read_plug_value(_plug2(path), attr_type)


def _as_double(path):
    """Internal units: radians for an angle, centimetres for a distance."""
    return _plug2(path).asDouble()


def _unpickle(raw):
    try:
        return pickle.loads(base64.b64decode(raw.encode("ascii")))
    except Exception:
        return "<not a pickle payload: %r>" % (raw,)


class _UnitCase(unittest.TestCase):
    """Restores the scene's units after every test."""

    def setUp(self):
        self._units = {k: mc.currentUnit(query=True, **{k: True})
                       for k in ("linear", "angle", "time")}

    def tearDown(self):
        mc.currentUnit(linear=self._units["linear"],
                       angle=self._units["angle"])
        mc.currentUnit(time=self._units["time"])

    def _new_scene(self, angle="deg", linear="cm", time="film"):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        mc.currentUnit(linear=linear, angle=angle)
        mc.currentUnit(time=time)

    def _deform(self, plane):
        mc.dgeval(mc.listRelatives(plane, shapes=True)[0] + ".outMesh")


class TestInitTimeWriterUnits(_UnitCase):
    """``_write_plug_init_time`` takes internal units on every unit plug."""

    def _write(self, path, value):
        import maya.OpenMaya as om1

        from mpynode._common.plugs.plug_write import _write_plug_init_time

        sel = om1.MSelectionList()
        sel.add(path)
        plug = om1.MPlug()
        sel.getPlug(0, plug)
        _write_plug_init_time(plug, plug.attribute(), value)

    def test_angles_and_distances_take_internal_units(self):
        for angle, linear in (("deg", "cm"), ("deg", "m"),
                              ("rad", "cm"), ("rad", "m")):
            with self.subTest(angle=angle, linear=linear):
                self._new_scene(angle=angle, linear=linear)
                nm = mc.createNode("transform", name="wUnits")
                mc.addAttr(nm, longName="ang", attributeType="doubleAngle")
                mc.addAttr(nm, longName="eul", attributeType="double3")
                for axis in "XYZ":
                    mc.addAttr(nm, longName="eul" + axis,
                               attributeType="doubleAngle", parent="eul")
                self._write(nm + ".ang",        0.5)
                self._write(nm + ".eul",        (0.1, 0.2, 0.3))
                self._write(nm + ".rotateX",    0.25)
                self._write(nm + ".rotate",     (0.4, 0.5, 0.6))
                self._write(nm + ".translate",  (1.0, 2.0, 3.0))
                self._write(nm + ".translateX", 5.0)
                self._write(nm + ".scale",      (2.0, 3.0, 4.0))
                self.assertAlmostEqual(_as_double(nm + ".ang"), 0.5)
                self.assertEqual(
                    [round(_as_double(nm + ".eul" + a), 9) for a in "XYZ"],
                    [0.1, 0.2, 0.3])
                self.assertAlmostEqual(_as_double(nm + ".rotateX"), 0.4)
                self.assertEqual(
                    [round(_as_double(nm + ".rotate" + a), 9) for a in "YZ"],
                    [0.5, 0.6])
                self.assertAlmostEqual(_as_double(nm + ".translateX"), 5.0)
                self.assertEqual(
                    [round(_as_double(nm + ".translate" + a), 9)
                     for a in "YZ"],
                    [2.0, 3.0])
                self.assertEqual(list(mc.getAttr(nm + ".scale")[0]),
                                 [2.0, 3.0, 4.0])

    def test_time_takes_the_ui_time_unit(self):
        for unit in ("film", "ntsc"):
            with self.subTest(unit=unit):
                self._new_scene(time=unit)
                nm = mc.createNode("transform", name="wTime")
                mc.addAttr(nm, longName="tm", attributeType="time")
                self._write(nm + ".tm", 12.0)
                self.assertAlmostEqual(_read(nm + ".tm", "time"), 12.0)


class TestTransformOutputs(_UnitCase):
    """mPyTransform: every output reads back what the expression wrote."""

    def test_angle_outputs_round_trip(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        for angle in ("deg", "rad"):
            with self.subTest(angle=angle):
                self._new_scene(angle=angle)
                t  = MPyTransform.create(name="txAng")
                nm = t.get_name()
                t.add_input_attr("aIn", "doubleAngle")
                t.add_input_attr("eIn", "euler")
                t.add_output_attr("aOut", "doubleAngle")
                t.add_output_attr("eOut", "euler")
                mc.setAttr(nm + ".aIn", 30.0 if angle == "deg" else 0.5)
                mc.setAttr(nm + ".eIn", 0.1, 0.2, 0.3)
                t.set_compute_expression(
                    "self.aOut = self.aIn\n"
                    "self.eOut = self.eIn\n")
                mc.getAttr(nm + ".worldMatrix[0]")
                self.assertAlmostEqual(_read(nm + ".aOut", "doubleAngle"),
                                       _read(nm + ".aIn", "doubleAngle"))
                self.assertEqual(
                    [round(v, 9) for v in _read(nm + ".eOut", "euler")],
                    [round(v, 9) for v in _read(nm + ".eIn", "euler")])

    def test_hex_and_pickle_outputs_are_encoded(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        self._new_scene()
        t  = MPyTransform.create(name="txStr")
        nm = t.get_name()
        t.add_output_attr("hx", "hex")
        t.add_output_attr("pk", "pickle")
        t.set_compute_expression(
            "self.hx = 'Hi ' + chr(233)\n"
            "self.pk = {'a': [1, 2]}\n")
        mc.getAttr(nm + ".worldMatrix[0]")
        self.assertEqual(mc.getAttr(nm + ".hx"),            "48 69 20 c3 a9")
        self.assertEqual(_read(nm + ".hx", "hex"),          "Hi é")
        self.assertEqual(_unpickle(mc.getAttr(nm + ".pk")), {"a": [1, 2]})
        self.assertEqual(_read(nm + ".pk", "pickle"),       {"a": [1, 2]})


class TestDeformerOutputs(_UnitCase):
    """The deformer family writes through the datablock."""

    def _deformer(self, name):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(sx=1, sy=1)[0]
        d     = MPyDeformer.create_on(plane, name=name)
        return plane, d, d.get_name()

    def test_time_output_reads_like_a_time_input(self):
        for unit in ("film", "ntsc"):
            with self.subTest(unit=unit):
                self._new_scene(time=unit)
                plane, d, dn = self._deformer("dTime")
                d.add_input_attr("tIn", "time")
                d.add_output_attr("tOut", "time")
                d.set_compute_expression(
                    (d.get_compute_expression() or "")
                    + "\nself.tOut = self.tIn\n")
                mc.currentTime(12)
                self._deform(plane)
                self.assertAlmostEqual(_read(dn + ".tIn", "time"), 12.0)
                self.assertAlmostEqual(_read(dn + ".tOut", "time"), 12.0)

    def test_hex_and_pickle_outputs_are_encoded(self):
        self._new_scene()
        plane, d, dn = self._deformer("dStr")
        d.add_output_attr("hx", "hex")
        d.add_output_attr("pk", "pickle")
        d.add_output_attr("hxArr", "hex", is_array=True)
        # A consumer sizes the array output's seeded buffer to one element.
        sink = mc.createNode("transform", name="hxSink")
        mc.addAttr(sink, longName="str", dataType="string")
        mc.connectAttr(dn + ".hxArr[0]", sink + ".str")
        d.set_compute_expression(
            (d.get_compute_expression() or "")
            + "\nself.hx = 'Hi'\n"
            "self.pk = (1, 'two')\n"
            "self.hxArr[0] = 'Ok'\n")
        self._deform(plane)
        self.assertEqual(mc.getAttr(dn + ".hx"),            "48 69")
        self.assertEqual(_read(dn + ".hx", "hex"),          "Hi")
        self.assertEqual(_unpickle(mc.getAttr(dn + ".pk")), (1, "two"))
        self.assertEqual(mc.getAttr(dn + ".hxArr[0]"),      "4f 6b")


_DUMP = (
    "import json\n"
    "import numpy as np\n"
    "def _d(v):\n"
    "    if isinstance(v, np.ndarray):\n"
    "        return ['ndarray', list(v.shape), v.tolist()]\n"
    "    return [type(v).__name__, None, v]\n"
    "self.seen = json.dumps(\n"
    "    {k: _d(getattr(self, k))\n"
    "     for k in ('fUv', 'fUvArr', 'fHx', 'fHxArr', 'fPk', 'fPkArr')},\n"
    "    default=repr, sort_keys=True)\n"
)


class TestFileDatablockReads(_UnitCase):
    """mPyFile reads its inputs off data handles (worker-thread safe); the
    values must be identical to the plug read every other node uses."""

    def _inputs(self, node, nm):
        node.add_input_attr("fUv", "float2")
        node.add_input_attr("fUvArr", "float2", is_array=True)
        node.add_input_attr("fHx", "hex")
        node.add_input_attr("fHxArr", "hex", is_array=True)
        node.add_input_attr("fPk", "pickle")
        node.add_input_attr("fPkArr", "pickle", is_array=True)
        node.add_output_attr("seen", "string")
        mc.setAttr(nm + ".fUv",       0.25,    0.75)
        mc.setAttr(nm + ".fUvArr[0]", 0.125,   0.5)
        mc.setAttr(nm + ".fUvArr[2]", 0.375,   0.625)
        mc.setAttr(nm + ".fHx",       "48 69", type="string")
        mc.setAttr(nm + ".fHxArr[1]", "4f 6b", type="string")
        payload = base64.b64encode(pickle.dumps({"a": [1, 2]})).decode("ascii")
        mc.setAttr(nm + ".fPk", payload, type="string")
        mc.setAttr(nm + ".fPkArr[0]", payload, type="string")

    def test_matches_the_plug_read(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.wrappers.mpy_file import MPyFile

        self._new_scene()
        n  = MPyNode.create(name="plugRead")
        nn = n.get_name()
        self._inputs(n, nn)
        n.set_compute_expression(_DUMP)
        want = json.loads(mc.getAttr(nn + ".seen"))
        self.assertEqual(want["fUv"], ["ndarray", [2], [0.25, 0.75]])
        self.assertEqual(want["fHx"], ["str", None, "Hi"])
        self.assertEqual(want["fPk"], ["dict", None, {"a": [1, 2]}])

        f = MPyFile.create(name="dbRead", seed_defaults=False,
                            as_texture=False)
        fn = f.get_name()
        self._inputs(f, fn)
        f.set_compute_expression(_DUMP + "self.outColor = (0.5, 0.5, 0.5)\n")
        mc.getAttr(fn + ".outColor")
        got = json.loads(mc.getAttr(fn + ".seen"))
        for key in sorted(want):
            with self.subTest(key=key):
                self.assertEqual(got[key], want[key])


if __name__ == "__main__":
    unittest.main()
