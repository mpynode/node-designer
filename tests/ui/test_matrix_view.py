"""Enriched MatrixView surface (Point 2).

MatrixView is the kMatrix return type. It now wraps Maya API 2.0 internally
and exposes the full MMatrix + MTransformationMatrix method surface. Every
numerical return is a numpy array / numpy scalar; matrix-valued results return
a new MatrixView (chainable); mutators act in place and return self.
"""

from __future__ import annotations

import unittest

import numpy as np
import maya.OpenMaya as om1
import maya.api.OpenMaya as om2

from tests._setup import standalone_init
from mpynode._common.plugs.promoted_types import MatrixView


def setUpModule():
    standalone_init()


def _np_translate(tx, ty, tz):
    m = np.eye(4)
    m[3, 0], m[3, 1], m[3, 2] = tx, ty, tz
    return m


class TestConstruction(unittest.TestCase):
    def test_default_is_identity(self):
        m = MatrixView()
        np.testing.assert_array_almost_equal(m.asNumpy(), np.eye(4))

    def test_from_numpy_4x4(self):
        a = _np_translate(7, 8, 9)
        np.testing.assert_array_almost_equal(MatrixView(a).asNumpy(), a)

    def test_from_16_list(self):
        flat = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 7, 8, 9, 1]
        m    = MatrixView(flat)
        self.assertAlmostEqual(m.getElement(3, 1), 8.0)

    def test_from_api1_mmatrix(self):
        mm = om1.MMatrix()
        om1.MScriptUtil.createMatrixFromList(
            [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 7, 8, 9, 1], mm
        )
        np.testing.assert_array_almost_equal(
            MatrixView(mm).asNumpy(), _np_translate(7, 8, 9)
        )

    def test_from_api2_mmatrix(self):
        mm = om2.MMatrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 7, 8, 9, 1])
        np.testing.assert_array_almost_equal(
            MatrixView(mm).asNumpy(), _np_translate(7, 8, 9)
        )

    def test_from_api2_transformation_matrix(self):
        tm = om2.MTransformationMatrix()
        tm.setTranslation(om2.MVector(7, 8, 9), om2.MSpace.kTransform)
        np.testing.assert_array_almost_equal(
            MatrixView(tm).asNumpy(), _np_translate(7, 8, 9)
        )


class TestRawAccessors(unittest.TestCase):
    def test_asMatrix_is_api2_mmatrix(self):
        m = MatrixView(_np_translate(1, 2, 3))
        self.assertIsInstance(m.asMatrix(), om2.MMatrix)

    def test_asNumpy_shape_dtype(self):
        a = MatrixView().asNumpy()
        self.assertEqual(a.shape, (4, 4))
        self.assertEqual(a.dtype, np.float64)

    def test_asTransformationMatrix_is_api2(self):
        m = MatrixView()
        self.assertIsInstance(m.asTransformationMatrix(), om2.MTransformationMatrix)


class TestMMatrixSurface(unittest.TestCase):
    def test_inverse_returns_matrixview_and_inverts(self):
        m   = MatrixView(_np_translate(10, 20, 30))
        inv = m.inverse()
        self.assertIsInstance(inv, MatrixView)
        np.testing.assert_array_almost_equal(
            inv.translation(), [-10, -20, -30]
        )

    def test_inverse_chains(self):
        m = MatrixView(_np_translate(10, 20, 30))
        np.testing.assert_array_almost_equal(
            m.inverse().inverse().asNumpy(), m.asNumpy()
        )

    def test_transpose(self):
        m = MatrixView(_np_translate(7, 0, 0))
        t = m.transpose()
        self.assertIsInstance(t, MatrixView)
        self.assertAlmostEqual(t.getElement(0, 3), 7.0)

    def test_adjoint_returns_matrixview(self):
        self.assertIsInstance(MatrixView().adjoint(), MatrixView)

    def test_homogenize_returns_matrixview(self):
        self.assertIsInstance(MatrixView().homogenize(), MatrixView)

    def test_det4x4_identity(self):
        d = MatrixView().det4x4()
        self.assertIsInstance(d, np.floating)
        self.assertAlmostEqual(float(d), 1.0)

    def test_det3x3_identity(self):
        d = MatrixView().det3x3()
        self.assertIsInstance(d, np.floating)
        self.assertAlmostEqual(float(d), 1.0)

    def test_getElement_numpy_scalar(self):
        m = MatrixView(_np_translate(7, 8, 9))
        e = m.getElement(3, 1)
        self.assertIsInstance(e, np.floating)
        self.assertAlmostEqual(float(e), 8.0)

    def test_isSingular_false_for_identity(self):
        self.assertIs(MatrixView().isSingular(), False)

    def test_isSingular_true_for_zero(self):
        self.assertIs(MatrixView(np.zeros((4, 4))).isSingular(), True)

    def test_isEquivalent(self):
        a = MatrixView(_np_translate(1, 2, 3))
        self.assertIs(a.isEquivalent(MatrixView(_np_translate(1, 2, 3))), True)
        self.assertIs(a.isEquivalent(MatrixView()), False)
        # Accepts a raw numpy too.
        self.assertIs(a.isEquivalent(_np_translate(1, 2, 3)), True)

    def test_setElement_mutates_and_returns_self(self):
        m   = MatrixView()
        out = m.setElement(3, 0, 5.0)
        self.assertIs(out, m)
        self.assertAlmostEqual(m.getElement(3, 0), 5.0)
        self.assertAlmostEqual(m.translation()[0], 5.0)

    def test_setToIdentity_mutates_and_returns_self(self):
        m   = MatrixView(_np_translate(1, 2, 3))
        out = m.setToIdentity()
        self.assertIs(out, m)
        np.testing.assert_array_almost_equal(m.asNumpy(), np.eye(4))

    def test_setToProduct_mutates_and_returns_self(self):
        m   = MatrixView()
        a   = MatrixView(_np_translate(1, 2, 3))
        b   = MatrixView(_np_translate(4, 5, 6))
        out = m.setToProduct(a, b)
        self.assertIs(out, m)
        np.testing.assert_array_almost_equal(m.translation(), [5, 7, 9])


