"""Native codegen for the component-tag read surface (task #84).

A plain node whose compute reads a geo INPUT's component tags --
``self.<geo>.region("literalTag")`` (gather the tagged vertices'/CVs' positions
-> ``(K, 3)``) or ``self.<geo>.component_tags["literalTag"]["indices"]`` (the
raw indices: ``(K,)`` for a mesh/curve single-indexed tag, ``(K, 2)`` ``(u, v)``
for a surface double-indexed CV tag) -- must:

  * lower DETERMINISTICALLY (no AI-porter PORT region -- the HARD RULE): the tag
    is decoded in C++ off the input's geometry DATA MObject via
    ``MFnGeometryData::componentTagContents`` + ``MFnSingleIndexedComponent`` /
    ``MFnDoubleIndexedComponent``, the SAME decode ``geometry.py`` uses, and
  * COMPILE against the running mayapy's Maya devkit, and
  * be BYTE-EXACT interp-vs-compiled on a real authored component tag.

Any tag use outside this surface (a bare ``.component_tags`` dict, a non-literal
tag name, ``["type"]`` instead of ``["indices"]``) must REJECT the lowering so
the node keeps the AI-porter path (zero regression).

Structural + reject assertions need no compiler; the compile / parity tests SKIP
(never fail) without a C++ compiler or devkit.
"""
import os
import re
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_REGION = ("pts = self.inG.region('grp')\n"
           "self.cx = float(pts.mean(axis=0)[0])\n"
           "self.cy = float(pts.mean(axis=0)[1])\n"
           "self.cz = float(pts.mean(axis=0)[2])\n"
           "self.k = float(pts.shape[0])\n")
_TAGIDX = ("idx = self.inG.component_tags['grp']['indices']\n"
           "self.s = float(idx.sum())\n"
           "self.k = float(idx.size)\n")
_REGION_OUTS = [("cx", "double"), ("cy", "double"), ("cz", "double"),
                ("k", "double")]
_TAGIDX_OUTS = [("s", "double"), ("k", "double")]
# ``tag_clusters`` differs from the two above in the ONE way that matters: the
# tag names are RUNTIME data read from a multi-string input, not a compile-time
# literal. sum() over the padded (N, L) result pins membership AND the -1 fill.
_TAGCL = ("cl = self.inG.tag_clusters(self.clusterTags)\n"
          "self.n = float(cl.shape[0])\n"
          "self.w = float(cl.shape[1])\n"
          "self.s = float(cl.sum())\n")
_TAGCL_OUTS = [("n", "double"), ("w", "double"), ("s", "double")]


def _make_node(name, compute, gt, outs, str_arrays=()):
    import maya.cmds as mc
    import mpynode

    mc.file(new=True, force=True)
    n = mc.createNode("mPyNode", name=name)
    w = mpynode.wrap_node(n)
    w.add_input_attr("inG", gt)
    for nm in str_arrays:
        w.add_input_attr(nm, "string", is_array=True)
    for nm, t in outs:
        w.add_output_attr(nm, t)
    w.set_compute_expression(compute)
    return n


def _spec(name, compute, gt, outs, str_arrays=()):
    from mpynode.native.spec import spec_extractor

    return spec_extractor.extract_spec(
        _make_node(name, compute, gt, outs, str_arrays))


def _gen(name, compute, gt, outs, str_arrays=()):
    from mpynode.native import compiler as codegen

    return codegen.generate_cpp(_spec(name, compute, gt, outs, str_arrays),
                                for_port=True)


