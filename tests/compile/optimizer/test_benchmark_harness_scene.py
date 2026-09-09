"""The benchmark harness must measure a node doing REAL work.

Two defects made that untrue, and together they let a wrong candidate ship:

  * ``_BUILTIN`` (the representative scene table) was keyed on the exact node
    TYPE NAME. Compiled types get suffixed -- ``metaballs`` -> ``metaballsSw`` --
    so every renamed type silently lost its scene and fell back to generic
    spec-seeding, which for an SDF generator yields an EMPTY isosurface.
  * even when a builtin scene WAS found it was applied BEFORE
    ``seed_bench_scene``, so the generic seeder overwrote it and padded its
    arrays with hundreds of junk elements.

The harness is a standalone script (it calls ``maya.standalone.initialize()`` at
import), so it is never imported. These tests read its source and exec the pure
helper out of the AST -- which is enough to pin the contract without booting Maya.
"""

from __future__ import annotations

import ast
import os
import unittest
from tests import _paths

_HARNESS = os.path.join(_paths.ROOT, "tools", "harness", "benchmark_node.py")


def _source():
    with open(_HARNESS) as fh:
        return fh.read()


def _load_func(name, ns=None):
    """Exec ONE top-level function out of the harness, without importing it."""
    tree = ast.parse(_source())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            mod = ast.Module(body=[node], type_ignores=[])
            g = dict(ns or {})
            exec(compile(mod, _HARNESS, "exec"), g)
            return g[name]
    raise AssertionError("%s() not found in %s" % (name, _HARNESS))


class TestBuiltinSceneKey(unittest.TestCase):
    def setUp(self):
        self.builtin = {"metaClay": lambda r: ["metaClay", r],
                        "metaballs": lambda r: ["metaballs", r]}
        self.fn = _load_func("_builtin_scene_key", {"_BUILTIN": self.builtin})

    def test_exact_name_still_matches(self):
        self.assertEqual(self.fn("metaballs"), "metaballs")
        self.assertEqual(self.fn("metaClay"), "metaClay")

    def test_compiled_suffix_still_finds_the_scene(self):
        # THE BUG: metaballsSw fell through to generic seeding -> empty mesh.
        self.assertEqual(self.fn("metaballsSw"), "metaballs")
        self.assertEqual(self.fn("metaballsCmp"), "metaballs")
        self.assertEqual(self.fn("metaClaySw"), "metaClay")

    def test_unrelated_type_matches_nothing(self):
        self.assertIsNone(self.fn("kDTreeSw"))
        self.assertIsNone(self.fn("patchRelaxSw"))
        self.assertIsNone(self.fn(""))
        self.assertIsNone(self.fn(None))

    def test_longest_key_wins(self):
        fn = _load_func("_builtin_scene_key",
                        {"_BUILTIN": {"meta": 1, "metaballs": 2}})
        self.assertEqual(fn("metaballsSw"), "metaballs")


