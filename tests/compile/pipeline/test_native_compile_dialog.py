"""Native CompileDialog node-picker/bundle-manager + subprocess-verify wiring

Consolidated from: test_compile_bundle_manager.py, test_subprocess_verify.py.
"""

from __future__ import annotations

# ===================== from test_compile_bundle_manager.py =====================
import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _setUpModule__compile_bundle_manager():
    standalone_init()


class _FakeTable:
    def __init__(self):
        self.row_count = 0
        self.items     = {}

    def setRowCount(self, n):
        self.row_count = n

    def setItem(self, r, c, item):
        self.items[(r, c)] = item

    def item(self, r, c):
        return self.items.get((r, c))

    def resizeColumnToContents(self, c):
        pass


class _FakeSelf:
    """Duck-typed CompileDialog touching only the picker plumbing."""

    def __init__(self, scene_nodes=None, checked=None):
        self._scene_nodes = list(scene_nodes or [])
        self._checked     = set(checked or [])
        # External .mpn rows merged into the table (none in these scene tests).
        self._file_rows = {}
        # Per-node persistent unchecks (pruned/remapped alongside _checked).
        self._persistent_unchecked = set()
        self._has_persistent       = {}
        self._row_by_type          = {}
        self._busy                 = False
        self._table                = _FakeTable()
        self.rendered              = []
        self.styled                = []
        self.rendered_persist      = []
        self.refresh_calls         = 0
        # _refresh_table disambiguates file rows from the live scene with this
        # pure staticmethod; bind the real one, as a CompileDialog would have.
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as _CD

        self._disambiguate_file_rows = _CD._disambiguate_file_rows

    # Stub the Qt-touching renderers so _refresh_table's DATA logic runs
    # without real QTableWidgetItems.
    def _render_row(self, row, name, ntype):
        self.rendered.append((row, name, ntype, name in self._checked))

    def _apply_row_style(self, row, checked):
        self.styled.append((row, checked))

    def _render_persistent_cell(self, row, name):
        self.rendered_persist.append((row, name))

    # Stub so re-rendering methods can be checked for their state effect and
    # for triggering a re-render.
    def _refresh_table(self):
        self.refresh_calls += 1


