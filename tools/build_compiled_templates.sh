#!/usr/bin/env bash
# Launcher for tools/build_compiled_templates.py under mayapy 2026.
# Mirrors the env tools/run_tests.sh uses, plus the optimizer knobs.
#
#   tools/build_compiled_templates.sh --smoke --only voxelize
#   tools/build_compiled_templates.sh --jobs 8 --opt-jobs 8
#
# The orchestrator itself does no Maya work -- it fans out one mayapy WORKER per
# template (tools/build_compiled_templates_worker.py). Phase A (transpile + AI
# assist + compile) is untimed and runs --jobs wide; phase B (optimizer) runs
# --opt-jobs wide with its benchmarks serialised on MPYNODE_BENCH_LOCK.
#
# Long-running: a full 43-template phase B is measured in HOURS. Run it under
# caffeinate on AC, and never alongside another benchmark -- the lock only
# covers processes that honour it.
set -uo pipefail
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$TOOLS_DIR/.."

MAYAPY="/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy"
export MPYNODE_USE_STUDIO=1 QT_QPA_PLATFORM=offscreen
export MPYNODE_ROOT="$PWD"
# numpy/scipy/PIL live outside Maya on some setups. Point
# MPYNODE_EXTRA_PYTHONPATH at that site-packages dir if you need them.
# APPEND only -- prepending shadows Maya's own numpy and breaks the
# ndarray tests (ptp/itemset were removed from ndarray in NumPy 2.0).
export PYTHONPATH="$PWD/scripts${MPYNODE_EXTRA_PYTHONPATH:+:$MPYNODE_EXTRA_PYTHONPATH}"
export MAYA_PLUG_IN_PATH="$PWD/plug-ins"

# The orchestrator spawns workers with this interpreter.
export MPYNODE_MAYAPY="$MAYAPY"

# Pinned so generated C++ is byte-stable across processes. Unpinned, set
# iteration order varies per interpreter, the emitted C++ differs run to run,
# and the port cache misses every node on every rebuild.
export PYTHONHASHSEED=0

# The default port cache lives under ~/mpynode/, which is unwritable on this
# machine: every put() EPERMs, compile_controller swallows it, and phase B then
# misses the entry phase A was supposed to have warmed -- so an AI-ported node
# re-ports from scratch and can hit the porter's 600s timeout. Same redirect
# tools/av_run_probe.sh and tools/sweep_models_run.py already use. The typeid
# registry is deliberately NOT redirected: it only needs to be WRITTEN when a
# node wants a brand-new id, and reads of the real one work fine.
export MPYNODE_PORT_CACHE="${MPYNODE_PORT_CACHE:-$PWD/.mpynode_local/port_cache}"

# 2 optimize rounds per node, per the user's decision.
export MPYNODE_OPT_ROUNDS="${MPYNODE_OPT_ROUNDS:-2}"

# Phase B's optimizer runs the Claude CLI AS AN AGENT, and granting it Bash makes
# the CLI install its own shell sandbox -- which cannot nest inside one we are
# already in. Unset, the agent dies at startup, check_agent() refuses, and every
# node silently demotes to the one-shot text path: a full run that looks like it
# optimized and never gave the agent a tool. Same knob, same value, as
# tools/arm_experiment_run.py and tools/sweep_models_run.py.
export MPYNODE_OPT_AGENT_NO_SANDBOX="${MPYNODE_OPT_AGENT_NO_SANDBOX:-1}"

# Phase B runs many agents at once but only ONE benchmark at a time. The lock
# itself lives in scripts/; this only names the file every worker shares. Unset
# it and the lock is a no-op -- which is only safe for a serial run.
export MPYNODE_BENCH_LOCK="${MPYNODE_BENCH_LOCK:-$PWD/_build_state/.bench.lock}"

exec "$MAYAPY" "$TOOLS_DIR/build_compiled_templates.py" "$@"
