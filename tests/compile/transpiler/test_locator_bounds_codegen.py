"""A COMPILED locator must report the extent it draws, like the interpreted one.

``MPyLocator`` measures its drawing in ``evaluateDrawItems`` and answers
``boundingBox()`` with it, so Frame Selected fits the gizmo instead of
MPxLocatorNode's default unit cube (see tests/nodes/test_locator_bounds.py).
The emitted node had no such override, so a compiled gizmo kept answering
"unbounded" -- framing it zoomed to the whole scene, and the same node behaved
differently depending on whether it had been compiled.

The C++ cannot cache the extent on the node the way Python caches it on
``self``: the expression runs in the draw override, which the node cannot
reach. It goes in a per-node map instead, keyed by hashCode like the hover soup
and the tween state -- and, like those, it has to be evicted when the node dies
so a later node reusing the freed hash does not inherit a dead extent.
"""
from __future__ import annotations

import unittest


def _cpp(hover: bool = False, stored_vars: bool = True):
    from mpynode.native import compiler as codegen
    from tests.compile.transpiler.test_native_codegen import (
        _locator_spec__locator_hover_codegen)

    spec = _locator_spec__locator_hover_codegen(hover)
    if not stored_vars:
        # No hover AND no stored vars: the hover/stored-var service block is
        # not emitted at all for this node (`if needs_hover or svars`), which
        # is the shape Widget Showcase has.
        spec = dict(spec)
        spec.pop("variables", None)
        spec["compute"] = "self.draw = DrawCircle(radius=2.0)\n"
    return codegen._generate_locator_cpp(spec)


class TestCompiledLocatorReportsItsExtent(unittest.TestCase):

    def setUp(self):
        self.cpp = _cpp(False)

    def test_the_node_declares_itself_bounded(self):
        self.assertIn("bool isBounded() const override { return true; }", self.cpp)
        # Defined INSIDE the class: the draw-side globals live in an anonymous
        # namespace, and a member cannot be defined there (MSVC C2888).
        self.assertIn("MBoundingBox boundingBox() const override {", self.cpp)

    def test_the_box_comes_from_the_measured_extent(self):
        self.assertIn("g_bbox.find(MObjectHandle(thisMObject()).hashCode());",
                      self.cpp)
        # Nothing measured yet -> the stock answer, matching the interpreted
        # node's fallback before its first draw.
        self.assertIn("if (it == g_bbox.end()) return MPxLocatorNode::boundingBox();",
                      self.cpp)

    def test_it_is_measured_once_per_draw_not_per_query(self):
        # Maya asks for the box during selection and framing; running the
        # expression there would be re-entrant.
        self.assertIn("_setBBox(_bbHash, _bb, _anyBB);", self.cpp)
        # Keyed off its own handle, not the hover path's _nodeHash, which a
        # locator without hover never declares.
        self.assertIn("const unsigned _bbHash = MObjectHandle(objPath.node()).hashCode();",
                      self.cpp)

    def test_the_rules_match_command_bounds(self):
        # Same three judgement calls the Python helper makes.
        self.assertIn("if (i < d.lineWorld.size() && d.lineWorld[i]) continue;",
                      self.cpp)            # world-space items are not object space
        self.assertIn("if (pg.worldSpace) continue;", self.cpp)
        self.assertIn("out.expand(MPoint(c.x - r, c.y - r, c.z - r));",
                      self.cpp)            # a shape grows by its radius
        self.assertIn("for (size_t i = 0; i < d.textPos.size(); ++i)", self.cpp)

    def test_nothing_drawn_clears_the_entry(self):
        # A gizmo that stops drawing must not keep reporting its old extent.
        self.assertIn("if (any) g_bbox[hash] = bb; else g_bbox.erase(hash);",
                      self.cpp)

    def test_the_map_is_declared_before_the_body_that_reads_it(self):
        # C++ is order-sensitive: the definition of boundingBox() must follow
        # the map, or the plug-in does not compile at all.
        self.assertLess(self.cpp.index("std::map<unsigned, MBoundingBox> g_bbox"),
                        self.cpp.index("MBoundingBox boundingBox() const override {"))

    def test_a_dead_node_does_not_leave_its_extent_behind(self):
        self.assertIn("g_bbox.erase(hash);", self.cpp)     # per-node removal
        self.assertIn("g_bbox.clear();", self.cpp)         # scene change

    def test_the_draw_override_stays_unbounded(self):
        """Load-bearing pairing, not an oversight.

        The NODE reports a real box, which is what framing and bbox picking
        read. The draw OVERRIDE keeps ``isBounded`` false, so VP2 never culls
        the drawing -- if it culled on the node's box, a gizmo drawing far from
        its origin would be culled before it had ever been measured, and a box
        that only fills on draw would never fill. The interpreted override does
        not declare bounds either.
        """
        self.assertIn(
            "bool isBounded(const MDagPath&, const MDagPath&) const override "
            "{ return false; }", self.cpp)

    def test_a_hover_locator_gets_it_too(self):
        # The hover build emits a different set of globals; the extent is not
        # tied to that opt-in.
        hov = _cpp(True)
        self.assertIn("MBoundingBox boundingBox() const override {", hov)
        self.assertIn("static bool _drawnBounds(", hov)


class TestALocatorWithNoHoverAndNoStoredVars(unittest.TestCase):
    """The shape that broke: no hover service block is emitted for it at all.

    The helpers first went inside that block, so this node called
    ``_drawnBounds`` / ``_setBBox`` with nothing defining them and keyed the
    extent off a ``_nodeHash`` only the hover path declares -- C3861 twice and
    C2065 once, from a real MSVC run. The earlier tests all passed, because
    the shared fixture carries stored vars and so always emits the block.
    """

    def setUp(self):
        self.cpp = _cpp(hover=False, stored_vars=False)

    def test_the_service_block_really_is_absent(self):
        # Guard on the premise -- if this node starts emitting the block, this
        # whole class stops testing what it was written for.
        self.assertNotIn("g_hoverTris", self.cpp)

    def test_the_helpers_are_defined_anyway(self):
        self.assertIn("static bool _drawnBounds(", self.cpp)
        self.assertIn("static void _setBBox(", self.cpp)

    def test_they_are_defined_before_prepareForDraw_calls_them(self):
        self.assertLess(self.cpp.index("static void _setBBox("),
                        self.cpp.index("_setBBox(_bbHash"))

    def test_the_hash_does_not_come_from_the_hover_path(self):
        self.assertIn("const unsigned _bbHash = MObjectHandle(objPath.node()).hashCode();",
                      self.cpp)

    def test_mobjecthandle_is_included(self):
        # MApiNamespace.h only forward-declares it -- reads as C2027 otherwise.
        self.assertIn("#include <maya/MObjectHandle.h>", self.cpp)


if __name__ == "__main__":
    unittest.main()
