"""MPxTransform + MPxTransformationMatrix emission (FLUSH-FREE re-arch).

Mirror of the interpreted flush-free ``mPyTransform`` (``_api1/mpy_transform.py``):

  * the paired ``MPxTransformationMatrix::asMatrix()`` returns the PLAIN default
    TRS matrix -- the expression NO LONGER runs there (authoring the local matrix
    from asMatrix froze descendant DAG world caches and needed a per-frame
    timeChanged flush hack);
  * the expression's desired LOCAL matrix ``D`` is produced by ``desiredLocal()``
    (the deterministically-lowered math, or the AI-porter PORT region);
  * ``compute()`` authors ``opm = inv(L) * D`` (row-major) into a hidden
    ``_outLocalFlat`` double[16] array output, so ``world = matrix x opm x parent
    == D x parent`` -- delivered through a genuine input plug so descendants +
    world caches track natively (no flush);
  * a paired stock ``fourByFourMatrix`` relay rebuilds ``_outLocalFlat`` into a
    matrix wired to ``offsetParentMatrix``; it is auto-created per node by an
    emitted ``nodeAdded`` callback (+ kAfterOpen/kAfterImport sweeps), so a bare
    ``createNode`` just works -- exactly like the interpreted ``ensure_opm_relay``;
  * ``compute()`` pulls its matrix inputs THROUGH the datablock (cleans them so
    Maya re-dirties on the next change -- the freeze fix). The node NEVER reads
    its own DAG parent: WORLD placement is opt-in via a declared matrix input
    (``self.local_matrix = world @ inv(parent)``), so there is no imperative
    parent read to go stale and no feedback loop.

Only the matrix MATH (``desiredLocal``'s body, between the PORT markers) is filled
by the AI porter when the compute does not deterministically lower.
"""
from __future__ import annotations

import re

from .spec_model import PORT_BEGIN, PORT_END, lowered_guard
from .nd_runtime import _nd_runtime_cpp
from mpynode.native.compiler.kernels import nd_io_cpp
from .emit_attr import (_create_lines, _read_plug_decl, _read_plug_assign,
                        _read_plug_array_decl, _read_plug_array_assign,
                        findplug_family_extras, findplug_local_hint)
from . import emit_geo_io


_TRANSFORM_BASE = "MPxTransform"

# Every user INPUT except a SCALAR matrix (bespoke -- see
# _transform_matrix_inputs) is wired into desiredLocal() via findPlug and read
# into an ``in_a<ident>`` local, then either bound by nd_lower._materialise_input
# when the compute lowers or handed to the AI-porter PORT region.

# Base headers every emitted transform needs. ALL transforms carry the opm
# scaffold (custom array output + compute + dirty override + relay callbacks),
# so the header set is not gated on whether the node declares matrix inputs.
_TRANSFORM_INCLUDES = [
    "cmath", "random", "cstdint",
    "maya/MPxTransform.h", "maya/MPxTransformationMatrix.h",
    "maya/MFnPlugin.h", "maya/MTypeId.h",
    "maya/MMatrix.h", "maya/MVector.h", "maya/MEulerRotation.h",
    "maya/MQuaternion.h", "maya/MStatus.h", "maya/MGlobal.h",
    "maya/MAngle.h", "maya/MTime.h",
    # attr creation + plug/datablock IO for _outLocalFlat + matrix inputs +
    # the generic scalar inputs (numeric / unit / enum / compound / typed).
    "maya/MPxNode.h", "maya/MFnMatrixAttribute.h", "maya/MFnMatrixData.h",
    "maya/MFnNumericAttribute.h", "maya/MFnNumericData.h",
    "maya/MFnUnitAttribute.h", "maya/MFnCompoundAttribute.h",
    "maya/MFnEnumAttribute.h", "maya/MFnTypedAttribute.h", "maya/MFnData.h",
    "maya/MFnAttribute.h", "maya/MFnDependencyNode.h",
    "maya/MPlug.h", "maya/MPlugArray.h",
    "maya/MDataBlock.h", "maya/MDataHandle.h",
    "maya/MArrayDataHandle.h", "maya/MArrayDataBuilder.h",
    "maya/MFileIO.h", "maya/MString.h", "maya/MStringArray.h", "maya/MObject.h",
    # relay auto-wiring callbacks.
    "maya/MMessage.h", "maya/MDGMessage.h", "maya/MSceneMessage.h",
]

# Built-in transform channels the lowered/ported math may read; a change to any
# must re-dirty the opm output (mirrors the interpreted node's
# _BUILTIN_MATRIX_INPUT_NAMES). ``parentMatrix`` is intentionally absent -- the
# node never reads its DAG parent (WORLD placement is opt-in via a connected
# matrix input), so an ancestor move carries the node natively without a re-eval.
_BUILTIN_TRIGGER_NAMES = (
    "translate", "rotate", "scale", "shear", "rotateOrder",
)

