"""Post-port VP2 shading-node override injection for compiled mPyFile textures.

WHY: a compiled mPyFile renders correctly in software / Arnold / the Hypershade
swatch (all CPU-evaluate ``outColor`` through the DG ``compute()``), but Viewport
2.0 shows a single FLAT colour -- OGS can only display a custom 2D texture through
a registered ``MHWRender::MPxShadingNodeOverride``, and codegen emits none. This
module splices that override into the finalized single-node ``.cpp`` AFTER the
porter (a deterministic text transform -- the AI body is reused untouched, so no
re-port), mirroring the GUI-confirmed prototype in
``tests/data/scanline_defs.py`` but generalized to ANY mPyFile:

  * The override reuses Maya's built-in ``mayaFileTexture`` fragment (no custom
    GPU shader) and, in ``updateShader``, bakes the WHOLE pixel buffer for the
    current inputs and uploads it as the fragment's 2D texture.
  * The bake calls a shared ``nd_texel(...)`` extracted from the ported
    ``compute()`` PORT region, so VP2 pixels are the SAME per-texel math as
    compute -- VP2 == software == Arnold by construction (no hand-copied look
    that can drift, cf. the fixture prototype whose hardcoded bake diverged from
    the real intensity+sRGB scanline compute).

The transform is a no-op (returns the text unchanged) for a ``.cpp`` it does not
recognize (no PORT region), so it is safe to run over every node in a bundle.
"""

from __future__ import annotations

import re
import textwrap
from typing import List, Optional


# ---- Parsing the deterministic codegen output ------------------------------
_CLASS_RE = re.compile(r"\nclass (\w+) : public MPx\w+ \{")
_REGISTER_RE = re.compile(r'registerNode\(\s*"(\w+)"')
_PORT_BEGIN = "// ===== BEGIN PORTED COMPUTE ====="
_PORT_END = "// ===== END PORTED COMPUTE ====="

# A compute the transpiler lowered DETERMINISTICALLY has no PORT region at all --
# emit_compute writes this banner and wraps the body in spec_model.lowered_guard
# instead. Gating only on the PORT markers silently turned this whole module OFF
# for every texture node the transpiler learned to lower (the mPyFile group, once
# texture read/sample became blessed kernels): no override, and VP2 falls back to
# a flat colour. Recognize BOTH shapes.
_LOWERED_BEGIN = "// --- deterministic numpy->C++ lowered compute (no port) ---"
_LOWERED_END = "// --- finalize ---"

# One compute input declaration, e.g.
#   const int in_aBands = data.inputValue(aBands).asInt();
#   const double in_aFrame = data.inputValue(aFrame).asTime().value();
#   const float2& in_aUvCoord = data.inputValue(aUvCoord).asFloat2();
_INPUT_DECL_RE = re.compile(
    r"^\s*const\s+(?P<type>[\w:]+(?:\s*&)?)\s+(?P<var>in_\w+)\s*=\s*"
    r"data\.inputValue\((?P<attr>\w+)\)\.(?P<read>[\w().]+);\s*$",
    re.M)

# One ARRAY (multi) compute input. Codegen does NOT declare these with a one-line
# inputValue(); it fills a std::vector from an MArrayDataHandle:
#     std::vector<MString> in_aLayers;
#     {
#         MArrayDataHandle _arr = data.inputArrayValue(aLayers);
#         ...
#             if (_li >= in_aLayers.size()) in_aLayers.resize(_li + 1, MString());
#             in_aLayers[_li] = eh.asString();
# so _INPUT_DECL_RE never saw them and nd_texel dropped every array input off its
# signature -- the extracted body then referenced an undeclared identifier.
_MULTI_DECL_RE = re.compile(
    r"^[ \t]*std::vector<(?P<elem>[\w:]+)>\s+(?P<var>in_a\w+);\s*\n"
    r"[ \t]*\{\s*\n"
    r"[ \t]*MArrayDataHandle\s+\w+\s*=\s*data\.inputArrayValue\((?P<attr>a\w+)\);"
    r".*?(?P=var)\.resize\([^,]+,\s*(?P<fill>[^)]*(?:\(\))?)\);"
    r".*?(?P=var)\[\w+\]\s*=\s*\w+\.(?P<read>as\w+)\(\);",
    re.M | re.S)

# attr member -> plug name from initialize(): aBands = nAttr.create("bands", ...
_CREATE_RE = re.compile(
    r"(?P<attr>a\w+)\s*=\s*\w+\.create(?:Color)?\(\s*\"(?P<plug>\w+)\"")

# Maya's float2/float3/double3/... are ARRAY typedefs, and every place this module
# touches an input has to treat one differently from a scalar: passing it by value
# decays to a pointer (so the body's `const float3&` will not bind), `= T()` is not
# valid initialization for an array, MPlug has no asFloat3(), and `(double)` on one
# is not a conversion. type -> (element ctype, count, MPlug child read).
_ARRAY_TYPES = {
    "float2": ("float", 2, "asFloat"), "float3": ("float", 3, "asFloat"),
    "double2": ("double", 2, "asDouble"), "double3": ("double", 3, "asDouble"),
    "double4": ("double", 4, "asDouble"),
    "short2": ("short", 2, "asShort"), "short3": ("short", 3, "asShort"),
    "int2": ("int", 2, "asInt"), "int3": ("int", 3, "asInt"),
}


class _Input:
    __slots__ = ("type", "var", "attr", "read", "plug", "multi", "elem", "fill")

    def __init__(self, type_, var, attr, read, plug, multi=False, elem="",
                 fill=""):
        self.type = type_.replace(" ", "")   # 'float2&'
        self.var = var                       # 'in_aBands'
        self.attr = attr                     # 'aBands'
        self.read = read                     # 'asInt()' / 'asTime().value()'
        self.plug = plug                     # 'bands'
        self.multi = multi                   # array (multi) input
        self.elem = elem                     # multi element ctype ('MString')
        self.fill = fill                     # multi sparse-gap default

    @property
    def is_uv(self):
        if self.multi:
            return False
        return self.read.startswith("asFloat2") or self.type == "float2&"

    @property
    def is_time(self):
        return "asTime" in self.read

    @property
    def bare_type(self):
        return self.type.rstrip("&")

    @property
    def plug_read(self):
        """How to read this input off an MPlug in updateDG (mirrors compute's
        value semantics)."""
        if self.is_time:
            return "asMTime().value()"
        return self.read  # asString()/asInt()/asFloat()/asDouble()/asBool()

    @property
    def member_type(self):
        """C++ type for the override's cached member (time -> double)."""
        return "double" if self.is_time else self.bare_type

    @property
    def array_info(self):
        return None if self.multi else _ARRAY_TYPES.get(self.bare_type)

    @property
    def param_type(self):
        """nd_texel parameter type. An array typedef or a vector must stay a
        REFERENCE: passed by value the array decays to a pointer, which the
        body's `const float3&` cannot bind to, and copying a vector per texel is
        pure waste."""
        if self.multi or self.array_info:
            return "const %s&" % self.bare_type
        return self.bare_type


def _parse_inputs(cpp: str) -> List[_Input]:
    """All compute() input declarations, with plug names resolved from
    initialize()'s create() calls. Returned in SOURCE order, so nd_texel's
    signature reads like the compute it was cut out of."""
    attr_to_plug = {m.group("attr"): m.group("plug")
                    for m in _CREATE_RE.finditer(cpp)}
    found = []
    # Only scan the inputs block of compute() (between '--- inputs ---' and the
    # next section) so we don't pick up stray matches elsewhere.
    m = re.search(r"//\s*---\s*inputs\s*---(.*?)\n\n", cpp, re.S)
    scope = m.group(1) if m else cpp
    for d in _INPUT_DECL_RE.finditer(scope):
        attr = d.group("attr")
        found.append((d.start(),
                      _Input(d.group("type"), d.group("var"), attr,
                             d.group("read"), attr_to_plug.get(attr, ""))))
    for d in _MULTI_DECL_RE.finditer(scope):
        attr = d.group("attr")
        found.append((d.start(),
                      _Input("std::vector<%s>" % d.group("elem"), d.group("var"),
                             attr, d.group("read") + "()",
                             attr_to_plug.get(attr, ""), multi=True,
                             elem=d.group("elem"), fill=d.group("fill").strip())))
    return [i for _, i in sorted(found, key=lambda t: t[0])]


# One output-handle declaration + its default seed setter, e.g.
#   MDataHandle h_aMaxWidth = data.outputValue(aMaxWidth);
#   h_aMaxWidth.setInt(0);
_OUTPUT_DECL_RE = re.compile(
    r"MDataHandle\s+h_(?P<var>a\w+)\s*=\s*data\.outputValue\((?P<attr>a\w+)\);\s*\n"
    r"\s*h_(?P=var)\.(?P<setter>set\w+)\(", re.M)

# Scalar output setter -> C++ value type (for the nd_texel shim + write-back).
_SETTER_CTYPE = {
    "setInt": "int", "setFloat": "float", "setDouble": "double",
    "setBool": "bool", "setShort": "short",
}
_CTYPE_DEFAULT = {"int": "0", "short": "0", "float": "0.0f", "double": "0.0",
                  "bool": "false"}


