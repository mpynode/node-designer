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

The generator also wrote the generating host's plug-in extension, so on
macOS this gate called every shipped script stale and the tool rewrote them
to ``.bundle``. Each script now picks ``.mll``, ``.bundle`` or ``.so`` when it
runs, and the generator's text is the same on every OS.

Each script then gave ``_verify_one``'s generic row alone, so 8 said SKIP
where the pipeline passes the node on its authored ``@maya_test``. It now runs
``verify._default_verify``, the generic check and the authored test merged as
in the pipeline's row. That verify opens new scenes, so a script refuses to
run while the open scene has unsaved changes, before it touches the scene,
and it names the ``mpynode`` folder it imported.

Run as ``mayapy verify_in_maya.py``, as the refusal advises, every script
then failed at that guard: ``maya.cmds`` is empty until Maya starts. A
script run that way now starts Maya itself, before it imports ``mpynode``,
so a ``userSetup.py`` install's paths apply. And a PASS the authored test
alone decided printed a bare ``VERIFY PASS maxerr None``, even when the
generic check's harness had failed (an outdated ``mpynode`` on the path):
the line now gives the row's reason, marked ``skipped`` or ``COULD NOT RUN``.

``tools/regen_verify_scripts.py`` does the regenerating; this module is the
gate over its result. Compared line by line with whitespace runs collapsed
(the tool's ``matches``): the align sweep columnises the shipped copies, and
that is the only difference allowed.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import glob
import importlib.util
import io
import json
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import _paths
from tests._setup import standalone_init

_TOOL  = os.path.join(_paths.ROOT, "tools", "regen_verify_scripts.py")
_REGEN = None
_OSES  = (("win32", ".mll"), ("darwin", ".bundle"), ("linux", ".so"))


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


@contextlib.contextmanager
def _on_os(platform):
    """``sys.platform`` reads ``platform``: toolchain.current_os reads it."""
    real         = sys.platform
    sys.platform = platform
    try:
        yield
    finally:
        sys.platform = real


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

    def test_each_runs_the_pipeline_verify_on_its_own_spec(self):
        # One parity implementation: the only function is run(), it calls
        # verify._default_verify (never _verify_one alone), NAME is the
        # type, and SPEC is the manifest row's spec.
        for rel, spec, text in _shipped():
            tree = ast.parse(text)
            funcs = [n.name for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.Lambda))]
            self.assertEqual(funcs, ["run"], rel)
            calls = [ast.unparse(n.func) for n in ast.walk(tree)
                     if isinstance(n, ast.Call)]
            self.assertIn("_cc._default_verify", calls, rel)
            self.assertNotIn("_cc._verify_one", calls, rel)
            assigns = [(t.id, n.value) for n in tree.body
                       if isinstance(n, ast.Assign) for t in n.targets]
            self.assertEqual([k for k, _v in assigns],
                             ["EXT", "NAME", "BUNDLE", "SPEC"], rel)
            consts = dict(assigns)
            self.assertEqual(ast.literal_eval(consts["NAME"]),
                             spec["suggested"]["node_type_name"], rel)
            self.assertEqual(ast.unparse(consts["SPEC"].func), "json.loads",
                             rel)
            self.assertEqual(json.loads(consts["SPEC"].args[0].value), spec,
                             rel)

    def test_the_generator_writes_the_same_text_on_every_os(self):
        # Generated on macOS, every script named a .bundle: the generator
        # wrote the generating host's plug-in extension.
        from mpynode.native.ai import verify_scripts
        from mpynode.native.toolchain import toolchain

        for rel, spec, _text in _shipped():
            texts = set()
            for platform, ext in _OSES:
                with _on_os(platform):
                    texts.add(verify_scripts._verify_script(spec))
                with mock.patch.object(toolchain, "plugin_ext",
                                       return_value=ext):
                    texts.add(verify_scripts._verify_script(spec))
            self.assertEqual(len(texts), 1, rel)

    def test_each_picks_the_plugin_for_the_os_it_runs_on(self):
        for rel, _spec, text in _shipped():
            name = os.path.basename(os.path.dirname(rel))
            code = compile(text, rel, "exec")
            for platform, ext in _OSES:
                ns = {"__file__": "/x/verify_in_maya.py",
                      "__name__": "verify_probe"}
                with _on_os(platform):
                    exec(code, ns)
                self.assertEqual(os.path.basename(ns["BUNDLE"]), name + ext,
                                 (rel, platform))

    def test_each_is_lf_with_a_final_newline(self):
        for rel, _spec, text in _shipped():
            self.assertNotIn("\r", text, rel)
            self.assertTrue(text.endswith("\n"), rel)


