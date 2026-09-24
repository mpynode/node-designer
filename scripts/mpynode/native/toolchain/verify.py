"""Parity verification for compiled native plugins.

Split out of :mod:`mpynode.native.toolchain.compile_controller` (the BUILD
half). This module owns the PARITY-VERIFY half: load a freshly built ``.bundle``
and check each surviving node's compiled type against its Python original
mPyNode, per MPx family (scalar compute / deformer / iksolver / geometry
generator). Two delivery wrappers are provided -- ``main_thread_verify_fn``
(marshals onto Maya's main thread for a GUI caller) and ``subprocess_verify_fn``
(runs the check in a throwaway ``mayapy`` process so the caller's live scene is
never touched). ``compile_controller.compile_plugin`` calls ``_default_verify``
(or an injected ``verify_fn``) at its verify stage.

Import-safe under plain ``python3``: there is NO ``import maya`` at module top;
every Maya / numpy / mpynode-runtime import is lazy INSIDE the function that
needs it, mirroring the original module's headless guarantee.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import time

from mpynode.native.toolchain import toolchain

_MAYA_DEFAULT = toolchain.preferred_maya_dir()


# ---------------------------------------------------------------------------
# Default parity verify (lazily imports maya -- never at module top)
# ---------------------------------------------------------------------------


def _load_python_plugins(cmds):
    """Register the mpynode Python node types (``mpynode_api1`` /
    ``mpynode_api2``) in this Maya session, quietly and idempotently.

    The per-family parity checks rebuild the Python ORIGINAL with
    ``createNode(<mPy type>)`` -- mPyMesh, mPyDeformer, mPyIkSolver, ... -- and
    in the Node Designer those types are always registered. The headless build
    worker only initialises ``maya.standalone``, so there the type was unknown
    and every such family reported "verify could not run" ('NoneType' has no
    add_input_attr / Unable to create dependency node) while only the families
    that create their twin through a wrapper (which loads the plug-in itself)
    ever ran the generic check. Never raises: a load failure surfaces as the
    same per-node verify reason it always did."""
    for p in ("mpynode_api1", "mpynode_api2"):
        try:
            if not cmds.pluginInfo(p, q=True, loaded=True):
                cmds.loadPlugin(p, quiet=True)
        except Exception:
            pass


def _default_verify(bundle_path, rows, maya=_MAYA_DEFAULT,
                    run_authored_tests=True):
    """Load the bundle and parity-check each surviving node vs its Python original.

    Returns ``{type_name: {"ran": bool, "pass": bool|None, "maxerr": float|None,
    "tol": float|None, "reason": str}}``. NEVER raises -- a verify failure is a
    node-row flag, not a build failure (design "Failure handling").

    ``run_authored_tests`` (default True) additionally runs each node's authored
    ``@maya_test`` methods against the COMPILED node -- a stronger, author-written
    correctness gate. Default True so every headless caller (the test suite, the
    per-template audit, a direct call) keeps exercising authored tests; the Node
    Designer compile dialog passes ``False`` to make running them opt-in (the
    built-in generic byte-parity check below always runs regardless).

    Lazily imports ``maya.cmds`` INSIDE this function so the module stays
    import-safe under plain python3. Implements the same per-family verify
    (scalar / deformer / iksolver) the parity sweep uses. In the app this runs
    on the caller's thread, which marshals it to Maya's main thread.
    """
    out = {}
    try:
        import maya.cmds as cmds  # noqa: F401  (lazy: keeps module headless-safe)
    except Exception as exc:
        for r in rows:
            out[r["type_name"]] = {
                "ran": False, "pass": None, "maxerr": None, "tol": None,
                "reason": "verify skipped (no Maya runtime): %s" % exc,
            }
        return out

    # The Python originals need their node types registered (see the helper).
    _load_python_plugins(cmds)
    base = os.path.basename(bundle_path)
    try:
        if not cmds.pluginInfo(base, q=True, loaded=True):
            cmds.loadPlugin(bundle_path)
    except Exception as exc:
        for r in rows:
            out[r["type_name"]] = {
                "ran": False, "pass": None, "maxerr": None, "tol": None,
                "reason": "loadPlugin failed: %s" % exc,
            }
        return out

    # ONE deadline for the WHOLE bundle, computed before the row loop and threaded
    # down -- never per node. The dialog calls subprocess_verify_fn with
    # timeout=600 for the entire bundle, so a per-node timing budget on a multi-node
    # build would push the process past it and turn EVERY row into "subprocess
    # verify produced no result", which is far worse than no timing at all.
    deadline = time.perf_counter() + _TIMING_BUDGET_S
    for r in rows:
        tn = r["type_name"]
        try:
            res = _verify_one(cmds, bundle_path, r["spec"], maya=maya,
                              deadline=deadline)
        except Exception as exc:
            # A harness exception means we COULD NOT verify -- NOT a parity
            # failure. Flag it as a not-run skip (ran=False/pass=None) so the
            # build is never falsely reported as "FAILED parity".
            res = {"ran": False, "pass": None, "maxerr": None, "tol": None,
                   "reason": "verify could not run: %s" % exc}
        # Generic parity did not run/pass -> the node was never timed. Wherever
        # parity SKIPS (skinCluster, mesh-input IK solvers, stride-coupled arrays,
        # NURBS CV deformers, AI-ported RNG, ...) that is a real coverage hole, and
        # an ABSENT timing field would read as "measured, fine". Say it instead.
        if _timing_enabled() and "timing" not in res:
            res["timing"] = {
                "measured": False,
                "reason":   "not timed -- generic parity did not pass for this "
                          "node, so there is no trustworthy pair to measure (%s)"
                          % (res.get("reason") or "skipped")}
        # Augment with the node's authored @maya_test(s): a stronger gate for
        # behaviour the generic harness can't drive (moving UVs, deleting a face).
        # Runs the SAME test the interpreted node passes against the COMPILED
        # node, and can upgrade a generic "skip" into a real pass/fail. Gated on
        # ``run_authored_tests`` so the GUI can make it opt-in.
        if run_authored_tests:
            try:
                authored = _run_authored_tests(cmds, bundle_path, r["spec"])
            except Exception as exc:
                authored = {"ran": True, "passed": False, "count": 0,
                            "passes": 0,
                            "reason": "authored @maya_test harness error: %s"
                            % exc}
            if authored is not None:
                res = _merge_authored_test(res, authored)
        out[tn] = res
    return out


def _run_authored_tests(cmds, bundle_path, spec):
    """Run the node's authored ``@maya_test``(s) (from ``spec['methods']``)
    against a freshly-created COMPILED node instance. Returns ``None`` when the
    node defines no tests, else an aggregate
    ``{ran, passed, count, passes, reason}``. Each test runs in its own fresh
    scene (mirroring :func:`_verify_geo`) so they can't contaminate one another.
    """
    source = (spec or {}).get("methods") or ""
    from mpynode._common import node_setups

    test_specs = node_setups.find_tests(source)
    if not test_specs:
        return None
    from mpynode._common.methods import methods_registry

    name = spec["suggested"]["node_type_name"]
    base = os.path.basename(bundle_path)
    # The interpreted node gets time1.outTime wired into every non-array kTime
    # input by the wrapper's add_input_attr (_mpy_node.py: attr_type == "time"
    # and not is_array), and .mpn deserialize restores it. createNode() below
    # does not, so an authored test that reads a time-driven input sees 0.0 on
    # the compiled node while the interpreted one sees currentTime -- a Game of
    # Life board seeded from `frame` then diverges and the test fails on a node
    # whose C++ is correct.
    time_ins = [k for k, v in (spec.get("inputs") or {}).items()
                if v.get("type") == "time" and not v.get("is_array")]
    results = []
    for ts in test_specs:
        cmds.file(new=True, force=True)
        if not cmds.pluginInfo(base, q=True, loaded=True):
            cmds.loadPlugin(bundle_path)
        comp = cmds.createNode(name)
        for a in time_ins:
            try:
                if not cmds.objExists("time1"):
                    cmds.createNode("time", name="time1", skipSelect=True)
                cmds.connectAttr("time1.outTime", "%s.%s" % (comp, a),
                                 force=True)
            except Exception:
                pass
        results.append(
            methods_registry.run_test_on_node_name(comp, source, ts.func_name))
    passes = sum(1 for r in results if r["passed"])
    fails  = [r for r in results if not r["passed"]]
    reason = "" if not fails else "; ".join(
        "%s: %s" % (r["name"], r["error"]) for r in fails)
    return {"ran": True, "passed": not fails, "count": len(results),
            "passes": passes, "reason": reason}


def _merge_authored_test(res, authored):
    """Fold an authored ``@maya_test`` aggregate into a generic verify ``res``.

    The authored test is a real verification, so:
      * when the generic verify SKIPPED (``ran=False``) it becomes the verdict
        (a complex geo node the generic harness couldn't drive now gets a real
        pass/fail);
      * when the generic verify RAN, both must pass.
    The aggregate is attached under ``res['authored_test']`` and summarised in
    ``reason`` so the compile report can surface it."""
    res                  = dict(res)
    res["authored_test"] = authored
    # Whether the GENERIC pointwise compare ran, kept apart from the merged
    # `ran` below -- that one becomes True on the authored test alone, and a
    # reader (the optimizer's ledger, the report) has to know which it was.
    res["generic_ran"] = bool(res.get("ran"))
    if authored.get("ran"):
        if res.get("ran"):
            res["pass"] = bool(res.get("pass")) and bool(authored["passed"])
        else:
            res["ran"]  = True
            res["pass"] = bool(authored["passed"])
            if res.get("tol") is None:
                res["tol"] = 0.0
    if not authored["passed"]:
        extra = "authored @maya_test FAILED: %s" % (authored.get("reason") or "")
    else:
        extra = ("authored @maya_test: %d/%d passed"
                 % (authored.get("passes", 0), authored.get("count", 0)))
    prev          = (res.get("reason") or "").strip()
    res["reason"] = (prev + " | " + extra) if prev else extra
    return res


def _attr_components(val):
    """Flatten a ``cmds.getAttr`` return into a flat list of floats so parity
    compares EVERY component. A scalar -> ``[v]``; a double3 (Maya returns
    ``[(x, y, z)]``) -> ``[x, y, z]``; a matrix (flat 16) -> all 16. The old
    code peeled lists down to ``val[0]`` -- comparing only X of a vector and
    only m[0][0] of a matrix -> a port wrong on any other component scored
    maxerr~=0 and falsely "verified".

    A STRING leaf compares as ``[len] + code points``: equal iff identical, and
    the leading length keeps a longer string from hiding behind zip truncation.
    hexAttribute's hex-dump output raised here for a year and its parity read
    "could not run". Raises (caught upstream as a skip) only for a leaf that is
    neither numeric nor text (``None`` from a typed plug getAttr cannot read --
    those are routed to the geometry reader before reaching this)."""
    if isinstance(val, str):
        return _string_components(val)
    if isinstance(val, (list, tuple)):
        out = []
        for e in val:
            out.extend(_attr_components(e))
        return out
    return [float(val)]


def _string_components(s):
    return [float(len(s))] + [float(ord(c)) for c in s]


def _geo_output_components(node, attr, geo_type):
    """Flat components for a DECLARED geometry output (rbfWrap's ``outGeo:mesh``):
    a leading point count, a topology signature, then every point (and normal /
    colour) component -- the same data :func:`_verify_geo` compares for a
    generator, read through the API because ``getAttr`` cannot read typed data.
    An empty / null plug yields ``[0.0]`` so empty-vs-built shows as a mismatch
    rather than as nothing to compare."""
    import maya.api.OpenMaya as om2

    kind = {"mesh": "mesh", "nurbsCurve": "curve"}.get(geo_type, "surface")
    try:
        geo = _read_geo_components(om2, node, kind, {"attr": attr})
    except Exception:
        geo = None
    if not geo:
        return [0.0]
    pts  = geo.get("pts") or []
    topo = geo.get("topo") or ()
    sig  = []
    for part in topo:
        if isinstance(part, (list, tuple)):
            sig.append(float(len(part)))
            sig.append(float(sum(float(x) for x in part
                                 if isinstance(x, (int, float)))))
        elif isinstance(part, (int, float)):
            sig.append(float(part))
    return [float(len(pts) // 3)] + sig + list(pts) + list(geo.get("attrs") or [])


def _components_maxerr(a, b):
    """Max abs difference across paired components (over the shorter length).
    0.0 when either side is empty -- the OUT loop only calls this for declared
    outputs, so empty means nothing to compare, not a pass/fail signal."""
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


# A discrepancy from a genuine PORT bug (wrong sign / index / formula) is bounded
# by the OUTPUT magnitude -- O(scene units) for any real node, well under this
# ceiling. A divergence ABOVE it (or a non-finite result) means the computation
# blew up under randomized inputs: the signature of a STATEFUL / ITERATIVE solver
# (dnet feeds output positions back across evals) sensitive to float-accumulation
# order, for which drive-and-compare parity is not a valid check. Classified as an
# INCONCLUSIVE SKIP. Only ever downgrades FAIL->SKIP, so it can never mask a real
# bug as a PASS.
_DIVERGE_CEIL = 1.0e6

# How far past `tol` a CARRY-STATE drift is still read as drift rather than a
# port bug -- see _carry_state_drift. Deliberately tight: the band exists to
# excuse two correct-but-differently-advanced solver trajectories separating,
# and a systematic port bug is bounded by OUTPUT magnitude, which is orders
# above this. dnet's maxDisplacement sentinel diverged by exactly 1.0 = 1e4 x
# tol, so it stays a FAIL under this rule; its residual carry drift is 1.83 x.
_CARRY_DRIFT_MULT = 10.0


# ---------------------------------------------------------------------------
# Compiled-vs-interpreted TIMING guard
#
# Parity answers "does it compute the same thing", never "at what cost". A
# voxelize port swapped MMeshIntersector (octree) for MFnMesh::getClosestPoint
# with a NULL MMeshIsectAccelParams*: identical answers, deterministic, through
# every gate -- and 714 SECONDS per evaluation where the accelerated form took
# 0.125 s. Nothing here measured speed, so nothing could see it.
#
# The thresholds below are REASONED (from ~8% recorded run-to-run noise, the 15 ms
# bench floor and a ~0.4 ms fixed whole-evaluation cost), NOT calibrated against a
# table of real nodes. So the guard MEASURES AND RECORDS unconditionally but only
# emits a `warning` when MPYNODE_TIMING_WARN is set -- see _timing_warn_enabled.
# ---------------------------------------------------------------------------
def _env_float(name, default):
    """Read a float from the environment, falling back on anything unparseable.
    These are parsed at MODULE scope, so a typo (MPYNODE_TIMING_WARN_RATIO=five)
    would otherwise raise at import and take the whole toolchain package down with
    it -- its __init__ imports this module. The bare `or` idiom covers an empty
    string but not a non-numeric one."""
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return float(default)


_TIMING_WARN_RATIO = _env_float("MPYNODE_TIMING_WARN_RATIO", 5)
_TIMING_LOUD_RATIO = 10.0
_TIMING_BUDGET_S   = _env_float("MPYNODE_TIMING_BUDGET_S", 90)
_TIMING_SAMPLES    = 3


def _timing_enabled():
    """Is the timing pass allowed to run at all? On unless MPYNODE_TIMING says
    otherwise -- recording numbers is cheap next to the parity sweep and the
    global budget (_TIMING_BUDGET_S) bounds the whole bundle."""
    return (os.environ.get("MPYNODE_TIMING", "1") or "1").strip().lower() \
        not in ("0", "off", "false", "no")


def _timing_warn_enabled():
    """May a measurement be turned into a `warning`? OFF by default: the 5.0
    threshold has no calibration table behind it yet, and an unvalidated warning
    on every compile is worse than none. The numbers land in the row regardless."""
    return (os.environ.get("MPYNODE_TIMING_WARN", "") or "").strip().lower() \
        in ("1", "on", "true", "yes")


def _timing_floor_ms():
    """The noise floor, read from the OPTIMIZER's single source of truth rather
    than re-declared here (lazy import keeps this module headless-safe)."""
    try:
        from mpynode.native.ai import optimizer_live as _ol
        return float(_ol._BENCH_FLOOR_MS)
    except Exception:
        return 15.0


def _timing_rungs():
    """The two scene sizes the timing pass may use, ``(geo_density, array_len)``
    each, taken from the optimizer's bench ladder so the sizes have ONE spelling.
    Rung A is the cheap probe; rung B is only reached via the interlock in
    :func:`_run_timing`."""
    try:
        from mpynode.native.ai import optimizer_live as _ol
        return _ol._BENCH_LADDER[0], _ol._BENCH_LADDER[2]
    except Exception:
        return (40, 512), (140, 5000)


def _time_pair(cmds, py_node, cpp_node, pull_py, pull_cpp, perturbs, deadline):
    """Best-of-N wall time for one pull of each side. Returns
    ``{"py_ms", "cpp_ms", "n", "truncated"}`` or None.

    ``perturbs`` are :func:`bench_perturb_fn` closures, one per node. They MUST be
    called OUTSIDE the timed region and once per tick for BOTH nodes -- each keeps
    its own counter, so one tick leaves the two nodes at the SAME value. Without
    them a content-memoizing compute is timed as a cache hit (measured on the
    kd-tree: 0.169 ms static vs 1.785 ms with one query point moved).

    min(), not median: run-to-run noise is one-sided (an interruption only ADDS
    time), so the minimum is the closest estimate of intrinsic cost -- and taking
    it on BOTH sides removes "the compiled sample was unluckily high" as a route
    to a false alarm."""
    if not perturbs or any(p is None for p in perturbs):
        return None
    # UNTIMED warm-up: drops every first-touch cost (accelerator build, MImage
    # load, plugin page-in) that would otherwise land in sample #1.
    for p in perturbs:
        p()
    pull_py()
    pull_cpp()

    py_s, cpp_s = [], []
    truncated = False
    for _ in range(_TIMING_SAMPLES):
        for p in perturbs:
            p()
        # Interleaved, so a machine-wide load spike hits both sides.
        t0 = time.perf_counter()
        pull_py()
        py_s.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        pull_cpp()
        cpp_s.append(time.perf_counter() - t0)
        if deadline is not None and time.perf_counter() > deadline:
            truncated = True
            break
    if not py_s or not cpp_s:
        return None                 # fewer than one COMPLETE pair
    return {"py_ms": min(py_s) * 1000.0, "cpp_ms": min(cpp_s) * 1000.0,
            "n": min(len(py_s), len(cpp_s)), "truncated": truncated}


def _timing_verdict(py_ms, cpp_ms, floor_ms, n, truncated, scene,
                    mesh_query=False, warn=None):
    """Classify one measurement into a named, actionable row (pure -- no Maya).

    Same job as :func:`_staleness_reason`: turn a number into a sentence someone
    can act on. ``mesh_query`` is the spec's ``uses_mesh_intersector`` flag (set by
    spec_extractor._MESH_QUERY_PATTERNS); ``warn`` overrides the env gate."""
    if py_ms is None or cpp_ms is None:
        return {"measured": False,
                "reason": "timing not measured (no complete paired sample)"}
    row = {"measured": True, "py_ms": py_ms, "cpp_ms": cpp_ms, "n": n,
           "truncated": bool(truncated), "scene": scene}
    # THE FLOOR IS ON THE MAX, NOT ON py_ms -- do not "fix" this back. A floor on
    # the interpreted side alone would make the guard PERMANENTLY SILENT on the
    # exact asymptotic defect it exists for: geometry density (the only generic
    # knob) grows the COMPILED side's cost while the interpreted side stays flat,
    # so py_ms would sit under the floor forever no matter how slow the port got.
    if max(py_ms, cpp_ms) < floor_ms:
        row["ratio"]   = (cpp_ms / py_ms) if py_ms > 0 else None
        row["verdict"] = "below-floor"
        return row
    ratio        = (cpp_ms / py_ms) if py_ms > 0 else float("inf")
    row["ratio"] = ratio
    if ratio < _TIMING_WARN_RATIO:
        row["verdict"] = "ok"
        return row
    loud           = ratio >= _TIMING_LOUD_RATIO
    row["verdict"] = "much-slower" if loud else "slower"
    if warn is None:
        warn = _timing_warn_enabled()
    if not warn:
        return row
    if loud:
        msg = ("TIMING: the compiled node measured %.1fx -- ORDERS OF MAGNITUDE "
               "slower than the interpreted Python it replaces (%.1f ms vs %.1f "
               "ms, best of %d, %s); this is almost certainly an algorithmic "
               "regression in the port, not a constant factor."
               % (ratio, cpp_ms, py_ms, n, scene))
    else:
        msg = ("TIMING: the compiled node measured %.1fx SLOWER than the "
               "interpreted Python it replaces (%.1f ms vs %.1f ms, best of %d, "
               "%s). If the Python leans on a vectorised numpy/BLAS/scipy kernel "
               "this can be expected." % (ratio, cpp_ms, py_ms, n, scene))
    if mesh_query:
        msg += (" It uses an ACCELERATED Maya query (MMeshIntersector, "
                "MMeshIsectAccelParams) -- check the port did not lower it to an "
                "unaccelerated linear scan.")
    if truncated:
        msg += (" (measurement cut short by the timing budget; the ratio is a "
                "lower bound)")
    row["warning"] = msg
    return row


def _pair_stats(a, b):
    """Compare paired components tolerating divergence. Returns
    ``(maxerr, n_comparable, n_diverged)``:
      * a pair with BOTH sides non-finite (both implementations blew up) is
        counted in ``n_diverged`` and excluded from ``maxerr`` (not a signal);
      * a pair with EXACTLY ONE side non-finite is a real discrepancy -> +inf;
      * otherwise the abs difference contributes to ``maxerr``."""
    maxerr = 0.0
    n_cmp  = 0
    n_div  = 0
    for x, y in zip(a, b):
        fx, fy = math.isfinite(x), math.isfinite(y)
        if not fx and not fy:
            n_div += 1
            continue
        if fx != fy:
            maxerr = float("inf")
            n_cmp += 1
            continue
        maxerr = max(maxerr, abs(x - y))
        n_cmp += 1
    return maxerr, n_cmp, n_div


def _set_plug(cmds, plug, t, v):
    """setAttr one input plug per type. vector/euler/color are double3 (color's
    usedAsColor float3 accepts a double3 setAttr, verified); quaternion is an
    at='compound' of 4 double children X/Y/Z/W (no parent setAttr, so drive the
    children); matrix is a flat-16 -type "matrix"; everything else is a plain
    scalar. Works on both a plain plug and a multi ELEMENT plug (node.attr[i])."""
    if t in ("vector", "euler", "color"):
        cmds.setAttr(plug, v[0], v[1], v[2], type="double3")
    elif t == "float2":
        # numeric compound-2 (mPyFile's uvCoord = uCoord/vCoord) -> double2 setAttr.
        cmds.setAttr(plug, v[0], v[1], type="double2")
    elif t == "quaternion":
        for ax, ev in zip(("X", "Y", "Z", "W"), v):
            cmds.setAttr(plug + ax, ev)
    elif t == "matrix":
        cmds.setAttr(plug, *[float(x) for x in v], type="matrix")
    else:
        cmds.setAttr(plug, v)


def _rand_matrix16(random):
    """A non-trivial but well-formed row-vector affine matrix (flat-16, row-major):
    random 3x3 upper-left + translate row, last column (indices 3/7/11/15) pinned
    to the affine [0,0,0,1] so Maya accepts it as a matrix."""
    m     = [random.uniform(-1.5, 1.5) for _ in range(16)]
    m[3]  = m[7] = m[11] = 0.0
    m[15] = 1.0
    return m


def _elem_value(t, random, enum_n=2):
    """A random driveable value for ONE plug or multi-element of attr-type t."""
    if t == "float2":
        return [random.uniform(0.0, 1.0) for _ in range(2)]
    if t in ("vector", "euler"):
        return [random.uniform(-2.0, 2.0) for _ in range(3)]
    if t == "color":
        return [random.uniform(0.0, 1.0) for _ in range(3)]
    if t == "quaternion":
        return [random.uniform(-1.0, 1.0) for _ in range(4)]
    if t == "matrix":
        return _rand_matrix16(random)
    if t == "bool":
        return random.choice([0, 1])
    if t == "int":
        return random.randint(-6, 6)
    if t == "enum":
        return random.randint(0, max(0, enum_n - 1))
    if t == "time":
        return float(random.randint(1, 48))
    return random.uniform(-4.0, 4.0)


def _array_values(t, k, random, enum_n=2):
    """K driveable multi-element values for an ARRAY input of type ``t``.

    int arrays are seeded in ``[0, k-1]`` (NOT the wide scalar range): a node that
    uses an int array as INDICES into a parallel array (e.g. dnet's
    ``index0``/``index1`` into ``positions``) would read OUT OF BOUNDS on an
    arbitrary int, and an OOB read in a compiled C++ node HARD-CRASHES the process
    (a segfault is uncatchable in-process). Keeping indices within the seeded
    element count makes array driving crash-safe for the common index-array
    pattern while still exercising real parity."""
    if t == "int":
        return [random.randint(0, max(0, k - 1)) for _ in range(k)]
    return [_elem_value(t, random, enum_n) for _ in range(k)]


# TYPED geo inputs -- driveable by WIRING a real upstream shape into the plug. The
# same source feeds both nodes, so both read identical geometry: a NON-vacuous
# probe for a geo-consuming node that used to be left at default (vacuous PASS).
# One that can't be wired on BOTH sides (a codegen gap) is peeled and annotated.
_GEO_IN_TYPES = frozenset(("nurbsCurve", "mesh", "nurbsSurface"))

# INPUT types the harness cannot synthesize a coherent value for: ``string``/
# ``hex`` carry no numeric sample, so they are LEFT AT THEIR DEFAULT on both nodes
# (identical, if unexercised) rather than setAttr'd with a float. The compared==0
# vacuous guard downstream turns a genuinely-needed unwired input into an honest
# skip instead of a false PASS.
_NON_DRIVEABLE_IN = frozenset(("string", "hex"))

# Output geometry plug per typed geo input kind (the connection SOURCE the wiring
# helper reads off a freshly-built upstream shape).
_GEO_SRC_PLUG = {
    "mesh":         ".worldMesh[0]",
    "nurbsCurve":   ".worldSpace[0]",
    "nurbsSurface": ".worldSpace[0]",
}


def _make_upstream_shape(cmds, geo_type, cfg, density=None):
    """Build a deterministic upstream shape for a typed geo input and return its
    output-geometry plug (``worldMesh`` / ``worldSpace``). ``cfg`` varies the
    resolution so a multi-element / multi-config wiring exercises distinct
    topology rather than one repeated shape.

    ``density`` (BENCHMARK use only) requests a DENSE shape instead of the tiny
    parity one. Parity only needs a few verts to compare values; a benchmark
    needs enough geometry for the compute to dominate the tick. Left None the
    shapes are byte-identical to before, so the parity path is unaffected."""
    if geo_type == "mesh":
        if density:
            tr = cmds.polySphere(sx=int(density), sy=int(density), ch=False)[0]
        else:
            sx = 1 + (cfg % 3)
            tr = cmds.polyCube(sx=sx, sy=sx, sz=sx, ch=False)[0]
    elif geo_type == "nurbsCurve":
        tr = cmds.circle(ch=False, s=(int(density) if density else 6 + (cfg % 4)))[0]
    else:  # nurbsSurface
        # cfg-varying like the mesh and curve branches above. Held at a constant 4
        # this built five IDENTICAL spheres across the sweep, so a nurbsSurface
        # consumer got no topology variation at all. `% 3` against _GEO_CFGS = 5
        # keeps the A->B->C->A revisit the sweep relies on, and cfg 0 still yields
        # 4 -- so the scalar parity path, which always passes cfg 0, is unchanged.
        n  = int(density) if density else 4 + (cfg % 3)
        tr = cmds.sphere(ch=False, sections=n, spans=n)[0]
    shp = cmds.listRelatives(tr, s=True, f=True)[0]
    return shp + _GEO_SRC_PLUG[geo_type]


def _wire_geo_input(cmds, nodes, attr, geo_type, is_array, cfg, density=None,
                    rewire=False):
    """Connect a real upstream shape into a typed geo INPUT plug on EVERY node in
    ``nodes`` (the SAME source per element -> identical geometry on the Python and
    compiled sides). Idempotent: a plug already connected is left alone and no
    orphan shape is created for it. Returns ``True`` only if every needed plug got
    wired; ``False`` (caller peels + annotates) when a plug is missing on a side or
    a connect raises -- the signature of a geo-input codegen gap.

    ``rewire=True`` drops the already-connected skip so the caller can REPLACE the
    upstream shape (a fresh one for this ``cfg`` / ``density``). Default False, so
    every pre-existing caller keeps the idempotent behaviour byte-for-byte."""
    n_elems = 3 if is_array else 1
    ok      = True
    for i in range(n_elems):
        need = []
        for nd in nodes:
            dst = ("%s.%s[%d]" % (nd, attr, i)) if is_array else ("%s.%s" % (nd, attr))
            try:
                if not cmds.objExists(dst):
                    ok = False
                    continue
                if not rewire and cmds.listConnections(dst, s=True, d=False):
                    continue  # already wired (both sides share it or a prior cfg)
                need.append(dst)
            except Exception:
                ok = False
        if not need:
            continue
        try:
            src = _make_upstream_shape(cmds, geo_type, cfg + i, density=density)
        except Exception:
            ok = False
            continue
        for dst in need:
            try:
                cmds.connectAttr(src, dst, force=True)
            except Exception:
                ok = False
    return ok


_PACKED_SEED_CAST = {"doubleArray": float, "Int32Array": int}


def _packed_dt(cmds, node, attr):
    """dataType of a PACKED (typed-array) input plug, else None for a multi.

    Detected from the LIVE plug rather than the spec because the seeder drives
    the interpreted and the compiled node through this one path and a scene
    saved before packed storage still carries a numeric multi. A packed plug has
    NO element plugs, so a per-element ``attr[i]`` setAttr raises -- and a raise
    inside the harness reports as a not-run SKIP, i.e. the node would ship green
    with parity never actually checked."""
    try:
        if cmds.attributeQuery(attr, node=node, multi=True):
            return None
        dt = cmds.getAttr("%s.%s" % (node, attr), type=True)
    except Exception:
        return None
    return dt if dt in _PACKED_SEED_CAST else None


def _seed_packed(cmds, plug, dt, values):
    """Write a whole packed table in ONE setAttr. True if it was written."""
    cast = _PACKED_SEED_CAST[dt]
    try:
        cmds.setAttr(plug, [cast(v) for v in values], type=dt)
        return True
    except Exception:
        return False


_RANGED_TYPES = frozenset(("double", "float", "int", "long", "short", "angle"))


def _clamp_drive(cmds, nodes, attr, t, v):
    """Clamp a random scalar drive into the attribute's declared [min, max].

    A preset attribute can carry a range (mPyFile's ``preFilterRadius`` has
    min 0) and ``setAttr`` REFUSES a value outside it -- which, raised from the
    drive loop, read as "verify could not run" for every texture node. The range
    is read off the FIRST node that declares one and the SAME clamped value goes
    to every node, so the two sides still see identical inputs. Types without a
    scalar range (compounds, matrices, strings) and attrs without limits pass
    through unchanged."""
    if t not in _RANGED_TYPES or not isinstance(v, (int, float)):
        return v
    lo = hi = None
    for nd in nodes:
        try:
            if cmds.attributeQuery(attr, node=nd, minExists=True):
                lo = cmds.attributeQuery(attr, node=nd, minimum=True)[0]
            if cmds.attributeQuery(attr, node=nd, maxExists=True):
                hi = cmds.attributeQuery(attr, node=nd, maximum=True)[0]
        except Exception:
            continue
        if lo is not None or hi is not None:
            break
    if lo is not None and v < lo:
        v = lo
    if hi is not None and v > hi:
        v = hi
    return v


def _drive_array_input(cmds, nodes, attr, t, values):
    """setAttr the multi ELEMENT plugs attr[0..K-1] to ``values`` on every node.
    A connected multi is left to its source (identical on both sides). A packed
    (typed-array) input has no element plugs and is written whole instead."""
    for nd in nodes:
        base = nd + "." + attr
        try:
            if cmds.listConnections(base, s=True, d=False):
                continue
        except Exception:
            pass
        dt = _packed_dt(cmds, nd, attr)
        if dt:
            _seed_packed(cmds, base, dt, values)
            continue
        for i, ev in enumerate(values):
            _set_plug(cmds, "%s[%d]" % (base, i), t,
                      _clamp_drive(cmds, nodes, attr, t, ev))


def _read_array_output(cmds, node, attr):
    """(flat component list, element count) for a multi OUTPUT plug. Pulls the
    plug first (dgeval) so the compute populates its elements, then reads every
    written logical index and flattens all components (so a wrong Y/Z/matrix
    element can't hide)."""
    plug = node + "." + attr
    try:
        cmds.dgeval(plug)
    except Exception:
        pass
    try:
        idxs = cmds.getAttr(plug, multiIndices=True) or []
    except Exception:
        idxs = []
    comps = []
    for i in idxs:
        try:
            comps.extend(_attr_components(cmds.getAttr("%s[%d]" % (plug, i))))
        except Exception:
            pass
    return comps, len(idxs)


def _native_family_outputs(spec):
    """Outputs a family writes through NATIVE plugs rather than declared ones.

    An mPyTransform's compute sets ``self.local_matrix`` and the result leaves
    through the transform's own ``matrix`` plug; with no declared outputs the
    scalar path called that "no scalar outputs to compare" and aimTransform was
    never checked. The plug exists on both the interpreted reference (built as
    an mPyTransform) and the compiled MPxTransform, so it is compared like any
    declared matrix output. Marked ``native`` so the reference builder does not
    try to add it."""
    if (spec.get("mpy_type") or "") == "mPyTransform":
        return {"matrix": {"type": "matrix", "native": True}}
    return {}


def _side_effect_gated_enums(spec):
    """Enum inputs whose value is handed to a blessed ``NativeSideEffect``
    method -- ``mode = int(self.skinMode)`` ... ``self.sync_paint(mode)``.

    Such a method is interactive-only and lowers to NOTHING in the compiled
    node; on the interpreted node it does its job (twistSwingSkin's sync_paint
    loads a weight set INTO weightList on a paint-mode switch). Randomising the
    selector therefore makes the two nodes legitimately differ (FAIL 1.18 on a
    node that matches at 0.0 in Live mode), so the generic drive holds such an
    enum at its DEFAULT and says so. Detection is textual: the enum's plug is
    either an argument of the call or assigned to a name that is."""
    import re as _re
    compute = spec.get("compute") or ""
    enums = [nm for nm, m in (spec.get("inputs") or {}).items()
             if isinstance(m, dict) and m.get("type") == "enum"]
    if not enums or "self." not in compute:
        return frozenset()
    try:
        from mpynode.native.compiler.kernels.blessed_transpile import (
            side_effect_method_names)
        methods = side_effect_method_names(spec)
    except Exception:
        methods = frozenset()
    if not methods:
        return frozenset()
    # every argument identifier of every side-effect call
    args = set()
    for m in methods:
        for call in _re.finditer(r"self\.%s\s*\(([^)]*)\)" % _re.escape(m), compute):
            args.update(_re.findall(r"[A-Za-z_][A-Za-z_0-9.]*", call.group(1)))
    held = set()
    for nm in enums:
        plug = "self." + nm
        if plug in args:
            held.add(nm)
            continue
        # `mode = int(self.skinMode)` and `mode` is an argument
        for am in _re.finditer(r"^\s*([A-Za-z_]\w*)\s*=\s*[^\n=]*\bself\.%s\b"
                               % _re.escape(nm), compute, _re.M):
            if am.group(1) in args:
                held.add(nm)
                break
    return frozenset(held)


def _enum_default(meta, names):
    """The declared default of an enum input as an index (0 when unknown)."""
    dv = (meta or {}).get("default_value")
    if isinstance(dv, bool):
        return int(dv)
    if isinstance(dv, (int, float)):
        return int(dv)
    if isinstance(dv, str) and names and dv in names:
        return list(names).index(dv)
    return 0


def _held_enum_note(held, reason=""):
    if not held:
        return reason
    note = ("enum(s) held at default because they select an interpreted-only "
            "side effect: %s" % ", ".join(sorted(held)))
    return (reason + " -- " + note) if reason else note


def _skin_rig(cmds, tag):
    """Two identical rest meshes (a cylinder "arm") sharing ONE 3-joint chain,
    plus the smooth-bind weights and bind matrices a native skinCluster gives
    that arm -- captured, then the native cluster is unbound so both meshes sit
    at rest for the custom skin nodes. Mirrors
    tools/harness/skin_twist_swing_dual_parity.build_and_capture, which proved
    the twist/swing node on a real arm; this is the generic, asset-free arm.

    Returns ``(mesh_a, mesh_b, joints, elbow, bind, weights)`` where ``bind`` is
    one flat-16 matrix per joint and ``weights`` is ``nv x len(joints)``."""
    xf = cmds.polyCylinder(r=0.5, h=6.0, sx=8, sy=6, sz=1, ch=False,
                           name="skinA_" + tag)[0]
    cmds.select(clear=True)
    j0     = cmds.joint(p=(0.0, -3.0, 0.0), name="j0_" + tag)
    j1     = cmds.joint(p=(0.0, 0.0, 0.0),  name="j1_" + tag)
    j2     = cmds.joint(p=(0.0, 3.0, 0.0),  name="j2_" + tag)
    joints = [j0, j1, j2]
    sc = cmds.skinCluster(joints + [xf], toSelectedBones=True,
                          maximumInfluences=2, obeyMaxInfluences=True)[0]
    infl    = list(cmds.skinCluster(sc, q=True, influence=True) or [])
    order   = [infl.index(j) for j in joints]
    nv      = cmds.polyEvaluate(xf, vertex=True)
    weights = []
    for vtx in range(nv):
        w = cmds.skinPercent(sc, "%s.vtx[%d]" % (xf, vtx), q=True, value=True)
        weights.append([float(w[order[i]]) for i in range(len(joints))])
    bind = [list(cmds.getAttr("%s.bindPreMatrix[%d]" % (sc, infl.index(j))))
            for j in joints]
    cmds.skinCluster(sc, e=True, unbind=True)      # both meshes: exact rest
    xb = cmds.duplicate(xf, name="skinB_" + tag)[0]
    return xf, xb, joints, j1, bind, weights


def _bind_skin_node(cmds, node, joints, bind, weights):
    """Wire the shared joints into a custom skin node and paint the stock
    weights on it -- identical on the interpreted and the compiled node."""
    for i, jnt in enumerate(joints):
        cmds.connectAttr(jnt + ".worldMatrix[0]", "%s.matrix[%d]" % (node, i),
                         force=True)
        cmds.setAttr("%s.bindPreMatrix[%d]" % (node, i),
                     *[float(x) for x in bind[i]], type="matrix")
    for vtx, row in enumerate(weights):
        for j, wv in enumerate(row):
            if wv:
                cmds.setAttr("%s.weightList[%d].weights[%d]" % (node, vtx, j),
                             float(wv))


def _pose_skin_rig(cmds, elbow, random):
    """Bend the elbow: a pose both skins see through the shared joints."""
    cmds.setAttr(elbow + ".rotate", random.uniform(-60.0, 60.0),
                 random.uniform(-30.0, 30.0), random.uniform(-45.0, 45.0),
                 type="double3")


def _skin_weight_values(weights, roll=0):
    """A declared per-vertex-per-joint weight array (twistWeights /
    swingWeights) sized N*J from the stock weights: the stock set as-is, or
    rolled one influence over and renormalised so a second set differs."""
    J   = len(weights[0]) if weights else 0
    out = []
    for row in weights:
        r = list(row[-roll % J:]) + list(row[:-roll % J]) if roll and J else list(row)
        s = sum(r)
        out.extend(float(x / s) if s > 1e-9 else float(x) for x in r)
    return out


def _unregistered_type(cmds, node, type_name, tol):
    """A skip row when ``createNode(type_name)`` did not make a ``type_name``.

    Maya makes an ``unknown`` node for a type no loaded plug-in registers, and
    the drive then dies on "No object matches name: unknown1.brightness" --
    reported as a harness failure of the NODE. It is a bundle problem: say so."""
    try:
        actual = cmds.nodeType(node)
    except Exception:
        actual = None
    if actual == type_name:
        return None
    return {"ran": False, "pass": None, "maxerr": None, "tol": tol,
            "reason": "the loaded bundle does not register node type '%s' "
                      "(createNode made %s) -- nothing to compare against"
                      % (type_name, "an '%s' node" % actual if actual else
                         "nothing")}


def _read_outputs(cmds, node, out_meta):
    """Read EVERY declared output off one node -> ``{attr: (components, count)}``
    (``count`` is None for a non-array plug). The READ half of the scalar parity
    compare, so the timing pull and the parity compare force exactly the same
    evaluation."""
    out = {}
    for o, m in out_meta.items():
        if m.get("type") in _GEO_IN_TYPES and not m.get("is_array"):
            # A declared geometry output. getAttr prints "The data is not a
            # numeric or string value" and returns None -- rbfWrap's parity died
            # on float(None) -- so read it through the API like a generator's.
            out[o] = (_geo_output_components(node, o, m.get("type")), None)
        elif m.get("is_array"):
            out[o] = _read_array_output(cmds, node, o)
        else:
            # ALL components (see _attr_components): comparing only [0] silently
            # passed a vector wrong on Y/Z or a transposed matrix.
            out[o] = (_attr_components(cmds.getAttr(node + "." + o)), None)
    return out


def _apply_drive(cmds, nodes, drive):
    """Set one recorded input set onto both nodes.

    ``drive`` is ``{attr: (type, is_array, value)}`` -- captured once so the SAME
    inputs can be re-presented later (see :func:`_staleness_reason`).
    """
    for attr, (t, is_array, value) in drive.items():
        if is_array:
            _drive_array_input(cmds, nodes, attr, t, value)
        else:
            _drive_input(cmds, nodes, attr, t, value)


def _staleness_reason(maxerr, replay_err, tol):
    """Did the node only diverge when an EARLIER input set came back?

    The parity loop drives 30 fresh random input sets, so a compiled node that
    never invalidates a cache is already caught -- its output stops tracking the
    interpreted one immediately. What that loop cannot see is a cache keyed on
    the WRONG thing: correct while inputs keep changing, wrong the moment a
    previously-seen state is presented again. Randomized draws essentially never
    revisit an exact prior state, so the loop is blind to it by construction.

    Re-presenting input set #1 at the end closes that gap for one extra
    evaluation. A divergence that appears ONLY on the replay is a specific,
    nameable defect (stale or mis-keyed cached state), not a generic parity
    failure, and saying so is the difference between an actionable report and
    "it did not match".

    NOTE the reference is the interpreted node at every step -- deliberately NOT
    "the replay must equal the first reading". A node with persistent state is
    SUPPOSED to answer differently the second time it sees the same input, and
    an equality rule would condemn it for working correctly.
    """
    if replay_err is None or not math.isfinite(replay_err):
        return None
    if replay_err <= tol:
        return None
    if maxerr > tol:
        return None                 # already failing; nothing extra to say
    return ("output diverged (%.3g > tol %.3g) only when an EARLIER input set "
            "was presented again, after matching across 30 fresh input sets -- "
            "the signature of state cached across evaluations that is stale or "
            "keyed on the wrong input" % (replay_err, tol))


def _drive_input(cmds, nodes, attr, t, v):
    """Set input ``attr = v`` on every node in ``nodes``, ROBUST to CONNECTED
    plugs -- so a node with connected (e.g. texture / time) inputs is verified
    instead of aborting the whole parity check.

    A connected plug can't be ``setAttr``'d (Maya raises), so it is left to its
    incoming source, which is identical on both the Python and compiled node. A
    ``time`` input is special: on a Python mPyNode ``time`` is auto-connected to
    ``time1`` but on the compiled node it is a plain, UNCONNECTED plug, so we
    drive the shared timeline (``currentTime``) AND ``setAttr`` the value onto any
    unconnected time plug -- driving BOTH sides to the same frame."""
    if t == "time":
        try:
            cmds.currentTime(v)
        except Exception:
            pass
    v = _clamp_drive(cmds, nodes, attr, t, v)
    for nd in nodes:
        plug = nd + "." + attr
        try:
            if cmds.listConnections(plug, s=True, d=False):
                continue  # connected: value comes from the source (both sides)
        except Exception:
            pass
        _set_plug(cmds, plug, t, v)


# =====================================================================
# BENCHMARK scene seeding (shared with tools/harness/benchmark_node.py)
#
# The AI optimizer only accepts a candidate that benchmarks measurably faster, so
# a node whose inputs are never driven benchmarks an EMPTY compute and nothing can
# ever be accepted. The type knowledge lives HERE next to _elem_value/_set_plug/
# _wire_geo_input rather than being duplicated into the harness.
#
# EVERY supported input and output type is driven/pulled, single AND array. Only
# `python` and `message` are out of scope (no scene-side value).
# =====================================================================

# No driveable scene value: a python attr is a live object, a message plug a pure
# connection. Everything else -- including string/hex, which PARITY leaves alone
# -- is seeded here.
_BENCH_SKIP_TYPES = frozenset(("python", "message"))


def _bench_string_value(t, attr):
    """A harmless text value for a string-backed input (string / hex).

    Parity leaves these at default (it cannot synthesize a value comparable on
    both sides), but a BENCHMARK only needs the node to do its normal work, and
    a node that branches on a string would otherwise take a different path than
    it does in production. Anything that looks like a path is left alone -- a
    bogus filename makes a file node do MORE (and different) work, not less."""
    low = (attr or "").lower()
    if any(k in low for k in ("file", "path", "dir", "folder", "image", "tex")):
        return None
    return "bench" if t != "hex" else "0"


# ---------------------------------------------------------------------------
# Fixtures for file-reading nodes, and the representative scenes
# ---------------------------------------------------------------------------
# A node that reads a file used to be driven with an EMPTY path on both sides
# ("honest for the geometry, the file branch never exercised") or skipped
# outright ("reads an image file"). Both sides can read the SAME generated
# file instead: a band-limited gradient PNG for a texture, a cube sequence for
# a JSON mesh reader, an .ndio cache for a disk cache. Generated, never shipped:
# the harness owns no asset and depends on no repo layout.

# The image harness (tools/harness/mpyfile_image_parity.py) gates DG-vs-DG
# texture parity at this: the compiled node decodes through MImage, the
# interpreted one through the runtime's reader, and the two differ by a
# rounding step, never more.
_TEXTURE_TOL = 1.5 / 255.0

_FIXTURE_FRAMES = 48          # the geo drive samples `time` in [1, 48]


def _write_png_rgb(path, w, h, pixel):
    """Write an 8-bit RGB PNG with ``pixel(u, v) -> (r, g, b)`` in 0..1.
    Pure Python (zlib + struct): mayapy ships no PIL."""
    import struct
    import zlib

    raw = bytearray()
    for y in range(h):
        raw.append(0)                           # filter: none
        vv = 1.0 - (y / (h - 1.0) if h > 1 else 0.0)
        for x in range(w):
            uu = x / (w - 1.0) if w > 1 else 0.0
            r, g, b = pixel(uu, vv)
            raw += bytes(max(0, min(255, int(round(c * 255.0)))) for c in (r, g, b))

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xffffffff))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return path


