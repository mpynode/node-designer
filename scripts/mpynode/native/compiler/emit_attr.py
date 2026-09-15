"""Shared attribute/IO emission foundation for all emitters."""
from __future__ import annotations

import re

from .spec_model import _CPP, _num_default
from . import emit_geo_io as _geo
from .emit_hex import _HEX_CPP as _HEX_CPP_BLOCK


_INCLUDES = [
    # std math/utilities the ported compute may use (random/cstdint back the
    # optional RNG helper; harmless when unused)
    "cmath", "algorithm", "vector", "random", "cstdint",
    # Maya core
    "maya/MPxNode.h", "maya/MFnPlugin.h", "maya/MTypeId.h",
    "maya/MFnNumericAttribute.h", "maya/MFnUnitAttribute.h",
    "maya/MFnMatrixAttribute.h", "maya/MFnEnumAttribute.h",
    "maya/MFnTypedAttribute.h", "maya/MFnCompoundAttribute.h",
    "maya/MFnNumericData.h", "maya/MFnData.h",
    "maya/MAngle.h", "maya/MTime.h", "maya/MMatrix.h", "maya/MString.h",
    "maya/MVector.h", "maya/MEulerRotation.h", "maya/MQuaternion.h",
    "maya/MFloatVector.h",
    "maya/MDataBlock.h", "maya/MDataHandle.h", "maya/MArrayDataHandle.h",
    "maya/MArrayDataBuilder.h", "maya/MPlug.h", "maya/MStatus.h",
]

# Headers a `packed` (typed-array) input read/create needs. NOT in _INCLUDES:
# node_scaffold appends these only when the spec actually has a packed attr, so
# every other node's frag stays byte-identical (same gating as hex/mesh/nurbs).
PACKED_INCLUDES = [
    "maya/MFnDoubleArrayData.h", "maya/MFnIntArrayData.h",
    "maya/MDoubleArray.h", "maya/MIntArray.h",
]

# `packed` array INPUT -> (MFnData enum, MFn*ArrayData class, M*Array class).
# Element type stays double/int, so _CPP and every downstream consumer of
# `std::vector<T> in_<member>` is unchanged -- only the plug KIND and the read
# differ. Mirrors _api2/helpers.py::_PACKED_DATA_KIND / _PACKED_FN.
_PACKED_DATA = {
    "double": ("kDoubleArray", "MFnDoubleArrayData", "MDoubleArray"),
    "int": ("kIntArray", "MFnIntArrayData", "MIntArray"),
}

def _ident(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_]", "_", str(name))
    if not s or not (s[0].isalpha() or s[0] == "_"):
        s = "a_" + s
    return s

def keyable_array_inputs(mpy_type):
    """The array inputs this mPy type exempts from "arrays are never keyable".

    Read from the SAME SSOT the interpreted side uses --
    ``MPyNode.KEYABLE_ARRAY_INPUTS`` on the type's wrapper class -- so a
    compiled node's channel box matches its interpreted twin instead of
    re-deciding the rule here. Maya honours ``keyable`` only at attribute
    CREATION, so a compiled node that misses the exemption cannot be repaired
    afterwards: neither ``addAttr -e -keyable`` nor ``setAttr`` on the plug
    moves the channel box, and a non-keyable multi also loses its
    default-valued elements on save/reload.
    """
    try:
        from mpynode._node_registry import get_spec
        node_spec = get_spec(mpy_type)
        if node_spec is None:
            return frozenset()
        cls = node_spec.get_wrapper_class()
    except Exception:
        return frozenset()
    return frozenset(getattr(cls, "KEYABLE_ARRAY_INPUTS", ()) or ())


def _members(spec):
    """Assign a unique C++ MObject member name to each attr plug."""
    out = []
    seen = set()
    keyable_arrays = keyable_array_inputs(spec.get("mpy_type"))
    for kind in ("inputs", "outputs"):
        for plug, meta in (spec.get(kind) or {}).items():
            base = "a" + _ident(plug)[:1].upper() + _ident(plug)[1:]
            m = base
            i = 1
            while m in seen:
                i += 1
                m = "%s%d" % (base, i)
            seen.add(m)
            entry = {"plug": plug, "member": m, "kind": kind, "meta": meta}
            # Re-key an exempt array. node_scaffold appends ``extra_flags``
            # AFTER _create_lines, so this wins over the blanket
            # setKeyable(false) the array branch emits.
            if (kind == "inputs" and meta.get("is_array")
                    and not meta.get("packed") and plug in keyable_arrays):
                entry["extra_flags"] = [
                    "    %s.setKeyable(true);" % _fn_for(meta.get("type"))]
            out.append(entry)
    return out

def _cpp_str(s):
    """Escape a Python str for use inside a C++ double-quoted string literal."""
    return str(s).replace("\\", "\\\\").replace('"', '\\"')

def _enum_field_label_index(field, default_idx):
    """Parse a Maya listEnum field token: ``'Label'`` -> (Label, default_idx);
    ``'Label=N'`` -> (Label, N). Bad index -> (whole, default_idx)."""
    s = str(field)
    if "=" in s:
        label, _, num = s.rpartition("=")
        try:
            return label, int(num)
        except ValueError:
            return s, default_idx
    return s, default_idx

def _bool_default(meta):
    """C++ literal for a bool attr's recorded default (``addAttr dv``).

    The twin of :func:`spec_model._num_default` for the one numeric type whose
    C++ spelling is not ``repr()``. No recorded default -> ``false``, so a node
    that declares none stays byte-identical."""
    v = meta.get("default_value")
    if v is None:
        return "false"
    return "true" if v else "false"

def _color_default(meta):
    """The recorded RGB default of a colour attr as three floats, or ``None``
    when absent, malformed, or all-zero -- black is what ``createColor`` already
    gives, so emitting nothing keeps such a node byte-identical."""
    v = meta.get("default_value")
    if not isinstance(v, (list, tuple)) or len(v) < 3:
        return None
    try:
        rgb = tuple(float(x) for x in v[:3])
    except Exception:
        return None
    return rgb if any(rgb) else None

