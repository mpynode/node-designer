"""A compiled array output is clean at the ATTRIBUTE after compute.

The generated finalize wrote each array output through a builder and
``_outArr.setAllClean()``, which cleans the ELEMENTS. The array attribute
stayed dirty, so the Evaluation Manager called compute once per connected
array output (measured 2026-09-23: Spine 3 computes a frame, DNET 2 with its
solver drifting away from DG). ``emit_attr._array_write_lines`` now also emits
``data.setClean(<member>)``, on the written branch and on the default-fill
branch alike.

This compiles a real node with two array outputs and reads the datablock state
back. The emitted text is pinned by
``tests/attributes/test_array_output_builder.py``, the interpreted twin by
``tests/attributes/test_array_output_clean.py``.

SKIPS (never fails) when this host cannot compile for the running Maya.
"""
import os
import shutil
import tempfile
import unittest

from tests._setup import ensure_plugins_loaded, standalone_init
from tests.attributes.test_array_output_builder import _running_maya_root


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# Filled INSIDE a guard, like procrustesTags: a guard-false evaluation reaches
# the finalize with empty buffers and takes the default-fill branch.
_COMPUTE = ("if self.gate:\n"
            "    self.aOut = self.aIn\n"
            "    self.bOut = self.aIn\n"
            "self.s = 1.0\n")
_NAME    = "arrCleanRt"
_TYPE_ID = "0x00070571"


class TestCompiledArrayOutputsClean(unittest.TestCase):
    """Compile once, then pull one array and look at its sibling."""

    _tmp    = None
    _bundle = None

    @classmethod
    def setUpClass(cls):
        from mpynode.native.toolchain import toolchain

        root = _running_maya_root()
        if not root or not toolchain.check_toolchain(root).get("ok"):
            return
        import maya.cmds as mc
        import mpynode
        from mpynode.native.spec import spec_extractor
        from mpynode.native.toolchain import compile_controller as cc

        mc.file(new=True, force=True)
        src = mc.createNode("mPyNode", name="arrCleanRtSrc")
        w   = mpynode.wrap_node(src)
        w.add_input_attr("aIn", "double", is_array=True)
        w.add_input_attr("gate", "bool")
        w.add_output_attr("aOut", "double", is_array=True)
        w.add_output_attr("bOut", "double", is_array=True)
        w.add_output_attr("s", "double")
        w.set_compute_expression(_COMPUTE)
        spec                                = spec_extractor.extract_spec(src)
        spec["suggested"]["node_type_name"] = _NAME
        spec["suggested"]["class_name"]     = "ArrCleanRt"
        spec["suggested"]["type_id"]        = _TYPE_ID

        cls._tmp = tempfile.mkdtemp(prefix="arr_clean_rt_")
        res = cc.compile_plugin([spec], _NAME, cls._tmp, strict=True, verify=False,
                                reuse_cache=False, maya=root)
        if not res["ok"]:
            raise AssertionError("build failed: %s" % res.get("errors"))
        cls._bundle = res["bundle_path"]
        mc.file(new=True, force=True)
        mc.loadPlugin(cls._bundle)

    @classmethod
    def tearDownClass(cls):
        if not cls._bundle:
            return
        import maya.cmds as mc
        try:
            mc.file(new=True, force=True)
            mc.unloadPlugin(os.path.basename(cls._bundle))
        except Exception:
            pass
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        if not self._bundle:
            self.skipTest("no C++ toolchain or Maya devkit for the running mayapy")
        import maya.cmds as mc

        mc.file(new=True, force=True)
        mc.evaluationManager(mode="off")
        self.node = mc.createNode(_NAME)
        for i, v in enumerate((1.0, 2.0, 3.0)):
            mc.setAttr("%s.aIn[%d]" % (self.node, i), v)

    def _assert_both_clean(self, why):
        import maya.cmds as mc

        for attr in ("aOut", "bOut"):
            self.assertFalse(mc.isDirty("%s.%s" % (self.node, attr), datablock=True),
                             "%s left dirty after %s" % (attr, why))

    def test_pulling_one_array_cleans_the_other(self):
        import maya.cmds as mc

        mc.setAttr(self.node + ".gate", True)
        self.assertEqual(mc.getAttr(self.node + ".aOut[1]"), 2.0)
        self._assert_both_clean("a written evaluation")
        self.assertEqual(mc.getAttr(self.node + ".bOut")[0], (1.0, 2.0, 3.0))

    def test_default_fill_branch_cleans_too(self):
        import maya.cmds as mc

        mc.setAttr(self.node + ".gate", True)
        mc.getAttr(self.node + ".aOut[0]")  # materialise the elements
        mc.setAttr(self.node + ".gate", False)
        self.assertEqual(mc.getAttr(self.node + ".aOut[1]"), 0.0)
        self._assert_both_clean("a guard-false evaluation")


if __name__ == "__main__":
    unittest.main()
