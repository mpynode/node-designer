"""nd_lower end-to-end parity harness (Maya-FREE, run under mayapy for numpy).

For each fixture it:
  1. Builds codegen-style ins/outs descriptors + a compute block, lowers it via
     nd_lower.lower_compute -> C++ body lines.
  2. Generates a self-contained C++ program: minimal Maya shims (MVector / MAngle
     / MTime / a MockHandle sink), the Maya input locals (``in_<member>``) seeded
     with the fixture's test values, the output sinks (``h_<member>`` handles /
     ``out_<member>`` buffers), the lowered body, then PROBE prints per output.
  3. Compiles with clang++ -std=c++17 -O2 -I <native>, runs it, and compares each
     output to the numpy ORACLE -- the SAME compute block exec'd against numpy
     inputs (exactly what the interpreted node computes).

Also asserts the REJECT fixtures (matrix I/O, string I/O, unwritten output,
non-output self-write) yield None from try_lower_compute -> codegen falls back to
the AI porter unchanged (zero regression).

Usage:
    mayapy nd_lower_test.py
Exit 0 == every positive fixture bit-faithful and every reject rejected.
"""
import os
import sys
import shutil
import subprocess
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# HERE is .../scripts/mpynode/native/tests -- three dirname()s to reach scripts/.
# _INC = .../scripts/mpynode/native/compiler (where nd_runtime.h now lives).
_INC = os.path.join(os.path.dirname(HERE), "compiler")
_SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from mpynode.native.compiler import nd_lower

# Maya C++ container element type per attr type (matches codegen._CPP subset).
_MAYA_CTYPE = {
    "float": "float", "double": "double", "int": "int", "bool": "bool",
    "enum": "short", "angle": "double", "time": "double", "matrix": "MMatrix",
}
# numpy dtype per attr type, for the oracle inputs.
_NP_DTYPE = {
    "float": np.float64, "double": np.float64, "angle": np.float64,
    "time": np.float64, "int": np.int64, "enum": np.int64, "bool": np.bool_,
    "matrix": np.float64,
}
_VEC = ("vector", "euler")


def _member(plug):
    return "a" + plug[:1].upper() + plug[1:]


def _descr(plug, typ, is_array, kind):
    return {"plug": plug, "member": _member(plug), "kind": kind,
            "meta": {"type": typ, "is_array": is_array}}


# ---------------------------------------------------------------------------
# C++ generation
# ---------------------------------------------------------------------------
def _cpp_lit(v):
    return "%.17g" % float(v)


def _decl_input(d, value):
    """C++ declaring the Maya input local in_<member> seeded to `value`."""
    m = d["member"]
    t = d["meta"]["type"]
    src = "in_" + m
    if not d["meta"]["is_array"]:
        if t in _VEC:
            a = list(value)
            return "    double %s[3] = {%s, %s, %s};" % (
                src, _cpp_lit(a[0]), _cpp_lit(a[1]), _cpp_lit(a[2]))
        if t == "matrix":
            flat = ", ".join(_cpp_lit(x) for row in value for x in row)
            return "    MMatrix %s{%s};" % (src, flat)
        c = _MAYA_CTYPE[t]
        if t == "bool":
            return "    bool %s = %s;" % (src, "true" if value else "false")
        return "    %s %s = %s;" % (c, src, _cpp_lit(value))
    # arrays
    if t in _VEC:
        items = ", ".join("MVector(%s, %s, %s)"
                          % (_cpp_lit(r[0]), _cpp_lit(r[1]), _cpp_lit(r[2]))
                          for r in value)
        return "    std::vector<MVector> %s = {%s};" % (src, items)
    if t == "matrix":
        items = ", ".join(
            "MMatrix{%s}" % ", ".join(_cpp_lit(x) for row in mtx for x in row)
            for mtx in value)
        return "    std::vector<MMatrix> %s = {%s};" % (src, items)
    c = _MAYA_CTYPE[t]
    if t == "bool":
        items = ", ".join("true" if x else "false" for x in value)
    else:
        items = ", ".join(_cpp_lit(x) for x in value)
    return "    std::vector<%s> %s = {%s};" % (c, src, items)


def _decl_output(d):
    m = d["member"]
    t = d["meta"]["type"]
    if not d["meta"]["is_array"]:
        return "    MockHandle h_%s;" % m
    if t in _VEC:
        return "    std::vector<MVector> out_%s;" % m
    return "    std::vector<%s> out_%s;" % (_MAYA_CTYPE[t], m)


def _print_output(d):
    m = d["member"]
    plug = d["plug"]
    t = d["meta"]["type"]
    if not d["meta"]["is_array"]:
        if t in _VEC or t == "color":
            return ('    printf("PROBE %s 3 : %%.17g %%.17g %%.17g\\n", '
                    "h_%s.d[0], h_%s.d[1], h_%s.d[2]);" % (plug, m, m, m))
        return ('    printf("PROBE %s 1 : %%.17g\\n", (double)h_%s.d[0]);'
                % (plug, m))
    if t in _VEC:
        return ('    { printf("PROBE %s %%zu :", out_%s.size()*3);'
                " for (size_t _i=0;_i<out_%s.size();++_i)"
                ' printf(" %%.17g %%.17g %%.17g", out_%s[_i].x, out_%s[_i].y,'
                " out_%s[_i].z); printf(\"\\n\"); }"
                % (plug, m, m, m, m, m))
    return ('    { printf("PROBE %s %%zu :", out_%s.size());'
            " for (size_t _i=0;_i<out_%s.size();++_i)"
            ' printf(" %%.17g", (double)out_%s[_i]); printf("\\n"); }'
            % (plug, m, m, m))


_SHIM = r"""#include "nd_runtime.h"
#include <cstdio>
#include <vector>
#include <cmath>
#include <initializer_list>

struct MVector { double x, y, z;
    MVector() : x(0), y(0), z(0) {}
    MVector(double a, double b, double c) : x(a), y(b), z(c) {} };
// Row-major 4x4 shim mirroring Maya's MMatrix: a public `matrix[4][4]` member
// (as the transform emitter writes via m.matrix[r][c]) plus operator()(r, c)
// (as the nd_lower matrix materialiser reads). The initializer_list ctor seeds
// 16 row-major doubles for the generic input fixtures.
struct MMatrix { double matrix[4][4];
    MMatrix() { for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j)
                    matrix[i][j] = (i == j) ? 1.0 : 0.0; }
    MMatrix(std::initializer_list<double> v) { int k = 0;
        for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j)
            matrix[i][j] = *(v.begin() + k++); }
    double operator()(int r, int c) const { return matrix[r][c]; } };
struct MPoint { double x, y, z, w;
    MPoint() : x(0), y(0), z(0), w(1) {}
    MPoint(double a, double b, double c) : x(a), y(b), z(c), w(1) {} };
struct MColor { float r, g, b, a;
    MColor() : r(0), g(0), b(0), a(1) {}
    MColor(float R, float G, float B, float A) : r(R), g(G), b(B), a(A) {} };
struct MAngle { double v; MAngle(double a) : v(a) {} };
struct MTime  { double v; MTime(double a)  : v(a) {} };
struct MockHandle {
    double d[3] = {0, 0, 0};
    void setDouble(double a) { d[0] = a; }
    void setFloat(float a)   { d[0] = a; }
    void setInt(int a)       { d[0] = a; }
    void setBool(bool a)     { d[0] = a ? 1.0 : 0.0; }
    void setShort(short a)   { d[0] = a; }
    void setMAngle(MAngle a) { d[0] = a.v; }
    void setMTime(MTime a)   { d[0] = a.v; }
    void set3Double(double a, double b, double c) { d[0]=a; d[1]=b; d[2]=c; }
    void set3Float(float a, float b, float c) { d[0]=a; d[1]=b; d[2]=c; }
};
"""


