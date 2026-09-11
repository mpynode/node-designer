"""compile_bridge -- pure packaging of a native-compile result into a
conversational hand-off for the AI assistant (WS2 "Compile with AI" concierge).

This module is deliberately Qt-free and Maya-free: it takes the plain result
dict produced by ``compile_controller`` (and the compile options / a tail of the
build log) and returns plain data + human-readable text. That keeps the whole
decision surface unit-testable headlessly, and lets both the compile dialog and
the assistant panel share one definition of "what went wrong and what to say
about it".

Design follows Revision 2 of the unified-compile design (the reframe):

  * The win for a technical artist is a *compiling* C++ node that verifies
    "in the ballpark", NOT a perfect deterministic transpile. So we NEVER frame
    a non-parity or un-lowerable node as a hard failure. We surface it, and hand
    the user + the assistant everything needed to iterate.
  * Verify results are first-class and VISIBLE. A node that built but whose
    output diverged from the Python reference is reported right next to a node
    that failed to build at all -- both are "things to look at", not "errors".
  * The assistant is welcome to author / fix the C++ directly, or reshape the
    Python so it lowers cleanly. The user green-lights, hand-edits, or keeps
    iterating. Nothing here blocks; it enables.

Result-dict shape consumed (from compile_controller):
    {ok, bundle_path, manifest_path, plugin_name, nodes:[row...], errors, strict}
Row shape:
    {source_node, type_name, type_id, base, build_status, build_reason,
     ported, incomplete:[...], invented_io:[...],
     verify:{ran, pass, maxerr, tol, reason},
     spec:{... portability:{blockers, unported}}}
"""

from __future__ import annotations

# build_status values that mean "a C++ node exists in the bundle".
_BUILT_STATUSES = ("compiled", "transformed", "ok", "built")
# build_status values that mean "no C++ node was produced for this source node".
_UNBUILT_STATUSES = ("dropped", "failed", "error", "skipped")

# How many trailing build-log lines to carry into the hand-off by default.
_LOG_TAIL_LINES = 40


# --------------------------------------------------------------------------- #
# formatting helpers
# --------------------------------------------------------------------------- #
def _fmt_num(v):
    """Compact, human-readable rendering of a float (or None) for the report."""
    if v is None:
        return "n/a"
    try:
        return "%.1e" % float(v)
    except (TypeError, ValueError):
        return str(v)


def _verify_line(verify):
    """One-line summary of a row's verify sub-dict."""
    verify = verify or {}
    if not verify.get("ran"):
        reason = (verify.get("reason") or "").strip()
        if reason:
            return "verify: did not run (%s)" % reason
        return "verify: did not run"
    ok    = verify.get("pass")
    tag   = "PASS" if ok else ("FAIL" if ok is False else "unknown")
    parts = ["verify: %s" % tag]
    parts.append("maxerr=%s" % _fmt_num(verify.get("maxerr")))
    parts.append("tol=%s" % _fmt_num(verify.get("tol")))
    reason = (verify.get("reason") or "").strip()
    if reason and ok is not True:
        parts.append("(%s)" % reason)
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# row selection / summarisation
# --------------------------------------------------------------------------- #
def _row_summary(row):
    row    = row or {}
    verify = row.get("verify") or {}
    spec   = row.get("spec") or {}
    port   = spec.get("portability") or {}
    return {
        "source_node":  row.get("source_node"),
        "type_name":    row.get("type_name"),
        "build_status": row.get("build_status"),
        "build_reason": row.get("build_reason") or "",
        "verify": {
            "ran":    verify.get("ran"),
            "pass":   verify.get("pass"),
            "maxerr": verify.get("maxerr"),
            "tol":    verify.get("tol"),
            "reason": verify.get("reason") or "",
            "timing": verify.get("timing") or {},
        },
        "blockers": list(port.get("blockers") or []),
        # The gap, what the AI port did about it, and whether anything checked
        # -- the assistant needs all three to answer usefully.
        "unported":    list(port.get("unported") or []),
        "incomplete":  list(row.get("incomplete") or []),
        "invented_io": list(row.get("invented_io") or []),
        "ported":      bool(row.get("ported")),
    }


