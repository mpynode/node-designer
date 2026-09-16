"""Typed geometry-output constructors for the mPy geometry generators.

The mPy geometry generators (``mPyMesh`` / ``mPyNurbsCurve`` /
``mPyNurbsSurface``) hand a finished data object to their output plug
(``outMesh`` / ``outCurve`` / ``outSurface``). This module provides the
*canonical, validated* shapes a user constructs and assigns to that plug --
:class:`Mesh`, :class:`NurbsCurve`, :class:`NurbsSurface` -- plus the free
marshaller functions (:func:`build_mesh_data` etc.) that turn one into the
native ``MFn*Data`` MObject.

**Structural (duck) typing.** The plug does NOT require an instance of these
classes. A node's ``compute`` accepts *any* object exposing the required
attributes for its kind (mesh: ``points`` / ``counts`` / ``indices``), reads
the optionals if present, and rejects only when a *required* attribute is
missing. So a user's own ``Foo`` with ``.points`` / ``.counts`` / ``.indices``
marshals exactly like a :class:`Mesh`. The dataclasses remain the canonical
shape -- they give validation, cmd+click-able source, keyword-typo protection,
and the Output Builder default -- but they are a convenience, not a gate.

**Fail soft.** All validation lives in the marshaller free functions (so a
duck-typed ``Foo`` is validated identically to a :class:`Mesh`). Invalid or
empty geometry logs to stderr and returns an *empty* data MObject -- never
raises out of ``compute`` (matches the pre-existing contract).

**Normals / colors (mesh).** ``normals`` / ``colors`` are optional, each with
its own optional index array (independent -- Maya stores them as separate
face-vertex channels). The rule is symmetric for both:

* attr set, index ``None``  -> per-vertex (length must equal ``len(points)``)
* attr set, index set       -> per-face-vertex, indexed (index length must
  equal ``sum(counts)``, values index into the attr array)

``colors`` may be ``(*, 3)`` RGB (alpha defaults to 1.0) or ``(*, 4)`` RGBA;
``normals`` are always ``(*, 3)``.
"""
from __future__ import annotations

import json as _json
import sys

import numpy as np
import maya.api.OpenMaya as om


# ===========================================================================
# Small coercion helpers (best-effort, None on failure).
# ===========================================================================


def _log(msg: str) -> None:
    sys.stderr.write(msg if msg.endswith("\n") else msg + "\n")


def _as_points(arr, tag):
    """Coerce ``arr`` to an ``(N, 3)`` float64 array, or None."""
    if arr is None:
        return None
    try:
        out = np.asarray(arr, dtype=np.float64)
    except Exception:
        _log(f"[{tag}] points not float-coercible")
        return None
    if out.ndim != 2 or out.shape[1] != 3:
        _log(f"[{tag}] points must be (N, 3); got shape {out.shape}")
        return None
    return out


def _as_int_1d(arr):
    """Coerce ``arr`` to a flat int32 array, or None."""
    if arr is None:
        return None
    try:
        return np.asarray(arr, dtype=np.int32).flatten()
    except Exception:
        return None


def _source_node_name(plug):
    """Name of the node FEEDING ``plug``, or None.

    DISPLAY ONLY -- this is what lets a geometry object print as
    ``Mesh("pCubeShape1")`` instead of an anonymous blob. An attached object
    holds datablock DATA, which carries no identity of its own, so the identity
    has to come from the plug it was decoded off.

    Resolved LAZILY and cached by the caller: it must never cost anything on the
    compute hot path, only when something actually displays the object. An
    unconnected plug has no meaningful source -- return None and let the caller
    fall back to a structural summary rather than naming the consuming node
    (``mPyMesh1`` is not the name of the mesh).

    Not every geometry read can supply a plug: ``_read_handle_value`` is
    contracted plug-free for the worker-thread compute path (Hypershade swatch /
    Arnold), where plug access is unsafe. Objects decoded there carry
    ``source_plug=None`` and simply repr with their structural summary -- a
    display label is never worth weakening that contract.
    """
    if plug is None:
        return None
    try:
        src = plug.source()
        if src.isNull:
            return None
        return om.MFnDependencyNode(src.node()).name()
    except Exception:
        return None


def _as_vec_2d(arr, width_choices, tag, name):
    """Coerce ``arr`` to a 2D float array whose second dim is in
    ``width_choices`` (e.g. (3,) for normals, (3, 4) for colors). None on
    failure or empty."""
    if arr is None:
        return None
    try:
        out = np.asarray(arr, dtype=np.float64)
    except Exception:
        _log(f"[{tag}] {name} not float-coercible")
        return None
    if out.size == 0:
        return None
    if out.ndim != 2 or out.shape[1] not in width_choices:
        _log(f"[{tag}] {name} must be (M, {'|'.join(map(str, width_choices))}); "
             f"got shape {out.shape}")
        return None
    return out


# ===========================================================================
# Mesh
# ===========================================================================

_MESH_TAG = "mPyMesh"


def _face_vertex_enumeration(counts, indices):
    """Return ``(face_ids, vertex_ids)`` MIntArrays enumerating every
    face-vertex in flat order (face 0's verts, then face 1's, ...). ``vertex
    _ids[k]`` is the mesh vertex id of the k-th face-vertex; the k-th entry
    aligns with a per-face-vertex attribute array of length ``sum(counts)``."""
    face_ids   = om.MIntArray()
    vertex_ids = om.MIntArray()
    off        = 0
    for f, c in enumerate(int(x) for x in counts):
        for j in range(c):
            face_ids.append(f)
            vertex_ids.append(int(indices[off + j]))
        off += c
    return face_ids, vertex_ids


def _apply_mesh_normals(mfn, n_points, counts, indices, normals, normal_indices):
    """Assign per-vertex or per-face-vertex normals to a built mesh."""
    nrm = _as_vec_2d(normals, (3,), _MESH_TAG, "normals")
    if nrm is None:
        return
    total_fv = int(np.sum(counts))
    idx      = _as_int_1d(normal_indices)
    try:
        if idx is None:
            # Per-vertex: one normal per mesh vertex.
            if nrm.shape[0] != n_points:
                _log(f"[{_MESH_TAG}] per-vertex normals need len == "
                     f"{n_points}; got {nrm.shape[0]}; skipped")
                return
            vec = om.MVectorArray([om.MVector(float(a), float(b), float(c))
                                   for a, b, c in nrm])
            vids = om.MIntArray(list(range(n_points)))
            mfn.setVertexNormals(vec, vids)
        else:
            # Per-face-vertex, indexed: expand nrm[idx] over the face-vertices.
            if idx.shape[0] != total_fv:
                _log(f"[{_MESH_TAG}] normal_indices len {idx.shape[0]} != "
                     f"sum(counts) {total_fv}; skipped")
                return
            if idx.min(initial=0) < 0 or (idx.size and idx.max() >= nrm.shape[0]):
                _log(f"[{_MESH_TAG}] normal_indices out of range; skipped")
                return
            expanded = nrm[idx]
            vec = om.MVectorArray([om.MVector(float(a), float(b), float(c))
                                   for a, b, c in expanded])
            face_ids, vertex_ids = _face_vertex_enumeration(counts, indices)
            mfn.setFaceVertexNormals(vec, face_ids, vertex_ids)
    except Exception as exc:
        _log(f"[{_MESH_TAG}] normal assignment failed: {exc}")


def _apply_mesh_colors(mfn, n_points, counts, indices, colors, color_indices):
    """Assign per-vertex or per-face-vertex colors to a built mesh.

    Uses ``setVertexColors`` / ``setFaceVertexColors`` (which auto-create the
    default color set) -- ``createColorSet`` + ``assignColors`` fails with
    "Object does not exist" on a mesh parented to an ``MFnMeshData`` (the DG
    output data object), so colors never actually landed on the old path."""
    col = _as_vec_2d(colors, (3, 4), _MESH_TAG, "colors")
    if col is None:
        return
    total_fv = int(np.sum(counts))
    cidx     = _as_int_1d(color_indices)
    # Normalise to RGBA (alpha 1.0 for RGB input).
    if col.shape[1] == 3:
        col = np.concatenate([col, np.ones((col.shape[0], 1),
                                           dtype=np.float64)], axis=1)

    def _mcolor(c):
        return om.MColor((float(c[0]), float(c[1]), float(c[2]), float(c[3])))

    try:
        if cidx is None:
            # Per-vertex: one color per mesh vertex.
            if col.shape[0] != n_points:
                _log(f"[{_MESH_TAG}] per-vertex colors need len == "
                     f"{n_points}; got {col.shape[0]}; skipped")
                return
            carr = om.MColorArray([_mcolor(c) for c in col])
            mfn.setVertexColors(carr, om.MIntArray(list(range(n_points))))
        else:
            # Per-face-vertex, indexed: expand col[cidx] over the face-vertices.
            if cidx.shape[0] != total_fv:
                _log(f"[{_MESH_TAG}] color_indices len {cidx.shape[0]} != "
                     f"sum(counts) {total_fv}; skipped")
                return
            if cidx.min(initial=0) < 0 or (cidx.size and cidx.max() >= col.shape[0]):
                _log(f"[{_MESH_TAG}] color_indices out of range; skipped")
                return
            expanded = col[cidx]
            carr     = om.MColorArray([_mcolor(c) for c in expanded])
            face_ids, vertex_ids = _face_vertex_enumeration(counts, indices)
            mfn.setFaceVertexColors(carr, face_ids, vertex_ids)
    except Exception as exc:
        _log(f"[{_MESH_TAG}] color assignment failed: {exc}")