class _Output:
    __slots__ = ("var", "attr", "plug", "setter", "ctype")

    def __init__(self, var, attr, plug, setter):
        self.var = var                    # 'aMaxWidth'
        self.attr = attr                  # 'aMaxWidth'
        self.plug = plug                  # 'maxWidth'
        self.setter = setter              # 'setInt'
        self.ctype = _SETTER_CTYPE.get(setter, "")


def _parse_outputs(cpp: str) -> List[_Output]:
    attr_to_plug = {m.group("attr"): m.group("plug")
                    for m in _CREATE_RE.finditer(cpp)}
    outs = []
    for m in _OUTPUT_DECL_RE.finditer(cpp):
        attr = m.group("attr")
        outs.append(_Output(m.group("var"), attr, attr_to_plug.get(attr, ""),
                            m.group("setter")))
    return outs


def _extra_outputs(cpp: str) -> List[_Output]:
    """Outputs BEYOND the standard texture pair (outColor/outAlpha) -- e.g. the
    int maxWidth/maxHeight of the composite node. Each is a NODE-scalar the ported
    body writes inside the (now nd_texel) region, so nd_texel gets a shim + an
    out-ref param, compute writes the real handle back, and the VP2 bake passes a
    throwaway. Only scalar setters are handled (a non-scalar extra -> skipped, so
    injection stays a no-op rather than emitting broken C++)."""
    return [o for o in _parse_outputs(cpp)
            if o.plug not in ("outColor", "outAlpha") and o.ctype]


def _parse_composite_path(cpp: str):
    """The string-array path member feeding nd_img_composite (multi-file node), or
    None. Returns {'var','attr','plug'} for the VP2 bake to re-load the composite."""
    m = re.search(r"nd_img_composite\(\s*\w+\s*,\s*\w+\s*,\s*(in_a\w+)\s*,", cpp)
    if not m:
        return None
    var = m.group(1)                       # 'in_aFilePaths'
    attr = var[len("in_"):]                # 'aFilePaths'
    attr_to_plug = {mm.group("attr"): mm.group("plug")
                    for mm in _CREATE_RE.finditer(cpp)}
    return {"var": var, "attr": attr, "plug": attr_to_plug.get(attr, "")}


def _call_args(body: str, start: int) -> Optional[List[str]]:
    """The comma-split argument list of the call whose ``(`` follows *start*, or
    ``None`` when the parens never close. Depth counts ``()``, ``[]`` AND ``{}``:
    a lowered argument is routinely ``nd::from_data<double>({a, b}, {2})`` or
    ``MString((nd::strv_at(v, i)).c_str())``, and splitting those on a bare comma
    tears the call apart."""
    i = body.index("(", start)
    depth, close = 0, -1
    for j in range(i, len(body)):
        if body[j] == "(":
            depth += 1
        elif body[j] == ")":
            depth -= 1
            if depth == 0:
                close = j
                break
    if close < 0:
        return None
    args, depth, cur = [], 0, ""
    for ch in body[i + 1:close]:
        if ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        cur += ch
    args.append(cur.strip())
    return args


# The local name a lowered body gives an ARRAY (multi) input, and the input it
# came from. Two shapes reach here: deterministic codegen COPIES the vector into
# the transpiler's own element type, while an optimizer rewrite aliases it by
# reference. Either way the local has to resolve back to the cached member so a
# looped multi-layer read can be probed for its resolution.
_LIFT_COPY_RE = re.compile(r"^[ \t]*(\w+)\.reserve\((in_a\w+)\.size\(\)\);", re.M)
_LIFT_ALIAS_RE = re.compile(
    r"^[ \t]*const\s+std::vector<[\w:]+>\s*&\s*(\w+)\s*=\s*(in_a\w+)\s*;", re.M)


def _parse_texload(body: str, inputs=()) -> Optional[dict]:
    """The one blessed ``nd_tex_load_linear(...)`` call in *body*, re-pointed at
    the override's cached members -- or ``None``.

    Lets the VP2 bake run at the image's OWN resolution, which is what the
    ``nd_img_load_raw`` path already did before texture reads became a blessed
    kernel; without it a lowered texture bakes onto a synthetic 256x256 grid and
    the viewport is visibly softer than the swatch.

    Two shapes, both keyed off the ONE call's path argument:

      * ``{"kind": "one"}``  -- the path is a plain input variable (File Simple,
        File Scanline). Probe that one image.
      * ``{"kind": "many"}`` -- the path indexes an ARRAY (multi) input lifted
        into a local (the multi-layer composite's ``for`` over ``layers``). This
        used to be rejected, which is exactly why compositeTexture baked 256x256
        while its interpreted twin uploaded 1024x1024. Probe EVERY element and
        keep the max, because ``_composite_layers`` sizes its canvas with
        ``max_h = max(s[0] for s in sizes)`` over the layers it can load.
    """
    # A composite lowers to ONE nd_tex_composite_layers call and does its loading
    # inside the kernel, so there is no nd_tex_load_linear in the body to key
    # off. Handle it first: the layer vector is arg 0 and the four load presets
    # sit at 5..8, which is everything the size probe needs.
    comp = [m.start() for m in re.finditer(r"\bnd_tex_composite_layers\s*\(", body)]
    if comp:
        if len(comp) != 1:
            return None
        args = _call_args(body, comp[0])
        # (paths, ops, nOps, u, v, cs, pf, kernel, radius, wU, wV, bd, ms,
        #  cache, mutex, out)
        if not args or len(args) != 16:
            return None
        mid = ", ".join(re.sub(r"\bin_a", "_m_in_a", a) for a in args[5:9])
        lifted = dict(_LIFT_COPY_RE.findall(body))
        lifted.update(dict(_LIFT_ALIAS_RE.findall(body)))
        multi = {i.var for i in inputs if i.multi}
        srcs = sorted({lifted.get(t, t) for t in re.findall(r"\b\w+\b", args[0])}
                      & multi)
        if len(srcs) != 1:
            return None
        vec = "_m_" + srcs[0]
        return {"kind": "many", "vec": vec,
                "call": "nd_tex_load_linear(_texCache, _texMutex, "
                        "%s[_li], %s, _lw, _lh)" % (vec, mid)}

    hits = [m.start() for m in re.finditer(r"\bnd_tex_load_linear\s*\(", body)]
    if len(hits) != 1:
        return None
    args = _call_args(body, hits[0])
    # (cache, mutex, path, colorSpace, prefilter, kernel, radius, &w, &h)
    if not args or len(args) != 9:
        return None
    mid = ", ".join(re.sub(r"\bin_a", "_m_in_a", a) for a in args[3:7])
    path = args[2]
    if re.fullmatch(r"in_a\w+", path):
        return {"kind": "one",
                "call": "nd_tex_load_linear(_texCache, _texMutex, "
                        "%s, %s, _w, _h)" % ("_m_" + path, mid)}
    lifted = dict(_LIFT_COPY_RE.findall(body))
    lifted.update(dict(_LIFT_ALIAS_RE.findall(body)))
    multi = {i.var for i in inputs if i.multi}
    srcs = sorted({lifted.get(t, t) for t in re.findall(r"\b\w+\b", path)}
                  & multi)
    if len(srcs) != 1:
        return None
    vec = "_m_" + srcs[0]
    return {"kind": "many", "vec": vec,
            "call": "nd_tex_load_linear(_texCache, _texMutex, "
                    "%s[_li], %s, _lw, _lh)" % (vec, mid)}


def _parse_wrap_override(body: str, inputs) -> Optional[List["_Input"]]:
    """The two wrap-mode INPUTS *body* hands to ``nd_tex_sample``, or ``None``.

    The bake needs these so it can force CLAMP addressing for its OWN nd_texel
    call. A bake grid that puts a texel on the CORNERS (``u = x/(W-1)``, which is
    what makes the baked texel an exact source texel under nd_tex_sample's
    ``fx = uu*(W-1)`` convention) hits ``u == 1.0`` on the last column, and the
    default wrap mode is ``fmodf(coord, 1.0f)`` -- so 1.0 folds to 0.0 and the
    last column samples column 0 (likewise the top row). On the closed interval
    [0,1] clamp and wrap agree EVERYWHERE except at exactly 1.0, so clamping the
    bake changes nothing but that endpoint, and it matches the interpreted
    viewport tier, which uploads the source buffer with no wrap applied at all.

    Deliberately derived from the CALL rather than from a plug name: a body that
    bakes its own wrap into the expression (Game Of Life's ``u - floor(u)``)
    has nothing to override, and returning None there keeps it on the texel-
    CENTRE grid instead of silently corrupting its edges. Refuses unless every
    nd_tex_sample passes the same two bare input variables and those variables
    appear NOWHERE else in the body -- otherwise forcing them would change
    something besides the addressing.
    """
    # Every kernel that takes the wrap pair, and where it sits in its argument
    # list: (argc, index of wrapU). A table rather than one hardcoded call, so a
    # body that composites through nd_tex_composite_layers -- which samples
    # INSIDE the kernel and so has no nd_tex_sample of its own -- is still
    # recognised. Missing it silently drops the bake back to the texel-CENTRE
    # grid, which is the defect this whole path exists to prevent.
    _WRAP_AT = {
        "nd_tex_sample": (10, 5),            # (lin,W,H,u,v,wU,wV,border,miss,out)
        "nd_tex_composite_layers": (16, 9),  # (...,wU,wV,border,miss,cache,mtx,out)
    }
    hits = []
    for name, (argc, at) in _WRAP_AT.items():
        for m in re.finditer(r"\b%s\s*\(" % name, body):
            hits.append((m.start(), argc, at))
    if not hits:
        return None
    by_var = {i.var: i for i in inputs if not i.multi}
    pair = None
    for h, argc, at in hits:
        args = _call_args(body, h)
        if not args or len(args) != argc:
            return None
        got = tuple(re.sub(r"^\(\s*(?:int|short|unsigned)\s*\)\s*", "", a).strip()
                    for a in args[at:at + 2])
        if pair is None:
            pair = got
        elif pair != got:
            return None
    for v in set(pair):
        if v not in by_var:
            return None
        if len(re.findall(r"\b%s\b" % re.escape(v), body)) != len(hits) * pair.count(v):
            return None
    return [by_var[pair[0]], by_var[pair[1]]]


