"""Watch panel widget.

Renders a live snapshot of every variable in the user expression's
``exec_locals`` after the last compute. Filtered through a glob /
substring filter the user types into the toolbar.

Layout:
  [ Enable Watch ]  Filter: [ target_*       ]

  Variable        Value             Type
  ----------      -----------       --------
  alpha           0.5               float
  target_pos      [1.0, 2.0, 3.0]   ndarray...

The variables are read from the node's ``_watchVarsData`` plug; the
collection happens inside ``exec_with_profile_watch`` when the
``watch_enabled`` toggle is on.

Filter semantics (handled by ``_common.instrumentation.filter_watch_vars``
at write time AND ``apply_filter`` here at display time):
  * empty filter \u2192 show every captured var
  * contains ``*? [`` \u2192 fnmatch.fnmatchcase pattern (e.g. ``target_*``)
  * otherwise \u2192 case-sensitive substring match
"""

from __future__ import annotations

import fnmatch

import maya.cmds as mc
from mpynode._common.instrumentation.watch import (
    WATCH_FRAMEWORK_KEY,
    WatchLabel,
)
from mpynode.ui.widgets.image_preview import (
    ImagePreviewDelegate,
    WaveformPlayer,
    attach_value,
    cleanup_media_widgets,
    is_audio_item,
    is_previewable_item,
    is_showing_image,
    is_showing_waveform,
    refresh_media_widget,
    render_waveform_pref_on,
    set_image_view,
    set_waveform_view,
    toggle_value_mode,
    toggle_waveform_view,
)
from mpynode.ui.qt_wrapper import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    Qt,
    QTimer,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from mpynode.ui.widgets.font_prefs import wire_area_font


# Typed-geometry attr kinds that have no displayable scalar/string value.
# cmds.getAttr on these raises ("data is not a numeric or string value")
# and forces upstream geometry evaluation, so the Watch never reads them.
_NON_DISPLAYABLE_TYPES = frozenset({"mesh", "nurbsCurve", "nurbsSurface"})

#: attr_type -> the wrapper class a user sees for it, so a geometry plug labels
#: itself the SAME way the object does everywhere else (``Mesh("pCubeShape1")``).
_GEO_LABEL_CLASS = {
    "mesh":         "Mesh",
    "nurbsCurve":   "NurbsCurve",
    "nurbsSurface": "NurbsSurface",
}


def _geometry_label(node_name: str, attr: str, atype: str) -> str:
    """``Mesh("pSphereShape1")`` for a connected geometry plug.

    The VALUE of a geometry plug still can't be shown here -- reading it would
    force the upstream to evaluate, which the live poll must never do. But which
    shape is plugged in is pure DG topology: ``plug.source()`` touches no
    geometry data and evaluates nothing, so the identity is free.

    Falls back to the bare ``<mesh>`` placeholder when nothing is connected --
    there is genuinely no shape to name then.
    """
    placeholder = "<%s>" % (atype or "geometry")
    cls         = _GEO_LABEL_CLASS.get(atype)
    if cls is None:
        return placeholder
    try:
        import maya.api.OpenMaya as _om

        from mpynode._api2.geometry import _source_node_name

        _sel = _om.MSelectionList()
        _sel.add(node_name + "." + attr)
        src = _source_node_name(_sel.getPlug(0))
    except Exception:
        return WatchLabel(placeholder, cls)
    text = '%s("%s")' % (cls, src) if src else placeholder
    return WatchLabel(text, cls)


def _geometry_multi_label(node_name: str, attr: str, atype: str):
    """Per-element source labels for a geometry MULTI, e.g.
    ``[Mesh("a"), Mesh("b")]``.

    Indices come from ``getExistingArrayAttributeIndices()`` for the same reason
    the value path uses it: ``cmds.getAttr(..., multiIndices=True)``
    unconditionally forces a recompute, which the live poll must not trigger.
    Falls back to the bare ``<mesh[]>`` placeholder if nothing is connected.
    """
    placeholder = "<%s[]>" % atype
    cls         = _GEO_LABEL_CLASS.get(atype)
    if cls is None:
        return placeholder
    try:
        import maya.api.OpenMaya as _om

        from mpynode._api2.geometry import _source_node_name

        _sel = _om.MSelectionList()
        _sel.add(node_name + "." + attr)
        parent  = _sel.getPlug(0)
        indices = list(parent.getExistingArrayAttributeIndices())
        labels  = []
        for idx in indices:
            src  = _source_node_name(parent.elementByLogicalIndex(idx))
            text = '%s("%s")' % (cls, src) if src else placeholder
            labels.append(WatchLabel(text, cls))
    except Exception:
        return WatchLabel(placeholder, cls)
    return labels or WatchLabel(placeholder, cls)


def _cap_watch_dict(d: dict) -> dict:
    """Replace any value over the ``watch_max_value_kb`` preference with a
    compact "<too large>" marker. Values under the limit (including numpy
    arrays) pass through unchanged so their real type is preserved."""
    try:
        from mpynode._common.instrumentation import cap_watch_value, watch_max_bytes
    except Exception:
        return d
    try:
        mb = watch_max_bytes()
        return {k: cap_watch_value(v, mb) for k, v in d.items()}
    except Exception:
        return d


