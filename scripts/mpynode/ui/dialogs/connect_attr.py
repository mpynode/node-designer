"""NDConnectInputAttrDialog + NDConnectOutputAttrDialog.

Multi-source selection + automatic next-available-index for multi
(array) targets.

Connection-filter quality-of-life (prefix-anchored substring +
``Show all attrs`` toggle to surface non-keyable attrs).

Redesigned filter / sort / hide model:
  * Always show ``cmds.listAttr(settable=True)`` so compound parents
    (``translate``, ``rotate``, matrices, quaternions) are visible by
    default. The old ``Show all attrs`` checkbox conflated noise hiding
    with compound hiding and is gone.
  * New checkbox: ``Hide pivots & limits`` (default ON via prefs). Strips
    just the ``rotatePivot* / scalePivot* / *Limit*`` families instead
    of the whole non-keyable surface.
  * Filter input is now ``fnmatch.fnmatchcase`` when it contains
    ``*? [`` glob metacharacters, otherwise a case-INsensitive
    substring match against the full ``node.attr`` string. This makes
    ``pCube1.tr*``, ``*translate``, ``rotate`` all just work.
  * Tree headers are clickable. Each is a 3-way cycle:
      * ``Node.Attr``: Selection \u2192 Natsort\u2191 \u2192 Natsort\u2193
      * ``Type``: TypeAlpha\u2191 \u2192 TypeAlpha\u2193 \u2192 TypeCategory
        (compound vectors / matrices / quaternions \u2192 linear/angle scalars
        \u2192 plain numerics \u2192 typed data \u2192 strings \u2192 other).
    The current sort mode + arrow indicator is rendered into the header
    label. Initial sort comes from ``connect_dialog_sort_mode_default``
    pref (default ``selection``).

Returns a list of (source_plug, target_plug) pairs on Accept.
"""

from __future__ import annotations

import fnmatch
import re

from maya import cmds
from mpynode.ui.qt_wrapper import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)


# ---------------------------------------------------------------------------
# Pivot / limit detection
# ---------------------------------------------------------------------------

# Case-sensitive substrings matched against an attr's SHORT name: the noise
# families ``listAttr(settable=True)`` dumps on a transform-rich rig, which
# almost nobody connects to. Stripped when ``Hide pivots & limits`` is on.
_PIVOT_LIMIT_PATTERNS = (
    "rotatePivot",
    "scalePivot",
    "rotateAxis",
    "rotateOrient",
    "Limit",
    "limit",
    "minRot",
    "maxRot",
    "minScale",
    "maxScale",
    "minTrans",
    "maxTrans",
    "selectHandle",
    "displayHandle",
    "displayLocalAxis",
    "displayRotatePivot",
    "displayScalePivot",
)


def _is_pivot_or_limit(attr_name: str) -> bool:
    """Return True if ``attr_name`` looks like a pivot or limit attribute."""
    return any(pat in attr_name for pat in _PIVOT_LIMIT_PATTERNS)


# ---------------------------------------------------------------------------
# Type-category bucketing
# ---------------------------------------------------------------------------

# Lower index = earlier in the type-category sort. The order matches what a
# rigger scrolling for a compatible source usually wants: vectors (the most
# common connect target) first, then matrices/quaternions, linear/angle
# scalars, plain numerics, typed data, strings, everything else.
_TYPE_CATEGORY_ORDER: dict[str, int] = {
    # Compound vectors (Tier 0 \u2014 first)
    "double3":  0,
    "float3":   0,
    "short3":   0,
    "long3":    0,
    "compound": 0,
    # Compound matrices
    "matrix":    1,
    "fltMatrix": 1,
    # Compound quaternions
    "double4": 2,
    "float4":  2,
    # Linear / angle scalars + time
    "doubleLinear": 3,
    "doubleAngle":  3,
    "time":         3,
    # Plain numerics
    "double": 4,
    "float":  4,
    "long":   4,
    "short":  4,
    "byte":   4,
    "bool":   4,
    "enum":   4,
    "int":    4,
    # Typed data
    "mesh":          5,
    "nurbsCurve":    5,
    "nurbsSurface":  5,
    "polyComp":      5,
    "lattice":       5,
    "subdiv":        5,
    "componentList": 5,
    # Strings
    "string":      6,
    "stringArray": 6,
    "message":     6,
}


def _type_category_key(type_str: str) -> tuple:
    """Sort key: (category index, type name) \u2014 within a category, types
    are alpha-sorted so ``double3`` < ``float3`` etc."""
    cat = _TYPE_CATEGORY_ORDER.get(type_str, 7)
    return (cat, type_str.lower(), type_str)


# ---------------------------------------------------------------------------
# Natural sort (no third-party `natsort` dep needed; ~10 lines pure Python).
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"(\d+)")


