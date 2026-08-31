"""Array OUTPUT write uses a fresh SIZED ``MArrayDataBuilder``.

``emit_attr._array_write_lines`` used to retrieve the datablock's EXISTING
builder (``_outArr.builder()``), which copies every element already in the
array before the loop overwrites it. Constructing a fresh builder sized to the
value count skips that copy.

Measured on Maya 2026 / arm64 / -O3 with two otherwise-identical MPxNode types
(fixed-size double array output, one eval per perturbed input):

    N=1000     21.1us -> 15.2us   1.39x
    N=10000   222.0us -> 94.5us   2.35x
    N=100000 3091.4us -> 961.5us  3.22x

FULL-REWRITE SEMANTICS: elements the compute does not write this evaluation
are DROPPED, where ``builder()`` kept them. This is a deliberate behaviour
change (see the module note in emit_attr).

One case is EXCEPTED: a compute that wrote NOTHING at all. A zero-sized builder
is a full rewrite to EMPTY, so a guard-false evaluation (procrustesCluster and
procrustesTags fill their output only when clusters/rest/deformed are all
non-empty) would WIPE the array. The rewrite is skipped when the buffer is
empty; ``setAllClean`` still runs.

Skipping the rewrite is NOT the same as matching the interpreter, and this
module used to assert that it was. Every api2 base PRE-SEEDS an array output to
the per-type default before compute runs, so an evaluation that assigns nothing
publishes DEFAULTS -- it does not republish the previous evaluation's values.
Measured on the interpreted reference for the spec below (2026-08-20):

    gate=True  [1,2,3]  -> [(0, 1.0), (1, 2.0), (2, 3.0)]
    gate=False [1,2,3]  -> [(0, 0.0), (1, 0.0), (2, 0.0)]   <-- defaults
    gate=True  [4,5]    -> [(0, 4.0), (1, 5.0), (2, 3.0)]   <-- stale tail (T94)

So the empty branch writes the per-type default to each EXISTING element
(element count untouched, which is what keeps a compiled count of 0 unreachable
for ``verify._is_stale_tail_shrink``). Holding the previous matrices instead was
measured as a 5.255 divergence on procrustesTags: clearing every ``clusterTags``
element froze the compiled rivets at their last pose while the interpreted ones
released to identity.

The SHORT-write tail drop on the last line above is a separate, DELIBERATE
divergence (T14/T94, see ``_api2.helpers.write_multi_plug_value``) and is still
asserted as such below.
"""

from __future__ import annotations

import os
import shutil
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _arr_spec(t):
    """A plain MPxNode with one array input and one array output of type ``t``."""
    return {
        "schema_version": 1, "source_node": "arrProbe", "mpy_type": "mPyNode",
        "suggested": {"node_type_name": "arrProbe", "class_name": "ArrProbe",
                      "type_id": "0x00070311", "mpx_base": "MPxNode"},
        "inputs": {"aIn": {"type": t, "is_array": True}},
        "outputs": {"aOut": {"type": t, "is_array": True}},
        "compute": "pass\n", "init": "", "affects": "all",
        "portability": {"portable": True, "blockers": [], "warnings": [],
                        "reads_image_file": False},
    }


