"""NDPreferencesDialog \u2014 modal preferences UI.

Sections:
  * Editor: font family + size
  * Add Attribute: default time auto-connect
  * Connect dialog: default Show all attrs
  * Locations: read-only map of every path MPyNode resolves (and which of
    env / preference / mpynode.ini / default supplied it), plus the one
    overridable path -- the port cache

Buttons:
  * Save \u2014 persist + close
  * Cancel \u2014 discard + close
  * Reset Defaults \u2014 wipe to DEFAULT_PREFS

All values flow through ``mpynode.ui.preferences.set_pref`` so listeners
(e.g. live editor font updates) fire on Save.
"""

from __future__ import annotations

import os

from mpynode.ui import preferences
from mpynode.ui.qt_wrapper import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedLayout,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _writable_label(path: str) -> str:
    """"yes" / "no" for the Locations table, by ATTEMPTING a write.

    ``os.access`` is not usable here: on macOS it reports success for a
    directory that then raises ``PermissionError`` under App Management
    protection (a dir created by another signed app), which is exactly the
    case this column exists to surface. Walks up to the nearest existing
    ancestor, since a not-yet-created path is fine if its parent is writable."""
    probe = path
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            return "?"
        probe = parent
    test = os.path.join(probe, ".mpynode_write_probe")
    try:
        with open(test, "w"):
            pass
        os.remove(test)
        return "yes"
    except Exception:  # noqa: BLE001
        return "NO"


# Known editors -> open-in-editor command template. A preset fills the command
# line edit; "Custom..." leaves it for hand-editing.
_EDITOR_PRESETS = [
    # "Auto-detect" clears the field (empty = detect at launch); the default.
    ("Auto-detect", ""),
    ("VS Code", "code --goto {file}:{line}"),
    ("Cursor", "cursor --goto {file}:{line}"),
    ("PyCharm", "pycharm --line {line} {file}"),
    ("Sublime", "subl {file}:{line}"),
    ("gvim", "gvim +{line} {file}"),
    ("Notepad++", "notepad++ -n{line} {file}"),
    ("WingIDE", "wing {file}:{line}"),
    ("Custom…", ""),
]


