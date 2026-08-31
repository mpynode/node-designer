"""Golden parity harness for the SDF dual-marching-cubes helper.

``_common/nodes/mesh/sdf_dmc.py`` is the SHARED helper the LIVE Python ``mPyMesh``
metaballs node runs. The #37 effort refactors it into a transpiler-friendly form so
the native compiler's DETERMINISTIC path (nd_lower -> py_to_cpp) can lower it instead
of falling to the slow AI porter. Those refactors MUST be behaviour-preserving.

This module freezes the CURRENT ``mesh_from_shapes`` output on a battery of
representative cases as a golden fixture, and gates every later refactor against it:
``points`` must match within a tight tolerance, and ``counts`` / ``indices`` (and the
vertex ordering implied by element-wise point comparison) must match EXACTLY.

The helper is pure-numpy, so this runs WITHOUT Maya (fast refactor loop):

    python3 native/tests/sdf_dmc_parity.py capture   # freeze golden (run on ORIGINAL)
    python3 native/tests/sdf_dmc_parity.py check      # assert current == golden

It is also exposed as a unittest (``SdfDmcParityTest``) for the native gate.
"""
from __future__ import annotations

import importlib.util
import os

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SDF_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "..", "_common", "nodes", "mesh", "sdf_dmc.py"))
_GOLDEN = os.path.join(_HERE, "fixtures", "sdf_dmc_golden.npz")

# Points come from linear edge interpolation; a behaviour-preserving refactor may
# reassociate a few float ops, so allow a tight absolute tolerance. counts/indices
# are integers and must match EXACTLY (any face/topology change fails).
_PT_ATOL = 1e-9


def _load_sdf():
    """Import sdf_dmc.py by file path (no mpynode package __init__ -> no Maya)."""
    spec = importlib.util.spec_from_file_location("sdf_dmc_under_test", _SDF_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mat(translate=(0, 0, 0), euler=(0, 0, 0), scale=(1, 1, 1), rotate_order=0):
    """Compose a Maya row-vector 4x4 (M3 = diag(scale) @ R, translate in row 3)
    using the helper's own euler_to_matrix so test matrices decompose cleanly."""
    m = _load_sdf()
    R = m.euler_to_matrix(np.asarray(euler, dtype=np.float64), rotate_order)[:3, :3]
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = np.diag(np.asarray(scale, dtype=np.float64)) @ R
    M[3, :3] = np.asarray(translate, dtype=np.float64)
    return M


def build_cases():
    """Deterministic input sets exercising every sdf_dmc code path.

    Each case is a dict with the full mesh_from_shapes(...) argument set. Shapes:
    0=sphere, 1=box, 2=cylinder. No RNG -- fully reproducible.
    """
    d64 = np.float64
    cases = {}

    def case(name, mats, stype, add, smooth, rad, hgt, ax, half, res, iso=0.0):
        cases[name] = dict(
            matrices=np.asarray(mats, dtype=d64),
            shape_types=np.asarray(stype, dtype=np.int64),
            additive=np.asarray(add, dtype=bool),
            smoothing=np.asarray(smooth, dtype=d64),
            radius=np.asarray(rad, dtype=d64),
            height=np.asarray(hgt, dtype=d64),
            axis=np.asarray(ax, dtype=np.int64),
            half_extents=np.asarray(half, dtype=d64),
            resolution=res,
            iso_value=iso,
        )

    I = np.eye(4, dtype=d64)
    H = [0.5, 0.5, 0.5]

    # --- single primitives ---
    case("sphere", [I], [0], [True], [0.0], [1.0], [1.0], [1], [H], 8)
    case("box_rot", [_mat(euler=(0.3, 0.5, -0.2))], [1], [True], [0.0],
         [1.0], [1.0], [1], [[0.6, 0.4, 0.5]], 8)
    case("cyl_axis1", [I], [2], [True], [0.0], [0.5], [1.4], [1], [H], 8)
    # cylinder along X and Z exercise eval_cylinder's radial-axis selection.
    case("cyl_axis0", [I], [2], [True], [0.0], [0.5], [1.4], [0], [H], 8)
    case("cyl_axis2", [I], [2], [True], [0.0], [0.5], [1.4], [2], [H], 8)

    # --- CSG ops ---
    case("union", [_mat(translate=(-0.4, 0, 0)), _mat(translate=(0.4, 0, 0))],
         [0, 0], [True, True], [0.0, 0.0], [1.0, 1.0], [1.0, 1.0], [1, 1],
         [H, H], 8)
    case("smooth_union",
         [_mat(translate=(-0.5, 0, 0)), _mat(translate=(0.5, 0, 0))],
         [0, 0], [True, True], [0.0, 0.35], [1.0, 1.0], [1.0, 1.0], [1, 1],
         [H, H], 10)
    case("difference", [I, _mat(translate=(0.6, 0.3, 0.2))],
         [1, 0], [True, False], [0.0, 0.0], [1.0, 0.7], [1.0, 1.0], [1, 1],
         [[0.9, 0.9, 0.9], H], 8)

    # --- transforms: non-uniform scale + rotation (decompose/affine_inverse) ---
    case("scaled_rot",
         [_mat(translate=(0.1, -0.2, 0.05), euler=(0.4, -0.3, 0.6),
               scale=(1.4, 0.7, 1.1))],
         [0], [True], [0.0], [1.0], [1.0], [1], [H], 8)

    # --- multi-shape mixed ---
    case("multi",
         [_mat(translate=(-0.6, 0, 0)),
          _mat(translate=(0.6, 0, 0), scale=(1.0, 1.3, 1.0)),
          _mat(translate=(0, 0.6, 0), euler=(0, 0.5, 0))],
         [0, 1, 2], [True, True, False], [0.0, 0.2, 0.0],
         [1.0, 1.0, 0.5], [1.0, 1.0, 1.2], [1, 1, 1],
         [H, [0.7, 0.5, 0.6], H], 9)

    # --- edge cases ---
    case("empty", np.zeros((0, 4, 4), dtype=d64), [], [], [], [], [], [],
         np.zeros((0, 3), dtype=d64), 8)
    case("tiny_res", [I], [0], [True], [0.0], [1.0], [1.0], [1], [H], 2)
    case("iso_shift", [I], [0], [True], [0.0], [1.2], [1.0], [1], [H], 8, iso=0.15)

    return cases


def _run(mod, c):
    return mod.mesh_from_shapes(
        c["matrices"], c["shape_types"], c["additive"], c["smoothing"],
        c["radius"], c["height"], c["axis"], c["half_extents"],
        c["resolution"], c["iso_value"])


def capture(path=_GOLDEN):
    """Freeze the CURRENT sdf_dmc output for every case into an .npz golden."""
    mod = _load_sdf()
    cases = build_cases()
    blob = {}
    for name, c in cases.items():
        pts, cnts, idx = _run(mod, c)
        blob["%s__points" % name] = np.asarray(pts, dtype=np.float64)
        blob["%s__counts" % name] = np.asarray(cnts, dtype=np.int64)
        blob["%s__indices" % name] = np.asarray(idx, dtype=np.int64)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, **blob)
    return {name: (blob["%s__points" % name].shape[0],
                   blob["%s__counts" % name].shape[0]) for name in cases}


