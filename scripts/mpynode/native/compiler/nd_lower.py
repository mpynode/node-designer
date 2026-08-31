"""nd_lower -- lower an mpynode compute BLOCK into a node compute() body.

This is the codegen-integration half of the deterministic port pipeline. Given
codegen's input/output descriptor dicts (each ``{plug, member, kind, meta:{type,
is_array}}``) and the node's Python compute source, it emits the C++ that:

  1. MATERIALISES every ``self.<attr>`` the compute reads -- a Maya input local
     (``in_<member>``: a scalar, a ``double3``, a ``std::vector<T>``, or a
     ``std::vector<MVector>``) -- into an ``nd::`` value bound to the transpiler
     environment under ``py_to_cpp.env_cpp_name("self.<attr>")``;
  2. runs the transpiled statement block (``py_to_cpp.transpile_compute_block``),
     which reads those bindings and, at each ``self.<out> = expr`` assignment,
     invokes a WRITER that stores the produced ``nd::`` value into codegen's sink
     (a scalar handle ``h_<member>`` or an array buffer ``out_<member>``);
  3. is rejected wholesale (``UnsupportedSpec`` -> caller returns ``None`` ->
     codegen falls back to the AI porter unchanged) if ANY input/output type is
     outside the supported numeric subset, the compute uses an unsupported
     construct, or a declared output is never written.

Supported I/O (numeric only -- everything nd:: can represent bit-faithfully):
  * scalar   : float/double/int/bool/enum/angle/time
  * 1-D array: float/double/int/bool/enum/angle/time            -> nd shape (N,)
  * vector   : vector/euler (a double3)                          -> nd shape (3,)
  * vec array: vector/euler multi (std::vector<MVector>)         -> nd shape (N,3)
Unsupported (matrix/string/hex/quaternion/float2/color, matrix arrays, meshes,
nurbs) reject -- those keep the existing AI-porter path with zero regression.

The nd:: element dtype per Maya attr type mirrors nd_runtime.h (double/int64/bool
only). Reads convert the Maya container element type to the nd dtype when they
differ (float->double, int->int64, enum(short)->int64); writes convert back.
"""

from __future__ import annotations

import ast
import copy
import re

from mpynode.native.compiler import py_to_cpp
from mpynode.native.compiler.errors import UnsupportedSpec
from mpynode.native.compiler.py_to_cpp import (scalar_t, array_t, str_t,
                                      strv_t, env_cpp_name, Val)
from mpynode.native.compiler.kernels import file_texture_cpp
from mpynode.native.compiler.kernels import blessed_transpile
from mpynode._common.interface.morph_method_interface import (WEIGHT_PLUG,
                                                              LIVE_CPP_VARS)

# nd element dtype for each Maya attr type (only numeric types map).
_ND_DTYPE = {
    "float": "double", "double": "double", "angle": "double", "time": "double",
    "int": "int64", "enum": "int64",
    "bool": "bool",
}
# nd C++ element type for an nd dtype.
_ND_CTYPE = {"double": "double", "int64": "int64_t", "bool": "bool"}
# Maya C++ container element type per attr type (mirrors codegen._CPP for the
# numeric subset; used to decide whether a read needs an element conversion).
_MAYA_CTYPE = {
    "float": "float", "double": "double", "int": "int", "bool": "bool",
    "enum": "short", "angle": "double", "time": "double",
}
# Types carried as a 3-component vector (double3 scalar / std::vector<MVector>).
_VEC_TYPES = ("vector", "euler")

# ---- geometry-INPUT read surface (Phase 6). A typed geo INPUT (mesh/
# nurbsCurve/nurbsSurface) is handed to compute() as ``in_<member>`` (an MFn*)
# plus ``in_<member>_obj`` (the DATA MObject, for null-guarding) by
# emit_attr._read_line. The interpreted wrapper (_api2/geometry.py) exposes
# a numpy READ SURFACE off that same data
# (.points/.counts/.indices/.normals for a mesh; CVs/knots/degree/form for NURBS).
# nd_lower reproduces it DETERMINISTICALLY: it AST-rewrites each supported
# ``self.<geoIn>.<channel>`` read into a synthetic
# ``self.__ndgeo_<member>_<channel>_`` attr bound to an nd:: value materialised
# from ``in_<member>`` via the SAME MFn call the wrapper uses, so the compiled
# read is byte-identical. Any geo use OUTSIDE this surface (``.fn``,
# ``.component_tags``, ``.region(...)``, ``.copy()``, a bare pass-through, an
# array geo input, an unsupported channel) rejects the whole lowering -> the AI
# porter path is kept unchanged.
# attr_type -> internal geo kind used by the channel tables below.
_GEO_IN_TYPE_KIND = {"mesh": "mesh", "nurbsCurve": "curve", "nurbsSurface": "surface"}
# Supported deterministic read-surface channels per geo kind. (colors and
# component_tags are intentionally absent: colors round-trips through a per-face-
# vertex layout the transpiler has no shape for yet, and tags need a component
# decode -- both stay on the porter until first-class.)
_GEO_IN_CHANNELS = {
    "mesh": {"points", "counts", "indices", "normals", "uvs"},
    "curve": {"points", "cvs", "degree", "form", "knots"},
    "surface": {"points", "cvs", "num_u", "num_v", "degree_u", "degree_v",
                "form_u", "form_v", "knots_u", "knots_v"},
}
# Prefix for the synthetic self-attr a rewritten geo channel read binds to.
_GEO_SYN_PREFIX = "__ndgeo_"
# Pseudo-channel for ``len(self.<geoArr>)`` (whole list, no element index).
_GEO_ARR_LEN = "__len__"


def _tag_syn(member, op, tag):
    """A valid-identifier synthetic self-attr name for a component-tag read
    (``op`` in {region, tagidx}); the tag NAME is sanitised into the identifier."""
    return "%s%s_%s_%s_" % (_GEO_SYN_PREFIX, member, op, re.sub(r"\W", "_", tag))


def _is_geo_input(meta):
    # A SINGLE (non-array) typed geo input, read via the ``in_<m>`` MFn* the
    # emitter declares (see _materialise_geo_channel). Array geo inputs go through
    # _is_geo_array_input (the ``std::vector<Nd<Kind>>`` struct model) instead.
    return (not meta.get("is_array")) and meta.get("type") in _GEO_IN_TYPE_KIND


def _is_geo_array_input(meta):
    # An ARRAY (multi/list) typed geo input, read via the emitter's
    # ``std::vector<Nd<Kind>> in_<m>`` (see _materialise_geo_array_channel). Only
    # the plain MPxNode path declares that vector, so array-geo lowering is gated to
    # lower_compute (allow_geo_array=True); other families fall back to the porter.
    return bool(meta.get("is_array")) and meta.get("type") in _GEO_IN_TYPE_KIND

# ---- geometry-generator contract (mesh/curve/surface). The geo codegen emitter
# (_generate_geo_cpp) synthesises the typed geo output and reproduces the
# MFn*::create marshalling itself; the PORT region only has to FILL a fixed set
# of C++ buffers from the Python compute, which nd_lower can produce when the
# geometry math is pure-numeric. The compute's trailing
# ``self.<outMesh|outCurve|outSurface> = build_default_output(...)`` is the
# framework's build step -- codegen reproduces it natively, so nd_lower STRIPS
# that assignment and writes the flat buffers the emitter declared instead.
# Which synthesised geo output attr each kind assigns (stripped before lowering).
_GEO_OUT_ATTR = {"mesh": "outMesh", "curve": "outCurve", "surface": "outSurface"}
# Dataclass constructor name per kind. When the compute assigns
# ``self.<outAttr> = Mesh(...)`` / ``NurbsCurve(...)`` / ``NurbsSurface(...)``
# the lowerer REWRITES it into synthetic ``self.<field> = <expr>`` buffer writes
# (see _rewrite_geo_constructor), so the same buffer-fill machinery applies.
_GEO_CTOR_CLASS = {"mesh": "Mesh", "curve": "NurbsCurve", "surface": "NurbsSurface"}
# Positional field order for each dataclass ctor (matches _api2/geometry.py). A
# positional arg at index i maps to the i-th field; keyword args map by name.
_GEO_CTOR_POSITIONAL = {
    "mesh": ("points", "counts", "indices", "normals", "normal_indices",
             "colors", "color_indices"),
    "curve": ("points", "degree", "periodic", "kv"),
    "surface": ("points", "degree_u", "degree_v", "periodic_u", "periodic_v",
                "kv_u", "kv_v", "num_u", "num_v"),
}
# self.<attr> the compute writes -> (emitter buffer name, buffer kind). Buffer
# kinds: "mpoint_arr" (std::vector<MPoint>), "int_arr" (std::vector<int>),
# "int_scalar" (a plain int the emitter declared), "vec3_arr"
# (std::vector<MVector>), "color_arr" (std::vector<MColor>, RGBA), "double_arr"
# (std::vector<double>), "bool_scalar" (an int 0/1). Several attrs may target the
# same buffer (curve/surface accept self.cvs OR self.points for the CV grid;
# dataclass ``num_u`` and flat ``num_cvs_u`` both fill numU; ``kv``/``knots``
# both fill knots). Non-required buffers (normals/colors/periodic/knots) are
# optional -- absent = the emitter's default (smooth normals / no color set /
# open form / uniform knots), matching the interpreted marshaller.
_GEO_BUFFERS = {
    "mesh": {
        "points":         ("points",        "mpoint_arr"),
        "counts":         ("counts",        "int_arr"),
        "indices":        ("indices",       "int_arr"),
        "normals":        ("normals",       "vec3_arr"),
        "normal_indices": ("normalIndices", "int_arr"),
        "colors":         ("colors",        "color_arr"),
        "color_indices":  ("colorIndices",  "int_arr"),
    },
    "curve": {
        "points":   ("cvs",      "mpoint_arr"),
        "cvs":      ("cvs",      "mpoint_arr"),
        "degree":   ("degree",   "int_scalar"),
        "periodic": ("periodic", "bool_scalar"),
        "kv":       ("knots",    "double_arr"),
        "knots":    ("knots",    "double_arr"),
    },
    "surface": {
        "points":     ("cvs",       "mpoint_arr"),
        "cvs":        ("cvs",       "mpoint_arr"),
        "num_cvs_u":  ("numU",      "int_scalar"),
        "num_cvs_v":  ("numV",      "int_scalar"),
        "num_u":      ("numU",      "int_scalar"),
        "num_v":      ("numV",      "int_scalar"),
        "degree_u":   ("degreeU",   "int_scalar"),
        "degree_v":   ("degreeV",   "int_scalar"),
        "periodic_u": ("periodicU", "bool_scalar"),
        "periodic_v": ("periodicV", "bool_scalar"),
        "kv_u":       ("knotsU",    "double_arr"),
        "kv_v":       ("knotsV",    "double_arr"),
        "knots_u":    ("knotsU",    "double_arr"),
        "knots_v":    ("knotsV",    "double_arr"),
    },
}
# Buffers that MUST be filled for a lowering to be accepted (others default:
# curve degree=3, surface degreeU/V=3 in the emitter). Tracked by BUFFER name
# so self.cvs and self.points both satisfy the "cvs" requirement.
_GEO_REQUIRED_BUFS = {
    "mesh":    ["points", "counts", "indices"],
    "curve":   ["cvs"],
    "surface": ["cvs", "numU", "numV"],
}


def _combined_helper_source(spec):
    """Helper source(s) for the transpiler: the node's INIT-tier ``def``s PLUS
    the source of every followed external helper unit
    (``spec['external_helper_units']``, produced by import_follower when the
    compute/init ``import``s pure-Python helpers from another module -- e.g. the
    metaballs node's ``from ...sdf_dmc import mesh_from_shapes``).

    A blessed ``Transpile`` method whose followed free fn calls its own sibling
    module-level helpers (e.g. ``twist_swing`` -> ``_twist_matrix`` /
    ``dual_quaternion`` in ``skin_blend.py``) also contributes that module's whole
    source, so those siblings resolve in the transpiler's helper pool
    (blessed_transpile.transpile_helper_sources; empty for a non-blessed type).

    Returns a LIST of source strings (followed units FIRST, the node-local INIT
    source LAST so a node-local ``def`` shadows an identically named followed
    helper), which ``py_to_cpp._parse_helpers`` parses independently and merges.
    Returns None when there is nothing to register -- byte-identical to the old
    ``spec.get('init')`` behaviour for a node with no init and no followed
    helpers, so non-metaballs lowerings are wholly unaffected."""
    parts = [u["source"] for u in (spec.get("external_helper_units") or [])
             if isinstance(u, dict) and u.get("source") and u["source"].strip()]
    parts += blessed_transpile.transpile_helper_sources(spec)
    init = spec.get("init")
    if init and init.strip():
        parts.append(init)
    return parts or None


def _is_scalar_numeric(meta):
    return (not meta.get("is_array")) and meta["type"] in _ND_DTYPE


def _is_numeric_array(meta):
    return bool(meta.get("is_array")) and meta["type"] in _ND_DTYPE


def _is_vector_scalar(meta):
    return (not meta.get("is_array")) and meta["type"] in _VEC_TYPES


def _is_vector_array(meta):
    return bool(meta.get("is_array")) and meta["type"] in _VEC_TYPES


def _is_color_scalar(meta):
    # A single (non-array) `color` compound (createColor: R/G/B float children).
    return (not meta.get("is_array")) and meta["type"] == "color"


def _is_color_array(meta):
    # A `color` multi -> std::vector<MFloatVector> (nd (N,3)).
    return bool(meta.get("is_array")) and meta["type"] == "color"


def _is_quaternion_scalar(meta):
    # A single `quaternion` compound (4 double children x/y/z/w) -> nd (4,).
    return (not meta.get("is_array")) and meta["type"] == "quaternion"


def _is_quaternion_array(meta):
    # A `quaternion` multi -> std::vector<MQuaternion> (nd (N,4)).
    return bool(meta.get("is_array")) and meta["type"] == "quaternion"


def _is_float2_scalar(meta):
    # A single `float2` compound (u/v) -> nd (2,).
    return (not meta.get("is_array")) and meta["type"] == "float2"


def _is_float2_array(meta):
    # A `float2` multi -> std::vector<std::array<float,2>> (nd (N,2)).
    return bool(meta.get("is_array")) and meta["type"] == "float2"


def _is_matrix_scalar(meta):
    return (not meta.get("is_array")) and meta["type"] == "matrix"


def _is_matrix_array(meta):
    return bool(meta.get("is_array")) and meta["type"] == "matrix"


def _is_string_scalar(meta):
    # A single (non-array) `string` or `hex` attr -> a std::string carrier. `hex`
    # rides string: emit_attr._read_line already decodes the stored hex to plain
    # text in in_<m> (an MString), and _string_scalar_output_lines re-encodes on
    # write.
    return (not meta.get("is_array")) and meta["type"] in ("string", "hex")


def _is_string_array(meta):
    # A `string`/`hex` multi -> the transpiler's `strv` carrier
    # (std::vector<std::string>), which supports len() and positional indexing.
    # The element read is already decoded by emit_attr._elem_read_expr, so `hex`
    # rides string here exactly as it does for the scalar.
    return bool(meta.get("is_array")) and meta["type"] in ("string", "hex")


# ---- input materialisation: Maya local -> nd:: value bound under `dst` -----
def _materialise_input(m, dst):
    """Emit C++ (indent-1) binding ``in_<member>`` to nd local ``dst``.

    Returns (lines, CppType) or raises UnsupportedSpec for an unhandled type.
    """
    meta = m["meta"]
    t = meta["type"]
    src = "in_" + m["member"]

    if _is_scalar_numeric(meta):
        dt = _ND_DTYPE[t]
        c = _ND_CTYPE[dt]
        return (["    %s %s = (%s)(%s);" % (c, dst, c, src)], scalar_t(dt))

    if _is_vector_scalar(meta):
        # double3 -> nd (3,) float array.
        return (["    nd::Array<double> %s = nd::from_data<double>("
                 "{%s[0], %s[1], %s[2]}, {3});" % (dst, src, src, src)],
                array_t("double", 1))

    if _is_numeric_array(meta):
        dt = _ND_DTYPE[t]
        c = _ND_CTYPE[dt]
        if _MAYA_CTYPE[t] == c:                      # same element type: direct
            return (["    nd::Array<%s> %s = nd::from_data<%s>("
                     "%s, {(int64_t)%s.size()});" % (c, dst, c, src, src)],
                    array_t(dt, 1))
        # differing element type: convert through a typed temp.
        return ([
            "    nd::Array<%s> %s;" % (c, dst),
            "    {",
            "        std::vector<%s> _tmp(%s.begin(), %s.end());" % (c, src, src),
            "        %s = nd::from_data<%s>(_tmp, {(int64_t)_tmp.size()});"
            % (dst, c),
            "    }",
        ], array_t(dt, 1))

    if _is_vector_array(meta):
        # std::vector<MVector> -> nd (N,3) float array (matches the dense (N,3)
        # numpy seeding the interpreted compute sees).
        return ([
            "    nd::Array<double> %s;" % dst,
            "    {",
            "        std::vector<double> _tmp; _tmp.reserve(%s.size() * 3);" % src,
            "        for (size_t _i = 0; _i < %s.size(); ++_i) {" % src,
            "            _tmp.push_back(%s[_i].x);" % src,
            "            _tmp.push_back(%s[_i].y);" % src,
            "            _tmp.push_back(%s[_i].z);" % src,
            "        }",
            "        %s = nd::from_data<double>(_tmp, {(int64_t)%s.size(), 3});"
            % (dst, src),
            "    }",
        ], array_t("double", 2))

    if _is_color_scalar(meta):
        # float3 color compound (asFloat3 -> in_<m>[0..2]) -> nd (3,) double.
        # Mirrors the vector-scalar binding; the color OUTPUT writer already
        # exists (_color_scalar_output_lines).
        return (["    nd::Array<double> %s = nd::from_data<double>("
                 "{(double)%s[0], (double)%s[1], (double)%s[2]}, {3});"
                 % (dst, src, src, src)],
                array_t("double", 1))

    if _is_color_array(meta):
        # std::vector<MFloatVector> -> nd (N,3) double (mirrors vector-array).
        return ([
            "    nd::Array<double> %s;" % dst,
            "    {",
            "        std::vector<double> _tmp; _tmp.reserve(%s.size() * 3);" % src,
            "        for (size_t _i = 0; _i < %s.size(); ++_i) {" % src,
            "            _tmp.push_back((double)%s[_i].x);" % src,
            "            _tmp.push_back((double)%s[_i].y);" % src,
            "            _tmp.push_back((double)%s[_i].z);" % src,
            "        }",
            "        %s = nd::from_data<double>(_tmp, {(int64_t)%s.size(), 3});"
            % (dst, src),
            "    }",
        ], array_t("double", 2))

    if _is_quaternion_scalar(meta):
        # double in_<m>[4] {x,y,z,w} (read via the 4 compound child handles) ->
        # nd (4,) double.
        return (["    nd::Array<double> %s = nd::from_data<double>("
                 "{%s[0], %s[1], %s[2], %s[3]}, {4});"
                 % (dst, src, src, src, src)],
                array_t("double", 1))

    if _is_quaternion_array(meta):
        # std::vector<MQuaternion> -> nd (N,4) double.
        return ([
            "    nd::Array<double> %s;" % dst,
            "    {",
            "        std::vector<double> _tmp; _tmp.reserve(%s.size() * 4);" % src,
            "        for (size_t _i = 0; _i < %s.size(); ++_i) {" % src,
            "            _tmp.push_back(%s[_i].x);" % src,
            "            _tmp.push_back(%s[_i].y);" % src,
            "            _tmp.push_back(%s[_i].z);" % src,
            "            _tmp.push_back(%s[_i].w);" % src,
            "        }",
            "        %s = nd::from_data<double>(_tmp, {(int64_t)%s.size(), 4});"
            % (dst, src),
            "    }",
        ], array_t("double", 2))

    if _is_float2_scalar(meta):
        # float2 compound (asFloat2 -> in_<m>[0..1]) -> nd (2,) double.
        return (["    nd::Array<double> %s = nd::from_data<double>("
                 "{(double)%s[0], (double)%s[1]}, {2});" % (dst, src, src)],
                array_t("double", 1))

    if _is_float2_array(meta):
        # std::vector<MFloatVector> (float2 carrier; u=.x, v=.y) -> nd (N,2)
        # double (mirrors vector/color-array; float2 has 2 components).
        return ([
            "    nd::Array<double> %s;" % dst,
            "    {",
            "        std::vector<double> _tmp; _tmp.reserve(%s.size() * 2);" % src,
            "        for (size_t _i = 0; _i < %s.size(); ++_i) {" % src,
            "            _tmp.push_back((double)%s[_i].x);" % src,
            "            _tmp.push_back((double)%s[_i].y);" % src,
            "        }",
            "        %s = nd::from_data<double>(_tmp, {(int64_t)%s.size(), 2});"
            % (dst, src),
            "    }",
        ], array_t("double", 2))

    if _is_matrix_scalar(meta):
        # MMatrix -> nd (4,4) row-major. numpy M[i,j] == MMatrix m(i,j) (Maya
        # row-vector convention; translate in row 3), matching the interpreted
        # node's as_numpy() and the transform matrix-input binding.
        elems = ", ".join("%s(%d, %d)" % (src, r, c)
                          for r in range(4) for c in range(4))
        return (["    nd::Array<double> %s = nd::from_data<double>("
                 "{%s}, {4, 4});" % (dst, elems)],
                array_t("double", 2))

    if _is_matrix_array(meta):
        # std::vector<MMatrix> -> nd (N,4,4) row-major (matches the dense (N,4,4)
        # numpy the interpreted geo compute reads via self.<matrixArray>).
        return ([
            "    nd::Array<double> %s;" % dst,
            "    {",
            "        std::vector<double> _tmp; _tmp.reserve(%s.size() * 16);" % src,
            "        for (size_t _i = 0; _i < %s.size(); ++_i) {" % src,
            "            for (int _r = 0; _r < 4; ++_r)",
            "                for (int _c = 0; _c < 4; ++_c)",
            "                    _tmp.push_back(%s[_i](_r, _c));" % src,
            "        }",
            "        %s = nd::from_data<double>(_tmp, {(int64_t)%s.size(), 4, 4});"
            % (dst, src),
            "    }",
        ], array_t("double", 3))

    if _is_string_scalar(meta):
        # string/hex INPUT: in_<m> is an MString (hex already decoded to plain
        # text by emit_attr._read_line). Bind to a std::string for the transpiler's
        # str kind (pass-through / concat / equality). .asChar() is a const char*.
        return (["    std::string %s = %s.asChar();" % (dst, src)], str_t())

    if _is_string_array(meta):
        # string/hex MULTI: in_<m> is a std::vector<MString> (dense, gap slots
        # already filled by the array read loop). Copy to the std::vector
        # <std::string> the `strv` kind carries -- one conversion up front rather
        # than an .asChar() at every index, and it keeps the carrier type the
        # same one list(<str>) already produces.
        return ([
            "    std::vector<std::string> %s;" % dst,
            "    %s.reserve(%s.size());" % (dst, src),
            "    for (size_t _si = 0; _si < %s.size(); ++_si) {" % src,
            "        %s.push_back(%s[_si].asChar());" % (dst, src),
            "    }",
        ], strv_t())

    raise UnsupportedSpec("nd_lower: input %r type %r not liftable"
                          % (m["plug"], t))


# ---- output writers: nd:: Val -> codegen sink (h_<member> / out_<member>) --
def _scalar_expr(val):
    """A C++ scalar expression from a produced Val (scalar or 0-d array)."""
    if val.type.kind == "scalar":
        return val.code
    if val.type.kind == "array" and val.type.rank in (0, None):
        return "(%s).item()" % val.code
    raise UnsupportedSpec("nd_lower: array value assigned to a scalar output")


# Maya handle setter for a scalar output; %s pairs are (member/expr).
def _scalar_output_lines(m, val):
    t = m["meta"]["type"]
    h = "h_" + m["member"]
    e = _scalar_expr(val)
    if t == "float":
        return ["%s.setFloat((float)(%s));" % (h, e)]
    if t == "double":
        return ["%s.setDouble((double)(%s));" % (h, e)]
    if t == "int":
        return ["%s.setInt((int)(%s));" % (h, e)]
    if t == "bool":
        return ["%s.setBool((bool)(%s));" % (h, e)]
    if t == "enum":
        return ["%s.setShort((short)(%s));" % (h, e)]
    if t == "angle":
        return ["%s.setMAngle(MAngle((double)(%s)));" % (h, e)]
    if t == "time":
        return ["%s.setMTime(MTime((double)(%s)));" % (h, e)]
    raise UnsupportedSpec("nd_lower: output %r type %r not liftable"
                          % (m["plug"], t))


def _vector_scalar_output_lines(m, val):
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: non-array value assigned to vector "
                              "output %r" % m["plug"])
    h = "h_" + m["member"]
    # Length-guarded (see _color_scalar_output_lines): a pack that is not exactly
    # 3-wide never reads out of bounds now that tuple literals lower (a 2-tuple
    # fills X/Y and leaves Z=0; extras ignored). Numeric parity for well-formed
    # 3-vectors is unchanged. _cast_array to double so an integral/bool pack (e.g.
    # ``self.outNormal = (0, 0, 1)``, which lowers to nd::Array<int64_t>) does not
    # emit ``nd::Array<double> = nd::Array<int64_t>`` (no viable conversion ->
    # non-compiling C++); a double value is passed through unchanged.
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.size();",
        "    double _d[3] = {0.0, 0.0, 0.0};",
        "    for (int64_t _i = 0; _i < _n && _i < 3; ++_i)",
        "        _d[_i] = (*_o.data)[_i];",
        "    %s.set3Double(_d[0], _d[1], _d[2]);" % h,
        "}",
    ]


