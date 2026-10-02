"""The one attr type table (``_common/attr_types.py``): two names, one stored.

* every list of types (wrapper, dialog, assistant tool, assistant prompt)
  comes from the table and agrees with it;
* every type has an artist name and a description; the artist names that
  differ from the stored name, plus Maya's ``double4`` / ``float3``, are
  aliases, translated to the stored name at every input point (the wrapper,
  the ``.mpn`` restore, scene attr maps, the plug readers, the compile spec);
* ``python`` is retired (renamed ``pickle``) and rejected with that hint;
* ``tools/migrate_attr_names.py`` translates data to stored names, is
  idempotent and leaves the repo clean.
"""

from __future__ import annotations

import collections
import importlib.util
import io
import json
import math
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import maya.cmds as mc

from tests._paths import ROOT
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


# (stored, artist, description), in table order.
_TABLE = [
    ("double", "float64", "double (64-bit)"),
    ("float", "float32", "float (32-bit)"),
    ("long", "int", "long"),
    ("bool", "bool", "bool (on / off)"),
    ("doubleAngle", "angle", "doubleAngle (radians)"),
    ("doubleLinear", "distance", "doubleLinear (cm)"),
    ("double3", "vector", "double3 (no unit)"),
    ("euler", "euler", "double3 of doubleAngle (radians)"),
    ("position", "position", "double3 of doubleLinear (cm)"),
    ("matrix", "matrix", "matrix (4x4 doubles)"),
    ("quaternion", "quaternion", "double4 (X/Y/Z/W)"),
    ("color", "color", "float3 (colour)"),
    ("float2", "uv", "float2 (U/V)"),
    ("string", "string", "string (text)"),
    ("enum", "enum", "enum (named choices, default False/True)"),
    ("hex", "hex", "string (stored as UTF-8 hex)"),
    ("pickle", "pickle", "string (pickled data, C++ unsupported)"),
    ("mesh", "mesh", "mesh (code gets a Mesh object)"),
    ("nurbsCurve", "nurbsCurve", "nurbsCurve (code gets a NurbsCurve object)"),
    ("nurbsSurface", "nurbsSurface",
     "nurbsSurface (code gets a NurbsSurface object)"),
    ("time", "time", "time (frames)"),
]

_ALIASES = {
    "float64":  "double",
    "float32":  "float",
    "int":      "long",
    "angle":    "doubleAngle",
    "distance": "doubleLinear",
    "vector":   "double3",
    "uv":       "float2",
    "double4":  "quaternion",
    "float3":   "color",
}

_PYTHON = "attr_type 'python' was renamed: use 'pickle'"


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401
        return True
    except Exception:
        return False