def _create_lines(m):
    """C++ lines that create + flag one attribute in initialize()."""
    plug, mem, meta = m["plug"], m["member"], m["meta"]
    t = meta["type"]
    is_out = m["kind"] == "outputs"
    L = []
    a = '"%s"' % plug
    if meta.get("packed") and t in _PACKED_DATA and not is_out:
        # ONE typed-array plug, not a multi -- returns EARLY so the setArray()
        # tail below never runs (setArray on a typed array would make it an
        # array OF arrays). The default MObject is required: a kDoubleArray attr
        # created with MObject::kNullObj has no data on a fresh node.
        kind, data_fn, _ = _PACKED_DATA[t]
        L += [
            "    {",
            "        %s _pd;" % data_fn,
            "        MObject _pdo = _pd.create();",
            "        %s = tAttr.create(%s, %s, MFnData::%s, _pdo);"
            % (mem, a, a, kind),
            "    }",
        ]
        L += _flags("tAttr", is_out, keyable=False)
        return L
    if t in ("float", "double", "int", "bool"):
        data = {"float": "kFloat", "double": "kDouble", "int": "kInt",
                "bool": "kBoolean"}[t]
        dflt = {"float": _num_default(meta, float, "0.0"),
                "double": _num_default(meta, float, "0.0"),
                "int": _num_default(meta, int, "0"),
                "bool": _bool_default(meta)}[t]
        L.append("    %s = nAttr.create(%s, %s, MFnNumericData::%s, %s);"
                  % (mem, a, a, data, dflt))
        L += _flags("nAttr", is_out)
    elif t == "vector":
        # Build the 3 children explicitly so they're named <plug>X/Y/Z
        # (matching the Python wrapper) instead of Maya's default <plug>0/1/2.
        cx, cy, cz = mem + "X", mem + "Y", mem + "Z"
        for cm, ax in ((cx, "X"), (cy, "Y"), (cz, "Z")):
            L.append('    MObject %s = nAttr.create("%s%s", "%s%s", '
                     'MFnNumericData::kDouble, 0.0);' % (cm, plug, ax, plug, ax))
        L.append("    %s = nAttr.create(%s, %s, %s, %s, %s);"
                  % (mem, a, a, cx, cy, cz))
        L += _flags("nAttr", is_out)
    elif t == "euler":
        # Like vector (double3 X/Y/Z) but the children are doubleAngle
        # (MFnUnitAttribute kAngle), matching the Python wrapper's euler and
        # Maya's own rotate. The parent stays numeric, so reads/writes and flags
        # go through nAttr like vector; values flow as radians.
        cx, cy, cz = mem + "X", mem + "Y", mem + "Z"
        for cm, ax in ((cx, "X"), (cy, "Y"), (cz, "Z")):
            L.append('    MObject %s = uAttr.create("%s%s", "%s%s", '
                     'MFnUnitAttribute::kAngle, 0.0);' % (cm, plug, ax, plug, ax))
        L.append("    %s = nAttr.create(%s, %s, %s, %s, %s);"
                  % (mem, a, a, cx, cy, cz))
        L += _flags("nAttr", is_out)
    elif t == "quaternion":
        # Generic compound of 4 doubles X/Y/Z/W (W default 1.0 = identity).
        # There is no numeric double4, so unlike vector/euler this is an
        # MFnCompoundAttribute read/written via child handles (see _read_line /
        # _out_handle_default).
        cx, cy, cz, cw = mem + "X", mem + "Y", mem + "Z", mem + "W"
        for cm, ax, dv in (
            (cx, "X", "0.0"), (cy, "Y", "0.0"),
            (cz, "Z", "0.0"), (cw, "W", "1.0"),
        ):
            L.append('    MObject %s = nAttr.create("%s%s", "%s%s", '
                     'MFnNumericData::kDouble, %s);' % (cm, plug, ax, plug, ax, dv))
        L.append("    %s = cAttr.create(%s, %s);" % (mem, a, a))
        for cm in (cx, cy, cz, cw):
            L.append("    cAttr.addChild(%s);" % cm)
        L += _flags("cAttr", is_out)
    elif t == "float2":
        # 2-float numeric compound (e.g. uvCoord); read via asFloat2(). Stays a
        # genuine float2 so it connects to place2dTexture.outUV.
        #
        # Child names come from the interface SSOT via ``children`` when it
        # declares them, else <plug>X/<plug>Y. The parent connect DOES ignore
        # child names -- but addressing a child by name does not, and mPyFile's
        # uvCoord children are uCoord/vCoord, not uvCoordX/uvCoordY. The generic
        # rule left a compiled mPyFile with no uCoord plug while the outUV
        # connect kept working, which is exactly why it went unnoticed.
        # uvFilterSize's declared children ARE <plug>X/Y, so it is unchanged.
        kids = meta.get("children") or [plug + "X", plug + "Y"]
        cx, cy = mem + "X", mem + "Y"
        for cm, cn in ((cx, kids[0]), (cy, kids[1])):
            L.append('    MObject %s = nAttr.create("%s", "%s", '
                     'MFnNumericData::kFloat, 0.0);' % (cm, cn, cn))
        L.append("    %s = nAttr.create(%s, %s, %s, %s);"
                  % (mem, a, a, cx, cy))
        L += _flags("nAttr", is_out)
    elif t == "color":
        # createColor sets usedAsColor and auto-creates R/G/B children, so the
        # attr binds to material.color + Arnold like a stock file node's outColor.
        L.append("    %s = nAttr.createColor(%s, %s);" % (mem, a, a))
        # createColor takes no default and, until 2026-09-14, none was ever
        # set: every compiled node with a colour INPUT came up (0,0,0) where
        # the Python node carried its recorded default. Mesh Maze's authored
        # test asserts on those defaults (walls wallColor, tiles solutionColor)
        # and read black off the compiled node while the Python passed;
        # Voxelize's defaultColor and Mesh Regions' six colours were wrong the
        # same way. Emitted only for a NON-ZERO recorded default (black is what
        # createColor gives anyway), so every other node stays byte-identical.
        # Float literals select the (float,float,float) overload the k3Float
        # attr createColor makes expects; double literals would bind k3Double.
        _cdv = _color_default(meta)
        if _cdv and not is_out:
            L.append("    nAttr.setDefault(%s);"
                     % ", ".join("%rf" % c for c in _cdv))
        L += _flags("nAttr", is_out)
    elif t in ("angle", "time"):
        unit = "kAngle" if t == "angle" else "kTime"
        # angle: the recorded default is honoured, in RADIANS, on both sides --
        # the MFnUnitAttribute default is internal units here, and the
        # interpreted node's `cmds.addAttr -dv` on a doubleAngle is radians
        # too (0.5 -> 28.648 deg measured on both, 2026-09-14). time: the
        # interpreted node passes NO default for a time attr (add_input_attr
        # forwards default_value for float/double/int/angle only, and a scalar
        # time plug is auto-connected to time1 anyway), so a recorded time
        # default is ignored here as well -- honouring it read 2.0 where the
        # Python node read 0.0. No shipped template records one; byte-identical.
        dflt = _num_default(meta, float, "0.0") if t == "angle" else "0.0"
        L.append("    %s = uAttr.create(%s, %s, MFnUnitAttribute::%s, %s);"
                  % (mem, a, a, unit, dflt))
        L += _flags("uAttr", is_out)
    elif t == "matrix":
        L.append("    %s = mAttr.create(%s, %s, MFnMatrixAttribute::kDouble);"
                  % (mem, a, a))
        L += _flags("mAttr", is_out, keyable=False)
    elif t == "enum":
        # 3rd arg is the default field index -- follow the recorded
        # default_value (fallback 0 keeps a no-default enum byte-identical).
        L.append("    %s = eAttr.create(%s, %s, %s);"
                  % (mem, a, a, _num_default(meta, int, "0")))
        # Field labels may be Maya/OCIO-supplied (e.g. mPyFile's colorSpace) and
        # the user can't sanitize them: C-string escape the label and honor an
        # explicit `Label=index`. A plain label is emitted byte-identically.
        _next_idx = 0
        for fld in (meta.get("enum_names") or []):
            _label, _idx = _enum_field_label_index(fld, _next_idx)
            L.append('    eAttr.addField("%s", %d);' % (_cpp_str(_label), _idx))
            _next_idx = _idx + 1
        L += _flags("eAttr", is_out)
    elif t in ("string", "hex"):
        L.append("    %s = tAttr.create(%s, %s, MFnData::kString);" % (mem, a, a))
        L += _flags("tAttr", is_out, keyable=False)
    elif t == "nurbsCurve":
        # Typed kNurbsCurve attr, read into an MFnNurbsCurve local by _read_line
        # so the ported compute can query it in pure C++. Not keyable
        # (geometry connection, not an animatable value).
        L.append("    %s = tAttr.create(%s, %s, MFnData::kNurbsCurve);" % (mem, a, a))
        L += _flags("tAttr", is_out, keyable=False)
    elif t == "mesh":
        # Typed kMesh attr, read into an MFnMesh local by _read_line so the
        # ported compute can query points/topology (procrustes reads self.mesh
        # -> MFnMesh::getPoints). Not keyable.
        L.append("    %s = tAttr.create(%s, %s, MFnData::kMesh);" % (mem, a, a))
        L += _flags("tAttr", is_out, keyable=False)
    elif t == "nurbsSurface":
        # Typed kNurbsSurface attr, read into an MFnNurbsSurface local by
        # _read_line. Not keyable (geometry connection).
        L.append("    %s = tAttr.create(%s, %s, MFnData::kNurbsSurface);" % (mem, a, a))
        L += _flags("tAttr", is_out, keyable=False)
    if meta.get("is_array"):
        fn = _fn_for(t)
        L.append("    %s.setArray(true);" % fn)
        if is_out:
            L.append("    %s.setUsesArrayDataBuilder(true);" % fn)
        else:
            # A scalar-numeric multi INPUT is otherwise keyable, which puts it in
            # the channel box where arrays don't belong (compound and dt-typed
            # arrays already don't display). Still editable in the AE.
            L.append("    %s.setKeyable(false);" % fn)
    return L

