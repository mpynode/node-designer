"""MPyFile (API 2.0) -- expression-driven file-texture node.

A 2D-texture shading node that lets the user write Python expressions
for both the DG ``compute()`` path (per-UV sampling) AND the VP2
``MPxShadingNodeOverride.updateShader`` path (texture upload + sampler
binding). Functionally clones Maya's built-in ``file`` node with all
the image-processing knobs MayaCustomFileNode (``customFileTexture``)
exposes -- color-space linearization, CPU pre-filter blur, full GPU
sampler state -- but with EVERY line of the implementation editable
in the Node Designer.

Three source tiers per node:

* ``_initSource`` (Init tab) -- runs once per file open. Holds the
 25-entry color-space catalogue,
 gamut matrices, EOTFs, kernel
 builders, _linearize, _prefilter,
 _sample, VP2 sampler-enum maps.
* ``_computeSource`` (Compute tab) -- runs per DG compute(). Reads
 ``self.fileName`` / ``self.uvCoord``
 / etc. and writes ``self.outColor``
 + ``self.outAlpha``.
* ``_viewportSource`` (Viewport) -- runs per VP2 updateShader. Reads
 the same preset plug surface via
 ``self.X`` plus ``self.shader``
 (MShaderInstance) and uploads the
 linearized pixel buffer to the GPU.

Plug surface (mirrors ``customFileTexture`` exactly):

 Inputs: fileName, uvCoord (compound), uvFilterSize (compound),
 colorSpace (25-entry enum), preFilter, preFilterKernel,
 preFilterRadius, filterMode, maxAnisotropy, mipmapMode,
 mipLODBias, minLOD, maxLOD, wrapModeU, wrapModeV,
 borderColor.
 Outputs: outColor (color3), outAlpha (float).

Classification:

 texture/2d:swatch/2dTextureSwatchGen:drawdb/shader/texture/2d/mPyFile

This is what gives the node the Hypershade swatch + auto-place2dTexture
upstream + VP2 override registration.

MTypeId 0x00135720 (next free in the mpynode private range).
"""

from __future__ import annotations

import sys

import maya.api.OpenMaya as om
import maya.api.OpenMayaRender as omr
from mpynode._api2 import helpers
from mpynode._common.compute import output_defaults
from mpynode._common.io import serialization
from mpynode._common.storedvars import stored_var_store as _svstore
from mpynode._common.compute.expression import (
    build_exec_namespace,
    compile_expression,
    exec_with_profile_watch,
    safe_compile_expression,
)
from mpynode._common.compute.self_proxy import SelfProxy
from mpynode._common.plugs.promoted_types import TimeFloat
from mpynode._common.osl.osl_registry import MANAGED_SHADER_OUTPUTS
from mpynode._common.interface import file_texture_interface as _iface
# Maya-free texture-ops math: the importable twin of the inline math in
# ``_defaults/file_defaults.py`` DEFAULT_INIT_SOURCE. Kept in lock-step by
# test_file_texture_ops_drift.
from mpynode._common.methods import file_texture_ops as _tex

# Optional numpy: only for the DUMMY_TEXTURE_MODE solid-red buffer. None-safe
# so a numpy-less create doesn't crash.
try:
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None


# ===========================================================================
# Enum constants -- SSOT is the declarative interface (kept in sync with
# customFileTexture for scene-compat). Imported for bare-name use below.
# ===========================================================================

from mpynode._common.interface.file_texture_interface import (  # noqa: E402
    kFilterPoint, kFilterLinear, kFilterAnisotropic,
    kMipmapNone, kMipmapAuto,
    kWrapWrap, kWrapClamp, kWrapMirror, kWrapBorder,
    kPreFilterBox, kPreFilterQuadratic, kPreFilterQuartic, kPreFilterGaussian,
)


# 25-entry color-space catalogue, aliased from the interface SSOT for external
# reference. Index order is STABLE -- scene-saved integers round-trip.
from mpynode._common.interface.file_texture_interface import (  # noqa: E402
    COLOR_SPACE_NAMES as _COLOR_SPACE_NAMES,
)


# ===========================================================================
# Declarative preset-interface builder (single source of truth)
# ===========================================================================
# Preset texture attrs are declared once as data in the Maya-free SSOT
# ``file_texture_interface`` -- the SAME table the native porter projects to its
# spec. ``_build_preset_interface`` replays it as the exact MFn call sequence the
# imperative code hand-wrote, so the registered node is unchanged. Pinned by
# ``TestConformsToLiveNode`` + the live-attr golden.

# flag token -> MFn* function-set property name.
_FLAG_ATTR = {
    "keyable": "keyable", "storable": "storable", "hidden": "hidden",
    "writable": "writable", "readable": "readable",
    "used_as_color": "usedAsColor", "used_as_filename": "usedAsFilename",
    "connectable": "connectable",
}
# scalar attr_type -> MFnNumericData token.
_SCALAR_DATA = {
    "float": om.MFnNumericData.kFloat,
    "int":   om.MFnNumericData.kInt,
    "bool":  om.MFnNumericData.kBoolean,
}
_CHILD_DATA = {"kFloat": om.MFnNumericData.kFloat}
# interface long-name -> MPyFile class attr holding the MObject (referenced by
# compute() / the VP2 override / attributeAffects).
_CLASS_REF = {
    "fileName": "aFileName",
    "uvCoord": "aUvCoord", "uCoord": "aUCoord", "vCoord": "aVCoord",
    "uvFilterSize": "aUvFilterSize",
    "uvFilterSizeX": "aUvFilterSizeX", "uvFilterSizeY": "aUvFilterSizeY",
    "colorSpace": "aColorSpace",
    "preFilter": "aPreFilter", "preFilterKernel": "aPreFilterKernel",
    "preFilterRadius": "aPreFilterRadius",
    "filterMode": "aFilterMode", "maxAnisotropy": "aMaxAnisotropy",
    "mipmapMode": "aMipmapMode", "mipLODBias": "aMipLODBias",
    "minLOD": "aMinLOD", "maxLOD": "aMaxLOD",
    "wrapModeU": "aWrapU", "wrapModeV": "aWrapV",
    "borderColor": "aBorderColor", "borderColorR": "aBorderColorR",
    "borderColorG": "aBorderColorG", "borderColorB": "aBorderColorB",
    "outColor": "aOutColor", "outColorR": "aOutColorR",
    "outColorG": "aOutColorG", "outColorB": "aOutColorB",
    "outAlpha":         "aOutAlpha",
    "outTransparency":  "aOutTransparency",
    "outTransparencyR": "aOutTransparencyR",
    "outTransparencyG": "aOutTransparencyG",
    "outTransparencyB": "aOutTransparencyB",
    "outSize": "aOutSize", "outSizeX": "aOutSizeX", "outSizeY": "aOutSizeY",
}


def _apply_flags(fn, flags):
    # MFn* mutates the LAST-created attr, so call this immediately after each
    # create. Order among these booleans doesn't matter.
    for name, val in flags.items():
        setattr(fn, _FLAG_ATTR[name], val)


# Every framework-owned output plug (parents + children), from the SSOT. Used by
# the dirty propagation, the user-output skip set and the no-refresh set, so a
# new output in FILE_TEXTURE_ATTRS reaches all three without a hand-edit.
_MANAGED_OUTPUT_NAMES = tuple(_iface.output_names())


def _derive_out_size(self_proxy):
    """(width, height) of the image this node reads, as floats; (0, 0) for none.

    Routed through the node's own blessed ``read_texture()`` so it honours the
    colour-space / pre-filter presets AND the embedded-image fallback, and hits
    the same cache entry the compute already populated."""
    try:
        buf = self_proxy.read_texture()
    except Exception:
        return (0.0, 0.0)
    if buf is None or getattr(buf, "ndim", 0) < 2:
        return (0.0, 0.0)
    return (float(buf.shape[1]), float(buf.shape[0]))


def _build_preset_interface(cls):
    """Register the mPyFile preset texture attrs from ``_iface.FILE_TEXTURE_ATTRS`` and
    set the ``cls.aXxx`` MObject refs. Reproduces the exact imperative MFn sequence."""
    nAttr = om.MFnNumericAttribute()
    tAttr = om.MFnTypedAttribute()
    eAttr = om.MFnEnumAttribute()
    for e in _iface.FILE_TEXTURE_ATTRS:
        t = e["attr_type"]
        if t == "string":
            default = om.MFnStringData().create(e.get("default", ""))
            obj     = tAttr.create(e["long"], e["short"], om.MFnData.kString, default)
            _apply_flags(tAttr, e.get("flags", {}))
        elif t == "enum":
            obj = eAttr.create(e["long"], e["short"], e.get("default", 0))
            for label, idx in e["enum"]:
                eAttr.addField(label, idx)
            _apply_flags(eAttr, e.get("flags", {}))
        elif t in ("float2", "color"):
            child_objs = []
            for c in e["children"]:
                co = nAttr.create(c["long"], c["short"], _CHILD_DATA[c["data"]],
                                  c.get("default", 0.0))
                _apply_flags(nAttr, c.get("flags", {}))
                setattr(cls, _CLASS_REF[c["long"]], co)
                child_objs.append(co)
            obj = nAttr.create(e["long"], e["short"], *child_objs)
            _apply_flags(nAttr, e.get("flags", {}))
        else:  # float / int / bool scalar
            obj = nAttr.create(e["long"], e["short"], _SCALAR_DATA[t], e.get("default"))
            if "min" in e:
                nAttr.setMin(e["min"])
            if "max" in e:
                nAttr.setMax(e["max"])
            _apply_flags(nAttr, e.get("flags", {}))
        cls.addAttribute(obj)
        setattr(cls, _CLASS_REF[e["long"]], obj)


# ===========================================================================
# MPyFile -- the MPxNode subclass (DG path)
# ===========================================================================


