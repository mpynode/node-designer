"""nd_runtime degenerate-divisor / NaN parity oracle (run under mayapy).

Compiles nd_intnan_test.cpp at the SHIPPING flags (-O3 -ffp-contract=off, see
native/toolchain/toolchain.py), runs it, and asserts every emitted value against
numpy -- numpy is the spec, including its non-trapping `x // 0 == 0` and its
NaN-propagating np.minimum/np.maximum.

The C++ side crashing (SIGFPE from an unguarded integer divide) shows up here as
"RUN FAILED", which is the point: a signal is not a std::exception, so an
unguarded `//0` inside a compiled node takes the whole host down.

Usage:
    mayapy nd_intnan_test.py
Exit code 0 == all cases parity-clean.
"""
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_INC = os.path.join(os.path.dirname(HERE), "compiler")
SRC = os.path.join(HERE, "nd_intnan_test.cpp")

IMIN = int(np.iinfo(np.int64).min)
NAN = np.nan
INF = np.inf


def _compile_and_run():
    cxx = shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        print("SKIP: no C++ compiler on PATH")
        sys.exit(0)
    exe = os.path.join(HERE, "_nd_intnan_test.bin")
    cmd = [cxx, "-std=c++17", "-O3", "-ffp-contract=off", "-I", _INC, SRC, "-o", exe]
    # finally, not a trailing remove (same fix as nd_runtime_test): the binary
    # was cleaned up only when it ran clean, so a RED run stranded
    # _nd_intnan_test.bin in the source tree.
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("COMPILE FAILED:\n", r.stderr)
            sys.exit(1)
        out = subprocess.run([exe], capture_output=True, text=True)
        if out.returncode != 0:
            print("RUN FAILED (rc=%d -- a negative rc is a SIGNAL, e.g. -8 SIGFPE "
                  "from an unguarded integer divide):\n%s"
                  % (out.returncode, out.stderr))
            sys.exit(1)
    finally:
        try:
            os.remove(exe)
        except OSError:
            pass
    return out.stdout


def _msvc_float(v):
    """``float()`` that understands MSVC's NaN spellings.

    MSVC's CRT prints a quiet NaN as ``-nan(ind)`` (and a signaling one as
    ``nan(snan)``) where libc++/libstdc++ print plain ``-nan``/``nan``.
    Python's ``float()`` rejects the parenthesised form, so on Windows this
    harness -- whose whole subject IS the NaN edges -- died parsing the C++
    output it had just produced (measured 2026-08-14:
    ``ValueError: could not convert string to float: '-nan(ind)'``).
    The NaN sign is not meaningful and every comparison below is NaN-aware.
    """
    s = v.strip().lower()
    if s.endswith("(ind)") or s.endswith("(snan)"):
        return float("nan")
    return float(s)


def _parse(text):
    """-> {(case, name): 1-D ndarray}, plus a DONE sentinel check."""
    got = {}
    done = False
    for line in text.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "DONE":
            done = True
            continue
        if t[0] != "RES":
            continue
        case, name, dt, n = t[1], t[2], t[3], int(t[4])
        assert t[5] == ":", line
        vals = t[6:]
        assert len(vals) == n, line
        if dt == "i64":
            got[(case, name)] = np.array([int(v) for v in vals], dtype=np.int64)
        else:
            got[(case, name)] = np.array([_msvc_float(v) for v in vals],
                                         dtype=np.float64)
    return got, done


