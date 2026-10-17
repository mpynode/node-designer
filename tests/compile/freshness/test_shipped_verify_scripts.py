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

A FAIL still exited 0 like a PASS, so a shell caller read it as success.
Run as a script, a FAIL now raises after its FAIL line, so mayapy exits 1
and Maya shows an error; ``run()`` still returns False to a caller. A PASS,
a PASS on the authored test alone and a SKIP exit 0.

A verify leaves the scene it made modified, so a second run in the same
session is refused, and the refusal's advice (save first, or a fresh
mayapy) fit only the user's own work. It now ends by saying to clear a
scene a previous verify left with ``cmds.file(new=True, force=True)``; that
command, run as written, lets the script run again.

``tools/regen_verify_scripts.py`` does the regenerating; this module is the
gate over its result. Compared line by line with whitespace runs collapsed
(the tool's ``matches``): the align sweep columnises the shipped copies, and
that is the only difference allowed. Each script is also LF. The tool's own
check compared line by line only, so it called a CRLF script fresh and never
rewrote it; a CRLF script is now stale there too, and the tool writes it
back LF with its own text, columns kept.
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
# The refusal's last sentence: how to clear a scene a previous verify left.
_ADVICE = ("If a previous verify left this scene, run "
           "cmds.file(new=True, force=True) first.")


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


class TestTheToolRewritesACrlfScriptLF(unittest.TestCase):
    """The tool's --check compared line by line, which ignores line endings,
    so it called a CRLF script fresh and a run never rewrote it. Every
    shipped script, copied to a scratch tree as CRLF: --check exits 1 and
    names each one, a run writes each back LF with its own text, so its
    columns stay, and --check then passes. One copy is also stale in its
    text: it is rewritten with the generator's text, LF."""

    def _tool(self, root, rows, *argv):
        """The tool's main(argv) on the scripts in ``rows``; (rc, stdout)."""
        buf = io.StringIO()
        with mock.patch.object(_REGEN, "_ROOT", root), \
                mock.patch.object(_REGEN, "shipped", lambda: rows), \
                contextlib.redirect_stdout(buf):
            rc = _REGEN.main(list(argv))
        return rc, buf.getvalue()

    def test_a_crlf_script_is_stale_and_rewritten_lf(self):
        import shutil
        import tempfile

        from mpynode.native.ai import verify_scripts

        root = tempfile.mkdtemp(prefix="verify_crlf_")
        self.addCleanup(shutil.rmtree, root, True)
        rows, want = [], {}
        for i, (rel, spec, text) in enumerate(_shipped()):
            path = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # The LF text, whatever the shipped copy holds (the test above
            # gates that), made LF the way the tool makes it: a lone CR too.
            # The first copy is also stale in its text.
            text = _REGEN.lf(text)
            body = text + "# stale\n" if i == 0 else text
            with open(path, "wb") as fh:
                fh.write(body.replace("\n", "\r\n").encode("utf-8"))
            rows.append((path, os.path.basename(os.path.dirname(rel)), spec))
            want[rel] = (verify_scripts._verify_script(spec) if i == 0
                         else text).encode("utf-8")
        self.assertTrue(len(want) > 1)
        first = next(iter(want))

        def read_all():
            out = {}
            for rel in want:
                with open(os.path.join(root, *rel.split("/")), "rb") as fh:
                    out[rel] = fh.read()
            return out

        before = read_all()
        n      = len(want)
        rc, out = self._tool(root, rows, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn("0 fresh, %d stale" % n, out)
        for rel in want:
            line = "   stale " + rel + ("" if rel == first
                                         else " (CRLF line endings)")
            self.assertIn(line + "\n", out)
        rc, out = self._tool(root, rows, "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertEqual(read_all(), before, "--dry-run wrote")

        rc, out = self._tool(root, rows)
        self.assertEqual(rc, 0, out)
        self.assertIn("0 fresh, %d rewritten" % n, out)
        self.assertEqual(read_all(), want)
        rc, out = self._tool(root, rows, "--check")
        self.assertEqual(rc, 0, out)
        self.assertIn("%d fresh, 0 stale" % n, out)


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
            self.assertTrue(str(cm.exception).endswith(_ADVICE), rel)
            self.assertFalse(dv.called, rel)
            self.assertEqual(buf.getvalue().splitlines(),
                             ["VERIFY MPYNODE " + pkg], rel)
            self.assertTrue(mc.file(q=True, modified=True), rel)
            self.assertEqual(sorted(mc.ls()), before, rel)
            self.assertEqual(mc.getAttr(node + ".translateX"), 3.5, rel)

    def test_the_refusal_clears_the_scene_a_previous_verify_left(self):
        # A verify leaves the scene it made modified, so a second run in the
        # same session was refused, with advice that fit only the user's own
        # work: save it, or start a fresh mayapy. The refusal now names the
        # command that clears such a scene; run as written, it lets the
        # script run again.
        import re

        import maya.cmds as mc
        from mpynode.native.toolchain import verify

        def a_verify(bundle, rows):
            # What a verify does to the scene: new scene, its own nodes.
            mc.file(new=True, force=True)
            mc.createNode("transform", name="verifyTwin")
            return {rows[0]["type_name"]: {"ran": True, "pass": True,
                                           "maxerr": 0.0, "tol": 1e-4}}

        for rel, _spec, text in _shipped():
            mc.file(new=True, force=True)
            ns = _load_script(rel, text)
            with mock.patch.object(verify, "_default_verify",
                                   side_effect=a_verify) as dv, \
                    contextlib.redirect_stdout(io.StringIO()) as buf:
                self.assertTrue(ns["run"](), rel)
                self.assertTrue(mc.file(q=True, modified=True), rel)
                with self.assertRaises(RuntimeError) as cm:
                    ns["run"]()
                self.assertEqual(dv.call_count, 1, rel)
                advice = re.search(r"run (\S+\(.*\)) first\.$",
                                   str(cm.exception))
                self.assertIsNotNone(advice, (rel, str(cm.exception)))
                exec(advice.group(1), ns)
                self.assertFalse(mc.file(q=True, modified=True), rel)
                self.assertTrue(ns["run"](), rel)
            self.assertEqual(dv.call_count, 2, rel)
            self.assertEqual(buf.getvalue().splitlines()[-1],
                             "VERIFY PASS maxerr 0.0", rel)

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
    starts Maya before it imports ``mpynode``, and only then. Run that way,
    a FAIL raises, so mayapy exits 1."""

    _PASS = {"ran": True, "pass": True, "maxerr": 0.0, "tol": 1e-4,
             "reason": ""}
    _FAIL = {"ran": True, "pass": False, "maxerr": 0.5, "tol": 1e-4,
             "reason": "outColor diverged"}
    _FAIL_LINE = ("VERIFY FAIL generic check maxerr 0.5 > tol 0.0001 | "
                  "outColor diverged")

    def _exec(self, rel, text, bare, run_name, row=None, call=False):
        """Exec the shipped script under ``bare``'s maya with the pipeline's
        verify returning ``row`` (a PASS by default), then call its run()
        when ``call``; (stdout, what it raised or None, run()'s value)."""
        import mpynode  # noqa: F401  (imported before sys.modules is patched)
        from mpynode.native.toolchain import toolchain, verify  # noqa: F401

        name = os.path.basename(os.path.dirname(rel))
        buf  = io.StringIO()
        ns = {"__file__": os.path.join(_paths.ROOT, rel),
              "__name__": run_name}
        rows   = {name: dict(row or self._PASS)}
        raised = got = None
        with bare.active(), \
                mock.patch.object(verify, "_default_verify",
                                  return_value=rows), \
                contextlib.redirect_stdout(buf):
            try:
                exec(compile(text, rel, "exec"), ns)
                if call:
                    got = ns["run"]()
            except Exception as exc:
                raised = exc
        return buf.getvalue(), raised, got

    def test_each_starts_maya_before_importing_mpynode(self):
        for rel, _spec, text in _shipped():
            bare = _BareMayapy()
            out, raised, _ = self._exec(rel, text, bare, "__main__")
            self.assertIsNone(raised, rel)
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
            out, raised, _ = self._exec(rel, text, bare, "__main__")
            self.assertIsNone(raised, rel)
            self.assertNotIn("initialize", bare.events, rel)
            self.assertIn("VERIFY PASS maxerr 0.0", out, rel)
            bare = _BareMayapy()
            out, raised, _ = self._exec(rel, text, bare, "verify_probe")
            self.assertIsNone(raised, rel)
            self.assertNotIn("initialize", bare.events, rel)
            self.assertEqual(out, "", rel)

    def test_each_fail_raises_when_run_and_returns_false_when_called(self):
        # A FAIL exited 0 like a PASS. Run as a script, by a bare mayapy or
        # in a running Maya, it now raises after its FAIL line: mayapy exits
        # 1 and Maya shows an error. Imported, run() returns False.
        for rel, _spec, text in _shipped():
            name = os.path.basename(os.path.dirname(rel))
            for started in (False, True):
                bare = _BareMayapy(started=started)
                out, raised, _ = self._exec(rel, text, bare, "__main__",
                                            self._FAIL)
                self.assertIsInstance(raised, RuntimeError, (rel, started))
                self.assertEqual(str(raised),
                                 "VERIFY FAIL: the compiled " + name + " does "
                                 "not match the original; see the VERIFY "
                                 "FAIL line above.", (rel, started))
                self.assertEqual(out.splitlines()[-1], self._FAIL_LINE,
                                 (rel, started))
            bare = _BareMayapy(started=True)
            out, raised, got = self._exec(rel, text, bare, "verify_probe",
                                          self._FAIL, call=True)
            self.assertIsNone(raised, rel)
            self.assertIs(got, False, rel)
            self.assertEqual(out.splitlines()[-1], self._FAIL_LINE, rel)

    def test_a_pass_or_a_skip_run_as_a_script_raises_nothing(self):
        # Every verdict the pipeline does not call a FAIL exits 0: a PASS, a
        # PASS on the authored test alone (the generic check skipped, or
        # COULD NOT RUN: the pipeline calls both PASS), and a SKIP.
        why  = " | authored @maya_test: 1/1 passed"
        head = "VERIFY PASS (authored @maya_test only; generic check "
        cases = [
            (self._PASS, "VERIFY PASS maxerr 0.0"),
            ({"ran": True, "pass": True, "maxerr": None, "tol": 0.0,
              "generic_ran": False, "reason": "NURBS CV idiom" + why},
             head + "skipped) NURBS CV idiom" + why),
            ({"ran": True, "pass": True, "maxerr": None, "tol": 0.0,
              "generic_ran": False,
              "reason": "verify could not run: boom" + why},
             head + "COULD NOT RUN) verify could not run: boom" + why),
            ({"ran": False, "pass": None, "maxerr": None, "tol": None,
              "reason": "nothing to compare"},
             "VERIFY SKIP (nothing to compare)"),
        ]
        for rel, _spec, text in _shipped():
            for row, line in cases:
                out, raised, _ = self._exec(rel, text,
                                            _BareMayapy(started=True),
                                            "__main__", row)
                self.assertIsNone(raised, (rel, line))
                self.assertEqual(out.splitlines()[-1], line, (rel, line))


if __name__ == "__main__":
    unittest.main()
