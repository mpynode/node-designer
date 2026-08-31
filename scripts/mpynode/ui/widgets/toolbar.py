"""NDToolBar + ND-specific QToolButton subclass for the New \u25be dropdown.

Mirrors the original `NDToolBar` which has:
  * `New \u25be` QToolButton (instant-popup menu of all registered node types)
  * Save Node (F5)
  * Save All

The toolbar's `contextMenuEvent` is overridden to no-op so right-clicking
the toolbar area doesn't show Maya's "Toolbars >..." menu.
"""

from __future__ import annotations

from typing import Callable

from mpynode._node_registry import REGISTRY, iter_new_node_menu_entries
from mpynode.ui.qt_wrapper import QAction, QPushButton, QToolBar, QWidget
from mpynode.ui.widgets.menus import StayOpenMenu, show_new_node_options


class NDToolBar(QToolBar):
    """Top toolbar for the Node Designer.

    Receives a few callable hooks at construction time so the main
    window doesn't need to reach into the toolbar to wire things up
    after the fact.
    """

    def __init__(
        self,
        parent: QWidget,
        on_new_node: Callable[[str], None],
        on_save_node: Callable[[], None],
        on_save_all: Callable[[], None],
        on_compile: Callable[[], None] | None = None,
        on_new_from_template: Callable[[], None] | None = None,
    ):
        super().__init__("Node Designer Toolbar", parent)
        self.setObjectName("NDToolBar")
        self.setMovable(False)

        self._on_new_node = on_new_node
        self._on_save_node = on_save_node
        self._on_save_all = on_save_all
        # Optional, so call sites that don't pass it get a no-op Compile
        # button rather than a crash.
        self._on_compile = on_compile or (lambda: None)
        self._on_new_from_template = on_new_from_template or (lambda: None)

        self._new_btn: QPushButton | None = None
        self._build_buttons()

    def _build_buttons(self) -> None:
        # Local, to avoid a top-level cycle: icons imports from qt_wrapper,
        # which is already imported here.
        from mpynode.ui.widgets.icons import get_node_type_icon

        # Keeps New off the window border. The main window matches this width
        # to the central layout's left margin, so "New" lines up with the File
        # menu and the left panel's edge.
        self._left_spacer = QWidget(self)
        self._left_spacer.setFixedWidth(6)
        self.addWidget(self._left_spacer)

        # Pops up a menu of every registered node type. The text is plain
        # "New" because Qt draws the dropdown arrow itself once the button
        # has a menu -- spelling one out would double it.
        self._new_btn = QPushButton("New", self)
        self._new_btn.setToolTip("Create a new mPy* node")
        # StayOpenMenu keeps the pulldown open after a pick, so several nodes
        # can be made in a row (click-away / Esc closes it). LEFT-click uses
        # the default new_node_mode pref; RIGHT-click offers the per-type
        # create modes (vanilla / header / template).
        self._new_menu = StayOpenMenu(
            self._new_btn,
            right_click_handler=lambda act, pos: show_new_node_options(
                self._new_menu, act, self._on_new_node, pos
            ),
        )

        def _add_new_node_action(native_type):
            spec = REGISTRY[native_type]
            action = QAction(native_type, self._new_menu)
            action.setIcon(get_node_type_icon(native_type))
            action.setToolTip(spec.description or native_type)
            # Tells the right-click handler which type to offer modes for.
            action.setData(native_type)
            # Capture native_type per action; left-click = default mode.
            action.triggered.connect(
                lambda checked=False, nt=native_type: self._on_new_node(nt)
            )
            self._new_menu.addAction(action)

        # Pinned-first order (mPyNode, separator, the rest) is shared with the
        # Node > New Node submenu via iter_new_node_menu_entries().
        for native_type in iter_new_node_menu_entries():
            if native_type is None:
                self._new_menu.addSeparator()
            else:
                _add_new_node_action(native_type)
        # The gallery entry sits in the same menu below the per-type list, and
        # supersedes the per-type templates.
        self._new_menu.addSeparator()
        self._new_from_template_action = QAction("New from Template…", self)
        self._new_from_template_action.setToolTip(
            "Browse the template gallery and create a node from a template"
        )
        self._new_from_template_action.triggered.connect(
            lambda checked=False: self._on_new_from_template()
        )
        self._new_menu.addAction(self._new_from_template_action)
        self._new_btn.setMenu(self._new_menu)
        self.addWidget(self._new_btn)

        self.addSeparator()

        # Save Node (F5)
        self._save_action = QAction("Save", self)
        self._save_action.setToolTip("Save the active node's expression (F5)")
        self._save_action.triggered.connect(lambda checked=False: self._on_save_node())
        self.addAction(self._save_action)

        # Save All
        self._save_all_action = QAction("Save All", self)
        self._save_all_action.setToolTip("Save every open tab")
        self._save_all_action.triggered.connect(
            lambda checked=False: self._on_save_all()
        )
        self.addAction(self._save_all_action)

        self.addSeparator()

        # Opens the bundle manager: add/remove nodes, then compile them into
        # one native .bundle.
        self._compile_action = QAction("Compile" + "…", self)
        self._compile_action.setToolTip(
            "Compile mPy* nodes into a native plugin")
        self._compile_action.triggered.connect(
            lambda checked=False: self._on_compile()
        )
        self.addAction(self._compile_action)

    def set_left_inset(self, px: int) -> None:
        """Set the width of the leading spacer so the New button aligns
        with the window's content left edge. Best-effort."""
        try:
            self._left_spacer.setFixedWidth(max(0, int(px)))
        except Exception:
            pass

    def contextMenuEvent(self, event):
        # Suppresses Maya's toolbar-area context menu.
        event.accept()
