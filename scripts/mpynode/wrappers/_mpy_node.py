"""User-facing wrapper for the mPyNode plug-in node.

Usage::

 from mpynode.wrappers._mpy_node import MPyNode

 n = MPyNode.create(name="multiplier")
 n.add_input_attr("a", "float")
 n.add_input_attr("b", "float")
 n.add_output_attr("c", "float")
 # self-only: read inputs via self.X, write outputs via self.X.
 n.set_compute_expression("self.c = self.a * self.b * 2")
 # identity: n.get_name() / n.set_name("newName")

 cmds.setAttr("multiplier.a", 3)
 cmds.setAttr("multiplier.b", 4)
 print(cmds.getAttr("multiplier.c")) # 24

The wrapper hides the JSON serialization of the input/output attr maps
and exposes a script-friendly API.
"""

from __future__ import annotations

import importlib
import keyword

import maya.cmds as mc
from mpynode._common.lifecycle.init_registry import InitSourceMixin
from mpynode._common.lifecycle.gap_spacing_registry import GapSpacingMixin
from mpynode._common.lifecycle.metadata_registry import MetadataMixin
from mpynode._common.methods.methods_registry import MethodsSourceMixin
from mpynode._common.io.serialization import decode_attr_map, encode_attr_map


# Hidden string plug holding a node's logical (Python-subclass) identity as an
# importable dotted path (e.g. ``"myrig.nodes.BlackWhiteFile"``), pickle-style.
# Absent / empty => the node is the plain root wrapper for its Maya type.
_PY_CLASS_PLUG = "class_path"


def _read_py_class(node_name: str):
    """Return the ``_pyClass`` dotted path stored on ``node_name`` (or ``None``).

    Reads the plug by name so callers (``__new__``, the scene tree) can inspect a
    node's logical identity without constructing a wrapper. Never raises."""
    try:
        if not mc.attributeQuery(_PY_CLASS_PLUG, node=node_name, exists=True):
            return None
        val = mc.getAttr("%s.%s" % (node_name, _PY_CLASS_PLUG))
    except Exception:  # noqa: BLE001
        return None
    return val or None


def _import_py_class(dotted_path: str):
    """Import ``module.ClassName`` and return the class object, or ``None``.

    v1 supports top-level classes only (a single split on the last ``.``); nested
    qualnames are out of scope. Never raises -- any failure (missing package,
    missing symbol, non-class) returns ``None`` so callers fall back to the root
    wrapper."""
    if not dotted_path or "." not in dotted_path:
        return None
    module_path, _, class_name = dotted_path.rpartition(".")
    try:
        module = importlib.import_module(module_path)
        obj = getattr(module, class_name, None)
    except Exception:  # noqa: BLE001
        return None
    return obj if isinstance(obj, type) else None


def _invalidate_plug_governance() -> None:
    """Tell the plug gate the managed-attr maps changed.

    The gate memoises "does this plug surface?" per node, and the answer is
    read out of ``_inputAttrs`` / ``_outputAttrs``. Every write to those two
    plugs funnels through ``_write_input_map`` / ``_write_output_map``, so
    calling this from there is sufficient to keep the memo honest. Imported
    lazily -- ``wrappers`` is imported during plug-in registration, before the
    ``_common`` package is necessarily importable."""
    try:
        from mpynode._common.plugs import plug_governance

        plug_governance.invalidate()
    except Exception:  # noqa: BLE001
        pass


def _reserved_name_reason(name: str, node_type: str | None):
    """Why ``name`` collides with a framework slot on ``node_type``, or None.

    Lazy + fail-open for the same reason as ``_invalidate_plug_governance``:
    this module is imported during plug-in registration, before ``_common`` is
    necessarily importable."""
    try:
        from mpynode._common.interface.reserved_names import check_reserved_name

        return check_reserved_name(name, node_type=node_type)
    except Exception:  # noqa: BLE001
        return None


def _in_attr_surgery() -> bool:
    """True while a destructive attr rebuild (reorder / .mpn restore) is open.

    Depth-only (``in_attr_surgery_block``), NOT ``in_attr_surgery``: the latter
    stays True for a couple of seconds after the outermost block closes so a
    deferred EM pull is still covered, which would leave this guard downgraded
    to a warning for every interactive add-attr in that window."""
    try:
        from mpynode._common.lifecycle import scene_state

        return bool(scene_state.in_attr_surgery_block())
    except Exception:  # noqa: BLE001
        return False


def _display_warning(msg: str) -> None:
    """Surface ``msg`` in the script editor AND on stderr. Never raises."""
    try:
        import maya.api.OpenMaya as om2

        om2.MGlobal.displayWarning(msg)
    except Exception:  # noqa: BLE001
        pass
    import sys

    sys.stderr.write(msg + "\n")


def _validate_attr_name(name: str, node_type: str | None = None) -> None:
    """Reject attribute names that can't be reached as ``self.<name>``.

    The expression contract is self-only, so a user attr name must be a valid
    Python identifier and not a keyword (``self.in`` / ``self.class`` are
    SyntaxErrors). Builtin-shadowing names (``min`` / ``type``) are allowed --
    ``self.min`` is unambiguous.

    A name that would be shadowed by (or would shadow) a framework slot on
    ``node_type`` is rejected too -- EXCEPT mid attr-surgery. ``_reorder_attrs``
    deletes every user attr and re-adds it, so raising there would destroy a
    legacy node's attributes and their connections; the same goes for a legacy
    ``.mpn`` restore. Those windows warn and let the name through.
    """
    if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
        raise ValueError(
            f"attribute name {name!r} must be a valid Python identifier and not "
            f"a Python keyword (it is accessed as self.{name})"
        )
    reason = _reserved_name_reason(name, node_type)
    if reason is None:
        return
    msg = (
        f"attribute name {name!r} is reserved by the framework: {reason}. "
        f"Pick another name."
    )
    if _in_attr_surgery():
        _display_warning("[mpynode] " + msg)
        return
    raise ValueError(msg)


# Maya cmds.addAttr type strings keyed by our wire-type strings.
_ADD_ATTR_KIND: dict[str, dict] = {
    "float": {"at": "float"},
    "double": {"at": "double"},
    "int": {"at": "long"},
    "bool": {"at": "bool"},
    "vector": {"at": "double3"},
    "matrix": {"dt": "matrix"},
    "string": {"dt": "string"},
    # angle / euler / enum.
    "angle": {"at": "doubleAngle"},
    "euler": {"at": "double3"},  # parent compound; XYZ children are doubleAngle
    "enum": {"at": "enum"},  # enumName supplied per-instance below
    # python = string with pickle/base64 wrap; hex = string with UTF-8-hex wrap
    # (write plain text -> "48 69 ..."; read decodes back), which drives Maya's
    # ``type`` node textInput. mesh/nurbsCurve/nurbsSurface = typed geo plugs.
    "python": {"dt": "string"},
    "hex": {"dt": "string"},
    "mesh": {"dt": "mesh"},
    "nurbsCurve": {"dt": "nurbsCurve"},
    "nurbsSurface": {"dt": "nurbsSurface"},
    # time — single time value, auto-connectable to time1.
    "time": {"at": "time"},
    # quaternion — 4 doubles (X/Y/Z/W), identity [0,0,0,1]. cmds can't make a
    # numeric double4, so at='compound' nc=4 with 4 explicit double children
    # (matches Maya's eulerToQuat.outputQuat).
    "quaternion": {"at": "compound", "numberOfChildren": 4},
    # color — 3-float RENDERABLE color (R/G/B children + usedAsColor) so it
    # binds to material.color / Arnold like a stock file node's outColor.
    "color": {"at": "float3", "usedAsColor": True},
    # float2 — 2-float compound (U/V), e.g. a uvCoord pair. Like float3/color
    # the 2 children must be added explicitly (cmds does NOT auto-create them).
    "float2": {"at": "float2"},
}


# Identity-matrix flat-16 for ``mc.setAttr(..., type="matrix")``. Initializes
# new matrix plugs so they read as identity: Maya leaves ``dt='matrix'`` storage
# unset by default, which breaks ``mc.getAttr`` / ``plug.asMObject``.
_IDENTITY_MATRIX_16 = (
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
)