def _gen_cpp(ins, outs, values, body):
    L = [_SHIM, "int main() {"]
    for d in ins:
        L.append(_decl_input(d, values[d["plug"]]))
    for d in outs:
        L.append(_decl_output(d))
    L.append("    // ===== lowered compute =====")
    L += body
    L.append("    // ===== probes =====")
    for d in outs:
        L.append(_print_output(d))
    L.append("    return 0;")
    L.append("}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# numpy oracle
# ---------------------------------------------------------------------------
class _Self:
    pass


def _oracle(ins, outs, values, source, init=None):
    obj = _Self()
    for d in ins:
        t = d["meta"]["type"]
        v = values[d["plug"]]
        if d["meta"]["is_array"]:
            if t in _VEC:
                arr = np.asarray(v, dtype=np.float64).reshape(-1, 3)
            elif t == "matrix":
                arr = np.asarray(v, dtype=np.float64).reshape(-1, 4, 4)
            else:
                arr = np.asarray(v, dtype=_NP_DTYPE[t])
            setattr(obj, d["plug"], arr)
        elif t == "matrix":
            setattr(obj, d["plug"], np.asarray(v, dtype=np.float64).reshape(4, 4))
        elif t in _VEC:
            setattr(obj, d["plug"], np.asarray(v, dtype=np.float64))
        elif t == "bool":
            setattr(obj, d["plug"], bool(v))
        elif t in ("int", "enum"):
            setattr(obj, d["plug"], int(v))
        else:
            setattr(obj, d["plug"], float(v))
    # The interpreted node evaluates INIT (helper defs) then compute in one
    # namespace; mirror that so the oracle sees the same helpers. Imports are
    # stripped (numpy is injected; the build_default_output import is unused by
    # the numeric helpers).
    src = source if not init else (_strip_imports(init) + "\n" + source)
    exec(src, {"np": np, "self": obj})
    out = {}
    for d in outs:
        out[d["plug"]] = np.asarray(getattr(obj, d["plug"]),
                                    dtype=np.float64).ravel()
    return out


# ---------------------------------------------------------------------------
# compile + run
# ---------------------------------------------------------------------------
def _compile_run(cpp, tag):
    cxx = shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        return None, "no C++ compiler on PATH"
    # Private per-invocation temp dir so two harness processes on this checkout
    # (the Maya-2024 and Maya-2026 gates at once) never race on a fixed file --
    # one's cleanup deleting the other's binary between compile and exec. The nd::
    # runtime is still found via -I _INC (native/compiler, where nd_runtime.h is).
    with tempfile.TemporaryDirectory(prefix="ndl_%s_" % tag) as d:
        src = os.path.join(d, "t.cpp")
        exe = os.path.join(d, "t.bin")
        with open(src, "w") as f:
            f.write(cpp)
        r = subprocess.run([cxx, "-std=c++17", "-O2", "-I", _INC, src,
                            "-o", exe], capture_output=True, text=True)
        if r.returncode != 0:
            return None, "COMPILE FAILED:\n" + r.stderr
        out = subprocess.run([exe], capture_output=True, text=True)
        if out.returncode != 0:
            return None, "RUN FAILED:\n" + out.stderr
        return out.stdout, None


def _parse_probes(text):
    got = {}
    for line in text.splitlines():
        t = line.split()
        if len(t) < 3 or t[0] != "PROBE":
            continue
        plug = t[1]
        colon = t.index(":")
        got[plug] = np.array([float(x) for x in t[colon + 1:]], dtype=np.float64)
    return got


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
# (name, ins, outs, source, values)  ins/outs as (plug, type, is_array)
POS = [
    ("scalar_double", [("a", "double", False)], [("b", "double", False)],
     "self.b = self.a * 2.0 + 1.0", {"a": 3.5}),
    ("scalar_int", [("n", "int", False)], [("m", "int", False)],
     "self.m = self.n * self.n", {"n": 7}),
    ("scalar_bool_passthrough", [("flag", "bool", False)],
     [("r", "bool", False)], "self.r = self.flag", {"flag": True}),
    ("scalar_bool_from_cmp", [("a", "double", False)], [("r", "bool", False)],
     "self.r = self.a >= 2.0", {"a": 3.0}),
    ("angle_io", [("ang", "angle", False)], [("res", "angle", False)],
     "self.res = self.ang * 2.0", {"ang": 0.5}),
    ("time_io", [("t", "time", False)], [("o", "double", False)],
     "self.o = self.t + 10.0", {"t": 24.0}),
    ("vector_scalar", [("v", "vector", False)], [("w", "vector", False)],
     "self.w = self.v * 2.0", {"v": [1.0, 2.0, 3.0]}),
    ("vector_cross", [("v", "vector", False), ("u", "vector", False)],
     [("w", "vector", False)], "self.w = np.cross(self.v, self.u)",
     {"v": [1.0, 0.0, 0.0], "u": [0.0, 1.0, 0.0]}),
    ("numeric_array_sq", [("xs", "double", True)], [("ys", "double", True)],
     "self.ys = self.xs * self.xs", {"xs": [1.0, 2.0, 3.0, 4.0]}),
    ("numeric_array_reduce", [("xs", "double", True)],
     [("total", "double", False)], "self.total = np.sum(self.xs)",
     {"xs": [1.0, 2.0, 3.0, 4.0]}),
    ("numeric_array_norm", [("xs", "double", True)],
     [("nrm", "double", False)], "self.nrm = np.linalg.norm(self.xs)",
     {"xs": [3.0, 4.0]}),
    ("int_array_scale", [("ks", "int", True)], [("ss", "int", True)],
     "self.ss = self.ks * 2", {"ks": [1, 2, 3]}),
    ("vector_array_offset", [("pts", "vector", True)],
     [("outp", "vector", True)], "self.outp = self.pts + 1.0",
     {"pts": [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, -3.0, 4.0]]}),
    ("multi_output", [("a", "double", False), ("b", "double", False)],
     [("s", "double", False), ("d", "double", False)],
     "self.s = self.a + self.b\nself.d = self.a - self.b",
     {"a": 5.0, "b": 3.0}),
    ("local_intermediate", [("a", "double", False), ("b", "double", False)],
     [("r", "double", False)], "t = self.a * self.b\nself.r = t + 1.0",
     {"a": 2.0, "b": 3.0}),
    ("array_maximum", [("xs", "double", True)], [("ys", "double", True)],
     "self.ys = np.maximum(self.xs, 0.0)",
     {"xs": [-1.0, 2.0, -3.0, 4.0]}),
    ("unused_input", [("a", "double", False), ("unused", "double", False)],
     [("b", "double", False)], "self.b = self.a + 1.0",
     {"a": 10.0, "unused": 999.0}),
    # RNG: RandomState(seed).random(...) -> nd::MT19937, bit-exact vs numpy's
    # legacy RandomState (draw-for-draw in nd_rng_test.py). These prove the FULL
    # lowered path preserves that bit-exactness, so a lowered RNG node
    # parity-checks cleanly (verify._verify_one does NOT skip it).
    ("rng_random_sum", [], [("total", "double", False)],
     "import numpy as np\n"
     "rng = np.random.RandomState(12345)\n"
     "v = rng.random(4)\n"
     "self.total = float(np.sum(v))\n", {}),
    ("rng_random_vec", [], [("w", "vector", False)],
     "import numpy as np\n"
     "rng = np.random.RandomState(7)\n"
     "self.w = rng.random(3)\n", {}),
    ("rng_seed_from_input", [("seed", "int", False)],
     [("total", "double", False)],
     "import numpy as np\n"
     "rng = np.random.RandomState(int(self.seed))\n"
     "v = rng.random(2)\n"
     "self.total = float(v[0] + v[1])\n", {"seed": 20260708}),
    ("rng_random_sample", [], [("total", "double", False)],
     "import numpy as np\n"
     "rng = np.random.RandomState(99)\n"
     "v = rng.random_sample(5)\n"
     "self.total = float(np.sum(v))\n", {}),
    ("rng_random_2d", [], [("total", "double", False)],
     "import numpy as np\n"
     "rng = np.random.RandomState(3)\n"
     "v = rng.random((2, 3))\n"
     "self.total = float(np.sum(v))\n", {}),
    # ---- P1 op coverage (SP-5) ----------------------------------------------
    # array compare, bitwise/invert, np.where, multiple-newaxis broadcast,
    # tile/roll/take, ys/xs = np.nonzero unpack, and the GoL zero-pad stencil.
    # These drive the newly-wired ops through the FULL generic lower path
    # (materialise -> transpile -> output writer) and parity-check vs numpy.
    ("cmp_array_scalar", [("xs", "double", True)], [("r", "bool", True)],
     "self.r = self.xs >= 2.0", {"xs": [1.0, 2.0, 3.0, 0.5]}),
    ("cmp_array_array", [("xs", "double", True), ("ys", "double", True)],
     [("r", "bool", True)], "self.r = self.xs > self.ys",
     {"xs": [1.0, 5.0, 3.0], "ys": [2.0, 4.0, 3.0]}),
    # bitwise on bool arrays == the GoL stencil's alive-mask primitives.
    ("bitwise_bool_array", [("a", "bool", True), ("b", "bool", True)],
     [("r", "bool", True)], "self.r = (self.a & self.b) | (~self.a)",
     {"a": [True, False, True, False], "b": [True, True, False, False]}),
    ("bitwise_int_array", [("a", "int", True), ("b", "int", True)],
     [("r", "int", True)], "self.r = (self.a & self.b) | (self.a ^ self.b)",
     {"a": [6, 3, 12], "b": [3, 3, 10]}),
    ("where_array", [("xs", "double", True)], [("r", "double", True)],
     "self.r = np.where(self.xs > 0.0, self.xs, -self.xs)",
     {"xs": [-1.0, 2.0, -3.0, 4.0]}),
    ("where_scalar_branches", [("xs", "double", True)],
     [("r", "double", True)], "self.r = np.where(self.xs > 2.0, 1.0, 0.0)",
     {"xs": [1.0, 2.0, 3.0, 4.0]}),
    # single np.newaxis on TWO operands -> GoL's centers[:,None,:]+corners[None,:,:]
    ("newaxis_center_corner", [], [("out", "double", True)],
     "import numpy as np\n"
     "centers = np.arange(6, dtype=np.float64).reshape(2, 3)\n"
     "corners = np.arange(9, dtype=np.float64).reshape(3, 3)\n"
     "pts = centers[:, None, :] + corners[None, :, :]\n"
     "self.out = pts.reshape(-1)\n", {}),
    # DOUBLE np.newaxis -> GoL's base=(8*np.arange(m))[:,None,None]
    ("double_newaxis_int", [], [("out", "int", True)],
     "import numpy as np\n"
     "base = (8 * np.arange(3, dtype=np.int64))[:, None, None]\n"
     "quad = np.arange(24, dtype=np.int64).reshape(1, 6, 4)\n"
     "idx = base + quad\n"
     "self.out = idx.reshape(-1)\n", {}),
    # np.cumsum: axis=None FLATTENS to 1-D, axis=k preserves shape.
    ("cumsum_flat", [("xs", "double", True)], [("out", "double", True)],
     "self.out = np.cumsum(self.xs)", {"xs": [1.0, 2.0, 3.0, 4.0]}),
    ("cumsum_axes", [("xs", "double", True)], [("out", "double", True)],
     "m = self.xs.reshape(2, 3)\n"
     "self.out = np.concatenate([np.cumsum(m, axis=0).reshape(-1),\n"
     "                           np.cumsum(m, axis=1).reshape(-1),\n"
     "                           np.cumsum(m).reshape(-1)])\n",
     {"xs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]}),
    ("cumsum_int", [("a", "int", True)], [("out", "int", True)],
     "self.out = np.cumsum(self.a)", {"a": [5, -2, 7, 0, 3]}),
    # The EXCLUSIVE prefix sum as a strictly-upper matmul (what patch_relax used
    # before cumsum existed) vs the shift form. `cumsum(a) - a` would NOT match:
    # subtracting rounds a second time. Shifting is pure data movement, so this
    # difference must be EXACTLY zero, not merely close.
    ("cumsum_exclusive_equals_matmul", [("xs", "double", True)],
     [("out", "double", True)],
     "import numpy as np\n"
     "a = self.xs.reshape(2, 4)\n"
     "k = np.arange(4)\n"
     "pre = (k[:, None] < k[None, :]).astype(np.float64)\n"
     "via_matmul = a @ pre\n"
     "shifted = np.concatenate([np.zeros((2, 1)),\n"
     "                          np.cumsum(a, axis=1)[:, :-1]], axis=1)\n"
     "self.out = (via_matmul - shifted).reshape(-1)\n",
     {"xs": [1.0, 1e16, 1.0, -1e16, 0.5, 0.25, 0.125, 0.0625]}),
    ("tile_1d", [("xs", "double", True)], [("out", "double", True)],
     "self.out = np.tile(self.xs, 3)", {"xs": [1.0, 2.0, 3.0]}),
    # correctness TRAP: np.roll WRAPS (cyclic) -- distinct from the zero-pad
    # stencil below. Both must parity-pass, proving roll-wrap is not conflated
    # with the bounded GoL neighbour count.
    ("roll_wrap", [("xs", "double", True)], [("out", "double", True)],
     "self.out = np.roll(self.xs, 2)", {"xs": [1.0, 2.0, 3.0, 4.0, 5.0]}),
    ("take_flat", [("xs", "double", True), ("idx", "int", True)],
     [("out", "double", True)], "self.out = np.take(self.xs, self.idx)",
     {"xs": [10.0, 20.0, 30.0, 40.0], "idx": [3, 0, 2, 1, 0]}),
    # ys, xs = np.nonzero(2d) unpack -> per-axis int64 index arrays (GoL cores).
    ("nonzero_unpack_2d", [], [("ysout", "int", True), ("xsout", "int", True)],
     "import numpy as np\n"
     "board = np.array([[0, 1, 0], [1, 0, 1]], dtype=np.int64)\n"
     "ys, xs = np.nonzero(board)\n"
     "self.ysout = ys\n"
     "self.xsout = xs\n", {}),
    # the GoL neighbour-count kernel: ZERO-PADDED (bounded) shifted-slice sums
    # via augmented slice-assign, then the Conway alive mask. This is the exact
    # stencil _gol_step uses -- NOT np.roll wrap.
    ("gol_zeropad_stencil", [], [("out", "bool", True)],
     "import numpy as np\n"
     "b = np.array([[0, 0, 0, 0, 0],\n"
     "              [0, 0, 1, 0, 0],\n"
     "              [0, 0, 1, 0, 0],\n"
     "              [0, 0, 1, 0, 0],\n"
     "              [0, 0, 0, 0, 0]], dtype=np.int64)\n"
     "n = np.zeros_like(b)\n"
     "n[1:, :] += b[:-1, :]\n"
     "n[:-1, :] += b[1:, :]\n"
     "n[:, 1:] += b[:, :-1]\n"
     "n[:, :-1] += b[:, 1:]\n"
     "n[1:, 1:] += b[:-1, :-1]\n"
     "n[1:, :-1] += b[:-1, 1:]\n"
     "n[:-1, 1:] += b[1:, :-1]\n"
     "n[:-1, :-1] += b[1:, 1:]\n"
     "alive = (n == 3) | ((b == 1) & (n == 2))\n"
     "self.out = alive.reshape(-1)\n", {}),
    # ---- matrix INPUT lift (Stage 3, #40) -----------------------------------
    # A scalar `matrix` input materialises to a (4, 4) nd::Array (row-major,
    # read via MMatrix::operator()(r, c)); double-subscript indexing extracts
    # elements. This is the shapeMatrix scalar path the metaballs node needs.
    ("matrix_scalar_elems", [("m", "matrix", False)], [("r", "double", False)],
     "self.r = float(self.m[3, 0] * 2.0 + self.m[3, 1] + self.m[0, 0])",
     {"m": [[2.0, 0.0, 0.0, 0.0], [0.0, 3.0, 0.0, 0.0],
            [0.0, 0.0, 4.0, 0.0], [-2.0, 5.0, 0.0, 1.0]]}),
    # A `matrix` ARRAY input materialises to an (N, 4, 4) nd::Array; a counted
    # for-range over N with triple-subscript reads + scalar subscript-assign is
    # the exact shape of the metaballs CSG fold (loop over shapeMatrix[i]).
    ("matrix_array_trace", [("mats", "matrix", True)],
     [("out", "double", True)],
     "n = self.mats.shape[0]\n"
     "res = np.empty(n)\n"
     "for i in range(n):\n"
     "    res[i] = float(self.mats[i, 0, 0] + self.mats[i, 1, 1]"
     " + self.mats[i, 2, 2] + self.mats[i, 3, 3])\n"
     "self.out = res\n",
     {"mats": [[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0], [1.5, 0.0, 0.0, 1.0]],
               [[2.0, 0.0, 0.0, 0.0], [0.0, 3.0, 0.0, 0.0],
                [0.0, 0.0, 4.0, 0.0], [-2.0, 0.0, 0.0, 1.0]],
               [[0.5, 0.0, 0.0, 0.0], [0.0, 0.5, 0.0, 0.0],
                [0.0, 0.0, 0.5, 0.0], [7.25, 1.0, 2.0, 1.0]]]}),
    # ---- color OUTPUT from a tuple pack (nd (3,) -> set3Float) ---------------
    # A fully-numeric compute ending in `self.outColor = (r, g, b)` now lowers
    # deterministically: the tuple literal packs a rank-1 nd::Array (ex_Tuple),
    # and the color writer sets the FLOAT R/G/B children.
    ("color_pack",
     [("cr", "double", False), ("cg", "double", False), ("cb", "double", False)],
     [("oc", "color", False)],
     "self.oc = (self.cr, self.cg, self.cb)",
     {"cr": 0.5, "cg": 0.25, "cb": 0.75}),
    # The LIST spelling of the case above. ex_List delegates to the same
    # _sequence_literal as ex_Tuple, so the emitted C++ is byte-identical -- but
    # nothing pinned that, and Transpiler.ex_List could be deleted with no test
    # going red. This fixture is the pin.
    ("color_pack_list",
     [("cr", "double", False), ("cg", "double", False), ("cb", "double", False)],
     [("oc", "color", False)],
     "self.oc = [self.cr, self.cg, self.cb]",
     {"cr": 0.5, "cg": 0.25, "cb": 0.75}),
    ("color_bright_contrast",
     [("cr", "double", False), ("cg", "double", False), ("cb", "double", False),
      ("bright", "double", False), ("contrast", "double", False)],
     [("oc", "color", False)],
     "r = self.cr * self.bright\n"
     "g = self.cg * self.bright\n"
     "b = self.cb * self.bright\n"
     "r = (r - 0.5) * self.contrast + 0.5\n"
     "g = (g - 0.5) * self.contrast + 0.5\n"
     "b = (b - 0.5) * self.contrast + 0.5\n"
     "r = min(max(r, 0.0), 1.0)\n"
     "g = min(max(g, 0.0), 1.0)\n"
     "b = min(max(b, 0.0), 1.0)\n"
     "self.oc = (r, g, b)",
     {"cr": 0.8, "cg": 0.2, "cb": 0.5, "bright": 1.3, "contrast": 1.5}),
    # ---- vector OUTPUT from an ALL-INTEGER tuple pack (int64 -> double) -------
    # `self.w = (0, 0, 1)` lowers to nd::from_data<int64_t>(...); the vector
    # writer must _cast_array to double, else `nd::Array<double> = <int64_t>` does
    # not compile. Up-vectors / zero directions / euler resets all take this shape.
    ("vector_int_pack", [], [("w", "vector", False)],
     "self.w = (0, 0, 1)", {}),
    ("vector_int_pack_from_ints", [("n", "int", False)],
     [("w", "vector", False)], "self.w = (self.n, 0, self.n * 2)", {"n": 3}),
]

# ---------------------------------------------------------------------------
# inline-helper fixtures (SP-5b): the compute calls free functions DEFINED in the
# node's INIT tier. The transpiler must monomorphise each helper per call-site
# arg-type signature, emit it as a C++ lambda ABOVE the compute body
# (callee-before-caller), and infer its return type from `return` stmts.
# ---------------------------------------------------------------------------
# The real Game of Life numpy kernel shared by the mPyMesh + mPyFile templates.
# _gol_board is a pure function of (h, w, samples, frame, reset): nested helper
# calls, a default arg, a for-range loop reassigning a local, RNG, the zero-pad
# neighbour stencil and the Conway alive mask, all in one.
_GOL_INIT = (
    "import numpy as np\n"
    "from mpynode._api2.mpy_mesh import build_default_output\n"
    "\n"
    "def _gol_seed(h, w, density, seed=0):\n"
    "    rng = np.random.RandomState(int(seed) & 0x7fffffff)\n"
    "    return rng.random((int(h), int(w))) < float(density)\n"
    "\n"
    "def _gol_step(board):\n"
    "    b = board.astype(np.uint8)\n"
    "    pad = np.zeros((b.shape[0] + 2, b.shape[1] + 2), dtype=np.uint8)\n"
    "    pad[1:-1, 1:-1] = b\n"
    "    n = (pad[:-2, :-2] + pad[:-2, 1:-1] + pad[:-2, 2:] +\n"
    "         pad[1:-1, :-2]                 + pad[1:-1, 2:] +\n"
    "         pad[2:, :-2]  + pad[2:, 1:-1]  + pad[2:, 2:])\n"
    "    return (n == 3) | ((b == 1) & (n == 2))\n"
    "\n"
    "def _gol_board(h, w, samples, frame, reset):\n"
    "    h = max(1, int(h))\n"
    "    w = max(1, int(w))\n"
    "    density = float(samples) / float(h * w)\n"
    "    if reset:\n"
    "        return _gol_seed(h, w, density, seed=int(frame))\n"
    "    board = _gol_seed(h, w, density, seed=0)\n"
    "    for _ in range(max(0, int(frame) - 1)):\n"
    "        board = _gol_step(board)\n"
    "    return board\n"
)

# (name, ins, outs, init, source, values)
HELP = [
    # scalar helper, single arg + arithmetic on the result.
    ("help_scalar", [("a", "double", False)], [("r", "double", False)],
     "def _dbl(x):\n    return x * 2.0\n",
     "self.r = _dbl(self.a) + 1.0", {"a": 3.0}),
    # array arg + array return (whole-array elementwise inside the helper).
    ("help_array", [("xs", "double", True)], [("ys", "double", True)],
     "def _scale(a, k):\n    return a * k\n",
     "self.ys = _scale(self.xs, 3.0)", {"xs": [1.0, 2.0, 3.0, 4.0]}),
    # helper calling helper -> callee-before-caller lambda emission order.
    ("help_nested", [("a", "double", False)], [("r", "double", False)],
     "def _inner(x):\n    return x + 1.0\n\n"
     "def _outer(x):\n    return _inner(x) * 2.0\n",
     "self.r = _outer(self.a)", {"a": 4.0}),
    # default arg omitted (b defaults 0.0) AND overridden (via keyword) -> two
    # distinct monomorphisations of the SAME helper coexist.
    ("help_default", [("a", "double", False)],
     [("d", "double", False), ("o", "double", False)],
     "def _lin(x, m, b=0.0):\n    return x * m + b\n",
     "self.d = _lin(self.a, 2.0)\nself.o = _lin(self.a, 2.0, b=5.0)",
     {"a": 3.0}),
    # same helper called with int AND double args -> two monomorphisations
    # (distinct C++ scalar types) from one def.
    ("help_polymorphic",
     [("i", "int", False), ("f", "double", False)],
     [("ri", "int", False), ("rf", "double", False)],
     "def _sq(x):\n    return x * x\n",
     "self.ri = _sq(self.i)\nself.rf = _sq(self.f)",
     {"i": 6, "f": 2.5}),
    # THE FLAGSHIP KERNEL: the full GoL board (nested helpers, default arg,
    # for-loop, RNG, zero-pad stencil, Conway mask) lowered + bit-faithful.
    ("help_gol_board",
     [("h", "int", False), ("w", "int", False), ("samples", "int", False),
      ("frame", "int", False), ("reset", "enum", False)],
     [("out", "bool", True)], _GOL_INIT,
     "board = _gol_board(self.h, self.w, self.samples, self.frame, self.reset)\n"
     "self.out = board.reshape(-1)\n",
     {"h": 6, "w": 6, "samples": 10, "frame": 4, "reset": 0}),
    # GoL board with reset=1 -> the reset branch (seed varies with frame).
    ("help_gol_board_reset",
     [("h", "int", False), ("w", "int", False), ("samples", "int", False),
      ("frame", "int", False), ("reset", "enum", False)],
     [("out", "bool", True)], _GOL_INIT,
     "board = _gol_board(self.h, self.w, self.samples, self.frame, self.reset)\n"
     "self.out = board.reshape(-1)\n",
     {"h": 5, "w": 7, "samples": 12, "frame": 9, "reset": 1}),
    # DIRECT SELF-RECURSION, integer kernel (factorial). The base case returns
    # an int and the recursive branch is int*int -> the least-fixed-point return
    # type must stay int64 (not over-widen to double). Emits a
    # `std::function<int64_t(int64_t)>` recursive lambda.
    ("help_rec_factorial", [("n", "int", False)], [("r", "int", False)],
     "def _fac(n):\n"
     "    if n <= 1:\n"
     "        return 1\n"
     "    return n * _fac(n - 1)\n",
     "self.r = _fac(self.n)", {"n": 8}),
    # DIRECT SELF-RECURSION, float kernel with TWO self-calls per level and a
    # branch base case: the Cox-de Boor / uniform B-spline basis recurrence.
    # Exercises float return-type inference + double recursion depth.
    ("help_rec_cox_deboor",
     [("i", "int", False), ("k", "int", False), ("x", "double", False)],
     [("r", "double", False)],
     "def _cdb(i, k, x):\n"
     "    if k == 0:\n"
     "        if i <= x and x < i + 1.0:\n"
     "            return 1.0\n"
     "        return 0.0\n"
     "    a = (x - i) / k * _cdb(i, k - 1, x)\n"
     "    b = (i + k + 1.0 - x) / k * _cdb(i + 1, k - 1, x)\n"
     "    return a + b\n",
     "self.r = _cdb(self.i, self.k, self.x)",
     {"i": 0, "k": 3, "x": 1.7}),
    # DIRECT SELF-RECURSION whose returns MIX int (base) and float (recursive
    # branch adds 0.5): the fixed point must promote to double so the recursive
    # sum is not truncated. Guards against base-case-only dtype inference.
    ("help_rec_mixed_dtype", [("n", "int", False)], [("r", "double", False)],
     "def _acc(n):\n"
     "    if n <= 0:\n"
     "        return 0\n"
     "    return 0.5 + _acc(n - 1)\n",
     "self.r = _acc(self.n)", {"n": 5}),
    # RECURSION (two self-calls, fib) that ALSO calls a sibling NON-recursive
    # helper: the sibling must be emitted exactly once across the fixed-point
    # re-transpiles, and the self-call arg (`n - 1`) must map to the SAME
    # monomorphisation as the top-level call (`self.n`), else it looks polymorphic.
    ("help_rec_fib_sibling", [("n", "int", False)], [("r", "int", False)],
     "def _bump(x):\n"
     "    return x + 1\n"
     "\n"
     "def _fib(n):\n"
     "    if n < 2:\n"
     "        return _bump(n) - 1\n"
     "    return _fib(n - 1) + _fib(n - 2)\n",
     "self.r = _fib(self.n)", {"n": 12}),
]

# helper rejects: try_lower_compute must return None (fall back to AI porter)
HELP_REJ = [
    # self-recursion with NO base case (every `return` re-invokes the helper) ->
    # would not terminate; the recursive-lambda path rejects when no base-case
    # return exists to anchor the return type.
    ("help_recursive", [("a", "double", False)], [("r", "double", False)],
     "def _f(x):\n    return _f(x) + 1.0\n", "self.r = _f(self.a)"),
    # helper references an unknown free name -> body fails -> whole node rejects.
    ("help_unknown_name", [("a", "double", False)], [("r", "double", False)],
     "def _g(x):\n    return x + _MISSING\n", "self.r = _g(self.a)"),
    # *args helper -> unsupported signature.
    ("help_starargs", [("a", "double", False)], [("r", "double", False)],
     "def _h(*xs):\n    return xs[0]\n", "self.r = _h(self.a)"),
    # mutual recursion (cycle across two helpers) -> unsupported (the second
    # helper's std::function would be referenced before its declaration).
    ("help_mutual", [("a", "double", False)], [("r", "double", False)],
     "def _p(x):\n    return _q(x) + 1.0\n\ndef _q(x):\n    return _p(x) * 2.0\n",
     "self.r = _p(self.a)"),
    # POLYMORPHIC recursion: the recursive call uses a different argument type
    # (int vs double) -> unbounded monomorphisation -> reject.
    ("help_poly_recursive", [("a", "double", False)],
     [("r", "double", False)],
     "def _pr(x):\n    if x < 1.0:\n        return 0.0\n"
     "    return _pr(int(x) - 1) + 1.0\n",
     "self.r = _pr(self.a)"),
    # ARRAY-returning recursion: only scalar recursion is supported; a helper
    # whose base case returns an array is rejected (fail-closed).
    ("help_array_recursive", [("a", "double", True), ("k", "int", False)],
     [("r", "double", True)],
     "def _ar(a, k):\n    if k <= 0:\n        return a\n"
     "    return _ar(a, k - 1) + 1.0\n",
     "self.r = _ar(self.a, self.k)"),
]


# rejects: try_lower_compute must return None (codegen falls back)
REJ = [
    # an unsupported input that is actually READ -> reject (an untouched one is
    # legitimately lowerable -- see `unused_input` above).
    ("matrix_in_used", [("m", "matrix", False)], [("o", "double", False)],
     "self.o = self.m"),
    ("string_in_used", [("s", "string", False)], [("o", "double", False)],
     "self.o = self.s"),
    ("unwritten_output", [("a", "double", False)],
     [("b", "double", False), ("c", "double", False)], "self.b = self.a"),
    # write-ONLY non-declared self.<attr> (a dead store / typo'd output): never
    # read back, so it is NOT persistent state and has no output writer -> reject
    # rather than absorb a meaningless store. (A written-AND-read one IS state and
    # lowers via the per-node registry -- test_native_stateful_scaffold.py.)
    ("writeonly_selfwrite", [("a", "double", False)], [("b", "double", False)],
     "self.b = self.a\nself._dead = 1.0"),
    # state READ with NO write: a self.<attr> that is neither an input, an output,
    # nor ever assigned -- its value comes from OUTSIDE the node. nd_lower's
    # member-state model only covers state WRITTEN before it is read, so a pure
    # orphan read has no binding and rejects -> AI porter.
    ("persistent_state_read", [("a", "double", False)], [("o", "double", False)],
     "self.o = self.a + self._state"),
    ("matrix_out", [("a", "double", False)], [("o", "matrix", False)],
     "self.o = self.a"),
]


# ---------------------------------------------------------------------------
# geometry-generator fixtures (mesh/curve/surface buffer fill)
# ---------------------------------------------------------------------------
# emitter buffer layout per kind: (buffer name, probe kind), including the
# OPTIONAL channels (normals/colors + indices, periodic flags, knot vectors). A
# fixture that leaves a channel unset produces an empty buffer the oracle omits;
# one that sets it exercises the matching nd_lower writer.
_GEO_BUFS = {
    "mesh":    [("points", "mpoint"), ("counts", "int_arr"),
                ("indices", "int_arr"), ("normals", "vec3"),
                ("normalIndices", "int_arr"), ("colors", "color"),
                ("colorIndices", "int_arr")],
    "curve":   [("cvs", "mpoint"), ("degree", "int_scalar"),
                ("periodic", "int_scalar"), ("knots", "double_arr")],
    "surface": [("cvs", "mpoint"), ("numU", "int_scalar"),
                ("numV", "int_scalar"), ("degreeU", "int_scalar"),
                ("degreeV", "int_scalar"), ("periodicU", "int_scalar"),
                ("periodicV", "int_scalar"), ("knotsU", "double_arr"),
                ("knotsV", "double_arr")],
}


def _geo_decls(kind):
    if kind == "mesh":
        return ["    std::vector<MPoint> points;",
                "    std::vector<int> counts;",
                "    std::vector<int> indices;",
                "    std::vector<MVector> normals;",
                "    std::vector<int> normalIndices;",
                "    std::vector<MColor> colors;",
                "    std::vector<int> colorIndices;"]
    if kind == "curve":
        return ["    std::vector<MPoint> cvs;", "    int degree = 3;",
                "    int periodic = 0;", "    std::vector<double> knots;"]
    return ["    std::vector<MPoint> cvs;",
            "    int numU = 0, numV = 0;",
            "    int degreeU = 3, degreeV = 3;",
            "    int periodicU = 0, periodicV = 0;",
            "    std::vector<double> knotsU;",
            "    std::vector<double> knotsV;"]


def _geo_probes(kind):
    L = []
    for buf, bt in _GEO_BUFS[kind]:
        if bt == "mpoint":
            L.append('    { printf("PROBE %s %%zu :", %s.size()*3);'
                     " for (size_t _i=0;_i<%s.size();++_i)"
                     ' printf(" %%.17g %%.17g %%.17g", %s[_i].x, %s[_i].y,'
                     ' %s[_i].z); printf("\\n"); }'
                     % (buf, buf, buf, buf, buf, buf))
        elif bt == "vec3":
            L.append('    { printf("PROBE %s %%zu :", %s.size()*3);'
                     " for (size_t _i=0;_i<%s.size();++_i)"
                     ' printf(" %%.17g %%.17g %%.17g", %s[_i].x, %s[_i].y,'
                     ' %s[_i].z); printf("\\n"); }'
                     % (buf, buf, buf, buf, buf, buf))
        elif bt == "color":
            L.append('    { printf("PROBE %s %%zu :", %s.size()*4);'
                     " for (size_t _i=0;_i<%s.size();++_i)"
                     ' printf(" %%.17g %%.17g %%.17g %%.17g", (double)%s[_i].r,'
                     ' (double)%s[_i].g, (double)%s[_i].b, (double)%s[_i].a);'
                     ' printf("\\n"); }'
                     % (buf, buf, buf, buf, buf, buf, buf))
        elif bt == "int_arr":
            L.append('    { printf("PROBE %s %%zu :", %s.size());'
                     " for (size_t _i=0;_i<%s.size();++_i)"
                     ' printf(" %%.17g", (double)%s[_i]); printf("\\n"); }'
                     % (buf, buf, buf, buf))
        elif bt == "double_arr":
            L.append('    { printf("PROBE %s %%zu :", %s.size());'
                     " for (size_t _i=0;_i<%s.size();++_i)"
                     ' printf(" %%.17g", %s[_i]); printf("\\n"); }'
                     % (buf, buf, buf, buf))
        else:  # int_scalar
            L.append('    printf("PROBE %s 1 : %%.17g\\n", (double)%s);'
                     % (buf, buf))
    return L


def _gen_geo_cpp(ins, kind, values, body):
    L = [_SHIM, "int main() {"]
    for d in ins:
        L.append(_decl_input(d, values[d["plug"]]))
    L += _geo_decls(kind)
    L.append("    // ===== lowered geo compute =====")
    L += body
    L.append("    // ===== probes =====")
    L += _geo_probes(kind)
    L.append("    return 0;")
    L.append("}")
    return "\n".join(L) + "\n"


def _strip_imports(source):
    """Blank top-level import statements (numpy is provided in the oracle
    namespace; helper imports are unused after the build line is stripped)."""
    import ast as _ast
    tree = _ast.parse(source)
    strip = []
    for st in tree.body:
        if isinstance(st, (_ast.Import, _ast.ImportFrom)):
            strip.append((st.lineno, getattr(st, "end_lineno", st.lineno)))
    if not strip:
        return source
    lines = source.splitlines()
    for (a, b) in strip:
        for ln in range(a, b + 1):
            if 1 <= ln <= len(lines):
                lines[ln - 1] = ""
    return "\n".join(lines)


def _geo_oracle(ins, kind, values, source, init=None):
    obj = _Self()
    for d in ins:
        t = d["meta"]["type"]
        v = values[d["plug"]]
        if d["meta"]["is_array"]:
            if t in _VEC:
                arr = np.asarray(v, dtype=np.float64).reshape(-1, 3)
            elif t == "matrix":
                arr = np.asarray(v, dtype=np.float64).reshape(-1, 4, 4)
            else:
                arr = np.asarray(v, dtype=_NP_DTYPE[t])
            setattr(obj, d["plug"], arr)
        elif t == "matrix":
            setattr(obj, d["plug"], np.asarray(v, dtype=np.float64).reshape(4, 4))
        elif t in _VEC:
            setattr(obj, d["plug"], np.asarray(v, dtype=np.float64))
        elif t == "bool":
            setattr(obj, d["plug"], bool(v))
        elif t in ("int", "enum"):
            setattr(obj, d["plug"], int(v))
        else:
            setattr(obj, d["plug"], float(v))
    # Mirror lower_geo_compute: rewrite a dataclass ctor (self.outX = Mesh(...))
    # into synthetic self.<field> = <expr> assigns so the oracle populates the SAME
    # buffers the lowerer fills, then strip any remaining build_default_output
    # assign. (No-op for the non-ctor fixtures.)
    src = nd_lower._rewrite_geo_constructor(source, kind)
    src = nd_lower._strip_geo_output_assign(
        src, nd_lower._GEO_OUT_ATTR[kind])
    src = _strip_imports(src)
    if init:
        src = _strip_imports(init) + "\n" + src
    exec(src, {"np": np, "self": obj})
    out = {}
    for attr, (buf, _bt) in nd_lower._GEO_BUFFERS[kind].items():
        if hasattr(obj, attr):
            out[buf] = np.asarray(getattr(obj, attr), dtype=np.float64).ravel()
    return out


# (name, kind, ins, source, values)  ins as (plug, type, is_array)
_MESH_SRC = (
    "import numpy as np\n"
    "from mpynode._api2.mpy_mesh import build_default_output\n"
    "self.points = self.vin * self.scale\n"
    "self.counts = self.cin\n"
    "self.indices = self.iin\n"
    "self.outMesh = build_default_output(self.points, self.counts, self.indices)"
)
_CURVE_SRC = (
    "import numpy as np\n"
    "from mpynode._api2.mpy_nurbs_curve import build_default_output\n"
    "self.points = self.cvsIn + self.offset\n"
    "self.degree = 3\n"
    "self.outCurve = build_default_output(self.points, degree=self.degree)"
)
_SURF_SRC = (
    "import numpy as np\n"
    "from mpynode._api2.mpy_nurbs_surface import build_default_output\n"
    "self.cvs = self.cvsIn * self.scale\n"
    "self.num_cvs_u = self.nu\n"
    "self.num_cvs_v = self.nv\n"
    "self.outSurface = build_default_output(self.cvs, self.num_cvs_u, "
    "self.num_cvs_v)"
)
# Constructor-form fixtures (self.outX = Ctor(...)). Array literals hold only
# numeric constants (a variable inside a literal is not lowerable); the scalar
# input perturbs via a trailing scale multiply, matching the GoL pattern.
_MESH_CTOR_PV = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import Mesh\n"
    "P = np.array([[0.0,0.0,0.0],[1.0,0.0,0.0],[1.0,1.0,0.0],[0.0,1.0,0.0]], "
    "dtype=np.float64) * (1.0 + 0.1 * self.scale)\n"
    "C = np.full(1, 4, dtype=np.int32)\n"
    "I = np.array([0,1,2,3], dtype=np.int32)\n"
    "N = np.array([[0.0,0.0,1.0],[0.0,0.0,1.0],[0.0,0.0,1.0],[0.0,0.0,1.0]], "
    "dtype=np.float64)\n"
    "COL = np.array([[1.0,0.0,0.0,1.0],[0.0,1.0,0.0,1.0],[0.0,0.0,1.0,1.0],"
    "[1.0,1.0,0.0,1.0]], dtype=np.float64)\n"
    "self.outMesh = Mesh(points=P, counts=C, indices=I, normals=N, colors=COL)"
)
_MESH_CTOR_IDX = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import Mesh\n"
    "P = np.array([[0.0,0.0,0.0],[1.0,0.0,0.0],[1.0,1.0,0.0],[0.0,1.0,0.0]], "
    "dtype=np.float64) * (1.0 + 0.1 * self.scale)\n"
    "C = np.full(1, 4, dtype=np.int32)\n"
    "I = np.array([0,1,2,3], dtype=np.int32)\n"
    "Ndir = np.array([[0.0,0.0,1.0],[1.0,0.0,0.0]], dtype=np.float64)\n"
    "NI = np.array([0,0,1,1], dtype=np.int32)\n"
    "PAL = np.array([[1.0,0.0,0.0,1.0],[0.0,1.0,0.0,1.0]], dtype=np.float64)\n"
    "CI = np.array([0,1,0,1], dtype=np.int32)\n"
    "self.outMesh = Mesh(points=P, counts=C, indices=I, normals=Ndir, "
    "normal_indices=NI, colors=PAL, color_indices=CI)"
)
# Identity-arg form (GoL pattern): the compute writes self.points/counts/indices
# directly, then passes them BY NAME to the ctor. _rewrite_geo_constructor must
# DROP the self-identity assigns (else self.points = (self.points) reads a
# write-only output buffer and fails to lower).
_MESH_CTOR_SELF = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import Mesh\n"
    "self.points = np.array([[0.0,0.0,0.0],[1.0,0.0,0.0],[1.0,1.0,0.0],"
    "[0.0,1.0,0.0]], dtype=np.float64) * (1.0 + 0.1 * self.scale)\n"
    "self.counts = np.full(1, 4, dtype=np.int32)\n"
    "self.indices = np.array([0,1,2,3], dtype=np.int32)\n"
    "self.outMesh = Mesh(points=self.points, counts=self.counts, "
    "indices=self.indices)"
)
_CURVE_CTOR_PER = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import NurbsCurve\n"
    "cvs = np.array([[1.0,0.0,0.0],[0.7,0.7,0.0],[0.0,1.0,0.0],[-0.7,0.7,0.0],"
    "[-1.0,0.0,0.0],[-0.7,-0.7,0.0],[0.0,-1.0,0.0],[0.7,-0.7,0.0],"
    "[1.0,0.0,0.0],[0.7,0.7,0.0],[0.0,1.0,0.0]], dtype=np.float64) "
    "* (1.0 + 0.1 * self.scale)\n"
    "self.outCurve = NurbsCurve(points=cvs, degree=3, periodic=True)"
)
_CURVE_CTOR_KV = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import NurbsCurve\n"
    "cvs = np.array([[0.0,0.0,0.0],[1.0,0.0,0.0],[2.0,0.0,0.0],[3.0,0.0,0.0],"
    "[4.0,0.0,0.0],[5.0,0.0,0.0]], dtype=np.float64) * (1.0 + 0.1 * self.scale)\n"
    "kv = np.array([0.0,0.0,0.0,1.0,2.0,3.0,3.0,3.0], dtype=np.float64)\n"
    "self.outCurve = NurbsCurve(points=cvs, degree=3, kv=kv)"
)
_SURF_CTOR_PER = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import NurbsSurface\n"
    "rx = np.array([1.0,0.7,0.0,-0.7,-1.0,-0.7,0.0,0.7,1.0,0.7,0.0], "
    "dtype=np.float64)\n"
    "ry = np.array([0.0,0.7,1.0,0.7,0.0,-0.7,-1.0,-0.7,0.0,0.7,1.0], "
    "dtype=np.float64)\n"
    "heights = np.array([0.0,1.0,2.0,3.0], dtype=np.float64)\n"
    "ones_v = np.ones(4, dtype=np.float64)\n"
    "ones_u = np.ones(11, dtype=np.float64)\n"
    "X = (rx[:, None] * ones_v[None, :]).reshape(-1)\n"
    "Z = (ry[:, None] * ones_v[None, :]).reshape(-1)\n"
    "Y = (ones_u[:, None] * heights[None, :]).reshape(-1)\n"
    "grid = np.column_stack([X, Y, Z]) * (1.0 + 0.1 * self.scale)\n"
    "self.outSurface = NurbsSurface(points=grid, num_u=11, num_v=4, "
    "degree_u=3, degree_v=3, periodic_u=True, periodic_v=False)"
)
GEO = [
    ("mesh_scaled", "mesh",
     [("vin", "vector", True), ("scale", "double", False),
      ("cin", "int", True), ("iin", "int", True)],
     _MESH_SRC,
     {"vin": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
      "scale": 2.0, "cin": [3], "iin": [0, 1, 2]}),
    ("curve_offset", "curve",
     [("cvsIn", "vector", True), ("offset", "double", False)],
     _CURVE_SRC,
     {"cvsIn": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0],
                [3.0, 0.0, 0.0]], "offset": 1.0}),
    ("surface_scaled", "surface",
     [("cvsIn", "vector", True), ("scale", "double", False),
      ("nu", "int", False), ("nv", "int", False)],
     _SURF_SRC,
     {"cvsIn": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                [1.0, 1.0, 0.0]], "scale": 1.5, "nu": 2, "nv": 2}),
    # --- typed-dataclass CONSTRUCTOR form (self.outX = Mesh/NurbsCurve/
    # NurbsSurface(...)): the ctor is rewritten to synthetic self.<field>
    # buffer writes, exercising the normals/colors/periodic/knots writers. ---
    ("mesh_ctor_pervertex", "mesh",
     [("scale", "double", False)], _MESH_CTOR_PV,
     {"scale": 1.0}),
    ("mesh_ctor_indexed", "mesh",
     [("scale", "double", False)], _MESH_CTOR_IDX,
     {"scale": 1.0}),
    ("mesh_ctor_selfidentity", "mesh",
     [("scale", "double", False)], _MESH_CTOR_SELF,
     {"scale": 1.0}),
    ("curve_ctor_periodic", "curve",
     [("scale", "double", False)], _CURVE_CTOR_PER,
     {"scale": 1.0}),
    ("curve_ctor_kv", "curve",
     [("scale", "double", False)], _CURVE_CTOR_KV,
     {"scale": 1.0}),
    ("surface_ctor_periodic", "surface",
     [("scale", "double", False)], _SURF_CTOR_PER,
     {"scale": 1.0}),
]

