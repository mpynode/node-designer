"""Controller-level divergence guard (must-fix #1 backstop).

In the per-Class model, multiple INSTANCES of one Class compile to the SAME
native type. The controller must:

* collapse genuinely-IDENTICAL instances to one representative (compile the
  Class once) instead of aborting as a "duplicate type", and
* refuse to silently mis-compile DIVERGED instances (Duplicate-then-edit) --
  surfacing an actionable "fork the divergent instance" error instead.

Both paths are exercised without real codegen: the specs are marked non-portable
so they drop at the portability gate (best-effort), which is AFTER the
divergence guard -- so the guard's decision is observed with no compiler/LLM
work. Gated on a working native toolchain (the pre-flight runs before the loop).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestControllerDivergenceGuard(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.native.toolchain import toolchain
        from mpynode.native.toolchain import compile_controller as cc

        if not toolchain.check_toolchain(cc._MAYA_DEFAULT).get("ok"):
            self.skipTest("no native toolchain on this host")

    def _make_pair(self, name_a, name_b, expr_a, expr_b, cls="WidgetGuard"):
        """Two instances of ONE Class with the given compute expressions,
        returned as (non-portable) porter specs sharing one node_type_name."""
        from mpynode import MPyNode
        from mpynode._common.io.user_classes import synthesize, dotted_path
        from mpynode.native.spec import spec_extractor

        synthesize(cls, "mPyNode")
        a = MPyNode.create(name=name_a)
        a.set_compute_expression(expr_a)
        a.set_py_class(dotted_path(cls))
        b = MPyNode.create(name=name_b)
        b.set_compute_expression(expr_b)
        b.set_py_class(dotted_path(cls))
        specs = [spec_extractor.extract_spec(a.get_name()),
                 spec_extractor.extract_spec(b.get_name())]
        # Both derive their type from the shared Class -> same node_type_name.
        self.assertEqual(specs[0]["suggested"]["node_type_name"],
                         specs[1]["suggested"]["node_type_name"])
        # Force non-portable so they drop at the portability gate (no codegen),
        # AFTER the divergence guard has already decided.
        for s in specs:
            s["portability"] = {"portable": False, "blockers": ["test-forced"]}
        return specs

    def _compile(self, specs):
        from mpynode.native.toolchain import compile_controller as cc

        events = []
        res = cc.compile_plugin(
            specs, "divGuardPlug", tempfile.mkdtemp(prefix="divguard_"),
            strict=False, verify=False, reuse_cache=False,
            complete_fn=lambda *a, **k: "",
            progress_cb=lambda ev: events.append(ev))
        return res, events

    def test_diverged_instances_are_flagged_with_actionable_message(self):
        specs = self._make_pair("ccDivA", "ccDivB", "out = x + 1", "out = x + 2")
        res, _events = self._compile(specs)
        reasons = " ".join(r.get("build_reason", "") for r in res["nodes"])
        self.assertIn("diverged", reasons.lower())
        # The drop reason tells the user how to resolve it (fork the instance);
        # this same string is what strict mode appends to `errors` and aborts on.
        self.assertIn("fork", reasons.lower())
        self.assertFalse(res["ok"])

    def test_identical_instances_collapse_silently(self):
        specs = self._make_pair("ccIdA", "ccIdB", "out = x + 1", "out = x + 1")
        res, events = self._compile(specs)
        reasons = " ".join(r.get("build_reason", "") for r in res["nodes"])
        # The second instance must NOT be reported as a divergence...
        self.assertNotIn("diverged", reasons.lower())
        # ...it is collapsed to the first (an 'info' event, no divergence drop).
        collapsed = [e for e in events
                     if "collapsed identical" in (e.get("detail") or "")]
        self.assertTrue(collapsed, "expected a 'collapsed identical' info event")


if __name__ == "__main__":
    unittest.main()
