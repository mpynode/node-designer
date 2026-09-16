"""Deterministic native lowering of the batched multi-cluster Procrustes solver
(task #67).

``mpynode._common.nodes.constraint.procrustes.procrustes_clusters`` fits N rigid
frames (one per vertex cluster) in a single vectorized call: batched gather
(``np.take``), masked per-cluster centroid, batched cross-covariance
(``np.einsum``), batched SVD + determinant reflection guard, and a matrix[]
array output. A node whose compute reads its two mesh inputs through the geo
read surface (``self.<geo>.points``) and calls this solver must:

  * lower DETERMINISTICALLY -- pure C++, no AI-porter PORT (the HARD RULE),
    EVEN when the compute is wrapped in the interpreted eager-eval guard
    (``_ok = True; try: ... except Exception: _ok = False; if _ok and ...``),
    which ``nd_lower._strip_eager_guard`` removes on the compile path, and
  * be BYTE-EXACT interp-vs-compiled on a real deformed mesh with a
    well-conditioned (non-coplanar) cluster.

This is the permanent guard for the transpiler capabilities the solver needs:
multi-dim ``nd::take``, batched einsum/svd/det, matrix[] array output, and --
the subtle one -- ``bool_mask.sum(axis=1)`` promoting to an int64 accumulator
(summing in bool saturates at 1, which silently collapsed every per-cluster
count to 1 and scaled the translation by the cluster width). ``py_to_cpp_test``
guards the individual ops; this guards the whole solver end to end, plus the
shipped ``procrustes_tags`` template (instantiate -> demo -> parity).

The synthetic cluster node built from the ``_INIT`` / ``_COMPUTE`` literals
below is NOT the deleted procrustes_cluster template -- it is an inline
fixture, and it is the only coverage for ``nd_lower._strip_eager_guard``,
``verify._has_stride_coupled_arrays`` and ``verify._uses_nurbs_cv_idiom``.

Compile / parity tests SKIP (never fail) without a C++ compiler or devkit.
"""
import json
import math
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_INIT = ("import numpy as np\n"
         "from mpynode._common.nodes.constraint.procrustes import "
         "procrustes_clusters\n")

# The shipped-template compute: read both meshes through the geo read surface
# (self.<geo>.points), reshape the flat cluster ids by the declared width, and
# fit every cluster in one call -- wrapped in the interpreted eager-eval guard
# the compile path strips.
_COMPUTE = (
    "_ok = True\n"
    "try:\n"
    "    rest = self.meshOrig.points\n"
    "    deformed = self.mesh.points\n"
    "    flat = np.asarray(self.clusters, dtype=np.int64)\n"
    "    Lw = int(self.clusterWidth)\n"
    "    clusters = flat.reshape(-1, Lw)\n"
    "    bind = np.asarray(self.bindMatrices, dtype=np.float64).reshape(-1, 4, 4)\n"
    "except Exception:\n"
    "    _ok = False\n"
    "if _ok and clusters.shape[0] and rest.shape[0] and deformed.shape[0]:\n"
    "    self.outMatrix = procrustes_clusters(rest, deformed, clusters, bind)\n")


def _make_node(name):
    import maya.cmds as mc
    import mpynode

    n = mc.createNode("mPyNode", name=name)
    w = mpynode.wrap_node(n)
    w.add_input_attr("meshOrig", "mesh")
    w.add_input_attr("mesh", "mesh")
    w.add_input_attr("clusters", "int", is_array=True)
    w.add_input_attr("clusterWidth", "int")
    w.add_input_attr("bindMatrices", "matrix", is_array=True)
    w.add_output_attr("outMatrix", "matrix", is_array=True)
    w.set_init_expression(_INIT)
    w.set_compute_expression(_COMPUTE)
    return n


def _gen(name):
    from mpynode.native import compiler as codegen
    from mpynode.native.spec import spec_extractor

    import maya.cmds as mc
    mc.file(new=True, force=True)
    spec = spec_extractor.extract_spec(_make_node(name))
    return codegen.generate_cpp(spec, for_port=True)


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


def _tags_template_path():
    root = os.environ.get("MPYNODE_ROOT") or os.getcwd()
    return os.path.join(root, "templates", "MPyConstraint",
                        "Procrustes Tags", "template.mpn")


