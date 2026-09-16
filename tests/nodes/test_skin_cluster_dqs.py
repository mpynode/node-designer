"""Correctness invariants for the shipped dual-quaternion (DQS) default.

DQS is only "correct" if it satisfies the rigid-skinning invariants:
  * SINGLE influence -> exact rigid transform of the rest points, which is
    identical to what LBS produces (both reduce to ``rest @ M``). This pins the
    quaternion round-trip (matrix -> quat -> matrix) + the dual-part translation.
  * BIND pose (all M == identity) -> rest (no deform).
  * A genuine multi-influence blend DIFFERS from LBS (else the default is
    accidentally linear, not dual-quaternion).

Run on a live ``mPySkinCluster`` driving the DQS default Compute, so it exercises
exactly the shipped source string.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestDQSInvariants(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _skin(self, weights, name):
        """A 3x3 plane skinned by a 2-joint chain; ``weights`` is a callable
        (t) -> (w0, w1) over the normalised vertex height."""
        j1 = mc.joint(p=(0, 0, 0), n="dj1")
        mc.select(clear=True)
        j2 = mc.joint(p=(0, 2, 0), n="dj2")
        mc.select(clear=True)
        # axis=(0,0,1) pins the plane to XY so it genuinely spans the joint
        # chain's Y. With the default axis the plane lies in XZ and object-space
        # Y is pure float noise (~1e-16). That noise is NOT uniformly zero on
        # every platform: where it varies, its span is truthy, `or 1.0` never
        # fires, and the grading below normalises NOISE into a plausible-looking
        # [0, 1/3, 2/3, 1] ramp -- this test passed on macOS that way. Where the
        # noise is exactly 0.0 instead, span is falsy, every t becomes 0.0, and
        # the skin collapses to a single influence, where DQS is identical to
        # LBS by definition.
        plane = mc.polyPlane(name="dP", w=4, h=4, sx=3, sy=3, axis=(0, 0, 1))[0]

        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        sc = MPySkinCluster.create(plane, joints=[j1, j2], name=name)
        n  = mc.polyEvaluate(plane, vertex=True)
        ys = [mc.xform("%s.vtx[%d]" % (plane, v), q=True, os=True, t=True)[1]
              for v in range(n)]
        lo, hi = min(ys), max(ys)
        span = (hi - lo) or 1.0
        for v in range(n):
            w0, w1 = weights((ys[v] - lo) / span)
            sc.set_vertex_weight(v, 0, float(w0))
            sc.set_vertex_weight(v, 1, float(w1))
        return plane, sc, (j1, j2)

    def _points(self, plane, sc, src):
        node = sc.get_name()
        sc.set_init_expression("import numpy as np\n")
        sc.set_compute_expression(src)
        mc.dgdirty(node + ".outputGeometry")
        n = mc.polyEvaluate(plane, vertex=True)
        return np.asarray([
            mc.xform("%s.vtx[%d]" % (plane, v), q=True, os=True, t=True)
            for v in range(n)])

    def test_single_influence_equals_lbs(self):
        # All weight on j2 -> a single rigid influence; DQS == LBS == rest @ M.
        from mpynode._defaults import skin_cluster_defaults as lbs
        from mpynode._defaults import skin_cluster_dqs_defaults as dqs

        plane, sc, (j1, j2) = self._skin(lambda t: (0.0, 1.0), "dqsSingle")
        mc.setAttr(j2 + ".rotateZ", 40.0)
        mc.setAttr(j2 + ".translateX", 0.5)
        lbs_pts = self._points(plane, sc, lbs.DEFAULT_COMPUTE_SOURCE)
        dqs_pts = self._points(plane, sc, dqs.DEFAULT_COMPUTE_SOURCE)
        self.assertGreater(float(np.abs(lbs_pts - lbs_pts.mean(0)).max()), 0.1)
        self.assertTrue(
            np.allclose(lbs_pts, dqs_pts, atol=1e-6),
            "single-influence DQS != LBS (max %r)"
            % float(np.abs(lbs_pts - dqs_pts).max()))

    def test_bind_pose_is_rest(self):
        from mpynode._defaults import skin_cluster_dqs_defaults as dqs
        plane, sc, _ = self._skin(lambda t: (1.0 - t, t), "dqsBind")
        rest = np.asarray([
            mc.xform("%s.vtx[%d]" % (plane, v), q=True, os=True, t=True)
            for v in range(mc.polyEvaluate(plane, vertex=True))])
        out = self._points(plane, sc, dqs.DEFAULT_COMPUTE_SOURCE)  # unposed
        self.assertTrue(np.allclose(out, rest, atol=1e-6),
                        "DQS bind pose deviates from rest (max %r)"
                        % float(np.abs(out - rest).max()))

    def test_blend_differs_from_lbs(self):
        # A graded two-influence blend under a real bend: DQS must differ from
        # LBS (dual-quaternion vs linear), else it's not really DQS.
        from mpynode._defaults import skin_cluster_defaults as lbs
        from mpynode._defaults import skin_cluster_dqs_defaults as dqs
        plane, sc, (j1, j2) = self._skin(lambda t: (1.0 - t, t), "dqsBlend")
        mc.setAttr(j2 + ".rotateZ", 80.0)
        lbs_pts = self._points(plane, sc, lbs.DEFAULT_COMPUTE_SOURCE)
        dqs_pts = self._points(plane, sc, dqs.DEFAULT_COMPUTE_SOURCE)
        self.assertGreater(float(np.abs(lbs_pts - dqs_pts).max()), 1e-3,
                           "DQS is indistinguishable from LBS on a real blend")


if __name__ == "__main__":
    unittest.main()
