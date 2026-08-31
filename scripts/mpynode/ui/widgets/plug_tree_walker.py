"""Plug_tree_walker -- Qt-free helper that walks a wrapped Maya
node's full plug surface for the Node Designer UI.

unifies the UI's INPUT / OUTPUT / Internals panes around a
SINGLE source of truth: the live plug tree (the same tree
``self.X`` resolves against inside user expressions). The artist
sees exactly the surface they can address, with the same direction
bucketing Maya's Node Editor uses.

API
---

``walk_plug_tree(node_name) -> list[RowSpec]``
 Walk every attribute on the node, classify direction, expand
 compounds + arrays, filter out hidden/bookkeeping plugs.

``RowSpec`` is a NamedTuple with::

 direction: "INPUT" | "OUTPUT" | "INTERNAL"
 plug_path: str (e.g. "amplitude" or "amplitude.amplitudeX"
 or "input[0].inputGeometry")
 short_name: str (e.g. "amplitudeX")
 parent_path: str ("" if top-level)
 depth: int (0 for top-level, 1 for children,...)
 is_array: bool
 is_compound: bool (has children)
 is_user_added: bool (came in via add_input_attr/add_output_attr)
 is_internal_api: bool (per-wrapper INTERNAL_API_SLOTS)
 attr_type: str (best-effort: "kMatrix" / "kFloat3" / etc.)
 value_text: str (display-only: short repr or "<connected>")

Bucketing rules
---------------

For each top-level plug:

* ``isWritable() and not isReadable()`` -> INPUT
* ``isReadable() and not isWritable()`` -> OUTPUT
* ``isWritable() and isReadable()`` -> INPUT (Maya's bidir
 attrs default to input
 role in the Node Editor)
* Match against the wrapper class's ``INTERNAL_API_SLOTS`` -> INTERNAL

Filters (omitted entirely):

* ``MFnAttribute.isHidden() == True`` -> omitted (Maya bookkeeping)
* leading underscore (``_initSource``, ``_storedVarsData``, etc.)
* Maya internal bookkeeping names (``caching``, ``frozen``,
 ``isHistoricallyInteresting``, ``nodeState``, ``binMembership``)

The walker is Qt-free so it can be unit-tested under mayapy without
importing Qt -- the widget code is a thin view over its output.
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional

import maya.cmds as mc
import maya.OpenMaya as om


# Names hidden from the UI even if they pass the ``isHidden`` check. Kept
# narrow on purpose: the variables-widget test contract pins ``message``,
# ``nodeState``, ``binMembership``, ``isHistoricallyInteresting``, ``caching``
# and ``frozen`` as USER-VISIBLE -- standard Maya attrs the artist may want to
# wire. So this holds only non-user-facing Maya container/template plugs;
# mpynode's own leading-underscore bookkeeping is caught separately.
_HARD_BLACKLIST = frozenset((
    "publishedNodeInfo",
    "publishedNode",
    "hyperLayout",
    "hyperPosition",
    "isCollapsed",
    "blackBox",
    "borderConnections",
    "renderInfo",
    "viewName",
    "iconName",
    "viewMode",
    "uiTreatment",
    "customTreatment",
    "creator",
    "creationDate",
    "containerType",
    "rmbCommand",
    "templateName",
    "templatePath",
    "templateVersion",
))


# Managed shader-string outputs (osl, ...) are writable+readable, so they
# would default to INPUT, but are conceptually OUTPUTS. osl_registry is the
# single source of truth; frozenset for the direction classifier's lookup.
try:
    from mpynode._common.osl.osl_registry import MANAGED_SHADER_OUTPUTS as _MSO
    _MANAGED_SHADER_OUTPUTS = frozenset(_MSO)
except Exception:  # pragma: no cover - osl_registry always importable
    _MANAGED_SHADER_OUTPUTS = frozenset(("osl",))


class RowSpec(NamedTuple):
    direction: str          # "INPUT" / "OUTPUT" / "INTERNAL"
    plug_path: str          # e.g. "input[0].inputGeometry"
    short_name: str         # e.g. "inputGeometry"
    parent_path: str        # e.g. "input[0]" or ""
    depth: int              # 0 / 1 / 2...
    is_array: bool
    is_compound: bool
    is_user_added: bool
    is_internal_api: bool
    attr_type: str          # best-effort, "" if unknown
    value_text: str         # display-only


# ===========================================================================
# Internal helpers
# ===========================================================================


def _attr_short_name(attr_mobj) -> str:
    try:
        return om.MFnAttribute(attr_mobj).name() or ""
    except Exception:
        return ""


def _attr_is_hidden(attr_mobj) -> bool:
    try:
        return bool(om.MFnAttribute(attr_mobj).isHidden())
    except Exception:
        return False


def _attr_is_writable(attr_mobj) -> bool:
    try:
        return bool(om.MFnAttribute(attr_mobj).isWritable())
    except Exception:
        return False


def _attr_is_readable(attr_mobj) -> bool:
    try:
        return bool(om.MFnAttribute(attr_mobj).isReadable())
    except Exception:
        return False


def _attr_type_label(attr_mobj) -> str:
    """Best-effort short label for the attribute Fn type."""
    try:
        api = attr_mobj.apiTypeStr() if hasattr(attr_mobj, "apiTypeStr") else ""
    except Exception:
        api = ""
    return api or ""


def _classify_direction(attr_mobj, name, internal_api_slots):
    if name in internal_api_slots:
        return "INTERNAL"
    # Writable (so the tab/AI can author them) AND readable (connection
    # source), which would fall through to INPUT below. Force OUTPUT so they
    # land in the Attributes-tab OUTPUT tree; being non-user-added they render
    # as read-only locked, undeletable rows.
    if name in _MANAGED_SHADER_OUTPUTS:
        return "OUTPUT"
    writable = _attr_is_writable(attr_mobj)
    readable = _attr_is_readable(attr_mobj)
    if writable and not readable:
        return "INPUT"
    if readable and not writable:
        return "OUTPUT"
    if writable and readable:
        # Bidirectional -- the Maya default for kNumericAttribute,
        # kUnitAttribute, kEnumAttribute, kMatrixAttribute. The Node Editor
        # displays these as INPUT.
        return "INPUT"
    return "INPUT"


def _should_filter(name) -> bool:
    if not name:
        return True
    if name.startswith("_"):
        return True
    if name in _HARD_BLACKLIST:
        return True
    return False


def _decode_user_added(node_name) -> set:
    """Cross-reference _inputAttrs + _outputAttrs JSON maps so the
    walker can flag is_user_added correctly. Returns a set of short
    plug names that the artist added via add_input_attr/add_output_attr."""
    out = set()
    for attr_storage in ("_inputAttrs", "_outputAttrs"):
        try:
            if not mc.attributeQuery(attr_storage, node=node_name, exists=True):
                continue
            blob = mc.getAttr(node_name + "." + attr_storage) or ""
            if not blob:
                continue
            from mpynode._common.io import serialization

            attr_map = serialization.decode_attr_map(blob)
            out.update(attr_map.keys())
        except Exception:
            continue
    return out


# Maya node type -> (module path, wrapper class name). The wrappers declare
# INTERNAL_API_SLOTS as a class attr. Module-level so the same map drives both
# the slot-set lookup AND the wrapper-instance constructor.
_TYPE_TO_WRAPPER = {
    "mPyDeformer": ("mpynode.wrappers.mpy_deformer", "MPyDeformer"),
    "mPySkinCluster": ("mpynode.wrappers.mpy_skin_cluster", "MPySkinCluster"),
    "mPyBlendShape": ("mpynode.wrappers.mpy_blend_shape", "MPyBlendShape"),
    "mPyTransform": ("mpynode.wrappers.mpy_transform", "MPyTransform"),
    "mPyMesh": ("mpynode.wrappers.mpy_mesh", "MPyMesh"),
    # NOT the _api2/ MPxNode classes: those take no __init__ args (so a
    # node-name string can't construct them) and carry no
    # INTERNAL_API_SLOTS / wrapper-mixin API.
    "mPyNurbsCurve":   ("mpynode.wrappers.mpy_nurbs_curve", "MPyNurbsCurve"),
    "mPyNurbsSurface": ("mpynode.wrappers.mpy_nurbs_surface", "MPyNurbsSurface"),
    "mPyNode": ("mpynode.wrappers._mpy_node", "MPyNode"),
    "mPyLocator": ("mpynode.wrappers.mpy_locator", "MPyLocator"),
    "mPyConstraint": ("mpynode.wrappers.mpy_constraint", "MPyConstraint"),
    "mPyIkSolver": ("mpynode.wrappers.mpy_iksolver", "MPyIkSolver"),
    # mPyFile is NOT plug-only: its Viewport tab injects non-plug bridge
    # handles (self.shader / time / texture_manager / ...) from
    # MPyFile.INTERNAL_API_SLOTS. Without this entry _wrapper_class_for
    # returns None and the Variables-Internal group silently stays empty,
    # breaking the "no black box" invariant test_variables_internal_panel
    # enforces.
    "mPyFile": ("mpynode.wrappers.mpy_file", "MPyFile"),
}


def _wrapper_class_for(node_name):
    """Resolve the user-facing wrapper class for ``node_name`` (e.g.
    ``MPyIkSolver`` for an ``mPyIkSolver`` node). Returns None on any
    lookup failure -- node doesn't exist, type isn't registered, or
    the wrapper module fails to import."""
    try:
        node_type = mc.nodeType(node_name)
    except Exception:
        return None
    entry = _TYPE_TO_WRAPPER.get(node_type)
    if entry is None:
        return None
    module_name, class_name = entry
    try:
        mod = __import__(module_name, fromlist=[class_name])
    except Exception:
        return None
    return getattr(mod, class_name, None)


def _wrapper_instance_for(node_name):
    """Construct a wrapper instance for ``node_name``. Every wrapper
    takes the Maya node name as its single positional ``__init__``
    arg, so this is uniform across the codebase.

    used by the Variables-Internal live-value renderer to
    read each ``INTERNAL_API_SLOTS`` slot via ``getattr(wrapper, slot)``.

    Returns None on any failure (missing class, constructor raised,
    etc.); callers fall back to displaying the slot name with a
    diagnostic value string.
    """
    cls = _wrapper_class_for(node_name)
    if cls is None:
        return None
    try:
        return cls(node_name)
    except Exception:
        return None


def _normalize_internal_api_slot_specs(raw):
    """Accept either the legacy flat string form
    ``("name1", "name2",...)`` OR the new extended-tuple form
    ``(("name", "read"|"write", "type hint"),...)``. Returns a list
    of 3-tuples ``(name, direction, type_hint)``; legacy entries get
    ``direction=""`` and ``type_hint=""``."""
    out = []
    for entry in raw or ():
        if isinstance(entry, str):
            out.append((entry, "", ""))
            continue
        try:
            name = entry[0]
            direction = entry[1] if len(entry) > 1 else ""
            type_hint = entry[2] if len(entry) > 2 else ""
            out.append((str(name), str(direction), str(type_hint)))
        except Exception:
            # Skip silently; callers still render the rest of the table.
            continue
    return out


def _internal_api_slot_specs_for(node_name):
    """Return the (name, direction, type_hint) triples for
    the wrapper's INTERNAL_API_SLOTS. Returns an empty list on any
    lookup failure. The Variables-Internal panel renders this
    extended schema; pass-1 callers (only the name matters) should
    use:func:`_internal_api_slots_for` instead."""
    cls = _wrapper_class_for(node_name)
    if cls is None:
        return []
    try:
        raw = getattr(cls, "INTERNAL_API_SLOTS", ())
    except Exception:
        return []
    return _normalize_internal_api_slot_specs(raw)


def _internal_api_method_specs_for(node_name):
    """Return the blessed MethodSpec tuple for the node's wrapper, or []."""
    cls = _wrapper_class_for(node_name)
    if cls is None:
        return []
    try:
        return list(getattr(cls, "INTERNAL_API_METHODS", ()) or [])
    except Exception:
        return []


