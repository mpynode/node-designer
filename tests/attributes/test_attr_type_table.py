"""The one attr type table (``_common/attr_types.py``) and the retired names.

* every list of types (wrapper, dialog, assistant tool, assistant prompt)
  comes from the table and agrees with it;
* ``int`` / ``vector`` / ``angle`` (and ``double4`` / ``float3``) are rejected
  everywhere with a hint naming the replacement -- no aliases;
* ``tools/migrate_attr_names.py`` is idempotent and leaves the repo clean.
"""

from __future__ import annotations

import collections
import importlib.util
import io
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import maya.cmds as mc

from tests._paths import ROOT
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


_OLD_TO_NEW = {
    "int":     "long",
    "vector":  "double3",
    "angle":   "doubleAngle",
    "double4": "quaternion",
    "float3":  "color",
}


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

    def test_float2_accepted_but_not_offered(self):
        from mpynode._common import attr_types

        self.assertIn("float2", attr_types.ALL_NAMES)
        self.assertNotIn("float2", attr_types.DIALOG_NAMES)
        self.assertNotIn("float2", attr_types.ASSISTANT_NAMES)

    def test_assistant_list_is_the_dialog_list(self):
        from mpynode._common import attr_types

        self.assertEqual(attr_types.ASSISTANT_NAMES, attr_types.DIALOG_NAMES)

    def test_no_retired_name_is_accepted(self):
        from mpynode._common import attr_types

        self.assertEqual(attr_types.RETIRED, _OLD_TO_NEW)
        for old, new in attr_types.RETIRED.items():
            self.assertNotIn(old, attr_types.ALL_NAMES)
            self.assertIn(new, attr_types.ALL_NAMES)

    def test_plugs_created_are_unchanged(self):
        # Commit 1 renames the stored vocabulary only: long is still -at long,
        # double3 -at double3, doubleAngle -at doubleAngle.
        from mpynode._common import attr_types

        kinds = attr_types.add_attr_kwargs()
        self.assertEqual(kinds["long"],        {"at": "long"})
        self.assertEqual(kinds["double3"],     {"at": "double3"})
        self.assertEqual(kinds["doubleAngle"], {"at": "doubleAngle"})
        self.assertEqual(kinds["euler"],       {"at": "double3"})
        self.assertEqual(kinds["double"],      {"at": "double"})
        self.assertEqual(kinds["float"],       {"at": "float"})

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

        self.assertEqual(attr_types.unknown_type_message("vector"),
                         "attr_type 'vector' was renamed: use 'double3'")
        msg = attr_types.unknown_type_message("banana")
        self.assertIn("'banana' not supported; valid:", msg)
        for name in attr_types.ALL_NAMES:
            self.assertIn(repr(name), msg)


class _MayaBase(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="retiredNames")


