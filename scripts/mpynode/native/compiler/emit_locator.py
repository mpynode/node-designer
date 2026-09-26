"""MPxLocatorNode + MPxDrawOverride emission."""
from __future__ import annotations

import ast

from .spec_model import (PORT_BEGIN, PORT_END, lowered_guard,
                         LOWERED_GUARD_INCLUDE)
from .emit_attr import (_ident, _create_lines, _read_plug_decl,
                        _read_plug_assign, _read_plug_array_decl,
                        _read_plug_array_assign, findplug_family_extras,
                        findplug_local_hint)
from . import emit_geo_io
from .nd_runtime import _nd_runtime_cpp
from mpynode.native.compiler.kernels import nd_io_cpp
from mpynode.native.compiler.kernels import locator_draw_cpp


_LOCATOR_BASE = "MPxLocatorNode"

_LOCATOR_INCLUDES_COMMON = [
    "cmath", "vector", "cstdio", "cstdlib", "string", "algorithm", "map",
    "random", "cstdint",
    "maya/MPoint.h", "maya/MColor.h", "maya/MVector.h", "maya/MString.h",
    "maya/MUserData.h",
]

_LOCATOR_INCLUDES_PLUGIN = [
    # MObjectHandle: every locator now keys its drawn extent by node hash
    # (boundingBox / _setBBox), not just the hover + stored-var builds.
    # MApiNamespace.h only forward-declares it, which reads as C2027.
    "maya/MObjectHandle.h",
    "maya/MPxLocatorNode.h", "maya/MFnPlugin.h", "maya/MTypeId.h",
    "maya/MMatrix.h", "maya/MBoundingBox.h", "maya/MTransformationMatrix.h",
    "maya/MDagPath.h", "maya/MObject.h", "maya/MFnDependencyNode.h",
    "maya/MPlug.h", "maya/MAnimControl.h", "maya/MTime.h",
    "maya/MStatus.h", "maya/MGlobal.h", "maya/MSelectionList.h",
    "maya/MDrawRegistry.h", "maya/MPxDrawOverride.h", "maya/MUIDrawManager.h",
    "maya/MFrameContext.h", "maya/MViewport2Renderer.h",
    "maya/MHWGeometryUtilities.h",
    "maya/MPointArray.h", "maya/MColorArray.h", "maya/MIntArray.h",
    # attribute function sets for initialize() (recreates the user input plugs)
    "maya/MFnNumericAttribute.h", "maya/MFnEnumAttribute.h",
    "maya/MFnTypedAttribute.h", "maya/MFnNumericData.h", "maya/MFnData.h",
]

_LOCATOR_INCLUDES_MESH = [
    "maya/MFnMesh.h", "maya/MFloatVectorArray.h", "maya/MFn.h",
    # Component tags travel on the mesh DATA, not the MFnMesh -- see the
    # RegionMesh tag table and tag_indices() below.
    "maya/MFnGeometryData.h", "maya/MFnSingleIndexedComponent.h",
    "maya/MStringArray.h",
]

# Cross-frame stored-var persistence WITHOUT the hover service (no Qt, no
# timer): just the per-node map keyed by node hash + its delete/scene teardown.
_LOCATOR_INCLUDES_TWEEN = [
    "maya/MObjectHandle.h", "maya/MNodeMessage.h", "maya/MSceneMessage.h",
    "maya/MMessage.h",
]

_LOCATOR_INCLUDES_HOVER = [
    "chrono", "set",
    "maya/M3dView.h", "maya/MItDependencyNodes.h", "maya/MFnDagNode.h",
    "maya/MObjectHandle.h", "maya/MTimerMessage.h", "maya/MSceneMessage.h",
    "maya/MNodeMessage.h", "maya/MMessage.h", "maya/MFn.h",
    "QtCore/QPoint", "QtGui/QCursor", "QtWidgets/QWidget",
]

# Generic-input headers. MMatrix is used in the SHARED Inputs/computeBuffers
# region (compiled by BOTH the plugin AND the standalone probe) so it rides the
# common pre-#ifndef block; attr-function-set + plug-read headers are plugin-only
# (initialize()/prepareForDraw() live inside #ifndef MPYNODE_PROBE).
_LOCATOR_INCLUDES_GENERIC_COMMON = ["maya/MMatrix.h"]
_LOCATOR_INCLUDES_GENERIC_PLUGIN = [
    "maya/MFnUnitAttribute.h", "maya/MFnCompoundAttribute.h",
    "maya/MFnMatrixAttribute.h", "maya/MFnMatrixData.h", "maya/MAngle.h",
    # base function set: the only one that covers every generic attr type
    # uniformly for setAffectsAppearance (see the generics loop in initialize())
    "maya/MFnAttribute.h",
]

def _loc_scalar_inputs(spec):
    """Scalar user inputs (float/int/bool/enum) wired into the draw."""
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        t = meta.get("type")
        if t in ("float", "int", "bool", "enum") and not meta.get("is_array"):
            out.append({"plug": plug, "member": "in_" + _ident(plug),
                        "type": t, "enum_names": meta.get("enum_names") or [],
                        "default_value": meta.get("default_value")})
    return out

def _loc_mesh_inputs(spec):
    """SINGLE mesh user inputs (drive extract_region in the draw).

    Array meshes ride the generic geo path (std::vector<NdMesh>) instead."""
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        if meta.get("type") == "mesh" and not meta.get("is_array"):
            out.append({"plug": plug, "member": _ident(plug)})
    return out

def _loc_scalar_bespoke(meta):
    """True when this input is served by one of the bespoke, byte-identical
    single-value paths above (scalar numeric / string / color / single mesh).
    Everything else -- every remaining scalar type AND every ARRAY of any type,
    geometry included -- rides the shared findPlug readers."""
    if meta.get("is_array"):
        return False
    return meta.get("type") in ("float", "int", "bool", "enum", "string",
                                "color", "mesh")

def _loc_string_inputs(spec):
    """String user inputs wired into the draw (e.g. animated_text's displayText).

    Read as an MString from the plug and seeded into computeBuffers as
    ``in_<name>`` so the draw expression can push it into ``data.textStr``.
    """
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        if meta.get("type") == "string" and not meta.get("is_array"):
            out.append({"plug": plug, "member": "in_" + _ident(plug),
                        "default_value": meta.get("default_value")})
    return out

def _loc_color_inputs(spec):
    """Color user inputs wired into the draw (e.g. mesh_regions' defaultColor /
    hoverColor / selectColor). A ``color`` attr is a 3-float compound
    (MFnNumericAttribute::createColor); read as RGB into ``in_<name>[3]`` and
    exposed to the draw expression as an ``MColor``. Alpha is a SEPARATE scalar
    input when the node wants one (mesh_regions has an ``alpha`` float)."""
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        if meta.get("type") == "color" and not meta.get("is_array"):
            out.append({"plug": plug, "member": "in_" + _ident(plug),
                        "default_value": meta.get("default_value")})
    return out

def _loc_color_default(val):
    """"r, g, b" C++ float initialiser for a color default (3-seq or None)."""
    try:
        r, g, b = (float(val[0]), float(val[1]), float(val[2]))
        return "%sf, %sf, %sf" % (repr(r), repr(g), repr(b))
    except Exception:
        return "0.0f, 0.0f, 0.0f"

# Every user INPUT not served by a bespoke path (_loc_scalar_bespoke) is wired
# into the draw via the shared findPlug readers and the same Inputs-POD
# marshalling: the remaining scalar types, ARRAYS of any type, and geometry.
# element count for the compound (C-array) generic types (scalar/matrix absent).
_LOC_GENERIC_ARITY = {"vector": 3, "euler": 3, "quaternion": 4, "float2": 2}
# element C-type for those compounds (float2 is float; the rest double).
_LOC_GENERIC_ELEM = {"vector": "double", "euler": "double",
                     "quaternion": "double", "float2": "float"}

def _loc_generic_inputs(spec):
    """Generic (non-scalar/string/color/mesh) user INPUT attrs wired into the
    draw. Canonical ``m`` dicts (member ``a_<ident>``) so emit_attr._create_lines
    (plug create) + _read_plug_decl/_read_plug_assign (the findPlug read) consume
    them unchanged; the read local (``in_a_<ident>``) is copied into the Inputs
    POD and re-exposed to the porter inside computeBuffers -- mirroring the
    existing color/string marshalling. Locator draw math is always AI-ported."""
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        if _loc_scalar_bespoke(meta):
            continue
        out.append({"plug": plug, "member": "a_" + _ident(plug),
                    "meta": meta, "kind": "inputs"})
    return out

def _loc_generic_field(gm):
    """Inputs-POD field decl (same C++ shape as the read local, named by member
    -- e.g. ``double a_x[3] = {...};``). Arrays/geometry carry their value type
    (std::vector<T> / Nd<Kind>), which copies into the POD by assignment."""
    mem, meta = gm["member"], gm["meta"]
    if emit_geo_io.is_geo(meta["type"]):
        return emit_geo_io.geo_plug_decls(gm)[0].replace("in_" + mem, mem, 1)
    if meta.get("is_array"):
        return _read_plug_array_decl(gm).replace("in_" + mem, mem, 1)
    return _read_plug_decl(gm).replace("in_" + mem, mem, 1)

def _loc_generic_copy(gm):
    """Copy the findPlug read local ``in_<member>`` into ``inp.<member>``."""
    mem, meta = gm["member"], gm["meta"]
    # vectors and Nd<Kind> structs assign wholesale; only the fixed C-array
    # compounds need the element loop.
    if meta.get("is_array") or emit_geo_io.is_geo(meta["type"]):
        return "    inp.%s = in_%s;" % (mem, mem)
    ar = _LOC_GENERIC_ARITY.get(meta["type"])
    if ar:
        return ("    for (int _k = 0; _k < %d; ++_k) inp.%s[_k] = in_%s[_k];"
                % (ar, mem, mem))
    return "    inp.%s = in_%s;" % (mem, mem)

def _loc_generic_expose(gm):
    """computeBuffers porter-local exposing ``inp.<member>`` as ``in_<member>``."""
    mem, meta = gm["member"], gm["meta"]
    t = meta["type"]
    if emit_geo_io.is_geo(t) or meta.get("is_array"):
        # one const-ref binding covers std::vector<T>, Nd<Kind> and their lists.
        decl  = _loc_generic_field(gm).strip().rstrip(";")
        ctype = decl[:decl.rfind(" ")].strip()
        return ("    const %s& in_%s = inp.%s; (void)in_%s;"
                % (ctype, mem, mem, mem))
    ar = _LOC_GENERIC_ARITY.get(t)
    if ar:
        return ("    const %s (&in_%s)[%d] = inp.%s; (void)in_%s;"
                % (_LOC_GENERIC_ELEM[t], mem, ar, mem, mem))
    if t == "matrix":
        return "    const MMatrix& in_%s = inp.%s; (void)in_%s;" % (mem, mem, mem)
    if t in ("string", "hex"):
        return "    const MString& in_%s = inp.%s; (void)in_%s;" % (mem, mem, mem)
    if t in ("int", "bool", "enum"):
        return ("    const %s in_%s = inp.%s; (void)in_%s;"
                % ({"int": "int", "bool": "bool", "enum": "short"}[t],
                   mem, mem, mem))
    return "    const double in_%s = inp.%s; (void)in_%s;" % (mem, mem, mem)

def _loc_generic_hint(t):
    """C++ shape of a generic input's ``in_a<ident>`` local (PORT comment)."""
    return {
        "double": "double", "angle": "double, RADIANS", "time": "double, seconds",
        "vector": "double[3]; .x==[0]", "euler": "double[3], RADIANS",
        "quaternion": "double[4] {x,y,z,w}", "float2": "float[2]",
        "matrix": "MMatrix; m(row,col)",
    }.get(t, t)

def _loc_implicit_stored_vars(src):
    """Cross-frame state a draw expression keeps WITHOUT declaring it: written
    as ``self.X = ...`` and read back as ``getattr(self, "X", <literal>)``.

    Elastic hover tweens are written this way, so spec["variables"] was empty
    and the g_tween struct came out as a bare ``char _unused;`` -- every read
    then folded to its seed and the hover blend was pinned at 0.

    Only the PAIRED form is promoted: the getattr default is the sole source of
    both the C++ type and the seed, so a name that is only ever written has
    neither. Framework slots (self.draw, self.auto_refresh, ...) are excluded --
    they already route to their own DrawData fields."""
    try:
        tree = ast.parse(src or "")
    except (SyntaxError, ValueError):
        return {}
    from mpynode.wrappers.mpy_locator import MPyLocator
    reserved = set(n for n, _rw, _doc in MPyLocator.INTERNAL_API_SLOTS)
    written, defaults = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            for tgt in targets:
                if (isinstance(tgt, ast.Attribute)
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == "self"):
                    written.add(tgt.attr)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "getattr" and len(node.args) == 3
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "self"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            try:
                val = ast.literal_eval(node.args[2])
            except (ValueError, SyntaxError):
                continue
            # bool before int: isinstance(True, int) is True
            if isinstance(val, bool):
                kind = "bool"
            elif isinstance(val, int):
                kind = "int"
            elif isinstance(val, float):
                kind = "float"
            else:
                continue
            defaults[node.args[1].value] = {"kind": kind, "value": val}
    # sorted: struct field order is .cpp bytes, it must not ride set ordering
    return {n: defaults[n] for n in sorted(defaults)
            if n in written and n not in reserved}

def _loc_stored_vars(spec):
    """Stored vars seeded into the draw as mutable locals, persisted across
    frames in the g_tween map (hover or not -- see _locator_hover_service)."""
    out    = []
    merged = dict(spec.get("variables") or {})
    for name, meta in _loc_implicit_stored_vars(spec.get("compute")).items():
        merged.setdefault(name, meta)
    for name, meta in merged.items():
        kind = meta.get("kind")
        val  = meta.get("value")
        if kind == "bool":
            ctype, seed = "bool", ("true" if val else "false")
        elif kind == "int":
            ctype, seed = "long", ("%d" % int(val if val is not None else 0))
        elif kind == "float":
            ctype, seed = "double", repr(float(val) if val is not None else 0.0)
        else:
            # Non-scalar / unknown stored vars cannot be seeded as a scalar
            # local; skip (the expression must not depend on it for parity).
            continue
        out.append({"name": _ident(name), "ctype": ctype, "seed": seed})
    return out

def _loc_input_default(t, val, enum_names):
    if t == "bool":
        return "true" if val else "false"
    if t == "enum":
        try:
            return "%d" % int(val)
        except Exception:
            return "0"
    if t == "int":
        try:
            return "%d" % int(val)
        except Exception:
            return "0"
    # float
    try:
        return "%sf" % repr(float(val))
    except Exception:
        return "0.0f"

def _loc_input_ctype(t):
    return {"float": "float", "int": "int", "bool": "bool", "enum": "short"}[t]

def _loc_input_read(member, plug, t):
    """C++ to read one scalar input plug into inp.<member> (plugin side)."""
    acc = {"float": "asFloat", "int": "asInt", "bool": "asBool",
           "enum": "asShort"}[t]
    return [
        "    { MStatus _ms; MPlug _p = fn.findPlug(\"%s\", false, &_ms);" % plug,
        "      if (_ms == MS::kSuccess && !_p.isNull()) inp.%s = _p.%s(); }"
        % (member, acc),
    ]