def _is_built(row):
    return (row.get("build_status") or "") in _BUILT_STATUSES


def _is_unbuilt(row):
    return (row.get("build_status") or "") in _UNBUILT_STATUSES


def _is_diverged(row):
    """Built, verify ran, and the compiled output did NOT match the Python."""
    v = row.get("verify") or {}
    return bool(v.get("ran")) and v.get("pass") is False


def _is_incomplete(row):
    """Built, but the C++ says so itself: the AI porter marked a construct it
    could not translate, or emitted I/O it was told never to emit. The bundle is
    real and loads -- this is the node telling the truth about what is missing,
    which is the whole point of not hard-rejecting it up front."""
    return bool(row.get("incomplete") or row.get("invented_io"))


def _is_unchecked_port(row):
    """Built by the AI porter, and NOTHING checked it.

    Verify is structurally non-fatal and skips for many legitimate reasons (RNG,
    an image read, a skinCluster with no bound rig...). On a deterministically
    lowered node a skip is routine -- the transpiler is the guarantee. On an
    LLM-authored body there is no other guarantee at all: "it compiled" is the
    only gate it passed. Same skip, different meaning, so only the ported case
    is surfaced."""
    v = row.get("verify") or {}
    return _is_built(row) and bool(row.get("ported")) and not v.get("ran")


def _wants_attention(row):
    """A row worth talking to the assistant about in the 'failure' flow: it did
    not build, it diverged from the reference, it admits to being incomplete, or
    it is an AI port that nothing verified."""
    return (_is_unbuilt(row) or _is_diverged(row) or _is_incomplete(row)
            or _is_unchecked_port(row))


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def classify(result):
    """Bucket a compile result's rows so callers (the compile dialog, the
    orchestrator) share ONE definition of what
    happened. Pure; JSON-safe lists of the original row dicts.

    Returns:
        {n_total, built, dropped, diverged, incomplete, unchecked, verified_ok,
         needs_ai}
    where each bucket is a list of rows and ``needs_ai`` is True when anything
    failed to build, diverged from the Python reference, shipped incomplete, or
    is an unverified AI port (i.e. there is something worth an AI conversation
    about)."""
    result     = result or {}
    rows       = result.get("nodes") or []
    built      = [r for r in rows if _is_built(r)]
    dropped    = [r for r in rows if _is_unbuilt(r)]
    diverged   = [r for r in rows if _is_diverged(r)]
    incomplete = [r for r in rows if _is_incomplete(r)]
    unchecked  = [r for r in rows if _is_unchecked_port(r)]
    verified_ok = [r for r in built
                   if (r.get("verify") or {}).get("pass") is True]
    return {
        "n_total":     len(rows),
        "built":       built,
        "dropped":     dropped,
        "diverged":    diverged,
        "incomplete":  incomplete,
        "unchecked":   unchecked,
        "verified_ok": verified_ok,
        "needs_ai":    bool(dropped or diverged or incomplete or unchecked),
    }


def needs_ai(result):
    """True when the result has anything worth handing to the assistant (a node
    that didn't build, or a node that built but diverged from the reference)."""
    return classify(result)["needs_ai"]


