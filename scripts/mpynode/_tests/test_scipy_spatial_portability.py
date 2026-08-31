"""scipy.spatial is not wholesale unported -- cKDTree lowers to nd::KDTree.

The gate used to flag the whole submodule as "no auto-port path yet", so a
closest-point node that compiles to a real native kernel was told it had no
port path. These pin both directions: the lowered surface must be silent, the
genuinely-missing constructs must still say so, and a template's OWN helper
named `procrustes` must not be mistaken for scipy's.
"""

from __future__ import annotations

import unittest

from mpynode.native.spec import spec_extractor

_MSG = "scipy.spatial construct with no auto-port path yet"


def _unported(src):
    return spec_extractor.assess_portability(src, "", {}, {}, {}).get(
        "unported") or []


def _flags_spatial(src):
    return any(_MSG in u for u in _unported(src))


class TestLoweredSpatialIsSilent(unittest.TestCase):

    def test_from_import_ckdtree_is_not_flagged(self):
        self.assertFalse(_flags_spatial(
            "from scipy.spatial import cKDTree\n"
            "d, i = cKDTree(p).query(q, k=1)\n"))

    def test_dotted_ckdtree_is_not_flagged(self):
        self.assertFalse(_flags_spatial(
            "import scipy.spatial\n"
            "t = scipy.spatial.cKDTree(p)\n"))

    def test_kdtree_spelling_is_not_flagged(self):
        self.assertFalse(_flags_spatial(
            "from scipy.spatial import KDTree\n"
            "t = KDTree(p)\n"))


class TestGenuineGapsStillWarn(unittest.TestCase):

    def test_delaunay_is_flagged(self):
        self.assertTrue(_flags_spatial(
            "from scipy.spatial import Delaunay\n"
            "t = Delaunay(p)\n"))

    def test_convex_hull_is_flagged(self):
        self.assertTrue(_flags_spatial(
            "import scipy.spatial\n"
            "h = scipy.spatial.ConvexHull(p)\n"))

    def test_distance_submodule_is_flagged(self):
        self.assertTrue(_flags_spatial(
            "from scipy.spatial.distance import cdist\n"
            "d = cdist(a, b)\n"))

    def test_rotation_transform_submodule_is_flagged(self):
        self.assertTrue(_flags_spatial(
            "from scipy.spatial.transform import Rotation\n"
            "r = Rotation.from_quat(q)\n"))

    def test_mixed_import_still_flags_the_unported_name(self):
        """cKDTree alongside Delaunay must still warn -- about Delaunay."""
        self.assertTrue(_flags_spatial(
            "from scipy.spatial import cKDTree, Delaunay\n"))


class TestNoFalsePositiveOnLocalHelpers(unittest.TestCase):

    def test_a_local_procrustes_helper_is_not_scipys(self):
        """templates/MPyConstraint/procrustes_* define their own."""
        self.assertFalse(_flags_spatial(
            "import numpy as np\n"
            "def procrustes(a, b):\n"
            "    return np.dot(a.T, b)\n"
            "r = procrustes(x, y)\n"))

    def test_a_local_distance_matrix_helper_is_not_scipys(self):
        self.assertFalse(_flags_spatial(
            "import numpy as np\n"
            "def distance_matrix(a, b):\n"
            "    return np.abs(a - b)\n"))

    def test_other_heavy_submodules_are_unaffected(self):
        self.assertTrue(any("heavy scipy submodule" in u
                            for u in _unported("import scipy.optimize\n")))


if __name__ == "__main__":
    unittest.main()
