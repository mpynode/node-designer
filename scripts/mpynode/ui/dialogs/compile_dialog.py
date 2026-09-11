"""CompileDialog — "Compile to native plugin…" view (multi-node).

Pure view for the native-compile feature. The rigger selects N mPy* nodes in
the scene tree, picks "Compile to native plugin…", and this dialog drives the
engine: it extracts a spec per node ON THE GUI/MAIN THREAD (Maya is live here),
hands the plain-data spec list to ``native.compile_controller.CompileController``
(which runs the slow port + clang++ link off-thread), streams per-node status
into a table, and on success offers to load the built ``.bundle``.

Threading rule (the one hard constraint, design "Module layout"): the
controller fires ``progress_cb`` on its WORKER thread, so ``_on_progress`` must
NEVER touch a widget — it only re-emits a queued Qt ``Signal``; the
``@Slot``-decorated ``_on_progress_main`` (delivered on the GUI thread via
``Qt.QueuedConnection``) is the only place widgets are touched. The controller's
terminal ``{"stage": "done"}`` event arrives the same way, so completion is
handled inside that slot — already marshaled to the GUI thread.

All ``maya`` imports are local to methods so the module stays import-safe under
plain python3 / mayapy without a running Maya (matches the package convention).
"""

from __future__ import annotations

import os
import textwrap
import time

from mpynode.ui.qt_wrapper import (
    QAbstractItemView,
    QBrush,
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QFileDialog,
    QFont,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPalette,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyledItemDelegate,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
    Slot,
)

# Keep "…" labels consistent with the rest of the UI (e.g. "Export to.mpn…").
_ELLIPSIS = "…"

# Braille spinner frames: a QTimer cycles these every _SPIN_INTERVAL_MS while a
# compile runs, so the UI reads as alive even when one step (LLM port / clang++
# link) runs long with no sub-progress. qt_wrapper does not re-export QMovie.
_SPIN_FRAMES      = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPIN_INTERVAL_MS = 110

# Collapsible-log toggle labels: "▸" = collapsed, "▾" = expanded.
_LOG_LABEL_COLLAPSED = "Log ▸"
_LOG_LABEL_EXPANDED  = "Log ▾"


def _log_toggle_text(shown: bool) -> str:
    """Toggle-button label for the log pane's current visibility."""
    return _LOG_LABEL_EXPANDED if shown else _LOG_LABEL_COLLAPSED


# Hard wrap width for the log pane + the one indent step the log already uses
# for a sub-line ("  [AI-optimize] ..."). 80 fits the dialog's default width at
# the pane's 10pt monospace, above the 56/60 column rules the summary draws.
_LOG_WRAP_COLS   = 80
_LOG_WRAP_INDENT = "  "


def _wrap_log_line(text) -> str:
    """Hard-wrap an over-long log line, indenting the continuations one step
    deeper than their own header so a wrapped block reads as one entry.

    Without this the remainder of a long "  [AI-optimize] round 2/4 ..." line
    restarts at column 0 and reads as a new, prefix-less entry. Lines already
    inside the width come back untouched -- ordinary output must not be
    reflowed -- and a single over-long token (a path, an identifier) is never
    split, so it stays copy-pasteable.
    """
    out = []
    for line in str(text).split("\n"):
        if len(line) <= _LOG_WRAP_COLS:
            out.append(line)
            continue
        head = line[:len(line) - len(line.lstrip(" "))]
        pieces = textwrap.wrap(line, width=_LOG_WRAP_COLS,
                               subsequent_indent=head + _LOG_WRAP_INDENT,
                               break_long_words=False, break_on_hyphens=False)
        out.extend(pieces or [line])
    return "\n".join(out)

# Table columns. Col 0 is a per-row checkbox: the dialog lists EVERY mPy* node
# in the scene and the bundle is whatever the user checks (default unchecked).
#   * Class    = Option-A notation (``Class(Parent)`` / ``Parent()``), the
#                canonical logical identity -- same as the scene tree.
#   * Node Type= the DERIVED compiled type the bundle registers (camelCase of
#                the Class when classed; the instance-derived type when
#                class-less), NOT the base native type.
_COL_CHECK   = 0
_COL_NODE    = 1  # "Node Name"
_COL_CLASS   = 2  # canonical Class in Option-A notation
_COL_SOURCE  = 3  # "Scene" or "External .mpn"
_COL_PERSIST = 4  # "Data" -- per-node "bake persistent data" checkbox
_COL_TYPE    = 5  # "Node Type" -- the derived compiled type (mc.createNode(...))
_COL_STATUS  = 6

# Column count + header labels kept next to the indices so they never drift.
_COL_COUNT = 7
_COL_HEADERS = ["Compile", "Node Name", "Class", "Source", "Data", "Node Type",
                "Status"]

# Separates a Status cell's build verdict from the optimizer's verdict, and is
# the seam that makes re-stamping idempotent.
_OPT_MARK = " · "


def _parent_wrapper_name(native_type):
    """Root wrapper class name for ``native_type`` (``mPyNode`` -> ``MPyNode``),
    used as the Parent in the Class column's Option-A notation. Falls back to the
    native type string if the registry can't resolve it. Mirrors the scene tree /
    Identity panel derivation so all three read identically."""
    try:
        from mpynode._node_registry import get_spec

        spec = get_spec(native_type)
        if spec is not None:
            root = spec.get_wrapper_class()
            if isinstance(root, type):
                return root.__name__
    except Exception:
        pass
    return native_type

# Unchecked rows are dimmed so the bundle set is obvious at a glance.
_DIM_BRUSH = QBrush(QColor(140, 140, 140))

# CHECKED rows get a subtly brighter background so the bundle set stands out
# (paired with the dimmed text on unchecked rows). Deliberately LIGHT -- a small
# brightening of the dark theme background, not a selection colour. Applied to
# the text cells AND the two centered-checkbox cell WIDGETS (Compile / Data), so
# the highlight spans the WHOLE row rather than leaving dark gaps.
# ``_checked_row_color`` derives it from the table's own Base colour at runtime.
_CHECKED_ROW_FALLBACK = QColor(72, 76, 84)

# Cap (logical px) for the table header's minimum section size. QHeaderView's
# DEFAULT minimum is style-derived: on Windows (Fusion/Vista) ~36-37px, well
# above a checkbox cell's real content (~18-22px), so the ResizeToContents
# checkbox column is clamped UP, leaving an empty focus-selectable strip before
# the Node column. macOS's smaller default hides it. Lowering the floor lets
# col 0 hug the checkbox on Windows too; stays below indicator width at all DPIs.
_CHECKBOX_COL_MIN_PX = 12

# Max height (logical px) of the scrollable Maya-version list. Tuned to sit
# flush with the 3-button column to its right (Select All / None + Log toggle);
# many installed versions then scroll instead of widening the dialog.
_VER_LIST_MAX_H = 100


def _checkbox_min_section_size(current: int) -> int:
    """The header minimum section size to use: never larger than the current
    default. Returns ``min(current, _CHECKBOX_COL_MIN_PX)`` so the change is
    strictly one-directional -- it can only LOWER the floor, never raise it, so
    the already-tight macOS layout is mathematically untouched while Windows's
    oversized floor is reduced enough for the checkbox column to hug its box."""
    return min(current, _CHECKBOX_COL_MIN_PX)


class _NoFocusDelegate(QStyledItemDelegate):
    """Table item delegate that never paints the per-cell focus rectangle.

    The node table is ``NoSelection``, but clicking a text cell still sets the
    view's *current index*, and the platform style then draws a focus square
    around that ONE cell. Inclusion here is driven entirely by the Compile
    checkbox (and clicking a row toggles it), so a lingering current-cell
    highlight is pure visual noise. ``QStyledItemDelegate.paint`` renders from
    the option ``initStyleOption`` primes, so clearing ``State_HasFocus`` here
    guarantees the focus primitive is never drawn -- for every column, without
    touching selection, the table's own focus frame, or the checkboxes."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.State_HasFocus


def _sanitize_plugin_name(name: str) -> str:
    """Turn a raw name into a valid C identifier (no spaces) for a plugin name.

    Mirrors ``spec_extractor._sanitize_ident``: non-ident chars -> ``_``, and a
    leading non-alpha gets an ``n_`` prefix. The dialog validates the
    plugin-name field with this so the bundler never sees an illegal name.
    """
    import re

    s = re.sub(r"[^0-9A-Za-z_]", "_", str(name or "compiledPlugin"))
    if not s or not (s[0].isalpha() or s[0] == "_"):
        s = "n_" + s
    return s


def _default_plugin_name(nodes) -> str:
    """Default plugin name from the selection.

    Per the design: the node's native type when ``N == 1``, else a generic
    multi-node name. Always sanitized to a C identifier.
    """
    if len(nodes) == 1:
        _name, native_type = nodes[0]
        return _sanitize_plugin_name(native_type or _name or "compiledPlugin")
    return "compiledNodes"


# Completion-summary formatting ------------------------------------------------
# Rule separating the finish summary from the streamed compiler output above.
# The log clears at the START of every compile, so this is a within-run divider.
_SUMMARY_RULE = "─" * 60


def _now() -> float:
    """Monotonic clock seam (patched in tests) used for elapsed-time display."""
    return time.monotonic()


def _format_elapsed(seconds) -> str:
    """``M:SS`` for a duration in seconds (e.g. ``0:07``, ``12:05``); ``""`` for
    ``None`` or a negative value so callers can omit the timer cleanly."""
    if seconds is None or seconds < 0:
        return ""
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return "%d:%02d" % (minutes, secs)


def _generated_sources(out_dir, rows):
    """Absolute paths of the per-node C++ the assembler wrote under
    ``out_dir/build/source/`` as ``<type_name>.cpp``, for the rows whose file
    actually exists on disk. Rows without a ``type_name`` are skipped; the result
    is de-duplicated and sorted."""
    if not out_dir:
        return []
    from mpynode.native.compiler import bundler
    src_dir = bundler.source_dir_for(out_dir)
    found   = []
    for row in rows or []:
        type_name = (row or {}).get("type_name")
        if not type_name:
            continue
        path = os.path.join(src_dir, "%s.cpp" % type_name)
        if os.path.exists(path) and path not in found:
            found.append(path)
    return sorted(found)


def _companion_command_lines(result):
    """Per-command native-vs-companion report lines from a compile ``result``.

    Every ``@maya_command`` the native codegen could not translate ships as a
    sibling companion Python plugin (``result['companions']``); each is reported
    as ``"<name> (<kind>) -> companion"`` so the user sees exactly which commands
    became ``maya.cmds`` calls (and that they live in the sibling plugin). Pure;
    returns ``[]`` when there are no companions."""
    lines = []
    for rec in (result or {}).get("companions") or []:
        for c in rec.get("commands") or []:
            lines.append("%s (%s) -> companion"
                         % (c.get("name"), c.get("kind")))
    return lines


def _rounds_clause(info):
    """How the adaptive optimize loop ended for one node, as a clause for its
    summary line: `` -- 3 rounds of max 6, stopped: round 3 not-faster ...``.
    Empty when the record carries no stop reason (a skipped node, a result from
    before the engine recorded one), so that line renders as it always did.
    The wording is REPORT.md's (``stage_report._stop_phrase``)."""
    why = (info or {}).get("stop_reason")
    if not why:
        return ""
    n   = int(info.get("rounds") or 0)
    mx  = int(info.get("max_rounds") or 0)
    ran = "%d round%s" % (n, "" if n == 1 else "s")
    cap = (" of max %d" % mx) if mx > 0 else ""
    return " -- %s%s, stopped: %s" % (ran, cap, why)


def _optimize_summary_lines(result):
    """The AI optimizer's report as human log lines (#64): per-node accepted /
    kept / skipped + reason -- each trailed by how the adaptive loop ended when
    the record says (``_rounds_clause``) -- plus any provider-skip / hard-error
    / deterministic fallback status. Empty when the optimizer did not run.
    Reads the ``result['optimize']`` map the compile controller attaches."""
    opt = (result or {}).get("optimize") or {}
    if not opt:
        return []
    lines = ["", "AI optimization:"]
    if opt.get("__status__"):
        lines.append("  %s" % opt["__status__"])
    for tn, info in opt.items():
        if not isinstance(tn, str) or tn.startswith("__"):
            continue
        if not isinstance(info, dict):
            continue
        if info.get("accepted"):
            line = "  %s: %.2fx faster" % (tn, info.get("speedup", 1.0))
        else:
            line = "  %s: kept original (%s)" % (tn, info.get("reason", ""))
        lines.append(line + _rounds_clause(info))
    if opt.get("__error__"):
        lines.append("  ERROR (non-fatal): %s" % opt["__error__"])
    if opt.get("__fallback__"):
        lines.append("  %s" % opt["__fallback__"])
    return lines


def _verify_crashed(result):
    """True if any node's parity verify did NOT run because the sandbox verify
    subprocess CRASHED (vs. a benign skip like "no reference") -- a strong signal
    the compiled bundle is bad and loading it into the live session would crash
    Maya the same way (#61). Keyed on the verify reason carrying "crash"."""
    for r in (result or {}).get("nodes") or []:
        v = r.get("verify") or {}
        if not v.get("ran") and "crash" in (v.get("reason") or "").lower():
            return True
    return False


def _summary_lines(ok, elapsed_str, plugin_name, bundle_path, manifest_path,
                   source_files, node_lines, error_lines, command_lines=None,
                   warning_lines=None):
    """The completion block appended to the compile log: a separator rule, a
    'done + elapsed' headline, then the generated artifacts (bundle / manifest /
    source files), per-node results, and per-command native-vs-companion lines on
    success, or the errors on failure. ``warning_lines`` are NON-fatal issues on
    an otherwise-OK build (a best-effort dropped node, a companion command set
    that couldn't ship) -- rendered on the success path so they aren't silently
    swallowed. Pure (no widgets / no filesystem) so it's trivially testable."""
    out = ["", _SUMMARY_RULE]
    if ok:
        out.append("✓ Compiled in %s" % elapsed_str if elapsed_str
                   else "✓ Compiled")
        if plugin_name:
            out.append("  Plugin:   %s" % plugin_name)
        if bundle_path:
            out.append("  Bundle:   %s" % bundle_path)
        if manifest_path:
            out.append("  Manifest: %s" % manifest_path)
        for src in source_files or []:
            out.append("  Source:   %s" % src)
        for node in node_lines or []:
            out.append("  Node:     %s" % node)
        for cmd in command_lines or []:
            out.append("  Command:  %s" % cmd)
        for warn in warning_lines or []:
            out.append("  Warning:  %s" % warn)
    else:
        out.append("✗ Compile failed after %s" % elapsed_str if elapsed_str
                   else "✗ Compile failed")
        for err in error_lines or []:
            out.append("  %s" % err)
    out.append(_SUMMARY_RULE)
    return out


def _resolve_maya_dir():
    """Best-effort install root of the RUNNING Maya, so the bundle BUILD and the
    verify SUBPROCESS both target the same version as the live session instead of
    a hardcoded default (``_MAYA_DEFAULT`` = maya2026 in the engine). Returns
    ``None`` if it can't be resolved -- the caller then falls back to the engine
    default.

    ``MAYA_LOCATION`` is set by every running Maya session. On macOS it points at
    ``.../maya<ver>/Maya.app/Contents``; the bundler / ``_mayapy_for`` expect the
    install ROOT (``.../maya<ver>``), so strip that app-bundle suffix. On
    Linux/Windows ``MAYA_LOCATION`` is already the install root.
    """
    loc = os.environ.get("MAYA_LOCATION", "") or ""
    if not loc:
        return None
    # Tolerate a trailing path separator before matching the app-bundle suffix,
    # else the install root is wrong and the pre-flight probes the wrong Maya.
    loc    = loc.rstrip("/\\")
    suffix = "/Maya.app/Contents"
    if loc.endswith(suffix):
        loc = loc[: -len(suffix)]
    return loc or None


def _scene_mpy_nodes():
    """``[(node_name, native_type), ...]`` for every mPy* node in the scene.

    Same enumeration the scene tree uses (``all_native_types`` x ``cmds.ls``);
    this is the live source the dialog's checkbox list is built from. Lazy maya
    import keeps this module import-safe under plain python3; returns ``[]`` if
    unavailable.
    """
    try:
        import maya.cmds as cmds

        from mpynode._node_registry import all_native_types
    except Exception:
        return []
    out = []
    for nt in all_native_types():
        try:
            for name in (cmds.ls(type=nt) or []):
                out.append((name, nt))
        except Exception:
            pass
    return out


def _mpn_trust_prompt():
    """The pickle-trust prompt for reading an external ``.mpn`` in the compile
    UI. A ``.mpn`` can carry pickled stored vars -> decoding it is an RCE
    surface, so the read is gated EXACTLY like the Node Designer import path
    (``make_trust_prompt(allow_always=True, subject=".mpn template")``) instead
    of forcing ``trusted=True``. (Headless ``compile_from_mpn_paths`` is the
    explicit, non-interactive escape hatch and keeps ``trusted=True``.)"""
    from mpynode._common.lifecycle import make_trust_prompt

    return make_trust_prompt(allow_always=True, subject=".mpn template")


