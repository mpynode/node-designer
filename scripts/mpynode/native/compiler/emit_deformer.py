"""MPxDeformerNode/MPxSkinCluster deform() emission."""
from __future__ import annotations

from mpynode._common.interface.morph_method_interface import LIVE_CPP_VARS

from .spec_model import PORT_BEGIN, PORT_END, lowered_guard
from .emit_attr import (_array_read_lines, _image_read_hint_lines,
                        _image_read_lines, _read_line)
from . import emit_geo_io


_DEFORMER_BASES = ("MPxDeformerNode", "MPxSkinCluster")

# Framework plugs an mPy deformer registers that its MPx BASE does not provide,
# as ``{mpy_type: ((plug, meta, extra_flags), ...)}``.
#
# ``MPxSkinCluster`` hands a compiled skinCluster ``matrix`` / ``bindPreMatrix``
# for free, but ``MPxDeformerNode`` has no ``targetGeometry`` -- that plug is
# mPyBlendShape's own, so a compiled blendShape has to declare it or the target
# meshes have nowhere to land. Without it every target connection is dropped on
# Convert to C++ (measured: 167 of them) and the compiled node is the only mPy
# node in the tree whose user-facing plug surface differs from its interpreted
# twin.
#
# It is deliberately NOT storable, exactly like the interpreted declaration: the
# deform reads the BAKED tables, the meshes are a live authoring link, and
# writing 167 meshes into every scene that touches one is not the point.
_BASE_FRAMEWORK_ATTRS = {
    "mPyBlendShape": (
        ("targetGeometry", {"type": "mesh", "is_array": True},
         ["    tAttr.setStorable(false);"]),
        # The live gate, matching the interpreted declaration in
        # _api1/mpy_blend_shape.py: ON by default, because following a connected
        # target is the behaviour the plug exists to expose rather than to
        # withhold. Switching it off pins the deform to the baked tables.
        ("liveTargets", {"type": "bool", "default_value": True},
         ["    nAttr.setKeyable(false);"]),
    ),
}


def base_attr_members(spec, members):
    """The framework plugs this deformer's MPx base does not supply, as
    emit_attr member dicts (mirrors ``file_texture_cpp.base_attr_members``).

    A plug the spec already carries is skipped -- the user/spec attr wins, since
    it is emitted anyway. Empty for every mpy_type without a framework plug.
    """
    from .emit_attr import _ident

    entries = _BASE_FRAMEWORK_ATTRS.get((spec or {}).get("mpy_type"), ())
    if not entries:
        return []
    have = set()
    for kind in ("inputs", "outputs"):
        have |= set((spec.get(kind) or {}).keys())
    taken = {m["member"] for m in (members or [])}
    out = []
    for plug, meta, flags in entries:
        if plug in have:
            continue
        ident = _ident(plug)
        base = "a" + ident[:1].upper() + ident[1:]
        mem, i = base, 1
        while mem in taken:
            i += 1
            mem = "%s%d" % (base, i)
        taken.add(mem)
        out.append({"plug": plug, "member": mem, "kind": "inputs",
                    "meta": dict(meta), "extra_flags": list(flags),
                    "affects": True})
    return out

_DEFORMER_INCLUDES = [
    "maya/MPxGeometryFilter.h", "maya/MItGeometry.h", "maya/MPoint.h",
    "maya/MPointArray.h", "maya/MFnMatrixData.h",
    "maya/MPlugArray.h", "maya/MFnDependencyNode.h",
    # skinCluster dense weightList read (derive the `weights` child attr)
    "maya/MFnCompoundAttribute.h", "maya/MArrayDataHandle.h",
    # mesh topology / 1-ring adjacency for relaxation-style deformers
    "maya/MFnMesh.h", "maya/MItMeshVertex.h", "maya/MIntArray.h", "maya/MFn.h",
    # per-vertex normals (deterministic getVertexNormals lowering);
    # MSpace comes transitively via MFnMesh.h (no standalone maya/MSpace.h)
    "maya/MFloatVectorArray.h", "maya/MFloatVector.h",
]