def _color_scalar_output_lines(m, val):
    """A single ``color`` output (e.g. outColor): an nd (3,) value ->
    ``h_<m>.set3Float`` (float R/G/B). Mirrors _vector_scalar_output_lines but
    writes the FLOAT children Maya's createColor compound exposes (matching
    emit_attr._OUT_DEFAULT["color"] set3Float and the full-parity glue). The
    value length is guarded so a pack that is not exactly 3-wide never reads out
    of bounds (missing channels default to 0, extras ignored)."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: non-array value assigned to color "
                              "output %r" % m["plug"])
    h = "h_" + m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.size();",
        "    float _c[3] = {0.0f, 0.0f, 0.0f};",
        "    for (int64_t _i = 0; _i < _n && _i < 3; ++_i)",
        "        _c[_i] = (float)(*_o.data)[_i];",
        "    %s.set3Float(_c[0], _c[1], _c[2]);" % h,
        "}",
    ]


def _color_array_output_lines(m, val):
    """A ``color`` ARRAY output: an nd (N,3) value -> ``std::vector<MFloatVector>
    out_<m>`` (flushed to the multi plug by emit_attr._array_write_lines, whose
    color element setter reads .x/.y/.z)."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: scalar value assigned to color-array "
                              "output %r" % m["plug"])
    out = "out_" + m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.shape.empty() ? 0 : _o.shape[0];",
        "    %s.resize((size_t)_n);" % out,
        "    for (int64_t _i = 0; _i < _n; ++_i)",
        "        %s[(size_t)_i] = MFloatVector((float)(*_o.data)[_i*3+0], "
        "(float)(*_o.data)[_i*3+1], (float)(*_o.data)[_i*3+2]);" % out,
        "}",
    ]


def _quaternion_scalar_output_lines(m, val):
    """A single ``quaternion`` output: an nd (4,) value -> the 4 compound child
    handles (x/y/z/w) of ``h_<m>`` (there is no numeric set4Double; mirrors
    emit_attr._out_handle_default's child-handle seed). Missing components default
    to identity [0,0,0,1]; the value length is guarded so a shorter/longer pack
    never reads out of bounds."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: non-array value assigned to quaternion "
                              "output %r" % m["plug"])
    h = "h_" + m["member"]
    mem = m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.size();",
        "    double _q[4] = {0.0, 0.0, 0.0, 1.0};",
        "    for (int64_t _i = 0; _i < _n && _i < 4; ++_i)",
        "        _q[_i] = (*_o.data)[_i];",
        "    MFnCompoundAttribute _qf(%s);" % mem,
        "    %s.child(_qf.child(0)).setDouble(_q[0]);" % h,
        "    %s.child(_qf.child(1)).setDouble(_q[1]);" % h,
        "    %s.child(_qf.child(2)).setDouble(_q[2]);" % h,
        "    %s.child(_qf.child(3)).setDouble(_q[3]);" % h,
        "}",
    ]


def _quaternion_array_output_lines(m, val):
    """A ``quaternion`` ARRAY output: an nd (N,4) value -> ``std::vector<MQuaternion>
    out_<m>`` (flushed by emit_attr._array_write_lines, whose quaternion element
    setter writes .x/.y/.z/.w via the compound children)."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: scalar value assigned to quaternion-array "
                              "output %r" % m["plug"])
    out = "out_" + m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.shape.empty() ? 0 : _o.shape[0];",
        "    %s.resize((size_t)_n);" % out,
        "    for (int64_t _i = 0; _i < _n; ++_i)",
        "        %s[(size_t)_i] = MQuaternion((*_o.data)[_i*4+0], "
        "(*_o.data)[_i*4+1], (*_o.data)[_i*4+2], (*_o.data)[_i*4+3]);" % out,
        "}",
    ]


def _float2_scalar_output_lines(m, val):
    """A single ``float2`` output: an nd (2,) value -> ``h_<m>.set2Float`` (float
    u/v). Length-guarded so a non-2-wide pack never reads out of bounds."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: non-array value assigned to float2 "
                              "output %r" % m["plug"])
    h = "h_" + m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.size();",
        "    float _f[2] = {0.0f, 0.0f};",
        "    for (int64_t _i = 0; _i < _n && _i < 2; ++_i)",
        "        _f[_i] = (float)(*_o.data)[_i];",
        "    %s.set2Float(_f[0], _f[1]);" % h,
        "}",
    ]


def _float2_array_output_lines(m, val):
    """A ``float2`` ARRAY output: an nd (N,2) value -> ``std::vector<MFloatVector>
    out_<m>`` (float2 carrier; u=.x, v=.y, .z=0). Flushed by
    emit_attr._array_write_lines whose float2 element setter calls set2Float."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: scalar value assigned to float2-array "
                              "output %r" % m["plug"])
    out = "out_" + m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.shape.empty() ? 0 : _o.shape[0];",
        "    %s.resize((size_t)_n);" % out,
        "    for (int64_t _i = 0; _i < _n; ++_i)",
        "        %s[(size_t)_i] = MFloatVector((float)(*_o.data)[_i*2+0], "
        "(float)(*_o.data)[_i*2+1], 0.0f);" % out,
        "}",
    ]


def _numeric_array_output_lines(m, val):
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: scalar value assigned to array output "
                              "%r" % m["plug"])
    t = m["meta"]["type"]
    dt = _ND_DTYPE[t]
    ndc = _ND_CTYPE[dt]
    mc = _MAYA_CTYPE[t]
    out = "out_" + m["member"]
    return [
        "{",
        "    nd::Array<%s> _o = (%s);" % (ndc, _cast_array(val, dt)),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    %s.resize((size_t)_o.size());" % out,
        "    for (size_t _i = 0; _i < (size_t)_o.size(); ++_i)",
        "        %s[_i] = (%s)(*_o.data)[_i];" % (out, mc),
        "}",
    ]


def _vector_array_output_lines(m, val):
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: scalar value assigned to vector-array "
                              "output %r" % m["plug"])
    out = "out_" + m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.shape.empty() ? 0 : _o.shape[0];",
        "    %s.resize((size_t)_n);" % out,
        "    for (int64_t _i = 0; _i < _n; ++_i)",
        "        %s[(size_t)_i] = MVector((*_o.data)[_i*3+0], "
        "(*_o.data)[_i*3+1], (*_o.data)[_i*3+2]);" % out,
        "}",
    ]


def _matrix_scalar_output_lines(m, val):
    """A single ``matrix`` output: an nd (4,4) value -> ``h_<m>.setMMatrix``.
    The nd matrix is Maya-layout row-vector (same convention as MMatrix), stored
    row-major, so element (r,c) is ``data[r*4+c]``."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: non-array value assigned to matrix "
                              "output %r" % m["plug"])
    h = "h_" + m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    MMatrix _m;",
        "    for (int _r = 0; _r < 4; ++_r) for (int _c = 0; _c < 4; ++_c)",
        "        _m(_r, _c) = (*_o.data)[_r * 4 + _c];",
        "    %s.setMMatrix(_m);" % h,
        "}",
    ]


def _matrix_array_output_lines(m, val):
    """A ``matrix`` ARRAY output: an nd (N,4,4) value -> ``std::vector<MMatrix>
    out_<m>`` (flushed to the multi plug by emit_attr._array_write_lines)."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower: scalar value assigned to matrix-array "
                              "output %r" % m["plug"])
    out = "out_" + m["member"]
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.shape.empty() ? 0 : _o.shape[0];",
        "    %s.resize((size_t)_n);" % out,
        "    for (int64_t _i = 0; _i < _n; ++_i) {",
        "        MMatrix _m;",
        "        for (int _r = 0; _r < 4; ++_r) for (int _c = 0; _c < 4; ++_c)",
        "            _m(_r, _c) = (*_o.data)[_i * 16 + _r * 4 + _c];",
        "        %s[(size_t)_i] = _m;" % out,
        "    }",
        "}",
    ]


def _cast_array(val, dt):
    """A C++ expr yielding an nd::Array<_ND_CTYPE[dt]> from a Val (astype if the
    produced dtype differs)."""
    if val.type.dtype == dt:
        return val.code
    return "nd::astype<%s>(%s)" % (_ND_CTYPE[dt], val.code)


def _string_scalar_output_lines(m, val):
    """A single ``string``/``hex`` output: a std::string carrier Val ->
    ``h_<m>.setString(...)``. hex re-encodes the plain text to space-separated
    hex on write (the deterministic finalize is a plain setClean -- unlike the AI
    PORT path, there is no separate hex-encode finalize, so the writer encodes)."""
    if val.type.kind != "str":
        raise UnsupportedSpec("nd_lower: non-string value assigned to string "
                              "output %r" % m["plug"])
    h = "h_" + m["member"]
    expr = "MString((%s).c_str())" % val.code
    if m["meta"]["type"] == "hex":
        return ["%s.setString(nd_hex_encode(%s));" % (h, expr)]
    return ["%s.setString(%s);" % (h, expr)]


def _output_writer(m):
    """Return a callable(Val) -> list[str] writing m's output, or raise."""
    meta = m["meta"]
    if _is_scalar_numeric(meta):
        return lambda val: _scalar_output_lines(m, val)
    if _is_vector_scalar(meta):
        return lambda val: _vector_scalar_output_lines(m, val)
    if _is_color_scalar(meta):
        return lambda val: _color_scalar_output_lines(m, val)
    if _is_color_array(meta):
        return lambda val: _color_array_output_lines(m, val)
    if _is_quaternion_scalar(meta):
        return lambda val: _quaternion_scalar_output_lines(m, val)
    if _is_quaternion_array(meta):
        return lambda val: _quaternion_array_output_lines(m, val)
    if _is_float2_scalar(meta):
        return lambda val: _float2_scalar_output_lines(m, val)
    if _is_float2_array(meta):
        return lambda val: _float2_array_output_lines(m, val)
    if _is_numeric_array(meta):
        return lambda val: _numeric_array_output_lines(m, val)
    if _is_vector_array(meta):
        return lambda val: _vector_array_output_lines(m, val)
    if _is_matrix_scalar(meta):
        return lambda val: _matrix_scalar_output_lines(m, val)
    if _is_matrix_array(meta):
        return lambda val: _matrix_array_output_lines(m, val)
    if _is_string_scalar(meta):
        return lambda val: _string_scalar_output_lines(m, val)
    raise UnsupportedSpec("nd_lower: output %r type %r not liftable"
                          % (m["plug"], meta["type"]))


# ---- public entry ----------------------------------------------------------
def _used_self_attrs(source, declared=None):
    """Set of attr names read/written as ``self.<attr>`` in the source.

    ``declared`` opts into the STRING-NAMED forms ``getattr(self, "<attr>",
    default)`` and ``hasattr(self, "<attr>")``, which name an attribute just as
    much as a dot access does. An attr missed here is never materialised into
    the transpiler env, and ``getattr`` would then silently fold to its default
    even though the node declares the plug -- it compiles clean and draws the
    wrong thing.

    Only names IN ``declared`` are added: ``getattr(self, "notThere", 0.25)``
    is the legitimate "this node has no such plug" case and must stay
    unmentioned so it folds to the default instead of failing the allowlist.
    With ``declared`` None the result is exactly the dot-access set, so the
    callers that have not opted in are unchanged."""
    used = set()
    for n in ast.walk(ast.parse(source)):
        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "self"):
            used.add(n.attr)
        elif (declared and isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in ("getattr", "hasattr")
                and len(n.args) >= 2
                and isinstance(n.args[0], ast.Name) and n.args[0].id == "self"
                and isinstance(n.args[1], ast.Constant)
                and isinstance(n.args[1].value, str)
                and n.args[1].value in declared):
            used.add(n.args[1].value)
    return used


def _persistent_state_vars(source, declared):
    """Names WHOLE-assigned as ``self.<name> = ...`` AND read that are NOT
    declared IO.

    These are persistent stateful self-vars -- a latched rest length, a solver
    carry-over, a simulation buffer -- that an interpreted node writes once (or
    each eval) and expects to SURVIVE between compute() calls. A compiled
    MPxNode::compute() is stateless per-eval, so codegen must give them a per-node
    home (see ``_state_registry_preamble``); otherwise the AI porter tends to
    silently FLATTEN them (spine's stretch went inert, dnet cold-started).

    A var qualifies only when it is BOTH whole-assigned (the first write fixes
    its C++ member type) AND read somewhere -- a value that is written but never
    read is a dead store / typo'd output, left to reject on the normal path
    rather than silently absorbed as harmless state. A read that has no
    preceding write is an orphan (its value comes from outside the node) and is
    rejected downstream (py_to_cpp / _unbound_self_reads)."""
    declared = set(declared)
    tree = ast.parse(source)
    written, read = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            targets = n.targets
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            targets = [n.target]
        else:
            targets = ()
        for t in targets:
            if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                    and t.value.id == "self" and t.attr not in declared):
                written.add(t.attr)
        # a Load-context self.<attr> is a READ (an aug-assign target is both, so
        # it is captured by the write scan above and the Load walk below).
        if (isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load)
                and isinstance(n.value, ast.Name) and n.value.id == "self"
                and n.attr not in declared):
            read.add(n.attr)
    return written & read


def _state_member_ctype(t):
    """C++ declaration type for a persistent-state member's CppType."""
    if t.kind == "array":
        return "nd::Array<%s>" % _ND_CTYPE[t.dtype]
    if t.kind == "scalar":
        return _ND_CTYPE[t.dtype]
    raise UnsupportedSpec("nd_lower: persistent state of kind %r not supported"
                          % t.kind)


def _state_member_decls(state_members):
    """C++ CLASS-BODY lines declaring the persistent state as PER-INSTANCE members.

    The state lives IN the node object: constructed with it, destroyed with it,
    at an address that is stable for its whole life. Each member ``X`` is paired
    with ``X_isset`` (false until first written) so that ``hasattr(self,'X')``
    lowers to a genuine first-run test, and every member carries a default
    initialiser -- the node's ``<cls>() {}`` ctor names none of them, so without
    one the POD members would be INDETERMINATE on the first eval.

    This replaces a function-static ``std::vector<_NdState>`` keyed on
    ``(const void*)this``, which was three defects at once: (1) the
    ``&_nd_states.back()`` it handed out DANGLES the moment another instance's
    compute() push_back()s and reallocates -- Maya's parallel EM evaluates nodes
    concurrently, and the vector had no mutex either; (2) nothing ever evicted a
    record, so the registry grew for the life of the session; and (3) a NEW node
    allocated at a deleted node's address inherited that node's state -- measured
    2 of 8 fresh nodes starting at 301.0 instead of 1.0, because ``acc_isset``
    was already true so the first-run seed was skipped. A per-instance member has
    none of the three by construction.

    ``state_members`` is ``name -> CppType`` as discovered by the transpiler."""
    if not state_members:
        return []
    raw = ["// --- persistent per-instance state (latched across compute calls) ---",
           "struct _NdState {"]
    for nm in sorted(state_members):
        raw.append("    bool %s_isset = false;" % nm)
        raw.append("    %s %s {};" % (_state_member_ctype(state_members[nm]), nm))
    raw += ["};",
            "_NdState _ndState;",
            "std::mutex _ndStateMutex;"]
    return ["    " + ln for ln in raw]      # indent-1, matching the other members


def _state_binding_preamble(state_members):
    """C++ compute-body preamble exposing the per-instance state as ``_NdState& st``.

    The mutex is per INSTANCE, so it never serialises two different nodes -- it
    only orders two concurrent compute() calls on the SAME node (parallel EM,
    cached-playback background evaluation, a plug pull off the main thread),
    where an unguarded ``st.<x> = nd::add(st.<x>, ...)`` would race on the
    Array's shared buffer and shape vectors. Taken inside the lowered body's
    try-block, so it also releases on the exception path."""
    if not state_members:
        return []
    raw = ["// --- persistent per-instance state (see the _NdState member) ---",
           "std::lock_guard<std::mutex> _ndStateLock(_ndStateMutex);",
           "_NdState& st = _ndState;"]
    return ["    " + ln for ln in raw]      # indent-1, matching materialise lines


def _output_subscript_targets(source, out_plugs):
    """Classify how each declared output is ASSIGNED in the compute.

    Returns ``(subscript_written, whole_written)`` sets of output plug names:
      * ``whole_written``    -- ``self.<out> = expr`` (the existing writer path);
      * ``subscript_written``-- ``self.<out>[...] = ...`` (in-place indexed write,
        e.g. spline's ``self.samples[i] = acc`` inside a loop bounded by
        ``len(self.samples)``). AugAssign targets count the same way.
    A node whose output is written by index needs that output bound as a PRE-SIZED
    buffer (see _materialise_output_buffer) so ``len``/indexing/writes have real
    elements; a whole-assign output keeps the write-on-assignment writer path, so
    whole-array writers (sine_ripple / metaballs) are completely unaffected."""
    subscript, whole = set(), set()

    def _attr_plug(node):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "self" and node.attr in out_plugs):
            return node.attr
        return None

    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Assign):
            targets = n.targets
        elif isinstance(n, ast.AugAssign):
            targets = [n.target]
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Subscript):
                p = _attr_plug(t.value)
                if p is not None:
                    subscript.add(p)
            else:
                p = _attr_plug(t)
                if p is not None:
                    whole.add(p)
    return subscript, whole


def _materialise_output_buffer(m, dst):
    """Pre-size an nd:: buffer for an ARRAY output WRITTEN BY INDEX.

    The buffer is sized to the output multi's connected element count -- exactly
    what the interpreted node seeds (``output_defaults.seed_user_output_defaults_
    api2`` sizes ``self.<out>`` to ``max connected out-index + 1``). The compute
    then reads ``len(self.<out>)`` / indexes it and writes elements in place;
    ``lower_compute`` flushes the buffer to ``out_<member>`` after the body via
    the SAME writer the whole-assign path uses. ``data.outputArrayValue(<member>)
    .elementCount()`` is the compiled analogue of the connected-index span (the
    AI porter reads the identical count for this node class).

    Returns ``(lines, CppType)`` or raises for an unliftable output type."""
    meta = m["meta"]
    t = meta["type"]
    member = m["member"]
    ncount = "_ndoutn_" + member
    count = ("    int64_t %s = (int64_t)data.outputArrayValue(%s).elementCount();"
             % (ncount, member))
    if _is_vector_array(meta):
        return ([count,
                 "    nd::Array<double> %s = nd::zeros<double>({%s, 3});"
                 % (dst, ncount)],
                array_t("double", 2))
    if _is_numeric_array(meta):
        dt = _ND_DTYPE[t]
        c = _ND_CTYPE[dt]
        return ([count,
                 "    nd::Array<%s> %s = nd::zeros<%s>({%s});"
                 % (c, dst, c, ncount)],
                array_t(dt, 1))
    raise UnsupportedSpec("nd_lower: output buffer for %r type %r not liftable"
                          % (m["plug"], t))


# MFn type constant per geo kind, for the null/type guard on the input DATA.
_GEO_FN_CONST = {"mesh": "kMesh", "curve": "kNurbsCurve", "surface": "kNurbsSurface"}


def _geo_vec3_lines(dst, guard, fill, count):
    """(N,3) double nd::Array from an (x,y,z)-yielding Maya array. ``fill`` is the
    guarded call populating a local ``_ga`` array; ``count`` is ``_ga.length()``."""
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
    ] + fill + [
        "        std::vector<double> _gt; _gt.reserve((size_t)%s * 3);" % count,
        "        for (unsigned int _gi = 0; _gi < %s; ++_gi) {" % count,
        "            _gt.push_back(_ga[_gi].x); _gt.push_back(_ga[_gi].y); "
        "_gt.push_back(_ga[_gi].z);",
        "        }",
        "        %s = nd::from_data<double>(_gt, {(int64_t)%s, 3});" % (dst, count),
        "    }",
    ]


def _geo_int1_lines(dst, guard, fill, arrname, count):
    """(K,) int64 nd::Array from an MIntArray ``arrname`` populated by ``fill``."""
    return [
        "    nd::Array<int64_t> %s;" % dst,
        "    {",
    ] + fill + [
        "        std::vector<int64_t> _gt((size_t)%s);" % count,
        "        for (unsigned int _gi = 0; _gi < %s; ++_gi) _gt[_gi] = "
        "(int64_t)%s[_gi];" % (count, arrname),
        "        %s = nd::from_data<int64_t>(_gt, {(int64_t)%s});" % (dst, count),
        "    }",
    ]


def _geo_dbl1_lines(dst, fill, arrname, count):
    """(K,) double nd::Array from an MDoubleArray ``arrname`` populated by ``fill``."""
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
    ] + fill + [
        "        std::vector<double> _gt((size_t)%s);" % count,
        "        for (unsigned int _gi = 0; _gi < %s; ++_gi) _gt[_gi] = "
        "%s[_gi];" % (count, arrname),
        "        %s = nd::from_data<double>(_gt, {(int64_t)%s});" % (dst, count),
        "    }",
    ]


def _geo_uv_lines(src, guard, dst):
    """(M,2) double nd::Array of the FIRST non-empty UV set's (u,v) points, read
    from MFnMesh ``src`` -- matches the interpreted Mesh.uvs (uv_sets[0].points,
    empty sets skipped). ``guard`` is the ``!obj.isNull() && obj.hasFn(kMesh)``
    check; an absent/empty mesh yields an empty (0,2) array (parity with interp)."""
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _uv; int64_t _m = 0;",
        "        if (%s) {" % guard,
        "            MStringArray _sn; %s.getUVSetNames(_sn);" % src,
        "            for (unsigned int _si = 0; _si < _sn.length(); ++_si) {",
        "                MString _setn = _sn[_si];",
        "                MFloatArray _ua, _va; %s.getUVs(_ua, _va, &_setn);" % src,
        "                if (_ua.length() == 0) continue;",
        "                _m = (int64_t)_ua.length();",
        "                _uv.reserve((size_t)_m * 2);",
        "                for (unsigned int _ui = 0; _ui < _ua.length(); ++_ui) {",
        "                    _uv.push_back((double)_ua[_ui]); "
        "_uv.push_back((double)_va[_ui]);",
        "                }",
        "                break;",
        "            }",
        "        }",
        "        %s = nd::from_data<double>(_uv, {_m, 2});" % dst,
        "    }",
    ]


def _cpp_str(s):
    """A C++ double-quoted string literal for ``s`` (component-tag NAME)."""
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')


# component-tag decode headers -- added to a node's TU only when it reads a tag
# (see node_scaffold._spec_reads_component_tag) so every other geo node's frag
# stays byte-identical (port cache intact).
GEO_TAG_INCLUDES = ("maya/MFnGeometryData.h", "maya/MFnSingleIndexedComponent.h",
                    "maya/MFnDoubleIndexedComponent.h", "maya/MIntArray.h",
                    "maya/MFn.h")

# UV read-surface headers (MFnMesh::getUVSetNames + getUVs) -- added to a node's
# TU only when it reads mesh ``.uvs`` (see node_scaffold._spec_reads_uv), so every
# other geo node's frag stays byte-identical (port cache intact).
GEO_UV_INCLUDES = ("maya/MStringArray.h", "maya/MFloatArray.h")


def _materialise_geo_tag(member, kind, spec, dst):
    """Emit C++ (indent-1) binding a component-tag read to nd local ``dst``,
    decoded off the geo-input DATA MObject ``in_<member>_obj`` via
    ``MFnGeometryData::componentTagContents`` -- the SAME decode the interpreted
    ``geometry.py`` ``region`` / ``component_tags`` use (single-indexed for mesh/
    curve, double-indexed ``(u, v)`` for a surface). ``spec`` is
    ``("region", tag)`` (gather points/CVs -> ``(K, 3)`` double) or
    ``("tagidx", tag)`` (raw indices -> ``(K,)`` int64 mesh/curve, ``(K, 2)``
    int64 surface). Returns (lines, CppType)."""
    op, tag = spec
    if op == "tagclusters":
        return _materialise_geo_tag_clusters(member, kind, tag, dst)
    src = "in_" + member
    obj = src + "_obj"
    tagc = _cpp_str(tag)
    fn = _GEO_FN_CONST[kind]
    guard = "!%s.isNull() && %s.hasFn(MFn::%s)" % (obj, obj, fn)
    # C++ that decodes the tag component into a flat MIntArray _tel (single) or a
    # pair _tu/_tv (double), inside a `if (tag present) { ... }` block.
    open_ = [
        "    {",
        "        %s _tg(%s);" % ("MFnGeometryData", obj),
        "        if (%s && _tg.hasComponentTag(%s)) {" % (guard, tagc),
        "            MObject _tc = _tg.componentTagContents(%s);" % tagc,
        "            if (!_tc.isNull() && _tc.hasFn(MFn::kComponent)) {",
    ]
    close_ = ["            }", "        }", "    }"]

    if kind == "surface":
        decode = [
            "                MFnDoubleIndexedComponent _tdi(_tc);",
            "                MIntArray _tu, _tv; _tdi.getElements(_tu, _tv);",
        ]
    else:
        decode = [
            "                MFnSingleIndexedComponent _tsi(_tc);",
            "                MIntArray _tel; _tsi.getElements(_tel);",
        ]

    if op == "region":
        # gather point/CV positions by the decoded indices (matches the
        # interpreted ``region`` points-gather for a vertex/cv tag).
        if kind == "mesh":
            # Object-space positions straight off the mesh's internal float
            # array (the same read nd_read_mesh uses): Maya stores vertices as
            # float3, so getPoints(kObject) is that array widened to double --
            # reading it raw is bit-identical and skips the MPointArray copy.
            read_pts = ["                const float* _tp = "
                        "in_%s.getRawPoints(NULL);" % member,
                        "                int _tpn = (_tp == 0) ? 0 : "
                        "in_%s.numVertices();" % member]
            npts = "_tpn"
            xyz = ("_tgt.push_back((double)_tp[3 * %(i)s]); "
                   "_tgt.push_back((double)_tp[3 * %(i)s + 1]); "
                   "_tgt.push_back((double)_tp[3 * %(i)s + 2]);")
        else:  # curve or surface CVs
            read_pts = ["                MPointArray _tp; "
                        "in_%s.getCVs(_tp, MSpace::kObject);" % member]
            npts = "(int)_tp.length()"
            xyz = ("_tgt.push_back(_tp[%(i)s].x); "
                   "_tgt.push_back(_tp[%(i)s].y); _tgt.push_back(_tp[%(i)s].z);")
        body = ["    nd::Array<double> %s;" % dst,
                "    std::vector<double> _tgt;"] + open_ + decode + read_pts
        if kind == "surface":
            body += [
                "                int _tnv = (int)in_%s.numCVsInV();" % member,
                "                for (unsigned int _ti = 0; _ti < _tu.length(); "
                "++_ti) {",
                "                    int _lin = _tu[_ti] * _tnv + _tv[_ti];",
                "                    if (_lin >= 0 && _lin < %s) {" % npts,
                "                        " + xyz % {"i": "_lin"},
                "                    }",
                "                }",
            ]
        else:
            body += [
                "                for (unsigned int _ti = 0; _ti < _tel.length(); "
                "++_ti) {",
                "                    int _tid = _tel[_ti];",
                "                    if (_tid >= 0 && _tid < %s) {" % npts,
                "                        " + xyz % {"i": "_tid"},
                "                    }",
                "                }",
            ]
        body += close_ + [
            "    %s = nd::from_data<double>(_tgt, "
            "{(int64_t)(_tgt.size() / 3), 3});" % dst]
        return body, array_t("double", 2)

    if op == "tagidx":
        if kind == "surface":
            body = ["    nd::Array<int64_t> %s;" % dst,
                    "    std::vector<int64_t> _tgt;"] + open_ + decode + [
                "                _tgt.reserve((size_t)_tu.length() * 2);",
                "                for (unsigned int _ti = 0; _ti < _tu.length(); "
                "++_ti) { _tgt.push_back((int64_t)_tu[_ti]); "
                "_tgt.push_back((int64_t)_tv[_ti]); }",
            ] + close_ + [
                "    %s = nd::from_data<int64_t>(_tgt, "
                "{(int64_t)(_tgt.size() / 2), 2});" % dst]
            return body, array_t("int64", 2)
        body = ["    nd::Array<int64_t> %s;" % dst,
                "    std::vector<int64_t> _tgt;"] + open_ + decode + [
            "                _tgt.resize((size_t)_tel.length());",
            "                for (unsigned int _ti = 0; _ti < _tel.length(); "
            "++_ti) _tgt[_ti] = (int64_t)_tel[_ti];",
        ] + close_ + [
            "    %s = nd::from_data<int64_t>(_tgt, {(int64_t)_tgt.size()});" % dst]
        return body, array_t("int64", 1)

    raise UnsupportedSpec("nd_lower: geo tag op %r not materialisable" % op)


