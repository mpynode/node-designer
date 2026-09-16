"""Shared C++ geometry value model for plain-node geo OUTPUTS and geo ARRAYS.

The geo GENERATOR path (emit_geo._generate_geo_cpp) fills a fixed set of bare
buffers and builds ONE synthesized output; it stays byte-identical. This module
adds the reusable pieces the *generic* MPxNode path needs to support a geo type
in the three remaining attribute cells:

  * single geo OUTPUT on a plain node   -> ``NdMesh out_<m>; ... build+set``
  * array (list) geo INPUT              -> ``std::vector<NdMesh> in_<m>``
  * array (list) geo OUTPUT             -> ``std::vector<NdMesh> out_<m>``

A geo value is carried as a small readback/build struct (``NdMesh`` / ``NdCurve``
/ ``NdSurface``) with free helpers:

  * ``nd_read_<kind>(const MObject& dataObj) -> Nd<Kind>`` -- extract via the SAME
    MFn* calls the interpreted wrapper + nd_lower._materialise_geo_channel use, so
    a compiled read is byte-identical to the interpreted numpy surface.
  * ``nd_build_<kind>(const Nd<Kind>&) -> MObject`` -- topology-guarded
    MFn*::create into a fresh MFn*Data MObject (mirrors emit_geo._geo_build_lines
    / _api2.geometry.build_*_data): a violated invariant yields an EMPTY geometry,
    never an out-of-bounds crash.

The emitted block carries its own ``#ifndef`` include guard so it is idempotent
when several nodes are concatenated into one bundle translation unit.
"""
from __future__ import annotations

# attr type -> internal kind used by every table here.
_KIND = {"mesh": "mesh", "nurbsCurve": "curve", "nurbsSurface": "surface"}

# C++ struct type name per kind.
_STRUCT = {"mesh": "NdMesh", "curve": "NdCurve", "surface": "NdSurface"}

# Include sets per kind, merged into the node's includes when a geo array/output
# of that kind is present. MPoint/MVector/vector/string/map are common.
_COMMON_INCLUDES = [
    "vector", "string", "map",
    "maya/MObject.h", "maya/MFn.h", "maya/MFnData.h",
    "maya/MPoint.h", "maya/MPointArray.h", "maya/MVector.h",
    "maya/MDataHandle.h", "maya/MArrayDataHandle.h", "maya/MArrayDataBuilder.h",
    # NOTE: MSpace is pulled transitively by the MFn* geo headers (there is no
    # maya/MSpace.h); the generator path relies on the same transitive include.
]
_KIND_INCLUDES = {
    "mesh": ["maya/MFnMesh.h", "maya/MFnMeshData.h", "maya/MIntArray.h",
             "maya/MFloatVectorArray.h", "maya/MVectorArray.h",
             "maya/MColor.h", "maya/MColorArray.h",
             # UV read surface (nd_read_mesh getUVSetNames + getUVs).
             "maya/MStringArray.h", "maya/MFloatArray.h"],
    "curve": ["maya/MFnNurbsCurve.h", "maya/MFnNurbsCurveData.h",
              "maya/MDoubleArray.h"],
    "surface": ["maya/MFnNurbsSurface.h", "maya/MFnNurbsSurfaceData.h",
                "maya/MDoubleArray.h"],
}


def kinds_in_spec(spec):
    """Set of geo kinds ("mesh"/"curve"/"surface") that appear as an ARRAY input,
    or as ANY geo output (single or array), on a plain MPxNode -- i.e. the cells
    this module services. A single geo INPUT is handled by emit_attr._read_line
    and does NOT need this module."""
    kinds = set()
    for grp in ("inputs", "outputs"):
        for _plug, meta in (spec.get(grp) or {}).items():
            t = meta.get("type")
            if t not in _KIND:
                continue
            if grp == "outputs" or meta.get("is_array"):
                kinds.add(_KIND[t])
    return kinds


def geo_io_includes(kinds):
    """Includes needed for the emitted helpers of ``kinds`` (a set)."""
    inc = list(_COMMON_INCLUDES)
    for k in ("mesh", "curve", "surface"):
        if k in kinds:
            for h in _KIND_INCLUDES[k]:
                if h not in inc:
                    inc.append(h)
    return inc


