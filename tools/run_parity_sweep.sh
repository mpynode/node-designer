#!/usr/bin/env bash
#
# Pre-release gate: re-verify COMPILED native parity for all 12 basic mPyNode
# types against their built .bundles (no rebuild, no porter, no LLM). Exits 0
# only if all 12 pass -- wire this into CI / run before tagging a release.
#
#   bash tools/run_parity_sweep.sh
#
# Each type is verified in its own isolated mayapy subprocess (so the bundles
# never share a Maya runtime / MTypeId space). Override MAYAPY to target a
# different Maya (defaults to Maya 2026 on macOS). Runtime ~6 min.
#
# The .bundle fixtures are NOT committed (.gitignore: *.bundle), so a fresh
# clone has to build them first -- see tools/parity_sweep/run_parity_sweep.py,
# which says so and exits before spending six minutes proving it.
#
# See tools/parity_sweep/ for the runner and per-type parity_*.py checks.
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERE="$(cd "$TOOLS_DIR/.." && pwd)"
export MPYNODE_ROOT="$HERE"
export MAYAPY="${MAYAPY:-/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy}"
# T38: the fixtures are .ma scenes full of MPyNode Python, and headless can't
# show the trust prompt -- without this opt-in the INTERPRETED side of every
# comparison stops computing and the sweep reports a bogus FAIL. Inherited by
# the per-type mayapy subprocesses.
export MPYNODE_TRUST_PICKLE=1

exec "$MAYAPY" "$TOOLS_DIR/parity_sweep/run_parity_sweep.py"
