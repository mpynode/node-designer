"""Mpynode._api2.helpers — API 2.0 helpers for the API 2 plugin.

Functions here build / read / write Maya plugs via ``maya.api.OpenMaya``.
Used by the API 2.0 plugin node modules (``_api2/_mpy_node.py``,
``_api2/mpy_locator.py``, ``_api2/mpy_constraint.py``, etc.).

adds pickle (pickle+base64 over string) + mesh + nurbsCurve
+ nurbsSurface support to read_plug_value / write_plug_value.
"""

from __future__ import annotations

import base64
import pickle
from typing import Any

import maya.api.OpenMaya as om
import numpy as np

from mpynode._common.attr_types import BY_NAME as _ATTR_TYPES_BY_NAME
from mpynode._common.attr_types import (canonical, stored_name,
                                       unknown_type_message)

# Maya-free; imported at module top so the pickle-attr read hot path consults
# pickle-trust with a plain global read (no per-compute import cost).
from mpynode._common.io import trust


# ---------------------------------------------------------------------------
# Attribute factory helpers
# ---------------------------------------------------------------------------


def make_internal_string_attr(
    long_name:  str,
    short_name: str,
    default:    str  = "",
    storable:   bool = True,
):
    """Build an internal hidden string attribute. Returns the MObject.

    ``storable=False`` keeps the attribute out of
    the.ma. Used for the profile + watch snapshot data plugs so the
    transient last-frame snapshot doesn't pollute saved scene files
    AND reopened scenes start fresh (no stale data from a prior session).
    """
    str_data       = om.MFnStringData()
    default_obj    = str_data.create(default)
    fn             = om.MFnTypedAttribute()
    obj            = fn.create(long_name, short_name, om.MFnData.kString, default_obj)
    fn.connectable = False
    fn.readable    = False
    fn.writable    = True
    fn.storable    = bool(storable)
    fn.internal    = True
    fn.keyable     = False
    fn.hidden      = True
    return obj


def make_expression_attr():
    """The compute-source attr (``_computeSource``) is connectable +
    keyable (so users can wire a stringNode into it if they want, e.g. to
    switch expressions per frame). Otherwise same flags as the other
    internal strings.

    Default is "" (empty string). Was previously "None" (literal),
    which Maya's 2dTextureSwatchGen for texture nodes may try to
    interpret as a file path during swatch generation -- a possible
    cause of the mPyFile Hypershade Browser swatches degrading to
    a single-sample render."""
    str_data       = om.MFnStringData()
    default_obj    = str_data.create("")
    fn             = om.MFnTypedAttribute()
    obj            = fn.create("_computeSource", "_computeSource", om.MFnData.kString, default_obj)
    fn.connectable = True
    fn.readable    = True
    fn.writable    = True
    fn.storable    = True
    fn.internal    = True
    fn.keyable     = True
    fn.hidden      = True
    return obj


def make_legacy_expression_attr():
    """DEPRECATED. Exists solely so a v1 scene can be opened without data loss.

    v1 (``node-designer``) stored its single compute source on a plug literally
    named ``expression``. v2 stores four source tiers and calls the compute one
    ``_computeSource``, so a v1 scene's ``setAttr ".expression"`` had nowhere
    to land -- and because v2 registers the same node TYPE name, Maya builds a
    v2 node and replays v1's setAttrs at it rather than making an unknown node.
    The measured result was that the attributes survived and the CODE was
    silently dropped; saving over the original then lost it for good.

    Declaring the plug gives that value somewhere to arrive. It is not part of
    v2's authoring surface: hidden, unconnectable, and swept into
    ``_computeSource`` by ``_common/io/v1_upgrade`` on the next scene-open
    callback.

    ``storable=True`` on purpose. It would be tidier to make it transient so a
    converted node never re-saves the legacy payload -- but then a conversion
    that FAILED would evaporate the moment the user saved, turning a
    recoverable problem into a permanent one. It is cleared explicitly, and
    only on success.
    """
    str_data    = om.MFnStringData()
    default_obj = str_data.create("")
    fn          = om.MFnTypedAttribute()
    obj         = fn.create("expression", "expression", om.MFnData.kString, default_obj)
    # Not connectable and not internal: this is an inert carrier, and giving it
    # setInternalValue handling would make a legacy payload look like an edit.
    fn.connectable = False
    fn.readable    = True
    fn.writable    = True
    fn.storable    = True
    fn.keyable     = False
    fn.hidden      = True
    fn.channelBox  = False
    return obj


def make_bool_attr(
    long_name:  str,
    short_name: str,
    default:    bool = False,
    storable:   bool = True,
):
    """Build a hidden framework-toggle bool attribute.

    Used for the ``debug_mode`` + profile / deep_profile / watch
    toggles. These are framework instrumentation switches the Node
    Designer's Profile + Watch tabs flip via ``cmds.setAttr`` --
    they must NOT appear in the Attribute Editor or Channel Box,
    where they could be accidentally keyed or look like part of the
    user-authored attribute surface. ``cmds.setAttr`` / ``getAttr``
    still work on hidden attrs, so the UI hookups are unaffected.

    ``storable=False`` keeps the attribute value out of the .ma so
    it always reverts to ``default`` on file open (used for the
    profile / watch toggles -- avoids ever shipping a scene with the
    profiler accidentally left on).
    """
    fn             = om.MFnNumericAttribute()
    obj            = fn.create(long_name, short_name, om.MFnNumericData.kBoolean, default)
    fn.connectable = False
    fn.storable    = bool(storable)
    fn.keyable     = False
    # Hide from Attribute Editor + Channel Box. The framework UI
    # reaches these via cmds.setAttr/getAttr which ignore visibility.
    fn.hidden     = True
    fn.channelBox = False
    return obj


def build_internal_attrs(cls):
    """Add the standard internal attrs to an MPxNode subclass.

    Returns a dict mapping convenience names to the MObject plugs:
      ``_computeSource``, ``inputs``, ``outputs``,
      ``stored_vars_list``, ``stored_vars_data``, ``debug_mode``,
      ``profile_enabled``, ``deep_profile_enabled``, ``watch_enabled``,
      ``profile_snapshot_data``, ``watch_vars_data``.

    Caller stores these on the class so ``compute()`` and
    ``setInternalValue`` can compare against them.
    """
    plugs = {
        "_computeSource": make_expression_attr(),
        # v1 compatibility carrier -- see make_legacy_expression_attr.
        "legacy_expression": make_legacy_expression_attr(),
        "inputs":            make_internal_string_attr("_inputAttrs", "_inputAttrs"),
        "outputs":           make_internal_string_attr("_outputAttrs", "_outputAttrs"),
        "stored_vars_list": make_internal_string_attr(
            "_storedVarNames", "_storedVarNames"
        ),
        "stored_vars_data": make_internal_string_attr(
            "_storedVarsData", "_storedVarsData"
        ),
        "debug_mode": make_bool_attr("debug_mode", "dbgm"),
        # profile + watch toggles (visible in channel box). storable=False so
        # they are always OFF on file open -- never ship a scene profiling.
        "profile_enabled": make_bool_attr("profile_enabled", "prfen", storable=False),
        "deep_profile_enabled": make_bool_attr(
            "deep_profile_enabled", "dprfen", storable=False
        ),
        "watch_enabled": make_bool_attr("watch_enabled", "wtcen", storable=False),
        # Snapshot data plugs (hidden strings written by
        # exec_with_profile_watch's throttle, read by the panels).
        # storable=False -- transient last-frame data, never saved.
        "profile_snapshot_data": make_internal_string_attr(
            "_profileSnapshotData", "_profileSnapshotData", storable=False
        ),
        "watch_vars_data": make_internal_string_attr(
            "_watchVarsData", "_watchVarsData", storable=False
        ),
    }
    for plug in plugs.values():
        cls.addAttribute(plug)
    return plugs