def _own_public_names(cls):
    """Public names ``cls`` adds on top of the MPyNode base, sorted.

    The base's own surface (get_name / add_input_attr / the plug plumbing) is
    excluded: it is the same on every node and would bury the per-type API."""
    try:
        from mpynode.wrappers._mpy_node import MPyNode

        base = {n for n in dir(MPyNode) if not n.startswith("_")}
        return sorted(n for n in dir(cls)
                      if not n.startswith("_") and n not in base)
    except Exception:
        return []


def authoring_method_rows_for(node_name):
    """``(name, sig, doc)`` for the wrapper's AUTHORING methods.

    The scene-mutating Python API -- ``load_target``, ``add_target``,
    ``rebuild`` -- as opposed to ``INTERNAL_API_METHODS``, which is the curated,
    plug-validated COMPUTE-time surface that lowers to C++. An authoring method
    does file IO and mutates the node, so it can never join that tuple.

    CURATED, not derived. The membership list is the wrapper's ``AUTHORING_API``
    tuple; ``dir(cls)``-minus-the-base (what this used to return) could not tell
    a real authoring verb like ``add_target`` from internal table plumbing like
    ``rebuild_slots``, so it surfaced both. A wrapper with no ``AUTHORING_API``
    declares no authoring surface and gets [] -- a new method is invisible until
    it is listed, which is the point: the list is a promise to the user.

    Only MEMBERSHIP and the doc are curated. The SIGNATURE is still derived with
    ``inspect`` so it can never drift from the wrapper. The doc falls back to the
    method's own docstring when the tuple leaves it blank. Returns [] on any
    lookup failure."""
    import inspect

    cls = _wrapper_class_for(node_name)
    if cls is None:
        return []
    rows = []
    for name, doc in _authoring_api_entries(cls):
        # getattr_static: never triggers a descriptor, so a property that reads
        # an unconnected plug cannot raise out of a UI refresh.
        raw = inspect.getattr_static(cls, name, None)
        fn = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
        if not inspect.isfunction(fn):
            continue
        try:
            sig = str(inspect.signature(fn))
            sig = sig.replace("(self, ", "(", 1).replace("(self)", "()", 1)
            sig = sig.replace("(cls, ", "(", 1).replace("(cls)", "()", 1)
        except (TypeError, ValueError):
            sig = "(...)"
        rows.append((name, name + sig, doc or (inspect.getdoc(fn) or "").strip()))
    return rows


