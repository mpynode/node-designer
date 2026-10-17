"""Every writer of a file the repository tracks writes it LF, on Windows too.

These writers opened their file in text mode, so on Windows each line came
out CRLF while the repository stores the file LF:

  * ``mpn_io.save_mpn``: every ``.mpn`` (the Node Designer's File > Export
    .mpn, and the template generator)
  * ``_demos/build_templates.py``: each template's ``description.md``
    (``_write_template`` and ``_write_template_to``)
  * ``tools/harness/mega_plugin.py``: ``mega_results.json``
  * ``tools/regen_mega_transpiled.py``: the All Templates stage-1 ``.cpp``
  * ``tools/check_stage1_freshness.py --write-baseline``:
    ``tests/data/stage1_stale_baseline.json``
  * ``tools/sync_harness_manifest.py``: ``tools/harness/templates.json``
  * ``tools/harness/rebench_shipped.py``: a node's ``rounds.json``

Each test drives one writer as its tool or caller does, with every text-mode
write made to turn "\\n" into "\\r\\n" as Windows does, on every host, and
wants no CR in what it wrote. Where the writer writes a shipped file again
from the same input, it wants the shipped bytes back.
"""

from __future__ import annotations

import tests  # noqa: F401 -- first: keeps the run out of ~/.mpynode

import builtins
import contextlib
import glob
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init

_ROOT      = _paths.ROOT
_TEMPLATES = os.path.join(_ROOT,  "templates")
_TOOLS     = os.path.join(_ROOT,  "tools")
_HARNESS   = os.path.join(_TOOLS, "harness")
_MEGA      = os.path.join(_TEMPLATES, "All Templates Plugin", "build")


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


@contextlib.contextmanager
def _windows_text_mode():
    """A text-mode write turns "\\n" into "\\r\\n", as on Windows, on any
    host. A write that passes ``newline`` is left alone."""
    real = builtins.open

    def _open(file, mode="r", buffering=-1, encoding=None, errors=None,
              newline=None, *args, **kwargs):
        if "b" not in mode and newline is None and set(mode) & set("wax+"):
            newline = "\r\n"
        return real(file, mode, buffering, encoding, errors, newline,
                    *args, **kwargs)

    with mock.patch.object(builtins, "open", _open):
        yield


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _load_tool(name, path, argv=None):
    """Import a tool by path, without running its __main__ block. sys.path
    and sys.argv are put back afterwards."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "path", list(sys.path)), \
            mock.patch.object(sys, "argv", list(argv or [path])):
        spec.loader.exec_module(mod)
    return mod


def _rel(path):
    return os.path.relpath(path, _ROOT).replace("\\", "/")


class _LFCase(unittest.TestCase):
    # A failure names every file and what is wrong with it.
    maxDiff = None

    def _tmp(self):
        d = tempfile.mkdtemp(prefix="tracked_lf_")
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def _assert_lf(self, path):
        """The file's bytes, after checking it has no CR."""
        data = _read(path)
        self.assertEqual(data.count(b"\r"), 0,
                         "%s was written with %d CR"
                         % (os.path.basename(path), data.count(b"\r")))
        return data

    def _assert_same_bytes(self, got, want, what):
        if got == want:
            return
        why = ("the same once CRLF is made LF"
               if got.replace(b"\r\n", b"\n") == want
               else "different beyond line endings")
        self.fail("%s: %d bytes vs %d shipped, %s" % (what, len(got),
                                                      len(want), why))


class TestTheTestForcesWindowsLineEndings(_LFCase):
    """Without this every test below could pass on a host that writes LF
    anyway."""

    def test_a_plain_text_write_comes_out_crlf(self):
        path = os.path.join(self._tmp(), "plain.txt")
        with _windows_text_mode():
            with open(path, "w") as fh:
                fh.write("a\nb\n")
        self.assertEqual(_read(path), b"a\r\nb\r\n")

    def test_a_write_that_passes_newline_is_left_alone(self):
        path = os.path.join(self._tmp(), "lf.txt")
        with _windows_text_mode():
            with open(path, "w", newline="") as fh:
                fh.write("a\nb\n")
        self.assertEqual(_read(path), b"a\nb\n")