def _gradient_png(path, phase=0.0, n=64):
    """A smooth sin gradient -- no frequency a uv sample cannot resolve -- with
    a phase so several layers differ from each other."""
    import math

    def pixel(u, vv):
        return (0.5 + 0.5 * math.sin(2.0 * math.pi * u + phase),
                0.5 + 0.5 * math.sin(2.0 * math.pi * vv + phase),
                0.5 + 0.5 * math.sin(math.pi * (u + vv) + phase))
    return _write_png_rgb(path, n, n, pixel)


_CUBE_COUNTS = [4, 4, 4, 4, 4, 4]
_CUBE_INDICES = [0, 3, 2, 1, 4, 5, 6, 7, 0, 1, 5, 4, 3, 7, 6, 2, 0, 4, 7, 3,
                 1, 2, 6, 5]


def _cube_points(scale):
    return [[sx * scale, sy * scale, sz * scale]
            for sz in (-0.5, 0.5) for sy in (-0.5, 0.5) for sx in (-0.5, 0.5)]


def _json_mesh_sequence(dirpath, frames=_FIXTURE_FRAMES):
    """``mesh.####.json`` cubes, one per frame, growing with the frame -- the
    shape the shipped JSON Mesh Reader fixtures use (points/counts/indices).
    Returns the ``####`` template ``ndio.frame_path`` expands."""
    import json as _json

    for f in range(1, frames + 1):
        doc = {"points": _cube_points(1.0 + 0.05 * f),
               "counts": _CUBE_COUNTS, "indices": _CUBE_INDICES}
        with open(os.path.join(dirpath, "mesh.%04d.json" % f), "w") as fh:
            _json.dump(doc, fh)
    return os.path.join(dirpath, "mesh.####.json")