def _materialise_geo_tag_clusters(member, kind, tags_member, dst):
    """Emit C++ (indent-1) binding ``self.<geo>.tag_clusters(self.<strArrayIn>)``
    to nd local ``dst``: one padded ``(N, L)`` int64 cluster array, ``-1`` fill.

    Unlike ``region`` / ``tagidx`` the tag NAMES are RUNTIME data -- they come
    from the multi-string input ``in_<tags_member>`` (a ``std::vector<MString>``
    the emitter already reads), not from a compile-time literal. Membership is
    decoded per name off the geo-input DATA MObject ``in_<member>_obj`` via
    ``MFnGeometryData::componentTagContents``, the SAME decode the interpreted
    ``Mesh.tag_clusters`` uses, and padded exactly like
    ``component_tags.pad_clusters`` (``L = max(maxlen, 1)``, row-major, ``-1``
    fill, empty names -> ``(0, 1)``). Returns (lines, CppType)."""
    if kind != "mesh":
        # ``tag_clusters`` is a Mesh-only wrapper method, so only a mesh input has
        # an interpreted counterpart to be at parity with; a curve/surface read
        # stays on the porter (a surface's double-indexed (u, v) components have
        # no padded-cluster shape either way).
        raise UnsupportedSpec(
            "nd_lower: tag_clusters is only supported on a mesh geo input "
            "(got %r)" % kind)
    obj = "in_%s_obj" % member
    names = "in_" + tags_member
    guard = "!%s.isNull() && %s.hasFn(MFn::%s)" % (obj, obj, _GEO_FN_CONST[kind])
    body = [
        "    nd::Array<int64_t> %s;" % dst,
        "    {",
        "        std::vector< std::vector<int64_t> > _tcr;",
        "        MFnGeometryData _tg(%s);" % obj,
        "        if (%s) {" % guard,
        "            for (size_t _tn = 0; _tn < %s.size(); ++_tn) {" % names,
        "                std::vector<int64_t> _trow;",
        "                if (_tg.hasComponentTag(%s[_tn])) {" % names,
        "                    MObject _tc = _tg.componentTagContents(%s[_tn]);"
        % names,
        "                    if (!_tc.isNull() && _tc.hasFn(MFn::kComponent)) {",
        "                        MFnSingleIndexedComponent _tsi(_tc);",
        "                        MIntArray _tel; _tsi.getElements(_tel);",
        "                        _trow.resize((size_t)_tel.length());",
        "                        for (unsigned int _ti = 0; _ti < _tel.length(); "
        "++_ti) _trow[_ti] = (int64_t)_tel[_ti];",
        "                    }",
        "                }",
        "                _tcr.push_back(_trow);",
        "            }",
        "        }",
        "        int64_t _tw = 1;",
        "        for (size_t _tn = 0; _tn < _tcr.size(); ++_tn)",
        "            if ((int64_t)_tcr[_tn].size() > _tw) "
        "_tw = (int64_t)_tcr[_tn].size();",
        "        std::vector<int64_t> _tgt("
        "(size_t)((int64_t)_tcr.size() * _tw), (int64_t)-1);",
        "        for (size_t _tn = 0; _tn < _tcr.size(); ++_tn)",
        "            for (size_t _tk = 0; _tk < _tcr[_tn].size(); ++_tk)",
        "                _tgt[(size_t)((int64_t)_tn * _tw) + _tk] = "
        "_tcr[_tn][_tk];",
        "        %s = nd::from_data<int64_t>(_tgt, "
        "{(int64_t)_tcr.size(), _tw});" % dst,
        "    }",
    ]
    return body, array_t("int64", 2)


def _materialise_geo_channel(member, kind, channel, dst):
    """Emit C++ (indent-1) binding a geo-input read-surface ``channel`` to nd
    local ``dst``, read from ``in_<member>`` (an MFn*) exactly as the interpreted
    wrapper reads it. Returns (lines, CppType). Raises UnsupportedSpec for a
    channel with no deterministic materialiser (kept off the porter path).

    A ``channel`` given as a tuple ``(op, tag)`` is a component-tag read and is
    delegated to :func:`_materialise_geo_tag` (region / tag indices)."""
    if isinstance(channel, tuple):
        return _materialise_geo_tag(member, kind, channel, dst)
    src = "in_" + member
    guard = "!%s_obj.isNull() && %s_obj.hasFn(MFn::%s)" % (
        src, src, _GEO_FN_CONST[kind])

    # ---- mesh --------------------------------------------------------------
    if kind == "mesh":
        if channel == "points":
            # Object-space positions straight off the mesh's internal float
            # array (the same read nd_read_mesh uses): Maya stores vertices as
            # float3, so getPoints(kObject) is that array widened to double --
            # reading it raw is bit-identical and skips the MPointArray copy.
            return ([
                "    nd::Array<double> %s;" % dst,
                "    {",
                "        const float* _gr = (%s) ? %s.getRawPoints(NULL) : "
                "(const float*)0;" % (guard, src),
                "        unsigned int _gn = (_gr == 0) ? 0u : "
                "(unsigned int)%s.numVertices();" % src,
                "        std::vector<double> _gt; _gt.reserve((size_t)_gn * 3);",
                "        for (unsigned int _gi = 0; _gi < _gn; ++_gi) {",
                "            _gt.push_back((double)_gr[3 * _gi]); "
                "_gt.push_back((double)_gr[3 * _gi + 1]); "
                "_gt.push_back((double)_gr[3 * _gi + 2]);",
                "        }",
                "        %s = nd::from_data<double>(_gt, {(int64_t)_gn, 3});" % dst,
                "    }",
            ], array_t("double", 2))
        if channel in ("counts", "indices"):
            which = "_gc" if channel == "counts" else "_gv"
            fill = [
                "        MIntArray _gc, _gv;",
                "        if (%s) %s.getVertices(_gc, _gv);" % (guard, src),
            ]
            return (_geo_int1_lines(dst, guard, fill, which, "%s.length()" % which),
                    array_t("int64", 1))
        if channel == "normals":
            fill = [
                "        MFloatVectorArray _ga;",
                "        if (%s) %s.getVertexNormals(false, _ga, MSpace::kObject);"
                % (guard, src),
            ]
            return (_geo_vec3_lines(dst, guard, fill, "_ga.length()"),
                    array_t("double", 2))
        if channel == "uvs":
            # (M,2) (u,v) points of the FIRST non-empty UV set -- matches the
            # interpreted Mesh.uvs (uv_sets[0].points; empty sets skipped).
            return (_geo_uv_lines(src, guard, dst), array_t("double", 2))

    # ---- curve -------------------------------------------------------------
    if kind == "curve":
        if channel in ("points", "cvs"):
            fill = [
                "        MPointArray _ga;",
                "        if (%s) %s.getCVs(_ga, MSpace::kObject);" % (guard, src),
            ]
            return (_geo_vec3_lines(dst, guard, fill, "_ga.length()"),
                    array_t("double", 2))
        if channel == "knots":
            fill = [
                "        MDoubleArray _gk;",
                "        if (%s) %s.getKnots(_gk);" % (guard, src),
            ]
            return (_geo_dbl1_lines(dst, fill, "_gk", "_gk.length()"),
                    array_t("double", 1))
        if channel in ("degree", "form"):
            call = "degree" if channel == "degree" else "form"
            return ([
                "    int64_t %s = 0;" % dst,
                "    if (%s) %s = (int64_t)%s.%s();" % (guard, dst, src, call),
            ], scalar_t("int64"))

    # ---- surface -----------------------------------------------------------
    if kind == "surface":
        if channel in ("cvs", "points"):
            # (nu, nv, 3) U-major grid -- matches the interpreted reshape. Both
            # ``.points`` (unified name) and ``.cvs`` (NURBS alias) read this.
            return ([
                "    nd::Array<double> %s;" % dst,
                "    {",
                "        MPointArray _ga; int64_t _nu = 0, _nv = 0;",
                "        if (%s) { %s.getCVs(_ga, MSpace::kObject); "
                "_nu = (int64_t)%s.numCVsInU(); _nv = (int64_t)%s.numCVsInV(); }"
                % (guard, src, src, src),
                "        std::vector<double> _gt; _gt.reserve((size_t)_ga.length() "
                "* 3);",
                "        for (unsigned int _gi = 0; _gi < _ga.length(); ++_gi) {",
                "            _gt.push_back(_ga[_gi].x); _gt.push_back(_ga[_gi].y); "
                "_gt.push_back(_ga[_gi].z);",
                "        }",
                "        if ((int64_t)_ga.length() == _nu * _nv && _nu > 0 && "
                "_nv > 0)",
                "            %s = nd::from_data<double>(_gt, {_nu, _nv, 3});" % dst,
                "        else",
                "            %s = nd::from_data<double>(_gt, "
                "{(int64_t)_ga.length(), 3});" % dst,
                "    }",
            ], array_t("double", 3))
        if channel in ("knots_u", "knots_v"):
            call = "getKnotsInU" if channel == "knots_u" else "getKnotsInV"
            fill = [
                "        MDoubleArray _gk;",
                "        if (%s) %s.%s(_gk);" % (guard, src, call),
            ]
            return (_geo_dbl1_lines(dst, fill, "_gk", "_gk.length()"),
                    array_t("double", 1))
        _SCAL = {"num_u": "numCVsInU", "num_v": "numCVsInV",
                 "degree_u": "degreeU", "degree_v": "degreeV",
                 "form_u": "formInU", "form_v": "formInV"}
        if channel in _SCAL:
            return ([
                "    int64_t %s = 0;" % dst,
                "    if (%s) %s = (int64_t)%s.%s();" % (guard, dst, src, _SCAL[channel]),
            ], scalar_t("int64"))

    raise UnsupportedSpec("nd_lower: geo channel %r on %s not materialisable"
                          % (channel, kind))


def _rewrite_geo_reads(source, geo_in, str_arr_in=None):
    """Rewrite the geometry-input READ SURFACE into synthetic self-attrs.

    ``geo_in``: ``{plug: (member, kind)}`` for each declared SINGLE geo INPUT.
    ``str_arr_in``: ``{plug: member}`` for each declared multi-STRING INPUT --
    the only argument ``self.<geo>.tag_clusters(...)`` accepts (its tag names
    are runtime data read from ``in_<member>``).
    Returns ``(new_source, binds)`` where ``binds`` maps ``synthetic_plug ->
    (member, kind, channel)``. Raises ``UnsupportedSpec`` if any geo input (or a
    local single-assignment alias of one) is used outside the supported numpy
    read surface -- so the whole compute falls back to the AI porter with zero
    regression.
    """
    str_arr_in = str_arr_in or {}
    tree = ast.parse(source)

    # A local name aliases a geo input only if it is assigned EXACTLY once and that
    # assignment is ``name = self.<geoIn>`` (a reassigned / multi-source name is
    # NOT treated as an alias -- its geo assignment then survives as a bare use and
    # is rejected below, conservatively).
    name_vals = {}
    for st in ast.walk(tree):
        if isinstance(st, ast.Assign):
            for tg in st.targets:
                if isinstance(tg, ast.Name):
                    name_vals.setdefault(tg.id, []).append(st.value)
    alias = {}
    for nm, vals in name_vals.items():
        if len(vals) != 1:
            continue
        v = vals[0]
        if (isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name)
                and v.value.id == "self" and v.attr in geo_in):
            alias[nm] = v.attr

    binds = {}
    bad = []

    def _georef(node):
        # -> plug if node reads a geo input directly (self.<geoIn>) or via alias.
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "self" and node.attr in geo_in):
            return node.attr
        if isinstance(node, ast.Name) and node.id in alias:
            return alias[node.id]
        return None

    class _T(ast.NodeTransformer):
        def visit_Assign(self, node):
            # Drop the now-dead ``alias = self.<geoIn>`` binding (its every use is
            # rewritten to a synthetic; a surviving bare use is rejected via _bad).
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in alias
                    and _georef(node.value) is not None):
                return None
            self.generic_visit(node)
            return node

        def visit_Attribute(self, node):
            plug = _georef(node.value)
            if plug is not None:
                member, kind = geo_in[plug]
                ch = node.attr
                if ch in _GEO_IN_CHANNELS.get(kind, ()):
                    syn = "%s%s_%s_" % (_GEO_SYN_PREFIX, member, ch)
                    binds[syn] = (member, kind, ch)
                    return ast.copy_location(
                        ast.Attribute(
                            value=ast.Name(id="self", ctx=ast.Load()),
                            attr=syn, ctx=node.ctx), node)
                bad.append("%s.%s" % (plug, ch))
                return node
            # A bare ``self.<geoIn>`` that reached here is NOT a supported channel
            # base (the outer channel access would have consumed it) -> unsupported.
            if (isinstance(node.value, ast.Name) and node.value.id == "self"
                    and node.attr in geo_in):
                bad.append(node.attr)
                return node
            self.generic_visit(node)
            return node

        def visit_Name(self, node):
            if node.id in alias:
                bad.append(node.id)   # bare alias use (not consumed as a channel)
            return node

        def visit_Call(self, node):
            # ``self.<geo>.region("literalTag")`` -> synthetic (K,3) points gather.
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "region":
                plug = _georef(f.value)
                if plug is not None:
                    if (len(node.args) == 1 and not node.keywords
                            and isinstance(node.args[0], ast.Constant)
                            and isinstance(node.args[0].value, str)):
                        member, kind = geo_in[plug]
                        tag = node.args[0].value
                        syn = _tag_syn(member, "region", tag)
                        binds[syn] = (member, kind, ("region", tag))
                        return ast.copy_location(_syn_attr(syn), node)
                    bad.append("%s.region(<non-literal>)" % plug)
                    return node
            # ``self.<geo>.tag_clusters(self.<multiStringIn>)`` -> synthetic
            # (N, L) padded int64 cluster array, tag NAMES read at runtime.
            if isinstance(f, ast.Attribute) and f.attr == "tag_clusters":
                plug = _georef(f.value)
                if plug is not None:
                    a = node.args[0] if len(node.args) == 1 else None
                    if (a is not None and not node.keywords
                            and isinstance(a, ast.Attribute)
                            and isinstance(a.value, ast.Name)
                            and a.value.id == "self"
                            and a.attr in str_arr_in):
                        member, kind = geo_in[plug]
                        syn = _tag_syn(member, "tagcl", a.attr)
                        binds[syn] = (member, kind,
                                      ("tagclusters", str_arr_in[a.attr]))
                        return ast.copy_location(_syn_attr(syn), node)
                    bad.append("%s.tag_clusters(<not a multi-string input>)"
                               % plug)
                    return node
            self.generic_visit(node)
            return node

        def visit_Subscript(self, node):
            # ``self.<geo>.component_tags["literalTag"]["indices"]`` -> synthetic
            # (K,) [mesh/curve] or (K,2) [surface] int index array.
            if (isinstance(node.slice, ast.Constant)
                    and node.slice.value == "indices"
                    and isinstance(node.value, ast.Subscript)):
                inner = node.value
                base = inner.value
                if (isinstance(base, ast.Attribute)
                        and base.attr == "component_tags"
                        and isinstance(inner.slice, ast.Constant)
                        and isinstance(inner.slice.value, str)):
                    plug = _georef(base.value)
                    if plug is not None:
                        member, kind = geo_in[plug]
                        tag = inner.slice.value
                        syn = _tag_syn(member, "tagidx", tag)
                        binds[syn] = (member, kind, ("tagidx", tag))
                        return ast.copy_location(_syn_attr(syn), node)
            self.generic_visit(node)
            return node

    def _syn_attr(syn):
        return ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                             attr=syn, ctx=ast.Load())

    new_tree = _T().visit(tree)
    if bad:
        raise UnsupportedSpec(
            "nd_lower: geometry input used outside the supported read surface: %s"
            % ", ".join(sorted(set(bad))))
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree), binds


# ---- ARRAY (multi) geo-input read surface: ``self.<geoArr>[<int>].<channel>``.
# The emitter reads a multi geo input into ``std::vector<Nd<Kind>> in_<m>`` (see
# emit_geo_io.geo_array_input_lines / emit_compute); this rewrites each element
# channel read into a synthetic self-attr materialised from ``in_<m>[index]``.
def _const_int(node):
    """The int a literal index node denotes, else None. ``-1`` parses as a USub
    UnaryOp (not a negative Constant), so both forms are matched."""
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)
            and not isinstance(node.operand.value, bool)):
        return -node.operand.value
    if (isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool)):
        return node.value
    return None


def _geo_arr_elem(node, geo_arr_in):
    """-> ``(plug, index)`` if ``node`` is ``self.<geoArr>[<const int>]`` for a
    declared array geo input, else None. The index may be NEGATIVE (Python
    end-relative, see _geo_arr_at); non-constant indices are NOT matched (they
    fall through to a bare use -> porter fallback)."""
    if (isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "self"
            and node.value.attr in geo_arr_in):
        idx = _const_int(node.slice)
        if idx is not None:
            return (node.value.attr, idx)
    return None


def _geo_arr_ix_tag(idx):
    """The index token used inside a synthetic self-attr name -- a negative index
    becomes ``m<k>`` so the name stays a valid C++ identifier."""
    return ("m%d" % -idx) if idx < 0 else ("%d" % idx)


def _geo_arr_at(v, idx):
    """``(element lvalue, in-range condition)`` for ``in_<m>[idx]``.

    A NEGATIVE literal index counts from the END, exactly as Python does on the
    interpreted value: ``read_user_inputs_dict`` hands the compute a DENSE list
    whose length is the multi's logical span, which is the same span the
    emitter's ``std::vector`` has (verified against dense / gapped / offset
    multis), so ``list[-k]`` and ``in_<m>[size-k]`` are the same element.
    The condition is false when the index is out of range; every caller then
    leaves its channel empty (the missing-multi-element convention)."""
    if idx >= 0:
        return ("%s[%d]" % (v, idx), "(size_t)%d < %s.size()" % (idx, v))
    return ("%s[%s.size() - %d]" % (v, v, -idx), "%s.size() >= %d" % (v, -idx))


def _geo_arr_vec3(v, idx, field, dst):
    """(N,3) double nd::Array from ``in_<m>[idx].<field>`` (std::vector<MPoint|
    MVector>). Bounds-safe: an out-of-range idx yields an empty (0,3) array."""
    e, ok = _geo_arr_at(v, idx)
    ref = "%s.%s" % (e, field)
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _gt; int64_t _n = 0;",
        "        if (%s) {" % ok,
        "            _n = (int64_t)%s.size();" % ref,
        "            _gt.reserve((size_t)_n * 3);",
        "            for (size_t _gi = 0; _gi < %s.size(); ++_gi) {" % ref,
        "                _gt.push_back(%s[_gi].x); _gt.push_back(%s[_gi].y); "
        "_gt.push_back(%s[_gi].z);" % (ref, ref, ref),
        "            }",
        "        }",
        "        %s = nd::from_data<double>(_gt, {_n, 3});" % dst,
        "    }",
    ]


def _geo_arr_int1(v, idx, field, dst):
    """(K,) int64 nd::Array from ``in_<m>[idx].<field>`` (std::vector<int>)."""
    e, ok = _geo_arr_at(v, idx)
    ref = "%s.%s" % (e, field)
    return [
        "    nd::Array<int64_t> %s;" % dst,
        "    {",
        "        std::vector<int64_t> _gt;",
        "        if (%s) {" % ok,
        "            _gt.resize(%s.size());" % ref,
        "            for (size_t _gi = 0; _gi < %s.size(); ++_gi) _gt[_gi] = "
        "(int64_t)%s[_gi];" % (ref, ref),
        "        }",
        "        %s = nd::from_data<int64_t>(_gt, {(int64_t)_gt.size()});" % dst,
        "    }",
    ]


def _geo_arr_uv(v, idx, dst):
    """(M,2) double nd::Array of the first UV set's (u,v) points from
    ``in_<m>[idx].uvs`` / ``.numUVs`` (filled by nd_read_mesh)."""
    e, ok = _geo_arr_at(v, idx)
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _gt; int64_t _m = 0;",
        "        if (%s) { _gt = %s.uvs; _m = (int64_t)%s.numUVs; }" % (ok, e, e),
        "        %s = nd::from_data<double>(_gt, {_m, 2});" % dst,
        "    }",
    ]


def _geo_arr_dbl1(v, idx, field, dst):
    """(K,) double nd::Array from ``in_<m>[idx].<field>`` (std::vector<double>)."""
    e, ok = _geo_arr_at(v, idx)
    ref = "%s.%s" % (e, field)
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _gt;",
        "        if (%s) _gt = %s;" % (ok, ref),
        "        %s = nd::from_data<double>(_gt, {(int64_t)_gt.size()});" % dst,
        "    }",
    ]


def _geo_arr_scalar_int(v, idx, field, dst):
    """int64 scalar from ``in_<m>[idx].<field>`` (0 when idx out of range)."""
    e, ok = _geo_arr_at(v, idx)
    return [
        "    int64_t %s = 0;" % dst,
        "    if (%s) %s = (int64_t)%s.%s;" % (ok, dst, e, field),
    ]


def _geo_arr_len(v, dst):
    """int64 element count of the ARRAY geo input -- ``len(self.<geoArr>)``. The
    emitter's vector is dense over the multi's logical span, the same span the
    interpreted dense list has, so the two counts agree."""
    return ["    int64_t %s = (int64_t)%s.size();" % (dst, v)]


def _geo_arr_surface_cvs(v, idx, dst):
    """(nu,nv,3) U-major CV grid (or (N,3) fallback) from ``in_<m>[idx]`` NdSurface
    (matches _materialise_geo_channel surface cvs / the interpreted reshape)."""
    e, ok = _geo_arr_at(v, idx)
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _gt; int64_t _nu = 0, _nv = 0, _n = 0;",
        "        if (%s) {" % ok,
        "            _n = (int64_t)%s.cvs.size();" % e,
        "            _nu = (int64_t)%s.numU; _nv = (int64_t)%s.numV;" % (e, e),
        "            _gt.reserve((size_t)_n * 3);",
        "            for (size_t _gi = 0; _gi < %s.cvs.size(); ++_gi) {" % e,
        "                _gt.push_back(%s.cvs[_gi].x); _gt.push_back(%s.cvs[_gi].y); "
        "_gt.push_back(%s.cvs[_gi].z);" % (e, e, e),
        "            }",
        "        }",
        "        if (_n == _nu * _nv && _nu > 0 && _nv > 0)",
        "            %s = nd::from_data<double>(_gt, {_nu, _nv, 3});" % dst,
        "        else",
        "            %s = nd::from_data<double>(_gt, {_n, 3});" % dst,
        "    }",
    ]


def _materialise_geo_array_channel(member, kind, index, channel, dst):
    """Bind an ARRAY geo-input element read ``self.<geoArr>[index].<channel>`` to
    nd local ``dst``, read from the ``in_<member>[index]`` Nd<Kind> struct the
    emitter declared. Bounds-safe (out-of-range index -> empty channel, parity
    with a missing multi element). Returns (lines, CppType). Raises
    UnsupportedSpec for an unsupported kind/channel (-> porter fallback).

    Channels whose struct field matches the single-geo _materialise_geo_channel
    read (hence parity-proven) are supported; the curve/surface ``form*`` enum is
    NOT (the struct stores a periodic 0/1, not the raw MFn form()), so it falls to
    the porter. The synthetic ``__len__`` channel (index None) is the whole-list
    ``len(self.<geoArr>)``."""
    v = "in_" + member
    if channel == _GEO_ARR_LEN:
        return (_geo_arr_len(v, dst), scalar_t("int64"))
    if kind == "mesh":
        if channel in ("points", "normals"):
            return (_geo_arr_vec3(v, index, channel, dst), array_t("double", 2))
        if channel in ("counts", "indices"):
            return (_geo_arr_int1(v, index, channel, dst), array_t("int64", 1))
        if channel == "uvs":
            return (_geo_arr_uv(v, index, dst), array_t("double", 2))
    if kind == "curve":
        if channel in ("points", "cvs"):
            return (_geo_arr_vec3(v, index, "cvs", dst), array_t("double", 2))
        if channel == "knots":
            return (_geo_arr_dbl1(v, index, "knots", dst), array_t("double", 1))
        if channel == "degree":
            return (_geo_arr_scalar_int(v, index, "degree", dst), scalar_t("int64"))
    if kind == "surface":
        if channel in ("points", "cvs"):
            return (_geo_arr_surface_cvs(v, index, dst), array_t("double", 3))
        if channel in ("knots_u", "knots_v"):
            field = "knotsU" if channel == "knots_u" else "knotsV"
            return (_geo_arr_dbl1(v, index, field, dst), array_t("double", 1))
        _SCAL = {"num_u": "numU", "num_v": "numV",
                 "degree_u": "degreeU", "degree_v": "degreeV"}
        if channel in _SCAL:
            return (_geo_arr_scalar_int(v, index, _SCAL[channel], dst),
                    scalar_t("int64"))
    raise UnsupportedSpec(
        "nd_lower: geo array channel %r on %s not materialisable" % (channel, kind))