def _fn_for(t):
    # euler's parent compound, float2 and color all go through nAttr (euler's
    # children are angles, but the compound + array/flag calls are numeric).
    if t in ("float", "double", "int", "bool", "vector", "euler",
             "float2", "color"):
        return "nAttr"
    if t == "quaternion":
        return "cAttr"
    if t in ("angle", "time"):
        return "uAttr"
    if t == "matrix":
        return "mAttr"
    if t == "enum":
        return "eAttr"
    return "tAttr"

def _flags(fn, is_out, keyable=True):
    if is_out:
        return ["    %s.setWritable(false);" % fn, "    %s.setStorable(false);" % fn]
    out = ["    %s.setStorable(true);" % fn]
    if keyable:
        out.append("    %s.setKeyable(true);" % fn)
    return out

def _read_line(m, src="data"):
    """C++ that reads one input into a local `in_<member>` (or '' if skipped).

    ``src`` is the datablock var name -- ``data`` in compute(), ``block`` in
    deform().
    """
    mem, t = m["member"], m["meta"]["type"]
    v = "in_" + mem
    if t == "hex":
        # hex INPUT: the stored value is space-separated UTF-8 hex; decode it to
        # the plain text the ported compute expects (mirrors _api2/helpers.py
        # get_attr hex branch, so interpreted and compiled reads agree).
        return ("    const MString %s = nd_hex_decode(%s.inputValue(%s).asString());"
                % (v, src, mem))
    if t == "nurbsCurve":
        # Wrap the input curve's kNurbsCurve MObject in an MFnNurbsCurve for the
        # ported compute's curve queries (findParamFromLength / getPointAtParam
        # / tangent -- real MFnNurbsCurve methods; see the NURBS CURVE
        # translation guide). in_<m>_obj is kept so the port can null-guard it.
        return "\n".join([
            "    MObject %s_obj = %s.inputValue(%s).asNurbsCurve();" % (v, src, mem),
            "    MFnNurbsCurve %s(%s_obj);" % (v, v),
        ])
    if t == "mesh":
        # Wrap the input mesh's kMesh MObject in an MFnMesh for the ported
        # compute's point/topology queries. getPoints on a DATA mesh is
        # kObject-space, and a worldMesh connection already delivers world
        # coords. in_<m>_obj is kept so the port can null-guard an empty mesh.
        return "\n".join([
            "    MObject %s_obj = %s.inputValue(%s).asMesh();" % (v, src, mem),
            "    MFnMesh %s(%s_obj);" % (v, v),
        ])
    if t == "nurbsSurface":
        return "\n".join([
            "    MObject %s_obj = %s.inputValue(%s).asNurbsSurface();" % (v, src, mem),
            "    MFnNurbsSurface %s(%s_obj);" % (v, v),
        ])
    rd = {
        "float": "asFloat", "double": "asDouble", "int": "asInt", "bool": "asBool",
        "enum": "asShort", "matrix": "asMatrix", "string": "asString",
    }
    if t in rd:
        ctype = {"float": "float", "double": "double", "int": "int", "bool": "bool",
                 "enum": "short", "matrix": "MMatrix", "string": "MString"}[t]
        return "    const %s %s = %s.inputValue(%s).%s();" % (ctype, v, src, mem, rd[t])
    if t in ("vector", "euler"):
        # euler reads identically to vector: asDouble3() on an angle compound
        # returns Maya's internal radians (matching .asAngle().asRadians()).
        return "    const double3& %s = %s.inputValue(%s).asDouble3();" % (v, src, mem)
    if t == "float2":
        # 2-float compound (uvCoord); access components as in_<m>[0]/[1].
        return "    const float2& %s = %s.inputValue(%s).asFloat2();" % (v, src, mem)
    if t == "color":
        # 3-float color compound (borderColor); access as in_<m>[0/1/2].
        return "    const float3& %s = %s.inputValue(%s).asFloat3();" % (v, src, mem)
    if t == "quaternion":
        # Generic compound of 4 doubles: read each child handle (no asDouble4).
        # Exposed to the ported compute as double in_<m>[4] = {x, y, z, w}.
        return "\n".join([
            "    double %s[4];" % v,
            "    {",
            "        MFnCompoundAttribute _qf(%s);" % mem,
            "        MDataHandle _qh = %s.inputValue(%s);" % (src, mem),
            "        %s[0] = _qh.child(_qf.child(0)).asDouble();" % v,
            "        %s[1] = _qh.child(_qf.child(1)).asDouble();" % v,
            "        %s[2] = _qh.child(_qf.child(2)).asDouble();" % v,
            "        %s[3] = _qh.child(_qf.child(3)).asDouble();" % v,
            "    }",
        ])
    if t == "angle":
        return "    const double %s = %s.inputValue(%s).asAngle().asRadians();" % (v, src, mem)
    if t == "time":
        return "    const double %s = %s.inputValue(%s).asTime().value();" % (v, src, mem)
    return ""

