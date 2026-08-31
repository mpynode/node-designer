import unittest
import maya.standalone
maya.standalone.initialize()
import maya.cmds as mc
from mpynode.wrappers.mpy_file import MPyFile


class TestBlessedMethodTier(unittest.TestCase):
    def setUp(self):
        if not mc.pluginInfo("mpynode_api2", q=True, loaded=True):
            mc.loadPlugin("mpynode_api2")

    def test_method_is_callable_and_bound(self):
        node = MPyFile.create(name="tierFile#")
        node.set_compute_expression(
            "self.outAlpha = 1.0 if callable(self.read_texture) else -1.0\n"
            "self.outColor = (0.0, 0.0, 0.0)")
        self.assertEqual(mc.getAttr(node._name + ".outAlpha"), 1.0)

    def test_unknown_method_still_raises(self):
        node = MPyFile.create(name="tier2File#")
        node.set_compute_expression(
            "try:\n"
            "    _ = self.no_such_method\n"
            "    self.outAlpha = -1.0\n"
            "except AttributeError:\n"
            "    self.outAlpha = 2.0\n"
            "self.outColor = (0.0, 0.0, 0.0)")
        self.assertEqual(mc.getAttr(node._name + ".outAlpha"), 2.0)


if __name__ == "__main__":
    unittest.main()
