"""nd::MT19937 bit-exactness oracle/driver (run under mayapy).

Compiles nd_rng_test.cpp with clang++ -std=c++17 -O2, runs it, parses the
SEQ/SHAPE protocol, and asserts each nd:: draw sequence is BIT-IDENTICAL to
numpy.random.RandomState. Equality is exact (==): the 53-bit draws are
power-of-two rationals so both sides yield the same IEEE double, and %.17g
round-trips a double losslessly.

Usage:
    mayapy nd_rng_test.py
Exit code 0 == every sequence bit-identical to numpy legacy RandomState.
"""
import os
import sys
import shutil
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# nd_runtime.h stays in the package at scripts/mpynode/native/compiler/; this
# harness lives out in the suite, so -I pivots on the repo root (three
# dirname()s up from tests/compile/native) and descends back into scripts/.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
_INC = os.path.join(_ROOT, "scripts", "mpynode", "native", "compiler")
SRC = os.path.join(HERE, "nd_rng_test.cpp")


def _compile_and_run():
    cxx = shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        print("SKIP: no C++ compiler on PATH")
        sys.exit(0)
    exe = os.path.join(HERE, "_nd_rng.bin")
    cmd = [cxx, "-std=c++17", "-O2", "-I", _INC, SRC, "-o", exe]
    # finally, not a trailing remove (same fix as nd_runtime_test): the binary
    # was cleaned up only when it ran clean, so a RED run stranded _nd_rng.bin
    # in the source tree -- the run after which nobody looks at the directory.
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("COMPILE FAILED:\n", r.stderr)
            sys.exit(1)
        out = subprocess.run([exe], capture_output=True, text=True)
        if out.returncode != 0:
            print("RUN FAILED:\n", out.stderr)
            sys.exit(1)
    finally:
        try:
            os.remove(exe)
        except OSError:
            pass
    return out.stdout


def _seed_from_name(name):
    """seed_<N> / fill<seed> handled by caller; here parse scalar-seed cases."""
    return int(name.split("_", 1)[1])


def _expected(kind, name, tokens):
    """Return the numpy-oracle flat ndarray for one protocol line."""
    if kind == "SEQ":
        count = int(tokens[0])
        if name.startswith("seed_"):
            seed = int(name[len("seed_"):])
            return np.random.RandomState(seed).random_sample(count)
        if name.startswith("initarr_"):
            words = [int(w) for w in name[len("initarr_"):].split("_")]
            key = np.array(words, dtype=np.uint32)
            return np.random.RandomState(key).random_sample(count)
        raise KeyError("no oracle for SEQ %r" % name)
    if kind == "SHAPE":
        seed = int(tokens[0])
        ndim = int(tokens[1])
        dims = [int(x) for x in tokens[2:2 + ndim]]
        return np.random.RandomState(seed).random(tuple(dims)).ravel()
    raise KeyError("unknown kind %r" % kind)


def main():
    text = _compile_and_run()
    fails = []
    n_cases = 0
    n_draws = 0
    for line in text.splitlines():
        t = line.split()
        if not t or t[0] not in ("SEQ", "SHAPE"):
            continue
        kind = t[0]
        name = t[1]
        try:
            colon = t.index(":")
        except ValueError:
            fails.append("%s %s: malformed (no ':')" % (kind, name))
            continue
        header = t[2:colon]
        vals = np.array([float(v) for v in t[colon + 1:]], dtype=np.float64)
        try:
            exp = np.asarray(_expected(kind, name, header), dtype=np.float64).ravel()
        except KeyError as e:
            fails.append(str(e))
            continue
        n_cases += 1
        n_draws += vals.size
        if exp.shape != vals.shape:
            fails.append("%s %s: length %d != %d" % (kind, name, vals.size, exp.size))
            continue
        # BIT-EXACT: identical IEEE doubles, no tolerance.
        if not np.array_equal(vals, exp):
            n_bad = int(np.count_nonzero(vals != exp))
            first = int(np.argmax(vals != exp))
            fails.append("%s %s: %d/%d draws differ; first at idx %d got=%.17g exp=%.17g"
                         % (kind, name, n_bad, vals.size, first, vals[first], exp[first]))
    print("cases=%d draws=%d" % (n_cases, n_draws))
    if n_cases == 0:
        print("NO CASES PARSED")
        sys.exit(1)
    if fails:
        print("FAIL (%d):" % len(fails))
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("ALL BIT-EXACT")
    sys.exit(0)


if __name__ == "__main__":
    main()
