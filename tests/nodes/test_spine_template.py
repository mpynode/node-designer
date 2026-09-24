"""Compute checks for the Spine template (``MPyNode/Spine``), Maya-free.

Spine builds its own uniform B-spline from ``controlMatrices`` and drives the
riders' rotation and scale the way rig/examples/rail_spine.py does. These tests
run the SHIPPED init_source + compute on plain numpy with a stand-in ``self``
-- exactly what the interpreted node runs -- against:

* the rail_spine reference (tests/data/spine_rail_spine_oracle.json): 5 cases,
  50 states -- flagged drivers, Frozen / Infinite / Clamped, open and closed;
* the curve's own maths: clamped ends, arc-length spacing, a closed curve
  registered on control 0 and wrapping for any shift, right-handed frames, the
  driver modes and the basis weights.

The compiled node is held to the same source by the compile's parity check and
the template's own ``@maya_test`` methods.
"""

import json
import math
import os
import unittest

import numpy as np

_ROOT   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MPN    = os.path.join(_ROOT, "templates", "MPyNode", "Spine", "template.mpn")
_ORACLE = os.path.join(_ROOT, "tests", "data", "spine_rail_spine_oracle.json")


class _Mat(object):
    """A matrix input: numpy-convertible, with the wrapper's ``scale()``."""

    def __init__(self, m):
        self.m = np.asarray(m, dtype=np.float64).reshape(4, 4)

    def scale(self):
        return np.linalg.norm(self.m[:3, :3], axis=1)

    def __array__(self, dtype=None, copy=None):
        return self.m if dtype is None else self.m.astype(dtype)


class _MatArray(list):
    def __array__(self, dtype=None, copy=None):
        a = np.asarray([x.m for x in self], dtype=np.float64).reshape(-1, 4, 4)
        return a if dtype is None else a.astype(dtype)


class _Self(object):
    pass


def _template():
    with open(_MPN, encoding="utf-8") as fh:
        return json.load(fh)["data"]


_DATA = _template()


def _defaults():
    """Every input at the node's own default (arrays empty, matrices identity)."""
    out = {}
    for name, meta in _DATA["input_attrs"].items():
        t = meta["attr_type"]
        if t == "matrix":
            out[name] = _MatArray() if meta.get("is_array") else _Mat(np.eye(4))
        elif meta.get("is_array"):
            out[name] = np.zeros(0, dtype=np.int64 if t == "int" else np.float64)
        else:
            out[name] = meta.get("default_value", 0)
    return out


def _matrix(pos, rows=None, scale=(1.0, 1.0, 1.0)):
    m = np.eye(4)
    if rows is not None:
        m[:3, :3] = np.asarray(rows, dtype=np.float64)
    m[:3, :3] *= np.asarray(scale, dtype=np.float64)[:, None]
    m[3, :3] = pos
    return _Mat(m)


def run(controls, **inputs):
    """Run the compute; ``controls`` is a list of _Mat. Returns ``self``."""
    ns = {}
    exec(compile(_DATA["init_source"], "<spine init>", "exec"), ns)
    s = _Self()
    for k, v in dict(_defaults(), controlMatrices=_MatArray(controls), **inputs).items():
        if isinstance(v, (list, tuple)) and not isinstance(v, _MatArray):
            v = np.asarray(v, dtype=np.float64)
        setattr(s, k, v)
    ns["self"] = s
    exec(compile(_DATA["expression"], "<spine compute>", "exec"), ns)
    return s


def rows(e):
    """Row-vector rotation rows of an XYZ euler (radians): Rx * Ry * Rz."""
    cx, sx = math.cos(e[0]), math.sin(e[0])
    cy, sy = math.cos(e[1]), math.sin(e[1])
    cz, sz = math.cos(e[2]), math.sin(e[2])
    return np.array([[cy * cz, cy * sz, -sy],
                     [sx * sy * cz - cx * sz, sx * sy * sz + cx * cz, sx * cy],
                     [cx * sy * cz + sx * sz, cx * sy * sz - sx * cz, cx * cy]])


def _points(pts):
    return [_matrix(p) for p in pts]


_ZIGZAG = [(0.0, 0.0, 0.0), (3.0, 4.0, 1.0), (6.0, -1.0, 2.5), (9.0, 3.5, -1.0), (12.0, 0.5, 0.5)]
_PENTA = [(4.0 * math.cos(2.0 * math.pi * k / 5.0), 0.0, 4.0 * math.sin(2.0 * math.pi * k / 5.0))
           for k in range(5)]


