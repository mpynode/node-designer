"""Autocomplete -- vocabulary builder for the Init / Expression editors.

the Init tab and Expression tab autocomplete pull from
the live plug tree (via ``walk_plug_tree``), promoted-type method
suggestions per attribute, the user's stored vars list, the
per-wrapper ``INTERNAL_API_SLOTS``, and a small set of
Python builtins / common Maya modules.

The module exports two pieces:

*:func:`build_vocabulary(node_name, scope)` -- pure Python helper
 returning a sorted ``list[Completion]``. Testable headless;
 Qt-free.
*:func:`make_completer(parent, words)` -- thin Qt factory that
 creates a ``QCompleter`` backed by a ``QStringListModel``. Lazy
 Qt import so the rest of the module stays Qt-free.

Three scopes:

* ``"expression"`` -- the Compute (Expression) tab. Full ``self.X``
 surface (every plug walked + promoted-type methods) plus init
 bindings plus stored vars plus the Python builtins set.
* ``"viewport"`` -- the Viewport tab. Same completions as the
 Expression scope (live plug tree + promoted-type methods + init
 bindings + stored vars + Python builtins). Used by mPyFile.
* ``"init"`` -- the Init tab. NO plug-tree completions (InitProxy
 doesn't resolve plugs; reads happen in Expression). Just the
 helpers (``init_helpers`` module functions, ``self.X =...``
 scaffolding) plus Python builtins.

Each completion is a ``Completion`` namedtuple::

 text: str -- the literal text inserted
 kind: str -- "plug" | "method" | "internal" | "binding"
 | "storage" | "builtin"
 tooltip: str -- short doc shown next to the completion

The Qt editor pulls just the ``text`` list off these for the
QCompleter; the ``kind`` + ``tooltip`` fields are reserved for a future tooltip-popup feature.
"""

from __future__ import annotations

from typing import List, NamedTuple


class Completion(NamedTuple):
    text:    str
    kind:    str
    tooltip: str


# ===========================================================================
# Promoted-type method tables
# ===========================================================================


# Shown when the user types ``self.<plug>.``, per attribute Fn type. The
# promotions are locked:
#
#   * kMatrix                -> MatrixView
#   * kNumericAttribute k3   -> CompoundPlugProxy
#   * kTypedAttribute kMesh / kNurbsCurve / kNurbsSurface / kLattice
#                            -> MFn*Handle (writable + numpy bridge)
#
# Every other type falls through to plain Python attribute access.
_TYPE_METHODS = {
    "kMatrixAttribute": [
        ("asMatrix()", "method", "MMatrix (raw 4x4)"),
        ("asNumpy()", "method", "(4, 4) float64 numpy"),
        ("translation()", "method", "MVector translation component"),
        ("rotation()", "method", "MEulerRotation rotation component"),
        ("scale()", "method", "MVector scale component"),
    ],
    "kAttribute3Double": [
        ("asNumpy()", "method", "(3,) float64 numpy"),
    ],
    "kAttribute3Float": [
        ("asNumpy()", "method", "(3,) float64 numpy"),
    ],
    "kAttribute2Double": [
        ("asNumpy()", "method", "(2,) float64 numpy"),
    ],
    "kAttribute2Float": [
        ("asNumpy()", "method", "(2,) float64 numpy"),
    ],
}


# Methods on the writable output handles of the deformer family:
# ``self.outputGeometry[i]`` hands back an ``MFnMeshHandle`` or similar.
_HANDLE_METHODS = {
    "kMesh": [
        ("getPoints()", "method", "(N, 3) float64 numpy"),
        ("setPoints(arr)", "method", "Write (N, 3) numpy back to the mesh"),
        ("numVertices", "method", "Vertex count"),
    ],
    "kNurbsCurve": [
        ("getCVs()", "method", "(N, 3) float64 numpy"),
        ("setCVs(arr)", "method", "Write (N, 3) numpy back to the curve"),
    ],
    "kNurbsSurface": [
        ("getCVs()", "method", "(M, N, 3) float64 numpy"),
        ("setCVs(arr)", "method", "Write (M, N, 3) numpy back to the surface"),
    ],
    "kLattice": [
        ("getPoints()", "method", "(M, N, P, 3) float64 numpy"),
        ("setPoints(arr)", "method", "Write back to the lattice"),
    ],
}