def _authoring_api_entries(cls):
    """``[(name, doc)]`` from a wrapper's ``AUTHORING_API``, or [].

    Accepts a bare name or a ``(name, doc)`` pair per entry so a wrapper with
    well-documented methods need not restate their docstrings."""
    try:
        raw = getattr(cls, "AUTHORING_API", ()) or ()
    except Exception:
        return []
    out = []
    for entry in raw:
        if isinstance(entry, str):
            out.append((entry, ""))
        elif isinstance(entry, (tuple, list)) and entry:
            out.append((str(entry[0]), str(entry[1]) if len(entry) > 1 else ""))
    return out


def wrapper_property_rows_for(node_name):
    """``(name, kind, doc)`` for the wrapper's Python ``@property`` surface.

    Read as ``self.X`` with no call. Distinct from ``INTERNAL_API_SLOTS``, which
    is the bridge-injected non-plug surface -- the two overlap on most wrappers
    but not all, and a property missing from the SLOTS tuple is otherwise
    invisible. Returns [] on any lookup failure."""
    import inspect

    cls = _wrapper_class_for(node_name)
    if cls is None:
        return []
    rows = []
    for name in _own_public_names(cls):
        raw = inspect.getattr_static(cls, name, None)
        if not isinstance(raw, property):
            continue
        doc = (inspect.getdoc(raw) or "").strip()
        rows.append((name, "property", doc))
    return rows


