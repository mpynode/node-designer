"""Coexist-and-reroute convert/revert: node_swap primitives (attach/detach) +
the command layer (is_converted, _ConvertToCppCommand, _RevertToPyCommand).

Uses the plugin-provided ``stubCompiled`` / ``stubCompiledLocator`` types (see
``_stub_compiled_plugin``) as the compiled target -- a genuine PLUGIN node type
with a real ``a``/``b``/``c`` attr schema, so the reroute actually transfers
edges (an attr-less target would be a false pass). The interpreted source uses a
stock ``network`` for the pure-primitive tests and a real ``MPyNode`` for the
command tests.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import (
    ensure_plugins_loaded, ensure_stub_compiled_plugin, standalone_init)


def setUpModule():
    standalone_init()


def _abc_net(name=None):
    """A ``network`` with double ``inA``/``inB`` inputs + a double ``outC``
    output -- the same logical attr NAMES as the stub compiled node, so the
    reroute (which connects ``remote -> cpp.<sameAttr>``) transfers."""
    n = mc.createNode("network", name=name) if name else mc.createNode("network")
    mc.addAttr(n, ln="inA", at="double")
    mc.addAttr(n, ln="inB", at="double")
    mc.addAttr(n, ln="outC", at="double")
    return n


class TestAttachCompiledDG(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_stub_compiled_plugin()

    def test_attach_creates_reroutes_links_locks(self):
        from mpynode._base.node_swap import attach_compiled

        src = _abc_net("cx")
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", src + ".inA")   # input (to duplicate)
        mc.setAttr(src + ".inB", 5.0)             # static (to snapshot)
        mc.connectAttr(src + ".outC", down + ".i")  # output (to move)

        cpp, dropped = attach_compiled(src, "stubCompiled")

        self.assertTrue(mc.objExists(cpp))
        self.assertEqual(mc.nodeType(cpp), "stubCompiled")
        # input duplicated (both src and cpp fan off up.o) ...
        self.assertTrue(mc.isConnected(up + ".o", cpp + ".inA"))
        self.assertTrue(mc.isConnected(up + ".o", src + ".inA"))
        # static value snapshotted ...
        self.assertAlmostEqual(mc.getAttr(cpp + ".inB"), 5.0)
        # output MOVED (cpp drives downstream; src no longer does) ...
        self.assertTrue(mc.isConnected(cpp + ".outC", down + ".i"))
        self.assertFalse(mc.isConnected(src + ".outC", down + ".i"))
        # message link established ...
        self.assertTrue(mc.isConnected(
            src + ".mpyCompiledLink", cpp + ".mpyInterpretedLink"))
        # cpp is locked against casual deletion.
        self.assertEqual(mc.lockNode(cpp, q=True, lock=True), [True])
        self.assertEqual(dropped, [])


class TestDetachCompiledDG(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_stub_compiled_plugin()

    def test_detach_moves_back_and_deletes(self):
        from mpynode._base.node_swap import attach_compiled, detach_compiled

        src = _abc_net("cx")
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", src + ".inA")
        mc.connectAttr(src + ".outC", down + ".i")
        cpp, _ = attach_compiled(src, "stubCompiled")

        dropped = detach_compiled(cpp, src)

        self.assertFalse(mc.objExists(cpp))                     # cpp deleted
        self.assertTrue(mc.isConnected(src + ".outC", down + ".i"))  # output back
        self.assertFalse(                                       # link attr removed
            mc.attributeQuery("mpyCompiledLink", node=src, exists=True))
        self.assertTrue(mc.isConnected(up + ".o", src + ".inA"))  # input untouched
        self.assertEqual(dropped, [])


class TestIsConverted(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_stub_compiled_plugin()

    def test_is_converted_and_linked_node_track_the_link(self):
        from mpynode._base.node_swap import attach_compiled, detach_compiled
        from mpynode._base.commands import (
            is_converted, linked_compiled_node)

        src = _abc_net("cx")
        self.assertFalse(is_converted(src))
        self.assertIsNone(linked_compiled_node(src))

        cpp, _ = attach_compiled(src, "stubCompiled")
        self.assertTrue(is_converted(src))
        self.assertEqual(linked_compiled_node(src), cpp)

        detach_compiled(cpp, src)
        self.assertFalse(is_converted(src))
        self.assertIsNone(linked_compiled_node(src))


class TestLocatorCoexist(unittest.TestCase):
    """The locator path: same-parent create (co-located gizmo) + lodVisibility
    idle-safety. A stock ``locator`` shape drives the ``isAType("locator")``
    branch without needing the mPy plugin."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_stub_compiled_plugin()

    def _loc(self):
        loc = mc.createNode("locator")  # returns the shape; auto-parents a xform
        mc.addAttr(loc, ln="inA", at="double")
        mc.addAttr(loc, ln="inB", at="double")
        mc.addAttr(loc, ln="outC", at="double")
        return loc

    def test_attach_parents_under_same_transform_and_hides(self):
        from mpynode._base.node_swap import attach_compiled

        loc = self._loc()
        parent = mc.listRelatives(loc, parent=True, fullPath=True)[0]
        cpp, _ = attach_compiled(loc, "stubCompiledLocator")
        # C++ locator lives under the SAME transform (co-located gizmo) ...
        self.assertEqual(
            mc.listRelatives(cpp, parent=True, fullPath=True)[0], parent)
        # ... the idle Python locator is hidden via lodVisibility ...
        self.assertEqual(mc.getAttr(loc + ".lodVisibility"), 0)
        # ... snapshotted for exact restore ...
        self.assertTrue(
            mc.attributeQuery("mpyPreConvertLodVis", node=loc, exists=True))
        # ... and the C++ locator stays visible.
        self.assertEqual(mc.getAttr(cpp + ".lodVisibility"), 1)

    def test_detach_restores_lod_and_deletes_only_the_cpp_shape(self):
        from mpynode._base.node_swap import attach_compiled, detach_compiled

        loc = self._loc()
        parent = mc.listRelatives(loc, parent=True, fullPath=True)[0]
        cpp, _ = attach_compiled(loc, "stubCompiledLocator")
        detach_compiled(cpp, loc)
        self.assertFalse(mc.objExists(cpp))          # only the cpp shape deleted
        self.assertTrue(mc.objExists(loc))           # python shape survives
        self.assertTrue(mc.objExists(parent))        # shared transform survives
        self.assertEqual(mc.getAttr(loc + ".lodVisibility"), 1)  # restored
        self.assertFalse(
            mc.attributeQuery("mpyPreConvertLodVis", node=loc, exists=True))

    def test_attach_reports_when_lodvis_not_settable(self):
        from mpynode._base.node_swap import attach_compiled, detach_compiled

        loc = self._loc()
        # lodVisibility driven from upstream is not settable, so the idle
        # Python locator cannot be hidden with setAttr.
        drv = mc.createNode("network")
        mc.addAttr(drv, ln="v", at="bool")
        mc.setAttr(drv + ".v", 1)
        mc.connectAttr(drv + ".v", loc + ".lodVisibility")

        cpp, dropped = attach_compiled(loc, "stubCompiledLocator")

        # No misleading snapshot is written when the hide could not happen ...
        self.assertFalse(
            mc.attributeQuery("mpyPreConvertLodVis", node=loc, exists=True))
        # ... and the failure is surfaced, not silently swallowed.
        self.assertTrue(any("lodVisibility" in d for d in dropped))
        # Revert is a clean no-op on lodVisibility (nothing was changed).
        detach_compiled(cpp, loc)
        self.assertEqual(mc.getAttr(loc + ".lodVisibility"), 1)