def _load_script(rel, text):
    """The shipped script's namespace, imported but not run."""
    ns = {"__file__": os.path.join(_paths.ROOT, rel),
          "__name__": "verify_probe"}
    exec(compile(text, rel, "exec"), ns)
    return ns


class TestShippedVerifyScriptsInAScene(unittest.TestCase):
    """Each shipped script against this process's real Maya scene, with the
    pipeline's verify replaced by a recorder: the verify itself is the
    pipeline's, covered by its own tests."""

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        self.addCleanup(mc.file, new=True, force=True)

    def test_each_refuses_a_scene_with_unsaved_changes(self):
        # The verify opens new scenes: run in a scene with unsaved changes, a
        # script raises before it touches it, and says why.
        import maya.cmds as mc
        import mpynode
        from mpynode.native.toolchain import verify

        node = mc.createNode("transform", name="unsavedWork")
        mc.setAttr(node + ".translateX", 3.5)
        self.assertTrue(mc.file(q=True, modified=True))
        before = sorted(mc.ls())
        pkg    = os.path.dirname(os.path.abspath(mpynode.__file__))
        for rel, _spec, text in _shipped():
            ns  = _load_script(rel, text)
            buf = io.StringIO()
            with mock.patch.object(verify, "_default_verify") as dv, \
                    contextlib.redirect_stdout(buf), \
                    self.assertRaises(RuntimeError) as cm:
                ns["run"]()
            self.assertIn("unsaved changes", str(cm.exception), rel)
            self.assertIn("Save first, or run it in a fresh mayapy",
                          str(cm.exception), rel)
            self.assertFalse(dv.called, rel)
            self.assertEqual(buf.getvalue().splitlines(),
                             ["VERIFY MPYNODE " + pkg], rel)
            self.assertTrue(mc.file(q=True, modified=True), rel)
            self.assertEqual(sorted(mc.ls()), before, rel)
            self.assertEqual(mc.getAttr(node + ".translateX"), 3.5, rel)

    def test_each_reports_the_merged_row_on_a_clean_scene(self):
        # An untitled scene with no changes runs: the script hands its own
        # row to the pipeline's verify and reports the merged verdict.
        import maya.cmds as mc
        import mpynode
        from mpynode.native.toolchain import verify

        self.assertFalse(mc.file(q=True, modified=True))
        pkg = os.path.dirname(os.path.abspath(mpynode.__file__))
        for rel, spec, text in _shipped():
            ns   = _load_script(rel, text)
            name = spec["suggested"]["node_type_name"]
            why = ("no scalar outputs to compare | "
                   "authored @maya_test: 1/1 passed")
            row = {"ran": True, "pass": True, "maxerr": None, "tol": 0.0,
                   "generic_ran": False, "reason": why}
            buf = io.StringIO()
            with mock.patch.object(verify, "_default_verify",
                                   return_value={name: row}) as dv, \
                    contextlib.redirect_stdout(buf):
                ok = ns["run"]()
            self.assertTrue(ok, rel)
            dv.assert_called_once_with(ns["BUNDLE"],
                                       [{"type_name": name, "spec": spec}])
            lines = buf.getvalue().splitlines()
            self.assertEqual(lines[0], "VERIFY MPYNODE " + pkg, rel)
            # The authored test alone passed it: the line says why the
            # generic check did not run.
            self.assertEqual(lines[-1],
                             "VERIFY PASS (authored @maya_test only; generic "
                             "check skipped) " + why, rel)