def _rewrite_geo_array_reads(source, geo_arr_in):
    """Rewrite the ARRAY geo-input READ SURFACE into synthetic self-attrs.

    ``geo_arr_in``: ``{plug: (member, kind)}`` for each declared ARRAY geo INPUT.
    Handles ``self.<geoArr>[<int>].<channel>`` (the index may be negative), a
    single-assignment alias ``x = self.<geoArr>[<int>]`` then ``x.<channel>``, and
    the whole-list ``len(self.<geoArr>)``. Returns ``(new_source, binds)`` where
    ``binds`` maps ``synthetic_plug -> (member, kind, index, channel)`` (index
    None for ``len``). Raises ``UnsupportedSpec`` for any element use outside the
    supported channel surface -> whole compute falls back to the porter."""
    tree = ast.parse(source)

    name_vals = {}
    for st in ast.walk(tree):
        if isinstance(st, ast.Assign):
            for tg in st.targets:
                if isinstance(tg, ast.Name):
                    name_vals.setdefault(tg.id, []).append(st.value)
    alias = {}
    for nm, vals in name_vals.items():
        if len(vals) != 1:
            continue
        el = _geo_arr_elem(vals[0], geo_arr_in)
        if el is not None:
            alias[nm] = el

    binds = {}
    bad = []

    def _elemref(node):
        el = _geo_arr_elem(node, geo_arr_in)
        if el is not None:
            return el
        if isinstance(node, ast.Name) and node.id in alias:
            return alias[node.id]
        return None

    def _syn_attr(syn):
        return ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                             attr=syn, ctx=ast.Load())

    class _T(ast.NodeTransformer):
        def visit_Assign(self, node):
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in alias
                    and _geo_arr_elem(node.value, geo_arr_in) is not None):
                return None                   # drop dead alias binding
            self.generic_visit(node)
            return node

        def visit_Call(self, node):
            # ``len(self.<geoArr>)`` -> the multi's element count.
            one = (len(node.args) == 1 and not node.keywords)
            arg = node.args[0] if one else None
            if (isinstance(node.func, ast.Name) and node.func.id == "len"
                    and isinstance(arg, ast.Attribute)
                    and isinstance(arg.value, ast.Name) and arg.value.id == "self"
                    and arg.attr in geo_arr_in):
                member, kind = geo_arr_in[arg.attr]
                syn = "%sarrlen_%s_" % (_GEO_SYN_PREFIX, member)
                binds[syn] = (member, kind, None, _GEO_ARR_LEN)
                return ast.copy_location(_syn_attr(syn), node)
            self.generic_visit(node)
            return node

        def visit_Attribute(self, node):
            el = _elemref(node.value)
            if el is not None:
                plug, index = el
                member, kind = geo_arr_in[plug]
                ch = node.attr
                if ch in _GEO_IN_CHANNELS.get(kind, ()):
                    syn = "%sarr_%s_%s_%s_" % (_GEO_SYN_PREFIX, member,
                                               _geo_arr_ix_tag(index), ch)
                    binds[syn] = (member, kind, index, ch)
                    return ast.copy_location(_syn_attr(syn), node)
                bad.append("%s[%d].%s" % (plug, index, ch))
                return node
            self.generic_visit(node)
            return node

        def visit_Name(self, node):
            if node.id in alias:
                bad.append(node.id)           # bare alias use (not a channel)
            return node

    new_tree = _T().visit(tree)
    if bad:
        raise UnsupportedSpec(
            "nd_lower: geo array input used outside the supported read surface: %s"
            % ", ".join(sorted(set(bad))))
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree), binds


def _geo_input_surface(ins, source, allow_geo_array=False):
    """Rewrite the geometry-input read surface in ``source`` and materialise every
    referenced channel. Shared by lower_compute / lower_geo_compute / lower_deform
    so every family reads a single geo INPUT identically (the emitter has already
    declared the ``in_<member>`` MFn* those reads bind to).

    ``ins``            : codegen input descriptor dicts.
    ``allow_geo_array``: also process ARRAY geo inputs (``self.<geoArr>[i].<ch>``),
                         which bind to the emitter's ``std::vector<Nd<Kind>>
                         in_<m>``. Only the plain MPxNode path (lower_compute)
                         declares that vector, so it passes True; the generator /
                         deformer paths leave array reads to fall back to the porter.
    Returns ``(new_source, geo_env, geo_materialise)``:
      new_source      -- ``source`` with each supported geo read rewritten to a
                         synthetic self-attr (unchanged when there are none).
      geo_env         -- ``{"self.<syn>": CppType}`` to seed the transpiler env.
      geo_materialise -- indent-1 C++ lines binding each synthetic to its nd value.
    Raises UnsupportedSpec if a geo input is used outside the supported surface."""
    geo_in = {i["plug"]: (i["member"], _GEO_IN_TYPE_KIND[i["meta"]["type"]])
              for i in ins if _is_geo_input(i["meta"])}
    geo_arr = {i["plug"]: (i["member"], _GEO_IN_TYPE_KIND[i["meta"]["type"]])
               for i in ins if _is_geo_array_input(i["meta"])} if allow_geo_array \
        else {}
    if not geo_in and not geo_arr:
        return source, {}, []
    geo_env = {}
    geo_materialise = []
    if geo_in:
        str_arr = {i["plug"]: i["member"] for i in ins
                   if i["meta"].get("is_array")
                   and i["meta"].get("type") == "string"}
        source, geo_binds = _rewrite_geo_reads(source, geo_in, str_arr)
        for syn, (member, kind, channel) in geo_binds.items():
            lines, typ = _materialise_geo_channel(
                member, kind, channel, env_cpp_name("self." + syn))
            geo_materialise += lines
            geo_env["self." + syn] = typ
    if geo_arr:
        source, arr_binds = _rewrite_geo_array_reads(source, geo_arr)
        for syn, (member, kind, index, channel) in arr_binds.items():
            lines, typ = _materialise_geo_array_channel(
                member, kind, index, channel, env_cpp_name("self." + syn))
            geo_materialise += lines
            geo_env["self." + syn] = typ
    return source, geo_env, geo_materialise


# ---- Eager-evaluation guard stripping --------------------------------------
# An interpreted compute wraps its input reads in a guard so a PARTIAL state
# during EAGER evaluation (mid-wiring, before the demo/setup seeds inputs, or
# while an input is momentarily unconnected) no-ops instead of raising::
#
#     _ok = True
#     try:
#         <body>
#     except Exception:
#         _ok = False
#     if _ok and <cond> ...:
#         <assign>
#
# A COMPILED node never sees a partial state -- Maya delivers valid input handles
# at compute time -- so the guard is pure interpreted-side defense. To let the
# SAME defensively-wrapped source lower deterministically (no AI-porter), strip
# the guard to its equivalent unguarded form before lowering::
#
#     <body>
#     if <cond> ...:
#         <assign>
#
# Only a TRIVIAL handler (the flag set to a constant and/or ``pass``) is
# recognised; any real recovery logic is left intact so the node falls back to
# the porter with zero behaviour change. This transform runs ONLY on the compile
# path -- the interpreted node keeps its try/except and its eager-eval safety.


def _is_trivial_guard_try(node):
    """A ``Try`` is an eager guard iff it has no else/finally and every handler
    body is only ``pass`` and/or ``<name> = <constant>`` (the failure flag)."""
    if node.orelse or node.finalbody or not node.handlers:
        return False
    for h in node.handlers:
        for s in h.body:
            if isinstance(s, ast.Pass):
                continue
            if (isinstance(s, ast.Assign) and len(s.targets) == 1
                    and isinstance(s.targets[0], ast.Name)
                    and isinstance(s.value, ast.Constant)):
                continue
            return False
    return True


def _guard_flag(node):
    """The failure-flag name a trivial guard sets in its handler, else None."""
    for h in node.handlers:
        for s in h.body:
            if (isinstance(s, ast.Assign)
                    and isinstance(s.targets[0], ast.Name)
                    and isinstance(s.value, ast.Constant)):
                return s.targets[0].id
    return None


class _FlagStripper(ast.NodeTransformer):
    """Remove the guard flag from downstream boolean tests: ``_ok and X`` -> X,
    ``_ok and X and Y`` -> ``X and Y``, a lone ``_ok`` -> ``True``."""

    def __init__(self, flag):
        self.flag = flag

    def visit_BoolOp(self, node):
        vals = [v for v in node.values
                if not (isinstance(v, ast.Name) and v.id == self.flag)]
        if not vals:
            return ast.copy_location(ast.Constant(value=True), node)
        node.values = vals
        self.generic_visit(node)
        if len(node.values) == 1:
            return node.values[0]
        return node

    def visit_Name(self, node):
        if node.id == self.flag and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Constant(value=True), node)
        return node


def _strip_eager_guard(source):
    """Rewrite a top-level eager-evaluation guard (see module note) to its
    unguarded form so a defensively-wrapped interpreted compute lowers. Returns
    the source unchanged if no trivial guard is present."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    flag = None
    hoisted = []
    changed = False
    for st in tree.body:
        if isinstance(st, ast.Try) and _is_trivial_guard_try(st):
            f = _guard_flag(st)
            if f is not None:
                flag = f
            hoisted.extend(st.body)       # hoist the guarded body to top level
            changed = True
        else:
            hoisted.append(st)
    if not changed:
        return source
    # Drop the `flag = <const>` bookkeeping assigns, then strip the flag from the
    # downstream if-tests.
    cleaned = []
    for st in hoisted:
        if (flag and isinstance(st, ast.Assign) and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
                and st.targets[0].id == flag
                and isinstance(st.value, ast.Constant)):
            continue
        cleaned.append(st)
    new_tree = ast.Module(body=cleaned, type_ignores=[])
    if flag:
        new_tree = _FlagStripper(flag).visit(new_tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


class LoweredBody(list):
    """compute() body lines PLUS the class-body declarations they depend on.

    A plain list everywhere it is consumed (``lowered_guard`` splices it,
    ``reject_unlowered_io`` only tests it against None), so no caller changes.
    ``state_decls`` is the extra channel the node emitter needs: the lowered body
    binds ``st`` to a per-instance ``_NdState`` member, and only the emitter that
    writes the class body can declare it."""

    state_decls = ()


def lower_compute(ins, outs, source, init=None, spec=None):
    """Lower a compute block to C++ body lines, or raise UnsupportedSpec.

    ins/outs : codegen descriptor dicts.
    source   : the Python compute block (bare statements).
    init     : optional helper source; its top-level `def`s the compute calls are
               lowered to C++ lambdas emitted ahead of the body. A single source
               string OR a list of sources (INIT-tier + followed external helper
               units; see _combined_helper_source).
    spec     : optional full spec dict -- carries spec['mpy_type'] so blessed API
               methods (self.read_texture()/self.sample_texture()) lower to the
               hand-written nd_tex_* kernels. None (or a non-blessed type) ->
               empty blessed maps -> zero behaviour change for every other node.
    Returns a list of indent-1 C++ lines: input materialisation, hoisted decls,
    helper lambdas, then the transpiled body (which writes outputs inline via
    the writers). Outputs written BY INDEX are bound as pre-sized buffers and
    flushed after the body (see _materialise_output_buffer).
    """
    if not outs:
        raise UnsupportedSpec("nd_lower: node has no outputs")

    # Strip any interpreted-side eager-evaluation guard (try/except + _ok flag)
    # so a defensively-wrapped compute lowers deterministically; a compiled node
    # never sees the partial state the guard defends against.
    source = _strip_eager_guard(source)

    # Geometry INPUT read surface (Phase 6): rewrite each supported
    # ``self.<geoIn>.<channel>`` (single) and ``self.<geoArr>[i].<channel>`` (array)
    # read into a synthetic self-attr bound to an nd:: value materialised from the
    # input MFn* / Nd<Kind> struct. Done BEFORE _used_self_attrs so the rewritten
    # synthetics (not the raw geo plug) are what gets bound + transpiled. The plain
    # MPxNode is the only family whose emitter declares ``std::vector<Nd<Kind>>
    # in_<m>``, so it is the only path that opts into array-geo (allow_geo_array).
    source, geo_env, geo_materialise = _geo_input_surface(
        ins, source, allow_geo_array=True)

    used = _used_self_attrs(source)

    # Bind every USED input of a liftable type; unused inputs are ignored (a
    # node may carry an input its numpy-liftable compute never touches). A used
    # input of an unliftable type raises -> whole node falls back.
    env = dict(geo_env)
    materialise = list(geo_materialise)
    in_by_plug = {i["plug"]: i for i in ins}
    # sorted(): `used` is a SET of attr-name strings, whose iteration order
    # moves with PYTHONHASHSEED. These bindings are independent declarations, so
    # any fixed order is correct -- but it has to BE fixed, or the node's C++
    # (and its build hash) differs process to process. Same reason as the
    # sorted(subscript_out) below.
    for plug in sorted(used):
        m = in_by_plug.get(plug)
        if m is None:
            continue                      # not an input (maybe an output write)
        lines, typ = _materialise_input(m, env_cpp_name("self." + plug))
        materialise += lines
        env["self." + plug] = typ

    # Bind each output WRITTEN BY INDEX as a pre-sized buffer (so len()/index/
    # write work); whole-assigned outputs keep the writer-on-assignment path.
    out_by_plug = {o["plug"]: o for o in outs}
    subscript_out, whole_out = _output_subscript_targets(source, set(out_by_plug))
    buffered = []
    out_materialise = []
    for plug in sorted(subscript_out):
        m = out_by_plug[plug]
        if plug in whole_out:
            raise UnsupportedSpec("nd_lower: output %r written both whole and by "
                                  "index; not supported" % plug)
        if not m["meta"].get("is_array"):
            raise UnsupportedSpec("nd_lower: indexed write to non-array output %r"
                                  % plug)
        lines, typ = _materialise_output_buffer(m, env_cpp_name("self." + plug))
        out_materialise += lines
        env["self." + plug] = typ
        buffered.append(m)

    # A writer per WHOLE-assigned output (raises if the output type is unliftable
    # AND the compute actually writes it). Index-written outputs are flushed from
    # their buffer after the body instead, so they get no on-assignment writer.
    writers = {"self." + o["plug"]: _output_writer(o)
               for o in outs if o["plug"] not in subscript_out}

    # Persistent stateful self-vars (undeclared self.<name> written whole): give
    # them a per-node home so they LATCH across evals instead of being flattened.
    declared = {i["plug"] for i in ins} | {o["plug"] for o in outs}
    state_vars = _persistent_state_vars(source, declared)

    # Blessed API-method lowerings (mPyFile texture kernels). Empty maps for a
    # non-blessed/non-mPyFile spec -> the transpiler behaves exactly as before.
    blessed, blessed_unpack = ({}, {})
    if spec is not None:
        blessed, blessed_unpack = file_texture_cpp.make_blessed_lowerings(
            ins, outs, spec)

    res, written, helper_lines = py_to_cpp.transpile_compute_block(
        source, env, writers, init, state_vars=state_vars,
        blessed=blessed, blessed_unpack=blessed_unpack)

    # The state binding (declares `st`) must precede any body line that reads or
    # writes a member; member C++ types come from the transpiler's discovery. The
    # matching declarations go in the CLASS body -- returned alongside the lines
    # for the node emitter to place (see LoweredBody.state_decls).
    state_decls = _state_member_decls(res.state_members)
    state_preamble = _state_binding_preamble(res.state_members)

    # Index-written outputs are written into their buffer (not via a writer), so
    # count them as written for the completeness check.
    written = set(written) | {"self." + m["plug"] for m in buffered}
    missing = [o["plug"] for o in outs if ("self." + o["plug"]) not in written]
    if missing:
        raise UnsupportedSpec("nd_lower: compute does not write output(s) %s"
                              % ", ".join(sorted(missing)))

    # Flush each index-written buffer into its out_<member> sink via the SAME
    # writer the whole-assign path uses (resize + element copy from the buffer).
    flush = []
    for m in buffered:
        buf = Val(env_cpp_name("self." + m["plug"]), env["self." + m["plug"]])
        flush += _output_writer(m)(buf)

    body = LoweredBody(
        state_preamble + materialise + out_materialise + list(res.decl_lines)
        + list(helper_lines) + list(res.body_lines) + flush)
    body.state_decls = tuple(state_decls)
    return body


def try_lower_compute(ins, outs, spec):
    """Attempt to lower spec['compute']; return C++ body lines or None.

    None means "not lowerable" -- the caller keeps its existing behaviour. Any
    UnsupportedSpec (unliftable type, unsupported construct, unwritten output,
    empty/absent compute) yields None so codegen falls back with zero regression.
    """
    source = spec.get("compute")
    if not source or not source.strip():
        return None
    has_geo_out = any(o["meta"]["type"] in _GEO_IN_TYPE_KIND for o in outs)
    try:
        if has_geo_out:
            # Geo outputs use the emit_geo_io Nd<Kind> struct value model, not the
            # numeric nd:: sinks -- route to the dedicated geo-io lowerer.
            return lower_geo_io_compute(ins, outs, source,
                                        _combined_helper_source(spec))
        return lower_compute(ins, outs, source, _combined_helper_source(spec),
                             spec=spec)
    except UnsupportedSpec:
        return None


# ---- geometry-generator lowering (mesh/curve/surface buffer fill) ----------
def _geo_mpoint_lines(buf, val):
    """Fill std::vector<MPoint> buffer `buf` from an (N,3) nd value."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower geo: non-array assigned to point buffer "
                              "%r" % buf)
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.shape.empty() ? 0 : _o.shape[0];",
        "    %s.clear(); %s.reserve((size_t)_n);" % (buf, buf),
        "    for (int64_t _i = 0; _i < _n; ++_i)",
        "        %s.push_back(MPoint((*_o.data)[_i*3+0], (*_o.data)[_i*3+1], "
        "(*_o.data)[_i*3+2]));" % buf,
        "}",
    ]


def _geo_intarr_lines(buf, val):
    """Fill std::vector<int> buffer `buf` from a 1-D nd value (int cast)."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower geo: non-array assigned to int buffer "
                              "%r" % buf)
    return [
        "{",
        "    nd::Array<int64_t> _o = (%s);" % _cast_array(val, "int64"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.size();",
        "    %s.clear(); %s.reserve((size_t)_n);" % (buf, buf),
        "    for (int64_t _i = 0; _i < _n; ++_i) "
        "%s.push_back((int)(*_o.data)[_i]);" % buf,
        "}",
    ]


def _geo_intscalar_lines(buf, val):
    """Assign int buffer `buf` from a scalar (or 0-d array) nd value."""
    return ["%s = (int)(%s);" % (buf, _scalar_expr(val))]


def _geo_boolscalar_lines(buf, val):
    """Assign int (0/1) buffer `buf` from a scalar nd value (periodic flag)."""
    return ["%s = (%s) ? 1 : 0;" % (buf, _scalar_expr(val))]


def _geo_vec3arr_lines(buf, val):
    """Fill std::vector<MVector> buffer `buf` from an (N,3) nd value. A value
    whose width is not exactly 3 leaves the buffer EMPTY (skipped), matching
    geometry._as_vec_2d(normals, (3,)) -- never an out-of-bounds stride read."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower geo: non-array assigned to vec3 buffer "
                              "%r" % buf)
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.shape.empty() ? 0 : _o.shape[0];",
        "    int64_t _w = _o.shape.size() < 2 ? 0 : _o.shape[1];",
        "    %s.clear();" % buf,
        "    if (_w == 3) {",
        "        %s.reserve((size_t)_n);" % buf,
        "        for (int64_t _i = 0; _i < _n; ++_i)",
        "            %s.push_back(MVector((*_o.data)[_i*3+0], (*_o.data)[_i*3+1], "
        "(*_o.data)[_i*3+2]));" % buf,
        "    }",
        "}",
    ]


def _geo_colorarr_lines(buf, val):
    """Fill std::vector<MColor> buffer `buf` from an (N,3) or (N,4) nd value.
    Width is read at runtime; RGB (3-wide) gets alpha 1.0 -- matching
    geometry._apply_mesh_colors' RGB->RGBA normalisation."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower geo: non-array assigned to color buffer "
                              "%r" % buf)
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.shape.empty() ? 0 : _o.shape[0];",
        "    int64_t _w = _o.shape.size() < 2 ? 0 : _o.shape[1];",
        "    %s.clear();" % buf,
        # width must be 3 (RGB) or 4 (RGBA); anything else leaves the buffer
        # empty (skipped), matching geometry._as_vec_2d(colors, (3, 4)) and
        # avoiding an out-of-bounds stride read.
        "    if (_w == 3 || _w == 4) {",
        "        %s.reserve((size_t)_n);" % buf,
        "        for (int64_t _i = 0; _i < _n; ++_i) {",
        "            double _r = (*_o.data)[_i*_w+0];",
        "            double _g = (*_o.data)[_i*_w+1];",
        "            double _b = (*_o.data)[_i*_w+2];",
        "            double _a = (_w >= 4) ? (*_o.data)[_i*_w+3] : 1.0;",
        "            %s.push_back(MColor((float)_r, (float)_g, (float)_b, "
        "(float)_a));" % buf,
        "        }",
        "    }",
        "}",
    ]


def _geo_doublearr_lines(buf, val):
    """Fill std::vector<double> buffer `buf` from a 1-D nd value (knot vector)."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower geo: non-array assigned to double buffer "
                              "%r" % buf)
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = _o.size();",
        "    %s.clear(); %s.reserve((size_t)_n);" % (buf, buf),
        "    for (int64_t _i = 0; _i < _n; ++_i) "
        "%s.push_back((*_o.data)[_i]);" % buf,
        "}",
    ]


def _geo_writer(buf, btype):
    if btype == "mpoint_arr":
        return lambda val: _geo_mpoint_lines(buf, val)
    if btype == "int_arr":
        return lambda val: _geo_intarr_lines(buf, val)
    if btype == "int_scalar":
        return lambda val: _geo_intscalar_lines(buf, val)
    if btype == "bool_scalar":
        return lambda val: _geo_boolscalar_lines(buf, val)
    if btype == "vec3_arr":
        return lambda val: _geo_vec3arr_lines(buf, val)
    if btype == "color_arr":
        return lambda val: _geo_colorarr_lines(buf, val)
    if btype == "double_arr":
        return lambda val: _geo_doublearr_lines(buf, val)
    raise UnsupportedSpec("nd_lower geo: unknown buffer kind %r" % btype)


def _rewrite_geo_constructor(source, kind):
    """Rewrite ``self.<outAttr> = <Ctor>(...)`` (a Mesh / NurbsCurve /
    NurbsSurface dataclass construction) into synthetic ``self.<field> = <expr>``
    buffer writes so the existing buffer-fill machinery lowers it unchanged.

    Only the *canonical constructor by name* is recognised (spec: the native
    boundary is explicit). A ``build_default_output(...)`` assign is left intact
    (``_strip_geo_output_assign`` handles it). A ``None`` argument is dropped (it
    means "channel absent" -- the emitter default). A ``self.<field>`` argument
    whose name matches its target field (e.g. ``Mesh(points=self.points)``) is
    also dropped: the buffer already holds that value from the compute's own
    ``self.<field> = ...`` write, so re-emitting ``self.points = (self.points)``
    would read a write-only output buffer and fail to lower. Positional args map
    by the field order in ``_GEO_CTOR_POSITIONAL``; keyword args map by name.

    The ctor statement's lines are blanked and the synthetic assigns appended at
    the END of the source (every referenced local is in scope by then). Returns
    the source unchanged if no such constructor is present."""
    cls = _GEO_CTOR_CLASS[kind]
    out_attr = _GEO_OUT_ATTR[kind]
    positional = _GEO_CTOR_POSITIONAL[kind]
    tree = ast.parse(source)
    lines = source.splitlines()
    appended = []
    hit = False

    def _is_none(node):
        return isinstance(node, ast.Constant) and node.value is None

    for st in tree.body:
        tgt = None
        if isinstance(st, ast.Assign) and len(st.targets) == 1:
            tgt = st.targets[0]
        elif isinstance(st, ast.AnnAssign):
            tgt = st.target
        if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "self" and tgt.attr == out_attr):
            continue
        val = st.value
        if not (isinstance(val, ast.Call) and isinstance(val.func, ast.Name)
                and val.func.id == cls):
            continue                    # not the canonical ctor (leave for strip)

        assigns = []
        for i, arg in enumerate(val.args):
            if isinstance(arg, ast.Starred):
                raise UnsupportedSpec("nd_lower geo: *args ctor not lowerable")
            if i >= len(positional):
                raise UnsupportedSpec("nd_lower geo: too many positional ctor "
                                      "args for %s" % cls)
            if _is_none(arg):
                continue
            seg = ast.get_source_segment(source, arg)
            if seg is None:
                raise UnsupportedSpec("nd_lower geo: cannot extract ctor arg src")
            if seg.strip() == "self.%s" % positional[i]:
                continue                # identity: buffer already holds this value
            assigns.append("self.%s = (%s)" % (positional[i], seg))
        for kw in val.keywords:
            if kw.arg is None:
                raise UnsupportedSpec("nd_lower geo: **kwargs ctor not lowerable")
            if _is_none(kw.value):
                continue
            seg = ast.get_source_segment(source, kw.value)
            if seg is None:
                raise UnsupportedSpec("nd_lower geo: cannot extract ctor kwarg src")
            if seg.strip() == "self.%s" % kw.arg:
                continue                # identity: buffer already holds this value
            assigns.append("self.%s = (%s)" % (kw.arg, seg))

        a, b = st.lineno, getattr(st, "end_lineno", st.lineno)
        for ln in range(a, b + 1):
            if 1 <= ln <= len(lines):
                lines[ln - 1] = ""
        appended.extend(assigns)
        hit = True

    if not hit:
        return source
    return "\n".join(lines) + "\n" + "\n".join(appended) + "\n"


