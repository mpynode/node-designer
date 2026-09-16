"""Markdown reports for a staged compile: one per node, plus an index.

The shape is taken from a hand-written optimisation report that materially
changed how the optimizer was built -- headline table, per-round table with an
"exact?" column, and a NEGATIVE RESULTS section. The lesson worth copying is
that the rejected attempts carry more information than the accepted ones: "I
predicted structure-of-arrays would be faster and it was a 2x regression" is
transferable, and "12.41x" is not.

Three things this module refuses to leave out, each because its absence has
already cost something real:

* **Which gate judged the rounds.** A node whose pointwise parity SKIPs is gated
  only by its authored ``@maya_test``. A report that prints a speedup without
  saying so reads as verified when it is not -- that is exactly the hole a wrong
  candidate once shipped through.
* **What the benchmark measured.** Scene size, and whether the output was
  non-empty. A 96x on an empty isosurface is not a 96x.
* **Predicted vs measured.** Recorded per round, before the measurement.

Everything here is derived from ``rounds.json`` and the manifest row, so a
report can be regenerated from disk without re-running anything.
"""

from __future__ import annotations

import json
import os
import time

from mpynode.native.compiler import bundler

_STAGE_FILES = (
    ("1_transpiled.cpp", "deterministic transpile (no AI)"),
    ("2_assisted.cpp", "AI filled the unported region(s)"),
)


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _fmt_ms(v):
    return "%.3f ms" % v if isinstance(v, (int, float)) else "--"


def _fmt_x(v):
    return "%.2fx" % v if isinstance(v, (int, float)) else "--"


def _fmt_dur(v):
    if not isinstance(v, (int, float)):
        return "--"
    return "%d s" % round(v) if v < 90 else "%.1f min" % (v / 60.0)


_OUTCOME_MARK = {
    "accept":            "ACCEPTED",
    "baseline":          "--",
    "not-faster":        "rejected: not faster",
    "no-change":         "rejected: no change to the source",
    "compile-failed":    "rejected: did not compile",
    "unmeasurable":      "rejected: unmeasurable",
    "bench-diverged":    "rejected: outputs diverge from the baseline on the bench scene",
    "invalid-candidate": "rejected: invalid candidate",
    "regressed":         "rejected: slower on the small scene",
    "error":             "rejected: error",
}


def _outcome_text(outcome):
    if outcome in _OUTCOME_MARK:
        return _OUTCOME_MARK[outcome]
    if outcome.startswith("parity-"):
        return "rejected: parity %s" % outcome[len("parity-"):]
    return outcome


def _gate_sentence(gate):
    """Spell out, in words, how much the speedup below is actually worth."""
    if gate == "none":
        return ("**No parity gate ran.** Nothing was accepted, because a "
                "candidate that cannot be checked is not a candidate.")
    if not gate:
        return "Parity gate: not recorded."
    if gate == "authored-only":
        return (
            "**Parity gate: authored `@maya_test` only.** The generic pointwise "
            "compare did not run for this node, so every accepted round below "
            "was judged by the authored test's own scene -- a behavioural check, "
            "not a numerical one. The bench-scene fingerprint (when recorded "
            "below) is the only value-level check these rounds had.")
    if gate == "not exercised":
        return ("Parity gate: not exercised -- no candidate reached the parity "
                "check (the baseline was unmeasurable or no round compiled).")
    if gate == "pointwise":
        return ("Parity gate: `pointwise`. Every accepted round was compared "
                "value-for-value against the interpreted Python; this node has "
                "no authored `@maya_test`.")
    return (
        "Parity gate: `%s`. Every accepted round was re-checked against the "
        "interpreted Python before it was allowed to win. Where a node's "
        "generic pointwise parity SKIPS -- a deformer writes through the native "
        "`outputGeometry`, which the scalar harness cannot read -- the authored "
        "`@maya_test` is the ONLY gate, so treat those rows as behavioural "
        "checks rather than numerical ones." % gate)