def _setdirty_lines(cls, ins, base, base_extra=()):
    """Emit setDependentsDirty(): user/dynamic inputs (and the inherited
    envelope/influence plugs) don't auto-propagate to the connected
    outputGeom[] elements in the deformer eval path, so dirty them by hand.
    Without this the node deforms on connect but never updates when an input
    (e.g. a driver matrix or a joint) changes.

    ``base_extra`` carries the framework plugs the MPx base did not supply
    (mPyBlendShape's targetGeometry). They reach attributeAffects already, but
    that is exactly the propagation this function exists because it cannot be
    relied on -- so a plug left out here is dirtied by nothing at all.
    """
    trig = ["attr == %s" % i["member"] for i in ins]
    trig += ["attr == %s" % i["member"] for i in (base_extra or ())
             if i.get("kind") == "inputs"]
    trig.append("attr == MPxGeometryFilter::envelope")
    if base == "MPxSkinCluster":
        trig += ["attr == MPxSkinCluster::matrix",
                 "attr == MPxSkinCluster::bindPreMatrix",
                 "attr == MPxSkinCluster::weightList"]
    cond = (" ||\n        ").join(trig)
    return [
        "MStatus %s::setDependentsDirty(const MPlug& plug, MPlugArray& affected) {" % cls,
        "    const MObject attr = plug.attribute();",
        "    const bool trigger =",
        "        %s;" % cond,
        "    if (trigger) {",
        "        MStatus st;",
        "        MFnDependencyNode fn(thisMObject());",
        "        MPlug outArray = fn.findPlug(MPxGeometryFilter::outputGeom, false, &st);",
        "        if (st == MS::kSuccess) {",
        "            const unsigned int ne = outArray.numElements();",
        "            for (unsigned int i = 0; i < ne; ++i)",
        "                affected.append(outArray.elementByPhysicalIndex(i));",
        "        }",
        "    }",
        "    return MS::kSuccess;",
        "}",
    ]

def _matrix_array_read(var, attr):
    """Read an inherited matrix-array plug into `std::vector<MMatrix> var`,
    LOGICAL-indexed: ``var[j]`` is logical element ``j``, sparse gaps filled with
    identity, sized to ``max logical + 1``. Mirrors the interpreted
    ``MatrixArrayView.stack()`` (via ``_MatrixPlugProvider``) so
    ``np.asarray(self.<matrixArray>)`` and this agree byte-for-byte -- a physical
    push_back would misalign ``matrix[j]`` / ``bindPreMatrix[j]`` / weight column
    ``j`` whenever the influence indices are sparse."""
    return [
        "    std::vector<MMatrix> %s;" % var,
        "    {",
        "        MArrayDataHandle _mh = block.inputArrayValue(%s, &status);" % attr,
        "        unsigned int _nm = _mh.elementCount();",
        "        std::vector<unsigned int> _li; std::vector<MMatrix> _mv;",
        "        _li.reserve(_nm); _mv.reserve(_nm);",
        "        int _maxli = -1;",
        "        for (unsigned int _k = 0; _k < _nm; ++_k) {",
        "            unsigned int _ix = _mh.elementIndex();",
        "            _li.push_back(_ix);",
        "            _mv.push_back(MFnMatrixData(_mh.inputValue().data()).matrix());",
        "            if ((int)_ix > _maxli) _maxli = (int)_ix;",
        "            _mh.next();",
        "        }",
        "        %s.assign((size_t)(_maxli + 1), MMatrix::identity);" % var,
        "        for (size_t _t = 0; _t < _mv.size(); ++_t) %s[_li[_t]] = _mv[_t];"
        % var,
        "    }",
    ]