class TestAttachCompiledDeformer(unittest.TestCase):
    """A deformer (``geometryFilter``) was excluded from coexist-convert on the
    grounds that it is chain-based with no output plug to move. It has
    ``outputGeometry[]`` -- an output plug like any other -- so the reroute is
    the ordinary one. Stock ``deltaMush`` stands in for both sides: a genuine
    geometryFilter carrying the nested ``weightList[i].weights[j]`` multi, and
    no ``.bundle`` dependency.

    NOT ``cluster``/``softMod``: those are driven by a HANDLE transform, and
    ``duplicate_inputs`` duplicates ``clusterXforms``/``matrix`` onto the
    sibling, so both deformers end up owned by the same handle -- deleting the
    sibling then makes Maya delete the handle, which deletes the original. That
    is native handle machinery; the mPy deformer types have no handle."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _mushed_sphere(self):
        t = mc.polySphere(r=1.0, sx=6, sy=6)[0]
        return mc.deltaMush(t)[0]

    def test_attach_moves_output_geometry_and_carries_painted_weights(self):
        from mpynode._base.node_swap import attach_compiled

        src = self._mushed_sphere()
        mc.setAttr(src + ".envelope", 0.6)
        for i in (0, 3, 7):
            mc.setAttr("%s.weightList[0].weights[%d]" % (src, i), 0.25)
        downstream = mc.listConnections(src + ".outputGeometry", plugs=True,
                                        d=True, s=False)
        upstream = mc.listConnections(src + ".input[0].inputGeometry",
                                      plugs=True, s=True, d=False)
        self.assertTrue(downstream, "fixture must have a downstream chain")

        cpp, _dropped = attach_compiled(src, "deltaMush")

        # the deformation chain now runs through the C++ sibling ...
        self.assertEqual(
            mc.listConnections(cpp + ".outputGeometry", plugs=True,
                               d=True, s=False), downstream)
        self.assertFalse(
            mc.listConnections(src + ".outputGeometry", plugs=True,
                               d=True, s=False),
            "the idle Python deformer must no longer drive downstream")
        # ... fanning off the SAME upstream geometry ...
        self.assertEqual(
            mc.listConnections(cpp + ".input[0].inputGeometry", plugs=True,
                               s=True, d=False), upstream)
        # ... static values carried ...
        self.assertAlmostEqual(mc.getAttr(cpp + ".envelope"), 0.6)
        # ... and the nested weightList multi survived: the DOTTED
        # listChildren case that used to raise on
        # `deltaMush1.weightList[0].weightList.weights`.
        self.assertEqual(
            [mc.getAttr("%s.weightList[0].weights[%d]" % (cpp, i))
             for i in (0, 3, 7)], [0.25, 0.25, 0.25])

    def test_detach_restores_the_python_deformer_in_the_chain(self):
        from mpynode._base.node_swap import attach_compiled, detach_compiled

        src = self._mushed_sphere()
        downstream = mc.listConnections(src + ".outputGeometry", plugs=True,
                                        d=True, s=False)
        cpp, _ = attach_compiled(src, "deltaMush")
        detach_compiled(cpp, src)
        self.assertFalse(mc.objExists(cpp))
        self.assertEqual(
            mc.listConnections(src + ".outputGeometry", plugs=True,
                               d=True, s=False), downstream)


class TestTransformCoexist(unittest.TestCase):
    """A DAG transform gets an INPUTS-ONLY convert: the sibling is built under
    the same parent and fans off the same upstream, but the outputs stay put and
    the children stay parented to the interpreted node. Moving `worldMatrix`
    while parentage still pointed at the Python node would silently half-convert
    the scene, so the user is warned instead (``downstream_dependents``) and gets
    to decide.

    Uses a real ``mPyTransform`` as BOTH sides: the interpreted node auto-builds a
    ``fourByFourMatrix`` opm relay, so the sibling builds one too -- which is the
    only way to exercise the companion-relay cleanup on detach."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _rigged_transform(self):
        grp = mc.createNode("transform", name="rigRoot")
        xf = mc.createNode("mPyTransform", name="pyXf", parent=grp)
        mc.createNode("transform", name="kidA", parent=xf)
        sink = mc.createNode("network"); mc.addAttr(sink, ln="m", at="matrix")
        mc.connectAttr(xf + ".worldMatrix[0]", sink + ".m", force=True)
        drv = mc.createNode("transform", name="driver")
        # translate->translate on purpose: driving an angle from a distance
        # makes Maya splice in a unitConversion, so `drv` would no longer be
        # the upstream and the assertions would test the wrong edge.
        mc.connectAttr(drv + ".translateY", xf + ".translateY", force=True)
        return xf, drv, sink

    def _relays(self):
        return {n for n in (mc.ls(type="fourByFourMatrix") or [])}

    def test_attach_duplicates_inputs_but_leaves_outputs_and_children(self):
        from mpynode._base.node_swap import attach_compiled

        xf, drv, sink = self._rigged_transform()
        cpp, dropped = attach_compiled(xf, "mPyTransform")

        self.assertEqual(dropped, [])
        self.assertEqual(mc.listRelatives(cpp, parent=True), ["rigRoot"],
                         "the sibling belongs beside the node it mirrors")
        # input duplicated onto the sibling, source keeps it ...
        self.assertTrue(mc.isConnected(drv + ".translateY", cpp + ".translateY"))
        self.assertTrue(mc.isConnected(drv + ".translateY", xf + ".translateY"))
        # ... but downstream and parentage are UNTOUCHED.
        self.assertTrue(mc.isConnected(xf + ".worldMatrix[0]", sink + ".m"),
                        "the Python transform must keep driving downstream")
        self.assertEqual(
            [k.split("|")[-1] for k in
             (mc.listRelatives(xf, children=True, fullPath=True) or [])],
            ["kidA"])
        self.assertFalse(mc.listRelatives(cpp, children=True) or [])

    def test_attach_leaves_the_sibling_driving_its_own_relay(self):
        """`offsetParentMatrix` is driven by the node's OWN auto-built relay, so
        it looks like an ordinary incoming edge. Force-duplicating the source's
        would displace the sibling's -- the compiled node would then mirror the
        interpreted matrix instead of computing its own, and the relay it built
        on creation would be orphaned."""
        from mpynode._base.node_swap import attach_compiled

        xf, _drv, _sink = self._rigged_transform()
        py_relay = mc.listConnections(xf + ".offsetParentMatrix",
                                      s=True, d=False)
        cpp, _ = attach_compiled(xf, "mPyTransform")

        cpp_relay = mc.listConnections(cpp + ".offsetParentMatrix",
                                       s=True, d=False)
        self.assertTrue(cpp_relay, "the sibling must keep a relay of its own")
        self.assertNotEqual(cpp_relay, py_relay,
                            "the sibling must not be driven by the source's relay")
        self.assertEqual(
            mc.listConnections(xf + ".offsetParentMatrix", s=True, d=False),
            py_relay, "and the source must keep its own")

    def test_detach_deletes_the_siblings_private_relay(self):
        """Without the cleanup the sibling's auto-built relay is orphaned and
        `_outLocalFlat` stays cross-wired into it -- one leaked node per
        convert/revert cycle."""
        from mpynode._base.node_swap import attach_compiled, detach_compiled

        xf, _drv, sink = self._rigged_transform()
        before = self._relays()
        cpp, _ = attach_compiled(xf, "mPyTransform")
        self.assertTrue(self._relays() - before,
                        "fixture must actually build a sibling relay")

        detach_compiled(cpp, xf)

        self.assertFalse(mc.objExists(cpp))
        self.assertEqual(self._relays(), before, "sibling relay must be gone")
        self.assertTrue(mc.isConnected(xf + ".worldMatrix[0]", sink + ".m"))
        self.assertEqual(
            [k.split("|")[-1] for k in
             (mc.listRelatives(xf, children=True, fullPath=True) or [])],
            ["kidA"])

    def test_downstream_dependents_reports_what_will_not_be_rewired(self):
        from mpynode._base.node_swap import downstream_dependents

        xf, _drv, sink = self._rigged_transform()
        edges, children = downstream_dependents(xf)
        self.assertTrue(any(r == sink + ".m" for _l, r in edges), edges)
        self.assertEqual([c.split("|")[-1] for c in children], ["kidA"])
        self.assertFalse(
            [r for _l, r in edges if mc.nodeType(r.split(".")[0])
             == "fourByFourMatrix"],
            "the node's own opm relay is private wiring, not user downstream")


if __name__ == "__main__":
    unittest.main()