# ---- struct + read + build C++ (emitted text) -----------------------------

_MESH_CPP = r"""
struct NdMesh {
    bool present;
    std::vector<MPoint>  points;
    std::vector<int>     counts;
    std::vector<int>     indices;
    std::vector<MVector> normals;
    std::vector<int>     normalIndices;
    std::vector<MColor>  colors;
    std::vector<int>     colorIndices;
    std::vector<double>  uvs;     // flat (u,v) pairs of the first non-empty UV set
    long                 numUVs;  // uvs.size()/2 (points into the (M,2) UV space)
    // The UV ASSIGNMENT of that same set: uv-verts per face (parallels counts)
    // and flat uvIds into uvs. Without these the points alone cannot be written
    // back, which is why a compiled mesh used to come out unwrapped.
    std::vector<int>     uvCounts;
    std::vector<int>     uvIds;
    std::map<std::string, std::vector<int> > component_tags;
    NdMesh() : present(false), numUVs(0) {}
};

static NdMesh nd_read_mesh(const MObject& _o) {
    NdMesh g;
    if (_o.isNull() || !_o.hasFn(MFn::kMesh)) return g;
    MFnMesh _fn(_o);
    g.present = true;
    // Object-space positions straight off the mesh's internal float array. Maya
    // stores vertices as float3, so getPoints(kObject) is that same array widened
    // to double -- reading it raw skips the MPointArray copy and is bit-identical
    // (kObject only: any other space would apply a matrix in double).
    const float* _rp = _fn.getRawPoints(NULL);
    unsigned int _nv = (_rp == 0) ? 0 : (unsigned int)_fn.numVertices();
    g.points.resize(_nv);
    for (unsigned int i = 0; i < _nv; ++i)
        g.points[i] = MPoint((double)_rp[3 * i], (double)_rp[3 * i + 1],
                             (double)_rp[3 * i + 2]);
    // Topology and normals in bulk: MIntArray::get copies the whole array in one
    // call instead of one operator[] per element.
    MIntArray _gc, _gv; _fn.getVertices(_gc, _gv);
    g.counts.resize(_gc.length());
    if (_gc.length()) _gc.get(g.counts.data());
    g.indices.resize(_gv.length());
    if (_gv.length()) _gv.get(g.indices.data());
    MFloatVectorArray _na; _fn.getVertexNormals(false, _na, MSpace::kObject);
    g.normals.resize(_na.length());
    for (unsigned int i = 0; i < _na.length(); ++i) g.normals[i] = MVector(_na[i]);
    // UVs of the FIRST non-empty UV set (matches interp Mesh.uvs = uv_sets[0].points).
    MStringArray _sn; _fn.getUVSetNames(_sn);
    for (unsigned int _si = 0; _si < _sn.length(); ++_si) {
        MString _setn = _sn[_si];
        MFloatArray _ua, _va; _fn.getUVs(_ua, _va, &_setn);
        if (_ua.length() == 0) continue;
        g.numUVs = (long)_ua.length();
        g.uvs.reserve((size_t)g.numUVs * 2);
        for (unsigned int _ui = 0; _ui < _ua.length(); ++_ui) {
            g.uvs.push_back((double)_ua[_ui]); g.uvs.push_back((double)_va[_ui]);
        }
        // ...and the assignment for that SAME set, so nd_build_mesh can put it
        // back (points with no uvIds cannot be assigned to faces).
        MIntArray _uac, _uai; _fn.getAssignedUVs(_uac, _uai, &_setn);
        g.uvCounts.reserve(_uac.length());
        for (unsigned int _k = 0; _k < _uac.length(); ++_k)
            g.uvCounts.push_back(_uac[_k]);
        g.uvIds.reserve(_uai.length());
        for (unsigned int _k = 0; _k < _uai.length(); ++_k)
            g.uvIds.push_back(_uai[_k]);
        break;
    }
    return g;
}

static MObject nd_build_mesh(const NdMesh& g) {
    MStatus _st;
    MFnMeshData _dc;
    MObject _data = _dc.create(&_st);
    // Bulk constructors, not one append() per element: a 155k-vertex mesh soup
    // (meshMaze) is ~740k append calls otherwise -- and its ledger called the
    // node marshalling-bound.
    MPointArray _pa; if (!g.points.empty()) _pa = MPointArray(g.points.data(), (unsigned)g.points.size());
    MIntArray _pc; if (!g.counts.empty()) _pc = MIntArray(g.counts.data(), (unsigned)g.counts.size());
    MIntArray _ic; if (!g.indices.empty()) _ic = MIntArray(g.indices.data(), (unsigned)g.indices.size());
    long _sumc = 0; bool _ok = !g.points.empty() && !g.counts.empty();
    for (size_t i = 0; i < g.counts.size(); ++i) { if (g.counts[i] < 3) _ok = false; _sumc += g.counts[i]; }
    if ((long)g.indices.size() != _sumc) _ok = false;
    if (_ok)
        for (size_t i = 0; i < g.indices.size(); ++i)
            if (g.indices[i] < 0 || g.indices[i] >= (int)g.points.size()) { _ok = false; break; }
    if (_ok) {
        MFnMesh _mf;
        _mf.create((int)g.points.size(), (int)g.counts.size(), _pa, _pc, _ic, _data, &_st);
        if (!g.normals.empty()) {
            if (g.normalIndices.empty()) {
                if (g.normals.size() == g.points.size()) {
                    std::vector<int> _viv(g.normals.size());
                    for (size_t i = 0; i < _viv.size(); ++i) _viv[i] = (int)i;
                    MVectorArray _nr(g.normals.data(), (unsigned)g.normals.size());
                    MIntArray _vi(_viv.data(), (unsigned)_viv.size());
                    _mf.setVertexNormals(_nr, _vi);
                }
            } else if ((long)g.normalIndices.size() == _sumc) {
                bool _nok = true;
                for (size_t i = 0; i < g.normalIndices.size(); ++i)
                    if (g.normalIndices[i] < 0 || g.normalIndices[i] >= (int)g.normals.size()) { _nok = false; break; }
                if (_nok) {
                    std::vector<MVector> _nrv; std::vector<int> _fiv, _viv; int _off = 0;
                    _nrv.reserve((size_t)_sumc); _fiv.reserve((size_t)_sumc); _viv.reserve((size_t)_sumc);
                    for (size_t _f = 0; _f < g.counts.size(); ++_f) {
                        for (int _j = 0; _j < g.counts[_f]; ++_j) {
                            int _fv = _off + _j;
                            _nrv.push_back(g.normals[(size_t)g.normalIndices[(size_t)_fv]]);
                            _fiv.push_back((int)_f); _viv.push_back(g.indices[(size_t)_fv]);
                        }
                        _off += g.counts[_f];
                    }
                    MVectorArray _nr(_nrv.data(), (unsigned)_nrv.size());
                    MIntArray _fi(_fiv.data(), (unsigned)_fiv.size());
                    MIntArray _vi(_viv.data(), (unsigned)_viv.size());
                    _mf.setFaceVertexNormals(_nr, _fi, _vi);
                }
            }
        }
        if (!g.colors.empty()) {
            if (g.colorIndices.empty()) {
                if (g.colors.size() == g.points.size()) {
                    std::vector<int> _viv(g.colors.size());
                    for (size_t i = 0; i < _viv.size(); ++i) _viv[i] = (int)i;
                    MColorArray _co(g.colors.data(), (unsigned)g.colors.size());
                    MIntArray _vi(_viv.data(), (unsigned)_viv.size());
                    _mf.setVertexColors(_co, _vi);
                }
            } else if ((long)g.colorIndices.size() == _sumc) {
                bool _cok = true;
                for (size_t i = 0; i < g.colorIndices.size(); ++i)
                    if (g.colorIndices[i] < 0 || g.colorIndices[i] >= (int)g.colors.size()) { _cok = false; break; }
                if (_cok) {
                    std::vector<MColor> _cov; std::vector<int> _fiv, _viv; int _off = 0;
                    _cov.reserve((size_t)_sumc); _fiv.reserve((size_t)_sumc); _viv.reserve((size_t)_sumc);
                    for (size_t _f = 0; _f < g.counts.size(); ++_f) {
                        for (int _j = 0; _j < g.counts[_f]; ++_j) {
                            int _fv = _off + _j;
                            _cov.push_back(g.colors[(size_t)g.colorIndices[(size_t)_fv]]);
                            _fiv.push_back((int)_f); _viv.push_back(g.indices[(size_t)_fv]);
                        }
                        _off += g.counts[_f];
                    }
                    MColorArray _co(_cov.data(), (unsigned)_cov.size());
                    MIntArray _fi(_fiv.data(), (unsigned)_fiv.size());
                    MIntArray _vi(_viv.data(), (unsigned)_viv.size());
                    _mf.setFaceVertexColors(_co, _fi, _vi);
                }
            }
        }
        // UVs -- DEFAULT SET ONLY. MFnMesh::create auto-creates "map1" and
        // setUVs/assignUVs work on a mesh parented to an MFnMeshData;
        // createUVSet does NOT there (it raises "Object does not exist"), the
        // same limitation the colour path hits with createColorSet. Guards
        // mirror the interpreted _apply_mesh_uvs (geometry.py): the UV face
        // layout must equal the mesh's own, sum(uvCounts) must equal the
        // face-vertex total, and every uvId must be in range -- otherwise the
        // set is DROPPED rather than assigned as garbage.
        if (!g.uvs.empty() && g.uvCounts.size() == g.counts.size()) {
            const long _nuv = (long)(g.uvs.size() / 2);
            bool _uok = ((long)g.uvIds.size() == _sumc);
            for (size_t i = 0; _uok && i < g.uvCounts.size(); ++i)
                if (g.uvCounts[i] != g.counts[i]) _uok = false;
            for (size_t i = 0; _uok && i < g.uvIds.size(); ++i)
                if (g.uvIds[i] < 0 || g.uvIds[i] >= (int)_nuv) _uok = false;
            if (_uok) {
                // De-interleave into two double runs, then the bulk (double[])
                // constructors narrow to float exactly as append((float)x) did.
                std::vector<double> _ud((size_t)_nuv), _vd((size_t)_nuv);
                for (long i = 0; i < _nuv; ++i) {
                    _ud[(size_t)i] = g.uvs[(size_t)(2 * i)];
                    _vd[(size_t)i] = g.uvs[(size_t)(2 * i + 1)];
                }
                MFloatArray _su, _sv;
                if (_nuv) { _su = MFloatArray(_ud.data(), (unsigned)_nuv); _sv = MFloatArray(_vd.data(), (unsigned)_nuv); }
                MIntArray _auc, _aui;
                if (!g.uvCounts.empty()) _auc = MIntArray(g.uvCounts.data(), (unsigned)g.uvCounts.size());
                if (!g.uvIds.empty()) _aui = MIntArray(g.uvIds.data(), (unsigned)g.uvIds.size());
                _mf.setUVs(_su, _sv);
                _mf.assignUVs(_auc, _aui);
            }
        }
    }
    return _data;
}
"""