def _weightlist_read():
    """Read the inherited skinCluster ``weightList`` into a dense row-major
    ``std::vector<double> skinW`` of shape ``(skinN, skinJ)`` -- LOGICAL-indexed
    (row v == vertex logical index, col j == influence logical index), ZERO
    gap-fill, with ``skinN = max vertex logical + 1`` and ``skinJ = max influence
    logical + 1``. Matches the interpreted ``WeightListView.asNumpy()`` so
    ``np.asarray(self.weightList)`` and this agree byte-for-byte. The ``weights``
    child attr is derived from ``weightList`` (no dependency on a
    ``MPxSkinCluster::weights`` static)."""
    return [
        "    std::vector<double> skinW; int64_t skinN = 0, skinJ = 0;",
        "    {",
        "        MObject _wAttr;",
        "        {",
        "            MStatus _cst;",
        "            MFnCompoundAttribute _cfn(MPxSkinCluster::weightList, &_cst);",
        "            if (_cst == MS::kSuccess && _cfn.numChildren() > 0)",
        "                _wAttr = _cfn.child(0);",
        "        }",
        "        MStatus _wst;",
        "        MArrayDataHandle _wl = block.inputArrayValue("
        "MPxSkinCluster::weightList, &_wst);",
        "        unsigned int _nv = _wl.elementCount();",
        "        int _maxv = -1, _maxj = -1;",
        "        std::vector<unsigned int> _vi; _vi.reserve(_nv);",
        "        std::vector<std::vector<unsigned int> > _ji(_nv);",
        "        std::vector<std::vector<double> > _wv(_nv);",
        "        for (unsigned int _k = 0; _k < _nv; ++_k) {",
        "            unsigned int _v = _wl.elementIndex();",
        "            _vi.push_back(_v);",
        "            if ((int)_v > _maxv) _maxv = (int)_v;",
        "            MArrayDataHandle _w(_wl.inputValue().child(_wAttr));",
        "            unsigned int _nj = _w.elementCount();",
        "            for (unsigned int _m = 0; _m < _nj; ++_m) {",
        "                unsigned int _j = _w.elementIndex();",
        "                if ((int)_j > _maxj) _maxj = (int)_j;",
        "                _ji[_k].push_back(_j);",
        "                _wv[_k].push_back(_w.inputValue().asDouble());",
        "                _w.next();",
        "            }",
        "            _wl.next();",
        "        }",
        "        skinN = (int64_t)(_maxv + 1);",
        "        skinJ = (int64_t)(_maxj + 1);",
        "        skinW.assign((size_t)(skinN * skinJ), 0.0);",
        "        for (unsigned int _k = 0; _k < _nv; ++_k) {",
        "            int64_t _row = (int64_t)_vi[_k] * skinJ;",
        "            for (size_t _t = 0; _t < _ji[_k].size(); ++_t)",
        "                skinW[(size_t)(_row + (int64_t)_ji[_k][_t])] = _wv[_k][_t];",
        "        }",
        "    }",
    ]

def _member_for(plug, *groups):
    """The C++ member holding ``plug``, searched across member groups."""
    for g in groups:
        for m in (g or ()):
            if m.get("plug") == plug:
                return m["member"]
    return None