# --------------------------------------------------------------------------
# Which surface each SCRIPT TIER can actually reach.
#
# `self` is not one object in this product. The expression tiers get a
# SelfProxy; the API tab (setup / demo / @maya_command bodies, and the Methods
# module it absorbed) gets the real WRAPPER. The two surfaces are disjoint, and
# showing one while editing the other is pure noise -- MEASURED on mPyFile
# (_tests/test_framework_tier_scope.py re-measures all of this, so a future
# change to SelfProxy cannot silently make the panel lie):
#
#   wrapper     read_texture / time / fileName -> AttributeError
#   SelfProxy   has_osl_expression             -> AttributeError
#
# The expression tiers are NOT uniform either:
#
#   Init      `self` resolves PLUGS ONLY. No blessed methods, no slots
#             (self.read_texture and self.time both raise). Init builds the
#             helper namespace; the bridge has not bound the rest yet.
#   Compute   blessed methods + slots, EXCEPT the VP2-only handles.
#   Viewport  blessed methods + every slot (it is the tier those exist for).
#   OSL       not Python at all -- a shader-source string output. NO Python
#             surface applies, so the panel shows nothing rather than a list
#             of things that cannot be called from a shader.
_TIER_INIT = "Init"
_TIER_COMPUTE = "Compute"
_TIER_VIEWPORT = "Viewport"
_TIER_OSL = "OSL"
_TIER_API = "API"

_TIER_SCOPES = {
    _TIER_INIT: {
        "methods": False, "slots": False, "authoring": False, "draw": False,
        "note": "Init resolves PLUGS only -- see the Attributes tab. Blessed "
                "methods and Properties are bound for Compute / Viewport.",
    },
    _TIER_COMPUTE: {
        "methods": True, "slots": True, "authoring": False, "draw": True,
        "note": "",
    },
    _TIER_VIEWPORT: {
        "methods": True, "slots": True, "authoring": False, "draw": False,
        "note": "",
    },
    _TIER_OSL: {
        "methods": False, "slots": False, "authoring": False, "draw": False,
        "note": "OSL is a shader language, not Python -- no framework surface "
                "applies here.",
    },
    _TIER_API: {
        "methods": False, "slots": False, "authoring": True, "draw": False,
        "note": "",
    },
}

# Fallback for an unknown/absent tier: the Compute scope. A caller that cannot
# name the active tier gets the tier users spend most of their time in rather
# than an empty panel.
_DEFAULT_TIER = _TIER_COMPUTE


def script_tiers():
    """The script-tier names this module knows, in strip order."""
    return (_TIER_INIT, _TIER_COMPUTE, _TIER_VIEWPORT, _TIER_OSL, _TIER_API)


def framework_scope_for(tier):
    """Which Framework-tab groups the given script tier can reach.

    ``{methods, slots, authoring, draw: bool, note: str}``. ``note`` is a
    one-line explanation shown when the tier reaches nothing, so an empty panel
    reads as an answer rather than a failure."""
    return dict(_TIER_SCOPES.get(tier or "", _TIER_SCOPES[_DEFAULT_TIER]))