def read_multi_plug_values(node_name: str, attr: str, meta: dict):
    """Read a multi (array) plug element-by-element.

    ``cmds.getAttr`` on a typed multi PARENT raises ("compound with mixed
    type elements"), so we enumerate the logical indices and read each
    element. Vector/euler elements are stacked into an ``(n, 3)`` numpy
    array (matching what the expression sees); other types return a list.
    """
    atype = (meta or {}).get("attr_type", "")
    # Values aren't readable (and evaluating them is expensive), but each
    # element's SOURCE is free -- list what is plugged in rather than one
    # opaque placeholder for the whole array.
    if atype in _NON_DISPLAYABLE_TYPES:
        return _geometry_multi_label(node_name, attr, atype)
    # NOT ``cmds.getAttr(plug, multiIndices=True)``: that query
    # UNCONDITIONALLY forces a recompute of an output multi (an element
    # getAttr respects the clean cache, the index query does not), so on the
    # ~80ms live poll it re-ran the user expression once per multi output --
    # the "node constantly evaluated" and "Save fires 4-8x" reports.
    # getExistingArrayAttributeIndices() reads the datablock without
    # evaluating, so a clean output is served from cache.
    _plug = None
    try:
        import maya.api.OpenMaya as _om

        _sel = _om.MSelectionList()
        _sel.add(node_name + "." + attr)
        _plug   = _sel.getPlug(0)
        indices = list(_plug.getExistingArrayAttributeIndices())
    except Exception:
        try:
            indices = mc.getAttr(node_name + "." + attr, multiIndices=True) or []
        except Exception:
            indices = []
    elem_meta = {"attr_type": atype, "is_array": False}
    by_idx    = {}
    for idx in indices:
        try:
            ev = mc.getAttr("%s.%s[%d]" % (node_name, attr, idx))
        except Exception:
            continue
        by_idx[idx] = reshape_plug_value(ev, elem_meta)
    # Mirror the compute read: a NON-sparse array is shown DENSE (length
    # max_logical+1, gaps = the attribute default) so Watch matches what the
    # expression sees via read_user_inputs_dict; a sparse array stays compact.
    sparse = bool((meta or {}).get("sparse", False))
    if sparse or not by_idx:
        vals = [by_idx[i] for i in sorted(by_idx)]
    else:
        try:
            from mpynode._api2.helpers import array_gap_default

            attr_obj = _plug.attribute() if _plug is not None else None
            default  = array_gap_default(attr_obj, atype)
        except Exception:
            default = 0.0
        vals = [by_idx.get(i, default) for i in range(max(by_idx) + 1)]
    # Compound numeric multis stack into one ndarray, matching
    # read_user_inputs_dict. An EMPTY input returns a 0-length array of the
    # right shape/dtype -- NOT a bare list -- so Type/Size still read
    # numpy.ndarray[float64] / (0, 3) rather than list / 0.
    if atype in ("vector", "euler", "color"):
        try:
            import numpy as _np

            return (_np.array([_np.asarray(v).reshape(3) for v in vals])
                    if vals else _np.zeros((0, 3), dtype=_np.float64))
        except Exception:
            return vals
    if atype == "quaternion":
        try:
            import numpy as _np

            return (_np.array([_np.asarray(v).reshape(4) for v in vals])
                    if vals else _np.zeros((0, 4), dtype=_np.float64))
        except Exception:
            return vals
    if atype == "matrix":
        try:
            import numpy as _np

            return (_np.array([_np.asarray(v).reshape(4, 4) for v in vals])
                    if vals else _np.zeros((0, 4, 4), dtype=_np.float64))
        except Exception:
            return vals
    # Scalar numeric multis mirror read_user_inputs_dict's type contract so
    # the Watch shows the SAME array AND dtype the expression sees:
    #   float / double / angle / time -> float64
    #   int / enum                    -> int64
    #   bool                          -> bool
    # string / python / geometry stay Python lists (numpy can't stack them).
    # Empty arrays keep the right dtype so it is still reported.
    try:
        import numpy as _np

        if atype in ("float", "double", "angle", "time"):
            return (_np.asarray(vals, dtype=_np.float64)
                    if vals else _np.zeros(0, dtype=_np.float64))
        if atype in ("int", "enum"):
            return (_np.asarray(vals, dtype=_np.int64)
                    if vals else _np.zeros(0, dtype=_np.int64))
        if atype == "bool":
            return (_np.asarray(vals, dtype=bool)
                    if vals else _np.zeros(0, dtype=bool))
    except Exception:
        pass
    return vals


def _angle_ui_to_radians(value):
    """Convert an angular value read via ``cmds.getAttr`` (which returns the
    current UI angular unit -- DEGREES by default) into RADIANS, so the Watch
    shows the SAME value the expression sees (``read_plug_value`` reads angles
    via ``plug.asDouble()`` = internal radians). Unit-independent: if the UI is
    already set to radians, ``MAngle(value, uiUnit)`` interprets it correctly.
    Never raises -- falls back to the raw value."""
    try:
        import maya.api.OpenMaya as _om

        return _om.MAngle(float(value), _om.MAngle.uiUnit()).asRadians()
    except Exception:
        return value


def reshape_plug_value(value, meta: dict):
    """Reshape a raw ``cmds.getAttr`` value for nicer Watch display so an
    input/output reads like the expression sees it: a ``matrix`` becomes a
    4x4 numpy array, a ``vector`` / ``euler`` a (3,) array. ``angle`` / ``euler``
    values are converted from the UI angular unit (degrees) to RADIANS so they
    match what the expression reads (``plug.asDouble()``). Scalars, strings, and
    array (multi) plugs pass through unchanged. Pure + defensive."""
    try:
        meta = meta or {}
        if bool(meta.get("is_array", False)):
            return value
        atype = meta.get("attr_type", "")
        if value is None:
            return value
        import numpy as _np

        if atype == "angle":
            # The expression sees radians; cmds.getAttr gave the UI unit.
            return _angle_ui_to_radians(value)
        if atype == "matrix":
            return _np.array(value, dtype=float).reshape(4, 4)
        if atype in ("vector", "euler", "color"):
            # cmds.getAttr returns [(x, y, z)] for a double3 / float3.
            flat = (
                value[0]
                if len(value) == 1 and isinstance(value[0], (list, tuple))
                else value
            )
            if atype == "euler":
                # Each component is an angle -> UI unit to radians.
                return _np.array(
                    [_angle_ui_to_radians(x) for x in flat], dtype=float
                ).reshape(3)
            return _np.array(flat, dtype=float).reshape(3)
        if atype == "quaternion":
            # cmds.getAttr returns [(x, y, z, w)] for the 4-double compound.
            flat = (
                value[0]
                if len(value) == 1 and isinstance(value[0], (list, tuple))
                else value
            )
            return _np.array(flat, dtype=float).reshape(4)
    except Exception:
        pass
    return value


def apply_filter(vars_dict: dict, filter_text: str) -> dict:
    """Filter a vars dict by glob or substring. Pure function (testable)."""
    if not vars_dict:
        return {}
    pat = (filter_text or "").strip()
    if not pat:
        return dict(vars_dict)
    has_glob = any(c in pat for c in ("*", "?", "["))
    out      = {}
    for name, value in vars_dict.items():
        if has_glob:
            if fnmatch.fnmatchcase(name, pat):
                out[name] = value
        else:
            if pat in name:
                out[name] = value
    return out


