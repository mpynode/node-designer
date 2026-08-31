"""Native codegen for the typed-dataclass geo channels (Phase 2).

Locks the native side of the typed geometry output work: a compute that assigns
``self.outMesh = Mesh(...)`` / ``NurbsCurve(...)`` / ``NurbsSurface(...)`` with
the new channels (per-vertex + indexed normals/colors, periodic curve/surface)

  * lowers DETERMINISTICALLY -- no AI-porter PORT region (the HARD RULE), and
  * emits the matching ``MFn*`` marshalling (setVertex*/setFaceVertex* normals
    and colors; ``kPeriodic`` form) guarded by the fail-soft topology check that
    mirrors ``geometry.build_mesh_data`` (so bad buffers ship an EMPTY mesh, not
    an out-of-bounds crash), and
  * COMPILES clean against the running mayapy's Maya devkit headers.

Structural assertions need no compiler; the compile test SKIPs (never fails)
without a C++ compiler or devkit, so the suite stays green off the build host.
Bit-exact interp-vs-compiled parity for these channels is covered by the compile
controller's parity sweep + the ``nd_lower`` buffer-fill fixtures.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_MESH_PV = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import Mesh\n"
    "P = np.array([[0.0,0.0,0.0],[1.0,0.0,0.0],[1.0,1.0,0.0],[0.0,1.0,0.0]], "
    "dtype=np.float64) * (1.0 + 0.1 * self.scale)\n"
    "C = np.full(1, 4, dtype=np.int32)\n"
    "I = np.array([0,1,2,3], dtype=np.int32)\n"
    "N = np.array([[0.0,0.0,1.0],[0.0,0.0,1.0],[0.0,0.0,1.0],[0.0,0.0,1.0]], "
    "dtype=np.float64)\n"
    "COL = np.array([[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0],[1.0,1.0,0.0]], "
    "dtype=np.float64)\n"
    "self.outMesh = Mesh(points=P, counts=C, indices=I, normals=N, colors=COL)"
)
_MESH_IDX = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import Mesh\n"
    "P = np.array([[0.0,0.0,0.0],[1.0,0.0,0.0],[1.0,1.0,0.0],[0.0,1.0,0.0]], "
    "dtype=np.float64) * (1.0 + 0.1 * self.scale)\n"
    "C = np.full(1, 4, dtype=np.int32)\n"
    "I = np.array([0,1,2,3], dtype=np.int32)\n"
    "Ndir = np.array([[0.0,0.0,1.0],[1.0,0.0,0.0]], dtype=np.float64)\n"
    "NI = np.array([0,0,1,1], dtype=np.int32)\n"
    "PAL = np.array([[1.0,0.0,0.0],[0.0,1.0,0.0]], dtype=np.float64)\n"
    "CI = np.array([0,1,0,1], dtype=np.int32)\n"
    "self.outMesh = Mesh(points=P, counts=C, indices=I, normals=Ndir, "
    "normal_indices=NI, colors=PAL, color_indices=CI)"
)
_CURVE_PER = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import NurbsCurve\n"
    "cvs = np.array([[1.0,0.0,0.0],[0.7,0.7,0.0],[0.0,1.0,0.0],[-0.7,0.7,0.0],"
    "[-1.0,0.0,0.0],[-0.7,-0.7,0.0],[0.0,-1.0,0.0],[0.7,-0.7,0.0],"
    "[1.0,0.0,0.0],[0.7,0.7,0.0],[0.0,1.0,0.0]], dtype=np.float64) "
    "* (1.0 + 0.1 * self.scale)\n"
    "self.outCurve = NurbsCurve(points=cvs, degree=3, periodic=True)"
)
_SURF_PER = (
    "import numpy as np\n"
    "from mpynode._api2.geometry import NurbsSurface\n"
    "rx = np.array([1.0,0.7,0.0,-0.7,-1.0,-0.7,0.0,0.7,1.0,0.7,0.0], "
    "dtype=np.float64)\n"
    "ry = np.array([0.0,0.7,1.0,0.7,0.0,-0.7,-1.0,-0.7,0.0,0.7,1.0], "
    "dtype=np.float64)\n"
    "heights = np.array([0.0,1.0,2.0,3.0], dtype=np.float64)\n"
    "ones_v = np.ones(4, dtype=np.float64)\n"
    "ones_u = np.ones(11, dtype=np.float64)\n"
    "X = (rx[:, None] * ones_v[None, :]).reshape(-1)\n"
    "Z = (ry[:, None] * ones_v[None, :]).reshape(-1)\n"
    "Y = (ones_u[:, None] * heights[None, :]).reshape(-1)\n"
    "grid = np.column_stack([X, Y, Z]) * (1.0 + 0.1 * self.scale)\n"
    "self.outSurface = NurbsSurface(points=grid, num_u=11, num_v=4, "
    "degree_u=3, degree_v=3, periodic_u=True, periodic_v=False)"
)


def _spec_for(mpy_type, compute):
    """Build a live node with a single ``scale`` input + the given compute, and
    extract a production porter spec from it."""
    import maya.cmds as mc
    import mpynode
    from mpynode.native.spec import spec_extractor

    mc.file(new=True, force=True)
    n = mc.createNode(mpy_type)
    w = mpynode.wrap_node(n)
    w.add_input_attr("scale", "double")
    w.set_compute_expression(compute)
    return spec_extractor.extract_spec(n)


def _running_maya_root():
    import sys
    from mpynode.native.toolchain import toolchain

    seeds = [os.environ.get("MAYA_LOCATION") or "",
             os.path.dirname(os.path.abspath(sys.executable))]
    for seed in seeds:
        cur = seed
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(toolchain.maya_include_dir(cur),
                                          "maya")):
                return cur
            cur = os.path.dirname(cur)
    return None


def _gen(mpy_type, compute):
    from mpynode.native import compiler as codegen

    return codegen.generate_cpp(_spec_for(mpy_type, compute), for_port=True)


class TestGeoChannelsLowerPureCpp(unittest.TestCase):
    """Structural (no compiler): the channel computes lower with no PORT region
    and emit the expected marshalling + fail-soft guard."""

    def _assert_no_port(self, cpp):
        from mpynode.native import compiler as codegen
        self.assertNotIn(codegen.PORT_BEGIN, cpp,
                         "geo channel compute must lower to pure C++ (no PORT)")

    def test_mesh_per_vertex_normals_colors(self):
        cpp = _gen("mPyMesh", _MESH_PV)
        self._assert_no_port(cpp)
        self.assertIn("setVertexNormals", cpp)
        self.assertIn("setVertexColors", cpp)
        # fail-soft topology guard (mirrors geometry.build_mesh_data).
        self.assertIn("_topoOK", cpp)

    def test_mesh_indexed_normals_colors(self):
        cpp = _gen("mPyMesh", _MESH_IDX)
        self._assert_no_port(cpp)
        self.assertIn("setFaceVertexNormals", cpp)
        self.assertIn("setFaceVertexColors", cpp)
        self.assertIn("_topoOK", cpp)

    def test_curve_periodic(self):
        cpp = _gen("mPyNurbsCurve", _CURVE_PER)
        self._assert_no_port(cpp)
        self.assertIn("kPeriodic", cpp)

    def test_surface_periodic(self):
        cpp = _gen("mPyNurbsSurface", _SURF_PER)
        self._assert_no_port(cpp)
        self.assertIn("kPeriodic", cpp)


class TestGeoChannelsCompileNative(unittest.TestCase):
    """The generated translation unit compiles against the running mayapy's
    Maya devkit. SKIP (not fail) without a compiler/devkit."""

    def _compile(self, mpy_type, compute, tag):
        from mpynode.native.toolchain import toolchain

        cxx = shutil.which("clang++") or shutil.which("g++")
        if not cxx:
            self.skipTest("no C++ compiler on PATH")
        maya = _running_maya_root()
        if not maya:
            self.skipTest("no Maya devkit headers for the running mayapy")

        cpp = _gen(mpy_type, compute)
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

    def test_mesh_pv_compiles(self):
        self._compile("mPyMesh", _MESH_PV, "meshPV")

    def test_mesh_idx_compiles(self):
        self._compile("mPyMesh", _MESH_IDX, "meshIdx")

    def test_curve_periodic_compiles(self):
        self._compile("mPyNurbsCurve", _CURVE_PER, "curvePer")

    def test_surface_periodic_compiles(self):
        self._compile("mPyNurbsSurface", _SURF_PER, "surfPer")


if __name__ == "__main__":
    unittest.main()