def _apply_mesh_uvs(mfn, counts, uv_sets):
    """Assign UVs to a built mesh from the ``UVSet`` list the reader produces.

    DEFAULT SET ONLY. ``MFnMesh.create`` auto-creates ``map1`` and
    ``setUVs`` + ``assignUVs`` against it work on a mesh parented to an
    ``MFnMeshData``; ``createUVSet`` does NOT -- it raises "Object does not
    exist" there, the same failure ``_apply_mesh_colors`` records for
    ``createColorSet``. Measured on Maya 2026, cube parented to MFnMeshData:
    default set round-trips 24 UVs, ``createUVSet("secondSet")`` raises. Extra
    sets are therefore logged and skipped rather than silently dropped.
    (``create(uValues=, vValues=)`` seeds the points but leaves ZERO assigned
    ids, so it is no shortcut -- assignUVs is required either way.)

    Fail-soft like every other marshaller here: logs and returns, never raises
    out of compute.
    """
    if not uv_sets:
        return
    try:
        sets = list(uv_sets)
    except Exception:
        return
    if not sets:
        return
    if len(sets) > 1:
        _log(f"[{_MESH_TAG}] {len(sets) - 1} extra UV set(s) skipped: "
             f"createUVSet is not available on an output data mesh; only the "
             f"default set is written")

    uv = sets[0]
    try:
        pts     = np.asarray(uv.points,  dtype=np.float64)
        ucounts = np.asarray(uv.counts,  dtype=np.int64)
        uidx    = np.asarray(uv.indices, dtype=np.int64)
    except Exception as exc:
        _log(f"[{_MESH_TAG}] UV set is not array-like: {exc}; skipped")
        return

    if pts.ndim != 2 or pts.shape[1] != 2 or pts.shape[0] == 0:
        _log(f"[{_MESH_TAG}] UV points must be (M, 2); got {pts.shape}; skipped")
        return
    # The UV face layout must match the mesh's OWN face layout, or assignUVs
    # writes garbage: a rebuilt mesh whose topology changed keeps stale UVs.
    if ucounts.shape[0] != len(counts) or \
            not np.array_equal(ucounts, np.asarray(counts, dtype=np.int64)):
        _log(f"[{_MESH_TAG}] UV counts do not match the mesh face layout "
             f"({ucounts.shape[0]} vs {len(counts)}); UVs skipped")
        return
    if uidx.shape[0] != int(ucounts.sum()):
        _log(f"[{_MESH_TAG}] UV indices length {uidx.shape[0]} != sum(counts) "
             f"{int(ucounts.sum())}; UVs skipped")
        return
    if uidx.size and (uidx.min() < 0 or uidx.max() >= pts.shape[0]):
        _log(f"[{_MESH_TAG}] UV indices out of range for {pts.shape[0]} UVs; "
             f"skipped")
        return

    try:
        mfn.setUVs([float(u) for u in pts[:, 0]],
                   [float(v) for v in pts[:, 1]])
        mfn.assignUVs([int(c) for c in ucounts], [int(i) for i in uidx])
    except Exception as exc:
        _log(f"[{_MESH_TAG}] UV assignment failed: {exc}")


