"""Native file-texture (mPyFile) full-parity codegen + glue + clang harness

Consolidated from: test_file_texture_cpp.py, test_full_parity_scanline_tail.py, test_mpyfile_full_parity_codegen.py.
"""

from __future__ import annotations

# ===================== from test_file_texture_cpp.py =====================
import os
import shutil
import subprocess
import sys
import tempfile
from tests import _paths

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = _paths.ROOT
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

TOL = 5e-4


def _python_helpers():
    """exec the shipped Init source to get the real _linearize/_prefilter/_sample."""
    import maya.standalone
    try:
        maya.standalone.initialize()
    except Exception:
        pass
    import numpy as np  # noqa: F401  (used inside the exec'd source)
    from mpynode._defaults.file_defaults import DEFAULT_INIT_SOURCE
    ns = {}
    exec(DEFAULT_INIT_SOURCE, ns)
    return ns["_linearize"], ns["_prefilter"], ns["_sample"], np


_HARNESS_MAIN = r"""
#include <cstdio>
#include <cmath>
#include <vector>
#include <string>
#include <cstdlib>
int main() {
    int ncases;
    if (scanf("%d", &ncases) != 1) return 1;
    for (int ci = 0; ci < ncases; ++ci) {
        int W, H, cs, pf, kernel, wu, wv;
        float radius, u, v, br, bg, bb;
        if (scanf("%d %d %d %d %d %f %f %f %d %d %f %f %f",
                  &W, &H, &cs, &pf, &kernel, &radius, &u, &v, &wu, &wv,
                  &br, &bg, &bb) != 13) return 2;
        std::vector<unsigned char> raw((size_t)W * H * 4);
        for (size_t i = 0; i < raw.size(); ++i) { int t; scanf("%d", &t); raw[i] = (unsigned char)t; }
        float rq = (radius != 0.0f) ? (nearbyintf(radius * 10.0f) / 10.0f) : 0.0f;
        std::vector<float> lin;
        nd_tex_linearize(raw.data(), W, H, cs, lin);
        nd_tex_prefilter(lin, W, H, pf != 0, kernel, rq);
        float border[3] = {br, bg, bb};
        float miss[4] = {1.0f, 0.0f, 1.0f, 1.0f};
        float out[4];
        nd_tex_sample(lin.data(), W, H, u, v, wu, wv, border, miss, out);
        printf("%.9g %.9g %.9g %.9g\n", out[0], out[1], out[2], out[3]);
    }
    return 0;
}
"""


