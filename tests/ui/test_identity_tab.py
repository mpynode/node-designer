"""Identity panel + Option A scene-tree rendering.

Option A: the scene tree's column 1 renders the node's canonical Class as
``Class(Parent)`` when classed and ``Parent()`` when class-less, where Parent is
the root wrapper class name for the node's native type (MPyNode/MPyFile/...) --
mirroring the baked ``class X(Parent):`` line.

Identity panel (minimal layout): Class is the ONE editable field; the node type
is the derived camelCase (lower-first) of the Class, shown only inside the two
read-only projection lines (Python API + Native C++), both resolving to
``<type>1`` -- the SAME name Maya gives a node created either way.

Importing the widget pulls Qt, so create a QApplication at IMPORT time (before
maya.standalone installs a non-GUI QCoreApplication). Mirrors the other UI test
modules.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest

# QApplication at IMPORT time -- mirrors the other UI test modules.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-identity-tab-test"])

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestOptionA(unittest.TestCase):
    def test_classed_label(self):
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.scene_tree import NDSceneTreeItem

        mc.file(new=True, force=True)
        n = MPyNode.create(name="optA#")
        n.set_py_class("mpynode_user.Procrustes")
        item = NDSceneTreeItem(None, n.get_name(), "mPyNode")
        self.assertEqual(item.text(1), "Procrustes(MPyNode)")

    def test_classless_label(self):
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.scene_tree import NDSceneTreeItem

        mc.file(new=True, force=True)
        n    = MPyNode.create(name="optAless#")  # class-less
        item = NDSceneTreeItem(None, n.get_name(), "mPyNode")
        self.assertEqual(item.text(1), "MPyNode()")


class TestIdentityTab(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_classed_derives_the_node_type(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idtab#")
        n.set_py_class("mpynode_user.Procrustes")
        w = NDIdentityWidget()
        w.setPyNode(n)
        self.assertEqual(w.class_name_text(), "Procrustes")
        self.assertEqual(w.node_type_text(), "procrustes")

    def test_multiword_class_camelcases_the_type(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idtabmw#")
        n.set_py_class("mpynode_user.ProcrustesConstraint")
        w = NDIdentityWidget()
        w.setPyNode(n)
        self.assertEqual(w.node_type_text(), "procrustesConstraint")

    def test_classless_is_empty(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idtabless#")
        w = NDIdentityWidget()
        w.setPyNode(n)
        self.assertEqual(w.class_name_text(), "")
        self.assertEqual(w.node_type_text(), "")

    def test_naming_a_classless_node_commits(self):
        """Typing a PascalCase name into the Class field + Enter fires
        ``editingFinished`` -> ``_commit_class``, which synthesizes + stamps the
        canonical class, repopulates the derived projections, and emits
        ``classChanged``."""
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idnameflow#")
        w = NDIdentityWidget()
        w.setPyNode(n)
        self.assertEqual(w.class_name_text(), "")  # class-less to start
        emitted = []
        w.classChanged.connect(lambda s: emitted.append(s))
        w._class_edit.setText("MyThing")
        w._commit_class()
        self.assertEqual(n.get_py_class(),    "mpynode_user.MyThing")
        self.assertEqual(w.class_name_text(), "MyThing")
        self.assertEqual(w.node_type_text(),  "myThing")
        self.assertEqual(emitted,             ["MyThing"])

    def test_refresh_survives_deleted_node(self):
        """If the backing node is gone (deleted / externally renamed),
        ``refresh()`` must NOT raise -- it degrades to the empty render so the
        sibling panels (Attributes/Framework/Variables/Profile/Watch) still
        populate."""
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idgone#")
        n.set_py_class("mpynode_user.Ghosty")
        w = NDIdentityWidget()
        w.setPyNode(n)
        self.assertEqual(w.class_name_text(), "Ghosty")
        mc.delete(n.get_name())  # backing node now dead
        w.refresh()              # must not raise
        self.assertEqual(w.node_type_text(), "")
        self.assertEqual(w.class_name_text(), "")

    def test_recommit_same_class_does_not_reemit(self):
        """Focus-out on an already-classed node with no edit fires
        ``editingFinished`` -> ``_commit_class``; an unchanged name must NOT
        re-synthesize or re-emit ``classChanged`` (which would trigger a
        redundant scene-tree re-render)."""
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idrecommit#")
        n.set_py_class("mpynode_user.Keeper")
        w = NDIdentityWidget()
        w.setPyNode(n)
        self.assertEqual(w.class_name_text(), "Keeper")
        emitted = []
        w.classChanged.connect(lambda s: emitted.append(s))
        w._commit_class()              # simulate focus-out, no edit
        self.assertEqual(emitted, [])  # no redundant re-emit
        self.assertEqual(n.get_py_class(), "mpynode_user.Keeper")

    def test_invalid_class_name_rejected(self):
        """A non-PascalCase entry is rejected: the node stays class-less and the
        field resets (no partial stamp)."""
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idbadname#")
        w = NDIdentityWidget()
        w.setPyNode(n)
        w._class_edit.setText("has space")
        w._commit_class()
        self.assertEqual(n.get_py_class() or "", "")
        self.assertEqual(w.class_name_text(), "")


# TestTheBakeContractIsReadableHere lived here. The panel no longer renders
# the "What the bake carries" note, the Python API projection or the Native
# C++ projection -- they were reference text that cost more vertical space
# than the rest of the panel and were not re-read after the first look. The
# panel now earns its place on one thing: Class, which is editable nowhere
# else (the Scene tree shows it read-only in column 1).


class TestClearingTheClass(unittest.TestCase):
    """Blank + Enter unstamps THIS node. There used to be no way back to
    class-less from any UI: the field ignored a blank, the prompt read it as
    Cancel, and the scene tree's comment called the omission deliberate."""

    def test_blank_clears_a_classed_node_and_emits(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idclear#")
        n.set_py_class("mpynode_user.Doomed")
        w = NDIdentityWidget()
        w.setPyNode(n)
        self.assertEqual(w.class_name_text(), "Doomed")
        emitted = []
        w.classChanged.connect(lambda s: emitted.append(s))
        w._class_edit.setText("")
        w._commit_class()
        self.assertFalse(n.get_py_class())
        self.assertEqual(w.class_name_text(), "")
        self.assertEqual(w.node_type_text(),  "")
        self.assertEqual(emitted,             [""])

    def test_blank_on_a_classless_node_is_a_no_op(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        n = MPyNode.create(name="idblank#")
        w = NDIdentityWidget()
        w.setPyNode(n)
        emitted = []
        w.classChanged.connect(lambda s: emitted.append(s))
        w._class_edit.setText("")
        w._commit_class()          # focus-out on an empty field, nothing to do
        self.assertEqual(emitted, [])
        self.assertFalse(n.get_py_class())

    def test_clearing_one_instance_leaves_its_siblings_classed(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        a = MPyNode.create(name="idsibA#")
        b = MPyNode.create(name="idsibB#")
        a.set_py_class("mpynode_user.Shared")
        b.set_py_class("mpynode_user.Shared")
        w = NDIdentityWidget()
        w.setPyNode(a)
        w._class_edit.setText("")
        w._commit_class()
        self.assertFalse(a.get_py_class())
        self.assertEqual(b.get_py_class(), "mpynode_user.Shared")


if __name__ == "__main__":
    unittest.main()
