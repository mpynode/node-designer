"""Array-output ELEMENT LIFETIME is deliberately different interpreted vs compiled.

T14 gave the generated C++ full-rewrite semantics (a fresh sized
``MArrayDataBuilder``); the interpreted writer still takes the datablock's
existing builder and so preserves stale higher indices. T94 resolved that split
as INTENDED -- documented, not converged -- because the interpreted count is
load-bearing in a way the compiled one is not: every api2 base sizes an array
output's pre-seeded buffer from that plug's existing element indices -- inline
in ``_api2/_mpy_node.py`` (mPyNode) and ``_api2/mpy_constraint.py``
(mPyConstraint), via ``output_defaults.seed_user_output_defaults_api2`` for
mesh / nurbs / file -- and four shipped templates read that count straight back
as their N.

The consequence for ``verify.py``: the interpreted reference's element count is
a HIGH-WATER MARK, not the count that evaluation produced, so ``na != nb`` on
its own is no longer evidence of a port bug. It still is when the compiled side
never reached the interpreted count -- which is the classic broken-port
signature and must keep failing.
"""

from __future__ import annotations

import ast
import inspect
import unittest

from ._setup import standalone_init


def setUpModule():
    standalone_init()


def _verify_src():
    from mpynode.native.toolchain import verify

    return inspect.getsource(verify)


def _verify_one_ast():
    for node in ast.parse(_verify_src()).body:
        if isinstance(node, ast.FunctionDef) and node.name == "_verify_one":
            return node
    raise AssertionError("verify._verify_one not found")


def _array_count_block():
    """The `if m.get("is_array"):` statement lifted out of
    ``_verify_one._compare_once`` and compiled.

    ``_compare_once`` is a closure over a live Maya scene, so it cannot be
    called from a unit test -- but its array bookkeeping is what decides
    excused-vs-real, and string-grepping it (what T100 shipped) passes even
    when the high-water mark is taken off the WRONG side. Executing the shipped
    statement is the only way to drive the real decision."""
    for fn in ast.walk(_verify_one_ast()):
        if isinstance(fn, ast.FunctionDef) and fn.name == "_compare_once":
            break
    else:
        raise AssertionError("verify._verify_one._compare_once not found")
    hits = [n for n in ast.walk(fn)
            if isinstance(n, ast.If) and isinstance(n.test, ast.Call)
            and isinstance(n.test.func, ast.Attribute)
            and n.test.func.attr == "get"
            and isinstance(n.test.func.value, ast.Name)
            and n.test.func.value.id == "m"]
    if len(hits) != 1:
        raise AssertionError("expected one `m.get(...)` branch, found %d"
                             % len(hits))
    mod = ast.Module(body=[hits[0]], type_ignores=[])
    ast.fix_missing_locations(mod)
    return compile(mod, "<verify._compare_once>", "exec")


def _drive_sweep(pairs, out="values"):
    """Replay a sweep of ``(interpreted_count, compiled_count)`` readings
    through the SHIPPED bookkeeping. Returns ``(stale_tail, count_mismatch)``."""
    from mpynode.native.toolchain import verify

    code = _array_count_block()
    ns = {"m": {"is_array": True}, "o": out, "out_hiwater": {},
          "stale_tail": {}, "count_mismatch": {},
          "_is_stale_tail_shrink": verify._is_stale_tail_shrink}
    for na, nb in pairs:
        ns["na"], ns["nb"] = na, nb
        exec(code, ns)
    return ns["stale_tail"], ns["count_mismatch"]