class MPyFile(om.MPxNode):
    """API 2.0 expression-driven file-texture node."""

    NODE_NAME              = "mPyFile"
    NODE_ID                = om.MTypeId(0x00135720)
    DRAW_DB_CLASSIFICATION = "drawdb/shader/texture/2d/mPyFile"
    DRAW_REGISTRANT_ID     = "mPyFilePlugin"
    PLUGIN_NODE_CLASSIFY = (
        "texture/2d"
        ":swatch/2dTextureSwatchGen"
        ":" + DRAW_DB_CLASSIFICATION
    )

    # BAREBONES_MODE: when True, compute() and runViewport() use a hardcoded
    # inline port of customFileTexture's logic, bypassing the user-expression /
    # init-namespace / viewport-source chain. Default False = the full mpynode
    # user-editable path. Class-level toggle only (there is no per-node attr).
    BAREBONES_MODE: bool = False

    # DUMMY_TEXTURE_MODE -- diagnostic for the Maya 2026 white-viewport bug:
    # the override ignores fileName and uploads a solid red 64x64 RGBA float32
    # texture. Sphere renders RED = the GPU-upload + parameter-binding path
    # works and the problem is file loading. Still white = the override ->
    # fragment binding itself is broken.
    DUMMY_TEXTURE_MODE: bool = False

    # --- internal-mpynode attrs (set by helpers.build_internal_attrs) ---
    _expression_attr:            om.MObject = om.MObject.kNullObj
    _input_attrs_attr:           om.MObject = om.MObject.kNullObj
    _output_attrs_attr:          om.MObject = om.MObject.kNullObj
    _stored_vars_list_attr:      om.MObject = om.MObject.kNullObj
    _stored_vars_data_attr:      om.MObject = om.MObject.kNullObj
    _debug_mode_attr:            om.MObject = om.MObject.kNullObj
    _profile_enabled_attr:       om.MObject = om.MObject.kNullObj
    _deep_profile_enabled_attr:  om.MObject = om.MObject.kNullObj
    _watch_enabled_attr:         om.MObject = om.MObject.kNullObj
    _profile_snapshot_data_attr: om.MObject = om.MObject.kNullObj
    _watch_vars_data_attr:       om.MObject = om.MObject.kNullObj

    # --- preset file-texture attrs (mirrors customFileTexture) ---
    aFileName:        om.MObject = om.MObject.kNullObj
    aUvCoord:         om.MObject = om.MObject.kNullObj
    aUCoord:          om.MObject = om.MObject.kNullObj
    aVCoord:          om.MObject = om.MObject.kNullObj
    aUvFilterSize:    om.MObject = om.MObject.kNullObj
    aUvFilterSizeX:   om.MObject = om.MObject.kNullObj
    aUvFilterSizeY:   om.MObject = om.MObject.kNullObj
    aColorSpace:      om.MObject = om.MObject.kNullObj
    aPreFilter:       om.MObject = om.MObject.kNullObj
    aPreFilterKernel: om.MObject = om.MObject.kNullObj
    aPreFilterRadius: om.MObject = om.MObject.kNullObj
    aFilterMode:      om.MObject = om.MObject.kNullObj
    aMaxAnisotropy:   om.MObject = om.MObject.kNullObj
    aMipmapMode:      om.MObject = om.MObject.kNullObj
    aMipLODBias:      om.MObject = om.MObject.kNullObj
    aMinLOD:          om.MObject = om.MObject.kNullObj
    aMaxLOD:          om.MObject = om.MObject.kNullObj
    aWrapU:           om.MObject = om.MObject.kNullObj
    aWrapV:           om.MObject = om.MObject.kNullObj
    aBorderColor:     om.MObject = om.MObject.kNullObj
    aBorderColorR:    om.MObject = om.MObject.kNullObj
    aBorderColorG:    om.MObject = om.MObject.kNullObj
    aBorderColorB:    om.MObject = om.MObject.kNullObj
    aOutColor:        om.MObject = om.MObject.kNullObj
    aOutColorR:       om.MObject = om.MObject.kNullObj
    aOutColorG:       om.MObject = om.MObject.kNullObj
    aOutColorB:       om.MObject = om.MObject.kNullObj
    aOutAlpha:        om.MObject = om.MObject.kNullObj

    # --- viewport source attr (matches the wrapper's ViewportSourceMixin) ---
    aViewportSource: om.MObject = om.MObject.kNullObj

    # --- managed render-target shader output(s): osl (+ future hlsl/...) ---
    #     statically registered like outColor; names from
    #     osl_registry.MANAGED_SHADER_OUTPUTS. Populated in initializer().
    aShaderOutputs: dict = {}

    def __init__(self):
        super().__init__()
        # Compute (expression) cache.
        self._expr_str: str = ""
        self._expr_code = compile_expression("")
        # Viewport cache.
        self._viewport_str: str = ""
        self._viewport_code = compile_expression("")
        # Thread safety: cache the decoded _inputAttrs map so setDependentsDirty
        # (fires on the Hypershade swatch worker thread) needs no findPlug DG
        # read. compute() populates it on every main-thread invocation.
        self._user_input_map_cache: dict = {}

    # ------------------------------------------------------------------
    # Creators
    # ------------------------------------------------------------------

    @staticmethod
    def creator():
        return MPyFile()

    @staticmethod
    def initializer():
        # ORDER MATTERS for Maya 2026's CPU-side swatch generator
        # (2dTextureSwatchGen): it iterates attrs in DECLARATION order and
        # treats the first input plug as a hint for "what kind of texture is
        # this". customFileTexture declares fileName first. When mPyFile
        # declared its internals (expression, _inputAttrs, ...) first, the
        # generator silently degraded to a single-sample render and every
        # Hypershade Browser thumbnail came out one solid colour regardless of
        # UV. Internal-attr registration is therefore delayed until AFTER all
        # preset texture attrs -- see the block before attributeAffects below.

        # Preset texture interface (fileName .. borderColor + outColor/outAlpha)
        # from the declarative SSOT. See _build_preset_interface.
        _build_preset_interface(MPyFile)

        # Typed-attr fn set for the managed shader-output plugs declared below.
        tAttr = om.MFnTypedAttribute()

        # ---- managed render-target shader output(s) -- e.g. osl ----------
        # A connectable string OUTPUT authored in the OSL tab / by the AI
        # translator and wired into a renderer node such as aiOslShader.
        # Registered STATICALLY (like outColor) so it exists on every instance
        # and is undeletable. Writable (setAttr from the tab/AI/demo) AND
        # readable+connectable (a valid connection SOURCE); the Attributes-tab
        # walker force-classifies it as OUTPUT. NOT internal=True -- that kills
        # connectability. NOT in the attributeAffects(... outColor) graph -- a
        # string plug there makes Maya 2026's VP2 fragment compiler reject the
        # texture binding (white viewport / black swatch).
        MPyFile.aShaderOutputs = {}
        for _sh_name in MANAGED_SHADER_OUTPUTS:
            _sh_default = om.MFnStringData().create("")
            _sh_attr = tAttr.create(
                _sh_name, _sh_name, om.MFnData.kString, _sh_default
            )
            tAttr.storable    = True
            tAttr.writable    = True
            tAttr.readable    = True
            tAttr.connectable = True
            tAttr.keyable     = False
            # hidden=True: osl is writable, so a non-hidden writable string
            # would render as an editable AE field -- but it is a wire/tab
            # artifact, not an artist control. hidden removes it from the AE +
            # channel box WITHOUT affecting setAttr, connectAttr (still a
            # connection SOURCE) or .ma persistence; the Node Designer plug
            # walker does NOT filter on isHidden, so it still shows as an OUTPUT
            # row (parity with Maya's own hidden `message`).
            tAttr.hidden = True
            MPyFile.addAttribute(_sh_attr)
            MPyFile.aShaderOutputs[_sh_name] = _sh_attr

        # ---- mpynode internal attrs (LAST, on purpose -- see top of ----
        #      initializer for why) -------------------------------------
        plugs                               = helpers.build_internal_attrs(MPyFile)
        MPyFile._expression_attr            = plugs["_computeSource"]
        MPyFile._input_attrs_attr           = plugs["inputs"]
        MPyFile._output_attrs_attr          = plugs["outputs"]
        MPyFile._stored_vars_list_attr      = plugs["stored_vars_list"]
        MPyFile._stored_vars_data_attr      = plugs["stored_vars_data"]
        MPyFile._debug_mode_attr            = plugs["debug_mode"]
        MPyFile._profile_enabled_attr       = plugs["profile_enabled"]
        MPyFile._deep_profile_enabled_attr  = plugs["deep_profile_enabled"]
        MPyFile._watch_enabled_attr         = plugs["watch_enabled"]
        MPyFile._profile_snapshot_data_attr = plugs["profile_snapshot_data"]
        MPyFile._watch_vars_data_attr       = plugs["watch_vars_data"]

        # Viewport source plug.
        MPyFile.aViewportSource = helpers.make_internal_string_attr(
            "_viewportSource", "_viewportSource"
        )
        MPyFile.addAttribute(MPyFile.aViewportSource)

        # Hidden time input. The wrapper auto-connects time1.outTime so
        # ``self.time`` is always available (image-sequence expressions need no
        # manual wiring). DELIBERATELY NOT in ``attributeAffects(... outColor)``
        # -- a kTime input in the affects graph makes Maya's VP2 fragment
        # compiler reject the texture-parameter binding (white viewport / black
        # swatch). The per-frame refresh comes from the timeChanged callback
        # below via ``dgdirty(outColor)`` instead.
        _time_fn = om.MFnUnitAttribute()
        MPyFile._time_in_attr = _time_fn.create(
            "_timeIn", "_tin", om.MFnUnitAttribute.kTime, 0.0
        )
        _time_fn.storable = True
        _time_fn.keyable  = False
        _time_fn.readable = False
        _time_fn.writable = True
        _time_fn.hidden   = True
        MPyFile.addAttribute(MPyFile._time_in_attr)

        # ---- attributeAffects -------------------------------------------
        # Must list every CHILD of outColor explicitly: Maya's legacy Software
        # renderer (which draws the Hypershade Materials-tab swatch by rendering
        # a sphere under lambert1) pulls outColorR/G/B individually, not the
        # compound parent. Without them the children never go dirty on a uvCoord
        # change, compute() never re-runs, and the swatch renders black while
        # the VP2 viewport looks correct. customFileTexture has the same tuple.
        outs = (
            MPyFile.aOutColor,
            MPyFile.aOutColorR,
            MPyFile.aOutColorG,
            MPyFile.aOutColorB,
            MPyFile.aOutAlpha,
            # The stock file node carries these in its affects graph too. The
            # VP2 hazard called out below is about non-fragment INPUTS on the
            # src side; extra float3/float2 OUTPUTS on the dst side are what a
            # real `file` node already does.
            MPyFile.aOutTransparency,
            MPyFile.aOutTransparencyR,
            MPyFile.aOutTransparencyG,
            MPyFile.aOutTransparencyB,
            MPyFile.aOutSize,
            MPyFile.aOutSizeX,
            MPyFile.aOutSizeY,
        )
        # This list MUST match customFileTexture's exactly. Maya 2026's VP2
        # fragment compiler reads the attributeAffects graph for shader-param
        # binding hints; a string plug like ``_expression_attr`` (or an extra
        # non-fragment input like ``uvFilterSize``) makes it silently reject the
        # texture binding -- white viewport / black swatch -- even though
        # setParameter appears to succeed. Expression / viewport plug changes
        # propagate via setInternalValue + manual ``dgdirty`` instead.
        # The set comes from the declarative SSOT (inputs flagged
        # affects_output=True; excludes uvFilterSize + string/time/internal).
        all_inputs = tuple(getattr(MPyFile, _CLASS_REF[nm])
                           for nm in _iface.affects_input_names())
        for src in all_inputs:
            for dst in outs:
                try:
                    MPyFile.attributeAffects(src, dst)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # MPxNode hooks
    # ------------------------------------------------------------------

    def setInternalValue(self, plug, data_handle):
        """Recompile cached code objects when the expression or
        viewport source plug changes."""
        try:
            attr      = plug.attribute()
            node_name = ""
            try:
                node_name = om.MFnDependencyNode(self.thisMObject()).name()
            except Exception:
                pass
            if attr == type(self)._expression_attr:
                new_src        = data_handle.asString()
                self._expr_str = new_src
                code = safe_compile_expression(
                    new_src,
                    node_name = node_name,
                    filename  = "<mpyfile-compute>",
                )
                if code is not None:
                    self._expr_code = code
                # Manual dirty prop: expression isn't in attributeAffects (the
                # VP2 fragment compiler chokes on string-affects-color).
                try:
                    import maya.cmds as _cmds
                    if node_name:
                        _cmds.dgdirty(node_name + ".outColor")
                        _cmds.dgdirty(node_name + ".outAlpha")
                except Exception:
                    pass
            elif attr == type(self).aViewportSource:
                new_src            = data_handle.asString()
                self._viewport_str = new_src
                code = safe_compile_expression(
                    new_src,
                    node_name = node_name,
                    filename  = "<mpyfile-viewport>",
                )
                if code is not None:
                    self._viewport_code = code
                # Same rationale as the expression branch: nudge the override
                # to re-bind.
                try:
                    import maya.cmds as _cmds
                    if node_name:
                        _cmds.dgdirty(node_name + ".outColor")
                except Exception:
                    pass
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # BAREBONES inline compute / viewport
    # ------------------------------------------------------------------

    def _compute_barebones(self, plug, data_block):
        """Inline mirror of customFileTexture.compute(). Reads every
        preset plug from the data block directly, samples the texture
        via the Maya-free ``file_texture_ops`` (``_tex``) helpers (no user
        expression / no init namespace / no viewport source), and writes
        outColor + outAlpha. Identical math to customFileTexture."""
        try:
            path      = data_block.inputValue(MPyFile.aFileName).asString()
            cs_index  = data_block.inputValue(MPyFile.aColorSpace).asShort()
            prefilter = data_block.inputValue(MPyFile.aPreFilter).asBool()
            pf_kernel = data_block.inputValue(MPyFile.aPreFilterKernel).asShort()
            pf_radius = data_block.inputValue(MPyFile.aPreFilterRadius).asFloat()
            uv_h      = data_block.inputValue(MPyFile.aUvCoord)
            u         = uv_h.child(MPyFile.aUCoord).asFloat()
            v         = uv_h.child(MPyFile.aVCoord).asFloat()
            wrap_u    = data_block.inputValue(MPyFile.aWrapU).asShort()
            wrap_v    = data_block.inputValue(MPyFile.aWrapV).asShort()
            bc_h      = data_block.inputValue(MPyFile.aBorderColor)
            bc_vec    = bc_h.asFloatVector()
            border    = (bc_vec.x, bc_vec.y, bc_vec.z)
        except Exception:
            return

        pixels = _tex.load_linear_pixels(
            path, cs_index, prefilter, pf_kernel, pf_radius
        )
        r, g, b, a = _tex.sample(pixels, u, v, wrap_u, wrap_v, border)

        try:
            oc = data_block.outputValue(MPyFile.aOutColor)
            oc.setMFloatVector(om.MFloatVector(r, g, b))
            oc.setClean()
        except Exception:
            pass
        try:
            oa = data_block.outputValue(MPyFile.aOutAlpha)
            oa.setFloat(float(a))
            oa.setClean()
        except Exception:
            pass
        try:
            data_block.setClean(plug)
        except Exception:
            pass

    def _run_viewport_barebones(self, shader, mappings):
        """Inline mirror of customFileTexture's updateShader. Uploads
        the linearized texture to the GPU and binds it to the
        mayaFileTexture fragment's map_param + sampler_param. No
        user-expression involvement.

        Reads preset plug values via ``MFnDependencyNode.findPlug``
        (the API-level read). Do NOT use ``cmds.getAttr`` here --
        ``updateShader`` runs on Maya's render thread where
        ``cmds.getAttr`` silently fails (returns None), the int()
        cast raises TypeError, our bare except bails before the
        texture upload, and the viewport renders white because the
        GPU sampler has no bound texture. customFileTexture uses
        findPlug for this exact reason."""
        try:
            node_obj  = self.thisMObject()
            fn        = om.MFnDependencyNode(node_obj)
            file_name = fn.findPlug("fileName", False).asString()
            cs_index  = int(fn.findPlug("colorSpace", False).asShort())
            preFilter = bool(fn.findPlug("preFilter", False).asBool())
            preFilterKernel = int(
                fn.findPlug("preFilterKernel", False).asShort()
            )
            preFilterRadius = float(
                fn.findPlug("preFilterRadius", False).asFloat()
            )
            filterMode = int(fn.findPlug("filterMode", False).asShort())
            maxAnisotropy = int(
                fn.findPlug("maxAnisotropy", False).asInt()
            )
            mipmapMode = int(fn.findPlug("mipmapMode", False).asShort())
            mipLODBias = float(
                fn.findPlug("mipLODBias", False).asFloat()
            )
            minLOD    = int(fn.findPlug("minLOD", False).asInt())
            maxLOD    = int(fn.findPlug("maxLOD", False).asInt())
            wrapModeU = int(fn.findPlug("wrapModeU", False).asShort())
            wrapModeV = int(fn.findPlug("wrapModeV", False).asShort())
            bc        = fn.findPlug("borderColor", False)
            border = (
                bc.child(0).asFloat(),
                bc.child(1).asFloat(),
                bc.child(2).asFloat(),
            )
        except Exception as exc:
            import sys
            sys.stderr.write(
                "[mPyFile barebones-viewport] plug read failed: %s\n" % exc
            )
            return

        # Find map + sampler parameters on the fragment.
        map_param  = None
        samp_param = None
        try:
            for pname in shader.parameterList():
                try:
                    ptype = shader.parameterType(pname)
                except Exception:
                    continue
                if (map_param is None
                        and ptype == omr.MShaderInstance.kTexture2):
                    map_param = pname
                elif (samp_param is None
                        and ptype == omr.MShaderInstance.kSampler):
                    samp_param = pname
                if map_param and samp_param:
                    break
        except Exception:
            return

        linear = _tex.load_linear_pixels(
            file_name, cs_index, preFilter, preFilterKernel, preFilterRadius
        )
        if linear is not None and map_param:
            texture = _tex.upload_linear_texture(
                linear, file_name, cs_index, mipmapMode,
                preFilter, preFilterKernel, preFilterRadius,
                name_prefix="mpyfile::bb::",
                dummy_name=("mpyfile::bb::DUMMY_RED_64x64"
                            if MPyFile.DUMMY_TEXTURE_MODE else None),
            )
            if texture is not None:
                try:
                    assignment         = omr.MTextureAssignment()
                    assignment.texture = texture
                    shader.setParameter(map_param, assignment)
                finally:
                    try:
                        omr.MRenderer.getTextureManager().releaseTexture(texture)
                    except Exception:
                        pass

        if samp_param is not None:
            try:
                desc = omr.MSamplerStateDesc()
                desc.setDefaults()
                desc.filter        = _tex.vp2_filter_for(filterMode)
                desc.maxAnisotropy = maxAnisotropy
                desc.mipLODBias    = mipLODBias
                desc.minLOD        = minLOD
                desc.maxLOD        = maxLOD
                desc.addressU      = _tex.vp2_wrap_for(wrapModeU)
                desc.addressV      = _tex.vp2_wrap_for(wrapModeV)
                try:
                    desc.borderColor = (
                        float(border[0]), float(border[1]),
                        float(border[2]), 1.0,
                    )
                except Exception:
                    pass
                shader.setParameter(
                    samp_param,
                    omr.MStateManager.acquireSamplerState(desc),
                )
            except Exception:
                pass

    def setDependentsDirty(self, plug, affected_plugs):
        """Mirror MPyNode's dynamic dirty-prop for USER inputs (in case the
        user adds extra inputs via add_input_attr) and dirty the native
        outColor/outAlpha when a user input changes. Preset inputs are
        already covered by static attributeAffects.

        Routed through the shared :func:`dirty_affects.declare_user_affects`
        helper (``extra_outputs`` carries the native outputs) so this body
        cannot re-introduce the super-return bug."""
        from mpynode._common.plugs import dirty_affects

        # A SUSPENDED node (nodeState Has No Effect / Blocking -- Convert to
        # C++ sets it on the idle Python node, a user may too) forwards
        # nothing. The Evaluation Manager evaluates every user output an
        # animated input dirties whether or not anything reads it -- a full
        # expression run per frame on a node meant to be idle (Mesh Maze's
        # int solutionSteps after Convert to C++, measured 2026-09-14).
        if dirty_affects.api2_dirty_gate(self, plug):
            return None
        dirty_affects.declare_user_affects(
            self.thisMObject(),
            plug,
            affected_plugs,
            MPyFile._input_attrs_attr,
            MPyFile._output_attrs_attr,
            extra_outputs=(MPyFile.aOutColor, MPyFile.aOutAlpha),
        )
        return None

    def compute(self, plug, data_block):
        """DG path: read inputs, run the user Compute expression,
        write outColor + outAlpha."""
        # Defer while a scene is being READ: the Evaluation Manager can pull an
        # output mid-load, before this node's dynamic attrs are restored, making
        # the expression raise a spurious "self has no plug named ..." error.
        try:
            import maya.OpenMaya as _om1

            if _om1.MFileIO.isReadingFile():
                return self
        except Exception:
            pass
        # Suspended (nodeState != Normal): not evaluated. The plug stays
        # dirty so un-suspending recomputes it -- the API 1.0 deformers'
        # contract. Read off the data block: safe on an EM worker thread.
        from mpynode._common.plugs import dirty_affects as _dirty_affects

        if _dirty_affects.api2_suspended_in_block(self, data_block):
            return self

        try:
            attr_obj = plug.attribute()
            attr_fn  = om.MFnAttribute(attr_obj)
            out_name = attr_fn.name
        except Exception:
            return self

        # USER outputs (declared in _outputAttrs): pulling one must also
        # trigger compute + get written, exactly like outColor/outAlpha.
        try:
            _outs = om.MFnDependencyNode(self.thisMObject()).findPlug(
                MPyFile._output_attrs_attr, True
            ).asString()
            output_map = serialization.decode_attr_map(_outs) if _outs else {}
        except Exception:
            output_map = {}

        is_ours = (
            attr_obj == MPyFile.aOutColor
            or attr_obj == MPyFile.aOutAlpha
            or attr_obj == MPyFile.aOutTransparency
            or attr_obj == MPyFile.aOutSize
            or (plug.isChild and plug.parent().attribute()
                in (MPyFile.aOutColor, MPyFile.aOutTransparency,
                    MPyFile.aOutSize))
            or out_name in _MANAGED_OUTPUT_NAMES
            or out_name in output_map
        )
        if not is_ours:
            return self

        # BAREBONES short-circuit: run the inline customFileTexture path instead
        # of the user-expression / init-namespace machinery below.
        if type(self).BAREBONES_MODE:
            self._compute_barebones(plug, data_block)
            return self

        node_obj = self.thisMObject()

        # Read stored vars via the data block.
        stored_vars = {}
        try:
            sv_str = data_block.inputValue(
                MPyFile._stored_vars_data_attr
            ).asString()
            stored_vars = (
                _svstore.load_for_compute(node_obj, sv_str)
            )
        except Exception:
            stored_vars = {}

        # Pre-populate compute_locals with EVERY preset plug value, read
        # straight from the data block. Two reasons:
        #
        # 1. THREAD SAFETY. Maya's Hypershade Materials-tab swatch renderer runs
        #    compute() on a worker thread, and the data block is the ONLY Maya
        #    API documented thread-safe in compute(); PlugProxy / SelfProxy use
        #    MFnDependencyNode, which is not. Without this, the expression's
        #    ``self.fileName`` read raises AttributeError on the worker thread,
        #    aborts before setting self.outColor, and the lambert swatch renders
        #    BLACK. customFileTexture reads the data block for the same reason.
        #
        # 2. SPEED. Avoids a fresh MFnDependencyNode walk per attr per compute().
        #
        # Reads now hit compute_locals (SelfProxy tier 1) instead of the plug
        # tree (tier 2); the shipped default Compute source already uses these
        # names.
        preset_locals = {
            "outColor": (0.0, 0.0, 0.0),
            "outAlpha": 0.0,
            # Seeded None, NOT a value: None is what tells the write step below
            # "the compute did not assign this", so it derives (1 - alpha) /
            # the image size instead. A numeric seed would be indistinguishable
            # from a deliberate assignment of that same number.
            "outTransparency": None,
            "outSize":         None,
        }
        # self.time -- current frame as a TimeFloat (carries the scene fps), so
        # image-sequence expressions can index by frame. Read from the hidden
        # _timeIn plug: worker-thread safe, unlike cmds.currentTime.
        try:
            _time_val = data_block.inputValue(
                MPyFile._time_in_attr
            ).asTime().value
        except Exception:
            _time_val = 0.0
        preset_locals["time"] = TimeFloat(_time_val)
        try:
            preset_locals["fileName"] = (
                data_block.inputValue(MPyFile.aFileName).asString()
            )
        except Exception:
            preset_locals["fileName"] = ""
        try:
            uv_handle = data_block.inputValue(MPyFile.aUvCoord)
            u_val     = uv_handle.child(MPyFile.aUCoord).asFloat()
            v_val     = uv_handle.child(MPyFile.aVCoord).asFloat()
        except Exception:
            u_val, v_val = 0.0, 0.0
        preset_locals["uvCoord"] = (float(u_val), float(v_val))
        # WORKAROUND: skip the uvFilterSize compound data-block read. BOTH
        # ``child(aUvFilterSizeX).asFloat()`` and ``asFloat2()`` hard-crash Maya
        # 2026's Hypershade swatch generator for mPyFile specifically (fine for
        # customFileTexture; the handle appears to be in an invalid state).
        # Default to (0.0, 0.0) -- DEFAULT_COMPUTE_SOURCE doesn't reference
        # ``self.uvFilterSize``. Expressions needing real values must read it
        # from outside the swatch path (e.g. cmds.getAttr on the main thread).
        preset_locals["uvFilterSize"] = (0.0, 0.0)
        try:
            preset_locals["colorSpace"] = int(
                data_block.inputValue(MPyFile.aColorSpace).asShort()
            )
        except Exception:
            preset_locals["colorSpace"] = 0
        try:
            preset_locals["preFilter"] = bool(
                data_block.inputValue(MPyFile.aPreFilter).asBool()
            )
        except Exception:
            preset_locals["preFilter"] = False
        try:
            preset_locals["preFilterKernel"] = int(
                data_block.inputValue(MPyFile.aPreFilterKernel).asShort()
            )
        except Exception:
            preset_locals["preFilterKernel"] = 3  # Gaussian
        try:
            preset_locals["preFilterRadius"] = float(
                data_block.inputValue(MPyFile.aPreFilterRadius).asFloat()
            )
        except Exception:
            preset_locals["preFilterRadius"] = 2.0
        try:
            preset_locals["filterMode"] = int(
                data_block.inputValue(MPyFile.aFilterMode).asShort()
            )
        except Exception:
            preset_locals["filterMode"] = 2  # Anisotropic
        try:
            preset_locals["maxAnisotropy"] = int(
                data_block.inputValue(MPyFile.aMaxAnisotropy).asInt()
            )
        except Exception:
            preset_locals["maxAnisotropy"] = 16
        try:
            preset_locals["mipmapMode"] = int(
                data_block.inputValue(MPyFile.aMipmapMode).asShort()
            )
        except Exception:
            preset_locals["mipmapMode"] = 1  # Auto
        try:
            preset_locals["mipLODBias"] = float(
                data_block.inputValue(MPyFile.aMipLODBias).asFloat()
            )
        except Exception:
            preset_locals["mipLODBias"] = 0.0
        try:
            preset_locals["minLOD"] = int(
                data_block.inputValue(MPyFile.aMinLOD).asInt()
            )
        except Exception:
            preset_locals["minLOD"] = 0
        try:
            preset_locals["maxLOD"] = int(
                data_block.inputValue(MPyFile.aMaxLOD).asInt()
            )
        except Exception:
            preset_locals["maxLOD"] = 16
        try:
            preset_locals["wrapModeU"] = int(
                data_block.inputValue(MPyFile.aWrapU).asShort()
            )
        except Exception:
            preset_locals["wrapModeU"] = 0  # Wrap
        try:
            preset_locals["wrapModeV"] = int(
                data_block.inputValue(MPyFile.aWrapV).asShort()
            )
        except Exception:
            preset_locals["wrapModeV"] = 0
        try:
            bc_handle = data_block.inputValue(MPyFile.aBorderColor)
            bc_vec    = bc_handle.asFloatVector()
            preset_locals["borderColor"] = (
                float(bc_vec.x), float(bc_vec.y), float(bc_vec.z)
            )
        except Exception:
            preset_locals["borderColor"] = (0.0, 0.0, 0.0)

        # Recognize USER-added outputs as compute-locals so ``self.<out> = v``
        # lands in the locals snapshot (harvested by write_user_outputs) rather
        # than a compute-time plug write. Seed = the base-contract default (C5):
        # a scalar, or a PRE-SIZED ``(N, ...)`` buffer for an array output so an
        # in-place ``self.<out>[i] = v`` works instead of raising on ``None``.
        _fn_out = om.MFnDependencyNode(node_obj)
        for _user_out, _user_seed in output_defaults.seed_user_output_defaults_api2(
                _fn_out, output_map).items():
            preset_locals.setdefault(_user_out, _user_seed)

        # Read USER inputs via the data block (thread-safe), BEFORE the
        # SelfProxy is built so they can be seeded into compute_locals.
        # Otherwise ``self.<user input>`` falls through to the plug tree, unsafe
        # on the swatch / Arnold worker thread: ``AttributeError: 'self' has no
        # plug ...`` aborts the expression and the render goes magenta.
        try:
            inputs_str = data_block.inputValue(
                MPyFile._input_attrs_attr
            ).asString()
            input_map = (
                serialization.decode_attr_map(inputs_str) if inputs_str else {}
            )
        except Exception:
            input_map = {}
        input_values: dict = {}
        if input_map:
            input_values = helpers.read_user_inputs_dict_from_datablock(
                data_block, node_obj, input_map
            )
            # Seed into compute_locals so ``self.<user input>`` resolves with NO
            # plug read -- what makes it work on the Hypershade swatch / Arnold
            # worker thread. ``setdefault`` so a same-named preset / output
            # plug still wins.
            for _in_name, _in_val in input_values.items():
                preset_locals.setdefault(_in_name, _in_val)

        self_proxy = SelfProxy(
            node_obj,
            datablock       = data_block,
            user_storage    = stored_vars,
            compute_locals  = preset_locals,
            node_type_label = type(self).__name__,
            node_type_name  = type(self).NODE_NAME,
        )

        # Self-only: user inputs are reached via self.X (seeded into the
        # SelfProxy snapshot above for worker-thread safety), NOT as bare names.
        namespace         = build_exec_namespace()
        namespace["self"] = self_proxy

        if self._expr_code is None:
            data_block.setClean(plug)
            return self

        # Sync compiled code with the _computeSource plug so a DUPLICATED
        # node runs its expression (see helpers.ensure_expr_code).
        helpers.ensure_expr_code(self, type(self)._expression_attr)

        captured: list[str] = []

        def _on_err(msg):
            captured.append(msg)

        ok = exec_with_profile_watch(
            self._expr_code,
            namespace,
            on_error = _on_err,
            node_obj = node_obj,
        )
        if not ok:
            if captured:
                # Base-contract policy (C10): suppress the benign transient
                # missing-plug error (declared-but-unresolved plug pulled mid
                # scene-load / graph rebuild), surface everything else --
                # identical to the base mPyNode instead of drifting.
                from mpynode._common.compute.base_contract import broadcast_compute_error

                broadcast_compute_error(
                    "mPyFile",
                    captured[0],
                    declared_names=set(input_map) | set(output_map),
                )

        # Read back outColor + outAlpha from the SelfProxy / locals.
        locals_out = self_proxy.get_compute_locals()
        out_color  = locals_out.get("outColor", (0.0, 0.0, 0.0))
        out_alpha  = locals_out.get("outAlpha", 0.0)

        try:
            r, g, b = (float(out_color[0]),
                       float(out_color[1]),
                       float(out_color[2]))
        except Exception:
            r, g, b = 1.0, 0.0, 1.0  # magenta on bad shape

        try:
            oc_handle = data_block.outputValue(MPyFile.aOutColor)
            oc_handle.setMFloatVector(om.MFloatVector(r, g, b))
            oc_handle.setClean()
        except Exception:
            pass
        try:
            oa_handle = data_block.outputValue(MPyFile.aOutAlpha)
            oa_handle.setFloat(float(out_alpha))
            oa_handle.setClean()
        except Exception:
            pass

        # outTransparency: DERIVED as 1 - alpha per channel unless the compute
        # assigned it. A compute writes colour + alpha; transparency is the same
        # information a shader's .transparency wants, in the polarity it wants
        # (alpha 1 = opaque = transparency 0), so deriving it here saves every
        # expression a reverse node -- and keeps the default write two lines,
        # which is what the full-parity tail recognizer matches on.
        try:
            _ot = locals_out.get("outTransparency")
            if _ot is None:
                _t = min(1.0, max(0.0, 1.0 - float(out_alpha)))
                tr, tg, tb = _t, _t, _t
            else:
                tr, tg, tb = (float(_ot[0]), float(_ot[1]), float(_ot[2]))
            ot_handle = data_block.outputValue(MPyFile.aOutTransparency)
            ot_handle.setMFloatVector(om.MFloatVector(tr, tg, tb))
            ot_handle.setClean()
        except Exception:
            pass

        # outSize: the pixel dimensions of the image this node reads, so it is a
        # property of `fileName` (+ the embedded fallback) rather than of the
        # compute -- read_texture() is cached, so this costs nothing beyond the
        # load the compute already did, and a node that reads no image reports
        # (0, 0). An explicit assignment still wins.
        try:
            _os = locals_out.get("outSize")
            if _os is None:
                _os = _derive_out_size(self_proxy)
            os_handle = data_block.outputValue(MPyFile.aOutSize)
            os_handle.set2Float(float(_os[0]), float(_os[1]))
            os_handle.setClean()
        except Exception:
            pass

        # Commit any USER-added outputs the expression set (the native
        # outColor/outAlpha/outTransparency/outSize were written just above).
        try:
            helpers.write_user_outputs(
                data_block,
                self.thisMObject(),
                output_map,
                locals_out,
                skip=_MANAGED_OUTPUT_NAMES,
            )
        except Exception:
            pass

        # Commit the stored-var diff to the thread-safe in-memory store (no DG
        # access, no cmds.setAttr); flushed to the plug on scene save/export.
        storage_diff = self_proxy.diff_storage()
        if storage_diff:
            new_stored = dict(stored_vars)
            for k, v in storage_diff.items():
                if v is None:
                    new_stored.pop(k, None)
                else:
                    new_stored[k] = v
            _svstore.set_for_compute(node_obj, new_stored)

        try:
            data_block.setClean(plug)
        except Exception:
            pass

        return self

    # ------------------------------------------------------------------
    # Viewport (VP2) entry point -- called by MPyFileOverride.updateShader
    # ------------------------------------------------------------------

    def runViewport(
        self,
        shader,
        mappings,
        stored_vars_str: str  | None = None,
        input_attrs_str: str  | None = None,
        user_inputs:     dict | None = None,
        presets:         dict | None = None,
    ) -> None:
        """Execute the Viewport source with bridge-injected helpers.

        Thread-safe variant: ``MPyFileOverride.updateDG`` (which Maya
        invokes on the main thread before ``updateShader``) caches the
        ``_storedVarsData`` and ``_inputAttrs`` plug strings on the
        override instance, then passes them in here. That way runViewport
        can run on the VP2 render thread without touching the unsafe
        ``MFnDependencyNode.findPlug`` API.

        BAREBONES short-circuit: when
        ``BAREBONES_MODE`` is True, route through the inline
        customFileTexture-style helper instead. Same purpose as in
        compute() -- prove that the swatch / viewport behaviour comes
        from the integration layer, not from the math.

        Bindings exposed in the expression's compute_locals tier (so
        the user reaches them via ``self.X``):

            self.shader            -- the MShaderInstance Maya wants us
                                      to push texture + sampler params
                                      into.
            self.mappings          -- the MAttributeParameterMappingList
                                      Maya hands updateShader.
            self.texture_manager   -- MRenderer.getTextureManager().
            self.state_manager     -- omr.MStateManager (class).

        Same Init namespace + ``self`` plug-tree surface as the
        Compute expression. Stored-var diffs round-trip back to
        ``_storedVarsData`` for cross-call state.
        """
        if type(self).BAREBONES_MODE:
            self._run_viewport_barebones(shader, mappings)
            return
        if self._viewport_code is None:
            return

        node_obj = self.thisMObject()

        # Decode stored vars from the cached string (read by updateDG on
        # the main thread). Fall back to a fresh MFn read only when no
        # string was passed in AND we're on the main thread.
        if stored_vars_str is None:
            import threading as _threading
            if _threading.current_thread() is _threading.main_thread():
                try:
                    stored_vars_str = om.MFnDependencyNode(node_obj).findPlug(
                        MPyFile._stored_vars_data_attr, True
                    ).asString()
                except Exception:
                    stored_vars_str = ""
            else:
                stored_vars_str = ""

        # Read stored vars UNCONDITIONALLY, mirroring compute(). In a live
        # session load_and_clear_all() moves stored vars into the in-memory
        # cache and CLEARS the plug to "", which ``load_for_compute(obj, "")``
        # is designed to serve; it is also "" on the VP2 render thread. The old
        # ``if stored_vars_str:`` guard skipped the read in both cases, so a
        # stateful Viewport source re-ran from ``{}`` every frame.
        try:
            stored_vars = _svstore.load_for_compute(node_obj, stored_vars_str or "")
        except Exception:
            stored_vars = {}

        try:
            texture_manager = omr.MRenderer.getTextureManager()
        except Exception:
            texture_manager = None

        viewport_locals = {
            "time":            TimeFloat(_viewport_time_value()),
            "shader":          shader,
            "mappings":        mappings,
            "texture_manager": texture_manager,
            "state_manager":   omr.MStateManager,
        }
        # Seed user inputs (read on the main thread in updateDG) so
        # ``self.<user input>`` resolves on the safe tier, not the unsafe
        # render-thread plug path. ``setdefault`` so a bridge handle wins.
        if user_inputs:
            for _in_name, _in_val in user_inputs.items():
                viewport_locals.setdefault(_in_name, _in_val)
        # Same treatment for the PRESET plugs. read_texture / sample_texture
        # read these off ``self``; the plug tier cannot serve them here, so a
        # Viewport tier calling self.read_texture() failed on 'colorSpace'.
        # setdefault keeps a user input of the same name winning, matching the
        # precedence compute() gives preset_locals.
        if presets:
            for _p_name, _p_val in presets.items():
                viewport_locals.setdefault(_p_name, _p_val)

        self_proxy = SelfProxy(
            node_obj,
            datablock       = None,
            user_storage    = stored_vars,
            compute_locals  = viewport_locals,
            node_type_label = type(self).__name__,
            node_type_name  = type(self).NODE_NAME,
        )

        # Self-only: user inputs are reached via self.X (seeded into the
        # SelfProxy snapshot above), NOT as bare names.
        namespace         = build_exec_namespace()
        namespace["self"] = self_proxy

        captured: list[str] = []

        def _on_err(msg):
            captured.append(msg)

        ok = exec_with_profile_watch(
            self._viewport_code,
            namespace,
            log_event_name = "<mpyfile-viewport>",
            on_error       = _on_err,
            node_obj       = node_obj,
        )
        if not ok and captured:
            sys.stderr.write(f"[mPyFile viewport] {captured[0]}")
            try:
                from mpynode._common.util.log_bus import log as _log_bus

                _log_bus(f"[mPyFile] {captured[0]}", level="error")
            except Exception:
                pass

        # Commit the stored-var diff to the in-memory store (safe from the VP2
        # render thread; flushed to the plug on scene save/export).
        storage_diff = self_proxy.diff_storage()
        if storage_diff:
            new_stored = dict(stored_vars)
            for k, v in storage_diff.items():
                if v is None:
                    new_stored.pop(k, None)
                else:
                    new_stored[k] = v
            _svstore.set_for_compute(node_obj, new_stored)