# Builtins + Maya modules user expressions reach for. Short, to avoid noise.
_PYTHON_BUILTINS = [
    ("np", "builtin", "numpy alias (import numpy as np)"),
    ("numpy", "builtin", "numpy module"),
    ("mc", "builtin", "maya.cmds alias"),
    ("om", "builtin", "maya.OpenMaya (API 1.0)"),
    ("om2", "builtin", "maya.api.OpenMaya (API 2.0)"),
    ("self", "builtin", "the SelfProxy for the executing node"),
    ("True", "builtin", ""),
    ("False", "builtin", ""),
    ("None", "builtin", ""),
    ("len", "builtin", ""),
    ("range", "builtin", ""),
    ("enumerate", "builtin", ""),
    ("zip", "builtin", ""),
    ("print", "builtin", ""),
    ("isinstance", "builtin", ""),
    ("float", "builtin", ""),
    ("int", "builtin", ""),
    ("str", "builtin", ""),
    ("list", "builtin", ""),
    ("dict", "builtin", ""),
    ("tuple", "builtin", ""),
    ("set", "builtin", ""),
]


# Surfaced in BOTH scopes: common enough to suggest in Expression too.
_INIT_HELPERS = [
    ("mtm_to_numpy", "method", "MTransformationMatrix -> (4, 4) float64 numpy"),
    ("mtm_translation_numpy", "method", "MTransformationMatrix -> (3,) translation"),
    ("mtm_rotation_numpy", "method", "MTransformationMatrix -> (3,) Euler rotation"),
    ("mtm_scale_numpy", "method", "MTransformationMatrix -> (3,) scale"),
    ("mfnmesh_to_numpy_points", "method", "MFnMesh -> (N, 3) float64 numpy"),
    ("mfncurve_to_numpy_cvs", "method", "MFnNurbsCurve -> (N, 3) float64 numpy"),
    ("mfnsurface_to_numpy_cvs", "method", "MFnNurbsSurface -> (M, N, 3) float64 numpy"),
    ("mfnlattice_to_numpy_points", "method", "MFnLattice -> (M, N, P, 3) float64 numpy"),
    ("joint_chain_walk", "method", "Walk a joint chain start -> end"),
]


# ===========================================================================
# Vocabulary builder
# ===========================================================================


def build_vocabulary(node_name=None, scope="expression"):
    """Build the autocomplete vocabulary for the editor
    bound to ``node_name`` in ``scope`` ("init", "expression", or "viewport").

    Returns a sorted list of ``Completion`` records (sorted by
    ``text`` for predictable ordering -- the QCompleter sorts again
    by prefix-match at display time).

    The function tolerates ``node_name=None`` (returns a stub
    vocabulary with Python builtins + init helpers only) so the
    editor can ask for completions before its node binding is
    established.
    """
    out = []
    out.extend(Completion(t, k, d) for (t, k, d) in _PYTHON_BUILTINS)
    out.extend(Completion(t, k, d) for (t, k, d) in _INIT_HELPERS)

    if node_name and scope in ("expression", "viewport"):
        out.extend(_plug_completions(node_name))
        out.extend(_internal_api_completions(node_name))
        out.extend(_stored_var_completions(node_name))
        out.extend(_init_binding_completions(node_name))

    # Sort + dedupe by text, keeping the first-seen kind/tooltip.
    seen = {}
    for c in out:
        if c.text not in seen:
            seen[c.text] = c
    return sorted(seen.values(), key=lambda c: c.text)


# ---------------------------------------------------------------------------
# Vocabulary contributors
# ---------------------------------------------------------------------------


def _plug_completions(node_name):
    """Pull plug paths from ``walk_plug_tree``. Each top-level plug
    becomes ``self.<short_name>``; each compound child becomes
    ``self.<parent>.<child>``; each array becomes ``self.<name>[0]``.
    Promoted-type methods get appended per row.

    Returns a list of Completion records. Empty on any walker
    failure -- the editor degrades gracefully to the Python +
    init-helper vocabulary only.
    """
    try:
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree
    except Exception:
        return []
    try:
        rows = walk_plug_tree(node_name)
    except Exception:
        return []
    if not rows:
        return []

    out = []
    for r in rows:
        # The literal text typed after ``self.``. For nested rows (e.g.
        # ``amplitude.amplitudeX``) the FULL path is what the SelfProxy /
        # PlugProxy resolver expects.
        path    = r.plug_path
        kind    = "plug" + ("-user" if r.is_user_added else "")
        suffix  = "[0]" if r.is_array else ""
        text    = "self.{}{}".format(path, suffix)
        tooltip = "{} ({})".format(path, r.attr_type or "plug")
        out.append(Completion(text, kind, tooltip))

        # Promoted-type methods.
        for (method_text, method_kind, method_doc) in _TYPE_METHODS.get(
            r.attr_type, []
        ):
            full = "self.{}.{}".format(path, method_text)
            out.append(Completion(full, method_kind, method_doc))

    # Handle methods for the deformer family's writable outputs, surfaced as
    # ``self.outputGeometry[0].setPoints(...)``.
    for r in rows:
        if r.direction!= "OUTPUT" or not r.is_array:
            continue
        # RowSpec carries no typed-data family, so guess from the short
        # name: outputGeometry -> kMesh. The generator wrappers expose
        # outCurve / outSurface / outLattice.
        family = _guess_family_from_name(r.short_name)
        if family is None:
            continue
        for (method_text, method_kind, method_doc) in _HANDLE_METHODS.get(family, []):
            full = "self.{}[0].{}".format(r.short_name, method_text)
            out.append(Completion(full, method_kind, method_doc))
    return out