class TestGeoEmptiness(unittest.TestCase):
    """None = not geometry (a numeric/array output must stay unaffected),
    True = positively empty, False = holds real geometry."""

    def setUp(self):
        self.fn = _load_func("_geo_emptiness")

    # Real Maya apiType constants are opaque ints; any distinct values do.
    MESH, CURVE, SURFACE, NUMERIC = 1, 2, 3, 99

    class _MFn:
        kMeshData, kNurbsCurveData, kNurbsSurfaceData = 1, 2, 3

    class _Om:
        """Stand-in for maya.api.OpenMaya.

        Every MFn* constructor SUCCEEDS regardless of the data handed to it --
        which is the real behaviour that broke the first implementation, and the
        reason dispatch must go through apiType().
        """

        MFn = None      # set in __init__

        def __init__(self, counts=None):
            self.MFn = TestGeoEmptiness._MFn
            counts = counts or {}

            def mk(attr, key):
                class _Fn:
                    def __init__(_s, data):
                        _s._v = counts.get(key, "raise")

                    def __getattr__(_s, name):
                        if name != attr:
                            raise AttributeError(name)
                        v = object.__getattribute__(_s, "_v")
                        if v == "raise":
                            raise RuntimeError("Object does not exist")
                        return v
                return _Fn
            self.MFnMesh = mk("numVertices", "mesh")
            self.MFnNurbsCurve = mk("numCVs", "curve")
            self.MFnNurbsSurface = mk("numCVsInU", "surface")

    class _Plug:
        def __init__(self, data=None, raises=False):
            self._d, self._r = data, raises

        def asMObject(self):
            if self._r:
                raise RuntimeError("no data")
            return self._d

    class _Data:
        def __init__(self, api=1, null=False):
            self._a, self._n = api, null

        def isNull(self):
            return self._n

        def apiType(self):
            return self._a

    def test_real_mesh_is_not_empty(self):
        om = self._Om({"mesh": 1664059})
        self.assertIs(self.fn(self._Plug(self._Data(self.MESH)), om), False)

    def test_zero_vertex_mesh_is_empty(self):
        om = self._Om({"mesh": 0})
        self.assertIs(self.fn(self._Plug(self._Data(self.MESH)), om), True)

    def test_constructed_but_inaccessible_is_empty(self):
        # an empty geo data object is not null: MFnMesh constructs on it, then
        # raises "Object does not exist" on first access. That is how the
        # empty metaballs isosurface presented.
        om = self._Om({"mesh": "raise"})
        self.assertIs(self.fn(self._Plug(self._Data(self.MESH)), om), True)

    def test_numeric_output_is_not_geometry(self):
        # kdtree's outputs are numeric arrays, and an MFn* constructs on
        # numeric data then fails the count access, so judging by construction
        # reported every kdtree benchmark as empty geometry. apiType is the
        # only reliable discriminator.
        om = self._Om()
        self.assertIsNone(self.fn(self._Plug(self._Data(self.NUMERIC)), om))

    def test_null_data_and_unreadable_plug_are_not_geometry(self):
        om = self._Om({"mesh": 10})
        self.assertIsNone(
            self.fn(self._Plug(self._Data(self.MESH, null=True)), om))
        self.assertIsNone(self.fn(self._Plug(raises=True), om))

    def test_a_curve_is_judged_as_a_curve(self):
        # MFnMesh would construct-and-raise on curve data; apiType dispatch
        # reads it with MFnNurbsCurve instead of calling it an empty mesh.
        om = self._Om({"mesh": "raise", "curve": 42})
        self.assertIs(self.fn(self._Plug(self._Data(self.CURVE)), om), False)

    def test_empty_surface_is_empty(self):
        om = self._Om({"surface": 0})
        self.assertIs(self.fn(self._Plug(self._Data(self.SURFACE)), om), True)


class TestHarnessWiring(unittest.TestCase):
    def test_builtin_lookup_goes_through_the_resolver(self):
        src = _source()
        self.assertTrue("_builtin_scene_key(" in src,
                        "harness never calls _builtin_scene_key()")
        self.assertFalse("args.node_type in _BUILTIN" in src,
                         "the exact-match lookup is what dropped the scene")

    def test_builtin_scene_is_applied_after_generic_seeding(self):
        # Ordering is the point: seed_bench_scene pads arrays to k_array
        # elements, so a scene applied before it gets padded with junk shapes.
        src = _source()
        # main() applies the scene through _apply_scene (which trims the driven
        # multis, then calls _apply_ops); the copies get the same call.
        self.assertTrue("seed_bench_scene" in src and "_apply_scene(node, ops" in src,
                        "expected both call sites to exist")
        main_at = src.index("def main(")
        self.assertLess(src.index("seed_bench_scene", main_at),
                        src.index("_apply_scene(node, ops", main_at),
                        "the representative scene must be applied AFTER seeding")

    def test_empty_output_is_reported_and_fatal(self):
        src = _source()
        self.assertTrue("empty_output" in src,
                        "no empty_output flag in BENCH_JSON")
        self.assertTrue("_geo_emptiness(" in src,
                        "harness never probes for empty geometry")


if __name__ == "__main__":
    unittest.main()
