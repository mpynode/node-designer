"""A wrapper stays bound to the NODE, not to the name string it was built with.

``MPyNode`` caches the node name and every plug accessor concatenates it
(``self._name + "._computeSource"``). A ``cmds.rename`` performed OUTSIDE the
wrapper -- which templates do (``templates/MPyLocator/Mesh Regions``
renames the locator and its transform after building them) -- used to leave that
cached string pointing at a name that no longer exists, so any wrapper held
across the rename was DEAD.

These tests pin the object-identity contract: the name re-resolves from the
node's ``MObjectHandle`` (``partialPathName`` for DAG nodes, the dependency-node
name otherwise), and the pre-existing fallback behaviour for a deleted node is
unchanged.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestExternalRenameRefresh(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    # -- DAG node (mPyLocator shape) ------------------------------------

    def test_dag_get_name_follows_external_rename(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="renameMe")
        old = loc.get_name()
        mc.rename(old, "renamedShape")
        self.assertEqual(loc.get_name(), "renamedShape")

    def test_dag_plug_access_survives_external_rename(self):
        """get_name() alone is not enough -- the accessors concatenate the
        cached string directly, so they must follow the rename too."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="plugRename")
        mc.rename(loc.get_name(), "plugRenamed")
        loc.set_compute_expression("self.draw = None\n")
        self.assertEqual(loc.get_compute_expression(), "self.draw = None\n")

    def test_dag_shape_reachable_after_parent_transform_rename(self):
        """mesh_regions renames the PARENT transform as well; the shape's
        partial path must still resolve."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="parentRename")
        mc.rename(loc.get_transform(), "region_left")
        self.assertTrue(mc.objExists(loc.get_name()))

    # -- DG node (mPyNode) ----------------------------------------------

    def test_dg_get_name_follows_external_rename(self):
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(name="dgRename")
        mc.rename(node.get_name(), "dgRenamed")
        self.assertEqual(node.get_name(), "dgRenamed")
        node.set_compute_expression("x = 1\n")
        self.assertEqual(node.get_compute_expression(), "x = 1\n")

    # -- behaviour that must NOT change ---------------------------------

    def test_set_name_still_returns_and_caches_the_new_name(self):
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(name="viaSetName")
        self.assertEqual(node.set_name("viaSetNameB"), "viaSetNameB")
        self.assertEqual(node.get_name(), "viaSetNameB")

    def test_deleted_node_keeps_last_known_name(self):
        """A dead wrapper degrades exactly as before: get_name() returns the
        last known string (it does not raise) and cmds fails at the call site."""
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(name="doomedNode")
        name = node.get_name()
        mc.delete(name)
        self.assertEqual(node.get_name(), name)

    def test_repr_uses_the_live_name(self):
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(name="reprNode")
        mc.rename(node.get_name(), "reprRenamed")
        self.assertIn("reprRenamed", repr(node))


class TestRenameFalloutInTabLookup(unittest.TestCase):
    """Fallout of the refresh above: a lookup keyed on the PRE-rename name.

    ``NDScriptTabWidget.renameTabForNode(old, new)`` is called AFTER the
    ``cmds.rename``, and finds the tab by ``tab_node.get_name() == old_name``.
    Now that a wrapper follows the rename, that comparison can never match, and
    the open editor tab would keep its stale title. The lookup must accept
    EITHER name -- which is also correct for a wrapper that has not refreshed.

    Driven through the real (unbound) method with a duck-typed host so no
    QApplication / live Designer is needed.
    """

    def setUp(self):
        mc.file(new=True, force=True)

    def test_rename_tab_lookup_finds_the_renamed_node(self):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(name="tabRename")
        old  = node.get_name()
        mc.rename(old, "tabRenamed")

        class _Tab:
            def getMPyNode(self):
                return node

            def hasUnsavedChanges(self):
                return False

        class _Host:
            def __init__(self):
                self.titled = None

            def count(self):
                return 1

            def widget(self, _i):
                return _Tab()

            def _setTabTitle(self, index, name, dirty):
                self.titled = (index, name, dirty)

        host  = _Host()
        found = NDScriptTabWidget.renameTabForNode(host, old, "tabRenamed")
        self.assertTrue(found, "the tab for the renamed node was not found")
        self.assertEqual(host.titled, (0, "tabRenamed", False))


if __name__ == "__main__":
    unittest.main()