def _bench_sentence(bench):
    """The scene the timings were taken on. Absent from ledgers written before
    2026-09-08, and said so: a speedup without its scene is not a measurement."""
    if not isinstance(bench, dict) or not bench:
        return ("Bench scene: not recorded (ledger predates the scene record; "
                "no noise-floor gate, no per-tick perturbation check and no "
                "output fingerprint applied to these rounds).")
    rung  = bench.get("rung") or [None, None]
    moved = bench.get("perturbed")
    parts = ["Bench scene: %s" % _rung_text(rung)]
    if bench.get("floor_ms") is not None:
        parts.append("noise floor %s ms" % _fmt_num(bench["floor_ms"]))
    if moved is not None:
        parts.append("moved per tick: %s" % (", ".join("`%s`" % m for m in moved)
                                              if moved else "nothing"))
    if bench.get("fingerprint"):
        parts.append("outputs %s" % bench["fingerprint"])
    sr = bench.get("small_rung")
    if isinstance(sr, (list, tuple)) and len(sr) == 2:
        parts.append("accepts re-timed against the incumbent on the smallest "
                     "scene (%s) and rejected if slower there" % _rung_text(sr))
    if bench.get("below_floor"):
        parts.append("baseline under the noise floor at the largest scene, so "
                     "every accept had to clear 1.15x on two independent timings")
    line = "; ".join(parts) + "."
    if bench.get("reason"):
        line += " %s." % bench["reason"].rstrip(".")
    return line


def _fmt_num(v):
    return ("%g" % v) if isinstance(v, (int, float)) else str(v)


def _rung_text(rung):
    """A ladder rung in words. Compute rungs are (geo density, array length);
    a texture node's rungs are ("bake", source px) -- a VP2 bake of the node."""
    r = (list(rung) if isinstance(rung, (list, tuple)) else [None, None]) + [None, None]
    if r[0] == "bake":
        return "VP2 bake of a %spx source image" % ("?" if r[1] is None else r[1])
    return "geo density %s / array length %s" % tuple(
        "?" if x is None else x for x in r[:2])


def _remeasured_short(rec):
    """Summary-table phrase for a re-measurement."""
    if rec.get("diverged"):
        return "outputs DIVERGE from the baseline"
    if rec.get("baseline_ms") is None or rec.get("final_ms") is None:
        return "unmeasurable under the gate"
    return "**%s** (outputs match)" % _fmt_x(rec.get("speedup"))


def _remeasured_lines(rec):
    """The honest number, printed beside the old one, never over it.

    ``rounds.json["remeasured"]`` is written by tools/harness/rebench_shipped.py:
    the shipped final and its own pre-optimization baseline compiled again and
    timed on one calibrated scene under the gated harness (noise floor,
    animated-input perturbation, output fingerprint)."""
    if not isinstance(rec, dict) or not rec:
        return []
    rung = list(rec.get("rung") or []) + [None, None]
    scene = "geo density %s / array length %s" % tuple(
        "?" if x is None else x for x in rung[:2])
    head = ("**Re-measured %s** under the gated harness (noise floor, "
            "animated-input perturbation, output fingerprint), %s"
            % (rec.get("date") or "later", scene))
    if rec.get("diverged"):
        body = ("%s: **the shipped file's outputs DIVERGE from its own "
                "pre-optimization baseline on this scene** -- %s. Its timing "
                "(%s against the baseline's %s) compares two different programs "
                "and is not a speedup; revert decision pending."
                % (head, rec["diverged"], _fmt_ms(rec.get("final_ms")),
                   _fmt_ms(rec.get("baseline_ms"))))
    elif rec.get("baseline_ms") is None:
        body = ("%s: **unmeasurable** -- %s. The speedup above was taken before "
                "the gate existed and cannot be reproduced under it."
                % (head, rec.get("reason") or "no reason recorded"))
    elif rec.get("final_ms") is None:
        body = ("%s: baseline %s, but the shipped final could not be measured -- "
                "%s." % (head, _fmt_ms(rec["baseline_ms"]),
                         rec.get("reason") or "no reason recorded"))
    else:
        body = ("%s: baseline %s -> shipped %s (**%s**); outputs match. The "
                "speedup above was taken before the gate existed; this is the "
                "number to quote."
                % (head, _fmt_ms(rec["baseline_ms"]), _fmt_ms(rec["final_ms"]),
                   _fmt_x(rec.get("speedup"))))
    moved = rec.get("perturbed")
    if moved is not None:
        body += " Moved per tick: %s." % (
            ", ".join("`%s`" % m for m in moved) if moved else "nothing")
    return [body, ""]


