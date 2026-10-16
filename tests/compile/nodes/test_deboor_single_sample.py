"""De Boor Spline with a single sample reads the last CV, interpreted and compiled.

With one sample the template's compute spaced its samples by
``float(i) / (n - 1)``: the interpreted node raised ZeroDivisionError and
``samples[0]`` read (0, 0, 0). The compiled node read the last CV: its lowered
loop divides in double (0 / 0 is NaN, so every basis weight is 0) and the write
after the loop sets the last sample to the last CV; the shipped final sends
n < 2 down that same lowered loop. The interpreted node decides, and here it
was the one that was wrong, so the template's compute now guards the division:
a single sample sits at the end of the curve and gets the last CV.

Stage 1 moved on 2 rows (the template and its All Templates copy) and the
guard was spliced into 00_baseline. The optimizer rounds rewrote compute(), so
the final, its source, rounds 01-02 and the All Templates source keep the stage
1 before the guard until they are re-optimized. Pinned here: the template and
its build specs, the stage-1 lineage, exactly which files keep the older stamp,
and the interpreted reference.
"""
from __future__ import annotations

import json
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_TPL   = os.path.join(_paths.ROOT, "templates", "MPyNode", "De Boor Spline")
_BUILD = os.path.join(_TPL, "build")
_ALLT  = os.path.join(_paths.ROOT, "templates", "All Templates Plugin")

# The stage 1 the optimizer rounds were built from, before the guard.
_OLD_STAMP = "09c7d56e4491"
# The lineage files whose compute() an optimizer round rewrote: the guard was
# not spliced into them, so they keep the older stamp until re-optimized.
# test_node_state_parity, test_node_state_array_affects and
# test_array_output_grow still check their nodeState gate, state edge and grow
# block.
_KEPT = {
    "templates/MPyNode/De Boor Spline/build/spline/spline.cpp",
    "templates/MPyNode/De Boor Spline/build/source/spline.cpp",
    "templates/MPyNode/De Boor Spline/build/stages/spline/3_optimized/"
    "01_cache_sparse_basis.cpp",
    "templates/MPyNode/De Boor Spline/build/stages/spline/3_optimized/"
    "02_direct_handle_io.cpp",
    "templates/All Templates Plugin/build/source/spline.cpp",
}
_GUARD = (
    "        nl_u = (double)(nd::at1(nl_kv, (-((int64_t)1))));\n"
    "        if (((nl_n > (int64_t)1))) {\n"
    "            nl_u = ((((double)((double)((double)(nl_i)))) / ((double)"
    "((nl_n - (int64_t)1)))) * (double)(nd::at1(nl_kv, (-((int64_t)1)))));\n"
    "        }\n")
# Why the kept files already read the last CV: n < 2 takes the lowered loop,
# whose last write is the last CV.
_FAST = "bool fast = (c >= 1 && degree >= 0 && n >= 2);"
_LAST_CV = ("nd::assign(nd::slice(ndin_self_samples, {nd::Sl::at((-((int64_t)1)))"
            "}), nd::slice(ndin_self_cv, {nd::Sl::at((-((int64_t)1)))}));")


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read().replace("\r\n", "\n")


def _rel(path):
    return os.path.relpath(path, _paths.ROOT).replace(os.sep, "/")


def _stamp(text):
    m = re.search(r"^// build: ([0-9a-f]{12})", text, re.M)
    return m.group(1) if m else None


def _lineage(build):
    out = []
    for folder, _dirs, files in os.walk(os.path.join(build, "stages", "spline")):
        out += [os.path.join(folder, f) for f in files
                if f.endswith(".cpp") and f != "1_transpiled.cpp"]
    for p in (os.path.join(build, "spline", "spline.cpp"),
              os.path.join(build, "source", "spline.cpp")):
        if os.path.isfile(p):
            out.append(p)
    return sorted(out)


def _spline_row(manifest):
    with open(manifest, encoding="utf-8") as fh:
        rows = [r for r in json.load(fh)["nodes"] if r["type_name"] == "spline"]
    assert len(rows) == 1, manifest
    return rows[0]


class TestTemplateAndSpecs(unittest.TestCase):
    """The build records regenerate stage 1 from the template's compute."""

    def test_every_build_spec_carries_the_template_compute(self):
        with open(os.path.join(_TPL, "template.mpn"), encoding="utf-8") as fh:
            expr = json.load(fh)["data"]["expression"]
        self.assertIn("    if n > 1:\n", expr)
        for man in (os.path.join(_BUILD, "manifest.json"),
                    os.path.join(_ALLT, "build", "manifest.json"),
                    os.path.join(_ALLT, "reports", "mega_manifest.json")):
            with self.subTest(manifest=_rel(man)):
                self.assertEqual(_spline_row(man)["spec"]["compute"], expr)


