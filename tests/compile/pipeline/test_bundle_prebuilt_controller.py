"""The compile controller's two ways of taking nodes that are ALREADY compiled.

``bundle_prebuilt`` makes a plug-in of nothing but compiled sources -- the
Compile dialog's path when every checked row is "Compiled C++" -- and returns
the same result dict ``compile_plugin`` does, so the dialog's finish path
(summary, warnings, the offer to load) serves it unchanged. ``compile_plugin``
itself takes ``prebuilt=`` sources beside its specs: they join the link as
they are, and a clash with each other or with a spec is refused at
pre-flight, before any port.

Text only: ``compile_now=False`` writes the re-buildable tree without a
compiler, and the ``compile_plugin`` test replaces the assembler.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from tests.compile.pipeline.test_native_bundle import _src, _write, _devkit


class TestBundlePrebuilt(unittest.TestCase):

    def setUp(self):
        self.d    = tempfile.mkdtemp(prefix="bp_ctl_")
        self.maya = _devkit(self.d)
        self.a    = _write(self.d, "in/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        self.b    = _write(self.d, "in/bNode.cpp", _src("bNode", "BNode", "0x00081001"))

    def test_a_generated_tree_comes_back_in_the_controllers_shape(self):
        from mpynode.native.toolchain import compile_controller as cc

        events = []
        res = cc.bundle_prebuilt([self.a, self.b], "duo", os.path.join(self.d, "out"),
                                 maya=self.maya, compile_now=False,
                                 progress_cb=events.append)
        self.assertTrue(res["ok"], res)
        self.assertTrue(res["prebuilt"])
        self.assertEqual([r["type_name"] for r in res["nodes"]], ["aNode", "bNode"])
        self.assertEqual({r["build_status"] for r in res["nodes"]}, {"generated"})
        self.assertEqual(res["nodes"][0]["cache"], "prebuilt")
        self.assertFalse(res["nodes"][0]["verify"]["ran"])
        self.assertTrue(os.path.isfile(res["manifest_path"]))
        self.assertEqual(res["companions"], [])
        stages = [(e["stage"], e["status"]) for e in events]
        self.assertIn(("assemble", "start"), stages)
        self.assertEqual(stages[-1], ("done", "ok"))

    def test_a_refused_set_never_reaches_the_bundler(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.compiler import bundler

        dup = _write(self.d, "dup/bNode.cpp", _src("bNode", "BNode", "0x00081000"))  # a's id
        with mock.patch.object(bundler, "assemble") as asm:
            res = cc.bundle_prebuilt([self.a, dup], "duo", os.path.join(self.d, "out"),
                                     maya=self.maya, compile_now=False)
        self.assertFalse(res["ok"])
        self.assertIn("E4", res["errors"][0])
        self.assertEqual(asm.call_count, 0)

    def test_two_targets_give_the_multi_version_shape(self):
        from mpynode.native.toolchain import compile_controller as cc

        targets = [{"label": "Maya2025", "root": self.maya, "version": "2025"},
                   {"label": "Maya2027", "root": self.maya, "version": "2027"}]
        res = cc.bundle_prebuilt([self.a], "duo", os.path.join(self.d, "out"),
                                 targets=targets, compile_now=False)
        self.assertTrue(res["multi"])
        self.assertTrue(res["ok"], res)
        self.assertEqual([r["label"] for r in res["results"]], ["Maya2025", "Maya2027"])
        # One folder per version, named by the bare year -- never the label.
        self.assertEqual([r["out_dir"] for r in res["results"]],
                         [os.path.join(self.d, "out", y) for y in ("2025", "2027")])
        for r in res["results"]:
            self.assertTrue(r["result"]["ok"])
            self.assertTrue(os.path.isfile(os.path.join(r["out_dir"], "build", "manifest.json")))

    def test_start_bundle_runs_it_on_the_worker(self):
        from mpynode.native.toolchain import compile_controller as cc

        done   = threading.Event()
        events = []

        def cb(ev):
            events.append(ev)
            if ev.get("stage") == "done":
                done.set()

        ctl = cc.CompileController(progress_cb=cb)
        t = ctl.start_bundle([self.a, self.b], "duo", os.path.join(self.d, "out"),
                             maya=self.maya, compile_now=False)
        t.join(60)
        self.assertTrue(done.wait(1))
        self.assertFalse(ctl.is_busy())
        self.assertTrue(ctl.result["ok"], ctl.result)


class TestCompilePluginTakesPrebuilt(unittest.TestCase):
    """``compile_plugin(prebuilt=...)`` with no specs: the assembler is handed
    the compiled sources, their ids are claimed, and the manifest carries a
    row per member."""

    def setUp(self):
        self.d    = tempfile.mkdtemp(prefix="bp_cp_")
        self.maya = _devkit(self.d)
        self.a    = _write(self.d, "in/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        self.b    = _write(self.d, "in/bNode.cpp", _src("bNode", "BNode", "0x00081001"))

    def _fake_assemble(self, calls):
        def assemble(nodes, plugin_name, out_dir, **kw):
            calls.append((list(nodes), kw))
            os.makedirs(out_dir, exist_ok=True)
            bundle = os.path.join(out_dir, plugin_name + ".mll")
            open(bundle, "wb").close()
            return {"plugin": plugin_name, "bundle": bundle, "ok": True, "dropped": [],
                    "nodes": [{"name": n, "status": "compiled", "id": kw["registry"]
                               .allocate_many([n])[n], "reason": ""} for n, _p in nodes]}
        return assemble

    def test_prebuilt_sources_reach_the_assembler_with_their_ids(self):
        from mpynode.native.toolchain import compile_controller as cc, toolchain
        from mpynode.native.compiler import bundler

        calls = []
        with mock.patch.object(toolchain, "check_toolchain", return_value={"ok": True}), \
             mock.patch.object(bundler, "assemble", side_effect=self._fake_assemble(calls)):
            res = cc.compile_plugin([], "duo", os.path.join(self.d, "out"),
                                    verify=False, maya=self.maya, ai_assist=False,
                                    prebuilt=[self.a, self.b])
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(calls), 1)
        nodes, kw = calls[0]
        self.assertEqual([n for n, _p in nodes], ["aNode", "bNode"])
        self.assertEqual(kw["registry"].allocate_many(["aNode"]), {"aNode": "0x00081000"})
        rows = {r["type_name"]: r for r in res["nodes"]}
        self.assertEqual(rows["aNode"]["cache"], "prebuilt")
        self.assertEqual(rows["aNode"]["type_id"], "0x00081000")
        self.assertIsNone(rows["aNode"]["spec"])
        with open(res["manifest_path"]) as fh:
            man = json.load(fh)
        self.assertEqual([r["type_name"] for r in man["nodes"]], ["aNode", "bNode"])

    def test_a_clash_is_refused_before_anything_is_ported(self):
        from mpynode.native.toolchain import compile_controller as cc, toolchain
        from mpynode.native.compiler import bundler

        dup   = _write(self.d, "dup/aNode.cpp", _src("aNode", "ANode", "0x00081002"))
        calls = []
        with mock.patch.object(toolchain, "check_toolchain", return_value={"ok": True}), \
             mock.patch.object(bundler, "assemble", side_effect=self._fake_assemble(calls)):
            res = cc.compile_plugin([], "duo", os.path.join(self.d, "out"),
                                    verify=False, maya=self.maya, ai_assist=False,
                                    prebuilt=[self.a, dup])
        self.assertFalse(res["ok"])
        self.assertIn("E1", res["errors"][0])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
