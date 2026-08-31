"""Methods tab tier: registry/mixin + tab wiring

Consolidated from: test_methods_registry.py, test_methods_tab_wiring.py.
"""

from __future__ import annotations

# ===================== from test_methods_registry.py =====================
import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__methods_registry():
    standalone_init()
    ensure_plugins_loaded()


_CMD_SRC = (
    "from mpynode._common.methods.maya_command import maya_command\n"
    "\n"
    "@maya_command(name='setRegion', undoable=True)\n"
    "def set_region_ids(self, indices=None):\n"
    "    return indices\n"
)


class TestMethodsSourceMixin(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_locator import MPyLocator

        self.loc = MPyLocator.create(name="methTest")

    def test_set_get_has_clear(self):
        self.assertFalse(self.loc.has_methods_source())
        self.assertTrue(self.loc.set_methods_source(_CMD_SRC))
        self.assertEqual(self.loc.get_methods_source(), _CMD_SRC)
        self.assertTrue(self.loc.has_methods_source())
        self.loc.clear_methods_source()
        self.assertFalse(self.loc.has_methods_source())

    def test_plug_exists_after_set(self):
        import maya.cmds as mc

        self.loc.set_methods_source("x = 1\n")
        self.assertTrue(mc.attributeQuery(
            "_methodsSource", node=self.loc.get_name(), exists=True))

    def test_list_commands(self):
        self.loc.set_methods_source(_CMD_SRC)
        cmds = self.loc.list_commands()
        self.assertEqual([c["name"] for c in cmds], ["setRegion"])
        self.assertEqual(cmds[0]["func_name"], "set_region_ids")

    def test_call_command_binds_self_to_wrapper(self):
        self.loc.set_methods_source(
            "from mpynode._common.methods.maya_command import maya_command\n"
            "@maya_command\n"
            "def my_name(self):\n"
            "    return self.get_name()\n")
        self.assertEqual(self.loc.call_command("my_name"),
                         self.loc.get_name())

    def test_call_command_by_func_or_command_name(self):
        self.loc.set_methods_source(_CMD_SRC)
        # callable by the command name AND the python def name
        self.assertEqual(self.loc.call_command("setRegion", indices=[1, 2]),
                         [1, 2])
        self.assertEqual(self.loc.call_command("set_region_ids", indices=[3]),
                         [3])

    def test_call_unknown_command_raises(self):
        self.loc.set_methods_source(_CMD_SRC)
        with self.assertRaises(KeyError):
            self.loc.call_command("nope")

    def test_set_returns_false_on_syntax_error_but_keeps_text(self):
        bad = "def broken(:\n    pass\n"
        self.assertFalse(self.loc.set_methods_source(bad))
        # text is preserved so the user doesn't lose their edits
        self.assertEqual(self.loc.get_methods_source(), bad)

    def test_methods_isolated_from_compute(self):
        # A name defined in Methods must NOT leak into the compute namespace.
        self.loc.set_methods_source("SECRET = 123\n")
        # build_methods_namespace has it...
        self.assertEqual(self.loc.build_methods_namespace().get("SECRET"), 123)
        # ...but compute is independent: no API reads SECRET from compute.


class TestSpecCapturesMethods(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def test_methods_and_commands_in_spec(self):
        from mpynode.native.spec import spec_extractor
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="specMeth")
        loc.set_compute_expression("self.polygons = None\n")
        loc.set_methods_source(_CMD_SRC)
        spec = spec_extractor.extract_spec(loc.get_name())
        self.assertIn("methods", spec)
        self.assertEqual([c["name"] for c in spec["commands"]], ["setRegion"])

    def test_no_methods_means_no_keys(self):
        from mpynode.native.spec import spec_extractor
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="plainLoc")
        loc.set_compute_expression("self.polygons = None\n")
        spec = spec_extractor.extract_spec(loc.get_name())
        # A node with no methods keeps a byte-identical spec (no new keys).
        self.assertNotIn("methods", spec)
        self.assertNotIn("commands", spec)


# ===================== from test_methods_tab_wiring.py =====================
import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import ensure_plugins_loaded, standalone_init

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-methodstab-test"])


def _setUpModule__methods_tab_wiring():
    standalone_init()
    # Load the plugins so this module is order-independent in the shared
    # mayapy process; siblings create live mPyLocator nodes right after.
    ensure_plugins_loaded()