# The persistent per-instance state spec_model emits INSIDE the node class, e.g.
#     struct _NdState {
#         bool board_isset = false;
#         nd::Array<bool> board {};
#     };
# Nested, so a free nd_texel emitted above the class cannot name the type. It is
# hoisted to file scope (still inside the per-node namespace the bundler wraps)
# and threaded into nd_texel by reference -- see _parse_state.
_STATE_STRUCT_RE = re.compile(
    r"^[ \t]*struct _NdState \{.*?^[ \t]*\};[ \t]*\n", re.M | re.S)
_STATE_ARRAY_RE = re.compile(r"^[ \t]*nd::Array<\w+>\s+(\w+)\s*\{\}\s*;", re.M)


def _parse_state(cpp: str):
    """``{'struct', 'array'}`` for a stateful node, else ``None``.

    ``struct`` is the verbatim nested ``_NdState`` definition (to hoist);
    ``array`` is the name of its first ``nd::Array`` member, or "".

    That array is the node's simulation grid, and its shape is the resolution
    the VP2 bake should run at -- the interpreted Viewport tier uploads at
    ``board.shape`` for exactly this reason, so a 20x20 Game of Life board
    stays 20x20 instead of being resampled onto the synthetic 256x256 grid.
    """
    m = _STATE_STRUCT_RE.search(cpp)
    if not m:
        return None
    struct = m.group(0)
    am = _STATE_ARRAY_RE.search(struct)
    return {"struct": struct, "array": am.group(1) if am else ""}


def _default_literal(inp: _Input) -> str:
    ai = inp.array_info
    if ai:
        # An array typedef is aggregate-initialized; `= float3()` does not compile.
        return "{%s}" % ", ".join([_CTYPE_DEFAULT[ai[0]]] * ai[1])
    if inp.member_type == "double":
        return "0.0"
    if inp.member_type == "float":
        return "0.0f"
    if inp.member_type in ("int", "short"):
        return "0"
    if inp.member_type == "bool":
        return "false"
    return ""  # MString etc. default-construct


# ---- Emission --------------------------------------------------------------
_OVERRIDE_INCLUDES = (
    "// --- VP2 interactive-viewport shading override (codegen) ---\n"
    # The bake is row-parallel; see the worker block in updateShader.
    "#include <thread>\n"
    "#include <atomic>\n"
    "#include <mutex>\n"
    "#include <algorithm>\n"
    "#include <maya/MViewport2Renderer.h>\n"
    "#include <maya/MPxShadingNodeOverride.h>\n"
    "#include <maya/MShaderManager.h>\n"
    "#include <maya/MTextureManager.h>\n"
    "#include <maya/MStateManager.h>\n"
    "#include <maya/MDrawRegistry.h>\n"
    "#include <maya/MFnDependencyNode.h>\n"
    "#include <maya/MItDependencyNodes.h>\n"
    "#include <maya/MEventMessage.h>\n"
    "#include <maya/MMessage.h>\n"
    "#include <maya/MGlobal.h>\n"
    "#include <maya/MStringArray.h>\n"
    "#include <maya/MPlug.h>\n"
    "#include <maya/MFn.h>\n"
    "#include <string>\n")


def _texel_signature(inputs, has_raw, extras=(), has_texcache=False,
                     has_state=False):
    """Return the nd_texel parameter list.

    Params: uv (double _u,_v) + every NON-uv input (verbatim type/name so the
    ported body compiles unchanged) + image context (only when the node reads an
    image) + the blessed texture cache (lowered bodies only, again under the
    body's own names) + the persistent state pair (stateful nodes, likewise
    under the body's own names) + the outColor/outAlpha references + one out-ref
    per EXTRA node-scalar output the ported body writes (e.g. maxWidth/Height).
    """
    params = ["double _u", "double _v"]
    for i in inputs:
        if i.is_uv:
            continue
        params.append("%s %s" % (i.param_type, i.var))
    if has_raw:
        params += ["unsigned int _imgW", "unsigned int _imgH",
                   "const unsigned char* _imgPixels", "bool _imgOK"]
    if has_texcache:
        params += ["NdTexCache& _texCache", "std::mutex& _texMutex"]
    if has_state:
        # Named exactly as the node members the body already references, so its
        # "std::lock_guard<std::mutex> _ndStateLock(_ndStateMutex);" and
        # "_NdState& st = _ndState;" preamble compiles here UNCHANGED. compute()
        # passes its own members; the override passes the SAME node's, so the
        # viewport and the DG share one simulation rather than forking it.
        params += ["_NdState& _ndState", "std::mutex& _ndStateMutex"]
    params += ["float& _oR", "float& _oG", "float& _oB", "float& _oA"]
    for o in extras:
        params.append("%s& _o_%s" % (o.ctype, o.var))
    return params


def _make_texel_fn(port_body, inputs, has_raw, extras=(), has_texcache=False,
                   has_state=False):
    uv = next((i for i in inputs if i.is_uv), None)
    uv_name = uv.var if uv else "in_aUvCoord"
    params = _texel_signature(inputs, has_raw, extras, has_texcache, has_state)
    lines = [
        "// ===========================================================================",
        "// nd_texel -- one pixel of the mPyFile buffer. SHARED by compute() (one",
        "// sample at the surface uv) and the VP2 override bake (the whole grid), so",
        "// the viewport pixels are the SAME per-texel math as software/Arnold.",
        "// (Body is the ported compute region, reused verbatim via handle shims.)",
        "// ===========================================================================",
        "static void nd_texel(",
        "        " + ",\n        ".join(params) + ") {",
        "    const float _nd_uv[2] = { (float)_u, (float)_v };",
        "    const float2& %s = _nd_uv;" % uv_name,
        "    struct _NdColSh { float &r, &g, &b;",
        "        void set3Float(float R, float G, float B) { r=R; g=G; b=B; } }",
        "        h_aOutColor{_oR, _oG, _oB};",
        "    struct _NdAlpSh { float &a;",
        "        void setFloat(float A) { a=A; } } h_aOutAlpha{_oA};",
    ]
    # Shims for EXTRA node-scalar outputs (e.g. maxWidth/maxHeight): the ported
    # body calls h_<var>.<setter>(...), so bind that name to the out-ref and the
    # body drops in unchanged (the VP2 bake passes a throwaway).
    for o in extras:
        lines.append(
            "    struct _NdSh_%s { %s &v; void %s(%s V){v=V;} } h_%s{_o_%s};"
            % (o.var, o.ctype, o.setter, o.ctype, o.var, o.var))
    # Silence unused-parameter warnings for inputs the body may not reference
    # (e.g. fileName on an image node -- the image arrives via the ctx params).
    for i in inputs:
        if i.is_uv:
            continue
        lines.append("    (void)%s;" % i.var)
    # Rename the ported body's output-handle writes to hit the shims. The body
    # already calls h_aOutColor.set3Float / h_aOutAlpha.setFloat -- those names
    # are the shims here, so the body drops in UNCHANGED.
    lines.append(port_body.rstrip("\n"))
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _compute_call(inputs, has_raw, extras=(), has_texcache=False,
                  guard_type=None, has_state=False):
    """The replacement compute() body: call nd_texel at the surface uv, write the
    real MDataHandles (outColor/outAlpha + any extra node-scalar outputs).

    ``guard_type`` (the node type name) re-emits spec_model.lowered_guard's
    try/catch around the call. It is set only when the region replaced WAS a
    lowered guard, so a transpiled body that throws still reports through
    MGlobal::displayError and abandons the evaluation exactly as before.
    """
    uv = next((i for i in inputs if i.is_uv), None)
    uv_name = uv.var if uv else "in_aUvCoord"
    args = ["(double)%s[0]" % uv_name, "(double)%s[1]" % uv_name]
    for i in inputs:
        if i.is_uv:
            continue
        args.append(i.var)
    if has_raw:
        args += ["_imgW", "_imgH", "_imgPixels", "_imgOK"]
    if has_texcache:
        args += ["_texCache", "_texMutex"]
    if has_state:
        args += ["_ndState", "_ndStateMutex"]
    args += ["_oR", "_oG", "_oB", "_oA"]
    for o in extras:
        args.append("_o_%s" % o.var)
    body = []
    for o in extras:
        body.append("%s _o_%s = %s;"
                    % (o.ctype, o.var, _CTYPE_DEFAULT.get(o.ctype, "0")))
    body += [
        "float _oR = 0.0f, _oG = 0.0f, _oB = 0.0f, _oA = 0.0f;",
        "nd_texel(" + ", ".join(args) + ");",
        "h_aOutColor.set3Float(_oR, _oG, _oB);",
        "h_aOutAlpha.setFloat(_oA);",
    ]
    for o in extras:
        body.append("h_%s.%s(_o_%s);" % (o.var, o.setter, o.var))

    lines = ["    // ===== texel (shared with the VP2 override bake) ====="]
    if guard_type:
        lines.append("    try {")
        lines += ["    " + s for s in body]
        lines.append("    } catch (const std::exception& _ndErr) {")
        lines.append('        MGlobal::displayError(MString("%s: ") + '
                     "_ndErr.what());" % guard_type)
        lines.append("        return MS::kFailure;")
        lines.append("    }")
    else:
        lines += ["    " + s for s in body]
    return "\n".join(lines)


