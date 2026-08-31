"""Spec tables + predicates (leaf): supported types, geo maps, _check."""
from __future__ import annotations

from .errors import UnsupportedSpec  # noqa: F401


_SUPPORTED = {
    "float", "double", "int", "bool", "angle", "time",
    "vector", "euler", "matrix", "enum", "string", "hex",
    # texture/file interface (mPyFile preset capture): uvCoord (float2) +
    # outColor/borderColor (renderable color3).
    "float2", "color",
    # quaternion: generic compound of 4 doubles (X/Y/Z/W). Scalar only --
    # like color/float2, it is NOT in _ARRAY_OK and is parity-skipped.
    "quaternion",
    # nurbsCurve INPUT: a kNurbsCurve typed attr read into an MFnNurbsCurve so the
    # ported compute can call curve queries in pure C++ (spine). Scalar only (NOT
    # in _ARRAY_OK); parity is loose/skipped (depends on the connected curve).
    "nurbsCurve",
    # mesh / nurbsSurface INPUT: kMesh / kNurbsSurface typed attrs read into an
    # MFnMesh / MFnNurbsSurface so the ported compute can query points/topology.
    # Like nurbsCurve these are INPUT-ONLY on a plain MPxNode (a geo OUTPUT goes
    # through the mPyMesh/mPyNurbsSurface generator types -- enforced in _check).
    # Scalar only (NOT in _ARRAY_OK); parity is loose/skipped.
    "mesh", "nurbsSurface",
}

# Geometry types are readable as an INPUT (MFn* wrap) but have no plain-MPxNode
# OUTPUT setter -- a geo OUTPUT comes only from the geo-generator node types.
# Declaring one as a user OUTPUT attr would pass the _SUPPORTED check then
# KeyError in _OUT_DEFAULT, so _check rejects it loudly.
_GEO_INPUT_ONLY = {"mesh", "nurbsCurve", "nurbsSurface"}

# Types representable as a dense/sparse C++ array (std::vector<_CPP[t]>) on BOTH
# the input read and output write paths (emit_attr._elem_read_expr /
# _elem_set_stmt / _array_gap_default_cpp). string/hex are MString vectors (hex
# round-trips decoded<->encoded per element); color is an MFloatVector (rgb)
# vector; quaternion is an MQuaternion vector via the attr's compound children.
# Geometry and python remain non-array.
_ARRAY_OK = {"float", "double", "int", "bool", "vector", "euler", "matrix",
             "angle", "time", "enum", "string", "hex", "color", "quaternion",
             "float2"}

# float2 arrays are carried as std::vector<MFloatVector> (u=.x, v=.y, .z unused)
# -- reuses the color-array machinery (no new include) with a 2-component
# read/write (asFloat2 / set2Float); see emit_attr._elem_read_expr/_elem_set_stmt.
_CPP = {"float": "float", "double": "double", "int": "int", "bool": "bool",
        "enum": "short", "angle": "double", "time": "double",
        "vector": "MVector", "euler": "MVector", "matrix": "MMatrix",
        "string": "MString", "hex": "MString", "color": "MFloatVector",
        "quaternion": "MQuaternion", "float2": "MFloatVector"}

def _spec_has_hex(spec):
    """True if any user attr (input or output) is a `hex` type -- gates emission
    of the nd_hex_encode/decode helpers and the <string> include."""
    return any(m["meta"].get("type") == "hex" for m in _members(spec))

def _spec_has_nurbs_curve(spec):
    """True if any user attr is a `nurbsCurve` -- gates the curve/point/xform
    includes (MFnNurbsCurve read + om.MTransformationMatrix euler decompose)."""
    return any(m["meta"].get("type") == "nurbsCurve" for m in _members(spec))

def _spec_has_mesh(spec):
    """True if any user attr is a `mesh` -- gates the MFnMesh / point-array
    includes for the mesh INPUT read (procrustes reads self.mesh)."""
    return any(m["meta"].get("type") == "mesh" for m in _members(spec))

def _spec_has_nurbs_surface(spec):
    """True if any user attr is a `nurbsSurface` -- gates the MFnNurbsSurface
    includes for the surface INPUT read."""
    return any(m["meta"].get("type") == "nurbsSurface" for m in _members(spec))

def _spec_has_packed(spec):
    """True if any user attr is a `packed` (typed-array) input -- gates the
    MFn*ArrayData / M*Array includes for the one-handle whole-table read."""
    return any(m["meta"].get("packed") for m in _members(spec))

PORT_BEGIN = "// ===== BEGIN PORTED COMPUTE ====="

PORT_END = "// ===== END PORTED COMPUTE ====="

