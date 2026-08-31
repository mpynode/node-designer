"""Per-class divergence detection (must-fix #1 core).

Instances of one Class share a compiled type but carry authored code per plug,
so Duplicate-then-edit can make siblings diverge. ``divergence.diverged_classes``
flags any Class whose instances are not structurally identical (differing
normalized-source content hash), so the compile path can warn + fork instead of
silently compiling one representative. Class-less nodes are omitted. The hash
ignores comments/whitespace, so a comment-only edit is NOT a divergence.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestDivergence(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _mk(self, name, cls=None, expr="out = 1"):
        from mpynode import MPyNode

        n = MPyNode.create(name=name)
        n.set_compute_expression(expr)
        if cls:
            from mpynode._common.io.user_classes import synthesize, dotted_path

            synthesize(cls, "mPyNode")
            n.set_py_class(dotted_path(cls))
        return n

    def test_identical_instances_not_diverged(self):
        from mpynode.native.spec.divergence import diverged_classes

        a = self._mk("divA1", cls="Widget", expr="out = x + 1")
        b = self._mk("divB1", cls="Widget", expr="out = x + 1")
        self.assertEqual(diverged_classes([a, b]), {})

    def test_edited_sibling_diverges(self):
        from mpynode.native.spec.divergence import diverged_classes

        a = self._mk("divA2", cls="Widget", expr="out = x + 1")
        b = self._mk("divB2", cls="Widget", expr="out = x + 2")  # edited body
        d = diverged_classes([a, b])
        self.assertIn("mpynode_user.Widget", d)
        # two distinct content hashes -> two partitions
        self.assertEqual(len(d["mpynode_user.Widget"]), 2)

    def test_comment_only_change_not_diverged(self):
        from mpynode.native.spec.divergence import diverged_classes

        a = self._mk("divCmt1", cls="Widget", expr="out = x + 1")
        b = self._mk("divCmt2", cls="Widget", expr="out = x + 1  # tweak")
        self.assertEqual(diverged_classes([a, b]), {})

    def test_classless_nodes_omitted(self):
        from mpynode.native.spec.divergence import (
            group_nodes_by_class, diverged_classes)

        a = self._mk("divLess1", cls=None, expr="out = 1")
        b = self._mk("divLess2", cls=None, expr="out = 2")
        self.assertEqual(group_nodes_by_class([a, b]), {})
        self.assertEqual(diverged_classes([a, b]), {})

    def test_distinct_classes_do_not_cross_contaminate(self):
        from mpynode.native.spec.divergence import diverged_classes

        # Two consistent Classes, each with identical instances -> no divergence.
        a = self._mk("divX1", cls="Alpha", expr="out = 1")
        b = self._mk("divX2", cls="Alpha", expr="out = 1")
        c = self._mk("divY1", cls="Beta", expr="out = 2")
        d = self._mk("divY2", cls="Beta", expr="out = 2")
        self.assertEqual(diverged_classes([a, b, c, d]), {})

    def test_none_wrappers_are_skipped(self):
        # A bad node name wraps to None; it must not crash detection nor be
        # mistaken for a (class-less/empty) node that hides a real divergence.
        from mpynode.native.spec.divergence import (
            diverged_classes, class_is_diverged, group_nodes_by_class)

        a = self._mk("divNone1", cls="Widget", expr="out = x + 1")
        b = self._mk("divNone2", cls="Widget", expr="out = x + 2")
        # None mixed in with two genuinely-diverged instances -> still diverged.
        self.assertTrue(class_is_diverged([a, None, b]))
        d = diverged_classes([a, None, b])
        self.assertIn("mpynode_user.Widget", d)
        self.assertEqual(len(d["mpynode_user.Widget"]), 2)
        # None never fabricates a group.
        self.assertEqual(list(group_nodes_by_class([None, None])), [])

    def test_end_to_end_plan_forks_over_live_nodes(self):
        from mpynode.native.spec.divergence import diverged_classes, plan_forks

        a = self._mk("divPlanA", cls="Widget", expr="out = x + 1")
        b = self._mk("divPlanB", cls="Widget", expr="out = x + 2")
        plans = plan_forks(diverged_classes([a, b]))
        self.assertEqual(len(plans), 1)
        p = plans[0]
        self.assertEqual(p["class_path"], "mpynode_user.Widget")
        # First variant keeps Widget; the second is forked to Widget2.
        self.assertEqual(p["keep"], ["divPlanA"])
        self.assertEqual(len(p["forks"]), 1)
        self.assertEqual(p["forks"][0]["class_name"], "Widget2")
        self.assertEqual(p["forks"][0]["nodes"], ["divPlanB"])


class TestPlanForks(unittest.TestCase):
    """Pure planner tests -- no Maya, tiny stand-in nodes."""

    class _N:
        def __init__(self, name):
            self._n = name

        def get_name(self):
            return self._n

    def _grp(self, *names):
        return [self._N(n) for n in names]

    def test_three_variants_get_sequential_names(self):
        from mpynode.native.spec.divergence import plan_forks

        diverged = {"mpynode_user.Widget": {
            "h0": self._grp("a1", "a2"),
            "h1": self._grp("b1"),
            "h2": self._grp("c1"),
        }}
        plans = plan_forks(diverged)
        p = plans[0]
        self.assertEqual(p["keep"], ["a1", "a2"])
        self.assertEqual([f["class_name"] for f in p["forks"]],
                         ["Widget2", "Widget3"])
        self.assertEqual(p["forks"][0]["nodes"], ["b1"])
        self.assertEqual(p["forks"][1]["nodes"], ["c1"])

    def test_taken_names_are_skipped(self):
        from mpynode.native.spec.divergence import plan_forks

        diverged = {"mpynode_user.Widget": {
            "h0": self._grp("a1"),
            "h1": self._grp("b1"),
        }}
        # Widget2 already exists in the scene -> fork lands on Widget3.
        plans = plan_forks(diverged, taken_names={"Widget2"})
        self.assertEqual(plans[0]["forks"][0]["class_name"], "Widget3")

    def test_deterministic_across_calls(self):
        from mpynode.native.spec.divergence import plan_forks

        diverged = {"mpynode_user.Widget": {
            "h0": self._grp("a1"), "h1": self._grp("b1"), "h2": self._grp("c1")}}
        self.assertEqual(plan_forks(diverged), plan_forks(diverged))

    def test_non_diverged_class_omitted(self):
        from mpynode.native.spec.divergence import plan_forks

        # A single-variant entry (shouldn't appear in a real divergence map, but
        # be robust) yields no plan.
        self.assertEqual(plan_forks({"mpynode_user.X": {"h0": self._grp("a")}}), [])


class TestSpecLevelDivergence(unittest.TestCase):
    """Spec-dict detection used by the compile controller (pure, no Maya)."""

    def _spec(self, type_name, compute, **kw):
        s = {"suggested": {"node_type_name": type_name}, "compute": compute,
             "inputs": kw.get("inputs", {"x": {}}),
             "outputs": kw.get("outputs", {"out": {}})}
        for k in ("init", "methods", "variables"):
            if k in kw:
                s[k] = kw[k]
        return s

    def test_identical_specs_not_diverged(self):
        from mpynode.native.spec.divergence import (
            diverged_spec_groups, specs_are_identical)

        a = self._spec("widget", "out = x + 1")
        b = self._spec("widget", "out = x + 1")
        self.assertTrue(specs_are_identical(a, b))
        self.assertEqual(diverged_spec_groups([a, b]), {})

    def test_divergent_specs_flagged(self):
        from mpynode.native.spec.divergence import (
            diverged_spec_groups, specs_are_identical)

        a = self._spec("widget", "out = x + 1")
        b = self._spec("widget", "out = x + 2")
        self.assertFalse(specs_are_identical(a, b))
        d = diverged_spec_groups([a, b])
        self.assertIn("widget", d)
        self.assertEqual(len(d["widget"]), 2)

    def test_comment_only_spec_change_not_diverged(self):
        from mpynode.native.spec.divergence import diverged_spec_groups

        a = self._spec("widget", "out = x + 1")
        b = self._spec("widget", "out = x + 1  # tweak")
        self.assertEqual(diverged_spec_groups([a, b]), {})

    def test_distinct_types_do_not_collide(self):
        from mpynode.native.spec.divergence import diverged_spec_groups

        a = self._spec("alpha", "out = 1")
        b = self._spec("beta", "out = 2")
        self.assertEqual(diverged_spec_groups([a, b]), {})

    def test_attr_type_or_array_divergence_flagged(self):
        # Same attr NAMES + same compute, but one input toggled to is_array: a
        # real structural divergence (changes generated C++). The names-only
        # node-level hash misses this; the spec-level hash must catch it.
        from mpynode.native.spec.divergence import (
            diverged_spec_groups, specs_are_identical)

        a = self._spec("widget", "out = x + 1",
                       inputs={"x": {"type": "double", "is_array": False}})
        b = self._spec("widget", "out = x + 1",
                       inputs={"x": {"type": "double", "is_array": True}})
        self.assertFalse(specs_are_identical(a, b))
        d = diverged_spec_groups([a, b])
        self.assertIn("widget", d)
        self.assertEqual(len(d["widget"]), 2)

    def test_same_attr_type_and_array_not_diverged(self):
        from mpynode.native.spec.divergence import diverged_spec_groups

        meta = {"x": {"type": "double", "is_array": False}}
        a = self._spec("widget", "out = x + 1", inputs=dict(meta))
        b = self._spec("widget", "out = x + 1", inputs=dict(meta))
        self.assertEqual(diverged_spec_groups([a, b]), {})

    def test_specs_without_type_name_skipped(self):
        from mpynode.native.spec.divergence import diverged_spec_groups

        a = {"compute": "out = 1"}  # no suggested.node_type_name
        b = {"compute": "out = 2"}
        self.assertEqual(diverged_spec_groups([a, b]), {})


if __name__ == "__main__":
    unittest.main()