def _build_harness():
    from mpynode.native.compiler.kernels.file_texture_cpp import MATH_CPP
    src = _HARNESS_MAIN.split("int main", 1)[0] + MATH_CPP + "\nint main" + \
        _HARNESS_MAIN.split("int main", 1)[1]
    d = tempfile.mkdtemp(prefix="ndtex_math_")
    cpp = os.path.join(d, "harness.cpp")
    exe = os.path.join(d, "harness")
    with open(cpp, "w") as fh:
        fh.write(src)
    r = subprocess.run(["clang++", "-std=c++17", "-O2", "-o", exe, cpp],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL: harness compile error:\n", r.stderr)
        sys.exit(1)
    return exe


def main():
    _linearize, _prefilter, _sample, np = _python_helpers()
    np.random.seed(12345)
    exe = _build_harness()

    cases = []          # (W,H,cs,pf,kernel,radius,u,v,wu,wv,br,bg,bb, raw)
    expected = []       # (r,g,b,a)
    # Cover every colour space with a couple of UVs; sample wrap/kernel combos.
    for cs in range(25):
        for _ in range(3):
            W, H = 6, 5
            raw = np.random.randint(0, 256, (H, W, 4), dtype=np.uint8)
            u = float(np.random.uniform(-0.3, 1.3))
            v = float(np.random.uniform(-0.3, 1.3))
            wu = int(np.random.randint(0, 4))
            wv = int(np.random.randint(0, 4))
            pf = int(np.random.randint(0, 2))
            kernel = int(np.random.randint(0, 4))
            radius = float(np.random.choice([0.0, 1.0, 1.5, 2.0, 3.0]))
            br, bg, bb = (float(np.random.rand()) for _ in range(3))
            lin = _linearize(raw, cs)
            rq = round(radius, 1) if radius else 0.0
            lin = _prefilter(lin, bool(pf), kernel, rq)
            r, g, b, a = _sample(lin, u, v, wu, wv, (br, bg, bb))
            cases.append((W, H, cs, pf, kernel, radius, u, v, wu, wv, br, bg, bb, raw))
            expected.append((r, g, b, a))

    # Feed the harness.
    lines = ["%d" % len(cases)]
    for (W, H, cs, pf, kernel, radius, u, v, wu, wv, br, bg, bb, raw) in cases:
        lines.append("%d %d %d %d %d %.9g %.9g %.9g %d %d %.9g %.9g %.9g" % (
            W, H, cs, pf, kernel, radius, u, v, wu, wv, br, bg, bb))
        lines.append(" ".join(str(int(x)) for x in raw.flatten()))
    r = subprocess.run([exe], input="\n".join(lines), capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL: harness run error:\n", r.stderr)
        sys.exit(1)

    got = [tuple(float(x) for x in ln.split()) for ln in r.stdout.strip().splitlines()]
    if len(got) != len(expected):
        print("FAIL: got %d results, expected %d" % (len(got), len(expected)))
        sys.exit(1)

    maxerr = 0.0
    worst = None
    for i, (e, g) in enumerate(zip(expected, got)):
        for ec, gc in zip(e, g):
            d = abs(float(ec) - float(gc))
            if d > maxerr:
                maxerr = d
                worst = (i, cases[i][2], e, g)  # (case, cs, exp, got)
    print("cases=%d  maxerr=%.3e  tol=%.1e" % (len(cases), maxerr, TOL))
    if worst:
        print("worst: case=%d cs=%d exp=%r got=%r" % worst)
    if maxerr > TOL:
        print("FAIL: math parity exceeds tolerance")
        sys.exit(1)
    print("PASS: C++ texture math matches Python helpers across 25 colour spaces")
    sys.exit(0)


# ===================== from test_full_parity_scanline_tail.py =====================
import unittest

from mpynode._defaults.file_defaults import (
    DEFAULT_COMPUTE_SOURCE,
    DEFAULT_INIT_SOURCE,
)
from mpynode.native.compiler.kernels import file_texture_cpp as ftc


# INLINE spelling of the load+sample core: bare _load_linear_pixels/_sample
# calls from the Init tab. The shipped default now uses the blessed-method
# spelling (see _BLESSED_CORE), but the inline one is still fully supported
# hand-written compute, so these tests exercise it explicitly, independent of
# DEFAULT_COMPUTE_SOURCE. It must end with the exact _DEFAULT_WRITE block so
# ftc.make_scanline_compute() can swap the write.
_INLINE_DEFAULT_COMPUTE = (
    "linear = _load_linear_pixels(\n"
    "    self.fileName,\n"
    "    int(self.colorSpace),\n"
    "    bool(self.preFilter),\n"
    "    int(self.preFilterKernel),\n"
    "    float(self.preFilterRadius),\n"
    ")\n"
    "u, v = self.uvCoord\n"
    "border = np.asarray(self.borderColor, dtype=np.float32)\n"
    "r, g, b, a = _sample(\n"
    "    linear,\n"
    "    float(u), float(v),\n"
    "    int(self.wrapModeU), int(self.wrapModeV),\n"
    "    (float(border[0]), float(border[1]), float(border[2])),\n"
    ")\n"
    "self.outColor = (r, g, b)\n"
    "self.outAlpha = a\n"
)


# Init that adds the scanline look constants the tail references by name.
SCANLINE_INIT = DEFAULT_INIT_SOURCE + (
    "\nimport math\n"
    "NUM_BANDS = 12.0\n"
    "SPEED = 0.1\n"
    "TWO_PI = 6.283185307179586\n"
)


def _full_inputs(extra=None):
    """The preset surface is_full_parity_file_node requires, plus extras."""
    base = {
        "fileName": {"type": "string"},
        "uvCoord": {"type": "float2"},
        "colorSpace": {"type": "int"},
        "preFilter": {"type": "bool"},
        "preFilterKernel": {"type": "int"},
        "preFilterRadius": {"type": "float"},
        "wrapModeU": {"type": "int"},
        "wrapModeV": {"type": "int"},
        "borderColor": {"type": "color"},
    }
    if extra:
        base.update(extra)
    return base


def _spec(compute, init="", inputs=None):
    return {
        "suggested": {"reads_image_file": True},
        "inputs": inputs if inputs is not None else _full_inputs(),
        "compute": compute,
        "init": init,
    }


# Blessed API-method spelling of the load+sample core: self.read_texture() +
# self.sample_texture(buf, u, v). The method_registry SSOT recognises it as the
# SAME core as the Init helpers, so it routes through identical glue.
_BLESSED_CORE = (
    "buf = self.read_texture()\n"
    "u, v = self.uvCoord\n"
    "r, g, b, a = self.sample_texture(buf, u, v)\n"
)


def _blessed_spec(compute, init="", inputs=None):
    """A full-parity mPyFile spec whose compute uses the blessed method spelling.
    Needs mpy_type so method_registry.methods_for_type resolves the blessings."""
    spec = _spec(compute, init=init, inputs=inputs)
    spec["mpy_type"] = "mPyFile"
    return spec


def _mname(plug):
    """The C++ MObject member name codegen assigns to a plug (a + Capitalized)."""
    return "a" + plug[:1].upper() + plug[1:]


def _members():
    """ins/outs in the shape codegen passes to compute_glue_lines (member names
    follow codegen's `a<Capitalized>` convention; the glue prepends in_ / h_)."""
    def mk(kind, plug, typ, is_array=False):
        return {"kind": kind, "plug": plug, "member": _mname(plug),
                "meta": {"type": typ, "is_array": is_array}}
    ins = [
        mk("inputs", "fileName", "string"),
        mk("inputs", "uvCoord", "float2"),
        mk("inputs", "colorSpace", "int"),
        mk("inputs", "preFilter", "bool"),
        mk("inputs", "preFilterKernel", "int"),
        mk("inputs", "preFilterRadius", "float"),
        mk("inputs", "wrapModeU", "int"),
        mk("inputs", "wrapModeV", "int"),
        mk("inputs", "borderColor", "color"),
        mk("inputs", "tIn", "float"),
    ]
    outs = [
        mk("outputs", "outColor", "color"),
        mk("outputs", "outAlpha", "float"),
    ]
    return ins, outs


class TestMakeScanlineCompute(unittest.TestCase):
    def test_swaps_only_the_write_lines(self):
        c = ftc.make_scanline_compute(_INLINE_DEFAULT_COMPUTE)
        self.assertIn("_load_linear_pixels(", c)
        self.assertIn("_sample(", c)
        # the plain write is gone; the modulated write is present
        self.assertNotIn("self.outColor = (r, g, b)", c)
        self.assertIn("self.outColor = (r * scan, g * scan, b * scan)", c)
        self.assertIn("math.sin(", c)
        self.assertIn("self.tIn", c)

    def test_raises_if_default_shape_changes(self):
        with self.assertRaises(ValueError):
            ftc.make_scanline_compute("self.outColor = (1,2,3)\n")


class TestClassify(unittest.TestCase):
    def test_pure_default_is_default(self):
        kind, tail = ftc.classify_full_parity_compute(
            _spec(_INLINE_DEFAULT_COMPUTE, init=DEFAULT_INIT_SOURCE))
        self.assertEqual(kind, "default")
        self.assertIsNone(tail)

    def test_default_plus_scanline_is_scanline(self):
        compute = ftc.make_scanline_compute(_INLINE_DEFAULT_COMPUTE)
        kind, tail = ftc.classify_full_parity_compute(
            _spec(compute, init=SCANLINE_INIT,
                  inputs=_full_inputs({"tIn": {"type": "float"}})))
        self.assertEqual(kind, "scanline")
        self.assertEqual(tail["tin"], "tIn")
        self.assertEqual(tail["bands"], 12.0)
        self.assertEqual(tail["speed"], 0.1)
        self.assertAlmostEqual(tail["twopi"], 6.283185307179586)
        self.assertEqual((tail["c0"], tail["c1"], tail["c2"], tail["c3"]),
                         (0.4, 0.6, 0.5, 0.5))

    def test_unrecognized_tail_is_none(self):
        # default load+sample but a CUSTOM tail the glue cannot reproduce.
        compute = _INLINE_DEFAULT_COMPUTE.replace(
            "self.outColor = (r, g, b)\nself.outAlpha = a\n",
            "self.outColor = (r * 0.5, g, b + math.tan(u))\nself.outAlpha = a\n",
        )
        kind, tail = ftc.classify_full_parity_compute(
            _spec(compute, init=SCANLINE_INIT))
        self.assertIsNone(kind)
        self.assertIsNone(tail)

    def test_scanline_without_const_in_init_is_none(self):
        # tail references NUM_BANDS/SPEED/TWO_PI; if Init never defines them the
        # C++ value is unknown -> must NOT be treated as full-parity.
        compute = ftc.make_scanline_compute(_INLINE_DEFAULT_COMPUTE)
        kind, _ = ftc.classify_full_parity_compute(
            _spec(compute, init=DEFAULT_INIT_SOURCE,  # no NUM_BANDS etc.
                  inputs=_full_inputs({"tIn": {"type": "float"}})))
        self.assertIsNone(kind)

    def test_scanline_with_nonscalar_tin_is_none(self):
        # the tail emits `(double)in_<tin>`; for a vector/array tIn that is not
        # a valid cast, and `self.tIn * SPEED` would be elementwise, so fall
        # back instead of emitting wrong C++.
        compute = ftc.make_scanline_compute(_INLINE_DEFAULT_COMPUTE)
        for bad in ("vector", "float2", "matrix", "string"):
            kind, _ = ftc.classify_full_parity_compute(
                _spec(compute, init=SCANLINE_INIT,
                      inputs=_full_inputs({"tIn": {"type": bad}})))
            self.assertIsNone(kind, "tIn type %r must not classify scanline" % bad)

    def test_scanline_without_tin_input_is_none(self):
        # tail reads self.tIn; if tIn was not captured as an input the emitted
        # C++ would reference a non-existent member.
        compute = ftc.make_scanline_compute(_INLINE_DEFAULT_COMPUTE)
        kind, _ = ftc.classify_full_parity_compute(
            _spec(compute, init=SCANLINE_INIT, inputs=_full_inputs()))  # no tIn
        self.assertIsNone(kind)

    def test_blessed_default_is_default(self):
        # blessed core + the plain default write is the SAME "default" as the
        # Init-helper spelling.
        compute = _BLESSED_CORE + "self.outColor = (r, g, b)\nself.outAlpha = a\n"
        spec = _blessed_spec(compute, init=DEFAULT_INIT_SOURCE)
        kind, tail = ftc.classify_full_parity_compute(spec)
        self.assertEqual(kind, "default")
        self.assertIsNone(tail)
        self.assertTrue(ftc.use_full_parity_glue(spec))

    def test_blessed_scanline_is_scanline(self):
        # same blessed core, ending in the canonical scanline tail from the
        # SSOT, with the scanline Init consts and a scalar tIn input.
        compute = _BLESSED_CORE + ftc._SCANLINE_COMPUTE_TAIL
        kind, tail = ftc.classify_full_parity_compute(
            _blessed_spec(compute, init=SCANLINE_INIT,
                          inputs=_full_inputs({"tIn": {"type": "float"}})))
        self.assertEqual(kind, "scanline")
        self.assertEqual(tail["tin"], "tIn")
        self.assertEqual(tail["bands"], 12.0)
        self.assertEqual(tail["speed"], 0.1)
        self.assertAlmostEqual(tail["twopi"], 6.283185307179586)
        self.assertEqual((tail["c0"], tail["c1"], tail["c2"], tail["c3"]),
                         (0.4, 0.6, 0.5, 0.5))

    def test_blessed_custom_tail_not_full_parity(self):
        # a custom write the glue cannot reproduce falls back to the porter
        # path, rather than silently rendering plain texture.
        compute = _BLESSED_CORE + "self.outColor = (r * 0.5, g, b)\nself.outAlpha = a\n"
        spec = _blessed_spec(compute, init=SCANLINE_INIT)
        kind, tail = ftc.classify_full_parity_compute(spec)
        self.assertIsNone(kind)
        self.assertIsNone(tail)
        self.assertFalse(ftc.use_full_parity_glue(spec))

    _DEFAULT_WRITE = "self.outColor = (r, g, b)\nself.outAlpha = a\n"

    def test_blessed_swapped_uv_not_full_parity(self):
        # the glue hardcodes sampling at uvCoord[0]/[1], so a compute that
        # samples (v, u) but ends in the default write must not use it: the
        # texture would come out transposed.
        compute = (
            "buf = self.read_texture()\n"
            "u, v = self.uvCoord\n"
            "r, g, b, a = self.sample_texture(buf, v, u)\n"   # swapped
            + self._DEFAULT_WRITE
        )
        spec = _blessed_spec(compute, init=DEFAULT_INIT_SOURCE)
        self.assertEqual(ftc.classify_full_parity_compute(spec), (None, None))
        self.assertFalse(ftc.use_full_parity_glue(spec))

    def test_blessed_scaled_uv_not_full_parity(self):
        # A uv transform (2x tiling) the glue does not compute -> not full parity.
        compute = (
            "buf = self.read_texture()\n"
            "u, v = self.uvCoord\n"
            "r, g, b, a = self.sample_texture(buf, u * 2.0, v * 2.0)\n"
            + self._DEFAULT_WRITE
        )
        spec = _blessed_spec(compute, init=DEFAULT_INIT_SOURCE)
        self.assertEqual(ftc.classify_full_parity_compute(spec), (None, None))
        self.assertFalse(ftc.use_full_parity_glue(spec))

    def test_blessed_reassigned_uv_alias_not_full_parity(self):
        # An alias rebound after the unpack is no longer the raw channel: the
        # glue would sample uvCoord while the interpreted node samples u*2.
        compute = (
            "buf = self.read_texture()\n"
            "u, v = self.uvCoord\n"
            "u = u * 2.0\n"
            "r, g, b, a = self.sample_texture(buf, u, v)\n"
            + self._DEFAULT_WRITE
        )
        spec = _blessed_spec(compute, init=DEFAULT_INIT_SOURCE)
        self.assertEqual(ftc.classify_full_parity_compute(spec), (None, None))
        self.assertFalse(ftc.use_full_parity_glue(spec))

    def test_blessed_subscript_uv_alias_is_default(self):
        # uv = self.uvCoord; sample_texture(buf, uv[0], uv[1]) -> the SAME default.
        compute = (
            "buf = self.read_texture()\n"
            "uv = self.uvCoord\n"
            "r, g, b, a = self.sample_texture(buf, uv[0], uv[1])\n"
            + self._DEFAULT_WRITE
        )
        spec = _blessed_spec(compute, init=DEFAULT_INIT_SOURCE)
        kind, tail = ftc.classify_full_parity_compute(spec)
        self.assertEqual(kind, "default")
        self.assertIsNone(tail)
        self.assertTrue(ftc.use_full_parity_glue(spec))

    def test_blessed_direct_uvcoord_index_is_default(self):
        # sample_texture(buf, self.uvCoord[0], self.uvCoord[1]) -> default.
        compute = (
            "buf = self.read_texture()\n"
            "r, g, b, a = self.sample_texture(buf, self.uvCoord[0], self.uvCoord[1])\n"
            + self._DEFAULT_WRITE
        )
        spec = _blessed_spec(compute, init=DEFAULT_INIT_SOURCE)
        kind, _ = ftc.classify_full_parity_compute(spec)
        self.assertEqual(kind, "default")
        self.assertTrue(ftc.use_full_parity_glue(spec))


class TestUseFullParityGlue(unittest.TestCase):
    def test_default_uses_glue(self):
        self.assertTrue(ftc.use_full_parity_glue(
            _spec(_INLINE_DEFAULT_COMPUTE, init=DEFAULT_INIT_SOURCE)))

    def test_scanline_uses_glue(self):
        compute = ftc.make_scanline_compute(_INLINE_DEFAULT_COMPUTE)
        self.assertTrue(ftc.use_full_parity_glue(
            _spec(compute, init=SCANLINE_INIT,
                  inputs=_full_inputs({"tIn": {"type": "float"}}))))

    def test_unrecognized_tail_does_not_use_glue(self):
        # THE SAFETY PROPERTY: do not silently drop a custom tail.
        compute = _INLINE_DEFAULT_COMPUTE.replace(
            "self.outColor = (r, g, b)\nself.outAlpha = a\n",
            "self.outColor = (r * 0.5, g, b)\nself.outAlpha = a\n",
        )
        self.assertFalse(ftc.use_full_parity_glue(
            _spec(compute, init=SCANLINE_INIT)))

    def test_non_file_node_never_uses_glue(self):
        spec = _spec(_INLINE_DEFAULT_COMPUTE, init=DEFAULT_INIT_SOURCE,
                     inputs={"uvCoord": {"type": "float2"}})  # missing presets
        self.assertFalse(ftc.use_full_parity_glue(spec))


class TestShippedDefaultIsBlessed(unittest.TestCase):
    """The shipped mPyFile default Compute uses the blessed-method spelling
    (self.read_texture() / self.sample_texture()), not the inline helper calls.
    It classifies as full-parity "default" via the blessed spec (mpy_type set),
    so it compiles to the same C++ as the inline spelling."""

    def test_shipped_default_uses_blessed_methods(self):
        self.assertIn("self.read_texture()", DEFAULT_COMPUTE_SOURCE)
        self.assertIn("self.sample_texture(", DEFAULT_COMPUTE_SOURCE)
        self.assertNotIn("_load_linear_pixels(", DEFAULT_COMPUTE_SOURCE)
        self.assertNotIn("_sample(", DEFAULT_COMPUTE_SOURCE)

    def test_shipped_default_classifies_as_default(self):
        spec = _blessed_spec(DEFAULT_COMPUTE_SOURCE, init=DEFAULT_INIT_SOURCE)
        kind, tail = ftc.classify_full_parity_compute(spec)
        self.assertEqual(kind, "default")
        self.assertIsNone(tail)
        self.assertTrue(ftc.use_full_parity_glue(spec))


class TestComputeGlueLinesNoTail(unittest.TestCase):
    """Regression lock: the no-tail body is unchanged (writes _outc directly)."""

    def test_writes_outc_directly(self):
        ins, outs = _members()
        body = "\n".join(ftc.compute_glue_lines(ins, outs))
        self.assertIn("nd_tex_load_linear(", body)
        self.assertIn("nd_tex_sample(", body)
        self.assertIn("h_aOutColor.set3Float(_outc[0], _outc[1], _outc[2]);",
                      body)
        self.assertIn("h_aOutAlpha.setFloat(_outc[3]);", body)
        self.assertNotIn("_scan", body)
        self.assertNotIn("std::sin", body)


class TestComputeGlueLinesScanlineTail(unittest.TestCase):
    def _emit(self, tail):
        ins, outs = _members()
        return "\n".join(ftc.compute_glue_lines(ins, outs, tail=tail))

    def test_emits_scanline_modulation(self):
        tail = {"c0": 0.4, "c1": 0.6, "c2": 0.5, "c3": 0.5,
                "bands": 12.0, "speed": 0.1, "twopi": 6.283185307179586,
                "tin": "tIn"}
        body = self._emit(tail)
        self.assertIn("nd_tex_load_linear(", body)
        self.assertIn("nd_tex_sample(", body)
        # modulation: scan from std::sin over v + tIn, applied to outColor
        self.assertIn("std::sin(", body)
        self.assertIn("(double)in_aTIn", body)
        self.assertIn("_v", body)
        self.assertIn("_outc[0] * _scan", body)
        self.assertIn("_outc[1] * _scan", body)
        self.assertIn("_outc[2] * _scan", body)
        # alpha passes through unmodulated
        self.assertIn("h_aOutAlpha.setFloat(_outc[3]);", body)
        # must NOT also emit the plain (unmodulated) colour write
        self.assertNotIn(
            "h_aOutColor.set3Float(_outc[0], _outc[1], _outc[2]);", body)

    def test_constants_flow_through_not_vacuous(self):
        tail = {"c0": 0.3, "c1": 0.7, "c2": 0.25, "c3": 0.75,
                "bands": 7.0, "speed": 0.05, "twopi": 6.0, "tin": "tIn"}
        body = self._emit(tail)
        self.assertIn("7.0", body)
        self.assertIn("0.05", body)
        self.assertIn("0.3", body)
        self.assertIn("0.7", body)
        self.assertNotIn("12.0", body)
        self.assertNotIn("0.1 ", body)

    def test_tin_member_name_flows_through(self):
        tail = {"c0": 0.4, "c1": 0.6, "c2": 0.5, "c3": 0.5,
                "bands": 12.0, "speed": 0.1, "twopi": 6.283185307179586,
                "tin": "frame"}
        ins, outs = _members()
        # rename the tIn input plug -> the glue must follow the member name
        for m in ins:
            if m["plug"] == "tIn":
                m["plug"] = "frame"
                m["member"] = _mname("frame")
        body = "\n".join(ftc.compute_glue_lines(ins, outs, tail=tail))
        self.assertIn("(double)in_aFrame", body)


# ===================== from test_mpyfile_full_parity_codegen.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest


# The shipped default compute calls the standard Init helpers and the gate
# needs both; a rewritten compute falls back to the porter path.
_FULL_COMPUTE = (
    "linear = _load_linear_pixels(self.fileName, int(self.colorSpace),\n"
    "    bool(self.preFilter), int(self.preFilterKernel), float(self.preFilterRadius))\n"
    "u, v = self.uvCoord\n"
    "r, g, b, a = _sample(linear, float(u), float(v), int(self.wrapModeU),\n"
    "    int(self.wrapModeV), (0.0, 0.0, 0.0))\n"
    "self.outColor = (r, g, b)\nself.outAlpha = a\n"
)

_FULL_INPUTS = {
    "fileName": {"attr_type": "string"},
    "uvCoord": {"attr_type": "float2"},
    "colorSpace": {"attr_type": "enum", "enum_names": ["sRGB", "linear"]},
    "preFilter": {"attr_type": "bool"},
    "preFilterKernel": {"attr_type": "enum", "enum_names": ["box", "gauss"]},
    "preFilterRadius": {"attr_type": "float"},
    "wrapModeU": {"attr_type": "enum", "enum_names": ["wrap", "clamp"]},
    "wrapModeV": {"attr_type": "enum", "enum_names": ["wrap", "clamp"]},
    "borderColor": {"attr_type": "color"},
}
_FULL_OUTPUTS = {"outColor": {"attr_type": "color"}, "outAlpha": {"attr_type": "float"}}


def _full_spec(inputs=None, compute=_FULL_COMPUTE, reads_image_file=True):
    from mpynode.native.spec import spec_extractor as se
    inputs = _FULL_INPUTS if inputs is None else inputs
    sug = {"node_type_name": "fullFileNode", "class_name": "FullFileNode",
           "type_id": "0x00070abc", "mpx_base": "MPxNode",
           "classification": "texture/2d:swatch/2dTextureSwatchGen"}
    if reads_image_file:
        sug["reads_image_file"] = True
    return {
        "suggested": sug, "mpy_type": "mPyFile",
        "compute": compute, "init": "",
        "inputs": {n: se.normalize_attr(m) for n, m in inputs.items()},
        "outputs": {n: se.normalize_attr(m) for n, m in _FULL_OUTPUTS.items()},
        "variables": {},
        "portability": {"portable": True, "blockers": [], "warnings": [],
                        "reads_image_file": reads_image_file},
    }


class TestFullParityDetection(unittest.TestCase):
    def test_detects_full_parity_file_node(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftx
        self.assertTrue(ftx.use_full_parity_glue(_full_spec()))

    def test_missing_presets_not_full_parity(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftx
        spec = _full_spec(inputs={"fileName": {"attr_type": "string"},
                                  "uvCoord": {"attr_type": "float2"}})
        self.assertFalse(ftx.use_full_parity_glue(spec))

    def test_custom_compute_not_full_parity(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftx
        # reads_image_file + presets, but compute doesn't call the std helpers.
        spec = _full_spec(compute="self.outColor = (0.0, 0.0, 0.0)\nself.outAlpha = 1.0")
        self.assertFalse(ftx.use_full_parity_glue(spec))


class TestFullParityCodegen(unittest.TestCase):
    def setUp(self):
        from mpynode.native import compiler as codegen
        self.cpp = codegen.generate_cpp(_full_spec(), for_port=True)

    def test_emits_verified_helpers(self):
        self.assertIn("nd_tex_load_linear", self.cpp)
        self.assertIn("nd_tex_sample", self.cpp)
        self.assertIn("nd_tex_linearize", self.cpp)

    def test_emits_cache_members(self):
        self.assertIn("NdTexCache", self.cpp)
        self.assertIn("std::mutex", self.cpp)

    def test_vertical_flip_present(self):
        # The orientation fix: MImage bottom-up -> top-down to match numpy/PIL.
        self.assertIn("verticalFlip", self.cpp)

    def test_no_ai_port_region(self):
        from mpynode.native import compiler as codegen
        self.assertNotIn(codegen.PORT_BEGIN, self.cpp)

    def test_extra_includes(self):
        self.assertIn("#include <mutex>", self.cpp)
        self.assertIn("#include <string>", self.cpp)

    def test_filename_declared_first(self):
        # Swatch generator hint: fileName must be the first input attribute.
        i_file = self.cpp.index('addAttribute(aFileName)')
        for other in ("aColorSpace", "aUvCoord", "aWrapModeU", "aBorderColor"):
            self.assertLess(i_file, self.cpp.index("addAttribute(%s)" % other),
                            "fileName must be addAttribute'd before %s" % other)

    def test_glue_calls_sample_into_color_output(self):
        self.assertIn("nd_tex_sample(_lin", self.cpp)
        self.assertIn("h_aOutColor.set3Float", self.cpp)
        self.assertIn("h_aOutAlpha.setFloat", self.cpp)

    def test_color_output_children_in_affects(self):
        """The legacy software swatch renderer pulls outColor's R/G/B children
        individually -- without attributeAffects(input -> child) the children
        never go dirty, compute() doesn't re-run per swatch sample, and the
        Hypershade swatch renders black/partial. The Python mPyFile wires the
        children explicitly for the same reason; codegen must too."""
        self.assertIn("MFnNumericAttribute", self.cpp)
        self.assertIn("aOutColor_r", self.cpp)
        self.assertIn("aOutColor_g", self.cpp)
        self.assertIn("aOutColor_b", self.cpp)
        self.assertIn(".child(0)", self.cpp)
        self.assertIn("attributeAffects(aUvCoord, aOutColor_r)", self.cpp)
        self.assertIn("attributeAffects(aUvCoord, aOutColor_g)", self.cpp)
        self.assertIn("attributeAffects(aUvCoord, aOutColor_b)", self.cpp)
        self.assertIn("attributeAffects(aUvCoord, aOutColor)", self.cpp)

    def test_non_color_output_has_no_child_affects(self):
        """outAlpha (scalar float) must NOT get spurious child-affects."""
        self.assertNotIn("aOutAlpha_r", self.cpp)

    def test_blessed_uvcoord_default_lowers_via_glue(self):
        """A blessed default compute (self.read_texture()/self.sample_texture())
        routes through the SAME deterministic glue as the Init-helper spelling --
        no AI PORT region."""
        from mpynode.native import compiler as codegen
        blessed = (
            "buf = self.read_texture()\n"
            "u, v = self.uvCoord\n"
            "r, g, b, a = self.sample_texture(buf, u, v)\n"
            "self.outColor = (r, g, b)\nself.outAlpha = a\n"
        )
        cpp = codegen.generate_cpp(_full_spec(compute=blessed), for_port=True)
        self.assertIn("nd_tex_load_linear", cpp)
        self.assertIn("nd_tex_sample", cpp)
        self.assertIn("h_aOutColor.set3Float", cpp)
        self.assertIn("h_aOutAlpha.setFloat", cpp)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)


class TestScanlineStillUsesPortRegion(unittest.TestCase):
    """A bare reads_image_file node (no full preset surface) keeps the inline
    _imgPixels scaffold + AI PORT region -- the lightweight path is unchanged."""

    def test_scanline_keeps_port_region(self):
        from mpynode.native.spec import spec_extractor as se
        from mpynode.native import compiler as codegen
        spec = {
            "suggested": {"node_type_name": "scanlineNode", "class_name": "ScanlineNode",
                          "type_id": "0x00070abd", "mpx_base": "MPxNode",
                          "reads_image_file": True},
            "mpy_type": "mPyFile", "compute": "pass", "init": "",
            "inputs": {"fileName": se.normalize_attr({"attr_type": "string"}),
                       "uvCoord": se.normalize_attr({"attr_type": "float2"})},
            "outputs": {"outColor": se.normalize_attr({"attr_type": "color"})},
            "variables": {},
            "portability": {"portable": True, "blockers": [], "warnings": [],
                            "reads_image_file": True},
        }
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn(codegen.PORT_BEGIN, cpp)        # still AI-filled
        self.assertIn("_imgPixels", cpp)              # inline scaffold
        self.assertNotIn("nd_tex_load_linear", cpp)   # no verified-helper block


def _scanline_spec():
    """A bare reads_image_file node (lightweight path): fileName + uvCoord, custom
    compute via the AI PORT region. Mirrors the scanlineOverTime demo node."""
    from mpynode.native.spec import spec_extractor as se
    return {
        "suggested": {"node_type_name": "scanlineNode", "class_name": "ScanlineNode",
                      "type_id": "0x00070abd", "mpx_base": "MPxNode",
                      "reads_image_file": True},
        "mpy_type": "mPyFile",
        "compute": ("u, v = self.uvCoord\nself.outColor = (u, v, 0.0)\n"
                    "self.outAlpha = 1.0\n"),
        "init": "",
        "inputs": {"fileName": se.normalize_attr({"attr_type": "string"}),
                   "uvCoord": se.normalize_attr({"attr_type": "float2"}),
                   "tIn": se.normalize_attr({"attr_type": "float"})},
        "outputs": {"outColor": se.normalize_attr({"attr_type": "color"}),
                    "outAlpha": se.normalize_attr({"attr_type": "float"})},
        "variables": {},
        "portability": {"portable": True, "blockers": [], "warnings": [],
                        "reads_image_file": True},
    }


class TestLightweightImageCache(unittest.TestCase):
    """PERF regression guard: the lightweight reads_image_file path must NOT call
    MImage::readFromFile inside compute() (i.e. per shading sample). Decoding the
    image per sample makes a render thousands of times slower than the Python node
    (which caches the decode in _GRID_CACHE). The decode must be cached per node
    instance and re-run only when the path changes."""

    def setUp(self):
        from mpynode.native import compiler as codegen
        self.codegen = codegen
        self.cpp = codegen.generate_cpp(_scanline_spec(), for_port=True)

    def test_decode_is_not_per_compute(self):
        body = self.cpp.split("::compute(", 1)[1]
        self.assertNotIn(
            ".readFromFile(", body,
            "MImage::readFromFile must NOT be CALLED inside compute() (per-sample "
            "decode = a render thousands of times slower than the cached Python node)")
        self.assertNotIn("MImage _img;", self.cpp,
                         "the per-compute local MImage (the slow path) must be gone")

    def test_uses_cached_loader(self):
        self.assertIn("nd_img_load_raw", self.cpp,
                      "compute must obtain pixels via the cached loader")
        self.assertIn("nd_img_load_raw(_imgRawCache", self.cpp)
        # The decode happens exactly once, in the cache helper (not per sample).
        self.assertEqual(self.cpp.count(".readFromFile("), 1)

    def test_emits_cache_members(self):
        self.assertIn("NdImgRawCache _imgRawCache", self.cpp)
        self.assertIn("std::mutex", self.cpp)
        self.assertIn("#include <mutex>", self.cpp)

    def test_porter_contract_preserved(self):
        # The ported body still reads these locals (complete_fn / LLM contract).
        for sym in ("_imgPixels", "_imgOK", "_imgW", "_imgH"):
            self.assertIn(sym, self.cpp)
        self.assertIn(self.codegen.PORT_BEGIN, self.cpp)


class TestFloat2ChildNamesComeFromTheSSOT(unittest.TestCase):
    """A compiled mPyFile must expose ``uCoord``, not ``uvCoordX``.

    Codegen used to synthesize float2 children as ``<plug>X``/``<plug>Y`` on the
    premise that "parent connect ignores child names". True for
    ``place2dTexture.outUV -> uvCoord``, which is why this survived -- but
    addressing a child BY NAME is not a connect, and the authored tests for all
    five mPyFile templates do ``setAttr <node>.uCoord``. Those failed against
    every compiled mPyFile node while the build still reported it compiled.

    The child long-names are declared in the SSOT and now travel
    SSOT -> build_porter_meta_table -> normalize_attr -> emit_attr.
    """

    def _emit(self, plug, meta):
        from mpynode.native.compiler import emit_attr
        return "\n".join(emit_attr._create_lines({
            "plug": plug, "member": "a" + plug[0].upper() + plug[1:],
            "meta": meta, "kind": "inputs"}))

    def test_the_ssot_child_names_reach_the_generated_cpp(self):
        from mpynode._common.interface import file_texture_interface as iface
        from mpynode.native.spec import spec_extractor as se

        meta = se.normalize_attr(iface.build_porter_meta_table()["uvCoord"])
        self.assertEqual(meta.get("children"), ["uCoord", "vCoord"],
                         "children must survive the SSOT -> spec projection")

        cpp = self._emit("uvCoord", meta)
        self.assertIn('nAttr.create("uCoord", "uCoord"', cpp)
        self.assertIn('nAttr.create("vCoord", "vCoord"', cpp)
        self.assertNotIn("uvCoordX", cpp)
        self.assertNotIn("uvCoordY", cpp)

    def test_uv_filter_size_is_unchanged(self):
        """Its declared children ARE <plug>X/Y, so the fix must not move it."""
        from mpynode._common.interface import file_texture_interface as iface
        from mpynode.native.spec import spec_extractor as se

        meta = se.normalize_attr(
            iface.build_porter_meta_table()["uvFilterSize"])
        cpp = self._emit("uvFilterSize", meta)
        self.assertIn('nAttr.create("uvFilterSizeX", "uvFilterSizeX"', cpp)
        self.assertIn('nAttr.create("uvFilterSizeY", "uvFilterSizeY"', cpp)

    def test_a_float2_with_no_declared_children_still_falls_back(self):
        """A user-declared float2 has no SSOT entry, so the generic rule stands."""
        from mpynode.native.spec import spec_extractor as se

        cpp = self._emit("myUv", se.normalize_attr({"attr_type": "float2"}))
        self.assertIn('nAttr.create("myUvX", "myUvX"', cpp)
        self.assertIn('nAttr.create("myUvY", "myUvY"', cpp)


class TestExactTexelFastPath(unittest.TestCase):
    """nd_tex_sample's corner-grid short-circuit, against the Python sampler.

    ``_build_harness``/``_python_helpers`` above already compile the real kernel
    and compare it to ``_sample``, but the only driver for them was a ``main()``
    that unittest never calls -- and it draws UVs from ``uniform(-0.3, 1.3)``, so
    it lands on an exact texel essentially never. The fast path is therefore the
    one branch of the sampler that harness cannot reach. These cases feed it the
    VP2 bake's own corner-grid coordinates instead.
    """

    @classmethod
    def setUpClass(cls):
        if shutil.which("clang++") is None:
            raise unittest.SkipTest("clang++ not on PATH")
        cls.exe = _build_harness()
        cls.helpers = _python_helpers()

    @staticmethod
    def _corner_uvs(w, h):
        """Exactly what emit_vp2_override emits for a corner-grid bake."""
        return [(x / float(max(w - 1, 1)), 1.0 - py / float(max(h - 1, 1)))
                for py in range(h) for x in range(w)]

    def _run(self, W, H, cs=0):
        _linearize, _prefilter, _sample, np = self.helpers
        np.random.seed(4242)
        raw = np.random.randint(0, 256, (H, W, 4), dtype=np.uint8)
        lin = _linearize(raw, cs)
        lin = _prefilter(lin, False, 0, 0.0)
        uvs = self._corner_uvs(W, H)
        lines = ["%d" % len(uvs)]
        expected = []
        for u, v in uvs:
            # wrap mode 1 (clamp) is what the corner grid ships with.
            lines.append("%d %d %d 0 0 0 %.9g %.9g 1 1 0 0 0" % (W, H, cs, u, v))
            lines.append(" ".join(str(int(x)) for x in raw.flatten()))
            expected.append(_sample(lin, float(u), float(v), 1, 1, (0.0, 0.0, 0.0)))
        r = subprocess.run([self.exe], input="\n".join(lines),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = [tuple(float(x) for x in ln.split())
               for ln in r.stdout.strip().splitlines()]
        self.assertEqual(len(got), len(expected))
        return uvs, expected, got

    def test_corner_grid_matches_the_python_sampler(self):
        for W, H in ((6, 5), (8, 8), (17, 9)):
            with self.subTest(W=W, H=H):
                uvs, expected, got = self._run(W, H)
                worst = max(abs(float(e) - float(g))
                            for exp, gt in zip(expected, got)
                            for e, g in zip(exp, gt))
                self.assertLessEqual(
                    worst, TOL,
                    "corner-grid sample drifted from the Python twin at "
                    "%dx%d: %.3e" % (W, H, worst))

    def test_the_fast_path_is_actually_taken(self):
        """Non-vacuity. If tx were never 0 the test above would pass while
        exercising only the full blend -- which is exactly the gap in the
        random-UV harness this class exists to close."""
        f32 = self.helpers[3].float32
        for W, H in ((6, 5), (8, 8), (17, 9)):
            hits = 0
            for u, _v in self._corner_uvs(W, H):
                # The shipped chain: u -> float, clamp (identity in [0,1]),
                # times (W-1), minus its own truncation.
                fx = f32(f32(u) * f32(W - 1))
                if f32(fx - f32(int(fx))) == f32(0.0):
                    hits += 1
            self.assertEqual(hits, W * H,
                             "tx must be exactly 0 for every corner-grid texel "
                             "at %dx%d (got %d/%d) -- if this regresses the "
                             "fast path silently stops firing" % (W, H, hits, W * H))


if __name__ == "__main__":
    import unittest
    unittest.main()