# Hidden double[16] array output carrying the desired offsetParentMatrix.
_OPM_FLAT_ATTR = "_outLocalFlat"
_OPM_FLAT_ATTR_SHORT = "_olf"

# Gate-mix helper for the gated dual-matrix contract: take rotation / translate /
# scale of `wt` where the matching gate is true, else keep it from `wb`. Rotation
# & scale are split by the upper-3x3 row norms (assumes negligible shear). Mirrors
# the interpreted _gate_mix_world (_api1/helpers.py) byte-for-byte, and
# emit_iksolver's version.
_TRANSFORM_MATRIX_HELPERS = r"""
static MMatrix nd_gate_mix(const MMatrix& wb, const MMatrix& wt,
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
"""


def _ident(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_]", "_", str(name))
    if not s or not (s[0].isalpha() or s[0] == "_"):
        s = "a_" + s
    return s


def _transform_matrix_inputs(spec: dict):
    """[(plug, cpp_local)] for each scalar MATRIX input the transform declares --
    e.g. aim's matrix0/matrix1. The local name mirrors nd_lower._transform_in_
    local (``matrix0`` -> ``in_aMatrix0``) so the lowered ``desiredLocal`` body
    binds to the same identifiers this scaffold reads the plugs into."""
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        if meta.get("type") == "matrix" and not meta.get("is_array"):
            ident = _ident(plug)
            out.append((plug, "in_a" + ident[:1].upper() + ident[1:]))
    return out


def _transform_generic_inputs(spec: dict):
    """member dicts for each non-matrix, non-array user INPUT wired via findPlug.

    Each dict is the canonical ``m`` shape (plug/member/meta/kind) so it feeds
    emit_attr._create_lines (plug creation), _read_plug_decl/_read_plug_assign
    (the findPlug read into ``in_a<ident>``), and nd_lower._materialise_input
    (the deterministic bind) unchanged. ``member`` is ``a<ident>`` -- the static
    MObject is ``a<ident>`` (collision-safe on MPxTransform's method surface,
    matching the matrix path's ``a_<ident>`` scheme) and the read local is
    ``in_a<ident>``."""
    out = []
    for plug, meta in (spec.get("inputs") or {}).items():
        if meta.get("type") == "matrix" and not meta.get("is_array"):
            continue  # bespoke SCALAR matrix path (_transform_matrix_inputs)
        out.append({"plug": plug, "member": "a_" + _ident(plug),
                    "meta": meta, "kind": "inputs"})
    return out


def _generic_local_hint(t):
    """Human-readable C++ shape of a generic input's ``in_a<ident>`` local, for
    the AI-porter comment block."""
    return {
        "float": "double", "double": "double", "int": "int", "bool": "bool",
        "enum": "short", "angle": "double, RADIANS", "time": "double, seconds",
        "vector": "double[3]; .x==[0]", "euler": "double[3], RADIANS",
        "color": "float[3] RGB", "float2": "float[2]",
        "quaternion": "double[4] {x,y,z,w}", "string": "MString; .asChar()",
    }.get(t, t)


def _matrix_type_id(type_id: str) -> str:
    """Derive a distinct MTypeId for the paired transformation matrix."""
    try:
        return "0x%08x" % (int(str(type_id), 16) + 1)
    except Exception:
        return type_id + " + 1"