def _live_targets_read(tg_member, gate_member):
    """Read the CONNECTED target meshes into the live CSR the blessed delta
    kernels take (``liveSlot`` / ``liveOffset`` / ``liveComponents`` /
    ``liveDeltas``), diffed against ``originalGeometry``.

    Construction history in a compiled node: the deform READS its target meshes
    rather than re-baking them, so it writes no plug and pushes nothing onto the
    undo stack -- the same contract the interpreted adapters keep, and the reason
    a re-bake from inside an evaluation is not an option (its setAttr has to be
    marshalled off the evaluation and lands in its own undo chunk).

    The table is UNWEIGHTED and keyed by live ENTRY, because the effective
    weights do not exist yet here -- they are computed by the compute body that
    runs after this. The kernel applies ``w[liveSlot[k]]``, which is what lets
    this prologue be weight-free and still agree with interpreted to the bit.

    Unlike interpreted this does NOT skip zero-weight slots (it has no effective
    weights to test), so it reads every connected target every evaluation. That
    is a cost difference, never a result difference: a zero-weight slot
    contributes 0.0 whether it is taken from the live table or the bake.
    """
    slot = LIVE_CPP_VARS["liveSlot"][1]
    ofs = LIVE_CPP_VARS["liveOffset"][1]
    comp = LIVE_CPP_VARS["liveComponents"][1]
    dlt = LIVE_CPP_VARS["liveDeltas"][1]
    return [
        "    // --- live targets (construction history; no plug write) ---",
        "    std::vector<int64_t> %s;" % slot,
        "    std::vector<int64_t> %s(1, 0);" % ofs,
        "    std::vector<int64_t> %s;" % comp,
        "    std::vector<double> %s;" % dlt,
        "    {",
        "        MStatus _lst;",
        "        bool _liveOn = true;",
        "        {",
        "            MDataHandle _lh = block.inputValue(%s, &_lst);" % gate_member,
        "            if (_lst == MS::kSuccess) _liveOn = _lh.asBool();",
        "        }",
        "        MFnDependencyNode _lfn(thisMObject(), &_lst);",
        "        if (_liveOn && _lst == MS::kSuccess) {",
        "            // Rest reference: originalGeometry BY NAME. 2026 exposes",
        "            // MPxGeometryFilter::originalGeometry as a static member and",
        "            // 2024 does not, so the name is the only spelling that",
        "            // compiles against both devkits.",
        "            MPointArray _rest;",
        "            bool _haveRest = false;",
        "            MStatus _ost;",
        "            MObject _ogAttr = _lfn.attribute(\"originalGeometry\", &_ost);",
        "            if (_ost == MS::kSuccess && !_ogAttr.isNull()) {",
        "                MArrayDataHandle _og = block.inputArrayValue(_ogAttr, &_ost);",
        "                if (_ost == MS::kSuccess",
        "                        && _og.jumpToElement(multiIndex) == MS::kSuccess) {",
        "                    MObject _om = _og.inputValue().asMesh();",
        "                    if (!_om.isNull()) {",
        "                        MFnMesh _ofn(_om, &_ost);",
        "                        if (_ost == MS::kSuccess) {",
        "                            _ofn.getPoints(_rest, MSpace::kObject);",
        "                            _haveRest = (_rest.length() == n);",
        "                        }",
        "                    }",
        "                }",
        "            }",
        "            // No rest reference -> no live pass. Measuring against the",
        "            // incoming points instead would fold any UPSTREAM deformation",
        "            // into every delta, silently and with the wrong sign.",
        "            MStatus _pst, _ast;",
        "            MPlug _tgPlug = _lfn.findPlug(%s, false, &_pst);" % tg_member,
        "            MArrayDataHandle _tg = block.inputArrayValue(%s, &_ast);"
        % tg_member,
        "            if (_haveRest && _pst == MS::kSuccess && _ast == MS::kSuccess",
        "                    && _tg.elementCount() > 0) {",
        "                for (;;) {",
        "                    MStatus _est;",
        "                    const unsigned int _li = _tg.elementIndex(&_est);",
        "                    if (_est != MS::kSuccess) break;",
        "                    // isDestination() is the ONLY honest discriminator:",
        "                    // targetGeometry is setStorable(false)+setCached(true),",
        "                    // so a DISCONNECTED element keeps serving its last",
        "                    // cached mesh and the data alone cannot tell you the",
        "                    // connection is gone. Trusting it would resurrect a",
        "                    // deleted target the baked deltas still drive.",
        "                    MPlug _el = _tgPlug.elementByLogicalIndex(_li, &_est);",
        "                    if (_est == MS::kSuccess && _el.isDestination()) {",
        "                        MObject _tm = _tg.inputValue().asMesh();",
        "                        MStatus _mst;",
        "                        if (!_tm.isNull()) {",
        "                            MFnMesh _tfn(_tm, &_mst);",
        "                            MPointArray _tp;",
        "                            if (_mst == MS::kSuccess)",
        "                                _tfn.getPoints(_tp, MSpace::kObject);",
        "                            // topology drift -> keep that slot's bake",
        "                            if (_mst == MS::kSuccess && _tp.length() == n) {",
        "                                int64_t _rows = 0;",
        "                                for (unsigned int _v = 0; _v < n; ++_v) {",
        "                                    const double _dx = _tp[_v].x - _rest[_v].x;",
        "                                    const double _dy = _tp[_v].y - _rest[_v].y;",
        "                                    const double _dz = _tp[_v].z - _rest[_v].z;",
        "                                    if (_dx != 0.0 || _dy != 0.0 || _dz != 0.0) {",
        "                                        %s.push_back((int64_t)_v);" % comp,
        "                                        %s.push_back(_dx);" % dlt,
        "                                        %s.push_back(_dy);" % dlt,
        "                                        %s.push_back(_dz);" % dlt,
        "                                        ++_rows;",
        "                                    }",
        "                                }",
        "                                %s.push_back((int64_t)_li);" % slot,
        "                                %s.push_back(%s.back() + _rows);" % (ofs, ofs),
        "                            }",
        "                        }",
        "                    }",
        "                    if (_tg.next() != MS::kSuccess) break;",
        "                }",
        "            }",
        "        }",
        "    }",
    ]


