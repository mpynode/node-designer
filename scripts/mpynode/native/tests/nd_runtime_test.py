"""nd_runtime numpy-parity oracle/driver (run under mayapy).

Compiles nd_runtime_test.cpp with clang++ -std=c++17 -O2, runs it, parses the
IN/OUT protocol, reconstructs the inputs, recomputes each op with numpy, and
asserts parity. Inputs flow C++ -> here (single source of truth, no drift).

Usage:
    mayapy nd_runtime_test.py
Exit code 0 == all cases parity-clean.
"""
import os
import sys
import shutil
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# nd_runtime.h lives in native/compiler/; add that dir to -I so the
# `#include "nd_runtime.h"` in nd_runtime_test.cpp still resolves after the move.
_INC = os.path.join(os.path.dirname(HERE), "compiler")
SRC = os.path.join(HERE, "nd_runtime_test.cpp")
FTOL = dict(rtol=1e-12, atol=1e-12)

_DT = {"f64": np.float64, "i64": np.int64, "bool": np.bool_}


def _compile_and_run():
    cxx = shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        print("SKIP: no C++ compiler on PATH")
        sys.exit(0)
    exe = os.path.join(HERE, "_nd_test.bin")
    # -ffp-contract=off matches the shipping recipe (toolchain.py) and is what
    # makes the MATMUL2D BITEXACT block in the .cpp mean anything: with
    # contraction ON the compiler picks FMA per call site, so an UNCHANGED
    # nd_runtime.h already yields different matmul bytes at -O1 vs -O2.
    cmd = [cxx, "-std=c++17", "-O2", "-ffp-contract=off", "-I", _INC, SRC, "-o", exe]
    # finally, not a trailing remove: the binary was cleaned up only when every
    # case passed, so a RED run left a stale _nd_test.bin sitting in the source
    # tree -- exactly the run after which nobody is looking at the directory.
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("COMPILE FAILED:\n", r.stderr)
            sys.exit(1)
        out = subprocess.run([exe], capture_output=True, text=True)
        if out.returncode != 0:
            # The MATMUL2D BITEXACT block is the only thing in the .cpp that
            # exits nonzero, and it reports on STDOUT -- printing stderr alone
            # said literally nothing when it tripped.
            print("RUN FAILED:\n", out.stderr)
            print("\n".join(out.stdout.splitlines()[-12:]))
            sys.exit(1)
    finally:
        try:
            os.remove(exe)
        except OSError:
            pass
    return out.stdout


def _parse(text):
    """-> list of (case_name, {name: ndarray} for IN, [(name, ndarray)] for OUT)."""
    cases = []
    cur = None
    for line in text.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "CASE":
            cur = {"name": t[1], "ins": {}, "outs": []}
        elif t[0] == "END":
            cases.append(cur)
            cur = None
        elif t[0] in ("IN", "OUT"):
            name = t[1]
            dt = _DT[t[2]]
            ndim = int(t[3])
            dims = [int(x) for x in t[4:4 + ndim]]
            assert t[4 + ndim] == ":", line
            vals = t[4 + ndim + 1:]
            if dt is np.bool_:
                arr = np.array([int(v) for v in vals], dtype=np.int64).astype(np.bool_)
            elif dt is np.int64:
                arr = np.array([int(v) for v in vals], dtype=np.int64)
            else:
                arr = np.array([float(v) for v in vals], dtype=np.float64)
            arr = arr.reshape(dims) if ndim > 0 else arr.reshape(())
            if t[0] == "IN":
                cur["ins"][name] = arr
            else:
                cur["outs"].append((name, arr))
    return cases