_LOCATOR_MESH_HELPERS = r'''
// ---- mesh-region helpers (mirror mpynode/_common/mesh_region.py) ----------
struct RegionMesh {
    bool present;
    std::vector<MPoint>  pts;       // vertex positions
    std::vector<int>     counts;    // per-face vertex counts
    std::vector<int>     connects;  // flat polygon-vertex connectivity
    std::vector<MVector> normals;   // per-vertex unit normals (aligned to pts)
    // COMPONENT TAGS, read off the mesh DATA (MFnGeometryData) when the input is
    // read -- parallel arrays, tag name -> component ids. They are carried here
    // because the compute is pure math over this struct and cannot itself do a
    // scene/plug query; the reader can, so it does it once and hands the table
    // over. Empty when the input carries no tags (or for emitters that do not
    // populate it, e.g. the ik solver's floor mesh).
    std::vector<std::string>       tagNames;
    std::vector<std::vector<int> > tagIds;
    // The SOURCE TRANSFORM, off the same MFnGeometryData. worldMesh[0] data
    // carries OBJECT-space points plus this matrix -- it does NOT bake world
    // points, and a data-built function set has no DAG path, so getPoints(
    // kWorld) cannot reach world space. Row-major, Maya's row-vector
    // convention (translation in [12..14]); identity when absent, so a mesh
    // with no transform (or an emitter that does not populate it) is a no-op.
    // A plain double[16] rather than an MMatrix: MMatrix.h is plugin-only and
    // these helpers must also compile in the -DMPYNODE_PROBE translation unit.
    double matrix[16];
    RegionMesh() : present(false) {
        for (int _i = 0; _i < 16; ++_i) matrix[_i] = (_i % 5) ? 0.0 : 1.0;
    }
};
// tag_indices(mesh, name): component ids for a named component tag, or empty.
// Mirrors component_tags.tag_indices_from_mesh_data -- an absent tag reads as
// EMPTY (the same blank the Python draws for a tag that matches nothing).
static std::vector<int> tag_indices(const RegionMesh& mesh,
                                    const std::string& name) {
    for (size_t _i = 0; _i < mesh.tagNames.size(); ++_i) {
        if (mesh.tagNames[_i] == name) return mesh.tagIds[_i];
    }
    return std::vector<int>();
}
static std::vector<int> tag_indices(const RegionMesh& mesh,
                                    const MString& name) {
    return tag_indices(mesh, std::string(name.asChar()));
}
// mesh_matrix / mesh_to_world / mesh_dir_to_world: the mesh input's own
// transform. Mirror component_tags.mesh_matrix_from_mesh_data. Use these to
// place a patch in WORLD space -- reading the points alone gives OBJECT space,
// which draws the region at the origin no matter where the mesh is.
static const double* mesh_matrix(const RegionMesh& mesh) {
    return mesh.matrix;
}
static MPoint mesh_to_world(const RegionMesh& mesh, const MPoint& p) {
    const double* m = mesh.matrix;
    return MPoint(p.x * m[0] + p.y * m[4] + p.z * m[8]  + m[12],
                  p.x * m[1] + p.y * m[5] + p.z * m[9]  + m[13],
                  p.x * m[2] + p.y * m[6] + p.z * m[10] + m[14]);
}
// Directions ignore translation. Uniform/rigid transforms are the norm here, so
// the 3x3 is applied and re-normalized rather than an inverse-transpose.
static MVector mesh_dir_to_world(const RegionMesh& mesh, const MVector& v) {
    const double* m = mesh.matrix;
    MVector o(v.x * m[0] + v.y * m[4] + v.z * m[8],
              v.x * m[1] + v.y * m[5] + v.z * m[9],
              v.x * m[2] + v.y * m[6] + v.z * m[10]);
    double _l = o.length();
    return (_l > 1e-12) ? (o / _l) : v;
}
struct RegionBuffer {
    std::vector<MPoint>  points;    // compacted region vertices
    std::vector<int>     indices;   // remapped (0..U-1) connectivity
    std::vector<int>     counts;    // per-face vertex counts (selection order)
    std::vector<MVector> normals;   // per-vertex normals (aligned to points)
};
// extract_region(mesh, faceIds, withNormals): compact the given faces into a
// (points, indices, counts[, normals]) buffer. np.unique(return_inverse=True)
// => ascending-sorted unique vertices + inverse remap (must match for parity).
static RegionBuffer extract_region(const RegionMesh& mesh,
                                   const std::vector<int>& faceIds,
                                   bool withNormals) {
    RegionBuffer out;
    if (!mesh.present || faceIds.empty() || mesh.counts.empty()) return out;
    const int F = (int)mesh.counts.size();
    std::vector<int> faceOff(F, 0);                 // exclusive prefix sum
    for (int f = 1; f < F; ++f) faceOff[f] = faceOff[f - 1] + mesh.counts[f - 1];
    std::vector<int> valid;                          // keep valid ids, in order
    for (size_t k = 0; k < faceIds.size(); ++k) {
        int fid = faceIds[k];
        if (fid >= 0 && fid < F) valid.push_back(fid);
    }
    if (valid.empty()) return out;
    std::vector<int> regionVerts, selCounts;
    for (size_t k = 0; k < valid.size(); ++k) {
        int fid = valid[k];
        int c = mesh.counts[fid];
        int s = faceOff[fid];
        selCounts.push_back(c);
        for (int j = 0; j < c; ++j) {
            int pos = s + j;
            if (pos >= 0 && pos < (int)mesh.connects.size())
                regionVerts.push_back(mesh.connects[pos]);
        }
    }
    if (regionVerts.empty()) return out;
    std::vector<int> uniq(regionVerts);              // sorted-unique
    std::sort(uniq.begin(), uniq.end());
    uniq.erase(std::unique(uniq.begin(), uniq.end()), uniq.end());
    std::map<int, int> remap;
    for (size_t i = 0; i < uniq.size(); ++i) remap[uniq[i]] = (int)i;
    out.indices.reserve(regionVerts.size());
    for (size_t i = 0; i < regionVerts.size(); ++i)
        out.indices.push_back(remap[regionVerts[i]]);
    out.counts = selCounts;
    out.points.reserve(uniq.size());
    for (size_t i = 0; i < uniq.size(); ++i) {
        int g = uniq[i];
        out.points.push_back((g >= 0 && g < (int)mesh.pts.size())
                                 ? mesh.pts[g] : MPoint(0, 0, 0));
    }
    if (withNormals) {
        out.normals.reserve(uniq.size());
        for (size_t i = 0; i < uniq.size(); ++i) {
            int g = uniq[i];
            out.normals.push_back((g >= 0 && g < (int)mesh.normals.size())
                                      ? mesh.normals[g] : MVector(0, 0, 0));
        }
    }
    return out;
}
'''

_MESH_QUERY_HELPERS = r'''
// ---- closest-vertex queries on a RegionMesh (deterministic, O(N)) ----------
static int rm_closestVertex(const RegionMesh& m, const MPoint& p) {
    int best = -1; double bd = 1e300;
    for (size_t i = 0; i < m.pts.size(); ++i) {
        double dx = m.pts[i].x - p.x, dy = m.pts[i].y - p.y, dz = m.pts[i].z - p.z;
        double d = dx * dx + dy * dy + dz * dz;       // squared distance is enough
        if (d < bd) { bd = d; best = (int)i; }
    }
    return best;
}
static MVector rm_normalAt(const RegionMesh& m, int vid) {
    return (vid >= 0 && vid < (int)m.normals.size()) ? m.normals[vid] : MVector(0, 1, 0);
}
'''