def _make_override_block(cls, type_name, inputs, has_raw, extras=(), comp=None,
                         has_texcache=False, texload=None, state=None,
                         wrap_clamp=None):
    """The MPxShadingNodeOverride subclass + timeChanged callback, in an
    anonymous namespace, that bakes via nd_texel and uploads per frame.

    ``comp`` (from _parse_composite_path) drives the multi-file variant: the
    override caches the string-array path plug and rebuilds the composite via
    nd_img_composite for the bake. ``extras`` are node-scalar outputs nd_texel
    also writes (maxWidth/maxHeight) -- the bake passes throwaways for them."""
    over = cls + "Override"
    scalars = [i for i in inputs if not i.is_uv]
    fn_inp = next((i for i in inputs if i.plug == "fileName"), None)

    # cached members
    members = []
    for i in scalars:
        members.append("    %s _m_%s = %s;"
                       % (i.member_type, i.var, _default_literal(i) or "%s()" % i.member_type))
    if comp:
        members += ["    std::vector<MString> _m_paths;",
                    "    NdImgCompositeCache _cache;", "    std::mutex _mtx;"]
    elif has_raw:
        members += ["    NdImgRawCache _cache;", "    std::mutex _mtx;"]
    if has_texcache:
        # The override's OWN pair, mirroring the NdImgRawCache members above: the
        # node's are instance members of a class this block cannot reach. Both
        # sides key the same blessed loader on the same inputs, so the pixels are
        # identical -- only the cache storage is duplicated.
        members += ["    NdTexCache _texCache;", "    std::mutex _texMutex;"]
    if state:
        # NOT a private copy: persistent state must be SHARED with compute(), or
        # the viewport would run a second, independently-advancing simulation.
        # Resolved in updateDG (main thread) because MFnDependencyNode +
        # userNode() from the VP2 render thread can crash Maya -- the same reason
        # the interpreted MPyFileOverride caches its _mpx_node there.
        members += ["    %s* _nodePtr = nullptr;" % cls]

    # updateDG: cache each scalar plug value (+ the path array) on the main thread.
    dg = ["    void updateDG() override {",
          "        MStatus st; MFnDependencyNode fn(_node, &st); if (!st) return;",
          "        MPlug p;"]
    if state:
        dg.append("        _nodePtr = dynamic_cast<%s*>(fn.userNode());" % cls)
    for i in scalars:
        ai = i.array_info
        if i.multi:
            # Same sparse-array walk compute() does off the MArrayDataHandle,
            # including its gap fill, so a hole reads the same value both sides.
            dg += [
                '        p = fn.findPlug("%s", false, &st);' % i.plug,
                "        if (st) {",
                "            _m_%s.clear();" % i.var,
                "            unsigned int _ne = p.numElements(), _n = 0;",
                "            for (unsigned int _i = 0; _i < _ne; ++_i) {",
                "                unsigned int _li = p.elementByPhysicalIndex(_i).logicalIndex();",
                "                if (_li + 1 > _n) _n = _li + 1;",
                "            }",
                "            _m_%s.resize(_n%s);"
                % (i.var, (", " + i.fill) if i.fill else ""),
                "            for (unsigned int _i = 0; _i < _ne; ++_i) {",
                "                MPlug _e = p.elementByPhysicalIndex(_i);",
                "                _m_%s[_e.logicalIndex()] = _e.%s;" % (i.var, i.read),
                "            }",
                "        }",
            ]
        elif ai:
            # MPlug has no asFloat3(); a compound reads through its CHILDREN.
            dg += ['        p = fn.findPlug("%s", false, &st);' % i.plug,
                   "        if (st && p.numChildren() >= %d) {" % ai[1]]
            dg += ["            _m_%s[%d] = p.child(%d).%s();"
                   % (i.var, k, k, ai[2]) for k in range(ai[1])]
            dg.append("        }")
        else:
            dg.append('        p = fn.findPlug("%s", false, &st); if (st) _m_%s = p.%s;'
                      % (i.plug, i.var, i.plug_read))
    if comp:
        dg += [
            '        p = fn.findPlug("%s", false, &st);' % comp["plug"],
            "        if (st) {",
            "            _m_paths.clear();",
            "            unsigned int _ne = p.numElements(), _n = 0;",
            "            for (unsigned int _i = 0; _i < _ne; ++_i) {",
            "                unsigned int _li = p.elementByPhysicalIndex(_i).logicalIndex();",
            "                if (_li + 1 > _n) _n = _li + 1;",
            "            }",
            "            _m_paths.resize(_n);",
            "            for (unsigned int _i = 0; _i < _ne; ++_i) {",
            "                MPlug _e = p.elementByPhysicalIndex(_i);",
            "                _m_paths[_e.logicalIndex()] = _e.asString();",
            "            }",
            "        }",
        ]
    dg.append("    }")

    # texel call args from cached members (+ throwaways for extra outputs).
    texel_args = ["u", "v"]
    for i in scalars:
        texel_args.append("_m_%s" % i.var)
    if has_raw:
        texel_args += ["_w", "_h", "pix", "true"]
    if has_texcache:
        texel_args += ["_texCache", "_texMutex"]
    if state:
        texel_args += ["_nodePtr->_ndState", "_nodePtr->_ndStateMutex"]
    texel_args += ["r", "g", "b", "a"]
    for o in extras:
        texel_args.append("_dump_%s" % o.var)

    # texture cache key: fold every varying scalar (or the path list) in so any
    # edit re-uploads.
    key_parts = ['MString texName("%sVP2::");' % type_name]
    if comp:
        key_parts.append("for (size_t _i = 0; _i < _m_paths.size(); ++_i) "
                         '{ texName += _m_paths[_i]; texName += MString("|"); }')
    if fn_inp:
        key_parts.append("texName += _m_%s;" % fn_inp.var)
    for i in scalars:
        if i is fn_inp:
            continue
        key_parts.append('texName += MString("|");')
        # (double) is a conversion for a scalar ONLY. An MString appends directly,
        # an array typedef and a vector fold component by component -- otherwise a
        # node whose only varying input is one of those keys every edit to the SAME
        # texture name and the viewport never refreshes.
        if i.multi:
            key_parts.append(
                "for (size_t _i = 0; _i < _m_%s.size(); ++_i) { texName += %s; "
                'texName += MString(","); }'
                % (i.var, ("_m_%s[_i]" % i.var) if i.elem == "MString"
                   else "(double)_m_%s[_i]" % i.var))
        elif i.array_info:
            for k in range(i.array_info[1]):
                key_parts.append('texName += MString(",");' if k else "")
                key_parts.append("texName += (double)_m_%s[%d];" % (i.var, k))
            key_parts = [s for s in key_parts if s]
        elif i.member_type == "MString":
            key_parts.append("texName += _m_%s;" % i.var)
        else:
            key_parts.append("texName += (double)_m_%s;" % i.var)

    # The image source for the bake grid: composite (multi-file), else raw cache
    # (single file), else a synthetic default resolution.
    #
    # `corner` selects the texel-CORNER bake grid, and ONLY the blessed-texload
    # branches set it. Those go through nd_tex_sample, whose bilinear lookup is
    # `fx = uu * (W - 1)`; on a corner grid that is exactly `x`, so every baked
    # texel IS a source texel -- which is what the interpreted tier uploads. The
    # other branches index NEAREST (`int(uu*w)`), where the texel-CENTRE grid is
    # already exact, so switching them to corners would REGRESS them.
    corner = False
    if comp:
        load = [
            "        unsigned int _w = 0, _h = 0;",
            "        const unsigned char* pix = nullptr;",
            "        bool ok = nd_img_composite(_cache, _mtx, _m_paths, _w, _h, pix);",
            "        if (!ok || _w == 0 || _h == 0 || !pix) return;",
        ]
    elif has_raw and fn_inp:
        load = [
            "        unsigned int _w = 0, _h = 0;",
            "        const unsigned char* pix = nullptr;",
            "        bool ok = nd_img_load_raw(_cache, _mtx, _m_%s, _w, _h, pix);"
            % fn_inp.var,
            "        if (!ok || _w == 0 || _h == 0 || !pix) return;",
        ]
    elif texload:
        # Blessed texture-cache reader: probe the SAME loader the body uses just
        # to learn the image size, then bake at that resolution.
        #
        # There is deliberately NO size cap. A cap looks like cheap insurance,
        # but the interpreted tier uploads at the source's FULL resolution, so
        # any cap is a resolution mismatch -- the two tiers then hand VP2
        # differently-sized textures and its filtering makes them disagree
        # everywhere, not just on the pixels that were dropped. A 1024 cap put
        # 26% of a 2048 source's texels wrong, which is worse than the defect
        # it was insuring against. The heavy-file cost is real, but it is the
        # cost the reference tier already pays, and matching it is the point.
        corner = wrap_clamp is not None
        load = ["        unsigned int _w = 0, _h = 0;"]
        if texload["kind"] == "many":
            # Looped multi-layer read: the canvas is the MAX over the layers that
            # load, mirroring _composite_layers' max_h/max_w. Probing only the
            # first layer (or not probing at all) is what left compositeTexture
            # baking 256x256 against a 1024x1024 interpreted upload.
            load += [
                "        for (size_t _li = 0; _li < %s.size(); ++_li) {"
                % texload["vec"],
                "            unsigned int _lw = 0, _lh = 0;",
                "            if (%s) {" % texload["call"],
                "                if (_lw > _w) _w = _lw;",
                "                if (_lh > _h) _h = _lh;",
                "            }",
                "        }",
            ]
        else:
            load.append("        if (!%s) { _w = 0; _h = 0; }" % texload["call"])
        load += [
            "        if (_w == 0 || _h == 0) { _w = 256; _h = 256; }",
        ]
    elif state:
        # A stateful generator has no image to size the grid from, but it DOES
        # have its simulation array -- bake at that, like the interpreted tier
        # uploading at board.shape. Resampling a 20x20 Game of Life board onto
        # the synthetic 256x256 grid is 164x the texels for a blurrier result.
        load = ["        if (!_nodePtr) return;",
                "        unsigned int _w = 256, _h = 256;",
                "        {",
                "            // Prime: one texel advances/reseeds the simulation",
                "            // for this frame, exactly as the Viewport tier calls",
                "            // _gol_advance(self) before reading board.shape.",
                "            // Without it the grid below is the PREVIOUS frame's",
                "            // size whenever a resolution input just changed.",
                "            double u = 0.0, v = 0.0;",
                "            float r = 0.0f, g = 0.0f, b = 0.0f, a = 0.0f;"]
        for o in extras:
            load.append("            %s _dump_%s = %s;"
                        % (o.ctype, o.var, _CTYPE_DEFAULT.get(o.ctype, "0")))
        load += ["            nd_texel(%s);" % ", ".join(texel_args),
                 "        }"]
        if state["array"]:
            load += [
                "        {",
                # NOT capped. The interpreted tier uploads the state array at its
                # full size, so a cap here hands VP2 a DIFFERENT-sized texture and
                # its filtering then makes the two tiers disagree everywhere, not
                # just on the rows the cap dropped. Same reason the texload branch
                # above carries no cap. The ndim/shape guard below is what handles
                # the degenerate case; a ceiling is not needed for that.
                "            std::lock_guard<std::mutex> _lk(_nodePtr->_ndStateMutex);",
                "            const auto& _sarr = _nodePtr->_ndState.%s;"
                % state["array"],
                "            if (_sarr.ndim() == 2 && _sarr.shape[0] > 0 &&",
                "                    _sarr.shape[1] > 0) {",
                "                _h = (unsigned int)_sarr.shape[0];",
                "                _w = (unsigned int)_sarr.shape[1];",
                "            }",
                "        }",
            ]
    else:
        # Synthetic: no file. Bake a fixed grid; nd_texel needs no image ctx.
        load = [
            "        const unsigned int _w = 256, _h = 256;",
        ]
        if has_raw:
            # Defensive; unreachable via the shipped pipeline, which force-injects
            # a fileName plug for every single-file reader so the `elif` branch
            # runs. texel_args still passes `pix` (has_raw), so declare it null to
            # keep the emitted C++ valid -- nd_texel guards nullptr -> magenta.
            load.append("        const unsigned char* pix = nullptr;")

    block = []
    block.append("// ===========================================================================")
    block.append("// VP2 shading override -- interactive Viewport 2.0 shading for %s." % type_name)
    block.append("// Reuses the built-in mayaFileTexture fragment; bakes the whole buffer via")
    block.append("// nd_texel (shared with compute) and uploads it. The bake is skipped when the")
    block.append("// texture manager already holds this content key -- see the guard below.")
    block.append("// ===========================================================================")
    block.append("namespace {")
    block.append("")
    block.append('const MString kDrawClassification_%s("drawdb/shader/texture/2d/%s");'
                 % (cls, type_name))
    block.append('const MString kRegistrantId_%s("%sOverride");' % (cls, type_name))
    block.append("")
    block.append("class %s : public MHWRender::MPxShadingNodeOverride {" % over)
    block.append("public:")
    block.append("    static MHWRender::MPxShadingNodeOverride* creator(const MObject& obj) {")
    block.append("        return new %s(obj);" % over)
    block.append("    }")
    block.append("    %s(const MObject& obj)" % over)
    block.append("        : MHWRender::MPxShadingNodeOverride(obj), _node(obj) {}")
    block.append("    ~%s() override {}" % over)
    block.append("    MHWRender::DrawAPI supportedDrawAPIs() const override {")
    block.append("        return MHWRender::kAllDevices;")
    block.append("    }")
    block.append("    bool allowConnections() const override { return true; }")
    block.append('    MString fragmentName() const override { return MString("mayaFileTexture"); }')
    block.append("    bool valueChangeRequiresFragmentRebuild(const MPlug*) const override {")
    block.append("        return false;")
    block.append("    }")
    block.append("    void getCustomMappings(")
    block.append("            MHWRender::MAttributeParameterMappingList& mappings) override {")
    block.append('        MHWRender::MAttributeParameterMapping uv("uvCoord", "uvCoord", true, true);')
    block.append("        mappings.append(uv);")
    block.append("    }")
    # Which fragment output a downstream connection resolves to. WITHOUT this,")
    # VP2 cannot resolve a .transparency (or .outAlpha) connection at all, so the
    # viewport and the DG-driven swatch disagree -- the interpreted mPyFile
    # override carries the same three cases. The stock mayaFileTexture fragment
    # already declares outTransparency and fills it with 1 - outAlpha, which is
    # the same derivation the DG side does.
    block.append("    MString outputForConnection(const MPlug& sourcePlug,")
    block.append("                                const MPlug&) override {")
    block.append("        const std::string _n(sourcePlug.partialName(")
    block.append("            false, false, false, false, false, true).asChar());")
    block.append('        if (_n.rfind("outColor", 0) == 0) return MString("outColor");')
    block.append('        if (_n.rfind("outTransparency", 0) == 0)')
    block.append('            return MString("outTransparency");')
    block.append('        if (_n == "outAlpha") return MString("outAlpha");')
    block.append('        return MString("");')
    block.append("    }")
    block += dg
    block.append("    void updateShader(")
    block.append("            MHWRender::MShaderInstance& shader,")
    block.append("            const MHWRender::MAttributeParameterMappingList&) override {")
    block.append("        MStringArray plist; shader.parameterList(plist);")
    block.append("        MString mapParam, sampParam;")
    block.append("        for (unsigned int i = 0; i < plist.length(); ++i) {")
    block.append("            MHWRender::MShaderInstance::ParameterType pt =")
    block.append("                shader.parameterType(plist[i]);")
    block.append("            if (mapParam.length() == 0 && pt == MHWRender::MShaderInstance::kTexture2)")
    block.append("                mapParam = plist[i];")
    block.append("            else if (sampParam.length() == 0 && pt == MHWRender::MShaderInstance::kSampler)")
    block.append("                sampParam = plist[i];")
    block.append("        }")
    block.append("        MHWRender::MRenderer* renderer = MHWRender::MRenderer::theRenderer();")
    block.append("        if (!renderer) return;")
    block.append("        MHWRender::MTextureManager* tmgr = renderer->getTextureManager();")
    block.append("        if (!tmgr) return;")
    block.append("        if (mapParam.length()) {")
    # nd_runtime throws on every bad shape/index and a lowered `raise` throws the
    # same, so the bake CAN throw. compute() has lowered_guard for that; the
    # viewport had nothing, and an exception escaping updateShader takes Maya's
    # renderer with it. Skip the frame instead.
    block.append("        try {")
    # The bake call's OWN argument list. Identical to texel_args except that a
    # corner-grid bake pins the wrap-mode inputs to CLAMP (1). This list is used
    # ONLY by the loop below; compute() builds its arguments in _compute_call
    # straight off the real MDataHandles, and the stateful PRIME call above keeps
    # texel_args -- so the override cannot leak into either.
    bake_args = list(texel_args)
    if corner and wrap_clamp:
        _forced = {"_m_%s" % w.var: "(%s)1" % w.member_type for w in wrap_clamp}
        bake_args = [_forced.get(a, a) for a in bake_args]
    if corner:
        # CORNER grid. `max(_h - 1, 1)` mirrors the interpreted tier's own
        # `1.0 - py / float(max(h - 1, 1))`, so a 1-pixel image cannot divide by
        # zero and still lands on row 0.
        v_expr = "1.0 - (double)py / (double)(_h > 1 ? _h - 1 : 1)"
        u_expr = "(double)x / (double)(_w > 1 ? _w - 1 : 1)"
    else:
        v_expr = "1.0 - ((double)py + 0.5) / (double)_h"
        u_expr = "((double)x + 0.5) / (double)_w"
    # THE BAKE GUARD. Maya calls updateShader on every viewport refresh, and the
    # loop below re-synthesises the WHOLE buffer. Measured on a STATIC 1024x1024
    # fileTexture -- no time input, nothing driving it: 21.7 ms/frame (46 fps),
    # spent entirely rebuilding pixels that had not changed. At 1024x1024 that is
    # 1,048,576 nd_texel calls and a 16 MB float buffer, per node, per frame.
    #
    # texName is already a content key over every input the bake reads, so ask
    # the texture manager for it FIRST and skip the bake on a hit.
    #
    # This is NOT the instance-level `_last_acquired_*` short-circuit the
    # interpreted tier deliberately disabled (``_api2/mpy_file.py:1514``). That
    # one skipped the RE-BIND, which is wrong because Maya dispatches against
    # several MShaderInstances (viewport, material viewer, swatch generator) with
    # no way to tell them apart. Here setParameter still runs on every call --
    # only the synthesis is skipped, through the very acquireTexture name cache
    # that comment cites as the reason instance caching is unnecessary.
    #
    # A `state` node is excluded STRUCTURALLY, not by preference: its key folds
    # in a hash of the baked pixels (below), so the key does not exist until the
    # bake has already run. gameOfLifeTex measures 470 fps regardless.
    guard = not state
    pad = "    " if guard else ""
    if guard:
        block.append("            " + "\n            ".join(key_parts))
        block.append("            MHWRender::MTexture* tex = tmgr->findTexture(texName);")
        block.append("            if (!tex) {")
    block += ["    " + pad + ln for ln in load]
    block.append("            " + pad + "std::vector<float> baked((size_t)_w * _h * 4);")

    # ---- ROW-PARALLEL BAKE -------------------------------------------------
    # Every texel is a pure function of (u, v) plus inputs held constant for the
    # bake, workers write DISJOINT row slices, and there is no accumulation or
    # reduction -- so the buffer is bit-identical regardless of thread count.
    # Measured before this: ~33 ms for a 1024x1024 grid, which is 30 fps for any
    # node that must genuinely re-bake every frame (scanlineTex has `frame` in
    # its content key; a state node can never be cache-guarded at all).
    #
    # A worker MUST NOT let an exception escape: nd_runtime throws on a bad
    # shape/index and a lowered `raise` throws the same, and an exception
    # leaving a std::thread calls std::terminate -- i.e. it would take Maya down
    # rather than skip a frame. Each worker catches and flags instead.
    if state:
        # STATE NODES ONLY. nd_texel's body carries its own
        # `lock_guard(_ndStateMutex)` -- that is the ported compute body, reused
        # verbatim, and compute() genuinely needs the lock against concurrent DG
        # evaluation, so it cannot be stripped here. At 1024x1024 it was
        # 1,048,576 acquisitions of the SHARED mutex per frame: a large serial
        # cost on its own, and an absolute barrier to threading the loop.
        #
        # So take the real lock ONCE around the dispatch below -- the board is
        # then stable for the whole bake, which is what the per-texel lock was
        # buying anyway -- and hand nd_texel a LOCAL, per-worker mutex instead.
        # The body compiles unchanged, the state is still protected, and the
        # per-texel acquisition becomes uncontended and thread-private.
        #
        # What makes the workers safe to run against ONE state without the real
        # mutex between them is that they perform no state transition at all:
        #
        #   advance -- the body's transition is `if (shape_bad || fr != lastFrame)
        #     { ...; st.lastFrame = fr; }`. The PRIME call above already ran it,
        #     on the same cached scalars the loop uses, so the predicate is dead
        #     for every worker texel. Only the prime can advance a frame.
        #   bake-to-disk -- `nd_tex_write` holds its OWN `static _ndWriteMutex`
        #     and publishes through a temp + rename, so it is serialised and
        #     atomic regardless of who calls it (that helper already anticipates
        #     "the VP2 override bake and the Hypershade swatch worker"). It is
        #     likewise settled by the prime via st.bakedFrame.
        #
        # Holding the real mutex across the dispatch is also STRICTER than what
        # it replaced: compute() could previously interleave between texels and
        # advance the board mid-bake; now it waits, so the frame is coherent.
        bake_args = [("_ndLocalStateMutex" if a == "_nodePtr->_ndStateMutex"
                      else a) for a in bake_args]
    block.append("            " + pad + "std::atomic<bool> _bakeFailed(false);")
    block.append("            " + pad + "auto _bakeRows = [&](unsigned int _y0, "
                                        "unsigned int _y1) {")
    block.append("                " + pad + "try {")
    if state:
        block.append("                    " + pad + "std::mutex _ndLocalStateMutex;")
    block.append("                    " + pad + "for (unsigned int py = _y0; py < _y1; ++py) {")
    block.append("                        " + pad + "double v = %s;" % v_expr)
    block.append("                        " + pad + "float* drow = &baked[(size_t)py * _w * 4];")
    block.append("                        " + pad + "for (unsigned int x = 0; x < _w; ++x) {")
    block.append("                            " + pad + "double u = %s;" % u_expr)
    block.append("                            " + pad + "float r = 0.0f, g = 0.0f, b = 0.0f, a = 0.0f;")
    for o in extras:
        block.append("                            " + pad + "%s _dump_%s = %s;"
                     % (o.ctype, o.var, _CTYPE_DEFAULT.get(o.ctype, "0")))
    block.append("                            " + pad + "nd_texel(%s);" % ", ".join(bake_args))
    block.append("                            " + pad + "drow[x*4+0]=r; drow[x*4+1]=g; drow[x*4+2]=b; drow[x*4+3]=a;")
    block.append("                        " + pad + "}")
    block.append("                    " + pad + "}")
    block.append("                " + pad + "} catch (...) { _bakeFailed.store(true); }")
    block.append("            " + pad + "};")
    # Scoped so the state lock (state nodes only) is held for the DISPATCH and
    # nothing else -- not the hash, not acquireTexture, not setParameter. The
    # prime call and the shape read in `load` above take the same mutex and are
    # already scoped closed by here; re-locking a held std::mutex would deadlock,
    # so this scope must stay below them.
    block.append("            " + pad + "{")
    if state:
        block.append("                " + pad + "std::lock_guard<std::mutex> "
                                                "_bakeStateLock(_nodePtr->_ndStateMutex);")
    block.append("                " + pad + "unsigned int _nthr = "
                                            "std::thread::hardware_concurrency();")
    block.append("                " + pad + "if (_nthr == 0u) _nthr = 1u;")
    block.append("                " + pad + "if (_nthr > 12u) _nthr = 12u;")
    # One row per worker minimum: a 20x20 Game of Life board is a real case, and
    # spawning 12 threads to do 20 rows costs more than it saves.
    block.append("                " + pad + "if (_nthr > _h) _nthr = (_h > 0u) ? _h : 1u;")
    block.append("                " + pad + "if (_nthr <= 1u) {")
    block.append("                    " + pad + "_bakeRows(0u, _h);")
    block.append("                " + pad + "} else {")
    block.append("                    " + pad + "const unsigned int _chunk = "
                                                "(_h + _nthr - 1u) / _nthr;")
    block.append("                    " + pad + "std::vector<std::thread> _bakeThreads;")
    block.append("                    " + pad + "_bakeThreads.reserve(_nthr - 1u);")
    block.append("                    " + pad + "for (unsigned int _t = 1u; _t < _nthr; ++_t) {")
    block.append("                        " + pad + "const unsigned int _y0 = _t * _chunk;")
    block.append("                        " + pad + "if (_y0 >= _h) break;")
    block.append("                        " + pad + "const unsigned int _y1 = "
                                                    "std::min(_y0 + _chunk, _h);")
    # std::thread's constructor throws std::system_error when the OS refuses a
    # thread, and letting that escape would destroy _bakeThreads with joinable
    # members still in it -- std::terminate, i.e. Maya dies. Run the chunk here
    # instead: slower, but the frame still bakes.
    block.append("                        " + pad + "try {")
    block.append("                            " + pad + "_bakeThreads.emplace_back(_bakeRows, _y0, _y1);")
    block.append("                        " + pad + "} catch (...) { _bakeRows(_y0, _y1); }")
    block.append("                    " + pad + "}")
    # This thread takes chunk 0 rather than idling while N-1 workers run.
    block.append("                    " + pad + "_bakeRows(0u, std::min(_chunk, _h));")
    block.append("                    " + pad + "for (std::thread& _th : _bakeThreads)")
    block.append("                        " + pad + "if (_th.joinable()) _th.join();")
    block.append("                " + pad + "}")
    block.append("            " + pad + "}")
    block.append("            " + pad + "if (_bakeFailed.load()) return;")
    block.append("            " + pad + "MHWRender::MTextureDescription desc;")
    block.append("            " + pad + "desc.setToDefault2DTexture();")
    block.append("            " + pad + "desc.fWidth = _w; desc.fHeight = _h; desc.fDepth = 1;")
    block.append("            " + pad + "desc.fBytesPerRow = _w * 4 * 4;")
    block.append("            " + pad + "desc.fBytesPerSlice = desc.fBytesPerRow * _h;")
    block.append("            " + pad + "desc.fMipmaps = 1; desc.fArraySlices = 1;")
    block.append("            " + pad + "desc.fFormat = MHWRender::kR32G32B32A32_FLOAT;")
    block.append("            " + pad + "desc.fTextureType = MHWRender::kImage2D;")
    block.append("            " + pad + "desc.fEnvMapType = MHWRender::kEnvNone;")
    if not guard:
        block.append("            " + "\n            ".join(key_parts))
    if state:
        # The scalar-input key is not a content key, and for a path-dependent
        # simulation that is not enough: scrub 1 -> 2 -> 1 and every input is
        # byte-identical to the first visit while the BOARD has advanced two
        # generations, so acquireTexture hands back the stale generation-0
        # texture. Fold the pixels themselves in. The interpreted tier does the
        # same thing with int(board.sum()) in its texture name.
        block.append("            {")
        block.append("                unsigned long long _hv = 1469598103934665603ULL;")
        block.append("                const unsigned char* _hb =")
        block.append("                    (const unsigned char*)baked.data();")
        block.append("                const size_t _hn = baked.size() * sizeof(float);")
        block.append("                for (size_t _i = 0; _i < _hn; ++_i) {")
        block.append("                    _hv ^= (unsigned long long)_hb[_i];")
        block.append("                    _hv *= 1099511628211ULL;")
        block.append("                }")
        block.append('                texName += MString("|c=");')
        block.append("                texName += (int)(_hv & 0x7FFFFFFFULL);")
        block.append("            }")
    if guard:
        # Inside `if (!tex)`: assign to the tex declared above, then close.
        block.append("                tex = tmgr->acquireTexture(")
        block.append("                    texName, desc, baked.data(), false);")
        block.append("            }")
    else:
        block.append("            MHWRender::MTexture* tex =")
        block.append("                tmgr->acquireTexture(texName, desc, baked.data(), false);")
    block.append("            if (tex) {")
    block.append("                MHWRender::MTextureAssignment assign; assign.texture = tex;")
    block.append("                shader.setParameter(mapParam, assign);")
    block.append("                tmgr->releaseTexture(tex);")
    block.append("            }")
    block.append("        } catch (const std::exception&) { return; }")
    block.append("        }")
    block.append("        if (sampParam.length()) {")
    block.append("            MHWRender::MSamplerStateDesc sdesc; sdesc.setDefaults();")
    if state and state["array"]:
        # Baked at the simulation's OWN resolution, so one texel IS one cell.
        # Linear filtering would grey-blend neighbouring cells and wrap would
        # bleed the far edge in -- the interpreted tier picks point+clamp here
        # for the same reason ("NEAREST filtering keeps the cells crisp").
        block.append("            sdesc.filter = MHWRender::MSamplerState::kMinMagMipPoint;")
        block.append("            sdesc.addressU = MHWRender::MSamplerState::kTexClamp;")
        block.append("            sdesc.addressV = MHWRender::MSamplerState::kTexClamp;")
    else:
        # CLAMP, not WRAP: every interpreted mPyFile Viewport tier sets
        # kTexClamp, and the buffer uploaded here is the WHOLE texture -- the
        # node's own wrapModeU/V already ran inside nd_texel while it was baked.
        # Repeating it on the GPU wraps a second time, and on the corner grid it
        # folds the last column/top row back onto the first.
        block.append("            sdesc.filter = MHWRender::MSamplerState::kMinMagMipLinear;")
        block.append("            sdesc.addressU = MHWRender::MSamplerState::kTexClamp;")
        block.append("            sdesc.addressV = MHWRender::MSamplerState::kTexClamp;")
    block.append("            const MHWRender::MSamplerState* ss =")
    block.append("                MHWRender::MStateManager::acquireSamplerState(sdesc);")
    block.append("            if (ss) shader.setParameter(sampParam, *ss);")
    block.append("        }")
    block.append("    }")
    block.append("private:")
    block.append("    MObject _node;")
    block += members
    block.append("};")
    block.append("")
    block.append("MCallbackId g_timeChangedCb_%s = 0;" % cls)
    block.append("void ndOnTimeChanged_%s(void*) {" % cls)
    block.append("    MItDependencyNodes it(MFn::kInvalid);")
    block.append("    for (; !it.isDone(); it.next()) {")
    block.append("        MFnDependencyNode fn(it.thisNode());")
    block.append("        if (fn.typeId() == %s::id) {" % cls)
    block.append('            MString cmd("dgdirty ");')
    block.append('            cmd += fn.name(); cmd += ".outColor";')
    block.append("            MGlobal::executeCommand(cmd, false, false);")
    block.append("        }")
    block.append("    }")
    block.append("}")
    block.append("")
    block.append("}  // namespace")
    block.append("")
    return "\n".join(block), over