def _strip_geo_output_assign(source, out_attr):
    """Blank any top-level ``self.<out_attr> = ...`` (the build_default_output
    step codegen reproduces natively). Line numbers are preserved (lines are
    emptied, not removed) so transpiler error messages stay accurate."""
    tree = ast.parse(source)
    strip = []
    for st in tree.body:
        tgt = None
        if isinstance(st, ast.Assign) and len(st.targets) == 1:
            tgt = st.targets[0]
        elif isinstance(st, ast.AnnAssign):
            tgt = st.target
        if (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "self" and tgt.attr == out_attr):
            strip.append((st.lineno, getattr(st, "end_lineno", st.lineno)))
    if not strip:
        return source
    lines = source.splitlines()
    for (a, b) in strip:
        for ln in range(a, b + 1):
            if 1 <= ln <= len(lines):
                lines[ln - 1] = ""
    return "\n".join(lines)


def lower_geo_compute(in_members, kind, source, init=None):
    """Lower a geometry-generator compute to buffer-fill C++, or raise.

    in_members : codegen input descriptor dicts (user INPUT attrs only -- the
                 geo output is synthesised by the emitter, not in the spec).
    kind       : "mesh" | "curve" | "surface".
    source     : the Python compute block. Its trailing
                 ``self.<geoOut> = build_default_output(...)`` is stripped; the
                 remaining ``self.<buffer> = expr`` writes fill the emitter's
                 flat buffers (points/counts/indices | cvs/degree | ...).
    init       : optional helper source; its top-level `def`s the compute calls
                 are lowered to C++ lambdas emitted ahead of the body. A single
                 source string OR a list of sources (INIT-tier + followed
                 external helper units; see _combined_helper_source).
    Returns indent-1 C++ lines: input materialisation, hoisted decls, helper
    lambdas, then the transpiled buffer-fill body.
    """
    if kind not in _GEO_BUFFERS:
        raise UnsupportedSpec("nd_lower geo: unknown kind %r" % kind)
    # Strip any interpreted-side eager-evaluation guard before lowering.
    source = _strip_eager_guard(source)
    # Rewrite a canonical dataclass ctor (self.outX = Mesh(...)) into synthetic
    # buffer writes, THEN strip any remaining build_default_output(...) assign.
    src = _rewrite_geo_constructor(source, kind)
    src = _strip_geo_output_assign(src, _GEO_OUT_ATTR[kind])

    # Geometry INPUT read surface: a generator may read from a mesh/curve/surface
    # INPUT (single via in_<member> MFn*, or ARRAY via std::vector<Nd<Kind>>
    # in_<member> -- emit_geo emits both). Bind each read channel before the numeric
    # input loop (which has no geo case).
    src, geo_env, geo_materialise = _geo_input_surface(
        in_members, src, allow_geo_array=True)

    used = _used_self_attrs(src)
    env = dict(geo_env)
    materialise = list(geo_materialise)
    in_by_plug = {i["plug"]: i for i in in_members}
    for plug in sorted(used):             # sorted(): see lower_compute
        m = in_by_plug.get(plug)
        if m is None:
            continue                      # not an input (a buffer write, etc.)
        lines, typ = _materialise_input(m, env_cpp_name("self." + plug))
        materialise += lines
        env["self." + plug] = typ

    bufmap = _GEO_BUFFERS[kind]
    writers = {"self." + attr: _geo_writer(buf, bt)
               for attr, (buf, bt) in bufmap.items()}

    res, written, helper_lines = py_to_cpp.transpile_compute_block(
        src, env, writers, init)

    filled = {bufmap[d.split(".", 1)[1]][0] for d in written}
    missing = [b for b in _GEO_REQUIRED_BUFS[kind] if b not in filled]
    if missing:
        raise UnsupportedSpec("nd_lower geo: buffers never filled: %s"
                              % ", ".join(missing))

    return (materialise + list(res.decl_lines) + list(helper_lines)
            + list(res.body_lines))


def try_lower_geo_compute(in_members, kind, spec):
    """Attempt to lower a geo generator's spec['compute']; C++ lines or None.

    None -> codegen keeps the AI-porter PORT region (zero regression)."""
    source = spec.get("compute")
    if not source or not source.strip():
        return None
    try:
        return lower_geo_compute(in_members, kind, source,
                                 _combined_helper_source(spec))
    except UnsupportedSpec:
        return None


# ---- geometry I/O lowering (#83): a PLAIN MPxNode whose OUTPUT(s) are geo -- a
# single geo output built from a Mesh/NurbsCurve/NurbsSurface ctor or copied from
# an array geo input element, and/or an ARRAY (list) geo output that is a whole
# passthrough of an array geo input or a fixed-length list of same-kind items.
# The value model is the emit_geo_io Nd<Kind> struct, NOT the numeric nd:: model.
# Support is scoped to the tractable, verifiable patterns; anything else raises
# -> try_lower_compute returns None -> the AI porter fills the same struct
# scaffold (still pure C++). Field expressions ARE lowered through the numeric
# transpiler (so ``Mesh(points=self.inMesh.points * 2, ...)`` works), reusing
# _geo_input_surface for single AND array geo channel reads.
def _geo_mpoint_flat_lines(buf, val):
    """Fill std::vector<MPoint> `buf` from an (N,3) OR (nu,nv,3) nd value. Count
    is the flat element total / 3, so a surface CV grid flattens U-major (matches
    the interpreted NurbsSurface flat-CV marshalling)."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower geo-io: non-array assigned to point buffer")
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _n = (int64_t)(_o.data ? _o.data->size() / 3 : 0);",
        "    %s.clear(); %s.reserve((size_t)_n);" % (buf, buf),
        "    for (int64_t _i = 0; _i < _n; ++_i)",
        "        %s.push_back(MPoint((*_o.data)[_i*3+0], (*_o.data)[_i*3+1], "
        "(*_o.data)[_i*3+2]));" % buf,
        "}",
    ]


# dataclass ctor field -> (Nd<Kind> struct field, buffer kind). "mpoint_arr_flat"
# uses the flat writer above (surface CV grid).
_GEOIO_FIELDS = {
    "mesh": {
        "points": ("points", "mpoint_arr"), "counts": ("counts", "int_arr"),
        "indices": ("indices", "int_arr"), "normals": ("normals", "vec3_arr"),
        "normal_indices": ("normalIndices", "int_arr"),
        "colors": ("colors", "color_arr"),
        "color_indices": ("colorIndices", "int_arr"),
    },
    "curve": {
        "points": ("cvs", "mpoint_arr"), "cvs": ("cvs", "mpoint_arr"),
        "degree": ("degree", "int_scalar"), "periodic": ("periodic", "bool_scalar"),
        "kv": ("knots", "double_arr"), "knots": ("knots", "double_arr"),
    },
    "surface": {
        "points": ("cvs", "mpoint_arr_flat"), "cvs": ("cvs", "mpoint_arr_flat"),
        "num_cvs_u": ("numU", "int_scalar"), "num_cvs_v": ("numV", "int_scalar"),
        "num_u": ("numU", "int_scalar"), "num_v": ("numV", "int_scalar"),
        "degree_u": ("degreeU", "int_scalar"), "degree_v": ("degreeV", "int_scalar"),
        "periodic_u": ("periodicU", "bool_scalar"),
        "periodic_v": ("periodicV", "bool_scalar"),
        "kv_u": ("knotsU", "double_arr"), "kv_v": ("knotsV", "double_arr"),
        "knots_u": ("knotsU", "double_arr"), "knots_v": ("knotsV", "double_arr"),
    },
}
# struct fields that MUST be filled for a single-geo ctor to lower (others take
# the struct default: curve/surface degree=3, open form, uniform knots).
_GEOIO_REQUIRED = {"mesh": ["points", "counts", "indices"],
                   "curve": ["cvs"], "surface": ["cvs", "numU", "numV"]}
_GEOIO_SYN_PREFIX = "__geoio_"


def _geoio_writer(struct_var, structfield, btype):
    buf = "%s.%s" % (struct_var, structfield)
    if btype == "mpoint_arr":
        return lambda val: _geo_mpoint_lines(buf, val)
    if btype == "mpoint_arr_flat":
        return lambda val: _geo_mpoint_flat_lines(buf, val)
    if btype == "int_arr":
        return lambda val: _geo_intarr_lines(buf, val)
    if btype == "int_scalar":
        return lambda val: _geo_intscalar_lines(buf, val)
    if btype == "bool_scalar":
        return lambda val: _geo_boolscalar_lines(buf, val)
    if btype == "vec3_arr":
        return lambda val: _geo_vec3arr_lines(buf, val)
    if btype == "color_arr":
        return lambda val: _geo_colorarr_lines(buf, val)
    if btype == "double_arr":
        return lambda val: _geo_doublearr_lines(buf, val)
    raise UnsupportedSpec("nd_lower geo-io: unknown buffer kind %r" % btype)


def _geoio_ctor_writes(source, call, kind, struct_var, syn_base, writers, label):
    """Rewrite a geo dataclass ctor CALL into synthetic ``self.<syn> = (<field
    expr>)`` assigns whose writers fill ``struct_var``'s Nd<Kind> fields.

    Shared by the SINGLE geo output and by each ctor item of an ARRAY geo output
    list literal (whose ``struct_var`` is an ``out_<m>[k]`` element), so both
    model a ctor identically. ``syn_base`` disambiguates the synthetic attr names
    between elements. Returns the synthetic assign source lines; raises
    UnsupportedSpec for a non-ctor / unlowerable / incomplete ctor."""
    cls = _GEO_CTOR_CLASS[kind]
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == cls):
        raise UnsupportedSpec("nd_lower geo-io: %s must be a %s(...) constructor"
                              % (label, cls))
    positional = _GEO_CTOR_POSITIONAL[kind]
    fld_map = _GEOIO_FIELDS[kind]
    assigns = []
    for i, arg in enumerate(call.args):
        if isinstance(arg, ast.Starred) or i >= len(positional):
            raise UnsupportedSpec("nd_lower geo-io: bad positional ctor args")
        fname = positional[i]
        if isinstance(arg, ast.Constant) and arg.value is None:
            continue
        assigns.append((fname, ast.get_source_segment(source, arg)))
    for kw in call.keywords:
        if kw.arg is None:
            raise UnsupportedSpec("nd_lower geo-io: **kwargs ctor not lowerable")
        if isinstance(kw.value, ast.Constant) and kw.value.value is None:
            continue
        assigns.append((kw.arg, ast.get_source_segment(source, kw.value)))
    # emit a synthetic write per field, register its struct-field writer.
    appended = []
    filled = set()
    for fname, seg in assigns:
        if fname not in fld_map:
            raise UnsupportedSpec("nd_lower geo-io: ctor field %r not lowerable "
                                  "for %s" % (fname, kind))
        if seg is None:
            raise UnsupportedSpec("nd_lower geo-io: cannot extract ctor arg src")
        structfield, btype = fld_map[fname]
        syn = "%s%s_%s_" % (_GEOIO_SYN_PREFIX, syn_base, structfield)
        appended.append("self.%s = (%s)" % (syn, seg))
        writers["self." + syn] = _geoio_writer(struct_var, structfield, btype)
        filled.add(structfield)
    miss = [b for b in _GEOIO_REQUIRED[kind] if b not in filled]
    if miss:
        raise UnsupportedSpec("nd_lower geo-io: %s missing required field(s) %s"
                              % (label, ", ".join(miss)))
    return appended


def _geoio_elem_copy(dst, member, index):
    """Struct copy of ARRAY geo INPUT element ``in_<member>[index]`` into the
    ``dst`` Nd<Kind> lvalue (index resolved by the shared _geo_arr_at, so a
    negative one counts from the end). Bounds-safe: an out-of-range index leaves
    ``dst`` default-constructed (empty geometry), the same missing-multi-element
    convention _materialise_geo_array_channel uses on the read side."""
    e, ok = _geo_arr_at("in_" + member, index)
    return ["    if (%s) %s = %s;" % (ok, dst, e)]


def lower_geo_io_compute(ins, outs, source, init=None):
    """Lower a plain-node geo-OUTPUT compute to C++ that fills the emit_geo_io
    ``out_<m>`` buffers, or raise UnsupportedSpec.

    Supported patterns:
      * array (list) geo output whole passthrough: ``self.<arrOut> =
        self.<arrIn>`` (same kind) -> ``out_<o> = in_<i>;`` (struct-vector copy).
      * array (list) geo output FIXED-LENGTH list/tuple literal: ``self.<arrOut> =
        [<item>, <item>, ...]`` -> ``out_<o>.resize(N);`` then one item write per
        slot. Each item is either a same-kind ctor (lowered like a single geo
        output, into ``out_<o>[k]``) or a same-kind ARRAY geo INPUT element
        ``self.<arrIn>[<const int>]`` (struct copy). The literal's length is the
        element count, so slot k lands on logical index k -- what the interpreted
        ``write_multi_plug_value`` does with the same list.
      * single geo output ctor: ``self.<out> = Mesh(points=..., counts=...,
        indices=...)`` (resp. NurbsCurve / NurbsSurface) -> the field expressions
        are lowered through the numeric transpiler (reusing the geo-INPUT read
        surface) and written into the ``out_<m>`` struct fields.
      * single geo output passthrough of an ARRAY geo input ELEMENT:
        ``self.<out> = self.<arrIn>[<const int>]`` (same kind) -> struct copy.
    Any other geo-output shape (mixed geo+numeric outputs, an elementwise/
    comprehension list build, a bare non-ctor value) raises -> AI porter.
    """
    geo_out_by_plug = {o["plug"]: o for o in outs
                       if o["meta"]["type"] in _GEO_IN_TYPE_KIND}
    if not geo_out_by_plug:
        raise UnsupportedSpec("nd_lower geo-io: no geo output")
    if len(geo_out_by_plug) != len(outs):
        raise UnsupportedSpec("nd_lower geo-io: mixed geo + numeric outputs")

    geo_in_by_plug = {i["plug"]: i for i in ins
                      if i["meta"]["type"] in _GEO_IN_TYPE_KIND}
    # ARRAY geo inputs, keyed as _geo_arr_elem wants them, so an
    # ``self.<arrIn>[<const int>]`` passthrough item is matched by the SAME
    # element matcher the read surface uses.
    geo_arr_in = {i["plug"]: (i["member"], _GEO_IN_TYPE_KIND[i["meta"]["type"]])
                  for i in ins if _is_geo_array_input(i["meta"])}
    # Strip any interpreted-side eager-evaluation guard before lowering.
    source = _strip_eager_guard(source)
    tree = ast.parse(source)
    lines = source.splitlines()
    passthru = []            # raw C++ (array struct-vector copies)
    written = set()          # geo output plugs satisfied
    writers = {}             # self.<syn> -> writer callable
    syn_env_needed = False
    # Per output plug, the FORM of each assignment: "direct" (all of its C++ goes
    # into passthru, ahead of the body), "body" (a ctor, all of it emitted by the
    # transpiler) or "split" (a list literal with ctor items: both). Re-assigning
    # ONE output across different forms is rejected below -- passthru is emitted
    # ahead of the body wholesale, so last-write-wins would not match Python.
    write_forms = {}

    for st in list(tree.body):
        tgt = st.targets[0] if (isinstance(st, ast.Assign)
                                and len(st.targets) == 1) else None
        if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "self" and tgt.attr in geo_out_by_plug):
            continue
        o = geo_out_by_plug[tgt.attr]
        kind = _GEO_IN_TYPE_KIND[o["meta"]["type"]]
        val = st.value

        # Same-kind ARRAY geo input elements are the passthrough item vocabulary
        # for BOTH a single geo output and each slot of an array geo output.
        same_kind_arr = {p: v for p, v in geo_arr_in.items()
                         if geo_in_by_plug[p]["meta"]["type"] == o["meta"]["type"]}
        appended = []

        if o["meta"].get("is_array"):
            # (a) whole passthrough of a same-kind array geo INPUT.
            if (isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name)
                    and val.value.id == "self" and val.attr in geo_in_by_plug
                    and geo_in_by_plug[val.attr]["meta"].get("is_array")
                    and geo_in_by_plug[val.attr]["meta"]["type"] == o["meta"]["type"]):
                src_m = geo_in_by_plug[val.attr]["member"]
                passthru.append("    out_%s = in_%s;" % (o["member"], src_m))
                _blank_stmt(lines, st)
                written.add(o["plug"])
                write_forms.setdefault(o["plug"], []).append("direct")
                continue
            # (b) fixed-length list/tuple literal: one ctor or element passthrough
            # per slot. The slot count is known at compile time, so the vector is
            # resized up front and each slot written independently.
            if not isinstance(val, (ast.List, ast.Tuple)):
                raise UnsupportedSpec(
                    "nd_lower geo-io: array geo output %r must be a whole "
                    "passthrough of a same-kind array geo input or a "
                    "fixed-length list of same-kind items" % o["plug"])
            passthru.append("    out_%s.resize(%d);" % (o["member"], len(val.elts)))
            for k, item in enumerate(val.elts):
                dst = "out_%s[%d]" % (o["member"], k)
                el = _geo_arr_elem(item, same_kind_arr)
                if el is not None:
                    passthru += _geoio_elem_copy(dst, same_kind_arr[el[0]][0], el[1])
                    continue
                appended += _geoio_ctor_writes(
                    source, item, kind, dst, "%s_%d" % (o["member"], k), writers,
                    "array geo output %r item %d" % (o["plug"], k))
                syn_env_needed = True
        else:
            # (c) single geo output = a same-kind ARRAY geo input ELEMENT (struct
            # copy), else (d) the canonical ctor by name.
            el = _geo_arr_elem(val, same_kind_arr)
            if el is not None:
                passthru += _geoio_elem_copy("out_" + o["member"],
                                             same_kind_arr[el[0]][0], el[1])
                _blank_stmt(lines, st)
                written.add(o["plug"])
                write_forms.setdefault(o["plug"], []).append("direct")
                continue
            appended = _geoio_ctor_writes(
                source, val, kind, "out_" + o["member"], o["member"], writers,
                "single geo output %r" % o["plug"])
            syn_env_needed = True

        _blank_stmt(lines, st)
        # append synthetic assigns at the end (every referenced local in scope).
        if appended:
            lines.append("")
            lines.extend(appended)
        written.add(o["plug"])
        if not appended:
            form = "direct"
        else:
            form = "split" if o["meta"].get("is_array") else "body"
        write_forms.setdefault(o["plug"], []).append(form)

    missing = [p for p in geo_out_by_plug if p not in written]
    if missing:
        raise UnsupportedSpec("nd_lower geo-io: output(s) not written: %s"
                              % ", ".join(sorted(missing)))
    # Repeats of ONE form keep their relative order (all-passthru or all-body), so
    # last-write-wins still holds; anything else would reorder the writes.
    mixed = sorted(p for p, f in write_forms.items()
                   if len(f) > 1 and (len(set(f)) > 1 or f[0] == "split"))
    if mixed:
        raise UnsupportedSpec("nd_lower geo-io: output(s) %s re-assigned in mixed "
                              "forms (struct copy / list literal / constructor); "
                              "the copies are emitted ahead of the transpiled body, "
                              "so the final value would not match Python"
                              % ", ".join(mixed))

    source2 = "\n".join(lines)

    # geometry-INPUT read surface for the ctor field expressions: SINGLE geo ins
    # (``self.<geoIn>.<channel>``, bound off the emitter's in_<m> MFn*) AND ARRAY
    # geo ins (``self.<geoArr>[i].<channel>``, bound off its std::vector<Nd<Kind>>
    # in_<m>). emit_compute declares BOTH for a plain MPxNode, which is the only
    # family this lowerer serves, so it opts into array-geo like lower_compute.
    source2, geo_env, geo_materialise = _geo_input_surface(
        ins, source2, allow_geo_array=True)

    # materialise the numeric inputs the (rewritten) field expressions use.
    env = dict(geo_env)
    materialise = list(geo_materialise)
    if syn_env_needed:
        used = _used_self_attrs(source2)
        in_by_plug = {i["plug"]: i for i in ins}
        for plug in sorted(used):         # sorted(): see lower_compute
            m = in_by_plug.get(plug)
            if m is None:
                continue
            ls, typ = _materialise_input(m, env_cpp_name("self." + plug))
            materialise += ls
            env["self." + plug] = typ
        res, wrote, helper_lines = py_to_cpp.transpile_compute_block(
            source2, env, writers, init)
        body = (materialise + list(res.decl_lines) + list(helper_lines)
                + list(res.body_lines))
    else:
        body = []

    return passthru + body


def _blank_stmt(lines, st):
    """Blank a statement's source lines in-place (preserve line numbers)."""
    a, b = st.lineno, getattr(st, "end_lineno", st.lineno)
    for ln in range(a, b + 1):
        if 1 <= ln <= len(lines):
            lines[ln - 1] = ""


# ---- deformer lowering (deform(): getPoints/setPoints on outputGeometry) ---
# The deformer compute contract (see _api1/mpy_deformer.py) is:
#
#     mesh = self.outputGeometry[<i>]   # writable MFnMesh proxy for geometry <i>
#     rest = mesh.getPoints()           # (N,3) float64 numpy of object-space pts
#     ... pure-numeric per-vertex math over rest / self.envelope / user inputs ...
#     mesh.setPoints(deformed)          # write the (M,3) result back
#
# codegen's _deform_lines already harvests the CURRENT geometry into an
# MPointArray ``pts`` (length ``n``) via ``iter.allPositions`` and, after the
# port region, commits it with ``iter.setAllPositions``. nd_lower lowers the
# numeric middle by rewriting the mesh-proxy idiom into transpiler-friendly
# self-attr forms:
#
#   * ``<mesh> = self.outputGeometry[<const>]``  -> blanked (mesh var recorded)
#   * ``<rest> = <mesh>.getPoints()``            -> ``<rest> = self.__ndpoints__``
#   * ``<mesh>.setPoints(<expr>)``               -> ``self.__ndout__ = (<expr>)``
#
# A NURBS deformer (mPyDeformer on a curve/surface) reads/writes CVs
# via ``cvPositions()`` / ``setCVPositions(<expr>)`` instead. Those are accepted
# as exact aliases of getPoints/setPoints: ``iter.allPositions`` returns the CVs
# in the same order MFnNurbs*::cvPositions does, so the lowered body is identical.
#
# then binding ``self.__ndpoints__`` to an (N,3) nd::Array materialised from
# ``pts``, ``self.envelope`` to the C++ ``env`` float, and user inputs as usual;
# the ``self.__ndout__`` writer scatters the produced (M,3) value back into
# ``pts``. Anything outside this shape (skin weightList reads, input-mesh reads,
# matrix ``.asNumpy()``, unsupported ops) rejects -> AI porter (zero regression).

# Synthetic self-attrs the rewrite introduces (never real plugs, so they can't
# collide with a user input/output name).
_DEFORM_POINTS_ATTR = "__ndpoints__"   # harvested rest points, bound (N,3)
_DEFORM_OUT_ATTR = "__ndout__"         # setPoints target, scattered back to pts
_DEFORM_NORMALS_ATTR = "__ndnormals__"  # per-vertex normals, bound (N,3)


def _deform_normals_materialise(dst, angle_weighted, space):
    """Emit C++ (indent-1) binding an (N,3) nd::Array<double> of per-vertex
    normals, filled from the input-geometry mesh via the SAME averaged-normal
    API the interpreted node calls (``MFnMesh::getVertexNormals``) -> byte-parity
    with the Python ``mesh.getVertexNormals``. Self-contained: uses ``block`` and
    ``multiIndex`` (deform() params in scope where the lowered body is inserted),
    so emit_deformer needs no change. For a full-membership deform the mesh vertex
    order matches ``MItGeometry::allPositions`` order, so normals[i] aligns pts[i]
    (same assumption as the CSR adjacency block)."""
    awc = "true" if angle_weighted else "false"
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        MStatus _nst;",
        "        MArrayDataHandle _nInGeo = block.outputArrayValue("
        "MPxGeometryFilter::input, &_nst);",
        "        MFloatVectorArray _nrm;",
        "        if (_nst == MS::kSuccess && "
        "_nInGeo.jumpToElement(multiIndex) == MS::kSuccess) {",
        "            MObject _nMeshObj = _nInGeo.outputValue().child("
        "MPxGeometryFilter::inputGeom).asMesh();",
        "            if (!_nMeshObj.isNull() && _nMeshObj.hasFn(MFn::kMesh)) {",
        "                MFnMesh(_nMeshObj).getVertexNormals(%s, _nrm, "
        "MSpace::%s);" % (awc, space),
        "            }",
        "        }",
        "        std::vector<double> _tmpn; _tmpn.reserve((size_t)_nrm.length() "
        "* 3);",
        "        for (unsigned int _i = 0; _i < _nrm.length(); ++_i) {",
        "            _tmpn.push_back(_nrm[_i].x);",
        "            _tmpn.push_back(_nrm[_i].y);",
        "            _tmpn.push_back(_nrm[_i].z);",
        "        }",
        "        %s = nd::from_data<double>(_tmpn, "
        "{(int64_t)_nrm.length(), 3});" % dst,
        "    }",
    ]


def _deform_points_materialise(dst):
    """Emit C++ (indent-1) binding the harvested ``pts`` MPointArray to an
    (N,3) nd::Array<double> local named ``dst`` (matches the dense (N,3) numpy
    the interpreted deform's ``getPoints()`` returns)."""
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _tmp; _tmp.reserve((size_t)n * 3);",
        "        for (unsigned int _i = 0; _i < n; ++_i) {",
        "            _tmp.push_back(pts[_i].x);",
        "            _tmp.push_back(pts[_i].y);",
        "            _tmp.push_back(pts[_i].z);",
        "        }",
        "        %s = nd::from_data<double>(_tmp, {(int64_t)n, 3});" % dst,
        "    }",
    ]