def _desired_local_body(cls, mcls, matrix_inputs, generic_inputs,
                        transform_lowered, spec, for_port):
    """Out-of-line ``<mcls>::desiredLocal()`` -- produce the expression's desired
    LOCAL matrix ``D`` under the GATED LOCAL-MATRIX contract (mirrors mPyIkSolver,
    single joint, bind offset == identity). Sets up the read locals (declared
    matrix inputs) + the gated sinks (``local_matrix`` MMatrix + ``local_set``
    flag + ``apply_*`` bools), runs the lowered/ported math (which writes those
    sinks), then dispatches LOCAL > no-op via ``nd_gate_mix`` and returns ``D``.
    ``compute()`` turns ``D`` into ``opm = inv(L) * D``. The node never reads its
    DAG parent -- WORLD placement is opt-in via a connected matrix input
    (``local_matrix = world @ inv(parent)``)."""
    L = []
    L.append("MMatrix %s::desiredLocal() const {" % mcls)
    L.append("    // L = the plain default TRS matrix; the base for un-gated")
    L.append("    // channels (bind offset == identity, so the rest IS the live TRS).")
    L.append("    MMatrix m = MPxTransformationMatrix::asMatrix();")
    L.append("    // This node's own live channels -> self.translate / rotate")
    L.append("    // (RADIANS) / scale / shear / rotate_order (see nd_lower).")
    L.append("    MVector        t = translation(MSpace::kTransform);")
    L.append("    MEulerRotation r = eulerRotation(MSpace::kTransform);")
    L.append("    MVector        sc = scale(MSpace::kTransform);")
    L.append("    MVector        shr = shear(MSpace::kTransform);")
    L.append("    // rotationOrder() is 1-based (kXYZ==1); offset to the 0-based")
    L.append("    // .rotateOrder plug enum so self.rotate_order matches interp.")
    L.append("    int            ro = (int)rotationOrder() - 1;")
    L.append("    (void)t; (void)r; (void)sc; (void)shr; (void)ro;")
    # Declared matrix inputs into the locals the lowered body binds to (e.g.
    # aim's matrix0/matrix1, or a connected parentWorld for world->local). Read
    # is deferred during scene read (plugs not yet restored) / before the
    # back-ref is synced -- return the plain TRS, Maya recomputes once whole.
    for _plug, local in matrix_inputs:
        L.append("    MMatrix %s;" % local)
    # Generic scalar inputs (float/vector/euler/color/quaternion/float2/angle/
    # time/enum/string) into their ``in_a<ident>`` locals (defaulted; assigned
    # inside the same plug-valid guard as the matrix inputs).
    for gm in generic_inputs:
        _t, _arr = gm["meta"]["type"], gm["meta"].get("is_array")
        if emit_geo_io.is_geo(_t):
            L += emit_geo_io.geo_plug_decls(gm)
        elif _arr:
            L.append(_read_plug_array_decl(gm))
        else:
            L.append(_read_plug_decl(gm))
    if matrix_inputs or generic_inputs:
        L.append("    if (!fNode.isNull() && !MFileIO::isReadingFile()) {")
        L.append("        MStatus _st;")
        L.append("        MFnDependencyNode _fn(fNode);")
        for plug, local in matrix_inputs:
            L.append('        { MPlug _p = _fn.findPlug("%s", false, &_st);' % plug)
            L.append("          if (_st) { MObject _o;")
            L.append("            if (_p.getValue(_o) == MS::kSuccess && "
                     "!_o.isNull())")
            L.append("              %s = MFnMatrixData(_o).matrix(); } }" % local)
        for gm in generic_inputs:
            _t, _arr = gm["meta"]["type"], gm["meta"].get("is_array")
            _geo = emit_geo_io.is_geo(_t)
            L.append('        { MPlug _p = _fn.findPlug("%s", false, &_st);'
                     % gm["plug"])
            L.append("          if (_st) {")
            if _geo and _arr:
                L += emit_geo_io.geo_plug_array_input_lines(gm, "_p")
            elif _geo:
                L += emit_geo_io.geo_plug_input_lines(gm, "_p")
            elif _arr:
                L += _read_plug_array_assign(gm, "_p")
            else:
                L.append(_read_plug_assign(gm, "_p"))
            L.append("          } }")
        L.append("    }")
    for _plug, local in matrix_inputs:
        L.append("    (void)%s;" % local)
    for gm in generic_inputs:
        L.append("    (void)in_%s;" % gm["member"])
    # The gated sinks the lowered/ported math writes (defaults = no-op).
    L.append("    // Gated local-matrix sinks (defaults => a plain transform: no")
    L.append("    // matrix set, so the dispatch below is a no-op regardless of")
    L.append("    // the gates). Gates default TRUE so setting local_matrix drives")
    L.append("    // ALL channels; the expression closes a gate to keep it live.")
    L.append("    MMatrix local_matrix;")
    L.append("    bool local_set = false;")
    L.append("    bool apply_rotate = true, apply_translate = true, "
             "apply_scale = true;")
    if transform_lowered is not None:
        L.append("    // --- deterministic numpy->C++ lowered transform (no port) ---")
        # desiredLocal() returns a matrix, not an MStatus, so "abandon the
        # evaluation" is returning `m` -- the plain TRS, which is what the
        # interpreted transform leaves behind when its expression raises.
        L += lowered_guard(spec["suggested"]["node_type_name"],
                           transform_lowered, ["return m;"])
    else:
        L.append("    " + PORT_BEGIN)
        if for_port:
            L.append("    // Gated dual-matrix contract. Write the desired matrix +")
            L.append("    // gates into these locals; the scaffold dispatches WORLD >")
            L.append("    // LOCAL > no-op and returns the desired local D.")
            L.append("    // Map the Python contract:")
            L.append("    //   self.translate     -> t (MVector; t.x/t.y/t.z)")
            L.append("    //   self.rotate        -> r (MEulerRotation, RADIANS; "
                     "r.x/r.y/r.z)")
            L.append("    //   self.scale         -> sc (MVector; sc.x/sc.y/sc.z)")
            L.append("    //   self.shear         -> shr (MVector; shr.x/shr.y/shr.z)")
            L.append("    //   self.rotate_order  -> ro (int, 0-based like "
                     ".rotateOrder)")
            for plug, local in matrix_inputs:
                L.append("    //   self.%s        -> %s (an MMatrix; m[i,j]==%s(i,j))"
                         % (plug, local, local))
            for gm in generic_inputs:
                L.append("    //   self.%s        -> in_%s (%s)"
                         % (gm["plug"], gm["member"],
                            findplug_local_hint(
                                gm, _generic_local_hint(gm["meta"]["type"]))))
            L.append("    //   self.local_matrix = X   -> local_matrix (X, MMatrix); "
                     "local_set = true;")
            L.append("    //   self.apply_rotate = b   -> apply_rotate = b;   "
                     "(likewise apply_translate / apply_scale)")
            L.append("    // Un-gated channels fall back to the live TRS (m). Set")
            L.append("    // local_matrix + open at least one gate to drive the node.")
            L.append("    // For WORLD placement read a connected parent matrix input")
            L.append("    // and set local_matrix = worldDesired * parent.inverse().")
            L.append("    // Reproduce numpy with std::sin/cos etc. Pure math only.")
            L.append("    // Original Python compute (translate faithfully):")
            for src_line in (spec.get("compute") or "").splitlines():
                L.append("    //   | %s" % src_line)
        else:
            L.append("    // TODO: write local_matrix + apply_* below.")
            for src_line in (spec.get("compute") or "").splitlines():
                L.append("    //   | %s" % src_line)
        L.append("    " + PORT_END)
    # Dispatch: LOCAL > no-op (mirrors mPyIkSolver, single joint, bind==identity).
    L.append("    // Dispatch: local_matrix > no-op; every gate closed OR nothing")
    L.append("    // set => identity opm (D = L, plain transform).")
    L.append("    bool any_gate = apply_rotate || apply_translate || apply_scale;")
    L.append("    if (!local_set || !any_gate) return m;")
    L.append("    return nd_gate_mix(m, local_matrix, apply_rotate, "
             "apply_translate, apply_scale);")
    L.append("}")
    return L


