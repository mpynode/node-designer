"""The artifact that actually LINKS must carry the current emitter's output.

``test_stage1_codegen_freshness`` gates ``build/stages/<ty>/1_transpiled.cpp``,
which is regenerated from the manifest spec on every run and is therefore always
today's codegen. That is NOT what ships. What ships is
``build/<ty>/<ty>.cpp`` -- the optimizer's promoted winner -- and it is produced
through the PORT CACHE, whose key is (spec + PORTER_RECIPE_VERSION). An
emitter-only change moves neither, so a HIT is a ``shutil.copyfile`` with codegen
SKIPPED and the shipped artifact keeps the OLD emitter's output while stage 1
shows the new one. ``port_cache.py``'s own header has recorded that trap four
times; the fourth reached a shipped bundle.

Measured, the day this test was written: ``fileTexture`` and ``scanlineTex``
shipped in mPyMega with ZERO ``nd_png`` symbols while their own
``1_transpiled.cpp`` carried 31, and a compiled ``fileTexture`` disagreed with
the interpreted one by 3.69e-01. ``compositeTexture`` escaped only because its
spec happened to move that day (it adopted ``composite_layers``). Every gate in
the suite was green.

The fix for a failure here is to BUMP ``PORTER_RECIPE_VERSION`` and rebuild the
named templates -- not to edit this test.
"""

from __future__ import annotations

import json
import os
import re
import unittest
from tests import _paths

_ROOT = _paths.ROOT
_SRC_TEMPLATES = os.path.join(_ROOT, "templates")
# The compiled trees now live inside the templates they were generated from, so
# the walk root and the source root are one and the same.
_CT = _SRC_TEMPLATES

_BUILD_HASH = re.compile(r"^// build:\s*([0-9a-f]+)", re.M)


def _build_hash(path):
    """The emitter's own stamp, or None if the file has none."""
    try:
        with open(path) as fh:
            head = fh.read(4000)
    except OSError:
        return None
    m = _BUILD_HASH.search(head)
    return m.group(1) if m else None


def _read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return ""


def _nodes():
    """Every (family, template, type, paths) the compiled tree ships.

    A build tree whose SOURCE template no longer exists is skipped and reported
    separately: it cannot be rebuilt, so gating it would be a permanent red with
    no action available.
    """
    live, orphaned = [], []
    if not os.path.isdir(_CT):
        return live, orphaned
    for fam in sorted(os.listdir(_CT)):
        fdir = os.path.join(_CT, fam)
        if not os.path.isdir(fdir):
            continue
        for tpl in sorted(os.listdir(fdir)):
            build = os.path.join(fdir, tpl, "build")
            man = os.path.join(build, "manifest.json")
            if not os.path.isfile(man):
                continue
            try:
                with open(man) as fh:
                    rows = json.load(fh).get("nodes") or []
            except (OSError, ValueError):
                continue
            # Ask for the template.mpn, not the directory: the directory is the
            # one the walk is standing in, so isdir() is now always True and the
            # orphan gate would go permanently empty without saying so.
            has_source = os.path.isfile(
                os.path.join(_SRC_TEMPLATES, fam, tpl, "template.mpn"))
            for row in rows:
                ty = row.get("type_name")
                if not ty:
                    continue
                stages = os.path.join(build, "stages", ty)
                entry = {
                    "rel": "%s/%s" % (fam, tpl),
                    "type": ty,
                    "stage1": os.path.join(stages, "1_transpiled.cpp"),
                    "baseline": os.path.join(stages, "3_optimized",
                                             "00_baseline.cpp"),
                    "final": os.path.join(build, ty, ty + ".cpp"),
                }
                if not os.path.isfile(entry["final"]):
                    continue
                (live if has_source else orphaned).append(entry)
    return live, orphaned


class TestShippedArtifactsAreFresh(unittest.TestCase):

    def test_the_artifacts_are_actually_on_disk(self):
        """Non-vacuity: every assertion below iterates the same list, so an
        empty one would make all of them pass."""
        live, _ = _nodes()
        self.assertGreater(
            len(live), 30,
            "found almost no shipped artifacts under %s -- the freshness "
            "assertions below would be vacuous" % _CT)

    def test_no_shipped_artifact_came_from_a_stale_port_cache(self):
        """The cache-hit tell: the optimizer's baseline carries a DIFFERENT
        emitter stamp than the stage-1 the same build produced."""
        live, _ = _nodes()
        stale = []
        for e in live:
            t1 = _build_hash(e["stage1"])
            base = _build_hash(e["baseline"])
            if t1 is None or base is None:
                continue          # no optimizer stage for this node
            if t1 != base:
                stale.append("%s (%s): 1_transpiled=%s but 00_baseline=%s"
                             % (e["rel"], e["type"], t1, base))
        self.assertEqual(
            stale, [],
            "shipped artifact(s) were served from a STALE port cache -- their "
            "C++ predates the current emitter even though stage 1 does not. "
            "Bump PORTER_RECIPE_VERSION in "
            "scripts/mpynode/native/toolchain/port_cache.py (with a note "
            "saying why, as every prior bump does) and rebuild these with "
            "tools/build_compiled_templates.sh --only \"<template>\" --force:"
            "\n  " + "\n  ".join(stale))

    def test_no_shipped_artifact_caps_the_vp2_bake(self):
        """A cap has no Python analogue: the interpreted tier uploads at full
        resolution, so a capped bake hands VP2 a different-sized texture and its
        filtering makes the two tiers disagree EVERYWHERE, not just on the rows
        the cap dropped."""
        live, orphaned = _nodes()
        capped = ["%s (%s)" % (e["rel"], e["type"])
                  for e in live + orphaned
                  if "_kMaxBake" in _read(e["final"])]
        self.assertEqual(
            capped, [],
            "shipped artifact(s) still clamp the VP2 CPU bake. The cap was "
            "removed from emit_vp2_override; these predate that. Rebuild "
            "them:\n  " + "\n  ".join(capped))

    def test_texture_readers_ship_the_exact_decoder(self):
        """If today's codegen gives a node the exact PNG decoder, the artifact
        that LINKS must have it too. This is the specific shape of the defect
        that shipped: stage 1 had 31 nd_png, the linked artifact had 0."""
        live, _ = _nodes()
        missing = []
        for e in live:
            if "nd_png" not in _read(e["stage1"]):
                continue          # not a texture reader; nothing to require
            if "nd_png" not in _read(e["final"]):
                missing.append("%s (%s)" % (e["rel"], e["type"]))
        self.assertEqual(
            missing, [],
            "stage 1 emits the exact PNG decoder for these nodes but the "
            "SHIPPED artifact does not -- they decode through MImage, which "
            "premultiplies and quantises to 8 bits, so the compiled node "
            "disagrees with the interpreted one. Bump PORTER_RECIPE_VERSION "
            "and rebuild:\n  " + "\n  ".join(missing))

    def test_orphaned_build_trees_are_named(self):
        """A build tree with no source template cannot be rebuilt, so the gates
        above skip it. Keep that list SHORT and visible rather than silent."""
        _, orphaned = _nodes()
        rels = sorted({e["rel"] for e in orphaned})
        self.assertEqual(
            rels, ["MPyFile/File Brightness Contrast"],
            "the set of compiled build trees with no source template under "
            "templates/ changed. These are skipped by the freshness gates "
            "above because nothing can regenerate them. If a template was "
            "deliberately retired, update this list; if one went missing by "
            "accident, restore it. Found: %r" % (rels,))


if __name__ == "__main__":
    unittest.main()
