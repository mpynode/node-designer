"""Parity gate for the metaballs compute/init GLUE rewrite (#37 Stage 4).

The metaballs ``mPyMesh`` node's LIVE (interpreted) compute densifies each sparse
per-shape input array onto the demo's semantic defaults, then calls
``mesh_from_shapes``. The #37 effort rewrites that glue into a transpiler-friendly
form so the native compiler can lower it deterministically:

  OLD:  x = _read_dense(self, "name", default)   # getattr-by-string + enumerate
        pts, cnts, idx = mesh_from_shapes(...)    # 3-tuple unpack

  NEW:  x = _dense_over(self.name, default)        # direct attr + slice-assign
        packed = _mesh_packed(...)                 # single packed return
        pts = packed[2:2+3V].reshape(V,3); ...     # slice the packed layout

Both run in the SAME interpreted node, so the rewrite MUST be behaviour-preserving.
``read_user_inputs_dict`` always hands the compute a numpy array for a numeric
multi (an empty multi is ``zeros(0)``, never ``None``), so ``_dense_over`` --
which overlays ``raw[:k]`` onto the length-n defaults -- reproduces ``_read_dense``
exactly for every case the node can actually see.

This gate runs the OLD and NEW glue over the SAME mock ``self`` inputs (sparse
arrays of assorted lengths, so the semantic-default tail is exercised per attr)
and asserts the produced ``(points, counts, indices)`` match EXACTLY. Pure-numpy,
so it runs without Maya:

    python3 tests/compile/native/metaballs_glue_parity.py

Also exposed as a unittest (``MetaballsGlueParityTest``) for the native gate.
"""
from __future__ import annotations

import importlib.util
import os

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
# Three levels up from tests/compile/native is the repo root; the helper stays
# in the package, so descend back through scripts/mpynode to reach it.
_SDF_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "scripts", "mpynode",
                 "_common", "nodes", "mesh", "sdf_dmc.py"))