# ===========================================================================
# MPyFileOverride -- VP2 MPxShadingNodeOverride
# ===========================================================================


_FRAGMENT_NAME = "mayaFileTexture"
"""Maya's built-in fragment graph for the stock ``file`` node. We reuse
it verbatim so the Hypershade swatch + viewport shading come for free;
all we do in updateShader is rebind the texture + sampler state."""


class MPyFileOverride(omr.MPxShadingNodeOverride):
    """VP2 override for ``mPyFile``.

    Reuses Maya's built-in ``mayaFileTexture`` shade-fragment graph.

    In BAREBONES mode (the default while we bisect the swatch bug),
    this override does the texture-upload + sampler-binding INLINE
    on the override instance -- mirroring customFileTexture's
    architecture exactly: plug reads in updateDG (cache on the
    instance), GPU upload + setParameter in updateShader (use the
    cached values). Maya uses the plug reads in updateDG to track
    override dependencies; without them in updateDG, Maya doesn't
    know the override needs to refresh when the upstream file
    changes -- and the bound texture stays stale or unset.

    When BAREBONES_MODE is False, the override delegates to the
    MPxNode's runViewport (which runs the user-edited Viewport
    source).
    """

    @staticmethod
    def creator(obj):
        return MPyFileOverride(obj)

    def __init__(self, obj):
        super().__init__(obj)
        self._node_obj = obj
        # Thread safety: cache the MPxNode python instance in updateDG (main
        # thread) so updateShader (render thread) can call runViewport without
        # an MFnDependencyNode + userNode() lookup.
        self._mpx_node = None
        # Cached plug values, populated in updateDG. Mirrors
        # customFileTexture's pattern -- see updateDG docstring.
        self._file_name         = ""
        self._cs_index          = 0
        self._pre_filter        = False
        self._pre_filter_kernel = kPreFilterGaussian
        self._pre_filter_radius = 2.0
        self._filter_mode       = kFilterLinear
        self._max_anisotropy    = 1
        self._mipmap_mode       = kMipmapAuto
        self._mip_lod_bias      = 0.0
        self._min_lod           = 0
        self._max_lod           = 16
        self._wrap_u            = kWrapWrap
        self._wrap_v            = kWrapWrap
        self._border_color      = (0.0, 0.0, 0.0)
        # Track what was last uploaded so we don't re-allocate the
        # texture on every updateShader call.
        self._last_acquired_file      = None
        self._last_acquired_cs        = None
        self._last_acquired_prefilter = None
        # Internal-plug strings: populated by updateDG (main thread), read by
        # updateShader / runViewport (VP2 render thread) so neither has to make
        # an unsafe findPlug call there.
        self._stored_vars_str: str = ""
        self._input_attrs_str: str = ""
        # User-input values, read on the MAIN thread in updateDG and passed into
        # runViewport so ``self.<user input>`` resolves on the safe tier.
        #
        # NOTE: reading a plug here does NOT register it as an OGS dependency of
        # the override -- only fragment-mapped plugs (fileName via
        # usedAsFilename, uvCoord via getCustomMappings) are tracked, so a
        # manual preset / user-input edit does not refresh the viewport on its
        # own. That comes from the per-node AttributeChanged callback
        # (register_attr_refresh_callbacks). This read is purely the
        # render-thread-safe value cache.
        self._user_inputs: dict = {}

    def supportedDrawAPIs(self):
        return omr.MRenderer.kAllDevices

    def fragmentName(self):
        return _FRAGMENT_NAME

    def allowConnections(self):
        return True

    def valueChangeRequiresFragmentRebuild(self, plug):
        # All our knobs feed sampler / texture state, not the fragment
        # graph structure. No recompile needed.
        return False

    def outputForConnection(self, sourcePlug, destinationPlug):
        try:
            name = sourcePlug.partialName(useLongNames=True)
        except Exception:
            return ""
        if name.startswith("outColor"):
            return "outColor"
        # The stock `mayaFileTexture` fragment graph already carries this: its
        # mayaFileTextureOutput struct declares `float3 outTransparency` and
        # mayaFileTextureColorEffects fills it with 1 - outAlpha -- the same
        # derivation the DG side does. Without the mapping VP2 cannot resolve a
        # .transparency connection at all, so the viewport and the (DG-driven)
        # swatch disagree. outSize gets no entry: the fragment has no such output.
        if name.startswith("outTransparency"):
            return "outTransparency"
        if name == "outAlpha":
            return "outAlpha"
        return ""

    def getCustomMappings(self, mappings):
        # Make sure VP2 routes uvCoord through to the fragment input.
        mappings.append(
            omr.MAttributeParameterMapping("uvCoord", "uvCoord", True, True)
        )

    def updateDG(self):
        """Read all the preset plug values and cache them on the
        instance. Maya uses these reads to track the override's
        dependencies -- which plugs need to dirty the shader. WITHOUT
        these reads in updateDG, Maya doesn't know the override
        depends on uvCoord / fileName / etc., and updateShader may
        run with stale or unset values. customFileTexture follows
        this exact pattern."""
        try:
            fn = om.MFnDependencyNode(self._node_obj)
            # Resolve + cache the MPxNode python instance here: Maya guarantees
            # updateDG runs on the main thread, so updateShader (render thread)
            # can reuse it with no MFn lookups.
            try:
                self._mpx_node = fn.userNode()
            except Exception:
                self._mpx_node = None
            self._file_name = fn.findPlug("fileName", False).asString()
            self._cs_index = int(
                fn.findPlug("colorSpace", False).asShort()
            )
            self._pre_filter = bool(
                fn.findPlug("preFilter", False).asBool()
            )
            self._pre_filter_kernel = int(
                fn.findPlug("preFilterKernel", False).asShort()
            )
            self._pre_filter_radius = float(
                fn.findPlug("preFilterRadius", False).asFloat()
            )
            self._filter_mode = int(
                fn.findPlug("filterMode", False).asShort()
            )
            self._max_anisotropy = max(1, min(16, int(
                fn.findPlug("maxAnisotropy", False).asInt()
            )))
            self._mipmap_mode = int(
                fn.findPlug("mipmapMode", False).asShort()
            )
            self._mip_lod_bias = float(
                fn.findPlug("mipLODBias", False).asFloat()
            )
            self._min_lod = int(fn.findPlug("minLOD", False).asInt())
            self._max_lod = int(fn.findPlug("maxLOD", False).asInt())
            self._wrap_u  = int(fn.findPlug("wrapModeU", False).asShort())
            self._wrap_v  = int(fn.findPlug("wrapModeV", False).asShort())
            bc            = fn.findPlug("borderColor", False)
            self._border_color = (
                bc.child(0).asFloat(),
                bc.child(1).asFloat(),
                bc.child(2).asFloat(),
            )
            # Cache user-expression-path internal-plug strings (runViewport
            # reads these later on the VP2 render thread).
            try:
                self._stored_vars_str = fn.findPlug(
                    MPyFile._stored_vars_data_attr, True
                ).asString()
            except Exception:
                self._stored_vars_str = ""
            try:
                self._input_attrs_str = fn.findPlug(
                    MPyFile._input_attrs_attr, True
                ).asString()
            except Exception:
                self._input_attrs_str = ""
            # Read EVERY user input plug now (main thread) so runViewport can
            # seed them into the safe ``self.<name>`` tier on the render thread,
            # where findPlug is unsafe. This read does NOT register an OGS
            # dependency; the viewport refresh on a manual edit comes from
            # register_attr_refresh_callbacks (see Bug A below).
            try:
                input_map = (
                    serialization.decode_attr_map(self._input_attrs_str)
                    if self._input_attrs_str else {}
                )
                self._user_inputs = (
                    helpers.read_user_inputs_dict(self._node_obj, input_map)
                    if input_map else {}
                )
            except Exception:
                self._user_inputs = {}
        except Exception as exc:
            sys.stderr.write(
                "[MPyFileOverride.updateDG] plug read failed: %s\n" % exc
            )

    def _preset_snapshot(self):
        """The mPyFile preset plugs updateDG already cached, by plug name.

        These are the presets ``file_methods.read_texture`` /
        ``sample_texture`` read off ``self`` -- on the render thread the plug
        tier cannot serve them, so a Viewport tier calling ``self.read_texture()``
        died on ``'colorSpace'`` even once the blessed methods resolved. Both
        shipped Viewport tiers that read an image (File Simple, File Scanline)
        need this. updateDG runs on the MAIN thread, so every value here was
        read safely; runViewport only copies them into compute_locals."""
        return {
            "fileName":        self._file_name,
            "colorSpace":      self._cs_index,
            "preFilter":       self._pre_filter,
            "preFilterKernel": self._pre_filter_kernel,
            "preFilterRadius": self._pre_filter_radius,
            "wrapModeU":       self._wrap_u,
            "wrapModeV":       self._wrap_v,
            "borderColor":     self._border_color,
        }

    def updateShader(self, shader, mappings):
        """In BAREBONES mode, do the texture upload + sampler binding
        directly on this override instance using the values cached in
        updateDG. customFileTexture-style. Otherwise delegate to the
        MPxNode's user-Viewport path."""
        import sys


        if MPyFile.BAREBONES_MODE:
            self._update_shader_barebones(shader, mappings)
            return

        # User-Viewport path: delegate via the cached ``self._mpx_node``
        # (resolved on the main thread in updateDG). Calling MFnDependencyNode +
        # userNode() from this VP2 render-thread context can crash Maya.
        if self._mpx_node is None:
            return
        try:
            self._mpx_node.runViewport(
                shader,
                mappings,
                stored_vars_str = self._stored_vars_str,
                input_attrs_str = self._input_attrs_str,
                user_inputs     = self._user_inputs,
                presets         = self._preset_snapshot(),
            )
        except Exception as exc:
            sys.stderr.write(
                "[mPyFile override] runViewport failed: %s\n" % exc
            )

    def _update_shader_barebones(self, shader, mappings):
        """Inline customFileTexture-style updateShader. Uses the
        values cached by updateDG. Re-uploads the texture only when
        the file / colour-space / pre-filter settings change (same
        guard customFileTexture uses)."""
        import sys
        sys.stderr.write(
            "[MPyFileOverride._update_shader_barebones] file=%r cs=%d\n"
            % (self._file_name, self._cs_index)
        )

        # Find the fragment's texture + sampler parameters.
        map_param  = None
        samp_param = None
        try:
            for pname in shader.parameterList():
                try:
                    ptype = shader.parameterType(pname)
                except Exception:
                    continue
                if (map_param is None
                        and ptype == omr.MShaderInstance.kTexture2):
                    map_param = pname
                elif (samp_param is None
                        and ptype == omr.MShaderInstance.kSampler):
                    samp_param = pname
                if map_param and samp_param:
                    break
        except Exception:
            return

        # ALWAYS re-bind; never short-circuit on the _last_acquired_* cache.
        # That cache only helps if Maya reuses one override instance, but Maya
        # dispatches updateShader against DIFFERENT MShaderInstances (viewport,
        # material viewer, browser swatch generator) with no way to tell them
        # apart. acquireTexture is internally cached by tex_name, so the GPU
        # upload still happens once per unique (path, cs, prefilter) and
        # re-binding costs only the setParameter call.
        sys.stderr.write(
            "[MPyFileOverride._update_shader_barebones] map=%r samp=%r "
            "(always rebinding -- cache disabled)\n"
            % (map_param, samp_param)
        )
        if map_param is not None and self._file_name:
            if MPyFile.DUMMY_TEXTURE_MODE and _np is not None:
                # Solid-red 64x64 RGBA float32 in scene-linear. Renders red =
                # the GPU pipeline works; else the fragment binding is broken.
                linear         = _np.zeros((64, 64, 4), dtype=_np.float32)
                linear[..., 0] = 1.0  # R
                linear[..., 3] = 1.0  # A
                sys.stderr.write(
                    "[MPyFileOverride._update_shader_barebones] "
                    "DUMMY_TEXTURE_MODE = solid red 64x64\n"
                )
            else:
                linear = _tex.load_linear_pixels(
                    self._file_name, self._cs_index,
                    self._pre_filter, self._pre_filter_kernel,
                    self._pre_filter_radius,
                )
            sys.stderr.write(
                "[MPyFileOverride._update_shader_barebones] linear=%s\n"
                % ("OK" if linear is not None else "None")
            )
            if linear is not None:
                texture = _tex.upload_linear_texture(
                    linear, self._file_name, self._cs_index,
                    self._mipmap_mode, self._pre_filter,
                    self._pre_filter_kernel, self._pre_filter_radius,
                    name_prefix="mpyfile::bb::",
                    dummy_name=("mpyfile::bb::DUMMY_RED_64x64"
                                if MPyFile.DUMMY_TEXTURE_MODE else None),
                )
                sys.stderr.write(
                    "[MPyFileOverride._update_shader_barebones] texture=%s\n"
                    % ("OK" if texture is not None else "None")
                )
                if texture is not None:
                    try:
                        assignment         = omr.MTextureAssignment()
                        assignment.texture = texture
                        shader.setParameter(map_param, assignment)
                        sys.stderr.write(
                            "[MPyFileOverride._update_shader_barebones] "
                            "setParameter %s OK\n" % map_param
                        )
                    finally:
                        try:
                            omr.MRenderer.getTextureManager().releaseTexture(
                                texture
                            )
                        except Exception:
                            pass

        # Sampler state (always re-apply).
        if samp_param is not None:
            try:
                desc = omr.MSamplerStateDesc()
                desc.setDefaults()
                desc.filter        = _tex.vp2_filter_for(self._filter_mode)
                desc.maxAnisotropy = self._max_anisotropy
                desc.mipLODBias    = self._mip_lod_bias
                desc.minLOD        = self._min_lod
                desc.maxLOD        = self._max_lod
                desc.addressU      = _tex.vp2_wrap_for(self._wrap_u)
                desc.addressV      = _tex.vp2_wrap_for(self._wrap_v)
                try:
                    desc.borderColor = (
                        float(self._border_color[0]),
                        float(self._border_color[1]),
                        float(self._border_color[2]),
                        1.0,
                    )
                except Exception:
                    pass
                shader.setParameter(
                    samp_param,
                    omr.MStateManager.acquireSamplerState(desc),
                )
            except Exception:
                pass