# --------------------------------------------------------------------------- #
class TestEagerGuardStrip(unittest.TestCase):
    """``_strip_eager_guard`` rewrites the interpreted eager-eval guard to its
    unguarded form (compile path only) -- so a defensively-wrapped compute
    lowers. Maya-free (pure AST transform)."""

    def _strip(self, src):
        from mpynode.native.compiler.nd_lower import _strip_eager_guard
        return _strip_eager_guard(src)

    def test_compound_condition_drops_flag(self):
        out = self._strip(
            "_ok = True\ntry:\n    a = self.x.points\nexcept Exception:\n"
            "    _ok = False\nif _ok and a.shape[0] and b:\n    self.y = a\n")
        self.assertNotIn("_ok", out)
        self.assertNotIn("try", out)
        self.assertIn("a = self.x.points", out)
        self.assertIn("if a.shape[0] and b:", out)

    def test_lone_flag_becomes_true(self):
        out = self._strip(
            "_ok = True\ntry:\n    a = self.x.points\nexcept Exception:\n"
            "    _ok = False\nif _ok:\n    self.y = a\n")
        self.assertNotIn("_ok", out)
        self.assertIn("if True:", out)

    def test_non_guard_is_unchanged(self):
        src = "a = self.x.points\nself.y = a\n"
        self.assertEqual(self._strip(src).strip(), src.strip())

    def test_real_handler_not_stripped(self):
        # a handler with real recovery logic is NOT a trivial guard -> left
        # intact so the node falls back to the porter (no silent behaviour change).
        src = ("try:\n    a = self.x.points\nexcept Exception:\n"
               "    a = compute_fallback()\nself.y = a\n")
        self.assertIn("except", self._strip(src))


# --------------------------------------------------------------------------- #
class TestClusterLowerPureCpp(unittest.TestCase):
    def test_guarded_solver_lowers(self):
        from mpynode.native import compiler as codegen

        cpp = _gen("clLower")
        self.assertNotIn(codegen.PORT_BEGIN, cpp,
                         "guarded batched Procrustes solver must lower to C++")
        # Fingerprints of the ops the solver relies on.
        self.assertIn("nd::take",   cpp)
        self.assertIn("nd::einsum", cpp)
        self.assertIn("nd::svd",    cpp)
        self.assertIn("nd::det",    cpp)
        # bool mask count must promote to an int64 accumulator (the 8x bug).
        self.assertIn("nd::sum(nd::astype<int64_t>", cpp)
        # matrix[] array output sink.
        self.assertIn("std::vector<MMatrix>", cpp)


# --------------------------------------------------------------------------- #
class TestClusterRuntimeParity(unittest.TestCase):
    """Byte-exact interp-vs-compiled on a real deformed mesh.

    worldMesh does not bake the transform in headless mayapy, so DEFORM the
    object-space vertices to make rest != deformed -- a genuine non-identity
    rigid fit. One cluster of all 8 cube corners is non-coplanar (a coplanar
    face cluster is a degenerate Procrustes fit whose rotation is ambiguous, so
    LAPACK and the Jacobi SVD legitimately disagree there).
    """

    def test_cluster_parity(self):
        import maya.cmds as mc
        from mpynode.native.spec import spec_extractor
        from mpynode.native.toolchain import compile_controller as cc

        if not _have_toolchain():
            self.skipTest("no C++ compiler or Maya devkit for the running mayapy")

        mc.file(new=True, force=True)
        rest_tr, _ = mc.polyCube(sx=1, sy=1, sz=1)
        rest_shp = mc.listRelatives(rest_tr, s=True, f=True)[0]
        def_tr   = mc.duplicate(rest_tr)[0]
        def_shp  = mc.listRelatives(def_tr, s=True, f=True)[0]
        for i in range(8):
            a = 0.35 * i
            mc.move(0.20 * math.cos(a), 0.15 * math.sin(a * 1.3) + 0.4,
                    0.12 * math.sin(a), "%s.vtx[%d]" % (def_shp, i),
                    r=True, os=True)

        ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        clus  = [0, 1, 2, 3, 4, 5, 6, 7]

        def wire(n):
            mc.connectAttr(rest_shp + ".worldMesh[0]", n + ".meshOrig", f=True)
            mc.connectAttr(def_shp + ".worldMesh[0]", n + ".mesh", f=True)
            for i, v in enumerate(clus):
                mc.setAttr("%s.clusters[%d]" % (n, i), v)
            mc.setAttr(n + ".clusterWidth", 8)
            mc.setAttr("%s.bindMatrices[0]" % n, *ident, type="matrix")

        ni = _make_node("i_cluster")
        wire(ni)
        interp = mc.getAttr(ni + ".outMatrix[0]")

        spec   = spec_extractor.extract_spec(ni)
        d      = tempfile.mkdtemp()
        res = cc.compile_plugin([spec], "clusterpar", d, strict=True,
                                verify=False, reuse_cache=False)
        self.assertTrue(res["ok"], "build failed: %s" % res.get("errors"))
        mc.loadPlugin(res["bundle_path"])
        nc = mc.createNode(spec["suggested"]["node_type_name"])
        wire(nc)
        compiled = mc.getAttr(nc + ".outMatrix[0]")

        maxerr = max(abs(float(a) - float(b))
                     for a, b in zip(list(interp), list(compiled)))
        self.assertLess(maxerr, 1e-6,
                        "cluster parity maxerr=%.3e\ninterp=%s\ncompiled=%s"
                        % (maxerr, interp, compiled))


