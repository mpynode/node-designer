"""Orchestrate N specs -> ported + cached + compiled + verified native plugin.

This is the engine behind the Node Designer's "Compile to native plugin..."
action. It glues the existing pieces together:

  port_cache (content-addressed .cpp cache)  ->  porter.port_node (AI port +
  compile fix-loop on a cache miss)  ->  bundler.assemble (namespace + link
  every node into ONE .bundle)  ->  an optional in-Maya parity verify  ->  a
  manifest.json build receipt.

Contract (the "manifest seam"): the engine is contracted on
``(list[spec], options) -> (bundle, manifest)``, NOT on "scene selection". The
selection -> spec step (``spec_extractor.extract_spec`` over selected nodes) is
a thin adapter the UI layers on top; a future "plugin project" rebuild calls the
SAME engine with specs re-extracted from a saved manifest.

Qt-free + import-safe under plain ``python3`` -- there is NO ``import maya`` at
module top. The default parity verify lazily imports ``maya.utils`` /
``maya.cmds`` INSIDE the function, so this module imports (and most of it runs)
headlessly; only the default verify needs a Maya runtime. Progress is reported
through a plain ``progress_cb`` callback, never a Qt signal -- the dialog adapts
the callback to a queued Qt signal itself.

Progress events
---------------
``progress_cb(event: dict)`` is called at every state change. The event dict has
a STABLE vocabulary (the compile dialog reads these keys):

  * ``stage``  : one of ``"preflight" | "portability" | "cache" | "port" |
                 "assemble" | "verify" | "log" | "done"``.
  * ``node``   : the node's type_name (str), or ``None`` for plugin-wide stages.
  * ``status`` : one of ``"start" | "hit" | "miss" | "ok" | "fail" | "skip" |
                 "abort" | "line"``.
  * ``detail`` : a short human-readable string (may be "").  For a
                 ``stage="log", status="line"`` event it is ONE raw line of
                 compiler/linker output (the dialog appends these to its live
                 log window); ``node`` tags which node's port emitted it, or is
                 ``None`` for the plugin-wide assemble/link.
  * ``i``      : 1-based index of the current node (0 for plugin-wide events).
  * ``n``      : total node count for the run.

Threading
---------
``compile_plugin`` is a SYNCHRONOUS engine; it runs everything on the calling
thread and fires ``progress_cb`` on that same thread. ``CompileController``
wraps it in a daemon ``threading.Thread`` (mirroring
``ui/llm/cli_base.BaseCliClient``): there, ``progress_cb`` fires on the WORKER
thread, so a GUI adapter MUST marshal each event onto the Qt thread (e.g. via a
queued Qt ``Signal``) before touching any widget. The slow middle (port +
clang++ link) touches no Maya API; only the default verify does, and it runs on
the caller's thread -- in the app the caller marshals it to Maya's main thread
with ``maya.utils.executeInMainThreadWithResult``.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
import traceback

from mpynode.native.compiler import bundler
from mpynode.native.compiler import emit_vp2_override
from mpynode.native.compiler.errors import UnsupportedSpec
from mpynode.native.toolchain import port_cache
from mpynode.native.ai import porter
from mpynode.native.ai import optimizer_live
from mpynode.native.ai import prompt as _prompt
from mpynode.native.toolchain import toolchain
from mpynode.native.toolchain import typeid_registry
# Aliased: compile_plugin()'s boolean `verify=` param would otherwise SHADOW this
# module inside the function body ('bool' has no attribute _default_verify).
from mpynode.native.toolchain import verify as _verify_mod
from mpynode.native.toolchain import stage_report as _stage_report

_MAYA_DEFAULT = toolchain.preferred_maya_dir()

# manifest.json schema revision (additive fields gate on this for scope B).
MANIFEST_VERSION = 1


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _emit(progress_cb, stage, node, status, detail="", i=0, n=0):
    """Fire ``progress_cb`` with one stable-vocab event (never raises)."""
    if progress_cb is None:
        return
    try:
        progress_cb({
            "stage":  stage,
            "node":   node,
            "status": status,
            "detail": detail,
            "i":      i,
            "n":      n,
        })
    except Exception:
        # A misbehaving UI callback must never break the build.
        pass


def _make_log_cb(progress_cb, node, i, n):
    """A ``log_cb(line)`` that forwards each compiler output line as a
    ``stage='log', status='line'`` progress event so the dialog can stream it.

    Returns ``None`` when ``progress_cb`` is ``None`` -- nothing is listening, so
    the porter/bundler get no callback (the streaming pipe still drains, but no
    per-line work is done). ``node`` is the type_name for a per-node port, or
    ``None`` for a plugin-wide (assemble) stage; ``i``/``n`` mirror the node
    index/total of the surrounding stage events.
    """
    if progress_cb is None:
        return None

    def _cb(line):
        _emit(progress_cb, "log", node, "line", line, i, n)

    return _cb


def _make_port_log_cb(progress_cb, node, i, n, log_path):
    """A ``log_cb(line)`` that streams a port's live output to the UI AND tees it
    to a durable per-node ``compile.log``.

    Unlike ``_make_log_cb`` this ALWAYS returns a callback (even headless with no
    ``progress_cb``) so the on-disk log is written regardless -- it captures the
    porter's streamed chain-of-thought / tool activity (claude_cli stream-json)
    plus every compiler line, which is exactly the "internal discussion the AI
    agent had to generate a valid .cpp" an audit wants. Append-per-line keeps it
    crash-durable during a multi-minute port; file errors never break the build."""
    def _cb(line):
        if progress_cb is not None:
            _emit(progress_cb, "log", node, "line", line, i, n)
        if log_path:
            try:
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(line if str(line).endswith("\n") else str(line) + "\n")
            except Exception:
                pass

    return _cb


def _cancelled(cancel_event):
    return bool(cancel_event is not None and cancel_event.is_set())


def _preflight_message(headline, problems):
    """Compose an actionable multi-line pre-flight failure message.

    ``headline`` is the one-line summary; ``problems`` are the specific,
    fixable issues (each shown as a bullet). Surfaced verbatim in the compile
    dialog's failure box and status line, so it must read for a human.
    """
    lines = [str(headline)]
    for p in (problems or []):
        lines.append("  - %s" % p)
    return "\n".join(lines)


def _opt_int(value):
    """An OptimizeResult count as an int; 0 for anything that is not one (a
    test fake's attribute, None from an engine that recorded none)."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _node_needs_llm(spec):
    """True if porting this spec will actually invoke the LLM -- i.e. codegen
    emits an AI PORT region rather than the full compute.

    A node that lowers DETERMINISTICALLY (geo I/O, mPyTransform, mPyFile, any
    pure-numeric body the transpiler handles) never calls ``complete_fn`` in
    ``porter.port_node`` (see its ``PORT_BEGIN not in skeleton`` early-return),
    so it needs NO reachable AI provider. Used to keep the provider pre-flight
    from blocking such a build. On any codegen error (out-of-scope spec, etc.)
    it conservatively returns True, so the normal port path still surfaces the
    error / requires a provider -- preserving the prior fail-fast behavior.
    """
    try:
        from mpynode.native import compiler as codegen

        skeleton = codegen.generate_cpp(spec, for_port=True)
        return codegen.PORT_BEGIN in skeleton
    except Exception:
        return True


# The framework node types the MPyNode plugins themselves register. A COMPILED
# node must NEVER take one of these names: registering "mPyNode"/"mPyIkSolver"
# from a generated bundle would shadow the real framework type Maya already
# knows, breaking every existing scene. Static (no ``import maya`` at top) and
# compared case-insensitively.
RESERVED_NODE_TYPE_NAMES = frozenset(n.lower() for n in (
    "mPyNode", "mPyMesh", "mPyFile", "mPyDeformer", "mPyLocator",
    "mPyTransform", "mPyConstraint", "mPyIkSolver", "mPyBlendShape",
    "mPySkinCluster", "mPyNurbsCurve", "mPyNurbsSurface",
))


def _type_name_for(spec):
    """The sanitized native node-type name for a spec.

    Mirrors what ``porter.port_node`` will use: it runs
    ``porter.apply_type_name(spec, suggested.node_type_name)`` which sanitizes
    the name in place. We apply it here too so the cache key, the out-dir, the
    bundler pair, and the manifest all agree on ONE name.
    """
    suggested = (spec or {}).get("suggested", {}) or {}
    raw       = suggested.get("node_type_name")
    porter.apply_type_name(spec, raw)
    return spec["suggested"]["node_type_name"]


def _resolve_provider_model(provider, model):
    """Resolve (provider, model), reading live config ONLY for None values.

    Importing config is deferred to here so a caller that passes BOTH explicit
    values never imports ``ui.llm.config`` (and never touches preferences /
    Maya). This keeps the headless path config-free.
    """
    if provider is not None and model is not None:
        return provider, model
    from mpynode.ui.llm import config as _config

    if provider is None:
        provider = _config.get_provider()
    if model is None:
        model = _config.get_model(provider)
    return provider, model


# ---------------------------------------------------------------------------
# Synchronous engine
# ---------------------------------------------------------------------------


def _metadata_defaults():
    """Global metadata defaults from Node Designer preferences, or ``{}``.

    Moved to ``metadata_registry.prefs_defaults`` so the .py bake reads the same
    defaults this compile does -- otherwise a node with a blank license would
    compile with the studio default and bake without it."""
    from mpynode._common.lifecycle import metadata_registry as md

    return md.prefs_defaults()


def _merge_metadata_defaults_into_specs(specs, defaults):
    """Merge global metadata ``defaults`` into each spec: an empty per-node field
    falls back to the default. Sets ``spec['metadata']`` only when the merged
    result is non-empty (cache-stable otherwise). Mutates ``specs`` in place;
    pure given ``(specs, defaults)``."""
    from mpynode._common.lifecycle import metadata_registry as md

    for spec in specs:
        if not isinstance(spec, dict):
            continue
        merged = md.merge_metadata(spec.get("metadata"), defaults)
        if md.is_empty(merged):
            spec.pop("metadata", None)
        else:
            spec["metadata"] = merged


def _apply_persistent_policy(specs, bake_persistent):
    """Apply the persistent-bake decision to ``specs`` IN PLACE.

    Each spec may carry its OWN ``bake_persistent`` override (stamped by the
    compile dialog per node, or by ``compile_from_mpn_paths`` per ``.mpn`` file);
    it WINS over the global ``bake_persistent`` default. When the effective
    decision is False, the spec's ``variables`` (the persistent stored-var
    summaries) are dropped so they are NOT baked into the generated C++ -- a
    "vanilla" node.

    The per-spec key is POPPED after it is consumed so it never reaches the
    ``port_cache`` key: the bake decision is already reflected there by
    ``variables`` being ``{}`` or not, so leaving the key in would needlessly
    fork the cache for two builds that produce identical C++.
    """
    for s in specs:
        keep = s.pop("bake_persistent", bake_persistent)
        # Only EMPTY an existing variables dict -- never ADD the key to a spec
        # that lacked it, so a key-absent spec keeps a cache key identical to
        # its key-absent twin.
        if not keep and "variables" in s:
            s["variables"] = {}


def compile_from_mpn_paths(paths, plugin_name, out_dir, *, trusted=True,
                           **options):
    """Compile a list of external ``.mpn`` files into ONE native plugin, WITHOUT
    creating any scene nodes.

    Loads each ``.mpn`` (``mpn_io.load_mpn``), adapts it to a porter spec
    (``mpn_spec_adapter.spec_from_mpn_payload`` -- pure, no live node), then feeds
    the SAME scene-free engine ``compile_plugin``. ``**options`` are forwarded
    verbatim to ``compile_plugin`` (e.g. ``strict``, ``verify``, ``provider``,
    ``model``, and the new ``bake_persistent``).

    Each entry in ``paths`` is either a plain path string OR a
    ``(path, bake_persistent)`` tuple. A tuple flags THAT file's persistent data
    per-file: its ``bake_persistent`` is stamped onto the spec (the engine's
    per-spec override, which wins over the global ``bake_persistent`` in
    ``**options``). A plain string falls back to the global default.

    ``trusted`` (default True) is passed to ``load_mpn`` so a pickle-bearing
    ``.mpn`` does not fail closed in a headless/batch context. NOTE: a malicious
    ``.mpn`` can execute code on load via pickle -- only compile ``.mpn`` files
    you trust (same trust model as importing one). The adapter itself never
    decodes pickle; it works off the already-decoded payload.

    The imports of ``mpn_io`` / ``mpn_spec_adapter`` are LAZY (inside this
    function) so this module keeps its no-``import maya``-at-top guarantee.
    """
    from mpynode._common.io import mpn_io
    from mpynode.native.spec import mpn_spec_adapter

    specs = []
    for entry in paths:
        if isinstance(entry, (tuple, list)):
            # (path,) or (path, bake): always take the inner path; bake only
            # when a second element is present (else fall back to the global).
            path = entry[0]
            bake = entry[1] if len(entry) >= 2 else None
        else:
            path, bake = entry, None
        data = mpn_io.load_mpn(path, trusted=trusted)
        spec = mpn_spec_adapter.spec_from_mpn_payload(data)
        if bake is not None:
            spec["bake_persistent"] = bool(bake)
        specs.append(spec)
    return compile_plugin(specs, plugin_name, out_dir, **options)


def compile_plugin_multi(specs, plugin_name, out_dir, targets, *,
                         verify_fn_for=None, progress_cb=None,
                         cancel_event=None, **options):
    """Compile the SAME ``specs`` once per Maya version in ``targets``.

    Each target is built against THAT version's devkit (``maya=target["root"]``)
    into its OWN ``out_dir/<label>/`` subfolder, and (when verifying) parity-
    checked in that version's ``mayapy`` -- so the produced ``.bundle``/``.mll``
    is ABI-correct for the version it lives under. ``targets`` is the
    ``toolchain.discover_maya_installs`` shape (each a dict with ``label`` +
    ``root``).

    Robustness:
      * the spec list is DEEP-COPIED per version, so ``compile_plugin``'s
        in-place mutations (metadata merge, ``bake_persistent`` strip, type-name
        sanitize) of one build never leak into the next;
      * a per-version failure (or even an engine exception) is recorded and the
        loop CONTINUES -- a missing/incompatible devkit for one version must not
        sink the others;
      * ``cancel_event`` is checked before each version so Cancel stops promptly.

    ``verify_fn_for(root)`` -- if given -- returns the verify_fn for that
    version (the dialog passes ``subprocess_verify_fn(maya=root)``); otherwise
    any ``options["verify_fn"]`` is used as-is for every version.

    Returns ``{"ok", "multi": True, "plugin_name", "out_dir", "cancelled",
    "errors": [str], "results": [{"label", "root", "out_dir",
    "result": <compile_plugin dict>}]}`` where ``ok`` is True only if EVERY
    requested version was reached AND built ok (a cancel between versions =>
    ``ok`` False, ``cancelled`` True). ``errors`` aggregates the per-version
    failure summaries (+ a cancel note); it is always present (possibly empty).
    """
    import copy as _copy

    n       = len(targets)
    results = []
    # maya/verify_fn are set per-version below; never let a caller's value collide.
    base_opts = dict(options)
    base_opts.pop("maya", None)
    base_opts.pop("verify_fn", None)

    # Each per-version compile_plugin emits its OWN terminal "done". Swallow those
    # so the consumer sees exactly ONE "done" (the outer one below) and is not
    # prematurely finished after the first version. Every other inner event still
    # flows through for the live narration.
    def _inner_cb(ev):
        if progress_cb is None:
            return
        if isinstance(ev, dict) and ev.get("stage") == "done":
            return
        progress_cb(ev)

    cancelled = False
    for i, target in enumerate(targets):
        if _cancelled(cancel_event):
            cancelled = True
            break
        label = target.get("label") or str(target.get("root"))
        root  = target.get("root")
        _emit(progress_cb, "version", label, "start",
              "Compiling %s (%d/%d)" % (label, i + 1, n), i, n)
        sub_out = os.path.join(out_dir, label)
        specs_i = _copy.deepcopy(specs)
        if verify_fn_for is not None:
            vf = verify_fn_for(root)
        else:
            vf = options.get("verify_fn")
        try:
            res = compile_plugin(specs_i, plugin_name, sub_out,
                                 maya=root, verify_fn=vf,
                                 progress_cb=_inner_cb,
                                 cancel_event=cancel_event, **base_opts)
        except UnsupportedSpec as exc:
            # A REFUSAL, not a crash. ``compile_plugin`` consumes every
            # porter-scope UnsupportedSpec inside its per-node loop, so the only
            # one that escapes it is a hard "cannot be built here" -- today the
            # generation-time Qt gate in ``bundler.assemble`` (Windows, devkit Qt
            # headers unextracted), which already carries an actionable message
            # naming MPYNODE_QT_INCLUDE. Framing that as "build crashed" turns a
            # clean answer into an apparent bug, so the reason is passed through.
            res = {
                "ok": False, "bundle_path": None, "manifest_path": None,
                "plugin_name": plugin_name, "nodes": [],
                # No label prefix: both consumers already carry it (the
                # aggregate below prefixes "<label>: ", the dialog renders the
                # sub-result under its own version row).
                "errors": ["build refused: %s" % exc],
                "strict": base_opts.get("strict", True),
            }
        except Exception as exc:  # one version's crash must not abort the rest
            res = {
                "ok": False, "bundle_path": None, "manifest_path": None,
                "plugin_name": plugin_name, "nodes": [],
                "errors": ["%s build crashed: %s" % (label, exc)],
                "strict": base_opts.get("strict", True),
            }
        _emit(progress_cb, "version", label,
              "ok" if res.get("ok") else "fail",
              "%s -> %s" % (label, sub_out), i, n)
        results.append({"label": label, "root": root,
                        "out_dir": sub_out, "result": res})

    n_ok = sum(1 for r in results if r["result"].get("ok"))
    # ok ONLY if EVERY requested version was reached AND succeeded. ``len(results)
    # == n`` is what stops a cancel-between-versions being hidden as success.
    ok = (bool(targets) and not cancelled and len(results) == n
          and all(r["result"].get("ok") for r in results))
    # Aggregate a top-level errors list so success / per-version-failure /
    # cancelled / crash all return the SAME shape.
    errors = []
    if cancelled:
        errors.append("cancelled after %d/%d version(s)" % (len(results), n))
    for r in results:
        if not r["result"].get("ok"):
            sub_errs = "; ".join(str(e) for e in (r["result"].get("errors") or []))
            errors.append("%s: %s" % (r["label"], sub_errs or "failed"))
    _emit(progress_cb, "done", None, "ok" if ok else "fail",
          "%d/%d version(s) ok" % (n_ok, n), 0, n)
    return {"ok": ok, "multi": True, "plugin_name": plugin_name,
            "out_dir": out_dir, "results": results, "errors": errors,
            "cancelled": cancelled}


# The (c.6) AI optimizer validates each node's .cpp IN ISOLATION against compute
# parity, so it must refuse any node where an unexercised transform could regress:
_SHARED_HELPER_MARKER = "=== MPYNODE SHARED HELPER BEGIN"


def _optimize_skip_reason(cpp_path, spec, *, one_shot=False):
    """Return why a node must NOT be AI-optimized (empty string = safe to try).

    One isolation hazard the compute-parity gate can't catch:
      * a shared followed-import helper block -- ``bundler.assemble`` dedups these
        across nodes by name (first-wins). Optimizing one node's copy in isolation
        could ship another node's UN-validated helper body, or (if the signature
        changed) break the link. Detect the marker in the finalized .cpp and skip.

    Plus, when ``one_shot`` (the run has no tool-using agent), one budget hazard:
    that path cannot edit the file, so the model has to return the WHOLE unit in
    a single reply. Asking for one that provably cannot fit buys a truncation the
    gate rejects -- a spent call and a "nothing beat the baseline" that reads
    exactly like "already fast". Unlike the two above this is NOT a pure function
    of the node: the same .cpp skips or not depending on the path the run takes
    and the configured ceiling. It is the PATH, not the provider kind: a CLI
    provider demoted to the one-shot rewrite has to retype the file too.
    """
    # mPyFile is NO LONGER blanket-skipped. (c.5) runs before this, so the
    # optimizer sees the spliced VP2 override -- and the shared nd_texel it bakes
    # through IS compute-parity covered, because compute() calls the same
    # function. What parity cannot see is the override SURFACE being deleted
    # outright, so optimizer_knowledge._PLUGIN_ANCHORS carries its tokens and a
    # candidate that drops one is rejected as invalid before a compile is spent.
    try:
        with open(cpp_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return ""
    if _SHARED_HELPER_MARKER in text:
        return "shared followed-import helper (cross-node dedup)"
    if one_shot:
        needed = _response_tokens_needed(text)
        cap    = _resolve_optimize_max_tokens()
        if needed > cap:
            return ("too large for a whole-file rewrite -- needs ~%d response "
                    "tokens and the cap is %d. This run has no tool-using "
                    "agent, so the model must retype the ENTIRE file in one "
                    "reply. Raise 'Max response tokens' in Preferences > AI "
                    "Optimization, or make the agent path available (it edits "
                    "the file in place instead of retyping it)" % (needed, cap))
    return ""


def _optimizer_is_one_shot(provider, kind):
    """Will the optimizer have to retype the whole file in one reply?

    ``kind == "api"`` never has a tool-using headless mode, so it always will.
    A CLI provider does -- until ``optimizer_live._make_agent`` DEMOTES it,
    which it does on exactly one pre-flight (``llm_client.check_agent``: binary
    on PATH, a sandbox that nests). Asking that same pre-flight here, about the
    same ``provider`` the caller forwards to ``optimize_surviving``, is what
    keeps the budget gate from disagreeing with the path the run actually takes.

    An unaskable pre-flight reads as one-shot: this module must stay importable
    headless, and "it cannot edit in place" is the conservative answer -- it
    costs at worst a skipped optimization, never a spent 11-minute round.
    """
    if kind == "api":
        return True
    try:
        from mpynode.native.ai import llm_client

        return not llm_client.check_agent(provider).get("ok")
    except Exception:
        return True


def _response_tokens_needed(text):
    """Response tokens the one-shot optimizer needs to return ``text`` whole.

    Shared by the skip gate and the per-node readout so the two can never quote
    different numbers. 3.5 chars/token errs LOW for punctuation-dense C++, so
    the estimate over-asks rather than waving through a unit that will not fit.
    """
    return int(len(text or "") / 3.5 * 1.25)


def _resolve_optimize_max_tokens():
    """The configured API response ceiling, or the shipped default if prefs are
    unreachable -- this module must stay importable headless."""
    try:
        from mpynode.ui import preferences

        return preferences.resolve_optimize_max_tokens()
    except Exception:
        return 64000


def _resolve_ai_assist(ai_assist, optimize):
    """``optimize`` implies ``ai_assist``.

    Stage 3 rewrites a WORKING .cpp for speed; handed a skeleton whose PORT
    region is still empty there is nothing to make faster and nothing that
    compiles. Rather than error on a contradictory pair, resolve it here -- the
    UI shows the implication by checking-and-locking the assist box.
    """
    return bool(ai_assist or optimize)


def _write_stage(out_dir, type_name, stage, text):
    """Persist one durable pipeline artifact under build/stages/<Type>/.

    Best-effort: a build must never fail because its audit trail could not be
    written. Returns the path, or None.
    """
    try:
        d = bundler.stage_dir_for(out_dir, type_name)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, stage + ".cpp")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path
    except OSError:
        return None


def compile_plugin(specs, plugin_name, out_dir, *, strict=True, verify=True,
                   reuse_cache=True, complete_fn=None, verify_fn=None,
                   progress_cb=None, cancel_event=None, provider=None,
                   model=None, registry=None, maya=_MAYA_DEFAULT,
                   bake_persistent=True, optimize=False, ai_assist=True,
                   clean_scratch=True, keep_intermediates=False):
    """Compile a list of specs into ONE native plugin .bundle (+ manifest.json).

    ``specs`` is a list of already-extracted spec dicts (the
    ``spec_extractor.extract_spec`` output shape). Synchronous: runs every step
    on the calling thread and fires ``progress_cb`` there too.

    Steps (design "controller -> bundler bridge"):
      a. resolve ``provider``/``model`` -- ONLY if a value is None (so callers
         can pass both and avoid config/Maya).
      b. FAIL-FAST portability BEFORE any codegen/LLM: a spec whose
         ``portability.portable`` is False (or whose ``blockers`` list is
         non-empty) is never ported -- ``strict`` aborts the whole compile;
         best-effort drops it and records the reason.
      c. per surviving node: cache key from the spec; on a HIT copy the cached
         ``.cpp`` into ``out_dir/<type_name>/`` (no LLM); on a MISS run
         ``porter.port_node`` (the only expensive step) and write the result
         back to the cache atomically.
      c.6. (``optimize`` only) opt-in AI C++ optimizer: rewrite each finalized
         ``.cpp`` for speed, accepting a candidate only if parity still passes AND
         it is measurably faster (else keep the original). Default OFF -> no-op.
         Every round's source is kept under ``build/stages/<Type>/3_optimized/``;
         ``keep_intermediates`` keeps each round's compiled plug-in there too.
      d. ``bundler.assemble`` the surviving ``(type_name, cpp_path)`` pairs once.
      d.1. (``clean_scratch``, default on) delete the build lint -- the per-node
         working dirs and the optimizer's ``_optscratch``. Never ``build/source``
         or ``build/stages``.
      e. (verify only) ``verify_fn`` if given, else the default Maya parity check
         -- a verify FAIL marks the row but is NOT a build failure.
      f. write ``manifest.json`` next to the bundle.

    Returns ``{ok, bundle_path, manifest_path, plugin_name, nodes:[rows],
    errors:[...], strict}``.
    """
    n_total   = len(specs)
    ai_assist = _resolve_ai_assist(ai_assist, optimize)
    provider, model = _resolve_provider_model(provider, model)
    # Start each run with a clean translate-once helper cache so the run is
    # self-contained (the cache otherwise lives for the whole Maya process).
    # Within THIS run a shared helper is still translated once across all nodes.
    porter.reset_helper_memo()
    os.makedirs(out_dir, exist_ok=True)
    # Merge global metadata DEFAULTS into each spec BEFORE the per-node cache key
    # is computed -- metadata is part of the build identity. Best-effort +
    # headless-safe (no defaults -> no spec change).
    _merge_metadata_defaults_into_specs(specs, _metadata_defaults())
    # Compile-side persistent-data toggle. Done HERE (before the per-node cache
    # key) so it flows into BOTH the key AND codegen/porter; a codegen-only flag
    # would serve a baked .cpp for a non-baked build. Per-spec overrides win.
    _apply_persistent_policy(specs, bake_persistent)
    errors = []
    # rows: per-node manifest entries (built up across stages).
    rows = []

    # ---- (a.1) PRE-FLIGHT: can this host actually compile? -----------------
    # A missing C++ toolchain used to surface only as an opaque per-node
    # "[WinError 2] The system cannot find the file specified" -- AFTER the LLM
    # had run and spent tokens. Check compiler + devkit BEFORE any codegen or
    # port. Needed for BOTH a cache hit and a miss (both compile).
    tc = toolchain.check_toolchain(maya)
    if not tc.get("ok"):
        reason = _preflight_message(
            "This computer is not set up to compile native plugins yet.",
            tc.get("problems"))
        _emit(progress_cb, "preflight", None, "fail", reason, 0, n_total)
        errors.append(reason)
        return _result(False, None, None, plugin_name, rows, errors, strict,
                       out_dir, provider, model, progress_cb, write_manifest=True)

    # ---- (a.2) PRE-FLIGHT: do two nodes want the SAME command name? --------
    # ``bundler.assemble`` already treats a duplicate ``registerCommand`` as
    # fatal, but it reads the name out of GENERATED C++ -- so it cannot fire
    # until every node has been ported. A 44-node run spent 83 minutes porting
    # before dying there. The spec already carries the FINAL names (a
    # ``creates=True`` command is uniquified by ``resolve_create_command_names``
    # back at extraction), so the same answer is available now, for free.
    # Fatal regardless of ``strict``, matching the bundler: Maya registers a
    # given command name exactly once, so there is no safe auto-resolution.
    cmd_owners = {}
    for spec in specs:
        # Skip whatever the (b) gate below would drop anyway -- same condition,
        # same field. An unportable node never reaches codegen, so it emits no
        # registerCommand and the bundler never counted it; failing here on a
        # node that was never going to ship would reject builds that succeed
        # today.
        _port = (spec or {}).get("portability") or {}
        if _port.get("portable") is False or (_port.get("blockers") or []):
            continue
        owner = _type_name_for(spec)
        for cmd in ((spec or {}).get("commands") or []):
            cmd_name = (cmd or {}).get("name")
            if cmd_name:
                cmd_owners.setdefault(cmd_name, []).append(owner)
    clashes = sorted((k, v) for k, v in cmd_owners.items() if len(v) > 1)
    if clashes:
        reason = _preflight_message(
            "Two node types want to register the same command name. Rename one "
            "side, or drop it, before compiling them together.",
            ["'%s' is declared by: %s" % (k, ", ".join(v)) for k, v in clashes])
        _emit(progress_cb, "preflight", None, "fail", reason, 0, n_total)
        errors.append(reason)
        return _result(False, None, None, plugin_name, rows, errors, strict,
                       out_dir, provider, model, progress_cb, write_manifest=True)

    # The AI provider is only used on a cache MISS with no injected complete_fn.
    # Check once here (cheap, no tokens) and enforce at the first miss, so a fully
    # cached rebuild never needs an AI configured. With assist declined no node
    # reaches an LLM at all, so an unconfigured provider must not block the build.
    provider_check = None
    if complete_fn is None and ai_assist:
        provider_check = porter.check_provider(provider, model)

    # ---- (b) fail-fast portability + (c) cache/port -----------------------
    surviving = []  # list of (type_name, cpp_path, spec, key, cache_status)
    # Did ANY node in this run need the LLM? Accumulated from the per-node
    # _node_needs_llm below and reported ONCE after the loop.
    any_needs_llm     = False
    seen_type_names   = set()  # enforce unique native type names across the build
    kept_spec_by_type = {}     # type_name -> first spec kept for it (divergence cmp)
    for idx, spec in enumerate(specs, start=1):
        if _cancelled(cancel_event):
            _emit(progress_cb, "port", None, "abort",
                  "cancelled before node %d/%d" % (idx, n_total), idx, n_total)
            errors.append("cancelled after %d/%d nodes" % (idx - 1, n_total))
            return _result(False, None, None, plugin_name, rows, errors, strict,
                           out_dir, provider, model, progress_cb,
                           write_manifest=True)

        type_name = _type_name_for(spec)

        # (b.0) NAME guards -- BEFORE codegen/LLM. Both abort in strict mode and
        # drop+continue best-effort (the mega keeps the good nodes).
        #   (i) reserved: a compiled node may not register a framework type name.
        if type_name.lower() in RESERVED_NODE_TYPE_NAMES:
            reason = ("reserved node-type name %r -- a compiled node may not "
                      "reuse a built-in MPyNode framework type (mPyNode, "
                      "mPyIkSolver, ...); rename the source node" % type_name)
            _emit(progress_cb, "portability", type_name, "fail", reason,
                  idx, n_total)
            rows.append(_drop_row(spec, type_name, "name", reason,
                                  provider, model))
            if strict:
                errors.append("%s %s" % (type_name, reason))
                return _result(False, None, None, plugin_name, rows, errors,
                               strict, out_dir, provider, model, progress_cb,
                               write_manifest=True)
            continue
        #   (ii) same native type name. INSTANCES of one Class legitimately share
        #   a type -- if their code is IDENTICAL, collapse to the first. If it
        #   DIFFERS it is a divergence (Duplicate-then-edit) or a class-name
        #   collision: one type holds ONE code variant, so the others would be
        #   silently mis-compiled. Surface it instead of guessing.
        if type_name in seen_type_names:
            from mpynode.native.spec.divergence import specs_are_identical

            kept = kept_spec_by_type.get(type_name)
            if kept is not None and specs_are_identical(spec, kept):
                _emit(progress_cb, "portability", type_name, "info",
                      "collapsed identical instance %r (Class compiles once)"
                      % spec.get("source_node", ""), idx, n_total)
                continue
            reason = ("diverged instances of node-type %r -- another selected "
                      "node compiles to it with DIFFERENT code; a Class compiles "
                      "to ONE native type. Fork the divergent instance into its "
                      "own Class (or rename the colliding class) before "
                      "compiling" % type_name)
            _emit(progress_cb, "portability", type_name, "fail", reason,
                  idx, n_total)
            rows.append(_drop_row(spec, type_name, "divergence", reason,
                                  provider, model))
            if strict:
                errors.append("%s %s" % (type_name, reason))
                return _result(False, None, None, plugin_name, rows, errors,
                               strict, out_dir, provider, model, progress_cb,
                               write_manifest=True)
            continue
        seen_type_names.add(type_name)
        kept_spec_by_type[type_name] = spec

        # (b) portability gate -- BEFORE codegen/LLM.
        _emit(progress_cb, "portability", type_name, "start", "", idx, n_total)
        port     = spec.get("portability") or {}
        blockers = list(port.get("blockers") or [])
        if port.get("portable") is False or blockers:
            reason = "not portable: " + ("; ".join(blockers) or "blocked")
            _emit(progress_cb, "portability", type_name, "fail", reason,
                  idx, n_total)
            if strict:
                errors.append("%s %s" % (type_name, reason))
                rows.append(_drop_row(spec, type_name, "portability", reason,
                                      provider, model))
                # Strict: abort the whole compile; never port a blocked node.
                return _result(False, None, None, plugin_name, rows, errors,
                               strict, out_dir, provider, model, progress_cb,
                               write_manifest=True)
            # best-effort: drop + record, keep going.
            rows.append(_drop_row(spec, type_name, "portability", reason,
                                  provider, model))
            continue

        # Per-node port scratch lives under build/<type>/ so leftovers never
        # clutter the top level (bundle + companions only); removed after a
        # successful build below.
        node_out_dir = os.path.join(bundler.build_dir_for(out_dir), type_name)
        os.makedirs(node_out_dir, exist_ok=True)
        cpp_dst = os.path.join(node_out_dir, type_name + ".cpp")
        key     = port_cache.cache_key(spec, provider=provider, model=model)

        def _stage_cb(stage, text, _tn=type_name, _i=idx):
            _write_stage(out_dir, _tn, stage, text)
            # An artifact landing on disk is the only unambiguous "this stage
            # finished" signal (port ok/fail cannot tell 1 from 2). ``detail``
            # carries the stage id.
            _emit(progress_cb, "stage", _tn, "ok", stage, _i, n_total)

        # Does finishing this node require the AI? Answers both the cache
        # question below and the preflight one further down.
        needs_llm     = _node_needs_llm(spec)
        any_needs_llm = any_needs_llm or needs_llm

        # (c) cache lookup. A cached .cpp for an LLM-bound node IS AI-authored, so
        # a run whose contract is "no AI touched this" skips the lookup entirely
        # rather than hitting and having to explain the provenance.
        _emit(progress_cb, "cache", type_name, "start", "", idx, n_total)
        use_cache = reuse_cache and (ai_assist or not needs_llm)
        cached    = port_cache.get_path(key) if use_cache else None
        if cached:
            # HIT: copy the cached .cpp into the node out-dir; no LLM, no codegen.
            shutil.copyfile(cached, cpp_dst)
            # No holes in the stage history: re-derive the deterministic skeleton
            # (cheap, no LLM) so build/stages/<Type>/1_transpiled.cpp exists for a
            # cached node too. A codegen change since caching can make this raise
            # -- record it rather than failing an otherwise fine build.
            try:
                # Local import: module-level would be circular.
                from mpynode.native import compiler as _codegen
                _stage_cb("1_transpiled", _codegen.generate_cpp(spec,
                                                                for_port=True))
            except Exception as exc:
                _write_stage(out_dir, type_name, "1_transpiled.NOT_GENERATED",
                             "// %s\n" % exc)
            # For an LLM-bound node the cached .cpp IS the assisted stage --
            # recording only stage 1 would read as "the AI never ran" for a file
            # the AI wrote. A fully-lowered node gets no stage 2. The FILE is
            # written here; the EVENT is held back and marked `_cached`, since the
            # AI ran in some EARLIER run, not this one.
            cached_assist = False
            if needs_llm:
                try:
                    with open(cached, encoding="utf-8") as _fh:
                        # _write_stage swallows OSError and returns None;
                        # announcing regardless would point at a missing file.
                        cached_assist = bool(_write_stage(
                            out_dir, type_name, "2_assisted", _fh.read()))
                except OSError:
                    pass
            _emit(progress_cb, "cache", type_name, "hit",
                  "cache hit %s" % key[:12], idx, n_total)
            if cached_assist:
                _emit(progress_cb, "stage", type_name, "ok",
                      "2_assisted_cached", idx, n_total)
            surviving.append((type_name, cpp_dst, spec, key, "hit"))
            continue

        # MISS: port it. This is the only expensive step.
        _emit(progress_cb, "cache", type_name, "miss",
              "cache miss %s" % key[:12], idx, n_total)

        # AI pre-flight, deferred to the first real port: if this node will invoke
        # the LLM and the provider is unreachable, abort HERE, before any prompt is
        # sent. A DETERMINISTICALLY-lowered node never calls the LLM, so it must
        # NOT be blocked by a missing provider (see _node_needs_llm).
        if (provider_check is not None and not provider_check.get("ok")
                and needs_llm):
            reason = _preflight_message(
                "The AI provider needed to port %r is not reachable."
                % type_name, provider_check.get("problems"))
            _emit(progress_cb, "preflight", type_name, "fail", reason, idx,
                  n_total)
            rows.append(_drop_row(spec, type_name, "preflight", reason,
                                  provider, model))
            errors.append(reason)
            return _result(False, None, None, plugin_name, rows, errors, strict,
                           out_dir, provider, model, progress_cb,
                           write_manifest=True)

        _emit(progress_cb, "port", type_name, "start", "porting", idx, n_total)
        # One durable log per node: the porter's streamed CoT/tool activity AND
        # every compiler line tee into out_dir/<type>/compile.log, so a headless
        # audit keeps the full "how the AI got to a valid .cpp" transcript.
        compile_log_path = os.path.join(node_out_dir, "compile.log")
        port_log_cb = _make_port_log_cb(progress_cb, type_name, idx, n_total,
                                        compile_log_path)
        complete = complete_fn or porter.make_cli_complete_fn(
            cancel_event, log_cb=port_log_cb)
        try:
            r = porter.port_node(spec, node_out_dir, complete_fn=complete,
                                 maya=maya, type_name=type_name,
                                 log_cb=port_log_cb, ai_assist=ai_assist,
                                 stage_cb=_stage_cb)
        except porter.PortCancelled:
            _emit(progress_cb, "port", type_name, "abort", "port cancelled",
                  idx, n_total)
            errors.append("%s port cancelled" % type_name)
            return _result(False, None, None, plugin_name, rows, errors, strict,
                           out_dir, provider, model, progress_cb,
                           write_manifest=True)
        except Exception as exc:
            reason = "port error: %s" % exc
            _emit(progress_cb, "port", type_name, "fail", reason, idx, n_total)
            rows.append(_drop_row(spec, type_name, "port", reason, provider,
                                  model))
            if strict:
                errors.append("%s %s" % (type_name, reason))
                return _result(False, None, None, plugin_name, rows, errors,
                               strict, out_dir, provider, model, progress_cb,
                               write_manifest=True)
            continue

        if r.get("needs_assist"):
            # Not an error -- the node has a deterministic .cpp with its gaps
            # marked; it just cannot be bundled until someone fills them.
            n_regions = r.get("port_regions", 0)
            reason = ("needs AI assist: %d region(s) the transpiler could not "
                      "lower -- baseline C++ written to build/stages/%s/"
                      "1_transpiled.cpp" % (n_regions, type_name))
            _emit(progress_cb, "port", type_name, "assist", reason, idx, n_total)
            rows.append(_drop_row(spec, type_name, "assist", reason, provider,
                                  model))
            if strict:
                errors.append("%s %s" % (type_name, reason))
                return _result(False, None, None, plugin_name, rows, errors,
                               strict, out_dir, provider, model, progress_cb,
                               write_manifest=True)
            continue

        if r.get("ok"):
            # Write the spliced .cpp back to the cache atomically (hit next time).
            try:
                with open(r["cpp"], "r", encoding="utf-8") as fh:
                    cpp_text = fh.read()
                port_cache.put(key, cpp_text, meta={
                    "recipe":    port_cache.PORTER_RECIPE_VERSION,
                    "provider":  provider,
                    "model":     model,
                    "type_name": type_name,
                    "source":    spec.get("source_node"),
                })
            except Exception as exc:
                # A cache-write failure must not fail the build -- but it must
                # not be silent either. An unwritable cache dir costs a full LLM
                # re-port on EVERY later run, and the only symptom used to be a
                # cache that reports "miss" forever.
                _emit(progress_cb, "cache", type_name, "warn",
                      "cache write failed: %s" % exc, idx, n_total)
            # port_node already wrote the .cpp at cpp_dst (out_dir/<name>.cpp).
            cpp_path = r.get("cpp") or cpp_dst
            _emit(progress_cb, "port", type_name, "ok",
                  "ported (%d fix rounds)" % r.get("fix_rounds", 0),
                  idx, n_total)
            surviving.append((type_name, cpp_path, spec, key, "miss"))
        else:
            log_text = r.get("compiler_log") or ""
            tail     = log_text.strip().splitlines()
            reason   = "port failed to compile: %s" % (tail[-1] if tail else "?")
            # Turn a cryptic compiler error (e.g. STL1001) into a plain-English
            # next step appended to the failure.
            hint = toolchain.diagnose_compiler_log(log_text)
            if hint:
                reason = reason + "\n" + hint
            _emit(progress_cb, "port", type_name, "fail", reason, idx, n_total)
            rows.append(_drop_row(spec, type_name, "port", reason, provider,
                                  model))
            if strict:
                errors.append("%s %s" % (type_name, reason))
                return _result(False, None, None, plugin_name, rows, errors,
                               strict, out_dir, provider, model, progress_cb,
                               write_manifest=True)
            # best-effort: drop + continue.

    if not surviving:
        _emit(progress_cb, "assemble", None, "fail", "no portable nodes", 0,
              n_total)
        errors.append("no portable nodes to assemble")
        return _result(False, None, None, plugin_name, rows, errors, strict,
                       out_dir, provider, model, progress_cb,
                       write_manifest=True)

    if _cancelled(cancel_event):
        _emit(progress_cb, "assemble", None, "abort", "cancelled before assemble",
              0, n_total)
        errors.append("cancelled before assemble")
        return _result(False, None, None, plugin_name, rows, errors, strict,
                       out_dir, provider, model, progress_cb,
                       write_manifest=True)

    # Porting is OVER, so "did the AI have to fill anything?" is now answered.
    # Said here, once per run, because it is the only place that knows it -- a UI
    # cannot infer "assist never ran" from a missing 2_assisted artifact.
    # Narration only: nothing downstream reads it.
    if not any_needs_llm:
        _emit(progress_cb, "port", None, "skip",
              "no node needed AI assist -- every compute lowered "
              "deterministically", 0, n_total)

    # ---- (c.4) port-honesty scan -------------------------------------------
    # What the AI-authored body admits to (PORT_INCOMPLETE markers) and what it
    # emitted despite being told not to (file/process/network/scene I/O).
    # Scanned HERE, before (c.5), because that transform REPLACES the whole PORT
    # region with a marker-stripped nd_texel call (emit_vp2_override), leaving an
    # mPyFile with no markers at all. Measured: fileTexture and gameOfLifeTex
    # shipped real PORT_INCOMPLETE notes the manifest missed for this reason.
    honesty = {}
    for (tn, cpp, spec, key, cache_status) in surviving:
        try:
            with open(cpp, "r", encoding="utf-8") as fh:
                honesty[tn] = _prompt.scan_ported_body(fh.read())
        except OSError:
            honesty[tn] = {"ported": False, "incomplete": [], "io": []}

    # ---- (c.5) VP2 shading-node override injection -------------------------
    # A compiled mPyFile renders in software / Arnold / the swatch (all DG-evaluate
    # outColor), but Viewport 2.0 needs an MPxShadingNodeOverride, which codegen
    # does not emit. Splice one into each texture node's FINALIZED .cpp -- a
    # deterministic post-port transform reusing the cached AI body via a shared
    # nd_texel, so VP2 == compute and no re-port is needed. Best-effort: a failed
    # injection leaves the base .cpp (still renders in software/Arnold).
    # A REFUSED injection used to be silent -- no _emit, nothing in the manifest,
    # nothing in REPORT.md -- so a node that shades flat in the viewport shipped
    # looking exactly like one that works. skip_reason() exists to be reported;
    # report it, on the SAME stage/status pair the two arms below already use so
    # no UI branch has to learn a new stage id.
    vp2_skip = {}
    for (tn, cpp, spec, key, cache_status) in surviving:
        if spec.get("mpy_type") != "mPyFile":
            continue
        try:
            with open(cpp, "r", encoding="utf-8") as fh:
                src = fh.read()
            # A port-cache HIT can serve an ALREADY-injected .cpp, for which
            # skip_reason says "override already present". Without this check
            # that reads as a loud false skip.
            if "MPxShadingNodeOverride" in src:
                continue
            reason = emit_vp2_override.skip_reason(src)
            if not reason:
                new = emit_vp2_override.inject_vp2_override(src, spec)
                if new != src:
                    with open(cpp, "w", encoding="utf-8") as fh:
                        fh.write(new)
                    _emit(progress_cb, "port", tn, "ok",
                          "VP2 viewport override injected", 0, n_total)
            else:
                vp2_skip[tn] = reason
                _emit(progress_cb, "port", tn, "ok",
                      "no VP2 override: %s; Viewport 2.0 shades it a FLAT "
                      "colour (swatch / software / Arnold unaffected)" % reason,
                      0, n_total)
        except Exception as exc:
            vp2_skip[tn] = str(exc)
            _emit(progress_cb, "port", tn, "ok",
                  "VP2 override skipped (%s); renders in software/Arnold" % exc,
                  0, n_total)

    # ---- (c.6) opt-in AI C++ optimizer (post-port, pre-assemble) ----------
    # Ask the AI to rewrite each finalized .cpp for speed. A candidate is accepted
    # ONLY if the pipeline's OWN parity verify still passes AND it benchmarks
    # measurably faster; otherwise the original is kept. Opt-in + default-OFF so a
    # normal build is byte-for-byte unchanged (the gate lives in optimizer_live/
    # optimizer; this is just the seam). Any optimizer error is non-fatal.
    # optimize_summary surfaces the per-node outcome to the UI (#64) instead of a
    # transient log line; always defined so the attach below is safe when off.
    optimize_summary = {}
    any_accepted     = False
    # Per-node record of what the AI actually DID (see optimizer_live), and the
    # run-level verdict derived from it below. A provider that dies at startup
    # every round used to reach here as a normal "kept original" -- or worse, as
    # an accept on byte-identical source that benchmark noise scored 1.15x.
    opt_ai_status = {}
    ai_never_ran  = ""
    if optimize and not _cancelled(cancel_event):
        # Two preflights, one failure shape (emit fail + __status__ + error,
        # and the deterministic build still links). The ruler first: without
        # tools/harness/benchmark_node.py nothing the AI proposed could be
        # timed, and every node would come back "kept original" for a reason
        # that names no cause; there is no point probing the provider then.
        harness_problem = optimizer_live.benchmark_harness_problem()
        prov = ({"ok": False, "problems": [harness_problem]} if harness_problem
                else porter.check_provider(provider, model))
        if not prov.get("ok"):
            reason = _preflight_message(
                "AI optimize was requested but the benchmark harness is missing."
                if harness_problem else
                "AI optimize was requested but the provider is not reachable.",
                prov.get("problems"))
            _emit(progress_cb, "optimize", None, "fail", reason, 0, n_total)
            optimize_summary["__status__"] = reason
            errors.append(reason)
            ai_never_ran = reason
        else:
            # Scene-safe parity: the subprocess verify (throwaway mayapy) never
            # touches the caller's live scene. Authored @maya_tests stay ON: for a
            # node whose generic pointwise parity SKIPS there is otherwise no gate
            # at all, so every candidate is rejected however good it is. A deformer
            # is exactly that (no declared outputs; its work leaves through the
            # native outputGeometry), and verify._merge_authored_test turns that
            # skip back into a real pass/fail.
            opt_verify = verify_fn or _verify_mod.subprocess_verify_fn(maya=maya)
            # Only optimize nodes safe to validate in isolation -- skip mPyFile
            # (VP2 override) and shared-helper nodes, so an optimized node can
            # never ship an un-gated transform or an unvalidated shared helper.
            opt_nodes = []
            # Asked ONCE per run, not per node: it is a property of the machine
            # + provider, and it costs a sandbox probe. Reuses the kind
            # check_provider already resolved, and the SAME provider is handed
            # to optimize_surviving below, so the gate can never disagree with
            # the provider the run actually uses.
            one_shot = _optimizer_is_one_shot(provider, prov.get("kind"))
            for (tn, cpp, spec, _k, _cs) in surviving:
                skip = _optimize_skip_reason(cpp, spec, one_shot=one_shot)
                if skip:
                    _emit(progress_cb, "optimize", None, "skip",
                          "%s skipped: %s" % (tn, skip), 0, n_total)
                    optimize_summary[tn] = {"accepted": False,
                                            "reason": "skipped: %s" % skip}
                    continue
                if one_shot:
                    # Show the ratio even when it FITS: the point is to warn
                    # while there is still headroom, not only once it is gone.
                    try:
                        with open(cpp, "r", encoding="utf-8") as _fh:
                            _need = _response_tokens_needed(_fh.read())
                        _emit(progress_cb, "optimize", None, "info",
                              "%s response budget: %d/%d tokens"
                              % (tn, _need, _resolve_optimize_max_tokens()),
                              0, n_total)
                    except Exception:
                        pass
                opt_nodes.append((tn, cpp, spec))
            try:
                # log_cb carries ONLY the engine's high-level narration (baseline
                # ms, per-round ACCEPT/reject). compile_log_cb carries the noisy
                # per-line streams, so it is FILTERED to the optimizer's own
                # "[optimizer] ..." notes: unfiltered it floods the dialog, but off
                # entirely the only report of a killed AI call reached nothing, so
                # a timeout that fired printed nothing at all.
                opt_res = optimizer_live.optimize_surviving(
                    opt_nodes, out_dir, maya=maya,
                    verify_fn=opt_verify, complete_fn=complete_fn,
                    cancel_event=cancel_event, provider=provider,
                    keep_intermediates = keep_intermediates,
                    status_out         = opt_ai_status,
                    log_cb=lambda m: _emit(progress_cb, "optimize", None, "info",
                                           m, 0, n_total),
                    compile_log_cb=lambda m: (
                        _emit(progress_cb, "optimize", None, "info", m, 0,
                              n_total)
                        if str(m).startswith("[optimizer]") else None))
                for tn, r in (opt_res or {}).items():
                    acc = bool(getattr(r, "accepted", False))
                    spd = getattr(r, "speedup", 1.0)
                    spd = float(spd) if spd is not None else 1.0
                    rsn = getattr(r, "reason", "")
                    # How the adaptive loop ended -- rounds RUN, the cap, why it
                    # stopped -- so the dialog's summary can say it. The engine
                    # has recorded all three since 2026-09-09; a result without
                    # them (a fake, an older engine) reads 0 / "" and the dialog
                    # prints the line it always did.
                    optimize_summary[tn] = {
                        "accepted": acc, "speedup": spd, "reason": rsn,
                        "rounds":      _opt_int(getattr(r, "rounds", 0)),
                        "max_rounds":  _opt_int(getattr(r, "max_rounds", 0)),
                        "stop_reason": str(getattr(r, "stop_reason", "") or ""),
                        "ai": opt_ai_status.get(tn, {})}
                    if acc:
                        any_accepted = True
                        _emit(progress_cb, "optimize", None, "ok",
                              "%s: %.2fx faster" % (tn, spd), 0, n_total)
                    else:
                        _emit(progress_cb, "optimize", None, "ok",
                              "%s: kept original (%s)" % (tn, rsn), 0, n_total)
            except Exception as exc:
                # NON-fatal but never SILENT: emit a fail event so the user sees
                # the optimizer errored, not a mystery "kept original". The
                # un-optimized .cpp still assembles.
                _emit(progress_cb, "optimize", None, "fail",
                      "AI-optimize error (non-fatal): %s" % exc, 0, n_total)
                errors.append("AI-optimize error (non-fatal): %s" % exc)
                optimize_summary["__error__"] = str(exc)
            # (c.6.1) DID the AI actually do anything? A round that fails at
            # startup returns the UNCHANGED source, which then compiles, passes
            # parity (it is the same file) and benchmarks within noise of itself
            # -- so "accept, 1.15x faster" is exactly what a dead provider looks
            # like from here. `candidates` counts rounds that came back with
            # DIFFERENT source; zero of those across every node, with a recorded
            # failure, means the run optimized nothing. Requiring the recorded
            # failure is what keeps an honest "already optimal" answer (no error,
            # no candidate) from being called a fault.
            blocked = sorted(tn for tn, st in opt_ai_status.items()
                             if (st or {}).get("errors"))
            delivered = sum(int((st or {}).get("candidates") or 0)
                            for st in opt_ai_status.values())
            if opt_nodes and blocked and not delivered:
                first = (opt_ai_status[blocked[0]].get("errors") or [""])[0]
                ai_never_ran = (
                    "AI optimize was requested but produced no candidate for "
                    "any of the %d node(s) attempted (%d blocked: %s). First "
                    "failure: %s"
                    % (len(opt_nodes), len(blocked), ", ".join(blocked[:5]),
                       first))
                _emit(progress_cb, "optimize", None, "fail", ai_never_ran, 0,
                      n_total)
                errors.append(ai_never_ran)
                optimize_summary["__status__"] = ai_never_ran

    # Cancel pressed DURING the (possibly multi-minute) optimize step must abort
    # before we commit to the link, not build anyway and offer to load it (#67).
    if _cancelled(cancel_event):
        _emit(progress_cb, "assemble", None, "abort", "cancelled after optimize",
              0, n_total)
        errors.append("cancelled after optimize")
        # Undo any accepted optimize so a later run starts from the deterministic
        # source, not a half-committed optimized .cpp.
        optimizer_live.rollback_preopt(
            [cpp for (_tn, cpp, _s, _k, _cs) in surviving])
        return _result(False, None, None, plugin_name, rows, errors, strict,
                       out_dir, provider, model, progress_cb,
                       write_manifest=True)

    # ---- (d) assemble -----------------------------------------------------
    _emit(progress_cb, "assemble", None, "start",
          "linking %d node(s)" % len(surviving), 0, n_total)
    reg = registry or typeid_registry.TypeIdRegistry()
    # Manual MTypeId pins from each node's metadata, applied BEFORE assemble so
    # the allocator sees them. Ids are derived from the Class otherwise; this is
    # the override for a rare clash with a third-party plugin. An unusable value
    # is ignored by ``pin`` and reported rather than failing the build.
    for (tn, _cpp, spec, _k, _cs) in surviving:
        pinned = ((spec.get("metadata") or {}).get("type_id") or "").strip()
        if pinned and reg.pin(tn, pinned) is None:
            _emit(progress_cb, "typeid", tn, "warn",
                  "ignoring unusable pinned type_id %r (using the derived id)"
                  % pinned, 0, n_total)
    asm_nodes = [(tn, cpp) for (tn, cpp, _s, _k, _cs) in surviving]
    report = bundler.assemble(asm_nodes, plugin_name, out_dir, strict=strict,
                              registry=reg, maya=maya, compile_now=True,
                              log_cb=_make_log_cb(progress_cb, None, 0, n_total))

    # Followed-import helpers that were hoisted into the one shared C++ unit
    # (translate-once / dedup). Surfaced on the result for the GUI/manifest.
    asm_shared    = report.get("shared_helpers") or []
    asm_conflicts = report.get("shared_helper_conflicts") or []

    # A derived id is a hash, so two nodes in one bundle can (rarely) want the same
    # one. The allocator probes forward; say so, because the loser's id then
    # depends on the bundle's contents -- worth pinning if it is saved into a .mb.
    for (cname, wanted, got) in reg.collisions:
        _emit(progress_cb, "typeid", cname, "warn",
              "derived id 0x%08x already taken in this bundle; using 0x%08x "
              "(pin it in Node Info to make it permanent)" % (wanted, got),
              0, n_total)

    # Per-node type_id + build status from assemble's report.
    asm_by_name = {rec["name"]: rec for rec in report.get("nodes", [])}
    for (tn, cpp, spec, key, cache_status) in surviving:
        rec = asm_by_name.get(tn, {})
        # What the shipped C++ admits to, captured at (c.4) from the ARTIFACT, so
        # a cache HIT reports what a fresh port would. Deliberately NOT folded into
        # ``build_status``: that string gates companions, verify and scratch
        # cleanup, so a new value there would skip verify on the neediest nodes.
        scan = honesty.get(tn) or {"ported": False, "incomplete": [], "io": []}
        rows.append({
            "source_node": spec.get("source_node"),
            "type_name":   tn,
            "type_id":     rec.get("id"),
            # pinned / pin-file / derived, with a "+probed" suffix when a hash
            # clash in this bundle pushed it forward -- so a collision is visible
            # in the manifest instead of silently absorbed.
            "type_id_source": reg.sources.get(tn, ""),
            "base":           spec.get("suggested", {}).get("mpx_base", "MPxNode"),
            "spec_hash":      key,
            "port_cache_key": key,
            "cache":          cache_status,
            "build_status":   rec.get("status", "unknown"),
            "build_reason":   rec.get("reason", ""),
            "ported":         scan["ported"],
            "incomplete":     scan["incomplete"],
            "invented_io":    scan["io"],
            # scan's OPTIONAL 4th key (absent when empty -- hence ``.get``):
            # std facilities the PORT region uses with no include for them,
            # i.e. what libc++ accepted on this machine and the MSVC STL will
            # reject. A finding, never a gate. Normally empty on the porter
            # path (porter._splice repairs it at splice time); a .cpp cached
            # before that repair existed is the case this reports.
            "missing_includes": scan.get("includes", []),
            # Why this node got no MPxShadingNodeOverride, "" when it did (or is
            # not an mPyFile). A node with a reason here is CORRECT everywhere
            # the DG evaluates outColor and FLAT in Viewport 2.0 -- the one
            # difference a user cannot otherwise see in the build output.
            "vp2_skip": vp2_skip.get(tn, ""),
            "verify": {"ran": False, "pass": None, "maxerr": None,
                       "tol": None, "reason": ""},
            "spec": spec,
        })
        if scan["incomplete"]:
            _emit(progress_cb, "honesty", tn, "incomplete",
                  "; ".join(scan["incomplete"]), 0, n_total)
        if scan["io"]:
            _emit(progress_cb, "honesty", tn, "io",
                  "; ".join(scan["io"]), 0, n_total)

    bundle_path = report.get("bundle")
    # Honest success (#62): the linker returning ok is not enough -- the artifact
    # must exist on disk. os.path.exists handles a file OR dir bundle.
    bundle_exists = bool(bundle_path) and os.path.exists(bundle_path)
    build_ok      = bool(report.get("ok") and bundle_exists)

    # #66: an AI-optimized candidate can compile + parity-pass in isolation yet
    # still fail the FINAL multi-node link. Fall back to the deterministic .cpp
    # and re-assemble ONCE, so an accepted optimize can never turn a good build
    # into no build at all.
    if not build_ok and any_accepted:
        restored = optimizer_live.rollback_preopt(
            [cpp for (_tn, cpp, _s, _k, _cs) in surviving])
        if restored:
            _emit(progress_cb, "optimize", None, "info",
                  "AI-optimized candidate failed the final link; rebuilding with "
                  "the deterministic C++", 0, n_total)
            errors.append("AI-optimized candidate failed the final link; shipped "
                          "the deterministic build instead")
            optimize_summary["__fallback__"] = (
                "rebuilt deterministic after optimized-candidate link failure")
            report = bundler.assemble(
                asm_nodes, plugin_name, out_dir, strict=strict, registry=reg,
                maya=maya, compile_now=True,
                log_cb=_make_log_cb(progress_cb, None, 0, n_total))
            bundle_path   = report.get("bundle")
            bundle_exists = bool(bundle_path) and os.path.exists(bundle_path)
            build_ok      = bool(report.get("ok") and bundle_exists)
            # The rows above reflect the FIRST (failed) report; refresh them from
            # the deterministic re-assemble so a node that now ships is not left
            # marked compile-failed and dropped from verify/companions (#66).
            asm_shared    = report.get("shared_helpers") or []
            asm_conflicts = report.get("shared_helper_conflicts") or []
            asm_by_name = {arec["name"]: arec
                           for arec in report.get("nodes", [])}
            for row in rows:
                arec = asm_by_name.get(row["type_name"])
                if arec is not None:
                    row["type_id"]      = arec.get("id")
                    row["build_status"] = arec.get("status", "unknown")
                    row["build_reason"] = arec.get("reason", "")

    # The build has committed one way or the other; drop any leftover pre-optimize
    # backups (rollback already consumed the ones it restored).
    if optimize:
        optimizer_live.discard_preopt(
            [cpp for (_tn, cpp, _s, _k, _cs) in surviving])

    if not build_ok:
        reason = report.get("reason") or "assemble failed"
        # A linker that returned success but produced no artifact is a phantom
        # build -- say so explicitly rather than the vague "assemble failed".
        if report.get("ok") and bundle_path and not bundle_exists:
            reason = ("linker reported success but no bundle exists on disk at %s"
                      % bundle_path)
        # Decode a known toolset mismatch (STL1001) into an actionable hint.
        hint = toolchain.diagnose_compiler_log(report.get("stderr"))
        if hint:
            reason = reason + "\n" + hint
        _emit(progress_cb, "assemble", None, "fail", reason, 0, n_total)
        errors.append("assemble: %s" % reason)
        # Note dropped nodes (best-effort).
        for dn in report.get("dropped", []) or []:
            errors.append("dropped: %s" % dn)
        fail_result = _result(False, bundle_path, None, plugin_name, rows, errors,
                              strict, out_dir, provider, model, progress_cb,
                              write_manifest=True)
        if optimize_summary:
            fail_result["optimize"] = optimize_summary
        return fail_result
    for dn in report.get("dropped", []) or []:
        errors.append("dropped: %s" % dn)
    _emit(progress_cb, "assemble", None, "ok",
          "bundle: %s" % os.path.basename(bundle_path), 0, n_total)

    # ---- (d1) clean the per-node working subdirs --------------------------
    # assemble wrote the clean source under build/source/, so the per-node
    # build/<type>/ working folder is redundant clutter. Removed for every node
    # that BUILT; a dropped node's subdir stays for debugging. Guarded to stay
    # under out_dir. ``clean_scratch=False`` keeps the lot.
    _clean_working_subdirs(out_dir, rows, clean_scratch)

    # ---- (e0) command-name gate + per-command report ----------------------
    # Every @maya_command compiles INTO the .bundle as a real MPxCommand, so no
    # sibling <type>_commands.py is written. emit_companions is retained purely as
    # the CROSS-NODE clash gate: command names are one global namespace, and a name
    # on two nodes fails the 2nd registerCommand at load -- which in a merged
    # bundle aborts initializePlugin for the WHOLE plug-in. Only gate nodes whose
    # type ACTUALLY registered: best-effort can drop one while a sibling links.
    companions = []
    built = {r["type_name"] for r in rows
             if r["build_status"] in ("compiled", "transformed")}
    cmd_nodes = [(tn, spec) for (tn, _cpp, spec, _k, _cs) in surviving
                 if tn in built]
    if any((spec or {}).get("commands") for (_tn, spec) in cmd_nodes):
        from mpynode.native.compiler import command_companion
        try:
            companions = command_companion.emit_companions(
                cmd_nodes, plugin_name, out_dir)
        except ValueError as exc:
            # A cross-node command-name clash / invalid name: the .bundle is
            # valid, but the commands can't ship -- surface it, don't abort.
            errors.append("companion: %s" % exc)
            _emit(progress_cb, "assemble", None, "fail",
                  "companion: %s" % exc, 0, n_total)
        else:
            # Nothing is written any more, so the report is built from the specs
            # instead; the dialog still lists every command the bundle registers.
            by_type = {tn: spec for (tn, spec) in cmd_nodes}
            n_cmds  = 0
            for r in rows:
                spec     = by_type.get(r["type_name"])
                cmds_for = (spec or {}).get("commands") or []
                if not cmds_for:
                    continue
                r["commands"] = command_companion.companion_command_summary(
                    (spec or {}).get("methods") or "", commands=cmds_for)
                n_cmds += len(cmds_for)
            if n_cmds:
                _emit(progress_cb, "assemble", None, "ok",
                      "bundled command(s): %d (no companion plug-in)" % n_cmds,
                      0, n_total)

    # ---- (e) verify (build-non-fatal) -------------------------------------
    if verify:
        _emit(progress_cb, "verify", None, "start", "parity check", 0, n_total)
        verify_rows = [r for r in rows
                       if r["build_status"] in ("compiled", "transformed")
                       and r.get("spec") is not None]
        try:
            if verify_fn is not None:
                vres = verify_fn(bundle_path, verify_rows)
            else:
                vres = _verify_mod._default_verify(bundle_path, verify_rows, maya=maya)
        except Exception as exc:
            # Verify must never fail the build.
            vres = {}
            errors.append("verify error (non-fatal): %s" % exc)
        for r in rows:
            if r["type_name"] in (vres or {}):
                r["verify"] = vres[r["type_name"]]
                v           = r["verify"]
                if v.get("ran") and v.get("pass") is False:
                    _emit(progress_cb, "verify", r["type_name"], "fail",
                          "maxerr=%s" % v.get("maxerr"), 0, n_total)
                elif v.get("ran") and v.get("pass"):
                    _emit(progress_cb, "verify", r["type_name"], "ok",
                          "maxerr=%s" % v.get("maxerr"), 0, n_total)
                else:
                    _emit(progress_cb, "verify", r["type_name"], "skip",
                          v.get("reason", ""), 0, n_total)
        _emit(progress_cb, "verify", None, "ok", "verify done", 0, n_total)

    # ---- (f) manifest -----------------------------------------------------
    # The bundle is real and loadable, so bundle_path is reported either way --
    # but a run that asked for AI optimization and got NONE must not come back
    # ok. A 43-template batch reported ok=43/fail=0 while no agent session ever
    # started; the whole point of the run was the optimization it did not do.
    result = _result(not ai_never_ran, bundle_path, None, plugin_name, rows,
                     errors, strict,
                     out_dir, provider, model, progress_cb, write_manifest=True)
    result["shared_helpers"] = asm_shared
    if asm_conflicts:
        result["shared_helper_conflicts"] = asm_conflicts
    if companions:
        result["companions"] = companions
    # Surface the AI optimizer's report (accepted / speedup / reason per node,
    # plus any skip/error/fallback status) so the dialog can show it (#64).
    if optimize_summary:
        result["optimize"] = optimize_summary
    # ONE key that says WHY ok is False here, so a caller never has to tell
    # "the AI never ran" from "the build is broken" by matching error strings.
    # The bundle in ``bundle_path`` is real, linked and loadable either way.
    if ai_never_ran:
        result["ai_optimize_failed"] = ai_never_ran
    return result


def _clean_working_subdirs(out_dir, rows, clean_scratch=True):
    """Remove per-node port scratch dirs after a build so the folder stays clean.

    New-layout scratch lives at ``build/<type>/``: removed for every node that
    BUILT, kept for a DROPPED node (debugging). ALSO sweeps the PRE-REORG scratch
    location ``out_dir/<type>/`` (top level) for EVERY node -- migration so
    re-compiling an old FLAT folder ends with only the bundle (+ ``*_commands.py``
    companions) and ``build/`` at the top. Both removals are guarded to stay
    strictly under ``out_dir`` so a surprising type name can't escape the folder.

    ``clean_scratch`` additionally removes the optimizer's working directory
    (``build/_optscratch/``), which nothing used to clean and which grows a full
    build tree + agent workspace per optimized node. Never touches
    ``build/source/`` or ``build/stages/``: the shipped C++, the per-round
    revisions and the reports are the whole point of keeping the folder.
    """
    if not clean_scratch:
        return
    out_abs   = os.path.abspath(out_dir)
    build_dir = bundler.build_dir_for(out_dir)
    scratch_root = os.path.join(build_dir,
                                optimizer_live.OPT_SCRATCH_DIRNAME)

    def _rmdir_under_out(path):
        try:
            if (os.path.isdir(path)
                    and os.path.abspath(path).startswith(out_abs + os.sep)):
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass

    for r in rows or []:
        tn = r.get("type_name") or ""
        if not tn:
            continue
        _rmdir_under_out(os.path.join(out_dir, tn))       # migration (top level)
        if r.get("build_status") in ("compiled", "transformed"):
            _rmdir_under_out(os.path.join(build_dir, tn))  # build/<type> if built
            # Same rule for where the optimizer ran: its rounds are already
            # durable under build/stages/<Type>/, so the working tree is lint --
            # unless the node dropped, when it is the only place the logs survive.
            _rmdir_under_out(os.path.join(scratch_root, tn))
    try:
        os.rmdir(scratch_root)    # only lands when every node's scratch went
    except OSError:
        pass


def _drop_row(spec, type_name, stage, reason, provider, model):
    """A manifest row for a node dropped before/at port (no type_id/build)."""
    return {
        "source_node":    spec.get("source_node"),
        "type_name":      type_name,
        "type_id":        None,
        "type_id_source": "",
        "base":           spec.get("suggested", {}).get("mpx_base", "MPxNode"),
        "spec_hash":      port_cache.cache_key(spec, provider=provider, model=model),
        "port_cache_key": port_cache.cache_key(spec, provider=provider,
                                                model=model),
        "cache":        None,
        "build_status": "dropped",
        "build_reason": "%s: %s" % (stage, reason),
        # Uniform row shape: nothing was ported, so nothing to admit to.
        "ported":           False,
        "incomplete":       [],
        "invented_io":      [],
        "missing_includes": [],
        "verify": {"ran": False, "pass": None, "maxerr": None, "tol": None,
                   "reason": ""},
        "spec": spec,
    }


def _write_manifest(out_dir, plugin_name, bundle_path, rows, strict, provider,
                    model):
    """Write ``manifest.json`` into ``out_dir/build/`` and return its path.

    The manifest is a build receipt, not something loaded at runtime, so it lives
    in the ``build/`` folder next to the source/scripts (the top level holds only
    the bundle + companions). Top-level fields: manifest_version,
    porter_recipe_version, provider, model, strict, plugin_name, bundle, created.
    Per-node: source_node hint, type_name, type_id, base, spec_hash,
    port_cache_key, verify row, AND the full spec (so scope B can recompute the
    exact cache key and rebuild byte-identically).
    """
    import json

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "porter_recipe_version": port_cache.PORTER_RECIPE_VERSION,
        "provider": provider,
        "model": model,
        "strict": strict,
        "plugin_name": plugin_name,
        "bundle": bundle_path,
        "created": time.time(),
        "nodes": rows,
    }
    build_dir = bundler.build_dir_for(out_dir)
    os.makedirs(build_dir, exist_ok=True)
    path = os.path.join(build_dir, "manifest.json")
    tmp  = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        # NOT sort_keys: the embedded spec carries attribute DECLARATION ORDER
        # only as its dict INSERTION order (emit_attr iterates spec[kind].items()),
        # and unlike the ``.mpn`` attr map there is no per-meta ``order`` field to
        # rebuild it from. Alphabetizing it broke the "rebuild byte-identically"
        # promise above, and addAttribute() order IS Channel Box / AE order.
        json.dump(manifest, fh, indent=2, default=str)
        fh.write("\n")
    os.replace(tmp, path)  # atomic on POSIX
    # Sweep a stale top-level manifest.json a pre-reorg compile left behind, so
    # the top level never carries two manifests.
    try:
        stale = os.path.join(out_dir, "manifest.json")
        if os.path.isfile(stale):
            os.remove(stale)
    except OSError:
        pass
    return path