def _viewport_time_value() -> float:
    """Current frame for the VP2 viewport path. Runs on the main thread
    (updateShader / prepareForDraw), so ``cmds.currentTime`` is safe here
    (unlike ``compute()``, which reads the hidden ``_timeIn`` plug)."""
    try:
        from maya import cmds

        return float(cmds.currentTime(query=True))
    except Exception:
        return 0.0


def _on_time_change(_client_data=None) -> None:
    """Fired on every timeline change. mPyFile is always time-aware (so
    image sequences animate without manual wiring), so dirty outColor on
    EVERY instance to force a per-frame texture re-read. ``_timeIn`` is
    deliberately kept out of ``attributeAffects`` (it breaks the VP2
    fragment binding), so this ``dgdirty`` is how the per-frame refresh
    propagates -- the same mechanism expression / viewport edits use."""
    try:
        from maya import cmds

        for node in cmds.ls(type=MPyFile.NODE_NAME) or []:
            try:
                cmds.dgdirty(node + ".outColor")
            except Exception:
                pass
    except Exception:
        pass


def register_time_change_callback() -> int:
    """Install the timeChanged callback. Tracked via CALLBACK_MANAGER so
    it's removed cleanly on plugin unload."""
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API2

        cb_id = om.MEventMessage.addEventCallback("timeChanged", _on_time_change)
        return CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, OWNER_API2)
    except Exception as exc:
        sys.stderr.write(
            "[mPyFile] failed to register time-change callback: %s\n" % exc
        )
        return -1