def _deform_writeback_lines(val):
    """Writer for ``self.__ndout__``: scatter a produced (M,3) nd value back
    into the harvested ``pts`` MPointArray. Only min(M, n) points are written
    (the deform commits exactly the ``n`` harvested slots via setAllPositions)."""
    if not val.type.is_array():
        raise UnsupportedSpec("nd_lower deform: non-array value passed to "
                              "setPoints")
    return [
        "{",
        "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
        "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
        "    int64_t _m = _o.shape.empty() ? 0 : _o.shape[0];",
        "    unsigned int _lim = (_m < (int64_t)n) ? (unsigned int)_m : n;",
        "    for (unsigned int _i = 0; _i < _lim; ++_i)",
        "        pts[_i] = MPoint((*_o.data)[_i*3+0], (*_o.data)[_i*3+1], "
        "(*_o.data)[_i*3+2]);",
        "}",
    ]


def _apply_normals_idiom(tree, source, lines, mesh_vars):
    """Detect the per-vertex-normals idiom and, iff the COMPLETE triple is
    present and supported, rewrite it in place (mutating ``lines``). Returns
    ``{"aw": bool, "space": str}`` when applied, else None (leaving ``lines``
    untouched so the statements pass through and reject to the AI porter -- zero
    regression / never a partial rewrite).

    The idiom (as authored in sine_ripple):
        nrm = om.MFloatVectorArray()
        <mesh>.getVertexNormals(<aw const>, nrm, om.MSpace.k<Space>)
        <normals> = np.array([[nrm[i].x, nrm[i].y, nrm[i].z]
                              for i in range(nrm.length())], dtype=...)
    -> ``<normals> = self.__ndnormals__`` (bound to an (N,3) nd::Array filled by
    MFnMesh::getVertexNormals -- see _deform_normals_materialise)."""

    def _dotted_attr(node):
        # om.MSpace.kObject -> ("MSpace", "kObject"); else None
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Attribute)):
            return node.value.attr, node.attr
        return None

    fva = {}         # MFloatVectorArray var name -> (lineno, end)
    gvn = None       # (var, aw_bool, space_attr, lineno, end)
    conv = None      # (target, lineno, end, indent)
    for st in tree.body:
        end = getattr(st, "end_lineno", st.lineno)
        # nrm = om.MFloatVectorArray()
        if (isinstance(st, ast.Assign) and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
                and isinstance(st.value, ast.Call)
                and isinstance(st.value.func, ast.Attribute)
                and st.value.func.attr == "MFloatVectorArray"
                and not st.value.args and not st.value.keywords):
            fva[st.targets[0].id] = (st.lineno, end)
            continue
        # <mesh>.getVertexNormals(<aw>, nrm, om.MSpace.k<Space>)
        if (gvn is None and isinstance(st, ast.Expr)
                and isinstance(st.value, ast.Call)
                and isinstance(st.value.func, ast.Attribute)
                and isinstance(st.value.func.value, ast.Name)
                and st.value.func.value.id in mesh_vars
                and st.value.func.attr == "getVertexNormals"
                and len(st.value.args) == 3 and not st.value.keywords):
            aw, nvar, spc = st.value.args
            da = _dotted_attr(spc)
            if (isinstance(aw, ast.Constant) and isinstance(aw.value, bool)
                    and isinstance(nvar, ast.Name) and nvar.id in fva
                    and da is not None and da[0] == "MSpace"):
                gvn = (nvar.id, aw.value, da[1], st.lineno, end)
            continue
        # <normals> = np.array([[nrm[i].x, ...] for i in range(nrm.length())], ...)
        if (conv is None and isinstance(st, ast.Assign) and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
                and isinstance(st.value, ast.Call)
                and isinstance(st.value.func, ast.Attribute)
                and st.value.func.attr == "array"):
            raw = lines[st.lineno - 1]
            indent = raw[:len(raw) - len(raw.lstrip())]
            conv = (st.targets[0].id, st.lineno, end, indent,
                    {n.id for n in ast.walk(st.value)
                     if isinstance(n, ast.Name)})

    # require the COMPLETE, consistent triple (same MFloatVectorArray var)
    if gvn is None or conv is None:
        return None
    nvar, aw, space, g_lo, g_hi = gvn
    tgt, c_lo, c_hi, indent, c_names = conv
    if nvar not in fva or nvar not in c_names:
        return None

    def _blank(a, b):
        for ln in range(a, b + 1):
            if 1 <= ln <= len(lines):
                lines[ln - 1] = ""

    f_lo, f_hi = fva[nvar]
    _blank(f_lo, f_hi)             # nrm = om.MFloatVectorArray()
    _blank(g_lo, g_hi)             # mesh.getVertexNormals(...)
    _blank(c_lo, c_hi)            # the np.array(...) conversion
    lines[c_lo - 1] = "%s%s = self.%s" % (indent, tgt, _DEFORM_NORMALS_ATTR)
    return {"aw": aw, "space": space}


# ---- mPyBlendShape ``self.morphs`` OBJECT surface -> blessed METHOD calls.
# The MorphStack object (``_api2/morph.py``) is a Python-side affordance and the
# transpiler has no object model at all (no classes, dunders or dicts), so the
# object is ERASED here exactly the way ``_rewrite_geo_reads`` erases
# Mesh/NurbsCurve/NurbsSurface: each recognised member becomes the blessed
# ``Transpile`` method that already lowers, and the object never reaches
# py_to_cpp.
#
# Every rewrite is 1:1 with a MorphStack member, so interpreted and compiled run
# the SAME kernel -- MorphStack.apply() calls morph_blend.apply_morphs, and
# self.morph_apply lowers by transpiling that same function. Each argument
# expression is passed through exactly ONCE (this is why ``apply`` has its own
# kernel rather than being composed here: composing would emit ``base`` twice,
# and ``base`` is typically ``mesh.getPoints()``).
_MORPH_PROP = "morphs"

# MorphStack member -> (blessed method, min args, max args). Pinned against the
# registry by a test so a renamed method cannot silently stop being reachable.
_MORPH_CALLS = {
    "deltas": ("morph_deltas", 1, 2),
    "apply": ("morph_apply", 1, 2),
}

# A const string sequence unrolls its loop body once per element. 40 correctives
# on a face rig is plausible; a nested pair over the same list is 1600 copies and
# is not. Counted in EMITTED STATEMENTS, so nesting multiplies the way it really
# does. Cap it and say so -- silently truncating would compile a node that
# quietly ignores most of its targets.
_MORPH_UNROLL_CAP = 256


def _is_morphs(node):
    """True for the ``self.morphs`` attribute node."""
    return (isinstance(node, ast.Attribute)
            and node.attr == _MORPH_PROP
            and isinstance(node.value, ast.Name)
            and node.value.id == "self")


# ---- Const-string folding, so a NAME key can reach a compile-time slot.
# `key = 'browUp'` already lowers to a real `std::string` local, and py_to_cpp
# tracks name -> TYPE, never name -> VALUE. So a string local is a genuine
# runtime value that can differ per branch:
#
#     key = 'browUp'
#     if float(self.envelope) > 0.5:
#         key = 'mouthOpen'
#
# Folding that to a constant would silently drive the wrong shape. The rule is
# therefore PROVE, not assume: a name is foldable only when the whole compute
# binds it exactly once, at top level, from string literals, and never mutates
# it. Anything else keeps its runtime form and honest-rejects at the key site.
def _target_names(t):
    """Every NAME an assignment target binds (attribute/subscript targets bind
    none -- they mutate an object, they do not rebind an identifier)."""
    if isinstance(t, ast.Name):
        return [t.id]
    if isinstance(t, (ast.Tuple, ast.List)):
        out = []
        for e in t.elts:
            out += _target_names(e)
        return out
    if isinstance(t, ast.Starred):
        return _target_names(t.value)
    return []


def _bound_names(node):
    """Every name bound by this single node, across EVERY binding construct.

    Enumerated exhaustively on purpose: a binding form missed here reads as
    "bound once" and the fold silently uses a stale value."""
    if isinstance(node, ast.Assign):
        out = []
        for t in node.targets:
            out += _target_names(t)
        return out
    if isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
        return _target_names(node.target)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return _target_names(node.target)
    if isinstance(node, (ast.With, ast.AsyncWith)):
        out = []
        for it in node.items:
            if it.optional_vars is not None:
                out += _target_names(it.optional_vars)
        return out
    if isinstance(node, ast.comprehension):
        return _target_names(node.target)
    if isinstance(node, ast.ExceptHandler):
        return [node.name] if node.name else []
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        a = node.args
        out = [node.name]
        for arg in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
            out.append(arg.arg)
        if a.vararg:
            out.append(a.vararg.arg)
        if a.kwarg:
            out.append(a.kwarg.arg)
        return out
    if isinstance(node, ast.ClassDef):
        return [node.name]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [(al.asname or al.name.split(".")[0]) for al in node.names]
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return list(node.names)
    if isinstance(node, ast.Delete):
        out = []
        for t in node.targets:
            out += _target_names(t)
        return out
    return []


_SEQ_MUTATORS = frozenset({"append", "extend", "insert", "pop", "clear",
                           "sort", "reverse", "remove", "__setitem__"})


def _mutated_names(tree):
    """Names reached by an in-place mutation -- ``NAMES[0] = x``, ``NAMES.append``.

    These bind no identifier, so the binding count above cannot see them."""
    out = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                and isinstance(n.ctx, (ast.Store, ast.Del))):
            out.add(n.value.id)
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.attr in _SEQ_MUTATORS):
            out.add(n.func.value.id)
    return out


def _const_str_literal(node):
    """A str literal, or a tuple/list of them -- else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        vals = []
        for e in node.elts:
            if not (isinstance(e, ast.Constant) and isinstance(e.value, str)):
                return None
            vals.append(e.value)
        return tuple(vals)
    return None


def _const_str_env(tree):
    """name -> str (3a) or tuple[str] (3b) for every PROVABLY constant binding."""
    counts = {}
    for n in ast.walk(tree):
        for nm in _bound_names(n):
            counts[nm] = counts.get(nm, 0) + 1
    mutated = _mutated_names(tree)

    env = {}
    for stmt in tree.body:                      # top level only, never nested
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
            continue
        tgt = stmt.targets[0]
        if not isinstance(tgt, ast.Name):
            continue
        if counts.get(tgt.id) != 1 or tgt.id in mutated:
            continue
        val = _const_str_literal(stmt.value)
        if val is not None:
            env[tgt.id] = val
    return env, counts


def _const_str_of(node, env):
    """The compile-time string this expression denotes, or None.

    Recognised: a literal, a folded scalar name (3a), and a folded sequence
    subscripted by an integer literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        v = env.get(node.id)
        return v if isinstance(v, str) else None
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)
            and not isinstance(node.slice.value, bool)):
        seq = env.get(node.value.id)
        if isinstance(seq, tuple) and 0 <= node.slice.value < len(seq):
            return seq[node.slice.value]
    return None


class _SlotCollector(ast.NodeVisitor):
    """Ordered DISTINCT name keys reached through ``self.morphs[...]``.

    Deliberately separate from the rewrite and deliberately unable to reject:
    the interpreted node resolves names through this same ordering, and it may
    legitimately use MorphStack members that have no compiled form at all. If
    collection shared the rewrite's rejects, one authoring-only call would empty
    the slot table and break name lookup on a node that runs perfectly well.

    ``generic_visit`` is depth-first pre-order, so this is SOURCE order over the
    already-unrolled tree -- deterministic, and stable when unrelated code moves.
    """

    def __init__(self, env):
        self._env = env
        self.slots = []

    def visit_Attribute(self, node):
        if (node.attr == "weight" and isinstance(node.value, ast.Subscript)
                and _is_morphs(node.value.value)):
            nm = _const_str_of(node.value.slice, self._env)
            if nm is not None and nm not in self.slots:
                self.slots.append(nm)
        self.generic_visit(node)


def _folded_tree(source):
    """``(tree, env, counts)`` after const-folding and loop unrolling.

    The one place the compute is prepared for BOTH slot collection and the
    rewrite, so the two can never see a differently-shaped tree."""
    tree = ast.parse(source)
    env, counts = _const_str_env(tree)
    tree.body = _unroll_const_for(tree.body, env, counts, [0])
    return tree, env, counts


class _SubstName(ast.NodeTransformer):
    """Replace every READ of ``name`` with a string constant."""

    def __init__(self, name, value):
        self._name = name
        self._value = value

    def visit_Name(self, node):
        if node.id == self._name and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Constant(value=self._value), node)
        return node


def _range_unroll_len(node, env, counts):
    """Iteration count for a ``for i in range(...)`` that MUST be unrolled, else 0.

    "Must" is the whole point. ``for i in range(n)`` already lowers to a real C++
    loop, and turning that into N copies would change the shape of code that
    compiles perfectly well today. So this fires only for the one construct that
    cannot survive any other way: a body that subscripts a constant NAME
    sequence with the loop variable (``self.morphs[NAMES[i]]``), where the index
    has to be a compile-time constant for the name to resolve at all.
    """
    if not (isinstance(node, ast.For) and isinstance(node.target, ast.Name)):
        return 0
    it = node.iter
    if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name)
            and it.func.id == "range" and len(it.args) == 1
            and not it.keywords):
        return 0

    # range(<int literal>) or range(len(<const seq>))
    a = it.args[0]
    n = None
    if isinstance(a, ast.Constant) and isinstance(a.value, int) \
            and not isinstance(a.value, bool):
        n = a.value
    elif (isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
          and a.func.id == "len" and len(a.args) == 1
          and isinstance(a.args[0], ast.Name)):
        seq = env.get(a.args[0].id)
        if isinstance(seq, tuple):
            n = len(seq)
    if n is None or n < 0:
        return 0

    var = node.target.id
    needed = False
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
                and isinstance(env.get(sub.value.id), tuple)
                and isinstance(sub.slice, ast.Name)
                and sub.slice.id == var):
            needed = True
            break
    if not needed:
        return 0
    if counts.get(var) != 1:
        raise UnsupportedSpec(
            "nd_lower: '%s' indexes a constant name list but is bound in more "
            "than one place, so the loop cannot be unrolled." % var)
    return n


def _unroll_const_for(body, env, counts, budget):
    """Unroll ``for x in <const str seq>`` into one copy of the body per element.

    Such a loop REJECTS today ("only 'for i in range(...)' is supported"), so
    unrolling can only turn a reject into a compile -- no existing codegen path
    changes shape. Doing it here means py_to_cpp never sees the sequence at all,
    which is why this needs no new string-sequence type in the shared transpiler.
    """
    out = []
    for st in body:
        for field in ("body", "orelse", "finalbody"):
            if hasattr(st, field) and isinstance(getattr(st, field), list):
                setattr(st, field, _unroll_const_for(
                    getattr(st, field), env, counts, budget))
        if isinstance(st, ast.For) and isinstance(st.iter, (ast.Name, ast.Tuple,
                                                            ast.List)):
            seq = (env.get(st.iter.id) if isinstance(st.iter, ast.Name)
                   else _const_str_literal(st.iter))
            if isinstance(seq, tuple):
                if not isinstance(st.target, ast.Name):
                    raise UnsupportedSpec(
                        "nd_lower: a for-loop over a constant name list must "
                        "bind a single plain variable (got a tuple target).")
                if st.orelse:
                    raise UnsupportedSpec(
                        "nd_lower: for/else over a constant name list has no "
                        "compiled form -- drop the else branch.")
                for sub in ast.walk(st):
                    if isinstance(sub, (ast.Break, ast.Continue)):
                        raise UnsupportedSpec(
                            "nd_lower: break/continue inside a for-loop over a "
                            "constant name list cannot be unrolled.")
                if counts.get(st.target.id) != 1:
                    raise UnsupportedSpec(
                        "nd_lower: '%s' is bound in more than one place, so the "
                        "loop over a constant name list cannot be unrolled. Use "
                        "a loop variable that is used nowhere else."
                        % st.target.id)
                # Count what is actually EMITTED. st.body has already been
                # unrolled by the recursion above, so a nested pair multiplies
                # here exactly as it does in the output.
                budget[0] += len(seq) * max(1, len(st.body))
                if budget[0] > _MORPH_UNROLL_CAP:
                    raise UnsupportedSpec(
                        "nd_lower: unrolling constant-name loops would emit "
                        "more than %d statements. Index the weights directly "
                        "(self.morphs.resolved) instead of naming every target."
                        % _MORPH_UNROLL_CAP)
                for val in seq:
                    for inner in st.body:
                        cp = _SubstName(st.target.id, val).visit(
                            copy.deepcopy(inner))
                        out.append(cp)
                continue
        # for i in range(...) whose body indexes a constant name list by i.
        n_rng = _range_unroll_len(st, env, counts)
        if n_rng:
            if st.orelse:
                raise UnsupportedSpec(
                    "nd_lower: for/else over a range that indexes a constant "
                    "name list has no compiled form -- drop the else branch.")
            for sub in ast.walk(st):
                if isinstance(sub, (ast.Break, ast.Continue)):
                    raise UnsupportedSpec(
                        "nd_lower: break/continue inside a range loop that "
                        "indexes a constant name list cannot be unrolled.")
            budget[0] += n_rng * max(1, len(st.body))
            if budget[0] > _MORPH_UNROLL_CAP:
                raise UnsupportedSpec(
                    "nd_lower: unrolling constant-name loops would emit more "
                    "than %d statements. Index the weights directly "
                    "(self.morphs.resolved) instead of naming every target."
                    % _MORPH_UNROLL_CAP)
            for k in range(n_rng):
                for inner in st.body:
                    cp = _SubstName(st.target.id, k).visit(
                        copy.deepcopy(inner))
                    out.append(cp)
            continue
        out.append(st)
    return out


def _self_call(name, args):
    return ast.Call(func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                                       attr=name, ctx=ast.Load()),
                    args=list(args), keywords=[])


def _self_attr(name):
    return ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                         attr=name, ctx=ast.Load())


def _desugar_morphs(source):
    """Desugar the ``self.morphs`` surface. Returns ``(source, slot_names)``.

    Recognised (everything else honest-rejects)::

        self.morphs.weights          -> self.weight
        self.morphs.resolved         -> self.morph_weights()
        self.morphs.deltas(b)        -> self.morph_deltas(b, self.morph_weights())
        self.morphs.deltas(b, w)     -> self.morph_deltas(b, w)
        self.morphs.apply(b)         -> self.morph_apply(b, 1.0)
        self.morphs.apply(b, e)      -> self.morph_apply(b, e)
        self.morphs[<int>].weight    -> self.weight[<int>]
        self.morphs[<name>].weight   -> self.morph_weight_at(<slot>)
        len(self.morphs)             -> self.weight.shape[0]

    ``<name>`` is a string literal, a folded constant name, a folded constant
    sequence element, or a constant-sequence loop variable. Each DISTINCT name
    gets an ordinal SLOT in first-encounter order, and ``slot_names`` is that
    ordered list. Only the integer slot is baked into the C++; the per-rig
    ``weight[]`` index it maps to travels as node data in ``shapeSlot``, so one
    bundle still serves any rig.

    THE ORDERING IS THIS FUNCTION'S RETURN VALUE, and it is the only source of
    it. The compiler, ``MPyBlendShape.rebuild()`` (which fills ``shapeSlot``) and
    the interpreted ``MorphStack`` all call in here rather than re-deriving it --
    two orderings that drifted would produce a node that compiles, runs, deforms,
    and silently drives the wrong shape.

    Rejecting the remainder is the point: a member that quietly lowered to
    something other than what ``MorphStack`` does interpreted would be a silent
    divergence, which is far worse than a compile error.
    """
    if _MORPH_PROP not in source:
        return source, ()
    try:
        tree, env, counts = _folded_tree(source)
    except SyntaxError:
        return source, ()

    # Slots are assigned BEFORE any rewrite so the ordering does not depend on
    # how far the rewrite gets. A compute that rejects still has a well-defined
    # slot list, which is what the interpreted node reads.
    collector = _SlotCollector(env)
    collector.visit(tree)
    slots = collector.slots

    class _T(ast.NodeTransformer):
        def visit_Call(self, node):
            # len(self.morphs) -> self.weight.shape[0]
            if (isinstance(node.func, ast.Name) and node.func.id == "len"
                    and len(node.args) == 1 and _is_morphs(node.args[0])):
                return ast.copy_location(
                    ast.Subscript(
                        value=ast.Attribute(value=_self_attr(WEIGHT_PLUG),
                                            attr="shape", ctx=ast.Load()),
                        slice=ast.Constant(value=0), ctx=ast.Load()),
                    node)
            # self.morphs.<call>(...)
            f = node.func
            if isinstance(f, ast.Attribute) and _is_morphs(f.value):
                spec = _MORPH_CALLS.get(f.attr)
                if spec is None:
                    raise UnsupportedSpec(
                        "nd_lower: self.morphs.%s(...) has no compiled form. "
                        "In a Compute the MorphStack surface is .weights / "
                        ".resolved / .deltas(base, w) / .apply(base, envelope) "
                        "/ [int].weight / len()." % f.attr)
                if node.keywords:
                    raise UnsupportedSpec(
                        "nd_lower: self.morphs.%s(...) takes positional "
                        "arguments only" % f.attr)
                method, lo, hi = spec
                args = [self.visit(a) for a in node.args]
                if not (lo <= len(args) <= hi):
                    raise UnsupportedSpec(
                        "nd_lower: self.morphs.%s() expects %d..%d argument(s), "
                        "got %d" % (f.attr, lo, hi, len(args)))
                if f.attr == "deltas" and len(args) == 1:
                    args = args + [_self_call("morph_weights", [])]
                elif f.attr == "apply" and len(args) == 1:
                    args = args + [ast.Constant(value=1.0)]
                return ast.copy_location(_self_call(method, args), node)
            self.generic_visit(node)
            return node

        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Subscript) and _is_morphs(
                    node.value.value):
                if node.attr != "weight":
                    raise UnsupportedSpec(
                        "nd_lower: self.morphs[...].%s has no compiled form. "
                        "Only .weight is reachable from an indexed target in a "
                        "Compute; the sparse delta members exist in authoring "
                        "code only." % node.attr)
                sl = node.value.slice
                # by position -- straight into the weight multi
                if (isinstance(sl, ast.Constant) and isinstance(sl.value, int)
                        and not isinstance(sl.value, bool) and sl.value >= 0):
                    return ast.copy_location(
                        ast.Subscript(value=_self_attr(WEIGHT_PLUG),
                                      slice=ast.Constant(value=sl.value),
                                      ctx=ast.Load()),
                        node)
                # by name -- through the compile-time slot indirection
                nm = _const_str_of(sl, env)
                if nm is not None:
                    return ast.copy_location(
                        _self_call("morph_weight_at",
                                   [ast.Constant(value=slots.index(nm))]),
                        node)
                if isinstance(sl, ast.Name):
                    raise UnsupportedSpec(
                        "nd_lower: self.morphs[%s] -- '%s' is not a provable "
                        "constant, so its name cannot be resolved to a slot at "
                        "compile time. A name key must be a literal, or a "
                        "variable assigned ONCE at the top of the Compute from "
                        "a string literal and never reassigned."
                        % (sl.id, sl.id))
                raise UnsupportedSpec(
                    "nd_lower: self.morphs[...] needs a non-negative INTEGER "
                    "literal index, or a NAME that is a compile-time constant "
                    "string (a literal, a top-level constant, an element of a "
                    "top-level constant tuple, or a constant-tuple loop "
                    "variable).")
            if _is_morphs(node.value):
                if node.attr == "weights":
                    return ast.copy_location(_self_attr(WEIGHT_PLUG), node)
                if node.attr == "resolved":
                    return ast.copy_location(
                        _self_call("morph_weights", []), node)
                raise UnsupportedSpec(
                    "nd_lower: self.morphs.%s has no compiled form. In a "
                    "Compute the MorphStack surface is .weights / .resolved / "
                    ".deltas(base, w) / .apply(base, envelope) / [int].weight / "
                    "len()." % node.attr)
            self.generic_visit(node)
            return node

    new_tree = _T().visit(tree)
    ast.fix_missing_locations(new_tree)

    # Anything still referencing the object escaped every recognised form (a bare
    # `self.morphs`, an iteration, a slice). There is no value to produce, so
    # reject loudly rather than emit something plausible.
    for n in ast.walk(new_tree):
        if _is_morphs(n):
            raise UnsupportedSpec(
                "nd_lower: self.morphs used in a form with no compiled "
                "equivalent (bare reference, iteration or slice). Recognised: "
                ".weights / .resolved / .deltas(base, w) / .apply(base, "
                "envelope) / [int].weight / [\"name\"].weight / "
                "len(self.morphs).")

    # Const string bindings the fold fully consumed are dead now. Dropping them
    # keeps sequences away from py_to_cpp entirely -- which is what lets a name
    # key compile with NO new string-sequence type in the shared transpiler. A
    # binding still read elsewhere is left alone (a plain str local lowers fine).
    if env:
        live = {n.id for n in ast.walk(new_tree)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        new_tree.body = [
            st for st in new_tree.body
            if not (isinstance(st, ast.Assign) and len(st.targets) == 1
                    and isinstance(st.targets[0], ast.Name)
                    and st.targets[0].id in env
                    and st.targets[0].id not in live)]

    return ast.unparse(new_tree), tuple(slots)


def _rewrite_morph_reads(source):
    """The desugared source alone -- see :func:`_desugar_morphs`."""
    return _desugar_morphs(source)[0]


def morph_slot_names(source):
    """The ordered NAME keys a compute reaches through ``self.morphs[...]``.

    ``slot k`` is this tuple's index k. The compiler bakes k, the wrapper fills
    ``shapeSlot[k]`` with that name's ``weight[]`` index on the rig at hand, and
    the interpreted MorphStack resolves the same way -- three consumers, one
    ordering, because they all call THIS.

    Never raises: collection is independent of whether the compute can compile,
    and a node that uses an authoring-only MorphStack member still needs its
    names resolved interpreted. Returns ``()`` for a source that names nothing,
    that does not parse, or whose folding itself is unsupported (the real error
    surfaces from the compile proper)."""
    if _MORPH_PROP not in source:
        return ()
    try:
        tree, env, _counts = _folded_tree(source)
    except (SyntaxError, UnsupportedSpec):
        return ()
    collector = _SlotCollector(env)
    collector.visit(tree)
    return tuple(collector.slots)


def _rewrite_deform_io(source):
    """Rewrite the getPoints/setPoints mesh-proxy idiom into self-attr forms.

    Returns ``(rewritten_source, normals_info)`` where ``normals_info`` is None
    or ``{"aw": bool, "space": str}`` (the optional per-vertex-normals idiom).
    Raises UnsupportedSpec if the required idiom (>=1 getPoints AND >=1 setPoints
    on a self.outputGeometry proxy) is absent. Edits are line-local (blank +
    single-line replacement, setPoints arg parenthesised so a multi-line arg
    stays valid) -- the result is re-parsed by the transpiler, so exact line
    numbers only matter for error text."""
    tree = ast.parse(source)
    lines = source.splitlines()
    mesh_vars = set()
    n_get = 0
    n_set = 0

    def _indent_of(lineno):
        raw = lines[lineno - 1]
        return raw[:len(raw) - len(raw.lstrip())]

    def _blank(a, b):
        for ln in range(a, b + 1):
            if 1 <= ln <= len(lines):
                lines[ln - 1] = ""

    for st in tree.body:
        end = getattr(st, "end_lineno", st.lineno)
        # mesh = self.outputGeometry[<const>]
        if (isinstance(st, ast.Assign) and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
                and isinstance(st.value, ast.Subscript)
                and isinstance(st.value.value, ast.Attribute)
                and isinstance(st.value.value.value, ast.Name)
                and st.value.value.value.id == "self"
                and st.value.value.attr == "outputGeometry"):
            mesh_vars.add(st.targets[0].id)
            _blank(st.lineno, end)
            continue
        # rest = mesh.getPoints()   (mesh)  OR  mesh.cvPositions()  (NURBS)
        # Both are the geometry-filter "read all object-space points" idiom; the
        # emitted deform() harvests them uniformly via MItGeometry::allPositions
        # (CV order for NURBS == getPoints order for mesh), so they lower the same.
        if (isinstance(st, ast.Assign) and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
                and isinstance(st.value, ast.Call)
                and isinstance(st.value.func, ast.Attribute)
                and isinstance(st.value.func.value, ast.Name)
                and st.value.func.value.id in mesh_vars
                and st.value.func.attr in ("getPoints", "cvPositions")
                and not st.value.args and not st.value.keywords):
            ind = _indent_of(st.lineno)
            tgt = st.targets[0].id
            _blank(st.lineno, end)
            lines[st.lineno - 1] = "%s%s = self.%s" % (ind, tgt,
                                                       _DEFORM_POINTS_ATTR)
            n_get += 1
            continue
        # mesh.setPoints(<expr>)  (mesh)  OR  mesh.setCVPositions(<expr>)  (NURBS)
        if (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call)
                and isinstance(st.value.func, ast.Attribute)
                and isinstance(st.value.func.value, ast.Name)
                and st.value.func.value.id in mesh_vars
                and st.value.func.attr in ("setPoints", "setCVPositions")
                and len(st.value.args) == 1 and not st.value.keywords):
            arg_src = ast.get_source_segment(source, st.value.args[0])
            if arg_src is None:
                raise UnsupportedSpec("nd_lower deform: cannot extract setPoints "
                                      "argument source")
            ind = _indent_of(st.lineno)
            _blank(st.lineno, end)
            lines[st.lineno - 1] = "%sself.%s = (%s)" % (ind, _DEFORM_OUT_ATTR,
                                                         arg_src)
            n_set += 1
            continue

    if n_get == 0 or n_set == 0:
        raise UnsupportedSpec("nd_lower deform: getPoints/setPoints (or "
                              "cvPositions/setCVPositions) idiom on "
                              "self.outputGeometry not found")
    # optional: per-vertex-normals idiom (mutates `lines` iff the full triple is
    # present + supported; the getPoints/setPoints lines already handled above are
    # distinct, so there is no line collision).
    normals_info = _apply_normals_idiom(tree, source, lines, mesh_vars)
    return "\n".join(lines), normals_info