# knot builders shared by curve + surface (nd_-prefixed to avoid colliding with
# the generator's _buildOpenKnots).
_KNOTS_CPP = r"""
static void nd_buildOpenKnots(int numCVs, int degree, MDoubleArray& out) {
    int n = numCVs + degree - 1;
    if (n <= 0) return;
    int inner = n - 2 * degree; if (inner < 0) inner = 0;
    for (int i = 0; i < degree; ++i) out.append(0.0);
    for (int i = 0; i < inner; ++i) out.append((double)(i + 1));
    double last = (double)(inner + 1);
    for (int i = 0; i < degree; ++i) out.append(last);
    while ((int)out.length() > n) out.remove(out.length() - 1);
}
static void nd_buildPeriodicKnots(int numCVs, int degree, MDoubleArray& out) {
    int n = numCVs + degree - 1;
    if (n <= 0) return;
    for (int i = 0; i < n; ++i) out.append((double)(i - degree + 1));
}
"""

_CURVE_CPP = r"""
struct NdCurve {
    bool present;
    std::vector<MPoint> cvs;
    int degree;
    int periodic;
    std::vector<double> knots;
    std::map<std::string, std::vector<int> > component_tags;
    NdCurve() : present(false), degree(3), periodic(0) {}
};

static NdCurve nd_read_curve(const MObject& _o) {
    NdCurve g;
    if (_o.isNull() || !_o.hasFn(MFn::kNurbsCurve)) return g;
    MFnNurbsCurve _fn(_o);
    g.present = true;
    MPointArray _pa; _fn.getCVs(_pa, MSpace::kObject);
    for (unsigned int i = 0; i < _pa.length(); ++i) g.cvs.push_back(_pa[i]);
    g.degree = _fn.degree();
    g.periodic = (_fn.form() == MFnNurbsCurve::kPeriodic) ? 1 : 0;
    MDoubleArray _gk; _fn.getKnots(_gk);
    for (unsigned int i = 0; i < _gk.length(); ++i) g.knots.push_back(_gk[i]);
    return g;
}

static MObject nd_build_curve(const NdCurve& g) {
    MStatus _st;
    MFnNurbsCurveData _dc;
    MObject _data = _dc.create(&_st);
    MPointArray _cv; for (size_t i = 0; i < g.cvs.size(); ++i) _cv.append(g.cvs[i]);
    if ((int)_cv.length() >= g.degree + 1) {
        MDoubleArray _knots;
        if (!g.knots.empty() && (int)g.knots.size() == (int)_cv.length() + g.degree - 1) {
            for (size_t i = 0; i < g.knots.size(); ++i) _knots.append(g.knots[i]);
        } else if (g.periodic) {
            nd_buildPeriodicKnots((int)_cv.length(), g.degree, _knots);
        } else {
            nd_buildOpenKnots((int)_cv.length(), g.degree, _knots);
        }
        MFnNurbsCurve::Form _form = g.periodic ? MFnNurbsCurve::kPeriodic : MFnNurbsCurve::kOpen;
        MFnNurbsCurve _cf;
        _cf.create(_cv, _knots, (unsigned)g.degree, _form, false, false, _data, &_st);
    }
    return _data;
}
"""

