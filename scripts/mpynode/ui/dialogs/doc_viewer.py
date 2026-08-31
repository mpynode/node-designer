"""Built-in Markdown documentation viewer (Help menu).

Renders ``docs/*.md`` through Qt's native ``QTextBrowser.setMarkdown`` --
no external dependencies. Relative ``.md`` links navigate in place with a
Back / Forward / Home history; ``http(s)`` links open in the system
browser. The link classification + docs discovery live in the Qt-free
``mpynode._common.util.docs_locator`` (which is where the unit tests bite).

Qt's ``setMarkdown`` ignores style sheets, so readability (heading
spacing + colour coding, table padding/zebra striping, code-block tint)
is applied by post-processing the populated ``QTextDocument`` directly --
see :func:`style_markdown_document`. The same heading walk powers
:meth:`MarkdownBrowser._scroll_to_slug`, because ``setMarkdown`` does not
emit named heading anchors for ``scrollToAnchor`` to find.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import (
    QAction,
    QBrush,
    QColor,
    QDesktopServices,
    QDialog,
    QFont,
    QHBoxLayout,
    QPalette,
    QPushButton,
    QTextBlockFormat,
    QTextBrowser,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTextFrameFormat,
    QTextLength,
    QTextTable,
    QTextTableFormat,
    QUrl,
    QVBoxLayout,
)
from mpynode._common.util import docs_locator


# Per-theme palettes: headings colour-coded by depth, tables a header band +
# zebra rows, code blocks a box + token colours.
_DARK = {
    "heading": {1: "#8FD0FF", 2: "#63B3E8", 3: "#5FBE9C", 4: "#C9A6F0"},
    "heading_default": "#A8B6C2",
    "code_bg": "#161B22",
    "code_keyword": "#FF7B72",
    "code_string": "#A5D6FF",
    "code_comment": "#8B949E",
    "code_number": "#79C0FF",
    "table_border": "#4A4F55",
    "table_header_bg": "#33383E",
    "table_zebra_bg": "#2A2E33",
    "inline_code_bg": "#3A3F47",
    "inline_code_fg": "#D7BA7D",
}
_LIGHT = {
    "heading": {1: "#1A5FA8", 2: "#1F6FB0", 3: "#1E7A52", 4: "#6A3FA0"},
    "heading_default": "#444444",
    "code_bg": "#F6F8FA",
    "code_keyword": "#CF222E",
    "code_string": "#0A3069",
    "code_comment": "#6E7781",
    "code_number": "#0550AE",
    "table_border": "#C8C8C8",
    "table_header_bg": "#E6E9ED",
    "table_zebra_bg": "#F4F6F8",
    "inline_code_bg": "#EFF1F3",
    "inline_code_fg": "#953800",
}


def _enum_int(v) -> int:
    """Integer value of a Qt enum across bindings. PySide2 (Qt5) enums are
    int-convertible; PySide6 (Qt6) scoped enums are not -- use ``.value``."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(v.value)


# Height-types for QTextBlockFormat.setLineHeight (Qt6 demands a plain int).
_PROP_HEIGHT = _enum_int(QTextBlockFormat.ProportionalHeight)
_SINGLE_HEIGHT = _enum_int(QTextBlockFormat.SingleHeight)

# Qt tags every fenced-code line (incl. interior blanks) with
# BlockCodeLanguage -- far more reliable than the rendered font.
try:
    _CODE_LANG_PROP = _enum_int(QTextFormat.BlockCodeLanguage)
except Exception:
    _CODE_LANG_PROP = 0x1090

# Inline code spans are the fixed-pitch fragments. Tested with hasProperty and
# NOT with charFormat().fontFixedPitch(): on Qt 5.15 the property is present on
# the span but its VALUE is False, so a value test matches nothing at all on
# Maya 2024 while working fine on 2026.
try:
    _FIXED_PITCH_PROP = _enum_int(QTextFormat.FontFixedPitch)