class TestRetiredNamesRaise(_MayaBase):

    def test_add_input_attr_names_the_replacement(self):
        for old, new in _OLD_TO_NEW.items():
            with self.assertRaises(ValueError) as cm:
                self.node.add_input_attr("x_" + old, old)
            self.assertEqual(
                str(cm.exception),
                "attr_type %r was renamed: use %r" % (old, new))
            self.assertFalse(mc.objExists(self.node.get_name() + ".x_" + old))

    def test_add_output_attr_names_the_replacement(self):
        for old, new in _OLD_TO_NEW.items():
            with self.assertRaises(ValueError) as cm:
                self.node.add_output_attr("y_" + old, old)
            self.assertEqual(
                str(cm.exception),
                "attr_type %r was renamed: use %r" % (old, new))

    def test_unknown_name_lists_the_valid_ones(self):
        with self.assertRaises(ValueError) as cm:
            self.node.add_input_attr("z", "banana")
        self.assertIn("not supported; valid:", str(cm.exception))
        self.assertIn("'double3'", str(cm.exception))

    def test_read_plug_value_names_the_replacement(self):
        import maya.api.OpenMaya as om

        from mpynode._api2.helpers import read_plug_value

        self.node.add_input_attr("v", "double3")
        sel = om.MSelectionList()
        sel.add(self.node.get_name() + ".v")
        plug = sel.getPlug(0)
        for old, new in _OLD_TO_NEW.items():
            with self.assertRaises(ValueError) as cm:
                read_plug_value(plug, old)
            self.assertEqual(
                str(cm.exception),
                "attr_type %r was renamed: use %r" % (old, new))
        self.assertEqual(list(read_plug_value(plug, "double3")),
                         [0.0, 0.0, 0.0])

    def test_datablock_read_names_the_replacement(self):
        # The thread-safe twin of read_plug_value used to drop a retired name
        # silently (its handle reads return None = skip).
        import maya.api.OpenMaya as om

        from mpynode._api2.helpers import read_user_inputs_dict_from_datablock

        self.node.add_input_attr("v", "double3")
        sel = om.MSelectionList()
        sel.add(self.node.get_name())
        node_obj = sel.getDependNode(0)
        for old, new in _OLD_TO_NEW.items():
            with self.assertRaises(ValueError) as cm:
                read_user_inputs_dict_from_datablock(
                    None, node_obj, {"v": {"attr_type": old}})
            self.assertEqual(
                str(cm.exception),
                "attr_type %r was renamed: use %r" % (old, new))

    def test_mpn_restore_rejects_before_creating_anything(self):
        # A retired name in an .mpn payload raises before the node or any
        # attr exists -- no half-built node.
        from mpynode._common.io.mpn_io import (apply_payload_to_node,
                                               deserialize_node)

        payload = {
            "native_type": "mPyNode",
            "input_attrs": {
                "first":  {"attr_type": "double", "order": 0},
                "second": {"attr_type": "int", "order": 1},
            },
            "output_attrs": {},
        }
        before = set(mc.ls(type="mPyNode"))
        with self.assertRaises(ValueError) as cm:
            deserialize_node(payload)
        self.assertEqual(str(cm.exception),
                         "attr_type 'int' was renamed: use 'long'")
        self.assertEqual(set(mc.ls(type="mPyNode")), before)

        with self.assertRaises(ValueError) as cm:
            apply_payload_to_node(self.node, payload)
        self.assertEqual(str(cm.exception),
                         "attr_type 'int' was renamed: use 'long'")
        self.assertFalse(mc.objExists(self.node.get_name() + ".first"))

    def test_new_names_make_the_same_plugs(self):
        n = self.node.get_name()
        self.node.add_input_attr("l", "long", default_value=3)
        self.node.add_input_attr("d3", "double3")
        self.node.add_input_attr("da", "doubleAngle")
        self.node.add_output_attr("lo", "long")
        self.assertEqual(mc.attributeQuery("l", node=n, attributeType=True),
                         "long")
        self.assertEqual(mc.attributeQuery("d3", node=n, attributeType=True),
                         "double3")
        self.assertEqual(mc.attributeQuery("d3X", node=n, attributeType=True),
                         "double")
        self.assertEqual(mc.attributeQuery("da", node=n, attributeType=True),
                         "doubleAngle")
        self.assertEqual(mc.getAttr(n + ".l"), 3)
        amap = self.node.get_input_attr_map()
        self.assertEqual(amap["l"]["attr_type"],  "long")
        self.assertEqual(amap["d3"]["attr_type"], "double3")
        self.assertEqual(amap["da"]["attr_type"], "doubleAngle")


class TestCompilePathHint(unittest.TestCase):
    """Compiling a stale .mpn (no live node) reports the rename too."""

    def test_check_names_the_replacement(self):
        from mpynode.native.compiler.errors import UnsupportedSpec
        from mpynode.native.compiler.spec_model import _check

        for old, new in _OLD_TO_NEW.items():
            spec = {"suggested": {"mpx_base": "MPxNode"},
                    "inputs": {"x": {"type": old, "is_array": False}},
                    "outputs": {}}
            with self.assertRaises(UnsupportedSpec) as cm:
                _check(spec)
            self.assertEqual(
                str(cm.exception),
                "attr 'x': attr_type %r was renamed: use %r" % (old, new))

    def test_normalize_attr_note(self):
        from mpynode.native.spec.spec_extractor import normalize_attr

        self.assertEqual(normalize_attr({"attr_type": "vector"})["note"],
                         "attr_type 'vector' was renamed: use 'double3'")
        self.assertEqual(normalize_attr({"attr_type": "banana"})["note"],
                         "unknown attr_type 'banana' -- no native mapping")
        self.assertNotIn("note", normalize_attr({"attr_type": "double3"}))


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

    def test_mpn(self):
        out, counts = self._twice(self.M.migrate_mpn, _MPN)
        self.assertEqual(counts, {"angle": 1, "int": 1, "vector": 1})
        self.assertIn('"attr_type": "doubleAngle"', out)
        self.assertIn('"attr_type": "long"', out)
        self.assertIn('"attr_type": "double3"', out)
        self.assertIn('"angle": {', out)  # attr NAME kept
        self.assertIn('\\"attr_type\\": \\"int\\" stays text', out)

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

    @unittest.skipUnless(_git_work_tree(ROOT), "not a git work tree")
    def test_repo_is_already_migrated(self):
        # Idempotent on the real data: after --apply nothing is left to do.
        totals = self.M.run(apply=False, stream=io.StringIO())
        self.assertEqual(sum(totals.values()), 0, dict(totals))


if __name__ == "__main__":
    unittest.main()