_SURFACE_CPP = r"""
struct NdSurface {
    bool present;
    std::vector<MPoint> cvs;
    int numU, numV;
    int degreeU, degreeV;
    int periodicU, periodicV;
    std::vector<double> knotsU, knotsV;
    std::map<std::string, std::vector<int> > component_tags;
    NdSurface() : present(false), numU(0), numV(0), degreeU(3), degreeV(3),
                  periodicU(0), periodicV(0) {}
};

static NdSurface nd_read_surface(const MObject& _o) {
    NdSurface g;
    if (_o.isNull() || !_o.hasFn(MFn::kNurbsSurface)) return g;
    MFnNurbsSurface _fn(_o);
    g.present = true;
    MPointArray _pa; _fn.getCVs(_pa, MSpace::kObject);
    for (unsigned int i = 0; i < _pa.length(); ++i) g.cvs.push_back(_pa[i]);
    g.numU = (int)_fn.numCVsInU();
    g.numV = (int)_fn.numCVsInV();
    g.degreeU = (int)_fn.degreeU();
    g.degreeV = (int)_fn.degreeV();
    g.periodicU = (_fn.formInU() == MFnNurbsSurface::kPeriodic) ? 1 : 0;
    g.periodicV = (_fn.formInV() == MFnNurbsSurface::kPeriodic) ? 1 : 0;
    MDoubleArray _ku; _fn.getKnotsInU(_ku);
    for (unsigned int i = 0; i < _ku.length(); ++i) g.knotsU.push_back(_ku[i]);
    MDoubleArray _kv; _fn.getKnotsInV(_kv);
    for (unsigned int i = 0; i < _kv.length(); ++i) g.knotsV.push_back(_kv[i]);
    return g;
}

static MObject nd_build_surface(const NdSurface& g) {
    MStatus _st;
    MFnNurbsSurfaceData _dc;
    MObject _data = _dc.create(&_st);
    MPointArray _cv; for (size_t i = 0; i < g.cvs.size(); ++i) _cv.append(g.cvs[i]);
    if (g.numU >= g.degreeU + 1 && g.numV >= g.degreeV + 1 &&
        (int)_cv.length() == g.numU * g.numV) {
        MDoubleArray _ku;
        if (!g.knotsU.empty() && (int)g.knotsU.size() == g.numU + g.degreeU - 1) {
            for (size_t i = 0; i < g.knotsU.size(); ++i) _ku.append(g.knotsU[i]);
        } else if (g.periodicU) { nd_buildPeriodicKnots(g.numU, g.degreeU, _ku); }
        else { nd_buildOpenKnots(g.numU, g.degreeU, _ku); }
        MDoubleArray _kv;
        if (!g.knotsV.empty() && (int)g.knotsV.size() == g.numV + g.degreeV - 1) {
            for (size_t i = 0; i < g.knotsV.size(); ++i) _kv.append(g.knotsV[i]);
        } else if (g.periodicV) { nd_buildPeriodicKnots(g.numV, g.degreeV, _kv); }
        else { nd_buildOpenKnots(g.numV, g.degreeV, _kv); }
        MFnNurbsSurface::Form _fu = g.periodicU ? MFnNurbsSurface::kPeriodic : MFnNurbsSurface::kOpen;
        MFnNurbsSurface::Form _fv = g.periodicV ? MFnNurbsSurface::kPeriodic : MFnNurbsSurface::kOpen;
        MFnNurbsSurface _sf;
        _sf.create(_cv, _ku, _kv, (unsigned)g.degreeU, (unsigned)g.degreeV,
                   _fu, _fv, false, _data, &_st);
    }
    return _data;
}
"""