# Header the boundary handler below needs (MGlobal::displayError). Already in the
# iksolver/locator/transform include lists; the plain-node, geo-generator and
# deformer lists get it ONLY when a lowered body is emitted, so an AI-ported
# node's frag stays byte-identical.
LOWERED_GUARD_INCLUDE = "maya/MGlobal.h"

# Closest-point mesh query header (MMeshIntersector + MPointOnMesh live in the
# same header, which self-includes MPoint/MFloatPoint/MFloatVector/MMatrix/
# MIntArray -- no companions needed). Emitted ONLY when the spec carries
# ``suggested.uses_mesh_intersector``: the porter is forbidden to add #includes,
# and every other node's frag must stay byte-identical.
MESH_INTERSECTOR_INCLUDE = "maya/MMeshIntersector.h"


def lowered_guard(type_name, lowered, on_error, indent="    "):
    """Wrap a deterministically-lowered body in its Maya-entry-point handler.

    A transpiled body can leave by exception: nd_runtime throws
    std::runtime_error for every bad shape/index, and a lowered ``raise``
    (py_to_cpp.st_Raise) throws the same. Nothing in the generated code used to
    catch it, so the compiled node's behaviour on that path was whatever the
    caller happened to do with an escaping exception -- while the interpreted
    node reports the error (base_contract.broadcast_compute_error) and abandons
    the evaluation. Convert it here instead, using the failure convention the
    emitted code already uses everywhere else (MGlobal::displayError +
    MS::kFailure -- see kernels/command_codegen).

    ``on_error`` is the entry point's own abandon-the-evaluation statement(s);
    it differs per hook (an MStatus compute returns kFailure, desiredLocal
    returns the un-driven matrix, the void draw builder empties its buffers).
    The body lines are spliced VERBATIM so the guard cannot perturb them.
    """
    L = [indent + "try {"]
    L += list(lowered)
    L.append(indent + "} catch (const std::exception& _ndErr) {")
    L.append(indent + '    MGlobal::displayError(MString("%s: ") + _ndErr.what());'
             % type_name)
    for stmt in on_error:
        L.append(indent + "    " + stmt)
    L.append(indent + "}")
    return L

_GEO_KIND = {
    "mPyMesh": "mesh",
    "mPyNurbsCurve": "curve",
    "mPyNurbsSurface": "surface",
}

_GEO_INFO = {
    "mesh":    {"attr": "outMesh", "short": "out", "data": "kMesh",
                "fn": "MFnMesh", "datafn": "MFnMeshData", "formns": None},
    "curve":   {"attr": "outCurve", "short": "oc", "data": "kNurbsCurve",
                "fn": "MFnNurbsCurve", "datafn": "MFnNurbsCurveData",
                "formns": "MFnNurbsCurve"},
    "surface": {"attr": "outSurface", "short": "os", "data": "kNurbsSurface",
                "fn": "MFnNurbsSurface", "datafn": "MFnNurbsSurfaceData",
                "formns": "MFnNurbsSurface"},
}

def _geo_kind(spec):
    return _GEO_KIND.get(spec.get("mpy_type"))

