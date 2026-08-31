"""mPyTransform per-channel READ slots (SRT + shear + rotate order).

The node exposes its OWN live channels to the compute expression as five
always-present reads -- ``self.translate`` / ``self.rotate`` (**radians**) /
``self.scale`` / ``self.shear`` (each a ``(3,)`` numpy) and ``self.rotate_order``
(int 0..5, 0 == xyz). Any change to a channel re-evaluates the node, and the
values match the deterministically-compiled node's MPxTransformationMatrix
component reads (verified end-to-end by the compile+parity harness).
"""

from __future__ import annotations

import math
import unittest

import maya.cmds as mc
import numpy as np

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _drive_from(read_expr, base=0.0):
    """Compute source: worldMatrix tx = (``read_expr``) + ``base``, translate
    gate only (so tx is driven purely by the read value, un-gated channels stay
    live)."""
    return (
        "import numpy as np\n"
        "val = float(%s)\n" % read_expr
        + "m = np.eye(4)\n"
        "m[3, 0] = val + %r\n" % base
        + "self.local_matrix = m\n"
        "self.apply_translate = True\n"
    )


class TestChannelReads(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_translate_readable(self):
        """self.translate carries the live translate channel (cm)."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 7.0)
        mc.setAttr(n + "._computeSource",
                   _drive_from("self.translate[1]", base=100.0), type="string")
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12], 107.0)

    def test_translate_reevaluates_on_change(self):
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".translateY", 7.0)
        mc.setAttr(n + "._computeSource",
                   _drive_from("self.translate[1]", base=100.0), type="string")
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12], 107.0)
        mc.setAttr(n + ".translateY", 9.0)
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12], 109.0)

    def test_rotate_is_radians(self):
        """rotateZ = 90 deg -> self.rotate[2] == pi/2 (radians), NOT 90."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".rotateZ", 90.0)
        mc.setAttr(n + "._computeSource",
                   _drive_from("self.rotate[2]"), type="string")
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12],
                               math.pi / 2.0, places=5)

    def test_rotate_reevaluates_on_change(self):
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".rotateZ", 90.0)
        mc.setAttr(n + "._computeSource",
                   _drive_from("self.rotate[2]"), type="string")
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12],
                               math.pi / 2.0, places=5)
        mc.setAttr(n + ".rotateZ", 180.0)
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12],
                               math.pi, places=5)

    def test_scale_readable(self):
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".scaleY", 3.0)
        mc.setAttr(n + "._computeSource",
                   _drive_from("self.scale[1]", base=50.0), type="string")
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12], 53.0)

    def test_shear_readable(self):
        """self.shear carries the live shear channel (shearXY == child 0)."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".shearXY", 0.5)
        mc.setAttr(n + "._computeSource",
                   _drive_from("self.shear[0]", base=60.0), type="string")
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12], 60.5)

    def test_rotate_order_is_zero_based_int(self):
        """rotateOrder set to 2 (zxy) -> self.rotate_order == 2 (matches the
        .rotateOrder plug's 0-based enum, not the 1-based RotationOrder)."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + ".rotateOrder", 2)
        mc.setAttr(n + "._computeSource",
                   _drive_from("self.rotate_order", base=70.0), type="string")
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12], 72.0)

    def test_default_scale_is_one(self):
        """A fresh node reads self.scale == (1, 1, 1)."""
        n = mc.createNode("mPyTransform", name="t1")
        mc.setAttr(n + "._computeSource",
                   _drive_from("np.sum(self.scale)", base=0.0), type="string")
        self.assertAlmostEqual(mc.getAttr(n + ".worldMatrix[0]")[12], 3.0)