def _kept_cmd_stmts(hook: str, call: str) -> List[str]:
    """The bundled-@maya_command statements the scaffold already spliced into a
    plugin hook, lifted out of *hook* verbatim (see step (7): this module swaps
    both hooks WHOLESALE, so anything not carried across is dropped)."""
    return [ln.strip() for ln in hook.splitlines() if call in ln]


def _init_plugin(cls, type_name, cmd_register=()):
    over = cls + "Override"
    classif = ("texture/2d:swatch/2dTextureSwatchGen:"
               "drawdb/shader/texture/2d/%s" % type_name)
    lines = [
        "MStatus initializePlugin(MObject obj) {",
        '    MFnPlugin plugin(obj, "mpynode-native", "1.0", "Any");',
        '    MString _classif("%s");' % classif,
        '    MStatus st = plugin.registerNode("%s", %s::id, %s::creator,'
        % (type_name, cls, cls),
        "        %s::initialize, MPxNode::kDependNode, &_classif);" % cls,
        "    if (!st) return st;",
    ]
    lines += ["    " + s for s in cmd_register]
    lines += [
        "    MHWRender::MDrawRegistry::registerShadingNodeOverrideCreator(",
        "        kDrawClassification_%s, kRegistrantId_%s, %s::creator);"
        % (cls, cls, over),
        "    g_timeChangedCb_%s = MEventMessage::addEventCallback(" % cls,
        '        "timeChanged", ndOnTimeChanged_%s);' % cls,
        "    return MS::kSuccess;",
        "}",
    ]
    return "\n".join(lines)


