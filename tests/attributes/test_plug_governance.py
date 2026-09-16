"""Managed-plug governance: an mpynode only surfaces plugs it manages.

An attribute is reachable through ``self.<name>`` / ``node.<name>`` only if it is
MANAGED:

  * STATIC -- part of the node type's registered surface (declared in the
    plug-in's ``initialize()`` or inherited from MPxNode / MFnDagNode /
    MPxDeformerNode). ``outMesh``, ``worldMatrix``, ``envelope``, ``nodeState``,
    ``_timeIn`` are all static. Nobody "added" them, so nobody can smuggle one in.
  * DYNAMIC and recorded -- added through ``add_input_attr`` /
    ``add_output_attr`` (Node Designer, the ``.mpn`` loader, the Python API), which
    records the name in the hidden ``_inputAttrs`` / ``_outputAttrs`` map.

A DYNAMIC attribute that is NOT in the map was created behind the framework's
back (a bare ``cmds.addAttr``). It does not surface. The contract is that an
unmanaged plug is indistinguishable from a plug that does not exist -- reads fall
through to stored vars / init bindings exactly as an unknown name does, and
writes land in user storage instead of the plug.
"""

from __future__ import annotations

import unittest

from maya import cmds
# api1 -- the whole plugs package is api1, and Maya rejects an MObject of one
# flavour in the other's signatures, so PlugProxy / plug_governance must be
# handed api1 MObjects.
import maya.OpenMaya as om

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _mobj(node):
    sel = om.MSelectionList()
    sel.add(node)
    mobj = om.MObject()
    sel.getDependNode(0, mobj)
    return mobj


class _GovernanceCase(unittest.TestCase):
    """Shared fixture: a fresh mPyMesh carrying one of each attribute origin."""

    def setUp(self):
        cmds.file(new=True, force=True)
        from mpynode.wrappers.mpy_mesh import MPyMesh

        self.nd   = MPyMesh.create(name="govMesh")
        self.node = self.nd.get_name()
        # MANAGED: recorded in _inputAttrs by the framework's own API.
        self.nd.add_input_attr("managedIn", "float")
        self.nd.add_input_attr("managedVec", "vector")
        self.nd.add_output_attr("probeOut", "float")
        cmds.setAttr(self.node + ".managedIn", 3.5)
        # UNMANAGED: a bare Maya command, behind the framework's back. Given a
        # DISTINCT short name so the tests can prove both spellings are denied.
        cmds.addAttr(self.node, longName="smuggled", shortName="smug",
                     attributeType="double")
        cmds.setAttr(self.node + ".smuggled", 41.5)

    def _probe(self, body):
        """Run ``body`` in a compute; it must assign a float to self.probeOut."""
        self.nd.set_compute_expression(body)
        cmds.dgdirty(self.node + ".probeOut")
        return cmds.getAttr(self.node + ".probeOut")


