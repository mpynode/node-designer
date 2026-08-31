"""Preferences module \u2014 JSON-backed user preferences.

Lazy-loaded from ``~/mpynode/preferences.json`` on first access. Defaults
are baked in so the file doesn't need to exist for the app to work.

Public API:
  * ``get_pref(key, default=None)`` \u2014 read a value
  * ``set_pref(key, value)`` \u2014 write + persist + notify listeners
  * ``reset_to_defaults()`` \u2014 wipe back to DEFAULT_PREFS
  * ``editor_font()`` \u2014 build a QFont from saved family + size
  * ``register_change_listener(cb)`` / ``unregister_change_listener(cb)``
    \u2014 callbacks fire on every set_pref with (key, new_value)

This module is imported by:
  * ``editor_core.py::_initTextAttrs`` (font family + size)
  * AddAttr dialog ``_make_time_subframe`` (time auto-connect default)
  * Connect dialog ``_BaseConnectDialog._build_ui`` (Show all default)

All the call sites already have try/except ImportError fallbacks, so this
module appearing later in the load order doesn't break anything that ran
before \u2014 they pick up real prefs once we're imported.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Storage location \u2014 cross-platform user prefs dir.
# Keeping it Maya-version-agnostic so prefs survive Maya upgrades. Lives under
# the shared, VISIBLE per-user home (``~/mpynode``, override MPYNODE_HOME) so
# nothing is hidden from a first-time user (see mpynode._common.home).
# ---------------------------------------------------------------------------
from mpynode._common import home as _home

PREFS_PATH = _home.preferences_path()
PREFS_DIR = os.path.dirname(PREFS_PATH)


def _default_template_search_paths() -> list[str]:
    """The shipped default for ``template_search_paths``: the repo's
    ``templates/`` dir. Resolved the same way
    ``template_gallery._bundled_templates_root()`` resolves it
    (``$MPYNODE_ROOT/templates`` first, else walk up to the dir holding
    ``scripts/mpynode``). Always returns a 1-element list (the path need not
    exist yet -- existence filtering happens in template_search_paths())."""
    env_root = os.environ.get("MPYNODE_ROOT")
    if env_root:
        return [os.path.abspath(os.path.join(env_root, "templates"))]
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(d, "scripts", "mpynode")):
            return [os.path.join(d, "templates")]
        parent = os.path.dirname(d)
        if parent == d:
            return [os.path.join(d, "templates")]
        d = parent


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
# All known preference keys + their default values. ``get_pref(key)``
# falls back to this dict when the key isn't in the user's file.
DEFAULT_PREFS: dict[str, Any] = {
    # Editor
    "editor_font_family": "Courier",
    "editor_font_size": 10,  # in points
    # "jump to source" command; {file} and {line} are substituted with the
    # target path and 1-based line before it runs. EMPTY = auto-detect, i.e.
    # editor_launch.detect_default_editor_command() probes for an installed
    # editor (Cursor / VS Code / VSCodium / Sublime / PyCharm) at launch, so a
    # fresh install needs no configuration. A non-empty value overrides it.
    "external_editor_command": "",
    # What a fresh node's EMPTY code tabs (Init, Compute, Viewport, OSL,
    # Methods) show:
    #   "none"     -- blank tabs (start from scratch).
    #   "headers"  -- each empty tab is prefilled with an auto-generated
    #                 commented header. Display-only, never written to the node.
    # Any unrecognized value (incl. the retired "template") falls back to
    # "headers" -- see new_node_mode().
    "new_node_mode": "headers",
    # Folders scanned recursively for template folders (each holding a
    # template.mpn) by the "New from Template..." gallery. Defaults to the
    # bundled templates/ dir; a studio can add shared roots. Bad values fall
    # back to the default -- see template_search_paths().
    "template_search_paths": _default_template_search_paths(),
    # Where the AI porter's translated C++ is cached. BLANK is the normal case
    # and means "fall through": MPYNODE_PORT_CACHE, then [paths] port_cache,
    # then <home>/port_cache. This is the only location with a UI field, because
    # it is the only one that is a pure CACHE -- a wrong path costs a re-port,
    # where a wrong home would move the trust store and the type-id pins. A
    # value belonging to a DIFFERENT OS is ignored; see port_cache_dir_pref().
    "port_cache_dir": "",
    # AddAttr dialog
    "addattr_time_auto_connect": True,
    # Connect dialog
    "connect_dialog_show_all_default": False,
    # Hide pivots (rotatePivot* / scalePivot*) and *Limit* attrs by default.
    # Replaces the old "Show all attrs" toggle, which conflated noise hiding
    # with compound-parent hiding.
    "connect_dialog_hide_pivots_default": True,
    # Default sort mode for the candidate-attrs tree. Allowed values:
    #   "selection"      — Maya selection order (and source-attr declaration order)
    #   "natural_asc"    — natsort by node.attr ascending
    #   "natural_desc"   — natsort descending
    #   "type_alpha_asc" — alpha sort by type name ascending
    #   "type_alpha_desc"— alpha sort by type name descending
    #   "type_category"  — bucketed by type-family (compounds → scalars → typed → strings)
    "connect_dialog_sort_mode_default": "selection",
    # Watch panel
    # ``np.array2string(suppress_small=...)`` controls scientific
    # notation: True hides exponents for small / large floats so a 4x4
    # matrix of plain numbers renders as plain numbers. Default ON.
    "watch_suppress_scientific": True,
    # ``np.array2string(threshold=...)`` controls element truncation via
    # numpy's ``...`` summarization. True -> ``np.inf``, the full array.
    # Default OFF: numpy's standard 200-element threshold keeps the snapshot
    # plug small and the UI tree row height bounded.
    "watch_threshold_inf": False,
    # Watch + Variables tabs: ON rounds numpy array values to
    # ``display_round_digits``; OFF shows full float precision.
    "display_round_enabled": True,
    "display_round_digits": 8,
    # A stored PIL image renders as a square thumbnail in the Value column.
    # This is the fixed SOURCE size (px) it is built at; Qt then scales it to
    # the live column width. Bigger = crisper when the column is wide.
    "variables_image_preview_px": 256,
    # A stored animated GIF plays in the Value column instead of showing a
    # static first frame. ON by default, but repaints continuously.
    "variables_animate_gif": True,
    # Stored audio bytes -- a WAV container (auto-detected) or, via right-click
    # "Show as Waveform", raw uint8-mono PCM -- render as a waveform in the
    # Value column (click to play, drag to scrub, with QtMultimedia). Off ->
    # audio bytes show their text repr.
    "variables_render_waveform": True,
    # Cadence (ms) at which the Watch panel re-reads the snapshot + live plug
    # values on a main-thread timer. Lower = snappier and more CPU. Clamped.
    "watch_refresh_ms": 80,
    # Watch tab: a value is displayed only if its in-memory size is at or under
    # this many KILOBYTES. Bigger ones become a "<... too large to display>"
    # marker, so a full mesh-point buffer can't bloat the snapshot or freeze
    # the panel. Raise it if you routinely inspect big arrays.
    "watch_max_value_kb": 64,
    # Larger ceiling (KB) for previewable media (images / WAV audio) so a gif
    # or waveform reaches the render path instead of being elided by the cap
    # above. Still bounded, so a truly huge image is capped.
    "watch_max_media_kb": 2048,
    # .mpn export: ON compresses stored vars with lzma (smaller, ~10x slower
    # to write); OFF uses zlib. The OS-native save dialog is always used, so
    # this pref is the only max-compression switch.
    "mpn_export_max_compression": False,
    # Connect dialog
    # ON filters the candidate-plug list to types that can actually DG-connect
    # to the target attr (scalar \u2194 scalar, vector3 \u2194 vector3, matrix \u2194 matrix).
    "connect_dialog_filter_by_type_default": True,
    # GLOBAL metadata defaults, auto-filled into a node's Info dialog and used
    # at compile time for any empty per-node field, so a studio can set
    # license/author once. Per-node values always win. ``authors`` is a free
    # multi-line string (one "Name <email>" per line; also split on ';');
    # ``license`` is the whole legal block (copyright line, copyleft or CC
    # notice, SPDX id, or full terms) -- there is no separate copyright default.
    # All SHIP EMPTY for cache stability: a stock install injects no metadata,
    # so a no-metadata node keeps a byte-identical spec + port-cache key. The
    # compile-time version fallback ("1.0") comes from metadata_registry.
    "metadata_default_authors": "",
    "metadata_default_version": "",
    "metadata_default_license": "",
    # Mirror the node's metadata into the baked .py header. Only the three
    # defaults above reach a COMPILE, so this touches neither the spec nor the
    # port-cache key and the byte-identical guarantee above still holds. SHIPS
    # ON: a script that leaves the building should carry its license.
    "metadata_bake_header": True,
    # AI Assistant (Claude CLI): opt-in multi-agent / "ultracode" orchestration
    # for a single turn (the main agent spawns Task sub-agents). SHIPS OFF --
    # several times slower/costlier than the lean single-call default, and only
    # worth it for genuinely complex node builds.
    "assistant_multiagent_claude_cli": False,
    # Window layout, persisted on close. All default to None (0 for the mode)
    # so a first run falls back to the hard-coded sizes / Workspace mode. Lists
    # of ints, validated on restore by mpynode_designer._coerce_int_list.
    "layout_main_splitter": None,     # [left, editor, assistant] pane widths
    "layout_right_splitter": None,    # [editor, tools] heights
    "layout_mode_tab": 0,             # 0 = Workspace, 1 = Templates
    "layout_window_geometry": None,   # [x, y, w, h]
    "layout_gallery_splitter": None,        # [tree, preview] gallery widths
    "layout_gallery_right_splitter": None,  # [preview, description] heights
    # Node Designer: how the SELECTED Expressions/Script tab is emphasised. One
    # of VALID_SCRIPT_TAB_STYLES (see script_tab_style()). Read live by
    # script_tab_content.py; changing it updates open editors with no restart.
    "script_tab_style": "boxed",
    # Compile-with-AI: auto-run the assistant's follow-up recompiles without a
    # fresh human press. The FIRST compile ALWAYS requires one; this governs
    # only the AI's iterations. OFF so the user stays in the loop by default.
    "auto_recompile": False,
    # AI C++ optimizer wall-clock budget for ONE rewrite/fix model call. The
    # 600s/2400s numbers are arbitrary, so the user can DISABLE the timeout
    # entirely: the call then runs unbounded (only Cancel stops it) with a
    # liveness heartbeat proving progress. Ships ENABLED at the generous
    # budget, preserving existing behaviour; read via resolve_optimize_timeout.
    "optimize_timeout_enabled": True,
    "optimize_timeout_seconds": 2400,
    # Response-token ceiling for the AI optimizer's API path ONLY. Without a
    # tool-using CLI it must return the WHOLE translation unit in one reply,
    # and the shared 4096 default truncated 91% of this repo's cached units --
    # the gate then rejected the truncation and the round found nothing. 64000
    # clears 72% and sits at/below both shipped models' output ceilings. NOT
    # applied to the porter, which asks only for the marked compute region: a
    # cap above a user-typed model's own limit is a non-retryable 400, which
    # there would abort the whole port.
    "optimize_max_tokens": 64000,
}


# ---------------------------------------------------------------------------
# Cache + listeners
# ---------------------------------------------------------------------------
_cache: dict[str, Any] | None = None
_cache_lock = threading.Lock()
_listeners: list[Callable[[str, Any], None]] = []


def _ensure_loaded() -> None:
    """Lazy-load preferences from disk on first access."""
    global _cache
    with _cache_lock:
        if _cache is not None:
            return
        loaded: dict[str, Any] = {}
        if os.path.exists(PREFS_PATH):
            try:
                with open(PREFS_PATH, "r") as f:
                    parsed = json.load(f)
                if isinstance(parsed, dict):
                    loaded = parsed
            except Exception:
                # Corrupt JSON \u2014 ignore and fall back to defaults.
                loaded = {}
        # Merge defaults + loaded so new keys added in code show up
        # for users with old prefs files.
        _cache = {**DEFAULT_PREFS, **loaded}


def _save() -> None:
    """Write the current cache to disk. Best-effort \u2014 silent on failure.

    Written 0600 into a 0700 dir and swapped in atomically: this file holds the
    assistant API keys in plaintext, so the default umask (0644 \u2014 world
    readable) is not acceptable, and a crash mid-write must not truncate every
    preference the user has.
    """
    if _cache is None:
        return
    tmp = None
    try:
        os.makedirs(PREFS_DIR, exist_ok=True)
        try:
            os.chmod(PREFS_DIR, 0o700)
        except OSError:
            pass                     # not owner / unusual fs -- keep going
        tmp = "%s.tmp-%d" % (PREFS_PATH, os.getpid())
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(_cache, f, indent=2, sort_keys=True)
        os.replace(tmp, PREFS_PATH)  # atomic; preserves the 0600 of `tmp`
        tmp = None
    except Exception:
        pass
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_pref(key: str, default: Any = None) -> Any:
    """Return the saved value for ``key``, or fall back to:
    1. Explicit ``default`` arg if provided
    2. ``DEFAULT_PREFS[key]`` if known
    3. ``None``
    """
    _ensure_loaded()
    if key in _cache:  # type: ignore[operator]
        return _cache[key]  # type: ignore[index]
    if default is not None:
        return default
    return DEFAULT_PREFS.get(key)


def set_pref(key: str, value: Any) -> None:
    """Set + persist + notify listeners. Listener exceptions are swallowed."""
    _ensure_loaded()
    old = _cache.get(key)  # type: ignore[union-attr]
    _cache[key] = value  # type: ignore[index]
    _save()
    if old!= value:
        for cb in list(_listeners):
            try:
                cb(key, value)
            except Exception:
                pass


def reset_to_defaults() -> None:
    """Reset all known prefs to DEFAULT_PREFS."""
    for key, val in DEFAULT_PREFS.items():
        set_pref(key, val)


def all_prefs() -> dict[str, Any]:
    """Return a shallow copy of the current pref dict."""
    _ensure_loaded()
    return dict(_cache or {})


def resolve_optimize_timeout() -> float:
    """The AI-optimizer LLM-call wall-clock budget, in seconds.

    Returns ``float("inf")`` when the ``optimize_timeout_enabled`` preference is
    OFF -- meaning "no wall-clock kill; only user Cancel stops the call" -- so
    the caller can pass it straight through to the LLM client as an unbounded
    budget. When ON, returns the ``optimize_timeout_seconds`` value as a float.
    Defensive: a bad/missing seconds value falls back to the shipped default.
    """
    if not get_pref("optimize_timeout_enabled", True):
        return float("inf")
    try:
        return float(get_pref("optimize_timeout_seconds", 2400))
    except (TypeError, ValueError):
        return 2400.0


def resolve_optimize_max_tokens() -> int:
    """Response-token ceiling for the AI optimizer's API path.

    Two consumers: the request the optimizer actually sends, and the compile
    pre-flight that refuses a node whose translation unit cannot fit in it.
    Both must read the same number or the gate would refuse work the request
    could have done (or wave through work it could not). Defensive: a bad value
    falls back to the shipped default rather than raising mid-compile.
    """
    try:
        return int(get_pref("optimize_max_tokens", 64000))
    except (TypeError, ValueError):
        return 64000


# ---------------------------------------------------------------------------
# New-node authoring mode
# ---------------------------------------------------------------------------

# Valid values for the ``new_node_mode`` pref. The former "template" choice is
# retired (example nodes come from the "New from Template..." gallery); a prefs
# file still storing it is migrated to "headers" on read by new_node_mode().
VALID_NEW_NODE_MODES = ("none", "headers")


def new_node_mode() -> str:
    """Return the validated new-node authoring mode.

    One of ``"none"`` / ``"headers"``. A stored ``"template"`` (from an older
    build, before the template gallery replaced it) is migrated to
    ``"headers"``. Any other unrecognized value also falls back to
    ``"headers"``.
    """
    val = get_pref("new_node_mode", "headers")
    if val in VALID_NEW_NODE_MODES:
        return val
    return "headers"


# ---------------------------------------------------------------------------
# Node Designer: selected-tab emphasis style
# ---------------------------------------------------------------------------

# Selectable emphasis styles for the Expressions/Script selector. Keys MUST
# match the stylesheet map in ui/widgets/script_tab_content.py (test-enforced):
#   underline  -- base fill + bold + 3px highlight underline
#   gray       -- inactive recedes to grey; selected brightens + bold (no accent)
#   top_accent -- accent bar on the TOP edge + fill + bold
#   fill       -- selected tab filled with the theme highlight colour
#   classic    -- the original solid dark fill (for side-by-side comparison)
#   boxed      -- bordered cells + highlight fill on the selected one (DEFAULT)
VALID_SCRIPT_TAB_STYLES = ("underline", "gray", "top_accent", "fill", "classic",
                           "boxed")

# Shipped default; kept in sync with DEFAULT_PREFS["script_tab_style"]. `boxed`
# rather than `fill`: every other style draws the tabs borderless, so the
# INACTIVE ones fused into one band and the strip stopped reading as tabs.
DEFAULT_SCRIPT_TAB_STYLE = "boxed"


def script_tab_style() -> str:
    """Return the validated selected-tab emphasis style (one of
    :data:`VALID_SCRIPT_TAB_STYLES`). An unknown/legacy value falls back to the
    shipped default ``"fill"``."""
    val = get_pref("script_tab_style", DEFAULT_SCRIPT_TAB_STYLE)
    if val in VALID_SCRIPT_TAB_STYLES:
        return val
    return DEFAULT_SCRIPT_TAB_STYLE


def show_new_node_header() -> bool:
    """True when a fresh node's empty code tabs should show the
    auto-generated commented header (i.e. mode == ``"headers"``).

    All five code editors (Init, Compute, Viewport, OSL, Methods) gate
    their auto-header on this single helper so the preference is honest
    across every tab.
    """
    return new_node_mode() == "headers"


def template_search_paths() -> list[str]:
    """Return the validated list of template search roots.

    Reads the ``template_search_paths`` pref, expands ``~`` and environment
    variables in each entry, and drops blanks. An empty result or a stored
    value that is not a non-empty list of strings falls back to the shipped
    default (``_default_template_search_paths()``). Non-existent paths are NOT
    filtered here (the gallery's discovery layer logs + drops those) so the
    Preferences editor can still show a path the user is about to create.
    """
    raw = get_pref("template_search_paths", None)
    if not isinstance(raw, list):
        return list(_default_template_search_paths())
    out: list[str] = []
    for p in raw:
        if not isinstance(p, str):
            continue
        p = os.path.expanduser(os.path.expandvars(p)).strip()
        if p:
            out.append(p)
    return out or list(_default_template_search_paths())


def _looks_like_windows_abs(p: str) -> bool:
    """``C:\\x``, ``c:/x`` or a ``\\\\server\\share`` UNC path."""
    return ((len(p) >= 3 and p[0].isalpha() and p[1] == ":" and p[2] in "\\/")
            or p.startswith("\\\\"))


def is_foreign_os_path(p: str) -> bool:
    """True when ``p`` is an absolute path that belongs to a DIFFERENT OS.

    ``preferences.json`` travels: a studio network home mounted by both a Mac
    and a Windows box is ordinary, and an absolute path is the one kind of pref
    value that cannot survive the trip. Applying it anyway hands Maya a path
    that can never exist, so the caller falls back to the OS-correct default
    instead (and the Locations page says why).

    Relative paths are never foreign -- they work anywhere."""
    p = (p or "").strip()
    if not p:
        return False
    if os.name == "nt":
        # A POSIX absolute path. Not just "contains /": "C:/x" is a perfectly
        # legal Windows path, so require a LEADING slash and no drive letter.
        return p.startswith("/") and not _looks_like_windows_abs(p)
    return _looks_like_windows_abs(p)


def port_cache_dir_pref() -> str:
    """The user's port-cache override, or ``""`` meaning "fall through".

    Blank, non-string, and foreign-OS values all read as unset, so a prefs file
    shared between platforms degrades to each machine's own default rather than
    to a broken path. ``~`` and ``$VAR`` are expanded, matching
    :func:`template_search_paths`."""
    raw = get_pref("port_cache_dir", "")
    if not isinstance(raw, str) or not raw.strip():
        return ""
    if is_foreign_os_path(raw):
        return ""
    return os.path.expanduser(os.path.expandvars(raw.strip()))


# ---------------------------------------------------------------------------
# Editor-font helper
# ---------------------------------------------------------------------------


def editor_font():
    """Build a QFont from the saved editor_font_family + editor_font_size.

    Imports QFont lazily to avoid pulling Qt at module import time.
    """
    from mpynode.ui.qt_wrapper import QFont

    font = QFont(get_pref("editor_font_family", "Courier"))
    try:
        font.setPointSize(int(get_pref("editor_font_size", 10)))
    except Exception:
        font.setPointSize(10)
    font.setStyleHint(QFont.Monospace)
    font.setFixedPitch(True)
    return font


# ---------------------------------------------------------------------------
# Listener registry
# ---------------------------------------------------------------------------


def register_change_listener(cb: Callable[[str, Any], None]) -> None:
    """Subscribe to (key, new_value) notifications on every set_pref."""
    if cb not in _listeners:
        _listeners.append(cb)


def unregister_change_listener(cb: Callable[[str, Any], None]) -> None:
    """Unsubscribe. Safe to call on a callback that wasn't registered."""
    try:
        _listeners.remove(cb)
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Test hook \u2014 reset module state. Used by tests to simulate fresh launch.
# Not part of the public API.
# ---------------------------------------------------------------------------


def _reset_for_tests() -> None:
    global _cache
    with _cache_lock:
        _cache = None
        _listeners.clear()