def _expected():
    """Every expected value comes from numpy, never from a hand-written literal."""
    exp = {}
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        # 1 / 2: integer // and % with 0 and -1 divisors.
        a = np.array([7, -7, 0, 5, -5, IMIN, IMIN, IMIN, 9, -9, IMIN], dtype=np.int64)
        b = np.array([0, 0, 0, -1, -1, -1, 0, 1, 4, 4, 3], dtype=np.int64)
        exp[("int_degenerate", "fd")] = a // b
        exp[("int_degenerate", "md")] = np.mod(a, b)

        xs = np.array([7, -7, 0, IMIN, IMIN, -13], dtype=np.int64)
        ys = np.array([0, 0, 0, -1, 0, -1], dtype=np.int64)
        exp[("int_scalar", "fd")] = xs // ys
        exp[("int_scalar", "md")] = np.mod(xs, ys)

        # 3: float // and % by zero.
        fa = np.array([5.0, -5.0, 0.0, -0.0])
        fb = np.zeros(4)
        exp[("float_divzero", "fd")] = fa // fb
        exp[("float_divzero", "md")] = np.mod(fa, fb)

        # 4: minimum/maximum, flat.
        xa = np.array([NAN, 1.0, NAN, 2.0, -0.0, INF, -INF, 3.0])
        xb = np.array([1.0, NAN, NAN, 7.0, 0.0, 1.0, 1.0, NAN])
        exp[("minmax_flat", "mx")] = np.maximum(xa, xb)
        exp[("minmax_flat", "mn")] = np.minimum(xa, xb)

        # 5: minimum/maximum, broadcast (3,1) x (3,2).
        col = np.array([NAN, 2.0, -1.0]).reshape(3, 1)
        m2 = np.array([1.0, NAN, NAN, 5.0, 4.0, NAN]).reshape(3, 2)
        exp[("minmax_bcast", "mx")] = np.maximum(col, m2).ravel()
        exp[("minmax_bcast", "mn")] = np.minimum(col, m2).ravel()

        # 6: np.max / np.min reductions over NaN.
        m = np.array([[1.0, NAN, 3.0],
                      [4.0, 5.0, 6.0],
                      [NAN, 8.0, 9.0]])
        exp[("reduce_nan", "mx1")] = m.max(1)
        exp[("reduce_nan", "mn1")] = m.min(1)
        exp[("reduce_nan", "mx0")] = m.max(0)
        exp[("reduce_nan", "mn0")] = m.min(0)
        exp[("reduce_nan", "mxall")] = np.array([m.max()])
        exp[("reduce_nan", "mnall")] = np.array([m.min()])

        # 7: integer max/min unaffected.
        ia = np.array([3, -4, 0, IMIN], dtype=np.int64)
        ib = np.array([1, 5, 0, 7], dtype=np.int64)
        exp[("int_minmax", "mx")] = np.maximum(ia, ib)
        exp[("int_minmax", "mn")] = np.minimum(ia, ib)
        exp[("int_minmax", "rmx")] = np.array([ia.max()], dtype=np.int64)
        exp[("int_minmax", "rmn")] = np.array([ia.min()], dtype=np.int64)

        # 8: scalar apply_binop Min/Max.
        ls = np.array([NAN, 1.0, NAN, 2.0])
        rs = np.array([1.0, NAN, NAN, 7.0])
        exp[("minmax_scalar", "mx")] = np.maximum(ls, rs)
        exp[("minmax_scalar", "mn")] = np.minimum(ls, rs)
    return {k: np.asarray(v).ravel() for k, v in exp.items()}


def _same(got, want):
    if got.shape != want.shape:
        return False
    if want.dtype.kind in "iu":
        return np.array_equal(got.astype(np.int64), want.astype(np.int64))
    # NaN must MATCH NaN (that is the property under test), so compare the
    # NaN masks and the finite values separately -- np.allclose would not.
    # `==` deliberately treats -0.0 as 0.0: numpy's own min/max sign-of-zero
    # result is SIMD-lane dependent (ARM FMIN/FMAX vs the scalar ternary), so it
    # is not a contract and must not be pinned here.
    gn, wn = np.isnan(got), np.isnan(want)
    if not np.array_equal(gn, wn):
        return False
    return np.array_equal(got[~gn], want[~wn])


def main():
    text = _compile_and_run()
    got, done = _parse(text)
    if not done:
        print("HARNESS DID NOT REACH DONE\n", text)
        sys.exit(1)
    exp = _expected()
    fails = []
    for key in sorted(exp):
        if key not in got:
            fails.append("%s/%s: not emitted by the C++ side" % key)
            continue
        if not _same(got[key], exp[key]):
            fails.append("%s/%s: mismatch\n  got=%s\n  exp=%s"
                         % (key[0], key[1], got[key], exp[key]))
    for key in sorted(got):
        if key not in exp:
            fails.append("%s/%s: emitted but no oracle" % key)
    print("checks=%d" % len(exp))
    if fails:
        print("FAIL (%d):" % len(fails))
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("ALL PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
