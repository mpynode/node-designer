# tests/compile/freshness/test_harness_manifest_coverage.py  (pure -- no setUpModule)
"""The compiled-demos manifest must cover the whole templates TREE.

``tools/harness/run_all.py`` and ``mega_plugin.py`` iterate
``templates.json``; neither ever walks ``templates/``. A template with no row is
therefore never compiled and never audited, yet the run still reports all-green
-- a false pass over a subset. That is how a "41 compiled / 1 dropped" figure
was presented as full coverage while it only ever spanned a 42-row subset of the
43 templates on disk.

Two tools already detect exactly this and already exit 1 on drift
(``tools/sync_harness_manifest.py --check`` and ``tools/list_template_coverage.py``)
-- but no test invoked either, so the drift landed silently anyway. These tests
invoke them, comparing the manifest against the TREE rather than against itself,
and carry their own negative control so the gate cannot quietly go vacuous if a
checker ever stops firing.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from tests import _paths

_ROOT = _paths.ROOT
_HARNESS = os.path.join(_ROOT, "tools", "harness")
_TEMPLATES = os.path.join(_ROOT, "templates")


def _link_dir(target, link):
    """Point ``link`` at the directory ``target`` without copying it.

    ``os.symlink`` on Windows needs SeCreateSymbolicLinkPrivilege, which a
    normal account only has with Developer Mode on; without it the call fails
    with WinError 1314 and this test errored on every stock Windows machine.
    An NTFS junction needs no privilege, and ``shutil.rmtree`` (which
    ``TemporaryDirectory`` uses) removes a junction without recursing into its
    target -- verified here before relying on it, because the target is the
    REAL templates tree. Junctions need an absolute target; ``_TEMPLATES`` is.
    """
    try:
        os.symlink(target, link)
    except OSError as exc:
        if getattr(exc, "winerror", None) != 1314:
            raise
        import _winapi
        _winapi.CreateJunction(target, link)
_MANIFEST = os.path.join(_HARNESS, "templates.json")
_SYNC_TOOL = os.path.join(_ROOT, "tools", "sync_harness_manifest.py")
_COVERAGE_TOOL = os.path.join(_ROOT, "tools", "list_template_coverage.py")

if _HARNESS not in sys.path:
    sys.path.insert(0, _HARNESS)

import demo_specs  # noqa: E402


def _load_tool(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(*argv):
    proc = subprocess.run([sys.executable] + list(argv),
                          capture_output=True, text=True, timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


class TestManifestCoversTheTree(unittest.TestCase):
    def test_every_template_on_disk_has_a_manifest_row(self):
        cov = _load_tool("_list_template_coverage", _COVERAGE_TOOL)
        disk = {p.replace("\\", "/") for p in cov.on_disk()}
        rows = demo_specs.load_templates(_HARNESS, _ROOT)
        covered = {r["mpn"].replace("\\", "/") for r in rows}
        # Without this the two assertions below pass on an empty walk.
        self.assertGreater(len(disk), 30,
                           "found almost no template.mpn under %s" % _TEMPLATES)
        self.assertEqual(
            sorted(disk - covered), [],
            "on disk but NOT in templates.json -- never compiled, never "
            "audited; run tools/sync_harness_manifest.py")
        self.assertEqual(
            sorted(covered - disk), [],
            "in templates.json but MISSING on disk -- a stale row the harness "
            "will try to compile")

    def test_sync_harness_manifest_check_reports_no_drift(self):
        rc, out = _run(_SYNC_TOOL, "--check")
        self.assertEqual(rc, 0, "harness manifest drift:\n" + out)
        self.assertIn("manifest already covers all", out)

    def test_list_template_coverage_reports_no_difference(self):
        rc, out = _run(_COVERAGE_TOOL)
        self.assertEqual(rc, 0, "harness coverage drift:\n" + out)
        self.assertIn("NOT compiled by the harness (0)", out)
        self.assertIn("MISSING on disk (0)", out)


class TestTheDriftCheckersActuallyFire(unittest.TestCase):
    """A gate whose checker never fires IS the defect it is meant to catch, so
    both checkers are run once against a manifest that is known to be short a
    row."""

    DROP = "templates/MPyMesh/Voxelize/template.mpn"

    def _shadow_root(self, tmp):
        """A repo-shaped root: the real templates tree, the real tools, and a
        manifest with ``DROP``'s row removed."""
        os.makedirs(os.path.join(tmp, "tools"))
        shadow_harness = os.path.join(tmp, "tools", "harness")
        os.makedirs(shadow_harness)
        _link_dir(_TEMPLATES, os.path.join(tmp, "templates"))
        shutil.copy(_SYNC_TOOL, os.path.join(tmp, "tools"))
        shutil.copy(_COVERAGE_TOOL, os.path.join(tmp, "tools"))
        shutil.copy(os.path.join(_HARNESS, "demo_specs.py"), shadow_harness)
        with open(_MANIFEST) as fh:
            rows = json.load(fh)
        kept = [r for r in rows
                if r["mpn"].replace("\\", "/") != self.DROP]
        self.assertEqual(len(kept), len(rows) - 1,
                         "%s is not in the manifest to begin with" % self.DROP)
        with open(os.path.join(shadow_harness, "templates.json"), "w") as fh:
            json.dump(kept, fh, indent=1)
        return tmp

    def test_both_tools_exit_nonzero_on_a_missing_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._shadow_root(tmp)
            rc, out = _run(os.path.join(root, "tools",
                                        "sync_harness_manifest.py"), "--check")
            self.assertEqual(rc, 1, "sync --check did not flag the drift:\n" + out)
            self.assertIn(self.DROP, out)
            rc, out = _run(os.path.join(root, "tools",
                                        "list_template_coverage.py"))
            self.assertEqual(rc, 1, "coverage tool did not flag the drift:\n" + out)
            self.assertIn("NOT compiled by the harness (1)", out)
            self.assertIn(self.DROP, out)


if __name__ == "__main__":
    unittest.main()