def _locator_hover_service(cls, data_cls, svars, needs_hover=True):
    """Emit the file-static passive-hover + idle-refresh + stored-var service
    (anonymous namespace, plugin-only). A direct C++ port of
    mpynode/_common/{hover_tracker,draw_refresh}.py:

      * one 30fps MTimerMessage casts the cursor ray (HiDPI-correct) and records
        the hovered locator -> ``self.hovered``;
      * the same tick redraws every ``self.auto_refresh`` node so the elastic
        tween advances even when nothing in the DG changed (and even when the
        cursor has left the gizmo);
      * stored vars persist across frames in ``g_tween`` -- a file-static
        per-node map keyed by node hash (review MF-4: NOT MUserData, whose
        per-object reuse isn't guaranteed and diverges across viewports).

    Crash safety mirrors the Python originals: MObjectHandle.isValid() guards +
    kBeforeNew/kBeforeOpen/kMayaExiting teardown. GUI-only: the timer never
    starts outside MGlobal::kInteractive, so headless/probe stays untouched.

    With ``needs_hover`` False only the stored-var half is emitted: the same
    ``g_tween`` map + per-node/scene teardown, minus the cursor ray, the timer
    and the idle redraw (so a non-hover node still links no Qt). The
    interpreted locator commits stored vars EVERY evaluation regardless of
    hover, so the compiled one must persist them regardless of hover too.
    """
    tween_cls = cls + "Tween"
    L         = []
    if needs_hover:
        L.append("// ===== passive hover + idle-refresh service (needs_hover) ==========")
        L.append("// Port of mpynode/_common/{hover_tracker,draw_refresh}.py. One")
        L.append("// session 30fps timer casts the cursor ray to find the hovered")
        L.append("// locator (self.hovered) and redraws auto_refresh nodes so the tween")
        L.append("// keeps advancing. Stored vars persist in a file-static per-node map.")
    else:
        L.append("// ===== stored-var persistence service ==============================")
        L.append("// This locator has no hover/idle-refresh needs, but it DOES mutate")
        L.append("// stored vars: the interpreted node commits them back every draw")
        L.append("// evaluation, so they persist across frames here too -- the same")
        L.append("// file-static per-node map, without the cursor ray or the timer.")
    L.append("namespace {")
    L.append("struct %s {" % tween_cls)
    for v in svars:
        L.append("    %s %s = %s;   // seed == Inputs sv_%s default (lockstep)"
                 % (v["ctype"], v["name"], v["seed"], v["name"]))
    if not svars:
        L.append("    char _unused;  // no stored vars; keep the type non-empty")
    L.append("};")
    L.append("static std::map<unsigned, %s> g_tween;            // per-node cross-frame state" % tween_cls)
    if needs_hover:
        L.append("static std::map<unsigned, MObjectHandle> g_handles;     // hash -> handle")
        L.append("static std::map<unsigned, std::vector<MPoint> > g_hoverTris;  // precise-hover soup (local space)")
        L.append("static std::set<unsigned> g_autoRefresh;                // nodes wanting idle redraw")
    L.append("static std::map<unsigned, MCallbackId> g_removalCbs;    // per-node delete callbacks")
    if needs_hover:
        L.append("static bool          g_hoverValid = false;")
        L.append("static unsigned      g_hoverHash  = 0;")
        L.append("static MObjectHandle g_hoverHandle;")
        L.append("static MCallbackId   g_timerId = 0;")
        L.append("static double        g_lastDirtyT = -1.0;  // wall time of the last idle-redraw request (-1 = never)")
        L.append("static double        g_cpuAtDirty = 0.0;   // main-thread CPU seconds at that request")
        L.append("static double        g_lastRedraw = 0.0;   // CPU seconds the last request turned out to cost")
    L.append("static std::vector<MCallbackId> g_sceneCbs;")
    L.append("static bool          g_started = false;")
    L.append("")
    if needs_hover:
        L.append("static double _wallClock() {")
        L.append("    using namespace std::chrono;")
        L.append("    static const steady_clock::time_point t0 = steady_clock::now();")
        L.append("    return duration_cast<duration<double> >(steady_clock::now() - t0).count();")
        L.append("}")
        L.append("static double _epochClock() {")
        L.append("    // self.wallclock: seconds since the epoch -- the same clock and ORIGIN as")
        L.append("    // Python's time.time(), so a compiled and an interpreted gizmo side by")
        L.append("    // side sit at the same phase, not just the same speed.")
        L.append("    using namespace std::chrono;")
        L.append("    return duration_cast<duration<double> >(system_clock::now().time_since_epoch()).count();")
        L.append("}")
        L.append("static double _threadCpu() {")
        L.append("    // CPU seconds consumed by THIS (the main) thread. An idle main thread")
        L.append("    // consumes none, so the CPU spent since our last request is what")
        L.append("    // servicing it cost -- evaluation, prepareForDraw and draw -- with no")
        L.append("    // dependence on when Maya delivers its events.")
        L.append("#ifdef _WIN32")
        L.append("    FILETIME _c, _e, _k, _u;")
        L.append("    if (!GetThreadTimes(GetCurrentThread(), &_c, &_e, &_k, &_u)) return 0.0;")
        L.append("    const unsigned long long _kt = ((unsigned long long)_k.dwHighDateTime << 32) | _k.dwLowDateTime;")
        L.append("    const unsigned long long _ut = ((unsigned long long)_u.dwHighDateTime << 32) | _u.dwLowDateTime;")
        L.append("    return (double)(_kt + _ut) * 1e-7;")
        L.append("#else")
        L.append("    struct timespec _ts;")
        L.append("    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &_ts) != 0) return 0.0;")
        L.append("    return (double)_ts.tv_sec + (double)_ts.tv_nsec * 1e-9;")
        L.append("#endif")
        L.append("}")
        L.append("static bool _isHovered(unsigned hash) { return g_hoverValid && g_hoverHash == hash; }")
        L.append("static void _registerNode(unsigned hash, const MObject& node) { g_handles[hash] = MObjectHandle(node); }")
        L.append("static void _setHoverTris(unsigned hash, const std::vector<MPoint>& t) {")
        L.append("    if (t.size() >= 3) g_hoverTris[hash] = t; else g_hoverTris.erase(hash);")
        L.append("}")
        L.append("static void _clearHoverTris(unsigned hash) { g_hoverTris.erase(hash); }")
        L.append("")
    L.append("// Per-node delete teardown (mirrors draw_refresh.addNodePreRemovalCallback /")
    L.append("// hover_tracker.addNodeRemovedCallback): evict THIS node's state so it")
    L.append("// doesn't leak and -- crucially -- so a later node that reuses the freed")
    L.append("// MObjectHandle hashCode() starts from the lockstep defaults, not a dead")
    L.append("// node's stale tween (Python kept these on self, immune to hash reuse).")
    L.append("")
    L.append("static void _onNodeRemoved(MObject& node, void*) {")
    L.append("    unsigned hash = MObjectHandle(node).hashCode();   // node still valid here")
    if needs_hover:
        L.append("    g_tween.erase(hash); g_handles.erase(hash);")
        L.append("    g_hoverTris.erase(hash); g_autoRefresh.erase(hash);")
    else:
        L.append("    g_tween.erase(hash);")
    # Same reason as the tween: a later node reusing this freed hashCode() must
    # not inherit a dead node's extent.
    L.append("    g_bbox.erase(hash);")
    L.append("    g_removalCbs.erase(hash);   // Maya releases the firing callback itself")
    if needs_hover:
        L.append("    if (g_hoverValid && g_hoverHash == hash) { g_hoverValid = false; g_hoverHash = 0; }")
    L.append("}")
    L.append("static void _ensureNodeRemovalCb(unsigned hash, MObject node) {")
    L.append("    if (g_removalCbs.find(hash) != g_removalCbs.end()) return;")
    L.append("    MStatus s;  // addNodePreRemovalCallback wants a non-const MObject&")
    L.append("    MCallbackId id = MNodeMessage::addNodePreRemovalCallback(node, _onNodeRemoved, NULL, &s);")
    L.append("    if (s) g_removalCbs[hash] = id;")
    L.append("}")
    L.append("")
    if needs_hover:
        L.append("// Fan-triangulate the drawn polygon soups into ONE local-space triangle")
        L.append("// set for precise (ray-vs-triangle) hover -- matches the fill the draw")
        L.append("// renders. A soup qualifies on the node flag OR its own precise_hover.")
        L.append("static void _buildHoverTris(const %s& d, const MDagPath& dp, std::vector<MPoint>& out) {" % data_cls)
        L.append("    out.clear();")
        L.append("    for (size_t pi = 0; pi < d.polys.size(); ++pi) {")
        L.append("        const DrawPoly& pg = d.polys[pi];")
        L.append("        if (!(d.preciseHover || pg.preciseHover)) continue;")
        L.append("        if (pg.pts.empty() || pg.cnt.empty()) continue;")
        L.append("        std::vector<MPoint> P = pg.pts;")
        L.append("        if (pg.worldSpace) { MMatrix wInv = dp.inclusiveMatrixInverse();")
        L.append("            for (size_t i = 0; i < P.size(); ++i) P[i] = P[i] * wInv; }")
        L.append("        const size_t F = pg.cnt.size();")
        L.append("        std::vector<int> off(F, 0);")
        L.append("        for (size_t f = 1; f < F; ++f) off[f] = off[f-1] + pg.cnt[f-1];")
        L.append("        for (size_t f = 0; f < F; ++f) {")
        L.append("            int c = pg.cnt[f]; if (c < 3) continue;")
        L.append("            for (int k = 1; k + 1 < c; ++k) {")
        L.append("                int loc0 = off[f], lock = off[f] + k, lock1 = off[f] + k + 1;")
        L.append("                if (lock1 >= (int)pg.idx.size()) break;")
        L.append("                int i0 = pg.idx[loc0], i1 = pg.idx[lock], i2 = pg.idx[lock1];")
        L.append("                if (i0 < (int)P.size() && i1 < (int)P.size() && i2 < (int)P.size())")
        L.append("                    { out.push_back(P[i0]); out.push_back(P[i1]); out.push_back(P[i2]); }")
        L.append("            }")
        L.append("        }")
        L.append("    }")
        L.append("}")
        L.append("")
        L.append("// Cursor ray in world space (HiDPI-corrected: Qt logical px -> physical).")
        L.append("static bool _cursorRay(MPoint& o, MVector& d) {")
        L.append("    MStatus st;")
        L.append("    M3dView view = M3dView::active3dView(&st);")
        L.append("    if (!st) return false;")
        L.append("    QWidget* w = view.widget();")
        L.append("    if (!w) return false;")
        L.append("    QPoint gp = QCursor::pos();")
        L.append("    QPoint local = w->mapFromGlobal(gp);")
        L.append("    double dpr = w->devicePixelRatioF();")
        L.append("    int x = (int)llround((double)local.x() * dpr);")
        L.append("    int y = (int)llround((double)view.portHeight() - (double)local.y() * dpr);")
        L.append("    if (x < 0 || y < 0 || x > view.portWidth() || y > view.portHeight()) return false;")
        L.append("    MPoint src; MVector vec;")
        L.append("    if (!view.viewToWorld((short)x, (short)y, src, vec)) return false;")
        L.append("    o = src; d = vec; return true;")
        L.append("}")
        L.append("")
        L.append("static double _rayAABB(const MPoint& o, const MVector& d, const MPoint& lo, const MPoint& hi) {")
        L.append("    double tmin = 0.0, tmax = 1e30;")
        L.append("    for (int i = 0; i < 3; ++i) {")
        L.append("        double oi = o[i], di = d[i], loi = lo[i], hii = hi[i];")
        L.append("        if (fabs(di) < 1e-9) { if (oi < loi || oi > hii) return -1.0; }")
        L.append("        else {")
        L.append("            double t1 = (loi - oi) / di, t2 = (hii - oi) / di;")
        L.append("            if (t1 > t2) { double tmp = t1; t1 = t2; t2 = tmp; }")
        L.append("            if (t1 > tmin) tmin = t1;")
        L.append("            if (t2 < tmax) tmax = t2;")
        L.append("            if (tmin > tmax) return -1.0;")
        L.append("        }")
        L.append("    }")
        L.append("    return tmin;")
        L.append("}")
        L.append("")
        L.append("// Vectorized-free Moller-Trumbore over the flat triangle soup (3 pts/tri).")
        L.append("static double _rayTris(const MPoint& o, const MVector& d, const std::vector<MPoint>& tris) {")
        L.append("    double best = 1e30; bool hit = false;")
        L.append("    for (size_t i = 0; i + 2 < tris.size(); i += 3) {")
        L.append("        MVector e1 = tris[i+1] - tris[i];")
        L.append("        MVector e2 = tris[i+2] - tris[i];")
        L.append("        MVector p = d ^ e2;")
        L.append("        double det = e1 * p;")
        L.append("        if (fabs(det) < 1e-9) continue;")
        L.append("        double inv = 1.0 / det;")
        L.append("        MVector tv = o - tris[i];")
        L.append("        double u = (tv * p) * inv;")
        L.append("        if (u < 0.0 || u > 1.0) continue;")
        L.append("        MVector q = tv ^ e1;")
        L.append("        double v = (d * q) * inv;")
        L.append("        if (v < 0.0 || u + v > 1.0) continue;")
        L.append("        double t = (e2 * q) * inv;")
        L.append("        if (t > 1e-6 && t < best) { best = t; hit = true; }")
        L.append("    }")
        L.append("    return hit ? best : -1.0;")
        L.append("}")
        L.append("")
        L.append("// Update the hovered node; repaint any node whose hover state changed.")
        L.append("static void _setHovered(bool valid, unsigned hash, const MObject& obj) {")
        L.append("    if (g_hoverValid == valid && (!valid || g_hoverHash == hash)) return;")
        L.append("    MObjectHandle oldH = g_hoverHandle; bool oldValid = g_hoverValid;")
        L.append("    g_hoverValid = valid; g_hoverHash = hash;")
        L.append("    g_hoverHandle = valid ? MObjectHandle(obj) : MObjectHandle();")
        L.append("    if (oldValid && oldH.isValid()) MHWRender::MRenderer::setGeometryDrawDirty(oldH.object());")
        L.append("    if (valid && g_hoverHandle.isValid()) MHWRender::MRenderer::setGeometryDrawDirty(g_hoverHandle.object());")
        L.append("}")
        L.append("")
        L.append("static void _poll(float, float, void*) {")
        L.append("    // idle redraw for auto_refresh nodes (cursor-independent so the tween")
        L.append("    // keeps animating after the cursor leaves the gizmo), THROTTLED on the")
        L.append("    // main thread's own CPU clock: the CPU it consumed since our last request")
        L.append("    // is what servicing that request cost (an idle thread consumes none), and")
        L.append("    // the next request waits 2x that, never less than a tick. Idle animation")
        L.append("    // therefore takes at most ~half the main thread however many locators are")
        L.append("    // in the scene (unthrottled, 100 nodes saturated it at 7.8 fps forever),")
        L.append("    // a cheap redraw keeps the full tick rate, and whatever else the user does")
        L.append("    // on the main thread backs the animation off. Earlier meters -- tick")
        L.append("    // lateness, VP2 render events -- depended on Maya's event ordering and")
        L.append("    // misread the cost. Port of draw_refresh.throttle_step.")
        L.append("    const double _now = _wallClock(), _period = 1.0 / 30.0, _cpu = _threadCpu();")
        L.append("    const double _spent = (g_lastDirtyT < 0.0) ? 0.0 : std::max(0.0, _cpu - g_cpuAtDirty);")
        L.append("    const double _wait = std::max(_period, 2.0 * _spent);")
        L.append("    if (!g_autoRefresh.empty() && (g_lastDirtyT < 0.0 || (_now - g_lastDirtyT) >= _wait)) {")
        L.append("        g_lastRedraw = _spent; g_lastDirtyT = _now; g_cpuAtDirty = _cpu;")
        L.append("        for (std::set<unsigned>::iterator it = g_autoRefresh.begin(); it != g_autoRefresh.end(); ++it) {")
        L.append("            std::map<unsigned, MObjectHandle>::iterator h = g_handles.find(*it);")
        L.append("            if (h != g_handles.end() && h->second.isValid())")
        L.append("                MHWRender::MRenderer::setGeometryDrawDirty(h->second.object());")
        L.append("        }")
        L.append("    }")
        L.append("    MPoint o; MVector d;")
        L.append("    if (!_cursorRay(o, d)) { _setHovered(false, 0, MObject::kNullObj); return; }")
        L.append("    double bestT = 1e30; bool found = false; unsigned bestHash = 0; MObject bestObj;")
        L.append("    for (MItDependencyNodes nit(MFn::kPluginLocatorNode); !nit.isDone(); nit.next()) {")
        L.append("        MObject node = nit.thisNode();")
        L.append("        MFnDependencyNode dn(node);")
        L.append("        if (dn.typeId() != %s::id) continue;   // only OUR generated type" % cls)
        L.append("        MDagPath dp; if (!MDagPath::getAPathTo(node, dp)) continue;")
        L.append("        unsigned hash = MObjectHandle(node).hashCode();")
        L.append("        std::map<unsigned, std::vector<MPoint> >::iterator ti = g_hoverTris.find(hash);")
        L.append("        if (ti != g_hoverTris.end()) {")
        L.append("            // precise: ray into local space then ray-vs-triangle")
        L.append("            MMatrix w2l = dp.inclusiveMatrixInverse();")
        L.append("            MPoint lo = o * w2l; MVector ld = d * w2l;")
        L.append("            double tt = _rayTris(lo, ld, ti->second);")
        L.append("            if (tt < 0.0 || tt >= bestT) continue;")
        L.append("            bestT = tt; found = true; bestHash = hash; bestObj = node;")
        L.append("        } else {")
        L.append("            MFnDagNode fnDag(dp);")
        L.append("            MBoundingBox bb = fnDag.boundingBox();")
        L.append("            bb.transformUsing(dp.inclusiveMatrix());")
        L.append("            double tt = _rayAABB(o, d, bb.min(), bb.max());")
        L.append("            if (tt < 0.0 || tt >= bestT) continue;")
        L.append("            bestT = tt; found = true; bestHash = hash; bestObj = node;")
        L.append("        }")
        L.append("    }")
        L.append("    _setHovered(found, bestHash, bestObj);")
        L.append("}")
        L.append("")
    L.append("static void _onSceneEvent(void*) {")
    if needs_hover:
        L.append("    g_hoverValid = false; g_hoverHash = 0; g_hoverHandle = MObjectHandle();")
        L.append("    g_lastDirtyT = -1.0; g_cpuAtDirty = 0.0; g_lastRedraw = 0.0;")
    L.append("    for (std::map<unsigned, MCallbackId>::iterator it = g_removalCbs.begin();")
    L.append("         it != g_removalCbs.end(); ++it) MMessage::removeCallback(it->second);")
    L.append("    g_removalCbs.clear();")
    if needs_hover:
        L.append("    g_autoRefresh.clear(); g_hoverTris.clear(); g_handles.clear(); g_tween.clear();")
    else:
        L.append("    g_tween.clear();")
    L.append("    g_bbox.clear();")
    L.append("}")
    L.append("static void _ensureHoverStarted() {")
    L.append("    if (g_started) return;")
    L.append("    if (MGlobal::mayaState() != MGlobal::kInteractive) { g_started = true; return; }  // batch: no-op, no retry")
    L.append("    MStatus s; MCallbackId id;")
    L.append("    id = MSceneMessage::addCallback(MSceneMessage::kBeforeNew, _onSceneEvent, NULL, &s);  if (s) g_sceneCbs.push_back(id);")
    L.append("    id = MSceneMessage::addCallback(MSceneMessage::kBeforeOpen, _onSceneEvent, NULL, &s); if (s) g_sceneCbs.push_back(id);")
    L.append("    id = MSceneMessage::addCallback(MSceneMessage::kMayaExiting, _onSceneEvent, NULL, &s);if (s) g_sceneCbs.push_back(id);")
    if needs_hover:
        L.append("    g_timerId = MTimerMessage::addTimerCallback((float)(1.0/30.0), _poll, NULL, &s);")
        L.append("    if (s && g_timerId) { g_started = true; return; }")
        L.append("    // registration failed: undo the scene callbacks we just added so a")
        L.append("    // retry next draw doesn't double-register (g_started stays false).")
        L.append("    for (size_t i = 0; i < g_sceneCbs.size(); ++i) MMessage::removeCallback(g_sceneCbs[i]);")
        L.append("    g_sceneCbs.clear(); g_timerId = 0;")
    else:
        L.append("    g_started = true;   // no timer to fail: the scene hooks are all we need")
    L.append("}")
    L.append("static void _stopHover() {")
    if needs_hover:
        L.append("    if (g_timerId) { MMessage::removeCallback(g_timerId); g_timerId = 0; }")
    L.append("    for (size_t i = 0; i < g_sceneCbs.size(); ++i) MMessage::removeCallback(g_sceneCbs[i]);")
    L.append("    g_sceneCbs.clear(); _onSceneEvent(NULL); g_started = false;")
    L.append("}")
    L.append("}  // anonymous namespace")
    L.append("")
    return "\n".join(L)

