""".mpn serialize/deserialize round-trip + persistent toggles

Consolidated from: test_phase24.py, test_mpn_persistent_toggle.py.
"""

from __future__ import annotations

# ===================== from test_phase24.py =====================
import json
import os
import tempfile
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase24():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Round-trip via the IO module
# ===========================================================================


class TestMpnRoundTrip(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        self._tmpdir = tempfile.mkdtemp(prefix="ndmpn_")

    def tearDown(self):
        for f in os.listdir(self._tmpdir):
            try:
                os.remove(os.path.join(self._tmpdir, f))
            except Exception:
                pass
        try:
            os.rmdir(self._tmpdir)
        except Exception:
            pass

    def _make_full_node(self, name="full"):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=name)
        n.add_input_attr("alpha", "float")
        n.add_input_attr("vec", "vector")
        n.add_input_attr("mode", "enum", enum_names=["off", "on", "standby"])
        n.add_output_attr("out", "vector")
        n.set_input_attr_color("alpha", "#ff0000")
        n.set_input_attr_color("vec", "#00ffff")
        n.set_compute_expression("out = vec * alpha")
        n.set_variable("counter", 7)
        n.set_variable("config", {"a": 1, "b": [1, 2, 3]})
        return n

    def test_serialize_captures_everything(self):
        from mpynode._common.io.mpn_io import serialize_node

        n = self._make_full_node()
        payload = serialize_node(n)

        self.assertEqual(payload["native_type"], "mPyNode")
        self.assertEqual(payload["expression"], "out = vec * alpha")
        self.assertIn("alpha", payload["input_attrs"])
        self.assertIn("vec", payload["input_attrs"])
        self.assertIn("mode", payload["input_attrs"])
        self.assertIn("out", payload["output_attrs"])
        self.assertEqual(payload["input_attrs"]["alpha"].get("ui_color"), "#ff0000")
        self.assertEqual(payload["input_attrs"]["vec"].get("ui_color"), "#00ffff")
        self.assertEqual(
            payload["input_attrs"]["mode"].get("enum_names"),
            ["off", "on", "standby"],
        )
        self.assertEqual(payload["stored_vars"]["counter"], 7)
        self.assertEqual(payload["stored_vars"]["config"], {"a": 1, "b": [1, 2, 3]})

    def _roundtrip(self, compression, fname):
        from mpynode._common.io.mpn_io import load_mpn, save_mpn, serialize_node

        n = self._make_full_node()
        payload = serialize_node(n)
        path = os.path.join(self._tmpdir, fname)
        save_mpn(payload, path, compression=compression)
        return load_mpn(path), payload

    def test_save_load_zlib_preserves_payload(self):
        loaded, payload = self._roundtrip("zlib", "z.mpn")
        self.assertEqual(loaded, payload)

    def test_save_load_lzma_preserves_payload(self):
        loaded, payload = self._roundtrip("lzma", "x.mpn")
        self.assertEqual(loaded, payload)

    def test_save_load_none_preserves_payload(self):
        loaded, payload = self._roundtrip("none", "n.mpn")
        self.assertEqual(loaded, payload)

    def test_save_load_numpy_stored_var(self):
        """The original bug: numpy stored vars used to crash JSON export.
        They must now round-trip through the codec."""
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        from mpynode._common.io.mpn_io import load_mpn, save_mpn, serialize_node

        n = self._make_full_node(name="np_node")
        arr = np.arange(12, dtype=np.float64).reshape(3, 4)
        n.set_variable("mat", arr)
        path = os.path.join(self._tmpdir, "np.mpn")
        save_mpn(serialize_node(n), path)  # default zlib
        loaded = load_mpn(path)
        self.assertIn("mat", loaded["stored_vars"])
        self.assertTrue(np.array_equal(loaded["stored_vars"]["mat"], arr))

    def test_load_mpn_graceful_partial_and_reports_failures(self):
        """A stored var that can't be reconstructed is skipped; the rest
        load, and the failure is reported via return_failures."""
        import base64
        import pickle
        import zlib
        from mpynode._common.io.mpn_io import load_mpn

        inner = {"good": pickle.dumps(7, protocol=5), "bad": b"not-a-pickle"}
        sv = json.dumps({
            "protocol": 7, "format": "keyed", "codec": "zlib",
            "data_b64": base64.b64encode(
                zlib.compress(pickle.dumps(inner, protocol=5), 6)
            ).decode("ascii"),
        })
        env = {"version": 2, "data": {"native_type": "mPyNode", "stored_vars": sv}}
        path = os.path.join(self._tmpdir, "partial.mpn")
        with open(path, "w") as f:
            json.dump(env, f)
        # trusted=True is load_mpn's headless opt-in: without it the per-file
        # pickle gate fails closed (no prompt_fn) and refuses the legacy blob,
        # leaving stored_vars {}.
        data, failures = load_mpn(path, return_failures=True, trusted=True)
        self.assertEqual(data["stored_vars"], {"good": 7})
        self.assertIn("bad", failures)

    def test_envelope_format_v2(self):
        from mpynode._common.io.mpn_io import save_mpn

        path = os.path.join(self._tmpdir, "v2.mpn")
        save_mpn({"native_type": "mPyNode", "stored_vars": {"x": 1}}, path)
        with open(path) as f:
            envelope = json.load(f)
        self.assertEqual(envelope["version"], 2)
        self.assertIn("data", envelope)
        # expression/attrs stay JSON; stored_vars is a single codec blob.
        self.assertIsInstance(envelope["data"]["stored_vars"], str)
        self.assertNotIn("format", envelope)

    def test_load_rejects_bad_version(self):
        from mpynode._common.io.mpn_io import load_mpn

        path = os.path.join(self._tmpdir, "bad_version.mpn")
        with open(path, "w") as f:
            json.dump({"version": 999, "data": {}}, f)
        with self.assertRaises(ValueError):
            load_mpn(path)

    def test_load_rejects_non_dict_data(self):
        from mpynode._common.io.mpn_io import load_mpn

        path = os.path.join(self._tmpdir, "bad_data.mpn")
        with open(path, "w") as f:
            json.dump({"version": 2, "data": "not_a_dict"}, f)
        with self.assertRaises(ValueError):
            load_mpn(path)

    def test_full_round_trip_via_deserialize(self):
        """Save + load + reconstruct → new node has identical surface."""
        from mpynode._common.io.mpn_io import (
            deserialize_node,
            load_mpn,
            save_mpn,
            serialize_node,
        )

        src = self._make_full_node(name="orig")
        path = os.path.join(self._tmpdir, "rt.mpn")
        save_mpn(serialize_node(src), path)

        # Fresh scene proves the import doesn't depend on the source node.
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

        new_node = deserialize_node(load_mpn(path), name="reborn")
        self.assertEqual(new_node.get_name(), "reborn")
        self.assertEqual(new_node.get_compute_expression(), "out = vec * alpha")
        self.assertIn("alpha", new_node.get_input_attr_map())
        self.assertIn("vec", new_node.get_input_attr_map())
        self.assertIn("mode", new_node.get_input_attr_map())
        self.assertIn("out", new_node.get_output_attr_map())
        self.assertEqual(new_node.get_input_attr_color("alpha"), "#ff0000")
        self.assertEqual(new_node.get_input_attr_color("vec"), "#00ffff")
        self.assertEqual(
            mc.attributeQuery("mode", node=new_node.get_name(), listEnum=True),
            ["off:on:standby"],
        )
        self.assertEqual(
            new_node.get_variables(),
            {"counter": 7, "config": {"a": 1, "b": [1, 2, 3]}},
        )


