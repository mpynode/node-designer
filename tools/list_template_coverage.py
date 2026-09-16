"""Which templates does the compile harness actually cover?

``run_all.py`` iterates templates.json, not the templates tree. Any template
missing from the manifest is silently never compiled, so "all green" would be a
false pass on a subset. Prints the difference both ways.

  python3 tools/list_template_coverage.py
"""

from __future__ import annotations

import os
import sys

_HERE    = os.path.dirname(os.path.abspath(__file__))
_ROOT    = os.path.dirname(_HERE)
_HARNESS = os.path.join(_ROOT, "tools", "harness")
sys.path.insert(0, _HARNESS)

TEMPLATES = os.path.join(_ROOT, "templates")


def on_disk():
    out = []
    for dirpath, _dirs, files in os.walk(TEMPLATES):
        if "template.mpn" in files:
            p = os.path.join(dirpath, "template.mpn")
            out.append(os.path.relpath(p, _ROOT))
    return sorted(out)


def main():
    from demo_specs import load_templates

    rows    = load_templates(_HARNESS, _ROOT)
    covered = {r["mpn"].replace("\\", "/") for r in rows}
    disk    = {p.replace("\\", "/") for p in on_disk()}

    print("templates on disk   : %d" % len(disk))
    print("templates in manifest: %d" % len(covered))

    missing = sorted(disk - covered)
    extra   = sorted(covered - disk)
    print("\n=== on disk but NOT compiled by the harness (%d) ===" % len(missing))
    for m in missing:
        print("  %s" % m)
    print("\n=== in manifest but MISSING on disk (%d) ===" % len(extra))
    for m in extra:
        print("  %s" % m)
    return 1 if (missing or extra) else 0


if __name__ == "__main__":
    raise SystemExit(main())
