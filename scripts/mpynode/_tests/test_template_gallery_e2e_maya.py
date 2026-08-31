"""End-to-end Maya gate for the template gallery (Design #2).

Scans the REAL shipped templates/ tree from disk via template_gallery.scan_all(),
then drives the create commands in a live Maya session: a deformer template wires
to a selected polyCube (Create + Run setup), and the seed-only path leaves the node
seeded-but-unwired. Maya-only / Qt-free (run_tests.py needs no QApplication).
"""

import unittest

import maya.cmds as mc
from maya import cmds

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _find_entry(category, native_type):
    """Depth-first search of a TemplateCategory tree for the first leaf whose
    native_type matches. Returns the TemplateEntry or None."""
    # children of a category are TemplateCategory or TemplateEntry; entries
    # have an mpn_path attribute, categories have children.
    for child in getattr(category, "children", []):
        if hasattr(child, "mpn_path"):
            if getattr(child, "native_type", None) == native_type:
                return child
        else:
            found = _find_entry(child, native_type)
            if found is not None:
                return found
    return None


class TestTemplateGalleryDiscoveryE2E(unittest.TestCase):
    def test_scan_all_finds_shipped_deformer_template(self):
        from mpynode._common.util import template_gallery
        roots = template_gallery.scan_all()
        self.assertTrue(roots, "scan_all returned no roots")
        entry = None
        for _label, _path, tree in roots:
            entry = _find_entry(tree, "mPyDeformer")
            if entry is not None:
                break
        self.assertIsNotNone(
            entry, "no shipped template with native_type mPyDeformer found")
        self.assertTrue(entry.mpn_path.endswith("template.mpn"))
        self.assertEqual(entry.native_type, "mPyDeformer")


class TestTemplateCreateWiringE2E(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def _deformer_entry(self):
        from mpynode._common.util import template_gallery
        for _label, _path, tree in template_gallery.scan_all():
            entry = _find_entry(tree, "mPyDeformer")
            if entry is not None:
                return entry
        self.fail("shipped mPyDeformer template not found by scan_all")

    def test_create_plus_run_setup_wires_to_selection(self):
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode._base.commands import _TemplateCreateCommand, run_undoable
        entry = self._deformer_entry()
        payload = load_mpn(entry.mpn_path, trusted=True)
        mesh = mc.polyCube()[0]
        mc.select(mesh)
        name = run_undoable(
            _TemplateCreateCommand(payload, "mPyDeformer", run_setup=True))
        self.assertIsNotNone(name)
        geo = cmds.deformer(name, q=True, g=True) or []
        self.assertTrue(geo, "Create+Run setup did not wire the deformer")

    def test_create_plus_run_setup_excludes_self(self):
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode._base.commands import _TemplateCreateCommand, run_undoable
        entry = self._deformer_entry()
        payload = load_mpn(entry.mpn_path, trusted=True)
        mesh = mc.polyCube()[0]
        mc.select(mesh)
        name = run_undoable(
            _TemplateCreateCommand(payload, "mPyDeformer", run_setup=True))
        geo = cmds.deformer(name, q=True, g=True) or []
        self.assertNotIn(name, geo)


class TestTemplateCreateSeedOnlyE2E(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def _deformer_entry(self):
        from mpynode._common.util import template_gallery
        for _label, _path, tree in template_gallery.scan_all():
            entry = _find_entry(tree, "mPyDeformer")
            if entry is not None:
                return entry
        self.fail("shipped mPyDeformer template not found by scan_all")

    def test_seed_only_create_is_seeded_not_wired(self):
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode._base.commands import _ImportNodeCommand, run_undoable
        from mpynode._node_registry import get_spec
        entry = self._deformer_entry()
        payload = load_mpn(entry.mpn_path, trusted=True)
        mc.polyCube()                       # something selectable in the scene
        cmd = _ImportNodeCommand(
            payload, restore_persistent=False, seed_setup=True)
        run_undoable(cmd)
        name = cmd.created_name
        self.assertIsNotNone(name)
        # seeded: methods source carries a setup def
        node = get_spec("mPyDeformer").get_wrapper_class()(name)
        self.assertIn("def setup", node.get_methods_source() or "")
        # NOT wired: no deformer geometry attached
        self.assertFalse(cmds.deformer(name, q=True, g=True) or [])


if __name__ == "__main__":
    unittest.main()