class TestMpnSourceTiers(unittest.TestCase):
    """The .mpn must round-trip the sister source tiers (Init / Viewport / OSL
    / Methods), not just Compute -- otherwise saving a node with an Init or a
    Methods tab silently loses that code. Additive + optional: a node without a
    tier carries no key for it (simple-node payloads stay unchanged)."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        self._tmpdir = tempfile.mkdtemp(prefix="ndmpn_src_")

    def tearDown(self):
        for f in os.listdir(self._tmpdir):
            try:
                os.remove(os.path.join(self._tmpdir, f))
            except Exception:
                pass
        try:
            os.rmdir(self._tmpdir)
        except Exception:
            pass

    def test_serialize_captures_init_source(self):
        from mpynode._common.io.mpn_io import serialize_node
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="initnode")
        n.set_init_expression("import math  # init tier")
        payload = serialize_node(n)
        self.assertEqual(payload.get("init_source"), "import math  # init tier")

    def test_simple_node_has_no_empty_source_keys(self):
        from mpynode._common.io.mpn_io import serialize_node
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="bare")
        payload = serialize_node(n)
        # no init/methods tier set -> no key (payload stays minimal)
        self.assertNotIn("init_source", payload)
        self.assertNotIn("methods_source", payload)

    def test_round_trip_restores_init_source(self):
        from mpynode._common.io.mpn_io import (
            deserialize_node, load_mpn, save_mpn, serialize_node)
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="initorig")
        n.set_init_expression("X = 42  # init")
        path = os.path.join(self._tmpdir, "init.mpn")
        save_mpn(serialize_node(n), path)

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        reborn = deserialize_node(load_mpn(path), name="initreborn")
        self.assertEqual(reborn.get_init_expression(), "X = 42  # init")

    def test_serialize_and_round_trip_methods_source(self):
        from mpynode._common.io.mpn_io import (
            deserialize_node, load_mpn, save_mpn, serialize_node)
        from mpynode.wrappers.mpy_locator import MPyLocator

        src = ("from mpynode._common.methods.maya_command import maya_command\n"
               "@maya_command(name='setMeshRegion')\n"
               "def set_region(self, indices=None):\n"
               "    pass\n")
        loc = MPyLocator.create(name="methloc")
        loc.set_methods_source(src)
        payload = serialize_node(loc)
        self.assertEqual(payload.get("methods_source"), src)

        path = os.path.join(self._tmpdir, "meth.mpn")
        save_mpn(payload, path)
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        reborn = deserialize_node(load_mpn(path), name="methreborn")
        self.assertEqual(reborn.get_methods_source(), src)
        # the @maya_command survives so the compiled node still gets the cmd
        self.assertEqual([c["name"] for c in reborn.list_commands()],
                         ["setMeshRegion"])

    def test_deserialize_reports_tier_setter_failure(self):
        """A setter returning False (e.g. syntax-error methods source) must be
        surfaced via the opt-in return_failures channel -- but the text is
        still persisted (the user never loses the broken edit)."""
        from mpynode._common.io.mpn_io import (
            deserialize_node, load_mpn, save_mpn, serialize_node)
        from mpynode.wrappers.mpy_locator import MPyLocator

        bad = "def f(:\n    pass\n"  # deliberate SyntaxError
        loc = MPyLocator.create(name="badmeth")
        loc.set_methods_source(bad)
        path = os.path.join(self._tmpdir, "badmeth.mpn")
        save_mpn(serialize_node(loc), path)

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        reborn, fails = deserialize_node(
            load_mpn(path), name="badmethreborn", return_failures=True)
        self.assertIn("methods_source", fails)
        self.assertIsInstance(fails["methods_source"], str)
        # the text is still persisted; only the validation flag bubbled up.
        self.assertEqual(reborn.get_methods_source(), bad)

    def test_deserialize_default_contract_unchanged(self):
        """Without return_failures, deserialize_node still returns a single
        node (not a tuple) -- preserves the existing 4 callers."""
        from mpynode._common.io.mpn_io import deserialize_node

        payload = {
            "native_type": "mPyNode",
            "expression": "",
            "input_attrs": {},
            "output_attrs": {},
            "stored_vars": {},
        }
        result = deserialize_node(payload, name="defaultcontract")
        self.assertFalse(
            isinstance(result, tuple),
            "default deserialize_node call must NOT return a tuple",
        )

    def test_deserialize_reports_missing_tier_setter(self):
        """A payload carrying a tier the wrapper doesn't support must be
        surfaced via return_failures -- the silent drop is the bug.

        Pick whatever source tier the BASE ``MPyNode`` genuinely lacks: now
        that MethodsSourceMixin is on the base (Methods tab on every type),
        methods_source is no longer missing -- but the Viewport/OSL tiers live
        only on MPyFile, so a vanilla mPyNode still lacks those setters and
        exercises the missing-setter branch."""
        from mpynode._common.io.mpn_io import _SOURCE_TIER_SETTERS, deserialize_node
        from mpynode.wrappers._mpy_node import MPyNode

        tier = next((t for t, setter in _SOURCE_TIER_SETTERS.items()
                     if not hasattr(MPyNode, setter)), None)
        self.assertIsNotNone(
            tier, "no source tier is missing from MPyNode -- the missing-setter "
            "branch can no longer be exercised on the base wrapper; add a tier "
            "or test against a deliberately-limited wrapper")
        setter = _SOURCE_TIER_SETTERS[tier]
        payload = {
            "native_type": "mPyNode",
            "expression": "",
            "input_attrs": {},
            "output_attrs": {},
            "stored_vars": {},
            tier: "some non-empty tier source\n",
        }
        node, fails = deserialize_node(
            payload, name="missingtier", return_failures=True)
        self.assertIn(tier, fails)
        self.assertIn(setter, fails[tier])


# ===========================================================================
# _ImportNodeCommand (undoable)
# ===========================================================================


class TestImportNodeCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_import_command_creates_node(self):
        from mpynode._base.commands import _ImportNodeCommand, run_undoable

        payload = {
            "native_type": "mPyNode",
            "expression": "out = 1",
            "input_attrs": {"a": {"attr_type": "float", "is_array": False}},
            "output_attrs": {"out": {"attr_type": "float", "is_array": False}},
            "stored_vars": {},
        }
        cmd = _ImportNodeCommand(payload, name="imp")
        run_undoable(cmd)
        self.assertEqual(cmd.created_name, "imp")
        self.assertTrue(mc.objExists("imp"))

    def test_import_command_undo_removes_node(self):
        from mpynode._base.commands import _ImportNodeCommand, run_undoable

        payload = {
            "native_type": "mPyNode",
            "expression": "",
            "input_attrs": {},
            "output_attrs": {},
            "stored_vars": {},
        }
        cmd = _ImportNodeCommand(payload, name="undoable_imp")
        run_undoable(cmd)
        self.assertTrue(mc.objExists("undoable_imp"))
        mc.undo()
        self.assertFalse(mc.objExists("undoable_imp"))

    def test_import_command_collects_tier_failures(self):
        """Tier-restore failures during import must be surfaced on the
        command object so a UI consumer can show them to the user."""
        from mpynode._base.commands import _ImportNodeCommand, run_undoable

        payload = {
            "native_type": "mPyLocator",  # has set_methods_source
            "expression": "",
            "input_attrs": {},
            "output_attrs": {},
            "stored_vars": {},
            "methods_source": "def f(:\n    pass\n",  # SyntaxError
        }
        cmd = _ImportNodeCommand(payload, name="cmd_badmeth")
        run_undoable(cmd)
        self.assertTrue(isinstance(cmd.tier_failures, dict))
        self.assertIn("methods_source", cmd.tier_failures)
        self.assertIsInstance(cmd.tier_failures["methods_source"], str)


# ===========================================================================
# Shelf installer (mock cmds.shelfButton)
# ===========================================================================


class TestShelfInstaller(unittest.TestCase):
    def test_install_returns_None_when_no_shelf(self):
        """In mayapy with no Maya UI, get_top_shelf returns None and
        install_shelf_button returns None gracefully."""
        from mpynode.ui.shelf import install_shelf_button

        # No active shelf in mayapy → expect None.
        result = install_shelf_button()
        self.assertIsNone(result)

    def test_command_string_imports_show_designer(self):
        from mpynode.ui.shelf import SHELF_BUTTON_COMMAND

        self.assertIn("show_designer", SHELF_BUTTON_COMMAND)
        self.assertIn("from mpynode.ui.mpynode_designer import", SHELF_BUTTON_COMMAND)


# ===========================================================================
# UI shape (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestUIShape(unittest.TestCase):
    def test_file_menu_has_import_export_actions(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_menu_bar)
        self.assertIn("Import .mpn", src)
        self.assertIn("Export Current Node as .mpn", src)
        self.assertIn("importMpnDialog", src)
        self.assertIn("exportCurrentNodeAsMpn", src)

    def test_main_window_has_export_helpers(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        for name in (
            "importMpnDialog",
            "exportCurrentNodeAsMpn",
            "_export_node_as_mpn",
            "_on_export_node_requested",
        ):
            self.assertTrue(
                hasattr(NDMainWindow, name),
                f"NDMainWindow should have {name}",
            )

    def test_scene_tree_has_export_signal_and_menu(self):
        import inspect

        from mpynode.ui.widgets.scene_tree import NDSceneTree

        self.assertTrue(hasattr(NDSceneTree, "exportNodeRequested"))
        src = inspect.getsource(NDSceneTree._build_context_menu)
        self.assertIn("Export to.mpn", src)
        self.assertIn("exportNodeRequested.emit", src)

    def test_main_window_wires_export_signal(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._wire_signals)
        self.assertIn("exportNodeRequested.connect", src)
        self.assertIn("_on_export_node_requested", src)

    def test_import_command_class_present(self):
        from mpynode._base.commands import _ImportNodeCommand

        self.assertTrue(callable(_ImportNodeCommand))



class TestExportCompressionPref(unittest.TestCase):
    """.mpn export uses the OS-native dialog; the lzma 'maximum
    compression' option lives in Preferences (no custom dialog)."""

    def test_pref_exists_default_off(self):
        from mpynode.ui import preferences

        self.assertIn("mpn_export_max_compression", preferences.DEFAULT_PREFS)
        self.assertIs(
            preferences.DEFAULT_PREFS["mpn_export_max_compression"], False
        )

    def test_export_uses_native_dialog_and_reads_pref(self):
        import inspect
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._export_node_as_mpn)
        self.assertIn("getSaveFileName", src)            # native dialog
        self.assertNotIn("DontUseNativeDialog", src)     # NOT a custom dialog
        self.assertIn("mpn_export_max_compression", src)  # reads the pref

    def test_prefs_dialog_exposes_export_checkbox(self):
        import inspect
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        src = inspect.getsource(NDPreferencesDialog)
        self.assertIn("_export_max_compress_check", src)
        self.assertIn("mpn_export_max_compression", src)


