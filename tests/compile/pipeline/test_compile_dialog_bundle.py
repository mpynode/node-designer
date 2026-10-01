"""Compile dialog: rows for nodes that are ALREADY compiled.

"Add compiled nodes…" adds already-compiled sources as rows (Source =
"Compiled C++"); each checked one shows a live pre-flight verdict in Status;
and Compile with nothing but compiled rows checked bundles them as they are,
through ``CompileController.start_bundle`` -- no spec, no port, no verify.
With scene rows checked too, the compiled ones ride along as ``prebuilt``.

Constructs the real ``CompileDialog`` (a QDialog), so a GUI QApplication must
exist at IMPORT time -- mirrors the other compile-dialog test modules.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-compile-bundle-test"])

from tests._setup import ensure_plugins_loaded, standalone_init
from tests.compile.pipeline.test_native_bundle import _src, _write


def setUpModule():
    standalone_init()


class _FakeController:
    """Records what the dialog asked for instead of building anything."""

    def __init__(self):
        self.calls  = []
        self.result = None

    def is_busy(self):
        return False

    def start_bundle(self, paths, plugin_name, out_dir, **opts):
        self.calls.append(("bundle", list(paths), plugin_name, out_dir, opts))

    def start(self, specs, plugin_name, out_dir, **opts):
        self.calls.append(("compile", list(specs), plugin_name, out_dir, opts))

    def start_multi(self, specs, plugin_name, out_dir, targets, **opts):
        self.calls.append(("multi", list(specs), plugin_name, out_dir, opts))


@unittest.skipIf(_QApp is None, "no Qt")
class TestCompiledRows(unittest.TestCase):

    def setUp(self):
        import sys
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        sys.modules.pop("mpynode_user", None)
        self.d = tempfile.mkdtemp(prefix="dlg_bundle_")
        self.a = _write(self.d, "a/build/source/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        self.b = _write(self.d, "b/build/source/bNode.cpp", _src("bNode", "BNode", "0x00081001"))

    def _dialog(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        dlg = CompileDialog()
        self.addCleanup(dlg.close)
        return dlg

    @staticmethod
    def _row_of(dlg, name):
        for i, (nm, _t) in enumerate(dlg._scene_nodes):
            if nm == name:
                return i
        return None

    @staticmethod
    def _cell(dlg, row, col):
        from mpynode.ui.dialogs import compile_dialog as cd

        it = dlg._table.item(row, col)
        return it.text() if it is not None else None

    def test_added_sources_become_checked_compiled_rows(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        dlg = self._dialog()
        added, problems = dlg.add_compiled_sources([self.a, self.b])
        self.assertEqual((added, problems), (["aNode", "bNode"], []))
        row = self._row_of(dlg, "aNode")
        self.assertIsNotNone(row)
        self.assertEqual(self._cell(dlg, row, cd._COL_SOURCE), "Compiled C++")
        self.assertEqual(self._cell(dlg, row, cd._COL_TYPE),   "aNode")
        self.assertEqual(self._cell(dlg, row, cd._COL_CLASS),  "ANode (C++)")
        self.assertEqual(self._cell(dlg, row, cd._COL_STATUS), "Ready")
        self.assertTrue(dlg._compile_checkbox(row).isChecked())
        self.assertIn("aNode", dlg._checked)

    def test_the_data_box_is_off_for_a_compiled_row(self):
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode.ui.qt_wrapper import QCheckBox

        dlg = self._dialog()
        dlg.add_compiled_sources([self.a])
        row = self._row_of(dlg, "aNode")
        box = dlg._table.cellWidget(row, cd._COL_PERSIST).findChild(QCheckBox)
        self.assertFalse(box.isEnabled())

    def test_a_source_that_is_not_a_node_is_reported_not_added(self):
        dlg = self._dialog()
        bad = _write(self.d, "x/plugin_main.cpp", "// entry point")
        added, problems = dlg.add_compiled_sources([bad])
        self.assertEqual(added, [])
        self.assertEqual(len(problems), 1)
        self.assertIsNone(self._row_of(dlg, "plugin_main"))

    def test_the_same_node_twice_is_reported_once(self):
        dlg = self._dialog()
        dlg.add_compiled_sources([self.a])
        again = _write(self.d, "a2/build/source/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        added, problems = dlg.add_compiled_sources([again])
        self.assertEqual(added, [])
        self.assertIn("already listed", problems[0])

    def test_two_compiled_rows_on_one_id_show_a_conflict(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        dlg = self._dialog()
        c   = _write(self.d, "c/build/source/cNode.cpp", _src("cNode", "CNode", "0x00081000"))
        dlg.add_compiled_sources([self.a, c])
        for name in ("aNode", "cNode"):
            status = self._cell(dlg, self._row_of(dlg, name), cd._COL_STATUS)
            self.assertTrue(status.startswith("Conflict: E4"), status)
        # unchecking one clears the conflict on the other
        dlg._checked.discard("cNode")
        dlg._refresh_compiled_status()
        self.assertEqual(self._cell(dlg, self._row_of(dlg, "aNode"), cd._COL_STATUS), "Ready")
        self.assertEqual(self._cell(dlg, self._row_of(dlg, "cNode"), cd._COL_STATUS), "")

    def test_a_compiled_row_conflicts_with_a_scene_node_of_the_same_type(self):
        from mpynode import MPyNode
        from mpynode._common.io.user_classes import synthesize, dotted_path
        from mpynode.ui.dialogs import compile_dialog as cd

        synthesize("ANode", "mPyNode")
        n = MPyNode.create(name="liveA")
        n.set_py_class(dotted_path("ANode"))
        dlg        = self._dialog()
        scene_row  = self._row_of(dlg, "liveA")
        scene_type = self._cell(dlg, scene_row, cd._COL_TYPE)
        clash = _write(self.d, "k/build/source/%s.cpp" % scene_type,
                       _src(scene_type, "ANode", "0x00081005"))
        dlg.add_compiled_sources([clash])
        comp_row = self._row_of(dlg, scene_type)
        self.assertEqual(self._cell(dlg, comp_row, cd._COL_STATUS), "Ready")
        dlg._checked.add("liveA")
        dlg._refresh_compiled_status()
        status = self._cell(dlg, comp_row, cd._COL_STATUS)
        self.assertTrue(status.startswith("Conflict:"), status)
        self.assertIn("liveA", status)

    def test_compile_with_only_compiled_rows_bundles_them_as_they_are(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        dlg = self._dialog()
        dlg.add_compiled_sources([self.a, self.b])
        fake            = _FakeController()
        dlg._controller = fake
        dlg._name_edit.setText("duo")
        out = os.path.join(self.d, "out")
        dlg._out_edit.setText(out)
        with mock.patch.object(cd.QMessageBox, "warning", return_value=None):
            dlg._on_compile()
        self.addCleanup(dlg._set_busy, False)
        self.assertEqual(len(fake.calls), 1, fake.calls)
        kind, paths, name, out_dir, opts = fake.calls[0]
        self.assertEqual(kind,            "bundle")
        self.assertEqual(paths,           [self.a, self.b])
        self.assertEqual((name, out_dir), ("duo", out))
        self.assertTrue(dlg._busy)
        # progress events are keyed by the registered node name
        self.assertEqual(sorted(dlg._row_by_type), ["aNode", "bNode"])
        self.assertEqual(self._cell(dlg, self._row_of(dlg, "aNode"), cd._COL_STATUS), "queued")

    def test_fresh_open_clears_compiled_rows(self):
        dlg = self._dialog()
        dlg.add_compiled_sources([self.a])
        dlg.refresh_nodes()
        self.assertIsNone(self._row_of(dlg, "aNode"))
        self.assertEqual(dlg._compiled_rows, {})


if __name__ == "__main__":
    unittest.main()