def build_mesh_data(obj):
    """Marshal a mesh-like object into an ``MFnMeshData`` MObject.

    ``obj`` need only expose ``points`` / ``counts`` / ``indices`` (duck
    typing). Optional attrs read if present: ``normals`` / ``normal_indices``
    / ``colors`` / ``color_indices``. Returns an empty (but valid) data
    MObject on any failure or empty input -- never raises.
    """
    data_obj = om.MFnMeshData().create()

    points   = _as_points(getattr(obj, "points", None), _MESH_TAG)
    counts   = _as_int_1d(getattr(obj, "counts", None))
    indices  = _as_int_1d(getattr(obj, "indices", None))

    if points is None or counts is None or indices is None:
        return data_obj
    if points.shape[0] == 0 or counts.shape[0] == 0:
        return data_obj

    expected_idx = int(counts.sum())
    if expected_idx != indices.shape[0]:
        _log(f"[{_MESH_TAG}] indices length {indices.shape[0]} != "
             f"sum(counts) {expected_idx}; empty mesh.")
        return data_obj
    if (counts < 3).any():
        _log(f"[{_MESH_TAG}] counts has entries < 3 (degenerate faces); "
             "empty mesh.")
        return data_obj
    n_points = int(points.shape[0])
    if (indices < 0).any() or (indices >= n_points).any():
        _log(f"[{_MESH_TAG}] indices has out-of-range vertex ids; empty mesh.")
        return data_obj

    try:
        pts_array = om.MPointArray([om.MPoint(float(p[0]), float(p[1]),
                                              float(p[2])) for p in points])
        mfn = om.MFnMesh()
        mfn.create(pts_array, [int(c) for c in counts],
                   [int(i) for i in indices], parent=data_obj)
    except Exception as exc:
        _log(f"[{_MESH_TAG}] MFnMesh.create failed: {exc}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return om.MFnMeshData().create()

    _apply_mesh_normals(mfn, n_points, counts, indices,
                        getattr(obj, "normals", None),
                        getattr(obj, "normal_indices", None))
    _apply_mesh_colors(mfn, n_points, counts, indices,
                       getattr(obj, "colors", None),
                       getattr(obj, "color_indices", None))
    _apply_mesh_uvs(mfn, counts, getattr(obj, "uv_sets", None))
    return data_obj


# ===========================================================================
# NURBS curve
# ===========================================================================

_CURVE_TAG     = "mPyNurbsCurve"
_VALID_DEGREES = (1, 2, 3, 5, 7)


def _expected_knots(num_cvs, degree):
    """Knot count Maya's ``MFn*::create`` expects: ``num_cvs + degree - 1``
    for BOTH open and periodic forms (verified against a stock periodic
    circle: 11 CVs, degree 3 -> 13 knots = 11 + 3 - 1)."""
    return num_cvs + degree - 1


_CURVE_FORM_BY_NAME = {
    "open":     om.MFnNurbsCurve.kOpen,
    "closed":   om.MFnNurbsCurve.kClosed,
    "periodic": om.MFnNurbsCurve.kPeriodic,
}


def _resolve_curve_form(obj):
    """Return ``(form_kind, periodic_bool)``.

    Honors an optional legacy ``form`` attribute (a string
    ``"open"``/``"closed"``/``"periodic"`` or an int ``MFnNurbsCurve`` form
    constant) which the ``build_default_output`` shim passes through so the
    ``closed`` form the periodic-only :class:`NurbsCurve` can't express is not
    lost. If ``form`` is absent (the dataclass case) it falls back to the
    ``periodic`` bool. ``periodic_bool`` drives uniform knot generation
    (clamped vs continuous), so ``closed`` -> ``False`` -> clamped knots,
    matching the legacy marshaller."""
    form = getattr(obj, "form", None)
    if form is not None:
        if isinstance(form, str):
            kind = _CURVE_FORM_BY_NAME.get(form.lower(), om.MFnNurbsCurve.kOpen)
        elif isinstance(form, int) and not isinstance(form, bool):
            kind = int(form)
        else:
            kind = om.MFnNurbsCurve.kOpen
        return kind, (kind == om.MFnNurbsCurve.kPeriodic)
    periodic = bool(getattr(obj, "periodic", False))
    return (om.MFnNurbsCurve.kPeriodic if periodic
            else om.MFnNurbsCurve.kOpen), periodic


def _curve_uniform_knots(num_cvs, degree, periodic):
    """Uniform knot vector, length ``num_cvs + degree - 1`` for both forms.
    Open: clamped (multiplicity ``degree`` at the ends). Periodic: continuous
    integers ``[-degree+1 .. num_cvs-1]`` (matches Maya's periodic convention;
    the caller must supply CVs that already wrap)."""
    n_knots = _expected_knots(num_cvs, degree)
    if n_knots <= 0:
        return []
    if periodic:
        return [float(i - degree + 1) for i in range(n_knots)]
    inner = max(n_knots - 2 * degree, 0)
    knots = [0.0] * degree
    knots.extend(float(i + 1) for i in range(inner))
    knots.extend([float(inner + 1)] * degree)
    return knots[:n_knots]


def build_curve_data(obj):
    """Marshal a curve-like object into an ``MFnNurbsCurveData`` MObject.

    Required attr: ``points`` (CV positions, ``(N, 3)``). Optional: ``degree``
    (default 3), ``periodic`` (default False), ``kv`` (knot vector; auto if
    None or wrong length). An optional legacy ``form`` attribute
    (``"open"``/``"closed"``/``"periodic"``) overrides ``periodic`` -- the
    ``build_default_output`` shim uses it to keep the ``closed`` form
    reachable. Returns an empty data MObject on failure.
    """
    data_obj = om.MFnNurbsCurveData().create()

    cvs = _as_points(getattr(obj, "points", None), _CURVE_TAG)
    if cvs is None or cvs.shape[0] == 0:
        return data_obj

    degree = getattr(obj, "degree", 3)
    degree = int(degree) if degree is not None else 3
    if degree not in _VALID_DEGREES:
        _log(f"[{_CURVE_TAG}] invalid degree {degree}; defaulting to 3")
        degree = 3

    form_kind, periodic = _resolve_curve_form(obj)
    num_cvs = int(cvs.shape[0])
    if num_cvs < degree + 1:
        _log(f"[{_CURVE_TAG}] need at least degree+1 CVs ({degree + 1}); "
             f"got {num_cvs}; empty curve")
        return data_obj

    kv = getattr(obj, "kv", None)
    if kv is None:
        knot_list = _curve_uniform_knots(num_cvs, degree, periodic)
    else:
        try:
            knot_list = [float(k) for k in
                         np.asarray(kv, dtype=np.float64).flatten()]
        except Exception:
            knot_list = _curve_uniform_knots(num_cvs, degree, periodic)

    expected = _expected_knots(num_cvs, degree)
    if len(knot_list) != expected:
        if kv is not None:
            _log(f"[{_CURVE_TAG}] knot count {len(knot_list)} != expected "
                 f"{expected}; rebuilding uniform")
        knot_list = _curve_uniform_knots(num_cvs, degree, periodic)

    try:
        pts_array = om.MPointArray([om.MPoint(float(p[0]), float(p[1]),
                                              float(p[2])) for p in cvs])
        knot_array = om.MDoubleArray([float(k) for k in knot_list])
        om.MFnNurbsCurve().create(pts_array, knot_array, degree, form_kind,
                                  False, False, data_obj)
    except Exception as exc:
        _log(f"[{_CURVE_TAG}] MFnNurbsCurve.create failed: {exc}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return om.MFnNurbsCurveData().create()
    return data_obj


# ===========================================================================
# NURBS surface
# ===========================================================================

_SURFACE_TAG = "mPyNurbsSurface"


def _coerce_surface_cvs(cvs, num_u, num_v):
    """Return ``((N, 3) float64, num_u, num_v)`` or ``(None, 0, 0)``. Accepts
    an ``(nu, nv, 3)`` grid (U-major) or a flat ``(nu*nv, 3)`` array (then
    ``num_u`` / ``num_v`` are required)."""
    if cvs is None:
        return None, 0, 0
    try:
        arr = np.asarray(cvs, dtype=np.float64)
    except Exception:
        return None, 0, 0
    if arr.ndim == 3 and arr.shape[2] == 3:
        u, v = int(arr.shape[0]), int(arr.shape[1])
        return arr.reshape(u * v, 3), u, v
    if arr.ndim == 2 and arr.shape[1] == 3:
        if num_u is None or num_v is None:
            _log(f"[{_SURFACE_TAG}] flat CVs (N, 3) require num_u + num_v; "
                 f"got shape {arr.shape}")
            return None, 0, 0
        u, v = int(num_u), int(num_v)
        if u * v != arr.shape[0]:
            _log(f"[{_SURFACE_TAG}] num_u * num_v ({u}*{v}={u * v}) != "
                 f"rows ({arr.shape[0]})")
            return None, 0, 0
        return arr, u, v
    _log(f"[{_SURFACE_TAG}] points must be (U, V, 3) or (N, 3); "
         f"got {arr.shape}")
    return None, 0, 0


_SURFACE_FORM_BY_NAME = {
    "open":     om.MFnNurbsSurface.kOpen,
    "closed":   om.MFnNurbsSurface.kClosed,
    "periodic": om.MFnNurbsSurface.kPeriodic,
}


def _resolve_surface_form(obj, form_attr, periodic_attr):
    """Per-direction analogue of :func:`_resolve_curve_form`. ``form_attr`` is
    ``"form_u"`` / ``"form_v"`` (legacy shim override); ``periodic_attr`` is
    ``"periodic_u"`` / ``"periodic_v"`` (dataclass field)."""
    form = getattr(obj, form_attr, None)
    if form is not None:
        if isinstance(form, str):
            kind = _SURFACE_FORM_BY_NAME.get(form.lower(),
                                             om.MFnNurbsSurface.kOpen)
        elif isinstance(form, int) and not isinstance(form, bool):
            kind = int(form)
        else:
            kind = om.MFnNurbsSurface.kOpen
        return kind, (kind == om.MFnNurbsSurface.kPeriodic)
    periodic = bool(getattr(obj, periodic_attr, False))
    return (om.MFnNurbsSurface.kPeriodic if periodic
            else om.MFnNurbsSurface.kOpen), periodic


def _resolve_degree(degree, label):
    degree = int(degree) if degree is not None else 3
    if degree not in _VALID_DEGREES:
        _log(f"[{_SURFACE_TAG}] invalid {label}={degree}; defaulting to 3")
        return 3
    return degree


def _surface_knots(num_cvs, degree, periodic, kv, label):
    if kv is not None:
        try:
            kl = [float(k) for k in np.asarray(kv, dtype=np.float64).flatten()]
        except Exception:
            kl = None
        if kl is not None:
            expected = _expected_knots(num_cvs, degree)
            if len(kl) == expected:
                return kl
            _log(f"[{_SURFACE_TAG}] {label} count {len(kl)} != expected "
                 f"{expected}; rebuilding uniform")
    return _curve_uniform_knots(num_cvs, degree, periodic)


def build_surface_data(obj):
    """Marshal a surface-like object into an ``MFnNurbsSurfaceData`` MObject.

    Required attr: ``points`` (``(nu, nv, 3)`` grid or ``(nu*nv, 3)`` flat).
    Optional: ``degree_u`` / ``degree_v`` (default 3), ``periodic_u`` /
    ``periodic_v`` (default False), ``kv_u`` / ``kv_v`` (auto if None/wrong
    length), ``num_u`` / ``num_v`` (required only for flat points). Optional
    legacy ``form_u`` / ``form_v`` attributes
    (``"open"``/``"closed"``/``"periodic"``) override ``periodic_u`` /
    ``periodic_v`` (used by the ``build_default_output`` shim).
    """
    data_obj = om.MFnNurbsSurfaceData().create()

    cvs, num_u, num_v = _coerce_surface_cvs(
        getattr(obj, "points", None),
        getattr(obj, "num_u", None), getattr(obj, "num_v", None))
    if cvs is None or cvs.shape[0] == 0:
        return data_obj

    degree_u = _resolve_degree(getattr(obj, "degree_u", 3), "degree_u")
    degree_v = _resolve_degree(getattr(obj, "degree_v", 3), "degree_v")
    form_u, periodic_u = _resolve_surface_form(obj, "form_u", "periodic_u")
    form_v, periodic_v = _resolve_surface_form(obj, "form_v", "periodic_v")

    if num_u < degree_u + 1 or num_v < degree_v + 1:
        _log(f"[{_SURFACE_TAG}] need (degree+1) CVs each direction; "
             f"got u={num_u}/d={degree_u}, v={num_v}/d={degree_v}")
        return data_obj

    knots_u = _surface_knots(num_u, degree_u, periodic_u,
                             getattr(obj, "kv_u", None), "kv_u")
    knots_v = _surface_knots(num_v, degree_v, periodic_v,
                             getattr(obj, "kv_v", None), "kv_v")

    try:
        pts_array = om.MPointArray([om.MPoint(float(p[0]), float(p[1]),
                                              float(p[2])) for p in cvs])
        ku  = om.MDoubleArray([float(k) for k in knots_u])
        kvv = om.MDoubleArray([float(k) for k in knots_v])
        om.MFnNurbsSurface().create(pts_array, ku, kvv, degree_u, degree_v,
                                    form_u, form_v, False, data_obj)
    except Exception as exc:
        _log(f"[{_SURFACE_TAG}] MFnNurbsSurface.create failed: {exc}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return om.MFnNurbsSurfaceData().create()
    return data_obj


# ===========================================================================
# Unified geometry objects (Mesh / NurbsCurve / NurbsSurface). One type serves
# inputs (attached read: lazy numpy + delegating .fn) and outputs (value bucket
# marshalled by the build_*_data functions above). Validation lives in the
# marshallers, so a duck-typed object validates identically.
# ===========================================================================


# Component-tag decode. Single-indexed (one int per element): mesh vtx / edge /
# face / uv AND NURBS *curve* CVs. Double-indexed (a ``(u, v)`` pair): NURBS
# *surface* CVs, decoded separately via ``MFnDoubleIndexedComponent``.
_COMP_TYPE = {
    om.MFn.kMeshVertComponent: "vertex",
    om.MFn.kMeshEdgeComponent: "edge",
    om.MFn.kMeshPolygonComponent: "face",
    om.MFn.kMeshMapComponent: "uv",
    om.MFn.kCurveCVComponent: "cv",
}

_DOUBLE_COMP_TYPE = {
    om.MFn.kSurfaceCVComponent: "cv",
}


def _decode_single_component(comp):
    """Decode a single-indexed component MObject into ``(type_str, indices)``.
    ``indices`` is a flat ``(K,)`` int64 array."""
    if comp is None or comp.isNull():
        return "unknown", np.empty(0, dtype=np.int64)
    typ = _COMP_TYPE.get(comp.apiType(), "unknown")
    try:
        sic = om.MFnSingleIndexedComponent(comp)
        idx = np.asarray(sic.getElements(), dtype=np.int64)
    except Exception:
        idx = np.empty(0, dtype=np.int64)
    return typ, idx


def _decode_double_component(comp):
    """Decode a double-indexed component MObject (NURBS surface CVs) into
    ``(type_str, indices)`` where ``indices`` is a ``(K, 2)`` int64 array of
    ``(u, v)`` grid coordinates.

    api2 ``MFnDoubleIndexedComponent.getElements()`` returns a *list of
    ``(u, v)`` tuples* on Maya 2026 (verified empirically); older/other builds
    document a ``(uList, vList)`` 2-tuple. Both forms are handled."""
    if comp is None or comp.isNull():
        return "unknown", np.empty((0, 2), dtype=np.int64)
    typ = _DOUBLE_COMP_TYPE.get(comp.apiType(), "unknown")
    try:
        dic = om.MFnDoubleIndexedComponent(comp)
        els = dic.getElements()
        # Distinguish the two return shapes: a (uList, vList) 2-tuple whose
        # first entry is itself a sequence of ints, vs a list of (u, v) pairs.
        if (isinstance(els, tuple) and len(els) == 2
                and hasattr(els[0], "__len__")):
            u = np.asarray(list(els[0]), dtype=np.int64)
            v = np.asarray(list(els[1]), dtype=np.int64)
            idx = (np.column_stack([u, v]) if u.size
                   else np.empty((0, 2), dtype=np.int64))
        else:
            pairs = list(els)
            idx = (np.asarray(pairs, dtype=np.int64) if pairs
                   else np.empty((0, 2), dtype=np.int64))
            if idx.ndim == 1:
                idx = idx.reshape(-1, 2)
    except Exception:
        idx = np.empty((0, 2), dtype=np.int64)
    return typ, idx


class UVSet:
    """One UV set of a mesh, exposed as a standalone 2D "mesh".

    A mesh's UVs are a per-face-vertex channel living in their OWN 2D index space
    (a vertex on a UV seam is split into several distinct UV points), so a UV set
    is naturally its own little mesh -- flat, no normals. It mirrors the
    :class:`Mesh` ``points`` / ``counts`` / ``indices`` convention exactly, but in
    the UV index space:

      * ``name``    -- the Maya UV-set name (e.g. ``"map1"``); reference a set by
                       name.
      * ``points``  -- ``(M, 2)`` float64, the (u, v) coordinates.
      * ``counts``  -- ``(F,)`` int64, uv-verts per face (parallels the mesh's
                       per-face vertex counts).
      * ``indices`` -- ``(sum(counts),)`` int64, flat uvIds into ``points``
                       (parallels the mesh's flat vertex connectivity).

    ``num_uvs`` == ``len(points)`` and generally differs from the mesh's vertex
    count. A plain value bucket (no live function set). Use :meth:`as_mesh` to get
    a real 2D :class:`Mesh` (padded to ``(u, v, 0.0)``, unmapped faces dropped) if
    you want to flow the layout through the mesh marshaller / an output plug.
    """

    __slots__ = ("name", "points", "counts", "indices")

    def __init__(self, name, points=None, counts=None, indices=None):
        self.name = name
        self.points = (np.empty((0, 2), dtype=np.float64) if points is None
                       else np.asarray(points, dtype=np.float64))
        self.counts = (np.empty(0, dtype=np.int64) if counts is None
                       else np.asarray(counts, dtype=np.int64))
        self.indices = (np.empty(0, dtype=np.int64) if indices is None
                        else np.asarray(indices, dtype=np.int64))

    @property
    def num_uvs(self):
        return int(self.points.shape[0])

    def __repr__(self):
        return "UVSet(name=%r, num_uvs=%d, faces=%d)" % (
            self.name, self.num_uvs, int(self.counts.shape[0]))

    def to_json(self):
        return {"type": "UVSet", "name": self.name,
                "points": _jlist(self.points), "counts": _jlist(self.counts),
                "indices": _jlist(self.indices)}

    @classmethod
    def from_json(cls, payload):
        if isinstance(payload, (str, bytes)):
            payload = _json.loads(payload)
        return cls(payload.get("name"), payload.get("points"),
                   payload.get("counts"), payload.get("indices"))

    def as_mesh(self):
        """A detached 2D :class:`Mesh` value: UV points padded to ``(u, v, 0.0)``
        with unmapped faces (uv-vert count < 3) dropped, so it satisfies the mesh
        marshaller's ``(N,3)`` / ``counts>=3`` requirements. Returns an
        (empty-but-valid) Mesh when the set has no usable faces."""
        pts2 = self.points
        pts3 = np.zeros((int(pts2.shape[0]), 3), dtype=np.float64)
        if pts2.shape[0]:
            pts3[:, :2] = pts2
        keep_counts  = []
        keep_indices = []
        off          = 0
        for c in self.counts.tolist():
            c = int(c)
            if c >= 3:
                keep_counts.append(c)
                keep_indices.extend(int(x) for x in self.indices[off:off + c])
            off += c
        return Mesh(points=pts3,
                    counts=np.asarray(keep_counts, dtype=np.int64),
                    indices=np.asarray(keep_indices, dtype=np.int64))


def _looks_like_morph(obj):
    """Duck-type test for a sparse offset field (``mpynode._api2.morph.Morph``
    and anything shaped like it). Deliberately NOT an isinstance check so
    geometry.py stays independent of morph.py."""
    return hasattr(obj, "indices") and hasattr(obj, "offsets")


# The 27 cells a coincident partner can occupy when the grid step IS the
# tolerance (own cell + the 26 that touch it).
_CELL_NEIGHBOURS = np.array(
    [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)],
    dtype=np.int64)


def _cell_keys(cells):
    """Fold ``(N, 3)`` integer cell coordinates down to ONE int64 key each.

    21 bits per axis keeps every product inside int64. A fold COLLISION only
    adds candidate pairs -- each candidate is confirmed by the real distance --
    so the answer never depends on the fold."""
    k = cells & 0x1FFFFF
    return (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)


def _points_within(points, other_points, tolerance):
    """Indices of the ``points`` rows lying within Euclidean ``tolerance`` of
    ANY row of ``other_points``.

    This is the predicate the reference ``MeshData.difference`` gets from
    ``scipy.spatial.cKDTree(other).query(points)[0] <= tolerance`` -- the
    NEAREST neighbour is inside the tolerance exactly when SOME neighbour is.
    scipy is an optional external package and this is a core wrapper, so the
    same predicate is computed with a uniform spatial hash instead. The grid
    step IS the tolerance, so a matching pair can only land in the same cell or
    one of the 26 touching it: the 27-cell scan is EXACT, not an approximation.
    """
    n = int(points.shape[0])
    if n == 0 or other_points.shape[0] == 0:
        return np.zeros(0, dtype=np.int64)
    tol = float(tolerance)
    # A zero tolerance (exact coincidence) still needs a positive grid step;
    # identical coordinates floor into the identical cell at any step.
    step        = tol if tol > 0.0 else 1e-12
    origin      = other_points.min(axis=0)
    q_cells     = np.floor((points - origin) / step).astype(np.int64)
    t_keys      = _cell_keys(np.floor((other_points - origin) / step).astype(np.int64))
    order       = np.argsort(t_keys, kind="stable")
    sorted_keys = t_keys[order]

    hit = np.zeros(n, dtype=bool)
    for offset in _CELL_NEIGHBOURS:
        keys = _cell_keys(q_cells + offset)
        lo   = np.searchsorted(sorted_keys, keys, side="left")
        run  = np.searchsorted(sorted_keys, keys, side="right") - lo
        rows = np.flatnonzero(run > 0)
        if rows.size == 0:
            continue
        lens = run[rows]
        # Ragged gather: expand each query's run of candidates into a flat pair
        # list, then keep the pairs that are really inside the tolerance.
        total      = int(lens.sum())
        q_idx      = np.repeat(rows, lens)
        within_run = np.arange(total) - np.repeat(np.cumsum(lens) - lens, lens)
        t_idx      = order[np.repeat(lo[rows], lens) + within_run]
        d          = points[q_idx] - other_points[t_idx]
        hit[q_idx[np.sqrt((d * d).sum(axis=1)) <= tol]] = True
    return np.flatnonzero(hit).astype(np.int64)


class Mesh:
    """A mesh geometry object -- the SAME type on inputs and outputs.

    Two modes:

    * **Attached** (what an input plug hands you): holds the retained geometry
      DATA MObject and lazily mints an ``MFnMesh`` from it. The numpy read
      surface (``points`` / ``counts`` / ``indices`` / ``normals`` / ``colors``
      / ``component_tags``) is materialized on first access and cached. EM-safe
      because the data comes from the datablock, never a name/plug re-resolve.
    * **Value** (what you construct or ``copy()``): a plain arrays bucket you
      assign to an output plug. ``build_mesh_data`` marshals it (duck-typed).

    Self-sufficient: everything the ``mpynode._common.nodes.mesh`` helpers
    provided is a member here -- ``mesh_arrays`` -> ``points``/``counts``/
    ``indices``, ``mesh_vertex_normals`` -> ``normals``, region/tag helpers ->
    ``component_tags`` + ``region(tag)``. The raw function set is ``fn`` (any
    ``MFn*`` method also works directly via delegation, e.g. ``mesh.getPoints()``
    keeps working). ``copy()`` returns a detached editable value you can send to
    an output with NO imports:

        out = self.inMesh.copy(); out.points = out.points * 2; self.outMesh = out

    Required for a value/output mesh: ``points`` (N,3), ``counts`` (F,),
    ``indices`` (sum(counts),). Optional: ``normals`` / ``normal_indices``,
    ``colors`` / ``color_indices`` (per-vertex vs per-face-vertex -- see module
    docstring).
    """

    def __init__(self, points=None, counts=None, indices=None,
                 normals=None, normal_indices=None,
                 colors=None, color_indices=None):
        self._attached = False
        self._data     = None  # retained api2 geometry DATA MObject
        self._fn       = None  # cached MFnMesh (attached mode)
        self._tags     = None  # cached component_tags dict
        self._uv_sets  = None  # cached list[UVSet] (attached mode)

        # Construction niceties, INTERPRETED mode only -- attached mode bypasses
        # __init__ via _attach, and a compiled compute rewrites geo constructors
        # positionally, so these are not lowered:
        #   * Mesh(uv_set) -- a UVSet as the first arg (no counts/indices)
        #     builds the UV layout as a 2D mesh. Delegates to UVSet.as_mesh() so
        #     the z-pad + drop-small-face logic lives in one place.
        #   * a ``(M, 2)`` points array is padded with z=0 to ``(M, 3)``.
        if (points is not None and counts is None and indices is None
                and isinstance(points, UVSet)):
            src = points.as_mesh()
            points, counts, indices = src._points, src._counts, src._indices
        elif points is not None:
            points = np.asarray(points, dtype=np.float64)
            if points.ndim == 2 and points.shape[1] == 2:
                pad        = np.zeros((points.shape[0], 3), dtype=np.float64)
                pad[:, :2] = points
                points     = pad

        self._points        = None if points is None else np.asarray(points, dtype=np.float64)
        self._counts        = None if counts is None else np.asarray(counts, dtype=np.int64)
        self._indices       = None if indices is None else np.asarray(indices, dtype=np.int64)
        self._normals       = None if normals is None else np.asarray(normals, dtype=np.float64)
        self.normal_indices = normal_indices
        self._colors        = None if colors is None else np.asarray(colors, dtype=np.float64)
        self.color_indices  = color_indices

    @classmethod
    def _attach(cls, data_mobject, source_plug=None):
        """Build an ATTACHED mesh from a geometry DATA MObject (the EM-safe
        handle sourced off the datablock).

        ``source_plug`` is kept for DISPLAY only -- :attr:`name` resolves the
        upstream shape's name off it lazily so the mesh reprs as
        ``Mesh("pCubeShape1")``. It is never used to re-resolve DATA.
        """
        m                = cls.__new__(cls)
        m._attached      = True
        m._data          = data_mobject
        m._fn            = None
        m._tags          = None
        m._uv_sets       = None
        m._points        = None
        m._counts        = None
        m._indices       = None
        m._normals       = None
        m.normal_indices = None
        m._colors        = None
        m.color_indices  = None
        m._src_plug      = source_plug
        m._name          = None
        return m

    @property
    def name(self):
        """Name of the shape feeding this mesh, or None for a value mesh.

        Lazy + cached: costs nothing until something displays the object.

        Shadows the ``MFnMesh.name`` that ``__getattr__`` would otherwise
        delegate to -- that one is built from geometry DATA rather than a
        dependency node, so calling it raises "Object does not exist". Nothing
        working is lost.
        """
        nm = self.__dict__.get("_name")
        if nm is None:
            nm                     = _source_node_name(self.__dict__.get("_src_plug"))
            self.__dict__["_name"] = nm
        return nm

    # ----- raw function set + delegation -----
    @property
    def fn(self):
        """The live ``MFnMesh`` (attached mode), or None if detached/empty."""
        f = self.__dict__.get("_fn")
        if f is None:
            d = self.__dict__.get("_data")
            if d is not None and not d.isNull():
                f                    = om.MFnMesh(d)
                self.__dict__["_fn"] = f
        return f

    def __getattr__(self, name):
        # Only reached for attributes not found normally. Forward public names
        # to the underlying MFnMesh so mesh.getPoints() etc. keep working; never
        # forward private/dunder lookups, which would recurse.
        if name.startswith("_"):
            raise AttributeError(name)
        f = self.fn
        if f is not None:
            return getattr(f, name)
        raise AttributeError(
            "%r: this Mesh is detached (arrays only, no live function set)" % name)

    # ----- lazy numpy read surface -----
    def _cow_detach(self):
        """Copy-on-write: materialize every channel off the live handle, then
        sever the .fn link so the object becomes an editable value bucket."""
        if not self.__dict__.get("_attached"):
            return
        _ = self.counts; _ = self.indices; _ = self.points
        try:
            _ = self.normals
        except Exception:
            pass
        try:
            _ = self.colors
        except Exception:
            pass
        try:
            _ = self.component_tags
        except Exception:
            pass
        # UVs too, and BEFORE _attached is cleared: the uv_sets getter reads the
        # live handle only while attached, so afterwards it can only ever cache
        # []. Without this, `mesh.points = ...` on an attached input mesh
        # silently discards its UVs.
        try:
            _ = self.uv_sets
        except Exception:
            pass
        self._attached = False
        self._data     = None
        self._fn       = None

    def _ensure_topo(self):
        if self.__dict__.get("_counts") is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                c, conn = f.getVertices()
                self._counts  = np.asarray(c, dtype=np.int64)
                self._indices = np.asarray(conn, dtype=np.int64)

    @property
    def points(self):
        v = self.__dict__.get("_points")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v            = np.asarray(f.getPoints(om.MSpace.kObject))[:, :3].astype(np.float64)
                self._points = v
        return v

    @points.setter
    def points(self, val):
        self._cow_detach()
        self._points = None if val is None else np.asarray(val, dtype=np.float64)

    @property
    def counts(self):
        self._ensure_topo()
        return self.__dict__.get("_counts")

    @counts.setter
    def counts(self, val):
        self._cow_detach()
        self._counts = None if val is None else np.asarray(val, dtype=np.int64)

    @property
    def indices(self):
        self._ensure_topo()
        return self.__dict__.get("_indices")

    @indices.setter
    def indices(self, val):
        self._cow_detach()
        self._indices = None if val is None else np.asarray(val, dtype=np.int64)

    @property
    def normals(self):
        v = self.__dict__.get("_normals")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                try:
                    nrm           = f.getVertexNormals(False, om.MSpace.kObject)
                    v             = np.asarray(nrm)[:, :3].astype(np.float64)
                    self._normals = v
                except Exception:
                    v = None
        return v

    @normals.setter
    def normals(self, val):
        self._cow_detach()
        self._normals = None if val is None else np.asarray(val, dtype=np.float64)

    @property
    def colors(self):
        v = self.__dict__.get("_colors")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                try:
                    v            = np.asarray(f.getVertexColors()).astype(np.float64)
                    self._colors = v
                except Exception:
                    v = None
        return v

    @colors.setter
    def colors(self, val):
        self._cow_detach()
        self._colors = None if val is None else np.asarray(val, dtype=np.float64)

    @property
    def component_tags(self):
        """``{tag_name: {"type": "vertex"|"edge"|"face"|"uv", "indices": np}}``.
        Read live off the geometry DATA (attached mode); ``{}`` otherwise."""
        t = self.__dict__.get("_tags")
        if t is None:
            t = {}
            d = self.__dict__.get("_data")
            if self.__dict__.get("_attached") and d is not None and not d.isNull():
                try:
                    gd = om.MFnGeometryData(d)
                    for nm in gd.componentTags():
                        try:
                            comp = gd.componentTagContents(nm)
                            typ, idx = _decode_single_component(comp)
                            t[nm] = {"type": typ, "indices": idx}
                        except Exception:
                            pass
                except Exception:
                    pass
            self._tags = t
        return t

    def region(self, tag):
        """Points of a vertex ``tag`` (``(K,3)``), or its raw indices for a
        face/edge/uv tag, or None if the tag is absent.

        NOTE the return type depends on the tag's component type, so this does
        NOT compose with ``from_faces`` / ``from_vertices``. Use ``from_tag``,
        which dispatches on the tag's own type."""
        info = self.component_tags.get(tag)
        if not info:
            return None
        idx = info["indices"]
        if info["type"] == "vertex":
            pts = self.points
            return pts[idx] if pts is not None else None
        return idx

    def tag_clusters(self, names):
        """``names`` (one component-tag NAME per cluster) -> one padded
        ``(N, L)`` int64 array, ``-1`` fill -- the shape the vectorized
        Procrustes solver consumes. An absent tag contributes an empty row.

        Membership is read LIVE off the geometry DATA this wrapper is attached
        to (the same ``MFnGeometryData`` decode ``component_tags`` uses), so a
        component-tag edit takes effect on the next evaluation. Unattached /
        null data yields the empty ``(0, 1)`` array, matching
        ``component_tags.clusters_from_self_tags_live``."""
        from mpynode._common.nodes.mesh.component_tags import pad_clusters

        d = self.__dict__.get("_data")
        if not (self.__dict__.get("_attached") and d is not None
                and not d.isNull()):
            return pad_clusters([])
        tags = self.component_tags
        rows = []
        for t in (names or []):
            info = tags.get(t)
            rows.append(list(info["indices"]) if info else [])
        return pad_clusters(rows)

    # ----- sub-mesh extraction -----
    def contains_vertices(self, vertices, contained=True):
        """Face indices touching ``vertices``. ``contained`` requires EVERY
        corner of the face to be in the set; otherwise ANY corner matches."""
        counts  = self.counts
        indices = self.indices
        if counts is None or indices is None:
            return np.zeros(0, dtype=np.int64)
        verts          = np.unique(np.asarray(vertices, dtype=np.int64).ravel())
        nf             = int(counts.size)
        face_of_corner = np.repeat(np.arange(nf, dtype=np.int64), counts)
        hits = np.bincount(face_of_corner,
                           weights=np.isin(indices, verts).astype(np.float64),
                           minlength=nf)
        keep = (hits >= counts) if contained else (hits > 0)
        return np.where(keep)[0].astype(np.int64)

    def from_faces(self, faces, exclude=False):
        """A new detached Mesh rebuilt from ``faces`` (face indices). Points are
        compacted to those actually used and ``indices`` renumbered to match.

        ``exclude=True`` keeps everything EXCEPT the listed faces. Derived
        channels (normals / colors) and component tags are dropped: vertices are
        renumbered and faces are a subset, so the originals no longer apply."""
        counts  = self.counts
        indices = self.indices
        points  = self.points
        if counts is None or indices is None:
            return Mesh()
        nf   = int(counts.size)
        want = np.asarray(faces, dtype=np.int64).ravel()
        mask = np.zeros(nf, dtype=bool)
        mask[want[(want >= 0) & (want < nf)]] = True
        if exclude:
            mask = ~mask
        face_of_corner = np.repeat(np.arange(nf, dtype=np.int64), counts)
        stream         = indices[mask[face_of_corner]]
        m              = Mesh()
        m._counts      = counts[mask].astype(np.int64)
        if stream.size == 0 or points is None:
            m._points  = np.zeros((0, 3), dtype=np.float64)
            m._indices = np.zeros(0, dtype=np.int64)
            return m
        used, remap = np.unique(stream, return_inverse=True)
        m._points  = np.array(points[used], dtype=np.float64)
        m._indices = remap.astype(np.int64)
        return m

    def from_vertices(self, vertices, contained=True, exclude=False):
        """A new detached Mesh rebuilt from the faces touching ``vertices``."""
        return self.from_faces(
            self.contains_vertices(vertices, contained=contained),
            exclude=exclude)

    def from_tag(self, tag, exclude=False, contained=True):
        """A new detached Mesh rebuilt from a component ``tag``, dispatching on
        the tag's OWN component type -- face tags route through ``from_faces``,
        vertex tags through ``from_vertices``.

        This is the safe form of ``from_faces(region(tag))``: ``region`` returns
        POINTS for a vertex tag and INDICES for a face tag, so feeding it
        straight to ``from_faces`` silently produces garbage on a vertex tag.

        Raises KeyError (listing what IS on the mesh) when the tag is absent --
        a typo'd or renamed tag is a mistake, not an empty region."""
        info = self.component_tags.get(tag)
        if not info:
            raise KeyError(
                "no component tag %r on this mesh; available: %s"
                % (tag, sorted(self.component_tags) or "(none)"))
        kind = info["type"]
        idx  = info["indices"]
        if kind == "face":
            return self.from_faces(idx, exclude=exclude)
        if kind == "vertex":
            return self.from_vertices(idx, contained=contained,
                                      exclude=exclude)
        raise ValueError(
            "component tag %r is a %r tag; from_tag supports 'face' and "
            "'vertex' tags" % (tag, kind))

    @property
    def uv_sets(self):
        """``list[UVSet]`` -- every UV set on this mesh, each a standalone 2D UV
        "mesh" (``name`` + 2D ``points`` + ``counts`` + ``indices``).

        Read live + EM-safely off the attached DATA MObject's ``MFnMesh`` (same
        path as ``points`` / ``component_tags``), cached on first access. ``[]``
        for a detached/value mesh or a mesh with no UVs. Fail-soft PER SET: a
        corrupt or empty set is skipped, never raised (mirrors
        ``component_tags``), so one bad set can't blank the rest.

        UVs are a per-face-vertex channel in an INDEPENDENT 2D index space -- a
        seam corner is unshared, so ``num_uvs`` generally differs from the mesh's
        vertex count. ``counts``/``indices`` follow the polygon order exactly like
        the mesh's own, but ``indices`` point into the UV ``points`` array. Feed a
        set through ``UVSet.as_mesh()`` if you want a real 2D DG mesh."""
        u = self.__dict__.get("_uv_sets")
        if u is None:
            u = []
            if self.__dict__.get("_attached"):
                f = self.fn
                if f is not None:
                    try:
                        names = list(f.getUVSetNames())
                    except Exception:
                        names = []
                    for i, nm in enumerate(names):
                        try:
                            ua, va = f.getUVs(nm)
                            if len(ua) == 0:
                                continue  # empty set: skip (never marshal)
                            pts = np.column_stack([
                                np.asarray(ua, dtype=np.float64),
                                np.asarray(va, dtype=np.float64)])
                            uv_counts, uv_ids = f.getAssignedUVs(nm)
                            label = nm if nm else "uvSet%d" % i
                            u.append(UVSet(
                                label, pts,
                                np.asarray(uv_counts, dtype=np.int64),
                                np.asarray(uv_ids, dtype=np.int64)))
                        except Exception:
                            pass  # fail-soft: skip a bad set
            self.__dict__["_uv_sets"] = u
        return u

    @property
    def uvs(self):
        """``(M, 2)`` float64 -- the (u, v) points of the FIRST non-empty UV set
        (``uv_sets[0].points``), or an empty ``(0, 2)`` array when the mesh has no
        UVs. Convenience shorthand for the common "just give me the UV points"
        read; use ``uv_sets`` for per-set names / counts / indices."""
        sets = self.uv_sets
        if sets:
            return sets[0].points
        return np.empty((0, 2), dtype=np.float64)

    def copy(self):
        """A DETACHED value copy (severs the .fn link). Edit its channels and
        assign to an output plug -- no imports required."""
        m          = Mesh()
        p          = self.points
        m._points  = None if p is None else np.array(p, dtype=np.float64)
        c          = self.counts
        m._counts  = None if c is None else np.array(c, dtype=np.int64)
        i          = self.indices
        m._indices = None if i is None else np.array(i, dtype=np.int64)
        n          = self.normals
        if n is not None:
            m._normals = np.array(n, dtype=np.float64)
        m.normal_indices = self.normal_indices
        col              = self.colors
        if col is not None:
            m._colors = np.array(col, dtype=np.float64)
        m.color_indices = self.color_indices
        try:
            m._tags = {k: dict(v) for k, v in self.component_tags.items()}
        except Exception:
            pass
        # UV sets ride along. FRESH UVSet objects over COPIED arrays -- sharing
        # them would alias the source mesh's cache, so a caller editing
        # out.uv_sets[0].points would corrupt the input mesh. Without this the
        # common `out = self.inMesh.copy(); out.points = ...` idiom reaches the
        # output plug with no UVs at all, whatever the marshaller does.
        try:
            m._uv_sets = [
                UVSet(u.name,
                      np.array(u.points, dtype=np.float64),
                      np.array(u.counts, dtype=np.int64),
                      np.array(u.indices, dtype=np.int64))
                for u in (self.uv_sets or [])
            ]
        except Exception:
            pass
        return m

    # ----- serialization -----
    def __reduce__(self):
        """Pickle as a DETACHED value mesh (see the Serialization section).

        UV sets ride along. ``copy()`` now carries them too, so this is
        belt-and-braces rather than the only carrier it once was; ``uv_sets``
        reads the cache on a detached mesh, so it stays correct either way."""
        state = _detached_state(self)
        try:
            state["_uv_sets"] = list(self.uv_sets)
        except Exception:
            state["_uv_sets"] = []
        return (_geo_from_state, (Mesh, state))

    def to_json(self):
        """A plain-JSON dict of every channel -- no numpy, no Maya handles."""
        return {
            "type":           "Mesh",
            "name":           self.name,
            "points":         _jlist(self.points),
            "counts":         _jlist(self.counts),
            "indices":        _jlist(self.indices),
            "normals":        _jlist(self.normals),
            "normal_indices": _jlist(self.normal_indices),
            "colors":         _jlist(self.colors),
            "color_indices":  _jlist(self.color_indices),
            "component_tags": _jtags(self.component_tags),
            "uv_sets":        [u.to_json() for u in self.uv_sets],
        }

    @classmethod
    def from_json(cls, payload):
        """Rebuild a detached Mesh from :meth:`to_json` output (dict or text)."""
        if isinstance(payload, (str, bytes)):
            payload = _json.loads(payload)
        m = cls(points=payload.get("points"), counts=payload.get("counts"),
                indices        = payload.get("indices"),
                normals        = payload.get("normals"),
                normal_indices = payload.get("normal_indices"),
                colors         = payload.get("colors"),
                color_indices=payload.get("color_indices"))
        m._tags    = _tags_from_json(payload.get("component_tags"))
        m._uv_sets = [UVSet.from_json(u) for u in (payload.get("uv_sets") or [])]
        m._name    = payload.get("name")
        return m

    # ----- arithmetic -----
    # Make numpy defer to __radd__/__rmul__ instead of broadcasting a Mesh into
    # an array: without this ``np.float64(2) * mesh`` iterates the object.
    __array_ufunc__ = None

    def _points_for_edit(self):
        """Detach (so the edit can't be discarded by ``to_mobject``'s attached
        pass-through) and hand back the writable point array."""
        self._cow_detach()
        pts = self.__dict__.get("_points")
        if pts is None:
            raise ValueError("this Mesh has no points to operate on")
        return pts

    def _iadd_mesh(self, other):
        """Union: concatenate topology, rebasing the other side's indices past
        our vertex count. This is NOT a boolean -- faces are appended, not
        merged. Our OWN component tags survive (our vertices and faces keep
        their indices); the other side's are dropped."""
        self._cow_detach()
        sp = self.__dict__.get("_points")
        sc = self.__dict__.get("_counts")
        si = self.__dict__.get("_indices")
        op, oc, oi = other.points, other.counts, other.indices
        if op is None or oc is None or oi is None:
            return
        if sp is None or sc is None or si is None:
            self._points  = np.array(op, dtype=np.float64)
            self._counts  = np.array(oc, dtype=np.int64)
            self._indices = np.array(oi, dtype=np.int64)
        else:
            self._indices = np.concatenate(
                [si, np.asarray(oi, dtype=np.int64) + sp.shape[0]])
            self._counts = np.concatenate([sc, np.asarray(oc, dtype=np.int64)])
            self._points = np.concatenate(
                [sp, np.asarray(op, dtype=np.float64)])
        # Derived channels no longer line up with the combined topology.
        self._normals       = None
        self.normal_indices = None
        self._colors        = None
        self.color_indices  = None
        # UVs are per-face-vertex, so the appended faces have no UV entries and
        # the set's counts no longer match the face list. Explicitly [] ("read,
        # none") rather than None ("not read"): _cow_detach above already
        # materialized the pre-union UVs, so None would leave them in place and
        # the marshaller would assign a stale, mis-sized layout.
        self._uv_sets = []

    def _iadd_morph(self, other, sign):
        """Apply a sparse offset field in place.

        Uses ``np.add.at``, NOT ``points[idx] += off``: fancy-index in-place
        assignment keeps only the LAST write when idx repeats, which would
        silently under-apply a target whose indices are not unique."""
        pts = self._points_for_edit()
        idx = np.asarray(other.indices, dtype=np.int64).ravel()
        off = np.asarray(other.offsets, dtype=np.float64).reshape(-1, 3)
        if idx.size == 0:
            return
        if idx.size != off.shape[0]:
            raise ValueError(
                "morph has %d indices but %d offsets"
                % (idx.size, off.shape[0]))
        if int(idx.min()) < 0 or int(idx.max()) >= pts.shape[0]:
            raise ValueError(
                "morph index out of range for a %d-vertex mesh (max %d)"
                % (pts.shape[0], int(idx.max())))
        np.add.at(pts, idx, off if sign > 0 else -off)

    def __iadd__(self, other):
        if isinstance(other, Mesh):
            self._iadd_mesh(other)
        elif _looks_like_morph(other):
            self._iadd_morph(other, 1.0)
        else:
            pts          = self._points_for_edit()
            self._points = pts + np.asarray(other, dtype=np.float64)
        return self

    def __add__(self, other):
        return self.copy().__iadd__(other)

    def __radd__(self, other):
        # sum([m1, m2, ...]) seeds with int 0.
        if isinstance(other, int) and other == 0:
            return self.copy()
        return self.__add__(other)

    def _isub_mesh(self, other, tolerance=1e-6):
        """Tolerance-based overlap removal -- NOT a boolean. Drops every face of
        ours whose corners ALL coincide (within ``tolerance``) with a vertex of
        ``other``, then compacts the points and renumbers.

        Mirrors the reference ``MeshData.difference``: match vertices with a
        nearest-neighbour-within-tolerance query, then
        ``from_vertices(matched, contained=True, exclude=True)``. It is the
        inverse of the union ``+``, so ``(a + b) - b`` gives back ``a`` whenever
        the two sides share no coincident vertices.

        Derived channels, component tags and UV sets are dropped: faces are a
        subset and the vertices are renumbered, so none of them still apply."""
        self._cow_detach()
        points       = self.__dict__.get("_points")
        other_points = other.points
        if points is None or other_points is None:
            return
        # No topology means no faces to remove -- leave the point bucket alone
        # rather than letting from_faces hand back an empty mesh.
        if (self.__dict__.get("_counts") is None
                or self.__dict__.get("_indices") is None):
            return
        matched = _points_within(
            points, np.asarray(other_points, dtype=np.float64), tolerance)
        if matched.size == 0:
            return
        new                 = self.from_vertices(matched, contained=True, exclude=True)
        self._points        = new._points
        self._counts        = new._counts
        self._indices       = new._indices
        self._normals       = None
        self.normal_indices = None
        self._colors        = None
        self.color_indices  = None
        self._tags          = {}
        self._uv_sets       = None

    def __isub__(self, other):
        if isinstance(other, Mesh):
            self._isub_mesh(other)
        elif _looks_like_morph(other):
            self._iadd_morph(other, -1.0)
        else:
            pts          = self._points_for_edit()
            self._points = pts - np.asarray(other, dtype=np.float64)
        return self

    def __sub__(self, other):
        return self.copy().__isub__(other)

    def __imul__(self, other):
        if isinstance(other, Mesh) or _looks_like_morph(other):
            raise TypeError(
                "Mesh * Mesh and Mesh * Morph are undefined; multiply by a "
                "scalar or a (3,) vector to scale the point field")
        pts          = self._points_for_edit()
        self._points = pts * np.asarray(other, dtype=np.float64)
        return self

    def __mul__(self, other):
        return self.copy().__imul__(other)

    __rmul__ = __mul__

    def to_mobject(self):
        # Attached + unedited: zero-copy, tag-preserving pass-through of the
        # input data. Edited/value: rebuild from arrays via the marshaller.
        if self.__dict__.get("_attached"):
            d = self.__dict__.get("_data")
            if d is not None and not d.isNull():
                return d
        return build_mesh_data(self)

    def __repr__(self):
        nm = self.name
        if nm:
            return 'Mesh("%s")' % nm
        mode = "attached" if self.__dict__.get("_attached") else "value"
        p    = self.__dict__.get("_points")
        if p is None:
            n = "lazy" if self.__dict__.get("_attached") else 0
        else:
            n = len(p)
        return "<Mesh %s verts=%s>" % (mode, n)


class NurbsCurve:
    """A NURBS curve geometry object -- the SAME type on inputs and outputs.

    Two modes (mirrors :class:`Mesh`):

    * **Attached** (what an input plug hands you): holds the retained geometry
      DATA MObject and lazily mints an ``MFnNurbsCurve`` from it. The numpy read
      surface (``points``/``cvs`` / ``degree`` / ``form`` / ``knots`` /
      ``component_tags``) is materialized on first access and cached. EM-safe.
    * **Value** (what you construct or ``copy()``): a plain arrays bucket you
      assign to an output plug. ``build_curve_data`` marshals it (duck-typed).

    Self-sufficient: the raw function set is ``fn`` (any ``MFnNurbsCurve`` method
    also works via delegation, e.g. ``curve.cvPositions(...)`` keeps working).
    ``copy()`` returns a detached editable value you can send to an output with
    NO imports.

    Construction (value/output): ``points`` (N,3 CV positions) required.
    Optional: ``degree`` (default 3), ``periodic`` (default False = open),
    ``kv`` (knot vector; auto if None). ``knots`` is an alias for ``kv``.
    """

    def __init__(self, points=None, degree=3, periodic=False, kv=None):
        self._attached = False
        self._data     = None  # retained api2 geometry DATA MObject
        self._fn       = None  # cached MFnNurbsCurve (attached mode)
        self._tags     = None  # cached component_tags dict
        self._points   = None if points is None else np.asarray(points, dtype=np.float64)
        self._degree   = int(degree) if degree is not None else 3
        self._periodic = bool(periodic)
        self._knots    = None if kv is None else np.asarray(kv, dtype=np.float64)
        self._form     = None  # value mode derives form from periodic

    @classmethod
    def _attach(cls, data_mobject, source_plug=None):
        c           = cls.__new__(cls)
        c._attached = True
        c._data     = data_mobject
        c._fn       = None
        c._tags     = None
        c._points   = None
        c._degree   = None
        c._periodic = None
        c._knots    = None
        c._form     = None
        c._src_plug = source_plug
        c._name     = None
        return c

    @property
    def name(self):
        """Name of the shape feeding this curve, or None for a value curve.
        Lazy + cached -- see :func:`_source_node_name`."""
        nm = self.__dict__.get("_name")
        if nm is None:
            nm                     = _source_node_name(self.__dict__.get("_src_plug"))
            self.__dict__["_name"] = nm
        return nm

    # ----- raw function set + delegation -----
    @property
    def fn(self):
        """The live ``MFnNurbsCurve`` (attached mode), or None if detached."""
        f = self.__dict__.get("_fn")
        if f is None:
            d = self.__dict__.get("_data")
            if d is not None and not d.isNull():
                f                    = om.MFnNurbsCurve(d)
                self.__dict__["_fn"] = f
        return f

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        f = self.fn
        if f is not None:
            return getattr(f, name)
        raise AttributeError(
            "%r: this NurbsCurve is detached (arrays only, no function set)" % name)

    def _cow_detach(self):
        if not self.__dict__.get("_attached"):
            return
        _ = self.points; _ = self.degree; _ = self.form; _ = self.knots
        try:
            _ = self.component_tags
        except Exception:
            pass
        self._attached = False
        self._data     = None
        self._fn       = None

    # ----- lazy numpy read surface -----
    @property
    def points(self):
        v = self.__dict__.get("_points")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v = np.asarray(
                    f.cvPositions(om.MSpace.kObject))[:, :3].astype(np.float64)
                self._points = v
        return v

    @points.setter
    def points(self, val):
        self._cow_detach()
        self._points = None if val is None else np.asarray(val, dtype=np.float64)

    # ``cvs`` reads the same CV positions (matches the generator scratch name).
    @property
    def cvs(self):
        return self.points

    @cvs.setter
    def cvs(self, val):
        self.points = val

    @property
    def degree(self):
        v = self.__dict__.get("_degree")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v            = int(f.degree)
                self._degree = v
        return v

    @degree.setter
    def degree(self, val):
        self._cow_detach()
        self._degree = None if val is None else int(val)

    @property
    def form(self):
        v = self.__dict__.get("_form")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v          = int(f.form)
                self._form = v
        return v

    @form.setter
    def form(self, val):
        self._cow_detach()
        self._form = val

    @property
    def periodic(self):
        # Value mode stores an explicit bool; attached mode derives it from form.
        p = self.__dict__.get("_periodic")
        if p is not None:
            return p
        fm = self.form
        return bool(fm == om.MFnNurbsCurve.kPeriodic) if fm is not None else False

    @periodic.setter
    def periodic(self, val):
        self._cow_detach()
        self._periodic = bool(val)

    @property
    def knots(self):
        v = self.__dict__.get("_knots")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v           = np.asarray(f.knots(), dtype=np.float64)
                self._knots = v
        return v

    @knots.setter
    def knots(self, val):
        self._cow_detach()
        self._knots = None if val is None else np.asarray(val, dtype=np.float64)

    # ``kv`` is the name ``build_curve_data`` reads; alias it to ``knots`` so a
    # copy()'d attached curve round-trips its real knot vector on output.
    @property
    def kv(self):
        return self.knots

    @kv.setter
    def kv(self, val):
        self.knots = val

    @property
    def component_tags(self):
        """``{tag_name: {"type": "cv", "indices": np}}`` (curve CV tags are
        single-indexed). Read live off the geometry DATA (attached mode)."""
        t = self.__dict__.get("_tags")
        if t is None:
            t = {}
            d = self.__dict__.get("_data")
            if self.__dict__.get("_attached") and d is not None and not d.isNull():
                try:
                    gd = om.MFnGeometryData(d)
                    for nm in gd.componentTags():
                        try:
                            comp = gd.componentTagContents(nm)
                            typ, idx = _decode_single_component(comp)
                            t[nm] = {"type": typ, "indices": idx}
                        except Exception:
                            pass
                except Exception:
                    pass
            self._tags = t
        return t

    def region(self, tag):
        """CV positions of a ``cv`` tag (``(K,3)``), or its raw indices for any
        other tag type, or None if the tag is absent."""
        info = self.component_tags.get(tag)
        if not info:
            return None
        idx = info["indices"]
        if info["type"] == "cv":
            pts = self.points
            return pts[idx] if pts is not None else None
        return idx

    def copy(self):
        """A DETACHED value copy (severs the .fn link). Edit its channels and
        assign to an output plug -- no imports required."""
        c           = NurbsCurve()
        p           = self.points
        c._points   = None if p is None else np.array(p, dtype=np.float64)
        c._degree   = self.degree
        c._form     = self.form
        c._periodic = self.periodic
        k           = self.knots
        c._knots    = None if k is None else np.array(k, dtype=np.float64)
        try:
            c._tags = {kk: dict(vv) for kk, vv in self.component_tags.items()}
        except Exception:
            pass
        return c

    # ----- serialization -----
    def __reduce__(self):
        """Pickle as a DETACHED value curve (see the Serialization section)."""
        return (_geo_from_state, (NurbsCurve, _detached_state(self)))

    def to_json(self):
        """A plain-JSON dict of every channel -- no numpy, no Maya handles."""
        return {
            "type":           "NurbsCurve",
            "name":           self.name,
            "points":         _jlist(self.points),
            "degree":         None if self.degree is None else int(self.degree),
            "form":           self.form,
            "periodic":       bool(self.periodic),
            "knots":          _jlist(self.knots),
            "component_tags": _jtags(self.component_tags),
        }

    @classmethod
    def from_json(cls, payload):
        """Rebuild a detached NurbsCurve from :meth:`to_json` output."""
        if isinstance(payload, (str, bytes)):
            payload = _json.loads(payload)
        c = cls(points=payload.get("points"),
                degree   = payload.get("degree") or 3,
                periodic = bool(payload.get("periodic")),
                kv=payload.get("knots"))
        c._form = payload.get("form")
        c._tags = _tags_from_json(payload.get("component_tags"))
        c._name = payload.get("name")
        return c

    # ----- arithmetic -----
    __array_ufunc__ = None

    def __iadd__(self, other):
        """Concatenate another curve's CVs onto this one, producing ONE longer
        curve through both control point sets -- not two curves in one shape.

        Knots are dropped so the marshaller rebuilds a uniform vector for the
        combined CV count: the originals describe the old parameterisations and
        cannot be spliced. Degree and ``periodic`` must MATCH -- silently
        re-fitting to another degree, or appending onto a closed curve, is far
        more likely a mistake than an intent."""
        if not isinstance(other, NurbsCurve):
            raise TypeError(
                "NurbsCurve + %s is undefined; only another NurbsCurve can be "
                "concatenated" % type(other).__name__)
        if int(other.degree) != int(self.degree):
            raise ValueError(
                "degree mismatch: %d vs %d -- resample one curve first"
                % (int(self.degree), int(other.degree)))
        if bool(other.periodic) != bool(self.periodic):
            raise ValueError(
                "periodic mismatch: %r vs %r -- appending onto a closed curve "
                "is ambiguous" % (bool(self.periodic), bool(other.periodic)))
        op = other.points
        self._cow_detach()
        sp = self.__dict__.get("_points")
        if op is None:
            return self
        if sp is None:
            self._points = np.array(op, dtype=np.float64)
        else:
            self._points = np.concatenate(
                [sp, np.asarray(op, dtype=np.float64)])
        self._knots = None
        return self

    def __add__(self, other):
        return self.copy().__iadd__(other)

    def __radd__(self, other):
        if isinstance(other, int) and other == 0:
            return self.copy()
        return self.__add__(other)

    def to_mobject(self):
        # Attached + unedited: zero-copy, tag-preserving pass-through.
        if self.__dict__.get("_attached"):
            d = self.__dict__.get("_data")
            if d is not None and not d.isNull():
                return d
        return build_curve_data(self)

    def __repr__(self):
        nm = self.name
        if nm:
            return 'NurbsCurve("%s")' % nm
        mode = "attached" if self.__dict__.get("_attached") else "value"
        p    = self.__dict__.get("_points")
        n    = ("lazy" if self.__dict__.get("_attached") else 0) if p is None else len(p)
        return "<NurbsCurve %s cvs=%s>" % (mode, n)


class NurbsSurface:
    """A NURBS surface geometry object -- the SAME type on inputs and outputs.

    Two modes (mirrors :class:`Mesh` / :class:`NurbsCurve`):

    * **Attached** (input plug): retained geometry DATA MObject + lazy
      ``MFnNurbsSurface``. numpy read surface: ``points``/``cvs`` (an
      ``(nu, nv, 3)`` U-major grid), ``degree_u`` / ``degree_v``, ``form_u`` /
      ``form_v``, ``knots_u`` / ``knots_v``, ``num_u`` / ``num_v``,
      ``component_tags`` (double-indexed CVs), ``region(tag)``.
    * **Value** (constructed / ``copy()``): arrays bucket marshalled by
      ``build_surface_data`` (duck-typed).

    Construction (value/output): ``points`` ((nu,nv,3) grid or (nu*nv,3) flat)
    required. Optional: ``degree_u`` / ``degree_v`` (3), ``periodic_u`` /
    ``periodic_v`` (False), ``kv_u`` / ``kv_v`` (auto), ``num_u`` / ``num_v``
    (flat points only). ``knots_u`` / ``knots_v`` alias ``kv_u`` / ``kv_v``.
    """

    def __init__(self, points=None, degree_u=3, degree_v=3,
                 periodic_u=False, periodic_v=False,
                 kv_u=None, kv_v=None, num_u=None, num_v=None):
        self._attached   = False
        self._data       = None
        self._fn         = None
        self._tags       = None
        self._points     = None if points is None else np.asarray(points, dtype=np.float64)
        self._degree_u   = int(degree_u) if degree_u is not None else 3
        self._degree_v   = int(degree_v) if degree_v is not None else 3
        self._periodic_u = bool(periodic_u)
        self._periodic_v = bool(periodic_v)
        self._knots_u    = None if kv_u is None else np.asarray(kv_u, dtype=np.float64)
        self._knots_v    = None if kv_v is None else np.asarray(kv_v, dtype=np.float64)
        self._num_u      = num_u
        self._num_v      = num_v
        self._form_u     = None
        self._form_v     = None

    @classmethod
    def _attach(cls, data_mobject, source_plug=None):
        s             = cls.__new__(cls)
        s._attached   = True
        s._data       = data_mobject
        s._fn         = None
        s._tags       = None
        s._points     = None
        s._degree_u   = None
        s._degree_v   = None
        s._periodic_u = None
        s._periodic_v = None
        s._knots_u    = None
        s._knots_v    = None
        s._num_u      = None
        s._num_v      = None
        s._form_u     = None
        s._form_v     = None
        s._src_plug   = source_plug
        s._name       = None
        return s

    @property
    def name(self):
        """Name of the shape feeding this surface, or None for a value surface.
        Lazy + cached -- see :func:`_source_node_name`."""
        nm = self.__dict__.get("_name")
        if nm is None:
            nm                     = _source_node_name(self.__dict__.get("_src_plug"))
            self.__dict__["_name"] = nm
        return nm

    # ----- raw function set + delegation -----
    @property
    def fn(self):
        """The live ``MFnNurbsSurface`` (attached mode), or None if detached."""
        f = self.__dict__.get("_fn")
        if f is None:
            d = self.__dict__.get("_data")
            if d is not None and not d.isNull():
                f                    = om.MFnNurbsSurface(d)
                self.__dict__["_fn"] = f
        return f

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        f = self.fn
        if f is not None:
            return getattr(f, name)
        raise AttributeError(
            "%r: this NurbsSurface is detached (arrays only, no function set)" % name)

    def _cow_detach(self):
        if not self.__dict__.get("_attached"):
            return
        _ = self.num_u; _ = self.num_v
        _ = self.points
        _ = self.degree_u; _ = self.degree_v
        _ = self.form_u; _ = self.form_v
        _ = self.knots_u; _ = self.knots_v
        try:
            _ = self.component_tags
        except Exception:
            pass
        self._attached = False
        self._data     = None
        self._fn       = None

    # ----- lazy numpy read surface -----
    @property
    def num_u(self):
        v = self.__dict__.get("_num_u")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v           = int(f.numCVsInU)
                self._num_u = v
        return v

    @num_u.setter
    def num_u(self, val):
        self._cow_detach()
        self._num_u = val

    @property
    def num_v(self):
        v = self.__dict__.get("_num_v")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v           = int(f.numCVsInV)
                self._num_v = v
        return v

    @num_v.setter
    def num_v(self, val):
        self._cow_detach()
        self._num_v = val

    @property
    def points(self):
        """``(nu, nv, 3)`` U-major CV grid (attached), or the stored value."""
        v = self.__dict__.get("_points")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                flat = np.asarray(
                    f.cvPositions(om.MSpace.kObject))[:, :3].astype(np.float64)
                nu, nv = int(f.numCVsInU), int(f.numCVsInV)
                if flat.shape[0] == nu * nv and nu > 0 and nv > 0:
                    v = flat.reshape(nu, nv, 3)   # U-major (v fastest)
                else:
                    v = flat
                self._points = v
        return v

    @points.setter
    def points(self, val):
        self._cow_detach()
        self._points = None if val is None else np.asarray(val, dtype=np.float64)

    @property
    def cvs(self):
        return self.points

    @cvs.setter
    def cvs(self, val):
        self.points = val

    def _lazy_scalar(self, cache_name, fn_attr, cast=int):
        v = self.__dict__.get(cache_name)
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v                         = cast(getattr(f, fn_attr))
                self.__dict__[cache_name] = v
        return v

    @property
    def degree_u(self):
        return self._lazy_scalar("_degree_u", "degreeInU")

    @degree_u.setter
    def degree_u(self, val):
        self._cow_detach()
        self._degree_u = None if val is None else int(val)

    @property
    def degree_v(self):
        return self._lazy_scalar("_degree_v", "degreeInV")

    @degree_v.setter
    def degree_v(self, val):
        self._cow_detach()
        self._degree_v = None if val is None else int(val)

    @property
    def form_u(self):
        return self._lazy_scalar("_form_u", "formInU")

    @form_u.setter
    def form_u(self, val):
        self._cow_detach()
        self._form_u = val

    @property
    def form_v(self):
        return self._lazy_scalar("_form_v", "formInV")

    @form_v.setter
    def form_v(self, val):
        self._cow_detach()
        self._form_v = val

    @property
    def periodic_u(self):
        p = self.__dict__.get("_periodic_u")
        if p is not None:
            return p
        fm = self.form_u
        return bool(fm == om.MFnNurbsSurface.kPeriodic) if fm is not None else False

    @periodic_u.setter
    def periodic_u(self, val):
        self._cow_detach()
        self._periodic_u = bool(val)

    @property
    def periodic_v(self):
        p = self.__dict__.get("_periodic_v")
        if p is not None:
            return p
        fm = self.form_v
        return bool(fm == om.MFnNurbsSurface.kPeriodic) if fm is not None else False

    @periodic_v.setter
    def periodic_v(self, val):
        self._cow_detach()
        self._periodic_v = bool(val)

    @property
    def knots_u(self):
        v = self.__dict__.get("_knots_u")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v             = np.asarray(f.knotsInU(), dtype=np.float64)
                self._knots_u = v
        return v

    @knots_u.setter
    def knots_u(self, val):
        self._cow_detach()
        self._knots_u = None if val is None else np.asarray(val, dtype=np.float64)

    @property
    def knots_v(self):
        v = self.__dict__.get("_knots_v")
        if v is None and self.__dict__.get("_attached"):
            f = self.fn
            if f is not None:
                v             = np.asarray(f.knotsInV(), dtype=np.float64)
                self._knots_v = v
        return v

    @knots_v.setter
    def knots_v(self, val):
        self._cow_detach()
        self._knots_v = None if val is None else np.asarray(val, dtype=np.float64)

    # ``kv_u`` / ``kv_v`` are the names ``build_surface_data`` reads.
    @property
    def kv_u(self):
        return self.knots_u

    @kv_u.setter
    def kv_u(self, val):
        self.knots_u = val

    @property
    def kv_v(self):
        return self.knots_v

    @kv_v.setter
    def kv_v(self, val):
        self.knots_v = val

    @property
    def component_tags(self):
        """``{tag_name: {"type": "cv", "indices": (K,2) np}}`` -- surface CV
        tags are double-indexed ``(u, v)`` grid coordinates."""
        t = self.__dict__.get("_tags")
        if t is None:
            t = {}
            d = self.__dict__.get("_data")
            if self.__dict__.get("_attached") and d is not None and not d.isNull():
                try:
                    gd = om.MFnGeometryData(d)
                    for nm in gd.componentTags():
                        try:
                            comp = gd.componentTagContents(nm)
                            typ, idx = _decode_double_component(comp)
                            t[nm] = {"type": typ, "indices": idx}
                        except Exception:
                            pass
                except Exception:
                    pass
            self._tags = t
        return t

    def region(self, tag):
        """CV positions of a ``cv`` tag (``(K,3)``, gathered from the grid via
        the ``(u, v)`` pairs), or the raw ``(K,2)`` indices otherwise, or None."""
        info = self.component_tags.get(tag)
        if not info:
            return None
        idx = info["indices"]
        if info["type"] == "cv":
            pts = self.points
            if pts is None or idx.size == 0:
                return None
            if pts.ndim == 3:
                return pts[idx[:, 0], idx[:, 1]]
            # flat fallback: linearize (u, v) with num_v.
            nv = self.num_v or 1
            return pts[idx[:, 0] * nv + idx[:, 1]]
        return idx

    def copy(self):
        """A DETACHED value copy (severs the .fn link)."""
        s             = NurbsSurface()
        p             = self.points
        s._points     = None if p is None else np.array(p, dtype=np.float64)
        s._degree_u   = self.degree_u
        s._degree_v   = self.degree_v
        s._form_u     = self.form_u
        s._form_v     = self.form_v
        s._periodic_u = self.periodic_u
        s._periodic_v = self.periodic_v
        ku            = self.knots_u
        s._knots_u    = None if ku is None else np.array(ku, dtype=np.float64)
        kvv           = self.knots_v
        s._knots_v    = None if kvv is None else np.array(kvv, dtype=np.float64)
        s._num_u      = self.num_u
        s._num_v      = self.num_v
        try:
            s._tags = {kk: dict(vv) for kk, vv in self.component_tags.items()}
        except Exception:
            pass
        return s

    # ----- serialization -----
    def __reduce__(self):
        """Pickle as a DETACHED value surface (see the Serialization section)."""
        return (_geo_from_state, (NurbsSurface, _detached_state(self)))

    def to_json(self):
        """A plain-JSON dict of every channel -- no numpy, no Maya handles."""
        return {
            "type":           "NurbsSurface",
            "name":           self.name,
            "points":         _jlist(self.points),
            "degree_u":       None if self.degree_u is None else int(self.degree_u),
            "degree_v":       None if self.degree_v is None else int(self.degree_v),
            "form_u":         self.form_u,
            "form_v":         self.form_v,
            "periodic_u":     bool(self.periodic_u),
            "periodic_v":     bool(self.periodic_v),
            "knots_u":        _jlist(self.knots_u),
            "knots_v":        _jlist(self.knots_v),
            "num_u":          None if self.num_u is None else int(self.num_u),
            "num_v":          None if self.num_v is None else int(self.num_v),
            "component_tags": _jtags(self.component_tags),
        }

    @classmethod
    def from_json(cls, payload):
        """Rebuild a detached NurbsSurface from :meth:`to_json` output."""
        if isinstance(payload, (str, bytes)):
            payload = _json.loads(payload)
        s = cls(points=payload.get("points"),
                num_u=payload.get("num_u"), num_v=payload.get("num_v"),
                degree_u   = payload.get("degree_u") or 3,
                degree_v   = payload.get("degree_v") or 3,
                periodic_u = bool(payload.get("periodic_u")),
                periodic_v = bool(payload.get("periodic_v")),
                kv_u=payload.get("knots_u"), kv_v=payload.get("knots_v"))
        s._form_u = payload.get("form_u")
        s._form_v = payload.get("form_v")
        s._tags   = _tags_from_json(payload.get("component_tags"))
        s._name   = payload.get("name")
        return s

    def to_mobject(self):
        if self.__dict__.get("_attached"):
            d = self.__dict__.get("_data")
            if d is not None and not d.isNull():
                return d
        return build_surface_data(self)

    def __repr__(self):
        nm = self.name
        if nm:
            return 'NurbsSurface("%s")' % nm
        mode = "attached" if self.__dict__.get("_attached") else "value"
        p    = self.__dict__.get("_points")
        if p is None:
            n = "lazy" if self.__dict__.get("_attached") else 0
        else:
            n = p.shape[0] * p.shape[1] if p.ndim == 3 else len(p)
        return "<NurbsSurface %s cvs=%s>" % (mode, n)


# ===========================================================================
# Structural gates -- required-attr presence per geometry kind. compute() uses
# these to decide whether a user-assigned object is a geometry payload worth
# marshalling, independent of its concrete class.
# ===========================================================================

_REQUIRED = {
    "mesh":    ("points", "counts", "indices"),
    "curve":   ("points",),
    "surface": ("points",),
}


def _is_like(obj, kind) -> bool:
    return obj is not None and all(hasattr(obj, a) for a in _REQUIRED[kind])


def is_mesh_like(obj) -> bool:
    return _is_like(obj, "mesh")


def is_curve_like(obj) -> bool:
    return _is_like(obj, "curve")


def is_surface_like(obj) -> bool:
    return _is_like(obj, "surface")


# ===========================================================================
# Serialization -- pickle + JSON
# ===========================================================================
#
# A geometry object is interchangeable OUTSIDE Maya: pickle it, ship it, load
# it in a plain Python process. Both formats carry the DETACHED channels (plain
# numpy arrays / primitives). The live Maya handles (``_data`` MObject, ``_fn``
# function set) are NOT serializable and never in the payload; an ATTACHED
# object materializes its channels first, so what comes back is always a
# detached value object -- the same thing ``copy()`` returns.


def _geo_from_state(cls, state):
    """Unpickle hook: rebuild a DETACHED geometry object from its channels.

    Module-level (pickle must import it by name) and shared by all three
    geometry types -- the state dict is just the detached ``__dict__``."""
    obj = cls.__new__(cls)
    obj.__dict__.update(state)
    return obj


def _detached_state(obj):
    """The picklable ``__dict__`` of ``obj`` -- its channels, materialized off
    the live handle if attached, with the Maya handles dropped."""
    state = obj.copy().__dict__.copy()
    state.pop("_data", None)
    state.pop("_fn", None)
    state["_attached"] = False
    state["_name"]     = obj.name          # keep the source-shape label for display
    return state


def _jlist(arr):
    """A numpy array as nested JSON lists (or None)."""
    return None if arr is None else np.asarray(arr).tolist()


def _jtags(tags):
    return {k: {"type": v.get("type"), "indices": _jlist(v.get("indices"))}
            for k, v in (tags or {}).items()}


def _tags_from_json(payload):
    return {k: {"type": v.get("type"),
                "indices": np.asarray(v.get("indices") or [], dtype=np.int64)}
            for k, v in (payload or {}).items()}


def geometry_from_json(payload):
    """Rebuild whichever geometry type ``payload`` describes.

    ``payload`` is the dict (or JSON text) produced by any ``to_json()``; it
    carries a ``"type"`` tag naming the class."""
    if isinstance(payload, (str, bytes)):
        payload = _json.loads(payload)
    kind = payload.get("type")
    for cls in (Mesh, NurbsCurve, NurbsSurface, UVSet):
        if cls.__name__ == kind:
            return cls.from_json(payload)
    raise ValueError(
        "geometry_from_json: unknown geometry type %r (expected one of "
        "Mesh / NurbsCurve / NurbsSurface / UVSet)" % (kind,))