def _natural_key(s: str) -> list:
    """Split ``s`` into alternating text-and-int chunks so e.g.
    ``pCube2 < pCube10`` instead of string-sort's ``pCube10 < pCube2``."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in _NUM_RE.split(s or "")
        if part
    ]


# ---------------------------------------------------------------------------
# Type compatibility
# ---------------------------------------------------------------------------
# Maya raw attribute type strings -> a category. Two plugs are DG-connect-
# compatible iff their categories intersect. Type names come from
# ``cmds.getAttr(plug, type=True)`` / ``cmds.attributeQuery(attributeType)``.

_NUMERIC_SCALAR_TYPES: frozenset[str] = frozenset(
    {
        # plain numerics
        "float",
        "double",
        "long",
        "short",
        "byte",
        "char",
        "bool",
        # unit scalars
        "doubleAngle",
        "doubleLinear",
        "time",
        # enums
        "enum",
    }
)
_VECTOR3_TYPES: frozenset[str] = frozenset(
    {
        "float3",
        "double3",
        "long3",
        "short3",
    }
)
_VECTOR4_TYPES: frozenset[str] = frozenset(
    {
        "float4",
        "double4",
    }
)
_MATRIX_TYPES:        frozenset[str] = frozenset({"matrix", "fltMatrix"})
_STRING_TYPES:        frozenset[str] = frozenset({"string"})
_MESH_TYPES:          frozenset[str] = frozenset({"mesh"})
_NURBS_CURVE_TYPES:   frozenset[str] = frozenset({"nurbsCurve"})
_NURBS_SURFACE_TYPES: frozenset[str] = frozenset({"nurbsSurface"})


def _type_categories(maya_type: str) -> frozenset[str]:
    """Return the set of compat categories a given Maya type belongs to.

    Returns an empty set for unknown types so the caller can decide
    whether to be permissive or strict.
    """
    cats: set[str] = set()
    if maya_type in _NUMERIC_SCALAR_TYPES:
        cats.add("scalar")
    if maya_type in _VECTOR3_TYPES:
        cats.add("vector3")
    if maya_type in _VECTOR4_TYPES:
        cats.add("vector4")
    if maya_type in _MATRIX_TYPES:
        cats.add("matrix")
    if maya_type in _STRING_TYPES:
        cats.add("string")
    if maya_type in _MESH_TYPES:
        cats.add("mesh")
    if maya_type in _NURBS_CURVE_TYPES:
        cats.add("nurbs_curve")
    if maya_type in _NURBS_SURFACE_TYPES:
        cats.add("nurbs_surface")
    return frozenset(cats)


def _type_compatible(target_maya_type: str, source_maya_type: str) -> bool:
    """Returns True iff a plug of ``source_maya_type`` can be DG-connected
    to a plug of ``target_maya_type`` (or vice versa \u2014 the relation is
    symmetric for our purposes).

    Maya's connection rules in practice:
      * Numeric scalars (float/double/int/bool/angle/time/enum) are all
        interconvertible \u2014 you can connect a bool into a float input.
      * 3-vector compounds (float3/double3) match each other.
      * 4-vector compounds (float4/double4) match each other.
      * Matrix matches matrix (and fltMatrix).
      * Typed data (mesh / nurbsCurve / nurbsSurface / string) only
        connects to its own type.

    Unknown types are treated as compatible (be permissive when we
    can't tell \u2014 don't hide a plug the user might actually want).
    """
    if not target_maya_type or not source_maya_type:
        return True  # unknown \u2014 be permissive
    if target_maya_type == source_maya_type:
        return True
    target_cats = _type_categories(target_maya_type)
    source_cats = _type_categories(source_maya_type)
    if not target_cats or not source_cats:
        # At least one is uncategorized \u2014 permissive fallback.
        return True
    return bool(target_cats & source_cats)


def _resolve_target_attr_type(target_plug: str) -> str:
    """Best-effort resolve the Maya attribute type of a plug.

    Handles multi parents (``cmds.attributeQuery`` returns the element
    type by default) AND typed attrs (which return ``"typed"`` from
    attributeQuery; we drill into ``cmds.getAttr type=True`` for the
    real data type).
    """
    node, _, attr = target_plug.partition(".")
    if not node or not attr:
        return ""
    # Strip trailing [N] / [0] / etc. for attributeQuery.
    attr_root = attr.split("[", 1)[0]
    t         = ""
    try:
        t = cmds.attributeQuery(attr_root, node=node, attributeType=True) or ""
    except Exception:
        t = ""
    if t == "typed" or not t:
        # Typed attr or unknown \u2014 ask getAttr for the real data type.
        for probe in (target_plug, target_plug + "[0]"):
            try:
                got = cmds.getAttr(probe, type=True) or ""
                if got and got!= "typed":
                    return got
            except Exception:
                pass
    return t or ""


# ---------------------------------------------------------------------------
# Candidate-plug enumeration
# ---------------------------------------------------------------------------


def _list_candidate_plugs(
    hide_pivots: bool = True,
) -> list[tuple[str, str, str]]:
    """Walk the current Maya selection and return every settable attr as
    a list of ``(node_name, attr_long_name, attr_type)`` tuples.

    always uses ``cmds.listAttr(settable=True)`` so
    compound parents are visible. ``hide_pivots`` (default True) strips
    the rotatePivot / scalePivot / *Limit* noise.

    Selection order is preserved \u2014 ``cmds.ls(sl=True)`` returns nodes
    in selection order, and per-node attrs come back in the order Maya
    stores them (which matches the AE / Channel-Box layout).
    """
    sel = cmds.ls(sl=True) or []
    rows: list[tuple[str, str, str]] = []
    for node in sel:
        try:
            attrs = cmds.listAttr(node, settable=True) or []
        except Exception:
            attrs = []
        for attr in attrs:
            if hide_pivots and _is_pivot_or_limit(attr):
                continue
            try:
                a_type = cmds.getAttr(f"{node}.{attr}", type=True)
            except Exception:
                a_type = ""
            rows.append((node, attr, a_type or ""))
    return rows


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


def _filter_matches(node_attr: str, filter_text: str) -> bool:
    """Stricter filter \u2014 EXACT match against the
    attribute name (last segment after ``.``) unless a wildcard
    metacharacter is present, in which case fnmatch glob applies.

    Behavior:
      * Empty filter \u2192 match everything (initial state).
      * Filter contains ``*? [`` \u2192 fnmatch glob applied to the FULL
        ``node.attr`` string. Wildcard semantics:
            ``"pCube?.r*"``    \u2192 single-char glob + suffix glob.
            ``"*translate*"``  \u2192 substring-style wildcard.
            ``"tx"``           \u2192 exact match (no wildcard, no glob).
      * Filter has NO wildcard \u2192 case-insensitive EXACT match against
        the ATTRIBUTE NAME (the part after the last ``.``). So typing
        ``translate`` matches only ``pCube1.translate`` (and any other
        node's ``translate`` attr), NOT ``pCube1.translateX``.
    """
    pat = (filter_text or "").strip()
    if not pat:
        return True
    has_glob = any(ch in pat for ch in ("*", "?", "["))
    full     = (node_attr or "").lower()
    needle   = pat.lower()
    if has_glob:
        return fnmatch.fnmatchcase(full, needle)
    # No wildcard \u2192 strict exact match against the attr name.
    attr_part = full.rsplit(".", 1)[-1]
    return needle == attr_part


# ---------------------------------------------------------------------------
# Multi-index helper
# ---------------------------------------------------------------------------


def _next_available_multi_index(plug_name: str) -> int:
    """Return the next free index for a multi plug (max existing + 1)."""
    try:
        indices = cmds.getAttr(plug_name, multiIndices=True) or []
    except Exception:
        return 0
    if not indices:
        return 0
    return max(indices) + 1


def compute_connection_pairs(
    target_plug:     str,
    target_is_multi: bool,
    source_plugs:    list[str],
    clobber:         bool      = False,
) -> list[tuple[str, str]]:
    """Given the target + chosen source plugs, return the list of
    (source, dest) connection pairs.

    For a MULTI target, each source maps to a distinct element index.
    ``clobber=True`` allocates from index 0 (the caller is expected to
    trim the array first -- see :class:`_ClobberMultiConnectCommand`);
    ``clobber=False`` (default) appends at the next-available index.
    For a scalar target, only the first source is used.
    """
    if not source_plugs:
        return []
    if not target_is_multi:
        # Scalar target: pick the first source only.
        return [(source_plugs[0], target_plug)]

    # Multi target: distribute over indices -- from 0 when clobbering,
    # else continue past the existing elements.
    pairs: list[tuple[str, str]] = []
    next_idx = 0 if clobber else _next_available_multi_index(target_plug)
    for src in source_plugs:
        dst = f"{target_plug}[{next_idx}]"
        pairs.append((src, dst))
        next_idx += 1
    return pairs


def _next_available_source_index(plug_name: str) -> int:
    """Return the next element index to use when wiring a multi OUTPUT plug
    out to destinations.

    Unlike :func:`_next_available_multi_index` -- which returns
    ``max(existing index)+1`` over EVERY index that exists (including those
    that merely hold cached compute data) -- this skips only indices that
    are ALREADY wired as an outgoing source. A freshly-evaluated output
    whose elements ``[0..N-1]`` hold computed data but drive nothing yet is
    therefore wired starting at index 0, which is exactly where the node's
    compute writes (``write_multi_plug_value`` fills ``[0..len-1]``).

    This fixes the "connected transforms stuck at 0,0,0" bug: previously an
    ungated node that had cached N elements got its destinations wired at
    ``[N..2N-1]`` (past the data region), and compute -- which "leaves
    pre-existing higher indices in place" -- never wrote them.
    """
    try:
        conns = (
            cmds.listConnections(
                plug_name,
                source      = False,
                destination = True,
                plugs       = True,
                connections = True,
            )
            or []
        )
    except Exception:
        return 0
    # connections=True gives a flat [thisElemPlug, otherPlug, ...] list, so the
    # even entries are this node's element plugs ("node.points[3]").
    src_indices: list[int] = []
    for src in conns[0::2]:
        m = re.search(r"\[(\d+)\]\s*$", src)
        if m:
            src_indices.append(int(m.group(1)))
    if not src_indices:
        return 0
    return max(src_indices) + 1


def compute_output_connection_pairs(
    source_plug:     str,
    source_is_multi: bool,
    dest_plugs:      list[str],
    clobber:         bool      = False,
) -> list[tuple[str, str]]:
    """Given a node's OUTPUT plug + the chosen destination plugs, return the
    list of (source, dest) connection pairs.

    For a MULTI output, each destination is driven by a distinct source
    element. ``clobber=True`` allocates from index 0 (the caller is expected
    to trim the array first -- see :class:`_ClobberMultiConnectCommand`);
    ``clobber=False`` (default) allocates from
    :func:`_next_available_source_index` so the wiring aligns with the indices
    compute actually writes (starting at 0 for a fresh output, appending past
    indices already wired as a source). For a scalar output, the single output
    drives every destination.
    """
    if not dest_plugs:
        return []
    if not source_is_multi:
        return [(source_plug, dst) for dst in dest_plugs]

    pairs: list[tuple[str, str]] = []
    next_idx = 0 if clobber else _next_available_source_index(source_plug)
    for dst in dest_plugs:
        pairs.append((f"{source_plug}[{next_idx}]", dst))
        next_idx += 1
    return pairs


# ---------------------------------------------------------------------------
# Multi (array) TARGET attributes on the OTHER node
# ---------------------------------------------------------------------------
# ``cmds.listAttr(settable=True)`` returns compound children under a multi
# ancestor as DOTTED, un-indexed names -- e.g. ``polyColorPerVertex1.
# vertexColor.vertexColorRGB``. Passing that to ``connectAttr`` fails with
# "Incompatible multi-attribute parent levels": a multi ancestor requires an
# ``[index]``. These helpers auto-insert it, so one output can fan across the
# target's elements or an array output can map element-wise onto them.


def _attr_is_multi(node: str, attr_name: str) -> bool:
    """True if ``node.attr_name`` is a multi (array) attribute."""
    try:
        return bool(cmds.attributeQuery(attr_name, node=node, multi=True))
    except Exception:
        return False


def parse_index_range(text: str, default_count: int) -> list[int]:
    """Parse a user range string into a sorted, de-duplicated index list.

    ``""`` / ``"all"``      -> ``range(default_count)``
    ``"0:14"``              -> ``range(0, 14)``  (end-exclusive, slice-style)
    ``"0,2,5"``             -> ``[0, 2, 5]``
    ``"0:4,7,9:11"``        -> combination of the above

    Unparseable tokens are skipped. Negative indices are dropped.
    """
    s = (text or "").strip().lower()
    if not s or s == "all":
        return list(range(max(0, int(default_count))))
    out: list[int] = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if ":" in tok:
            a, _, b = tok.partition(":")
            try:
                start = int(a) if a.strip() else 0
                end   = int(b) if b.strip() else int(default_count)
            except ValueError:
                continue
            out.extend(range(start, end))
        else:
            try:
                out.append(int(tok))
            except ValueError:
                continue
    return sorted({i for i in out if i >= 0})


def resolve_multi_target(target_plug: str) -> dict:
    """Inspect a candidate DESTINATION plug for an un-indexed multi ancestor.

    Returns a dict:
      ``is_multi_target``  -- the plug lives under a multi ancestor with no index
      ``template``         -- ``"node.pre[{idx}].post"`` (``str.format(idx=...)``)
                              or ``None`` when unsupported
      ``existing_count``   -- number of elements already present on the multi
      ``existing_indices`` -- their logical indices
      ``nested``           -- 2+ un-indexed multi ancestors (unsupported)
    """
    info = {
        "is_multi_target":  False,
        "template":         None,
        "existing_count":   0,
        "existing_indices": [],
        "nested":           False,
    }
    node, _, attr = (target_plug or "").partition(".")
    if not node or not attr:
        return info
    segments = attr.split(".")
    # Un-indexed multi segments (a segment already carrying ``[idx]`` is fine).
    multi_positions = [
        i
        for i, seg in enumerate(segments)
        if "[" not in seg and _attr_is_multi(node, seg)
    ]
    if not multi_positions:
        return info
    info["is_multi_target"] = True
    if len(multi_positions) > 1:
        info["nested"] = True  # unsupported: 2+ un-indexed multi ancestors
        return info
    pos      = multi_positions[0]
    ancestor = node + "." + ".".join(segments[: pos + 1])
    try:
        idx = cmds.getAttr(ancestor, multiIndices=True) or []
    except Exception:
        idx = []
    info["existing_indices"] = list(idx)
    info["existing_count"]   = len(idx)
    tmpl_segments            = list(segments)
    tmpl_segments[pos]       = segments[pos] + "[{idx}]"
    info["template"]         = node + "." + ".".join(tmpl_segments)
    return info


def expand_dest_plugs(
    dest_plugs: list[str], range_text: str = ""
) -> tuple[list[str], list[str]]:
    """Expand any multi-target leaf in ``dest_plugs`` into concrete indexed
    plugs, using ``range_text`` (or the target's existing element count).

    Returns ``(expanded_plugs, warnings)``. Plain (non-multi) plugs pass
    through unchanged; nested double-multi targets are skipped with a warning.
    """
    expanded: list[str] = []
    warnings: list[str] = []
    for plug in dest_plugs:
        info = resolve_multi_target(plug)
        if not info["is_multi_target"]:
            expanded.append(plug)
            continue
        if info["nested"] or not info["template"]:
            warnings.append(
                f"{plug}: nested array attributes are not supported for "
                "auto-indexed connection; connect an explicit element."
            )
            continue
        rt = (range_text or "").strip().lower()
        if rt in ("", "all"):
            # Blank / 'all' -> drive exactly the elements that already exist
            # (their real logical indices, which may be sparse/non-0-based).
            indices = list(info["existing_indices"])
            if not indices:
                indices = [0]  # empty multi + no range -> seed element [0]
        else:
            indices = parse_index_range(range_text, info["existing_count"])
            if not indices:
                # A non-blank range that resolves to nothing (e.g. '10:5',
                # '2:2', garbage) is a user error -- surface it rather than
                # silently wiring an unrequested [0].
                warnings.append(
                    f"{plug}: range {range_text!r} selected no valid indices."
                )
                continue
        for i in indices:
            expanded.append(info["template"].format(idx=i))
    return expanded, warnings


# The resolution above is DIRECTION-AGNOSTIC: a SOURCE plug under an un-indexed
# multi ancestor (driver.worldMatrix, blendShape.weight) needs the same ``[idx]``
# insertion a destination does. These source-named aliases let the INPUT dialog
# read symmetrically with the OUTPUT one.
resolve_multi_source = resolve_multi_target
expand_source_plugs  = expand_dest_plugs


# ---------------------------------------------------------------------------
# Sort modes (per-column 3-way cycle)
# ---------------------------------------------------------------------------

_NODE_SORT_MODES = ("selection", "natural_asc", "natural_desc")
_TYPE_SORT_MODES = ("type_alpha_asc", "type_alpha_desc", "type_category")
_ALL_SORT_MODES  = _NODE_SORT_MODES + _TYPE_SORT_MODES

# Header arrow indicator per mode.
_MODE_INDICATORS = {
    "selection":       "\u2022",  # bullet
    "natural_asc":     "\u2191",  # up arrow
    "natural_desc":    "\u2193",  # down arrow
    "type_alpha_asc":  "\u2191",
    "type_alpha_desc": "\u2193",
    "type_category":   "\u2605",  # star
}


def _sort_rows(
    rows: list[tuple[str, str, str]], mode: str
) -> list[tuple[str, str, str]]:
    """Sort the (node, attr, type) row list by the given mode. Pure
    function \u2014 returns a new list, doesn't mutate the input.

    ``mode == "selection"`` is a no-op (preserves enumeration order).
    """
    if mode == "selection" or not rows:
        return list(rows)
    if mode == "natural_asc":
        return sorted(rows, key=lambda r: _natural_key(f"{r[0]}.{r[1]}"))
    if mode == "natural_desc":
        return sorted(rows, key=lambda r: _natural_key(f"{r[0]}.{r[1]}"), reverse=True)
    if mode == "type_alpha_asc":
        return sorted(
            rows,
            key=lambda r: ((r[2] or "").lower(), _natural_key(f"{r[0]}.{r[1]}")),
        )
    if mode == "type_alpha_desc":
        return sorted(
            rows,
            key     = lambda r: ((r[2] or "").lower(), _natural_key(f"{r[0]}.{r[1]}")),
            reverse = True,
        )
    if mode == "type_category":
        return sorted(
            rows,
            key=lambda r: (
                _type_category_key(r[2] or ""),
                _natural_key(f"{r[0]}.{r[1]}"),
            ),
        )
    # Unknown mode \u2014 fall back to selection order.
    return list(rows)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class _BaseConnectDialog(QDialog):
    HEADER_LABELS = ("Node.Attr", "Type")

    def __init__(self, parent, target_plug: str, target_is_multi: bool, title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(560, 440)

        self._target_plug     = target_plug
        self._target_is_multi = target_is_multi
        self._chosen:     list[str] = []
        self._extra_flag: bool = False
        # Multi-side index policy: True = clobber (wire from index 0 after
        # trimming the array), False = append at next-available. Only
        # meaningful when the mPy attr itself is a multi.
        self._clobber: bool = False

        # sort state. (column_index, mode)
        # Column 0 = Node.Attr, Column 1 = Type. Mode comes from prefs.
        self._sort_mode = self._initial_sort_mode()
        self._sort_col  = 0 if self._sort_mode in _NODE_SORT_MODES else 1

        self._build_ui()
        self._populate_tree()

    @staticmethod
    def _initial_sort_mode() -> str:
        """Read the default sort mode from prefs. Falls back to selection."""
        try:
            from mpynode.ui.preferences import get_pref

            mode = get_pref("connect_dialog_sort_mode_default", "selection")
        except Exception:
            mode = "selection"
        if mode not in _ALL_SORT_MODES:
            mode = "selection"
        return mode

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        target_lbl = f"Target: {self._target_plug}"
        if self._target_is_multi:
            target_lbl += "  [multi — select multiple sources to fill indices]"
        outer.addWidget(QLabel(target_lbl, self))

        self._filter_edit = QLineEdit(self)
        self._filter_edit.setPlaceholderText(
            "Filter \u2026 (exact attr name, or fnmatch glob like 'translate*')"
        )
        self._filter_edit.setToolTip(
            "Filter mode:\n"
            "  \u2022 Empty                 \u2192 show all\n"
            "  \u2022 No wildcard          \u2192 EXACT match against the attr "
            "name (e.g. ``translate`` matches ``pCube1.translate`` but NOT "
            "``pCube1.translateX``)\n"
            "  \u2022 Glob (*? [)        \u2192 fnmatch against the full "
            "node.attr (e.g. ``translate*`` matches translate, translateX, "
            "translateY, translateZ)"
        )
        self._filter_edit.textChanged.connect(self._apply_filter)
        outer.addWidget(self._filter_edit)

        self._tree = QTreeWidget(self)
        self._tree.setHeaderLabels(list(self.HEADER_LABELS))
        self._tree.setColumnCount(2)
        # ExtendedSelection so the user can pick multiple sources to fill
        # multi indices.
        self._tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        # A header click cycles that column's sort mode. ``setSortingEnabled
        # (False)`` leaves header sections NON-clickable in Qt, so
        # ``setSectionsClickable(True)`` is required or sectionClicked never fires.
        self._tree.setSortingEnabled(False)  # custom sort, not Qt's built-in
        try:
            header = self._tree.header()
            header.setSectionsClickable(True)
            # Cosmetic: the "current sort column" indicator gets better
            # contrast with this on.
            header.setHighlightSections(True)
            header.sectionClicked.connect(self._on_header_clicked)
        except Exception:
            pass
        outer.addWidget(self._tree, stretch=1)

        # Replaces the earlier "Show all" toggle; default comes from prefs.
        self._hide_pivots_check = QCheckBox("Hide pivots & limits", self)
        try:
            from mpynode.ui.preferences import get_pref

            self._hide_pivots_check.setChecked(
                bool(get_pref("connect_dialog_hide_pivots_default", True))
            )
        except Exception:
            self._hide_pivots_check.setChecked(True)
        self._hide_pivots_check.toggled.connect(lambda _on: self._populate_tree())
        outer.addWidget(self._hide_pivots_check)

        # When checked (default, via pref), the candidate tree shows only plugs
        # whose Maya type can DG-connect to the target attr.
        self._compat_check = QCheckBox("Filter by compatible type", self)
        self._compat_check.setToolTip(
            "Only show plugs whose type can be connected to the target. "
            "E.g. a vector input only shows compound 3-tuples (translate, "
            "rotate, scale); a float input only shows scalars (visibility, "
            "translateX,...). Uncheck to see every settable plug."
        )
        try:
            from mpynode.ui.preferences import get_pref

            self._compat_check.setChecked(
                bool(get_pref("connect_dialog_filter_by_type_default", True))
            )
        except Exception:
            self._compat_check.setChecked(True)
        self._compat_check.toggled.connect(lambda _on: self._populate_tree())
        outer.addWidget(self._compat_check)

        # Subclass injects extra checkbox(es) here via _build_extra_widgets.
        self._build_extra_widgets(outer)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._connect_btn = QPushButton("Connect", self)
        self._cancel_btn  = QPushButton("Cancel", self)
        btn_row.addWidget(self._connect_btn)
        btn_row.addWidget(self._cancel_btn)
        outer.addLayout(btn_row)

        self._connect_btn.clicked.connect(self._on_connect_clicked)
        self._cancel_btn.clicked.connect(self.reject)

        self._update_header_indicator()

    def _build_extra_widgets(self, outer_layout) -> None:
        """Subclasses override to add Append / Replace checkboxes."""
        pass

    # ------------------------------------------------------------------
    # Tree population + filter
    # ------------------------------------------------------------------

    def _populate_tree(self) -> None:
        self._tree.clear()
        hide_pivots = (
            self._hide_pivots_check.isChecked()
            if hasattr(self, "_hide_pivots_check")
            else True
        )
        rows = _list_candidate_plugs(hide_pivots=hide_pivots)
        # The target type is resolved once per populate; the per-row check is
        # a cheap set intersection.
        filter_by_type = (
            self._compat_check.isChecked() if hasattr(self, "_compat_check") else False
        )
        if filter_by_type:
            target_type = _resolve_target_attr_type(self._target_plug)
            if target_type:
                rows = [r for r in rows if _type_compatible(target_type, r[2])]
        if not rows:
            placeholder = QTreeWidgetItem(self._tree)
            placeholder.setText(0, "(select source nodes in Maya scene first)")
            placeholder.setFlags(Qt.ItemIsEnabled)
            return
        rows = _sort_rows(rows, self._sort_mode)
        for node, attr, a_type in rows:
            item    = QTreeWidgetItem(self._tree)
            display = f"{node}.{attr}"
            item.setText(0, display)
            item.setText(1, a_type)
            item.setData(0, Qt.UserRole, display)
            # The FULL node.attr string, so the filter can match either side.
            item.setData(0, Qt.UserRole + 1, display)
        # Pre-size col 0 to its widest entry so long ``node.attr`` names are
        # readable without a drag. It stays user-resizable afterward.
        try:
            self._tree.resizeColumnToContents(0)
        except Exception:
            pass
        # Re-apply the existing filter to the freshly populated rows.
        if hasattr(self, "_filter_edit"):
            self._apply_filter(self._filter_edit.text())

    def _apply_filter(self, text: str) -> None:
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            full = item.data(0, Qt.UserRole + 1) or item.text(0)
            item.setHidden(not _filter_matches(full, text))

    # ------------------------------------------------------------------
    # Header sort cycling
    # ------------------------------------------------------------------

    def _on_header_clicked(self, col: int) -> None:
        """3-way cycle: clicking a column header advances its sort mode.
        Clicking a different column resets to that column's first mode."""
        if col == 0:
            modes = _NODE_SORT_MODES
        elif col == 1:
            modes = _TYPE_SORT_MODES
        else:
            return

        if self._sort_col == col and self._sort_mode in modes:
            idx             = modes.index(self._sort_mode)
            self._sort_mode = modes[(idx + 1) % len(modes)]
        else:
            self._sort_col  = col
            self._sort_mode = modes[0]
        self._populate_tree()
        self._update_header_indicator()

    def _update_header_indicator(self) -> None:
        """Render the active sort mode's indicator into the header text."""
        node_label, type_label = self.HEADER_LABELS
        indicator = _MODE_INDICATORS.get(self._sort_mode, "")
        if self._sort_col == 0:
            node_label = f"{node_label} {indicator}".strip()
        elif self._sort_col == 1:
            type_label = f"{type_label} {indicator}".strip()
        try:
            self._tree.setHeaderLabels([node_label, type_label])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Accept
    # ------------------------------------------------------------------

    def _on_connect_clicked(self) -> None:
        items = self._tree.selectedItems()
        if not items:
            return
        plugs: list[str] = []
        for it in items:
            plug = it.data(0, Qt.UserRole)
            if plug:
                plugs.append(plug)
        if not plugs:
            return
        self._chosen = plugs
        self.accept()

    def getChosenPlugs(self) -> list[str]:
        """Return the list of plugs the user selected (one or more)."""
        return list(self._chosen)

    def getExtraFlag(self) -> bool:
        """Append (input) or Replace (output) flag, depending on subclass."""
        return self._extra_flag

    def getClobber(self) -> bool:
        """True when a MULTI mPy attr should be rebuilt from index 0 (clobber)
        rather than appended to. Always False for scalar attrs."""
        return bool(getattr(self, "_clobber", False))

    def getRangeText(self) -> str:
        """The array index range text for multi-plug auto-indexing -- the multi
        TARGET on the output dialog, the multi SOURCE on the input dialog. Empty
        string when the dialog has no range field."""
        w = getattr(self, "_range_edit", None)
        return w.text() if w is not None else ""

    # ------------------------------------------------------------------
    # Shared multi-plug (array-ancestor) index range field
    # ------------------------------------------------------------------
    # A plug (source OR destination) under an un-indexed multi ancestor -- e.g.
    # polyColorPerVertex.vertexColor[i].vertexColorRGB, driver.worldMatrix --
    # needs an [index] before it can connect. This field governs WHICH indices
    # are driven, and enables + pre-fills only when such a plug is selected.
    # Used by BOTH dialogs, so input and output auto-index symmetrically.

    def _build_range_field(self, outer_layout, label_text: str,
                           tooltip: str) -> None:
        range_row         = QHBoxLayout()
        self._range_label = QLabel(label_text, self)
        self._range_edit  = QLineEdit(self)
        self._range_edit.setPlaceholderText("e.g. 0:14  (blank = all existing)")
        self._range_edit.setToolTip(tooltip)
        self._range_label.setEnabled(False)
        self._range_edit.setEnabled(False)
        # Last value WE auto-filled -- so a selection change can refresh a stale
        # auto value without stomping a range the user typed by hand.
        self._range_autofill = ""
        range_row.addWidget(self._range_label)
        range_row.addWidget(self._range_edit)
        outer_layout.addLayout(range_row)
        try:
            self._tree.itemSelectionChanged.connect(
                self._on_range_selection_changed)
        except Exception:
            pass

    def _on_range_selection_changed(self) -> None:
        """Enable + pre-fill the range field when a selected leaf lives under a
        multi ancestor; pre-fill uses the largest existing element count among the
        selected multi plugs. Refreshes the auto value when the selection switches
        to a different multi plug, but never overwrites a hand-typed range."""
        if not hasattr(self, "_range_edit"):
            return
        max_count = 0
        any_multi = False
        for it in self._tree.selectedItems():
            plug = it.data(0, Qt.UserRole)
            if not plug:
                continue
            info = resolve_multi_target(plug)
            if info.get("is_multi_target") and not info.get("nested"):
                any_multi = True
                max_count = max(max_count, int(info.get("existing_count", 0)))
        self._range_label.setEnabled(any_multi)
        self._range_edit.setEnabled(any_multi)
        cur = self._range_edit.text().strip()
        # The field is "ours to manage" when empty or still holding the value we
        # last auto-filled; a hand-edited value is left untouched.
        user_edited = bool(cur) and cur != getattr(self, "_range_autofill", "")
        if user_edited:
            return
        new_val              = ("0:%d" % max_count) if (any_multi and max_count) else ""
        self._range_autofill = new_val
        self._range_edit.setText(new_val)


class NDConnectInputAttrDialog(_BaseConnectDialog):
    """Connect source plug(s) -> our input. For multi inputs, each source
    fills the next available index."""

    def __init__(self, parent, target_plug: str, target_is_multi: bool = False):
        super().__init__(
            parent,
            target_plug,
            target_is_multi,
            title="Connect Source(s) \u2192 Input",
        )

    def _build_extra_widgets(self, outer_layout) -> None:
        if self._target_is_multi:
            # Multi input: the knob that matters is the index-start policy, not
            # connectAttr's scalar force. Checked (default) = clobber (trim the
            # array + wire sources from index 0); unchecked = append at the
            # next-available index.
            self._clobber_check = QCheckBox(
                "Overwrite from index 0 (off = append to end)", self
            )
            self._clobber_check.setChecked(True)
            self._clobber_check.setToolTip(
                "Checked: remove existing elements and wire the selected "
                "sources from index 0 (array is resized to your selection).\n"
                "Unchecked: keep existing connections and append the new "
                "sources at the next available indices."
            )
            outer_layout.addWidget(self._clobber_check)
        else:
            # Scalar input: connectAttr force overwrites the existing source.
            self._force_check = QCheckBox(
                "Force (overwrite existing connection on scalar target)", self
            )
            self._force_check.setChecked(True)
            outer_layout.addWidget(self._force_check)

        # Which source indices are wired when a chosen SOURCE attr lives under a
        # multi ancestor and the connection auto-inserts an index. Mirrors the
        # output dialog's target-array range.
        self._build_range_field(
            outer_layout,
            "Source array indices:",
            "Which indices of the array SOURCE attribute to wire.\n"
            "  • blank / 'all' → every element that already exists\n"
            "  • '0:14'          → indices 0..13 (end-exclusive)\n"
            "  • '0,2,5'         → those indices\n"
            "Each selected source element wires to the next input index (multi "
            "input) or the scalar input takes the first.",
        )

    def _on_connect_clicked(self) -> None:
        if self._target_is_multi:
            self._clobber = self._clobber_check.isChecked()
            # Each element is a scalar destination; clobber trims first, append
            # writes to empty slots -- either way force the per-element wire.
            self._extra_flag = True
        else:
            self._clobber    = False
            self._extra_flag = self._force_check.isChecked()
        super()._on_connect_clicked()


class NDConnectOutputAttrDialog(_BaseConnectDialog):
    """Connect our output -> destination plug(s).

    For multi outputs, each chosen destination plug receives a connection
    from the next available index of the output.
    """

    def __init__(self, parent, target_plug: str, target_is_multi: bool = False):
        super().__init__(
            parent,
            target_plug,
            target_is_multi,
            title="Connect Output \u2192 Destination(s)",
        )

    def _build_extra_widgets(self, outer_layout) -> None:
        if self._target_is_multi:
            # Multi output: index-start policy (see the input dialog note).
            self._clobber_check = QCheckBox(
                "Overwrite from index 0 (off = append to end)", self
            )
            self._clobber_check.setChecked(True)
            self._clobber_check.setToolTip(
                "Checked: remove existing elements and wire the selected "
                "destinations from index 0 (array is resized to your "
                "selection).\nUnchecked: keep existing connections and append "
                "at the next available indices."
            )
            outer_layout.addWidget(self._clobber_check)
        else:
            self._replace_check = QCheckBox(
                "Replace existing connection on destination", self
            )
            self._replace_check.setChecked(True)
            outer_layout.addWidget(self._replace_check)

        # Which indices get driven when a destination attr lives under a multi
        # ancestor and the connection auto-inserts an index. Enables + pre-fills
        # with the target's element count only when such a target is selected.
        # The builder is shared with the input dialog on _BaseConnectDialog.
        self._build_range_field(
            outer_layout,
            "Target array indices:",
            "Which indices of the array TARGET attribute to drive.\n"
            "  • blank / 'all' → every element that already exists\n"
            "  • '0:14'          → indices 0..13 (end-exclusive)\n"
            "  • '0,2,5'         → those indices\n"
            "A single output fans across the range; an array output maps "
            "element-wise onto it.",
        )

    def _on_connect_clicked(self) -> None:
        if self._target_is_multi:
            self._clobber    = self._clobber_check.isChecked()
            self._extra_flag = True  # clobber/append both force the dest wire
        else:
            self._clobber    = False
            self._extra_flag = self._replace_check.isChecked()
        super()._on_connect_clicked()
