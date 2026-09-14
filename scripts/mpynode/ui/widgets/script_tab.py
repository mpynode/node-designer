"""NDScriptTabWidget \u2014 the tab-per-node script editor container.

Features: one tab per opened mPy node, ``activeNodeChanged`` signal,
dirty tracking + Save / Save All + tab-close confirm, and an
``NDScriptEditor`` (line numbers + syntax highlighting + Ctrl+wheel
zoom).
"""

from __future__ import annotations

from mpynode._base.commands import _SetExpressionCommand, run_undoable
from mpynode.ui.qt_wrapper import (
    QMessageBox,
    QPainter,
    Qt,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Signal,
)
from mpynode.ui.widgets.logo_relief import paint_relief
from mpynode.ui.widgets.script_editor import NDScriptEditor
from mpynode.ui.widgets.tall_tab_bar import taller


class NDEditorTabBar(QTabBar):
    """QTabBar that makes the close ("X") button reliable on a *movable*
    tab bar.

    Stock Qt arms a tab drag on mouse-press anywhere on the tab. When the
    bar is movable + closable, the slightest cursor twitch between press and
    release on the X starts a tab *move* and the close click is lost -- so
    closes feel flaky and "off-target". This bar fixes that two ways:

      * The clickable close region is padded by a few px (forgiving aim).
      * When a press lands on that region we do NOT let the base class arm
        a drag; we emit ``tabCloseRequested`` on release instead (if the
        cursor is still over the region -- standard button cancel-on-drag).

    Presses on the tab body still select + drag-reorder as usual. Exact hits
    on Qt's own close button keep working untouched (those events go to the
    child button and never reach this override, so there's no double-close).
    """

    # Extra padding (px) around Qt's close button to widen the aim target.
    _CLOSE_HIT_PAD = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending_close = -1

    def tabSizeHint(self, index):
        # Taller tabs, matching the other horizontal strips. Only the height
        # grows, so the close button + padded hit target are unaffected.
        return taller(super().tabSizeHint(index))

    def _close_rect(self, index: int):
        """Padded close-button rect for ``index`` (tab-bar coords), or None."""
        for side in (QTabBar.RightSide, QTabBar.LeftSide):
            btn = self.tabButton(index, side)
            if btn is not None and btn.isVisible():
                pad = self._CLOSE_HIT_PAD
                return btn.geometry().adjusted(-pad, -pad, pad, pad)
        return None

    def _close_index_at(self, pos) -> int:
        for i in range(self.count()):
            rect = self._close_rect(i)
            if rect is not None and rect.contains(pos):
                return i
        return -1

    def mousePressEvent(self, event):
        self._pending_close = -1
        # Middle-click has no per-tab-bar handler: selecting a tab's node is a
        # GLOBAL Designer shortcut (NDMainWindow.eventFilter) that resolves the
        # tab via ``middleClickNodeName`` below, so middle-press falls through
        # to the base class here. Right-click closes the tab, same path as the
        # X and its unsaved-changes prompt.
        if event.button() == Qt.RightButton:
            idx = self.tabAt(event.pos())
            if idx >= 0:
                self.tabCloseRequested.emit(idx)
                event.accept()
                return
        if event.button() == Qt.LeftButton:
            idx = self._close_index_at(event.pos())
            if idx >= 0:
                # On the padded close target: arm a close and do NOT forward,
                # so no tab drag can start.
                self._pending_close = idx
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # While a close is armed, swallow movement so no reorder begins.
        if self._pending_close >= 0:
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pending_close >= 0 and event.button() == Qt.LeftButton:
            idx                 = self._pending_close
            self._pending_close = -1
            # Drag-off cancels, matching normal push-button behaviour.
            if self._close_index_at(event.pos()) == idx:
                self.tabCloseRequested.emit(idx)
            event.accept()
            return
        self._pending_close = -1
        super().mouseReleaseEvent(event)

    def middleClickNodeName(self, global_pos):
        """mPyNode name for the tab under ``global_pos`` (screen coords), or None.

        Participates in the Designer's global middle-click shortcut
        (:meth:`NDMainWindow.eventFilter`): a middle-click anywhere resolves the
        node under the cursor, and over this tab bar that is the clicked tab's
        node. Replaces the old per-tab-bar middle-click override.
        """
        try:
            idx = self.tabAt(self.mapFromGlobal(global_pos))
            if idx < 0:
                return None
            owner  = self.parentWidget()
            getter = getattr(owner, "nodeNameForIndex", None)
            if callable(getter):
                return getter(idx)
        except Exception:
            pass
        return None