_KIND_CPP = {"mesh": _MESH_CPP, "curve": _CURVE_CPP, "surface": _SURFACE_CPP}


def geo_io_cpp(kinds):
    """Emit the struct+read+build C++ block for ``kinds`` (a set), wrapped in an
    idempotent include guard. Empty string if ``kinds`` is empty."""
    if not kinds:
        return ""
    parts = ["#ifndef MPYNODE_GEO_IO_H", "#define MPYNODE_GEO_IO_H"]
    if "curve" in kinds or "surface" in kinds:
        parts.append(_KNOTS_CPP)
    for k in ("mesh", "curve", "surface"):
        if k in kinds:
            parts.append(_KIND_CPP[k])
    parts.append("#endif  // MPYNODE_GEO_IO_H")
    return "\n".join(parts)


# ---- per-attr code emitters (used by emit_compute) -------------------------

# MDataHandle accessor that yields the geo DATA MObject, per kind.
_AS = {"mesh": "asMesh", "curve": "asNurbsCurve", "surface": "asNurbsSurface"}


def is_geo(t):
    """True for a geometry attr type (mesh/nurbsCurve/nurbsSurface)."""
    return t in _KIND


def geo_kind_of(t):
    return _KIND.get(t)


def geo_out_decls(o):
    """Declare the output geo value buffer: ``Nd<Kind> out_<m>;`` (single) or
    ``std::vector<Nd<Kind>> out_<m>;`` (array). Default-constructed = empty
    geometry (the neutral stub), so a node that never fills it ships empty geo."""
    kind = _KIND[o["meta"]["type"]]
    st   = _STRUCT[kind]
    v    = "out_" + o["member"]
    if o["meta"].get("is_array"):
        return ["    std::vector<%s> %s;" % (st, v)]
    return ["    %s %s;" % (st, v)]