class TestChannelDirtyTriggers(unittest.TestCase):
    def test_channels_are_dirty_triggers(self):
        from mpynode._api1.mpy_transform import _BUILTIN_MATRIX_INPUT_NAMES

        for ch in ("translate", "rotate", "scale", "shear", "rotateOrder"):
            self.assertIn(ch, _BUILTIN_MATRIX_INPUT_NAMES)

    def test_pivots_not_in_trigger_set(self):
        """Pivots do not affect the per-channel reads, so they were reverted out
        of the trigger set (they are NOT needed for the SRT contract)."""
        from mpynode._api1.mpy_transform import _BUILTIN_MATRIX_INPUT_NAMES

        for ch in ("rotatePivot", "scalePivot", "rotateAxis"):
            self.assertNotIn(ch, _BUILTIN_MATRIX_INPUT_NAMES)


class TestChannelInputExposure(unittest.TestCase):
    """The channels are INPUT attributes (Inputs pane), NOT internal variables."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_channels_classify_as_input_not_internal(self):
        from mpynode.ui.widgets.plug_tree_walker import (
            walk_plug_tree, filter_by_direction)

        n = mc.createNode("mPyTransform", name="t1")
        rows = walk_plug_tree(n)
        input_names = {r.short_name for r in filter_by_direction(rows, "INPUT")}
        internal_names = {r.short_name
                          for r in filter_by_direction(rows, "INTERNAL")}
        for ch in ("translate", "rotate", "scale", "shear", "rotateOrder"):
            self.assertIn(ch, input_names, "%s must classify as INPUT" % ch)
            self.assertNotIn(ch, internal_names,
                             "%s must NOT be an internal var" % ch)

    def test_exposed_plugs_lookup(self):
        from mpynode.ui.widgets.plug_tree_walker import _exposed_input_plugs_for

        n = mc.createNode("mPyTransform", name="t1")
        exposed = _exposed_input_plugs_for(n)
        for ch in ("translate", "rotate", "scale", "shear", "rotateOrder"):
            self.assertIn(ch, exposed)

    def test_promoted_channels_survive_framework_filter(self):
        """The channels are DAG framework attrs (hidden by default) but the
        EXPOSED_INPUT_PLUGS allowlist keeps them visible in the Inputs pane;
        genuinely-hidden base attrs (worldMatrix) stay filtered."""
        from mpynode._common.plugs.plug_filter import is_hidden_input_row

        exposed = ("translate", "rotate", "scale", "shear", "rotateOrder")
        self.assertTrue(is_hidden_input_row("translate", ()))       # default hide
        self.assertFalse(is_hidden_input_row("translate", exposed))  # promoted
        self.assertTrue(is_hidden_input_row("worldMatrix", exposed))  # still hidden


class TestChannelLowering(unittest.TestCase):
    def test_local_reads_registry(self):
        from mpynode.native.compiler import nd_lower

        self.assertEqual(
            set(nd_lower._TRANSFORM_LOCAL_READS),
            {"translate", "rotate", "scale", "shear", "rotate_order"},
        )

    def test_channel_reads_lower_deterministically(self):
        from mpynode.native.compiler import nd_lower

        spec = {
            "compute": (
                "import numpy as np\n"
                "m = np.eye(4)\n"
                "m[3, 0] = float(self.translate[0])\n"
                "m[3, 1] = float(self.rotate[2])\n"
                "m[3, 2] = float(self.scale[1])\n"
                "m[0, 3] = float(self.shear[0]) + float(self.rotate_order)\n"
                "self.local_matrix = m\n"
                "self.apply_translate = True\n"
            ),
            "inputs": {},
        }
        res = nd_lower.try_lower_transform(spec)
        self.assertIsNotNone(
            res, "the per-channel reads must lower deterministically (not PORT)")
        joined = "\n".join(res)
        self.assertIn("{t.x, t.y, t.z}", joined)      # translate -> t
        self.assertIn("{r.x, r.y, r.z}", joined)      # rotate -> r (radians)
        self.assertIn("{sc.x, sc.y, sc.z}", joined)   # scale -> sc
        self.assertIn("{shr.x, shr.y, shr.z}", joined)  # shear -> shr
        self.assertIn("(int64_t)(ro)", joined)        # rotate_order -> ro (int)


if __name__ == "__main__":
    unittest.main()