def _uninit_plugin(cls, cmd_deregister=()):
    lines = [
        "MStatus uninitializePlugin(MObject obj) {",
        "    MFnPlugin plugin(obj);",
        "    if (g_timeChangedCb_%s) {" % cls,
        "        MMessage::removeCallback(g_timeChangedCb_%s);" % cls,
        "        g_timeChangedCb_%s = 0;" % cls,
        "    }",
        "    MHWRender::MDrawRegistry::deregisterShadingNodeOverrideCreator(",
        "        kDrawClassification_%s, kRegistrantId_%s);" % (cls, cls),
    ]
    lines += ["    " + s for s in cmd_deregister]
    lines += [
        "    return plugin.deregisterNode(%s::id);" % cls,
        "}",
    ]
    return "\n".join(lines)


def _lowered_region(cpp: str):
    """``(body, full)`` for a deterministically-lowered compute, else ``None``.

    ``full`` spans the banner through the guard's closing brace (what compute()
    hands over to the nd_texel call); ``body`` is only the statements INSIDE the
    guard's ``try``. The catch arm is deliberately excluded: it ends in
    ``return MS::kFailure;``, which cannot appear in a void nd_texel -- compute()
    re-emits the guard around the call instead, so its error behaviour is
    unchanged.
    """
    i0 = cpp.find(_LOWERED_BEGIN)
    if i0 < 0:
        return None
    i1 = cpp.find(_LOWERED_END, i0)
    if i1 < 0:
        return None
    end = cpp.rfind("}", i0, i1)
    if end < 0:
        return None
    full = cpp[i0:end + 1]
    t = full.find("try {")
    c = full.rfind("} catch (const std::exception&")
    if t < 0 or c < 0 or c < t:
        return None
    return full[t + len("try {"):c], full


