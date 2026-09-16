"""Stored variables: write side, deferred store, serialization/decode-cache, wrapper API

Consolidated from: test_phase19.py, test_stored_var_store.py, test_decode_cache.py, test_phase11.py.
"""

from __future__ import annotations

# ===================== from test_phase19.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase19():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Wrapper-level: set_variable + rename_variable
# ===========================================================================


class TestStoredVarWrapper(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_set_stored_var_creates_if_missing(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sv1")
        n.set_variable("counter", 0)
        self.assertEqual(n.get_variables(), {"counter": 0})
        # A var CREATED by set_variable is session-only. Persistence is an
        # opt-in (add_variable, set_variable_persistent, persistent=True) --
        # never a side effect of writing a value.
        self.assertNotIn("counter", n.get_variable_names())

    def test_set_stored_var_updates_existing(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sv2")
        n.add_variable("counter", 0)
        n.set_variable("counter", 42)
        self.assertEqual(n.get_variables()["counter"], 42)

    def test_set_stored_var_with_complex_value(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sv3")
        n.set_variable("config", {"a": 1, "b": [1, 2, 3]})
        self.assertEqual(
            n.get_variables()["config"],
            {"a": 1, "b": [1, 2, 3]},
        )

    def test_rename_stored_var_preserves_value(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sv4")
        n.add_variable("foo", 99)
        n.rename_variable("foo", "bar")
        self.assertNotIn("foo", n.get_variables())
        self.assertEqual(n.get_variables()["bar"], 99)
        self.assertIn("bar", n.get_variable_names())
        self.assertNotIn("foo", n.get_variable_names())

    def test_rename_stored_var_collision_raises(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sv5")
        n.add_variable("a", 1)
        n.add_variable("b", 2)
        with self.assertRaises(ValueError):
            n.rename_variable("a", "b")

    def test_rename_stored_var_missing_raises(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sv6")
        with self.assertRaises(ValueError):
            n.rename_variable("nonexistent", "anything")


# ===========================================================================
# Storage commands (undoable)
# ===========================================================================


class TestStorageCommands(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_add_stored_var_command_undoable(self):
        from mpynode._base.commands import _AddStoredVarCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sc1")
        run_undoable(_AddStoredVarCommand(n, "counter", 5))
        self.assertEqual(n.get_variables().get("counter"), 5)

        mc.undo()
        self.assertNotIn("counter", n.get_variables())

        mc.redo()
        self.assertEqual(n.get_variables().get("counter"), 5)

    def test_remove_stored_var_command_undoable(self):
        from mpynode._base.commands import _RemoveStoredVarCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sc2")
        n.add_variable("doomed", 7)

        run_undoable(_RemoveStoredVarCommand(n, "doomed"))
        self.assertNotIn("doomed", n.get_variables())

        mc.undo()
        # Maya's chunk-undo should restore the _storedVarsData attr.
        self.assertEqual(n.get_variables().get("doomed"), 7)

    def test_set_stored_var_command_undoable(self):
        from mpynode._base.commands import _SetStoredVarCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sc3")
        n.add_variable("x", 1)
        run_undoable(_SetStoredVarCommand(n, "x", 999))
        self.assertEqual(n.get_variables()["x"], 999)

        mc.undo()
        self.assertEqual(n.get_variables()["x"], 1)

    def test_rename_stored_var_command_undoable(self):
        from mpynode._base.commands import _RenameStoredVarCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="sc4")
        n.add_variable("old", "hello")

        run_undoable(_RenameStoredVarCommand(n, "old", "new"))
        self.assertEqual(n.get_variables().get("new"), "hello")
        self.assertNotIn("old", n.get_variables())

        mc.undo()
        self.assertEqual(n.get_variables().get("old"), "hello")
        self.assertNotIn("new", n.get_variables())


# ===========================================================================
# Change-listener registry: a compute-time persistent-var write goes only to
# the in-memory store, so the designer subscribes to refresh the Variables /
# Watch UI without a plug change. The notify carries the node's hashCode,
# which must equal the name-derived hash the designer resolves.
# ===========================================================================


class TestStoredVarChangeListener(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_add_notify_remove(self):
        from mpynode._common.storedvars import stored_var_store as svs

        got = []
        cb  = lambda h: got.append(h)
        svs.add_change_listener(cb)
        try:
            svs._notify_change("HASH_A")
            self.assertEqual(got, ["HASH_A"])
            # duplicate add must not double-fire
            svs.add_change_listener(cb)
            got.clear()
            svs._notify_change("HASH_B")
            self.assertEqual(got, ["HASH_B"])
        finally:
            svs.remove_change_listener(cb)
        got.clear()
        svs._notify_change("HASH_C")
        self.assertEqual(got, [])

    def test_raising_listener_is_isolated(self):
        from mpynode._common.storedvars import stored_var_store as svs

        good = []

        def boom(h):
            raise RuntimeError("listener boom")

        cb = lambda h: good.append(h)
        svs.add_change_listener(boom)
        svs.add_change_listener(cb)
        try:
            svs._notify_change("HASH_X")
            self.assertEqual(good, ["HASH_X"])
        finally:
            svs.remove_change_listener(boom)
            svs.remove_change_listener(cb)

    def test_set_for_compute_notifies_with_name_hash(self):
        import maya.api.OpenMaya as om

        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode.wrappers._mpy_node import MPyNode

        n    = MPyNode.create(name="listenNode")
        name = n.get_name()
        sel  = om.MSelectionList()
        sel.add(name)
        mo  = sel.getDependNode(0)

        got = []
        cb  = lambda h: got.append(h)
        svs.add_change_listener(cb)
        try:
            svs.set_for_compute(mo, {"buf": b"bytes"})
            self.assertEqual(len(got), 1)
            # the notify hash must match what the designer resolves by name
            self.assertEqual(got[0], svs._hash_for_name(name))
        finally:
            svs.remove_change_listener(cb)

    def test_the_name_based_writers_notify_too(self):
        """``set_for_compute`` is not the only write path.

        ``stored_vars_api`` -- and so ``MPyNode.set_variable`` from a user
        script -- lands in ``set_var`` / ``set_data`` / ``remove_var``. Those
        used to mutate the store silently, so a scripted write left the
        Variables and Watch panels rendering the PREVIOUS value until
        something unrelated happened to refresh them.
        """
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode.wrappers._mpy_node import MPyNode

        n    = MPyNode.create(name="writerNode")
        name = n.get_name()
        want = svs._hash_for_name(name)

        for label, call in (
            ("set_var", lambda: svs.set_var(name, "v", 1)),
            ("set_data", lambda: svs.set_data(name, {"v": 2})),
            ("remove_var", lambda: svs.remove_var(name, "v")),
        ):
            got = []
            cb  = lambda h: got.append(h)          # noqa: E731
            svs.add_change_listener(cb)
            try:
                call()
            finally:
                svs.remove_change_listener(cb)
            self.assertEqual(
                got, [want],
                "%s did not notify the stored-var listeners; a scripted "
                "write leaves the UI stale" % label)

    def test_set_variable_through_the_public_api_notifies(self):
        """End-to-end on the path the user actually types."""
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode.wrappers._mpy_node import MPyNode

        n   = MPyNode.create(name="apiWriterNode")
        got = []
        cb  = lambda h: got.append(h)              # noqa: E731
        svs.add_change_listener(cb)
        try:
            n.set_variable("audioData", b"RIFF....WAVE", persistent=True)
        finally:
            svs.remove_change_listener(cb)
        self.assertIn(
            svs._hash_for_name(n.get_name()), got,
            "MPyNode.set_variable fired no change notification")


# ===========================================================================
# Persistence preservation: _SetStoredVarCommand(persistent=...) must honor a
# Temporary var's non-persistent status -- neither loading media into it nor
# editing its value inline may silently promote it. The default is None (leave
# the status alone), matching set_variable; True/False still set it.
# ===========================================================================


class TestStoredVarPersistencePreservation(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_set_into_temp_var_stays_non_persistent(self):
        from mpynode._base.commands import (
            _AddTemporaryVarCommand,
            _SetStoredVarCommand,
            run_undoable,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="mp1")
        run_undoable(_AddTemporaryVarCommand(n, "clip", b"old"))
        self.assertFalse(n.is_variable_persistent("clip"))

        run_undoable(_SetStoredVarCommand(n, "clip", b"newbytes", False))
        self.assertEqual(n.get_variables().get("clip"), b"newbytes")
        self.assertFalse(n.is_variable_persistent("clip"))

    def test_default_does_not_promote_and_explicit_true_still_does(self):
        from mpynode._base.commands import (
            _AddTemporaryVarCommand,
            _SetStoredVarCommand,
            run_undoable,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="mp2")
        run_undoable(_AddTemporaryVarCommand(n, "clip", b"old"))

        # default (no flag) leaves the status alone -- an inline value edit on
        # a Temporary row used to silently promote it to Persistent.
        run_undoable(_SetStoredVarCommand(n, "clip", b"edited"))
        self.assertEqual(n.get_variables().get("clip"), b"edited")
        self.assertFalse(n.is_variable_persistent("clip"))

        # explicit True is still how you promote...
        run_undoable(_SetStoredVarCommand(n, "clip", b"promoted", True))
        self.assertTrue(n.is_variable_persistent("clip"))

        # ...and the default then leaves it persistent, too.
        run_undoable(_SetStoredVarCommand(n, "clip", b"stayput"))
        self.assertTrue(n.is_variable_persistent("clip"))
        self.assertEqual(n.get_variables().get("clip"), b"stayput")


# ===========================================================================
# End-to-end counter through stored vars + expression
# ===========================================================================


class TestStoredVarRoundTrip(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_counter_increments_via_stored_var(self):
        """The phase19 plan called for: tests for round-trip a stored
        counter through the UI. UI is inspect-only at the test level,
        so we do the wrapper round-trip + verify the expression sees
        the value."""
        from mpynode._base.commands import (
            _AddStoredVarCommand,
            _SetStoredVarCommand,
            run_undoable,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="rt1")
        n.add_input_attr("trigger", "float")
        n.add_output_attr("counter_out", "int")
        n.add_variable("counter", 0)
        n.set_compute_expression("self.counter = self.counter + 1\nself.counter_out = self.counter")
        # Trigger compute by reading the output.
        v1 = mc.getAttr(n.get_name() + ".counter_out")
        # Bump trigger to force recompute.
        mc.setAttr(n.get_name() + ".trigger", 1.0)
        v2 = mc.getAttr(n.get_name() + ".counter_out")

        # User writes to stored var via UI (= command):
        run_undoable(_SetStoredVarCommand(n, "counter", 100))
        # Bump trigger again \u2192 expression should pick up reset.
        mc.setAttr(n.get_name() + ".trigger", 2.0)
        v3 = mc.getAttr(n.get_name() + ".counter_out")
        self.assertEqual(v3, 101)  # 100 + 1


# ===========================================================================
# Validators (pure functions, no Qt instantiation needed)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestValidators(unittest.TestCase):
    def test_validate_var_name_basic(self):
        from mpynode.ui.widgets.variables import validate_var_name

        ok, _ = validate_var_name("counter", set())
        self.assertTrue(ok)
        ok, _ = validate_var_name("my_var_1", set())
        self.assertTrue(ok)

    def test_validate_var_name_empty(self):
        from mpynode.ui.widgets.variables import validate_var_name

        ok, _ = validate_var_name("", set())
        self.assertFalse(ok)

    def test_validate_var_name_keyword(self):
        from mpynode.ui.widgets.variables import validate_var_name

        for kw in ("class", "def", "if", "self", "lambda"):
            ok, _ = validate_var_name(kw, set())
            self.assertFalse(ok, f"{kw!r} should be invalid")

    def test_validate_var_name_collision(self):
        from mpynode.ui.widgets.variables import validate_var_name

        ok, _ = validate_var_name("foo", existing={"foo"})
        self.assertFalse(ok)

    def test_validate_var_name_leading_digit(self):
        from mpynode.ui.widgets.variables import validate_var_name

        ok, _ = validate_var_name("1foo", set())
        self.assertFalse(ok)

    def test_parse_value_text_literals(self):
        from mpynode.ui.widgets.variables import parse_value_text

        self.assertEqual(parse_value_text("42"),        42)
        self.assertEqual(parse_value_text("3.14"),      3.14)
        self.assertEqual(parse_value_text("'hello'"),   "hello")
        self.assertEqual(parse_value_text('"hello"'),   "hello")
        self.assertEqual(parse_value_text("[1, 2, 3]"), [1, 2, 3])
        self.assertEqual(parse_value_text("{'a': 1}"),  {"a": 1})
        self.assertEqual(parse_value_text("True"),      True)
        self.assertEqual(parse_value_text("None"),      None)
        self.assertEqual(parse_value_text(""),          None)

    def test_parse_value_text_rejects_non_literal(self):
        from mpynode.ui.widgets.variables import parse_value_text

        for bad in ("foo", "1 + 2", "[].append(1)", "lambda x: x"):
            with self.assertRaises(ValueError):
                parse_value_text(bad)


# ===========================================================================
# Widget structural tests (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestVariablesWidgetShape(unittest.TestCase):
    def test_widget_has_buttons_and_methods(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget

        for name in (
            "_on_add_clicked",
            "_on_remove_clicked",
            "_on_item_changed",
            "_handle_inline_rename",
            "_handle_inline_value_edit",
            "refresh",
            "setPyNode",
        ):
            self.assertTrue(
                hasattr(NDVariablesWidget, name),
                f"NDVariablesWidget should have {name}",
            )

    def test_tree_item_is_editable(self):
        from mpynode.ui.qt_wrapper import Qt
        from mpynode.ui.widgets.variables import NDVariableTreeItem

        flags = NDVariableTreeItem.EDITABLE_FLAGS
        self.assertTrue(bool(flags & Qt.ItemIsEditable))

    def test_designer_imports_new_widget_module(self):
        import inspect

        import mpynode.ui.mpynode_designer as dm

        src = inspect.getsource(dm)
        self.assertIn(
            "from mpynode.ui.widgets.variables import NDVariablesWidget",
            src,
        )

    def test_buttons_wired(self):
        import inspect

        from mpynode.ui.widgets.variables import NDVariablesWidget

        src = inspect.getsource(NDVariablesWidget.__init__)
        self.assertIn("_add_btn.clicked.connect",     src)
        self.assertIn("_del_btn.clicked.connect",     src)
        self.assertIn("_refresh_btn.clicked.connect", src)
        self.assertIn("_tree.itemChanged.connect",    src)


# ===================== from test_stored_var_store.py =====================
import os
import tempfile
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__stored_var_store():
    standalone_init()


def _plug_raw(name):
    try:
        return mc.getAttr(name + "._storedVarsData") or ""
    except Exception:
        return ""


class TestStoredVarStoreUnit(unittest.TestCase):
    """Resilient encoder -- pure, no scene state."""

    def test_resilient_encode_passes_clean_dict(self):
        from mpynode._common.io import serialization as ser

        blob, dropped = ser.encode_stored_vars_resilient({"a": 1, "b": [1, 2]})
        self.assertEqual(dropped, [])
        self.assertEqual(ser.decode_stored_vars(blob), {"a": 1, "b": [1, 2]})

    def test_resilient_encode_drops_unpicklable(self):
        from mpynode._common.io import serialization as ser

        bad = lambda x: x  # noqa: E731 -- lambdas can't pickle
        blob, dropped = ser.encode_stored_vars_resilient(
            {"good": 42, "bad": bad}
        )
        self.assertEqual(dropped, ["bad"])
        decoded = ser.decode_stored_vars(blob)
        self.assertEqual(decoded, {"good": 42})


class TestStoredVarStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._common.storedvars import stored_var_store

        stored_var_store.evict_all()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="svstore_test")
        self.name = self.node.get_name()

    # -- deferred semantics -------------------------------------------

    def test_write_is_deferred_plug_stays_empty(self):
        from mpynode._common.storedvars import stored_var_store as svs

        self.node.set_variable("k", [1, 2, 3])
        # Value visible via the store / API immediately...
        self.assertEqual(self.node.get_variables().get("k"), [1, 2, 3])
        self.assertEqual(svs.get_data(self.name).get("k"), [1, 2, 3])
        # ...but the plug is still empty (deferred).
        self.assertEqual(_plug_raw(self.name), "")

    def test_flush_then_plug_has_data(self):
        from mpynode._common.storedvars import stored_var_store as svs

        self.node.set_variable("k", 99, persistent=True)
        svs.flush_all()
        raw = _plug_raw(self.name)
        self.assertTrue(raw)
        from mpynode._common.io import serialization as ser

        self.assertEqual(ser.decode_stored_vars(raw).get("k"), 99)

    def test_clear_loaded_plugs_keeps_cache(self):
        from mpynode._common.storedvars import stored_var_store as svs

        self.node.set_variable("k", 7, persistent=True)
        svs.flush_all()
        self.assertTrue(_plug_raw(self.name))
        svs.clear_loaded_plugs()
        self.assertEqual(_plug_raw(self.name), "")
        # cache intact
        self.assertEqual(svs.get_data(self.name).get("k"), 7)

    def test_load_and_clear_hydrates_then_empties_plug(self):
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode._common.io import serialization as ser

        # Seed the plug directly + drop the cache, simulating a fresh load.
        mc.setAttr(
            self.name + "._storedVarsData",
            ser.encode_stored_vars({"k": "hello"}),
            type="string",
        )
        svs.evict_all()
        svs.load_and_clear_all()
        self.assertEqual(_plug_raw(self.name), "")                   # plug cleared
        self.assertEqual(svs.get_data(self.name).get("k"), "hello")  # cached

    def test_no_stale_read_after_load_clear(self):
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode._common.io import serialization as ser

        mc.setAttr(
            self.name + "._storedVarsData",
            ser.encode_stored_vars({"k": 1}),
            type="string",
        )
        svs.evict_all()
        svs.load_and_clear_all()
        # Update in memory; plug must remain empty (no stale serialized copy).
        self.node.set_variable("k", 2)
        self.assertEqual(_plug_raw(self.name), "")
        self.assertEqual(self.node.get_variables().get("k"), 2)

    def test_load_preserves_init_session_vars(self):
        # On scene open Init runs first and flushes a session var into the
        # cache BEFORE load_and_clear_all hydrates the plug. The hydrate must
        # MERGE (plug wins per key), not clobber the init-written var.
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode._common.io import serialization as ser

        mc.setAttr(
            self.name + "._storedVarsData",
            ser.encode_stored_vars({"persisted": 7}),
            type="string",
        )
        svs.evict_all()
        svs.set_data(self.name, {"sessionvar": 123})  # simulate Init-source flush
        svs.load_and_clear_all()
        data = svs.get_data(self.name)
        self.assertEqual(data.get("sessionvar"), 123)  # init session var kept
        self.assertEqual(data.get("persisted"), 7)     # persistent restored

    def test_footprint_nonzero(self):
        from mpynode._common.storedvars import stored_var_store as svs

        self.node.set_variable("blob", list(range(1000)))
        self.assertGreater(svs.footprint(self.name), 0)
        self.assertGreater(svs.total_footprint(), 0)

    # -- compute integration ------------------------------------------

    def test_compute_writeback_goes_to_store_not_plug(self):
        from mpynode._common.storedvars import stored_var_store as svs

        self.node.add_output_attr("out", "float")
        self.node.add_variable("counter", 0)  # seed so self.counter reads ok
        self.node.set_compute_expression(
            "self.counter = self.counter + 1\nself.out = float(self.counter)\n"
        )
        # Pull the output to force a compute.
        mc.getAttr(self.name + ".out")
        self.assertGreaterEqual(svs.get_data(self.name).get("counter", 0), 1)
        # The compute write-back did NOT touch the plug (deferred).
        self.assertEqual(_plug_raw(self.name), "")

    # -- persistence round-trips --------------------------------------

    def test_save_open_roundtrip(self):
        self.node.set_variable(
            "payload", {"nums": [1, 2, 3], "tag": "x"}, persistent=True)
        tmp = os.path.join(tempfile.gettempdir(), "svstore_save_rt.ma")
        mc.file(rename=tmp)
        mc.file(save=True, type="mayaAscii", force=True)  # kBeforeSave -> flush
        mc.file(new=True, force=True)                     # evict cache
        mc.file(tmp, open=True, force=True)               # kAfterOpen -> load+clear
        from mpynode._common.storedvars.stored_vars_api import get_variables

        got = get_variables(self.name)
        self.assertEqual(got.get("payload"), {"nums": [1, 2, 3], "tag": "x"})
        # plug cleared again post-load (session invariant)
        self.assertEqual(_plug_raw(self.name), "")
        os.remove(tmp)

    def test_export_selection_roundtrip(self):
        self.node.set_variable("exp", [9, 8, 7], persistent=True)
        tmp = os.path.join(tempfile.gettempdir(), "svstore_export_rt.ma")
        mc.select(self.name, r=True)
        mc.file(tmp, exportSelected=True, type="mayaAscii", force=True)  # kBeforeExport -> flush
        mc.file(new=True, force=True)
        mc.file(tmp, i=True)                                             # import -> kAfterImport load+clear
        from mpynode._common.storedvars.stored_vars_api import get_variables

        # imported node keeps its name (no namespace clash in a fresh scene)
        got = get_variables(self.name)
        self.assertEqual(got.get("exp"), [9, 8, 7])
        os.remove(tmp)

    # -- undo / redo ---------------------------------------------------

    def test_undo_redo_add_var(self):
        from mpynode._base.commands import _AddStoredVarCommand, run_undoable

        run_undoable(_AddStoredVarCommand(self.node, "added", 123))
        self.assertEqual(self.node.get_variables().get("added"), 123)
        mc.undo()
        self.assertNotIn("added", self.node.get_variables())
        mc.redo()
        self.assertEqual(self.node.get_variables().get("added"), 123)


class TestRegistryGate(unittest.TestCase):
    """Two-tier model: only vars in ``_storedVarNames`` (registered /
    promoted) are serialized; every other ``self.X`` write is session-only
    (live in the store, never saved)."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._common.storedvars import stored_var_store

        stored_var_store.evict_all()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="gate_test")
        self.name = self.node.get_name()

    def test_unregistered_compute_var_is_not_flushed(self):
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode._common.io import serialization as ser

        self.node.add_output_attr("out", "float")
        # self.foo is NOT registered (no add/promote) -> session-only.
        self.node.set_compute_expression("self.foo = [1, 2, 3]\nself.out = 1.0\n")
        mc.getAttr(self.name + ".out")  # force compute
        # live this session...
        self.assertEqual(svs.get_data(self.name).get("foo"), [1, 2, 3])
        # ...but never serialized.
        svs.flush_all()
        raw   = _plug_raw(self.name)
        saved = ser.decode_stored_vars(raw) if raw else {}
        self.assertNotIn("foo", saved)

    def test_registered_var_is_flushed(self):
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode._common.io import serialization as ser

        self.node.add_variable("bar", 0)   # registered
        self.node.set_variable("bar", 42)
        svs.flush_all()
        saved = ser.decode_stored_vars(_plug_raw(self.name))
        self.assertEqual(saved.get("bar"), 42)

    def test_session_var_not_persistent_across_reload(self):
        from mpynode._common.storedvars.stored_vars_api import (
            get_variables,
            get_variable_names,
        )

        self.node.add_output_attr("out", "float")
        self.node.set_compute_expression(
            "if not hasattr(self, 'seed'):\n"
            "    self.seed = 7\n"
            "self.out = float(self.seed)\n"
        )
        mc.getAttr(self.name + ".out")
        self.assertEqual(get_variables(self.name).get("seed"), 7)
        # never registered -> not in the persistent registry
        self.assertNotIn("seed", get_variable_names(self.name))

        tmp = os.path.join(tempfile.gettempdir(), "svstore_session_rt.ma")
        mc.file(rename=tmp)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(new=True, force=True)
        mc.file(tmp, open=True, force=True)
        # session var was never serialized -> not registered after reload (a
        # re-seed on open lands in the store but never in the registry).
        self.assertNotIn("seed", get_variable_names(self.name))
        os.remove(tmp)

    def test_legacy_blob_keys_are_migrated(self):
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode._common.io import serialization as ser
        from mpynode._common.storedvars.stored_vars_api import get_variable_names

        # Simulate an old-scheme node: data baked into the plug, registry
        # empty (pre-gate auto-persist).
        mc.setAttr(
            self.name + "._storedVarsData",
            ser.encode_stored_vars({"legacy": 99}),
            type="string",
        )
        mc.setAttr(self.name + "._storedVarNames", "", type="string")
        svs.evict_all()
        svs.load_and_clear_all()
        # migrated: auto-registered + preserved in the store
        self.assertIn("legacy", get_variable_names(self.name))
        self.assertEqual(svs.get_data(self.name).get("legacy"), 99)
        # and it re-flushes (no data loss for old scenes)
        svs.flush_all()
        self.assertEqual(
            ser.decode_stored_vars(_plug_raw(self.name)).get("legacy"), 99
        )



class TestPersistenceToggle(unittest.TestCase):
    """Promote/demote = toggling ``_storedVarNames`` membership without
    touching the live value (Variables-tab checkbox / set_variable_persistent)."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._common.storedvars import stored_var_store

        stored_var_store.evict_all()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="toggle_test")
        self.name = self.node.get_name()

    def _saved(self):
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode._common.io import serialization as ser

        svs.flush_all()
        raw = _plug_raw(self.name)
        return ser.decode_stored_vars(raw) if raw else {}

    def test_promote_makes_session_var_saved(self):
        from mpynode._common.storedvars.stored_vars_api import (
            set_variable_persistent,
            get_variable_names,
        )

        self.node.add_output_attr("out", "float")
        self.node.set_compute_expression("self.foo = [1, 2, 3]\nself.out = 1.0\n")
        mc.getAttr(self.name + ".out")                         # compute -> ephemeral self.foo
        self.assertNotIn("foo", self._saved())                 # session-only
        set_variable_persistent(self.name, "foo", True)        # promote
        self.assertIn("foo", get_variable_names(self.name))
        self.assertEqual(self._saved().get("foo"), [1, 2, 3])  # now saved

    def test_demote_keeps_value_but_unsaves(self):
        from mpynode._common.storedvars.stored_vars_api import set_variable_persistent

        self.node.add_variable("bar", 0)
        self.node.set_variable("bar", 5)
        self.assertEqual(self._saved().get("bar"), 5)     # persistent
        set_variable_persistent(self.name, "bar", False)  # demote
        # value still live this session...
        self.assertEqual(self.node.get_variables().get("bar"), 5)
        # ...but no longer serialized
        self.assertNotIn("bar", self._saved())

    def test_toggle_is_undoable(self):
        from mpynode._base.commands import _SetPersistentCommand, run_undoable
        from mpynode._common.storedvars.stored_vars_api import get_variable_names

        self.node.add_output_attr("out", "float")
        self.node.set_compute_expression("self.foo = 1\nself.out = 1.0\n")
        mc.getAttr(self.name + ".out")
        run_undoable(_SetPersistentCommand(self.node, "foo", True))
        self.assertIn("foo", get_variable_names(self.name))
        mc.undo()
        self.assertNotIn("foo", get_variable_names(self.name))
        mc.redo()
        self.assertIn("foo", get_variable_names(self.name))


# ===================== from test_decode_cache.py =====================
import unittest

from mpynode._common.io import serialization as ser


class TestDecodeCache(unittest.TestCase):
    def setUp(self):
        ser.clear_stored_var_decode_cache()

    def test_equivalence_with_uncached(self):
        blob = ser.encode_stored_vars({"a": 1, "b": [2, 3], "c": "hi"})
        self.assertEqual(ser.decode_cached(blob), ser.decode_stored_vars(blob))

    def test_empty_returns_dict_not_cached(self):
        self.assertEqual(ser.decode_cached(""), {})
        self.assertEqual(ser.decode_cached("None"), {})
        self.assertEqual(ser._stored_var_decode_cache_info()[0], 0)

    def test_cache_hit_skips_unpickle(self):
        import pickle

        blob = ser.encode_stored_vars({"data": list(range(100))})
        ser.decode_cached(blob)  # warm (one real decode)
        calls      = {"n": 0}
        real_loads = pickle.loads

        def counting_loads(*a, **k):
            calls["n"] += 1
            return real_loads(*a, **k)

        pickle.loads = counting_loads
        try:
            for _ in range(50):  # simulate 50 frames, same blob
                got = ser.decode_cached(blob)
        finally:
            pickle.loads = real_loads
        self.assertEqual(got, {"data": list(range(100))})
        self.assertEqual(calls["n"], 0, "cache hits must not re-unpickle")

    def test_changed_blob_is_a_miss(self):
        b1 = ser.encode_stored_vars({"x": 1})
        b2 = ser.encode_stored_vars({"x": 2})
        self.assertEqual(ser.decode_cached(b1), {"x": 1})
        self.assertEqual(ser.decode_cached(b2), {"x": 2})  # different string

    def test_container_isolation(self):
        """Mutating the returned dict's container must not corrupt the
        cache (shallow-copy handout)."""
        blob           = ser.encode_stored_vars({"a": 1})
        d1             = ser.decode_cached(blob)
        d1["injected"] = 999                      # mutate the handed-out container
        d2             = ser.decode_cached(blob)  # same blob -> cache hit
        self.assertNotIn("injected", d2)
        self.assertEqual(d2, {"a": 1})

    def test_byte_budget_eviction(self):
        # Shrink the budget, push enough distinct blobs to force eviction.
        orig_max                    = ser._DECODE_CACHE_MAX_BYTES
        ser._DECODE_CACHE_MAX_BYTES = 2000  # tiny
        try:
            ser.clear_stored_var_decode_cache()
            for i in range(50):
                blob = ser.encode_stored_vars({"k": "x" * 200, "i": i})
                ser.decode_cached(blob)
            count, total = ser._stored_var_decode_cache_info()
            self.assertLessEqual(total, ser._DECODE_CACHE_MAX_BYTES * 2,
                                 "cache bytes should stay roughly bounded")
            self.assertGreater(count, 0)
        finally:
            ser._DECODE_CACHE_MAX_BYTES = orig_max
            ser.clear_stored_var_decode_cache()

    def test_oversized_single_entry_not_infinite_loop(self):
        orig_max                    = ser._DECODE_CACHE_MAX_BYTES
        ser._DECODE_CACHE_MAX_BYTES = 10  # smaller than any real blob
        try:
            ser.clear_stored_var_decode_cache()
            blob = ser.encode_stored_vars({"big": "y" * 5000})
            got  = ser.decode_cached(blob)  # must return, not hang
            self.assertEqual(got, {"big": "y" * 5000})
            self.assertEqual(ser._stored_var_decode_cache_info()[0], 1)
        finally:
            ser._DECODE_CACHE_MAX_BYTES = orig_max
            ser.clear_stored_var_decode_cache()

    def test_clear_empties_cache(self):
        ser.decode_cached(ser.encode_stored_vars({"a": 1}))
        self.assertGreater(ser._stored_var_decode_cache_info()[0], 0)
        ser.clear_stored_var_decode_cache()
        self.assertEqual(ser._stored_var_decode_cache_info(), (0, 0))

    def test_numpy_value_roundtrips(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        arr  = np.arange(12).reshape(3, 4)
        blob = ser.encode_stored_vars({"arr": arr})
        got  = ser.decode_cached(blob)
        self.assertTrue(np.array_equal(got["arr"], arr))


class TestStoredVarsApiRoutesThroughStore(unittest.TestCase):
    """Tier-2: stored_vars_api no longer decodes the plug directly -- it
    reads/writes the authoritative in-memory store (which hands out
    copies), so it must reference ``stored_var_store`` and must NOT touch
    the read-only decode cache or decode the plug itself."""

    def test_stored_vars_api_routes_through_store(self):
        import inspect
        from mpynode._common.storedvars import stored_vars_api

        src = inspect.getsource(stored_vars_api)
        self.assertIn("stored_var_store", src)
        self.assertNotIn("decode_cached", src)
        self.assertNotIn("decode_stored_vars", src)


class TestStoredVarCodec(unittest.TestCase):
    """zlib/lzma/none codecs round-trip, and legacy (codec-less) blobs
    still decode."""

    def _rt(self, comp):
        from mpynode._common.io import serialization as ser

        data = {"counter": 7, "nums": list(range(500)), "tag": "abc"}
        blob = ser.encode_stored_vars(data, compression=comp)
        return ser.decode_stored_vars(blob), blob

    def test_zlib_roundtrip(self):
        out, _ = self._rt("zlib")
        self.assertEqual(out["counter"], 7)
        self.assertEqual(out["nums"], list(range(500)))

    def test_lzma_roundtrip(self):
        out, _ = self._rt("lzma")
        self.assertEqual(out["nums"], list(range(500)))

    def test_none_roundtrip(self):
        out, _ = self._rt("none")
        self.assertEqual(out["nums"], list(range(500)))

    def test_compression_shrinks_compressible_data(self):
        _, z = self._rt("zlib")
        _, n = self._rt("none")
        self.assertLess(len(z), len(n))  # repetitive range() compresses

    def test_default_is_zlib(self):
        from mpynode._common.io import serialization as ser
        import json

        blob = ser.encode_stored_vars({"a": 1})
        self.assertEqual(json.loads(blob).get("codec"), "zlib")

    def test_legacy_protocol5_blob_still_decodes(self):
        # Hand-build a pre-compression (protocol 5, no codec) blob and
        # confirm the new decoder reads it (treats absent codec as raw).
        import base64, json, pickle
        from mpynode._common.io import serialization as ser

        raw = pickle.dumps({"legacy": [1, 2, 3]}, protocol=5)
        legacy = json.dumps(
            {"protocol": 5, "data_b64": base64.b64encode(raw).decode("ascii")}
        )
        self.assertEqual(ser.decode_stored_vars(legacy), {"legacy": [1, 2, 3]})


class TestKeyedTwoStep(unittest.TestCase):
    """Two-step keyed format: per-value pickle isolation + single
    compress pass + graceful partial decode."""

    def test_format_marker_is_keyed(self):
        import json
        from mpynode._common.io import serialization as ser

        w = json.loads(ser.encode_stored_vars({"a": 1, "b": [1, 2]}))
        self.assertEqual(w.get("protocol"), 8)
        self.assertEqual(w.get("format"),   "keyed2")
        self.assertEqual(w.get("codec"),    "zlib")
        # all-safe values carry no pickle -> opening the file needs no trust prompt
        self.assertFalse(w.get("has_pickle"))

    def test_resilient_drops_unpicklable_value(self):
        from mpynode._common.io import serialization as ser

        bad = lambda x: x  # noqa: E731
        blob, dropped = ser.encode_stored_vars_resilient({"ok": 5, "bad": bad})
        self.assertEqual(dropped, ["bad"])
        out = ser.decode_stored_vars(blob)
        self.assertEqual(out, {"ok": 5})

    def test_graceful_partial_decode_reports_failures(self):
        # Hand-build a keyed blob whose 'bad' entry isn't a valid pickle,
        # simulating a value whose class can't be reconstructed on load.
        import base64, json, pickle, zlib
        from mpynode._common.io import serialization as ser

        inner = {"good": pickle.dumps(42, protocol=5), "bad": b"not-a-pickle"}
        outer = zlib.compress(pickle.dumps(inner, protocol=5), 6)
        blob = json.dumps({
            "protocol": 7, "format": "keyed", "codec": "zlib",
            "data_b64": base64.b64encode(outer).decode("ascii"),
        })
        values, failures = ser.decode_stored_vars_detailed(blob)
        self.assertEqual(values, {"good": 42})  # salvaged the good one
        self.assertIn("bad", failures)          # reported the bad one
        # plain decode returns the partial dict, no raise
        self.assertEqual(ser.decode_stored_vars(blob), {"good": 42})

    def test_lzma_keyed_roundtrip(self):
        from mpynode._common.io import serialization as ser

        blob = ser.encode_stored_vars({"x": list(range(300))}, compression="lzma")
        self.assertEqual(ser.decode_stored_vars(blob)["x"], list(range(300)))

    def test_clean_decode_has_no_failures(self):
        from mpynode._common.io import serialization as ser

        blob = ser.encode_stored_vars({"a": 1, "b": "two"})
        values, failures = ser.decode_stored_vars_detailed(blob)
        self.assertEqual(values, {"a": 1, "b": "two"})
        self.assertEqual(failures, {})


# ===================== from test_phase11.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase11():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


class TestStoredVarsWrapperAPI(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_empty_initial(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="emptyVars")
        self.assertEqual(n.get_variable_names(), [])
        self.assertEqual(n.get_variables(), {})

    def test_add_stored_var(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="addVar")
        n.add_variable("counter", 0)
        n.add_variable("history", [])

        names = n.get_variable_names()
        self.assertIn("counter", names)
        self.assertIn("history", names)

        data = n.get_variables()
        self.assertEqual(data["counter"], 0)
        self.assertEqual(data["history"], [])

    def test_set_stored_vars(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="setVars")
        n.set_variables({"x": 5, "y": [1, 2, 3], "z": "hello"})

        data = n.get_variables()
        self.assertEqual(data["x"], 5)
        self.assertEqual(data["y"], [1, 2, 3])
        self.assertEqual(data["z"], "hello")

    def test_remove_stored_var(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="rmVar")
        n.add_variable("a", 1)
        n.add_variable("b", 2)
        n.remove_variable("a")

        names = n.get_variable_names()
        self.assertNotIn("a", names)
        self.assertIn("b", names)
        data = n.get_variables()
        self.assertNotIn("a", data)

    def test_clear_stored_vars(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="clearVars")
        n.add_variable("a", 1)
        n.add_variable("b", 2)
        n.clear_variables()

        self.assertEqual(n.get_variable_names(), [])
        self.assertEqual(n.get_variables(), {})


class TestStoredVarsExpression(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_expression_increments_stored_counter(self):
        """Per-compute counter: each query of the output should
        increment the stored counter."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="counterNode")
        n.add_variable("counter", 0)
        n.add_input_attr("trigger", "float")
        n.add_output_attr("out", "int")
        n.set_compute_expression("""
self.counter = self.counter + 1
out = self.counter
""")

        cube = mc.polyCube(name="counterCube")[0]
        mc.connectAttr(n.get_name() + ".out", cube + ".translateX", force=True)

        # First eval
        mc.setAttr(n.get_name() + ".trigger", 1.0)
        mc.xform(cube, q=True, ws=True, t=True)
        # The counter is now 1; check stored value.
        self.assertEqual(n.get_variables()["counter"], 1)

        # Trigger another eval
        mc.setAttr(n.get_name() + ".trigger", 2.0)
        mc.xform(cube, q=True, ws=True, t=True)
        self.assertEqual(n.get_variables()["counter"], 2)

    def test_stored_var_persists_across_save_load(self):
        """Stored var should survive.ma save + reload."""
        import os
        import tempfile

        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="persistNode")
        n.add_variable("history", [10, 20, 30])

        # Save the scene.
        tmp_path = tempfile.mktemp(suffix=".ma")
        mc.file(rename=tmp_path)
        mc.file(save=True, type="mayaAscii")

        # Reload.
        mc.file(new=True, force=True)
        mc.file(tmp_path, open=True, force=True, ignoreVersion=True)

        # Get stored vars from the loaded node.
        loaded = MPyNode("persistNode")
        self.assertEqual(loaded.get_variables()["history"], [10, 20, 30])

        # Cleanup.
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestNDVariablesWidget(unittest.TestCase):
    def test_widget_classes_present(self):
        from mpynode.ui.mpynode_designer import NDVariablesWidget

        self.assertTrue(hasattr(NDVariablesWidget, "setPyNode"))
        self.assertTrue(hasattr(NDVariablesWidget, "refresh"))

    def test_widget_uses_get_stored_vars(self):
        """The User/Session sections read stored vars through
        get_variables (not the plug directly). The call now lives in
        the shared ``_stored_data_and_registry`` helper that both
        sections delegate to."""
        import inspect

        from mpynode.ui.widgets.variables import NDVariablesWidget

        src = inspect.getsource(NDVariablesWidget._stored_data_and_registry)
        self.assertIn("get_variables", src)


# ===========================================================================
# set_variable(persistent=None): writing a VALUE must not change a LIFETIME
# ===========================================================================


class TestSetVariableRespectsExistingPersistence(unittest.TestCase):
    """``persistent`` defaults to None = leave the status alone.

    Writing a value used to PROMOTE the var to persistent (the old default was
    True), so ``n.set_variable("scratch", v)`` on a session-only var silently
    started saving it into the scene. Explicit True/False still set the status.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="pnone")
        self.name = self.node.get_name()

    def test_update_keeps_a_temporary_var_temporary(self):
        self.node.add_variable("scratch", 1, persistent=False)
        self.node.set_variable("scratch", 2)
        self.assertEqual(self.node.get_variables()["scratch"], 2)
        self.assertFalse(
            self.node.is_variable_persistent("scratch"),
            "writing a value PROMOTED a Temporary var to Persistent")

    def test_update_keeps_a_persistent_var_persistent(self):
        self.node.add_variable("keep", 1)          # declared persistent
        self.node.set_variable("keep", 2)
        self.assertEqual(self.node.get_variables()["keep"], 2)
        self.assertTrue(
            self.node.is_variable_persistent("keep"),
            "writing a value DEMOTED a Persistent var to Temporary")

    def test_a_new_var_is_temporary(self):
        self.node.set_variable("fresh", 1)
        self.assertFalse(self.node.is_variable_persistent("fresh"))

    def test_explicit_true_still_promotes(self):
        self.node.set_variable("up", 1)
        self.assertFalse(self.node.is_variable_persistent("up"))
        self.node.set_variable("up", 2, persistent=True)
        self.assertTrue(self.node.is_variable_persistent("up"))

    def test_explicit_false_still_demotes(self):
        self.node.add_variable("down", 1)
        self.assertTrue(self.node.is_variable_persistent("down"))
        self.node.set_variable("down", 2, persistent=False)
        self.assertFalse(self.node.is_variable_persistent("down"))

    def test_a_temporary_var_is_still_not_saved(self):
        """Non-vacuity: Temporary must actually stay out of the flush."""
        from mpynode._common.storedvars import stored_var_store as svs
        from mpynode._common.io import serialization as ser

        self.node.set_variable("scratch", 5)
        self.node.set_variable("kept", 6, persistent=True)
        svs.flush_all()
        saved = ser.decode_stored_vars(
            mc.getAttr(self.name + "._storedVarsData") or "")
        self.assertEqual(saved.get("kept"), 6)
        self.assertNotIn("scratch", saved)

    # The UI's inline value edit rides the same rule through
    # _SetStoredVarCommand -- see TestStoredVarPersistencePreservation.

    # -- .mpn must not launder Temporary back into Persistent -------------

    def test_mpn_roundtrip_keeps_a_temporary_only_node_temporary(self):
        """``deserialize_node`` reads an ABSENT ``persistent_vars`` key as
        "legacy payload, assume all persistent", so a node whose vars are ALL
        session-only has to serialize an explicit empty list."""
        from mpynode._common.io import mpn_io

        self.node.set_variable("scratch", 5)
        payload = mpn_io.serialize_node(self.node)
        self.assertEqual(payload.get("persistent_vars"), [])
        dst = mpn_io.deserialize_node(payload, name="pnone_mpn_dst")
        self.assertEqual(dst.get_variables().get("scratch"), 5)
        self.assertFalse(
            dst.is_variable_persistent("scratch"),
            "the .mpn round-trip PROMOTED a session-only var to persistent")

    def test_a_node_with_no_stored_vars_omits_the_tag_list(self):
        """Plain-node payloads stay byte-identical (the key is additive)."""
        from mpynode._common.io import mpn_io

        payload = mpn_io.serialize_node(self.node)
        self.assertNotIn("persistent_vars", payload)


def setUpModule():
    _setUpModule__phase19()
    _setUpModule__stored_var_store()
    _setUpModule__phase11()


if __name__ == "__main__":
    import unittest
    unittest.main()
