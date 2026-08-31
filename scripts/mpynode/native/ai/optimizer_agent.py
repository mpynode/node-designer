"""Optimize a generated .cpp by giving an AI agent the file and a build+bench loop.

Optimizing code means: change something, build it, measure it, keep it if it got
faster, revert if it did not -- many times. That is what a human (or an agentic
model with file + shell tools) does, and it is what produced the hand-optimized
reference this feature is measured against.

The previous design could not do any of that. The optimizer called the CLI with
``Read,Edit,Write,Bash`` all DENIED (the porter's ``_CLI_DENY``, correct for the
porter because porting IS a pure text task). So the only possible interaction was
"here are 3434 lines as a string, return all 3434 back but faster, in one shot,
without building or measuring". On a real node the answer came back truncated
mid-function, or as prose describing a patch -- and no amount of prompt surgery
fixes a blindfolded one-shot rewrite.

This module hands the agent a WORKSPACE instead:

    <ws>/<name>.cpp        the file to edit, in place
    <ws>/build.sh          compile it  -> <name>.bundle          (one command)
    <ws>/bench.sh          build + measure -> "MEDIAN_MS: <x>"   (one command)
    <ws>/TASK.md           goal, invariants, the Python reference

and lets it iterate. Nothing is returned through the model's response: the work
IS the edited file, which the caller reads back off disk.

The safety gate is UNCHANGED and still external: whatever the agent leaves behind
is independently recompiled, parity-checked against the interpreted Python, and
benchmarked by ``optimizer.optimize_cpp`` before it can be accepted. A
fast-but-wrong result still cannot ship.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import stat

# Same cross-compiler include rule the porter and the one-shot optimizer inject,
# from its single home. The agent edits the whole file, so it is the one path
# that can add a `#include` -- and the only compile it runs is clang.
from .translation_knowledge import PORTABILITY_RULE


_HARNESS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "tools", "harness"))
_BENCHMARK_SCRIPT = os.path.join(_HARNESS_DIR, "benchmark_node.py")


def _project_root():
    return os.path.normpath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", "..", ".."))


def _chmod_x(path):
    try:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP)
    except Exception:
        pass


def _bench_lock_env():
    """Env telling ``benchmark_node.py`` to take the benchmark lock, or ``{}``.

    The lock only ever covered ``optimizer_live._measure`` -- the ENGINE's
    benchmark. The agent measures through THIS script instead, and a
    process-table sampler caught four of them timing at once while the engine's
    own runs never overlapped even once. ``benchmark_node.py`` is the single
    file both paths run, so that is where the lock now lives; this is where the
    agent's side is told to take it.

    The engine must NOT be told: it already holds the same flock around the
    whole child, and flock belongs to the open file description, so a child
    taking it again would block on its own parent. ``optimizer_live._base_env``
    scrubs the marker for exactly that reason.

    Empty when the lock is off, which keeps every single-process run untouched.
    """
    try:
        from .optimizer_live import bench_lock_path

        path = bench_lock_path()
    except Exception:
        return {}
    if not path:
        return {}
    return {"MPYNODE_BENCH_LOCK": path, "MPYNODE_BENCH_LOCK_CHILD": "1"}


def _bench_lock_exports():
    """:func:`_bench_lock_env` as ``bench.sh`` lines.

    Exported EXPLICITLY rather than left to inheritance for the same reason
    every other var in the script is: it runs three processes down from the
    compile, under a CLI's own shell.
    """
    return ['export %s="%s"' % (k, v) for k, v in _bench_lock_env().items()]


@contextlib.contextmanager
def _agent_bench_lock_env():
    """Put the lock env in THIS process while the agent runs, then take it out.

    ``bench.sh`` is not the only way to reach ``benchmark_node.py``: its
    absolute path is written into that script in plain text, and the agent is
    invited to read the harness, so a hand-rolled invocation gets a child with
    none of bench.sh's exports and benchmarks UNSERIALISED. The agent process is
    spawned from here and inherits this environment, so every descendant it
    starts -- bench.sh or otherwise -- is covered.

    Scoped as tightly as possible: the engine's own benchmark runs AFTER
    ``agent_fn`` returns, on this same thread, and would deadlock on its parent
    if it inherited the marker. A no-op when the lock is off.
    """
    env = _bench_lock_env()
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _bench_sh(name, ntype, mayapy, ws, spec_path, bench_array, bench_geo,
              bench_iters):
    """A single command the agent can run to get one number back.

    Builds first (so it can never measure a stale bundle) and runs the benchmark
    in a FRESH mayapy -- Maya cannot reload a plug-in in-process, so measuring
    twice in one session would silently re-measure the first build.
    """
    root = _project_root()
    args = ['"$HERE/%s.bundle"' % name, ntype,
            "--iters", str(int(bench_iters))]
    if spec_path:
        args += ["--spec", '"%s"' % spec_path,
                 "--bench-array", str(int(bench_array)),
                 "--bench-geo", str(int(bench_geo))]
    return "\n".join([
        "#!/usr/bin/env bash",
        "# Build %s.cpp and measure it. Prints 'MEDIAN_MS: <ms>'." % name,
        "set -uo pipefail",
        'HERE="$(cd "$(dirname "$0")" && pwd)"',
        '"$HERE/build.sh" || { echo "BUILD FAILED"; exit 1; }',
        'export MPYNODE_ROOT="%s"' % root,
        'export MPYNODE_USE_STUDIO=1',
        'export QT_QPA_PLATFORM=offscreen',
        'export MAYA_DISABLE_CER=1 MAYA_DISABLE_CIP=1',
        'export PYTHONPATH="%s:${PYTHONPATH:-}"' % os.path.join(root, "scripts"),
        'export MAYA_PLUG_IN_PATH="%s:$HERE:${MAYA_PLUG_IN_PATH:-}"'
        % os.path.join(root, "plug-ins"),
    ] + _bench_lock_exports() + [
        'OUT="$("%s" "%s" %s 2>&1)"' % (mayapy, _BENCHMARK_SCRIPT,
                                        " ".join(args)),
        'echo "$OUT" | grep -q "^BENCH_JSON:" || { echo "BENCH FAILED"; '
        'echo "$OUT" | tail -30; exit 1; }',
        'echo "$OUT" | sed -n "s/.*\\"median_ms\\": \\([0-9.]*\\).*/MEDIAN_MS: '
        '\\1/p" | tail -1',
        # Anything the node itself printed. Without this, stdout is captured
        # into $OUT and thrown away, so printf-profiling inside compute()
        # silently produces nothing and the agent cannot find its own hotspot.
        'echo "--- NODE OUTPUT (last 40 lines) ---"',
        'echo "$OUT" | grep -v "^BENCH_JSON:" | tail -40',
        "",
    ])


# The agent's account of the round it just ran: slug / theme / hypothesis /
# predicted_speedup / risk. Report material only -- see _TASK_MD.
ROUND_JSON = "ROUND.json"

_ROUND_META_KEYS = ("slug", "theme", "hypothesis", "predicted_speedup", "risk")


def read_round_meta(ws_dir):
    """Parse ``<ws>/ROUND.json``, or ``{}``.

    Tolerant by design: a missing, truncated or malformed file costs the report
    a paragraph, and must never cost the build a measured optimization.
    """
    try:
        with open(os.path.join(ws_dir, ROUND_JSON)) as fh:
            data = json.load(fh)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    meta = {k: data[k] for k in _ROUND_META_KEYS if k in data}
    try:
        if meta.get("predicted_speedup") is not None:
            meta["predicted_speedup"] = float(meta["predicted_speedup"])
    except (TypeError, ValueError):
        meta.pop("predicted_speedup", None)
    return meta


def render_history_block(ledger):
    """What EARLIER rounds already tried, for the next round's prompt.

    Each round is a fresh process, so without this the agent re-derives from
    scratch and can spend itself re-proposing an idea that already measured
    slower. Returns "" when there is nothing to say -- an empty ledger, or a
    ledger holding only the baseline (round 1, where nothing has been TRIED
    yet) -- so the block is absent rather than hollow, exactly like the
    conditional ``{budget_block}``.

    Rounds with no stated theme are still listed: dropping them would tell the
    next round that fewer things were attempted than were.
    """
    rows = [r for r in (ledger or []) if getattr(r, "index", 0)]
    if not rows:
        return ""
    lines = ["", "## What earlier rounds already tried",
             "Each round before this one ran in a SEPARATE session and could not",
             "see the others. This is their record -- do not spend this round",
             "re-deriving it. An idea listed as slower already lost on THIS",
             "workload; beating it needs a different approach, not a retry.",
             ""]
    for r in rows:
        theme = (getattr(r, "theme", "") or "").strip()
        head = "* round %s -- %s" % (r.index, theme or "(no theme recorded)")
        bits = [str(getattr(r, "outcome", "") or "?")]
        ms = getattr(r, "ms", None)
        if ms is not None:
            bits.append("measured %.3f ms" % ms)
        pred = getattr(r, "predicted_speedup", None)
        if pred is not None:
            bits.append("predicted %.2fx" % pred)
        lines.append("%s -- %s" % (head, ", ".join(bits)))
        hyp = (getattr(r, "hypothesis", "") or "").strip()
        if hyp:
            lines.append("    reasoning: %s" % hyp)
        if getattr(r, "outcome", "") == "accept":
            # Re-proposing a change that is already in the file wastes a round.
            lines.append("    ACCEPTED -- already applied in the file you were "
                         "given. Build on it, do not redo it.")
    lines.append("")
    return "\n".join(lines)


_TASK_MD = """# Optimize `{name}.cpp` for speed

