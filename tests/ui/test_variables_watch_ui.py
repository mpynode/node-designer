"""Variables tab sections + Watch tab widget UI

Consolidated from: test_variables_sections.py, test_watch_size_column.py, test_watch_python_decode.py, test_watch_live_suspend.py, test_watch_no_force_eval.py.
"""

from __future__ import annotations

# ===================== from test_variables_sections.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-sections-test"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__variables_sections():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestVariablesSections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._common.storedvars import stored_var_store

        stored_var_store.evict_all()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="sections_test")
        self.name = self.node.get_name()
        self.node.add_variable("zeta", 1)            # persistent
        self.node.add_output_attr("out", "float")
        self.node.set_compute_expression("self.alpha = 5\nself.out = 1.0\n")
        mc.getAttr(self.name + ".out")                 # compute -> temporary

    def _rows(self, section):
        from mpynode.ui.widgets.variables import NDVariableTreeItem

        out = []
        for i in range(section.childCount()):
            ch = section.child(i)
            if isinstance(ch, NDVariableTreeItem):
                out.append(ch)
        return out

    def _build(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget

        w = NDVariablesWidget()
        w._py_node = self.node
        w.refresh()
        return w

    def test_vars_split_into_correct_sections(self):
        w = self._build()
        persistent = [r.var_name for r in self._rows(w._persistent_section)]
        temporary = [r.var_name for r in self._rows(w._temporary_section)]
        self.assertEqual(persistent, ["zeta"])
        self.assertEqual(temporary, ["alpha"])

    def test_underscore_session_var_hidden_from_temporary(self):
        # Underscore-prefixed vars are private scratch (e.g. the example's
        # self._player QMediaPlayer) -- they must not clutter the inspector.
        from mpynode._common.storedvars import stored_var_store

        stored_var_store.set_var(self.name, "_player", "<player>")
        w = self._build()
        temp = [r.var_name for r in self._rows(w._temporary_section)]
        self.assertIn("alpha", temp)
        self.assertNotIn("_player", temp)

    def test_underscore_session_var_hidden_from_watch(self):
        from mpynode._common.storedvars import stored_var_store
        from mpynode.ui.widgets.watch import NDWatchWidget

        stored_var_store.set_var(self.name, "_player", "<player>")
        w = NDWatchWidget()
        w.setPyNode(self.node)
        w._watch_cb.setChecked(True)   # Watch is opt-in
        temp = self._watch_sections(w).get("Temporary", [])
        self.assertIn("alpha", temp)
        self.assertNotIn("_player", temp)

    def test_edit_gating_by_section(self):
        from mpynode.ui.qt_wrapper import Qt

        w = self._build()
        prow = self._rows(w._persistent_section)[0]
        trow = self._rows(w._temporary_section)[0]
        self.assertTrue(prow.flags() & Qt.ItemIsEditable)    # persistent editable
        self.assertFalse(trow.flags() & Qt.ItemIsEditable)   # temporary locked

    def test_promote_moves_to_persistent_section(self):
        from mpynode._common.storedvars.stored_vars_api import get_variable_names

        w = self._build()
        alpha = self._rows(w._temporary_section)[0]
        self.assertEqual(alpha.var_name, "alpha")
        w._toggle_persistent(alpha, True)  # promote (right-click target)
        self.assertIn("alpha", get_variable_names(self.name))
        persistent = [r.var_name for r in self._rows(w._persistent_section)]
        temporary = [r.var_name for r in self._rows(w._temporary_section)]
        self.assertIn("alpha", persistent)
        self.assertNotIn("alpha", temporary)

    def test_demote_moves_to_temporary_section(self):
        from mpynode._common.storedvars.stored_vars_api import get_variable_names

        w = self._build()
        zeta = self._rows(w._persistent_section)[0]
        w._toggle_persistent(zeta, False)  # demote
        self.assertNotIn("zeta", get_variable_names(self.name))
        temporary = [r.var_name for r in self._rows(w._temporary_section)]
        self.assertIn("zeta", temporary)


    def test_temporary_value_shown_without_any_persistent(self):
        # Regression: a long placeholder in the empty Persistent section used
        # to widen col 0 via ResizeToContents and hide the Value column for
        # Temporary rows. Demote zeta so no persistent vars remain.
        self.node.set_variable_persistent("zeta", False)
        w = self._build()
        rows = {r.var_name: r for r in self._rows(w._temporary_section)}
        self.assertIn("alpha", rows)
        self.assertIn("zeta", rows)
        self.assertEqual(rows["alpha"].text(2), repr(5))
        # the empty Persistent section's placeholder must span all columns
        ph = w._persistent_section.child(0)
        self.assertTrue(ph.isFirstColumnSpanned())

    def test_section_headers_span_all_columns(self):
        # The Properties/Internal (INTERNAL_API_SLOTS) section moved to the
        # Framework tab; the Variables tab now renders only the Persistent +
        # Temporary user-var sections.
        w = self._build()
        for sec in (
            w._persistent_section,
            w._temporary_section,
        ):
            self.assertTrue(sec.isFirstColumnSpanned())

    def test_save_refreshes_variables_tab(self):
        # _on_tab_saved (F5 handler) must refresh the Variables tab so a
        # freshly-written self.X var appears without a manual refresh.
        import inspect

        try:
            from mpynode.ui.mpynode_designer import NDMainWindow
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"designer import unavailable: {exc}")
        src = inspect.getsource(NDMainWindow._on_tab_saved)
        self.assertIn("_variables_widget.refresh", src)


    @staticmethod
    def _flash_rgba(item):
        c = item.background(0).color()
        return (c.red(), c.green(), c.blue(), c.alpha())

    def test_initial_build_does_not_flash(self):
        # First time a node is shown (node switch), nothing should flash.
        w = self._build()
        for sec in (w._persistent_section, w._temporary_section):
            for r in self._rows(sec):
                self.assertNotEqual(self._flash_rgba(r), (255, 204, 0, 110))

    def test_new_var_is_selected_and_flashed_on_same_node_refresh(self):
        w = self._build()  # initial: knows zeta, alpha (no flash)
        # Write a NEW self.X var and compute so it lands in the store.
        self.node.set_compute_expression(
            "self.alpha = 5\nself.beta = 2\nself.out = 1.0\n"
        )
        mc.getAttr(self.name + ".out")
        w.refresh()  # same node -> beta is new -> selected + flashed
        cur = w._tree.currentItem()
        self.assertIsNotNone(cur)
        self.assertEqual(getattr(cur, "var_name", None), "beta")
        # flash background applied (the async clear timer hasn't run in
        # this headless loop, so it's still set).
        self.assertEqual(self._flash_rgba(cur), (255, 204, 0, 110))
        # a pre-existing var is NOT flashed
        others = {
            r.var_name: r
            for r in self._rows(w._temporary_section)
        }
        if "alpha" in others:
            self.assertNotEqual(self._flash_rgba(others["alpha"]), (255, 204, 0, 110))


    def test_dir_column_not_editable(self):
        # The blank Dir column (col 1) must not open an editor, even on
        # persistent rows (which are otherwise ItemIsEditable).
        w = self._build()
        delegate = w._tree.itemDelegateForColumn(1)
        self.assertIsNotNone(delegate)
        self.assertIsNone(delegate.createEditor(None, None, None))


    def test_delete_removes_temporary_and_persistent(self):
        import mpynode.ui.widgets.variables as vmod
        from mpynode._common.storedvars.stored_vars_api import get_variable_names

        orig = vmod.confirm_delete_node
        vmod.confirm_delete_node = lambda *a, **k: True
        try:
            w = self._build()
            # delete a Temporary var
            w._delete_vars(["alpha"])
            self.assertNotIn("alpha", self.node.get_variables())
            # delete a Persistent var (clears value + unregisters)
            w._delete_vars(["zeta"])
            self.assertNotIn("zeta", self.node.get_variables())
            self.assertNotIn("zeta", get_variable_names(self.name))
        finally:
            vmod.confirm_delete_node = orig

    def test_context_menu_offers_delete(self):
        import inspect
        from mpynode.ui.widgets.variables import NDVariablesWidget

        src = inspect.getsource(NDVariablesWidget._on_context_menu)
        self.assertIn("Delete Variable", src)
        self.assertIn("_delete_vars", src)


    def test_numpy_value_formatted_and_top_aligned(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        from mpynode.ui.qt_wrapper import Qt
        from mpynode.ui.widgets.watch import _format_value

        arr = np.arange(12).reshape(3, 4).astype(float)
        self.node.set_variable("mat", arr, persistent=True)
        w = self._build()
        rows = {r.var_name: r for r in self._rows(w._persistent_section)}
        self.assertIn("mat", rows)
        item = rows["mat"]
        # value uses the shared numpy-aware formatter (not bare repr)
        self.assertEqual(item.text(2), _format_value(arr))
        self.assertIn("array(", item.text(2))
        # columns top-aligned (name lines up with first row of the array)
        self.assertTrue(item.textAlignment(0) & Qt.AlignTop)
        self.assertTrue(item.textAlignment(2) & Qt.AlignTop)

    def test_value_column_monospace(self):
        from mpynode.ui.qt_wrapper import QFont

        w = self._build()
        rows = self._rows(w._persistent_section)
        self.assertTrue(rows)
        self.assertEqual(rows[0].font(2).styleHint(), QFont.Monospace)

    def test_delete_dialog_wording_is_variable(self):
        import inspect
        from mpynode.ui.widgets.variables import NDVariablesWidget
        from mpynode.ui.dialogs import confirm

        src = inspect.getsource(NDVariablesWidget._delete_vars)
        self.assertIn('entity="variable"', src)
        csrc = inspect.getsource(confirm.confirm_delete_node)
        self.assertIn("entity", csrc)
        self.assertNotIn('"Delete node', csrc)

    def test_watch_rows_top_aligned_source(self):
        import inspect
        from mpynode.ui.widgets.watch import NDWatchWidget

        # The per-row top-alignment loop now lives in _sync_group_children
        # (the canonical row-builder), not _populate_tree.
        src = inspect.getsource(NDWatchWidget._sync_group_children)
        self.assertIn("AlignTop", src)


    def test_round_pref_controls_display_precision(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        val = np.array([1.123456789012345])
        try:
            preferences.set_pref("display_round_enabled", True)
            preferences.set_pref("display_round_digits", 8)
            out8 = _format_value(val)
            preferences.set_pref("display_round_digits", 2)
            out2 = _format_value(val)
            preferences.set_pref("display_round_enabled", False)
            outfull = _format_value(val)
        finally:
            preferences.set_pref("display_round_enabled", True)
            preferences.set_pref("display_round_digits", 8)
        self.assertIn("1.12", out2)
        self.assertIn("1.1234567", out8)       # 8 decimals
        self.assertIn("1.123456789", outfull)  # full precision, no rounding
        self.assertNotEqual(out2, out8)

    def test_add_temporary_vs_persistent_commands(self):
        from mpynode._base.commands import (
            _AddStoredVarCommand,
            _AddTemporaryVarCommand,
            run_undoable,
        )
        from mpynode._common.storedvars.stored_vars_api import get_variable_names

        run_undoable(_AddStoredVarCommand(self.node, "p_new", 1))
        run_undoable(_AddTemporaryVarCommand(self.node, "t_new", 2))
        names = get_variable_names(self.name)
        self.assertIn("p_new", names)      # persistent -> registered
        self.assertNotIn("t_new", names)   # temporary -> NOT registered
        data = self.node.get_variables()
        self.assertEqual(data.get("p_new"), 1)
        self.assertEqual(data.get("t_new"), 2)  # still live in the store

    def test_add_temporary_is_undoable(self):
        from mpynode._base.commands import _AddTemporaryVarCommand, run_undoable

        run_undoable(_AddTemporaryVarCommand(self.node, "t_undo", 9))
        self.assertEqual(self.node.get_variables().get("t_undo"), 9)
        mc.undo()
        self.assertNotIn("t_undo", self.node.get_variables())
        mc.redo()
        self.assertEqual(self.node.get_variables().get("t_undo"), 9)

    def test_rename_delegate_overlaps_name_column(self):
        import inspect
        from mpynode.ui.widgets.variables import NDVariablesWidget

        src = inspect.getsource(NDVariablesWidget.__init__)
        self.assertIn("setItemDelegateForColumn(0", src)
        self.assertIn("updateEditorGeometry", src)

    def test_add_dialog_has_persistent_checkbox_default_on(self):
        import inspect
        from mpynode.ui.widgets.variables import NDVariablesWidget

        src = inspect.getsource(NDVariablesWidget._prompt_new_var)
        self.assertIn("Persistent", src)
        self.assertIn("setChecked(True)", src)


    def test_pref_change_live_updates_variables(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        from mpynode.ui import preferences

        self.node.set_variable(
            "mat", np.array([1.123456789012345]), persistent=True)
        preferences.set_pref("display_round_enabled", True)
        preferences.set_pref("display_round_digits", 8)
        w = self._build()
        text8 = {
            r.var_name: r for r in self._rows(w._persistent_section)
        }["mat"].text(2)
        try:
            # Changing the pref must re-render the open widget with NO
            # manual refresh (listener fires on set_pref).
            preferences.set_pref("display_round_digits", 2)
            text2 = {
                r.var_name: r for r in self._rows(w._persistent_section)
            }["mat"].text(2)
        finally:
            preferences.set_pref("display_round_enabled", True)
            preferences.set_pref("display_round_digits", 8)
        self.assertNotEqual(text8, text2)
        self.assertIn("1.12", text2)

    def test_widgets_register_pref_listener(self):
        import inspect
        from mpynode.ui.widgets.variables import NDVariablesWidget
        from mpynode.ui.widgets.watch import NDWatchWidget

        for cls in (NDVariablesWidget, NDWatchWidget):
            src = inspect.getsource(cls.__init__)
            self.assertIn("register_change_listener", src)


    def test_toolbar_has_left_inset(self):
        from mpynode.ui.widgets.toolbar import NDToolBar
        from mpynode.ui.qt_wrapper import QWidget

        parent = QWidget()
        tb = NDToolBar(
            parent,
            on_new_node=lambda nt: None,
            on_save_node=lambda: None,
            on_save_all=lambda: None,
        )
        self.assertTrue(hasattr(tb, "_left_spacer"))
        self.assertGreater(tb._left_spacer.width(), 0)
        tb.set_left_inset(13)
        self.assertEqual(tb._left_spacer.width(), 13)


    @staticmethod
    def _watch_sections(w):
        t = w._tree
        out = {}
        for i in range(t.topLevelItemCount()):
            h = t.topLevelItem(i)
            out[h.text(0)] = [
                h.child(j).text(0) for j in range(h.childCount())
            ]
        return out

    def test_watch_tab_groups_store_vars(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        self.node.add_variable("p_persist", 1)        # persistent
        self.node.add_output_attr("wout", "float")
        self.node.set_compute_expression("self.t_temp = 7\nself.wout = 1.0\n")
        mc.getAttr(self.name + ".wout")                 # compute -> t_temp (temporary)

        w = NDWatchWidget()
        w.setPyNode(self.node)
        # Watch is opt-in; stored vars only populate once Enable Watch is on.
        w._watch_cb.setChecked(True)
        secs = self._watch_sections(w)
        self.assertIn("Persistent", secs)
        self.assertIn("Temporary", secs)
        self.assertIn("p_persist", secs["Persistent"])
        self.assertIn("t_temp", secs["Temporary"])

        # Scope toggle: hide Persistent -> its section disappears.
        w._show_persist_cb.setChecked(False)
        secs2 = self._watch_sections(w)
        self.assertNotIn("Persistent", secs2)
        self.assertIn("Temporary", secs2)

    def test_watch_tab_shows_io_when_capture_disabled(self):
        # Regression: Inputs / Outputs are live plug values, NOT watch
        # captures, so they must appear even when "Enable Watch" is OFF (only
        # Locals / Temporary / Persistent need capture). The io read used to
        # sit behind the enable gate, leaving the tab empty.
        from mpynode.ui.widgets.watch import NDWatchWidget
        from mpynode.wrappers._mpy_node import MPyNode

        io = MPyNode.create(name="ioCaptureOff")
        io.add_input_attr("gain", "float", default_value=2.0)
        io.add_output_attr("result", "float")
        io.set_compute_expression("self.result = self.gain * 2.0\n")
        nm = io.get_name()
        mc.setAttr(nm + ".gain", 3.0)
        mc.getAttr(nm + ".result")

        w = NDWatchWidget()
        w.setPyNode(io)                       # Watch capture left OFF (default)
        self.assertFalse(w._watch_cb.isChecked())
        secs = self._watch_sections(w)
        self.assertIn("Inputs", secs)
        self.assertIn("Outputs", secs)
        self.assertIn("gain", secs["Inputs"])
        self.assertIn("result", secs["Outputs"])
        # Locals / stored vars still require Enable Watch -> hidden when off.
        self.assertNotIn("Locals", secs)
        self.assertNotIn("Temporary", secs)
        self.assertNotIn("Persistent", secs)

    def test_watch_tab_scope_checkboxes_default_on(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        w = NDWatchWidget()
        for cb in (w._show_locals_cb, w._show_temp_cb, w._show_persist_cb):
            self.assertTrue(cb.isChecked())

    def test_variables_setpynode_disposes_waveform_player(self):
        # On a node switch the previous node's audio player + temp .wav must be
        # released, not abandoned.
        w = self._build()                 # variables widget, _py_node = self.node

        class _Spy:
            def __init__(self):
                self.disposed = False

            def dispose(self):
                self.disposed = True

        spy = _Spy()
        w._waveform_player = spy
        w.setPyNode(None)                 # node change -> dispose old player
        self.assertTrue(spy.disposed)
        # Keep the per-tab singleton (disposed = resources released, but the
        # SAME wrapper) so surviving cells never point at a replaced player.
        self.assertIs(w._waveform_player, spy)

    def test_watch_setpynode_disposes_waveform_player(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        w = NDWatchWidget()
        w.setPyNode(self.node)

        class _Spy:
            def __init__(self):
                self.disposed = False

            def dispose(self):
                self.disposed = True

        spy = _Spy()
        w._waveform_player = spy
        w.setPyNode(None)
        self.assertTrue(spy.disposed)
        self.assertIs(w._waveform_player, spy)


# ===================== from test_watch_size_column.py =====================
import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _setUpModule__watch_size_column():
    standalone_init()


class TestFormatValueLabel(unittest.TestCase):
    """A collapsed stand-in prints bare -- quoting it would say "str", which
    is exactly what the Type column is there to deny."""

    def test_a_collapsed_label_is_not_quoted(self):
        from mpynode._common.instrumentation.watch import WatchLabel
        from mpynode.ui.widgets.watch import _format_value

        self.assertEqual(
            _format_value(WatchLabel('Mesh("pSphereShape1")', "Mesh")),
            'Mesh("pSphereShape1")')
        self.assertEqual(
            _format_value(WatchLabel("<mesh>", "Mesh")), "<mesh>")

    def test_a_real_string_keeps_its_quotes(self):
        # The quoting default must survive: it is the only thing separating
        # the string "5" from the number 5, and it makes stray whitespace
        # visible.
        from mpynode.ui.widgets.watch import _format_value

        self.assertEqual(_format_value("5"), "'5'")
        self.assertEqual(_format_value(" pad "), "' pad '")

    def test_every_label_only_type_renders_the_same_way(self):
        # Not just Mesh: the collapse dispatches on MODULE, so one class from
        # each of the three label-only modules is the real contract. All three
        # columns must agree -- bare value, true class, no phoney size.
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        from mpynode._api2.geometry import Mesh, NurbsCurve, NurbsSurface, UVSet
        from mpynode._api2.morph import Morph, MorphStack
        from mpynode._common.draw.draw_types import DrawCircle, DrawText
        from mpynode._common.instrumentation.watch import cap_watch_value
        from mpynode.ui.widgets.watch import (
            _format_size,
            _format_type,
            _format_value,
        )

        cases = [
            Mesh(points=np.zeros((4, 3)),
                 counts=np.array([4], dtype=np.int32),
                 indices=np.arange(4, dtype=np.int32)),
            NurbsCurve(points=np.zeros((8, 3))),
            NurbsSurface(points=np.zeros((4, 4, 3))),
            UVSet("map1", points=np.zeros((4, 2)),
                  counts=np.array([4], dtype=np.int64),
                  indices=np.arange(4, dtype=np.int64)),
            Morph(name="smile", offsets=np.zeros((5, 3)),
                  indices=np.arange(5, dtype=np.int64)),
            MorphStack(weight=np.zeros(2), names=["a", "b"]),
            DrawCircle(center=(0, 0, 0), radius=2.0),
            DrawText("hello"),
        ]
        for obj in cases:
            cls = type(obj).__name__
            label = cap_watch_value(obj)
            self.assertEqual(_format_type(label), cls)
            self.assertEqual(_format_size(label), "NA",
                             "%s should have no size" % cls)
            shown = _format_value(label)
            self.assertEqual(shown, repr(obj))
            self.assertFalse(shown.startswith("'"),
                             "%s value is quoted: %s" % (cls, shown))


class TestFormatSize(unittest.TestCase):
    def test_list_and_tuple_count(self):
        from mpynode.ui.widgets.watch import _format_size

        self.assertEqual(_format_size([1, 2, 3]), "3")
        self.assertEqual(_format_size((1, 2)), "2")
        self.assertEqual(_format_size([]), "0")

    def test_string_length(self):
        from mpynode.ui.widgets.watch import _format_size

        self.assertEqual(_format_size("hello"), "5")
        self.assertEqual(_format_size(""), "0")

    def test_dict_and_set_count(self):
        from mpynode.ui.widgets.watch import _format_size

        self.assertEqual(_format_size({"a": 1, "b": 2}), "2")
        self.assertEqual(_format_size({1, 2, 3}), "3")

    def test_bytes_count(self):
        from mpynode.ui.widgets.watch import _format_size

        self.assertEqual(_format_size(b"abcd"), "4")

    def test_numpy_shape(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        from mpynode.ui.widgets.watch import _format_size

        self.assertEqual(_format_size(np.zeros((3, 4))), "(3, 4)")
        self.assertEqual(_format_size(np.array([1, 2, 3])), "(3,)")

    def test_scalars_are_na(self):
        from mpynode.ui.widgets.watch import _format_size

        for v in (5, 3.14, None, True, False):
            self.assertEqual(_format_size(v), "NA",
                             "scalar %r should be NA" % (v,))

    def test_placeholder_markers_are_na(self):
        from mpynode.ui.widgets.watch import _format_size

        self.assertEqual(_format_size("<mesh>"), "NA")
        self.assertEqual(_format_size("<...too large to display: 64 KB>"), "NA")

    def test_a_collapsed_label_has_no_meaningful_size(self):
        # len() here would report the width of the LABEL TEXT (21 for
        # 'Mesh("pSphereShape1")'), which says nothing about the mesh -- and
        # the geometry is deliberately never read, so there is no count.
        from mpynode._common.instrumentation.watch import WatchLabel
        from mpynode.ui.widgets.watch import _format_size

        self.assertEqual(
            _format_size(WatchLabel('Mesh("pSphereShape1")', "Mesh")), "NA")

    def test_never_raises(self):
        from mpynode.ui.widgets.watch import _format_size

        class _Boom:
            def __len__(self):
                raise RuntimeError("boom")

        class _NoLen:
            pass

        self.assertEqual(_format_size(_Boom()), "NA")
        self.assertEqual(_format_size(_NoLen()), "NA")


class TestFormatType(unittest.TestCase):
    """The Type column must report the REAL runtime type -- numpy arrays as
    ``numpy.ndarray[<dtype>]`` (not ``list``), with the element dtype so
    int64 / float64 / float32 is visible at a glance."""

    def test_numpy_array_carries_dtype(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        from mpynode.ui.widgets.watch import _format_type

        self.assertEqual(
            _format_type(np.array([1, 2, 3], dtype=np.int64)),
            "numpy.ndarray[int64]")
        self.assertEqual(
            _format_type(np.array([1, 2, 3], dtype=np.int32)),
            "numpy.ndarray[int32]")
        self.assertEqual(
            _format_type(np.array([1.0, 2.0], dtype=np.float64)),
            "numpy.ndarray[float64]")
        self.assertEqual(
            _format_type(np.array([1.0, 2.0], dtype=np.float32)),
            "numpy.ndarray[float32]")
        self.assertEqual(
            _format_type(np.array([True, False])),
            "numpy.ndarray[bool]")

    def test_numpy_scalar_keeps_short_name(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        from mpynode.ui.widgets.watch import _format_type

        # A numpy scalar is NOT an ndarray -> plain module-qualified name.
        self.assertEqual(_format_type(np.float64(1.5)), "numpy.float64")

    def test_builtin_containers_unchanged(self):
        from mpynode.ui.widgets.watch import _format_type

        self.assertEqual(_format_type([1, 2, 3]), "list")
        self.assertEqual(_format_type((1, 2)), "tuple")
        self.assertEqual(_format_type({"a": 1}), "dict")
        self.assertEqual(_format_type("hi"), "str")

    def test_a_collapsed_label_reports_what_it_replaced(self):
        # WatchLabel IS a str, so the plain type() answer would be "str" for
        # every geometry plug and every API dataclass at once.
        from mpynode._common.instrumentation.watch import WatchLabel
        from mpynode.ui.widgets.watch import _format_type

        self.assertEqual(
            _format_type(WatchLabel('Mesh("pCubeShape1")', "Mesh")), "Mesh")
        self.assertEqual(
            _format_type(WatchLabel("<nurbsCurve>", "NurbsCurve")),
            "NurbsCurve")

    def test_never_raises(self):
        from mpynode.ui.widgets.watch import _format_type

        class _Boom:
            @property
            def dtype(self):
                raise RuntimeError("boom")

        # A non-ndarray object whose dtype explodes must not raise; it just
        # falls through to the (module-qualified) type name.
        label = _format_type(_Boom())
        self.assertIsInstance(label, str)
        self.assertTrue(label.endswith("_Boom"), label)


class TestWatchColumnWiring(unittest.TestCase):
    def test_header_has_size_as_fourth_column(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        src = inspect.getsource(NDWatchWidget.__init__)
        self.assertIn('"Size"', src)
        self.assertIn("setColumnCount(4)", src)

    def test_size_cell_populated_after_type(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        src = inspect.getsource(NDWatchWidget._sync_group_children)
        self.assertIn("_format_size", src)
        self.assertIn("setText(3", src)
        # The per-row alignment loop must widen to cover the new column.
        self.assertIn("range(4)", src)


# ===================== from test_watch_python_decode.py =====================
import base64
import os
import pickle

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import numpy as np

from tests._setup import standalone_init


def _setUpModule__watch_python_decode():
    standalone_init()


def _encode(obj) -> str:
    """Mirror the wire format read_plug_value writes/reads for python attrs."""
    return base64.b64encode(pickle.dumps(obj)).decode("ascii")


class TestDecodePythonString(unittest.TestCase):
    """The canonical raw-string decoder reused by the UI."""

    def setUp(self):
        from mpynode._common.io import trust

        trust.reset_for_new_scene()  # trusted authored scene

    def tearDown(self):
        # Restore a trusted default so this module's untrusted-scene cases
        # can't leak the global trust flag into later test modules.
        from mpynode._common.io import trust

        trust.reset_for_new_scene()

    def test_trusted_dict_roundtrips(self):
        from mpynode._api2.helpers import decode_python_string

        obj = {"a": 1, "pts": [1.0, 2.0, 3.0]}
        self.assertEqual(decode_python_string(_encode(obj)), obj)

    def test_empty_returns_none(self):
        from mpynode._api2.helpers import decode_python_string

        self.assertIsNone(decode_python_string(""))

    def test_untrusted_refuses(self):
        from mpynode._api2.helpers import decode_python_string
        from mpynode._common.io import trust

        trust.note_file_opened(False)  # untrusted scene
        self.assertIsNone(decode_python_string(_encode({"a": 1})))

    def test_corrupt_raises_valueerror(self):
        from mpynode._api2.helpers import decode_python_string

        with self.assertRaises(ValueError):
            decode_python_string("not-valid-base64-pickle!!!")


class TestWatchDecodeIOValue(unittest.TestCase):
    def setUp(self):
        from mpynode._common.io import trust

        trust.reset_for_new_scene()

    def tearDown(self):
        from mpynode._common.io import trust

        trust.reset_for_new_scene()

    def test_non_python_passthrough(self):
        from mpynode.ui.widgets.watch import decode_io_value

        self.assertEqual(decode_io_value(0.5, "float"), 0.5)
        self.assertEqual(decode_io_value("[1.0, 2.0]", "string"), "[1.0, 2.0]")

    def test_python_dict_decoded_with_real_type(self):
        from mpynode.ui.widgets.watch import decode_io_value, _format_type

        raw = _encode({"x": 1, "y": 2})
        decoded = decode_io_value(raw, "python")
        self.assertEqual(decoded, {"x": 1, "y": 2})
        self.assertEqual(_format_type(decoded), "dict")

    def test_python_numpy_decoded_with_real_type(self):
        from mpynode.ui.widgets.watch import decode_io_value, _format_type

        arr = np.arange(6, dtype=float).reshape(2, 3)
        decoded = decode_io_value(_encode(arr), "python")
        self.assertIsInstance(decoded, np.ndarray)
        np.testing.assert_array_equal(decoded, arr)
        # The type label now carries the element dtype (int64 vs float64 vs
        # float32 is the whole point of the column for numpy arrays).
        self.assertEqual(_format_type(decoded), "numpy.ndarray[float64]")

    def test_python_corrupt_falls_back_to_raw_string(self):
        """A corrupt payload must NOT raise on the live poll -- show the
        raw string instead."""
        from mpynode.ui.widgets.watch import decode_io_value

        raw = "garbage-not-pickle"
        self.assertEqual(decode_io_value(raw, "python"), raw)

    def test_python_untrusted_shows_raw_string(self):
        from mpynode.ui.widgets.watch import decode_io_value
        from mpynode._common.io import trust

        trust.note_file_opened(False)
        raw = _encode({"x": 1})
        self.assertEqual(decode_io_value(raw, "python"), raw)


class TestWatchDecodeCache(unittest.TestCase):
    def setUp(self):
        from mpynode._common.io import trust

        trust.reset_for_new_scene()

    def test_unchanged_blob_not_reunpickled(self):
        from mpynode.ui.widgets import watch as W

        calls = {"n": 0}
        # Count actual unpickles by spying on the canonical decoder.
        from mpynode._api2 import helpers

        orig = helpers.decode_python_string

        def _spy(raw):
            calls["n"] += 1
            return orig(raw)

        helpers.decode_python_string = _spy
        try:
            cache: dict = {}
            raw = _encode({"a": 1})
            v1 = W.decode_io_value_cached(cache, "python", raw, "python")
            v2 = W.decode_io_value_cached(cache, "python", raw, "python")
            self.assertEqual(v1, {"a": 1})
            self.assertEqual(v2, {"a": 1})
            self.assertEqual(calls["n"], 1, "unchanged blob should decode once")
        finally:
            helpers.decode_python_string = orig

    def test_changed_blob_is_redecoded_and_cache_does_not_grow(self):
        from mpynode.ui.widgets.watch import decode_io_value_cached

        cache: dict = {}
        a = decode_io_value_cached(cache, "python", _encode({"v": 1}), "python")
        b = decode_io_value_cached(cache, "python", _encode({"v": 2}), "python")
        self.assertEqual(a, {"v": 1})
        self.assertEqual(b, {"v": 2})
        # Only the latest blob per attr is retained.
        self.assertEqual(len(cache), 1)
        self.assertEqual(cache["python"][1], {"v": 2})


class TestEndToEndRealNode(unittest.TestCase):
    """Lock the wire-format contract: what a real mPyNode WRITES to a python
    output plug must be exactly what the Watch reader decodes back."""

    @classmethod
    def setUpClass(cls):
        import maya.cmds as mc

        if not mc.pluginInfo("mpynode_api2", q=True, loaded=True):
            mc.loadPlugin("mpynode_api2")

    def test_node_python_output_roundtrips_through_decode_io_value(self):
        import maya.cmds as mc

        from mpynode._common.io import trust
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.watch import decode_io_value, _format_type

        mc.file(new=True, force=True)
        trust.reset_for_new_scene()  # authored scene -> trusted

        node = MPyNode.create(name="pyEmitter")
        node.add_output_attr("cfg", "python")
        node.set_compute_expression(
            "import numpy as _np\n"
            "self.cfg = {'name': 'demo', 'pts': _np.arange(6).reshape(2, 3)}\n"
        )
        # Force compute, then read the RAW bus string off the plug exactly
        # like the Watch tab does.
        raw = mc.getAttr(node.get_name() + ".cfg")
        self.assertIsInstance(raw, str)

        decoded = decode_io_value(raw, "python")
        self.assertEqual(_format_type(decoded), "dict")
        self.assertEqual(decoded["name"], "demo")
        np.testing.assert_array_equal(
            decoded["pts"], np.arange(6).reshape(2, 3)
        )


# ===================== from test_watch_live_suspend.py =====================
import unittest


class _FakeTimer:
    def __init__(self):
        self._active = False

    def isActive(self):
        return self._active

    def start(self):
        self._active = True

    def stop(self):
        self._active = False


class _FakeWatch:
    """Minimal stand-in carrying just the attributes the timer methods touch.

    ``_start_live_timer`` / ``_stop_live_timer`` delegate to the REAL widget
    methods so the suspend guard inside them is exercised (not re-implemented).
    """

    def __init__(self):
        self._live_timer = _FakeTimer()
        self._refreshing = False
        self._py_node = object()  # truthy -> a node is "selected"
        self._live_suspended = False
        self._live_was_active = False
        self.refresh_calls = 0

    def refresh(self):
        self.refresh_calls += 1

    def isVisible(self):
        return True

    def _start_live_timer(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        NDWatchWidget._start_live_timer(self)

    def _stop_live_timer(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        NDWatchWidget._stop_live_timer(self)


class TestWatchLiveSuspend(unittest.TestCase):
    def setUp(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        self.W = NDWatchWidget
        self.f = _FakeWatch()

    def test_start_then_suspend_stops_timer(self):
        self.W._start_live_timer(self.f)
        self.assertTrue(self.f._live_timer.isActive())
        self.W.suspend_live(self.f)
        self.assertTrue(self.f._live_suspended)
        self.assertFalse(self.f._live_timer.isActive())

    def test_tick_during_suspend_does_not_refresh(self):
        self.W._start_live_timer(self.f)
        self.W.suspend_live(self.f)
        # A queued timer tick landing during the save window must no-op.
        self.W._on_live_tick(self.f)
        self.assertEqual(self.f.refresh_calls, 0)

    def test_start_is_a_noop_while_suspended(self):
        self.W.suspend_live(self.f)
        self.W._start_live_timer(self.f)
        self.assertFalse(self.f._live_timer.isActive())

    def test_resume_rearms_only_if_was_active(self):
        self.W._start_live_timer(self.f)  # active before save
        self.W.suspend_live(self.f)
        self.W.resume_live(self.f)
        self.assertFalse(self.f._live_suspended)
        self.assertTrue(self.f._live_timer.isActive())
        # And ticks refresh again post-resume.
        self.W._on_live_tick(self.f)
        self.assertEqual(self.f.refresh_calls, 1)

    def test_resume_does_not_start_if_was_inactive(self):
        # Timer never started (Watch off) -> resume must not start it.
        self.W.suspend_live(self.f)
        self.W.resume_live(self.f)
        self.assertFalse(self.f._live_timer.isActive())


# ===================== from test_watch_no_force_eval.py =====================
import contextlib
import io
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__watch_no_force_eval():
    standalone_init()


class TestWatchNoForceEval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def _make(self, name, marker):
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(name=name)
        node.add_output_attr("pts", "vector", is_array=True)
        node.set_compute_expression(
            'print("%s")\nself.pts = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]\n' % marker
        )
        return node.get_name()

    def _count(self, marker, fn):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = fn()
        return buf.getvalue().count(marker), result

    def test_clean_multi_read_does_not_recompute(self):
        """Reading a CLEAN multi output via the Watch path must not re-run
        the expression."""
        from mpynode.ui.widgets.watch import read_multi_plug_values

        mc.file(new=True, force=True)
        name = self._make("EVALW1", "EVALW1")
        mc.getAttr(name + ".pts[0]")  # prime -> clean
        meta = {"attr_type": "vector", "is_array": True}
        n, _ = self._count("EVALW1", lambda: read_multi_plug_values(name, "pts", meta))
        self.assertEqual(n, 0)

    def test_repeated_reads_do_not_recompute(self):
        """Successive live-poll reads of a clean output stay at zero
        recomputes (no 'constantly evaluating')."""
        from mpynode.ui.widgets.watch import read_multi_plug_values

        mc.file(new=True, force=True)
        name = self._make("EVALW2", "EVALW2")
        mc.getAttr(name + ".pts[0]")  # prime
        meta = {"attr_type": "vector", "is_array": True}
        total = 0
        for _ in range(5):
            n, _ = self._count(
                "EVALW2", lambda: read_multi_plug_values(name, "pts", meta)
            )
            total += n
        self.assertEqual(total, 0)

    def test_values_are_still_correct(self):
        """The cache-respecting read still returns the right (n,3) values."""
        from mpynode.ui.widgets.watch import read_multi_plug_values

        mc.file(new=True, force=True)
        name = self._make("EVALW3", "EVALW3")
        mc.getAttr(name + ".pts[0]")  # prime
        meta = {"attr_type": "vector", "is_array": True}
        val = read_multi_plug_values(name, "pts", meta)
        import numpy as np

        self.assertEqual(np.asarray(val).shape, (2, 3))
        self.assertEqual(list(np.asarray(val)[0]), [1.0, 2.0, 3.0])
        self.assertEqual(list(np.asarray(val)[1]), [4.0, 5.0, 6.0])

    def test_input_change_is_reflected(self):
        """We must not over-cache: when an actual INPUT changes, the next
        Watch read recomputes and shows the new value (the element getAttr
        recomputes naturally; only the index *query* was forced before)."""
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.watch import read_multi_plug_values

        mc.file(new=True, force=True)
        node = MPyNode.create(name="inDriven")
        node.add_input_attr("k", "float", default_value=1.0)
        node.add_output_attr("pts", "vector", is_array=True)
        node.set_compute_expression(
            'print("EVALW4")\n'
            "self.pts = [[self.k, 0.0, 0.0], [0.0, self.k, 0.0]]\n"
        )
        name = node.get_name()
        meta = {"attr_type": "vector", "is_array": True}
        mc.setAttr(name + ".k", 1.0)
        mc.getAttr(name + ".pts[0]")  # real first eval (viewport/connection)
        v1 = read_multi_plug_values(name, "pts", meta)
        import numpy as np

        self.assertEqual(float(np.asarray(v1)[0][0]), 1.0)
        # change the input -> next read must reflect the new value
        mc.setAttr(name + ".k", 7.0)
        n, v2 = self._count(
            "EVALW4", lambda: read_multi_plug_values(name, "pts", meta)
        )
        self.assertGreaterEqual(n, 1)
        self.assertEqual(float(np.asarray(v2)[0][0]), 7.0)

    def test_scalar_array_reads_as_numpy_with_runtime_dtype(self):
        """A scalar int / float / bool array plug must read back as the SAME
        numpy array -- and dtype -- the expression sees via
        read_user_inputs_dict (int64 / float64 / bool), NOT a Python list (the
        "index0/anchors shown as list" report). string arrays stay lists."""
        import numpy as np
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.watch import read_multi_plug_values

        mc.file(new=True, force=True)
        node = MPyNode.create(name="scalarArrays")
        node.add_input_attr("idx", "int", is_array=True)
        node.add_input_attr("wts", "float", is_array=True)
        node.add_input_attr("flags", "bool", is_array=True)
        node.add_input_attr("tags", "string", is_array=True)
        node.add_input_attr("empty", "int", is_array=True)
        name = node.get_name()
        for i, v in enumerate((2, 3, 1)):
            mc.setAttr("%s.idx[%d]" % (name, i), v)
        for i, v in enumerate((0.5, 1.5)):
            mc.setAttr("%s.wts[%d]" % (name, i), v)
        for i, v in enumerate((True, False, True)):
            mc.setAttr("%s.flags[%d]" % (name, i), v)
        for i, v in enumerate(("a", "b")):
            mc.setAttr("%s.tags[%d]" % (name, i), v, type="string")

        idx = read_multi_plug_values(
            name, "idx", {"attr_type": "int", "is_array": True})
        self.assertIsInstance(idx, np.ndarray)
        self.assertEqual(idx.dtype, np.dtype(np.int64))
        self.assertEqual(list(idx), [2, 3, 1])

        wts = read_multi_plug_values(
            name, "wts", {"attr_type": "float", "is_array": True})
        self.assertIsInstance(wts, np.ndarray)
        self.assertEqual(wts.dtype, np.dtype(np.float64))
        self.assertEqual(list(wts), [0.5, 1.5])

        flags = read_multi_plug_values(
            name, "flags", {"attr_type": "bool", "is_array": True})
        self.assertIsInstance(flags, np.ndarray)
        self.assertEqual(flags.dtype, np.dtype(bool))
        self.assertEqual(list(flags), [True, False, True])

        # string arrays can't be cleanly stacked into numpy -> stay a list.
        tags = read_multi_plug_values(
            name, "tags", {"attr_type": "string", "is_array": True})
        self.assertIsInstance(tags, list)
        self.assertEqual(tags, ["a", "b"])

        # An empty array still reports the right dtype (0-length numpy array),
        # matching read_user_inputs_dict's np.zeros(0, dtype=...) contract.
        empt = read_multi_plug_values(
            name, "empty", {"attr_type": "int", "is_array": True})
        self.assertIsInstance(empt, np.ndarray)
        self.assertEqual(empt.dtype, np.dtype(np.int64))
        self.assertEqual(empt.shape, (0,))

    def test_sparse_and_gapfill_scalar_arrays_stay_typed_numpy(self):
        """Both index paths of read_multi_plug_values keep the numpy dtype:
        the SPARSE path returns a COMPACT array of the set values; the DENSE
        path gap-fills missing indices with the attr default. (DNET-style
        index arrays exercise exactly these paths.)"""
        import numpy as np
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.watch import read_multi_plug_values

        mc.file(new=True, force=True)
        node = MPyNode.create(name="sparseArrays")
        node.add_input_attr("g", "int", is_array=True)
        name = node.get_name()
        # Non-contiguous indices: set 0 and 2, leave 1 unset (a gap).
        mc.setAttr("%s.g[0]" % name, 5)
        mc.setAttr("%s.g[2]" % name, 7)

        # sparse -> COMPACT [5, 7] (present values, sorted by index), int64.
        sp = read_multi_plug_values(
            name, "g", {"attr_type": "int", "is_array": True, "sparse": True})
        self.assertIsInstance(sp, np.ndarray)
        self.assertEqual(sp.dtype, np.dtype(np.int64))
        self.assertEqual(list(sp), [5, 7])

        # dense -> the index-1 gap is filled with the attr default (0 for int),
        # int64, length 3 -- matching what the expression sees.
        dn = read_multi_plug_values(
            name, "g", {"attr_type": "int", "is_array": True, "sparse": False})
        self.assertIsInstance(dn, np.ndarray)
        self.assertEqual(dn.dtype, np.dtype(np.int64))
        self.assertEqual(dn.shape, (3,))
        self.assertEqual(int(dn[0]), 5)
        self.assertEqual(int(dn[1]), 0)
        self.assertEqual(int(dn[2]), 7)

    def test_angle_attrs_display_radians_not_degrees(self):
        """angle / euler attrs must display in RADIANS -- the value the
        expression reads (plug.asDouble()) -- not the UI degrees cmds.getAttr
        returns. Single, array, and euler compound all convert."""
        import math
        import numpy as np
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.watch import (
            read_multi_plug_values,
            reshape_plug_value,
        )

        mc.file(new=True, force=True)
        node = MPyNode.create(name="angleNode")
        node.add_input_attr("ang", "angle")
        node.add_input_attr("angs", "angle", is_array=True)
        node.add_input_attr("rot", "euler")
        name = node.get_name()
        mc.setAttr("%s.ang" % name, 90)          # 90 deg (UI unit)
        mc.setAttr("%s.angs[0]" % name, 90)
        mc.setAttr("%s.angs[1]" % name, 180)
        mc.setAttr("%s.rot" % name, 90, 180, 45, type="double3")

        single = reshape_plug_value(
            mc.getAttr("%s.ang" % name),
            {"attr_type": "angle", "is_array": False})
        self.assertAlmostEqual(float(single), math.pi / 2, places=6)

        arr = read_multi_plug_values(
            name, "angs", {"attr_type": "angle", "is_array": True})
        self.assertIsInstance(arr, np.ndarray)
        self.assertEqual(arr.dtype, np.dtype(np.float64))
        self.assertAlmostEqual(float(arr[0]), math.pi / 2, places=6)
        self.assertAlmostEqual(float(arr[1]), math.pi, places=6)

        rot = reshape_plug_value(
            mc.getAttr("%s.rot" % name),
            {"attr_type": "euler", "is_array": False})
        self.assertIsInstance(rot, np.ndarray)
        np.testing.assert_allclose(
            rot, [math.radians(90), math.radians(180), math.radians(45)],
            atol=1e-6)

    def test_empty_compound_array_reads_as_typed_numpy(self):
        """An empty vector array input reports numpy.ndarray[float64] shape
        (0, 3) -- matching read_user_inputs_dict's np.zeros((0, 3)) -- not a
        bare Python list (the compound-branch empty-fallback fix)."""
        import numpy as np
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.watch import read_multi_plug_values, _format_type

        mc.file(new=True, force=True)
        node = MPyNode.create(name="emptyVec")
        node.add_input_attr("v", "vector", is_array=True)  # no elements set
        name = node.get_name()
        v = read_multi_plug_values(
            name, "v", {"attr_type": "vector", "is_array": True})
        self.assertIsInstance(v, np.ndarray)
        self.assertEqual(v.dtype, np.dtype(np.float64))
        self.assertEqual(v.shape, (0, 3))
        self.assertEqual(_format_type(v), "numpy.ndarray[float64]")


def setUpModule():
    _setUpModule__variables_sections()
    _setUpModule__watch_size_column()
    _setUpModule__watch_python_decode()
    _setUpModule__watch_no_force_eval()


if __name__ == "__main__":
    import unittest
    unittest.main()