VALID_INPUT_TYPES = list(_ADD_ATTR_KIND.keys())
VALID_OUTPUT_TYPES = list(_ADD_ATTR_KIND.keys())


# PACKED array storage: one typed-array plug instead of a numeric multi.
#
# A numeric multi costs one ``mc.setAttr`` per ELEMENT -- measured at ~173 us
# each with the node unwired, and ~3.8 ms each on an mPyBlendShape carrying 167
# connected targets (Maya re-enters setDependentsDirty ~2x per connected target
# on every element write). A 655,928-value table took 41.5 MINUTES. The same
# tables as typed arrays are three setAttr calls totalling 0.017 s.
#
# ``packed`` is a STORAGE flag, not a new wire type: the element type stays
# ``double`` / ``int``, so the expression still sees a flat sequence and the
# generated C++ still materialises the same ``std::vector<T>``. Only the plug
# kind and the read/write prologue change.
#
# INPUT-only and dense-only by design:
#   * a typed array has no logical element indices, so it cannot be ``sparse``
#     and its elements cannot be individually connected;
#   * array OUTPUTS pre-size themselves from their existing element indices
#     (see ``_api2/helpers.write_multi_plug_value``) and the self-sizing
#     templates read that count back as their N -- a packed output would have
#     no element count to read, so outputs keep the multi.
_PACKED_DT = {"double": "doubleArray", "int": "Int32Array"}


def _validate_packed(name, attr_type, is_array, sparse):
    """Reject a ``packed`` request the storage cannot honour."""
    if not is_array:
        raise ValueError(
            f"packed applies to array attrs only ({name!r}); pass is_array=True"
        )
    if attr_type not in _PACKED_DT:
        raise ValueError(
            f"packed is not available for attr_type {attr_type!r} ({name!r}); "
            f"valid: {sorted(_PACKED_DT)}"
        )
    if sparse:
        raise ValueError(
            f"packed and sparse are mutually exclusive ({name!r}): a typed "
            f"array has no logical element indices to read sparsely"
        )

# Child-axis suffixes for compound attrs whose children are renamed alongside
# the parent (vector/euler XYZ, quaternion XYZW, color RGB).
_COMPOUND_CHILD_AXES = {
    "vector": ("X", "Y", "Z"),
    "euler": ("X", "Y", "Z"),
    "quaternion": ("X", "Y", "Z", "W"),
    "color": ("R", "G", "B"),
    "float2": ("U", "V"),
}

# Scalar numeric types that accept min/max/default via cmds.addAttr. Compound,
# bool, enum, string, geometry and time don't take these here.
_NUMERIC_LIMIT_TYPES = ("float", "double", "int", "angle")


def _apply_numeric_limits(kwargs, attr_type, min_value, max_value, default_value):
    """Add minValue/maxValue/defaultValue to ``cmds.addAttr`` kwargs for a
    scalar numeric attr. No-op for non-numeric types or None values."""
    if attr_type not in _NUMERIC_LIMIT_TYPES:
        return
    cast = int if attr_type == "int" else float
    if min_value is not None:
        kwargs["minValue"] = cast(min_value)
    if max_value is not None:
        kwargs["maxValue"] = cast(max_value)
    if default_value is not None:
        kwargs["defaultValue"] = cast(default_value)


def _record_numeric_limits(meta, attr_type, min_value, max_value, default_value):
    """Persist min/max/default into an attr's JSON meta dict so they survive
    .mpn template round-trips (Maya scene save already keeps them natively)."""
    if attr_type not in _NUMERIC_LIMIT_TYPES:
        return
    if min_value is not None:
        meta["min_value"] = min_value
    if max_value is not None:
        meta["max_value"] = max_value
    if default_value is not None:
        meta["default_value"] = default_value


def _apply_enum_default(kwargs, attr_type, default_value):
    """Add an enum's starting field index as ``cmds.addAttr`` defaultValue.

    Enum is a numeric (short) attr under the hood, so addAttr accepts an int
    ``defaultValue``; it is NOT a min/max-limited type, hence its own helper.
    No-op for non-enum types or an unset default."""
    if attr_type == "enum" and default_value is not None:
        kwargs["defaultValue"] = int(default_value)


def _record_enum_default(meta, attr_type, default_value):
    """Persist an enum's default field index into its JSON meta so it survives
    .mpn template round-trips. Recorded only when supplied, so a node with no
    explicit enum default keeps a byte-identical spec / port-cache key."""
    if attr_type == "enum" and default_value is not None:
        meta["default_value"] = int(default_value)


def _apply_bool_default(kwargs, attr_type, default_value):
    """Add a bool's starting value as ``cmds.addAttr`` defaultValue.

    bool is a numeric attr under the hood, so addAttr accepts an int
    ``defaultValue``; it is NOT a min/max-limited type, hence its own helper
    (twin of :func:`_apply_enum_default`). No-op for non-bool types or an unset
    default.

    Needed because Maya omits a multi element whose value equals the attribute
    default when it writes a .ma: a bool stream whose compute overlays True for
    absent elements must declare True, or every authored False vanishes on
    reload (metaballs ``additive``)."""
    if attr_type == "bool" and default_value is not None:
        kwargs["defaultValue"] = int(bool(default_value))


def _record_bool_default(meta, attr_type, default_value):
    """Persist a bool's default into its JSON meta so it survives .mpn template
    round-trips and reaches codegen (``emit_attr._bool_default``). Recorded only
    when supplied, so a node with no explicit bool default keeps a
    byte-identical spec / port-cache key."""
    if attr_type == "bool" and default_value is not None:
        meta["default_value"] = bool(default_value)


def _color_default_rgb(attr_type, default_value):
    """Normalize a colour attr's ``(r, g, b)`` default to three floats, or None.

    A ``color`` is a float3 parent whose R/G/B children are added one at a time,
    each carrying its OWN defaultValue -- so unlike the scalar helpers above
    there is no single kwargs dict to fill. Both the apply site and
    :func:`_record_color_default` take the normalized triple from here so they
    cannot disagree. Anything that is not a 3-sequence of numbers is ignored, so
    every existing caller keeps its zeros."""
    if attr_type != "color" or not isinstance(default_value, (list, tuple)):
        return None
    if len(default_value) != 3:
        return None
    try:
        return [float(c) for c in default_value]
    except (TypeError, ValueError):
        return None


def _record_color_default(meta, attr_type, default_value):
    """Persist a colour's default into its JSON meta so it survives .mpn
    template round-trips and reaches codegen (``nAttr.setDefault``). Without
    this the default is applied to the live plug but LOST on serialize, so a
    node rebuilt from its template comes back all-zero. Recorded only when
    supplied, so a node with no explicit colour default keeps a byte-identical
    spec / port-cache key."""
    rgb = _color_default_rgb(attr_type, default_value)
    if rgb is not None:
        meta["default_value"] = rgb


def _invalidate_affects() -> None:
    """Drop the cached input/output schema used by setDependentsDirty so a
    just-added/removed/renamed attr is picked up immediately. Lives on the
    MPyNode base so every wrapper -- which all inherit MPyNode -- gets it."""
    try:
        from mpynode._common.plugs import dirty_affects

        dirty_affects.invalidate_all()
    except Exception:
        pass