# geo rejects: try_lower_geo_compute must return None (fall back to AI porter)
GEO_REJ = [
    # required buffers (counts/indices) never filled.
    ("mesh_missing_buffers", "mesh", [("vin", "vector", True)],
     "self.points = self.vin"),
    # a self-write to an attr that is not a geo buffer.
    ("geo_unknown_attr", "mesh",
     [("vin", "vector", True), ("cin", "int", True), ("iin", "int", True)],
     "self.points = self.vin\nself.counts = self.cin\n"
     "self.indices = self.iin\nself.junk = self.vin"),
    # a deferred P1 op (np.nonzero) -- exactly what GoL needs; rejects cleanly
    # until SP-5 lands, so codegen keeps the AI porter (zero regression).
    ("geo_deferred_op", "mesh",
     [("vin", "vector", True), ("cin", "int", True), ("iin", "int", True)],
     "import numpy as np\nys = np.nonzero(self.vin)\n"
     "self.points = self.vin\nself.counts = self.cin\nself.indices = self.iin"),
]


# ---------------------------------------------------------------------------
# geo-generator + inline-helper fixture: the ACTUAL Game of Life mPyMesh compute
# calling the _gol_board INIT helper -- the flagship end-to-end acceptance (a real
# template lowered to pure C++, bit-faithful vs its numpy interpretation).
# ---------------------------------------------------------------------------
# Derived from templates/MPyMesh/Game Of Life, but deliberately NOT a copy:
# it wraps its inputs and its _GOL_INIT imports build_default_output, neither of
# which the template does. The template has since moved to the ctor form; this
# still writes self.points / self.counts / self.indices first, making it the
# harness's only coverage of the retired flat-buffer idiom the api2 bridges must
# keep supporting. Do NOT re-sync it.
_GOL_MESH_COMPUTE = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import Mesh\n"
    "\n"
    "bx = max(1, int(self.boardX))\n"
    "by = max(1, int(self.boardY))\n"
    "board = _gol_board(by, bx, self.randomSamples, self.frame, self.resetBoard)\n"
    "\n"
    "half = 0.5 * max(1e-6, float(self.cellSize))\n"
    "ys, xs = np.nonzero(board)\n"
    "m = int(xs.shape[0])\n"
    "\n"
    "if m == 0:\n"
    "    self.points = np.zeros((0, 3), dtype=np.float64)\n"
    "    self.counts = np.zeros(0, dtype=np.int32)\n"
    "    self.indices = np.zeros(0, dtype=np.int32)\n"
    "else:\n"
    "    centers = np.column_stack([\n"
    "        xs.astype(np.float64),\n"
    "        ys.astype(np.float64),\n"
    "        np.zeros(m, dtype=np.float64),\n"
    "    ])\n"
    "    corners = np.array([\n"
    "        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],\n"
    "        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],\n"
    "    ], dtype=np.float64) * half\n"
    "    self.points = (centers[:, None, :] + corners[None, :, :]).reshape(-1, 3)\n"
    "    faces = np.array([\n"
    "        [0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],\n"
    "        [3, 7, 6, 2], [0, 4, 7, 3], [1, 2, 6, 5],\n"
    "    ], dtype=np.int32)\n"
    "    base = (8 * np.arange(m, dtype=np.int32))[:, None, None]\n"
    "    self.indices = (base + faces[None, :, :]).reshape(-1)\n"
    "    self.counts = np.full(6 * m, 4, dtype=np.int32)\n"
    "\n"
    "self.outMesh = Mesh(points=self.points, counts=self.counts, "
    "indices=self.indices)"
)

