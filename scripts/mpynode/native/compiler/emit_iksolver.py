"""MPxIkSolverNode doSolve() emission."""
from __future__ import annotations

from .spec_model import PORT_BEGIN, PORT_END, lowered_guard
from .emit_attr import (_ident, _create_lines, _image_read_hint_lines,
                        _image_read_lines, _pick_path_input, _read_plug_decl,
                        _read_plug_assign, _read_plug_array_decl,
                        _read_plug_array_assign, findplug_family_extras,
                        findplug_local_hint)
from .emit_locator import _LOCATOR_MESH_HELPERS, _MESH_QUERY_HELPERS
from . import emit_geo_io
from . import nd_lower
from .nd_runtime import _nd_runtime_cpp
from mpynode.native.compiler.kernels import file_texture_cpp
from mpynode.native.compiler.kernels import nd_io_cpp
from mpynode.native.compiler.kernels import command_dispatch


_IKSOLVER_BASE = "MPxIkSolverNode"

_IKSOLVER_INCLUDES = [
    "cmath", "vector", "algorithm", "map", "string", "random", "cstdint",
    "cstdio",
    "maya/MPxIkSolverNode.h", "maya/MFnPlugin.h", "maya/MTypeId.h",
    "maya/MIkHandleGroup.h", "maya/MFnIkHandle.h", "maya/MFnIkJoint.h",
    "maya/MFnTransform.h", "maya/MFnDagNode.h", "maya/MFnDependencyNode.h",
    "maya/MDagPath.h", "maya/MObject.h", "maya/MMatrix.h", "maya/MVector.h",
    "maya/MPoint.h", "maya/MEulerRotation.h", "maya/MQuaternion.h",
    "maya/MTransformationMatrix.h", "maya/MString.h", "maya/MPlug.h",
    "maya/MStatus.h", "maya/MGlobal.h", "maya/MFn.h",
    # user INPUT attrs (initialize) + optional mesh-floor input (doSolve).
    # NOTE: MSpace has no standalone header -- it arrives via MFnTransform.h /
    # MTransformationMatrix.h (already included above).
    "maya/MFnNumericAttribute.h", "maya/MFnEnumAttribute.h",
    "maya/MFnTypedAttribute.h", "maya/MFnNumericData.h", "maya/MFnData.h",
    # generic (non-scalar/non-mesh) user INPUT attrs: unit (angle/time/euler),
    # compound (quaternion), matrix create + the MAngle/MTime plug reads.
    "maya/MFnUnitAttribute.h", "maya/MFnCompoundAttribute.h",
    "maya/MFnMatrixAttribute.h", "maya/MAngle.h", "maya/MTime.h",
    "maya/MFnMesh.h", "maya/MPointArray.h", "maya/MIntArray.h",
    "maya/MFloatVectorArray.h",
    # local_matrices writeback drives offsetParentMatrix (matrix plug I/O).
    "maya/MFnMatrixData.h",
    # persisted per-joint bind offsets (a matrixArray attr on the solver node).
    "maya/MFnMatrixArrayData.h", "maya/MMatrixArray.h",
]