except Exception:
    _FIXED_PITCH_PROP = 0x2008

# NARROW NO-BREAK SPACE, used as the horizontal padding inside a code chip.
# Qt rich text has no char-level padding (the whole padding/border/radius
# family is frame- and cell-scoped), so the gap has to be a real character.
# NO-BREAK matters: U+2009 THIN SPACE is the same width but is a line-break
# opportunity, which splits the chip off its own text on roughly one wrap in
# three. The pad is formatted in the PROPORTIONAL body face -- in the mono face
# a space is a full character cell and the gap looks like a typo.
# Spelled as an escape so the source stays unambiguous.
_CHIP_PAD = "\u202f"


def _heading_block_margins(level: int):
    """(top, bottom) margin in px for a heading of the given level."""
    return {1: (22.0, 8.0), 2: (18.0, 6.0), 3: (14.0, 4.0)}.get(level, (10.0, 3.0))


def _block_is_code(block) -> bool:
    """True for a fenced-code line. Qt tags every line of a ``` block
    (including interior blank lines) with BlockCodeLanguage, so this is
    reliable where the rendered font is not."""
    return block.blockFormat().hasProperty(_CODE_LANG_PROP)


def style_markdown_document(document, dark: bool = True, doc_margin=None,
                            para_spacing=None, inline_code: bool = False) -> None:
    """Post-process a ``setMarkdown``-populated document for readability.

    Adds vertical breathing room + colour to headings, a touch more line
    spacing to body text, turns the cramped default tables into full-width
    tables with cell padding + a coloured header band + zebra rows, and
    renders fenced code as a GitHub-ish box with native syntax colouring.
    Idempotent enough to re-run after every load (each load re-parses the
    markdown fresh).

    The three keyword passes are OFF by default so this stays byte-identical
    for the Help viewer, which has rendered without them since it shipped.
    They exist for the template gallery, whose pane is a fraction of the
    dialog's size and wants its own metrics -- different numbers through one
    styler rather than a second implementation.

    ``doc_margin``   float px around the whole document. Qt's default is 4.0,
                     which reads as text jammed against the left edge.
    ``para_spacing`` ``(top, bottom)`` px for ordinary paragraphs. Qt's default
                     is 6/6 and the base function only ever set a line height,
                     so paragraphs ran together. List items and fenced code are
                     excluded -- they carry their own spacing.
    ``inline_code``  give single-backtick spans a tinted chip. See
                     :func:`_style_inline_code` for why this is not simply a
                     background on a fixed-pitch run.
    """
    pal = _DARK if dark else _LIGHT

    if doc_margin is not None:
        document.setDocumentMargin(float(doc_margin))

    block = document.firstBlock()
    while block.isValid():
        cursor = QTextCursor(block)
        bf = QTextBlockFormat(block.blockFormat())
        # Extra line spacing helps the density. Qt6 rejects the scoped
        # LineHeightTypes enum for the height-type, so pass a plain int.
        bf.setLineHeight(122.0, _PROP_HEIGHT)

        level = block.blockFormat().headingLevel()
        if level > 0:
            top, bottom = _heading_block_margins(level)
            bf.setTopMargin(top)
            bf.setBottomMargin(bottom)
            cursor.setBlockFormat(bf)
            colour = pal["heading"].get(level, pal["heading_default"])
            cf = QTextCharFormat()
            cf.setForeground(QColor(colour))
            cf.setFontWeight(QFont.Bold)
            sel = QTextCursor(block)
            sel.movePosition(QTextCursor.StartOfBlock)
            sel.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            sel.mergeCharFormat(cf)
        else:
            # Three exclusions. List items are already spaced as a group and a
            # margin on each one pulls a tight list apart. Fenced code sets its
            # own margins in _apply_code_box (8px at the box edges, 0 inside)
            # and a merge here would fight it. Table cells have cellPadding, so
            # a bottom margin there just makes every row taller.
            if (para_spacing is not None and block.textList() is None
                    and not _block_is_code(block)
                    and cursor.currentTable() is None):
                bf.setTopMargin(float(para_spacing[0]))
                bf.setBottomMargin(float(para_spacing[1]))
            cursor.setBlockFormat(bf)

        block = block.next()

    _style_code_blocks(document, pal)
    _style_tables(document, pal)
    if inline_code:
        # After the tables, so spans inside a cell sit on the zebra band.
        _style_inline_code(document, pal)