def _rounds_table(ledger):
    lines = ["| # | change | theme | predicted | measured | time | outcome |",
             "|---|---|---|---|---|---|---|"]
    for r in ledger:
        measured = _fmt_x(r.get("speedup"))
        if r.get("index") == 0:
            measured = _fmt_ms(r.get("ms"))
        elif r.get("ms") is not None and r.get("speedup") is None:
            measured = _fmt_ms(r.get("ms"))
        lines.append("| %02d | `%s` | %s | %s | %s | %s | %s |" % (
            r.get("index", 0),
            r.get("slug") or "--",
            (r.get("theme") or "").replace("|", "\\|") or "--",
            _fmt_x(r.get("predicted_speedup")),
            measured,
            _fmt_dur(r.get("duration_s")),
            _outcome_text(r.get("outcome", "")),
        ))
    return lines


def _predicted_vs_measured(ledger):
    """Only the rows where the prediction and the measurement disagree."""
    out = []
    for r in ledger:
        pred, got = r.get("predicted_speedup"), r.get("speedup")
        if not isinstance(pred, (int, float)):
            continue
        if r.get("outcome") == "accept" and isinstance(got, (int, float)):
            if abs(got - pred) / max(pred, 1e-9) < 0.25:
                continue        # close enough to be uninteresting
            out.append("* `%s` -- predicted %s, measured **%s**. %s"
                       % (r.get("slug") or "?", _fmt_x(pred), _fmt_x(got),
                          r.get("hypothesis") or ""))
        else:
            out.append("* `%s` -- predicted %s, **%s**. %s"
                       % (r.get("slug") or "?", _fmt_x(pred),
                          _outcome_text(r.get("outcome", "")),
                          r.get("note") or r.get("hypothesis") or ""))
    return out


def _stop_phrase(rounds):
    """How the adaptive loop ended, when the ledger says (written from
    2026-09-09); '' for ledgers from the fixed-count era, which recorded none."""
    why = (rounds or {}).get("stop_reason")
    if not why:
        return ""
    mx  = rounds.get("max_rounds")
    cap = (" of max %d" % mx) if isinstance(mx, int) and mx > 0 else ""
    return " -- %d run%s, stopped: %s" % (len(rounds.get("ledger") or []) - 1,
                                          cap, why)


def _stage_summary(stage_dir, row, rounds):
    """The three-line 'what actually ran' table at the top of a node report."""
    incomplete = list((row or {}).get("incomplete") or [])
    ported     = bool((row or {}).get("ported"))

    transpiled = os.path.isfile(os.path.join(stage_dir, "1_transpiled.cpp"))
    assisted   = os.path.isfile(os.path.join(stage_dir, "2_assisted.cpp"))

    t = "deterministic C++, no AI" if transpiled and not ported else \
        ("emitted, with region(s) the transpiler could not lower"
         if transpiled else "not recorded")
    if assisted:
        a = "ran" + (" -- %d region(s) still marked incomplete" % len(incomplete)
                     if incomplete else " -- no unresolved regions")
    else:
        a = "not run (nothing to fill)" if not ported else "not run"

    if rounds is None:
        o = "not run"
    elif rounds.get("accepted"):
        o = "**%s** over %d round(s)%s" % (_fmt_x(rounds.get("speedup")),
                                           len(rounds.get("ledger") or []) - 1,
                                           _stop_phrase(rounds))
    else:
        o = "ran, nothing accepted (%s)%s" % (rounds.get("reason") or "no gain",
                                              _stop_phrase(rounds))
    _rm = (rounds or {}).get("remeasured")
    if isinstance(_rm, dict) and _rm:
        o += " -- re-measured: %s" % _remeasured_short(_rm)

    return [
        "| stage | outcome |",
        "|---|---|",
        "| 1 Transpile | %s |" % t,
        "| 2 AI assist | %s |" % a,
        "| 3 AI optimize | %s |" % o,
    ]


