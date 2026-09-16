"""mPyIkSolver deterministic lowering (nd_lower.try_lower_iksolver).

The solver's doSolve() scaffold already owns the whole solve FRAME in C++ (joint
chain walk, bind-offset capture, gate-mix + offsetParentMatrix writeback); the
PORT region only ever had to FILL a fixed set of C++ locals. This binds that
surface to nd:: values so the Python solve expression lowers with no AI porter.

The read surface is a list of DICTS (``self.joints[j]["world_matrix"]``), which
the transpiler has no type for -- so joint reads are AST-rewritten into synthetic
per-channel self-attrs bound to stacked nd arrays.
"""

from __future__ import annotations

import json
import os
import unittest

from mpynode.native.compiler import nd_lower
from mpynode.native.compiler.errors import UnsupportedSpec
from tests import _paths


_TEMPLATE = os.path.join(
    _paths.ROOT,
    "templates", "MPyIkSolver", "Two Bone IK", "template.mpn")


def _spec(compute, **kw):
    spec = {"compute": compute, "inputs": {}, "outputs": {}}
    spec.update(kw)
    return spec


_MINIMAL = (
    "import numpy as np\n"
    "if self.__LEN__ >= 2:\n"
    "    self.world_matrices[0] = np.asarray("
    "self.joints[0]['world_matrix'], float).reshape(4, 4)\n"
)


def _src(body):
    return "import numpy as np\n" + body


class TestJointReadRewrite(unittest.TestCase):
    def test_direct_channel_read(self):
        out, chans = nd_lower._rewrite_ik_joint_reads(
            "w = self.joints[0]['world_matrix']\n")
        self.assertEqual(chans, {"world_matrix"})
        self.assertIn("self.__ndik_joints_world_matrix_[0]", out)

    def test_alias_channel_read(self):
        """`joints = self.joints` is an alias; the binding itself drops out."""
        out, chans = nd_lower._rewrite_ik_joint_reads(
            "joints = self.joints\n"
            "p = joints[1]['world_position']\n")
        self.assertEqual(chans, {"world_position"})
        self.assertIn("self.__ndik_joints_world_position_[1]", out)
        self.assertNotIn("joints = self.joints", out)

    def test_joint_dict_alias(self):
        """`jd = joints[i]` re-materialises the index at each channel use."""
        out, chans = nd_lower._rewrite_ik_joint_reads(
            "joints = self.joints\n"
            "jd = joints[2]\n"
            "m = jd['matrix']\n")
        self.assertEqual(chans, {"matrix"})
        self.assertIn("self.__ndik_joints_matrix_[2]", out)

    def test_len_becomes_numjoints(self):
        out, _chans = nd_lower._rewrite_ik_joint_reads(
            "joints = self.joints\n"
            "n = len(joints)\n")
        self.assertIn("self.__ndik_numjoints_", out)
        self.assertNotIn("len(", out)

    def test_unsupported_channel_rejects(self):
        """`rotation` (xform ro=True DEGREES) and `name` (a string) have no
        scaffold local -- reading either drops the whole compute to the porter."""
        for ch in ("rotation", "name"):
            with self.assertRaises(UnsupportedSpec):
                nd_lower._rewrite_ik_joint_reads(
                    "x = self.joints[0][%r]\n" % ch)

    def test_bare_joints_use_rejects(self):
        """Anything outside the channel surface (iteration, pass-through)."""
        with self.assertRaises(UnsupportedSpec):       # bare pass-through
            nd_lower._rewrite_ik_joint_reads(
                "joints = self.joints\n"
                "other = joints\n")
        with self.assertRaises(UnsupportedSpec):       # iteration
            nd_lower._rewrite_ik_joint_reads(
                "joints = self.joints\n"
                "for j in joints:\n"
                "    pass\n")
        with self.assertRaises(UnsupportedSpec):       # not via an alias either
            nd_lower._rewrite_ik_joint_reads("n = len(self.joints[0])\n")

    def test_dead_alias_binding_is_dropped(self):
        """An UNUSED `x = self.joints` is dead code -- the read is pure, so
        dropping the binding is safe. Any actual USE is still rejected above."""
        out, chans = nd_lower._rewrite_ik_joint_reads("x = self.joints\n")
        self.assertEqual(chans, set())
        self.assertNotIn("joints", out)


class TestNestedDefHoist(unittest.TestCase):
    def test_free_def_is_hoisted(self):
        body, helpers = nd_lower._hoist_nested_defs(
            "if True:\n"
            "    def rot(a):\n"
            "        return a * 2.0\n"
            "    x = rot(3.0)\n")
        self.assertIsNotNone(helpers)
        self.assertIn("def rot(a):", helpers)
        self.assertNotIn("def rot", body)

    def test_capturing_def_is_left_in_place(self):
        """A def closing over a block local is NOT a free function; leaving it
        in place makes the transpiler reject -- the safe direction."""
        body, helpers = nd_lower._hoist_nested_defs(
            "k = 2.0\n"
            "def scale(a):\n"
            "    return a * k\n"
            "x = scale(3.0)\n")
        self.assertIsNone(helpers)
        self.assertIn("def scale", body)

    def test_emptied_block_gets_a_pass(self):
        """Lifting the ONLY statement out of a block must not leave an empty
        body (an invalid AST that would fail to unparse/reparse)."""
        body, helpers = nd_lower._hoist_nested_defs(
            "if True:\n"
            "    def f(a):\n"
            "        return a\n")
        self.assertIsNotNone(helpers)
        self.assertIn("pass", body)
        compile(body, "<test>", "exec")   # must still be valid Python