class TestMethodsTabWiring(unittest.TestCase):
    def _src(self, fn):
        from mpynode.ui.widgets import script_tab_content as stc

        return inspect.getsource(getattr(stc.NDScriptTabContent, fn))

    def test_no_methods_segment_is_built(self):
        # The Methods pane is DELETED. It drew methods and free functions flat
        # at column 0, so nothing distinguished a class member from a module
        # function; the API view shows them indented inside `class X:`.
        src = self._src("__init__")
        self.assertNotIn("NDScriptPane", src)
        self.assertNotIn("_script_pane", src)
        self.assertNotIn('"Methods"', src)
        self.assertNotIn("_outer_bar", src)

    def test_the_api_view_feeds_the_dirty_aggregate(self):
        # Methods editing moved there, so that is where the tab now learns an
        # edit happened.
        src = self._src("__init__")
        self.assertIn("self._api_view.dirtyStateChanged.connect", src)
        self.assertIn("self._on_inner_dirty_changed", src)

    def test_init_listed_before_compute(self):
        src = self._src("__init__")
        self.assertLess(src.index('addTab(self._init_editor'),
                        src.index('addTab(self._expr_editor'),
                        "Init tab must be listed before Compute")

    @unittest.skipIf(_QAPP is None, "no Qt available")
    def test_actual_tab_order_is_tiers_then_api(self):
        """A real strip for an mPyLocator: Init, Compute, API -- J3's "most
        nodes would have three tabs: init, compute and API". No Methods, no
        Expressions/Script outer bar."""
        import maya.cmds as mc
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="tabOrderLoc")
        w = NDScriptTabContent(loc)
        try:
            tabs = w._inner_tabs
            labels = [tabs.tabText(i) for i in range(tabs.count())]
            self.assertEqual(labels, ["Init", "Compute", "API"])
        finally:
            w.deleteLater()

    def test_api_view_in_dirty_aggregate(self):
        self.assertIn("_api_view", self._src("hasUnsavedChanges"))

    def test_api_view_in_marksaved_aggregate(self):
        self.assertIn("_api_view", self._src("markSaved"))

    def test_api_view_in_refresh_aggregate(self):
        self.assertIn("_api_view", self._src("refresh"))


class TestRetiredPaneNotReferenced(unittest.TestCase):
    """Two generations of Methods surface are now DELETED: ``methods_pane.py``
    (the two-view tab) and ``script_pane.py`` (the outline + raw-buffer pane
    that replaced it). Nothing may send a reader to either, and nothing may
    import them."""

    def test_deleted_modules_really_are_gone(self):
        import os
        from mpynode.ui.widgets import methods_editor

        widgets_dir = os.path.dirname(methods_editor.__file__)
        for dead in ("methods_pane.py", "script_pane.py"):
            self.assertFalse(
                os.path.isfile(os.path.join(widgets_dir, dead)),
                "%s is back -- this guard is obsolete" % dead)

    def test_methods_editor_docs_have_no_dead_pointer(self):
        import inspect
        from mpynode.ui.widgets import methods_editor

        src = inspect.getsource(methods_editor)
        for dead in ("methods_pane.py", "NDMethodsPane"):
            self.assertNotIn(dead, src,
                             "methods_editor still points at the deleted %s"
                             % dead)

    def test_nothing_imports_the_deleted_pane(self):
        import os
        from mpynode.ui import widgets

        root = os.path.dirname(os.path.dirname(widgets.__file__))
        offenders = []
        for base, _dirs, files in os.walk(root):
            if "__pycache__" in base:
                continue
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                if ("from mpynode.ui.widgets.script_pane" in text
                        or "import script_pane" in text):
                    offenders.append(path)
        self.assertEqual(offenders, [])


class TestAmbientMethodsHeader(unittest.TestCase):
    """The seeded Methods header no longer carries the decorator import line --
    the decorators are ambient (pre-injected at runtime, re-synthesized at bake).
    It is still comment-only, so it routes entirely to the Methods view."""

    def test_header_has_no_decorator_import(self):
        from mpynode._common.methods.methods_registry import make_methods_header

        hdr = make_methods_header("mPyLocator")
        self.assertNotIn("import maya_command", hdr)
        self.assertNotIn("import maya_demo", hdr)

    def test_header_teaches_module_strip_and_ambient_decorator(self):
        from mpynode._common.methods.methods_registry import make_methods_header

        hdr = make_methods_header("mPyLocator")
        self.assertIn("Module", hdr)              # points at the Module strip
        self.assertIn("no import needed", hdr)    # states decorators are ambient
        self.assertIn("@maya_command", hdr)       # still shows the example

    def test_header_routes_entirely_to_methods_view(self):
        from mpynode._common.methods.methods_registry import make_methods_header
        from mpynode._common.methods.methods_split import split_methods_source

        hdr = make_methods_header("mPyLocator")
        functions_text, methods_text = split_methods_source(hdr)
        self.assertEqual(functions_text, "")      # Module strip empty
        self.assertEqual(methods_text, hdr)       # whole header in Methods view


def setUpModule():
    _setUpModule__methods_registry()
    _setUpModule__methods_tab_wiring()


if __name__ == "__main__":
    import unittest
    unittest.main()
