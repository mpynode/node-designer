"""Scene-open reserved-name collision scan (``scene_callbacks``).

Per LANDMINE 4 this is the ONLY diagnostic for a collision no authoring-time
site can see (a compute can create a stored var under any name at runtime), so
it has to keep working: fire on a colliding scene, stay SILENT on a clean one,
and never raise.
"""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# A name that genuinely SHADOWS on mPyMesh. The buffer names (points / colors
# / outMesh / ...) are output-scratch -- a real plug wins on read there, so
# they COEXIST with a user attr and are deliberately NOT reserved. ``time`` is
# a context READ slot with no backing plug, so it is the collision this scan
# has to keep catching.
_MESH_COLLIDING_NAME = "time"


def _make_mesh_with_attr(name, direction="input"):
    """mPyMesh carrying a user attr called ``name``.

    Built inside an attr-surgery window: the authoring guard downgrades to a
    warning there (the legacy-scene path), so this still builds the colliding
    attr that a pre-guard .ma file would carry."""
    from mpynode._common.lifecycle import scene_state
    from mpynode.wrappers.mpy_mesh import MPyMesh

    mesh = MPyMesh.create(skip_selection=True)
    scene_state.begin_attr_surgery()
    try:
        if direction == "input":
            mesh.add_input_attr(name, "float")
        else:
            mesh.add_output_attr(name, "float")
    finally:
        scene_state.end_attr_surgery()
    return mesh.get_name()


def _make_node_with_var(name):
    from mpynode._common.storedvars import stored_vars_api
    from mpynode.wrappers._mpy_node import MPyNode

    node = MPyNode.create(skip_selection=True)
    try:
        stored_vars_api.add_variable(node.get_name(), name, 1.0)
    except Exception:
        # If the authoring guard hardens from warn to raise, a LEGACY .ma still
        # carries the name -- which is the case this scan exists for. Seed the
        # registry plug directly so the test keeps covering it.
        mc.setAttr(node.get_name() + "._storedVarNames", name, type="string")
    return node.get_name()


