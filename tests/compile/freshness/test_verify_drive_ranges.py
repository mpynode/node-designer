"""The generic parity verify picks every input inside the attr's range.

Mesh Maze's generic verify never ran. The geometry drive perturbs each
declared default by 0.25 per config, so on config 3 solutionLength (max 1) was
1.1; the compiled node's setAttr refused it and the verify row read "could not
run". The other families clamped to the FIRST node that declared a range, so
a bound only the second node carried was skipped, and nothing read a soft
range or converted a unit type's limits (internal units) to the UI units
setAttr reads.

Now every pick goes through one fitter (verify._drive_fitter): the spec's
min / max (converted for a unit type), every live node's hard range, and a
soft range where one is present. A value inside is left exactly as drawn; one
outside is reflected back in, so the picks spread over the range instead of
piling on its ends. The shipped verify_in_maya.py scripts carry a standalone
twin of the same fitter (native/ai/verify_scripts._FIT_HELPERS).
"""

from __future__ import annotations

import inspect
import json
import math
import os
import random
import unittest

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


_MAZE = os.path.join(_paths.ROOT, "templates", "MPyMesh", "Mesh Maze", "build",
                     "manifest.json")


def _maze_spec():
    with open(_MAZE, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


class TestFold(unittest.TestCase):
    def test_a_value_inside_is_untouched(self):
        fold = _verify()._fold_into
        for v, lo, hi in ((0.3, 0.1, 0.7), (0.1, 0.1, 0.7), (0.7, 0.1, 0.7),
                          (5, 1, None), (-2.5, None, 0.0), (1.23, None, None)):
            self.assertIs(fold(v, lo, hi), v)

    def test_a_value_outside_is_reflected_back_in(self):
        fold = _verify()._fold_into
        self.assertAlmostEqual(fold(1.1, 0.0, 1.0),   0.9)
        self.assertAlmostEqual(fold(1.35, 0.0, 1.0),  0.65)
        self.assertAlmostEqual(fold(-0.25, 0.0, 1.0), 0.25)
        self.assertAlmostEqual(fold(3.2, 0.0, 1.0),   0.8)
        self.assertAlmostEqual(fold(-3.0, 0.0, None), 3.0)
        self.assertAlmostEqual(fold(5.0, None, 2.0),  -1.0)
        self.assertEqual(fold(4.0, 2.0, 2.0), 2.0)

    def test_out_of_range_draws_spread_instead_of_piling_on_the_ends(self):
        fold = _verify()._fold_into
        rng  = random.Random(3)
        vals = [fold(rng.uniform(-4.0, 4.0), 0.0, 1.0) for _ in range(2000)]
        self.assertTrue(all(0.0 <= v <= 1.0 for v in vals))
        on_ends = sum(1 for v in vals if v in (0.0, 1.0))
        self.assertEqual(on_ends, 0)  # a clamp put 87.5% of these on 0 or 1
        tenths = {min(int(v * 10), 9) for v in vals}
        self.assertEqual(tenths, set(range(10)))


class TestDriveRange(unittest.TestCase):
    """Real plugs: attributeQuery and setAttr speak the scene's UI units."""

    def setUp(self):
        mc.file(new=True, force=True)
        self.a = mc.createNode("transform", name="rangeA")
        self.b = mc.createNode("transform", name="rangeB")

    def tearDown(self):
        mc.currentUnit(angle="deg", linear="cm")

    def test_every_node_bounds_the_pick(self):
        """The interpreted twin declared only the min, the compiled one both:
        the old clamp read the first node and let 1.7 through."""
        v = _verify()
        mc.addAttr(self.a, ln="amount", at="double", min=0.0)
        mc.addAttr(self.b, ln="amount", at="double", min=0.0, max=1.0)
        self.assertEqual(v._drive_range(mc, (self.a, self.b), "amount", "double"),
                         (0.0, 1.0))
        got = v._fit_drive(mc, (self.a, self.b), "amount", "double", 1.7)
        self.assertAlmostEqual(got, 0.3)
        for nd in (self.a, self.b):
            mc.setAttr(nd + ".amount", got)

    def test_spec_limits_are_internal_units(self):
        """A doubleAngle's min_value / max_value are radians; setAttr reads
        degrees (and a doubleLinear's centimetres read in the UI unit)."""
        v    = _verify()
        meta = {"type": "doubleAngle", "min_value": 0.25, "max_value": 1.0}
        lo, hi = v._drive_range(mc, (self.a,), "nothing", "doubleAngle", meta)
        self.assertAlmostEqual(lo, math.degrees(0.25))
        self.assertAlmostEqual(hi, math.degrees(1.0))
        mc.currentUnit(linear="mm")
        meta = {"type": "doubleLinear", "min_value": 0.0, "max_value": 2.0}
        self.assertEqual(v._drive_range(mc, (self.a,), "nothing", "doubleLinear",
                                        meta), (0.0, 20.0))

    def test_live_unit_limits_need_no_conversion(self):
        v = _verify()
        mc.addAttr(self.b, ln="bend", at="doubleAngle", min=0.25, max=1.0)
        lo, hi = v._drive_range(mc, (self.a, self.b), "bend", "doubleAngle")
        self.assertAlmostEqual(lo, math.degrees(0.25))
        self.assertAlmostEqual(hi, math.degrees(1.0))
        got = v._fit_drive(mc, (self.a, self.b), "bend", "doubleAngle", 70.0)
        mc.setAttr(self.b + ".bend", got)  # inside: no refusal

    def test_a_soft_range_narrows_the_pick(self):
        v = _verify()
        mc.addAttr(self.a, ln="gain", at="double", min=0.0, max=10.0,
                   smn=2.0, smx=4.0)
        self.assertEqual(v._drive_range(mc, (self.a,), "gain", "double"),
                         (2.0, 4.0))
        self.assertAlmostEqual(v._fit_drive(mc, (self.a,), "gain", "double", 5.0),
                               3.0)
        mc.addAttr(self.a, ln="soft", at="double", smn=-1.0, smx=1.0)
        self.assertEqual(v._drive_range(mc, (self.a,), "soft", "double"),
                         (-1.0, 1.0))

    def test_unbounded_and_unranged_pass_through(self):
        v = _verify()
        mc.addAttr(self.a, ln="free", at="double")
        mc.addAttr(self.a, ln="vec", at="double3")
        for c in "XYZ":
            mc.addAttr(self.a, ln="vec" + c, at="double", p="vec")
        self.assertIsNone(v._drive_range(mc, (self.a,), "free", "double"))
        self.assertEqual(v._fit_drive(mc, (self.a,), "free", "double", -3.2), -3.2)
        self.assertEqual(v._fit_drive(mc, (self.a,), "vec", "double3", [9, 0, -9]),
                         [9, 0, -9])
        self.assertEqual(v._fit_drive(mc, (self.a,), "s", "string", "x"), "x")

    def test_an_integer_stays_an_integer(self):
        v = _verify()
        mc.addAttr(self.a, ln="bands", at="long", min=1)
        got = v._fit_drive(mc, (self.a,), "bands", "long", -6)
        self.assertEqual(got, 8)
        self.assertIsInstance(got, int)

    def test_a_compound_is_fitted_per_child(self):
        v = _verify()
        mc.addAttr(self.a, ln="tint", at="double3")
        mc.addAttr(self.a, ln="tintX", at="double", p="tint", min=0.0, max=1.0)
        mc.addAttr(self.a, ln="tintY", at="double", p="tint")
        mc.addAttr(self.a, ln="tintZ", at="double", p="tint")
        got = v._fit_drive(mc, (self.a,), "tint", "double3", [1.5, -9.0, 3.0])
        self.assertAlmostEqual(got[0], 0.5)
        self.assertEqual(got[1:], [-9.0, 3.0])


class TestGeoDrive(unittest.TestCase):
    """The drive that stopped Mesh Maze's generic verify, on real plugs."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _pair(self, inputs):
        """The harness's shape: one twin bare, the other with every declared
        limit and default (as the compiled node has them)."""
        import mpynode

        bare = mc.createNode("mPyMesh", name="bareMaze")
        full = mc.createNode("mPyMesh", name="limitedMaze")
        wb, wf = mpynode.wrap_node(bare), mpynode.wrap_node(full)
        for nm, m in inputs.items():
            kw = {k: m[k] for k in ("min_value", "max_value", "default_value")
                  if m.get(k) is not None and m["type"] != "color"}
            wb.add_input_attr(nm, m["type"])
            wf.add_input_attr(nm, m["type"], **kw)
        return bare, full

    def test_every_mesh_maze_config_is_accepted(self):
        v      = _verify()
        spec   = _maze_spec()
        inputs = spec["inputs"]
        nodes  = self._pair(inputs)
        roles  = v._geo_input_roles(spec.get("compute") or "", "mesh")
        rng    = random.Random(4242)
        seen   = []
        for cfg in range(v._GEO_CFGS):
            v._drive_geo_inputs(mc, nodes, inputs, roles, cfg, rng)
            got = [mc.getAttr(nd + ".solutionLength") for nd in nodes]
            self.assertAlmostEqual(got[0], got[1])
            seen.append(got[1])
        self.assertAlmostEqual(seen[0], 0.35)  # cfg 0 = the declared default
        self.assertTrue(all(0.0 <= s <= 1.0 for s in seen), seen)
        self.assertEqual(len({round(s, 6) for s in seen}), v._GEO_CFGS, seen)

    def test_a_unit_default_is_set_in_the_units_setattr_reads(self):
        """cfg 0 sets the declared default. A doubleAngle default of 0.5 rad
        used to go in as 0.5 degrees, below a 0.25 rad minimum."""
        v = _verify()
        inputs = {"bend": {"type": "doubleAngle", "min_value": 0.25,
                           "max_value": 1.0, "default_value": 0.5}}
        nodes = self._pair(inputs)
        rng   = random.Random(1)
        for cfg in range(v._GEO_CFGS):
            v._drive_geo_inputs(mc, nodes, inputs, {}, cfg, rng)
            got = mc.getAttr(nodes[1] + ".bend")
            self.assertGreaterEqual(got, math.degrees(0.25) - 1e-9)
            self.assertLessEqual(got, math.degrees(1.0) + 1e-9)
            if cfg == 0:
                self.assertAlmostEqual(got, math.degrees(0.5))


class TestEveryParityLoopPicksInside(unittest.TestCase):
    """_verify_one needs a compiled bundle, so pin the wiring by source."""

    def test_the_deformer_ik_and_scalar_loops_fit_every_pick(self):
        src = inspect.getsource(_verify()._verify_one)
        self.assertEqual(src.count("_input_fitters(cmds, "), 3)
        self.assertEqual(src.count("_fitted(fitters, a,"), 6)
        self.assertNotIn("_clamp_drive", src)

    def test_the_geo_drive_fits_and_converts(self):
        src = inspect.getsource(_verify()._drive_geo_inputs)
        self.assertIn("_input_fitters(cmds, nodes, inputs)", src)
        self.assertIn("_fitted(fitters, nm, _to_ui_units(cmds, t, v))", src)

    def test_direct_drives_keep_a_live_range_net(self):
        v = _verify()
        self.assertIn("_fit_drive(cmds, nodes, attr, t, v)",
                      inspect.getsource(v._drive_input))
        self.assertIn("_drive_fitter(cmds, nodes, attr, t)",
                      inspect.getsource(v._drive_array_input))


class TestShippedScriptsPickInside(unittest.TestCase):
    """The deformer / IK / scalar verify_in_maya.py scripts carry a twin of the
    fitter; the geometry script runs verify._verify_one itself."""

    def _spec(self, base="MPxNode", mpy_type="mPyNode"):
        return {"suggested": {"node_type_name": "probeNode",
                              "mpx_base": base},
                "mpy_type": mpy_type, "source_node": "probeSrc",
                "inputs":  {"amount": {"type": "double"}},
                "outputs": {"out": {"type": "double"}},
                "compute": "self.out = self.amount"}

    def test_each_script_fits_its_picks(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.ai import verify_scripts as vs

        deformer = sorted(codegen._DEFORMER_BASES)[0]
        for spec, call in (
                (self._spec(), "v = _fit((comp, SOURCE), a, t, _sample(t))"),
                (self._spec(deformer, "mPyDeformer"),
                 "v = _fit((src_d, cmp_d), a, t, _sample(t))"),
                (self._spec(codegen._IKSOLVER_BASE, "mPyIkSolver"),
                 "v = _fit((src_solver, cmp_solver), a, t,")):
            script = vs._verify_script(spec)
            compile(script, "verify_in_maya.py", "exec")
            self.assertIn(vs._FIT_HELPERS, script)
            self.assertIn(call, script)
            self.assertIn("import os, math, random", script)

    def test_the_script_fitter_matches_the_harness(self):
        from mpynode.native.ai import verify_scripts as vs

        v  = _verify()
        ns = {"cmds": mc, "math": math}
        exec(vs._FIT_HELPERS, ns)
        mc.file(new=True, force=True)
        a = mc.createNode("transform", name="twinA")
        b = mc.createNode("transform", name="twinB")
        mc.addAttr(a, ln="amount", at="double", min=0.0)
        mc.addAttr(b, ln="amount", at="double", min=0.0, max=1.0, smx=0.5)
        mc.addAttr(b, ln="count", at="long", min=1, max=6)
        mc.addAttr(b, ln="bend", at="doubleAngle", min=0.25, max=1.0)
        rng = random.Random(9)
        for attr, t, draw in (("amount", "double", lambda: rng.uniform(-4, 4)),
                              ("count", "long", lambda: rng.randint(-10, 10)),
                              ("bend", "doubleAngle", lambda: rng.uniform(-90, 90))):
            for _ in range(50):
                x = draw()
                self.assertEqual(ns["_fit"]((a, b), attr, t, x),
                                 v._fit_drive(mc, (a, b), attr, t, x))


if __name__ == "__main__":
    unittest.main()