def _ndio_mesh_cache(path, frames=2):
    """An ``.ndio`` container with ``points`` (frames, 8, 3), ``counts`` and
    ``indices`` -- what a disk mesh cache reads (``ndio.read(path, "points")``
    indexed by frame)."""
    import numpy as np
    from mpynode import ndio

    pts = np.array([_cube_points(1.0 + 0.5 * f) for f in range(frames)],
                   dtype=np.float64)
    ok = ndio.write(path, points=pts,
                    counts=np.array(_CUBE_COUNTS, dtype=np.int64),
                    indices=np.array(_CUBE_INDICES, dtype=np.int64))
    return path if ok else None


_OUTPUT_PATH_TOKENS = frozenset(("bake", "out", "output", "write", "export",
                                 "save", "dest", "cache_out"))


def _is_output_path_name(name):
    """A string input the node WRITES to (gameOfLifeTex's ``bakePath``) must not
    be handed an image to read -- the node would overwrite the fixture."""
    return any(t in _OUTPUT_PATH_TOKENS for t in _name_tokens(name))


def parity_fixtures(spec, k=4, dirpath=None):
    """``{string input: value}`` for every string input the harness can back
    with a generated file, or ``{}``.

    * an mPyFile's string inputs are image paths: one gradient PNG each, an
      array gets ``k`` of them with distinct phases (a composite's layers);
    * elsewhere the compute says what it reads: ``frame_path(`` / ``.json`` ->
      a JSON cube sequence template, ``ndio.read(`` -> an ``.ndio`` cache.

    Anything else stays as before (left at its default, recorded as peeled).
    """
    import tempfile

    inputs = spec.get("inputs") or {}
    strings = [(nm, bool(m.get("is_array"))) for nm, m in sorted(inputs.items())
               if isinstance(m, dict) and m.get("type") in _NON_DRIVEABLE_IN
               and not _is_output_path_name(nm)]
    if not strings:
        return {}
    compute    = spec.get("compute") or ""
    is_texture = (spec.get("mpy_type") or "") == "mPyFile"
    reads_json = "frame_path(" in compute or ".json" in compute
    reads_ndio = "ndio.read(" in compute
    if not (is_texture or reads_json or reads_ndio):
        return {}
    dirpath = dirpath or tempfile.mkdtemp(prefix="mpynode-parity-fixtures-")
    out     = {}
    for nm, is_arr in strings:
        try:
            if is_texture:
                if is_arr:
                    out[nm] = [_gradient_png(os.path.join(dirpath, "%s_%d.png" % (nm, i)),
                                             phase=0.7 * i) for i in range(k)]
                else:
                    out[nm] = _gradient_png(os.path.join(dirpath, nm + ".png"))
            elif reads_ndio:
                p = _ndio_mesh_cache(os.path.join(dirpath, nm + ".ndio"))
                if p:
                    out[nm] = p
            elif reads_json:
                sub = os.path.join(dirpath, nm)
                os.makedirs(sub, exist_ok=True)
                out[nm] = _json_mesh_sequence(sub)
        except Exception:
            continue
    return out


def apply_fixtures(cmds, nodes, fixtures):
    """setAttr every fixture path onto every node; arrays element by element.
    Never raises: a plug that refuses is left at its default on both sides."""
    for nm, val in (fixtures or {}).items():
        for nd in nodes:
            try:
                if isinstance(val, (list, tuple)):
                    for i, p in enumerate(val):
                        cmds.setAttr("%s.%s[%d]" % (nd, nm, i), p, type="string")
                else:
                    cmds.setAttr("%s.%s" % (nd, nm), val, type="string")
            except Exception:
                pass


def _identity_matrix(tx=0.0, ty=0.0, tz=0.0, sx=1.0, sy=1.0, sz=1.0):
    # row-major 4x4 as Maya's setAttr(...,type="matrix") expects (translate in
    # the last row) -- mirrors metaballs_parity._mat so the scene is comparable.
    return [sx, 0.0, 0.0, 0.0,
            0.0, sy, 0.0, 0.0,
            0.0, 0.0, sz, 0.0,
            tx, ty, tz, 1.0]


def _metaclay_scene(res):
    """A representative metaClay/metaballs workload: cube + smooth sphere -
    cylinder (all three CSG ops), matching the proven csg_all parity scene, at a
    caller-chosen grid resolution. Shared by the benchmark (heavy enough to
    time) and by geo parity (a random shape set yields an EMPTY isosurface, so
    parity never ran on metaballs)."""
    mats = [_identity_matrix(0, 0, 0),
            _identity_matrix(0.6, 0.3, 0),
            _identity_matrix(0, 0, 0)]
    stype  = [1, 0, 2]  # box, sphere, cylinder
    add    = [1, 1, 0]  # union, union, subtract
    smooth = [0.0, 0.4, 0.0]
    rad    = [1.0, 0.7, 0.4]
    hgt    = [1.0, 1.0, 2.4]
    ax     = [1, 1, 0]
    half   = [[0.8, 0.8, 0.8], [0.5, 0.5, 0.5], [0.5, 0.5, 0.5]]
    ops    = []
    for i, m in enumerate(mats):
        ops.append({"plug": "shapeMatrix[%d]" % i, "kind": "matrix", "value": m})
    for i in range(len(stype)):
        ops.append({"plug": "shapeType[%d]" % i, "value": stype[i]})
        ops.append({"plug": "additive[%d]" % i, "value": add[i]})
        ops.append({"plug": "smoothing[%d]" % i, "value": smooth[i]})
        ops.append({"plug": "radius[%d]" % i, "value": rad[i]})
        ops.append({"plug": "height[%d]" % i, "value": hgt[i]})
        ops.append({"plug": "axis[%d]" % i, "value": ax[i]})
        ops.append({"plug": "halfExtents[%d]" % i, "kind": "double3",
                    "value": half[i]})
    ops.append({"plug": "resolution", "value": int(res)})
    ops.append({"plug": "isoValue", "value": 0.1})
    return ops


def _voxelize_scene(res):
    """A representative voxelizer workload on the seeded bench sphere (radius
    1): a cell size of ``1/res`` puts ``2*res`` cells across the sphere, and the
    brake sits far above any count this scene can reach. Without this the
    generic seeder hands the node a random cell size and a random ``maxVoxels``
    (it drew 0.002 and 2), the brake fires on every tick, the output is empty
    and the node is recorded as unmeasurable. The brake is a large number rather
    than 0 (off) because the per-tick perturbation nudges every scalar input,
    and a nudge off 0 lands on a cap of one or two voxels -- the same empty
    output by another route."""
    return [
        {"plug": "voxelSize", "value": 1.0 / float(max(4, int(res))), "hold": True},
        {"plug": "maxVoxels", "value": 50000000, "hold": True},
    ]


# Representative scenes, keyed by the TEMPLATE type name a compiled type name
# starts with (metaballs -> metaballsSw); see builtin_scene_key.
BUILTIN_SCENES = {
    "metaClay":     _metaclay_scene,
    "metaballs":    _metaclay_scene,
    "voxelizeMesh": _voxelize_scene,
}


def builtin_scene_key(node_type, table=None):
    """Exact match first, then the LONGEST key ``node_type`` starts with."""
    table = BUILTIN_SCENES if table is None else table
    if node_type in table:
        return node_type
    low   = (node_type or "").lower()
    cands = [k for k in table if low.startswith(k.lower())]
    return max(cands, key=len) if cands else None


def builtin_scene_ops(node_type, res):
    key = builtin_scene_key(node_type)
    return BUILTIN_SCENES[key](res) if key else None


def scene_hold(ops):
    """The inputs a representative scene marks ``"hold": True``: its own
    settings (a cell size, a brake) that the per-tick perturbation must leave
    alone, because moving them rewrites the workload instead of animating it.
    Returns the base attribute names, multi index stripped."""
    out = set()
    for op in ops or []:
        if op.get("hold"):
            out.add(str(op.get("plug", "")).partition("[")[0])
    return frozenset(out)


def apply_scene_ops(cmds, node, ops):
    """Apply a scene's setAttr ops (``{"plug", "value", "kind"}``) to ``node``."""
    for op in ops or []:
        plug = "%s.%s" % (node, op["plug"])
        kind = op.get("kind", "scalar")
        val  = op["value"]
        if kind == "matrix":
            cmds.setAttr(plug, *[float(x) for x in val], type="matrix")
        elif kind == "double3":
            cmds.setAttr(plug, float(val[0]), float(val[1]), float(val[2]),
                         type="double3")
        else:
            cmds.setAttr(plug, val)


# Output array kinds a benchmark can give a consumer to, and the stock node
# whose multi input accepts them. double3-like outputs (a vector, a point, a
# colour, an euler triple) fan into plusMinusAverage.input3D; scalars into its
# input1D; matrices into multMatrix.matrixIn. Anything else is left unsized.
_OUTPUT_SINKS = {
    "plusMinusAverage.input3D": ("vector", "point", "color", "euler", "double3",
                                 "float3"),
    "plusMinusAverage.input1D": ("double", "float", "int", "long", "short",
                                 "angle", "bool"),
    "multMatrix.matrixIn": ("matrix",),
}


def _sink_for(out_type):
    for sink, kinds in _OUTPUT_SINKS.items():
        if out_type in kinds:
            return sink
    return None


def bench_size_output_multis(cmds, node, spec, k):
    """Give every array OUTPUT of ``node`` ``k`` consumers, so the compute has
    ``k`` elements to write.

    The runtime sizes an output array from its live plug elements
    (``len(self.samples)`` is ``numElements()``), and an element only persists
    while something is connected to it. The benchmark pulls ``attr[0]``, so
    spline computed ONE sample on 20 000 CVs and its "13571x" was the ratio of
    two one-sample programs (measured 2026-09-08: 8 sinks -> 8 distinct samples;
    10 000 connections cost 1.1 s once). One stock sink node per output, typed
    by :data:`_OUTPUT_SINKS`; the sink is never pulled, so the timed tick pays
    only for the node's own compute.

    Returns ``{"sized": [(attr, n, sink)], "skipped": [(attr, type, why)]}``.
    Never raises: a plug that will not connect is recorded and left.
    """
    out = {"sized": [], "skipped": []}
    k   = max(0, int(k))
    for attr, meta in sorted((spec.get("outputs") or {}).items()):
        if not isinstance(meta, dict) or not meta.get("is_array"):
            continue
        t    = meta.get("type")
        sink = _sink_for(t)
        if sink is None:
            out["skipped"].append((attr, t, "no stock sink for this type"))
            continue
        sink_type, sink_attr = sink.split(".")
        try:
            sink_node = cmds.createNode(sink_type)
        except Exception as exc:
            out["skipped"].append((attr, t, str(exc)[:80]))
            continue
        n = 0
        for i in range(k):
            try:
                cmds.connectAttr("%s.%s[%d]" % (node, attr, i),
                                 "%s.%s[%d]" % (sink_node, sink_attr, i))
                n += 1
            except Exception as exc:
                out["skipped"].append((attr, t, "stopped at %d: %s"
                                       % (i, str(exc)[:60])))
                break
        if n:
            out["sized"].append((attr, n, sink))
    return out


def seed_bench_scene(cmds, node, spec, *, k_array=512, geo_density=40,
                     rand=None):
    """Drive EVERY supported input of ``node`` at benchmark scale.

    Returns ``{"driven": [...], "skipped": [(attr, type, why)], "arrays": n}``
    so a caller can prove the workload was non-vacuous instead of assuming it.
    Never raises: a plug that refuses a value is recorded and skipped, because a
    partially-seeded benchmark is still a valid RELATIVE measurement (baseline
    and candidate see the identical scene) while an exception is not.
    """
    import random as _random
    rand    = rand or _random.Random(20260808)
    enum_of = {}
    for nm, m in (spec.get("inputs") or {}).items():
        if isinstance(m, dict) and m.get("enum_names"):
            enum_of[nm] = list(m["enum_names"])

    report = {"driven": [], "skipped": [], "arrays": 0, "outputs": []}
    for attr, meta in sorted((spec.get("inputs") or {}).items()):
        if not isinstance(meta, dict):
            continue
        t      = meta.get("type")
        is_arr = bool(meta.get("is_array"))
        if t in _BENCH_SKIP_TYPES:
            report["skipped"].append((attr, t, "no scene-side value"))
            continue
        try:
            if t in _GEO_IN_TYPES:
                ok = _wire_geo_input(cmds, (node,), attr, t, is_arr, 0,
                                     density=geo_density)
                (report["driven"] if ok else report["skipped"]).append(
                    (attr, t, "geo") if ok else (attr, t, "geo wire failed"))
                if is_arr:
                    report["arrays"] += 1
                continue
            if t in ("string", "hex"):
                v = _bench_string_value(t, attr)
                if v is None:
                    report["skipped"].append((attr, t, "path-like; left default"))
                    continue
                tgt = ("%s.%s[0]" % (node, attr)) if is_arr \
                    else ("%s.%s" % (node, attr))
                cmds.setAttr(tgt, v, type="string")
                report["driven"].append((attr, t, "string"))
                continue
            n_enum = len(enum_of.get(attr, [])) or 2
            if is_arr:
                vals = _array_values(t, int(k_array), rand, n_enum)
                _drive_array_input(cmds, (node,), attr, t, vals)
                report["driven"].append((attr, t, "array[%d]" % len(vals)))
                report["arrays"] += 1
            else:
                _drive_input(cmds, (node,), attr, t, _elem_value(t, rand, n_enum))
                report["driven"].append((attr, t, "scalar"))
        except Exception as exc:
            report["skipped"].append((attr, t, str(exc)[:80]))
    # Outputs too: an array output with no consumer has no elements to write.
    sized             = bench_size_output_multis(cmds, node, spec, k_array)
    report["outputs"] = list(sized["sized"])
    report["skipped"].extend(sized["skipped"])
    return report