def node_report_text(out_dir, type_name, *, row=None, spec=None):
    """The full Markdown for one node. Pure -- reads only files it is given."""
    stage_dir = bundler.stage_dir_for(out_dir, type_name)
    rounds    = _read_json(os.path.join(stage_dir, "rounds.json"))
    row       = row or {}
    spec      = spec or row.get("spec") or {}

    L    = ["# %s -- compile report" % type_name, ""]
    src  = row.get("source_node") or spec.get("source_node") or "?"
    base = (spec.get("suggested") or {}).get("mpx_base") or "MPxNode"
    L.append("**Source node:** `%s`  ·  **Base:** `%s`  ·  **Generated:** %s"
             % (src, base, time.strftime("%Y-%m-%d %H:%M")))
    L.append("")
    L += _stage_summary(stage_dir, row, rounds)
    L.append("")

    compute = (spec.get("compute") or "").strip()
    if compute:
        L += ["## The Python this was generated from", "",
              "```python", compute, "```", ""]

    # ---- stage 2 honesty -------------------------------------------------
    incomplete = list(row.get("incomplete") or [])
    invented   = list(row.get("invented_io") or [])
    if incomplete or invented:
        L += ["## Unfinished work in the generated C++", ""]
        for what in incomplete:
            L.append("* **not translated:** %s" % what)
        for what in invented:
            L.append("* **invented I/O flagged:** %s" % what)
        L.append("")

    # ---- known limitation: no VP2 override --------------------------------
    vp2_skip = (row.get("vp2_skip") or "").strip()
    if vp2_skip:
        L += ["## Known limitation -- Viewport 2.0", "",
              "No `MPxShadingNodeOverride` was emitted for this node: **%s**."
              % vp2_skip, "",
              "The node is CORRECT everywhere the DG evaluates `outColor` --"
              " software rendering, Arnold, and the Hypershade swatch. Only"
              " the interactive Viewport 2.0 differs: with no override and no"
              " texture classification, OGS shades the surface a single flat"
              " colour taken from the node's current `outColor` rather than"
              " sampling it per pixel.", "",
              "The interpreted node does not have this limitation, because its"
              " authored **Viewport** tier uploads the texture itself -- and"
              " that tier is Python that does not port.", ""]

    # ---- stage 3 ---------------------------------------------------------
    if rounds:
        L += ["## Optimization", ""]
        L.append(_gate_sentence(rounds.get("parity_gate")))
        L.append("")
        L.append(_bench_sentence(rounds.get("bench")))
        L.append("")
        L.append("Baseline **%s** -> best **%s** (**%s**)."
                 % (_fmt_ms(rounds.get("baseline_ms")),
                    _fmt_ms(rounds.get("best_ms")),
                    _fmt_x(rounds.get("speedup"))))
        L.append("")
        if rounds.get("stop_reason"):
            mx = rounds.get("max_rounds")
            L.append("Rounds: **%d** run%s; the loop stopped because %s."
                     % (len(rounds.get("ledger") or []) - 1,
                        (" of at most %d" % mx)
                        if isinstance(mx, int) and mx > 0 else "",
                        rounds["stop_reason"]))
            L.append("")
        L += _remeasured_lines(rounds.get("remeasured"))
        ledger = rounds.get("ledger") or []
        L += _rounds_table(ledger)
        L.append("")

        diverged = _predicted_vs_measured(ledger)
        if diverged:
            L += ["### Predicted vs measured", "",
                  "The rounds where the guess and the stopwatch disagreed. "
                  "These are the transferable part -- a prediction that missed "
                  "says more about the machine than one that landed.", ""]
            L += diverged
            L.append("")

        rejected = [r for r in ledger
                    if r.get("index") and r.get("outcome") != "accept"]
        if rejected:
            L += ["### Rejected rounds", ""]
            for r in rejected:
                L.append("* `%s` -- %s. %s"
                         % (r.get("slug") or "?",
                            _outcome_text(r.get("outcome", "")),
                            (r.get("note") or r.get("theme") or "").strip()))
            L.append("")

    # ---- verification ----------------------------------------------------
    v = row.get("verify") or {}
    if v.get("ran"):
        L += ["## Verification", "",
              "* parity: **%s**%s" % (
                  "pass" if v.get("pass") else "FAIL",
                  ("  (maxerr %s, tol %s)" % (v.get("maxerr"), v.get("tol")))
                  if v.get("maxerr") is not None else ""),
              ]
        if v.get("reason"):
            L.append("* %s" % v["reason"])
        # Timing rides on its own line: the whole Verification block is gated on
        # `ran`, and a slow-but-correct port is a PASSING row, so a note folded
        # into `reason` would never reach the rows it is about. The raw numbers
        # go in even when nothing is wrong -- that record is what a later
        # calibration pass reads back.
        t = v.get("timing") or {}
        if t.get("warning"):
            L.append("* %s" % t["warning"])
        if t.get("measured"):
            bits = []
            if t.get("n"):
                bits.append("best of %d" % t["n"])
            if t.get("scene"):
                bits.append(str(t["scene"]))
            L.append("* speed: compiled %s vs interpreted %s%s"
                     % (_fmt_ms(t.get("cpp_ms")), _fmt_ms(t.get("py_ms")),
                        (" (%s)" % ", ".join(bits)) if bits else ""))
        L.append("")

    # ---- files -----------------------------------------------------------
    L += ["## Files", "", "```"]
    for name, what in _STAGE_FILES:
        if os.path.isfile(os.path.join(stage_dir, name)):
            L.append("build/stages/%s/%-20s %s" % (type_name, name, what))
    opt = os.path.join(stage_dir, "3_optimized")
    if os.path.isdir(opt):
        for name in sorted(os.listdir(opt)):
            if name.endswith(".cpp"):
                L.append("build/stages/%s/3_optimized/%s" % (type_name, name))
    L.append("build/source/%s.cpp%s  SHIPPED" % (type_name, " " * 4))
    L.append("```")
    L.append("")
    return "\n".join(L)


