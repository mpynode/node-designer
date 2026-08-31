"""Base mPyNode contract faithfulness across node types.

Every node type re-implements the compute / expression pipeline on top
of its required Maya base class, so the base ``mPyNode`` behaviors are
NOT inherited and have historically drifted. These tests pin the shared
behaviors that every type must honor:

  * C10 -- benign / transient missing-plug errors are suppressed;
    genuine errors surface (shared ``base_contract.broadcast_compute_error``).
  * C14 -- an invalid mPyIkSolver expression surfaces the SyntaxError
    at SOLVE time via the shared ``safe_compile_expression`` (same as the
    base mPyNode). MPxIkSolverNode never routes setAttr through
    setInternalValue, so the solve-time compile is the node's only chance
    to surface a bad expression; it used to hand-roll ``compile()`` with a
    one-off message and no ``displayWarning`` (drift from the base).
  * C8 -- a DUPLICATED deformer still runs its expression (the fresh
    instance's cached code is reconciled from the ``_computeSource`` plug
    via ``ensure_expr_code``).
"""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


# ===========================================================================
# C10 -- shared benign-error suppression policy (unit level)
# ===========================================================================


class TestBroadcastComputeError(unittest.TestCase):
    """The shared error-broadcast policy used by every compute path."""

    def _missing_msg(self, name):
        return (
            "'self' has no plug, init binding, or stored var named "
            "'{}'. ...".format(name)
        )

    def test_declared_missing_plug_is_suppressed(self):
        from mpynode._common.compute.base_contract import broadcast_compute_error

        # missing-plug error for a DECLARED name is a transient EM pull
        # before the plug resolved -> suppressed (returns False).
        broadcast = broadcast_compute_error(
            "mPyNode",
            self._missing_msg("driverMatrix"),
            declared_names={"driverMatrix", "amplitude"},
        )
        self.assertFalse(broadcast)

    def test_undeclared_missing_plug_still_surfaces(self):
        from mpynode._common.compute.base_contract import broadcast_compute_error

        # an UNDECLARED name is a real typo and surfaces (returns True), but
        # only outside a transient state. should_defer_transient is
        # process-global (a 10s stamp after any kAfterOpen/kAfterImport), so
        # a neighbouring test that opens a scene leaks its grace window in
        # here. Pin it False; the transient case has its own test.
        with mock.patch(
            "mpynode._common.lifecycle.scene_state.should_defer_transient",
            return_value=False,
        ):
            broadcast = broadcast_compute_error(
                "mPyNode",
                self._missing_msg("typoName"),
                declared_names={"amplitude"},
            )
        self.assertTrue(broadcast)

    def test_transient_state_suppresses_undeclared_missing_plug(self):
        from mpynode._common.compute.base_contract import broadcast_compute_error

        # in a transient window even an UNDECLARED missing plug is deferred:
        # the schema may not be restored yet, so the "missing" name could be
        # a valid input that is not live yet.
        with mock.patch(
            "mpynode._common.lifecycle.scene_state.should_defer_transient",
            return_value=True,
        ):
            broadcast = broadcast_compute_error(
                "mPyNode",
                self._missing_msg("typoName"),
                declared_names={"amplitude"},
            )
        self.assertFalse(broadcast)

    def test_generic_error_always_surfaces(self):
        from mpynode._common.compute.base_contract import broadcast_compute_error

        broadcast = broadcast_compute_error(
            "mPyNode",
            "NameError: name 'np' is not defined",
            declared_names={"amplitude"},
        )
        self.assertTrue(broadcast)


# ===========================================================================
# C14 -- mPyIkSolver surfaces syntax errors on expression set
# ===========================================================================


