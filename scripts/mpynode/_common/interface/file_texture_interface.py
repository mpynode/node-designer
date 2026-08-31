"""Single declarative source of truth for the mPyFile texture preset interface.

The mPyFile preset attrs (fileName/uvCoord/colorSpace/.../outColor/outAlpha) are a
FIXED contract. They were previously declared in FIVE places kept in sync only by a
drift-guard test:

  1. ``_api2/mpy_file.py`` ``MPyFile.initializer()`` -- the imperative MFn build.
  2. ``_api2/mpy_file.py`` ``_COLOR_SPACE_NAMES`` -- the 25 colorSpace labels.
  3. ``native/spec/spec_extractor.py`` ``_MPYFILE_PRESET_META`` -- a pinned raw-meta table.
  4. a best-effort transient ``createNode("mPyFile")`` + ``attributeQuery`` capture --
     which flakily returned EMPTY in a batch build and silently stripped the interface
     (the 2026-07-19 mega drop: fileTexture/scanlineTex/brightContrastTex dropped).
  5. the triplicated ``k*`` enum int constants (mpy_file.py, _defaults/file_defaults.py,
     and the C++ mirror in native/compiler/kernels/file_texture_cpp.py).

This module OWNS the interface as data. ``MPyFile.initializer()`` BUILDS the Maya attrs
from it; the porter PROJECTS it to the raw-meta the spec system needs (no ``createNode``,
no snapshot). One source -> the flaky capture and the drift-guard maintenance are retired.

Pure Python: this module MUST NOT import maya (it lives in the Maya-free ``_common``
package so the headless porter/.mpn path can read it). The live api2 node interprets the
``attr_type``/``data``/``flags`` tokens into ``om.MFn*`` calls; the porter reads only the
``attr_type``/``direction``/``enum`` fields.
"""

from __future__ import annotations

# --- enum int constants (the SINGLE copy; mpy_file.py + file_defaults.py import these) ---
kFilterPoint = 0
kFilterLinear = 1
kFilterAnisotropic = 2

kMipmapNone = 0
kMipmapAuto = 1

kWrapWrap = 0
kWrapClamp = 1
kWrapMirror = 2
kWrapBorder = 3

kPreFilterBox = 0
kPreFilterQuadratic = 1
kPreFilterQuartic = 2
kPreFilterGaussian = 3

# --- colorSpace enum labels (in-repo contract, NOT OCIO-config-derived, so portable/
#     deterministic; index 0 = default; scene-saved integer indices round-trip). ---
COLOR_SPACE_NAMES = (
    "[Texture] sRGB Encoded Rec.709 (sRGB)",  # 0 (default)
    "[Texture] Gamma 1.8 Encoded Rec.709",  # 1
    "[Texture] Gamma 2.2 Encoded Rec.709",  # 2
    "[Texture] Gamma 2.4 Encoded Rec.709",  # 3
    "[Texture] sRGB Encoded AP1",  # 4
    "[Texture] Gamma 2.2 Encoded AP1",  # 5
    "[Texture] sRGB Encoded P3-D65",  # 6
    "[Texture] Gamma 2.2 Encoded AdobeRGB",  # 7
    "[Scene-linear] scene-linear Rec.709-sRGB",  # 8 (identity)
    "[Scene-linear] ACEScg",  # 9
    "[Scene-linear] ACES2065-1",  # 10
    "[Scene-linear] scene-linear DCI-P3 D65",  # 11
    "[Scene-linear] scene-linear AdobeRGB",  # 12
    "[Scene-linear] scene-linear Rec.2020",  # 13
    "[Display] sRGB",  # 14
    "[Display] Gamma 2.2 / Rec.709",  # 15
    "[Display] Rec.1886 / Rec.709 video",  # 16
    "[Display] AdobeRGB",  # 17
    "[Display] DCI-P3 D65",  # 18
    "[Utility] Raw",  # 19
    "[Log] ACEScct",  # 20
    "[Log] ARRI LogC v3 EI800 / AlexaWideGamut",  # 21
    "[Log] RED Log3G10 / REDWideGamutRGB",  # 22
    "[Log] Sony SLog3 / SGamut3",  # 23
    "[Log] Log film scan (ADX10)",  # 24
)


def _cs_enum():
    return [(name, i) for i, name in enumerate(COLOR_SPACE_NAMES)]