# ===================== from test_mpn_persistent_toggle.py =====================
import inspect
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import standalone_init, ensure_plugins_loaded


def _setUpModule__mpn_persistent_toggle():
    standalone_init()


class _FakeNode:
    """Minimal duck-typed py_node for serialize_node (no live Maya node)."""

    def __init__(self, name, variables):
        self._name = name
        self._vars = dict(variables)

    def get_name(self):
        return self._name

    def get_variables(self):
        return dict(self._vars)

    def get_variable_names(self):
        return list(self._vars)

    def get_compute_expression(self):
        return "out = x"

    def get_input_attr_map(self):
        return {"x": {"attr_type": "float"}}

    def get_output_attr_map(self):
        return {"out": {"attr_type": "float"}}


class TestSerializeIncludePersistent(unittest.TestCase):
    """(A) save-side include_persistent toggle on serialize_node."""

    def test_include_persistent_false_drops_stored_vars(self):
        from mpynode._common.io import mpn_io

        node = _FakeNode("foo", {"x": 5})
        with mock.patch.object(mpn_io.mc, "nodeType", return_value="mPyNode"):
            payload = mpn_io.serialize_node(node, include_persistent=False)
        self.assertEqual(payload["stored_vars"], {})
        # Definitions are still captured; only the persistent data drops.
        self.assertEqual(payload["expression"], "out = x")
        self.assertIn("x", payload["input_attrs"])
        self.assertIn("out", payload["output_attrs"])

    def test_default_keeps_stored_vars_backcompat(self):
        from mpynode._common.io import mpn_io

        node = _FakeNode("foo", {"x": 5})
        with mock.patch.object(mpn_io.mc, "nodeType", return_value="mPyNode"):
            payload = mpn_io.serialize_node(node)
        self.assertEqual(payload["stored_vars"], {"x": 5})

    def test_include_values_false_keeps_the_declarations_and_drops_the_data(self):
        # The Node Designer's "Declarations only": the restored node has its
        # persistent variables declared and None, the way an API-created node
        # starts -- NOT the include_persistent=False shape, which loses the
        # names too.
        from mpynode._common.io import mpn_io

        node = _FakeNode("foo", {"x": 5, "y": [1, 2]})
        with mock.patch.object(mpn_io.mc, "nodeType", return_value="mPyNode"):
            payload = mpn_io.serialize_node(node, include_values=False)
        self.assertEqual(payload["stored_vars"], {"x": None, "y": None})
        self.assertEqual(sorted(payload["persistent_vars"]), ["x", "y"])


