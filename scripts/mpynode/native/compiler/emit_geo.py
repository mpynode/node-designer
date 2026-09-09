"""Geometry-generator (mesh/curve/surface) compute() emission."""
from __future__ import annotations

from .spec_model import (PORT_BEGIN, PORT_END, _GEO_INFO, _spec_has_hex,
                         LOWERED_GUARD_INCLUDE, MESH_INTERSECTOR_INCLUDE,
                         lowered_guard)
from .emit_attr import (_array_read_lines, _create_lines, _image_read_hint_lines,
                        _image_read_lines, _members, _pick_path_input,
                        _read_line, PACKED_INCLUDES)
from .emit_hex import _HEX_CPP
from .nd_runtime import _nd_runtime_cpp
from mpynode.native.compiler.kernels import nd_io_cpp, file_texture_cpp
from . import emit_geo_io


_GEO_INCLUDES_BASE = [
    "cmath", "vector", "random", "cstdint",
    "maya/MPxNode.h", "maya/MFnPlugin.h", "maya/MTypeId.h",
    "maya/MFnNumericAttribute.h", "maya/MFnUnitAttribute.h",
    "maya/MFnEnumAttribute.h", "maya/MFnMatrixAttribute.h",
    "maya/MFnTypedAttribute.h", "maya/MFnCompoundAttribute.h",
    "maya/MFnNumericData.h", "maya/MFnData.h",
    "maya/MDataBlock.h", "maya/MDataHandle.h", "maya/MPlug.h", "maya/MStatus.h",
    "maya/MPoint.h", "maya/MPointArray.h", "maya/MVector.h", "maya/MMatrix.h",
    "maya/MIntArray.h", "maya/MDoubleArray.h",
    "maya/MAngle.h", "maya/MTime.h", "maya/MString.h",
]

_GEO_INCLUDES_KIND = {
    "mesh": ["maya/MFnMesh.h", "maya/MFnMeshData.h",
             "maya/MColor.h", "maya/MColorArray.h", "maya/MVectorArray.h"],
    "curve": ["maya/MFnNurbsCurve.h", "maya/MFnNurbsCurveData.h"],
    "surface": ["maya/MFnNurbsSurface.h", "maya/MFnNurbsSurfaceData.h"],
}

