"""Every shipped verify_in_maya.py is what the generator emits for its spec.

The porter writes ``build/<type>/verify_in_maya.py`` from
``native.ai.verify_scripts._verify_script(spec)`` when a template is built,
and nothing rewrote them after a generator change. On 2026-10-15, 28 of the 38
no longer matched: the ``position`` type was missing from 28 samplers, 4 named
the macOS ``.bundle`` instead of the ``.mll`` and sineRippleDefault's still
called ``mpynode.wrap``, which no longer exists. They were regenerated when
the scripts began fitting each pick inside the attr's range.

Later the same day every script became one program: embed the spec, run
``verify._verify_one``, the pipeline's own check, and report its row. The
deformer, IK and scalar scripts had carried their own sample / set / fit
code, and 17 of the 38 raised when run on their own (array, mesh, string,
matrix, colour and connected time inputs).

``tools/regen_verify_scripts.py`` does the regenerating; this module is the
gate over its result. Compared line by line with whitespace runs collapsed
(the tool's ``matches``): the align sweep columnises the shipped copies, and
that is the only difference allowed.
"""

from __future__ import annotations

import ast
import glob
import importlib.util
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _paths
from tests._setup import standalone_init

_TOOL  = os.path.join(_paths.ROOT, "tools", "regen_verify_scripts.py")
_REGEN = None


def setUpModule():
    global _REGEN
    standalone_init()
    spec   = importlib.util.spec_from_file_location("regen_verify_scripts", _TOOL)
    _REGEN = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_REGEN)


def _shipped():
    """``(relpath, spec, text)`` for every shipped verify script."""
    out = []
    for path, _ty, spec in _REGEN.shipped(_paths.ROOT):
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        out.append((os.path.relpath(path, _paths.ROOT).replace("\\", "/"),
                    spec, text))
    return out


def _finals():
    """Every shipped final, ``build/<type>/<type>.cpp``, as ``build/<type>``."""
    out = []
    for pat in ("templates/*/build/*/*.cpp", "templates/*/*/build/*/*.cpp"):
        for p in glob.glob(os.path.join(_paths.ROOT, pat)):
            d = os.path.dirname(p)
            if os.path.basename(p) == os.path.basename(d) + ".cpp":
                out.append(os.path.relpath(d, _paths.ROOT).replace("\\", "/"))
    return sorted(out)


class TestShippedVerifyScripts(unittest.TestCase):
    def test_there_is_one_per_shipped_final(self):
        have = sorted(os.path.dirname(rel) for rel, _s, _t in _shipped())
        self.assertEqual(have, _finals())
        self.assertTrue(have, "no shipped finals found")

    def test_each_matches_the_generator(self):
        from mpynode.native.ai import verify_scripts

        stale = []
        for rel, spec, text in _shipped():
            ast.parse(text)
            if not _REGEN.matches(text, verify_scripts._verify_script(spec)):
                stale.append(rel)
        self.assertEqual(stale, [],
                         "stale verify_in_maya.py -- regenerate with:\n"
                         "  mayapy tools/regen_verify_scripts.py")

    def test_each_runs_the_pipeline_check_on_its_own_spec(self):
        # One parity implementation: the only function is run(), it calls
        # verify._verify_one, and SPEC is the manifest row's spec.
        for rel, spec, text in _shipped():
            tree = ast.parse(text)
            funcs = [n.name for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.Lambda))]
            self.assertEqual(funcs, ["run"], rel)
            calls = [ast.unparse(n.func) for n in ast.walk(tree)
                     if isinstance(n, ast.Call)]
            self.assertIn("_cc._verify_one", calls, rel)
            embedded = [n.value for n in tree.body
                        if isinstance(n, ast.Assign)
                        and [t.id for t in n.targets] == ["SPEC"]]
            self.assertEqual(len(embedded), 1, rel)
            self.assertEqual(ast.unparse(embedded[0].func), "json.loads", rel)
            self.assertEqual(json.loads(embedded[0].args[0].value), spec, rel)

    def test_each_is_lf_with_a_final_newline(self):
        for rel, _spec, text in _shipped():
            self.assertNotIn("\r", text, rel)
            self.assertTrue(text.endswith("\n"), rel)


if __name__ == "__main__":
    unittest.main()
