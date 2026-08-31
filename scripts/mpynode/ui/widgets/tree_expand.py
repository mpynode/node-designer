"""Shift-click a section header to expand / collapse EVERY section in a tree.

A small, reusable behavior for the Node Designer's ``QTreeWidget`` "section"
trees (the template gallery, Variables, Watch, Framework, and the Script-pane
outline). Normally Qt's branch arrow toggles a single row one level; holding **Shift**
while left-clicking an *expandable* row instead expands (or collapses) that
row's ENTIRE SUBTREE recursively -- and ONLY its own subtree, never its
siblings or ancestors (shift-collapsing "basics" leaves "advanced" and the
root exactly as they were). The direction follows the row you click:
shift-clicking a collapsed row expands it and everything beneath it,
shift-clicking an expanded row collapses it and everything beneath it. Each
row's expanded state is stored per-item by Qt, so a later plain click reflects
whatever the last shift action left underneath.

There is no shared collapsible base class in this codebase, so this installs on
any ``QTreeWidget`` via an event filter on its viewport -- no subclassing
required. Qt-guarded the same way as the rest of ``ui/`` (importing this module
raises ``ImportError`` when neither PySide6 nor PySide2 is present).
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import QEvent, QObject, Qt


def toggle_all_from(tree, item):
    """Recursively expand or collapse the SUBTREE rooted at ``item``.

    ``item`` must be an expandable row (``childCount() > 0``); a leaf row or
    ``None`` is a no-op. The direction follows ``item``'s current state: a
    collapsed row is expanded together with every descendant, an expanded row is
    collapsed together with every descendant. Only ``item``'s own subtree is
    touched -- siblings and ancestors keep their state, so shift-collapsing one
    folder never rolls the whole tree up to the root. Returns ``True`` when it
    acted (so an event filter can consume the click) and ``False`` otherwise.

    ``tree`` is accepted for call-site symmetry / the None guard; the work is
    done through ``item`` so the effect stays scoped to that branch.
    """
    if tree is None or item is None:
        return False
    try:
        if item.childCount() == 0:
            return False
        expand = not item.isExpanded()
    except Exception:
        return False
    _set_subtree_expanded(item, expand)
    return True


def _set_subtree_expanded(item, expand):
    """Set ``item`` and every descendant row's expanded state to ``expand``.

    Qt stores the expanded flag per item even while an ancestor is collapsed, so
    collapsing a whole branch still records each subfolder's collapsed state --
    reopening the branch later shows it closed, as the user left it."""
    item.setExpanded(expand)
    for i in range(item.childCount()):
        _set_subtree_expanded(item.child(i), expand)


class _ShiftClickExpandAll(QObject):
    """Event filter: Shift + left-click an expandable row -> expand/collapse all.

    Installed on a tree's viewport; parented to the tree so it shares its
    lifetime. Only a left button press with the Shift modifier landing on an
    expandable row is handled (and consumed); every other event passes straight
    through, so ordinary clicks, the native branch arrows, right-click menus and
    selection all behave exactly as before.
    """

    def __init__(self, tree):
        super().__init__(tree)  # parent to the tree -> lives/dies with it
        self._tree = tree

    def eventFilter(self, obj, event):
        try:
            if event.type() != QEvent.MouseButtonPress:
                return False
            if event.button() != Qt.LeftButton:
                return False
            if not (event.modifiers() & Qt.ShiftModifier):
                return False
            try:
                pos = event.position().toPoint()  # PySide6 (QPointF)
            except AttributeError:
                pos = event.pos()                 # PySide2
            item = self._tree.itemAt(pos)
            if toggle_all_from(self._tree, item):
                return True  # consume: no single-row toggle / selection change
        except Exception:
            return False
        return False


def install_shift_click_expand_all(tree):
    """Install shift-click-expand/collapse-all on ``tree`` (a ``QTreeWidget``).

    Returns the event-filter object (also stashed on the tree so a Python
    reference is kept alive). Safe to call once per tree; ``None`` in -> ``None``
    out.
    """
    if tree is None:
        return None
    filt = _ShiftClickExpandAll(tree)
    tree.viewport().installEventFilter(filt)
    tree._nd_shift_expand_filter = filt  # keep a ref (belt-and-braces)
    return filt