class TestIkSolverSyntaxErrorSurfaces(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_bad_expression_surfaces_syntax_error(self):
        """An invalid mPyIkSolver expression surfaces the SyntaxError at
        SOLVE time via the shared ``safe_compile_expression`` (stderr +
        displayWarning), exactly like the base mPyNode.

        Root cause (verified by monkeypatch trace): MPxIkSolverNode does
        NOT route ``setAttr`` through ``setInternalValue`` -- the set-time
        compile path is dead code for this node. The solve entry point
        (``compute_ik_user_solve``) is therefore the node's ONLY chance to
        surface a bad expression. It used to hand-roll ``compile()`` with a
        one-off stderr line and no ``displayWarning``, diverging from the
        base contract; it now delegates to ``safe_compile_expression``.

        We exercise the real solve entry point directly (Maya's IK graph
        would not call it under a plain ``setAttr``), via a minimal shim
        that only needs ``thisMObject()``.
        """
        import maya.OpenMaya as om1

        from mpynode._api1 import helpers
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        s = MPyIkSolver.create(name="ikSyntax")
        mc.setAttr(
            s.get_name() + "._computeSource",
            "def (:\n",  # invalid syntax
            type="string",
        )

        # Resolve the node's API 1.0 MObject (compute_ik_user_solve builds
        # an api1 MFnDependencyNode from shim.thisMObject()).
        sel = om1.MSelectionList()
        sel.add(s.get_name())
        node_obj = om1.MObject()
        sel.getDependNode(0, node_obj)

        class _Shim(object):
            def thisMObject(self_inner):
                return node_obj

        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = helpers.compute_ik_user_solve(
                _Shim(),
                joints=[],
                end_effector=[0.0, 0.0, 0.0],
                pole_vector=[0.0, 0.0, 0.0],
                twist=0.0,
            )

        # a compile failure aborts the solve tick (last-known-good pose) and
        # surfaces the SyntaxError: compute_ik_user_solve returns its 5-tuple
        # sentinel with local_mats=None.
        self.assertEqual(result[0], None)
        self.assertEqual(len(result), 5)
        self.assertIn("compile failed", buf.getvalue())


# ===========================================================================
# C8 -- a duplicated deformer still runs its expression
# ===========================================================================


class TestDuplicatedDeformerRunsExpression(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.lifecycle import init_registry

        init_registry.clear_all_init_ns()

    def test_duplicated_deformer_still_deforms(self):
        """A deformer duplicated together with its geometry keeps
        deforming. Maya copies the ``_computeSource`` plug on duplicate
        but does NOT route through setInternalValue, so the fresh MPx
        instance's cached ``_expr_code`` is empty. ``ensure_expr_code``
        (called at the top of the compute path) must reconcile it from
        the plug so the duplicate is not a silent no-op.
        """
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="dupP", w=2, h=2, sx=4, sy=4)[0]
        d = MPyDeformer.create_on(plane)
        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += 0.5\n"
            "mesh.setPoints(pts)\n"
        )
        v_orig = mc.xform(plane + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(v_orig[1], 0.5, places=3)

        dup = mc.duplicate(plane, upstreamNodes=True, name="dupP_copy")[0]
        v_dup = mc.xform(dup + ".vtx[12]", q=True, ws=True, t=True)
        self.assertAlmostEqual(
            v_dup[1], 0.5, places=3,
            msg="duplicated deformer ran an empty expression "
                "(ensure_expr_code did not reconcile from the plug)",
        )


# ===========================================================================
# C10 -- every own-path compute type routes errors through the shared helper
# ===========================================================================


class TestOwnPathComputeUsesSharedSuppression(unittest.TestCase):
    """Each node type that re-implements its own compute path (mesh /
    nurbs curve / nurbs surface / constraint / transform / locator) must
    route expression errors through the shared ``broadcast_compute_error``
    policy, NOT an unconditional ``stderr`` write. Otherwise a benign,
    self-correcting transient missing-plug error (EM pull mid-load /
    graph-rebuild) spams the log on that type while the base mPyNode and
    the deformer family stay quiet -- the exact drift this audit removes.

    Verified behaviorally by spying on the shared helper: an erroring
    compute MUST call it (with the node's type label + the error message).
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _assert_routes_through_helper(self, make, trigger, label):
        node = make()
        with mock.patch(
            "mpynode._common.compute.base_contract.broadcast_compute_error"
        ) as spy:
            try:
                trigger(node)
            except Exception:
                pass
        self.assertTrue(
            spy.called,
            "{} compute did not route its expression error through "
            "broadcast_compute_error (still an unconditional stderr "
            "broadcast?)".format(label),
        )
        args, _kwargs = spy.call_args
        self.assertEqual(args[0], label)
        self.assertIn("nopePlug", args[1])

    def test_mesh_routes_error_through_shared_helper(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        def mk():
            p = MPyMesh.create(name="mErr")
            p.set_compute_expression("x = self.nopePlug\n")
            return p.get_name()

        self._assert_routes_through_helper(
            mk, lambda n: mc.getAttr(n + ".outMesh"), "mPyMesh"
        )

    def test_nurbs_curve_routes_error_through_shared_helper(self):
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve

        def mk():
            p = MPyNurbsCurve.create(name="cErr")
            p.set_compute_expression("x = self.nopePlug\n")
            return p.get_name()

        self._assert_routes_through_helper(
            mk, lambda n: mc.getAttr(n + ".outCurve"), "mPyNurbsCurve"
        )

    def test_nurbs_surface_routes_error_through_shared_helper(self):
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface

        def mk():
            p = MPyNurbsSurface.create(name="sErr")
            p.set_compute_expression("x = self.nopePlug\n")
            return p.get_name()

        self._assert_routes_through_helper(
            mk, lambda n: mc.getAttr(n + ".outSurface"), "mPyNurbsSurface"
        )

    def test_constraint_routes_error_through_shared_helper(self):
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        def mk():
            c = MPyConstraint.create(name="conErr")
            c.add_output_attr("constrained_pos", "vector")
            c.set_compute_expression("x = self.nopePlug\n")
            return c.get_name()

        self._assert_routes_through_helper(
            mk, lambda n: mc.getAttr(n + ".constrained_pos"), "mPyConstraint"
        )

    def test_transform_routes_error_through_shared_helper(self):
        def mk():
            n = mc.createNode("mPyTransform", name="xErr")
            mc.setAttr(
                n + "._computeSource", "x = self.nopePlug\n", type="string"
            )
            return n

        def trigger(n):
            # worldMatrix (not .matrix) pulls the opm output, which is what runs
            # the expression under the flush-free re-arch.
            mc.setAttr(n + ".translateY", 1.0)
            mc.getAttr(n + ".worldMatrix[0]")

        self._assert_routes_through_helper(mk, trigger, "mPyTransform")

    def test_file_routes_error_through_shared_helper(self):
        from mpynode.wrappers.mpy_file import MPyFile

        def mk():
            p = MPyFile.create(name="fErr", seed_defaults=False)
            p.set_compute_expression("x = self.nopePlug\n")
            return p.get_name()

        self._assert_routes_through_helper(
            mk, lambda n: mc.getAttr(n + ".outColor"), "mPyFile"
        )

    def test_locator_wires_shared_helper(self):
        """``mPyLocator._run_expression`` runs at VP2 draw time, which
        cannot be exercised headless. Pin the wiring structurally: the
        compute path must call the shared helper and must NOT keep the
        raw unconditional expression-error stderr write."""
        import inspect

        from mpynode._api2 import mpy_locator

        src = inspect.getsource(mpy_locator)
        self.assertIn("broadcast_compute_error", src)
        self.assertNotIn(
            'sys.stderr.write(f"[mPyLocator expression error]', src
        )


# ===========================================================================
# C1 -- every own-path compute type defers its expression during file read
# ===========================================================================


class TestOwnPathComputeDefersDuringFileRead(unittest.TestCase):
    """The base mPyNode skips its user expression entirely while a scene is
    being READ / OPENED (``MFileIO.isReadingFile()``): the Evaluation Manager
    can pull an output mid-load before the node's dynamic input attrs / schema
    plugs are restored, so running the expression then raises a spurious
    missing-plug error and commits a bogus (empty / default) output during
    load. Every type that re-implements its own compute path must honor the
    same defer, or it diverges from the base (C1).

    ``mPyLocator`` has NO ``compute()`` -- its expression runs at VP2 draw
    time, so there is no DG compute to guard; its transient case is covered by
    the shared C10 suppression instead. It is intentionally excluded here.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _assert_defers_during_file_read(self, make, trigger, cls):
        node = make()
        orig = cls._run_expression
        calls = []

        def spy(self_inner, *a, **k):
            calls.append(1)
            return orig(self_inner, *a, **k)

        with mock.patch.object(cls, "_run_expression", spy):
            # Phase 1: mid file-read -> the expression must NOT run.
            mc.dgdirty(node)
            del calls[:]
            with mock.patch(
                "maya.OpenMaya.MFileIO.isReadingFile", return_value=True
            ):
                try:
                    trigger(node)
                except Exception:
                    pass
            self.assertEqual(
                calls, [],
                "{} ran its expression during file read (C1 defer "
                "missing)".format(cls.__name__),
            )

            # Phase 2: scene whole -> the expression runs normally.
            mc.dgdirty(node)
            del calls[:]
            try:
                trigger(node)
            except Exception:
                pass
            self.assertTrue(
                calls,
                "{} did not run its expression once the scene was whole "
                "(defer never releases)".format(cls.__name__),
            )

    def test_mesh_defers_during_file_read(self):
        from mpynode._api2.mpy_mesh import MPyMesh
        from mpynode.wrappers.mpy_mesh import MPyMesh as MPyMeshWrap

        def mk():
            p = MPyMeshWrap.create(name="mDefer")
            p.set_compute_expression("x = 1\n")
            return p.get_name()

        self._assert_defers_during_file_read(
            mk, lambda n: mc.getAttr(n + ".outMesh"), MPyMesh
        )

    def test_nurbs_curve_defers_during_file_read(self):
        from mpynode._api2.mpy_nurbs_curve import MPyNurbsCurve
        from mpynode.wrappers.mpy_nurbs_curve import (
            MPyNurbsCurve as MPyNurbsCurveWrap,
        )

        def mk():
            p = MPyNurbsCurveWrap.create(name="cDefer")
            p.set_compute_expression("x = 1\n")
            return p.get_name()

        self._assert_defers_during_file_read(
            mk, lambda n: mc.getAttr(n + ".outCurve"), MPyNurbsCurve
        )

    def test_nurbs_surface_defers_during_file_read(self):
        from mpynode._api2.mpy_nurbs_surface import MPyNurbsSurface
        from mpynode.wrappers.mpy_nurbs_surface import (
            MPyNurbsSurface as MPyNurbsSurfaceWrap,
        )

        def mk():
            p = MPyNurbsSurfaceWrap.create(name="sDefer")
            p.set_compute_expression("x = 1\n")
            return p.get_name()

        self._assert_defers_during_file_read(
            mk, lambda n: mc.getAttr(n + ".outSurface"), MPyNurbsSurface
        )

    def test_transform_defers_during_file_read(self):
        # Flush-free re-arch: MPyTransform.compute runs the expression when
        # _outLocalFlat is pulled, reusing MPyTransformMatrix._run_expression.
        # So spy on MPyTransformMatrix, and pull worldMatrix, not .matrix.
        from mpynode._api1.mpy_transform import MPyTransformMatrix

        counter = {"n": 0}

        def mk():
            n = mc.createNode("mPyTransform", name="xDefer")
            mc.setAttr(n + "._computeSource", "x = 1\n", type="string")
            return n

        def trigger(n):
            # a fresh translate value re-dirties the opm output, so the
            # expression re-runs each phase.
            counter["n"] += 1
            mc.setAttr(n + ".translateY", float(counter["n"]))
            mc.getAttr(n + ".worldMatrix[0]")

        self._assert_defers_during_file_read(mk, trigger, MPyTransformMatrix)


# ===========================================================================
# C5 -- every own-path compute type pre-sizes ARRAY user outputs
# ===========================================================================


class TestOwnPathComputeArrayOutputPreSize(unittest.TestCase):
    """The base mPyNode pre-seeds every USER output into ``compute_locals``
    BEFORE running the expression; an ARRAY output gets a PRE-SIZED
    ``(N, ...)`` numpy buffer (``N`` = connected element span) so the user can
    slice-assign in place -- ``self.outVec[i] = v`` (base contract C5,
    ``output_defaults.output_default``). Every type that re-implements its own
    compute path must do the same.

    Before this fix these types seeded the slot with a bare ``None``
    (``_compute_locals.setdefault(name, None)``), so ``self.outVec[0] = v``
    raised ``TypeError: 'NoneType' object does not support item assignment``.
    That error is swallowed by the shared benign policy and the output plug
    silently keeps its default -- the same class of "inherited feature does
    not actually work on the subclass" bug the audit exists to remove.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _assert_array_output_presized(self, node_name):
        # Two locators give logical indices [0, 1], so the pre-sized buffer is
        # (2, 3). The expression slice-assigns [0]; [1] must keep its seeded
        # default, proving the buffer is a real (N, 3), not a one-off.
        loc0 = mc.spaceLocator(name="c5loc0")[0]
        loc1 = mc.spaceLocator(name="c5loc1")[0]
        mc.connectAttr(node_name + ".outVec[0]", loc0 + ".translate")
        mc.connectAttr(node_name + ".outVec[1]", loc1 + ".translate")
        # pull the DESTINATION plugs: in mayapy a getAttr on a connected
        # source output returns the cached datablock value without
        # re-evaluating. The destination is the reliable pull.
        v0 = mc.getAttr(loc0 + ".translate")[0]
        v1 = mc.getAttr(loc1 + ".translate")[0]
        self.assertEqual(
            tuple(round(c, 4) for c in v0), (1.0, 2.0, 3.0),
            "array output element [0] was not written by the in-place "
            "slice-assign -- C5 pre-size missing (self.outVec was None)",
        )
        self.assertEqual(
            tuple(round(c, 4) for c in v1), (0.0, 0.0, 0.0),
            "array output element [1] should be the seeded (N, 3) default",
        )

    def test_mesh_presizes_array_output(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="mArr")
        p.add_output_attr("outVec", "vector", is_array=True)
        p.set_compute_expression("self.outVec[0] = [1.0, 2.0, 3.0]\n")
        self._assert_array_output_presized(p.get_name())

    def test_nurbs_curve_presizes_array_output(self):
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve

        p = MPyNurbsCurve.create(name="cArr")
        p.add_output_attr("outVec", "vector", is_array=True)
        p.set_compute_expression("self.outVec[0] = [1.0, 2.0, 3.0]\n")
        self._assert_array_output_presized(p.get_name())

    def test_nurbs_surface_presizes_array_output(self):
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface

        p = MPyNurbsSurface.create(name="sArr")
        p.add_output_attr("outVec", "vector", is_array=True)
        p.set_compute_expression("self.outVec[0] = [1.0, 2.0, 3.0]\n")
        self._assert_array_output_presized(p.get_name())

    def test_file_presizes_array_output(self):
        from mpynode.wrappers.mpy_file import MPyFile

        p = MPyFile.create(name="fArr", seed_defaults=False)
        p.add_output_attr("outVec", "vector", is_array=True)
        p.set_compute_expression("self.outVec[0] = [1.0, 2.0, 3.0]\n")
        self._assert_array_output_presized(p.get_name())


# ===========================================================================
# C2 -- every own-path compute type seeds USER inputs DENSELY
# ===========================================================================


class TestOwnPathComputeDenseInputSeeding(unittest.TestCase):
    """The base mPyNode seeds every USER input DENSELY into the expression
    namespace so ``self.<input>`` is a numpy array / primitive -- NOT the
    ragged live plug proxy. A vector-array input read straight off the plug
    yields a sequence of ``(logical_index, value)`` tuples, so
    ``np.asarray(self.<in>)`` raises "setting an array element with a sequence
    ... inhomogeneous shape" (the exact class of bug that motivated this audit).
    Every type that re-implements its own compute
    path must seed inputs the same way (C2).
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_locator_seeds_dense_vector_array_input(self):
        """``mPyLocator.evaluateDrawItems`` reads user inputs but historically
        never merged them into ``compute_locals`` -- ``self.pts`` fell through
        to the live plug proxy, so ``np.asarray(self.pts)`` raised on a ragged
        shape. It must seed the dense read the base contract provides."""
        import maya.api.OpenMaya as om
        import numpy as np

        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="locDense")
        loc.add_input_attr("pts", "vector", is_array=True)
        n = loc.get_name()
        for i, v in enumerate([(1, 2, 3), (4, 5, 6), (7, 8, 9)]):
            mc.setAttr("%s.pts[%d]" % (n, i), v[0], v[1], v[2], type="double3")
        loc.set_compute_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawPoints\n"
            # C2: self.pts must be a dense (N, 3) numpy array. Off the raw
            # plug it is a ragged (index, value) proxy -> this raises.
            "arr = np.asarray(self.pts, dtype=np.float32)\n"
            "self.draw = DrawPoints(arr, color=(1, 1, 1))\n"
        )
        sel = om.MSelectionList()
        sel.add(n)
        mpx = om.MFnDependencyNode(sel.getDependNode(0)).userNode()
        cmds = mpx.evaluateDrawItems(time_value=0.0)["commands"]
        self.assertEqual(
            [c["slot"] for c in cmds], ["points"],
            "locator expression failed -- self.pts was not seeded as a dense "
            "numpy array (C2), so np.asarray(self.pts) raised",
        )
        np.testing.assert_allclose(
            cmds[0]["buffer"]["positions"],
            [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            atol=1e-5,
        )

    def test_file_seeds_dense_vector_array_input(self):
        """``mPyFile`` reads user inputs through the thread-safe data-block
        reader (``read_user_inputs_dict_from_datablock``) so the expression is
        valid on the Hypershade swatch / Arnold worker thread. That reader
        historically SKIPPED array + non-scalar inputs, so ``self.pts`` fell
        through to the (worker-unsafe, and ragged) live plug -- the same C2
        divergence. It must read arrays densely off the data block."""
        import numpy as np

        from mpynode.wrappers.mpy_file import MPyFile

        p = MPyFile.create(name="fDense", seed_defaults=False)
        p.add_input_attr("pts", "vector", is_array=True)
        p.add_output_attr("sumVec", "vector")
        n = p.get_name()
        for i, v in enumerate([(1, 2, 3), (4, 5, 6), (7, 8, 9)]):
            mc.setAttr("%s.pts[%d]" % (n, i), v[0], v[1], v[2], type="double3")
        p.set_compute_expression(
            "import numpy as np\n"
            # C2: self.pts must be a dense (N, 3) numpy array read off the
            # data block. Skipped -> falls through to the ragged live plug.
            "arr = np.asarray(self.pts, dtype=float)\n"
            "self.sumVec = arr.sum(axis=0)\n"
        )
        # Pull through a DESTINATION plug to force the node to compute.
        loc = mc.spaceLocator(name="fDenseLoc")[0]
        mc.connectAttr(n + ".sumVec", loc + ".translate")
        v = mc.getAttr(loc + ".translate")[0]
        self.assertEqual(
            tuple(round(c, 4) for c in v), (12.0, 15.0, 18.0),
            "mPyFile did not seed self.pts as a dense numpy array off the "
            "data block (C2) -- the vector-array sum did not reach the output",
        )

    def test_transform_seeds_dense_vector_array_input(self):
        """``mPyTransform._run_expression`` (api1 own path) built its
        ``compute_locals`` from curated internals + array outputs but did NOT
        seed user inputs, so ``self.pts`` fell through to the ragged live plug
        proxy -- the same C2 divergence. Must seed user inputs densely."""
        from mpynode.wrappers.mpy_transform import MPyTransform

        t = MPyTransform.create(name="txDense")
        n = t.get_name()
        t.add_input_attr("pts", "vector", is_array=True)
        for i, v in enumerate([(1, 2, 3), (4, 5, 6), (7, 8, 9)]):
            mc.setAttr("%s.pts[%d]" % (n, i), v[0], v[1], v[2], type="double3")
        t.set_compute_expression(
            "import numpy as np\n"
            # C2: self.pts must be a dense (N, 3) numpy array.
            "arr = np.asarray(self.pts, dtype=float)\n"
            "m = np.eye(4)\n"
            "m[3, :3] = arr.sum(axis=0)\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n"
        )
        # Force compute via a worldMatrix query; translation is flat 12/13/14.
        wm = mc.getAttr(n + ".worldMatrix[0]") or []
        self.assertEqual(len(wm), 16, "worldMatrix[0] should be 16 floats")
        self.assertEqual(
            (round(wm[12], 4), round(wm[13], 4), round(wm[14], 4)),
            (12.0, 15.0, 18.0),
            "MPyTransform did not seed self.pts as a dense numpy array (C2) "
            "-- the vector-array sum did not reach the output matrix",
        )

    def test_deformer_seeds_dense_vector_array_input(self):
        """The deformer family (mPyDeformer /
        mPyBlendShape / mPySkinCluster) computes through the shared api1
        ``run_generic_compute``, which built ``compute_locals`` from curated
        internals + array outputs but did NOT seed user inputs -- ``self.pts``
        fell through to the ragged live plug proxy (C2). It must seed user
        inputs densely so ``np.asarray(self.pts)`` works inside a deform."""
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="defDenseP", w=2, h=2, sx=2, sy=2)[0]
        d = MPyDeformer.create_on(plane)
        n = d.get_name()
        d.add_input_attr("pts", "vector", is_array=True)
        for i, v in enumerate([(1, 2, 3), (4, 5, 6), (7, 8, 9)]):
            mc.setAttr("%s.pts[%d]" % (n, i), v[0], v[1], v[2], type="double3")
        d.set_compute_expression(
            "import numpy as np\n"
            # C2: self.pts must be a dense (N, 3) numpy array; the ragged live
            # plug proxy raises here and the deform silently no-ops.
            "arr = np.asarray(self.pts, dtype=float)\n"
            "shift = float(arr.sum())\n"  # 45.0
            "mesh = self.outputGeometry[0]\n"
            "p = mesh.getPoints()\n"
            "p[:, 1] += shift\n"
            "mesh.setPoints(p)\n"
        )
        # Force the deform + read a vertex Y (stays 0 if the expression raised).
        y = mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)[1]
        self.assertAlmostEqual(
            y, 45.0, places=3,
            msg="mPyDeformer did not seed self.pts as a dense numpy array (C2) "
                "-- the vector-array sum did not reach the deformed vertices",
        )

    def test_iksolver_seeds_dense_vector_array_input(self):
        """``mPyIkSolver`` solves through ``compute_ik_user_solve`` (api1),
        whose ``compute_locals`` carried only the curated IK internals --
        a user input read as ``self.pts`` fell through to the ragged live plug
        proxy (C2). The solve path must seed user inputs densely too. We call
        the real solve entry point directly (Maya's IK graph would not tick it
        under a plain ``setAttr``), mirroring the syntax-error test's shim."""
        import maya.OpenMaya as om1

        from mpynode._api1 import helpers
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        s = MPyIkSolver.create(name="ikDense")
        n = s.get_name()
        s.add_input_attr("pts", "vector", is_array=True)
        for i, v in enumerate([(1, 2, 3), (4, 5, 6), (7, 8, 9)]):
            mc.setAttr("%s.pts[%d]" % (n, i), v[0], v[1], v[2], type="double3")
        mc.setAttr(
            n + "._computeSource",
            # C2: self.pts must be a dense (N, 3) numpy array; a ragged proxy
            # raises here and aborts the solve. Stash the sum in a local
            # matrix element to read it back from local_matrices.
            "import numpy as np\n"
            "arr = np.asarray(self.pts, dtype=float)\n"
            "m = np.eye(4)\n"
            "m[3, 0] = float(arr.sum())\n"
            "self.local_matrices[0] = m\n",
            type="string",
        )

        sel = om1.MSelectionList()
        sel.add(n)
        node_obj = om1.MObject()
        sel.getDependNode(0, node_obj)

        class _Shim(object):
            def thisMObject(self_inner):
                return node_obj

        local_mats, _world, _gr, _gt, _gs = helpers.compute_ik_user_solve(
            _Shim(),
            joints=["j"],  # length 1 -> matrix buffers are 1-slot lists
            end_effector=[0.0, 0.0, 0.0],
            pole_vector=[0.0, 0.0, 0.0],
            twist=0.0,
        )
        self.assertIsNotNone(
            local_mats,
            "mPyIkSolver solve failed -- self.pts was not seeded dense (C2), "
            "so np.asarray(self.pts) raised and aborted the solve",
        )
        self.assertIsNotNone(local_mats[0], "local_matrices[0] was not written")
        import numpy as _np
        self.assertAlmostEqual(
            float(_np.asarray(local_mats[0])[3, 0]), 45.0, places=3,
            msg="mPyIkSolver did not seed self.pts as a dense numpy array (C2) "
                "-- the vector-array sum did not reach local_matrices",
        )


if __name__ == "__main__":
    unittest.main()