class NDPreferencesDialog(QDialog):
    """Modal preferences dialog. Cache values until Save."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Node Designer Preferences")
        self.setModal(True)
        self.resize(560, 440)
        # Don't let the user shrink it below its open size when resizing smaller.
        self.setMinimumSize(560, 440)

        # Snapshot the current prefs so Cancel reverts cleanly.
        self._original = preferences.all_prefs()

        self._build_ui()
        self._load_into_widgets()
        self._wire_signals()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setSpacing(10)

        # Category sidebar + stacked pages: one short page per section, so the
        # dialog stays compact as preferences grow.
        body = QHBoxLayout()
        body.setSpacing(10)
        self._category_list = QListWidget(self)
        self._category_list.setFixedWidth(140)
        self._category_list.setSpacing(1)
        body.addWidget(self._category_list)
        self._pages_host = QWidget(self)
        self._pages      = QStackedLayout(self._pages_host)
        body.addWidget(self._pages_host, stretch=1)
        outer.addLayout(body, stretch=1)

        # ---- Editor ------------------------------------------------------
        ed          = self._add_page("Editor")
        editor_grid = QGridLayout()
        editor_grid.setVerticalSpacing(4)
        editor_grid.setHorizontalSpacing(6)
        editor_grid.addWidget(QLabel("Font family:"), 0, 0)
        self._font_family_combo = QComboBox()
        # "Maya default" first, as on the Fonts page. For the editor it is the
        # EMPTY preference: the platform's own monospace -- Consolas on
        # Windows, Monaco on macOS (preferences.default_editor_font_family),
        # which stays the shipped default. Then installed fixed-pitch families
        # only. The list used to be eight hard-coded names, half of which no
        # given machine has, and the combo accepted anything typed -- so a
        # saved family could name a font Qt then silently substituted.
        # Non-editable: what is offered exists.
        self._font_family_combo.addItem(preferences.UI_FONT_DEFAULT_LABEL)
        for fam in preferences.installed_monospace_families():
            self._font_family_combo.addItem(fam)
        if self._font_family_combo.count() == 1:  # headless: no font database
            self._font_family_combo.addItem(
                preferences.default_editor_font_family())
        self._font_family_combo.setToolTip(
            "'%s' is the platform's own monospace: %s here."
            % (preferences.UI_FONT_DEFAULT_LABEL,
               preferences.default_editor_font_family()))
        editor_grid.addWidget(self._font_family_combo, 0, 1)
        editor_grid.addWidget(QLabel("Font size (pt):"), 1, 0)
        self._font_size_edit = QLineEdit()
        self._font_size_edit.setMaximumWidth(80)
        editor_grid.addWidget(self._font_size_edit, 1, 1, alignment=Qt.AlignLeft)
        # {file}/{line} are substituted at launch. The line edit is the source
        # of truth; the presets combo only fills it in.
        editor_grid.addWidget(QLabel("Open-in-editor command:"), 2, 0)
        self._external_editor_edit = QLineEdit()
        self._external_editor_edit.setToolTip(
            "Command run to open a file in your external editor. "
            "{file} and {line} are replaced with the target path and "
            "1-based line number. Leave blank to auto-detect an installed "
            "editor (Cursor / VS Code / VSCodium / Sublime / PyCharm)."
        )
        self._external_editor_presets = QComboBox()
        for label, _cmd in _EDITOR_PRESETS:
            self._external_editor_presets.addItem(label)
        self._external_editor_presets.setToolTip(
            "Pick a known editor to fill in the command above."
        )
        # Two columns, like the Fonts page: the command edit takes column 1
        # and its presets get their own row under it. A third column for the
        # presets squeezed the family combo above to ~120 px (its popup
        # truncated the family names) and clipped the labels in column 0.
        editor_grid.addWidget(self._external_editor_edit, 2, 1)
        editor_grid.addWidget(QLabel("Preset:"), 3, 0)
        editor_grid.addWidget(self._external_editor_presets, 3, 1,
                              alignment=Qt.AlignLeft)
        editor_grid.setColumnStretch(1, 1)
        ed.addLayout(editor_grid)
        ed.addStretch(1)

        # ---- New Nodes ---------------------------------------------------
        # --- Fonts -------------------------------------------------------
        # The editor size stays on the Editor page beside its family, where it
        # has always been. Everything ELSE -- panels, trees, tab bars, the
        # identity strip, the AI Assistant -- follows one UI font, family and
        # size, from this page. (Two separate sizes lived here once; they
        # drifted to 20 and 15 while the icons and tab bars beside them stayed
        # put.)
        fo         = self._add_page("Fonts")
        fonts_grid = QGridLayout()
        fonts_grid.setVerticalSpacing(4)
        fonts_grid.setHorizontalSpacing(6)
        fonts_grid.addWidget(QLabel("UI font family:"), 0, 0)
        self._ui_font_family_combo = QComboBox()
        # "Maya default" first: the empty preference, i.e. follow Maya's own
        # UI font. Then every family this machine can render -- not only
        # fixed-pitch ones; a panel is prose and table rows, not code.
        self._ui_font_family_combo.addItem(preferences.UI_FONT_DEFAULT_LABEL)
        for fam in preferences.installed_font_families():
            self._ui_font_family_combo.addItem(fam)
        self._ui_font_family_combo.setToolTip(
            "Panels, trees, tab bars, the identity strip and the AI "
            "Assistant. '%s' follows Maya's own UI font."
            % preferences.UI_FONT_DEFAULT_LABEL)
        fonts_grid.addWidget(self._ui_font_family_combo, 0, 1)
        fonts_grid.addWidget(QLabel("UI font size (pt):"), 1, 0)
        self._ui_font_size_edit = QLineEdit()
        self._ui_font_size_edit.setMaximumWidth(80)
        self._ui_font_size_edit.setToolTip(
            "%d-%d. The Scene tab's type discs and C++ / pause chips scale "
            "with it." % (preferences.FONT_SIZE_MIN,
                          preferences.UI_FONT_SIZE_MAX))
        fonts_grid.addWidget(self._ui_font_size_edit, 1, 1,
                             alignment=Qt.AlignLeft)
        fonts_grid.setColumnStretch(1, 1)
        fo.addLayout(fonts_grid)
        _fonts_note = QLabel(
            "Applies immediately — no restart. The code editors have their "
            "own family and size on the Editor page.")
        _fonts_note.setWordWrap(True)
        fo.addWidget(_fonts_note)
        fo.addStretch(1)

        nn     = self._add_page("New Nodes")
        nn_row = QHBoxLayout()
        nn_row.addWidget(QLabel("New node code tabs:"))
        self._new_node_mode_combo = QComboBox()
        # (display label, persisted value) pairs.
        self._NEW_NODE_MODE_OPTIONS = (
            ("Headers (explain each tab)", "headers"),
            ("None (blank tabs)", "none"),
        )
        for label, _value in self._NEW_NODE_MODE_OPTIONS:
            self._new_node_mode_combo.addItem(label)
        self._new_node_mode_combo.setToolTip(
            "What a fresh node's empty code tabs (Init, Compute, Viewport, "
            "OSL, Methods) get when you create it:\n"
            "  Headers -- each empty tab is prefilled with a commented header "
            "explaining what belongs in it (default).\n"
            "  None -- blank tabs.\n"
            "Display-only: headers are never written to the node.\n"
            "(For a fully-working example node, use 'New from Template...'.)"
        )
        nn_row.addWidget(self._new_node_mode_combo, stretch=1)
        nn.addLayout(nn_row)
        # Template search paths -- roots scanned by "New from Template...".
        nn.addWidget(QLabel("Template search paths:"))
        paths_row                 = QHBoxLayout()
        self._template_paths_list = QListWidget()
        self._template_paths_list.setToolTip(
            "Folders scanned (recursively) by 'New from Template...' for "
            "template folders. The bundled templates/ dir is the default; add "
            "shared studio roots here."
        )
        paths_row.addWidget(self._template_paths_list, stretch=1)
        paths_btns                      = QVBoxLayout()
        self._template_paths_add_btn    = QPushButton("Add...")
        self._template_paths_remove_btn = QPushButton("Remove")
        paths_btns.addWidget(self._template_paths_add_btn)
        paths_btns.addWidget(self._template_paths_remove_btn)
        paths_btns.addStretch(1)
        paths_row.addLayout(paths_btns)
        nn.addLayout(paths_row, stretch=1)
        nn.addStretch(1)

        # ---- Node Designer -----------------------------------------------
        nd      = self._add_page("Node Designer")
        tab_row = QHBoxLayout()
        tab_row.addWidget(QLabel("Selected tab emphasis:"))
        self._script_tab_style_combo = QComboBox()
        # Display label -> persisted value. Values MUST match
        # preferences.VALID_SCRIPT_TAB_STYLES.
        self._SCRIPT_TAB_STYLE_OPTIONS = (
            ("Boxed cells (default)", "boxed"),
            ("Highlight fill", "fill"),
            ("Underline accent", "underline"),
            ("Gray recede (no accent)", "gray"),
            ("Top-edge accent", "top_accent"),
            ("Classic solid (old look)", "classic"),
        )
        for label, _value in self._SCRIPT_TAB_STYLE_OPTIONS:
            self._script_tab_style_combo.addItem(label)
        self._script_tab_style_combo.setToolTip(
            "How the SELECTED Expressions/Script tab stands out in the Node "
            "Designer editor. Changing this updates open editors immediately, "
            "so you can try each and pick a favourite."
        )
        tab_row.addWidget(self._script_tab_style_combo, stretch=1)
        nd.addLayout(tab_row)
        nd.addStretch(1)

        # ---- AI Optimization ---------------------------------------------
        ai                           = self._add_page("AI Optimization")
        self._optimize_timeout_check = QCheckBox("Cap each AI optimize call")
        self._optimize_timeout_check.setToolTip(
            "Bounds ONE model call -- a single agent session, or one whole-file "
            "rewrite/fix reply on a provider with no agent mode. It does NOT "
            "bound a round, a node, the optimize phase or the compile: each node "
            "runs 2 optimize rounds by default, and a round may spend up to 2 "
            "more fix calls, every one of them getting the full cap again. "
            "Parity and benchmark runs have their own separate limits; the C++ "
            "compile has none. The compile as a whole is unbounded -- only "
            "Cancel stops it: on a CLI provider that kills the call outright, "
            "on an API provider it takes effect between retries, rounds and "
            "nodes but cannot abort a reply already being read. A killed call "
            "is not thrown away: whatever the "
            "agent had already written to disk is still compiled, parity-checked "
            "and benchmarked. When OFF, each call runs unbounded."
        )
        ai.addWidget(self._optimize_timeout_check)
        ai_grid = QGridLayout()
        ai_grid.setVerticalSpacing(4)
        ai_grid.setHorizontalSpacing(6)
        self._optimize_timeout_label = QLabel("Per AI call timeout (seconds):")
        ai_grid.addWidget(self._optimize_timeout_label, 0, 0)
        self._optimize_timeout_edit = QLineEdit()
        self._optimize_timeout_edit.setFixedWidth(80)
        self._optimize_timeout_edit.setToolTip(
            "Wall-clock budget (seconds) for ONE AI optimize call when the cap "
            "is enabled -- not for the round, the node or the compile. Range "
            "10-86400 (24h). Default 2400 (40 min)."
        )
        ai_grid.addWidget(
            self._optimize_timeout_edit, 0, 1, alignment=Qt.AlignLeft)
        # Grey the seconds field AND its caption when the timeout is disabled,
        # so it reads as having no effect. Initial state in _load_into_widgets.
        self._optimize_timeout_check.toggled.connect(
            self._optimize_timeout_edit.setEnabled)
        self._optimize_timeout_check.toggled.connect(
            self._optimize_timeout_label.setEnabled)
        ai_grid.addWidget(QLabel("Max response tokens (API):"), 1, 0)
        self._optimize_max_tokens_edit = QLineEdit()
        self._optimize_max_tokens_edit.setFixedWidth(80)
        self._optimize_max_tokens_edit.setToolTip(
            "API providers only. Without a tool-using CLI the optimizer must "
            "return the WHOLE .cpp in one reply, so this ceiling has to hold "
            "the entire file or the compile skips the node and says so. Range "
            "1024-200000. Default 64000. Does not affect CLI providers, and "
            "does not affect the porter, which only returns the compute body."
        )
        ai_grid.addWidget(
            self._optimize_max_tokens_edit, 1, 1, alignment=Qt.AlignLeft)
        ai_grid.setColumnStretch(2, 1)
        ai.addLayout(ai_grid)
        ai.addStretch(1)

        # ---- Add Attribute -----------------------------------------------
        ap = self._add_page("Add Attribute")
        self._addattr_time_check = QCheckBox(
            "Default: Auto-connect time inputs to time1.outTime"
        )
        ap.addWidget(self._addattr_time_check)
        ap.addStretch(1)

        # ---- Connect -----------------------------------------------------
        cn = self._add_page("Connect")
        self._hide_pivots_check = QCheckBox(
            "Default: Hide pivots & limits (rotatePivot* / scalePivot* / *Limit*)"
        )
        cn.addWidget(self._hide_pivots_check)
        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Default sort mode:"))
        self._sort_mode_combo = QComboBox()
        # (display label, persisted value) pairs.
        self._SORT_MODE_OPTIONS = (
            ("Selection order", "selection"),
            ("Natural sort \u2191", "natural_asc"),
            ("Natural sort \u2193", "natural_desc"),
            ("Type alpha \u2191", "type_alpha_asc"),
            ("Type alpha \u2193", "type_alpha_desc"),
            ("Type category (compounds first)", "type_category"),
        )
        for label, _value in self._SORT_MODE_OPTIONS:
            self._sort_mode_combo.addItem(label)
        sort_row.addWidget(self._sort_mode_combo, stretch=1)
        cn.addLayout(sort_row)
        cn.addStretch(1)

        # ---- Watch -------------------------------------------------------
        wt = self._add_page("Watch")
        self._watch_suppress_check = QCheckBox(
            "Suppress scientific notation in numpy arrays"
        )
        self._watch_suppress_check.setToolTip(
            "Forwards np.array2string(suppress_small=True) so a 4x4 matrix "
            "of plain numbers renders as plain numbers (no 1.0e-9 noise)."
        )
        wt.addWidget(self._watch_suppress_check)
        self._watch_threshold_inf_check = QCheckBox(
            "Show full arrays (no element truncation)"
        )
        self._watch_threshold_inf_check.setToolTip(
            "Forwards np.array2string(threshold=np.inf). When OFF (default), "
            "large arrays are summarized with '...' to keep the snapshot "
            "plug small and the UI tree row height bounded."
        )
        wt.addWidget(self._watch_threshold_inf_check)
        self._round_check = QCheckBox("Round displayed numpy values")
        self._round_check.setToolTip(
            "When ON, numpy array values shown in the Watch + Variables "
            "tabs are rounded to the digit count below for readability. "
            "When OFF, full float precision is shown. (Display only -- the "
            "stored value is never rounded.)"
        )
        wt.addWidget(self._round_check)
        self._animate_gif_check = QCheckBox("Animate GIF images")
        self._animate_gif_check.setToolTip(
            "When ON, a stored var holding an animated GIF plays in the "
            "Value column (Watch + Variables tabs) instead of showing a "
            "static first frame. Continuous repaint -- turn off to keep it "
            "still."
        )
        wt.addWidget(self._animate_gif_check)
        self._render_waveform_check = QCheckBox(
            "Render audio (WAV/PCM) as a waveform"
        )
        self._render_waveform_check.setToolTip(
            "When ON, a stored var holding audio bytes -- a WAV container "
            "(auto-detected) or raw uint8-mono PCM (via the right-click "
            "'Show as Waveform' toggle) -- renders as a waveform in the Value "
            "column. Click to play, drag to scrub (when QtMultimedia is "
            "available). Off -> audio bytes show their text repr."
        )
        wt.addWidget(self._render_waveform_check)

        # Numeric fields share one grid so the value boxes line up.
        wt_grid = QGridLayout()
        wt_grid.setVerticalSpacing(4)
        wt_grid.setHorizontalSpacing(6)
        wt_grid.addWidget(QLabel("Rounding digits:"), 0, 0)
        self._round_digits_edit = QLineEdit()
        self._round_digits_edit.setFixedWidth(60)
        wt_grid.addWidget(self._round_digits_edit, 0, 1, alignment=Qt.AlignLeft)
        wt_grid.addWidget(QLabel("Image preview size (px):"), 1, 0)
        self._img_preview_edit = QLineEdit()
        self._img_preview_edit.setFixedWidth(60)
        self._img_preview_edit.setToolTip(
            "Source size a PIL-image variable's thumbnail is built at "
            "(e.g. 256 or 512). Qt scales it to the column width; larger "
            "= crisper when the column is wide. Range 32-2048."
        )
        wt_grid.addWidget(self._img_preview_edit, 1, 1, alignment=Qt.AlignLeft)
        wt_grid.addWidget(QLabel("Watch refresh rate (ms):"), 2, 0)
        self._watch_refresh_edit = QLineEdit()
        self._watch_refresh_edit.setFixedWidth(60)
        self._watch_refresh_edit.setToolTip(
            "How often (milliseconds) the Watch tab re-reads live values "
            "while enabled. Lower = snappier updates (more CPU); higher = "
            "lazier. Range 16-5000 (e.g. 80 ~= 12 fps)."
        )
        wt_grid.addWidget(self._watch_refresh_edit, 2, 1, alignment=Qt.AlignLeft)
        wt_grid.addWidget(QLabel("Watch max value size (KB):"), 3, 0)
        self._watch_max_kb_edit = QLineEdit()
        self._watch_max_kb_edit.setFixedWidth(60)
        self._watch_max_kb_edit.setToolTip(
            "Largest size (kilobytes) a single watched value is displayed at. "
            "Bigger values (e.g. a full mesh-point array) are replaced with a "
            "'too large to display' marker so they can't bloat the snapshot or "
            "freeze the Watch tab. Values under the limit keep their real type."
        )
        wt_grid.addWidget(self._watch_max_kb_edit, 3, 1, alignment=Qt.AlignLeft)
        wt_grid.setColumnStretch(2, 1)
        wt.addLayout(wt_grid)
        wt.addStretch(1)

        # ---- Export ------------------------------------------------------
        ex = self._add_page("Export")
        self._export_max_compress_check = QCheckBox(
            "Maximum compression on .mpn export (lzma)"
        )
        self._export_max_compress_check.setToolTip(
            "OFF (default): zlib -- fast, good ratio. ON: lzma -- smaller "
            "file, ~10x slower to write. The OS-native save dialog is used "
            "either way."
        )
        ex.addWidget(self._export_max_compress_check)
        ex.addStretch(1)

        # ---- Metadata ----------------------------------------------------
        md = self._add_page("Metadata")
        md.addWidget(QLabel(
            "Global DEFAULTS for new nodes' Info. Per-node values always win; "
            "these fill any field a node leaves blank (incl. at compile time, "
            "so a studio can set license/author once)."))
        md_grid = QGridLayout()
        md_grid.setVerticalSpacing(4)
        md_grid.setHorizontalSpacing(6)
        md_grid.addWidget(QLabel("Author(s):"), 0, 0)
        self._meta_authors_edit = QPlainTextEdit()
        self._meta_authors_edit.setFixedHeight(56)
        self._meta_authors_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._meta_authors_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded)
        self._meta_authors_edit.setToolTip(
            "One \"Name <email>\" per line (also split on ';').")
        md_grid.addWidget(self._meta_authors_edit, 0, 1)
        md_grid.addWidget(QLabel("Version:"), 1, 0)
        self._meta_version_edit = QLineEdit()
        md_grid.addWidget(self._meta_version_edit, 1, 1)
        md_grid.addWidget(QLabel("License:"), 2, 0)
        # Multi-line + EXPANDING: holds the whole legal block -- a copyright
        # line, a copyleft or CC notice, an SPDX id, or short-form license text
        # -- filling (and scrolling) the space below the other fields.
        self._meta_license_edit = QPlainTextEdit()
        self._meta_license_edit.setMinimumHeight(60)
        self._meta_license_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # NoWrap here for the same reason as the Node Info dialog: this text
        # feeds the very same banner, so a soft wrap would show a layout the
        # baked header cannot reproduce.
        self._meta_license_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._meta_license_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded)
        self._meta_license_edit.setToolTip(
            "The whole legal block, verbatim: a copyright line, a copyleft or\n"
            "Creative Commons notice, an SPDX id (e.g. MIT), or full terms.\n"
            "Emitted into the baked header exactly as typed, unlabelled.")
        md_grid.addWidget(self._meta_license_edit, 2, 1)
        md_grid.setColumnStretch(1, 1)
        # License row absorbs the vertical slack instead of an addStretch.
        md_grid.setRowStretch(2, 1)
        md.addLayout(md_grid, stretch=1)
        self._meta_bake_header_check = QCheckBox(
            "Include this metadata as a header in baked .py files")
        self._meta_bake_header_check.setToolTip(
            "Writes an author/version/license comment block at the top of\n"
            "File > Bake Node to .py output, above your own header.\n"
            "Compiled (C++) nodes always embed it -- that is also where the\n"
            "plug-in vendor, version and build hash come from.")
        md.addWidget(self._meta_bake_header_check)

        # ---- Advanced (rarely-touched / legacy) --------------------------
        # ---- Locations ----------------------------------------------------
        # A read-only map of where MPyNode reads/writes, plus the ONE path a
        # user may override. The table exists because the resolution is four
        # levels deep (env -> this pref -> mpynode.ini -> built-in default) and
        # nothing else in the UI reveals which level won, or that a location is
        # unwritable -- both of which surface far away as a failed compile.
        loc = self._add_page("Locations")
        loc.addWidget(QLabel(
            "Where MPyNode reads and writes per-user data. Set by your studio "
            "in mpynode.ini;\nthe port cache can be overridden just for you."))
        self._locations_tree = QTreeWidget()
        self._locations_tree.setHeaderLabels(
            ["What", "From", "Writable", "Path"])
        self._locations_tree.setRootIsDecorated(False)
        self._locations_tree.setToolTip(
            "Read-only. 'From' names which level of the resolution supplied "
            "the value: the environment, this preference, the install's "
            "mpynode.ini, or the built-in default."
        )
        loc.addWidget(self._locations_tree, stretch=1)

        loc.addWidget(QLabel("Port cache:"))
        pc_row                = QHBoxLayout()
        self._port_cache_edit = QLineEdit()
        self._port_cache_edit.setPlaceholderText(
            "(blank -- use the studio / built-in default)")
        self._port_cache_edit.setToolTip(
            "Where the AI porter's translated C++ is cached. Safe to point "
            "anywhere writable and safe to delete -- a wrong path only costs a "
            "re-port. Leave blank to fall back to mpynode.ini, then "
            "<home>/port_cache.\n\n"
            "This is the only location with a field here: it is a pure cache. "
            "The data home is deliberately absent, because moving it would "
            "also move the pickle-trust store and the type-id pins baked into "
            "saved scenes."
        )
        pc_row.addWidget(self._port_cache_edit, stretch=1)
        self._port_cache_browse_btn = QPushButton("Browse...")
        self._port_cache_reset_btn  = QPushButton("Reset")
        pc_row.addWidget(self._port_cache_browse_btn)
        pc_row.addWidget(self._port_cache_reset_btn)
        loc.addLayout(pc_row)
        # Explains an override that is being IGNORED -- an env var winning, or a
        # path from another OS. Silently accepting a value that never takes
        # effect is the failure this page exists to prevent.
        self._port_cache_note = QLabel("")
        self._port_cache_note.setWordWrap(True)
        loc.addWidget(self._port_cache_note)

        adv = self._add_page("Advanced")
        self._show_all_check = QCheckBox(
            "Default: Show all attrs (incl. pivots / non-keyable)  \u2014 LEGACY"
        )
        self._show_all_check.setToolTip(
            "This pref no longer affects the Connect dialog. "
            "It's kept here for back-compat with existing prefs files; new "
            "behavior is driven by 'Hide pivots & limits' + 'Default sort mode' "
            "on the Connect page."
        )
        adv.addWidget(self._show_all_check)
        adv.addStretch(1)

        # Select the first category + drive the stack from the sidebar.
        self._category_list.setCurrentRow(0)
        self._category_list.currentRowChanged.connect(self._pages.setCurrentIndex)

        # ------------------------------------------------------------------
        # Buttons row
        # ------------------------------------------------------------------
        btn_row         = QHBoxLayout()
        self._reset_btn = QPushButton("Reset Defaults", self)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch(1)
        self._save_btn = QPushButton("Save", self)
        self._save_btn.setDefault(True)
        self._cancel_btn = QPushButton("Cancel", self)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._cancel_btn)
        outer.addLayout(btn_row)

    def _add_page(self, title: str):
        """Register a sidebar category + create its stacked page, returning
        the page's content layout (with a bold title already added) for the
        caller to populate."""
        self._category_list.addItem(title)
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(4, 0, 4, 4)
        lay.setSpacing(8)
        header = QLabel(title, page)
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        lay.addWidget(header)
        self._pages.addWidget(page)
        return lay

    def _load_into_widgets(self) -> None:
        """Populate widgets from current preferences."""
        saved  = preferences.get_pref("editor_font_family")
        saved  = saved.strip() if isinstance(saved, str) else ""
        family = preferences.resolve_editor_font_family(saved)
        if not saved:
            # The empty preference IS "Maya default" (index 0): the platform
            # monospace, whatever this machine calls it.
            idx = 0
        else:
            idx = self._font_family_combo.findText(family)
            if idx < 0:
                # The resolved family is installed but Qt did not classify it
                # as fixed pitch (or there is no font database): offer it
                # anyway rather than showing a font the user did not choose.
                self._font_family_combo.addItem(family)
                idx = self._font_family_combo.findText(family)
        self._font_family_combo.setCurrentIndex(idx)

        self._font_size_edit.setText(str(preferences.get_pref("editor_font_size", 10)))

        _ui_fam = preferences.resolve_ui_font_family()
        _ui_idx = self._ui_font_family_combo.findText(_ui_fam) if _ui_fam else 0
        self._ui_font_family_combo.setCurrentIndex(max(0, _ui_idx))
        self._ui_font_size_edit.setText(str(preferences.resolve_font_size("ui")))


        # Empty = auto-detect. Show what auto-detect resolves to as placeholder
        # text so a blank field is self-explanatory.
        from mpynode.ui import editor_launch

        self._external_editor_edit.setText(
            preferences.get_pref("external_editor_command", "")
        )
        try:
            detected = editor_launch.detect_default_editor_command()
        except Exception:
            detected = ""
        if detected:
            self._external_editor_edit.setPlaceholderText(
                "Auto-detect: %s" % detected
            )

        cur_mode = preferences.new_node_mode()
        mode_idx = next(
            (i for i, (_l, v) in enumerate(self._NEW_NODE_MODE_OPTIONS)
             if v == cur_mode),
            0,
        )
        self._new_node_mode_combo.setCurrentIndex(mode_idx)
        self._template_paths_list.clear()
        for p in preferences.get_pref(
            "template_search_paths",
            preferences.DEFAULT_PREFS["template_search_paths"],
        ):
            self._template_paths_list.addItem(str(p))

        self._addattr_time_check.setChecked(
            bool(preferences.get_pref("addattr_time_auto_connect", True))
        )
        self._show_all_check.setChecked(
            bool(preferences.get_pref("connect_dialog_show_all_default", False))
        )

        self._hide_pivots_check.setChecked(
            bool(preferences.get_pref("connect_dialog_hide_pivots_default", True))
        )
        cur_sort = preferences.get_pref("connect_dialog_sort_mode_default", "selection")
        cur_idx  = 0
        for i, (_label, value) in enumerate(self._SORT_MODE_OPTIONS):
            if value == cur_sort:
                cur_idx = i
                break
        self._sort_mode_combo.setCurrentIndex(cur_idx)

        cur_tab_style = preferences.script_tab_style()
        tab_idx       = 0
        for i, (_label, value) in enumerate(self._SCRIPT_TAB_STYLE_OPTIONS):
            if value == cur_tab_style:
                tab_idx = i
                break
        self._script_tab_style_combo.setCurrentIndex(tab_idx)
        self._optimize_timeout_check.setChecked(
            bool(preferences.get_pref("optimize_timeout_enabled", True)))
        self._optimize_timeout_edit.setText(
            str(int(preferences.get_pref("optimize_timeout_seconds", 2400)))
        )
        self._optimize_max_tokens_edit.setText(
            str(preferences.resolve_optimize_max_tokens())
        )
        # Reflect the enable state on load (toggled fires only on user change).
        _opt_on = self._optimize_timeout_check.isChecked()
        self._optimize_timeout_edit.setEnabled(_opt_on)
        self._optimize_timeout_label.setEnabled(_opt_on)

        self._watch_suppress_check.setChecked(
            bool(preferences.get_pref("watch_suppress_scientific", True))
        )
        self._watch_threshold_inf_check.setChecked(
            bool(preferences.get_pref("watch_threshold_inf", False))
        )
        self._round_check.setChecked(
            bool(preferences.get_pref("display_round_enabled", True))
        )
        self._round_digits_edit.setText(
            str(int(preferences.get_pref("display_round_digits", 8)))
        )
        self._img_preview_edit.setText(
            str(int(preferences.get_pref("variables_image_preview_px", 256)))
        )
        self._animate_gif_check.setChecked(
            bool(preferences.get_pref("variables_animate_gif", True))
        )
        self._render_waveform_check.setChecked(
            bool(preferences.get_pref("variables_render_waveform", True))
        )
        self._watch_refresh_edit.setText(
            str(int(preferences.get_pref("watch_refresh_ms", 80)))
        )
        self._watch_max_kb_edit.setText(
            str(int(preferences.get_pref("watch_max_value_kb", 64)))
        )
        self._export_max_compress_check.setChecked(
            bool(preferences.get_pref("mpn_export_max_compression", False))
        )

        self._meta_authors_edit.setPlainText(
            str(preferences.get_pref("metadata_default_authors", "") or "")
        )
        self._meta_version_edit.setText(
            str(preferences.get_pref("metadata_default_version", "") or "")
        )
        self._meta_version_edit.setPlaceholderText("1.0 (default if blank)")
        # ``metadata_default_copyright`` was retired when Copyright merged into
        # License. A prefs file written before that still holds the value, so
        # carry it in ABOVE the license text rather than orphaning it. Saving
        # writes only the merged key, so this self-heals on the first save.
        _license = str(preferences.get_pref("metadata_default_license", "") or "")
        _legacy  = str(preferences.get_pref("metadata_default_copyright", "") or "")
        if _legacy.strip():
            _license = ("%s\n%s" % (_legacy.rstrip(), _license) if _license
                        else _legacy.rstrip())
        self._meta_license_edit.setPlainText(_license)
        self._meta_bake_header_check.setChecked(
            bool(preferences.get_pref("metadata_bake_header", True))
        )

        self._port_cache_edit.setText(
            str(preferences.get_pref("port_cache_dir", "") or "")
        )
        self._refresh_locations()

    # ------------------------------------------------------------------
    # Locations page
    # ------------------------------------------------------------------

    def _refresh_locations(self) -> None:
        """Repopulate the read-only table AND the note. Load-time only.

        Deliberately NOT wired to ``textChanged``: the table runs a real write
        probe per row (see :func:`_writable_label`), so rebuilding it per
        keystroke would be six file writes a character. Typing only refreshes
        the note."""
        self._refresh_locations_table()
        self._refresh_port_cache_note()


    def _refresh_locations_table(self) -> None:
        """The read-only resolved-paths table.

        Every value is asked of ``_common.home``, never recomputed here, so the
        page cannot drift from what the rest of MPyNode actually uses."""
        from mpynode._common import bootstrap, home

        self._locations_tree.clear()
        rows = (
            ("Data home",       "home",        "MPYNODE_HOME",
             home.home_dir),
            ("Preferences",     "preferences", "MPYNODE_PREFS",
             home.preferences_path),
            ("Trust store",     "trust_store", "MPYNODE_TRUST_STORE",
             home.trust_store_path),
            ("Type-id pins",    "typeid_pins", "MPYNODE_TYPEID_REGISTRY",
             home.typeid_pins_path),
            ("Port cache",      "port_cache",  "MPYNODE_PORT_CACHE",
             home.port_cache_dir),
            ("Compiled output", "compiled",    "MPYNODE_COMPILED",
             home.compiled_dir),
        )
        for label, key, env, resolver in rows:
            try:
                value = resolver()
            except Exception:
                value = "(unresolved)"
            if os.environ.get(env):
                source = env
            elif key == "port_cache" and preferences.port_cache_dir_pref():
                source = "this preference"
            elif bootstrap.path(key):
                source = "mpynode.ini"
            else:
                source = "default"
            QTreeWidgetItem(self._locations_tree,
                            [label, source, _writable_label(value), value])
        for col in range(3):
            self._locations_tree.resizeColumnToContents(col)

    def _refresh_port_cache_note(self) -> None:
        """Say when the field is being IGNORED, and why. Cheap enough to run on
        every keystroke -- no filesystem access."""
        env_override = os.environ.get("MPYNODE_PORT_CACHE")
        raw          = self._port_cache_edit.text().strip()
        if env_override:
            self._port_cache_edit.setEnabled(False)
            self._port_cache_browse_btn.setEnabled(False)
            self._port_cache_reset_btn.setEnabled(False)
            self._set_note(
                "Overridden by the MPYNODE_PORT_CACHE environment variable, "
                "which wins over this preference. In force: %s. Unset the "
                "variable to edit this here." % env_override, warn=True)
        elif raw and preferences.is_foreign_os_path(raw):
            self._set_note(
                "This looks like a path for another operating system, so it "
                "is being ignored and the default is used instead. "
                "preferences.json can be shared between a Mac and a Windows "
                "machine; an absolute path cannot.", warn=True)
        else:
            self._port_cache_edit.setEnabled(True)
            self._port_cache_browse_btn.setEnabled(True)
            self._port_cache_reset_btn.setEnabled(True)
            self._set_note("")

    def _set_note(self, text: str, warn: bool = False) -> None:
        self._port_cache_note.setText(text)
        self._port_cache_note.setVisible(bool(text))
        self._port_cache_note.setStyleSheet(
            "color: #c9a227;" if warn else "")

    def _wire_signals(self) -> None:
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._cancel_btn.clicked.connect(self.reject)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        self._template_paths_add_btn.clicked.connect(self._on_add_template_path)
        self._template_paths_remove_btn.clicked.connect(
            self._on_remove_template_path
        )
        self._external_editor_presets.activated.connect(
            self._on_external_editor_preset
        )
        self._port_cache_browse_btn.clicked.connect(self._on_browse_port_cache)
        self._port_cache_reset_btn.clicked.connect(self._on_reset_port_cache)
        # Live feedback: typing a foreign-OS path must warn before Save, not
        # silently do nothing afterwards. The NOTE only -- refreshing the whole
        # table here would write a probe file per row, per keystroke.
        self._port_cache_edit.textChanged.connect(
            lambda _t: self._refresh_port_cache_note())

    def _on_browse_port_cache(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Port Cache Folder",
            self._port_cache_edit.text().strip() or "")
        if path:
            self._port_cache_edit.setText(path)

    def _on_reset_port_cache(self) -> None:
        """Blank = fall through to mpynode.ini, then <home>/port_cache."""
        self._port_cache_edit.clear()

    def _on_external_editor_preset(self, idx: int) -> None:
        """Fill the command line edit from the chosen preset. 'Auto-detect'
        CLEARS the field (empty = auto-detect an installed editor at launch);
        'Custom...' (also an empty template) leaves the current text untouched
        for hand-editing."""
        if not (0 <= idx < len(_EDITOR_PRESETS)):
            return
        label, cmd = _EDITOR_PRESETS[idx]
        if label == "Auto-detect":
            self._external_editor_edit.clear()
        elif cmd:
            self._external_editor_edit.setText(cmd)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        try:
            size = int(self._font_size_edit.text().strip())
            if size < 6 or size > 72:
                raise ValueError("size out of range")
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Font Size",
                "Font size must be an integer between 6 and 72.",
            )
            return

        # Persist via set_pref so listeners fire.
        _efam = self._font_family_combo.currentText().strip()
        if (self._font_family_combo.currentIndex() <= 0
                or _efam == preferences.UI_FONT_DEFAULT_LABEL):
            _efam = ""  # "Maya default": Consolas / Monaco / DejaVu by platform
        preferences.set_pref("editor_font_family", _efam)
        preferences.set_pref("editor_font_size", size)
        preferences.set_pref(
            "external_editor_command",
            self._external_editor_edit.text().strip(),
        )
        nn_idx   = max(0, self._new_node_mode_combo.currentIndex())
        nn_value = self._NEW_NODE_MODE_OPTIONS[nn_idx][1]
        preferences.set_pref("new_node_mode", nn_value)
        preferences.set_pref(
            "template_search_paths",
            [
                self._template_paths_list.item(i).text()
                for i in range(self._template_paths_list.count())
            ],
        )
        preferences.set_pref(
            "addattr_time_auto_connect",
            self._addattr_time_check.isChecked(),
        )
        preferences.set_pref(
            "connect_dialog_show_all_default",
            self._show_all_check.isChecked(),
        )

        preferences.set_pref(
            "connect_dialog_hide_pivots_default",
            self._hide_pivots_check.isChecked(),
        )
        sort_idx   = max(0, self._sort_mode_combo.currentIndex())
        sort_value = self._SORT_MODE_OPTIONS[sort_idx][1]
        preferences.set_pref("connect_dialog_sort_mode_default", sort_value)

        tab_style_idx = max(0, self._script_tab_style_combo.currentIndex())
        preferences.set_pref(
            "script_tab_style",
            self._SCRIPT_TAB_STYLE_OPTIONS[tab_style_idx][1],
        )
        preferences.set_pref(
            "optimize_timeout_enabled",
            self._optimize_timeout_check.isChecked(),
        )
        try:
            _opt_secs = int(self._optimize_timeout_edit.text().strip())
        except ValueError:
            _opt_secs = 2400
        _opt_secs = max(10, min(_opt_secs, 86400))
        preferences.set_pref("optimize_timeout_seconds", _opt_secs)
        # Clamp rather than refuse: the editor size above hard-blocks Save with
        # a messagebox, but that idiom is the outlier in this dialog and a font
        # size is not worth blocking a whole Save over. The UI ceiling is the
        # lower UI_FONT_SIZE_MAX -- see preferences.py.
        try:
            _fs = int(self._ui_font_size_edit.text().strip())
        except ValueError:
            _fs = preferences.DEFAULT_PREFS["ui_font_size"]
        _fs  = max(preferences.FONT_SIZE_MIN,
                   min(_fs, preferences.UI_FONT_SIZE_MAX))
        _fam = self._ui_font_family_combo.currentText().strip()
        if (self._ui_font_family_combo.currentIndex() <= 0
                or _fam == preferences.UI_FONT_DEFAULT_LABEL):
            _fam = ""
        preferences.set_pref("ui_font_family", _fam)
        preferences.set_pref("ui_font_size", _fs)

        try:
            _opt_tok = int(self._optimize_max_tokens_edit.text().strip())
        except ValueError:
            _opt_tok = 64000
        _opt_tok = max(1024, min(_opt_tok, 200000))
        preferences.set_pref("optimize_max_tokens", _opt_tok)

        preferences.set_pref(
            "watch_suppress_scientific",
            self._watch_suppress_check.isChecked(),
        )
        preferences.set_pref(
            "watch_threshold_inf",
            self._watch_threshold_inf_check.isChecked(),
        )
        preferences.set_pref(
            "display_round_enabled",
            self._round_check.isChecked(),
        )
        try:
            _digits = int(self._round_digits_edit.text().strip())
        except ValueError:
            _digits = 8
        _digits = max(0, min(_digits, 17))
        preferences.set_pref("display_round_digits", _digits)
        try:
            _img_px = int(self._img_preview_edit.text().strip())
        except ValueError:
            _img_px = 256
        _img_px = max(32, min(_img_px, 2048))
        preferences.set_pref("variables_image_preview_px", _img_px)
        preferences.set_pref(
            "variables_animate_gif", self._animate_gif_check.isChecked()
        )
        preferences.set_pref(
            "variables_render_waveform",
            self._render_waveform_check.isChecked(),
        )
        try:
            _watch_ms = int(self._watch_refresh_edit.text().strip())
        except ValueError:
            _watch_ms = 80
        _watch_ms = max(16, min(_watch_ms, 5000))
        preferences.set_pref("watch_refresh_ms", _watch_ms)
        try:
            _watch_kb = int(self._watch_max_kb_edit.text().strip())
        except ValueError:
            _watch_kb = 64
        _watch_kb = max(1, min(_watch_kb, 1048576))  # 1 KB .. 1 GB
        preferences.set_pref("watch_max_value_kb", _watch_kb)
        preferences.set_pref(
            "mpn_export_max_compression",
            self._export_max_compress_check.isChecked(),
        )

        preferences.set_pref(
            "metadata_default_authors",
            self._meta_authors_edit.toPlainText().strip(),
        )
        preferences.set_pref(
            "metadata_default_version",
            self._meta_version_edit.text().strip(),
        )
        preferences.set_pref(
            "metadata_default_license",
            self._meta_license_edit.toPlainText().strip(),
        )
        # The retired key was folded into the License editor on load; blank it
        # so the carry-over cannot re-prepend the same text on every open.
        if str(preferences.get_pref("metadata_default_copyright", "") or ""):
            preferences.set_pref("metadata_default_copyright", "")
        preferences.set_pref(
            "metadata_bake_header",
            self._meta_bake_header_check.isChecked(),
        )
        # Stored VERBATIM (blank = fall through). Not normalised or made
        # absolute: a relative path is legitimate and portable, and expansion
        # belongs at read time in port_cache_dir_pref() so the user always sees
        # back exactly what they typed.
        preferences.set_pref(
            "port_cache_dir", self._port_cache_edit.text().strip())
        self.accept()

    def _on_reset_clicked(self) -> None:
        preferences.reset_to_defaults()
        self._load_into_widgets()

    def _on_add_template_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Add Template Search Path"
        )
        if not path:
            return
        existing = {
            self._template_paths_list.item(i).text()
            for i in range(self._template_paths_list.count())
        }
        if path not in existing:
            self._template_paths_list.addItem(path)

    def _on_remove_template_path(self) -> None:
        for item in self._template_paths_list.selectedItems():
            self._template_paths_list.takeItem(
                self._template_paths_list.row(item)
            )
