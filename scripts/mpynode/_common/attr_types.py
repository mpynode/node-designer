"""The attribute type table: the one place an mPyNode attr type is declared.

Every list of attr types is derived from :data:`ATTR_TYPES`:

* the wrapper's ``cmds.addAttr`` kwargs and its accepted names
  (``wrappers._mpy_node._ADD_ATTR_KIND`` / ``VALID_INPUT_TYPES`` /
  ``VALID_OUTPUT_TYPES``);
* the Add Attribute dialog's families and labels
  (``ui.dialogs.add_attr._ATTR_TYPE_GROUPS`` / ``ALL_ATTR_TYPES``);
* the assistant's tool enum and its prompt lists (``ui.llm.tools._ATTR_TYPES``,
  ``ui.llm.system_prompt``).

The table is in dialog order, so ``double`` -- Maya's own "Float" -- comes
first everywhere a list is shown. A stored name is Maya's attribute type for
the plug when that type alone describes it (``double``, ``long``,
``doubleAngle``, ``matrix``, ``float2``, and ``double3`` with plain double
children). ``euler``, ``color``, ``hex`` and ``python`` are our own words:
Maya tells those apart only by their child type or a flag, or has no type for
them. ``quaternion`` is our word for Maya's ``double4``.

Retired names are rejected, never aliased: :data:`RETIRED` maps each one to
its replacement so the error can say what to type instead.

This module imports nothing from Maya itself, but importing it through the
``mpynode._common`` package does (the package ``__init__`` needs Maya).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AttrType:
    """One attr type.

    ``add_attr`` is the ``cmds.addAttr`` kwargs for the parent plug; compound
    children are added by the wrapper. ``group`` is the Add Attribute dialog
    family (None when the dialog does not offer the type). ``in_dialog`` and
    ``in_assistant`` say whether the dialog offers it and whether the
    assistant may create it.
    """

    name:         str
    add_attr:     dict = field(default_factory=dict)
    label:        str = ""
    group:        int | None = None
    in_dialog:    bool = True
    in_assistant: bool = True


ATTR_TYPES: tuple[AttrType, ...] = (
    # -- numbers
    AttrType("double", {"at": "double"},
             "64-bit real (Maya's Float)", 0),
    AttrType("float", {"at": "float"},
             "32-bit real", 0),
    AttrType("long", {"at": "long"},
             "integer", 0),
    AttrType("bool", {"at": "bool"},
             "on / off", 0),
    AttrType("doubleAngle", {"at": "doubleAngle"},
             "angle, code reads radians", 0),
    # -- compounds and matrices
    AttrType("double3", {"at": "double3"},
             "3 doubles, no unit (Maya's Vector)", 1),
    # parent compound; the X/Y/Z children are doubleAngle.
    AttrType("euler", {"at": "double3"},
             "3 angles like rotate, radians", 1),
    # Maya's numeric matrix (kMatrixAttribute, like multMatrix.matrixIn):
    # reads as identity until set. Scenes saved before 2026-10 carry a typed
    # ``-dt matrix`` plug instead; readers take both, and every compute write
    # picks its call from the plug's actual kind (the wrong one crashes Maya).
    AttrType("matrix", {"at": "matrix"},
             "4x4 doubles", 1),
    # Maya's numeric double4 (like decomposeMatrix.outputQuat) with 4 explicit
    # double children X/Y/Z/W, added by the wrapper; W defaults to 1, so it
    # reads as the identity [0,0,0,1]. Connects both ways with a generic
    # compound of 4 (eulerToQuat.outputQuat).
    AttrType("quaternion", {"at": "double4"},
             "double4 X/Y/Z/W", 1),
    # 3-float RENDERABLE colour (R/G/B children + usedAsColor) so it binds to
    # material.color / Arnold like a stock file node's outColor.
    AttrType("color", {"at": "float3", "usedAsColor": True},
             "float3 used as colour", 1),
    # 2-float compound (U/V), e.g. a uvCoord pair. Like color, the 2 children
    # must be added explicitly (cmds does NOT auto-create them).
    AttrType("float2", {"at": "float2"},
             "2 floats U/V", 1),
    # -- text and data
    AttrType("string", {"dt": "string"},
             "text", 2),
    # enumName is supplied per instance by the wrapper.
    AttrType("enum", {"at": "enum"},
             "named choices, stored as an index", 2),
    # hex = string with a UTF-8-hex wrap (write plain text -> "48 69 ..."; read
    # decodes back), which drives Maya's ``type`` node textInput.
    AttrType("hex", {"dt": "string"},
             "text stored as UTF-8 hex", 2),
    # python = string with a pickle/base64 wrap.
    AttrType("python", {"dt": "string"},
             "any picklable object, not compilable", 2),
    # -- geometry (typed plugs)
    AttrType("mesh", {"dt": "mesh"},
             "polygon mesh", 3),
    AttrType("nurbsCurve", {"dt": "nurbsCurve"},
             "NURBS curve", 3),
    AttrType("nurbsSurface", {"dt": "nurbsSurface"},
             "NURBS surface", 3),
    # -- time: a single time value, auto-connectable to time1.
    AttrType("time", {"at": "time"},
             "scene time, e.g. frames", 4),
)

BY_NAME: dict[str, AttrType] = {t.name: t for t in ATTR_TYPES}

# Every accepted name, in table order.
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

# Retired name -> its replacement. Rejected everywhere; the replacement is
# only used to word the error. Also the v1 scene vocabulary map: v1 names are
# a subset of the old v2 names.
RETIRED: dict[str, str] = {
    "int":     "long",
    "vector":  "double3",
    "angle":   "doubleAngle",
    "double4": "quaternion",
    "float3":  "color",
}


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
    """The error text for a name that is not in the table.

    A retired name gets its replacement; anything else gets the valid names.
    """
    new = RETIRED.get(attr_type) if isinstance(attr_type, str) else None
    if new is not None:
        return "attr_type %r was renamed: use %r" % (attr_type, new)
    return "attr_type %r not supported; valid: %s" % (
        attr_type, sorted(ALL_NAMES))


def upgrade_legacy_name(attr_type):
    """Map a v1 scene's type name to today's name; other values pass through.

    Only for reading v1 data, whose vocabulary predates the renames. Never use
    it to accept a retired name from v2 code or files.
    """
    if isinstance(attr_type, str):
        return RETIRED.get(attr_type, attr_type)
    return attr_type
