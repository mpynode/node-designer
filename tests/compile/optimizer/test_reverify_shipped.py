"""tools/harness/reverify_shipped.py re-runs the build's own verify against a
fresh compile of each shipped node and rewrites only that node's ``verify``
block. These tests pin the planning, the block shape and the manifest
round-trip -- no compile, no Maya."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest

from tests import _paths

_TOOL = os.path.join(_paths.ROOT, "tools", "harness", "reverify_shipped.py")


def _tool():
    spec = importlib.util.spec_from_file_location("reverify_shipped", _TOOL)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_tree(root, *, with_final=True):
    build = os.path.join(root, "templates", "Fam", "Tpl", "build")
    os.makedirs(os.path.join(build, "thing"), exist_ok=True)
    doc = {"manifest_version": 1, "plugin_name": "Fam_Tpl",
           "nodes": [{"type_name": "thing", "spec": {"inputs": {}},
                      "verify": {"ran": False, "pass": None, "maxerr": None,
                                 "tol": None, "reason": "verify could not run: x"},
                      "build_status": "compiled"}],
           "strict": False}
    mf = os.path.join(build, "manifest.json")
    with open(mf, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(doc, indent=2) + "\n")
    if with_final:
        open(os.path.join(build, "thing", "thing.cpp"), "w").write("f")
    return build, mf


class TestPlan(unittest.TestCase):
    def test_every_node_with_a_final_is_planned(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            build, mf = _fake_tree(tmp)
            items, skipped = t.plan(root=tmp)
        self.assertEqual(skipped, [])
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["type_name"],     "thing")
        self.assertEqual(it["row_index"],     0)
        self.assertEqual(it["manifest_path"], mf)
        self.assertIn("could not run", it["old_verify"]["reason"])

    def test_missing_final_is_reported(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            _fake_tree(tmp, with_final=False)
            items, skipped = t.plan(root=tmp)
        self.assertEqual(items, [])
        self.assertEqual(skipped[0][0], "thing")

    def test_only_filter(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            _fake_tree(tmp)
            self.assertEqual(t.plan(root=tmp, only=["other"])[0], [])


class TestBlockAndManifest(unittest.TestCase):
    def test_finish_block_adds_generic_ran_and_date(self):
        t = _tool()
        b = t.finish_block({"ran": True, "pass": True, "maxerr": 0.0, "tol": 1e-4,
                            "reason": ""}, date="2026-09-08")
        self.assertTrue(b["generic_ran"])
        self.assertEqual(b["reverified"], "2026-09-08")
        # a merged block already says what the generic run was: kept
        b2 = t.finish_block({"ran": True, "pass": True, "generic_ran": False,
                             "authored_test": {"ran": True}}, date="d")
        self.assertFalse(b2["generic_ran"])

    def test_write_block_touches_only_the_verify_block(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            build, mf = _fake_tree(tmp)
            before = open(mf, encoding="utf-8").read()
            items, _ = t.plan(root=tmp)
            new = {"ran": True, "pass": True, "maxerr": 0.0, "tol": 1e-4,
                   "reason": "", "generic_ran": True, "reverified": "2026-09-08"}
            t.write_block(items[0], new)
            after = open(mf, encoding="utf-8").read()
            doc   = json.loads(after)
        self.assertEqual(doc["nodes"][0]["verify"], new)
        self.assertEqual(list(doc.keys()), ["manifest_version", "plugin_name", "nodes", "strict"])
        self.assertTrue(after.endswith("}\n"))
        self.assertNotIn("\r", after)
        # everything but the verify block is byte-identical
        strip = lambda s: "\n".join(l for l in s.splitlines() if '"verify"' not in l)
        self.assertEqual(len(strip(before).splitlines()) + 2, len(strip(after).splitlines()))

    def test_short_and_gate(self):
        t = _tool()
        self.assertTrue(t.short({"ran": False, "reason": "no"}).startswith("SKIP"))
        self.assertTrue(t.short({"ran": True, "pass": True, "maxerr": 1e-9,
                                 "tol": 1e-4}).startswith("PASS"))
        self.assertTrue(t.short({"ran": True, "pass": False, "maxerr": 0.5,
                                 "tol": 1e-4}).startswith("FAIL"))
        self.assertEqual(t.gate_of({"ran": True, "generic_ran": False,
                                    "authored_test": {"ran": True}}), "authored-only")


if __name__ == "__main__":
    unittest.main()