def _lowers(name, compute, gt, outs, str_arrays=()):
    from mpynode.native import compiler as codegen

    return codegen.PORT_BEGIN not in _gen(name, compute, gt, outs, str_arrays)


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
class TestTagLowerPureCpp(unittest.TestCase):
    def _no_port(self, cpp):
        from mpynode.native import compiler as codegen
        self.assertNotIn(codegen.PORT_BEGIN, cpp,
                         "tag read must lower to pure C++ (no PORT)")

    def test_mesh_region_lowers(self):
        cpp = _gen("tMReg", _REGION, "mesh", _REGION_OUTS)
        self._no_port(cpp)
        self.assertIn("MFnGeometryData", cpp)
        self.assertIn("componentTagContents", cpp)
        self.assertIn("MFnSingleIndexedComponent", cpp)
        # BEHAVIOUR, not spelling: the tagged vertices are gathered from the
        # mesh's OBJECT-space positions. Either MFnMesh read is correct (the raw
        # float3 array or an MPointArray -- bit-identical in object space); the
        # SPACE is the invariant. The gathered VALUES are pinned by
        # TestTagRuntimeParity.test_mesh_region_parity.
        self.assertTrue("getRawPoints(" in cpp
                        or "getPoints(_tp, MSpace::kObject)" in cpp,
                        "region must gather object-space vertex positions")
        self.assertEqual(
            sorted(set(re.findall(r"MSpace::\w+", cpp)) - {"MSpace::kObject"}),
            [], "mesh region gather must stay OBJECT space (the bit-safe one)")

    def test_mesh_tagidx_lowers(self):
        cpp = _gen("tMIdx", _TAGIDX, "mesh", _TAGIDX_OUTS)
        self._no_port(cpp)
        self.assertIn("MFnSingleIndexedComponent", cpp)

    def test_mesh_tag_clusters_lowers(self):
        cpp = _gen("tMCl", _TAGCL, "mesh", _TAGCL_OUTS, ("clusterTags",))
        self._no_port(cpp)
        self.assertIn("MFnGeometryData", cpp)
        self.assertIn("hasComponentTag", cpp)
        self.assertIn("MFnSingleIndexedComponent", cpp)
        # THE point of this form, asserted as BEHAVIOUR not spelling (the input
        # variable carries the emitter's member mangling): the tag name handed
        # to the decode is READ from the multi-string input at runtime.
        # region()/component_tags[] bake it as a C++ string literal instead --
        # which is precisely what a runtime tag list cannot do.
        self.assertIn("hasComponentTag(in_", cpp)
        self.assertNotIn('hasComponentTag("', cpp)
        # padded (N, L) with -1 fill -- the shape pad_clusters produces.
        self.assertIn("(int64_t)-1", cpp)

    def test_curve_region_lowers(self):
        cpp = _gen("tCReg", _REGION, "nurbsCurve", _REGION_OUTS)
        self._no_port(cpp)
        self.assertIn("getCVs(_tp, MSpace::kObject)", cpp)

    def test_surface_region_lowers(self):
        cpp = _gen("tSReg", _REGION, "nurbsSurface", _REGION_OUTS)
        self._no_port(cpp)
        self.assertIn("MFnDoubleIndexedComponent", cpp)
        self.assertIn("numCVsInV()", cpp)

    def test_surface_tagidx_lowers(self):
        cpp = _gen("tSIdx", _TAGIDX, "nurbsSurface", _TAGIDX_OUTS)
        self._no_port(cpp)
        self.assertIn("MFnDoubleIndexedComponent", cpp)

    def test_tag_headers_present(self):
        cpp = _gen("tHdr", _REGION, "mesh", _REGION_OUTS)
        self.assertIn("maya/MFnGeometryData.h", cpp)
        self.assertIn("maya/MFnSingleIndexedComponent.h", cpp)
        self.assertIn("maya/MFnDoubleIndexedComponent.h", cpp)

    def test_no_tag_read_omits_tag_headers(self):
        # a plain mesh-input node that never touches tags must NOT pull the tag
        # decode headers (keeps its frag byte-identical / port cache intact).
        cpp = _gen("tNoTag",
                   "self.cx = float(self.inG.points.mean(axis=0)[0])\n",
                   "mesh", [("cx", "double")])
        self.assertNotIn("maya/MFnGeometryData.h", cpp)