class TestTheTable(unittest.TestCase):

    def test_dialog_order_double_first(self):
        from mpynode._common import attr_types

        self.assertEqual(attr_types.ALL_NAMES[0],    "double")
        self.assertEqual(attr_types.DIALOG_NAMES[0], "double")
        self.assertEqual(attr_types.DIALOG_DEFAULT,  "double")

    def test_float2_offered_after_color(self):
        from mpynode._common import attr_types

        self.assertIn("float2", attr_types.DIALOG_NAMES)
        self.assertIn("float2", attr_types.ASSISTANT_NAMES)
        group = attr_types.DIALOG_GROUPS[1]
        self.assertEqual(group.index("float2"), group.index("color") + 1)
        self.assertEqual(attr_types.BY_NAME["float2"].label, "2 floats U/V")
        self.assertEqual(attr_types.dialog_label("float2"),
                         "float2  -  2 floats U/V")

    def test_assistant_list_is_the_dialog_list(self):
        from mpynode._common import attr_types

        self.assertEqual(attr_types.ASSISTANT_NAMES, attr_types.DIALOG_NAMES)

    def test_artist_names_and_descriptions(self):
        from mpynode._common import attr_types

        got = [(t.name, t.artist, t.description)
               for t in attr_types.ATTR_TYPES]
        self.assertEqual(got, _TABLE)

    def test_aliases(self):
        from mpynode._common import attr_types

        self.assertEqual(attr_types.ALIASES, _ALIASES)
        for alias, stored in attr_types.ALIASES.items():
            self.assertNotIn(alias, attr_types.ALL_NAMES)
            self.assertIn(stored, attr_types.ALL_NAMES)
            self.assertNotIn(alias, attr_types.RETIRED)

    def test_python_is_the_only_retired_name(self):
        from mpynode._common import attr_types

        self.assertEqual(attr_types.RETIRED, {"python": "pickle"})
        self.assertNotIn("python", attr_types.ALL_NAMES)
        self.assertIn("pickle", attr_types.ALL_NAMES)
        self.assertFalse(hasattr(attr_types, "RETIRED_HINTS"))

    def test_canonical(self):
        from mpynode._common import attr_types

        for name in attr_types.ALL_NAMES:
            self.assertEqual(attr_types.canonical(name), name)
        for alias, stored in _ALIASES.items():
            self.assertEqual(attr_types.canonical(alias), stored)
        with self.assertRaises(ValueError) as cm:
            attr_types.canonical("python")
        self.assertEqual(str(cm.exception), _PYTHON)
        for bad in ("banana", None, 3, "Double", ""):
            with self.assertRaises(ValueError):
                attr_types.canonical(bad)

    def test_stored_name_never_raises(self):
        from mpynode._common import attr_types

        self.assertEqual(attr_types.stored_name("vector"),  "double3")
        self.assertEqual(attr_types.stored_name("double3"), "double3")
        self.assertEqual(attr_types.stored_name("python"),  "python")
        self.assertEqual(attr_types.stored_name("banana"),  "banana")
        self.assertIsNone(attr_types.stored_name(None))

    def test_upgrade_legacy_name(self):
        # v1 data: int / vector / angle / python map to the stored names.
        from mpynode._common import attr_types

        self.assertEqual(attr_types.upgrade_legacy_name("int"), "long")
        self.assertEqual(attr_types.upgrade_legacy_name("vector"), "double3")
        self.assertEqual(attr_types.upgrade_legacy_name("angle"),
                         "doubleAngle")
        self.assertEqual(attr_types.upgrade_legacy_name("python"), "pickle")
        self.assertEqual(attr_types.upgrade_legacy_name("float"),  "float")
        self.assertEqual(attr_types.upgrade_legacy_name("euler"),  "euler")
        self.assertIsNone(attr_types.upgrade_legacy_name(None))

    def test_plugs_created_are_unchanged(self):
        # The stored vocabulary drives the plug: long is -at long, double3
        # -at double3, doubleAngle -at doubleAngle, pickle a string.
        from mpynode._common import attr_types

        kinds = attr_types.add_attr_kwargs()
        self.assertEqual(kinds["long"],        {"at": "long"})
        self.assertEqual(kinds["double3"],     {"at": "double3"})
        self.assertEqual(kinds["doubleAngle"], {"at": "doubleAngle"})
        self.assertEqual(kinds["euler"],       {"at": "double3"})
        self.assertEqual(kinds["double"],      {"at": "double"})
        self.assertEqual(kinds["float"],       {"at": "float"})
        self.assertEqual(kinds["pickle"],      {"dt": "string"})

    def test_wrapper_lists_come_from_the_table(self):
        from mpynode._common import attr_types
        from mpynode.wrappers import _mpy_node

        self.assertEqual(tuple(_mpy_node._ADD_ATTR_KIND), attr_types.ALL_NAMES)
        self.assertEqual(_mpy_node._ADD_ATTR_KIND,
                         attr_types.add_attr_kwargs())
        self.assertEqual(_mpy_node.VALID_INPUT_TYPES,
                         list(attr_types.ALL_NAMES))
        self.assertEqual(_mpy_node.VALID_OUTPUT_TYPES,
                         list(attr_types.ALL_NAMES))

    def test_assistant_tool_enum_comes_from_the_table(self):
        from mpynode._common import attr_types
        from mpynode.ui.llm import tools

        self.assertEqual(tools._ATTR_TYPES, list(attr_types.ASSISTANT_NAMES))
        self.assertEqual(tools._ATTR_TYPES[0], "double")
        self.assertEqual(tools._INPUT_ITEM["properties"]["type"]["enum"],
                         tools._ATTR_TYPES)
        self.assertEqual(tools._OUTPUT_ITEM["properties"]["type"]["enum"],
                         tools._ATTR_TYPES)

    def test_both_prompts_list_the_assistant_types(self):
        from mpynode._common import attr_types
        from mpynode.ui.llm import system_prompt

        block = system_prompt._attr_types_block()
        flat  = [t.strip(" .") for t in block.replace("\n", " ").split(",")]
        self.assertEqual(tuple(flat), attr_types.ASSISTANT_NAMES)
        for prompt in (system_prompt.build_system_prompt(),
                       system_prompt.build_payload_system_prompt()):
            self.assertIn("ATTRIBUTE TYPES", prompt)
            self.assertIn(block, prompt)
            self.assertNotIn("{ATTR_TYPES}", prompt)
            self.assertIn("double3 -> numpy (3,)", prompt)
            self.assertIn("long -> int", prompt)
            self.assertIn("doubleAngle -> float (rad)", prompt)
            self.assertNotIn("vector -> numpy", prompt)
            self.assertNotIn("angle -> float (rad)    ", prompt)

    @unittest.skipUnless(_qt_available(), "Qt unavailable")
    def test_dialog_lists_come_from_the_table(self):
        from mpynode._common import attr_types
        from mpynode.ui.dialogs import add_attr

        self.assertEqual(add_attr.ALL_ATTR_TYPES, attr_types.DIALOG_NAMES)
        self.assertEqual(add_attr._ATTR_TYPE_GROUPS, attr_types.DIALOG_GROUPS)

    def test_unknown_type_message(self):
        from mpynode._common import attr_types

        self.assertEqual(attr_types.unknown_type_message("python"), _PYTHON)
        msg = attr_types.unknown_type_message("banana")
        self.assertIn("'banana' not supported; valid:", msg)
        for name in attr_types.ALL_NAMES:
            self.assertIn(repr(name), msg)
        # ... and the aliases, each with the name it stands for.
        self.assertIn("aliases:", msg)
        for alias, stored in _ALIASES.items():
            self.assertIn("%r -> %r" % (alias, stored), msg)


class _MayaBase(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="typeNames")
        self.name = self.node.get_name()

    def _plug_shape(self, attr):
        """The Maya kind of ``attr`` and of its children, by child suffix."""
        n    = self.name
        kids = mc.attributeQuery(attr, node=n, listChildren=True) or []
        return {
            "at": mc.attributeQuery(attr, node=n, attributeType=True),
            "kids": [(k[len(attr):],
                      mc.attributeQuery(k, node=n, attributeType=True))
                     for k in kids],
            "color":    bool(mc.attributeQuery(attr, node=n, usedAsColor=True)),
            "keyable":  bool(mc.attributeQuery(attr, node=n, keyable=True)),
            "writable": bool(mc.attributeQuery(attr, node=n, writable=True)),
        }