def ensure_expr_code(node_mpx, expr_attr):
    """Reconcile ``node_mpx._expr_str`` / ``._expr_code`` with the live
    ``_computeSource`` plug, returning the compiled code object.

    Why this exists: every mpynode node compiles its expression in
    ``setInternalValue`` and caches it on the instance. Maya calls
    ``setInternalValue`` for interactive / scripted ``setAttr``, but it
    does NOT route through it when it **duplicates** a node -- the plug
    value is copied directly. So a duplicated node carries the source
    text yet keeps the fresh instance's empty/default ``_expr_code`` and
    does nothing (the symptom: a duplicated gizmo shows its expression in
    the UI but draws nothing). Calling this at the top of
    ``compute()`` / ``evaluateDrawItems()`` makes duplication (and any
    out-of-band plug edit) robust. Cheap: only recompiles when the source
    string actually changed.
    """
    fn = om.MFnDependencyNode(node_mpx.thisMObject())
    try:
        cur = fn.findPlug(expr_attr, True).asString() or ""
    except Exception:
        return getattr(node_mpx, "_expr_code", None)
    if cur != getattr(node_mpx, "_expr_str", None):
        from mpynode._common.compute.expression import (
            compile_expression,
            safe_compile_expression,
        )

        node_mpx._expr_str = cur
        code = safe_compile_expression(
            cur, node_name=fn.name(), filename="<mpynode-expression>"
        )
        node_mpx._expr_code = code if code is not None else compile_expression("")
    return node_mpx._expr_code


# ---------------------------------------------------------------------------
# Dynamic user-attr factory (called by MPyNode wrapper.add_input_attr / add_output_attr)
# ---------------------------------------------------------------------------


# Mapping from our wire-type strings to (MFn class, MFn type constant, default).
SUPPORTED_TYPES: dict[str, tuple] = {
    "float":   (om.MFnNumericAttribute, om.MFnNumericData.kFloat, 0.0),
    "double":  (om.MFnNumericAttribute, om.MFnNumericData.kDouble, 0.0),
    "long":    (om.MFnNumericAttribute, om.MFnNumericData.kInt, 0),
    "bool":    (om.MFnNumericAttribute, om.MFnNumericData.kBoolean, False),
    "double3": (None, None, None),  # special — handled below
    "matrix":  (None, None, None),  # special — handled below
    "string":  (None, None, None),  # special — handled below
}


# PACKED array storage: wire type -> (data MFn class, MFnData kind). Only the
# dense numeric tables qualify; see ``_mpy_node._PACKED_DT``, which MUST list the
# same wire types (the cmds path and this API path build the same plug).
_PACKED_DATA_KIND: dict[str, tuple] = {
    "double": (om.MFnDoubleArrayData, om.MFnData.kDoubleArray),
    "long":   (om.MFnIntArrayData, om.MFnData.kIntArray),
}


def make_dynamic_user_attr(long_name: str, attr_type: str, is_array: bool = False,
                           packed: bool = False):
    """Create an MObject for a user-added input or output attr.

    ``attr_type`` is one of the keys in SUPPORTED_TYPES. ``is_array`` makes
    the plug an array (multi) plug.

    ``packed`` (array inputs, ``double``/``long`` only) makes it a single
    typed-array plug (kDoubleArray / kIntArray) instead of a multi, so the whole
    table moves in one write. Mirrors ``_mpy_node.add_input_attr(packed=True)``;
    the two paths MUST agree or a node built through the API would carry a
    different plug kind than the same node built through ``cmds``.

    The plug is NOT added to any node here; the caller does
    ``cmds.addAttr`` or ``MFnDependencyNode.addAttribute`` per-instance.
    """
    short = long_name  # users get the same short name; can be customized later
    # An alias makes the same plug as its stored name.
    attr_type = canonical(attr_type)

    if packed:
        kind = _PACKED_DATA_KIND.get(attr_type)
        if kind is None:
            raise ValueError(
                f"packed is not available for attr_type {attr_type!r}"
            )
        data_cls, data_kind = kind
        fn  = om.MFnTypedAttribute()
        obj = fn.create(long_name, short, data_kind, data_cls().create())
        # A packed array is one plug: storable and readable/writable like any
        # typed attr, but never keyable (an array has no channel-box value) and
        # never ``array=True`` -- that would make a MULTI OF ARRAYS.
        fn.storable    = True
        fn.keyable     = False
        fn.connectable = True
        fn.readable    = True
        fn.writable    = True
        return obj

    if attr_type in ("float", "double", "long", "bool"):
        cls_, kind, default = SUPPORTED_TYPES[attr_type]
        fn  = cls_()
        obj = fn.create(long_name, short, kind, default)
    elif attr_type == "double3":
        fn  = om.MFnNumericAttribute()
        obj = fn.createPoint(long_name, short)
    elif attr_type == "matrix":
        fn  = om.MFnMatrixAttribute()
        obj = fn.create(long_name, short, om.MFnMatrixAttribute.kDouble)
        # MFnMatrixAttribute.create() leaves the default uninitialized and Maya
        # zero-fills it, so unconnected plugs read as a zero matrix (degenerate
        # for transforms). Identity matches every stock Maya matrix plug.
        try:
            fn.default = om.MMatrix()
        except AttributeError:
            try:
                fn.setDefault(om.MMatrix())
            except Exception:
                pass
    elif attr_type == "string":
        str_data    = om.MFnStringData()
        default_obj = str_data.create("")
        fn          = om.MFnTypedAttribute()
        obj         = fn.create(long_name, short, om.MFnData.kString, default_obj)
    else:
        raise ValueError(f"unsupported attr_type {attr_type!r}")

    # Common flags
    fn.storable    = True
    fn.keyable     = True
    fn.connectable = True
    fn.readable    = True
    fn.writable    = True

    if is_array:
        fn.array                = True
        fn.usesArrayDataBuilder = True

    return obj


# ---------------------------------------------------------------------------
# Plug value read / write helpers
# ---------------------------------------------------------------------------


def _geom_data_mobject(plug, data_block, kind):
    """Pull the typed-geometry data MObject for ``plug``.

    Inside ``compute()`` ``plug.asMObject()`` does NOT pull the upstream
    (e.g. a deformer feeding ``worldMesh``), so it returns rest/stale data.
    The EM-safe path is the datablock: ``inputValue(plug).asMesh()`` etc.,
    which evaluates the upstream. Falls back to ``asMObject`` (used in the
    draw-override / init context where no datablock exists)."""
    if data_block is not None:
        try:
            handle = data_block.inputValue(plug)
            if kind == "mesh":
                return handle.asMesh()
            if kind == "nurbsCurve":
                return handle.asNurbsCurve()
            if kind == "nurbsSurface":
                return handle.asNurbsSurface()
        except Exception:
            pass
    try:
        return plug.asMObject()
    except Exception:
        return None


def decode_python_string(raw: str) -> Any:
    """Decode a ``pickle`` attr's ``base64(pickle(obj))`` bus string into its
    live Python object. Canonical decoder shared by the compute read path
    (:func:`read_plug_value`) and UI code (the Watch tab).

    ``pickle.loads`` on attacker-controlled ``.ma`` data is RCE, so this is
    gated on the per-scene pickle-trust resolved at open/import. In an
    untrusted scene it refuses (returns ``None``); the bus works at full
    speed in a trusted scene.

    Returns ``None`` for an empty string or an untrusted scene; raises
    ``ValueError`` on a corrupt payload (clearer than a base64 dump).
    """
    if not raw:
        return None
    if not trust.pickle_trusted():
        return None
    try:
        return pickle.loads(base64.b64decode(raw.encode("ascii")))
    except Exception:
        raise ValueError(
            "failed to decode pickle attr payload; "
            "payload is not valid pickle+base64"
        )


def decode_hex_string(raw: str) -> str:
    """A ``hex`` attr's space-separated UTF-8 hex bytes ("48 69") as plain
    text ("Hi"). Blank reads as ``""``; anything that is not hex is returned
    as stored. Shared by the plug read and the data-handle read."""
    if not raw or not raw.strip():
        return ""
    try:
        return bytes.fromhex(raw.replace(" ", "")).decode("utf-8", "replace")
    except Exception:
        return raw


def encode_string_output(attr_type: str, value: Any) -> str:
    """The string a ``string`` / ``hex`` / ``pickle`` output stores for
    ``value``: the inverse of what the same type reads as.

    * ``pickle`` -- ``base64(pickle(value))``; read back by
      :func:`decode_python_string`, which is where the trust gate sits.
      Encoding runs no foreign code, so it is not gated.
    * ``hex`` -- a plain ``str`` as space-separated UTF-8 hex bytes, the form
      Maya's ``type`` node expects on ``textInput`` ("Hi" -> "48 69").
    * anything else -- ``str(value)``.

    ``None`` stores ``""`` for ``hex`` and ``pickle``. Shared by every writer
    (the api2 handle write and the api1 plug writes) so they cannot drift.
    """
    if attr_type == "pickle":
        if value is None:
            return ""
        try:
            # protocol 5: explicit + reader-compatible across Maya 2024
            # (py3.10) and 2026 (py3.11), both of which read protocol 5.
            return base64.b64encode(
                pickle.dumps(value, protocol=5)
            ).decode("ascii")
        except Exception as exc:
            raise ValueError(f"failed to pickle value for pickle attr: {exc}")
    if attr_type == "hex":
        if value is None:
            return ""
        return " ".join("%02x" % b for b in str(value).encode("utf-8"))
    return str(value)


