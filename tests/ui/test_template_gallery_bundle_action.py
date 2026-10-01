"""Templates gallery: "Add to bundle…" hands a compiled template's source to
the Compile dialog. Enabled only for a template that has been compiled."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

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
    _QAPP = _QApp.instance() or _QApp(["nd-gallery-bundle-test"])

from tests.compile.pipeline.test_native_bundle import _src, _write


@unittest.skipIf(_QApp is None, "no Qt")
class TestAddToBundleAction(unittest.TestCase):

    def _panel(self, on_bundle):
        from mpynode.ui.widgets.template_gallery_panel import NDTemplateGalleryPanel

        return NDTemplateGalleryPanel(parent=None, scan=lambda: [], on_bundle=on_bundle)

    @staticmethod
    def _entry(folder):
        from mpynode._common.util.template_gallery import TemplateEntry

        return TemplateEntry(label="T", folder=folder,
                             mpn_path=os.path.join(folder, "template.mpn"),
                             preview_path=None, description_path=None,
                             native_type="mPyNode")

    @staticmethod
    def _action(menu):
        for a in menu.actions():
            if a.text().startswith("Add to bundle"):
                return a
        return None

    def test_enabled_for_a_compiled_template_and_hands_over_its_source(self):
        d   = tempfile.mkdtemp(prefix="gal_bundle_")
        cpp = _write(d, "build/source/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        _write(d, "build/manifest.json", json.dumps({
            "plugin_name": "T", "nodes": [{"type_name": "aNode", "type_id": "0x00081000"}]}))
        got   = []
        panel = self._panel(got.append)
        menu  = panel._build_tree_menu(self._entry(d))
        act   = self._action(menu)
        self.assertIsNotNone(act)
        self.assertTrue(act.isEnabled())
        act.trigger()
        self.assertEqual(got, [cpp])

    def test_disabled_for_a_template_that_was_never_compiled(self):
        d     = tempfile.mkdtemp(prefix="gal_nobuild_")
        panel = self._panel(lambda p: None)
        act   = self._action(panel._build_tree_menu(self._entry(d)))
        self.assertIsNotNone(act)
        self.assertFalse(act.isEnabled())
        self.assertIn("Compile this template first", act.toolTip())

    def test_disabled_when_nothing_is_wired_to_receive_it(self):
        from mpynode.ui.widgets.template_gallery_panel import NDTemplateGalleryPanel

        d = tempfile.mkdtemp(prefix="gal_nowire_")
        _write(d, "build/source/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        _write(d, "build/manifest.json", json.dumps({
            "plugin_name": "T", "nodes": [{"type_name": "aNode", "type_id": "0x00081000"}]}))
        panel = NDTemplateGalleryPanel(parent=None, scan=lambda: [])
        act   = self._action(panel._build_tree_menu(self._entry(d)))
        self.assertFalse(act.isEnabled())


if __name__ == "__main__":
    unittest.main()