class TestRefreshFromScene(unittest.TestCase):
    def test_refresh_queries_scene_sorts_and_renders(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        orig                = cd._scene_mpy_nodes
        cd._scene_mpy_nodes = lambda: [("b", "T"), ("a", "U")]
        try:
            fake = _FakeSelf(checked=["a", "gone"])
            cd.CompileDialog._refresh_table(fake)
        finally:
            cd._scene_mpy_nodes = orig
        # Sorted, full scene listed.
        self.assertEqual(fake._scene_nodes,     [("a", "U"), ("b", "T")])
        self.assertEqual(fake._table.row_count, 2)
        self.assertEqual(len(fake.rendered),    2)
        # Stale 'gone' pruned; live 'a' check preserved.
        self.assertEqual(fake._checked, {"a"})

    def test_refresh_prunes_persistent_unchecked(self):
        """A per-node persistent uncheck for a node that no longer exists must be
        pruned on rescan (mirrors the _checked prune) so a later node reusing the
        name can't inherit the stale uncheck and silently lose its stored vars."""
        from mpynode.ui.dialogs import compile_dialog as cd

        orig                = cd._scene_mpy_nodes
        cd._scene_mpy_nodes = lambda: [("a", "T")]
        try:
            fake                       = _FakeSelf(scene_nodes=[("a", "T"), ("gone", "T")])
            fake._persistent_unchecked = {"gone", "a"}
            cd.CompileDialog._refresh_table(fake)
        finally:
            cd._scene_mpy_nodes = orig
        # 'gone' vanished -> pruned; 'a' survives -> kept.
        self.assertEqual(fake._persistent_unchecked, {"a"})

    def test_refresh_empty_scene_clears_everything(self):
        """The stale-list bug: a NEW empty scene must wipe the table+checks."""
        from mpynode.ui.dialogs import compile_dialog as cd

        orig                = cd._scene_mpy_nodes
        cd._scene_mpy_nodes = lambda: []
        try:
            fake = _FakeSelf(scene_nodes=[("old", "T")], checked=["old"])
            cd.CompileDialog._refresh_table(fake)
        finally:
            cd._scene_mpy_nodes = orig
        self.assertEqual(fake._scene_nodes,     [])
        self.assertEqual(fake._table.row_count, 0)
        self.assertEqual(fake._checked,         set())
        self.assertEqual(fake.rendered,         [])

    def test_refresh_is_noop_while_busy(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        orig                = cd._scene_mpy_nodes
        cd._scene_mpy_nodes = lambda: [("a", "T")]
        try:
            fake       = _FakeSelf(scene_nodes=[("old", "T")])
            fake._busy = True
            cd.CompileDialog._refresh_table(fake)
        finally:
            cd._scene_mpy_nodes = orig
        self.assertEqual(fake._scene_nodes, [("old", "T")])  # unchanged
        self.assertEqual(fake.rendered, [])

    def test_default_is_unchecked(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        orig                = cd._scene_mpy_nodes
        cd._scene_mpy_nodes = lambda: [("a", "T"), ("b", "U")]
        try:
            fake = _FakeSelf()
            cd.CompileDialog._refresh_table(fake)
        finally:
            cd._scene_mpy_nodes = orig
        self.assertEqual(fake._checked, set())
        self.assertEqual(cd.CompileDialog._checked_nodes(fake), [])


class TestCheckedSelection(unittest.TestCase):
    def test_checked_nodes_returns_only_checked_in_scene_order(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf(scene_nodes=[("a", "T"), ("b", "U"), ("c", "V")],
                         checked=["c", "a"])
        self.assertEqual(cd.CompileDialog._checked_nodes(fake),
                         [("a", "T"), ("c", "V")])

    def test_check_toggle_checks_and_unchecks(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf(scene_nodes=[("a", "T")])
        cd.CompileDialog._on_check_toggled(fake, cd._COL_CHECK, "a", 0, True)
        self.assertIn("a", fake._checked)
        cd.CompileDialog._on_check_toggled(fake, cd._COL_CHECK, "a", 0, False)
        self.assertNotIn("a", fake._checked)

    def test_check_toggle_ignores_non_check_column(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # Only the two checkbox columns mutate state; a content column is inert.
        fake = _FakeSelf(scene_nodes=[("a", "T")])
        cd.CompileDialog._on_check_toggled(fake, cd._COL_NODE, "a", 0, True)
        self.assertEqual(fake._checked, set())

    def test_set_all_checked_true_then_false(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf(scene_nodes=[("a", "T"), ("b", "U")])
        cd.CompileDialog._set_all_checked(fake, True)
        self.assertEqual(fake._checked, {"a", "b"})
        self.assertEqual(fake.refresh_calls, 1)
        cd.CompileDialog._set_all_checked(fake, False)
        self.assertEqual(fake._checked, set())
        self.assertEqual(fake.refresh_calls, 2)

    def test_set_all_checked_noop_while_busy(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake       = _FakeSelf(scene_nodes=[("a", "T")])
        fake._busy = True
        cd.CompileDialog._set_all_checked(fake, True)
        self.assertEqual(fake._checked, set())


class TestRefreshResetsSelectionOnOpen(unittest.TestCase):
    """refresh_nodes() is the OPEN path -> it resets the checkbox selection so
    each open starts fresh (default unchecked) and never carries a previous
    scene's checks (node names aren't unique across scenes). The Refresh BUTTON
    path (_refresh_table) preserves in-session checks for surviving nodes."""

    def test_refresh_nodes_resets_checked_and_row_map(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake              = _FakeSelf(scene_nodes=[("a", "T")], checked=["a"])
        fake._row_by_type = {"T": 0}
        cd.CompileDialog.refresh_nodes(fake)
        self.assertEqual(fake._checked,      set())
        self.assertEqual(fake._row_by_type,  {})
        self.assertEqual(fake.refresh_calls, 1)  # delegated to _refresh_table

    def test_refresh_nodes_noop_while_busy(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake       = _FakeSelf(scene_nodes=[("a", "T")], checked=["a"])
        fake._busy = True
        cd.CompileDialog.refresh_nodes(fake)
        self.assertEqual(fake._checked, {"a"})  # untouched
        self.assertEqual(fake.refresh_calls, 0)

    def test_close_event_clears_busy(self):
        """Closing mid-compile must clear _busy so the next open's refresh runs
        (else refresh_nodes early-returns and shows the stale list)."""
        from mpynode.ui.dialogs import compile_dialog as cd
        import inspect

        src = inspect.getsource(cd.CompileDialog.closeEvent)
        self.assertIn("self._busy = False", src)


class TestDefaultNameFromScene(unittest.TestCase):
    def test_default_name_for_single_node_scene_uses_type(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf(scene_nodes=[("myNode1", "coolType")])
        self.assertEqual(cd.CompileDialog._default_name_for_scene(fake),
                         "coolType")

    def test_default_name_for_multi_node_scene_is_generic(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf(scene_nodes=[("a", "T"), ("b", "U")])
        self.assertEqual(cd.CompileDialog._default_name_for_scene(fake),
                         "compiledNodes")

    def test_init_seeds_scene_nodes_from_live_scene(self):
        """__init__ must populate _scene_nodes from the scene BEFORE _build_ui
        seeds the name field (so the single-node default can actually fire)."""
        from mpynode.ui.dialogs import compile_dialog as cd
        import inspect

        src = inspect.getsource(cd.CompileDialog.__init__)
        self.assertIn("_scene_mpy_nodes", src)
        self.assertNotIn("self._scene_nodes = []", src)


class TestPlanCompileRows(unittest.TestCase):
    def test_first_row_per_type_kept_duplicates_dropped(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        entries = [(0, "T"), (1, "U"), (2, "T"), (3, "U")]
        row_by_type, dropped = cd.CompileDialog._plan_compile_rows(entries)
        self.assertEqual(row_by_type, {"T": 0, "U": 1})
        self.assertEqual(dropped, [2, 3])

    def test_no_duplicates_drops_nothing(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        entries = [(0, "T"), (1, "U")]
        row_by_type, dropped = cd.CompileDialog._plan_compile_rows(entries)
        self.assertEqual(row_by_type, {"T": 0, "U": 1})
        self.assertEqual(dropped, [])


class TestDedupSpecsByType(unittest.TestCase):
    def test_dedup_drops_colliding_type_names(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        specs = [
            {"suggested": {"node_type_name": "fooNode"}},
            {"suggested": {"node_type_name": "barNode"}},
            {"suggested": {"node_type_name": "fooNode"}},
        ]
        unique, identical_dropped, diverged_dropped = \
            cd.CompileDialog._dedup_specs_by_type(specs)
        self.assertEqual([s["suggested"]["node_type_name"] for s in unique],
                         ["fooNode", "barNode"])
        # the two empty fooNode specs are byte-identical, so they collapse
        # silently; no code is lost and nothing is a lossy divergence.
        self.assertEqual(identical_dropped, ["fooNode"])
        self.assertEqual(diverged_dropped, [])


class TestToolbarLauncherWiring(unittest.TestCase):
    def test_toolbar_accepts_on_compile_and_builds_action(self):
        from mpynode.ui.widgets.toolbar import NDToolBar

        sig = inspect.signature(NDToolBar.__init__)
        self.assertIn("on_compile", sig.parameters)
        src = inspect.getsource(NDToolBar._build_buttons)
        self.assertIn("self._on_compile", src)

    def test_designer_build_toolbar_passes_on_compile(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_toolbar)
        self.assertIn("on_compile", src)

    def test_designer_has_open_compile_dialog_launcher(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(hasattr(NDMainWindow, "_open_compile_dialog"))

    def test_open_compile_dialog_is_non_modal_and_refreshes(self):
        """Non-modal (show/raise, not exec_) AND re-queries the scene on every
        open (refresh_nodes) so it never shows a previous scene's nodes. The old
        seed/add_nodes path is gone (the table lists the whole scene now)."""
        from mpynode.ui.mpynode_designer import NDMainWindow

        launcher = inspect.getsource(NDMainWindow._open_compile_dialog)
        self.assertIn("show", launcher)
        self.assertNotIn("exec_", launcher)
        self.assertIn("refresh_nodes", launcher)
        self.assertNotIn("add_nodes", launcher)


# ===================== from test_subprocess_verify.py =====================
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init
from tests import _paths


def _setUpModule__subprocess_verify():
    standalone_init()


_ROWS = [
    {
        "type_name": "fooNode",
        "spec": {
            "suggested": {"node_type_name": "fooNode", "mpx_base": "MPxNode"},
            "compute":   "self.out = self.a + 1.0",
            "init":      "",
            "inputs":    {"a": {"type": "float"}},
            "outputs":   {"out": {"type": "float"}},
        },
        # extra keys the verify ignores but rows carry in production:
        "build_status": "compiled",
    }
]


class TestSubprocessVerifyUnit(unittest.TestCase):
    def test_serializes_payload_and_parses_result(self):
        from mpynode.native.toolchain import subprocess_verify_fn

        captured = {}

        def fake_runner(argv, env, timeout):
            with open(env["MPYNODE_VERIFY_PAYLOAD"]) as fh:
                captured["payload"] = json.load(fh)
            captured["argv"] = argv
            # Emulate the worker writing a result.
            res = {"fooNode": {"ran": True, "pass": True, "maxerr": 1e-9,
                               "tol": 1e-4, "reason": ""}}
            with open(env["MPYNODE_VERIFY_RESULT"], "w") as fh:
                json.dump(res, fh)
            return 0

        vf = subprocess_verify_fn(maya="/Applications/Autodesk/maya2026",
                                  runner=fake_runner)
        out = vf("/tmp/out/myPlug.bundle", _ROWS)

        p   = captured["payload"]
        self.assertEqual(p["bundle_path"], "/tmp/out/myPlug.bundle")
        self.assertEqual(p["rows"][0]["type_name"], "fooNode")
        # The full spec must ride along so the worker can build the Python ref.
        self.assertIn("compute", p["rows"][0]["spec"])
        self.assertEqual(p["maya"], "/Applications/Autodesk/maya2026")
        # mayapy must be the FIRST argv token.
        self.assertIn("mayapy", captured["argv"][0])
        # Result parsed back, keyed by type_name.
        self.assertTrue(out["fooNode"]["pass"])

    def test_run_authored_tests_flag_rides_the_payload(self):
        """The dialog's opt-in "Run authored node tests" flag must reach the
        verify worker via the payload. Default True (headless callers keep
        running authored tests); the dialog passes False to make it opt-in."""
        from mpynode.native.toolchain import subprocess_verify_fn

        captured = {}

        def fake_runner(argv, env, timeout):
            with open(env["MPYNODE_VERIFY_PAYLOAD"]) as fh:
                captured["payload"] = json.load(fh)
            with open(env["MPYNODE_VERIFY_RESULT"], "w") as fh:
                json.dump({"fooNode": {"ran": False, "pass": None,
                                       "maxerr": None, "tol": None,
                                       "reason": ""}}, fh)
            return 0

        # Opt-OUT (the dialog default): the flag reaches the worker as False.
        subprocess_verify_fn(maya="/x", runner=fake_runner,
                             run_authored_tests=False)("/o/p.bundle", _ROWS)
        self.assertIs(captured["payload"]["run_authored_tests"], False)
        # Default is True (headless callers keep running authored tests).
        subprocess_verify_fn(maya="/x", runner=fake_runner)("/o/p.bundle", _ROWS)
        self.assertIs(captured["payload"]["run_authored_tests"], True)

    def test_no_result_file_degrades_to_skip_never_raises(self):
        from mpynode.native.toolchain import subprocess_verify_fn

        def fake_runner(argv, env, timeout):
            return 1  # writes no result file

        vf  = subprocess_verify_fn(maya="/x", runner=fake_runner)
        out = vf("/tmp/out/myPlug.bundle", _ROWS)
        self.assertIn("fooNode", out)
        self.assertFalse(out["fooNode"]["ran"])
        self.assertIsNone(out["fooNode"]["pass"])
        self.assertIn("subprocess", out["fooNode"]["reason"].lower())

    def test_runner_raises_degrades_to_skip(self):
        from mpynode.native.toolchain import subprocess_verify_fn

        def fake_runner(argv, env, timeout):
            raise RuntimeError("spawn failed")

        vf  = subprocess_verify_fn(maya="/x", runner=fake_runner)
        out = vf("/tmp/out/myPlug.bundle", _ROWS)
        self.assertFalse(out["fooNode"]["ran"])
        self.assertIsNone(out["fooNode"]["pass"])

    def test_empty_rows_returns_empty(self):
        from mpynode.native.toolchain import subprocess_verify_fn

        def fake_runner(argv, env, timeout):  # should not even be needed
            with open(env["MPYNODE_VERIFY_RESULT"], "w") as fh:
                json.dump({}, fh)
            return 0

        vf  = subprocess_verify_fn(maya="/x", runner=fake_runner)
        out = vf("/tmp/out/myPlug.bundle", [])
        self.assertEqual(out, {})

    def test_worker_run_dispatches_to_verify_impl(self):
        from mpynode.native.toolchain import _verify_worker_run

        seen = {}

        def fake_impl(bundle_path, rows, maya=None, run_authored_tests=True):
            seen["args"]               = (bundle_path, rows, maya)
            seen["run_authored_tests"] = run_authored_tests
            return {"fooNode": {"ran": True, "pass": True, "maxerr": 0.0,
                                "tol": 1e-4, "reason": ""}}

        payload = {"bundle_path": "/b/p.bundle", "rows": _ROWS, "maya": "/m",
                   "run_authored_tests": False}
        out = _verify_worker_run(payload, init_maya=False, verify_impl=fake_impl)
        self.assertEqual(seen["args"][0], "/b/p.bundle")
        self.assertEqual(seen["args"][2], "/m")
        # The worker forwards the payload's run_authored_tests flag to the impl.
        self.assertIs(seen["run_authored_tests"], False)
        self.assertTrue(out["fooNode"]["pass"])

    def test_worker_main_reads_env_and_writes_result(self):
        import tempfile

        from mpynode.native.toolchain import verify as cc

        d            = tempfile.mkdtemp(prefix="mpynode_vw_")
        payload_path = os.path.join(d, "payload.json")
        result_path  = os.path.join(d, "result.json")
        with open(payload_path, "w") as fh:
            json.dump({"bundle_path": "/b.bundle", "rows": _ROWS, "maya": "/m"},
                      fh)

        # Patch _verify_worker_run so we don't touch maya; assert env round-trip.
        orig = cc._verify_worker_run
        cc._verify_worker_run = lambda payload, **kw: {
            "fooNode": {"ran": True, "pass": True, "maxerr": 0.0, "tol": 1e-4,
                        "reason": ""}}
        os.environ["MPYNODE_VERIFY_PAYLOAD"] = payload_path
        os.environ["MPYNODE_VERIFY_RESULT"]  = result_path
        try:
            cc._verify_worker_main()
        finally:
            cc._verify_worker_run = orig
            os.environ.pop("MPYNODE_VERIFY_PAYLOAD", None)
            os.environ.pop("MPYNODE_VERIFY_RESULT", None)

        with open(result_path) as fh:
            res = json.load(fh)
        self.assertTrue(res["fooNode"]["pass"])


# --------------------------------------------------------------------------
# Integration: a REAL subprocess verify. Proves the live scene is untouched.
# --------------------------------------------------------------------------
_MAYA2026 = "/Applications/Autodesk/maya2026"
_HAS_2026 = os.path.isfile(
    os.path.join(_MAYA2026, "Maya.app", "Contents", "bin", "mayapy"))
_ROOT = _paths.ROOT
_BESSEL_DIR = os.path.join(
    _ROOT, "tools", "parity_sweep", "fixtures", "besselField")
_BESSEL_BUNDLE = os.path.join(_BESSEL_DIR, "besselField.bundle")
_HAS_BESSEL = os.path.isfile(_BESSEL_BUNDLE) and os.path.isfile(
    os.path.join(_BESSEL_DIR, "spec.json"))


@unittest.skipUnless(_HAS_2026 and _HAS_BESSEL,
                     "needs maya2026 mayapy + prebuilt besselField bundle")
class TestSubprocessVerifyIntegration(unittest.TestCase):
    def test_real_subprocess_verify_leaves_live_scene_intact(self):
        import maya.cmds as mc

        from mpynode.native.toolchain import subprocess_verify_fn

        # A clean live scene with a sentinel node that MUST survive.
        mc.file(new=True, force=True)
        marker = mc.createNode("transform", name="DO_NOT_WIPE_ME")
        self.assertTrue(mc.objExists(marker))

        with open(os.path.join(_BESSEL_DIR, "spec.json")) as fh:
            spec = json.load(fh)
        tn   = spec["suggested"]["node_type_name"]
        rows = [{"type_name": tn, "spec": spec}]

        vf   = subprocess_verify_fn(maya=_MAYA2026)
        out  = vf(_BESSEL_BUNDLE, rows)

        # THE FIX: the parent process's scene must be completely untouched.
        self.assertTrue(
            mc.objExists(marker),
            "subprocess verify WIPED the live scene -- the marker is gone!",
        )
        # And the round-trip produced a structured result for the node.
        self.assertIn(tn, out, "no verify result returned: %r" % out)
        row = out[tn]
        for k in ("ran", "pass", "maxerr", "tol", "reason"):
            self.assertIn(k, row, "verify row missing %r: %r" % (k, row))
        # Parity may pass, fail or skip on the subprocess's scipy
        # availability; the fix under test is the untouched scene.
        print("\n  [integration] besselField subprocess verify -> %r" % row)


def setUpModule():
    _setUpModule__compile_bundle_manager()
    _setUpModule__subprocess_verify()


if __name__ == "__main__":
    import unittest
    unittest.main()
