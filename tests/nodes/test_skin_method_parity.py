"""Blessed skinning methods == the underlying free-fn math (interpreted).

The centralized ``self.linear_blend(rest, weights, joint, bind)`` /
``self.dual_quaternion(...)`` methods must deform a live, painted, posed skin
to the SAME points as calling the canonical ``skin_blend`` free functions directly
with the same plugs -- i.e. the blessed ``self.method`` binding is a faithful
passthrough that reads nothing off ``self`` (every operand is an explicit arg).
"""

from __future__ import annotations

import unittest

import maya.cmds as mc
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


# Blessed self.method() form -- reads nothing off self; the plugs are explicit
# args passed by the Compute (this is the shipped-default idiom).
_METHOD_LBS = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "mesh.setPoints(rest + float(self.envelope) * (self.linear_blend("
    "rest, self.weightList, self.matrix, self.bindPreMatrix) - rest))\n"
)
_METHOD_DQS = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "mesh.setPoints(rest + float(self.envelope) * (self.dual_quaternion("
    "rest, self.weightList, self.matrix, self.bindPreMatrix) - rest))\n"
)

# Direct free-fn form -- calls the canonical skin_blend math with the same plugs,
# bypassing the blessed method. Method == free-fn proves the binding is faithful.
_FREEFN_LBS = (
    "from mpynode._common.methods import skin_blend\n"
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "d = skin_blend.linear_blend(rest, self.weightList, self.matrix, "
    "self.bindPreMatrix)\n"
    "mesh.setPoints(rest + float(self.envelope) * (d - rest))\n"
)
_FREEFN_DQS = (
    "from mpynode._common.methods import skin_blend\n"
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "d = skin_blend.dual_quaternion(rest, self.weightList, self.matrix, "
    "self.bindPreMatrix)\n"
    "mesh.setPoints(rest + float(self.envelope) * (d - rest))\n"
)
_METHOD_TWISTSWING = (
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "mesh.setPoints(rest + float(self.envelope) * (self.twist_swing("
    "rest, self.weightList, self.matrix, self.bindPreMatrix) - rest))\n"
)
_FREEFN_TWISTSWING = (
    "from mpynode._common.methods import skin_blend\n"
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "d = skin_blend.twist_swing(rest, self.weightList, self.matrix, "
    "self.bindPreMatrix)\n"
    "mesh.setPoints(rest + float(self.envelope) * (d - rest))\n"
)


class TestSkinMethodParity(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _painted_posed_skin(self, name):
        j1 = mc.joint(p=(0, 0, 0), n="mj1")
        mc.select(clear=True)
        j2 = mc.joint(p=(0, 2, 0), n="mj2")
        mc.select(clear=True)
        # axis=(0,0,1) pins the plane to XY so it genuinely spans the joint
        # chain's Y. With the default axis the plane lies in XZ and object-space
        # Y is pure float noise (~1e-16), which is NOT uniformly zero on every
        # platform: where it varies, its span is truthy, `or 1.0` never fires,
        # and the grading below normalises NOISE into a plausible-looking
        # [0, 1/3, 2/3, 1] ramp. Where the noise is exactly 0.0 instead, span is
        # falsy, every t becomes 0.0 and the skin collapses to ONE influence --
        # which these method-vs-freefn comparisons still PASS under, vacuously,
        # because both sides then compute the same degenerate case.
        plane = mc.polyPlane(name="mP", w=4, h=4, sx=3, sy=3, axis=(0, 0, 1))[0]
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        sc = MPySkinCluster.create(plane, joints=[j1, j2], name=name)
        n = mc.polyEvaluate(plane, vertex=True)
        sc.set_init_expression("import numpy as np\n")
        ys = [mc.xform("%s.vtx[%d]" % (plane, v), q=True, os=True, t=True)[1]
              for v in range(n)]
        lo, hi = min(ys), max(ys)
        span = (hi - lo) or 1.0
        for v in range(n):
            t = (ys[v] - lo) / span
            sc.set_vertex_weight(v, 0, 1.0 - t)
            sc.set_vertex_weight(v, 1, t)
        mc.setAttr(j2 + ".rotateZ", 55.0)
        mc.setAttr(j2 + ".translateX", 0.4)
        return plane, sc

    def _points(self, plane, sc, src):
        node = sc.get_name()
        sc.set_compute_expression(src)
        mc.dgdirty(node + ".outputGeometry")
        n = mc.polyEvaluate(plane, vertex=True)
        return np.asarray([
            mc.xform("%s.vtx[%d]" % (plane, v), q=True, os=True, t=True)
            for v in range(n)])

    def test_lbs_method_equals_freefn(self):
        plane, sc = self._painted_posed_skin("mLBS")
        freefn = self._points(plane, sc, _FREEFN_LBS)
        method = self._points(plane, sc, _METHOD_LBS)
        self.assertGreater(float(np.abs(freefn - freefn.mean(0)).max()), 0.1)
        self.assertTrue(np.allclose(freefn, method, atol=1e-9),
                        "LBS method != skin_blend free fn (max %r)"
                        % float(np.abs(freefn - method).max()))

    def test_dqs_method_equals_freefn(self):
        plane, sc = self._painted_posed_skin("mDQS")
        freefn = self._points(plane, sc, _FREEFN_DQS)
        method = self._points(plane, sc, _METHOD_DQS)
        self.assertGreater(float(np.abs(freefn - freefn.mean(0)).max()), 0.1)
        self.assertTrue(np.allclose(freefn, method, atol=1e-9),
                        "DQS method != skin_blend free fn (max %r)"
                        % float(np.abs(freefn - method).max()))

    def test_twist_swing_method_equals_freefn(self):
        plane, sc = self._painted_posed_skin("mTSW")
        freefn = self._points(plane, sc, _FREEFN_TWISTSWING)
        method = self._points(plane, sc, _METHOD_TWISTSWING)
        self.assertGreater(float(np.abs(freefn - freefn.mean(0)).max()), 0.1)
        self.assertTrue(np.allclose(freefn, method, atol=1e-9),
                        "twist_swing method != skin_blend free fn (max %r)"
                        % float(np.abs(freefn - method).max()))


if __name__ == "__main__":
    unittest.main()