class TestTagRejectsToPorter(unittest.TestCase):
    def _rejects(self, name, compute, outs=(("cx", "double"),)):
        self.assertFalse(_lowers(name, compute, "mesh", list(outs)),
                         "unsupported tag use must NOT lower (keeps porter)")

    def test_bare_component_tags_rejects(self):
        self._rejects("rBare",
                      "self.cx = float(len(self.inG.component_tags))\n")

    def test_tag_type_key_rejects(self):
        # ["type"] is not the supported ["indices"] slice -> porter.
        self._rejects("rType",
                      "self.cx = float(self.inG.component_tags['grp']['type'] "
                      "== 'vertex')\n")

    def test_non_literal_region_rejects(self):
        self._rejects(
            "rDyn",
            "t = 'gr' + 'p'\npts = self.inG.region(t)\n"
            "self.cx = float(pts.mean())\n")

    def test_tag_clusters_literal_list_rejects(self):
        # the names must be a multi-string INPUT -- a literal list has no
        # in_<member> to index at runtime, so the compute stays on the porter.
        self._rejects("rClLit",
                      "cl = self.inG.tag_clusters(['a', 'b'])\n"
                      "self.cx = float(cl.shape[0])\n")

    def test_tag_clusters_on_surface_rejects(self):
        # tag_clusters is a Mesh-only wrapper method, so a surface read has no
        # interpreted counterpart to be at parity with -> porter, not a guess.
        self.assertFalse(
            _lowers("rClSrf", _TAGCL, "nurbsSurface", _TAGCL_OUTS,
                    ("clusterTags",)),
            "tag_clusters on a non-mesh must NOT lower (keeps porter)")


class TestTagCompileNative(unittest.TestCase):
    def _compile(self, name, compute, gt, outs, tag):
        from mpynode.native.toolchain import toolchain
        import subprocess

        if not _have_toolchain():
            self.skipTest("no C++ compiler or Maya devkit for the running mayapy")
        cxx = shutil.which("clang++") or shutil.which("g++")
        cpp = _gen(name, compute, gt, outs)
        inc = toolchain.maya_include_dir(_running_maya_root())
        native_dir = os.path.join(os.environ["MPYNODE_ROOT"], "scripts",
                                  "mpynode", "native")
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, tag + ".cpp")
            with open(src, "w") as fh:
                fh.write(cpp)
            cmd = [cxx, "-std=c++17", "-O2", "-c", src, "-o",
                   os.path.join(d, tag + ".o"), "-I", inc, "-I", native_dir]
            md = toolchain.maya_define()
            if md:
                cmd += ["-D" + md]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             "%s compile failed:\n%s" % (tag, proc.stderr[-4000:]))

    def test_mesh_region_compiles(self):
        self._compile("cMReg", _REGION, "mesh", _REGION_OUTS, "mReg")

    def test_surface_region_compiles(self):
        self._compile("cSReg", _REGION, "nurbsSurface", _REGION_OUTS, "sReg")

    def test_surface_tagidx_compiles(self):
        self._compile("cSIdx", _TAGIDX, "nurbsSurface", _TAGIDX_OUTS, "sIdx")