def verify_summary_lines(result):
    """One human-readable line per node for the compile dialog's FINAL summary,
    carrying build status + the verify verdict (pass/fail/maxerr/tol or the
    'did not run' reason). This makes verify a first-class, persistent part of
    the summary instead of a transient progress line."""
    rows  = (result or {}).get("nodes") or []
    lines = []
    for r in rows:
        name   = r.get("type_name") or "?"
        status = r.get("build_status") or "?"
        # `build_status` must keep saying "compiled" (it gates
        # verify/companions/cleanup upstream), but "compiled" alone reads as
        # done when what shipped is compiled-but-incomplete.
        if _is_incomplete(r):
            status = "%s, INCOMPLETE" % status
        lines.append("%s (%s) -- %s"
                     % (name, status, _verify_line(r.get("verify"))))
        for what in (r.get("incomplete") or []):
            lines.append("    ! not translated: %s" % what)
        for what in (r.get("invented_io") or []):
            lines.append("    ! AI body contains %s -- it was instructed not to "
                         "emit this; review before shipping" % what)
        # A slow-but-correct port is a PASSING row, and _verify_line drops
        # `reason` once ok is True -- so the timing note has to ride as its own
        # line or it is never seen on exactly the rows it is about.
        t = (r.get("verify") or {}).get("timing") or {}
        if t.get("warning"):
            lines.append("    ! %s" % t["warning"])
        if _is_unchecked_port(r):
            lines.append("    ! AI-ported and NOT verified -- 'it compiled' is "
                         "the only check this body passed")
    return lines


def build_handoff(result, options=None, log_tail=None, kind="failure"):
    """Package a compile ``result`` into a hand-off dict for the assistant.

    kind:
      "failure"  -> pick rows that need attention (didn't build, or diverged).
      "optimize" -> pick rows that DID build (candidates for perf work), even
                    if they verified clean.

    Returns a plain dict (JSON-safe) -- no Qt, no Maya objects.
    """
    result  = result or {}
    options = options or {}
    rows    = result.get("nodes") or []

    if kind == "optimize":
        picked_rows = [r for r in rows if _is_built(r)]
    else:
        picked_rows = [r for r in rows if _wants_attention(r)]

    summaries = [_row_summary(r) for r in picked_rows]

    primary   = None
    for s in summaries:
        if s.get("source_node"):
            primary = s["source_node"]
            break

    tail = list(log_tail or [])
    if len(tail) > _LOG_TAIL_LINES:
        tail = tail[-_LOG_TAIL_LINES:]

    return {
        "kind": kind,
        "primary_source_node": primary,
        "plugin_name": result.get("plugin_name"),
        "bundle_path": result.get("bundle_path"),
        "out_dir": options.get("out_dir"),
        "ok": bool(result.get("ok")),
        "rows": summaries,
        "errors": list(result.get("errors") or []),
        "log_tail": tail,
    }


_OSL_DEFAULT_SUGGESTIONS = (
    "If an input has no OSL equivalent (e.g. a runtime array, or a "
    "non-colour-typed output), consider reshaping the node's interface -- for "
    "example replacing a variable-length array input with a fixed number of "
    "scalar inputs, or deriving those inputs from the current data.",
)


def build_osl_handoff(reason, node_name=None, compute=None, suggestions=None):
    """Package an OSL-conversion dead-end into a hand-off for the assistant.

    The deterministic OSL transpiler (and the one-shot AI fallback) refuse some
    computes outright -- e.g. compositeTexture's ``filePaths[]`` string array +
    int ``maxWidth``/``maxHeight`` outputs, which OSL simply cannot express. Per
    the reframe, a hard "can't convert" should become an open-ended conversation
    where the assistant proposes an interface change (hard-code N single string
    inputs, generate N from the current path count, ...) rather than a dead end.

    Pure: returns a JSON-safe dict rendered by ``format_report_block`` /
    ``starter_prompt`` under ``kind == "osl"``."""
    return {
        "kind": "osl",
        "primary_source_node": node_name,
        "reason": reason or "",
        "compute": compute or "",
        "suggestions": list(suggestions or _OSL_DEFAULT_SUGGESTIONS),
        "rows": [],
        "errors": [],
        "log_tail": [],
    }