# ---- oracle: case name -> fn(ins) -> {out_name: expected ndarray} ------------
def _oracle(name, i):
    if name == "add_broadcast":
        return {"out": i["a"] + i["b"]}
    if name == "sub_mul":
        return {"out": (i["a"] - i["b"]) * 2}
    if name == "truediv_int_promote":
        return {"out": i["a"] / 2}
    if name == "floordiv_mod_neg":
        return {"fd": i["a"] // i["b"], "md": i["a"] % i["b"]}
    if name == "power_float":
        return {"out": i["a"] ** i["b"]}
    if name == "negate":
        return {"out": -i["a"]}
    if name == "newaxis_outer":
        return {"out": i["a"][:, None] * i["b"]}
    if name == "maximum_minimum":
        return {"mx": np.maximum(i["a"], i["b"]), "mn": np.minimum(i["a"], i["b"])}
    if name == "sum_axes":
        a = i["a"]
        return {"s0": a.sum(0), "s1": a.sum(1), "sall": a.sum(),
                "s1k": a.sum(1, keepdims=True)}
    if name == "sum_multiaxis_3d":
        a = i["a"]
        return {"s12": a.sum((1, 2)), "s02": a.sum((0, 2))}
    if name == "solve_singular_yields_zeros":
        # np.linalg.solve would raise LinAlgError; nd::solve returns zeros by
        # design (see the SAFETY note on nd::solve). Asserted literally.
        return {"x": np.zeros(2)}
    if name == "sum_mul_fused_and_fallback":
        a, b, c = i["a"], i["b"], i["c"]
        return {"last": (a * b).sum(2),
                "lastk": (a * b).sum(2, keepdims=True),
                "all": (a * b).sum(),
                "mid": (a * b).sum(1),
                "first": (a * b).sum(0),
                "bcast": (c * b).sum(2)}
    if name == "cumsum_2d":
        a = i["a"]
        return {"c0": a.cumsum(0), "c1": a.cumsum(1), "cn1": a.cumsum(-1),
                "cflat": a.cumsum()}
    if name == "cumsum_rounding_order":
        return {"c": i["a"].cumsum(0)}
    if name == "cumsum_strided":
        t = i["t"]
        return {"c0": t.cumsum(0), "cflat": t.cumsum()}
    if name == "cumsum_3d_int":
        a = i["a"]
        return {"c1": a.cumsum(1), "c2": a.cumsum(2), "cflat": a.cumsum()}
    if name == "mean_norm":
        a = i["a"]
        return {"m0": a.mean(0), "n1": np.linalg.norm(a, axis=1)}
    if name == "minmax_reduce":
        a = i["a"]
        return {"mx1": a.max(1), "mn0": a.min(0)}
    if name == "matmul_2d":
        return {"out": i["a"] @ i["b"]}
    if name == "matmul_2d_1d":
        return {"mv": i["a"] @ i["v"], "d": np.array(i["v"] @ i["v"])}
    if name == "matmul_batched":
        return {"out": i["a"] @ i["b"]}
    if name == "cross_transpose":
        return {"c": np.cross(i["a"], i["b"]), "mt": i["m"].T}
    if name == "reshape_infer_ravel":
        r = i["a"].reshape(3, -1)
        return {"r": r, "rav": r.T.ravel()}
    if name == "astype_trunc":
        return {"i": i["a"].astype(np.int64), "f": i["b"].astype(np.float64)}
    if name == "slice_1d":
        a = i["a"]
        return {"mid": a[2:7], "step2": a[::2], "rev": a[::-1],
                "head": a[:-2], "tail": a[3:]}
    if name == "slice_2d_block_index":
        m = i["m"]
        return {"block": m[:, 1:3], "row1": m[1, :], "lastcol": m[:, -1]}
    if name == "slice_assign":
        z = np.zeros((4, 4))
        z[1:3, 1:3] = np.array([[5, 6], [7, 8]], dtype=float)
        return {"z": z}
    if name == "constructors":
        return {"z": np.zeros((2, 2)), "o": np.ones(3), "f": np.full((2, 2), 7.0),
                "e": np.eye(3), "ar": np.arange(2, 11, 3).astype(float),
                "ls": np.linspace(0, 1, 5), "lsne": np.linspace(0, 1, 5, endpoint=False)}
    if name == "ufuncs":
        a = i["a"]
        return {"sin": np.sin(a), "sqrt": np.sqrt(np.array([0, 1, 4, 9.0])),
                "floor": np.floor(a), "sign": np.sign(a), "fabs": np.fabs(a),
                "exp": np.exp(np.array([0, 1, 2.0]))}
    if name == "compare_ops":
        a, b = i["a"], i["b"]
        return {"eq": a == b, "lt": a < b, "ge": a >= b, "ne_s": a != 2.0}
    if name == "compare_broadcast":
        return {"gt": i["m"] > i["r"]}
    if name == "bitwise_int":
        a, b = i["a"], i["b"]
        return {"band": a & b, "bor": a | b, "bxor": a ^ b, "inv": ~a}
    if name == "bitwise_bool":
        a, b = i["a"], i["b"]
        return {"band": a & b, "bor": a | b, "inv": ~a}
    if name == "logical_ops":
        a, b = i["a"], i["b"]
        return {"land": np.logical_and(a, b), "lor": np.logical_or(a, b),
                "lnot": np.logical_not(a)}
    if name == "where_op":
        cond, a, b = i["cond"], i["a"], i["b"]
        return {"w": np.where(cond, a, b), "ws": np.where(cond, 0.0, b)}
    if name == "nonzero_2d":
        ys, xs = np.nonzero(i["m"])
        return {"ys": ys, "xs": xs}
    if name == "concat_stack":
        a, b = i["a"], i["b"]
        return {"c0": np.concatenate([a, b], 0), "c1": np.concatenate([a, b], 1),
                "s0": np.stack([a, b], 0), "s1": np.stack([a, b], 1)}
    if name == "concat_views":
        return {"cf": np.concatenate([i["offv"], i["other3"]], 1),
                "cs": np.concatenate([i["strv"], i["other2"]], 1),
                "cmix": np.concatenate([i["strv"], i["other2"]], 0),
                "c3d": np.concatenate([i["c3"], i["d3"]], 1),
                "st1": np.stack([i["p"], i["q"], i["r"]], 1),
                "st0": np.stack([i["p"], i["q"], i["r"]], 0)}
    if name == "colstack_tile":
        return {"cs": np.column_stack([i["x"], i["y"], i["z"]]),
                "tl": np.tile(i["t1"], 3), "tl2": np.tile(i["t2"], (2, 1))}
    if name == "take_roll":
        a, m = i["a"], i["m"]
        return {"tk": np.take(a, i["idx"]), "rl": np.roll(a, 2),
                "tkax": np.take(m, np.array([2, 0]), axis=1),
                "rlax": np.roll(m, 1, axis=0)}
    raise KeyError("no oracle for case %r" % name)


def main():
    text = _compile_and_run()
    cases = _parse(text)
    if not cases:
        print("NO CASES PARSED")
        sys.exit(1)
    # The .cpp self-checks matmul2d's every dispatch arm against a literal
    # ascending-l reference on raw BYTES; numpy cannot do that job because
    # np.matmul goes through BLAS. A failure there already exits nonzero, so
    # this only guards the marker silently disappearing.
    if "MATMUL2D BITEXACT OK" not in text:
        print("MISSING MATMUL2D BITEXACT OK marker")
        sys.exit(1)
    # Same deal for matmul's BATCHED arm, which is a different kernel and which
    # the matmul_batched numpy case above cannot police: it is (2,2,2)@(2,2,3)
    # over small integers, and a reversed sum of two exactly representable terms
    # is bit-identical.
    if "MATMUL BATCHED BITEXACT OK" not in text:
        print("MISSING MATMUL BATCHED BITEXACT OK marker")
        sys.exit(1)
    fails = []
    n_checks = 0
    for c in cases:
        exp = _oracle(c["name"], c["ins"])
        for oname, actual in c["outs"]:
            n_checks += 1
            if oname not in exp:
                fails.append("%s/%s: no oracle output" % (c["name"], oname))
                continue
            e = np.asarray(exp[oname])
            if e.shape != actual.shape:
                fails.append("%s/%s: shape %s != %s" % (c["name"], oname, actual.shape, e.shape))
                continue
            if actual.dtype.kind in "iu" or e.dtype == np.int64:
                ok = np.array_equal(actual.astype(np.int64), np.asarray(e).astype(np.int64))
            else:
                ok = np.allclose(actual, e, **FTOL)
            if not ok:
                fails.append("%s/%s: value mismatch\n  got=%s\n  exp=%s"
                             % (c["name"], oname, actual.ravel(), e.ravel()))
    print("cases=%d checks=%d" % (len(cases), n_checks))
    if fails:
        print("FAIL (%d):" % len(fails))
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("ALL PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