def _read_plug_decl(m):
    """Declare the ``in_<member>`` local (defaulted) for the findPlug read path.

    The findPlug sibling of _read_line reads OFF a plug (not the datablock), used
    by the specialised families (transform/locator/iksolver) that read in a hook
    with no datablock. Decl is split from the assignment so the read can sit
    inside a plug-valid guard while the local stays visible + defaulted when the
    read is deferred (scene load). Local SHAPES match _read_line exactly, so
    nd_lower._materialise_input binds either path identically. Scalar (non-array)
    leaf / numeric-compound / matrix / string / angle / time types."""
    mem, t = m["member"], m["meta"]["type"]
    v = "in_" + mem
    if t in ("float", "double", "angle", "time"):
        return "    double %s = 0.0;" % v       # angle radians / time value
    if t == "int":
        return "    int %s = 0;" % v
    if t == "bool":
        return "    bool %s = false;" % v
    if t == "enum":
        return "    short %s = 0;" % v
    if t in ("string", "hex"):
        return "    MString %s;" % v
    if t in ("vector", "euler"):
        return "    double %s[3] = {0.0, 0.0, 0.0};" % v
    if t == "color":
        return "    float %s[3] = {0.0f, 0.0f, 0.0f};" % v
    if t == "float2":
        return "    float %s[2] = {0.0f, 0.0f};" % v
    if t == "quaternion":
        return "    double %s[4] = {0.0, 0.0, 0.0, 0.0};" % v
    if t == "matrix":
        return "    MMatrix %s;" % v
    return ""

def _read_plug_assign(m, plug_expr):
    """Assign ``in_<member>`` from an MPlug ``plug_expr`` (the findPlug read).

    Mirrors _read_line's per-type accessors, but off a plug: scalar leaf types
    via MPlug::asX(); numeric compounds (vector/euler/color/float2/quaternion)
    via child(i).asDouble()/asFloat() (no asDouble3 on a plug); matrix via
    getValue + MFnMatrixData; angle/time via asMAngle()/asMTime(). Indent-2
    (goes inside a ``if (_st) { ... }`` plug-valid guard)."""
    mem, t = m["member"], m["meta"]["type"]
    v = "in_" + mem
    p = plug_expr
    acc = {"float": "asFloat", "double": "asDouble", "int": "asInt",
           "bool": "asBool", "enum": "asShort", "string": "asString"}
    if t in acc:
        return "        %s = %s.%s();" % (v, p, acc[t])
    if t == "hex":
        # stored space-separated hex -> plain text (mirrors _read_line's hex).
        return "        %s = nd_hex_decode(%s.asString());" % (v, p)
    if t == "angle":
        return "        %s = %s.asMAngle().asRadians();" % (v, p)
    if t == "time":
        return "        %s = %s.asMTime().value();" % (v, p)
    if t in ("vector", "euler"):
        return ("        %s[0] = %s.child(0).asDouble(); "
                "%s[1] = %s.child(1).asDouble(); "
                "%s[2] = %s.child(2).asDouble();"
                % (v, p, v, p, v, p))
    if t == "color":
        return ("        %s[0] = %s.child(0).asFloat(); "
                "%s[1] = %s.child(1).asFloat(); "
                "%s[2] = %s.child(2).asFloat();"
                % (v, p, v, p, v, p))
    if t == "float2":
        return ("        %s[0] = %s.child(0).asFloat(); "
                "%s[1] = %s.child(1).asFloat();"
                % (v, p, v, p))
    if t == "quaternion":
        return ("        %s[0] = %s.child(0).asDouble(); "
                "%s[1] = %s.child(1).asDouble(); "
                "%s[2] = %s.child(2).asDouble(); "
                "%s[3] = %s.child(3).asDouble();"
                % (v, p, v, p, v, p, v, p))
    if t == "matrix":
        return ("        { MObject _mo; if (%s.getValue(_mo) == MS::kSuccess "
                "&& !_mo.isNull()) %s = MFnMatrixData(_mo).matrix(); }"
                % (p, v))
    return ""

def _read_plug_array_decl(m):
    """Declare ``std::vector<T> in_<member>`` for an ARRAY input read off a plug.

    findPlug sibling of _array_read_lines, for the specialised families
    (transform/locator/iksolver) that read in a hook with no datablock. Element
    type is the SAME ``_CPP[t]`` the datablock path uses, so the local shape is
    identical and nd_lower._materialise_input binds either path unchanged."""
    return "    std::vector<%s> %s;" % (_CPP[m["meta"]["type"]],
                                        "in_" + m["member"])

def _elem_plug_read_expr(t, p):
    """Expression reading ONE array element off the element MPlug ``p``.

    Plug sibling of _elem_read_expr: there is no MDataHandle in these hooks, and
    a plug addresses its compound children by index directly (so no ``_qf``
    MFnCompoundAttribute is needed). ``matrix`` has no expression form (getValue
    is a statement) -- _read_plug_array_assign special-cases it."""
    if t == "hex":
        return "nd_hex_decode(%s.asString())" % p
    if t in ("vector", "euler"):
        return ("MVector(%s.child(0).asDouble(), %s.child(1).asDouble(), "
                "%s.child(2).asDouble())" % (p, p, p))
    if t == "color":
        return ("MFloatVector(%s.child(0).asFloat(), %s.child(1).asFloat(), "
                "%s.child(2).asFloat())" % (p, p, p))
    if t == "float2":
        # float2 carried as MFloatVector (u=.x, v=.y, .z=0), as _elem_read_expr.
        return ("MFloatVector(%s.child(0).asFloat(), %s.child(1).asFloat(), "
                "0.0f)" % (p, p))
    if t == "quaternion":
        return ("MQuaternion(%s.child(0).asDouble(), %s.child(1).asDouble(), "
                "%s.child(2).asDouble(), %s.child(3).asDouble())"
                % (p, p, p, p))
    return {
        "float": "%s.asFloat()", "double": "%s.asDouble()",
        "int": "%s.asInt()", "bool": "%s.asBool()", "enum": "%s.asShort()",
        "string": "%s.asString()", "angle": "%s.asMAngle().asRadians()",
        "time": "%s.asMTime().value()",
    }[t] % p