# (name, kind, ins, init, source, values)
GEO_HELP = [
    ("gol_mesh", "mesh",
     [("boardX", "int", False), ("boardY", "int", False),
      ("randomSamples", "int", False), ("frame", "int", False),
      ("resetBoard", "enum", False), ("cellSize", "double", False)],
     _GOL_INIT, _GOL_MESH_COMPUTE,
     {"boardX": 8, "boardY": 8, "randomSamples": 20, "frame": 3,
      "resetBoard": 0, "cellSize": 0.9}),
]


# ---------------------------------------------------------------------------
# deformer fixtures (getPoints/setPoints in-place mutate of the `pts` array)
# ---------------------------------------------------------------------------
# The deform emitter harvests rest points into a `pts` MPointArray of length `n`,
# exposes `const float env` + the user inputs as `in_<member>`, then nd_lower
# materialises pts->(N,3), runs the transpiled math and scatters back into pts.
# This harness mimics that frame with a std::vector<MPoint> and probes the result.


def _gen_deform_cpp(ins, rest, env_val, values, body):
    L = [_SHIM, "int main() {"]
    items = ", ".join("MPoint(%s, %s, %s)"
                      % (_cpp_lit(p[0]), _cpp_lit(p[1]), _cpp_lit(p[2]))
                      for p in rest)
    L.append("    std::vector<MPoint> pts = {%s};" % items)
    L.append("    unsigned int n = (unsigned int)pts.size();")
    L.append("    float env = (float)(%s);" % _cpp_lit(env_val))
    L.append("    (void)env;")
    for d in ins:
        L.append(_decl_input(d, values[d["plug"]]))
    L.append("    // ===== lowered deform =====")
    L += body
    L.append("    // ===== probe (mutated points) =====")
    L.append('    { printf("PROBE points %zu :", pts.size()*3);'
             " for (size_t _i=0;_i<pts.size();++_i)"
             ' printf(" %.17g %.17g %.17g", pts[_i].x, pts[_i].y, pts[_i].z);'
             ' printf("\\n"); }')
    L.append("    return 0;")
    L.append("}")
    return "\n".join(L) + "\n"


def _mmat_init_list(mat):
    """``MMatrix{16 row-major doubles}`` literal for the _SHIM ctor."""
    return "MMatrix{%s}" % ", ".join(_cpp_lit(x) for row in mat for x in row)


def _gen_skin_deform_cpp(rest, env_val, joint_mats, bind_mats, w_dense, body):
    """Mirror emit_deformer's skin deform() frame WITHOUT a Maya datablock: seed
    pts / env and the dense C++ locals the lowered body reads (jointMat / bindPre
    std::vector<MMatrix>, skinW/skinN/skinJ), run the lowered body, probe pts."""
    L = [_SHIM, "int main() {"]
    items = ", ".join("MPoint(%s, %s, %s)"
                      % (_cpp_lit(p[0]), _cpp_lit(p[1]), _cpp_lit(p[2]))
                      for p in rest)
    L.append("    std::vector<MPoint> pts = {%s};" % items)
    L.append("    unsigned int n = (unsigned int)pts.size();")
    L.append("    float env = (float)(%s);" % _cpp_lit(env_val))
    L.append("    std::vector<MMatrix> jointMat = {%s};"
             % ", ".join(_mmat_init_list(m) for m in joint_mats))
    L.append("    std::vector<MMatrix> bindPre = {%s};"
             % ", ".join(_mmat_init_list(m) for m in bind_mats))
    wd = np.asarray(w_dense, dtype=np.float64)
    L.append("    std::vector<double> skinW = {%s};"
             % ", ".join(_cpp_lit(x) for x in wd.ravel()))
    L.append("    int64_t skinN = %d, skinJ = %d;" % (wd.shape[0], wd.shape[1]))
    L.append("    // ===== lowered skin deform =====")
    L += body
    L.append('    { printf("PROBE points %zu :", pts.size()*3);'
             " for (size_t _i=0;_i<pts.size();++_i)"
             ' printf(" %.17g %.17g %.17g", pts[_i].x, pts[_i].y, pts[_i].z);'
             ' printf("\\n"); }')
    L.append("    return 0;")
    L.append("}")
    return "\n".join(L) + "\n"


