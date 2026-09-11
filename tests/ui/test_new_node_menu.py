"""New-node menu UX.

Left-click a node type -> create using the default ``new_node_mode`` pref.
Right-click a node type -> a small menu exposing every create mode
(vanilla / with-header / from-template, the last gated by template existence).

Also covers the StayOpenMenu release-button gating: a right-click must NOT
create a node anymore (the old ``mouseReleaseEvent`` triggered on ANY button).
"""

from __future__ import annotations

import inspect
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # QApplication must exist before any QWidget/QMenu is constructed.
    from mpynode.ui.qt_wrapper import Qt
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        from PySide2.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    _QT = True
except Exception:  # pragma: no cover - Qt missing
    _QT = False


def setUpModule():
    # Some UI modules import maya.cmds at import time; init standalone AFTER the
    # QApplication above (the harness ordering rule for QWidget tests).
    try:
        from tests._setup import standalone_init

        standalone_init()
    except Exception:
        pass


class _FakeAction:
    """Stand-in for a QAction so the pure release-decision needs no widget."""

    def __init__(self, enabled=True, separator=False, submenu=None, data=None):
        self._enabled = enabled
        self._sep = separator
        self._menu = submenu
        self._data = data
        self.triggered_count = 0

    def isEnabled(self):
        return self._enabled

    def isSeparator(self):
        return self._sep

    def menu(self):
        return self._menu

    def data(self):
        return self._data

    def trigger(self):
        self.triggered_count += 1


@unittest.skipUnless(_QT, "Qt unavailable")
class TestReleaseDecision(unittest.TestCase):
    def _d(self, action, button, has_handler):
        from mpynode.ui.widgets.menus import _release_decision

        return _release_decision(action, button, has_handler)

    def test_left_click_leaf_triggers(self):
        self.assertEqual(self._d(_FakeAction(), Qt.LeftButton, False), "trigger")

    def test_right_click_leaf_with_handler_opens_options(self):
        self.assertEqual(self._d(_FakeAction(), Qt.RightButton, True), "options")

    def test_right_click_leaf_without_handler_is_noop(self):
        self.assertIsNone(self._d(_FakeAction(), Qt.RightButton, False))

    def test_right_click_never_triggers(self):
        # The bug being fixed: a right-click used to create a node.
        self.assertNotEqual(self._d(_FakeAction(), Qt.RightButton, True), "trigger")
        self.assertNotEqual(self._d(_FakeAction(), Qt.RightButton, False), "trigger")

    def test_separator_submenu_disabled_are_noop(self):
        self.assertIsNone(self._d(_FakeAction(separator=True), Qt.LeftButton, True))
        self.assertIsNone(self._d(_FakeAction(submenu=object()), Qt.LeftButton, True))
        self.assertIsNone(self._d(_FakeAction(enabled=False), Qt.LeftButton, True))

    def test_none_action_is_noop(self):
        self.assertIsNone(self._d(None, Qt.LeftButton, True))


@unittest.skipUnless(_QT, "Qt unavailable")
class TestOptionsMenu(unittest.TestCase):
    def test_vanilla_and_header_always_present(self):
        from mpynode.ui.widgets.menus import build_new_node_options_menu

        menu = build_new_node_options_menu(None, "mPyNode", lambda nt, m: None)
        texts = [a.text().lower() for a in menu.actions()]
        self.assertTrue(any("vanilla" in t for t in texts), texts)
        self.assertTrue(any("header" in t for t in texts), texts)

    def test_no_per_type_from_template_option(self):
        # The per-type right-click "From template" option is retired in favor
        # of the global "New from Template..." gallery action.
        from mpynode.ui.widgets.menus import build_new_node_options_menu

        for nt in ("mPyNode", "mPyDeformer", "mPyIkSolver"):
            menu = build_new_node_options_menu(None, nt, lambda *a: None)
            texts = [a.text().lower() for a in menu.actions()]
            self.assertFalse(
                any("template" in t for t in texts),
                "per-type 'From template' option must be removed: %r" % texts,
            )

    def test_options_only_offer_none_and_headers(self):
        from mpynode.ui.widgets.menus import build_new_node_options_menu

        calls = []
        menu = build_new_node_options_menu(
            None, "mPyDeformer", lambda nt, m: calls.append((nt, m))
        )
        for a in menu.actions():
            a.trigger()
        modes = [m for (_nt, m) in calls]
        self.assertEqual(set(modes), {"none", "headers"})
        self.assertTrue(all(nt == "mPyDeformer" for (nt, _m) in calls))