def read_plug_value(plug: om.MPlug, attr_type: str, data_block=None) -> Any:
    """Read a Maya plug value into a Python value matching attr_type.

    ``data_block``: when reading INSIDE compute(), pass the MDataBlock so
    geometry inputs (mesh / nurbs) are pulled EM-safely (evaluating any
    upstream deformer). Outside compute (draw override / init) pass None.
    """
    if attr_type == "float":
        return plug.asFloat()
    if attr_type == "double":
        return plug.asDouble()
    if attr_type == "long":
        return plug.asInt()
    if attr_type == "bool":
        return plug.asBool()
    if attr_type == "double3":
        # 3-channel compound; child(0/1/2) are doubles
        return np.array(
            [
                plug.child(0).asDouble(),
                plug.child(1).asDouble(),
                plug.child(2).asDouble(),
            ],
            dtype=np.float64,
        )
    if attr_type == "color":
        # 3-channel float compound (R/G/B); child(0/1/2) are floats.
        return np.array(
            [
                plug.child(0).asFloat(),
                plug.child(1).asFloat(),
                plug.child(2).asFloat(),
            ],
            dtype=np.float64,
        )
    if attr_type == "float2":
        # 2-channel float compound (U/V); child(0/1) are floats.
        return np.array(
            [
                plug.child(0).asFloat(),
                plug.child(1).asFloat(),
            ],
            dtype=np.float64,
        )
    if attr_type == "quaternion":
        # numeric double4 (X/Y/Z/W), or a generic compound of 4 doubles in a
        # scene saved before 2026-10; the children read the same on both.
        return np.array(
            [
                plug.child(0).asDouble(),
                plug.child(1).asDouble(),
                plug.child(2).asDouble(),
                plug.child(3).asDouble(),
            ],
            dtype=np.float64,
        )
    # doubleAngle / doubleLinear / euler / position / enum
    if attr_type == "doubleAngle":
        # doubleAngle stored in radians internally; asDouble returns radians.
        return plug.asDouble()
    if attr_type == "doubleLinear":
        # doubleLinear stored in centimetres internally; asDouble returns cm
        # whatever the scene's linear unit (1 m reads 100.0).
        return plug.asDouble()
    if attr_type in ("euler", "position"):
        return np.array(
            [
                plug.child(0).asDouble(),
                plug.child(1).asDouble(),
                plug.child(2).asDouble(),
            ],
            dtype=np.float64,
        )
    if attr_type == "enum":
        # EnumInt is an ``int`` subclass carrying the attr MObject so
        # ``self.<enum>.name()`` yields the field label, matching the plug-proxy
        # read. Load-bearing under C2 dense seeding: a plain ``int`` would
        # shadow the plug proxy and drop ``.name()``.
        from mpynode._common.plugs.promoted_types import EnumInt

        return EnumInt(plug.asInt(), plug.attribute())
    # time — returns the current time value as a float
    # (in current Maya UI units, typically frames).
    if attr_type == "time":
        try:
            return plug.asMTime().value
        except Exception:
            # Fall back to asDouble if MTime API is missing.
            return plug.asDouble()
    # pickle is a base64+pickle node-to-node data BUS. ``pickle.loads`` on
    # attacker-controlled .ma data is RCE, so it is gated on the per-scene trust
    # resolved once at open/import (same boundary as stored vars). "Connected"
    # is NOT special-cased: an attacker .ma can wire a plain string source
    # carrying the malicious literal into this input, so ``isDestination`` is no
    # proof of a safe runtime value. Untrusted scene -> refuse pickle outright.
    if attr_type == "pickle":
        # ``decode_python_string`` is the single source of truth for the
        # RCE-critical decode (trust gate + base64/pickle + corrupt payloads).
        return decode_python_string(plug.asString() or "")
    # hex is a space-separated UTF-8 hex byte string <-> plain ``str``. As an
    # INPUT it decodes hex -> text (read a Type node's textInput back as
    # readable text). The matching OUTPUT encode is in _write_value_to_handle.
    if attr_type == "hex":
        return decode_hex_string(plug.asString() or "")
    # Typed Maya geometry plugs. Returns the high-level MFn* function set so
    # the user gets ergonomic API access (m.numVertices, m.getPoints()).
    if attr_type == "mesh":
        mobj = _geom_data_mobject(plug, data_block, "mesh")
        if mobj is None or mobj.isNull():
            return None
        # Unified Mesh wrapper (attached mode): exposes points / counts /
        # indices / normals / colors / component_tags + region()/copy(), and
        # delegates any MFnMesh method to the live fn.
        from mpynode._api2.geometry import Mesh as _Mesh
        return _Mesh._attach(mobj, source_plug=plug)
    if attr_type == "nurbsCurve":
        mobj = _geom_data_mobject(plug, data_block, "nurbsCurve")
        if mobj is None or mobj.isNull():
            return None
        # Unified NurbsCurve wrapper (attached mode): points/cvs/degree/form/
        # knots/component_tags + region()/copy(), delegating any MFnNurbsCurve
        # method to the live fn.
        from mpynode._api2.geometry import NurbsCurve as _NurbsCurve
        return _NurbsCurve._attach(mobj, source_plug=plug)
    if attr_type == "nurbsSurface":
        mobj = _geom_data_mobject(plug, data_block, "nurbsSurface")
        if mobj is None or mobj.isNull():
            return None
        # Unified NurbsSurface wrapper (attached mode): points (nu,nv,3) grid,
        # degree/form/knots u|v, component_tags + region()/copy(), delegating
        # any MFnNurbsSurface method to the live fn.
        from mpynode._api2.geometry import NurbsSurface as _NurbsSurface
        return _NurbsSurface._attach(mobj, source_plug=plug)
    if attr_type == "matrix":
        # Unified api1/api2 return type: a numpy-transparent MatrixView
        # (np.asarray(M) -> (4,4), M @ X, plus .translation()/.rotation()).
        from mpynode._common.plugs.promoted_types import MatrixView

        try:
            mobj = plug.asMObject()
            mfn  = om.MFnMatrixData(mobj)
            m    = mfn.matrix()
            out  = np.zeros((4, 4), dtype=np.float64)
            for r in range(4):
                for c in range(4):
                    out[r, c] = m.getElement(r, c)
        except RuntimeError:
            # plug.asMObject() can raise kFailure on unconnected matrix
            # plugs with no stored data; fall back to identity.
            return MatrixView(np.eye(4, dtype=np.float64))
        # An all-zeros matrix is degenerate for transforms; treat it as identity
        # to match Maya's stock matrix plugs, and to cover the
        # MFnMatrixAttribute zero-init quirk in older saved scenes.
        if not out.any():
            return MatrixView(np.eye(4, dtype=np.float64))
        return MatrixView(out)
    if attr_type == "string":
        return plug.asString()
    # Every stored name is handled above. An alias reads as its stored name;
    # anything else raises (a retired name with its replacement).
    stored = canonical(attr_type)
    if stored == attr_type:
        raise ValueError(unknown_type_message(attr_type))
    return read_plug_value(plug, stored, data_block)


def _geo_value_to_data(attr_type: str, value: Any):
    """Marshal a geometry OUTPUT value into the matching ``MFn*Data`` MObject
    ready for ``handle.setMObject(...)``.

    Accepts (in priority order):
      * a finished data MObject (``MFnMeshData``/``…CurveData``/``…SurfaceData``
        the user built themselves) -- used as-is;
      * any object exposing ``to_mobject()`` -- the unified ``Mesh`` /
        ``NurbsCurve`` / ``NurbsSurface`` wrapper (attached-unedited returns its
        retained DATA zero-copy, preserving component tags; a ``copy()``/value
        rebuilds from arrays);
      * a duck-typed value bucket (any object exposing the required arrays) ->
        the ``geometry.build_*_data`` marshaller.

    Returns ``None`` if the value can't be marshalled to this geometry kind."""
    from mpynode._api2 import geometry as _geo

    if isinstance(value, om.MObject):
        return value
    to_mo = getattr(value, "to_mobject", None)
    if callable(to_mo):
        try:
            return to_mo()
        except Exception:
            return None
    if attr_type == "mesh" and _geo.is_mesh_like(value):
        return _geo.build_mesh_data(value)
    if attr_type == "nurbsCurve" and _geo.is_curve_like(value):
        return _geo.build_curve_data(value)
    if attr_type == "nurbsSurface" and _geo.is_surface_like(value):
        return _geo.build_surface_data(value)
    return None