def _result(ok, bundle_path, manifest_path, plugin_name, rows, errors, strict,
            out_dir, provider, model, progress_cb, write_manifest=False):
    """Build the return dict, writing the manifest as the LAST step if asked."""
    report_path = None
    if write_manifest:
        try:
            manifest_path = _write_manifest(out_dir, plugin_name, bundle_path,
                                            rows, strict, provider, model)
        except Exception as exc:
            errors.append("manifest write failed: %s" % exc)
            manifest_path = None
        # Reports ride with the manifest on EVERY exit path -- an aborted or
        # strict-failed build is when a human most needs to read what happened.
        # A report failure is never a build failure.
        try:
            written     = _stage_report.write_reports(out_dir, plugin_name, rows)
            report_path = written[-1] if written else None
        except Exception:
            report_path = None
    _emit(progress_cb, "done", None, "ok" if ok else "fail",
          "%d node(s)" % len(rows), 0, len(rows))
    return {
        "ok":            ok,
        "bundle_path":   bundle_path,
        "manifest_path": manifest_path,
        "report_path":   report_path,
        "plugin_name":   plugin_name,
        "nodes":         rows,
        "errors":        errors,
        "strict":        strict,
    }


# ---------------------------------------------------------------------------
# Threaded controller (mirrors ui/llm/cli_base.BaseCliClient)
# ---------------------------------------------------------------------------