class TestAliasesAreAccepted(_MayaBase):

    def test_every_alias_makes_the_stored_plug_input(self):
        for alias, stored in _ALIASES.items():
            with self.subTest(alias=alias):
                self.node.add_input_attr("a_" + alias, alias)
                self.node.add_input_attr("s_" + alias, stored)
                self.assertEqual(self._plug_shape("a_" + alias),
                                 self._plug_shape("s_" + alias))
                amap = self.node.get_input_attr_map()
                self.assertEqual(amap["a_" + alias]["attr_type"], stored)

    def test_every_alias_makes_the_stored_plug_output(self):
        for alias, stored in _ALIASES.items():
            with self.subTest(alias=alias):
                self.node.add_output_attr("a_" + alias, alias)
                self.node.add_output_attr("s_" + alias, stored)
                self.assertEqual(self._plug_shape("a_" + alias),
                                 self._plug_shape("s_" + alias))
                amap = self.node.get_output_attr_map()
                self.assertEqual(amap["a_" + alias]["attr_type"], stored)

    def test_the_plug_map_stores_the_stored_name(self):
        self.node.add_input_attr("n", "int", default_value=3)
        self.node.add_input_attr("v", "vector")
        self.node.add_input_attr("a", "angle")
        self.node.add_output_attr("o", "float64")
        raw_in  = json.loads(mc.getAttr(self.name + "._inputAttrs"))
        raw_out = json.loads(mc.getAttr(self.name + "._outputAttrs"))
        self.assertEqual({k: m["attr_type"] for k, m in raw_in.items()},
                         {"n": "long", "v": "double3", "a": "doubleAngle"})
        self.assertEqual(raw_out["o"]["attr_type"], "double")
        self.assertEqual(mc.getAttr(self.name + ".n"), 3)

    def test_python_raises_with_the_pickle_hint(self):
        with self.assertRaises(ValueError) as cm:
            self.node.add_input_attr("p", "python")
        self.assertEqual(str(cm.exception), _PYTHON)
        self.assertFalse(mc.objExists(self.name + ".p"))
        with self.assertRaises(ValueError) as cm:
            self.node.add_output_attr("q", "python")
        self.assertEqual(str(cm.exception), _PYTHON)
        self.assertFalse(mc.objExists(self.name + ".q"))

    def test_unknown_name_lists_stored_names_and_aliases(self):
        with self.assertRaises(ValueError) as cm:
            self.node.add_input_attr("z", "banana")
        msg = str(cm.exception)
        self.assertIn("not supported; valid:", msg)
        self.assertIn("'double3'",             msg)
        self.assertIn("'vector' -> 'double3'", msg)
        self.assertFalse(mc.objExists(self.name + ".z"))

    def test_read_plug_value_accepts_an_alias(self):
        import maya.api.OpenMaya as om

        from mpynode._api2.helpers import read_plug_value

        self.node.add_input_attr("v", "double3")
        mc.setAttr(self.name + ".v", 1.0, 2.0, 3.0, type="double3")
        sel = om.MSelectionList()
        sel.add(self.name + ".v")
        plug = sel.getPlug(0)
        self.assertEqual(list(read_plug_value(plug, "vector")),
                         [1.0, 2.0, 3.0])
        self.assertEqual(list(read_plug_value(plug, "double3")),
                         [1.0, 2.0, 3.0])
        with self.assertRaises(ValueError) as cm:
            read_plug_value(plug, "python")
        self.assertEqual(str(cm.exception), _PYTHON)
        with self.assertRaises(ValueError):
            read_plug_value(plug, "banana")

    def test_datablock_read_accepts_an_alias(self):
        # The thread-safe twin of read_plug_value: an alias reads, python and
        # unknown names raise instead of silently vanishing from ``self``.
        import maya.api.OpenMaya as om

        from mpynode._api2.helpers import read_user_inputs_dict_from_datablock

        self.node.add_input_attr("v", "double3")
        sel = om.MSelectionList()
        sel.add(self.name)
        node_obj = sel.getDependNode(0)
        # No data block here: the alias passes the type check and the read
        # itself is skipped.
        self.assertEqual(read_user_inputs_dict_from_datablock(
            None, node_obj, {"v": {"attr_type": "vector"}}), {})
        with self.assertRaises(ValueError) as cm:
            read_user_inputs_dict_from_datablock(
                None, node_obj, {"v": {"attr_type": "python"}})
        self.assertEqual(str(cm.exception), _PYTHON)

    def test_plug_helpers_translate_an_alias_map(self):
        # Every map in production comes through decode_attr_map, which
        # already translates. The plug helpers translate an alias themselves
        # too, so a map passed in directly reads (array containers included)
        # and writes like the stored one.
        from unittest import mock

        import maya.api.OpenMaya as om
        import numpy as np

        from mpynode._api2.helpers import read_user_inputs_dict
        from mpynode._common.io import serialization

        node = self.node
        n    = self.name
        node.add_input_attr("cnt", "long", is_array=True)
        node.add_input_attr("vec", "double3", is_array=True)
        node.add_output_attr("tot", "double3")
        node.add_output_attr("dbl", "double3", is_array=True)
        node.set_compute_expression(
            "self.tot = self.vec.sum(axis=0) + float(self.cnt.sum())\n"
            "self.dbl = [row * 2 for row in self.vec]\n")
        mc.setAttr(n + ".cnt[0]", 1)
        mc.setAttr(n + ".cnt[1]", 2)
        mc.setAttr(n + ".vec[0]", 1.0, 2.0, 3.0, type="double3")
        mc.setAttr(n + ".vec[1]", 4.0, 5.0, 6.0, type="double3")
        self.assertEqual(mc.getAttr(n + ".tot")[0], (8.0, 10.0, 12.0))

        sel = om.MSelectionList()
        sel.add(n)
        node_obj = sel.getDependNode(0)
        stored   = read_user_inputs_dict(node_obj, node.get_input_attr_map())
        alias = read_user_inputs_dict(node_obj, {
            "cnt": {"attr_type": "int", "is_array": True},
            "vec": {"attr_type": "vector", "is_array": True}})
        for name in ("cnt", "vec"):
            self.assertIsInstance(alias[name], np.ndarray)
            self.assertEqual(alias[name].dtype, stored[name].dtype)
            self.assertEqual(alias[name].tolist(), stored[name].tolist())
        self.assertEqual(alias["vec"].shape, (2, 3))

        # The node's own maps carry the aliases and decode passes them
        # through untranslated: the compute still reads and writes them.
        old = {"long": "int", "double3": "vector"}
        for plug in ("_inputAttrs", "_outputAttrs"):
            amap = json.loads(mc.getAttr(n + "." + plug))
            for meta in amap.values():
                meta["attr_type"] = old[meta["attr_type"]]
            mc.setAttr(n + "." + plug, json.dumps(amap), type="string")
        with mock.patch.object(serialization, "_ATTR_ALIASES", {}):
            self.assertEqual(
                node.get_input_attr_map()["vec"]["attr_type"], "vector")
            mc.setAttr(n + ".cnt[0]", 10)
            self.assertEqual(mc.getAttr(n + ".tot")[0], (17.0, 19.0, 21.0))
            self.assertEqual(
                [tuple(mc.getAttr("%s.dbl[%d]" % (n, i))[0])
                 for i in range(2)],
                [(2.0, 4.0, 6.0), (8.0, 10.0, 12.0)])

    def test_pickle_round_trips_an_object(self):
        # pickle is the old python type under its new name: an object written
        # by one node's output arrives whole at another node's input.
        from mpynode.wrappers._mpy_node import MPyNode

        producer = MPyNode.create(name="pickleOut")
        producer.add_output_attr("out", "pickle")
        producer.set_compute_expression(
            "self.out = {'msg': 'hi', 'items': [1, 2.5, (3, 'x')]}")
        consumer = MPyNode.create(name="pickleIn")
        consumer.add_input_attr("data", "pickle")
        consumer.add_output_attr("got", "string")
        consumer.set_compute_expression("self.got = repr(self.data)")
        mc.connectAttr(producer.get_name() + ".out",
                       consumer.get_name() + ".data")
        self.assertEqual(mc.getAttr(consumer.get_name() + ".got"),
                         repr({'msg': 'hi', 'items': [1, 2.5, (3, 'x')]}))
        self.assertEqual(
            consumer.get_input_attr_map()["data"]["attr_type"], "pickle")