# Families whose real output is a NATIVE base-class plug rather than a declared
# spec output. 24 of 44 templates declare no output at all (a deformer's result
# leaves through outputGeometry), so pulling only DECLARED outputs times those
# nodes doing nothing. Sourced from Maya (readable + non-writable attrs on a fresh
# node), not guessed; mesh/curve/surface defer to codegen._GEO_INFO so the attr
# name has ONE spelling.
_NATIVE_BENCH_OUTPUTS = {
    "mPyDeformer":    (("outputGeometry", True),),
    "mPySkinCluster": (("outputGeometry", True),),
    "mPyBlendShape":  (("outputGeometry", True),),
    "mPyTransform":   (("matrix", False), ("_outLocalFlat", True)),
    "mPyFile":        (("outColor", False), ("outAlpha", False)),
}

# Families with NO compute-driven output plug -- a plug-pull benchmark cannot
# measure them, and saying so beats reporting a silent zero.
#   * mPyLocator's per-frame math is computeBuffers(), called from the DRAW
#     OVERRIDE, never from MPxNode::compute. Its readable plugs are inherited DAG
#     state, and batch mayapy has no viewport to trigger a draw.
#   * mPyIkSolver's work is doSolve(), driven by an ikHandle -- measurable only
#     with a joint chain + handle rig (see bench_ik_rig()).
_BENCH_NO_PLUG_OUTPUT = {
    "mPyLocator": "work happens in the draw override (computeBuffers), not "
                  "compute; batch mayapy has no viewport to trigger it",
    "mPyIkSolver": "work happens in MPxIkSolverNode::doSolve(); drive it with "
                   "bench_ik_rig() instead of a plug pull",
}


def bench_pull_plugs(spec):
    """The output plugs a benchmark must pull, as ``[(attr, is_array)]``.

    ALL of them: pulling only one output lets the DG leave the others clean, so
    a node that writes three arrays would be timed doing a third of its work.
    ``python``/``message`` outputs are excluded (nothing to pull).

    Declared outputs are UNIONed with the family's native output rather than
    used as a fallback: a deformer that also declares a scalar output still does
    its real work in ``deform()``, so pulling only the scalar would time the
    cheap half. Returns [] for the families in ``_BENCH_NO_PLUG_OUTPUT``.
    """
    out = []
    for attr, meta in sorted((spec.get("outputs") or {}).items()):
        if not isinstance(meta, dict):
            continue
        if meta.get("type") in _BENCH_SKIP_TYPES:
            continue
        out.append((attr, bool(meta.get("is_array"))))

    mpy_type = spec.get("mpy_type")
    native   = list(_NATIVE_BENCH_OUTPUTS.get(mpy_type, ()))
    # Geometry generators: reuse the codegen table so outMesh/outCurve/outSurface
    # are never re-spelled here.
    from mpynode.native import compiler as codegen
    kind = codegen._geo_kind(spec)
    if kind:
        native.append((codegen._GEO_INFO[kind]["attr"], False))

    seen = {a for a, _ in out}
    for attr, is_arr in native:
        if attr not in seen:
            out.append((attr, is_arr))
            seen.add(attr)
    return out


def bench_make_node(cmds, spec, type_name, density=40):
    """Create the node to BENCHMARK, attached to whatever it needs to do work.

    `createNode` is right for a compute node and wrong for a deformer: a
    deformer's geometry arrives through the native ``input[0].inputGeometry``,
    which is not a declared spec input, so a bare `createNode` yields an ORPHAN
    with no mesh. Pulling ``outputGeometry`` then computes nothing and the node
    times as ~0.1 ms -- empty, not fast, and indistinguishable from fast in a
    ranking. The parity path already knows this (it uses ``cmds.deformer``);
    this is the same knowledge, so a family can never be driveable there and
    silently vacuous here.

    Returns the node whose plugs the benchmark should pull.
    """
    from mpynode.native import compiler as codegen
    base     = (spec.get("suggested") or {}).get("mpx_base") or ""
    mpy_type = spec.get("mpy_type") or ""
    is_deformer = (base in getattr(codegen, "_DEFORMER_BASES", ())
                   or mpy_type in ("mPyDeformer", "mPySkinCluster",
                                   "mPyBlendShape"))
    if is_deformer:
        d  = max(3, int(density))
        xf = cmds.polySphere(r=1, sx=d, sy=d, ch=False)[0]
        return cmds.deformer(xf, type=type_name)[0]
    return cmds.createNode(type_name)


_STATIC_INPUT_TOKENS = frozenset((
    "rest", "bind", "base", "orig", "original", "ref", "reference", "initial",
    "init", "bound"))


def _name_tokens(name):
    """camelCase / snake_case pieces of an attribute name, lower-cased."""
    return [t.lower() for t in
            re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name or "")]


def _is_static_input_name(name):
    """Does this input's NAME say it holds rig-time state -- a rest cage, bind
    matrices, an original shape -- rather than something that animates?

    ``restCage``, ``bindMatrices``, ``base_mesh``, ``origPoints`` are static;
    ``deformCage``, ``weight``, ``restore`` are not. Token match, so ``rest``
    inside ``restore`` does not count. A static input is left alone between
    benchmark ticks: caching work keyed on it (an inverse of the rest system) is
    a genuine per-frame win in a rig and stays rewarded; a memo keyed on an
    ANIMATED input is a cache hit and is not.
    """
    return any(t in _STATIC_INPUT_TOKENS for t in _name_tokens(name))


def _numeric_mover(cmds, tgt, t):
    """``fn(k)`` that writes a k-dependent value into numeric plug ``tgt``, or
    ``None`` when the plug is missing, driven from upstream, or does not move."""
    try:
        if not cmds.objExists(tgt):
            return None
        if cmds.listConnections(tgt, s=True, d=False):
            return None  # driven from upstream; writing it would fail
        cur = cmds.getAttr(tgt)
    except Exception:
        return None

    def fn(k, _tgt=tgt, _t=t):
        if _t == "matrix":
            # identity with a drifting translation: what an animated target does
            cmds.setAttr(_tgt, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0,
                         1e-3 * k, 0, 0, 1, type="matrix")
        elif _t == "float2":
            cmds.setAttr(_tgt, 1e-3 * k, 2e-3, type="float2")
        elif _t == "time":
            cmds.setAttr(_tgt, float(k))   # one frame per tick, like playback
        elif _t in ("double3", "float3", "vector", "point", "color", "euler"):
            cmds.setAttr(_tgt, 1e-3 * k, 2e-3, 3e-3)
        elif _t == "bool":
            cmds.setAttr(_tgt, k % 2)
        elif _t in ("int", "long", "short"):
            cmds.setAttr(_tgt, k)
        else:
            cmds.setAttr(_tgt, 1e-3 * k)

    # PROVE the move. A locked or range-clamped plug sails through setAttr and
    # would be timed as exactly the cache hit this exists to prevent (measured:
    # 3 setAttr attempts, 0 values changed).
    try:
        fn(1)
        if cmds.getAttr(tgt) == cur:
            return None
    except Exception:
        return None
    return fn


def _geo_mover(cmds, plug, geo_type):
    """``(fn, label)`` moving ONE vertex/CV of the shape wired into geometry
    input ``plug`` by 1e-3 per tick, or ``(None, None)``.

    The shape's output plug is re-evaluated inside ``fn`` -- OUTSIDE the timed
    region -- so the node's tick pays only for its own compute, not for the
    upstream mesh rebuild the move triggers.
    """
    comp_of = {"mesh": ".vtx[0]", "nurbsCurve": ".cv[0]",
               "nurbsSurface": ".cv[0][0]"}
    try:
        if not cmds.objExists(plug):
            return None, None
        srcs = cmds.listConnections(plug, s=True, d=False, p=True) or []
    except Exception:
        return None, None
    if not srcs:
        return None, None
    src_plug = srcs[0]
    shape    = src_plug.split(".")[0]
    comp     = shape + comp_of.get(geo_type, ".vtx[0]")

    def fn(k, _comp=comp, _src=src_plug):
        cmds.move(1e-3, 0.0, 0.0, _comp, r=True)
        try:
            cmds.dgeval(_src)
        except Exception:
            pass

    try:
        before = list(cmds.pointPosition(comp, w=True))
        fn(1)
        after = list(cmds.pointPosition(comp, w=True))
    except Exception:
        return None, None
    if after == before:
        return None, None
    return fn, comp


def bench_perturb_fn(cmds, node, spec, hold=()):
    """A cheap callable that moves the node's ANIMATED inputs between benchmark
    ticks, or ``None`` when there is nothing to move.

    ``dgdirty`` marks plugs dirty but leaves their VALUES identical, so a compute
    that memoizes on input content ("same points and same queries as last call ->
    reuse the answer") turns every timed tick into a no-op. That is not a
    speedup, it is the benchmark measuring a cache hit: an AI optimizer handed
    this workload is rewarded for adding a memo table instead of for making the
    algorithm faster, and in a real rig the fast path barely ever fires -- Maya
    only calls compute() when something genuinely changed.

    Measured on the optimized kDTree: 0.169 ms with static inputs vs 1.785 ms
    with one query point moved -- a 10.6x reporting error. Then measured again,
    2026-09-08, on rbfWrap: this function used to move ONE numeric scalar and
    rbfWrap has only mesh inputs, so nothing moved at all and a candidate that
    cached the whole solve was accepted at 2103 ms -> 0.34 ms ("6103x").

    So now it moves one element of EVERY free numeric input and one vertex/CV
    of EVERY geometry input (plus a deformer's native input mesh), EXCEPT inputs
    whose name says rest/bind/base/orig/ref/initial -- see
    :func:`_is_static_input_name`. That mirrors a rig: the rest cage is static,
    everything else animates. The callable carries ``.moved``, one label per
    thing it moves, for the ledger. Every move is proven by reading the value
    back; a plug that will not move is dropped rather than trusted.
    """
    # Everything a rig animates. `matrix` (aim targets, parent spaces), `time`
    # (simulations) and `float2` (a texture's uv) were missing at first, and
    # aimTransform -- three matrix inputs, nothing else -- was refused as
    # unperturbable on 2026-09-08.
    numeric = ("double", "float", "int", "long", "short", "bool", "angle",
               "double3", "float3", "vector", "point", "color", "euler",
               "matrix", "float2", "time")
    moves = []
    for attr, meta in sorted((spec.get("inputs") or {}).items()):
        if not isinstance(meta, dict):
            continue
        t      = meta.get("type")
        is_arr = bool(meta.get("is_array"))
        # A rest/bind-style name, or a plug the representative scene holds
        # (see scene_hold): the workload's own setting, not something that
        # animates between ticks.
        if _is_static_input_name(attr) or attr in hold:
            continue
        plug = ("%s.%s[0]" % (node, attr)) if is_arr else ("%s.%s" % (node, attr))
        if t in numeric:
            fn = _numeric_mover(cmds, plug, t)
            if fn is not None:
                moves.append(("%s%s (%s)" % (attr, "[0]" if is_arr else "", t), fn))
        elif t in _GEO_IN_TYPES:
            fn, comp = _geo_mover(cmds, plug, t)
            if fn is not None:
                moves.append(("%s <- %s" % (attr, comp), fn))
    # A deformer's geometry is not a declared input; it animates in every rig.
    fn, comp = _geo_mover(cmds, "%s.input[0].inputGeometry" % node, "mesh")
    if fn is not None:
        moves.append(("input[0].inputGeometry <- %s" % comp, fn))
    if not moves:
        return None

    state = {"i": 1}  # the proofs above already applied k=1

    def _perturb():
        state["i"] += 1
        for _label, fn in moves:
            try:
                fn(state["i"])
            except Exception:
                pass

    _perturb.moved = [label for label, _fn in moves]
    return _perturb

def bench_ik_rig(cmds, solver_node, n_joints=4, spacing=3.0):
    """Give an mPyIkSolver something to solve, and return a pull callable.

    An IK solver has no output plug: doSolve() runs when an ikHandle evaluates.
    Build a joint chain driven by a handle bound to this solver, then pulling
    the end joint's worldMatrix forces the solve. Mirrors the chain+handle drive
    in native/ai/verify_scripts.py.

    Returns ``(pull, goal_handle)`` or ``(None, None)`` if the rig cannot be
    built -- callers treat that as an honest skip, never a zero.
    """
    try:
        cmds.select(clear=True)
        joints = []
        for i in range(max(2, int(n_joints))):
            joints.append(cmds.joint(p=(i * spacing, 0.0, 0.0)))
        handle = cmds.ikHandle(sj=joints[0], ee=joints[-1],
                               sol=solver_node)[0]
    except Exception:
        return None, None

    tip = joints[-1]

    def _pull():
        # Reading the tip through the DG is what forces the solve.
        cmds.getAttr("%s.worldMatrix[0]" % tip)

    return _pull, handle


def _scale_pair_scene(cmds, nodes, in_meta, density, k_array, rand):
    """Grow the EXISTING parity pair's scene to a measurable size.

    Parity already stood both nodes up in a fresh scene with identical inputs;
    only the SIZE is wrong for a timing measurement. So re-wire the geo inputs at
    ``density`` and re-seed the array inputs at ``k_array`` -- on BOTH nodes, from
    the same source/values, so the pair stays comparable.

    SCALARS are deliberately left exactly as parity left them. Notably this does
    NOT call :func:`seed_bench_scene`: its voxelize configuration (voxelSize=0.96 /
    maxVoxels=4) is a dead scene, while the parity defaults (0.25 / 20000) are the
    live one -- timing a dead scene measures nothing."""
    for attr, meta in sorted((in_meta or {}).items()):
        if not isinstance(meta, dict):
            continue
        t      = meta.get("type")
        is_arr = bool(meta.get("is_array"))
        try:
            if t in _GEO_IN_TYPES:
                _wire_geo_input(cmds, nodes, attr, t, is_arr, 0,
                                density=density, rewire=True)
            elif is_arr and t not in _NON_DRIVEABLE_IN \
                    and t not in _BENCH_SKIP_TYPES:
                n_enum = len(meta.get("enum_names") or []) or 2
                _drive_array_input(cmds, nodes, attr, t,
                                   _array_values(t, int(k_array), rand, n_enum))
        except Exception:
            pass


def _pull_geo_plug(om2, node, attr):
    """Force ONE evaluation of a geometry output and do nothing else.

    Deliberately not :func:`_read_geo_components`: its MFn extraction
    (getPoints/getVertices/getVertexNormals/getFaceVertexColors) would sit inside
    the timed region as a large constant common to both sides and drag the ratio
    toward 1.0, hiding the very regression this measures."""
    sel = om2.MSelectionList()
    sel.add(node)
    plug = om2.MFnDependencyNode(sel.getDependNode(0)).findPlug(attr, True)
    plug.asMObject()


def _run_timing(cmds, spec, py_node, cpp_node, pull_py, pull_cpp, in_meta,
                deadline):
    """Time the compiled node against the interpreted one on the SAME pair.

    NEVER raises -- any problem degrades to ``{"measured": False, "reason": ...}``,
    because a timing hiccup must not turn a passing parity row into a failure."""
    try:
        import random as _random

        if deadline is None:
            # A direct caller (verify_scripts, a test) owns no bundle-wide budget;
            # give it a local one so this can never hang.
            deadline = time.perf_counter() + _TIMING_BUDGET_S
        if time.perf_counter() > deadline:
            return {"measured": False, "reason": "timing budget exhausted"}

        floor = _timing_floor_ms()
        mesh_query = bool((spec.get("suggested") or {}).get(
            "uses_mesh_intersector"))
        rand  = _random.Random(20260812)
        rungs = _timing_rungs()
        res   = None
        rung  = None
        # Two rungs only, never a ladder climb: A, then at most B.
        for geo_d, k_arr in rungs:
            if time.perf_counter() > deadline:
                if res is not None:
                    break
                return {"measured": False, "reason": "timing budget exhausted"}
            _scale_pair_scene(cmds, (py_node, cpp_node), in_meta, geo_d, k_arr,
                              rand)
            perturbs = [bench_perturb_fn(cmds, py_node, spec),
                        bench_perturb_fn(cmds, cpp_node, spec)]
            if any(p is None for p in perturbs):
                return {"measured": False,
                        "reason": "not measured (no perturbable input -- a "
                                  "content-memoizing compute would be timed as a "
                                  "cache hit)"}
            r = _time_pair(cmds, py_node, cpp_node, pull_py, pull_cpp, perturbs,
                           deadline)
            if r is None:
                return {"measured": False,
                        "reason": "not measured (no complete paired sample was "
                                  "taken)"}
            res, rung = r, (geo_d, k_arr)
            # LOAD-BEARING INTERLOCK -- the ENTIRE protection against hanging. A
            # single compiled evaluation cannot be interrupted once entered, and
            # the regime this guard exists for was 714 SECONDS per eval. So step up
            # to the bigger rung ONLY from a measurement that was both below the
            # noise floor (nothing learned yet) AND cheap (< 1 s). Never step up
            # after an already-expensive rung.
            if not (max(r["py_ms"], r["cpp_ms"]) < floor and r["cpp_ms"] < 1000.0):
                break
        if res is None:
            return {"measured": False, "reason": "not measured (no rung ran)"}
        row = _timing_verdict(res["py_ms"], res["cpp_ms"], floor, res["n"],
                              res["truncated"],
                              "geo %d / array %d" % (rung[0], rung[1]),
                              mesh_query=mesh_query)
        row["rung"] = [rung[0], rung[1]]
        return row
    except Exception as exc:
        return {"measured": False, "reason": "timing not measured: %s" % exc}


def _has_stride_coupled_arrays(spec):
    """True when the compute RESHAPES an array input by a scalar-int input (a
    'stride'/'width'), so the node's parallel array inputs are CROSS-COUPLED:
    their element counts must be mutually consistent (``len(flat) % width == 0``,
    and the reshaped row count must line up with a companion ``matrix[]``/array
    input). The generic parity harness seeds every multi INDEPENDENTLY at random,
    so it cannot satisfy that coupling -- the interpreted reference raises
    mid-compute (leaving a stale output) and the pointwise compare is a false
    fail. Detect the pattern so ``_verify_one`` can skip and defer to the authored
    ``@maya_test`` (which sets up a coherent set). Example: procrustesCluster --
    ``Lw = int(self.clusterWidth)`` then ``flat.reshape(-1, Lw)`` with a parallel
    ``bindMatrices`` matrix[].

    Conservative by construction (matches only a scalar-int input that demonstrably
    feeds a ``reshape``): a node like procrustesSingle, whose width comes from the
    array's OWN shape (``Lw = int(flat.shape[0])``) and which declares NO int
    scalar input, does NOT match -- its generic parity legitimately runs."""
    compute = spec.get("compute") or ""
    if "reshape" not in compute:
        return False
    inputs = spec.get("inputs") or {}
    int_scalars = [n for n, m in inputs.items()
                   if isinstance(m, dict) and m.get("type") == "int"
                   and not m.get("is_array")]
    has_array_in = any(isinstance(m, dict) and m.get("is_array")
                       for m in inputs.values())
    if not (int_scalars and has_array_in):
        return False
    import re as _re2
    for n in int_scalars:
        # direct: reshape( ... self.<n> ... )
        if _re2.search(r"reshape\s*\([^)]*self\.%s\b" % _re2.escape(n), compute):
            return True
        # aliased: <local> = int(self.<n>)   ...   reshape( ... <local> ... )
        for am in _re2.finditer(
                r"(\w+)\s*=\s*int\(\s*self\.%s\b" % _re2.escape(n), compute):
            alias = am.group(1)
            if _re2.search(r"reshape\s*\([^)]*\b%s\b" % _re2.escape(alias),
                           compute):
                return True
    return False