def _handle_write_kind(attr_obj, attr_type: str) -> dict:
    """The keyword arguments :func:`_write_value_to_handle` needs for the plug
    KIND behind ``attr_obj``, for the two types whose kind changed in 2026-10.

    * ``matrix``: today's plug is ``-at matrix`` (kMatrixAttribute), written
      with ``setMMatrix``. A scene saved earlier carries a typed ``-dt matrix``
      plug, written with ``setMObject(MFnMatrixData)``. The wrong call on
      either kind crashes Maya, so the kind is read off the attribute, never
      assumed.
    * ``quaternion``: today's plug is a numeric double4, written with
      ``set4Double``. A scene saved earlier carries a generic compound of 4
      doubles, which has no numeric accessor: its 4 child handles are written.
      A double4 also reports ``hasFn(kCompoundAttribute)``, so the test is the
      exact api type.

    Empty for every other type, and for today's kinds.
    """
    if attr_obj is None or attr_obj.isNull():
        return {}
    if attr_type == "matrix" and attr_obj.hasFn(om.MFn.kTypedAttribute):
        return {"typed_matrix": True}
    if (attr_type == "quaternion"
            and attr_obj.apiType() == om.MFn.kCompoundAttribute):
        cfn  = om.MFnCompoundAttribute(attr_obj)
        kids = [cfn.child(i) for i in range(cfn.numChildren())]
        return {"child_attrs": kids}
    return {}


def _write_value_to_handle(
    handle:       "om.MDataHandle",
    attr_type:    str,
    value:        Any,
    child_attrs                    = None,
    typed_matrix: bool             = False,
) -> None:
    """Write ``value`` into an already-resolved ``handle``.

    Pure handle-write: parameterized so we can call it from BOTH the
    scalar path (``data_block.outputValue(plug)``) AND the multi path
    (``builder.addElement(idx)``). Caller is responsible for any
    handle.setClean() / array_handle.setAllClean() + data_block.setClean(attr)
    bookkeeping.

    ``child_attrs`` and ``typed_matrix`` describe a LEGACY plug kind (see
    :func:`_handle_write_kind`, which callers use to fill them): the child
    attribute MObjects of a generic-compound ``quaternion``, and True for a
    typed ``-dt matrix`` plug. Left at their defaults, a quaternion is written
    as a numeric double4 and a matrix as an ``-at matrix`` plug.

    For ``mesh`` / ``nurbsCurve`` / ``nurbsSurface``, marshals ``value`` (a
    ``Mesh`` / ``NurbsCurve`` / ``NurbsSurface`` wrapper, a duck-typed arrays
    bucket, or a finished ``MFn*Data`` MObject) via :func:`_geo_value_to_data`
    and writes it with ``handle.setMObject`` -- so a geometry output works on
    ANY node type, not just the geometry generators.
    """
    if attr_type == "float":
        handle.setFloat(float(value))
    elif attr_type == "double":
        handle.setDouble(float(value))
    elif attr_type == "long":
        handle.setInt(int(value))
    elif attr_type == "bool":
        handle.setBool(bool(value))
    elif attr_type == "double3":
        v = np.asarray(value, dtype=np.float64).flatten()
        if v.size < 3:
            v = np.pad(v, (0, 3 - v.size))
        handle.set3Double(float(v[0]), float(v[1]), float(v[2]))
    elif attr_type == "color":
        # numeric float3 compound -- set3Float on the parent handle.
        v = np.asarray(value, dtype=np.float64).flatten()
        if v.size < 3:
            v = np.pad(v, (0, 3 - v.size))
        handle.set3Float(float(v[0]), float(v[1]), float(v[2]))
    elif attr_type == "float2":
        # numeric float2 compound -- set2Float on the parent handle.
        v = np.asarray(value, dtype=np.float64).flatten()
        if v.size < 2:
            v = np.pad(v, (0, 2 - v.size))
        handle.set2Float(float(v[0]), float(v[1]))
    elif attr_type == "quaternion":
        v = np.asarray(value, dtype=np.float64).flatten()
        if v.size < 4:
            v = np.pad(v, (0, 4 - v.size))
        if child_attrs is None:
            # numeric double4: one call on the parent handle.
            handle.set4Double(
                float(v[0]), float(v[1]), float(v[2]), float(v[3]))
        else:
            # legacy generic compound: no numeric accessor, write each child.
            for i, attr in enumerate(child_attrs):
                handle.child(attr).setDouble(float(v[i]))
    # doubleAngle / doubleLinear / euler / position / enum write side, in
    # internal units (radians, centimetres).
    elif attr_type in ("doubleAngle", "doubleLinear"):
        handle.setDouble(float(value))
    elif attr_type in ("euler", "position"):
        v = np.asarray(value, dtype=np.float64).flatten()
        if v.size < 3:
            v = np.pad(v, (0, 3 - v.size))
        handle.set3Double(float(v[0]), float(v[1]), float(v[2]))
    elif attr_type == "enum":
        handle.setInt(int(value))
    # time output -- set as MTime in current units.
    elif attr_type == "time":
        try:
            t = om.MTime(float(value), om.MTime.uiUnit())
            handle.setMTime(t)
        except Exception:
            # Older Maya: just write the raw double.
            handle.setDouble(float(value))
    # pickle output -- pickle the value, store as base64 string. hex output --
    # encode a plain ``str`` to the space-separated UTF-8 hex string Maya's
    # ``type`` node expects on ``textInput`` ("Hi" -> "48 69"). Write plain
    # text in the expression; the consumer receives the hex form.
    elif attr_type in ("pickle", "hex"):
        handle.setString(encode_string_output(attr_type, value))
    elif attr_type in ("mesh", "nurbsCurve", "nurbsSurface"):
        data_obj = _geo_value_to_data(attr_type, value)
        if data_obj is None:
            raise ValueError(
                f"cannot marshal {type(value).__name__} into a {attr_type!r} "
                f"output; assign a Mesh / NurbsCurve / NurbsSurface (or its "
                f"copy()), a duck-typed object exposing the required arrays, or "
                f"a finished MFn{attr_type[0].upper()}{attr_type[1:]}Data MObject."
            )
        handle.setMObject(data_obj)
    elif attr_type == "matrix":
        # Accept MMatrix / MTransformationMatrix / flat-16 / (4,4) / (3,3) via
        # the shared helper; (3,3) expands to 4x4 with a zero translate row.
        from mpynode._common.plugs.plug_proxy import _coerce_to_4x4_numpy
        arr = _coerce_to_4x4_numpy(value)
        if arr is None:
            raise ValueError(
                f"cannot coerce {type(value).__name__} to 4x4 matrix; "
                f"accepted forms: MMatrix, MTransformationMatrix, "
                f"flat 16-iterable, 4x4 array, 3x3 array."
            )
        m = om.MMatrix(arr.flatten().tolist())
        if typed_matrix:
            # legacy typed ``-dt matrix`` plug: setMMatrix here crashes Maya.
            handle.setMObject(om.MFnMatrixData().create(m))
        else:
            # ``-at matrix`` plug: setMObject here crashes Maya.
            handle.setMMatrix(m)
    elif attr_type == "string":
        handle.setString(str(value))
    else:
        # Every stored name is handled above. An alias writes as its stored
        # name; anything else raises (a retired name with its replacement).
        stored = canonical(attr_type)
        if stored == attr_type:
            raise ValueError(unknown_type_message(attr_type))
        _write_value_to_handle(handle, stored, value, child_attrs=child_attrs,
                               typed_matrix=typed_matrix)


def write_plug_value(
    data_block: om.MDataBlock, plug: om.MPlug, attr_type: str, value: Any
) -> None:
    """Write a Python value into a Maya output plug via the data block.

    SCALAR write path. For multi (array) plugs, use:func:`write_multi_plug_value` instead \u2014 calling this on a multi
    parent plug silently no-ops (Maya's ``data_block.outputValue`` on a
    multi parent doesn't write anything).
    """
    # An alias writes as its stored name: _handle_write_kind picks the write
    # call by it. Any other name is left for _write_value_to_handle to judge.
    attr_type = stored_name(attr_type)
    handle    = data_block.outputValue(plug)
    kind      = _handle_write_kind(plug.attribute(), attr_type)
    _write_value_to_handle(handle, attr_type, value, **kind)
    handle.setClean()


