"""py_to_cpp transpiler parity oracle/driver (run under mayapy, Maya-free).

For each fixture (a small numpy compute function + concrete inputs) this:
  1. runs the Python function under numpy  -> the ground-truth result;
  2. transpiles the SAME source to C++ nd:: statements via py_to_cpp;
  3. wraps it in `auto compute(args)`, materialises the inputs, compiles with
     clang++ -std=c++17 -O2, runs it, and parses the RES line;
  4. asserts the C++ result matches numpy (allclose for float, exact for int).

The Python source is BOTH the thing under test and the oracle -- there is no
hand-written expected value to drift. A second suite asserts that idioms outside
the supported surface raise UnsupportedSpec (reject-or-lower, never mis-lower).

Usage:  mayapy py_to_cpp_test.py
Exit 0 == every fixture parity-clean AND every reject rejected.
"""
import os
import sys
import math
import shutil
import subprocess
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# HERE is .../scripts/mpynode/native/tests -- three dirname()s to reach scripts/.
# _INC = .../scripts/mpynode/native/compiler (where nd_runtime.h now lives).
_INC = os.path.join(os.path.dirname(HERE), "compiler")
_SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # .../scripts
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from mpynode.native.compiler import py_to_cpp
from mpynode.native.compiler.py_to_cpp import (array_t, scalar_t, transpile_function,
                                      UnsupportedSpec)

_CTYPE = {"double": "double", "int64": "int64_t", "bool": "bool"}

# A fixed-seed generator for fixture inputs that need generic (non-structured)
# matrices -- SVD/det/einsum. Seeded so every run is byte-identical.
_R = np.random.RandomState(20260709)


# --------------------------------------------------------------------------
# type / literal helpers
# --------------------------------------------------------------------------
def _dtag(dtype):
    k = np.dtype(dtype).kind
    if k == "f":
        return "double"
    if k in "iu":
        return "int64"
    if k == "b":
        return "bool"
    raise TypeError("unsupported input dtype %r" % dtype)


def _cpp_type_of(v):
    if isinstance(v, np.ndarray):
        return array_t(_dtag(v.dtype), v.ndim)
    if isinstance(v, (bool, np.bool_)):
        return scalar_t("bool")
    if isinstance(v, (int, np.integer)):
        return scalar_t("int64")
    if isinstance(v, (float, np.floating)):
        return scalar_t("double")
    raise TypeError("unsupported input value %r" % (v,))


def _cval(x, dt):
    if dt == "bool":
        return "true" if bool(x) else "false"
    if dt == "int64":
        return "%d" % int(x)
    v = float(x)
    if math.isinf(v):
        return "(-INFINITY)" if v < 0 else "INFINITY"
    if math.isnan(v):
        return "NAN"
    r = repr(v)
    if ("." not in r) and ("e" not in r) and ("E" not in r):
        r += ".0"
    return r


def _emit_input(name, v):
    if isinstance(v, np.ndarray):
        dt = _dtag(v.dtype)
        flat = ", ".join(_cval(x, dt) for x in v.ravel(order="C").tolist())
        dims = ", ".join(str(d) for d in v.shape)
        return ("nd::Array<%s> %s = nd::from_data<%s>({%s}, {%s});"
                % (_CTYPE[dt], name, _CTYPE[dt], flat, dims))
    dt = _cpp_type_of(v).dtype
    return "%s %s = %s;" % (_CTYPE[dt], name, _cval(v, dt))


def _sig(name, t):
    if t.is_array():
        return "nd::Array<%s> %s" % (_CTYPE[t.dtype], name)
    return "%s %s" % (_CTYPE[t.dtype], name)


_PREAMBLE = r"""#include "nd_runtime.h"
#include <cstdio>
#include <cstdint>

static void pe(double v){ std::printf(" %.17g", v); }
static void pe(int64_t v){ std::printf(" %lld", (long long)v); }
static void pe(bool v){ std::printf(" %d", v ? 1 : 0); }

template <class T> static const char* dtag();
template <> const char* dtag<double>(){ return "f64"; }
template <> const char* dtag<int64_t>(){ return "i64"; }
template <> const char* dtag<bool>(){ return "bool"; }

template <class T>
static void print_result(const nd::Array<T>& a){
    nd::Array<T> c = a.copy();
    std::printf("RES %s %lld", dtag<T>(), (long long)c.ndim());
    for (int64_t d : c.shape) std::printf(" %lld", (long long)d);
    std::printf(" :");
    for (size_t i = 0; i < c.data->size(); ++i) pe((T)(*c.data)[i]);
    std::printf("\n");
}
static void print_result(double v){ std::printf("RES f64 0 : %.17g\n", v); }
static void print_result(int64_t v){ std::printf("RES i64 0 : %lld\n", (long long)v); }
static void print_result(bool v){ std::printf("RES bool 0 : %d\n", v ? 1 : 0); }
"""


def _build_program(src, inputs):
    order = list(inputs.keys())
    arg_types = {k: _cpp_type_of(v) for k, v in inputs.items()}
    res = transpile_function(src, arg_types)
    sig = ", ".join(_sig(n, arg_types[n]) for n in res.arg_names)
    lines = [_PREAMBLE, ""]
    lines.append("static auto compute(%s) {" % sig)
    lines.extend(res.decl_lines)
    lines.extend(res.body_lines)
    lines.append("}")
    lines.append("")
    lines.append("int main() {")
    for n in order:
        lines.append("    " + _emit_input(n, inputs[n]))
    call = ", ".join(res.arg_names)
    lines.append("    auto __r = compute(%s);" % call)
    lines.append("    print_result(__r);")
    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# compile + run one program
# --------------------------------------------------------------------------
def _compile_and_run(cxx, program, tag):
    # Compile + run in a private per-invocation temp dir so two harness processes
    # sharing this checkout (the Maya-2024 and Maya-2026 gates at once) never race
    # on a fixed file -- one's cleanup deleting the other's binary between compile
    # and exec. The nd:: runtime is found via -I _INC (native/compiler).
    with tempfile.TemporaryDirectory(prefix="pytocpp_%s_" % tag) as d:
        cpp = os.path.join(d, "t.cpp")
        exe = os.path.join(d, "t.bin")
        with open(cpp, "w") as fh:
            fh.write(program)
        cmd = [cxx, "-std=c++17", "-O2", "-I", _INC, cpp, "-o", exe]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return None, "COMPILE FAILED:\n%s\n---program---\n%s" % (
                r.stderr, program)
        out = subprocess.run([exe], capture_output=True, text=True)
        if out.returncode != 0:
            return None, "RUN FAILED:\n%s" % out.stderr
        return out.stdout, None


def _parse_res(text):
    for line in text.splitlines():
        t = line.split()
        if not t or t[0] != "RES":
            continue
        tag = t[1]
        ndim = int(t[2])
        dims = [int(x) for x in t[3:3 + ndim]]
        assert t[3 + ndim] == ":", line
        vals = t[3 + ndim + 1:]
        if tag == "i64":
            arr = np.array([int(v) for v in vals], dtype=np.int64)
        elif tag == "bool":
            arr = np.array([int(v) for v in vals], dtype=np.int64).astype(np.bool_)
        else:
            arr = np.array([float(v) for v in vals], dtype=np.float64)
        arr = arr.reshape(dims) if ndim > 0 else arr.reshape(())
        return tag, arr
    return None, None


def _run_oracle(name, src, inputs):
    ns = {"np": np, "numpy": np, "math": math}
    exec(src, ns)
    fn = ns[name]
    return fn(**{k: (v.copy() if isinstance(v, np.ndarray) else v)
                 for k, v in inputs.items()})


# --------------------------------------------------------------------------
# fixtures: (name, source, inputs)   -- source's def name MUST == name
# --------------------------------------------------------------------------
def _F(name, src, **inputs):
    # `_tol=(rtol, atol)` overrides the default tight float tolerance. Used only
    # for the Jacobi-SVD family, whose singular vectors are not LAPACK-identical;
    # results are compared via convention-independent quantities.
    tol = inputs.pop("_tol", None)
    return (name, src, inputs, tol)