## Goal
Make this Maya plug-in node compute FASTER. Correctness is not negotiable: the
numerical result must stay identical.

## The loop (this is the job)
```
./bench.sh          # builds {name}.cpp and prints  MEDIAN_MS: <ms>
```
Record the starting number. Then repeatedly: edit `{name}.cpp`, run `./bench.sh`,
keep the change if the number went DOWN, revert it if it did not. Keep going
while you are still finding wins. Measure -- do not assume an edit is faster.

Baseline on entry: **{baseline}**
{budget_block}{history_block}
## The workload you are optimizing for
The benchmark drives every input at scale and times the whole `compute()`:

* typed geometry inputs are a `polySphere(sx=sy={geo})` -- roughly {verts} verts
* every array input is filled with **{array} elements**
* one tick = `dgdirty(node)` then pull, median of {iters}

Pick the algorithm that wins at THOSE sizes. The right structure for 10 000
points is not the right one for 100, and the ratio between the two numbers above
decides whether per-query work or per-input-element work dominates.

Two node shapes, two different answers. Decide which you have BEFORE proposing
anything.

* ELEMENTWISE / GRID -- O(output), fixed arithmetic per element. The arithmetic
  is NOT the bottleneck here; per-access overhead and whole-array temporaries are
  the whole answer.