# Fixed C++ helper: gate-mix two row-vector (Maya) world matrices -- rotation /
# translate / scale of `wtarget` where the matching gate is true, else from
# `wbase`. Rotation & scale are split by the upper-3x3 row norms (assumes
# negligible shear -- true for joint chains). Mirrors the interpreted
# _gate_mix_world in mpynode/_api1/helpers.py byte-for-byte.
_IK_MATRIX_HELPERS = r"""
static MMatrix nd_ik_gate_mix(const MMatrix& wb, const MMatrix& wt,
                              bool gr, bool gt, bool gs) {
    double Rb[3][3], Sb[3], Rt[3][3], St[3];
    for (int i = 0; i < 3; ++i) {
        double bx = wb(i,0), by = wb(i,1), bz = wb(i,2);
        double bl = sqrt(bx*bx + by*by + bz*bz); Sb[i] = bl;
        double bs = (bl < 1e-12) ? 1.0 : bl;
        Rb[i][0] = bx/bs; Rb[i][1] = by/bs; Rb[i][2] = bz/bs;
        double tx = wt(i,0), ty = wt(i,1), tz = wt(i,2);
        double tl = sqrt(tx*tx + ty*ty + tz*tz); St[i] = tl;
        double ts = (tl < 1e-12) ? 1.0 : tl;
        Rt[i][0] = tx/ts; Rt[i][1] = ty/ts; Rt[i][2] = tz/ts;
    }
    double out[4][4] = {{0,0,0,0},{0,0,0,0},{0,0,0,0},{0,0,0,1}};
    for (int i = 0; i < 3; ++i) {
        double sc = gs ? St[i] : Sb[i];
        for (int k = 0; k < 3; ++k)
            out[i][k] = (gr ? Rt[i][k] : Rb[i][k]) * sc;
    }
    out[3][0] = gt ? wt(3,0) : wb(3,0);
    out[3][1] = gt ? wt(3,1) : wb(3,1);
    out[3][2] = gt ? wt(3,2) : wb(3,2);
    return MMatrix(out);
}

// Read a node's local ".matrix" (offset-free) as an MMatrix.
static MMatrix nd_ik_local_matrix(const MDagPath& path) {
    MMatrix m;
    MFnDependencyNode fn(path.node());
    MStatus ms; MPlug p = fn.findPlug("matrix", false, &ms);
    if (ms == MS::kSuccess && !p.isNull()) {
        MObject mo = p.asMObject();
        if (!mo.isNull()) m = MFnMatrixData(mo).matrix();
    }
    return m;
}

// Read / write a node's offsetParentMatrix.
static MMatrix nd_ik_get_offset(const MDagPath& path) {
    MMatrix m;
    MFnDependencyNode fn(path.node());
    MStatus ms; MPlug p = fn.findPlug("offsetParentMatrix", false, &ms);
    if (ms == MS::kSuccess && !p.isNull()) {
        MObject mo = p.asMObject();
        if (!mo.isNull()) m = MFnMatrixData(mo).matrix();
    }
    return m;
}
static void nd_ik_set_offset(const MDagPath& path, const MMatrix& off) {
    MFnDependencyNode fn(path.node());
    MStatus ms; MPlug p = fn.findPlug("offsetParentMatrix", false, &ms);
    if (ms == MS::kSuccess && !p.isNull()) {
        MFnMatrixData md; MObject mo = md.create(off);
        p.setMObject(mo);
    }
}

// Persist the captured per-joint bind offsets to the solver's OWN storable
// matrixArray plug. This mirrors the interpreted path's cmds.setAttr: the write
// is routed through the command engine, NOT MPlug::setMObject. A direct plug
// write on the solver's own node from inside doSolve re-dirties the node, so
// Maya re-evaluates the handle -> doSolve recurses (the fresh value is not yet
// readable via findPlug mid-eval, so the guard never trips) -> unbounded
// recursion -> crash. The command-engine write is synchronous, batch-safe (no
// idle loop needed), and serializes with the scene like any setAttr.
static void nd_ik_persist_bind(const MString& plugName, const MMatrixArray& arr) {
    MString cmd = "setAttr \"";
    cmd += plugName;
    cmd += "\" -type \"matrixArray\" ";
    char cb[24]; snprintf(cb, sizeof(cb), "%u", arr.length());
    cmd += cb;
    for (unsigned m = 0; m < arr.length(); ++m)
        for (int r = 0; r < 4; ++r)
            for (int c = 0; c < 4; ++c) {
                char vb[40]; snprintf(vb, sizeof(vb), " %.17g", arr[m](r, c));
                cmd += vb;
            }
    cmd += ";";
    MGlobal::executeCommand(cmd);
}
"""

_IK_CREATE_DATA = {"float": "kFloat", "double": "kDouble", "int": "kInt",
                   "bool": "kBoolean"}

_IK_READ_ACC = {"float": "asFloat", "double": "asDouble", "int": "asInt",
                "bool": "asBool", "enum": "asShort"}

_IK_CTYPE = {"float": "float", "double": "double", "int": "int",
             "bool": "bool", "enum": "short"}

def _ik_default(t, val, enum_names=None):
    if t == "bool":
        return "true" if val else "false"
    if t in ("enum", "int"):
        try:
            return "%d" % int(val)
        except Exception:
            return "0"
    try:
        return repr(float(val))   # float/double C++ literal
    except Exception:
        return "0.0"

def _ik_scalar_inputs(spec):
    """Scalar user inputs on the solver node (float/double/int/bool/enum)."""
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        t = meta.get("type")
        if t in _IK_BESPOKE_SCALAR_TYPES and not meta.get("is_array"):
            out.append({"plug": plug, "ident": _ident(plug), "type": t,
                        "enum_names": meta.get("enum_names") or [],
                        "default_value": meta.get("default_value")})
    return out

def _ik_mesh_inputs(spec):
    """SINGLE mesh user inputs on the solver node (the floor/collision surface).

    Array meshes ride the generic geo path (std::vector<NdMesh>) instead."""
    return [{"plug": plug, "ident": _ident(plug)}
            for plug, meta in (spec.get("inputs") or {}).items()
            if meta.get("type") == "mesh" and not meta.get("is_array")]

# Scalar user INPUT types with a bespoke, byte-identical read (_ik_scalar_inputs);
# a SINGLE mesh likewise (_ik_mesh_inputs). EVERY other input -- remaining scalar
# types and ARRAYS of any type, geometry included -- rides the shared findPlug
# readers below.
_IK_BESPOKE_SCALAR_TYPES = ("float", "double", "int", "bool", "enum")

def _ik_generic_inputs(spec):
    """User INPUT attrs read into doSolve through the shared findPlug readers.

    Canonical ``m`` dicts (member ``a_<ident>`` -> read local ``in_a_<ident>``)
    so emit_attr._create_lines (plug creation) + _read_plug_decl/_read_plug_assign
    (scalars), _read_plug_array_decl/_read_plug_array_assign (arrays) and
    emit_geo_io.geo_plug_* (geometry) consume them unchanged -- the same shared
    machinery the transform path uses. nd_lower.lower_iksolver binds these same
    ``in_a_<ident>`` locals on the deterministic path, so a lowered solve and a
    ported one read a user input through identical C++."""
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        t = meta.get("type")
        if not meta.get("is_array"):
            # bespoke scalar / single-mesh paths stay byte-identical
            if t in _IK_BESPOKE_SCALAR_TYPES or t == "mesh":
                continue
        out.append({"plug": plug, "member": "a_" + _ident(plug),
                    "meta": meta, "kind": "inputs"})
    return out

