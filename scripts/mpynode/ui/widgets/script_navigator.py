"""NDScriptNavigator -- the OUTLINE: the Script area's right-hand column.

Every row of every section is a target, and every target is reached by the same
call. J3's invariant: there is no "navigator navigation" and separately "tab
navigation" -- there is ``select(key)``, and several things that call it. The
navigator emits the key; :class:`NDScriptTabContent` owns the one implementation.

    EXPRESSIONS   Init / Compute / [Viewport] / [OSL] -- greyed when the wrapper
                  has no setter, which a tab strip structurally cannot say
    MODULE        hoisted imports, free functions, module classes + constants
    CLASS · name  the managed skeleton -- class decl, build(), Inputs, Variables
    SETUP/DEMOS/  the members that DO something, each with a run affordance
    TESTS/COMMANDS
    BLESSED       @maya_command / @maya_demo / @maya_test offers for this node
                  TYPE that the buffer does not already carry -- right-click to
                  insert or copy
    VARIABLES     declared names only -- the DATA lives on the left

SINGLE SOURCE OF TRUTH
Every row except the greyed tiers and the blessed offers comes from the SAME
region map the API view renders -- ``generate_node_script_with_regions()``. The
navigator and the API view cannot disagree about what exists or where it lives,
because there is only one list, and each row carries the baked line it lands on
plus the Methods-source line it is edited at.

Deliberately NOT sourced from ``outline_model.build_outline()`` for STRUCTURE:
that walks ``ast.FunctionDef`` only, so a module-level ``class SetupError`` never
appears. It IS used for the blessed offers, which have no region because they
are not in the source at all -- that is the one thing the region map cannot know.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QSize,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

# Every tier the Script area knows about, in runtime order, with the wrapper
# method whose presence decides whether the node has it. Same probe the tab
# strip uses -- see script_tab_content.
TIER_PROBES = (
    ("Init", "set_init_expression"),
    ("Compute", "set_compute_expression"),
    ("Viewport", "set_viewport_expression"),
    ("OSL", "set_osl_expression"),
)

_MODULE_KINDS = ("imports_hoisted", "module_segment")

# Member roles that get their OWN section, in the order J3 draws them. Anything
# else is a plain method and stays under CLASS.
_MEMBER_SECTIONS = (
    ("setup", "SETUP"),
    ("command", "COMMANDS"),
    ("demo", "DEMOS"),
    ("test", "TESTS"),
)

# Rows the Node Designer owns: you cannot rename or delete them from here, and
# the badge says so. Mirrors the API view's managed wash.
#
# NOT the U+1F512 lock emoji it used to be. An emoji resolves to the colour
# emoji font, which is taller than the UI font, so those rows -- and only those
# rows -- grew and broke the vertical rhythm. A geometric glyph comes out of the
# same font as the rest of the label. The word beside it ("managed" / "class" /
# "generated") is what actually carries the meaning.
_LOCK = "▪"
_RUN = "▶"
# Breathing room above a section header, and the floor every row is pinned to so
# no glyph in any column can stretch one.
_SECTION_PAD = 6

_COL_SYMBOL, _COL_KIND, _COL_META = range(3)

# What this pane is called, shown above the tree. "Outline", not "Inspector":
# it is a structural map of the bake, and every row is a PLACE you go. An
# inspector shows the properties of one selected thing, which in a Maya tool is
# already a name with an owner -- the Attribute Editor, and the Attributes tab
# beside this one. Two panes cannot share that word.
PANEL_TITLE = "Outline"


class _NoFocusRect(QStyledItemDelegate):
    """Paint rows without the style's focus rectangle.

    Section rows already refuse selection (``_section`` leaves them
    ``ItemIsEnabled`` alone), but refusing SELECTION does not refuse CURRENT:
    Qt still moves a current index onto whatever was clicked and the style
    still outlines it. On a section that outline landed as a small square in
    the empty Kind cell beside EXPRESSIONS or COMMANDS -- a mark on a row that
    cannot be actioned, and one no further click could clear.

    Only the dotted focus outline goes. Real selection still highlights, so a
    clicked row and ``setCurrentKey`` both still read.
    """

    def paint(self, painter, option, index):
        # Copy: the view reuses its option object across cells, so mutating the
        # one handed in would leak this into whatever it paints next.
        option = QStyleOptionViewItem(option)
        if option.state & QStyle.State_HasFocus:
            # XOR rather than ``&= ~``: inverting a QFlags is the one operation
            # whose behaviour differs between the two bindings this wraps.
            option.state = option.state ^ QStyle.State_HasFocus
        super().paint(painter, option, index)


def _lines(n: int) -> str:
    """``13 lines`` / ``1 line``. Spelled out: "ln" was an abbreviation the
    reader had to decode, and the column has the room."""
    return "%d line%s" % (n, "" if n == 1 else "s")


class _Offer:
    """A framework skeleton wearing the same two attributes the palette reads
    off an ``OutlineItem`` -- ``name`` and ``template`` -- so both sources of
    offer render and behave identically."""

    __slots__ = ("name", "template")

    def __init__(self, template):
        self.name = template.name
        self.template = template


class NDScriptNavigator(QWidget):
    """Read-only outline of the node, driven by the bake's region map."""

    # A row was CLICKED -- show where it lives: NDScriptTabContent.locate()
    # raises the API view at the row's line. A single click never leaves the
    # baked file (single = locate, double / Enter = go edit).
    locateRequested = Signal(str)
    # A row was ACTIVATED (double-click / Enter) -- open its authoring tab.
    # NDScriptTabContent.select() is the one implementation.
    selectRequested = Signal(str)
    # A persistent-variable row was ACTIVATED -- reveal it on the left, where
    # the DATA lives. Separate because its target is not in this pane's stack.
    variableActivated = Signal(str)
    # A runnable member's run affordance was chosen: (run_kind, run_name).
    runRequested = Signal(str, str)
    # A blessed offer's "Insert" was chosen; carries the template SOURCE.
    insertTemplateRequested = Signal(str)

    def __init__(self, py_node=None, parent=None):
        super().__init__(parent)
        self._py_node = py_node
        # Set once the user drags a column divider, after which auto-fit stops
        # fighting them. Until then Symbol tracks the pane width. INSTANCE
        # attributes, not class ones -- a mutable class attribute here is the
        # same session-wide bleed _shared_tier has.
        self._user_sized = False
        self._fitting = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # A title bar above the tree. Its HEIGHT is pushed in by the host --
        # see NDScriptTabContent -- and set to the editor's tab strip, so that
        # "Symbol | Kind | Detail" below it lands level with the first line of
        # code rather than with the tabs. Nothing here can measure that strip;
        # only the thing that owns it can.
        self._title_bar = QWidget(self)
        title_row = QHBoxLayout(self._title_bar)
        title_row.setContentsMargins(6, 0, 6, 0)
        title_row.setSpacing(6)
        self._title_label = QLabel(PANEL_TITLE, self._title_bar)
        # The bake's length. It used to be a DOCUMENT section holding one row,
        # which made a category out of a single number and put the FILE in a
        # list of things INSIDE the file. It is a fact about the whole pane,
        # which is what a title bar is for. Disabled, because unlike every row
        # below it there is nowhere to go when you click it.
        self._total_label = QLabel("", self._title_bar)
        self._total_label.setEnabled(False)
        title_row.addWidget(self._title_label)
        title_row.addStretch(1)
        title_row.addWidget(self._total_label)
        layout.addWidget(self._title_bar)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(3)
        # "Detail", not "Line": the column carries a span ("132 lines"), a count
        # ("13 attrs") or a state ("not on this type"). The baked and
        # Methods-source line numbers are on each row's tooltip.
        self._tree.setHeaderLabels(["Symbol", "Kind", "Detail"])
        self._tree.setRootIsDecorated(True)
        # 20px of indent plus the section arrow left a child row ~60px of the
        # 100px Symbol column. The names are the content; buy the width back.
        self._tree.setIndentation(12)
        self._tree.setSelectionMode(QAbstractItemView.SingleSelection)
        # Kept on the instance: PySide GC drops a delegate the C++ side
        # only weakly holds, and the rows silently get their squares back.
        self._no_focus = _NoFocusRect(self._tree)
        self._tree.setItemDelegate(self._no_focus)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_menu)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemActivated.connect(self._on_item_activated)

        header = self._tree.header()
        # MEASURED default: stretchLastSection is True and the header is hidden,
        # so widening the pane 180 -> 460 gave all 280 new pixels to the LINE
        # column (100 -> 358) while Symbol stayed pinned at the 100px
        # defaultSectionSize. Show the header so the dividers can be dragged --
        # the thing the column is for is reading names -- and let Symbol take
        # the slack instead.
        header.setStretchLastSection(False)
        # All three Interactive and budgeted by hand. ResizeToContents on Kind
        # or Line reproduces the same crush in a new place: one long cell
        # ("base MPyLocator") takes the width and Symbol falls back to its
        # floor. Symbol is the content; the other two are capped.
        for col in (_COL_SYMBOL, _COL_KIND, _COL_META):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        header.setSectionsMovable(False)
        header.sectionResized.connect(self._on_section_resized)

        layout.addWidget(self._tree)

        # Live colour updates, same contract editor_core uses for the font:
        if py_node is not None:
            self.setPyNode(py_node)

    # -- title bar ---------------------------------------------------------

    def setTitleHeight(self, height: int) -> None:
        """Match the title bar to the editor's tab strip.

        Pushed in rather than measured: this widget lives in a splitter beside
        the strip and has no business reaching across to it.
        """
        if height > 0:
            self._title_bar.setFixedHeight(int(height))

    # -- column sizing ---------------------------------------------------

    def _on_section_resized(self, index, _old, _new) -> None:
        """A drag on the Symbol divider hands sizing to the user for good."""
        if index == _COL_SYMBOL and not self._fitting:
            self._user_sized = True

    # Kind is a single short token; Detail is "132 lines" / "13 attrs" / a short
    # phrase. Capped BOTH absolutely and as a share of the pane: absolute caps
    # alone still starved the names at a realistic width (at J3's 236px
    # preferred, a 90 + 120 pair left Symbol on its 60px floor).
    _KIND_CAP = 90
    _META_CAP = 120
    _SYMBOL_FLOOR = 60
    _SYMBOL_SHARE = 0.45

    def _fit_symbol_column(self) -> None:
        """Budget all three columns, Symbol first. Called on resize, because an
        Interactive column does not track the viewport on its own -- which is
        the whole defect: the shipped default handed every new pixel to the
        LAST column and pinned Symbol at the 100px defaultSectionSize."""
        if self._user_sized:
            return
        width = self._tree.viewport().width()
        if width <= 0:
            return
        reserved = max(self._SYMBOL_FLOOR, int(width * self._SYMBOL_SHARE))
        spare = max(0, width - reserved)
        kind = min(self._tree.sizeHintForColumn(_COL_KIND) + 8,
                   self._KIND_CAP, int(spare * 0.45))
        meta = min(self._tree.sizeHintForColumn(_COL_META) + 8,
                   self._META_CAP, spare - kind)
        self._fitting = True
        try:
            self._tree.setColumnWidth(_COL_KIND, max(0, kind))
            self._tree.setColumnWidth(_COL_META, max(0, meta))
            self._tree.setColumnWidth(
                _COL_SYMBOL, max(self._SYMBOL_FLOOR, width - kind - meta))
        finally:
            self._fitting = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_symbol_column()

    def showEvent(self, event):
        # MEASURED: a fit that runs before the tree is laid out reads
        # sizeHintForColumn as near-zero, so the first show kept a budget of
        # 60/17/21 out of 178px. Re-fit once the geometry is real.
        super().showEvent(event)
        self._fit_symbol_column()

    # ------------------------------------------------------------------

    def setPyNode(self, py_node, regions=None) -> None:
        """Point at ``py_node``. Pass ``regions`` to reuse a bake the caller
        already has -- the Script tab does, so the node is baked once per
        refresh rather than once per surface."""
        self._py_node = py_node
        self.refresh(regions)

    def refresh(self, regions=None) -> None:
        """Rebuild from ``regions``; re-bakes when not supplied."""
        selected = self.currentKey()
        self._tree.clear()
        self._total_label.setText("")
        if self._py_node is None:
            return
        if regions is None:
            regions = self._bake_regions()
        by_kind = {}
        for r in regions:
            by_kind.setdefault(r["kind"], []).append(r)
        # CLASS sits directly under EXPRESSIONS: those two are what you reach
        # for, so they get the top of the pane. MODULE is reference rather than
        # destination, and drops below.
        self._build_supports(by_kind)
        self._build_class(by_kind)
        self._build_members(regions)
        self._build_module(regions)
        self._build_blessed()
        self._build_variables(by_kind)
        self._set_total(regions)
        self._tree.expandAll()
        self._fit_symbol_column()
        if selected:
            self.setCurrentKey(selected)

    def _bake_regions(self):
        try:
            from mpynode._common.io.py_export import (
                generate_node_script_with_regions,
            )

            return generate_node_script_with_regions(self._py_node)[1]
        except Exception:  # noqa: BLE001
            return []

    # -- row construction -------------------------------------------------

    def _row_height(self) -> int:
        return self._tree.fontMetrics().height() + 2

    def _section(self, title: str, meta: str = "") -> QTreeWidgetItem:
        item = QTreeWidgetItem(self._tree, [title, "", meta])
        item.setFlags(Qt.ItemIsEnabled)
        # Sections used to be exactly row height, so SUPPORTS / MODULE ran
        # together with their own children. The gap is what makes them read
        # as separators.
        item.setSizeHint(_COL_SYMBOL,
                         QSize(0, self._row_height() + _SECTION_PAD))
        return item

    def _row(self, section, name, kind="", meta="", key=None, payload=None):
        row = QTreeWidgetItem(section, [name, kind, meta])
        # PINNED, so a tall glyph in any column cannot stretch one row out of
        # step with its neighbours.
        row.setSizeHint(_COL_SYMBOL, QSize(0, self._row_height()))
        if key is not None:
            row.setData(_COL_SYMBOL, Qt.UserRole, key)
        if payload is not None:
            row.setData(_COL_SYMBOL, Qt.UserRole + 1, payload)
        return row

    def _build_supports(self, by_kind) -> None:
        # "EXPRESSIONS", not "SUPPORTS": these rows ARE the expression tiers,
        # and the old name described the implementation (a hasattr probe)
        # rather than the contents. The detail is blank for the same reason --
        # "hasattr probe" told the reader nothing they could act on. The
        # per-row "not on this type" survives, because that one is a fact
        # about their node.
        section = self._section("EXPRESSIONS", "")
        for label, probe in TIER_PROBES:
            has = hasattr(self._py_node, probe)
            regions = by_kind.get("expr_%s" % label.lower()) or []
            region = regions[0] if regions else None
            if not has:
                # The one thing a tab strip cannot say: this node has no such
                # tier, and here is why.
                row = self._row(section, label, "", "not on this type")
                row.setDisabled(True)
                row.setToolTip(_COL_SYMBOL, "No %s on %s" % (
                    probe, type(self._py_node).__name__))
                continue
            if region is None:
                self._row(section, label, "tier", "empty",
                          key="tier.%s" % label.lower())
            else:
                n = region["end"] - region["start"] + 1
                # Carries its REGION, so keyForRegion can find this row when
                # the API view reports a click on the folded rail. The reverse
                # lookup matches on the stored region's (kind, start, end);
                # with no payload there was nothing to match, and an
                # expression was the one managed block that highlighted
                # nothing. It went unnoticed while the rail teleported to the
                # tab instead, which lit the row on the way past.
                #
                # select() never reads this: a "tier." key short-circuits to
                # its tab well before regionForKey is consulted.
                self._row(section, label, "tier", _lines(n),
                          key="tier.%s" % label.lower(), payload=region)

    def _set_total(self, regions) -> None:
        """Put the bake's length in the title bar.

        This was a DOCUMENT section whose only row was the file itself. It read
        as noise: a category containing one entry, naming the document that
        every other row is already a part of. The NUMBER is worth keeping and
        belongs to the pane, so it moves to the pane's title.

        Same measurement as before -- the last line any region reaches, folds
        and all -- so the count does not change, only where it is shown.
        """
        total = 0
        for r in regions:
            if r["end"] + 1 > total:
                total = r["end"] + 1
        self._total_label.setText(_lines(total) if total else "")

    def _build_module(self, regions) -> None:
        rows = [r for r in regions if r["kind"] in _MODULE_KINDS]
        if not rows:
            # GOL has none; an empty header reads as broken, a stated zero
            # does not.
            section = self._section("MODULE", "module scope")
            empty = self._row(section, "(no module scope)", "", "0 segments")
            empty.setDisabled(True)
            return
        section = self._section("MODULE", "module scope")
        for r in rows:
            name = r.get("label") or r["kind"]
            kind = r.get("symbol_kind") or ""
            meta = self._span_meta(r)
            row = self._row(section, name, kind, meta,
                            key="module.%s" % name, payload=r)
            row.setToolTip(_COL_SYMBOL, self._where(r))
            if r["kind"] == "imports_hoisted":
                row.setText(_COL_KIND, "%s generated" % _LOCK)
                row.setText(_COL_META, "hoisted")
                row.setToolTip(
                    _COL_SYMBOL,
                    "Hoisted from your Methods source so the baked members "
                    "resolve their globals.")

    def _build_class(self, by_kind) -> None:
        decl = (by_kind.get("class_decl") or [None])[0]
        title = "CLASS" if decl is None else "CLASS · %s" % decl["label"]
        section = self._section(title, "")
        if decl is not None:
            base = decl.get("base") or ""
            row = self._row(section, "class %s" % decl["label"],
                            "%s class" % _LOCK, "base %s" % base,
                            key="class.decl", payload=decl)
            if base and base == decl["label"]:
                # The real wart J3 draws rather than hides: no _pyClass stamped,
                # so the bake emits `class MPyFile(MPyFile):`.
                row.setText(_COL_META, "⚠ unstamped")
                row.setToolTip(
                    _COL_SYMBOL,
                    "This node has no _pyClass stamped, so the baked class "
                    "name equals its base. Set it on the Identity tab.")
        build = (by_kind.get("build_signature") or [None])[0]
        if build is not None:
            self._row(section, "build()", "%s managed" % _LOCK, "classmethod",
                      key="class.build", payload=build)
        for kind, label, unit in (
                ("attrs_in", "Inputs", "attrs"),
                ("attrs_out", "Outputs", "attrs"),
                ("vars", "Variables", "declared")):
            region = (by_kind.get(kind) or [None])[0]
            if region is None:
                continue
            self._row(section, label, "%s managed" % _LOCK,
                      "%s %s" % (region.get("count", 0), unit),
                      key="class.%s" % kind, payload=region)

    def _build_members(self, regions) -> None:
        """SETUP / COMMANDS / DEMOS / TESTS get their own sections, each row
        carrying the run affordance the Methods outline used to own. Plain
        methods stay under CLASS MEMBERS."""
        members = [r for r in regions if r["kind"] == "method_member"]
        warnings = [r for r in regions if r["kind"] == "method_warning"]
        for role, title in _MEMBER_SECTIONS:
            rows = [r for r in members if r.get("symbol_kind") == role]
            if not rows:
                continue
            section = self._section(title, "")
            for r in rows:
                row = self._row(section, r["label"], "%s %s" % (
                    _RUN, r.get("run_kind") or role), self._span_meta(r),
                    key="member.%s" % r["label"], payload=r)
                row.setToolTip(
                    _COL_SYMBOL, "Right-click to run · %s" % self._where(r))
        plain = [r for r in members
                 if r.get("symbol_kind") not in dict(_MEMBER_SECTIONS)]
        if plain or warnings:
            section = self._section("CLASS MEMBERS", "")
            for r in plain:
                self._row(section, r["label"], r.get("symbol_kind") or "method",
                          self._span_meta(r), key="member.%s" % r["label"],
                          payload=r)
            for r in warnings:
                # A def the bake REFUSED. Silence here is how a member goes
                # missing from a baked .py without anyone noticing.
                row = self._row(section, r["label"], "⚠ not baked", "")
                row.setDisabled(True)
                row.setToolTip(
                    _COL_SYMBOL,
                    "The bake skipped this def -- it shadows a generated or "
                    "inherited name. See the warning comment in the API view.")

    def _build_blessed(self) -> None:
        """Framework commands this node TYPE can have and does not yet carry.

        The one section that cannot come from the region map: an offer is not in
        the source, so it bakes to nothing. Sourced from the same
        ``outline_model`` helper the Methods outline used, so the offers and
        their used/unused filtering are unchanged."""
        offers = self._template_offers()
        if not offers:
            return
        section = self._section("BLESSED", "right-click to add")
        for oit in offers:
            # A framework skeleton names a DECORATOR ("@maya_test"); a per-type
            # offer names a COMMAND, which reads as a call.
            decorator = oit.name.startswith("@") or oit.name.startswith("def ")
            row = self._row(section, oit.name if decorator else "%s()" % oit.name,
                            "framework" if decorator else "template", "",
                            payload=oit)
            # An OFFER, not code: nothing to jump to and nothing to run, so the
            # row is inert exactly as it was in the Methods outline. itemAt()
            # still reaches a disabled row, so the context menu works.
            row.setDisabled(True)
            row.setToolTip(
                _COL_SYMBOL,
                getattr(oit.template, "doc", None)
                or "Right-click to add this command.")

    def _template_offers(self):
        """The framework's blessed decorators, then any PLAIN command this node
        TYPE offers and the buffer does not already carry.

        The per-type offers go through ``build_outline`` so their used/unused
        filtering is the same one the Methods outline applied -- a template
        whose def is already in the buffer under a renamed command must not
        re-appear. The framework skeletons carry no such identity (a node may
        hold any number of commands), so they are always offered.
        """
        out = []
        try:
            from mpynode._common.node_setups import framework_templates

            out.extend(_Offer(t) for t in framework_templates())
        except Exception:  # noqa: BLE001
            pass
        try:
            from mpynode._common.methods.outline_model import build_outline

            native = getattr(self._py_node, "NATIVE_TYPE", None)
            src = ""
            if hasattr(self._py_node, "get_methods_source"):
                src = self._py_node.get_methods_source() or ""
            items = build_outline(src, native) or []
            out.extend(o for o in items
                       if o.template is not None and not o.is_used)
        except Exception:  # noqa: BLE001
            pass
        return out

    def _build_variables(self, by_kind=None) -> None:
        section = self._section("VARIABLES", "declared on the node")
        try:
            names = list(self._py_node.get_variable_names() or [])
        except Exception:  # noqa: BLE001
            names = []
        vars_region = ((by_kind or {}).get("vars") or [None])[0]
        var_lines = (vars_region or {}).get("var_lines") or {}
        for name in names:
            row = self._row(section, name, "persistent", "")
            row.setData(_COL_SYMBOL, Qt.UserRole, "var.%s" % name)
            offset = var_lines.get(name)
            if vars_region is not None and offset is not None:
                # Its OWN line in the bake, so a click locates it the way a
                # member row locates its def. keyForRegion matches on (kind,
                # start, end); a one-line span inside the vars block is this
                # variable's alone, so a click on the whole block still lands
                # on the CLASS > Variables row, not here.
                line = int(vars_region["start"]) + int(offset)
                row.setData(_COL_SYMBOL, Qt.UserRole + 1,
                            {"kind": "vars", "start": line, "end": line,
                             "label": name, "editable": False, "owner": None})
            row.setToolTip(
                _COL_SYMBOL,
                "Declared on the node. Click: its line in the API view. "
                "Double-click: the Variables tab, where the value lives.")
        if not names:
            # Honest rather than blank: the bake gates the block on
            # `if var_names:`, so a node with none emits nothing at all, and an
            # empty panel with no explanation reads as broken.
            empty = self._row(section, "(none declared)", "", "")
            empty.setDisabled(True)
            empty.setToolTip(
                _COL_SYMBOL,
                "This node declares no persistent variables, so the bake "
                "emits no add_variable() calls.")

    @staticmethod
    def _span_meta(region) -> str:
        n = region["end"] - region["start"] + 1
        return _lines(n)

    @staticmethod
    def _where(region) -> str:
        """Both line numbers, because they disagree and both matter: the baked
        one is what the API view shows, the Methods one is what you edit."""
        text = "baked line %d" % (region["start"] + 1)
        src_line = region.get("src_line")
        if src_line:
            text += " · Methods line %d" % src_line
        return text

    # -- activation --------------------------------------------------------

    def _on_item_clicked(self, item, _column) -> None:
        """Single click: LOCATE -- the host scrolls the API view to the row's
        line and stays there. Every row, the tiers and the variables included;
        this pane is the map of the baked file, and a click on the map shows
        the place, it does not leave the map."""
        key = item.data(_COL_SYMBOL, Qt.UserRole)
        if not key:
            return
        self.locateRequested.emit(key)

    def _on_item_activated(self, item, _column) -> None:
        """Double-click / Enter: GO EDIT -- the tier tab, the Variables tab
        (where the data lives), the Attributes tab; a member or module row has
        no other home than the baked file, so it scrolls there like a click."""
        key = item.data(_COL_SYMBOL, Qt.UserRole)
        if not key:
            return
        if key.startswith("var."):
            self.variableActivated.emit(key[4:])
            return
        self.selectRequested.emit(key)

    def _on_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return
        payload = item.data(_COL_SYMBOL, Qt.UserRole + 1)
        if payload is None:
            return
        template = getattr(payload, "template", None)
        if template is not None:
            self._template_menu(pos, payload)
            return
        run_kind = payload.get("run_kind") if hasattr(payload, "get") else None
        if not run_kind:
            return
        menu = QMenu(self._tree)
        act = menu.addAction("Run")
        exec_ = getattr(menu, "exec_", None) or menu.exec
        if exec_(self._tree.viewport().mapToGlobal(pos)) is act:
            self.runRequested.emit(
                run_kind, payload.get("run_name") or payload.get("label") or "")

    def _template_menu(self, pos, oit) -> None:
        """A template row is an OFFER: there is nothing to Run, so the menu puts
        the command's source INTO the buffer (or the clipboard). Unchanged from
        the Methods outline this replaces, including leaving the buffer DIRTY --
        the pasted ``name=`` is a default the user must change before committing
        (two node types shipping one plain command name is refused at
        mega-compile)."""
        source = (getattr(oit.template, "source", "") or "").strip("\n")
        if not source:
            return
        menu = QMenu(self._tree)
        insert_act = menu.addAction("Insert into Script")
        copy_act = menu.addAction("Copy Template")
        exec_ = getattr(menu, "exec_", None) or menu.exec
        chosen = exec_(self._tree.viewport().mapToGlobal(pos))
        if chosen is insert_act:
            self.insertTemplateRequested.emit(source)
        elif chosen is copy_act:
            self._copy(source)

    @staticmethod
    def _copy(source: str) -> None:
        # qt_wrapper deliberately does NOT export QApplication -- importing it
        # perturbs Qt platform init -- so lazy-import QGuiApplication from the
        # bound binding. clipboard() is static on PySide2/6.
        try:
            try:
                from PySide6.QtGui import QGuiApplication
            except ImportError:
                from PySide2.QtGui import QGuiApplication

            clip = QGuiApplication.clipboard()
            if clip is not None:
                clip.setText(source)
        except Exception:  # noqa: BLE001
            pass

    # -- selection, the other half of "one key, two projections" -----------

    def setCurrentKey(self, key: str) -> bool:
        """Light the row for ``key``. The return leg of the tab strip: selecting
        a tab lights its row, so the two never disagree about where you are."""
        item = self._item_for_key(key)
        if item is None:
            self._tree.setCurrentItem(None)
            return False
        self._tree.setCurrentItem(item)
        return True

    def currentKey(self):
        item = self._tree.currentItem()
        if item is None:
            return None
        return item.data(_COL_SYMBOL, Qt.UserRole)

    def _item_for_key(self, key):
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(_COL_SYMBOL, Qt.UserRole) == key:
                    return child
        return None

    def regionForKey(self, key):
        item = self._item_for_key(key)
        if item is None:
            return None
        return item.data(_COL_SYMBOL, Qt.UserRole + 1)

    def keyForRegion(self, region):
        """The inverse of :meth:`regionForKey`: which row names this region.

        Matched on ``(kind, start, end)``, NOT by identity: a payload stored
        with ``setData`` comes back through QVariant as an equal-valued COPY,
        so ``stored is region`` is False even for the very dict that was put
        there. The triple is unique -- two regions sharing all three would be
        the same region -- and stable, because the dicts carry BAKE line
        numbers that no keystroke rewrites.

        Deliberately a scan of the rows rather than a second kind -> key
        table: one mapping, walked in both directions, cannot drift.
        """
        if not isinstance(region, dict):
            return None
        want = (region.get("kind"), region.get("start"), region.get("end"))
        if want[0] is None:
            return None
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                stored = child.data(_COL_SYMBOL, Qt.UserRole + 1)
                if not isinstance(stored, dict):
                    continue
                if (stored.get("kind"), stored.get("start"),
                        stored.get("end")) == want:
                    return child.data(_COL_SYMBOL, Qt.UserRole)
        return None

    # -- introspection, for the host and for tests ------------------------

    def sectionTitles(self):
        return [self._tree.topLevelItem(i).text(_COL_SYMBOL)
                for i in range(self._tree.topLevelItemCount())]

    def rowsUnder(self, title):
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            if top.text(_COL_SYMBOL) == title:
                return [(top.child(j).text(_COL_SYMBOL),
                         top.child(j).text(_COL_META),
                         top.child(j).isDisabled())
                        for j in range(top.childCount())]
        return []

    def keysUnder(self, title):
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            if top.text(_COL_SYMBOL) == title:
                return [top.child(j).data(_COL_SYMBOL, Qt.UserRole)
                        for j in range(top.childCount())]
        return []
