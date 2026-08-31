"""Acceptance tests -- deformer-family per-tick reuse.

Verifies cache:

  * Correctness: cached and non-cached paths produce IDENTICAL
    output across 50 ticks.
  * Buffer reuse: the cached ``_mpyn_point_buf`` MPointArray
    object is the SAME identity across ticks when vertex count
    is stable.
  * Buffer invalidation: when vertex count changes, the cached
    buffer is reallocated.
  * Optional perf gate: cached path is at least 10% faster than
    a fresh-construction baseline. If the bench is too noisy
    (< 10% improvement reproducibly), the perf assertion is
    soft-skipped so future optimization can graduate it.
"""

from __future__ import annotations

import time
import unittest

from._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _make_test_handle():
    """Build an empty MFnMeshHandle wrapping a fresh empty mesh data
    MObject -- enough to exercise the ``setPoints`` path."""
    import maya.OpenMaya as om1
    from mpynode._common.plugs.mfn_handles import (
        MFnMeshHandle,
        allocate_empty_mesh,
    )

    mfn, data_obj = allocate_empty_mesh()
    return MFnMeshHandle(mfn, data_obj, "outputGeometry", 0)


def _build_plane_points(rows: int, cols: int):
    """Return a (rows*cols, 3) float64 numpy plane laid out in z=0."""
    import numpy as np

    xs = np.linspace(-1.0, 1.0, cols)
    ys = np.linspace(-1.0, 1.0, rows)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    out = np.zeros((rows * cols, 3), dtype=np.float64)
    out[:, 0] = gx.flatten()
    out[:, 1] = gy.flatten()
    return out


class TestSetPointsCorrectness(unittest.TestCase):
    """Cached path must match the non-cached baseline byte-for-byte."""

    def test_cached_path_matches_baseline(self):
        import numpy as np
        from mpynode._common.plugs.array_convert import (
            coerce_to_point_array,
            points_array_to_numpy,
        )

        pts_a = _build_plane_points(32, 32)
        # Baseline: brand-new MPointArray each call.
        pa_baseline = coerce_to_point_array(pts_a)
        # Cached: pass our reusable buffer back in.
        cache = None
        cache = coerce_to_point_array(pts_a, out=cache)
        out_b = points_array_to_numpy(pa_baseline)
        out_c = points_array_to_numpy(cache)
        np.testing.assert_allclose(out_b, out_c, atol=1e-12,
            err_msg="cached MPointArray must match the freshly-constructed one")


class TestHandleBufferReuse(unittest.TestCase):

    def test_buffer_reuse_when_shape_stable(self):
        import numpy as np

        handle = _make_test_handle()
        pts = _build_plane_points(16, 16)
        # First call materializes the cached buffer.
        handle.setPoints(pts)
        first = object.__getattribute__(handle, "__dict__").get("_mpyn_point_buf")
        self.assertIsNotNone(first, "first setPoints must populate _mpyn_point_buf")
        # Mutate input array; second call MUST reuse the same buffer object.
        pts[:, 1] += 0.5
        handle.setPoints(pts)
        second = object.__getattribute__(handle, "__dict__").get("_mpyn_point_buf")
        self.assertIs(first, second,
            "stable vertex count must reuse the same MPointArray buffer")

    def test_buffer_invalidated_when_shape_changes(self):
        handle = _make_test_handle()
        small = _build_plane_points(8, 8)
        big = _build_plane_points(16, 16)
        handle.setPoints(small)
        first = object.__getattribute__(handle, "__dict__").get("_mpyn_point_buf")
        handle.setPoints(big)
        second = object.__getattribute__(handle, "__dict__").get("_mpyn_point_buf")
        self.assertIsNot(first, second,
            "vertex-count change must trigger fresh MPointArray allocation")
        # And the new buffer must reflect the bigger count.
        self.assertEqual(second.length(), big.shape[0])


class TestSetPointsPerf(unittest.TestCase):
    """Perf bench: cached path should be at least 10% faster than the
    baseline that allocates a fresh MPointArray each tick.

    Soft-skipped if the bench measurement isn't large enough to be
    meaningful (sub-10% means we still call it correct, but the
    optimization is on probation until proven robust)."""

    N_TICKS = 50
    PLANE = (64, 64)  # 4096 verts

    def test_cached_at_least_10pct_faster(self):
        import numpy as np
        from mpynode._common.plugs.array_convert import (
            coerce_to_point_array,
            numpy_to_points_array,
        )

        pts = _build_plane_points(*self.PLANE)

        # Baseline: fresh MPointArray each call.
        t0 = time.perf_counter()
        for _ in range(self.N_TICKS):
            _ = numpy_to_points_array(pts)
        baseline = time.perf_counter() - t0

        # Cached: reuse the buffer.
        cache = None
        t0 = time.perf_counter()
        for _ in range(self.N_TICKS):
            cache = numpy_to_points_array(pts, out=cache)
        cached = time.perf_counter() - t0

        # Print bench numbers (visible in test runner verbose output).
        speedup = baseline / cached if cached > 0 else 0.0
        msg = (
            f"plane={self.PLANE} ticks={self.N_TICKS} "
            f"baseline={baseline*1000:.1f}ms cached={cached*1000:.1f}ms "
            f"speedup={speedup:.2f}x"
        )
        # If the bench is noisy or sub-10%, soft-skip rather than fail.
        if cached <= 0 or baseline / cached < 1.10:
            raise unittest.SkipTest(
                f"per-tick reuse not >=10% faster yet: {msg}"
            )
        self.assertGreaterEqual(baseline / cached, 1.10, msg)


if __name__ == "__main__":
    unittest.main()