class TestInterpretedWriterDocumentsTheContract(unittest.TestCase):
    """T94 asked for the contract to be WRITTEN DOWN, not implicit. The
    interpreted writer is where someone reading ``self.out = [...]`` lands."""

    def _doc(self):
        from mpynode._api2 import helpers

        return inspect.getdoc(helpers.write_multi_plug_value) or ""

    def test_it_names_the_compiled_side_and_the_divergence(self):
        doc = self._doc()
        self.assertIn("emit_attr", doc,
                      "the contract must point at the other half of it")
        low = doc.lower()
        self.assertIn("drop", low, "the compiled side DROPS unwritten elements")
        self.assertIn("high-water", low,
                      "the interpreted count is a high-water mark -- say so")

    def test_it_records_the_empty_buffer_exception(self):
        """A compute that writes NOTHING is a NO-OP on the compiled side too
        (``if (!out_x.empty())``), so the contract is 'short write drops the
        tail', not 'every eval rewrites'. Stating it as an unconditional
        rewrite would be wrong."""
        doc = self._doc()
        self.assertIn("empty", doc.lower())

    def test_it_says_why_the_interpreted_side_was_not_converged(self):
        """The pre-seed is the reason preservation is load-bearing, so the doc
        has to name the sites that actually perform it for the templates it
        cites. All six go through an INLINE pre-seed, not through
        ``seed_user_output_defaults_api2`` (that one serves mesh / nurbs /
        file): bubbleSort / spline / springChain / spine / mPyDnet are mPyNode
        and procrustesCluster is mPyConstraint."""
        doc = self._doc()
        self.assertIn("_mpy_node.py", doc,
                      "mPyNode pre-seeds inline -- name that site")
        self.assertIn("mpy_constraint.py", doc,
                      "mPyConstraint pre-seeds inline -- name that site")
        self.assertIn("seed_user_output_defaults_api2", doc,
                      "and name the shared helper the geometry bases use")


class TestStaleTailShrinkIsRecognised(unittest.TestCase):
    """The predicate verify.py uses to tell the KNOWN divergence apart from a
    real port bug. ``hiwater`` is the largest element count the COMPILED node
    has produced so far in the sweep."""

    def _p(self):
        from mpynode.native.toolchain import verify

        return verify._is_stale_tail_shrink

    def test_a_shrink_from_a_count_the_compiled_side_did_reach_is_known(self):
        # compiled produced 4 earlier, produces 2 now; interpreted still
        # reports its preserved 4. Exactly the T14/T94 gap: a SHORT write drops
        # its tail. T94 is the user's landed decision -- this must stay excused.
        self.assertIs(self._p()(4, 2, 4), True)
        self.assertIs(self._p()(4, 3, 4), True)

    def test_a_shrink_to_ZERO_is_a_WIPE_and_is_never_excused(self):
        """T101. ``emit_attr`` guards the rewrite with
        ``if (!out_<mem>.empty())``, so an evaluation that assigns NOTHING is a
        no-op and the compiled array keeps every element it had (pinned live by
        ``test_array_output_builder.test_guard_false_keeps_the_array``). A
        compiled count of 0 after the node has produced more is therefore
        UNREACHABLE while the guard stands -- it is the T96 wipe, not a tail
        drop, and excusing it is what made the guard's revert invisible."""
        self.assertIs(self._p()(4, 0, 4), False)
        self.assertIs(self._p()(1, 0, 1), False)

    def test_a_compiled_side_that_never_reached_the_count_is_a_real_mismatch(self):
        """Python 4 vs compiled 2 on EVERY evaluation is a broken port, not a
        shrink -- the compiled high-water never got to 4."""
        self.assertIs(self._p()(4, 2, 2), False)

    def test_a_compiled_side_that_produced_nothing_at_all_is_a_real_mismatch(self):
        self.assertIs(self._p()(4, 0, 0), False)

    def test_a_compiled_side_that_produced_MORE_is_never_excused(self):
        self.assertIs(self._p()(0, 4, 4), False)
        self.assertIs(self._p()(2, 4, 4), False)

    def test_equal_counts_are_not_a_divergence_at_all(self):
        self.assertIs(self._p()(4, 4, 4), False)

    def test_a_broken_port_stays_red_for_the_WHOLE_sweep(self):
        """Replay a sweep the way the parity loop does -- running high-water of
        the compiled count -- for a port that is systematically 2 short. Every
        iteration must stay a real mismatch; one benign classification would
        let the node ship."""
        p, hw = self._p(), 0
        for _ in range(5):
            na, nb = 4, 2
            hw = max(hw, nb)
            self.assertIs(p(na, nb, hw), False)

    def test_the_procrustes_shaped_sweep_is_benign_end_to_end(self):
        """A procrustes-shaped sweep must not raise a single false failure: ten
        evaluations with nothing to write, one that writes 4, then a mix of
        assigns-nothing and short evaluations.

        An assigns-nothing evaluation reads back 4 on BOTH sides -- the
        interpreted node reports its pre-seeded 4, the compiled node is a no-op
        under the ``empty()`` guard -- so it does not diverge at all. Every
        divergence left in the shape is a genuine short write, and those stay
        excused (T94)."""
        p, hw, real = self._p(), 0, []
        for na, nb in ([(0, 0)] * 10 + [(4, 4)] + [(4, 4), (4, 2)] * 5):
            hw = max(hw, nb)
            if na != nb and not p(na, nb, hw):
                real.append((na, nb, hw))
        self.assertEqual(real, [])