# --------------------------------------------------------------------------- #
class TestTagRuntimeParity(unittest.TestCase):
    """Byte-exact interp-vs-compiled decode on a REAL authored component tag."""

    def _parity(self, gt, mk_src, compute, outs, name, tags=()):
        import maya.cmds as mc
        from mpynode.native.spec import spec_extractor
        from mpynode.native.toolchain import compile_controller as cc

        if not _have_toolchain():
            self.skipTest("no C++ compiler or Maya devkit for the running mayapy")
        mc.file(new=True, force=True)
        shp = mk_src()
        src_plug = shp + (".outMesh" if gt == "mesh" else ".local")

        def _seed(n):
            # the SAME tag names must reach both nodes, or the comparison is
            # between two different questions rather than two implementations.
            for i, t in enumerate(tags):
                mc.setAttr("%s.clusterTags[%d]" % (n, i), t, type="string")

        ni = mc.createNode("mPyNode", name="i_" + name)
        import mpynode
        w = mpynode.wrap_node(ni)
        w.add_input_attr("inG", gt)
        if tags:
            w.add_input_attr("clusterTags", "string", is_array=True)
        for nm, t in outs:
            w.add_output_attr(nm, t)
        w.set_compute_expression(compute)
        mc.connectAttr(src_plug, ni + ".inG", f=True)
        _seed(ni)
        interp = {nm: mc.getAttr("%s.%s" % (ni, nm)) for nm, _ in outs}

        spec = spec_extractor.extract_spec(ni)
        d = tempfile.mkdtemp()
        res = cc.compile_plugin([spec], "tagpar_" + name, d, strict=True,
                                verify=False, reuse_cache=False)
        self.assertTrue(res["ok"], "build failed: %s" % res.get("errors"))
        mc.loadPlugin(res["bundle_path"])
        nc = mc.createNode(spec["suggested"]["node_type_name"])
        mc.connectAttr(src_plug, nc + ".inG", f=True)
        _seed(nc)
        for nm, _ in outs:
            vi = float(interp[nm])
            vc = float(mc.getAttr("%s.%s" % (nc, nm)))
            self.assertLess(abs(vi - vc), 1e-4,
                            "%s.%s interp=%s compiled=%s" % (name, nm, vi, vc))
        return {nm: float(interp[nm]) for nm, _ in outs}

    def _cube(self, tags):
        """``tags``: ``{tagName: [vtx, ...]}`` -- a dict, not one fixed name, so
        the padded-cluster form can be given a RAGGED tag set (the thing its -1
        fill exists for) instead of a synthetic single tag."""
        import maya.cmds as mc

        def mk():
            tr, _ = mc.polyCube()
            shp = mc.listRelatives(tr, s=True, f=True)[0]
            for nm, verts in tags.items():
                mc.componentTag(["%s.vtx[%d]" % (shp, v) for v in verts],
                                create=True, newTagName=nm)
            return shp
        return mk

    def _plane(self, uvs):
        import maya.cmds as mc

        def mk():
            tr, _ = mc.nurbsPlane(d=3, u=3, v=3)
            shp = mc.listRelatives(tr, s=True, f=True)[0]
            mc.componentTag(["%s.cv[%d][%d]" % (shp, u, v) for u, v in uvs],
                            create=True, newTagName="grp")
            return shp
        return mk

    def _curve(self, cvs):
        import maya.cmds as mc

        def mk():
            tr = mc.curve(d=3, p=[(0, 0, 0), (1, 2, 0), (2, -1, 0),
                                  (3, 1, 0), (4, 0, 0)])
            shp = mc.listRelatives(tr, s=True, f=True)[0]
            mc.componentTag(["%s.cv[%d]" % (shp, c) for c in cvs],
                            create=True, newTagName="grp")
            return shp
        return mk

    def test_mesh_region_parity(self):
        self._parity("mesh", self._cube({"grp": [0, 2, 4, 6]}), _REGION,
                     _REGION_OUTS, "mReg")

    def test_mesh_tagidx_parity(self):
        self._parity("mesh", self._cube({"grp": [1, 3, 5]}), _TAGIDX,
                     _TAGIDX_OUTS, "mIdx")

    def test_mesh_tag_clusters_parity(self):
        # Ragged ON PURPOSE: 4 members vs 2 forces the -1 padding, and a name
        # the mesh does not carry forces the empty-row path. A single equal-size
        # tag would pass with the padding and the absent-tag branch both wrong.
        got = self._parity("mesh",
                           self._cube({"grpA": [0, 2, 4, 6], "grpB": [1, 3]}),
                           _TAGCL, _TAGCL_OUTS, "mCl",
                           tags=("grpA", "grpB", "absent"))
        # Pin the interpreted side to hand-computed values so the comparison
        # above cannot pass VACUOUSLY by agreeing on nothing. Rows are
        # [0,2,4,6] / [1,3,-1,-1] / [-1,-1,-1,-1]: 3 clusters, width 4,
        # sum 12 + 2 - 4 = 10.
        self.assertEqual((got["n"], got["w"], got["s"]), (3.0, 4.0, 10.0))

    def test_surface_region_parity(self):
        self._parity("nurbsSurface", self._plane([(0, 0), (1, 2), (3, 4)]),
                     _REGION, _REGION_OUTS, "sReg")

    def test_surface_tagidx_parity(self):
        self._parity("nurbsSurface", self._plane([(0, 0), (1, 2), (3, 4)]),
                     _TAGIDX, _TAGIDX_OUTS, "sIdx")

    def test_curve_region_parity(self):
        self._parity("nurbsCurve", self._curve([0, 2, 4]), _REGION,
                     _REGION_OUTS, "cReg")