def _check(spec):
    base = spec.get("suggested", {}).get("mpx_base")
    # python + message are the ONLY two intentionally-excluded attr types. Reject
    # them here -- BEFORE any family-specific branch -- so the reject is uniform
    # across every node family AND authoritative even for a synthetic/external spec
    # that bypassed the extractor's portability blocker. EVERY other attr type
    # compiles to deterministic pure C++ (this is the whole-directive contract).
    _EXCLUDED = {
        "python": "python carries pickled/base64 data with no native C++ "
                  "representation",
        "message": "message carries no data payload -- it is a pure connection "
                   "marker with nothing to compute",
    }
    for kind in ("inputs", "outputs"):
        for plug, meta in (spec.get(kind) or {}).items():
            t = meta.get("type")
            if t in _EXCLUDED:
                raise UnsupportedSpec(
                    "attr %r type %r is the only kind of attr excluded from "
                    "compilation: %s. Every other attr type compiles."
                    % (plug, t, _EXCLUDED[t]))
    # @maya_command commands are not a compile error on any base: every command is
    # emitted INTO the node's own .bundle (mesh-region templates via
    # command_codegen, everything else via command_dispatch) -- never silently
    # dropped. So _check does NOT reject command-bearing non-locator specs; only
    # the mesh-region path (the locator branch below) validates its own commands.
    if _geo_kind(spec):
        # Geometry generators emit a typed geo data attr; their only "output"
        # is the built mesh/curve/surface. Validate portability + that user
        # INPUT attrs (if any) are plain scalar types.
        if not spec.get("portability", {}).get("portable", False):
            raise UnsupportedSpec(
                "spec is not portable: %s"
                % "; ".join(spec.get("portability", {}).get("blockers", [])))
        for plug, meta in (spec.get("inputs") or {}).items():
            t = meta.get("type")
            if t not in _SUPPORTED:
                raise UnsupportedSpec(
                    "geo-generator input %r type %r unsupported" % (plug, t))
            # Array inputs read into std::vector<T> via _array_read_lines, OR a geo
            # array into std::vector<Nd<Kind>> via emit_geo_io.geo_array_input_lines
            # (emit_geo uses the same machinery as the generic MPxNode). Every
            # _ARRAY_OK element type + geo (_GEO_INPUT_ONLY) is representable; any
            # other array element (python) fails LOUD here instead of emitting a
            # silently-wrong scalar read.
            if (meta.get("is_array") and t not in _ARRAY_OK
                    and t not in _GEO_INPUT_ONLY):
                raise UnsupportedSpec(
                    "geo-generator input %r is an array of %r (arrays support: %s)"
                    % (plug, t, ", ".join(sorted(_ARRAY_OK))))
        return
    if base == _TRANSFORM_BASE:
        # Custom transform: the matrix hook is MPxTransformationMatrix::
        # desiredLocal(). The scaffold exposes the live TRS frame implicitly and
        # drives offsetParentMatrix via the gated local-matrix sinks
        # (self.local_matrix + self.apply_*). A SCALAR MATRIX input takes the
        # bespoke matrix path; every other scalar goes through
        # emit_transform._transform_generic_inputs -> a findPlug read into an
        # ``in_a<ident>`` local, bound by nd_lower._materialise_input or handed to
        # the AI porter. ARRAY inputs and geometry ride those same shared readers,
        # so EVERY non-excluded attr type is accepted as a transform input.
        if not spec.get("portability", {}).get("portable", False):
            raise UnsupportedSpec(
                "spec is not portable: %s"
                % "; ".join(spec.get("portability", {}).get("blockers", [])))
        for plug, meta in (spec.get("inputs") or {}).items():
            t = meta.get("type")
            if t not in _SUPPORTED:
                raise UnsupportedSpec(
                    "transform input %r type %r unsupported (allowed: %s)"
                    % (plug, t, ", ".join(sorted(_SUPPORTED))))
        # A transform's output is the node's own local/offsetParentMatrix (the
        # _outLocalFlat carrier relayed into offsetParentMatrix); a user OUTPUT
        # attr has no sink and would be silently dropped -- reject it LOUD, as the
        # iksolver/deformer branches do for their inherent-output contracts.
        if (spec.get("outputs") or {}):
            raise UnsupportedSpec(
                "transform output is the node's local/offsetParentMatrix; user "
                "OUTPUT attrs (%s) are not supported"
                % ", ".join((spec.get("outputs") or {}).keys()))
        return
    if base == _LOCATOR_BASE:
        # A locator's "output" is its viewport draw, not DG attrs. Its draw
        # buffers (lines/points/text/shapes = f(time)) are marshalled by the
        # generated MPxDrawOverride, so what matters is the portability of the
        # draw expression. Numeric scalars + string + color are wired in by the
        # bespoke _loc_*_inputs paths; every other scalar, ARRAY input and
        # geometry rides emit_locator._loc_generic_inputs -> the shared readers,
        # marshalled through the Inputs POD. So EVERY non-excluded attr type is
        # accepted -- any number of meshes included (meshes[0] drives the region
        # draw).
        if not spec.get("portability", {}).get("portable", False):
            raise UnsupportedSpec(
                "spec is not portable: %s"
                % "; ".join(spec.get("portability", {}).get("blockers", [])))
        nmesh = 0
        for plug, meta in (spec.get("inputs") or {}).items():
            t = meta.get("type")
            if t not in _SUPPORTED:
                raise UnsupportedSpec(
                    "locator input %r type %r unsupported (allowed: %s) -- it "
                    "would be silently dropped from the compiled node's draw"
                    % (plug, t, ", ".join(sorted(_SUPPORTED))))
            if t == "mesh" and not meta.get("is_array"):
                nmesh += 1
        # @maya_command commands: one without a deterministic native template is
        # not rejected -- it rides command_dispatch's generic MPxCommand. Only the
        # mesh-region commands are validated here: they compile into the .bundle
        # and need a mesh input to connect/draw. classify_command is pure (no maya).
        from mpynode.native.compiler.kernels import command_codegen as _cc
        cmds = spec.get("commands") or []
        region_cmds = [c for c in cmds if _cc.classify_command(c) is not None]
        if region_cmds and nmesh == 0:
            raise UnsupportedSpec(
                "mesh-region command(s) %s require a mesh input to connect into "
                "and draw, but the node has none -- the command auto-connect and "
                "the region draw would be silent no-ops"
                % ", ".join(repr(c.get("name")) for c in region_cmds))
        # A locator's output is its viewport draw, not DG data; a user OUTPUT attr
        # has no sink and would be silently dropped -- reject it LOUD, mirroring the
        # iksolver/deformer inherent-output gates.
        if (spec.get("outputs") or {}):
            raise UnsupportedSpec(
                "locator output is its viewport draw; user OUTPUT attrs (%s) are "
                "not supported"
                % ", ".join((spec.get("outputs") or {}).keys()))
        return
    if base == _IKSOLVER_BASE:
        # IK solver: the joint/handle/pole/twist contract is fixed and marshalled
        # by doSolve(). Numeric scalar INPUTS ride emit_iksolver's bespoke path;
        # every other scalar, ARRAY input and geometry rides _ik_generic_inputs ->
        # the shared readers into an ``in_a<ident>`` local handed to the AI porter.
        # So EVERY non-excluded attr type is accepted as a solver input. Output is
        # joint rotations/translates -- no user OUTPUT attrs.
        if not spec.get("portability", {}).get("portable", False):
            raise UnsupportedSpec(
                "spec is not portable: %s"
                % "; ".join(spec.get("portability", {}).get("blockers", [])))
        for plug, meta in (spec.get("inputs") or {}).items():
            t = meta.get("type")
            if t not in _SUPPORTED:
                raise UnsupportedSpec(
                    "iksolver input %r type %r unsupported (allowed: %s)"
                    % (plug, t, ", ".join(sorted(_SUPPORTED))))
        if (spec.get("outputs") or {}):
            raise UnsupportedSpec(
                "iksolver output is joint rotations/translates; user OUTPUT "
                "attrs (%s) are not supported"
                % ", ".join((spec.get("outputs") or {}).keys()))
        return
    if base not in _SUPPORTED_BASES:
        raise UnsupportedSpec(
            "unsupported base %r; supported: %s "
            "(locator/transform come later)" % (base, ", ".join(_SUPPORTED_BASES))
        )
    if not spec.get("portability", {}).get("portable", False):
        raise UnsupportedSpec(
            "spec is not portable: %s"
            % "; ".join(spec.get("portability", {}).get("blockers", []))
        )
    if base in _DEFORMER_BASES and (spec.get("outputs") or {}):
        raise UnsupportedSpec(
            "deformer-family nodes drive inherited geometry via deform(); "
            "user-defined OUTPUT attrs (%s) are not supported -- the output is "
            "the deformed mesh" % ", ".join((spec.get("outputs") or {}).keys()))
    for kind in ("inputs", "outputs"):
        for plug, meta in (spec.get(kind) or {}).items():
            t = meta.get("type")
            if t not in _SUPPORTED:
                raise UnsupportedSpec(
                    "attr %r type %r unsupported" % (plug, t))
            # Geometry compiles in ALL four cells on a plain MPxNode: single
            # INPUT (MFn* read), single OUTPUT (Nd<Kind> build+set), and array
            # IN/OUT (std::vector<Nd<Kind>>, emit_geo_io). Geo is NOT in
            # _ARRAY_OK -- that set drives the numeric _CPP path, which has no
            # geo element type -- so geo arrays skip the gate below.
            if (meta.get("is_array") and t not in _ARRAY_OK
                    and t not in _GEO_INPUT_ONLY):
                raise UnsupportedSpec(
                    "attr %r is an array of %r (arrays support: %s)"
                    % (plug, t, ", ".join(sorted(_ARRAY_OK))))

def _num_default(meta, cast=float, fallback="0.0"):
    v = meta.get("default_value")
    if v is None:
        return fallback
    try:
        return repr(cast(v))
    except Exception:
        return fallback


# --- sibling imports at end of module: spec_model is imported first by the
# package facade, so pulling these at the top would create an import cycle
# (emit_* -> emit_attr -> spec_model). Every spec_model name above is defined by
# now, so the emit_* modules can safely ``from .spec_model import ...``.
from .emit_attr import _members  # noqa: E402,F401
from .emit_deformer import _DEFORMER_BASES  # noqa: E402,F401
from .emit_iksolver import _IKSOLVER_BASE  # noqa: E402,F401
from .emit_locator import _LOCATOR_BASE  # noqa: E402,F401
from .emit_transform import _TRANSFORM_BASE  # noqa: E402,F401
_SUPPORTED_BASES = ("MPxNode",) + _DEFORMER_BASES