def _format_osl_report(handoff):
    lines = ["[Compile report]", "intent: convert this node's compute to OSL"]
    node  = handoff.get("primary_source_node")
    if node:
        lines.append("node: %s" % node)
    reason = (handoff.get("reason") or "").strip()
    if reason:
        lines.append("blocker: OSL cannot express this compute -- %s" % reason)
    for s in handoff.get("suggestions") or []:
        lines.append("suggestion: %s" % s)
    lines.append("")
    lines.append(
        "Goal: get this node producing a valid OSL shader. OSL is more "
        "restrictive than the native C++ path, so this may require reshaping "
        "the node's interface (e.g. replacing an unsupported array input with a "
        "fixed set of scalar inputs). Propose an approach, walk me through the "
        "trade-offs, and I (the user) will decide before anything is applied.")
    lines.append("[/Compile report]")
    return "\n".join(lines)


def format_report_block(handoff):
    """Render a hand-off as a fenced, human-readable report block. This is what
    gets dropped into the assistant conversation so the model (and the user) can
    see exactly what compiled, what diverged, and what blocked lowering."""
    handoff = handoff or {}
    kind    = handoff.get("kind", "failure")
    if kind == "osl":
        return _format_osl_report(handoff)
    lines  = ["[Compile report]"]

    plugin = handoff.get("plugin_name")
    if plugin:
        lines.append("plugin: %s" % plugin)
    out_dir = handoff.get("out_dir")
    if out_dir:
        lines.append("out_dir: %s" % out_dir)
    lines.append("intent: %s" % ("optimize" if kind == "optimize"
                                 else _FAILURE_INTENT[failure_shape(handoff)]))

    rows = handoff.get("rows") or []
    if not rows:
        lines.append("nodes: (none flagged)")
    for s in rows:
        name = s.get("type_name") or "?"
        src  = s.get("source_node")
        head = "- %s" % name
        if src and src != name:
            head += " (from %s)" % src
        head += " [%s]" % (s.get("build_status") or "?")
        lines.append(head)
        reason = (s.get("build_reason") or "").strip()
        if reason:
            lines.append("    reason: %s" % reason)
        lines.append("    %s" % _verify_line(s.get("verify")))
        for b in s.get("blockers") or []:
            lines.append("    blocker: %s" % b)

    errors = handoff.get("errors") or []
    for e in errors:
        lines.append("error: %s" % e)

    tail = handoff.get("log_tail") or []
    if tail:
        lines.append("--- build log (tail) ---")
        lines.extend(str(t) for t in tail)

    lines.append("")
    if kind == "optimize":
        lines.append(
            "Goal: make the compiled C++ faster while keeping output on-par "
            "with the Python. You may rewrite the compute in C++ or restructure "
            "the Python so it lowers better. I (the user) will review and "
            "green-light, hand-edit, or ask you to keep iterating.")
    elif failure_shape(handoff) == "unverified":
        # "Produce valid, compiling C++" contradicts "already compiles, don't
        # rewrite" -- the model resolves that contradiction by rewriting.
        lines.append(
            "Goal: work out whether the compiled C++ actually matches the "
            "Python, and tell me what you found BEFORE changing anything. The "
            "node already builds; what is missing is a verification that can "
            "run. Landing a gate that works -- an authored @maya_test, or "
            "reshaping the Python so both sides agree on which outputs exist "
            "-- is a perfectly good outcome. I (the user) will review and "
            "green-light, hand-edit, or ask you to keep digging.")
    else:
        lines.append(
            "Goal: produce valid, compiling C++ that verifies on-par with the "
            "Python version -- being in the ballpark is a win. You may author "
            "or fix the C++ directly, or reshape the Python so it lowers "
            "cleanly. Perfect byte-parity is NOT required to proceed: I (the "
            "user) can green-light a not-100%-identical result, hand-edit it, "
            "or ask you to keep iterating toward parity. Nothing here is "
            "hard-blocked.")
    lines.append("[/Compile report]")
    return "\n".join(lines)