def _read_plug_array_assign(m, plug_expr):
    """Dense scatter read of an ARRAY input off the array MPlug ``plug_expr``.

    Mirrors _array_read_lines' DENSE semantics exactly -- scatter each present
    element to its logical index, grow to ``max_logical+1``, pre-fill gaps with
    the per-type attribute default -- so the compiled vector matches the
    interpreted ``read_user_inputs_dict`` element for element. Returns indent-2
    lines (sits inside the same plug-valid guard as _read_plug_assign)."""
    mem, t = m["member"], m["meta"]["type"]
    v = "in_" + mem
    if m["meta"].get("packed") and t in _PACKED_DATA:
        # A packed plug is NOT a multi: numElements()/elementByPhysicalIndex()
        # below are multi-only APIs and would report 0 elements on it, silently
        # yielding an EMPTY vector that compiles and runs. Read the whole typed
        # array off the plug in one getValue instead (same MObject idiom as the
        # matrix element branch). Produces the identical std::vector<T> local.
        _kind, data_fn, arr_t = _PACKED_DATA[t]
        return [
            "        {",
            "            MObject _po;",
            "            if (%s.getValue(_po) == MS::kSuccess && !_po.isNull()) {"
            % plug_expr,
            "                %s _pd(_po);" % data_fn,
            "                %s _pa = _pd.array();" % arr_t,
            "                %s.resize(_pa.length());" % v,
            "                if (_pa.length()) _pa.get(&%s[0]);" % v,
            "            }",
            "        }",
        ]
    L = [
        "        {",
        "            unsigned _an = %s.numElements();" % plug_expr,
        "            for (unsigned _ai = 0; _ai < _an; ++_ai) {",
        "                MPlug _ae = %s.elementByPhysicalIndex(_ai);" % plug_expr,
        "                unsigned _al = _ae.logicalIndex();",
        "                if (_al >= %s.size()) %s.resize(_al + 1, %s);"
        % (v, v, _array_gap_default_cpp(m["meta"])),
    ]
    if t == "matrix":
        L.append("                { MObject _mo; if (_ae.getValue(_mo) == "
                 "MS::kSuccess && !_mo.isNull()) %s[_al] = "
                 "MFnMatrixData(_mo).matrix(); }" % v)
    else:
        L.append("                %s[_al] = %s;"
                 % (v, _elem_plug_read_expr(t, "_ae")))
    return L + ["            }", "        }"]

def findplug_local_hint(m, scalar_hint):
    """Porter comment describing the C++ shape of ``in_<member>``.

    Wraps each family's own scalar wording with the array / geometry shape when
    the attr is one of those, so the PORT block documents what the read actually
    produced (std::vector / MFn wrapper / Nd<Kind> list)."""
    meta = m["meta"]
    t = meta["type"]
    if _geo.is_geo(t):
        kind = _geo.geo_kind_of(t)
        if meta.get("is_array"):
            return ("std::vector<%s>; dense, [i].points/.counts/... (.present)"
                    % _geo._STRUCT[kind])
        return ("%s; in_<m>_obj is the MObject (isNull() == no geometry)"
                % {"mesh": "MFnMesh", "curve": "MFnNurbsCurve",
                   "surface": "MFnNurbsSurface"}[kind])
    if meta.get("is_array"):
        return "std::vector<%s>; dense, indexed by LOGICAL index" % _CPP[t]
    return scalar_hint

def findplug_family_extras(generics):
    """(includes, helper_blocks) a findPlug-family TU needs for its generic inputs.

    transform/locator/iksolver assemble their own translation unit (node_scaffold
    returns early for them), so the conditional machinery the plain path adds
    around a hex or geometry attr has to be requested here instead: the hex
    transcode core, the MFn* headers a single geo read wraps, and the Nd<Kind>
    structs + nd_read_<kind> readers a geo ARRAY read builds."""
    incs, blocks = [], []
    metas = [g["meta"] for g in generics]
    types = {m["type"] for m in metas}
    if any(m.get("is_array") for m in metas):
        incs.append("vector")
    if "hex" in types:
        incs.append("string")
        blocks.append(_HEX_CPP_BLOCK)
    arr_types = {m["type"] for m in metas if m.get("is_array")}
    for t, hdr in (("color", "maya/MFloatVector.h"),
                   ("float2", "maya/MFloatVector.h"),
                   ("quaternion", "maya/MQuaternion.h"),
                   ("vector", "maya/MVector.h"), ("euler", "maya/MVector.h"),
                   ("matrix", "maya/MFnMatrixData.h"),
                   ("string", "maya/MString.h"), ("hex", "maya/MString.h")):
        if t in arr_types:
            incs.append(hdr)
    # packed (typed-array) input: _read_plug_array_assign reads it whole through
    # MFn*ArrayData. Gated on an actual packed attr so every other frag in these
    # families stays byte-identical.
    if any(m.get("packed") for m in metas):
        incs += list(PACKED_INCLUDES)
    # geometry (single OR array): the Nd<Kind> struct + nd_read_<kind> reader,
    # plus that kind's own includes.
    geo_metas = [m for m in metas if _geo.is_geo(m["type"])]
    geo_kinds = sorted({_geo.geo_kind_of(m["type"]) for m in geo_metas})
    if geo_kinds:
        incs.append("maya/MFn.h")
        incs += list(_geo.geo_io_includes(geo_kinds))
        blocks.append(_geo.geo_io_cpp(geo_kinds))
    seen, uniq = set(), []
    for i in incs:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq, blocks

def _pick_path_input(ins):
    """The image-path input for a texture/file node: a string ARRAY path (the
    multi-file composite source) first, else the input named 'fileName', else the
    first string/hex input, else None. Shared so the codegen (which decides
    whether to emit the single-file vs multi-file composite cache) and the
    image-load glue agree on the same input. The array takes precedence over a
    single fileName so a composite node whose spec also carries an (unused)
    fileName preset still routes to the composite path."""
    string_ins = [i for i in ins if i["meta"].get("type") in ("string", "hex")]
    for i in string_ins:
        if i["meta"].get("is_array"):
            return i
    for i in string_ins:
        if i["plug"].lower() == "filename":
            return i
    return string_ins[0] if string_ins else None


