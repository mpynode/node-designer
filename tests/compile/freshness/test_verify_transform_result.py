"""The generic parity verify compares a transform-family node's RESULT.

The interpreted mPyTransform and the compiled MPxTransform both keep
``matrix`` the plain TRS and deliver the compute's matrix through
``offsetParentMatrix`` (the ``_outLocalFlat`` relay). The generic check
compared ``matrix`` alone, so it compared two untouched TRS stacks: a compiled
aimTransform whose offset matrix was 0.25 off read maxerr 0.0, and only the
authored @maya_test caught it.

Now the check compares ``matrix``, ``dagLocalMatrix`` (``matrix`` times
``offsetParentMatrix``) and ``worldMatrix[0]``, with each twin under an
identical, non-identity parent so the world compare is not a copy of the
local one.

The "compiled" node here is a stand-in: an interpreted mPyTransform built from
the shipped aimTransform spec, handed to ``verify._verify_one`` by a cmds proxy
whenever it creates the compiled type. That keeps the test free of a C++
build while running the real drive and compare.
"""

from __future__ import annotations

import tests  # noqa: F401 -- first: keeps the run out of ~/.mpynode

import json
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _verify():
    from mpynode.native.toolchain import verify

    return verify


_AIM = os.path.join(_paths.ROOT, "templates", "MPyTransform",
                    "Aim Between Matrices", "build", "manifest.json")
_AIM_LINE = "self.local_matrix = M @ np.linalg.inv(P)\n"
_BUNDLE   = os.path.join("no", "such", "standin.mll")
_RESULT   = ("matrix", "dagLocalMatrix", "worldMatrix[0]")


