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

These are **not optional**. A test executes or imports each one, so deleting any
of them turns the suite red.

| Script | Enforced by |
|---|---|
| `check_stage1_freshness.py` | `test_stage1_codegen_freshness` — checked-in stage-1 C++ vs fresh transpiler output |
| `regen_mega_transpiled.py` | `test_mega_stage1_freshness` — same, for the combined plug-in tree |
| `regen_build_scripts.py` | `test_build_script_freshness` — every committed `build.sh`/`.bat` vs today's generators |
| `check_std_includes.py` | `test_std_include_check` — a `std::` facility used with no include (libc++ forgives, MSVC does not) |
| `scan_command_mpynode_deps.py` | `test_command_mpynode_deps` — what an embedded `@maya_command` can still reach |
| `sync_harness_manifest.py`, `list_template_coverage.py` | `test_harness_manifest_coverage` — a template missing from the manifest is silently never audited |
| `build_compiled_templates.sh` | `test_shipped_artifact_freshness` |
| `sweep_compile_one.py` | `test_optimizer_live` |
| `_unittest_exit.py` | `test_native_toolchain` |
| `harness/benchmark_node.py`, `harness/compile_one.py`, `harness/optimize_node.py`, `harness/demo_specs.py` | see `harness/README.md` |

`harness/benchmark_node.py` is the exception mentioned above: shipped code shells
out to it at runtime (`native/ai/optimizer_live.py` and `optimizer_agent.py` hold
its path in `_BENCHMARK_SCRIPT`). Move or rename it and every optimization
silently becomes "unmeasurable" — no error, no failing test.

## Building the compiled templates

```bash
tools/build_compiled_templates.sh [--smoke] [--only voxelize]
```

Mirrors `templates/` into `compiled_templates/` and compiles each one, farming
each template out to `build_compiled_templates_worker.py` in its own mayapy.

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