# --------------------------------------------------------------------------- #
class TestShippedTemplateParity(unittest.TestCase):
    """The SHIPPED procrustes_tags template: instantiate from its payload,
    run its demo (fabricates the scene, seeds the DECLARED inputs via setAttr),
    then prove the same node compiles PURE C++ and is byte-exact at a twisted
    frame. Guards the actual template + demo seeding from regression.

    Rehomed from procrustes_cluster (deleted). This is the repo's only
    end-to-end shipped-template -> demo -> deterministic-lowering -> parity
    gate, and leaving it pointed at a missing template would have turned it
    into a permanent silent skipTest rather than a failure. It reuses the
    demo's TAGGED mesh, which is what keeps it non-vacuous: the generic parity
    sweep wires an untagged shape and cannot exercise this node."""

    def test_shipped_template_demo_parity(self):
        import maya.cmds as mc
        import mpynode
        from mpynode._base.commands import _ImportNodeCommand, run_undoable
        from mpynode.native import compiler as codegen
        from mpynode.native.spec import spec_extractor
        from mpynode.native.toolchain import compile_controller as cc

        path = _tags_template_path()
        if not os.path.isfile(path):
            self.skipTest("shipped procrustes_tags template not found")
        if not _have_toolchain():
            self.skipTest("no C++ compiler or Maya devkit for the running mayapy")

        with open(path) as fh:
            data = json.load(fh)["data"]
        mc.file(new=True, force=True)
        cmd = _ImportNodeCommand(data, restore_persistent=False,
                                 seed_setup=False)
        name = run_undoable(cmd) or getattr(cmd, "created_name", None)
        node = mpynode.wrap_node(name)
        node.run_demo()

        # demo seeded the DECLARED inputs (not stored vars).
        self.assertTrue(mc.getAttr(name + ".clusterTags", multiIndices=True))
        self.assertTrue(mc.listAttr(name + ".bindMatrices", multi=True))

        mc.currentTime(60)  # twisted frame -> non-identity fits
        n_out = len(mc.listAttr(name + ".outMatrix", multi=True) or [])
        self.assertGreater(n_out, 0)
        interp = [mc.getAttr("%s.outMatrix[%d]" % (name, i))
                  for i in range(n_out)]

        mesh_src = mc.listConnections(name + ".mesh", s=True, d=False, p=True)[0]
        orig_src = mc.listConnections(name + ".meshOrig", s=True, d=False,
                                      p=True)[0]
        cl = [(i, mc.getAttr("%s.clusterTags[%d]" % (name, i)))
              for i in (mc.getAttr(name + ".clusterTags",
                                   multiIndices=True) or [])]
        nbm = len(mc.listAttr(name + ".bindMatrices", multi=True) or [])
        bms = [mc.getAttr("%s.bindMatrices[%d]" % (name, i))
               for i in range(nbm)]

        spec = spec_extractor.extract_spec(name)
        cpp  = codegen.generate_cpp(spec, for_port=True)
        self.assertNotIn(codegen.PORT_BEGIN, cpp,
                         "shipped template must lower deterministically")

        d = tempfile.mkdtemp()
        res = cc.compile_plugin([spec], "clusterTpl", d, strict=True,
                                verify=False, reuse_cache=False)
        self.assertTrue(res["ok"], "build failed: %s" % res.get("errors"))
        mc.loadPlugin(res["bundle_path"])
        nc = mc.createNode(spec["suggested"]["node_type_name"])
        mc.connectAttr(mesh_src, nc + ".mesh", f=True)
        mc.connectAttr(orig_src, nc + ".meshOrig", f=True)
        for i, v in cl:
            mc.setAttr("%s.clusterTags[%d]" % (nc, i), v, type="string")
        for i, m in enumerate(bms):
            mc.setAttr("%s.bindMatrices[%d]" % (nc, i), *list(m), type="matrix")
        compiled = [mc.getAttr("%s.outMatrix[%d]" % (nc, i))
                    for i in range(n_out)]

        maxerr = 0.0
        for i in range(n_out):
            for a, b in zip(list(interp[i]), list(compiled[i])):
                maxerr = max(maxerr, abs(float(a) - float(b)))
        self.assertLess(maxerr, 1e-6,
                        "shipped template parity maxerr=%.3e" % maxerr)