def _payload(input_attrs, output_attrs=None):
    return {
        "native_type":  "mPyNode",
        "input_attrs":  input_attrs,
        "output_attrs": output_attrs or {},
    }


class TestMpnRestore(_MayaBase):

    def _tmp(self):
        tmp = tempfile.mkdtemp(prefix="mpynode-attr-names-")
        self.addCleanup(shutil.rmtree, tmp, True)
        return tmp

    def test_artist_names_load_as_stored_names(self):
        from mpynode._common import attr_types
        from mpynode._common.io import mpn_io

        ins = {"i_" + t.artist: {"attr_type": t.artist, "order": k}
               for k, t in enumerate(attr_types.ATTR_TYPES)}
        outs = {"o_" + a: {"attr_type": a, "order": k}
                for k, a in enumerate(_ALIASES)}
        path = os.path.join(self._tmp(), "artist.mpn")
        mpn_io.save_mpn(_payload(ins, outs), path)
        payload = mpn_io.load_mpn(path, trusted=True)
        node    = mpn_io.deserialize_node(payload, name="artistNames")
        n       = node.get_name()

        want_in = {"i_" + t.artist: t.name for t in attr_types.ATTR_TYPES}
        got_in = {k: m["attr_type"]
                  for k, m in node.get_input_attr_map().items()}
        self.assertEqual(got_in, want_in)
        want_out = {"o_" + a: s for a, s in _ALIASES.items()}
        got_out = {k: m["attr_type"]
                   for k, m in node.get_output_attr_map().items()}
        self.assertEqual(got_out, want_out)
        # The plug is the stored name's plug.
        self.assertEqual(mc.attributeQuery("i_int", node=n, at=True), "long")
        self.assertEqual(mc.attributeQuery("o_double4", node=n, at=True),
                         "double4")
        # The payload itself was translated in place, before the create.
        self.assertEqual(payload["input_attrs"]["i_vector"]["attr_type"],
                         "double3")
        # Saved again, the file carries the stored names.
        again = mpn_io.serialize_node(node)
        self.assertEqual({k: m["attr_type"]
                          for k, m in again["input_attrs"].items()}, want_in)

    def test_python_raises_before_creating_anything(self):
        from mpynode._common.io import mpn_io

        def payload():
            return _payload({
                "first":  {"attr_type": "double", "order": 0},
                "second": {"attr_type": "python", "order": 1},
            })

        before = set(mc.ls(type="mPyNode"))
        with self.assertRaises(ValueError) as cm:
            mpn_io.deserialize_node(payload())
        self.assertEqual(str(cm.exception), _PYTHON)
        self.assertEqual(set(mc.ls(type="mPyNode")), before)

        with self.assertRaises(ValueError) as cm:
            mpn_io.apply_payload_to_node(self.node, payload())
        self.assertEqual(str(cm.exception), _PYTHON)
        self.assertFalse(mc.objExists(self.name + ".first"))

        # The same from a file on disk.
        path = os.path.join(self._tmp(), "python.mpn")
        mpn_io.save_mpn(payload(), path)
        with self.assertRaises(ValueError) as cm:
            mpn_io.deserialize_node(mpn_io.load_mpn(path, trusted=True))
        self.assertEqual(str(cm.exception), _PYTHON)
        self.assertEqual(set(mc.ls(type="mPyNode")), before)