def compare_to_golden(path=_GOLDEN):
    """Return {case: reason} for every mismatch vs the golden (empty == all pass)."""
    mod = _load_sdf()
    cases = build_cases()
    golden = np.load(path)
    fails = {}
    for name, c in cases.items():
        pts, cnts, idx = _run(mod, c)
        pts = np.asarray(pts, dtype=np.float64)
        cnts = np.asarray(cnts, dtype=np.int64)
        idx = np.asarray(idx, dtype=np.int64)
        gp = golden["%s__points" % name]
        gc = golden["%s__counts" % name]
        gi = golden["%s__indices" % name]
        if pts.shape != gp.shape:
            fails[name] = "points shape %s != golden %s" % (pts.shape, gp.shape)
            continue
        if not np.array_equal(cnts, gc):
            fails[name] = "counts differ (%d vs %d faces)" % (cnts.shape[0], gc.shape[0])
            continue
        if not np.array_equal(idx, gi):
            fails[name] = "indices differ"
            continue
        if pts.size and not np.allclose(pts, gp, atol=_PT_ATOL, rtol=0.0):
            fails[name] = "points differ (max abs %.2e)" % float(np.max(np.abs(pts - gp)))
            continue
    return fails


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "capture":
        summ = capture()
        print("captured golden ->", _GOLDEN)
        for n, (v, f) in sorted(summ.items()):
            print("  %-14s verts=%-6d faces=%d" % (n, v, f))
    else:
        fails = compare_to_golden()
        if fails:
            print("PARITY FAIL:")
            for n, r in sorted(fails.items()):
                print("  %-14s %s" % (n, r))
            sys.exit(1)
        print("PARITY OK (all %d cases match golden)" % len(build_cases()))
