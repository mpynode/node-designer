"""The "Add compiled nodes…" picker lists what the bundler has written under
its roots, one row per node, and hands back the checked ones."""

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
    _QAPP = _QApp.instance() or _QApp(["nd-compiled-picker-test"])

from tests.compile.pipeline.test_native_bundle import _src, _write


def _plugin_tree(root, plugin, node, cls, tid):
    _write(root, "%s/build/manifest.json" % plugin, json.dumps({
        "plugin_name": plugin, "porter_recipe_version": "36",
        "nodes": [{"type_name": node, "type_id": tid, "build_status": "compiled"}]}))
    return _write(root, "%s/build/source/%s.cpp" % (plugin, node), _src(node, cls, tid))


@unittest.skipIf(_QApp is None, "no Qt")
class TestPicker(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="picker_")
        self.a    = _plugin_tree(self.root, "plugA", "aNode", "ANode", "0x00081000")
        self.b    = _plugin_tree(self.root, "plugB", "bNode", "BNode", "0x00081001")

    def _picker(self):
        from mpynode.ui.dialogs.compiled_node_picker import CompiledNodePicker

        return CompiledNodePicker(roots=[self.root])

    def test_it_lists_one_row_per_compiled_node(self):
        p     = self._picker()
        nodes = sorted(m.node for m in p._members)
        self.assertEqual(nodes, ["aNode", "bNode"])
        self.assertEqual(p.selected_paths(), [])

    def test_select_all_returns_every_usable_path(self):
        p = self._picker()
        p._set_all(True)
        self.assertEqual(sorted(p.selected_paths()), sorted([self.a, self.b]))
        p._set_all(False)
        self.assertEqual(p.selected_paths(), [])

    def test_a_file_that_is_not_a_node_is_shown_but_not_selectable(self):
        p        = self._picker()
        bad      = _write(self.root, "plugA/build/source/plugin_main.cpp", "// entry")
        problems = p.add_sources([bad])
        self.assertEqual(len(problems), 1)
        p._set_all(True)
        self.assertNotIn(bad, p.selected_paths())

    def test_the_filter_hides_rows_and_select_all_respects_it(self):
        p = self._picker()
        p._search.setText("bNode")
        p._set_all(True)
        self.assertEqual(p.selected_paths(), [self.b])

    def test_a_manifest_row_without_a_source_is_skipped(self):
        _write(self.root, "plugC/build/manifest.json", json.dumps({
            "plugin_name": "plugC",
            "nodes": [{"type_name": "ghost", "type_id": "0x00081009"}]}))
        p = self._picker()
        self.assertNotIn("ghost", [m.node for m in p._members])

    def test_the_gallery_artifact_lookup_prefers_the_promoted_source(self):
        from mpynode.native.toolchain import bundle_plan

        self.assertEqual(bundle_plan.compiled_artifact_for(os.path.join(self.root, "plugA")),
                         self.a)
        self.assertIsNone(bundle_plan.compiled_artifact_for(os.path.join(self.root, "nope")))


if __name__ == "__main__":
    unittest.main()