def _skin_deform_oracle(rest, env_val, joint_mats, bind_mats, w_dense, source):
    """Run the skin compute on numpy: self.weightList/matrix/bindPreMatrix are the
    dense arrays (np.asarray is identity on them), self.envelope the float, and
    self.outputGeometry[0] the getPoints/setPoints mesh proxy."""
    obj = _Self()
    proxy = _MeshProxy(rest)
    obj.outputGeometry = [proxy]
    # envelope is a FLOAT plug (read via asFloat in both the compiled deform() and
    # the interpreted node), so mimic float32 precision -- otherwise a non-exact
    # value like 0.4 diverges from the compiled `float env` at ~1e-8.
    obj.envelope = float(np.float32(env_val))
    obj.weightList = np.asarray(w_dense, dtype=np.float64)
    obj.matrix = np.asarray(joint_mats, dtype=np.float64).reshape(-1, 4, 4)
    obj.bindPreMatrix = np.asarray(bind_mats, dtype=np.float64).reshape(-1, 4, 4)
    exec(_strip_imports("import numpy as np\n" + source), {"np": np, "self": obj})
    rest_arr = np.asarray(rest, dtype=np.float64).reshape(-1, 3)
    result = rest_arr.copy()
    if proxy._out is not None:
        lim = min(proxy._out.shape[0], rest_arr.shape[0])
        result[:lim] = proxy._out[:lim]
    return result.ravel()


class _MeshProxy:
    """numpy stand-in for self.outputGeometry[i]'s getPoints/setPoints proxy."""

    def __init__(self, rest):
        self._pts = np.asarray(rest, dtype=np.float64).reshape(-1, 3)
        self._out = None

    def getPoints(self):
        return self._pts.copy()

    def setPoints(self, arr):
        self._out = np.asarray(arr, dtype=np.float64).reshape(-1, 3)

    # NURBS geometry-filter idiom -- exact aliases (a NURBS filter reads/writes
    # CVs via cvPositions/setCVPositions; they lower to the same body as
    # getPoints/setPoints, so the oracle treats them identically).
    def cvPositions(self):
        return self._pts.copy()

    def setCVPositions(self, arr):
        self._out = np.asarray(arr, dtype=np.float64).reshape(-1, 3)


def _deform_oracle(ins, rest, env_val, values, source):
    obj = _Self()
    proxy = _MeshProxy(rest)
    obj.outputGeometry = [proxy]
    obj.envelope = float(env_val)
    for d in ins:
        t = d["meta"]["type"]
        v = values[d["plug"]]
        if d["meta"]["is_array"]:
            if t in _VEC:
                arr = np.asarray(v, dtype=np.float64).reshape(-1, 3)
            elif t == "matrix":
                arr = np.asarray(v, dtype=np.float64).reshape(-1, 4, 4)
            else:
                arr = np.asarray(v, dtype=_NP_DTYPE[t])
            setattr(obj, d["plug"], arr)
        elif t == "matrix":
            setattr(obj, d["plug"], np.asarray(v, dtype=np.float64).reshape(4, 4))
        elif t in _VEC:
            setattr(obj, d["plug"], np.asarray(v, dtype=np.float64))
        elif t == "bool":
            setattr(obj, d["plug"], bool(v))
        elif t in ("int", "enum"):
            setattr(obj, d["plug"], int(v))
        else:
            setattr(obj, d["plug"], float(v))
    exec(_strip_imports(source), {"np": np, "self": obj})
    # scatter min(M, n): the C++ writeback commits only the first n rows.
    rest_arr = np.asarray(rest, dtype=np.float64).reshape(-1, 3)
    n = rest_arr.shape[0]
    result = rest_arr.copy()
    out = proxy._out
    if out is not None:
        lim = min(out.shape[0], n)
        result[:lim] = out[:lim]
    return result.ravel()


# (name, rest, env, ins, source, values)  ins as (plug, type, is_array)
_DEF_TRANSLATE = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "env = float(self.envelope)\n"
    "deformed = rest + env * self.amount\n"
    "mesh.setPoints(deformed)"
)
_DEF_SCALE_INLINE = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "env = float(self.envelope)\n"
    "mesh.setPoints(rest * (1.0 + env))"
)
_DEF_NO_ENV = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "mesh.setPoints(rest * 2.0)"
)
_DEF_PER_VERTEX = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "env = float(self.envelope)\n"
    "mesh.setPoints(rest + env * self.offsets)"
)
# NURBS geometry-filter body: reads/writes CVs via cvPositions/setCVPositions
# (the curve/surface idiom). Must lower to the SAME body as getPoints/setPoints.
_DEF_NURBS_CV = (
    "import numpy as np\n"
    "geo = self.outputGeometry[0]\n"
    "rest = geo.cvPositions()\n"
    "env = float(self.envelope)\n"
    "out = rest.copy()\n"
    "out[:, 1] = out[:, 1] + env * self.amplitude * np.sin(rest[:, 0])\n"
    "geo.setCVPositions(out)"
)
_REST3 = [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [-4.0, 5.0, -6.0]]
# sphereWave-style body: mean(axis=0) + linalg.norm(axis=1, keepdims=True) +
# array-compare + np.where + np.sin. keepdims keeps norm's (N,1) shape so every
# downstream broadcast matches numpy. Rest is chosen so d>1.0 is TRUE for some
# rows and FALSE for others -> both np.where branches are exercised.
_DEF_SPHEREWAVE = (
    "import numpy as np\n"
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "env = float(self.envelope)\n"
    "centroid = rest.mean(axis=0)\n"
    "d = np.linalg.norm(rest - centroid, axis=1, keepdims=True)\n"
    "wave = np.where(d > 1.0, np.sin(d), 0.0)\n"
    "mesh.setPoints(rest + env * wave)"
)
_SW_REST = [[0.0, 0.0, 0.0], [0.2, 0.0, 0.0], [0.0, 0.2, 0.0],
            [3.0, 0.0, 0.0]]
DEF = [
    ("deform_translate", _REST3, 0.5,
     [("amount", "double", False)], _DEF_TRANSLATE,
     {"amount": 3.0}),
    ("deform_scale_inline", _REST3, 0.25,
     [], _DEF_SCALE_INLINE, {}),
    ("deform_no_env", _REST3, 1.0,
     [], _DEF_NO_ENV, {}),
    ("deform_per_vertex", _REST3, 0.5,
     [("offsets", "vector", True)], _DEF_PER_VERTEX,
     {"offsets": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}),
    ("deform_sphereWave", _SW_REST, 0.5,
     [], _DEF_SPHEREWAVE, {}),
    ("deform_nurbs_cv", _REST3, 0.5,
     [("amplitude", "double", False)], _DEF_NURBS_CV,
     {"amplitude": 2.0}),
]

# deformer rejects: try_lower_deform must return None (fall back to AI porter)
DEF_REJ = [
    # no setPoints -> idiom absent -> reject.
    ("deform_no_setpoints", "MPxDeformerNode", 1.0,
     [], "mesh = self.outputGeometry[0]\nrest = mesh.getPoints()", {}),
]


# ---------------------------------------------------------------------------
# skinCluster (MPxSkinCluster) fixtures -- compiled linear-blend skinning.
# ---------------------------------------------------------------------------
# The skin lowered body reads the dense C++ locals emit_deformer emits:
#   std::vector<MMatrix> jointMat / bindPre  (logical-indexed, identity gap-fill)
#   std::vector<double> skinW; int64_t skinN, skinJ;  (dense (N,J), 0 gap-fill)
# so this harness seeds those directly (no Maya datablock) and probes the mutated
# points; the oracle runs the SAME source on numpy.
#
# _SKIN_SRC / _SKIN_DQS_SRC are the INLINE skinning math -- the transpiler-
# primitive fixtures and the oracle for the METHOD sweep below. The SHIPPED
# defaults are the one-liner METHOD form (SSOT skin_blend.py); the assert catches
# an accidental revert, and the sweep proves the default lowers to the SAME C++.
from mpynode._defaults import skin_cluster_defaults as _scd
from mpynode._defaults import skin_cluster_dqs_defaults as _dqs

assert "linear_blend" in _scd.DEFAULT_COMPUTE_SOURCE, \
    "LBS default should call the blessed self.linear_blend method"
assert "dual_quaternion" in _dqs.DEFAULT_COMPUTE_SOURCE, \
    "DQS default should call the blessed self.dual_quaternion method"

_SKIN_SRC = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "N = rest.shape[0]\n"
    "W = np.asarray(self.weightList)\n"
    "joint = np.asarray(self.matrix)\n"
    "bind = np.asarray(self.bindPreMatrix)\n"
    "M = bind @ joint\n"
    "pts_h = np.concatenate([rest, np.ones((N, 1))], axis=1)\n"
    "deformed = np.einsum(\"vj,jkc,vk->vc\", W, M, pts_h)[:, :3]\n"
    "mesh.setPoints(rest + float(self.envelope) * (deformed - rest))\n"
)
_SKIN_DQS_SRC = r'''mesh = self.outputGeometry[0]
rest = mesh.getPoints()
N = rest.shape[0]
W = np.asarray(self.weightList)
joint = np.asarray(self.matrix)
bind = np.asarray(self.bindPreMatrix)
M = bind @ joint
R = np.transpose(M[:, :3, :3], (0, 2, 1))
t = M[:, 3, :3]
r00 = R[:, 0, 0]; r01 = R[:, 0, 1]; r02 = R[:, 0, 2]
r10 = R[:, 1, 0]; r11 = R[:, 1, 1]; r12 = R[:, 1, 2]
r20 = R[:, 2, 0]; r21 = R[:, 2, 1]; r22 = R[:, 2, 2]
tr = r00 + r11 + r22
S0 = np.sqrt(np.maximum(tr + 1.0, 1e-12)) * 2.0
qw0 = 0.25 * S0; qx0 = (r21 - r12) / S0; qy0 = (r02 - r20) / S0; qz0 = (r10 - r01) / S0
S1 = np.sqrt(np.maximum(1.0 + r00 - r11 - r22, 1e-12)) * 2.0
qw1 = (r21 - r12) / S1; qx1 = 0.25 * S1; qy1 = (r01 + r10) / S1; qz1 = (r02 + r20) / S1
S2 = np.sqrt(np.maximum(1.0 + r11 - r00 - r22, 1e-12)) * 2.0
qw2 = (r02 - r20) / S2; qx2 = (r01 + r10) / S2; qy2 = 0.25 * S2; qz2 = (r12 + r21) / S2
S3 = np.sqrt(np.maximum(1.0 + r22 - r00 - r11, 1e-12)) * 2.0
qw3 = (r10 - r01) / S3; qx3 = (r02 + r20) / S3; qy3 = (r12 + r21) / S3; qz3 = 0.25 * S3
m0 = tr > 0.0
m1 = (~m0) & (r00 >= r11) & (r00 >= r22)
m2 = (~m0) & (~m1) & (r11 >= r22)
qw = np.where(m0, qw0, np.where(m1, qw1, np.where(m2, qw2, qw3)))
qx = np.where(m0, qx0, np.where(m1, qx1, np.where(m2, qx2, qx3)))
qy = np.where(m0, qy0, np.where(m1, qy1, np.where(m2, qy2, qy3)))
qz = np.where(m0, qz0, np.where(m1, qz1, np.where(m2, qz2, qz3)))
qr = np.stack([qw, qx, qy, qz], axis=1)
tx = t[:, 0]; ty = t[:, 1]; tz = t[:, 2]
dw = -(tx * qx + ty * qy + tz * qz)
dx = tx * qw + ty * qz - tz * qy
dy = -tx * qz + ty * qw + tz * qx
dz = tx * qy - ty * qx + tz * qw
qd = 0.5 * np.stack([dw, dx, dy, dz], axis=1)
dot0 = np.sum(qr * qr[0], axis=1)
sgn = np.sign(dot0)
sgn = np.where(sgn == 0.0, 1.0, sgn)
qr = qr * sgn[:, None]
qd = qd * sgn[:, None]
br = np.einsum("vj,jk->vk", W, qr)
bd = np.einsum("vj,jk->vk", W, qd)
mag = np.sqrt(np.sum(br * br, axis=1))
br = br / mag[:, None]
bd = bd / mag[:, None]
bw = br[:, 0]; bx = br[:, 1]; by = br[:, 2]; bz = br[:, 3]
R00 = 1.0 - 2.0 * (by * by + bz * bz); R01 = 2.0 * (bx * by - bw * bz); R02 = 2.0 * (bx * bz + bw * by)
R10 = 2.0 * (bx * by + bw * bz); R11 = 1.0 - 2.0 * (bx * bx + bz * bz); R12 = 2.0 * (by * bz - bw * bx)
R20 = 2.0 * (bx * bz - bw * by); R21 = 2.0 * (by * bz + bw * bx); R22 = 1.0 - 2.0 * (bx * bx + by * by)
Rn = np.reshape(np.stack([R00, R01, R02, R10, R11, R12, R20, R21, R22], axis=1), (N, 3, 3))
cw = bw; cx = -bx; cy = -by; cz = -bz
dwb = bd[:, 0]; dxb = bd[:, 1]; dyb = bd[:, 2]; dzb = bd[:, 3]
px = dwb * cx + dxb * cw + dyb * cz - dzb * cy
py = dwb * cy - dxb * cz + dyb * cw + dzb * cx
pz = dwb * cz + dxb * cy - dyb * cx + dzb * cw
tn = 2.0 * np.stack([px, py, pz], axis=1)
deformed = np.einsum("vij,vj->vi", Rn, rest) + tn
mesh.setPoints(rest + float(self.envelope) * (deformed - rest))
'''

# METHOD-form computes: the SAME deform via the blessed API methods, lowered via
# the Transpile marker -> the followed skin_blend free fn as a C++ helper. Must be
# numerically identical to the inline default (which the oracle runs).
_SKIN_METHOD_LBS = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "mesh.setPoints(rest + float(self.envelope) * (self.linear_blend("
    "rest, self.weightList, self.matrix, self.bindPreMatrix) - rest))\n"
)
_SKIN_METHOD_DQS = _SKIN_METHOD_LBS.replace(
    "linear_blend", "dual_quaternion")
_SKIN_METHOD_SPEC = {"mpy_type": "mPySkinCluster", "init": "import numpy as np\n"}

# row-major 4x4 (Maya row-vector: translation in row 3).
def _T(tx, ty, tz):
    return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [tx, ty, tz, 1]]

def _S(sx, sy, sz):
    return [[sx, 0, 0, 0], [0, sy, 0, 0], [0, 0, sz, 0], [0, 0, 0, 1]]

def _matmul4(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]

# (name, rest, env, joint_mats (J,4,4), bind_mats (J,4,4), W_dense (N,J))
SKIN = [
    # 2 influences, 4 verts, non-identity bind (real batched matmul), graded W.
    ("skin_2inf", [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 0.0, 1.0],
                   [0.0, 2.0, 0.0]], 1.0,
     [_matmul4(_S(1.5, 1.0, 1.0), _T(2.0, 0.0, 0.0)),
      _matmul4(_S(1.0, 2.0, 1.0), _T(0.0, 3.0, 0.0))],
     [_T(-1.0, 0.0, 0.0), _T(0.0, -1.0, 0.0)],
     [[1.0, 0.0], [0.7, 0.3], [0.3, 0.7], [0.0, 1.0]]),
    # envelope < 1 (partial blend), 3 verts, 3 influences.
    ("skin_3inf_env", [[0.5, 0.5, 0.5], [-1.0, 2.0, 0.0], [3.0, 0.0, -2.0]], 0.4,
     [_T(1.0, 0.0, 0.0), _matmul4(_S(2.0, 2.0, 2.0), _T(0.0, 1.0, 0.0)),
      _T(0.0, 0.0, 4.0)],
     [_T(0.0, 0.0, 0.0), _T(-1.0, 0.0, 0.0), _T(0.0, 0.0, -2.0)],
     [[0.5, 0.5, 0.0], [0.2, 0.3, 0.5], [0.0, 0.1, 0.9]]),
]


