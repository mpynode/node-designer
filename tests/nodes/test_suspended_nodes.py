"""A suspended Python node (``nodeState`` Has No Effect / Blocking -- set by
Convert to C++, or by hand) must cost nothing per frame.

Two things kept costing after the outputs were moved off a converted
mPyBlendShape (Combo Correctives, 1306 verts, 167 targets; measured 2026-09-11):

* the Evaluation Manager evaluates a node whose inputs animate whether or not
  anything reads its outputs -- 8 deforms in 8 frames, 142 ms/frame, the same
  as before the convert. ``nodeState`` is what stops that, so the convert sets
  it (see ``node_swap._snapshot_state``);
* with the deform gone, ~100 ms/frame remained: the per-frame ``timeChanged``
  callback re-dirtied the node, and the Python ``setDependentsDirty`` override
  ran ~3,800 times a frame reading and decoding ``_inputAttrs`` each time.

These pin the callback half; ``test_dirty_recompute`` pins the dirty gate.
"""
from __future__ import annotations

import unittest
from unittest import mock

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestTimeChangeCallbacksSkipSuspendedNodes(unittest.TestCase):
    """Each deformer family's ``_on_time_change`` touches ``envelope`` on every
    node of its type so the deformer re-evaluates per frame. A suspended node
    has nothing to re-evaluate, so it is left alone -- touching it only
    re-dirties a node the Evaluation Manager would then evaluate for nothing."""

    _FAMILIES = (
        ("mpynode._api1.mpy_deformer", "mPyDeformer"),
        ("mpynode._api1.mpy_blend_shape", "mPyBlendShape"),
        ("mpynode._api1.mpy_skin_cluster", "mPySkinCluster"),
    )

    def setUp(self):
        mc.file(new=True, force=True)

    def _touched(self, module, node):
        """The ``.envelope`` writes the callback issued, as a set of plugs."""
        real_set_attr = mc.setAttr
        calls = []

        def spy(*args, **kwargs):
            calls.append(args[0] if args else None)
            return real_set_attr(*args, **kwargs)

        with mock.patch("maya.cmds.setAttr", spy):
            module._on_time_change(None)
        return {c for c in calls if isinstance(c, str) and c.endswith(".envelope")}

    def test_every_family_skips_a_suspended_node_and_touches_a_live_one(self):
        import importlib

        for mod_name, node_type in self._FAMILIES:
            module = importlib.import_module(mod_name)
            sphere = mc.polySphere(sx=6, sy=6)[0]
            node = mc.deformer(sphere, type=node_type)[0]
            with self.subTest(node_type=node_type):
                self.assertIn(node + ".envelope", self._touched(module, node),
                              "a live %s must be touched" % node_type)
                mc.setAttr(node + ".nodeState", 1)          # Has No Effect
                self.assertNotIn(node + ".envelope", self._touched(module, node),
                                 "a suspended %s must be left alone" % node_type)
                mc.setAttr(node + ".nodeState", 0)
                self.assertIn(node + ".envelope", self._touched(module, node),
                              "un-suspending resumes the touch")


if __name__ == "__main__":
    unittest.main()