class TestTransformationSurface(unittest.TestCase):
    def test_translation_numpy(self):
        t = MatrixView(_np_translate(7, 8, 9)).translation()
        self.assertIsInstance(t, np.ndarray)
        self.assertEqual(t.shape, (3,))
        np.testing.assert_array_almost_equal(t, [7, 8, 9])

    def test_setTranslation(self):
        m   = MatrixView()
        out = m.setTranslation([5, 6, 7])
        self.assertIs(out, m)
        np.testing.assert_array_almost_equal(m.translation(), [5, 6, 7])

    def test_rotation_identity_is_zero(self):
        r = MatrixView().rotation()
        self.assertIsInstance(r, np.ndarray)
        self.assertEqual(r.shape, (3,))
        np.testing.assert_array_almost_equal(r, [0, 0, 0])

    def test_scale_numpy(self):
        m = MatrixView(np.diag([2.0, 3.0, 4.0, 1.0]))
        s = m.scale()
        self.assertIsInstance(s, np.ndarray)
        np.testing.assert_array_almost_equal(s, [2, 3, 4])

    def test_setScale(self):
        m   = MatrixView()
        out = m.setScale([2, 3, 4])
        self.assertIs(out, m)
        np.testing.assert_array_almost_equal(m.scale(), [2, 3, 4])

    def test_shear_numpy(self):
        s = MatrixView().shear()
        self.assertIsInstance(s, np.ndarray)
        self.assertEqual(s.shape, (3,))

    def test_rotatePivot_numpy(self):
        p = MatrixView().rotatePivot()
        self.assertIsInstance(p, np.ndarray)
        self.assertEqual(p.shape, (3,))

    def test_as_matrix_family_returns_mmatrix(self):
        m = MatrixView(_np_translate(1, 2, 3))
        self.assertIsInstance(m.asMatrixInverse(), om2.MMatrix)
        self.assertIsInstance(m.asRotateMatrix(),  om2.MMatrix)
        self.assertIsInstance(m.asScaleMatrix(),   om2.MMatrix)


class TestNumpyTransparency(unittest.TestCase):
    def test_matmul_returns_numpy(self):
        a   = MatrixView(_np_translate(1, 2, 3))
        out = a @ np.eye(4)
        self.assertIsInstance(out, np.ndarray)
        np.testing.assert_array_almost_equal(out, a.asNumpy())

    def test_mul_returns_matrixview(self):
        a    = MatrixView(_np_translate(1, 2, 3))
        b    = MatrixView(_np_translate(4, 5, 6))
        prod = a * b
        self.assertIsInstance(prod, MatrixView)
        np.testing.assert_array_almost_equal(prod.translation(), [5, 7, 9])

    def test_pickle_round_trip(self):
        import pickle

        # Re-import MatrixView from the CURRENT sys.modules right before use.
        # maya.standalone + the node-designer2 userSetup bootstrap purge &
        # re-import the ``mpynode`` package repeatedly across a full-discover run
        # (every plugin load / scene op can fire it -- see the
        # "Maya loads STALE mpynode copy" gotcha), so the module-level
        # ``MatrixView`` binding can be a STALE pre-purge class object by the time
        # this test runs. pickle's ``__reduce__`` serializes the class by global
        # lookup and asserts identity against ``sys.modules[...].MatrixView``;
        # binding locally here guarantees ``a``'s class IS that object.
        from mpynode._common.plugs.promoted_types import MatrixView

        a = MatrixView(_np_translate(7, 8, 9))
        b = pickle.loads(pickle.dumps(a))
        self.assertIsInstance(b, MatrixView)
        np.testing.assert_array_almost_equal(b.asNumpy(), a.asNumpy())


if __name__ == "__main__":
    unittest.main()