class TestDeserializeRestorePersistent(unittest.TestCase):
    """(B) restore-side restore_persistent toggle on deserialize_node."""

    def setUp(self):
        ensure_plugins_loaded()

    def _round_trip_payload(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io import mpn_io
        from mpynode._common.storedvars.stored_vars_api import set_variable

        src = MPyNode.create(name="persist_src")
        nm = src.get_name()
        set_variable(nm, "v", 7, persistent=True)
        payload = mpn_io.serialize_node(src)
        self.assertEqual(payload["stored_vars"].get("v"), 7)
        return payload

    def test_restore_persistent_false_skips_stored_vars(self):
        from mpynode._common.io import mpn_io

        payload = self._round_trip_payload()
        off = mpn_io.deserialize_node(
            payload, name="persist_off", restore_persistent=False)
        self.assertNotIn("v", off.get_variables() or {})

    def test_default_restores_stored_vars_backcompat(self):
        from mpynode._common.io import mpn_io

        payload = self._round_trip_payload()
        on = mpn_io.deserialize_node(payload, name="persist_on")
        self.assertEqual((on.get_variables() or {}).get("v"), 7)

    def test_round_trip_preserves_non_persistent(self):
        """A non-persistent (session-only) stored var must NOT be promoted to
        persistent across a serialize_node -> deserialize_node round-trip; a
        persistent one stays persistent. The .mpn records the persistence set
        (persistent_vars), matching the .ma's _storedVarNames distinction."""
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io import mpn_io
        from mpynode._common.storedvars.stored_vars_api import set_variable

        src = MPyNode.create(name="persist_roundtrip_src")
        nm = src.get_name()
        set_variable(nm, "keep", 1, persistent=True)
        set_variable(nm, "scratch", 2, persistent=False)
        payload = mpn_io.serialize_node(src)
        # Capture keeps both values; the native spec extractor needs them...
        self.assertIn("keep", payload["stored_vars"])
        self.assertIn("scratch", payload["stored_vars"])
        # ...but only 'keep' is recorded as persistent.
        self.assertEqual(payload.get("persistent_vars"), ["keep"])
        dst = mpn_io.deserialize_node(payload, name="persist_roundtrip_dst")
        self.assertTrue(dst.is_variable_persistent("keep"))
        self.assertFalse(dst.is_variable_persistent("scratch"))

    def test_import_command_forwards_restore_persistent(self):
        from mpynode._base import commands

        src = inspect.getsource(commands._ImportNodeCommand)
        # a param on __init__, forwarded into deserialize_node.
        self.assertIn("restore_persistent", src)
        self.assertIn("restore_persistent=", src)


# ===========================================================================
# load_mpn_header (safe raw-JSON reader -- NO stored_vars decode, NO pickle)
# ===========================================================================


class TestLoadMpnHeader(unittest.TestCase):
    """load_mpn_header parses the raw JSON envelope and returns ``data`` with
    ``stored_vars`` left UNTOUCHED -- it must NEVER decode stored vars and must
    NEVER call serialization.decode_stored_vars_detailed. This is the
    security-critical accessor used by the template-gallery bulk scan."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="ndhdr_")

    def tearDown(self):
        for f in os.listdir(self._tmpdir):
            try:
                os.remove(os.path.join(self._tmpdir, f))
            except Exception:
                pass
        try:
            os.rmdir(self._tmpdir)
        except Exception:
            pass

    def _write_envelope(self, fname, data):
        path = os.path.join(self._tmpdir, fname)
        with open(path, "w") as f:
            json.dump({"version": 2, "data": data}, f)
        return path

    def test_header_returns_data_with_raw_stored_vars_string(self):
        from mpynode._common.io.mpn_io import load_mpn_header

        # stored_vars is an (opaque) encoded STRING, exactly as on disk.
        raw_sv = "ENCODED-STORED-VARS-BLOB"
        path = self._write_envelope(
            "hdr.mpn",
            {"native_type": "mPyNode", "expression": "out = 1",
             "stored_vars": raw_sv},
        )
        data = load_mpn_header(path)
        self.assertEqual(data["native_type"], "mPyNode")
        self.assertEqual(data["expression"], "out = 1")
        # stored_vars comes back as the raw string, not a decoded dict.
        self.assertEqual(data["stored_vars"], raw_sv)
        self.assertIsInstance(data["stored_vars"], str)

    def test_header_rejects_bad_version(self):
        from mpynode._common.io.mpn_io import load_mpn_header

        path = os.path.join(self._tmpdir, "badv.mpn")
        with open(path, "w") as f:
            json.dump({"version": 999, "data": {}}, f)
        with self.assertRaises(ValueError):
            load_mpn_header(path)

    def test_header_rejects_non_dict_data(self):
        from mpynode._common.io.mpn_io import load_mpn_header

        path = os.path.join(self._tmpdir, "badd.mpn")
        with open(path, "w") as f:
            json.dump({"version": 2, "data": "not_a_dict"}, f)
        with self.assertRaises(ValueError):
            load_mpn_header(path)

    def test_header_never_calls_stored_vars_decoder(self):
        """The security-critical guarantee: load_mpn_header must NEVER invoke
        the stored-vars decoder (which would pickle.loads an untrusted blob).
        Monkeypatch the decoder to BLOW UP if it is ever called."""
        from mpynode._common.io import mpn_io, serialization

        path = self._write_envelope(
            "noscan.mpn",
            {"native_type": "mPyNode", "stored_vars": "ENCODED-BLOB"},
        )

        def _boom(*a, **k):
            raise AssertionError(
                "load_mpn_header decoded stored_vars -- pickle path reached")

        original = serialization.decode_stored_vars_detailed
        serialization.decode_stored_vars_detailed = _boom
        try:
            data = mpn_io.load_mpn_header(path)
        finally:
            serialization.decode_stored_vars_detailed = original
        # Reached here without the AssertionError -> decoder was never called.
        self.assertEqual(data["stored_vars"], "ENCODED-BLOB")


def setUpModule():
    _setUpModule__phase24()
    _setUpModule__mpn_persistent_toggle()


class TestApiGapSpacingRoundTrip(unittest.TestCase):
    """The API view's blank-line spacing rides the .mpn like ``metadata`` does.

    Structured dict, captured only when NON-EMPTY. That last part is the whole
    reason a plain node's payload -- and every shipped template's -- is
    unchanged by the feature existing.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _node(self, name="gapio#"):
        from mpynode import MPyNode

        return MPyNode.create(name=name)

    def test_an_untouched_node_carries_no_key(self):
        from mpynode._common.io.mpn_io import serialize_node

        payload = serialize_node(self._node())
        self.assertNotIn("api_gap_spacing", payload)

    def test_spacing_survives_a_round_trip(self):
        from mpynode._common.io.mpn_io import deserialize_node, serialize_node

        node = self._node()
        node.set_api_gap_spacing({"attrs_out": 3, "return": 0})
        payload = serialize_node(node)
        self.assertEqual(payload["api_gap_spacing"],
                         {"attrs_out": 3, "return": 0})
        mc.file(new=True, force=True)
        rebuilt = deserialize_node(payload, skip_selection=True)
        if isinstance(rebuilt, (list, tuple)):
            rebuilt = rebuilt[0]
        self.assertEqual(rebuilt.get_api_gap_spacing(),
                         {"attrs_out": 3, "return": 0})

    def test_a_malformed_value_costs_only_its_own_key(self):
        node = self._node()
        node.set_api_gap_spacing({"attrs_out": 2, "class_decl": "lots",
                                  "": 4, "return": True})
        # str, empty name and bool are all unusable as a line COUNT; each one
        # falls back to the exporter's own spacing, which is always valid.
        self.assertEqual(node.get_api_gap_spacing(), {"attrs_out": 2})

    def test_a_count_is_clamped_rather_than_obeyed(self):
        from mpynode._common.lifecycle.gap_spacing_registry import MAX_GAP

        node = self._node()
        node.set_api_gap_spacing({"attrs_out": 9999, "return": -3})
        self.assertEqual(node.get_api_gap_spacing(),
                         {"attrs_out": MAX_GAP, "return": 0})


if __name__ == "__main__":
    import unittest
    unittest.main()