def _mmatrix_vec_to_nd_lines(src, dst):
    """C++ (indent-1) converting a ``std::vector<MMatrix> src`` (logical-indexed,
    identity gap-fill, produced by emit_deformer._matrix_array_read) into an
    (N,4,4) row-major ``nd::Array<double> dst``. Same layout _materialise_input
    uses for a matrix-array INPUT, so ``np.asarray(self.<matrixArray>)`` and this
    agree byte-for-byte."""
    return [
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _tmp; _tmp.reserve(%s.size() * 16);" % src,
        "        for (size_t _i = 0; _i < %s.size(); ++_i) {" % src,
        "            for (int _r = 0; _r < 4; ++_r)",
        "                for (int _c = 0; _c < 4; ++_c)",
        "                    _tmp.push_back(%s[_i](_r, _c));" % src,
        "        }",
        "        %s = nd::from_data<double>(_tmp, {(int64_t)%s.size(), 4, 4});"
        % (dst, src),
        "    }",
    ]


# skinCluster synthetic bindings: the self.<attr> read -> the C++ local
# emit_deformer emits before the lowered body. matrix/bindPreMatrix are the
# std::vector<MMatrix> from _matrix_array_read; weightList is the dense
# skinW/skinN/skinJ buffer from _weightlist_read.
_SKIN_MATRIX_SRC = {"matrix": "jointMat", "bindPreMatrix": "bindPre"}


def lower_deform(ins, spec, base):
    """Lower a deformer's deform() body to C++ body lines, or raise.

    ins  : codegen input descriptor dicts (user INPUT attrs; envelope + geometry
           are inherited, handled specially here).
    spec : the node spec (uses spec['compute']).
    base : the MPx base -- ``MPxDeformerNode`` OR ``MPxSkinCluster``. For skin,
           the inherited ``matrix`` / ``bindPreMatrix`` / ``weightList`` reads are
           bound to the dense C++ locals emit_deformer emits (jointMat / bindPre /
           skinW), so linear-blend skinning lowers to pure C++.
    Returns indent-1 C++ lines: points/envelope/input materialisation, hoisted
    decls, then the transpiled body (which scatters back into ``pts`` inline)."""
    if base not in ("MPxDeformerNode", "MPxSkinCluster"):
        raise UnsupportedSpec("nd_lower deform: base %r not lowered (only "
                              "MPxDeformerNode / MPxSkinCluster)" % base)
    source = spec.get("compute")
    if not source or not source.strip():
        raise UnsupportedSpec("nd_lower deform: empty compute")

    # Strip any interpreted-side eager-evaluation guard (try/except + _ok flag)
    # so a defensively-wrapped deform lowers deterministically; a compiled node
    # never sees the partial state the guard defends against.
    source = _strip_eager_guard(source)

    # Desugar the mPyBlendShape ``self.morphs`` OBJECT surface into the blessed
    # method calls that already lower. Must happen HERE, before anything reads
    # the compute: `called_method_reads` / `make_transpile_lowerings` /
    # `side_effect_method_names` all scan spec['compute'] textually for
    # `self.<method>(`, so they have to see the DESUGARED form or the implicit
    # table reads never get unioned into `used` and the env binding fails. The
    # spec copy is shallow and local -- spec['compute'] stays verbatim for
    # everyone else (it is part of the node's identity).
    if spec.get("mpy_type") == "mPyBlendShape":
        source = _rewrite_morph_reads(source)
        spec = dict(spec, compute=source)

    src, normals_info = _rewrite_deform_io(source)

    # Geometry INPUT read surface: a deformer may read from an EXTRA geo INPUT (a
    # second mesh/curve/surface beyond the deformed geometry), single via in_<m>
    # MFn* or ARRAY via std::vector<Nd<Kind>> in_<m> (emit_deformer emits both).
    # Bind each read channel before the numeric input loop (which has no geo case).
    src, geo_env, geo_materialise = _geo_input_surface(
        ins, src, allow_geo_array=True)

    used = _used_self_attrs(src)
    # A blessed ``Transpile`` method may declare implicit ``reads`` -- node attrs
    # bound INSIDE the followed free fn, never spelled self.<attr> in the compute.
    # Union each called method's declared reads into `used` so those env bindings
    # still fire. The shipped skin methods pass every operand explicitly
    # (reads=()), so this is a no-op for them today -- the skin plugs land in
    # `used` because the compute literally spells self.weightList / self.matrix /
    # self.bindPreMatrix -- but it stays for methods that opt into implicit reads.
    used |= set(blessed_transpile.called_method_reads(spec))
    env = dict(geo_env)
    materialise = list(geo_materialise)

    # harvested rest points -> (N,3) nd::Array.
    pts_dst = env_cpp_name("self." + _DEFORM_POINTS_ATTR)
    materialise += _deform_points_materialise(pts_dst)
    env["self." + _DEFORM_POINTS_ATTR] = array_t("double", 2)

    # optional per-vertex normals -> (N,3) nd::Array (MFnMesh::getVertexNormals).
    if normals_info is not None and _DEFORM_NORMALS_ATTR in used:
        nrm_dst = env_cpp_name("self." + _DEFORM_NORMALS_ATTR)
        materialise += _deform_normals_materialise(
            nrm_dst, normals_info["aw"], normals_info["space"])
        env["self." + _DEFORM_NORMALS_ATTR] = array_t("double", 2)

    # inherited envelope -> the C++ `env` float (only if the compute reads it).
    if "envelope" in used:
        env_dst = env_cpp_name("self.envelope")
        materialise.append("    double %s = (double)env;" % env_dst)
        env["self.envelope"] = scalar_t("double")

    # user inputs (a used input of an unliftable type raises -> whole fallback).
    in_by_plug = {i["plug"]: i for i in ins}
    for plug in sorted(used):             # sorted(): see lower_compute
        if plug in (_DEFORM_POINTS_ATTR, _DEFORM_OUT_ATTR,
                    _DEFORM_NORMALS_ATTR, "envelope"):
            continue
        if plug in LIVE_CPP_VARS:
            continue  # bound below to the emitter's locals, not to a plug --
                      # skipped here so a user input that happened to share the
                      # name cannot also emit a dead materialise line.
        if base == "MPxSkinCluster" and plug in ("matrix", "bindPreMatrix",
                                                 "weightList"):
            continue  # inherited skin plugs -> synthetic bindings below
        m = in_by_plug.get(plug)
        if m is None:
            continue
        lines, typ = _materialise_input(m, env_cpp_name("self." + plug))
        materialise += lines
        env["self." + plug] = typ

    # inherited skinCluster reads -> the dense C++ locals emit_deformer emits.
    if base == "MPxSkinCluster":
        for plug, vec_src in _SKIN_MATRIX_SRC.items():    # matrix / bindPreMatrix
            if plug in used:
                dst = env_cpp_name("self." + plug)
                materialise += _mmatrix_vec_to_nd_lines(vec_src, dst)
                env["self." + plug] = array_t("double", 3)
        if "weightList" in used:                          # dense (N,J) weights
            dst = env_cpp_name("self.weightList")
            materialise.append(
                "    nd::Array<double> %s = nd::from_data<double>(skinW, "
                "{skinN, skinJ});" % dst)
            env["self.weightList"] = array_t("double", 2)

    # Live-target CSR -> the std::vector locals emit_deformer's live prologue
    # declares. The ONE read surface here with no plug behind it: reading the
    # connected target meshes and diffing them against originalGeometry are Maya
    # calls no transpiled kernel can make, so the emitter does them and hands the
    # result across under these names. Both halves gate on the same thing -- the
    # called methods' declared reads -- so a binding without a prologue block, or
    # a prologue block nothing binds, cannot happen.
    for plug, (dt, vec) in LIVE_CPP_VARS.items():
        if plug in used:
            dst = env_cpp_name("self." + plug)
            c = _ND_CTYPE[dt]
            materialise.append(
                "    nd::Array<%s> %s = nd::from_data<%s>(%s, "
                "{(int64_t)%s.size()});" % (c, dst, c, vec, vec))
            env["self." + plug] = array_t(dt, 1)

    writers = {"self." + _DEFORM_OUT_ATTR: _deform_writeback_lines}
    # Blessed Transpile lowerings (self.<method>(...) -> transpiled free-fn
    # helper). Empty maps for a non-blessed type -> transpiler behaves as before.
    blessed, blessed_unpack = blessed_transpile.make_transpile_lowerings(spec)
    # Blessed NativeSideEffect methods called as a BARE statement lower to nothing
    # (interactive-only plug side effect, no numeric kernel). Empty for a
    # non-blessed type / a compute that calls none.
    side_effects = blessed_transpile.side_effect_method_names(spec)
    res, written, helper_lines = py_to_cpp.transpile_compute_block(
        src, env, writers, _combined_helper_source(spec),
        blessed=blessed, blessed_unpack=blessed_unpack,
        side_effect_methods=side_effects)
    if ("self." + _DEFORM_OUT_ATTR) not in written:
        raise UnsupportedSpec("nd_lower deform: setPoints result never produced")

    return (materialise + list(res.decl_lines) + list(helper_lines)
            + list(res.body_lines))


def try_lower_deform(ins, spec, base):
    """Attempt to lower a deformer's spec['compute']; C++ body lines or None.

    None -> codegen keeps the AI-porter PORT region (zero regression)."""
    source = spec.get("compute")
    if not source or not source.strip():
        return None
    try:
        return lower_deform(ins, spec, base)
    except UnsupportedSpec:
        return None


# ---- transform lowering (MPxTransformationMatrix::desiredLocal() body) -----
# The transform compute contract (see _api1/mpy_transform.py) is the GATED
# DUAL-MATRIX contract (mirrors mPyIkSolver). The lowered body reaches DG plug
# state through declared scalar MATRIX inputs (aim's matrix0/matrix1, bound to
# `in_a<Cap>` MMatrix locals) and the five always-present per-channel READS
# (`self.translate` / `self.rotate` [RADIANS] / `self.scale` / `self.shear`, each
# a (3,) nd value, and `self.rotate_order`, a scalar int) -- bound to the C++
# component locals emit_transform's desiredLocal declares before the lowered body
# (t / r / sc / shr from the MPxTransformationMatrix accessors, ro from
# rotationOrder() offset to the 0-based .rotateOrder plug enum).
#
# The expression writes the desired PARENT-RELATIVE `self.local_matrix` 4x4 plus
# the per-channel gates `self.apply_rotate` / `apply_translate` / `apply_scale`
# (scalar bools). The emit_transform scaffold declares those four as C++ locals
# (`local_matrix` MMatrix + `local_set` flag + `apply_*` bools), the lowered body
# writes them, then the scaffold dispatches (LOCAL > no-op) via `nd_gate_mix` and
# returns the desired local D. For WORLD placement the expression reads the
# parent through a declared matrix input and sets `local_matrix = world @
# inv(parent)` -- the node never reads its own DAG parent.
#
# Only these four sinks + the five channel reads + declared matrix inputs are
# lowerable; reading any other self.<attr> rejects -> AI porter (zero regression).

# self-attrs the lowered body may write.
_TRANSFORM_MATRIX_SINKS = ("local_matrix",)
_TRANSFORM_GATE_SINKS = ("apply_rotate", "apply_translate", "apply_scale")
# self-attrs the lowered body may READ -> (C++ component local, nd builder kind).
# These are this node's own live channels, bound to the MPxTransformationMatrix
# component locals emit_transform's desiredLocal declares before the lowered body.
_TRANSFORM_LOCAL_READS = {
    "translate": ("t", "vec3"),
    "rotate": ("r", "vec3"),        # MEulerRotation .x/.y/.z -> RADIANS
    "scale": ("sc", "vec3"),
    "shear": ("shr", "vec3"),
    "rotate_order": ("ro", "scalar"),
}


def _transform_in_local(plug):
    """C++ local name the scaffold reads a matrix INPUT plug into (must match
    emit_transform's matrix-input reader). ``matrix0`` -> ``in_aMatrix0``."""
    ident = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in plug)
    return "in_a" + ident[:1].upper() + ident[1:]


def _matrix_src_to_nd(src, dst):
    """nd (4,4) from a C++ MMatrix expression ``src`` (row-major; numpy m[i,j] ==
    MMatrix src(i,j), translation in row 3)."""
    elems = ", ".join("%s(%d, %d)" % (src, r, c)
                      for r in range(4) for c in range(4))
    return (["    nd::Array<double> %s = nd::from_data<double>("
             "{%s}, {4, 4});" % (dst, elems)],
            array_t("double", 2))


def _transform_component_to_nd(src, kind, dst):
    """nd value from a C++ transform-component local (see _TRANSFORM_LOCAL_READS).

    ``vec3`` (an MVector / MEulerRotation with ``.x/.y/.z``) -> nd (3,) double
    (matches the interpreted ``(3,)`` numpy channel seed; rotate is RADIANS).
    ``scalar`` (the rotate-order int) -> a scalar int64."""
    if kind == "vec3":
        return (["    nd::Array<double> %s = nd::from_data<double>("
                 "{%s.x, %s.y, %s.z}, {3});" % (dst, src, src, src)],
                array_t("double", 1))
    return (["    int64_t %s = (int64_t)(%s);" % (dst, src)],
            scalar_t("int64"))


def _transform_matrix_sink_writer(cpp_var, set_flag):
    """Writer for ``self.local_matrix``: scatter a produced (4,4) nd value into
    the C++ MMatrix ``cpp_var`` and raise its ``set_flag`` (row-major;
    ``cpp_var.matrix[r][c] = value[r,c]``)."""
    def _writer(val):
        if not val.type.is_array():
            raise UnsupportedSpec("nd_lower transform: non-array value assigned "
                                  "to %s" % cpp_var)
        return [
            "{",
            "    nd::Array<double> _o = (%s);" % _cast_array(val, "double"),
            "    if (_o.offset != 0 || !_o.is_contiguous()) _o = _o.copy();",
            "    for (int _r = 0; _r < 4; ++_r)",
            "        for (int _c = 0; _c < 4; ++_c)",
            "            %s.matrix[_r][_c] = (*_o.data)[_r*4 + _c];" % cpp_var,
            "    %s = true;" % set_flag,
            "}",
        ]
    return _writer


def _transform_gate_writer(cpp_var):
    """Writer for ``self.apply_*``: set the C++ bool ``cpp_var`` from a scalar
    (bool / int) value produced by the transpiler."""
    def _writer(val):
        if val.type.is_array() and val.type.rank not in (0, None):
            raise UnsupportedSpec("nd_lower transform: apply_* gate must be a "
                                  "scalar bool, got an array")
        code = val.code
        if val.type.is_array():
            code = "(%s).item()" % code
        return ["%s = ((%s) != 0);" % (cpp_var, code)]
    return _writer


def lower_transform(spec):
    """Lower a transform's desiredLocal() math to C++ body lines, or raise.

    Binds declared scalar matrix inputs to their ``in_a<Cap>`` MMatrix locals and
    writes the gated local-matrix sinks (``self.local_matrix`` + ``self.apply_*``)
    into the scaffold's C++ locals. Rejects (UnsupportedSpec) if the compute reads
    any unsupported self.<attr>, or never writes the matrix sink.
    Returns indent-1 C++ lines: matrix-input materialisation, hoisted decls, then
    the transpiled body (which writes the sinks inline via the writers)."""
    source = spec.get("compute")
    if not source or not source.strip():
        raise UnsupportedSpec("nd_lower transform: empty compute")

    used = _used_self_attrs(source)
    # Declared MATRIX inputs (scalar `matrix` type) the scaffold exposes as
    # `in_a<Cap>` MMatrix locals -- e.g. aim's matrix0/matrix1. Non-matrix or
    # array inputs are not liftable.
    matrix_inputs = {
        plug for plug, meta in (spec.get("inputs") or {}).items()
        if meta.get("type") == "matrix" and not meta.get("is_array")}
    # Generic scalar inputs (float/vector/euler/color/quaternion/float2/angle/
    # time/enum/string) the scaffold exposes as ``in_a<ident>`` locals. Reuse
    # emit_transform's collector so the member names + type filter are a single
    # source of truth (the read local + this bind must agree). _materialise_input
    # lifts every one except string (-> raises -> the whole compute PORTs).
    from mpynode.native.compiler.emit_transform import _transform_generic_inputs
    generic_ms = {gm["plug"]: gm for gm in _transform_generic_inputs(spec)}
    allowed = (set(_TRANSFORM_MATRIX_SINKS) | set(_TRANSFORM_GATE_SINKS)
               | set(_TRANSFORM_LOCAL_READS) | matrix_inputs | set(generic_ms))
    extra = used - allowed
    if extra:
        raise UnsupportedSpec("nd_lower transform: reads/writes unsupported self "
                              "attr(s): %s" % ", ".join(sorted(extra)))
    if not (used & set(_TRANSFORM_MATRIX_SINKS)):
        raise UnsupportedSpec("nd_lower transform: does not write "
                              "self.local_matrix")

    env = {}
    materialise = []
    for attr in sorted(used):             # sorted(): see lower_compute
        if attr in _TRANSFORM_MATRIX_SINKS or attr in _TRANSFORM_GATE_SINKS:
            continue  # sinks are writes, not reads
        # Readable self attrs: this node's own live channels (``self.translate``
        # etc. -> the C++ component locals t/r/sc/shr/ro), a declared scalar
        # matrix input (``self.matrix0`` -> ``in_a<Cap>``), or a generic scalar
        # input (``self.weight`` -> ``in_a<ident>``, bound via _materialise_input
        # -- which raises for string, dropping the whole compute to the porter).
        dst = env_cpp_name("self." + attr)
        if attr in _TRANSFORM_LOCAL_READS:
            comp_src, comp_kind = _TRANSFORM_LOCAL_READS[attr]
            lines, typ = _transform_component_to_nd(comp_src, comp_kind, dst)
        elif attr in matrix_inputs:
            lines, typ = _matrix_src_to_nd(_transform_in_local(attr), dst)
        else:
            lines, typ = _materialise_input(generic_ms[attr], dst)
        materialise += lines
        env["self." + attr] = typ

    writers = {
        "self.local_matrix": _transform_matrix_sink_writer(
            "local_matrix", "local_set"),
        "self.apply_rotate": _transform_gate_writer("apply_rotate"),
        "self.apply_translate": _transform_gate_writer("apply_translate"),
        "self.apply_scale": _transform_gate_writer("apply_scale"),
    }
    res, written, helper_lines = py_to_cpp.transpile_compute_block(
        source, env, writers, _combined_helper_source(spec))
    if "self.local_matrix" not in written:
        raise UnsupportedSpec("nd_lower transform: local_matrix sink not produced")

    return (materialise + list(res.decl_lines) + list(helper_lines)
            + list(res.body_lines))


def try_lower_transform(spec):
    """Attempt to lower a transform's spec['compute']; C++ body lines or None.

    None -> codegen keeps the AI-porter PORT region (zero regression)."""
    source = spec.get("compute")
    if not source or not source.strip():
        return None
    try:
        return lower_transform(spec)
    except UnsupportedSpec:
        return None


# ---- IK-solver lowering (MPxIkSolverNode::doSolve) -------------------------
# The doSolve scaffold (emit_iksolver) already declares the entire solve FRAME in
# C++: it walks the handle group, harvests the joint chain, captures/persists the
# bind offsets, and owns the gate-mix + offsetParentMatrix writeback. All the PORT
# region ever had to do was FILL a fixed set of C++ locals from the user's Python
# -- which is exactly what a deterministic lowering can produce. This binds the
# solver's framework ``self.<attr>`` surface to nd:: values, transpiles the body,
# and scatters the result back into those same locals.
#
# The Python surface is a list of DICTS (``self.joints[j]["world_matrix"]``), a
# shape the transpiler has none for -- so joint reads are AST-REWRITTEN into
# synthetic per-CHANNEL self-attrs bound to STACKED nd arrays, the same trick the
# geometry read surface uses (see _rewrite_geo_reads).
_IK_SYN_PREFIX = "__ndik_"
_IK_NUMJOINTS_SYN = _IK_SYN_PREFIX + "numjoints_"

# ``joints[j]["<channel>"]`` -> (C++ scaffold vector, element kind). Stacked to
# nd (N,4,4) for "mat" and (N,3) for "vec3". ``name`` (a string) and ``rotation``
# (``cmds.xform(ro=True)`` DEGREES, which the scaffold has no local for and whose
# rotateOrder/jointOrient parity is not reproducible here) are deliberately
# ABSENT -- reading either rejects the whole lowering to the porter.
_IK_JOINT_CHANNELS = {
    "world_matrix": ("bindWorld", "mat"),
    "matrix": ("jointLocal", "mat"),
    "world_position": ("jointPos", "vec3"),
}
# Framework scalars/vectors the scaffold declares -> (C++ local, kind).
_IK_SCALAR_READS = {
    "end_effector": ("endEffector", "vec3"),
    "pole_vector": ("poleVector", "vec3"),
    "twist": ("twist", "scalar"),
}
# ``self.<sink>[j] = <4x4>`` -> (C++ MMatrix vector, C++ set-flag vector). Bound
# as a MUTABLE nd (N,4,4) so an INDEXED write lowers through the transpiler's
# ordinary slice-assign; the scatter below turns it back into the sinks.
_IK_MATRIX_SINKS = {
    "world_matrices": ("outWorldMat", "outWorldSet"),
    "local_matrices": ("outLocalMat", "outLocalSet"),
}
# ``self.<gate> = bool`` (broadcast) or ``= [bool]`` (per joint) -> C++ vector.
_IK_GATE_SINKS = {
    "apply_rotate": "applyRotate",
    "apply_translate": "applyTranslate",
    "apply_scale": "applyScale",
}


def _ik_channel_syn(channel):
    """Synthetic self-attr a rewritten ``joints[j]["<channel>"]`` read binds to."""
    return "%sjoints_%s_" % (_IK_SYN_PREFIX, channel)


def _ik_joint_mat_to_nd(src, dst):
    """nd (numJoints,4,4) from a C++ ``std::vector<MMatrix>`` (row-major; numpy
    m[j,r,c] == src[j](r,c), translation in row 3 -- the same convention
    _matrix_src_to_nd uses for the single-matrix case)."""
    return ([
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _tmp; _tmp.reserve((size_t)numJoints * 16);",
        "        for (int _j = 0; _j < numJoints; ++_j)",
        "            for (int _r = 0; _r < 4; ++_r)",
        "                for (int _c = 0; _c < 4; ++_c)",
        "                    _tmp.push_back(%s[_j](_r, _c));" % src,
        "        %s = nd::from_data<double>(_tmp, {(int64_t)numJoints, 4, 4});"
        % dst,
        "    }",
    ], array_t("double", 3))


