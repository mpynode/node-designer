"""Parity re-presents an EARLIER input set, so a mis-keyed cache cannot hide.

Why this is needed at all: the parity loop drives 30 fresh random input sets and
compares against the interpreted node each time. That already catches a cache
that NEVER invalidates -- the compiled output stops tracking immediately. What it
cannot catch is a cache keyed on the wrong thing: correct while inputs keep
moving forward, wrong the moment a previously-seen state comes back. Random draws
essentially never revisit an exact prior state, so the loop is blind to that case
by construction.

The rule is deliberately NOT "the replay must equal the first reading". A node
with persistent state is SUPPOSED to answer differently the second time it sees
the same input; an equality rule would fail it for behaving correctly. The
interpreted node is the reference at every step instead -- it has no C++ cache,
so it always gives the true answer, stateful or not.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


class TestStalenessReason(unittest.TestCase):
    def setUp(self):
        from mpynode.native.toolchain import verify

        self.fn  = verify._staleness_reason
        self.tol = 1e-4

    def test_clean_run_says_nothing(self):
        self.assertIsNone(self.fn(0.0, 0.0, self.tol))
        self.assertIsNone(self.fn(1e-9, 1e-9, self.tol))

    def test_divergence_only_on_the_replay_is_named_as_cache_staleness(self):
        why = self.fn(1e-9, 0.5, self.tol)
        self.assertIsNotNone(why)
        self.assertIn("EARLIER input set", why)
        self.assertIn("cached across evaluations", why)

    def test_an_already_failing_node_gets_no_extra_claim(self):
        """If the loop already diverged, the replay adds no information -- and
        blaming a cache for a plain arithmetic bug is a bad diagnosis."""
        self.assertIsNone(self.fn(0.9, 0.9, self.tol))
        self.assertIsNone(self.fn(0.9, 0.001, self.tol))

    def test_no_replay_and_non_finite_are_ignored(self):
        self.assertIsNone(self.fn(0.0, None, self.tol))
        self.assertIsNone(self.fn(0.0, float("inf"), self.tol))
        self.assertIsNone(self.fn(0.0, float("nan"), self.tol))


class TestApplyDrive(unittest.TestCase):
    def test_scalars_and_arrays_route_to_their_own_driver(self):
        from mpynode.native.toolchain import verify

        calls = []

        class _Cmds:
            pass

        orig_scalar = verify._drive_input
        orig_array  = verify._drive_array_input
        verify._drive_input = lambda c, n, a, t, v: calls.append(
            ("scalar", a, t, v))
        verify._drive_array_input = lambda c, n, a, t, v: calls.append(
            ("array", a, t, v))
        try:
            verify._apply_drive(_Cmds(), ("a", "b"), {
                "gain": ("double", False, 0.5),
                "pts":  ("vector", True, [[0, 0, 0], [1, 1, 1]]),
            })
        finally:
            verify._drive_input       = orig_scalar
            verify._drive_array_input = orig_array

        self.assertIn(("scalar", "gain", "double", 0.5), calls)
        self.assertEqual(len([c for c in calls if c[0] == "array"]), 1)

    def test_the_same_drive_can_be_replayed_verbatim(self):
        """Replay is only meaningful if the recorded set is re-applicable."""
        from mpynode.native.toolchain import verify

        seen                = []
        orig_scalar         = verify._drive_input
        verify._drive_input = lambda c, n, a, t, v: seen.append(v)
        try:
            drive = {"gain": ("double", False, 0.25)}
            verify._apply_drive(None, ("a", "b"), drive)
            verify._apply_drive(None, ("a", "b"), drive)
        finally:
            verify._drive_input = orig_scalar

        self.assertEqual(seen, [0.25, 0.25])


class TestVerifyWiring(unittest.TestCase):
    """_verify_one needs Maya + a compiled bundle, so pin the wiring by source."""

    def _source(self):
        import inspect

        from mpynode.native.toolchain import verify

        return inspect.getsource(verify._verify_one)

    def test_the_first_input_set_is_recorded_and_replayed(self):
        src = self._source()
        self.assertTrue("first_drive" in src,
                        "_verify_one never records an input set to replay")
        self.assertTrue("_apply_drive(cmds, (orig, comp), first_drive)" in src,
                        "_verify_one never re-presents the first input set")

    def test_the_loop_error_is_kept_separate_from_the_replay_error(self):
        """maxerr absorbs replay_err, so the staleness test must compare against
        the PRE-replay figure or it can never fire."""
        src = self._source()
        self.assertTrue("loop_maxerr" in src)
        self.assertTrue("_staleness_reason(loop_maxerr, replay_err, tol)" in src,
                        "staleness must be judged on the pre-replay error")


if __name__ == "__main__":
    unittest.main()
