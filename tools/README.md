# `tools/`

Every dev/CI script lives here — there are no runners at the repo root. Nothing
in this directory is imported by the shipped `mpynode` package at import time,
with one exception noted below.

If you are just installing MPyNode, the only two you need are `run_tests.sh`
(verify the install) and, on a non-macOS host, `build_compiled_templates.sh`
(the shipped bundles are macOS-only).

## Gate launchers

| | macOS / Linux | Windows |
|---|---|---|
| Unit suite (~6,700 tests, ~9 min) | `tools/run_tests.sh [module ...]` | `tools\run_tests.bat [module ...]` |
| Compiled parity (12 types, ~6 min) | `tools/run_parity_sweep.sh` | `tools\run_parity_sweep.bat` |

Both pairs anchor on the repo root, not on `tools/`, and both hand the real exit
status back — mayapy's teardown forces exit 0 after
`maya.standalone.initialize()`, which is why every invocation goes through
`_unittest_exit.py` rather than `-m unittest`.

The parity sweep needs `.bundle` fixtures that are gitignored, so a fresh clone
cannot run it until `build_compiled_templates.sh` has run. It says so and exits
2 rather than reporting a column of `????`.

## Enforced by the unit suite

These 35 scripts are **not optional**. Deleting any one of them turns the unit
suite red: a test runs, imports or reads it, or checks that it is there. Each
row was measured by deleting the file in a copy of the tree and running the
tests that name it. Deleting any other script here turns no test red.

| Script | Enforced by |
|---|---|
| `check_stage1_freshness.py` | `test_stage1_codegen_freshness` — checked-in stage-1 C++ vs fresh transpiler output |
| `regen_build_scripts.py` | `test_build_script_freshness` — every committed `build.sh`/`.bat` vs today's generators |
| `regen_plugin_main.py` | `test_plugin_main_freshness` — every committed multi-node `plugin_main.cpp` vs today's generator, derived from the fragments beside it |
| `regen_verify_scripts.py` | `test_shipped_verify_scripts` — every shipped `verify_in_maya.py` vs today's generator, from its manifest row's spec |
| `check_std_includes.py` | `test_std_include_check` — a `std::` facility used with no include (libc++ forgives, MSVC does not) |
| `scan_command_mpynode_deps.py` | `test_command_mpynode_deps` — what an embedded `@maya_command` can still reach |
| `sync_harness_manifest.py`, `list_template_coverage.py` | `test_harness_manifest_coverage` — a template missing from the manifest is silently never audited |
| `migrate_attr_names.py` | `test_attr_type_table` — the attr type rename in each file kind, and that the repo is already migrated |
| `sweep_compile_one.py` | `test_optimizer_live` |
| `run_tests.sh`, `run_tests.bat` | `test_native_toolchain` — every mayapy call goes through `_unittest_exit.py`, both anchor on the repo root and hand back the real exit status |
| `run_parity_sweep.sh`, `run_parity_sweep.bat` | `test_native_toolchain` — the same, for the parity gate |
| `_unittest_exit.py` | `test_suite_home_isolation` — runs a test through it in a fresh process and checks that the run's data home is a temp folder; the two `run_tests` launchers cannot start the suite without it either |
| `parity_sweep/run_parity_sweep.py` | `test_native_compile_pipeline` (`TestParitySweepWiring`), `test_native_toolchain` |
| `parity_sweep/parity_<type>.py`, all 12 | `test_native_compile_pipeline` (`TestParitySweepWiring`) — each one is there and names no user's path |
| `harness/benchmark_node.py` | `test_bench_gate`, `test_benchmark_harness_lock`, `test_benchmark_harness_scene`, `test_optimizer_compile_hook`, `test_ai_unavailable_status`, `test_native_compile_pipeline` |
| `harness/demo_specs.py` | `test_harness_manifest_coverage` |
| `harness/optimize_node.py` | `test_optimize_node_driver` |
| `harness/idle_probe.py` | `test_idle_probe` — its Maya-free helpers |
| `harness/viewport_bench.py` | `test_viewport_bench` — its Maya-free helpers |
| `harness/rebench_shipped.py` | `test_rebench_shipped` — planning and record shape, no compile, no Maya |
| `harness/reverify_shipped.py` | `test_reverify_shipped` — the same |