def _transform_node_methods(cls, mcls, type_name, matrix_inputs, generic_inputs):
    """Out-of-line MPxTransform method definitions: initialize() (matrix + generic
    scalar inputs + the _outLocalFlat opm output), _syncNode/postConstructor
    (back-ref), compute() (author opm = inv(L) * D), and setDependentsDirty()
    (dirty the opm output's element plugs on any expression input change)."""
    L = []
    # ---- static attr definitions --------------------------------------------
    L.append("MObject %s::aOutLocalFlat;" % cls)
    for plug, _local in matrix_inputs:
        L.append("MObject %s::a_%s;" % (cls, _ident(plug)))
    for gm in generic_inputs:
        L.append("MObject %s::%s;" % (cls, gm["member"]))
    L.append("")
    # ---- initialize() -------------------------------------------------------
    L.append("MStatus %s::initialize() {" % cls)
    L.append("    MStatus st;")
    L.append("    MFnNumericAttribute nAttr;")
    if generic_inputs:
        L.append("    MFnUnitAttribute     uAttr;")
        L.append("    MFnCompoundAttribute cAttr;")
        L.append("    MFnEnumAttribute     eAttr;")
        L.append("    MFnTypedAttribute    tAttr;")
    # mAttr serves the bespoke SCALAR matrix path below AND a matrix ARRAY, which
    # rides the generic path (_create_lines emits mAttr.create for it).
    if matrix_inputs or any(gm["meta"]["type"] == "matrix"
                            for gm in generic_inputs):
        L.append("    MFnMatrixAttribute mAttr;")
        for plug, _local in matrix_inputs:
            obj = "a_%s" % _ident(plug)
            L.append("    %s = mAttr.create(\"%s\", \"%s\", "
                     "MFnMatrixAttribute::kDouble, &st);" % (obj, plug, plug))
            L.append("    if (!st) return st;")
            L.append("    mAttr.setStorable(true); mAttr.setWritable(true);")
            L.append("    mAttr.setReadable(true); mAttr.setConnectable(true);")
            L.append("    mAttr.setKeyable(false);")
            L.append("    st = %s::addAttribute(%s); if (!st) return st;"
                     % (cls, obj))
    # Generic scalar inputs: create via the shared emit_attr._create_lines (same
    # plug construction the plain-node scaffold uses) so a connected/AE value is
    # available to desiredLocal's findPlug read.
    for gm in generic_inputs:
        L += _create_lines(gm)
        L.append("    st = %s::addAttribute(%s); if (!st) return st;"
                 % (cls, gm["member"]))
    # Hidden double[16] opm carrier (matrix output from MPxTransform.compute
    # segfaults; a double[] array does not -- same reason as the interpreted node).
    L.append("    aOutLocalFlat = nAttr.create(\"%s\", \"%s\", "
             "MFnNumericData::kDouble, 0.0, &st);"
             % (_OPM_FLAT_ATTR, _OPM_FLAT_ATTR_SHORT))
    L.append("    if (!st) return st;")
    L.append("    nAttr.setArray(true); nAttr.setUsesArrayDataBuilder(true);")
    L.append("    nAttr.setWritable(false); nAttr.setStorable(false);")
    L.append("    nAttr.setReadable(true); nAttr.setHidden(true);")
    L.append("    st = %s::addAttribute(aOutLocalFlat); if (!st) return st;"
             % cls)
    for plug, _local in matrix_inputs:
        L.append("    %s::attributeAffects(a_%s, aOutLocalFlat);"
                 % (cls, _ident(plug)))
    for gm in generic_inputs:
        L.append("    %s::attributeAffects(%s, aOutLocalFlat);"
                 % (cls, gm["member"]))
    L.append("    return MS::kSuccess;")
    L.append("}")
    L.append("")
    # ---- _syncNode / postConstructor ----------------------------------------
    L.append("void %s::_syncNode() {" % cls)
    L.append("    %s* mtx = dynamic_cast<%s*>(transformationMatrixPtr());"
             % (mcls, mcls))
    L.append("    if (mtx) mtx->fNode = thisMObject();")
    L.append("}")
    L.append("")
    L.append("void %s::postConstructor() {" % cls)
    L.append("    MPxTransform::postConstructor();")
    L.append("    _syncNode();")
    L.append("}")
    L.append("")
    # ---- compute(): author opm = inv(L) * D into _outLocalFlat ---------------
    L.append("MStatus %s::compute(const MPlug& plug, MDataBlock& data) {" % cls)
    L.append("    _syncNode();")
    L.append("    bool isFlat = (plug.attribute() == aOutLocalFlat);")
    L.append("    if (!isFlat && plug.isElement()) {")
    L.append("        isFlat = (plug.array().attribute() == aOutLocalFlat);")
    L.append("    }")
    L.append("    if (!isFlat) return MPxTransform::compute(plug, data);")
    L.append("    // FREEZE FIX: pull the matrix inputs THROUGH the datablock so")
    L.append("    // Maya marks them clean and re-dirties on the next change (an")
    L.append("    // input never pulled here stays perpetually dirty and Maya then")
    L.append("    // skips setDependentsDirty for it -- freezing after frame 1).")
    for plug, _local in matrix_inputs:
        L.append("    { MStatus _s; data.inputValue(a_%s, &_s); }" % _ident(plug))
    for gm in generic_inputs:
        L.append("    { MStatus _s; data.inputValue(%s, &_s); }" % gm["member"])
    L.append("    %s* mtx = dynamic_cast<%s*>(transformationMatrixPtr());"
             % (mcls, mcls))
    L.append("    MMatrix L, D;")
    L.append("    if (mtx) { L = mtx->asMatrix(); D = mtx->desiredLocal(); }")
    L.append("    MMatrix opm = L.inverse() * D;  // world = L * opm * parent = D * parent")
    L.append("    MArrayDataHandle arrH = data.outputArrayValue(aOutLocalFlat);")
    L.append("    MArrayDataBuilder bld = arrH.builder();")
    L.append("    for (int i = 0; i < 16; ++i) {")
    L.append("        MDataHandle h = bld.addElement(i);")
    L.append("        h.setDouble(opm(i / 4, i % 4));  // row-major in00..in33")
    L.append("    }")
    L.append("    arrH.set(bld);")
    L.append("    data.setClean(plug);")
    L.append("    data.setClean(aOutLocalFlat);")
    L.append("    return MS::kSuccess;")
    L.append("}")
    L.append("")
    # ---- setDependentsDirty(): input change -> dirty opm element plugs -------
    L.append("MStatus %s::setDependentsDirty(const MPlug& plug, "
             "MPlugArray& affected) {" % cls)
    L.append("    MObject attr = plug.attribute();")
    L.append("    bool trig = false;")
    L.append("    if (!attr.isNull()) {")
    L.append("        MString nm = MFnAttribute(attr).name();")
    for plug, _local in matrix_inputs:
        L.append('        if (nm == "%s") trig = true;' % plug)
    for gm in generic_inputs:
        L.append('        if (nm == "%s") trig = true;' % gm["plug"])
    for nm in _BUILTIN_TRIGGER_NAMES:
        L.append('        if (nm == "%s") trig = true;' % nm)
    # a compound child (translateX) resolves to its parent channel (translate).
    L.append("        if (!trig && plug.isChild()) {")
    L.append("            MString pn = MFnAttribute(plug.parent().attribute())"
             ".name();")
    for nm in ("translate", "rotate", "scale", "shear"):
        L.append('            if (pn == "%s") trig = true;' % nm)
    # a generic compound input's child (offsetX) resolves to its parent (offset).
    for gm in generic_inputs:
        if gm["meta"]["type"] in ("vector", "euler", "color", "quaternion",
                                  "float2"):
            L.append('            if (pn == "%s") trig = true;' % gm["plug"])
    L.append("        }")
    L.append("    }")
    L.append("    if (trig) {")
    # Append the 16 ELEMENT plugs (not just the array root): the relay reads the
    # elements; appending only the root leaves already-computed elements clean, so
    # every change after the first is silently dropped (verified in the interpreted
    # node). elementByLogicalIndex materialises the element plug.
    L.append("        MStatus _st;")
    L.append("        MFnDependencyNode _fn(thisMObject());")
    L.append("        MPlug flat = _fn.findPlug(aOutLocalFlat, false, &_st);")
    L.append("        if (_st) {")
    L.append("            affected.append(flat);")
    L.append("            for (int i = 0; i < 16; ++i) {")
    L.append("                MPlug e = flat.elementByLogicalIndex(i, &_st);")
    L.append("                if (_st) affected.append(e);")
    L.append("            }")
    L.append("        }")
    L.append("    }")
    L.append("    return MPxTransform::setDependentsDirty(plug, affected);")
    L.append("}")
    return L


