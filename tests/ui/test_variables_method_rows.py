import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import maya.standalone
maya.standalone.initialize()
import maya.cmds as mc

from mpynode.wrappers.mpy_file import MPyFile
from mpynode.ui.widgets import variables

# Try to initialize QApplication for render tests
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication([])


class TestMethodRowsData(unittest.TestCase):
    def setUp(self):
        if not mc.pluginInfo("mpynode_api2", q=True, loaded=True):
            mc.loadPlugin("mpynode_api2")

    def test_dir_label_method(self):
        # Ask 1: Dir column shows the direction as a plain word (READ / WRITE /
        # READWRITE / METHOD); legacy directionless -> neutral "".
        self.assertEqual(variables._dir_label("method"), "METHOD")
        self.assertEqual(variables._dir_label("read"),   "READ")
        self.assertEqual(variables._dir_label(""),       "")

    def test_method_rows_present_with_signature(self):
        node    = MPyFile.create(name="varFile#")
        rows    = variables.collect_internal_api_rows(node._name)
        by_name = {name: (d, val) for (name, d, val) in rows}
        self.assertIn("read_texture", by_name)
        d, val = by_name["read_texture"]
        self.assertEqual(d, "method")
        self.assertIn("read_texture(", val)

    def test_slots_still_render(self):
        # mPyFile has INTERNAL_API_SLOTS bridge handles; ensure they still appear
        # and are NOT tagged "method".
        node         = MPyFile.create(name="varFile2#")
        rows         = variables.collect_internal_api_rows(node._name)
        method_names = {name for (name, d, v) in rows if d == "method"}
        self.assertEqual(method_names,
                         {"read_texture", "sample_texture", "composite_layers",
                          "write_texture"})


class TestSlotlessMethodRows(unittest.TestCase):
    """Regression: a wrapper with NO INTERNAL_API_SLOTS must still surface its
    blessed API methods. mPySkinCluster declares no bridge slots (every self.X is
    a plug), yet its linear_blend / dual_quaternion / twist_swing
    methods belong in the Variables-API panel. An early `if not specs: return []`
    used to swallow them for every slot-less wrapper."""

    def setUp(self):
        if not mc.pluginInfo("mpynode_api1", q=True, loaded=True):
            mc.loadPlugin("mpynode_api1")
        mc.file(new=True, force=True)

    def _skin(self, name):
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        j1 = mc.joint(p=(0, 0, 0), n="msrj1")
        mc.select(clear=True)
        j2 = mc.joint(p=(0, 2, 0), n="msrj2")
        mc.select(clear=True)
        plane = mc.polyPlane(name="msrP", w=4, h=4, sx=2, sy=2)[0]
        return MPySkinCluster.create(plane, joints=[j1, j2], name=name)

    def test_skin_cluster_has_empty_slots(self):
        # Pin the precondition this regression is about: the wrapper is slot-less.
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        self.assertEqual(tuple(MPySkinCluster.INTERNAL_API_SLOTS), ())

    def test_skin_methods_present_with_signature(self):
        sc      = self._skin("msrSkin#")
        rows    = variables.collect_internal_api_rows(sc.get_name())
        by_name = {name: (d, val) for (name, d, val) in rows}
        for meth in ("linear_blend", "dual_quaternion",
                     "twist_swing"):
            self.assertIn(meth, by_name, "%s missing from Variables-API rows" % meth)
            d, val = by_name[meth]
            self.assertEqual(d, "method")
            self.assertIn("%s(" % meth, val)


class TestMethodRowRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Skip in batch mode (mayapy) - QTreeWidget needs a real Qt event loop
        if mc.about(batch=True):
            raise unittest.SkipTest("QTreeWidget unavailable in batch mode")
        if _QAPP is None:
            raise unittest.SkipTest("Qt unavailable")

    def test_row_item_renders_method(self):
        from mpynode.ui.widgets.variables import NDPlugRowItem, _dir_label
        from mpynode.ui.qt_wrapper import QTreeWidget
        tree = QTreeWidget()
        tree.setColumnCount(3)
        item = NDPlugRowItem(tree, "read_texture", _dir_label("method"),
                             "read_texture() -- Load + linearize ...")
        self.assertEqual(item.text(1), "METHOD")
        self.assertTrue(item.toolTip(2).startswith("<qt>"))


if __name__ == "__main__":
    unittest.main()
