"""Functional tests for the redesigned bubble_sort gallery template.

Loads the SHIPPED ``template.mpn``, builds a live node, wires ``n`` outputs
(so ``len(self.sort) == n``) and drives it to verify the redesign:
  * outputs are lerped LIVE between minVal/maxVal (default 1..10),
  * one bubble-sort pass per evaluation until ascending-sorted (reset False),
  * changing maxVal rescales every output WITHOUT re-sorting,
  * Auto (reset 2) re-randomizes the moment it finishes -> continuous loop,
  * True (reset 1) keeps reshuffling and never settles.

State is asserted from the numeric output values (robust to how many times the
DG computes per frame), not from step counts.
"""

import os
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _template_path():
    from mpynode._common.util.template_gallery import _bundled_templates_root
    root = _bundled_templates_root()
    assert root, "bundled templates root not found"
    return os.path.join(root, "MPyNode", "Bubble Sort", "template.mpn")


def _load_payload():
    from mpynode._common.io.mpn_io import load_mpn_header
    return load_mpn_header(_template_path())


class TestBubbleSortTemplateContent(unittest.TestCase):
    """The shipped template carries the redesigned attrs + expression."""

    def test_attr_defaults_and_enum(self):
        ia = _load_payload()["input_attrs"]
        self.assertEqual(ia["maxVal"].get("default_value"), 100.0)
        self.assertEqual(ia["minVal"].get("default_value"), 1.0)
        self.assertEqual(ia["reset"].get("enum_names"),
                         ["False", "True", "Auto"])
        self.assertEqual(ia["reset"].get("default_value"), 2)   # defaults to Auto

    def test_expression_is_live_lerp_and_auto(self):
        expr = _load_payload()["expression"]
        self.assertIn("lo + t * (hi - lo)", expr)  # live lerp at output time
        self.assertIn("reset == 2", expr)          # Auto continuous loop


class TestBubbleSortBehavior(unittest.TestCase):
    N = 6

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node
        self.node = deserialize_node(_load_payload(), restore_persistent=False)
        self.name = self.node.get_name()
        self.locs = []
        for i in range(self.N):
            loc = mc.spaceLocator()[0]
            mc.connectAttr("%s.sort[%d]" % (self.name, i),
                           loc + ".scaleY", force=True)
            self.locs.append(loc)

    def _eval(self):
        """Force one recompute (the template's ``time`` is auto-connected to
        time1, so dgdirty is the clean per-eval driver) and pull every output."""
        mc.dgdirty(self.name)
        return [mc.getAttr(l + ".scaleY") for l in self.locs]

    def _drive_until_sorted(self, reset_val, max_evals=60):
        # "Fully sorted" is the node's own signal (text == SORTED!!!), which is
        # set on the no-swap verification pass -- one eval AFTER the values first
        # become ascending (standard bubble sort). Drive to that signal.
        mc.setAttr(self.name + ".reset", reset_val)
        vals = None
        for _ in range(max_evals):
            vals = self._eval()
            if mc.getAttr(self.name + ".text") == "SORTED!!!":
                return vals, True
        return vals, False

    def test_outputs_within_live_minmax(self):
        for v in self._eval():                        # defaults 1..100
            self.assertGreaterEqual(v, 1.0 - 1e-6)
            self.assertLessEqual(v, 100.0 + 1e-6)

    def test_sorts_then_holds(self):
        vals, ok = self._drive_until_sorted(0)        # False
        self.assertTrue(ok, "should reach a sorted (ascending) state")
        self.assertEqual(vals, sorted(vals))
        self.assertEqual(mc.getAttr(self.name + ".text"), "SORTED!!!")
        held = self._eval()                           # holds sorted
        self.assertEqual(held, sorted(held))
        self.assertEqual(mc.getAttr(self.name + ".text"), "SORTED!!!")

    def test_live_lerp_rescales_without_resort(self):
        vals, ok = self._drive_until_sorted(0)
        self.assertTrue(ok)
        self.assertEqual(vals, sorted(vals))
        mc.setAttr(self.name + ".maxVal", 50.0)               # rescale DOWN from 100
        rescaled = self._eval()
        self.assertEqual(rescaled, sorted(rescaled))      # NOT re-sorted
        self.assertLessEqual(max(rescaled), 50.0 + 1e-6)  # new ceiling
        self.assertLess(max(rescaled), max(vals))         # actually rescaled
        self.assertGreaterEqual(min(rescaled), 1.0 - 1e-6)

    def test_auto_reshuffles_after_completion(self):
        vals, ok = self._drive_until_sorted(2)                # Auto
        self.assertTrue(ok)
        after = self._eval()                                  # auto-regenerated
        self.assertNotEqual(after, vals)                      # fresh random set
        self.assertEqual(mc.getAttr(self.name + ".text"), "UNSORTED!!!")

    def test_true_holds_reshuffle(self):
        mc.setAttr(self.name + ".reset", 1)                   # True
        a = self._eval()
        b = self._eval()
        self.assertNotEqual(a, b)                             # reshuffled
        self.assertEqual(mc.getAttr(self.name + ".text"), "UNSORTED!!!")


if __name__ == "__main__":
    unittest.main()