# --- the ordered rich descriptor table -------------------------------------------------
# ORDER IS LOAD-BEARING: Maya 2026's 2dTextureSwatchGen iterates attributes in
# declaration order and uses the first INPUT plug as a "what kind of texture" hint --
# fileName MUST be first (matches customFileTexture) or Hypershade swatches degrade to a
# single sample. This list is the exact declaration order of ``MPyFile.initializer()``.
#
# Per entry:
#   long/short   -- Maya long + short attr names.
#   attr_type    -- native spec type (drives both the porter projection and the MFn build):
#                   string | float2 | color | enum | bool | int | float.
#   direction    -- "input" (writable) or "output" (writable=False). Drives porter routing.
#   default      -- default value (index for enum). initializer only.
#   min/max      -- explicit numeric limits (initializer nAttr.setMin/setMax only). Present
#                   ONLY where the imperative code set them; NOT projected to the porter.
#   enum         -- ordered [(label, index)] for enum attrs. label order == listEnum order.
#   children     -- for float2/color compounds: [{long,short,data,default,flags}], created
#                   before the parent (MFn mutates the last-created attr, so per-child flags
#                   are applied right after each child -- e.g. uvCoord children are keyable
#                   while the parent is not).
#   flags        -- parent/scalar flag dict, applied in insertion order after create:
#                   keyable/storable/hidden/writable/readable/used_as_color/used_as_filename.
#   affects_output -- participates in attributeAffects(-> outColor children + outAlpha).
#                   uvFilterSize + string/time/internal plugs are DELIBERATELY excluded
#                   (a non-fragment plug in the affects graph makes Maya 2026's VP2 fragment
#                   compiler reject the texture binding -> white viewport / black swatch).
FILE_TEXTURE_ATTRS = [
    {
        "long": "fileName", "short": "fn", "attr_type": "string", "direction": "input",
        "default": "",
        "flags": {"used_as_filename": True, "storable": True, "keyable": False},
        "affects_output": True,
    },
    {
        "long": "uvCoord", "short": "uv", "attr_type": "float2", "direction": "input",
        "children": [
            {"long": "uCoord", "short": "u", "data": "kFloat", "default": 0.0,
             "flags": {"keyable": True}},
            {"long": "vCoord", "short": "v", "data": "kFloat", "default": 0.0,
             "flags": {"keyable": True}},
        ],
        "flags": {"hidden": False, "storable": True},
        "affects_output": True,
    },
    {
        "long": "uvFilterSize", "short": "fs", "attr_type": "float2", "direction": "input",
        "children": [
            {"long": "uvFilterSizeX", "short": "fsx", "data": "kFloat", "default": 0.0,
             "flags": {}},
            {"long": "uvFilterSizeY", "short": "fsy", "data": "kFloat", "default": 0.0,
             "flags": {}},
        ],
        "flags": {"hidden": True},
        "affects_output": False,
    },
    {
        "long": "colorSpace", "short": "cs", "attr_type": "enum", "direction": "input",
        "default": 0, "enum": _cs_enum(),
        "flags": {"keyable": False, "storable": True},
        "affects_output": True,
    },
    {
        "long": "preFilter", "short": "pf", "attr_type": "bool", "direction": "input",
        "default": False,
        "flags": {"keyable": True, "storable": True},
        "affects_output": True,
    },
    {
        "long": "preFilterKernel", "short": "pfk", "attr_type": "enum", "direction": "input",
        "default": kPreFilterGaussian,
        "enum": [("Box", kPreFilterBox), ("Quadratic", kPreFilterQuadratic),
                 ("Quartic", kPreFilterQuartic), ("Gaussian", kPreFilterGaussian)],
        "flags": {"keyable": False, "storable": True},
        "affects_output": True,
    },
    {
        "long": "preFilterRadius", "short": "pfr", "attr_type": "float", "direction": "input",
        "default": 2.0, "min": 0.0, "max": 8.0,
        "flags": {"keyable": True, "storable": True},
        "affects_output": True,
    },
    {
        "long": "filterMode", "short": "fm", "attr_type": "enum", "direction": "input",
        "default": kFilterAnisotropic,
        "enum": [("Point", kFilterPoint), ("Linear", kFilterLinear),
                 ("Anisotropic", kFilterAnisotropic)],
        "flags": {"keyable": True, "storable": True},
        "affects_output": True,
    },
    {
        "long": "maxAnisotropy", "short": "maxa", "attr_type": "int", "direction": "input",
        "default": 16, "min": 1, "max": 16,
        "flags": {"keyable": True, "storable": True},
        "affects_output": True,
    },
    {
        "long": "mipmapMode", "short": "mmm", "attr_type": "enum", "direction": "input",
        "default": kMipmapAuto,
        "enum": [("None", kMipmapNone), ("Auto", kMipmapAuto)],
        "flags": {"keyable": True, "storable": True},
        "affects_output": True,
    },
    {
        "long": "mipLODBias", "short": "mlb", "attr_type": "float", "direction": "input",
        "default": 0.0, "min": -8.0, "max": 8.0,
        "flags": {"keyable": True},
        "affects_output": True,
    },
    {
        "long": "minLOD", "short": "mnl", "attr_type": "int", "direction": "input",
        "default": 0, "min": 0, "max": 16,
        "flags": {"keyable": True},
        "affects_output": True,
    },
    {
        "long": "maxLOD", "short": "mxl", "attr_type": "int", "direction": "input",
        "default": 16, "min": 0, "max": 16,
        "flags": {"keyable": True},
        "affects_output": True,
    },
    {
        "long": "wrapModeU", "short": "wmu", "attr_type": "enum", "direction": "input",
        "default": kWrapWrap,
        "enum": [("Wrap", kWrapWrap), ("Clamp", kWrapClamp),
                 ("Mirror", kWrapMirror), ("Border", kWrapBorder)],
        "flags": {"keyable": True},
        "affects_output": True,
    },
    {
        "long": "wrapModeV", "short": "wmv", "attr_type": "enum", "direction": "input",
        "default": kWrapWrap,
        "enum": [("Wrap", kWrapWrap), ("Clamp", kWrapClamp),
                 ("Mirror", kWrapMirror), ("Border", kWrapBorder)],
        "flags": {"keyable": True},
        "affects_output": True,
    },
    {
        "long": "borderColor", "short": "bcl", "attr_type": "color", "direction": "input",
        "children": [
            {"long": "borderColorR", "short": "bcr", "data": "kFloat", "default": 0.0,
             "flags": {}},
            {"long": "borderColorG", "short": "bcg", "data": "kFloat", "default": 0.0,
             "flags": {}},
            {"long": "borderColorB", "short": "bcb", "data": "kFloat", "default": 0.0,
             "flags": {}},
        ],
        "flags": {"used_as_color": True, "keyable": True, "storable": True},
        "affects_output": True,
    },
    {
        "long": "outColor", "short": "oc", "attr_type": "color", "direction": "output",
        "children": [
            {"long": "outColorR", "short": "ocr", "data": "kFloat", "default": 0.0,
             "flags": {}},
            {"long": "outColorG", "short": "ocg", "data": "kFloat", "default": 0.0,
             "flags": {}},
            {"long": "outColorB", "short": "ocb", "data": "kFloat", "default": 0.0,
             "flags": {}},
        ],
        "flags": {"storable": False, "writable": False, "readable": True,
                  "used_as_color": True},
    },
    {
        "long": "outAlpha", "short": "oa", "attr_type": "float", "direction": "output",
        "default": 1.0,
        "flags": {"storable": False, "writable": False, "readable": True},
    },
    # outTransparency / outSize complete the stock `file` node's output surface.
    # NEITHER is authored by the compute: a compute writes colour + alpha, and the
    # node DERIVES these from that, so every existing expression keeps working and
    # the full-parity tail recognizer still sees a 2-line default write.
    #   outTransparency = (1-a, 1-a, 1-a)   -- unless the compute assigns it
    #   outSize         = (w, h) of `fileName` at the node's own presets, so it is
    #                     a property of the FILE, not of the compute (the loader is
    #                     cached, so reading it costs nothing extra).
    {
        "long": "outTransparency", "short": "ot", "attr_type": "color",
        "direction": "output",
        "children": [
            {"long": "outTransparencyR", "short": "otr", "data": "kFloat",
             "default": 0.0, "flags": {}},
            {"long": "outTransparencyG", "short": "otg", "data": "kFloat",
             "default": 0.0, "flags": {}},
            {"long": "outTransparencyB", "short": "otb", "data": "kFloat",
             "default": 0.0, "flags": {}},
        ],
        "flags": {"storable": False, "writable": False, "readable": True,
                  "used_as_color": True},
    },
    {
        "long": "outSize", "short": "os", "attr_type": "float2",
        "direction": "output",
        "children": [
            {"long": "outSizeX", "short": "osx", "data": "kFloat",
             "default": 0.0, "flags": {}},
            {"long": "outSizeY", "short": "osy", "data": "kFloat",
             "default": 0.0, "flags": {}},
        ],
        "flags": {"storable": False, "writable": False, "readable": True},
    },
]