* QUERY -- an inner loop over a whole SECOND collection per output element
  (nearest point, nearest neighbour, containment, intersection, any "for each x,
  scan all y"). Cost is O(N x M), and NO amount of raw-pointer access, fusion or
  strength reduction changes that exponent. The lever is an ACCELERATION
  STRUCTURE over the scanned collection -- BVH, k-d tree, uniform or hash grid,
  sorted array plus binary search -- built ONCE, reused across queries, and it
  usually wants to survive across evaluations too. Measured on the voxelize node,
  replacing a linear closest-point scan with a binned-SAH BVH took one evaluation
  from 714 s to 0.125 s, and the sixteen rounds of constant-factor work that
  followed it each moved the total by single- or double-digit percent. If the
  node is query-shaped, spend the round on the structure.

The PORTER is separately forbidden to replace a named structure with a scan.
Your job is the mirror image: a scan that reached you is either one the Python
genuinely had or one the port introduced, and either way it is yours to
accelerate -- so long as the result is identical.

SIZE GATE for threading: do not open a parallel region for a pass whose SERIAL
cost is under ~50 us -- a condvar region costs ~4.8 us at 2 threads, ~18.3 us at
8 and ~42.7 us at 16, so the overhead GROWS with thread count rather than being a
constant. Weigh each pass against the sizes above before you reach for the
threading section below.

## Scope: read anything, change only your file
The ONE file you may modify is, by absolute path:

    {cpp_path}

Edit exactly that path. Other copies of `{name}.cpp` exist elsewhere on this
machine, including one in the PARENT directory of this workspace; they are build
scratch. `./bench.sh` only ever compiles the file above, so editing any other
copy produces edits that are never built and timings that never move.

Reading is unrestricted -- the benchmark harness and the Maya plug-in sources are
on this machine and you are welcome to read them to understand exactly what is
being timed. Do not spend the budget wandering further than that.

`build.sh` and `bench.sh` are FIXED. Editing them -- or the harness they call --
does not make the node faster, it makes the measurement wrong. Both are
checksummed before and after this run; if either changed, everything you did is
discarded. The same is true of "optimizing" by weakening the work: skipping
output writes, memoizing the OUTPUT so a re-evaluation returns the last answer,
or returning early. The independent parity check catches those and throws the
run away. (Caching derived STATE across evaluations is different, and
encouraged -- see below.)

## What you may change
Anything inside `{name}.cpp`, including the large inlined `nd_runtime.h` section:
specialise it, bypass it, or replace a generic helper with a purpose-built one
for this node. Add structs, precomputed tables, flattened trees, SoA layouts,
cache-friendly traversals -- whatever the measurement rewards. Algorithmic
changes are the point; micro-tweaks rarely move a real workload.

## Caching across evaluations -- allowed, and usually the biggest single win
Maya re-invokes `compute()` when ANY input goes dirty, so work derived from an
input that did NOT change is recomputed for nothing. On a node whose expensive
structure depends on one input (a tree, a factorisation, a neighbour table, a
resampled curve) while a DIFFERENT input animates, caching that structure is
routinely worth more than every micro-optimisation combined.

Do it in this shape, or not at all:

1. Cache DERIVED STATE, never the final output. Maya already caches clean plug
   values; re-caching the result is not an optimisation, it is skipping the work
   the benchmark is timing, and the parity check treats it as a wrong answer.
2. Invalidate on ALL THREE: `setDependentsDirty` (DG), `preEvaluation` (EM), and
   a cheap data fingerprint (buffer pointer + element count) as a backstop.
   Any one missing means correct in one evaluation mode and stale in another.
3. Per-instance members ONLY. Never a `static`/global map keyed by node: that
   leaks for the life of the session and lets a new node inherit a deleted
   node's results. If the file you were handed ALREADY has one -- a
   `static std::vector<NodeState*>` found-or-created on `(const void*)this` at
   the top of compute() -- then lifting it to a per-instance member is IN SCOPE
   and worth a round. The porter that wrote it could only edit between the PORT
   markers; you can edit the whole file, class body included. Move the struct
   and a `NodeState _state;` member into the class (keep the members' default
   initialisers -- the node's constructor names none of them), replace the
   lookup with `NodeState* st = &_state;`, and delete the registry.
4. Thread-safe by construction. Parallel EM evaluates nodes concurrently, so the
   validity flag must be `std::atomic` (or mutex-guarded) and the rebuild must
   happen under the lock.
5. Free it in the destructor, and keep it bounded.

Parity re-presents an EARLIER input set after driving many fresh ones, so a
cache keyed on the wrong SCALAR or ARRAY input is caught even though it looks
correct while inputs keep changing. GEOMETRY is covered on the GEO parity path
only: it re-wires a FRESH upstream shape per config across five configs, so a
mesh-keyed cache that never invalidates diverges there. The SCALAR parity path
still wires geometry ONCE and leaves that connection in place for its whole
drive loop, so a cache keyed on a geometry input reached through THAT path is
not covered -- earn it with the item-2 fingerprint.

## Already measured slower on Apple Silicon (M4), on a BVH closest-point sweep
Each of these was tried and measured. None is banned -- a different node, data
shape or CPU can flip any of them -- but proposing one spends your round on a
coin that has already come up tails, so do it only if you can say why THIS node
is different, and say that reason in ROUND.json.

* branchless triangle / region-test kernel -- 30-40% SLOWER. The core predicts
  the region tests well, so removing the branch only added work.
* structure-of-arrays 4-lane triangle kernel -- slower, same cause.
* prefetching both children on each traversal step -- neutral on one mesh, 11%
  worse on another. Traversal is bound by DEPENDENT loads, which a prefetch
  issued at the same time cannot hide.
* float instead of double for a box-distance test -- no gain, and it changed
  which of two exactly-equidistant candidates won. That is a parity failure.
* a per-triangle box reject inside a leaf -- halved the exact-kernel calls
  (286 -> 145 per query) and was STILL slower: the exact kernel is cheap and the
  reject added an unpredictable branch and a second memory stream.
* 32 SAH bins instead of 16 -- 122.2 vs 122.8 nodes visited per query. The tree
  was already at its plateau; a better split heuristic was not the lever.

The pattern behind all six: work removed from a well-predicted branch or an
already-cheap kernel is not work you get back, and the traversal is latency-bound
rather than throughput-bound. Prefer changes that remove a LEVEL of work -- a
better structure, a cache across evaluations, fewer nodes visited -- over changes
that make the same work marginally cheaper.

## Invariants (a violation is rejected downstream, so the run is wasted)
* The file stays ONE self-contained translation unit that compiles with
  `./build.sh`. No new headers outside Maya's SDK and the C++17 standard library.
  That library contains `<thread>`, `<future>` and `<atomic>`, so this bullet is
  NOT permission to thread: read "Threading" below first, where almost every
  parallel shape is prohibited.
* {portability}
  `build.sh` runs clang, so it CANNOT catch this for you -- the caching shape
  below asks for `std::atomic`/`std::mutex` explicitly, and those need
  `<atomic>`/`<mutex>` added at the top of the file.
* Keep `initializePlugin` / `uninitializePlugin`, the MTypeId, the node type
  name, and every attribute's name/type/array-ness exactly as they are. The
  node's plug interface is a contract with existing scenes.
* Results must match the reference below. This is re-verified independently
  against the interpreted Python across randomised scenes after you finish, and
  a divergent result is thrown away no matter how fast it is.
* NEVER NARROW, NOR LOOSEN, A COMPARISON THAT RESOLVES A TIE. A test that only
  RANKS candidates looks like it has slack; at an exact tie the winner is decided
  by the last bit -- recomputing a double box/point distance in float changed
  which of two exactly-equidistant triangles won, every value stayed inside
  tolerance, and the ANSWER changed. Any comparison that selects an index, a
  winner, or a branch keeps the source's TYPE, its DIRECTION, and its STRICTNESS
  (< vs <=, > vs >=).
* Keep it deterministic and thread-safe with respect to Maya's evaluation.
  Compile flags are fixed by `build.sh` (`-O3 -ffp-contract=off`); do not relax
  floating-point strictness to gain speed -- that is exactly what parity catches.

## Threading: one shape is permitted, the rest are prohibited
Nothing downstream checks any of this. The plausibility check on your output
inspects brace balance and file size, nothing more, so this prompt is the ONLY
enforcement -- a violation ships silently or surfaces as a race much later.

Prohibited, each with its reason:

* NO parallel REDUCTION (sum/min/max/argmin/accumulate). The numeric parity gate
  is TOLERANCE-based (1e-3/1e-4), so a reassociated sum drifts ~1 ULP and PASSES
  while breaking byte-parity. The gate CANNOT police this, so the rule has to.
* NO parallel append/push_back to a shared output whose ORDER then depends on
  completion order. Geo topology is compared EXACTLY, so it fails; for numeric
  outputs it is a silent race.
* NO Maya API call (MFn*, MPlug, MDataBlock, MGlobal::display*) from a worker.
* NO per-evaluate thread creation.
* NO letting the thread count or the chunk boundaries affect the ANSWER.

PERMITTED: a PARALLEL MAP WITH DETERMINISTIC PER-ELEMENT WRITE, subject to ALL of

1. the output container is SIZED BEFORE the region opens; each worker writes only
   out[i] for i in its own half-open range; no push_back, no shared accumulator,
   no atomic that decides a VALUE;
2. element i's value is a pure function of i and read-only inputs, so the result
   is independent of the chunk split;
3. ZERO Maya API in the worker body -- snapshot to raw C++ buffers on the calling
   thread first;
4. a PERSISTENT pool held as a per-node member, joined before compute() returns
   and freed in the destructor -- never created per-evaluate;
5. where an order-dependent MERGE is unavoidable, workers fill PRIVATE arenas and
   the merge runs SERIALLY, in fixed task-index order, on the calling thread.

A worked example of this shape is a KD-tree build/query kernel: the disjoint-
range gather(lo,hi) map with an n >= 20000 serial fallback, plus a private-arena
build closed by a deterministic serial splice. That shape shows points 1, 2 and
5 only -- it creates its threads per call,
which point 4 forbids here, and it sizes itself off hardware_concurrency with no
env knob. Copy the shape, not those two details.

Do NOT spread top-level passes eagerly. An external run that opened ~93 parallel
regions lost; pick the one pass that clears the ~50 us floor.

Cursor placement is a CORRECTNESS rule, not a tuning one: the chunk cursor MUST
be a member of the pool, NEVER file-scope. Maya's EM evaluates independent nodes
concurrently, so two instances of the same compiled node can be inside one region
at once and each rewinds the other's cursor -- 30 of 30 trials dropped vertices,
worst case 50% left unwritten. No single-instance test can see this.

Prefer a dynamic chunk cursor to an equal-block partition (+34-45%). Do NOT ship
a busy-spin pool -- it wins in isolation and collapses under load.

Payoff and its ceiling, honestly sourced: 10.2x-11.7x measured on a 12P+4E Apple
M4 for a per-vertex deformer sweep at N=10k-40k, bit-identical to serial. The
region runs underneath Maya's own EM pool. Our nodes are classified Serial --
established via dbpeek, NOT by observing a compute on a non-main thread -- so
they can be concurrent with other scheduling groups, and with 4-8 deformers
evaluating at once the incremental gain falls to 1.5x-3.6x. Thread it anyway, but
size the work against that number, not the single-node one. A rig with many
instances is not what this bench measures. Cap the worker count behind an env
knob so it can be turned down without a rebuild.

## Numerical reference (the parity target)
This is the original Python the C++ was generated from.

```python
{compute}
```
{init_block}
## When you are done
Leave the FASTEST version that builds and is numerically correct in
`{name}.cpp`. Do not leave the file mid-edit or non-compiling -- run `./bench.sh`
one last time and confirm it succeeds.

Then write `ROUND.json` beside it, describing this round:

```json
{{
  "slug": "simd_argmin",
  "theme": "hand-vectorise the argmin; LLVM will not vectorise an index-carrying reduction",
  "hypothesis": "the fcmp->fcsel chain is loop-carried, so use two independent accumulators",
  "predicted_speedup": 2.5,
  "risk": "f32 lanes could reorder near-ties, so accumulate in f64"
}}
```

* `slug` -- lower_snake_case, <= 40 chars, naming the ONE change that produced
  the win. It becomes this revision's filename, so make it read like a step in a
  story: `hoist_invariant`, `raw_points`, `thread_queries`, `cache_tree`.
* `theme` -- one sentence a reader who has not seen the diff can understand.
* `predicted_speedup` -- what you expected BEFORE you measured. Write what you
  actually predicted, including when the measurement went on to disagree. A
  prediction that missed ("structure-of-arrays will be faster" -- it was a 2x
  REGRESSION) is the most useful line in the report, so do not revise it to
  match the result.

This file is documentation, not a deliverable: it is read after the run and
cannot make a slow version look fast. Your reply text is discarded -- the file
on disk and this JSON are the whole output.
"""


_BUDGET_MD = """
## Your time budget: {mins} min
You are killed at {mins} min, wherever you are. One `./bench.sh` costs roughly a
minute (it builds, then starts a fresh Maya), so plan for on the order of
{cycles} measured attempts -- spend them on ideas that could pay off big, not on
re-tuning a constant you already tuned.

Keep `{name}.cpp` in a COMPILING, benchmarked state at all times. Make one
change, measure it, and only then start the next one. If the kill lands while
the file is half-edited it will not build, and everything you achieved in this
run is thrown away. Stop early rather than start an edit you cannot finish and
measure.
"""


def build_workspace(spec, ws_dir, cpp_text, *, maya=None, ntype=None,
                    spec_path=None, bench_array=512, bench_geo=40,
                    bench_iters=9, baseline_ms=None, budget_s=None,
                    history=None):
    """Create the agent's workspace and return ``(cpp_path, task_prompt)``."""
    from ..compiler import build_scripts
    from ..toolchain import toolchain

    name = spec["suggested"]["node_type_name"]
    ntype = ntype or name
    maya = maya or toolchain.default_maya_dir()

    os.makedirs(ws_dir, exist_ok=True)
    cpp_path = os.path.join(ws_dir, name + ".cpp")
    with open(cpp_path, "w") as fh:
        fh.write(cpp_text)

    # The SAME build script the shipped node uses -- flat layout, so <name>.cpp
    # and <name>.bundle sit next to each other in the workspace.
    build_path = os.path.join(ws_dir, "build.sh")
    # newline="" for the same reason as the bundler's build.sh: the generator
    # already emits LF, and a second translation on a Windows host would make
    # the script CRLF and die with "$'\r': command not found". No-op on macOS.
    with open(build_path, "w", newline="") as fh:
        fh.write(build_scripts.generate_build_sh(spec, maya=maya))
    _chmod_x(build_path)

    bench_path = os.path.join(ws_dir, "bench.sh")
    with open(bench_path, "w", newline="") as fh:
        fh.write(_bench_sh(name, ntype, toolchain.mayapy_path(maya), ws_dir,
                           spec_path, bench_array, bench_geo, bench_iters))
    _chmod_x(bench_path)

    init = (spec.get("init") or "").strip()
    init_block = ("\nAnd its init (runs once):\n\n```python\n%s\n```\n" % init
                  if init else "")
    # Only state a deadline when there IS one; with the timeout preference off
    # the run is unbounded and a fabricated clock would just cut it short.
    budget_block = ""
    if budget_s not in (None, 0) and budget_s != float("inf"):
        mins = max(1, int(float(budget_s) // 60))
        budget_block = _BUDGET_MD.format(mins=mins, cycles=max(1, mins - 5),
                                         name=name)
    # Mirrors verify._make_upstream_shape, which seeds a benchmark geo input
    # with polySphere(sx=sy=density). Descriptive only -- the agent is allowed
    # to read the harness and check, so a drift here misleads nobody for long.
    verts = max(0, int(bench_geo) * (int(bench_geo) - 1) + 2)
    task = _TASK_MD.format(
        name=name,
        compute=(spec.get("compute") or "").strip() or "(none)",
        init_block=init_block,
        budget_block=budget_block,
        history_block=render_history_block(history),
        portability=PORTABILITY_RULE,
        geo=int(bench_geo), verts="{:,}".format(verts),
        array=int(bench_array), iters=int(bench_iters), cpp_path=cpp_path,
        baseline=("%.3f ms" % baseline_ms) if baseline_ms else "run ./bench.sh")
    with open(os.path.join(ws_dir, "TASK.md"), "w") as fh:
        fh.write(task)
    # The workspace is reused every round. A leftover ROUND.json would be read
    # back as THIS round's account of itself, mislabelling one change with the
    # previous change's theme.
    try:
        os.remove(os.path.join(ws_dir, ROUND_JSON))
    except OSError:
        pass
    return cpp_path, task


def _guarded_paths(ws_dir):
    """Files whose contents define what "faster" MEANS for this run.

    The agent has a shell, so "make the number go down" is satisfiable by
    editing the thing that produces the number. Instruction alone is not a
    control; these are checksummed around the run.
    """
    return [os.path.join(ws_dir, "build.sh"),
            os.path.join(ws_dir, "bench.sh"),
            _BENCHMARK_SCRIPT,
            os.path.normpath(os.path.join(
                os.path.dirname(__file__), "..", "toolchain", "verify.py"))]


def _digests(paths):
    import hashlib
    out = {}
    for p in paths:
        try:
            with open(p, "rb") as fh:
                out[p] = hashlib.sha256(fh.read()).hexdigest()
        except Exception:
            out[p] = None
    return out


def optimize_with_agent(spec, ws_dir, cpp_text, agent_fn, *, maya=None,
                        ntype=None, spec_path=None, bench_array=512,
                        bench_geo=40, bench_iters=9, baseline_ms=None,
                        budget_s=None, log_cb=None, meta_out=None,
                        history=None):
    """Run the agent over ``cpp_text`` in ``ws_dir``; return the edited source.

    Returns ``cpp_text`` unchanged if the agent failed, left nothing usable, or
    altered the measurement itself -- the engine then finds no gain and keeps
    the original.

    ``meta_out`` (optional dict) is filled with the agent's own account of the
    round from ``ROUND.json`` -- slug, theme, hypothesis, predicted speedup,
    risk. Filled even on the discard paths, so a rejected round can still be
    reported by name instead of as an anonymous failure.
    """
    cpp_path, task = build_workspace(
        spec, ws_dir, cpp_text, maya=maya, ntype=ntype, spec_path=spec_path,
        bench_array=bench_array, bench_geo=bench_geo, bench_iters=bench_iters,
        baseline_ms=baseline_ms, budget_s=budget_s, history=history)
    guarded = _guarded_paths(ws_dir)
    before_digest = _digests(guarded)
    before = cpp_text
    agent_err = None
    try:
        with _agent_bench_lock_env():
            agent_fn(task)
    except Exception as exc:
        # Cancel is the user saying stop, so it propagates. Any OTHER failure --
        # in practice the wall-clock kill, which lands after the agent has already
        # made and MEASURED real edits -- must not throw that work away: the
        # agent's output is the file on disk, not its reply.
        from .llm_client import PortCancelled
        if isinstance(exc, PortCancelled):
            raise
        agent_err = exc
    finally:
        # Read back whatever is on disk EVEN IF the agent errored or was killed
        # late: a completed edit is still worth gating. The external
        # compile+parity+benchmark decides whether it is any good.
        try:
            with open(cpp_path) as fh:
                after = fh.read()
        except Exception:
            after = before
        # Read the account BEFORE any discard branch below, so a round thrown
        # away for touching the harness is still named in the report.
        if meta_out is not None:
            try:
                meta_out.update(read_round_meta(ws_dir))
            except Exception:
                pass
    if agent_err is not None and log_cb is not None:
        try:
            log_cb("[optimizer] the agent run ended early (%s: %s); gating "
                   "whatever it had already finished"
                   % (type(agent_err).__name__, agent_err))
        except Exception:
            pass
    changed = [p for p, d in _digests(guarded).items()
               if d != before_digest.get(p)]
    if changed:
        # The measurement moved under us, so no number from this run means
        # anything. Discard the candidate rather than gate it against a ruler
        # the candidate may have redrawn.
        if log_cb is not None:
            try:
                log_cb("[optimizer] DISCARDED: the agent modified the "
                       "measurement itself (%s)"
                       % ", ".join(os.path.basename(p) for p in changed))
            except Exception:
                pass
        return before
    if not after.strip():
        return before
    if log_cb is not None and after != before:
        try:
            log_cb("[optimizer] agent edited %s (%d -> %d bytes)"
                   % (os.path.basename(cpp_path), len(before), len(after)))
        except Exception:
            pass
    return after
