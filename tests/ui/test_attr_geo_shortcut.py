"""Attributes tab: "Create + Connect <geometry>" on a mesh / NURBS plug.

The panel side of :mod:`tests.authoring.test_create_geo_for_plug`. What matters
here is that the shortcut is offered for exactly the geometry attr types and
nothing else -- a float plug has no shape to make -- and that the panel's
handler really wires the plug rather than just creating a node beside it.
"""
from __future__ import annotations

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
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-geo-shortcut-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


@unittest.skipIf(_QAPP is None, "no Qt binding available")
class TestGeoShortcutInTheAttrTree(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="geoPanel")
        self.name = self.node.get_name()
        self.node.add_input_attr("inMesh", "mesh")
        self.node.add_input_attr("inCurve", "nurbsCurve")
        self.node.add_input_attr("amount", "float")
        self.node.add_output_attr("outMesh", "mesh")

    def _tree(self, direction="input"):
        from mpynode.ui.widgets.attributes import (NDInputAttrTree,
                                                   NDOutputAttrTree)

        tree = (NDInputAttrTree() if direction == "input"
                else NDOutputAttrTree())
        tree.setNode(self.node)
        return tree

    def _select(self, tree, attr_name):
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        found = None

        def _walk(item):
            nonlocal found
            if (isinstance(item, NDUserAttrTreeItem)
                    and getattr(item, "attr_name", None) == attr_name):
                found = item
            for i in range(item.childCount()):
                _walk(item.child(i))

        for i in range(tree.topLevelItemCount()):
            _walk(tree.topLevelItem(i))
        self.assertIsNotNone(found, "no row for %r" % attr_name)
        tree.clearSelection()
        found.setSelected(True)
        return found

    def test_a_geometry_plug_is_offered_the_shortcut(self):
        tree = self._tree()
        self._select(tree, "inMesh")
        self.assertEqual([it.attr_name for it in tree._selected_geo_items()],
                         ["inMesh"])

    def test_a_plain_plug_is_not(self):
        tree = self._tree()
        self._select(tree, "amount")
        self.assertEqual(tree._selected_geo_items(), [])

    def test_the_handler_wires_the_input(self):
        tree = self._tree()
        self._select(tree, "inCurve")
        tree._create_geo_for_selected()
        src = mc.listConnections(self.name + ".inCurve", source=True,
                                 destination=False, plugs=True) or []
        self.assertEqual(len(src), 1)
        # The wire is made from worldSpace[0]; listConnections reports the
        # multi parent for it, so accept either spelling.
        self.assertTrue(src[0].split(".", 1)[1].startswith("worldSpace"), src)

    def test_the_handler_wires_the_output(self):
        tree = self._tree("output")
        self._select(tree, "outMesh")
        tree._create_geo_for_selected()
        dst = mc.listConnections(self.name + ".outMesh", source=False,
                                 destination=True, plugs=True) or []
        self.assertEqual(len(dst), 1)
        self.assertTrue(dst[0].endswith(".inMesh"), dst)

    def test_the_menu_names_every_geometry_type(self):
        # A type the command can build but the menu cannot name would raise a
        # KeyError as the menu opens, taking the right-click with it.
        from mpynode._base.commands import _CreateGeoForPlugCommand
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        self.assertEqual(sorted(NDInputAttrTree._GEO_MENU_LABELS),
                         sorted(_CreateGeoForPlugCommand.GEO_TYPES))


if __name__ == "__main__":
    unittest.main()