def _outgoing_source_indices(out_plug) -> list:
    """Sorted logical indices of the array elements that are CONNECTED as a
    source (i.e. drive a downstream consumer).

    Returns ``[]`` for a non-array plug, an unconnected output, or on any
    query failure (so callers fall back to positional writes).
    """
    if out_plug is None:
        return []
    try:
        if not out_plug.isArray:
            return []
        srcs = []
        for ei in range(out_plug.numElements()):
            ep = out_plug.elementByPhysicalIndex(ei)
            if ep.isSource:
                srcs.append(ep.logicalIndex())
        srcs.sort()
        return srcs
    except Exception:
        return []


def write_multi_plug_value(
    data_block: om.MDataBlock,
    attr_obj:   om.MObject,
    attr_type:  str,
    values:     Any,
    out_plug                  = None,
) -> None:
    """Write an iterable of values into a Maya MULTI (array) output plug.

    Closes the long-standing gap where
    ``write_plug_value`` silently no-ops on multi parents. Maya needs
    ``outputArrayValue + builder + addElement`` per index.

    ``attr_obj`` is the multi parent's MObject (NOT a child MPlug).

    Index mapping for ``values`` (let ``S`` = the sorted logical indices of
    the output's outgoing/source connections, ``span = max(S) + 1``):
      * If ``out_plug`` has source connections AND ``len(values) < span``,
        the value list is a dense full-replacement that is too short to be
        logical-indexed up to the highest connection -- so the k-th value
        is written to the k-th CONNECTED element ``S[k]`` (extra
        connections beyond ``len(values)`` are left untouched). This drives
        the consumers the user actually wired even when Maya assigned those
        connections non-zero / offset logical indices (e.g. a saved scene
        wired at [N..2N-1] because the output had cached elements at
        [0..N-1] when it was connected), and tolerates a value count that
        differs from the connection count.
      * Otherwise the k-th value is written to logical index ``k``
        (``range(len(values))``) -- the positional default. Used for
        watch-only / pre-wire evals (no connections) and for in-place
        pre-sized buffer writes (``len(values) >= span``, so positional
        already covers every connected element at its own logical index).
    Pre-existing higher indices are left in place (Maya's standard multi
    semantics): ``array_handle.builder()`` hands back a builder already holding
    every element in the array, so an element this evaluation does not write
    KEEPS its previous value and the plug's element count is a HIGH-WATER MARK,
    not the count this evaluation produced.

    DELIBERATE DIVERGENCE FROM THE COMPILED PATH (T94, resolved 2026-08-13 by
    documenting it rather than converging). Since T14 the generated C++
    (``native/compiler/emit_attr._array_write_lines``) builds a FRESH
    ``MArrayDataBuilder`` sized to the value count, so a SHORT write DROPS the
    tail: write 3 elements then 2 and the interpreted node still reports
    ``multiIndices == [0, 1, 2]`` with ``out[2]`` at its old value, while the
    compiled node reports ``[0, 1]``.

    An EMPTY write also agrees, but NOT because either side is a no-op -- that
    reading was wrong and cost a real divergence. On this side the pre-seed
    below means an evaluation that assigns nothing publishes DEFAULTS, so the
    compiled ``if (!out_<mem>.empty())`` guard alone (skip the rewrite, keep the
    previous values) did NOT match: clearing every ``clusterTags`` element left
    the compiled procrustesTags rivets frozen at their last pose while these
    released to identity, measured at 5.255 on 2026-08-20. ``emit_attr`` now
    pairs that guard with an ``else`` that writes the per-type default to each
    EXISTING element -- same element count, default values -- which is what
    reproduces the pre-seed.

    The interpreted side is NOT brought to full-rewrite because preservation is
    load-bearing here in a way it is not in C++: every api2 base pre-seeds each
    array output to ``output_defaults.output_default(type, True, n)`` with ``n``
    read from that plug's EXISTING element indices
    (``getExistingArrayAttributeIndices``) -- inline in ``_api2/_mpy_node.py``
    for mPyNode and in ``_api2/mpy_constraint.py`` for mPyConstraint, and via
    ``output_defaults.seed_user_output_defaults_api2`` for mesh / nurbsCurve /
    nurbsSurface / file. The self-sizing templates read that count straight back
    as their N (bubbleSort ``len(self.sort)``, spline ``len(self.samples)``,
    springChain ``len(self.driven)``, spine ``len(self.outputTranslate)``). One
    short write under full-rewrite would therefore ratchet the array down
    permanently instead of recovering on the next evaluation -- measured on the
    compiled path, where 4,4,4,4 recovers and 4,2,2,2 sticks.
    ``native/toolchain/verify.py`` knows about this gap
    (``_is_stale_tail_shrink``) and does not score it as a parity failure.

    For ``mesh`` / ``nurbsCurve`` / ``nurbsSurface``, each element value is
    marshalled (wrapper / duck-typed bucket / finished MFn*Data MObject) and
    written to ``output[i]`` via the shared per-element writer -- so an ARRAY
    geometry output works on any node type (assign a ``list`` of geometry
    objects). This generalizes the deformer's existing per-``multiIndex``
    geometry write.

    CLEAN BOOKKEEPING: after the write the array is marked clean twice over --
    ``array_handle.setAllClean()`` for the elements and
    ``data_block.setClean(attr_obj)`` for the attribute itself. Without the
    second call the attribute stayed dirty after the evaluation that wrote it,
    and the Evaluation Manager called compute again for every connected array
    output (measured 2026-09-23: Spine 3 runs a frame, DNET 2, its solver
    stepping once per run). The compiled twin, ``emit_attr._array_write_lines``,
    emits the same pair.

    Type contract for ``values``:
      * scalar types (float / double / long / bool / string / doubleAngle /
        doubleLinear / enum / time / pickle) \u2014 1D iterable of scalars,
        e.g. ``[1.0, 2.0, 3.0]`` or ``np.array([1.0, 2.0, 3.0])``
      * double3 / euler / position \u2014 iterable of 3-element vectors, e.g.
        ``[[1,2,3], np.array([4,5,6])]``
      * matrix \u2014 iterable of 4x4 matrices, e.g.
        ``[np.eye(4), np.eye(4) * 2]``
      * mesh / nurbsCurve / nurbsSurface \u2014 iterable of geometry objects
        (``Mesh`` / ``NurbsCurve`` / ``NurbsSurface`` wrappers, duck-typed
        buckets, or finished ``MFn*Data`` MObjects)
    """
    # An alias writes as its stored name: _handle_write_kind picks the write
    # call by it. Any other name is left for _write_value_to_handle to judge.
    attr_type = stored_name(attr_type)

    # Tolerate None / non-iterable -- skip with empty list.
    try:
        seq = list(values) if values is not None else []
    except TypeError:
        seq = []

    # Pick destination logical indices. When the value list is a short
    # full-replacement (len < connected span), map the k-th value to the k-th
    # outgoing connection -- this heals scenes whose consumers were wired at
    # offset element indices. Otherwise write positional [0..len-1] (watch-only
    # / pre-wire evals, and pre-sized buffers that already cover every index).
    src_indices = _outgoing_source_indices(out_plug)
    if src_indices and len(seq) < (src_indices[-1] + 1):
        dest_indices = src_indices  # zip() below stops at the shorter of the two
    else:
        dest_indices = range(len(seq))

    kind         = _handle_write_kind(attr_obj, attr_type)
    array_handle = data_block.outputArrayValue(attr_obj)
    builder      = array_handle.builder()
    for logical_idx, value in zip(dest_indices, seq):
        elem_handle = builder.addElement(logical_idx)
        _write_value_to_handle(elem_handle, attr_type, value, **kind)
    array_handle.set(builder)
    array_handle.setAllClean()
    # setAllClean cleans the ELEMENTS only; the array attribute stayed dirty, so
    # the Evaluation Manager re-ran compute once per connected array output
    # (Spine 2.0: 5 runs a frame -> 1) and a DG read of the whole array paid a
    # second compute. See CLEAN BOOKKEEPING in the docstring.
    data_block.setClean(attr_obj)