class TestSaveMpnWritesLF(_LFCase):
    def test_every_shipped_template_saves_back_byte_for_byte(self):
        """load_mpn then save_mpn gives every shipped template.mpn back
        exactly: LF, no final newline."""
        from mpynode._common.io.mpn_io import load_mpn, save_mpn

        paths = sorted(glob.glob(os.path.join(_TEMPLATES, "**",
                                              "template.mpn"),
                                 recursive=True))
        self.assertGreater(len(paths), 30, "found almost no template.mpn")
        tmp, bad = self._tmp(), []
        for i, path in enumerate(paths):
            out = os.path.join(tmp, "%02d.mpn" % i)
            with _windows_text_mode():
                save_mpn(load_mpn(path, trusted=True), out)
            got, want = _read(out), _read(path)
            if got != want:
                bad.append("%s: %d CR, %s" % (
                    _rel(path), got.count(b"\r"),
                    "the same once CRLF is made LF"
                    if got.replace(b"\r\n", b"\n") == want
                    else "different beyond line endings"))
        self.assertEqual(bad, [])

    def test_the_node_designer_export_writes_lf(self):
        """File > Import .mpn, then File > Export .mpn: the dialog answered
        with a path and the persistent-values question with Include (its
        default button). ``self`` is a stand-in for the Node Designer window;
        the export body runs as written."""
        from mpynode._base.commands import _ImportNodeCommand, run_undoable
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode._node_registry import wrap_node
        from mpynode.ui import node_designer
        from mpynode.ui.qt_wrapper import QFileDialog, QMessageBox

        shipped = os.path.join(_TEMPLATES, "MPyNode", "Bubble Sort",
                               "template.mpn")
        mc.file(new=True, force=True)
        cmd = _ImportNodeCommand(load_mpn(shipped, trusted=True))
        run_undoable(cmd)
        name = cmd.created_name
        self.addCleanup(mc.file, new=True, force=True)
        window = types.SimpleNamespace(
            _ask_persistent_values=lambda node, target: True,
            _script_tab_widget=types.SimpleNamespace(
                saveTabsForNode=lambda node_name: None))
        out, warned = os.path.join(self._tmp(), "bubbleSort.mpn"), []
        with mock.patch.object(QFileDialog, "getSaveFileName",
                               lambda *a, **k: (out, "")), \
                mock.patch.object(QMessageBox, "warning",
                                  lambda *a, **k: warned.append(a[1:])), \
                _windows_text_mode():
            node_designer.NDMainWindow._export_node_as_mpn(
                window, wrap_node(name, mc.nodeType(name)))
        self.assertEqual(warned, [])
        data = self._assert_lf(out)
        self.assertFalse(data.endswith(b"\n"), "a final newline")
        with open(shipped, encoding="utf-8") as fh:
            want = json.load(fh)["data"]["expression"]
        self.assertEqual(json.loads(data)["data"]["expression"], want)


class TestBuildTemplatesWritesLF(_LFCase):
    """The template generator's two writers, each given a shipped template's
    payload and description, write that template's two files back."""

    @classmethod
    def setUpClass(cls):
        cls.bt = _load_tool(
            "_bt_lf", os.path.join(_paths.SCRIPTS, "mpynode", "_demos",
                                   "build_templates.py"))

    def _shipped(self, rel):
        from mpynode._common.io.mpn_io import load_mpn

        folder = os.path.join(_TEMPLATES, *rel.split("/"))
        with open(os.path.join(folder, "description.md"),
                  encoding="utf-8") as fh:
            description = fh.read()
        return folder, load_mpn(os.path.join(folder, "template.mpn"),
                                trusted=True), description

    def _assert_written_back(self, rel, root):
        shipped = os.path.join(_TEMPLATES, *rel.split("/"))
        for name in ("template.mpn", "description.md"):
            got = self._assert_lf(os.path.join(root, *rel.split("/"), name))
            self._assert_same_bytes(got, _read(os.path.join(shipped, name)),
                                    "%s/%s" % (rel, name))

    def test_write_template(self):
        native_type, rel = "mPyDeformer", "MPyDeformer/Sine Ripple"
        self.assertEqual(self.bt._TARGET_BY_TYPE[native_type], rel)
        _folder, payload, description = self._shipped(rel)
        root = self._tmp()
        with _windows_text_mode():
            self.bt._write_template(payload, native_type, description,
                                    root=root)
        self._assert_written_back(rel, root)

    def test_write_template_to(self):
        rel = "MPyNurbsCurve/NURBS Helix"
        _folder, payload, description = self._shipped(rel)
        root = self._tmp()
        with _windows_text_mode():
            self.bt._write_template_to(rel, payload, description, root=root)
        self._assert_written_back(rel, root)


