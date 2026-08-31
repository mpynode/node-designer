# scripts/mpynode/_tests/test_stage1_codegen_freshness.py
"""Every checked-in stage-1 C++ artifact must equal what the transpiler emits.

``build/stages/<Type>/1_transpiled.cpp`` is pure transpiler output --
``codegen.generate_cpp(spec, for_port=True)``, the exact call
``compile_controller.py:783`` makes. The build's ``manifest.json`` embeds the
FULL spec each node was keyed with, so the artifact can be re-derived from disk
and compared byte for byte without re-running a build (no compiler, no linker,
no AI). ``tools/check_stage1_freshness.py`` does the deriving; this module is
the gate over its result.

Nothing compared them before, so the tree quietly accumulated drift: the
artifacts predate the array-output-builder fix
(``MArrayDataBuilder _b = _outArr.builder();`` -> ``_b(&data, aX, n)``) and the
register-blocked reduction kernels, among others. A substring probe
(``test_mega_stage1_freshness``) catches ONE known staleness class; this catches
every class, including ones nobody has thought of.

WHY A BASELINE. 32 of the 45 artifacts were already stale when this landed, and
a gate that goes red on arrival gets disabled. So the known-stale set is checked
in as data (``data/stage1_stale_baseline.json``) and the gate is a RATCHET:

  * an artifact NOT in the baseline must match fresh codegen  -- catches new drift
  * an artifact IN the baseline must STILL be stale           -- forces the list to shrink

Both directions matter. Without the second, the baseline becomes a permanent
blanket; with it, refreshing an artifact is only "done" once its line is
deleted. A newly added node is gated by default, so the hole cannot grow
silently. The current count is printed on every run, pass or fail.

HASH SEED. Codegen order was process-dependent before ``T69``
(``nd_lower`` iterated a set of attribute names). That is fixed and pinned by
``test_nd_lower_determinism``, and measured here: the 45 artifacts hash
identically under ``PYTHONHASHSEED`` 0 / 7 / 12345. The subprocess still forces
``PYTHONHASHSEED=0`` so that a re-introduction anywhere in codegen shows up as a
transpiler regression rather than as this gate flapping.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_CHECKER = os.path.join(_ROOT, "tools", "check_stage1_freshness.py")
_BASELINE = os.path.join(_HERE, "data", "stage1_stale_baseline.json")

# Measured 2026-08-13: 45 artifacts, 5 manifests. Floors, not equalities -- the
# point is that a path rename or a manifest-shape change cannot turn this suite
# into a no-op that passes on an empty measurement.
_MIN_ARTIFACTS = 40
_MIN_MANIFESTS = 4

_RESULT = None


def _mayapy():
    """The interpreter for the child -- mayapy, never the Maya GUI binary.

    Under the headless runner ``sys.executable`` IS mayapy. Inside a GUI session
    it is ``Maya`` itself, and handing that a script path opens a whole second
    Maya, so look for mayapy beside it and in the sibling ``bin/`` first.
    """
    here = os.path.dirname(sys.executable)
    for cand in (os.path.join(here, "mayapy"),
                 os.path.join(os.path.dirname(here), "bin", "mayapy")):
        if os.path.isfile(cand):
            return cand
    return sys.executable


def _measure():
    """Fresh-vs-shipped for every stage-1 artifact, from a seeded subprocess."""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    out = os.path.join(tempfile.mkdtemp(prefix="mpynode-stage1-"),
                       "freshness.json")
    proc = subprocess.run([_mayapy(), _CHECKER, "--json", out],
                          capture_output=True, text=True, env=env)
    if proc.returncode != 0 or not os.path.isfile(out):
        raise AssertionError(
            "tools/check_stage1_freshness.py failed (rc=%d):\n%s\n%s"
            % (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:]))
    with open(out) as fh:
        return json.load(fh)


def _baseline():
    with open(_BASELINE) as fh:
        return json.load(fh)["stale"]


def _by_state(result, state):
    return sorted(rel for rel, row in result["artifacts"].items()
                  if row["state"] == state)


def setUpModule():
    global _RESULT
    _RESULT = _measure()
    stale = _by_state(_RESULT, "stale")
    known = set(_baseline())
    # The count, on every run, pass or fail: a tolerated stale set that nobody
    # can see is the thing this gate exists to prevent.
    sys.stderr.write(
        "[stage-1 freshness] %d checked / %d fresh / %d stale "
        "(%d baselined, %d unexpected) / %d error / %d absent / %d ungated\n"
        % (len(_RESULT["artifacts"]), len(_by_state(_RESULT, "fresh")),
           len(stale), len([r for r in stale if r in known]),
           len([r for r in stale if r not in known]),
           len(_by_state(_RESULT, "error")), len(_RESULT["absent"]),
           len(_RESULT["unmatched"])))


class TestStageOneMeasurementIsReal(unittest.TestCase):
    """Guards the gate itself -- everything below is vacuous without these."""

    def test_enough_artifacts_were_actually_compared(self):
        self.assertGreaterEqual(
            len(_RESULT["manifests"]), _MIN_MANIFESTS,
            "found %d build manifests; the walk in check_stage1_freshness.py "
            "stopped seeing them" % len(_RESULT["manifests"]))
        self.assertGreaterEqual(
            len(_RESULT["artifacts"]), _MIN_ARTIFACTS,
            "compared %d stage-1 artifacts; the rest of this suite would pass "
            "on an empty measurement" % len(_RESULT["artifacts"]))

    def test_codegen_ran_under_a_pinned_hash_seed(self):
        self.assertEqual(
            _RESULT["pythonhashseed"], "0",
            "the checker subprocess did not inherit PYTHONHASHSEED=0, so any "
            "diff it reports may be emission ORDER rather than drift")

    def test_no_artifact_on_disk_is_left_ungated(self):
        """An artifact whose type has no manifest row cannot be re-derived, so
        drift in it is invisible -- the ungated-checker class of T6/T62/T86."""
        self.assertEqual(
            _RESULT["unmatched"], [],
            "%d stage-1 artifact(s) sit next to a manifest that carries no spec "
            "row for them, so nothing compares them:\n  %s"
            % (len(_RESULT["unmatched"]), "\n  ".join(_RESULT["unmatched"])))

    def test_no_artifact_failed_to_transpile(self):
        broken = [(rel, _RESULT["artifacts"][rel].get("detail"))
                  for rel in _by_state(_RESULT, "error")]
        self.assertEqual(
            broken, [],
            "generate_cpp raised for these specs -- the gate cannot judge them "
            "either way:\n  " + "\n  ".join("%s: %s" % b for b in broken))


class TestTheUngatedScanIsNotDerivedFromParsedManifests(unittest.TestCase):
    """T109. ``test_no_artifact_on_disk_is_left_ungated`` above is only as good
    as the SEARCH that feeds it. Deriving that search from the manifests that
    PARSED means a build tree whose ``manifest.json`` is missing or unreadable
    contributes no artifacts to compare AND no artifacts to the ungated list --
    it reports a clean ``0 ungated`` for the exact hole the check exists to
    find. Driven over a synthetic tree so the real one stays untouched."""

    def _collect_over(self, root, trees):
        tools_dir = os.path.join(_ROOT, "tools")
        if tools_dir not in sys.path:
            sys.path.append(tools_dir)
        import check_stage1_freshness as checker

        was = (checker.ROOT, checker.TREES)
        checker.ROOT, checker.TREES = root, trees
        try:
            return checker.collect()
        finally:
            checker.ROOT, checker.TREES = was

    def _tree(self, manifest_body):
        root = tempfile.mkdtemp(prefix="mpynode-t109-")
        build = os.path.join(root, "compiled_templates", "probe", "build")
        os.makedirs(os.path.join(build, "stages", "probeNode"))
        if manifest_body is not None:
            with open(os.path.join(build, "manifest.json"), "w") as fh:
                fh.write(manifest_body)
        with open(os.path.join(build, "stages", "probeNode",
                               "1_transpiled.cpp"), "w") as fh:
            fh.write("// stage 1\n")
        # collect() reports repo-relative paths in the canonical "/" form (the
        # baseline is shared across platforms), so compare against that.
        return root, "compiled_templates/probe/build/stages/probeNode/1_transpiled.cpp"

    def _assert_seen(self, manifest_body, label):
        root, rel = self._tree(manifest_body)
        result = self._collect_over(root, ("compiled_templates",))
        self.assertEqual(
            result["artifacts"], {},
            "%s: nothing should have been re-derivable" % label)
        self.assertEqual(
            result["unmatched"], [rel],
            "%s: the artifact on disk was not reported as ungated, so the "
            "gate is green over an artifact nothing compares" % label)

    def test_an_unparseable_manifest_still_exposes_its_artifacts(self):
        self._assert_seen("{ not json at all", "unparseable manifest")

    def test_a_missing_manifest_still_exposes_its_artifacts(self):
        self._assert_seen(None, "no manifest")

    def test_a_manifest_without_a_nodes_list_still_exposes_its_artifacts(self):
        self._assert_seen('{"rows": []}', "manifest with no nodes list")


class TestStageOneArtifactsAreFresh(unittest.TestCase):
    """The gate: a ratchet over data/stage1_stale_baseline.json."""

    def test_artifacts_outside_the_baseline_match_fresh_codegen(self):
        known = set(_baseline())
        drifted = [rel for rel in _by_state(_RESULT, "stale")
                   if rel not in known]
        lines = []
        for rel in drifted:
            d = _RESULT["artifacts"][rel].get("detail") or {}
            lines.append("%s (first diff line %s, %s -> %s lines)"
                         % (rel, d.get("first_diff_line"),
                            d.get("shipped_lines"), d.get("fresh_lines")))
        self.assertEqual(
            drifted, [],
            "%d checked-in stage-1 artifact(s) no longer match what the "
            "transpiler emits. In preference order: (1) the emitter change is "
            "wrong -- fix it; (2) refresh the artifacts, `mayapy "
            "tools/regen_mega_transpiled.py` (codegen only, no compiler); "
            "(3) accept the drift with `mayapy tools/check_stage1_freshness.py "
            "--write-baseline`, which leaves a reviewable +N diff naming every "
            "artifact you just wrote off. Deleting this test is not on the "
            "list:\n  %s" % (len(drifted), "\n  ".join(lines)))

    def test_baseline_only_lists_artifacts_that_are_still_stale(self):
        fresh = set(_by_state(_RESULT, "fresh"))
        healed = sorted(rel for rel in _baseline() if rel in fresh)
        self.assertEqual(
            healed, [],
            "%d baselined artifact(s) now MATCH fresh codegen. Delete their "
            "lines from %s -- the known-stale list is only allowed to "
            "shrink:\n  %s"
            % (len(healed), os.path.relpath(_BASELINE, _ROOT),
               "\n  ".join(healed)))

    def test_baseline_only_lists_artifacts_that_were_measured(self):
        measured = set(_RESULT["artifacts"])
        orphans = sorted(rel for rel in _baseline() if rel not in measured)
        self.assertEqual(
            orphans, [],
            "%d baselined path(s) were not compared at all -- a typo or a "
            "deleted artifact, either way the exemption is dead weight and may "
            "be masking a real path:\n  %s"
            % (len(orphans), "\n  ".join(orphans)))


if __name__ == "__main__":
    unittest.main()