class TestStrideCoupledArrayDetection(unittest.TestCase):
    """``verify._has_stride_coupled_arrays``: the generic parity harness must SKIP
    a node whose array inputs are cross-coupled by a scalar-int reshape stride
    (procrustesCluster: ``clusters`` int[] + ``clusterWidth`` int + ``bindMatrices``
    matrix[]) -- the per-input random drive cannot synthesize a consistent set, so
    the interpreted reference raises mid-compute and the pointwise compare is a
    FALSE fail. It must still RUN for a node whose width comes from the array's OWN
    shape (procrustesSingle). Pure function -- no Maya needed."""

    @staticmethod
    def _spec(inputs, compute):
        return {"inputs": inputs, "compute": compute}

    def test_cluster_aliased_reshape_is_coupled(self):
        from mpynode.native.toolchain import verify
        spec = self._spec(
            {"clusters": {"type": "int", "is_array": True},
             "clusterWidth": {"type": "int"},
             "bindMatrices": {"type": "matrix", "is_array": True}},
            "Lw = int(self.clusterWidth)\nclusters = flat.reshape(-1, Lw)\n")
        self.assertTrue(verify._has_stride_coupled_arrays(spec))

    def test_direct_reshape_by_int_input_is_coupled(self):
        from mpynode.native.toolchain import verify
        spec = self._spec(
            {"data": {"type": "float", "is_array": True},
             "width": {"type": "int"}},
            "m = np.asarray(self.data).reshape(-1, self.width)\n")
        self.assertTrue(verify._has_stride_coupled_arrays(spec))

    def test_single_shape_derived_width_not_coupled(self):
        # procrustesSingle: width from the array's OWN shape, NO int scalar input.
        from mpynode.native.toolchain import verify
        spec = self._spec(
            {"cluster": {"type": "int", "is_array": True},
             "bindMatrix": {"type": "matrix"}},
            "flat = np.asarray(self.cluster).ravel()\n"
            "Lw = int(flat.shape[0])\nclusters = flat.reshape(1, Lw)\n")
        self.assertFalse(verify._has_stride_coupled_arrays(spec))

    def test_no_reshape_not_coupled(self):
        from mpynode.native.toolchain import verify
        spec = self._spec(
            {"vals": {"type": "int", "is_array": True},
             "k": {"type": "int"}},
            "self.out = np.asarray(self.vals) * self.k\n")
        self.assertFalse(verify._has_stride_coupled_arrays(spec))

    def test_int_scalar_not_feeding_reshape_not_coupled(self):
        # reshape by a LITERAL, int scalar present but unrelated -> not coupled.
        from mpynode.native.toolchain import verify
        spec = self._spec(
            {"pts": {"type": "vector", "is_array": True},
             "mode": {"type": "int"}},
            "g = np.asarray(self.pts).reshape(-1, 3)\nif self.mode:\n    pass\n")
        self.assertFalse(verify._has_stride_coupled_arrays(spec))


class TestNurbsCvIdiomDetection(unittest.TestCase):
    """``verify._uses_nurbs_cv_idiom``: the generic deformer parity harness
    attaches a polygon SPHERE, so a NURBS CV-idiom deformer
    (cvPositions/setCVPositions) must be SKIPPED there and deferred to its
    authored @maya_test (which drives a real NURBS surface)."""

    def test_cvpositions_read_is_nurbs_idiom(self):
        from mpynode.native.toolchain import verify
        spec = {"compute": "h = self.outputGeometry[0]\n"
                           "rest = h.cvPositions()\n"
                           "h.setCVPositions(rest)\n"}
        self.assertTrue(verify._uses_nurbs_cv_idiom(spec))

    def test_setcvpositions_only_is_nurbs_idiom(self):
        from mpynode.native.toolchain import verify
        self.assertTrue(verify._uses_nurbs_cv_idiom(
            {"compute": "h.setCVPositions(out)\n"}))

    def test_mesh_getpoints_is_not_nurbs_idiom(self):
        from mpynode.native.toolchain import verify
        spec = {"compute": "m = self.outputGeometry[0]\n"
                           "p = m.getPoints()\n"
                           "m.setPoints(p)\n"}
        self.assertFalse(verify._uses_nurbs_cv_idiom(spec))

    def test_empty_compute_is_not_nurbs_idiom(self):
        from mpynode.native.toolchain import verify
        self.assertFalse(verify._uses_nurbs_cv_idiom({}))
        self.assertFalse(verify._uses_nurbs_cv_idiom({"compute": ""}))


if __name__ == "__main__":
    unittest.main()