# ---- dual-quaternion skinning fixtures (RIGID joint matrices only) ----------
# DQS extracts a rotation quaternion per influence, so its fixtures must use
# rigid (rotation + translation) transforms -- a scaled matrix has no unit
# quaternion. Row-vector Maya rotation matrices (v' = v @ R).
import math as _math


def _Rz(deg):
    a = _math.radians(deg); c = _math.cos(a); s = _math.sin(a)
    return [[c, s, 0, 0], [-s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def _Rx(deg):
    a = _math.radians(deg); c = _math.cos(a); s = _math.sin(a)
    return [[1, 0, 0, 0], [0, c, s, 0], [0, -s, c, 0], [0, 0, 0, 1]]


# (name, rest, env, joint_mats (J,4,4 rigid), bind_mats (J,4,4 rigid), W (N,J))
SKIN_DQS = [
    # 2 rigid influences, 4 verts, non-identity rigid bind (real batched matmul).
    ("dqs_2inf", [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 0.0, 1.0],
                  [0.0, 2.0, 0.0]], 1.0,
     [_matmul4(_Rz(35.0), _T(2.0, 0.0, 0.0)),
      _matmul4(_Rx(-40.0), _T(0.0, 3.0, 0.0))],
     [_T(-1.0, 0.0, 0.0), _T(0.0, -1.0, 0.0)],
     [[1.0, 0.0], [0.7, 0.3], [0.3, 0.7], [0.0, 1.0]]),
    # envelope < 1 (partial blend), 3 verts, 3 rigid influences.
    ("dqs_3inf_env", [[0.5, 0.5, 0.5], [-1.0, 2.0, 0.0], [3.0, 0.0, -2.0]], 0.4,
     [_Rz(20.0), _matmul4(_Rx(50.0), _T(0.0, 1.0, 0.0)),
      _matmul4(_Rz(-25.0), _T(0.0, 0.0, 4.0))],
     [_T(0.0, 0.0, 0.0), _T(-1.0, 0.0, 0.0), _T(0.0, 0.0, -2.0)],
     [[0.5, 0.5, 0.0], [0.2, 0.3, 0.5], [0.0, 0.1, 0.9]]),
]


# ---------------------------------------------------------------------------
# transform fixtures (MPxTransformationMatrix::desiredLocal() body -- GATED
# LOCAL-MATRIX contract)
# ---------------------------------------------------------------------------
# lower_transform emits ONLY the sink-writing body: it scatters a produced (4,4)
# nd value into the C++ ``local_matrix`` MMatrix (+ its ``local_set`` flag) and
# sets the ``apply_*`` bools; the LOCAL>no-op dispatch lives in emit_transform.
# So the harness declares those four sinks + any declared scalar-matrix INPUT as
# an ``in_a<Cap>`` MMatrix local, runs the body, then probes local_matrix and the
# flags against a numpy oracle. WORLD placement is opt-in via a connected parent
# matrix input; the node never reads its own DAG parent, so there is no
# world_matrix sink and no parent_matrix local.

# MMatrix is provided by _SHIM (real-Maya layout: public matrix[4][4] member +
# operator()); the transform frame only adds MEulerRotation on top of it.
_TRANS_SHIM = r"""
struct MEulerRotation { double x, y, z;
    MEulerRotation(double a, double b, double c) : x(a), y(b), z(c) {} };
"""


def _mat_lit(mat):
    """C++ statements seeding MMatrix `m` to the 4x4 `mat` (row-major)."""
    L = ["    MMatrix m;"]
    for r in range(4):
        for c in range(4):
            L.append("    m.matrix[%d][%d] = %s;" % (r, c, _cpp_lit(mat[r][c])))
    return L


def _xf_in_local(plug):
    """`in_a<Cap>` MMatrix local name a matrix INPUT is bound to (mirrors
    nd_lower._transform_in_local / emit_transform)."""
    ident = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in plug)
    return "in_a" + ident[:1].upper() + ident[1:]


def _gen_transform_cpp(inputs, body):
    """inputs: {plug: 4x4 seed} for each declared scalar matrix INPUT. Sets up the
    gated-local-matrix frame emit_transform provides, runs the lowered body, and
    probes local_matrix (16) + the four flags."""
    L = [_SHIM, _TRANS_SHIM, "int main() {"]
    L += _mat_lit(_ID4)  # the base TRS `m` the scaffold declares
    L.append("    MVector t(%r,%r,%r); MEulerRotation r(%r,%r,%r); "
             "MVector sc(%r,%r,%r);" % (_XF_T + _XF_R + _XF_SC))
    L.append("    MVector shr(%r,%r,%r); int ro = %d;"
             % (_XF_SHR + (_XF_RO,)))
    L.append("    (void)m; (void)t; (void)r; (void)sc; (void)shr; (void)ro;")
    for plug, mat in inputs.items():
        L.append(_mmat_lit_named(_xf_in_local(plug), mat))
    # The four gated sinks (emit_transform defaults => a plain transform). No
    # world_matrix sink and no parent_matrix local: WORLD placement is opt-in via
    # a connected parent matrix input, read like any other in_a<Cap>.
    L.append("    MMatrix local_matrix;")
    L.append("    bool local_set = false;")
    L.append("    bool apply_rotate = true, apply_translate = true, "
             "apply_scale = true;")
    L.append("    // ===== lowered transform =====")
    L += body
    L.append("    // ===== probes (local_matrix, row-major, + the flags) =====")
    L.append('    { printf("PROBE local_matrix 16 :");'
             " for (int _r=0;_r<4;++_r) for (int _c=0;_c<4;++_c)"
             ' printf(" %.17g", local_matrix.matrix[_r][_c]); printf("\\n"); }')
    L.append('    printf("PROBE flags 4 : %d %d %d %d\\n",'
             " (int)local_set, (int)apply_rotate,"
             " (int)apply_translate, (int)apply_scale);")
    L.append("    return 0;")
    L.append("}")
    return "\n".join(L) + "\n"


def _transform_oracle(inputs, source):
    """Reproduce the gated-local-matrix compute on numpy. Matrix INPUTS are seeded
    as MatrixViews; the four sinks default to emit_transform's no-op state.
    Returns {local_set, apply_*} + the raveled local_matrix (None if unset)."""
    obj = _Self()
    for plug, mat in inputs.items():
        setattr(obj, plug, _MatrixView(mat))
    # This node's own live channels -- seeded to the SAME values the C++ scaffold
    # declares t / r / sc / shr / ro with (rotate is RADIANS, rotate_order 0-based).
    obj.translate = np.array(_XF_T, np.float64)
    obj.rotate = np.array(_XF_R, np.float64)
    obj.scale = np.array(_XF_SC, np.float64)
    obj.shear = np.array(_XF_SHR, np.float64)
    obj.rotate_order = _XF_RO
    obj.local_matrix = None
    # Gates default TRUE (mirrors emit_transform's desiredLocal scaffold).
    obj.apply_rotate = True
    obj.apply_translate = True
    obj.apply_scale = True
    exec(_strip_imports("import numpy as np\n" + source), {"np": np, "self": obj})
    return {
        "local_set": obj.local_matrix is not None,
        "local_matrix": (np.asarray(obj.local_matrix, np.float64).ravel()
                         if obj.local_matrix is not None else None),
        "apply_rotate": bool(obj.apply_rotate),
        "apply_translate": bool(obj.apply_translate),
        "apply_scale": bool(obj.apply_scale),
    }


_ID4 = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
_M0 = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
       [0.0, 0.0, 1.0, 0.0], [1.0, 2.0, 3.0, 1.0]]
