"""Regression guard for the offline optimizer driver (tools/harness/
optimize_node.py): it must compile candidates into an ISOLATED scratch dir, never
the source directory. make_adapters.compile_fn writes ``<out_dir>/<node>.cpp`` for
EVERY candidate (baseline + each optimize/fix round) before the parity+speed gate,
so if the driver handed it ``dirname(source)`` that path would equal the real
source and every proposed/rejected candidate would clobber the hand-tuned
original -- silent data loss on any reject / preview run.

The driver lives outside the mpynode package; add the harness dir to sys.path.
The compile/LLM/provider side channels are patched, so no clang / Maya / LLM run.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from tests import _paths

_ROOT = _paths.ROOT
_HARNESS = os.path.join(_ROOT, "tools", "harness")
if _HARNESS not in sys.path:
    sys.path.insert(0, _HARNESS)

import optimize_node  # noqa: E402
from mpynode.native.ai import optimizer, optimizer_live  # noqa: E402
from mpynode.native.ai import llm_client  # noqa: E402


class TestOptimizeNodeScratchIsolation(unittest.TestCase):
    def test_candidates_never_compile_into_the_source_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            srcdir = os.path.join(tmp, "build", "source")
            os.makedirs(srcdir)
            src = os.path.join(srcdir, "metaClay.cpp")
            with open(src, "w") as fh:
                fh.write("ORIGINAL_HANDTUNED")
            spec_path = os.path.join(tmp, "spec.json")
            with open(spec_path, "w") as fh:
                json.dump({"suggested": {"node_type_name": "metaClay",
                                         "mpx_base": "MPxNode"}}, fh)

            captured = {}

            def fake_make_adapters(spec, out_dir, **kw):
                captured["out_dir"] = out_dir
                return {"optimize_fn": lambda c: c, "fix_fn": lambda c, e: c,
                        "compile_fn": lambda c: (True, "", "b"),
                        "parity_fn": lambda b: None,
                        "benchmark_fn": lambda b: None}

            # Honest reject: nothing accepted, so the source must be untouched.
            def fake_optimize_cpp(baseline, **kw):
                return optimizer.OptimizeResult(
                    False, baseline, 100.0, 100.0, 1.0, 1, [], "no gain")

            argv = ["optimize_node.py", "--source", src, "--spec", spec_path]
            with mock.patch.object(llm_client, "check_provider",
                                   lambda *a, **k: {"ok": True}), \
                 mock.patch.object(optimizer_live, "make_adapters",
                                   fake_make_adapters), \
                 mock.patch.object(optimizer, "optimize_cpp", fake_optimize_cpp), \
                 mock.patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit):
                    optimize_node.main()

            # The compile scratch dir the driver handed the adapters must NOT be
            # the source dir, and the path compile_fn would write (<out_dir>/
            # metaClay.cpp) must NOT be the real source.
            self.assertIn("out_dir", captured)
            self.assertNotEqual(os.path.abspath(captured["out_dir"]),
                                os.path.abspath(srcdir))
            self.assertNotEqual(
                os.path.abspath(os.path.join(captured["out_dir"], "metaClay.cpp")),
                os.path.abspath(src))
            # And the untouched original is still on disk.
            with open(src) as fh:
                self.assertEqual(fh.read(), "ORIGINAL_HANDTUNED")


if __name__ == "__main__":
    unittest.main()