class TestUnmanagedPlugDoesNotSurface(_GovernanceCase):

    def test_raw_addattr_is_not_readable_from_the_expression(self):
        """The reported defect: a bare cmds.addAttr plug read fine as 41.5."""
        out = self._probe(
            "try:\n"
            "    v = self.smuggled\n"
            "    self.probeOut = 1.0\n"   # reachable -> FAIL
            "except AttributeError:\n"
            "    self.probeOut = 0.0\n"   # invisible -> PASS
        )
        self.assertEqual(out, 0.0)

    def test_unmanaged_is_denied_under_its_short_name_too(self):
        """A spelling-based gate would leak here: ``smug`` is the same
        attribute as ``smuggled`` and resolves just as well."""
        out = self._probe(
            "try:\n"
            "    v = self.smug\n"
            "    self.probeOut = 1.0\n"
            "except AttributeError:\n"
            "    self.probeOut = 0.0\n"
        )
        self.assertEqual(out, 0.0)

    def test_unmanaged_is_indistinguishable_from_nonexistent(self):
        """Same code path as an unknown name: fall through to stored vars."""
        out = self._probe(
            "self.smuggled = 7.25\n"          # -> user storage, NOT the plug
            "self.probeOut = self.smuggled\n"  # -> reads it back from storage
        )
        self.assertEqual(out, 7.25)
        # ...and the real plug was never touched.
        self.assertEqual(cmds.getAttr(self.node + ".smuggled"), 41.5)

    def test_unmanaged_not_readable_through_the_injected_node_handle(self):
        """``node`` is a second PlugProxy in the namespace; gating only
        SelfProxy would leave it wide open."""
        out = self._probe(
            "try:\n"
            "    v = node.smuggled\n"
            "    self.probeOut = 1.0\n"
            "except AttributeError:\n"
            "    self.probeOut = 0.0\n"
        )
        self.assertEqual(out, 0.0)

    def test_unmanaged_not_reachable_through_get_plug_proxy(self):
        """get_plug_proxy() is a public method, so SelfProxy.__getattr__ never
        runs -- the gate has to live in PlugProxy to cover it."""
        out = self._probe(
            "try:\n"
            "    v = self.get_plug_proxy().smuggled\n"
            "    self.probeOut = 1.0\n"
            "except AttributeError:\n"
            "    self.probeOut = 0.0\n"
        )
        self.assertEqual(out, 0.0)

    def test_unmanaged_geometry_not_reachable_through_geometry_data(self):
        """geometry_data(name) does its own by-name resolve, bypassing
        __getattr__ entirely, and returns the highest-value payload."""
        sph = cmds.polySphere(constructionHistory=False)[0]
        cmds.addAttr(self.node, longName="smuggledGeo", dataType="mesh")
        cmds.connectAttr(sph + ".outMesh", self.node + ".smuggledGeo")
        out = self._probe(
            "d = self.get_plug_proxy().geometry_data('smuggledGeo')\n"
            "self.probeOut = 0.0 if d is None else 1.0\n"
        )
        self.assertEqual(out, 0.0)

    def test_unmanaged_compound_and_its_children_are_denied(self):
        """The parent-chain rule exists so framework-created compound children
        resolve via the recorded parent. It must not become a back door: a
        wholly unmanaged compound is denied at the parent AND the child.

        (A child cannot be smuggled into a MANAGED compound -- Maya rejects
        ``addAttr -parent`` on an existing one with "Too many children on this
        compound", so a managed compound's children are always the
        framework's own.)"""
        cmds.addAttr(self.node, longName="rogueVec", attributeType="double3")
        for ax in "XYZ":
            cmds.addAttr(self.node, longName="rogueVec" + ax,
                         attributeType="double", parent="rogueVec")
        cmds.setAttr(self.node + ".rogueVecX", 5.5)
        out = self._probe(
            "try:\n"
            "    v = self.rogueVecX\n"
            "    self.probeOut = 1.0\n"
            "except AttributeError:\n"
            "    self.probeOut = 0.0\n"
        )
        self.assertEqual(out, 0.0)
        self.assertEqual(cmds.getAttr(self.node + ".rogueVecX"), 5.5)

    def test_unmanaged_write_does_not_reach_the_plug(self):
        self._probe("self.smuggled = 99.5\nself.probeOut = 1.0\n")
        self.assertEqual(cmds.getAttr(self.node + ".smuggled"), 41.5)


class TestManagedPlugsStillSurface(_GovernanceCase):

    def test_managed_input_is_readable(self):
        self.assertEqual(self._probe("self.probeOut = self.managedIn\n"), 3.5)

    def test_compound_child_of_a_managed_input_is_readable(self):
        """_inputAttrs records only the PARENT of a compound. The children are
        framework-created and must resolve via the parent."""
        cmds.setAttr(self.node + ".managedVecX", 2.25)
        self.assertEqual(self._probe("self.probeOut = self.managedVecX\n"), 2.25)

    def test_static_native_plug_is_readable(self):
        """``debug_mode`` is declared by the plug-in's initialize(), not added
        by anyone, so it is managed by definition.

        (Not ``outMesh``: that one is inherited from the stock ``mesh`` node
        AND is this node's own computed output, so reading it from inside the
        compute re-enters the DG and blows the stack. Its verdict is asserted
        directly in TestGovernanceInvalidation instead.)"""
        out = self._probe(
            "self.probeOut = 0.0 if self.debug_mode else 1.0\n")
        self.assertEqual(out, 1.0)

    def test_static_maya_base_plug_is_readable(self):
        self.assertEqual(self._probe("self.probeOut = float(self.nodeState)\n"), 0.0)

    def test_short_name_of_a_static_attr_still_resolves(self):
        """Every plug resolves by long OR short name, so the gate has to test
        the resolved ATTRIBUTE. ``nodeState`` is static; its short name is
        ``nds``, and that spelling must keep working."""
        self.assertEqual(self._probe("self.probeOut = float(self.nds)\n"), 0.0)