def _port_region(cpp: str):
    """``(body, full)`` for an AI-ported compute, else ``None``.

    Codegen's frame is the OUTERMOST BEGIN..END pair; a ported body that echoed
    the marker comments nests a second pair inside (an AI artifact). Anchor on
    the FIRST BEGIN and the LAST END and drop nested marker lines.
    """
    if _PORT_BEGIN not in cpp or _PORT_END not in cpp:
        return None
    b = cpp.index(_PORT_BEGIN) + len(_PORT_BEGIN)
    e = cpp.rindex(_PORT_END)
    body = "\n".join(ln for ln in cpp[b:e].splitlines()
                     if _PORT_BEGIN not in ln and _PORT_END not in ln)
    return body, cpp[cpp.index(_PORT_BEGIN):e + len(_PORT_END)]


def _is_stateful(body: str) -> bool:
    """True when the compute region mutates PER-INSTANCE persistent state
    (spec_model's ``_NdState`` / ``_ndStateMutex`` node members).

    This used to be a REFUSAL: the state members are nested in the node class
    and so unreachable from an nd_texel emitted above it, and calling that texel
    once per pixel looked like re-running the whole simulation step per pixel.
    Both are now handled, so it selects a variant instead of blocking one:

      * reachability -- the ``_NdState`` struct is hoisted to file scope (still
        inside the per-node namespace the bundler wraps) and the state pair is
        threaded into nd_texel by reference, exactly as ``_texCache``/
        ``_texMutex`` already are for the blessed texture loader;
      * cost -- the simulation advances under the author's own frame guard
        (``fr != st.lastFrame``), which latches on the FIRST texel, so texels
        2..N are the cheap sample path. That is the same idempotency the
        interpreted tier relies on to let Compute and Viewport both call
        ``_gol_advance`` without double-stepping.
    """
    return "_ndState" in body or "_NdState" in body