class NDScriptEditorPlaceholder(QWidget):
    """Editable QTextEdit + dirty tracking.

    replaces this with the real `NDScriptEditor` (line numbers
    + syntax highlighting). Same public API: getText / setText /
    hasUnsavedChanges / markSaved / refresh / getMPyNode.
    """

    # Lets the tab widget update the dirty marker in the tab title.
    dirtyStateChanged = Signal(bool)

    def __init__(self, py_node, parent=None):
        super().__init__(parent)
        self._py_node = py_node
        self._last_saved_text: str = ""
        self._suppress_change_signal = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._editor = QTextEdit(self)
        self._editor.setReadOnly(False)
        layout.addWidget(self._editor)

        self.refresh()
        self._editor.textChanged.connect(self._on_text_changed)

    # ------------------------------------------------------------------
    # Public API (kept identical for swap-in)
    # ------------------------------------------------------------------

    def getMPyNode(self):
        return self._py_node

    def getText(self) -> str:
        return self._editor.toPlainText()

    def setText(self, text: str) -> None:
        self._suppress_change_signal = True
        try:
            self._editor.setPlainText(text)
        finally:
            self._suppress_change_signal = False

    def hasUnsavedChanges(self) -> bool:
        return self.getText()!= self._last_saved_text

    def markSaved(self) -> None:
        """Mark the editor's current text as the last-saved baseline."""
        self._last_saved_text = self.getText()
        self.dirtyStateChanged.emit(False)

    def refresh(self) -> None:
        """Re-pull the expression from the node and reset the dirty baseline."""
        try:
            text = self._py_node.get_compute_expression() or ""
        except Exception:
            text = ""
        self.setText(text)
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        if self._suppress_change_signal:
            return
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())


def _sweepCallbackTokens(tokens: list) -> None:
    """Unregister + clear CALLBACK_MANAGER tokens in place. Safe to call twice.

    Module-level (not a method) so the ``destroyed`` handler can hold the token
    LIST without holding the widget.
    """
    if not tokens:
        return
    from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER

    for tok in list(tokens):
        try:
            CALLBACK_MANAGER.unregister(tok)
        except Exception:
            pass
    del tokens[:]