class TestGovernanceInvalidation(_GovernanceCase):

    def test_promoting_an_attr_to_managed_flips_the_verdict(self):
        """A cached deny must not outlive the edit that makes it managed."""
        from mpynode._common.plugs import plug_governance

        mobject = _mobj(self.node)
        attr    = om.MFnDependencyNode(mobject).attribute("smuggled")
        self.assertFalse(plug_governance.is_managed(mobject, attr, "smuggled"))

        self.nd.add_input_attr("adopted", "float")
        attr2 = om.MFnDependencyNode(mobject).attribute("adopted")
        self.assertTrue(plug_governance.is_managed(mobject, attr2, "adopted"))

    def test_undoing_an_add_input_attr_revokes_the_verdict(self):
        """Maya restores ``_inputAttrs`` by undoing our setAttr -- our Python
        never runs and the node is never destroyed, so without the undo
        callback the cached ALLOW would outlive the attribute."""
        from mpynode._common.plugs import plug_governance

        cmds.undoInfo(state=True, infinity=True)
        mobject = _mobj(self.node)

        cmds.undoInfo(openChunk=True)
        self.nd.add_input_attr("temporary", "float")
        cmds.undoInfo(closeChunk=True)

        attr = om.MFnDependencyNode(mobject).attribute("temporary")
        self.assertTrue(plug_governance.is_managed(mobject, attr, "temporary"))

        cmds.undo()

        # If the attribute survived the undo as a plain dynamic attr, it must
        # now be DENIED; if Maya removed it outright, it cannot resolve at all.
        try:
            attr = om.MFnDependencyNode(mobject).attribute("temporary")
            gone = attr.isNull()
        except Exception:
            gone = True
        if not gone:
            self.assertFalse(
                plug_governance.is_managed(mobject, attr, "temporary"))

    def test_invalidation_callbacks_are_installed_on_first_use(self):
        """The undo/redo hook self-installs; if it silently failed to register
        the cache would have no way to learn about an undo."""
        from mpynode._common.plugs import plug_governance

        mobject = _mobj(self.node)
        attr    = om.MFnDependencyNode(mobject).attribute("managedIn")
        plug_governance.is_managed(mobject, attr, "managedIn")
        self.assertTrue(plug_governance._installed)

    def test_static_attrs_never_consult_the_map(self):
        """The map load is the expensive half; a static attr must short-circuit
        before it, so the locator draw path never pays for it."""
        from mpynode._common.plugs import plug_governance

        mobject = _mobj(self.node)
        attr    = om.MFnDependencyNode(mobject).attribute("outMesh")
        plug_governance.invalidate()
        self.assertTrue(plug_governance.is_managed(mobject, attr, "outMesh"))
        self.assertFalse(plug_governance._map_is_loaded(mobject))


class TestForeignNodesAreUnaffected(unittest.TestCase):
    """The rule is about mpynodes. A plain Maya node has no managed map and
    must not be gated -- otherwise every PlugProxy on a transform breaks."""

    def setUp(self):
        cmds.file(new=True, force=True)

    def test_plain_transform_dynamic_attr_still_reads(self):
        from mpynode._common.plugs.plug_proxy import PlugProxy

        xf = cmds.createNode("transform", name="plainXform")
        cmds.addAttr(xf, longName="whatever", attributeType="double")
        cmds.setAttr(xf + ".whatever", 8.75)
        self.assertEqual(PlugProxy(_mobj(xf)).whatever, 8.75)


if __name__ == "__main__":
    unittest.main()