def _array_change_tag(value, precision: int = 8) -> str:
    """Compact, content-sensitive tag for a numpy array whose body numpy
    SUMMARIZED (elided interior elements).

    numpy's summarized repr shows only the first/last 3 rows, so a change
    confined to a hidden interior element leaves the visible text
    byte-identical -- e.g. a deform that only moves the compressed middle
    verts of a skinCluster weight array would look frozen in the Watch tab
    while the value (and the scene) actually changed. This tag makes such a
    change visible.

    Returns ``  shape=... min=... max=... mean=... #<hex>``: the shape /
    min / max / mean are a human-readable summary; the trailing ``#<hex>``
    (a digest of the ROUNDED bytes, so it tracks the displayed precision)
    GUARANTEES the text changes whenever ANY element -- visible or elided --
    changes, even when those stats happen to collide (skin weights are
    row-normalized, so min / max can stay 0 / 1 and the mean alone moves, or
    a permutation of interior values leaves every statistic identical).

    Pure, O(array), and NEVER raises (returns "" on any failure so the caller
    simply omits the tag). Runs on the ~80 ms live poll only for already-
    summarized numeric arrays.
    """
    try:
        import hashlib

        import numpy as _np

        p = max(0, min(int(precision), 17))
        with _np.errstate(all="ignore"):
            stats = "shape=%s min=%.*g max=%.*g mean=%.*g" % (
                tuple(value.shape),
                p, float(_np.nanmin(value)),
                p, float(_np.nanmax(value)),
                p, float(_np.nanmean(value)),
            )
        # Hash the ROUNDED bytes so the tag tracks the displayed precision and
        # ignores sub-precision / signed-zero / NaN-bit noise. Fall back to the
        # raw bytes if the round/cast fails so the change guarantee survives.
        try:
            buf = _np.ascontiguousarray(
                _np.round(value.astype("float64"), p)
            ).tobytes()
        except Exception:
            buf = _np.ascontiguousarray(value).tobytes()
        return "  " + stats + " #" + hashlib.blake2b(buf, digest_size=4).hexdigest()
    except Exception:
        return ""


def _format_value(value, max_lines: int = 12, max_chars_per_line: int = 200) -> str:
    """Best-effort repr for a variable value, preserving multi-line
    formatting (numpy matrices etc.) for readability.

    switched to multi-line preserving formatter.
    * Pass ``prefix="array("`` to ``np.array2string`` so subsequent
        rows are indented to line up under the first ``[`` (the wrap
        with ``"array(" +... + ")"`` confused numpy's auto-indent).
      * Read prefs ``watch_suppress_scientific`` (default True) and
        ``watch_threshold_inf`` (default False) so users can globally
        suppress scientific notation and / or disable element
        truncation.
    """
    s = None
    # Content-sensitive suffix for a SUMMARIZED numeric array (set below,
    # appended to the last line AFTER the caps so it always survives).
    tag = ""
    try:
        import numpy as _np

        if isinstance(value, _np.ndarray):
            # Pull prefs (safe defaults if module not importable).
            try:
                from mpynode.ui import preferences

                suppress      = bool(preferences.get_pref("watch_suppress_scientific", True))
                threshold_inf = bool(preferences.get_pref("watch_threshold_inf", False))
                round_enabled = bool(
                    preferences.get_pref("display_round_enabled", True)
                )
                try:
                    round_digits = int(
                        preferences.get_pref("display_round_digits", 8)
                    )
                except Exception:
                    round_digits = 8
                round_digits = max(0, min(round_digits, 17))
            except Exception:
                suppress      = True
                threshold_inf = False
                round_enabled = True
                round_digits  = 8

            kwargs = {
                "separator": ", ",
                "precision": round_digits if round_enabled else 8,
                # Critical for column alignment: tells numpy the caller
                # prepends ``array(``, so rows indent under the first ``[``.
                "prefix": "array(",
            }
            if not round_enabled:
                # Minimal digits that uniquely represent each float.
                kwargs["floatmode"]      = "unique"
                kwargs["suppress_small"] = bool(suppress)
            elif suppress:
                # ``suppress_small`` only kills scientific notation near
                # zero -- numpy decides on the max/min RATIO, so an array
                # holding 1e8 still renders scientific. This per-element
                # formatter uses fixed-point for human-scale numbers and
                # falls back to scientific only past ~20 chars, so garbage
                # / uninitialized doubles can't produce 100+ char rows.
                _prec      = kwargs["precision"]
                _max_chars = max(20, _prec + 14)

                def _smart_float(x, _p=_prec, _cap=_max_chars):
                    fixed = f"{x:.{_p}f}"
                    if len(fixed) <= _cap:
                        return fixed
                    return f"{x:.{_p}e}"

                kwargs["formatter"] = {"float_kind": _smart_float}
            else:
                kwargs["suppress_small"] = False
            if threshold_inf:
                kwargs["threshold"] = _np.inf
                # Opting into full arrays must also drop the widget-side
                # line/char caps, or we silently re-truncate.
                max_lines          = 10**9
                max_chars_per_line = 10**9
            else:
                # Cap elements so a 10000-row array doesn't blow up the
                # snapshot plug + UI row height.
                kwargs["threshold"] = 200
            s = "array(" + _np.array2string(value, **kwargs) + ")"
            # Past the threshold numpy elides interior elements, so the
            # visible first/last rows can be byte-identical even though a
            # HIDDEN element changed. Tag the content. Truncating path and
            # numeric dtypes only; the full-array path stays byte-identical.
            try:
                if (
                    not threshold_inf
                    and value.size > 200
                    and _np.issubdtype(value.dtype, _np.number)
                ):
                    tag = _array_change_tag(value, kwargs["precision"])
            except Exception:
                tag = ""
    except Exception:
        pass

    if s is None and isinstance(value, WatchLabel):
        # A stand-in for an object, not a user string. repr() would quote it
        # and assert "this is a str", contradicting the Type column.
        s = str(value)

    if s is None:
        try:
            s = repr(value)
        except Exception:
            try:
                s = str(value)
            except Exception:
                return "<unrepresentable>"

    # Cap per-line length first (very wide arrays).
    capped: list[str] = []
    for line in s.split("\n"):
        if len(line) > max_chars_per_line:
            line = line[:max_chars_per_line] + "\u2026"
        capped.append(line)

    # Then cap total line count.
    if len(capped) > max_lines:
        omitted = len(capped) - max_lines
        capped  = capped[:max_lines] + [f"\u2026 ({omitted} more lines)"]
    # Append the summarized-array change tag to the LAST retained line (a
    # same-line suffix -- never a new line, so the max_lines cap is unchanged).
    if tag and capped:
        capped[-1] = capped[-1] + tag
    return "\n".join(capped)


