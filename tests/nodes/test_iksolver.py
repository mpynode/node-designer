"""MPyIkSolver + 2 demos with VISIBLE joints + visible target cubes.

The IK solver is hard to verify without visible scene objects \u2014 the
IK system may skip evaluation if the chain doesn't lead anywhere
visible. Each test attaches a visible cube to the IK handle so Maya
forces the doSolve callback to run.
"""

from __future__ import annotations

import math
import os
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestMPyIkSolverBasics(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_node_type_registered(self):
        self.assertIn("mPyIkSolver", mc.allNodeTypes() or [])

    def test_create(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        s = MPyIkSolver.create(name="myIk")
        self.assertTrue(mc.objExists("myIk"))
        self.assertEqual(mc.nodeType("myIk"), "mPyIkSolver")

    def test_find_solver_creates_if_missing(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        # No iksolver in scene yet.
        self.assertEqual(mc.ls(type="mPyIkSolver"), [])
        s = MPyIkSolver.find_solver()
        self.assertTrue(mc.objExists(s.get_name()))
        # Calling find_solver again returns the same one.
        s2 = MPyIkSolver.find_solver()
        self.assertEqual(s.get_name(), s2.get_name())

    def test_internal_attrs(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        s = MPyIkSolver.create(name="ikInt")
        for plug in (
            "_computeSource", "_inputAttrs", "_outputAttrs",
            "_solverContextSnapshot", "debug_mode",
        ):
            self.assertTrue(
                mc.attributeQuery(plug, node=s.get_name(), exists=True),
                f"plug {plug!r} should exist on mPyIkSolver",
            )


class TestWalkJointChain(unittest.TestCase):
    """Pin the fix: walker correctly handles 3+ joint chains."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_walks_3_joint_chain(self):
        """3-joint chain: walk should return all 3 joints."""
        from mpynode._api1.helpers import _walk_joint_chain

        mc.select(clear=True)
        j0 = mc.joint(name="hip",   position=(0, 5, 0))
        j1 = mc.joint(name="knee",  position=(0, 0, 0))
        j2 = mc.joint(name="ankle", position=(0, -5, 0))

        chain = _walk_joint_chain(j0, "anyEffector")
        self.assertEqual(chain, [j0, j1, j2])

    def test_walks_2_joint_chain(self):
        from mpynode._api1.helpers import _walk_joint_chain

        mc.select(clear=True)
        j0 = mc.joint(name="root", position=(0, 0, 0))
        j1 = mc.joint(name="tip", position=(5, 0, 0))

        chain = _walk_joint_chain(j0, "anyEffector")
        self.assertEqual(chain, [j0, j1])

    def test_walks_single_joint(self):
        from mpynode._api1.helpers import _walk_joint_chain

        mc.select(clear=True)
        j     = mc.joint(name="lonely", position=(0, 0, 0))
        chain = _walk_joint_chain(j, "anyEffector")
        self.assertEqual(chain, [j])


class TestMPyIkSolverRecipe(unittest.TestCase):
    def test_recipe_registered_with_synthetics(self):
        from mpynode._common.util.recipes import get_recipe

        recipe = get_recipe("mPyIkSolver")
        self.assertIsNotNone(recipe)
        in_names = {e.name for e in recipe.inputs}
        for n in ("joints", "end_effector", "pole_vector", "twist"):
            self.assertIn(n, in_names)
        # ALL inputs are synthetic.
        for entry in recipe.inputs:
            self.assertEqual(
                entry.source_plug, "",
                f"{entry.name} should be SYNTHETIC for iksolver recipe",
            )
        # Two synthetic matrix outputs (local + world) + the three channel
        # gates; the legacy euler outputs are gone.
        out_names = {e.name for e in recipe.outputs}
        for n in ("local_matrices", "world_matrices",
                  "apply_rotate", "apply_translate", "apply_scale"):
            self.assertIn(n, out_names)
        self.assertNotIn("joint_rotations", out_names)
        for entry in recipe.outputs:
            self.assertEqual(entry.target_plug, "")
        # joints input exposes per-joint local + world matrices (for the solve).
        joints_in = next(e for e in recipe.inputs if e.name == "joints")
        self.assertIn("matrix", joints_in.children)
        self.assertIn("world_matrix", joints_in.children)


class TestMPyIkSolverMatrixSolve(unittest.TestCase):
    """The world_matrices path: a 2-bone aim solve drives the chain via
    offsetParentMatrix so the tip reaches the goal exactly, the joints' own
    rotate channels stay at rest, and jointOrient is preserved."""

    # the porter-friendly aim-frame solve shipped in the two_bone_ik template.
    AIM_EXPR = (
        "import math\n"
        "import numpy as np\n"
        "joints = self.joints\n"
        "if len(joints) >= 3:\n"
        "    p0 = np.asarray(joints[0]['world_position'], float)\n"
        "    p1 = np.asarray(joints[1]['world_position'], float)\n"
        "    p2 = np.asarray(joints[2]['world_position'], float)\n"
        "    W0 = np.asarray(joints[0]['world_matrix'], float).reshape(4, 4)\n"
        "    W1 = np.asarray(joints[1]['world_matrix'], float).reshape(4, 4)\n"
        "    B1 = float(np.linalg.norm(p1 - p0))\n"
        "    B2 = float(np.linalg.norm(p2 - p1))\n"
        "    target = np.asarray(self.end_effector, float)\n"
        "    gv = target - p0\n"
        "    reach = float(np.linalg.norm(gv))\n"
        "    if reach > 1e-9 and B1 > 1e-9 and B2 > 1e-9:\n"
        "        gd = gv / reach\n"
        "        d = min(max(reach, abs(B1 - B2) + 1e-4), B1 + B2 - 1e-4)\n"
        "        gp = p0 + d * gd\n"
        "        ref = p1 - p0\n"
        "        bn = np.cross(gd, ref)\n"
        "        if float(np.linalg.norm(bn)) < 1e-6:\n"
        "            bn = np.cross(gd, np.array([0.0, 0.0, 1.0]))\n"
        "        bn = bn / np.linalg.norm(bn)\n"
        "        ca = (B1 * B1 + d * d - B2 * B2) / (2.0 * B1 * d)\n"
        "        alpha = math.acos(max(-1.0, min(1.0, ca)))\n"
        "        def r3(ax, an):\n"
        "            x, y, z = ax[0], ax[1], ax[2]\n"
        "            c = math.cos(an); s = math.sin(an)\n"
        "            k = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])\n"
        "            return np.eye(3) + s * k + (1.0 - c) * (k @ k)\n"
        "        ud = r3(bn, alpha) @ gd; ud = ud / np.linalg.norm(ud)\n"
        "        kp = p0 + B1 * ud\n"
        "        ld = gp - kp; ld = ld / np.linalg.norm(ld)\n"
        "        def aim(w, rd, nd):\n"
        "            a = rd / np.linalg.norm(rd); b = nd / np.linalg.norm(nd)\n"
        "            v = np.cross(a, b); s = float(np.linalg.norm(v))\n"
        "            c = float(np.dot(a, b))\n"
        "            rct = np.eye(3) if s < 1e-9 else r3(v / s, -math.acos(max(-1.0, min(1.0, c))))\n"
        "            m = np.eye(4); m[:3, :3] = rct\n"
        "            return w @ m\n"
        "        self.world_matrices[0] = aim(W0, p1 - p0, ud)\n"
        "        self.world_matrices[1] = aim(W1, p2 - p1, ld)\n"
        "        self.apply_rotate = True\n"
        "        self.apply_translate = False\n"
        "        self.apply_scale = False\n"
    )

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _build_leg(self):
        if not mc.ls(type="mPyIkSolver"):
            mc.createNode("mPyIkSolver", name="mPyIkSolver1", skipSelect=True)
        mc.select(clear=True)
        hip   = mc.joint(position=(0.0, 5.0, 0.0),  name="ikHip")
        knee  = mc.joint(position=(0.0, 0.0, 0.0),  name="ikKnee")
        ankle = mc.joint(position=(0.0, -5.0, 0.0), name="ikAnkle")
        handle = mc.ikHandle(startJoint=hip, endEffector=ankle,
                             solver="mPyIkSolver", name="ikLeg")[0]
        solver = mc.ls(type="mPyIkSolver")[0]
        mc.setAttr(solver + "._computeSource", self.AIM_EXPR, type="string")
        return hip, knee, ankle, handle

    @staticmethod
    def _wpos(n):
        return mc.xform(n, q=True, ws=True, t=True)

    def _dist(self, a, b):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def test_tip_reaches_goal_and_channels_untouched(self):
        hip, knee, ankle, handle = self._build_leg()
        jo_before = mc.getAttr(hip + ".jointOrient")[0]
        for g in [(3.0, 1.0, 2.0), (4.0, 3.0, 0.0), (-2.0, 2.0, 4.0),
                  (5.0, 5.0, 5.0)]:
            mc.setAttr(handle + ".translate", *g, type="double3")
            mc.dgeval(ankle + ".worldMatrix[0]")
            err = self._dist(self._wpos(ankle), g)
            self.assertLess(err, 1e-3,
                            f"tip did not reach {g} (err={err:.3e})")
        # offsetParentMatrix does the work; the joints' own rotate stays at rest.
        for j in (hip, knee):
            for v in mc.getAttr(j + ".rotate")[0]:
                self.assertAlmostEqual(v, 0.0, places=5)
        # jointOrient is preserved across solves.
        jo_after = mc.getAttr(hip + ".jointOrient")[0]
        for a, b in zip(jo_before, jo_after):
            self.assertAlmostEqual(a, b, places=5)
        # offsetParentMatrix is actually driven (not identity).
        off = mc.getAttr(hip + ".offsetParentMatrix")
        self.assertGreater(sum(abs(off[i] - (1.0 if i in (0, 5, 10, 15) else 0.0))
                               for i in range(16)), 1e-6)

    def test_local_matrix_path_drives_offset_and_restores(self):
        # The LOCAL path: drive the knee with a parent-relative matrix (rotate
        # its rest frame), confirm offsetParentMatrix is driven while the joint's
        # own rotate stays 0; then unset it and confirm it restores to rest.
        hip, knee, ankle, handle = self._build_leg()
        local = ("import math, numpy as np\n"
                 "a = math.radians(30.0)\n"
                 "c = math.cos(a); s = math.sin(a)\n"
                 "rx = np.array([[1,0,0,0],[0,c,-s,0],[0,s,c,0],[0,0,0,1]], float)\n"
                 "Lk = np.asarray(self.joints[1]['matrix'], float).reshape(4, 4)\n"
                 "self.local_matrices[1] = rx @ Lk\n")
        solver = mc.ls(type="mPyIkSolver")[0]
        mc.setAttr(solver + "._computeSource", local, type="string")
        mc.setAttr(handle + ".translate", 0.0, 0.0, 0.0, type="double3")
        mc.dgeval(ankle + ".worldMatrix[0]")
        import numpy as np
        off = np.array(mc.getAttr(knee + ".offsetParentMatrix")).reshape(4, 4)
        self.assertFalse(np.allclose(off, np.eye(4)),
                         "local path did not drive knee offsetParentMatrix")
        for v in mc.getAttr(knee + ".rotate")[0]:
            self.assertAlmostEqual(v, 0.0, places=5)
        # unset (no slots) -> knee restores to its bind (identity) offset.
        mc.setAttr(solver + "._computeSource", "pass\n", type="string")
        mc.setAttr(handle + ".translate", 0.001, 0.0, 0.0, type="double3")
        mc.dgeval(ankle + ".worldMatrix[0]")
        off2 = np.array(mc.getAttr(knee + ".offsetParentMatrix")).reshape(4, 4)
        self.assertTrue(np.allclose(off2, np.eye(4), atol=1e-9),
                        "unset joint did not restore to its bind offset")


if __name__ == "__main__":
    unittest.main()