def _geo_build_lines(kind, info):
    """C++ that turns the filled buffers into the geo data MObject `newData`.

    Mesh: after MFnMesh::create, optional normals (per-vertex via
    setVertexNormals, or per-face-vertex indexed via setFaceVertexNormals) and
    optional colors (setVertexColors / setFaceVertexColors -> auto colorSet1) --
    mirroring geometry._apply_mesh_normals / _apply_mesh_colors bit-for-bit.
    Curve/surface: select open vs periodic form from the `periodic*` flag, use
    the supplied `knots*` buffer when non-empty else the matching uniform builder.
    """
    fn, datafn = info["fn"], info["datafn"]
    L = []
    L.append("    MStatus gstat;")
    L.append("    %s dataCreator;" % datafn)
    L.append("    MObject newData = dataCreator.create(&gstat);")
    if kind == "mesh":
        L += [
            "    // Bulk constructors, not one append() per element (meshMaze: a",
            "    // 155k-vertex soup was ~740k append calls, and marshalling-bound).",
            "    MPointArray _pa;",
            "    if (!points.empty()) _pa = MPointArray(points.data(), (unsigned)points.size());",
            "    MIntArray _pc;",
            "    if (!counts.empty()) _pc = MIntArray(counts.data(), (unsigned)counts.size());",
            "    MIntArray _ic;",
            "    if (!indices.empty()) _ic = MIntArray(indices.data(), (unsigned)indices.size());",
            "    // Topology guards mirror geometry.build_mesh_data: a violated",
            "    // invariant ships an EMPTY mesh (never an out-of-bounds crash).",
            "    long _sumc = 0; bool _topoOK = !points.empty() && !counts.empty();",
            "    for (size_t i = 0; i < counts.size(); ++i) {",
            "        if (counts[i] < 3) _topoOK = false;",
            "        _sumc += counts[i];",
            "    }",
            "    if ((long)indices.size() != _sumc) _topoOK = false;",
            "    if (_topoOK)",
            "        for (size_t i = 0; i < indices.size(); ++i)",
            "            if (indices[i] < 0 || indices[i] >= (int)points.size()) {",
            "                _topoOK = false; break;",
            "            }",
            "    if (_topoOK) {",
            "        %s geoFn;" % fn,
            "        geoFn.create((int)points.size(), (int)counts.size(),",
            "                     _pa, _pc, _ic, newData, &gstat);",
            "        // --- optional per-vertex / per-face-vertex normals ---",
            "        // (mirror _apply_mesh_normals: skip the channel on any size/",
            "        //  range mismatch rather than indexing out of bounds).",
            "        if (!normals.empty()) {",
            "            if (normalIndices.empty()) {",
            "                if (normals.size() == points.size()) {",
            "                    std::vector<int> _vidv(normals.size());",
            "                    for (size_t i = 0; i < _vidv.size(); ++i) _vidv[i] = (int)i;",
            "                    MVectorArray _nrm(normals.data(), (unsigned)normals.size());",
            "                    MIntArray _vids(_vidv.data(), (unsigned)_vidv.size());",
            "                    geoFn.setVertexNormals(_nrm, _vids);",
            "                }",
            "            } else if ((long)normalIndices.size() == _sumc) {",
            "                bool _ok = true;",
            "                for (size_t i = 0; i < normalIndices.size(); ++i)",
            "                    if (normalIndices[i] < 0 ||",
            "                        normalIndices[i] >= (int)normals.size()) {",
            "                        _ok = false; break;",
            "                    }",
            "                if (_ok) {",
            "                    std::vector<MVector> _nrv; std::vector<int> _fidv, _vidv; int _off = 0;",
            "                    _nrv.reserve((size_t)_sumc); _fidv.reserve((size_t)_sumc); _vidv.reserve((size_t)_sumc);",
            "                    for (size_t _f = 0; _f < counts.size(); ++_f) {",
            "                        for (int _j = 0; _j < counts[_f]; ++_j) {",
            "                            int _fv = _off + _j;",
            "                            _nrv.push_back(normals[(size_t)normalIndices[(size_t)_fv]]);",
            "                            _fidv.push_back((int)_f);",
            "                            _vidv.push_back(indices[(size_t)_fv]);",
            "                        }",
            "                        _off += counts[_f];",
            "                    }",
            "                    MVectorArray _nrm(_nrv.data(), (unsigned)_nrv.size());",
            "                    MIntArray _fids(_fidv.data(), (unsigned)_fidv.size());",
            "                    MIntArray _vids(_vidv.data(), (unsigned)_vidv.size());",
            "                    geoFn.setFaceVertexNormals(_nrm, _fids, _vids);",
            "                }",
            "            }",
            "        }",
            "        // --- optional per-vertex / per-face-vertex colors ---",
            "        if (!colors.empty()) {",
            "            if (colorIndices.empty()) {",
            "                if (colors.size() == points.size()) {",
            "                    std::vector<int> _vidv(colors.size());",
            "                    for (size_t i = 0; i < _vidv.size(); ++i) _vidv[i] = (int)i;",
            "                    MColorArray _col(colors.data(), (unsigned)colors.size());",
            "                    MIntArray _vids(_vidv.data(), (unsigned)_vidv.size());",
            "                    geoFn.setVertexColors(_col, _vids);",
            "                }",
            "            } else if ((long)colorIndices.size() == _sumc) {",
            "                bool _ok = true;",
            "                for (size_t i = 0; i < colorIndices.size(); ++i)",
            "                    if (colorIndices[i] < 0 ||",
            "                        colorIndices[i] >= (int)colors.size()) {",
            "                        _ok = false; break;",
            "                    }",
            "                if (_ok) {",
            "                    std::vector<MColor> _colv; std::vector<int> _fidv, _vidv; int _off = 0;",
            "                    _colv.reserve((size_t)_sumc); _fidv.reserve((size_t)_sumc); _vidv.reserve((size_t)_sumc);",
            "                    for (size_t _f = 0; _f < counts.size(); ++_f) {",
            "                        for (int _j = 0; _j < counts[_f]; ++_j) {",
            "                            int _fv = _off + _j;",
            "                            _colv.push_back(colors[(size_t)colorIndices[(size_t)_fv]]);",
            "                            _fidv.push_back((int)_f);",
            "                            _vidv.push_back(indices[(size_t)_fv]);",
            "                        }",
            "                        _off += counts[_f];",
            "                    }",
            "                    MColorArray _col(_colv.data(), (unsigned)_colv.size());",
            "                    MIntArray _fids(_fidv.data(), (unsigned)_fidv.size());",
            "                    MIntArray _vids(_vidv.data(), (unsigned)_vidv.size());",
            "                    geoFn.setFaceVertexColors(_col, _fids, _vids);",
            "                }",
            "            }",
            "        }",
            "    }",
        ]
    elif kind == "curve":
        L += [
            "    MPointArray _cv;",
            "    if (!cvs.empty()) _cv = MPointArray(cvs.data(), (unsigned)cvs.size());",
            "    if ((int)_cv.length() >= degree + 1) {",
            "        MDoubleArray _knots;",
            "        // Use a supplied knot vector ONLY at the length Maya expects",
            "        // (numCVs + degree - 1); otherwise rebuild uniform -- mirrors",
            "        // geometry.build_curve_data (a wrong-length kv is rebuilt).",
            "        if (!knots.empty() &&",
            "            (int)knots.size() == (int)_cv.length() + degree - 1) {",
            "            _knots = MDoubleArray(knots.data(), (unsigned)knots.size());",
            "        } else if (periodic) {",
            "            _buildPeriodicKnots((int)_cv.length(), degree, _knots);",
            "        } else {",
            "            _buildOpenKnots((int)_cv.length(), degree, _knots);",
            "        }",
            "        MFnNurbsCurve::Form _form = periodic ? MFnNurbsCurve::kPeriodic",
            "                                             : MFnNurbsCurve::kOpen;",
            "        %s geoFn;" % fn,
            "        geoFn.create(_cv, _knots, (unsigned)degree,",
            "                     _form, false, false, newData, &gstat);",
            "    }",
        ]
    else:  # surface
        L += [
            "    MPointArray _cv;",
            "    if (!cvs.empty()) _cv = MPointArray(cvs.data(), (unsigned)cvs.size());",
            "    if (numU >= degreeU + 1 && numV >= degreeV + 1 &&",
            "        (int)_cv.length() == numU * numV) {",
            "        // Supplied knot vectors are honored ONLY at the expected",
            "        // length (numCVs + degree - 1 per direction); otherwise",
            "        // rebuilt uniform -- mirrors geometry._surface_knots.",
            "        MDoubleArray _ku;",
            "        if (!knotsU.empty() && (int)knotsU.size() == numU + degreeU - 1) {",
            "            _ku = MDoubleArray(knotsU.data(), (unsigned)knotsU.size());",
            "        } else if (periodicU) {",
            "            _buildPeriodicKnots(numU, degreeU, _ku);",
            "        } else { _buildOpenKnots(numU, degreeU, _ku); }",
            "        MDoubleArray _kv;",
            "        if (!knotsV.empty() && (int)knotsV.size() == numV + degreeV - 1) {",
            "            _kv = MDoubleArray(knotsV.data(), (unsigned)knotsV.size());",
            "        } else if (periodicV) {",
            "            _buildPeriodicKnots(numV, degreeV, _kv);",
            "        } else { _buildOpenKnots(numV, degreeV, _kv); }",
            "        MFnNurbsSurface::Form _fu = periodicU ? MFnNurbsSurface::kPeriodic",
            "                                              : MFnNurbsSurface::kOpen;",
            "        MFnNurbsSurface::Form _fv = periodicV ? MFnNurbsSurface::kPeriodic",
            "                                              : MFnNurbsSurface::kOpen;",
            "        %s geoFn;" % fn,
            "        geoFn.create(_cv, _ku, _kv, (unsigned)degreeU, (unsigned)degreeV,",
            "                     _fu, _fv, false, newData, &gstat);",
            "    }",
        ]
    return L