class NDScriptTabWidget(QTabWidget):
    """Tab-per-node container. One tab per opened node.

    Drives the cascade via ``activeNodeChanged`` and the
    Save / Save All workflow via ``saveCurrentTab`` / ``saveAllTabs``.
    """

    # Active tab changed.
    activeNodeChanged = Signal(object)

    # Tab saved. Useful for status bar updates etc.
    tabSaved = Signal(object)  # py_node of the just-saved tab

    # The SET of open tabs changed. Carries the current open node names so
    # listeners can reconcile per-node MNodeMessage callbacks against it.
    tabsChanged = Signal(list)

    # Aggregated from each tab's OSL editor: a compile_bridge hand-off dict
    # the designer routes to the assistant panel.
    handoffToAssistant = Signal(object)
    # Aggregated from each tab's API view: a persistent-variable name the
    # designer reveals on the left-hand Variables tab.
    revealVariableRequested = Signal(str)
    # Aggregated from each tab's API view: "Inputs" / "Outputs", which the
    # designer turns into a raise of the left-hand Attributes tab.
    revealAttributesRequested = Signal(str)
    # Aggregated from each tab's tier strip: the active tier's NAME. The
    # Framework panel shows only the surface that tier can reach, so it must
    # follow the strip.
    tierChanged  = Signal(str)

    DIRTY_MARKER = " *"

    def __init__(self, parent=None):
        super().__init__(parent)
        # NDEditorTabBar gives a reliable close button on a movable bar.
        # Install BEFORE movable/closable, so it owns the close buttons.
        self.setTabBar(NDEditorTabBar(self))
        self.setMovable(True)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._on_tab_close_requested)
        self.currentChanged.connect(self._on_current_changed)
        # CALLBACK_MANAGER tokens for the before-duplicate hook below.
        self._scene_cb_tokens: list = []
        self._attachSceneCallbacks()

    # ------------------------------------------------------------------
    # Native-duplicate interception (T54)
    # ------------------------------------------------------------------

    def _attachSceneCallbacks(self) -> None:
        """Hook Maya's own duplicate so it cannot read stale plugs.

        The Designer's Duplicate / Convert / Export handlers already call
        ``saveTabsForNode`` first, but Maya's NATIVE duplicate (Ctrl+D,
        ``cmds.duplicate``) reads the DG directly -- and the code editors write
        their plugs only on an explicit Save. So a node the user has been typing
        in duplicated with the last-SAVED (often empty) expression.

        The handle rides CALLBACK_MANAGER so plugin uninit sweeps it, and the
        widget's ``destroyed`` signal removes it too: a Maya callback still
        pointing at a deleted QWidget is a crash, not a leak.
        """
        try:
            from maya import OpenMaya as om

            from mpynode._common.lifecycle.callbacks import (
                CALLBACK_MANAGER,
                OWNER_SHARED,
            )

            cb_id = om.MModelMessage.addBeforeDuplicateCallback(
                self._onBeforeDuplicate)
            self._scene_cb_tokens.append(
                CALLBACK_MANAGER.register(
                    cb_id, om.MMessage.removeCallback, OWNER_SHARED))
        except Exception:
            # Maya unavailable / older API: no interception, same as before.
            return
        # Capture the TOKEN LIST, not self -- a lambda closing over self would
        # keep the widget alive past the very destruction it is cleaning up for.
        tokens = self._scene_cb_tokens
        try:
            self.destroyed.connect(lambda *_: _sweepCallbackTokens(tokens))
        except Exception:
            pass

    def detachSceneCallbacks(self) -> None:
        """Remove the before-duplicate hook. Idempotent."""
        _sweepCallbackTokens(self._scene_cb_tokens)

    def _onBeforeDuplicate(self, *_args) -> None:
        # Fires on Maya's thread inside the duplicate; never let it raise, or
        # the duplicate the user asked for dies with it.
        try:
            self.flushDirtyTabsBeforeDuplicate()
        except Exception:
            pass

    def flushDirtyTabsBeforeDuplicate(self) -> int:
        """Flush every dirty tab to its plugs. Returns the number saved.

        Deliberately NOT scoped to the selection the way ``saveTabsForNode`` is:
        at this point Maya has not said what it is about to copy (``duplicate``
        may take explicit names, a selected transform whose SHAPE holds the mPy
        node, or upstream history), so scoping by guesswork would miss the one
        node that matters -- which is the whole defect. Over-flushing costs an
        extra undo entry and writes the user's own typed text to their own node;
        under-flushing loses it.

        Quiet: the explicit-Save syntax-error popup is suppressed here. A
        half-typed expression is the normal state at duplicate time, and a modal
        nested inside Maya's before-duplicate callback blocks the operation it
        is running inside. The text still reaches the plug.
        """
        return self.saveAllTabs(quiet=True)

    # ------------------------------------------------------------------
    # Empty-state relief (the embossed mPyNode logo)
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        super().paintEvent(event)
        # Only when the editor area is empty (no node open). The template
        # gallery paints the same relief for a row without a preview; both
        # go through logo_relief.paint_relief, so they cannot drift apart.
        if self.count() > 0:
            return
        p = QPainter(self)
        try:
            paint_relief(p, self.rect())
        finally:
            p.end()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def addOrRaiseTab(self, py_node) -> int:
        idx = self.getIndexOfNode(py_node)
        if idx >= 0:
            self.setCurrentIndex(idx)
            return idx
        result = self._addNewTab(py_node)
        # Tab list grew -- notify.
        self.tabsChanged.emit(self.getOpenNodeNames())
        return result

    def getIndexOfNode(self, py_node) -> int:
        if py_node is None:
            return -1
        target_name = py_node.get_name()
        for i in range(self.count()):
            tab      = self.widget(i)
            tab_node = tab.getMPyNode() if hasattr(tab, "getMPyNode") else None
            if tab_node is not None and tab_node.get_name() == target_name:
                return i
        return -1

    def getCurrentNode(self):
        if self.count() == 0:
            return None
        tab = self.currentWidget()
        if tab is None or not hasattr(tab, "getMPyNode"):
            return None
        return tab.getMPyNode()

    def getCurrentTab(self):
        return self.currentWidget()

    def getAllTabs(self) -> list:
        return [self.widget(i) for i in range(self.count())]

    def refreshIdentityViewsForNode(self, node_name: str) -> int:
        """Re-bake the API view and Outline of every open tab for ``node_name``
        -- its Class changed -- leaving the expression editors alone (see
        ``NDScriptTabContent.refreshIdentityViews``). Returns the tab count."""
        n = 0
        for tab in self.getAllTabs():
            fn   = getattr(tab, "refreshIdentityViews", None)
            node = tab.getMPyNode() if hasattr(tab, "getMPyNode") else None
            if fn is None or node is None:
                continue
            try:
                if node.get_name() != node_name:
                    continue
                fn()
                n += 1
            except Exception:
                pass
        return n

    def nodeNameForIndex(self, idx: int):
        """Name of the mPyNode owning tab ``idx`` (or None).

        Pure accessor. The Designer's global middle-click shortcut
        (:meth:`NDMainWindow.eventFilter`, via
        :meth:`NDEditorTabBar.middleClickNodeName`) uses this to select the
        clicked tab's node in the Maya scene. Supersedes the old
        ``selectNodeInSceneForIndex`` action, now centralized on the window.
        """
        if idx < 0 or idx >= self.count():
            return None
        tab  = self.widget(idx)
        node = tab.getMPyNode() if hasattr(tab, "getMPyNode") else None
        if node is None:
            return None
        try:
            return node.get_name()
        except Exception:
            return None

    def closeTabForNode(self, name: str) -> bool:
        for i in range(self.count()):
            tab      = self.widget(i)
            tab_node = tab.getMPyNode() if hasattr(tab, "getMPyNode") else None
            if tab_node is not None and tab_node.get_name() == name:
                self.removeTab(i)
                tab.deleteLater()
                # Tab list shrank -- notify.
                self.tabsChanged.emit(self.getOpenNodeNames())
                return True
        return False

    def closeAllTabs(self) -> int:
        """Close EVERY open tab (no dirty-save prompt) and emit ``tabsChanged``
        once. Returns the number of tabs closed.

        Used by NDMainWindow on a scene reset (File>New / File>Open): the whole
        scene -- and every node these tabs wrap -- has been replaced, so the tabs
        are stale document views with no live node to save to. Routing through
        this ONE method (rather than a raw ``removeTab`` loop) guarantees the
        ``tabsChanged`` reconcile fires, so per-node attr callbacks for the
        now-dead nodes are torn down too.
        """
        n = self.count()
        while self.count() > 0:
            tab = self.widget(0)
            self.removeTab(0)
            if tab is not None:
                tab.deleteLater()
        if n:
            self.tabsChanged.emit(self.getOpenNodeNames())
        return n

    def pruneStaleTabs(self) -> list:
        """Close every tab whose backing Maya node no longer exists; keep the
        rest. Returns the list of node names whose tabs were pruned.

        Liveness is decided by each tab's own ``isBackingNodeAlive()`` (an
        MObjectHandle test), NOT by name -- so a same-named node in a freshly
        loaded scene never rescues a stale tab (the old ``objExists(name)``
        check did, leaving a ghost tab), and a genuinely surviving tab (reopen
        on the unchanged scene) is kept. Tabs that can't report liveness
        (``None``) are conservatively KEPT. Emits ``tabsChanged`` once iff
        anything was pruned.
        """
        pruned = []
        # Back-to-front so removeTab indices stay valid as we drop tabs.
        for i in reversed(range(self.count())):
            tab = self.widget(i)
            if tab is None:
                continue
            checker = getattr(tab, "isBackingNodeAlive", None)
            alive   = None
            if callable(checker):
                try:
                    alive = checker()
                except Exception:
                    alive = None
            if alive is not False:
                continue  # alive (True) or unknown (None) -> keep
            name = None
            try:
                node = tab.getMPyNode() if hasattr(tab, "getMPyNode") else None
                name = node.get_name() if node is not None else None
            except Exception:
                name = None
            self.removeTab(i)
            tab.deleteLater()
            pruned.append(name)
        if pruned:
            self.tabsChanged.emit(self.getOpenNodeNames())
        return pruned

    def getOpenNodeNames(self) -> list:
        """Return list of node names for every currently open tab.

        used by NDMainWindow to reconcile per-node
        MNodeMessage callbacks. Stale tabs whose underlying node was
        deleted return None and are filtered out.
        """
        names = []
        for i in range(self.count()):
            tab = self.widget(i)
            if not hasattr(tab, "getMPyNode"):
                continue
            py_node = tab.getMPyNode()
            if py_node is None:
                continue
            try:
                names.append(py_node.get_name())
            except Exception:
                pass
        return names

    def renameTabForNode(self, old_name: str, new_name: str) -> bool:
        for i in range(self.count()):
            tab      = self.widget(i)
            tab_node = tab.getMPyNode() if hasattr(tab, "getMPyNode") else None
            # EITHER name: the signal fires AFTER cmds.rename, and a wrapper
            # tracks its MObject, so get_name() already reports ``new_name``.
            # Maya names are unique, so at most one tab can match.
            if tab_node is not None and tab_node.get_name() in (old_name,
                                                                new_name):
                self._setTabTitle(
                    i,
                    new_name,
                    tab.hasUnsavedChanges()
                    if hasattr(tab, "hasUnsavedChanges")
                    else False,
                )
                return True
        return False

    # ------------------------------------------------------------------
    # Save / Save All
    # ------------------------------------------------------------------

    def saveCurrentTab(self) -> bool:
        """Save the currently-active tab. Returns True if saved (or nothing
        to save), False if the tab can't be saved (no current tab)."""
        tab = self.getCurrentTab()
        if tab is None:
            return False
        return self._saveTab(tab)

    def saveAllTabs(self, quiet: bool = False) -> int:
        """Save every dirty tab. Returns the number of tabs saved.

        ``quiet`` suppresses the syntax-error popup (see ``_saveTab``); it is
        for the implicit before-duplicate flush, never for a user's Save All.
        """
        n_saved = 0
        for tab in self.getAllTabs():
            if hasattr(tab, "hasUnsavedChanges") and tab.hasUnsavedChanges():
                if self._saveTab(tab, quiet=quiet):
                    n_saved += 1
        return n_saved

    def saveTabsForNode(self, node_name: str) -> int:
        """Flush every DIRTY open tab belonging to ``node_name`` to its DG plugs
        (Compute via _SetExpressionCommand + Init/Viewport/OSL/Methods via
        markSaved). Returns the number of tabs saved.

        The per-tier code editors only commit to the node's plugs on an explicit
        Save -- nothing flushes on keystroke / focus-out / tab-switch. So an
        operation that reads the node's plugs (Duplicate, Export-to-.mpn) would
        otherwise serialize STALE/empty expressions for a node the user has been
        typing in without saving. Call this first to flush the live editor text.

        Targets ONLY the named node (not saveAllTabs) so duplicating / exporting
        one node never silently commits a DIFFERENT node's unsaved edits. A node
        with no open tab is a no-op -- its plugs are already authoritative."""
        n_saved = 0
        for tab in self.getAllTabs():
            if not hasattr(tab, "getMPyNode"):
                continue
            node = tab.getMPyNode()
            if node is None:
                continue
            try:
                same = node.get_name() == node_name
            except Exception:
                same = False
            if (
                same
                and hasattr(tab, "hasUnsavedChanges")
                and tab.hasUnsavedChanges()
            ):
                if self._saveTab(tab):
                    n_saved += 1
        return n_saved

    def _saveTab(self, tab, quiet: bool = False) -> bool:
        """Save a single tab via _SetExpressionCommand (undoable).

        ``quiet`` skips ONLY the syntax-error popup, for saves the user did not
        ask for (the before-duplicate flush). The text is written either way.

        after save, calls force_one_eval(py_node) so the user
        sees the result of the edit immediately (without scrubbing the
        timeline or moving an upstream input). Best-effort — silent on
        failure.

        Broadcast a save event to the Log tab so the user
        gets visible feedback that the button click / F5 actually did
        something (previously the only signal was the tab title's
        dirty-marker disappearing).
        """
        if not hasattr(tab, "getMPyNode") or not hasattr(tab, "getText"):
            return False
        py_node = tab.getMPyNode()
        if py_node is None:
            return False
        new_text  = tab.getText()
        node_name = ""
        try:
            node_name = py_node.get_name()
        except Exception:
            pass
        try:
            run_undoable(_SetExpressionCommand(py_node, new_text))
            if hasattr(tab, "markSaved"):
                tab.markSaved()
            # setInternalValue silently keeps the previous valid _expr_code on
            # SyntaxError, so without this popup the user has no idea their
            # save did nothing computational.
            try:
                from mpynode._common.compute.expression import compile_expression

                compile_expression(new_text)
            except SyntaxError as exc:
                # ...but NOT on an implicit flush: the user did not press Save,
                # a half-typed expression is the normal state there, and a modal
                # nested inside Maya's before-duplicate callback blocks the
                # duplicate. The text is committed either way; the complaint
                # arrives on their next explicit Save.
                if not quiet:
                    from mpynode.ui.qt_wrapper import QMessageBox

                    line = (exc.text or "").rstrip("\n") if exc.text else ""
                    detail = [
                        f"{exc.msg} (line {exc.lineno or '?'}, "
                        f"col {exc.offset or '?'})",
                    ]
                    if line:
                        detail.append("")
                        detail.append("    " + line)
                        if exc.offset and exc.offset > 0:
                            detail.append("    " + " " * (exc.offset - 1) + "^")
                    detail.append("")
                    detail.append(
                        "The previous valid expression is still active. Fix the "
                        "syntax error and Save again."
                    )
                    QMessageBox.warning(
                        self,
                        "Expression Compile Error",
                        "\n".join(detail),
                    )
            except Exception:
                # Anything else: swallow, to preserve legacy semantics.
                pass
            # Reset profile / watch stats so the next compute writes a FRESH
            # snapshot regardless of the 30-frame throttle. Without this, a
            # Save right after frame 15 shows nothing new until frame 30.
            try:
                import maya.api.OpenMaya as om
                from mpynode._common import instrumentation as _instr

                sel = om.MSelectionList()
                sel.add(py_node.get_name())
                node_obj = sel.getDependNode(0)
                _instr.reset_stats(node_obj)
            except Exception:
                pass
            # Nudge the node so compute() fires once.
            try:
                from mpynode._base.eval_helpers import force_one_eval

                force_one_eval(py_node)
            except Exception:
                pass
            # markSaved() persisted the Viewport + OSL sources, but neither
            # updates the RENDERER: the Viewport tier shades through
            # MPxShadingNodeOverride.updateShader (a dgdirty alone does NOT
            # redraw VP2), and the OSL tier feeds an Arnold aiOslShader that
            # only recompiles when OSLSceneModel re-runs. Without these the
            # look stays stale until a timeline scrub. No-ops for node types
            # without the respective tier.
            try:
                from mpynode._base.eval_helpers import (
                    force_viewport_refresh,
                    force_osl_refresh,
                )

                force_viewport_refresh(py_node)
                force_osl_refresh(py_node)
            except Exception:
                pass
            self.tabSaved.emit(py_node)
            # Visible feedback in the Log tab. LAST, so an earlier partial
            # failure doesn't surface as a successful save.
            try:
                from mpynode._common.util.log_bus import log as _log_bus

                _log_bus(f"Saved expression on {node_name!r}", level="info")
            except Exception:
                pass
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Tab close (with dirty confirm)
    # ------------------------------------------------------------------

    def _on_tab_close_requested(self, idx: int) -> None:
        tab = self.widget(idx)
        if tab is None:
            return

        if hasattr(tab, "hasUnsavedChanges") and tab.hasUnsavedChanges():
            response = self._showSaveConfirmDialog(tab)
            if response == QMessageBox.Cancel:
                return  # don't close
            if response == QMessageBox.Save:
                if not self._saveTab(tab):
                    return  # save failed; abort close

        self.removeTab(idx)
        tab.deleteLater()
        # Tab list shrank -- notify.
        self.tabsChanged.emit(self.getOpenNodeNames())

    def _showSaveConfirmDialog(self, tab) -> int:
        """Show Save / Discard / Cancel dialog for an unsaved tab.

        Returns one of: QMessageBox.Save, QMessageBox.Discard, QMessageBox.Cancel.
        """
        py_node   = tab.getMPyNode()
        node_name = py_node.get_name() if py_node else "(unknown)"
        msg       = QMessageBox(self)
        msg.setWindowTitle("Unsaved Changes")
        msg.setText(f"The expression for '{node_name}' has unsaved changes.")
        msg.setInformativeText("Save before closing the tab?")
        msg.setStandardButtons(
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        )
        msg.setDefaultButton(QMessageBox.Save)
        return msg.exec_() if hasattr(msg, "exec_") else msg.exec()

    def hasAnyDirtyTab(self) -> bool:
        for tab in self.getAllTabs():
            if hasattr(tab, "hasUnsavedChanges") and tab.hasUnsavedChanges():
                return True
        return False

    # ------------------------------------------------------------------
    # Tab title management
    # ------------------------------------------------------------------

    def _addNewTab(self, py_node) -> int:
        # NDScriptTabContent gives each tab the main expression editor AND
        # its sister JIT-source editor.
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        editor = NDScriptTabContent(py_node, parent=self)
        idx    = self.addTab(editor, py_node.get_name())
        # Wire dirty-state change to update the tab title's `*` marker.
        editor.dirtyStateChanged.connect(
            lambda dirty, e=editor: self._update_tab_dirty_marker(e, dirty)
        )
        # Aggregate up; the designer routes it to the assistant panel.
        editor.handoffToAssistant.connect(self.handoffToAssistant)
        # Same route for a variable click in the API view; the designer raises
        # the Variables tab, which is the only place the DATA is shown.
        editor.revealVariableRequested.connect(self.revealVariableRequested)
        # And for an attribute block; the designer raises the Attributes tab,
        # which is where those attrs are actually added and edited.
        editor.revealAttributesRequested.connect(self.revealAttributesRequested)
        # And the tier strip, so the Framework panel can follow it.
        editor.tierChanged.connect(self.tierChanged)
        self.setCurrentIndex(idx)
        return idx

    def _update_tab_dirty_marker(self, editor, dirty: bool) -> None:
        idx = self.indexOf(editor)
        if idx < 0:
            return
        py_node = editor.getMPyNode()
        if py_node is None:
            return
        self._setTabTitle(idx, py_node.get_name(), dirty)

    def _setTabTitle(self, idx: int, name: str, dirty: bool) -> None:
        title = name + (self.DIRTY_MARKER if dirty else "")
        self.setTabText(idx, title)

    def _on_current_changed(self, _idx: int) -> None:
        self.activeNodeChanged.emit(self.getCurrentNode())
