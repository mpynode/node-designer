"""Rewrite every shipped ``build/<type>/verify_in_maya.py`` from its spec.

The porter writes each one from
``native.ai.verify_scripts._verify_script(spec)`` when it builds a template,
and nothing else rewrote them: a change to that generator, or to a row's
spec, left the shipped scripts behind (on 2026-10-15, 28 of 38 no longer
matched). Every script embeds its node's whole spec, so a spec edit moves it
too. This tool writes each one again from its row in the build tree's
``manifest.json``, a codegen-only refresh like
``tools/regen_build_scripts.py``;
``tests/compile/freshness/test_shipped_verify_scripts`` is the gate over its
result.

A script is fresh when it matches the generator line for line once whitespace
runs are collapsed, since the shipped copies may be column-aligned. A stale
one is rewritten with the generator's text, LF. Only scripts that already
exist are rewritten. The generator's text does not depend on the OS running
this tool: each script picks its plug-in extension when it runs.

    mayapy tools/regen_verify_scripts.py --dry-run    report, write nothing
    mayapy tools/regen_verify_scripts.py              rewrite stale scripts
    mayapy tools/regen_verify_scripts.py --check      exit 1 if any is stale
    mayapy tools/regen_verify_scripts.py --only spline,mPyDnet
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

_MANIFESTS = ("templates/*/build/manifest.json",
              "templates/*/*/build/manifest.json")


def shipped(root=_ROOT):
    """``(path, type name, spec)`` for every shipped verify script."""
    out = []
    for pat in _MANIFESTS:
        for mf in sorted(glob.glob(os.path.join(root, pat))):
            with open(mf, encoding="utf-8") as fh:
                man = json.load(fh)
            for row in man.get("nodes") or []:
                ty = row.get("type_name")
                path = os.path.join(os.path.dirname(mf), ty or "",
                                    "verify_in_maya.py")
                if ty and os.path.isfile(path):
                    out.append((path, ty, row.get("spec") or {}))
    return out


def _lines(text):
    return [" ".join(ln.split()) for ln in text.splitlines()]


def matches(text, want):
    """True when ``text`` is ``want`` up to whitespace runs."""
    return _lines(text) == _lines(want)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report, write nothing")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any shipped script is stale")
    ap.add_argument("--only", default="",
                    help="comma-separated type names")
    args      = ap.parse_args(argv)
    read_only = args.dry_run or args.check
    only      = {t for t in args.only.split(",") if t}

    from mpynode.native.ai import verify_scripts

    fresh, stale = [], []
    for path, ty, spec in shipped():
        if only and ty not in only:
            continue
        rel = os.path.relpath(path, _ROOT).replace(os.sep, "/")
        with open(path, encoding="utf-8", newline="") as fh:
            old = fh.read()
        new = verify_scripts._verify_script(spec)
        if matches(old, new):
            fresh.append(rel)
            continue
        stale.append(rel)
        if not read_only:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)

    verb = "stale" if read_only else "rewritten"
    print("verify_in_maya.py: %d fresh, %d %s" % (len(fresh), len(stale), verb))
    for rel in stale:
        print("   %s %s" % (verb, rel))
    if args.check and stale:
        print("\nSTALE. Run: mayapy tools/regen_verify_scripts.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
