"""_CreateGeoForPlugCommand: build and wire the shape a geometry plug wants.

A ``time`` input can offer to plug in ``time1``; a mesh / NURBS plug had no
equivalent, so every one started as four steps in the Outliner -- create the
shape, find it under its transform, work out which of its many geometry plugs
is the right one, connect. This is that convenience, off the plug's own
right-click menu.

The two ends need different nodes, which is the part worth pinning:

* an INPUT gets a PRIMITIVE, because an empty shape would connect and then
  feed the plug nothing;
* an OUTPUT gets an EMPTY shape to draw into -- and, for a mesh, one that is
  in a shading group, or it is in the scene but invisible.

Every call the command makes is itself undoable, so one Ctrl+Z takes the whole
thing back and ``undoIt``/``redoIt`` stay no-ops (the ``_CreateNodeCommand``
contract).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


GEO = ("mesh", "nurbsCurve", "nurbsSurface")


class TestCreateGeoForPlug(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="geo")
        self.name = self.node.get_name()

    def _run(self, attr, attr_type, direction, is_array=False):
        from mpynode._base.commands import (_CreateGeoForPlugCommand,
                                            run_undoable)

        return run_undoable(_CreateGeoForPlugCommand(
            self.name, attr, attr_type, direction, is_array=is_array))

    # -- inputs --------------------------------------------------------

    def test_an_input_is_driven_by_real_geometry(self):
        # The plug must read something. A primitive has geometry in it; an
        # empty shape would wire up and deliver an empty mesh.
        for t in GEO:
            self.node.add_input_attr("in_" + t, t)
            made = self._run("in_" + t, t, "input")
            src  = mc.listConnections("%s.in_%s" % (self.name, t),
                                      source=True, destination=False,
                                      plugs=True) or []
            self.assertEqual(len(src), 1, t)
            self.assertIn(src[0].split(".", 1)[1].split("[")[0],
                          ("worldMesh", "worldSpace"), t)
            self.assertTrue(mc.objExists(made), t)

    def test_the_input_primitive_is_not_empty(self):
        self.node.add_input_attr("m", "mesh")
        self._run("m", "mesh", "input")
        shape = (mc.listConnections(self.name + ".m", shapes=True) or [None])[0]
        self.assertTrue(mc.polyEvaluate(shape, face=True) > 0)

    # -- outputs -------------------------------------------------------

    def test_an_output_gets_an_empty_shape_to_draw_into(self):
        for t in GEO:
            self.node.add_output_attr("out_" + t, t)
            made = self._run("out_" + t, t, "output")
            dst  = mc.listConnections("%s.out_%s" % (self.name, t),
                                      source=False, destination=True,
                                      plugs=True) or []
            self.assertEqual(len(dst), 1, t)
            self.assertIn(dst[0].split(".", 1)[1], ("inMesh", "create"), t)
            self.assertTrue(mc.objExists(made), t)

    def test_an_output_mesh_is_shaded(self):
        # Without a shading group it draws as nothing at all, which reads as
        # "the node is broken" rather than "the mesh has no shader".
        self.node.add_output_attr("om", "mesh")
        self._run("om", "mesh", "output")
        shape = (mc.listConnections(self.name + ".om", shapes=True) or [None])[0]
        sgs   = mc.listConnections(shape, type="shadingEngine") or []
        self.assertIn("initialShadingGroup", sgs)

    def test_the_output_shape_follows_the_setup_naming(self):
        # Same names each geometry node type's own setup gives its render
        # shape, so a node built either way reads the same in the Outliner.
        self.node.add_output_attr("om", "mesh")
        made = self._run("om", "mesh", "output")
        self.assertEqual(made, "omRender")
        self.assertEqual(mc.listRelatives(made, shapes=True), ["omRenderShape"])

    # -- arrays --------------------------------------------------------

    def test_an_array_plug_takes_the_next_free_element(self):
        # Maya rejects a connection to the bare multi parent, and a second
        # call must not clobber the first.
        self.node.add_input_attr("arr", "mesh", is_array=True)
        self._run("arr", "mesh", "input", is_array=True)
        self._run("arr", "mesh", "input", is_array=True)
        self.assertEqual(mc.getAttr(self.name + ".arr", multiIndices=True),
                         [0, 1])

    # -- undo / guards -------------------------------------------------

    def test_one_undo_takes_back_the_node_and_the_wire(self):
        self.node.add_input_attr("u", "mesh")
        before = set(mc.ls(type="transform"))
        self._run("u", "mesh", "input")
        self.assertTrue(mc.listConnections(self.name + ".u", source=True))
        mc.undo()
        self.assertEqual(set(mc.ls(type="transform")), before)
        self.assertFalse(mc.listConnections(self.name + ".u", source=True))

    def test_a_non_geometry_type_is_refused(self):
        from mpynode._base.commands import _CreateGeoForPlugCommand

        with self.assertRaises(ValueError):
            _CreateGeoForPlugCommand(self.name, "f", "float", "input")

    def test_a_bad_direction_is_refused(self):
        from mpynode._base.commands import _CreateGeoForPlugCommand

        with self.assertRaises(ValueError):
            _CreateGeoForPlugCommand(self.name, "m", "mesh", "sideways")

    def test_every_geometry_attr_type_is_covered(self):
        # The menu offers this for exactly the types the Add Attribute dialog
        # calls geometry; a new one there must land here too.
        from mpynode._base.commands import _CreateGeoForPlugCommand

        self.assertEqual(sorted(_CreateGeoForPlugCommand.GEO_TYPES), sorted(GEO))
        self.assertEqual(sorted(_CreateGeoForPlugCommand.PRIMITIVES), sorted(GEO))


if __name__ == "__main__":
    unittest.main()