# An invertible parent-world seed (scale + translate) for the world->local case.
_PW = [[2.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
       [0.0, 0.0, 1.0, 0.0], [5.0, -1.0, 4.0, 1.0]]
# Known channel values the transform scaffold seeds t / r / sc / shr / ro with,
# so a positive read test can assert self.translate / rotate / scale / shear /
# rotate_order parity (the oracle seeds the SAME values). rotate is RADIANS; ro
# is the 0-based enum int (matching the .rotateOrder plug).
_XF_T = (1.0, 2.0, 3.0)
_XF_R = (0.1, 0.2, 0.3)
_XF_SC = (2.0, 3.0, 4.0)
_XF_SHR = (0.5, 0.0, 0.0)
_XF_RO = 2

# (name, inputs{plug:4x4}, source)
TRANS = [
    # constant LOCAL translate offset, translate gate only (no inputs).
    ("xf_local_const", {},
     "m = np.eye(4)\nm[3, 1] = 2.0\n"
     "self.local_matrix = m\nself.apply_translate = True"),
    # reads ALL five own channels (translate / rotate [radians] / scale / shear /
    # rotate_order) and drives the local translate row from them.
    ("xf_reads_channels", {},
     "m = np.eye(4)\n"
     "m[3, 0] = float(self.translate[0]) + float(self.rotate[2]) + "
     "float(self.scale[1]) + float(self.shear[0]) + float(self.rotate_order)\n"
     "self.local_matrix = m\nself.apply_translate = True"),
    # WORLD placement via a CONNECTED parent input: local = world @ inv(parent),
    # rotate+translate gated. Exercises np.linalg.inv (-> nd::inv) lowering.
    ("xf_world_via_parent", {"matrix0": _M0, "parentWorld": _PW},
     "m = self.matrix0.asNumpy()\n"
     "P = self.parentWorld.asNumpy()\n"
     "self.local_matrix = m @ np.linalg.inv(P)\n"
     "self.apply_rotate = True\nself.apply_translate = True"),
    # LOCAL matrix from a matrix input, scale gate only.
    ("xf_local_from_input_scale", {"matrix0": _M0},
     "m = self.matrix0.asNumpy().copy()\nm[0, 0] = 2.0\n"
     "self.local_matrix = m\nself.apply_scale = True"),
    # trig-built LOCAL rotation (np.sin/np.cos path), rotate gate.
    ("xf_rotate_trig", {},
     "a = 0.7\nm = np.eye(4)\nca = np.cos(a)\nsa = np.sin(a)\n"
     "m[0, 0] = ca\nm[0, 1] = sa\nm[1, 0] = -sa\nm[1, 1] = ca\n"
     "self.local_matrix = m\nself.apply_rotate = True"),
]

# transform rejects: try_lower_transform must return None (fall back to AI porter)
TRANS_REJ = [
    # reads self.parent_matrix -- a removed legacy read slot (the node no longer
    # reads its DAG parent; a parent world arrives via a connected matrix input).
    ("xf_reads_parent_matrix",
     "self.local_matrix = self.parent_matrix\n"
     "self.apply_translate = True"),
    # writes self.world_matrix -- the AXED write slot. It is no longer an allowed
    # sink, and local_matrix is never written, so this must reject.
    ("xf_writes_world_matrix",
     "self.world_matrix = np.eye(4)\nself.apply_translate = True"),
    # writes self.output_matrix -- the removed legacy write slot.
    ("xf_writes_output_matrix", "self.output_matrix = np.eye(4)"),
    # opens a gate but never sets a matrix sink -> nothing to drive.
    ("xf_no_matrix_sink", "self.apply_rotate = True"),
]


def _check_recursion_rank_normalization(fails):
    """A recursive helper reached with a scalar arg whose CppType carries an
    incidental rank (rank 0 from an env binding) must monomorphise to the SAME
    lambda as its self-call arg (rank None from arithmetic). Built directly on
    transpile_compute_block with a rank-0 scalar env (nd_lower itself uses rank
    None, so only a direct caller exercises this) -- guards the sig-rank
    normalisation in py_to_cpp._call_helper."""
    from mpynode.native.compiler import py_to_cpp as p2c
    env = {"self.n": p2c.CppType("scalar", "int64", 0)}     # <-- rank 0, on purpose
    init = ("def _fac(n):\n"
            "    if n <= 1:\n        return 1\n"
            "    return n * _fac(n - 1)\n")
    try:
        _res, _w, helper_lines = p2c.transpile_compute_block(
            "self.r = _fac(self.n)\n", env,
            {"self.r": lambda v: ["out = %s;" % v.code]}, helper_source=init)
    except Exception as e:
        fails.append("RECURSION rank-norm: rank-0 scalar env misread as "
                     "polymorphic recursion: %r" % e)
        return
    text = "\n".join(helper_lines)
    if text.count("std::function<") != 1:
        fails.append("RECURSION rank-norm: expected exactly one std::function, "
                     "got %d" % text.count("std::function<"))
    if "std::function<int64_t(" not in text:
        fails.append("RECURSION rank-norm: factorial must stay int64_t")


def _check_linalg_p2_block_path(fails):
    """SP-6: the diag / det / einsum / svd op surface must be reachable through
    the compute-BLOCK path (self.<attr> env + output_writers + prefixed locals)
    that the geo/deform families use -- not only the single-function
    transpile_function harness that py_to_cpp_test exercises. py_to_cpp_test
    already proves the C++ kernels are numerically faithful; this proves the
    block path lowers (does not reject) a realistic Procrustes/Kabsch chain and
    a batched einsum, wiring nd::svd / nd::det / nd::diag / nd::einsum."""
    from mpynode.native.compiler import py_to_cpp as p2c
    env = {"self.P": p2c.CppType("array", "double", 2),     # (L,3) point cloud
           "self.Q": p2c.CppType("array", "double", 2)}
    src = ("P = self.P\n"
           "Q = self.Q\n"
           "H = P.T @ Q\n"
           "U, S, Vt = np.linalg.svd(H)\n"
           "d = float(np.sign(np.linalg.det(Vt.T @ U.T)))\n"
           "sel = np.array([0.0, 0.0, 1.0])\n"
           "vec = np.array([1.0, 1.0, 1.0]) + (d - 1.0) * sel\n"
           "D = np.diag(vec)\n"
           "self.R = Vt.T @ D @ U.T\n")
    try:
        res, _w, _h = p2c.transpile_compute_block(
            src, env, {"self.R": lambda v: ["out = %s;" % v.code]})
    except Exception as e:
        fails.append("LINALG P2 block-path: Procrustes chain rejected: %r" % e)
    else:
        text = "\n".join(res.decl_lines + res.body_lines)
        for need in ("nd::svd(", "nd::det(", "nd::diag(", "nd::SVD3"):
            if need not in text:
                fails.append("LINALG P2 block-path: missing %s in lowered C++"
                             % need)
    env2 = {"self.Pb": p2c.CppType("array", "double", 3),   # (n,L,3)
            "self.Qb": p2c.CppType("array", "double", 3)}
    try:
        res2, _w2, _h2 = p2c.transpile_compute_block(
            "self.Hb = np.einsum('nli,nlj->nij', self.Pb, self.Qb)\n",
            env2, {"self.Hb": lambda v: ["out = %s;" % v.code]})
    except Exception as e:
        fails.append("LINALG P2 block-path: batched einsum rejected: %r" % e)
    else:
        # A fixed compile-time subscript lowers to a specialized scalar
        # contraction loop (nd::atN reads); a diagonal / scalar-output subscript
        # falls back to nd::einsum. Either way the batched einsum must LOWER --
        # 'nli,nlj->nij' specializes, so its rank-3 reads appear as nd::at3.
        lowered = "\n".join(res2.decl_lines + res2.body_lines)
        if "nd::at3(" not in lowered and "nd::einsum(" not in lowered:
            fails.append("LINALG P2 block-path: batched einsum did not lower "
                         "(no specialized loop and no nd::einsum fallback)")


def _check_external_helper_units(fails):
    """Stage 1 (#38): import-following wired into the DETERMINISTIC path. When a
    node's compute calls a pure-Python helper it imported from another module,
    spec_extractor / mpn_spec_adapter attach the followed helper SOURCE as
    ``spec['external_helper_units']`` (list of {module,name,source}). nd_lower's
    ``_combined_helper_source`` must feed those sources to the transpiler so a
    bare-name call (``from mod import fn`` -> ``fn(...)``) lowers -- exactly the
    mechanism the metaballs template needs to reach ``mesh_from_shapes``.

    Proven at the STRING level (no clang): (a) WITHOUT the unit the bare call is
    unknown -> reject (None); (b) WITH the unit it lowers, emitting the helper
    lambda; (c) both the generic and geo entry points thread it; (d) a node-local
    INIT ``def`` shadows an identically named followed unit (INIT parsed last)."""
    eval_sphere = ("def eval_sphere(X, Y, Z, radius=1.0):\n"
                   "    return np.sqrt(X**2 + Y**2 + Z**2) - radius\n")
    ins = [_descr("x", "double", True, "input"),
           _descr("y", "double", True, "input"),
           _descr("z", "double", True, "input")]
    outs = [_descr("out", "double", True, "output")]
    compute = "self.out = eval_sphere(self.x, self.y, self.z, 2.0)\n"
    unit = {"module": "m.sdf", "name": "eval_sphere", "source": eval_sphere}

    if nd_lower.try_lower_compute(ins, outs, {"compute": compute}) is not None:
        fails.append("HELPER UNITS: bare call lowered WITHOUT a helper source "
                     "(should reject)")
    got = nd_lower.try_lower_compute(
        ins, outs, {"compute": compute, "external_helper_units": [unit]})
    if got is None:
        fails.append("HELPER UNITS: external_helper_units not fed to the "
                     "transpiler (generic path)")
    else:
        text = "\n".join(got)
        if "nd::sqrt" not in text:
            fails.append("HELPER UNITS: followed helper body not lowered")

    # geo entry point threads it too.
    geo_helper = ("def unit_quad():\n"
                  "    return np.array([[0.0,0.0,0.0],[1.0,0.0,0.0],"
                  "[1.0,1.0,0.0],[0.0,1.0,0.0]])\n")
    geo_src = ("self.points = unit_quad()\n"
               "self.counts = np.array([4], dtype=np.int64)\n"
               "self.indices = np.array([0,1,2,3], dtype=np.int64)\n")
    geo_unit = {"module": "m", "name": "unit_quad", "source": geo_helper}
    if nd_lower.try_lower_geo_compute([], "mesh", {"compute": geo_src}) is not None:
        fails.append("HELPER UNITS: geo bare call lowered WITHOUT a helper "
                     "source (should reject)")
    if nd_lower.try_lower_geo_compute(
            [], "mesh",
            {"compute": geo_src, "external_helper_units": [geo_unit]}) is None:
        fails.append("HELPER UNITS: external_helper_units not fed to the "
                     "transpiler (geo path)")

    # node-local INIT def shadows an identically named followed unit (INIT last).
    shadow_unit = {"module": "m", "name": "eval_sphere",
                   "source": ("def eval_sphere(X, Y, Z, radius=1.0):\n"
                              "    return X * 0.0 + 999.0\n")}  # wrong body
    shadowed = nd_lower.try_lower_compute(
        ins, outs,
        {"compute": compute, "init": eval_sphere,
         "external_helper_units": [shadow_unit]})
    if shadowed is None or "999.0" in "\n".join(shadowed):
        fails.append("HELPER UNITS: node-local INIT def did not shadow the "
                     "followed unit of the same name")


# Shim for the output-sized-buffer contract: an index-written array output is
# materialised as an nd:: buffer sized to `data.outputArrayValue(<member>)
# .elementCount()` -- the compiled analogue of the connected-output-index span
# the interpreted node pre-seeds (output_defaults.seed_user_output_defaults_api2).
# clang needs a `data` object exposing that call; this stub returns a fixed count.
_OUTBUF_DATA_SHIM = r"""
struct _NDArrStub { long long _n; long long elementCount() const { return _n; } };
struct _NDDataStub { long long _n;
    _NDArrStub outputArrayValue(int) const { return _NDArrStub{_n}; } };
"""


def _check_output_buffer_contract(fails):
    """Output-sized-buffer contract (T3, spline): an ARRAY output written BY
    INDEX (``self.<out>[i] = ...`` inside a loop bounded by ``len(self.<out>)``)
    is bound as a PRE-SIZED nd:: buffer sized to the output multi's connected
    element count, then flushed after the body -- the deterministic analogue of
    the AI-ported spline. This proves (a) the subscript path emits the buffer
    materialisation and lowers + runs bit-faithfully for BOTH numeric and vector
    arrays; (b) the gate is strict -- a WHOLE-array writer (sine_ripple /
    metaballs) emits NO buffer materialisation, so that path is untouched; and
    (c) it fails closed -- an indexed write to a scalar output, or an output
    written both whole and by index, rejects (-> AI porter, zero regression)."""
    # ---- (b) NON-REGRESSION: a whole-array writer must NOT materialise a buffer.
    whole = nd_lower.lower_compute(
        [_descr("xs", "double", True, "input")],
        [_descr("ys", "double", True, "output")],
        "self.ys = self.xs * 2.0")
    wtext = "\n".join(whole)
    if "outputArrayValue" in wtext or "_ndoutn_" in wtext:
        fails.append("OUTBUF: whole-array writer materialised an output buffer "
                     "(gate not strict -- would regress sine_ripple/metaballs)")

    # ---- (a) STRING GATE: subscript writers materialise the sized buffer.
    num = nd_lower.lower_compute(
        [_descr("xs", "double", True, "input")],
        [_descr("out", "double", True, "output")],
        "n = len(self.out)\nfor i in range(n):\n    self.out[i] = self.xs[i]\n")
    ntext = "\n".join(num)
    if ("outputArrayValue(aOut)" not in ntext
            or "nd::zeros<double>({_ndoutn_aOut})" not in ntext):
        fails.append("OUTBUF: numeric subscript output missing sized-buffer "
                     "materialisation")
    vec = nd_lower.lower_compute(
        [_descr("vin", "vector", True, "input")],
        [_descr("pts", "vector", True, "output")],
        "n = len(self.pts)\nfor i in range(n):\n    self.pts[i] = self.vin[i]\n")
    vtext = "\n".join(vec)
    if ("outputArrayValue(aPts)" not in vtext
            or "nd::zeros<double>({_ndoutn_aPts, 3})" not in vtext):
        fails.append("OUTBUF: vector subscript output missing sized-buffer "
                     "materialisation")

    # ---- (c) FAIL-CLOSED rejects.
    if nd_lower.try_lower_compute(
            [_descr("a", "double", False, "input")],
            [_descr("o", "double", False, "output")],
            {"compute": "self.o[0] = self.a\n"}) is not None:
        fails.append("OUTBUF: indexed write to a scalar output did not reject")
    if nd_lower.try_lower_compute(
            [_descr("xs", "double", True, "input")],
            [_descr("out", "double", True, "output")],
            {"compute": "self.out = self.xs\n"
                        "n = len(self.out)\nfor i in range(n):\n"
                        "    self.out[i] = self.out[i] + 1.0\n"}) is not None:
        fails.append("OUTBUF: output written both whole and by index did not "
                     "reject")

    # ---- END-TO-END: compile + run subscript fixtures vs a numpy oracle that
    # pre-seeds self.<out> to N zeros (exactly what the interpreted node does).
    N = 4
    fixtures = [
        # (out_type, ins, out_plug, source, values, oracle_seed_shape)
        ("num", [("xs", "double", True)], "out",
         "n = len(self.out)\n"
         "for i in range(n):\n"
         "    self.out[i] = self.xs[i] * 2.0 + float(i)\n",
         {"xs": [1.0, 2.0, 3.0, 4.0]}, (N,)),
        ("vec", [("vin", "vector", True)], "pts",
         "n = len(self.pts)\n"
         "for i in range(n):\n"
         "    self.pts[i] = self.vin[i] * 2.0\n",
         {"vin": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [4.0, 5.0, 6.0],
                  [-1.0, -2.0, -3.0]]}, (N, 3)),
    ]
    for kind, ins_s, out_plug, source, values, seed_shape in fixtures:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        out_type = "vector" if kind == "vec" else "double"
        outd = _descr(out_plug, out_type, True, "output")
        try:
            body = nd_lower.lower_compute(ins, [outd], source)
        except Exception as e:
            fails.append("OUTBUF e2e %s: lower_compute raised %r" % (kind, e))
            continue
        # Hand-built main(): input + output decls, the `data` stub sized to N and
        # the member symbol (aOut/aPts) the count line references, then the body.
        member = _member(out_plug)
        L = [_SHIM, _OUTBUF_DATA_SHIM, "int main() {"]
        for d in ins:
            L.append(_decl_input(d, values[d["plug"]]))
        L.append(_decl_output(outd))
        L.append("    int %s = 0; (void)%s;" % (member, member))
        L.append("    _NDDataStub data{ (long long)%d };" % N)
        L.append("    // ===== lowered compute =====")
        L += body
        L.append("    // ===== probe =====")
        L.append(_print_output(outd))
        L.append("    return 0;\n}")
        cpp = "\n".join(L) + "\n"
        out, err = _compile_run(cpp, "outbuf_" + kind)
        if err:
            fails.append("OUTBUF e2e %s: %s" % (kind, err))
            continue
        got = _parse_probes(out).get(out_plug)
        # Oracle: seed self.<out> to N zeros (interpreted node pre-sizing), exec.
        obj = _Self()
        for d in ins:
            setattr(obj, d["plug"], np.asarray(values[d["plug"]],
                                               dtype=np.float64))
        setattr(obj, out_plug, np.zeros(seed_shape, dtype=np.float64))
        exec(_strip_imports(source), {"np": np, "self": obj})
        exp = np.asarray(getattr(obj, out_plug), dtype=np.float64).ravel()
        if got is None or got.shape != exp.shape:
            fails.append("OUTBUF e2e %s: shape %s != %s"
                         % (kind, None if got is None else got.shape, exp.shape))
        elif not np.allclose(got, exp, rtol=1e-12, atol=1e-12):
            i = int(np.argmax(np.abs(got - exp)))
            fails.append("OUTBUF e2e %s: got=%.17g exp=%.17g at %d"
                         % (kind, got[i], exp[i], i))


# The aim_between_matrices compute: two MATRIX inputs (via .asNumpy()), an
# orthonormal aim basis made parent-relative with a CONNECTED parentWorld
# (self.local_matrix = M @ inv(P)), rotate + translate gates. Exercises the
# transform matrix-input frame, .asNumpy() passthrough, np.stack/concatenate,
# float()-wrapped norm/dot scalars, np.linalg.inv and the sink + gate writers.
_AIM_COMPUTE = (
    "m0 = self.matrix0.asNumpy()\n"
    "m1 = self.matrix1.asNumpy()\n"
    "p0 = m0[3, :3]\n"
    "p1 = m1[3, :3]\n"
    "fwd = p1 - p0\n"
    "length = float(np.linalg.norm(fwd))\n"
    "if length < 1e-9:\n"
    "    fwd = np.array([1.0, 0.0, 0.0])\n"
    "else:\n"
    "    fwd = fwd / length\n"
    "up = np.array([0.0, 1.0, 0.0])\n"
    "if abs(float(np.dot(fwd, up))) > 0.999:\n"
    "    up = np.array([0.0, 0.0, 1.0])\n"
    "side = np.cross(fwd, up)\n"
    "side = side / (float(np.linalg.norm(side)) + 1e-12)\n"
    "up2 = np.cross(side, fwd)\n"
    "c = 0.5 * (p0 + p1)\n"
    "row0 = np.concatenate([fwd, np.zeros(1)])\n"
    "row1 = np.concatenate([up2, np.zeros(1)])\n"
    "row2 = np.concatenate([side, np.zeros(1)])\n"
    "row3 = np.concatenate([c, np.ones(1)])\n"
    "M = np.stack([row0, row1, row2, row3])\n"
    "P = self.parentWorld.asNumpy()\n"
    "self.local_matrix = M @ np.linalg.inv(P)\n"
    "self.apply_rotate = True\n"
    "self.apply_translate = True\n"
)


class _MatrixView:
    """Oracle stand-in for the interpreted MatrixView (self.matrixK.asNumpy())."""

    def __init__(self, a):
        self._a = np.asarray(a, dtype=np.float64)

    def asNumpy(self):
        return self._a


def _mmat_lit_named(name, mat):
    """C++ `MMatrix <name>{16 row-major doubles};` seeding the initializer-list
    ctor the _SHIM MMatrix provides."""
    flat = ", ".join(_cpp_lit(mat[r][c]) for r in range(4) for c in range(4))
    return "    MMatrix %s{%s};" % (name, flat)


def _check_transform_matrix_inputs(fails):
    """T5 (aim): a transform whose desiredLocal() reads MATRIX INPUTS (matrix0/
    matrix1/parentWorld via .asNumpy()) and publishes an orthonormal aim basis via
    self.local_matrix = M @ inv(parentWorld) + apply_rotate/translate must lower
    deterministically AND match numpy. Proves the matrix-input frame + np.linalg.inv
    + the local_matrix sink + gate writers end-to-end, Maya-free (the scaffold
    exposes matrix0/matrix1/parentWorld as `in_aMatrix0`/`in_aMatrix1`/
    `in_aParentWorld` MMatrix locals; here they are shimmed + seeded)."""
    spec = {"compute": _AIM_COMPUTE, "init": "import numpy as np\n",
            "inputs": {"matrix0": {"type": "matrix", "is_array": False},
                       "matrix1": {"type": "matrix", "is_array": False},
                       "parentWorld": {"type": "matrix", "is_array": False}}}
    try:
        body = nd_lower.lower_transform(spec)
    except Exception as e:
        fails.append("XF-MTX aim: lower_transform raised %r" % e)
        return

    # Two driver matrices (translation-only) + an invertible parent world.
    def _xlate(p):
        return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0], [p[0], p[1], p[2], 1.0]]
    inputs = {"matrix0": _xlate([1.0, 2.0, 3.0]),
              "matrix1": _xlate([4.0, 6.0, 3.0]),
              "parentWorld": _PW}

    cpp = _gen_transform_cpp(inputs, body)
    out, err = _compile_run(cpp, "xf_aim")
    if err:
        fails.append("XF-MTX aim: %s" % err)
        return
    probes = _parse_probes(out)
    exp = _transform_oracle(inputs, _AIM_COMPUTE)

    # The aim publishes a LOCAL matrix (world @ inv(parent)) with rotate+translate.
    if not exp["local_set"]:
        fails.append("XF-MTX aim: oracle did not set local_matrix")
        return
    got = probes.get("local_matrix")
    ref = exp["local_matrix"]
    if got is None or got.shape != ref.shape:
        fails.append("XF-MTX aim: shape %s != %s"
                     % (None if got is None else got.shape, ref.shape))
    elif not np.allclose(got, ref, rtol=1e-9, atol=1e-9):
        i = int(np.argmax(np.abs(got - ref)))
        fails.append("XF-MTX aim: got=%.17g exp=%.17g at %d"
                     % (got[i], ref[i], i))
    flags = probes.get("flags")
    exp_flags = [exp["local_set"], exp["apply_rotate"],
                 exp["apply_translate"], exp["apply_scale"]]
    if flags is None or [int(x) for x in flags] != [int(b) for b in exp_flags]:
        fails.append("XF-MTX aim: flags %s != %s" % (flags, exp_flags))