class TestTheToolsWriteLF(_LFCase):
    def test_check_stage1_freshness_writes_the_baseline_lf(self):
        """--write-baseline: a stale artifact listed, then none again, which
        is the shipped file back."""
        tool = _load_tool("_csf_lf",
                          os.path.join(_TOOLS, "check_stage1_freshness.py"))
        shipped = os.path.join(_paths.DATA, "stage1_stale_baseline.json")
        path    = os.path.join(self._tmp(), "baseline.json")
        shutil.copyfile(shipped, path)
        stale = "templates/X/build/stages/x/1_transpiled.cpp"
        with mock.patch.object(tool, "BASELINE", path), \
                contextlib.redirect_stdout(io.StringIO()), \
                _windows_text_mode():
            tool._write_baseline({"artifacts": {
                stale: {"state": "stale"}, "y.cpp": {"state": "fresh"}}})
            self.assertEqual(json.loads(self._assert_lf(path))["stale"],
                             [stale])
            tool._write_baseline({"artifacts": {}})
        self._assert_same_bytes(self._assert_lf(path), _read(shipped),
                                "stage1_stale_baseline.json")

    def test_sync_harness_manifest_writes_the_manifest_lf(self):
        """A manifest one row short gets the row back, written LF."""
        tool = _load_tool("_shm_lf",
                          os.path.join(_TOOLS, "sync_harness_manifest.py"))
        drop = "templates/MPyMesh/Voxelize/template.mpn"
        with open(os.path.join(_HARNESS, "templates.json"),
                  encoding="utf-8") as fh:
            rows = json.load(fh)
        kept = [r for r in rows if r["mpn"] != drop]
        self.assertEqual(len(kept), len(rows) - 1, "%s has no row" % drop)
        path = os.path.join(self._tmp(), "templates.json")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            json.dump(kept, fh, indent=1)
        with mock.patch.object(tool, "MANIFEST", path), \
                mock.patch.object(sys, "argv", ["sync_harness_manifest.py"]), \
                mock.patch.object(sys, "path", [_HARNESS] + sys.path), \
                contextlib.redirect_stdout(io.StringIO()), \
                _windows_text_mode():
            self.assertEqual(tool.main(), 0)
        data = self._assert_lf(path)
        back = json.loads(data)
        self.assertIn(drop, [r["mpn"] for r in back])
        self.assertEqual(len(back), len(rows))
        self.assertEqual(data, (json.dumps(back, indent=1) + "\n").encode())

    def test_rebench_shipped_writes_rounds_lf(self):
        """A shipped rounds.json given its own remeasured block back is the
        shipped file again."""
        tool = _load_tool("_rbs_lf",
                          os.path.join(_HARNESS, "rebench_shipped.py"))
        shipped = os.path.join(_TEMPLATES, "MPyNode", "Ouch", "build",
                               "stages", "ouch", "rounds.json")
        with open(shipped, encoding="utf-8") as fh:
            record = json.load(fh)["remeasured"]
        path = os.path.join(self._tmp(), "rounds.json")
        shutil.copyfile(shipped, path)
        with _windows_text_mode():
            tool.write_record(path, record)
        self._assert_same_bytes(self._assert_lf(path), _read(shipped),
                                "ouch rounds.json")

    def _regen_mega(self, stage_text):
        """Run regen_mega_transpiled.py over three All Templates nodes.
        bubbleSort's stage 1 is ASCII and aimTransform's has non-ASCII
        comments; each file first holds ``stage_text(shipped bytes)`` and
        must be written back. animatedText's, non-ASCII too, is left as
        shipped and must be read as up to date, not rewritten. Returns
        ``{type: (written, shipped)}`` for the two rewritten."""
        tool = _load_tool("_rmt_lf",
                          os.path.join(_TOOLS, "regen_mega_transpiled.py"))
        with open(os.path.join(_MEGA, "manifest.json"),
                  encoding="utf-8") as fh:
            rows = {r["type_name"]: r for r in json.load(fh)["nodes"]}
        stale   = ("bubbleSort", "aimTransform")
        fresh   = "animatedText"
        tmp     = self._tmp()
        stages  = os.path.join(tmp, "stages")
        shipped = {}
        for ty in stale + (fresh,):
            shipped[ty] = _read(os.path.join(_MEGA, "stages", ty,
                                             "1_transpiled.cpp"))
            os.makedirs(os.path.join(stages, ty))
            with open(os.path.join(stages, ty, "1_transpiled.cpp"),
                      "wb") as fh:
                fh.write(shipped[ty] if ty == fresh
                         else stage_text(shipped[ty]))
        self.assertTrue(shipped["bubbleSort"].isascii())
        self.assertFalse(shipped["aimTransform"].isascii())
        self.assertFalse(shipped[fresh].isascii())
        manifest = os.path.join(tmp, "manifest.json")
        with open(manifest, "w", encoding="utf-8", newline="") as fh:
            json.dump({"nodes": [rows[ty] for ty in stale + (fresh,)]}, fh)
        out = io.StringIO()
        with mock.patch.object(tool, "MANIFEST", manifest), \
                mock.patch.object(tool, "STAGES", stages), \
                mock.patch.object(sys, "argv", ["regen_mega_transpiled.py"]), \
                mock.patch.object(sys, "path", list(sys.path)), \
                mock.patch("maya.standalone.initialize", lambda **k: None), \
                contextlib.redirect_stdout(out), \
                _windows_text_mode():
            rc = tool.main()
        self.assertEqual(rc, 0, out.getvalue())
        self.assertIn("changed : 2  aimTransform bubbleSort\n", out.getvalue())
        self.assertIn("same    : 1  animatedText\n", out.getvalue())
        self.assertEqual(_read(os.path.join(stages, fresh,
                                            "1_transpiled.cpp")),
                         shipped[fresh])
        return {ty: (self._assert_lf(os.path.join(stages, ty,
                                                  "1_transpiled.cpp")),
                     shipped[ty]) for ty in stale}

    def test_regen_mega_transpiled_rewrites_a_stale_stage1_lf(self):
        for ty, (got, want) in self._regen_mega(
                lambda shipped: b"// stale\n").items():
            self._assert_same_bytes(got, want, ty)

    def test_regen_mega_transpiled_rewrites_a_crlf_stage1_lf(self):
        """A CRLF copy of an up-to-date stage 1 is stale too, as
        tools/regen_stage1.py has it."""
        for ty, (got, want) in self._regen_mega(
                lambda shipped: shipped.replace(b"\n", b"\r\n")).items():
            self._assert_same_bytes(got, want, ty)

    def test_mega_plugin_writes_mega_results_lf(self):
        """The All Templates relink (MPYNODE_MEGA_FROM_ARTIFACTS=1) with the
        bundler's link faked: build/mega_results.json is LF."""
        from mpynode.native.compiler import bundler
        from mpynode.ui.llm import config

        out  = self._tmp()
        mega = os.path.join(_HARNESS, "mega_plugin.py")
        tool = _load_tool("_mega_lf", mega, argv=[mega, out, "mPyMega"])
        self.assertEqual(tool.OUT_DIR, out)

        def assemble(nodes, plugin_name, out_dir, **kwargs):
            return {"ok": True, "dropped": [],
                    "bundle": os.path.join(out_dir, "2025",
                                           plugin_name + ".mll"),
                    "nodes": [{"name": ty, "id": "0x%08x" % i,
                               "status": "compiled"}
                              for i, (ty, _cpp) in enumerate(nodes)]}

        with mock.patch.object(tool, "FROM_ARTIFACTS", True), \
                mock.patch.object(bundler, "assemble", assemble), \
                mock.patch.object(config, "set_provider", lambda *a: None), \
                mock.patch.object(config, "set_model", lambda *a: None), \
                mock.patch.object(config, "set_effort", lambda *a: None), \
                mock.patch("maya.standalone.initialize", lambda **k: None), \
                mock.patch.dict(os.environ), \
                mock.patch.object(sys, "path", [_HARNESS] + sys.path), \
                contextlib.redirect_stdout(io.StringIO()), \
                _windows_text_mode():
            self.assertEqual(tool.main(), 0)
        results = json.loads(self._assert_lf(
            os.path.join(out, "build", "mega_results.json")))
        self.assertTrue(results["ok"])
        self.assertGreater(results["n_linked"], 30)
        self.assertEqual(results["n_linked"], results["n_input"])


if __name__ == "__main__":
    unittest.main()