def _generate_geo_cpp(spec: dict, kind: str, for_port: bool = False) -> str:
    """Emit a native MPxNode geometry GENERATOR (mesh/curve/surface). The typed
    geo data output attr, attribute wiring, registration, and the
    buffers->MFn*::create marshalling (incl. default uniform/clamped knots, to
    match the framework's build_default_output) are fixed; only the geometry
    MATH that fills the buffers (between the PORT markers) is AI-ported.
    """
    sg = spec["suggested"]
    cls = sg["class_name"]
    type_name = sg["node_type_name"]
    type_id = sg["type_id"]
    info = _GEO_INFO[kind]
    out_attr = info["attr"]
    out_member = "a" + out_attr[:1].upper() + out_attr[1:]

    # User inputs only (the geo output is synthesized here, not from the spec).
    in_members = [m for m in _members(spec) if m["kind"] == "inputs"]

    # Deterministic numpy->C++ lowering of the geometry math. If the WHOLE
    # compute lowers (supported input types + constructs, and the required
    # buffers -- points/counts/indices | cvs/degree | cvs/numU/numV -- all
    # filled), the PORT region becomes the transpiled buffer-fill, nd_runtime.h
    # is inlined, and _geo_build_lines below reproduces build_default_output
    # natively. Otherwise None -> the AI-porter PORT region is kept unchanged.
    # Lazy import breaks the codegen<->nd_lower cycle.
    from mpynode.native.compiler import nd_lower
    geo_lowered = nd_lower.try_lower_geo_compute(in_members, kind, spec)
    nd_io_cpp.reject_unlowered_io(spec, geo_lowered, "geometry node")

    # ---- companion commands (Methods tab @maya_command defs) ----------------
    # Every @maya_command becomes a real MPxCommand registered by THIS bundle,
    # so a compile emits ONE plug-in. Empty for a command-less node (build stays
    # byte-identical). Lazy import mirrors emit_locator's command splice.
    from mpynode.native.compiler.kernels import command_dispatch
    cmd_out = command_dispatch.dispatch_for_spec(spec, type_name)
    if cmd_out["errors"]:
        from mpynode.native.compiler.errors import UnsupportedSpec
        raise UnsupportedSpec(
            "%s: @maya_command could not be lowered to an MPxCommand:\n  %s"
            % (type_name, "\n  ".join(cmd_out["errors"])))

    includes = list(_GEO_INCLUDES_BASE) + _GEO_INCLUDES_KIND[kind]
    # A SINGLE geo INPUT is read by emit_attr._read_line as `MFn<Kind> in_<m>`,
    # and emit_geo_io.kinds_in_spec deliberately skips it (it needs no Nd<Kind>
    # struct), so its MFn* header is requested here. Keying only on the
    # generator's OUTPUT kind left a curve/surface generator with a mesh input
    # emitting MFnMesh with no maya/MFnMesh.h -- it could not compile. Same-kind
    # inputs are already covered above, so no working frag changes.
    for m in in_members:
        t = m["meta"]["type"]
        if emit_geo_io.is_geo(t) and not m["meta"].get("is_array"):
            for h in _GEO_INCLUDES_KIND[emit_geo_io.geo_kind_of(t)]:
                if h not in includes:
                    includes.append(h)
    # packed (typed-array) input: _array_read_lines reads it whole through
    # MFn*ArrayData. Gated so a generator with no packed attr stays byte-identical.
    if any(m["meta"].get("packed") for m in in_members):
        for h in PACKED_INCLUDES:
            if h not in includes:
                includes.append(h)
    # MGlobal::displayError, used only by the lowered body's boundary handler --
    # gated so an AI-ported geo node's frag stays byte-identical.
    if geo_lowered is not None and LOWERED_GUARD_INCLUDE not in includes:
        includes.append(LOWERED_GUARD_INCLUDE)
    # Closest-point mesh query (MMeshIntersector / MFnMesh::getClosestPoint). The
    # generator already binds the mesh INPUT as `MFnMesh in_<member>` + its raw
    # MObject just above the PORT marker -- exactly what MMeshIntersector::create
    # takes -- but the porter may not add #includes, so without this header the
    # port cannot compile. Gated on the spec flag to keep other frags identical.
    if sg.get("uses_mesh_intersector") \
            and MESH_INTERSECTOR_INCLUDE not in includes:
        includes.append(MESH_INTERSECTOR_INCLUDE)
    # Sanctioned image-FILE read (reads_image_file): the generator loads its path
    # input via the cached nd_img_load_raw and hands the ported body an RGBA8
    # buffer, exactly like the generic MPxNode path (node_scaffold). Without this
    # the porter is told "the image is loaded above into _imgPixels" by the
    # translation guide while no such buffer exists -- so it drops the feature.
    # Gated on the spec flag to keep every other geo frag byte-identical.
    raw_img_cache = bool(sg.get("reads_image_file"))
    # _image_read_lines resolves its path input through _pick_path_input, which
    # prefers ANY string ARRAY over a scalar `fileName` (the multi-file composite
    # source) and then emits nd_img_composite against the COMPOSITE cache -- but
    # this arm only emits the single-file NdImgRawCache, so the TU would carry
    # undeclared identifiers and fail to compile. A multi-string input on a
    # geometry node is ordinary (procrustes_tags has one), so reject honestly
    # rather than emit a .cpp that cannot build.
    if raw_img_cache:
        _path_in = _pick_path_input(in_members)
        if _path_in is not None and _path_in["meta"].get("is_array"):
            from mpynode.native.compiler.errors import UnsupportedSpec
            raise UnsupportedSpec(
                "geometry node reads an image FILE but its path input %r is a "
                "string ARRAY (the multi-file composite form), which the "
                "geometry emitter has no cache for" % _path_in["plug"])
        # No path input at all (hardcoded path in Init, or a stored var): the
        # node has no path PLUG, so _image_read_lines has nothing to load and
        # returns []. Declaring the cache anyway -- and telling the porter the
        # pixels are "loaded above" -- would promise a buffer that is never
        # emitted. Suppress both; the porter then translates the read itself or
        # emits ND_PORT_INCOMPLETE, which is the honest outcome.
        raw_img_cache = _path_in is not None
    if raw_img_cache:
        for h in ("maya/MImage.h",) + tuple(file_texture_cpp.RAW_CACHE_INCLUDES):
            if h not in includes:
                includes.append(h)
    # hex attr transcode core uses std::string.
    has_hex = _spec_has_hex(spec)
    if has_hex and "string" not in includes:
        includes.append("string")
    # geo VALUE model (Nd<Kind> struct + nd_read_<kind>) needed when a geo ARRAY
    # input is read as std::vector<Nd<Kind>>. The generator assembles its own TU
    # (no node_scaffold geo_io injection), so add the struct + includes here.
    geo_io_kinds = emit_geo_io.kinds_in_spec(spec)
    if geo_io_kinds:
        for h in emit_geo_io.geo_io_includes(geo_io_kinds):
            if h not in includes:
                includes.append(h)
    # nd_io (ndio.read/write, np.fromfile/np.save, .tofile). Gated on the source
    # so a non-IO geo node's frag stays byte-identical (port cache intact).
    if nd_io_cpp.spec_uses_ndio(spec):
        for h in nd_io_cpp.NDIO_INCLUDES:
            if h not in includes:
                includes.append(h)
    for h in cmd_out["includes"]:
        if h not in includes:
            includes.append(h)

    L = []
    L.append("// %s -- generated MPxNode %s GENERATOR (codegen)." % (type_name, kind))
    L.append("// Source mPyNode: %s (%s)"
             % (spec.get("source_node"), spec.get("mpy_type")))
    L.append("// Typed geo output + %s::create marshalling are final; the geometry"
             % info["fn"])
    L.append("// math (between the PORT markers) is filled by the AI porter.")
    L.append("")
    for inc in includes:
        L.append("#include <%s>" % inc)
    L.append("")
    # Nd<Kind> struct + nd_read_<kind> (idempotent include guard) -- only when a
    # geo ARRAY input is present.
    if geo_io_kinds:
        L.append(emit_geo_io.geo_io_cpp(geo_io_kinds))
        L.append("")
    if kind in ("curve", "surface"):
        # Default uniform clamped-open knots -- matches geometry._curve_uniform_
        # knots (open: n = numCVs + degree - 1, clamped multiplicity `degree`).
        L.append("static void _buildOpenKnots(int numCVs, int degree, MDoubleArray& out) {")
        L.append("    int n = numCVs + degree - 1;")
        L.append("    if (n <= 0) return;")
        L.append("    int inner = n - 2 * degree; if (inner < 0) inner = 0;")
        L.append("    for (int i = 0; i < degree; ++i) out.append(0.0);")
        L.append("    for (int i = 0; i < inner; ++i) out.append((double)(i + 1));")
        L.append("    double last = (double)(inner + 1);")
        L.append("    for (int i = 0; i < degree; ++i) out.append(last);")
        L.append("    while ((int)out.length() > n) out.remove(out.length() - 1);")
        L.append("}")
        # Uniform periodic (continuous) knots -- matches geometry._curve_uniform_
        # knots periodic branch: n = numCVs + degree - 1, knot[i] = i - degree + 1.
        L.append("static void _buildPeriodicKnots(int numCVs, int degree, MDoubleArray& out) {")
        L.append("    int n = numCVs + degree - 1;")
        L.append("    if (n <= 0) return;")
        L.append("    for (int i = 0; i < n; ++i) out.append((double)(i - degree + 1));")
        L.append("}")
        L.append("")
    # hex attr transcode helpers (decode is used for hex geo inputs).
    if has_hex:
        L.append(_HEX_CPP)
    # nd:: header-only runtime, inlined verbatim above the class when the
    # geometry math was deterministically lowered (its own include guard makes
    # this idempotent). No lowering -> not inlined (byte-identical AI-port path).
    if geo_lowered is not None:
        L.append(_nd_runtime_cpp())
        L.append("")
        # nd_io sits ON TOP of nd:: (every accessor returns nd::Array<T>), so it
        # must follow the runtime. Own include guard -> idempotent in a bundle.
        if nd_io_cpp.spec_uses_ndio(spec):
            L.append(nd_io_cpp.NDIO_CPP)
            L.append("")
    # Raw-image decode cache, emitted just above the class so compute() can call
    # nd_img_load_raw(). A per-compute() MImage::readFromFile is the difference
    # between a live node and a stall, so the decode is cached per instance.
    if raw_img_cache:
        L.append(file_texture_cpp.RAW_CACHE_CPP)
        L.append("")
    L.append("class %s : public MPxNode {" % cls)
    L.append("public:")
    L.append("    %s() {}" % cls)
    L.append("    ~%s() override {}" % cls)
    L.append("    static void*   creator() { return new %s(); }" % cls)
    L.append("    static MStatus initialize();")
    L.append("    MStatus        compute(const MPlug& plug, MDataBlock& data) override;")
    L.append("    static MTypeId id;")
    for m in in_members:
        L.append("    static MObject %s;" % m["member"])
    L.append("    static MObject %s;" % out_member)
    # Per-instance file-IO document cache + lock.
    if nd_io_cpp.spec_uses_ndio(spec):
        L.append(nd_io_cpp.NDIO_MEMBERS.rstrip("\n"))
    # Per-instance raw-image cache + lock.
    if raw_img_cache:
        L.append(file_texture_cpp.RAW_CACHE_MEMBERS.rstrip("\n"))
    L.append("};")
    L.append("")
    L.append("MTypeId %s::id(%s);" % (cls, type_id))
    for m in in_members:
        L.append("MObject %s::%s;" % (cls, m["member"]))
    L.append("MObject %s::%s;" % (cls, out_member))
    L.append("")
    # initialize()
    L.append("MStatus %s::initialize() {" % cls)
    L.append("    MFnNumericAttribute nAttr;")
    L.append("    MFnUnitAttribute    uAttr;")
    L.append("    MFnEnumAttribute    eAttr;")
    L.append("    MFnMatrixAttribute  mAttr;")
    L.append("    MFnTypedAttribute   tAttr;")
    L.append("    MFnCompoundAttribute cAttr;")
    L.append("")
    for m in in_members:
        L += _create_lines(m)
    L.append('    %s = tAttr.create("%s", "%s", MFnData::%s);'
             % (out_member, out_attr, info["short"], info["data"]))
    L.append("    tAttr.setWritable(false);")
    L.append("    tAttr.setStorable(false);")
    L.append("")
    for m in in_members:
        L.append("    addAttribute(%s);" % m["member"])
    L.append("    addAttribute(%s);" % out_member)
    L.append("")
    for m in in_members:
        L.append("    attributeAffects(%s, %s);" % (m["member"], out_member))
    L.append("    return MS::kSuccess;")
    L.append("}")
    L.append("")
    if cmd_out["classes"]:
        # Placed AFTER <cls>::id is defined and initialize() closes (the command
        # classes reference the node class); the bundler wraps this scaffold-head
        # region in `namespace nd_<node>`, which is what keeps two nodes' command
        # support from colliding in a merged plug-in.
        L.append("// ==== bundled commands (Methods @maya_command) ====")
        L.append(cmd_out["classes"])
        L.append("")
    # compute()
    L.append("MStatus %s::compute(const MPlug& plug, MDataBlock& data) {" % cls)
    L.append("    if (plug != %s) return MS::kUnknownParameter;" % out_member)
    L.append("")
    L.append("    // --- inputs ---")
    for m in in_members:
        if emit_geo_io.is_geo(m["meta"]["type"]) and m["meta"].get("is_array"):
            # multi (list) geo input -> std::vector<Nd<Kind>> in_<member> (mirrors
            # the generic MPxNode path); nd_lower reads elements via the struct.
            L += emit_geo_io.geo_array_input_lines(m)
        elif m["meta"].get("is_array"):
            # array inputs read into std::vector<T> in_<member> (mirrors the
            # generic MPxNode path); _read_line has no array branch, so a geo
            # node with an array input would otherwise emit no read at all.
            L += _array_read_lines(m)
        else:
            rl = _read_line(m)
            if rl:
                L.append(rl)
    if raw_img_cache:
        L += _image_read_lines(in_members)
    L.append("")
    L.append("    // --- geometry buffers (fill below) ---")
    if kind == "mesh":
        L.append("    std::vector<MPoint> points;  // vertex positions")
        L.append("    std::vector<int>    counts;  // per-face vertex counts")
        L.append("    std::vector<int>    indices; // flat face-vertex indices")
        L.append("    std::vector<MVector> normals;       // optional; empty = smooth")
        L.append("    std::vector<int>     normalIndices; // optional face-vertex map")
        L.append("    std::vector<MColor>  colors;        // optional; empty = no set")
        L.append("    std::vector<int>     colorIndices;  // optional face-vertex map")
    elif kind == "curve":
        L.append("    std::vector<MPoint> cvs;     // control vertices")
        L.append("    int degree = 3;             // 1,2,3,5,7 (default 3)")
        L.append("    int periodic = 0;           // 0 = open, 1 = periodic")
        L.append("    std::vector<double> knots;  // optional; empty = uniform")
    else:
        L.append("    std::vector<MPoint> cvs;     // control vertices, U-major")
        L.append("    int numU = 0, numV = 0;     // CV grid dims")
        L.append("    int degreeU = 3, degreeV = 3;")
        L.append("    int periodicU = 0, periodicV = 0;  // 0 = open, 1 = periodic")
        L.append("    std::vector<double> knotsU, knotsV; // optional; empty = uniform")
    L.append("")
    if geo_lowered is not None:
        # Deterministic buffer-fill (no PORT region). Inputs are already read
        # into in_<member>; nd_lower materialises them, runs the transpiled
        # geometry math, and fills the buffers declared above.
        L.append("    // --- deterministic numpy->C++ lowered geometry (no port) ---")
        L += lowered_guard(type_name, geo_lowered, ["return MS::kFailure;"])
    else:
        L.append("    " + PORT_BEGIN)
        if for_port:
            L.append("    // Inputs are in `in_<name>`. Fill the geometry buffers above from them.")
            if raw_img_cache:
                L += _image_read_hint_lines(in_members)
            if kind == "mesh":
                L.append("    //   self.points (N,3)  -> points.push_back(MPoint(x,y,z))")
                L.append("    //   self.counts (F,)   -> counts.push_back(c)  (verts per face)")
                L.append("    //   self.indices (M,)  -> indices.push_back(i) (flat, sum(counts) long)")
            elif kind == "curve":
                L.append("    //   self.cvs/self.points (N,3) -> cvs.push_back(MPoint(x,y,z))")
                L.append("    //   self.degree (opt)          -> degree")
            else:
                L.append("    //   self.cvs (Nu*Nv,3) U-major -> cvs.push_back(MPoint(x,y,z))")
                L.append("    //   self.num_cvs_u / self.num_cvs_v -> numU / numV")
                L.append("    //   self.degree_u / self.degree_v (opt) -> degreeU / degreeV")
            L.append("    // Reproduce numpy with plain loops/std::sin/cos. Match CV/vertex ORDER.")
            L.append("    // Original Python compute (translate faithfully):")
            for src_line in (spec.get("compute") or "").splitlines():
                L.append("    //   | %s" % src_line)
        else:
            L.append("    // TODO: fill the geometry buffers from the Python compute below.")
            for src_line in (spec.get("compute") or "").splitlines():
                L.append("    //   | %s" % src_line)
        L.append("    " + PORT_END)
    L.append("")
    L.append("    // --- build the %s data + write output ---" % kind)
    L += _geo_build_lines(kind, info)
    L.append("    MDataHandle hOut = data.outputValue(%s, &gstat);" % out_member)
    L.append("    hOut.setMObject(newData);")
    L.append("    hOut.setClean();")
    L.append("    data.setClean(plug);")
    L.append("    return MS::kSuccess;")
    L.append("}")
    L.append("")
    # registration
    L.append("MStatus initializePlugin(MObject obj) {")
    L.append('    MFnPlugin plugin(obj, "mpynode-native", "1.0", "Any");')
    _reg_node = ('plugin.registerNode("%s", %s::id, %s::creator, %s::initialize)'
                 % (type_name, cls, cls, cls))
    if cmd_out["register"]:
        L.append("    MStatus st = %s;" % _reg_node)
        L.append("    if (!st) return st;")
        for reg in cmd_out["register"]:
            L.append("    " + reg)
        L.append("    return st;")
    else:
        L.append("    return %s;" % _reg_node)
    L.append("}")
    L.append("MStatus uninitializePlugin(MObject obj) {")
    L.append("    MFnPlugin plugin(obj);")
    for dereg in cmd_out["deregister"]:
        L.append("    " + dereg)
    L.append("    return plugin.deregisterNode(%s::id);" % cls)
    L.append("}")
    L.append("")
    return "\n".join(L)