class MPyNode(InitSourceMixin, MethodsSourceMixin, MetadataMixin,
              GapSpacingMixin):
    """Wrapper around an mPyNode instance in the scene.

    Carries the Methods tier (``MethodsSourceMixin``) AND the metadata tier
    (``MetadataMixin``) at the BASE so EVERY wrapper type -- vanilla mPyNode,
    mPyFile, mPyMesh, mPyDeformer, ... -- gets a "Methods" tab in the Node
    Designer and can carry per-node authorship/version/license metadata, not
    only mPyLocator. ``GapSpacingMixin`` rides along for the same reason: the
    API view's blank-line spacing is editable on every node type. All three add
    no ``__init__`` and create their hidden plug (``_methodsSource`` /
    ``_metadata`` / ``_apiGapSpacing``) lazily (only on the first set), so nodes
    that never author methods, metadata or spacing are unchanged.
    """

    # No bridge-injected non-plug ``self.X`` names: every ``self.X`` is either a
    # plug (Attributes tab) or per-call user storage (Variables-User).
    INTERNAL_API_SLOTS = ()

    # Attributes-tab allowlist: inherited plugs to SHOW when "Show framework
    # attrs" is OFF (see plug_filter.is_useful_inherited). Base default shows
    # NONE. Subclasses override with their own frozenset; one that forgets
    # inherits frozenset() -> safe, never leaks. Unregistered nodes have no
    # wrapper class, so the resolver returns None and the denylist applies.
    USEFUL_INHERITED_PLUGS = frozenset()

    NATIVE_TYPE = "mPyNode"

    # Array INPUTS are created non-keyable so scalar-numeric multis stay out of
    # the channel box. A subtype names here the FEW arrays that must be exempt
    # -- Maya honours keyable only at addAttr time, so an array left out of this
    # cannot be repaired afterwards. Base default exempts nothing.
    KEYABLE_ARRAY_INPUTS = ()

    def __new__(cls, name=None, *args, **kwargs):
        """Factory dispatch: ``MPyNode("someNode")`` returns the *specific*
        wrapper for that node's type (e.g. an ``MPySkinCluster`` for an
        ``mPySkinCluster`` node) instead of a bare ``MPyNode``.

        Only kicks in when constructing the base ``MPyNode`` directly with a
        name that resolves to a registered mPy type. Constructing a subclass
        (``MPySkinCluster("x")``) or an unregistered/non-mPy node falls
        through to normal construction (bare ``MPyNode``). Because the
        returned object is always an ``MPyNode`` subclass, Python runs the
        inherited ``__init__`` on it exactly once, and ``isinstance(x,
        MPyNode)`` still holds.

        NOTE: dispatch is on the *named node's own type*. For shape-based
        types (e.g. ``mPyLocator``) pass the shape name, not its transform.
        """
        if name:
            try:
                if mc.objExists(name):
                    from mpynode._node_registry import get_spec

                    spec = get_spec(mc.nodeType(name))
                    if spec is not None:
                        root = spec.get_wrapper_class()
                        if (isinstance(root, type)
                                and issubclass(root, MPyNode)):
                            # "Generic construction": the caller asked for base
                            # MPyNode or the registry root for this Maya type.
                            # Only then auto-resolve to a more specific class;
                            # an explicit subclass is honored as-is.
                            if cls is MPyNode or cls is root:
                                chosen = root
                                pc = _read_py_class(name)
                                if pc:
                                    logical = _import_py_class(pc)
                                    if (isinstance(logical, type)
                                            and issubclass(logical, root)):
                                        chosen = logical
                                if chosen is not cls:
                                    return object.__new__(chosen)
            except Exception as exc:
                import sys

                sys.stderr.write(
                    "[MPyNode.__new__] type dispatch for %r failed; "
                    "falling back to base MPyNode: %s\n" % (name, exc))
        return super().__new__(cls)

    @classmethod
    def _construction_help(cls) -> str:
        """Guidance appended to constructor errors: how to CREATE vs WRAP.

        Names the ACTUAL wrapper class (``cls.__name__``) so a subclass reads
        ``MPyLocator.build()``, not ``MPyNode.build()``. ``build`` and ``wrap``
        are inherited by every wrapper, so the advice is always valid.
        """
        n = cls.__name__
        return (
            f"{n}(name) wraps an EXISTING node by name; it does not create one. "
            f"To CREATE a new node, use {n}.build() (or {n}.create(name=...)). "
            f"To wrap an existing node, pass a name that exists, "
            f"e.g. {n}('myNode') or {n}.wrap('myNode')."
        )

    def __init__(self, name: str = None):
        # No name -> the caller almost certainly meant to CREATE a node
        # (e.g. ``TimesTwo()``). Replace Python's cryptic "missing 1 required
        # positional argument: 'name'" with guidance to the build() factory.
        if name is None:
            raise TypeError(
                f"{type(self).__name__}() needs the name of an existing node. "
                + self._construction_help()
            )
        if not mc.objExists(name):
            raise ValueError(
                f"node {name!r} does not exist. " + self._construction_help()
            )
        self._name = name

    @classmethod
    def wrap(cls, name: str):
        """Explicit factory: return the specific wrapper for an existing
        scene node by name (auto-detecting its mPy type). Equivalent to
        ``MPyNode(name)`` but reads more clearly at call sites.

        Returns ``None`` if ``name`` doesn't exist."""
        from mpynode._node_registry import wrap_node as _wrap

        return _wrap(name)

    @classmethod
    def _is_user_subclass(cls) -> bool:
        """True if ``cls`` is a user-defined logical subclass -- i.e. NOT the
        base ``MPyNode`` and NOT the registry root wrapper for its native type
        (``MPyFile``, ``MPyLocator``, ...).

        This is the distinction that drives ``ls()`` scoping and auto-stamp on
        ``create()``: a logical subclass narrows within a native type and carries
        an importable ``_pyClass`` identity; a root wrapper does not.
        """
        if cls is MPyNode:
            return False
        try:
            from mpynode._node_registry import get_spec

            spec = get_spec(cls.NATIVE_TYPE)
            if spec is not None and spec.get_wrapper_class() is cls:
                return False
        except Exception:  # noqa: BLE001
            pass
        return True

    @classmethod
    def ls(cls):
        """Return wrappers for every scene node of this class's native type.

        Base ``MPyNode`` / any root wrapper returns ALL nodes of its
        ``NATIVE_TYPE`` (bare + logical subclasses that share it). A user
        subclass returns only nodes whose live logical class ``isinstance``-es
        it -- import-on-wrap (``__new__``) has already upgraded each wrapper to
        its stamped ``_pyClass``, so the filter reflects true identity.
        """
        names = mc.ls(type=cls.NATIVE_TYPE, long=True) or []
        wrapped = []
        for n in names:
            try:
                wrapped.append(MPyNode(n))
            except Exception:  # noqa: BLE001
                continue
        if cls._is_user_subclass():
            return [w for w in wrapped if isinstance(w, cls)]
        return wrapped

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyNode":
        """Create a new mPyNode in the scene + return the wrapper.

        ``name=None`` (the default) DERIVES the name from the Class -- the
        camelCase (lower-first) of the class name, matching the compiled C++
        node type (see :meth:`_default_create_name`). So
        ``ProcrustesConstraint.create()`` -> ``procrustesConstraint1``, tying the
        Python-API default name to the same convention as
        ``mc.createNode('procrustesConstraint')``. An explicit ``name`` (which
        may include a ``#`` for Maya auto-numbering) overrides the derivation.

        ``skip_selection=True`` creates the node WITHOUT making it the active
        selection (passes ``skipSelect=True`` to ``cmds.createNode``); the
        default (False) reproduces Maya's behavior (the new node is selected).

        This is the PRIMITIVE: it returns a bare, inert, UNSEEDED node (no
        selection read, no methods-source seeding, no setup). Callers wanting
        the orchestrated path (seed the per-type methods source + optional
        ``setup(self)``) must use ``build()`` instead.
        """
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        if name is None:
            name = cls._default_create_name()
        ensure_loaded(cls.NATIVE_TYPE)
        node_name = mc.createNode(cls.NATIVE_TYPE, name=name,
                                  skipSelect=skip_selection)
        node = cls(node_name)
        # Auto-stamp the logical identity when a user subclass creates the node
        # (base/root wrappers stay unstamped -> None). ``build()`` funnels
        # through here, so it inherits the stamp for free.
        return cls._stamp_py_class(node)

    @classmethod
    def _default_create_name(cls):
        """Default node name for ``create(name=None)``: the camelCase
        (lower-first) of the Class name + Maya's ``#`` auto-number token
        (``ProcrustesConstraint`` -> ``procrustesConstraint#`` ->
        ``procrustesConstraint1``).

        This is the SAME convention the compiled C++ node type uses
        (``derive_class_identity``'s ``node_type_name`` = lower-first of the
        PascalCase Class), so ``Foo.create()`` and ``mc.createNode('foo')`` name
        their nodes alike. For a root wrapper it reproduces the native type
        (``MPyNode`` -> ``mPyNode#``, ``MPyConstraint`` -> ``mPyConstraint#``),
        so a no-arg create on a base type is unchanged. Every ``create()``
        override funnels its ``name is None`` case through here, so the Python
        default name is NEVER a hardcoded per-wrapper literal."""
        stem = cls.__name__ or "mPyNode"
        return stem[:1].lower() + stem[1:] + "#"

    @classmethod
    def _stamp_py_class(cls, node):
        """Stamp the logical ``_pyClass`` identity on ``node`` iff ``cls`` is a
        user subclass; return ``node`` for call-site chaining.

        Base ``MPyNode`` and every root wrapper (``MPyMesh``, ``MPyLocator``,
        ...) leave the plug empty -> ``get_py_class()`` returns ``None``. This
        is the SINGLE place the stamp is applied so every ``create()`` override
        stamps identically -- a subtype override that builds its node via a raw
        ``mc.createNode`` must call this before returning, or a user subclass of
        that subtype would silently lose its logical identity (W3/W4).
        """
        if cls._is_user_subclass():
            node.set_py_class(cls.__module__ + "." + cls.__qualname__)
        return node

    @classmethod
    def build(cls, name=None, setup=False, selection=None,
              skip_selection=False, **kwargs):
        """Create + populate a node; if ``setup=True``, also run its
        ``setup(self)``.

        ``create()`` stays the primitive; ``build()`` is the orchestrator the
        UI / commands use. Setup bodies NEVER call ``create()`` -- they wire the
        already-built ``self``. On a setup failure the node is left BUILT but
        UNWIRED (the exception is swallowed + logged), so creation never fails.

        Lives on the base ``MPyNode`` so every wrapper type inherits it. Honors
        each subtype's ``create()`` signature via the ``name=`` keyword (skin /
        blend default mesh/joints/targets to None -> bare; mPyFile keeps its
        seed_defaults/as_texture defaults).
        """
        from mpynode._common.methods.methods_registry import (
            build_methods_namespace, invoke_command, _resolved_is_instance_setup)
        if selection is None and setup:
            selection = mc.ls(selection=True, long=False) or []
        node = (cls.create(name=name, skip_selection=skip_selection)
                if name is not None
                else cls.create(skip_selection=skip_selection))
        cls._populate_methods_source(node)
        if setup:
            src = node.get_methods_source() or ""
            fn = build_methods_namespace(src).get("setup")
            if _resolved_is_instance_setup(fn):
                try:
                    invoke_command(fn, node, kwargs={"selection": selection, **kwargs})
                except Exception as exc:
                    import sys
                    sys.stderr.write("[_mpy_node.build] setup failed for %r: %s -- "
                                     "node built but left unwired.\n"
                                     % (node.get_name(), exc))
        return node

    @classmethod
    def _populate_methods_source(cls, node):
        """Ensure ``node._methodsSource`` carries a valid self-first setup
        (MERGE, not replace, design 6.1): append the type default only if the
        node has no setup yet; never clobber sibling methods; if it already has
        a setup, leave it. No-op for types without an authored setup source."""
        from mpynode._common import node_setups
        cur = node.get_methods_source() or ""
        # The merge rule lives in node_setups so the compile path applies the
        # IDENTICAL one -- a template's compiled node must carry the same seeded
        # setup as its interpreted twin, or the bundle silently lacks the
        # setup's create command.
        merged = node_setups.merge_type_default(cur, type(node).NATIVE_TYPE)
        if merged != cur:
            node.set_methods_source(merged)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    # Class-level defaults so the ``_name`` property is safe even on an
    # instance whose ``__init__`` never ran (``object.__new__`` in a factory).
    _name_cache = None
    _name_handle = None
    _name_fn = None
    _name_is_dag = False

    @property
    def _name(self) -> str:
        """This node's CURRENT Maya name, re-resolved from its ``MObject``.

        The wrapper binds to the OBJECT, not to the string it was built with.
        A ``cmds.rename`` run OUTSIDE the wrapper (templates do this --
        ``mesh_regions`` renames the locator it just built) would otherwise
        leave the cached string -- and therefore every ``self._name + ".attr"``
        plug access built from it -- pointing at a name that no longer exists.

        ``partialPathName()`` for a DAG node (shortest unambiguous path, so a
        duplicated shape name still resolves), the dependency-node name
        otherwise. Both are namespace-qualified and directly ``cmds``-usable.
        When no handle could be taken (an ambiguous name at construction) or the
        node is gone, this returns the last known string, so those cases fail
        exactly where they failed before.
        """
        handle = self._name_handle
        fn = self._name_fn
        if handle is None or fn is None or not handle.isValid():
            return self._name_cache
        try:
            self._name_cache = (fn.partialPathName() if self._name_is_dag
                                else fn.name())
        except Exception:  # noqa: BLE001
            pass
        return self._name_cache

    @_name.setter
    def _name(self, value: str) -> None:
        self._name_cache = value
        self._bind_name_handle(value)

    def _bind_name_handle(self, name: str) -> None:
        """Capture the ``MObjectHandle`` + function set backing ``_name``.

        Best effort: any failure (or a name matching more than one node, which
        ``cmds`` itself rejects as ambiguous) leaves the wrapper on the plain
        cached string it has always used.
        """
        self._name_handle = None
        self._name_fn = None
        self._name_is_dag = False
        try:
            import maya.api.OpenMaya as om2

            sel = om2.MSelectionList()
            sel.add(name)
            if sel.length() != 1:
                return
            obj = sel.getDependNode(0)
            if obj.hasFn(om2.MFn.kDagNode):
                self._name_fn = om2.MFnDagNode(obj)
                self._name_is_dag = True
            else:
                self._name_fn = om2.MFnDependencyNode(obj)
            self._name_handle = om2.MObjectHandle(obj)
        except Exception:  # noqa: BLE001
            self._name_handle = None
            self._name_fn = None
            self._name_is_dag = False

    def get_name(self) -> str:
        """Return this node's current Maya name (canonical accessor)."""
        return self._name

    def set_name(self, new_name: str) -> str:
        """Rename the underlying Maya node and return the resulting name.

        Wraps ``cmds.rename`` (Maya may adjust the requested name to keep
        it unique / legal) and updates the wrapper's cached name so the
        wrapper keeps pointing at the same node.
        """
        self._name = mc.rename(self._name, new_name)
        return self._name

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._name!r}>"

    # ------------------------------------------------------------------
    # Compute expression
    # ------------------------------------------------------------------

    def set_compute_expression(self, source: str) -> None:
        """Set the Compute-tab expression text on this node."""
        mc.setAttr(self._name + "._computeSource", source, type="string")

    def get_compute_expression(self) -> str:
        return mc.getAttr(self._name + "._computeSource") or ""

    def clear_compute_expression(self) -> None:
        """Reset the Compute expression to empty."""
        mc.setAttr(self._name + "._computeSource", "", type="string")

    def has_compute_expression(self) -> bool:
        """True if a non-empty Compute expression is set."""
        return bool(self.get_compute_expression().strip())

    # ------------------------------------------------------------------
    # Logical class identity (_pyClass)
    # ------------------------------------------------------------------

    def get_py_class(self):
        """Return this node's logical class dotted path, or ``None`` if unset.

        See ``_read_py_class`` for the by-name equivalent used before a wrapper
        exists."""
        return _read_py_class(self._name)

    def set_py_class(self, dotted_path: str) -> None:
        """Stamp an importable dotted class path on this node (lazy-adds the
        hidden ``_pyClass`` string plug, parity with ``_metadata``).

        An empty / ``None`` value clears the identity (reverts to the root
        wrapper)."""
        if not dotted_path:
            self.clear_py_class()
            return
        if not mc.attributeQuery(_PY_CLASS_PLUG, node=self._name, exists=True):
            mc.addAttr(self._name, longName=_PY_CLASS_PLUG, dataType="string",
                       hidden=True)
        mc.setAttr("%s.%s" % (self._name, _PY_CLASS_PLUG), dotted_path,
                   type="string")

    def clear_py_class(self) -> None:
        """Clear the logical identity (set the plug to empty; keep the attr)."""
        if mc.attributeQuery(_PY_CLASS_PLUG, node=self._name, exists=True):
            try:
                mc.setAttr("%s.%s" % (self._name, _PY_CLASS_PLUG), "",
                           type="string")
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Input attrs
    # ------------------------------------------------------------------

    def add_input_attr(
        self,
        name: str,
        attr_type: str,
        is_array: bool = False,
        enum_names: list[str] | None = None,
        auto_connect_time: bool = True,
        min_value=None,
        max_value=None,
        default_value=None,
        sparse: bool = False,
        packed: bool = False,
    ) -> None:
        """Add a user-defined INPUT plug to this node.

        Adds the plug via ``cmds.addAttr`` AND records it in the
        ``_inputAttrs`` JSON so the bridge knows which plugs to read
        when the expression executes.

        ``enum_names`` is required for ``attr_type='enum'``; ignored
        otherwise. Falls back to ``['False', 'True']`` if omitted.

        ``sparse`` (array inputs only): selects how the expression READS the
        array. The default ``False`` reads a DENSE numpy array of length
        ``max_logical+1`` with unconnected/unset gaps filled by the attribute
        default, so ``self.X[i]`` lines up with logical index ``i``. Pass
        ``True`` for a compact, connected-only read (the old behavior) -- e.g.
        a "collector" wired via ``nextAvailable`` where only the values matter,
        not their indices.

        ``packed`` (array inputs, ``double``/``int`` only): store the array as
        ONE typed-array plug (``doubleArray`` / ``Int32Array``) instead of a
        numeric multi. The expression sees the same flat sequence and the
        compiled node materialises the same ``std::vector<T>``; what changes is
        that the whole table moves in a single ``setAttr`` rather than one
        command per element -- 655,928 values measured at 41.5 min as a multi
        vs 0.017 s packed. Use it for dense, machine-written tables.

        Packed is mutually exclusive with ``sparse`` (a typed array has no
        logical element indices), its elements cannot be individually
        connected, and it cannot be toggled after creation -- unlike ``sparse``
        it is the plug KIND, not just a read hint, so switching means deleting
        and re-adding the attribute.

        ``min_value`` / ``max_value`` / ``default_value`` apply to scalar
        numeric types (float / double / int / angle). They map to
        ``cmds.addAttr`` minValue / maxValue / defaultValue (hard limits +
        unconnected value); each is optional (None = unset). Ignored for
        non-numeric types. ``default_value`` alone also applies to ``enum``
        (starting field index) and ``bool``. Ignored when ``packed``.

        ``auto_connect_time``: when True (default) AND
        ``attr_type='time'`` AND ``is_array=False``, the new plug is
        connected to ``time1.outTime`` so the user expression sees
        the current frame without manual wiring. The default ``time1``
        node is created if it doesn't exist (Maya almost always has it,
        but new scenes occasionally don't until something asks for time).
        Pass False to add the time plug bare.
        """
        _validate_attr_name(name, type(self).NATIVE_TYPE)
        if attr_type not in _ADD_ATTR_KIND:
            raise ValueError(
                f"attr_type {attr_type!r} not supported; valid: {sorted(_ADD_ATTR_KIND)}"
            )
        if packed:
            _validate_packed(name, attr_type, is_array, sparse)

        if packed:
            kwargs = {"dataType": _PACKED_DT[attr_type]}
        else:
            kwargs = dict(_ADD_ATTR_KIND[attr_type])
        kwargs["longName"] = name
        kwargs["shortName"] = name
        # Array inputs are NOT keyable: a scalar-numeric multi would otherwise
        # leak into the channel box. Still editable in the Attribute Editor.
        # KEYABLE_ARRAY_INPUTS opts a named array back in. That has to happen
        # HERE and nowhere else: `addAttr -e -keyable` is rejected outright, and
        # setAttr on the plug does not move the channel box -- both measured --
        # so attribute creation is the only chance to get the flag right.
        kwargs["keyable"] = (not is_array
                             or name in type(self).KEYABLE_ARRAY_INPUTS)
        # A packed array is ONE typed-array plug, not a multi -- the whole table
        # moves in a single setAttr instead of one command per element.
        if is_array and not packed:
            kwargs["multi"] = True
        # enumName is per-instance.
        if attr_type == "enum":
            entries = list(enum_names) if enum_names else ["False", "True"]
            kwargs["enumName"] = ":".join(entries)
        # min/max/default are numeric-attr flags; addAttr rejects them on a
        # dataType plug, and a packed table has no per-element default anyway.
        if not packed:
            _apply_numeric_limits(kwargs, attr_type, min_value, max_value,
                                  default_value)
            _apply_enum_default(kwargs, attr_type, default_value)
            _apply_bool_default(kwargs, attr_type, default_value)

        mc.addAttr(self._name, **kwargs)

        # vector (double3) — also create the 3 child plugs Maya expects.
        if attr_type == "vector":
            for axis in ("X", "Y", "Z"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="double",
                    parent=name,
                    keyable=True,
                )
        # euler is double3 with doubleAngle children.
        elif attr_type == "euler":
            for axis in ("X", "Y", "Z"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="doubleAngle",
                    parent=name,
                    keyable=True,
                )
        # quaternion — generic compound; 4 double children X/Y/Z/W. W defaults
        # to 1.0 so an unset / unconnected quaternion reads as identity.
        elif attr_type == "quaternion":
            for axis in ("X", "Y", "Z", "W"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="double",
                    parent=name,
                    keyable=True,
                    defaultValue=(1.0 if axis == "W" else 0.0),
                )
        # color — float3 + usedAsColor; the R/G/B float children must be added
        # explicitly (cmds float3 does NOT auto-create them).
        elif attr_type == "color":
            # An (r, g, b) default seeds each child. Without it a node wanting a
            # sensible starting colour has to fake one in the compute ("all
            # zeros means unset -> substitute"), which makes a deliberately
            # BLACK colour unreachable and shows a number that is not what is
            # drawn. Anything that is not a 3-sequence is ignored, so every
            # existing caller keeps its zeros.
            _cdv = _color_default_rgb(attr_type, default_value)
            for i, axis in enumerate(("R", "G", "B")):
                _kw = {} if _cdv is None else {"defaultValue": _cdv[i]}
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="float",
                    parent=name,
                    keyable=True,
                    **_kw
                )
        # float2 — float2 parent + 2 float children (U/V), added explicitly.
        elif attr_type == "float2":
            for axis in ("U", "V"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="float",
                    parent=name,
                    keyable=True,
                )

        attr_map = self._read_input_map()
        meta = {"attr_type": attr_type, "is_array": is_array}
        if is_array and sparse:
            meta["sparse"] = True
        if is_array and packed:
            meta["packed"] = True
        if attr_type == "enum":
            meta["enum_names"] = list(enum_names) if enum_names else ["False", "True"]
        _record_numeric_limits(meta, attr_type, min_value, max_value, default_value)
        _record_enum_default(meta, attr_type, default_value)
        _record_bool_default(meta, attr_type, default_value)
        # Input only: the OUTPUT path never applies a per-child colour default,
        # so recording one there would put a value in the payload that was
        # never on the plug.
        _record_color_default(meta, attr_type, default_value)
        meta["order"] = self._next_order_value(attr_map)
        attr_map[name] = meta
        self._write_input_map(attr_map)

        # Initialize a matrix INPUT to identity: ``dt='matrix'`` leaves the
        # storage empty, so mc.getAttr returns None and plug.asMObject raises
        # kFailure until something writes to it. Skip multis -- per-element init
        # is impractical, and read_plug_value already falls back to identity.
        if attr_type == "matrix" and not is_array:
            try:
                mc.setAttr(
                    self._name + "." + name,
                    _IDENTITY_MATRIX_16,
                    type="matrix",
                )
            except Exception:
                pass

        # auto-connect time1.outTime → our time input.
        if attr_type == "time" and auto_connect_time and not is_array:
            self._auto_connect_time_attr(name)

        # Install/refresh the user-input auto-dirty scriptJob so value changes
        # trigger re-eval in interactive Maya, then invalidate the affects cache.
        try:
            from mpynode._common.plugs import auto_dirty

            auto_dirty.refresh_for_node(self._name)
        except Exception:
            pass
        _invalidate_affects()

    def _auto_connect_time_attr(self, attr_name: str) -> None:
        """Find or create time1 and connect its outTime to our plug.

        Best-effort — silent on failure (already connected, missing
        permissions, etc.). The user can always wire it manually via
        the Connect dialog if this fails.
        """
        try:
            # Maya scenes usually already have time1 (a singleton time
            # node). If not, create it.
            if not mc.objExists("time1"):
                try:
                    mc.createNode("time", name="time1", skipSelect=True)
                except Exception:
                    pass
            if mc.objExists("time1"):
                mc.connectAttr(
                    "time1.outTime",
                    f"{self._name}.{attr_name}",
                    force=True,
                )
        except Exception:
            pass

    def delete_input_attr(self, name: str) -> None:
        attr_map = self._read_input_map()
        if name not in attr_map:
            return
        try:
            mc.deleteAttr(self._name + "." + name)
        except Exception:
            pass
        del attr_map[name]
        self._write_input_map(attr_map)
        _invalidate_affects()

    def rename_input_attr(self, old_name: str, new_name: str) -> None:
        """Rename an existing user-added INPUT attr.

        Renames the Maya plug + its X/Y/Z children for vector attrs +
        updates the ``_inputAttrs`` JSON map.
        """
        attr_map = self._read_input_map()
        if old_name not in attr_map:
            raise ValueError(f"input attr {old_name!r} not found")
        if new_name in attr_map and new_name!= old_name:
            raise ValueError(f"cannot rename to {new_name!r}: already exists")
        if new_name == old_name:
            return
        _validate_attr_name(new_name, type(self).NATIVE_TYPE)
        meta = attr_map[old_name]
        # Rename children FIRST for compound types so the parent's
        # short/long names align after the parent rename.
        _child_axes = _COMPOUND_CHILD_AXES.get(meta.get("attr_type"))
        if _child_axes:
            for axis in _child_axes:
                try:
                    mc.renameAttr(
                        self._name + "." + old_name + axis,
                        new_name + axis,
                    )
                except Exception:
                    pass
        mc.renameAttr(self._name + "." + old_name, new_name)
        del attr_map[old_name]
        attr_map[new_name] = meta
        self._write_input_map(attr_map)
        _invalidate_affects()

    def get_input_attr_map(self) -> dict:
        return self._ordered_attr_map(self._read_input_map())

    def list_valid_input_types(self) -> list[str]:
        return list(VALID_INPUT_TYPES)

    # ------------------------------------------------------------------
    # Output attrs
    # ------------------------------------------------------------------

    def add_output_attr(
        self,
        name: str,
        attr_type: str,
        is_array: bool = False,
        enum_names: list[str] | None = None,
        min_value=None,
        max_value=None,
        default_value=None,
    ) -> None:
        _validate_attr_name(name, type(self).NATIVE_TYPE)
        if attr_type not in _ADD_ATTR_KIND:
            raise ValueError(
                f"attr_type {attr_type!r} not supported; valid: {sorted(_ADD_ATTR_KIND)}"
            )

        kwargs = dict(_ADD_ATTR_KIND[attr_type])
        kwargs["longName"] = name
        kwargs["shortName"] = name
        # Outputs are NOT keyable (driven by compute).
        kwargs["keyable"] = False
        kwargs["writable"] = False
        kwargs["readable"] = True
        if is_array:
            kwargs["multi"] = True
        # enumName per-instance.
        if attr_type == "enum":
            entries = list(enum_names) if enum_names else ["False", "True"]
            kwargs["enumName"] = ":".join(entries)
        _apply_numeric_limits(kwargs, attr_type, min_value, max_value, default_value)
        _apply_enum_default(kwargs, attr_type, default_value)
        _apply_bool_default(kwargs, attr_type, default_value)

        mc.addAttr(self._name, **kwargs)

        if attr_type == "vector":
            for axis in ("X", "Y", "Z"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="double",
                    parent=name,
                    keyable=False,
                    writable=False,
                    readable=True,
                )
        # euler is double3 with doubleAngle children.
        elif attr_type == "euler":
            for axis in ("X", "Y", "Z"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="doubleAngle",
                    parent=name,
                    keyable=False,
                    writable=False,
                    readable=True,
                )
        # quaternion — generic compound; 4 double children X/Y/Z/W (W default 1.0).
        elif attr_type == "quaternion":
            for axis in ("X", "Y", "Z", "W"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="double",
                    parent=name,
                    keyable=False,
                    writable=False,
                    readable=True,
                    defaultValue=(1.0 if axis == "W" else 0.0),
                )
        # color — float3 + usedAsColor; explicit R/G/B float children.
        elif attr_type == "color":
            for axis in ("R", "G", "B"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="float",
                    parent=name,
                    keyable=False,
                    writable=False,
                    readable=True,
                )
        # float2 — float2 parent + 2 float children (U/V), added explicitly.
        elif attr_type == "float2":
            for axis in ("U", "V"):
                mc.addAttr(
                    self._name,
                    longName=name + axis,
                    shortName=name + axis,
                    attributeType="float",
                    parent=name,
                    keyable=False,
                    writable=False,
                    readable=True,
                )

        attr_map = self._read_output_map()
        meta = {"attr_type": attr_type, "is_array": is_array}
        if attr_type == "enum":
            meta["enum_names"] = list(enum_names) if enum_names else ["False", "True"]
        _record_numeric_limits(meta, attr_type, min_value, max_value, default_value)
        _record_enum_default(meta, attr_type, default_value)
        _record_bool_default(meta, attr_type, default_value)
        meta["order"] = self._next_order_value(attr_map)
        attr_map[name] = meta
        self._write_output_map(attr_map)

        # Initialize a matrix OUTPUT to identity -- same rationale as
        # add_input_attr: ``dt='matrix'`` storage is empty and reads fail.
        if attr_type == "matrix" and not is_array:
            try:
                mc.setAttr(
                    self._name + "." + name,
                    _IDENTITY_MATRIX_16,
                    type="matrix",
                )
            except Exception:
                pass

        _invalidate_affects()

    def delete_output_attr(self, name: str) -> None:
        attr_map = self._read_output_map()
        if name not in attr_map:
            return
        try:
            mc.deleteAttr(self._name + "." + name)
        except Exception:
            pass
        del attr_map[name]
        self._write_output_map(attr_map)
        _invalidate_affects()

    def rename_output_attr(self, old_name: str, new_name: str) -> None:
        """Rename an existing user-added OUTPUT attr."""
        attr_map = self._read_output_map()
        if old_name not in attr_map:
            raise ValueError(f"output attr {old_name!r} not found")
        if new_name in attr_map and new_name!= old_name:
            raise ValueError(f"cannot rename to {new_name!r}: already exists")
        if new_name == old_name:
            return
        _validate_attr_name(new_name, type(self).NATIVE_TYPE)
        meta = attr_map[old_name]
        _child_axes = _COMPOUND_CHILD_AXES.get(meta.get("attr_type"))
        if _child_axes:
            for axis in _child_axes:
                try:
                    mc.renameAttr(
                        self._name + "." + old_name + axis,
                        new_name + axis,
                    )
                except Exception:
                    pass
        mc.renameAttr(self._name + "." + old_name, new_name)
        del attr_map[old_name]
        attr_map[new_name] = meta
        self._write_output_map(attr_map)
        _invalidate_affects()

    def get_output_attr_map(self) -> dict:
        return self._ordered_attr_map(self._read_output_map())

    def list_valid_output_types(self) -> list[str]:
        return list(VALID_OUTPUT_TYPES)

    # ------------------------------------------------------------------
    # Per-attr UI color storage: the optional ``ui_color`` key on each meta
    # dict in _inputAttrs / _outputAttrs, a hex string like "#ff0000".
    # None / missing = use the type-default color.
    # ------------------------------------------------------------------

    def set_input_attr_color(self, name: str, hex_color: str | None) -> None:
        """Set (or clear, if hex_color is None) the UI color for an input."""
        attr_map = self._read_input_map()
        if name not in attr_map:
            raise ValueError(f"input attr {name!r} not found")
        meta = dict(attr_map[name])
        if hex_color is None:
            meta.pop("ui_color", None)
        else:
            meta["ui_color"] = hex_color
        attr_map[name] = meta
        self._write_input_map(attr_map)

    def set_input_attr_sparse(self, name: str, value: bool) -> None:
        """Set the ``sparse`` read flag on a user input ARRAY attr.

        ``sparse=True`` makes the expression read only the connected/set
        elements compactly; ``False`` (default) reads a dense, gap-filled
        array. Pure metadata edit -- the Maya plug is untouched."""
        attr_map = self._read_input_map()
        if name not in attr_map:
            raise ValueError(f"input attr {name!r} not found")
        meta = dict(attr_map[name])
        if not meta.get("is_array"):
            raise ValueError(f"sparse applies to array attrs only ({name!r})")
        if value:
            meta["sparse"] = True
        else:
            meta.pop("sparse", None)
        attr_map[name] = meta
        self._write_input_map(attr_map)

    def set_output_attr_color(self, name: str, hex_color: str | None) -> None:
        """Set (or clear, if hex_color is None) the UI color for an output."""
        attr_map = self._read_output_map()
        if name not in attr_map:
            raise ValueError(f"output attr {name!r} not found")
        meta = dict(attr_map[name])
        if hex_color is None:
            meta.pop("ui_color", None)
        else:
            meta["ui_color"] = hex_color
        attr_map[name] = meta
        self._write_output_map(attr_map)

    def get_input_attr_color(self, name: str) -> str | None:
        meta = self._read_input_map().get(name) or {}
        return meta.get("ui_color")

    def get_output_attr_color(self, name: str) -> str | None:
        meta = self._read_output_map().get(name) or {}
        return meta.get("ui_color")

    def get_all_attr_colors(self) -> dict:
        """Return {attr_name: hex_color} for every user attr (input +
        output) that has a custom UI color set."""
        out: dict = {}
        for name, meta in (self._read_input_map() or {}).items():
            color = (meta or {}).get("ui_color")
            if color:
                out[name] = color
        for name, meta in (self._read_output_map() or {}).items():
            color = (meta or {}).get("ui_color")
            if color:
                out[name] = color
        return out

    # ------------------------------------------------------------------
    # Stored variables
    # ------------------------------------------------------------------

    def get_variable_names(self) -> list[str]:
        """Return the list of variable names declared as persistent."""
        try:
            raw = mc.getAttr(self._name + "._storedVarNames") or ""
        except Exception:
            return []
        if not raw or raw == "None":
            return []
        return [n.strip() for n in raw.split(",") if n.strip()]

    def add_variable(self, name: str, value=None, persistent: bool = True) -> None:
        """Declare a new variable.

        With ``persistent=True`` (default) the name is registered in
        ``_storedVarNames`` so the value is flushed to ``_storedVarsData``
        on scene save/export (see :mod:`mpynode._common.storedvars.stored_var_store`);
        with ``persistent=False`` it is live for the session only.
        """
        from mpynode._common.storedvars import stored_vars_api

        stored_vars_api.add_variable(self._name, name, value, persistent)

    def remove_variable(self, name: str) -> None:
        from mpynode._common.storedvars import stored_vars_api

        stored_vars_api.remove_variable(self._name, name)

    def set_variable(self, name: str, value,
                     persistent: bool | None = None) -> None:
        """Update a single variable's value (creates it if missing).

        ``persistent`` controls scene-save membership. Default ``None``
        leaves it alone: an existing var keeps its Persistent/Temporary
        status, a new one is session-only. Pass True/False to set it."""
        from mpynode._common.storedvars import stored_vars_api

        stored_vars_api.set_variable(self._name, name, value, persistent)

    def rename_variable(self, old_name: str, new_name: str) -> None:
        """Rename a stored var, preserving its current value."""
        from mpynode._common.storedvars import stored_vars_api

        stored_vars_api.rename_variable(self._name, old_name, new_name)

    def get_variables(self) -> dict:
        """Return the current persistent dict (from the deferred store)."""
        from mpynode._common.storedvars import stored_vars_api

        return stored_vars_api.get_variables(self._name)

    def set_variable_persistent(self, name: str, persistent: bool) -> None:
        """Toggle whether ``name`` is saved with the scene (its
        ``_storedVarNames`` membership). The live value is untouched."""
        from mpynode._common.storedvars import stored_vars_api

        stored_vars_api.set_variable_persistent(self._name, name, persistent)

    def is_variable_persistent(self, name: str) -> bool:
        """True if ``name`` is saved with the scene."""
        from mpynode._common.storedvars import stored_vars_api

        return stored_vars_api.is_variable_persistent(self._name, name)

    def set_variables(self, data: dict) -> None:
        """Replace the persistent dict (and the names list to match)."""
        from mpynode._common.storedvars import stored_vars_api

        stored_vars_api.set_variables(self._name, data)

    def clear_variables(self) -> None:
        from mpynode._common.storedvars import stored_vars_api

        stored_vars_api.clear_variables(self._name)

    # ------------------------------------------------------------------
    # Profile + Watch instrumentation (read-only)
    # ------------------------------------------------------------------

    def is_profile_enabled(self) -> bool:
        """True if the cheap timing stats toggle is on."""
        try:
            return bool(mc.getAttr(self._name + ".profile_enabled"))
        except Exception:
            return False

    def is_deep_profile_enabled(self) -> bool:
        """True if the cProfile drill-down toggle is on (only effective
        when profile_enabled is also on)."""
        try:
            return bool(mc.getAttr(self._name + ".deep_profile_enabled"))
        except Exception:
            return False

    def is_watch_enabled(self) -> bool:
        """True if the watch capture toggle is on."""
        try:
            return bool(mc.getAttr(self._name + ".watch_enabled"))
        except Exception:
            return False

    def get_profile_snapshot(self) -> dict | None:
        """Return the latest profile snapshot dict (or None if not present).

        Shape: ``{last_us, avg_us, min_us, max_us, count, deep_table?}``
        ``deep_table`` is a list of cProfile rows when deep_profile is on.
        """
        from mpynode._common.instrumentation import read_profile_snapshot

        return read_profile_snapshot(self._name)

    def get_watch_vars(self) -> dict | None:
        """Return the latest watch vars dict (or None if not present)."""
        from mpynode._common.instrumentation import read_watch_vars

        return read_watch_vars(self._name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_input_map(self) -> dict:
        try:
            raw = mc.getAttr(self._name + "._inputAttrs") or ""
        except Exception:
            return {}
        try:
            return decode_attr_map(raw) if raw else {}
        except Exception:
            return {}

    def _write_input_map(self, attr_map: dict) -> None:
        mc.setAttr(
            self._name + "._inputAttrs", encode_attr_map(attr_map), type="string"
        )
        _invalidate_plug_governance()

    def _read_output_map(self) -> dict:
        try:
            raw = mc.getAttr(self._name + "._outputAttrs") or ""
        except Exception:
            return {}
        try:
            return decode_attr_map(raw) if raw else {}
        except Exception:
            return {}

    def _write_output_map(self, attr_map: dict) -> None:
        mc.setAttr(
            self._name + "._outputAttrs", encode_attr_map(attr_map), type="string"
        )
        _invalidate_plug_governance()

    # ------------------------------------------------------------------
    # User-attr ORDER preservation
    #
    # Maya appends dynamic attrs in creation order, but the JSON attr map is
    # stored ``sort_keys=True`` (deterministic .ma diffs), so its KEY order is
    # alphabetical. The authored sequence is carried in a per-attr ``order`` int
    # and sorted by on read. Maps saved before ``order`` existed fall back to
    # Maya's creation order (``listAttr(userDefined=True)``). ``order`` rides
    # INSIDE each meta, so sort_keys stays on.
    # ------------------------------------------------------------------

    def _dg_attr_index(self) -> dict:
        """Map user-attr name -> its position in Maya's creation order."""
        index: dict = {}
        try:
            for i, a in enumerate(mc.listAttr(self._name, userDefined=True) or []):
                index.setdefault(a, i)
        except Exception:
            pass
        return index

    def _next_order_value(self, attr_map: dict) -> int:
        """Order value for a new attr appended to ``attr_map`` (sorts last).

        Backfills ``order`` onto any existing legacy entries (from Maya's
        creation order) first, so a freshly added attr always lands after the
        ones already present -- even on a map that predates order-preservation.
        Mutates the metas in ``attr_map`` (the caller writes them back)."""
        if any("order" not in m for m in attr_map.values()):
            dg = self._dg_attr_index()
            ordered = sorted(
                attr_map.items(),
                key=lambda kv: (dg.get(kv[0], 1_000_000), kv[0]),
            )
            for i, (_n, m) in enumerate(ordered):
                m["order"] = i
        return max((m.get("order", -1) for m in attr_map.values()), default=-1) + 1

    def _ordered_attr_map(self, attr_map: dict) -> dict:
        """Return ``attr_map`` sorted by each entry's ``order`` field.

        Entries lacking ``order`` (legacy maps) fall back to Maya's creation
        order, then name. Every returned meta carries a contiguous ``order``
        int so serialization / codegen persist the sequence. The result is a
        fresh dict of fresh metas; the stored plug is untouched."""
        if not attr_map:
            return dict(attr_map)
        dg = self._dg_attr_index() if any(
            "order" not in m for m in attr_map.values()) else {}

        def _key(item):
            name, meta = item
            o = meta.get("order")
            if o is not None:
                return (0, o, name)
            return (1, dg.get(name, 1_000_000), name)

        out: dict = {}
        for i, (name, meta) in enumerate(sorted(attr_map.items(), key=_key)):
            m = dict(meta)
            m["order"] = i
            out[name] = m
        return out

    # ------------------------------------------------------------------
    # User-attr REORDER (plug-level)
    #
    # Maya has no "move attribute" command, so reordering is DESTRUCTIVE:
    # snapshot every user attr's value + in/out connections, deleteAttr them
    # all, re-add in the new order (re-stamping ``order``), then restore values
    # + reconnect. The Channel Box / Node Editor follow because the plugs are
    # physically recreated in sequence. Callers run this in a single undo chunk
    # (``_ReorderAttrCommand``) and gate it to the timeline being idle.
    # ------------------------------------------------------------------

    def reorder_input_attrs(self, new_order) -> None:
        """Reorder user INPUT attrs to ``new_order`` (a permutation of the
        existing input attr names). Preserves values + connections."""
        self._reorder_attrs(list(new_order), "input")

    def reorder_output_attrs(self, new_order) -> None:
        """Reorder user OUTPUT attrs to ``new_order``. Preserves connections."""
        self._reorder_attrs(list(new_order), "output")

    def _reorder_attrs(self, new_order: list, direction: str) -> None:
        if direction == "input":
            read, write = self._read_input_map, self._write_input_map
            adder, color_setter = self.add_input_attr, self.set_input_attr_color
        else:
            read, write = self._read_output_map, self._write_output_map
            adder, color_setter = self.add_output_attr, self.set_output_attr_color
        attr_map = read()
        if set(new_order) != set(attr_map):
            raise ValueError(
                "reorder list must be a permutation of the existing %s attrs; "
                "got %r vs %r" % (direction, sorted(new_order), sorted(attr_map))
            )
        if list(self._ordered_attr_map(attr_map).keys()) == list(new_order):
            return  # already in this order -- nothing to do
        node = self._name

        # The destructive rebuild momentarily empties this direction's schema
        # map (write({}) below), so an EM/viewport eager-pull mid-edit would
        # fire the expression against missing attrs -- the same benign,
        # self-correcting transient scene-open produces. Mark an attr-surgery
        # window so that error is suppressed for the duration; the window
        # auto-expires and finally guarantees it closes.
        from mpynode._common.lifecycle import scene_state as scene_io
        scene_io.begin_attr_surgery()
        try:
            # 1. Snapshot value + connections (both directions) for every attr.
            snaps = {nm: self._snapshot_attr_for_reorder(node, nm, attr_map[nm])
                     for nm in attr_map}

            # 2. Delete every user attr of this direction (compound/array
            #    children cascade with their parent).
            for nm in list(attr_map):
                try:
                    mc.deleteAttr(node + "." + nm)
                except Exception:
                    pass

            # 3. Reset the stored map (so ``order`` re-stamps 0..n-1 in the new
            #    sequence) and re-add in the requested order.
            write({})
            for nm in new_order:
                self._readd_attr_for_reorder(adder, nm, attr_map[nm])
                col = (attr_map[nm] or {}).get("ui_color")
                if col:
                    try:
                        color_setter(nm, col)
                    except Exception:
                        pass

            # 4. Restore values, then reconnect.
            for nm in new_order:
                self._restore_attr_for_reorder(node, nm, snaps[nm])
        finally:
            scene_io.end_attr_surgery()

        _invalidate_affects()

    def _snapshot_attr_for_reorder(self, node: str, name: str, meta: dict) -> dict:
        snap = {"in": [], "out": [], "value": None, "matrix": False}
        # Query the parent plug AND every compound child: a compound can be
        # wired per-child (``vecX <- someFloat``), which a parent-only query
        # misses. The ``connections=True`` pair form yields element plugs for
        # multis. Dedup because a parent query can surface child pairs too.
        plugs = [node + "." + name]
        for axis in (_COMPOUND_CHILD_AXES.get(meta.get("attr_type")) or []):
            plugs.append(node + "." + name + axis)
        seen_in, seen_out = set(), set()
        for plug in plugs:
            pin = mc.listConnections(plug, source=True, destination=False,
                                     plugs=True, connections=True) or []
            for i in range(0, len(pin) - 1, 2):
                pair = (pin[i + 1], pin[i])           # (src, thisPlug)
                if pair not in seen_in:
                    seen_in.add(pair)
                    snap["in"].append(pair)
            pout = mc.listConnections(plug, source=False, destination=True,
                                      plugs=True, connections=True) or []
            for i in range(0, len(pout) - 1, 2):
                pair = (pout[i], pout[i + 1])          # (thisPlug, dst)
                if pair not in seen_out:
                    seen_out.add(pair)
                    snap["out"].append(pair)
        # Value (best-effort) for a NON-array, NON-time attr with NO incoming
        # connection -- a connected/driven plug restores via the connection, and
        # ``time`` is re-auto-connected to time1 on re-add.
        attr_type = meta.get("attr_type")
        if (not meta.get("is_array") and attr_type != "time" and not snap["in"]):
            try:
                snap["value"] = mc.getAttr(node + "." + name)
                snap["matrix"] = (attr_type == "matrix")
            except Exception:
                snap["value"] = None
        return snap

    def _readd_attr_for_reorder(self, adder, name: str, meta: dict) -> None:
        attr_type = meta.get("attr_type", "float")
        is_array = bool(meta.get("is_array", False))
        enum_names = meta.get("enum_names")
        kw = {
            "min_value": meta.get("min_value"),
            "max_value": meta.get("max_value"),
            "default_value": meta.get("default_value"),
        }
        if adder is self.add_input_attr and is_array and meta.get("sparse"):
            kw["sparse"] = True
        # Packed is the plug KIND, so a reorder/re-add MUST carry it or the
        # attribute silently comes back as a numeric multi.
        if adder is self.add_input_attr and is_array and meta.get("packed"):
            kw["packed"] = True
        try:
            adder(name, attr_type, is_array, enum_names=enum_names, **kw)
        except TypeError:
            try:
                adder(name, attr_type, is_array, enum_names=enum_names)
            except TypeError:
                adder(name, attr_type, is_array)

    def _restore_attr_for_reorder(self, node: str, name: str, snap: dict) -> None:
        plug = node + "." + name
        if snap.get("value") is not None and not snap.get("in"):
            try:
                self._set_plug_value(plug, snap["value"], snap.get("matrix"))
            except Exception:
                pass
        for src, this_plug in snap.get("in", []):
            try:
                mc.connectAttr(src, this_plug, force=True)
            except Exception:
                pass
        for this_plug, dst in snap.get("out", []):
            try:
                mc.connectAttr(this_plug, dst, force=True)
            except Exception:
                pass

    @staticmethod
    def _set_plug_value(plug: str, value, is_matrix: bool) -> None:
        if is_matrix:
            mc.setAttr(plug, *value, type="matrix")
            return
        # getAttr on a compound (vector/euler/quaternion/color) returns a
        # single-tuple list like [(x, y, z)]; unwrap it to positional args.
        if (isinstance(value, (list, tuple)) and len(value) == 1
                and isinstance(value[0], (list, tuple))):
            mc.setAttr(plug, *value[0])
        elif isinstance(value, (list, tuple)):
            mc.setAttr(plug, *value)
        else:
            mc.setAttr(plug, value)