class TestTheParityLoopUsesIt(unittest.TestCase):
    """Driven, not grepped: every case below EXECUTES the shipped
    ``_compare_once`` bookkeeping (see :func:`_array_count_block`)."""

    def test_the_predicate_is_wired_into_the_compare_loop(self):
        from mpynode.native.toolchain import verify

        src = inspect.getsource(verify)
        self.assertEqual(src.count("def _is_stale_tail_shrink"), 1)
        self.assertIn("_is_stale_tail_shrink(na, nb,", src,
                      "the compare loop must consult it")

    def test_a_known_divergence_is_reported_not_swallowed(self):
        stale, mismatch = _drive_sweep([(4, 4), (4, 2)])
        self.assertEqual(stale, {"values": (4, 2)},
                         "a benign divergence still has to be visible in the row")
        self.assertEqual(mismatch, {})

    def test_a_wipe_after_the_compiled_side_reached_the_count_still_FAILS(self):
        """T101, end to end through the real loop. Revert the ``emit_attr``
        ``empty()`` guard and this is the shape the sweep sees: the compiled
        node produced 4, then a guard-false evaluation clears the array."""
        stale, mismatch = _drive_sweep([(4, 4), (4, 4), (4, 0)])
        self.assertEqual(mismatch, {"values": (4, 0)},
                         "the T96 wipe must reach _pick_count_verdict")
        self.assertEqual(stale, {})

    def test_the_high_water_is_the_COMPILED_count_not_the_interpreted_one(self):
        """A port that is systematically 2 short across the whole sweep. Taking
        the high-water off ``na`` instead of ``nb`` would make every reading
        ``na == hiwater`` and excuse the lot -- the exact miscomputation the old
        string-grep could not see."""
        stale, mismatch = _drive_sweep([(4, 2)] * 5)
        self.assertEqual(mismatch, {"values": (4, 2)})
        self.assertEqual(stale, {})

    def test_a_non_array_output_is_never_length_checked(self):
        from mpynode.native.toolchain import verify

        code = _array_count_block()
        ns = {"m": {}, "o": "scalar", "na": 4, "nb": 0, "out_hiwater": {},
              "stale_tail": {}, "count_mismatch": {},
              "_is_stale_tail_shrink": verify._is_stale_tail_shrink}
        exec(code, ns)
        self.assertEqual(
            (ns["stale_tail"], ns["count_mismatch"], ns["out_hiwater"]),
            ({}, {}, {}))