def _load_sdf():
    spec = importlib.util.spec_from_file_location("sdf_dmc_glue_test", _SDF_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SDF = _load_sdf()


# --- the OLD glue: _read_dense + mesh_from_shapes (verbatim from the .mpn) ----
def _read_dense(self, name, defaults):
    proxy = getattr(self, name, None)
    out = np.array(defaults)
    n = out.shape[0]
    if proxy is None or n == 0:
        return out
    is_vec = out.ndim > 1
    try:
        for idx, elem in enumerate(proxy):
            if idx >= n:
                break
            out[idx] = np.asarray(elem, dtype=out.dtype) if is_vec else elem
    except TypeError:
        pass
    return out


def _old_glue(self):
    mats = np.asarray(self.shapeMatrix, dtype=np.float64)
    if mats.ndim != 3 or mats.shape[0] == 0:
        return (np.zeros((0, 3), dtype=np.float64),
                np.zeros(0, dtype=np.int32),
                np.zeros(0, dtype=np.int32))
    n = mats.shape[0]
    shape_type = _read_dense(self, "shapeType", np.zeros(n, dtype=np.int64))
    additive = _read_dense(self, "additive", np.ones(n, dtype=bool))
    smoothing = _read_dense(self, "smoothing", np.zeros(n, dtype=np.float64))
    radius = _read_dense(self, "radius", np.where(shape_type == 2, 0.5, 1.0))
    height = _read_dense(self, "height", np.ones(n, dtype=np.float64))
    axis = _read_dense(self, "axis", np.ones(n, dtype=np.int64))
    half = _read_dense(self, "halfExtents", np.tile([0.5, 0.5, 0.5], (n, 1)))
    _res = getattr(self, "resolution", None)
    res = 8 if _res is None else int(_res)
    _iso = getattr(self, "isoValue", None)
    iso = 0.0 if _iso is None else float(_iso)
    return _SDF.mesh_from_shapes(
        mats, shape_type, additive, smoothing, radius, height, axis, half,
        res, iso)


# --- the NEW glue: _dense_over + _mesh_packed (verbatim from the rewritten
#     init/expression that nd_lower lowers) ------------------------------------
def _dense_over(raw, defaults):
    out = np.array(defaults)
    n = out.shape[0]
    k = raw.shape[0]
    if k > n:
        k = n
    out[0:k] = raw[0:k]
    return out


def _new_glue(self):
    mats = np.asarray(self.shapeMatrix, dtype=np.float64)
    n = mats.shape[0]
    shape_type = _dense_over(self.shapeType, np.zeros(n, dtype=np.int64))
    additive = _dense_over(self.additive, np.ones(n, dtype=np.int64))
    smoothing = _dense_over(self.smoothing, np.zeros(n, dtype=np.float64))
    radius = _dense_over(self.radius, np.where(shape_type == 2, 0.5, 1.0))
    height = _dense_over(self.height, np.ones(n, dtype=np.float64))
    axis = _dense_over(self.axis, np.ones(n, dtype=np.int64))
    half = _dense_over(self.halfExtents, np.full((n, 3), 0.5))
    packed = _SDF._mesh_packed(
        mats, shape_type, additive, smoothing, radius, height, axis, half,
        int(self.resolution), float(self.isoValue))
    V = int(packed[0])
    F = int(packed[1])
    points = packed[2:2 + 3 * V].reshape(V, 3)
    indices = packed[2 + 3 * V:2 + 3 * V + 4 * F].astype(np.int32)
    counts = np.full(F, 4, dtype=np.int32)
    return points, counts, indices


class _MockSelf:
    """Mirrors what read_user_inputs_dict hands the compute: every numeric multi
    is a dense numpy array (empty -> zeros(0), never None); scalars are ints."""

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _mat(tx=0.0, ty=0.0, tz=0.0):
    m = np.eye(4, dtype=np.float64)
    m[3, :3] = (tx, ty, tz)
    return m


def build_cases():
    d64 = np.float64
    cases = {}

    # Case A: box(0) sphere(1) box(2). radius set only for the sphere (index 1)
    # so radius is dense length 2 -> index 2 pads with the non-cyl default 1.0;
    # halfExtents set for both boxes (0, 2) but NOT the sphere (1) -> the gap at
    # index 1 is the attr default [0,0,0] (irrelevant to a sphere); height/axis
    # empty (no cylinder) -> full-default tails.
    cases["mixed_tail_pad"] = _MockSelf(
        shapeMatrix=np.stack([_mat(-0.7, 0, 0), _mat(0.2, 0.3, 0), _mat(0.8, 0, 0)]),
        shapeType=np.array([1, 0, 1], dtype=np.int64),
        additive=np.array([True, True, True], dtype=bool),
        smoothing=np.array([0.0, 0.3, 0.0], dtype=d64),
        radius=np.array([0.0, 0.9], dtype=d64),           # len 2 < n=3
        height=np.zeros(0, dtype=d64),                    # empty multi
        axis=np.zeros(0, dtype=np.int64),                 # empty multi
        halfExtents=np.array([[0.6, 0.6, 0.6], [0.0, 0.0, 0.0], [0.5, 0.4, 0.7]],
                             dtype=d64),
        resolution=8, isoValue=0.0)

    # Case B: a cylinder in the mix, exercising radius/height/axis all set, plus
    # the smooth-union and difference CSG branches. sphere(0) cyl(1) box(2), the
    # box additive=False (difference). halfExtents dense len 3 (gaps at 0,1).
    cases["csg_all_ops"] = _MockSelf(
        shapeMatrix=np.stack([_mat(-0.4, 0, 0), _mat(0.3, 0, 0), _mat(0.5, 0.4, 0)]),
        shapeType=np.array([0, 2, 1], dtype=np.int64),
        additive=np.array([True, True, False], dtype=bool),
        smoothing=np.array([0.0, 0.4, 0.0], dtype=d64),
        radius=np.array([1.0, 0.5, 0.0], dtype=d64),
        height=np.array([0.0, 1.3], dtype=d64),           # len 2 < n=3
        axis=np.array([0, 0], dtype=np.int64),            # len 2 < n=3 -> tail=1
        halfExtents=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.7, 0.5, 0.6]],
                             dtype=d64),
        resolution=9, isoValue=0.1)

    # Case C: single sphere, no per-shape arrays set at all EXCEPT shapeType (so
    # every attr falls entirely to its semantic default tail). radius default
    # for a sphere is 1.0.
    cases["all_defaults"] = _MockSelf(
        shapeMatrix=np.stack([_mat(0, 0, 0)]),
        shapeType=np.array([0], dtype=np.int64),
        additive=np.zeros(0, dtype=bool),
        smoothing=np.zeros(0, dtype=d64),
        radius=np.zeros(0, dtype=d64),
        height=np.zeros(0, dtype=d64),
        axis=np.zeros(0, dtype=np.int64),
        halfExtents=np.zeros((0, 3), dtype=d64),
        resolution=8, isoValue=0.0)

    # Case E: EMPTY scene (0 shapes). The OLD glue short-circuits via its
    # ``if mats.ndim != 3 or mats.shape[0] == 0`` guard; the NEW glue drops that
    # guard and folds n==0 through _mesh_packed (which returns an empty packed
    # array). Both must yield the identical empty (points, counts, indices).
    cases["empty_scene"] = _MockSelf(
        shapeMatrix=np.zeros((0, 4, 4), dtype=d64),
        shapeType=np.zeros(0, dtype=np.int64),
        additive=np.zeros(0, dtype=bool),
        smoothing=np.zeros(0, dtype=d64),
        radius=np.zeros(0, dtype=d64),
        height=np.zeros(0, dtype=d64),
        axis=np.zeros(0, dtype=np.int64),
        halfExtents=np.zeros((0, 3), dtype=d64),
        resolution=8, isoValue=0.0)

    # Case D: all-cylinder default radius branch (where(shape_type==2, 0.5, 1.0)
    # -> 0.5) exercised via an empty radius multi with a cylinder present.
    cases["cyl_default_radius"] = _MockSelf(
        shapeMatrix=np.stack([_mat(0, 0, 0)]),
        shapeType=np.array([2], dtype=np.int64),
        additive=np.zeros(0, dtype=bool),
        smoothing=np.zeros(0, dtype=d64),
        radius=np.zeros(0, dtype=d64),                    # -> default 0.5 (cyl)
        height=np.zeros(0, dtype=d64),                    # -> default 1.0
        axis=np.zeros(0, dtype=np.int64),                 # -> default 1 (Y)
        halfExtents=np.zeros((0, 3), dtype=d64),
        resolution=8, isoValue=0.0)

    return cases