def _style_inline_code(document, pal) -> None:
    """Give single-backtick spans a tinted chip.

    An inline span and a fenced line render in the SAME mono face, so the font
    cannot tell them apart. What can: a fenced line carries
    ``BlockCodeLanguage`` on its BLOCK format, which an inline span never has.
    That is the same discriminator ``_block_is_code`` already uses.

    Headings are skipped. A heading block already gets a colour + bold merged
    across the whole of it, and a chip painted inside that reads as damage
    rather than emphasis (37 sites in the docs, 1 in the templates).

    Spans are collected FIRST and rewritten BACK TO FRONT: each pad insert adds
    characters and shifts every position after it, so a forward pass would
    corrupt every span but the first.

    Known ceiling: the chip has square corners. Qt rich text has no char-level
    border-radius -- the padding/border/radius family is frame- and cell-scoped
    only, CSS ``border-radius`` is dropped, and a custom inline ``QTextObject``
    is not usable from PySide (``handlerForObject`` returns None immediately
    after ``registerHandler``). A square tinted chip is as close to the VSCode
    pill as this widget goes.
    """
    body = document.defaultFont()
    cf = QTextCharFormat()
    cf.setBackground(QColor(pal["inline_code_bg"]))
    cf.setForeground(QColor(pal["inline_code_fg"]))
    # Slightly smaller so the chip sits INSIDE the line: the background paints
    # the span's own ascent+descent, and a mono face at the body size is taller
    # than the surrounding proportional text, so the chip would overhang.
    size = body.pointSizeF()
    if size and size > 0:
        cf.setFontPointSize(size * 0.92)

    pad = QTextCharFormat(cf)
    pad.setFontFixedPitch(False)
    # Qt6 wants setFontFamilies; Qt5 ignores it and wants setFontFamily. Set
    # both -- the pad must render in the proportional face to be a thin gap.
    for setter in ("setFontFamilies", "setFontFamily"):
        fn = getattr(pad, setter, None)
        if fn is None:
            continue
        try:
            fn([body.family()] if setter == "setFontFamilies" else body.family())
        except (TypeError, AttributeError):
            pass

    chip_bg = QColor(pal["inline_code_bg"])
    spans = []
    block = document.firstBlock()
    while block.isValid():
        if not _block_is_code(block) and block.blockFormat().headingLevel() == 0:
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.length():
                    fmt = frag.charFormat()
                    # Skip anything already chipped. The rest of this module is
                    # "idempotent enough" because every load re-parses the
                    # markdown; without this guard a re-style on the SAME
                    # document would pad every span a second time (the pad
                    # characters themselves carry the fixed-pitch property, so
                    # they would also be picked up as spans of their own).
                    if (fmt.hasProperty(_FIXED_PITCH_PROP)
                            and fmt.background().color() != chip_bg):
                        spans.append((frag.position(),
                                      frag.position() + frag.length()))
                it += 1
        block = block.next()

    for start, end in reversed(spans):
        sel = QTextCursor(document)
        sel.setPosition(start)
        sel.setPosition(end, QTextCursor.KeepAnchor)
        sel.mergeCharFormat(cf)
        # Trailing pad before leading, so `start` is still valid when we get
        # to it.
        tail = QTextCursor(document)
        tail.setPosition(end)
        tail.insertText(_CHIP_PAD, pad)
        head = QTextCursor(document)
        head.setPosition(start)
        head.insertText(_CHIP_PAD, pad)