def _deform_lines(cls, ins, spec, base, for_port, lowered=None,
                  img_read=False, img_embedded=False, base_extra=(),
                  live_targets=False):
    """Body of deform() for the deformer family (MPxDeformerNode/MPxSkinCluster).

    Mirrors the Python contract: whole point array via allPositions, an
    ``env`` envelope scalar, user input locals, and (skin) inherited joint +
    bind-pose matrices -- with a marked region the AI fills with the per-point
    deformation. Stub mode is an identity pass-through.

    ``lowered`` (nd_lower.try_lower_deform output) replaces the AI PORT region
    with the deterministic numpy->C++ body: it materialises the harvested
    ``pts`` into an (N,3) nd::Array, runs the transpiled deform math, and
    scatters the result back into ``pts`` -- so the CSR adjacency scaffold (only
    used by AI-ported relaxation deformers) is skipped when lowering.

    ``img_read``/``img_embedded`` come from node_scaffold, which DECLARED the
    image caches. They are passed in rather than re-derived from the spec: this
    emitter used to derive nothing at all, so a sanctioned deformer got the cache
    declared above the class and no load in deform() -- a buffer the translation
    guide promised the porter and that never existed.
    """
    is_skin = base == "MPxSkinCluster"
    L = []
    L.append("MStatus %s::deform(MDataBlock& block, MItGeometry& iter," % cls)
    L.append("                   const MMatrix& worldMatrix, unsigned int multiIndex) {")
    L.append("    MStatus status;")
    L.append("    const float env = block.inputValue(MPxGeometryFilter::envelope, &status).asFloat();")
    L.append("")
    if ins:
        L.append("    // --- user inputs ---")
        for i in ins:
            if emit_geo_io.is_geo(i["meta"]["type"]) and i["meta"].get("is_array"):
                # multi (list) geo input -> std::vector<Nd<Kind>> in_<member>.
                L += emit_geo_io.geo_array_input_lines(i, src="block")
            elif i["meta"].get("is_array"):
                L += _array_read_lines(i, src="block")
            else:
                rl = _read_line(i, src="block")
                if rl:
                    L.append(rl)
        L.append("")
    # Sanctioned image-FILE read. Emitted AFTER the user inputs (the load reads
    # the path local one of them just declared) and BEFORE the geometry harvest,
    # so the whole deform body -- lowered or ported -- sees _imgPixels. The cache
    # itself is declared by node_scaffold; without this the declaration is dead
    # and the porter is told about a buffer that does not exist.
    if img_read:
        L += _image_read_lines(ins, embedded=img_embedded)
        L.append("")
    if lowered is not None:
        L += _raw_harvest_lines()
    else:
        L.append("    MPointArray pts;")
        L.append("    iter.allPositions(pts);")
        L.append("    const unsigned int n = pts.length();")
    L.append("")
    # Live targets. AFTER the harvest (it sizes the diff against `n`) and BEFORE
    # the lowered body, whose blessed delta call binds the four tables it builds.
    #
    # ``live_targets`` is decided by node_scaffold, NOT re-derived here: the
    # blessed calls are only visible after the ``self.morphs`` desugar, so the
    # raw spec this emitter is handed reports no called methods and no reads at
    # all. Deriving it here silently emitted nothing while nd_lower bound the
    # names anyway -- caught, at least, as an undeclared-identifier build error.
    if live_targets:
        tg = _member_for("targetGeometry", ins, base_extra)
        gate = _member_for("liveTargets", ins, base_extra)
        if tg and gate:
            L += _live_targets_read(tg, gate)
            L.append("")
    # Vertex adjacency (CSR, canonical sorted 1-ring) for relaxation-style
    # deformers, built from THIS geometry index's input mesh; empty if topology
    # is unavailable (the ported body must then leave pts unchanged).
    # MItGeometry::allPositions order matches MFnMesh/MItMeshVertex for a
    # full-mesh deform, so adjNbr indexes pts[] directly. Only the AI-porter
    # path consumes it -- a lowered deform has no adjacency binding.
    if lowered is None:
        L.append("    // --- vertex adjacency (CSR, canonical sorted 1-ring) ---")
        L.append("    std::vector<int> adjStart(n + 1, 0);")
        L.append("    std::vector<int> adjNbr;")
        L.append("    {")
        L.append("        MStatus _ast;")
        L.append("        MArrayDataHandle _inGeo = block.outputArrayValue(MPxGeometryFilter::input, &_ast);")
        L.append("        if (_ast == MS::kSuccess && _inGeo.jumpToElement(multiIndex) == MS::kSuccess) {")
        L.append("            MObject _meshObj = _inGeo.outputValue().child(MPxGeometryFilter::inputGeom).asMesh();")
        L.append("            if (!_meshObj.isNull() && _meshObj.hasFn(MFn::kMesh)) {")
        L.append("                std::vector<std::vector<int> > _rings(n);")
        L.append("                MItMeshVertex _vit(_meshObj, &_ast);")
        L.append("                for (; !_vit.isDone(); _vit.next()) {")
        L.append("                    int _vi = _vit.index();")
        L.append("                    if (_vi < 0 || _vi >= (int)n) continue;")
        L.append("                    MIntArray _conn; _vit.getConnectedVertices(_conn);")
        L.append("                    std::vector<int>& _r = _rings[_vi];")
        L.append("                    _r.resize(_conn.length());")
        L.append("                    for (unsigned _k = 0; _k < _conn.length(); ++_k) _r[_k] = _conn[_k];")
        L.append("                    std::sort(_r.begin(), _r.end());")
        L.append("                    _r.erase(std::unique(_r.begin(), _r.end()), _r.end());")
        L.append("                }")
        L.append("                for (unsigned _i = 0; _i < n; ++_i)")
        L.append("                    adjStart[_i + 1] = adjStart[_i] + (int)_rings[_i].size();")
        L.append("                adjNbr.reserve((size_t)adjStart[n]);")
        L.append("                for (unsigned _i = 0; _i < n; ++_i)")
        L.append("                    for (size_t _k = 0; _k < _rings[_i].size(); ++_k)")
        L.append("                        adjNbr.push_back(_rings[_i][_k]);")
        L.append("            }")
        L.append("        }")
        L.append("    }")
        L.append("")
    if is_skin:
        L.append("    // --- skin influences (inherited matrix[] / bindPreMatrix[]) ---")
        L += _matrix_array_read("jointMat", "MPxSkinCluster::matrix")
        L += _matrix_array_read("bindPre", "MPxSkinCluster::bindPreMatrix")
        # Dense weightList buffer -- ONLY the deterministic lowered body consumes
        # it (skinW/skinN/skinJ -> nd (N,J) in nd_lower); the AI-port path reads
        # weightList itself, so skip it there to avoid an unused buffer.
        if lowered is not None:
            L += _weightlist_read()
        L.append("")
    if lowered is not None:
        # deterministic numpy->C++ deform: materialise pts -> (N,3) nd::Array,
        # run the transpiled math, scatter back into pts. No AI port region.
        L.append("    // --- deterministic numpy->C++ lowered deform (no port) ---")
        # The guard wraps the WHOLE lowered body, not its per-vertex loops (which
        # the lowered body emits, scattering into `pts` inline): a per-vertex
        # try/catch would mean per-vertex RECOVERY -- some points deformed, the
        # rest not -- which no interpreted node can produce (a raising Python
        # deform commits nothing). One handler here abandons the whole deform, so
        # `pts` is never written back and the geometry passes through unchanged.
        L += lowered_guard(spec["suggested"]["node_type_name"], lowered,
                           ["return MS::kFailure;"])
    else:
        L.append("    " + PORT_BEGIN)
        if for_port:
            L.append("    // Deform IN PLACE: pts[i] is the object-space MPoint of vertex i (i in")
            L.append("    // [0,n)); mutate it and leave the result in pts. Honour the envelope `env`")
            L.append("    // (0..1, blend deformed vs original) and, if the source used painted")
            L.append("    // weights, scale by weightValue(block, multiIndex, i).")
            if img_read:
                L += _image_read_hint_lines(ins)
            L.append("    // `adjStart`/`adjNbr` (std::vector<int>) are the CSR 1-ring adjacency:")
            L.append("    //   neighbors of pts[i] are adjNbr[adjStart[i] .. adjStart[i+1]).")
            L.append("    //   Use for Laplacian/Taubin/relaxation smoothing; if adjNbr is empty")
            L.append("    //   (topology unavailable) leave pts unchanged. numba @njit/prange ->")
            L.append("    //   plain loops; a prange step is Jacobi (read src, write a SEPARATE")
            L.append("    //   buffer, then swap) -- preserve that double-buffering exactly.")
            if is_skin:
                L.append("    // Linear-blend skin: jointMat[j] is influence j's world matrix, bindPre[j]")
                L.append("    //   its bind-pose inverse. Per-influence weights live in the inherited")
                L.append("    //   weightList[i].weights[j] plug (read via MArrayDataHandle on")
                L.append("    //   MPxSkinCluster::weightList if the port needs them). Classic skin:")
                L.append("    //   p' = sum_j w_ij * (pts[i] * bindPre[j] * jointMat[j]).")
            L.append("    // Original Python compute (translate faithfully):")
        else:
            L.append("    // Stub: identity deform (geometry passes through unchanged).")
            L.append("    // Original Python compute (for reference):")
        for src_line in (spec.get("compute") or "").splitlines():
            L.append("    //   | %s" % src_line)
        L.append("    " + PORT_END)
    L.append("")
    if lowered is not None:
        L += _raw_commit_lines()
    else:
        L.append("    iter.setAllPositions(pts);")
    L.append("    return MS::kSuccess;")
    L.append("}")
    return L


