"""Interpreted user outputs compute after a scene is opened, imported or
referenced, as the compiled twin's do, with no input touched.

Measured 2026-10-15 on 6e8f90b: after a reload the interpreted node read each
user output's DEFAULT until one of its inputs changed, while the compiled twin
(All Templates Plugin) computed it. Ouch's color read (0, 0, 0) for
(0, 1, 0), Hex Attribute's output None, Bubble Sort's text None, Mesh Maze's
solutionSteps 0 for 20. Every API 2.0 compute family was affected: mPyNode,
mPyConstraint, mPyFile, mPyMesh, mPyNurbsCurve, mPyNurbsSurface. On an open
11 of 35 probe cases were stale, on an import or a reference 8.

Cause: the file reader restores input values without calling
``setDependentsDirty``, and that override is the only thing that dirties a
dynamic user output. ``dgdirty`` cannot repair it afterwards: it has no effect
on an output no propagation has reached. The fix,
``dirty_affects.dirty_file_read_outputs``, replays the skipped propagation for
every node the read built, once the read is over. Nothing computes until an
output is pulled.

Not covered, because they were already right after a reload: the transform
and deformer families write their user outputs while they evaluate, and the
locator has no DG compute.
"""
from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

import maya.OpenMaya as om1
import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_FAMILIES = ("mPyNode", "mPyConstraint", "mPyFile", "mPyMesh",
             "mPyNurbsCurve", "mPyNurbsSurface")
_EXPR = ("self.outD = self.a * 3.0\n"
         "self.outV = (self.a, self.a + 1.0, self.a + 2.0)\n")
_RELOADS = ("open", "import", "reference", "reference inside an open")


def _family_node(node_type, name):
    """A node with user input ``a`` = 5 and user outputs ``outD`` = 15 and
    ``outV`` = (5, 6, 7)."""
    import mpynode

    node = mc.createNode(node_type, name=name, skipSelect=True)
    w    = mpynode.wrap_node(node)
    w.add_input_attr("a", "double")
    w.add_output_attr("outD", "double")
    w.add_output_attr("outV", "double3")
    w.set_compute_expression(_EXPR)
    mc.setAttr(node + ".a", 5.0)
    return node


def _template_node(rel):
    from mpynode._common.io import mpn_io

    path    = os.path.join(_paths.ROOT, "templates", rel, "template.mpn")
    payload = mpn_io.load_mpn(path, trusted=True)
    return mpn_io.deserialize_node(payload, skip_selection=True).get_name()