# ===========================================================================
# Manual-attribute viewport refresh (Bug A)
# ===========================================================================
#
# Only ``fileName`` (usedAsFilename -> the mayaFileTexture fragment's
# fileTextureName param) and ``uvCoord`` (custom-mapped in getCustomMappings)
# are registered with Maya's OGS as this override's dependencies, so editing
# either auto-refreshes. Every OTHER preset / user input is read in updateDG
# only to CACHE the value -- that read registers no OGS dependency, so a manual
# edit dirties nothing the viewport watches and the surface stays stale until a
# timeline scrub forces a redraw (via _on_time_change's per-frame dgdirty --
# which is exactly why scrubbing "fixes" it).
#
# This installs a per-node AttributeChanged callback supplying the SAME trigger
# a scrub gets for free: dgdirty outColor + a deferred VP2 refresh. It
# deliberately does NOT add these plugs to attributeAffects / getCustomMappings
# or flip valueChangeRequiresFragmentRebuild -- any of those can trip the Maya
# 2026 fragment-binding trap (white viewport / black swatch).


# Names that must NEVER kick a refresh: the outputs (refreshing on an output
# write would feed back into a redraw loop) and the internal hidden
# expression-storage plugs (all `_`-prefixed).
_NO_REFRESH_ATTRS = frozenset(
    set(_MANAGED_OUTPUT_NAMES)
    | set(MANAGED_SHADER_OUTPUTS)
)