class _BareMayapy:
    """``maya`` as a bare ``mayapy verify_in_maya.py`` has it: ``maya.cmds``
    is empty until ``maya.standalone.initialize()`` runs. Records the
    initialize and every ``mpynode`` import, in order."""

    def __init__(self, started=False):
        self.events                = []
        self.cmds                  = types.ModuleType("maya.cmds")
        self.standalone            = types.ModuleType("maya.standalone")
        self.maya                  = types.ModuleType("maya")
        self.maya.cmds             = self.cmds
        self.maya.standalone       = self.standalone
        self.standalone.initialize = self._initialize
        if started:
            self.cmds.file = self._file

    def _file(self, *a, **k):
        return False

    def _initialize(self):
        self.events.append("initialize")
        self.cmds.file = self._file

    @contextlib.contextmanager
    def active(self):
        real = builtins.__import__

        def recording(name, *a, **k):
            if name == "mpynode" or name.startswith("mpynode."):
                self.events.append("import " + name)
            return real(name, *a, **k)

        mods = {"maya": self.maya, "maya.cmds": self.cmds,
                "maya.standalone": self.standalone}
        with mock.patch.dict(sys.modules, mods), \
                mock.patch.object(builtins, "__import__", recording):
            yield


class TestShippedVerifyScriptsRunByMayapy(unittest.TestCase):
    """``mayapy verify_in_maya.py``, the refusal's own advice: the script
    starts Maya before it imports ``mpynode``, and only then."""

    def _exec(self, rel, text, bare, run_name):
        """Exec the shipped script under ``bare``'s maya with the pipeline's
        verify replaced by a recorder; its stdout."""
        import mpynode  # noqa: F401  (imported before sys.modules is patched)
        from mpynode.native.toolchain import toolchain, verify  # noqa: F401

        name = os.path.basename(os.path.dirname(rel))
        row = {"ran": True, "pass": True, "maxerr": 0.0, "tol": 1e-4,
               "reason": ""}
        buf = io.StringIO()
        ns = {"__file__": os.path.join(_paths.ROOT, rel),
              "__name__": run_name}
        with bare.active(), \
                mock.patch.object(verify, "_default_verify",
                                  return_value={name: row}), \
                contextlib.redirect_stdout(buf):
            exec(compile(text, rel, "exec"), ns)
        return buf.getvalue()

    def test_each_starts_maya_before_importing_mpynode(self):
        for rel, _spec, text in _shipped():
            bare = _BareMayapy()
            out  = self._exec(rel, text, bare, "__main__")
            self.assertEqual(bare.events.count("initialize"), 1, rel)
            self.assertEqual(bare.events[0], "initialize", rel)
            self.assertIn("import mpynode", bare.events, rel)
            # ...and it then runs: the guard query works, the verdict prints.
            self.assertIn("VERIFY PASS maxerr 0.0", out, rel)

    def test_none_starts_maya_when_it_is_running_or_imported(self):
        # In Maya, or under a runner that started it, cmds is full: no
        # second start. Imported rather than run, it starts nothing either.
        for rel, _spec, text in _shipped():
            bare = _BareMayapy(started=True)
            out  = self._exec(rel, text, bare, "__main__")
            self.assertNotIn("initialize", bare.events, rel)
            self.assertIn("VERIFY PASS maxerr 0.0", out, rel)
            bare = _BareMayapy()
            out  = self._exec(rel, text, bare, "verify_probe")
            self.assertNotIn("initialize", bare.events, rel)
            self.assertEqual(out, "", rel)


if __name__ == "__main__":
    unittest.main()
