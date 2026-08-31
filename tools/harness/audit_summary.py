"""Summarize master_results.json from a compiler-audit run and classify each
template so the follow-up high-fallback pass is unambiguous.

Usage:
    python3 audit_summary.py [master_results.json]

Prints:
  * a per-template table (status / det|ai / seconds / verify / #demos built)
  * the multi-demo breakdown (esp. DNET's Grid Net / Layout Net / Two Knots)
  * the buckets:
      OK             -- compiled + every demo built + reopened + parity VERIFIED
      HONEST-DROP    -- correctly non-portable (open()/cmds/2D-index)
      VERIFY-FAIL    -- parity ran and FAILED
      VERIFY-NOT-RUN -- everything built, but nothing ever checked parity
      NEEDS-FALLBACK -- dropped/failed for a reason that a high-effort retry may
                        fix (candidate for the MPYNODE_PORT_EFFORT=high pass)
  * a ready-to-run `run_all.py` folder list for the NEEDS-FALLBACK bucket.
"""
import os
import sys
import json

HARNESS = os.path.dirname(os.path.abspath(__file__))
AUDIT_ROOT = os.path.join(os.path.dirname(os.path.dirname(HARNESS)),
                          "_audit")                         # audit output root
DEFAULT = os.path.join(AUDIT_ROOT, "master_results.json")

# Templates that SHOULD drop (correct-by-design; never a fallback candidate),
# named by the .mpn each audit row is built from. Spelling the audit FOLDER out
# here by hand went dead the moment the folders were renamed
# basics_<category>_<name> -> basics_<MPyType>_<name>: every key matched
# nothing, so the bucket could never fire and these were reported as
# NEEDS-FALLBACK. Resolving through templates.json -- the same rows run_all.py
# stamps into master_results.json's "folder" -- means a key can no longer
# quietly match nothing.
#
# NOT here: MPyConstraint/Procrustes Tags -- still correct, but the
# original reason for it is DEAD (T112, re-measured 2026-08-21). That reason was
# "the drop on record is the AI porter calling a hallucinated svd3(), which a
# high-effort re-port can fix". There is no drop on record any more: the node
# builds with `a:ai-not-needed` (every compute lowers deterministically, no LLM
# is involved) and is parity-verified against the interpreted node end to end
# (T111). Its live component-tag read lowers natively -- the tags ride the mesh
# DATA off the input handle.
#
# It stays out of HONEST_DROP for a DIFFERENT reason: classify() only consults
# this tuple when compile FAILED (`if not cok and folder in HONEST_DROP`), and a
# node that compiles deterministically today has no by-design reason to fail. So
# if it ever does drop, that is a real regression and NEEDS-FALLBACK is the
# honest verdict -- filing it correct-by-design would hide it.
HONEST_DROP_TEMPLATES = (
    "MPyNode/Ouch",                     # open() + maya.cmds at compute
    "MPyFile/File Scanline",            # open()/PIL image read
    "MPyFile/File Simple",              # open()/PIL image read
)


def _honest_drop_folders():
    """HONEST_DROP_TEMPLATES as the audit folder names they resolve to."""
    with open(os.path.join(HARNESS, "templates.json")) as fh:
        by_mpn = {r["mpn"]: r["folder"] for r in json.load(fh)}
    folders = set()
    for rel in HONEST_DROP_TEMPLATES:
        mpn = "templates/%s/template.mpn" % rel
        if mpn not in by_mpn:
            raise KeyError("HONEST_DROP has no templates.json row: %s" % mpn)
        folders.add(by_mpn[mpn])
    return folders


HONEST_DROP = _honest_drop_folders()


# Printed in this order. VERIFY-NOT-RUN sits between the two verify outcomes:
# worse than a pass, weaker evidence than a measured failure.
BUCKETS = ("OK", "HONEST-DROP", "GEOMETRY-MISMATCH", "VERIFY-FAIL",
           "VERIFY-NOT-RUN", "NEEDS-FALLBACK")

# Buckets the high-effort retry can actually help. VERIFY-NOT-RUN is deliberately
# NOT here: re-porting a node cannot make a parity check RUN, so listing it would
# send the fallback pass after nodes whose port was never in question.
FALLBACK_BUCKETS = ("NEEDS-FALLBACK", "GEOMETRY-MISMATCH", "VERIFY-FAIL")


def geometry_mismatches(rec):
    """Demo labels whose REOPENED compiled scene built different geometry than
    the interpreted demo.

    run_all.py's own reopen gate only looks at reopened / unknown_nodes /
    compiled_nodes, so without this the vertex-count comparison would be one
    more recorded number with no consumer.
    """
    bad = []
    for d in (rec.get("demos") or []):
        rj = d.get("reopen") or {}
        if rj.get("verts_match") is False:
            bad.append(d.get("label") or d.get("func_name") or "?")
    return bad


