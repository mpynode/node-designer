# `tools/harness/` — out-of-suite mayapy drivers

Nothing here runs in `tools/run_tests.sh`. These are attended drivers: they
compile templates with the AI porter, build Maya scenes, render VP2 frames and
link the combined plug-in — minutes to hours each, and several cost API calls.
The unit suite covers their *logic*; these prove the end-to-end result.

Because they are attended, most are not reachable from any script. That is
deliberate, and it is also how three of them rotted unnoticed before (they were
deleted). If you add one, give it a `Usage:` line and list it below, or the next
audit will read it as dead.

Every driver expects the standard env. From the repo root:

```bash
export MPYNODE_ROOT=$PWD MPYNODE_USE_STUDIO=1 \
       PYTHONPATH=$PWD/scripts MAYA_PLUG_IN_PATH=$PWD/plug-ins \
       QT_QPA_PLATFORM=offscreen MPYNODE_TRUST_PICKLE=1
MAYAPY=/Applications/Autodesk/maya2026/Maya.app/Contents/MacOS/mayapy
```

## Per-template audit — one plug-in per template

`run_all.py` is the orchestrator; it iterates `templates.json` (not the
templates tree — `tools/sync_harness_manifest.py` keeps the two in step) and
runs each step in an isolated fresh mayapy.

```bash
python3 tools/harness/run_all.py [folder1 folder2 ...]   # all, or a subset
python3 tools/harness/audit_summary.py master_results.json
```

It shells out to `compile_one.py` (compile one `.mpn`), `build_demo_compiled.py`
(build the demo scene and swap in the compiled type) and `reopen_check.py`
(reopen the saved `.ma` in a fresh process and confirm the type still loads).
Those three are also usable on their own.

## Combined plug-in — every template in ONE bundle

The counterpart set, for `templates/All Templates Plugin/`. `run_all_mega.py`
assumes the bundle already exists; `mega_plugin.py` is what builds it.

```bash
"$MAYAPY" tools/harness/mega_plugin.py "templates/All Templates Plugin"
python3   tools/harness/run_all_mega.py [folder1 ...]
"$MAYAPY" tools/harness/mega_loadtest.py "templates/All Templates Plugin"
"$MAYAPY" tools/harness/mega_verify.py <bundle> <results_json> <out_dir> <asset_png>
```

`mega_loadtest.py` is the strongest of these: it proves the one bundle registers
every node type *and* every `@maya_command`, instantiates each type, runs a
command end to end, and unloads without stranding a name — and it derives the
expected command names from the source templates, so it cannot pass by agreeing
with the emitter. `build_demo_mega.py` / `reopen_check_mega.py` are the mega
forms of the two `run_all.py` helpers and are driven by `run_all_mega.py`.

Setting `MPYNODE_MEGA_FROM_ARTIFACTS=1` links the per-template artifacts already
in `templates/` instead of re-porting every `.mpn`.

## Benchmark and optimizer

`benchmark_node.py` is the only file here that shipped code depends on: the AI
optimizer shells out to it at runtime (`native/ai/optimizer_live.py`,
`optimizer_agent.py` — both hold its path in `_BENCHMARK_SCRIPT`). Moving or
renaming it silently turns every optimization "unmeasurable", with no error.

```bash
"$MAYAPY" tools/harness/benchmark_node.py <bundle> <node_type> [--out outMesh]
python    tools/harness/optimize_node.py --source build/source/metaClay.cpp \
              --spec spec.json [--parity metaballs_parity.py] [--apply]
```

`metaballs_parity.py` and `skin_twist_swing_dual_parity.py` are the two
template-specific parity checks an optimizer run can be pointed at with
`--parity`, for nodes the generic verify can only mark INCONCLUSIVE.

Three honesty rules, all measured into existence on 2026-09-08. The harness
refuses a node with nothing to perturb between ticks (every tick would re-time
a cache hit; `--allow-unperturbed` overrides), and it moves one element of
every animated numeric input plus one vertex of every animated geometry input
per tick -- inputs named rest/bind/base/orig/ref/initial stay put, so caching
keyed on a rest cage is still rewarded. Through the optimizer, a baseline
still below `MPYNODE_BENCH_FLOOR_MS` (15 ms) at the largest scene rung is
unmeasurable, not a speed target. `--fingerprint-out FILE` dumps every pulled
output after warm-up so the optimizer can reject a candidate whose outputs
differ from the baseline's on the same scene (ledger outcome `bench-diverged`).

## Live-session measurements (Script Editor, not mayapy)

A locator's cost is its draw override, which no headless benchmark reaches
(`ogsRender` never executes UI drawables), and the cost that matters for a gizmo
is "what happens to my scene when I have fifty of these". Two scripts answer
that inside an interactive Maya; both refuse to run in batch.

| Script | Question |
|---|---|
| `viewport_bench.py` | Cost PER redraw: N copies of a node (interpreted from a `.mpn`, compiled from a plug-in, or both), `refresh(force=True)` timed over F frames → ms/refresh, ms/copy. |
| `idle_probe.py` | Cost AT IDLE: with N copies in the scene and nobody touching Maya, redraws/s and main-thread CPU % over a window; configs for compiled, interpreted (optionally with a patched expression) and Mesh Regions on its head, with an optional cursor sweep for hover-driven gizmos. |

```python
import viewport_bench, idle_probe          # scripts/ + tools/harness/ on sys.path
viewport_bench.run(compiled_type="animatedText", plugin=PLUG, copies=(1, 10, 50, 100), frames=60)
idle_probe.run([idle_probe.compiled_config("cpp", "animatedText", plugin=PLUG)], seconds=10)
```

Both were written for the 2026-09 locator draw-cost pass (whole-pixel point sizes,
one drawable batch per node, the CPU-metered idle-refresh throttle) and are how
its numbers are re-checked. Their Maya-free helpers are unit-tested
(`tests/compile/optimizer/test_viewport_bench.py`, `test_idle_probe.py`).

## VP2 probes

Headless viewport rendering is fragile, so these escalate from "can this mayapy
render anything at all" to "does this texture display correctly".

| Script | Question |
|---|---|
| `vp2_diag.py` | Can this headless mayapy produce a non-black VP2 frame at all? |
| `vp2_probe.py` | Does the shipped texture rig display (baseline + fix gate)? |
| `vp2_probe_any.py` | Same, for an arbitrary bundle + texture node. |
| `mpyfile_image_parity.py` | Full mPyFile parity by image: bake every channel, render 1:1, diff. |

All four share the plane + unlit-`surfaceShader` + `ogsRender` rig that
`benchmark_node.py:_bake_pull` copies (it copies rather than imports because
each parses `sys.argv` at import and so cannot be used as a library).

## Support files

`templates.json` is the audit manifest — the list `run_all.py`, `mega_plugin.py`
and `reopen_check.py` iterate. `demo_specs.py` is an import-safe AST mirror of
`node_setups.find_demos`, needed because the orchestrators run under plain
`python3` and cannot import `mpynode` or `maya`.