class TestShippedLineage(unittest.TestCase):
    """Stage 1 and 00_baseline carry the guard; the optimizer rounds and the
    final keep the older stamp, and read the last CV without it."""

    def test_stage1_and_the_baseline_carry_the_guard(self):
        s1 = _read(os.path.join(_BUILD, "stages", "spline", "1_transpiled.cpp"))
        self.assertEqual(s1.count(_GUARD), 1)
        self.assertEqual(
            _read(os.path.join(_ALLT, "build", "stages", "spline",
                               "1_transpiled.cpp")), s1)
        self.assertEqual(
            _read(os.path.join(_BUILD, "stages", "spline", "3_optimized",
                               "00_baseline.cpp")), s1)

    def test_exactly_the_optimized_files_keep_the_older_stamp(self):
        kept, current = set(), set()
        for build in (_BUILD, os.path.join(_ALLT, "build")):
            stamp = _stamp(_read(os.path.join(build, "stages", "spline",
                                              "1_transpiled.cpp")))
            self.assertNotEqual(stamp, _OLD_STAMP)
            for p in _lineage(build):
                (kept if _stamp(_read(p)) != stamp else current).add(_rel(p))
        self.assertEqual(kept, _KEPT)
        self.assertEqual(current, {
            "templates/MPyNode/De Boor Spline/build/stages/spline/3_optimized/"
            "00_baseline.cpp"})
        for rel in sorted(_KEPT):
            with self.subTest(file=rel):
                self.assertEqual(_stamp(_read(os.path.join(_paths.ROOT, rel))),
                                 _OLD_STAMP)

    def test_the_kept_files_send_one_sample_down_the_lowered_loop(self):
        for rel in sorted(_KEPT):
            text = _read(os.path.join(_paths.ROOT, rel))
            with self.subTest(file=rel):
                self.assertNotIn(_GUARD, text)
                self.assertEqual(text.count(_FAST), 1)
                self.assertEqual(text.count(_LAST_CV), 1)
                self.assertLess(text.index(_FAST), text.index(_LAST_CV))


class TestInterpretedReference(unittest.TestCase):
    """What the compiled node already does, read off the interpreted node."""

    # No CV at the origin: the unguarded compute read (0, 0, 0).
    _CVS = [(0.5, 0.25, -1), (1, 2, 0), (3, -1, 1), (4, 0, 2), (6, 1, 0)]

    def setUp(self):
        mc.file(new=True, force=True)

    def _spline(self, cvs):
        from mpynode._common.io import mpn_io

        payload = mpn_io.load_mpn(os.path.join(_TPL, "template.mpn"),
                                  trusted=True)
        node = mpn_io.deserialize_node(payload, skip_selection=True).get_name()
        for k, v in enumerate(cvs):
            mc.setAttr("%s.cv[%d]" % (node, k), *v)
        return node

    def _assert_vec(self, got, want, places=6):
        self.assertEqual(len(got), 3)
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=places)

    def test_a_single_sample_reads_the_last_cv(self):
        node = self._spline(self._CVS)
        self._assert_vec(mc.getAttr(node + ".samples[0]")[0], self._CVS[-1])
        self.assertEqual(mc.getAttr(node + ".samples", multiIndices=True), [0])

    def test_a_single_connected_sample_follows_the_last_cv(self):
        node = self._spline(self._CVS)
        sink = mc.createNode("transform", skipSelect=True)
        mc.connectAttr(node + ".samples[0]", sink + ".translate")
        self._assert_vec(mc.getAttr(sink + ".translate")[0], self._CVS[-1])
        mc.setAttr(node + ".cv[4]", 7, 2, 1)
        self._assert_vec(mc.getAttr(sink + ".translate")[0], (7, 2, 1))

    def test_every_degree_and_cv_count(self):
        for count in range(1, len(self._CVS) + 1):
            mc.file(new=True, force=True)
            cvs  = self._CVS[:count]
            node = self._spline(cvs)
            for degree in (0, 1, 2, 3, 5):
                mc.setAttr(node + ".degree", degree)
                with self.subTest(cvs=count, degree=degree):
                    self._assert_vec(mc.getAttr(node + ".samples[0]")[0],
                                     cvs[-1])

    def test_two_samples_still_span_the_curve(self):
        node = self._spline(self._CVS)
        self._assert_vec(mc.getAttr(node + ".samples[1]")[0], self._CVS[-1])
        self._assert_vec(mc.getAttr(node + ".samples[0]")[0], self._CVS[0])


if __name__ == "__main__":
    unittest.main()