# --- projections -----------------------------------------------------------------------

def enum_labels(entry: dict) -> list:
    """Ordered enum labels for an enum descriptor (== Maya listEnum order)."""
    return [label for (label, _idx) in entry.get("enum", [])]


def build_porter_meta_table() -> dict:
    """Project the rich table down to the porter's raw-meta shape, keyed by attr name:
    ``{name: {"attr_type", "_writable", "_readable", "enum_names"?, "default_value"?}}``.

    Presets carry NOTHING beyond attr_type/_writable/_readable except the two cases
    below, so their normalized specs and their ``port_cache`` keys stay as small as the
    old hand-pinned ``_MPYFILE_PRESET_META``. ``_readable`` is True for every preset
    (Maya writable attrs are readable, and the outputs are readable-only); ``_writable``
    is True iff the attr is an input.

    FLOAT2 also carries ``children`` -- the child LONG names. Codegen otherwise
    synthesizes ``<plug>X`` / ``<plug>Y``, which is right for ``uvFilterSize`` but WRONG
    for ``uvCoord``, whose children are ``uCoord`` / ``vCoord``. Without this the compiled
    node had no ``uCoord`` plug at all and ``setAttr <node>.uCoord`` failed on every
    compiled mPyFile node, while the parent-level ``place2dTexture.outUV`` connect kept
    working -- which is why it went unnoticed.

    ENUMS also carry ``default_value``, the declared default FIELD INDEX. Codegen bakes it
    as the third ``MFnEnumAttribute::create`` argument, so without it a compiled mPyFile
    registers filterMode=Point / mipmapMode=None instead of the SSOT Anisotropic/Auto. It
    is a real change to the generated C++, so the resulting ``port_cache`` miss on the
    enum-referencing specs is the cache contract working as designed, not churn.
    """
    table = {}
    for e in FILE_TEXTURE_ATTRS:
        meta = {
            "attr_type": e["attr_type"],
            "_writable": e["direction"] == "input",
            "_readable": True,
        }
        if e["attr_type"] == "enum":
            meta["enum_names"] = enum_labels(e)
            meta["default_value"] = e["default"]
        if e["attr_type"] == "float2":
            meta["children"] = [c["long"] for c in e["children"]]
        table[e["long"]] = meta
    return table


