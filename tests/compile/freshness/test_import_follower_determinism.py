"""``collect_helper_sources`` must emit the SAME order in every process.

Its BFS worklist is seeded from -- and extended by -- sets of (module, symbol)
tuples. Python randomizes string hashing per process, so iterating those sets
raw made the followed-helper order differ every run. That order reaches
``spec['external_helper_units']``, and ``port_cache`` canonicalizes with
``json.dumps(sort_keys=True)``, which sorts DICT KEYS but **preserves LIST
ORDER** -- so the cache key moved every process and 13 of 42 templates re-ran the
LLM porter on every rebuild (measured by tools/probe_spec_determinism.py).

Tested as the real PROPERTY, not the implementation: run the collector in two
subprocesses under different ``PYTHONHASHSEED`` values and compare. A test that
merely asserted ``sorted()`` appears in the source would pass while a future
refactor reintroduced a set anywhere else in the traversal.

``import_follower`` is pure stdlib (ast/os/sysconfig), so no Maya is needed --
these subprocesses run bare and stay fast.
"""
import json
import os
import subprocess
import sys
import textwrap
import unittest

from tests import _setup  # noqa: F401  (env + sys.path)

from mpynode.native.ai import import_follower

# A compute that pulls in several helpers from ONE module, which in turn
# reference their own siblings -- so both the seed set (_refs_in) and the
# per-node dep set (_deps_of) have more than one member and can reorder.
_COMPUTE = textwrap.dedent("""
    from mpynode._common.draw.draw_types import (
        DrawLines, DrawMesh, DrawPoints, DrawText)

    def compute(self):
        a = DrawLines
        b = DrawMesh
        c = DrawPoints
        d = DrawText
        self.out = (a, b, c, d)
""")

_CHILD = textwrap.dedent("""
    import json, sys
    sys.path.insert(0, %r)
    from mpynode.native.ai import import_follower
    res = import_follower.collect_helper_sources(%r)
    print("ORDER_JSON:" + json.dumps(
        [(u["module"], u["name"]) for u in res["sources"]]))
""")


def _scripts_dir():
    here = os.path.dirname(os.path.abspath(import_follower.__file__))
    # .../scripts/mpynode/native/ai -> .../scripts
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def _order_under(seed):
    """Followed-helper order produced by a fresh process with PYTHONHASHSEED."""
    env                   = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD % (_scripts_dir(), _COMPUTE)],
        capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise AssertionError("child failed (rc=%d):\n%s\n%s"
                             % (proc.returncode, proc.stdout[-2000:],
                                proc.stderr[-2000:]))
    for line in proc.stdout.splitlines():
        if line.startswith("ORDER_JSON:"):
            return json.loads(line[len("ORDER_JSON:"):])
    raise AssertionError("child printed no ORDER_JSON:\n%s" % proc.stdout[-2000:])


class TestFollowedHelperOrderIsProcessStable(unittest.TestCase):
    def test_same_order_under_different_hash_seeds(self):
        """The regression itself: different seeds must not reorder the units."""
        a = _order_under(1)
        b = _order_under(999983)
        self.assertTrue(a, "the fixture must actually follow some helpers")
        self.assertEqual(
            a, b,
            "followed-helper order is hash-seed dependent again -- the port "
            "cache will miss on every rebuild and the porter prompt will "
            "differ run to run")

    def test_order_is_stable_across_repeated_calls(self):
        """In-process determinism (cheap; catches a stateful regression)."""
        first  = import_follower.collect_helper_sources(_COMPUTE)["sources"]
        second = import_follower.collect_helper_sources(_COMPUTE)["sources"]
        self.assertEqual([(u["module"], u["name"]) for u in first],
                         [(u["module"], u["name"]) for u in second])

    def test_the_fixture_exercises_a_multi_member_traversal(self):
        """Guards the test itself: with 0 or 1 followed helper this suite would
        pass no matter how badly the ordering regressed."""
        got = import_follower.collect_helper_sources(_COMPUTE)["sources"]
        self.assertGreater(
            len(got), 1,
            "fixture followed %d helper(s); it must follow several or the "
            "reorder it exists to catch cannot happen" % len(got))


class TestSpecKeyIsProcessStable(unittest.TestCase):
    """The consequence the fix exists for: the cache key must not move."""

    def test_units_order_feeds_a_stable_cache_key(self):
        from mpynode.native.toolchain import port_cache

        def _spec(order):
            return {"suggested": {"node_type_name": "n"}, "compute": _COMPUTE,
                    "external_helper_units": order}

        units = import_follower.collect_helper_sources(_COMPUTE)["sources"]
        self.assertGreater(len(units), 1)
        key      = port_cache.cache_key(_spec(units), provider="p", model="m")
        shuffled = list(reversed(units))
        other    = port_cache.cache_key(_spec(shuffled), provider="p", model="m")
        # Pins WHY order matters: json.dumps preserves list order, so a reorder
        # really does move the key. If this ever stops being true the sort above
        # is no longer load-bearing and this suite should be revisited.
        self.assertNotEqual(
            key, other,
            "reordering external_helper_units no longer changes the cache key "
            "-- the traversal sort may no longer be needed")


if __name__ == "__main__":
    unittest.main()