def verify_tag(node0):
    """The verify column. Never blank.

    ``verify_ran`` had exactly one producer (compile_one.py) and no consumer, so
    a node nothing verified printed an EMPTY column -- visually identical to a
    node that passed. Say which of the three it is, and when it did not run, say
    why.
    """
    if node0.get("verify_ran") is True:
        return "  verify=%s maxerr=%s" % (node0.get("verify_pass"),
                                          node0.get("verify_maxerr"))
    return "  verify=NOT-RUN (%s)" % (node0.get("verify_reason")
                                      or "no reason recorded")


def classify(rec):
    folder = rec["folder"]
    st = rec.get("status")
    cj = rec.get("compile") or {}
    cok = cj.get("ok")
    node0 = (cj.get("nodes") or [{}])[0]
    vp = node0.get("verify_pass")     # True / False / None(=skip or texture)
    if not cok and folder in HONEST_DROP:
        return "HONEST-DROP"
    if not cok:
        return "NEEDS-FALLBACK"       # compile dropped for a non-design reason
    if st != "ok":
        return "NEEDS-FALLBACK"       # compiled but a demo build/reopen failed
    if geometry_mismatches(rec):
        # Reopened clean and built the WRONG amount of geometry. The strongest
        # evidence available -- a real scene running the real demo -- so it
        # outranks the parity verdict below.
        return "GEOMETRY-MISMATCH"
    if vp is False:
        # Compiled + built + reopened, but the parity check FAILED: the port is
        # incorrect (not bit-faithful). A high-effort retry may produce a correct
        # port, so it is a fallback candidate, not a clean pass.
        return "VERIFY-FAIL"
    if node0.get("verify_ran") is not True:
        # Built and reopened, but NOTHING compared it to the Python. That is an
        # absence of evidence, not evidence of correctness, and it used to fall
        # straight through to "OK" -- the same silent-no-signal shape the
        # verify column had.
        return "VERIFY-NOT-RUN"
    return "OK"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    recs = json.load(open(path))
    recs.sort(key=lambda r: r["folder"])
    buckets = {b: [] for b in BUCKETS}
    print("%-42s %-14s %-7s %8s  demos(ok/total)" %
          ("folder", "status", "det|ai", "secs"))
    print("-" * 92)
    for r in recs:
        cj = r.get("compile") or {}
        detai = ("det" if cj.get("deterministic") else
                 ("ai" if cj.get("ai_ported") else "-"))
        demos = r.get("demos") or []
        dok = sum(1 for d in demos if d.get("status") == "ok")
        b = classify(r)
        buckets[b].append(r["folder"])
        node0 = (cj.get("nodes") or [{}])[0]
        vtag = verify_tag(node0)
        print("%-42s %-14s %-7s %8s  %d/%d%s" %
              (r["folder"], r.get("status"), detai,
               str(cj.get("seconds")), dok, len(demos), vtag))
        # multi-demo detail
        if len(demos) > 1:
            for d in demos:
                print("        - %-26s %s" % (d.get("label"), d.get("status")))
        # a mismatch is unactionable without the two numbers behind it
        for d in demos:
            rj = d.get("reopen") or {}
            if rj.get("verts_match") is False:
                print("        ! GEOMETRY [%s] compiled %s verts vs "
                      "interpreted %s (delta %+d)"
                      % (d.get("label"), rj.get("mesh_verts"),
                         rj.get("interp_mesh_verts"), rj.get("verts_delta") or 0))
    print("-" * 92)
    for b in BUCKETS:
        print("%-17s (%d): %s" % (b, len(buckets[b]), ", ".join(buckets[b]) or "-"))
    if buckets["VERIFY-NOT-RUN"]:
        print("\nWARN: %d template(s) compiled, built and reopened with NOTHING "
              "checking parity." % len(buckets["VERIFY-NOT-RUN"]))
        print("      They are NOT re-port candidates -- read each one's "
              "verify=NOT-RUN reason above and")
        print("      fix the reason the check skipped, or accept the node "
              "unverified deliberately.")
    fallback = []
    for b in FALLBACK_BUCKETS:
        fallback += buckets[b]
    if fallback:
        print("\nHIGH-FALLBACK run (T8-reliable tier -- drops + verify-fails):")
        print("  MPYNODE_PORT_EFFORT=high MPYNODE_PORT_ULTRACODE=0 \\")
        print("  python3 tools/harness/run_all.py " + " ".join(fallback))


if __name__ == "__main__":
    main()