def viewport_only_slots(node_name) -> frozenset:
    """INTERNAL_API_SLOTS names only the VIEWPORT tier can reach.

    mPyFile's shader / mappings / texture_manager / state_manager are injected
    by the VP2 bridge; in Compute they raise AttributeError (measured). Declared
    per wrapper as ``VIEWPORT_ONLY_SLOTS`` -- the slot DOCS already said
    "(Viewport tab only)", but prose is not a gate."""
    cls = _wrapper_class_for(node_name)
    if cls is None:
        return frozenset()
    try:
        return frozenset(getattr(cls, "VIEWPORT_ONLY_SLOTS", ()) or ())
    except Exception:
        return frozenset()


def _exposed_input_plugs_for(node_name) -> frozenset:
    """Inherited plug names the wrapper PROMOTES to always-visible INPUT
    attributes (its ``EXPOSED_INPUT_PLUGS`` class attr). e.g. mPyTransform
    surfaces translate / rotate / scale / shear / rotateOrder (+ children) so the
    default framework filter does not hide them from the Inputs pane. Returns an
    empty frozenset on any lookup failure (the plain framework filter applies)."""
    cls = _wrapper_class_for(node_name)
    if cls is None:
        return frozenset()
    try:
        return frozenset(getattr(cls, "EXPOSED_INPUT_PLUGS", ()) or ())
    except Exception:
        return frozenset()


def _useful_inherited_plugs_for(node_name):
    """Resolve the wrapper's ``USEFUL_INHERITED_PLUGS`` allowlist for
    ``node_name`` (inherited plugs to SHOW when the framework filter is on).

    Returns a ``frozenset`` for a registered mpy type, or ``None`` when there
    is no wrapper class (unregistered / non-mpy node) OR the class explicitly
    sets ``USEFUL_INHERITED_PLUGS = None`` -- in which case the Attributes tab
    falls back to the legacy denylist."""
    cls = _wrapper_class_for(node_name)
    if cls is None:
        return None
    try:
        val = getattr(cls, "USEFUL_INHERITED_PLUGS", None)
    except Exception:
        return None
    if val is None:
        return None
    return frozenset(val)


def _internal_api_slots_for(node_name) -> frozenset:
    """Look up the wrapper class for this node type and return its
    INTERNAL_API_SLOTS class attribute (per L.1). Returns an empty
    frozenset on any lookup failure.

    robustness: accepts both the legacy flat-string declaration
    AND the extended (name, direction, type_hint) form -- this function
    just extracts the NAMES (callers that care about
    direction / type_hint should use:func:`_internal_api_slot_specs_for`).
    """
    specs = _internal_api_slot_specs_for(node_name)
    return frozenset(name for name, _dir, _hint in specs)


def _read_value_text(node_name, plug_path):
    """Display-only value formatter. Returns ``"<connected>"`` for
    input plugs driven by a connection, otherwise a truncated repr
    of cmds.getAttr (UI-context only -- this is NOT inside compute,
    so cmds.getAttr is fine here).

    pre-check the plug's data type to skip ``cmds.getAttr``
    on types that Maya can't stringify (mesh / nurbsCurve /
    nurbsSurface / lattice / Message / componentList / etc.).
    Calling ``getAttr`` on those plugs prints a noisy
    ``// Error: The data is not a numeric or string value, and
    cannot be displayed.`` warning to the script editor every
    refresh -- even though the call doesn't raise.
    """
    full = node_name + "." + plug_path
    try:
        connected = bool(mc.connectionInfo(full, isDestination=True))
    except Exception:
        connected = False
    if connected:
        try:
            src = mc.connectionInfo(full, sourceFromDestination=True)
            if src:
                return "<- {}".format(src)
        except Exception:
            pass
        return "<connected>"
    # Skip getAttr for data types Maya can't render.
    try:
        attr_type = mc.getAttr(full, type=True)
    except Exception:
        attr_type = None
    if attr_type in _NON_DISPLAYABLE_ATTR_TYPES:
        return ""
    try:
        val = mc.getAttr(full)
    except Exception:
        return "<unreadable>"
    if val is None:
        return ""
    text = repr(val)
    if len(text) > 80:
        text = text[:77] + "..."
    return text


# Types where ``cmds.getAttr`` prints a noisy "data is not a numeric or string
# value" error instead of returning anything. They are typed-data plugs
# (geometry, message, component lists) with no meaningful one-line preview.
_NON_DISPLAYABLE_ATTR_TYPES = frozenset(
    {
        "mesh",
        "nurbsCurve",
        "nurbsSurface",
        "lattice",
        "subdiv",
        "Message",
        "message",
        "componentList",
        "polyFaces",
        "polyEdges",
        "polyVertices",
        "attributeAlias",
        "dataPolyComponent",
        "dataReferenceEdits",
        "spectrumRGB",
        "geometry",
        "generic",
    }
)


