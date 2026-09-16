"""Pure-numpy property tests for the twist/swing skinning math.

``skin_blend.twist_swing`` applies dual-quaternion skinning to the TWIST
about each bone's local X axis and linear-blend skinning to the remaining SWING
(bend). These tests pin the behaviour (and the twist-axis convention) with a
numpy oracle -- no Maya needed:

  * pure X-twist (any weights) == DQS  (swing collapses to identity)
  * single-joint influence      == LBS == DQS (full transform recovered)
  * identity pose               == rest
  * pure swing single joint     == LBS  (twist collapses to identity)
  * 180-deg twist               stays finite (singularity guard)
  * M_twist @ M_swing           == M    (decomposition composes back)
  * blended twist+bend          stays near LBS or DQS (no elbow collapse)
  * twist + bend                differs from BOTH LBS and DQS (genuine blend)
"""
from __future__ import annotations

import unittest

import numpy as np

from mpynode._common.methods import skin_blend


def _rx(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def _ry(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)


def _rz(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def _m_row(r_col, pos):
    """Maya row-vector 4x4 from a COLUMN rotation + position."""
    m         = np.eye(4)
    m[:3, :3] = r_col.T
    m[3, :3]  = pos
    return m


def _inv_row(m):
    """Rigid inverse of a row-vector transform."""
    r           = m[:3, :3]
    t           = m[3, :3]
    ri          = r.T
    out         = np.eye(4)
    out[:3, :3] = ri
    out[3, :3]  = -t @ ri
    return out


class TestTwistSwingSkin(unittest.TestCase):
    def setUp(self):
        rng       = np.random.default_rng(0)
        self.rest = rng.normal(size=(40, 3))
        # Two bones: bone0 identity frame; bone1 frame rotated so its local X
        # points along world Y -- exercises the twist-axis extraction on a
        # non-axis-aligned bone.
        self._rb  = [np.eye(3), _rz(np.pi / 2)]
        self._pb  = [np.array([0.0, -2.0, 0.0]), np.array([0.5, 1.0, 0.3])]
        self._jbw = [_m_row(self._rb[i], self._pb[i]) for i in range(2)]
        self.bind = np.stack([_inv_row(self._jbw[i]) for i in range(2)])
        # Blended weights along Y.
        t                   = np.clip((self.rest[:, 1] + 3.0) / 6.0, 0.0, 1.0)
        self.W              = np.stack([1.0 - t, t], axis=1)
        self.W_single       = np.zeros((40, 2))
        self.W_single[:, 0] = 1.0

    def _joint(self, rots):
        """World matrices for the two bones after applying LOCAL-frame rotations."""
        return np.stack([_m_row(rots[i], [0, 0, 0]) @ self._jbw[i]
                         for i in range(2)])

    def _mx(self, a, b):
        return float(np.abs(np.asarray(a) - np.asarray(b)).max())

    def test_pure_twist_equals_dqs(self):
        # All rotation about each bone's local X -> swing is identity -> the LBS
        # pass is a no-op, so the result must equal pure DQS (for ANY weights).
        jt  = self._joint([_rx(0.9), _rx(-1.3)])
        ts  = skin_blend.twist_swing(self.rest, self.W, jt, self.bind)
        dqs = skin_blend.dual_quaternion(self.rest, self.W, jt, self.bind)
        self.assertLess(self._mx(ts, dqs), 1e-9)

    def test_single_joint_equals_lbs_and_dqs(self):
        # One influence per vertex -> the result recovers the full rigid
        # transform, which equals both LBS and DQS for a single joint.
        jg  = self._joint([_rx(0.4) @ _ry(0.5) @ _rz(-0.3), np.eye(3)])
        ts  = skin_blend.twist_swing(self.rest, self.W_single, jg, self.bind)
        lbs = skin_blend.linear_blend(self.rest, self.W_single, jg, self.bind)
        dqs = skin_blend.dual_quaternion(self.rest, self.W_single, jg, self.bind)
        self.assertLess(self._mx(ts, lbs), 1e-9)
        self.assertLess(self._mx(ts, dqs), 1e-9)

    def test_identity_pose_is_rest(self):
        j0 = self._joint([np.eye(3), np.eye(3)])
        ts = skin_blend.twist_swing(self.rest, self.W, j0, self.bind)
        self.assertLess(self._mx(ts, self.rest), 1e-9)

    def test_pure_swing_single_joint_equals_lbs(self):
        # A single-influence pure bend (rotateY) -> twist is identity, so the
        # result equals LBS for that joint.
        js  = self._joint([_ry(0.8), np.eye(3)])
        ts  = skin_blend.twist_swing(self.rest, self.W_single, js, self.bind)
        lbs = skin_blend.linear_blend(self.rest, self.W_single, js, self.bind)
        self.assertLess(self._mx(ts, lbs), 1e-9)

    def test_180_twist_is_finite(self):
        j180 = self._joint([_rx(np.pi), _rx(np.pi)])
        ts   = skin_blend.twist_swing(self.rest, self.W, j180, self.bind)
        self.assertTrue(bool(np.isfinite(ts).all()))

    def test_decomposition_composes_to_M(self):
        jt = self._joint([_rx(0.9) @ _ry(0.6), _rx(-1.1) @ _rz(0.4)])
        M  = self.bind @ jt
        m_twist, m_swing = skin_blend._split_twist_swing(M, self.bind)
        self.assertLess(self._mx(m_twist @ m_swing, M), 1e-9)

    def test_blended_twist_bend_stays_near_lbs_or_dqs(self):
        # Regression (elbow collapse): in the BLEND region a vertex must stay
        # near EITHER the LBS or the DQS result -- the twist/swing blend lives
        # between them. Far from BOTH is the "flew off" collapse a swing about
        # the wrong (M-translation) pivot produced.
        c0   = np.array([0.0, 0.0, 0.0])
        c1   = np.array([0.0, 4.0, 0.0])
        jbw  = [_m_row(np.eye(3), c0), _m_row(np.eye(3), c1)]
        bind = np.stack([_inv_row(jbw[i]) for i in range(2)])
        th   = np.linspace(0, 2 * np.pi, 12, endpoint=False)
        ys   = np.linspace(-1.0, 8.0, 20)
        rest = np.array([[np.cos(a), y, np.sin(a)] for y in ys for a in th])
        w1   = np.clip((rest[:, 1] - 2.0) / 4.0, 0.0, 1.0)
        W    = np.stack([1.0 - w1, w1], axis=1)
        # Elbow: twist 90 (rotateX) + bend 60 (rotateZ); shoulder stays put.
        elbow          = _m_row(_rx(np.pi / 2) @ _rz(np.deg2rad(60.0)), [0, 0, 0]) @ jbw[1]
        jt             = np.stack([jbw[0], elbow])
        ts             = skin_blend.twist_swing(rest, W, jt, bind)
        lbs            = skin_blend.linear_blend(rest, W, jt, bind)
        dqs            = skin_blend.dual_quaternion(rest, W, jt, bind)
        dl             = np.linalg.norm(ts - lbs, axis=1)
        dd             = np.linalg.norm(ts - dqs, axis=1)
        implausibility = float(np.minimum(dl, dd).max())
        self.assertTrue(bool(np.isfinite(ts).all()))
        self.assertLess(implausibility, 0.6,
                        "twist/swing blend vertex flew off both LBS and DQS "
                        "(%.3f) -- swing rotating about the wrong pivot?"
                        % implausibility)

    def test_axis_default_is_x_and_byte_identical(self):
        # The twist_axis generalization must not perturb the shipped X path:
        # the default (no axis arg) is byte-for-byte identical to explicit axis=0.
        jt        = self._joint([_rx(0.9) @ _ry(0.6), _rx(-1.1) @ _rz(0.4)])
        d_default = skin_blend.twist_swing(self.rest, self.W, jt, self.bind)
        d_x       = skin_blend.twist_swing(self.rest, self.W, jt, self.bind, 0)
        self.assertLessEqual(self._mx(d_default, d_x), 0.0)  # exactly equal

    def test_axis_selects_a_different_decomposition(self):
        # A generic twist+bend pose must give DIFFERENT results under X vs Y vs Z
        # -- proving the axis argument actually drives the twist decomposition.
        jt = self._joint([_rx(0.9) @ _ry(0.6), _rx(-1.1) @ _rz(0.4)])
        dx = skin_blend.twist_swing(self.rest, self.W, jt, self.bind, 0)
        dy = skin_blend.twist_swing(self.rest, self.W, jt, self.bind, 1)
        dz = skin_blend.twist_swing(self.rest, self.W, jt, self.bind, 2)
        self.assertGreater(self._mx(dx, dy), 1e-3)
        self.assertGreater(self._mx(dx, dz), 1e-3)
        self.assertGreater(self._mx(dy, dz), 1e-3)
        for d in (dx, dy, dz):
            self.assertTrue(bool(np.isfinite(d).all()))

    def test_pure_twist_about_each_axis_equals_dqs(self):
        # Generalizes test_pure_twist_equals_dqs to Y and Z: a pure rotation
        # about the CHOSEN twist axis (in the bone's LOCAL frame) is all-twist
        # / no-swing, so the LBS swing pass is a no-op and the result equals
        # pure DQS. Same conjugation fixture -- a world-axis rotation
        # conjugated by the bind frame rotates about that axis's bind column.
        rotfn = {0: _rx, 1: _ry, 2: _rz}
        for axis in (0, 1, 2):
            R   = rotfn[axis]
            jt  = self._joint([R(0.9), R(-1.3)])
            ts  = skin_blend.twist_swing(self.rest, self.W, jt, self.bind, axis)
            dqs = skin_blend.dual_quaternion(self.rest, self.W, jt, self.bind)
            self.assertLess(self._mx(ts, dqs), 1e-9,
                            "axis %d: pure-axis twist != DQS" % axis)

    def test_differs_from_lbs_and_dqs(self):
        # A twist + bend pose: the result must deform and differ from BOTH pure
        # LBS and pure DQS (else it is not really the twist/swing blend).
        jtb = self._joint([_rx(1.0) @ _ry(0.7), _rx(-0.8) @ _ry(0.5)])
        ts  = skin_blend.twist_swing(self.rest, self.W, jtb, self.bind)
        lbs = skin_blend.linear_blend(self.rest, self.W, jtb, self.bind)
        dqs = skin_blend.dual_quaternion(self.rest, self.W, jtb, self.bind)
        self.assertGreater(self._mx(ts, self.rest), 0.1)   # deforms
        self.assertGreater(self._mx(ts, lbs),       1e-3)  # not plain LBS
        self.assertGreater(self._mx(ts, dqs),       1e-3)  # not plain DQS
        self.assertTrue(bool(np.isfinite(ts).all()))


class TestTwistSwingDual(unittest.TestCase):
    """``twist_swing_dual`` carries SEPARATE twist vs swing weight sets on one
    node. Same math as ``twist_swing`` when both sets match; genuinely different
    when they diverge (the twist_swing_skin template's raison d'etre)."""

    def setUp(self):
        rng          = np.random.default_rng(1)
        self.rest    = rng.normal(size=(40, 3))
        rb           = [np.eye(3), _rz(np.pi / 2)]
        pb           = [np.array([0.0, -2.0, 0.0]), np.array([0.5, 1.0, 0.3])]
        self._jbw    = [_m_row(rb[i], pb[i]) for i in range(2)]
        self.bind    = np.stack([_inv_row(self._jbw[i]) for i in range(2)])
        t            = np.clip((self.rest[:, 1] + 3.0) / 6.0, 0.0, 1.0)
        self.W       = np.stack([1.0 - t, t], axis=1)    # graded
        ts           = np.clip((t - 0.5) * 3.0 + 0.5, 0.0, 1.0)
        self.W_sharp = np.stack([1.0 - ts, ts], axis=1)  # sharper falloff

    def _joint(self, rots):
        return np.stack([_m_row(rots[i], [0, 0, 0]) @ self._jbw[i]
                         for i in range(2)])

    def _mx(self, a, b):
        return float(np.abs(np.asarray(a) - np.asarray(b)).max())

    def test_equal_sets_match_twist_swing(self):
        # Passing the SAME array for both weight sets must reproduce twist_swing
        # byte-for-byte (twist_swing delegates to twist_swing_dual(W, W)).
        jt     = self._joint([_rx(1.0) @ _ry(0.7), _rx(-0.8) @ _ry(0.5)])
        dual   = skin_blend.twist_swing_dual(self.rest, self.W, self.W, jt, self.bind)
        single = skin_blend.twist_swing(self.rest, self.W, jt, self.bind)
        self.assertLess(self._mx(dual, single), 0.0 + 1e-12)

    def test_distinct_sets_diverge_and_stay_finite(self):
        # A sharper SWING set (twist set unchanged) must change the result vs the
        # equal-sets case -- proving the swing pass genuinely reads swing_weights.
        jt    = self._joint([_rx(1.0) @ _ry(0.7), _rx(-0.8) @ _ry(0.5)])
        equal = skin_blend.twist_swing_dual(self.rest, self.W, self.W, jt, self.bind)
        diff = skin_blend.twist_swing_dual(self.rest, self.W, self.W_sharp, jt,
                                           self.bind)
        self.assertGreater(self._mx(diff, equal), 1e-3)
        self.assertTrue(bool(np.isfinite(diff).all()))

    def test_twist_set_drives_only_the_twist_pass(self):
        # Under a PURE X-twist pose the swing collapses to identity, so the swing
        # weights are irrelevant and any twist_weights must equal pure DQS with
        # those twist_weights -- regardless of what swing_weights are.
        jt = self._joint([_rx(0.9), _rx(-1.3)])
        dual = skin_blend.twist_swing_dual(self.rest, self.W, self.W_sharp, jt,
                                           self.bind)
        dqs = skin_blend.dual_quaternion(self.rest, self.W, jt, self.bind)
        self.assertLess(self._mx(dual, dqs), 1e-9)


if __name__ == "__main__":
    unittest.main()