def _relay_helpers(type_name):
    """File-scope helpers that auto-wire the stock ``fourByFourMatrix`` relay
    (mirrors the interpreted ``ensure_opm_relay`` + ``register_relay_callbacks``).
    The relay is built via MEL (idempotent) so a bare ``createNode`` just works
    and a loaded scene's restored relay is left untouched."""
    L = []
    L.append("// ---- flush-free opm relay auto-wiring (stock fourByFourMatrix) ---")
    L.append("static MCallbackId g_ndNodeAddedCb = 0;")
    L.append("static MCallbackId g_ndAfterOpenCb = 0;")
    L.append("static MCallbackId g_ndAfterImportCb = 0;")
    L.append("")
    L.append("static void nd_ensure_opm_relay(const MString& node) {")
    L.append("    // Idempotent: skip if offsetParentMatrix already driven (a")
    L.append("    // restored relay or a prior call). MEL loop avoids C++ int")
    L.append("    // concatenation and reuses the battle-tested createNode/")
    L.append("    // connectAttr path.")
    L.append("    MString mel =")
    L.append("        MString(\"{ string $n=\\\"\") + node + \"\\\";\\n\"")
    L.append("        \"  if (size(`listConnections -s 1 -d 0 "
             "($n+\\\".offsetParentMatrix\\\")`)==0) {\\n\"")
    L.append("        \"    if (!`pluginInfo -q -loaded matrixNodes`) "
             "loadPlugin -quiet matrixNodes;\\n\"")
    L.append("        \"    string $r=`createNode -ss fourByFourMatrix "
             "-n ($n+\\\"_opmRelay\\\")`;\\n\"")
    L.append("        \"    for ($i=0;$i<16;$i++) connectAttr -f "
             "($n+\\\"._outLocalFlat[\\\"+$i+\\\"]\\\") "
             "($r+\\\".in\\\"+($i/4)+($i%4));\\n\"")
    L.append("        \"    connectAttr -f ($r+\\\".output\\\") "
             "($n+\\\".offsetParentMatrix\\\");\\n\"")
    L.append("        \"  } }\";")
    L.append("    MGlobal::executeCommand(mel);")
    L.append("}")
    L.append("")
    L.append("static void nd_on_node_added(MObject& node, void*) {")
    L.append("    if (MFileIO::isReadingFile()) return;  // saved scenes carry it")
    L.append("    MStatus st; MFnDependencyNode fn(node, &st);")
    L.append("    if (!st) return;")
    L.append("    nd_ensure_opm_relay(fn.name());")
    L.append("}")
    L.append("")
    L.append("static void nd_sweep_relays(void*) {")
    L.append("    MStringArray nodes;")
    L.append("    MGlobal::executeCommand(\"ls -type %s\", nodes);" % type_name)
    L.append("    for (unsigned i = 0; i < nodes.length(); ++i)")
    L.append("        nd_ensure_opm_relay(nodes[i]);")
    L.append("}")
    return L