def _aim_spec():
    with open(_AIM, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


class _StandInCmds(object):
    """maya.cmds, except that creating the spec's compiled type builds an
    interpreted mPyTransform with ``compute`` instead, and the bundle reads as
    loaded."""

    def __init__(self, spec, compute, inherits=True):
        self.spec     = spec
        self.type     = spec["suggested"]["node_type_name"]
        self.compute  = compute
        self.inherits = inherits
        self.node     = None

    def __getattr__(self, name):
        return getattr(mc, name)

    def pluginInfo(self, name, *args, **kwargs):
        if name == os.path.basename(_BUNDLE):
            return True
        return mc.pluginInfo(name, *args, **kwargs)

    def createNode(self, type_name, *args, **kwargs):
        if type_name != self.type:
            return mc.createNode(type_name, *args, **kwargs)
        from mpynode.wrappers.mpy_transform import MPyTransform

        w = MPyTransform.create(name="standIn_" + self.type)
        for nm, m in self.spec["inputs"].items():
            w.add_input_attr(nm, m["type"], is_array=bool(m.get("is_array")))
        w.set_init_expression(self.spec["init"])
        w.set_compute_expression(self.compute)
        self.node = w.get_name()
        if not self.inherits:
            mc.setAttr(self.node + ".inheritsTransform", 0)
        return self.node

    def nodeType(self, node, *args, **kwargs):
        if node == self.node and not args and not kwargs:
            return self.type
        return mc.nodeType(node, *args, **kwargs)


def _matrix(node, plug):
    return [float(x) for x in mc.getAttr(node + "." + plug)]


def _maxerr(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


class TestTheResultPlugsAreCompared(unittest.TestCase):
    def test_an_mpytransform_is_compared_on_its_result(self):
        out = _verify()._native_family_outputs({"mpy_type": "mPyTransform"})
        self.assertEqual(tuple(out), _RESULT)
        for meta in out.values():
            self.assertEqual(meta, {"type": "matrix", "native": True})

    def test_an_mpxtransform_base_is_a_transform_family(self):
        v    = _verify()
        spec = {"suggested": {"mpx_base": "MPxTransform"}}
        self.assertTrue(v._is_transform_family(spec))
        self.assertEqual(tuple(v._native_family_outputs(spec)), _RESULT)

    def test_other_families_add_nothing(self):
        v = _verify()
        for spec in ({"mpy_type": "mPyNode",
                      "suggested": {"mpx_base": "MPxNode"}},
                     {"mpy_type": "mPyLocator",
                      "suggested": {"mpx_base": "MPxLocatorNode"}}, {}):
            self.assertFalse(v._is_transform_family(spec))
            self.assertEqual(v._native_family_outputs(spec), {})


class TestEachTwinGetsTheSameParent(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_parents_are_identical_and_not_identity(self):
        a = mc.createNode("transform", name="twinA")
        b = mc.createNode("transform", name="twinB")
        mc.setAttr(a + ".translate", 1.0, 2.0, 3.0, type="double3")
        a, b = _verify()._parent_transform_twins(mc, (a, b))
        pa = mc.listRelatives(a, parent=True)[0]
        pb = mc.listRelatives(b, parent=True)[0]
        self.assertNotEqual(pa, pb)
        self.assertEqual(_matrix(pa, "worldMatrix[0]"),
                         _matrix(pb, "worldMatrix[0]"))
        ident = [float(i % 5 == 0) for i in range(16)]
        self.assertGreater(_maxerr(_matrix(pa, "worldMatrix[0]"), ident), 1.0)
        # Relative: each node keeps its own TRS.
        self.assertEqual(mc.getAttr(a + ".translate")[0], (1.0, 2.0, 3.0))
        self.assertEqual(mc.getAttr(b + ".translate")[0], (0.0, 0.0, 0.0))


class TestTheGenericCheckSeesTheTransformResult(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        self.spec = _aim_spec()
        self.assertEqual(self.spec["compute"].count(_AIM_LINE), 1)
        env = mock.patch.dict(os.environ, {"MPYNODE_TIMING": "0"})
        env.start()
        self.addCleanup(env.stop)

    def _run(self, compute, inherits=True):
        cmds = _StandInCmds(self.spec, compute, inherits)
        row  = _verify()._verify_one(cmds, _BUNDLE, self.spec)
        orig = mc.ls("orig_" + cmds.type)[0]
        return row, orig, cmds.node

    def test_a_matching_twin_passes_on_a_result_that_moved(self):
        row, orig, comp = self._run(self.spec["compute"])
        self.assertTrue(row["ran"], row)
        self.assertTrue(row["pass"], row)
        self.assertLessEqual(row["maxerr"], 1e-9)
        # Neither compare is vacuous: the local result left identity, and the
        # world matrix is not the local one.
        ident = [float(i % 5 == 0) for i in range(16)]
        local = _matrix(orig, "dagLocalMatrix")
        self.assertGreater(_maxerr(local, ident), 0.1)
        self.assertGreater(_maxerr(_matrix(orig, "worldMatrix[0]"), local), 0.1)
        self.assertLessEqual(_maxerr(_matrix(orig, "matrix"), ident), 1e-12)

    def test_an_offset_matrix_a_quarter_off_fails(self):
        """The round 7 mutant: the compiled offset matrix +0.25 in X. Its TRS
        `matrix` matches, which is all the old check compared."""
        bumped = self.spec["compute"].replace(
            _AIM_LINE, "L = M @ np.linalg.inv(P)\nL[3, 0] += 0.25\n"
                       "self.local_matrix = L\n")
        row, orig, comp = self._run(bumped)
        self.assertTrue(row["ran"], row)
        self.assertFalse(row["pass"], row)
        self.assertAlmostEqual(row["maxerr"], 0.25, places=6)
        self.assertLessEqual(
            _maxerr(_matrix(orig, "matrix"), _matrix(comp, "matrix")), 1e-12)

    def test_a_twin_that_ignores_its_parent_fails_on_the_world_matrix(self):
        row, orig, comp = self._run(self.spec["compute"], inherits=False)
        self.assertTrue(row["ran"], row)
        self.assertFalse(row["pass"], row)
        self.assertGreater(row["maxerr"], 1.0)
        # Only the world matrix differs.
        for plug in ("matrix", "dagLocalMatrix"):
            self.assertLessEqual(
                _maxerr(_matrix(orig, plug), _matrix(comp, plug)), 1e-9, plug)
        self.assertGreater(_maxerr(_matrix(orig, "worldMatrix[0]"),
                                   _matrix(comp, "worldMatrix[0]")), 1.0)


if __name__ == "__main__":
    unittest.main()