def _has_carry_state(spec):
    """True when the compute keeps a value BETWEEN evaluations -- a solver carry
    buffer, an integrator's velocity, a latched rest length.

    Delegates to ``_persistent_state_vars``, the SAME definition codegen uses to
    give such a var a per-node home, so the harness and the compiler cannot
    disagree about what "stateful" means. 6 of the 43 shipped templates match."""
    compute = spec.get("compute") or ""
    if not compute:
        return False
    declared = set(spec.get("inputs") or {}) | set(spec.get("outputs") or {})
    from mpynode.native.compiler.nd_lower import _persistent_state_vars
    try:
        return bool(_persistent_state_vars(compute, declared))
    except SyntaxError:
        return False


class _ExpressionErrorTap:
    """Context manager that counts the ``[<type> expression error]`` lines the
    interpreted runtime prints to stderr (``base_contract.report_error``) while
    the reference evaluates. Everything else it writes passes straight through.
    In-process by design: the interpreted node's compute runs in THIS mayapy."""

    def __init__(self):
        self.hits  = 0
        self._real = None

    def write(self, s):
        if "expression error" in s:
            self.hits += 1
        return self._real.write(s) if self._real is not None else len(s)

    def flush(self):
        if self._real is not None:
            self._real.flush()

    def __enter__(self):
        import sys
        self._real, sys.stderr = sys.stderr, self
        return self

    def __exit__(self, *exc):
        import sys
        sys.stderr = self._real
        return False


def _reference_raised(cmds, node, out_meta):
    """Evaluate the INTERPRETED node once and say whether its compute raised.

    The generic drive is random -- a negative ``degree`` for a b-spline, an
    index past an array -- and on such a set the reference raises mid-compute
    and leaves whatever it last wrote in its outputs, while the compiled node
    handles the same input its own way. Comparing those two is comparing a
    stale buffer to a live one (spline read as FAIL 1.99 that way). Such a set
    is NOT comparable; the caller excludes it and says so."""
    with _ExpressionErrorTap() as tap:
        try:
            _read_outputs(cmds, node, out_meta)
        except Exception:
            return True
    return tap.hits > 0


def _interp_is_idempotent(cmds, node, out_meta, tol):
    """Does the INTERPRETED node answer the same twice for UNCHANGED inputs?

    Pointwise interp-vs-compiled parity silently assumes the two sides evaluate
    the same number of times. They do not: per drive the harness evaluates the
    interpreted node more often than the compiled one -- ``_reference_raised``
    reads it, and this probe dirties it and reads it again -- and until
    2026-09 a written array output stayed dirty (``setAllClean`` only), so every
    read re-ran compute once per array output. For a node carrying state that
    asymmetry advances the two trajectories differently, and the compare
    measures the harness rather than the port -- dnet drifts 1.8e-4 that way
    while being faithful to 1.0e-9.

    So MEASURE it per drive instead of assuming: dirty the interpreted node,
    make it recompute, and see whether its own answer moved. A drive where it
    did is not comparable and is excluded; the rest are compared for real. The
    ``dgdirty`` is required -- ``_read_outputs`` is a plain ``getAttr`` and a
    clean plug would hand back the cached value, making every node look
    idempotent."""
    before = _read_outputs(cmds, node, out_meta)
    cmds.dgdirty(node)
    after = _read_outputs(cmds, node, out_meta)
    for o in out_meta:
        a, b = before.get(o), after.get(o)
        if a is None or b is None:
            continue
        me, nc, _nd = _pair_stats(a[0], b[0])
        if nc and (not math.isfinite(me) or me > tol):
            return False
    return True


def _carry_state_drift(spec, maxerr, tol):
    """True when a SMALL divergence comes from state the compute carries across
    evaluations, for which pointwise interp-vs-compiled parity is not defined.

    The harness evaluates the interpreted node more often than the compiled one
    (see :func:`_interp_is_idempotent`), so anything the compute keeps between
    evaluations -- a solver carry buffer, an integrator's velocity -- is
    advanced a DIFFERENT number of times on the two sides. Both are
    individually correct; the trajectories simply separate. dnet is the case
    in point: with ``resetBuffer=0`` its positions come from the carried
    buffer, and on the one drive where the solver relaxes nothing
    (``iterations <= 0``) there is no contraction left to pull the two back
    together.

    Keyed on ``_persistent_state_vars`` -- the SAME definition codegen already
    uses to give a carry-over var a per-node home -- so this cannot fire on a
    stateless node. That structural precondition is the point: the pre-existing
    magnitude-only ceiling (_DIVERGE_CEIL) was wide enough to absorb a real port
    bug, and dnet's maxDisplacement sentinel sat behind it. Bounded at
    _CARRY_DRIFT_MULT x tol on top, so a sentinel-class error (1e4 x tol) still
    FAILS. Only ever downgrades FAIL->SKIP, never produces a PASS."""
    if not (math.isfinite(maxerr) and tol < maxerr <= tol * _CARRY_DRIFT_MULT):
        return False
    return _has_carry_state(spec)


def _uses_nurbs_cv_idiom(spec):
    """True when a deformer's compute reads/writes NURBS control points via
    ``cvPositions()`` / ``setCVPositions()`` -- the NURBS-deformer idiom for a
    curve/surface. The generic deformer drive attaches BOTH the interpreted and
    the compiled node to a polygon SPHERE, but this compute only handles a NURBS
    output handle: on a mesh the interpreted node's ``cvPositions()`` raises and
    leaves the rest mesh, while the compiled deform (geometry-agnostic
    ``MItGeometry``) still runs -- so the pointwise compare is a false fail. Detect
    it so ``_verify_one`` skips and defers to the authored ``@maya_test`` (which
    drives a real NURBS surface). Same class as the skinCluster / mesh-iksolver /
    stride-coupled skips -- see :func:`_has_stride_coupled_arrays`."""
    compute = spec.get("compute") or ""
    return "cvPositions" in compute or "setCVPositions" in compute


def _is_stale_tail_shrink(na, nb, hiwater):
    """Is this array-length divergence the KNOWN interpreted-vs-compiled
    element-lifetime gap rather than a port bug?

    The two sides keep array elements for different lengths of time, on purpose
    (T14/T94 -- see ``_api2.helpers.write_multi_plug_value``). The interpreted
    reference takes the datablock's existing builder, so its element count is a
    HIGH-WATER MARK across the sweep; the compiled node builds a fresh sized
    builder, so its count is what THIS evaluation produced. A node whose output
    shrinks therefore reports ``na > nb`` with no port bug in sight.

    ``hiwater`` is the largest count the COMPILED side has produced so far in
    this sweep, and it is what keeps the excuse narrow: agreement implies the
    interpreted high-water equals the compiled high-water, so the divergence is
    only excused when the compiled node DID reach ``na`` at some point and has
    since written fewer. A port that is systematically short (Python 4 vs
    compiled 2 every evaluation, ``hiwater == 2``) never reaches it and stays a
    real mismatch, as does a compiled side that produced MORE than the
    interpreted reference ever did.

    A shrink to ZERO is NOT this gap and is never excused (T101). ``emit_attr``
    guards the rewrite with ``if (!out_<mem>.empty())``, so an evaluation whose
    compute assigns nothing leaves the compiled array with every element it
    already had -- a compiled count of 0 after the node has produced more is
    UNREACHABLE while that guard stands. Seeing one means the array was WIPED
    (the T96 signature, i.e. the guard is gone), which is a real failure, not a
    tail drop. Rejecting it costs the T94 excuse nothing: a genuine short write
    always leaves at least one element behind.

    That branch is no longer a no-op: since 2026-08-20 it writes the per-type
    DEFAULT to each surviving element, matching the interpreted pre-seed. The
    reachability argument above is unchanged -- it writes in place and never
    touches the element COUNT -- but this gate is count-only, so it can neither
    see nor score that fill. What does is the VALUE comparison in
    ``_compare_once``; and that comparison never reached the empty branch on
    procrustesTags, because ``clusterTags`` is a string array and strings are in
    ``_NON_DRIVEABLE_IN``, so no drive could ever empty it. The divergence sat
    green for that reason, not because a count agreed.

    What this cannot see -- and no count can, now that the interpreted count is
    a high-water mark -- is a port that shrinks ONLY mid-sweep while the Python
    keeps its length. That case is indistinguishable from the intended
    semantics; the shared prefix is still compared pointwise.
    """
    return 0 < nb < na == hiwater


def _with_stale_tail(reason, stale_tail):
    """Append the excused-shrink note (if any) to a row's ``reason``.

    Excused, but NEVER SILENT: say which outputs shrank and by how much, so a
    reader can tell "the semantics gap fired here" from "no array divergence".
    Called on every :func:`_verify_one` return reachable once the sweep has run
    -- appending it on the normal path only dropped the note from rows that are
    vacuous, beyond ``_DIVERGE_CEIL``, or carry another real count mismatch,
    which is exactly where a reader needs both facts.
    """
    if not stale_tail:
        return reason
    note = ("array output(s) shrank below the interpreted reference's "
            "preserved element count (%s) -- the DELIBERATE compiled-vs-"
            "interpreted element-lifetime gap (see "
            "_api2.helpers.write_multi_plug_value), not a port error; the "
            "shared prefix was still compared"
            % ", ".join("%s Python %d vs compiled %d" % (o, na, nb)
                        for o, (na, nb) in sorted(stale_tail.items())))
    return (reason + " -- " if reason else "") + note


def _count_mismatch_reason(o, na, nb, geo_wired_any, unassigned):
    """Classify ONE array-length divergence. Returns ``(ran, passed, reason)``.

    Three causes are distinguishable, and the original single test collapsed the
    first two into the third's excuse:

    * the compiled body populated an output the Python compute NEVER ASSIGNS.
      That is provable from the spec without running anything, so it is a real
      FAIL whose reason names the cause. Blaming the harness here is what let a
      kd-tree port ship ``distance``/``closestIndex`` values harvested from two
      discarded Python locals.
    * the PYTHON side came back empty while a geometry input was wired: the
      interpreted reference cannot evaluate a synthesized upstream shape in a
      headless standalone (live MFn query) where the compiled node reads its own
      datablock and succeeds. Genuinely inconclusive -> SKIP.
    * anything else -- INCLUDING the compiled side being the empty one, which is
      the classic broken-port signature. The old test was ``min(na, nb) == 0``,
      symmetric, so it skipped that direction too AND narrated it as "the
      interpreted reference could not evaluate", the exact opposite of the truth.
    """
    if o in (unassigned or ()):
        return (True, False,
                "array output %r: the compiled body populated %d element(s) for "
                "an output the Python compute never assigns (Python %d) -- the "
                "port invented values instead of leaving it untouched"
                % (o, nb, na))
    if geo_wired_any and na == 0 and nb > 0:
        return (False, None,
                "array output %r count diverged (Python %d vs compiled %d) with "
                "a wired geometry input -- the interpreted reference could not "
                "evaluate the synthesized geometry headlessly (live MFn query); "
                "pointwise parity inconclusive -- skipped" % (o, na, nb))
    return (True, False,
            "array output %r element count differs (Python %d vs compiled %d)"
            % (o, na, nb))


def _pick_count_verdict(mismatches, geo_wired_any, unassigned):
    """The strongest verdict among every output that diverged in length.

    ``count_mismatch`` used to be one slot overwritten on every hit across the
    30-iteration sweep, so whichever output diverged LAST decided the outcome --
    a benign geometry-driven skip recorded last would bury a real failure
    recorded first. A real verdict now outranks an inconclusive one, and ties
    break on the output name so the answer does not depend on dict order.
    """
    verdicts = [(o, _count_mismatch_reason(o, na, nb, geo_wired_any, unassigned))
                for o, (na, nb) in sorted(mismatches.items())]
    verdicts.sort(key=lambda pair: (0 if pair[1][0] else 1, pair[0]))
    return verdicts[0][1]