class TestRailSpineReference(unittest.TestCase):
    """Rider for rider against the real rail_spine rig (after moving a control,
    so rest and live keys differ): scale straight from the driver blend,
    rotation rows, and positions (these carry Maya's motionPath arc-length
    error, hence the looser bound)."""

    def test_matches_rail_spine(self):
        with open(_ORACLE, encoding="utf-8") as fh:
            oracle = json.load(fh)
        ns = {}
        exec(compile(_DATA["init_source"], "<spine init>", "exec"), ns)
        for cname, case in oracle["cases"].items():
            per   = case["periodic"]
            restK = ns["_sp_chord_keys"](np.asarray(case["rest_positions"]), per)
            ctrls = [_Mat(m) for m in case["control_matrices"]]
            rflag = [1.0 if k in case["rotate_controls"] else 0.0 for k in range(5)]
            sflag = [1.0 if k in case["scale_controls"] else 0.0 for k in range(5)]
            worst = [0.0, 0.0, 0.0]
            for st in case["states"]:
                out = run(ctrls, samples=case["u"], degree=case["degree"], periodic=per,
                          stretch=st["stretch"], shift=st["shift"], pivot=st["pivot"],
                          scale=st["scale"], defaultLength=st["defaultLength"],
                          restKeys=restK, curveAimAxis=case["aim_axis"],
                          curveUpAxis=case["up_axis"],
                          rotateMode=1 if case["rotate_controls"] else 2, rotateFlags=rflag,
                          rotateProjection=st["rotateProjection"],
                          scaleMode=1 if case["scale_controls"] else 2, scaleFlags=sflag,
                          scaleProjection=st["scaleProjection"])
                for r in st["riders"]:
                    i        = r["index"]
                    worst[0] = max(worst[0], float(np.abs(out.outputScale[i] - r["scale"]).max()))
                    worst[1] = max(worst[1], float(np.abs(rows(out.outputRotate[i]).reshape(-1)
                                                          - r["rows"]).max()))
                    worst[2] = max(worst[2], float(np.abs(out.outputTranslate[i]
                                                          - r["translate"]).max()))
            with self.subTest(case=cname):
                self.assertLess(worst[0], 1e-4, "scale off rail_spine")
                self.assertLess(worst[1], 5e-4, "rotation off rail_spine")
                self.assertLess(worst[2], 2e-2, "position off rail_spine")


class TestCurve(unittest.TestCase):

    def test_open_curve_is_clamped_to_the_end_controls(self):
        for d in (1, 2, 3, 4):
            out = run(_points(_ZIGZAG), samples=[0.0, 1.0], degree=d)
            with self.subTest(degree=d):
                np.testing.assert_allclose(out.outputTranslate[0], _ZIGZAG[0], atol=1e-9)
                np.testing.assert_allclose(out.outputTranslate[1], _ZIGZAG[-1], atol=1e-9)

    def test_samples_are_spread_by_arc_length(self):
        n      = 4001
        out    = run(_points(_ZIGZAG), samples=np.linspace(0.0, 1.0, n))
        chords = np.linalg.norm(np.diff(out.outputTranslate, axis=0), axis=1)
        self.assertAlmostEqual(chords.sum() / out.currentLength, 1.0, delta=1e-6)
        self.assertLess((chords.max() - chords.min()) / chords.mean(), 1e-5)

    def test_closed_curve_registers_on_control_0(self):
        P = np.asarray(_ZIGZAG)
        want = {1: P[0],
                2: (P[4] + 6.0 * P[0] + P[1]) / 8.0,
                3: (P[4] + 4.0 * P[0] + P[1]) / 6.0}
        for d, w in want.items():
            out = run(_points(_ZIGZAG), samples=[0.0, 1.0], degree=d, periodic=True)
            with self.subTest(degree=d):
                np.testing.assert_allclose(out.outputTranslate[0], w, atol=1e-9)
                np.testing.assert_allclose(out.outputTranslate[1], w, atol=1e-9)

    def test_closed_curve_wraps_for_any_shift(self):
        us   = np.linspace(0.0, 1.0, 9)
        base = run(_points(_PENTA), samples=us, periodic=True, shift=0.75)
        for shift in (-0.25, 1.75, -1.25):
            out = run(_points(_PENTA), samples=us, periodic=True, shift=shift)
            with self.subTest(shift=shift):
                np.testing.assert_allclose(out.outputTranslate, base.outputTranslate, atol=1e-9)
                np.testing.assert_allclose(out.outputRotate, base.outputRotate, atol=1e-9)

    def test_translate_projection_past_the_open_ends(self):
        base    = run(_points(_ZIGZAG), samples=[1.0])
        clamped = run(_points(_ZIGZAG), samples=[0.9, 1.0], shift=0.2, translateProjection=0)
        infin   = run(_points(_ZIGZAG), samples=[0.9, 1.0], shift=0.2, translateProjection=1)
        for i in (0, 1):
            np.testing.assert_allclose(clamped.outputTranslate[i], _ZIGZAG[-1], atol=1e-9)
        end  = np.asarray(_ZIGZAG[-1])
        tail = end - np.asarray(_ZIGZAG[-2])
        tail = tail / np.linalg.norm(tail)
        for i, over in ((0, 0.1), (1, 0.2)):
            np.testing.assert_allclose(infin.outputTranslate[i],
                                       end + tail * over * base.currentLength, atol=1e-9)

    def test_degree_is_held_below_the_control_count(self):
        pts = _ZIGZAG[:3]
        a   = run(_points(pts), samples=np.linspace(0.0, 1.0, 7), degree=7)
        b   = run(_points(pts), samples=np.linspace(0.0, 1.0, 7), degree=2)
        np.testing.assert_allclose(a.outputTranslate, b.outputTranslate, atol=1e-12)

    def test_one_control_holds_every_rider(self):
        out = run(_points(_ZIGZAG[1:2]), samples=[0.0, 0.5, 1.0])
        np.testing.assert_allclose(out.outputTranslate, [_ZIGZAG[1]] * 3, atol=1e-12)