class TestReservedCollisionScan(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._common.lifecycle import scene_callbacks

        self.cb = scene_callbacks

    def test_clean_scene_is_silent(self):
        _make_mesh_with_attr("wobble")
        _make_node_with_var("counter")
        self.assertEqual(self.cb._scan_reserved_name_collisions(), [])
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            self.assertEqual(self.cb._warn_reserved_name_collisions(), 0)
        self.assertEqual(buf.getvalue(), "")

    def test_empty_scene_is_silent(self):
        self.assertEqual(self.cb._scan_reserved_name_collisions(), [])

    def test_colliding_attr_is_reported(self):
        mesh = _make_mesh_with_attr(_MESH_COLLIDING_NAME)
        hits = self.cb._scan_reserved_name_collisions()
        self.assertEqual(len(hits), 1, hits)
        node_type, node, kind, name, reason = hits[0]
        self.assertEqual((node_type, node, kind, name),
                         ("mPyMesh", mesh, "input attr",
                          _MESH_COLLIDING_NAME))
        self.assertIn("framework READ slot", reason)

    def test_colliding_output_attr_is_reported(self):
        _make_mesh_with_attr("time", direction="output")
        kinds = {(h[2], h[3]) for h in self.cb._scan_reserved_name_collisions()}
        self.assertIn(("output attr", "time"), kinds)

    def test_colliding_stored_var_is_reported(self):
        node = _make_node_with_var("get_compute_locals")
        hits = self.cb._scan_reserved_name_collisions()
        self.assertEqual(len(hits), 1, hits)
        self.assertEqual(hits[0][:4],
                         ("mPyNode", node, "stored var", "get_compute_locals"))

    def test_reserved_prefix_is_reported(self):
        _make_node_with_var("_psp_sneaky")
        hits = self.cb._scan_reserved_name_collisions()
        self.assertEqual(len(hits), 1, hits)
        self.assertIn("_psp_", hits[0][4])

    def test_one_consolidated_report_not_one_per_name(self):
        _make_mesh_with_attr(_MESH_COLLIDING_NAME)
        _make_node_with_var("get_compute_locals")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            self.assertEqual(self.cb._warn_reserved_name_collisions(), 2)
        text = buf.getvalue()
        # ONE header, one trailing newline -- not a wall of separate warnings.
        self.assertEqual(text.count("[reserved_names]"), 1, text)
        self.assertIn("2 reserved-name collision(s) on 2 node(s)", text)
        self.assertIn(_MESH_COLLIDING_NAME, text)
        self.assertIn("get_compute_locals", text)

    def test_report_is_capped(self):
        limit = self.cb._COLLISION_REPORT_LIMIT
        hits = [("mPyMesh", "m%d" % i, "input attr",
                 _MESH_COLLIDING_NAME, "because")
                for i in range(limit + 5)]
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            with mock.patch.object(
                self.cb, "_scan_reserved_name_collisions", return_value=hits
            ):
                self.assertEqual(
                    self.cb._warn_reserved_name_collisions(), limit + 5)
        text = buf.getvalue()
        self.assertIn("... and 5 more", text)
        self.assertEqual(text.count("input attr"), limit)

    def test_scan_neither_evaluates_nor_modifies(self):
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(skip_selection=True)
        node.add_output_attr("out_x", "float")
        _make_mesh_with_attr(_MESH_COLLIDING_NAME)
        mc.file(modified=False)

        seen     = []
        real_get = mc.getAttr

        def _spy(*args, **kwargs):
            if args:
                seen.append(str(args[0]).split(".", 1)[-1])
            return real_get(*args, **kwargs)

        with mock.patch.object(mc, "getAttr", _spy):
            self.cb._scan_reserved_name_collisions()
        # Only the three internal topology plugs are read -- no OUTPUT plug is
        # ever pulled, so the scan cannot trigger a compute.
        self.assertEqual(set(seen),
                         {"_inputAttrs", "_outputAttrs", "_storedVarNames"})
        self.assertFalse(mc.file(q=True, modified=True))

    def test_scan_survives_a_broken_attr_map(self):
        mesh = _make_mesh_with_attr(_MESH_COLLIDING_NAME)
        mc.setAttr(mesh + "._outputAttrs", "{not json", type="string")
        # The unreadable map is skipped; the readable one still reports.
        hits = self.cb._scan_reserved_name_collisions()
        self.assertEqual([h[3] for h in hits], [_MESH_COLLIDING_NAME])


class TestSceneOpenEmitsReport(unittest.TestCase):
    """End-to-end through the real kAfterOpen callback."""

    def test_open_of_a_colliding_scene_warns(self):
        import os
        import tempfile

        from mpynode._common.lifecycle import scene_callbacks

        mc.file(new=True, force=True)
        _make_mesh_with_attr(_MESH_COLLIDING_NAME)
        _make_node_with_var("get_compute_locals")
        path = os.path.join(tempfile.mkdtemp(prefix="mpynode-rn-"), "s.ma")
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)

        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            mc.file(path, open=True, force=True)
        text = buf.getvalue()
        self.assertIn("[reserved_names] scene-open scan:", text)
        self.assertIn("%r" % _MESH_COLLIDING_NAME, text)
        self.assertIn("'get_compute_locals'", text)

        # ...and the open itself completed normally (never blocked).
        self.assertEqual(len(mc.ls(type="mPyMesh") or []), 1)
        self.assertEqual(len(mc.ls(type="mPyNode") or []), 1)

        mc.file(new=True, force=True)
        buf2 = io.StringIO()
        with contextlib.redirect_stderr(buf2):
            scene_callbacks._on_scene_opened(None)
        self.assertNotIn("[reserved_names]", buf2.getvalue())
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()
