"""Native codegen for the geometry full-matrix (task #83): mesh / nurbsCurve /
nurbsSurface in EVERY compile cell -- Single-in Single-out, Array-in Array-out.

The geo READ surface (Phase 6, single INPUT) is covered by
``test_native_geo_input_read``. This suite covers the three cells that were
previously honest-rejected:

  * single geo OUTPUT: ``self.out = Mesh(points=..., counts=..., indices=...)``
    (resp. NurbsCurve / NurbsSurface) lowers DETERMINISTICALLY (no AI porter):
    the ctor field expressions are transpiled and written into an ``NdMesh`` /
    ``NdCurve`` / ``NdSurface`` value struct, then built with the SAME MFn*
    ``create`` calls the geometry generators use.
  * array (list) geo INPUT: ``std::vector<NdKind> in_<m>`` read element-by-
    element from the multi plug via ``MArrayDataHandle``.
  * array (list) geo OUTPUT whole passthrough: ``self.outList = self.inList``
    -> struct-vector copy, built back per element via ``MArrayDataBuilder``.

Every case must (a) lower with NO PORT region (the HARD RULE: compiled compute is
pure C++), (b) COMPILE against the running mayapy's Maya devkit, and (c) survive
a RUNTIME round-trip -- wire a real upstream shape into the geo input plug(s),
eval the geo output plug(s), read the built geometry back via MFn* and assert
topology + point positions are preserved.

Structural + reject assertions need no compiler; the compile / round-trip tests
SKIP (never fail) without a C++ compiler or devkit, so the suite stays green off
the build host.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# ---- computes: single = ctor off the input read surface; array = passthrough --
_SINGLE = {
    "mesh": "self.aOut = Mesh(points=self.aIn.points, counts=self.aIn.counts, "
            "indices=self.aIn.indices)\n",
    "nurbsCurve": "self.aOut = NurbsCurve(cvs=self.aIn.cvs, "
                  "degree=self.aIn.degree, knots=self.aIn.knots)\n",
    "nurbsSurface": "self.aOut = NurbsSurface(cvs=self.aIn.cvs, "
                    "num_u=self.aIn.num_u, num_v=self.aIn.num_v, "
                    "degree_u=self.aIn.degree_u, degree_v=self.aIn.degree_v, "
                    "knots_u=self.aIn.knots_u, knots_v=self.aIn.knots_v)\n",
}
_ARRAY   = "self.aOut = self.aIn\n"

_KIND_OF = {"mesh": "mesh", "nurbsCurve": "curve", "nurbsSurface": "surface"}
_KINDS   = ("mesh", "nurbsCurve", "nurbsSurface")


def _make_node(name, compute, t, is_array):
    import maya.cmds as mc
    import mpynode

    mc.file(new=True, force=True)
    n = mc.createNode("mPyNode", name=name)
    w = mpynode.wrap_node(n)
    w.add_input_attr("aIn", t, is_array=is_array)
    w.add_output_attr("aOut", t, is_array=is_array)
    w.set_compute_expression(compute)
    return n


def _spec(name, compute, t, is_array):
    from mpynode.native.spec import spec_extractor

    return spec_extractor.extract_spec(_make_node(name, compute, t, is_array))


def _gen(name, compute, t, is_array, for_port=True):
    from mpynode.native import compiler as codegen

    return codegen.generate_cpp(_spec(name, compute, t, is_array),
                                for_port=for_port)


def _lowers(name, compute, t, is_array):
    """True iff the compute lowered deterministically (no PORT region)."""
    from mpynode.native import compiler as codegen

    return codegen.PORT_BEGIN not in _gen(name, compute, t, is_array)


def _compute(t, is_array):
    return _ARRAY if is_array else _SINGLE[t]


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


def _have_toolchain():
    return bool((shutil.which("clang++") or shutil.which("g++"))
                and _running_maya_root())


# --------------------------------------------------------------------------- #
class TestGeoOutputLowerPureCpp(unittest.TestCase):
    """Every geo cell lowers with NO PORT region and pulls in the shared geo
    value model (emit_geo_io) helpers."""

    def _no_port(self, cpp):
        from mpynode.native import compiler as codegen
        self.assertNotIn(codegen.PORT_BEGIN, cpp,
                         "geo output/array must lower to pure C++ (no PORT)")

    def test_single_output_lowers(self):
        for t in _KINDS:
            with self.subTest(kind=t):
                cpp = _gen("gOut_" + t, _SINGLE[t], t, False)
                self._no_port(cpp)
                kc = _KIND_OF[t].capitalize()
                self.assertIn("nd_build_%s" % _KIND_OF[t], cpp)
                self.assertIn("Nd%s out_" % kc, cpp)
                self.assertIn("setMObject", cpp)

    def test_array_input_lowers(self):
        for t in _KINDS:
            with self.subTest(kind=t):
                cpp = _gen("gArr_" + t, _ARRAY, t, True)
                self._no_port(cpp)
                k = _KIND_OF[t]
                # array in -> vector read via nd_read_<kind> in a dense loop
                self.assertIn("nd_read_%s" % k, cpp)
                self.assertIn("std::vector<Nd%s> in_" % k.capitalize(), cpp)
                # array out -> vector build via nd_build_<kind> + MArrayDataBuilder
                self.assertIn("nd_build_%s" % k, cpp)
                self.assertIn("MArrayDataBuilder", cpp)

    def test_geo_io_header_emitted_once(self):
        # the shared value model is emitted with an include guard (single TU).
        cpp = _gen("gGuard", _SINGLE["mesh"], "mesh", False)
        self.assertIn("MPYNODE_GEO_IO_H", cpp)

    def test_mesh_uv_read_and_write_emitted(self):
        # The mesh value struct must round-trip the UV ASSIGNMENT. Reading the
        # uv POINTS alone is not enough: with no uvCounts/uvIds, nd_build_mesh
        # cannot assign them and every mesh through a compiled node comes out
        # unwrapped. Structural guard so a regression shows up with no
        # compiler/devkit (the runtime proof is test_mesh_array).
        cpp = _gen("gUvEmit", _ARRAY, "mesh", True)
        for sym in ("uvCounts", "uvIds", "getAssignedUVs", "setUVs",
                    "assignUVs"):
            self.assertIn(sym, cpp, "mesh TU is missing UV symbol %r" % sym)


class TestGeoOutputRejectsToPorter(unittest.TestCase):
    """A geo-output shape the deterministic path cannot model must NOT lower --
    it keeps the AI-porter path (zero regression)."""

    def _rejects(self, name, compute, t, is_array):
        self.assertFalse(_lowers(name, compute, t, is_array),
                         "unsupported geo output must NOT lower (keeps porter)")

    def test_array_output_non_passthrough_rejects(self):
        # an elementwise list build has no numeric model -> porter.
        self._rejects(
            "rArrBuild",
            "self.aOut = [Mesh(points=m.points, counts=m.counts, "
            "indices=m.indices) for m in self.aIn]\n", "mesh", True)

    def test_single_output_missing_required_field_rejects(self):
        # a mesh ctor without indices is missing a required field -> porter.
        self._rejects("rMiss",
                      "self.aOut = Mesh(points=self.aIn.points, "
                      "counts=self.aIn.counts)\n", "mesh", False)

    def test_single_output_non_ctor_rejects(self):
        # a bare pass-through of a single geo value is not a ctor -> porter.
        self._rejects("rBare", "self.aOut = self.aIn\n", "mesh", False)


class TestGeoIoCompileNative(unittest.TestCase):
    """The generated TU compiles against the running mayapy's Maya devkit. SKIP
    (not fail) without a compiler/devkit."""

    def _compile(self, name, t, is_array, tag):
        from mpynode.native.toolchain import toolchain

        if not _have_toolchain():
            self.skipTest("no C++ compiler or Maya devkit for the running mayapy")
        cxx = shutil.which("clang++") or shutil.which("g++")
        cpp = _gen(name, _compute(t, is_array), t, is_array)
        inc = toolchain.maya_include_dir(_running_maya_root())
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

    def test_mesh_single_compiles(self):
        self._compile("cMeshOne", "mesh", False, "meshOne")

    def test_mesh_array_compiles(self):
        self._compile("cMeshArr", "mesh", True, "meshArr")

    def test_curve_single_compiles(self):
        self._compile("cCrvOne", "nurbsCurve", False, "crvOne")

    def test_curve_array_compiles(self):
        self._compile("cCrvArr", "nurbsCurve", True, "crvArr")

    def test_surface_single_compiles(self):
        self._compile("cSrfOne", "nurbsSurface", False, "srfOne")

    def test_surface_array_compiles(self):
        self._compile("cSrfArr", "nurbsSurface", True, "srfArr")


# --------------------------------------------------------------------------- #
def _make_source(mc, t, seed):
    if t == "mesh":
        tr, _ = mc.polyCube(w=1 + seed, h=1, d=1)
        mc.move(seed * 3.0, 0, 0, tr)
        shp = mc.listRelatives(tr, s=True, f=True)[0]
        return shp + ".outMesh"
    if t == "nurbsCurve":
        pts = [(0, 0, 0), (1, 1 + seed, 0), (2, -1, 0), (3, 1, 0), (4, 0, 0)]
        tr  = mc.curve(d=3, p=pts)
        shp = mc.listRelatives(tr, s=True, f=True)[0]
        return shp + ".local"
    tr, _ = mc.nurbsPlane(d=3, u=3, v=3, w=1 + seed)
    shp = mc.listRelatives(tr, s=True, f=True)[0]
    return shp + ".local"


def _read_geo(om2, plug, kind):
    try:
        data = plug.asMObject()
    except Exception:
        return None
    if data is None or data.isNull():
        return None

    def _flat(arr):
        out = []
        for p in arr:
            out.extend((round(p.x, 5), round(p.y, 5), round(p.z, 5)))
        return out

    try:
        if kind == "mesh":
            mfn = om2.MFnMesh(data)
            if mfn.numVertices == 0:
                return None
            counts, connects = mfn.getVertices()
            # UV points PLUS the assignment (per-face uv counts + uvIds). A
            # mesh built from a bare ctor legitimately has no UV set at all and
            # these raise, so they must not sink the whole read -- only the
            # passthrough case asserts on them.
            try:
                _u, _v = mfn.getUVs()
                _uc, _ui = mfn.getAssignedUVs()
            except Exception:
                _u, _v, _uc, _ui = [], [], [], []
            return {"pts": _flat(mfn.getPoints(om2.MSpace.kObject)),
                    "topo": (tuple(counts), tuple(connects)),
                    "uv": ([round(x, 5) for x in _u], [round(x, 5) for x in _v],
                           tuple(_uc), tuple(_ui))}
        if kind == "curve":
            mfn = om2.MFnNurbsCurve(data)
            if mfn.numCVs == 0:
                return None
            return {"pts": _flat(mfn.cvPositions(om2.MSpace.kObject)),
                    "topo": (mfn.numCVs, mfn.degree)}
        mfn = om2.MFnNurbsSurface(data)
        if mfn.numCVsInU == 0 or mfn.numCVsInV == 0:
            return None
        return {"pts": _flat(mfn.cvPositions(om2.MSpace.kObject)),
                "topo": (mfn.numCVsInU, mfn.numCVsInV,
                         mfn.degreeInU, mfn.degreeInV)}
    except Exception:
        return None


class TestGeoIoRuntimeRoundTrip(unittest.TestCase):
    """The empirical proof: wire a real shape in, eval, read the built geometry
    back and assert topology + positions survived. SKIP without a
    compiler/devkit."""

    def _roundtrip(self, t, is_array):
        import maya.cmds as mc
        import maya.api.OpenMaya as om2
        from mpynode.native.toolchain import compile_controller as cc

        if not _have_toolchain():
            self.skipTest("no C++ compiler or Maya devkit for the running mayapy")
        kind = _KIND_OF[t]
        name = "geoio_%s_%s" % (t, "arr" if is_array else "one")
        spec = _spec(name, _compute(t, is_array), t, is_array)
        # give each node a distinct type id (a re-registered id would clash).
        base                                = 0x00070560 + _KINDS.index(t) * 4 + (1 if is_array else 0)
        spec["suggested"]["type_id"]        = "0x%08x" % base
        spec["suggested"]["node_type_name"] = name
        spec["suggested"]["class_name"]     = "GeoIoRt" + name.title().replace("_", "")

        d = tempfile.mkdtemp()
        res = cc.compile_plugin([spec], name, d, strict=True, verify=False,
                                reuse_cache=False)
        self.assertTrue(res["ok"], "build failed: %s" % res.get("errors"))
        mc.file(new=True, force=True)
        mc.loadPlugin(res["bundle_path"])
        node   = mc.createNode(name)
        n_elem = 3 if is_array else 1
        srcs   = []
        for i in range(n_elem):
            out_plug = _make_source(mc, t, i)
            dst      = "%s.aIn[%d]" % (node, i) if is_array else "%s.aIn" % node
            mc.connectAttr(out_plug, dst, f=True)
            srcs.append(out_plug)
        mc.dgeval("%s.aOut" % node)

        for i in range(n_elem):
            ssel = om2.MSelectionList()
            ssel.add(srcs[i])
            exp  = _read_geo(om2, ssel.getPlug(0), kind)
            nsel = om2.MSelectionList()
            nsel.add(node)
            op = om2.MFnDependencyNode(nsel.getDependNode(0)).findPlug("aOut", False)
            if is_array:
                op = op.elementByLogicalIndex(i)
            got = _read_geo(om2, op, kind)
            self.assertIsNotNone(exp, "source geometry [%d] empty" % i)
            self.assertIsNotNone(got, "output geometry [%d] empty" % i)
            self.assertEqual(exp["topo"], got["topo"],
                             "%s[%d] topology changed" % (name, i))
            self.assertEqual(len(exp["pts"]), len(got["pts"]))
            for a, b in zip(exp["pts"], got["pts"]):
                self.assertLess(abs(a - b), 1e-4,
                                "%s[%d] point moved" % (name, i))
            # A mesh passing THROUGH a compiled node must keep its UVs. The
            # struct copy has to carry the uv ASSIGNMENT (uvCounts/uvIds), not
            # just the uv points -- without the ids the rebuilt mesh comes out
            # unwrapped. Asserted on the whole-list passthrough only: the
            # single-output CTOR path builds from points/counts/indices and has
            # no UVs on EITHER side (interpreted Mesh(...) makes none either).
            if kind == "mesh" and is_array:
                self.assertTrue(exp["uv"][0],
                                "source mesh [%d] has no UVs to preserve" % i)
                self.assertEqual(exp["uv"], got["uv"],
                                 "%s[%d] UVs did not survive the compiled "
                                 "round-trip" % (name, i))
        try:
            mc.file(new=True, force=True)
            mc.unloadPlugin(os.path.basename(res["bundle_path"]))
        except Exception:
            pass

    def test_mesh_single(self):
        self._roundtrip("mesh", False)

    def test_mesh_array(self):
        self._roundtrip("mesh", True)

    def test_curve_single(self):
        self._roundtrip("nurbsCurve", False)

    def test_curve_array(self):
        self._roundtrip("nurbsCurve", True)

    def test_surface_single(self):
        self._roundtrip("nurbsSurface", False)

    def test_surface_array(self):
        self._roundtrip("nurbsSurface", True)


if __name__ == "__main__":
    unittest.main()