def _guess_family_from_name(name):
    name_l = (name or "").lower()
    if "mesh" in name_l or name == "outputGeometry":
        return "kMesh"
    if "curve" in name_l:
        return "kNurbsCurve"
    if "surface" in name_l:
        return "kNurbsSurface"
    if "lattice" in name_l:
        return "kLattice"
    return None


def _internal_api_completions(node_name):
    """Per-wrapper INTERNAL_API_SLOTS surface as
    ``self.<slot>`` completions. e.g. mPyField exposes
    ``self.positions``, ``self.velocities`` etc."""
    try:
        from mpynode.ui.widgets.plug_tree_walker import (
            _internal_api_slots_for,
        )
        slots = _internal_api_slots_for(node_name)
    except Exception:
        return []
    return [
        Completion("self.{}".format(s), "internal",
                   "non-plug API slot (INTERNAL_API_SLOTS)")
        for s in sorted(slots)
    ]


def _stored_var_completions(node_name):
    """User storage var names. Read from the node's ``_storedVarNames``
    plug (lightweight CSV) so we don't have to deserialize the full
    ``_storedVarsData`` blob just to populate autocomplete."""
    try:
        import maya.cmds as mc

        if not mc.attributeQuery("_storedVarNames", node=node_name, exists=True):
            return []
        blob = mc.getAttr(node_name + "._storedVarNames") or ""
    except Exception:
        return []
    names = [n.strip() for n in blob.split(",") if n.strip()]
    return [
        Completion("self.{}".format(n), "storage",
                   "user-stored variable (persistent)")
        for n in names
    ]


def _init_binding_completions(node_name):
    """Names defined in the Init tab's exec namespace. We can't
    re-exec the Init source from the autocomplete path (would slow
    every refresh), but we CAN extract top-level assignments via a
    cheap AST walk -- this catches the common case where the Init
    tab defines helper functions or constants."""
    try:
        import maya.cmds as mc

        if not mc.attributeQuery("_initSource", node=node_name, exists=True):
            return []
        src = mc.getAttr(node_name + "._initSource") or ""
    except Exception:
        return []
    if not src.strip():
        return []
    return _extract_top_level_names(src)


def _extract_top_level_names(source_text):
    """Cheap AST walk over the Init source. Returns Completion
    records for every top-level function def / class def / assignment
    target. Silently returns [] on syntax error."""
    import ast

    try:
        tree = ast.parse(source_text)
    except Exception:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(Completion(node.name, "binding",
                                   "init-tab function"))
        elif isinstance(node, ast.ClassDef):
            out.append(Completion(node.name, "binding",
                                   "init-tab class"))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.append(Completion(target.id, "binding",
                                           "init-tab variable"))
    return out


# ===========================================================================
# Qt completer factory (lazy Qt import)
# ===========================================================================


def make_completer(parent, words):
    """Build a ``QCompleter`` backed by a ``QStringListModel``
    over ``words`` (list[str]). Returns ``None`` if Qt is unavailable
    (allows headless mayapy callers to skip silently).

    The returned completer has::

        * caseSensitivity   = CaseInsensitive
        * filterMode        = MatchContains   (matches anywhere in word)
        * completionMode    = PopupCompletion (drop-down popup)
        * widget            = parent (so popup positions correctly)
    """
    try:
        from PySide6.QtCore import Qt as _Qt, QStringListModel
        from PySide6.QtWidgets import QCompleter
    except Exception:
        try:
            from PySide2.QtCore import Qt as _Qt, QStringListModel
            from PySide2.QtWidgets import QCompleter
        except Exception:
            return None
    completer = QCompleter(parent)
    model     = QStringListModel(list(words), completer)
    completer.setModel(model)
    completer.setCaseSensitivity(_Qt.CaseInsensitive)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    try:
        # Qt 5.2+ only.
        completer.setFilterMode(_Qt.MatchContains)
    except Exception:
        pass
    if parent is not None:
        completer.setWidget(parent)
    return completer


def update_completer_words(completer, words):
    """Replace the wordlist of an existing QCompleter without recreating
    it. ``words`` should be a list[str]. Silent no-op on bad
    completer."""
    if completer is None:
        return
    try:
        from PySide6.QtCore import QStringListModel
    except Exception:
        try:
            from PySide2.QtCore import QStringListModel
        except Exception:
            return
    try:
        model = QStringListModel(list(words), completer)
        completer.setModel(model)
    except Exception:
        pass
