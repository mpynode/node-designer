"""The benchmark harness must serialize its own timed section.

``optimizer_live.bench_lock()`` only ever wrapped ``optimizer_live._measure``,
which is the ENGINE's benchmark. The optimizer AGENT measures through its own
``./bench.sh``, three processes away (``benchmark_node.py`` <- ``bash bench.sh``
<- ``claude ... Bash``), and nothing on that path took the lock. Measured with an
OS process-table sampler on 2026-08-13: engine benchmarks alone gave max
concurrency 1 and 0 overlapping pairs; with the agent live, max concurrency 4 and
36 overlapping pairs, and every one of the 66 observations that made up the 20
concurrency events was an ``_optscratch/<type>/_optagent/`` bundle -- never a
``3_optimized/`` one.

``benchmark_node.py`` is the one file both paths run, so the lock belongs here.

The DEADLOCK this must not create: on the engine path the PARENT already holds
that same flock across the whole child (``_measure``), and flock belongs to the
open file description, so a child taking it again would block on its own parent
until ``MPYNODE_BENCH_LOCK_TIMEOUT``. The harness therefore locks only when
``bench.sh`` -- which runs with no lock-holding ancestor -- says to.

The harness calls ``maya.standalone.initialize()`` at import, so (like
``test_benchmark_harness_scene``) these tests exec the pure helper out of the AST
and read the rest structurally.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import os
import tempfile
import time
import unittest

from mpynode.native.ai import optimizer_live
from tests import _paths

# POSIX-only. ``optimizer_live.bench_lock()`` degrades to a documented no-op
# where it is absent ("on a platform with no fcntl -- Windows"), so the tests
# that assert real flock semantics cannot run there. Imported optionally rather
# than at module scope because a bare ``import fcntl`` made the WHOLE module
# fail to load on Windows 2026-08-14, taking the five structural tests below --
# which need no lock at all -- down with it.
try:
    import fcntl
except ImportError:  # pragma: no cover -- exercised only on Windows
    fcntl = None

_needs_flock = unittest.skipUnless(
    fcntl is not None, "fcntl/flock is POSIX-only; the bench lock is a "
                       "documented no-op without it")

_HARNESS = os.path.join(_paths.ROOT, "tools", "harness", "benchmark_node.py")

# The marker bench.sh exports. Duplicated here ON PURPOSE: the harness and the
# workspace generator are different files that must agree on one string, and a
# test that imported the constant from one of them could not catch a rename in
# the other.
_MARKER = "MPYNODE_BENCH_LOCK_CHILD"


def _source():
    with open(_HARNESS) as fh:
        return fh.read()


def _load_func(name, ns=None):
    tree = ast.parse(_source())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            mod = ast.Module(body=[node], type_ignores=[])
            g = dict(ns or {})
            exec(compile(mod, _HARNESS, "exec"), g)
            return g[name]
    raise AssertionError("%s() not found in %s" % (name, _HARNESS))


def _const(name):
    """A module-level literal constant, read out of the harness source."""
    for node in ast.parse(_source()).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("%s not found in %s" % (name, _HARNESS))


def _bench_lock_fn(no_import=False):
    """The harness's ``_bench_lock`` with the module globals it needs.

    ``no_import=True`` swaps in a ``__import__`` that raises, which is the
    standalone case: the harness is invoked directly by ``run_all.py`` from a
    tree where ``mpynode`` is not on the path.
    """
    ns = {"os": os, "contextlib": contextlib,
          "_LOCK_CHILD_ENV": _const("_LOCK_CHILD_ENV"),
          "_OFF": _const("_OFF")}
    if no_import:
        def _boom(*a, **kw):
            raise ImportError("no mpynode here")

        ns["__builtins__"] = dict(vars(builtins), __import__=_boom)
    return _load_func("_bench_lock", ns)


class _Env:
    def __init__(self, **kw):
        self._kw = kw
        self._old = {}

    def __enter__(self):
        for k, v in self._kw.items():
            self._old[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _lock_is_taken(path):
    """True if an exclusive flock is held on ``path`` (see test_bench_lock)."""
    if not os.path.exists(path):
        return False
    fh = open(path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    else:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return False
    finally:
        fh.close()


class TestTheMarkerNameIsTheContract(unittest.TestCase):
    """``bench.sh`` (generated by ``optimizer_agent``) and this harness are two
    files that have to agree on one string, with no import between them. Rename
    it on one side and the lock silently stops covering the agent again."""

    def test_the_harness_reads_the_agreed_variable(self):
        self.assertEqual(_const("_LOCK_CHILD_ENV"), _MARKER)


@_needs_flock
class TestTheDefaultPathStaysFree(unittest.TestCase):
    """No marker -> the harness must not so much as look at the lockfile. This
    is what keeps the ENGINE path (where the parent holds the lock) from
    deadlocking on itself, and what keeps a standalone run free."""

    def test_without_the_marker_it_does_not_wait_on_a_held_lock(self):
        # Decisive: the lock is ON and ALREADY HELD from a second open file
        # description. If the harness tried to acquire it, this would block
        # until MPYNODE_BENCH_LOCK_TIMEOUT (1800s), not return in milliseconds.
        fn = _bench_lock_fn()
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            held = open(lock, "a+")
            try:
                fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with _Env(MPYNODE_BENCH_LOCK=lock, **{_MARKER: None}):
                    t0 = time.time()
                    with fn("thing"):
                        pass
                    self.assertLess(time.time() - t0, 5.0)
            finally:
                fcntl.flock(held.fileno(), fcntl.LOCK_UN)
                held.close()

    def test_off_values_of_the_marker_are_off(self):
        fn = _bench_lock_fn()
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            for val in ("", "0", "off", "false", "no"):
                with _Env(MPYNODE_BENCH_LOCK=lock, **{_MARKER: val}):
                    with fn("thing"):
                        self.assertFalse(_lock_is_taken(lock),
                                         "%r must not take the lock" % val)


class TestTheAgentPathIsSerialized(unittest.TestCase):
    @_needs_flock
    def test_the_marker_makes_the_harness_hold_the_real_lock(self):
        fn = _bench_lock_fn()
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            with _Env(MPYNODE_BENCH_LOCK=lock, **{_MARKER: "1"}):
                with fn("thing"):
                    self.assertTrue(
                        _lock_is_taken(lock),
                        "the agent's benchmark ran WITHOUT the bench lock")
                self.assertFalse(_lock_is_taken(lock),
                                 "the lock outlived the timed section")

    @_needs_flock
    def test_it_is_the_same_lockfile_the_engine_uses(self):
        # Two locks would serialize each path against itself and neither
        # against the other -- exactly today's defect, harder to see.
        fn = _bench_lock_fn()
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            with _Env(MPYNODE_BENCH_LOCK=lock, **{_MARKER: "1"}):
                self.assertEqual(optimizer_live.bench_lock_path(), lock)
                with fn("thing"):
                    self.assertTrue(_lock_is_taken(lock))

    def test_the_global_lock_being_off_still_means_off(self):
        # The marker says "no ancestor holds it", not "force a lock on".
        fn = _bench_lock_fn()
        with _Env(MPYNODE_BENCH_LOCK=None, **{_MARKER: "1"}):
            t0 = time.time()
            with fn("thing"):
                pass
            self.assertLess(time.time() - t0, 5.0)


class TestStandaloneStillRuns(unittest.TestCase):
    """``run_all.py`` and the parity harnesses invoke this script directly, from
    environments where ``mpynode`` may not import. A benchmark must never fail
    because its optional lock could not be found."""

    def test_an_unimportable_optimizer_live_degrades_to_no_lock(self):
        fn = _bench_lock_fn(no_import=True)
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            with _Env(MPYNODE_BENCH_LOCK=lock, **{_MARKER: "1"}):
                with fn("thing"):
                    pass


class TestTheGeneratedBenchShActuallyTurnsItOn(unittest.TestCase):
    """Close the loop between the two files without booting Maya: take the env
    the REAL ``bench.sh`` exports and hand it to the REAL harness helper. A
    name that matches but a value that reads as "off" would pass every test
    above and still leave the agent unserialized."""

    def _exports(self, text):
        env = {}
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("export "):
                continue
            body = line[len("export "):]
            if "=" not in body:
                continue
            k, _, v = body.partition("=")
            if k.strip() in ("MPYNODE_BENCH_LOCK", _MARKER):
                env[k.strip()] = v.strip().strip('"')
        return env

    @_needs_flock
    def test_bench_sh_env_makes_the_harness_take_the_lock(self):
        import shutil

        from mpynode.native.ai import optimizer_agent

        spec = {"suggested": {"node_type_name": "widgetNode",
                              "class_name": "WidgetNode",
                              "mpx_base": "MPxNode", "type_id": "0x00012345"},
                "inputs": {}, "outputs": {}, "compute": "pass", "init": ""}
        ws = tempfile.mkdtemp(prefix="benchlock_")
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        lock = os.path.join(ws, "bench.lock")
        with _Env(MPYNODE_BENCH_LOCK=lock):
            optimizer_agent.build_workspace(spec, ws, "// x\n")
            with open(os.path.join(ws, "bench.sh")) as fh:
                env = self._exports(fh.read())

        self.assertEqual(env.get("MPYNODE_BENCH_LOCK"), lock)
        with _Env(**env):
            with _bench_lock_fn()("widgetNode"):
                self.assertTrue(_lock_is_taken(lock),
                                "bench.sh's env did not turn the lock on")


def _main_ast():
    for node in ast.parse(_source()).body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main() not found in %s" % _HARNESS)


def _bench_lock_withs(fn_node):
    return [n for n in ast.walk(fn_node)
            if isinstance(n, ast.With)
            and any(isinstance(i.context_expr, ast.Call)
                    and isinstance(i.context_expr.func, ast.Name)
                    and i.context_expr.func.id == "_bench_lock"
                    for i in n.items)]


def _contains_sample_loop(node):
    for n in ast.walk(node):
        if (isinstance(n, ast.Attribute) and n.attr == "append"
                and isinstance(n.value, ast.Name) and n.value.id == "samples"):
            return True
    return False


def _contains_warmup_loop(node):
    for n in ast.walk(node):
        if (isinstance(n, ast.Attribute) and n.attr == "warmup"
                and isinstance(n.value, ast.Name) and n.value.id == "args"):
            return True
    return False


class TestTheTimedSectionIsInsideTheLock(unittest.TestCase):
    """A helper nobody calls protects nothing, and the assertion has to be
    structural: `"bench_lock" in src` would pass on a call in a comment."""

    def test_main_wraps_its_measurement_in_the_lock(self):
        withs = _bench_lock_withs(_main_ast())
        self.assertTrue(withs, "main() never enters _bench_lock()")
        self.assertTrue(any(_contains_sample_loop(w) for w in withs),
                        "the timed sample loop is OUTSIDE the bench lock")

    def test_the_warmup_is_inside_it_too(self):
        # Warmup is full-rate compute. Left outside, one process's warmup runs
        # during another's timed region -- the same corruption, just quieter.
        withs = _bench_lock_withs(_main_ast())
        self.assertTrue(any(_contains_warmup_loop(w) for w in withs),
                        "the warmup loop is OUTSIDE the bench lock")


if __name__ == "__main__":
    unittest.main()