def _image_read_lines(ins, embedded=False):
    """MImage file load for a sanctioned texture/file node (Option D).

    Picks the path input (named 'fileName', else the first string input) and
    loads it into an RGBA8 row-major buffer exposed to the ported compute as
    ``_imgPixels`` / ``_imgW`` / ``_imgH`` / ``_imgOK``. No string input -> []
    (defensive: nothing to load). The actual pixel math (sample/scanline/grain)
    is filled by the AI porter against this buffer; the imread/Image.open call
    in the Python source maps to this load (see translation_knowledge).

    When the path input is a string ARRAY (a list of file paths), the load is a
    multi-file COMPOSITE (scan max size, resize-to-max, premultiplied-alpha
    composite) built once by ``nd_img_composite`` -- but exposed through the
    SAME _imgPixels/_imgW/_imgH/_imgOK names, so the ported compute samples it
    exactly like a single image (and _imgW/_imgH ARE the composite/max size).

    ``embedded`` -> also emit the baked-embeddedImage fallback (#98): when the
    fileName load fails (blank / unreadable), decode the staged embedded bytes
    via a SEPARATE cache slot. Mirrors the Python ``read_texture()``, which reads
    fileName first and falls back to the ``embeddedImage`` buffer. (Embedded
    fallback is single-file only; N/A for the array/composite path.)

    This is the RAW arm -- a hand-rolled compute that taps pixels itself. A
    compute that calls the blessed read_texture() lowers instead, and gets the
    same fallback as a retry through its by-path NdTexCache (file_texture_cpp
    _emit_load), with no second cache slot."""
    fn = _pick_path_input(ins)
    if fn is None:
        return []
    v = "in_" + fn["member"]
    if fn["meta"].get("is_array"):
        return [
            "",
            "    // --- multi-file composite load (CACHED; nd_img_composite above) ---",
            "    // Scan all paths for the max size, resize each to it (nearest),",
            "    // premultiplied-alpha composite in order; result exposed as an 8-bit",
            "    // RGBA buffer _imgPixels[(y*_imgW + x)*4 + c] (0..255), _imgW x _imgH.",
            "    unsigned int _imgW = 0, _imgH = 0;",
            "    const unsigned char* _imgPixels = nullptr;",
            "    bool _imgOK = nd_img_composite(_imgCompCache, _imgCompMutex, %s," % v,
            "                                   _imgW, _imgH, _imgPixels);",
        ]
    lines = [
        "",
        "    // --- image file load (CACHED; see nd_img_load_raw above the class) ---",
        "    // The decode (MImage::readFromFile) runs ONCE per node instance and is",
        "    // re-read only when the path changes -- a per-compute() decode runs once",
        "    // per shading sample and makes a render thousands of times slower than",
        "    // the Python node (which caches the decoded array). Pixels are RGBA, 8-bit,",
        "    // row-major: _imgPixels[(y*_imgW + x)*4 + c], c in {0=R,1=G,2=B,3=A}, 0..255;",
        "    // _imgOK is false when the read failed -- handle that in the ported compute.",
        "    unsigned int _imgW = 0, _imgH = 0;",
        "    const unsigned char* _imgPixels = nullptr;",
        "    bool _imgOK = nd_img_load_raw(_imgRawCache, _imgRawMutex, %s," % v,
        "                                 _imgW, _imgH, _imgPixels);",
    ]
    if embedded:
        lines += [
            "    // Embedded-image fallback (#98): fileName blank/unreadable -> decode the",
            "    // baked embeddedImage bytes (staged to a temp file once; SEPARATE cache",
            "    // slot so the constant image decodes once, never per shading sample).",
            "    if (!_imgOK) {",
            "        MString _embPath = nd_img_embedded_path();",
            "        if (_embPath.length() > 0)",
            "            _imgOK = nd_img_load_raw(_imgEmbedCache, _imgEmbedMutex, _embPath,",
            "                                     _imgW, _imgH, _imgPixels);",
            "    }",
        ]
    return lines


def _image_read_hint_lines(ins):
    """PORT-region hints describing the buffer ``_image_read_lines`` produced.

    Three facts a translator cannot recover from ``_imgPixels`` itself; without
    them a plausible port is silently upside-down, in the wrong transfer
    function, or crashes on a blank path. Row order is ARM-DEPENDENT: the
    single-file ``nd_img_load_raw`` hands back MImage's native BOTTOM-UP rows
    while ``nd_img_composite`` verticalFlips to top-down (it mirrors a PIL/numpy
    Init helper) -- both behind the same ``_imgPixels`` name, so the hint names
    whichever arm was actually emitted. Same ``_pick_path_input`` resolution as
    the read itself, so hint and buffer can never describe different inputs; no
    path input -> [] (no read was emitted, so there is nothing to describe)."""
    fn = _pick_path_input(ins)
    if fn is None:
        return []
    if fn["meta"].get("is_array"):
        rows = ("    //   * rows are TOP-DOWN (nd_img_composite verticalFlips "
                "to match PIL/numpy); if the Python")
        rows2 = "    //     indexed bottom-up, flip here."
    else:
        rows = ("    //   * rows are MImage's native BOTTOM-UP order; if "
                "the Python flipped to top-down, flip here too.")
        rows2 = None
    lines = [
        "    // The image file is loaded above into _imgPixels "
        "(RGBA8, _imgW x _imgH, _imgOK); translate the Python",
        "    // pixel read/sample against it -- do NOT call "
        "imread/Image.open/MImage in C++.",
        rows,
    ]
    if rows2:
        lines.append(rows2)
    lines += [
        "    //   * channels are RAW 8-bit; if the Python applied "
        "a transfer function (sRGB EOTF), apply it here too.",
        "    //   * _imgOK false (blank/unreadable path) must take "
        "the SAME fallback branch the Python takes.",
    ]
    return lines


_OUT_DEFAULT = {
    "float": "%s.setFloat(0.0f);", "double": "%s.setDouble(0.0);",
    "int": "%s.setInt(0);",
    "bool": "%s.setBool(false);", "enum": "%s.setShort(0);",
    "matrix": "%s.setMMatrix(MMatrix());",
    "string": '%s.setString("");', "hex": '%s.setString("");',
    "angle": "%s.setMAngle(MAngle(0.0));", "time": "%s.setMTime(MTime(0.0));",
    "vector": "%s.set3Double(0.0, 0.0, 0.0);",
    "euler": "%s.set3Double(0.0, 0.0, 0.0);",
    "float2": "%s.set2Float(0.0f, 0.0f);",
    "color": "%s.set3Float(0.0f, 0.0f, 0.0f);",
}

def _out_handle_default(m):
    """Declare an output MDataHandle `h_<member>` + seed a neutral default."""
    mem, t = m["member"], m["meta"]["type"]
    h = "h_" + mem
    if t == "quaternion":
        # Generic compound: seed identity [0,0,0,1] via child handles (the
        # parent handle has no numeric set4Double). The porter overwrites by
        # constructing its own MFnCompoundAttribute(<member>) -- see _setter_hint.
        return [
            "    MDataHandle %s = data.outputValue(%s);" % (h, mem),
            "    {",
            "        MFnCompoundAttribute _qf(%s);" % mem,
            "        %s.child(_qf.child(0)).setDouble(0.0);" % h,
            "        %s.child(_qf.child(1)).setDouble(0.0);" % h,
            "        %s.child(_qf.child(2)).setDouble(0.0);" % h,
            "        %s.child(_qf.child(3)).setDouble(1.0);" % h,
            "    }",
        ]
    return [
        "    MDataHandle %s = data.outputValue(%s);" % (h, mem),
        "    " + _OUT_DEFAULT[t] % h,
    ]

