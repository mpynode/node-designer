"""Shared menu helpers for the Node Designer.

``StayOpenMenu`` keeps a popup menu open after a (leaf) action is
triggered, so users can fire several actions in a row -- e.g. create
several nodes from the New ▾ / Node ▸ New Node pulldown without having to
reopen it each time. The menu closes on click-away or Esc, as usual.

New-node UX:
  * LEFT-click a node type   -> create it using the default ``new_node_mode``
    preference (the usual one-click create).
  * RIGHT-click a node type  -> a small menu exposing the create modes
    (vanilla / with-header). The pref is just the left-click default;
    right-click always offers the full choice. (Per-type "From template"
    is retired -- use the global "New from Template…" gallery action.)

The right-click handler is wired in by the owning menu (toolbar / Node menu)
via ``right_click_handler``; ``show_new_node_options`` + ``build_new_node_
options_menu`` are the shared builders so both menus behave identically.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import Qt, QMenu


def _release_decision(action, button, has_handler):
    """Decide what a mouse release over ``action`` should do in a StayOpenMenu.

    Returns one of:
      * ``"trigger"`` -- fire the action and keep the menu open (LEFT click on
        a leaf action);
      * ``"options"`` -- delegate to the right-click handler (RIGHT click on a
        leaf action, when a handler is wired);
      * ``None``      -- fall back to the default ``QMenu`` handling.

    Pure (no Qt widget needed) so the button-gating logic is unit-testable.
    Crucially, ONLY a left click ever returns ``"trigger"`` -- the old code
    fired on any button, which is why a right-click also created a node.
    """
    is_leaf = (
        action is not None
        and action.isEnabled()
        and not action.isSeparator()
        and action.menu() is None
    )
    if not is_leaf:
        return None
    if button == Qt.LeftButton:
        return "trigger"
    if button == Qt.RightButton and has_handler:
        return "options"
    return None


class StayOpenMenu(QMenu):
    """QMenu that does NOT close when a normal (leaf) action is LEFT-clicked.

    Submenus, disabled items, and separators behave normally. A right-click on
    a leaf action is delegated to ``right_click_handler(action, global_pos)``
    when one is supplied (used to pop up the per-type create-mode options);
    without a handler a right-click is a no-op (it no longer creates a node).
    """

    def __init__(self, *args, right_click_handler=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._right_click_handler = right_click_handler

    def mouseReleaseEvent(self, event):
        action = self.activeAction()
        decision = _release_decision(
            action, event.button(), self._right_click_handler is not None
        )
        if decision == "trigger":
            action.trigger()
            event.accept()
            return
        if decision == "options":
            try:
                pos = event.globalPos()
            except AttributeError:  # PySide6: globalPos() -> globalPosition()
                pos = event.globalPosition().toPoint()
            self._right_click_handler(action, pos)
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _type_supports_attach(native_type):
    """True if creating ``native_type`` can auto-attach to the selection -- i.e.
    a wiring type (deformer / skin / blend / IK) that ``node_setup`` knows how to
    set up. Types without a setup source (e.g. mPyNode) cannot. Never raises."""
    try:
        from mpynode._common import node_setups

        return bool(node_setups.type_has_setup(native_type))
    except Exception:
        return False


def build_attach_context_menu(parent, native_type, mode, on_create):
    """Return the one-entry right-click context for a create-mode option:
    "Create + run setup", which calls ``on_create(native_type, mode, True)`` so
    the node is created + wired to the current selection. A plain left-click
    create never runs setup; this right-click is the explicit opt-in."""
    ctx = QMenu(parent)
    ctx.addAction(
        "Create + run setup",
        lambda *a: on_create(native_type, mode, True),
    )
    return ctx


class NewNodeOptionsMenu(QMenu):
    """The right-click [Vanilla / With header] menu for a node
    type.

      * LEFT-click an item   -> create in that mode (no setup, the same as the
        normal left-click create).
      * RIGHT-click an item  -> for WIRING types only, pops a small context
        ("Create + run setup") so the user can wire the node to the current
        selection on purpose. For non-wiring types a right-click is inert.
    """

    def __init__(self, parent, native_type, on_create):
        super().__init__(parent)
        self._native_type = native_type
        self._on_create = on_create
        self._supports_attach = _type_supports_attach(native_type)
        self.setToolTipsVisible(True)

    def mouseReleaseEvent(self, event):
        action = self.activeAction()
        is_leaf = (
            action is not None
            and action.isEnabled()
            and not action.isSeparator()
            and action.menu() is None
        )
        if (
            is_leaf
            and event.button() == Qt.RightButton
            and self._supports_attach
        ):
            try:
                pos = event.globalPos()
            except AttributeError:  # PySide6
                pos = event.globalPosition().toPoint()
            ctx = build_attach_context_menu(
                self, self._native_type, action.data(), self._on_create
            )
            try:
                ctx.exec_(pos)
            except AttributeError:
                ctx.exec(pos)
            event.accept()
            return
        super().mouseReleaseEvent(event)


def build_new_node_options_menu(parent, native_type, on_create):
    """Return a :class:`NewNodeOptionsMenu` of create-mode options for
    ``native_type``.

    Always offers "Vanilla (no header)" and "With header". Per-type "From
    template" is retired -- use the global "New from Template…" gallery action
    instead. LEFT-click an
    entry calls ``on_create(native_type, mode)`` (no setup); for wiring types a
    RIGHT-click on an entry offers a "Create + run setup" context that calls
    ``on_create(native_type, mode, True)``.
    ``mode`` is ``"none"`` / ``"headers"``.
    """
    menu = NewNodeOptionsMenu(parent, native_type, on_create)

    def _add(text, mode):
        act = menu.addAction(text, lambda *a, m=mode: on_create(native_type, m))
        act.setData(mode)
        if menu._supports_attach:
            act.setToolTip("Right-click: create + run setup")
        return act

    _add("Vanilla (no header)", "none")
    _add("With header", "headers")
    return menu


def show_new_node_options(parent, action, on_create, global_pos):
    """Right-click handler: pop up the create-mode options for ``action``'s
    node type (read from ``action.data()``). ``on_create(native_type, mode)``.

    Returns False (and shows nothing) if the action carries no node type.
    """
    native_type = action.data() if action is not None else None
    if not native_type:
        return False
    menu = build_new_node_options_menu(parent, native_type, on_create)
    try:
        menu.exec_(global_pos)
    except AttributeError:  # PySide6 renamed exec_ -> exec
        menu.exec(global_pos)
    return True