def _generate_locator_cpp(spec, for_port=False):
    """Emit a native MPxLocatorNode + MPxDrawOverride plugin (v2). The node, the
    draw-override scaffold, selection/input/mesh marshalling, and the
    buffer->MUIDrawManager routing (lines/points/text/shapes + the full polygon
    path: 4 fill color modes, backface cull, wireframe incl. boundary-only,
    world-space) are FIXED; only the per-frame buffer-building math (between the
    PORT markers, in a free ``<cls>_computeBuffers(const Inputs&, Data&)``) is
    filled by the AI porter from the original Python draw expression.

    A standalone probe (``-DMPYNODE_PROBE``, links OpenMaya+Foundation only)
    reads a frame file and dumps the buffers as JSON for NUMERICAL parity vs
    the Python ``evaluateDrawItems`` (incl. the polygon buffer); the on-screen
    draw is the user's visual check.
    """
    # No deterministic lowering exists for this node type -- the
    # compute ALWAYS goes to the AI porter, so a file read could
    # never be attached to real buffers.
    nd_io_cpp.reject_unlowered_io(spec, None, "locator")
    sg             = spec["suggested"]
    cls            = sg["class_name"]
    type_name      = sg["node_type_name"]
    type_id        = sg["type_id"]
    data_cls       = cls + "Data"
    inp_cls        = cls + "Inputs"
    draw_cls       = cls + "DrawOverride"
    classification = "drawdb/geometry/%s" % type_name
    registrant     = "%sPlugin" % type_name

    scalars     = _loc_scalar_inputs(spec)
    meshes      = _loc_mesh_inputs(spec)
    strings     = _loc_string_inputs(spec)
    colors      = _loc_color_inputs(spec)
    generics    = _loc_generic_inputs(spec)
    svars       = _loc_stored_vars(spec)
    has_mesh    = bool(meshes)
    needs_hover = bool(spec.get("needs_hover"))
    tween_cls   = cls + "Tween"

    # ---- companion commands (Methods tab @maya_command defs) ----------------
    # Emit the recognised companion MPxCommands (createMeshRegion/setMeshRegion)
    # + their register/deregister lines. The classes ride the scaffold head (so
    # the bundler namespace-wraps them); registration rides the plugin hooks.
    from mpynode.native.compiler.kernels import command_codegen
    _REGION_ATTR = "regionFaces"
    cmd_ctx = {
        "node_type_name": type_name,
        "node_cls":       cls,
        "mesh_plug":      meshes[0]["plug"] if meshes else "inMesh",
        "region_attr":    _REGION_ATTR,
    }
    cmd_out      = command_codegen.emit_commands(spec.get("commands") or [], cmd_ctx)
    has_commands = bool(cmd_out["supported"])
    needs_region = bool(cmd_out["needs_region_attr"])
    # Everything command_codegen did NOT claim goes to the generic dispatch
    # emitter (C++ MPxCommand + MSyntax + undo; the body still runs Python).
    # The natively handled pair is excluded so it is not emitted twice.
    from mpynode.native.compiler.kernels import command_dispatch
    disp_out = command_dispatch.dispatch_for_spec(
        spec, type_name,
        exclude=[c["name"] for c in (spec.get("commands") or [])
                 if command_codegen.classify_command(c) is not None])
    _unsupported = [n for n in cmd_out["unsupported"]
                    if n not in set(disp_out["supported"])]
    if _unsupported:
        # Surface (never silently drop) commands neither emitter could lower.
        L_note = ", ".join(_unsupported)
        if disp_out["errors"]:
            L_note += " (%s)" % "; ".join(disp_out["errors"])
        import sys as _sys
        _sys.stderr.write(
            "[command_codegen] %s: no deterministic template for command(s): "
            "%s (skipped; AI-porter fallback is a follow-up)\n"
            % (type_name, L_note))

    # Deterministic self.draw -> C++ emit lowering. If the WHOLE draw expression
    # lowers, the PORT region becomes the transpiled body and nd_runtime.h is
    # inlined; otherwise None -> the AI-porter PORT region is kept. A node with
    # the mesh-region commands already has its own no-AI draw, so it never needs
    # this. Lazy import breaks the codegen<->nd_lower cycle.
    draw_lowered = None
    if not (needs_region and meshes):
        from mpynode.native.compiler import nd_lower
        draw_lowered = nd_lower.try_lower_locator(spec)

    L = []
    L.append("// %s -- generated MPxLocatorNode + MPxDrawOverride v2 (codegen)." % type_name)
    L.append("// Source mPyNode: %s (%s)"
             % (spec.get("source_node"), spec.get("mpy_type")))
    L.append("// Node + draw-override scaffold + selection/input/mesh marshalling")
    L.append("// + buffer routing (lines/points/text/shapes/polygons) are final;")
    L.append("// the per-frame buffer math (computeBuffers, between PORT markers)")
    L.append("// is filled by the AI porter from the Python draw expression.")
    L.append("")
    # generic inputs may place MMatrix in the SHARED Inputs/computeBuffers region
    # (compiled by the probe too), so its header rides the common block.
    common_inc = list(_LOCATOR_INCLUDES_COMMON)
    if draw_lowered is not None:
        # lowered_guard's handler (MGlobal::displayError) sits in computeBuffers,
        # which the probe compiles too -- so its header cannot ride the
        # plugin-only block. Gated on the lowering so an AI-ported locator's
        # frag stays byte-identical (the plugin list still carries it there).
        common_inc.append(LOWERED_GUARD_INCLUDE)
    _extra_incs, _extra_blocks = findplug_family_extras(generics)
    if generics:
        common_inc += _LOCATOR_INCLUDES_GENERIC_COMMON
        # array / geo / hex machinery lands in the Inputs POD + computeBuffers,
        # which the probe compiles too -> COMMON block, not plugin-only.
        common_inc += [i for i in _extra_incs if i not in common_inc]
    for inc in common_inc:
        L.append("#include <%s>" % inc)
    L.append("")
    L.append("#ifndef MPYNODE_PROBE  // plugin-only headers (skip for the probe)")
    plug_inc = list(_LOCATOR_INCLUDES_PLUGIN)
    if has_mesh:
        plug_inc += _LOCATOR_INCLUDES_MESH
    if needs_hover:
        plug_inc += _LOCATOR_INCLUDES_HOVER
    elif svars:
        plug_inc += _LOCATOR_INCLUDES_TWEEN
    if generics:
        plug_inc += _LOCATOR_INCLUDES_GENERIC_PLUGIN
    if has_commands:
        plug_inc += cmd_out["includes"]
    if disp_out["includes"]:
        plug_inc += disp_out["includes"]
    # Seed the seen-set with the COMMON includes (emitted in the earlier loop) so
    # a command's self-contained STL headers (e.g. <vector>) aren't emitted twice.
    _seen_inc = set(common_inc)
    for inc in plug_inc:
        if inc in _seen_inc:
            continue
        _seen_inc.add(inc)
        L.append("#include <%s>" % inc)
    if needs_hover:
        # The idle-refresh throttle meters the main thread's own CPU clock.
        # Emitted HERE, in the top include region: the mega bundler opens each
        # node's namespace after the last top-level directive, so a #include
        # further down would push that namespace past the class declaration.
        L.append("#ifdef _WIN32")
        L.append("#ifndef NOMINMAX")
        L.append("#define NOMINMAX")
        L.append("#endif")
        L.append("#define WIN32_LEAN_AND_MEAN")
        L.append("#define NOGDI")
        L.append("#define NOUSER")
        L.append("#include <windows.h>   // GetThreadTimes")
        L.append("#else")
        L.append("#include <time.h>      // clock_gettime(CLOCK_THREAD_CPUTIME_ID)")
        L.append("#endif")
    L.append("#endif")
    L.append("")

    # ---- nd runtime (only when the draw expression lowered) ------------------
    # Sits above the Data container so the lowered computeBuffers -- and the
    # probe, which compiles the same region -- can see nd::Array.
    if draw_lowered is not None:
        L.append(_nd_runtime_cpp())
        L.append("")
        # nd::Array -> MPoint/MColor bridges + the normalize_color rules the
        # emit lowering calls into. Maya types only; no DrawPoly dependency.
        L.append(locator_draw_cpp.DRAW_LOWER_HELPERS)
        L.append("")

    # ---- fixed mesh-region helpers (only when a mesh input exists) ----------
    if has_mesh:
        L.append(_LOCATOR_MESH_HELPERS)
    # hex transcode / geo Nd<Kind> readers used by the generic input reads. Both
    # sit above the Inputs POD so computeBuffers (and the probe) can see them.
    for blk in _extra_blocks:
        L.append(blk)

    # ---- ordered draw transport ----------------------------------------------
    # Mirrors draw_types.to_commands(): ONE record per authored item, replayed
    # front-to-back. Authoring order IS draw order (no per-type bucketing), so
    # the interpreted and compiled renderers cannot disagree about layering.
    L.append("// One polygon soup == one DrawMesh. Several may coexist, each with")
    L.append("// its own style -- they are NOT merged into a single soup.")
    L.append("struct DrawPoly {")
    L.append("    std::vector<MPoint> pts;       // \"points\"")
    L.append("    std::vector<int>    idx;       // \"indices\" (flat)")
    L.append("    std::vector<int>    cnt;       // \"counts\" (per-face)")
    L.append("    int    colorMode = 0;          // 0 uniform,1 face,2 vertex,3 face_vertex")
    L.append("    MColor uniform = MColor(0.5f, 0.5f, 0.5f, 1.0f);")
    L.append("    std::vector<MColor> faceColors;        // mode 1 (len F)")
    L.append("    std::vector<MColor> vertexColors;      // mode 2 (len nPts)")
    L.append("    std::vector<MColor> faceVertexColors;  // mode 3 (len sum(counts))")
    L.append("    bool   cull = false;                // cull_backfaces")
    L.append("    bool   hasWire = false;             // wireframe present")
    L.append("    MColor wireColor = MColor(0, 0, 0, 1);")
    L.append("    double wireWidth = 1.0;")
    L.append("    bool   wireBoundaryOnly = false;")
    L.append("    bool   worldSpace = false;")
    L.append("    // -1 == inherit the node-wide auto_highlight (what the")
    L.append("    // interpreted buf.get(\"highlight_*\", auto_highlight) does), 0/1 ==")
    L.append("    // the flag was set explicitly. A bool store lands as 0/1.")
    L.append("    int    highlightFill = -1;")
    L.append("    int    highlightWire = -1;")
    L.append("    bool   preciseHover = false;        // per-item hover opt-in")
    L.append("};")
    L.append("// One draw command: WHAT to draw and WHERE its payload lives.")
    L.append("struct DrawCmd {")
    L.append("    int slot;    // 0 line, 1 point, 2 text, 3 shape, 4 poly")
    L.append("    int index;   // index into the matching buffer")
    L.append("    DrawCmd(int s, int i) : slot(s), index(i) {}")
    L.append("};")
    L.append("")

    # ---- draw-data container -------------------------------------------------
    L.append("class %s : public MUserData {" % data_cls)
    L.append("public:")
    L.append("    %s() : MUserData() {}" % data_cls)
    L.append("    // THE drawing, in authoring order -- one record per item. Push")
    L.append("    // through the emit* helpers below; never touch the SoA directly.")
    L.append("    std::vector<DrawCmd>  cmds;")
    L.append("    // line/point/text/shape payloads (parallel SoA, indexed by DrawCmd)")
    L.append("    std::vector<MPoint>   lineStart, lineEnd;")
    L.append("    std::vector<MColor>   lineColor;")
    L.append("    std::vector<char>     lineWorld;  // world_space (bool)")
    L.append("    std::vector<MPoint>   pointPos;")
    L.append("    std::vector<MColor>   pointColor;")
    L.append("    std::vector<float>    pointSize;")
    L.append("    std::vector<MPoint>   textPos;")
    L.append("    std::vector<MString>  textStr;")
    L.append("    std::vector<MColor>   textColor;")
    L.append("    std::vector<double>   textSize;   // object-space glyph height (-> pixels via localPpu at draw)")
    L.append("    std::vector<int>      shapeKind;   // 0=sphere,1=circle,2=box,3=cone,4=cylinder")
    L.append("    std::vector<MPoint>   shapeCenter;")
    L.append("    std::vector<double>   shapeRadius;")
    L.append("    std::vector<MVector>  shapeAxis;")
    L.append("    std::vector<MColor>   shapeColor;")
    L.append("    std::vector<char>     shapeFilled; // bool")
    L.append("    // polygon payloads -- one DrawPoly per DrawMesh drawn this frame")
    L.append("    std::vector<DrawPoly> polys;")
    L.append("    // --- emit helpers: push ONE item, in draw order ---")
    L.append("    void emitLine(const MPoint& a, const MPoint& b, const MColor& c,")
    L.append("                  bool worldSpace = false) {")
    L.append("        lineStart.push_back(a); lineEnd.push_back(b); lineColor.push_back(c);")
    L.append("        lineWorld.push_back(worldSpace ? (char)1 : (char)0);")
    L.append("        cmds.push_back(DrawCmd(0, (int)lineStart.size() - 1));")
    L.append("    }")
    L.append("    void emitPoint(const MPoint& p, const MColor& c, float size) {")
    L.append("        pointPos.push_back(p); pointColor.push_back(c); pointSize.push_back(size);")
    L.append("        cmds.push_back(DrawCmd(1, (int)pointPos.size() - 1));")
    L.append("    }")
    L.append("    void emitText(const MPoint& p, const MString& s, const MColor& c,")
    L.append("                  double size) {")
    L.append("        textPos.push_back(p); textStr.push_back(s);")
    L.append("        textColor.push_back(c); textSize.push_back(size);")
    L.append("        cmds.push_back(DrawCmd(2, (int)textPos.size() - 1));")
    L.append("    }")
    L.append("    void emitShape(int kind, const MPoint& center, double radius,")
    L.append("                   const MVector& axis, const MColor& c, bool filled) {")
    L.append("        shapeKind.push_back(kind); shapeCenter.push_back(center);")
    L.append("        shapeRadius.push_back(radius); shapeAxis.push_back(axis);")
    L.append("        shapeColor.push_back(c); shapeFilled.push_back(filled ? (char)1 : (char)0);")
    L.append("        cmds.push_back(DrawCmd(3, (int)shapeKind.size() - 1));")
    L.append("    }")
    L.append("    // Append an empty polygon soup and hand back a reference to fill.")
    L.append("    DrawPoly& emitPoly() {")
    L.append("        polys.push_back(DrawPoly());")
    L.append("        cmds.push_back(DrawCmd(4, (int)polys.size() - 1));")
    L.append("        return polys.back();")
    L.append("    }")
    L.append("    // gizmo flags from the expression. autoHighlight gates the")
    L.append("    // selection tint in addUIDrawables/_drawPoly.")
    L.append("    bool   autoHighlight = true;")
    L.append("    bool   autoRefresh = false;")
    L.append("    bool   preciseHover = false;")
    if svars:
        L.append("    // stored-var conduits: computeBuffers writes the mutated locals")
        L.append("    // here; prepareForDraw persists them to g_tween (file-static")
        L.append("    // cross-frame map). NOT touched by reset().")
        for v in svars:
            L.append("    %s sv_%s = %s;" % (v["ctype"], v["name"], v["seed"]))
    L.append("    // draw-time state (set by prepareForDraw; used by addUIDrawables)")
    L.append("    bool   selected = false;")
    L.append("    MColor selColor = MColor(1, 1, 1, 1);")
    L.append("    double viewPosLocal[3] = {0.0, 0.0, 1.0};")
    L.append("    // screen pixels per OBJECT unit at the node's depth (set by prepareForDraw;")
    L.append("    // 0 = unknown, e.g. headless -> text sizes are taken as pixels)")
    L.append("    double localPpu = 0.0;")
    L.append("    void reset() {")
    L.append("        cmds.clear();")
    L.append("        lineStart.clear(); lineEnd.clear(); lineColor.clear(); lineWorld.clear();")
    L.append("        pointPos.clear(); pointColor.clear(); pointSize.clear();")
    L.append("        textPos.clear(); textStr.clear(); textColor.clear(); textSize.clear();")
    L.append("        shapeKind.clear(); shapeCenter.clear(); shapeRadius.clear();")
    L.append("        shapeAxis.clear(); shapeColor.clear(); shapeFilled.clear();")
    L.append("        polys.clear();")
    L.append("        autoHighlight = true; autoRefresh = false; preciseHover = false;")
    L.append("    }")
    L.append("};")
    L.append("")

    # ---- DrawInputs (POD; spec-driven) --------------------------------------
    L.append("// Per-frame inputs to computeBuffers (POD so the probe can build it).")
    L.append("struct %s {" % inp_cls)
    L.append("    double timeVal = 0.0;")
    L.append("    double wallClock = 0.0;   // self.wallclock / time.time(): epoch seconds; 0 for deterministic parity")
    L.append("    bool   selected = false;")
    L.append("    bool   isLead = false;")
    L.append("    bool   hovered = false;")
    L.append("    float  selColor[4] = {1.0f, 1.0f, 1.0f, 1.0f};")
    for s in scalars:
        L.append("    %s %s = %s;"
                 % (_loc_input_ctype(s["type"]), s["member"],
                    _loc_input_default(s["type"], s["default_value"], s["enum_names"])))
    for s in strings:
        # Seed the plug DEFAULT, the same way every other input type does: the
        # field keeps this value when the findPlug read fails, and it is what
        # the standalone probe starts from.
        L.append("    MString %s = %s;"
                 % (s["member"],
                    locator_draw_cpp._cpp_string(str(s["default_value"] or ""))))
    for c in colors:
        L.append("    float  %s[3] = {%s};"
                 % (c["member"], _loc_color_default(c["default_value"])))
    for gm in generics:
        L.append(_loc_generic_field(gm))
    for m in meshes:
        L.append("    RegionMesh %s;" % m["member"])
    if needs_region:
        L.append("    std::vector<int> %s;   // settable face region (companion cmd writes the attr)"
                 % _REGION_ATTR)
    for v in svars:
        L.append("    %s sv_%s = %s;   // stored-var seed" % (v["ctype"], v["name"], v["seed"]))
    L.append("};")
    L.append("")

    # ---- buffer-building math (AI-filled / probe-testable region) ------------
    L.append("// Build the per-frame draw buffers. PURE math: no Maya scene access,")
    L.append("// so the standalone probe can call it directly for numerical parity.")
    L.append("static void %s_computeBuffers(const %s& inp, %s& data) {"
             % (cls, inp_cls, data_cls))
    L.append("    data.reset();")
    L.append("    // --- draw state ---")
    L.append("    const double timeVal = inp.timeVal;")
    L.append("    const double wallClock = inp.wallClock;")
    L.append("    const bool   selected = inp.selected;")
    L.append("    const bool   is_lead = inp.isLead;")
    L.append("    const bool   hovered = inp.hovered;")
    L.append("    const MColor selection_color(inp.selColor[0], inp.selColor[1],")
    L.append("                                 inp.selColor[2], inp.selColor[3]);")
    L.append("    (void)timeVal; (void)wallClock; (void)selected; (void)is_lead;")
    L.append("    (void)hovered; (void)selection_color;")
    if scalars:
        L.append("    // --- user inputs (self.<name> or bare <name> -> in_<name>) ---")
        for s in scalars:
            L.append("    const %s %s = inp.%s; (void)%s;"
                     % (_loc_input_ctype(s["type"]), s["member"], s["member"], s["member"]))
            if s["type"] == "enum":
                names = ", ".join('"%s"' % n for n in s["enum_names"])
                L.append("    static const char* _names_%s[] = {%s};" % (s["member"], names))
                L.append("    const std::string %s_name = (%s >= 0 && %s < %d) ? _names_%s[%s] : \"\";"
                         % (s["member"], s["member"], s["member"],
                            len(s["enum_names"]), s["member"], s["member"]))
                L.append("    (void)%s_name;" % s["member"])
    if strings:
        L.append("    // --- string inputs (self.<name> -> in_<name>; MString, use")
        L.append("    //     .asChar() for a const char*). e.g. push into data.textStr. ---")
        for s in strings:
            L.append("    const MString& %s = inp.%s; (void)%s;"
                     % (s["member"], s["member"], s["member"]))
    if colors:
        L.append("    // --- color inputs (self.<name> -> in_<name>; MColor rgb, plus")
        L.append("    //     in_<name>[0..2] as raw floats). e.g. a DrawPoly uniform. ---")
        for c in colors:
            L.append("    const MColor %s(inp.%s[0], inp.%s[1], inp.%s[2]); (void)%s;"
                     % (c["member"], c["member"], c["member"], c["member"],
                        c["member"]))
    if generics:
        L.append("    // --- generic inputs (self.<name> -> in_a<ident>; findPlug read) ---")
        for gm in generics:
            L.append(_loc_generic_expose(gm))
    if meshes:
        L.append("    // --- mesh inputs (bare <name>; call extract_region(<name>, faceIds, withNormals),")
        L.append("    //     tag_indices(<name>, tagName) for a named component tag) ---")
        for m in meshes:
            L.append("    const RegionMesh& %s = inp.%s; (void)%s;"
                     % (m["member"], m["member"], m["member"]))
    if needs_region:
        L.append("    // --- settable face region (companion command writes the regionFaces attr) ---")
        L.append("    const std::vector<int>& faceIds = inp.%s; (void)faceIds;"
                 % _REGION_ATTR)
    if svars:
        L.append("    // --- stored vars (self.<name> -> mutable local; persisted across")
        L.append("    //     frames via g_tween -- see the write-back after PORT_END) ---")
        for v in svars:
            L.append("    %s %s = inp.sv_%s; (void)%s;"
                     % (v["ctype"], v["name"], v["name"], v["name"]))
    if svars:
        # Wrap the AI-ported body in an immediately-invoked lambda so a bare
        # `return;` in the translated expression exits only the body -- the
        # stored-var write-back below still runs (else the tween would freeze).
        L.append("    [&]() {  // SV-GUARD: an early return must not skip the write-back")
    if draw_lowered is not None:
        L.append("    // --- deterministic self.draw -> C++ emit lowering (no port) ---")
        # computeBuffers() returns void, so "abandon the evaluation" is
        # data.reset() -- an empty drawing, which is exactly the dict(_EMPTY)
        # the interpreted locator returns when its draw expression raises. The
        # interpreted path also skips its stored-var commit on that branch, so
        # rewind each mutated local to its seed before the write-back below.
        _on_err = ["data.reset();"]
        _on_err += ["%s = inp.sv_%s;" % (v["name"], v["name"]) for v in svars]
        L       += lowered_guard(type_name, draw_lowered, _on_err)
    else:
        L.append("    " + PORT_BEGIN)
    if draw_lowered is None and for_port:
        L.append("    // Emit the drawing ITEM BY ITEM, in the SAME order the Python")
        L.append("    // expression composes it -- authoring order IS draw order. Call one")
        L.append("    // emit* helper per DrawItem; never push into the SoA vectors directly:")
        L.append("    //   DrawLines/DrawCurve -> data.emitLine(start, end, MColor, worldSpace)   (one call PER SEGMENT)")
        L.append("    //   DrawPoints          -> data.emitPoint(MPoint, MColor, float size)")
        L.append("    //   DrawText            -> data.emitText(MPoint, MString, MColor, double size)  (raw size -- do NOT truncate to int)")
        L.append("    //   DrawSphere/Circle/Box/Cone/Cylinder -> data.emitShape(kind, center, radius, axis, MColor, filled)")
        L.append("    //           kind: sphere->0, circle->1, box->2, cone->3, cylinder->4")
        L.append("    //           axis is the MVector normal; pass MVector(0,1,0) for spheres")
        L.append("    // DrawMesh -> DrawPoly& pg = data.emitPoly(); then fill pg:")
        L.append("    //   \"points\"  -> pg.pts (MPoint);  \"indices\" -> pg.idx (int, flat)")
        L.append("    //   \"counts\"  -> pg.cnt (int, per-face)")
        L.append("    //   \"colors\" (one RGBA)        -> pg.colorMode=0; pg.uniform=MColor(r,g,b,a)")
        L.append("    //   \"face_colors\" (F x RGBA)    -> pg.colorMode=1; pg.faceColors")
        L.append("    //   \"vertex_colors\" (nPts x RGBA)-> pg.colorMode=2; pg.vertexColors")
        L.append("    //   \"face_vertex_colors\" (sumCnt x RGBA) -> pg.colorMode=3; pg.faceVertexColors")
        L.append("    //   \"cull_backfaces\"-> pg.cull; \"wireframe\"(RGBA)-> pg.hasWire=true, pg.wireColor")
        L.append("    //   \"wireframe_width\"-> pg.wireWidth; \"wireframe_boundary_only\"-> pg.wireBoundaryOnly")
        L.append("    //   \"world_space\"-> pg.worldSpace; \"highlight_fill\"/\"highlight_wire\"-> pg.highlightFill/Wire")
        L.append("    //   \"precise_hover\" -> pg.preciseHover")
        L.append("    //   Several DrawMeshes -> several emitPoly() calls; do NOT merge them.")
        L.append("    //   Nothing drawn -> emit nothing (leave data.cmds empty).")
        L.append("    // self.auto_highlight -> data.autoHighlight; self.auto_refresh -> data.autoRefresh;")
        L.append("    // self.precise_hover -> data.preciseHover (accepted; refresh/hover are deferred no-ops).")
        if colors:
            L.append("    // COLOR inputs (self.<name>): available as an MColor local named")
            L.append("    // in_<name> (RGB; raw floats in in_<name>[0..2]). Use e.g. for")
            L.append("    // a DrawPoly uniform / a region tint. Names: %s"
                     % ", ".join("in_" + _ident(c["plug"]) for c in colors))
        if generics:
            L.append("    // GENERIC inputs (self.<name>) as read-only C++ locals:")
            for gm in generics:
                L.append("    //   self.%s -> in_%s (%s)"
                         % (gm["plug"], gm["member"],
                            findplug_local_hint(
                                gm, _loc_generic_hint(gm["meta"]["type"]))))
        if meshes:
            L.append("    // Mesh region: RegionBuffer rb = extract_region(%s, faceIds, true);" % meshes[0]["member"])
            L.append("    //   rb.points/rb.indices/rb.counts/rb.normals are std::vectors; %s.present is the connect flag." % meshes[0]["member"])
            L.append("    // COMPONENT TAGS are already read off the mesh data: tag_indices(%s, name)" % meshes[0]["member"])
            L.append("    //   returns std::vector<int> component ids for a named tag (empty if absent).")
            L.append("    //   Use it for tag_indices_from_mesh_data(...) / mesh_data_from_node_plug(...)")
            L.append("    //   in the Python -- do NOT report those as unportable scene queries.")
            L.append("    // The mesh's own TRANSFORM is read off that same data:")
            L.append("    //   mesh_to_world(%s, MPoint) -> world point" % meshes[0]["member"])
            L.append("    //   mesh_dir_to_world(%s, MVector) -> world unit direction (normals)" % meshes[0]["member"])
            L.append("    //   mesh_matrix(%s) -> const double* row-major 4x4 (identity if none)" % meshes[0]["member"])
            L.append("    //   %s.pts and rb.points/rb.normals are OBJECT space. Map the Python's" % meshes[0]["member"])
            L.append("    //   mesh_matrix_from_mesh_data(...) onto these -- also PORTABLE, never")
            L.append("    //   ND_PORT_INCOMPLETE. Skipping it draws the region at the ORIGIN.")
        L.append("    // Reproduce numpy with std::vector + loops/std::sin/cos. Map numpy rows -> one push each.")
        L.append("    // Original Python draw expression (translate faithfully):")
        for src_line in (spec.get("compute") or "").splitlines():
            L.append("    //   | %s" % src_line)
    elif draw_lowered is None and needs_region and meshes:
        # A node carrying the companion mesh-region commands IS a region drawer,
        # so the no-AI path emits the region draw directly (no porter): extract
        # the settable face region and draw it as a tinted, wire-framed soup.
        mm = meshes[0]["member"]
        L.append("    // Deterministic mesh-region draw (companion-command node; no AI port).")
        L.append("    RegionBuffer _rb = extract_region(%s, faceIds, true);" % mm)
        L.append("    if (!_rb.points.empty() && !_rb.counts.empty()) {")
        L.append("        DrawPoly& _pg = data.emitPoly();")
        L.append("        _pg.pts = _rb.points;")
        L.append("        _pg.idx = _rb.indices;")
        L.append("        _pg.cnt = _rb.counts;")
        L.append("        _pg.colorMode = 0;")
        L.append("        _pg.uniform = MColor(1.0f, 0.6f, 0.1f, 1.0f);")
        L.append("        _pg.hasWire = true;")
        L.append("        _pg.wireColor = MColor(0.0f, 0.0f, 0.0f, 1.0f);")
        L.append("        _pg.highlightFill = true;")
        L.append("    }")
    elif draw_lowered is None:
        L.append("    // TODO: translate the Python draw expression below into buffer pushes.")
        for src_line in (spec.get("compute") or "").splitlines():
            L.append("    //   | %s" % src_line)
    if draw_lowered is None:
        L.append("    " + PORT_END)
    if svars:
        L.append("    }();  // end SV-GUARD body")
        L.append("    // persist mutated stored vars out to the draw-data conduit")
        L.append("    // (prepareForDraw copies these into the cross-frame g_tween map).")
        for v in svars:
            L.append("    data.sv_%s = %s;" % (v["name"], v["name"]))
    L.append("}")
    L.append("")

    L.append("#ifndef MPYNODE_PROBE  // ===== plugin scaffold (excluded from probe) =====")
    L.append("")
    # ---- the locator node ----------------------------------------------------
    # The extent of each node's last drawing, for boundingBox() below.
    # Measured in prepareForDraw, where the buffers exist -- the node itself
    # never sees them (the interpreted MPyLocator caches it on self, off the
    # same buffers). Declared HERE, before the class, because the draw side's
    # globals sit in an anonymous namespace and the member body cannot.
    L.append("static std::map<unsigned, MBoundingBox> g_bbox;   // hash -> drawn extent")
    L.append("class %s : public MPxLocatorNode {" % cls)
    L.append("public:")
    L.append("    %s() {}" % cls)
    L.append("    ~%s() override {}" % cls)
    L.append("    static void*   creator() { return new %s(); }" % cls)
    L.append("    static MStatus initialize();")
    L.append("    static MTypeId id;")
    L.append("    static MString drawDbClassification;")
    L.append("    static MString drawRegistrantId;")
    L.append("    // The drawn extent (see _drawnBounds), so Frame Selected and a bbox")
    L.append("    // pick line up with the gizmo -- MPxLocatorNode's default is the unit")
    L.append("    // cube scaled by localScale, which describes a plain locator's cross.")
    L.append("    bool isBounded() const override { return true; }")
    L.append("    MBoundingBox boundingBox() const override {")
    L.append("        // Measured off the last drawing, never by re-running the")
    L.append("        // expression: Maya asks for this during selection and framing.")
    L.append("        // Before the first draw nothing is measured and the stock")
    L.append("        // locator box stands.")
    L.append("        std::map<unsigned, MBoundingBox>::const_iterator it =")
    L.append("            g_bbox.find(MObjectHandle(thisMObject()).hashCode());")
    L.append("        if (it == g_bbox.end()) return MPxLocatorNode::boundingBox();")
    L.append("        return it->second;")
    L.append("    }")
    for s in scalars:
        L.append("    static MObject a_%s;" % s["member"])
    for m in meshes:
        L.append("    static MObject a_%s;" % m["member"])
    for s in strings:
        L.append("    static MObject a_%s;" % s["member"])
    for c in colors:
        L.append("    static MObject a_%s;" % c["member"])
    for gm in generics:
        L.append("    static MObject %s;" % gm["member"])
    L.append("};")
    L.append("MTypeId %s::id(%s);" % (cls, type_id))
    L.append('MString %s::drawDbClassification("%s");' % (cls, classification))
    L.append('MString %s::drawRegistrantId("%s");' % (cls, registrant))
    for s in scalars:
        L.append("MObject %s::a_%s;" % (cls, s["member"]))
    for m in meshes:
        L.append("MObject %s::a_%s;" % (cls, m["member"]))
    for s in strings:
        L.append("MObject %s::a_%s;" % (cls, s["member"]))
    for c in colors:
        L.append("MObject %s::a_%s;" % (cls, c["member"]))
    for gm in generics:
        L.append("MObject %s::%s;" % (cls, gm["member"]))
    L.append("")
    # ---- passive-hover + idle-refresh + stored-var service (needs_hover) -----
    #      Placed after <cls>::id is defined (the per-node scan filters on it).
    #      Stored vars alone also need it: they persist across frames in the
    #      same g_tween map, hover or not (the interpreted node commits them
    #      back to the node every draw evaluation).
    if needs_hover or svars:
        L.append(_locator_hover_service(cls, data_cls, svars, needs_hover))
    # ---- initialize(): recreate the user input attrs so the plugin node has
    #      the same plugs the original drew from (and they can be connected). --
    L.append("MStatus %s::initialize() {" % cls)
    if scalars or meshes or needs_region or strings or colors or generics:
        L.append("    MFnNumericAttribute nAttr;")
        L.append("    MFnEnumAttribute    eAttr;")
        L.append("    MFnTypedAttribute   tAttr;")
        if generics:
            L.append("    MFnUnitAttribute     uAttr;")
            L.append("    MFnCompoundAttribute cAttr;")
            L.append("    MFnMatrixAttribute   mAttr;")
        for s in scalars:
            plug = s["plug"]
            t    = s["type"]
            mem  = "a_" + s["member"]
            if t == "float":
                L.append('    %s = nAttr.create("%s", "%s", MFnNumericData::kFloat, %s);'
                         % (mem, plug, plug, _loc_input_default("float", s["default_value"], [])))
                L.append("    nAttr.setStorable(true); nAttr.setKeyable(true);")
                L.append("    nAttr.setAffectsAppearance(true);")
            elif t == "int":
                L.append('    %s = nAttr.create("%s", "%s", MFnNumericData::kInt, %s);'
                         % (mem, plug, plug, _loc_input_default("int", s["default_value"], [])))
                L.append("    nAttr.setStorable(true); nAttr.setKeyable(true);")
                L.append("    nAttr.setAffectsAppearance(true);")
            elif t == "bool":
                L.append('    %s = nAttr.create("%s", "%s", MFnNumericData::kBoolean, %s);'
                         % (mem, plug, plug, _loc_input_default("bool", s["default_value"], [])))
                L.append("    nAttr.setStorable(true); nAttr.setKeyable(true);")
                L.append("    nAttr.setAffectsAppearance(true);")
            elif t == "enum":
                L.append('    %s = eAttr.create("%s", "%s", %s);'
                         % (mem, plug, plug, _loc_input_default("enum", s["default_value"], s["enum_names"])))
                for i, fld in enumerate(s["enum_names"]):
                    L.append('    eAttr.addField("%s", %d);' % (fld, i))
                L.append("    eAttr.setStorable(true); eAttr.setKeyable(true);")
                L.append("    eAttr.setAffectsAppearance(true);")
            L.append("    addAttribute(%s);" % mem)
        for m in meshes:
            mem = "a_" + m["member"]
            L.append('    %s = tAttr.create("%s", "%s", MFnData::kMesh);'
                     % (mem, m["plug"], m["plug"]))
            L.append("    tAttr.setStorable(false); tAttr.setWritable(true);")
            L.append("    tAttr.setAffectsAppearance(true);")
            L.append("    addAttribute(%s);" % mem)
        for s in strings:
            mem = "a_" + s["member"]
            L.append('    %s = tAttr.create("%s", "%s", MFnData::kString);'
                     % (mem, s["plug"], s["plug"]))
            L.append("    tAttr.setStorable(true); tAttr.setWritable(true);")
            L.append("    tAttr.setKeyable(false); tAttr.setAffectsAppearance(true);")
            L.append("    addAttribute(%s);" % mem)
        for c in colors:
            mem = "a_" + c["member"]
            dv  = c["default_value"]
            L.append('    %s = nAttr.createColor("%s", "%s");'
                     % (mem, c["plug"], c["plug"]))
            try:
                r, g, b = float(dv[0]), float(dv[1]), float(dv[2])
                L.append("    nAttr.setDefault(%sf, %sf, %sf);"
                         % (repr(r), repr(g), repr(b)))
            except Exception:
                pass
            L.append("    nAttr.setStorable(true); nAttr.setKeyable(true);")
            L.append("    nAttr.setAffectsAppearance(true);")
            L.append("    addAttribute(%s);" % mem)
        # Generic inputs: create via the shared emit_attr._create_lines (correct
        # compound-child / unit / matrix construction for every type) so a
        # connected/AE value is readable by prepareForDraw's findPlug read.
        for gm in generics:
            L += _create_lines(gm)
            # Via the BASE function set: _create_lines picks its own (numeric /
            # unit / compound / matrix / typed) per type, so there is no single
            # `xAttr` in scope to call this on.
            L.append("    MFnAttribute(%s).setAffectsAppearance(true);"
                     % gm["member"])
            L.append("    addAttribute(%s);" % gm["member"])
        if needs_region:
            # Settable face-region attr the companion commands write + the draw
            # reads (faceIds). Persistent int array (storable) so it round-trips.
            L.append("    { MObject _rgn = tAttr.create(\"%s\", \"rgnf\", MFnData::kIntArray);"
                     % _REGION_ATTR)
            L.append("      tAttr.setStorable(true); tAttr.setWritable(true);")
            # setAffectsAppearance: writing regionFaces marks the VP2 draw dirty
            # -- an explicit DG signal complementing the draw override's
            # isAlwaysDirty=true. Valid on MFnTypedAttribute for a kIntArray.
            L.append("      tAttr.setKeyable(false); tAttr.setAffectsAppearance(true);")
            L.append("      addAttribute(_rgn); }")
    L.append("    return MS::kSuccess;")
    L.append("}")
    L.append("")
    if has_commands:
        # Companion MPxCommand classes (region helpers + the recognised cmds).
        # Placed in the scaffold head AFTER <cls>::id is defined (the classes
        # reference it); the bundler wraps this region in `namespace nd_<node>`.
        L.append("// ==== companion commands (Methods @maya_command) ====")
        L.append(cmd_out["classes"])
        L.append("")
    if disp_out["classes"]:
        # Same placement rule: the bundler namespace-wraps this region, which is
        # what keeps two nodes' command support from colliding in one plug-in.
        L.append("// ==== generic @maya_command dispatch commands ====")
        L.append(disp_out["classes"])
        L.append("")
    # ---- the draw override ---------------------------------------------------
    L.append("// The extent of what was drawn, in OBJECT space -- the port of")
    L.append("// draw_buffers.command_bounds, rule for rule: a shape grows by its own")
    L.append("// radius (a sphere whose CENTRE is in frame is not a sphere in frame),")
    L.append("// text contributes only its anchor (glyphs are sized in PIXELS, so their")
    L.append("// on-screen extent is not an object-space quantity), and world-space")
    L.append("// items are skipped because a bounding box is reported in the shape's")
    L.append("// own space. Returns false when nothing drawable was emitted.")
    L.append("static bool _drawnBounds(const %s& d, MBoundingBox& out) {" % data_cls)
    L.append("    bool any = false;")
    L.append("    for (size_t i = 0; i < d.lineStart.size(); ++i) {")
    L.append("        if (i < d.lineWorld.size() && d.lineWorld[i]) continue;")
    L.append("        out.expand(d.lineStart[i]); out.expand(d.lineEnd[i]); any = true;")
    L.append("    }")
    L.append("    for (size_t i = 0; i < d.pointPos.size(); ++i) { out.expand(d.pointPos[i]); any = true; }")
    L.append("    for (size_t i = 0; i < d.textPos.size(); ++i)  { out.expand(d.textPos[i]);  any = true; }")
    L.append("    for (size_t i = 0; i < d.shapeCenter.size(); ++i) {")
    L.append("        const double r = (i < d.shapeRadius.size()) ? std::fabs(d.shapeRadius[i]) : 0.0;")
    L.append("        const MPoint& c = d.shapeCenter[i];")
    L.append("        out.expand(MPoint(c.x - r, c.y - r, c.z - r));")
    L.append("        out.expand(MPoint(c.x + r, c.y + r, c.z + r));")
    L.append("        any = true;")
    L.append("    }")
    L.append("    for (size_t p = 0; p < d.polys.size(); ++p) {")
    L.append("        const DrawPoly& pg = d.polys[p];")
    L.append("        if (pg.worldSpace) continue;")
    L.append("        for (size_t i = 0; i < pg.pts.size(); ++i) { out.expand(pg.pts[i]); any = true; }")
    L.append("    }")
    L.append("    return any;")
    L.append("}")
    L.append("static void _setBBox(unsigned hash, const MBoundingBox& bb, bool any) {")
    L.append("    if (any) g_bbox[hash] = bb; else g_bbox.erase(hash);")
    L.append("}")
    L.append("class %s : public MHWRender::MPxDrawOverride {" % draw_cls)
    L.append("public:")
    L.append("    static MHWRender::MPxDrawOverride* creator(const MObject& obj) {")
    L.append("        return new %s(obj);" % draw_cls)
    L.append("    }")
    L.append("    ~%s() override {}" % draw_cls)
    L.append("    MHWRender::DrawAPI supportedDrawAPIs() const override {")
    L.append("        return MHWRender::kAllDevices;")
    L.append("    }")
    L.append("    bool hasUIDrawables() const override { return true; }")
    L.append("    bool isTransparent() const override { return true; }")
    L.append("    bool isBounded(const MDagPath&, const MDagPath&) const override { return false; }")
    L.append("    MUserData* prepareForDraw(const MDagPath& objPath,")
    L.append("                              const MDagPath& cameraPath,")
    L.append("                              const MHWRender::MFrameContext& frameContext,")
    L.append("                              MUserData* oldData) override;")
    L.append("    void addUIDrawables(const MDagPath& objPath,")
    L.append("                        MHWRender::MUIDrawManager& dm,")
    L.append("                        const MHWRender::MFrameContext& frameContext,")
    L.append("                        const MUserData* userData) override;")
    L.append("private:")
    L.append("    %s(const MObject& obj)" % draw_cls)
    L.append("        : MHWRender::MPxDrawOverride(obj, NULL, true) {}")
    L.append("};")
    L.append("")
    # ---- prepareForDraw ------------------------------------------------------
    L.append("MUserData* %s::prepareForDraw(const MDagPath& objPath," % draw_cls)
    L.append("                              const MDagPath& cameraPath,")
    L.append("                              const MHWRender::MFrameContext& frameContext,")
    L.append("                              MUserData* oldData) {")
    L.append("    (void)frameContext;")
    L.append("    %s* data = dynamic_cast<%s*>(oldData);" % (data_cls, data_cls))
    L.append("    if (!data) data = new %s();" % data_cls)
    L.append("    %s inp;" % inp_cls)
    L.append("    inp.timeVal = MAnimControl::currentTime().value();")
    if needs_hover:
        L.append("    // --- live wall clock + passive cursor-ray hover (needs_hover) ---")
        L.append("    MObjectHandle _objH(objPath.node());")
        L.append("    const unsigned _nodeHash = _objH.hashCode();")
        L.append("    _ensureHoverStarted();")
        L.append("    _registerNode(_nodeHash, objPath.node());")
        L.append("    _ensureNodeRemovalCb(_nodeHash, objPath.node());")
        L.append("    inp.wallClock = _epochClock();         // self.wallclock: seconds since the epoch (time.time())")
        L.append("    inp.hovered = _isHovered(_nodeHash);   // cursor under this locator?")
    else:
        if svars:
            L.append("    // --- cross-frame stored vars (no hover service: no clock/hover) ---")
            L.append("    MObjectHandle _objH(objPath.node());")
            L.append("    const unsigned _nodeHash = _objH.hashCode();")
            L.append("    _ensureHoverStarted();")
            L.append("    _ensureNodeRemovalCb(_nodeHash, objPath.node());")
        L.append("    inp.wallClock = 0.0;  // wall-clock animation deferred (deterministic)")
        L.append("    inp.hovered = false;  // passive hover deferred (no headless equivalent)")
    if svars:
        L.append("    { %s& _tw = g_tween[_nodeHash];   // seed stored vars from last frame"
                 % tween_cls)
        for v in svars:
            L.append("      inp.sv_%s = _tw.%s;" % (v["name"], v["name"]))
        L.append("    }")
    L.append("    // --- selection state (MGeometryUtilities + active-list fallback) ---")
    L.append("    MHWRender::DisplayStatus _st = MHWRender::MGeometryUtilities::displayStatus(objPath);")
    L.append("    inp.isLead = (_st == MHWRender::kLead);")
    L.append("    bool _active = (_st == MHWRender::kActive);")
    L.append("    inp.selected = inp.isLead || _active;")
    L.append("    MColor _wc = MHWRender::MGeometryUtilities::wireframeColor(objPath);")
    L.append("    inp.selColor[0] = _wc.r; inp.selColor[1] = _wc.g;")
    L.append("    inp.selColor[2] = _wc.b; inp.selColor[3] = _wc.a;")
    L.append("    if (!inp.selected) {")
    L.append("        MSelectionList _al; MGlobal::getActiveSelectionList(_al);")
    L.append("        if (_al.length()) {")
    L.append("            bool _hit = _al.hasItem(objPath);")
    L.append("            if (!_hit) { MDagPath _tp(objPath); _tp.pop(); _hit = _al.hasItem(_tp); }")
    L.append("            if (_hit) inp.selected = true;")
    L.append("        }")
    L.append("    }")
    L.append("    // --- camera position in the locator's local frame (backface cull) ---")
    L.append("    MMatrix _camW = cameraPath.inclusiveMatrix();")
    L.append("    MMatrix _objWInv = objPath.inclusiveMatrixInverse();")
    L.append("    MPoint _camLocal = MPoint(_camW(3,0), _camW(3,1), _camW(3,2)) * _objWInv;")
    L.append("    data->viewPosLocal[0] = _camLocal.x;")
    L.append("    data->viewPosLocal[1] = _camLocal.y;")
    L.append("    data->viewPosLocal[2] = _camLocal.z;")
    L.append("    // --- local text scale: screen pixels per OBJECT unit at the node's depth.")
    L.append("    //     Port of draw_buffers.pixels_per_world_unit * matrix_uniform_scale:")
    L.append("    //     project a 1-unit probe along the camera up axis at the object origin")
    L.append("    //     through world->clip and read the NDC delta in pixels. 0 when the")
    L.append("    //     view is unavailable (headless) -> text sizes are taken as pixels.")
    L.append("    data->localPpu = 0.0;")
    L.append("    { MStatus _fs;")
    L.append("      const MMatrix _vp = frameContext.getMatrix(MHWRender::MFrameContext::kViewProjMtx, &_fs);")
    L.append("      int _vx = 0, _vy = 0, _vw = 0, _vh = 0;")
    L.append("      frameContext.getViewportDimensions(_vx, _vy, _vw, _vh);")
    L.append("      const MMatrix _ow = objPath.inclusiveMatrix();")
    L.append("      MVector _up(_camW(1,0), _camW(1,1), _camW(1,2));   // camera up axis (row 1)")
    L.append("      const double _un = _up.length();")
    L.append("      if (_fs == MS::kSuccess && _vh > 0 && _un > 1e-12) {")
    L.append("          _up /= _un;")
    L.append("          const MPoint _a(_ow(3,0), _ow(3,1), _ow(3,2));")
    L.append("          const MPoint _b = _a + _up;                       // ref_len 1.0")
    L.append("          // row-vector world->clip; only (y, w) are needed")
    L.append("          const double _cyA = _a.x*_vp(0,1) + _a.y*_vp(1,1) + _a.z*_vp(2,1) + _vp(3,1);")
    L.append("          const double _cwA = _a.x*_vp(0,3) + _a.y*_vp(1,3) + _a.z*_vp(2,3) + _vp(3,3);")
    L.append("          const double _cyB = _b.x*_vp(0,1) + _b.y*_vp(1,1) + _b.z*_vp(2,1) + _vp(3,1);")
    L.append("          const double _cwB = _b.x*_vp(0,3) + _b.y*_vp(1,3) + _b.z*_vp(2,3) + _vp(3,3);")
    L.append("          if (_cwA > 1e-9 && _cwB > 1e-9) {")
    L.append("              const double _ppw = std::fabs(_cyB / _cwB - _cyA / _cwA) * 0.5 * (double)_vh;")
    L.append("              const double _sx = MVector(_ow(0,0), _ow(0,1), _ow(0,2)).length();")
    L.append("              const double _sy = MVector(_ow(1,0), _ow(1,1), _ow(1,2)).length();")
    L.append("              const double _sz = MVector(_ow(2,0), _ow(2,1), _ow(2,2)).length();")
    L.append("              const double _prod = _sx * _sy * _sz;")
    L.append("              data->localPpu = _ppw * ((_prod > 0.0) ? std::cbrt(_prod) : 1.0);")
    L.append("          }")
    L.append("      }")
    L.append("    }")
    if scalars or meshes or needs_region or strings or colors or generics:
        L.append("    // --- user input plugs ---")
        L.append("    MFnDependencyNode fn(objPath.node());")
        if needs_region:
            L.append("    // settable face region (companion command writes this attr)")
            L.append("    { MStatus _rs; MPlug _rp = fn.findPlug(\"%s\", false, &_rs);"
                     % _REGION_ATTR)
            L.append("      if (_rs == MS::kSuccess && !_rp.isNull()) {")
            L.append("          MObject _rd = _rp.asMObject();")
            L.append("          if (!_rd.isNull() && _rd.hasFn(MFn::kIntArrayData)) {")
            L.append("              MFnIntArrayData _iad(_rd); MIntArray _ra = _iad.array();")
            L.append("              for (unsigned _i = 0; _i < _ra.length(); ++_i) inp.%s.push_back(_ra[_i]);"
                     % _REGION_ATTR)
            L.append("          }")
            L.append("      } }")
        for s in scalars:
            L += _loc_input_read(s["member"], s["plug"], s["type"])
        for s in strings:
            L.append("    { MStatus _ms; MPlug _p = fn.findPlug(\"%s\", false, &_ms);" % s["plug"])
            L.append("      if (_ms == MS::kSuccess && !_p.isNull()) inp.%s = _p.asString(); }"
                     % s["member"])
        for c in colors:
            L.append("    { MStatus _ms; MPlug _p = fn.findPlug(\"%s\", false, &_ms);" % c["plug"])
            L.append("      if (_ms == MS::kSuccess && !_p.isNull() && _p.numChildren() >= 3) {")
            L.append("          inp.%s[0] = _p.child(0).asFloat();" % c["member"])
            L.append("          inp.%s[1] = _p.child(1).asFloat();" % c["member"])
            L.append("          inp.%s[2] = _p.child(2).asFloat(); } }" % c["member"])
        for gm in generics:
            _t, _arr = gm["meta"]["type"], gm["meta"].get("is_array")
            _geo = emit_geo_io.is_geo(_t)
            if _geo:
                L += emit_geo_io.geo_plug_decls(gm)
            elif _arr:
                L.append(_read_plug_array_decl(gm))
            else:
                L.append(_read_plug_decl(gm))
            L.append("    { MStatus _ms; MPlug _p = fn.findPlug(\"%s\", false, &_ms);"
                     % gm["plug"])
            L.append("      if (_ms == MS::kSuccess && !_p.isNull()) {")
            if _geo and _arr:
                L += emit_geo_io.geo_plug_array_input_lines(gm, "_p")
            elif _geo:
                L += emit_geo_io.geo_plug_input_lines(gm, "_p")
            elif _arr:
                L += _read_plug_array_assign(gm, "_p")
            else:
                L.append(_read_plug_assign(gm, "_p"))
            L.append("      } }")
            L.append(_loc_generic_copy(gm))
        for m in meshes:
            L.append("    { MStatus _ms; MPlug _p = fn.findPlug(\"%s\", false, &_ms);" % m["plug"])
            L.append("      if (_ms == MS::kSuccess && !_p.isNull()) {")
            L.append("          MObject _mo = _p.asMObject();")
            L.append("          if (!_mo.isNull() && _mo.hasFn(MFn::kMesh)) {")
            L.append("              MFnMesh _fm(_mo);")
            L.append("              MPointArray _pa; _fm.getPoints(_pa, MSpace::kObject);")
            L.append("              for (unsigned _i = 0; _i < _pa.length(); ++_i) inp.%s.pts.push_back(_pa[_i]);" % m["member"])
            L.append("              MIntArray _vc, _vi; _fm.getVertices(_vc, _vi);")
            L.append("              for (unsigned _i = 0; _i < _vc.length(); ++_i) inp.%s.counts.push_back(_vc[_i]);" % m["member"])
            L.append("              for (unsigned _i = 0; _i < _vi.length(); ++_i) inp.%s.connects.push_back(_vi[_i]);" % m["member"])
            L.append("              MFloatVectorArray _nr; _fm.getVertexNormals(false, _nr, MSpace::kObject);")
            L.append("              for (unsigned _i = 0; _i < _nr.length(); ++_i) inp.%s.normals.push_back(MVector(_nr[_i].x, _nr[_i].y, _nr[_i].z));" % m["member"])
            # Component tags live on the mesh DATA, not on MFnMesh, so read them
            # from the SAME MObject. Without this the compute cannot resolve a
            # named region at all and silently draws nothing.
            L.append("              { MStatus _gs; MFnGeometryData _gd(_mo, &_gs);")
            L.append("                if (_gs == MS::kSuccess) {")
            L.append("                    MStringArray _tn; _gd.componentTags(_tn);")
            L.append("                    for (unsigned _t = 0; _t < _tn.length(); ++_t) {")
            L.append("                        MStatus _cs; MObject _comp = _gd.componentTagContents(_tn[_t], &_cs);")
            L.append("                        if (_cs != MS::kSuccess || _comp.isNull()) continue;")
            L.append("                        MFnSingleIndexedComponent _sic(_comp, &_cs);")
            L.append("                        if (_cs != MS::kSuccess) continue;")
            L.append("                        MIntArray _ids; _sic.getElements(_ids);")
            L.append("                        std::vector<int> _tv; _tv.reserve(_ids.length());")
            L.append("                        for (unsigned _k = 0; _k < _ids.length(); ++_k) _tv.push_back(_ids[_k]);")
            L.append("                        inp.%s.tagNames.push_back(std::string(_tn[_t].asChar()));" % m["member"])
            L.append("                        inp.%s.tagIds.push_back(_tv);" % m["member"])
            L.append("                    }")
            # The SOURCE TRANSFORM rides the same data. Points read above are
            # OBJECT space (a data-built MFnMesh has no DAG path, so kWorld is
            # unreachable); without this a world-space patch draws at the origin.
            L.append("                    MMatrix _wm;")
            L.append("                    if (_gd.getMatrix(_wm) == MS::kSuccess) {")
            L.append("                        for (int _r = 0; _r < 4; ++_r)")
            L.append("                            for (int _c = 0; _c < 4; ++_c)")
            L.append("                                inp.%s.matrix[_r * 4 + _c] = _wm(_r, _c);" % m["member"])
            L.append("                    }")
            L.append("                } }")
            L.append("              inp.%s.present = true;" % m["member"])
            L.append("          }")
            L.append("      } }")
    L.append("    %s_computeBuffers(inp, *data);" % cls)
    if svars:
        L.append("    { %s& _tw = g_tween[_nodeHash];   // persist mutated stored vars"
                 % tween_cls)
        for v in svars:
            L.append("      _tw.%s = data->sv_%s;" % (v["name"], v["name"]))
        L.append("    }")
    if needs_hover:
        L.append("    // idle redraw: keep ticking while the tween is animating")
        L.append("    if (data->autoRefresh) g_autoRefresh.insert(_nodeHash);")
        L.append("    else g_autoRefresh.erase(_nodeHash);")
        L.append("    // precise hover: register the drawn triangle soup (node flag OR a")
        L.append("    // per-item precise_hover); _setHoverTris clears when nothing opted in.")
        L.append("    { std::vector<MPoint> _htris; _buildHoverTris(*data, objPath, _htris);")
        L.append("      _setHoverTris(_nodeHash, _htris); }")
    L.append("    // Frame Selected must fit the drawing, not MPxLocatorNode's unit box.")
    L.append("    // The hash is taken here rather than from the hover path's _nodeHash,")
    L.append("    // which a locator with no hover and no stored vars never declares; it")
    L.append("    // is the same key boundingBox() looks up.")
    L.append("    { const unsigned _bbHash = MObjectHandle(objPath.node()).hashCode();")
    L.append("      MBoundingBox _bb; const bool _anyBB = _drawnBounds(*data, _bb);")
    L.append("      _setBBox(_bbHash, _bb, _anyBB); }")
    L.append("    data->selected = inp.selected;")
    L.append("    data->selColor = MColor(inp.selColor[0], inp.selColor[1], inp.selColor[2], inp.selColor[3]);")
    L.append("    return data;")
    L.append("}")
    L.append("")
    # ---- addUIDrawables ------------------------------------------------------
    # Selection tint. Port of MPyLocatorDrawOverride._tinted: the highlight
    # replaces HUE, never opacity, so a translucent drawing stays translucent
    # while selected instead of snapping solid.
    L.append("// Selection tint: Maya's wireframe color over the element's OWN alpha")
    L.append("// (port of MPyLocatorDrawOverride._tinted -- the highlight changes what")
    L.append("// color a drawing is, not how much you can see through it).")
    L.append("static inline MColor _selTint(const MColor& sel, const MColor& own) {")
    L.append("    return MColor(sel.r, sel.g, sel.b, own.a);")
    L.append("}")
    L.append("")
    # One polygon soup, drawn where its DrawCmd sits in the ordered list.
    L.append("// Draw ONE polygon soup (fill: fan-triangulate; optional backface cull,")
    L.append("// world-space rebase, wireframe overlay). ``wInv`` is the frame's")
    L.append("// world->local inverse, applied only when the soup is world-space.")
    L.append("static void _drawPoly(MHWRender::MUIDrawManager& dm, const %s& d," % data_cls)
    L.append("                      const DrawPoly& pg, const MMatrix& wInv) {")
    L.append("    if (pg.pts.empty() || pg.cnt.empty()) return;")
    L.append("    const bool selOK = d.selected;")
    L.append("    // Per-aspect selection highlight; an unset flag inherits the node-wide")
    L.append("    // self.auto_highlight (_draw_polygons' highlight_fill/highlight_wire")
    L.append("    // default to global_auto_highlight).")
    L.append("    const bool hlFill = (pg.highlightFill < 0) ? d.autoHighlight")
    L.append("                                              : (pg.highlightFill != 0);")
    L.append("    const bool hlWire = (pg.highlightWire < 0) ? d.autoHighlight")
    L.append("                                              : (pg.highlightWire != 0);")
    L.append("    std::vector<MPoint> P = pg.pts;")
    L.append("    if (pg.worldSpace) {")
    L.append("        for (size_t i = 0; i < P.size(); ++i) P[i] = P[i] * wInv;")
    L.append("    }")
    L.append("    const size_t F = pg.cnt.size();")
    L.append("    std::vector<int> off(F, 0);")
    L.append("    for (size_t f = 1; f < F; ++f) off[f] = off[f-1] + pg.cnt[f-1];")
    L.append("    MPoint vp(d.viewPosLocal[0], d.viewPosLocal[1], d.viewPosLocal[2]);")
    L.append("    std::vector<char> faceVisible(F, 1);")
    L.append("    if (pg.cull) {")
    L.append("        for (size_t f = 0; f < F; ++f) {")
    L.append("            int c = pg.cnt[f]; if (c < 3) { faceVisible[f] = 0; continue; }")
    L.append("            MPoint p0 = P[pg.idx[off[f]]];")
    L.append("            MPoint p1 = P[pg.idx[off[f]+1]];")
    L.append("            MPoint p2 = P[pg.idx[off[f]+2]];")
    L.append("            MVector nrm = (p1 - p0) ^ (p2 - p0);")
    L.append("            MVector vd = vp - p0;")
    L.append("            faceVisible[f] = (nrm * vd > 0.0) ? 1 : 0;")
    L.append("        }")
    L.append("    }")
    L.append("    MPointArray tri; MColorArray tcol;")
    L.append("    const bool perCorner = (pg.colorMode != 0);")
    L.append("    const bool tintFill = (selOK && hlFill);")
    L.append("    for (size_t f = 0; f < F; ++f) {")
    L.append("        if (!faceVisible[f]) continue;")
    L.append("        int c = pg.cnt[f]; if (c < 3) continue;")
    L.append("        for (int k = 1; k + 1 < c; ++k) {")
    L.append("            int corner[3] = {0, k, k + 1};")
    L.append("            for (int t = 0; t < 3; ++t) {")
    L.append("                int loc = off[f] + corner[t];")
    L.append("                int vid = pg.idx[loc];")
    L.append("                tri.append(P[vid]);")
    L.append("                if (perCorner) {")
    L.append("                    MColor col;")
    L.append("                    if (pg.colorMode == 1 && f < pg.faceColors.size()) col = pg.faceColors[f];")
    L.append("                    else if (pg.colorMode == 2 && vid < (int)pg.vertexColors.size()) col = pg.vertexColors[vid];")
    L.append("                    else if (pg.colorMode == 3 && loc < (int)pg.faceVertexColors.size()) col = pg.faceVertexColors[loc];")
    L.append("                    tcol.append(tintFill ? _selTint(d.selColor, col) : col);")
    L.append("                }")
    L.append("            }")
    L.append("        }")
    L.append("    }")
    L.append("    if (tri.length() >= 3) {")
    L.append("        dm.beginDrawable();")
    L.append("        // A tint rides on the colors already built (per corner above, or the")
    L.append("        // uniform below), so the soup keeps its own alpha while selected.")
    L.append("        if (perCorner) { dm.mesh(MHWRender::MUIDrawManager::kTriangles, tri, NULL, &tcol); }")
    L.append("        else { dm.setColor(tintFill ? _selTint(d.selColor, pg.uniform) : pg.uniform);")
    L.append("               dm.mesh(MHWRender::MUIDrawManager::kTriangles, tri); }")
    L.append("        dm.endDrawable();")
    L.append("    }")
    L.append("    // wireframe overlay (optional boundary-only; respects cull)")
    L.append("    if (pg.hasWire) {")
    L.append("        std::map<long long, int> edgeCount;")
    L.append("        std::vector<std::pair<int,int> > edges;")
    L.append("        for (size_t f = 0; f < F; ++f) {")
    L.append("            if (!faceVisible[f]) continue;")
    L.append("            int c = pg.cnt[f]; if (c < 2) continue;")
    L.append("            for (int k = 0; k < c; ++k) {")
    L.append("                int a = pg.idx[off[f] + k];")
    L.append("                int b = pg.idx[off[f] + ((k + 1) % c)];")
    L.append("                int lo = a < b ? a : b, hi = a < b ? b : a;")
    L.append("                long long key = (long long)lo * 1000000LL + hi;")
    L.append("                if (edgeCount.find(key) == edgeCount.end()) edges.push_back(std::make_pair(lo, hi));")
    L.append("                edgeCount[key] += 1;")
    L.append("            }")
    L.append("        }")
    L.append("        const MColor wcol = (selOK && hlWire) ? _selTint(d.selColor, pg.wireColor)")
    L.append("                                              : pg.wireColor;")
    L.append("        dm.beginDrawable();")
    L.append("        dm.setColor(wcol);")
    L.append("        dm.setLineWidth((float)pg.wireWidth);")
    L.append("        for (size_t e = 0; e < edges.size(); ++e) {")
    L.append("            int lo = edges[e].first, hi = edges[e].second;")
    L.append("            long long key = (long long)lo * 1000000LL + hi;")
    L.append("            if (pg.wireBoundaryOnly && edgeCount[key] != 1) continue;")
    L.append("            dm.line(P[lo], P[hi]);")
    L.append("        }")
    L.append("        dm.endDrawable();")
    L.append("    }")
    L.append("}")
    L.append("")
    L.append("// Whole-pixel point size. VP2 draws fat points through a shader whose size is")
    L.append("// a parameter and caches the instance BY VALUE: every distinct size is a new")
    L.append("// instance (~85 us measured per point), a repeated value is ~free. Continuous")
    L.append("// sizes made every point its own instance -- 56% of a locator's draw cost.")
    L.append("// Rounding bounds the distinct values scene-wide (<= 0.5 px change); the")
    L.append("// interpreted framework rounds identically (draw_buffers.point_pixel_size).")
    L.append("static float _pointPx(float s) { long p = std::lround((double)s); return (float)(p < 1 ? 1 : p); }")
    L.append("// Port of draw_buffers.local_text_pixel_size: an object-space glyph height")
    L.append("// becomes bitmap-font pixels at this depth, clamped to [6, 256]. With no view")
    L.append("// scale (headless / degenerate) the size is taken as pixels, as the framework")
    L.append("// does when local_ppu is None.")
    L.append("static unsigned _textPx(double size, double ppu) {")
    L.append("    if (ppu <= 0.0) return (unsigned)(size < 0.0 ? 0.0 : size);")
    L.append("    double px = size * ppu; if (px < 6.0) px = 6.0; if (px > 256.0) px = 256.0;")
    L.append("    return (unsigned)std::lround(px);")
    L.append("}")
    L.append("")
    L.append("void %s::addUIDrawables(const MDagPath& objPath," % draw_cls)
    L.append("                        MHWRender::MUIDrawManager& dm,")
    L.append("                        const MHWRender::MFrameContext& frameContext,")
    L.append("                        const MUserData* userData) {")
    L.append("    (void)frameContext;")
    L.append("    const %s* d = dynamic_cast<const %s*>(userData);" % (data_cls, data_cls))
    L.append("    if (!d) return;")
    L.append("    // Framework auto-highlight (MPyLocatorDrawOverride.addUIDrawables'")
    L.append("    // override_color): when selected AND self.auto_highlight, every")
    L.append("    // line/point/text/shape takes the selection color -- its RGB over the")
    L.append("    // element's own alpha, so translucent stays translucent. Polygons decide")
    L.append("    // per aspect, inside _drawPoly.")
    L.append("    const bool hlAll = (d->selected && d->autoHighlight);")
    L.append("    // one world->local inverse per frame; world-space items rebase with it")
    L.append("    const MMatrix wInv = objPath.inclusiveMatrixInverse();")
    L.append("    // replay the drawing FRONT TO BACK -- authoring order is draw order.")
    L.append("    // ONE drawable batch per node (like the interpreted framework): a")
    L.append("    // begin/end pair per item cost 10% of the per-node draw time at N=100.")
    L.append("    dm.beginDrawable();")
    L.append("    for (size_t ci = 0; ci < d->cmds.size(); ++ci) {")
    L.append("        const int i = d->cmds[ci].index;")
    L.append("        switch (d->cmds[ci].slot) {")
    L.append("            case 0: {  // line")
    L.append("                MPoint a = d->lineStart[i], b = d->lineEnd[i];")
    L.append("                if (d->lineWorld[i]) { a = a * wInv; b = b * wInv; }")
    L.append("                dm.setColor(hlAll ? _selTint(d->selColor, d->lineColor[i]) : d->lineColor[i]);")
    L.append("                dm.line(a, b);")
    L.append("            } break;")
    L.append("            case 1: {  // point")
    L.append("                dm.setColor(hlAll ? _selTint(d->selColor, d->pointColor[i]) : d->pointColor[i]);")
    L.append("                dm.setPointSize(_pointPx(d->pointSize[i])); dm.point(d->pointPos[i]);")
    L.append("            } break;")
    L.append("            case 2: {  // text")
    L.append("                dm.setColor(hlAll ? _selTint(d->selColor, d->textColor[i]) : d->textColor[i]);")
    L.append("                dm.setFontSize(_textPx(d->textSize[i], d->localPpu));")
    L.append("                dm.text(d->textPos[i], d->textStr[i]);")
    L.append("            } break;")
    L.append("            case 3: {  // shape")
    L.append("                dm.setColor(hlAll ? _selTint(d->selColor, d->shapeColor[i]) : d->shapeColor[i]);")
    L.append("                const bool fl = d->shapeFilled[i] != 0;")
    L.append("                switch (d->shapeKind[i]) {")
    L.append("                    case 0: dm.sphere(d->shapeCenter[i], d->shapeRadius[i], fl); break;")
    L.append("                    case 1: dm.circle(d->shapeCenter[i], d->shapeAxis[i], d->shapeRadius[i], fl); break;")
    L.append("                    case 2: dm.box(d->shapeCenter[i], MVector(0,1,0), MVector(1,0,0),")
    L.append("                                   d->shapeRadius[i], d->shapeRadius[i], d->shapeRadius[i], fl); break;")
    L.append("                    case 3: dm.cone(d->shapeCenter[i], d->shapeAxis[i], d->shapeRadius[i], d->shapeRadius[i]*2.0, fl); break;")
    L.append("                    case 4: dm.cylinder(d->shapeCenter[i], d->shapeAxis[i], d->shapeRadius[i], d->shapeRadius[i]*2.0, 16, fl); break;")
    L.append("                    default: dm.circle(d->shapeCenter[i], d->shapeAxis[i], d->shapeRadius[i], fl); break;")
    L.append("                }")
    L.append("            } break;")
    L.append("            // polygons open their own batches: close ours around the call")
    L.append("            default: dm.endDrawable(); _drawPoly(dm, *d, d->polys[i], wInv); dm.beginDrawable(); break;")
    L.append("        }")
    L.append("    }")
    L.append("    dm.endDrawable();")
    L.append("}")
    L.append("")
    # ---- registration --------------------------------------------------------
    L.append("MStatus initializePlugin(MObject obj) {")
    L.append('    MFnPlugin plugin(obj, "mpynode-native", "1.0", "Any");')
    L.append("    MStatus st = plugin.registerNode(")
    L.append('        "%s", %s::id, %s::creator, %s::initialize,'
             % (type_name, cls, cls, cls))
    L.append("        MPxNode::kLocatorNode, &%s::drawDbClassification);" % cls)
    L.append("    if (!st) return st;")
    for reg in cmd_out["register"]:
        L.append("    " + reg)
    for reg in disp_out["register"]:
        L.append("    " + reg)
    L.append("    return MHWRender::MDrawRegistry::registerDrawOverrideCreator(")
    L.append("        %s::drawDbClassification, %s::drawRegistrantId, %s::creator);"
             % (cls, cls, draw_cls))
    L.append("}")
    L.append("MStatus uninitializePlugin(MObject obj) {")
    if needs_hover:
        L.append("    _stopHover();  // tear down the hover timer + scene callbacks")
    elif svars:
        L.append("    _stopHover();  // tear down the stored-var scene callbacks")
    L.append("    MFnPlugin plugin(obj);")
    L.append("    MHWRender::MDrawRegistry::deregisterDrawOverrideCreator(")
    L.append("        %s::drawDbClassification, %s::drawRegistrantId);" % (cls, cls))
    for dereg in cmd_out["deregister"]:
        L.append("    " + dereg)
    for dereg in disp_out["deregister"]:
        L.append("    " + dereg)
    L.append("    return plugin.deregisterNode(%s::id);" % cls)
    L.append("}")
    L.append("")
    L.append("#endif  // !MPYNODE_PROBE")
    L.append("")
    # ---- standalone probe (numerical buffer parity) -------------------------
    L.append("#ifdef MPYNODE_PROBE")
    L.append("// Standalone buffer dumper: reads a frame file (argv[1]) describing each")
    L.append("// frame's inputs, runs computeBuffers, prints the draw buffers as JSON.")
    L.append("// Compile with -DMPYNODE_PROBE as an executable; links OpenMaya+Foundation")
    L.append("// only. Used to numerically compare the ported draw math (incl. polygons)")
    L.append("// against the original Python evaluateDrawItems().")
    L.append("static void _emitPts(const std::vector<MPoint>& v) {")
    L.append('    printf("[");')
    L.append("    for (size_t i = 0; i < v.size(); ++i)")
    L.append('        printf("%s[%.9g,%.9g,%.9g]", i?",":"", v[i].x, v[i].y, v[i].z);')
    L.append('    printf("]");')
    L.append("}")
    L.append("static void _emitVecs(const std::vector<MVector>& v) {")
    L.append('    printf("[");')
    L.append("    for (size_t i = 0; i < v.size(); ++i)")
    L.append('        printf("%s[%.9g,%.9g,%.9g]", i?",":"", v[i].x, v[i].y, v[i].z);')
    L.append('    printf("]");')
    L.append("}")
    L.append("static void _emitCols(const std::vector<MColor>& v) {")
    L.append('    printf("[");')
    L.append("    for (size_t i = 0; i < v.size(); ++i)")
    L.append('        printf("%s[%.9g,%.9g,%.9g,%.9g]", i?",":"", v[i].r, v[i].g, v[i].b, v[i].a);')
    L.append('    printf("]");')
    L.append("}")
    L.append("static void _emitCol(const MColor& c) {")
    L.append('    printf("[%.9g,%.9g,%.9g,%.9g]", c.r, c.g, c.b, c.a);')
    L.append("}")
    L.append("template<class T> static void _emitNums(const std::vector<T>& v) {")
    L.append('    printf("[");')
    L.append("    for (size_t i = 0; i < v.size(); ++i)")
    L.append('        printf("%s%.9g", i?",":"", (double)v[i]);')
    L.append('    printf("]");')
    L.append("}")
    L.append("static void _emitStrs(const std::vector<MString>& v) {")
    L.append('    printf("[");')
    L.append("    for (size_t i = 0; i < v.size(); ++i)")
    L.append('        printf("%s\\"%s\\"", i?",":"", v[i].asChar());')
    L.append('    printf("]");')
    L.append("}")
    L.append("static void _emitCmds(const std::vector<DrawCmd>& v) {")
    L.append("    static const char* kSlot[] = {\"lines\",\"points\",\"text\",\"shapes\",\"polygons\"};")
    L.append('    printf("[");')
    L.append("    for (size_t i = 0; i < v.size(); ++i) {")
    L.append("        int s = v[i].slot; if (s < 0 || s > 4) s = 4;")
    L.append('        printf("%s[\\"%s\\",%d]", i?",":"", kSlot[s], v[i].index);')
    L.append("    }")
    L.append('    printf("]");')
    L.append("}")
    L.append("static void _emitPolys(const std::vector<DrawPoly>& v) {")
    L.append('    printf("[");')
    L.append("    for (size_t i = 0; i < v.size(); ++i) {")
    L.append("        const DrawPoly& pg = v[i];")
    L.append('        printf("%s{", i?",":"");')
    L.append('        printf("\\"points\\":"); _emitPts(pg.pts); printf(",");')
    L.append('        printf("\\"indices\\":"); _emitNums(pg.idx); printf(",");')
    L.append('        printf("\\"counts\\":"); _emitNums(pg.cnt); printf(",");')
    L.append('        printf("\\"colorMode\\":%d,", pg.colorMode);')
    L.append('        printf("\\"uniform\\":"); _emitCol(pg.uniform); printf(",");')
    L.append('        printf("\\"faceColors\\":"); _emitCols(pg.faceColors); printf(",");')
    L.append('        printf("\\"vertexColors\\":"); _emitCols(pg.vertexColors); printf(",");')
    L.append('        printf("\\"faceVertexColors\\":"); _emitCols(pg.faceVertexColors); printf(",");')
    L.append('        printf("\\"cull\\":%d,", pg.cull?1:0);')
    L.append('        printf("\\"wire\\":%d,", pg.hasWire?1:0);')
    L.append('        printf("\\"wireColor\\":"); _emitCol(pg.wireColor); printf(",");')
    L.append('        printf("\\"wireWidth\\":%.9g,", pg.wireWidth);')
    L.append('        printf("\\"wireBoundaryOnly\\":%d,", pg.wireBoundaryOnly?1:0);')
    L.append('        printf("\\"worldSpace\\":%d,", pg.worldSpace?1:0);')
    L.append('        printf("\\"highlightFill\\":%d,", pg.highlightFill?1:0);')
    L.append('        printf("\\"highlightWire\\":%d,", pg.highlightWire?1:0);')
    L.append('        printf("\\"preciseHover\\":%d", pg.preciseHover?1:0);')
    L.append('        printf("}");')
    L.append("    }")
    L.append('    printf("]");')
    L.append("}")
    # per-frame input setter for scalar inputs
    L.append("static void _setInput(%s& f, const std::string& n, double v) {" % inp_cls)
    if scalars:
        first = True
        for s in scalars:
            kw    = "if" if first else "else if"
            first = False
            if s["type"] == "bool":
                L.append('    %s (n == "%s") f.%s = (v != 0.0);' % (kw, s["member"], s["member"]))
            elif s["type"] == "enum":
                L.append('    %s (n == "%s") f.%s = (short)v;' % (kw, s["member"], s["member"]))
            elif s["type"] == "int":
                L.append('    %s (n == "%s") f.%s = (int)v;' % (kw, s["member"], s["member"]))
            else:
                L.append('    %s (n == "%s") f.%s = (float)v;' % (kw, s["member"], s["member"]))
        L.append("    else { (void)f; (void)n; (void)v; }")
    else:
        L.append("    (void)f; (void)n; (void)v;")
    L.append("}")
    L.append("static std::vector<%s> _readFrames(const char* path) {" % inp_cls)
    L.append("    std::vector<%s> out;" % inp_cls)
    L.append("    FILE* fp = fopen(path, \"r\"); if (!fp) return out;")
    L.append("    char tok[256]; %s cur; bool inFrame = false; (void)inFrame;" % inp_cls)
    L.append("    while (fscanf(fp, \"%255s\", tok) == 1) {")
    L.append("        std::string k(tok);")
    L.append('        if (k == "FRAME") { cur = %s(); inFrame = true; }' % inp_cls)
    L.append('        else if (k == "ENDFRAME") { out.push_back(cur); inFrame = false; }')
    L.append('        else if (k == "TIME") { double x; if(fscanf(fp, "%lf", &x)==1) cur.timeVal = x; }')
    L.append('        else if (k == "WALL") { double x; if(fscanf(fp, "%lf", &x)==1) cur.wallClock = x; }')
    L.append('        else if (k == "STATE") { int a,b,c; if(fscanf(fp, "%d %d %d", &a,&b,&c)==3){ cur.selected=a; cur.isLead=b; cur.hovered=c; } }')
    L.append('        else if (k == "SELCOL") { float r,g,b,a; if(fscanf(fp, "%f %f %f %f", &r,&g,&b,&a)==4){ cur.selColor[0]=r; cur.selColor[1]=g; cur.selColor[2]=b; cur.selColor[3]=a; } }')
    L.append('        else if (k == "IN") { char nm[128]; double x; if(fscanf(fp, "%127s %lf", nm, &x)==2) _setInput(cur, std::string(nm), x); }')
    if has_mesh:
        mm = meshes[0]["member"]
        L.append('        else if (k == "MESHPTS") { int n; if(fscanf(fp, "%%d", &n)==1){ cur.%s.pts.clear(); for(int i=0;i<n;++i){ double a,b,c; if(fscanf(fp,"%%lf %%lf %%lf",&a,&b,&c)==3) cur.%s.pts.push_back(MPoint(a,b,c)); } cur.%s.present = true; } }' % (mm, mm, mm))
        L.append('        else if (k == "MESHCNT") { int n; if(fscanf(fp, "%%d", &n)==1){ cur.%s.counts.clear(); for(int i=0;i<n;++i){ int a; if(fscanf(fp,"%%d",&a)==1) cur.%s.counts.push_back(a); } } }' % (mm, mm))
        L.append('        else if (k == "MESHCON") { int n; if(fscanf(fp, "%%d", &n)==1){ cur.%s.connects.clear(); for(int i=0;i<n;++i){ int a; if(fscanf(fp,"%%d",&a)==1) cur.%s.connects.push_back(a); } } }' % (mm, mm))
        L.append('        else if (k == "MESHNRM") { int n; if(fscanf(fp, "%%d", &n)==1){ cur.%s.normals.clear(); for(int i=0;i<n;++i){ double a,b,c; if(fscanf(fp,"%%lf %%lf %%lf",&a,&b,&c)==3) cur.%s.normals.push_back(MVector(a,b,c)); } } }' % (mm, mm))
    if needs_region:
        # FACEIDS feeds the settable region (inp.<region>) so the probe can
        # exercise the deterministic mesh-region draw for compiled-vs-Python
        # parity (needs_region implies a mesh input, so this chains after MESH*).
        L.append('        else if (k == "FACEIDS") { int n; if(fscanf(fp, "%%d", &n)==1){ cur.%s.clear(); for(int i=0;i<n;++i){ int a; if(fscanf(fp,"%%d",&a)==1) cur.%s.push_back(a); } } }' % (_REGION_ATTR, _REGION_ATTR))
    L.append("    }")
    L.append("    fclose(fp); return out;")
    L.append("}")
    L.append("int main(int argc, char** argv) {")
    L.append("    std::vector<%s> frames;" % inp_cls)
    L.append("    if (argc > 1) frames = _readFrames(argv[1]);")
    L.append("    if (frames.empty()) { %s f; frames.push_back(f); }" % inp_cls)
    L.append('    printf("[");')
    L.append("    for (size_t k = 0; k < frames.size(); ++k) {")
    L.append("        %s data; %s_computeBuffers(frames[k], data);" % (data_cls, cls))
    L.append('        printf("%s{", k?",":"");')
    L.append('        printf("\\"time\\":%.9g,", frames[k].timeVal);')
    L.append('        printf("\\"cmds\\":");      _emitCmds(data.cmds);     printf(",");')
    L.append('        printf("\\"lineStart\\":"); _emitPts(data.lineStart); printf(",");')
    L.append('        printf("\\"lineEnd\\":");   _emitPts(data.lineEnd);   printf(",");')
    L.append('        printf("\\"lineColor\\":"); _emitCols(data.lineColor); printf(",");')
    L.append('        printf("\\"lineWorld\\":"); _emitNums(data.lineWorld); printf(",");')
    L.append('        printf("\\"pointPos\\":");  _emitPts(data.pointPos);  printf(",");')
    L.append('        printf("\\"pointColor\\":");_emitCols(data.pointColor);printf(",");')
    L.append('        printf("\\"pointSize\\":"); _emitNums(data.pointSize); printf(",");')
    L.append('        printf("\\"textPos\\":");   _emitPts(data.textPos);   printf(",");')
    L.append('        printf("\\"textStr\\":");   _emitStrs(data.textStr);  printf(",");')
    L.append('        printf("\\"textColor\\":"); _emitCols(data.textColor);printf(",");')
    L.append('        printf("\\"textSize\\":");  _emitNums(data.textSize); printf(",");')
    L.append('        printf("\\"shapeKind\\":"); _emitNums(data.shapeKind);printf(",");')
    L.append('        printf("\\"shapeCenter\\":");_emitPts(data.shapeCenter);printf(",");')
    L.append('        printf("\\"shapeRadius\\":");_emitNums(data.shapeRadius);printf(",");')
    L.append('        printf("\\"shapeAxis\\":"); _emitVecs(data.shapeAxis); printf(",");')
    L.append('        printf("\\"shapeColor\\":");_emitCols(data.shapeColor);printf(",");')
    L.append('        printf("\\"shapeFilled\\":");_emitNums(data.shapeFilled);printf(",");')
    L.append('        printf("\\"polys\\":"); _emitPolys(data.polys);')
    L.append('        printf("}");')
    L.append("    }")
    L.append('    printf("]\\n");')
    L.append("    return 0;")
    L.append("}")
    L.append("#endif")
    L.append("")
    return "\n".join(L)