@unittest.skipUnless(_QT, "Qt unavailable")
class TestWiring(unittest.TestCase):
    """Both creation menus must set per-action node-type data, pass a
    right-click handler, and route to a mode-aware create call."""

    def test_toolbar_sets_data_and_right_click_handler(self):
        from mpynode.ui.widgets import toolbar

        src = inspect.getsource(toolbar)
        self.assertIn("setData(", src)
        self.assertIn("right_click_handler", src)
        self.assertIn("show_new_node_options", src)

    def test_designer_menu_sets_data_and_right_click_handler(self):
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer)
        self.assertIn("right_click_handler", src)
        self.assertIn("show_new_node_options", src)

    def test_new_node_command_accepts_mode_override(self):
        from mpynode.ui import mpynode_designer

        sig = inspect.signature(mpynode_designer.NDMainWindow._new_node_command)
        self.assertIn("mode", sig.parameters)

    def test_add_new_node_event_accepts_mode_override(self):
        from mpynode.ui import mpynode_designer

        sig = inspect.signature(mpynode_designer.NDMainWindow.addNewNodeEvent)
        self.assertIn("mode", sig.parameters)

    def test_main_window_has_post_create_helper(self):
        from mpynode.ui import mpynode_designer

        self.assertTrue(
            hasattr(mpynode_designer.NDMainWindow, "_post_create"),
            "addNewNodeEvent's select+open-tabs tail must be factored into "
            "_post_create(name) so the gallery path can reuse it",
        )
        sig = inspect.signature(
            mpynode_designer.NDMainWindow._post_create
        )
        # (self, name)
        self.assertIn("name", sig.parameters)

    def test_main_window_has_create_from_template(self):
        from mpynode.ui import mpynode_designer

        sig = inspect.signature(
            mpynode_designer.NDMainWindow._create_from_template
        )
        for p in ("payload", "native_type", "run_setup"):
            self.assertIn(p, sig.parameters)
        self.assertTrue(
            hasattr(mpynode_designer.NDMainWindow, "_on_new_from_template")
        )

    def test_create_from_template_routes_by_run_setup(self):
        # run_setup=False -> _ImportNodeCommand(seed_setup=True, restore
        # _persistent=False); run_setup=True -> _TemplateCreateCommand.
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(
            mpynode_designer.NDMainWindow._create_from_template
        )
        self.assertIn("_TemplateCreateCommand", src)
        self.assertIn("_ImportNodeCommand", src)
        self.assertIn("seed_setup", src)
        self.assertIn("restore_persistent", src)
        self.assertIn("run_undoable", src)
        self.assertIn("_post_create", src)

    def test_designer_wires_reveal_and_select(self):
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer)
        # The gallery is shown as a full-width mode now, not opened as a modal
        # dialog (Option B mode tabs).
        self.assertNotIn("open_template_gallery", src)
        self.assertIn("_show_templates_mode", src)
        self.assertIn("New from Template", src)


