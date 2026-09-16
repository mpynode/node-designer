"""Offline, attended AI-optimizer driver over one compiled node's source .cpp.

This is the metaClay-style loop as a repeatable tool: point it at a
``build/source/<node>.cpp`` plus the node's spec (the manifest's per-node spec)
and, optionally, a parity harness; it runs the parity-and-speed-gated engine
(``optimizer.optimize_cpp``) with the live adapters and reports whether a faster,
still-correct rewrite was found. Every proposal is snapshotted (numbered) next to
the source, a ledger is written, and with ``--apply`` the winner is swapped into
the live ``.cpp`` (the original is backed up first).

It is ATTENDED: an AI rewrite of hand-tuned C++ deserves a human glance before it
ships, and a real run spends model tokens + minutes of compiling.

Usage (plain python or mayapy; adapters spawn their own fresh mayapy):
    python optimize_node.py --source build/source/metaClay.cpp \
        --spec spec.json [--node-type metaClay] [--out-plug outMesh] \
        [--parity metaballs_parity.py] [--rounds 3] [--min-speedup 1.05] \
        [--maya /Applications/Autodesk/maya2026] [--apply]

Prints 'OPTIMIZE_JSON:{...}' as the last line; exit 0 iff a candidate was accepted.
"""
import argparse
import dataclasses
import json
import os
import sys

from mpynode.native.ai import optimizer, optimizer_live


def _tee_optimizer(optimize_fn, snap_dir, node):
    """Wrap the model's optimize_fn so every proposed candidate is written to a
    numbered snapshot before it is compiled -- so an attended operator can diff
    exactly what the AI proposed each round, accepted or not."""
    state = {"i": 0}

    def wrapped(cpp_text):
        cand = optimize_fn(cpp_text)
        state["i"] += 1
        path = os.path.join(snap_dir, "%s.opt%d.cpp" % (node, state["i"]))
        try:
            with open(path, "w") as fh:
                fh.write(cand)
        except Exception:
            pass
        return cand

    return wrapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="path to the node's .cpp")
    ap.add_argument("--spec", required=True, help="path to the node spec JSON")
    ap.add_argument("--node-type", default=None)
    ap.add_argument("--out-plug", default="outMesh")
    ap.add_argument("--parity",      default=None, help="parity harness .py (PARITY_JSON)")
    ap.add_argument("--rounds",      type=int,     default=3)
    ap.add_argument("--min-speedup", type=float,   default=1.05)
    ap.add_argument("--bench-res",   type=int,     default=16)
    ap.add_argument("--maya", default=None)
    ap.add_argument("--apply", action="store_true",
                    help="swap the winner into the live .cpp (backs up original)")
    args = ap.parse_args()

    result = {"accepted": False, "source": args.source, "reason": "",
              "baseline_ms": None, "best_ms": None, "speedup": 1.0,
              "rounds": 0, "ledger": [], "errors": []}
    try:
        with open(args.source) as fh:
            baseline = fh.read()
        with open(args.spec) as fh:
            spec = json.load(fh)
        node     = args.node_type or spec["suggested"]["node_type_name"]
        out_dir  = os.path.dirname(os.path.abspath(args.source))
        snap_dir = os.path.join(out_dir, "opt_snapshots")
        os.makedirs(snap_dir, exist_ok=True)
        # Compile candidates into an ISOLATED scratch dir, NOT the source dir:
        # make_adapters.compile_fn writes <build_scratch>/<node>.cpp for every
        # candidate (baseline + each round) BEFORE the parity+speed gate, so if it
        # were handed the source dir that path would equal args.source and a
        # proposed/rejected candidate would clobber the hand-tuned original. The
        # real source is only rewritten on accept + --apply below (with a backup).
        build_scratch = os.path.join(snap_dir, "build")
        os.makedirs(build_scratch, exist_ok=True)

        # Check the provider is reachable BEFORE spending a baseline compile.
        from mpynode.native.ai.llm_client import check_provider
        prov = check_provider()
        if not prov.get("ok"):
            result["reason"] = "provider not reachable: %s" % (
                "; ".join(prov.get("problems", [])) or "unknown")
            result["errors"].append(result["reason"])
            print("OPTIMIZE_JSON:" + json.dumps(result))
            sys.exit(1)

        ad = optimizer_live.make_adapters(
            spec, build_scratch, maya=args.maya, node_type=node,
            out_plug=args.out_plug, parity_harness=args.parity,
            bench_res=args.bench_res, log_cb=lambda m: print("[opt] %s" % m))
        ad["optimize_fn"] = _tee_optimizer(ad["optimize_fn"], snap_dir, node)

        res = optimizer.optimize_cpp(
            baseline, rounds=args.rounds, min_speedup=args.min_speedup,
            label=node, log_cb=lambda m: print("[engine] %s" % m), **ad)

        result["accepted"]    = res.accepted
        result["reason"]      = res.reason
        result["baseline_ms"] = res.baseline_ms
        result["best_ms"]     = res.best_ms
        result["speedup"]     = res.speedup
        result["rounds"]      = res.rounds
        result["ledger"]      = [dataclasses.asdict(r) for r in res.ledger]

        # Persist the ledger + winner alongside the source.
        with open(os.path.join(snap_dir, "%s.ledger.json" % node), "w") as fh:
            json.dump(result, fh, indent=2)
        if res.accepted:
            with open(os.path.join(snap_dir, "%s.winner.cpp" % node), "w") as fh:
                fh.write(res.best_cpp)
            if args.apply:
                backup = os.path.join(snap_dir, "%s.pre_opt.cpp" % node)
                with open(backup, "w") as fh:
                    fh.write(baseline)
                with open(args.source, "w") as fh:
                    fh.write(res.best_cpp)
                result["applied_to"] = args.source
                result["backup"]     = backup
    except Exception:
        import traceback
        result["errors"].append(traceback.format_exc())
    finally:
        print("OPTIMIZE_JSON:" + json.dumps(result))
        sys.exit(0 if result.get("accepted") else 1)


if __name__ == "__main__":
    main()