class TestOldSceneMaps(_MayaBase):
    """A scene saved before 2026-10-01 stored int / vector / angle in its
    ``_inputAttrs`` / ``_outputAttrs`` JSON."""

    def test_decode_attr_map_translates_aliases(self):
        from mpynode._common.io.serialization import decode_attr_map

        amap = decode_attr_map(json.dumps({
            "n": {"attr_type": "int"},
            "v": {"attr_type": "vector", "is_array": True},
            "a": {"attr_type": "angle"},
            "p": {"attr_type": "python"},
            "d": {"attr_type": "double"},
            "x": {"attr_type": "banana"},
        }))
        self.assertEqual({k: m["attr_type"] for k, m in amap.items()}, {
            "n": "long", "v": "double3", "a": "doubleAngle",
            # The retired stored name: translated in scene data only.
            "p": "pickle",
            # Stored names and unknowns: returned as stored, for the reader
            # to judge.
            "d": "double", "x": "banana"})
        self.assertTrue(amap["v"]["is_array"])

    def test_scene_with_old_names_loads_and_reads(self):
        import maya.api.OpenMaya as om

        from mpynode._api2.helpers import read_user_inputs_dict
        from mpynode._common.io import trust
        from mpynode.wrappers._mpy_node import MPyNode

        node = self.node
        node.add_input_attr("n", "long")
        node.add_input_attr("v", "double3")
        node.add_input_attr("a", "doubleAngle")
        node.add_input_attr("na", "long", is_array=True)
        node.add_output_attr("on", "long")
        node.add_output_attr("ov", "double3")
        node.add_output_attr("oa", "doubleAngle")
        node.set_compute_expression(
            "self.on = self.n * 2 + int(sum(self.na))\n"
            "self.ov = self.v * 2\n"
            "self.oa = self.a * 2\n")
        n = self.name
        mc.setAttr(n + ".n", 3)
        mc.setAttr(n + ".v", 1.0, 2.0, 3.0, type="double3")
        mc.setAttr(n + ".a",     0.25)  # UI units: degrees
        mc.setAttr(n + ".na[0]", 4)
        mc.setAttr(n + ".na[1]", 5)
        want = {o: mc.getAttr(n + "." + o) for o in ("on", "ov", "oa")}
        self.assertEqual(want["on"], 15)

        # Write the old names into the scene's maps, as an older build did.
        old = {"long": "int", "double3": "vector", "doubleAngle": "angle"}
        for plug in ("_inputAttrs", "_outputAttrs"):
            amap = json.loads(mc.getAttr(n + "." + plug))
            for meta in amap.values():
                meta["attr_type"] = old[meta["attr_type"]]
            mc.setAttr(n + "." + plug, json.dumps(amap), type="string")
        self.assertIn('"vector"', mc.getAttr(n + "._inputAttrs"))
        self.assertIn('"angle"', mc.getAttr(n + "._outputAttrs"))

        tmp  = tempfile.mkdtemp(prefix="mpynode-old-maps-")
        path = os.path.join(tmp, "old_maps.ma")
        self.addCleanup(shutil.rmtree, tmp, True)
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(new=True, force=True)

        prior_env                          = os.environ.get("MPYNODE_TRUST_PICKLE")
        os.environ["MPYNODE_TRUST_PICKLE"] = "1"

        def restore():
            if prior_env is None:
                os.environ.pop("MPYNODE_TRUST_PICKLE", None)
            else:
                os.environ["MPYNODE_TRUST_PICKLE"] = prior_env
            mc.file(new=True, force=True)
            trust.reset_for_new_scene()

        self.addCleanup(restore)
        mc.file(path, open=True, force=True)

        reopened = MPyNode(n)
        self.assertEqual(
            {k: m["attr_type"]
             for k, m in reopened.get_input_attr_map().items()},
            {"n": "long", "v": "double3", "a": "doubleAngle", "na": "long"})
        self.assertEqual(
            {k: m["attr_type"]
             for k, m in reopened.get_output_attr_map().items()},
            {"on": "long", "ov": "double3", "oa": "doubleAngle"})

        sel = om.MSelectionList()
        sel.add(n)
        vals = read_user_inputs_dict(sel.getDependNode(0),
                                     reopened.get_input_attr_map())
        self.assertEqual(vals["n"], 3)
        self.assertEqual(list(vals["v"]), [1.0, 2.0, 3.0])
        self.assertAlmostEqual(vals["a"], math.radians(0.25))
        self.assertEqual(list(vals["na"]), [4, 5])

        # The compute reads the old maps too.
        mc.setAttr(n + ".n", 3)
        got = {o: mc.getAttr(n + "." + o) for o in ("on", "ov", "oa")}
        self.assertEqual(got, want)

    def test_scene_with_python_attr_reads_as_pickle(self):
        # ``python`` was the stored name until the pickle rename; a scene
        # saved before it keeps computing, while new code is rejected.
        from mpynode._common.io import trust
        from mpynode.wrappers._mpy_node import MPyNode

        node = self.node
        node.add_input_attr("k", "long")
        node.add_output_attr("obj", "pickle")
        node.set_compute_expression(
            "self.obj = {'k': self.k, 'twice': [self.k] * 2}\n")
        n = self.name
        mc.setAttr(n + ".k", 7)
        want = mc.getAttr(n + ".obj")
        self.assertTrue(want)

        amap                     = json.loads(mc.getAttr(n + "._outputAttrs"))
        amap["obj"]["attr_type"] = "python"
        mc.setAttr(n + "._outputAttrs", json.dumps(amap), type="string")
        self.assertIn('"python"', mc.getAttr(n + "._outputAttrs"))

        tmp  = tempfile.mkdtemp(prefix="mpynode-old-python-")
        path = os.path.join(tmp, "old_python.ma")
        self.addCleanup(shutil.rmtree, tmp, True)
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(new=True, force=True)

        prior_env                          = os.environ.get("MPYNODE_TRUST_PICKLE")
        os.environ["MPYNODE_TRUST_PICKLE"] = "1"

        def restore():
            if prior_env is None:
                os.environ.pop("MPYNODE_TRUST_PICKLE", None)
            else:
                os.environ["MPYNODE_TRUST_PICKLE"] = prior_env
            mc.file(new=True, force=True)
            trust.reset_for_new_scene()

        self.addCleanup(restore)
        mc.file(path, open=True, force=True)

        reopened = MPyNode(n)
        self.assertEqual(
            reopened.get_output_attr_map()["obj"]["attr_type"], "pickle")
        mc.setAttr(n + ".k", 7)
        self.assertEqual(mc.getAttr(n + ".obj"), want)
        with self.assertRaisesRegex(ValueError, "use 'pickle'"):
            reopened.add_input_attr("p", "python")