def _raw_harvest_lines():
    """The geometry harvest of a LOWERED deform (indent-1 C++).

    MItGeometry offers only MPointArray -- double, 4-wide -- for bulk access, so
    ``allPositions``/``setAllPositions`` cost a 5.1 MB allocation plus a
    float->double widen and a double->float narrow over a 160k-vertex mesh
    (measured 535 us of an 890 us deform, sineRipple ledger). For a MESH deformed
    in full (every vertex is a member, so iterator index i == vertex i) the
    output mesh's own float xyz store holds exactly the values allPositions would
    widen, so the lowered body reads it raw (``_rawIn``), writes its narrowed
    result back into that same store (nd_lower ``_deform_writeback_lines``), and
    :func:`_raw_commit_lines` tells Maya the surface moved. The casts are the
    ones the MPointArray round trip performs, so the mesh is bit-identical;
    4 of the 50 accepted optimizer rounds did exactly this by hand.

    MEASURED 2026-09-09, sineRipple at 159,602 vertices, same scene, outputs
    identical: MPointArray round trip 23.32 ms; raw read + MFnMesh::setPoints
    23.21 ms; raw read + iter.setAllPositions 24.26 ms; raw read + in-place
    write + updateSurface 20.88 ms. Only the in-place write pays.

    Any other geometry (NURBS CVs, a partial deformer set) takes the MPointArray
    path unchanged: ``_rawIn`` stays null and ``pts`` is filled.
    ``outputArrayValue`` hands back the datablock's storage without pulling, so
    there is no re-entry into this compute.
    """
    return [
        "    // --- geometry harvest: raw float fast path (mesh, full membership) ---",
        "    MPointArray pts;",
        "    const float* _rawIn = 0;",
        "    MObject _outMeshObj;",
        "    unsigned int n = 0;",
        "    {",
        "        MStatus _hs;",
        "        MArrayDataHandle _hOut = block.outputArrayValue("
        "MPxGeometryFilter::outputGeom, &_hs);",
        "        if (_hs == MS::kSuccess && _hOut.jumpToElement(multiIndex) == "
        "MS::kSuccess) {",
        "            MObject _om = _hOut.outputValue().asMesh();",
        "            if (!_om.isNull() && _om.hasFn(MFn::kMesh)) {",
        "                MFnMesh _ofn(_om, &_hs);",
        "                const int _nv = (_hs == MS::kSuccess) ? _ofn.numVertices() "
        ": -1;",
        "                if (_nv > 0 && (unsigned int)_nv == iter.count()) {",
        "                    const float* _rp = _ofn.getRawPoints(&_hs);",
        "                    if (_hs == MS::kSuccess && _rp) {",
        "                        _rawIn = _rp; _outMeshObj = _om; "
        "n = (unsigned int)_nv;",
        "                    }",
        "                }",
        "            }",
        "        }",
        "    }",
        "    if (!_rawIn) { iter.allPositions(pts); n = pts.length(); }",
    ]


def _raw_commit_lines():
    """Commit a LOWERED deform's result (indent-1 C++). On the raw path the
    points already sit in the mesh's own store (the writer put them there), so
    the commit is ``MFnMesh::updateSurface`` -- the bbox / normal refresh
    setPoints would have done; otherwise ``iter.setAllPositions(pts)``. See
    :func:`_raw_harvest_lines`."""
    return [
        "    if (_rawIn) {",
        "        MFnMesh(_outMeshObj).updateSurface();",
        "    } else {",
        "        iter.setAllPositions(pts);",
        "    }",
    ]