class TestArrayOutputSizedBuilder(unittest.TestCase):
    """Pure codegen -- no Maya needed."""

    def test_write_lines_use_sized_builder(self):
        from mpynode.native.compiler import emit_attr
        got = emit_attr._array_write_lines(
            {"member": "aAOut", "plug": "aOut",
             "meta": {"type": "double", "is_array": True}})
        self.assertIn(
            "            MArrayDataBuilder _b(&data, aAOut, "
            "(unsigned)out_aAOut.size());", got)
        self.assertNotIn("        MArrayDataBuilder _b = _outArr.builder();",
                         got)

    def test_write_lines_keep_the_commit_pair(self):
        """The sized builder replaces ONLY how the builder is obtained: the
        handle, the per-element addElement loop and the set/setAllClean commit
        must all survive, or the output never reaches the plug."""
        from mpynode.native.compiler import emit_attr
        got = emit_attr._array_write_lines(
            {"member": "aAOut", "plug": "aOut",
             "meta": {"type": "double", "is_array": True}})
        self.assertIn(
            "        MArrayDataHandle _outArr = data.outputArrayValue(aAOut);",
            got)
        self.assertIn("                MDataHandle eh = _b.addElement((unsigned)_i);",
                      got)
        self.assertIn("            _outArr.set(_b);", got)
        self.assertIn("        _outArr.setAllClean();", got)

    def test_write_lines_skip_the_rewrite_when_nothing_was_written(self):
        """An EMPTY buffer must not reach ``_outArr.set``: a sized builder of
        zero elements is a full rewrite to empty, which would WIPE the array on a
        guard-false evaluation. ``setAllClean`` stays outside the guard."""
        from mpynode.native.compiler import emit_attr
        got = emit_attr._array_write_lines(
            {"member": "aAOut", "plug": "aOut",
             "meta": {"type": "double", "is_array": True}})
        self.assertIn("        if (!out_aAOut.empty()) {", got)
        self.assertLess(got.index("        if (!out_aAOut.empty()) {"),
                        got.index("            _outArr.set(_b);"),
                        "the empty guard must wrap the builder + set")
        self.assertGreater(got.index("        _outArr.setAllClean();"),
                           got.index("        }"),
                           "setAllClean must stay outside the empty guard")

    def test_write_lines_default_the_existing_elements_when_nothing_written(self):
        """Skipping the rewrite is not enough -- the elements that survive must
        be reset to the attribute DEFAULT, which is what the interpreted node
        publishes (its base pre-seeds the output before compute). Without this
        the compiled node republishes the previous evaluation's values.

        The loop walks ``elementCount()`` and writes in place, so it must NOT
        touch the element count: ``verify._is_stale_tail_shrink`` relies on a
        compiled count of 0 being unreachable while the empty guard stands.
        """
        from mpynode.native.compiler import emit_attr
        got = emit_attr._array_write_lines(
            {"member": "aAOut", "plug": "aOut",
             "meta": {"type": "double", "is_array": True}})
        self.assertIn("        } else {", got)
        self.assertIn("            double _dflt = 0.0;", got)
        self.assertIn("            unsigned _ne = _outArr.elementCount();", got)
        self.assertIn("                eh.setDouble(_dflt);", got)
        # in-place walk, never a builder -- a builder here would resize.
        self.assertNotIn("_b.addElement",
                         got[got.index("        } else {"):])
        self.assertGreater(got.index("        _outArr.setAllClean();"),
                           got.index("        } else {"),
                           "setAllClean must still run after the default fill")

    def test_every_array_type_emits_the_sized_builder(self):
        """Every ``_ARRAY_OK`` element type routes through the same writer --
        incl. quaternion, whose block also declares an MFnCompoundAttribute."""
        from mpynode.native import compiler as codegen
        for t in sorted(codegen._ARRAY_OK):
            cpp = codegen.generate_cpp(_arr_spec(t), for_port=False)
            self.assertIn("MArrayDataBuilder _b(&data, aAOut, "
                          "(unsigned)out_aAOut.size());", cpp,
                          "%s: array output not written via a sized builder" % t)
            self.assertNotIn("MArrayDataBuilder _b = _outArr.builder();", cpp,
                             "%s: still retrieves the existing builder" % t)
            self.assertIn("if (!out_aAOut.empty()) {", cpp,
                          "%s: empty buffer would wipe the array" % t)
            self.assertIn("} else {", cpp,
                          "%s: no default fill on a guard-false evaluation" % t)
            self.assertIn("unsigned _ne = _outArr.elementCount();", cpp,
                          "%s: empty branch does not walk existing elements" % t)


# --------------------------------------------------------------------------- #
# Runtime proof. The three cases above pin the EMITTED TEXT only; nothing there
# shows that a short write really drops the tail, nor that a compute which
# writes NOTHING leaves the array alone. These compile a real plug-in and drive
# it. SKIP (never fail) without a C++ compiler / devkit.

# Same shape as procrustesCluster: the array output is filled INSIDE a guard, so
# a guard-false evaluation reaches the unconditional finalize with an empty
# buffer.
_RT_COMPUTE = "if self.gate:\n    self.aOut = self.aIn\n"
_RT_NAME = "arrOutRt"
_RT_TYPE_ID = "0x00070570"


def _running_maya_root():
    import sys
    from mpynode.native.toolchain import toolchain

    seeds = [os.environ.get("MAYA_LOCATION") or "",
             os.path.dirname(os.path.abspath(sys.executable))]
    for seed in seeds:
        cur = seed
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(toolchain.maya_include_dir(cur), "maya")):
                return cur
            cur = os.path.dirname(cur)
    return None


def _have_toolchain():
    return bool((shutil.which("clang++") or shutil.which("g++"))
                and _running_maya_root())


