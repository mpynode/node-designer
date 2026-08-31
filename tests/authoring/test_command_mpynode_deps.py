# tests/authoring/test_command_mpynode_deps.py  (pure -- no setUpModule)
"""No shipped template may carry an ``import mpynode`` a command can reach.

A ``@maya_command`` body ships as EMBEDDED PYTHON inside the compiled .mll. On a
machine that has Maya but NOT the mpynode package -- the whole point of
distributing a .mll -- every such import raises ModuleNotFoundError the first
time the command runs. ``command_dispatch.reachable_mpynode_imports`` already
found them, but ``emit_dispatch_commands`` only wrote them to stderr ("Not fatal
-- the command still compiles"), the tests that existed fed it three-line
SYNTHETIC sources, and ``tools/scan_command_mpynode_deps.py`` was invoked by no
test at all. 13 templates broke down exactly that gap. The emitter now FAILS the
compile whenever a Python payload is emitted (see the reachable-mpynode section
note there); this module is the corpus-wide half of that gate.

So this gates the REAL corpus, with the SAME source a bundle actually gets:
each ``.mpn``'s ``methods_source`` run through
``node_setups.merge_type_default(src, native_type)``, mirroring
``mpn_spec_adapter.spec_from_mpn_payload``. All 43 templates are scanned
(measured 0.63s: 0.59s to load+merge+detect, 0.04s to walk -- no subsetting
needed).

A command-LESS template is scanned too, with an empty command list, which leaves
exactly the module-scope imports: ``build_methods_namespace`` execs the whole
source before it looks up anything, so those turn fatal the day the template --
or the per-type default merged into it -- acquires a single ``@maya_command``,
with no edit to the import itself. That is the LATENT bucket, and it is how the
13 went from "no command, nothing to break" to broken.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import os
import unittest

from mpynode._common import node_setups
from mpynode._common.methods.maya_command import detect_commands
from mpynode.native.compiler.kernels import command_dispatch as cd
from tests import _paths

_ROOT = _paths.ROOT
_TEMPLATES = os.path.join(_ROOT, "templates")
_SCAN_TOOL = os.path.join(_ROOT, "tools", "scan_command_mpynode_deps.py")

_CORPUS = None


def _corpus():
    """Every shipped template as (rel, merged_source, commands), parsed once.

    The merge is the production one -- no ``root=`` override -- so this is byte
    for byte what ``spec_from_mpn_payload`` hands the compiler.
    """
    global _CORPUS
    if _CORPUS is not None:
        return _CORPUS
    out = []
    for dirpath, _dirs, files in sorted(os.walk(_TEMPLATES)):
        if "template.mpn" not in files:
            continue
        path = os.path.join(dirpath, "template.mpn")
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        data = payload.get("data", payload)
        merged = node_setups.merge_type_default(
            data.get("methods_source") or "", data.get("native_type") or "")
        out.append((os.path.relpath(path, _ROOT).replace("\\", "/"),
                    merged, detect_commands(merged)))
    _CORPUS = out
    return out


def _inject_module_scope(src):
    return "import mpynode\n" + src


def _inject_into_command_body(src, func_name):
    """``src`` with ``import mpynode`` as the first statement of ``func_name``."""
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == func_name)
    first = fn.body[0]
    lines = src.splitlines()
    lines.insert(first.lineno - 1, " " * first.col_offset + "import mpynode")
    return "\n".join(lines) + "\n"


class TestShippedTemplatesReachNoMpynodeImport(unittest.TestCase):
    def test_no_template_has_a_reachable_or_latent_mpynode_import(self):
        rows = _corpus()
        # Both guards keep the loop below from passing on an empty corpus.
        self.assertGreater(len(rows), 30,
                           "found almost no template.mpn under %s" % _TEMPLATES)
        self.assertGreater(len([r for r in rows if r[2]]), 10,
                           "no template appears to declare a @maya_command -- "
                           "the merge or the detector is broken")
        bad = []
        for rel, merged, cmds in rows:
            hits = cd.reachable_mpynode_imports(merged, cmds)
            if hits:
                bad.append("%s%s\n    %s"
                           % (rel, "" if cmds else "  [no command yet: LATENT]",
                              "\n    ".join(hits)))
        self.assertEqual(
            bad, [],
            "template(s) reach an `import mpynode` that ships as embedded "
            "Python in the .mll and raises ModuleNotFoundError wherever "
            "mpynode is not installed. Vendor the code into the Methods source "
            "or move the import inside a demo/test:\n" + "\n".join(bad))

    def test_the_scan_tool_reports_the_whole_tree_clean(self):
        spec = importlib.util.spec_from_file_location("_scan_cmd_deps",
                                                      _SCAN_TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = mod.main(["--quiet", "--root", _ROOT])
        out = buf.getvalue()
        self.assertEqual(rc, 0, "tools/scan_command_mpynode_deps.py:\n" + out)
        self.assertIn("dirty   (0)", out)
        self.assertIn("latent module-scope mpynode imports (0)", out)


class TestTheReachabilityCheckActuallyFires(unittest.TestCase):
    """The corpus above is clean today, so each assertion is re-run against a
    REAL shipped source with the defect injected -- otherwise a detector that
    silently stopped reporting would leave the gate green forever."""

    def _first(self, want_commands):
        for rel, merged, cmds in _corpus():
            if bool(cmds) == want_commands:
                return rel, merged, cmds
        self.fail("no template with commands=%s in the corpus" % want_commands)

    def test_module_scope_import_in_a_command_bearing_template_is_reported(self):
        rel, merged, cmds = self._first(True)
        hits = cd.reachable_mpynode_imports(_inject_module_scope(merged), cmds)
        self.assertTrue(hits, rel)
        self.assertIn("module scope", hits[0])

    def test_import_inside_a_real_command_body_is_reported(self):
        rel, merged, cmds = self._first(True)
        func = cmds[0]["func_name"]
        hits = cd.reachable_mpynode_imports(
            _inject_into_command_body(merged, func), cmds)
        self.assertTrue(hits, "%s: %s" % (rel, func))
        self.assertTrue(any("in def %s" % func in h for h in hits), hits)

    def test_module_scope_import_in_a_command_less_template_is_reported(self):
        """LATENT: nothing reaches it today, and it still execs ahead of every
        lookup the moment this template acquires a command."""
        rel, merged, cmds = self._first(False)
        hits = cd.reachable_mpynode_imports(_inject_module_scope(merged), cmds)
        self.assertTrue(hits, rel)
        self.assertIn("module scope", hits[0])


if __name__ == "__main__":
    unittest.main()
