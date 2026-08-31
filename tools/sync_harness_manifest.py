"""Add every template that is on disk but absent from the audit manifest.

``run_all.py`` / ``mega_plugin.py`` iterate ``templates.json``, so a template
that never got a row is silently never compiled -- an all-green audit over a
subset. This appends the missing rows, derived from each ``.mpn`` the same way
the existing rows were, and leaves existing rows untouched.

  python3 tools/sync_harness_manifest.py [--check]
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_HARNESS = os.path.join(_ROOT, "tools", "harness")
sys.path.insert(0, _HARNESS)

MANIFEST = os.path.join(_HARNESS, "templates.json")
TEMPLATES = os.path.join(_ROOT, "templates")


def _folder_for(rel):
    # Mirrors the existing rows: path under templates/ with separators folded
    # to '_', minus the trailing '/template.mpn'.
    # SPACES fold too: leaf folders are now "Mesh Regions" / "Two Bone IK", and
    # this value becomes the harness folder key AND (with a '_plugin' suffix)
    # the plugin filename -- so it has to stay a legal identifier.
    parts = rel.split("/")[1:-1]          # drop 'templates' and 'template.mpn'
    return "_".join(parts).replace(" ", "_")


def main():
    from demo_specs import demo_specs_for

    check = "--check" in sys.argv
    rows = json.load(open(MANIFEST))
    have = {r["mpn"].replace("\\", "/") for r in rows}

    disk = []
    for dirpath, _dirs, files in os.walk(TEMPLATES):
        if "template.mpn" in files:
            p = os.path.join(dirpath, "template.mpn")
            disk.append(os.path.relpath(p, _ROOT).replace("\\", "/"))
    disk.sort()

    added = []
    for rel in disk:
        if rel in have:
            continue
        path = os.path.join(_ROOT, rel)
        data = (json.load(open(path)) or {}).get("data") or {}
        demos = demo_specs_for(path)
        folder = _folder_for(rel)
        row = {
            "mpn": rel,
            "folder": folder,
            "plugin": folder + "_plugin",
            "native_type": data.get("native_type") or data.get("node_type"),
            "node_name": data.get("node_name"),
            "demo_label": demos[0][1] if demos else "Run demo",
            "n_demos": len(demos),
        }
        rows.append(row)
        added.append(row)

    for r in added:
        print("  + %-52s type=%-14s node=%-22s demos=%d"
              % (r["mpn"], r["native_type"], r["node_name"], r["n_demos"]))
    if not added:
        print("  manifest already covers all %d templates" % len(disk))
        return 0
    if check:
        print("\n--check: %d row(s) WOULD be added" % len(added))
        return 1

    rows.sort(key=lambda r: r["mpn"])
    with open(MANIFEST, "w") as fh:
        json.dump(rows, fh, indent=1)
        fh.write("\n")
    print("\nwrote %s (%d rows)" % (MANIFEST, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
