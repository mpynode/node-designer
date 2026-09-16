"""Expression namespace contract + numpy vector type contract

Consolidated from: test_phase27_1.py, test_phase16_5.py.
"""

from __future__ import annotations

# ===================== from test_phase27_1.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase27_1():
    standalone_init()


# ===========================================================================
# Namespace plumbing: single dict, no auto-imports, listcomps work.
# ===========================================================================


class TestSingleNamespaceExec(unittest.TestCase):
    """Exec_with_profile_watch now takes a single namespace dict, not
    separate globals + locals."""

    def test_signature_is_single_namespace(self):
        import inspect

        from mpynode._common.compute.expression import exec_with_profile_watch

        params = list(inspect.signature(exec_with_profile_watch).parameters)
        # params are (code, namespace); they were exec_globals + exec_locals.
        self.assertEqual(params[0], "code")
        self.assertEqual(params[1], "namespace")
        self.assertNotIn("exec_globals", params)
        self.assertNotIn("exec_locals", params)

    def test_exec_writes_back_to_namespace(self):
        from mpynode._common.compute.expression import (
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression("y = 7 * 6")
        ns: dict = {}
        ok = exec_with_profile_watch(code, ns)
        self.assertTrue(ok)
        self.assertEqual(ns["y"], 42)

    def test_listcomp_sees_input_value(self):
        """The pre-Phase-27 separate globals/locals split caused
        listcomps to NOT see locals. Single namespace fixes that."""
        from mpynode._common.compute.expression import (
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression("out = [seed * i for i in range(5)]")
        ns: dict = {"seed": 7}
        ok = exec_with_profile_watch(code, ns)
        self.assertTrue(ok)
        self.assertEqual(ns["out"], [0, 7, 14, 21, 28])


# ===========================================================================
# No auto-imported modules.
# ===========================================================================


class TestNoAutoImports(unittest.TestCase):
    """Contract: only ``__builtins__`` is auto-injected.
    Users must explicitly ``import numpy as np`` etc."""

    def test_bare_np_raises_NameError(self):
        from mpynode._common.compute.expression import (
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression("y = np.zeros(3)")
        ns:       dict = {}
        captured: list[str] = []
        ok = exec_with_profile_watch(
            code, ns, on_error=lambda msg: captured.append(msg)
        )
        self.assertFalse(ok)
        self.assertEqual(len(captured), 1)
        self.assertIn("'np' is not defined", captured[0])

    def test_bare_math_raises_NameError(self):
        from mpynode._common.compute.expression import (
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression("y = math.pi")
        ns:       dict = {}
        captured: list[str] = []
        ok = exec_with_profile_watch(
            code, ns, on_error=lambda msg: captured.append(msg)
        )
        self.assertFalse(ok)
        self.assertIn("'math' is not defined", captured[0])

    def test_bare_cmds_raises_NameError(self):
        from mpynode._common.compute.expression import (
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression("y = cmds.ls()")
        ns:       dict = {}
        captured: list[str] = []
        ok = exec_with_profile_watch(
            code, ns, on_error=lambda msg: captured.append(msg)
        )
        self.assertFalse(ok)
        self.assertIn("'cmds' is not defined", captured[0])

    def test_explicit_import_numpy_works(self):
        from mpynode._common.compute.expression import (
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression("import numpy as np\ny = np.zeros(3).tolist()")
        ns: dict = {}
        ok = exec_with_profile_watch(code, ns)
        self.assertTrue(ok)
        self.assertEqual(ns["y"], [0.0, 0.0, 0.0])

    def test_builtins_still_available(self):
        """``__builtins__`` must remain so ``len``, ``range``, ``dict``,
        ``list``, ``print`` etc. work without import."""
        from mpynode._common.compute.expression import (
            build_exec_namespace,
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression(
            "out_len = len([1, 2, 3])\n"
            "out_range = list(range(3))\n"
            "out_dict = dict(a=1, b=2)"
        )
        ns = build_exec_namespace()  # __builtins__ only
        ok = exec_with_profile_watch(code, ns)
        self.assertTrue(ok)
        self.assertEqual(ns["out_len"],   3)
        self.assertEqual(ns["out_range"], [0, 1, 2])
        self.assertEqual(ns["out_dict"],  {"a": 1, "b": 2})


# ===========================================================================
# build_exec_namespace shape.
# ===========================================================================


class TestBuildExecNamespace(unittest.TestCase):
    def test_only_builtins_in_default_namespace(self):
        from mpynode._common.compute.expression import build_exec_namespace

        ns = build_exec_namespace()
        self.assertIn("__builtins__", ns)
        self.assertNotIn("np",   ns)
        self.assertNotIn("math", ns)
        self.assertNotIn("cmds", ns)

    def test_extras_overlay_applied(self):
        from mpynode._common.compute.expression import build_exec_namespace

        ns = build_exec_namespace(extras={"foo": 42})
        self.assertEqual(ns["foo"], 42)


# ===========================================================================
# SelfProxy: stored vars accessed via self.X
# ===========================================================================


class TestSelfProxyStoredVars(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_self_X_reads_stored_var(self):
        """Self.X reads the value injected by the bridge."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="self_read")
        n.add_variable("greet", "hello")
        n.add_output_attr("out", "string")
        n.set_compute_expression("self.out = self.greet")
        result = mc.getAttr(n.get_name() + ".out")
        self.assertEqual(result, "hello")

    def test_self_X_writes_user_storage_and_persists(self):
        """Self.X =... writes to user storage; bridge commits via diff;
        subsequent computes see the updated value."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="self_write")
        n.add_variable("counter", 0)
        n.add_input_attr("trigger", "float")
        n.add_output_attr("out", "int")
        n.set_compute_expression("self.counter = self.counter + 1\nself.out = self.counter")
        mc.setAttr(n.get_name() + ".trigger", 1.0)
        first = mc.getAttr(n.get_name() + ".out")
        self.assertEqual(first, 1)
        self.assertEqual(n.get_variables()["counter"], 1)

        mc.setAttr(n.get_name() + ".trigger", 2.0)
        second = mc.getAttr(n.get_name() + ".out")
        self.assertEqual(second, 2)
        self.assertEqual(n.get_variables()["counter"], 2)

    def test_self_supports_brand_new_storage_keys(self):
        """User can create a new stored var by writing self.X = value
        even if the var wasn't pre-declared."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="self_new")
        n.add_input_attr("trigger", "float")
        n.add_output_attr("dummy", "float")
        n.set_compute_expression("self.brand_new = 99\ndummy = 0.0")
        mc.setAttr(n.get_name() + ".trigger", 1.0)
        mc.getAttr(n.get_name() + ".dummy")  # trigger compute
        stored = n.get_variables()
        self.assertEqual(stored.get("brand_new"), 99)


# ===========================================================================


# ===================== from test_phase16_5.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase16_5():
    standalone_init()


# ===========================================================================
# mPyConstraint preset inputs are numpy
# ===========================================================================


class TestConstraintInputsAreNumpy(unittest.TestCase):
    """Each of the 5 preset constraint inputs (or 4 vectors +
    1 scalar) arrives in the user expression with the right type."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _probe_input_type(self, input_name: str) -> str:
        """Create an mPyConstraint, set an expression that captures
        ``type(self.<input_name>).__name__`` to a string output, force eval,
        return the type name. preset constraint inputs are
        accessed via ``self.X``."""
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        c = MPyConstraint.create(name=f"probe_{input_name}")
        c.add_output_attr("type_name", "string")
        c.set_compute_expression(f"self.type_name = type(self.{input_name}).__name__")

        # setAttr on any preset input makes setDependentsDirty mark the user
        # outputs dirty, so the next getAttr computes. Without the nudge the
        # output stays clean and returns "".
        mc.setAttr(c.get_name() + ".targetTranslate", 0.0, 0.0, 0.0, type="double3")

        return mc.getAttr(c.get_name() + ".type_name") or ""

    def test_targetTranslate_is_ndarray(self):
        self.assertEqual(self._probe_input_type("targetTranslate"), "ndarray")

    def test_targetRotate_is_ndarray(self):
        self.assertEqual(self._probe_input_type("targetRotate"), "ndarray")

    def test_restTranslate_is_ndarray(self):
        self.assertEqual(self._probe_input_type("restTranslate"), "ndarray")

    def test_restRotate_is_ndarray(self):
        self.assertEqual(self._probe_input_type("restRotate"), "ndarray")

    def test_targetWeight_is_python_float(self):
        """Scalar should stay as Python float (not np.float64)."""
        self.assertEqual(self._probe_input_type("targetWeight"), "float")

    def test_constraint_supports_inline_vector_math(self):
        """The UX win: targetTranslate * weight + restTranslate * (1-weight)
        works directly without manual zip/loop."""
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        src = mc.polyCube(name="srcCube")[0]
        dst = mc.polyCube(name="dstCube")[0]
        c   = MPyConstraint.create(name="weightedCstr")
        c.add_output_attr("out", "vector")
        # numpy expression reading preset inputs via self.X.
        c.set_compute_expression(
            "constrained = self.targetTranslate * self.targetWeight + "
            "self.restTranslate * (1 - self.targetWeight)\n"
            "self.out = constrained"
        )
        mc.connectAttr(src + ".translate", c.get_name() + ".targetTranslate", force=True)
        mc.connectAttr(c.get_name() + ".out", dst + ".translate", force=True)
        mc.setAttr(src + ".translate", 10.0, 0.0, 0.0, type="double3")
        mc.setAttr(c.get_name() + ".restTranslate", 0.0, 0.0, 0.0, type="double3")

        # Half-weight blend: driven should be at (5, 0, 0)
        mc.setAttr(c.get_name() + ".targetWeight", 0.5)
        ws = mc.xform(dst, q=True, ws=True, t=True)
        self.assertAlmostEqual(ws[0], 5.0, places=4)
        self.assertAlmostEqual(ws[1], 0.0, places=4)
        self.assertAlmostEqual(ws[2], 0.0, places=4)

        # Full weight: driven matches source
        mc.setAttr(c.get_name() + ".targetWeight", 1.0)
        ws = mc.xform(dst, q=True, ws=True, t=True)
        self.assertAlmostEqual(ws[0], 10.0, places=4)


# ===========================================================================
# Other nodes already used numpy \u2014 pin the existing behavior
# ===========================================================================


class TestOtherNodesAlreadyNumpy(unittest.TestCase):
    """Pin the existing numpy-correctness so a future change can't regress
    these inputs to Python list."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_iksolver_end_effector_is_ndarray(self):
        """MPyIkSolver wraps end_effector / pole_vector via np.asarray. Pin via
        inspect (the ndarray wrapping lives in the SelfProxy compute_locals)."""
        import inspect

        from mpynode._api1.helpers import compute_ik_doSolve, compute_ik_user_solve

        src = inspect.getsource(compute_ik_user_solve)
        self.assertIn('"end_effector": np.asarray(end_effector', src)
        self.assertIn('"pole_vector": np.asarray(pole_vector', src)

        src2 = inspect.getsource(compute_ik_doSolve)
        # world_position comes from the offset-free BIND world matrix, a
        # float64 ndarray via _np4, not a raw cmds.xform list; rotation stays
        # an explicit float64 ndarray. Pin both.
        self.assertIn('"world_position": world_mat[3, :3]', src2)
        self.assertIn("np.array(local_rot, dtype=np.float64)", src2)
        from mpynode._api1.helpers import _np4
        self.assertIn("dtype=np.float64", inspect.getsource(_np4))

    def test_mpynode_user_vector_input_is_ndarray(self):
        """MPyNode reads user-added vector inputs via read_plug_value
        which returns numpy. Pin it via the helper source."""
        import inspect

        from mpynode._api2.helpers import read_plug_value

        src = inspect.getsource(read_plug_value)
        self.assertIn("return np.array", src)
        self.assertIn("dtype=np.float64", src)


# ===========================================================================
# Demo regression
# ===========================================================================


def setUpModule():
    _setUpModule__phase27_1()
    _setUpModule__phase16_5()


if __name__ == "__main__":
    import unittest
    unittest.main()