class TestSolverLowering(unittest.TestCase):
    def test_minimal_world_matrix_write_lowers(self):
        src = _src(
            "if len(self.joints) >= 1:\n"
            "    self.world_matrices[0] = np.asarray("
            "self.joints[0]['world_matrix'], float).reshape(4, 4)\n")
        lines = nd_lower.try_lower_iksolver(_spec(src))
        self.assertIsNotNone(lines, "a plain world-matrix write must lower")
        joined = "\n".join(lines)
        self.assertIn("bindWorld[_j](_r, _c)", joined)  # stacked read
        self.assertIn("outWorldSet[_j] = 1;", joined)   # scatter + flag

    def test_local_matrix_sink_lowers(self):
        src = _src(
            "self.local_matrices[0] = np.asarray("
            "self.joints[0]['matrix'], float).reshape(4, 4)\n")
        lines = nd_lower.try_lower_iksolver(_spec(src))
        self.assertIsNotNone(lines)
        joined = "\n".join(lines)
        self.assertIn("jointLocal[_j](_r, _c)", joined)
        self.assertIn("outLocalSet[_j] = 1;", joined)

    def test_scalar_gate_broadcasts(self):
        src = _src(
            "self.world_matrices[0] = np.eye(4)\n"
            "self.apply_rotate = True\n"
            "self.apply_translate = False\n")
        joined = "\n".join(nd_lower.try_lower_iksolver(_spec(src)))
        self.assertIn("applyRotate[_j] = _g;", joined)
        self.assertIn("applyTranslate[_j] = _g;", joined)

    def test_list_gate_is_per_joint(self):
        src = _src(
            "self.world_matrices[0] = np.eye(4)\n"
            "self.apply_rotate = np.array([1.0, 0.0, 1.0])\n")
        joined = "\n".join(nd_lower.try_lower_iksolver(_spec(src)))
        self.assertIn("_j < numJoints && _j < _n", joined)

    def test_end_effector_pole_twist_bind(self):
        src = _src(
            "t = np.asarray(self.end_effector, float) "
            "+ np.asarray(self.pole_vector, float) * float(self.twist)\n"
            "m = np.eye(4)\n"
            "m[3, :3] = t\n"
            "self.world_matrices[0] = m\n")
        joined = "\n".join(nd_lower.try_lower_iksolver(_spec(src)))
        self.assertIn("{endEffector.x, endEffector.y, endEffector.z}", joined)
        self.assertIn("{poleVector.x, poleVector.y, poleVector.z}", joined)
        self.assertIn("(double)(twist);", joined)

    def test_no_matrix_sink_rejects(self):
        """Gates alone drive nothing -- there is no solve to lower."""
        src = _src("self.apply_rotate = True\n")
        self.assertIsNone(nd_lower.try_lower_iksolver(_spec(src)))

    def test_unknown_self_attr_rejects(self):
        src = _src(
            "self.world_matrices[0] = np.eye(4) * float(self.nope)\n")
        self.assertIsNone(nd_lower.try_lower_iksolver(_spec(src)))

    def test_empty_compute_is_none(self):
        self.assertIsNone(nd_lower.try_lower_iksolver(_spec("")))
        self.assertIsNone(nd_lower.try_lower_iksolver(_spec("   \n")))

    def test_user_input_binds(self):
        """A declared user INPUT binds to the SAME in_<member> local the AI
        porter path reads, so both paths see identical C++."""
        src = _src(
            "self.world_matrices[0] = np.eye(4) * float(self.blend)\n")
        spec   = _spec(src, inputs={"blend": {"type": "double"}})
        joined = "\n".join(nd_lower.try_lower_iksolver(spec))
        self.assertIn("in_blend", joined)


class TestTwoBoneIkTemplate(unittest.TestCase):
    """The shipped template is the acceptance bar: it must lower, and the
    generated C++ must carry NO port region (i.e. no AI porter round-trip)."""

    def setUp(self):
        if not os.path.exists(_TEMPLATE):
            self.skipTest("two_bone_ik template not present")
        with open(_TEMPLATE) as fh:
            self.source = json.load(fh)["data"]["expression"]

    def test_template_lowers(self):
        lines = nd_lower.try_lower_iksolver(_spec(self.source))
        self.assertIsNotNone(
            lines, "the shipped two_bone_ik template must lower deterministically")

    def test_generated_cpp_has_no_port_region(self):
        from mpynode.native.compiler import emit_iksolver
        from mpynode.native.compiler.spec_model import PORT_BEGIN

        spec = _spec(self.source,
                     suggested={"class_name": "TwoBoneIk",
                                "node_type_name": "twoBoneIk",
                                "type_id":        "0x00136000",
                                "mpx_base": "MPxIkSolverNode"},
                     source_node="twoBoneIk1", mpy_type="mPyIkSolver")
        cpp = emit_iksolver._generate_iksolver_cpp(spec)
        self.assertNotIn(PORT_BEGIN, cpp)
        self.assertIn("nd::Array", cpp)     # lowered math present
        self.assertIn("namespace nd", cpp)  # nd_runtime.h inlined

    def test_unlowerable_solver_keeps_the_port_region(self):
        """Zero regression: a compute outside the lowerable subset still gets
        the AI-porter scaffold exactly as before."""
        from mpynode.native.compiler import emit_iksolver
        from mpynode.native.compiler.spec_model import PORT_BEGIN

        spec = _spec("for jd in self.joints:\n    pass\n",
                     suggested={"class_name": "Weird",
                                "node_type_name": "weirdSolver",
                                "type_id":        "0x00136001",
                                "mpx_base": "MPxIkSolverNode"},
                     source_node="weird1", mpy_type="mPyIkSolver")
        cpp = emit_iksolver._generate_iksolver_cpp(spec)
        self.assertIn(PORT_BEGIN, cpp)


if __name__ == "__main__":
    unittest.main()
