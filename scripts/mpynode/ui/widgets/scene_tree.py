"""NDSceneTree — lists every mPy* node in the scene + emits selection changes.

Selection in the scene tree is consumed by ``NDMainWindow`` which delegates
to the script tab widget (``addOrRaiseTab``). The tab raise then drives all
panel updates via ``scriptTabChanged``.

each row gets a per-node-type letter-pill icon.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode._node_registry import all_native_types, REGISTRY
from mpynode.ui.qt_wrapper import (
    QAbstractItemView,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QHeaderView,
    QPainter,
    QRect,
    QSize,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    Signal,
)
from mpynode.ui.widgets.icons import _HALO_PAD, get_node_type_icon
from mpynode.ui.widgets.font_prefs import wire_area_font

# Dim color for the node-type column so the name reads as primary.
_TYPE_COLUMN_BRUSH = QBrush(QColor(150, 150, 150))

# Per-item C++ state read by _CppChipDelegate, stored on col 1 so the delegate
# reads it straight off the model index. THREE states, mirroring the menu's
# compile-then-convert flow; marking only the last left compiling invisible.
_CPP_BADGE_ROLE = Qt.UserRole + 17
_CPP_NONE       = 0  # no compiled C++ type available for this node's Class
_CPP_COMPILED   = 1  # compiled type loaded, but this Python node is still driving
_CPP_CONVERTED  = 2  # a hidden compiled C++ sibling is driving downstream
# True when the node does NOT evaluate: nodeState is Has No Effect / Blocking,
# set by Convert to C++ (which suspends the idle Python node) or by hand.
_PAUSED_ROLE    = Qt.UserRole + 18


class _CppChipDelegate(QStyledItemDelegate):
    """Draws a small ``C++`` chip at the RIGHT edge of the Class column.

    Why a right-edge chip and not a suffix on the class text: the class text has
    a variable length, so a suffix lands at a ragged x and cannot be scanned
    down the column. A fixed right margin lets converted rows line up.

    The reserved width is charged to EVERY row, chipped or not. That is a real
    (if unlabelled) column's worth of space, and it is the deliberate price of
    keeping the chip at a fixed x -- otherwise the class text of a chipped row
    would be elided to a different width than its neighbours.

    The chip has TWO weights, because compile and convert are two states:
    FILLED + bold for a converted node (a compiled sibling is live and driving)
    and OUTLINE + regular for a merely compiled one (the type is loaded, Python
    still drives). One mark at two weights, rather than two unrelated badges, so
    the compile -> convert progression reads as a single scale.

    A second, smaller PAUSE chip (two bars) sits left of it whenever the node
    does not evaluate -- ``nodeState`` Has No Effect / Blocking, which Convert
    to C++ sets on the idle Python node and a user may set by hand. A
    converted row therefore shows both: C++ drives, Python is paused. Its
    width is charged only to the rows that carry it (a paused row is rare;
    taking 20 px off every row's class text for it was not worth the fixed x).

    Both chips are laid out against the VIEWPORT's right edge, not the item
    rect's: the stretched last section can run past the visible viewport, and
    the C++ chip drawn at the item's edge came back clipped.
    """

    CHIP_W   = 26                        # px of the C++ chip body
    PAUSE_W  = 14                        # px of the pause chip body
    GUTTER   = 6                         # px between chips, and between the text and the chips
    MARGIN   = 6                         # px kept clear at the viewport's right edge
    RESERVED = CHIP_W + GUTTER + MARGIN  # charged to EVERY row
    CHIP_H   = 14

    @classmethod
    def reserved_for(cls, paused: bool) -> int:
        """Px kept clear of class text on a row: the fixed reserve, plus the
        pause chip and its gutter on a paused row only."""
        return cls.RESERVED + (cls.PAUSE_W + cls.GUTTER if paused else 0)

    @classmethod
    def chip_rects(cls, rect, viewport_width, chipped, paused):
        """Where the chips go: ``{"cpp": QRect | None, "pause": QRect | None}``.

        Right-aligned to the visible viewport (``viewport_width``, 0 = unknown),
        never past the item rect, so a stretched last section cannot push a chip
        off screen. Pure, so a test can pin it without painting."""
        right = rect.right()
        if viewport_width:
            right = min(right, int(viewport_width) - 1)
        right -= cls.MARGIN
        top = rect.top() + max(1, (rect.height() - cls.CHIP_H) // 2)
        out = {"cpp": None, "pause": None}
        if chipped:
            out["cpp"] = QRect(right - cls.CHIP_W + 1, top, cls.CHIP_W, cls.CHIP_H)
            right -= cls.CHIP_W + cls.GUTTER
        if paused:
            out["pause"] = QRect(right - cls.PAUSE_W + 1, top, cls.PAUSE_W, cls.CHIP_H)
        return out

    _BG         = QColor(0x39, 0x48, 0x4D)
    _FG         = QColor(0x93, 0xC3, 0xCD)
    _BORDER     = QColor(0x46, 0x59, 0x5F)
    _BG_SEL     = QColor(0x3C, 0x5C, 0x72)
    _FG_SEL     = QColor(0xE2, 0xF4, 0xFA)
    _BORDER_SEL = QColor(0x5B, 0x7F, 0x97)
    # Outline weight: no fill and a dimmer glyph, so a compiled-but-idle node
    # can't be mistaken for a live one.
    _FG_DIM     = QColor(0x6F, 0x8B, 0x93)
    _FG_DIM_SEL = QColor(0xB9, 0xD6, 0xE0)

    def paint(self, painter, option, index):
        state  = index.data(_CPP_BADGE_ROLE) or _CPP_NONE
        paused = bool(index.data(_PAUSED_ROLE))
        opt    = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # Draw at FULL width and elide by hand: a shortened rect also shortens
        # the SELECTION HIGHLIGHT, leaving a dark notch beside the chip.
        # super().paint() re-runs initStyleOption and would discard an edited
        # opt.text, so draw through the style directly -- same CE_ItemViewItem.
        widget = self.parent() or getattr(option, "widget", None)
        style  = widget.style() if widget is not None else None
        if opt.text and style is not None:
            # Ask the style where the text goes rather than guess its margins,
            # then keep RESERVED px clear. Done on EVERY row, chipped or not,
            # so the column elides to one width.
            tr = style.subElementRect(QStyle.SE_ItemViewItemText, opt, widget)
            opt.text = QFontMetrics(opt.font).elidedText(
                opt.text, Qt.ElideRight,
                max(0, tr.width() - self.reserved_for(paused)))
        if style is None:
            super().paint(painter, opt, index)
        else:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)

        if not state and not paused:
            return
        filled   = state == _CPP_CONVERTED
        selected = bool(option.state & QStyle.State_Selected)
        vp_w     = 0
        try:
            vp_w = widget.viewport().width() if widget is not None else 0
        except Exception:
            vp_w = 0
        rects = self.chip_rects(QRect(option.rect), vp_w, bool(state), paused)
        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            chip = rects["cpp"]
            if chip is not None:
                painter.setPen(self._BORDER_SEL if selected else self._BORDER)
                if filled:
                    painter.setBrush(QBrush(self._BG_SEL if selected else self._BG))
                    fg = self._FG_SEL if selected else self._FG
                else:
                    painter.setBrush(Qt.NoBrush)
                    fg = self._FG_DIM_SEL if selected else self._FG_DIM
                painter.drawRoundedRect(chip, 3, 3)
                f = QFont(option.font)
                f.setBold(filled)
                # Was a hardcoded 9px, which stayed put while the rest of the
                # row scaled. Derived from the row font so the chip keeps its
                # relative size at any panel_font_size; floored so it never
                # vanishes.
                _pt = option.font.pointSize()
                if _pt > 0:
                    f.setPointSize(max(6, int(round(_pt * 0.75))))
                else:
                    f.setPixelSize(max(7, int(round(option.font.pixelSize() * 0.75))))
                painter.setFont(f)
                painter.setPen(fg)
                painter.drawText(chip, Qt.AlignCenter, "C++")
            pause = rects["pause"]
            if pause is not None:
                # Two bars, DRAWN rather than a glyph: no font carries U+23F8
                # reliably at 9 px, and a tofu box would say nothing.
                painter.setPen(self._BORDER_SEL if selected else self._BORDER)
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(pause, 3, 3)
                fg = self._FG_SEL if selected else self._FG
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(fg))
                bar_w = 2
                bar_h = pause.height() - 6
                x0    = pause.left() + (pause.width() - (2 * bar_w + 2)) // 2
                y0    = pause.top() + 3
                painter.drawRect(QRect(x0, y0, bar_w, bar_h))
                painter.drawRect(QRect(x0 + bar_w + 2, y0, bar_w, bar_h))
        finally:
            painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width() + self.RESERVED, s.height())


class _NamePadDelegate(QStyledItemDelegate):
    """Adds a small right gutter to the Name column so the widest node name
    doesn't butt up against the Class column. Only widens the size hint (the
    Name column is ``ResizeToContents``, so the extra width becomes trailing
    empty space); painting + the inline-rename editor inherit the default."""

    PAD = 14  # px of breathing room between the longest name and the Class col

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width() + self.PAD, s.height())


class NDSceneTreeItem(QTreeWidgetItem):
    """One row per mPy* node.

    Two columns: col 0 = the (editable) node name + per-node-type letter
    pill icon; col 1 = the canonical Class, dimmed, in **Option A** notation:
    ``Class(Parent)`` when the node carries a logical Class and ``Parent()``
    when it is class-less, where Parent is the root wrapper class name for the
    node's native type (MPyNode/MPyFile/...) -- mirroring the baked
    ``class X(Parent):`` line. The per-type icon on col 0 still conveys the root
    type. Splitting the Class into its own column lets the tree auto-align every
    entry into a column to the right of the names (and re-space on rename).
    """

    def __init__(self, parent, name: str, native_type: str):
        super().__init__(parent)
        self.node_name    = name
        self.native_type  = native_type
        self.is_converted = False
        self.is_paused    = False
        self.cpp_state    = _CPP_NONE
        # col 0 = name (inline-editable), col 1 = dimmed class tag.
        self.setFlags(self.flags() | Qt.ItemIsEditable)
        self.setForeground(1, _TYPE_COLUMN_BRUSH)
        self._refresh_label()

    def _refresh_compiled_state(self) -> None:
        """Re-read where this node sits on the compile -> convert flow.

        Uses the SAME predicate PAIR as the right-click menu -- ``is_converted``
        (which offers "Revert to Python") and ``is_convertible_to_cpp`` (which
        enables "Convert to C++") -- so the badge and the menu can never
        disagree about what either state means. Marking only ``is_converted``
        left the first half of the flow invisible: compiling a node loads a
        plug-in and changes nothing the tree could show, so a compiled node was
        pixel-identical to one that had never been compiled at all.

        The two predicates are mutually exclusive by construction
        (``is_convertible_to_cpp`` early-returns False once a node is
        converted), hence converted is tested FIRST and wins.

        Both are wrapped because this runs for every row on every scene refresh,
        and a node mid-delete would otherwise take the whole tree down with it.
        """
        from mpynode._base.commands import is_convertible_to_cpp, is_converted

        try:
            self.is_converted = bool(is_converted(self.node_name))
        except Exception:
            self.is_converted = False
        if self.is_converted:
            self.cpp_state = _CPP_CONVERTED
        else:
            try:
                convertible = is_convertible_to_cpp(
                    self.node_name, self.native_type)
            except Exception:
                convertible = False
            self.cpp_state = _CPP_COMPILED if convertible else _CPP_NONE
        # Padded on EVERY row, ringed or not, so the discs keep one size and
        # centre and only the ring appears/vanishes. The ring is exclusive to
        # CONVERTED -- the node whose evaluation actually moved.
        self.setIcon(0, get_node_type_icon(
            self.native_type, pad=_HALO_PAD, ring=self.is_converted))
        # Does the node evaluate at all? Convert to C++ suspends the idle
        # Python node (nodeState Has No Effect / Blocking); a user may too.
        # Read here, with the rest of the row's state, so the pause chip and
        # the tooltip can never disagree with the node.
        state_name = "Normal"
        try:
            st             = int(mc.getAttr(self.node_name + ".nodeState"))
            self.is_paused = st != 0
            state_name = {0: "Normal", 1: "Has No Effect",
                          2: "Blocking"}.get(st, str(st))
        except Exception:
            self.is_paused = False
        if self.cpp_state == _CPP_CONVERTED:
            if self.is_paused:
                python_line = ("this Python node is paused (nodeState %s) and "
                               "kept as the source." % state_name)
            else:
                python_line = ("this Python node still evaluates (nodeState "
                               "Normal) and is kept as the source.")
            tip = (
                "Converted to C++.\n"
                "A hidden compiled C++ sibling is driving downstream "
                "connections; %s\n"
                "Right-click → Revert to Python to drive from Python again."
                % python_line
            )
        elif self.cpp_state == _CPP_COMPILED:
            tip = (
                "Compiled C++ plug-in loaded.\n"
                "A compiled type for this node's Class is available, but this "
                "node is still evaluating in Python.\n"
                "Right-click → Convert to C++ to drive from the compiled node."
            )
        else:
            tip = ""
        if self.is_paused and self.cpp_state != _CPP_CONVERTED:
            paused_line = ("Not evaluating: nodeState is %s (set by hand; "
                           "Normal resumes)." % state_name)
            tip = paused_line + ("\n\n" + tip if tip else "")
        for col in (0, 1):
            self.setToolTip(col, tip)

    def _class_label(self) -> str:
        """Option A: ``Class(Parent)`` when classed, else ``Parent()``.

        Parent = the root wrapper class name for this node's native type
        (MPyNode/MPyFile/...), mirroring the baked ``class X(Parent):`` line."""
        from mpynode._node_registry import get_spec
        from mpynode.wrappers._mpy_node import _read_py_class

        parent = self.native_type
        try:
            spec = get_spec(self.native_type)
            if spec is not None:
                root = spec.get_wrapper_class()
                if isinstance(root, type):
                    parent = root.__name__
        except Exception:
            pass
        pc = _read_py_class(self.node_name)
        if pc:
            short = pc.rpartition(".")[2]
            if short:
                return "%s(%s)" % (short, parent)
        return "%s()" % parent

    def _refresh_label(self) -> None:
        self.setText(0, self.node_name)
        self.setText(1, self._class_label())
        # Stashed for fast lookup on selection.
        self.setData(0, Qt.UserRole, (self.node_name, self.native_type))
        # Icon + tooltip depend on the node NAME, so re-read them here rather
        # than only at construction -- a rename must not strand the badge.
        self._refresh_compiled_state()
        self.setData(1, _CPP_BADGE_ROLE, self.cpp_state)
        self.setData(1, _PAUSED_ROLE, self.is_paused)

    def setNodeName(self, new_name: str) -> None:
        self.node_name = new_name
        self._refresh_label()


class NDSceneTree(QTreeWidget):
    """Lists every mPy* instance in the current scene.

    Emits ``nodeSelected(name: str, native_type: str)`` when the user
    picks a row.

    emits ``exportNodeRequested(name: str, native_type: str)``
    when user picks "Export to.mpn\u2026" from the right-click menu.
    NDMainWindow handles the actual file dialog + serialization.

    emits ``exportNodeScriptRequested(name, native_type)`` /
    ``copyNodeScriptRequested(name, native_type)`` when user picks
    "Bake Node to .py File\u2026" / "Bake Node to Clipboard" -- NDMainWindow bakes the
    rebuild script to a chosen .py file / puts it on the clipboard. One-way:
    Methods bake to real Python, the Methods tab won't repopulate.

    emits ``deleteNodeRequested(name: str, native_type: str)`` when user
    picks "Delete Node" from the right-click menu. NDMainWindow confirms,
    closes any open tab, deletes the scene node, and refreshes the tree.

    emits ``nodeRenamed(old_name: str, new_name: str)`` after an inline
    rename (double-click the name, or right-click ▸ Rename Node) has been
    applied to the scene via ``mc.rename``. NDMainWindow uses it to retitle
    the open editor tab.
    """

    nodeSelected              = Signal(str, str)
    exportNodeRequested       = Signal(str, str)
    exportNodeScriptRequested = Signal(str, str)
    copyNodeScriptRequested   = Signal(str, str)
    deleteNodeRequested       = Signal(str, str)
    nodeRenamed               = Signal(str, str)
    # "Info…" -> NDMainWindow opens the per-node metadata dialog.
    nodeInfoRequested = Signal(str, str)
    # "Duplicate" / "Duplicate + Inputs" -> NDMainWindow deep-copies the node
    # (incl. independent persistent data); "+ Inputs" also re-wires its inputs.
    duplicateNodeRequested       = Signal(str, str)
    duplicateWithInputsRequested = Signal(str, str)
    # "Run setup" -> NDMainWindow runs this node's own ``setup()`` against the
    # current Maya selection, in one undo chunk.
    runSetupRequested = Signal(str, str)
    # "Run demo" -> NDMainWindow runs the node's ``demo()``, which fabricates
    # its OWN showcase scene (no selection), in one undo chunk. Third arg is
    # the chosen demo's func_name.
    runDemoRequested = Signal(str, str, str)
    # "Name Class…" / "Rename Class" -> NDMainWindow prompts for a Class name,
    # synthesizes the in-memory class and stamps ``class_path``. A rename
    # cascades to every scene instance of the old Class.
    nameClassRequested = Signal(str, str)
    # "Reclassify (Fork to New Class)" -> NDMainWindow re-stamps ONLY this
    # instance, forking it away from its former Class.
    reclassifyRequested = Signal(str, str)
    # "Convert to C++" -> NDMainWindow coexist-converts this interpreted node
    # to a hidden compiled C++ sibling, in one undo chunk.
    convertToCppRequested = Signal(str, str)
    # "Revert to Python" -> NDMainWindow deletes the hidden compiled sibling
    # and moves its outputs back onto this Python node, in one undo chunk.
    revertToPyRequested = Signal(str, str)
    # "Compile…" -> NDMainWindow opens the native compile dialog with THIS node
    # preselected, so the user isn't hunting the full scene list.
    compileNodeRequested = Signal(str, str)
    # "Load Compiled Plug-in…" -> NDMainWindow browses for an already-built
    # .bundle and makes it resident. Compiled types are SESSION-scoped (nothing
    # puts ~/mpynode/compiled on MAYA_PLUG_IN_PATH), so without this the only
    # way back to an earlier build is to compile it all over again.
    loadCompiledPluginRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        wire_area_font(self, "panel")
        self.setColumnCount(2)
        # The col-0 icon conveys the root type; col 1 shows _pyClass identity.
        self.setHeaderLabels(["Name", "Class"])
        self.setRootIsDecorated(False)
        # Every scene-tree action operates on one node; batch compiling is
        # driven from the toolbar "Compile…" dialog's checkbox list instead.
        self.setSelectionMode(QTreeWidget.SingleSelection)
        # Name hugs its content so col 1 lines up right of the longest name.
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setStretchLastSection(True)
        # ResizeToContents hugs the content exactly, smashing the widest name
        # against the Class column -- so add a trailing gutter.
        self.setItemDelegateForColumn(0, _NamePadDelegate(self))
        # col 1 also carries the right-edge "C++" chip. The icon size must grow
        # by the halo pad or Qt scales the padded pixmap back down and the ring
        # is lost; the DISC inside is still 16px, so the pill reads as before.
        self.setItemDelegateForColumn(1, _CppChipDelegate(self))
        self.setIconSize(QSize(16 + 2 * _HALO_PAD, 16 + 2 * _HALO_PAD))
        # Click a header to sort; click again to flip asc/desc.
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.AscendingOrder)
        # Rename is explicit (double / right-click) so a single click still
        # just selects + opens the node.
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Guard so programmatic rebuilds don't fire spurious renames.
        self._suppress_item_changed = False
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.itemChanged.connect(self._on_item_changed)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def refresh(self) -> None:
        """Re-query the scene and rebuild the tree."""
        self._suppress_item_changed = True
        try:
            self.clear()
            for nt in all_native_types():
                try:
                    instances = mc.ls(type=nt) or []
                except Exception:
                    instances = []
                for name in instances:
                    NDSceneTreeItem(self, name, nt)
        finally:
            self._suppress_item_changed = False

    def _on_selection_changed(self) -> None:
        items = self.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.UserRole)
        if not data:
            return
        name, nt = data
        self.nodeSelected.emit(name, nt)

    def findItem(self, name: str) -> NDSceneTreeItem | None:
        """Return the item for the given node name, or None."""
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if isinstance(item, NDSceneTreeItem) and item.node_name == name:
                return item
        return None

    def selectNode(self, name: str) -> bool:
        """Select the row for ``name``. Returns True if found."""
        item = self.findItem(name)
        if item is None:
            return False
        self.clearSelection()
        item.setSelected(True)
        self.scrollToItem(item)
        return True

    def refresh_node_class_tag(self, name: str) -> None:
        """Re-render one row's Option A Class label (col 1) after its
        ``class_path`` changed. Cheaper than a full :meth:`refresh` and keeps
        selection. A ``None`` / unknown name is a no-op."""
        item = self.findItem(name)
        if item is None:
            return
        self._suppress_item_changed = True
        try:
            item._refresh_label()
        finally:
            self._suppress_item_changed = False

    # ------------------------------------------------------------------
    # Inline rename (double-click the name, or right-click ▸ Rename Node)
    # ------------------------------------------------------------------

    def _on_item_double_clicked(self, item, column: int) -> None:
        # Only the name column is editable, whichever column was clicked.
        if isinstance(item, NDSceneTreeItem):
            self.editItem(item, 0)

    def _begin_rename(self, item) -> None:
        """Programmatically start inline-editing ``item``'s name (col 0)."""
        if isinstance(item, NDSceneTreeItem):
            self.editItem(item, 0)

    def _on_item_changed(self, item, column: int) -> None:
        if self._suppress_item_changed or column != 0:
            return
        if not isinstance(item, NDSceneTreeItem):
            return
        old_name = item.node_name
        new_name = item.text(0).strip()
        # No-op / empty -> restore the displayed name.
        if not new_name or new_name == old_name:
            self._set_item_name_silently(item, old_name)
            return
        try:
            actual = mc.rename(old_name, new_name)
        except Exception:
            # Rename failed (bad name, clash Maya refused, etc.) -> revert.
            self._set_item_name_silently(item, old_name)
            return
        if not actual:
            self._set_item_name_silently(item, old_name)
            return
        # Maya may sanitize the name (illegal chars, uniquifying).
        item.node_name = actual
        self._set_item_name_silently(item, actual)
        if actual != old_name:
            self.nodeRenamed.emit(old_name, actual)

    def _set_item_name_silently(self, item, name: str) -> None:
        """Set col-0 text + UserRole without re-triggering rename."""
        self._suppress_item_changed = True
        try:
            item.node_name = name
            item.setText(0, name)
            item.setData(0, Qt.UserRole, (name, item.native_type))
        finally:
            self._suppress_item_changed = False

    # ------------------------------------------------------------------
    # right-click context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        """Right-click context menu -- built by :meth:`_build_context_menu`."""
        menu = self._build_context_menu()
        menu.exec_(event.globalPos()) if hasattr(menu, "exec_") else menu.exec(
            event.globalPos()
        )

    def _build_context_menu(self):
        """Build (but do not show) the right-click context menu and return the
        populated ``QMenu``.

        Always shows ``Refresh`` (moved off the awkward toolbar button into the
        right-click menu). When an item is selected, also shows per-item actions
        (Rename, Select in Scene, Info, Export, Duplicate, Delete). Split out
        from :meth:`contextMenuEvent` so the menu contents are unit-testable
        without an event / exec loop."""
        from mpynode.ui.qt_wrapper import QAction, QMenu

        menu = QMenu(self)

        # Refresh is always available, regardless of selection.
        refresh_act = QAction("Refresh", menu)
        refresh_act.triggered.connect(self.refresh)
        menu.addAction(refresh_act)

        items = self.selectedItems()
        first = items[0] if items else None
        if isinstance(first, NDSceneTreeItem):
            menu.addSeparator()
            rename_act = QAction("Rename Node", menu)
            rename_act.triggered.connect(
                lambda checked=False, it=first: self._begin_rename(it)
            )
            menu.addAction(rename_act)
            select_act = QAction("Select Node in Scene", menu)
            select_act.triggered.connect(
                lambda checked=False, n=first.node_name: self._select_in_scene(n)
            )
            menu.addAction(select_act)
            info_act = QAction("Info…", menu)
            info_act.triggered.connect(
                lambda checked=False,
                n = first.node_name,
                t = first.native_type: self.nodeInfoRequested.emit(n, t)
            )
            menu.addAction(info_act)
            export_act = QAction("Export to.mpn\u2026", menu)
            export_act.triggered.connect(
                lambda checked=False,
                n = first.node_name,
                t = first.native_type: self.exportNodeRequested.emit(n, t)
            )
            menu.addAction(export_act)
            export_py_act = QAction("Bake Node to .py File\u2026", menu)
            export_py_act.triggered.connect(
                lambda checked=False,
                n = first.node_name,
                t = first.native_type: self.exportNodeScriptRequested.emit(n, t)
            )
            menu.addAction(export_py_act)
            copy_py_act = QAction("Bake Node to Clipboard", menu)
            copy_py_act.triggered.connect(
                lambda checked=False,
                n = first.node_name,
                t = first.native_type: self.copyNodeScriptRequested.emit(n, t)
            )
            menu.addAction(copy_py_act)

            # Class-less -> "Name Class…". Classed -> "Rename Class" (cascades
            # to every instance) plus "Reclassify" (this instance only).
            # Clearing: confirm the Rename Class prompt BLANK, or blank the
            # Identity field -- this instance only, like Reclassify.
            from mpynode.wrappers._mpy_node import _read_py_class

            menu.addSeparator()
            _classed = bool(_read_py_class(first.node_name))
            name_act = QAction(
                "Rename Class" if _classed else "Name Class…", menu)
            name_act.setToolTip(
                "Rename this Class (re-stamps every scene instance of it); "
                "confirm blank to clear this node's Class"
                if _classed else
                "Name this node's Class (its Class identity + baked class name)"
            )
            name_act.triggered.connect(
                lambda checked=False,
                n = first.node_name,
                t = first.native_type: self.nameClassRequested.emit(n, t)
            )
            menu.addAction(name_act)
            if _classed:
                fork_act = QAction("Reclassify (Fork to New Class)", menu)
                fork_act.setToolTip(
                    "Give THIS instance its own new Class, forking it away from "
                    "the others that share its current Class"
                )
                fork_act.triggered.connect(
                    lambda checked=False,
                    n = first.node_name,
                    t = first.native_type: self.reclassifyRequested.emit(n, t)
                )
                menu.addAction(fork_act)

            # Deep copy incl. independent persistent data; "+ Inputs" also
            # re-wires the source's input connections.
            menu.addSeparator()
            dup_act = QAction("Duplicate", menu)
            dup_act.triggered.connect(
                lambda checked=False,
                n = first.node_name,
                t = first.native_type: self.duplicateNodeRequested.emit(n, t)
            )
            menu.addAction(dup_act)
            dup_inputs_act = QAction("Duplicate + Inputs", menu)
            dup_inputs_act.setToolTip(
                "Duplicate this node AND re-create its input connections"
            )
            dup_inputs_act.triggered.connect(
                lambda checked=False,
                n = first.node_name,
                t = first.native_type: self.duplicateWithInputsRequested.emit(n, t)
            )
            menu.addAction(dup_inputs_act)

            # Compile / Convert / Revert are ALWAYS shown, with a
            # MUTUALLY-EXCLUSIVE enable so the menu guides the flow (#69).
            # Compile is first because that is the order it runs in, and the
            # names are kept apart on purpose: "Compile to C++" builds the
            # .bundle / C++ TYPE, "Convert Node to C++" swaps THIS instance
            # onto it. Converted -> enabled Revert; convertible (classed +
            # coexist-eligible + compiled type loaded) -> enabled Convert;
            # otherwise Convert is disabled, there being nothing to convert to.
            from mpynode._base.commands import (
                is_convertible_to_cpp, is_converted)

            converted = is_converted(first.node_name)
            convertible = is_convertible_to_cpp(
                first.node_name, first.native_type)

            menu.addSeparator()

            # Disabled once the node is convertible or converted -- its Class's
            # compiled type already exists. Recompiling such a node stays
            # available from the Compile dialog itself.
            compile_act = QAction("Compile to C++…", menu)
            if converted or convertible:
                compile_act.setEnabled(False)
                compile_act.setToolTip(
                    "This node's Class already has a compiled C++ type -- use "
                    "Convert Node to C++ / Revert Node to Python, or recompile "
                    "from the Compile dialog")
            else:
                compile_act.setToolTip(
                    "Build the compiled C++ node TYPE: open the native compile "
                    "dialog with this node preselected"
                )
                compile_act.triggered.connect(
                    lambda checked=False,
                    n = first.node_name,
                    t = first.native_type: self.compileNodeRequested.emit(n, t)
                )
            menu.addAction(compile_act)

            # ALWAYS enabled. A compiled type is SESSION-scoped, so an earlier
            # build (or a declined post-compile load prompt) leaves Convert
            # greyed out with no way back except recompiling. This is that way.
            load_act = QAction("Load Compiled Plug-in…", menu)
            load_act.setToolTip(
                "Load an already-built .bundle into this session so its "
                "compiled node type is registered and Convert Node to C++ "
                "becomes available")
            load_act.triggered.connect(
                lambda checked=False: self.loadCompiledPluginRequested.emit()
            )
            menu.addAction(load_act)

            if converted:
                revert_act = QAction("Revert Node to Python", menu)
                revert_act.setToolTip(
                    "Delete the compiled C++ sibling and drive downstream "
                    "from this Python node again")
                revert_act.triggered.connect(
                    lambda checked=False,
                    n = first.node_name,
                    t = first.native_type:
                    self.revertToPyRequested.emit(n, t)
                )
                menu.addAction(revert_act)
            else:
                convert_act = QAction("Convert Node to C++", menu)
                if convertible:
                    convert_act.setToolTip(
                        "Swap THIS node onto the compiled C++ type: create a "
                        "hidden compiled sibling that drives downstream (this "
                        "Python node stays as the source)")
                    convert_act.triggered.connect(
                        lambda checked=False,
                        n = first.node_name,
                        t = first.native_type:
                        self.convertToCppRequested.emit(n, t)
                    )
                else:
                    convert_act.setEnabled(False)
                    convert_act.setToolTip(
                        "This node's Class has no compiled C++ type loaded in "
                        "THIS session (or the type is not coexist-eligible) -- "
                        "run Compile to C++, or use Load Compiled Plug-in... "
                        "if it was already built")
                menu.addAction(convert_act)

            # Shown when the TYPE defines a ``setup()`` hook OR the node's OWN
            # Methods source carries an instance ``def setup(self)``.
            from mpynode._common.methods.methods_registry import node_has_runnable_setup

            if node_has_runnable_setup(first.node_name, first.native_type):
                menu.addSeparator()
                run_setup_act = QAction("Run setup", menu)
                run_setup_act.setToolTip(
                    "Run this node's setup() on the current selection"
                )
                run_setup_act.triggered.connect(
                    lambda checked=False,
                    n = first.node_name,
                    t = first.native_type: self.runSetupRequested.emit(n, t)
                )
                menu.addAction(run_setup_act)

            # Shown when the Methods source carries at least one demo
            # (@maya_demo or a reserved def demo). One demo -> a flat action;
            # more -> a submenu. Demo has NO type default.
            from mpynode._common.methods.methods_registry import methods_source_of
            from mpynode._common import node_setups

            demos = node_setups.find_demos(
                methods_source_of(first.node_name))
            if len(demos) == 1:
                menu.addSeparator()
                run_demo_act = QAction("Run demo", menu)
                run_demo_act.setToolTip(
                    "Run this node's demo() (builds a self-contained showcase "
                    "scene)"
                )
                run_demo_act.triggered.connect(
                    lambda checked=False,
                    n  = first.node_name,
                    t  = first.native_type,
                    dn = demos[0].func_name:
                    self.runDemoRequested.emit(n, t, dn)
                )
                menu.addAction(run_demo_act)
            elif demos:
                menu.addSeparator()
                demo_menu = menu.addMenu("Run demo")
                for spec in demos:
                    a = QAction(spec.label, demo_menu)
                    a.triggered.connect(
                        lambda checked=False,
                        n  = first.node_name,
                        t  = first.native_type,
                        dn = spec.func_name:
                        self.runDemoRequested.emit(n, t, dn)
                    )
                    demo_menu.addAction(a)

            # Destructive action set off by its own separator.
            menu.addSeparator()
            delete_act = QAction("Delete Node", menu)
            delete_act.triggered.connect(
                lambda checked=False,
                n = first.node_name,
                t = first.native_type: self.deleteNodeRequested.emit(n, t)
            )
            menu.addAction(delete_act)

        return menu

    def middleClickNodeName(self, global_pos):
        """mPyNode name for the row under ``global_pos`` (screen coords), or None.

        Participates in the Designer's global middle-click shortcut
        (:meth:`NDMainWindow.eventFilter`): a middle-click anywhere resolves the
        node under the cursor, and over this tree that is the clicked row's node.
        Replaces the old per-tree middle-click override, so the "grab it in the
        viewport" shortcut now works everywhere in the Designer, not just here.
        """
        try:
            item = self.itemAt(self.viewport().mapFromGlobal(global_pos))
            if isinstance(item, NDSceneTreeItem):
                return item.node_name
        except Exception:
            pass
        return None

    def _select_in_scene(self, name: str) -> None:
        try:
            mc.select(name, replace=True)
        except Exception:
            pass