class CompileDialog(QDialog):
    """Non-modal dialog that compiles checked mPy* nodes into one ``.bundle``.

    The dialog lists EVERY mPy* node in the current scene with a per-row
    checkbox (default unchecked); the bundle is whatever the user checks. The
    node list is re-queried from the live scene every time the dialog is shown
    (``refresh_nodes``), so it never displays nodes from a previous scene.

    The dialog owns a single ``CompileController`` it reuses across Compile
    clicks; a run is non-blocking (the worker is off-thread) so the window
    stays live and Cancel drives the worker's cancel ``Event``.
    """

    # Queued bridge: the controller's worker-thread ``progress_cb`` only EMITS
    # this; the GUI-thread slot below is the sole widget-toucher.
    _progress = Signal(object)

    # WS2 concierge: after a compile finishes with something the AI could help
    # with (a node that didn't build, or built but diverged from the Python
    # reference), "Fix with AI" emits a hand-off dict (ui.llm.compile_bridge).
    # The designer wires it to the assistant panel's ``seed_compile_context``,
    # so the dialog stays decoupled from the panel.
    handoffToAssistant = Signal(object)

    # Emitted after the class-less compile gate stamps a Class onto one or more
    # scene nodes; payload is the list of newly-stamped node NAMES so the designer
    # re-syncs its Identity panel + scene-tree tags for those nodes (#68).
    classesStamped = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Full live scene listing (re-queried on every open) and the set of
        # checked node NAMES = the bundle. Seeded here BEFORE _build_ui so the
        # plugin-name default can reflect a single-node scene.
        self._scene_nodes = sorted(_scene_mpy_nodes())
        self._checked     = set()
        # Scene NODE names whose diverged-code loss the user explicitly accepted
        # ("Compile first variant only"). Per-node, NOT a global flag, so
        # acknowledging one Class's divergence never mutes an UNRELATED type's
        # lossy drop (an external .mpn, an mPyFile spec-level one) never shown.
        self._acknowledged_diverged_nodes = set()
        # External .mpn rows added via "Add .mpn files…": display name ->
        # (path, native_type, has_persistent, node_type, class_short). They
        # compile with NO scene node, via the pure mpn_spec_adapter instead of
        # the live extract_spec. Seeded BEFORE _build_ui (which merges them in).
        self._file_rows = {}
        # Per-node "bake persistent data" choice, tracking only EXPLICIT
        # unchecks. A node NOT in this set bakes (the legacy default), so a
        # detection miss can never silently DROP a node's stored vars; the
        # global "Ignore persistent data" checkbox overrides this for all nodes.
        self._persistent_unchecked = set()
        # name -> bool cache of "does this node carry persistent data", filled
        # lazily during _refresh_table; drives only the Persistent column's
        # default look (enabled/checked), never the compile-time bake decision.
        self._has_persistent = {}
        self.setWindowTitle("Compile to Native Plugin")
        # Not modal: a compile can take minutes; the user may want to keep
        # working in Maya while it runs (the worker never touches the scene).
        self.setModal(False)
        self.resize(560, 420)

        # Lazily-created controller (Qt-free engine); reused across runs.
        self._controller = None
        # type_name -> table row index, filled at Compile time once specs are
        # extracted (progress events are keyed by the sanitized type_name).
        self._row_by_type = {}
        self._bundle_path = None
        self._busy        = False

        # Spinner + collapsible-log state. ``_status_msg`` is the canonical
        # status text; the spinner (when running) renders it with a leading
        # animated frame. ``_log_shown`` tracks the collapsible log pane.
        self._status_msg   = ""
        self._spin_running = False
        self._spin_i       = 0
        self._spin_timer   = None  # created in _build_ui
        self._log_shown    = False
        # Monotonic origin of the current run (set in _set_busy(True)); drives
        # the elapsed timer. None while idle -> the spinner shows no timer.
        self._run_start = None

        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    # ---- pipeline (transpile -> assist -> optimize) ----------------------

    def _dim(self, text):
        """A secondary-colour explanatory label."""
        lab = QLabel(text, self)
        pal = lab.palette()
        pal.setColor(QPalette.WindowText,
                     pal.color(QPalette.Disabled, QPalette.WindowText))
        lab.setPalette(pal)
        return lab

    def _build_pipeline_ui(self):
        """The three stages, as a gate the user can stop at.

        The single "AI-optimize C++ (slow)" checkbox this replaces conflated
        three different things. Split out, each stage can be declined:

          1  Transpile   always runs, never calls an LLM. Its output is a
                         DELIVERABLE -- for a node the transpiler cannot fully
                         lower it is a .cpp with the gaps marked, which someone
                         with no AI budget can finish by hand.
          2  AI assist   fills those gaps. Defaults ON because porting is
                         unconditional today, and defaulting it off would
                         silently stop shipping nodes that currently build.
          3  AI optimize iterative speed passes; implies 2, because optimizing a
                         skeleton with unfilled gaps is meaningless.
        """
        box = QVBoxLayout()
        box.setSpacing(2)
        head = QLabel("Pipeline", self)
        f    = head.font()
        f.setBold(True)
        head.setFont(f)
        box.addWidget(head)

        # One grid so the boxes line up in a column and the explanatory text in
        # a second; hand-tuned spacing can't -- the three labels differ in width.
        grid = QGridLayout()
        grid.setContentsMargins(18, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(3)

        # Stage 1 is not negotiable, but it IS a stage -- without a box the group
        # read as two optional things. Checked and non-interactive, but NOT via
        # setEnabled(False): Qt greys a disabled checkbox's label.
        self._transpile_check = QCheckBox("1  Transpile", self)
        self._transpile_check.setChecked(True)
        self._transpile_check.setFocusPolicy(Qt.NoFocus)
        # Locked ON by reverting the toggle, NOT by making the widget transparent
        # to mouse events: Qt delivers tooltips through the mouse-event path, so
        # that would make the explanation below permanently unreachable.
        self._transpile_check.toggled.connect(
            lambda on: None if on else self._transpile_check.setChecked(True))
        self._transpile_check.setToolTip(
            "Always runs, and never calls an LLM. Its output is a deliverable "
            "in its own right: for a node the transpiler cannot fully lower it "
            "is a .cpp with each gap marked, which someone with no AI budget "
            "can finish by hand.")
        grid.addWidget(self._transpile_check, 0, 0)
        grid.addWidget(self._dim("always · deterministic C++, no AI"), 0, 1)

        self._assist_check = QCheckBox("2  AI assist", self)
        self._assist_check.setChecked(True)
        self._assist_check.setToolTip(
            "Let the AI fill the compute regions the deterministic transpiler "
            "could not lower.\n"
            "Unchecked: those nodes STOP after step 1. Their baseline C++ is "
            "still written to build/stages/<Type>/1_transpiled.cpp with each "
            "gap marked for a later pass, but they are not compiled and not "
            "bundled -- and no AI provider is required for the build.\n"
            "Nodes the transpiler CAN fully lower are unaffected either way.")
        grid.addWidget(self._assist_check, 1, 0)
        grid.addWidget(
            self._dim("fill the regions the transpiler could not lower"), 1, 1)

        self._optimize_check = QCheckBox("3  AI optimize", self)
        self._optimize_check.setChecked(False)
        self._optimize_check.setToolTip(
            "After porting, an AI agent iteratively rewrites each node's C++ "
            "for speed, measuring every attempt. A round is accepted ONLY if "
            "parity still passes AND it benchmarks measurably faster, so it can "
            "never make a node wrong or slower.\n"
            "Every attempt -- including the rejected ones -- is kept under "
            "build/stages/<Type>/3_optimized/ with a report.\n"
            "Slow, and needs a configured, reachable AI provider.")
        self._optimize_check.toggled.connect(self._sync_pipeline_gates)
        grid.addWidget(self._optimize_check, 2, 0)

        self._rounds_combo = QComboBox(self)
        for n in ("1", "2", "3", "4", "6", "8"):
            self._rounds_combo.addItem(n)
        self._rounds_combo.setCurrentText("6")
        self._rounds_combo.setToolTip(
            "At most this many optimize rounds per node. Each round is one AI "
            "attempt plus a compile, a parity check and a benchmark. The loop "
            "always runs 2, then continues only while the last round was "
            "accepted with a gain of at least 1.15x.")
        rounds_row = QHBoxLayout()
        rounds_row.setContentsMargins(0, 0, 0, 0)
        rounds_row.addWidget(self._dim("max rounds"))
        rounds_row.addWidget(self._rounds_combo)
        # The rule the combo caps, in the caption column like row 0's. It was
        # stated only in the combo's tooltip, so the step read as a fixed count.
        rounds_row.addWidget(self._dim(
            "adaptive \u00b7 always 2 rounds, then only while the last gained "
            "\u2265 1.15x"))
        rounds_row.addStretch(1)
        grid.addLayout(rounds_row, 2, 1)

        # Retention. The default keeps source + reports (tens of KB) and drops
        # build lint; the opt-in also keeps the per-round .bundle files (~90 KB
        # each). Both sit in the checkbox column so the four boxes read as one.
        self._keep_intermediates_check = QCheckBox("Keep intermediates", self)
        self._keep_intermediates_check.setToolTip(
            "Also keep the compiled .bundle for every optimize round.\n"
            "Off by default: the per-round C++, the ledger and the reports are "
            "always kept, and they are what is worth reading.")
        grid.addWidget(self._keep_intermediates_check, 3, 0)

        self._clean_scratch_check = QCheckBox("Clean scratch after compile", self)
        self._clean_scratch_check.setChecked(True)
        self._clean_scratch_check.setToolTip(
            "Delete the build lint when the compile finishes: object files, "
            "per-node port scratch and the optimizer's working directory.\n"
            "Never touches build/source/ or build/stages/ -- the C++ and the "
            "reports always survive.")
        grid.addWidget(self._clean_scratch_check, 3, 1)

        grid.setColumnStretch(1, 1)
        box.addLayout(grid)

        self._sync_pipeline_gates()
        return box

    # ---- live pipeline rail ----------------------------------------------
    # Five checkpoints that light up as the run passes them, so "where is it" is
    # answerable at a glance instead of by reading the log. The rail SUMMARISES
    # an N-node run, which is where it could start lying, so it advances by rank
    # with the WEAKEST outcome on top: one node whose parity SKIPPED means the
    # run was not fully checked, and a green tick would say it was.
    _RAIL_STEPS = (("transpile", "Transpile"),
                   ("assist", "AI assist"),
                   ("optimize", "AI optimize"),
                   ("verify", "Verify"),
                   ("bundle", "Bundle"))

    _RAIL_GLYPH = {"pending": "○", "run": "▶", "done": "✓",
                   "skip": "⊘", "fail": "✕", "off": "–"}
    _RAIL_RANK = {"pending": 0, "run": 1, "done": 2, "skip": 3, "fail": 4}
    _RAIL_COLOR = {"run": "#4a9eff", "done": "#4caf50", "skip": "#c9a227",
                   "fail": "#e05252"}

    def _build_rail_ui(self):
        """The checkpoint strip + the one-line "what is it doing" caption."""
        box = QVBoxLayout()
        box.setSpacing(1)
        row = QHBoxLayout()
        row.setSpacing(14)
        self._rail_labels = {}
        for key, _title in self._RAIL_STEPS:
            lab                    = QLabel("", self)
            self._rail_labels[key] = lab
            row.addWidget(lab)
        row.addStretch(1)
        box.addLayout(row)
        self._rail_detail = self._dim("")
        box.addWidget(self._rail_detail)
        self._rail_state = {}
        self._rail_reset({"ai_assist": True, "optimize": False})
        return box

    def _rail_reset(self, pipe):
        """Start a run from a clean rail. A tick left over from the previous
        compile is a lie about this one."""
        pipe             = pipe or {}
        self._rail_state = {k: "pending" for k, _t in self._RAIL_STEPS}
        if not pipe.get("ai_assist", True):
            self._rail_state["assist"] = "off"
        if not pipe.get("optimize", False):
            self._rail_state["optimize"] = "off"
        if getattr(self, "_rail_detail", None) is not None:
            self._rail_detail.setText("")
        for key, _t in self._RAIL_STEPS:
            self._rail_render(key)

    def _rail_set(self, key, state):
        """Advance a checkpoint -- never retreat, and never light a declined one.

        ``off`` is frozen (the user said no; no event may overrule that) and the
        rest move only UP the rank, so node B starting cannot un-tick node A's
        finished work and a late success cannot scrub an earlier failure.
        """
        cur = self._rail_state.get(key)
        if cur == "off" or key not in self._rail_state:
            return
        if self._RAIL_RANK.get(state, 0) <= self._RAIL_RANK.get(cur, 0):
            return
        self._rail_state[key] = state
        self._rail_render(key)

    def _rail_render(self, key):
        lab = (getattr(self, "_rail_labels", None) or {}).get(key)
        if lab is None:
            return
        title = dict(self._RAIL_STEPS).get(key, key)
        state = self._rail_state.get(key, "pending")
        lab.setText("%s %s" % (self._RAIL_GLYPH.get(state, "○"), title))
        colour = self._RAIL_COLOR.get(state)
        lab.setStyleSheet(("color: %s;" % colour) if colour else "")
        lab.setToolTip("%s: %s" % (title, state))

    def _rail_apply(self, stage, status, detail=""):
        """Map one progress event onto the rail. Unknown events say nothing."""
        detail = detail or ""
        if stage == "done":
            # Whatever nothing reached says "did not run", not "pending" -- at
            # the end, pending reads as "the run stopped early".
            for key, _t in self._RAIL_STEPS:
                if self._rail_state.get(key) == "pending":
                    self._rail_set(key, "skip")
            return
        if stage == "stage":
            if detail == "1_transpiled":
                self._rail_set("transpile", "done")
            elif detail in ("2_assisted", "2_assisted_cached"):
                # A cached body is still an AI-filled body -- the checkpoint is
                # about the C++ that shipped, not about who typed it today.
                self._rail_set("assist", "done")
            return
        if stage in ("cache", "port") and status in ("start", "miss"):
            self._rail_set("transpile", "run")
            return
        if stage == "port" and status == "ok":
            # Only transpile. A node the transpiler fully lowers reaches "port
            # ok" with no LLM call, so ticking AI assist here would be a false
            # credit; the 2_assisted artifact above distinguishes the two.
            self._rail_set("transpile", "done")
            return
        if stage == "port" and status == "fail":
            # The failure belongs to whichever of the two stages was still in
            # flight: nothing transpiled yet means it never got as far as assist.
            owner = ("assist" if self._rail_state.get("transpile") == "done"
                     else "transpile")
            self._rail_set(owner, "fail")
            return
        if stage == "port" and status == "skip":
            # The controller STATING (not us inferring) that porting finished and
            # no node needed the LLM. Retire the chip here: with AI optimize off
            # no optimize event resolves it, so it read "pending" all run. Only a
            # `pending` chip moves, so a genuine `done` can't be scrubbed back to
            # `skip` (skip OUTRANKS done); `off`/`fail` are left alone by _rail_set.
            if self._rail_state.get("assist") == "pending":
                self._rail_set("assist", "skip")
            return
        if stage == "optimize":
            # Optimize starts only once EVERY node has finished porting, so an
            # assist chip still "pending" here is final (no node needed an LLM),
            # not "not yet" -- the terminal sweep can be an hour away.
            if self._rail_state.get("assist") == "pending":
                self._rail_set("assist", "skip")
            if detail:
                self._rail_detail.setText(detail)
            self._rail_set("optimize",
                           {"ok": "done", "fail": "fail",
                            "skip": "skip"}.get(status, "run"))
            return
        if stage == "verify":
            self._rail_set("verify",
                           {"start": "run", "ok": "done", "fail": "fail",
                            "skip": "skip"}.get(status, "run"))
            return
        if stage == "assemble":
            self._rail_set("bundle",
                           {"start": "run", "ok": "done",
                            "fail": "fail"}.get(status, "run"))
            return

    def _on_open_report(self):
        """Open this build's REPORT.md in the built-in Markdown viewer."""
        path = self._last_report_path
        if not path or not os.path.isfile(path):
            QMessageBox.information(
                self, "No Report",
                "This build did not write a report.")
            return
        try:
            from mpynode.ui.dialogs.doc_viewer import DocViewerDialog

            if getattr(self, "_report_viewer", None) is None:
                self._report_viewer = DocViewerDialog(self)
            self._report_viewer.setWindowTitle("Compile Report")
            self._report_viewer.open_path(path)
            self._report_viewer.show()
            self._report_viewer.raise_()
        except Exception as exc:
            QMessageBox.warning(self, "Report", "Could not open the report:\n%s"
                                % exc)

    def _on_open_folder(self):
        from mpynode.ui.editor_launch import reveal_in_file_manager

        target = self._last_report_path or self._last_ai_out_dir
        if not target:
            return
        ok, err = reveal_in_file_manager(target)
        if not ok:
            QMessageBox.warning(self, "Open Folder", str(err))

    def _sync_pipeline_gates(self, *_):
        """Show the implications instead of applying them silently.

        Stage 3 needs stage 2 (nothing to optimize otherwise), and it needs the
        authored tests: for a node whose generic pointwise parity SKIPS -- a
        deformer writes through the native ``outputGeometry``, which the scalar
        harness cannot read -- the authored ``@maya_test`` is the ONLY gate the
        optimizer has. The engine already forces both; checking-and-disabling
        the boxes makes that visible rather than a surprise in the log.
        """
        opt = self._optimize_check.isChecked()
        for check, remembered in ((self._assist_check, "_assist_user_state"),
                                  (self._run_tests_check, "_tests_user_state")):
            if opt:
                if getattr(self, remembered, None) is None:
                    setattr(self, remembered, check.isChecked())
                check.setChecked(True)
                check.setEnabled(False)
            else:
                was = getattr(self, remembered, None)
                if was is not None:
                    check.setChecked(was)
                    setattr(self, remembered, None)
                check.setEnabled(True)
        self._rounds_combo.setEnabled(opt)
        self._keep_intermediates_check.setEnabled(opt)
        if opt:
            self._assist_check.setToolTip(
                "Forced on by AI optimize: there is nothing to make faster in a "
                "skeleton whose regions are still empty.")
            self._run_tests_check.setToolTip(
                "Forced on by AI optimize. For a node whose generic pointwise "
                "parity SKIPS -- a deformer writes through the native "
                "outputGeometry, which the scalar harness cannot read -- the "
                "authored @maya_test is the ONLY gate standing between a "
                "candidate rewrite and your scene.")
        self._sync_compile_button_label()

    def _sync_compile_button_label(self):
        """Name the button after what pressing it actually runs (R2.5 Q2).

        "Compile with AI" is the DEFAULT action -- the pipeline already routes
        every node the deterministic transpiler cannot fully lower through the
        AI porter. But the label must not claim AI when the user has declined
        stage 2: with AI assist off, those nodes stop after the transpile and no
        provider is contacted, so it is a plain "Compile". Reads the RESOLVED
        gate (``_pipeline_options``), because AI optimize implies AI assist.
        """
        btn = getattr(self, "_compile_btn", None)
        if btn is None:  # called from _sync_pipeline_gates during _build_ui
            return
        btn.setText("Compile with AI" if self._pipeline_options()["ai_assist"]
                    else "Compile")

    def _pipeline_options(self):
        """The pipeline choices, resolved. One place, so UI and engine agree."""
        optimize = self._optimize_check.isChecked()
        try:
            rounds = int(self._rounds_combo.currentText())
        except (TypeError, ValueError):
            rounds = 6
        return {
            "ai_assist":          self._assist_check.isChecked() or optimize,
            "optimize":           optimize,
            "optimize_rounds":    rounds,
            "keep_intermediates": self._keep_intermediates_check.isChecked(),
            "clean_scratch":      self._clean_scratch_check.isChecked(),
            "run_tests":          self._run_tests_check.isChecked() or optimize,
        }

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setSpacing(6)
        outer.setContentsMargins(10, 10, 10, 10)

        # --- plugin name -------------------------------------------------
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Plugin name:", self))
        self._name_edit = QLineEdit(self)
        self._name_edit.setText(self._default_name_for_scene())
        name_row.addWidget(self._name_edit, stretch=1)
        outer.addLayout(name_row)

        # --- output folder ----------------------------------------------
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output folder:", self))
        self._out_edit = QLineEdit(self)
        self._out_edit.setText(self._default_out_dir())
        out_row.addWidget(self._out_edit, stretch=1)
        self._browse_btn = QPushButton("Browse" + _ELLIPSIS, self)
        out_row.addWidget(self._browse_btn)
        outer.addLayout(out_row)
        # Keep the output folder tracking the plugin name until the user
        # picks a folder by hand (then we stop auto-syncing).
        self._out_user_set = False

        # --- provider / model (read-only; configured in the panel) -------
        self._provider_label = QLabel(self._provider_text(), self)
        self._provider_label.setEnabled(False)  # informational, dimmed
        outer.addWidget(self._provider_label)

        # --- node table (checkbox list of every mPy* node in the scene) --
        self._table = QTableWidget(0, _COL_COUNT, self)
        self._table.setHorizontalHeaderLabels(_COL_HEADERS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        # Inclusion is driven by the checkbox, not row selection. Clicking a
        # row's text cells toggles it -- a much larger hit target.
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        # ...and NoSelection still leaves a current-cell focus square on click;
        # a no-focus delegate strips it so no per-cell highlight ever paints.
        self._table.setItemDelegate(_NoFocusDelegate(self._table))
        self._table.cellClicked.connect(self._on_row_cell_clicked)
        header = self._table.horizontalHeader()
        try:
            from mpynode.ui.qt_wrapper import QHeaderView

            # Checkbox column hugs its checkbox; Node Name + Class + Node Type
            # are user-resizable (drag the header divider); Source + Data hug
            # their content; Status stretches to fill the rest.
            header.setSectionResizeMode(_COL_CHECK, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(_COL_NODE,  QHeaderView.Interactive)
            header.setSectionResizeMode(_COL_CLASS, QHeaderView.Interactive)
            header.setSectionResizeMode(_COL_SOURCE,
                                        QHeaderView.ResizeToContents)
            header.setSectionResizeMode(_COL_PERSIST,
                                        QHeaderView.ResizeToContents)
            header.setSectionResizeMode(_COL_TYPE, QHeaderView.Interactive)
            header.setSectionResizeMode(_COL_STATUS, QHeaderView.Stretch)
            # Lower the (style-derived) minimum section size so the
            # ResizeToContents checkbox column can shrink to its real content on
            # Windows, where the default floor (~36-37px) clamps it wide and
            # leaves a focus-selectable gap. Monotonic (only lowers), so macOS
            # is untouched. Must precede _refresh_table.
            header.setMinimumSectionSize(
                _checkbox_min_section_size(header.minimumSectionSize()))
        except Exception:
            header.setStretchLastSection(True)
        # Populate from the live scene (re-queried on every open).
        self._refresh_table()
        outer.addWidget(self._table, stretch=1)

        # --- selection helpers -------------------------------------------
        edit_row             = QHBoxLayout()
        self._select_all_btn = QPushButton("Select All", self)
        self._select_all_btn.setToolTip("Check every node in the scene")
        self._select_none_btn = QPushButton("Select None", self)
        self._select_none_btn.setToolTip("Uncheck every node")
        self._refresh_btn = QPushButton("Refresh", self)
        self._refresh_btn.setToolTip(
            "Re-scan the scene for mPy* nodes (after creating/deleting one)")
        # Add external .mpn templates to the list WITHOUT creating scene nodes.
        self._add_mpn_btn = QPushButton("Add .mpn files" + _ELLIPSIS, self)
        self._add_mpn_btn.setToolTip(
            "Add external .mpn node templates to compile -- no scene node is "
            "created; they are read straight off disk")
        edit_row.addWidget(self._select_all_btn)
        edit_row.addWidget(self._select_none_btn)
        edit_row.addWidget(self._refresh_btn)
        edit_row.addWidget(self._add_mpn_btn)
        edit_row.addStretch(1)
        outer.addLayout(edit_row)

        # --- options -----------------------------------------------------
        opt_row = QHBoxLayout()
        # Default ON = strict (abort the whole compile on any per-node
        # failure). Unchecking switches the controller to best-effort.
        self._strict_check = QCheckBox("Strict (abort on any node failure)", self)
        self._strict_check.setChecked(True)
        self._strict_check.setToolTip(
            "Strict: if ANY selected node fails to port or compile, abort the "
            "whole build and produce no plugin.\n"
            "Unchecked (best-effort): build every node that can, and drop the "
            "ones that fail -- each dropped node is reported with a reason.\n"
            "Verify is REPORTED, never fatal: a parity failure does not abort "
            "the build or drop the node, in either mode.\n"
            "Strict has NOTHING to do with your authored @maya_test methods -- "
            "those run only when 'Run authored node tests' is checked, in either "
            "mode.")
        opt_row.addWidget(self._strict_check)
        # Default OFF = do NOT run authored @maya_test methods during the build.
        # The built-in byte-parity check always runs; this extra author-written
        # gate is opt-in because it is slower and not needed for a working plugin.
        self._run_tests_check = QCheckBox("Run authored node tests", self)
        self._run_tests_check.setChecked(False)
        self._run_tests_check.setToolTip(
            "Also run each node's authored @maya_test method(s) against the "
            "COMPILED node during verification, for extra parity confidence.\n"
            "Optional and OFF by default -- the built-in byte-parity check "
            "always runs regardless; nodes with no @maya_test are unaffected.")
        opt_row.addWidget(self._run_tests_check)
        # Default OFF = bake persistent stored-var data into the compiled plugin.
        # Checking it compiles a "vanilla" plugin (drops baked persistent data).
        self._ignore_persistent_check = QCheckBox("Ignore persistent data", self)
        self._ignore_persistent_check.setToolTip(
            "Compile a vanilla plugin: do NOT bake persistent stored-variable "
            "values into the generated C++ (definitions/defaults are kept). "
            "Overrides the per-node Persistent column (greys it out) for ALL "
            "nodes while checked.")
        opt_row.addWidget(self._ignore_persistent_check)
        opt_row.addStretch(1)
        outer.addLayout(opt_row)

        # --- pipeline: three gated stages --------------------------------
        outer.addLayout(self._build_pipeline_ui())

        # --- target Maya versions (multi-version compile) ----------------
        # Auto-detect installed Maya versions usable as build targets (devkit +
        # mayapy); one checkbox each, the RUNNING Maya pre-checked. Check 2+ to
        # build a plugin per version into out_dir/<label>/. If discovery finds
        # nothing the row is omitted and the compile targets the running Maya.
        self._maya_targets = []
        self._maya_checks  = {}
        try:
            from mpynode.native.toolchain import toolchain

            self._maya_targets = toolchain.discover_maya_installs()
        except Exception:
            self._maya_targets = []
        # Live-log toggle: created unconditionally so the dialog always has it.
        # Placed in the version button column (below) when versions exist, else
        # it falls back onto the status row.
        self._log_toggle_btn = QPushButton(_log_toggle_text(False), self)
        self._log_toggle_btn.setToolTip("Show/hide the live compiler output log")
        self._log_toggle_btn.setCheckable(True)
        if self._maya_targets:
            default_labels = set(self._default_checked_labels(
                self._maya_targets, _resolve_maya_dir()))
            outer.addWidget(QLabel("Maya versions:", self))
            # Scrollable, height-capped list so 5+ installed versions scroll
            # instead of widening the dialog. The Select All / None + Log toggle
            # buttons stack to its RIGHT, sized to sit flush with the list.
            ver_row    = QHBoxLayout()
            ver_scroll = QScrollArea(self)
            ver_scroll.setWidgetResizable(True)
            ver_scroll.setMaximumHeight(_VER_LIST_MAX_H)
            ver_host = QWidget(ver_scroll)
            ver_col  = QVBoxLayout(ver_host)
            ver_col.setContentsMargins(4, 2, 4, 2)
            ver_col.setSpacing(2)
            for t in self._maya_targets:
                cb = QCheckBox(t["label"], self)
                cb.setChecked(t["label"] in default_labels)
                cb.setToolTip(
                    "Build a separate plugin against %s (%s).\nCheck two or "
                    "more to build each into its own sub-folder."
                    % (t["label"], t["root"]))
                self._maya_checks[t["label"]] = cb
                ver_col.addWidget(cb)
            ver_col.addStretch(1)
            ver_scroll.setWidget(ver_host)
            ver_row.addWidget(ver_scroll, stretch=1)
            # Right-hand button column: Select All / None (the "compile all
            # versions" affordance) + the live-log toggle, top-aligned.
            ver_btn_col       = QVBoxLayout()
            self._ver_all_btn = QPushButton("Select All", self)
            self._ver_all_btn.setToolTip("Check every Maya version")
            self._ver_none_btn = QPushButton("Select None", self)
            self._ver_none_btn.setToolTip("Uncheck every Maya version")
            self._ver_all_btn.clicked.connect(
                lambda checked=False: self._set_all_versions(True))
            self._ver_none_btn.clicked.connect(
                lambda checked=False: self._set_all_versions(False))
            ver_btn_col.addWidget(self._ver_all_btn)
            ver_btn_col.addWidget(self._ver_none_btn)
            ver_btn_col.addWidget(self._log_toggle_btn)
            ver_btn_col.addStretch(1)
            ver_row.addLayout(ver_btn_col)
            outer.addLayout(ver_row)

        # --- status ------------------------------------------------------
        # No progress bar: the slowest steps (LLM port, clang++ link, subprocess
        # parity verify) have no sub-progress, so a percentage would only lie (it
        # used to pin to 100% the instant work started). Instead an animated
        # braille spinner prefixes this honest phase line, and a collapsible log
        # pane below streams the raw compiler output. The Log toggle lives in the
        # version button column, or on the status row when no installs exist.
        status_row         = QHBoxLayout()
        self._status_label = QLabel("", self)
        status_row.addWidget(self._status_label, stretch=1)
        if not self._maya_targets:
            status_row.addWidget(self._log_toggle_btn)
        outer.addLayout(status_row)

        # --- live pipeline rail (checkpoints + what the AI is trying) -----
        outer.addLayout(self._build_rail_ui())

        # --- live compiler log (collapsible; auto-opens on compile) ------
        # Hidden when idle so it doesn't dominate the dialog; _set_busy(True)
        # clears + shows it, and the Log toggle flips it any time.
        self._log_view = QPlainTextEdit(self)
        self._log_view.setReadOnly(True)
        self._log_view.setVisible(False)
        # Right-click Clear / Copy All, mirroring the Node Designer log (#70).
        self._log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._log_view.customContextMenuRequested.connect(
            self._on_log_context_menu)
        try:
            # Monospace so columns in compiler diagnostics line up.
            mono = QFont("Menlo")
            mono.setStyleHint(QFont.Monospace)
            mono.setPointSize(10)
            self._log_view.setFont(mono)
            # A bounded scrollback keeps a long, chatty link from growing the
            # widget's memory without limit (0 = unlimited).
            self._log_view.setMaximumBlockCount(5000)
        except Exception:
            pass
        outer.addWidget(self._log_view, stretch=1)

        # Spinner timer: cycles _tick_spinner while a compile runs. Parented to
        # self so it's cleaned up with the dialog; started/stopped in _set_busy.
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(_SPIN_INTERVAL_MS)
        self._spin_timer.timeout.connect(self._tick_spinner)

        # --- per-node green-light strip (WS2 R2.2) -----------------------
        # Verify is non-fatal by design, so a diverged / incomplete / unverified
        # node still SHIPS. What was missing is the user's say in it: this strip
        # appears after a finish with one row per flagged node -- "Green-light"
        # accepts that node's C++ as-is, un-green-lit means "keep iterating" and
        # it rides into the "Fix with AI" hand-off.
        self._greenlight_box    = QWidget(self)
        self._greenlight_layout = QVBoxLayout(self._greenlight_box)
        self._greenlight_layout.setContentsMargins(0, 0, 0, 0)
        self._greenlight_layout.setSpacing(2)
        self._greenlight_box.setVisible(False)
        outer.addWidget(self._greenlight_box)
        # source_node (or type_name) -> the row's checkable Green-light button.
        self._greenlight_btns = {}
        # The keys the user has accepted this run.
        self._greenlit = set()

        # --- buttons -----------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._compile_btn = QPushButton("Compile", self)
        self._compile_btn.setDefault(True)
        self._cancel_btn = QPushButton("Cancel", self)
        self._cancel_btn.setEnabled(False)  # only enabled during a run
        # WS2 concierge: appears only after a finish that has something the AI
        # could help with (a dropped or diverged node). Hands the compile report
        # to the assistant to iterate toward a compiling, on-par C++ node.
        self._ai_btn = QPushButton("Fix with AI" + _ELLIPSIS, self)
        self._ai_btn.setVisible(False)
        self._ai_btn.setToolTip(
            "Hand this compile's report to the AI assistant to get the flagged "
            "node(s) compiling with output on-par with the Python version.")
        # The compile writes REPORT.md (index) plus one per node under
        # build/stages/. Without a way in, that work is invisible unless someone
        # goes looking in Finder -- so surface it where the run finished.
        self._report_btn = QPushButton("Report" + _ELLIPSIS, self)
        self._report_btn.setVisible(False)
        self._report_btn.setToolTip(
            "Open this build's report: what each stage did per node, every "
            "optimize round including the rejected ones, and which parity gate "
            "judged them.")
        self._report_btn.clicked.connect(self._on_open_report)
        self._folder_btn = QPushButton("Open Folder", self)
        self._folder_btn.setVisible(False)
        self._folder_btn.setToolTip("Reveal the output folder.")
        self._folder_btn.clicked.connect(self._on_open_folder)
        self._close_btn = QPushButton("Close", self)
        btn_row.addWidget(self._compile_btn)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._ai_btn)
        btn_row.addWidget(self._report_btn)
        btn_row.addWidget(self._folder_btn)
        btn_row.addWidget(self._close_btn)
        outer.addLayout(btn_row)
        # Set by _on_finished; the two buttons above are separate clicks.
        self._last_report_path = None
        # Stashed by _on_finished so the AI button (a separate click) can rebuild
        # the hand-off from the last result without re-running the compile.
        self._last_ai_result  = None
        self._last_ai_out_dir = None
        # Name the Compile button after what it will actually run, now that both
        # the pipeline checkboxes and the button itself exist.
        self._sync_compile_button_label()

    def _wire_signals(self) -> None:
        self._browse_btn.clicked.connect(self._on_browse)
        self._name_edit.textChanged.connect(self._on_name_changed)
        self._select_all_btn.clicked.connect(
            lambda checked=False: self._set_all_checked(True))
        self._select_none_btn.clicked.connect(
            lambda checked=False: self._set_all_checked(False))
        # Refresh BUTTON re-scans the scene but PRESERVES the user's in-session
        # checks for surviving nodes (unlike refresh_nodes(), the open path).
        self._refresh_btn.clicked.connect(
            lambda checked=False: self._refresh_table())
        self._add_mpn_btn.clicked.connect(
            lambda checked=False: self._on_add_mpn())
        # The global "Ignore persistent data" greys out / restores the per-node
        # Persistent column when toggled.
        self._ignore_persistent_check.toggled.connect(
            lambda checked=False: self._on_ignore_persistent_toggled())
        # Declining AI assist renames the Compile button, so it never claims an
        # AI pass the user switched off ("AI optimize" arrives via
        # _sync_pipeline_gates, which syncs the label itself).
        self._assist_check.toggled.connect(
            lambda checked=False: self._sync_compile_button_label())
        # Row checkboxes are per-cell widgets; each one wires its own toggled
        # signal to _on_check_toggled in _make_check_cell (no table-level
        # itemChanged -- the cells hold no checkable items).
        self._compile_btn.clicked.connect(self._on_compile)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._ai_btn.clicked.connect(
            lambda checked=False: self._on_fix_with_ai())
        self._close_btn.clicked.connect(self.close)
        # The Log button collapses/expands the live compiler-output pane.
        self._log_toggle_btn.clicked.connect(
            lambda checked=False: self._toggle_log())
        # Worker-thread progress events hop to the GUI thread here. Qt
        # auto-queues a cross-thread Signal; QueuedConnection makes that
        # explicit (the slot is the ONLY place widgets are touched).
        self._progress.connect(self._on_progress_main, Qt.QueuedConnection)

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    def _set_cell(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem("" if text is None else str(text))
        self._table.setItem(row, col, item)

    def _stamp_optimize_results(self, result) -> None:
        """Put each node's optimizer verdict on its own row.

        ``result['optimize']`` already carries accepted/speedup per node, but it
        only ever reached the scrolling log -- so the table read "verified" both
        for a node that got 4.7x and for one whose every candidate was rejected.
        A rejected round is stated too: silence reads as "not optimized", and
        "tried, kept the original" is the more useful fact.
        """
        opt = (result or {}).get("optimize") or {}
        for type_name, rec in opt.items():
            row = self._row_by_type.get(type_name)
            if row is None or not isinstance(rec, dict):
                continue
            item = self._table.item(row, _COL_STATUS)
            base = (item.text() if item is not None else "") or ""
            base = base.split(_OPT_MARK, 1)[0]  # re-stamping is idempotent
            if rec.get("accepted"):
                try:
                    note = "%.1fx faster" % float(rec.get("speedup") or 1.0)
                except (TypeError, ValueError):
                    note = "optimized"
            else:
                note = "kept original"
            self._set_cell(row, _COL_STATUS, base + _OPT_MARK + note)

    def _default_name_for_scene(self) -> str:
        """Plugin-name default derived from the live scene: the single mPy
        node's native type when the scene has exactly one, else the generic
        name. (``_scene_nodes`` is seeded in ``__init__`` before this runs.)"""
        return _default_plugin_name(self._scene_nodes)

    def _default_out_dir(self) -> str:
        """Default output folder: ``~/mpynode/compiled/<pluginName>``.

        A per-user, always-writable location in the same VISIBLE family as the
        port cache / typeid registry (``~/mpynode``, override MPYNODE_HOME; see
        mpynode._common.home). The user can override via Browse.
        """
        from mpynode._common import home

        name = _sanitize_plugin_name(self._name_edit.text()
                                     if hasattr(self, "_name_edit")
                                     else _default_plugin_name(self._scene_nodes))
        return os.path.join(home.compiled_dir(), name)

    def _provider_text(self) -> str:
        """One-line 'Porter: <Provider label> / <model>' from live config."""
        try:
            from mpynode.ui.llm import config

            provider = config.get_provider()
            model    = config.get_model(provider)
            label    = config.PROVIDER_LABELS.get(provider, provider)
        except Exception:
            return "Porter: (provider unavailable)"
        model_txt = (" / %s" % model) if model else ""
        return "Porter: %s%s" % (label, model_txt)

    # ------------------------------------------------------------------
    # Field events
    # ------------------------------------------------------------------

    def _on_name_changed(self, _text: str) -> None:
        # Keep the output folder following the plugin name until the user
        # explicitly picks a folder.
        if not self._out_user_set:
            self._out_edit.setText(self._default_out_dir())

    def _on_browse(self) -> None:
        start = self._out_edit.text().strip() or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", start
        )
        if chosen:
            self._out_user_set = True
            self._out_edit.setText(chosen)

    # ------------------------------------------------------------------
    # Scene node list + checkbox selection
    # ------------------------------------------------------------------

    def refresh_nodes(self) -> None:
        """Re-query the live scene, rebuild the node list, AND reset the
        checkbox selection. This is the OPEN path (called every time the dialog
        is shown): each open starts fresh (default unchecked) and never carries
        a previous scene's checks -- node names aren't unique across scenes, so
        preserving checks by name could silently pre-select a node the user
        never chose. (The Refresh *button* uses ``_refresh_table`` directly,
        which preserves in-session checks for surviving nodes.)

        No-op while a compile is in flight (it would wipe the live per-node
        status); ``closeEvent`` clears ``_busy`` so a close-mid-compile then
        reopen still refreshes.
        """
        if self._busy:
            return
        self._checked     = set()
        self._row_by_type = {}
        # External .mpn rows are an in-session add; a fresh open starts clean
        # (the Refresh *button* goes through _refresh_table and keeps them).
        self._file_rows = {}
        # Per-node persistent choices + detection cache are also in-session.
        self._persistent_unchecked = set()
        self._has_persistent       = {}
        self._refresh_table()

    def preselect_node(self, name) -> None:
        """Check exactly ``name`` (a scene node) and clear other checks, so a
        scene-tab right-click "Compile…" lands one click from compiling just it.

        Ignored while a compile is in flight (it would wipe the live per-node
        status), or when ``name`` is not a listed node (a stale / renamed
        reference) -- never silently check the wrong node.
        """
        if self._busy:
            return
        if name not in {n for (n, _t) in self._scene_nodes}:
            return
        self._checked = {name}
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Rebuild the node table from the LIVE scene. Each row: a checkbox,
        Node, Type, Status. Checks for nodes that no longer exist are pruned;
        checks for surviving nodes are preserved. No-op while a compile is in
        flight (it would wipe the live per-node status / ``_row_by_type``)."""
        if self._busy:
            return
        nodes = sorted(_scene_mpy_nodes())
        # A file row whose name now collides with a scene node created AFTER it
        # was added must be renamed -- otherwise both rows key on one name and
        # the live scene node would be silently compiled from the stale .mpn.
        scene_names = {n for (n, _t) in nodes}
        (self._file_rows, self._checked,
         self._persistent_unchecked) = self._disambiguate_file_rows(
            self._file_rows, self._checked, self._persistent_unchecked,
            scene_names)
        # Merge external .mpn file rows so they list + compile alongside scene
        # nodes. Their checks survive a rescan because they are in ``names``.
        file_rows = sorted(
            (name, val[1]) for name, val in self._file_rows.items())
        nodes             = nodes + file_rows
        self._scene_nodes = nodes
        names             = {n for (n, _t) in nodes}
        self._checked     = {n for n in self._checked if n in names}
        # Prune stale per-node persistent unchecks (mirroring _checked): a later
        # node reusing the name would inherit it and silently lose stored vars.
        self._persistent_unchecked = {n for n in self._persistent_unchecked
                                      if n in names}
        # Re-detect persistent presence for this rebuild (a node may have gained
        # or cleared stored vars since the last refresh).
        self._has_persistent = {}
        self._table.setRowCount(len(nodes))
        # Each row's checkbox sets its state BEFORE connecting its signal, so
        # rebuilding rows never fires a toggle -- no suppress flag needed.
        for row, (node_name, native_type) in enumerate(nodes):
            self._render_row(row, node_name, native_type)
        self._table.resizeColumnToContents(_COL_CHECK)
        self._table.resizeColumnToContents(_COL_NODE)
        self._table.resizeColumnToContents(_COL_CLASS)
        self._table.resizeColumnToContents(_COL_SOURCE)
        self._table.resizeColumnToContents(_COL_PERSIST)
        self._table.resizeColumnToContents(_COL_TYPE)

    def _source_label(self, name: str) -> str:
        """Where a row's node comes from: ``"External .mpn"`` for a row added off
        disk (in ``_file_rows``), else ``"Scene"`` for a live scene node."""
        return "External .mpn" if name in self._file_rows else "Scene"

    @staticmethod
    def _default_checked_labels(installs, running_root):
        """Which Maya version label(s) to PRE-CHECK: the running Maya if it is one
        of the detected installs, else the highest version (installs come version-
        sorted from ``discover_maya_installs``). Empty list when nothing detected.
        Guarantees at least one is checked when any install exists."""
        if not installs:
            return []
        if running_root:
            rr = os.path.abspath(running_root)
            for t in installs:
                if os.path.abspath(t.get("root") or "") == rr:
                    return [t["label"]]
        return [installs[-1]["label"]]

    def _checked_targets(self):
        """The detected Maya targets whose checkbox is ticked, in display order.
        Empty when no version row is shown (no installs detected)."""
        out = []
        for t in getattr(self, "_maya_targets", []) or []:
            cb = self._maya_checks.get(t["label"])
            try:
                if cb is not None and cb.isChecked():
                    out.append(t)
            except Exception:
                pass
        return out

    def _set_all_versions(self, checked: bool) -> None:
        """Check/uncheck every Maya-version target (Select All / None)."""
        for cb in getattr(self, "_maya_checks", {}).values():
            try:
                cb.setChecked(bool(checked))
            except Exception:
                pass

    def _make_check_cell(self, name, col, row, checked, enabled):
        """A cell widget hosting a horizontally-centered ``QCheckBox``.

        Centering via a layout is the only reliable way across Qt styles: a
        checkable ``QTableWidgetItem`` pins its indicator to the cell's leading
        edge and leaves a selectable empty gap (the "box next to the checkbox"
        the user saw). State is set BEFORE the ``toggled`` signal is connected,
        so building/rebuilding a cell never spuriously fires the handler --
        which is why no suppress flag is needed."""
        container = QWidget(self._table)
        lay       = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        cb = QCheckBox(container)
        cb.setChecked(bool(checked))
        cb.setEnabled(bool(enabled))
        lay.addWidget(cb, 0, Qt.AlignCenter)
        cb.toggled.connect(
            lambda state, n=name, c=col, r=row:
            self._on_check_toggled(c, n, r, bool(state)))
        return container

    def _render_row(self, row: int, name: str, native_type: str) -> None:
        """Render one table row: a centered include checkbox (col 0) + Node Name /
        Class / Source / Data / Node Type / Status."""
        checked = name in self._checked
        # Col 0 (include) is always enabled; centered via a cell widget so it
        # doesn't float at the leading edge next to a selectable empty gap.
        self._table.setCellWidget(
            row, _COL_CHECK,
            self._make_check_cell(name, _COL_CHECK, row, checked, True))
        self._set_cell(row, _COL_NODE,   name)
        self._set_cell(row, _COL_CLASS,  self._row_class_label(name, native_type))
        self._set_cell(row, _COL_SOURCE, self._source_label(name))
        self._render_persistent_cell(row, name)
        # Node Type = the DERIVED compiled type (what the bundle registers /
        # mc.createNode targets), NOT the base native type.
        self._set_cell(row, _COL_TYPE, self._row_node_type(name, native_type))
        self._set_cell(row, _COL_STATUS, "")
        self._apply_row_style(row, checked)

    # ------------------------------------------------------------------
    # Class + Node Type projection (Option A / derived compiled type)
    # ------------------------------------------------------------------

    def _row_class_short(self, name: str) -> str:
        """Short Class name for a row (``""`` when class-less / unknown).

        Scene node: its stamped ``class_path`` short name. External .mpn row: the
        Class short name captured from the payload at add time (``""`` for a
        class-less / un-migrated .mpn), so a class-less .mpn renders ``Parent()``
        exactly like a class-less scene node -- never a Class fabricated from the
        instance-derived node type."""
        val = self._file_rows.get(name)
        if val is not None:
            return (val[4] if len(val) > 4 else "") or ""
        try:
            from mpynode.wrappers._mpy_node import _read_py_class

            pc = _read_py_class(name) or ""
        except Exception:
            pc = ""
        return pc.rpartition(".")[2] if pc else ""

    def _row_class_label(self, name: str, native_type: str) -> str:
        """Option-A Class notation for a row: ``Class(Parent)`` classed,
        ``Parent()`` class-less -- the same notation the scene tree shows."""
        short  = self._row_class_short(name)
        parent = _parent_wrapper_name(native_type)
        return "%s(%s)" % (short, parent) if short else "%s()" % parent

    def _row_node_type(self, name: str, native_type: str) -> str:
        """The DERIVED compiled type name the bundle would register for a row.

        External .mpn row: the ``node_type_name`` the adapter already computed.
        Scene node: ``derive_class_identity(class_path or name)['node_type_name']``
        -- byte-identical to what ``spec_extractor.extract_spec`` produces
        (camelCase of the Class when classed; the instance-derived type when
        class-less), so the column matches what actually compiles."""
        val = self._file_rows.get(name)
        if val is not None:
            return (val[3] if len(val) > 3 else "") or ""
        try:
            from mpynode.native.spec.identity import derive_class_identity
            from mpynode.wrappers._mpy_node import _read_py_class

            class_path = _read_py_class(name) or ""
            return derive_class_identity(
                class_path or name, native_type)["node_type_name"]
        except Exception:
            return ""

    def _checked_row_color(self) -> QColor:
        """The 'a little brighter than the background' highlight colour for
        CHECKED rows, derived once from the table's own Base colour so it adapts
        to the theme (Maya's dark palette) and stays subtle. Falls back to a fixed
        subtle grey if the palette can't be read (e.g. a duck-typed test table)."""
        col = getattr(self, "_checked_row_color_cache", None)
        if col is not None:
            return col
        try:
            base = self._table.palette().color(QPalette.Base)
            hl   = base.lighter(135)
            # On a near-black base, lighter() barely moves -- lift additively so
            # the highlight is always visible but still gentle.
            if hl.value() - base.value() < 12:
                hl = QColor(min(base.red() + 20, 255),
                            min(base.green() + 22, 255),
                            min(base.blue() + 26, 255))
            col = hl
        except Exception:
            col = _CHECKED_ROW_FALLBACK
        self._checked_row_color_cache = col
        return col

    def _tint_cell_widget(self, widget, checked: bool) -> None:
        """Give a centered-checkbox cell widget (Compile / Data) the checked-row
        background so the highlight spans the FULL row -- those two columns are
        cell WIDGETS, not items, so ``item.setBackground`` can't reach them. Uses
        the widget PALETTE (not a stylesheet) so the child QCheckBox indicator is
        never restyled. Best-effort: a duck-typed widget without the palette API
        is a silent no-op."""
        try:
            if checked:
                widget.setAutoFillBackground(True)
                pal = widget.palette()
                pal.setColor(widget.backgroundRole(), self._checked_row_color())
                widget.setPalette(pal)
            else:
                # Back to a default (transparent) cell.
                widget.setAutoFillBackground(False)
                widget.setPalette(QPalette())
        except Exception:
            pass

    def _apply_row_style(self, row: int, checked: bool) -> None:
        """Style one row for its bundle-inclusion state: dim the TEXT of UNCHECKED
        rows, and give CHECKED rows a subtle brighter background across the whole
        row (the text cells AND the two centered-checkbox cell widgets) so the
        bundle set is obvious at a glance."""
        normal = QBrush()
        bg     = QBrush(self._checked_row_color()) if checked else QBrush()
        for col in (_COL_NODE, _COL_CLASS, _COL_SOURCE, _COL_TYPE, _COL_STATUS):
            item = self._table.item(row, col)
            if item is not None:
                item.setForeground(normal if checked else _DIM_BRUSH)
                item.setBackground(bg)
        # The Compile + Data columns are cell widgets, not items -- tint their
        # containers so the row highlight has no dark gaps.
        for col in (_COL_CHECK, _COL_PERSIST):
            w = self._table.cellWidget(row, col)
            if w is not None:
                self._tint_cell_widget(w, checked)

    # ------------------------------------------------------------------
    # Per-node persistent-data column
    # ------------------------------------------------------------------

    @staticmethod
    def _persist_cell_state(has_persistent, global_ignore, user_unticked,
                            in_bundle=True):
        """``(enabled, checked)`` for one node's Persistent checkbox.

        A node WITH persistent data gets an enabled box, checked unless the user
        explicitly unticked it; a node WITHOUT gets a disabled, unchecked box
        (nothing to bake) -- so the column doubles as an at-a-glance "which nodes
        carry persistent data" indicator. The whole column greys out (disabled,
        unchecked) while the global "Ignore persistent data" is on. A node NOT in
        the bundle (col-0 unchecked, so it won't compile) is also disabled, but
        keeps showing its has-data indicator so the column still reads."""
        if global_ignore:
            return (False, False)
        checked = bool(has_persistent) and not user_unticked
        enabled = bool(has_persistent) and in_bundle
        return (enabled, checked)

    @staticmethod
    def _bake_choice_for(name, global_ignore, persistent_unchecked):
        """The per-spec ``bake_persistent`` value to stamp for ``name``, or
        ``None`` to leave it UNSET (use the global default).

        When globally ignoring, return ``None`` so the global ``bake_persistent=
        False`` strips ALL nodes uniformly (a per-spec True would wrongly
        override it). Otherwise bake unless the user explicitly unticked the
        node -- the legacy default is to bake, so a node we never showed a usable
        checkbox for is still baked."""
        if global_ignore:
            return None
        return name not in persistent_unchecked

    def _global_ignore_persistent(self) -> bool:
        """Is the global 'Ignore persistent data' checkbox on? Tolerates being
        called before the checkbox exists (the first _build_ui -> _refresh_table
        runs before the option row is created)."""
        try:
            return bool(self._ignore_persistent_check.isChecked())
        except Exception:
            return False

    def _node_has_persistent(self, name: str) -> bool:
        """Best-effort: does this row's node carry persistent (stored-var) data?

        File rows cache the answer (detected once at add time, on the row tuple);
        scene nodes are read live via the wrapper, memoised in ``_has_persistent``.
        Drives both the Data column's default look AND the pre-compile bake
        confirm (via :meth:`_nodes_baking_persistent`) -- so ``_on_compile``
        drops the ``_has_persistent`` cache before the confirm to force a live
        re-read (a wrong answer would silently skip the confirm). The bake
        itself still keys off explicit unchecks, so a false answer never drops
        data; it only affects whether the confirm prompt fires."""
        if name in self._has_persistent:
            return self._has_persistent[name]
        val = self._file_rows.get(name)
        if val is not None:
            has = bool(val[2]) if len(val) > 2 else False
        else:
            try:
                import mpynode

                w   = mpynode.wrap_node(name)
                has = bool(w is not None and (w.get_variables() or {}))
            except Exception:
                has = False
        self._has_persistent[name] = has
        return has

    def _render_persistent_cell(self, row: int, name: str) -> None:
        """Render the Data (per-node bake-persistent) column's checkbox for one
        row -- a centered cell widget, enabled/checked per ``_persist_cell_state``."""
        enabled, checked = self._persist_cell_state(
            self._node_has_persistent(name),
            self._global_ignore_persistent(),
            name in self._persistent_unchecked,
            in_bundle=name in self._checked)
        self._table.setCellWidget(
            row, _COL_PERSIST,
            self._make_check_cell(name, _COL_PERSIST, row, checked, enabled))
        # Keep the checked-row highlight on the freshly-built Data widget so the
        # ignore-persistent re-render path never leaves a dark gap in a checked
        # (highlighted) row.
        w = self._table.cellWidget(row, _COL_PERSIST)
        if w is not None:
            self._tint_cell_widget(w, name in self._checked)

    def _refresh_persistent_column(self) -> None:
        """Re-render just the Data column for every current row (cheap; no scene
        rescan) -- used when the global 'Ignore persistent data' toggles.
        Reads each row's name from its Node cell (col 0 is now a widget, not an
        item); rebuilding the cell widgets fires no toggles (state set before
        the signal is connected)."""
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _COL_NODE)
            name = item.text() if item is not None else None
            if name:
                self._render_persistent_cell(row, name)

    def _on_ignore_persistent_toggled(self) -> None:
        """Grey out / restore the per-node Data column when the global
        'Ignore persistent data' is toggled. No-op while a compile runs."""
        if self._busy:
            return
        self._refresh_persistent_column()

    def _nodes_baking_persistent(self, checked):
        """Names among ``checked`` whose Data box is (auto-)checked, i.e. that
        will BAKE their persistent stored data into the compiled plugin: a node
        with persistent data that is neither explicitly unticked nor globally
        ignored. Drives the pre-compile bake confirmation."""
        global_ignore = self._global_ignore_persistent()
        if global_ignore:
            return []  # a vanilla plugin bakes nothing -> nothing to confirm
        out = []
        for (name, _t) in checked:
            if (self._node_has_persistent(name)
                    and self._bake_choice_for(
                        name, global_ignore, self._persistent_unchecked)):
                out.append(name)
        return out

    def _confirm_bake_persistent(self, names) -> bool:
        """Confirm baking persistent stored data for ``names`` into the plugin.
        Returns True to proceed, False to abort the compile. Isolated so headless
        tests can stub it (mirrors ``_prompt_divergence_choice`` / ``_warn``)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Bake Persistent Data")
        box.setText(
            "%d selected node(s) carry persistent stored data that will be "
            "BAKED into the compiled plugin:" % len(names))
        box.setInformativeText(
            "  " + "\n  ".join(names)
            + "\n\nThe current stored values become the compiled node's baked "
            "defaults. Untick a node's Data column (or check 'Ignore persistent "
            "data') to compile a vanilla plugin instead.\n\nBake and continue?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Yes)
        return box.exec_() == QMessageBox.Yes

    def _checked_nodes(self):
        """``[(node_name, native_type), ...]`` for the checked rows (the bundle),
        in the table's display order."""
        return [(n, t) for (n, t) in self._scene_nodes if n in self._checked]

    def _compile_checkbox(self, row):
        """The Compile ``QCheckBox`` hosted in col 0's cell widget, or None."""
        w = self._table.cellWidget(row, _COL_CHECK)
        if w is None:
            return None
        return w.findChild(QCheckBox)

    def _on_row_cell_clicked(self, row: int, col: int) -> None:
        """Click anywhere on a row's TEXT cells toggles that row's Compile
        checkbox (and thus the whole-row highlight) -- a big, easy hit target.

        Clicks on the two checkbox-widget columns (Compile, Data) are left to
        those checkboxes' own handlers so they are never double-toggled."""
        if col in (_COL_CHECK, _COL_PERSIST):
            return
        cb = self._compile_checkbox(row)
        if cb is not None and cb.isEnabled():
            cb.toggle()  # fires toggled -> _on_check_toggled -> set + highlight

    def _on_check_toggled(self, col, name, row, checked) -> None:
        """A row checkbox (a cell widget) was toggled by the user. Col 0 updates
        the bundle set (and re-renders that row's Data cell so its enabled state
        tracks bundle membership live); the Data column records an explicit
        per-node persistent uncheck. Programmatic state changes never reach here
        -- ``_make_check_cell`` sets state before connecting the signal."""
        if not name:
            return
        if col == _COL_CHECK:
            if checked:
                self._checked.add(name)
            else:
                self._checked.discard(name)
            try:
                # Re-render the Data box first (its enabled state tracks bundle
                # membership), THEN restyle the whole row so the checked-row
                # highlight lands on the freshly-built widget.
                self._render_persistent_cell(row, name)
                self._apply_row_style(row, checked)
            except Exception:
                pass
        elif col == _COL_PERSIST:  # track only EXPLICIT unchecks (default=bake)
            if checked:
                self._persistent_unchecked.discard(name)
            else:
                self._persistent_unchecked.add(name)

    def _unique_row_name(self, base: str) -> str:
        """A display name for a new file row that doesn't collide with a scene
        node or another file row (names key ``_checked`` / ``_row_by_type``, so a
        clash would silently merge two rows). Appends `` (2)``, `` (3)``…."""
        existing = {n for (n, _t) in self._scene_nodes} | set(self._file_rows)
        name     = base or "imported"
        if name not in existing:
            return name
        i = 2
        while ("%s (%d)" % (name, i)) in existing:
            i += 1
        return "%s (%d)" % (name, i)

    @staticmethod
    def _disambiguate_file_rows(file_rows, checked, persistent_unchecked,
                               scene_names):
        """Rename any file row whose name now collides with a LIVE scene node so
        the genuine scene node is never silently compiled from a stale .mpn.

        A file row added BEFORE a same-named scene node exists wouldn't be
        caught by ``_unique_row_name`` (the scene node didn't exist yet); this
        re-runs on every rescan. Returns ``(new_file_rows, new_checked,
        new_persistent_unchecked)`` with BOTH the ``_checked`` AND the per-node
        ``_persistent_unchecked`` entries remapped to the renamed name -- so an
        explicit persistent uncheck FOLLOWS its row and can never attach to an
        unrelated node that later takes the freed name (a silent data-loss
        class). Idempotent: a non-colliding set is returned unchanged."""
        used        = set(scene_names)
        new_rows    = {}
        new_checked = set(checked)
        new_persist = set(persistent_unchecked)
        for fname, val in file_rows.items():
            name = fname
            if name in used:
                base = name
                i    = 2
                name = "%s (%d)" % (base, i)
                while name in used:
                    i += 1
                    name = "%s (%d)" % (base, i)
                if fname in new_checked:
                    new_checked.discard(fname)
                    new_checked.add(name)
                if fname in new_persist:
                    new_persist.discard(fname)
                    new_persist.add(name)
            new_rows[name] = val
            used.add(name)
        return new_rows, new_checked, new_persist

    def _on_add_mpn(self) -> None:
        """Pick external .mpn templates and add them as compile rows WITHOUT
        creating any scene node. Each file is read for its node type (and a
        pickle-trust decision); the row routes through the pure adapter at
        compile time."""
        if self._busy:
            return
        start = self._out_edit.text().strip() or os.path.expanduser("~")
        chosen = QFileDialog.getOpenFileNames(
            self, "Add .mpn files", start, "MPyNode templates (*.mpn)")
        # PySide returns ``(files, selectedFilter)``; tolerate a bare list too.
        paths = chosen[0] if isinstance(chosen, tuple) else chosen
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode.native.spec import mpn_spec_adapter

        # Gate the (RCE-capable) pickle decode behind a per-file trust prompt --
        # never force trusted=True from the UI. One prompt instance handles all
        # picked files, so its "always" choice persists across them.
        prompt  = _mpn_trust_prompt()
        added   = []
        skipped = []
        # Dedup by IDENTITY = the sanitized native ``node_type_name`` the bundle
        # keys on (what _dedup_specs_by_type collapses). A node already in
        # another .mpn row is a duplicate -- as is re-adding the same file.
        existing_ids = {val[3] for val in self._file_rows.values()
                        if len(val) > 3 and val[3]}
        for path in paths or []:
            try:
                data = load_mpn(path, prompt_fn=prompt)
            except Exception as exc:
                QMessageBox.warning(
                    self, "Cannot Read .mpn",
                    "Could not read '%s':\n%s" % (path, exc))
                continue
            native_type = data.get("native_type") or ""
            # Dual-read the display name: new-key .mpn payloads carry ``node_name``
            # (the old key was ``source_name``); fall back to the file stem.
            base = (data.get("node_name") or data.get("source_name")
                    or os.path.splitext(os.path.basename(path))[0])
            try:
                spec      = mpn_spec_adapter.spec_from_mpn_payload(data)
                node_type = (spec.get("suggested") or {}).get("node_type_name")
            except Exception as exc:
                # Loaded but not adaptable to a compile spec (corrupted /
                # hand-edited .mpn). Never add an un-buildable row -- it would
                # abort the WHOLE compile when it re-adapts.
                QMessageBox.warning(
                    self, "Cannot Adapt .mpn",
                    "Could not build a compile spec from '%s':\n%s" % (path, exc))
                continue
            if node_type and node_type in existing_ids:
                skipped.append((base, path))
                continue
            name           = self._unique_row_name(base)
            has_persistent = bool(data.get("stored_vars"))
            # The .mpn's ACTUAL Class short name (empty when class-less), so the
            # Class column reads faithfully instead of reverse-engineering one
            # from the node type -- which would mislabel a class-less .mpn.
            class_path  = data.get("class_path") or data.get("py_class") or ""
            class_short = class_path.rpartition(".")[2] if class_path else ""
            self._file_rows[name] = (path, native_type, has_persistent,
                                     node_type, class_short)
            self._checked.add(name)
            if node_type:
                existing_ids.add(node_type)
            added.append(name)
        if skipped:
            QMessageBox.information(
                self, "Duplicate Nodes Skipped",
                "These .mpn file(s) define a node already in the list and were "
                "skipped (each node is unique in one plugin):\n  %s"
                % "\n  ".join("%s  (%s)" % (b, p) for (b, p) in skipped))
        if added:
            self._refresh_table()

    def _set_all_checked(self, checked: bool) -> None:
        """Check or uncheck every node, then re-render. No-op while busy."""
        if self._busy:
            return
        if checked:
            self._checked = {n for (n, _t) in self._scene_nodes}
        else:
            self._checked = set()
        self._refresh_table()

    @staticmethod
    def _plan_compile_rows(entries):
        """Given ``[(row, type_name), ...]`` in compile order, return
        ``(row_by_type, dropped_rows)``: the FIRST row per native type maps the
        progress key; later rows with a duplicate type are dropped (their spec
        is deduped away by ``_dedup_specs_by_type``) so they get a terminal
        'skipped' label instead of a stuck 'queued'."""
        row_by_type  = {}
        dropped_rows = []
        for (row, type_name) in entries:
            if type_name in row_by_type:
                dropped_rows.append(row)
            else:
                row_by_type[type_name] = row
        return row_by_type, dropped_rows

    @staticmethod
    def _dedup_specs_by_type(specs):
        """Collapse specs sharing a native type_name to ONE per type -- the
        bundler would otherwise overwrite fragments / Maya would reject a
        duplicate registerNode. In the per-Class model multiple INSTANCES of one
        Class legitimately share a type, so this is normal, not an error.

        Returns ``(unique_specs, identical_dropped, diverged_dropped)``:
        ``identical_dropped`` is a list of TYPE NAMES for byte-identical instances
        collapsed with no loss (silent); ``diverged_dropped`` is a list of the
        DROPPED SPECS whose code differed from the kept representative (only the
        first kept) -- returned whole so the caller can key an acknowledgment by
        ``source_node`` and still show the type name."""
        from mpynode.native.spec.divergence import specs_are_identical

        kept_by_type      = {}
        unique            = []
        identical_dropped = []
        diverged_dropped  = []
        for spec in specs:
            tn = (spec.get("suggested") or {}).get("node_type_name")
            if tn in kept_by_type:
                if specs_are_identical(spec, kept_by_type[tn]):
                    identical_dropped.append(tn)
                else:
                    diverged_dropped.append(spec)
                continue
            kept_by_type[tn] = spec
            unique.append(spec)
        return unique, identical_dropped, diverged_dropped

    # ------------------------------------------------------------------
    # Per-Class divergence pre-flight (must-fix #1)
    # ------------------------------------------------------------------

    def _scene_wrappers_for(self, checked):
        """Wrap the live SCENE nodes among ``checked`` (skipping external .mpn
        rows, which have no scene node). Returns a list of wrappers (Nones for
        anything that fails to wrap are filtered by ``divergence``)."""
        from mpynode._node_registry import wrap_node

        out = []
        for (name, native_type) in checked:
            if name in self._file_rows:
                continue
            try:
                out.append(wrap_node(name, native_type))
            except Exception:
                out.append(None)
        return out

    def _divergence_report(self, checked):
        """``{class_path: {hash: [wrapper, ...]}}`` for checked scene Classes
        whose instances have diverged (Duplicate-then-edit). Empty ⇒ safe."""
        from mpynode.native.spec.divergence import diverged_classes

        return diverged_classes(self._scene_wrappers_for(checked))

    @staticmethod
    def _scene_class_names():
        """Every short Class name a fork must avoid, so a fork picks a genuinely
        unused ``<Base>N`` and never collides with an existing Class.

        Unions two sources: (1) Classes with a live scene instance, and (2) every
        Class already SYNTHESIZED in-memory under ``mpynode_user`` -- those
        persist across scene opens / File>New and are never pruned, so a fork
        landing on an orphaned name whose base differs would make ``stamp_class``
        raise and the fork silently fail."""
        names = set()
        # (2) in-memory synthesized classes (orphans included).
        try:
            from mpynode._common.io.user_classes import ensure_module

            for nm, val in vars(ensure_module()).items():
                if isinstance(val, type):
                    names.add(nm)
        except Exception:
            pass
        # (1) Classes with a live scene instance.
        from mpynode._node_registry import all_native_types
        from mpynode.wrappers._mpy_node import _read_py_class

        try:
            import maya.cmds as mc
        except Exception:
            return names
        for nt in all_native_types():
            try:
                nodes = mc.ls(type=nt) or []
            except Exception:
                continue
            for n in nodes:
                pc = _read_py_class(n)
                if pc:
                    names.add(pc.rpartition(".")[2])
        return names

    def _apply_fork_plan(self, plan, nt_by_name):
        """Stamp each forked instance onto its new Class, as ONE undo chunk.
        ``plan`` is ``divergence.plan_forks`` output; ``nt_by_name`` maps a node
        name to its native type. Returns the number of nodes re-stamped."""
        import maya.cmds as mc
        from mpynode._common.io.user_classes import stamp_class

        forks = [(f["class_name"], n)
                 for entry in plan for f in entry["forks"] for n in f["nodes"]]
        if not forks:
            return 0
        count  = 0
        opened = False
        try:
            if len(forks) > 1:
                mc.undoInfo(openChunk=True)
                opened = True
            for (new_name, node_name) in forks:
                nt = nt_by_name.get(node_name)
                if not nt:
                    continue
                try:
                    if stamp_class(node_name, nt, new_name):
                        count += 1
                except Exception:
                    pass
        finally:
            if opened:
                mc.undoInfo(closeChunk=True)
        return count

    def _prompt_divergence_choice(self, diverged):
        """Ask how to resolve diverged Classes. Returns ``"fork"`` /
        ``"representative"`` / ``"cancel"``. Isolated so tests can stub it."""
        lines = []
        for class_path, parts in diverged.items():
            short    = class_path.rpartition(".")[2] or class_path
            variants = len(parts)
            insts    = sum(len(v) for v in parts.values())
            lines.append("  • %s — %d instances in %d different code variants"
                         % (short, insts, variants))
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Diverged Class Instances")
        box.setText(
            "Some selected Classes have instances whose code has DIVERGED.\n"
            "A Class compiles to ONE native type, so only one code variant per "
            "Class can be kept.\n\n" + "\n".join(lines))
        box.setInformativeText(
            "Fork: give each extra variant its own new Class so every variant "
            "compiles (nothing lost).\n"
            "Compile first only: keep one variant per Class and DROP the "
            "others' code.")
        fork_btn = box.addButton("Fork divergent instances",
                                  QMessageBox.AcceptRole)
        rep_btn = box.addButton("Compile first variant only",
                                QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(fork_btn)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is fork_btn:
            return "fork"
        if clicked is rep_btn:
            return "representative"
        return "cancel"

    def _warn(self, title, text):
        """Show a modal warning (isolated so headless tests can stub it)."""
        QMessageBox.warning(self, title, text)

    def _prompt_class_name_for(self, name):
        """Prompt for a PascalCase Class name for the class-less node ``name``.

        Returns the entered name, ``None`` if the user cancelled (or left it
        empty). Isolated so headless tests can stub it (mirrors
        ``_prompt_divergence_choice``)."""
        # Hard-wrap the prompt: QInputDialog's label does not word-wrap, so a
        # single long line would stretch the window very wide (one entry field).
        text, ok = QInputDialog.getText(
            self, "Name Class",
            "'%s' has no Class.\n\n"
            "A compiled node's type is derived from its Class, so a class-less\n"
            "node would take its type from the (renameable) node name.\n"
            "Enter a PascalCase Class name to compile it, or Cancel to skip it:"
            % name)
        if not ok:
            return None
        return (text or "").strip() or None

    def _apply_classless_names(self, to_stamp):
        """Stamp each ``(node_name, native_type, class_name)`` in ``to_stamp``
        onto its new Class, as ONE undo chunk. Returns the number stamped."""
        import maya.cmds as mc
        from mpynode._common.io.user_classes import stamp_class

        if not to_stamp:
            return 0
        count  = 0
        opened = False
        try:
            if len(to_stamp) > 1:
                mc.undoInfo(openChunk=True)
                opened = True
            for (node_name, native_type, class_name) in to_stamp:
                try:
                    if stamp_class(node_name, native_type, class_name):
                        count += 1
                except Exception:
                    pass
        finally:
            if opened:
                mc.undoInfo(closeChunk=True)
        return count

    def _resolve_classless(self, checked):
        """Refuse to silently compile a class-less node (must-fix #2).

        A node with no Class would derive its compiled type from its renameable
        instance name -- the original identity footgun. For each checked SCENE
        node with no ``class_path``: prompt for a PascalCase Class name and stamp
        it (synthesize + set_py_class), or -- if the user cancels / enters an
        invalid name -- EXCLUDE that node from this compile (uncheck it). External
        ``.mpn`` rows are skipped (they carry their own baked identity).

        Runs BEFORE the bake confirm + divergence pre-flight so the newly-assigned
        Class feeds correct per-Class derivation and grouping. Returns the number
        of nodes NEWLY named a Class this call (0 = none) -- the caller uses a
        non-zero count to stop after naming and await a second, deliberate Compile
        click (typing a Class name + Enter must never auto-compile). Naming/
        exclusion is the user's explicit, non-destructive choice, so there is no
        whole-compile cancel from here."""
        from mpynode._common.io.py_export import is_pascal_class_name
        from mpynode.wrappers._mpy_node import _read_py_class

        to_stamp   = []  # (name, native_type, class_name)
        to_exclude = []  # names
        for (name, native_type) in checked:
            if name in self._file_rows:
                continue
            try:
                has_class = bool(_read_py_class(name))
            except Exception:
                has_class = False
            if has_class:
                continue
            entered = self._prompt_class_name_for(name)
            if entered is None:
                to_exclude.append(name)  # cancelled / empty -> skip this node
                continue
            if not is_pascal_class_name(entered):
                self._warn(
                    "Invalid Class Name",
                    "'%s' is not a valid PascalCase Class name; skipping %s."
                    % (entered, name))
                to_exclude.append(name)
                continue
            to_stamp.append((name, native_type, entered))

        named         = 0
        stamped_names = []
        if to_stamp:
            self._apply_classless_names(to_stamp)
            # Verify each stamp took; a name clash (same name, different base)
            # can make it fail. A still-class-less node must NOT fall through to
            # an instance-name compile -- exclude + warn instead.
            for (name, _nt, class_name) in to_stamp:
                if not (_read_py_class(name) or ""):
                    self._warn(
                        "Class Not Assigned",
                        "Could not assign Class '%s' to %s; excluding it from "
                        "this compile." % (class_name, name))
                    to_exclude.append(name)
                else:
                    named += 1
                    stamped_names.append(name)

        if to_exclude:
            for name in to_exclude:
                self._checked.discard(name)
        if to_stamp or to_exclude:
            self._refresh_table()
        # Notify the designer so a panel showing a just-stamped node re-syncs its
        # Identity render (#68). Only the VERIFIED-stamped names, never excluded.
        if stamped_names:
            try:
                self.classesStamped.emit(list(stamped_names))
            except Exception:
                pass
        return named

    def _resolve_divergence(self, checked):
        """Pre-flight the checked scene nodes for per-Class divergence and
        resolve it before spec extraction. Returns True to proceed, False if the
        user cancelled (or a fork could not be fully applied). May mutate the
        scene (fork) inside one undo chunk."""
        from mpynode.native.spec.divergence import plan_forks

        self._acknowledged_diverged_nodes = set()
        diverged                          = self._divergence_report(checked)
        if not diverged:
            return True
        choice = self._prompt_divergence_choice(diverged)
        if choice == "cancel":
            return False
        if choice == "representative":
            # User accepts that these specific diverged instances' code is
            # dropped -- acknowledge them BY NODE so the post-dedup warning is
            # muted for exactly these, not for unrelated types.
            for parts in diverged.values():
                for grp in parts.values():
                    for w in grp:
                        try:
                            self._acknowledged_diverged_nodes.add(w.get_name())
                        except Exception:
                            pass
            return True
        # Fork: assign each extra variant its own Class, then proceed. After
        # this the previously-diverged instances extract to DISTINCT types.
        nt_by_name = {n: t for (n, t) in checked}
        plan       = plan_forks(diverged, taken_names=self._scene_class_names())
        expected   = sum(len(f["nodes"]) for entry in plan for f in entry["forks"])
        applied    = self._apply_fork_plan(plan, nt_by_name)
        if applied != expected:
            # A fork target name clashed with a different-base Class (or the node
            # failed to wrap). Do NOT fall through to a lossy compile -- stop and
            # let the user resolve it (rename the Class, or fork manually).
            self._warn(
                "Fork Incomplete",
                "Could not fork all divergent instances (%d of %d succeeded). A "
                "target Class name is likely already used by a different node "
                "type. Rename the Class (or reclassify the instance from the "
                "scene tree), then compile again." % (applied, expected))
            return False
        return True

    # ------------------------------------------------------------------
    # Compile / cancel
    # ------------------------------------------------------------------

    def _preflight_unload_if_loaded(self, plugin_name) -> bool:
        """If a plugin with the target name is already loaded, offer to unload it
        before recompiling (#71). Returns False ONLY if the user cancels the whole
        compile; True to proceed (nothing loaded, unloaded, or chose to continue).
        Main-thread only -- touches ``maya.cmds`` (the worker thread cannot)."""
        try:
            import maya.cmds as mc
            from mpynode.native.toolchain import toolchain

            base = plugin_name + toolchain.plugin_ext()
        except Exception:
            return True
        try:
            loaded = bool(mc.pluginInfo(base, q=True, loaded=True))
        except Exception:
            loaded = False
        if not loaded:
            return True
        resp = QMessageBox.question(
            self, "Plugin Already Loaded",
            "A plugin named '%s' is already loaded. Recompiling will overwrite "
            "it. Unload it now so the rebuild is clean?\n\n(If it has nodes in "
            "the scene, unload may fail -- Cancel and delete them first.)" % base,
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes)
        if resp == QMessageBox.Cancel:
            return False
        if resp == QMessageBox.Yes:
            try:
                mc.unloadPlugin(base)
            except Exception as exc:
                QMessageBox.warning(
                    self, "Unload Failed",
                    "Could not unload '%s': %s\n\nContinuing; the rebuild may keep "
                    "the old code resident until you reload it." % (base, exc))
        return True

    def _on_compile(self) -> None:
        """Validate, extract specs on the MAIN thread, then start the worker.

        Spec extraction touches live nodes, so it MUST happen here (the GUI/
        main thread), not in the controller's worker — Maya's API is not
        thread-safe (design "threading spine", step 1).
        """
        if self._busy:
            return

        # A fresh run supersedes any prior AI hand-off offer -- including the
        # per-node green-lights, which are consent for THAT build's C++ only.
        self._ai_btn.setVisible(False)
        self._last_ai_result  = None
        self._last_ai_out_dir = None
        self._reset_greenlights()

        plugin_name = _sanitize_plugin_name(self._name_edit.text())
        if not plugin_name:
            QMessageBox.warning(self, "Invalid Plugin Name",
                                "Enter a valid plugin name (a C identifier).")
            return
        # Reflect the sanitized name back so the user sees what's used.
        if plugin_name != self._name_edit.text():
            self._name_edit.setText(plugin_name)

        out_dir = self._out_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "No Output Folder",
                                "Choose an output folder for the plugin.")
            return

        checked = self._checked_nodes()
        if not checked:
            QMessageBox.warning(self, "Nothing to Compile",
                                "Check at least one node to compile.")
            return

        # --- class-less naming gate (must-fix #2) ------------------------
        # A class-less node would compile to a type derived from its renameable
        # instance name (the identity footgun): name a Class or exclude it. Runs
        # FIRST so the assigned Class feeds the bake + divergence steps below.
        named = 0
        try:
            named = self._resolve_classless(checked)
        except Exception as exc:
            QMessageBox.warning(
                self, "Class Check Skipped",
                "Could not check for class-less nodes:\n%s" % exc)
        checked = self._checked_nodes()  # the gate may have excluded nodes
        if not checked:
            self._warn(
                "Nothing to Compile",
                "Every checked node was class-less and skipped. Name a Class "
                "(type a PascalCase name into the Identity panel, or right-click "
                "the node ▸ Name Class) to compile it.")
            return
        # Naming a Class is its OWN deliberate step -- typing a name + Enter must
        # not auto-compile. Stamp here, then stop; the user presses Compile again.
        if named:
            self._warn(
                "Class Named",
                "Named a Class for %d node(s). Review the list and click "
                "Compile again to build." % named)
            return

        # --- persistent-data bake confirm --------------------------------
        # Baking embeds a node's current stored values as the compiled node's
        # defaults, so confirm first (skipped when nothing would bake).
        #
        # This runs BEFORE the divergence pre-flight for two reasons:
        #  1. The divergence "Fork" choice MUTATES the scene (set_py_class), so
        #     every user-abortable gate must sit ahead of it, or declining here
        #     would leave a "forked but nothing compiled" scene.
        #  2. The dialog is non-modal, so the render-time persistence cache can
        #     go stale (a node may gain stored vars out-of-band). Drop it and
        #     re-read live so the confirm reflects the current scene.
        self._has_persistent = {}
        baking               = self._nodes_baking_persistent(checked)
        if baking and not self._confirm_bake_persistent(baking):
            return  # user declined the bake

        # --- per-Class divergence pre-flight (must-fix #1) ---------------
        # Instances of one Class compile to ONE native type but carry code per
        # instance, so Duplicate-then-edit can make siblings diverge. Resolve it
        # (fork them, or compile a single representative) BEFORE extracting
        # specs, so what follows is a clean one-type-per-Class build.
        try:
            if not self._resolve_divergence(checked):
                return  # user cancelled
        except Exception as exc:
            # Detection must never block a compile: warn and fall through to the
            # controller's own divergence backstop.
            QMessageBox.warning(
                self, "Divergence Check Skipped",
                "Could not check for diverged Class instances:\n%s" % exc)

        # --- extract specs on the main thread (Maya is live here) --------
        specs             = []
        self._row_by_type = {}
        try:
            from mpynode.native.ai import porter
            from mpynode.native.spec import spec_extractor
        except Exception as exc:
            QMessageBox.critical(self, "Compile Unavailable",
                                 "Native compile modules failed to import:\n%s"
                                 % exc)
            return

        # Map node name -> its row in the full (all-scene) table so progress
        # events (keyed by the sanitized type_name) update the correct row.
        row_by_name = {n: i for i, (n, _t) in enumerate(self._scene_nodes)}
        # Global "Ignore persistent data" overrides every per-node choice. Read
        # once here so each spec below is stamped consistently.
        global_ignore = self._global_ignore_persistent()
        entries       = []  # (row, type_name) per checked node, in compile order
        for (node_name, _native_type) in checked:
            row = row_by_name.get(node_name, 0)
            try:
                if node_name in self._file_rows:
                    # External .mpn row: build the spec from the file via the pure
                    # adapter -- no scene node is created.
                    from mpynode._common.io.mpn_io import load_mpn
                    from mpynode.native.spec import mpn_spec_adapter

                    path = self._file_rows[node_name][0]
                    spec = mpn_spec_adapter.spec_from_mpn_payload(
                        load_mpn(path, prompt_fn=_mpn_trust_prompt()))
                else:
                    spec = spec_extractor.extract_spec(node_name)
            except Exception as exc:
                QMessageBox.critical(
                    self, "Spec Extraction Failed",
                    "Could not read node '%s':\n%s" % (node_name, exc))
                return
            # Normalize the type name exactly as the controller will (idempotent
            # apply_type_name), so progress events keyed by it map to this row.
            try:
                suggested = (spec.get("suggested") or {})
                porter.apply_type_name(spec, suggested.get("node_type_name"))
                type_name = spec["suggested"]["node_type_name"]
            except Exception:
                type_name = node_name
            # Per-node persistent bake: stamp this spec's own override (the
            # engine's per-spec value wins over the global default). ``None`` ->
            # leave unset (global-ignore strips all uniformly via the default).
            choice = self._bake_choice_for(
                node_name, global_ignore, self._persistent_unchecked)
            if choice is not None:
                spec["bake_persistent"] = choice
            self._set_cell(row, _COL_TYPE, type_name)
            entries.append((row, type_name))
            specs.append(spec)

        # Two checked nodes can sanitize to the SAME native type_name; the
        # bundler would collide their fragments and Maya would reject the
        # duplicate registerNode. The FIRST row per type drives progress; later
        # duplicates are relabeled, else they sit at 'queued' forever.
        self._row_by_type, dropped_rows = self._plan_compile_rows(entries)
        for kept_row in self._row_by_type.values():
            self._set_cell(kept_row, _COL_STATUS, "queued")
        for dropped_row in dropped_rows:
            self._set_cell(dropped_row, _COL_STATUS, "collapsed (same Class)")

        # Collapse instances of one Class to a single compiled type. Identical
        # instances collapse silently (normal). Warn about a LOSSY collapse
        # (diverged code) UNLESS the user acknowledged that exact node in the
        # pre-flight -- so a spec-level divergence the node-level check can't see
        # (mPyFile is_array, an external .mpn row) is still surfaced.
        specs, _identical_dropped, diverged_dropped = \
            self._dedup_specs_by_type(specs)
        unacked = [s for s in diverged_dropped
                   if s.get("source_node") not in self._acknowledged_diverged_nodes]
        if unacked:
            types = sorted({(s.get("suggested") or {}).get("node_type_name")
                            for s in unacked} - {None})
            QMessageBox.warning(
                self, "Diverged Node Types",
                "These node type(s) had instances with DIFFERENT code; only the "
                "first was compiled and the rest were dropped:\n  %s\n\nFork the "
                "divergent instances into their own Classes, or rename the "
                "colliding node/Class, to compile them all."
                % ", ".join(types))

        # --- start the worker -------------------------------------------
        from mpynode.native.toolchain import (
            CompileController,
            subprocess_verify_fn,
        )

        if self._controller is None:
            self._controller = CompileController(progress_cb=self._on_progress)
        strict = self._strict_check.isChecked()
        # The three pipeline gates, resolved in one place (stage 3 implies stage
        # 2 and the authored tests -- see _sync_pipeline_gates).
        pipe = self._pipeline_options()
        # Authored @maya_test(s) run during verify when the user opts in, and
        # unconditionally when the optimizer runs (for a node whose pointwise
        # parity SKIPS they are its only gate). Run in the verify subprocess.
        run_tests = pipe["run_tests"]
        # Opt-in AI C++ optimizer (default OFF): threaded into the engine's (c.6)
        # post-port step; a rewrite ships only if it still passes parity AND is
        # measurably faster, else the original .cpp is kept.
        optimize  = pipe["optimize"]
        ai_assist = pipe["ai_assist"]
        # Post-build sweep of the working dirs (object files, per-node port
        # scratch, the optimizer's _optscratch). build/source + build/stages are
        # never touched; unchecked keeps the lot for inspection.
        clean_scratch = pipe["clean_scratch"]
        # Keep each optimize round's compiled plug-in beside its source, so a
        # round can be LOADED rather than only read. ~90 KB per round.
        keep_intermediates = pipe["keep_intermediates"]
        # Per-run override of the optimizer's round count (engine default 2).
        os.environ["MPYNODE_OPT_ROUNDS"] = str(pipe["optimize_rounds"])
        # Global default passed to the engine. "Ignore persistent data" -> a
        # vanilla plugin (strip ALL nodes' stored vars); otherwise the per-spec
        # overrides stamped above decide each node (default = bake = legacy).
        bake_persistent = not global_ignore

        # Which Maya version(s) to build against:
        #   * no version row shown -> the running Maya, single build into out_dir.
        #   * exactly one checked -> single build against it, into out_dir.
        #   * two or more checked -> one build PER version into out_dir/<label>/,
        #     built + verified against that version's devkit.
        # The parity verify always runs in a SEPARATE mayapy process
        # (subprocess_verify_fn): it does file(new=True), which run in-process
        # would WIPE the user's live session.
        targets = self._checked_targets()
        if self._maya_targets and not targets:
            QMessageBox.warning(
                self, "No Maya Version",
                "Check at least one Maya version to build against.")
            return

        # #71: if a plugin with the target name is already loaded, recompiling
        # overwrites a loaded binary (Windows locks it; macOS keeps it stale until
        # reload). Offer to unload it first. Returns False only on user-cancel.
        if not self._preflight_unload_if_loaded(plugin_name):
            self._set_status_msg("Compile cancelled.")
            return

        # #65: apply the disable-able optimize-timeout preference to the env the
        # optimizer LLM call reads (MPYNODE_OPT_TIMEOUT). inf -> "off" = unbounded
        # (only user Cancel stops the call; a liveness heartbeat proves progress).
        try:
            from mpynode.ui import preferences

            _tmo = preferences.resolve_optimize_timeout()
            os.environ["MPYNODE_OPT_TIMEOUT"] = (
                "off" if _tmo == float("inf") else str(int(_tmo)))
        except Exception:
            pass

        self._set_busy(True)
        self._rail_reset(pipe)
        self._bundle_path = None
        # The Maya root a SINGLE build targeted (None for multi / no-target):
        # _on_finished uses it to avoid offering to load an ABI-mismatched bundle.
        self._build_target_root = None
        try:
            if len(targets) >= 2:
                self._set_status_msg(
                    "Compiling %d node(s) for %d Maya versions…"
                    % (len(specs), len(targets)))
                self._controller.start_multi(
                    specs, plugin_name, out_dir, targets,
                    strict=strict, verify=True,
                    verify_fn_for=lambda root: subprocess_verify_fn(
                        maya=root, run_authored_tests=run_tests),
                    bake_persistent=bake_persistent, optimize=optimize,
                    ai_assist=ai_assist, clean_scratch=clean_scratch,
                    keep_intermediates=keep_intermediates)
            else:
                # The one checked version, else the Maya we are ACTUALLY running
                # in, so the bundle ABI matches and the verify mayapy exists.
                maya_dir                = targets[0]["root"] if targets else _resolve_maya_dir()
                self._build_target_root = maya_dir
                maya_kw                 = {"maya": maya_dir} if maya_dir else {}
                self._set_status_msg("Compiling %d node(s)…" % len(specs))
                self._controller.start(specs, plugin_name, out_dir,
                                       strict=strict, verify=True,
                                       verify_fn=subprocess_verify_fn(
                                           run_authored_tests=run_tests,
                                           **maya_kw),
                                       bake_persistent    = bake_persistent,
                                       optimize           = optimize,
                                       ai_assist          = ai_assist,
                                       clean_scratch      = clean_scratch,
                                       keep_intermediates = keep_intermediates,
                                       **maya_kw)
        except RuntimeError as exc:
            # A run is already in progress (shouldn't happen — _busy guards).
            self._set_busy(False)
            QMessageBox.warning(self, "Already Running", str(exc))

    def _on_cancel(self) -> None:
        if self._controller is not None and self._busy:
            self._controller.cancel()
            self._set_status_msg("Cancelling…")
            self._cancel_btn.setEnabled(False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._compile_btn.setEnabled(not busy)
        self._cancel_btn.setEnabled(busy)
        # Lock the inputs during a run.
        self._name_edit.setEnabled(not busy)
        self._out_edit.setEnabled(not busy)
        self._browse_btn.setEnabled(not busy)
        self._strict_check.setEnabled(not busy)
        self._run_tests_check.setEnabled(not busy)
        self._optimize_check.setEnabled(not busy)
        self._select_all_btn.setEnabled(not busy)
        self._select_none_btn.setEnabled(not busy)
        self._refresh_btn.setEnabled(not busy)
        self._add_mpn_btn.setEnabled(not busy)
        self._ignore_persistent_check.setEnabled(not busy)
        self._assist_check.setEnabled(not busy)
        self._rounds_combo.setEnabled(not busy)
        self._keep_intermediates_check.setEnabled(not busy)
        self._clean_scratch_check.setEnabled(not busy)
        # Re-assert the stage implications AFTER the blanket re-enable above, or
        # finishing a run hands back an unchecked-able "AI assist" with optimize on.
        if not busy:
            self._sync_pipeline_gates()
        # Lock the per-version target checkboxes too.
        for _cb in getattr(self, "_maya_checks", {}).values():
            try:
                _cb.setEnabled(not busy)
            except Exception:
                pass
        # Lock the version Select All / None too (getattr-guarded: the whole
        # version section is omitted when no installs are detected).
        for _b in (getattr(self, "_ver_all_btn", None),
                   getattr(self, "_ver_none_btn", None)):
            if _b is not None:
                try:
                    _b.setEnabled(not busy)
                except Exception:
                    pass
        # Don't allow checkbox edits mid-compile (would desync _row_by_type).
        self._table.setEnabled(not busy)
        # (The Log toggle stays enabled during a run so the user can collapse
        # the pane while it streams.)
        if busy:
            # Stamp the run start (elapsed timer + finish summary), open an
            # empty log window, and spin.
            self._run_start = _now()
            self._clear_log()
            self._show_log(True)
            self._start_spinner()
        else:
            self._stop_spinner()

    # ------------------------------------------------------------------
    # Status spinner (animated "something is happening" feedback)
    # ------------------------------------------------------------------

    def _render_status(self) -> None:
        """Write the status label: ``<frame> <message>`` while spinning, else
        just the message. The single point that touches ``_status_label``.

        Guarded against a missing label: a queued QTimer tick can fire after the
        dialog is torn down, so a ``None`` (or already-deleted) label must be a
        no-op rather than an AttributeError -- matching ``_append_log`` /
        ``_show_log``."""
        if self._status_label is None:
            return
        msg = self._status_msg or ""
        if self._spin_running:
            frame = _SPIN_FRAMES[self._spin_i % len(_SPIN_FRAMES)]
            # A small elapsed timer rides next to the animated frame so a long
            # step (LLM port / clang++ link) shows it's still progressing.
            run_start = getattr(self, "_run_start", None)
            elapsed = (_format_elapsed(_now() - run_start)
                       if run_start is not None else "")
            if elapsed:
                self._status_label.setText(
                    ("%s %s  %s" % (frame, elapsed, msg)).rstrip())
            else:
                self._status_label.setText(("%s %s" % (frame, msg)).rstrip())
        else:
            self._status_label.setText(msg)

    def _set_status_msg(self, msg) -> None:
        """Set the canonical status message and repaint (keeps any spinner
        frame). Use this instead of ``_status_label.setText`` everywhere so the
        spinner remains the sole renderer of the label while busy."""
        self._status_msg = msg or ""
        self._render_status()

    def _tick_spinner(self) -> None:
        """QTimer slot: advance one animation frame."""
        self._spin_i = (self._spin_i + 1) % len(_SPIN_FRAMES)
        self._render_status()

    def _start_spinner(self) -> None:
        self._spin_running = True
        self._spin_i       = 0
        self._render_status()
        if self._spin_timer is not None:
            self._spin_timer.start(_SPIN_INTERVAL_MS)

    def _stop_spinner(self) -> None:
        self._spin_running = False
        if self._spin_timer is not None:
            self._spin_timer.stop()
        self._render_status()  # drop the frame, keep the final message

    # ------------------------------------------------------------------
    # Collapsible live compiler-output log
    # ------------------------------------------------------------------

    def _append_log(self, line) -> None:
        """Append one raw compiler/linker output line to the log pane.

        The single point every line goes through, so the wrap happens here once
        rather than in each emitter."""
        if self._log_view is not None:
            self._log_view.appendPlainText(_wrap_log_line(line))

    def _clear_log(self) -> None:
        if self._log_view is not None:
            self._log_view.clear()

    def _on_log_context_menu(self, pos) -> None:
        """Right-click menu for the compile log: Clear / Copy All -- mirrors the
        Node Designer log widget so the compile log is clearable too (#70)."""
        from mpynode.ui.qt_wrapper import QAction, QMenu

        menu         = QMenu(self._log_view)
        clear_action = QAction("Clear", menu)
        clear_action.triggered.connect(self._clear_log)
        menu.addAction(clear_action)
        copy_action = QAction("Copy All", menu)
        copy_action.triggered.connect(self._copy_log_all)
        menu.addAction(copy_action)
        menu.exec_(self._log_view.mapToGlobal(pos))

    def _copy_log_all(self) -> None:
        """Push the whole compile-log buffer to the clipboard (mirrors
        logger.py: lazy-import QGuiApplication from the bound Qt binding)."""
        if self._log_view is None:
            return
        try:
            try:
                from PySide6.QtGui import QGuiApplication
            except ImportError:
                from PySide2.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(self._log_view.toPlainText())
        except Exception:
            pass

    def _show_log(self, show: bool) -> None:
        """Show/hide the log pane and sync the toggle button's arrow."""
        self._log_shown = bool(show)
        if self._log_view is not None:
            self._log_view.setVisible(self._log_shown)
        if self._log_toggle_btn is not None:
            self._log_toggle_btn.setText(_log_toggle_text(self._log_shown))
            try:
                self._log_toggle_btn.setChecked(self._log_shown)
            except Exception:
                pass

    def _toggle_log(self) -> None:
        self._show_log(not self._log_shown)

    # ------------------------------------------------------------------
    # Progress bridge (worker thread -> GUI thread)
    # ------------------------------------------------------------------

    def _on_progress(self, event) -> None:
        """Controller callback. Runs on the WORKER thread — NO widget access.

        Only re-emit the queued Signal; ``_on_progress_main`` (GUI thread) does
        all the widget work.
        """
        self._progress.emit(event)

    @Slot(object)
    def _on_progress_main(self, event) -> None:
        """GUI-thread handler for one progress event (and the terminal 'done')."""
        if not isinstance(event, dict):
            return
        stage  = event.get("stage")
        node   = event.get("node")
        status = event.get("status")
        detail = event.get("detail") or ""
        i      = event.get("i") or 0
        n      = event.get("n") or 0

        # Live compiler/linker output streams to the log pane ONLY -- never the
        # status line/table (it would thrash the phase summary line by line).
        if stage == "log" and status == "line":
            self._append_log(detail)
            return

        # High-level narration -> log pane (a readable build story; the porter's
        # own streamed lines interleave between these).
        nline = self._narration_line(stage, status, node, detail, i, n)
        if nline is not None:
            self._append_log(nline)

        # Checkpoint strip: the same events, as five lights instead of prose.
        self._rail_apply(stage, status, detail)

        # A new Maya version started (multi-version build): each version rebuilds
        # every node, so reset the rows and track the version now building.
        if stage == "version":
            if status == "start":
                self._set_status_msg(detail or ("Compiling %s…" % node))
                for r in self._row_by_type.values():
                    self._set_cell(r, _COL_STATUS, "queued")
            return  # version events don't map to a node row

        # Status message (the spinner renders it; never write the label direct).
        if node and stage == "stage":
            # "<node>: stage ok" is not a sentence; a pipeline artifact reports
            # itself by name, and an unrecognised one stays quiet.
            what = self._STAGE_CELL.get(detail)
            if what:
                self._set_status_msg("%s: %s" % (node, what))
        elif node:
            self._set_status_msg("%s: %s %s" % (node, stage, status))
        elif detail:
            self._set_status_msg(detail)

        # Per-node table cell.
        if node is not None and node in self._row_by_type:
            cell = self._cell_text(stage, status, detail)
            if cell is not None:
                self._set_cell(self._row_by_type[node], _COL_STATUS, cell)

        # Terminal event — it came through the same queued Signal, so we are on
        # the GUI thread and completion is safe to handle right here.
        if stage == "done":
            self._on_finished()

    # A pipeline artifact landing on disk, as a row status / a log line. Any
    # other stage id returns None -- an unknown stage must leave the row alone
    # rather than write literal "stage ok" over its real build status.
    # `_cached` is the SAME artifact reached with no AI call this run: row status
    # and rail tick, but NO log line -- the cache-hit line already said so.
    _STAGE_CELL = {"1_transpiled": "transpiled",
                   "2_assisted": "AI-assisted",
                   "2_assisted_cached": "AI-assisted (cached)"}
    _STAGE_LINE = {"1_transpiled": "deterministic C++ written (no AI)",
                   "2_assisted": "AI filled the compute regions"}

    @staticmethod
    def _cell_text(stage, status, detail) -> str:
        """Short status string for a node row from a progress event.

        ``None`` means "say nothing" -- the caller must not touch the cell.
        """
        if stage == "stage":
            return CompileDialog._STAGE_CELL.get(detail)
        if stage == "preflight" and status == "fail":
            return "blocked: %s" % detail if detail else "blocked"
        if stage == "portability" and status == "fail":
            return "won't port: %s" % detail if detail else "won't port"
        if stage == "cache" and status == "hit":
            return "cached"
        if stage == "cache" and status == "miss":
            return "porting…"
        if stage == "port" and status == "start":
            return "porting…"
        if stage == "port" and status == "ok":
            return "ported"
        if stage in ("port", "assemble") and status == "fail":
            return "failed: %s" % detail if detail else "failed"
        if stage == "verify" and status == "ok":
            return "verified"
        if stage == "verify" and status == "fail":
            return "FAILED parity (%s)" % detail if detail else "FAILED parity"
        if stage == "verify" and status == "skip":
            # A skip is "built fine, just not parity-checked" (RNG, array/multi
            # attrs, or a harness error) -- surface WHY, and never as a failure.
            return ("compiled (verify skipped: %s)" % detail if detail
                    else "compiled (verify skipped)")
        if status == "abort":
            return "cancelled"
        return "%s %s" % (stage, status)

    @staticmethod
    def _narration_line(stage, status, node, detail, i=0, n=0):
        """A human, high-level log line for one progress event -- or ``None`` to
        say nothing. These read as a build story in the log pane and interleave
        with the porter's own streamed lines ("[name] generating C++
        skeleton...", "[name] requesting AI compute body...", compiler output).

        Raw ``log`` lines are appended verbatim elsewhere, so they return
        ``None`` here (no double-handling)."""
        if stage == "log":
            return None
        if stage == "stage":
            what = CompileDialog._STAGE_LINE.get(detail)
            return ("[%s] %s." % (node, what)) if what else None
        if stage == "version" and status == "start":
            return "\n=== %s ===" % (detail or node)
        if stage == "version" and status == "ok":
            return "  %s done." % node
        if stage == "version" and status == "fail":
            return "  %s FAILED." % node
        if stage == "preflight" and status == "fail":
            return "Pre-flight failed:\n%s" % detail
        if stage == "cache" and status == "hit":
            return "[%s] reusing cached C++ (no AI call)." % node
        if stage == "cache" and status == "miss":
            return ("[%s] no cache -- generating C++ and sending to AI for "
                    "translation..." % node)
        if stage == "port" and status == "ok":
            return "[%s] AI port compiled OK." % node
        if stage == "port" and status == "fail":
            return "[%s] AI port FAILED: %s" % (node, detail)
        if stage == "port" and status == "skip":
            # Plugin-wide (node is None): why the AI-assist checkpoint just went
            # grey-ticked. Without it the chip changes with no explanation.
            return ("%s." % detail) if detail else None
        if stage == "optimize":
            # The AI-optimizer's narration (baseline ms, speedup, kept-original
            # or skip reason) is carried in ``detail``, node name folded in --
            # so events fire with node=None and never clobber a row's status.
            return ("  [AI-optimize] %s" % detail) if detail else None
        if stage == "assemble" and status == "start":
            return "Linking native plugin..."
        if stage == "assemble" and status == "ok":
            return "Plugin linked."
        if stage == "assemble" and status == "fail":
            return "Plugin link FAILED: %s" % detail
        if stage == "verify" and status == "start":
            return "Parity-checking compiled node(s) vs Python..."
        if stage == "honesty" and status == "incomplete":
            return ("[%s] built, but the C++ marks work it could NOT translate: "
                    "%s" % (node, detail))
        if stage == "honesty" and status == "io":
            return ("[%s] the AI-written compute contains %s -- it was instructed "
                    "never to emit this. The bundle still shipped; review it."
                    % (node, detail))
        return None

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def _on_finished(self) -> None:
        """Run finished (the 'done' event fired). Read the controller result.

        Appends a completion summary to the compile log — a separator rule, a
        clear 'done' line with how long the build took, and the artifacts it
        generated (bundle / manifest / per-node ``.cpp`` and their locations on
        disk) — so the user sees exactly what was produced and where.
        """
        # Capture the end BEFORE _set_busy(False) (which stops the spinner) so
        # the elapsed time reflects the real finish moment.
        end = _now()
        self._set_busy(False)
        result = self._controller.result if self._controller is not None else None
        if not isinstance(result, dict):
            self._set_status_msg("Compile finished (no result).")
            return

        run_start = getattr(self, "_run_start", None)
        elapsed_str = (_format_elapsed(end - run_start)
                       if run_start is not None else "")

        # Offer the report as soon as there is one -- including after a FAILED
        # build, when it is most worth reading (how far each node got, and why).
        self._last_report_path = result.get("report_path")
        has_report = bool(self._last_report_path
                          and os.path.isfile(self._last_report_path))
        self._report_btn.setVisible(has_report)
        self._folder_btn.setVisible(has_report)

        # Multi-version result has a different shape (per-version sub-results).
        if result.get("multi"):
            self._on_finished_multi(result, elapsed_str)
            return

        ok            = bool(result.get("ok"))
        bundle_path   = result.get("bundle_path")
        manifest_path = result.get("manifest_path")
        plugin_name   = result.get("plugin_name")
        errors        = result.get("errors") or []
        rows          = result.get("nodes") or []

        # Before the ok/fail split: a run whose bundle failed to link is exactly
        # when "which nodes got faster, and by how much" is worth reading.
        self._stamp_optimize_results(result)

        # Honest success (#59): a result can carry ok=True with a bundle_path not
        # on disk (a phantom build). Never celebrate / offer to load one that
        # isn't there. os.path.exists handles a file OR dir bundle.
        bundle_exists = bool(bundle_path) and os.path.exists(bundle_path)
        if ok and bundle_path and not bundle_exists:
            errors = list(errors) + [
                "reported success but no bundle exists on disk: %s" % bundle_path]

        # ok=False can mean ONLY that the AI optimize step delivered nothing --
        # the controller sets this key for exactly that, and the bundle in
        # ``bundle_path`` still LINKED. Rendering it as a flat "Compile failed"
        # hid a real, loadable artifact and never offered to load it, so it
        # takes the built branch with the AI failure carried as a warning.
        ai_failed = str(result.get("ai_optimize_failed") or "")

        if (ok or ai_failed) and bundle_exists:
            self._bundle_path = bundle_path
            # Generated artifacts: the per-node .cpp sit next to the bundle.
            out_dir = os.path.dirname(bundle_path)
            sources = _generated_sources(out_dir, rows)
            # Per-node summary carries the verify verdict (pass/fail/maxerr or
            # the "did not run" reason), so parity is FIRST-CLASS and persistent
            # rather than a transient progress line. It never hard-blocks.
            from mpynode.ui.llm import compile_bridge

            node_lines    = compile_bridge.verify_summary_lines(result)
            command_lines = _companion_command_lines(result)
            companion_paths = [rec.get("path")
                               for rec in (result.get("companions") or [])
                               if rec.get("path")]
            n_built = sum(1 for r in rows
                          if r.get("build_status") in ("compiled", "transformed"))
            # ok=True can still carry NON-fatal errors (a best-effort dropped
            # node, a companion command set that failed to ship). Surface them as
            # summary warnings + a modal, so a command-loss isn't lost in the log.
            warning_lines = [str(e) for e in errors]
            for line in _summary_lines(True, elapsed_str, plugin_name,
                                       bundle_path, manifest_path, sources,
                                       node_lines, [], command_lines=command_lines,
                                       warning_lines=warning_lines):
                self._append_log(line)
            for oline in _optimize_summary_lines(result):
                self._append_log(oline)
            if ai_failed:
                self._append_log(
                    "AI optimize FAILED: %s -- the plugin LINKED and can be "
                    "loaded; it just ships the un-optimized C++." % ai_failed)
            in_clause   = (" in %s" % elapsed_str) if elapsed_str else ""
            warn_clause = (" (%d warning(s))" % len(errors)) if errors else ""
            self._set_status_msg(
                "Built %s%s (%d node(s))%s."
                % (os.path.basename(bundle_path), in_clause, n_built,
                   " -- AI optimize FAILED" if ai_failed else warn_clause))
            if errors:
                QMessageBox.warning(
                    self,
                    "Built, but AI optimize failed" if ai_failed
                    else "Built with warnings",
                    "The plugin built, but %d issue(s) need attention:\n\n%s"
                    % (len(errors), "\n".join(warning_lines)))
            # Only offer to load if the build targeted the RUNNING Maya -- a
            # bundle built for another version can't load in this session.
            if _verify_crashed(result):
                # #61: the sandbox parity verify CRASHED loading this bundle, so
                # loading it live could crash Maya the same way. Never offer to.
                self._append_log(
                    "Parity verification CRASHED while sandbox-loading the "
                    "compiled bundle -- NOT loading it into this live session "
                    "(loading it could crash Maya). Rebuild or inspect the node "
                    "before loading.")
                QMessageBox.warning(
                    self, "Load Skipped (unsafe)",
                    "Parity verification crashed while loading the compiled "
                    "bundle in a sandbox, so it was NOT loaded into this live "
                    "session (loading it could crash Maya the same way). Rebuild "
                    "or inspect the node before loading it.")
            elif self._should_offer_load(
                    getattr(self, "_build_target_root", None),
                    _resolve_maya_dir()):
                self._offer_load(bundle_path, companion_paths)
            else:
                self._append_log(
                    "Built for a non-running Maya version; load it from a "
                    "matching Maya session.")
            self._update_ai_button(result, out_dir)
        else:
            error_lines = [str(e) for e in errors]
            for line in _summary_lines(False, elapsed_str, plugin_name,
                                       bundle_path, manifest_path, [], [],
                                       error_lines):
                self._append_log(line)
            for oline in _optimize_summary_lines(result):
                self._append_log(oline)
            after = (" after %s" % elapsed_str) if elapsed_str else ""
            self._set_status_msg("Compile failed%s." % after)
            msg = "Compile failed."
            if errors:
                msg = "Compile failed:\n\n" + "\n".join(str(e) for e in errors)
            QMessageBox.warning(self, "Compile Failed", msg)
            self._update_ai_button(
                result, os.path.dirname(bundle_path) if bundle_path else None)

    def _update_ai_button(self, result, out_dir) -> None:
        """Show the "Fix with AI" button iff this result has something the
        assistant could help with (a node that didn't build, or that built but
        diverged from the Python reference). Stash the result so a later click
        can rebuild the hand-off without re-running the compile."""
        from mpynode.ui.llm import compile_bridge

        want = False
        try:
            want = compile_bridge.needs_ai(result)
        except Exception:
            want = False
        self._last_ai_result  = result if want else None
        self._last_ai_out_dir = out_dir if want else None
        self._rebuild_greenlight_rows(result if want else None)
        self._refresh_ai_button()
        if want:
            self._append_log(
                "Some node(s) need attention -- press \"Fix with AI\" to hand "
                "the report to the assistant and iterate toward a compiling, "
                "on-par C++ node, or green-light the ones you accept as-is.")

    # ---- per-node green-light (WS2 R2.2) ------------------------------

    @staticmethod
    def _row_key(row):
        """Stable per-node key for a result row. External .mpn rows have no
        scene node, so fall back to the compiled type name."""
        return (row or {}).get("source_node") or (row or {}).get("type_name")

    @staticmethod
    def _flagged_rows(result):
        """The rows the assistant would be asked about, worst-first and deduped.

        Uses only ``compile_bridge.classify``'s public buckets, so the dialog and
        the hand-off can never disagree about which nodes are flagged."""
        from mpynode.ui.llm import compile_bridge

        try:
            buckets = compile_bridge.classify(result)
        except Exception:
            return []
        out, seen = [], set()
        for name in ("dropped", "diverged", "incomplete", "unchecked"):
            for row in buckets.get(name) or []:
                if id(row) in seen:
                    continue
                seen.add(id(row))
                out.append((name, row))
        return out

    _GREENLIGHT_WHY = {
        "dropped":    "did not build",
        "diverged":   "built, but its output DIVERGED from the Python",
        "incomplete": "built, but the C++ marks work it could not translate",
        "unchecked":  "AI-ported, and nothing verified it",
    }

    def _reset_greenlights(self) -> None:
        """Drop the previous run's consent. A green-light is about ONE build's
        C++; carrying it into the next run would silently accept code the user
        has never seen."""
        self._greenlit = set()
        self._rebuild_greenlight_rows(None)

    def _greenlight_buttons(self) -> dict:
        """key -> the checkable Green-light button currently offered."""
        return dict(self._greenlight_btns)

    def _rebuild_greenlight_rows(self, result) -> None:
        """Re-render one Green-light row per flagged node (none when clean)."""
        for btn in self._greenlight_btns.values():
            try:
                btn.toggled.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._greenlight_btns = {}
        while self._greenlight_layout.count():
            item = self._greenlight_layout.takeAt(0)
            w    = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        flagged = self._flagged_rows(result) if result else []
        for kind, row in flagged:
            key = self._row_key(row)
            if not key:
                continue
            line = QHBoxLayout()
            line.setContentsMargins(0, 0, 0, 0)
            line.addWidget(self._dim("%s -- %s"
                                     % (key, self._GREENLIGHT_WHY[kind])))
            line.addStretch(1)
            btn = QPushButton("Green-light", self._greenlight_box)
            btn.setCheckable(True)
            btn.setChecked(key in self._greenlit)
            btn.setToolTip(
                "Accept this node's compiled C++ as it is. It already ships and "
                "stays editable; green-lighting only takes it OUT of the "
                "\"Fix with AI\" ask. Leave it off to keep iterating on it.")
            btn.toggled.connect(
                lambda on, k=key: self._on_greenlight_toggled(k, on))
            line.addWidget(btn)
            self._greenlight_btns[key] = btn
            holder                     = QWidget(self._greenlight_box)
            holder.setLayout(line)
            self._greenlight_layout.addWidget(holder)
        self._greenlight_box.setVisible(bool(self._greenlight_btns))

    def _on_greenlight_toggled(self, key, on) -> None:
        if on:
            self._greenlit.add(key)
        else:
            self._greenlit.discard(key)
        self._refresh_ai_button()

    def _pending_rows(self):
        """Flagged rows the user has NOT green-lit -- the AI's actual ask."""
        return [row for _kind, row in self._flagged_rows(self._last_ai_result)
                if self._row_key(row) not in self._greenlit]

    def _refresh_ai_button(self) -> None:
        """The AI ask exists only while some flagged node is still un-accepted."""
        self._ai_btn.setVisible(
            bool(self._last_ai_result) and bool(self._pending_rows()))

    def _on_fix_with_ai(self) -> None:
        """Build a hand-off from the last result and emit it for the designer to
        route to the assistant panel. The dialog stays decoupled from the panel
        (it only emits ``handoffToAssistant``)."""
        from mpynode.ui.llm import compile_bridge

        result = self._last_ai_result
        if not isinstance(result, dict):
            return
        log_tail = []
        if self._log_view is not None:
            log_tail = self._log_view.toPlainText().splitlines()[-40:]
        # Ask only about what the user has NOT accepted. A green-lit node is a
        # decision, not an omission -- carrying it in would have the assistant
        # "fix" C++ the user just signed off on. A shallow copy keeps the
        # controller's own result dict untouched.
        if self._greenlit:
            result = dict(result)
            result["nodes"] = [r for r in (result.get("nodes") or [])
                               if self._row_key(r) not in self._greenlit]
        handoff = compile_bridge.build_handoff(
            result, {"out_dir": self._last_ai_out_dir},
            log_tail=log_tail, kind="failure")
        self.handoffToAssistant.emit(handoff)

    def _on_finished_multi(self, result, elapsed_str) -> None:
        """Completion summary for a multi-version build: one line per Maya
        version (its output folder, or its failure), and an offer to load the
        build matching the RUNNING Maya (the only one this session can load)."""
        results = result.get("results") or []
        ok      = bool(result.get("ok"))

        def _sub_built(sub):
            # Honest per-version success (#59): ok AND the bundle exists on disk.
            # A version's ok=False can ALSO mean ONLY that its AI optimize step
            # delivered nothing while its bundle LINKED (compile_plugin_multi
            # forwards ``optimize`` to every per-version compile_plugin, which
            # sets this key for exactly that). Reporting that as a flat FAILED
            # hid a loadable artifact -- same rule as the single-build path.
            p = sub.get("bundle_path")
            return bool((sub.get("ok") or sub.get("ai_optimize_failed"))
                        and p and os.path.exists(p))

        n_ok      = sum(1 for r in results if _sub_built(r.get("result") or {}))
        in_clause = (" in %s" % elapsed_str) if elapsed_str else ""
        ai_failed = [r.get("label") for r in results
                     if (r.get("result") or {}).get("ai_optimize_failed")
                     and _sub_built(r.get("result") or {})]

        self._append_log("")
        self._append_log("=" * 56)
        head = ("All %d Maya version(s) built OK" % len(results) if ok
                else "Built %d/%d Maya version(s)" % (n_ok, len(results)))
        if ai_failed:
            head += " -- AI optimize FAILED: %s" % ", ".join(ai_failed)
        self._append_log("%s%s" % (head, in_clause))
        for r in results:
            sub   = r.get("result") or {}
            label = r.get("label")
            if _sub_built(sub):
                why = str(sub.get("ai_optimize_failed") or "")
                self._append_log(
                    "  %s  ->  %s%s"
                    % (label, sub["bundle_path"],
                       ("   [AI optimize FAILED: %s -- the plugin LINKED and "
                        "can be loaded; it just ships the un-optimized C++.]"
                        % why) if why else ""))
            else:
                errs = "; ".join(str(e) for e in (sub.get("errors") or []))
                self._append_log("  %s  ->  FAILED%s"
                                 % (label, (": %s" % errs) if errs else ""))
        self._set_status_msg("%s%s." % (head, in_clause))

        # Offer to load the version matching the running Maya (unambiguous; a
        # bundle built for another version can't load in this session).
        running = _resolve_maya_dir()
        if running:
            rr = os.path.abspath(running)
            for r in results:
                sub = r.get("result") or {}
                if (_sub_built(sub)
                        and os.path.abspath(r.get("root") or "") == rr):
                    self._bundle_path = sub["bundle_path"]
                    # #61: never offer to load a bundle whose sandbox parity
                    # verify CRASHED -- loading it live could crash Maya the same
                    # way (mirrors the single-build gate in _on_finished).
                    if _verify_crashed(sub):
                        self._append_log(
                            "Parity verification CRASHED while sandbox-loading "
                            "the compiled bundle -- NOT loading it into this "
                            "live session (loading it could crash Maya).")
                        QMessageBox.warning(
                            self, "Load Skipped (unsafe)",
                            "Parity verification crashed while loading the "
                            "compiled bundle in a sandbox, so it was NOT loaded "
                            "into this live session (loading it could crash Maya "
                            "the same way). Rebuild or inspect the node first.")
                        break
                    companion_paths = [rec.get("path")
                                       for rec in (sub.get("companions") or [])
                                       if rec.get("path")]
                    self._offer_load(sub["bundle_path"], companion_paths)
                    break

        if not ok:
            # Drive the modal off the SAME predicate as the log, so a version
            # that only lost its AI optimize (and is being offered to load) can
            # never also be named as a version that "failed to build".
            failed = [r.get("label") for r in results
                      if not _sub_built(r.get("result") or {})]
            if failed:
                QMessageBox.warning(
                    self, "Compile Failed",
                    "These Maya version(s) failed to build:\n  %s"
                    % ", ".join(failed))

    @staticmethod
    def _should_offer_load(target_root, running_root):
        """Whether to offer to load a freshly built bundle into THIS session.

        A bundle built against a Maya version OTHER than the running one can't
        load here (ABI mismatch), so only offer when the build target matches
        the running Maya. ``target_root`` None (legacy: built for the running
        Maya) or ``running_root`` None (can't tell) -> offer (unchanged
        behaviour)."""
        if not target_root or not running_root:
            return True
        return os.path.abspath(target_root) == os.path.abspath(running_root)

    def _offer_load(self, bundle_path: str, companion_paths=None) -> None:
        """Ask whether to load the built ``.bundle`` into the live session.

        Loads via ``load_or_reload_native_plugin`` (scene-safe): if a previous
        build of the same plugin is already loaded, it is unloaded first so the
        NEW code takes effect (the plain load-if-absent guard would silently keep
        stale code); and it NEVER calls file(new) -- the current scene is left
        intact. If the unload fails because the plugin still has nodes in the
        scene, that is surfaced as a warning rather than crashing.

        ``companion_paths`` are the sibling companion command plugins written
        beside the bundle. They are loaded AFTER the bundle (the bundle registers
        the compiled node type; the companion registers the commands that drive
        it), so ``maya.cmds.<command>()`` works once both are loaded.
        """
        resp = QMessageBox.question(
            self, "Load Plugin",
            "Built:\n%s\n\nLoad it into Maya now?" % bundle_path,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if resp != QMessageBox.Yes:
            # Say so. A silent return reads as unqualified success: the build IS
            # fine, but with no type registered "Convert Node to C++" stays grey.
            self._append_log(
                "Plug-in NOT loaded into this session: %s\n"
                "Its compiled node type is not registered here, so 'Convert "
                "Node to C++' stays disabled. Load it later from the Scene "
                "tab: right-click a node > Load Compiled Plug-in..."
                % bundle_path)
            return
        try:
            from mpynode._base.plugins import load_or_reload_native_plugin

            res = load_or_reload_native_plugin(bundle_path)
        except Exception as exc:
            QMessageBox.critical(self, "Load Failed",
                                 "Could not load the plugin:\n%s" % exc)
            return
        if res.get("error"):
            QMessageBox.warning(self, "Load Failed", res["error"])
            self._set_status_msg("Load failed: %s" % res.get("base"))
            return
        verb = "Reloaded" if res.get("reloaded") else "Loaded"
        # #63: "loaded" is necessary but not sufficient -- confirm the bundle
        # actually REGISTERED the compiled node type(s) the build recorded. A load
        # that registers nothing is a failed compile masquerading as success.
        try:
            from mpynode._base.plugins import validate_registered_types

            vres = validate_registered_types(bundle_path)
        except Exception:
            vres = {"ok": True}
        if not vres.get("ok"):
            QMessageBox.warning(
                self, "Loaded but Not Registered",
                vres.get("error")
                or ("%s loaded but did not register its compiled node type(s)."
                    % res.get("base")))
            self._set_status_msg(
                "%s %s (no node type registered)" % (verb, res.get("base")))
            return
        # Arm the compiled-geo UV-dirty bridge. Compiled mesh/curve/surface nodes
        # don't propagate a source UV-only edit across their geometry input, so
        # without this a moved UV leaves the output stale until the next time
        # change. The manifest names the compiled type(s) + geo kind, so coverage
        # is armed BEFORE the first instance exists (instance-based discovery
        # can't see a type with no nodes); a second sweep covers existing ones.
        # Non-fatal -- a load without the bridge is still a usable plugin.
        try:
            from mpynode._common.plugs import auto_dirty

            out_dir  = os.path.dirname(bundle_path)
            manifest = os.path.join(out_dir, "build", "manifest.json")
            auto_dirty.install_native_geo_coverage_from_manifest(manifest)
            auto_dirty.install_native_geo_coverage()
        except Exception:
            pass
        # Load the sibling companion command plugin(s) AFTER the bundle.
        comp_errs = []
        for cpath in companion_paths or []:
            try:
                from mpynode._base.plugins import load_or_reload_native_plugin

                cres = load_or_reload_native_plugin(cpath)
            except Exception as exc:
                comp_errs.append("%s: %s" % (os.path.basename(cpath), exc))
                continue
            if cres.get("error"):
                comp_errs.append(cres["error"])
        if comp_errs:
            QMessageBox.warning(
                self, "Companion Load Failed",
                "The plugin loaded, but a companion command plugin did not:\n\n"
                + "\n".join(comp_errs))
            self._set_status_msg(
                "%s %s (companion load failed)." % (verb, res.get("base")))
            return
        n_comp = len(companion_paths or [])
        suffix = (" + %d companion plugin(s)" % n_comp) if n_comp else ""
        self._set_status_msg("%s %s%s." % (verb, res.get("base"), suffix))

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        # If a run is in progress, cancel the worker before closing so it
        # doesn't keep porting against a dead dialog.
        if self._busy and self._controller is not None:
            self._controller.cancel()
        # Stop the spinner QTimer: otherwise it keeps firing on the hidden
        # (reused) dialog until 'done' -- wasteful, and a teardown race.
        self._stop_spinner()
        # Closing must NOT leave the reused dialog stuck "busy": the next open's
        # refresh_nodes() early-returns while busy and would re-show the previous
        # scene's node list. The worker's later 'done' re-clears it harmlessly.
        self._busy = False
        super().closeEvent(event)