def _verify_one(cmds, bundle_path, spec, maya=_MAYA_DEFAULT, deadline=None):
    """Parity-check ONE node (compiled type vs the Python original mPyNode).

    Dispatches by MPx base: compute (scalar plug compare), deformer (point
    compare on a sphere), iksolver (joint world-position compare). Returns a row
    ``{ran, pass, maxerr, tol, reason}``.

    ``deadline`` is the BUNDLE-WIDE ``time.perf_counter()`` cut-off for the
    optional timing pass (owned by :func:`_default_verify`); None means "no shared
    budget", and the timing pass falls back to its own local one.
    """
    import random

    from mpynode.native import compiler as codegen
    from mpynode.native.compiler import emit_compute
    from mpynode.native.spec import spec_extractor

    # RNG parity depends on WHICH porter path the node took:
    #   * DETERMINISTICALLY LOWERED RNG maps to nd::MT19937, which reproduces
    #     numpy's legacy RandomState draw-for-draw (nd_rng_test.py) -- pointwise
    #     parity is MEANINGFUL and MUST run (bit-exact, maxerr == 0).
    #   * AI-PORTED RNG uses C++ <random>, NOT bit-identical to Python -- a
    #     pointwise check would always "fail", so skip it.
    # The scaffold's PORT region marker distinguishes the two: a fully lowered node
    # has NO PORT_BEGIN. RNG can only survive lowering via the bit-exact
    # nd::MT19937 idiom, so "no PORT region" implies "bit-exact RNG". Checking the
    # SCAFFOLD, not the filled .cpp, is correct: the LLM only fills the PORT
    # region, never removes it.
    if spec_extractor.spec_uses_rng(spec):
        try:
            _scaffold = codegen.generate_cpp(spec)
        except Exception:
            _scaffold = ""
        if (not _scaffold) or (codegen.PORT_BEGIN in _scaffold):
            return {"ran": False, "pass": None, "maxerr": None, "tol": None,
                    "reason": "uses RNG via the AI porter (C++ <random>); not "
                              "bit-identical to Python -- pointwise parity "
                              "skipped"}
        # else: RNG was deterministically lowered to bit-exact nd::MT19937 --
        # fall through and parity-check it like any other numeric node.

    # Geometry generators emit a TYPED geo data attr, not scalar plugs, and take
    # ARRAY inputs. The generic scalar harness below can neither read a geo output
    # nor drive multis, so route geo nodes to a dedicated component-parity branch
    # BEFORE the array skip claims them. (The RNG skip above still applies first.)
    #
    # This runs BEFORE the image skip below. A geo node that ALSO reads an image
    # used to hit that skip first and lose ALL of its parity checking -- silently,
    # because the controller swallows verify problems. The image read now NARROWS
    # the claim: string inputs are driven EMPTY, so both sides take the same
    # no-file fallback and the geometry is compared for real while the
    # decoded-pixel path is not. That caveat rides on the row's reason.
    _gk = codegen._geo_kind(spec)
    if _gk:
        row = _verify_geo(cmds, bundle_path, spec, _gk, deadline=deadline)
        if spec_extractor.spec_reads_image_file(spec):
            row["reason"] = "; ".join(
                x for x in (row.get("reason"), _GEO_IMAGE_NOTE) if x)
        return row

    # Texture/file nodes read their image via MImage::readFromFile at eval time,
    # so output depends on EXTERNAL file state and MImage's decode / colour
    # management will not match a raw PIL/cv2 read bit-for-bit. Skip BEFORE
    # touching the scene -- the build is still verified to compile + load; this is
    # a not-checked flag, NOT a parity failure.
    #
    # The deformer family and the ik solver are EXCLUDED for exactly the reason
    # geo was hoisted above this: they have real parity branches further down, and
    # letting this skip claim them would forfeit ALL of it silently. Both of those
    # branches leave string inputs at their DEFAULT on either node (see the
    # `_NON_DRIVEABLE_IN` continue in each drive loop), so the two take the SAME
    # no-file fallback -- the deformation / solve is compared for real and only the
    # decoded-pixel path goes unexercised. That caveat rides on the row's reason.
    reads_img = spec_extractor.spec_reads_image_file(spec)
    base      = spec.get("suggested", {}).get("mpx_base", "MPxNode")
    # An mPyFile is no longer skipped: parity_fixtures() hands both nodes the
    # same generated gradient PNG and the compare runs at _TEXTURE_TOL. Only a
    # non-texture, non-geometry node that reads an image still has no fixture.
    if reads_img and spec.get("mpy_type") != "mPyFile" \
            and base not in codegen._DEFORMER_BASES \
            and base != codegen._IKSOLVER_BASE:
        return {"ran": False, "pass": None, "maxerr": None, "tol": None,
                "reason": "reads an image file (MImage::readFromFile) and the "
                          "harness has no fixture for this family; output "
                          "depends on external file state -- pointwise parity "
                          "skipped (build verified to compile + load)"}

    # ARRAY (multi) attrs are DRIVEN and COMPARED: multi INPUT element plugs are
    # setAttr'd on both nodes and multi OUTPUT plugs read back index-by-index. A
    # non-vacuous guard skips the row if no component ended up comparable, so an
    # empty-output node is a not-checked skip, never a false PASS.

    # float2 (uvCoord) is the texture interface -- a NATIVE mPyFile attr, never
    # user-declarable, so a texture node is rebuilt AS an mPyFile below and its
    # uvCoord DRIVEN with outColor/outAlpha compared. Most file nodes were already
    # skipped above via reads_image_file; a PROCEDURAL texture (no file read) falls
    # through and gets real parity. A float2 on a NON-texture node has no host to
    # rebuild on (can't happen today) -- skip honestly rather than raise.
    tex = sorted({n for n, m in
                  list((spec.get("inputs") or {}).items())
                  + list((spec.get("outputs") or {}).items())
                  if isinstance(m, dict) and m.get("type") == "float2"})
    if tex and spec.get("mpy_type") != "mPyFile":
        return {"ran": False, "pass": None, "maxerr": None, "tol": None,
                "reason": "uses float2 attr(s) %s on a non-mPyFile node; float2 is "
                          "the native texture interface and has no generic host to "
                          "rebuild on -- pointwise parity skipped" % ", ".join(tex)}

    # Cross-coupled array inputs (procrustesCluster's flat `clusters` reshaped by
    # `clusterWidth`, one row per `bindMatrices` element): the generic drive seeds
    # each multi INDEPENDENTLY, so it cannot produce a mutually-consistent set. Fed
    # an inconsistent one the interpreted reference RAISES mid-compute while the
    # compiled C++ reshapes its own way -> a FALSE fail. Defer to the authored
    # @maya_test, which sets up a coherent set. See _has_stride_coupled_arrays.
    if _has_stride_coupled_arrays(spec):
        return {"ran": False, "pass": None, "maxerr": None, "tol": None,
                "reason": "compute reshapes an array input by a scalar-int "
                          "stride/width -- its array inputs are cross-coupled "
                          "(element counts must be mutually consistent), which the "
                          "generic per-input random drive cannot synthesize; "
                          "pointwise parity skipped (authored @maya_test is the "
                          "parity gate)"}

    name = spec["suggested"]["node_type_name"]

    # ----- deformer family -----
    if base in codegen._DEFORMER_BASES:
        import mpynode
        tol      = 1e-3
        src_type = spec.get("mpy_type") or "mPyDeformer"
        # A skinCluster attached with a bare cmds.deformer has NO wired joints and
        # NO painted weights (J=0), so the generic point-compare pits two
        # degenerate skins against each other: LBS collapses to zeros (a vacuous
        # "pass") and DQS's qr[0] throws IndexError and crashes Maya. Skip here;
        # tools/harness/skin_*_parity.py is the source of truth.
        # A skinCluster attached with a bare cmds.deformer has no joints and no
        # weights (J=0): LBS collapses to zeros, DQS crashes on qr[0]. So a skin
        # gets a bound arm instead of a sphere -- see _skin_rig.
        is_skin = base == "MPxSkinCluster" or src_type == "mPySkinCluster"
        # A NURBS geometry filter (cvPositions/setCVPositions) only handles NURBS
        # output; the generic drive attaches a polygon SPHERE, on which the
        # interpreted node raises and the pointwise compare is a false fail. Defer
        # to the authored @maya_test (drives a real NURBS surface).
        if _uses_nurbs_cv_idiom(spec):
            return {"ran": False, "pass": None, "maxerr": None, "tol": tol,
                    "reason": "NURBS CV-idiom deformer "
                              "(cvPositions/setCVPositions); generic drive uses a "
                              "polygon sphere, so pointwise parity is skipped -- "
                              "authored @maya_test drives a real NURBS surface"}
        IN_META = spec.get("inputs") or {}
        INP     = {k: v["type"] for k, v in IN_META.items()}
        ENUM = {k: (v.get("enum_names") or [])
                for k, v in IN_META.items() if v.get("type") == "enum"}
        K_ARR = 4
        cmds.file(new=True, force=True)
        if not cmds.pluginInfo(os.path.basename(bundle_path), q=True, loaded=True):
            cmds.loadPlugin(bundle_path)
        random.seed(7)

        def sph(nm):
            return cmds.polySphere(r=1, sx=12, sy=12, ch=False, name=nm)[0]

        if is_skin:
            sa, sb, joints, elbow, bind, weights = _skin_rig(cmds, name)
        else:
            sa = sph("origS_" + name)
        da = cmds.deformer(sa, type=src_type)[0]
        w  = mpynode.wrap_node(da)
        for nm, m in IN_META.items():
            t  = m["type"]
            ia = bool(m.get("is_array"))
            if t == "enum":
                w.add_input_attr(nm, t, is_array=ia, enum_names=ENUM.get(nm) or None)
            else:
                w.add_input_attr(nm, t, is_array=ia)
        if (spec.get("init") or "").strip():
            w.set_init_expression(spec["init"])
        w.set_compute_expression(spec["compute"])
        if not is_skin:
            sb = sph("cmpS_" + name)
        db = cmds.deformer(sb, type=name)[0]
        if is_skin:
            for _nd in (da, db):
                _bind_skin_node(cmds, _nd, joints, bind, weights)

        held_enums = _side_effect_gated_enums(spec)

        def smp(nm, t):
            if t == "bool":
                return random.choice([0, 1])
            if t == "enum":
                if nm in held_enums:
                    return _enum_default(IN_META.get(nm), ENUM.get(nm))
                return random.randint(0, max(0, len(ENUM.get(nm, [])) - 1))
            if t in ("vector", "euler", "color"):
                return [random.uniform(0.0, 1.0) for _ in range(3)]
            if t == "quaternion":
                return [random.uniform(-1.0, 1.0) for _ in range(4)]
            if t == "matrix":
                return _rand_matrix16(random)
            if t == "time":
                return float(random.randint(1, 24))
            if "iter" in nm.lower() or t == "int":
                return random.randint(1, 8)
            if nm.lower() == "mu":
                return random.uniform(-0.62, -0.40)
            if nm.lower() in ("lam", "lambda"):
                return random.uniform(0.15, 0.6)
            return random.uniform(0.0, 1.0)

        def pts(sp):
            return cmds.xform(sp + ".vtx[*]", q=True, os=True, t=True)

        maxerr = 0.0
        for _ in range(10):
            env = random.uniform(0, 1)
            cmds.setAttr(da + ".envelope", env)
            cmds.setAttr(db + ".envelope", env)
            if is_skin:
                _pose_skin_rig(cmds, elbow, random)
            weight_arrays = 0
            for a, m in IN_META.items():
                t = m["type"]
                if t in _NON_DRIVEABLE_IN or t in _GEO_IN_TYPES:
                    continue  # string/geo input: left at default (identical both)
                if m.get("is_array"):
                    if is_skin and "weight" in a.lower() and t in ("double", "float"):
                        # a declared per-vertex-per-joint weight set (N*J), not
                        # K_ARR random floats
                        vals = _skin_weight_values(weights, roll=weight_arrays)
                        weight_arrays += 1
                    else:
                        vals = _array_values(t, K_ARR, random,
                                             len(ENUM.get(a, [])) or 2)
                    _drive_array_input(cmds, (da, db), a, t, vals)
                else:
                    _drive_input(cmds, (da, db), a, t, smp(a, t))
            pa, pb = pts(sa), pts(sb)
            for i in range(min(len(pa), len(pb))):
                maxerr = max(maxerr, abs(pa[i] - pb[i]))
        row = {"ran": True, "pass": maxerr <= tol, "maxerr": maxerr,
               "tol": tol, "reason": _IMAGE_UNEXERCISED_NOTE if reads_img else ""}
        row["reason"] = _held_enum_note(held_enums, row["reason"])
        if _timing_enabled():
            # v1 scope: the deformer pair is bound to a fixed 12x12 sphere and its
            # pull marshals every vertex through Python, so a ratio measured here
            # would be dominated by the harness, not the node. Say so in the row --
            # a blank timing field would read as "measured, fine".
            row["timing"] = {
                "measured": False,
                "reason":   "deformer timing not implemented -- the parity pair is "
                          "bound to a fixed 12x12 sphere and its pull marshals "
                          "every vertex through Python"}
        return row

    # ----- iksolver family -----
    if base == codegen._IKSOLVER_BASE:
        tol = 1e-3
        # Mesh-input solvers need a wired floor for a meaningful check; the
        # generic harness skips those (it would compare two identity solvers).
        mesh_inputs = [n for n, m in (spec.get("inputs") or {}).items()
                       if m.get("type") == "mesh"]
        if mesh_inputs:
            return {"ran": False, "pass": None, "maxerr": None, "tol": tol,
                    "reason": "mesh-input IK solver needs a wired floor; "
                              "skipped in generic verify"}
        # An IK solver has no output plug -- doSolve() runs when an ikHandle
        # evaluates -- so the observable is the JOINT WORLD POSITIONS it authors
        # (robust to euler representation, unlike comparing rotate channels).
        # Stand up two identical 3-joint chains, bind one handle to the
        # interpreted solver and one to the compiled solver, move both to the SAME
        # goals while driving the same input samples, and compare. Same drive as
        # native/ai/verify_scripts._verify_script_iksolver and
        # tools/parity_sweep/parity_mPyIkSolver.py, run in-process here.
        import mpynode
        src_type = spec.get("mpy_type") or "mPyIkSolver"
        IN_META  = spec.get("inputs") or {}
        ENUM = {k: (v.get("enum_names") or [])
                for k, v in IN_META.items() if v.get("type") == "enum"}
        K_ARR = 4
        cmds.file(new=True, force=True)
        if not cmds.pluginInfo(os.path.basename(bundle_path), q=True, loaded=True):
            cmds.loadPlugin(bundle_path)
        random.seed(11)

        def chain(prefix, n=3, blen=5.0):
            cmds.select(clear=True)
            js = [cmds.joint(p=(i * blen, 0.0, 0.0), name="%s_j%d" % (prefix, i))
                  for i in range(n)]
            # A slight bend so the solve plane is well-defined.
            cmds.setAttr(js[1] + ".preferredAngleZ", 10.0)
            return js

        def ws(joints):
            out = []
            for j in joints:
                out.extend(cmds.xform(j, q=True, ws=True, t=True))
            return out

        sa = cmds.createNode(src_type)
        w  = mpynode.wrap_node(sa)
        for nm, m in IN_META.items():
            t  = m["type"]
            ia = bool(m.get("is_array"))
            if t == "enum":
                w.add_input_attr(nm, t, is_array=ia, enum_names=ENUM.get(nm) or None)
            else:
                w.add_input_attr(nm, t, is_array=ia)
        if (spec.get("init") or "").strip():
            w.set_init_expression(spec["init"])
        w.set_compute_expression(spec["compute"])
        sb = cmds.createNode(name)

        ja = chain("srcIk_" + name)
        ha = cmds.ikHandle(sj=ja[0], ee=ja[-1], sol=sa)[0]
        jb = chain("cmpIk_" + name)
        hb = cmds.ikHandle(sj=jb[0], ee=jb[-1], sol=sb)[0]

        rest   = ws(ja)
        maxerr = 0.0
        moved  = False
        for _ in range(8):
            goal = (random.uniform(2.0, 9.0), random.uniform(-4.0, 4.0),
                    random.uniform(-4.0, 4.0))
            for h in (ha, hb):
                cmds.xform(h, ws=True, t=goal)
            for a, m in IN_META.items():
                t = m["type"]
                if t in _NON_DRIVEABLE_IN or t in _GEO_IN_TYPES:
                    continue  # string/geo input: left at default (identical both)
                enum_n = len(ENUM.get(a, [])) or 2
                if m.get("is_array"):
                    _drive_array_input(cmds, (sa, sb), a, t,
                                       _array_values(t, K_ARR, random, enum_n))
                else:
                    _drive_input(cmds, (sa, sb), a, t,
                                 _elem_value(t, random, enum_n))
            pa, pb = ws(ja), ws(jb)
            for i in range(min(len(pa), len(pb))):
                maxerr = max(maxerr, abs(pa[i] - pb[i]))
                if abs(pa[i] - rest[i]) > tol:
                    moved = True
        if not moved:
            # The REFERENCE chain never left its rest pose, so maxerr is 0 because
            # nothing ever solved -- a vacuous pass, not a parity result. Say so.
            return {"ran": False, "pass": None, "maxerr": None, "tol": tol,
                    "reason": "the interpreted solver never moved its chain (no "
                              "solve was driven), so a pointwise compare would be "
                              "vacuous -- parity skipped"}
        row = {"ran": True, "pass": maxerr <= tol, "maxerr": maxerr,
               "tol": tol, "reason": _IMAGE_UNEXERCISED_NOTE if reads_img else ""}
        if _timing_enabled():
            # doSolve() is driven by an ikHandle, not a plug pull, so the shared
            # _run_timing (which perturbs inputs and pulls output plugs) does not
            # apply. A blank timing field would read as "measured, fine".
            row["timing"] = {
                "measured": False,
                "reason":   "iksolver timing not implemented -- doSolve() is driven "
                          "by an ikHandle rather than an output-plug pull (see "
                          "bench_ik_rig)"}
        return row

    # ----- scalar compute family (now also drives/compares ARRAY multis) -----
    tol = 1e-4
    from mpynode.wrappers._mpy_node import MPyNode
    IN_META  = spec.get("inputs") or {}
    OUT_META = dict(spec.get("outputs") or {})
    OUT_META.update(_native_family_outputs(spec))
    INP = {k: v["type"] for k, v in IN_META.items()}
    OUT = {k: v["type"] for k, v in OUT_META.items()}
    ENUM = {k: (v.get("enum_names") or [])
            for k, v in IN_META.items() if v.get("type") == "enum"}
    if not OUT:
        # No outputs to compare -> the parity loop below would be vacuous (maxerr
        # stays 0.0 -> a false PASS). Mark as a not-run skip BEFORE touching the
        # scene; the build still compiled + loaded.
        return {"ran": False, "pass": None, "maxerr": None, "tol": tol,
                "reason": "no scalar outputs to compare -- pointwise parity "
                          "skipped (vacuous check)"}
    # Number of elements seeded into each array (multi) INPUT. Parallel per-shape
    # arrays (dnet index0/index1/...) all get K so they align by index; identical
    # seeds on both nodes make even degenerate values a valid parity probe.
    K_ARR = 4
    cmds.file(new=True, force=True)
    if not cmds.pluginInfo(os.path.basename(bundle_path), q=True, loaded=True):
        cmds.loadPlugin(bundle_path)
    random.seed(1234)
    # Texture nodes expose uvCoord / outColor / outAlpha / fileName as NATIVE attrs
    # (not add_input_attr'd), so a generic mPyNode can't host them. Rebuild the
    # Python original AS an mPyFile; a preset already present on the fresh node is
    # skipped in the add loops below. Genuine USER attrs are still added normally.
    is_texture   = spec.get("mpy_type") == "mPyFile"
    is_transform = spec.get("mpy_type") == "mPyTransform"
    if is_texture:
        from mpynode.wrappers.mpy_file import MPyFile
        w = MPyFile.create(name="orig_" + name)
    elif is_transform:
        # The compute writes self.local_matrix, which only a transform-family
        # node has; a generic mPyNode host would raise on every evaluation.
        from mpynode.wrappers.mpy_transform import MPyTransform
        w = MPyTransform.create(name="orig_" + name)
    else:
        w = MPyNode.create(name="orig_" + name)
    orig = w.get_name()
    if is_texture:
        # Two decode paths (MImage on the compiled side, the runtime's reader on
        # the interpreted): the image harness gates DG-vs-DG at 1.5/255.
        tol = _TEXTURE_TOL

    def _is_native(node, attr):
        try:
            return bool(cmds.attributeQuery(attr, node=node, exists=True))
        except Exception:
            return False

    for nm, m in IN_META.items():
        if (is_texture or is_transform) and _is_native(orig, nm):
            continue  # native preset (uvCoord/fileName/...) already present
        t  = m["type"]
        ia = bool(m.get("is_array"))
        if t == "enum":
            w.add_input_attr(nm, t, is_array=ia, enum_names=ENUM.get(nm) or None)
        else:
            w.add_input_attr(nm, t, is_array=ia)
    for nm, m in OUT_META.items():
        if m.get("native") or (is_texture and _is_native(orig, nm)):
            continue  # native output (outColor/outAlpha/matrix) already present
        w.add_output_attr(nm, m["type"], is_array=bool(m.get("is_array")))
    if (spec.get("init") or "").strip():
        w.set_init_expression(spec["init"])
    w.set_compute_expression(spec["compute"])
    comp         = cmds.createNode(name)
    unregistered = _unregistered_type(cmds, comp, name, tol)
    if unregistered:
        return unregistered
    # An array OUTPUT has no elements until something consumes them, and the
    # runtime sizes it from those elements -- so spline / springChain /
    # procrustesTags wrote nothing on either side ("no comparable components")
    # and spine compared 0 elements against 4. K_ARR consumers on BOTH nodes.
    for _nd in (orig, comp):
        bench_size_output_multis(cmds, _nd, spec, K_ARR)

    held_enums = _side_effect_gated_enums(spec)

    def smp(t, nm):
        if t == "bool":
            return random.choice([0, 1])
        if t == "int":
            return random.randint(-6, 6)
        if t == "enum":
            if nm in held_enums:
                return _enum_default(IN_META.get(nm), ENUM.get(nm))
            return random.randint(0, max(0, len(ENUM.get(nm, [])) - 1))
        if t == "float2":
            # texture uvCoord: sample across a few tiles so u-v wrap/floor is
            # exercised, not only the [0,1) cell.
            return [random.uniform(-2.0, 2.0) for _ in range(2)]
        if t == "color":
            return [random.uniform(0, 1) for _ in range(3)]
        if t in ("vector", "euler"):
            return [random.uniform(-4, 4) for _ in range(3)]
        if t == "quaternion":
            return [random.uniform(-1, 1) for _ in range(4)]
        if t == "matrix":
            return _rand_matrix16(random)
        if t == "time":
            return float(random.randint(1, 48))
        return random.uniform(-4, 4)

    # TYPED geo inputs: wire a real upstream shape into each so a geo-consuming
    # node gets REAL parity instead of a vacuous default read. Wired ONCE; the
    # connection persists across the drive loop. One that can't be wired on both
    # sides (a codegen gap) is peeled.
    geo_unwired = []
    for nm, m in IN_META.items():
        if m["type"] in _GEO_IN_TYPES:
            if not _wire_geo_input(cmds, (orig, comp), nm, m["type"],
                                   bool(m.get("is_array")), 0):
                geo_unwired.append(nm)

    # string inputs (+ any geo input that could not be wired) are left at their
    # default on BOTH nodes (identical state) -- recorded so a PASS is honestly
    # annotated as only-partially-exercised.
    # A string input the harness can back with a generated file gets one, on
    # BOTH nodes, before the drive loop (the loop leaves strings alone).
    fixtures = parity_fixtures(spec, k=K_ARR)
    apply_fixtures(cmds, (orig, comp), fixtures)
    fixed = sorted(fixtures)
    peeled = sorted([nm for nm, m in IN_META.items()
                     if m["type"] in _NON_DRIVEABLE_IN and nm not in fixtures]
                    + geo_unwired)
    maxerr   = 0.0
    compared = 0  # non-vacuous guard: components actually paired
    diverged = 0  # pairs where BOTH sides blew up (non-finite)
    # name -> (py_count, compiled_count). A DICT, not one slot: every diverging
    # output is kept so the strongest verdict decides (_pick_count_verdict).
    count_mismatch = {}
    # name -> largest element count the COMPILED side has produced so far, and
    # the divergences excused against it (_is_stale_tail_shrink). Post-T14 the
    # interpreted count is a HIGH-WATER MARK and the compiled one is per-eval, so
    # recording every na != nb turned the deliberate semantics gap into a FAIL.
    out_hiwater = {}
    stale_tail  = {}
    first_drive = None              # input set #1, re-presented after the loop

    def _compare_once():
        """One compiled-vs-interpreted comparison over every output."""
        err, ncomp, ndiv = 0.0, 0, 0
        ra = _read_outputs(cmds, orig, OUT_META)
        rb = _read_outputs(cmds, comp, OUT_META)
        for o, m in OUT_META.items():
            ao, na = ra[o]
            bo, nb = rb[o]
            if m.get("is_array"):
                hw             = max(out_hiwater.get(o, 0), nb)
                out_hiwater[o] = hw
                if na != nb:
                    if _is_stale_tail_shrink(na, nb, hw):
                        stale_tail[o] = (na, nb)
                    else:
                        count_mismatch[o] = (na, nb)
            me, nc, nd = _pair_stats(ao, bo)
            err = max(err, me)
            ncomp += nc
            ndiv  += nd
        return err, ncomp, ndiv

    # Only a carry-state node can be non-idempotent, and the probe costs an extra
    # evaluation per drive -- so decide ONCE, structurally, instead of probing all
    # 43 templates. See _interp_is_idempotent.
    carry_state          = _has_carry_state(spec)
    noncomparable_drives = 0
    raised_drives        = 0
    for _ in range(30):
        drive = {}
        for a, m in IN_META.items():
            t = m["type"]
            if t in _NON_DRIVEABLE_IN or t in _GEO_IN_TYPES:
                continue  # string peeled; geo already wired to an upstream shape
            if m.get("is_array"):
                drive[a] = (t, True, _array_values(t, K_ARR, random,
                                                   len(ENUM.get(a, [])) or 2))
            else:
                drive[a] = (t, False, smp(t, a))
        _apply_drive(cmds, (orig, comp), drive)
        if _reference_raised(cmds, orig, OUT_META):
            # The reference could not compute this input set at all; its
            # outputs are stale. Not a parity signal either way.
            raised_drives += 1
            continue
        if carry_state and not _interp_is_idempotent(cmds, orig, OUT_META, tol):
            # The reference moved under its own feet on this input set, so the
            # two sides cannot be lined up here. Excluded, and COUNTED -- a
            # quietly shrunken sweep reads as "covered everything".
            noncomparable_drives += 1
            continue
        # Only a comparable drive is worth replaying (_staleness_reason).
        if first_drive is None:
            first_drive = drive
        me, nc, nd = _compare_once()
        maxerr = max(maxerr, me)
        compared += nc
        diverged += nd

    # A -> B -> A. Everything above walks FORWARD through fresh random states, so
    # it can never revisit one -- which is exactly where a mis-keyed cache hides.
    # Re-present input set #1 and compare against the interpreted node again.
    loop_maxerr = maxerr            # before the replay, so the two can be told apart
    replay_err  = None
    if first_drive:
        _apply_drive(cmds, (orig, comp), first_drive)
        # Re-checked, not assumed: this input set was comparable when it was
        # first seen, but the reference has evaluated many times since.
        if not (carry_state
                and not _interp_is_idempotent(cmds, orig, OUT_META, tol)):
            replay_err, nc, nd = _compare_once()
            maxerr = max(maxerr, replay_err)
            compared += nc
            diverged += nd
    if count_mismatch:
        # The cause is decided per output by _count_mismatch_reason; when several
        # diverged the strongest verdict wins.
        geo_ins = [nm for nm, m in IN_META.items()
                   if m["type"] in _GEO_IN_TYPES]
        geo_wired_any = any(nm not in geo_unwired for nm in geo_ins)
        unassigned = emit_compute.unassigned_output_plugs(
            list(OUT_META), spec.get("compute"))
        ran, passed, why = _pick_count_verdict(count_mismatch, geo_wired_any,
                                               unassigned)
        return {"ran": ran, "pass": passed, "maxerr": maxerr, "tol": tol,
                "reason": _with_stale_tail(why, stale_tail)}
    # Divergence guard: a non-finite or beyond-ceiling maxerr under randomized
    # inputs is the signature of a stateful/iterative solver (see _DIVERGE_CEIL),
    # NOT a systematic port bug -> inconclusive skip, never a false FAIL.
    if not math.isfinite(maxerr) or maxerr > _DIVERGE_CEIL:
        return {"ran": False, "pass": None, "maxerr": maxerr, "tol": tol,
                "reason": _with_stale_tail(
                    "outputs diverge beyond the sanity ceiling (%.1e) under "
                    "randomized inputs -- the signature of a stateful/"
                    "iterative solver, for which naive pointwise parity is "
                    "not a valid check -- skipped" % _DIVERGE_CEIL,
                    stale_tail)}
    if _carry_state_drift(spec, maxerr, tol):
        return {"ran": False, "pass": None, "maxerr": maxerr, "tol": tol,
                "reason": _with_stale_tail(
                    "compute carries state across evaluations and the outputs "
                    "drifted by %.3g (<= %gx tol %.3g) -- the harness "
                    "evaluates the interpreted node more often than the "
                    "compiled one, so the two carry buffers are advanced a "
                    "different number of times; pointwise parity is not a "
                    "valid check -- skipped (authored @maya_test is the parity "
                    "gate)" % (maxerr, _CARRY_DRIFT_MULT, tol),
                    stale_tail)}
    if carry_state and noncomparable_drives and maxerr > tol:
        # A stateful node whose reference was non-idempotent on SOME sets and
        # whose comparable sets still diverged: the two sides were evaluated a
        # different number of times, so the remaining difference is a
        # trajectory difference, not a pointwise verdict. springChain flipped
        # PASS 0.0 / FAIL 0.147 between two identical runs this way. Say the
        # numbers, refuse the verdict.
        return {"ran": False, "pass": None, "maxerr": maxerr, "tol": tol,
                "reason": _with_stale_tail(
                    "compute carries state; the interpreted reference was "
                    "non-idempotent on %d of 30 input sets and the %d comparable "
                    "sets still diverged by %.3g (tol %.3g) -- with the two sides "
                    "evaluated a different number of times that is a trajectory "
                    "difference, not a port verdict; pointwise parity "
                    "inconclusive (authored @maya_test is the parity gate)"
                    % (noncomparable_drives, 30 - noncomparable_drives
                       - raised_drives, maxerr, tol),
                    stale_tail)}
    if compared == 0:
        # Zero comparable components across all configs -- a vacuous check (an
        # array output that never populated, or both sides blew up identically).
        # Skip rather than a false PASS.
        why = ("the interpreted reference raised on every one of the 30 input "
               "sets (the generic random drive never produced a valid set)"
               if raised_drives >= 30 else
               "the interpreted reference was non-idempotent on every one of "
               "the 30 input sets, so none could be lined up"
               if noncomparable_drives >= 30 else
               "both implementations blew up (non-finite) on every comparable "
               "component" if diverged else "outputs produced no comparable "
               "components across the sweep")
        return {"ran": False, "pass": None, "maxerr": None, "tol": tol,
                "reason": _with_stale_tail(
                    "%s -- pointwise parity skipped (vacuous)" % why,
                    stale_tail)}
    reason = ""
    if noncomparable_drives:
        reason = ("compared on %d of 30 input sets: on %d the interpreted "
                  "reference was non-idempotent (it carries state, and the "
                  "harness evaluates it more often than the compiled node), "
                  "so those cannot be lined up pointwise"
                  % (30 - noncomparable_drives, noncomparable_drives))
    if raised_drives:
        reason = ((reason + " -- " if reason else "")
                  + "on %d of 30 input sets the interpreted reference raised "
                    "mid-compute (an input the node rejects, e.g. a negative "
                    "degree) and left stale outputs; those sets were excluded"
                  % raised_drives)
    if fixed:
        reason = ((reason + " -- " if reason else "")
                  + "%d string input(s) driven with generated fixtures: %s"
                  % (len(fixed), ", ".join(fixed)))
    reason = _held_enum_note(held_enums, reason)
    if peeled:
        reason = ((reason + " -- " if reason else "")
                  + "verified with %d geo/string input(s) left at default "
                    "(unwired, could not be synthesized): %s"
                  % (len(peeled), ", ".join(peeled)))
    # Excused, but never silent -- see _with_stale_tail.
    reason = _with_stale_tail(reason, stale_tail)
    # Name the failure when it is specifically the replay that broke. A bare
    # "maxerr too large" sends someone hunting through the maths; "it only broke
    # when an earlier input came back" points straight at the cache.
    stale = _staleness_reason(loop_maxerr, replay_err, tol)
    if stale:
        reason = (reason + " -- " if reason else "") + stale
    passed = maxerr <= tol
    row = {"ran": True, "pass": passed, "maxerr": maxerr,
           "tol": tol, "reason": reason}
    # Gated on the GENERIC verdict computed RIGHT HERE, never the merged one:
    # _merge_authored_test ANDs an authored-test failure into `pass` afterwards,
    # and gating on that would silence the guard on exactly the nodes whose
    # authored test is red. Requiring generic parity to have PASSED also rules out
    # the biggest false positive: an interpreted compute that raises mid-evaluation
    # is FAST, and would otherwise read as "the compiled node is 1000x slower".
    if passed and _timing_enabled():
        row["timing"] = _run_timing(
            cmds, spec, orig, comp,
            lambda: _read_outputs(cmds, orig, OUT_META),
            lambda: _read_outputs(cmds, comp, OUT_META),
            IN_META, deadline)
    return row