def main():
    fails = []
    _check_recursion_rank_normalization(fails)
    _check_linalg_p2_block_path(fails)
    _check_external_helper_units(fails)
    _check_output_buffer_contract(fails)
    _check_transform_matrix_inputs(fails)
    n_ok = 0
    for name, ins_s, outs_s, source, values in POS:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        outs = [_descr(p, t, a, "output") for (p, t, a) in outs_s]
        try:
            body = nd_lower.lower_compute(ins, outs, source)
        except Exception as e:
            fails.append("%s: lower_compute raised %r" % (name, e))
            continue
        cpp = _gen_cpp(ins, outs, values, body)
        out, err = _compile_run(cpp, name)
        if err:
            fails.append("%s: %s" % (name, err))
            continue
        got = _parse_probes(out)
        exp = _oracle(ins, outs, values, source)
        ok = True
        for d in outs:
            plug = d["plug"]
            g = got.get(plug)
            e = exp[plug]
            if g is None or g.shape != e.shape:
                fails.append("%s.%s: shape %s != %s"
                             % (name, plug, None if g is None else g.shape,
                                e.shape))
                ok = False
                continue
            # color children are FLOAT (set3Float) -> allow float epsilon.
            tol = 1e-6 if d["meta"]["type"] == "color" else 1e-9
            if not np.allclose(g, e, rtol=tol, atol=tol):
                i = int(np.argmax(np.abs(g - e)))
                fails.append("%s.%s: got=%.17g exp=%.17g at %d"
                             % (name, plug, g[i], e[i], i))
                ok = False
        if ok:
            n_ok += 1

    n_rej = 0
    for name, ins_s, outs_s, source in REJ:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        outs = [_descr(p, t, a, "output") for (p, t, a) in outs_s]
        spec = {"compute": source}
        res = nd_lower.try_lower_compute(ins, outs, spec)
        if res is not None:
            fails.append("REJECT %s: expected None, got %d lines"
                         % (name, len(res)))
        else:
            n_rej += 1

    # ----- inline-helper fixtures (INIT-tier free functions) -----
    n_help = 0
    for name, ins_s, outs_s, init, source, values in HELP:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        outs = [_descr(p, t, a, "output") for (p, t, a) in outs_s]
        try:
            body = nd_lower.lower_compute(ins, outs, source, init)
        except Exception as e:
            fails.append("HELP %s: lower_compute raised %r" % (name, e))
            continue
        cpp = _gen_cpp(ins, outs, values, body)
        out, err = _compile_run(cpp, "help_" + name)
        if err:
            fails.append("HELP %s: %s" % (name, err))
            continue
        got = _parse_probes(out)
        exp = _oracle(ins, outs, values, source, init)
        ok = True
        for d in outs:
            plug = d["plug"]
            g = got.get(plug)
            e = exp[plug]
            if g is None or g.shape != e.shape:
                fails.append("HELP %s.%s: shape %s != %s"
                             % (name, plug, None if g is None else g.shape,
                                e.shape))
                ok = False
                continue
            if not np.allclose(g, e, rtol=1e-9, atol=1e-9):
                i = int(np.argmax(np.abs(g - e)))
                fails.append("HELP %s.%s: got=%.17g exp=%.17g at %d"
                             % (name, plug, g[i], e[i], i))
                ok = False
        if ok:
            n_help += 1

    n_help_rej = 0
    for name, ins_s, outs_s, init, source in HELP_REJ:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        outs = [_descr(p, t, a, "output") for (p, t, a) in outs_s]
        res = nd_lower.try_lower_compute(ins, outs,
                                         {"compute": source, "init": init})
        if res is not None:
            fails.append("HELP REJECT %s: expected None, got %d lines"
                         % (name, len(res)))
        else:
            n_help_rej += 1

    # ----- geometry-generator fixtures (buffer fill) -----
    n_geo = 0
    for name, kind, ins_s, source, values in GEO:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        try:
            body = nd_lower.lower_geo_compute(ins, kind, source)
        except Exception as e:
            fails.append("GEO %s: lower_geo_compute raised %r" % (name, e))
            continue
        cpp = _gen_geo_cpp(ins, kind, values, body)
        out, err = _compile_run(cpp, "geo_" + name)
        if err:
            fails.append("GEO %s: %s" % (name, err))
            continue
        got = _parse_probes(out)
        exp = _geo_oracle(ins, kind, values, source)
        ok = True
        for buf, e in exp.items():
            g = got.get(buf)
            if g is None or g.shape != e.shape:
                fails.append("GEO %s.%s: shape %s != %s"
                             % (name, buf, None if g is None else g.shape,
                                e.shape))
                ok = False
                continue
            if not np.allclose(g, e, rtol=1e-9, atol=1e-9):
                i = int(np.argmax(np.abs(g - e)))
                fails.append("GEO %s.%s: got=%.17g exp=%.17g at %d"
                             % (name, buf, g[i], e[i], i))
                ok = False
        if ok:
            n_geo += 1

    n_geo_rej = 0
    for name, kind, ins_s, source in GEO_REJ:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        res = nd_lower.try_lower_geo_compute(ins, kind, {"compute": source})
        if res is not None:
            fails.append("GEO REJECT %s: expected None, got %d lines"
                         % (name, len(res)))
        else:
            n_geo_rej += 1

    # ----- geo + inline-helper fixtures (the full GoL mPyMesh template) -----
    n_geohelp = 0
    for name, kind, ins_s, init, source, values in GEO_HELP:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        try:
            body = nd_lower.lower_geo_compute(ins, kind, source, init)
        except Exception as e:
            fails.append("GEOHELP %s: lower_geo_compute raised %r" % (name, e))
            continue
        cpp = _gen_geo_cpp(ins, kind, values, body)
        out, err = _compile_run(cpp, "geohelp_" + name)
        if err:
            fails.append("GEOHELP %s: %s" % (name, err))
            continue
        got = _parse_probes(out)
        exp = _geo_oracle(ins, kind, values, source, init)
        ok = True
        for buf, e in exp.items():
            g = got.get(buf)
            if g is None or g.shape != e.shape:
                fails.append("GEOHELP %s.%s: shape %s != %s"
                             % (name, buf, None if g is None else g.shape,
                                e.shape))
                ok = False
                continue
            if not np.allclose(g, e, rtol=1e-9, atol=1e-9):
                i = int(np.argmax(np.abs(g - e)))
                fails.append("GEOHELP %s.%s: got=%.17g exp=%.17g at %d"
                             % (name, buf, g[i], e[i], i))
                ok = False
        if ok:
            n_geohelp += 1

    # ----- deformer fixtures (getPoints/setPoints in-place mutate) -----
    n_def = 0
    for name, rest, env_val, ins_s, source, values in DEF:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        spec = {"compute": source}
        try:
            body = nd_lower.lower_deform(ins, spec, "MPxDeformerNode")
        except Exception as e:
            fails.append("DEF %s: lower_deform raised %r" % (name, e))
            continue
        cpp = _gen_deform_cpp(ins, rest, env_val, values, body)
        out, err = _compile_run(cpp, "def_" + name)
        if err:
            fails.append("DEF %s: %s" % (name, err))
            continue
        got = _parse_probes(out).get("points")
        exp = _deform_oracle(ins, rest, env_val, values, source)
        if got is None or got.shape != exp.shape:
            fails.append("DEF %s.points: shape %s != %s"
                         % (name, None if got is None else got.shape, exp.shape))
        elif not np.allclose(got, exp, rtol=1e-9, atol=1e-9):
            i = int(np.argmax(np.abs(got - exp)))
            fails.append("DEF %s.points: got=%.17g exp=%.17g at %d"
                         % (name, got[i], exp[i], i))
        else:
            n_def += 1

    n_def_rej = 0
    for name, base, env_val, ins_s, source, values in DEF_REJ:
        ins = [_descr(p, t, a, "input") for (p, t, a) in ins_s]
        res = nd_lower.try_lower_deform(ins, {"compute": source}, base)
        if res is not None:
            fails.append("DEF REJECT %s: expected None, got %d lines"
                         % (name, len(res)))
        else:
            n_def_rej += 1

    # ----- skinCluster fixtures (compiled linear-blend skinning) -----
    n_skin = 0
    for name, rest, env_val, joint_mats, bind_mats, w_dense in SKIN:
        try:
            body = nd_lower.lower_deform([], {"compute": _SKIN_SRC},
                                        "MPxSkinCluster")
        except Exception as e:
            fails.append("SKIN %s: lower_deform raised %r" % (name, e))
            continue
        cpp = _gen_skin_deform_cpp(rest, env_val, joint_mats, bind_mats,
                                   w_dense, body)
        out, err = _compile_run(cpp, "skin_" + name)
        if err:
            fails.append("SKIN %s: %s" % (name, err))
            continue
        got = _parse_probes(out).get("points")
        exp = _skin_deform_oracle(rest, env_val, joint_mats, bind_mats,
                                  w_dense, _SKIN_SRC)
        if got is None or got.shape != exp.shape:
            fails.append("SKIN %s.points: shape %s != %s"
                         % (name, None if got is None else got.shape, exp.shape))
        elif not np.allclose(got, exp, rtol=1e-9, atol=1e-9):
            i = int(np.argmax(np.abs(got - exp)))
            fails.append("SKIN %s.points: got=%.17g exp=%.17g at %d"
                         % (name, got[i], exp[i], i))
        else:
            n_skin += 1

    # ----- skinCluster fixtures (compiled dual-quaternion skinning) -----
    n_skin_dqs = 0
    for name, rest, env_val, joint_mats, bind_mats, w_dense in SKIN_DQS:
        try:
            body = nd_lower.lower_deform([], {"compute": _SKIN_DQS_SRC},
                                        "MPxSkinCluster")
        except Exception as e:
            fails.append("SKIN_DQS %s: lower_deform raised %r" % (name, e))
            continue
        cpp = _gen_skin_deform_cpp(rest, env_val, joint_mats, bind_mats,
                                   w_dense, body)
        out, err = _compile_run(cpp, "skin_dqs_" + name)
        if err:
            fails.append("SKIN_DQS %s: %s" % (name, err))
            continue
        got = _parse_probes(out).get("points")
        exp = _skin_deform_oracle(rest, env_val, joint_mats, bind_mats,
                                  w_dense, _SKIN_DQS_SRC)
        if got is None or got.shape != exp.shape:
            fails.append("SKIN_DQS %s.points: shape %s != %s"
                         % (name, None if got is None else got.shape, exp.shape))
        elif not np.allclose(got, exp, rtol=1e-8, atol=1e-8):
            i = int(np.argmax(np.abs(got - exp)))
            fails.append("SKIN_DQS %s.points: got=%.17g exp=%.17g at %d"
                         % (name, got[i], exp[i], i))
        else:
            n_skin_dqs += 1

    # ----- skin via blessed API methods (Transpile-lowered free fn) -----
    # Both method forms must compile to C++ numerically identical to the inline
    # default (oracle runs the inline source), proving self.linear_blend /
    # self.dual_quaternion lower to the same pure-C++ math with no AI port.
    n_skin_method = 0
    _METHOD_CASES = (
        ("LBS", _SKIN_METHOD_LBS, _SKIN_SRC, SKIN, 1e-9),
        ("DQS", _SKIN_METHOD_DQS, _SKIN_DQS_SRC, SKIN_DQS, 1e-8),
    )
    _n_skin_method_total = sum(len(fx) for _t, _m, _i, fx, _tol in _METHOD_CASES)
    for tag, method_src, inline_src, fixtures, tol in _METHOD_CASES:
        spec = dict(_SKIN_METHOD_SPEC, compute=method_src)
        for name, rest, env_val, joint_mats, bind_mats, w_dense in fixtures:
            try:
                body = nd_lower.lower_deform([], spec, "MPxSkinCluster")
            except Exception as e:
                fails.append("SKIN_METHOD %s %s: lower_deform raised %r"
                             % (tag, name, e))
                continue
            cpp = _gen_skin_deform_cpp(rest, env_val, joint_mats, bind_mats,
                                       w_dense, body)
            out, err = _compile_run(cpp, "skin_method_%s_%s" % (tag, name))
            if err:
                fails.append("SKIN_METHOD %s %s: %s" % (tag, name, err))
                continue
            got = _parse_probes(out).get("points")
            exp = _skin_deform_oracle(rest, env_val, joint_mats, bind_mats,
                                      w_dense, inline_src)
            if got is None or got.shape != exp.shape:
                fails.append("SKIN_METHOD %s %s.points: shape %s != %s"
                             % (tag, name, None if got is None else got.shape,
                                exp.shape))
            elif not np.allclose(got, exp, rtol=tol, atol=tol):
                i = int(np.argmax(np.abs(got - exp)))
                fails.append("SKIN_METHOD %s %s.points: got=%.17g exp=%.17g at %d"
                             % (tag, name, got[i], exp[i], i))
            else:
                n_skin_method += 1

    # ----- transform fixtures (desiredLocal() gated local-matrix sink) -----
    n_xf = 0
    for name, inputs, source in TRANS:
        spec = {"compute": source,
                "inputs": {p: {"type": "matrix", "is_array": False}
                           for p in inputs}}
        try:
            body = nd_lower.lower_transform(spec)
        except Exception as e:
            fails.append("XF %s: lower_transform raised %r" % (name, e))
            continue
        cpp = _gen_transform_cpp(inputs, body)
        out, err = _compile_run(cpp, "xf_" + name)
        if err:
            fails.append("XF %s: %s" % (name, err))
            continue
        probes = _parse_probes(out)
        exp = _transform_oracle(inputs, source)
        ok = True
        # Flags must match exactly.
        flags = probes.get("flags")
        exp_flags = [int(exp["local_set"]),
                     int(exp["apply_rotate"]), int(exp["apply_translate"]),
                     int(exp["apply_scale"])]
        if flags is None or [int(x) for x in flags] != exp_flags:
            fails.append("XF %s: flags %s != %s" % (name, flags, exp_flags))
            ok = False
        # Compare the local_matrix sink the compute set.
        if exp["local_matrix"] is not None:
            g = probes.get("local_matrix")
            e = exp["local_matrix"]
            if g is None or g.shape != e.shape:
                fails.append("XF %s.local_matrix: shape %s != %s"
                             % (name, None if g is None else g.shape, e.shape))
                ok = False
            elif not np.allclose(g, e, rtol=1e-9, atol=1e-9):
                i = int(np.argmax(np.abs(g - e)))
                fails.append("XF %s.local_matrix: got=%.17g exp=%.17g at %d"
                             % (name, g[i], e[i], i))
                ok = False
        if ok:
            n_xf += 1

    n_xf_rej = 0
    for name, source in TRANS_REJ:
        res = nd_lower.try_lower_transform({"compute": source})
        if res is not None:
            fails.append("XF REJECT %s: expected None, got %d lines"
                         % (name, len(res)))
        else:
            n_xf_rej += 1

    print("positive_ok=%d/%d rejects_ok=%d/%d help_ok=%d/%d help_rejects_ok=%d/%d "
          "geo_ok=%d/%d geo_rejects_ok=%d/%d geohelp_ok=%d/%d "
          "def_ok=%d/%d def_rejects_ok=%d/%d skin_ok=%d/%d skin_dqs_ok=%d/%d "
          "skin_method_ok=%d/%d xf_ok=%d/%d xf_rejects_ok=%d/%d"
          % (n_ok, len(POS), n_rej, len(REJ), n_help, len(HELP),
             n_help_rej, len(HELP_REJ), n_geo, len(GEO),
             n_geo_rej, len(GEO_REJ), n_geohelp, len(GEO_HELP),
             n_def, len(DEF), n_def_rej, len(DEF_REJ), n_skin, len(SKIN),
             n_skin_dqs, len(SKIN_DQS),
             n_skin_method, _n_skin_method_total,
             n_xf, len(TRANS), n_xf_rej, len(TRANS_REJ)))
    if fails:
        print("FAIL (%d):" % len(fails))
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("ALL PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
