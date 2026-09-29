"""Rewrite every committed ``build/source/plugin_main.cpp`` from its fragments.

``plugin_main.cpp`` is codegen, exactly like the build scripts
``tools/regen_build_scripts.py`` covers, and it had no gate: a change to
``bundler.make_plugin_main`` left the shipped All Templates Plugin describing
the previous entry point, and nothing went red. This tool derives each one
again from the fragments beside it (``bundler.fragment_info`` reads the hook
names, the registered node name, the MTypeIds and the commands back off each
``<node>.cpp``), keeping the member order, vendor, version and strictness the
committed file records; ``tests/compile/freshness/test_plugin_main_freshness``
is the gate over its result.

    mayapy tools/regen_plugin_main.py            rewrite stale files
    mayapy tools/regen_plugin_main.py --check    exit 1 if any is stale
    mayapy tools/regen_plugin_main.py --json P   write the measurement to P
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

_TEMPLATES = os.path.join(_ROOT, "templates")
_NOT_NODES = {"plugin_main.cpp", "shared_helpers.cpp"}

_NAME_RE    = re.compile(r"^// (.+?) -- combined MPyNode plugin entry", re.M)
_DECL_RE    = re.compile(r"^MStatus (register_\w+)\(MFnPlugin&\);", re.M)
_VENDOR_RE  = re.compile(r'MFnPlugin plugin\(obj, "((?:[^"\\]|\\.)*)", "((?:[^"\\]|\\.)*)", "Any"\);')
_STRICT_RE  = re.compile(r"^#define ND_BUNDLE_STRICT (\d)", re.M)


def _iter_plugin_mains(root=_TEMPLATES):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        if "plugin_main.cpp" in filenames and os.path.basename(dirpath) == "source":
            yield os.path.join(dirpath, "plugin_main.cpp")


def _unescape(lit: str) -> str:
    return lit.replace('\\"', '"').replace("\\\\", "\\")


def regenerate(path: str, bundler) -> tuple[str, str]:
    """``(old_text, new_text)`` for one committed plugin_main.cpp."""
    with open(path, encoding="utf-8", newline="") as fh:
        old = fh.read()
    src_dir = os.path.dirname(path)
    name_m  = _NAME_RE.search(old)
    plugin  = name_m.group(1) if name_m else os.path.basename(
        os.path.dirname(os.path.dirname(os.path.dirname(path))))
    vm      = _VENDOR_RE.search(old)
    vendor  = _unescape(vm.group(1)) if vm else "mpynode-native"
    version = _unescape(vm.group(2)) if vm else "1.0"
    sm      = _STRICT_RE.search(old)
    strict  = bool(int(sm.group(1))) if sm else False

    infos = {}
    for fname in sorted(os.listdir(src_dir)):
        if not fname.endswith(".cpp") or fname in _NOT_NODES:
            continue
        with open(os.path.join(src_dir, fname), encoding="utf-8") as fh:
            info = bundler.fragment_info(fh.read())
        infos[info["register"]] = info
    # Member order is what the committed file records (its declaration order),
    # then any fragment it did not know about, by file name.
    order  = [h for h in _DECL_RE.findall(old) if h in infos]
    order += [h for h in infos if h not in order]
    new = bundler.make_plugin_main([infos[h] for h in order], plugin,
                                   vendor=vendor, version=version,
                                   strict_load=strict)
    # The committed file keeps whatever line endings it has (the mega tree is
    # stored CRLF on some checkouts, LF on others -- git normalises).
    if "\r\n" in old:
        new = new.replace("\n", "\r\n")
    return old, new


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any committed plugin_main.cpp is stale")
    ap.add_argument("--json", metavar="PATH",
                    help="write the measurement here (read-only, like --check)")
    args      = ap.parse_args(argv)
    read_only = args.check or bool(args.json)

    from mpynode.native.compiler import bundler

    stale, fresh, broken = [], [], []
    for path in _iter_plugin_mains():
        rel = os.path.relpath(path, _ROOT).replace(os.sep, "/")
        try:
            old, new = regenerate(path, bundler)
        except Exception as exc:  # a fragment the parser cannot read
            broken.append("%s: %s" % (rel, exc))
            continue
        if old == new:
            fresh.append(rel)
            continue
        stale.append(rel)
        if not read_only:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)

    result = {"fresh": fresh, "stale": stale, "broken": broken}
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    verb = "stale" if read_only else "rewritten"
    print("plugin_main.cpp: %d fresh, %d %s, %d unreadable"
          % (len(fresh), len(stale), verb, len(broken)))
    for p in stale:
        print("   %s %s" % (verb, p))
    for p in broken:
        print("   BROKEN %s" % p)
    if broken:
        return 2
    return 1 if (read_only and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