def affects_input_names() -> list:
    """Ordered input long-names that participate in attributeAffects(-> outputs)."""
    return [e["long"] for e in FILE_TEXTURE_ATTRS
            if e["direction"] == "input" and e.get("affects_output")]


def output_names() -> list:
    """Every managed OUTPUT long-name, parents and children (declaration order).

    The single source for "is this plug one the framework owns?" -- the dirty
    propagation, the user-output skip set and the no-refresh set all read this,
    so adding an output to the table above wires it everywhere at once instead
    of leaving a hand-maintained tuple to drift."""
    names = []
    for e in FILE_TEXTURE_ATTRS:
        if e["direction"] != "output":
            continue
        names.append(e["long"])
        names += [c["long"] for c in e.get("children", [])]
    return names


def _validate():
    """Fail loudly at import if the table violates an invariant the consumers rely on."""
    for e in FILE_TEXTURE_ATTRS:
        if e["attr_type"] == "enum":
            for label, _idx in e["enum"]:
                # _preset_attr_meta's live oracle splits listEnum on ':' -- a label
                # containing ':' would mis-split the drift guard.
                assert ":" not in label, (
                    "enum label %r on %r contains ':'" % (label, e["long"]))
        if e["attr_type"] == "float2":
            assert len(e.get("children", [])) == 2, "%s float2 needs 2 children" % e["long"]
        if e["attr_type"] == "color":
            assert len(e.get("children", [])) == 3, "%s color needs 3 children" % e["long"]
            assert e["flags"].get("used_as_color"), "%s color needs used_as_color" % e["long"]


_validate()