class TestAnExcusedShrinkIsNeverSilent(unittest.TestCase):
    """``_verify_one`` promises "Excused, but never silent". The note used to be
    appended on the LAST return only, so an excused shrink vanished from a
    vacuous row, a beyond-ceiling row, and -- worst -- a row that also carried a
    real count mismatch, which is precisely where a reader needs both facts."""

    def _h(self):
        from mpynode.native.toolchain import verify

        return verify._with_stale_tail

    def test_the_note_names_every_output_and_both_counts(self):
        txt = self._h()("", {"values": (4, 2), "alpha": (3, 1)})
        self.assertIn("values Python 4 vs compiled 2", txt)
        self.assertIn("alpha Python 3 vs compiled 1", txt)

    def test_it_is_appended_to_an_existing_reason(self):
        txt = self._h()("already said something", {"values": (4, 2)})
        self.assertTrue(txt.startswith("already said something -- "), txt)
        self.assertIn("values Python 4 vs compiled 2", txt)

    def test_no_excused_shrink_leaves_the_reason_byte_identical(self):
        self.assertEqual(self._h()("a reason", {}), "a reason")
        self.assertEqual(self._h()("", {}), "")

    def test_every_post_sweep_return_carries_it(self):
        """Resolve the ``reason`` of every ``_verify_one`` return reachable
        once ``stale_tail`` exists, and require it to have gone through the
        helper. Dropping any one call site turns this red."""
        fn = _verify_one_ast()
        bind = min(n.lineno for n in ast.walk(fn)
                   if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "stale_tail"
                           for t in n.targets))
        assigns = {}
        for n in ast.walk(fn):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)):
                assigns.setdefault(n.targets[0].id, []).append((n.lineno, n.value))
        for v in assigns.values():
            v.sort()

        def _nearest_above(name, lineno):
            # ast.walk is breadth-first, so "the last one seen" is arbitrary --
            # `row` is rebound on several earlier return paths.
            return [val for ln, val in assigns.get(name, ()) if ln <= lineno]

        def _reason_of(value):
            if isinstance(value, ast.Dict):
                for k, v in zip(value.keys, value.values):
                    if isinstance(k, ast.Constant) and k.value == "reason":
                        return v
            return None

        def _is_wrapped(expr):
            return (isinstance(expr, ast.Call)
                    and isinstance(expr.func, ast.Name)
                    and expr.func.id == "_with_stale_tail")

        checked = []
        for n in ast.walk(fn):
            if not isinstance(n, ast.Return) or n.lineno < bind:
                continue
            val = n.value
            if isinstance(val, ast.Name):
                bound = [b for b in map(_reason_of,
                                        _nearest_above(val.id, n.lineno))
                         if b is not None]
                if not bound:
                    continue
                val = bound[-1]
            else:
                val = _reason_of(val)
                if val is None:
                    continue
            exprs = ([v for _ln, v in assigns.get(val.id, ())]
                     if isinstance(val, ast.Name) else [val])
            checked.append(n.lineno)
            self.assertTrue(
                any(_is_wrapped(e) for e in exprs),
                "verify.py:%d returns a reason that never passes through "
                "_with_stale_tail -- an excused shrink is silent on that path"
                % n.lineno)
        self.assertEqual(len(checked), 5,
                         "expected the 5 post-sweep reason returns "
                         "(count_mismatch / diverge-ceiling / carry-drift / "
                         "vacuous / normal), found %r" % (checked,))


class TestTheRealFailuresAreUntouched(unittest.TestCase):
    """Guard rail: the count verdicts T-unassigned-honesty pinned must not have
    been 'fixed' by relaxing _count_mismatch_reason instead."""

    def test_an_empty_compiled_side_is_still_a_hard_fail(self):
        from mpynode.native.toolchain import verify

        ran, passed, _t = verify._count_mismatch_reason(
            "output", 4, 0, geo_wired_any=True, unassigned=set())
        self.assertTrue(ran)
        self.assertFalse(passed)

    def test_an_invented_output_is_still_a_hard_fail(self):
        from mpynode.native.toolchain import verify

        ran, passed, text = verify._count_mismatch_reason(
            "distance", 0, 4, geo_wired_any=True, unassigned={"distance"})
        self.assertTrue(ran)
        self.assertFalse(passed)
        self.assertIn("never assigns", text)


if __name__ == "__main__":
    unittest.main()
