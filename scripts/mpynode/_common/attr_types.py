"""The attribute type table: the one place an mPyNode attr type is declared.

Every list of attr types is derived from :data:`ATTR_TYPES`:

* the wrapper's ``cmds.addAttr`` kwargs and its accepted names
  (``wrappers._mpy_node._ADD_ATTR_KIND`` / ``VALID_INPUT_TYPES`` /
  ``VALID_OUTPUT_TYPES``);
* the Add Attribute dialog's families and labels
  (``ui.dialogs.add_attr._ATTR_TYPE_GROUPS`` / ``ALL_ATTR_TYPES``);
* the assistant's tool enum and its prompt lists (``ui.llm.tools._ATTR_TYPES``,
  ``ui.llm.system_prompt``).

Every type has two names and stores one:

* the STORED name (``AttrType.name``) is what files, scene attr maps, the
  get-APIs and errors carry. It is Maya's attribute type for the plug when
  that type alone describes it (``double``, ``long``, ``doubleAngle``,
  ``doubleLinear``, ``matrix``, ``float2``, and ``double3`` with plain double
  children). ``euler``, ``position``, ``quaternion``, ``color``, ``hex`` and
  ``pickle`` are our own words: Maya tells those apart only by their child
  type or a flag, or has no type for them.
* the ARTIST name (``AttrType.artist``) is the dropdown's word for it
  (``float64``, ``int``, ``angle``, ``vector`` ...), with
  ``AttrType.description`` beside it.

A name a user types may be either: :func:`canonical` translates an alias
(:data:`ALIASES` -- every artist name that differs from its stored name, plus
Maya's own ``double4`` / ``float3`` for ``quaternion`` / ``color``) to the
stored name at every input point. :data:`RETIRED` names are rejected with the
replacement in the error.

The table is in dialog order, so ``double`` -- Maya's own "Float" -- comes
first everywhere a list is shown.

The unit types read and write Maya's INTERNAL units, whatever the scene's UI
units: ``doubleAngle`` / ``euler`` in radians, ``doubleLinear`` / ``position``
in centimetres (at linear unit m, a translate of 1.5 reads 150.0).

This module imports nothing from Maya itself, but importing it through the
``mpynode._common`` package does (the package ``__init__`` needs Maya).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AttrType:
    """One attr type.

    ``name`` is the stored name. ``add_attr`` is the ``cmds.addAttr`` kwargs
    for the parent plug; compound children are added by the wrapper.
    ``group`` is the Add Attribute dialog family (None when the dialog does
    not offer the type). ``in_dialog`` and ``in_assistant`` say whether the
    dialog offers it and whether the assistant may create it. ``artist`` is
    the dropdown's name for the type and ``description`` the dropdown's right
    column.
    """

    name:         str
    add_attr:     dict = field(default_factory=dict)
    label:        str = ""
    group:        int | None = None
    in_dialog:    bool = True
    in_assistant: bool = True
    artist:       str = ""
    description:  str = ""


ATTR_TYPES: tuple[AttrType, ...] = (
    # -- numbers
    AttrType("double", {"at": "double"},
             "64-bit real (Maya's Float)", 0,
             artist="float64",
             description="double (64-bit)"),
    AttrType("float", {"at": "float"},
             "32-bit real", 0,
             artist="float32",
             description="float (32-bit)"),
    AttrType("long", {"at": "long"},
             "integer", 0,
             artist="int",
             description="long"),
    AttrType("bool", {"at": "bool"},
             "on / off", 0,
             artist="bool",
             description="bool (on / off)"),
    AttrType("doubleAngle", {"at": "doubleAngle"},
             "angle, code reads radians", 0,
             artist="angle",
             description="doubleAngle (radians)"),
    # Maya's distance (like translateX): connects to translate channels with
    # no unitConversion node, and the code reads internal centimetres.
    AttrType("doubleLinear", {"at": "doubleLinear"},
             "distance, code reads cm", 0,
             artist="distance",
             description="doubleLinear (cm)"),
    # -- compounds and matrices
    AttrType("double3", {"at": "double3"},
             "3 doubles, no unit (Maya's Vector)", 1,
             artist="vector",
             description="double3 (no unit)"),
    # parent compound; the X/Y/Z children are doubleAngle.
    AttrType("euler", {"at": "double3"},
             "3 angles like rotate, radians", 1,
             artist="euler",
             description="double3 of doubleAngle (radians)"),
    # parent compound; the X/Y/Z children are doubleLinear, like translate, so
    # it wires to and from translate with no unitConversion node at any unit.
    AttrType("position", {"at": "double3"},
             "3 distances like translate, cm", 1,
             artist="position",
             description="double3 of doubleLinear (cm)"),
    # Maya's numeric matrix (kMatrixAttribute, like multMatrix.matrixIn):
    # reads as identity until set. Scenes saved before 2026-10 carry a typed
    # ``-dt matrix`` plug instead; readers take both, and every compute write
    # picks its call from the plug's actual kind (the wrong one crashes Maya).
    AttrType("matrix", {"at": "matrix"},
             "4x4 doubles", 1,
             artist="matrix",
             description="matrix (4x4 doubles)"),
    # Maya's numeric double4 (like decomposeMatrix.outputQuat) with 4 explicit
    # double children X/Y/Z/W, added by the wrapper; W defaults to 1, so it
    # reads as the identity [0,0,0,1]. Connects both ways with a generic
    # compound of 4 (eulerToQuat.outputQuat).
    AttrType("quaternion", {"at": "double4"},
             "double4 X/Y/Z/W", 1,
             artist="quaternion",
             description="double4 (X/Y/Z/W)"),
    # 3-float RENDERABLE colour (R/G/B children + usedAsColor) so it binds to
    # material.color / Arnold like a stock file node's outColor.
    AttrType("color", {"at": "float3", "usedAsColor": True},
             "float3 used as colour", 1,
             artist="color",
             description="float3 (colour)"),
    # 2-float compound (U/V), e.g. a uvCoord pair. Like color, the 2 children
    # must be added explicitly (cmds does NOT auto-create them).
    AttrType("float2", {"at": "float2"},
             "2 floats U/V", 1,
             artist="uv",
             description="float2 (U/V)"),
    # -- text and data
    AttrType("string", {"dt": "string"},
             "text", 2,
             artist="string",
             description="string (text)"),
    # enumName is supplied per instance by the wrapper.
    AttrType("enum", {"at": "enum"},
             "named choices, stored as an index", 2,
             artist="enum",
             description="enum (named choices, default False/True)"),
    # hex = string with a UTF-8-hex wrap (write plain text -> "48 69 ..."; read
    # decodes back), which drives Maya's ``type`` node textInput.
    AttrType("hex", {"dt": "string"},
             "text stored as UTF-8 hex", 2,
             artist="hex",
             description="string (stored as UTF-8 hex)"),
    # pickle = string with a pickle/base64 wrap.
    AttrType("pickle", {"dt": "string"},
             "any picklable object, not compilable", 2,
             artist="pickle",
             description="string (pickled data, C++ unsupported)"),
    # -- geometry (typed plugs)
    AttrType("mesh", {"dt": "mesh"},
             "polygon mesh", 3,
             artist="mesh",
             description="mesh (code gets a Mesh object)"),
    AttrType("nurbsCurve", {"dt": "nurbsCurve"},
             "NURBS curve", 3,
             artist="nurbsCurve",
             description="nurbsCurve (code gets a NurbsCurve object)"),
    AttrType("nurbsSurface", {"dt": "nurbsSurface"},
             "NURBS surface", 3,
             artist="nurbsSurface",
             description="nurbsSurface (code gets a NurbsSurface object)"),
    # -- time: a single time value, auto-connectable to time1.
    AttrType("time", {"at": "time"},
             "scene time, e.g. frames", 4,
             artist="time",
             description="time (frames)"),
)

BY_NAME: dict[str, AttrType] = {t.name: t for t in ATTR_TYPES}

# Every stored name, in table order (the aliases are :data:`ALIASES`).
ALL_NAMES: tuple[str, ...] = tuple(BY_NAME)

# The dialog's families, in table order; the flattened tuple is the dialog's
# order and membership.
DIALOG_GROUPS: tuple[tuple[str, ...], ...] = tuple(
    tuple(t.name for t in ATTR_TYPES if t.in_dialog and t.group == g)
    for g in sorted({t.group for t in ATTR_TYPES if t.in_dialog})
)
DIALOG_NAMES: tuple[str, ...] = tuple(n for g in DIALOG_GROUPS for n in g)

# The type the dialog pre-selects when nothing was picked this session.
DIALOG_DEFAULT = "double"

# What the assistant may create, in the dialog's order.
ASSISTANT_NAMES: tuple[str, ...] = tuple(
    t.name for t in ATTR_TYPES if t.in_assistant)

# Alias -> stored name: every name a user may type that is not a stored name.
# Each artist name that differs from its stored name, plus Maya's own name for
# a plug whose stored name is ours (the ``-at`` that is not itself a stored
# name: ``double4`` -> ``quaternion``, ``float3`` -> ``color``).
ALIASES: dict[str, str] = {
    t.artist: t.name for t in ATTR_TYPES if t.artist != t.name}
ALIASES.update(
    (t.add_attr["at"], t.name) for t in ATTR_TYPES
    if "at" in t.add_attr and t.add_attr["at"] not in BY_NAME)

# Retired name -> its replacement. Rejected everywhere a name is typed; the
# replacement is only used to word the error. Also mapped for v1 data
# (:func:`upgrade_legacy_name`).
RETIRED: dict[str, str] = {"python": "pickle"}


def add_attr_kwargs() -> dict[str, dict]:
    """``{name: cmds.addAttr kwargs}`` for every accepted type (fresh dicts)."""
    return {t.name: dict(t.add_attr) for t in ATTR_TYPES}


def dialog_label(name: str) -> str:
    """The Add Attribute combo text for ``name``: ``"<name>  -  <label>"``."""
    t = BY_NAME.get(name)
    if t is None or not t.label:
        return name
    return "%s  -  %s" % (name, t.label)


def unknown_type_message(attr_type) -> str:
    """The error text for a name that is neither stored nor an alias.

    A retired name gets its replacement; anything else gets the stored names
    and the aliases.
    """
    new = RETIRED.get(attr_type) if isinstance(attr_type, str) else None
    if new is not None:
        return "attr_type %r was renamed: use %r" % (attr_type, new)
    return "attr_type %r not supported; valid: %s; aliases: %s" % (
        attr_type, sorted(ALL_NAMES),
        ", ".join("%r -> %r" % kv for kv in sorted(ALIASES.items())))


def canonical(attr_type) -> str:
    """The stored name for ``attr_type``: a stored name is returned as is, an
    alias as the name it stands for. Anything else raises ``ValueError`` with
    :func:`unknown_type_message`.
    """
    if isinstance(attr_type, str):
        if attr_type in BY_NAME:
            return attr_type
        stored = ALIASES.get(attr_type)
        if stored is not None:
            return stored
    raise ValueError(unknown_type_message(attr_type))


def stored_name(attr_type):
    """:func:`canonical` that never raises, for reading stored data: an alias
    becomes its stored name; anything else (a stored name, a retired or
    unknown name, a non-string) comes back unchanged for the caller to judge.
    """
    if isinstance(attr_type, str):
        return ALIASES.get(attr_type, attr_type)
    return attr_type


def upgrade_legacy_name(attr_type):
    """Map a v1 scene's type name to today's stored name; other values pass
    through.

    Only for reading v1 data, whose vocabulary predates the renames: it maps
    through :data:`ALIASES` and :data:`RETIRED` (``int`` -> ``long``,
    ``vector`` -> ``double3``, ``angle`` -> ``doubleAngle``, ``python`` ->
    ``pickle``). Never use it to accept a retired name from v2 code or files.
    """
    if isinstance(attr_type, str):
        attr_type = ALIASES.get(attr_type, attr_type)
        return RETIRED.get(attr_type, attr_type)
    return attr_type