def _style_code_blocks(document, pal) -> None:
    """Group consecutive fenced-code lines into regions, give each a
    contiguous background box, and syntax-highlight Python regions."""
    blocks = []
    b = document.firstBlock()
    while b.isValid():
        blocks.append(b)
        b = b.next()

    i, n = 0, len(blocks)
    while i < n:
        if not _block_is_code(blocks[i]):
            i += 1
            continue
        j = i
        while j < n and _block_is_code(blocks[j]):
            j += 1
        region = blocks[i:j]  # contiguous code lines (interior blanks incl.)
        _apply_code_box(region, pal)
        _highlight_python(document, region, pal)
        i = j


def _apply_code_box(region, pal) -> None:
    bg = QColor(pal["code_bg"])
    last = len(region) - 1
    for idx, blk in enumerate(region):
        bf = QTextBlockFormat()
        bf.setBackground(bg)
        bf.setLeftMargin(12.0)
        bf.setRightMargin(12.0)
        # Vertical padding only at the box edges so the lines stay flush.
        bf.setTopMargin(8.0 if idx == 0 else 0.0)
        bf.setBottomMargin(8.0 if idx == last else 0.0)
        # Single line height: proportional leading leaves page-coloured
        # stripes between lines (the box must paint solid).
        bf.setLineHeight(0.0, _SINGLE_HEIGHT)
        QTextCursor(blk).mergeBlockFormat(bf)


def _highlight_python(document, region, pal) -> None:
    """Colour keywords / strings / comments / numbers in a code region
    using the stdlib tokenizer (no external deps). Non-Python or malformed
    blocks (shell, console output) are left plain -- the box still shows."""
    import io
    import keyword
    import tokenize

    text = "\n".join(blk.text() for blk in region)
    spans = []  # (start_row, start_col, end_row, end_col, colour)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            ttype, tstr, (srow, scol), (erow, ecol), _ = tok
            colour = None
            if ttype == tokenize.COMMENT:
                colour = pal["code_comment"]
            elif ttype == tokenize.STRING:
                colour = pal["code_string"]
            elif ttype == tokenize.NUMBER:
                colour = pal["code_number"]
            elif ttype == tokenize.NAME and keyword.iskeyword(tstr):
                colour = pal["code_keyword"]
            if colour:
                spans.append((srow, scol, erow, ecol, colour))
    except Exception:
        # TokenError / IndentationError / etc. -> not clean Python; skip.
        return

    for srow, scol, erow, ecol, colour in spans:
        try:
            start = region[srow - 1].position() + scol
            end = region[erow - 1].position() + ecol
        except IndexError:
            continue
        cur = QTextCursor(document)
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        cf = QTextCharFormat()
        cf.setForeground(QColor(colour))
        cur.mergeCharFormat(cf)


def _style_tables(document, pal) -> None:
    root = document.rootFrame()
    if root is None:
        return
    for frame in root.childFrames():
        if not isinstance(frame, QTextTable):
            continue
        tf = QTextTableFormat(frame.format())
        tf.setCellPadding(6.0)
        tf.setCellSpacing(0.0)
        tf.setBorder(1.0)
        tf.setBorderBrush(QBrush(QColor(pal["table_border"])))
        try:  # BorderStyle_Solid: present in Qt 5.x+, guard regardless
            tf.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
        except (AttributeError, TypeError):
            pass
        # Full width spreads the columns out; the default sizes to content.
        tf.setWidth(QTextLength(QTextLength.PercentageLength, 100.0))
        frame.setFormat(tf)

        rows, cols = frame.rows(), frame.columns()
        for r in range(rows):
            if r == 0:
                bg = QColor(pal["table_header_bg"])
            elif r % 2 == 0:
                bg = QColor(pal["table_zebra_bg"])
            else:
                bg = None
            if bg is None:
                continue
            for c in range(cols):
                cell = frame.cellAt(r, c)
                ccf = cell.format()
                ccf.setBackground(bg)
                cell.setFormat(ccf)


