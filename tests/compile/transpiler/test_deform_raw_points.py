"""Codegen rule 1: a LOWERED deform harvests and commits positions through the
output mesh's raw float store, not an MPointArray round trip.

MItGeometry offers only MPointArray (double, 4-wide) for bulk access, so the
scaffold's ``allPositions`` / ``setAllPositions`` cost a 5.1 MB allocation plus
a float->double widen and a double->float narrow on a 160k-vertex mesh --
measured 535 us of an 890 us deform (sineRipple ledger). Eight of the 50
accepted optimizer rounds in the shipped ledgers removed exactly that by hand.
The emitter now does it for every lowered deform, gated on a MESH with full
membership, with the MPointArray path kept as the fallback and untouched for the
AI-port path (whose contract is ``pts``).

The write side was measured, not assumed (sineRipple, 159,602 vertices, same
scene, outputs identical): MPointArray round trip 23.32 ms; raw read +
MFnMesh::setPoints 23.21; raw read + setAllPositions 24.26; raw read + writing
the mesh's own store + updateSurface 20.88. Hence the in-place write.
"""

from __future__ import annotations

import unittest

from mpynode.native import compiler as codegen


def _spec(compute, base="MPxDeformerNode", inputs=None):
    return {
        "suggested": {"node_type_name": "rawPtsTest", "class_name": "RawPtsTest",
                      "type_id": "0x000701a5", "mpx_base": base},
        "mpy_type": "mPyDeformer" if base == "MPxDeformerNode" else "mPySkinCluster",
        "compute": compute,
        "init": "",
        "inputs": dict(inputs or {}),
        "outputs": {},
        "portability": {"portable": True, "blockers": [], "warnings": []},
    }


_LOWERS = ("mesh = self.outputGeometry[0]\n"
           "rest = mesh.getPoints()\n"
           "mesh.setPoints(rest * (1.0 + self.envelope))\n")
# getPoints with no setPoints: nd_lower rejects the idiom -> the AI-port path.
_PORTS = ("mesh = self.outputGeometry[0]\n"
          "rest = mesh.getPoints()\n")


class TestLoweredDeformUsesRawPoints(unittest.TestCase):
    def setUp(self):
        self.cpp = codegen.generate_cpp(_spec(_LOWERS), for_port=True)
        self.assertIn("lowered deform (no port)", self.cpp)   # the premise

    def test_harvest_probes_the_output_mesh_raw_store(self):
        c = self.cpp
        self.assertIn("MPxGeometryFilter::outputGeom", c)
        self.assertIn("_ofn.getRawPoints(&_hs)", c)
        # full membership only: iterator index i == vertex i
        self.assertIn("(unsigned int)_nv == iter.count()", c)

    def test_the_mpointarray_path_is_the_fallback(self):
        c = self.cpp
        self.assertIn("if (!_rawIn) { iter.allPositions(pts); n = pts.length(); }", c)
        # the harvest comes before the lowered body, the commit after it
        self.assertLess(c.index("_rawIn = _rp"), c.index("lowered deform (no port)"))
        self.assertLess(c.index("lowered deform (no port)"),
                        c.index("MFnMesh(_outMeshObj).updateSurface();"))

    def test_materialise_widens_the_raw_floats(self):
        c = self.cpp
        self.assertIn("_tmp.push_back((double)_rawIn[3 * _i]);", c)
        self.assertIn("_tmp.push_back(pts[_i].x);", c)          # fallback kept

    def test_writeback_narrows_into_the_mesh_store(self):
        c = self.cpp
        self.assertIn("float* _rawOut = const_cast<float*>(_rawIn);", c)
        self.assertIn("_rawOut[3 * _i]     = (float)(*_o.data)[_i*3+0];", c)
        # only min(M, n) slots are written; the rest already hold their value
        import re
        self.assertTrue(re.search(r"_i < _lim; \+\+_i\) \{\s*_rawOut\[3 \* _i\]", c))
        self.assertIn("pts[_i] = MPoint(", c)                    # fallback kept

    def test_commit_is_updatesurface_or_setallpositions(self):
        c = self.cpp
        self.assertIn("MFnMesh(_outMeshObj).updateSurface();", c)
        self.assertIn("iter.setAllPositions(pts);", c)
        self.assertEqual(c.count("iter.setAllPositions(pts);"), 1)
        self.assertNotIn("MFloatPointArray", c)      # no intermediate array

    def test_no_new_includes(self):
        # MFnMesh.h is already in the deformer set; nothing else is needed, so an
        # AI-ported deformer's frag (which shares the include list) cannot move.
        self.assertNotIn("MFloatPointArray.h", self.cpp)


class TestSkinClusterLowersTheSameWay(unittest.TestCase):
    def test_skin_deform_takes_the_raw_path(self):
        from mpynode._defaults import skin_cluster_defaults as scd
        spec = _spec(scd.DEFAULT_COMPUTE_SOURCE, base="MPxSkinCluster")
        spec["init"] = scd.DEFAULT_INIT_SOURCE
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("lowered deform (no port)", cpp)
        self.assertIn("_ofn.getRawPoints(&_hs)", cpp)
        self.assertIn("MFnMesh(_outMeshObj).updateSurface();", cpp)


class TestPortPathIsUntouched(unittest.TestCase):
    """The AI porter's contract is ``pts``: an MPointArray of every point,
    mutated in place. It keeps the unconditional harvest and commit."""

    def test_port_path_keeps_the_mpointarray_contract(self):
        cpp = codegen.generate_cpp(_spec(_PORTS), for_port=True)
        self.assertNotIn("lowered deform (no port)", cpp)
        self.assertIn("    MPointArray pts;\n    iter.allPositions(pts);\n"
                      "    const unsigned int n = pts.length();", cpp)
        self.assertNotIn("_rawIn", cpp)
        self.assertNotIn("updateSurface", cpp)
        self.assertIn("\n    iter.setAllPositions(pts);\n    return MS::kSuccess;", cpp)


if __name__ == "__main__":
    unittest.main()