def geo_array_input_lines(m, src="data"):
    """Read a multi (list) geo INPUT into ``std::vector<Nd<Kind>> in_<m>``.

    Dense: scatter each present element to its logical index; gap slots stay
    default-constructed (``present == false``), matching the interpreted list
    where a missing multi element is an empty geometry."""
    mem  = m["member"]
    kind = _KIND[m["meta"]["type"]]
    v    = "in_" + mem
    st   = _STRUCT[kind]
    rd   = "nd_read_" + kind
    as_  = _AS[kind]
    return [
        "    std::vector<%s> %s;" % (st, v),
        "    {",
        "        MArrayDataHandle _garr = %s.inputArrayValue(%s);" % (src, mem),
        "        unsigned _gn = _garr.elementCount();",
        "        for (unsigned _gi = 0; _gi < _gn; ++_gi) {",
        "            unsigned _gli = _garr.elementIndex();",
        "            if (_gli >= %s.size()) %s.resize(_gli + 1);" % (v, v),
        "            %s[_gli] = %s(_garr.inputValue().%s());" % (v, rd, as_),
        "            _garr.next();",
        "        }",
        "    }",
    ]


_FN = {"mesh": "MFnMesh", "curve": "MFnNurbsCurve", "surface": "MFnNurbsSurface"}
# MFn type constant guarding the plug's MObject before wrapping/reading it.
_FN_CONST = {"mesh": "MFn::kMesh", "curve": "MFn::kNurbsCurve",
             "surface": "MFn::kNurbsSurface"}