def _format_type(value) -> str:
    """Friendly type label. numpy arrays carry their ELEMENT dtype, e.g.
    ``numpy.ndarray[int64]`` / ``numpy.ndarray[float64]`` / ``numpy.ndarray
    [float32]`` -- so int vs float vs float32 is visible at a glance and the
    label matches the array the expression actually sees. numpy scalars keep
    their short name (``numpy.float64``); torch tensors also surface their
    dtype (``torch.Tensor[float32]``). Everything else uses the plain
    module-qualified type name."""
    try:
        # A collapsed stand-in (geometry plug, API dataclass) reports what it
        # REPLACED; otherwise the Type column reads "str" for all of them.
        _label_type = getattr(value, "type_name", None)
        if _label_type:
            return _label_type
        # numpy arrays: append the element dtype.
        try:
            import numpy as _np

            if isinstance(value, _np.ndarray):
                return "numpy.ndarray[%s]" % value.dtype
        except Exception:
            pass
        t    = type(value)
        mod  = getattr(t, "__module__", "")
        name = t.__name__
        # torch tensors expose a dtype too (torch.float32 -> "float32").
        if mod == "torch" and name == "Tensor":
            try:
                return "torch.Tensor[%s]" % str(value.dtype).replace("torch.", "")
            except Exception:
                pass
        if mod and mod not in ("builtins", ""):
            return f"{mod}.{name}"
        return name
    except Exception:
        return ""


def _format_size(value) -> str:
    """Compact size descriptor for the Watch "Size" column.

      * numpy.ndarray            -> its shape, e.g. ``(3, 4)``
      * str / bytes              -> character / byte count
      * list / tuple / dict /
        set / other Sized        -> element count
      * scalars (int/float/bool/
        None) and len-less objects -> ``NA``
      * internal placeholder markers ('<mesh>', '<...too large…>') -> ``NA``

    Runs on the ~80 ms live poll for every visible row, so it is O(1) and MUST
    NEVER raise (a thrown exception there would break the whole refresh).
    """
    try:
        # numpy arrays: report the SHAPE, not __len__ (which is just dim 0).
        try:
            import numpy as _np

            if isinstance(value, _np.ndarray):
                return str(tuple(value.shape))
        except Exception:
            pass

        # Strings report length, except the angle-bracketed placeholders the
        # watch pipeline substitutes for values it won't show inline
        # ('<mesh>', '<...too large to display: N KB>') -- no user size.
        if isinstance(value, str):
            # A stand-in has no user size; len() would measure the LABEL.
            if isinstance(value, WatchLabel):
                return "NA"
            if len(value) >= 2 and value[0] == "<" and value[-1] == ">":
                return "NA"
            return str(len(value))

        if isinstance(value, (list, tuple, dict, set, frozenset,
                              bytes, bytearray)):
            return str(len(value))

        # bool is an int subclass with no meaningful length; exclude numbers.
        if isinstance(value, (bool, int, float)) or value is None:
            return "NA"

        # Any other object that defines __len__ (e.g. custom containers).
        if getattr(type(value), "__len__", None) is not None:
            return str(len(value))
        return "NA"
    except Exception:
        return "NA"


def decode_io_value(raw, attr_type):
    """Turn a raw plug value into the object to DISPLAY in the Watch tab.

    For a ``python`` attr the stored value is a ``base64(pickle(obj))`` bus
    string; decode it (trust-gated) so the panel shows the live object and
    its real type (dict / ndarray / custom class / ...) instead of an opaque
    string. Any other ``attr_type`` is returned unchanged.

    Safe for the 80 ms live poll: NEVER raises. Falls back to the raw string
    when the scene is untrusted (pickle refused), the payload is empty, or
    decoding fails (corrupt blob).
    """
    if attr_type != "python":
        return raw
    if not raw:
        return raw
    try:
        from mpynode._common.io import trust

        if not trust.pickle_trusted():
            # Untrusted scene: cannot unpickle (RCE) -> show the bus string.
            return raw
        from mpynode._api2.helpers import decode_python_string

        obj = decode_python_string(raw)
        # None here means "no object" (raw is non-empty and trusted).
        return raw if obj is None else obj
    except Exception:
        # Corrupt payload or any failure: show raw rather than drop the
        # row or freeze the poll.
        return raw


def decode_io_value_cached(cache: dict, attr: str, raw, attr_type):
    """``decode_io_value`` with a per-attr memo so an unchanged ``python``
    blob is not re-unpickled on every live-poll tick.

    ``cache`` maps ``attr -> (raw, decoded)`` and keeps only the LATEST blob
    per attr, so it can't grow unbounded even when the value changes every
    tick (e.g. an unseeded-random output)."""
    prev = cache.get(attr)
    if prev is not None and prev[0] == raw:
        return prev[1]
    decoded     = decode_io_value(raw, attr_type)
    cache[attr] = (raw, decoded)
    return decoded