class TestPickleTrustScan(_MayaBase):
    """The open-time trust scan flags a pickle input holding a literal from
    the file, and not one driven by a connection."""

    def test_pickle_literal_needs_trust(self):
        import base64
        import pickle

        from mpynode._common.lifecycle import trust_prompt

        n = self.name
        self.node.add_input_attr("blob", "pickle")
        # Nothing else on the node asks for trust.
        for attr in ("_computeSource", "_initSource"):
            if mc.attributeQuery(attr, node=n, exists=True):
                mc.setAttr("%s.%s" % (n, attr), "", type="string")
        self.assertFalse(trust_prompt._node_has_pickle_python_literal(mc, n))
        self.assertFalse(trust_prompt._scene_has_pickle_blobs(mc))

        literal = base64.b64encode(pickle.dumps({"a": 1})).decode("ascii")
        mc.setAttr(n + ".blob", literal, type="string")
        self.assertTrue(trust_prompt._node_has_pickle_python_literal(mc, n))
        self.assertTrue(trust_prompt._scene_has_pickle_blobs(mc))

        # Driven by a connection, the value is not a file literal.
        src = mc.createNode("network")
        mc.addAttr(src, longName="text", dataType="string")
        mc.connectAttr(src + ".text", n + ".blob")
        self.assertFalse(trust_prompt._node_has_pickle_python_literal(mc, n))
        self.assertFalse(trust_prompt._scene_has_pickle_blobs(mc))


class TestPyExport(unittest.TestCase):

    def test_attr_call_writes_the_stored_name(self):
        from mpynode._common.io import py_export

        for alias, stored in _ALIASES.items():
            self.assertEqual(
                py_export._attr_call("add_input_attr", "a",
                                     {"attr_type": alias}),
                py_export._attr_call("add_input_attr", "a",
                                     {"attr_type": stored}))
        self.assertIn("'double3'", py_export._attr_call(
            "add_output_attr", "v", {"attr_type": "vector"}))
        self.assertIn("'pickle'", py_export._attr_call(
            "add_input_attr", "p", {"attr_type": "pickle"}))


