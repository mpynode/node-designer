"""'New from Template' gallery panel.

An always-available ``QWidget`` — a permanent tab in the Node Designer's
shared right-hand side panel (see ui/mpynode_designer.py). Lifted out of the
former non-modal ``TemplateGalleryDialog`` so the gallery lives inside a tab
rather than a pop-up.

A QTreeWidget (left) of templates discovered by
``_common.template_gallery.scan_all`` — one top item per search root, category
folders nested, template leaves tagged with their native_type — and a preview
pane (right) showing the template's preview (QVideoWidget for .mp4, QMovie for
.gif, QPixmap for .png/.jpg), its description.md (rendered via
QTextBrowser.setMarkdown), and a metadata line. Create / Create + Run demo
emit (payload, native_type, run_setup, run_demo, demo_name) to an
``on_create`` callback after loading the FULL payload via ``mpn_io.load_mpn``
(the only decoding load in the flow). Unlike the old dialog, the panel stays
open after Create (it is a permanent tab, not a pop-up) and has no Cancel
button.

Pickle safety: the tree + metadata line read raw JSON only, via
``mpn_io.load_mpn_header`` (no stored-vars decode). The decoding ``load_mpn``
runs ONLY on the single template the user clicks Create on.
"""

from __future__ import annotations

import os

from mpynode.ui.editor_launch import reveal_in_file_manager, reveal_label
from mpynode.ui.qt_wrapper import (
    HAS_QT_MULTIMEDIA,
    QColor,
    QDesktopServices,
    QLabel,
    QLineEdit,
    QMenu,
    QMovie,
    QPainter,
    QPalette,
    QPixmap,
    QPushButton,
    QSize,
    QSplitter,
    QSplitterHandle,
    QStackedWidget,
    Qt,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QVideoWidget,
    QWidget,
    start_video_preview,
)
from mpynode.ui.widgets.logo_relief import paint_relief, relief_layers

def _coerce_int_list(value, n):
    """Return ``value`` as a list of exactly ``n`` ints, or None if it is not a
    valid persisted layout value (wrong type / length / non-int element).
    Mirrors the helper of the same name in ui/mpynode_designer.py; duplicated
    here rather than imported to avoid a circular import (the designer imports
    this module)."""
    if not isinstance(value, (list, tuple)) or len(value) != n:
        return None
    try:
        return [int(x) for x in value]
    except (TypeError, ValueError):
        return None


# Role used to stash the TemplateEntry on its leaf item.
_ENTRY_ROLE = Qt.UserRole + 1

# Breathing room per tree row. Rows carried NO size hint, so Qt packed them to
# the exact glyph height (15px at the shipped font) and the list read as
# cramped. Same idiom as the outline pane's script_navigator._row_height().
_ROW_PAD = 6

# Splitter separator: inset from the ends, so the divider reads as a divider.
_SEPARATOR_COLOR = (90, 90, 90)
_SEPARATOR_INSET = 24