_NOT_FOUND_MD = (
    "# Documentation not found\n\n"
    "Could not locate the `docs/` folder. It should sit beside the "
    "`scripts/` folder, or you can set the `MPYNODE_ROOT` environment "
    "variable to the project root."
)

# Placeholder repo URL -- swap for the real one when the project is pushed.
GITHUB_URL = "https://github.com/mpynode/node-designer"


def open_github(url: str = None) -> None:
    """Open the project's GitHub page in the system browser."""
    QDesktopServices.openUrl(QUrl(url or GITHUB_URL))


class MarkdownBrowser(QTextBrowser):
    """Read-only Markdown browser with in-app link navigation + history."""

    def __init__(self, parent=None):
        super(MarkdownBrowser, self).__init__(parent)
        # We handle every click: relative .md links must be resolved +
        # markdown-parsed, not loaded as HTML/plain text.
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setReadOnly(True)
        # A slightly larger base font; the Qt default is cramped.
        f = self.font()
        if f.pointSize() > 0:
            f.setPointSize(f.pointSize() + 1)
            self.setFont(f)
        self._current_path = None
        self._back = []
        self._fwd = []
        self.anchorClicked.connect(self._on_anchor)

    def _dark_theme(self) -> bool:
        return self.palette().color(QPalette.Base).lightness() < 128

    def _apply_styles(self):
        try:
            style_markdown_document(self.document(), dark=self._dark_theme())
        except Exception:
            # Styling is cosmetic -- never break rendering, but report it so
            # a binding quirk doesn't masquerade as "styling did nothing".
            import sys
            import traceback

            sys.stderr.write("[doc_viewer] styling failed (non-fatal):\n")
            traceback.print_exc()

    # -- loading --------------------------------------------------------
    def load(self, path, anchor="", _record=True) -> bool:
        """Render the markdown at ``path``. Returns False (without raising)
        if the file can't be read, showing an inline error instead."""
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            self.setMarkdown(
                "# Document not found\n\n`%s`\n\n%s" % (path, exc)
            )
            return False
        if _record and self._current_path and self._current_path != path:
            self._back.append(self._current_path)
            self._fwd.clear()
        self._current_path = path
        self.setMarkdown(text)
        self._apply_styles()
        if anchor:
            self._scroll_to_slug(anchor)
        return True

    def show_not_found(self):
        self._current_path = None
        self.setMarkdown(_NOT_FOUND_MD)

    # -- navigation -----------------------------------------------------
    def _on_anchor(self, url):
        if self._current_path is None:
            return
        kind = docs_locator.resolve_doc_link(self._current_path, url.toString())
        if kind[0] == "external":
            QDesktopServices.openUrl(QUrl(kind[1]))
        elif kind[0] == "anchor":
            self._scroll_to_slug(kind[1])
        elif kind[0] == "file":
            self.load(kind[1], kind[2])
        # "unknown" -> ignore (graceful no-op)

    def _scroll_to_slug(self, slug) -> bool:
        """Scroll so the heading whose text slugifies to ``slug`` sits at
        the top of the viewport. Qt's ``setMarkdown`` emits no named
        heading anchors, so ``scrollToAnchor`` can't do this -- we walk the
        heading blocks and match slugs ourselves.

        Returns True if a matching heading was found. Matching is exact on
        the doc's slug scheme, with a hyphen/underscore-insensitive
        fallback so GitHub-style anchors still navigate.
        """
        if not slug:
            return False
        doc = self.document()
        target = slug.strip().lower()
        loose = target.replace("-", "")
        block = doc.firstBlock()
        while block.isValid():
            if block.blockFormat().headingLevel() > 0:
                hslug = docs_locator.slugify(block.text())
                if hslug == target or hslug.replace("-", "") == loose:
                    y = doc.documentLayout().blockBoundingRect(block).top()
                    self.verticalScrollBar().setValue(int(y))
                    return True
            block = block.next()
        return False

    def go_back(self):
        if self._back:
            self._fwd.append(self._current_path)
            self.load(self._back.pop(), _record=False)

    def go_forward(self):
        if self._fwd:
            self._back.append(self._current_path)
            self.load(self._fwd.pop(), _record=False)