def _is_viewport_refresh_attr(attr_name: str) -> bool:
    """True if setting ``attr_name`` on an mPyFile should kick a VP2 refresh.

    Presets (colorSpace / preFilter / wrap / border / the GPU sampler knobs)
    and user inputs (tIn, ...) all feed the look but are not fragment-mapped,
    so a manual edit needs an explicit refresh. Outputs and internal hidden
    plugs (``_``-prefixed) are excluded."""
    if not attr_name:
        return False
    if attr_name in _NO_REFRESH_ATTRS:
        return False
    if attr_name.startswith("_"):
        return False
    return True


# Coalescing latch: executeDeferred does NOT merge duplicate callables, so a
# slider drag emitting N setAttrs would queue N full refreshes. While one is
# pending we skip enqueuing more; the queued refresh redraws everything dirtied
# in the meantime. Reset when the refresh actually runs.
_refresh_pending = False


def _refresh_active_view() -> None:
    """Force a VP2 redraw. Runs deferred (main-thread idle) so it never fires
    synchronously from inside the AttributeChanged callback."""
    global _refresh_pending
    _refresh_pending = False
    try:
        from maya import cmds

        cmds.refresh()
    except Exception:
        pass


def _dirty_and_refresh(node_name: str) -> None:
    """Dirty ``node_name``'s outColor and kick a VP2 redraw so a manual preset /
    user-input edit shows immediately -- the same trigger pairing a timeline
    scrub supplies. Defensive: never raise inside a DG callback."""
    global _refresh_pending
    try:
        from maya import cmds

        # dgdirty EVERY changed node; only the (global) refresh coalesces.
        try:
            cmds.dgdirty(node_name + ".outColor")
        except Exception:
            pass
        # Defer the redraw: refreshing synchronously from inside an
        # AttributeChanged callback risks re-entrancy. The _refresh_pending
        # latch coalesces a burst into ONE trailing refresh. (Headless mayapy
        # has no idle loop, so the deferred refresh just no-ops.)
        if _refresh_pending:
            return
        try:
            from maya.utils import executeDeferred

            _refresh_pending = True
            executeDeferred(_refresh_active_view)
        except Exception:
            _refresh_pending = False
    except Exception:
        pass