def _out_setclean(m):
    return "    h_%s.setClean();" % m["member"]

def _write_lines(m):
    """Phase-1 stub: declare handle, write neutral default, mark clean."""
    return _out_handle_default(m) + [_out_setclean(m)]

def _setter_hint(m):
    """Human/AI hint: which setter call writes this output handle."""
    mem, t = m["member"], m["meta"]["type"]
    call = {
        "float": "h_%s.setFloat(<float>)", "double": "h_%s.setDouble(<double>)",
        "int": "h_%s.setInt(<int>)",
        "bool": "h_%s.setBool(<bool>)", "enum": "h_%s.setShort(<short>)",
        "matrix": "h_%s.setMMatrix(<MMatrix>)",
        "string": "h_%s.setString(<MString>)", "hex": "h_%s.setString(<MString>)",
        "angle": "h_%s.setMAngle(MAngle(<radians>))",
        "time": "h_%s.setMTime(MTime(<seconds>))",
        "vector": "h_%s.set3Double(<x>, <y>, <z>)",
        "euler": "h_%s.set3Double(<rx>, <ry>, <rz>)  // radians",
        "float2": "h_%s.set2Float(<u>, <v>)",
        "color": "h_%s.set3Float(<r>, <g>, <b>)  // 0..1 linear color",
        "quaternion": ("MFnCompoundAttribute qf(<member>); "
                       "h_%s.child(qf.child(0..3)).setDouble(<x>,<y>,<z>,<w>)"),
    }[t]
    return call % mem

def _elem_read_expr(t):
    """Expression reading one array element value from a handle `eh`.

    `string`/`color` read straight off the element handle. `hex` decodes the
    stored space-separated hex to plain text (mirrors the single-hex read).
    `quaternion` needs the attr's compound children, addressed via `_qf` (an
    ``MFnCompoundAttribute`` the array read/write loops declare when the element
    type is a quaternion) -- so this expression references `_qf`."""
    if t == "string":
        return "eh.asString()"
    if t == "hex":
        return "nd_hex_decode(eh.asString())"
    if t == "color":
        return "MFloatVector(eh.asFloat3())"
    if t == "float2":
        # float2 carried as MFloatVector (u=.x, v=.y, .z=0); read the 2 floats.
        return "MFloatVector(eh.asFloat2()[0], eh.asFloat2()[1], 0.0f)"
    if t == "quaternion":
        return ("MQuaternion(eh.child(_qf.child(0)).asDouble(), "
                "eh.child(_qf.child(1)).asDouble(), "
                "eh.child(_qf.child(2)).asDouble(), "
                "eh.child(_qf.child(3)).asDouble())")
    return {
        "float": "eh.asFloat()", "double": "eh.asDouble()",
        "int": "eh.asInt()", "bool": "eh.asBool()",
        "enum": "eh.asShort()", "matrix": "eh.asMatrix()",
        "angle": "eh.asAngle().asRadians()", "time": "eh.asTime().value()",
        "vector": "MVector(eh.asDouble3())",
        "euler": "MVector(eh.asDouble3())",
    }[t]

def _elem_set_stmt(t, val):
    """Statement setting one array element (handle `eh`) from `val`.

    `hex` re-encodes the plain-text buffer to space-separated hex on write
    (mirrors the single-hex finalize). `quaternion` writes its 4 compound
    children via `_qf` (declared by the array write loop for quaternion)."""
    if t in ("vector", "euler"):
        return "eh.set3Double((%s).x, (%s).y, (%s).z);" % (val, val, val)
    if t == "matrix":
        return "eh.setMMatrix(%s);" % val
    if t == "angle":
        return "eh.setMAngle(MAngle(%s));" % val
    if t == "time":
        return "eh.setMTime(MTime(%s));" % val
    if t == "enum":
        return "eh.setShort(%s);" % val
    if t == "string":
        return "eh.setString(%s);" % val
    if t == "hex":
        return "eh.setString(nd_hex_encode(%s));" % val
    if t == "color":
        return "eh.set3Float((%s).x, (%s).y, (%s).z);" % (val, val, val)
    if t == "float2":
        # float2 carried as MFloatVector (u=.x, v=.y); write the 2 floats.
        return "eh.set2Float((%s).x, (%s).y);" % (val, val)
    if t == "quaternion":
        return (" ".join(
            "eh.child(_qf.child(%d)).setDouble((%s).%s);" % (i, val, ax)
            for i, ax in enumerate("xyzw")))
    return {"float": "eh.setFloat(%s);", "double": "eh.setDouble(%s);",
            "int": "eh.setInt(%s);",
            "bool": "eh.setBool(%s);"}[t] % val

def _array_gap_default_cpp(meta):
    """C++ literal for a dense-array gap slot, mirroring
    ``_api2.helpers.array_gap_default`` (matrix=identity, vector/euler=zero,
    numeric=the addAttr default value)."""
    t = meta["type"]
    if t == "matrix":
        return "MMatrix()"
    if t in ("vector", "euler"):
        return "MVector()"
    if t == "int":
        return _num_default(meta, int, "0")
    if t == "bool":
        return _bool_default(meta)
    if t == "enum":
        return "0"
    if t == "time":
        return "0.0"
    if t in ("string", "hex"):
        return "MString()"
    if t == "color":
        return "MFloatVector(0.0f, 0.0f, 0.0f)"
    if t == "float2":
        return "MFloatVector(0.0f, 0.0f, 0.0f)"
    if t == "quaternion":
        return "MQuaternion()"
    # float / double / angle (radians) -- dv recorded for numeric types.
    return _num_default(meta, float, "0.0")

def _qf_decl(t, mem):
    """A ``quaternion`` array element addresses its 4 compound children through an
    ``MFnCompoundAttribute`` bound to the attr MObject -- declared once per array
    loop block. Empty for every other (leaf/numeric-compound) element type."""
    if t == "quaternion":
        return ["        MFnCompoundAttribute _qf(%s);" % mem]
    return []