def _walk_attribute(
    node_mob,
    attr_mob,
    node_name,
    user_added_names,
    internal_api_slots,
    parent_path,
    depth,
    rows,
):
    """Recursive walker. Resolves an attribute MObject into one or
    more RowSpec entries (a top-level row for the attr itself + child
    rows for compound members + element rows for array element[0]
    if populated)."""
    name = _attr_short_name(attr_mob)
    if _should_filter(name):
        return
    # Deliberately NOT filtered on MFnAttribute.isHidden(): the variables
    # widget contract pins ``message`` -- isHidden=True on every node -- as
    # user-visible. Only leading-underscore bookkeeping and _HARD_BLACKLIST go.

    if parent_path:
        plug_path = "{}.{}".format(parent_path, name)
    else:
        plug_path = name

    direction = _classify_direction(attr_mob, name, internal_api_slots)

    is_array = False
    try:
        is_array = bool(om.MFnAttribute(attr_mob).isArray())
    except Exception:
        is_array = False

    # kCompoundAttribute and kNumericAttribute k3 etc. both have iterable
    # child attrs.
    n_children = 0
    is_compound = False
    try:
        if attr_mob.hasFn(om.MFn.kCompoundAttribute):
            is_compound = True
            n_children = om.MFnCompoundAttribute(attr_mob).numChildren()
    except Exception:
        is_compound = False
        n_children = 0
    # k2/k3/k4 short tuples look numeric but have compound-like child
    # accessors, so display them as compound when they have components.
    try:
        if attr_mob.hasFn(om.MFn.kNumericAttribute):
            fn_num = om.MFnNumericAttribute(attr_mob)
            try:
                nc = fn_num.numChildren() if hasattr(fn_num, "numChildren") else 0
                if nc > 0:
                    is_compound = True
                    n_children = max(n_children, nc)
            except Exception:
                pass
    except Exception:
        pass

    rows.append(RowSpec(
        direction=direction,
        plug_path=plug_path,
        short_name=name,
        parent_path=parent_path,
        depth=depth,
        is_array=is_array,
        is_compound=is_compound,
        is_user_added=(name in user_added_names),
        is_internal_api=(name in internal_api_slots),
        attr_type=_attr_type_label(attr_mob),
        # NEVER read a multi PARENT: cmds.getAttr on one UNCONDITIONALLY
        # forces a recompute of an output multi (element reads respect the
        # clean cache, the parent read does not) and can't stringify it
        # anyway. Doing so re-ran the user expression on every panel refresh.
        # The per-element rows below carry the real values.
        value_text="" if is_array else _read_value_text(node_name, plug_path),
    ))

    # NOT for arrays: their children surface as element[i] rows instead.
    if is_compound and not is_array and n_children > 0:
        for i in range(n_children):
            try:
                child_attr = (
                    om.MFnCompoundAttribute(attr_mob).child(i)
                    if attr_mob.hasFn(om.MFn.kCompoundAttribute)
                    else om.MFnNumericAttribute(attr_mob).child(i)
                )
            except Exception:
                try:
                    child_attr = om.MFnAttribute(attr_mob).child(i)
                except Exception:
                    continue
            _walk_attribute(
                node_mob, child_attr, node_name,
                user_added_names, internal_api_slots,
                parent_path=plug_path,
                depth=depth + 1,
                rows=rows,
            )

    # Surface EVERY populated array element: an index counts as populated if
    # it has a value set or an upstream connection, matching what the Node
    # Editor and Channel Box show. Sparse arrays with no data emit nothing.
    if is_array:
        # Via the API, NOT ``cmds.getAttr(plug, multiIndices=True)``: the cmds
        # query UNCONDITIONALLY forces a recompute of an output multi, so
        # walking the tree on every panel refresh re-ran the user expression
        # -- a source of the "Save fires the expression 4-8x" report.
        # getExistingArrayAttributeIndices() reads the datablock instead.
        try:
            import maya.api.OpenMaya as _om2

            _sel2 = _om2.MSelectionList()
            _sel2.add(node_name + "." + plug_path)
            elem_indices = list(
                _sel2.getPlug(0).getExistingArrayAttributeIndices()
            )
        except Exception:
            try:
                elem_indices = (
                    mc.getAttr(node_name + "." + plug_path, multiIndices=True) or []
                )
            except Exception:
                elem_indices = []
        for raw_idx in elem_indices:
            try:
                idx = int(raw_idx)
            except Exception:
                continue
            elem_path = "{}[{}]".format(plug_path, idx)
            try:
                if is_compound and n_children > 0:
                    rows.append(RowSpec(
                        direction=direction,
                        plug_path=elem_path,
                        short_name="[{}]".format(idx),
                        parent_path=plug_path,
                        depth=depth + 1,
                        is_array=False,
                        is_compound=True,
                        is_user_added=(name in user_added_names),
                        is_internal_api=False,
                        attr_type=_attr_type_label(attr_mob),
                        value_text=_read_value_text(node_name, elem_path),
                    ))
                    for i in range(n_children):
                        try:
                            child_attr = (
                                om.MFnCompoundAttribute(attr_mob).child(i)
                                if attr_mob.hasFn(om.MFn.kCompoundAttribute)
                                else om.MFnNumericAttribute(attr_mob).child(i)
                            )
                        except Exception:
                            continue
                        _walk_attribute(
                            node_mob, child_attr, node_name,
                            user_added_names, internal_api_slots,
                            parent_path=elem_path,
                            depth=depth + 2,
                            rows=rows,
                        )
                else:
                    rows.append(RowSpec(
                        direction=direction,
                        plug_path=elem_path,
                        short_name="[{}]".format(idx),
                        parent_path=plug_path,
                        depth=depth + 1,
                        is_array=False,
                        is_compound=False,
                        is_user_added=(name in user_added_names),
                        is_internal_api=False,
                        attr_type=_attr_type_label(attr_mob),
                        value_text=_read_value_text(node_name, elem_path),
                    ))
            except Exception:
                pass