# ---------------------------------------------------------------------------
# Geometry-generator parity (mPyMesh / mPyNurbsCurve / mPyNurbsSurface)
# ---------------------------------------------------------------------------

# Deterministic input configs the geo parity sweep tries. Config 0 uses declared
# defaults (author-chosen to build valid geometry); later configs perturb scalars
# within valid ranges so parity covers a range of geometry, not one sample.
#
# LOAD-BEARING with _make_upstream_shape's mesh branch (``sx = 1 + (cfg % 3)``):
# because 5 configs run over a period-3 shape, cfg 3 rebuilds the SAME topology as
# cfg 0. That A->B->C->A revisit is the mis-keyed-cache probe for GEOMETRY inputs
# (the scalar path buys the same probe by replaying input set #1 -- see
# _staleness_reason). Changing this count or that modulo so the sequence never
# revisits a shape SILENTLY DELETES the probe.
_GEO_CFGS = 5

# The mesh idiom is build_default_output(points, counts, indices). Trace which
# INPUT feeds each role by matching `self.<role> = ... self.<input>` so the sweep
# can seed array inputs into ONE valid polygon. Curve/surface generators feed a CV
# array plus, for a surface, the numU/numV grid dims.
import re as _re

# The CV feeder is the FIRST ``self.<input>`` after ``=``, not a trailing scalar:
# ``self.cvs = self.cvsIn * self.scale`` must attribute cvs->cvsIn. A greedy
# ``[^\n]*`` backtracks to the LAST self.X (``scale``), leaving the CV array
# unseeded -- fatal for surfaces. ``*?`` (lazy) stops at the first one.
_GEO_ROLE_RE = {
    "points":  _re.compile(r"self\.points\s*=\s*[^\n]*?self\.(\w+)"),
    "counts":  _re.compile(r"self\.counts\s*=\s*[^\n]*?self\.(\w+)"),
    "indices": _re.compile(r"self\.indices\s*=\s*[^\n]*?self\.(\w+)"),
    "cvs":     _re.compile(r"self\.cvs\s*=\s*[^\n]*?self\.(\w+)"),
    "numU":    _re.compile(r"self\.num_cvs_u\s*=\s*[^\n]*?self\.(\w+)"),
    "numV":    _re.compile(r"self\.num_cvs_v\s*=\s*[^\n]*?self\.(\w+)"),
}

# The CONSTRUCTOR form -- ``Mesh(points=p, counts=c, indices=i)`` -- names the
# role in the KEYWORD, never in a ``self.<role>`` member, so none of the patterns
# above can fire on it. ``Mesh(points=self.vin, counts=self.cin, ...)`` detected NO
# roles: `cin` got the generic 0..3 ramp, the mesh refused to build ("indices
# length 4 != sum(counts) 6"), every config came back EMPTY and the node returned
# a not-run SKIP -- which reads as green in a summary. Each keyword's value is
# scanned only as far as the next ``,`` or ``)`` so one role cannot steal the next
# argument's input. ``points=`` is kind-dependent, resolved in _geo_input_roles.
_GEO_CTOR_ROLE_RE = {
    "counts":  _re.compile(r"\bcounts\s*=\s*[^\n,)]*?self\.(\w+)"),
    "indices": _re.compile(r"\bindices\s*=\s*[^\n,)]*?self\.(\w+)"),
    "numU":    _re.compile(r"\bnum_u\s*=\s*[^\n,)]*?self\.(\w+)"),
    "numV":    _re.compile(r"\bnum_v\s*=\s*[^\n,)]*?self\.(\w+)"),
}
_GEO_CTOR_POINTS_RE = _re.compile(r"\bpoints\s*=\s*[^\n,)]*?self\.(\w+)")

# A surface needs numU*numV == len(cvs) with numU,numV >= degree+1 (=4 at the
# default degree 3). The CV seed is therefore a _GEO_SURF_DIM x _GEO_SURF_DIM
# grid and the detected numU/numV inputs are driven to _GEO_SURF_DIM so the
# grid is valid for EVERY config (a degree-3 curve is happy with the same run).
_GEO_SURF_DIM = 4

# Rides on the verify row of a geo node that also reads an image file: its
# GEOMETRY is genuinely compared, but string inputs are driven empty so both sides
# stay on the no-file fallback and nothing about the decoded image is checked.
_GEO_IMAGE_NOTE = ("reads an image file (MImage::readFromFile): the harness "
                   "drives its path input(s) EMPTY, so geometry parity above is "
                   "real but the image/texture-colour path is NOT exercised")

# Same narrowing for the deformer family and the ik solver, which reach their
# parity branches because the image skip above deliberately does not claim them.
# Those drives leave string inputs at their DEFAULT rather than driving them
# empty -- identical on both nodes either way, which is what makes the compare
# real -- so the wording differs from the geo note above.
_IMAGE_UNEXERCISED_NOTE = ("reads an image file (MImage::readFromFile): the "
                           "harness leaves its path input(s) at their DEFAULT on "
                           "both nodes, so the parity above is real but the "
                           "image/texture-colour path is NOT exercised")


def _geo_input_roles(compute, kind=None):
    """Map an input name -> its geometry role (points/counts/indices/cvs) by
    scanning the compute source for the build_default_output feeder idiom OR the
    Mesh/NurbsCurve/NurbsSurface CONSTRUCTOR form. Best-effort: an input with no
    detected role gets generic seeding. The member form wins where both appear
    -- it is the direct feeder. ``kind`` disambiguates the ctor's ``points=``
    keyword: mesh vertices need one quad, curve/surface CVs need the grid."""
    roles = {}
    for role, rx in _GEO_ROLE_RE.items():
        m = rx.search(compute or "")
        if m:
            roles[m.group(1)] = role
    m = _GEO_CTOR_POINTS_RE.search(compute or "")
    if m:
        roles.setdefault(m.group(1), "points" if kind == "mesh" else "cvs")
    for role, rx in _GEO_CTOR_ROLE_RE.items():
        m = rx.search(compute or "")
        if m:
            roles.setdefault(m.group(1), role)
    return roles


def _geo_scalar_value(meta, t, cfg, random, role=None):
    """A driveable value for a non-array scalar input at config ``cfg``. Config 0
    uses the declared default (valid geometry); later configs perturb it while
    keeping size-like ints POSITIVE (a negative board/degree builds nothing).
    A numU/numV grid-dim input is pinned to the CV grid's dimension for EVERY
    config so numU*numV keeps matching the seeded CV count (an empty surface
    otherwise)."""
    if role in ("numU", "numV"):
        return _GEO_SURF_DIM
    if t == "string":
        # Driven EMPTY on BOTH sides: the harness owns no fixture, and inventing
        # a path would pit MImage's decode against PIL's. Empty keeps both sides
        # on the SAME no-file fallback -- honest for the GEOMETRY, but the
        # file-backed branch is never exercised (see _GEO_IMAGE_NOTE).
        return ""
    dv = meta.get("default_value")
    if cfg == 0 and dv is not None:
        if t in ("vector", "euler", "color") and not isinstance(dv, (list, tuple)):
            return [dv, dv, dv]
        return dv
    if t == "color":
        # float3 RGB: perturbed like a vector, but an undeclared default draws
        # from 0..1 (the generic -2..2 jitter would hand out a negative colour).
        if isinstance(dv, (list, tuple)) and len(dv) == 3:
            return [dv[i] + 0.1 * cfg for i in range(3)]
        return [random.uniform(0.0, 1.0) for _ in range(3)]
    if t == "bool":
        return random.choice([0, 1])
    if t == "enum":
        n = len(meta.get("enum_names") or []) or 2
        return random.randint(0, n - 1)
    if t == "int":
        base = int(dv) if isinstance(dv, (int, float)) else 6
        return max(1, base + cfg)               # stay positive for size inputs
    if t == "time":
        return float(cfg + 1)
    if t in ("vector", "euler"):
        if isinstance(dv, (list, tuple)) and len(dv) == 3:
            return [dv[i] + 0.1 * cfg for i in range(3)]
        return [random.uniform(-2, 2) for _ in range(3)]
    base = float(dv) if isinstance(dv, (int, float)) else 1.0
    return base + 0.25 * cfg


def _geo_array_value(role, t, cfg):
    """A structurally-valid seed for an ARRAY input given its detected role, so
    the generator can build ONE quad (mesh) or a short CV run (curve/surface).
    Returns a list of per-element values (scalars, or [x,y,z] for vectors)."""
    if role == "counts":
        return [4]                              # one quad
    if role == "indices":
        return [0, 1, 2, 3]                     # its four corners
    if t == "matrix":
        # a matrix-array geo input (e.g. an SDF shape-stream's per-shape world
        # matrices): one translated identity per config -> a single valid shape
        # frame. Flat-16 row-major, matching setAttr -type "matrix".
        tx = 0.1 * cfg
        return [[1.0, 0.0, 0.0, 0.0,
                 0.0, 1.0, 0.0, 0.0,
                 0.0, 0.0, 1.0, 0.0,
                 tx, 0.0, 0.0, 1.0]]
    if role == "cvs":
        # A DIM x DIM CV grid, U-major (row u, col v at u*DIM+v). Enough for a
        # degree-3 curve (>= degree+1 CVs) AND a DIM x DIM surface where
        # numU*numV == len(cvs). Perturbing the spacing per config exercises
        # distinct geometry without changing the grid dims.
        s = 1.0 + 0.1 * cfg
        return [[u * s, v * s, 0.0]
                for u in range(_GEO_SURF_DIM) for v in range(_GEO_SURF_DIM)]
    if role == "points" or t in ("vector", "euler"):
        # A non-degenerate unit quad in the XY plane (mesh vertex/CV run).
        s = 1.0 + 0.1 * cfg
        return [[0.0, 0.0, 0.0], [s, 0.0, 0.0], [s, s, 0.0], [0.0, s, 0.0]]
    if t == "bool":
        # a bool multi rejects setAttr values past 1 ("past its maximum value
        # of 1"); alternate 0/1 rather than the generic 0..3 ramp.
        return [0, 1, 0, 1]
    # Unknown int array with no detected role: a short ramp (best effort). If
    # this fails to build geometry the components>0 guard skips honestly.
    return [0, 1, 2, 3]


def _drive_geo_inputs(cmds, nodes, inputs, roles, cfg, random, fixtures=None):
    """Set identical values on every node in ``nodes`` for input config ``cfg``.
    Scalars prefer their declared default; arrays get a role-seeded valid set;
    ``time`` inputs drive the shared timeline (a time plug may be auto-connected
    to time1 on the Python original -- currentTime drives that, setAttr the
    unconnected compiled plug)."""
    for nm, meta in inputs.items():
        t = meta.get("type")
        if t in _GEO_IN_TYPES:
            # A TYPED geo input on a generator (e.g. mesh-in -> mesh-out relax):
            # wire a FRESH upstream shape for this cfg. rewire=True is what makes
            # the geometry actually vary across the sweep -- left idempotent the
            # cfg-0 shape stayed connected for all 5 configs and every geo-in node
            # was only ever parity-checked against ONE 8-vertex cube.
            _wire_geo_input(cmds, nodes, nm, t, bool(meta.get("is_array")), cfg,
                            rewire=True)
            continue
        if meta.get("is_array"):
            vals = _geo_array_value(roles.get(nm), t, cfg)
            for nd in nodes:
                dt = _packed_dt(cmds, nd, nm)
                if dt:
                    # No element plugs on a packed table -- write it whole.
                    _seed_packed(cmds, "%s.%s" % (nd, nm), dt, vals)
                    continue
                for i, ev in enumerate(vals):
                    plug = "%s.%s[%d]" % (nd, nm, i)
                    if t in ("vector", "euler"):
                        cmds.setAttr(plug, ev[0], ev[1], ev[2], type="double3")
                    elif t == "matrix":
                        # a matrix element multi wants the flat-16 -type flag
                        # (a bare setAttr raises "not a simple numeric attribute").
                        cmds.setAttr(plug, *ev, type="matrix")
                    else:
                        cmds.setAttr(plug, ev)
            continue
        v = _geo_scalar_value(meta, t, cfg, random, roles.get(nm))
        if t == "string" and fixtures and nm in fixtures:
            v = fixtures[nm]      # a generated file both nodes read
        if t == "time":
            cmds.currentTime(v)
            for nd in nodes:
                if not cmds.listConnections(nd + "." + nm, s=True, d=False):
                    cmds.setAttr(nd + "." + nm, v)
            continue
        for nd in nodes:
            if t in ("vector", "euler", "color"):
                # a colour is a float3 compound; -type double3 sets it too. A
                # bare setAttr raises "Error reading data element number 2".
                cmds.setAttr(nd + "." + nm, v[0], v[1], v[2], type="double3")
            elif t == "string":
                # a string plug needs the -type flag ("not a simple numeric
                # attribute") -- without it the whole node's geo parity was lost
                # to a harness exception, which reports as a not-run SKIP.
                cmds.setAttr(nd + "." + nm, v, type="string")
            else:
                cmds.setAttr(nd + "." + nm, v)


def _read_geo_components(om2, node, kind, info):
    """Read the geo data MObject off ``node.<out attr>`` and return
    ``{"pts": [x,y,z,...], "topo": <hashable>}`` -- or None when the plug holds
    no geometry (empty / null). ``pts`` is a FLAT float list (all components, so
    a wrong Y/Z can never hide); ``topo`` captures connectivity so a points-only
    match with different topology still fails."""
    sel = om2.MSelectionList()
    sel.add(node)
    mob  = sel.getDependNode(0)
    plug = om2.MFnDependencyNode(mob).findPlug(info["attr"], True)
    try:
        data = plug.asMObject()
    except Exception:
        return None
    if data.isNull():
        return None

    def _flat(pt_array):
        out = []
        for p in pt_array:
            out.extend((p.x, p.y, p.z))
        return out

    # An EMPTY geometry (an all-dead Game-of-Life board -> 0-vertex mesh) is a
    # valid null-ish data object: MFn* may CONSTRUCT on it yet raise "Object does
    # not exist" on first access. Wrap the whole per-kind read so it reports None
    # ("no geometry") -- never a crash, never a false PASS.
    try:
        if kind == "mesh":
            mfn = om2.MFnMesh(data)
            if mfn.numVertices == 0:
                return None
            counts, connects = mfn.getVertices()
            # Normals + colors are part of the output contract, so compare them
            # too: a native gap that drops a channel then FAILS instead of
            # false-passing on a points-only match. Color-set NAMES go in `topo`,
            # so a present-vs-absent set is a hard topology mismatch.
            attrs = []
            try:
                nrm = mfn.getVertexNormals(False, om2.MSpace.kObject)
                for v in nrm:
                    attrs.extend((v.x, v.y, v.z))
            except Exception:
                pass
            color_sets = tuple(mfn.getColorSetNames() or [])
            for cs in color_sets:
                try:
                    for c in mfn.getFaceVertexColors(cs):
                        attrs.extend((c.r, c.g, c.b, c.a))
                except Exception:
                    pass
            return {"pts": _flat(mfn.getPoints(om2.MSpace.kObject)),
                    "topo": (tuple(counts), tuple(connects), color_sets),
                    "attrs": attrs}
        if kind == "curve":
            mfn = om2.MFnNurbsCurve(data)
            if mfn.numCVs == 0:
                return None
            # form + knots are in `topo`, so periodic vs open and any custom knot
            # vector are compared for free (a native form/knot gap -> hard fail).
            return {"pts": _flat(mfn.cvPositions(om2.MSpace.kObject)),
                    "topo": (mfn.degree, int(mfn.form),
                             tuple(round(k, 9) for k in mfn.knots())),
                    "attrs": []}
        # surface
        mfn = om2.MFnNurbsSurface(data)
        if mfn.numCVsInU == 0 or mfn.numCVsInV == 0:
            return None
        return {"pts": _flat(mfn.cvPositions(om2.MSpace.kObject)),
                "topo": (mfn.degreeInU, mfn.degreeInV,
                         int(mfn.formInU), int(mfn.formInV),
                         tuple(round(k, 9) for k in mfn.knotsInU()),
                         tuple(round(k, 9) for k in mfn.knotsInV())),
                "attrs": []}
    except Exception:
        return None