def skip_reason(cpp: str) -> str:
    """Why ``inject_vp2_override`` will not transform *cpp*, or "" when it will.

    Exists so a skip is REPORTABLE. This module going quiet is exactly how the
    mPyFile group shipped with no override at all once its computes started
    lowering deterministically: a silent no-op reads identically to success.
    """
    if "MPxShadingNodeOverride" in cpp:
        return "override already present"
    reg = _port_region(cpp) or _lowered_region(cpp)
    if reg is None:
        return "no ported or lowered compute region"
    if _is_stateful(reg[0]) and _parse_state(cpp) is None:
        # Stateful bodies ARE supported (see _is_stateful), but only through the
        # hoisted-struct path -- which needs the struct to be findable. An
        # AI-ported node that rolled its own state shape has none, so refuse
        # rather than emit an nd_texel referencing members it cannot reach.
        return "compute mutates per-instance state with no _NdState struct"
    if _CLASS_RE.search(cpp) is None:
        return "no MPxNode class"
    if not any(i.is_uv for i in _parse_inputs(cpp)):
        return "no uvCoord input (not a per-pixel texture)"
    return ""


def can_inject(cpp: str) -> bool:
    """True when *cpp* is a single-node texture compute this module can transform
    -- either an AI PORT region or a deterministically-lowered one -- with an
    MPxNode class and no override already spliced in."""
    return not skip_reason(cpp)


def inject_vp2_override(cpp: str, spec: Optional[dict] = None) -> str:
    """Splice the VP2 shading override into a finalized single-node texture
    ``.cpp``. Idempotent + a no-op when the ``.cpp`` is not a recognized texture
    port (so it is safe to run over every node in a bundle)."""
    if "MPxShadingNodeOverride" in cpp:
        return cpp  # already injected
    if not can_inject(cpp):
        return cpp

    cm = _CLASS_RE.search(cpp)
    cls = cm.group(1)
    rm = _REGISTER_RE.search(cpp)
    if not rm:
        return cpp
    type_name = rm.group(1)

    inputs = _parse_inputs(cpp)
    if not any(i.is_uv for i in inputs):
        return cpp  # a texture without uvCoord is not a per-pixel node we bake
    # An image node loads its buffer either from a single fileName (nd_img_load_raw)
    # or from a string-array path list (nd_img_composite, the multi-file node); both
    # feed nd_texel the same _imgPixels/_imgW/_imgH/_imgOK context.
    has_raw = (("nd_img_load_raw" in cpp or "nd_img_composite" in cpp)
               and "_imgPixels" in cpp)
    comp = _parse_composite_path(cpp)
    # Extra node-scalar outputs the ported body writes (e.g. maxWidth/maxHeight):
    # nd_texel gets a shim + out-ref for each so the body ports in unchanged.
    extras = _extra_outputs(cpp)
    # A deterministically-lowered texture reads its pixels through the blessed
    # nd_tex_load_linear kernel, whose cache + mutex are INSTANCE members of the
    # node class -- unreachable from a free nd_texel emitted above it. Pass them
    # in under their own names so the body still compiles unchanged; the override
    # carries its own pair, exactly as it already does for NdImgRawCache.
    # Matched as a PATTERN over any nd_tex_* kernel, not as one literal call.
    # This was `"nd_tex_load_linear(_texCache, _texMutex" in cpp`, which went
    # dark the moment a second kernel (nd_tex_composite_layers) took the pair in
    # a different argument position: nd_texel then lost the parameters while its
    # body still referenced them, and the TU failed to compile. Keyed on the
    # member names appearing as adjacent arguments to a kernel, so any future
    # kernel that threads the cache is picked up without editing this line.
    has_texcache = bool(
        re.search(r"nd_tex_\w+\([^;]*\b_texCache\s*,\s*_texMutex\b", cpp))

    # (1) extract the compute body to become nd_texel. Two shapes: an AI PORT
    # region, or a deterministically-lowered guard. `full` is captured HERE,
    # before (2)/(3) insert text, so (4) can replace it by value.
    _lowered = _lowered_region(cpp)
    if _lowered is not None:
        port_body, port_full = _lowered
    else:
        port_body, port_full = _port_region(cpp)

    # Persistent per-instance state, threaded into nd_texel so the viewport bake
    # runs the SAME simulation as compute() instead of forking a second one.
    state = _parse_state(cpp) if _is_stateful(port_body) else None

    # Array (multi) inputs only join the signature when the extracted body
    # actually names one. An AI-ported composite reads its layers through the
    # hoisted nd_img_composite/_imgPixels context instead, and adding an unused
    # vector param there would change output on a path that already works.
    inputs = [i for i in inputs
              if not i.multi or re.search(r"\b%s\b" % i.var, port_body)]
    texload = _parse_texload(port_body, inputs) if has_texcache else None
    # Only meaningful alongside a texload probe: it is the corner bake grid that
    # needs the endpoint fixed, and that grid only exists on those branches.
    wrap_clamp = _parse_wrap_override(port_body, inputs) if texload else None

    # (2) includes after <mutex> (raw-cache) or before the class otherwise.
    if "#include <mutex>\n" in cpp:
        cpp = cpp.replace("#include <mutex>\n",
                          "#include <mutex>\n" + _OVERRIDE_INCLUDES, 1)
    else:
        cpp = cpp.replace("\nclass %s " % cls,
                          "\n" + _OVERRIDE_INCLUDES + "\nclass %s " % cls, 1)

    # (2.5) hoist the nested _NdState struct to file scope so the free nd_texel
    # can name the type. The class keeps its `_NdState _ndState;` member, which
    # now resolves to the hoisted one -- and both stay inside the per-node
    # `namespace nd_<type>` the bundler wraps, so a mega build cannot collide.
    if state:
        cpp = cpp.replace(state["struct"], "", 1)
        cpp = cpp.replace(
            "\nclass %s " % cls,
            "\n// --- persistent per-instance state, hoisted out of %s so the\n"
            "// --- shared nd_texel below can take it by reference.\n"
            "%s\nclass %s "
            % (cls, textwrap.dedent(state["struct"]).strip(), cls), 1)

    # (3) nd_texel just before the class.
    texel = _make_texel_fn(port_body, inputs, has_raw, extras, has_texcache,
                           state is not None)
    cpp = cpp.replace("\nclass %s " % cls, "\n" + texel + "\nclass %s " % cls, 1)

    # (4) replace compute()'s region with the nd_texel call. `port_full` was
    # captured in step (1) from the original text; the nd_texel inserted in (3)
    # has its markers stripped, so this exact-substring replace only hits compute().
    # A lowered region carried its own try/catch, so the call re-emits that guard
    # and compute()'s error behaviour is byte-for-byte what it was.
    cpp = cpp.replace(
        port_full,
        _compute_call(inputs, has_raw, extras, has_texcache,
                      guard_type=(type_name if _lowered is not None else None),
                      has_state=state is not None),
        1)

    # (5) override class + callback immediately before initialize().
    block, _over = _make_override_block(cls, type_name, inputs, has_raw, extras,
                                        comp, has_texcache, texload, state,
                                        wrap_clamp)
    m = re.search(r"\nMStatus \w+::initialize\(\) \{", cpp)
    if not m:
        return cpp
    cpp = cpp[:m.start()] + "\n\n" + block + cpp[m.start() + 1:]

    # (6) setUsedAsFilename(true) on the fileName attr (Hypershade file-browse +
    # relative-path resolution). Only when the node reads a file.
    if has_raw:
        cpp = re.sub(
            r'(aFileName = tAttr\.create\("fileName"[^;]*;\n)',
            r"\1    tAttr.setUsedAsFilename(true);\n", cpp, count=1)

    # (7) swap the plugin entry points. WHOLESALE, so the bundled-@maya_command
    # register/deregister statements the scaffold spliced into the hooks are
    # lifted out and re-emitted in the new hooks (register after registerNode's
    # success check, deregister before deregisterNode) -- otherwise a texture
    # node's commands would vanish from the VP2 build. No commands ->
    # byte-identical.
    def _swap_init(_m):
        return _init_plugin(cls, type_name,
                            _kept_cmd_stmts(_m.group(0), "plugin.registerCommand("))

    def _swap_uninit(_m):
        return _uninit_plugin(
            cls, _kept_cmd_stmts(_m.group(0), "plugin.deregisterCommand("))

    cpp, n1 = re.subn(r"MStatus initializePlugin\(MObject obj\) \{.*?\n\}",
                      _swap_init, cpp, count=1, flags=re.S)
    cpp, n2 = re.subn(r"MStatus uninitializePlugin\(MObject obj\) \{.*?\n\}",
                      _swap_uninit, cpp, count=1, flags=re.S)
    if n1 != 1 or n2 != 1:
        raise RuntimeError("inject_vp2_override: init/uninit swap failed "
                           "(init=%d uninit=%d)" % (n1, n2))
    return cpp
