"""Why does the port cache miss every LLM-ported node on every rebuild?

Runs ``dump_canonical_specs.py`` in TWO separate mayapy processes and diffs the
canonical cache payloads. If a spec differs across processes, the cache key
differs, and the porter re-runs for nothing.

Reports the exact JSON PATH of every difference, so the answer is a field name
rather than a hunch. Also re-runs one process with PYTHONHASHSEED pinned, which
distinguishes "something is built from a set/frozenset" (per-process string hash
randomization reorders it, and json.dumps preserves LIST order) from any other
source of nondeterminism.

Run:  mayapy tools/probe_spec_determinism.py      (drives its own subprocesses)
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMPER = os.path.join(ROOT, "tools", "dump_canonical_specs.py")
MAYAPY = os.environ.get(
    "MPYNODE_MAYAPY",
    "/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy")


def L(m=""):
    print(m, flush=True)


def _run(out_path, hashseed=None):
    env = dict(os.environ)
    if hashseed is not None:
        env["PYTHONHASHSEED"] = str(hashseed)
    else:
        env.pop("PYTHONHASHSEED", None)
    p = subprocess.run([MAYAPY, DUMPER, out_path], env=env,
                       capture_output=True, text=True)
    if p.returncode != 0:
        L(p.stdout[-2000:])
        L(p.stderr[-2000:])
        raise SystemExit("dumper failed (rc=%d)" % p.returncode)
    with open(out_path) as fh:
        return json.load(fh)


def _diff_paths(a, b, path=""):
    """Every leaf path where two JSON structures differ."""
    out = []
    if type(a) is not type(b):
        return [(path, "type %s != %s" % (type(a).__name__, type(b).__name__))]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(("%s.%s" % (path, k), "only in B"))
            elif k not in b:
                out.append(("%s.%s" % (path, k), "only in A"))
            else:
                out.extend(_diff_paths(a[k], b[k], "%s.%s" % (path, k)))
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append((path, "len %d != %d" % (len(a), len(b))))
        else:
            same_set = False
            try:
                same_set = sorted(map(repr, a)) == sorted(map(repr, b))
            except Exception:
                pass
            if a != b and same_set:
                # Same members, different order -- the signature of a set.
                out.append((path, "REORDERED (same %d members): %s -> %s"
                            % (len(a), str(a)[:90], str(b)[:90])))
            else:
                for i, (x, y) in enumerate(zip(a, b)):
                    out.extend(_diff_paths(x, y, "%s[%d]" % (path, i)))
    elif a != b:
        out.append((path, "%s -> %s" % (str(a)[:90], str(b)[:90])))
    return out


def main():
    scratch = tempfile.mkdtemp(prefix="spec-determinism-")
    L("=" * 78)
    L("SPEC / CACHE-KEY DETERMINISM ACROSS PROCESSES")
    L("=" * 78)

    L("run A (free hash seed) ...")
    a = _run(os.path.join(scratch, "a.json"))
    L("run B (free hash seed) ...")
    b = _run(os.path.join(scratch, "b.json"))

    unstable = []
    for rel in sorted(set(a) | set(b)):
        ka = (a.get(rel) or {}).get("key")
        kb = (b.get(rel) or {}).get("key")
        if ka != kb:
            unstable.append(rel)

    L("")
    L("templates            : %d" % len(a))
    L("UNSTABLE cache keys  : %d" % len(unstable))
    L("")
    if not unstable:
        L("All keys stable across processes -- the churn is NOT in the spec.")
    for rel in unstable:
        L("  %s" % rel)
        diffs = _diff_paths((a[rel] or {}).get("canonical"),
                            (b[rel] or {}).get("canonical"))
        for path, why in diffs[:8]:
            L("      %-46s %s" % (path.lstrip("."), why))
        if len(diffs) > 8:
            L("      ... %d more" % (len(diffs) - 8))

    # -- is it hash-seed dependent? -----------------------------------------
    L("")
    L("-" * 78)
    L("run C + D (PYTHONHASHSEED=0, pinned) ...")
    c = _run(os.path.join(scratch, "c.json"), hashseed=0)
    d = _run(os.path.join(scratch, "d.json"), hashseed=0)
    pinned_unstable = [rel for rel in sorted(set(c) | set(d))
                       if (c.get(rel) or {}).get("key")
                       != (d.get(rel) or {}).get("key")]
    L("UNSTABLE with the hash seed PINNED: %d" % len(pinned_unstable))
    for rel in pinned_unstable:
        L("  %s" % rel)
    L("")
    if unstable and not pinned_unstable:
        L("VERDICT: the churn is PYTHONHASHSEED-dependent -- something in the")
        L("         spec is built from a set/frozenset. json.dumps sorts DICT")
        L("         keys but PRESERVES LIST ORDER, so a list materialised from a")
        L("         set re-orders every process and moves the key.")
    elif unstable:
        L("VERDICT: unstable even with the hash seed pinned -- the cause is NOT")
        L("         set-iteration order. See the diff paths above.")
    else:
        L("VERDICT: specs are stable across processes; look elsewhere (the key")
        L("         also folds in provider/model/recipe).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