class DocViewerDialog(QDialog):
    """Non-modal window wrapping a MarkdownBrowser + Back/Forward/Home."""

    def __init__(self, parent=None):
        super(DocViewerDialog, self).__init__(parent)
        self.setWindowTitle("Node Designer — Documentation")
        self.setModal(False)
        self.resize(900, 720)

        layout = QVBoxLayout(self)
        nav = QHBoxLayout()
        self._back_btn = QPushButton("◀ Back")
        self._fwd_btn = QPushButton("Forward ▶")
        self._home_btn = QPushButton("Home")
        for b in (self._back_btn, self._fwd_btn, self._home_btn):
            nav.addWidget(b)
        nav.addStretch(1)
        layout.addLayout(nav)

        self.browser = MarkdownBrowser(self)
        layout.addWidget(self.browser)

        self._back_btn.clicked.connect(self.browser.go_back)
        self._fwd_btn.clicked.connect(self.browser.go_forward)
        self._home_btn.clicked.connect(self.open_home)

    def open_home(self):
        home = docs_locator.home_doc()
        if home:
            self.browser.load(home)
        else:
            self.browser.show_not_found()

    def open_path(self, path):
        if path:
            self.browser.load(path)
        else:
            self.open_home()


def open_doc_viewer(parent, path=None):
    """Create-or-reuse a single DocViewerDialog on ``parent`` and show it.

    A second invocation navigates the existing window rather than spawning a
    duplicate. Tolerates the dialog's C++ side having been destroyed.
    """
    viewer = getattr(parent, "_nd_doc_viewer", None)
    try:
        viewer.isVisible()  # probe: raises if the wrapped C++ object is gone
    except (RuntimeError, AttributeError):
        viewer = None
    if viewer is None:
        viewer = DocViewerDialog(parent)
        try:
            parent._nd_doc_viewer = viewer
        except (AttributeError, TypeError):
            pass
    viewer.open_path(path)
    viewer.show()
    viewer.raise_()
    viewer.activateWindow()
    return viewer


def add_documentation_menu(help_menu, parent):
    """Append the documentation entries to an existing Help ``QMenu``:

    * ``Documentation...``  -> opens docs/index.md (home)
    * ``Node Types`` submenu -> one entry per docs/node_types/*.md

    Returns ``(doc_action, node_types_submenu)``.
    """
    help_menu.addSeparator()

    # Parent each QAction to its menu, not the window: an unparented QAction
    # with no retained Python ref is GC'd and drops out of the menu.
    doc_action = QAction("Documentation…", help_menu)
    doc_action.triggered.connect(
        lambda checked=False: open_doc_viewer(parent)
    )
    help_menu.addAction(doc_action)

    nt_menu = help_menu.addMenu("Node Types")
    # mPyNode is pinned to the top with a separator (mirrors the "New" menu);
    # a ``None`` entry from the menu-order helper means "insert a separator".
    entries = docs_locator.list_node_type_docs_menu_order()
    any_action = False
    for entry in entries:
        if entry is None:
            nt_menu.addSeparator()
            continue
        title, path = entry
        act = QAction(title, nt_menu)
        act.triggered.connect(
            lambda checked=False, p=path: open_doc_viewer(parent, p)
        )
        nt_menu.addAction(act)
        any_action = True
    if not any_action:
        nt_menu.setEnabled(False)

    help_menu.addSeparator()
    github_action = QAction("Node Designer on GitHub", help_menu)
    github_action.triggered.connect(lambda checked=False: open_github())
    help_menu.addAction(github_action)

    return doc_action, nt_menu, github_action