class TestFrames(unittest.TestCase):

    def test_frames_are_right_handed_and_aim_along_the_curve(self):
        us = np.linspace(0.02, 0.98, 13)
        h  = 1e-6
        for aim, up in ((0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)):
            out = run(_points(_ZIGZAG), samples=us, curveAimAxis=aim, curveUpAxis=up)
            fwd = run(_points(_ZIGZAG), samples=us + h).outputTranslate \
                - run(_points(_ZIGZAG), samples=us - h).outputTranslate
            fwd = fwd / np.linalg.norm(fwd, axis=1)[:, None]
            for i in range(len(us)):
                R = rows(out.outputRotate[i])
                with self.subTest(aim=aim, up=up, sample=i):
                    self.assertAlmostEqual(np.linalg.det(R), 1.0, delta=1e-9)
                    self.assertGreater(float(R[aim] @ fwd[i]), 1.0 - 1e-6)

    def test_invert_flags_flip_their_rows(self):
        us   = [0.3, 0.7]
        base = run(_points(_ZIGZAG), samples=us, curveAimAxis=1, curveUpAxis=2)
        inva = run(_points(_ZIGZAG), samples=us, curveAimAxis=1, curveUpAxis=2,
                   curveInvertAimAxis=1)
        invu = run(_points(_ZIGZAG), samples=us, curveAimAxis=1, curveUpAxis=2,
                   curveInvertUpAxis=1)
        for i in range(2):
            b = rows(base.outputRotate[i])
            np.testing.assert_allclose(rows(inva.outputRotate[i])[1], -b[1], atol=1e-9)
            np.testing.assert_allclose(rows(invu.outputRotate[i])[2], -b[2], atol=1e-9)
            self.assertAlmostEqual(np.linalg.det(rows(inva.outputRotate[i])), 1.0, delta=1e-9)
            self.assertAlmostEqual(np.linalg.det(rows(invu.outputRotate[i])), 1.0, delta=1e-9)


def _twist_line():
    """Five controls up Y; control 3 turned 90 degrees about Y (its Z row +X)."""
    ctrls    = [_matrix((0.0, 3.0 * k, 0.0)) for k in range(5)]
    ctrls[3] = _matrix((0.0, 9.0, 0.0), rows=[[0, 0, -1], [0, 1, 0], [1, 0, 0]])
    return ctrls


def _twist_deg(out):
    return [math.degrees(math.atan2(rows(e)[2][0], rows(e)[2][2])) for e in out.outputRotate]


