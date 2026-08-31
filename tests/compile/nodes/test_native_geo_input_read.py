"""Native codegen for the geometry-INPUT read surface (Phase 6).

A plain node whose compute reads a typed geo INPUT's numpy read surface --
``self.<mesh>.points`` / ``.counts`` / ``.indices`` / ``.normals``, a curve's
``.cvs`` / ``.degree`` / ``.form`` / ``.knots``, a surface's ``.cvs`` /
``.num_u`` / ``.degree_u`` / ``.knots_u`` -- must:

  * lower DETERMINISTICALLY -- no AI-porter PORT region (the HARD RULE): the
    read is materialised in C++ from the input ``MFn*`` with the SAME call the
    interpreted wrapper uses (``getPoints(kObject)`` / ``getVertices`` /
    ``getVertexNormals`` / ``getCVs`` / ``getKnots``...), and
  * COMPILE clean against the running mayapy's Maya devkit, and
  * be BYTE-EXACT interp-vs-compiled (the compile controller's parity sweep,
    driven by ``verify._wire_geo_input`` wiring a real upstream shape into the
    typed geo plug on both sides).

Any geo use OUTSIDE the supported read surface (``.fn`` / ``.component_tags`` /
``.region(...)`` / ``.copy()`` / a bare pass-through / an ARRAY geo input) must
REJECT the whole lowering so the node keeps the existing AI-porter path (zero
regression).

Structural + reject assertions need no compiler; the compile / parity tests SKIP
(never fail) without a C++ compiler or devkit, so the suite stays green off the
build host.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# ---- geo-input read computes (byte-parity fixtures) -----------------------
_MESH_PTS = (
    "p = self.inMesh.points\n"
    "c = p.mean(axis=0)\n"
    "self.cx = float(c[0])\n"
    "self.cy = float(c[1])\n"
    "self.cz = float(c[2])\n"
)
# The point VALUES, not just the vertex COUNT `_MESH_TOPO` pins via `.shape[0]`:
# vertex 1's three components read individually (so a swapped component or a bad
# stride in the C++ ingest shows even on a symmetric cube) plus a whole-array
# magnitude (so a wrong vertex count shows too).
_MESH_PT_VALUES = (
    "p = self.inMesh.points\n"
    "self.px = float(p[1, 0])\n"
    "self.py = float(p[1, 1])\n"
    "self.pz = float(p[1, 2])\n"
    "self.ss = float((p * p).sum())\n"
)
_MESH_TOPO = (
    "self.sc = float(int(self.inMesh.counts.sum()))\n"
    "self.si = float(int(self.inMesh.indices.sum()))\n"
    "self.nv = float(self.inMesh.points.shape[0])\n"
    "n = self.inMesh.normals\n"
    "self.ny = float(n.mean(axis=0)[1])\n"
)
_MESH_ALIAS = (
    "g = self.inMesh\n"
    "self.cx = float(g.points.mean(axis=0)[0])\n"
    "self.nv = float(g.counts.sum())\n"
)
_CURVE = (
    "cv = self.inCrv.cvs\n"
    "self.cx = float(cv.mean(axis=0)[0])\n"
    "self.dg = float(self.inCrv.degree)\n"
    "self.kn = float(self.inCrv.knots.sum())\n"
)
_SURF = (
    "self.nu = float(self.inSrf.num_u)\n"
    "self.du = float(self.inSrf.degree_u)\n"
    "self.ku = float(self.inSrf.knots_u.sum())\n"
    "self.cg = float(self.inSrf.cvs.mean())\n"
)
# `.points` is the UNIFIED coefficient accessor -- it must lower on a surface
# exactly like `.cvs` (both read the (nu,nv,3) CV grid). This locks that parity.
_SURF_POINTS = (
    "g = self.inSrf.points\n"
    "self.nu = float(g.shape[0])\n"          # num_u inferred from the grid shape
    "self.nv = float(g.shape[1])\n"          # num_v inferred from the grid shape
    "self.cg = float(g.mean())\n"
)


def _make_node(name, compute, inputs, outs):
    import maya.cmds as mc
    import mpynode

    mc.file(new=True, force=True)
    n = mc.createNode("mPyNode", name=name)
    w = mpynode.wrap_node(n)
    for nm, t in inputs:
        w.add_input_attr(nm, t)
    for nm, t in outs:
        w.add_output_attr(nm, t)
    w.set_compute_expression(compute)
    return n


def _spec(name, compute, inputs, outs):
    from mpynode.native.spec import spec_extractor

    return spec_extractor.extract_spec(_make_node(name, compute, inputs, outs))


def _gen(name, compute, inputs, outs):
    from mpynode.native import compiler as codegen

    return codegen.generate_cpp(_spec(name, compute, inputs, outs), for_port=True)


def _lowers(name, compute, inputs, outs):
    """True iff the compute lowered deterministically (no PORT region)."""
    from mpynode.native import compiler as codegen

    return codegen.PORT_BEGIN not in _gen(name, compute, inputs, outs)


def _running_maya_root():
    import sys
    from mpynode.native.toolchain import toolchain

    seeds = [os.environ.get("MAYA_LOCATION") or "",
             os.path.dirname(os.path.abspath(sys.executable))]
    for seed in seeds:
        cur = seed
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(toolchain.maya_include_dir(cur), "maya")):
                return cur
            cur = os.path.dirname(cur)
    return None


_MESH_IN = [("inMesh", "mesh")]
_CRV_IN = [("inCrv", "nurbsCurve")]
_SRF_IN = [("inSrf", "nurbsSurface")]
_XYZ = [("cx", "double"), ("cy", "double"), ("cz", "double")]


class TestGeoInputLowerPureCpp(unittest.TestCase):
    """The geo read surface lowers with NO PORT region and emits the expected
    MFn read call."""

    def _no_port(self, cpp):
        from mpynode.native import compiler as codegen
        self.assertNotIn(codegen.PORT_BEGIN, cpp,
                         "geo-input read must lower to pure C++ (no PORT)")

    def test_mesh_points(self):
        # BEHAVIOUR, not spelling: `.points` must ingest the mesh's OBJECT-space
        # vertex positions. Object space is exactly what makes the raw float3
        # array and the MPointArray read bit-identical, so EITHER MFnMesh call
        # is correct -- what must never change is the SPACE (any other one
        # applies a matrix in double). The ingested VALUES are pinned by
        # TestGeoInputParity.test_mesh_point_values_parity.
        cpp = _gen("gMeshPts", _MESH_PTS, _MESH_IN, _XYZ)
        self._no_port(cpp)
        self.assertTrue("getRawPoints(" in cpp
                        or "getPoints(_ga, MSpace::kObject)" in cpp,
                        "mesh .points must ingest object-space vertex positions")
        self.assertEqual(
            sorted(set(re.findall(r"MSpace::\w+", cpp)) - {"MSpace::kObject"}),
            [], "mesh ingest must stay OBJECT space (the bit-safe one)")

    def test_mesh_topo_and_normals(self):
        cpp = _gen("gMeshTopo", _MESH_TOPO, _MESH_IN,
                   [("sc", "double"), ("si", "double"), ("nv", "double"),
                    ("ny", "double")])
        self._no_port(cpp)
        self.assertIn("getVertices(_gc, _gv)", cpp)
        self.assertIn("getVertexNormals(false, _ga, MSpace::kObject)", cpp)

    def test_mesh_alias(self):
        # `g = self.inMesh; g.points` -- the single-assignment alias also lowers.
        self.assertTrue(_lowers("gMeshAlias", _MESH_ALIAS, _MESH_IN,
                                [("cx", "double"), ("nv", "double")]))

    def test_curve(self):
        cpp = _gen("gCurve", _CURVE, _CRV_IN,
                   [("cx", "double"), ("dg", "double"), ("kn", "double")])
        self._no_port(cpp)
        self.assertIn("getCVs(_ga, MSpace::kObject)", cpp)
        self.assertIn("getKnots(_gk)", cpp)

    def test_surface(self):
        cpp = _gen("gSurf", _SURF, _SRF_IN,
                   [("nu", "double"), ("du", "double"), ("ku", "double"),
                    ("cg", "double")])
        self._no_port(cpp)
        self.assertIn("numCVsInU()", cpp)
        self.assertIn("getKnotsInU(_gk)", cpp)
        self.assertIn("getCVs(_ga, MSpace::kObject)", cpp)

    def test_surface_points_is_unified_alias_of_cvs(self):
        # `.points` on a surface must lower identically to `.cvs` (the (nu,nv,3)
        # grid) -- the unified coefficient accessor, first-class across all three.
        cpp = _gen("gSurfPts", _SURF_POINTS, _SRF_IN,
                   [("nu", "double"), ("nv", "double"), ("cg", "double")])
        self._no_port(cpp)
        self.assertIn("getCVs(_ga, MSpace::kObject)", cpp)


class TestGeoInputRejectsToPorter(unittest.TestCase):
    """A geo use outside the supported read surface rejects the deterministic
    lowering so the node keeps the AI-porter path (PORT region present)."""

    def _rejects(self, name, compute, inputs=_MESH_IN, outs=(("cx", "double"),)):
        self.assertFalse(_lowers(name, compute, inputs, list(outs)),
                         "unsupported geo use must NOT lower (keeps porter path)")

    def test_fn_escape_hatch_rejects(self):
        self._rejects("rFn", "self.cx = float(self.inMesh.fn.numVertices)\n")

    def test_component_tags_rejects(self):
        self._rejects("rTags",
                      "self.cx = float(len(self.inMesh.component_tags))\n")

    def test_copy_rejects(self):
        self._rejects("rCopy",
                      "m = self.inMesh.copy()\nself.cx = float(m.points.mean())\n")

    def test_bare_passthrough_rejects(self):
        self._rejects(
            "rBare",
            "import numpy as np\n"
            "self.cx = float(np.asarray(self.inMesh.getPoints()).mean())\n")

    def test_array_geo_input_rejects(self):
        # an ARRAY geo input is not a single-geo read -> falls back to the porter.
        self._rejects("rArr", "self.cx = float(len(self.inMesh))\n",
                      inputs=[("inMesh", "mesh")])


class TestGeoInputCompileNative(unittest.TestCase):
    """The generated TU compiles against the running mayapy's Maya devkit. SKIP
    (not fail) without a compiler/devkit."""

    def _compile(self, name, compute, inputs, outs, tag):
        from mpynode.native.toolchain import toolchain

        cxx = shutil.which("clang++") or shutil.which("g++")
        if not cxx:
            self.skipTest("no C++ compiler on PATH")
        maya = _running_maya_root()
        if not maya:
            self.skipTest("no Maya devkit headers for the running mayapy")
        cpp = _gen(name, compute, inputs, outs)
        inc = toolchain.maya_include_dir(maya)
        native_dir = os.path.join(os.environ["MPYNODE_ROOT"], "scripts",
                                  "mpynode", "native")
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, tag + ".cpp")
            with open(src, "w") as fh:
                fh.write(cpp)
            obj = os.path.join(d, tag + ".o")
            cmd = [cxx, "-std=c++17", "-O2", "-c", src, "-o", obj,
                   "-I", inc, "-I", native_dir]
            md = toolchain.maya_define()
            if md:
                cmd += ["-D" + md]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             "%s native compile failed:\n%s"
                             % (tag, proc.stderr[-4000:]))
            self.assertTrue(os.path.isfile(obj) and os.path.getsize(obj) > 0)

    def test_mesh_compiles(self):
        self._compile("gMeshPts", _MESH_TOPO, _MESH_IN,
                      [("sc", "double"), ("si", "double"), ("nv", "double"),
                       ("ny", "double")], "meshRead")

    def test_curve_compiles(self):
        self._compile("gCurve", _CURVE, _CRV_IN,
                      [("cx", "double"), ("dg", "double"), ("kn", "double")],
                      "curveRead")

    def test_surface_compiles(self):
        self._compile("gSurf", _SURF, _SRF_IN,
                      [("nu", "double"), ("du", "double"), ("ku", "double"),
                       ("cg", "double")], "surfRead")


class TestGeoInputParity(unittest.TestCase):
    """Byte-exact interp-vs-compiled parity for the geo read surface (the compile
    controller build + verify._verify_one, which wires a real upstream shape into
    the typed geo plug on both sides). SKIP without a compiler/devkit."""

    def _parity(self, name, compute, inputs, outs):
        import maya.cmds as mc
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import verify

        if not (shutil.which("clang++") or shutil.which("g++")):
            self.skipTest("no C++ compiler on PATH")
        if not _running_maya_root():
            self.skipTest("no Maya devkit headers for the running mayapy")
        spec = _spec(name, compute, inputs, outs)
        d = tempfile.mkdtemp()
        res = cc.compile_plugin([spec], name + "P", d, strict=True,
                                verify=False, reuse_cache=False)
        self.assertTrue(res["ok"], "build failed: %s" % res.get("errors"))
        r = verify._verify_one(mc, res["bundle_path"], spec)
        self.assertTrue(r["ran"], "parity did not run: %s" % r.get("reason"))
        self.assertTrue(r["pass"],
                        "%s parity FAILED maxerr=%s reason=%s"
                        % (name, r.get("maxerr"), r.get("reason")))

    def test_mesh_parity(self):
        self._parity("gMeshPar", _MESH_TOPO, _MESH_IN,
                     [("sc", "double"), ("si", "double"), ("nv", "double"),
                      ("ny", "double")])

    def test_mesh_point_values_parity(self):
        # `_MESH_TOPO` only pins `points.shape[0]`. This pins the object-space
        # POSITIONS the ingest produces -- the behaviour any change to how the
        # mesh point array is read (MPointArray vs the raw float3 array) must
        # preserve exactly.
        self._parity("gMeshPtValPar", _MESH_PT_VALUES, _MESH_IN,
                     [("px", "double"), ("py", "double"), ("pz", "double"),
                      ("ss", "double")])

    def test_curve_parity(self):
        self._parity("gCurvePar", _CURVE, _CRV_IN,
                     [("cx", "double"), ("dg", "double"), ("kn", "double")])

    def test_surface_parity(self):
        self._parity("gSurfPar", _SURF, _SRF_IN,
                     [("nu", "double"), ("du", "double"), ("ku", "double"),
                      ("cg", "double")])

    def test_surface_points_parity(self):
        # `.points` (unified name) is byte-exact with the interpreted grid read.
        self._parity("gSurfPtsPar", _SURF_POINTS, _SRF_IN,
                     [("nu", "double"), ("nv", "double"), ("cg", "double")])


if __name__ == "__main__":
    unittest.main()