def _ik_joint_vec_to_nd(src, dst):
    """nd (numJoints,3) from a C++ ``std::vector<MVector>`` (mirrors the dense
    (N,3) numpy the interpreted joints[j]["world_position"] seeds)."""
    return ([
        "    nd::Array<double> %s;" % dst,
        "    {",
        "        std::vector<double> _tmp; _tmp.reserve((size_t)numJoints * 3);",
        "        for (int _j = 0; _j < numJoints; ++_j) {",
        "            _tmp.push_back(%s[_j].x);" % src,
        "            _tmp.push_back(%s[_j].y);" % src,
        "            _tmp.push_back(%s[_j].z);" % src,
        "        }",
        "        %s = nd::from_data<double>(_tmp, {(int64_t)numJoints, 3});" % dst,
        "    }",
    ], array_t("double", 2))


def _ik_vec3_to_nd(src, dst):
    """nd (3,) from a C++ MVector local (endEffector / poleVector)."""
    return (["    nd::Array<double> %s = nd::from_data<double>("
             "{%s.x, %s.y, %s.z}, {3});" % (dst, src, src, src)],
            array_t("double", 1))


def _ik_matrix_sink_scatter(nd_name, mat_vec, set_vec):
    """Scatter a bound (N,4,4) sink buffer back into the scaffold's MMatrix
    vector, raising the per-joint set flag ONLY where the value CHANGED.

    Change-detection is what recovers the Python ``None`` slot: the interpreted
    buffer starts as ``[None] * n`` and an untouched slot leaves the joint at its
    rest offset, but an nd array has no None to carry. Seeding the buffer with the
    scaffold's own default and flagging only what moved is EXACTLY equivalent --
    for an unwritten joint the writeback's two branches coincide. Set-to-rest
    gives ``offset = inv(local) @ (local@bind@pw) @ inv(pw) == bind`` and threads
    ``parentWorld = local@bind@pw``, which is precisely the restore-bind branch,
    so a false "set" cannot change the result either."""
    return [
        "    {",
        "        nd::Array<double> _s = %s;" % nd_name,
        "        if (_s.offset != 0 || !_s.is_contiguous()) _s = _s.copy();",
        "        for (int _j = 0; _j < numJoints; ++_j) {",
        "            bool _ch = false;",
        "            for (int _r = 0; _r < 4 && !_ch; ++_r)",
        "                for (int _c = 0; _c < 4 && !_ch; ++_c)",
        "                    if ((*_s.data)[((size_t)_j * 4 + _r) * 4 + _c]",
        "                            != %s[_j](_r, _c)) _ch = true;" % mat_vec,
        "            if (!_ch) continue;",
        "            for (int _r = 0; _r < 4; ++_r)",
        "                for (int _c = 0; _c < 4; ++_c)",
        "                    %s[_j].matrix[_r][_c] =" % mat_vec,
        "                        (*_s.data)[((size_t)_j * 4 + _r) * 4 + _c];",
        "            %s[_j] = 1;" % set_vec,
        "        }",
        "    }",
    ]


def _ik_gate_writer(cpp_var):
    """Writer for ``self.apply_*``: a SCALAR broadcasts to the whole chain, a
    sequence gates per joint with missing entries left at the scaffold default --
    mirroring the interpreted ``_normalize_gate(val, n, default)``."""
    def _writer(val):
        if val.type.is_array():
            return [
                "{",
                "    nd::Array<double> _g = (%s);" % _cast_array(val, "double"),
                "    if (_g.offset != 0 || !_g.is_contiguous()) _g = _g.copy();",
                "    int64_t _n = _g.shape.empty() ? 0 : _g.shape[0];",
                "    for (int _j = 0; _j < numJoints && _j < _n; ++_j)",
                "        %s[_j] = ((*_g.data)[_j] != 0.0) ? 1 : 0;" % cpp_var,
                "}",
            ]
        return [
            "{",
            "    const char _g = ((%s) != 0) ? 1 : 0;" % val.code,
            "    for (int _j = 0; _j < numJoints; ++_j) %s[_j] = _g;" % cpp_var,
            "}",
        ]
    return _writer


def _hoist_nested_defs(source):
    """Lift ``def``s nested inside the compute body out to helper sources.

    The transpiler only lowers helpers registered from the INIT tier, but a solve
    is naturally written with its math inline (``def rot3(axis, ang): ...`` inside
    an ``if``). Hoisting is only sound when the def is genuinely a free function,
    so a def that CLOSES OVER a block local is left in place -- it then reaches the
    transpiler as an unsupported statement and the whole compute drops to the
    porter, which is the safe direction.

    Returns ``(new_source, hoisted_source_or_None)``."""
    tree = ast.parse(source)
    hoisted, kept_names = [], set()

    def _free_ok(fn):
        """True when ``fn`` only reads its own params/locals, module aliases, or
        another hoisted helper -- i.e. nothing from the enclosing block."""
        bound = {a.arg for a in fn.args.args}
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                bound.add(n.id)
            elif isinstance(n, (ast.For, ast.comprehension)):
                tgt = getattr(n, "target", None)
                if isinstance(tgt, ast.Name):
                    bound.add(tgt.id)
        allowed = bound | set(_NP_MODULE_ALIASES) | _HOIST_FREE_BUILTINS \
            | kept_names
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if n.id not in allowed:
                    return False
        return True

    class _T(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if not _free_ok(node):
                return node
            kept_names.add(node.name)
            hoisted.append(node)
            return None

        def generic_visit(self, node):
            node = super().generic_visit(node)
            # Lifting the only statement out of a block leaves an EMPTY body,
            # which is not a valid AST -- backfill the `pass`.
            for field in ("body", "orelse", "finalbody"):
                blk = getattr(node, field, None)
                if isinstance(blk, list) and not blk and hasattr(node, "lineno"):
                    setattr(node, field, [ast.Pass()])
            return node

    new_tree = _T().visit(tree)
    if not hoisted:
        return source, None
    ast.fix_missing_locations(new_tree)
    mod = ast.Module(body=hoisted, type_ignores=[])
    ast.fix_missing_locations(mod)
    return ast.unparse(new_tree), ast.unparse(mod)


# Module aliases a hoisted helper may reference without capturing a block local.
_NP_MODULE_ALIASES = ("np", "numpy", "math", "ndio")
# Builtins a hoisted helper may reference; anything else reads as a CAPTURE of an
# enclosing local and keeps the def in place (-> the compute drops to the porter).
_HOIST_FREE_BUILTINS = frozenset({
    "abs", "min", "max", "sum", "len", "range", "float", "int", "bool", "round",
    "enumerate", "zip", "pow", "print", "sorted", "list", "tuple",
})


def _rewrite_ik_joint_reads(source):
    """Rewrite the solver's joint READ SURFACE into synthetic self-attrs.

    ``self.joints[j]["<channel>"]`` (and the same through a single-assignment
    alias, ``joints = self.joints``) becomes ``self.__ndik_joints_<channel>_[j]``,
    and ``len(<joints>)`` becomes the bound scalar ``self.__ndik_numjoints_``.
    Returns ``(new_source, channels_used)``; raises UnsupportedSpec if the joints
    list is touched OUTSIDE that surface (an unsupported channel, iteration, a
    bare pass-through) so the whole compute falls back to the porter."""
    tree = ast.parse(source)

    # `X = self.joints` counts as an alias only when X is assigned EXACTLY once
    # (a reassigned name is not an alias; its bare use is then rejected below).
    assigns = {}
    for st in ast.walk(tree):
        if isinstance(st, ast.Assign):
            for tg in st.targets:
                if isinstance(tg, ast.Name):
                    assigns.setdefault(tg.id, []).append(st.value)

    def _is_self_joints(n):
        return (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "self" and n.attr == "joints")

    alias = {nm for nm, vals in assigns.items()
             if len(vals) == 1 and _is_self_joints(vals[0])}

    def _joints_ref(n):
        return _is_self_joints(n) or (isinstance(n, ast.Name) and n.id in alias)

    # `jd = <joints>[<idx>]` -- a per-joint dict alias. Restricted to a
    # single-assignment name whose INDEX is a plain name/constant, so
    # re-materialising that index at each use cannot change meaning.
    jd_alias = {}
    for nm, vals in assigns.items():
        if len(vals) != 1:
            continue
        v = vals[0]
        if (isinstance(v, ast.Subscript) and _joints_ref(v.value)
                and isinstance(v.slice, (ast.Name, ast.Constant))):
            jd_alias[nm] = v.slice

    channels, bad = set(), []

    def _chan_node(key, idx, node):
        if key not in _IK_JOINT_CHANNELS:
            bad.append('joints[...]["%s"]' % key)
            return node
        channels.add(key)
        return ast.copy_location(
            ast.Subscript(
                value=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                                    attr=_ik_channel_syn(key), ctx=ast.Load()),
                slice=idx, ctx=node.ctx), node)

    def _str_key(sl):
        return sl.value if (isinstance(sl, ast.Constant)
                            and isinstance(sl.value, str)) else None

    class _T(ast.NodeTransformer):
        def visit_Assign(self, node):
            # Drop the now-dead alias bindings (every use is rewritten).
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and ((node.targets[0].id in alias
                          and _joints_ref(node.value))
                         or node.targets[0].id in jd_alias)):
                return None
            self.generic_visit(node)
            return node

        def visit_Subscript(self, node):
            key = _str_key(node.slice)
            if key is not None:
                inner = node.value
                if isinstance(inner, ast.Subscript) and _joints_ref(inner.value):
                    return _chan_node(key, self.visit(inner.slice), node)
                if isinstance(inner, ast.Name) and inner.id in jd_alias:
                    return _chan_node(key, jd_alias[inner.id], node)
            self.generic_visit(node)
            return node

        def visit_Call(self, node):
            if (isinstance(node.func, ast.Name) and node.func.id == "len"
                    and len(node.args) == 1 and _joints_ref(node.args[0])):
                return ast.copy_location(
                    ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                                  attr=_IK_NUMJOINTS_SYN, ctx=ast.Load()), node)
            self.generic_visit(node)
            return node

        def visit_Attribute(self, node):
            # A bare `self.joints` reaching here was not consumed as a channel.
            if _is_self_joints(node):
                bad.append("self.joints")
                return node
            self.generic_visit(node)
            return node

        def visit_Name(self, node):
            if node.id in alias or node.id in jd_alias:
                bad.append(node.id)
            return node

    new_tree = _T().visit(tree)
    if bad:
        raise UnsupportedSpec(
            "nd_lower iksolver: joints used outside the supported read surface "
            "(%s); supported channels are %s"
            % (", ".join(sorted(set(bad))),
               ", ".join(sorted(_IK_JOINT_CHANNELS))))
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree), channels


def lower_iksolver(spec):
    """Lower a solver's doSolve() math to C++ body lines, or raise.

    Binds the framework read surface (joint channels, end_effector, pole_vector,
    twist) plus any declared user INPUT, runs the transpiled body against mutable
    nd sink buffers, then scatters those buffers into the scaffold's
    ``outWorldMat``/``outLocalMat`` (+ set flags) and gate vectors. Rejects
    (UnsupportedSpec) if the compute touches an unsupported ``self.<attr>`` or
    never drives a joint."""
    source = spec.get("compute")
    if not source or not source.strip():
        raise UnsupportedSpec("nd_lower iksolver: empty compute")

    from mpynode.native.compiler.emit_iksolver import (
        _ik_scalar_inputs, _ik_generic_inputs)

    source, hoisted = _hoist_nested_defs(source)
    source, channels = _rewrite_ik_joint_reads(source)

    # Declared user INPUTs: the bespoke scalars read into `in_<ident>` and the
    # generic attrs read into `in_<member>` -- the SAME locals emit_iksolver
    # declares, so the bind and the read cannot drift.
    user_ms = {s["plug"]: {"member": s["ident"], "meta": {"type": s["type"]}}
               for s in _ik_scalar_inputs(spec)}
    user_ms.update({gm["plug"]: gm for gm in _ik_generic_inputs(spec)})

    syn_reads = {_ik_channel_syn(ch) for ch in channels}
    used = _used_self_attrs(source)
    allowed = (syn_reads | {_IK_NUMJOINTS_SYN} | set(_IK_SCALAR_READS)
               | set(_IK_MATRIX_SINKS) | set(_IK_GATE_SINKS) | set(user_ms))
    extra = used - allowed
    if extra:
        raise UnsupportedSpec("nd_lower iksolver: reads/writes unsupported self "
                              "attr(s): %s" % ", ".join(sorted(extra)))
    if not (used & set(_IK_MATRIX_SINKS)):
        raise UnsupportedSpec("nd_lower iksolver: never writes "
                              "self.world_matrices / self.local_matrices")

    env, materialise = {}, []
    for attr in sorted(used):
        if attr in _IK_GATE_SINKS:
            continue                      # write-only (no readable binding)
        dst = env_cpp_name("self." + attr)
        if attr == _IK_NUMJOINTS_SYN:
            lines = ["    int64_t %s = (int64_t)numJoints;" % dst]
            typ = scalar_t("int64")
        elif attr in syn_reads:
            ch = next(c for c in channels if _ik_channel_syn(c) == attr)
            src, kind = _IK_JOINT_CHANNELS[ch]
            lines, typ = (_ik_joint_mat_to_nd(src, dst) if kind == "mat"
                          else _ik_joint_vec_to_nd(src, dst))
        elif attr in _IK_SCALAR_READS:
            src, kind = _IK_SCALAR_READS[attr]
            if kind == "vec3":
                lines, typ = _ik_vec3_to_nd(src, dst)
            else:
                lines = ["    double %s = (double)(%s);" % (dst, src)]
                typ = scalar_t("double")
        elif attr in _IK_MATRIX_SINKS:
            # Seeded from the scaffold's OWN default so an untouched slot is
            # detectably unchanged (see _ik_matrix_sink_scatter).
            src, _set_vec = _IK_MATRIX_SINKS[attr]
            lines, typ = _ik_joint_mat_to_nd(src, dst)
        else:
            lines, typ = _materialise_input(user_ms[attr], dst)
        materialise += lines
        env["self." + attr] = typ

    writers = {"self." + g: _ik_gate_writer(v) for g, v in _IK_GATE_SINKS.items()}
    helper_sources = _combined_helper_source(spec) or []
    if hoisted:
        helper_sources = list(helper_sources) + [hoisted]
    res, _written, helper_lines = py_to_cpp.transpile_compute_block(
        source, env, writers, helper_sources or None)

    scatter = []
    for attr in sorted(used & set(_IK_MATRIX_SINKS)):
        mat_vec, set_vec = _IK_MATRIX_SINKS[attr]
        scatter += _ik_matrix_sink_scatter(
            env_cpp_name("self." + attr), mat_vec, set_vec)

    return (materialise + list(res.decl_lines) + list(helper_lines)
            + list(res.body_lines) + scatter)


def try_lower_iksolver(spec):
    """Attempt to lower a solver's spec['compute']; C++ body lines or None.

    None -> codegen keeps the AI-porter PORT region (zero regression)."""
    source = spec.get("compute")
    if not source or not source.strip():
        return None
    try:
        return lower_iksolver(spec)
    except UnsupportedSpec:
        return None
    except SyntaxError:
        return None


# ==== mPyLocator -- deterministic draw lowering ============================
# The draw CONTEXT the scaffold hands computeBuffers as named C++ locals (see
# emit_locator: `const double timeVal`, `const bool selected`, ...). Each entry
# is (c++ expression, kind) with the same shape as _IK_SCALAR_READS.
_LOC_CONTEXT_READS = {
    "time": ("timeVal", "double"),
    "selected": ("selected", "bool"),
    "is_lead": ("is_lead", "bool"),
    "hovered": ("hovered", "bool"),
}
# self.selection_color -> the scaffold's MColor local, as an nd (4,).
_LOC_SELECTION_COLOR = "selection_color"
# Write-only draw flags. Each lowers to a plain member store on `data`.
_LOC_FLAG_SINKS = {
    "auto_highlight": "autoHighlight",
    "auto_refresh": "autoRefresh",
    "precise_hover": "preciseHover",
}
_LOC_DRAW_SINK = "draw"
# self.<enum>.name() reads the enum's FIELD NAME. Rewritten to a synthetic
# self-attr so it binds through the ordinary input path (see below).
_LOC_ENUM_NAME_PREFIX = "__nd_enumname_"
# `time.time()` (under whatever name the Init tab imported it) -> the scaffold's
# per-frame wall clock, bound through a synthetic attr.
_LOC_WALLCLOCK_ATTR = "__nd_wallclock"


def _rewrite_loc_wallclock(source, init_source):
    """``time.time()``, however imported -> a synthetic ``self.__nd_wallclock``.

    The scaffold already computes a per-frame ``wallClock``, so binding it
    through a synthetic attr reuses the normal materialise path and leaves the
    transpiler with no notion of a clock -- the same trick
    ``_rewrite_loc_enum_names`` uses.

    Origin resolution is shared with the transpiler
    (``py_to_cpp._parse_import_bindings``), so every spelling that calls the
    same function is recognised: ``import time`` / ``import time as _wall`` ->
    ``_wall.time()``, and ``from time import time [as clock]`` -> ``clock()``.
    No AMBIENT default is seeded -- an unimported ``time`` is a NameError in
    Python, so there is nothing to translate.

    Returns ``(source, used)``."""
    bindings, stars = py_to_cpp._parse_import_bindings([init_source, source])
    if not bindings and not stars:
        return source, False
    used = []
    tree = ast.parse(source)
    # A name the compute REBINDS is not the module any more.
    bound = {n.id for n in ast.walk(tree)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}

    class _T(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if node.args or node.keywords:
                return node
            dotted = py_to_cpp.dotted_name(node.func)
            if dotted is None:
                return node
            head = dotted.partition(".")[0]
            # Require a REAL binding: canonical_dotted passes an unresolved name
            # through unchanged, so a bare `time.time()` with no import would
            # otherwise match itself -- and with no import that is a NameError
            # in Python, not a clock.
            if head in bound or (head not in bindings and not stars):
                return node
            if py_to_cpp.canonical_dotted(dotted, bindings, stars) != "time.time":
                return node
            used.append(True)
            return ast.copy_location(ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr=_LOC_WALLCLOCK_ATTR, ctx=ast.Load()), node)

    tree = _T().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree), bool(used)


def _rewrite_loc_enum_names(source, enum_plugs):
    """``self.<enum>.name()`` -> a synthetic ``self.__nd_enumname_<enum>`` read.

    The locator scaffold ALREADY emits a lookup table and an
    ``in_<plug>_name`` std::string beside every enum input -- it has simply
    been dead code (``(void)in_<plug>_name;``). Rewriting the call into a
    synthetic attr binds that existing local through the normal materialise
    path, so the transpiler needs no notion of "this int64 came from an enum"
    and its type system is untouched.

    Returns ``(source, used_plugs)``; the source is unchanged when the node
    declares no enum inputs."""
    if not enum_plugs:
        return source, set()
    used = set()

    class _T(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            fn = node.func
            if (isinstance(fn, ast.Attribute) and fn.attr == "name"
                    and not node.args and not node.keywords
                    and isinstance(fn.value, ast.Attribute)
                    and isinstance(fn.value.value, ast.Name)
                    and fn.value.value.id == "self"
                    and fn.value.attr in enum_plugs):
                used.add(fn.value.attr)
                return ast.copy_location(ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr=_LOC_ENUM_NAME_PREFIX + fn.value.attr,
                    ctx=ast.Load()), node)
            return node

    tree = _T().visit(ast.parse(source))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree), used


def _loc_flag_writer(member):
    """Writer for `self.<flag> = <bool>` -> `data.<member> = ...;`."""
    def _w(val):
        code = val.code if val.type.kind == "scalar" else (val.code + ".item()")
        return ["    data.%s = (bool)(%s);" % (member, code)]
    return _w


def _loc_color_to_nd(src, dst):
    """nd (4,) from a C++ MColor local (selection_color / a color input)."""
    return (["    nd::Array<double> %s = nd::from_data<double>("
             "{%s.r, %s.g, %s.b, %s.a}, {4});" % (dst, src, src, src, src)],
            array_t("double", 1))


def lower_locator(spec):
    """Lower a locator's draw expression to C++ body lines, or raise.

    Binds the per-frame draw context (time / selected / is_lead / hovered /
    selection_color) plus every declared user INPUT, desugars ``self.draw`` into
    ordered emit statements (see kernels.locator_draw_cpp), and transpiles the
    result. Rejects (UnsupportedSpec) on any construct without a proven compiled
    form -- the caller then keeps the AI-porter PORT region."""
    from mpynode.native.compiler.kernels import locator_draw_cpp
    from mpynode.native.compiler.emit_locator import (
        _loc_scalar_inputs, _loc_string_inputs, _loc_color_inputs,
        _loc_generic_inputs)

    source = spec.get("compute")
    if not source or not source.strip():
        raise UnsupportedSpec("nd_lower locator: empty compute")

    source, hoisted = _hoist_nested_defs(source)
    # self.draw = <drawing>  ->  ordered self.__nd_draw_*(...) statements.
    source = locator_draw_cpp.desugar_draw(source)

    scalar_ins = _loc_scalar_inputs(spec)
    user_ms = {s["plug"]: {"member": s["member"][3:], "meta": {"type": s["type"]}}
               for s in scalar_ins}
    # A single string plug binds to the transpiler's str kind (_materialise_input);
    # the scaffold already exposes it as `const MString& in_<name>`. String
    # ARRAYS stay unbound -- there is no string-array kind -- so a draw that
    # reads one still falls through to the porter.
    user_ms.update({s["plug"]: {"member": s["member"][3:],
                                "meta": {"type": "string"}}
                    for s in _loc_string_inputs(spec)})
    user_ms.update({gm["plug"]: gm for gm in _loc_generic_inputs(spec)})
    color_ms = {c["member"][3:]: c for c in _loc_color_inputs(spec)}

    enum_plugs = {s["plug"] for s in scalar_ins if s["type"] == "enum"}
    source, _enum_reads = _rewrite_loc_enum_names(source, enum_plugs)
    source, wall_used = _rewrite_loc_wallclock(source, spec.get("init"))
    if wall_used and not spec.get("needs_hover"):
        # `wallClock` is only seeded per-frame for a needs_hover node; without
        # it the scaffold pins it to 0.0 and the compiled gizmo would sit frozen
        # while the interpreted one animates. (The AI-porter path has the same
        # constraint -- this only declines to make it worse.)
        raise UnsupportedSpec("nd_lower locator: time.time() needs the live "
                              "wall clock (set self.auto_refresh)")

    blessed = locator_draw_cpp.make_blessed_lowerings()
    allowed = (set(_LOC_CONTEXT_READS) | {_LOC_SELECTION_COLOR}
               | set(_LOC_FLAG_SINKS) | {_LOC_DRAW_SINK}
               | set(user_ms) | set(color_ms)
               | {_LOC_ENUM_NAME_PREFIX + p for p in enum_plugs}
               | {_LOC_WALLCLOCK_ATTR}
               | set(blessed))          # the synthetic emit calls desugar made
    # The declared set is what the NODE declares, not what this lowerer can
    # bind. A plug it cannot bind (a string input, say) must still be collected
    # so it fails the `allowed` check below and the node falls back to the
    # porter -- folding getattr to its default there would silently ignore a
    # plug the user wired up.
    declared = (allowed | set(spec.get("inputs") or {})
                | set(spec.get("outputs") or {}))
    used = _used_self_attrs(source, declared)
    extra = used - allowed
    if extra:
        raise UnsupportedSpec("nd_lower locator: reads/writes unsupported self "
                              "attr(s): %s" % ", ".join(sorted(extra)))

    env, materialise = {}, []
    for attr in sorted(used):
        if attr in _LOC_FLAG_SINKS or attr == _LOC_DRAW_SINK or attr in blessed:
            continue      # write-only sinks + emit calls: no readable binding
        dst = env_cpp_name("self." + attr)
        if attr == _LOC_SELECTION_COLOR:
            lines, typ = _loc_color_to_nd(_LOC_SELECTION_COLOR, dst)
        elif attr in color_ms:
            lines, typ = _loc_color_to_nd("in_" + attr, dst)
        elif attr in _LOC_CONTEXT_READS:
            src, kind = _LOC_CONTEXT_READS[attr]
            c = "bool" if kind == "bool" else "double"
            lines = ["    %s %s = (%s)(%s);" % (c, dst, c, src)]
            typ = scalar_t("bool" if kind == "bool" else "double")
        elif attr == _LOC_WALLCLOCK_ATTR:
            # NOTE: _wallClock() is steady_clock measured from the plugin's
            # first call, while time.time() is epoch seconds. The motion and its
            # speed are identical; only the PHASE differs from the interpreted
            # node, which a wall-clock animation does not define. Deliberate --
            # user decision, 2026-08-05.
            lines = ["    const double %s = wallClock;" % dst]
            typ = scalar_t("double")
        elif attr.startswith(_LOC_ENUM_NAME_PREFIX):
            # the scaffold's own enum-name lookup, bound as a std::string
            plug = attr[len(_LOC_ENUM_NAME_PREFIX):]
            lines = ["    const std::string %s = in_%s_name;" % (dst, plug)]
            typ = str_t()
        else:
            lines, typ = _materialise_input(user_ms[attr], dst)
        materialise += lines
        env["self." + attr] = typ

    writers = {"self." + f: _loc_flag_writer(m)
               for f, m in _LOC_FLAG_SINKS.items()}
    helper_sources = _combined_helper_source(spec) or []
    if hoisted:
        helper_sources = list(helper_sources) + [hoisted]
    res, _written, helper_lines = py_to_cpp.transpile_compute_block(
        source, env, writers, helper_sources or None,
        blessed=blessed, const_source=spec.get("init"))

    return (materialise + list(res.decl_lines) + list(helper_lines)
            + list(res.body_lines))


def try_lower_locator(spec):
    """Attempt to lower a locator's spec['compute']; C++ body lines or None.

    None -> codegen keeps the AI-porter PORT region (zero regression)."""
    source = spec.get("compute")
    if not source or not source.strip():
        return None
    try:
        return lower_locator(spec)
    except UnsupportedSpec:
        return None
    except SyntaxError:
        return None