class _PreviewLabel(QLabel):
    """Preview that re-fits its image/gif on every resize (so it tracks the
    splitter divider). A row that ships no preview file gets the empty
    script editor's relief instead -- the embossed mPyNode logo, painted by
    the very same ``logo_relief.paint_relief`` -- with the row's ``label``
    (a node class such as ``MPyLocator``) set quietly beneath it, or the
    bare logo when no label is given."""

    def __init__(self, parent=None):
        super(_PreviewLabel, self).__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(160)
        self._mode   = None  # None | "image" | "movie" | "none"
        self._source = None  # original QPixmap (image mode)
        self._movie  = None  # QMovie (movie mode) + GC ref
        self._label  = None  # caption under the logo (none mode)

    def clear_preview(self):
        self._stop_movie()
        self._mode   = None
        self._source = None
        self._label  = None
        self.clear()

    def show_image(self, pixmap):
        self._stop_movie()
        self._mode, self._source = "image", pixmap
        self._render()

    def show_movie(self, movie):
        self._stop_movie()
        self._mode, self._movie = "movie", movie
        self.setMovie(movie)
        movie.start()
        self._render()

    def show_no_preview(self, label=None):
        """Draw the logo relief, captioned beneath with ``label`` when given."""
        self._stop_movie()
        self._mode, self._source = "none", None
        self._label = (str(label).strip() or None) if label else None
        self._render()

    def resizeEvent(self, event):
        super(_PreviewLabel, self).resizeEvent(event)
        self._render()

    def minimumSizeHint(self):
        # QLabel reports its PIXMAP size here, and _render() scales that pixmap
        # to fill the label -- so the minimum would equal the pane's CURRENT
        # width, turning the splitter divider into a one-way ratchet: it can
        # grow the preview (raising the floor again) but never shrink it. A
        # small content-independent floor keeps the drag two-way. The height
        # floor still comes from setMinimumHeight() in __init__.
        return QSize(1, self.minimumHeight())

    def _stop_movie(self):
        if self._movie is not None:
            self._movie.stop()
            self._movie = None

    def _render(self):
        if self._mode == "image" and self._source and not self._source.isNull():
            self.setPixmap(self._source.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        elif self._mode == "movie" and self._movie is not None:
            native = self._movie_native_size()
            if native is not None and native.width() > 0 and native.height() > 0:
                self._movie.setScaledSize(
                    native.scaled(self.size(), Qt.KeepAspectRatio))
        elif self._mode == "none":
            self.setPixmap(self._no_preview_pixmap(self.size()))

    def _movie_native_size(self):
        try:
            self._movie.jumpToFrame(0)
            return self._movie.currentPixmap().size()
        except Exception:
            return None

    def _watermark_layers(self, side):
        # (light, dark) silhouettes of the logo at ``side`` px, from the
        # cache logo_relief shares with the script editor.
        return relief_layers(side)

    def _no_preview_pixmap(self, size):
        if size.width() <= 0 or size.height() <= 0:
            return QPixmap()
        canvas = QPixmap(size)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        try:
            # The editor's empty-state relief on a transparent canvas, so
            # the panel shows through exactly as it does behind the script
            # area; the caption sits beneath the logo, never across it.
            paint_relief(
                painter, canvas.rect(), caption=self._label,
                caption_color=self.palette().color(QPalette.WindowText))
        finally:
            painter.end()
        return canvas


class _SeparatorHandle(QSplitterHandle):
    """Splitter handle that paints a subtle centered line, inset from the
    ends, so the divider is easy to see with space around it."""

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setPen(QColor(*_SEPARATOR_COLOR))
            rect = self.rect()
            if self.orientation() == Qt.Vertical:
                # Horizontal bar (vertical splitter) -> horizontal line.
                y = rect.center().y()
                painter.drawLine(rect.left() + _SEPARATOR_INSET, y,
                                 rect.right() - _SEPARATOR_INSET, y)
            else:
                # Vertical bar (horizontal splitter) -> vertical line.
                x = rect.center().x()
                painter.drawLine(x, rect.top() + _SEPARATOR_INSET,
                                 x, rect.bottom() - _SEPARATOR_INSET)
        finally:
            painter.end()


class _SeparatorSplitter(QSplitter):
    """QSplitter whose handles paint a visible centered separator line."""

    def createHandle(self):
        return _SeparatorHandle(self.orientation(), self)


class NDTemplateGalleryPanel(QWidget):
    """Always-available template picker (tree + preview) for the shared side
    panel. Embeds as a tab; stays open after Create."""

    def __init__(self, parent=None, on_create=None, scan=None):
        super(NDTemplateGalleryPanel, self).__init__(parent)
        self._on_create = on_create
        # Injectable for tests; defaults to the real discovery.
        if scan is None:
            from mpynode._common.util import template_gallery
            scan = template_gallery.scan_all
        self._scan       = scan
        self._player     = None  # keep a ref so the QMediaPlayer isn't GC'd
        self._demo_first = None  # func_name of the primary demo (button click)
        # Gates layout persistence. A gallery parented into a non-current tab
        # is never laid out, so its splitters report Qt placeholder even-split
        # sizes -- real-looking, but not the user's layout. Saving those would
        # clobber a good value, so save_layout() no-ops until shown.
        self._ever_shown = False
        self._build_ui()
        self.reload()

    # -- UI construction ------------------------------------------------
    def _build_ui(self):
        outer    = QVBoxLayout(self)
        splitter = _SeparatorSplitter(Qt.Horizontal, self)
        splitter.setHandleWidth(10)
        outer.addWidget(splitter, 1)
        self._h_splitter = splitter  # [tree | preview]; persisted across sessions

        # Stacked under the tree, so their width tracks the templates column.
        left             = QWidget(splitter)
        lv               = QVBoxLayout(left)
        self.filter_edit = QLineEdit(left)
        self.filter_edit.setPlaceholderText("Filter…")
        self.filter_edit.textChanged.connect(self._apply_filter)
        lv.addWidget(self.filter_edit)
        self.tree = QTreeWidget(left)
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(self._on_selection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        # Shift-click a category header to expand / collapse THAT subtree only.
        # Categories start collapsed, so this is the quick "open this branch".
        from mpynode.ui.widgets.tree_expand import (
            install_shift_click_expand_all,
        )
        install_shift_click_expand_all(self.tree)
        lv.addWidget(self.tree, 1)
        self.refresh_btn = QPushButton("Refresh", left)
        self.refresh_btn.clicked.connect(lambda checked=False: self.reload())
        lv.addWidget(self.refresh_btn)
        # Same actions as the tree's right-click menu; buildable rows only.
        self.create_btn = QPushButton("Create", left)
        self.create_btn.clicked.connect(lambda checked=False: self._do_create(False))
        lv.addWidget(self.create_btn)
        # "Create + Run setup" was REMOVED here on purpose: running a setup
        # now lives solely on the scene tab's right-click menu.
        #
        # A plain QPushButton, since qt_wrapper doesn't expose QToolButton. One
        # demo runs on click; 2+ attach a QMenu so each is reachable, with the
        # primary click passing the FIRST demo's func_name.
        self.create_demo_btn = QPushButton("Create + Run demo", left)
        self.create_demo_btn.setToolTip(
            "Create this node, then run its self-contained demo (builds a "
            "showcase scene). Enabled only when the template defines a demo.")
        self.create_demo_btn.clicked.connect(
            lambda checked=False: self._on_demo_btn_clicked()
        )
        self.create_demo_btn.setEnabled(False)
        lv.addWidget(self.create_demo_btn)
        self._refresh_button_state()
        splitter.addWidget(left)

        # Preview over metadata + description, with a draggable divider.
        right_split = _SeparatorSplitter(Qt.Vertical, self)
        right_split.setHandleWidth(16)
        self._right_split = right_split  # [preview | description]; persisted

        # The scaling label (image/gif/no-preview) plus, when QtMultimedia is
        # present, a QVideoWidget for .mp4.
        self.preview_stack = QStackedWidget(right_split)
        self.preview_label = _PreviewLabel(self.preview_stack)
        self.preview_stack.addWidget(self.preview_label)
        self.video_widget = None
        if HAS_QT_MULTIMEDIA and QVideoWidget is not None:
            self.video_widget = QVideoWidget(self.preview_stack)
            self.video_widget.setAspectRatioMode(Qt.KeepAspectRatio)
            self.preview_stack.addWidget(self.video_widget)
        right_split.addWidget(self.preview_stack)

        bottom          = QWidget(right_split)
        bv              = QVBoxLayout(bottom)
        self.meta_label = QLabel(bottom)
        self.meta_label.setWordWrap(True)
        bv.addWidget(self.meta_label)
        self.desc_browser = QTextBrowser(bottom)
        # Route links out to the system browser instead of letting Qt navigate.
        # A QTextBrowser defaults to openLinks=True, so clicking the DOI in
        # Patch Relax's description made Qt setSource() the URL and BLANK the
        # pane -- there is no Back button here to get the description back.
        # Same contract as the docs viewer (see doc_viewer.MarkdownBrowser).
        self.desc_browser.setOpenLinks(False)
        self.desc_browser.setOpenExternalLinks(False)
        self.desc_browser.anchorClicked.connect(self._on_desc_anchor)
        bv.addWidget(self.desc_browser, 1)
        right_split.addWidget(bottom)

        right_split.setStretchFactor(0, 1)
        right_split.setStretchFactor(1, 1)
        right_split.setSizes([360, 240])

        splitter.addWidget(right_split)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Absent / malformed saved values leave the defaults above in place.
        self._restore_splitter_sizes()

    # -- layout persistence ---------------------------------------------
    _PREF_H = "layout_gallery_splitter"        # [tree, preview]
    _PREF_V = "layout_gallery_right_splitter"  # [preview, description]

    def _restore_splitter_sizes(self):
        """Apply the saved gallery splitter positions, if any. Called from
        _build_ui BEFORE the panel is shown — setSizes on an unshown splitter
        seeds the initial proportions, which Qt realizes on first show."""
        try:
            from mpynode.ui.preferences import get_pref
        except Exception:
            return
        h = _coerce_int_list(get_pref(self._PREF_H), 2)
        if h is not None and sum(h) > 0:
            try:
                self._h_splitter.setSizes(h)
            except Exception:
                pass
        v = _coerce_int_list(get_pref(self._PREF_V), 2)
        if v is not None and sum(v) > 0:
            try:
                self._right_split.setSizes(v)
            except Exception:
                pass

    def save_layout(self):
        """Persist the two gallery splitter positions. Best-effort; invoked
        from the Designer's closeEvent alongside the main window's own layout
        save (splitter sizes are saved at close, not per-drag, to avoid
        thrashing the prefs file).

        No-op until the panel has actually been shown: a gallery parented into
        the non-current Templates tab (Workspace mode is the default) is never
        laid out, and its splitters then report Qt's placeholder even-split
        sizes (e.g. [45, 45]) — non-zero but meaningless. Writing those would
        clobber a good saved layout just by opening+closing the Designer, so we
        gate on _ever_shown rather than on the sizes() sum (which cannot tell a
        real layout from the placeholder)."""
        if not self._ever_shown:
            return
        try:
            from mpynode.ui.preferences import set_pref
        except Exception:
            return
        try:
            h = [int(x) for x in self._h_splitter.sizes()]
            if sum(h) > 0:
                set_pref(self._PREF_H, h)
        except Exception:
            pass
        try:
            v = [int(x) for x in self._right_split.sizes()]
            if sum(v) > 0:
                set_pref(self._PREF_V, v)
        except Exception:
            pass

    # -- population (E4) ------------------------------------------------
    def reload(self):
        self.tree.clear()
        for root_label, root_path, root_cat in self._scan():
            root_item = self._add_node(None, root_cat)
            root_item.setToolTip(0, root_path)
            # Only the search root expands, so its top-level categories are
            # visible while each category itself starts COLLAPSED.
            root_item.setExpanded(True)

    def _add_node(self, parent_item, node):
        # A node is a category, a buildable entry, or both. Buildable ones get
        # a native_type suffix; an entry with an unreadable type is disabled.
        native_type = getattr(node, "native_type", None)
        is_entry    = hasattr(node, "mpn_path")
        if native_type:
            label = "%s  [%s]" % (node.label, native_type)
        elif is_entry:
            label = "%s  [?]" % node.label
        else:
            label = node.label
        item = QTreeWidgetItem([label])
        item.setSizeHint(
            0, QSize(0, self.tree.fontMetrics().height() + _ROW_PAD))
        item.setData(0, _ENTRY_ROLE, node)
        if is_entry and native_type is None:
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            item.setToolTip(
                0,
                "Unreadable template or unknown node type — cannot create.",
            )
        if parent_item is None:
            self.tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
        children = getattr(node, "children", ())
        for child in children:
            self._add_node(item, child)
        # Categories start COLLAPSED; reload() expands the root.
        return item

    # -- selection / preview (E5) --------------------------------------
    def _on_selection(self, current=None, previous=None):
        self._update_preview(self._selected_entry())
        self._refresh_button_state()

    def _refresh_button_state(self):
        """Enable/disable the Create buttons for the current selection. Create
        is available for any buildable node (a real ``native_type``); Create +
        Run demo only when the template carries its own ``def demo(self)``."""
        entry       = self._selected_entry()
        native_type = getattr(entry, "native_type", None)
        buildable   = bool(native_type)
        self.create_btn.setEnabled(buildable)
        # Demo has NO type default -- gated purely on the template's own demos.
        demos = self._template_demos(entry) if buildable else []
        # Cached for the primary-click path.
        self._demo_first = demos[0].func_name if demos else None
        self.create_demo_btn.setEnabled(bool(demos))
        self.create_demo_btn.setToolTip(
            "" if demos else "This template has no demo to run.")
        menu = self.create_demo_btn.menu()
        if menu is not None:
            menu.clear()
        if len(demos) > 1:
            menu = menu or QMenu(self.create_demo_btn)
            for spec in demos:
                a = menu.addAction(spec.label)
                a.triggered.connect(
                    lambda checked=False, dn=spec.func_name:
                    self._do_create(run_demo=True, demo_name=dn))
            self.create_demo_btn.setMenu(menu)
        else:
            self.create_demo_btn.setMenu(None)

    def _on_demo_btn_clicked(self):
        """Primary demo-button click. Runs the FIRST demo (single-demo case, or
        the primary of a >1 dropdown when Qt still routes a click through). With
        a menu attached (2+ demos), Qt shows the dropdown and the per-action
        handlers pass each demo's func_name instead."""
        self._do_create(run_demo=True, demo_name=self._demo_first)

    def _build_tree_menu(self, entry):
        # Create actions are buildable-only, but the reveal action is offered
        # for EVERY row backed by a folder -- so a pure category still gets
        # a menu.
        if entry is None:
            return None
        menu        = QMenu(self.tree)
        native_type = getattr(entry, "native_type", None)
        if not native_type:
            self._add_reveal_action(menu, entry)
            return menu
        create = menu.addAction("Create")
        create.triggered.connect(lambda checked=False: self._do_create(False))
        # "Create + Run setup" was REMOVED here on purpose; it lives solely on
        # the scene tab's right-click menu. Demo has NO type default: one demo
        # -> a plain action, several -> a submenu.
        demos = self._template_demos(entry)
        if len(demos) == 1:
            demo_act = menu.addAction("Create + Run demo")
            demo_act.triggered.connect(
                lambda checked=False, dn=demos[0].func_name:
                self._do_create(run_demo=True, demo_name=dn))
        elif demos:
            demo_menu = menu.addMenu("Create + Run demo")
            for spec in demos:
                a = demo_menu.addAction(spec.label)
                a.triggered.connect(
                    lambda checked=False, dn=spec.func_name:
                    self._do_create(run_demo=True, demo_name=dn))
        else:
            demo_act = menu.addAction("Create + Run demo")
            demo_act.setEnabled(False)
            demo_act.setToolTip("This template has no demo to run.")
        menu.addSeparator()
        self._add_reveal_action(menu, entry)
        return menu

    @staticmethod
    def _reveal_path(entry):
        """The on-disk folder a tree row maps to: a template's own folder
        (``TemplateEntry.folder``), a category's (``TemplateCategory.abs_path``),
        or the ``.mpn`` itself if the folder is gone. ``None`` when nothing on
        disk backs the row -- the gallery is scanned once, so an entry can
        outlive the files it was built from."""
        for attr in ("folder", "abs_path", "mpn_path"):
            path = getattr(entry, attr, None)
            if path and os.path.exists(path):
                return path
        return None

    def _add_reveal_action(self, menu, entry):
        """Append the platform-named reveal action. Disabled-with-tooltip when
        the row has no readable path, matching how this menu already handles a
        template with no demo."""
        path = self._reveal_path(entry)
        act  = menu.addAction(reveal_label())
        if path:
            act.triggered.connect(
                lambda checked=False, p=path: reveal_in_file_manager(p))
        else:
            act.setEnabled(False)
            act.setToolTip("This item has no folder on disk.")
        return act

    @staticmethod
    def _template_has_demo(entry):
        """True when the template's own methods_source carries a self-first
        ``def demo``. Demo has NO type default, so this is the ONLY gate. Reads
        the RAW JSON header (no pickle decode) + statically detects the hook
        (never exec'd)."""
        try:
            from mpynode._common.io import mpn_io
            from mpynode._common import node_setups
            data = mpn_io.load_mpn_header(getattr(entry, "mpn_path", None))
            src  = (data or {}).get("methods_source") or ""
            return node_setups.find_demo(src) is not None
        except Exception:
            return False

    @staticmethod
    def _template_demos(entry):
        """All demos declared in a template's own methods_source (source order):
        a list of ``node_setups.DemoSpec``. Reads the RAW JSON header (no pickle
        decode) + static detection (never exec'd). Empty on any failure."""
        try:
            from mpynode._common.io import mpn_io
            from mpynode._common import node_setups
            data = mpn_io.load_mpn_header(getattr(entry, "mpn_path", None))
            src  = (data or {}).get("methods_source") or ""
            return node_setups.find_demos(src)
        except Exception:
            return []

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        self.tree.setCurrentItem(item)
        menu = self._build_tree_menu(self._selected_entry())
        if menu is None:
            return
        gpos = self.tree.viewport().mapToGlobal(pos)
        menu.exec_(gpos) if hasattr(menu, "exec_") else menu.exec(gpos)

    def _update_preview(self, entry):
        # Stop any video, return to the label page, clear the text.
        self.stop_video()
        self.preview_stack.setCurrentWidget(self.preview_label)
        self.preview_label.clear_preview()
        self.meta_label.clear()
        self.desc_browser.clear()
        if entry is None:
            return

        native_type = getattr(entry, "native_type",      None)
        pp          = getattr(entry, "preview_path",     None)
        dp          = getattr(entry, "description_path", None)
        # A pure container with no landing-page assets stays blank.
        if native_type is None and not pp and not dp:
            return

        # .mp4 -> QVideoWidget, .gif -> QMovie, else QPixmap. The label
        # auto-fits image/gif on resize; the video widget fits itself.
        shown = False
        if pp:
            low = pp.lower()
            if low.endswith(".mp4"):
                if self.video_widget is not None:
                    player = start_video_preview(pp, self.video_widget)
                    if player is not None:
                        self._player = player
                        self.preview_stack.setCurrentWidget(self.video_widget)
                        shown = True
            elif low.endswith(".gif"):
                self.preview_label.show_movie(QMovie(pp))
                shown = True
            else:
                pix = QPixmap(pp)
                if not pix.isNull():
                    self.preview_label.show_image(pix)
                    shown = True
        # No preview file: the logo relief stands in, captioned with the node
        # class -- a category's own name, or the category a template sits in.
        # A pure container with no landing page at all stayed blank above.
        if not shown and (native_type is not None or dp):
            self.preview_label.show_no_preview(self._placeholder_word(entry))

        # Description.
        if dp:
            try:
                with open(dp, encoding="utf-8") as fh:
                    self.desc_browser.setMarkdown(fh.read())
            except OSError:
                pass
            else:
                self._style_description()

        # Buildable nodes only; raw JSON, never decodes pickle.
        if native_type is not None:
            meta = None
            try:
                from mpynode._common.io import mpn_io
                meta = (mpn_io.load_mpn_header(entry.mpn_path)
                        or {}).get("metadata")
            except Exception:
                meta = None
            bits = [native_type]
            if isinstance(meta, dict):
                if meta.get("authors"):
                    bits.append("by %s" % meta["authors"])
                if meta.get("version"):
                    bits.append("v%s" % meta["version"])
            self.meta_label.setText("  •  ".join(str(b) for b in bits))

    def _placeholder_word(self, entry):
        """The caption drawn over the logo when ``entry`` has no preview image.

        A category is captioned with its own name (the folder is the node
        class: ``MPyLocator``). A template is captioned with the category it
        sits in, so every template of a class shares one word; a template
        directly under a search root has no such category and falls back to
        its native type. ``None`` when nothing sensible is known, which leaves
        the relief bare, exactly as the empty script editor shows it."""
        native_type = getattr(entry, "native_type", None)
        label       = getattr(entry, "label", None)
        if native_type is None:
            return label or None
        item   = self.tree.currentItem()
        parent = item.parent() if item is not None else None
        # ``parent.parent() is None`` means ``parent`` is a search ROOT row
        # ("templates"), which is a location, not a node class.
        if parent is not None and parent.parent() is not None:
            node = parent.data(0, _ENTRY_ROLE)
            if getattr(node, "native_type", None) is None:
                cat = getattr(node, "label", None)
                if cat:
                    return cat
        return native_type

    def _style_description(self):
        """Restyle the just-loaded description.

        Shares the docs viewer's styler rather than growing a second one. The
        metrics differ because the surfaces do: this pane is ~240px tall inside
        the panel, the docs viewer is a 900x720 dialog, so it opts into the
        margin / paragraph / inline-code passes that the viewer leaves off.

        Non-fatal by design: a styling failure must never cost the user the
        description text, which is already on screen by this point.
        """
        try:
            from mpynode.ui.dialogs.doc_viewer import style_markdown_document

            dark = self.desc_browser.palette().color(
                QPalette.Base).lightness() < 128
            style_markdown_document(
                self.desc_browser.document(),
                dark         = dark,
                doc_margin   = 14.0,
                para_spacing = (0.0, 10.0),
                inline_code  = True,
            )
        except Exception:  # noqa: BLE001
            pass

    def _on_desc_anchor(self, url):
        """Open a description's link in the system browser.

        The pane has no navigation of its own, so letting Qt follow the link
        would replace the description with a blank page and no way back."""
        try:
            QDesktopServices.openUrl(url)
        except Exception:  # noqa: BLE001
            pass

    def _selected_entry(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        return item.data(0, _ENTRY_ROLE)

    # -- filter (E6) ----------------------------------------------------
    def _apply_filter(self, text):
        needle = (text or "").strip().lower()
        root   = self.tree.invisibleRootItem()
        self._filter_item(root, needle)
        # Categories start collapsed, so a hit would stay hidden under its
        # ancestors. While a needle is present expand every still-visible
        # container; when the box clears, restore reload()'s default.
        for i in range(root.childCount()):
            top = root.child(i)
            if needle:
                self._expand_visible_containers(top)
            else:
                self._restore_collapsed_default(top)

    def _expand_visible_containers(self, item):
        """Expand ``item`` and every non-hidden descendant container so a
        filtered match is revealed (hidden branches are left alone)."""
        if item.childCount() and not item.isHidden():
            item.setExpanded(True)
            for i in range(item.childCount()):
                self._expand_visible_containers(item.child(i))

    def _restore_collapsed_default(self, top):
        """Restore the default expand state for a search-root branch: the root
        item expanded, every category beneath it collapsed (mirrors reload())."""
        top.setExpanded(True)
        stack = [top.child(i) for i in range(top.childCount())]
        while stack:
            it = stack.pop()
            it.setExpanded(False)
            stack.extend(it.child(i) for i in range(it.childCount()))

    def _filter_item(self, item, needle):
        # True if this subtree has any visible node. Categories AND entries can
        # have children, so leaf-ness comes from childCount; buildable nodes
        # always match by text.
        is_root           = item is self.tree.invisibleRootItem()
        any_child_visible = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), needle):
                any_child_visible = True
        if is_root:
            return any_child_visible
        node         = item.data(0, _ENTRY_ROLE)
        buildable    = bool(getattr(node, "native_type", None))
        is_tree_leaf = item.childCount() == 0
        if not needle:
            self_match = True
        elif is_tree_leaf or buildable:
            self_match = needle in item.text(0).lower()
        else:
            self_match = False
        visible = (not needle) or self_match or any_child_visible
        item.setHidden(not visible)
        return visible

    # -- create (E7) ----------------------------------------------------
    def _do_create(self, run_setup=False, run_demo=False, demo_name=None):
        entry = self._selected_entry()
        if entry is None or not getattr(entry, "native_type", None):
            return
        from mpynode._common.io import mpn_io
        # The ONLY full / decoding load in the flow.
        payload = mpn_io.load_mpn(entry.mpn_path)
        if self._on_create is not None:
            self._on_create(payload, entry.native_type, bool(run_setup),
                            bool(run_demo), demo_name)
        # A permanent tab does NOT close after Create; the old dialog did.

    def stop_video(self):
        """Stop + release the video preview player. Public so the host can stop
        playback when this tab is hidden or the shared side panel collapses."""
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass
            self._player = None

    def showEvent(self, event):
        # Marks the splitter geometry as real for save_layout(). A non-current
        # QTabWidget page gets NO showEvent until its tab is selected, so this
        # only trips once the user opens the Templates mode.
        self._ever_shown = True
        super(NDTemplateGalleryPanel, self).showEvent(event)

    def hideEvent(self, event):
        # Never let a QMediaPlayer keep running under a hidden tab / panel.
        self.stop_video()
        super(NDTemplateGalleryPanel, self).hideEvent(event)