FIXTURES = [
    _F("scalar_arith",
       "def scalar_arith(a, b):\n"
       "    return a * b + a / b - 2.0\n",
       a=3.0, b=4.0),
    _F("scalar_int_ops",
       "def scalar_int_ops(a, b):\n"
       "    return a // b + a % b\n",
       a=17, b=5),
    _F("scalar_pow_neg",
       "def scalar_pow_neg(a):\n"
       "    return -(a ** 3) + 1.0\n",
       a=2.5),
    _F("array_elementwise",
       "def array_elementwise(a, b):\n"
       "    return a * b + a - b / 2.0\n",
       a=np.array([1.0, 2.0, 3.0, 4.0]),
       b=np.array([5.0, 6.0, 7.0, 8.0])),
    _F("broadcast_2d",
       "def broadcast_2d(a, b):\n"
       "    return a + b\n",
       a=np.arange(3.0).reshape(3, 1),
       b=np.arange(4.0).reshape(1, 4)),
    _F("int_truediv_promote",
       "def int_truediv_promote(a):\n"
       "    return a / 2\n",
       a=np.array([1, 2, 3, 7], dtype=np.int64)),
    _F("floordiv_mod_array",
       "def floordiv_mod_array(a, b):\n"
       "    return a // b + a % b\n",
       a=np.array([-7, 8, 9, -10], dtype=np.int64), b=3),
    _F("power_array",
       "def power_array(a):\n"
       "    return a ** 2\n",
       a=np.array([1.0, -2.0, 3.5])),
    _F("ufuncs",
       "def ufuncs(a):\n"
       "    return np.sin(a) + np.sqrt(np.abs(a)) + np.floor(a)\n",
       a=np.array([-1.5, 0.5, 2.25, 4.0])),
    # Phase-2 fusion ADVERSARIAL: the fused output variable is ALSO an input
    # leaf (`a = a + b`). A by-reference leaf bind would alias the reallocated
    # output and read zeros; leaves must be captured by value. (Regression for
    # the fusion self-aliasing bug.)
    _F("fuse_self_alias_arith",
       "def fuse_self_alias_arith(a, b):\n"
       "    a = a + b\n"
       "    a = a * b - a\n"
       "    a = -a + b\n"
       "    return a\n",
       a=np.array([1.0, 2.0, 3.0, 4.0]),
       b=np.array([5.0, 6.0, 7.0, 8.0])),
    # Phase-2 fusion ADVERSARIAL: a SCALAR leaf reads the destination
    # (`a = a / (sum(a)+1)`). The scalar must be hoisted BEFORE the output is
    # reallocated, else it reads the fresh (zeroed) buffer -> wrong divisor.
    _F("fuse_self_alias_scalar_leaf",
       "def fuse_self_alias_scalar_leaf(a):\n"
       "    a = a / (float(a.sum()) + 1.0)\n"
       "    return a * 2.0 - a\n",
       a=np.array([1.0, 2.0, 3.0, 4.0])),
    # Phase-2 fusion ADVERSARIAL: rank-2 self-alias (contiguity guard + flat
    # read + by-value capture on a 2-D destination).
    _F("fuse_self_alias_2d",
       "def fuse_self_alias_2d(m, n):\n"
       "    m = m * n + m\n"
       "    return m - n\n",
       m=np.arange(12.0).reshape(3, 4),
       n=(np.arange(12.0).reshape(3, 4) + 1.0)),
    # Phase-2 fusion ADVERSARIAL: an INLINE bool-arithmetic scalar leaf whose
    # value is 2 (bool + bool). It must NOT be hoisted into `const bool` (which
    # would truncate 2 -> 1); the fused result must equal a + 2, matching the
    # nd:: cast-to-int64. (Regression for the bool-scalar-leaf fusion bug.)
    _F("fuse_bool_scalar_leaf",
       "def fuse_bool_scalar_leaf(a, p, q):\n"
       "    return a + ((p > 0) + (q > 0))\n",
       a=np.array([10, 20, 30], dtype=np.int64), p=5, q=3),
    _F("reduce_axis",
       "def reduce_axis(a):\n"
       "    return a.sum(axis=1) + a.mean(axis=1)\n",
       a=np.arange(12.0).reshape(3, 4)),
    _F("reduce_all",
       "def reduce_all(a):\n"
       "    return a.sum() + a.max() - a.min()\n",
       a=np.array([[1.0, 5.0], [3.0, 2.0]])),
    _F("matmul_2d",
       "def matmul_2d(a, b):\n"
       "    return a @ b\n",
       a=np.arange(6.0).reshape(2, 3), b=np.arange(12.0).reshape(3, 4)),
    _F("matvec",
       "def matvec(a, v):\n"
       "    return a @ v\n",
       a=np.arange(6.0).reshape(2, 3), v=np.array([1.0, 2.0, 3.0])),
    # Matmul scalarization: exercise the small-fixed-size fast paths in
    # nd::matmul2d (3x3, 4x4, and a metaballs-style strided-slice (N,3)@(3,3)).
    # These must stay byte-identical to the generic loop.
    _F("matmul_3x3",
       "def matmul_3x3(a, b):\n"
       "    return a @ b\n",
       a=np.arange(9.0).reshape(3, 3), b=(np.arange(9.0).reshape(3, 3) + 0.5)),
    _F("matmul_4x4",
       "def matmul_4x4(a, b):\n"
       "    return a @ b\n",
       a=np.arange(16.0).reshape(4, 4), b=(np.arange(16.0).reshape(4, 4) - 3.0)),
    _F("matmul_strided_slice",
       "def matmul_strided_slice(p, m):\n"
       "    return p[:, :3] @ m[:3, :3]\n",
       p=np.arange(20.0).reshape(5, 4), m=(np.arange(16.0).reshape(4, 4) + 0.25)),
    # Matmul-as-fusion-producer (Inc2): the REAL metaballs hot transform -- a
    # strided (N,3) view @ (3,3) feeding a (3,) ROW broadcast. Must fuse into one
    # loop (inline dot-product producer + per-column broadcast read) and stay
    # byte-identical to nd::add(nd::matmul(...), rowvec). Non-contiguous A view.
    _F("matmul_bcast_transform",
       "def matmul_bcast_transform(p, m):\n"
       "    return p[:, :3] @ m[:3, :3] + m[3, :3]\n",
       p=np.arange(20.0).reshape(5, 4), m=(np.arange(16.0).reshape(4, 4) + 0.25)),
    # Inc2: pure row broadcast (rank-2 + rank-1), no matmul -- the (N,) operand
    # must be read by COLUMN index, byte-identical to nd::add broadcasting.
    _F("matmul_bcast_rowvec",
       "def matmul_bcast_rowvec(a, c):\n"
       "    return a * 2.0 + c\n",
       a=np.arange(12.0).reshape(3, 4), c=np.array([0.5, -1.0, 2.0, 3.5])),
    # Inc2: matmul producer combined with a scalar AND a row broadcast in one
    # fused tree ((a@b)*s + c). Exercises scalar-hoist + producer + bcast together.
    _F("matmul_prod_scaled_bcast",
       "def matmul_prod_scaled_bcast(a, b, s, c):\n"
       "    return (a @ b) * s + c\n",
       a=np.arange(6.0).reshape(2, 3), b=(np.arange(12.0).reshape(3, 4) - 2.0),
       s=1.5, c=np.array([1.0, 2.0, 3.0, 4.0])),
    # Inc2: integer dtype through the matmul producer + broadcast (promotion /
    # C++ integer accumulation must match nd::matmul + nd::add exactly).
    _F("matmul_bcast_int",
       "def matmul_bcast_int(a, b, c):\n"
       "    return a @ b + c\n",
       a=np.arange(6, dtype=np.int64).reshape(2, 3),
       b=np.arange(12, dtype=np.int64).reshape(3, 4),
       c=np.array([1, 2, 3, 4], dtype=np.int64)),
    # Inc2 ADVERSARIAL (skeptic panel): self-alias in PRODUCER mode -- the
    # assignment target is ALSO the matmul-A input. The matmul operands must be
    # snapshot BY VALUE before the output realloc (shared_ptr copy of the old
    # buffer), else the reads see the freshly-zeroed output.
    _F("matmul_selfalias_producer",
       "def matmul_selfalias_producer(a, b, c):\n"
       "    a = a @ b + c\n"
       "    return a\n",
       a=np.arange(9.0).reshape(3, 3), b=(np.arange(9.0).reshape(3, 3) + 1.0),
       c=np.array([10.0, 20.0, 30.0])),
    # Inc2 ADVERSARIAL: transposed / non-contiguous B (strides[0] < strides[1])
    # feeding the producer -- stride reads must match nd::matmul2d exactly.
    _F("matmul_transposed_b",
       "def matmul_transposed_b(p, m):\n"
       "    return p[:, :3] @ m[:3, :3].T + m[3, :3]\n",
       p=np.arange(12.0).reshape(4, 3), m=(np.arange(16.0).reshape(4, 4) + 0.1)),
    # Inc2 ADVERSARIAL: non-commutative ops with the row vector on the LEFT --
    # child/operand order must be preserved (c - a@b, c / (a@b), maximum(c, a@b)).
    _F("matmul_bcast_sub_left",
       "def matmul_bcast_sub_left(a, b, c):\n"
       "    return c - a @ b\n",
       a=np.arange(6.0).reshape(2, 3), b=(np.arange(12.0).reshape(3, 4) - 5.0),
       c=np.array([1.0, 2.0, 3.0, 4.0])),
    _F("matmul_bcast_div_denom",
       "def matmul_bcast_div_denom(a, b, c):\n"
       "    return c / (a @ b)\n",
       a=(np.arange(6.0).reshape(2, 3) + 1.0),
       b=(np.arange(12.0).reshape(3, 4) + 1.0),
       c=np.array([1.0, 2.0, 3.0, 4.0])),
    _F("matmul_bcast_maximum_left",
       "def matmul_bcast_maximum_left(a, b, c):\n"
       "    return np.maximum(c, a @ b)\n",
       a=(np.arange(6.0).reshape(2, 3) - 3.0),
       b=(np.arange(12.0).reshape(3, 4) - 6.0),
       c=np.array([0.0, 5.0, -5.0, 100.0])),
    # Inc2 ADVERSARIAL: two matmul producers summed into the same (m,N) output.
    _F("matmul_two_producers",
       "def matmul_two_producers(a, b, c, d):\n"
       "    return a @ b + c @ d\n",
       a=np.arange(6.0).reshape(2, 3), b=(np.arange(12.0).reshape(3, 4) + 1.0),
       c=np.arange(10.0).reshape(2, 5), d=(np.arange(20.0).reshape(5, 4) - 3.0)),
    # Inc2 ADVERSARIAL: K==0 empty inner dim -> acc runs zero times -> zeros(m,N)
    # + bcast (non-empty output; the guard passes on 0==0 inner-dim).
    _F("matmul_k0_inner",
       "def matmul_k0_inner(a, b, c):\n"
       "    return a @ b + c\n",
       a=np.zeros((2, 0)), b=np.zeros((0, 3)), c=np.array([1.0, 2.0, 3.0])),
    _F("cross_prod",
       "def cross_prod(a, b):\n"
       "    return np.cross(a, b)\n",
       a=np.array([1.0, 0.0, 0.0]), b=np.array([0.0, 1.0, 0.0])),
    _F("reshape_transpose",
       "def reshape_transpose(a):\n"
       "    return a.reshape(3, 2).T\n",
       a=np.arange(6.0).reshape(2, 3)),
    _F("slice_strided",
       "def slice_strided(a):\n"
       "    return a[2:8:2] + a[::-1][2:8:2]\n",
       a=np.arange(10.0)),
    _F("slice_2d_block",
       "def slice_2d_block(m):\n"
       "    return m[1:3, 1:3]\n",
       m=np.arange(16.0).reshape(4, 4)),
    _F("slice_assign_loop",
       "def slice_assign_loop(n):\n"
       "    out = np.zeros(n)\n"
       "    for i in range(n):\n"
       "        out[i] = i * i\n"
       "    return out\n",
       n=6),
    _F("if_branch_hoist",
       "def if_branch_hoist(x):\n"
       "    if x > 0.0:\n"
       "        y = x * 2.0\n"
       "    else:\n"
       "        y = -x\n"
       "    return y + 1.0\n",
       x=-3.0),
    _F("while_accumulate",
       "def while_accumulate(n):\n"
       "    s = 0.0\n"
       "    i = 0\n"
       "    while i < n:\n"
       "        s = s + i\n"
       "        i = i + 1\n"
       "    return s\n",
       n=5),
    _F("clip_maximum",
       "def clip_maximum(a, b):\n"
       "    return np.clip(np.maximum(a, b), 0.0, 5.0)\n",
       a=np.array([-2.0, 3.0, 9.0, 1.0]),
       b=np.array([0.0, -1.0, 4.0, 7.0])),
    # NaN through maximum/minimum/clip. np.maximum/np.minimum PROPAGATE a NaN
    # from EITHER operand, and the transpiler fuses them into a scalar loop whose
    # per-element body must agree with the nd:: arm of the SAME guarded block --
    # a bare `a > b ? a : b` returns the non-NaN operand when the LEFT one is NaN,
    # so index 0 below (NaN on the left) is the case that catches the drift and
    # index 1 (NaN on the right) pins the other position. Every leaf here is a
    # LITERAL array on purpose: _R is a module-level RandomState consumed at
    # import in list order, so a fixture that drew from it would re-roll the
    # inputs of every fixture BELOW it and break unrelated cases.
    _F("nan_maximum_arrays",
       "def nan_maximum_arrays(a, b):\n"
       "    return np.maximum(a, b)\n",
       a=np.array([np.nan, 1.0, -2.0, 3.0]),
       b=np.array([2.0, np.nan, -5.0, 3.0])),
    _F("nan_minimum_arrays",
       "def nan_minimum_arrays(a, b):\n"
       "    return np.minimum(a, b)\n",
       a=np.array([np.nan, 1.0, -2.0, 3.0]),
       b=np.array([2.0, np.nan, -5.0, 3.0])),
    # array-vs-scalar: the other leaf shape (a hoisted `scl`), which is what the
    # deterministically-lowered templates actually emit.
    _F("nan_maximum_scalar",
       "def nan_maximum_scalar(a):\n"
       "    return np.maximum(a, 0.0)\n",
       a=np.array([np.nan, 1.0, -2.0, 3.0])),
    _F("nan_clip",
       "def nan_clip(a):\n"
       "    return np.clip(a, 0.0, 5.0)\n",
       a=np.array([np.nan, 1.0, -2.0, 9.0])),
    _F("newaxis_outer",
       "def newaxis_outer(a, b):\n"
       "    return a[:, None] * b[None, :]\n",
       a=np.array([1.0, 2.0, 3.0]), b=np.array([10.0, 20.0, 30.0, 40.0])),
    _F("norm_axis",
       "def norm_axis(a):\n"
       "    return np.linalg.norm(a, axis=1)\n",
       a=np.arange(12.0).reshape(3, 4)),
    _F("constructors",
       "def constructors(scale):\n"
       "    return np.linspace(0.0, 1.0, 5) * scale + np.arange(5) * 0.0\n",
       scale=2.0),
    _F("astype_trunc",
       "def astype_trunc(a):\n"
       "    return a.astype(int)\n",
       a=np.array([1.9, -1.9, 2.5, -2.5, 3.0])),
    _F("full_like_sum",
       "def full_like_sum(a):\n"
       "    return a + np.full_like(a, 10.0)\n",
       a=np.arange(6.0).reshape(2, 3)),
    _F("shape_unpack",
       "def shape_unpack(m):\n"
       "    h, w = m.shape\n"
       "    return m * float(h) + float(w)\n",
       m=np.arange(6.0).reshape(2, 3)),
    _F("rng_random",
       "def rng_random(seed):\n"
       "    rng = np.random.RandomState(seed)\n"
       "    return rng.random((3, 4))\n",
       seed=12345),
    _F("rng_scaled",
       "def rng_scaled(seed):\n"
       "    rng = np.random.RandomState(seed)\n"
       "    return rng.random((2, 5)) * 100.0 - 50.0\n",
       seed=7),
    # P1 ops added in SP-5 (formerly reject fixtures): now lowered + parity.
    _F("np_where",
       "def np_where(a):\n"
       "    return np.where(a > 0, a, -a)\n",
       a=np.array([-2.0, 3.0, -1.0, 4.0])),
    _F("np_roll",
       "def np_roll(a):\n"
       "    return np.roll(a, 1)\n",
       a=np.arange(5.0)),
    _F("np_concatenate",
       "def np_concatenate(a, b):\n"
       "    return np.concatenate([a, b])\n",
       a=np.array([1.0, 2.0, 3.0]), b=np.array([4.0, 5.0])),
    _F("array_compare",
       "def array_compare(a):\n"
       "    return a < 0.5\n",
       a=np.array([0.1, 0.9, 0.5, -0.3, 2.0])),
    # ---- SP-6: linalg P2 (diag / det / einsum / transpose axes / svd) -------
    _F("diag_1d_to_2d",
       "def diag_1d_to_2d(v):\n"
       "    return np.diag(v)\n",
       v=np.array([2.0, -3.0, 5.0, 7.0])),
    _F("diag_2d_to_1d",
       "def diag_2d_to_1d(m):\n"
       "    return np.diag(m)\n",
       m=np.arange(12.0).reshape(3, 4)),
    _F("det_3x3",
       "def det_3x3(m):\n"
       "    return np.linalg.det(m)\n",
       m=_R.randn(3, 3)),
    _F("det_2x2",
       "def det_2x2(m):\n"
       "    return np.linalg.det(m)\n",
       m=_R.randn(2, 2)),
    _F("det_batched",
       "def det_batched(a):\n"
       "    return np.linalg.det(a)\n",
       a=_R.randn(5, 3, 3)),
    # np.linalg.solve -- nd::solve is the same partial-pivot LU LAPACK
    # getrf/getrs runs, so these should agree far tighter than tolerance.
    #
    # These use LITERAL matrices rather than _R draws on purpose. `_R` is a
    # module-level seeded RandomState consumed at import in list order, so
    # adding a draw here would silently re-roll the inputs of every case
    # defined BELOW -- which is exactly how gather_rows_int_index first
    # started indexing out of bounds.
    _F("solve_3x3_vector_rhs",
       "def solve_3x3_vector_rhs(a, b):\n"
       "    return np.linalg.solve(a, b)\n",
       a=np.array([[4.0, 1.0, 2.0], [1.0, 5.0, 1.0], [2.0, 1.0, 6.0]]),
       b=np.array([1.0, 2.0, 3.0])),
    _F("solve_matrix_rhs",
       "def solve_matrix_rhs(a, b):\n"
       "    return np.linalg.solve(a, b)\n",
       a=np.array([[7.0, 1.0, 2.0, 0.0], [1.0, 8.0, 1.0, 2.0],
                   [2.0, 1.0, 9.0, 1.0], [0.0, 2.0, 1.0, 6.0]]),
       b=np.array([[1.0, -2.0], [3.0, 0.5], [-1.0, 4.0], [2.0, 1.0]])),
    # The exchange matrix plus a small diagonal: partial pivoting must swap on
    # EVERY column (|A[0,0]|=0.1 vs |A[7,0]|=1). A no-pivot LU divides by the
    # 0.1 diagonal and drifts badly, which the 3x3 cases above would not catch.
    _F("solve_8x8_needs_pivoting",
       "def solve_8x8_needs_pivoting(a, b):\n"
       "    return np.linalg.solve(a, b)\n",
       a=np.eye(8)[::-1] + 0.1 * np.eye(8),
       b=np.arange(1.0, 9.0)),
    # An exactly-zero leading pivot -- a swap is not an optimisation here, it
    # is the only thing standing between this and a divide by zero.
    _F("solve_zero_leading_pivot",
       "def solve_zero_leading_pivot(a, b):\n"
       "    return np.linalg.solve(a, b)\n",
       a=np.array([[0.0, 2.0], [3.0, 1.0]]), b=np.array([4.0, 5.0])),
    _F("einsum_matmul",
       "def einsum_matmul(a, b):\n"
       "    return np.einsum('ij,jk->ik', a, b)\n",
       a=_R.randn(3, 4), b=_R.randn(4, 2)),
    _F("einsum_batched_mm",
       "def einsum_batched_mm(a, b):\n"
       "    return np.einsum('nij,njk->nik', a, b)\n",
       a=_R.randn(5, 3, 3), b=_R.randn(5, 3, 3)),
    _F("einsum_three_ops",
       "def einsum_three_ops(a, b, c):\n"
       "    return np.einsum('nij,njk,nkl->nil', a, b, c)\n",
       a=_R.randn(4, 3, 3), b=_R.randn(4, 3, 3), c=_R.randn(4, 3, 3)),
    _F("einsum_matvec_batched",
       "def einsum_matvec_batched(a, v):\n"
       "    return np.einsum('nij,nj->ni', a, v)\n",
       a=_R.randn(6, 3, 3), v=_R.randn(6, 3)),
    _F("einsum_vecmat_batched",
       "def einsum_vecmat_batched(v, a):\n"
       "    return np.einsum('ni,nij->nj', v, a)\n",
       v=_R.randn(6, 3), a=_R.randn(6, 3, 3)),
    _F("einsum_gram",
       "def einsum_gram(p, q):\n"
       "    return np.einsum('nli,nlj->nij', p, q)\n",
       p=_R.randn(4, 8, 3), q=_R.randn(4, 8, 3)),
    _F("transpose_axes",
       "def transpose_axes(a):\n"
       "    return np.transpose(a, (0, 2, 1))\n",
       a=np.arange(24.0).reshape(2, 3, 4)),
    # Jacobi SVD -- compared via convention-independent quantities only.
    _F("svd_singular_values",
       "def svd_singular_values(m):\n"
       "    U, S, Vt = np.linalg.svd(m)\n"
       "    return S\n",
       m=_R.randn(3, 3), _tol=(1e-6, 1e-6)),
    _F("svd_reconstruct",
       "def svd_reconstruct(m):\n"
       "    U, S, Vt = np.linalg.svd(m)\n"
       "    return U @ np.diag(S) @ Vt\n",
       m=_R.randn(3, 3), _tol=(1e-6, 1e-6)),
    _F("svd_batched_reconstruct",
       "def svd_batched_reconstruct(a):\n"
       "    U, S, Vt = np.linalg.svd(a)\n"
       "    return U @ (S[:, :, None] * Vt)\n",
       a=_R.randn(5, 3, 3), _tol=(1e-6, 1e-6)),
    # np.linalg.inv (Gauss-Jordan) -- the aim transform's `inv(parent_matrix)`.
    # randn matrices are well-conditioned so nd::inv (partial-pivot GJ) matches
    # numpy's LU inverse element-for-element to ~1e-12.
    _F("inv_4x4",
       "def inv_4x4(m):\n"
       "    return np.linalg.inv(m)\n",
       m=_R.randn(4, 4), _tol=(1e-9, 1e-9)),
    _F("inv_3x3",
       "def inv_3x3(m):\n"
       "    return np.linalg.inv(m)\n",
       m=_R.randn(3, 3), _tol=(1e-9, 1e-9)),
    _F("inv_batched",
       "def inv_batched(a):\n"
       "    return np.linalg.inv(a)\n",
       a=_R.randn(5, 4, 4), _tol=(1e-9, 1e-9)),
    # Non-vacuous: m @ inv(m) == I (proves the inverse is a true inverse, not a
    # transpose/adjugate lookalike that would pass a shape-only check).
    _F("inv_reconstruct_identity",
       "def inv_reconstruct_identity(m):\n"
       "    return m @ np.linalg.inv(m)\n",
       m=_R.randn(4, 4), _tol=(1e-9, 1e-9)),
    # The real payoff: the Kabsch/Procrustes rotation. R is the UNIQUE optimal
    # rotation, so numpy's R and the Jacobi-SVD R agree despite different U/V
    # sign conventions. Exercises svd + det + diag + transpose + matmul chain.
    _F("kabsch_rotation",
       "def kabsch_rotation(p, q):\n"
       "    H = p.T @ q\n"
       "    U, S, Vt = np.linalg.svd(H)\n"
       "    d = float(np.sign(np.linalg.det(Vt.T @ U.T)))\n"
       "    sel = np.array([0.0, 0.0, 1.0])\n"
       "    vec = np.array([1.0, 1.0, 1.0]) + (d - 1.0) * sel\n"
       "    D = np.diag(vec)\n"
       "    R = Vt.T @ D @ U.T\n"
       "    return R\n",
       p=_R.randn(8, 3), q=_R.randn(8, 3), _tol=(1e-6, 1e-6)),
    # Batched reflection sign d = sign(det(Vt^T U^T)) -- convention-independent.
    _F("kabsch_sign_batched",
       "def kabsch_sign_batched(p, q):\n"
       "    H = np.einsum('nli,nlj->nij', p, q)\n"
       "    U, S, Vt = np.linalg.svd(H)\n"
       "    Vt_t = np.transpose(Vt, (0, 2, 1))\n"
       "    U_t = np.transpose(U, (0, 2, 1))\n"
       "    return np.sign(np.linalg.det(np.einsum('nij,njk->nik', Vt_t, U_t)))\n",
       p=_R.randn(4, 8, 3), q=_R.randn(4, 8, 3), _tol=(1e-6, 1e-6)),
    # Forces the reflection branch (d = -1): q is p reflected through the
    # xy-plane, so the proper-rotation solution MUST apply the Kabsch correction.
    # Validates the full R = Vt^T @ diag(1,1,-1) @ U^T assembly against numpy.
    _F("kabsch_reflection",
       "def kabsch_reflection(p):\n"
       "    refl = np.array([[1.0, 0.0, 0.0],\n"
       "                     [0.0, 1.0, 0.0],\n"
       "                     [0.0, 0.0, -1.0]])\n"
       "    q = p @ refl\n"
       "    H = p.T @ q\n"
       "    U, S, Vt = np.linalg.svd(H)\n"
       "    d = float(np.sign(np.linalg.det(Vt.T @ U.T)))\n"
       "    sel = np.array([0.0, 0.0, 1.0])\n"
       "    vec = np.array([1.0, 1.0, 1.0]) + (d - 1.0) * sel\n"
       "    D = np.diag(vec)\n"
       "    R = Vt.T @ D @ U.T\n"
       "    return R\n",
       p=_R.randn(8, 3), _tol=(1e-6, 1e-6)),
    # Batched slice-assignment into a tiled-identity stack (the vectorized
    # Procrustes reflection-guard D). Isolates D[:, 2, 2] = d on a (n,3,3) array.
    _F("batched_diag_slice_assign",
       "def batched_diag_slice_assign(d):\n"
       "    n = d.shape[0]\n"
       "    D = np.tile(np.eye(3), (n, 1, 1))\n"
       "    D[:, 2, 2] = d\n"
       "    return D\n",
       d=_R.randn(5), _tol=(1e-9, 1e-9)),
    # Batched block slice-assignment: the vectorized Maya-layout attachment M.
    _F("batched_block_assign",
       "def batched_block_assign(r, t):\n"
       "    n = r.shape[0]\n"
       "    M = np.tile(np.eye(4), (n, 1, 1))\n"
       "    M[:, :3, :3] = np.transpose(r, (0, 2, 1))\n"
       "    M[:, 3, :3] = t\n"
       "    return M\n",
       r=_R.randn(5, 3, 3), t=_R.randn(5, 3), _tol=(1e-9, 1e-9)),
    # The full VECTORIZED Kabsch rotation (tile+slice-assign D + 3-op einsum R).
    # Each cluster's R is the unique optimal rotation -> convention-independent.
    _F("batched_kabsch_rotation",
       "def batched_kabsch_rotation(p, q):\n"
       "    n = p.shape[0]\n"
       "    H = np.einsum('nli,nlj->nij', p, q)\n"
       "    U, S, Vt = np.linalg.svd(H)\n"
       "    Vt_t = np.transpose(Vt, (0, 2, 1))\n"
       "    U_t = np.transpose(U, (0, 2, 1))\n"
       "    d = np.sign(np.linalg.det(np.einsum('nij,njk->nik', Vt_t, U_t)))\n"
       "    D = np.tile(np.eye(3), (n, 1, 1))\n"
       "    D[:, 2, 2] = d\n"
       "    R = np.einsum('nij,njk,nkl->nil', Vt_t, D, U_t)\n"
       "    return R\n",
       p=_R.randn(4, 8, 3), q=_R.randn(4, 8, 3), _tol=(1e-6, 1e-6)),
    # Multi-dim gather: np.take(a, idx2d, axis=0) -> a.shape[:axis]+idx.shape+...
    _F("take_2d_index_axis0",
       "def take_2d_index_axis0(a, idx):\n"
       "    return np.take(a, idx, axis=0)\n",
       a=_R.randn(9, 3), idx=np.array([[0, 2, 4, 8], [1, 3, 5, 7]]),
       _tol=(1e-12, 1e-12)),
    # Bool-mask reduction over an axis (the Procrustes per-cluster vertex count).
    _F("bool_mask_sum_axis",
       "def bool_mask_sum_axis(c):\n"
       "    mask = c >= 0\n"
       "    return np.maximum(mask.sum(axis=1), 1).astype(np.float64)\n",
       c=np.array([[0, 1, 2, 3, 4, 5, 6, 7], [0, -1, 2, -1, 4, -1, 6, -1]]),
       _tol=(1e-12, 1e-12)),
    # Centroid = row-sum / per-row count (broadcast counts[:, None]).
    _F("masked_centroid",
       "def masked_centroid(p, c):\n"
       "    mask = c >= 0\n"
       "    counts = np.maximum(mask.sum(axis=1), 1)\n"
       "    return p.sum(axis=1) / counts[:, None]\n",
       p=_R.randn(2, 8, 3),
       c=np.array([[0, 1, 2, 3, 4, 5, 6, 7], [0, -1, 2, -1, 4, -1, 6, -1]]),
       _tol=(1e-9, 1e-9)),
    # A SCALAR-tested conditional expression SELECTING between two arrays -- a
    # plain C++ ternary, not np.where's elementwise blend (the IK pole-vector
    # fallback: `pole - p0 if norm(pole) > eps else p1 - p0`).
    _F("ifexp_array_branches",
       "def ifexp_array_branches(a, b, t):\n"
       "    return (a * 2.0 if float(t) > 0.5 else b - 1.0) + a\n",
       a=_R.randn(4), b=_R.randn(4), t=0.75),
    _F("ifexp_array_branches_false",
       "def ifexp_array_branches_false(a, b, t):\n"
       "    return (a * 2.0 if float(t) > 0.5 else b - 1.0) + a\n",
       a=_R.randn(4), b=_R.randn(4), t=0.25),
    _F("ifexp_array_2d",
       "def ifexp_array_2d(m, n, t):\n"
       "    return m @ (n if float(t) < 0.5 else m)\n",
       m=_R.randn(3, 3), n=_R.randn(3, 3), t=0.1),
    # Tuple unpack from an explicit value tuple (`x, y, z = a[0], a[1], a[2]`).
    _F("tuple_unpack_literal",
       "def tuple_unpack_literal(a):\n"
       "    x, y, z = (a[0], a[1], a[2])\n"
       "    return x * 100.0 + y * 10.0 + z\n",
       a=np.array([1.0, 2.0, 3.0])),
    # Simultaneous assignment: every RHS is bound BEFORE any target is written,
    # so a swap really swaps instead of clobbering through.
    _F("tuple_unpack_swap",
       "def tuple_unpack_swap(a, b):\n"
       "    x, y = a, b\n"
       "    x, y = y, x\n"
       "    return x * 10.0 + y\n",
       a=3.0, b=7.0),
    # np.array built from LIVE scalars (the IK cross-product matrix), including
    # the nested-list 2-D form.
    _F("array_literal_from_scalars",
       "def array_literal_from_scalars(a):\n"
       "    x, y, z = (a[0], a[1], a[2])\n"
       "    k = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])\n"
       "    return k @ k\n",
       a=np.array([0.3, -0.5, 0.8])),
    _F("array_literal_mixed_const_live",
       "def array_literal_mixed_const_live(s):\n"
       "    return np.array([1.0, float(s) * 2.0, 3.0])\n",
       s=2.5),

    # ------------------------------------------------------------------
    # SP-6: the ndarray METHOD surface. Every operation appears in BOTH spellings
    # wherever numpy provides both: the claim is not "it lowered" but that
    # a.f(...) and np.f(a, ...) compute the same thing. numpy is the oracle, so
    # the traps are checked automatically -- banker's rounding, ddof=0,
    # first-occurrence ties, NaN ordering, sort's axis=-1 vs cumsum's flatten.
    # ------------------------------------------------------------------
    _F("m_all_any",
       "def m_all_any(a, b):\n"
       "    return np.array([float(a.all()), float(a.any()),\n"
       "                     float(np.all(a)), float(np.any(a)),\n"
       "                     float(b.all()), float(b.any())])\n",
       a=np.array([1.0, 2.0, 3.0]), b=np.array([0.0, 1.0, 0.0])),
    _F("m_all_any_axis",
       "def m_all_any_axis(a):\n"
       "    return a.all(axis=1).astype(np.int64) + np.any(a, axis=1)\n",
       a=np.array([[1.0, 0.0], [1.0, 2.0], [0.0, 0.0]])),
    _F("m_prod",
       "def m_prod(a):\n"
       "    return a.prod() + np.prod(a)\n",
       a=np.array([1.0, 2.0, 3.0, 4.0])),
    _F("m_prod_axis_int",
       "def m_prod_axis_int(a):\n"
       "    return a.prod(axis=1) * np.prod(a, axis=0).sum()\n",
       a=np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int64)),
    _F("m_cumprod_cumsum",
       "def m_cumprod_cumsum(a):\n"
       "    return a.cumprod() + a.cumsum() + np.cumprod(a) + np.cumsum(a)\n",
       a=np.array([1.0, 2.0, 3.0, 4.0])),
    _F("m_cumprod_axis",
       "def m_cumprod_axis(a):\n"
       "    return np.cumprod(a, axis=1) - a.cumprod(axis=1)\n",
       a=np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])),
    # ddof defaults to 0 (POPULATION). If the kernel used the sample form this
    # fixture is off by ~15% -- numpy catches it, no hand-written expectation.
    _F("m_std_var",
       "def m_std_var(a):\n"
       "    return np.array([a.std(), a.var(), np.std(a), np.var(a),\n"
       "                     a.std(ddof=1), np.var(a, ddof=1)])\n",
       a=np.array([1.0, 2.0, 3.0, 4.0])),
    _F("m_std_axis",
       "def m_std_axis(a):\n"
       "    return a.std(axis=1) + np.var(a, axis=0).sum()\n",
       a=np.arange(12.0).reshape(3, 4)),
    _F("m_ptp",
       "def m_ptp(a):\n"
       "    return a.ptp() + np.ptp(a) + a.ptp(axis=1).sum()\n",
       a=np.array([[1.0, 5.0, 3.0], [9.0, 2.0, 7.0]])),
    # Ties resolve to the FIRST occurrence; a >= comparison would answer 2/3.
    _F("m_argmax_argmin_ties",
       "def m_argmax_argmin_ties(a):\n"
       "    return np.array([a.argmax(), a.argmin(),\n"
       "                     np.argmax(a), np.argmin(a)])\n",
       a=np.array([1.0, 3.0, 3.0, 1.0, 2.0])),
    # A NaN BEATS every number in argmax AND argmin -- a plain > loop answers 4
    # and 2 here instead of 1 and 1.
    _F("m_argmax_nan",
       "def m_argmax_nan(a):\n"
       "    return np.array([a.argmax(), a.argmin()])\n",
       a=np.array([3.0, np.nan, 1.0, np.nan, 5.0])),
    _F("m_argmax_axis",
       "def m_argmax_axis(a):\n"
       "    return a.argmax(axis=0) + np.argmin(a, axis=0)\n",
       a=np.array([[1.0, 9.0, 3.0], [4.0, 2.0, 6.0]])),
    # Tie-free input: numpy's default introsort and our stable sort agree
    # exactly. (With ties only kind='stable' is specified -- see the
    # m_argsort_stable_ties reject-free note in the array-method unit tests.)
    _F("m_argsort",
       "def m_argsort(a):\n"
       "    return a.argsort() + np.argsort(a)\n",
       a=np.array([3.0, 1.0, 4.0, 1.5, 9.0, 2.6])),
    _F("m_argsort_nan_last",
       "def m_argsort_nan_last(a):\n"
       "    return np.argsort(a)\n",
       a=np.array([3.0, np.nan, 1.0, 2.0])),
    # np.sort defaults to axis=-1 (each ROW), NOT the flattened array.
    _F("m_sort_default_axis",
       "def m_sort_default_axis(a):\n"
       "    return np.sort(a)\n",
       a=np.array([[3.0, 1.0, 2.0], [9.0, 8.0, 7.0]])),
    _F("m_sort_axis0_and_none",
       "def m_sort_axis0_and_none(a):\n"
       "    return np.sort(a, axis=0).ravel() + np.sort(a, axis=None)\n",
       a=np.array([[3.0, 1.0, 2.0], [9.0, 8.0, 7.0]])),
    _F("m_argsort_axis0",
       "def m_argsort_axis0(a):\n"
       "    return np.argsort(a, axis=0)\n",
       a=np.array([[3.0, 1.0, 2.0], [9.0, 8.0, 7.0]])),
    # a.sort() mutates IN PLACE. `b = a` aliases the same object in Python, so
    # b must come back sorted too -- `a = nd::sort(a)` would fail this.
    _F("m_sort_inplace_alias",
       "def m_sort_inplace_alias(a):\n"
       "    b = a\n"
       "    a.sort()\n"
       "    return b\n",
       a=np.array([3.0, 1.0, 4.0, 1.5, 9.0, 2.6])),
    _F("m_sort_inplace_axis0",
       "def m_sort_inplace_axis0(a):\n"
       "    a.sort(axis=0)\n"
       "    return a\n",
       a=np.array([[3.0, 1.0, 2.0], [9.0, 8.0, 7.0]])),
    # A negative axis must be normalised before it reaches nd::transpose, which
    # indexes axes[i] directly. `-1` is UnaryOp(USub, Constant(1)), not
    # Constant(-1), so the obvious isinstance test misses it entirely.
    _F("m_transpose_negative_axes",
       "def m_transpose_negative_axes(a):\n"
       "    return a.transpose(-1, -2) + np.transpose(a, (-1, -2))\n",
       a=np.arange(6.0).reshape(2, 3)),
    _F("m_squeeze",
       "def m_squeeze(a):\n"
       "    return a.squeeze(0) + np.squeeze(a, 0)\n",
       a=np.arange(6.0).reshape(1, 2, 3)),
    _F("m_swapaxes",
       "def m_swapaxes(a):\n"
       "    return a.swapaxes(0, 1) + np.swapaxes(a, 0, 1)\n",
       a=np.arange(6.0).reshape(2, 3)),
    _F("m_diagonal_trace",
       "def m_diagonal_trace(a):\n"
       "    return (a.diagonal().sum() + np.diagonal(a, 1).sum()\n"
       "            + a.trace() + np.trace(a, -1))\n",
       a=np.arange(9.0).reshape(3, 3)),
    # axis=None FLATTENS first: a (2,2) repeated twice is an 8-vector.
    _F("m_repeat",
       "def m_repeat(a):\n"
       "    return a.repeat(2) + np.repeat(a, 2)\n",
       a=np.array([[1.0, 2.0], [3.0, 4.0]])),
    _F("m_repeat_axis",
       "def m_repeat_axis(a):\n"
       "    return np.repeat(a, 3, axis=0) - a.repeat(3, axis=0)\n",
       a=np.array([[1.0, 2.0], [3.0, 4.0]])),
    # np.compress(cond, a) leads with the MASK; a.compress(cond) with the array.
    _F("m_compress_both_orders",
       "def m_compress_both_orders(a, c):\n"
       "    return np.compress(c, a) + a.compress(c)\n",
       a=np.array([1.0, 2.0, 3.0, 4.0]),
       c=np.array([True, False, True, False])),
    _F("m_compress_axis",
       "def m_compress_axis(a, c):\n"
       "    return np.compress(c, a, axis=0)\n",
       a=np.arange(6.0).reshape(3, 2), c=np.array([True, False, True])),
    # 'left' vs 'right' differ by 2 on this input, so the flag is really tested.
    _F("m_searchsorted",
       "def m_searchsorted(a, v):\n"
       "    return (np.searchsorted(a, v) * 10\n"
       "            + a.searchsorted(v, 'right'))\n",
       a=np.array([1.0, 2.0, 2.0, 3.0]),
       v=np.array([0.0, 2.0, 2.5, 9.0])),
    _F("m_choose",
       "def m_choose(i, x, y):\n"
       "    return i.choose((x, y)) + np.choose(i, (x, y))\n",
       i=np.array([0, 1, 0, 1], dtype=np.int64),
       x=np.array([10.0, 20.0, 30.0, 40.0]),
       y=np.array([-1.0, -2.0, -3.0, -4.0])),
    # Half-to-EVEN. std::round would answer 1/2/3/-1/-2 for these five.
    _F("m_round_banker",
       "def m_round_banker(a):\n"
       "    return a.round() + np.round(a)\n",
       a=np.array([0.5, 1.5, 2.5, -0.5, -1.5, 3.5])),
    # numpy SCALES, rints, and unscales -- which is why round(1.2345,3) is 1.234
    # and round(2.675,2) is 2.68. Rounding "correctly" would disagree with both.
    _F("m_round_decimals",
       "def m_round_decimals(a):\n"
       "    return np.round(a, 3) + a.round(decimals=3)\n",
       a=np.array([1.2345, 2.675, -1.0005, 0.12345])),
    _F("m_round_decimals_2",
       "def m_round_decimals_2(a):\n"
       "    return np.round(a, 2)\n",
       a=np.array([2.675, 1.005, 2.345, -2.675])),
    # Integer arrays take an exact integer path: unscaling by 0.1 in floating
    # point can land on 19.999999999999996 and truncate to 19.
    _F("m_round_int_negative_decimals",
       "def m_round_int_negative_decimals(a):\n"
       "    return np.round(a, -1) + a.round(-1)\n",
       a=np.array([15, 25, 35, -15, -25, 44], dtype=np.int64)),
    _F("m_round_int_noop",
       "def m_round_int_noop(a):\n"
       "    return a.round()\n",
       a=np.array([1, 2, 3], dtype=np.int64)),
    _F("m_take_method",
       "def m_take_method(a, i):\n"
       "    return a.take(i) + np.take(a, i)\n",
       a=np.array([10.0, 20.0, 30.0, 40.0]),
       i=np.array([3, 0, 2], dtype=np.int64)),
    _F("m_copy_free",
       "def m_copy_free(a):\n"
       "    return np.copy(a) + a.copy()\n",
       a=np.array([1.0, 2.0, 3.0])),
    _F("m_conj_real_identity",
       "def m_conj_real_identity(a):\n"
       "    return a.conj() + np.conjugate(a)\n",
       a=np.array([1.0, -2.0, 3.5])),
    _F("m_byteswap_involution",
       "def m_byteswap_involution(a):\n"
       "    return a.byteswap().byteswap()\n",
       a=np.array([1, 256, -7], dtype=np.int64)),
    _F("m_fill",
       "def m_fill(a):\n"
       "    b = a.copy()\n"
       "    b.fill(7.5)\n"
       "    return b + a\n",
       a=np.array([1.0, 2.0, 3.0])),
    _F("m_put_both_spellings",
       "def m_put_both_spellings(a, i):\n"
       "    b = a.copy()\n"
       "    b.put(i, np.array([9.0, 8.0]))\n"
       "    c = a.copy()\n"
       "    np.put(c, i, np.array([9.0, 8.0]))\n"
       "    return b + c\n",
       a=np.array([1.0, 2.0, 3.0, 4.0]),
       i=np.array([0, 3], dtype=np.int64)),
    _F("m_itemset",
       "def m_itemset(a):\n"
       "    b = a.copy()\n"
       "    b.itemset(1, 42.0)\n"
       "    return b\n",
       a=np.array([1.0, 2.0, 3.0])),
    # The method ZERO-fills, the free function REPEATS -- same name, different
    # answers, so both are pinned.
    _F("m_resize_method_zero_fills",
       "def m_resize_method_zero_fills(a):\n"
       "    b = a.copy()\n"
       "    b.resize(6)\n"
       "    return b\n",
       a=np.array([1.0, 2.0, 3.0])),
    _F("m_resize_free_repeats",
       "def m_resize_free_repeats(a):\n"
       "    return np.resize(a, 6)\n",
       a=np.array([1.0, 2.0, 3.0])),
    # setflags has no observable effect on a compiled array; the values must be
    # untouched rather than the statement being rejected.
    _F("m_setflags_noop",
       "def m_setflags_noop(a):\n"
       "    b = a.copy()\n"
       "    b.setflags(write=True)\n"
       "    return b\n",
       a=np.array([1.0, 2.0, 3.0])),
    _F("m_nonzero_method_unpack",
       "def m_nonzero_method_unpack(a):\n"
       "    ys, xs = a.nonzero()\n"
       "    return ys * 10 + xs\n",
       a=np.array([[0.0, 1.0, 0.0], [2.0, 0.0, 3.0]])),
    _F("m_bool_prod_promotes",
       "def m_bool_prod_promotes(a):\n"
       "    return a.prod() + a.sum() + a.cumsum().sum()\n",
       a=np.array([True, True, False, True])),
    # A chain in one expression, mixing spellings, on a NON-contiguous operand
    # (the transpose view) -- the strided paths in each kernel.
    _F("m_chain_on_strided_view",
       "def m_chain_on_strided_view(a):\n"
       "    t = a.transpose()\n"
       "    return np.sort(t, axis=1).cumsum(axis=0) + t.round(1)\n",
       a=(np.arange(12.0).reshape(3, 4) * 0.37)),

    # ---- SP-7: scipy.spatial.cKDTree ------------------------------------
    # True parity against REAL scipy, but only on TIE-FREE data: where two points
    # are exactly equidistant scipy's index is an artifact of its tree layout
    # while ours is the documented lowest-index rule. That divergence is pinned in
    # _tests/test_kdtree.py rather than hidden under a loose tolerance here; the
    # irrational coordinates below make an exact tie impossible.
    #
    # Distances carry a tolerance because scipy's own k=1 distance is not
    # bit-identical to sqrt(sum of squares) either (measured: 43/400 differ, max
    # 2.22e-16). Indices are compared EXACTLY.
    _F("kd_query_k1_dist",
       "def kd_query_k1_dist(p, q):\n"
       "    from scipy.spatial import cKDTree\n"
       "    t = cKDTree(p)\n"
       "    d, i = t.query(q)\n"
       "    return d\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3),
       q=(np.arange(24.0).reshape(8, 3) * np.e % 6.1),
       _tol=(1e-12, 1e-12)),
    _F("kd_query_k1_idx",
       "def kd_query_k1_idx(p, q):\n"
       "    from scipy.spatial import cKDTree\n"
       "    t = cKDTree(p)\n"
       "    d, i = t.query(q)\n"
       "    return i.astype(np.float64)\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3),
       q=(np.arange(24.0).reshape(8, 3) * np.e % 6.1)),
    _F("kd_query_k3",
       "def kd_query_k3(p, q):\n"
       "    from scipy.spatial import cKDTree\n"
       "    t = cKDTree(p)\n"
       "    d, i = t.query(q, 3)\n"
       "    return d + i.astype(np.float64) * 0.001\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3),
       q=(np.arange(24.0).reshape(8, 3) * np.e % 6.1),
       _tol=(1e-12, 1e-12)),
    # leafsize changes the tree SHAPE only. Because the result is defined by the
    # (distance, index) rule rather than by traversal, both trees must return
    # the identical answer -- so this whole expression is exactly zero.
    _F("kd_query_leafsize_cannot_change_the_answer",
       "def kd_query_leafsize_cannot_change_the_answer(p, q):\n"
       "    from scipy.spatial import cKDTree\n"
       "    t1 = cKDTree(p, leafsize=1)\n"
       "    t2 = cKDTree(p, leafsize=64)\n"
       "    a, ia = t1.query(q, 2)\n"
       "    b, ib = t2.query(q, 2)\n"
       "    return a - b + (ia - ib).astype(np.float64)\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3),
       q=(np.arange(24.0).reshape(8, 3) * np.e % 6.1),
       _tol=(1e-12, 1e-12)),
    # output_type='ndarray' is REQUIRED, not optional: scipy's default is a
    # Python set, which has no lowered carrier and would make the two sides
    # return different types.
    _F("kd_query_pairs",
       "def kd_query_pairs(p):\n"
       "    from scipy.spatial import cKDTree\n"
       "    t = cKDTree(p)\n"
       "    pr = t.query_pairs(3.0, output_type='ndarray')\n"
       "    return pr.astype(np.float64).sum(axis=0)\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3)),

    # The CHAINED spelling -- `cKDTree(p).query(q)`, the one scipy's own docs
    # use. It has no name to bind, so the tree becomes a temporary. Requiring a
    # named local instead is what sent the real closest-point node to the AI
    # porter, which replaced the tree with an O(N*M) scan.
    _F("kd_query_chained_temporary_idx",
       "def kd_query_chained_temporary_idx(p, q):\n"
       "    from scipy.spatial import cKDTree\n"
       "    d, i = cKDTree(p).query(q, k=1)\n"
       "    return i.astype(np.float64)\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3),
       q=(np.arange(24.0).reshape(8, 3) * np.e % 6.1)),
    # Chained and bound must be the SAME tree, so this is exactly zero -- a
    # tolerance-free invariant rather than a re-measurement of scipy.
    _F("kd_query_chained_equals_bound",
       "def kd_query_chained_equals_bound(p, q):\n"
       "    from scipy.spatial import cKDTree\n"
       "    t = cKDTree(p)\n"
       "    a, ia = t.query(q, 2)\n"
       "    b, ib = cKDTree(p).query(q, 2)\n"
       "    return a - b + (ia - ib).astype(np.float64)\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3),
       q=(np.arange(24.0).reshape(8, 3) * np.e % 6.1)),
    # The whole closest-point node in one line: query, then GATHER the winning
    # rows with p[i]. Both halves had to be lowered for this to compile at all.
    _F("kd_query_then_gather_rows",
       "def kd_query_then_gather_rows(p, q):\n"
       "    from scipy.spatial import cKDTree\n"
       "    d, i = cKDTree(p).query(q, k=1)\n"
       "    return p[i]\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3),
       q=(np.arange(24.0).reshape(8, 3) * np.e % 6.1)),
    # (No parity fixture for the chained query_ball_point: scipy returns ragged
    # lists there while the lowering returns a CSR (starts, items) pair, so the
    # unpack is not valid Python for the oracle to run. Same reason the BOUND
    # form has none. Its chained spelling is covered in nd_lower_test.)
    _F("kd_query_pairs_chained",
       "def kd_query_pairs_chained(p):\n"
       "    from scipy.spatial import cKDTree\n"
       "    pr = cKDTree(p).query_pairs(3.0, output_type='ndarray')\n"
       "    return pr.astype(np.float64).sum(axis=0)\n",
       p=(np.arange(60.0).reshape(20, 3) * np.pi % 7.3)),

    # ---- fancy indexing: a[idx] with an integer ARRAY (gather on axis 0) ----
    # numpy is the oracle. nd::take's axis form is the same operation, including
    # the negative-index wrap, so these are bit-exact.
    _F("gather_rows_int_index",
       "def gather_rows_int_index(a, w):\n"
       "    i = (np.abs(w[:, 0]) * 5.0).astype(np.int64)\n"
       "    return a[i]\n",
       a=(np.arange(24.0).reshape(6, 4)), w=_R.randn(7, 2)),
    _F("gather_rows_negative_index_wraps",
       "def gather_rows_negative_index_wraps(a):\n"
       "    i = np.array([-1, -6, 0, 3, -3])\n"
       "    return a[i]\n",
       a=(np.arange(24.0).reshape(6, 4))),
    _F("gather_rows_2d_index_block",
       "def gather_rows_2d_index_block(a):\n"
       "    i = np.array([[0, 2], [5, 1], [3, 3]])\n"
       "    return a[i].sum(axis=2)\n",
       a=(np.arange(24.0).reshape(6, 4))),
    _F("gather_rank1_by_rank1",
       "def gather_rank1_by_rank1(a):\n"
       "    i = np.array([4, 0, 4, 2])\n"
       "    return a[i] * 2.0\n",
       a=(np.arange(5.0) * 1.7)),

    # ---- SP-7: numpy gap-fill -------------------------------------------
    # numpy is the oracle here. No tolerance is set unless a measurement
    # forced one, so these are bit-exact comparisons by default.
    _F("gap_trig_and_conversions",
       "def gap_trig_and_conversions(a):\n"
       "    return np.tanh(a) + np.radians(a) + np.degrees(a) "
       "+ np.deg2rad(a) + np.rad2deg(a)\n",
       a=_R.randn(6, 4)),
    _F("gap_negative_keeps_int_dtype",
       "def gap_negative_keeps_int_dtype(a):\n"
       "    i = (a * 10.0).astype(np.int64)\n"
       "    return np.negative(i).astype(np.float64)\n",
       a=_R.randn(5, 3)),
    _F("gap_add_subtract_aliases",
       "def gap_add_subtract_aliases(a, b):\n"
       "    return np.subtract(np.add(a, b), np.multiply(a, b))\n",
       a=_R.randn(4, 5), b=_R.randn(4, 5)),
    _F("gap_nan_predicates",
       "def gap_nan_predicates(a):\n"
       "    b = a / 0.0\n"
       "    return (np.isnan(b).astype(np.float64) * 4.0\n"
       "            + np.isinf(b).astype(np.float64) * 2.0\n"
       "            + np.isfinite(b).astype(np.float64))\n",
       a=np.array([[-1.0, 0.0, 1.0], [2.0, -0.0, 3.0]])),
    _F("gap_nan_to_num_defaults",
       "def gap_nan_to_num_defaults(a):\n"
       "    b = a / 0.0\n"
       "    return np.nan_to_num(b) * 1e-300\n",
       a=np.array([[-1.0, 0.0, 1.0], [2.0, -0.0, 3.0]])),
    _F("gap_nan_to_num_explicit",
       "def gap_nan_to_num_explicit(a):\n"
       "    b = a / 0.0\n"
       "    return np.nan_to_num(b, nan=-1.0, posinf=9.0, neginf=-9.0)\n",
       a=np.array([[-1.0, 0.0, 1.0], [2.0, -0.0, 3.0]])),
    # isclose broadcasts through ew_binary; allclose/array_equal fold to a
    # scalar bool, so they are lifted into the array to be comparable.
    _F("gap_isclose_broadcast",
       "def gap_isclose_broadcast(a, b):\n"
       "    return np.isclose(a, b).astype(np.float64)\n",
       a=np.array([[1.0], [2.0], [3.0]]),
       b=np.array([1.0, 2.0000000001])),
    _F("gap_isclose_tolerances",
       "def gap_isclose_tolerances(a):\n"
       "    b = a + 1e-6\n"
       "    return (np.isclose(a, b).astype(np.float64)\n"
       "            + np.isclose(a, b, rtol=1e-12, atol=1e-14).astype(np.float64)\n"
       "            + float(np.allclose(a, b)) + float(np.array_equal(a, b)))\n",
       a=_R.randn(4, 3)),
    _F("gap_array_equal_true",
       "def gap_array_equal_true(a):\n"
       "    return a * 0.0 + float(np.array_equal(a, a)) "
       "+ float(np.allclose(a, a))\n",
       a=_R.randn(3, 3)),
    # sets: unique flattens, isin keeps a's shape, bincount is int64
    _F("gap_unique_flattens",
       "def gap_unique_flattens(a):\n"
       "    i = (a * 3.0).astype(np.int64)\n"
       "    return np.unique(i).astype(np.float64)\n",
       a=_R.randn(5, 4)),
    _F("gap_setdiff1d",
       "def gap_setdiff1d(a, b):\n"
       "    i = (a * 4.0).astype(np.int64)\n"
       "    j = (b * 4.0).astype(np.int64)\n"
       "    return np.setdiff1d(i, j).astype(np.float64)\n",
       a=_R.randn(20), b=_R.randn(9)),
    _F("gap_isin_keeps_shape",
       "def gap_isin_keeps_shape(a, b):\n"
       "    i = (a * 3.0).astype(np.int64)\n"
       "    j = (b * 3.0).astype(np.int64)\n"
       "    return np.isin(i, j).astype(np.float64)\n",
       a=_R.randn(4, 5), b=_R.randn(7)),
    _F("gap_bincount",
       "def gap_bincount(a):\n"
       "    i = np.abs(a * 5.0).astype(np.int64)\n"
       "    return np.bincount(i).astype(np.float64)\n",
       a=_R.randn(30)),
    _F("gap_bincount_minlength",
       "def gap_bincount_minlength(a):\n"
       "    i = np.abs(a * 2.0).astype(np.int64)\n"
       "    return np.bincount(i, minlength=24).astype(np.float64)\n",
       a=_R.randn(15)),
    # layout
    _F("gap_ascontiguous_and_asanyarray",
       "def gap_ascontiguous_and_asanyarray(a):\n"
       "    t = np.ascontiguousarray(a.T)\n"
       "    return t + np.asanyarray(t)\n",
       a=_R.randn(4, 6)),
    _F("gap_atleast_1d",
       "def gap_atleast_1d(a):\n"
       "    return np.atleast_1d(a) * 2.0\n",
       a=_R.randn(5)),
    _F("gap_broadcast_to",
       "def gap_broadcast_to(a):\n"
       "    return np.broadcast_to(a, (4, 3)) * 1.5\n",
       a=_R.randn(3)),
    _F("gap_flip_family",
       "def gap_flip_family(a):\n"
       "    return (np.flipud(a) + np.fliplr(a) * 2.0 "
       "+ np.flip(a, 1) * 4.0 + np.flip(a, axis=0) * 8.0)\n",
       a=_R.randn(5, 6)),
    _F("gap_diff_orders_and_axes",
       "def gap_diff_orders_and_axes(a):\n"
       "    return (np.diff(a).sum(axis=1) + np.diff(a, 2).sum(axis=1)\n"
       "            + np.diff(a, 1, 0).sum(axis=0))\n",
       a=_R.randn(6, 6)),
    _F("gap_pad_scalar_width",
       "def gap_pad_scalar_width(a):\n"
       "    return np.pad(a, 2)\n",
       a=_R.randn(4, 3)),
    _F("gap_pad_per_axis_and_value",
       "def gap_pad_per_axis_and_value(a):\n"
       "    return np.pad(a, ((1, 2), (3, 0)), constant_values=-7.5)\n",
       a=_R.randn(4, 3)),
    _F("gap_pad_1d_pair",
       "def gap_pad_1d_pair(a):\n"
       "    return np.pad(a, (2, 3), mode='constant')\n",
       a=_R.randn(7)),
    # numeric
    _F("gap_outer_flattens_both",
       "def gap_outer_flattens_both(a, b):\n"
       "    return np.outer(a, b) + np.outer(a.reshape(2, 3), b)\n",
       a=_R.randn(6), b=_R.randn(4)),
    _F("gap_interp",
       "def gap_interp(x):\n"
       "    xp = np.linspace(0.0, 1.0, 11)\n"
       "    fp = xp * xp * 3.0 - 1.0\n"
       "    return np.interp(x, xp, fp)\n",
       x=(np.arange(40.0) * 0.031 - 0.2)),
    _F("gap_nanmax_nanmin",
       "def gap_nanmax_nanmin(a):\n"
       "    b = a * 1.0\n"
       "    b[0] = np.nan\n"
       "    return a * 0.0 + np.nanmax(b) - np.nanmin(b)\n",
       a=_R.randn(9)),
    _F("gap_meshgrid_xy",
       "def gap_meshgrid_xy(x, y):\n"
       "    X, Y = np.meshgrid(x, y)\n"
       "    return X * 10.0 + Y\n",
       x=_R.randn(5), y=_R.randn(3)),
    _F("gap_fill_diagonal",
       "def gap_fill_diagonal(a):\n"
       "    b = a * 1.0\n"
       "    np.fill_diagonal(b, -3.25)\n"
       "    return b\n",
       a=_R.randn(5, 5)),
    _F("gap_fill_diagonal_nonsquare",
       "def gap_fill_diagonal_nonsquare(a):\n"
       "    b = a * 1.0\n"
       "    np.fill_diagonal(b, 0.0)\n"
       "    return b\n",
       a=_R.randn(3, 7)),
    # The whole reason np.add.at exists: repeated indices must ACCUMULATE,
    # which b[idx] += v does not do.
    _F("gap_add_at_accumulates",
       "def gap_add_at_accumulates(a, v):\n"
       "    b = a * 0.0\n"
       "    idx = np.array([0, 2, 0, 1, 2, 0])\n"
       "    np.add.at(b, idx, v)\n"
       "    return b\n",
       a=_R.randn(4), v=_R.randn(6)),
    _F("gap_add_at_rows",
       "def gap_add_at_rows(a, v):\n"
       "    b = a * 0.0\n"
       "    idx = np.array([1, 1, 0])\n"
       "    np.add.at(b, idx, v)\n"
       "    return b\n",
       a=_R.randn(3, 4), v=_R.randn(3, 4)),
    # append/delete/insert: with axis omitted numpy FLATTENS and returns 1-D,
    # which is a different shape than axis=0. Both branches are pinned.
    _F("gap_append_flattens_without_axis",
       "def gap_append_flattens_without_axis(a, b):\n"
       "    return np.append(a, b)\n",
       a=_R.randn(3, 4), b=_R.randn(2, 5)),
    _F("gap_append_axis0",
       "def gap_append_axis0(a, b):\n"
       "    return np.append(a, b, axis=0)\n",
       a=_R.randn(3, 4), b=_R.randn(2, 4)),
    _F("gap_delete_flat",
       "def gap_delete_flat(a):\n"
       "    return np.delete(a, np.array([0, 3, 5]))\n",
       a=_R.randn(4, 3)),
    _F("gap_delete_axis1",
       "def gap_delete_axis1(a):\n"
       "    return np.delete(a, np.array([1, 3]), axis=1)\n",
       a=_R.randn(4, 5)),
    _F("gap_delete_scalar_index",
       "def gap_delete_scalar_index(a):\n"
       "    return np.delete(a, 2, axis=0)\n",
       a=_R.randn(5, 3)),
    # The subtle one: with a REPEATED index numpy ranks stably, shifts each
    # index by its rank, and keeps the caller's value order -- so [1,1] puts
    # both values at slots 1 and 2 in the order given.
    _F("gap_insert_repeated_index",
       "def gap_insert_repeated_index(a, v):\n"
       "    return np.insert(a, np.array([1, 1, 3]), v)\n",
       a=_R.randn(6), v=_R.randn(3)),
    _F("gap_insert_axis0_rows",
       "def gap_insert_axis0_rows(a, v):\n"
       "    return np.insert(a, np.array([0, 2]), v, axis=0)\n",
       a=_R.randn(4, 3), v=_R.randn(2, 3)),
    _F("gap_insert_scalar_value",
       "def gap_insert_scalar_value(a):\n"
       "    return np.insert(a, np.array([1]), 9.5, axis=1)\n",
       a=_R.randn(3, 4)),
    _F("gap_insert_rank3",
       "def gap_insert_rank3(a, v):\n"
       "    return np.insert(a, np.array([1]), v, axis=1)\n",
       a=_R.randn(2, 3, 4), v=_R.randn(2, 4)),
    _F("gap_block_2x2",
       "def gap_block_2x2(a, b, c, d):\n"
       "    return np.block([[a, b], [c, d]])\n",
       a=_R.randn(2, 3), b=_R.randn(2, 4),
       c=_R.randn(5, 3), d=_R.randn(5, 4)),
    _F("gap_block_single_row",
       "def gap_block_single_row(a, b):\n"
       "    return np.block([a, b])\n",
       a=_R.randn(3, 2), b=_R.randn(3, 5)),
    # ---- ITEM-18 gap-fill ------------------------------------------------
    # Every fixture below whose result is pure data movement (or an int64
    # expression compared with array_equal) is gated at _tol=(0.0, 0.0) -- exact
    # equality, not a tolerance.
    #
    # `raise` in a guard that does NOT fire: the values must be untouched. The
    # firing case has no numpy value to compare against, so parity here is
    # exactly "the guard costs nothing".
    _F("gap_raise_guard_not_taken",
       "def gap_raise_guard_not_taken(a):\n"
       "    if a.shape[0] < 1:\n"
       "        raise ValueError('empty input')\n"
       "    return a * 2.0\n",
       a=_R.randn(6), _tol=(0.0, 0.0)),
    # `x is None` is decided at COMPILE time, so the fixture only passes if the
    # branch numpy takes is the branch the C++ keeps -- a flipped fold returns
    # a * 3.0 and mismatches every element.
    _F("gap_none_is_taken",
       "def gap_none_is_taken(a):\n"
       "    src = None\n"
       "    if src is None:\n"
       "        return a * 2.0\n"
       "    return a * 3.0\n",
       a=_R.randn(5), _tol=(0.0, 0.0)),
    _F("gap_none_is_not_taken",
       "def gap_none_is_not_taken(a):\n"
       "    if a is not None:\n"
       "        return a * 2.0\n"
       "    return a * 3.0\n",
       a=_R.randn(5), _tol=(0.0, 0.0)),
    _F("gap_none_is_not_on_none",
       "def gap_none_is_not_on_none(a):\n"
       "    src = None\n"
       "    if src is not None:\n"
       "        return a * 3.0\n"
       "    return a * 2.0\n",
       a=_R.randn(5), _tol=(0.0, 0.0)),
    # meshgrid: the decade weights make ANY axis permutation a value mismatch
    # and the unequal lengths make it a SHAPE mismatch too. int64 inputs keep
    # the comparison exact (array_equal) with no floating point in the mix.
    _F("gap_meshgrid_ij_2_int",
       "def gap_meshgrid_ij_2_int(x, y):\n"
       "    X, Y = np.meshgrid(x, y, indexing='ij')\n"
       "    return X * 10 + Y\n",
       x=np.array([1, 2, 3, 4, 5], dtype=np.int64),
       y=np.array([6, 7, 8], dtype=np.int64)),
    _F("gap_meshgrid_ij_3_int",
       "def gap_meshgrid_ij_3_int(x, y, z):\n"
       "    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')\n"
       "    return X * 100 + Y * 10 + Z\n",
       x=np.array([1, 2], dtype=np.int64),
       y=np.array([3, 4, 5], dtype=np.int64),
       z=np.array([6, 7, 8, 9], dtype=np.int64)),
    _F("gap_meshgrid_xy_3_int",
       "def gap_meshgrid_xy_3_int(x, y, z):\n"
       "    X, Y, Z = np.meshgrid(x, y, z)\n"
       "    return X * 100 + Y * 10 + Z\n",
       x=np.array([1, 2], dtype=np.int64),
       y=np.array([3, 4, 5], dtype=np.int64),
       z=np.array([6, 7, 8, 9], dtype=np.int64)),
    # ...and the double path, one grid at a time so the comparison stays a pure
    # data movement (exact) rather than a multiply-add clang may contract.
    _F("gap_meshgrid_ij_2_x",
       "def gap_meshgrid_ij_2_x(x, y):\n"
       "    X, Y = np.meshgrid(x, y, indexing='ij')\n"
       "    return X\n",
       x=_R.randn(5), y=_R.randn(3), _tol=(0.0, 0.0)),
    _F("gap_meshgrid_ij_2_y",
       "def gap_meshgrid_ij_2_y(x, y):\n"
       "    X, Y = np.meshgrid(x, y, indexing='ij')\n"
       "    return Y\n",
       x=_R.randn(5), y=_R.randn(3), _tol=(0.0, 0.0)),
    _F("gap_meshgrid_ij_3_z",
       "def gap_meshgrid_ij_3_z(x, y, z):\n"
       "    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')\n"
       "    return Z\n",
       x=_R.randn(3), y=_R.randn(4), z=_R.randn(5), _tol=(0.0, 0.0)),
    _F("gap_meshgrid_xy_3_y",
       "def gap_meshgrid_xy_3_y(x, y, z):\n"
       "    X, Y, Z = np.meshgrid(x, y, z)\n"
       "    return Y\n",
       x=_R.randn(3), y=_R.randn(4), z=_R.randn(5), _tol=(0.0, 0.0)),
    # np.unique(return_index=True): the INDEX side is the contract. Every value
    # below repeats, so a non-stable sort picks a later occurrence and the
    # int64 comparison (exact, not tolerance) fails.
    _F("gap_unique_return_index_values",
       "def gap_unique_return_index_values(a):\n"
       "    u, i = np.unique(a, return_index=True)\n"
       "    return u\n",
       a=np.array([3.0, 1.0, 3.0, 2.0, 1.0, 3.0, 2.0, 1.0]), _tol=(0.0, 0.0)),
    _F("gap_unique_return_index_indices",
       "def gap_unique_return_index_indices(a):\n"
       "    u, i = np.unique(a, return_index=True)\n"
       "    return i\n",
       a=np.array([3.0, 1.0, 3.0, 2.0, 1.0, 3.0, 2.0, 1.0])),
    _F("gap_unique_return_index_int",
       "def gap_unique_return_index_int(a):\n"
       "    u, i = np.unique(a, return_index=True)\n"
       "    return i\n",
       a=np.array([5, 5, 4, 7, 4, 5, 7, 7, 4, 9], dtype=np.int64)),
    # rank-2 input: numpy flattens for unique, so the indices are into the
    # C-order RAVEL, not into any row.
    _F("gap_unique_return_index_2d",
       "def gap_unique_return_index_2d(a):\n"
       "    u, i = np.unique(a, return_index=True)\n"
       "    return i\n",
       a=np.array([[2, 1, 2], [3, 1, 3], [1, 2, 3]], dtype=np.int64)),
    # The indices must actually re-select the values they name.
    _F("gap_unique_return_index_gather",
       "def gap_unique_return_index_gather(a):\n"
       "    u, i = np.unique(a, return_index=True)\n"
       "    return a[i] - u\n",
       a=np.array([3.0, 1.0, 3.0, 2.0, 1.0, 3.0, 2.0, 1.0]), _tol=(0.0, 0.0)),
    # ---- python builtin min()/max(): CPython's NaN asymmetry --------------
    # CPython's two-arg max(a, b) keeps the FIRST operand unless the second
    # compares greater -- `b if b > a else a` -- and min() is its mirror. A NaN
    # never compares greater/less, so max(nan, 1.0) is nan while max(1.0, nan)
    # is 1.0. This is NOT np.maximum (which propagates NaN from either side),
    # so these four cases pin BOTH operand positions for BOTH builtins.
    # Inputs are literals: nothing here draws from _R, so the seeded fixture
    # stream above is untouched.
    _F("builtin_max_nan_left",
       "def builtin_max_nan_left(a, b):\n"
       "    return max(a, b)\n",
       a=float("nan"), b=1.0),
    _F("builtin_max_nan_right",
       "def builtin_max_nan_right(a, b):\n"
       "    return max(a, b)\n",
       a=1.0, b=float("nan")),
    _F("builtin_min_nan_left",
       "def builtin_min_nan_left(a, b):\n"
       "    return min(a, b)\n",
       a=float("nan"), b=1.0),
    _F("builtin_min_nan_right",
       "def builtin_min_nan_right(a, b):\n"
       "    return min(a, b)\n",
       a=1.0, b=float("nan")),
    # Ordinary (non-NaN) operands, both orderings + the int path: the NaN fix
    # reorders the emitted ternary's operands, so these guard that finite and
    # integer results did not move with it.
    _F("builtin_maxmin_ordinary",
       "def builtin_maxmin_ordinary(a, b):\n"
       "    return max(a, b) * 10.0 + min(a, b) + max(b, a) - min(b, a)\n",
       a=3.5, b=-2.25),
    _F("builtin_maxmin_int",
       "def builtin_maxmin_int(a, b):\n"
       "    return max(a, b) - min(a, b)\n",
       a=17, b=5),
    # ---- rank-0 (item) operands coerce to scalars -------------------------
    # `a[i]` and a whole-array reduction are rank-0 arrays, not scalars. Every
    # consumer here goes through _cast_scalar, which already accepts rank-0 --
    # which is why the `float(...)`-wrapped spelling has always worked. These
    # pin the unwrapped spelling for min()/max() and for math.*.
    _F("builtin_maxmin_rank0_operands",
       "def builtin_maxmin_rank0_operands(a, b):\n"
       "    return max(a[0], b) - min(a[1], b) + max(a.sum(), b)\n",
       a=np.array([3.0, -2.0, 5.0]), b=1.0),
    _F("math_of_rank0_operands",
       "def math_of_rank0_operands(a):\n"
       "    return math.sqrt(a[0]) + math.sin(a[1]) + math.fabs(a.sum())\n",
       a=np.array([4.0, 0.5, -2.0])),
]