class TestArrayOutputRuntime(unittest.TestCase):
    """Compile the guarded array-output node once, then drive it."""

    _tmp = None
    _bundle = None

    @classmethod
    def setUpClass(cls):
        if not _have_toolchain():
            return
        import maya.cmds as mc
        import mpynode
        from mpynode.native.spec import spec_extractor
        from mpynode.native.toolchain import compile_controller as cc

        mc.file(new=True, force=True)
        src = mc.createNode("mPyNode", name="arrOutRtSrc")
        w = mpynode.wrap_node(src)
        w.add_input_attr("aIn", "double", is_array=True)
        w.add_input_attr("gate", "bool")
        w.add_output_attr("aOut", "double", is_array=True)
        w.set_compute_expression(_RT_COMPUTE)
        spec = spec_extractor.extract_spec(src)
        spec["suggested"]["node_type_name"] = _RT_NAME
        spec["suggested"]["class_name"] = "ArrOutRt"
        spec["suggested"]["type_id"] = _RT_TYPE_ID

        cls._tmp = tempfile.mkdtemp()
        res = cc.compile_plugin([spec], _RT_NAME, cls._tmp, strict=True,
                                verify=False, reuse_cache=False)
        if not res["ok"]:
            raise AssertionError("build failed: %s" % res.get("errors"))
        cls._bundle = res["bundle_path"]
        mc.file(new=True, force=True)
        mc.loadPlugin(cls._bundle)

    @classmethod
    def tearDownClass(cls):
        if not cls._bundle:
            return
        import maya.cmds as mc
        try:
            mc.file(new=True, force=True)
            mc.unloadPlugin(os.path.basename(cls._bundle))
        except Exception:
            pass
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        if not self._bundle:
            self.skipTest("no C++ compiler or Maya devkit for the running mayapy")
        import maya.cmds as mc

        mc.file(new=True, force=True)
        self.node = mc.createNode(_RT_NAME)

    def _drive(self, values, gate=True):
        """Set ``aIn`` to exactly ``values`` (dropping any surplus element),
        evaluate ``aOut`` and return its elements as (index, value) pairs."""
        import maya.cmds as mc
        import maya.api.OpenMaya as om2

        for i, v in enumerate(values):
            mc.setAttr("%s.aIn[%d]" % (self.node, i), float(v))
        for i in (mc.getAttr(self.node + ".aIn", multiIndices=True) or []):
            if i >= len(values):
                mc.removeMultiInstance("%s.aIn[%d]" % (self.node, i), b=True)
        mc.setAttr(self.node + ".gate", bool(gate))

        sel = om2.MSelectionList()
        sel.add(self.node)
        p = om2.MFnDependencyNode(sel.getDependNode(0)).findPlug("aOut", False)
        n = p.evaluateNumElements()
        return [(p.elementByPhysicalIndex(i).logicalIndex(),
                 p.elementByPhysicalIndex(i).asDouble()) for i in range(n)]

    def test_short_write_drops_the_tail(self):
        """FULL-REWRITE: after a 3-element write, a 2-element write leaves TWO
        elements -- the third is gone, not stale. This is what the sized builder
        buys and what ``_outArr.builder()`` could not do."""
        self.assertEqual(self._drive([1.0, 2.0, 3.0]),
                         [(0, 1.0), (1, 2.0), (2, 3.0)])
        self.assertEqual(self._drive([4.0, 5.0]), [(0, 4.0), (1, 5.0)])

    def test_guard_false_keeps_the_elements_and_publishes_defaults(self):
        """A compute that writes NOTHING this evaluation must KEEP its elements
        and publish the per-type DEFAULT on each -- what the interpreted node
        does, because the api2 base pre-seeds the output before compute runs.

        This used to assert the previous values survived. They must not: on
        procrustesTags that froze every rivet at its last pose (divergence
        5.255) when the user cleared the ``clusterTags`` list, where the
        interpreted node released to identity.
        """
        self.assertEqual(self._drive([1.0, 2.0, 3.0]),
                         [(0, 1.0), (1, 2.0), (2, 3.0)])
        self.assertEqual(self._drive([1.0, 2.0, 3.0], gate=False),
                         [(0, 0.0), (1, 0.0), (2, 0.0)])
        # ... and it recovers: the next assigning evaluation republishes.
        self.assertEqual(self._drive([1.0, 2.0, 3.0]),
                         [(0, 1.0), (1, 2.0), (2, 3.0)])

    def test_guard_false_matches_the_interpreted_node(self):
        """The literals above are a MEASUREMENT, so measure them here rather
        than trusting the transcription: drive an interpreted mPyNode with the
        same compute and compare. A hardcoded expectation is what let the
        divergence sit in this file as a passing test.
        """
        import maya.cmds as mc
        import mpynode

        src = mc.createNode("mPyNode")
        w = mpynode.wrap_node(src)
        w.add_input_attr("aIn", "double", is_array=True)
        w.add_input_attr("gate", "bool")
        w.add_output_attr("aOut", "double", is_array=True)
        w.set_compute_expression(_RT_COMPUTE)

        def drive_interp(values, gate):
            import maya.api.OpenMaya as om2
            for i, v in enumerate(values):
                mc.setAttr("%s.aIn[%d]" % (src, i), float(v))
            for i in (mc.getAttr(src + ".aIn", multiIndices=True) or []):
                if i >= len(values):
                    mc.removeMultiInstance("%s.aIn[%d]" % (src, i), b=True)
            mc.setAttr(src + ".gate", bool(gate))
            sel = om2.MSelectionList()
            sel.add(src)
            p = om2.MFnDependencyNode(sel.getDependNode(0)).findPlug("aOut",
                                                                     False)
            n = p.evaluateNumElements()
            return [(p.elementByPhysicalIndex(i).logicalIndex(),
                     p.elementByPhysicalIndex(i).asDouble())
                    for i in range(n)]

        for values, gate in (([1.0, 2.0, 3.0], True),
                             ([1.0, 2.0, 3.0], False),
                             ([1.0, 2.0, 3.0], True)):
            self.assertEqual(self._drive(values, gate=gate),
                             drive_interp(values, gate),
                             "compiled vs interpreted diverge at gate=%s" % gate)


if __name__ == "__main__":
    unittest.main()