def _ik_generic_local_hint(t):
    """C++ shape of a generic input's ``in_a<ident>`` local (PORT comment)."""
    return {
        "vector": "double[3]; .x==[0]", "euler": "double[3], RADIANS",
        "color": "float[3] RGB", "float2": "float[2]",
        "quaternion": "double[4] {x,y,z,w}", "angle": "double, RADIANS",
        "time": "double, seconds", "string": "MString; .asChar()",
        "matrix": "MMatrix; m(row,col)",
    }.get(t, t)

def _generate_iksolver_cpp(spec: dict, for_port: bool = False) -> str:
    """Emit a native MPxIkSolverNode plugin. The solver config + the doSolve()
    data marshalling (walk the handle group's joint chain, capture/persist the
    per-joint bind offsets, read each joint's rest LOCAL + WORLD matrix /
    IK-handle target / pole / twist) AND the dual-matrix writeback (per joint:
    WORLD > LOCAL > restore-bind, gate-mix + offsetParentMatrix) are fixed; the
    SOLVE MATH between the PORT markers -- which fills each driven joint's desired
    LOCAL matrix (outLocalMat[j]) or WORLD matrix (outWorldMat[j]) + the per-joint
    channel gates -- is either DETERMINISTICALLY LOWERED from the Python solve
    expression (nd_lower.try_lower_iksolver) or, when the math falls outside the
    lowerable subset, filled by the AI porter.
    """
    iksolver_lowered = nd_lower.try_lower_iksolver(spec)
    # A file read can only be attached to real buffers on the lowered path; when
    # the compute drops to the AI porter there is nothing to attach it to.
    nd_io_cpp.reject_unlowered_io(spec, iksolver_lowered, "IK solver")
    sg        = spec["suggested"]
    cls       = sg["class_name"]
    type_name = sg["node_type_name"]
    type_id   = sg["type_id"]
    scalars   = _ik_scalar_inputs(spec)
    meshes    = _ik_mesh_inputs(spec)
    generics  = _ik_generic_inputs(spec)
    has_mesh  = bool(meshes)
    # Sanctioned image-FILE read (reads_image_file): load the path input through
    # the same CACHED decode every other base uses and hand the ported solve an
    # RGBA8 buffer. Without it the translation guide tells the porter the pixels
    # are "loaded above" while nothing was emitted, and the port drops the
    # feature. A string input is never a bespoke scalar, so the path always lands
    # in `generics` -- the same list _image_read_lines binds its read local from.
    # No path input at all (hardcoded path in Init) -> no cache and no hint: the
    # node has no path PLUG, so there is nothing to load.
    _img_path = (_pick_path_input(generics)
                 if sg.get("reads_image_file") else None)
    raw_img_cache       = bool(_img_path) and not _img_path["meta"].get("is_array")
    composite_img_cache = bool(_img_path) and bool(_img_path["meta"].get("is_array"))
    img_read            = raw_img_cache or composite_img_cache
    cmd_out             = command_dispatch.dispatch_for_spec(spec, type_name)
    if cmd_out["errors"]:
        import sys as _sys
        _sys.stderr.write(
            "[command_dispatch] %s: command(s) not lowered: %s\n"
            % (type_name, "; ".join(cmd_out["errors"])))
    L = []
    L.append("// %s -- generated MPxIkSolverNode skeleton (codegen)." % type_name)
    L.append("// Source mPyNode: %s (%s)"
             % (spec.get("source_node"), spec.get("mpy_type")))
    L.append("// Solver config + doSolve() marshalling (joint chain, end effector,")
    L.append("// pole/twist, USER INPUT attrs + optional floor MESH) are final; the")
    if iksolver_lowered is not None:
        L.append("// SOLVE MATH is DETERMINISTICALLY LOWERED from the Python solve")
        L.append("// expression (no AI porter); nd_runtime.h is inlined below.")
    else:
        L.append("// SOLVE MATH (between the PORT markers) is filled by the AI porter.")
    L.append("")
    _extra_incs, _extra_blocks = findplug_family_extras(generics)
    for inc in _IKSOLVER_INCLUDES:
        L.append("#include <%s>" % inc)
    for inc in _extra_incs:                  # hex / geo machinery (if declared)
        if inc not in _IKSOLVER_INCLUDES:
            L.append("#include <%s>" % inc)
    _img_incs = []
    if raw_img_cache:
        _img_incs = ["maya/MImage.h"] + list(file_texture_cpp.RAW_CACHE_INCLUDES)
    elif composite_img_cache:
        _img_incs = ["maya/MImage.h"] + list(
            file_texture_cpp.COMPOSITE_CACHE_INCLUDES)
    for inc in _img_incs:
        if inc not in _IKSOLVER_INCLUDES and inc not in _extra_incs:
            L.append("#include <%s>" % inc)
    # nd_io (ndio.read/write, np.fromfile/np.save, .tofile) rides on top of nd::,
    # so it is only reachable on the lowered path (reject_unlowered_io above).
    if iksolver_lowered is not None and nd_io_cpp.spec_uses_ndio(spec):
        for inc in nd_io_cpp.NDIO_INCLUDES:
            if (inc not in _IKSOLVER_INCLUDES and inc not in _extra_incs
                    and inc not in _img_incs):
                L.append("#include <%s>" % inc)
    if cmd_out["classes"]:
        _seen_inc = set(_IKSOLVER_INCLUDES) | set(_extra_incs) | set(_img_incs)
        if iksolver_lowered is not None and nd_io_cpp.spec_uses_ndio(spec):
            _seen_inc |= set(nd_io_cpp.NDIO_INCLUDES)
        for inc in cmd_out["includes"]:
            if inc not in _seen_inc:
                _seen_inc.add(inc)
                L.append("#include <%s>" % inc)
    L.append("")
    if iksolver_lowered is not None:
        L.append(_nd_runtime_cpp())
        L.append("")
        if nd_io_cpp.spec_uses_ndio(spec):
            L.append(nd_io_cpp.NDIO_CPP)
            L.append("")
    if has_mesh:
        L.append(_LOCATOR_MESH_HELPERS)
        L.append(_MESH_QUERY_HELPERS)
    for blk in _extra_blocks:
        L.append(blk)
    # Image decode cache, emitted above the class so doSolve() can call it. The
    # decode is cached per instance for the same reason as everywhere else: a
    # readFromFile per solve runs on every DG evaluation of the handle.
    if raw_img_cache:
        L.append(file_texture_cpp.RAW_CACHE_CPP)
        L.append("")
    if composite_img_cache:
        L.append(file_texture_cpp.COMPOSITE_CACHE_CPP)
        L.append("")
    L.append(_IK_MATRIX_HELPERS)
    L.append("class %s : public MPxIkSolverNode {" % cls)
    L.append("public:")
    L.append("    %s() {}" % cls)
    L.append("    ~%s() override {}" % cls)
    L.append("    static void*   creator() { return new %s(); }" % cls)
    L.append("    static MStatus initialize();")
    L.append("    static MTypeId id;")
    for s in scalars:
        L.append("    static MObject a_%s;" % s["ident"])
    for m in meshes:
        L.append("    static MObject a_%s;" % m["ident"])
    for gm in generics:
        L.append("    static MObject %s;" % gm["member"])
    L.append("    static MObject a_jointBindOffsets;  // persisted per-joint bind offsets")
    L.append('    MString solverTypeName() const override { return MString("%s"); }'
             % type_name)
    L.append("    bool isSingleChainOnly()      const override { return false; }")
    L.append("    bool isPositionOnly()         const override { return false; }")
    L.append("    bool hasJointLimitSupport()   const override { return false; }")
    L.append("    bool hasUniqueSolution()      const override { return true; }")
    L.append("    bool groupHandlesByTopology() const override { return false; }")
    L.append("    MStatus doSolve() override;")
    # Per-instance image cache + lock (doSolve is non-const, so no `mutable`).
    if raw_img_cache:
        L.append(file_texture_cpp.RAW_CACHE_MEMBERS.rstrip("\n"))
    if composite_img_cache:
        L.append(file_texture_cpp.COMPOSITE_CACHE_MEMBERS.rstrip("\n"))
    L.append("};")
    L.append("")
    L.append("MTypeId %s::id(%s);" % (cls, type_id))
    for s in scalars:
        L.append("MObject %s::a_%s;" % (cls, s["ident"]))
    for m in meshes:
        L.append("MObject %s::a_%s;" % (cls, m["ident"]))
    for gm in generics:
        L.append("MObject %s::%s;" % (cls, gm["member"]))
    L.append("MObject %s::a_jointBindOffsets;" % cls)
    L.append("")
    # initialize(): create the user INPUT plugs (scalars + the mesh floor).
    L.append("MStatus %s::initialize() {" % cls)
    if scalars or meshes or generics:
        L.append("    MFnNumericAttribute nAttr;")
        L.append("    MFnEnumAttribute    eAttr;")
        L.append("    MFnTypedAttribute   tAttr;")
        if generics:
            L.append("    MFnUnitAttribute     uAttr;")
            L.append("    MFnCompoundAttribute cAttr;")
            L.append("    MFnMatrixAttribute   mAttr;")
        for s in scalars:
            plug, mem, t = s["plug"], "a_" + s["ident"], s["type"]
            dv = _ik_default(t, s["default_value"], s["enum_names"])
            if t == "enum":
                L.append('    %s = eAttr.create("%s", "%s", %s);'
                         % (mem, plug, plug, dv))
                for i, fld in enumerate(s["enum_names"]):
                    L.append('    eAttr.addField("%s", %d);' % (fld, i))
                L.append("    eAttr.setStorable(true); eAttr.setKeyable(true);")
            else:
                L.append('    %s = nAttr.create("%s", "%s", MFnNumericData::%s, %s);'
                         % (mem, plug, plug, _IK_CREATE_DATA[t], dv))
                L.append("    nAttr.setStorable(true); nAttr.setKeyable(true);")
            L.append("    addAttribute(%s);" % mem)
        for m in meshes:
            mem = "a_" + m["ident"]
            L.append('    %s = tAttr.create("%s", "%s", MFnData::kMesh);'
                     % (mem, m["plug"], m["plug"]))
            L.append("    tAttr.setStorable(false); tAttr.setWritable(true);")
            L.append("    addAttribute(%s);" % mem)
        # Generic inputs: create via the shared emit_attr._create_lines (same plug
        # construction the plain-node scaffold uses) so a connected/AE value is
        # readable by doSolve's findPlug read below.
        for gm in generics:
            L += _create_lines(gm)
            L.append("    addAttribute(%s);" % gm["member"])
    # persisted per-joint bind offsets (matrixArray, hidden + storable so it
    # saves with the scene). Captured on the first solve; cleared by a re-bind.
    L.append("    { MFnTypedAttribute bAttr; MFnMatrixArrayData bDef;")
    L.append("      MObject bDefObj = bDef.create();")
    L.append('      a_jointBindOffsets = bAttr.create("_jointBindOffsets", "_jointBindOffsets", MFnData::kMatrixArray, bDefObj);')
    L.append("      bAttr.setStorable(true); bAttr.setHidden(true); bAttr.setWritable(true);")
    L.append("      addAttribute(a_jointBindOffsets); }")
    L.append("    return MS::kSuccess;")
    L.append("}")
    L.append("")
    if cmd_out["classes"]:
        # Placed after <cls>::id / initialize() (the classes reference them);
        # the bundler wraps this region in `namespace nd_<node>`, which is what
        # keeps two nodes' command support from colliding in a merged plug-in.
        L.append("// ==== companion commands (Methods @maya_command) ====")
        L.append(cmd_out["classes"])
        L.append("")
    L.append("MStatus %s::doSolve() {" % cls)
    L.append("    MStatus status;")
    L.append("    MIkHandleGroup* group = handleGroup();")
    L.append("    if (!group || group->handleCount() <= 0) return MS::kFailure;")
    L.append("    MObject handleObj = group->handle(0);")
    L.append("    MFnIkHandle fnHandle(handleObj, &status);")
    L.append("    if (!status) return status;")
    L.append("")
    L.append("    MDagPath startPath, effectorPath;")
    L.append("    fnHandle.getStartJoint(startPath);")
    L.append("    fnHandle.getEffector(effectorPath);")
    L.append("")
    L.append("    // Walk the joint chain: start joint, then first joint-child each step.")
    L.append("    std::vector<MDagPath> jointPaths;")
    L.append("    jointPaths.push_back(startPath);")
    L.append("    for (int guard = 0; guard < 100; ++guard) {")
    L.append("        MFnDagNode dagFn(jointPaths.back());")
    L.append("        bool advanced = false;")
    L.append("        for (unsigned c = 0; c < dagFn.childCount(); ++c) {")
    L.append("            MObject child = dagFn.child(c);")
    L.append("            if (!child.hasFn(MFn::kJoint)) continue;")
    L.append("            bool seen = false;")
    L.append("            for (size_t k = 0; k < jointPaths.size(); ++k)")
    L.append("                if (jointPaths[k].node() == child) { seen = true; break; }")
    L.append("            if (seen) continue;")
    L.append("            MDagPath childPath; MDagPath::getAPathTo(child, childPath);")
    L.append("            jointPaths.push_back(childPath);")
    L.append("            advanced = true; break;")
    L.append("        }")
    L.append("        if (!advanced) break;")
    L.append("    }")
    L.append("    const int numJoints = (int)jointPaths.size();")
    L.append("")
    L.append("    if (numJoints <= 0) return MS::kSuccess;")
    L.append("    const double RAD2DEG = 57.295779513082323;")
    L.append("    const double DEG2RAD = 0.017453292519943295;")
    L.append("    (void)RAD2DEG; (void)DEG2RAD;")
    L.append("")
    L.append("    // Per-joint offset-free LOCAL matrices (the '.matrix' plug --")
    L.append("    // excludes offsetParentMatrix, so it is stable across solves).")
    L.append("    std::vector<MMatrix> jointLocal(numJoints);")
    L.append("    for (int j = 0; j < numJoints; ++j)")
    L.append("        jointLocal[j] = nd_ik_local_matrix(jointPaths[j]);")
    L.append("")
    L.append("    // Chain root's TRUE DAG-parent world (EXCLUDES the chain's own")
    L.append("    // offsets -- unlike parentInverseMatrix, which folds a node's own")
    L.append("    // offsetParentMatrix in and would drift the reference each solve).")
    L.append("    MMatrix rootParentWorld;")
    L.append("    { MDagPath pp = jointPaths[0]; pp.pop();")
    L.append("      if (pp.length() > 0) rootParentWorld = pp.inclusiveMatrix(); }")
    L.append("")
    L.append("    // Per-joint BIND offsets: captured (root->tip) on the FIRST solve")
    L.append("    // from the joints' current offsetParentMatrix (before any writeback,")
    L.append("    // so they are the neutral), then locked + persisted in the storable")
    L.append("    // matrixArray plug (survives save/reload). A re-bind clears the plug")
    L.append("    // so the next solve re-captures the current pose as the new neutral.")
    L.append("    std::vector<MMatrix> bindOffsets(numJoints);")
    L.append("    { MFnDependencyNode _bfn(thisMObject());")
    L.append("      MStatus _bs; MPlug _bp = _bfn.findPlug(a_jointBindOffsets, false, &_bs);")
    L.append("      bool _have = false;")
    L.append("      if (_bs == MS::kSuccess && !_bp.isNull()) {")
    L.append("          MObject _bo = _bp.asMObject();")
    L.append("          if (!_bo.isNull()) { MStatus _ms2; MFnMatrixArrayData _mad(_bo, &_ms2);")
    L.append("              if (_ms2 == MS::kSuccess) {")
    L.append("                  // Copy each MMatrix (value type) out of the array WHILE the")
    L.append("                  // data MObject is alive: MFnMatrixArrayData::array() returns a")
    L.append("                  // reference into the buffer owned by _bo, so keeping an")
    L.append("                  // MMatrixArray alias would dangle (length reads 0 -> an")
    L.append("                  // out-of-bounds index -> crash) once _bo/_mad leave scope.")
    L.append("                  const MMatrixArray& _arr = _mad.array();")
    L.append("                  if (_arr.length() == (unsigned)numJoints) {")
    L.append("                      for (int j = 0; j < numJoints; ++j) bindOffsets[j] = _arr[j];")
    L.append("                      _have = true; } } } }")
    L.append("      if (!_have) {")
    L.append("          MMatrixArray _cap; _cap.setLength(numJoints);")
    L.append("          for (int j = 0; j < numJoints; ++j) {")
    L.append("              bindOffsets[j] = nd_ik_get_offset(jointPaths[j]); _cap[j] = bindOffsets[j]; }")
    L.append("          // persist via the command engine (see nd_ik_persist_bind): a direct")
    L.append("          // self-plug write here would recurse the solve to a crash.")
    L.append("          if (!_bp.isNull()) nd_ik_persist_bind(_bp.name(), _cap); } }")
    L.append("")
    L.append("    // REST world per joint: thread locals AND bind offsets from the root")
    L.append("    // parent (row-vector Maya: world = local * offset * parentWorld).")
    L.append("    // Stable across solves (bind offsets are locked).")
    L.append("    std::vector<MMatrix> bindWorld(numJoints);")
    L.append("    { MMatrix pw = rootParentWorld;")
    L.append("      for (int j = 0; j < numJoints; ++j) {")
    L.append("          bindWorld[j] = jointLocal[j] * bindOffsets[j] * pw; pw = bindWorld[j]; } }")
    L.append("")
    L.append("    std::vector<MVector> jointPos(numJoints);")
    L.append("    for (int j = 0; j < numJoints; ++j)")
    L.append("        jointPos[j] = MVector(bindWorld[j](3,0), bindWorld[j](3,1), bindWorld[j](3,2));")
    L.append("")
    L.append("    // End effector = IK handle world position (the user's target).")
    L.append("    MVector endEffector(0,0,0);")
    L.append("    { MDagPath hp; MFnDagNode(handleObj).getPath(hp);")
    L.append("      MMatrix hm = hp.inclusiveMatrix();")
    L.append("      endEffector = MVector(hm(3,0), hm(3,1), hm(3,2)); }")
    L.append("")
    L.append("    // Pole vector + twist from the handle's plugs.")
    L.append("    MVector poleVector(0,0,0); double twist = 0.0;")
    L.append("    { MFnDependencyNode hfn(handleObj); MStatus ps;")
    L.append('      MPlug a = hfn.findPlug("poleVectorX", false, &ps); if (ps) poleVector.x = a.asDouble();')
    L.append('      MPlug b = hfn.findPlug("poleVectorY", false, &ps); if (ps) poleVector.y = b.asDouble();')
    L.append('      MPlug cc= hfn.findPlug("poleVectorZ", false, &ps); if (ps) poleVector.z = cc.asDouble();')
    L.append('      MPlug t = hfn.findPlug("twist", false, &ps);       if (ps) twist = t.asDouble(); }')
    L.append("")
    if scalars or meshes:
        L.append("    // --- user INPUT attrs (read from THIS solver node) ---")
        L.append("    MFnDependencyNode _self(thisMObject());")
        for s in scalars:
            t, ident = s["type"], s["ident"]
            ct = _IK_CTYPE[t]
            dv = _ik_default(t, s["default_value"], s["enum_names"])
            L.append("    %s in_%s = %s;" % (ct, ident, dv))
            L.append('    { MStatus _ms; MPlug _p = _self.findPlug("%s", false, &_ms);'
                     % s["plug"])
            L.append("      if (_ms == MS::kSuccess && !_p.isNull()) in_%s = _p.%s(); }"
                     % (ident, _IK_READ_ACC[t]))
            if t == "enum":
                names = ", ".join('"%s"' % n for n in s["enum_names"])
                L.append("    static const char* _names_%s[] = {%s};"
                         % (ident, names if names else '""'))
                L.append('    std::string in_%s_name = (in_%s >= 0 && in_%s < %d) ? '
                         '_names_%s[in_%s] : std::string();'
                         % (ident, ident, ident, max(1, len(s["enum_names"])),
                            ident, ident))
        for m in meshes:
            ident = m["ident"]
            L.append("    RegionMesh %s;" % ident)
            L.append('    { MStatus _ms; MPlug _p = _self.findPlug("%s", false, &_ms);'
                     % m["plug"])
            L.append("      if (_ms == MS::kSuccess && !_p.isNull()) {")
            L.append("          MObject _mo = _p.asMObject();")
            L.append("          if (!_mo.isNull() && _mo.hasFn(MFn::kMesh)) {")
            L.append("              MFnMesh _fm(_mo);")
            L.append("              MPointArray _pa; _fm.getPoints(_pa, MSpace::kWorld);")
            L.append("              for (unsigned _i=0;_i<_pa.length();++_i) %s.pts.push_back(_pa[_i]);" % ident)
            L.append("              MIntArray _vc,_vi; _fm.getVertices(_vc,_vi);")
            L.append("              for (unsigned _i=0;_i<_vc.length();++_i) %s.counts.push_back(_vc[_i]);" % ident)
            L.append("              for (unsigned _i=0;_i<_vi.length();++_i) %s.connects.push_back(_vi[_i]);" % ident)
            L.append("              MFloatVectorArray _nr; _fm.getVertexNormals(false,_nr,MSpace::kWorld);")
            L.append("              for (unsigned _i=0;_i<_nr.length();++_i) %s.normals.push_back(MVector(_nr[_i].x,_nr[_i].y,_nr[_i].z));" % ident)
            L.append("              %s.present = true;" % ident)
            L.append("          } } }")
        L.append("")
    if generics:
        L.append("    // --- generic INPUT attrs (findPlug read into in_a<ident>) ---")
        L.append("    MFnDependencyNode _selfg(thisMObject());")
        for gm in generics:
            _t, _arr = gm["meta"]["type"], gm["meta"].get("is_array")
            _geo = emit_geo_io.is_geo(_t)
            if _geo:
                L += emit_geo_io.geo_plug_decls(gm)
            elif _arr:
                L.append(_read_plug_array_decl(gm))
            else:
                L.append(_read_plug_decl(gm))
            L.append('    { MStatus _ms; MPlug _p = _selfg.findPlug("%s", false, &_ms);'
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
            L.append("    (void)in_%s;" % gm["member"])
        L.append("")
    # Emitted AFTER the generic reads (the load takes the path local one of them
    # just declared) and BEFORE the solve, so both the lowered and the ported
    # body see _imgPixels.
    if img_read:
        L += _image_read_lines(generics)
        L.append("")
    L.append("    // Per-joint desired matrices. LOCAL (parent-relative) go in")
    L.append("    // outLocalMat[j] (default = rest parent-relative); WORLD (absolute)")
    L.append("    // go in outWorldMat[j] (default = rest world). Set the matching")
    L.append("    // *Set[j]=1 to DRIVE joint j; the fixed writeback below dispatches")
    L.append("    // WORLD > LOCAL > restore-bind, applying via offsetParentMatrix with")
    L.append("    // per-joint gating, leaving the joint's own channels + jointOrient intact.")
    L.append("    std::vector<MMatrix> outLocalMat(numJoints);")
    L.append("    for (int j = 0; j < numJoints; ++j) outLocalMat[j] = jointLocal[j] * bindOffsets[j];")
    L.append("    std::vector<char>    outLocalSet(numJoints, 0);")
    L.append("    std::vector<MMatrix> outWorldMat = bindWorld;")
    L.append("    std::vector<char>    outWorldSet(numJoints, 0);")
    L.append("    // Per-joint channel gates (default: rotate only). Set an element to")
    L.append("    // gate individual joints, or fill the whole vector to broadcast.")
    L.append("    std::vector<char> applyRotate(numJoints, 1), applyTranslate(numJoints, 0), applyScale(numJoints, 0);")
    L.append("    (void)effectorPath; (void)poleVector; (void)twist;")
    L.append("")
    if iksolver_lowered is not None:
        L.append("    // --- deterministic numpy->C++ lowered solve (no port) ---")
        # kFailure here skips the per-joint writeback below, so no joint is
        # moved -- the same nothing-applied outcome the interpreted solver has
        # when its expression raises.
        L += lowered_guard(type_name, iksolver_lowered,
                           ["return MS::kFailure;"])
    else:
        L.append("    " + PORT_BEGIN)
        L.append("    // For each DRIVEN joint j set EITHER outWorldSet[j]=1 + outWorldMat[j]")
        L.append("    // (a WORLD / absolute row-vector Maya MMatrix; mirrors")
        L.append("    // self.world_matrices[j]) OR outLocalSet[j]=1 + outLocalMat[j]")
        L.append("    // (a LOCAL / parent-relative MMatrix; mirrors self.local_matrices[j]).")
        L.append("    // Leave both 0 to leave joint j at its rest offset. Available inputs:")
        L.append("    //   numJoints, bindWorld[j] (rest WORLD MMatrix), jointLocal[j] (rest")
        L.append("    //   LOCAL MMatrix), jointPos[j] (MVector), endEffector (MVector),")
        L.append("    //   poleVector (MVector), twist (double).")
        L.append("    // Gate per joint: applyRotate[j]/applyTranslate[j]/applyScale[j] (char")
        L.append("    // 0/1; default rotate-only). To broadcast a scalar Python gate, set")
        L.append("    // every element. MMatrix indexing is m(row,col); rows 0..2 are the")
        L.append("    // basis axes, row 3 is the translation.")
        if scalars:
            L.append("    // User inputs: %s"
                     % ", ".join("in_%s" % s["ident"] for s in scalars))
        for gm in generics:
            L.append("    //   self.%s -> in_%s (%s)"
                     % (gm["plug"], gm["member"],
                        findplug_local_hint(
                            gm, _ik_generic_local_hint(gm["meta"]["type"]))))
        if img_read:
            L += _image_read_hint_lines(generics)
        if meshes:
            L.append("    // Floor MESH (world space): %s (RegionMesh; .present, .pts, .normals)."
                     % ", ".join(m["ident"] for m in meshes))
            L.append("    //   int v = rm_closestVertex(%s, pt); MVector nrm = rm_normalAt(%s, v);"
                     % (meshes[0]["ident"], meshes[0]["ident"]))
        L.append("    " + PORT_END)
    L.append("")
    L.append("    // Writeback: per joint WORLD > LOCAL > restore-bind, gate-mix +")
    L.append("    // offsetParentMatrix, threading each joint's parent world in C++ (the")
    L.append("    // DAG has not propagated our fresh offsets mid-solve, so a read-back")
    L.append("    // would use the parent's pre-update world). Mirrors _apply_joint_solve.")
    L.append("    { MMatrix parentWorld = rootParentWorld; bool warned = false;")
    L.append("      for (int j = 0; j < numJoints; ++j) {")
    L.append("          MMatrix Ml = jointLocal[j], Ob = bindOffsets[j];")
    L.append("          bool gr = applyRotate[j], gt = applyTranslate[j], gs = applyScale[j];")
    L.append("          if (outWorldSet[j]) {")
    L.append("              if (outLocalSet[j] && !warned) { warned = true;")
    L.append('                  MGlobal::displayWarning("mPyIkSolver: joint has both a local and world matrix set; using world."); }')
    L.append("              MMatrix restWorld = Ml * Ob * parentWorld;")
    L.append("              MMatrix wmixed = nd_ik_gate_mix(restWorld, outWorldMat[j], gr, gt, gs);")
    L.append("              MMatrix offset = Ml.inverse() * wmixed * parentWorld.inverse();")
    L.append("              nd_ik_set_offset(jointPaths[j], offset);")
    L.append("              parentWorld = wmixed;")
    L.append("          } else if (outLocalSet[j]) {")
    L.append("              MMatrix restPR = Ml * Ob;")
    L.append("              MMatrix lmixed = nd_ik_gate_mix(restPR, outLocalMat[j], gr, gt, gs);")
    L.append("              MMatrix offset = Ml.inverse() * lmixed;")
    L.append("              nd_ik_set_offset(jointPaths[j], offset);")
    L.append("              parentWorld = lmixed * parentWorld;")
    L.append("          } else {")
    L.append("              nd_ik_set_offset(jointPaths[j], Ob);")
    L.append("              parentWorld = Ml * Ob * parentWorld;")
    L.append("          }")
    L.append("      } }")
    L.append("    return MS::kSuccess;")
    L.append("}")
    L.append("")
    L.append("MStatus initializePlugin(MObject obj) {")
    L.append('    MFnPlugin plugin(obj, "mpynode-native", "1.0", "Any");')
    if cmd_out["classes"]:
        L.append('    MStatus st = plugin.registerNode("%s", %s::id, %s::creator,'
                 % (type_name, cls, cls))
        L.append("                                     %s::initialize, MPxNode::kIkSolverNode);"
                 % cls)
        L.append("    if (!st) return st;")
        for reg in cmd_out["register"]:
            L.append("    " + reg)
        L.append("    return st;")
    else:
        L.append('    return plugin.registerNode("%s", %s::id, %s::creator,'
                 % (type_name, cls, cls))
        L.append("                               %s::initialize, MPxNode::kIkSolverNode);"
                 % cls)
    L.append("}")
    L.append("MStatus uninitializePlugin(MObject obj) {")
    L.append("    MFnPlugin plugin(obj);")
    for dereg in cmd_out["deregister"]:
        L.append("    " + dereg)
    L.append("    return plugin.deregisterNode(%s::id);" % cls)
    L.append("}")
    L.append("")
    return "\n".join(L)