# --------------------------------------------------------------------------
# reject fixtures: (name, source, arg_types, expect_substring)
# --------------------------------------------------------------------------
REJECTS = [
    ("list_comprehension",
     "def f(a):\n    return np.array([x for x in a])\n",
     {"a": array_t("double", 1)}, ""),
    ("dict_literal",
     "def f(a):\n    d = {'k': a}\n    return d['k']\n",
     {"a": array_t("double", 1)}, ""),
    ("fstring",
     "def f(a):\n    s = f'{a}'\n    return a\n",
     {"a": array_t("double", 1)}, ""),
    ("svd_bare",  # SVD must be tuple-unpacked -> the bare-call form rejects
     "def f(a):\n    return np.linalg.svd(a)\n",
     {"a": array_t("double", 2)}, "tuple-unpack"),
    ("einsum_implicit",  # implicit (no '->') einsum is rejected
     "def f(a, b):\n    return np.einsum('ij,jk', a, b)\n",
     {"a": array_t("double", 2), "b": array_t("double", 2)}, "explicit"),
    # A SINGLE (N,N) solve now lowers to nd::solve (see the solve_* parity
    # cases above). A BATCHED (...,N,N) one still rejects -- nd::solve factors
    # one matrix, and quietly solving only the first block would be wrong.
    ("linalg_solve_batched_reject",
     "def f(a, b):\n    return np.linalg.solve(a, b)\n",
     {"a": array_t("double", 3), "b": array_t("double", 2)}, "BATCHED"),
    # The right-hand side has to be a vector or a matrix; rank 3 is neither.
    ("linalg_solve_bad_rhs_reject",
     "def f(a, b):\n    return np.linalg.solve(a, b)\n",
     {"a": array_t("double", 2), "b": array_t("double", 3)}, "right-hand side"),
    # pinv needs a GENERAL svd; nd::svd is 3x3-only, so there is nothing
    # deterministic to build it on and it must keep routing to the porter.
    ("linalg_pinv_reject",
     "def f(a):\n    return np.linalg.pinv(a)\n",
     {"a": array_t("double", 2)}, "porter"),
    # ---- SP-7 gap-fill guards ------------------------------------------
    # Each of these is an option whose semantics DIFFER from the lowered
    # default, so defaulting it silently would change results.
    ("pad_nonconstant_mode",
     "def f(a):\n    return np.pad(a, 1, mode='reflect')\n",
     {"a": array_t("double", 2)}, "constant"),
    # 'ij' now lowers (see gap_meshgrid_ij_*); a 4-input grid and a mismatched
    # unpack still do not.
    ("meshgrid_four_inputs",
     "def f(x, y, z, w):\n    A, B, C, D = np.meshgrid(x, y, z, w)\n    return A\n",
     {"x": array_t("double", 1), "y": array_t("double", 1),
      "z": array_t("double", 1), "w": array_t("double", 1)}, "2- and 3-input"),
    ("meshgrid_unpack_arity",
     "def f(x, y, z):\n    X, Y = np.meshgrid(x, y, z, indexing='ij')\n    return X\n",
     {"x": array_t("double", 1), "y": array_t("double", 1),
      "z": array_t("double", 1)}, "one grid per input"),
    ("meshgrid_indexing_must_be_literal",
     "def f(x, y):\n    m = 'ij'\n"
     "    X, Y = np.meshgrid(x, y, indexing=m)\n    return X\n",
     {"x": array_t("double", 1), "y": array_t("double", 1)}, "literal"),
    ("meshgrid_must_unpack",
     "def f(x, y):\n    return np.meshgrid(x, y)\n",
     {"x": array_t("double", 1), "y": array_t("double", 1)}, "tuple-unpack"),
    ("flip_needs_axis",   # the all-axes form is a different operation
     "def f(a):\n    return np.flip(a)\n",
     {"a": array_t("double", 2)}, "axis"),
    ("fill_diagonal_is_not_an_expression",
     "def f(a):\n    return np.fill_diagonal(a, 0.0)\n",
     {"a": array_t("double", 2)}, "statement"),
    ("nanmax_axis_not_lowered",
     "def f(a):\n    return a * 0.0 + np.nanmax(a, axis=0)\n",
     {"a": array_t("double", 2)}, "axis"),
    ("unique_return_counts",
     "def f(a):\n    u, c = np.unique(a, return_counts=True)\n    return u\n",
     {"a": array_t("double", 1)}, "not lowered"),
    ("interp_left_right",
     "def f(x, xp, fp):\n    return np.interp(x, xp, fp, left=0.0)\n",
     {"x": array_t("double", 1), "xp": array_t("double", 1),
      "fp": array_t("double", 1)}, "not lowered"),
    ("bincount_weights",
     "def f(a, w):\n    i = a.astype(np.int64)\n"
     "    return np.bincount(i, weights=w).astype(np.float64)\n",
     {"a": array_t("double", 1), "w": array_t("double", 1)}, "weights"),
    ("add_at_needs_a_writable_local",
     "def f(a, v):\n    idx = np.array([0, 1])\n"
     "    np.add.at(a * 2.0, idx, v)\n    return a\n",
     {"a": array_t("double", 1), "v": array_t("double", 1)}, "in place"),
    ("for_over_array",
     "def f(a):\n    s = 0.0\n    for x in a:\n        s = s + x\n    return s\n",
     {"a": array_t("double", 1)}, "range"),
    ("enumerate_reject",
     "def f(a):\n    s = 0.0\n    for i, x in enumerate(a):\n        s = s + x\n    return s\n",
     {"a": array_t("double", 1)}, "range"),
    ("type_conflict",
     "def f(a):\n    x = 1.0\n    x = a\n    return x\n",
     {"a": array_t("double", 1)}, "different C++ type"),
    # An ARRAY test on a conditional expression is still ambiguous -- a ternary
    # cannot express an elementwise blend, so np.where stays mandatory.
    ("ifexp_array_test",
     "def f(a, b):\n    return a if a > b else b\n",
     {"a": array_t("double", 1), "b": array_t("double", 1)},
     "boolean condition"),
    # Branch ranks differ -> no single lattice entry (numpy returns the branch
    # object unchanged rather than broadcasting).
    ("ifexp_rank_mismatch",
     "def f(m, v, t):\n    return m if float(t) > 0.5 else v\n",
     {"m": array_t("double", 2), "v": array_t("double", 1),
      "t": scalar_t("double")}, "array ranks"),
    ("tuple_unpack_arity",
     "def f(a):\n    x, y = (a[0], a[1], a[2])\n    return x + y\n",
     {"a": array_t("double", 1)}, "arity mismatch"),
    # An array element inside an array literal has no scalar slot to sit in.
    ("array_literal_array_element",
     "def f(a):\n    return np.array([a, a])\n",
     {"a": array_t("double", 1)}, "np.stack"),
    # ---- ITEM-18 gap-fill guards ----------------------------------------
    # `raise` lowers ONLY with a literal message. A computed one would have to
    # be built at runtime and there is nowhere to build it; a bare re-raise has
    # no exception to re-raise.
    ("raise_bare_reraise",
     "def f(a):\n    raise\n",
     {"a": array_t("double", 1)}, "re-raise"),
    ("raise_formatted_message",
     "def f(a):\n    raise ValueError('bad %d' % 3)\n",
     {"a": array_t("double", 1)}, "literal string"),
    ("raise_from_cause",
     "def f(a):\n    raise ValueError('x') from None\n",
     {"a": array_t("double", 1)}, "from"),
    ("raise_non_literal_exception",
     "def f(a):\n    raise a\n",
     {"a": array_t("double", 1)}, "raise <Exception>"),
    # None binds a NAME, not a value: only an identity test can read it, and the
    # binding cannot change type in either direction.
    ("none_used_as_a_value",
     "def f(a):\n    x = None\n    return a + x\n",
     {"a": array_t("double", 1)}, "no compiled value"),
    ("none_rebound_to_a_value",
     "def f(a):\n    x = None\n    x = a\n    return x\n",
     {"a": array_t("double", 1)}, "bound to None"),
    ("value_rebound_to_none",
     "def f(a):\n    x = a * 2.0\n    x = None\n    return a\n",
     {"a": array_t("double", 1)}, "reassigned to None"),
    # `== None` is an equality, not an identity test, so it is NOT folded.
    ("none_equality_not_folded",
     "def f(a):\n    x = None\n    if x == None:\n        return a\n    return a\n",
     {"a": array_t("double", 1)}, ""),
    # unique: only return_index has a lowering; the others each need their own
    # extra array.
    ("unique_return_inverse",
     "def f(a):\n    u, v = np.unique(a, return_inverse=True)\n    return u\n",
     {"a": array_t("double", 1)}, "not lowered"),
    ("unique_return_index_must_be_literal_true",
     "def f(a):\n    u, i = np.unique(a, return_index=False)\n    return u\n",
     {"a": array_t("double", 1)}, "return_index=True"),
    ("unique_return_index_unpack_arity",
     "def f(a):\n    u, i, c = np.unique(a, return_index=True)\n    return u\n",
     {"a": array_t("double", 1)}, "values, indices"),
    # A rank-0 operand coerces (see builtin_maxmin_rank0_operands /
    # math_of_rank0_operands above); a REAL array must still route to the
    # elementwise numpy spelling rather than silently taking .item().
    ("builtin_min_of_real_array",
     "def f(a, b):\n    return min(a, b)\n",
     {"a": array_t("double", 1), "b": scalar_t("double")}, "np.minimum"),
    ("math_of_real_array",
     "def f(a):\n    return math.sqrt(a)\n",
     {"a": array_t("double", 1)}, "np.sqrt"),
]