@unittest.skipUnless(_QT, "Qt unavailable")
class TestAutoAttachOption(unittest.TestCase):
    """Right-clicking an option (for wiring types) offers a 'Create + run setup'
    context so the user can wire the node to the current selection on purpose. A
    plain left-click create never runs setup."""

    def test_type_supports_attach_only_for_wiring_types(self):
        from mpynode.ui.widgets.menus import _type_supports_attach

        self.assertTrue(_type_supports_attach("mPyDeformer"))
        self.assertTrue(_type_supports_attach("mPyIkSolver"))
        self.assertTrue(_type_supports_attach("mPyMesh"))   # universal setup hook
        self.assertTrue(_type_supports_attach("mPyFile"))   # now has a setup source
        self.assertFalse(_type_supports_attach("mPyNode"))  # no setup source -> False anchor

    def test_option_items_carry_mode_data(self):
        from mpynode.ui.widgets.menus import build_new_node_options_menu

        menu = build_new_node_options_menu(None, "mPyNode", lambda *a: None)
        datas = {a.data() for a in menu.actions()}
        self.assertIn("none", datas)
        self.assertIn("headers", datas)

    def test_attach_context_invokes_on_create_with_autoconnect_true(self):
        from mpynode.ui.widgets.menus import build_attach_context_menu

        calls = []
        menu = build_attach_context_menu(
            None, "mPyDeformer", "headers",
            lambda nt, m, autoconnect: calls.append((nt, m, autoconnect)),
        )
        # The single auto-attach action must fire on_create(..., autoconnect=True).
        for a in menu.actions():
            a.trigger()
        self.assertIn(("mPyDeformer", "headers", True), calls)

    def test_options_menu_supports_attach_flag(self):
        from mpynode.ui.widgets.menus import build_new_node_options_menu

        m_wire = build_new_node_options_menu(None, "mPyDeformer", lambda *a: None)
        m_plain = build_new_node_options_menu(None, "mPyNode", lambda *a: None)
        self.assertTrue(m_wire._supports_attach)
        self.assertFalse(m_plain._supports_attach)

    def test_new_node_command_accepts_autoconnect(self):
        from mpynode.ui import mpynode_designer

        sig = inspect.signature(mpynode_designer.NDMainWindow._new_node_command)
        self.assertIn("autoconnect", sig.parameters)

    def test_add_new_node_event_accepts_autoconnect(self):
        from mpynode.ui import mpynode_designer

        sig = inspect.signature(mpynode_designer.NDMainWindow.addNewNodeEvent)
        self.assertIn("autoconnect", sig.parameters)

    def test_menus_module_wires_attach_context(self):
        from mpynode.ui.widgets import menus

        src = inspect.getsource(menus)
        self.assertIn("build_attach_context_menu", src)
        self.assertIn("auto-attach", src.lower())

    def test_attach_context_menu_label_says_run_setup(self):
        """The user-facing label for the right-click attach option should say
        'run setup', not the old 'auto-attach to selection' phrasing."""
        from mpynode.ui.widgets.menus import build_attach_context_menu

        calls = []
        menu = build_attach_context_menu(
            None, "mPyDeformer", "headers",
            lambda nt, m, ac: calls.append((nt, m, ac)),
        )
        actions = [a for a in menu.actions() if not a.isSeparator()]
        self.assertEqual(len(actions), 1)
        label = actions[0].text().lower()
        self.assertIn("run setup", label)
        self.assertNotIn("auto-attach", label)

    def test_build_new_or_setup_returns_setup_command_for_setup_type(self):
        from mpynode._base.commands import (
            _SetupNodeCommand, build_new_or_setup_command)
        cmd = build_new_or_setup_command("mPyMesh", mode=None, auto_setup=True)
        self.assertIsInstance(cmd, _SetupNodeCommand)
        cmd2 = build_new_or_setup_command("mPyNode", mode=None, auto_setup=True)
        self.assertNotIsInstance(cmd2, _SetupNodeCommand)


@unittest.skipUnless(_QT, "Qt unavailable")
class TestNewFromTemplateAction(unittest.TestCase):
    def test_node_menu_has_new_from_template_action(self):
        # The Node menu must offer a single global "New from Template..."
        # action wired to _on_new_from_template.
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._build_menu_bar)
        self.assertIn("New from Template", src)
        self.assertIn("_on_new_from_template", src)

    def test_toolbar_has_new_from_template(self):
        from mpynode.ui.widgets import toolbar

        src = inspect.getsource(toolbar)
        self.assertIn("New from Template", src)
        # The toolbar takes a hook callable rather than reaching back into the
        # main window (mirrors on_new_node / on_save_node).
        self.assertIn("on_new_from_template", src)

    def test_toolbar_ctor_accepts_on_new_from_template(self):
        from mpynode.ui.widgets.toolbar import NDToolBar

        sig = inspect.signature(NDToolBar.__init__)
        self.assertIn("on_new_from_template", sig.parameters)

    def test_designer_passes_on_new_from_template_to_toolbar(self):
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer)
        # The NDToolBar(...) construction must forward the gallery hook. The
        # keyword block is columnised, so the spacing around '=' is free.
        self.assertRegex(
            src, r"on_new_from_template\s*=\s*self\._on_new_from_template")


if __name__ == "__main__":
    unittest.main()