`harness/templates.json` is not a script, but deleting it turns
`test_harness_manifest_coverage` red too.

`harness/benchmark_node.py` is also the one exception noted at the top: shipped
code shells out to it at runtime (`native/ai/optimizer_live.py` and
`optimizer_agent.py` hold its path in `_BENCHMARK_SCRIPT`). Move or rename it and
the six test modules in its row turn red, and the compile preflight
(`optimizer_live.benchmark_harness_problem`) refuses AI optimize up front with
the missing path named; the deterministic build still ships.

## Building the compiled templates

```bash
tools/build_compiled_templates.sh [--smoke] [--only voxelize]
```

Walks `templates/` and compiles each one in place, into a `build/` tree inside
that template's own folder, farming each out to
`build_compiled_templates_worker.py` in its own mayapy.

## Bundling compiled nodes

| | macOS / Linux | Windows |
|---|---|---|
| Combine compiled node sources into one plug-in | `tools/bundle.sh NAME INPUT...` | `tools\bundle.bat NAME INPUT...` |

Both find a mayapy (`MPYNODE_MAYAPY`, then `MAYA_LOCATION`, then the newest
install with a devkit) and run `mpynode.native.bundle` under it -- `--help`
lists the input forms and options, `--check` runs every pre-flight check and
writes nothing, `--refresh DIR` rebuilds a bundle from the inputs its manifest
records. The plug-in lands in `--out DIR/<maya year>/NAME.mll` (`.bundle` on
macOS) -- the version is the folder, never part of the file name. The tree it
writes rebuilds with its own `build/build.bat` / `build.sh`, which need only a
compiler and Maya.

## Data migrations

```bash
python tools/migrate_attr_names.py            # dry run: what would change, per file and per name
python tools/migrate_attr_names.py --apply    # rewrite in place
```

`migrate_attr_names.py` translates every `attr_type` that is not a stored
name to its stored name, in the repo's own data: the aliases
(`attr_types.ALIASES`: `int` -> `long`, `vector` -> `double3`, `angle` ->
`doubleAngle`, `float64` -> `double` ...) and the retired names
(`attr_types.RETIRED`: `python` -> `pickle`). It reads that map from
`attr_types.py` by path, so it follows the table. It covers every git-tracked
`template.mpn`, `.ma` scene, template build manifest, spec fixture and
generated `verify_in_maya.py`; in a verify script's generated code only the
old stored names (`int`, `vector`, `angle`, `python`) are renamed as bare
literals, never a dict key (an attr name) or a keyword argument's value
(`initialize(name="python")`). Each rewrite is a token replacement, re-parsed
and checked so the type value is the only change. Plain Python 3, no Maya.

Repo-only: it never touches a scene or `.mpn` outside the repo. Those load as
they are, aliases included, and a scene that stored `python` still computes,
its map translated on read. The one exception is an `.mpn` naming `python`:
it is rejected with the replacement named, so rename it to `pickle`.
Idempotent: a dry run after `--apply` reports 0.

## Attended probes and gates

Run by hand when investigating the thing they name; none is wired into a script.
Each answers one question:

| Script | Question |
|---|---|
| `audit_name_clashes.py` | Which templates collide in the two flat namespaces a merged plug-in writes into? |
| `gate_bundled_commands.py` | Does a `@maya_command` really become a callable `MPxCommand` inside the node's own bundle? |
| `probe_locator_parity.py` | Does the deterministic draw lowering draw what the Python expression drew? |
| `probe_pinned_typeid_end_to_end.py` | Does a manual `type_id` pin actually reach the compiled binary? |
| `probe_spec_determinism.py` | Why does the port cache miss every LLM-ported node on a rebuild? |
| `verify_forport_false_stub.py` | Does the `for_port=False` branch emit a stub that really compiles and loads? |

`harness/` holds the heavier attended drivers — the per-template audit, the
combined plug-in set, the VP2 probes and the optimizer benchmark. See
`harness/README.md`.

`parity_sweep/` holds the runner and the twelve per-type `parity_<type>.py`
checks behind the parity gate. The runner builds those filenames dynamically
(`"parity_%s.py" % t`), so grep for the stem will not find them.