# MObjectHandle.hashCode() -> callback id; dedup + teardown bookkeeping. Cleared
# on scene change (Maya can reuse an MObject slot, hence hashCode, for a freshly
# loaded node) and on plugin unload (hashCodes survive an unload/reload, so a
# stale entry would block reinstall).
_ATTR_REFRESH_CB: dict = {}


def _reset_attr_refresh_state() -> None:
    """Clear the per-node dedup map + the refresh latch. Called on plugin unload
    (see mpynode_api2.uninitializePlugin) so a reload re-installs cleanly, and on
    scene change."""
    global _refresh_pending
    _ATTR_REFRESH_CB.clear()
    _refresh_pending = False


def _install_attr_refresh_callback(node_obj) -> None:
    """Install a per-node AttributeChanged viewport-refresh callback. Idempotent
    by MObjectHandle.hashCode()."""
    try:
        handle = om.MObjectHandle(node_obj)
        code   = handle.hashCode()
    except Exception:
        return
    if code in _ATTR_REFRESH_CB:
        return

    # kAttributeSet = direct setAttr (channel-box / AE edit); kIncomingDirection
    # = connect/disconnect. kOtherPlugSet is DELIBERATELY excluded: a connected
    # source pushing a value (time1.outTime -> tIn every frame) fires it, and
    # refreshing per-event would be a storm (the timeChanged callback already
    # covers animated values). Trade-off: a preset driven by an upstream node
    # won't auto-refresh, but a scrub or manual edit still does.
    relevant = om.MNodeMessage.kAttributeSet | om.MNodeMessage.kIncomingDirection

    def _cb(msg, plug, other_plug, _client, _h=handle):
        if not (msg & relevant):
            return
        try:
            if not _h.isValid():
                return
        except Exception:
            return
        # Don't fight the file loader: nodes are assigned their stored values
        # during read, and the scene redraws once after open anyway.
        try:
            if om.MFileIO.isReadingFile():
                return
        except Exception:
            pass
        try:
            attr_name = om.MFnAttribute(plug.attribute()).name
        except Exception:
            return
        if not _is_viewport_refresh_attr(attr_name):
            return
        try:
            node_name = om.MFnDependencyNode(_h.object()).name()
        except Exception:
            return
        # Looked up as a module global so tests can spy on it.
        _dirty_and_refresh(node_name)

    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API2

        cb_id = om.MNodeMessage.addAttributeChangedCallback(node_obj, _cb)
        CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, OWNER_API2)
        _ATTR_REFRESH_CB[code] = cb_id
    except Exception as exc:
        sys.stderr.write(
            "[mPyFile] attr-refresh callback install failed: %s\n" % exc
        )


def register_attr_refresh_callbacks() -> None:
    """Install per-node viewport-refresh AttributeChanged callbacks for every
    existing mPyFile + a node-added hook for future ones + a scene-open sweep,
    and clear the dedup map on scene change. Tracked via CALLBACK_MANAGER
    (OWNER_API2) so it tears down cleanly on plugin unload."""
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API2
        from maya import cmds
    except Exception:
        return

    def _sweep_existing():
        try:
            for n in cmds.ls(type=MPyFile.NODE_NAME) or []:
                try:
                    sel = om.MSelectionList()
                    sel.add(n)
                    _install_attr_refresh_callback(sel.getDependNode(0))
                except Exception:
                    pass
        except Exception:
            pass

    _sweep_existing()

    def _on_added(node_obj, _client):
        try:
            _install_attr_refresh_callback(node_obj)
        except Exception:
            pass

    try:
        cb_id = om.MDGMessage.addNodeAddedCallback(_on_added, MPyFile.NODE_NAME)
        CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, OWNER_API2)
    except Exception as exc:
        sys.stderr.write(
            "[mPyFile] node-added attr-refresh hook failed: %s\n" % exc
        )

    # addNodeAddedCallback can race a file load and miss nodes; the kAfterOpen
    # sweep is the idempotent backstop (mirrors auto_dirty).
    def _on_after_open(_client):
        _sweep_existing()

    try:
        cb_id = om.MSceneMessage.addCallback(
            om.MSceneMessage.kAfterOpen, _on_after_open
        )
        CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, OWNER_API2)
    except Exception:
        pass

    # Clear the dedup map before the scene-wide MObject invalidation so stale
    # hashCodes from the previous scene don't block fresh installs.
    def _clear(_client):
        _reset_attr_refresh_state()

    for evt_name in ("kBeforeNew", "kBeforeOpen"):
        evt = getattr(om.MSceneMessage, evt_name, None)
        if evt is None:
            continue
        try:
            cb_id = om.MSceneMessage.addCallback(evt, _clear)
            CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_API2
            )
        except Exception:
            pass