class TestCompilePath(unittest.TestCase):
    """A compile spec carries stored names whatever the .mpn said."""

    def _payload(self, ins, outs):
        return {
            "native_type":  "mPyNode",
            "node_name":    "typeNames",
            "expression":   "self.out = self.x",
            "input_attrs":  ins,
            "output_attrs": outs,
        }

    def test_mpn_with_aliases_compiles_like_stored_names(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.spec.mpn_spec_adapter import spec_from_mpn_payload

        stored = {
            "x":  {"attr_type": "double", "order": 0},
            "n":  {"attr_type": "long", "order": 1},
            "v":  {"attr_type": "double3", "order": 2},
            "a":  {"attr_type": "doubleAngle", "order": 3},
            "d":  {"attr_type": "doubleLinear", "order": 4},
            "q":  {"attr_type": "quaternion", "order": 5},
            "c":  {"attr_type": "color", "order": 6},
            "uv": {"attr_type": "float2", "order": 7},
            "f":  {"attr_type": "float", "order": 8},
        }
        alias = {
            "x":  {"attr_type": "float64", "order": 0},
            "n":  {"attr_type": "int", "order": 1},
            "v":  {"attr_type": "vector", "order": 2},
            "a":  {"attr_type": "angle", "order": 3},
            "d":  {"attr_type": "distance", "order": 4},
            "q":  {"attr_type": "double4", "order": 5},
            "c":  {"attr_type": "float3", "order": 6},
            "uv": {"attr_type": "uv", "order": 7},
            "f":  {"attr_type": "float32", "order": 8},
        }
        outs_s = {"out": {"attr_type": "double"}}
        outs_a = {"out": {"attr_type": "float64"}}
        s_spec = spec_from_mpn_payload(self._payload(stored, outs_s))
        a_spec = spec_from_mpn_payload(self._payload(alias, outs_a))
        self.assertEqual(a_spec, s_spec)
        self.assertEqual(a_spec["inputs"]["v"]["type"], "double3")
        self.assertEqual(codegen.generate_cpp(a_spec, for_port=True),
                         codegen.generate_cpp(s_spec, for_port=True))

    def test_normalize_attr(self):
        from mpynode.native.spec.spec_extractor import normalize_attr

        for alias, stored in _ALIASES.items():
            self.assertEqual(normalize_attr({"attr_type": alias}),
                             normalize_attr({"attr_type": stored}))
        self.assertEqual(normalize_attr({"attr_type": "python"})["note"],
                         _PYTHON)
        self.assertEqual(normalize_attr({"attr_type": "banana"})["note"],
                         "unknown attr_type 'banana' -- no native mapping")
        self.assertNotIn("note", normalize_attr({"attr_type": "double3"}))
        self.assertFalse(normalize_attr({"attr_type": "pickle"})["portable"])
        self.assertNotIn("note", normalize_attr({"attr_type": "pickle"}))

    def test_python_mpn_is_blocked_with_the_pickle_hint(self):
        # A compile reads an .mpn straight from its file: a python attr is a
        # portability blocker carrying the rename hint, as pickle blocks.
        from mpynode.native.spec.mpn_spec_adapter import spec_from_mpn_payload

        outs = {"out": {"attr_type": "double"}}
        for side in ("input_attrs", "output_attrs"):
            ins                   = {"x": {"attr_type": "double", "order": 0}}
            payload               = self._payload(ins, dict(outs))
            payload[side]["blob"] = {"attr_type": "python", "order": 1}
            port                  = spec_from_mpn_payload(payload)["portability"]
            label                 = "input" if side == "input_attrs" else "output"
            with self.subTest(side=side):
                self.assertFalse(port["portable"])
                self.assertIn("%s 'blob': %s" % (label, _PYTHON),
                              port["blockers"])

            payload               = self._payload(ins, dict(outs))
            payload[side]["blob"] = {"attr_type": "pickle", "order": 1}
            port                  = spec_from_mpn_payload(payload)["portability"]
            with self.subTest(side=side, attr_type="pickle"):
                self.assertFalse(port["portable"])
                self.assertIn("%s 'blob' is type 'pickle' (no native type)"
                              % label, port["blockers"])

    def test_check_translates_an_alias(self):
        from mpynode.native.compiler.spec_model import _check

        def spec(t):
            return {
                "schema_version": 1,
                "source_node":    "loc1",
                "mpy_type":       "mPyLocator",
                "suggested": {
                    "node_type_name": "loc1",
                    "class_name":     "Loc1",
                    "type_id":        "0x00070123",
                    "mpx_base":       "MPxLocatorNode",
                    "note":           "",
                    "heaviness":      "hard",
                },
                "inputs":      {"x": {"type": t, "is_array": False}},
                "outputs":     {},
                "variables":   {},
                "compute":     "self.polygons = None\n",
                "init":        "",
                "affects":     "all",
                "portability": {"portable": True, "blockers": []},
            }

        for alias, stored in _ALIASES.items():
            s = spec(alias)
            _check(s)  # must NOT raise
            self.assertEqual(s["inputs"]["x"]["type"], stored)

    def test_check_names_the_pickle_replacement(self):
        from mpynode.native.compiler.errors import UnsupportedSpec
        from mpynode.native.compiler.spec_model import _check

        spec = {"suggested": {"mpx_base": "MPxNode"},
                "inputs": {"x": {"type": "python", "is_array": False}},
                "outputs": {}}
        with self.assertRaises(UnsupportedSpec) as cm:
            _check(spec)
        self.assertEqual(str(cm.exception), "attr 'x': " + _PYTHON)

        spec["inputs"]["x"]["type"] = "pickle"
        with self.assertRaises(UnsupportedSpec) as cm:
            _check(spec)
        self.assertIn("type 'pickle' is the only kind of attr excluded",
                      str(cm.exception))


def _git_work_tree(root) -> bool:
    """True when ``root`` is inside a git work tree. The studio Perforce copy
    is not, so the migration tool (which lists files with ``git ls-files``)
    cannot scan it."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", root, "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True)
    except OSError:
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def _load_migration_tool():
    path = os.path.join(ROOT, "tools", "migrate_attr_names.py")
    spec = importlib.util.spec_from_file_location("_migrate_attr_names", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MPN = """{
  "data": {
    "input_attrs": {
      "angle": {
        "attr_type": "angle",
        "is_array": false
      },
      "n": {
        "attr_type": "int",
        "is_array": false
      }
    },
    "output_attrs": {
      "p": {
        "attr_type": "vector",
        "is_array": true
      }
    },
    "stored_vars": {
      "note": "\\"attr_type\\": \\"int\\" stays text"
    }
  },
  "version": 2
}"""

_MPN_NEW_NAMES = """{
  "data": {
    "input_attrs": {
      "blob": {
        "attr_type": "python",
        "is_array": false
      },
      "d": {
        "attr_type": "float64",
        "is_array": false
      },
      "f": {
        "attr_type": "float32",
        "is_array": false
      },
      "q": {
        "attr_type": "double4",
        "is_array": false
      }
    },
    "output_attrs": {
      "c": {
        "attr_type": "float3",
        "is_array": false
      },
      "t": {
        "attr_type": "uv",
        "is_array": false
      }
    }
  },
  "version": 2
}"""

_MANIFEST = """{
  "nodes": [
    {
      "spec": {
        "inputs": {
          "n": {
            "cpp": {
              "cat": "scalar",
              "cpp": "int"
            },
            "type": "int"
          },
          "v": {
            "cpp": {
              "cat": "vector"
            },
            "type": "vector"
          }
        },
        "outputs": {},
        "variables": {
          "k": {
            "kind": "int"
          }
        }
      }
    }
  ]
}
"""

_MA = (
    'createNode mPyNode -n "n1";\n'
    '\tsetAttr "._inputAttrs" -type "string" "{\\"a\\":{\\"attr_type\\":'
    '\\"int\\",\\"is_array\\":false},\\"b\\":{\\"attr_type\\":\\"vector\\",'
    '\\"is_array\\":true}}";\n'
    '\tsetAttr "._outputAttrs" -type "string" "{\\"o\\":{\\"attr_type\\":'
    '\\"angle\\",\\"is_array\\":false}}";\n'
    '\tsetAttr ".label" -type "string" "\\"attr_type\\":\\"int\\"";\n'
)

_VERIFY = (
    "import json\n"
    "INPUTS = {\"angle\": \"angle\", \"n\": \"int\"}\n"
    "SPEC = json.loads('{\"inputs\": {\"v\": {\"cpp\": {\"cat\": \"vector\", "
    "\"cpp\": \"int\"}, \"type\": \"vector\"}}, \"outputs\": {}}')\n"
    "\n"
    "def _sample(t):\n"
    "    if t == \"int\":\n"
    "        return 1\n"
    "    if t in (\"vector\", \"euler\"):\n"
    "        return [0, 0, 0]\n"
    "    return 0.0\n"
)


class TestMigrationTool(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.M = _load_migration_tool()

    def _twice(self, fn, text):
        c1, c2 = collections.Counter(), collections.Counter()
        once  = fn("x", text, c1)
        again = fn("x", once, c2)
        self.assertEqual(again, once, "a second pass changed the text")
        self.assertEqual(sum(c2.values()), 0)
        return once, c1

    def test_the_map_is_the_tables(self):
        from mpynode._common import attr_types

        want = dict(attr_types.ALIASES)
        want.update(attr_types.RETIRED)
        self.assertEqual(self.M.RENAME, want)

    def test_mpn(self):
        out, counts = self._twice(self.M.migrate_mpn, _MPN)
        self.assertEqual(counts, {"angle": 1, "int": 1, "vector": 1})
        self.assertIn('"attr_type": "doubleAngle"', out)
        self.assertIn('"attr_type": "long"', out)
        self.assertIn('"attr_type": "double3"', out)
        self.assertIn('"angle": {', out)  # attr NAME kept
        self.assertIn('\\"attr_type\\": \\"int\\" stays text', out)

    def test_mpn_artist_maya_and_retired_names(self):
        out, counts = self._twice(self.M.migrate_mpn, _MPN_NEW_NAMES)
        self.assertEqual(counts, {"python": 1, "float64": 1, "float32": 1,
                                  "double4": 1, "float3": 1, "uv": 1})
        for stored in ("pickle", "double", "float", "quaternion", "color",
                       "float2"):
            self.assertIn('"attr_type": "%s"' % stored, out)

    def test_manifest_keeps_cpp_cat_and_kinds(self):
        out, counts = self._twice(self.M.migrate_manifest, _MANIFEST)
        self.assertEqual(counts, {"int": 1, "vector": 1})
        self.assertIn('"cpp": "int"',      out)
        self.assertIn('"cat": "vector"',   out)
        self.assertIn('"kind": "int"',     out)
        self.assertIn('"type": "long"',    out)
        self.assertIn('"type": "double3"', out)

    def test_ma_payload_plugs_only(self):
        out, counts = self._twice(self.M.migrate_ma, _MA)
        self.assertEqual(counts, {"int": 1, "vector": 1, "angle": 1})
        self.assertIn('\\"attr_type\\":\\"long\\"',        out)
        self.assertIn('\\"attr_type\\":\\"double3\\"',     out)
        self.assertIn('\\"attr_type\\":\\"doubleAngle\\"', out)
        # a string plug that is not an attr map is left alone
        self.assertIn('".label" -type "string" "\\"attr_type\\":\\"int\\""',
                      out)

    def test_verify_script(self):
        out, counts = self._twice(self.M.migrate_verify_script, _VERIFY)
        self.assertEqual(counts, {"int": 2, "vector": 2, "angle": 1})
        self.assertIn('INPUTS = {"angle": "doubleAngle", "n": "long"}', out)
        self.assertIn('if t == "long":', out)
        self.assertIn('if t in ("double3", "euler"):', out)
        self.assertIn('"type": "double3"', out)
        self.assertIn('"cat": "vector"', out)
        self.assertIn('"cpp": "int"', out)

    def test_verify_script_keeps_non_type_literals(self):
        # Only the old stored names are code literals in a generated script.
        # A bare alias that was never stored means something else there, and
        # a keyword argument's value is never a type.
        src = (
            "import maya.standalone\n"
            "maya.standalone.initialize(name=\"python\")\n"
            "import maya.cmds as cmds\n"
            "def _set(p, v):\n"
            "    cmds.setAttr(p, *v, type=\"double4\")\n"
            "    cmds.addAttr('n', ln='c', at=\"float3\", usedAsColor=True)\n"
            "    cmds.polyUVSet('m', currentUVSet=True, uvSet=\"uv\")\n"
            "    k = \"distance\"\n"
            "    f = (\"float64\", \"float32\")\n"
        )
        out, counts = self._twice(self.M.migrate_verify_script, src)
        self.assertEqual(out, src)
        self.assertEqual(sum(counts.values()), 0)

        # python is an old stored name: a code literal is still renamed.
        out, counts = self._twice(self.M.migrate_verify_script,
                                  'def skip(t):\n'
                                  '    return t in ("python", "message")\n')
        self.assertEqual(counts, {"python": 1})
        self.assertIn('t in ("pickle", "message")', out)

    @unittest.skipUnless(_git_work_tree(ROOT), "not a git work tree")
    def test_repo_is_already_migrated(self):
        # Idempotent on the real data: every stored name is already stored.
        totals = self.M.run(apply=False, stream=io.StringIO())
        self.assertEqual(sum(totals.values()), 0, dict(totals))


if __name__ == "__main__":
    unittest.main()