def write_node_report(out_dir, type_name, *, row=None, spec=None):
    """Write ``build/stages/<Type>/REPORT.md``. Best-effort; returns path/None."""
    try:
        d = bundler.stage_dir_for(out_dir, type_name)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "REPORT.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(node_report_text(out_dir, type_name, row=row, spec=spec))
        return path
    except OSError:
        return None


def index_report_text(out_dir, plugin_name, rows):
    """The top-level ``REPORT.md``: one line per node, linking down."""
    L = ["# %s -- compile report" % plugin_name, "",
         "Generated %s" % time.strftime("%Y-%m-%d %H:%M"), "",
         "| node | status | assist | optimize | detail |",
         "|---|---|---|---|---|"]
    vp2_skips = []
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("type_name"):
            continue
        tn         = row["type_name"]
        stage_dir  = bundler.stage_dir_for(out_dir, tn)
        rounds     = _read_json(os.path.join(stage_dir, "rounds.json"))
        incomplete = list(row.get("incomplete") or [])
        assist = ("--" if not row.get("ported")
                  else ("%d unresolved" % len(incomplete) if incomplete
                        else "filled"))
        if rounds is None:
            opt = "--"
        elif rounds.get("accepted"):
            opt = "**%s**" % _fmt_x(rounds.get("speedup"))
        else:
            opt = "no gain"
        detail = ("[report](build/stages/%s/REPORT.md)" % tn
                  if os.path.isfile(os.path.join(stage_dir, "REPORT.md"))
                  else "--")
        L.append("| `%s` | %s | %s | %s | %s |"
                 % (tn, row.get("build_status") or "?", assist, opt, detail))
        if (row.get("vp2_skip") or "").strip():
            vp2_skips.append((tn, row["vp2_skip"].strip()))
    L.append("")
    if vp2_skips:
        L += ["## Known limitation -- Viewport 2.0", "",
              "These nodes compiled and are correct everywhere the DG evaluates"
              " `outColor` (software render, Arnold, Hypershade swatch), but no"
              " `MPxShadingNodeOverride` was emitted, so interactive Viewport"
              " 2.0 shades the surface a single flat colour:", ""]
        for tn, why in vp2_skips:
            L.append("* `%s` -- %s" % (tn, why))
        L.append("")
    L += ["## Layout", "",
          "```",
          "<Plugin>.bundle              the plug-in you load",
          "build/source/                the C++ that was compiled -- and only that",
          "build/stages/<Type>/         how it got there (kept; never swept)",
          "  1_transpiled.cpp             deterministic, no AI",
          "  2_assisted.cpp               AI filled the unported region(s)",
          "  3_optimized/NN_<slug>.cpp    one file per optimize round, rejects included",
          "  rounds.json                  machine-readable ledger",
          "  REPORT.md                    this node's full story",
          "```", ""]
    return "\n".join(L)


def write_index_report(out_dir, plugin_name, rows):
    """Write ``<out>/REPORT.md``. Best-effort; returns path/None."""
    try:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "REPORT.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(index_report_text(out_dir, plugin_name, rows))
        return path
    except OSError:
        return None


def write_reports(out_dir, plugin_name, rows):
    """Write every node report plus the index. Never raises."""
    written = []
    for row in rows or []:
        # A dropped node's row can be sparse, and a caller can hand us junk; a
        # report is documentation and must never be the thing that fails a build.
        if not isinstance(row, dict):
            continue
        tn = row.get("type_name")
        if not tn:
            continue
        p = write_node_report(out_dir, tn, row=row, spec=row.get("spec"))
        if p:
            written.append(p)
    idx = write_index_report(out_dir, plugin_name, rows)
    if idx:
        written.append(idx)
    return written
