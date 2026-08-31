"""Rewrite every committed build.sh / build.bat from today's generators.

The build scripts are CODEGEN output, exactly like ``1_transpiled.cpp``: a
change to ``bundler.make_*_build_*`` silently leaves 120 checked-in scripts
describing the old recipe. This is the codegen-only refresh -- no compiler, no
linker, no AI -- mirroring ``tools/regen_mega_transpiled.py``.

Only the RECIPE is refreshed; the generator INPUTS are held fixed. Those inputs
(plugin name, the fragment list and its compile ORDER, whether Qt was linked,
which install the artifact was built against) are not fully recoverable from
manifest.json -- ``frag_files`` is an ordered list assembled during the build
and may carry the shared-helpers unit -- but every one of them is recorded
verbatim in the committed script, so they are read back from there. Feeding the
generator anything else would REWRITE the recipe instead of refreshing it: the
single-node path takes the fixed ``bundler._LINK_LIBS``, for instance, not the
per-spec ``build_scripts._libs_for``.

Only rewrites files that ALREADY exist: a tree that never emitted a .bat does
not gain one here.

    mayapy tools/regen_build_scripts.py --dry-run   # report, write nothing
    mayapy tools/regen_build_scripts.py             # rewrite in place
    mayapy tools/regen_build_scripts.py --check     # exit 1 if any are stale
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

TREES = ("compiled_templates",)


def _iter_build_dirs():
    """Every ``build/`` holding a manifest.json with a ``nodes`` list."""
    for tree in TREES:
        base = os.path.join(ROOT, tree)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if "manifest.json" not in filenames:
                continue
            path = os.path.join(dirpath, "manifest.json")
            try:
                with open(path, encoding="utf-8") as fh:
                    man = json.load(fh)
            except (OSError, ValueError):
                continue
            if isinstance(man.get("nodes"), list):
                yield dirpath, man


def _linked(man):
    """Node rows that actually made it into the bundle."""
    return [n for n in man["nodes"]
            if (n.get("build_status") or "linked") not in ("dropped",)
            and n.get("type_name")]


def _plugin_name(build_dir, man):
    """The bundle stem. Recorded in the manifest; else the sibling artifact."""
    for key in ("plugin_name", "plugin"):
        v = man.get(key)
        if isinstance(v, str) and v:
            return os.path.splitext(os.path.basename(v))[0]
    # The build/ dir sits beside <plugin>.bundle; fall back to reading the
    # existing script rather than guessing from the folder name.
    sh = os.path.join(build_dir, "build.sh")
    if os.path.isfile(sh):
        with open(sh, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("# Rebuild native plugin '"):
                    return line.split("'")[1]
                if line.startswith("# Generated combined build for native plugin '"):
                    return line.split("'")[1]
    return None


# Inputs as recorded in the committed script. The multi-node compile lines keep
# frag_files in its original ORDER; the single-node link line names its one
# source; the provenance is either the label already stamped in, or -- first time
# through, before the resolver replaced it -- the old baked-in $MAYA default.
_FRAG_RE = re.compile(r'-c "\$HERE/source/([^"]+)"')
_SINGLE_SRC_RE = re.compile(r'-o "\$HERE/\.\./[^"]+" "\$HERE/source/([^"]+)"')
_PROV_RE = re.compile(r"^# Built against: (.+)$", re.M)
_OLD_MAYA_RE = re.compile(r'^MAYA="\$\{MAYA:-([^}]+)\}"$', re.M)


def _recorded_inputs(old_sh):
    """(frags, node_file, needs_qt, maya) read back out of a committed build.sh."""
    frags = [f for f in _FRAG_RE.findall(old_sh) if f != "plugin_main.cpp"]
    m = _SINGLE_SRC_RE.search(old_sh)
    node_file = m.group(1) if m else None
    needs_qt = "-framework QtCore" in old_sh
    prov = _PROV_RE.search(old_sh) or _OLD_MAYA_RE.search(old_sh)
    return frags, node_file, needs_qt, (prov.group(1) if prov else None)


def _regen_one(build_dir, man, bundler, build_scripts, toolchain):
    """(rel, {name: (old, new)}) for the scripts this tree already ships."""
    rel = os.path.relpath(build_dir, ROOT)
    rows = _linked(man)
    if not rows:
        return rel, {}
    plugin = _plugin_name(build_dir, man)
    if not plugin:
        return rel, {}

    sh_path = os.path.join(build_dir, "build.sh")
    if not os.path.isfile(sh_path):
        return rel, {}
    with open(sh_path, encoding="utf-8", newline="") as fh:
        old_sh = fh.read()
    frags, node_file, needs_qt, maya = _recorded_inputs(old_sh)

    out = {}
    if frags:
        # Multi-node: make_build_sh takes no maya at all -- the resolver is the
        # whole story, so there is no provenance line on this shape.
        gen = {
            "build.sh": bundler.make_build_sh(plugin, frags, needs_qt=needs_qt),
            "build.bat": bundler.make_build_bat(plugin, frags,
                                                needs_qt=needs_qt),
        }
    elif node_file:
        # Single-node: bundler.assemble passes the FIXED _LINK_LIBS here, and
        # gives the real maya only to the HOST platform's script -- the .bat is
        # written on a macOS host, so it carries no provenance.
        libs = list(bundler._LINK_LIBS)
        gen = {
            "build.sh": bundler.make_single_build_sh(
                plugin, node_file, libs, needs_qt=needs_qt, maya=maya),
            "build.bat": bundler.make_single_build_bat(
                plugin, node_file, libs, needs_qt=needs_qt, maya=None),
        }
    else:
        return rel, {}

    for fname, new in gen.items():
        path = os.path.join(build_dir, fname)
        if not os.path.isfile(path):
            continue                       # never CREATE, only refresh
        with open(path, encoding="utf-8", newline="") as fh:
            old = fh.read()
        out[fname] = (old, new)

    # Per-node scratch dirs (build/<type>/) carry their own script, emitted by
    # build_scripts.generate_build_* rather than the bundler pair. bundler
    # declares them disposable, but they ARE committed here
    # (build_compiled_templates_worker passes clean_scratch=False), so they
    # drift like any other codegen artifact if left out.
    for row in rows:
        sub = os.path.join(build_dir, row["type_name"])
        if not os.path.isdir(sub):
            continue
        for fname, fn in (("build.sh", build_scripts.generate_build_sh),
                          ("build.bat", build_scripts.generate_build_bat)):
            path = os.path.join(sub, fname)
            if not os.path.isfile(path):
                continue
            # write_plugin() calls generate_build_script(spec) with no maya, so
            # these carry no provenance line -- and unlike the bundler pair they
            # DO take the per-spec _libs_for.
            new = fn(row["spec"])
            with open(path, encoding="utf-8", newline="") as fh:
                old = fh.read()
            out["%s/%s" % (row["type_name"], fname)] = (old, new)
    return rel, out


def _orphans(build_dir, covered):
    """Scripts sitting in this tree that no manifest row accounts for.

    A renamed node leaves its old scratch dir behind; the script there is
    unowned codegen -- nothing can regenerate it, so it must be named rather
    than quietly dropped from the count.
    """
    out = []
    for dirpath, dirnames, filenames in os.walk(build_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fname in filenames:
            if fname not in ("build.sh", "build.bat"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fname),
                                  build_dir).replace(os.sep, "/")
            if rel not in covered:
                out.append(rel)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change, write nothing")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any committed script is stale")
    ap.add_argument("--json", metavar="PATH",
                    help="write the measurement here (implies --check's "
                         "read-only behaviour); consumed by the gate test")
    args = ap.parse_args(argv)
    read_only = args.dry_run or args.check or bool(args.json)

    from mpynode.native.compiler import build_scripts, bundler
    from mpynode.native.toolchain import toolchain

    trees = skipped = changed = same = 0
    stale = []
    orphans = []
    fresh = []
    for build_dir, man in _iter_build_dirs():
        trees += 1
        rel, scripts = _regen_one(build_dir, man, bundler, build_scripts,
                                  toolchain)
        orphans += ["%s/%s" % (rel, o)
                    for o in _orphans(build_dir, set(scripts))]
        if not scripts:
            skipped += 1
            continue
        for fname, (old, new) in sorted(scripts.items()):
            if old == new:
                same += 1
                fresh.append("%s/%s" % (rel, fname))
                continue
            changed += 1
            stale.append("%s/%s" % (rel, fname))
            if not read_only:
                with open(os.path.join(build_dir, fname), "w",
                          newline="") as fh:
                    fh.write(new)
                if fname.endswith(".sh"):
                    os.chmod(os.path.join(build_dir, fname), 0o755)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"trees": trees, "not_regenerable": skipped,
                       "fresh": sorted(fresh), "stale": sorted(stale),
                       "orphans": sorted(orphans)}, fh, indent=2)

    verb = "would rewrite" if read_only else "rewrote"
    print("build trees scanned : %d" % trees)
    print("  not regenerable   : %d  (no source/, no rows, or unknown plugin)"
          % skipped)
    print("  already current   : %d" % same)
    print("  %-17s : %d" % (verb, changed))
    for s in stale[:40]:
        print("      %s" % s)
    if len(stale) > 40:
        print("      ... and %d more" % (len(stale) - 40))
    print("  unowned (orphan)  : %d  (no manifest row -- not regenerable)"
          % len(orphans))
    for o in orphans:
        print("      %s" % o)

    if args.check and changed:
        print("\nSTALE. Run: mayapy tools/regen_build_scripts.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
