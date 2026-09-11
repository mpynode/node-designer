"""NDApiView -- the Script tab's "API" surface: the node as it bakes.

Shows the node exactly as ``File > Bake Node to .py`` would emit it, with each
expression body reduced to its call and a line count, every generated line
marked, and a right-click on any generated zone offering the tab that owns it.

Three things make this cheap rather than a second editor:

* the buffer IS ``py_export.generate_node_script_with_regions()``'s text, so
  what you read is what gets baked -- no synthesized document to keep in sync;
* folding is ``QTextBlock.setVisible(False)``, which ``QPlainTextDocumentLayout``
  genuinely honours, so nothing is rewritten and no offset remapping is needed;
* because ``blockNumber()`` survives a fold and the shipped gutter already skips
  invisible blocks, the line numbers stay TRUE baked line numbers and simply run
  non-contiguously across a fold (287 -> 419). No gutter subclass.

WHAT AN EXPRESSION LOOKS LIKE HERE
``node.set_compute_expression(‹ 2 lines ›)`` -- one line per tier, always. The
exporter emits the body inline, so ``node.set_init_expression(\"\"\"import math``
is ONE physical line: the call and the user's first body line share it. The
view hides every other line of the region and PAINTS OVER the rail from the
opening paren, so the delimiter, the first body line and the closer are never
on screen; the escaped (accumulator) form hides its ``exp = ...`` lines under
its call line the same way. The count is the body's own line count
(``body_lines``, recorded by the exporter) -- not the number of hidden blocks,
which under-counted a two-line compute as one and left a one-line body fully
visible, looking editable. Nothing expands: the body is authored in its own
tab, and right-click > Go to <tier> is the way there. The gutter still shows
TRUE baked line numbers, running non-contiguously across the hidden lines
(287 -> 419). No gutter subclass.

EDITABLE WHERE IT IS YOURS, READ-ONLY WHERE IT IS GENERATED
The Methods source is edited HERE, in the file it bakes into -- indented inside
``class X:``, with the free functions at module scope where they really land.
That is the whole reason the separate Methods pane went away: it showed methods
and free functions flat at column 0, so the one thing Python uses to express
scope was missing.

Two mechanics make that safe:

* ``setReadOnly`` is whole-widget -- Qt has no per-block read-only -- so the
  managed spans are protected by refusing the keystroke instead. Every mutating
  gesture (typing, Backspace/Delete, Cut, paste, drop) resolves to a character
  range and is allowed only if that range lies strictly inside one editable
  region.
* an edit shifts every offset below it, so each region carries a ``QTextCursor``
  rather than a pair of ints. Qt maintains those across edits, which is what
  keeps the paint markers, the fold counts and the write-back spans correct
  while you type.

Write-back is a SPLICE, never a re-parse: each editable region names its slice of
``_methodsSource`` (``src_line`` / ``src_lines``), and only that slice is
replaced. This is what keeps the bake's lossiness harmless -- a def the exporter
SKIPS emits a ``method_warning`` comment with no editable region, so it is
untouchable here and survives verbatim in the source.

ROOM AROUND A MANAGED BLOCK
Return with the caret at the head of any block opens a line above it; Backspace
in the run above closes it again, down to the two blocks touching. Both halves
are required -- a boundary that collapses but will not re-open is a one-way
door -- and the gesture is the same everywhere so there is no map of special
spots to memorise. Only a NEWLINE is safe on a managed boundary: a character
typed there would land on generated code, so it is refused.

Where the result LIVES depends on the boundary, and that is not an
implementation detail:

* above the first generated line is the user's own file header. It is real
  text, spliced into ``_methodsSource`` as lines 1..N (including its trailing
  blank, which is why the exporter no longer appends a separator of its own),
  and it is defined POSITIONALLY rather than by a region so that it still
  exists when it is empty -- which is the case where Return has to work.
* a gap between two generated blocks holds no text the node can store, so only
  the COUNT is kept: ``gap_spacing_registry``, keyed by block, sparse, and
  consulted by ``py_export._DEFAULT_GAP``. It has to be on the NODE rather than
  in this widget because ``refresh()`` re-bakes the buffer on every return to
  the tab, and spacing held here would not survive a tab switch.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import (
    QColor,
    QKeySequence,
    QPainter,
    QPalette,
    QTextCursor,
    Qt,
    Signal,
)
from mpynode.ui.widgets.editor_core import QtPythonEditor


# ONE question, asked in two places: "is this line the Node Designer's, or
# yours?" The gutter answers it with a band, the code area with a wash.
#
# A per-SECTION colour scheme lived here briefly -- ten hues driven from
# preferences, mirrored by the navigator. It went out again because at the
# alpha that keeps line numbers readable the hues are nearly indistinguishable,
# so it spent a preferences page and two paint paths on a distinction nobody
# could actually see. The managed/yours split is the one that carries.
_MANAGED_COLOR = "#d2691e"
# The whole line-number block, not a hairline: the mark has to survive being
# glanced at. Alpha rather than a solid fill so the digits stay readable.
_GUTTER_ALPHA = 120
# The code area gets a wash instead. Derived from the palette's TEXT colour, not
# a fixed grey: the editor is dark in Maya and light in a headless render, and a
# hard-coded wash disappears against one of them. Blending toward the text
# colour reads as "slightly grey" on either.
# HALVED from 20: at alpha 0 the wash IS the plain editable background, so this
# sits midway between "managed" and "yours" -- the mark still reads, without the
# managed blocks shouting over the code they contain.
_TINT_ALPHA = 10
# The expression rail is the ONE line that is half generated and half yours.
# Slightly stronger so the split stays legible at a glance; still a wash. Halved
# alongside _TINT_ALPHA so it keeps the same 1.5x relative emphasis.
_TINT_ALPHA_SPLIT = 15
# QTextCursor.selectedText() joins blocks with U+2029 PARAGRAPH SEPARATOR, never
# "\n". Spelled as an escape so the source stays unambiguous.
_PARA_SEP = "\u2029"
# The blank lines BETWEEN generated regions belong to no region at all. Left
# alone they are the worst of both worlds -- unmarked, so they look editable,
# and outside every region cursor, so typing is silently refused. They are the
# formatter's, not yours, so they read as managed like everything around them.
#
# A SENTINEL rather than "inherit the neighbour": a gap that inherited an
# editable module-scope region would paint as unmanaged while ``_allows`` still
# refused it -- the same lie, moved. Blank lines INSIDE your own function are
# already inside that region's span and never reach this.
_GAP_REGION = {"kind": "gap", "label": None}
# NOT "header": the top of the file is the user's own comment block and/or
# docstring, spliced back to Methods lines 1..N like any other region they own.
# The generated 16-line preamble is gone -- see py_export.BAKE_CONTRACT.
#
# "metadata" IS generated: the Node Info banner is regenerated from the node's
# metadata on every build of this buffer, so it is edited in that dialog, not
# here. Typing into it would be written back nowhere and overwritten on the next
# refresh -- exactly the staleness the refusal exists to prevent.
_GENERATED_KINDS = (
    "metadata", "imports", "class_decl", "build_signature",
    "attrs_in", "attrs_out", "expr_header", "vars", "helpers", "return",
    "method_warning", "gap",
)
# Generated kinds that sit ABOVE the user's header zone instead of below it.
#
# The zone is defined POSITIONALLY -- everything between here and the first
# generated line (see _top_limit / _top_start) -- because it has to exist while
# it is still empty. A generated region at the very top therefore collapses it
# to nothing, and since the save reads the zone off the DOCUMENT rather than off
# a region, an empty zone splices over Methods lines 1..N and DELETES a header
# the user really had. Listing the banner here keeps the zone below it.
_ABOVE_TOP_ZONE = ("metadata",)


class NDApiView(QtPythonEditor):
    """The baked ``.py``: folded, annotated, and editable where it is yours."""

    # A persistent-variable declaration was activated; carries the var name.
    variableActivated = Signal(str)
    # An attribute block was activated; carries "Inputs" or "Outputs" so the
    # host can raise the Attributes tab. Same rule the tiers and the variables
    # already follow: a click on generated code goes to where that thing is
    # actually authored, not to a read-only rendering of it.
    attributesActivated = Signal(str)
    # Right-click > "Go to <tier>" on an expression line; carries the tier
    # label (Init / Compute / Viewport / OSL) so the host can raise that tab.
    # Right-click ONLY: a left click on a rail highlights and stays put (see
    # mousePressEvent) -- the tier is already on screen under it.
    tierActivated = Signal(str)
    # Aggregate dirty state, same contract as the other Script-tab editors.
    dirtyStateChanged = Signal(bool)
    # A keystroke was refused because it landed on a generated span.
    editRefused = Signal(str)
    # A line was clicked; carries its REGION so the host can light up the
    # navigator row that names it. Carries the region rather than a key
    # because this view has no idea what the navigator calls things -- the
    # navigator maps it back with keyForRegion().
    regionActivated = Signal(object)

    def __init__(self, py_node=None, parent=None):
        super().__init__(parent)
        self._py_node = py_node
        self._regions = []
        self._source = ""
        # block number -> region, for hit-testing and painting
        self._block_region = {}
        # block number of each expression rail -> its region, for the
        # placeholder painted over the rail (``‹ N lines ›)``). Rebuilt with
        # the region index, so a rail that moved under typing above it is
        # still found.
        self._placeholders = {}
        # block number of each ``set_variable`` line -> its value entry (name /
        # open_col / summary, from the exporter): the data itself is never on
        # screen, the summary is painted over it.
        self._value_placeholders = {}
        # (region, QTextCursor) for EVERY region. Ints would go stale on the
        # first keystroke; Qt maintains cursors.
        self._region_cursors = []
        # block number -> (x0, x1, y0, y1) of the placeholder drawn on that
        # row. Not a click target -- a left click on a rail belongs to the
        # tier -- but the painter records it so a test can prove the
        # placeholder clears the line's own text instead of printing over it.
        self._marker_rects = {}
        self._last_saved_methods = None
        # Baseline for the blank-line spacing, same contract as the Methods
        # baseline above: re-read on every load so a re-bake is not "dirty".
        self._last_saved_spacing = {}
        self._loading = False
        # A drag-and-drop can both insert at the drop point AND delete at the
        # source, which is two guarded ranges rather than one. The surface it
        # replaces never accepted drops, so refusing them regresses nothing.
        self.setAcceptDrops(False)
        self.cursorPositionChanged.connect(self._skip_hidden_blocks)
        # QPlainTextEdit scrolls horizontally by BLITTING the viewport and
        # repainting only the newly exposed strip. Every decoration below is
        # positioned against the viewport rather than the document, so a blit
        # drags a copy of it sideways and nothing ever erases the copy --
        # markers smeared into trails. Repaint the whole viewport instead.
        self.horizontalScrollBar().valueChanged.connect(self._repaint_viewport)
        if py_node is not None:
            self.setPyNode(py_node)

    # ------------------------------------------------------------------
    # Contract used by the Script tab
    # ------------------------------------------------------------------

    def getMPyNode(self):
        return self._py_node

    def setPyNode(self, py_node) -> None:
        self._py_node = py_node
        self.refresh()

    def refresh(self, force: bool = False) -> None:
        """Re-bake and re-hide the bodies. Cheap enough to call on tab activation.

        REFUSES to run while there are unsaved edits: the bake is a projection
        of the node, so re-running it would silently discard whatever the user
        has typed since the last save.

        ``force`` is for a caller that changed the Methods source ITSELF (the
        blessed-template insert). Without it that caller deadlocks: writing the
        plug makes this view's baseline stale, which reads as "dirty", which
        makes the very refresh that would pick the change up a no-op.
        """
        if not force and self.hasUnsavedChanges():
            return
        src, regions = "", []
        if self._py_node is not None:
            try:
                from mpynode._common.io.py_export import (
                    generate_node_script_with_regions,
                )

                # DIRECTLY, never through resolve_bake_class_name -- that one
                # PROMPTS and STAMPS _pyClass on the node. Merely looking at
                # this tab must not mutate anything. WITH the persistent
                # values: this view shows the node as it IS -- each value as a
                # managed placeholder -- while the bake itself asks.
                src, regions = generate_node_script_with_regions(
                    self._py_node, include_values=True)
            except Exception as exc:  # noqa: BLE001
                src = "# The bake could not be generated:\n# %s: %s" % (
                    type(exc).__name__, exc)
                regions = []
        self._source = src
        self._regions = regions
        # This runs on EVERY return to the tab, so without a save/restore the
        # caret goes home to line 1 each time -- setPlainText resets both the
        # caret and the scroll. The tier editors keep their place because they
        # are buffers that are never reloaded; this one is a projection.
        where = self._capture_position()
        self._loading = True
        try:
            self.setPlainText(src)
        finally:
            self._loading = False
        self._build_region_cursors()
        self._index_regions()
        # setPlainText drops every block's visibility flag, so the bodies have
        # to be re-hidden after ANY load -- not just the first.
        self._hide_bodies()
        # AFTER hiding: a restored caret must not land on a hidden block.
        self._restore_position(where)
        self._last_saved_methods = self._methods_from_document()
        self._last_saved_spacing = self._spacing_from_document()
        self.dirtyStateChanged.emit(False)

    def _capture_position(self):
        """``(caret_block, caret_col, vscroll, hscroll)`` as it stands now."""
        cursor = self.textCursor()
        return (cursor.blockNumber(), cursor.columnNumber(),
                self.verticalScrollBar().value(),
                self.horizontalScrollBar().value())

    def _restore_position(self, where) -> None:
        """Put the caret and the scrollbars back, clamped to the new document.

        The re-bake can be shorter than what it replaced (a tier shrank), so
        every index is clamped rather than trusted.
        """
        if not where:
            return
        block_no, col, vscroll, hscroll = where
        doc = self.document()
        block_no = max(0, min(int(block_no), doc.blockCount() - 1))
        block = doc.findBlockByNumber(block_no)
        # A block that is now folded away would park the caret somewhere
        # invisible; walk forward to the first block the user can actually see.
        probe = block
        while probe.isValid() and not probe.isVisible():
            probe = probe.next()
        if probe.isValid():
            block = probe
        if block.isValid():
            cursor = self.textCursor()
            cursor.setPosition(
                block.position() + max(0, min(int(col), len(block.text()))))
            self.setTextCursor(cursor)
        for bar, value in ((self.verticalScrollBar(), vscroll),
                           (self.horizontalScrollBar(), hscroll)):
            bar.setValue(max(bar.minimum(), min(int(value), bar.maximum())))

    def _repaint_viewport(self, *_args) -> None:
        """Full repaint. Bound to horizontal scroll -- see ``__init__``."""
        self.viewport().update()

    # ------------------------------------------------------------------
    # Dirty / save, over the METHODS source rather than the whole document
    # ------------------------------------------------------------------

    def hasUnsavedChanges(self) -> bool:
        if self._last_saved_methods is None:
            return False
        if self._spacing_from_document() != self._last_saved_spacing:
            return True
        current = self._methods_from_document()
        return current is not None and current != self._last_saved_methods

    def _top_text(self) -> str:
        """The text above the first generated line: the user's file header.

        Read off the DOCUMENT rather than the header region, because the zone
        has to work when no header region exists -- that is the case where the
        user has just pressed Return on line 1 to make room for one.
        """
        limit = self._top_limit()
        start = self._top_start()
        if limit <= start:
            return ""
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)
        cursor.setPosition(limit, QTextCursor.KeepAnchor)
        text = cursor.selectedText().replace(_PARA_SEP, "\n")
        # The selection runs up to the first character of the generated line,
        # so it ends with the newline that terminates the header. That newline
        # is a SEPARATOR, not a line of its own; keeping it would splice one
        # extra blank line into the Methods source on every single save.
        return text[:-1] if text.endswith("\n") else text

    def _spacing_from_document(self) -> dict:
        """``{gap key: blank lines}`` for every boundary that no longer matches
        the exporter's own spacing.

        SPARSE: a boundary the user has not touched is absent, so a node that
        has never been re-spaced stores nothing and bakes exactly as before.
        """
        try:
            from mpynode._common.io.py_export import _DEFAULT_GAP, gap_key
        except Exception:  # noqa: BLE001
            return {}
        doc = self.document()
        out = {}
        for region, cursor in self._region_cursors or ():
            kind = region["kind"]
            if kind == "imports":
                # The blanks above the imports are the tail of the header,
                # which round-trips as Methods text. Counting them here too
                # would emit every one of them twice on the next bake.
                continue
            first = doc.findBlock(cursor.selectionStart()).blockNumber()
            count, probe = 0, first - 1
            while probe >= 0 and self._is_gap_line(probe):
                count += 1
                probe -= 1
            if count != _DEFAULT_GAP.get(kind, 0):
                out[gap_key(kind, region.get("label"))] = count
        return out

    def markSaved(self) -> None:
        """Splice every edited region back into ``_methodsSource`` and store it.

        Only the named slices are replaced, so anything the bake dropped -- a
        skipped member, a comment between defs -- is carried through untouched.
        """
        if not self.hasUnsavedChanges():
            return
        spacing = self._spacing_from_document()
        if spacing != self._last_saved_spacing:
            setter = getattr(self._py_node, "set_api_gap_spacing", None)
            if setter is not None:
                try:
                    setter(spacing)
                    self._last_saved_spacing = spacing
                except Exception as exc:  # noqa: BLE001
                    import sys

                    sys.stderr.write(
                        "[NDApiView] set_api_gap_spacing failed: %s\n" % exc)
        text = self._methods_from_document()
        if text is None:
            self.dirtyStateChanged.emit(self.hasUnsavedChanges())
            return
        try:
            self._py_node.set_methods_source(text)
        except Exception as exc:  # noqa: BLE001
            import sys

            sys.stderr.write("[NDApiView] set_methods_source failed: %s\n" % exc)
            return
        self._last_saved_methods = text
        self.dirtyStateChanged.emit(False)

    def _methods_from_document(self):
        """The Methods source implied by the document's editable regions, or
        None when this node has no Methods surface at all."""
        if self._py_node is None or not hasattr(
                self._py_node, "get_methods_source"):
            return None
        try:
            original = self._py_node.get_methods_source() or ""
        except Exception:  # noqa: BLE001
            return None
        lines = original.split("\n")
        edits = []
        for region, cursor in self._region_cursors:
            if not self._is_editable(region):
                continue
            if region["kind"] == "header":
                continue   # handled below, off the DOCUMENT, so that a header
                           # the user has only just started also lands
            src_line = region.get("src_line")
            span = region.get("src_lines")
            if not src_line or not span:
                continue
            edits.append((src_line, span, self._region_text(region, cursor)))
        # The file header, as lines 1..N of the Methods source. Taken from the
        # top zone rather than a region so that the case with NO header region
        # -- the user pressed Return on line 1 to make room -- prepends instead
        # of being dropped. Sorting puts it last, after every later splice, so
        # a change in its length cannot shift the line numbers those used.
        header = next((r for r in self._regions
                       if r["kind"] == "header"), None)
        n_header = int((header or {}).get("src_lines") or 0)
        top = self._top_text()
        if top or n_header:
            edits.append((1, n_header, top))
        # LAST first, so an earlier splice cannot invalidate a later index.
        for src_line, span, text in sorted(edits, reverse=True):
            # "" is NO lines, not one empty line -- deleting the whole header
            # has to close the hole rather than leave a blank at the top.
            replacement = text.split("\n") if text else []
            lines[src_line - 1:src_line - 1 + span] = replacement
        return "\n".join(lines)

    def _region_text(self, region, cursor) -> str:
        """A region's current text, back in Methods-source shape: the
        synthesized ``@classmethod`` dropped, the class-body indent removed,
        and the formatter's trailing blank lines dropped.

        The exact inverse of ``py_export._indent_block`` for unedited text.
        The trailing-blank strip is what makes ``_claim_end`` safe: the region
        now covers blank lines the bake ADDED and the Methods source never
        held, so without it every save would splice them in and the file would
        grow a blank line per save, forever.
        """
        text = cursor.selectedText().replace(_PARA_SEP, "\n")
        if region.get("synth_classmethod"):
            head, _sep, rest = text.partition("\n")
            if head.strip() == "@classmethod":
                text = rest
        if region.get("keep_blanks"):
            # The file header, whose trailing blank line IS the separator above
            # the imports and is part of the user's slice. Stripping it would
            # close the gap they opened, every save, until it stayed shut.
            return text
        if not region.get("indent"):
            return _strip_trailing_blanks(text)
        rows = text.split("\n")
        widths = [len(r) - len(r.lstrip(" ")) for r in rows if r.strip()]
        # Cap at the indent the bake ADDED so a deeper body keeps its shape,
        # and take the smallest actual indent so a user who dedented is not
        # cut into.
        cut = min(widths + [region["indent"]]) if widths else 0
        return _strip_trailing_blanks(
            "\n".join(r[cut:] if r.strip() else r for r in rows))

    # ------------------------------------------------------------------
    # Region index + folding
    # ------------------------------------------------------------------

    def _build_region_cursors(self) -> None:
        """One ``QTextCursor`` per region, selecting its text.

        The region dicts carry the line numbers the BAKE produced. The instant
        the user types, every line below the caret moves and those numbers are
        wrong -- for the paint markers, for the fold counts, and for the
        write-back spans. Qt maintains a cursor across edits; ints it does not.
        """
        doc = self.document()
        self._region_cursors = []
        for r in self._regions:
            first = doc.findBlockByNumber(r["start"])
            end = self._claim_end(r)
            last = doc.findBlockByNumber(end)
            if not first.isValid() or not last.isValid():
                continue
            cursor = QTextCursor(doc)
            cursor.setPosition(first.position())
            cursor.setPosition(last.position() + len(last.text()),
                               QTextCursor.KeepAnchor)
            self._region_cursors.append((r, cursor))

    def _claim_end(self, region) -> int:
        """A region's last line, extended over the BLANK lines that follow it
        when the region is yours.

        The formatter puts one or two blank lines between top-level items.
        Left unclaimed they were painted managed even BETWEEN two of your own
        functions, and refused every keystroke -- so there was nowhere to write
        a new top-level function at all. Absorbed into the preceding editable
        region they become yours, and the write-back strips the trailing blanks
        again (see ``_region_text``) so they cannot accumulate.

        Only ever extends over genuinely EMPTY lines, and never past the start
        of the next region.
        """
        end = int(region["end"])
        if not self._is_editable(region):
            return end
        doc = self.document()
        nxt = self._next_region_start(region)
        limit = (nxt - 1) if nxt is not None else (doc.blockCount() - 1)
        probe = end + 1
        while probe <= limit:
            block = doc.findBlockByNumber(probe)
            if not block.isValid() or block.text().strip():
                break
            end = probe
            probe += 1
        return end

    def _next_region_start(self, region):
        """The first line of the next region after ``region``, or None."""
        best = None
        for other in self._regions:
            if other is region or other["start"] <= region["end"]:
                continue
            if best is None or other["start"] < best:
                best = other["start"]
        return best

    def _live_span(self, cursor):
        """``(first_block, last_block)`` for a region, as it stands NOW."""
        doc = self.document()
        return (doc.findBlock(cursor.selectionStart()).blockNumber(),
                doc.findBlock(cursor.selectionEnd()).blockNumber())

    def _index_regions(self) -> None:
        self._block_region = {}
        self._placeholders = {}
        self._value_placeholders = {}
        if not self._region_cursors:
            for r in self._regions:
                for ln in range(r["start"], r["end"] + 1):
                    self._block_region[ln] = r
                self._index_placeholders(r, r["start"])
            self._fill_gaps()
            return
        for r, cursor in self._region_cursors:
            first, last = self._live_span(cursor)
            for ln in range(first, last + 1):
                self._block_region[ln] = r
            self._index_placeholders(r, first)
        self._fill_gaps()

    def _index_placeholders(self, region, first: int) -> None:
        """Record what is painted over ``region``'s lines, given its CURRENT
        first line: the expression call line, or each ``set_variable`` value."""
        if self._is_placeholder(region):
            self._placeholders[first + int(region.get("call_offset") or 0)] = region
        for entry in region.get("values") or ():
            self._value_placeholders[first + int(entry.get("offset") or 0)] = entry

    def _fill_gaps(self) -> None:
        """Give every unclaimed line BETWEEN regions the gap sentinel.

        These are the formatter's blank separators -- the line between the
        inputs block and the outputs block, the two before ``class``. Left
        unclaimed they painted as yours and refused to be typed in, which is
        how a blank line inside ``build()`` became a bug report.

        Bounded by the LAST claimed line: trailing blanks past the end of the
        document's last region are nobody's, and claiming them would put a
        managed band under empty space at the bottom of the file.
        """
        if not self._block_region:
            return
        for ln in range(min(self._block_region), max(self._block_region)):
            self._block_region.setdefault(ln, _GAP_REGION)

    def _is_editable(self, region) -> bool:
        """A region the USER owns: their Methods source, spliceable back by a
        named slice. The tier expressions are editable too, but in their own
        tabs -- each writes a different plug, and here each is one placeholder
        line."""
        return bool(region.get("editable")
                    and region.get("owner") == "set_methods_source"
                    and region.get("src_line")
                    and region.get("src_lines"))

    @staticmethod
    def _is_placeholder(region) -> bool:
        """An expression tier: shown as ONE line, its call, whatever form the
        exporter chose -- inline triple-quoted or the escaped accumulator."""
        kind = region.get("kind") or ""
        return kind.startswith("expr_") and kind != "expr_header"

    def _placeholder_regions(self):
        """Every region shown as one placeholder line. The body is authored in
        its own tab; here it is a managed call with a line count, and nothing
        opens it. (Expand/collapse lived here until 2026-09: a one-line body
        had nothing below its rail to fold and so showed in full, looking
        editable, and the count under-counted a two-line compute as one.)"""
        for r in self._regions:
            if self._is_placeholder(r):
                yield r

    @staticmethod
    def _rail_of(region) -> int:
        """The one line of a placeholder region that stays visible: the CALL.
        An inline body opens on the call line; the escaped form builds ``exp``
        first and calls last (``call_offset``, from the exporter)."""
        return int(region["start"]) + int(region.get("call_offset") or 0)

    @staticmethod
    def _placeholder_label(region) -> str:
        """``‹ 2 lines ›`` -- the body's OWN line count, as the editor counts
        it, recorded by the exporter as ``body_lines``. Never the number of
        hidden blocks: the first body line shares the call line and the
        closing delimiter has a line of its own, so blocks miscount."""
        n = int(region.get("body_lines") or 0)
        if n <= 0:
            n = int(region["end"]) - int(region["start"]) + 1
        return "‹ %d line%s ›" % (n, "" if n == 1 else "s")

    def _hide_bodies(self) -> None:
        """Hide every line of every placeholder region except its call line.

        IDEMPOTENT: it sets visibility True on the rail as well as False on
        the rest, so a re-run after a load that reset every flag lands in the
        same state.
        """
        doc = self.document()
        for r in self._placeholder_regions():
            rail = self._rail_of(r)
            for ln in range(r["start"], r["end"] + 1):
                block = doc.findBlockByNumber(ln)
                if block.isValid():
                    block.setVisible(ln == rail)
        doc.markContentsDirty(0, max(0, doc.characterCount() - 1))
        self.viewport().update()

    def _skip_hidden_blocks(self) -> None:
        """Arrow keys walk INTO folded blocks -- Qt does not skip them. Nudge
        the caret back out to the nearest visible block."""
        cursor = self.textCursor()
        block = cursor.block()
        if block.isVisible():
            return
        probe = block
        while probe.isValid() and not probe.isVisible():
            probe = probe.next()
        if not probe.isValid():
            probe = block
            while probe.isValid() and not probe.isVisible():
                probe = probe.previous()
        if not probe.isValid():
            return
        cursor.setPosition(probe.position())
        self.blockSignals(True)
        try:
            self.setTextCursor(cursor)
        finally:
            self.blockSignals(False)

    # ------------------------------------------------------------------
    # The edit guard. setReadOnly is whole-widget, so protection is refusal.
    # ------------------------------------------------------------------

    def _top_start(self) -> int:
        """Character position where the user's header zone BEGINS.

        Zero, unless a generated banner sits above it (``_ABOVE_TOP_ZONE`` --
        the Node Info metadata), in which case the zone starts on the line
        after that banner. Without this the zone would start at 0 and swallow
        the banner: every keystroke in it would be allowed, and the save --
        which reads the zone off the document -- would write the banner's own
        text back into the Methods source as if the user had typed it.
        """
        doc = self.document()
        for region, cursor in self._region_cursors or ():
            if region.get("kind") not in _ABOVE_TOP_ZONE:
                continue
            _first, last = self._live_span(cursor)
            block = doc.findBlockByNumber(last + 1)
            return block.position() if block.isValid() else 0
        for region in self._regions:
            if region.get("kind") not in _ABOVE_TOP_ZONE:
                continue
            block = doc.findBlockByNumber(region["end"] + 1)
            return block.position() if block.isValid() else 0
        return 0

    def _top_limit(self) -> int:
        """Character position where the GENERATED file begins.

        Everything between ``_top_start`` and here is the user's own header.
        That zone is defined positionally, not by a region, because it has to
        exist when it is EMPTY: on a node with no header the buffer opens on
        ``from mpynode import ...`` and the limit is 0, which is precisely the
        spot where Return has to work so the user can make room.

        The metadata banner is skipped. It is generated, but it sits ABOVE the
        zone rather than closing it -- counting it would put the limit at 0 on
        every node that has metadata, which is not "no room for a header", it
        is "the header zone does not exist", and the save reads an empty zone
        as an instruction to delete the header.
        """
        doc = self.document()
        best = None
        for region, cursor in self._region_cursors or ():
            if self._is_editable(region) or region.get("kind") in _ABOVE_TOP_ZONE:
                continue
            first = doc.findBlock(cursor.selectionStart()).blockNumber()
            if best is None or first < best:
                best = first
        if best is None:
            for region in self._regions:
                if self._is_editable(region) or region.get("kind") in _ABOVE_TOP_ZONE:
                    continue
                if best is None or region["start"] < best:
                    best = region["start"]
        if best is None:
            return 0
        block = doc.findBlockByNumber(best)
        return block.position() if block.isValid() else 0

    def _starts_block(self, block_no: int) -> bool:
        """True when ``block_no`` is the FIRST line of any block.

        Editable blocks count. The blank lines above your own ``def`` are the
        exporter's spacing exactly as the ones above ``class`` are, and a rule
        that moved one but not the other would be a boundary the user has to
        memorise.
        """
        region = self._block_region.get(block_no)
        if region is None or region is _GAP_REGION:
            return False
        return self._region_first_line(region) == block_no

    def _region_first_line(self, region) -> int:
        for other, cursor in self._region_cursors or ():
            if other is region:
                return self.document().findBlock(
                    cursor.selectionStart()).blockNumber()
        return region["start"]

    def _is_gap_line(self, block_no: int) -> bool:
        """A blank line that belongs to no region -- the exporter's spacing."""
        block = self.document().findBlockByNumber(block_no)
        if not block.isValid() or block.text().strip():
            return False
        region = self._block_region.get(block_no)
        return region is None or region is _GAP_REGION

    def _allows_spacing(self, lo, hi, removing, newline) -> bool:
        """The blank lines BETWEEN two managed blocks are the user's to set.

        Return with the caret at the head of a managed block pushes it down;
        Backspace pulls it back up until the two blocks touch. Nothing else is
        allowed here: a gap holds no text in the node's data model, so letting
        a character be typed into one would promise a round trip that does not
        exist. The COUNT does round-trip -- see gap_spacing_registry.
        """
        doc = self.document()
        b_lo, b_hi = doc.findBlock(lo), doc.findBlock(hi)
        if not b_lo.isValid() or not b_hi.isValid():
            return False
        if newline:
            if lo != hi:
                return False
            n = b_lo.blockNumber()
            if lo == b_lo.position() and self._starts_block(n):
                return True
            return self._is_gap_line(n)
        if not removing:
            return False
        for n in range(b_lo.blockNumber(), b_hi.blockNumber() + 1):
            if self._is_gap_line(n):
                continue
            # Ending EXACTLY at a block's first character consumes none of it,
            # which is what a Backspace at the head of a managed block does.
            if n == b_hi.blockNumber() and hi == b_hi.position():
                continue
            return False
        return True

    def _allows(self, lo: int, hi: int, removing: bool = False,
                newline: bool = False) -> bool:
        """True when the character range ``[lo, hi]`` lies inside ONE editable
        region.

        THE START BOUNDARY DEPENDS ON THE OPERATION, and getting this wrong
        costs either data or the ability to edit:

        * INSERTING at the exact anchor is unsafe. Measured: with a cursor on
          865..960, inserting at 865 moves it to 866..961 and leaves the new
          character OUTSIDE -- the write-back would drop it silently. So an
          insert must start strictly past the anchor.
        * REMOVING at the exact anchor is safe. Text taken from the front just
          shrinks the selection; there is no ambiguity about which side of the
          anchor it fell on.

        Applying the insert rule to deletions made the first character of every
        region immortal: you could backspace a def away letter by letter and be
        left with a lone ``c`` from ``class`` that nothing could remove, which
        is a syntax error the editor refuses to let you repair.
        """
        limit = self._top_limit()
        # The zone has a FLOOR as well as a ceiling: with a metadata banner
        # above it, `hi < limit` alone would hand the banner's own lines to the
        # user, and the save would then write them back as Methods source.
        start = self._top_start()
        if start <= lo and hi < limit:
            return True          # strictly inside the user's own header
        if hi == limit and lo >= start and (removing or newline):
            # Deleting UP TO the first generated line collapses the header;
            # a newline THERE pushes the generated code down and opens the
            # room the user asked for. Typing at that exact spot is refused --
            # the character would land on the generated line itself.
            return True
        if self._allows_spacing(lo, hi, removing, newline):
            return True
        for region, cursor in self._region_cursors:
            if not self._is_editable(region):
                continue
            start = cursor.selectionStart()
            if hi > cursor.selectionEnd():
                continue
            if lo > start or (removing and lo == start):
                return True
        return False

    def _edit_range(self, event):
        """``(lo, hi, removing, newline)`` for a keystroke, or None if it
        changes nothing.

        ``removing`` is True when the gesture only TAKES text away, which is
        allowed to start at a region's first character. ``newline`` marks
        Return/Enter specifically: it is the ONE insert that can be safe on a
        managed boundary, because all it can do is push the managed block down
        and open space above it.
        """
        cursor = self.textCursor()
        if event.matches(QKeySequence.Undo) or event.matches(QKeySequence.Redo):
            # Only ever replays edits that were already permitted.
            return None
        if event.matches(QKeySequence.Copy) or event.matches(
                QKeySequence.SelectAll):
            return None
        if cursor.hasSelection():
            selected = (cursor.selectionStart(), cursor.selectionEnd())
        else:
            selected = None
        key = event.key()
        if event.matches(QKeySequence.Cut):
            return (selected or (cursor.position(), cursor.position())) + (
                True, False)
        if event.matches(QKeySequence.Paste):
            # Replaces: deletes the selection AND inserts at its start, so it
            # carries the insert's anchor hazard, not the delete's freedom.
            return (selected or (cursor.position(), cursor.position())) + (
                False, False)
        if key == Qt.Key_Backspace:
            if selected:
                return selected + (True, False)
            return (cursor.position() - 1, cursor.position(), True, False)
        if key == Qt.Key_Delete:
            if selected:
                return selected + (True, False)
            return (cursor.position(), cursor.position() + 1, True, False)
        if key in (Qt.Key_Return, Qt.Key_Enter):
            return (selected or (cursor.position(), cursor.position())) + (
                False, True)
        if key in (Qt.Key_Tab, Qt.Key_Backtab):
            return (selected or (cursor.position(), cursor.position())) + (
                False, False)
        text = event.text()
        if text and text.isprintable():
            return (selected or (cursor.position(), cursor.position())) + (
                False, False)
        return None

    def keyPressEvent(self, event):
        span = self._edit_range(event)
        if span is not None and not self._allows(*span):
            self._refuse()
            return
        opened = (span is not None and span[3]
                  and span[0] == span[1]
                  and not self._inside_own_text(span[0]))
        super().keyPressEvent(event)
        if opened:
            # Qt leaves the caret AFTER the inserted newline, i.e. back at the
            # head of the block that just moved down -- so the room the user
            # opened is above them and the next keystroke lands in the wrong
            # place. Put them in the space they just made.
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.PreviousBlock)
            cursor.movePosition(QTextCursor.EndOfBlock)
            self.setTextCursor(cursor)
        if span is not None:
            self._after_edit()

    def _inside_own_text(self, pos: int) -> bool:
        """True when ``pos`` sits strictly inside a region the user owns, where
        Return means "split this line" and the caret must be left alone."""
        for region, cursor in self._region_cursors:
            if not self._is_editable(region):
                continue
            if cursor.selectionStart() < pos < cursor.selectionEnd():
                return True
        return False

    def insertFromMimeData(self, source):
        cursor = self.textCursor()
        lo = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        hi = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()
        if not self._allows(lo, hi, False, False):
            self._refuse()
            return
        super().insertFromMimeData(source)
        self._after_edit()

    def _refuse(self) -> None:
        region = self._block_region.get(self.textCursor().block().blockNumber())
        owner = (region or {}).get("label")
        kind = (region or {}).get("kind") or ""
        if kind.startswith("expr_") and owner:
            message = "Generated — edit this in the %s tab" % owner
        elif kind in ("attrs_in", "attrs_out"):
            message = "Generated — edit these on the Attributes tab"
        elif kind == "vars":
            message = "Generated — edit these on the Variables tab"
        elif kind == "metadata":
            message = "Generated — edit this in Node Info"
        else:
            message = "Generated by Node Designer — not editable here"
        self.editRefused.emit(message)

    def _after_edit(self) -> None:
        if self._loading:
            return
        self._index_regions()
        self.viewport().update()
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())

    # ------------------------------------------------------------------
    # Painting: the managed span wash + the end-of-line marker
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._block_region:
            return
        painter = QPainter(self.viewport())
        try:
            self._paint_markers(painter)
        finally:
            painter.end()

    def _paint_markers(self, painter) -> None:
        # Rebuilt every pass. This walks EVERY visible block (not just
        # event.rect()), so a stale entry here would keep a click target alive
        # under a marker that is no longer drawn.
        self._marker_rects = {}
        fm = self.fontMetrics()
        try:
            char_w = fm.horizontalAdvance("9")
        except AttributeError:
            char_w = fm.width("9")
        height = fm.height()
        right = self.viewport().width()

        limit = self.viewport().height()
        block = self.firstVisibleBlock()
        top = self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= limit:
            if block.isVisible():
                region = self._block_region.get(block.blockNumber())
                if region is not None:
                    self._paint_one(painter, block, region, top, height,
                                    char_w, right)
            block = block.next()
            if not block.isValid():
                break
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()

    def _marks_generated(self, region, block_no) -> bool:
        """True when this line carries generated content -- the whole line, or
        the managed half of an expression rail.

        ONE rule, read by BOTH the gutter bar and the viewport tint, so the two
        halves of the same signal cannot drift apart.
        """
        if region["kind"] in _GENERATED_KINDS:
            return True
        return bool(region.get("body_col") and block_no == region["start"])

    # ------------------------------------------------------------------
    # The gutter half of the managed mark
    # ------------------------------------------------------------------

    def lineNumberAreaWidth(self):
        """A little more room than the shipped ``3 + digits``, so the managed
        block is a band rather than a stripe touching the digits."""
        return super().lineNumberAreaWidth() + 4

    def lineNumberAreaPaintEvent(self, event):
        """Colour the WHOLE line-number block on every generated line.

        The gutter is a SEPARATE widget living in the viewport margin, so it
        never scrolls horizontally -- which is exactly why the managed mark
        belongs here rather than out at the right edge of the text. Painted
        UNDER the digits: super() draws them first, and this goes over the
        background at partial alpha so they stay legible.
        """
        super().lineNumberAreaPaintEvent(event)
        if not self._block_region:
            return
        painter = QPainter(self._line_number_widget)
        try:
            managed = QColor(_MANAGED_COLOR)
            managed.setAlpha(_GUTTER_ALPHA)
            width = self._line_number_widget.width()
            block = self.firstVisibleBlock()
            top = self.blockBoundingGeometry(block).translated(
                self.contentOffset()).top()
            bottom = top + self.blockBoundingRect(block).height()
            height = self.fontMetrics().height()
            while block.isValid() and top <= event.rect().bottom():
                if block.isVisible() and bottom >= event.rect().top():
                    region = self._block_region.get(block.blockNumber())
                    if region is not None and self._marks_generated(
                            region, block.blockNumber()):
                        painter.fillRect(0, int(top), width, int(height),
                                         managed)
                block = block.next()
                if not block.isValid():
                    break
                top = bottom
                bottom = top + self.blockBoundingRect(block).height()
        finally:
            painter.end()

    def _on_pref_changed(self, key, value):
        """Redraw BOTH halves of the managed mark. The base class handles the
        live font change; the gutter is a separate widget and does not follow
        a viewport update, so it is refreshed explicitly."""
        super()._on_pref_changed(key, value)
        try:
            self.viewport().update()
            self._line_number_widget.update()
        except RuntimeError:
            # C++ side already deleted; the base class unsubscribes us.
            pass

    def _wash(self, alpha):
        """A grey wash at ``alpha``, taken from the palette's TEXT colour.

        NOT a fixed grey. The editor is dark in Maya and light in a headless
        render, and either constant vanishes against the other background.
        Blending toward the text colour lifts a dark base and darkens a light
        one, so it reads as "slightly grey" on both.
        """
        colour = QColor(self.palette().color(QPalette.Text))
        colour.setAlpha(alpha)
        return colour

    def _paint_one(self, painter, block, region, top, height, char_w, right):
        kind = region["kind"]
        n = block.blockNumber()
        if kind in _GENERATED_KINDS:
            # FULL viewport width, so the wash is identical at every horizontal
            # scroll offset and cannot leave a seam.
            painter.fillRect(0, int(top), right, int(height),
                             self._wash(_TINT_ALPHA))
        elif self._marks_generated(region, n):
            # The rail line of an inline expression is HALF generated: the call
            # and its opening delimiter, then the user's own first body line.
            # Wash only the generated half rather than claiming the whole line.
            # Offset by the scroll: this span is measured in DOCUMENT columns,
            # so unlike the full-width wash it has to travel with the text.
            painter.fillRect(
                int(self.contentOffset().x()), int(top),
                int(region["body_col"] * char_w), int(height),
                self._wash(_TINT_ALPHA_SPLIT))
        if self._placeholders.get(n) is region:
            self._paint_placeholder(painter, region, n, top, height, char_w,
                                    right)
        entry = self._value_placeholders.get(n)
        if entry is not None and region.get("kind") == "vars":
            # The value itself is never on screen: a summary of it stands
            # where the literal or the blob sits in the bake.
            self._paint_placeholder(
                painter, region, n, top, height, char_w, right,
                label="‹ %s ›, persistent=True)" % entry.get("summary", "value"),
                open_col=int(entry.get("open_col") or 0))

    def _paint_placeholder(self, painter, region, block_no, top, height,
                           char_w, right, label=None, open_col=None):
        """Reduce the rail to one readable line: the call, the count, the
        closing paren -- ``node.set_compute_expression(‹ 2 lines ›)``.

        COVERED FROM ``open_col``, NOT ``body_col``. body_col is where the
        user's text starts, i.e. just PAST the opening delimiter -- so covering
        from there left the delimiter and the body's first character on screen
        next to a count saying the body is not shown, and the closer had to be
        guessed. It guessed ``\"\"\"``, which is wrong every time the exporter
        picked ``\'\'\'`` to dodge a quote collision, and read as a mismatched
        pair. Covering the whole argument means neither the delimiter nor its
        closer is drawn at all, and there is nothing left to get wrong.

        Left-aligned at that column, not at the viewport edge; right-aligned
        it sat straight ON TOP of the code whenever the rail was long enough
        to reach.
        """
        if open_col is None:
            open_col = region.get("open_col")
        if open_col is None:
            open_col = region.get("body_col") or 0
        if label is None:
            label = "%s)" % self._placeholder_label(region)
        x = int(self.contentOffset().x()) + int(open_col * char_w)
        width = max(0, right - x)
        if width <= 0:
            return
        painter.fillRect(x, int(top), width, int(height),
                         self.palette().color(QPalette.Base))
        painter.fillRect(x, int(top), width, int(height),
                         self._wash(_TINT_ALPHA))
        painter.setPen(QColor("#8a8a8a"))
        painter.drawText(x, int(top), width, int(height),
                         int(Qt.AlignLeft | Qt.AlignVCenter), label)
        # Recorded for the tests that prove it clears the line's own text.
        self._marker_rects[block_no] = (
            x, x + int(len(label) * char_w), int(top), int(top + height))

    # ------------------------------------------------------------------
    # Click routing
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        # NOTHING is intercepted here. The marker used to swallow the click to
        # toggle its fold, which meant the one gesture the user actually wanted
        # -- "take me to the Compute code this is standing in for" -- was the
        # one gesture ``‹ 80 lines ›`` refused. The whole rail, placeholder
        # included, now routes to the tier. Going there lives on right-click.
        super().mousePressEvent(event)
        cursor = self.cursorForPosition(event.pos())
        region = self._block_region.get(cursor.block().blockNumber())
        if region is None:
            return
        # Always: light up whatever row of the navigator names this region, so
        # clicking the outputs block in the code shows you where "Outputs"
        # lives in the table. Highlight only -- the host does NOT navigate,
        # because you are already looking at the thing you clicked.
        self.regionActivated.emit(region)
        # NO tier signal. Clicking an expression rail used to raise that tier's
        # tab, and the user retracted it: the tier is already on screen, folded,
        # so being yanked to another tab costs the place you were reading and
        # buys nothing. The highlight above is the whole response.
        #
        # Variables and attributes still DO navigate, and the difference is not
        # arbitrary: their content is not in this buffer at all. A persistent
        # variable's value is painted over with a summary, never shown, so
        # there is nothing here to stay and look at.
        if region["kind"] == "vars":
            name = _var_name_on(cursor.block().text())
            if name:
                self.variableActivated.emit(name)
            else:
                # The block's comment line names no variable, but the block
                # still means "variables" -- go there anyway rather than
                # swallowing the click.
                self.variableActivated.emit("")
        elif region["kind"] in ("attrs_in", "attrs_out") and region.get("label"):
            self.attributesActivated.emit(region["label"])

    # ------------------------------------------------------------------
    # The context menu, which does NOT go through the keystroke guard
    # ------------------------------------------------------------------

    def _offers_file_load(self) -> bool:
        """No. This document is a projection of the node; loading an unrelated
        file over it would leave every region cursor naming a slice of text
        that has nothing to do with the Methods source it writes back to."""
        return False

    def setPlainText(self, text):
        """Re-derive the region cursors after ANY external replacement.

        Rename and Promote both apply their rewrite with
        ``rename_var._set_editor_text`` -> ``setPlainText``. That un-hides
        every body and collapses the maintained cursors, so without this the
        next save would splice the wrong slices. Both rewrite IN PLACE and keep the
        line count, so the region line numbers still hold and simply rebuilding
        against them restores the invariant -- and Promote keeps working here,
        which is the point.

        ``refresh`` does its own rebuild under ``_loading``; skip it there
        rather than doing the work twice.
        """
        super().setPlainText(text)
        if self._loading or not self._regions:
            return
        self._build_region_cursors()
        self._index_regions()
        self._hide_bodies()
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())

    def _menu_may_mutate(self, event) -> bool:
        """Whether a right-click here may offer editing actions at all.

        Both the CLICK and any live selection have to be inside one editable
        region: Qt's standard Cut / Delete are wired straight to the C++ slots,
        so they never reach ``keyPressEvent`` and cannot be guarded there.
        """
        cursor = self.cursorForPosition(event.pos())
        region = self._block_region.get(cursor.block().blockNumber())
        if region is None or not self._is_editable(region):
            return False
        selection = self.textCursor()
        if selection.hasSelection() and not self._allows(
                selection.selectionStart(), selection.selectionEnd(),
                removing=True):
            return False
        return True

    def _go_to_target(self, region, line_text=""):
        """``(menu text, fire)`` for the tab that AUTHORS ``region``'s line, or
        ``None`` for generated text nothing authors (the class line, the
        imports, ``return node``). ``fire`` emits the matching signal, which
        the host routes exactly as it routes that signal from a click."""
        if not isinstance(region, dict):
            return None
        kind = region.get("kind") or ""
        label = region.get("label") or ""
        if self._is_placeholder(region) and label:
            return ("Go to %s" % label,
                    lambda: self.tierActivated.emit(label))
        if kind == "vars":
            name = _var_name_on(line_text or "") or ""
            return ("Go to Variables" + (" · %s" % name if name else ""),
                    lambda: self.variableActivated.emit(name))
        if kind in ("attrs_in", "attrs_out") and label:
            return ("Go to %s" % label,
                    lambda: self.attributesActivated.emit(label))
        return None

    def contextMenuEvent(self, event):
        if self._menu_may_mutate(event):
            # Inside the user's own code: the shared menu, unchanged -- Rename
            # and Promote to Persistent Variable included.
            super().contextMenuEvent(event)
            return
        from mpynode.ui.qt_wrapper import QMenu

        menu = QMenu(self)
        # On a generated line the one thing worth offering is the way to where
        # that line is AUTHORED: the tier tab, Variables, Attributes.
        # (The expand/collapse items lived here until the bodies stopped
        # opening at all.)
        goto_act = None
        block = self.cursorForPosition(event.pos()).block()
        target = self._go_to_target(
            self._block_region.get(block.blockNumber()), block.text())
        if target is not None:
            goto_act = menu.addAction(target[0])
            menu.addSeparator()
        undo_act = menu.addAction("Undo")
        redo_act = menu.addAction("Redo")
        menu.addSeparator()
        copy_act = menu.addAction("Copy")
        all_act = menu.addAction("Select All")
        menu.addSeparator()
        save_act = menu.addAction("Save To File...")
        undo_act.setEnabled(self.document().isUndoAvailable())
        redo_act.setEnabled(self.document().isRedoAvailable())
        copy_act.setEnabled(self.textCursor().hasSelection())
        chosen = menu.exec_(event.globalPos())
        if chosen is None:
            return
        if goto_act is not None and chosen is goto_act:
            target[1]()
        elif chosen is undo_act:
            self.undo()
        elif chosen is redo_act:
            self.redo()
        elif chosen is copy_act:
            self.copy()
        elif chosen is all_act:
            self.selectAll()
        elif chosen is save_act:
            self._save_to_file()

    # ------------------------------------------------------------------
    # Introspection, for the host and for tests
    # ------------------------------------------------------------------

    def regions(self):
        return list(self._regions)

    def source(self) -> str:
        return self._source

    def hiddenLineCount(self) -> int:
        doc = self.document()
        return sum(1 for i in range(doc.blockCount())
                   if not doc.findBlockByNumber(i).isVisible())

    def regionAt(self, line: int):
        return self._block_region.get(line)

    def goToLine(self, line: int) -> bool:
        """Put the caret on baked line ``line`` (0-based) and centre it.

        Used by the navigator, whose module-scope and class-member rows have no
        tab of their own. Returns False for a line that is folded away or out
        of range, rather than parking the caret somewhere invisible.
        """
        block = self.document().findBlockByNumber(int(line))
        if not block.isValid() or not block.isVisible():
            return False
        cursor = self.textCursor()
        cursor.setPosition(block.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        return True


def _strip_trailing_blanks(text: str) -> str:
    """Drop trailing whitespace-only lines, keeping the rest byte for byte."""
    rows = text.split("\n")
    while rows and not rows[-1].strip():
        rows.pop()
    return "\n".join(rows)


def _var_name_on(text: str):
    """``node.add_variable('board', persistent=True)`` -> ``board``; likewise
    ``node.set_variable('board', ..., persistent=True)`` (a value line)."""
    marker = "add_variable("
    i = text.find(marker)
    if i < 0:
        marker = "set_variable("
        i = text.find(marker)
    if i < 0:
        return None
    rest = text[i + len(marker):].lstrip()
    if not rest or rest[0] not in "'\"":
        return None
    quote = rest[0]
    j = rest.find(quote, 1)
    if j < 0:
        return None
    return rest[1:j]