def _generate_transform_cpp(spec: dict, for_port: bool = False) -> str:
    """Emit a native MPxTransform + MPxTransformationMatrix plugin in the
    flush-free form (see the module docstring). Only the matrix MATH (between the
    PORT markers, inside ``desiredLocal``) is AI-filled when the compute does not
    deterministically lower.
    """
    sg = spec["suggested"]
    cls = sg["class_name"]
    mcls = cls + "Matrix"
    type_name = sg["node_type_name"]
    type_id = sg["type_id"]
    matrix_id = _matrix_type_id(type_id)

    matrix_inputs = _transform_matrix_inputs(spec)
    generic_inputs = _transform_generic_inputs(spec)

    # Deterministic numpy->C++ lowering of the expression math. If the whole
    # compute lowers, the PORT region is replaced by the transpiled body and
    # nd_runtime.h is inlined; otherwise None -> the AI-porter PORT region is
    # kept. Lazy import breaks the codegen<->nd_lower cycle.
    from mpynode.native.compiler import nd_lower
    transform_lowered = nd_lower.try_lower_transform(spec)
    nd_io_cpp.reject_unlowered_io(spec, transform_lowered, "transform")

    from mpynode.native.compiler.kernels import command_dispatch
    cmd_out = command_dispatch.dispatch_for_spec(spec, type_name)
    if cmd_out["errors"]:
        import sys as _sys
        _sys.stderr.write("[command_dispatch] %s: %s\n"
                          % (type_name, "; ".join(cmd_out["errors"])))

    L = []
    L.append("// %s -- generated MPxTransform + MPxTransformationMatrix (codegen)."
             % type_name)
    L.append("// Source mPyNode: %s (%s)"
             % (spec.get("source_node"), spec.get("mpy_type")))
    L.append("// FLUSH-FREE: asMatrix() = plain TRS; desiredLocal() = expression")
    L.append("// D; compute() authors opm = inv(L)*D on _outLocalFlat; a stock")
    L.append("// fourByFourMatrix relay -> offsetParentMatrix (auto-wired).")
    L.append("")
    _extra_incs, _extra_blocks = findplug_family_extras(generic_inputs)
    for inc in _TRANSFORM_INCLUDES:
        L.append("#include <%s>" % inc)
    for inc in _extra_incs:                  # hex / geo machinery (if declared)
        if inc not in _TRANSFORM_INCLUDES:
            L.append("#include <%s>" % inc)
    # nd_io (ndio.read/write, np.fromfile/np.save, .tofile). Gated on the source
    # so a non-IO transform's frag stays byte-identical (port cache intact).
    if nd_io_cpp.spec_uses_ndio(spec):
        for inc in nd_io_cpp.NDIO_INCLUDES:
            if inc not in _TRANSFORM_INCLUDES and inc not in _extra_incs:
                L.append("#include <%s>" % inc)
    if cmd_out["includes"]:
        _seen_inc = set(_TRANSFORM_INCLUDES) | set(_extra_incs)
        if nd_io_cpp.spec_uses_ndio(spec):
            _seen_inc |= set(nd_io_cpp.NDIO_INCLUDES)
        for inc in cmd_out["includes"]:
            if inc in _seen_inc:
                continue
            _seen_inc.add(inc)
            L.append("#include <%s>" % inc)
    L.append("")
    if transform_lowered is not None:
        L.append(_nd_runtime_cpp())
        L.append("")
        # nd_io sits ON TOP of nd:: (every accessor returns nd::Array<T>), so it
        # must follow the runtime. Own include guard -> idempotent in a bundle.
        if nd_io_cpp.spec_uses_ndio(spec):
            L.append(nd_io_cpp.NDIO_CPP)
            L.append("")
    for blk in _extra_blocks:
        L.append(blk)
    # Gate-mix helper (used by desiredLocal's dispatch in every transform).
    L.append(_TRANSFORM_MATRIX_HELPERS)
    L.append("")

    # ---- transformation matrix (asMatrix = TRS; desiredLocal = D) ------------
    L.append("class %s : public MPxTransformationMatrix {" % mcls)
    L.append("public:")
    L.append("    %s() : MPxTransformationMatrix() {}" % mcls)
    L.append("    static void* creator() { return new %s(); }" % mcls)
    L.append("    static MTypeId id;")
    L.append("    MTypeId typeId() const override { return id; }")
    # Back-ref to the owning transform node, synced by the paired MPxTransform
    # each compute (asMatrix/desiredLocal have no thisMObject). Reading matrix
    # INPUTS + the DAG parent through it is safe -- never this node's own matrix
    # output, so no re-entrancy.
    L.append("    MObject fNode;")
    L.append("    MMatrix asMatrix() const override;   // plain default TRS")
    L.append("    MMatrix desiredLocal() const;        // expression result D")
    L.append("};")
    L.append("MTypeId %s::id(%s);" % (mcls, matrix_id))
    L.append("")
    # asMatrix(): plain TRS (the expression no longer runs here).
    L.append("MMatrix %s::asMatrix() const {" % mcls)
    L.append("    // Flush-free: return the plain TRS; the expression result rides")
    L.append("    // offsetParentMatrix (authored by the transform's compute()).")
    L.append("    return MPxTransformationMatrix::asMatrix();")
    L.append("}")
    L.append("")
    # desiredLocal(): the expression's desired local matrix D.
    L += _desired_local_body(cls, mcls, matrix_inputs, generic_inputs,
                             transform_lowered, spec, for_port)
    L.append("")

    # ---- the transform node -------------------------------------------------
    L.append("class %s : public MPxTransform {" % cls)
    L.append("public:")
    L.append("    %s() : MPxTransform() {}" % cls)
    L.append("    static void*   creator() { return new %s(); }" % cls)
    L.append("    static MTypeId id;")
    L.append("    static MObject aOutLocalFlat;")
    for plug, _local in matrix_inputs:
        L.append("    static MObject a_%s;" % _ident(plug))
    for gm in generic_inputs:
        L.append("    static MObject %s;" % gm["member"])
    L.append("    MPxTransformationMatrix* createTransformationMatrix() override {")
    L.append("        return new %s();" % mcls)
    L.append("    }")
    L.append("    static MStatus initialize();")
    L.append("    void postConstructor() override;")
    L.append("    MStatus compute(const MPlug&, MDataBlock&) override;")
    L.append("    MStatus setDependentsDirty(const MPlug&, MPlugArray&) override;")
    L.append("private:")
    L.append("    void _syncNode();")
    # Per-instance file-IO document cache + lock.
    if nd_io_cpp.spec_uses_ndio(spec):
        L.append(nd_io_cpp.NDIO_MEMBERS.rstrip("\n"))
    L.append("};")
    L.append("MTypeId %s::id(%s);" % (cls, type_id))
    L.append("")
    L += _transform_node_methods(cls, mcls, type_name, matrix_inputs,
                                 generic_inputs)
    L.append("")

    if cmd_out["classes"]:
        # The bundler namespace-wraps this region, so two nodes' command support
        # cannot collide in a merged plug-in.
        L.append("// ==== bundled commands (Methods @maya_command) ====")
        L.append(cmd_out["classes"])
        L.append("")

    # ---- relay auto-wiring helpers ------------------------------------------
    L += _relay_helpers(type_name)
    L.append("")

    # ---- registration -------------------------------------------------------
    L.append("MStatus initializePlugin(MObject obj) {")
    L.append('    MFnPlugin plugin(obj, "mpynode-native", "1.0", "Any");')
    L.append("    MStatus st;")
    L.append("    st = plugin.registerTransform(")
    L.append('        "%s", %s::id, %s::creator, %s::initialize,'
             % (type_name, cls, cls, cls))
    L.append("        %s::creator, %s::id);" % (mcls, mcls))
    L.append("    if (!st) return st;")
    for reg in cmd_out["register"]:
        L.append("    " + reg)
    L.append("    // Auto-wire the opm relay for new nodes + restored/imported")
    L.append("    // scenes (idempotent), mirroring the interpreted node.")
    L.append('    g_ndNodeAddedCb = MDGMessage::addNodeAddedCallback('
             'nd_on_node_added, "%s", NULL, &st);' % type_name)
    L.append("    g_ndAfterOpenCb = MSceneMessage::addCallback(")
    L.append("        MSceneMessage::kAfterOpen, nd_sweep_relays, NULL, &st);")
    L.append("    g_ndAfterImportCb = MSceneMessage::addCallback(")
    L.append("        MSceneMessage::kAfterImport, nd_sweep_relays, NULL, &st);")
    L.append("    return MS::kSuccess;")
    L.append("}")
    L.append("MStatus uninitializePlugin(MObject obj) {")
    L.append("    MFnPlugin plugin(obj);")
    L.append("    if (g_ndNodeAddedCb) MMessage::removeCallback(g_ndNodeAddedCb);")
    L.append("    if (g_ndAfterOpenCb) MMessage::removeCallback(g_ndAfterOpenCb);")
    L.append("    if (g_ndAfterImportCb) "
             "MMessage::removeCallback(g_ndAfterImportCb);")
    for dereg in cmd_out["deregister"]:
        L.append("    " + dereg)
    L.append("    return plugin.deregisterNode(%s::id);" % cls)
    L.append("}")
    L.append("")
    return "\n".join(L)
