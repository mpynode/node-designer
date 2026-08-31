"""ONE definition of "the candidate is the incumbent", used by both readers.

Two places answer the same question and used to answer it differently:

* the engine's no-change gate (``optimizer.optimize_cpp``) compares STRIPPED,
  because the one-shot path returns ``prompt._extract_body(...)``, which strips
  -- so a model that echoes the file back verbatim differs from the on-disk
  baseline by exactly the trailing newline, and an exact ``==`` would miss it;
* ``optimizer_live``'s ``candidates`` counter compared EXACTLY, so that same
  echo scored a candidate.

The measured cost is at RUN level: in a mixed batch where node A's agent dies
(0 candidates + a recorded error) and node B merely echoes, the echo's phantom
candidate makes ``delivered`` non-zero and SUPPRESSES the "AI never ran"
verdict -- the build comes back ok having optimized nothing.
"""

from __future__ import annotations

import tempfile
import unittest

from tests._setup import standalone_init
from mpynode.native.ai import optimizer, optimizer_live


def _setUpModule__unchanged_definition():
    standalone_init()


setUpModule = _setUpModule__unchanged_definition


_SPEC = {"suggested": {"node_type_name": "mPyThing", "mpx_base": "MPxNode"},
         "compute": "self.out = self.a ** 2", "init": ""}

# As it is read off disk: a real .cpp ends with a newline. That newline IS the
# whole difference an echoed answer comes back with.
_BASELINE_CPP = "void f(){ return; }\n"


def _echo(system, user):
    """A model that answers with the file it was given, fenced (the shape the
    one-shot path really receives). ``_extract_body`` strips the fence AND the
    surrounding whitespace, so what comes back is the baseline minus its
    trailing newline."""
    return "```cpp\n%s```" % _BASELINE_CPP


def _dead_agent(prompt):
    from mpynode.native.ai.llm_client import AgentUnavailable

    raise AgentUnavailable("sandbox_apply: Operation not permitted")


def _status_from(tmp, **over):
    """Run ONE real optimize round through the real adapters; return its
    status dict (what the run-level verdict is later computed from)."""
    kw = dict(maya="/x", run_step=lambda s, a, p, t: (None, False, ""))
    kw.update(over)
    status = {}
    ad = optimizer_live.make_adapters(_SPEC, tmp, status_out=status, **kw)
    out = ad["optimize_fn"](_BASELINE_CPP)
    return status, out


class TestTheTwoReadersAgree(unittest.TestCase):
    def test_a_verbatim_echo_is_not_counted_as_a_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out = _status_from(tmp, complete_fn=_echo)

        self.assertNotEqual(out, _BASELINE_CPP,
                            "the premise: _extract_body strips, so an echo is "
                            "not byte-equal to what went in")
        self.assertEqual(status["candidates"], 0,
                         "an echoed file is not a candidate -- the engine's "
                         "own gate already calls it 'no-change'")

    def test_the_engine_calls_that_same_answer_no_change(self):
        """The other half of the pair, pinned: whatever the counter decides,
        the engine must reach the same verdict on the same two strings."""
        with tempfile.TemporaryDirectory() as tmp:
            _status, cand = _status_from(tmp, complete_fn=_echo)

        res = optimizer.optimize_cpp(
            _BASELINE_CPP, rounds=1,
            optimize_fn=lambda cpp: cand,
            fix_fn=lambda cpp, err: cpp,
            compile_fn=lambda cpp: (True, "", "bundle"),
            parity_fn=lambda b: optimizer.ParityVerdict(optimizer.PARITY_PASS),
            benchmark_fn=lambda b: 10.0)

        self.assertEqual([r.outcome for r in res.ledger],
                         ["baseline", "no-change"])

    def test_a_real_edit_is_still_a_candidate(self):
        """The strip must not swallow a genuine rewrite -- only whole-file
        leading/trailing whitespace is ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            status, out = _status_from(
                tmp, complete_fn=lambda s, u: "```cpp\nvoid f(){ int x=1; }\n```")

        self.assertNotEqual(out.strip(), _BASELINE_CPP.strip())
        self.assertEqual(status["candidates"], 1)


class TestTheMixedBatchVerdict(unittest.TestCase):
    """A dead provider on node A and an echo on node B: the run delivered
    nothing, and must not report otherwise."""

    def _statuses(self):
        with tempfile.TemporaryDirectory() as a, \
                tempfile.TemporaryDirectory() as b:
            dead, _out_a = _status_from(a, agent_fn=_dead_agent)
            echo, _out_b = _status_from(b, complete_fn=_echo)
        return dead, echo

    def test_the_echo_does_not_rescue_the_run(self):
        from tests.compile.pipeline.test_ai_unavailable_status import (
            TestTheRunLevelVerdict)

        dead, echo = self._statuses()
        # The premise of the batch: node A recorded a real failure...
        self.assertTrue(dead["errors"], dead)
        self.assertEqual(dead["candidates"], 0)
        # ...and node B produced nothing either, whatever it looks like.
        self.assertEqual(echo["errors"], [])

        result, _events = TestTheRunLevelVerdict._run(
            self, status={"nodeA": dead, "nodeB": echo})

        self.assertFalse(result["ok"],
                         "an echoed file made 'delivered' non-zero and hid the "
                         "fact that the AI optimized nothing")
        self.assertIn("ai_optimize_failed", result)
        self.assertTrue(result["bundle_path"],
                        "the deterministic bundle is still real")


if __name__ == "__main__":
    unittest.main()