def main():
    cxx = shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        print("SKIP: no C++ compiler on PATH")
        sys.exit(0)

    fails = []
    n_ok = 0
    for i, (name, src, inputs, tol) in enumerate(FIXTURES):
        try:
            program = _build_program(src, inputs)
        except UnsupportedSpec as e:
            fails.append("%s: unexpected reject: %s" % (name, e))
            continue
        except Exception as e:  # noqa: BLE001
            fails.append("%s: transpile error: %r" % (name, e))
            continue
        out, err = _compile_and_run(cxx, program, "%02d" % i)
        if err:
            fails.append("%s: %s" % (name, err))
            continue
        tag, got = _parse_res(out)
        if got is None:
            fails.append("%s: no RES line in output:\n%s" % (name, out))
            continue
        try:
            exp = np.asarray(_run_oracle(name, src, inputs))
        except Exception as e:  # noqa: BLE001
            fails.append("%s: oracle error: %r" % (name, e))
            continue
        if exp.shape != got.shape:
            fails.append("%s: shape %s != numpy %s" % (name, got.shape, exp.shape))
            continue
        if tag in ("i64", "bool"):
            ok = np.array_equal(got.astype(np.int64), exp.astype(np.int64))
        else:
            rtol, atol = tol if tol is not None else (1e-9, 1e-9)
            # equal_nan: a NaN the oracle produced is a RESULT to match, not a
            # failure -- np.maximum/np.minimum/np.clip propagate NaN, so the
            # nan_* fixtures expect NaN in specific slots. This only relaxes the
            # NaN-vs-NaN pair; NaN vs a number still fails, which is exactly the
            # fused-loop-vs-nd:: divergence those fixtures exist to catch. No
            # pre-existing fixture is affected: allclose already scored NaN-vs-NaN
            # as a mismatch, so any fixture producing one would have been failing.
            ok = np.allclose(got, exp.astype(np.float64), rtol=rtol, atol=atol,
                             equal_nan=True)
        if not ok:
            fails.append("%s: value mismatch\n  got=%s\n  exp=%s"
                         % (name, got.ravel(), exp.ravel()))
            continue
        n_ok += 1

    # reject suite
    n_rej = 0
    for name, src, arg_types, sub in REJECTS:
        try:
            transpile_function(src, arg_types)
        except UnsupportedSpec as e:
            if sub and sub not in str(e):
                fails.append("reject/%s: wrong reason %r (want substring %r)"
                             % (name, str(e), sub))
                continue
            n_rej += 1
        except Exception as e:  # noqa: BLE001
            fails.append("reject/%s: raised %r, expected UnsupportedSpec"
                         % (name, e))
        else:
            fails.append("reject/%s: did NOT reject (transpiled clean)" % name)

    print("parity_ok=%d/%d  rejects_ok=%d/%d"
          % (n_ok, len(FIXTURES), n_rej, len(REJECTS)))
    if fails:
        print("FAIL (%d):" % len(fails))
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("ALL PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
