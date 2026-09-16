"""Run the genuine compiled-vs-Python parity check for ALL 12 basic mPyNode types.

Each per-type script (parity_<type>.py) runs in its OWN mayapy subprocess (so the
native bundles never share a Maya runtime / MTypeId space), opens the original
Python node, loads the EXISTING .bundle (no rebuild, no porter, no LLM), drives
identical inputs, and compares the CORRECT outputs for that type:

  attr nodes (mPyNode/mPyConstraint/mPyFile-procedural)  -> output attrs
  mPyFile full file-read (fullFileNode)                  -> outColor/outAlpha over colour spaces
  geometry generators (mesh/curve/surface)              -> output-plug CV/vertex positions
  deformers (deformer/blendShape)                       -> two-sphere object-space points
  mPySkinCluster                                        -> two bound rigs, posed, points
  mPyTransform                                          -> all 16 worldMatrix elements (the flush-free opm relay result)
  mPyIkSolver                                           -> joint WORLD positions over 8 IK goals
  mPyLocator                                            -> draw-buffer probe vs evaluateDrawItems

These supersede the per-type fixtures/<type>/verify_in_maya.py, several of
which were the generic scalar template with empty OUTPUTS (a vacuous PASS for the
geometry/transform/ik/locator/skin families).

Usage:
  bash tools/run_parity_sweep.sh          (or tools\\run_parity_sweep.bat)
  python3 tools/parity_sweep/run_parity_sweep.py
  (set MAYAPY to override the interpreter; defaults to Maya 2026 on macOS)

The .bundle fixtures this compares against are NOT committed (.gitignore lists
``*.bundle``), so a fresh clone has none on any platform. Without the pre-flight
below every per-type script printed ``RESULT error bundle_missing``, which
matches neither the PASS nor the FAIL pattern, so the sweep scored twelve
``????`` rows and exited 1 with no statement of why.
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAYAPY = os.environ.get(
    "MAYAPY",
    "/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy")

TYPES = [
    "mPyNode", "mPyConstraint", "mPyFile",
    "mPyMesh", "mPyNurbsCurve", "mPyNurbsSurface",
    "mPyDeformer", "mPyBlendShape", "mPySkinCluster",
    "mPyTransform", "mPyIkSolver", "mPyLocator",
]

# The per-type scripts were authored independently and each prints its own RESULT shape
# (JSON, "RESULT: PASS", "PARITY PASS", "overall=True", space-separated, ...), so
# the parser is deliberately tolerant. Parity values themselves are uniform.
_NUM = r"([0-9][0-9.eE+-]*)"
_ERR = re.compile(r"(?:overall_maxerr|maxerr)[=: ]\s*" + _NUM, re.IGNORECASE)
_COMP = re.compile(
    r"(?:total_comps|components_compared|components|comps|ncomp)[=: ]\s*(\d+)",
    re.IGNORECASE)
_PASS_TRUE = re.compile(
    r"overall=True|\bpass=True\b|RESULT:?\s*PASS\b|RESULT\|PASS\||"
    r"RESULT_LINE\s+PASS\b|\bPARITY\s+PASS\b|\bVERIFY\s+PASS\b", re.IGNORECASE)
_PASS_FALSE = re.compile(
    r"overall=False|\bpass=False\b|RESULT:?\s*FAIL\b|RESULT\|FAIL\||"
    r"RESULT_LINE\s+FAIL\b|\bPARITY\s+FAIL\b|\bVERIFY\s+FAIL\b", re.IGNORECASE)


def _parse(out):
    ok = err = comp = None
    # Locator (and any json-emitting script) prints a PARITY_RESULT blob.
    for jm in re.findall(r"PARITY_RESULT\s+(\{.*\})", out):
        try:
            d = json.loads(jm)
            v = d.get("parity_pass", d.get("pass", d.get("ok")))
            if isinstance(v, bool):
                ok = v
            if d.get("maxerr") is not None:
                err = float(d["maxerr"])
            comp = d.get("components_compared", d.get("components", comp))
        except Exception:
            pass
    if ok is None:
        if _PASS_TRUE.search(out):
            ok = True
        elif _PASS_FALSE.search(out):
            ok = False
    if err is None:
        err_m = _ERR.findall(out)
        err   = float(err_m[-1]) if err_m else None
    if comp is None:
        comp_m = _COMP.findall(out)
        comp   = int(comp_m[-1]) if comp_m else None
    return {"pass": ok, "maxerr": err, "components": comp}


def _missing_bundles():
    """Types whose fixture dir holds no .bundle. Each parity_<type>.py loads a
    prebuilt bundle from fixtures/<type>/ and bails if it is absent."""
    out = []
    for t in TYPES:
        d = os.path.join(HERE, "fixtures", t)
        try:
            have = any(f.endswith(".bundle") for f in os.listdir(d))
        except OSError:
            have = False
        if not have:
            out.append(t)
    return out


def main():
    missing = _missing_bundles()
    if missing:
        print("Parity sweep: CANNOT RUN -- no compiled fixtures for %d/%d types:"
              % (len(missing), len(TYPES)))
        print("  " + ", ".join(missing))
        print("\nThe .bundle fixtures are gitignored, so a fresh clone has none.")
        print("Build them first, then re-run:")
        print("    tools/build_compiled_templates.sh")
        print("\n(This exits now rather than spending ~6 min producing a column")
        print(" of '????' rows that say nothing about parity.)")
        sys.exit(2)

    print("Parity sweep: %d basic node types via %s\n" % (len(TYPES), MAYAPY))
    rows = []
    for t in TYPES:
        script = os.path.join(HERE, "parity_%s.py" % t)
        proc   = subprocess.run([MAYAPY, script], capture_output=True, text=True)
        info   = _parse(proc.stdout + "\n" + proc.stderr)
        rows.append((t, info))
        status = "PASS" if info["pass"] else ("FAIL" if info["pass"] is False
                                              else "????")
        me = "n/a" if info["maxerr"] is None else "%.3e" % info["maxerr"]
        nc = info["components"] if info["components"] is not None else "?"
        print("  %-18s %-5s  maxerr=%-10s components=%s" % (t, status, me, nc))

    n_pass = sum(1 for _, i in rows if i["pass"])
    worst = max((i["maxerr"] for _, i in rows if i["maxerr"] is not None),
                default=0.0)
    print("\n%d/%d PASS   worst maxerr=%.3e" % (n_pass, len(TYPES), worst))
    sys.exit(0 if n_pass == len(TYPES) else 1)


if __name__ == "__main__":
    main()