def _array_read_lines(m, src="data"):
    """Read an array INPUT into ``std::vector<T> in_<member>``.

    Dense by default (mirrors the interpreted ``read_user_inputs_dict``):
    scatter each existing element to its logical index, growing the vector to
    ``max_logical+1`` with gaps pre-filled by the per-type attribute default.
    A ``sparse`` input keeps the legacy compact (physical, connection-order)
    read. A ``packed`` input is one typed array, read whole in a single
    ``M*Array::get`` copy instead of an element-at-a-time handle walk.
    """
    mem, t = m["member"], m["meta"]["type"]
    v = "in_" + mem
    if m["meta"].get("packed") and t in _PACKED_DATA:
        # Emits the SAME `std::vector<T> in_<member>` as the multi paths, so
        # nd_lower/_materialise_input and every ported-compute reference bind
        # identically -- only the source of the bytes changes. A packed array is
        # dense by construction, so there is no gap fill.
        _kind, data_fn, arr_t = _PACKED_DATA[t]
        return [
            "    std::vector<%s> %s;" % (_CPP[t], v),
            "    {",
            "        MObject _po = %s.inputValue(%s).data();" % (src, mem),
            "        if (!_po.isNull()) {",
            "            %s _pd(_po);" % data_fn,
            "            %s _pa = _pd.array();" % arr_t,
            "            %s.resize(_pa.length());" % v,
            "            if (_pa.length()) _pa.get(&%s[0]);" % v,
            "        }",
            "    }",
        ]
    if m["meta"].get("sparse"):
        return [
            "    std::vector<%s> %s;" % (_CPP[t], v),
            "    {",
        ] + _qf_decl(t, mem) + [
            "        MArrayDataHandle _arr = %s.inputArrayValue(%s);" % (src, mem),
            "        unsigned _n = _arr.elementCount();",
            "        for (unsigned _i = 0; _i < _n; ++_i) {",
            "            MDataHandle eh = _arr.inputValue();",
            "            %s.push_back(%s);" % (v, _elem_read_expr(t)),
            "            _arr.next();",
            "        }",
            "    }",
        ]
    dflt = _array_gap_default_cpp(m["meta"])
    return [
        "    std::vector<%s> %s;" % (_CPP[t], v),
        "    {",
    ] + _qf_decl(t, mem) + [
        "        MArrayDataHandle _arr = %s.inputArrayValue(%s);" % (src, mem),
        "        unsigned _n = _arr.elementCount();",
        "        for (unsigned _i = 0; _i < _n; ++_i) {",
        "            unsigned _li = _arr.elementIndex();",
        "            if (_li >= %s.size()) %s.resize(_li + 1, %s);" % (v, v, dflt),
        "            MDataHandle eh = _arr.inputValue();",
        "            %s[_li] = %s;" % (v, _elem_read_expr(t)),
        "            _arr.next();",
        "        }",
        "    }",
    ]

def _array_write_lines(m):
    """Write `std::vector<T> out_<member>` back to an array OUTPUT.

    FULL-REWRITE semantics: a FRESH builder sized to the value count, not the
    datablock's existing one (``_outArr.builder()``), which copies every element
    already in the array before the loop overwrites it. Measured on Maya 2026 /
    arm64 / -O3, fixed-size double array, one eval per perturbed input:
    N=1000 1.39x, N=10000 2.35x, N=100000 3.22x.

    The trade is behavioural: an element the compute does NOT write this
    evaluation is DROPPED, where ``builder()`` kept it. The interpreted writer
    (``_api2.helpers.write_multi_plug_value``) still takes the existing builder
    and so still PRESERVES stale elements -- a known, accepted divergence.

    EMPTY buffer: a compute that wrote NOTHING this evaluation (e.g.
    procrustesCluster/procrustesTags, whose fill sits inside a
    `clusters/rest/deformed non-empty` guard) must leave every existing element
    at the attribute DEFAULT, because that is what the interpreter does -- it
    never touches the plug, and an unassigned output reads back as its default,
    NOT as the previous evaluation's value. Skipping the write entirely (what
    this did before) reproduced the OLD COMPILED behaviour rather than the
    interpreter's, so a node whose guard stopped assigning silently FROZE its
    last good result: clearing every `clusterTags` element left the compiled
    rivets holding their last pose while the interpreted ones released to
    identity (measured divergence 5.255). The default comes from
    ``_array_gap_default_cpp``, the same helper the dense-array READ path uses,
    which already mirrors ``_api2.helpers.array_gap_default``.

    ``setAllClean`` stays UNCONDITIONAL: the old code always left the output
    array clean, and a dirty array output re-enters compute.
    """
    mem, t = m["member"], m["meta"]["type"]
    v = "out_" + mem
    return [
        "    {",
    ] + _qf_decl(t, mem) + [
        "        MArrayDataHandle _outArr = data.outputArrayValue(%s);" % mem,
        "        if (!%s.empty()) {" % v,
        "            MArrayDataBuilder _b(&data, %s, (unsigned)%s.size());"
        % (mem, v),
        "            for (size_t _i = 0; _i < %s.size(); ++_i) {" % v,
        "                MDataHandle eh = _b.addElement((unsigned)_i);",
        "                %s" % _elem_set_stmt(t, "%s[_i]" % v),
        "            }",
        "            _outArr.set(_b);",
        "        } else {",
        "            %s _dflt = %s;" % (_CPP[t], _array_gap_default_cpp(m["meta"])),
        "            unsigned _ne = _outArr.elementCount();",
        "            for (unsigned _i = 0; _i < _ne; ++_i) {",
        "                MDataHandle eh = _outArr.outputValue();",
        "                %s" % _elem_set_stmt(t, "_dflt"),
        "                _outArr.next();",
        "            }",
        "        }",
        "        _outArr.setAllClean();",
        "    }",
    ]

def _scal_out_handle_lines(o):
    """Declare the scalar output write target for the AI PORT scaffold.

    A `hex` output writes a PLAIN-text MString BUFFER (``out_<member>``) that
    codegen hex-encodes into the live handle at finalize -- so the ported compute
    writes readable text exactly like the interpreter (which auto-encodes on
    setAttr). Every other type declares its live handle + neutral default."""
    if o["meta"]["type"] == "hex":
        return ["    MString out_%s;" % o["member"]]
    return _out_handle_default(o)

def _scal_out_hint(o):
    """The setter-hint comment for one scalar output in the PORT region."""
    if o["meta"]["type"] == "hex":
        return ("    //   set out_%s   (write PLAIN text; the hex attr auto-encodes it)"
                % o["member"])
    return "    //   %s" % _setter_hint(o)

def _scal_out_finalize(o):
    """Finalize one scalar output after the PORT body.

    hex: fetch the handle, hex-encode the plain-text buffer into it, mark clean;
    every other type just marks its already-written handle clean."""
    if o["meta"]["type"] == "hex":
        mem = o["member"]
        return [
            "    MDataHandle h_%s = data.outputValue(%s);" % (mem, mem),
            "    h_%s.setString(nd_hex_encode(out_%s));" % (mem, mem),
            "    h_%s.setClean();" % mem,
        ]
    return [_out_setclean(o)]

_UNSET = object()