class _ReloadCase(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        self.tmp = tempfile.mkdtemp(prefix="mpynode-reopen-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(mc.file, new=True, force=True)

    def _save(self, name="scene.ma"):
        path = os.path.join(self.tmp, name)
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        return path

    def _reload(self, path, how):
        """Reload the saved scene into an empty one; return the name prefix."""
        mc.file(new=True, force=True)
        if how == "open":
            mc.file(path, open=True, force=True)
            return ""
        if how == "import":
            mc.file(path, i=True, namespace="imp", force=True)
            return "imp:"
        mc.file(path, reference=True, namespace="ref")
        if how == "reference inside an open":
            parent = self._save("parent.ma")
            mc.file(new=True, force=True)
            mc.file(parent, open=True, force=True)
        return "ref:"


class TestEveryFamilyComputesAfterAReload(_ReloadCase):
    """The compound child is read first: a pull on the child alone must
    compute too."""

    def test_user_outputs(self):
        for how in _RELOADS:
            mc.file(new=True, force=True)
            for node_type in _FAMILIES:
                node = _family_node(node_type, "re_" + node_type)
                self.assertEqual(mc.getAttr(node + ".outD"), 15.0)
            prefix = self._reload(self._save(), how)
            for node_type in _FAMILIES:
                node = prefix + "re_" + node_type
                with self.subTest(reload=how, family=node_type):
                    self.assertEqual(mc.getAttr(node + ".outVY"), 6.0)
                    self.assertEqual(mc.getAttr(node + ".outD"), 15.0)

    def test_a_downstream_node_reads_its_upstream_after_an_open(self):
        up   = _family_node("mPyNode", "reUp")
        down = _family_node("mPyNode", "reDown")
        mc.connectAttr(up + ".outD", down + ".a")
        self.assertEqual(mc.getAttr(down + ".outD"), 45.0)
        self._reload(self._save(), "open")
        self.assertEqual(mc.getAttr("reDown.outD"), 45.0)


class TestTemplatesMatchTheCompiledTwin(_ReloadCase):
    """The value the compiled twin (All Templates Plugin, built from this
    tree) gives with the same inputs, before the save and after the open
    alike, measured 2026-10-15. Interpreted, after an open, on 6e8f90b:
    (0, 0, 0), None and None."""

    _HEX = ("44 52 41 47 20 4d 45 20 41 52 4f 55 4e 44 21 0a 58 3a 20 34 2e 35"
            " 0a 59 3a 20 35 2e 32 35 0a 5a 3a 20 36 2e 30 0a")

    def test_after_an_open(self):
        ouch = _template_node("MPyNode/Ouch")
        mc.setAttr(ouch + ".angle", 75.0)
        hexa = _template_node("MPyNode/Hex Attribute")
        mc.setAttr(hexa + ".inPosition", 4.5, 5.25, 6.0)
        bubble = _template_node("MPyNode/Bubble Sort")
        expected = {ouch + ".color": [(0.0, 1.0, 0.0)],
                    hexa + ".output": self._HEX,
                    bubble + ".text": "SORTED!!!"}
        for plug, value in expected.items():
            self.assertEqual(mc.getAttr(plug), value)
        self._reload(self._save(), "open")
        for plug, value in expected.items():
            with self.subTest(plug=plug):
                self.assertEqual(mc.getAttr(plug), value)


class TestNoExtraCompute(_ReloadCase):
    """Nothing computes while the file is read or right after it; an output
    computes once on its first pull and not on the next one; an import leaves
    the nodes already in the scene clean."""

    def _count(self):
        """Record (node name, reading a file) for every mPyNode compute."""
        import maya.api.OpenMaya as om

        from mpynode._api2._mpy_node import MPyNode

        calls = []
        real  = MPyNode.compute

        def counted(node, plug, block):
            calls.append((om.MFnDependencyNode(node.thisMObject()).name(),
                          om1.MFileIO.isReadingFile()))
            return real(node, plug, block)

        patcher = mock.patch.object(MPyNode, "compute", counted)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def test_open(self):
        _family_node("mPyNode", "reCount")
        path  = self._save()
        calls = self._count()
        self._reload(path, "open")
        self.assertEqual(calls, [])
        self.assertEqual(mc.getAttr("reCount.outD"), 15.0)
        self.assertEqual(len(calls), 1)
        mc.getAttr("reCount.outD")
        self.assertEqual(len(calls), 1)

    def test_import_into_a_live_scene(self):
        live = _family_node("mPyNode", "reLive")
        path = self._save()
        self.assertEqual(mc.getAttr(live + ".outD"), 15.0)
        calls = self._count()
        mc.file(path, i=True, namespace="imp", force=True)
        self.assertEqual(calls, [])
        self.assertEqual(mc.getAttr(live + ".outD"), 15.0)
        self.assertEqual(calls, [], "the live node was dirtied by the import")
        self.assertEqual(mc.getAttr("imp:reLive.outD"), 15.0)
        self.assertEqual([name for name, _reading in calls], ["imp:reLive"])


class TestTheReloadStaysSilent(_ReloadCase):
    """The replay writes nothing a user can see: the opened scene is not
    flagged modified, a reference records no edit, and a suspended node is
    left alone (default output, as the compiled node before any evaluation)."""

    def test_open_is_not_flagged_modified(self):
        _family_node("mPyFile", "reMod")
        self._reload(self._save(), "open")
        self.assertFalse(mc.file(q=True, modified=True))

    def test_a_reference_records_no_edit(self):
        _family_node("mPyNode", "reEdit")
        prefix = self._reload(self._save(), "reference")
        self.assertEqual(mc.getAttr(prefix + "reEdit.outD"), 15.0)
        ref_node = mc.referenceQuery(prefix + "reEdit", referenceNode=True)
        self.assertEqual(mc.referenceQuery(ref_node, editStrings=True), [])

    def test_a_suspended_node_is_left_alone(self):
        node = _family_node("mPyNode", "reIdle")
        mc.setAttr(node + ".nodeState", 1)
        self._reload(self._save(), "open")
        self.assertEqual(mc.getAttr("reIdle.outD"), 0.0)


class TestOneNodeTheReplayCannotWrite(_ReloadCase):
    """A node whose replay plug has an incoming connection refuses the write.
    It keeps its default and is named in a warning; the nodes read after it
    still compute. With one modifier for every node, its failed write stopped
    the batch, and the 2 nodes after it read 0.0 (measured 2026-10-15)."""

    def test_the_other_nodes_compute(self):
        for tag in ("A", "Wired", "B", "C"):
            _family_node("mPyNode", "re" + tag)
        src = mc.createNode("mPyNode", name="reSrc", skipSelect=True)
        mc.addAttr(src, longName="strOut", dataType="string")
        mc.connectAttr(src + ".strOut", "reWired._profileSnapshotData",
                       force=True)
        path = self._save()
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self._reload(path, "open")
        for name in ("reA", "reB", "reC"):
            with self.subTest(node=name):
                self.assertEqual(mc.getAttr(name + ".outD"), 15.0)
        self.assertIn("1 node(s) keep their user outputs' defaults",
                      err.getvalue())
        self.assertIn(": reWired", err.getvalue())


if __name__ == "__main__":
    unittest.main()