# ===========================================================================
# Public surface
# ===========================================================================


def walk_plug_tree(node_name) -> List[RowSpec]:
    """Walk every attribute on ``node_name`` and return a list of
    ``RowSpec`` entries ready for the Node Designer UI panes.

    Skip-with-empty-result on any error -- the UI tolerates an empty
    list and the caller can detect it.
    """
    if not node_name or not isinstance(node_name, str):
        return []
    try:
        sel = om.MSelectionList()
        sel.add(node_name)
        node_mob = om.MObject()
        sel.getDependNode(0, node_mob)
    except Exception:
        return []

    user_added = _decode_user_added(node_name)
    internal_api_slots = _internal_api_slots_for(node_name)

    try:
        fn = om.MFnDependencyNode(node_mob)
        n_attrs = fn.attributeCount()
    except Exception:
        return []

    rows: List[RowSpec] = []
    seen_top_level_names = set()
    for i in range(n_attrs):
        try:
            attr_mob = fn.attribute(i)
        except Exception:
            continue
        name = _attr_short_name(attr_mob)
        if not name:
            continue
        # Compound children are surfaced by the recursive walk; without
        # de-dupe both parent and children appear at the top level.
        try:
            attr_fn = om.MFnAttribute(attr_mob)
            parent_attr = attr_fn.parent()
            if not parent_attr.isNull():
                # Child of a compound; the parent walk will surface it.
                continue
        except Exception:
            pass
        if name in seen_top_level_names:
            continue
        seen_top_level_names.add(name)
        _walk_attribute(
            node_mob, attr_mob, node_name,
            user_added, internal_api_slots,
            parent_path="",
            depth=0,
            rows=rows,
        )
    return rows


def filter_by_direction(rows, direction):
    """Convenience: filter a RowSpec list by direction
    (``"INPUT"`` / ``"OUTPUT"`` / ``"INTERNAL"``)."""
    return [r for r in rows if r.direction == direction]


class TreeNode(object):
    """Light-weight nesting wrapper for ``walk_plug_tree``
    output. Each node holds the source ``RowSpec`` plus a list of
    child ``TreeNode``\\s. Qt-free; consumers build QTreeWidgetItem
    trees from this shape one-to-one.

    Built by:func:`treeify`. See that function for usage.
    """

    __slots__ = ("row", "children")

    def __init__(self, row):
        self.row = row
        self.children = []

    def __repr__(self):
        return "<TreeNode {!r} children={}>".format(
            self.row.plug_path, len(self.children),
        )


def treeify(rows):
    """Convert a flat ``[RowSpec,...]`` from:func:`walk_plug_tree` (depth-first order with explicit
    ``parent_path`` fields) into a nested list of ``TreeNode``
    instances ready for QTreeWidgetItem construction.

    Algorithm: single linear pass. Maintain a dict ``{plug_path:
    TreeNode}`` so each row can be looked up in O(1). For each row,
    create a TreeNode; if ``parent_path`` is empty OR the parent
    isn't in the index (orphaned row), the TreeNode becomes a
    top-level entry in the returned list. Otherwise it's appended
    to the parent's ``.children``.

    Returns ``list[TreeNode]`` (top-level entries in walker order).
    """
    by_path = {}
    top_level = []
    for row in rows:
        node = TreeNode(row)
        by_path[row.plug_path] = node
        parent = by_path.get(row.parent_path) if row.parent_path else None
        if parent is None:
            top_level.append(node)
        else:
            parent.children.append(node)
    return top_level


# ===========================================================================
# plug-tree mini-browser helpers (Qt-free)
#
# Public helpers over ``walk_plug_tree``, formatted for different consumers.
# They used to live in ui/widgets/variables.py, which still re-exports these
# names for back-compat.
# ===========================================================================