_SHAPE_TESTS = (("unbuilt", _is_unbuilt), ("diverged", _is_diverged),
                ("incomplete", _is_incomplete), ("unverified", _is_unchecked_port))


def _shape_and_row(handoff):
    """The hand-off's shape AND the row that decided it, worst-first.

    The row matters: the ask names a node, and naming the FIRST flagged row
    while describing the WORST row's failure asserts a measured divergence
    against a node that does not have one.
    """
    rows = (handoff or {}).get("rows") or []
    for shape, test in _SHAPE_TESTS:
        for r in rows:
            if test(r):
                return shape, r
    return "unbuilt", None


def failure_shape(handoff):
    """WHICH failure the "failure" hand-off is actually about.

    ``_wants_attention`` pools four very different situations, and every one of
    them used to be handed over as "please get it compiling" -- including a node
    whose ``build_status`` was already ``compiled`` and whose only problem was
    that parity COULD NOT BE MEASURED. Worst-first, because a node that did not
    build is the blocking problem when a run has several.
    """
    return _shape_and_row(handoff)[0]


_FAILURE_INTENT = {
    "unbuilt":    "get it compiling / on-par",
    "diverged":   "close a MEASURED divergence from the Python reference",
    "incomplete": "finish the parts the port could not translate",
    "unverified": "explain an AI port that compiled but could not be verified",
}


def starter_prompt(handoff):
    """A pre-filled first user turn for the assistant, embedding the report."""
    handoff = handoff or {}
    kind    = handoff.get("kind", "failure")
    report  = format_report_block(handoff)
    primary = handoff.get("primary_source_node")
    subj    = ("`%s`" % primary) if primary else "these nodes"
    shape, shape_row = _shape_and_row(handoff)
    if kind not in ("osl", "optimize") and shape_row:
        # Name the node the ask DESCRIBES, not the first flagged row.
        _named = shape_row.get("source_node") or shape_row.get("type_name")
        if _named:
            subj = "`%s`" % _named

    if kind == "osl":
        ask = (
            "The OSL conversion for %s hit a hard limit (see below). Please "
            "propose how to get it producing a valid OSL shader -- including "
            "any interface change that would make it expressible -- and walk me "
            "through it before applying anything." % subj)
    elif kind == "optimize":
        ask = (
            "Please look at the compiled node(s) below and propose ways to make "
            "%s faster in C++ without changing the output beyond tolerance. "
            "Walk me through the change before applying it." % subj)
    elif shape == "unverified":
        # Nothing measured went wrong, so "fix it" invites a rewrite of working
        # C++ against a phantom. Diagnosis first.
        ask = (
            "The native compile built %s, but its output could not be verified "
            "against the Python -- parity was NOT MEASURED, so 'it compiled' is "
            "the only check the C++ body passed. It is not known to be wrong. "
            "Please work out WHY verify could not run (see the "
            "reason below), and tell me whether the C++ actually diverges from "
            "the Python before changing anything. Do not rewrite working code to "
            "make a check pass. If the node needs a different gate -- an authored "
            "@maya_test, or reshaping the Python so the two sides agree on which "
            "outputs exist -- propose that instead." % subj)
    elif shape == "diverged":
        ask = (
            "The native compile built %s but its output DIVERGED from the Python "
            "reference (see the measured error below). Please find the cause and "
            "close the gap. Explain the approach, apply it, and we'll re-compile "
            "and check verify together." % subj)
    elif shape == "incomplete":
        ask = (
            "The native compile built %s, but the C++ marks work it could not "
            "translate. Please finish those parts so the node's behaviour matches "
            "the Python. Explain the approach, apply it, and we'll re-compile and "
            "check verify together." % subj)
    else:
        ask = (
            "The native compile flagged the node(s) below. Please get %s "
            "compiling with output on-par with the Python version. Explain the "
            "approach, apply it, and we'll re-compile and check verify "
            "together." % subj)

    return "%s\n\n%s" % (ask, report)
