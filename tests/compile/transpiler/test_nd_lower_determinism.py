"""``nd_lower`` must emit the SAME input-binding order in every process.

Every lowering entry point binds the node's used inputs by iterating
``_used_self_attrs(source)``, which is a **set** of attribute-name strings.
Python randomizes string hashing per process, so iterating it raw emitted the
``ndin_self_<plug>`` materialisation lines in a different order every run. That
order reaches ``generate_cpp``, so the node's C++ -- and its build hash, and any
"did codegen change" comparison built on it -- moved from process to process:
16 of the 43 shipped templates hashed differently across ``PYTHONHASHSEED`` 0 /
7 / 12345 (which ones differ depends on the seeds). Pinning
``PYTHONHASHSEED=0`` in the launchers hid it rather than fixing it.

Tested as the real PROPERTY, not the implementation: each lowering runs in two
subprocesses under different ``PYTHONHASHSEED`` values and the emitted lines are
compared. A test that merely asserted ``sorted()`` appears in the source would
pass while a future refactor reintroduced a set anywhere else in the traversal.

The five entry points that iterated that set raw are covered (plain compute,
deformer, geometry generator, geometry IO, transform). The iksolver and locator
lowerings already sorted; they are exercised by the shipped-template sweep
rather than by a fixture here. The lowering layer is pure ast/string work -- no
``import maya`` anywhere in ``nd_lower`` or its compiler dependencies -- so
these subprocesses run bare and stay fast.
"""
import json
import os
import subprocess
import sys
import textwrap
import unittest

from tests import _setup  # noqa: F401  (env + sys.path)

from mpynode.native.compiler import nd_lower

# Seven inputs, all read by every fixture: a one- or two-member set cannot
# reorder, so the fixture has to bind several or this suite proves nothing
# (asserted by test_every_fixture_binds_several_inputs).
_CHILD = textwrap.dedent("""
    import json, sys
    sys.path.insert(0, %r)
    from mpynode.native.compiler import nd_lower

    N = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf"]
    K = " + ".join("self." + n for n in N)

    def ins():
        return [{"plug": n, "member": n[0].upper() + n[1:], "kind": "inputs",
                 "meta": {"type": "float", "is_array": False}} for n in N]

    out = {}
    out["compute"] = nd_lower.try_lower_compute(
        ins(),
        [{"plug": "result", "member": "Result", "kind": "outputs",
          "meta": {"type": "float", "is_array": False}}],
        {"compute": "self.result = " + K + "\\n"})
    out["deform"] = nd_lower.try_lower_deform(
        ins(),
        {"compute": ("mesh = self.outputGeometry[0]\\n"
                     "pts = mesh.getPoints()\\n"
                     "k = " + K + "\\n"
                     "mesh.setPoints(pts * k)\\n")},
        "MPxDeformerNode")
    out["geo_generator"] = nd_lower.lower_geo_compute(
        ins(), "curve", "k = " + K + "\\nself.cvs = np.zeros((4, 3)) + k\\n")
    out["geo_io"] = nd_lower.lower_geo_io_compute(
        ins(),
        [{"plug": "outCurve", "member": "OutCurve", "kind": "outputs",
          "meta": {"type": "nurbsCurve", "is_array": False}}],
        "k = " + K + "\\nself.outCurve = NurbsCurve(cvs=np.zeros((4, 3)) + k)\\n")

    # The transform lowering binds DECLARED inputs (matrix + generic scalar)
    # rather than the geometry surface, so it needs its own spec shape.
    M = ["alphaMat", "bravoMat", "charlieMat", "deltaMat"]
    G = ["echoVal", "foxtrotVal", "golfVal"]
    out["transform"] = nd_lower.try_lower_transform({
        "compute": ("k = " + " + ".join("self." + g for g in G) + "\\n"
                    "m = " + " @ ".join("self." + n for n in M) + "\\n"
                    "self.local_matrix = m * k\\n"),
        "inputs": dict([(n, {"type": "matrix", "is_array": False}) for n in M]
                       + [(g, {"type": "float", "is_array": False})
                          for g in G]),
        "outputs": {}, "suggested": {}})
    print("LOWERED_JSON:" + json.dumps(out))
""")


def _scripts_dir():
    here = os.path.dirname(os.path.abspath(nd_lower.__file__))
    # .../scripts/mpynode/native/compiler -> .../scripts
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def _lowered_under(seed):
    """{path: [C++ lines]} produced by a fresh process with PYTHONHASHSEED."""
    env                   = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD % (_scripts_dir(),)],
        capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise AssertionError("child failed (rc=%d):\n%s\n%s"
                             % (proc.returncode, proc.stdout[-2000:],
                                proc.stderr[-2000:]))
    for line in proc.stdout.splitlines():
        if line.startswith("LOWERED_JSON:"):
            return json.loads(line[len("LOWERED_JSON:"):])
    raise AssertionError("child printed no LOWERED_JSON:\n%s" % proc.stdout[-2000:])


def _binding_order(lines):
    """The ``ndin_self_<plug>`` names in DECLARATION order (the reordered part).

    Only the materialisation lines declare one; the transpiled body reads them
    back in source order, so restricting to declarations keeps the assertion on
    the thing that actually moved.
    """
    out = []
    for ln in lines or []:
        for tok in ln.replace("(", " ").replace(")", " ").replace(";", " ").split():
            if tok.startswith("ndin_self_") and tok not in out:
                out.append(tok)
    return out


class TestLoweredInputOrderIsProcessStable(unittest.TestCase):
    """The regression itself: different seeds must not reorder the bindings."""

    @classmethod
    def setUpClass(cls):
        cls.a = _lowered_under(1)
        cls.b = _lowered_under(999983)

    def test_same_lowering_under_different_hash_seeds(self):
        for path in sorted(self.a):
            with self.subTest(path=path):
                self.assertEqual(
                    self.a[path], self.b[path],
                    "%s lowering is hash-seed dependent again -- generate_cpp "
                    "is no longer reproducible across processes, so the build "
                    "hash and every codegen comparison move for free" % path)

    def test_every_fixture_binds_several_inputs(self):
        """Guards the test itself: with 0 or 1 bound input this suite would
        pass no matter how badly the ordering regressed."""
        for path in ("compute", "deform", "geo_generator", "geo_io",
                     "transform"):
            with self.subTest(path=path):
                got = _binding_order(self.a.get(path))
                self.assertGreater(
                    len(got), 1,
                    "fixture %r bound %d input(s); it must bind several or the "
                    "reorder it exists to catch cannot happen" % (path, len(got)))


class TestUsedSelfAttrsIsStillUnordered(unittest.TestCase):
    """Pins WHY the consumers have to sort: the collector returns a SET.

    If it is ever changed to return an ordered value the sorts above stop being
    load-bearing and this suite should be revisited.
    """

    def test_collector_returns_a_set(self):
        got = nd_lower._used_self_attrs("x = self.alpha + self.bravo\n")
        self.assertIsInstance(got, set)
        self.assertEqual(got, {"alpha", "bravo"})


if __name__ == "__main__":
    unittest.main()