#: Plugs that mpynode reserves internally; never surface in the
#: variables widget Internal section.
PLUG_BROWSER_BLACKLIST = frozenset(
    {
        # mpynode bookkeeping -- not user-facing.
        "_computeSource",
        "_initSource",
        "_inputAttrs",
        "_outputAttrs",
        "_storedVarNames",
        "_storedVarsList",
        "_storedVarsData",
        "_profileSnapshotData",
        "_watchVarsData",
        "_debugMode",
        "_timeIn",
        "_profileEnabled",
        "_profileSummary",
        "_watchEnabled",
        "_watchEvalCount",
        # Output Builder plumbing (per-node).
        "_outputBuilderSource",
        "_outputBuilderEnabled",
        # snake_case mpynode bookkeeping (current plug names).
        "debug_mode",
        "profile_enabled",
        "deep_profile_enabled",
        "watch_enabled",
        # Maya bookkeeping.
        "caching",
        "frozen",
        "isHistoricallyInteresting",
        "binMembership",
    }
)


def collect_plug_rows(node_name):
    """Return [(plug_name, direction, value_text),...] for
    a node's full plug surface (inherited + user-added, with compound
    children + array element[0] expanded).

    Used by the variables widget to populate the Internal section.
    Backed by ``ui.widgets.plug_tree_walker.walk_plug_tree`` so the
    artist sees EXACTLY the surface ``self.X`` resolves against
    inside their expression -- inherited base-class plugs included,
    direction-bucketed the same way Maya's Node Editor does.

    Module-level + Qt-free so tests can exercise it under mayapy
    without a Qt main window. Falls back to the legacy
    ``cmds.listAttr`` walk on any walker exception.
    """
    if walk_plug_tree is not None:
        try:
            rows_spec = walk_plug_tree(node_name)
        except Exception:
            rows_spec = None
        if rows_spec:
            out = []
            for r in rows_spec:
                if r.short_name in PLUG_BROWSER_BLACKLIST:
                    continue
                # INTERNAL surfaces under its own section, not in IN/OUT.
                if r.direction == "INPUT":
                    direction = "IN"
                elif r.direction == "OUTPUT":
                    direction = "OUT"
                else:
                    continue  # internals handled separately
                out.append((r.plug_path, direction, r.value_text))
            return out

    # Legacy cmds.listAttr fallback.
    try:
        import maya.cmds as mc
    except Exception:
        return []
    try:
        attrs = mc.listAttr(node_name) or []
    except Exception:
        return []

    rows = []
    seen = set()
    for attr in attrs:
        short = attr.split(".")[0]  # top-level only
        if short in seen:
            continue
        seen.add(short)
        if short in PLUG_BROWSER_BLACKLIST:
            continue
        if short.startswith("_"):
            continue
        full = "{}.{}".format(node_name, short)
        try:
            writable = bool(mc.getAttr(full, settable=True))
        except Exception:
            writable = False
        try:
            connected = bool(mc.connectionInfo(full, isDestination=True))
        except Exception:
            connected = False
        direction = "IN" if writable or connected else "OUT"
        value_text = read_plug_value_text(full, connected)
        rows.append((short, direction, value_text))

    rows.sort()
    return rows


def collect_plug_tree(node_name):
    """Tree-shape variant of:func:`collect_plug_rows`.

    Returns a list of ``TreeNode`` objects (from
    ``plug_tree_walker.treeify``) ready for QTreeWidget rendering.
    Each top-level node may have ``.children`` which are themselves
    TreeNodes -- compound + array element nesting is preserved.

    Empty list on any walker exception (degrades gracefully).
    """
    try:
        rows = walk_plug_tree(node_name)
    except Exception:
        return []
    if not rows:
        return []
    # Same blacklist the legacy flat collector applies.
    rows = [r for r in rows if r.short_name not in PLUG_BROWSER_BLACKLIST]
    # INTERNAL is surfaced separately by collect_internal_api_rows.
    rows = [r for r in rows if r.direction in ("INPUT", "OUTPUT")]
    return treeify(rows)


def read_plug_value_text(full_plug, connected):
    """Render a plug's current value as a short text label
    suitable for a tree row. Returns ``"<- src"`` when the plug is
    a destination, ``"<unreadable>"`` for opaque types, or a truncated
    repr of the value."""
    try:
        import maya.cmds as mc
    except Exception:
        return ""
    if connected:
        try:
            src = mc.connectionInfo(full_plug, sourceFromDestination=True) or ""
        except Exception:
            src = ""
        return "<- {}".format(src) if src else "<connected>"
    try:
        value = mc.getAttr(full_plug)
    except Exception:
        return "<unreadable>"
    text = repr(value)
    if len(text) > 120:
        text = text[:117] + "..."
    return text