def _topo_mismatch_detail(a, b):
    """Name WHAT diverged between two ``topo`` tuples, as a short clause.

    "geo topology mismatch on outMesh (cfg 0)" named nothing: a 2-cell diagonal
    disagreement and a 7% backend divergence read identically. (Measured on the
    shipped voxelize bundle: interp 546 faces vs compiled 510, 91 vs 85 cubes.)
    Phrasing mirrors :func:`_count_mismatch_reason` -- deliberately NOT shared with
    it: the two data shapes have nothing in common and there are only two sites.

    Mesh ``topo`` is ``(counts, connects, color_sets)``; a curve/surface ``topo``
    is a degree/form/knots tuple, which is named by POSITION instead so this never
    raises on a non-mesh kind."""
    mesh_like = (len(a) == 3 and len(b) == 3
                 and all(isinstance(t[0], tuple) and isinstance(t[1], tuple)
                         for t in (a, b)))
    if not mesh_like:
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return ("topology element %d differs (interp %.60s vs compiled "
                        "%.60s)" % (i, repr(x), repr(y)))
        return ("topology tuples differ in length (interp %d vs compiled %d "
                "elements)" % (len(a), len(b)))

    ca, cb = a[0], b[0]
    if len(ca) != len(cb):
        return ("vertex/face COUNT differs: interp %d faces / %d connects vs "
                "compiled %d / %d (%+d faces)"
                % (len(ca), len(a[1]), len(cb), len(b[1]), len(cb) - len(ca)))
    for i, (x, y) in enumerate(zip(ca, cb)):
        if x != y:
            return ("face-size list differs at face %d (interp %d vs compiled %d)"
                    % (i, x, y))
    if a[1] != b[1]:
        for i, (x, y) in enumerate(zip(a[1], b[1])):
            if x != y:
                return ("connectivity differs at the same counts (%d faces): "
                        "first difference at flat index %d (interp %d vs "
                        "compiled %d)" % (len(ca), i, x, y))
        return ("connectivity differs at the same counts (%d faces): interp %d "
                "connects vs compiled %d" % (len(ca), len(a[1]), len(b[1])))
    if a[2] != b[2]:
        return ("colour sets differ: interp %s vs compiled %s"
                % (list(a[2]) or "none", list(b[2]) or "none"))
    return "topology tuples compare unequal but no element difference was found"


def _dump_geo_mismatch(dirpath, name, cfg, ci, cc):
    """Write both sides' ``pts`` and face-size list to ``dirpath`` for offline
    diagnosis (opt-in via MPYNODE_VERIFY_DUMP). Diagnosis ONLY: the gate's verdict
    is unchanged, because our generators emit in canonical sorted order (ordered
    maxerr == 0 on matching configs), so the ordered compare is already correct --
    "which cells differ" is a question for a throwaway script, not the gate.
    Never raises; the caller returns the SAME failing row either way."""
    import json

    try:
        os.makedirs(dirpath, exist_ok=True)
        for side, comp in (("interp", ci), ("compiled", cc)):
            path = os.path.join(dirpath, "%s_cfg%d_%s.json" % (name, cfg, side))
            # topo[0] is the face-size list on a mesh but a bare degree int on a
            # curve/surface -- keep both writable.
            topo0 = (comp.get("topo") or (None,))[0]
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"pts": list(comp.get("pts") or []),
                           "topo0": (list(topo0)
                                     if isinstance(topo0, (list, tuple))
                                     else topo0)}, fh)
    except Exception:
        pass


def _verify_geo(cmds, bundle_path, spec, kind, deadline=None):
    """Component parity for a geometry generator: rebuild the Python original,
    build the compiled node, drive identical inputs, and compare the geometry
    (topology + every point component) read straight off the output data plug
    via MFn*. NON-VACUOUS: if every sampled config yields EMPTY geometry the
    parity was never exercised, so return a not-run skip rather than a false
    PASS. A topology mismatch for the same inputs is a hard FAIL."""
    import random

    import maya.api.OpenMaya as om2
    import mpynode
    from mpynode.native import compiler as codegen

    tol      = 1e-4
    name     = spec["suggested"]["node_type_name"]
    mpy_type = spec.get("mpy_type") or "mPyMesh"
    info     = codegen._GEO_INFO[kind]
    inputs   = spec.get("inputs") or {}
    roles    = _geo_input_roles(spec.get("compute") or "", kind)

    cmds.file(new=True, force=True)
    if not cmds.pluginInfo(os.path.basename(bundle_path), q=True, loaded=True):
        cmds.loadPlugin(bundle_path)
    random.seed(4242)
    # Generated files for the string inputs a reader node needs (a JSON cube
    # sequence, an .ndio cache); {} for everything else -- see parity_fixtures.
    fixtures  = parity_fixtures(spec)
    scene_ops = builtin_scene_ops(name, 6)

    # Rebuild the Python original from the spec (its geo output attr is intrinsic
    # to the mPy* type -- we add only the user INPUT attrs).
    interp = cmds.createNode(mpy_type)
    w      = mpynode.wrap_node(interp)
    for nm, meta in inputs.items():
        t  = meta.get("type")
        kw = {}
        if meta.get("is_array"):
            kw["is_array"] = True
        if t == "enum":
            kw["enum_names"] = meta.get("enum_names") or None
        w.add_input_attr(nm, t, **kw)
    if (spec.get("init") or "").strip():
        w.set_init_expression(spec["init"])
    w.set_compute_expression(spec["compute"])
    comp         = cmds.createNode(name)
    unregistered = _unregistered_type(cmds, comp, name, tol)
    if unregistered:
        return unregistered

    saw_geom = False
    maxerr   = 0.0
    for cfg in range(_GEO_CFGS):
        _drive_geo_inputs(cmds, (interp, comp), inputs, roles, cfg, random,
                          fixtures=fixtures)
        if scene_ops:
            # Applied LAST so it wins: a random shape set is an EMPTY isosurface
            # for an SDF generator (metaballs never had a comparable config).
            for nd in (interp, comp):
                apply_scene_ops(cmds, nd, scene_ops)
        ci = _read_geo_components(om2, interp, kind, info)
        cc = _read_geo_components(om2, comp, kind, info)
        if ci is None or cc is None:
            # One (or both) built nothing this config; not comparable. If the
            # SIDES DISAGREE on emptiness that is a real divergence, not a skip.
            if (ci is None) != (cc is None):
                return {"ran": True, "pass": False, "maxerr": float("inf"),
                        "tol":    tol,
                        "reason": "geo emptiness mismatch on %s (cfg %d): "
                                  "interp=%s compiled=%s"
                                  % (info["attr"], cfg,
                                     "empty" if ci is None else "built",
                                     "empty" if cc is None else "built")}
            continue
        if ci["topo"] != cc["topo"]:
            dump_dir = os.environ.get("MPYNODE_VERIFY_DUMP")
            if dump_dir:
                _dump_geo_mismatch(dump_dir, name, cfg, ci, cc)
            return {"ran": True, "pass": False, "maxerr": float("inf"),
                    "tol":    tol,
                    "reason": "geo topology mismatch on %s (cfg %d): %s"
                              % (info["attr"], cfg,
                                 _topo_mismatch_detail(ci["topo"], cc["topo"]))}
        # Normals/colors ("attrs") must match in LENGTH first -- a differing
        # count means one side emitted a channel the other dropped (e.g. compiled
        # never wrote normals), which a component loop would silently truncate.
        ai, ac = ci.get("attrs", []), cc.get("attrs", [])
        if len(ai) != len(ac):
            return {"ran": True, "pass": False, "maxerr": float("inf"),
                    "tol":    tol,
                    "reason": "geo normals/colors channel mismatch on %s (cfg %d):"
                              " interp %d comps vs compiled %d"
                              % (info["attr"], cfg, len(ai), len(ac))}
        n = min(len(ci["pts"]), len(cc["pts"]))
        if n:
            saw_geom = True
            for i in range(n):
                d = abs(ci["pts"][i] - cc["pts"][i])
                if d > maxerr:
                    maxerr = d
        for i in range(len(ai)):
            d = abs(ai[i] - ac[i])
            if d > maxerr:
                maxerr = d
    if not saw_geom:
        return {"ran": False, "pass": None, "maxerr": None, "tol": tol,
                "reason": "every sampled config produced EMPTY geometry -- geo "
                          "parity not exercised (build compiled + loaded OK)"}
    passed = maxerr <= tol
    row = {"ran": True, "pass": passed, "maxerr": maxerr,
           "tol": tol, "reason": ""}
    # Gated on the GENERIC verdict here, not the merged one (see the twin call in
    # _verify_one): _merge_authored_test folds an authored-test failure into `pass`
    # afterwards, so gating on that would silence the guard on the very nodes whose
    # authored test is red -- voxelize among them.
    if passed and _timing_enabled():
        row["timing"] = _run_timing(
            cmds, spec, interp, comp,
            lambda: _pull_geo_plug(om2, interp, info["attr"]),
            lambda: _pull_geo_plug(om2, comp, info["attr"]),
            inputs, deadline)
    return row


# ---------------------------------------------------------------------------
# Main-thread verify bridge (for GUI callers)
# ---------------------------------------------------------------------------


def main_thread_verify_fn(maya=_MAYA_DEFAULT, run_authored_tests=True):
    """Return a ``verify_fn`` that runs the default parity check ON MAYA'S MAIN
    THREAD -- the correct thing for a GUI caller to pass to ``compile_plugin`` /
    ``CompileController.start``.

    ``compile_plugin`` calls ``verify_fn(bundle_path, rows)`` on its WORKER
    thread, but ``_default_verify`` mutates the Maya scene (loadPlugin, file new,
    polySphere, createNode, setAttr/getAttr) and Maya's API is NOT thread-safe
    (design "threading spine", step 6). This factory's closure marshals that work
    onto Maya's main thread via ``maya.utils.executeInMainThreadWithResult``,
    which blocks the worker until the main thread returns the result.

    Import-safe: ``maya.utils`` is imported lazily INSIDE the closure (never at
    module top), and if it is unavailable (headless python3) the closure falls
    back to calling ``_default_verify`` directly -- which itself degrades to
    per-node "verify skipped (no Maya runtime)" rows. So it is safe to pass
    unconditionally.
    """

    def _verify(bundle_path, rows):
        try:
            import maya.utils as _mutils
        except Exception:
            # No Maya runtime (headless) -- _default_verify degrades gracefully.
            return _default_verify(bundle_path, rows, maya=maya,
                                   run_authored_tests=run_authored_tests)
        return _mutils.executeInMainThreadWithResult(
            lambda: _default_verify(bundle_path, rows, maya=maya,
                                    run_authored_tests=run_authored_tests))

    return _verify


# ---------------------------------------------------------------------------
# Subprocess verify (scene-safe -- the verify's file(new) hits a throwaway
# process, NEVER the caller's live Maya scene)
# ---------------------------------------------------------------------------


_VERIFY_WORKER_CODE = (
    "import mpynode.native.toolchain.verify as _c; _c._verify_worker_main()"
)


def _skip_rows(rows, reason):
    """Build a per-row 'verify skipped' result dict (the verify_fn contract)."""
    out = {}
    for r in rows or []:
        try:
            out[r["type_name"]] = {
                "ran": False, "pass": None, "maxerr": None, "tol": None,
                "reason": reason,
            }
        except Exception:
            pass
    return out


def _mayapy_for(maya):
    """Resolve the ``mayapy`` executable from a Maya install dir, cross-platform.

    Thin wrapper over :func:`native.toolchain.mayapy_path` (kept for callers/
    tests that reference this name).
    """
    return toolchain.mayapy_path(maya)


def _scripts_root():
    """The ``scripts/`` dir (PYTHONPATH root for ``mpynode``) and the project
    root (which holds ``plug-ins/``), derived from THIS file's location:
    ``<root>/scripts/mpynode/native/toolchain/verify.py``."""
    toolchain_dir = os.path.dirname(os.path.abspath(__file__))
    native_dir    = os.path.dirname(toolchain_dir)
    mpynode_dir   = os.path.dirname(native_dir)
    scripts_dir   = os.path.dirname(mpynode_dir)
    root_dir      = os.path.dirname(scripts_dir)
    return scripts_dir, root_dir


def _worker_cwd(env):
    """Where the verify worker runs: the payload's own (temp) directory.

    ``mayapy -c`` puts the CWD on ``sys.path``, and Maya then executes any
    ``userSetup.py`` it finds there as ``./userSetup.py`` -- with the repo root
    as cwd (every tool and harness runs from it) that is the repo's own
    userSetup.py, which dies on ``__file__`` and ABORTS the rest of the startup
    chain. MEASURED 2026-09-08: the same fileTexture parity read 0.023 from the
    worker and 3e-7 in-process, because the aborted chain never activated the
    site-packages that supply PIL and the interpreted decode fell back to
    MImage. A neutral cwd keeps the worker's environment the caller's."""
    payload = (env or {}).get("MPYNODE_VERIFY_PAYLOAD")
    d       = os.path.dirname(payload) if payload else None
    return d if d and os.path.isdir(d) else None


def _default_verify_runner(argv, env, timeout):
    """Spawn the verify worker; returns the process return code. The worker
    writes its result JSON to ``env['MPYNODE_VERIFY_RESULT']`` -- this runner
    does not parse stdout. Runs in :func:`_worker_cwd`, never the caller's cwd."""
    import subprocess

    proc = subprocess.run(argv, env=env, timeout=timeout, cwd=_worker_cwd(env),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode


def _run_subprocess_verify(bundle_path, rows, *, maya=_MAYA_DEFAULT, runner=None,
                           timeout=600, run_authored_tests=True):
    """Run the parity verify in a separate mayapy process. Returns the same
    ``{type_name: {ran,pass,maxerr,tol,reason}}`` dict as ``_default_verify``.
    NEVER raises -- any failure degrades to per-node 'verify skipped' rows so a
    broken verify can never fail (or block) the build, and never touches the
    caller's scene."""
    import json
    import tempfile

    rows = rows or []
    if not rows:
        return {}

    runner = runner or _default_verify_runner
    tmpdir = None
    try:
        tmpdir       = tempfile.mkdtemp(prefix="mpynode_verify_")
        payload_path = os.path.join(tmpdir, "payload.json")
        result_path  = os.path.join(tmpdir, "result.json")

        # Only ship what the worker needs: bundle, (type_name, spec) per row,
        # and whether to run the authored @maya_test(s) inside the worker.
        payload = {
            "bundle_path": bundle_path,
            "maya": maya,
            "run_authored_tests": bool(run_authored_tests),
            "rows": [{"type_name": r["type_name"], "spec": r.get("spec")}
                     for r in rows],
        }
        with open(payload_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, default=str)

        scripts_dir, root_dir = _scripts_root()
        env = dict(os.environ)
        # Make the subprocess import THIS mpynode + find the api plugins, and
        # tell the worker where to read/write.
        cur_pp            = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = scripts_dir + (os.pathsep + cur_pp if cur_pp else "")
        cur_pi            = env.get("MAYA_PLUG_IN_PATH", "")
        plugins_dir       = os.path.join(root_dir, "plug-ins")
        env["MAYA_PLUG_IN_PATH"] = plugins_dir + (
            os.pathsep + cur_pi if cur_pi else "")
        env["MPYNODE_VERIFY_PAYLOAD"] = payload_path
        env["MPYNODE_VERIFY_RESULT"]  = result_path
        # Avoid a Maya-version mismatch when a different-version mayapy is
        # spawned from the current session.
        for v in ("MAYA_LOCATION", "PYTHONHOME"):
            env.pop(v, None)
        # A mis-compiled bundle can SEGFAULT this child mayapy. Disable Autodesk's
        # crash reporter (CER/CIP) so a sandboxed child crash never pops a "Maya
        # closed unexpectedly" dialog; a no-result run is already a SKIP (#60).
        env.setdefault("MAYA_DISABLE_CER", "1")
        env.setdefault("MAYA_DISABLE_CIP", "1")

        argv = [_mayapy_for(maya), "-c", _VERIFY_WORKER_CODE]
        try:
            runner(argv, env, timeout)
        except Exception as exc:
            return _skip_rows(rows, "subprocess verify failed to run: %s" % exc)

        if not os.path.isfile(result_path):
            return _skip_rows(
                rows, "subprocess verify produced no result (the verify "
                      "process may have crashed)")
        try:
            with open(result_path, encoding="utf-8") as fh:
                res = json.load(fh)
        except Exception as exc:
            return _skip_rows(
                rows, "subprocess verify result unreadable: %s" % exc)

        if not isinstance(res, dict):
            return _skip_rows(rows, "subprocess verify result malformed")
        # Backfill any rows the worker did not report (defensive).
        for r in rows:
            res.setdefault(r["type_name"], {
                "ran": False, "pass": None, "maxerr": None, "tol": None,
                "reason": "subprocess verify did not report this node",
            })
        return res
    except Exception as exc:
        return _skip_rows(rows, "subprocess verify error: %s" % exc)
    finally:
        if tmpdir is not None:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


def subprocess_verify_fn(maya=_MAYA_DEFAULT, runner=None, timeout=600,
                         run_authored_tests=True):
    """Return a ``verify_fn`` that runs the parity check in a SEPARATE mayapy
    process -- the scene-safe replacement for ``main_thread_verify_fn``.

    ``_default_verify`` calls ``cmds.file(new=True, force=True)`` to build a
    clean test scene; run in-process (even marshalled to the main thread) that
    WIPES the user's live session. This factory's closure ships the verify into
    a throwaway ``maya.standalone`` process whose ``file(new)`` only affects that
    process, so the caller's scene is never touched while the parity guarantee is
    kept.

    Contract matches ``main_thread_verify_fn``: ``verify_fn(bundle_path, rows)``
    -> ``{type_name: {ran,pass,maxerr,tol,reason}}``; NEVER raises; degrades to
    'verify skipped' rows when no subprocess can run. ``runner`` is injectable
    for tests (default spawns ``mayapy``)."""

    def _verify(bundle_path, rows):
        return _run_subprocess_verify(bundle_path, rows, maya=maya,
                                      runner=runner, timeout=timeout,
                                      run_authored_tests=run_authored_tests)

    return _verify


def _verify_worker_run(payload, init_maya=True, verify_impl=None):
    """The body the subprocess runs: (optionally) init maya.standalone + load
    the mpynode api plugins, then run the parity verify over the payload rows.
    ``init_maya`` / ``verify_impl`` are injectable for headless unit tests."""
    if init_maya:
        try:
            import maya.standalone
            maya.standalone.initialize()
        except Exception:
            pass
        try:
            import maya.cmds as _cmds
            _load_python_plugins(_cmds)
        except Exception:
            pass
    impl = verify_impl or _default_verify
    return impl(payload["bundle_path"], payload.get("rows") or [],
                maya=payload.get("maya", _MAYA_DEFAULT),
                run_authored_tests=payload.get("run_authored_tests", True))


def _verify_worker_main():
    """ENTRY POINT executed inside the mayapy verify subprocess (via ``-c``).
    Reads the payload + result paths from the environment, runs the verify, and
    writes the result JSON. Never lets an exception escape (a crash would just
    leave no result file, which the parent reads as a skip)."""
    import json

    payload_path = os.environ.get("MPYNODE_VERIFY_PAYLOAD", "")
    result_path  = os.environ.get("MPYNODE_VERIFY_RESULT", "")
    out          = {}
    payload      = {}
    try:
        with open(payload_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        out = _verify_worker_run(payload)
    except Exception as exc:
        for r in (payload.get("rows") or []):
            try:
                out[r["type_name"]] = {
                    "ran": False, "pass": None, "maxerr": None, "tol": None,
                    "reason": "verify worker error: %s" % exc,
                }
            except Exception:
                pass
    try:
        # Atomic write (tmp + os.replace) so a timeout/SIGKILL mid-write can't
        # leave the parent a torn file it would misreport as 'unreadable'.
        tmp = "%s.tmp-%d" % (result_path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(out, fh, default=str)
        os.replace(tmp, result_path)
    except Exception:
        pass
