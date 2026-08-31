"""The global benchmark lock.

Two Maya processes timing at once contend and corrupt BOTH numbers, which is not
a slow run but a WRONG verdict: it already made one whole recorded optimizer
experiment unreadable. But most of an optimizer round is LLM latency, so the
lock covers ONLY the timed subprocess -- N agents think concurrently while
exactly one benchmarks.

Mutual exclusion is asserted across REAL processes (an flock is a property of an
open file description; threads in one process would prove nothing about the
fleet), and the stale case is a real SIGKILL, because the failure to avoid is a
crashed holder wedging every other worker forever.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from mpynode.native.ai import optimizer_live


# Everything below the "lock is off" group asserts POSIX semantics -- flock
# across real processes, and a real SIGKILL. ``optimizer_live.bench_lock()``
# deliberately yields False "on a platform with no fcntl -- Windows", so there
# is nothing to assert there. The off-by-default group does NOT depend on
# either and keeps running everywhere.
try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover -- exercised only on Windows
    _fcntl = None

_needs_flock = unittest.skipUnless(
    _fcntl is not None and hasattr(signal, "SIGKILL"),
    "flock/SIGKILL are POSIX-only; bench_lock() is a documented no-op without "
    "fcntl")

_CHILD = os.path.join(os.path.dirname(__file__), "_bench_lock_child.py")


class _Env:
    """Set/restore env vars around a block (None removes)."""

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


def _spawn(lockpath, journal, tag, hold_s=1.0, mode="normal"):
    return subprocess.Popen(
        [sys.executable, _CHILD, lockpath, journal, tag, str(hold_s), mode],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _reap(proc):
    """Kill + wait + close the pipes (an un-drained Popen leaks its fds)."""
    try:
        os.kill(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    proc.wait(timeout=60)
    for pipe in (proc.stdout, proc.stderr):
        if pipe is not None:
            pipe.close()


def _journal(path):
    try:
        with open(path) as fh:
            return [ln.strip() for ln in fh if ln.strip()]
    except OSError:
        return []


def _wait_for(path, needle, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        if any(ln.startswith(needle) for ln in _journal(path)):
            return True
        time.sleep(0.05)
    return False


class TestTheLockIsOffByDefault(unittest.TestCase):
    """A single-process run must pay nothing: unset means no path, no file, no
    fcntl. This is what keeps every existing serial usage byte-identical."""

    def test_unset_resolves_to_no_lock_and_the_body_still_runs(self):
        with _Env(MPYNODE_BENCH_LOCK=None):
            self.assertEqual(optimizer_live.bench_lock_path(), "")
            with optimizer_live.bench_lock(label="x") as held:
                self.assertFalse(held)

    def test_explicit_off_values_disable_it(self):
        for val in ("", "0", "off", "OFF", "false", "no"):
            with _Env(MPYNODE_BENCH_LOCK=val):
                self.assertEqual(optimizer_live.bench_lock_path(), "",
                                 "%r must disable the lock" % val)

    def test_off_means_re_entrant_and_free_not_merely_untested(self):
        # With the lock ON this nesting would self-deadlock (flock conflicts
        # between two open file descriptions in ONE process). It returning
        # promptly is the proof that OFF touches nothing at all.
        with _Env(MPYNODE_BENCH_LOCK=None):
            t0 = time.time()
            with optimizer_live.bench_lock() as a:
                with optimizer_live.bench_lock() as b:
                    self.assertFalse(a or b)
            self.assertLess(time.time() - t0, 1.0)

    def test_on_resolves_to_a_writable_shared_path(self):
        # NOT the MPyNode home: ~/mpynode is EPERM here, and a lock that cannot
        # be created is a lock that silently protects nothing.
        with _Env(MPYNODE_BENCH_LOCK="1"):
            p = optimizer_live.bench_lock_path()
        self.assertTrue(p)
        self.assertTrue(os.path.isdir(os.path.dirname(p)))
        self.assertNotIn(os.path.join(os.path.expanduser("~"), "mpynode"), p)

    def test_any_other_value_is_taken_as_the_path(self):
        with _Env(MPYNODE_BENCH_LOCK="/tmp/some/where/bench.lock"):
            self.assertEqual(optimizer_live.bench_lock_path(),
                             "/tmp/some/where/bench.lock")


@_needs_flock
class TestMutualExclusionAcrossProcesses(unittest.TestCase):
    def test_two_processes_never_benchmark_at_the_same_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            journal = os.path.join(tmp, "journal.txt")
            procs = [_spawn(lock, journal, "p%d" % i, hold_s=0.6)
                     for i in range(4)]
            for p in procs:
                out, err = p.communicate(timeout=180)
                self.assertEqual(p.returncode, 0,
                                 "child failed: %s" % err.decode("utf-8",
                                                                 "replace"))
            lines = _journal(journal)
            self.assertEqual(len(lines), 8, lines)
            # The whole contract in one assertion: every ENTER is followed by
            # its own LEAVE before the next ENTER. Any interleaving is two
            # benchmarks running at once.
            depth = 0
            for ln in lines:
                depth += 1 if ln.startswith("ENTER") else -1
                self.assertIn(depth, (0, 1),
                              "overlapping benchmark windows: %s" % lines)
            self.assertEqual(depth, 0, lines)

    def test_a_waiter_actually_waits_for_the_holder(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            journal = os.path.join(tmp, "journal.txt")
            holder = _spawn(lock, journal, "holder", hold_s=2.0)
            self.assertTrue(_wait_for(journal, "ENTER holder"),
                            "holder never acquired")
            t0 = time.time()
            waiter = _spawn(lock, journal, "waiter", hold_s=0.0)
            waiter.communicate(timeout=180)
            waited = time.time() - t0
            holder.communicate(timeout=180)
            self.assertEqual(waiter.returncode, 0)
            self.assertGreater(waited, 0.5,
                               "the waiter did not block on the holder")
            self.assertEqual(_journal(journal)[:2],
                             ["ENTER holder", "LEAVE holder"])


@_needs_flock
class TestACrashedHolderDoesNotWedgeTheFleet(unittest.TestCase):
    """flock is released by the KERNEL when the holding fd goes away, so a
    SIGKILLed / segfaulted worker (a mis-compiled candidate really does segfault
    its mayapy) cannot leave a lock nobody can take."""

    def test_sigkilled_holder_releases_the_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            journal = os.path.join(tmp, "journal.txt")
            holder = _spawn(lock, journal, "zombie", mode="hang")
            self.assertTrue(_wait_for(journal, "HANGING zombie"),
                            "hanging holder never acquired the lock")
            _reap(holder)

            # The lockFILE survives (with the dead holder's pid still in it);
            # the LOCK must not.
            self.assertTrue(os.path.exists(lock))
            nxt = _spawn(lock, journal, "next", hold_s=0.0)
            out, err = nxt.communicate(timeout=120)
            self.assertEqual(nxt.returncode, 0,
                             "a killed holder wedged the lock: %s"
                             % err.decode("utf-8", "replace"))
            self.assertIn("LEAVE next", _journal(journal))


@_needs_flock
class TestAWedgedHolderIsALoudError(unittest.TestCase):
    def test_waiting_past_the_timeout_raises_instead_of_hanging(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            journal = os.path.join(tmp, "journal.txt")
            holder = _spawn(lock, journal, "wedged", mode="hang")
            self.assertTrue(_wait_for(journal, "HANGING wedged"))
            try:
                with _Env(MPYNODE_BENCH_LOCK=lock,
                          MPYNODE_BENCH_LOCK_TIMEOUT="1"):
                    t0 = time.time()
                    with self.assertRaises(optimizer_live.BenchLockTimeout) as cm:
                        with optimizer_live.bench_lock(label="me"):
                            pass
                    self.assertLess(time.time() - t0, 30.0)
                # The message must name the holder, or an operator has nothing
                # to go and kill.
                self.assertIn("wedged", str(cm.exception))
                self.assertIn("MPYNODE_BENCH_LOCK_TIMEOUT", str(cm.exception))
            finally:
                _reap(holder)

    def test_an_unopenable_lockfile_raises_rather_than_running_unlocked(self):
        with _Env(MPYNODE_BENCH_LOCK="/dev/null/nope/bench.lock"):
            with self.assertRaises(optimizer_live.BenchLockTimeout):
                with optimizer_live.bench_lock():
                    pass


@_needs_flock
class TestOnlyTheTimedSectionIsSerialized(unittest.TestCase):
    """The lock must sit around the benchmark subprocess and NOTHING else --
    holding it across the LLM round would serialize the fleet on its slowest
    thinker, which is the whole reason the lock is this narrow."""

    def test_the_benchmark_child_runs_under_the_lock(self):
        import tempfile as _tf

        from mpynode.native.ai.optimizer import ParityVerdict, PARITY_PASS

        spec = {"suggested": {"node_type_name": "mPyThing",
                              "mpx_base": "MPxNode"},
                "compute": "self.out = self.a", "init": ""}
        seen = {}

        with _tf.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")

            def run_step(script, args, prefix, timeout):
                # Held? Another process taking it non-blockingly would fail.
                seen["locked"] = _lock_is_taken(lock)
                return {"median_ms": 12.5}, True, ""

            with _Env(MPYNODE_BENCH_LOCK=lock):
                ad = optimizer_live.make_adapters(
                    spec, tmp, maya="/x",
                    complete_fn=lambda s, u: "x",
                    run_step=run_step,
                    parity_fn=lambda b: ParityVerdict(PARITY_PASS))
                ad["benchmark_fn"]("bundle")

        self.assertTrue(seen.get("locked"),
                        "the benchmark subprocess ran WITHOUT the bench lock")
        # ...and it is released again once the timed section is over.
        self.assertFalse(_lock_is_taken(lock))


@contextlib.contextmanager
def _hold(path):
    """Hold an exclusive flock on ``path`` for the block.

    From a SECOND open file description: an flock belongs to the description,
    not the process, so ``bench_lock``'s own ``open()`` in this same process is
    denied exactly as another worker's would be -- no child needed.
    """
    import fcntl

    fh = open(path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()


class _CancelledWhileWaiting:
    """Cancel pressed DURING the benchmark-lock wait.

    Clear on the first poll (``optimize_surviving``'s between-nodes check, so
    the node actually starts) and set on every poll after it -- which is the
    one ``bench_lock`` makes while it waits. A ``threading.Event`` flipped on a
    timer would test the same thing with a stopwatch.
    """

    def __init__(self):
        self.polls = 0

    def is_set(self):
        self.polls += 1
        return self.polls > 1


_BENCH_SPEC = {"suggested": {"node_type_name": "kDTree",
                             "mpx_base": "MPxNode"},
               "compute": "self.out = self.a", "init": ""}


@_needs_flock
class TestACancelDuringTheLockWaitIsACancel(unittest.TestCase):
    """``bench_lock`` raises ``_StepCancelled`` while waiting, but
    ``benchmark_fn`` was not ``_cancel_guard``-ed (only ``optimize_fn`` /
    ``fix_fn`` were), so a Cancel pressed during a lock wait was recorded as a
    round "error" -- or, at the baseline measurement, as a whole-node error.
    Only reachable with the lock ON."""

    def _adapters(self, tmp, cancel, **over):
        from mpynode.native.ai.optimizer import ParityVerdict, PARITY_PASS

        kw = dict(maya="/x", cancel_event=cancel,
                  complete_fn=lambda s, u: "x",
                  run_step=lambda *a, **k: ({"median_ms": 1.0}, True, ""),
                  parity_fn=lambda b: ParityVerdict(PARITY_PASS))
        kw.update(over)
        return optimizer_live.make_adapters(_BENCH_SPEC, tmp, **kw)

    def test_the_benchmark_adapter_raises_a_cancel_not_a_step_error(self):
        ev = threading.Event()
        ev.set()
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            with _Env(MPYNODE_BENCH_LOCK=lock):
                ad = self._adapters(tmp, ev)
                with _hold(lock):
                    with self.assertRaises(optimizer_live._OptimizeCancelled):
                        ad["benchmark_fn"]("bundle")

    def test_the_baseline_measurement_cancels_the_node_not_errors_it(self):
        """The unguarded call site: the engine measures the baseline OUTSIDE
        its per-round ``except Exception``, so a bare ``_StepCancelled`` there
        reached ``optimize_surviving`` as 'optimize kDTree failed'."""
        cancel = _CancelledWhileWaiting()
        notes, status = [], {}

        def factory(spec, out_dir, **kw):
            ad = self._adapters(out_dir, cancel, log_cb=None,
                                status_out=kw.get("status_out"))
            # The only real adapter under test is benchmark_fn; building C++ is
            # not what this is about.
            ad["compile_fn"] = lambda cpp: (True, "", "bundle")
            return ad

        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "bench.lock")
            cpp = os.path.join(tmp, "kDTree.cpp")
            with open(cpp, "w") as fh:
                fh.write("void f(){ return; }\n")
            with _Env(MPYNODE_BENCH_LOCK=lock), _hold(lock):
                res = optimizer_live.optimize_surviving(
                    [("kDTree", cpp, _BENCH_SPEC)], tmp,
                    verify_fn=lambda b, r: {}, adapters_factory=factory,
                    cancel_event=cancel, status_out=status,
                    log_cb=notes.append)

        self.assertEqual(res, {})
        self.assertEqual(status["kDTree"]["errors"], [],
                         "a user Cancel was filed as a node failure")
        self.assertTrue(any("cancelled" in n for n in notes), notes)
        self.assertFalse(any("failed" in n for n in notes), notes)


def _lock_is_taken(path):
    """True if an exclusive flock is held on ``path``.

    An flock belongs to the OPEN FILE DESCRIPTION, not the process, so a fresh
    ``open()`` here is denied even by a lock this same process is holding -- the
    probe works in-process and needs no child.
    """
    import fcntl

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


if __name__ == "__main__":
    unittest.main()