class TestDrivers(unittest.TestCase):

    def test_none_gives_identity_rotation_and_unit_scale(self):
        ctrls = [_matrix(p, scale=(2.0, 3.0, 4.0)) for p in _ZIGZAG]
        out   = run(ctrls, samples=[0.0, 0.5, 1.0], rotateMode=2, scaleMode=2)
        np.testing.assert_array_equal(out.outputRotate, np.zeros((3, 3)))
        np.testing.assert_array_equal(out.outputScale, np.ones((3, 3)))

    def test_matrix_mode_takes_the_outside_matrix(self):
        outside = _matrix((5.0, 5.0, 5.0), rows=[[0, 0, -1], [0, 1, 0], [1, 0, 0]],
                          scale=(2.0, 3.0, 4.0))
        out = run(_twist_line(), samples=[0.1, 0.5, 0.9], curveAimAxis=1, curveUpAxis=2,
                  rotateMode=3, rotateMatrix=outside, scaleMode=3, scaleMatrix=outside)
        for e in out.outputRotate:
            np.testing.assert_allclose(rows(e)[2], [1.0, 0.0, 0.0], atol=1e-9)
        np.testing.assert_allclose(out.outputScale, [[2.0, 3.0, 4.0]] * 3, atol=1e-12)

    def test_one_flagged_control_drives_every_rider(self):
        ctrls    = _points(_ZIGZAG)
        ctrls[2] = _matrix(_ZIGZAG[2], scale=(1.5, 0.5, 2.0))
        out      = run(ctrls, samples=[0.0, 0.5, 1.0], scaleMode=1, scaleFlags=[0, 0, 1, 0, 0])
        np.testing.assert_allclose(out.outputScale, [[1.5, 0.5, 2.0]] * 3, atol=1e-12)

    def test_rotate_projections_past_the_end_drivers(self):
        """Drivers on controls 1 (0 deg) and 3 (90 deg), keys 0.25 / 0.75:
        Clamped holds them, Frozen and Infinite carry on past them, and Frozen
        blends by the rest u, so shift leaves it alone."""
        common = dict(samples=[0.1, 0.5, 0.9], curveAimAxis=1, curveUpAxis=2, rotateMode=1,
                      rotateFlags=[0, 1, 0, 1, 0], restKeys=[0.0, 0.25, 0.5, 0.75, 1.0],
                      defaultLength=12.0)
        clamped = _twist_deg(run(_twist_line(), rotateProjection=2, **common))
        frozen  = _twist_deg(run(_twist_line(), rotateProjection=0, **common))
        shifted = _twist_deg(run(_twist_line(), rotateProjection=0, shift=0.05, **common))
        infin   = _twist_deg(run(_twist_line(), rotateProjection=1, shift=0.05, **common))
        np.testing.assert_allclose(clamped, [0.0, 45.0, 90.0], atol=1e-6)
        np.testing.assert_allclose(frozen, [-27.0, 45.0, 117.0], atol=1e-6)
        np.testing.assert_allclose(shifted, frozen, atol=1e-9)
        np.testing.assert_allclose(infin, [-18.0, 54.0, 126.0], atol=1e-6)

    def test_closed_blend_runs_across_the_seam(self):
        """A closed pentagon, scale drivers on controls 1 (x1) and 3 (x3): keys
        0.2 and 0.6, so sample 0 blends from control 3 (one turn back, key -0.4)
        to control 1, two thirds of the way. The same flags on an open curve,
        Clamped, hold control 1 at u=0."""
        ctrls    = _points(_PENTA)
        ctrls[3] = _matrix(_PENTA[3], scale=(3.0, 3.0, 3.0))
        common = dict(samples=[0.0, 0.4, 0.9], scaleMode=1, scaleFlags=[0, 1, 0, 1, 0],
                        scaleMethod=1, scaleProjection=1)
        closed = run(ctrls, periodic=True, **common)
        np.testing.assert_allclose(closed.outputScale[:, 0], [3.0 - 2.0 * 2.0 / 3.0, 2.0, 2.0],
                                   atol=1e-9)
        np.testing.assert_allclose(closed.controlKeys, [0.0, 0.2, 0.4, 0.6, 0.8], atol=1e-12)
        opened = run(ctrls, **dict(common, scaleProjection=2))
        self.assertAlmostEqual(float(opened.outputScale[0, 0]), 1.0, delta=1e-12)


class TestWeights(unittest.TestCase):

    def _check(self, **inputs):
        P   = np.asarray(_ZIGZAG)
        out = run(_points(_ZIGZAG), computeWeights=True, **inputs)
        W   = np.asarray(out.outputWeights).reshape(-1, 5)
        np.testing.assert_allclose(W @ P, out.outputTranslate, atol=1e-9)
        np.testing.assert_allclose(W.sum(axis=1), 1.0, atol=1e-12)

    def test_weights_reproduce_the_riders(self):
        us = np.linspace(0.0, 1.0, 11)
        for label, inputs in (("open d3", dict(samples=us)),
                              ("open d2", dict(samples=us, degree=2)),
                              ("closed d3", dict(samples=us, periodic=True)),
                              ("closed d2", dict(samples=us, periodic=True, degree=2)),
                              ("open past the ends", dict(samples=us, shift=0.3)),
                              ("open before the start", dict(samples=us, shift=-0.3))):
            with self.subTest(label):
                self._check(**inputs)

    def test_weights_only_on_request(self):
        out = run(_points(_ZIGZAG), samples=[0.5])
        self.assertFalse(hasattr(out, "outputWeights"))


if __name__ == "__main__":
    unittest.main()