class CompileController:
    """Run ``compile_plugin`` off the calling thread on a daemon worker.

    Mirrors ``ui/llm/cli_base.BaseCliClient``: ``start`` spawns a daemon
    ``threading.Thread`` running the synchronous engine, ``cancel`` sets a
    ``threading.Event`` the engine polls between nodes (and that the porter's
    cancel-aware ``complete_fn`` uses to terminate an in-flight CLI port), and
    ``is_busy`` reports whether a run is in progress.

    IMPORTANT: ``progress_cb`` fires on the WORKER thread. A GUI adapter MUST
    marshal each event onto the Qt thread (e.g. emit a queued Qt ``Signal``)
    before touching any widget -- never call into widgets from the callback
    directly. (This is the deliberate departure from the QObject-emits-Signal
    idiom noted in the design's "Module layout".)
    """

    def __init__(self, *, progress_cb=None):
        self._progress_cb = progress_cb
        self._cancel      = threading.Event()
        self._thread      = None
        self._busy        = False
        self._result      = None

    def is_busy(self):
        return self._busy

    @property
    def result(self):
        """The last run's return dict (None until a run finishes)."""
        return self._result

    def cancel(self):
        """Request cancellation (idempotent). The worker aborts at its next
        between-node check, terminates any in-flight porter/optimizer CLI
        subprocess, and stops the optimize loop between rounds and between
        nodes. On an API provider there is no subprocess to kill: the cancel
        lands between retries -- including during a rate-limit backoff -- but
        cannot abort a reply already being read."""
        self._cancel.set()

    def start(self, specs, plugin_name, out_dir, **opts):
        """Spawn the daemon worker. Raises if a run is already in progress.

        ``opts`` are forwarded verbatim to ``compile_plugin`` EXCEPT
        ``cancel_event`` (always this controller's Event) and ``progress_cb``
        (this controller's, set at construction). Returns the worker thread.
        """
        if self._busy:
            raise RuntimeError("CompileController is already running")
        self._cancel.clear()
        self._result = None
        self._busy   = True
        opts.pop("cancel_event", None)
        opts.pop("progress_cb", None)

        def _run():
            try:
                self._result = compile_plugin(
                    specs, plugin_name, out_dir,
                    progress_cb=self._progress_cb,
                    cancel_event=self._cancel, **opts)
            except UnsupportedSpec as exc:
                # Refusal, not a crash -- and this is the DEFAULT dialog path
                # (the compile dialog only calls start_multi for 2+ versions),
                # so it is where the Qt gate is most likely to land. No
                # traceback: the message IS the answer.
                self._result = {
                    "ok": False, "bundle_path": None, "manifest_path": None,
                    "plugin_name": plugin_name, "nodes": [],
                    "errors": ["build refused: %s" % exc],
                    "strict": opts.get("strict", True),
                }
                _emit(self._progress_cb, "done", None, "fail",
                      "build refused: %s" % exc, 0, 0)
            except Exception as exc:
                # Last-resort guard: surface an engine crash as a failed result
                # + a 'done/fail' event, never a silently dead worker.
                self._result = {
                    "ok": False, "bundle_path": None, "manifest_path": None,
                    "plugin_name": plugin_name, "nodes": [],
                    "errors": ["controller crash: %s\n%s"
                               % (exc, traceback.format_exc())],
                    "strict": opts.get("strict", True),
                }
                _emit(self._progress_cb, "done", None, "fail",
                      "controller crash: %s" % exc, 0, 0)
            finally:
                self._busy = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return self._thread

    def start_multi(self, specs, plugin_name, out_dir, targets, **opts):
        """Like ``start`` but builds ``specs`` against EVERY Maya version in
        ``targets`` (``compile_plugin_multi``), each into ``out_dir/<label>/``.

        ``opts`` are forwarded to ``compile_plugin_multi`` EXCEPT
        ``cancel_event`` (always this controller's Event) and ``progress_cb``
        (this controller's). ``verify_fn_for`` is the per-version verify factory.
        Returns the worker thread.
        """
        if self._busy:
            raise RuntimeError("CompileController is already running")
        self._cancel.clear()
        self._result = None
        self._busy   = True
        opts.pop("cancel_event", None)
        opts.pop("progress_cb", None)

        def _run():
            try:
                self._result = compile_plugin_multi(
                    specs, plugin_name, out_dir, targets,
                    progress_cb=self._progress_cb,
                    cancel_event=self._cancel, **opts)
            except UnsupportedSpec as exc:
                # Refusal, not a crash (see compile_plugin_multi, which already
                # absorbs the per-version case). Reached only if the refusal is
                # raised OUTSIDE that per-version try.
                self._result = {
                    "ok": False, "multi": True, "plugin_name": plugin_name,
                    "out_dir": out_dir, "results": [],
                    "errors": ["build refused: %s" % exc],
                }
                _emit(self._progress_cb, "done", None, "fail",
                      "build refused: %s" % exc, 0, 0)
            except Exception as exc:
                self._result = {
                    "ok": False, "multi": True, "plugin_name": plugin_name,
                    "out_dir": out_dir, "results": [],
                    "errors": ["controller crash: %s\n%s"
                               % (exc, traceback.format_exc())],
                }
                _emit(self._progress_cb, "done", None, "fail",
                      "controller crash: %s" % exc, 0, 0)
            finally:
                self._busy = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return self._thread