def array_gap_default(attr_obj, attr_type: str):
    """Per-element default used to fill unconnected logical-index gaps when
    reading a NON-sparse array input. Matrices -> identity, quaternions ->
    [0,0,0,1], double3/euler/position/color -> zeros(3), numeric -> the
    attribute's ``defaultValue`` (``addAttr dv=..``; radians / centimetres for
    the unit types), string -> "", and
    pickle / mesh / nurbsCurve / nurbsSurface -> None (gap-fill ill-defined)."""
    if attr_type == "matrix":
        return [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    if attr_type == "quaternion":
        return [0.0, 0.0, 0.0, 1.0]
    if attr_type in ("double3", "euler", "position", "color"):
        return [0.0, 0.0, 0.0]
    if attr_type == "float2":
        return [0.0, 0.0]
    if attr_type in ("float", "double", "long", "bool"):
        try:
            return om.MFnNumericAttribute(attr_obj).default
        except Exception:
            return 0
    if attr_type == "enum":
        try:
            return om.MFnEnumAttribute(attr_obj).default
        except Exception:
            return 0
    if attr_type == "doubleAngle":
        try:
            return om.MFnUnitAttribute(attr_obj).default.asRadians()
        except Exception:
            return 0.0
    if attr_type == "doubleLinear":
        try:
            return om.MFnUnitAttribute(attr_obj).default.asCentimeters()
        except Exception:
            return 0.0
    if attr_type == "time":
        return 0.0
    if attr_type in ("string", "hex"):
        return ""
    return None


# Maya data-array function set per PACKED wire type. ``double`` -> kDoubleArray
# (MFnDoubleArrayData), ``long`` -> kIntArray (MFnIntArrayData). Kept beside
# array_gap_default because a packed array has NO gaps -- there are no logical
# indices to leave unset -- so it deliberately has no gap-fill counterpart.
_PACKED_FN = {"double": om.MFnDoubleArrayData, "long": om.MFnIntArrayData}


def _packed_from_mobject(data_obj, attr_type: str) -> list:
    """Typed-array data MObject -> flat Python list, in ONE read.

    An unset/null object yields ``[]``, which is the correct empty table rather
    than an error: Maya leaves typed-array storage empty until first written.
    Shared by both reader entry points below."""
    fn_cls = _PACKED_FN.get(attr_type)
    if fn_cls is None or data_obj is None:
        return []
    try:
        if data_obj.isNull():
            return []
        return list(fn_cls(data_obj).array())
    except Exception:
        return []


def _read_packed_array(handle, attr_type: str) -> list:
    """Whole packed typed-array plug -> flat Python list, in ONE handle read.

    ``handle`` is an ``MDataHandle`` for the packed attr (NOT an
    ``MArrayDataHandle`` -- a packed attr is a single typed plug, not a multi).
    """
    try:
        data_obj = handle.data()
    except Exception:
        return []
    return _packed_from_mobject(data_obj, attr_type)


def _packed_plug_data(plug, data_block):
    """The typed-array data MObject behind a packed PLUG.

    Prefers the datablock (EM-safe, and the value the current evaluation is
    actually computing with) and falls back to the plug itself when no block
    was handed in."""
    if data_block is not None:
        try:
            return data_block.inputValue(plug.attribute()).data()
        except Exception:
            pass
    try:
        return plug.asMObject()
    except Exception:
        return None


def _read_multi(plug, attr_obj, attr_type, sparse, read_elem):
    """Read a multi plug into a Python list.

    ``sparse`` True -> compact, connected-only, physical order (legacy). False
    (default) -> dense, length ``max_logical+1``, gaps filled by
    :func:`array_gap_default` and existing values scattered to their logical
    index. Gap elements are NEVER materialized -- only existing elements are
    read; the rest are the default fill."""
    n = plug.numElements()
    if sparse or n == 0:
        return [read_elem(plug.elementByPhysicalIndex(i)) for i in range(n)]
    elems = [plug.elementByPhysicalIndex(i) for i in range(n)]
    span  = max(e.logicalIndex() for e in elems) + 1
    out   = [array_gap_default(attr_obj, attr_type) for _ in range(span)]
    for e in elems:
        out[e.logicalIndex()] = read_elem(e)
    return out


def read_user_inputs_dict(
    node_obj: om.MObject, attr_map: dict, data_block=None, geom_data_out=None
) -> dict:
    """Read all USER input plugs from the node into a Python dict.

    ``data_block``: pass the MDataBlock when reading inside compute() so
    geometry inputs (mesh / nurbs) pull upstream-evaluated data (EM-safe).
    Leave None outside compute (draw override / init).

    ``geom_data_out``: optional dict. When supplied AND a ``data_block`` is
    given, every SINGLE geometry input (mesh / nurbsCurve / nurbsSurface) also
    stashes its raw DATA MObject (the SAME api2 object ``self.<geo>`` wraps)
    keyed by input name. This is the ONLY Evaluation-Manager-safe handle on the
    flowing geometry DATA: component tags live on ``MFnGeometryData`` (the DATA,
    not the MFnMesh), and every side-channel plug read (``MSelectionList`` /
    ``connectedTo`` / ``cmds.getAttr``) returns empty on the EM worker thread.
    Reading tags off THIS object (see ``component_tags`` helpers) matches the
    positions ``self.mesh`` exposes exactly.

    ``attr_map`` is the parsed _inputAttrs JSON: {name: {attr_type, is_array}}.
    Values keyed by the attr name (matches what users write in expressions).

    Type contract:
      * Scalar input (``float``/``double``/``long``/``bool``/``string``):
        Python primitive
      * double3 input: ``np.ndarray (3,)``
      * Matrix input: ``MatrixView`` (numpy-transparent:
        ``np.asarray(M)`` -> (4,4); also ``.translation()/.rotation()``)
      * MULTI scalar input (``is_array=True``):
        - float/double/doubleAngle/doubleLinear/time \u2192 ``np.ndarray (n,)``
          dtype float64
        - long/enum \u2192 ``np.ndarray (n,)`` dtype int64
        - bool \u2192 ``np.ndarray (n,)`` dtype bool
        - string \u2192 ``list[str]``  (numpy string arrays are awkward)
      * MULTI double3 / euler / position input: ``np.ndarray (n, 3)`` dtype
        float64
      * MULTI matrix input: ``MatrixArrayView`` (numpy-transparent:
        ``np.asarray(M)`` -> (n,4,4); ``M[i]`` -> single view;
        ``M.translation()`` -> (n,3))
      * MULTI pickle / mesh / nurbsCurve / nurbsSurface input: ``list``
        (heterogeneous types, can't stack)

    Numerical compound multis (double3 / euler / position / matrix)
    are now stacked into a single numpy ndarray instead of a Python list of
    per-element ndarrays. The build path also avoids constructing the
    per-element ndarrays \u2014 raw scalar lists are collected and cast in one
    ``np.asarray`` call. User expressions that previously did
    ``[v[0] for v in vec_in]`` still work (numpy 2D arrays iterate over
    rows) and now also support ``vec_in[:, 0]`` / ``vec_in.shape`` /
    other numpy ergonomics.
    """
    fn_node = om.MFnDependencyNode(node_obj)
    out: dict = {}
    for name, meta in attr_map.items():
        attr_type = meta.get("attr_type", "double")
        is_array  = bool(meta.get("is_array", False))
        try:
            plug = fn_node.findPlug(name, True)
        except RuntimeError:
            # plug doesn't exist on this instance (yet); skip
            continue
        # An alias reads as its stored name: the array branches below pick
        # their container by it. Any other name is left for read_plug_value
        # to judge.
        attr_type = stored_name(attr_type)
        if not is_array:
            out[name] = read_plug_value(plug, attr_type, data_block=data_block)
            # EM-safe geometry DATA capture: stash the raw data MObject so
            # callers can read component tags (MFnGeometryData) off the SAME
            # object self.<geo> wraps. Only meaningful with a data_block.
            if (
                geom_data_out is not None
                and data_block is not None
                and attr_type in ("mesh", "nurbsCurve", "nurbsSurface")
            ):
                try:
                    _gm = _geom_data_mobject(plug, data_block, attr_type)
                    if _gm is not None and not _gm.isNull():
                        geom_data_out[name] = _gm
                except Exception:
                    pass
            continue

        sparse   = bool(meta.get("sparse", False))
        attr_obj = plug.attribute()

        # A packed input is ONE typed-array plug, not a multi. Every multi API
        # below (numElements / elementByPhysicalIndex, via _read_multi) raises
        # "Plug is not an array" on it, so the whole table is read off the plug
        # in one call BEFORE any of them are reached. Dense by construction --
        # no logical indices, so nothing to scatter and no gap to fill.
        if meta.get("packed"):
            values = _packed_from_mobject(
                _packed_plug_data(plug, data_block), attr_type)
            if attr_type == "long":
                out[name] = (np.asarray(values, dtype=np.int64) if values
                             else np.zeros(0, dtype=np.int64))
            else:
                out[name] = (np.asarray(values, dtype=np.float64) if values
                             else np.zeros(0, dtype=np.float64))
            continue

        # Compound numeric multis go straight to stacked numpy arrays: build
        # raw python lists per element and cast once, avoiding the per-element
        # np.array() that read_plug_value would do. ``_read_multi`` densifies a
        # non-sparse array (length max_logical+1, gaps = the attr default).
        if attr_type in ("double3", "euler", "position", "color"):
            values = _read_multi(
                plug, attr_obj, attr_type, sparse,
                lambda e: [
                    e.child(0).asDouble(),
                    e.child(1).asDouble(),
                    e.child(2).asDouble(),
                ],
            )
            out[name] = (
                np.asarray(values, dtype=np.float64)
                if values
                else np.zeros((0, 3), dtype=np.float64)
            )
            continue
        if attr_type == "float2":
            # 2-float compound multi -> stacked nd (n, 2) (children are floats).
            values = _read_multi(
                plug, attr_obj, attr_type, sparse,
                lambda e: [e.child(0).asFloat(), e.child(1).asFloat()],
            )
            out[name] = (
                np.asarray(values, dtype=np.float64)
                if values
                else np.zeros((0, 2), dtype=np.float64)
            )
            continue
        if attr_type == "quaternion":
            values = _read_multi(
                plug, attr_obj, attr_type, sparse,
                lambda e: [
                    e.child(0).asDouble(),
                    e.child(1).asDouble(),
                    e.child(2).asDouble(),
                    e.child(3).asDouble(),
                ],
            )
            out[name] = (
                np.asarray(values, dtype=np.float64)
                if values
                else np.zeros((0, 4), dtype=np.float64)
            )
            continue
        if attr_type == "matrix":
            from mpynode._common.plugs.promoted_types import MatrixArrayView

            def _read_mat(e):
                m = om.MFnMatrixData(e.asMObject()).matrix()
                return [[m.getElement(r, c) for c in range(4)] for r in range(4)]

            values = _read_multi(plug, attr_obj, attr_type, sparse, _read_mat)
            stacked = (
                np.asarray(values, dtype=np.float64)
                if values
                else np.zeros((0, 4, 4), dtype=np.float64)
            )
            out[name] = MatrixArrayView(stacked)
            continue

        # All other types: per-element via read_plug_value, then cast
        # to numpy when the dtype is well-defined.
        values = _read_multi(
            plug, attr_obj, attr_type, sparse,
            lambda e: read_plug_value(e, attr_type, data_block=data_block),
        )
        if attr_type in ("float", "double", "doubleAngle", "doubleLinear",
                         "time"):
            out[name] = (
                np.asarray(values, dtype=np.float64)
                if values
                else np.zeros(0, dtype=np.float64)
            )
        elif attr_type in ("long", "enum"):
            out[name] = (
                np.asarray(values, dtype=np.int64)
                if values
                else np.zeros(0, dtype=np.int64)
            )
        elif attr_type == "bool":
            out[name] = (
                np.asarray(values, dtype=bool) if values else np.zeros(0, dtype=bool)
            )
        else:
            # string / pickle / mesh / nurbsCurve / nurbsSurface stay
            # as Python list (heterogeneous / non-stackable).
            out[name] = values
    return out


def _read_handle_value(handle, attr_type, attr_obj=None):
    """Read a single ``MDataHandle`` by USER ``attr_type`` -- thread-safe
    (no plug access). Returns a Python scalar, a 3-list
    (double3/euler/position/color), a 4-list (quaternion), a 4x4 nested list
    (matrix), or ``None`` on failure.

    This is the data-handle analogue of the plug read in
    :func:`read_user_inputs_dict`; it is used on the worker-thread compute
    path (Hypershade swatch / Arnold) where ``findPlug`` is unsafe.

    ``hex`` and ``pickle`` decode exactly as :func:`read_plug_value` does:
    hex to text, pickle through :func:`decode_python_string` -- the same trust
    gate (``None`` in an untrusted scene, so ``None`` is a real value here)
    and the same ``ValueError`` on a corrupt payload, which is NOT swallowed."""
    if attr_type in ("hex", "pickle"):
        try:
            raw = handle.asString() or ""
        except Exception:
            return None
        if attr_type == "pickle":
            return decode_python_string(raw)
        return decode_hex_string(raw)
    try:
        if attr_type == "float":
            # A "float" attr is MFnNumericData.kFloat. asDouble() on a kFloat
            # handle reads 4 bytes as 8 -> GARBAGE (no raise), so read kFloat
            # with asFloat() first.
            try:
                return float(handle.asFloat())
            except Exception:
                return float(handle.asDouble())
        if attr_type == "double":
            try:
                return float(handle.asDouble())
            except Exception:
                return float(handle.asFloat())
        if attr_type == "doubleAngle":
            try:
                return float(handle.asAngle().asRadians())
            except Exception:
                return float(handle.asDouble())
        if attr_type == "doubleLinear":
            try:
                return float(handle.asDistance().asCentimeters())
            except Exception:
                return float(handle.asDouble())
        if attr_type == "time":
            try:
                return float(handle.asTime().value)
            except Exception:
                return float(handle.asDouble())
        if attr_type == "enum":
            # EnumInt (int subclass) carries the attr MObject so
            # ``self.<enum>.name()`` yields the field label, keeping this
            # handle read type-identical to the plug read. ``attr_obj`` may be
            # None here; EnumInt.name() then falls back to the integer string.
            from mpynode._common.plugs.promoted_types import EnumInt

            try:
                return EnumInt(handle.asInt(), attr_obj)
            except Exception:
                return EnumInt(handle.asShort(), attr_obj)
        if attr_type == "long":
            try:
                return int(handle.asInt())
            except Exception:
                return int(handle.asShort())
        if attr_type == "short":
            return int(handle.asShort())
        if attr_type == "bool":
            return bool(handle.asBool())
        if attr_type == "string":
            return handle.asString()
        if attr_type in ("double3", "euler", "position"):
            # double3 numeric compound (euler XYZ children are doubleAngle,
            # stored as raw radian doubles; position XYZ are doubleLinear, raw
            # centimetre doubles -- matches the plug read).
            try:
                return [float(x) for x in handle.asDouble3()]
            except Exception:
                return [float(x) for x in handle.asFloat3()]
        if attr_type == "color":
            # float3 numeric compound.
            try:
                return [float(x) for x in handle.asFloat3()]
            except Exception:
                return [float(x) for x in handle.asDouble3()]
        if attr_type == "float2":
            # float2 numeric compound.
            try:
                return [float(x) for x in handle.asFloat2()]
            except Exception:
                return [float(x) for x in handle.asDouble2()]
        if attr_type == "quaternion":
            # Needs the attr object to tell the kinds apart (thread-safe).
            if attr_obj is None:
                return None
            if attr_obj.apiType() != om.MFn.kCompoundAttribute:
                # numeric double4 (X/Y/Z/W).
                return [float(x) for x in handle.asDouble4()]
            # legacy generic compound -- no numeric accessor; read the child
            # handles.
            cfn = om.MFnCompoundAttribute(attr_obj)
            return [
                float(handle.child(cfn.child(i)).asDouble())
                for i in range(cfn.numChildren())
            ]
        if attr_type == "matrix":
            if attr_obj is not None and attr_obj.hasFn(om.MFn.kTypedAttribute):
                # A typed ``-dt matrix`` plug, from a scene saved before
                # 2026-10: asMatrix() on its handle reads garbage memory, so
                # read its matrix DATA; unset (null data) reads as identity,
                # like read_plug_value.
                try:
                    m = om.MFnMatrixData(handle.data()).matrix()
                except Exception:
                    m = om.MMatrix()
            else:
                m = handle.asMatrix()
            return [[m.getElement(r, c) for c in range(4)] for r in range(4)]
        if attr_type in ("mesh", "nurbsCurve", "nurbsSurface"):
            # Geometry read STRAIGHT off the data handle: the EM-safe
            # acquisition the wrapper design mandates. Never a name/plug/DAG
            # re-resolve, which returns empty on an EM worker thread. The
            # unified wrapper keeps ``self.<geoInput>`` identical to the
            # main-thread read_plug_value path.
            try:
                if attr_type == "mesh":
                    geo_data = handle.asMesh()
                elif attr_type == "nurbsCurve":
                    geo_data = handle.asNurbsCurve()
                else:
                    geo_data = handle.asNurbsSurface()
            except Exception:
                return None
            if geo_data is None or geo_data.isNull():
                return None
            from mpynode._api2.geometry import Mesh, NurbsCurve, NurbsSurface

            if attr_type == "mesh":
                return Mesh._attach(geo_data)
            if attr_type == "nurbsCurve":
                return NurbsCurve._attach(geo_data)
            return NurbsSurface._attach(geo_data)
    except Exception:
        return None
    return None


def _cast_datablock_multi(values, attr_type):
    """Cast a dense per-element list (read via data handles) into the SAME
    numpy container :func:`read_user_inputs_dict` produces, so
    ``self.<array>`` is byte-for-byte identical on the worker-thread path."""
    if attr_type in ("double3", "euler", "position", "color"):
        return (
            np.asarray(values, dtype=np.float64)
            if values
            else np.zeros((0, 3), dtype=np.float64)
        )
    if attr_type == "float2":
        return (
            np.asarray(values, dtype=np.float64)
            if values
            else np.zeros((0, 2), dtype=np.float64)
        )
    if attr_type == "quaternion":
        return (
            np.asarray(values, dtype=np.float64)
            if values
            else np.zeros((0, 4), dtype=np.float64)
        )
    if attr_type == "matrix":
        from mpynode._common.plugs.promoted_types import MatrixArrayView

        stacked = (
            np.asarray(values, dtype=np.float64)
            if values
            else np.zeros((0, 4, 4), dtype=np.float64)
        )
        return MatrixArrayView(stacked)
    if attr_type in ("float", "double", "doubleAngle", "doubleLinear", "time"):
        return (
            np.asarray(values, dtype=np.float64)
            if values
            else np.zeros(0, dtype=np.float64)
        )
    if attr_type in ("long", "enum"):
        return (
            np.asarray(values, dtype=np.int64)
            if values
            else np.zeros(0, dtype=np.int64)
        )
    if attr_type == "bool":
        return np.asarray(values, dtype=bool) if values else np.zeros(0, dtype=bool)
    # string / pickle / mesh / nurbsCurve / nurbsSurface stay a Python list.
    return values


def read_user_inputs_dict_from_datablock(
    data_block: om.MDataBlock,
    node_obj:   om.MObject,
    attr_map:   dict,
) -> dict:
    """Thread-safe, DENSE variant of :func:`read_user_inputs_dict`.

    Reads every USER input through ``data_block`` handles -- the Maya API
    documented as thread-safe inside ``compute()`` -- so the expression is
    valid on Hypershade's swatch generator / Arnold sampling worker thread
    where ``MFnDependencyNode.findPlug`` may crash.

    Type contract MATCHES :func:`read_user_inputs_dict` exactly (scalars ->
    Python primitives; double3/euler/position/color -> ``np.ndarray (3,)``;
    float2 -> ``np.ndarray (2,)``; hex -> decoded text; pickle -> the
    trust-gated unpickled object; matrix -> ``MatrixView``; multi scalar ->
    ``np.ndarray (n,)``; multi double3/euler/position/color ->
    ``np.ndarray (n, 3)``; multi float2 -> ``np.ndarray (n, 2)``; multi matrix
    -> ``MatrixArrayView``), so
    ``self.<input>`` behaves identically on the main and worker threads. This
    is the C2 (dense input seeding) base-contract guarantee for the file node.

    Array (multi) inputs iterate ``data_block.inputArrayValue`` (thread-safe)
    and are DENSE by default (length ``max_logical+1``, gaps filled by
    :func:`array_gap_default`) unless the attr was declared ``sparse``.

    ``quaternion`` reads a double4 with ``asDouble4`` and a legacy generic
    compound through its child handles. Returns a dict keyed by attr name.
    """
    out: dict = {}
    # The MFnDependencyNode.attribute() MObject lookup is a stateless read
    # (safe on a worker thread); the findPlug + asXxx call tree is what's not.
    fn_node = om.MFnDependencyNode(node_obj)
    for name, meta in attr_map.items():
        attr_type = meta.get("attr_type", "double")
        is_array  = bool(meta.get("is_array", False))
        try:
            attr_obj = fn_node.attribute(name)
        except RuntimeError:
            continue
        if attr_obj.isNull():
            continue
        # The handle reads below return None for a name they don't know, and
        # None means "skip", so an unknown name would silently vanish from
        # ``self``. An alias reads as its stored name; anything else raises
        # read_plug_value's error.
        if (not isinstance(attr_type, str)
                or attr_type not in _ATTR_TYPES_BY_NAME):
            attr_type = canonical(attr_type)

        if not is_array:
            try:
                handle = data_block.inputValue(attr_obj)
            except Exception:
                continue
            val = _read_handle_value(handle, attr_type, attr_obj)
            # None is a real pickle value (empty, or an untrusted scene), and
            # the plug read hands it to the expression.
            if val is None and attr_type != "pickle":
                continue
            if attr_type in ("double3", "euler", "position", "color",
                             "float2", "quaternion"):
                out[name] = np.asarray(val, dtype=np.float64)
            elif attr_type == "matrix":
                from mpynode._common.plugs.promoted_types import MatrixView

                out[name] = MatrixView(np.asarray(val, dtype=np.float64))
            else:
                out[name] = val
            continue

        # PACKED array input -- one typed-array plug, so the whole table comes
        # back from a single handle instead of a per-element MArrayDataHandle
        # walk. Same flat sequence to the expression; no logical indices exist,
        # so there is nothing to scatter and no gap to fill.
        if meta.get("packed"):
            try:
                handle = data_block.inputValue(attr_obj)
                values = _read_packed_array(handle, attr_type)
            except Exception:
                values = []
            out[name] = _cast_datablock_multi(values, attr_type)
            continue

        # ARRAY (multi) input -- inputArrayValue is the thread-safe multi
        # accessor. Build a DENSE list scattered to logical indices, then cast.
        sparse = bool(meta.get("sparse", False))
        gap    = array_gap_default(attr_obj, attr_type)
        try:
            arr = data_block.inputArrayValue(attr_obj)
        except Exception:
            continue
        pairs = []  # (logical_index, value)
        # api2 MArrayDataHandle iterates via isDone()/next() and reports the
        # current logical index via elementLogicalIndex(). There is no
        # elementCount / jumpToPhysicalIndex on this class.
        while not arr.isDone():
            try:
                lidx = arr.elementLogicalIndex()
                elem = arr.inputValue()
            except Exception:
                arr.next()
                continue
            # Outside the try: a corrupt pickle payload raises, as it does
            # from the plug read. Every other failure already reads as None.
            val = _read_handle_value(elem, attr_type, attr_obj)
            pairs.append((lidx, gap if val is None else val))
            arr.next()
        if sparse:
            values = [v for _lidx, v in pairs]
        elif pairs:
            span   = max(lidx for lidx, _v in pairs) + 1
            values = [gap for _ in range(span)]
            for lidx, v in pairs:
                values[lidx] = v
        else:
            values = []
        out[name] = _cast_datablock_multi(values, attr_type)
    return out


def write_user_outputs(data_block, node_obj, output_map, locals_out, skip=()):
    """Commit every USER output (declared in ``_outputAttrs`` -> ``output_map``)
    that the expression actually set, reading values from the SelfProxy
    ``compute_locals`` snapshot.

    Shared by the specialized nodes (mPyFile, generators, deformers, ...) so
    they support arbitrary user-added outputs uniformly -- the same way
    mPyNode does -- on top of their own native outputs.

    ``skip`` = native output names the node already wrote itself (e.g.
    ``("outColor", "outAlpha")`` for mPyFile) so they aren't double-written.
    """
    fn_node = om.MFnDependencyNode(node_obj)
    for out_attr_name, meta in output_map.items():
        if out_attr_name in skip:
            continue
        # Self-only: an output is committed only when the expression assigns
        # ``self.out = ...`` (SelfProxy routes that into compute_locals). Bare
        # assignments are NOT harvested.
        if out_attr_name in locals_out:
            value = locals_out[out_attr_name]
        else:
            continue
        if value is None:
            continue
        try:
            attr      = fn_node.findPlug(out_attr_name, True).attribute()
            attr_type = meta.get("attr_type", "double")
            if bool(meta.get("is_array", False)):
                write_multi_plug_value(data_block, attr, attr_type, value)
            else:
                write_plug_value(
                    data_block, om.MPlug(node_obj, attr), attr_type, value
                )
        except Exception:
            pass