def geo_plug_decls(m):
    """Declare a geo INPUT buffer for the findPlug path (transform/locator/
    iksolver read in a hook with no datablock).

    Both SINGLE and ARRAY use the plain-data ``Nd<Kind>`` struct rather than the
    plain path's ``MFn<Kind>`` wrapper: these families marshal inputs through a
    copyable POD (the locator's DrawInputs), which an MFn function set cannot
    live in, and Nd<Kind> is already the geo-array element type."""
    kind = _KIND[m["meta"]["type"]]
    v    = "in_" + m["member"]
    if m["meta"].get("is_array"):
        return ["    std::vector<%s> %s;" % (_STRUCT[kind], v)]
    return ["    %s %s;" % (_STRUCT[kind], v)]


def geo_plug_input_lines(m, plug_expr):
    """Read a SINGLE geo input off an MPlug. Indent-2 (inside the plug guard).

    Left default-constructed (``present == false``) when the plug carries no
    geometry, matching the interpreted empty-geometry case."""
    kind = _KIND[m["meta"]["type"]]
    v    = "in_" + m["member"]
    return [
        "        {",
        "            MObject _go = %s.asMObject();" % plug_expr,
        "            if (!_go.isNull() && _go.hasFn(%s)) %s = nd_read_%s(_go);"
        % (_FN_CONST[kind], v, kind),
        "        }",
    ]


def geo_plug_array_input_lines(m, plug_expr):
    """Dense read of a geo ARRAY off an MPlug into ``std::vector<Nd<Kind>>``.

    findPlug sibling of geo_array_input_lines, same dense semantics: scatter each
    present element to its logical index; gap slots stay default-constructed
    (``present == false``) -- an empty geometry, as in the interpreted list."""
    kind = _KIND[m["meta"]["type"]]
    v    = "in_" + m["member"]
    rd   = "nd_read_" + kind
    return [
        "        {",
        "            unsigned _gn = %s.numElements();" % plug_expr,
        "            for (unsigned _gi = 0; _gi < _gn; ++_gi) {",
        "                MPlug _ge = %s.elementByPhysicalIndex(_gi);" % plug_expr,
        "                unsigned _gl = _ge.logicalIndex();",
        "                if (_gl >= %s.size()) %s.resize(_gl + 1);" % (v, v),
        "                MObject _go = _ge.asMObject();",
        "                if (!_go.isNull() && _go.hasFn(%s)) %s[_gl] = %s(_go);"
        % (_FN_CONST[kind], v, rd),
        "            }",
        "        }",
    ]


def geo_output_lines(o):
    """Build+set a geo OUTPUT from its ``out_<m>`` buffer. Single: build one geo
    data MObject and set the handle. Array: an ``MArrayDataBuilder`` loop building
    one element per list entry (mirrors emit_attr._array_write_lines)."""
    mem  = o["member"]
    kind = _KIND[o["meta"]["type"]]
    v    = "out_" + mem
    bd   = "nd_build_" + kind
    if not o["meta"].get("is_array"):
        return [
            "    {",
            "        MDataHandle _goh = data.outputValue(%s);" % mem,
            "        _goh.setMObject(%s(%s));" % (bd, v),
            "        _goh.setClean();",
            "    }",
        ]
    return [
        "    {",
        "        MArrayDataHandle _goArr = data.outputArrayValue(%s);" % mem,
        "        MArrayDataBuilder _gb = _goArr.builder();",
        "        for (size_t _gi = 0; _gi < %s.size(); ++_gi) {" % v,
        "            MDataHandle _geh = _gb.addElement((unsigned)_gi);",
        "            _geh.setMObject(%s(%s[_gi]));" % (bd, v),
        "        }",
        "        _goArr.set(_gb);",
        "        _goArr.setAllClean();",
        "    }",
    ]