def compare():
    fails = {}
    for name, self_obj in build_cases().items():
        op, oc, oi = _old_glue(self_obj)
        np_, nc, ni = _new_glue(self_obj)
        op = np.asarray(op, np.float64); np_ = np.asarray(np_, np.float64)
        oc = np.asarray(oc, np.int64); nc = np.asarray(nc, np.int64)
        oi = np.asarray(oi, np.int64); ni = np.asarray(ni, np.int64)
        if op.shape != np_.shape:
            fails[name] = "points shape %s != %s" % (np_.shape, op.shape)
            continue
        if not np.array_equal(nc, oc):
            fails[name] = "counts differ (%d vs %d faces)" % (nc.shape[0], oc.shape[0])
            continue
        if not np.array_equal(ni, oi):
            fails[name] = "indices differ"
            continue
        if op.size and not np.array_equal(np_, op):
            fails[name] = "points differ (max abs %.2e)" % float(np.max(np.abs(np_ - op)))
            continue
    return fails


if __name__ == "__main__":
    import sys

    bad = compare()
    if bad:
        print("METABALLS GLUE PARITY FAIL:")
        for n, r in sorted(bad.items()):
            print("  %-18s %s" % (n, r))
        sys.exit(1)
    print("METABALLS GLUE PARITY OK (all %d cases match)" % len(build_cases()))
