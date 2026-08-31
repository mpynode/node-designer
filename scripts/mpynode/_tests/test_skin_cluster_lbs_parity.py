"""Interpreted parity: the shipped vectorized LBS default == the verified demo.

The shipped ``mPySkinCluster`` default Compute was rewritten to a vectorized
numpy spelling (``np.asarray(self.weightList)`` + batched ``@`` + ``einsum``) that
LOWERS to pure C++. This proves that rewrite is behavior-preserving: on a live,
fully-painted, posed skin, the vectorized default deforms the mesh to the SAME
points (1e-9) as the byte-verified sparse demo Compute
(``_demos/build_mPySkinCluster_customLBS.py``).
"""

from __future__ import annotations

import unittest

import maya.cmds as mc
import numpy as np

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestVectorizedDefaultMatchesDemo(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _build_full_painted_skin(self):
        """A plane skinned by a 2-joint chain, EVERY vertex painted with a
        height-graded blend (so both influences contribute), and the second
        joint posed so the deform is non-trivial."""
        j1 = mc.joint(p=(0, 0, 0), n="pj1")
        mc.select(clear=True)
        j2 = mc.joint(p=(0, 2, 0), n="pj2")
        mc.select(clear=True)
        # axis=(0,0,1) pins the plane to XY so it genuinely spans the joint
        # chain's Y. With the default axis the plane lies in XZ and object-space
        # Y is pure float noise (~1e-16), which is NOT uniformly zero on every
        # platform: where it varies, its span is truthy, `or 1.0` never fires,
        # and the grading below normalises NOISE into a plausible-looking
        # [0, 1/3, 2/3, 1] ramp -- this test passed on macOS that way. Where the
        # noise is exactly 0.0 instead, span is falsy, every t becomes 0.0,
        # every vertex paints (1.0, 0.0), skinPercent PRUNES the zero, and the
        # weightList densifies to ONE influence column against a two-influence
        # matrix array.
        plane = mc.polyPlane(name="pP", w=4, h=4, sx=3, sy=3, axis=(0, 0, 1))[0]

        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        sc = MPySkinCluster.create(plane, joints=[j1, j2], name="parSkin")
        node = sc.get_name()

        n = mc.polyEvaluate(plane, vertex=True)
        sc.set_init_expression("import numpy as np\n")
        # Grade the weight by vertex height (y): bottom -> j1, top -> j2.
        ys = [mc.xform("%s.vtx[%d]" % (plane, v), q=True, os=True, t=True)[1]
              for v in range(n)]
        lo, hi = min(ys), max(ys)
        span = (hi - lo) or 1.0
        for v in range(n):
            t = (ys[v] - lo) / span
            mc.skinPercent(node, "%s.vtx[%d]" % (plane, v),
                           transformValue=[(j1, 1.0 - t), (j2, t)])

        # Pose the second joint so both influences actually move the mesh.
        mc.setAttr(j2 + ".rotateZ", 40.0)
        mc.setAttr(j2 + ".translateX", 0.5)
        return plane, sc

    def _deformed_points(self, plane, sc, compute_src):
        node = sc.get_name()
        sc.set_compute_expression(compute_src)
        mc.dgdirty(node + ".outputGeometry")
        n = mc.polyEvaluate(plane, vertex=True)
        return np.asarray([
            mc.xform("%s.vtx[%d]" % (plane, v), q=True, os=True, t=True)
            for v in range(n)
        ])

    def test_vectorized_default_equals_sparse_demo(self):
        import mpynode._demos.build_mPySkinCluster_customLBS as builder
        from mpynode._defaults import skin_cluster_defaults as scd

        plane, sc = self._build_full_painted_skin()

        demo_pts = self._deformed_points(plane, sc, builder.COMPUTE_SOURCE)
        new_pts = self._deformed_points(plane, sc, scd.DEFAULT_COMPUTE_SOURCE)

        # non-trivial deform: the posed result must differ from the flat rest.
        self.assertGreater(float(np.abs(demo_pts - demo_pts.mean(0)).max()), 0.1)
        self.assertTrue(
            np.allclose(demo_pts, new_pts, atol=1e-9),
            "vectorized default deviates from the verified sparse demo:\n"
            "max abs diff = %r" % float(np.abs(demo_pts - new_pts).max()),
        )


if __name__ == "__main__":
    unittest.main()
