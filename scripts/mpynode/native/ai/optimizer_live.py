"""Live adapters binding the pure ``optimizer`` engine to the real toolchain.

The engine (``optimizer.optimize_cpp``) is side-effect-free: it drives five
injected callables. This module builds those five for a real node, reusing the
existing infrastructure rather than duplicating it:

  * optimize_fn / fix_fn  -> ``optimizer_knowledge`` prompts + the porter's own
                             cancellable LLM client (``make_cli_complete_fn``),
                             cleaned with the porter's ``prompt._extract_body``.
  * compile_fn            -> ``porter.compile_cpp(..., optimize=True)`` so the
                             recompile always carries ``-ffp-contract=off`` (a
                             fused mul+add would otherwise FMA-contract and drift
                             ~1 ULP, breaking parity).
  * parity_fn             -> a parity harness run in a FRESH mayapy (subprocess
                             isolation sidesteps Maya's no-plugin-reload), mapping
                             PARITY_JSON -> PASS / FAIL, and -> SKIP when there is
                             no harness or it produced no verdict (SKIP is never a
                             pass, so the engine safely refuses to accept).
  * benchmark_fn          -> ``benchmark_node.py`` in a fresh mayapy, parsing
                             BENCH_JSON's median_ms (None when unmeasurable).

Both side channels -- the model call (``complete_fn``) and the subprocess runner
(``run_step``) -- are injectable so this is unit-testable with no Maya / LLM /
compiler. Real imports are lazy (inside the factory) so importing this module
stays cheap and Maya-free.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Optional

from .optimizer import (ParityVerdict, PARITY_PASS, PARITY_FAIL, PARITY_SKIP,
                        is_unchanged)


# Where a round physically runs: build/_optscratch/<Type>. Pure lint -- the
# durable record lives in build/stages/<Type>/. Named here because the compile
# controller sweeps this dir and a second literal would drift silently.
OPT_SCRATCH_DIRNAME = "_optscratch"

_HARNESS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "tools", "harness"))
_BENCHMARK_SCRIPT = os.path.join(_HARNESS_DIR, "benchmark_node.py")

# Bench-scene ladder: (geo_density, array_len). A measurement dominated by fixed
# DG/marshalling cost cannot reveal an algorithmic win, so the scene grows until
# the node's own work dominates. Sizes mirror real rig regimes (density 40 is
# ~1.5k verts; 200 is ~40k). Rungs continue past the KD-tree's regime because
# "heavy" and "slow per element" differ: patch_relax over 39,802 verts is still
# only ~1 ms. Climbing stops at the first rung that clears the floor, so the extra
# rungs only apply to nodes that need them.
_BENCH_LADDER = ((40, 512), (90, 2000), (140, 5000), (200, 10000),
                 (300, 10000), (400, 20000))

# Below this the run-to-run noise (~8% at 0.4 ms) swamps any real difference.
_BENCH_FLOOR_MS = float(os.environ.get("MPYNODE_BENCH_FLOOR_MS", "15") or 15)

# _measure returns this -- NOT None -- when the harness refused because every geo
# output was empty: a too-small/degenerate scene, so the ladder should GROW. A
# bare None means the benchmark FAILED and retrying it would fail six more times.
_EMPTY_OUTPUT = object()


def _project_root():
    # scripts/mpynode/native/ai/optimizer_live.py -> project root is 5 up.
    return os.path.normpath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", "..", ".."))


def _optimize_cli_timeout() -> float:
    """Wall-clock budget (seconds) for ONE optimizer rewrite/fix LLM call.

    A full-file rewrite of a large node (e.g. the ~2900-line metaballs SDF/DMC
    compute) streams well PAST the porter's 600s translate budget
    (``MPYNODE_PORT_TIMEOUT``); with the shared 600s cap every optimization round
    times out before returning a candidate, so the gate has nothing to accept and
    the optimizer silently keeps the original transpiler output. Give the rewrite
    its own generous, separately-tunable budget. Default 2400s (40 min); override
    with ``MPYNODE_OPT_TIMEOUT``. A sentinel value of ``off``/``none``/``inf``/
    ``0``/`` `` (the UI writes this from the disable-able optimize-timeout
    preference) means UNBOUNDED -> ``float("inf")``: no wall-clock kill, only
    user Cancel stops the call (a liveness heartbeat proves it is working)."""
    raw = os.environ.get("MPYNODE_OPT_TIMEOUT", "2400")
    s = (raw or "").strip().lower()
    if s in ("", "0", "off", "none", "inf", "unbounded", "-1"):
        return float("inf")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 2400.0


def _optimize_rounds(default=2):
    """How many optimize rounds per node. ``MPYNODE_OPT_ROUNDS`` overrides.

    One AGENTIC round is a whole build+measure session (40 min at the default
    budget), so 2 rounds is ~110 min per node -- fine for a single compile,
    prohibitive for a model x flag sweep. Kept as an env override rather than a
    new argument so the shipped call path and its default are untouched. ``0`` is
    honoured: it measures the baseline and accepts nothing."""
    raw = os.environ.get("MPYNODE_OPT_ROUNDS")
    if raw is None or not str(raw).strip():
        return default
    try:
        return max(0, int(str(raw).strip()))
    except (TypeError, ValueError):
        return default


def _history_enabled():
    """Whether each round is told what the earlier rounds already tried.

    OFF by default. Rounds are independent restarts today, and that is a real
    strategy -- a fresh session carries no attachment to the approach that just
    failed. Feeding history back trades that diversity for continuity, which is
    a measurable question, not an obvious win. Opt in with ``MPYNODE_OPT_HISTORY``
    so both behaviours can be run from the same binary and compared.
    """
    raw = (os.environ.get("MPYNODE_OPT_HISTORY") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Global benchmark lock
# ---------------------------------------------------------------------------
# Two Maya processes timing at once contend for the same cores and corrupt BOTH
# numbers -- and a corrupt number here is not a slow run, it is a WRONG verdict
# that ships (or discards) a rewrite on noise. But an optimizer round is mostly
# LLM latency, so serializing whole rounds would throw the parallelism away for
# nothing. This serializes ONLY the timed subprocess, leaving N agents thinking
# concurrently while exactly one benchmarks.
#
# OFF unless MPYNODE_BENCH_LOCK is set, so a single-process run costs literally
# nothing (bench_lock() returns before it touches the filesystem) and no existing
# serial usage can change behaviour.

BENCH_LOCK_ENV = "MPYNODE_BENCH_LOCK"
BENCH_LOCK_TIMEOUT_ENV = "MPYNODE_BENCH_LOCK_TIMEOUT"
_BENCH_LOCK_DEFAULT_TIMEOUT = 1800.0
_BENCH_LOCK_POLL = 0.25


class BenchLockTimeout(RuntimeError):
    """Waited past ``MPYNODE_BENCH_LOCK_TIMEOUT`` for the benchmark lock.

    A wedged holder must degrade to a loud, attributable error -- never to an
    infinite hang (which reads as a dead fleet) and never to an unlocked
    benchmark (which reads as a good measurement).
    """


def bench_lock_path():
    """The lockfile to serialize benchmarks on, or ``""`` when the lock is OFF.

    ``MPYNODE_BENCH_LOCK`` unset / ``0`` / ``off`` -> off (the default).
    ``1``/``on`` -> a shared file in the system temp dir. Anything else is taken
    as the path itself, so a fleet can point every worker at one location.
    The default deliberately avoids the MPyNode home: that is ``~/mpynode``,
    which is EPERM on this machine, and a lock we cannot create is a lock that
    silently protects nothing.
    """
    raw = os.environ.get(BENCH_LOCK_ENV)
    if raw is None:
        return ""
    s = raw.strip()
    if s.lower() in ("", "0", "off", "false", "no"):
        return ""
    if s.lower() in ("1", "on", "true", "yes"):
        import tempfile

        return os.path.join(tempfile.gettempdir(), "mpynode-bench.lock")
    return s


def _bench_lock_timeout():
    raw = (os.environ.get(BENCH_LOCK_TIMEOUT_ENV) or "").strip().lower()
    if raw in ("", "0", "off", "none", "inf"):
        return (float("inf") if raw in ("off", "none", "inf")
                else _BENCH_LOCK_DEFAULT_TIMEOUT)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return _BENCH_LOCK_DEFAULT_TIMEOUT


@contextlib.contextmanager
def bench_lock(label="", log_cb=None, cancelled=None):
    """Hold the cross-process benchmark lock for the body. Yields True if held.

    A plain lockfile + ``fcntl.flock(LOCK_EX | LOCK_NB)`` in a poll loop -- no
    new dependencies, and no staleness bookkeeping to get wrong: the kernel
    drops an ``flock`` when the holding fd closes, INCLUDING when the holder is
    SIGKILLed or segfaults (which a mis-compiled candidate really does do). A
    crashed holder therefore cannot wedge the fleet; the next waiter takes the
    lock on its next poll.

    No-op (yields False) when the lock is off, or on a platform with no
    ``fcntl`` -- Windows, where the whole compile path is single-process anyway.
    ``cancelled()`` is polled while waiting so a user Cancel is not stuck behind
    another process's benchmark. Waiting past the timeout raises
    ``BenchLockTimeout``.
    """
    path = bench_lock_path()
    if not path:
        yield False
        return
    try:
        import fcntl
    except ImportError:
        yield False
        return

    def _say(msg):
        if log_cb is not None:
            try:
                log_cb(msg)
            except Exception:
                pass

    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        fh = open(path, "a+")
    except OSError as exc:
        # A lock we cannot create protects nothing, and pretending otherwise is
        # how two processes end up timing at once while the log says they did not.
        raise BenchLockTimeout(
            "cannot open the benchmark lockfile %r: %s. Point %s at a writable "
            "path (or unset it to disable benchmark serialization)."
            % (path, exc, BENCH_LOCK_ENV))
    timeout = _bench_lock_timeout()
    deadline = None if timeout == float("inf") else time.time() + timeout
    t0 = time.time()
    waited = False
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if cancelled is not None and cancelled():
                    raise _StepCancelled()
                if deadline is not None and time.time() >= deadline:
                    raise BenchLockTimeout(
                        "waited %.0fs for the benchmark lock %r (held by: %s). "
                        "Raise %s, or clear the wedged holder."
                        % (time.time() - t0, path, _bench_lock_holder(path),
                           BENCH_LOCK_TIMEOUT_ENV))
                if not waited:
                    waited = True
                    _say("[optimizer] %swaiting for the global benchmark lock"
                         % (label + ": " if label else ""))
                time.sleep(_BENCH_LOCK_POLL)
        if waited:
            _say("[optimizer] %sgot the benchmark lock after %.1fs"
                 % (label + ": " if label else "", time.time() - t0))
        # Diagnostic only -- flock, not this text, is the mutual exclusion.
        try:
            fh.seek(0)
            fh.truncate()
            fh.write("pid=%d label=%s since=%.0f\n"
                     % (os.getpid(), label or "?", time.time()))
            fh.flush()
        except OSError:
            pass
        yield True
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()


def _bench_lock_holder(path):
    """The holder line the current owner wrote, for the timeout message."""
    try:
        with open(path) as fh:
            return (fh.read(200).strip() or "unknown")
    except OSError:
        return "unknown"


def _base_env(out_dir):
    """Env for a fresh mayapy step: scripts on PYTHONPATH, plug-ins + the freshly
    compiled bundle's dir on MAYA_PLUG_IN_PATH, offscreen Qt. Mirrors the
    conventions in ``tools/harness/run_all.py``."""
    root = _project_root()
    e = dict(os.environ)
    # This process ALREADY holds the flock around the whole child (see
    # bench_lock), and an flock belongs to the open file description -- a child
    # told to take it too would wait on its own parent until the lock timeout
    # and then fail the measurement. Inherited rather than set here (only a
    # human export puts it in os.environ: bench.sh's export propagates DOWN,
    # and the agent window in optimizer_agent closes before the engine measures)
    # -- but the cost of being wrong is that deadlock, so scrub it.
    e.pop("MPYNODE_BENCH_LOCK_CHILD", None)
    e["MPYNODE_ROOT"] = root
    e["MPYNODE_USE_STUDIO"] = "1"
    e["PYTHONPATH"] = os.path.join(root, "scripts") + os.pathsep + e.get(
        "PYTHONPATH", "")
    e["MAYA_PLUG_IN_PATH"] = os.pathsep.join(
        [os.path.join(root, "plug-ins"), out_dir, e.get("MAYA_PLUG_IN_PATH", "")])
    e["QT_QPA_PLATFORM"] = "offscreen"
    # A mis-compiled candidate can SEGFAULT this child mayapy. Disable Autodesk's
    # crash reporter (CER/CIP) so it never pops a "Maya closed unexpectedly"
    # dialog; the parent Maya is unaffected. setdefault honours a parent override.
    e.setdefault("MAYA_DISABLE_CER", "1")
    e.setdefault("MAYA_DISABLE_CIP", "1")
    return e


class _StepCancelled(Exception):
    """Raised inside the cancel-aware run_step when ``cancel_event`` fires; the
    child mayapy is terminated before it propagates."""


def _terminate_step_proc(proc):
    """terminate() a child mayapy, then kill() it after a short grace."""
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=2.0)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=2.0)
        except Exception:
            pass


def _run_step_cancellable(cmd, out_dir, timeout, cancel_event, _popen=None):
    """Run ``cmd`` as a child mayapy, draining its output on a pump thread while
    the caller polls ``cancel_event`` ~every 0.1s; on cancel, terminate() then
    kill() the child and raise ``_StepCancelled``. Mirrors
    ``llm_client._run_cli_proc`` so closing the compile window kills an in-flight
    benchmark/parity child immediately instead of leaving it running to its own
    (default 1800s) timeout. Returns ``(stdout_text, returncode)``."""
    popen = _popen or subprocess.Popen
    proc = popen(cmd, cwd=_project_root(), env=_base_env(out_dir),
                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    pump = {}

    def _drain():
        # communicate() drains the (merged) pipe concurrently so a child that
        # writes >64KB can't deadlock on a full pipe while we poll for cancel.
        try:
            pump["out"] = proc.communicate()[0]
            pump["rc"] = proc.returncode
        except Exception as exc:  # pragma: no cover - defensive
            pump["exc"] = exc

    worker = threading.Thread(target=_drain, daemon=True)
    worker.start()
    deadline = (None if timeout in (None, float("inf"))
                else time.time() + timeout)
    try:
        while worker.is_alive():
            if cancel_event.is_set():
                _terminate_step_proc(proc)
                raise _StepCancelled()
            if deadline is not None and time.time() >= deadline:
                _terminate_step_proc(proc)
                raise subprocess.TimeoutExpired(cmd, timeout)
            worker.join(0.1)
        # Pump finished on its own -- but a cancel may have raced in just now.
        if cancel_event.is_set():
            _terminate_step_proc(proc)
            raise _StepCancelled()
        if "exc" in pump:
            raise pump["exc"]
    finally:
        if proc.poll() is None:
            _terminate_step_proc(proc)
        worker.join(2.0)
    out = pump.get("out")
    if isinstance(out, (bytes, bytearray)):
        out = out.decode("utf-8", "replace")
    return (out or ""), pump.get("rc")


def _make_run_step(mayapy, out_dir, timeout, cancel_event=None):
    """Default subprocess runner: ``mayapy <script> <args...>``; return
    (json_after_prefix | None, ok, tail). Never raises.

    When ``cancel_event`` is given (always the controller's Event in the live
    pipeline) the child is run cancel-aware, so closing the compile window
    terminates an in-flight child mayapy promptly instead of letting it run to
    its own timeout in the background."""

    def run_step(script, args, prefix, step_timeout=None):
        cmd = [mayapy, script] + [str(a) for a in args]
        tmo = step_timeout or timeout
        try:
            if cancel_event is None:
                p = subprocess.run(cmd, cwd=_project_root(),
                                   env=_base_env(out_dir),
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=tmo)
                out, rc = p.stdout.decode("utf-8", "replace"), p.returncode
            else:
                out, rc = _run_step_cancellable(cmd, out_dir, tmo, cancel_event)
        except _StepCancelled:
            return None, False, "cancelled"
        except subprocess.TimeoutExpired:
            return None, False, "TIMEOUT after %ss" % tmo
        except Exception as exc:
            return None, False, "subprocess error: %r" % exc
        data = None
        for line in out.splitlines():
            if line.startswith(prefix):
                try:
                    data = json.loads(line[len(prefix):])
                except Exception:
                    data = None
        tail = "\n".join(out.splitlines()[-25:])
        return data, (rc == 0), tail

    return run_step


class _OptimizeCancelled(BaseException):
    """A user Cancel, carried out past the engine's per-round guard.

    ``optimizer.optimize_cpp`` wraps each round in ``except Exception`` so one
    flaky adapter cannot abort the whole run -- correct for a flaky adapter and
    wrong for a cancel, which used to be logged as "round N: error" while the
    loop went on to start the next round. Deriving from ``BaseException`` is what
    lets the cancel through that guard without the pure engine having to learn
    the LLM client exists.
    """


def _cancel_guard(fn):
    """Re-raise a cancel out of ``fn`` as ``_OptimizeCancelled``.

    Two shapes reach here, one per waiting adapter: ``PortCancelled`` from the
    model call, and ``_StepCancelled`` from ``bench_lock`` polling
    ``cancelled()`` while it waits for another process's benchmark. Both are a
    user Cancel; unguarded, the second one surfaced as a round "error" -- or,
    at the baseline measurement (which the engine makes OUTSIDE its per-round
    guard), as a whole-node failure.

    The ``PortCancelled`` import is lazy for the same reason the rest of this
    module's are (keep importing it cheap), and matches ``optimizer_agent``'s
    own check.
    """

    def _call(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except _StepCancelled:
            raise _OptimizeCancelled()
        except Exception as exc:
            from .llm_client import PortCancelled
            if isinstance(exc, PortCancelled):
                raise _OptimizeCancelled()
            raise

    return _call


def make_adapters(spec: dict, out_dir: str, *,
                  maya: Optional[str] = None,
                  cancel_event=None,
                  log_cb=None,
                  node_type: Optional[str] = None,
                  out_plug: Optional[str] = None,
                  parity_harness: Optional[str] = None,
                  parity_fn=None,
                  benchmark_fn=None,
                  bench_hint: Optional[str] = None,
                  bench_iters: int = 9,
                  bench_res: int = 16,
                  bench_array: int = 512,
                  bench_geo: int = 40,
                  bench_scene: Optional[str] = None,
                  timeout: int = 1800,
                  complete_fn=None,
                  agent_fn=None,
                  agent_ws: Optional[str] = None,
                  provider: Optional[str] = None,
                  status_out=None,
                  run_step=None) -> dict:
    """Build the five engine adapters for ``spec`` compiling into ``out_dir``.

    ``parity_harness`` is a standalone mayapy script that prints ``PARITY_JSON``
    (e.g. ``metaballs_parity.py`` for metaClay); without one, parity is SKIP and
    the engine will not accept any candidate. ``parity_fn`` / ``benchmark_fn``
    can be passed directly to override. ``complete_fn`` and ``run_step`` are
    injectable for tests; in production they default to the porter's cancellable
    LLM client and a fresh-mayapy subprocess runner.

    ``provider`` is the RUN's provider -- the one the caller's own budget gate
    already pre-flighted (``compile_controller._optimizer_is_one_shot``). It is
    the agent pre-flight's input here so both ask one question; ``None`` keeps
    the prefs fallback ``check_provider`` already applies, which is what every
    run with no explicit override resolves to anyway.

    ``status_out`` (optional dict) is filled with what the AI ACTUALLY did:
    ``path`` (agent / one-shot + why), ``rounds`` attempted, ``candidates``
    (rounds that came back with source differing from what went in) and
    ``errors``. Without it a provider that dies at startup every round is
    indistinguishable from one that ran and found nothing: the round returns the
    UNCHANGED source, the gate re-measures it, and benchmark noise gets recorded
    as a speedup. ``candidates == 0`` with a non-empty ``errors`` is the caller's
    proof that no AI work happened at all.
    """
    from . import porter, prompt, optimizer_knowledge  # lazy: keep import cheap
    from . import optimizer_agent
    from .llm_client import make_cli_complete_fn
    from ..toolchain import toolchain

    name = spec["suggested"]["node_type_name"]
    ntype = node_type or name
    maya = maya or toolchain.default_maya_dir()
    agent_ws = agent_ws or os.path.join(out_dir, "_optagent")

    # Written BEFORE the adapters are built: both the engine's own benchmark and
    # the agent's bench.sh drive the node from this same spec, so the number the
    # agent optimizes against is the number the gate will re-measure.
    spec_path = os.path.join(out_dir, "_bench_spec.json")
    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(spec_path, "w") as fh:
            json.dump(spec, fh)
    except Exception:
        spec_path = None

    # An INJECTED complete_fn means the caller is deliberately driving the one-shot
    # text path (how the hygiene tests exercise it), so do not promote it to a live
    # tool-using agent -- that would make a unit test shell out to the real CLI.
    _text_path_requested = complete_fn is not None
    if complete_fn is None:
        from mpynode.ui import preferences as _prefs
        complete_fn = make_cli_complete_fn(
            cancel_event=cancel_event, log_cb=log_cb,
            timeout=_optimize_cli_timeout(),
            max_tokens=_prefs.resolve_optimize_max_tokens())
    if run_step is None:
        run_step = _make_run_step(toolchain.mayapy_path(maya), out_dir, timeout,
                                  cancel_event=cancel_event)

    # Optimizing is edit -> build -> measure -> keep-or-revert, repeatedly: give
    # the agent the file and that loop (optimizer_agent) and read the result back
    # off disk. The one-shot "return the whole file as text" path is only a
    # fallback for providers with no tool-using headless mode, or when the agent
    # itself could not be built.
    _agent_state = {"baseline_ms": None, "geo": None, "array": None,
                    "round_meta": {}, "history": []}
    _status = status_out if status_out is not None else {}
    _status.setdefault("rounds", 0)
    _status.setdefault("candidates", 0)
    _status.setdefault("errors", [])

    def _log(msg):
        if log_cb is not None:
            try:
                log_cb(msg)
            except Exception:
                pass

    def _fail(msg):
        """Record a reason the AI produced nothing, and say it out loud."""
        _status["errors"].append(msg)
        _log("[optimizer] %s: %s" % (ntype, msg))

    def _watch_agent(fn):
        """Wrap the agent so a startup failure is RECORDED before it is thrown.

        ``optimizer_agent.optimize_with_agent`` deliberately swallows a late
        failure -- by then the agent has edited and measured real files, and that
        work is worth gating. But it swallows an EARLY one identically, and then
        returns the untouched source; the engine dutifully rebuilds it, measures
        the same file twice, and records the difference as a speedup (a
        byte-identical 01_accept.cpp claiming 1.15x). The exception still
        propagates unchanged -- this only takes a copy on the way past.
        """

        def _call(prompt):
            try:
                return fn(prompt)
            except Exception as exc:
                from .llm_client import PortCancelled
                if not isinstance(exc, PortCancelled):
                    _agent_state["round_error"] = "%s: %s" % (
                        type(exc).__name__, exc)
                raise

        return _call

    def _make_agent():
        """The tool-using agent, or None (with a STATED reason) to fall back.

        Never fail silently here: a swallowed ImportError would quietly demote
        every optimize round to the blind one-shot path, which looks identical
        in the log and simply never finds anything.
        """
        if agent_fn is not None:
            _status["path"] = "agent (injected)"
            return _watch_agent(agent_fn)
        if _text_path_requested:
            _status["path"] = "one-shot (complete_fn injected by the caller)"
            return None
        try:
            from .llm_client import check_agent, make_cli_agent_fn
        except Exception as exc:
            _status["path"] = "one-shot (%r)" % (exc,)
            _log("[%s] no tool-using agent (%r); falling back to one-shot "
                 "whole-file rewrite" % (ntype, exc))
            return None
        # ONE pre-flight for every reason the agent cannot run (wrong provider,
        # binary off PATH, a sandbox that cannot nest). Cheap and token-free, and
        # it runs BEFORE the round is spent: without it the CLI dies ~2s in, the
        # failure is swallowed downstream, and the round is charged to the AI.
        # Asked about the RUN's provider, not prefs: the caller's budget gate
        # asked this same pre-flight about that provider, and a gate that
        # answers for one provider while the round runs another is no gate.
        chk = check_agent(provider)
        if not chk.get("ok"):
            why = "; ".join(chk.get("problems") or []) or "unavailable"
            _status["path"] = "one-shot (no agent: %s)" % why
            _log("[%s] no tool-using agent: %s. Falling back to one-shot "
                 "whole-file rewrite." % (ntype, why))
            return None
        os.makedirs(agent_ws, exist_ok=True)
        _status["path"] = "agent"
        _log("[%s] optimizing as an agent in %s" % (ntype, agent_ws))
        return _watch_agent(make_cli_agent_fn(
            agent_ws, cancel_event=cancel_event, log_cb=log_cb,
            timeout=_optimize_cli_timeout()))

    def optimize_fn(cpp_text):
        # Cleared per round: the engine reads it back through round_meta_fn
        # immediately after this returns, and a stale entry would label this
        # round's candidate with the previous round's theme.
        _agent_state["round_meta"] = {}
        _agent_state["round_error"] = None
        _status["rounds"] += 1
        agent = _make_agent()
        if agent is not None:
            # The agent's bench.sh MUST use the same calibrated scene the gate
            # measures with, or it optimizes for a workload nobody scores.
            out = optimizer_agent.optimize_with_agent(
                spec, agent_ws, cpp_text, agent, maya=maya, ntype=ntype,
                spec_path=spec_path,
                bench_array=(_agent_state["array"] or bench_array),
                bench_geo=(_agent_state["geo"] or bench_geo),
                bench_iters=bench_iters,
                baseline_ms=_agent_state["baseline_ms"],
                budget_s=_optimize_cli_timeout(), log_cb=log_cb,
                meta_out=_agent_state["round_meta"],
                history=_agent_state["history"])
        else:
            system, user = optimizer_knowledge.build_optimize_prompt(
                cpp_text, spec, bench_hint=bench_hint)
            # Same ledger the agent path gets, through the SAME renderer -- two
            # descriptions of one ledger could drift. Appended rather than woven
            # in: build_optimize_prompt owns the rest of the turn. Renders "" on
            # round 1 and whenever the sink was never registered, so with
            # history OFF (the default) this prompt is unchanged.
            user += optimizer_agent.render_history_block(
                _agent_state["history"])
            try:
                out = prompt._extract_body(complete_fn(system, user))
            except Exception as exc:
                # The engine logs a round error and moves on, so the RUN-level
                # "the AI never delivered anything" verdict has to be recorded
                # here or it is lost. Re-raised unchanged.
                from .llm_client import PortCancelled
                if not isinstance(exc, PortCancelled):
                    _fail("round %d one-shot rewrite failed -- %s: %s"
                          % (_status["rounds"], type(exc).__name__, exc))
                raise
        # The SAME predicate the engine's no-change gate uses. Counting an
        # echoed file here while the gate rejected it as unchanged is what let
        # one node's phantom candidate suppress a whole run's "AI never ran".
        if not is_unchanged(out, cpp_text):
            _status["candidates"] += 1
        elif _agent_state.get("round_error"):
            # The one shape that used to vanish: the AI failed, the UNCHANGED
            # source came back, and the gate scored the original against itself.
            _fail("round %d produced no candidate -- %s"
                  % (_status["rounds"], _agent_state["round_error"]))
        return out

    def round_meta_fn():
        """What the round that just ran said it was doing (may be empty)."""
        return dict(_agent_state.get("round_meta") or {})

    def round_cb(record, cpp_text):
        """Move the STATED entry baseline with the accepted best.

        ``_benchmark`` records ``baseline_ms`` only while it is calibrating, so
        every later round was told the FIRST measurement -- "Baseline on entry:
        33.183 ms" for a file that by then ran at 1.36 ms, and the round spent
        itself re-measuring to find that out. On accept the engine assigns
        ``best_cpp, best_ms = cand, ms`` immediately after emitting this record,
        so ``record.ms`` IS the measurement of the source the next round is
        handed; the accept rule is read here, never re-derived.
        """
        if record.outcome == "accept":
            _agent_state["baseline_ms"] = record.ms

    def history_sink(ledger):
        """The engine handing back the rounds resolved so far, pre-proposal.

        BOTH paths consume it: the agent gets it in TASK.md, the one-shot
        whole-file fallback (providers with no tool-using headless mode) gets
        the same block appended to its user turn. The sink is registered with
        no provider gate, so gating the READ on one would have collected the
        ledger for nobody on exactly those providers.
        """
        _agent_state["history"] = list(ledger or [])

    def fix_fn(cpp_text, errors):
        # The agent builds its own work, so a candidate that reaches here is
        # rare. Text repair is the right shape for it either way: it is a small,
        # bounded edit, not an optimization search.
        system, user = optimizer_knowledge.build_fix_prompt(cpp_text, errors)
        return prompt._extract_body(complete_fn(system, user))

    def compile_fn(cpp_text):
        cpp_path = os.path.join(out_dir, name + ".cpp")
        with open(cpp_path, "w") as fh:
            fh.write(cpp_text)
        # optimize=True enforces -O3 -ffp-contract=off on the unix recompile.
        return porter.compile_cpp(cpp_path, spec, out_dir, maya=maya,
                                  log_cb=log_cb, optimize=True)

    def _parity(bundle):
        if not parity_harness:
            return ParityVerdict(PARITY_SKIP,
                                 reason="no parity harness for %s" % ntype)
        data, ok, tail = run_step(parity_harness, [bundle], "PARITY_JSON:",
                                  timeout)
        if data is None:
            return ParityVerdict(PARITY_SKIP,
                                 reason="parity harness produced no verdict")
        if data.get("ok"):
            errs = [s.get("maxerr") for s in data.get("scenes", [])
                    if isinstance(s, dict) and s.get("maxerr") is not None]
            return ParityVerdict(PARITY_PASS,
                                 maxerr=(max(errs) if errs else None))
        reason = "; ".join(data.get("errors") or []) or "parity mismatch"
        return ParityVerdict(PARITY_FAIL, reason=reason)

    # The benchmark seeds EVERY supported input and pulls EVERY supported output
    # off this spec. Hardcoding `--out outMesh` meant any node without that plug
    # returned no measurement, so the optimizer kept the original -- silently.
    def _measure(bundle, geo, arr):
        args = [bundle, ntype, "--iters", bench_iters, "--res", bench_res]
        if spec_path:
            args += ["--spec", spec_path,
                     "--bench-array", arr, "--bench-geo", geo]
        if out_plug:                     # explicit override only
            args += ["--out", out_plug]
        if bench_scene:
            args += ["--scene", bench_scene]
        # ONLY the timed child is serialized (see bench_lock): the LLM round that
        # produced this candidate already ran concurrently with every other
        # process's, and holding the lock across it would serialize the fleet on
        # its slowest thinker for no measurement benefit.
        with bench_lock(label=ntype, log_cb=_log,
                        cancelled=(None if cancel_event is None
                                   else cancel_event.is_set)):
            data, ok, tail = run_step(_BENCHMARK_SCRIPT, args, "BENCH_JSON:",
                                      timeout)
        if data is None or data.get("median_ms") is None:
            # Say WHY. A crashed benchmark and a benignly unmeasurable one both
            # reached the engine as a bare "round N: unmeasurable", and the
            # round was dropped -- which silently threw away a real win.
            why = (tail or "").strip().splitlines()
            _log("[%s] benchmark produced no median_ms%s"
                 % (ntype, (": " + why[-1][:200]) if why else ""))
            # An EMPTY output is a too-small/degenerate SCENE, not a broken
            # benchmark: the ladder should grow rather than abandon the node.
            if isinstance(data, dict) and data.get("empty_output"):
                return _EMPTY_OUTPUT
            return None
        return float(data["median_ms"])

    def _calibrate(bundle):
        """Grow the scene until the node's own work dominates the measurement.

        At the shipped default (geo 40 / array 512) a KD-tree node measures
        ~0.4 ms with ~8% run-to-run noise: that is DG traversal and attribute
        marshalling, not the algorithm. An optimizer cannot see an algorithmic
        win it never spends time in, so it accepts micro-tweaks and reports a
        speedup that vanishes on a production-sized scene.

        Escalate until the baseline clears BENCH_FLOOR_MS (or the ladder ends),
        then FREEZE that size for every later measurement -- comparing a
        candidate against a baseline taken at a different scene size would be
        meaningless. Sizes track the external harness's S -> L regimes.
        """
        for geo, arr in _BENCH_LADDER:
            ms = _measure(bundle, geo, arr)
            if ms is _EMPTY_OUTPUT:
                # Not a failure -- the scene is too small for this node to
                # produce anything, so climb. A crash below still aborts at once;
                # retrying THAT would burn six mayapy launches to fail the same.
                _log("[%s] bench scene geo=%d array=%d -> output EMPTY; "
                     "growing" % (ntype, geo, arr))
                continue
            if ms is None:
                return None, geo, arr
            if ms >= _BENCH_FLOOR_MS or (geo, arr) == _BENCH_LADDER[-1]:
                return ms, geo, arr
            _log("[%s] bench scene geo=%d array=%d -> %.3f ms; too small to "
                 "optimize against, growing" % (ntype, geo, arr, ms))
        return None, bench_geo, bench_array

    def _benchmark(bundle):
        if _agent_state["geo"] is None:
            ms, geo, arr = _calibrate(bundle)
            _agent_state["geo"], _agent_state["array"] = geo, arr
            if ms is not None:
                _log("[%s] bench scene geo=%d array=%d -> %.3f ms baseline"
                     % (ntype, geo, arr, ms))
                _agent_state["baseline_ms"] = ms
            return ms
        # Past calibration the scene is FROZEN, so an empty output here is not
        # something growing can fix -- it is simply unmeasurable.
        ms = _measure(bundle, _agent_state["geo"], _agent_state["array"])
        return None if ms is _EMPTY_OUTPUT else ms

    ad = {
        # Every adapter that WAITS on something cancellable, wrapped so a Cancel
        # stops the run instead of being recorded as this round's error (see
        # _cancel_guard): the two model calls, and the benchmark -- which waits
        # on the cross-process bench_lock when it is enabled.
        "optimize_fn": _cancel_guard(optimize_fn),
        "fix_fn": _cancel_guard(fix_fn),
        "compile_fn": compile_fn,
        "parity_fn": parity_fn or _parity,
        "benchmark_fn": _cancel_guard(benchmark_fn or _benchmark),
        # Cheap pre-check so a truncated / prose answer is never compiled, never
        # written over the .cpp, and never fed back into the fix round.
        "validate_fn": optimizer_knowledge.implausible_reason,
        "round_meta_fn": round_meta_fn,
        "round_cb": round_cb,
    }
    # Withheld unless asked for: with the sink absent the engine never calls it,
    # `history` stays [], and every round renders the same prompt it does today.
    if _history_enabled():
        ad["history_sink"] = history_sink
    return ad


def parity_fn_from_verify(verify_fn, type_name, spec):
    """Adapt the pipeline's own parity verify into an engine ``parity_fn``.

    ``verify_fn(bundle, rows) -> {type_name: {ran, pass, maxerr, reason}}`` is the
    exact contract of ``verify.subprocess_verify_fn`` -- the compiled-vs-Python
    check the build already runs. Reusing it means the optimizer's 'correct' is
    the SAME correctness the build guarantees. A verify that did not run (no
    reference, no Maya) is SKIP, never a pass -- so the engine refuses to accept a
    candidate it cannot prove correct."""

    def _parity(bundle):
        rows = [{"type_name": type_name, "spec": spec}]
        res = verify_fn(bundle, rows) or {}
        r = res.get(type_name, {})
        if r.get("ran") and r.get("pass") is True:
            return ParityVerdict(PARITY_PASS, maxerr=r.get("maxerr"))
        if r.get("ran") and r.get("pass") is False:
            return ParityVerdict(PARITY_FAIL, maxerr=r.get("maxerr"),
                                 reason=r.get("reason") or "parity mismatch")
        return ParityVerdict(PARITY_SKIP,
                             reason=r.get("reason") or "verify did not run")

    return _parity


def _fmt_elapsed(seconds):
    """Elapsed as ``43s`` / ``4m12s``. Raw seconds stopped being readable the
    moment the heartbeat started printing four-digit numbers."""
    s = max(0, int(seconds))
    return "%ds" % s if s < 60 else "%dm%02ds" % (s // 60, s % 60)


class _Heartbeat:
    """Emit a periodic 'still working' line to ``log_cb`` during a long, silent
    optimize step (#65 liveness).

    The LLM client only tees its streamed thinking/tool events to log_cb AFTER
    the subprocess finishes (it drains via ``communicate()``), so during a
    multi-minute -- or, with the timeout disabled, unbounded -- rewrite the log
    would otherwise stay silent and look hung. This daemon thread ticks every
    ``interval`` seconds so the user has certainty the agent is still working.

    The tick is scoped to the CURRENT phase: ``set_round`` renames it and
    RESTARTS its clock, so it reads ``round 3/8 -- benchmarking 4m12s`` instead
    of one counter climbing across the whole node (it reached 5656s, and ~370
    lines, on one run). The caller drives that off the engine's existing
    ``round_cb`` -- the engine stays thread-free.

    A round is NOT one long AI call: it is propose -> build -> parity ->
    benchmark, and only the first is the model. Labelling the whole round "AI
    working" produced ticks like ``round 5/8 -- AI working 10m23s`` printed
    minutes AFTER the round's own "trying: ..." line proved the call had
    returned -- and past the 9m budget it claimed to be timing. ``set_phase``
    is the sub-phase, pushed by whichever adapter is running (see
    ``_wrap_phases``), which is the only place that knows.
    Stops on ``__exit__``; no-op when ``log_cb`` is None."""

    def __init__(self, log_cb, label, interval=300.0):
        self._log_cb = log_cb
        self._tag = ("[%s] " % label) if label else ""
        self._interval = interval
        self._stop = threading.Event()
        self._thread = None
        self._round = "baseline"
        # (phase text, phase start) as ONE attribute, so the ticking thread can
        # never pair a freshly-set phase with the previous phase's clock.
        self._phase = ("baseline -- measuring", time.time())

    def set_round(self, index, total):
        """Name the round that is about to run; restart the elapsed clock."""
        if index > total:
            # There is no round N+1: what still runs is the tail of the round
            # that just resolved (the version writer) and the engine's return
            # path. Holding the final round's name over it claimed a round that
            # was already over, and with `rounds=0` the label never left baseline.
            self._round = ""
            self.set_phase("finishing up")
            return
        self._round = "round %d/%d" % (index, total)
        self.set_phase("AI working")

    def set_phase(self, text):
        """Name the sub-phase inside the current round; restart the clock.

        The clock restarts because the number is only honest as "how long has
        THIS been running"; carried across sub-phases it reported the round's
        age against the sub-phase's name.
        """
        self._phase = (("%s -- %s" % (self._round, text)) if self._round
                       else text, time.time())

    def _emit(self, text):
        try:
            self._log_cb(text)
        except Exception:
            pass

    def __enter__(self):
        if self._log_cb is not None:
            # Beat once at t=0: the baseline compile + calibration ladder runs for
            # minutes before the engine narrates anything, and the dialog lights
            # its "AI optimize" checkpoint on the first optimize line to arrive.
            self._emit("%soptimizing -- measuring baseline" % self._tag)
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def _run(self):
        while not self._stop.wait(self._interval):
            phase, started = self._phase
            self._emit("%s%s %s" % (self._tag, phase,
                                    _fmt_elapsed(time.time() - started)))

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        return False


# One optimize round, by the adapter that runs each part of it. The engine calls
# these in order (propose -> build -> parity -> measure), so tagging them where
# they are INJECTED is the sub-phase signal -- no new engine callback, no thread
# in the pure module, nothing to keep in sync but this table.
_ADAPTER_PHASES = (("optimize_fn", "AI working"),
                   ("fix_fn", "AI repairing the build"),
                   ("compile_fn", "building C++"),
                   ("parity_fn", "checking parity"),
                   ("benchmark_fn", "benchmarking"))


def _wrap_phases(adapters, hb):
    """Make each adapter announce the heartbeat sub-phase it is entering.

    Mutates ``adapters`` in place (it is the dict this call site owns and is
    about to splat into the engine). An adapter the factory did not supply is
    left alone.
    """
    def _wrap(fn, phase):
        def _call(*args, **kwargs):
            hb.set_phase(phase)
            return fn(*args, **kwargs)
        return _call

    for key, phase in _ADAPTER_PHASES:
        fn = adapters.get(key)
        if fn is not None:
            adapters[key] = _wrap(fn, phase)


_SLUG_OK = re.compile(r"[^A-Za-z0-9_]+")


def _slugify(text, fallback):
    """A short, filename-safe theme name. Empty/None falls back to the outcome."""
    slug = _SLUG_OK.sub("_", (text or "").strip()).strip("_").lower()
    return (slug or _SLUG_OK.sub("_", fallback).strip("_").lower())[:40]


def make_version_writer(out_dir, type_name, keep_bundles=False):
    """A ``round_cb`` that keeps one ``.cpp`` per optimize round on disk.

    ``build/stages/<Type>/3_optimized/NN_<slug>.cpp`` -- zero-padded index so the
    directory reads in the order the work happened, slug so it reads as a story
    (``00_baseline`` -> ``01_hoist_invariant`` -> ``02_soa_split``). Rejected
    rounds are kept too: an attempt that measured SLOWER is the most transferable
    thing an optimization run produces, and it used to be overwritten.

    ``00_baseline.cpp`` is also the rollback source, replacing the transient
    ``<cpp>.preopt`` (which lived in the per-node scratch dir and was deleted
    with it on a successful build).

    ``keep_bundles`` additionally copies the round's compiled plug-in next to
    its source (``NN_<slug>.bundle``), so a reader can LOAD round 3 rather than
    read it. Off by default: ~90 KB per round, and the source plus the ledger
    are what is worth keeping unconditionally.
    """
    # Lazy, matching this module's convention (it is the live-binding layer and
    # keeps its heavier imports inside the functions that need them).
    from mpynode.native.compiler import bundler

    d = os.path.join(bundler.stage_dir_for(out_dir, type_name), "3_optimized")

    def _keep_bundle(record, stem):
        """Copy the round's binary out of the scratch dir before it is reused.

        Best-effort: keeping a souvenir must never fail the round that earned
        it. The plug-in is a DIRECTORY on macOS (.bundle) and a file elsewhere.
        """
        src = getattr(record, "bundle", None)
        if not src or not os.path.exists(src):
            return
        dst = os.path.join(d, stem + os.path.splitext(src)[1])
        try:
            if os.path.exists(dst):
                (shutil.rmtree(dst, ignore_errors=True) if os.path.isdir(dst)
                 else os.remove(dst))
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        except OSError:
            pass

    def _write_marker(record):
        """Account for a round that filed no source, under its own index.

        Best-effort like ``_keep_bundle``: the directory reading well must
        never cost the round that earned it.
        """
        try:
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "%02d_no_change.txt" % record.index)
            with open(path, "w") as fh:
                fh.write("round %d: no-change -- the candidate was identical "
                         "to the source this round was given, so there is no "
                         ".cpp of its own to keep. See rounds.json.\n"
                         % record.index)
            return path
        except OSError:
            return None

    def _write(record, cpp_text):
        if not cpp_text:
            return None
        # A no-change round produced no source of its own: `cpp_text` IS the
        # incumbent, byte for byte. Kept as a .cpp it was a duplicate of
        # 00_baseline.cpp (or of the last accepted round) filed under the slug
        # the agent CLAIMED -- 01_simd_lanes.cpp for work that never happened,
        # and a duplicate md5 for anyone auditing the directory. Dropped
        # outright it left 00 -> 02, which reads as a file someone deleted. A
        # marker keeps the index continuous and cannot be mistaken for source:
        # it is not a .cpp, so neither the REPORT.md listing nor the build
        # runner's `_round_cpps` (both .cpp-only) so much as see it.
        if record.outcome == "no-change":
            return _write_marker(record)
        try:
            os.makedirs(d, exist_ok=True)
            stem = "%02d_%s" % (record.index,
                                _slugify(record.slug, record.outcome))
            path = os.path.join(d, stem + ".cpp")
            with open(path, "w") as fh:
                fh.write(cpp_text)
        except OSError:
            return None
        if keep_bundles:
            _keep_bundle(record, stem)
        return path

    return _write


def write_rounds_json(out_dir, type_name, result, *, parity_gate=""):
    """The machine-readable ledger behind the node's REPORT.md.

    ``parity_gate`` records WHICH gate judged these rounds. That single field is
    the difference between a report that documents a verified speedup and one
    that documents an unverified one -- a node whose pointwise parity SKIPs is
    judged only by its authored @maya_test, and a reader has to be told so.
    """
    from mpynode.native.compiler import bundler

    rows = []
    for r in getattr(result, "ledger", []) or []:
        rows.append({
            "index": r.index, "outcome": r.outcome, "slug": r.slug,
            "theme": r.theme, "hypothesis": r.hypothesis,
            "predicted_speedup": r.predicted_speedup, "risk": r.risk,
            "compiled": r.compiled, "parity": r.parity, "ms": r.ms,
            "speedup": r.speedup, "fix_rounds": r.fix_rounds,
            "duration_s": r.duration_s, "note": r.note,
        })
    doc = {
        "type_name": type_name,
        "accepted": bool(getattr(result, "accepted", False)),
        "baseline_ms": getattr(result, "baseline_ms", None),
        "best_ms": getattr(result, "best_ms", None),
        "speedup": getattr(result, "speedup", 1.0),
        "rounds": getattr(result, "rounds", 0),
        "reason": getattr(result, "reason", ""),
        "parity_gate": parity_gate,
        "created": time.time(),
        "ledger": rows,
    }
    try:
        d = bundler.stage_dir_for(out_dir, type_name)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "rounds.json")
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")
        return path
    except OSError:
        return None


def rollback_preopt(cpp_paths):
    """Restore the pre-optimization ``.cpp`` for any accepted node whose backup
    (``<cpp>.preopt``, written by ``optimize_surviving`` before it overwrote the
    file) still exists (#66 fallback). Moves the backup back over the shipped
    file (atomically, also consuming the backup) so the build reverts to the
    deterministic transpiler output. Returns the list of restored cpp paths."""
    restored = []
    for cpp in cpp_paths or []:
        bak = cpp + ".preopt"
        if os.path.exists(bak):
            try:
                os.replace(bak, cpp)
                restored.append(cpp)
            except Exception:
                pass
    return restored


def discard_preopt(cpp_paths):
    """Remove leftover ``<cpp>.preopt`` backups after the build has committed to
    the optimized output (a successful final assemble). Best-effort."""
    for cpp in cpp_paths or []:
        bak = cpp + ".preopt"
        if os.path.exists(bak):
            try:
                os.remove(bak)
            except Exception:
                pass


def optimize_surviving(nodes, out_dir, *, maya=None, verify_fn=None,
                       complete_fn=None, run_step=None, cancel_event=None,
                       log_cb=None, compile_log_cb=None, rounds=2,
                       min_speedup=1.05, bench_res=16,
                       out_plug=None, adapters_factory=None, engine=None,
                       keep_intermediates=False, status_out=None,
                       provider=None):
    """Run the gated optimizer over each surviving node's finalized ``.cpp``.

    ``nodes`` is an iterable of ``(type_name, cpp_path, spec)``. ``out_dir`` is the
    node output ROOT -- the same thing ``stage_report.write_reports`` takes, NOT
    the ``build/`` dir: both paths taken from it here go through ``bundler``, which
    appends ``build/`` itself. Handing it ``build/`` instead put the durable audit
    trail at ``build/build/stages/``, where the report generator never looks.

    For each node the
    optimizer proposes/compiles/verifies/benchmarks candidates in an isolated
    scratch dir; ONLY on accept is the node's ``cpp_path`` overwritten with the
    winner (transform-or-passthrough, mirroring the (c.5) VP2 injection). Parity
    is gated by ``verify_fn`` (the pipeline's own subprocess verify) so a wrong
    rewrite can never ship; without a ``verify_fn`` parity is SKIP and nothing is
    accepted. A per-node error is isolated -- it never aborts the other nodes or
    the build. Returns ``{type_name: OptimizeResult}`` (only nodes that ran).

    A user Cancel is the one thing that DOES stop the loop: the node in flight is
    abandoned (nothing is written back -- only an accept overwrites ``cpp_path``)
    and the nodes after it are never started, so neither appears in the returned
    dict. That is the same shape as a per-node error, which also leaves the node
    out; the caller then sees the cancel through its own ``cancel_event``.

    ``log_cb`` receives ONLY the engine's high-level narration (baseline /
    ACCEPT / reject reasons). The noisy per-line streams (raw compiler output +
    AI chain-of-thought) go to ``compile_log_cb`` -- a SEPARATE channel that
    defaults off, so a dialog that only wants the narration story isn't flooded
    line-by-line (the flood the compile-hook used to funnel through ``log_cb``).

    ``adapters_factory`` / ``engine`` are injectable for tests; they default to
    ``make_adapters`` and ``optimizer.optimize_cpp``.

    ``provider`` is the run's AI provider, forwarded to ``make_adapters`` so the
    agent pre-flight there answers for the SAME provider the caller's budget
    gate pre-flighted. ``None`` = resolve from prefs, as before.

    ``status_out`` (optional dict) is filled with ``{type_name: {...}}`` saying
    what the AI actually did per node -- see ``make_adapters``. It is filled for
    EVERY node started, including one that errored out and so is absent from the
    returned results: "the optimizer never ran here" is exactly the case the
    caller has to be able to see.
    """
    from mpynode.native.compiler import bundler

    from .optimizer import optimize_cpp
    make = adapters_factory or make_adapters
    run = engine or optimize_cpp
    results = {}

    def _note(msg):
        if log_cb is not None:
            try:
                log_cb(msg)
            except Exception:
                pass

    for (type_name, cpp_path, spec) in nodes:
        # Between nodes. Without this the next node still pays a full baseline
        # compile + benchmark (minutes) before its first model call notices the
        # cancel, because only the model-calling adapters are cancel-guarded.
        if cancel_event is not None and cancel_event.is_set():
            _note("optimize cancelled before %s" % type_name)
            break
        node_status = {"rounds": 0, "candidates": 0, "errors": []}
        if status_out is not None:
            status_out[type_name] = node_status
        try:
            with open(cpp_path) as fh:
                baseline = fh.read()
            scratch = os.path.join(bundler.build_dir_for(out_dir),
                                   OPT_SCRATCH_DIRNAME, type_name)
            os.makedirs(scratch, exist_ok=True)
            pf = (parity_fn_from_verify(verify_fn, type_name, spec)
                  if verify_fn is not None else None)
            ad = make(spec, scratch, maya=maya, node_type=type_name,
                      out_plug=out_plug, parity_fn=pf, complete_fn=complete_fn,
                      run_step=run_step, cancel_event=cancel_event,
                      log_cb=compile_log_cb, bench_res=bench_res,
                      status_out=node_status, provider=provider)
            # Keep one .cpp per round under build/stages/<Type>/3_optimized/,
            # including the rejects. Durable, unlike the scratch dir this runs in.
            version_cb = make_version_writer(out_dir, type_name,
                                             keep_bundles=keep_intermediates)
            # The engine takes ONE round_cb and the adapters ship their own, so it
            # is popped and chained here (left in `ad` it collides with the keyword
            # below). The adapters' hook goes FIRST because it cannot raise and
            # version_cb can, and _emit_round swallows the whole callback anyway.
            state_cb = ad.pop("round_cb", None)
            n_rounds = _optimize_rounds(rounds)
            hb = _Heartbeat(log_cb, type_name)
            _wrap_phases(ad, hb)

            def round_cb(record, cpp_text):
                if state_cb is not None:
                    state_cb(record, cpp_text)
                # Round N resolved => round N+1 owns the silence that follows.
                # This is the boundary the engine ALREADY reports, so the
                # heartbeat rides it instead of the engine growing a clock.
                hb.set_round(record.index + 1, n_rounds)
                version_cb(record, cpp_text)

            with hb:
                res = run(baseline, rounds=n_rounds,
                          min_speedup=min_speedup, round_cb=round_cb,
                          label=type_name, log_cb=log_cb, **ad)
            write_rounds_json(out_dir, type_name, res,
                              parity_gate=("authored+pointwise" if verify_fn
                                           else "none"))
            if res.accepted:
                # Back up the deterministic original BEFORE overwriting, so the
                # controller can restore it if the accepted candidate later fails
                # the FINAL (multi-node) assemble (#66).
                try:
                    shutil.copy2(cpp_path, cpp_path + ".preopt")
                except Exception:
                    pass
                with open(cpp_path, "w") as fh:
                    fh.write(res.best_cpp)
            results[type_name] = res
        except _OptimizeCancelled:
            # Mid-node. The candidate is abandoned unwritten (only an accept
            # overwrites cpp_path), so the node keeps its deterministic .cpp.
            _note("optimize cancelled during %s (kept original)" % type_name)
            break
        except Exception as exc:
            node_status["errors"].append(
                "optimize failed: %s: %s" % (type(exc).__name__, exc))
            _note("optimize %s failed (kept original): %s" % (type_name, exc))
    return results