class NDWatchWidget(QWidget):
    """Watch tab \u2014 read-only live exec_locals view with glob filter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._py_node    = None
        self._refreshing = False
        # Cached unfiltered snapshot so retyping the filter needs no plug
        # round-trip. ``_cached_vars`` = expression locals (instrumentation
        # snapshot); ``_cached_stored`` = the live in-memory store.
        self._cached_vars:       dict = {}
        self._cached_stored:     dict = {}
        self._cached_registered: set = set()
        # Live user input / output plug values (read each refresh).
        self._cached_inputs:  dict = {}
        self._cached_outputs: dict = {}
        # The wrapper's self.X framework surface, carried inside the watch
        # snapshot under WATCH_FRAMEWORK_KEY (so it needs Enable Watch).
        self._cached_framework: dict = {}
        # Memo of the last decoded ``python`` value per full plug path, so an
        # unchanged base64+pickle blob isn't re-unpickled every 80 ms poll.
        self._py_decode_cache: dict = {}
        # Live-poll suspension (set while a Save / F5 is in flight so timer
        # ticks don't force extra computes during the save's dirty windows).
        self._live_suspended  = False
        self._live_was_active = False
        # Per-variable "show as image" choice from the right-click toggle.
        # Survives refreshes so a chosen image never reverts to its source
        # repr. Cleared when the active node changes.
        self._image_view_modes: dict = {}
        # Same, for the "show as waveform" choice on audio (WAV/PCM) vars.
        self._waveform_view_modes: dict = {}
        # Shared audio player for waveform cells (lazy; created on first play).
        self._waveform_player = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._header = QLabel("(no node selected)", self)
        layout.addWidget(self._header)

        btn_row        = QHBoxLayout()
        self._watch_cb = QCheckBox("Enable Watch", self)
        self._watch_cb.setToolTip(
            "Capture every variable in scope after each user compute. "
            "Heavyweight \u2014 turn off when not actively debugging."
        )
        filter_label      = QLabel("Filter:", self)
        self._filter_edit = QLineEdit(self)
        self._filter_edit.setPlaceholderText("name, glob (target_*), or substring")
        self._filter_edit.setToolTip(
            "Empty = show all captured vars. Use glob (target_*) or "
            "substring match (target) to narrow down."
        )
        btn_row.addWidget(self._watch_cb)
        btn_row.addWidget(filter_label)
        btn_row.addWidget(self._filter_edit)
        layout.addLayout(btn_row)

        # Scope row: choose which tiers the live feed shows. Locals come
        # from the watch snapshot (needs Enable Watch); Temporary +
        # Persistent are read live from the in-memory store each refresh.
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Show:", self))
        self._show_inputs_cb    = QCheckBox("Inputs",     self)
        self._show_outputs_cb   = QCheckBox("Outputs",    self)
        self._show_framework_cb = QCheckBox("Framework",  self)
        self._show_locals_cb    = QCheckBox("Locals",     self)
        self._show_temp_cb      = QCheckBox("Temporary",  self)
        self._show_persist_cb   = QCheckBox("Persistent", self)
        self._show_framework_cb.setToolTip(
            "The wrapper's self.X surface (a locator's draw / auto_refresh, a "
            "mesh's points / counts / indices, an IK solver's joints).\n"
            "Captured with the watch snapshot, so it needs Enable Watch.")
        for _cb in (
            self._show_inputs_cb,
            self._show_outputs_cb,
            self._show_framework_cb,
            self._show_locals_cb,
            self._show_temp_cb,
            self._show_persist_cb,
        ):
            _cb.setChecked(True)
            scope_row.addWidget(_cb)
        scope_row.addStretch(1)
        layout.addLayout(scope_row)

        self._tree = QTreeWidget(self)
        wire_area_font(self._tree, "panel", on_change=self._on_panel_font)
        # Shift-click a section header (Inputs / Outputs / Locals / ...) to
        # recursively expand or collapse that section's subtree.
        from mpynode.ui.widgets.tree_expand import (
            install_shift_click_expand_all,
        )
        install_shift_click_expand_all(self._tree)
        self._tree.setHeaderLabels(["Variable", "Value", "Type", "Size"])
        self._tree.setColumnCount(4)
        # Set once so watched values are visible without dragging; columns
        # stay user-draggable. Do NOT auto-resize per update -- dynamic
        # resizing during real-time watch proved unsafe (crashes).
        self._tree.setColumnWidth(0, 140)
        self._tree.setColumnWidth(1, 320)
        # Size is a compact column to the right of Type: list/dict -> count,
        # numpy array -> shape, str -> length, else "NA".
        self._tree.setColumnWidth(3, 70)
        # PIL-image vars render as a scaled thumbnail; other rows fall
        # through to the default delegate. The delegate also tracks the
        # column width on resize (relayout only -- no width writes).
        self._img_delegate = ImagePreviewDelegate(self._tree, value_col=1)
        self._tree.setItemDelegateForColumn(1, self._img_delegate)
        # Right-click an image-previewable row to toggle source<->image.
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)
        # Word-wrap + variable row height so the value cell can show
        # multi-line numpy reprs with column alignment intact.
        self._tree.setWordWrap(True)
        self._tree.setUniformRowHeights(False)
        # Cache a monospace font for the Value column so columns inside
        # numpy array reprs visually align.
        try:
            from mpynode.ui import preferences
            from mpynode.ui.qt_wrapper import QFont

            self._mono_font = QFont(preferences.default_editor_font_family())
            self._mono_font.setStyleHint(QFont.Monospace)
            self._mono_font.setFixedPitch(True)
            # A per-item font beats the view font, so this needs the size too.
            # Re-set on every pref change via _sync_mono_font below.
            self._sync_mono_font()
        except Exception:
            self._mono_font = None
        layout.addWidget(self._tree)

        self._watch_cb.toggled.connect(self._on_watch_toggled)
        self._filter_edit.textChanged.connect(self._on_filter_changed)
        for _cb in (
            self._show_inputs_cb,
            self._show_outputs_cb,
            self._show_framework_cb,
            self._show_locals_cb,
            self._show_temp_cb,
            self._show_persist_cb,
        ):
            _cb.toggled.connect(self._on_scope_changed)

        self._set_controls_enabled(False)

        # Under the Evaluation Manager an expression node's compute -- and so
        # its snapshot write plus the MNodeMessage callback that drives the
        # event-based refresh -- can run OFF the main thread, leaving that
        # refresh to land only on mouse-release. This main-thread QTimer poll
        # closes the gap for EVERY node type: it re-reads the snapshot + live
        # plug values and reconciles in place (cheap) at a steady cadence.
        # Runs only while Watch is enabled AND the tab is visible.
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(self._watch_refresh_interval())
        self._live_timer.timeout.connect(self._on_live_tick)

        # Live-update displayed values when a display-related preference
        # changes (rounding digits, scientific notation, full arrays).
        try:
            from mpynode.ui.preferences import register_change_listener

            register_change_listener(self._on_pref_changed)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setPyNode(self, py_node):
        # New node -> the remembered image choices no longer apply.
        if py_node is not self._py_node:
            self._image_view_modes    = {}
            self._waveform_view_modes = {}
            # Release the player + temp .wav but KEEP the wrapper object --
            # dispose() leaves it reusable, and any surviving reused cell
            # still points at it.
            if self._waveform_player is not None:
                try:
                    self._waveform_player.dispose()
                except Exception:
                    pass
        self._py_node = py_node
        self.refresh()

    def _ensure_waveform_player(self):
        """Lazily create the shared audio player for waveform cells."""
        if self._waveform_player is None:
            self._waveform_player = WaveformPlayer(self)
        return self._waveform_player

    _DISPLAY_PREF_KEYS = (
        "display_round_enabled",
        "display_round_digits",
        "watch_suppress_scientific",
        "watch_threshold_inf",
        "variables_image_preview_px",
        "variables_animate_gif",
        "variables_render_waveform",
    )

    def _on_pref_changed(self, key, value):
        """Re-render watched values when a display pref changes.
        Self-unregisters once the widget's C++ side is destroyed."""
        try:
            if key == "watch_refresh_ms":
                # Apply the new live-poll cadence immediately.
                self._live_timer.setInterval(self._watch_refresh_interval())
                return
            if key not in self._DISPLAY_PREF_KEYS:
                return
            self.refresh()
        except RuntimeError:
            try:
                from mpynode.ui.preferences import unregister_change_listener

                unregister_change_listener(self._on_pref_changed)
            except Exception:
                pass

    @staticmethod
    def _watch_refresh_interval() -> int:
        """Live-poll interval (ms) from prefs, clamped to a safe range."""
        try:
            from mpynode.ui import preferences

            ms = int(preferences.get_pref("watch_refresh_ms", 80))
        except Exception:
            ms = 80
        return max(16, min(ms, 5000))

    def setFilter(self, text: str) -> None:
        """Programmatic filter setter (used by tests + scripts)."""
        self._filter_edit.setText(text or "")

    def _sync_mono_font(self) -> None:
        """Point-size the Value column's mono font from ``panel_font_size``.

        Separate from construction because a per-item font overrides the
        view's: without re-setting it, the Value column would keep its old
        size while every other column followed the view.
        """
        if getattr(self, "_mono_font", None) is None:
            return
        try:
            from mpynode.ui.preferences import resolve_font_size

            self._mono_font.setPointSize(resolve_font_size("panel"))
        except Exception:
            pass

    def _on_panel_font(self) -> None:
        """panel_font_size changed: re-size the mono font, then repopulate so
        the per-item fonts are re-applied to existing rows."""
        self._sync_mono_font()
        try:
            self.refresh()
        except Exception:
            pass

    def refresh(self):
        """Re-read the snapshot from the plug + repopulate the tree."""
        # Re-entrancy guard. refresh() reads OUTPUT plugs via cmds.getAttr,
        # which forces the node's compute(). When watch is enabled that
        # compute writes _watchVarsData (cmds.setAttr), whose attributeChanged
        # callback calls refresh() again -- a synchronous loop that froze
        # Maya. Bail if a refresh is already on the stack.
        if self._refreshing:
            return
        self._refreshing = True
        try:
            if self._py_node is None:
                self._stop_live_timer()
                cleanup_media_widgets(self._tree)
                self._tree.clear()
                self._header.setText("(no node selected)")
                self._cached_vars       = {}
                self._cached_stored     = {}
                self._cached_registered = set()
                self._cached_inputs     = {}
                self._cached_outputs    = {}
                self._cached_framework  = {}
                # Uncheck the toggle too. Done while ``_refreshing`` is
                # True so the toggle handler no-ops.
                self._watch_cb.setChecked(False)
                self._set_controls_enabled(False)
                return
            self._header.setText(f"Watch: {self._py_node.get_name()}")

            # Only ``MPyNode`` declares ``is_watch_enabled`` /
            # ``get_watch_vars``, so detect support instead of crashing.
            supports_watch = hasattr(self._py_node, "is_watch_enabled")
            if not supports_watch:
                self._stop_live_timer()
                cleanup_media_widgets(self._tree)
                self._tree.clear()
                self._header.setText(
                    f"Watch: {self._py_node.get_name()} (not supported "
                    "for this node type)"
                )
                self._cached_vars      = {}
                self._cached_framework = {}
                self._watch_cb.setChecked(False)
                self._set_controls_enabled(False)
                return

            self._set_controls_enabled(True)

            _enabled = bool(self._py_node.is_watch_enabled())
            self._watch_cb.setChecked(_enabled)

            # Input/output values show REGARDLESS of the capture toggle --
            # they are cheap live plug reads, not instrumented captures. Only
            # Locals / Temporary / Persistent need Enable Watch, so read them
            # BEFORE the enable gate.
            self._cached_inputs  = self._read_io_values("get_input_attr_map")
            self._cached_outputs = self._read_io_values("get_output_attr_map")

            # Capture OFF hides Locals AND stored-var rows, but Inputs /
            # Outputs above still render.
            if not _enabled:
                self._stop_live_timer()
                self._cached_vars       = {}
                self._cached_stored     = {}
                self._cached_registered = set()
                self._cached_framework  = {}
                self._populate_tree()
                return

            # Watch is on: drive the main-thread live-refresh poll.
            self._start_live_timer()

            try:
                snap = self._py_node.get_watch_vars()
            except Exception:
                snap = None
            snap = dict(snap or {})
            # The framework surface rides in the snapshot under a reserved
            # key; lift it out BEFORE capping so it never renders as a Locals
            # row called "__framework__".
            self._cached_framework = _cap_watch_dict(
                snap.pop(WATCH_FRAMEWORK_KEY, None) or {})
            self._cached_vars = _cap_watch_dict(snap)

            # Also pull the live in-memory store (self.X temporary +
            # persistent). Cheap read; no instrumentation needed.
            try:
                from mpynode._common.storedvars.stored_vars_api import (
                    get_variable_names,
                    get_variables,
                )

                _nm                     = self._py_node.get_name()
                self._cached_stored     = _cap_watch_dict(get_variables(_nm) or {})
                self._cached_registered = set(get_variable_names(_nm))
            except Exception:
                self._cached_stored     = {}
                self._cached_registered = set()

            self._populate_tree()
        finally:
            self._refreshing = False

    def refresh_stored_only(self) -> None:
        """Re-read the in-memory stored vars and repopulate -- NOTHING else.

        The stored-var listener needs a refresh that cannot re-enter compute.
        Full :meth:`refresh` reads OUTPUT plugs (``_read_io_values``), which
        forces the node's compute(), which writes ``_watchVarsData``, whose
        callback calls refresh() again -- the loop the ``_refreshing`` guard
        exists for. That hazard is why the listener used to skip this widget
        entirely, leaving Watch showing a stale value after a scripted
        ``set_variable``. This path touches the store and the tree only, so it
        is safe from a plug callback.

        Gated the same way refresh() gates these rows: with capture OFF the
        stored caches are deliberately empty and must stay that way.
        """
        if self._refreshing or self._py_node is None:
            return
        if not hasattr(self._py_node, "is_watch_enabled"):
            return
        self._refreshing = True
        try:
            if not self._py_node.is_watch_enabled():
                return
            from mpynode._common.storedvars.stored_vars_api import (
                get_variable_names,
                get_variables,
            )

            name                    = self._py_node.get_name()
            self._cached_stored     = _cap_watch_dict(get_variables(name) or {})
            self._cached_registered = set(get_variable_names(name))
            self._populate_tree()
        except Exception:
            pass
        finally:
            self._refreshing = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def suspend_live(self) -> None:
        """Pause the live-refresh poll for the duration of a Save / F5.

        While a save runs it transiently re-dirties the node (set-expression
        + force_one_eval's bump/restore). An 80 ms timer tick landing in one
        of those dirty windows would force a full compute (doubled across a
        connected node chain), making the save fire the expression a varying
        number of extra times. Suspending the poll leaves only the single
        deterministic force_one_eval. Pair with :meth:`resume_live`."""
        self._live_suspended = True
        try:
            self._live_was_active = self._live_timer.isActive()
        except Exception:
            self._live_was_active = False
        self._stop_live_timer()

    def resume_live(self) -> None:
        """Undo :meth:`suspend_live` -- restart the poll only if it was
        actually running before the save (so we never start it when Watch is
        off)."""
        self._live_suspended = False
        if self._live_was_active:
            self._start_live_timer()

    def _start_live_timer(self) -> None:
        if self._live_suspended:
            return
        try:
            if not self._live_timer.isActive():
                self._live_timer.start()
        except Exception:
            pass

    def _stop_live_timer(self) -> None:
        try:
            if self._live_timer.isActive():
                self._live_timer.stop()
        except Exception:
            pass

    def _on_live_tick(self) -> None:
        """Main-thread live-refresh poll (see __init__): re-read the snapshot
        + live plug values and reconcile. Skips when suspended (mid-save), a
        refresh is already in flight, no node is selected, or the tab isn't
        visible."""
        if self._live_suspended or self._refreshing or self._py_node is None:
            return
        try:
            if not self.isVisible():
                return
        except Exception:
            pass
        try:
            self.refresh()
        except Exception:
            pass

    def _read_io_values(self, map_method_name: str) -> dict:
        """Read live values for the node's user input or output plugs.

        ``map_method_name`` is ``"get_input_attr_map"`` or
        ``"get_output_attr_map"``. Values are read straight off the plugs via
        ``cmds.getAttr`` (API-agnostic, works for every wrapper type) and
        reshaped for display. Returns {} for node types without the map.
        """
        node = self._py_node
        if node is None or not hasattr(node, map_method_name):
            return {}
        try:
            attr_map = getattr(node, map_method_name)() or {}
        except Exception:
            return {}
        if not attr_map:
            return {}
        name = node.get_name()
        out: dict = {}
        for attr, meta in attr_map.items():
            atype = (meta or {}).get("attr_type", "")
            # cmds.getAttr on a geometry plug raises AND evaluates the
            # (possibly heavy / animated) upstream geometry. On the live-poll
            # timer that spams the script editor and can freeze Maya, so show
            # a non-evaluating placeholder.
            if atype in _NON_DISPLAYABLE_TYPES:
                out[attr] = _geometry_label(name, attr, atype)
                continue
            if bool((meta or {}).get("is_array", False)):
                # getAttr on a typed-multi parent raises; read elementwise.
                out[attr] = read_multi_plug_values(name, attr, meta)
                continue
            try:
                val = mc.getAttr(name + "." + attr)
            except Exception:
                continue
            if atype == "python":
                # python attrs carry base64+pickle bus data; show the decoded
                # object and its real type, not the opaque string.
                out[attr] = decode_io_value_cached(
                    self._py_decode_cache, name + "." + attr, val, atype
                )
                continue
            out[attr] = reshape_plug_value(val, meta)
        return _cap_watch_dict(out)

    def _populate_tree(self) -> None:
        """Apply the current filter + scope and update the tree IN PLACE
        from cached data, grouped into Locals / Temporary / Persistent.

        Updating in place (reconciling existing items) rather than
        ``clear()`` + rebuild is what keeps the panel usable while values
        change LIVE -- e.g. dragging a locator that drives an interactive
        deformer now re-evaluates every frame, writing a fresh watch
        snapshot each time. A destructive rebuild on every snapshot reset
        the user's expand/collapse state, selection and scroll position
        (the category appeared to "collapse" mid-drag). Reconciling keeps
        all of that stable and only touches the values that actually
        changed.
        """
        filt = self._filter_edit.text()

        temp = {
            k: v
            for k, v in self._cached_stored.items()
            if k not in self._cached_registered and not k.startswith("_")
        }
        persist = {
            k: v
            for k, v in self._cached_stored.items()
            if k in self._cached_registered
        }
        # User inputs reach the expression as bare names, so they also land
        # in the locals snapshot. They have their own Inputs / Outputs
        # groups, so strip them here to avoid showing the value twice.
        io_names = set(self._cached_inputs) | set(self._cached_outputs)
        locals_only = {
            k: v for k, v in self._cached_vars.items() if k not in io_names
        }
        # Same for the framework surface: ``self.<input>`` reads make user
        # inputs show up here too, and they already have an Inputs group.
        framework_only = {
            k: v for k, v in self._cached_framework.items() if k not in io_names
        }

        groups = []
        if self._show_inputs_cb.isChecked():
            groups.append(("Inputs", apply_filter(self._cached_inputs, filt)))
        if self._show_outputs_cb.isChecked():
            groups.append(("Outputs", apply_filter(self._cached_outputs, filt)))
        if self._show_framework_cb.isChecked():
            groups.append(("Framework", apply_filter(framework_only, filt)))
        if self._show_locals_cb.isChecked():
            groups.append(("Locals", apply_filter(locals_only, filt)))
        if self._show_temp_cb.isChecked():
            groups.append(("Temporary", apply_filter(temp, filt)))
        if self._show_persist_cb.isChecked():
            groups.append(("Persistent", apply_filter(persist, filt)))

        # Only non-empty selected groups get a header.
        wanted        = [(label, data) for label, data in groups if data]
        wanted_labels = {label for label, _ in wanted}

        existing_headers = {}
        for i in range(self._tree.topLevelItemCount()):
            h                           = self._tree.topLevelItem(i)
            existing_headers[h.text(0)] = h

        # Drop headers whose group is now empty / hidden.
        for label in list(existing_headers.keys()):
            if label not in wanted_labels:
                idx = self._tree.indexOfTopLevelItem(existing_headers[label])
                if idx >= 0:
                    cleanup_media_widgets(self._tree, existing_headers[label])
                    self._tree.takeTopLevelItem(idx)
                del existing_headers[label]

        # Add / update headers in the canonical order.
        for pos, (label, data) in enumerate(wanted):
            header = existing_headers.get(label)
            if header is None:
                header = QTreeWidgetItem()
                header.setText(0, label)
                header.setFlags(Qt.ItemIsEnabled)
                self._tree.insertTopLevelItem(pos, header)
                # Span so the header text doesn't drive column sizing.
                header.setFirstColumnSpanned(True)
                existing_headers[label] = header
                # First creation only; afterwards respect the user's state.
                self._tree.expandItem(header)
            self._sync_group_children(header, data)

    def _sync_group_children(self, header, data: dict) -> None:
        """Reconcile a header's child rows with ``data`` (name -> value),
        updating values in place and adding / removing rows as needed."""
        existing = {}
        for i in range(header.childCount()):
            c                   = header.child(i)
            existing[c.text(0)] = c

        for name in list(existing.keys()):
            if name not in data:
                cleanup_media_widgets(self._tree, existing[name])
                header.removeChild(existing[name])
                del existing[name]

        # Add / update the rest in sorted order.
        for pos, name in enumerate(sorted(data.keys())):
            value = data[name]
            item  = existing.get(name)
            if item is None:
                item = QTreeWidgetItem()
                item.setText(0, name)
                header.insertChild(pos, item)
                # Top-align so name + type + size line up with the FIRST line
                # of a multi-line value instead of centering.
                for _c in range(4):
                    item.setTextAlignment(_c, Qt.AlignLeft | Qt.AlignTop)
                # Monospace the Value column so numpy reprs line up.
                if self._mono_font is not None:
                    try:
                        item.setFont(1, self._mono_font)
                    except Exception:
                        pass
            # The live update. Image-ish vars get an inline thumbnail plus a
            # right-click source<->image toggle; everything else is text.
            attach_value(item, 1, value, _format_value(value))
            item.setText(2, _format_type(value))
            item.setText(3, _format_size(value))
            # Re-apply the user's remembered image/source choice so it
            # survives the live refresh (attach_value resets it to default).
            if name in self._image_view_modes:
                set_image_view(item, 1, self._image_view_modes[name])
            # Same for the waveform choice, then (re)install the per-row
            # media widget. Idempotent: an already-correct widget is left
            # alone so a GIF doesn't restart / a waveform isn't re-decoded.
            _wave_pref = render_waveform_pref_on()
            if (_wave_pref and name in self._waveform_view_modes
                    and is_audio_item(item, 1)):
                set_waveform_view(item, 1, self._waveform_view_modes[name])
            try:
                refresh_media_widget(
                    self._tree, item, 1,
                    self._ensure_waveform_player() if _wave_pref else None,
                )
            except Exception:
                pass

    def _on_scope_changed(self, *args) -> None:
        """A Show: scope checkbox toggled -> re-render from cache."""
        if self._refreshing:
            return
        try:
            self._populate_tree()
        except Exception:
            pass

    def _set_controls_enabled(self, on: bool) -> None:
        self._watch_cb.setEnabled(on)
        self._filter_edit.setEnabled(on)

    def _on_watch_toggled(self, checked: bool) -> None:
        if self._refreshing or self._py_node is None:
            return
        try:
            mc.setAttr(self._py_node.get_name() + ".watch_enabled", bool(checked))
        except Exception:
            pass
        # Force one compute on ON so the snapshot plug populates now;
        # otherwise the panel stays empty until the user triggers a compute.
        if checked:
            try:
                from mpynode._base.eval_helpers import force_one_eval

                force_one_eval(self._py_node)
            except Exception:
                pass
        else:
            # Clear the snapshot plug so stale values don't linger.
            try:
                mc.setAttr(
                    self._py_node.get_name() + "._watchVarsData",
                    "",
                    type="string",
                )
            except Exception:
                pass
        # refresh() gates the whole panel on the watch-enabled flag, so the
        # tab matches the toggle in both directions.
        try:
            self.refresh()
        except Exception:
            pass

    def _on_context_menu(self, pos) -> None:
        """Right-click a Value cell to toggle the source repr against a
        rendered thumbnail (image rows) or a waveform (audio rows)."""
        item = self._tree.itemAt(pos)
        if item is None:
            return
        is_img = is_previewable_item(item, 1)
        is_aud = is_audio_item(item, 1) and render_waveform_pref_on()
        if not is_img and not is_aud:
            return
        from mpynode.ui.qt_wrapper import QMenu

        menu     = QMenu(self._tree)
        img_act  = None
        wave_act = None
        if is_img:
            img_lbl = (
                "Show as Source" if is_showing_image(item, 1) else "Show as Image"
            )
            img_act = menu.addAction(img_lbl)
        if is_aud:
            wave_lbl = (
                "Show as Source" if is_showing_waveform(item, 1)
                else "Show as Waveform"
            )
            wave_act = menu.addAction(wave_lbl)
        gpos   = self._tree.viewport().mapToGlobal(pos)
        run    = getattr(menu, "exec_", None) or menu.exec
        chosen = run(gpos)
        if img_act is not None and chosen is img_act:
            new_state = toggle_value_mode(item, 1)
            if new_state is not None:
                # Remember by variable name so the live refresh keeps it.
                self._image_view_modes[item.text(0)] = bool(new_state)
                refresh_media_widget(
                    self._tree, item, 1, self._ensure_waveform_player()
                )
                idx = self._tree.indexFromItem(item, 1)
                self._img_delegate.sizeHintChanged.emit(idx)
                self._tree.viewport().update()
        elif wave_act is not None and chosen is wave_act:
            new_state = toggle_waveform_view(item, 1)
            if new_state is not None:
                self._waveform_view_modes[item.text(0)] = bool(new_state)
                refresh_media_widget(
                    self._tree, item, 1, self._ensure_waveform_player()
                )
                idx = self._tree.indexFromItem(item, 1)
                self._img_delegate.sizeHintChanged.emit(idx)
                self._tree.viewport().update()

    def _on_filter_changed(self, _text: str) -> None:
        if self._refreshing:
            return
        self._populate_tree()