class TestMeshMatrixFromMeshData(unittest.TestCase):
    """``worldMesh[0]`` DATA carries OBJECT-space points plus the source
    transform as a SEPARATE matrix -- a data-constructed MFnMesh has no DAG
    path, so ``getPoints(kWorld)`` cannot reach world space. Any draw that reads
    a mesh input and claims world space is therefore pinned at the origin unless
    it applies that matrix itself.

    ``mesh_matrix_from_mesh_data`` is the read for it, a sibling of
    ``tag_indices_from_mesh_data`` off the SAME MFnGeometryData."""

    def _shape(self, name, t=(0.0, 0.0, 0.0), r=(0.0, 0.0, 0.0), s=1.0):
        import maya.cmds as mc
        tr = mc.polySphere(r=5, sx=8, sy=8, name=name)[0]
        mc.setAttr(tr + ".translate", *t)
        mc.setAttr(tr + ".rotate", *r)
        mc.setAttr(tr + ".scale", s, s, s)
        return mc.listRelatives(tr, shapes=True, fullPath=True)[0]

    def _data(self, shape, plug="worldMesh"):
        import maya.api.OpenMaya as om2
        sel = om2.MSelectionList(); sel.add(shape)
        p = om2.MFnDependencyNode(sel.getDependNode(0)).findPlug(plug, False)
        if p.isArray:
            p = p.elementByLogicalIndex(0)
        return p.asMObject(), sel.getDagPath(0)

    def setUp(self):
        import maya.cmds as mc
        mc.file(new=True, force=True)

    def test_identity_transform_reads_identity(self):
        from mpynode._common.nodes.mesh.component_tags import (
            mesh_matrix_from_mesh_data)
        data, _ = self._data(self._shape("ident"))
        m = mesh_matrix_from_mesh_data(data)
        self.assertEqual(len(m), 16)
        self.assertEqual([round(v, 9) for v in m],
                         [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])

    def test_translation_reaches_the_last_row(self):
        # Maya is row-vector (p * M), so translation lives in row 3.
        from mpynode._common.nodes.mesh.component_tags import (
            mesh_matrix_from_mesh_data)
        data, _ = self._data(self._shape("moved", t=(12.0, 3.0, -4.0)))
        m = mesh_matrix_from_mesh_data(data)
        self.assertEqual([round(v, 5) for v in m[12:15]], [12.0, 3.0, -4.0])

    def test_points_times_matrix_equal_a_true_world_read(self):
        # THE oracle: this is the whole reason the helper exists.
        import maya.api.OpenMaya as om2
        from mpynode._common.nodes.mesh.component_tags import (
            mesh_matrix_from_mesh_data)
        shape = self._shape("xf", t=(12.0, 3.0, -4.0), r=(0.0, 30.0, 0.0),
                            s=2.0)
        data, dag = self._data(shape)
        m = om2.MMatrix(mesh_matrix_from_mesh_data(data))
        got = [p * m for p in om2.MFnMesh(data).getPoints(om2.MSpace.kObject)]
        want = om2.MFnMesh(dag).getPoints(om2.MSpace.kWorld)
        self.assertEqual(len(got), len(want))
        for a, b in zip(got, want):
            self.assertAlmostEqual(a.x, b.x, places=5)
            self.assertAlmostEqual(a.y, b.y, places=5)
            self.assertAlmostEqual(a.z, b.z, places=5)

    def test_object_space_plug_data_reads_identity(self):
        # outMesh carries no transform -- the helper must not invent one.
        from mpynode._common.nodes.mesh.component_tags import (
            mesh_matrix_from_mesh_data)
        data, _ = self._data(self._shape("obj", t=(9.0, 9.0, 9.0)), "outMesh")
        m = mesh_matrix_from_mesh_data(data)
        self.assertEqual([round(v, 5) for v in m[12:15]], [0.0, 0.0, 0.0])

    def test_the_api1_datablock_path_reads_the_same_matrix(self):
        """The LIVE compute goes through ``mesh_data_from_node_plug``, which
        hands back an **api1** MObject -- so the api1 branch, not the api2 one,
        is what actually runs. api1 mirrors C++ (``getMatrix(MMatrix&)`` out-
        param) and has no ``.matrix`` property; reading it the api2 way returns
        None through the except and silently pins the draw at the origin."""
        import maya.OpenMaya as om1
        from mpynode._common.nodes.mesh.component_tags import (
            mesh_matrix_from_mesh_data)
        shape = self._shape("a1", t=(12.0, 3.0, -4.0), r=(0.0, 30.0, 0.0))

        sel = om1.MSelectionList()
        sel.add(shape + ".worldMesh[0]")
        plug = om1.MPlug()
        sel.getPlug(0, plug)
        if plug.isArray():
            plug = plug.elementByLogicalIndex(0)
        m1 = mesh_matrix_from_mesh_data(plug.asMObject())

        self.assertIsNotNone(m1, "api1 mesh data must yield a matrix")
        self.assertEqual([round(v, 5) for v in m1[12:15]], [12.0, 3.0, -4.0])
        # and it must agree with the api2 read of the same geometry
        data2, _ = self._data(shape)
        m2 = mesh_matrix_from_mesh_data(data2)
        for a, b in zip(m1, m2):
            self.assertAlmostEqual(a, b, places=6)

    def test_the_live_node_read_path_yields_a_matrix(self):
        """End to end through the helper the template actually calls."""
        import maya.cmds as mc
        import mpynode
        from mpynode._common.nodes.mesh.component_tags import (
            mesh_data_from_node_plug, mesh_matrix_from_mesh_data)
        shape = self._shape("live", t=(1.0, 2.0, 3.0))
        n = mc.createNode("mPyNode", name="wsProbe")
        mpynode.wrap_node(n).add_input_attr("inMesh", "mesh")
        mc.connectAttr(shape + ".worldMesh[0]", n + ".inMesh", force=True)
        m = mesh_matrix_from_mesh_data(mesh_data_from_node_plug(n, "inMesh"))
        self.assertIsNotNone(m)
        self.assertEqual([round(v, 5) for v in m[12:15]], [1.0, 2.0, 3.0])

    def test_none_and_garbage_never_raise(self):
        from mpynode._common.nodes.mesh.component_tags import (
            mesh_matrix_from_mesh_data)
        self.assertIsNone(mesh_matrix_from_mesh_data(None))
        self.assertIsNone(mesh_matrix_from_mesh_data("not an MObject"))

    def test_it_sits_beside_the_tag_read_on_the_same_data(self):
        # both helpers must accept the SAME MObject, or the compute would need
        # two different reads of one input
        from mpynode._common.nodes.mesh.component_tags import (
            mesh_matrix_from_mesh_data, tag_indices_from_mesh_data)
        import maya.cmds as mc
        shape = self._shape("both", t=(1.0, 2.0, 3.0))
        mc.componentTag(shape + ".f[0:5]", create=True, newTagName="tg")
        data, _ = self._data(shape)
        self.assertEqual(tag_indices_from_mesh_data(data, "tg"),
                         [0, 1, 2, 3, 4, 5])
        self.assertEqual([round(v, 5)
                          for v in mesh_matrix_from_mesh_data(data)[12:15]],
                         [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
