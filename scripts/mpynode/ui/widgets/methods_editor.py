"""Editor views for the per-node ``_methodsSource`` plug.

RETIRED SURFACE: the two-view **Methods** tab these classes backed -- and the
coordinator module that owned it -- are DELETED. Its replacement,
``script_pane.py``'s ``NDScriptPane``, has since been deleted too: the Methods
source is edited in the Script tab's API view (``api_view.py``), inside the
baked ``class X:`` where scope is visible. What follows describes the retired
split, which the views below still implement.

The plug stores ALL method material as one mixed Python namespace, shown as ONE
**Methods** tab: the class-body editor (``NDMethodsEditor`` -- class-bound defs:
``self``/``cls``-first, ``@classmethod``/``@staticmethod``) with a collapsible
**"Module"** strip pinned on top (``NDFunctionsEditor`` -- module-level material:
free functions, imports, constants, helper classes -- the code OUTSIDE the
class). The split is a UI view only; the node keeps its single ``_methodsSource``
string plug, split on load and re-joined on save -- see
``_common/methods/methods_split.py``. The class/attribute name ``functions_*``
is retained for the module-preamble editor; only the user-facing label changed to
"Module".

Both views are the same Python editor (line numbers, syntax highlighting, font
zoom) as NDInitEditor / NDScriptEditor. They do NO node IO themselves: the owning
coordinator holds the single ``set_methods_source`` write, so the two editors
can never clobber each other. Each view keeps only a local dirty baseline
(``setContent`` / ``markSavedLocal`` are the coordinator's hooks).

A ``def`` flagged ``@maya_command`` becomes a companion command (callable in the
interpreted node, compiled into an MPxCommand by the native pipeline); it rides
in whichever view its signature dictates (almost always Methods). NOTE:
companion-command *compilation* is currently supported only on mPyLocator (the
meshRegion keystone); the native pipeline fails loud if commands are authored on
another node type.
"""
from __future__ import annotations

from mpynode.ui.qt_wrapper import Signal
from mpynode.ui.widgets.editor_core import QtPythonEditor


class _NDMethodsBaseEditor(QtPythonEditor):
    """Shared base for the two views of a node's ``_methodsSource`` plug.

    Holds the editor text + a local dirty baseline but performs NO node IO: the
    owning coordinator splits the plug into the two views on load and owns the
    single write on save (join both, write once). ``setContent`` /
    ``markSavedLocal`` are the coordinator's hooks; there is deliberately no
    node-reading ``refresh`` or node-writing ``markSaved`` here.
    """

    dirtyStateChanged = Signal(bool)

    def __init__(self, py_node, parent=None):
        super().__init__(parent)
        self._py_node = py_node
        self._last_saved_text: str = ""
        self._suppress_change_signal = False
        self.textChanged.connect(self._on_text_changed)

    def getMPyNode(self):
        return self._py_node

    def getText(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self._suppress_change_signal = True
        try:
            self.setPlainText(text)
        finally:
            self._suppress_change_signal = False

    def hasUnsavedChanges(self) -> bool:
        return self.getText() != self._last_saved_text

    def setContent(self, text: str) -> None:
        """Load this view's content from the pane + reset the dirty baseline."""
        self.setText(text)
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)

    def markSavedLocal(self) -> None:
        """Reset the dirty baseline to the current text. NO node IO -- the pane
        already performed the single ``set_methods_source`` write."""
        self._last_saved_text = self.getText()
        self.dirtyStateChanged.emit(False)

    def _on_text_changed(self) -> None:
        if self._suppress_change_signal:
            return
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())

    def contextMenuEvent(self, event):
        """Standard editor right-click menu (Undo / Cut / Copy / Paste / Select
        All via ``createStandardContextMenu``), kept deliberately simple and
        identical across the Methods / Module views. The compute-oriented
        Load / Save / rename items on the shared QtPythonEditor base do not apply
        to the methods plug, so they are intentionally not carried here. Mirrors
        the base's ``menu.exec_(...)`` idiom so it behaves identically under
        PySide2 (Maya 2024) and PySide6 (2026)."""
        menu = self.createStandardContextMenu()
        menu.exec_(event.globalPos())


