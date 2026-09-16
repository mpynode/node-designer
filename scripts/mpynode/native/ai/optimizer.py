"""The AI C++ optimizer orchestration engine.

A pure, side-effect-injected loop that rewrites a compiled node's C++ for speed
and accepts a candidate ONLY if it (1) compiles, (2) still matches the
interpreted Python (parity PASS -- a SKIP is NOT a pass), AND (3) is measurably
faster than the current best. Otherwise it keeps the original C++ unchanged
(honest reject). It can never ship a faster-but-wrong or slower node.

Every side effect is a caller-supplied function, so this module imports no LLM /
Maya / compiler and is fully unit-testable with stubs:
  * optimize_fn(cpp) -> candidate_cpp        propose a faster whole-file .cpp
  * fix_fn(cpp, errors) -> candidate_cpp     repair a non-compiling candidate
  * compile_fn(cpp) -> (ok, log, bundle)     build the candidate
  * parity_fn(bundle) -> ParityVerdict       compiled-vs-interpreted parity
  * benchmark_fn(bundle) -> ms | None        median wall-clock (None=unmeasurable)

The live bindings for these live in ``optimizer_live`` (lazy Maya/LLM imports).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional


# Parity verdict statuses. SKIP means "could not be checked" -- it is NEVER a
# pass; the optimizer refuses to accept a candidate it cannot prove correct.
PARITY_PASS = "pass"
PARITY_FAIL = "fail"
PARITY_SKIP = "skip"


class BenchmarkDiverged(RuntimeError):
    """Raised by a ``benchmark_fn`` when the candidate's OUTPUTS on the bench
    scene differ from the baseline's on that same scene.

    Speed is only comparable between two programs that computed the same thing.
    A candidate that early-outs where the baseline grinds (an inconsistent
    random scene the authored ``@maya_test`` never sees) is not faster, it is
    doing less -- spline "3698x" and comboCorrectives "258x" were that. The
    engine records it as its own outcome (``bench-diverged``) rather than as
    "unmeasurable", because the difference matters to a reader.
    """


@dataclass
class ParityVerdict:
    status: str
    maxerr: Optional[float] = None
    reason: str = ""


def is_unchanged(candidate: str, current: str) -> bool:
    """Whether ``candidate`` IS the incumbent source rather than a new one.

    The single definition, because there are two readers: the no-change gate
    below, and ``optimizer_live``'s ``candidates`` counter (which feeds the
    run-level "the AI never delivered anything" verdict). They disagreed --
    exact there, stripped here -- so a verbatim echo scored a candidate while
    the gate recorded it as no-change, and one node's phantom candidate
    suppressed the verdict for a whole batch.

    Only whole-file leading/trailing whitespace is ignored: the one-shot path
    returns ``prompt._extract_body(...)``, which strips, so a model that echoes
    the file back differs from the on-disk baseline by a trailing newline and
    exact ``==`` would miss it. Nothing is normalised per line -- a change to
    any line, whitespace included, still reads as a real edit, because
    discarding a real optimization costs more than spending one round measuring
    a cosmetic one.
    """
    return candidate.strip() == current.strip()


@dataclass
class RoundRecord:
    index:      int  # 0 = baseline, 1.. = optimize rounds
    outcome:    str  # "baseline" / "accept" / "parity-fail" / ...
    note:       str = ""
    compiled:   Optional[bool] = None
    parity:     Optional[str] = None
    ms:         Optional[float] = None
    speedup:    Optional[float] = None
    fix_rounds: int = 0
    # What the optimizer SAID it was doing, from round_meta_fn. `slug` is a short
    # theme name and doubles as the version filename; `predicted_speedup` is
    # recorded BEFORE the measurement so the report can show predicted vs actual --
    # the divergences are the useful part.
    slug:              Optional[str] = None
    theme:             str = ""
    hypothesis:        str = ""
    predicted_speedup: Optional[float] = None
    risk:              str = ""
    duration_s:        Optional[float] = None
    # Where THIS round's binary was built -- a scratch path with the lifetime of
    # the run. Handed to round_cb so a caller can keep the artifact, and kept OUT
    # of the durable ledger, where it would be a lie by the time anyone read it.
    bundle: Optional[str] = None


@dataclass
class OptimizeResult:
    accepted:    bool
    best_cpp:    str
    baseline_ms: Optional[float]
    best_ms:     Optional[float]
    speedup:     float
    rounds:      int                # rounds actually RUN (the loop is adaptive)
    ledger:      List[RoundRecord] = field(default_factory=list)
    reason:      str = ""
    # ``max_rounds`` is the cap the caller set; ``stop_reason`` says why the loop
    # ended ("round 3 not-faster -- ...", "round 2 gained 1.08x, below ...",
    # "max rounds (6) reached"). Both empty/0 on ledgers from the fixed-count era.
    max_rounds:  int = 0
    stop_reason: str = ""


def _log(log_cb, msg):
    if log_cb is not None:
        try:
            log_cb(msg)
        except Exception:
            pass


def _fetch_meta(round_meta_fn):
    """What the optimizer SAYS it just attempted, or ``{}``.

    Never fatal. This is report material -- a node must not lose a real
    optimization because its narrator misbehaved.
    """
    if round_meta_fn is None:
        return {}
    try:
        return dict(round_meta_fn() or {})
    except Exception:
        return {}


def _round_intent(tag, i, rounds, meta):
    """One line saying what this round is ATTEMPTING, before it is judged.

    The outcome lines report what happened; this reports the claim, so the two
    read as a pair ("trying X, predicted 3x" then "1.84x"). Returns ``None``
    when the optimizer stated no theme -- saying nothing beats a hollow line.
    """
    theme = (meta.get("theme") or "").strip()
    if not theme:
        return None
    bits = []
    pred = meta.get("predicted_speedup")
    if pred:
        bits.append("predicted %.2fx" % pred)
    if meta.get("risk"):
        bits.append("risk: %s" % meta["risk"])
    return "%sround %d/%d trying: %s%s" % (
        tag, i, rounds, theme, (" (%s)" % ", ".join(bits)) if bits else "")


def _offer_history(history_sink, ledger):
    """Hand the rounds resolved SO FAR to the caller, before the next proposal.

    The mirror image of ``round_meta_fn``, which already carries data the other
    way (adapter -> engine). It exists because each optimize round is a FRESH
    process with no memory of the last: a rejected round leaves nothing behind,
    so the next one can re-propose the idea that just lost.

    A COPY is passed, never the engine's own list -- this is read-only context,
    and a sink that mutates its argument must not be able to blank the ledger
    that becomes rounds.json. Never fatal, for the same reason ``_fetch_meta``
    is not: context is report material, and a node must not lose a real
    optimization because its narrator misbehaved.
    """
    if history_sink is None:
        return
    try:
        history_sink(list(ledger))
    except Exception:
        pass


def _stop_reason(done, ended, floor_rounds, continue_gain):
    """Why round ``done + 1`` should NOT start, or ``None`` to continue.

    ``done`` rounds have run; ``ended`` is how the last one finished. Inside the
    guaranteed ``floor_rounds`` the answer is always continue -- a no-change or
    a reject there is not proof of a spent optimizer, and abandoning the node
    on it would skip exactly the hard ones worth a second attempt.
    """
    if done < floor_rounds:
        return None
    outcome = ended.get("outcome")
    if outcome != "accept":
        return ("round %d %s -- nothing new to compound from"
                % (done, outcome or "did not resolve"))
    gain = ended.get("gain")
    if gain is not None and gain < continue_gain:
        return ("round %d gained %.2fx, below the %.2fx needed to continue"
                % (done, gain, continue_gain))
    return None


def _emit_round(round_cb, record, cpp_text):
    """Hand a resolved round (and the source it produced) to the caller."""
    if round_cb is None:
        return
    try:
        round_cb(record, cpp_text)
    except Exception:
        pass


def _compile_with_fixes(cpp, compile_fn, fix_fn, max_fix_rounds, log_cb=None,
                        tag="", validate_fn=None):
    """Compile ``cpp``; on failure feed the compiler errors to ``fix_fn`` up to
    ``max_fix_rounds`` times. Returns (ok, log, bundle, cpp, fix_rounds).

    A fix whose output ``validate_fn`` rejects is DISCARDED and the loop stops
    with the last known-good ``cpp``. Feeding a corrupt candidate back in only
    produced a second corrupt candidate.
    """
    ok, log, bundle = compile_fn(cpp)
    fixes = 0
    while not ok and fixes < max_fix_rounds:
        fixes += 1
        cand = fix_fn(cpp, log)
        why  = validate_fn(cand, cpp) if validate_fn else None
        if why:
            _log(log_cb, "%sfix round %d rejected: %s" % (tag, fixes, why))
            return ok, log, bundle, cpp, fixes
        cpp = cand
        ok, log, bundle = compile_fn(cpp)
    return ok, log, bundle, cpp, fixes


def optimize_cpp(baseline_cpp: str, *,
                 optimize_fn:    Callable[[str], str],
                 fix_fn:         Callable[[str, str], str],
                 compile_fn:     Callable[[str], tuple],
                 parity_fn:      Callable[[str], ParityVerdict],
                 benchmark_fn:   Callable[[str], Optional[float]],
                 rounds:         int                                           = 3,
                 min_speedup:    float                                         = 1.05,
                 max_fix_rounds: int                                           = 2,
                 min_rounds:     int                                           = 2,
                 continue_gain:  float                                         = 1.15,
                 resolution_ms:  float                                         = 2.0,
                 confirm_gain:   float                                         = 1.15,
                 label:          str                                           = "",
                 log_cb                                                        = None,
                 validate_fn:    Optional[Callable[[str, str], Optional[str]]]
                 = None,
                 round_meta_fn: Optional[Callable[[], dict]] = None,
                 round_cb                                    = None,
                 history_sink: Optional[Callable[[List[RoundRecord]],
                                                 None]] = None,
                 accept_check_fn: Optional[Callable[[str, str],
                                                    Optional[str]]] = None,
                 resolution_fn: Optional[Callable[[], Optional[float]]] = None
                 ) -> OptimizeResult:
    """Optimize ``baseline_cpp`` under the parity+speed gate. See module docstring.

    Accepts a candidate iff it compiles, parity is PASS, its outputs on the bench
    scene match the baseline's (``benchmark_fn`` raises :class:`BenchmarkDiverged`
    otherwise), and it is faster than the current best by at least
    ``min_speedup`` (candidate_ms < best_ms / min_speedup).
    Each round proposes FROM the current best, so accepted rounds compound. On any
    failure the ORIGINAL ``baseline_cpp`` is returned unchanged (honest reject).

    ``rounds`` is the MAXIMUM. The loop is adaptive: it always runs
    ``min_rounds`` (clamped to ``rounds``), then continues only while the last
    round was ACCEPTED and its gain over the incumbent it replaced was at least
    ``continue_gain``; the first reject past ``min_rounds`` ends it. Measured on
    the shipped ledgers (2026-09): 20 of 29 nodes accepted both of a fixed 2
    rounds -- median gain of the second 1.58x, five of them larger than the
    first -- so the cap was binding, while a reject was almost never followed
    by an accept. The result records ``stop_reason`` and the rounds RUN.

    Below ``resolution_ms`` the incumbent sits inside the benchmark's own jitter
    (~8% at 0.4 ms), where ``min_speedup`` alone would accept noise. There a
    candidate must beat the incumbent by ``confirm_gain`` AND do so again on a
    second, independent ``benchmark_fn`` call; the SLOWER of the two is what is
    recorded. One extra benchmark, only at that size.

    ``resolution_fn() -> ms | None`` lets the benchmark adapter widen that band
    per node once it has calibrated: the live binding returns ``inf`` for a
    node whose baseline stayed under the noise floor even at the largest bench
    scene (5 of the 8 shipped deformer/skin nodes, 5.9-14.1 ms), so EVERY
    accept for it needs ``confirm_gain`` twice -- measured rather than declared
    unmeasurable, without letting noise through. ``None`` keeps
    ``resolution_ms``.

    ``validate_fn(candidate, current) -> reason | None`` is an OPTIONAL cheap
    pre-check applied to whatever the model returns, before spending a compile
    on it. It keeps this module content-agnostic: the live binding supplies
    ``optimizer_knowledge.implausible_reason`` (truncated / prose answers),
    while stub-driven tests inject nothing.

    ``round_meta_fn() -> dict`` is called once per round, right after
    ``optimize_fn``, for what the optimizer says it just attempted
    (``slug`` / ``theme`` / ``hypothesis`` / ``predicted_speedup`` / ``risk``).
    ``round_cb(record, cpp_text)`` receives EVERY resolved round -- accepted,
    rejected or errored -- with the source it produced. Rejected rounds matter
    most: "structure-of-arrays made it 2x slower" is only learnable if the
    attempt was kept. Both are optional and neither can fail a round.

    ``accept_check_fn(candidate_bundle, incumbent_bundle) -> reason | None``
    is an OPTIONAL last gate on a candidate that has already passed parity and
    beaten the incumbent on the calibrated scene. The live binding re-times
    both on the ladder's smallest scene when calibration climbed past it: a
    design that wins at 8k vertices by dropping a cache can lose 2x at 1.5k
    (rbfWrapDeformer, 2026-09-09). A reason rejects the round as
    ``regressed``; a :class:`BenchmarkDiverged` raised from it is recorded as
    ``bench-diverged``.

    ``history_sink(ledger_so_far)`` is called once per round, BEFORE
    ``optimize_fn``, with the rounds already resolved. Without it a round is
    handed only the current-best source, so a REJECTED idea leaves no trace and
    the next round can spend itself re-proposing it. Optional, because
    ``optimize_fn`` is a one-argument contract that predates this.
    """
    ledger: List[RoundRecord] = []
    tag = ("[%s] " % label) if label else ""

    # Baseline: already-shipped, trusted C++, so it is NOT re-parity-checked (the
    # reference is the interpreted Python). It only has to compile and benchmark so
    # candidates have a speed target. If it can't, optimizing is a safe no-op.
    b_ok, _b_log, b_bundle, _b_cpp, _b_fx = _compile_with_fixes(
        baseline_cpp, compile_fn, fix_fn, 0, log_cb=log_cb, tag=tag)
    def _baseline(note, **kw):
        rec = RoundRecord(0, "baseline", note, **kw)
        ledger.append(rec)
        _emit_round(round_cb, rec, baseline_cpp)
        return rec

    if not b_ok:
        _log(log_cb, "%sbaseline did not compile; skipping optimization" % tag)
        _baseline("did not compile", compiled=False)
        return OptimizeResult(False, baseline_cpp, None, None, 1.0, 0, ledger,
                              "baseline did not compile", max_rounds=rounds,
                              stop_reason="baseline did not compile")
    baseline_ms = benchmark_fn(b_bundle)
    if baseline_ms is None:
        _log(log_cb, "%sbaseline could not be benchmarked; skipping" % tag)
        _baseline("unmeasurable", compiled=True)
        return OptimizeResult(False, baseline_cpp, None, None, 1.0, 0, ledger,
                              "baseline could not be benchmarked",
                              max_rounds=rounds,
                              stop_reason="baseline could not be benchmarked")
    _baseline("", compiled=True, ms=baseline_ms, bundle=b_bundle)
    floor_rounds = max(0, min(min_rounds, rounds))
    _log(log_cb, "%sbaseline %.3f ms; up to %d optimize round(s) (at least %d; "
         "stops after a rejected round or a gain under %.2fx)"
         % (tag, baseline_ms, rounds, floor_rounds, continue_gain))

    best_cpp    = baseline_cpp
    best_ms     = baseline_ms
    best_bundle = b_bundle
    rounds_run  = 0
    stop_reason = ""
    # How the PREVIOUS round ended, for the stop rule: its outcome, and for an
    # accept the gain over the incumbent it replaced.
    ended = {"outcome": None, "gain": None}

    for i in range(1, rounds + 1):
        if i > 1:
            why = _stop_reason(i - 1, ended, floor_rounds, continue_gain)
            if why:
                stop_reason = why
                _log(log_cb, "%sstopping after round %d: %s" % (tag, i - 1, why))
                break
        rounds_run = i
        started    = time.time()
        meta       = {}
        cand       = None
        ended      = {"outcome": None, "gain": None}

        def _round(outcome, **kw):
            """Record one resolved round, stamped with what it claimed to do.

            One place rather than seven, so a new outcome cannot silently ship
            without its theme, its timing, or its source.
            """
            rec = RoundRecord(
                i, outcome,
                duration_s=round(time.time() - started, 3),
                slug=(meta.get("slug") or None),
                theme=(meta.get("theme") or ""),
                hypothesis=(meta.get("hypothesis") or ""),
                predicted_speedup=meta.get("predicted_speedup"),
                risk=(meta.get("risk") or ""),
                **kw)
            ledger.append(rec)
            ended["outcome"] = outcome
            _emit_round(round_cb, rec, cand)
            return rec

        # Before the proposal, not after: a round informed by history it has
        # not been handed yet is the whole defect this closes.
        _offer_history(history_sink, ledger)

        # Say the round BEGAN. `_round_intent` below cannot: the theme comes from
        # the optimizer, so it does not exist until the blocking call below returns
        # -- possibly tens of minutes. Otherwise the first sign is the outcome.
        _log(log_cb, "%sround %d/%d starting" % (tag, i, rounds))

        try:
            cand   = optimize_fn(best_cpp)
            meta   = _fetch_meta(round_meta_fn)
            intent = _round_intent(tag, i, rounds, meta)
            if intent:
                _log(log_cb, intent)
            # Reject a truncated / prose answer BEFORE spending a compile and a
            # fix round on it.
            why = validate_fn(cand, best_cpp) if validate_fn else None
            if why:
                _log(log_cb, "%sround %d: invalid candidate (%s)" % (tag, i, why))
                _round("invalid-candidate", note=why)
                continue
            # A candidate identical to the incumbent is not a candidate. Left to
            # run it re-compiles and re-benchmarks the SAME bytes, so timing
            # jitter alone decides -- that is how an "accept" at 1.15x got
            # recorded against a file byte-identical to its own baseline. Judged
            # BEFORE compile / parity / benchmark are spent on it. See
            # ``is_unchanged`` for why the comparison is stripped.
            if is_unchanged(cand, best_cpp):
                _log(log_cb, "%sround %d: no change to the source" % (tag, i))
                _round("no-change",
                       note="candidate is identical to the current best")
                continue
            ok, log, bundle, cand, fx = _compile_with_fixes(
                cand, compile_fn, fix_fn, max_fix_rounds, log_cb=log_cb, tag=tag,
                validate_fn=validate_fn)
            if not ok:
                _log(log_cb, "%sround %d: did not compile" % (tag, i))
                _round("compile-failed", compiled=False, fix_rounds=fx)
                continue
            verdict = parity_fn(bundle)
            if verdict.status != PARITY_PASS:
                _log(log_cb, "%sround %d: parity %s" % (tag, i, verdict.status))
                _round("parity-%s" % verdict.status, note=verdict.reason,
                       compiled=True, parity=verdict.status, fix_rounds=fx,
                       bundle=bundle)
                continue
            try:
                ms = benchmark_fn(bundle)
            except BenchmarkDiverged as exc:
                _log(log_cb, "%sround %d: outputs diverge from the baseline on "
                     "the bench scene -- %s" % (tag, i, exc))
                _round("bench-diverged", note=str(exc), compiled=True,
                       parity=PARITY_PASS, fix_rounds=fx, bundle=bundle)
                continue
            if ms is None:
                _log(log_cb, "%sround %d: unmeasurable" % (tag, i))
                _round("unmeasurable", compiled=True, parity=PARITY_PASS,
                       fix_rounds=fx, bundle=bundle)
                continue
            note = ""
            band = resolution_ms
            if resolution_fn is not None:
                try:
                    widened = resolution_fn()
                except Exception:
                    widened = None
                if widened is not None:
                    band = float(widened)
            band_label = ("under the noise floor" if band == float("inf")
                          else "under %g ms" % band)
            if ms < best_ms / min_speedup and best_ms < band:
                # The incumbent is inside the benchmark's own jitter, where
                # min_speedup alone would accept noise: demand confirm_gain,
                # and demand it twice, on independent measurements.
                need = best_ms / confirm_gain
                if not (ms < need):
                    _log(log_cb, "%sround %d: %.3f ms vs best %.3f ms is inside "
                         "the noise band (incumbent %s; needs %.2fx)"
                         % (tag, i, ms, best_ms, band_label, confirm_gain))
                    _round("not-faster", compiled=True, parity=PARITY_PASS,
                           ms=ms, fix_rounds=fx, bundle=bundle,
                           note="incumbent %s: %.2fx required, "
                                "measured %.2fx" % (band_label, confirm_gain,
                                                    best_ms / ms))
                    continue
                try:
                    ms2 = benchmark_fn(bundle)
                except BenchmarkDiverged as exc:
                    _log(log_cb, "%sround %d: outputs diverge from the baseline "
                         "on the bench scene -- %s" % (tag, i, exc))
                    _round("bench-diverged", note=str(exc), compiled=True,
                           parity=PARITY_PASS, fix_rounds=fx, bundle=bundle)
                    continue
                if ms2 is None or not (ms2 < need):
                    _log(log_cb, "%sround %d: %.3f ms not confirmed -- second "
                         "measurement %s" % (tag, i, ms,
                                             "unmeasurable" if ms2 is None
                                             else "%.3f ms" % ms2))
                    _round("not-faster", compiled=True, parity=PARITY_PASS,
                           ms=(ms if ms2 is None else ms2), fix_rounds=fx,
                           bundle = bundle,
                           note   = "incumbent %s: second measurement %s "
                                "did not confirm %.3f ms"
                                % (band_label,
                                   "unmeasurable" if ms2 is None
                                   else "%.3f ms" % ms2, ms))
                    continue
                note = ("confirmed twice (incumbent %s): %.3f / %.3f ms"
                        % (band_label, ms, ms2))
                ms = max(ms, ms2)
            if ms < best_ms / min_speedup and accept_check_fn is not None:
                try:
                    why = accept_check_fn(bundle, best_bundle)
                except BenchmarkDiverged as exc:
                    _log(log_cb, "%sround %d: outputs diverge from the "
                         "incumbent -- %s" % (tag, i, exc))
                    _round("bench-diverged", note=str(exc), compiled=True,
                           parity=PARITY_PASS, fix_rounds=fx, bundle=bundle)
                    continue
                if why:
                    _log(log_cb, "%sround %d: regressed -- %s" % (tag, i, why))
                    _round("regressed", note=why, compiled=True,
                           parity=PARITY_PASS, ms=ms, fix_rounds=fx,
                           bundle=bundle)
                    continue
            if ms < best_ms / min_speedup:
                speedup = baseline_ms / ms
                gain    = best_ms / ms
                _log(log_cb, "%sround %d: ACCEPT %.3f ms (%.2fx vs baseline, "
                     "%.2fx over the previous best)" % (tag, i, ms, speedup, gain))
                _round("accept", compiled=True, parity=PARITY_PASS, ms=ms,
                       speedup=speedup, fix_rounds=fx, bundle=bundle, note=note)
                ended["gain"] = gain
                best_cpp, best_ms, best_bundle = cand, ms, bundle
            else:
                _log(log_cb, "%sround %d: not faster (%.3f ms vs best %.3f ms)"
                     % (tag, i, ms, best_ms))
                _round("not-faster", compiled=True, parity=PARITY_PASS, ms=ms,
                       fix_rounds=fx, bundle=bundle)
        except Exception as exc:  # a flaky adapter must not abort the whole run
            _log(log_cb, "%sround %d: error %s" % (tag, i, exc))
            _round("error", note=str(exc))

    if not stop_reason:
        stop_reason = "max rounds (%d) reached" % rounds
    accepted = best_cpp is not baseline_cpp
    speedup  = (baseline_ms / best_ms) if best_ms else 1.0
    reason   = ("accepted (%.2fx)" % speedup) if accepted else "no candidate beat the baseline"
    return OptimizeResult(accepted, best_cpp, baseline_ms, best_ms, speedup,
                          rounds_run, ledger, reason,
                          max_rounds=rounds, stop_reason=stop_reason)