# ===========================================================================
# Node-lifecycle warming (Hypershade visibility + black-render fix)
# ===========================================================================
#
# Two defects share one root: a mPyFile created OUTSIDE ``shadingNode
# -asTexture`` (bare ``cmds.createNode`` -- the .mpn import / template /
# deserialize / duplicate / paste paths) skips the main-thread bookkeeping a
# texture node needs:
#
#   * P1 (Hypershade) -- ``-asTexture`` wires ``node.message ->
#     defaultTextureList1.textures``; ``createNode`` does not, so the
#     Hypershade can't graph the node. ``ensure_in_texture_list`` supplies it.
#
#   * P2 (black render/swatch) -- the user expression reads init-namespace
#     helpers (``_read_image``, ``np``). The swatch generator + Arnold evaluate
#     on WORKER threads, where ``ensure_init_namespace_for_mobject`` bails (its
#     lazy ``cmds.getAttr`` reload isn't thread-safe) unless the namespace is
#     ALREADY in the main-thread registry. A fresh node whose registration
#     races the swatch thread is evaluated with an EMPTY namespace ->
#     ``NameError`` BEFORE ``self.outColor`` is assigned -> the output stays at
#     its (0,0,0) default = BLACK. (Main-thread DG compute works because the
#     lazy reload fires there, which is why scrubbing "fixes" it.)
#     ``warm_init_namespace`` registers on the main thread first.


def ensure_in_texture_list(node_name: str) -> bool:
    """Wire ``node_name.message -> defaultTextureList1.textures`` so the
    Hypershade can graph the node (parity with ``shadingNode -asTexture``).

    Idempotent AND self-healing: it inspects the texture-list's source plugs
    (not just the node's message destinations) so it is robust to the create-
    time race where ``shadingNode -asTexture`` ALSO wires this connection -- if
    a duplicate ``message -> textures[*]`` element exists (e.g. created when this
    ran inline before ``-asTexture`` finished, or restored from a .ma saved with
    that bug), the extras are disconnected so exactly one remains. Returns True
    if the node is (now) a single member, False on any failure. Never raises."""
    try:
        from maya import cmds
    except Exception:
        return False
    try:
        if not cmds.objExists(node_name):
            return False
        msg = node_name + ".message"
        if not cmds.objExists("defaultTextureList1"):
            # Default node is created on demand by shadingNode; make it so the
            # connection has a destination even in a minimal scene.
            try:
                cmds.createNode(
                    "defaultTextureList", name="defaultTextureList1", shared=True
                )
            except Exception:
                pass
        # Enumerate (textures[i], sourcePlug) pairs already feeding the list.
        pairs = (
            cmds.listConnections(
                "defaultTextureList1.textures",
                connections=True, plugs=True,
                source=True, destination=False,
            )
            or []
        )
        mine_dests = [
            pairs[i] for i in range(0, len(pairs) - 1, 2) if pairs[i + 1] == msg
        ]
        if mine_dests:
            # Already a member. Drop any duplicate element(s) so exactly one
            # connection remains (race / legacy-.ma self-heal).
            for extra_dest in mine_dests[1:]:
                try:
                    cmds.disconnectAttr(msg, extra_dest)
                except Exception:
                    pass
            return True
        cmds.connectAttr(msg, "defaultTextureList1.textures", nextAvailable=True)
        return True
    except Exception:
        return False


def warm_init_namespace(node_name: str) -> bool:
    """Register ``node_name``'s init namespace into the main-thread registry
    NOW, so a later Hypershade-swatch / Arnold worker-thread eval resolves the
    init helpers via the non-lazy lookup instead of ``NameError``-ing to black.

    Returns True if an init namespace is now registered, False if the node has
    no usable ``_initSource``. Best-effort; never raises. Runs on the main
    thread only (the caller defers it there)."""
    try:
        from maya import cmds
    except Exception:
        return False
    try:
        if not cmds.objExists(node_name):
            return False
        if not cmds.attributeQuery("_initSource", node=node_name, exists=True):
            return False
        src = cmds.getAttr(node_name + "._initSource") or ""
        if not src.strip():
            return False
        from mpynode._common.lifecycle import init_registry as ir

        return bool(ir.register_init_source(node_name, src))
    except Exception:
        return False


def compiled_texture_types() -> tuple:
    """Node types from LOADED plug-ins that are compiled mPyFile-derived textures.

    A converted mPyFile ships as its OWN C++ node type (``fileTexture``,
    ``compositeTexture``, ...), not as an ``mPyFile``, so the type-filtered hooks
    below never saw one -- which is why a converted node could not be graphed in
    the Hypershade while its interpreted twin could. ``ls -textures`` reads
    ``defaultTextureList1`` membership, not classification, so a node nothing
    wires into that list is invisible there no matter how it is classified.

    Identified by the classification the mPyFile emitter always writes
    (``texture/2d`` AND ``swatch/2dTextureSwatchGen``) on a type that some loaded
    PLUG-IN provides. Stock Maya textures (``file``, ``checker``) are built in
    rather than plug-in-provided, so they are never in this set.

    Recomputed per call rather than cached: a compiled bundle can be loaded after
    api2 initialises, and the scene-open sweep is what picks its types up.
    Best-effort -- on any failure returns ``()`` and the hooks stay mPyFile-only.
    """
    try:
        from maya import cmds
    except Exception:
        return ()
    found = set()
    try:
        for plug in (cmds.pluginInfo(query=True, listPlugins=True) or []):
            try:
                types = cmds.pluginInfo(plug, query=True, dependNode=True) or []
            except Exception:
                continue
            for ntype in types:
                if ntype == MPyFile.NODE_NAME:
                    continue          # the interpreted node is hooked directly
                try:
                    classif = cmds.getClassification(ntype) or []
                except Exception:
                    continue
                for entry in classif:
                    if ("texture/2d" in entry
                            and "swatch/2dTextureSwatchGen" in entry):
                        found.add(ntype)
                        break
    except Exception:
        return ()
    return tuple(sorted(found))


def _warm_node_lifecycle(node_name: str) -> None:
    """Apply BOTH warmings to one node + dgdirty so an already-rendered cold
    (black) swatch re-renders warm. Main-thread only. Never raises."""
    try:
        ensure_in_texture_list(node_name)
    except Exception:
        pass
    warmed = False
    try:
        warmed = warm_init_namespace(node_name)
    except Exception:
        warmed = False
    if warmed:
        try:
            from maya import cmds

            cmds.dgdirty(node_name + ".outColor")
        except Exception:
            pass


def register_node_lifecycle_callbacks() -> None:
    """Install a node-added hook (+ scene-open sweep) that warms every mPyFile
    from ANY source (create / shadingNode / .mpn import / template / file-open):
    P1 (Hypershade-graphable) + P2 (no black swatch/render on first worker eval).

    Covers the COMPILED types too (``compiled_texture_types``). A converted
    mPyFile is its own C++ node type, so an mPyFile-only filter left every
    converted texture out of ``defaultTextureList1`` and therefore out of
    ``ls -textures`` -- graphable in Python, invisible in C++. P2 is a no-op on a
    compiled node (``warm_init_namespace`` returns False when the node has no
    ``_initSource``), so the shared warm is safe to reuse for both.

    The per-node work is DEFERRED to the main-thread idle: at node-added time
    the .mpn import has not yet set ``_initSource`` (it addAttr/setAttrs AFTER
    ``createNode``), and touching the DG mid-creation is unsafe. Tracked via
    CALLBACK_MANAGER (OWNER_API2) so it tears down on plugin unload."""
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API2
        from maya import cmds
    except Exception:
        return

    def _sweep_existing():
        try:
            for ntype in (MPyFile.NODE_NAME,) + compiled_texture_types():
                for n in cmds.ls(type=ntype) or []:
                    _warm_node_lifecycle(n)
        except Exception:
            pass

    _sweep_existing()

    def _on_added(node_obj, _client):
        # Resolve the name now (cheap) but defer the DG work. Skip while the
        # file is loading -- stored connections + the kAfterOpen sweep cover
        # that path, and touching the DG during read is unsafe.
        try:
            if om.MFileIO.isReadingFile():
                return
        except Exception:
            pass
        try:
            name = om.MFnDependencyNode(node_obj).name()
        except Exception:
            return
        try:
            from maya.utils import executeDeferred

            executeDeferred(_warm_node_lifecycle, name)
        except Exception:
            # No maya.utils (non-Maya context): skip. Deliberately NOT inline --
            # this callback fires DURING createNode, before ``-asTexture``
            # finishes its own texture-list wiring, so an inline
            # ensure_in_texture_list would race it into a DUPLICATE connection.
            # In batch (no idle loop) the warm never runs -- acceptable: no
            # Hypershade, and compute() is main-thread where the lazy reload
            # works.
            pass

    # One hook per type: addNodeAddedCallback takes a SINGLE type filter, and a
    # converted mPyFile arrives as its own compiled type, never as an mPyFile.
    for _ntype in (MPyFile.NODE_NAME,) + compiled_texture_types():
        try:
            cb_id = om.MDGMessage.addNodeAddedCallback(_on_added, _ntype)
            CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback,
                                      OWNER_API2)
        except Exception as exc:
            sys.stderr.write(
                "[mPyFile] node-added lifecycle hook failed for %s: %s\n"
                % (_ntype, exc)
            )

    # addNodeAddedCallback can race a file load and miss nodes; the kAfterOpen
    # sweep is the idempotent backstop (mirrors auto_dirty / attr-refresh).
    def _on_after_open(_client):
        _sweep_existing()

    try:
        cb_id = om.MSceneMessage.addCallback(
            om.MSceneMessage.kAfterOpen, _on_after_open
        )
        CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, OWNER_API2)
    except Exception:
        pass