class NDFunctionsEditor(_NDMethodsBaseEditor):
    """The "Module" view of ``_methodsSource``: module-level material -- free
    functions (no ``self``/``cls``), imports, constants/assignments, helper
    classes -- parsed out by ``split_methods_source`` (the code OUTSIDE the
    class). Rendered in the collapsible Module strip at the top of the Methods
    tab. Inherits the base's plain context menu; it has no setup/demo (those are
    ``self``-first methods). Class/attribute name kept as ``functions_*`` for
    compatibility; only the user-facing label is "Module"."""


class NDMethodsEditor(_NDMethodsBaseEditor):
    """The "Methods" view of ``_methodsSource``: class-bound defs (instance
    ``self``-first, ``@classmethod``, ``@staticmethod``, ``cls``-first) parsed
    out by ``split_methods_source``. This is the PRIMARY view -- it carries the
    setup/demo right-click menu and receives the empty-node header."""

    def contextMenuEvent(self, event):
        """Methods-view right-click menu: the standard editor menu plus a
        "Run setup on selection" item and one or more "Run demo" items -- shown
        ONLY when this node's Methods source defines a self-first
        ``def setup(self, ...)`` / at least one demo (``@maya_demo`` or the
        reserved ``def demo``). One demo -> a single flat action; two or more ->
        a "Run demo (new scene)" submenu of labeled entries.

        Overriding here (rather than on the shared QtPythonEditor base) keeps the
        items out of the Compute / Init / Viewport / OSL tabs -- and out of the
        Module strip, which never holds a self-first setup/demo. Mirrors the
        base's ``menu.exec_(...)`` idiom so it behaves identically under PySide2
        (Maya 2024) and PySide6 (2026)."""
        menu = self.createStandardContextMenu()
        has_setup = False
        demos = []
        try:
            from mpynode._common import node_setups

            src = self._py_node.get_methods_source() or ""
            has_setup = node_setups.find_setup(src) is not None
            demos = node_setups.find_demos(src)
        except Exception:
            has_setup = False
            demos = []
        if has_setup or demos:
            menu.addSeparator()
            if has_setup:
                act = menu.addAction("Run setup on selection")
                act.triggered.connect(self._run_setup_on_selection)
            if len(demos) == 1:
                dact = menu.addAction("Run demo (new scene)")
                dact.triggered.connect(
                    lambda checked=False, dn=demos[0].func_name:
                    self._run_demo(dn))
            elif demos:
                submenu = menu.addMenu("Run demo (new scene)")
                for spec in demos:
                    a = submenu.addAction(spec.label)
                    a.triggered.connect(
                        lambda checked=False, dn=spec.func_name:
                        self._run_demo(dn))
        menu.exec_(event.globalPos())

    def _run_setup_on_selection(self):
        """Run THIS node's own ``setup`` against the live Maya selection, in one
        undo chunk (delegates to ``_RunSetupCommand`` via ``run_undoable``)."""
        from mpynode._base.commands import _RunSetupCommand, run_undoable

        run_undoable(_RunSetupCommand(
            self._py_node.get_name(),
            self._py_node.NATIVE_TYPE))

    def _run_demo(self, demo_name=None):
        """Run THIS node's own demo (which fabricates its own showcase scene,
        NO selection), in one undo chunk (delegates to ``_RunDemoCommand`` via
        ``run_undoable``). ``demo_name`` selects among multiple demos."""
        from mpynode._base.commands import _RunDemoCommand, run_undoable

        run_undoable(_RunDemoCommand(
            self._py_node.get_name(),
            self._py_node.NATIVE_TYPE,
            demo_name))
