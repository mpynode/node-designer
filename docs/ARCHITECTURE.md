# MPyNode Architecture

For developers who want to understand the system or contribute to it. Paths are
repo-relative; jargon is defined the first time it appears.

MPyNode is two Maya plug-in files plus a pure-Python package that register **12
real MPx\* node types** whose `compute()` body is a Python source string stored
on the node's own `_computeSource` plug. On top sits a Qt authoring window (the
Node Designer); underneath sits a compiler that turns a finished Python node
into a distributable C++ Maya plug-in whose compute contains **no Python**.

## 1. The big picture

```text
 ┌──────────────────────┐   INTERPRETED NODE: a live Maya node. Attributes declared
 │ _initSource          │   at RUNTIME (19 wire types); compute() is a Python string
 │ _computeSource       │   on a plug. DG callbacks synthesise the attributeAffects
 │ _methodsSource       │   Maya cannot declare for runtime attrs
 │ _storedVarsData      │   (_common/plugs/auto_dirty.py).
 └─────────┬────────────┘
           │ native/spec/spec_extractor.py :: extract_spec(node)
           v
 ┌──────────────────────┐   SPEC, a plain dict, SCHEMA_VERSION 1: MPx base + type
 │ base, type_name      │   name, ORDERED input/output attr maps, all four source
 │ inputs{}, outputs{}  │   tiers, stored-var summaries, commands/methods, metadata,
 │ init/compute/...     │   and a `portability` verdict (blockers => never ported).
 │ commands[], methods  │   This dict is the ONLY input to everything below.
 │ portability{}        │
 └─────────┬────────────┘
           │ native/toolchain/compile_controller.py :: compile_plugin(specs, ...)
           ├─ key = sha256(spec + provider + model + PORTER_RECIPE_VERSION)
           │    HIT ───────────────────────────────────┐ copyfile, codegen SKIPPED
           v    MISS                                   │
 ┌──────────────────────────────────────────────┐      │
 │ STAGE 1  1_transpiled.cpp  (always emitted)  │      │  node_scaffold.generate_cpp
 │  lowered  -> nd:: calls, nd_runtime.h INLINED│      │  via nd_lower.try_lower_*
 │  rejected -> marked PORT region, Python kept │      │  -> py_to_cpp AST walk
 │              as `//   | ...` comments        │      │
 └────────┬─────────────────────────────────────┘      │
          │ PORT_BEGIN present? no ────────────┐       │
          v yes                                │       │
 ┌──────────────────────────────────────────┐  │       │  native/ai/porter.py
 │ STAGE 2  2_assisted.cpp                  │  │       │  CLI LLM fills ONLY the
 │  compile -> <=4 fix rounds -> retry      │  │       │  PORT region; written LAST
 └────────┬─────────────────────────────────┘  │       │  = the compiler's source
          v <─────────────────────────────────-┘       │
 ┌──────────────────────────────────────────┐          │  agent edits a real
 │ STAGE 3  3_optimized/NN_<slug>.cpp       │          │  workspace in place; keep
 │  (opt-in)                                │          │  iff compiles AND parity
 └────────┬─────────────────────────────────┘          │  PASS AND < best/1.05
          v <───────────────────────────────────────---┘
 build/source/<ty>.cpp ─> bundler.assemble ──> clang++ / cl / g++ ──> .bundle|.mll|.so
  (the file that LINKS)   native/compiler/     toolchain.py          + manifest.json
  build/<ty>/ is per-node SCRATCH, swept on success
                                                                            │
 VERIFY: a THROWAWAY mayapy drives identical inputs on the Python node <─────┘
 and the C++ node and diffs the outputs. The live scene is never touched.
```

Two properties are load-bearing. **Translate-or-reject**: there is no
interpreter fallback in the generated C++ — every Python construct either lowers
to a proven `nd::` call or is hard rejected with a precise `UnsupportedSpec`,
and both paths ship pure C++ (`native/compiler/TRANSPILER.md`). **The spec is
the contract**: `build/manifest.json` embeds the full spec each node was keyed
with, so any artifact can be re-derived from disk with no compiler, no linker
and no AI — which is what makes the freshness gates (section 5) possible.

## 2. Repo layout

| Path | Holds |
|---|---|
| `scripts/` | The only Python root. Put it on `PYTHONPATH`; everything lives in `scripts/mpynode/`. |
| `plug-ins/` | The two Maya entry points: `mpynode_api1.py` (OpenMaya 1.0 node types) and `mpynode_api2.py` (OpenMaya 2.0). Put this dir on `MAYA_PLUG_IN_PATH`. |
| `templates/` | 37 shipped gallery templates, `templates/<Type>/<Name>/{template.mpn,description.md}` across all 12 node types — **and the compiled C++ for each one, in that same folder**: `<Type>/<Name>/build/` holds the generated sources, the full optimizer stage lineage and a `build.sh`/`build.bat` beside them, so everything for one template is in one place. 39 per-template build trees (40 node `.cpp` files — `MPyLocator/Mesh Regions` ships two types). Sources + stage lineage are committed; binaries are not. |
| `templates/All Templates Plugin/` | The multi-node build tree that links every template into one plug-in, plus the turnkey demo around it: `build/` (37 namespaced fragments + the generated `plugin_main.cpp`, and the full stage lineage), 39 `.ma` demo scenes, `reports/`, and `plugin/` — where you build `mPyMega` (37/37 node types + 32 bundled commands). No binary is committed; its `build.sh` / `build.bat` compiles `build/` and installs the result into `plugin/`. The filename must stay `mPyMega.*` — Maya takes the plug-in name from it and the scenes `requires "mPyMega"`. |
| `tests/` | The unit suite, outside the package so shipping `scripts/mpynode/` does not ship the tests. 278 test modules grouped by area: `nodes/`, `ui/`, `authoring/`, `attributes/`, `framework/`, and `compile/` (split into `transpiler/`, `pipeline/`, `nodes/`, `optimizer/`, `freshness/`). Shared bootstrap `_setup.py`, repo anchors `_paths.py`, fixtures in `data/` and `test_assets/`. |
| `docs/` | All reference material: `index.md` (the API guide), `CHEATSHEET.md` (the authoring quick reference), this file, `PORTING.md` (Windows/Linux finish-and-verify handoff), and `node_types/` (one `.md` per type + `_input_type_contract.md`). Only `index.md` and `node_types/` are reachable from the in-app Help menu — `docs_locator` enumerates exactly those. |
| `tools/` | Every dev/CI script, and the only place they live — there are no runners at the repo root. The four gate launchers are `run_tests.sh` / `run_tests.bat` (unit suite) and `run_parity_sweep.sh` / `.bat` (compiled parity), plus `build_compiled_templates.sh`, the freshness checkers (`check_stage1_freshness.py`, `check_std_includes.py`, `regen_build_scripts.py`, `regen_mega_transpiled.py`), `parity_sweep/`, and the probes and audits. Most of these are not optional: thirteen are executed or imported by the unit suite, so deleting one turns tests red. `tools/harness/` holds the attended out-of-suite mayapy drivers (see its `README.md`), including `benchmark_node.py`, which the AI optimizer shells out to at runtime. |
| `icons/` | UI icons for the Node Designer. |
| `README.md`, `INSTALL.md`, `LICENSE.md` | The only docs at the root, and only because each is an entry point: the landing page, the two-env-var install, and the licence. Everything longer-form lives in `docs/`. `README.md` and `LICENSE.md` are additionally load-bearing — `docs_locator._repo_root_doc()` resolves them relative to the parent of `docs/` for the About dialog and the Help menu, so they cannot move. |
| `userSetup.py` | **Copy** (never symlink — `PROJECT_DIR` uses `abspath`, which does not follow links) into a Maya prefs `scripts/` dir, then set `MPYNODE_PROJECT_DIR`. Sets both paths, purges foreign `mpynode.*` modules from `sys.modules`. Skipped when `MPYNODE_USE_STUDIO=1`. |
| *(no runners at the root)* | The two gates' four launchers all live in `tools/`: `run_tests.{sh,bat}` and `run_parity_sweep.{sh,bat}`. They used to be split — the `.sh` unit runner in `tools/`, the other three at the root — which put `tools/run_tests.sh` and a bare `run_tests.bat` side by side in README's install check. |
| `_snapshots/`, `_snapshots.7z`, `.mpynode_local/` | Gitignored, machine-local. `_snapshots/` is ~39 GB of dated working copies; `.mpynode_local/` redirects the runtime data home (port cache, prefs, TypeId registry) when `~/mpynode` is unwritable. |

There is **no `.mod` file, no pip package and no installer**. Two environment
facts are the whole install: `MAYA_PLUG_IN_PATH` contains `plug-ins/` and
`sys.path` contains `scripts/`; plug-ins auto-load on first `create()` via
`_common/lifecycle/plugin_loader.py`. Everything MPyNode writes for a user
(`preferences.json`, `typeid_registry.json`, `trusted.json`, `port_cache/`,
`compiled/`) lives under one visible data home, resolved `MPYNODE_HOME` env ->
`scripts/mpynode/mpynode.ini` `[paths]` -> default `~/mpynode`
(`_common/home.py`, `_common/bootstrap.py`).

## 3. `scripts/mpynode` package map

| Package | Owns |
|---|---|
| `_common/` | The framework core — everything that is not UI, not a wrapper, and not the compiler. 13 sub-packages (below) plus `bootstrap.py` and `home.py`. |
| `native/` | The whole compile pipeline: transpiler, emitters, AI porter/optimizer, toolchain, spec extraction. |
| `ui/` | The Node Designer window and every widget, dialog and LLM client behind it. |
| `wrappers/` | The 12 public user-facing classes (`MPyNode`, `MPyDeformer`, …). This is the API users import. |
| `_api1/`, `_api2/` | The actual `MPx*` subclass implementations, split by Maya API generation. Never imported by users directly. |
| `_base/`, `_defaults/` | `commands.py` (create/duplicate/convert), `node_swap.py`, `node_callbacks.py`, `plugins.py`, `eval_helpers.py`; per-type starter content (`file_defaults.py`, three `skin_cluster_*_defaults.py`, `starter_registry.py`). |
| `_demos/` | **The template generator**, not sample code. `build_templates.py` (~711 KB) authors, runs and verifies every gallery template and writes it only when its verification passes. |
| `_node_registry.py`, `ndio.py`, `mpynode.ini` | Single source of truth for the 12 node types; compilable file IO usable from an expression; the ini (all keys shipped commented out) that is tier two of data-home resolution. |

### `_common/` sub-areas

| Sub-area | Owns |
|---|---|
| `compute/` | `compute.py`, `self_proxy.py` (the `self.X` read/write tier order), `expression.py`, `base_contract.py`, `output_defaults.py`, `user_input_seed.py`. |
| `plugs/` | 11 modules. `auto_dirty.py` + `dirty_affects.py` synthesise the `attributeAffects` Maya cannot declare for runtime attrs; `plug_read.py`/`plug_write.py`, `plug_governance.py`, `promoted_types.py`, `array_convert.py`. |
| `lifecycle/` | Plug-in loading, scene callbacks, trust prompt, the Init/Compute header generators, `init_registry.py` (Init runs once per file open; its names are bare globals in Compute), `metadata_registry.py` (Node Info + the baked `#` banner). |
| `methods/` | The Methods tier: `maya_command.py` (`@maya_command`/`@maya_demo`/`@maya_test` marker decorators), `methods_registry.py`, `test_helpers.py`, `outline_model.py`, plus per-family method sets (file/skin/morph). |
| `io/` | `mpn_io.py` (the `.mpn` round-trip format), `py_export.py` (the one-way `.py` bake), `value_codec.py`, `trust.py`, `content_hash.py`, `user_classes.py`. |
| `interface/`, `node_setups/` | Blessed method interfaces + `reserved_names.py` (what an attribute may not be called); per-node-type default `setup()` bodies, one module per family. |
| `storedvars/` | Persistent (saved with the scene) vs Temporary stored-variable store and its public API. |
| `draw/`, `osl/` | `mPyLocator` draw types/buffers; the OSL target (a connectable `.osl` string output, not an execution tier). |
| `instrumentation/` | Watch, cProfile encode/decode, exec runner, stats — what the Log/Watch/Profile tabs read. |
| `nodes/`, `util/` | Per-family node helpers; `log_bus.py`, `blas_guard.py`, `template_gallery.py`, `docs_locator.py`. |

### `native/` sub-areas

| Sub-area | Owns |
|---|---|
| `compiler/` | The deterministic half. `py_to_cpp.py` (the AST transpiler), `nd_lower.py` (the six `try_lower_*` family entry points), `nd_runtime.{py,h}` (the `nd::` C++ runtime, inlined into each generated file), `node_scaffold.py` (per-family dispatcher + metadata banner), ten `emit_*.py` emitters (`attr`, `compute`, `deformer`, `geo`, `geo_io`, `hex`, `iksolver`, `locator`, `transform`, `vp2_override`), `bundler.py`, `command_companion.py`, `spec_model.py`, `kernels/`, and `TRANSPILER.md`. |
| `ai/` | The assisted half. `porter.py` (stage 2), `optimizer.py` / `optimizer_live.py` / `optimizer_agent.py` / `optimizer_knowledge.py` (stage 3), `prompt.py`, `translation_knowledge.py`, `llm_client.py`, `import_follower.py`, `verify_scripts.py`. |
| `toolchain/` | `compile_controller.py` (the driver), `toolchain.py` (Maya discovery + compiler argv), `port_cache.py`, `typeid_registry.py`, `stage_report.py`, `verify.py`. |
| `spec/` | `spec_extractor.py`, `identity.py`, `divergence.py`, `mpn_spec_adapter.py`. |
| `tests/` | Out-of-suite C++ and parity fixtures (including `.cpp` test files) that the unit suite does not run. |

### `ui/` sub-areas

| Sub-area | Owns |
|---|---|
| `mpynode_designer.py` | The ~124 KB main window: mode tabs Workspace / Templates; Workspace is a 3-pane splitter — `Scene \| Attributes \| Variables \| Framework` left, the Script editor over `Log \| Watch \| Profile` centre, the AI Assistant right. |
| `widgets/` | 35 modules: `editor_core.py`, `script_tab_content.py`, `api_view.py`, `script_navigator.py`, `scene_tree.py`, `attributes.py`, `variables.py`, `template_gallery_panel.py`, … |
| `dialogs/`, `llm/` | 8 dialogs (`about`, `add_attr`, `compile_dialog`, `confirm`, `connect_attr`, `doc_viewer`, `node_info`, `preferences`); 6 LLM provider clients (`anthropic_client`, `openai_client`, `gemini_client`, and the three CLI ones `claude_cli_client`/`codex_cli_client`/`gemini_cli_client`) plus shared plumbing — `cli_base`, `config`, `payload`, `system_prompt`, `tools`, `compile_bridge`. |
| `qt_wrapper.py` | PySide6 first (Maya 2026+), falling back to PySide2 (Maya 2022–2025). |

## 4. Node types and how a wrapper relates to its Maya base

`scripts/mpynode/_node_registry.py` is the single source of truth: `REGISTRY:
dict[str, NodeTypeSpec]`, exactly 12 entries, each carrying `native_type`,
`wrapper_module`, `wrapper_class_name`, the hand-verified `native_class`, the
API generation and a `doc_slug` for versioned Autodesk help URLs. The scene
tree, `New Node ▸` and `native_type -> wrapper_class` all read it.

| Node type | Maya base | API | MTypeId | What it is |
|---|---|---|---|---|
| `mPyNode` | `MPxNode` | 2 | `0x00135700` | Generic Python expression node. Pinned first in `New Node ▸`. |
| `mPyLocator` | `MPxLocatorNode` + a bundled `MPxDrawOverride` | 2 | `0x00135702` | Viewport-drawn locator. Compute is DRAW code (`self.draw = …`); no DG user outputs. |
| `mPyConstraint` | `MPxNode` | 2 | `0x00135703` | Scriptable constraint, five preset target/rest inputs. Deliberately not `MPxConstraint`, which hijacks `compute()`. |
| `mPyIkSolver` | `MPxIkSolverNode` | 1 | `0x00135713` | Custom IK solve in Python. |
| `mPyDeformer` | `MPxDeformerNode` | 1 | `0x00135716` | The canonical deformer. `envelope` is inherited. |
| `mPyTransform` | `MPxTransform` + a paired `MPxTransformationMatrix` | 1 | `0x00135717` / `0x00135718` | Expression publishes a local `(4,4)` matrix + per-channel `apply_*` gates. Registered with `registerTransform()`. |
| `mPyMesh` | `MPxNode` | 2 | `0x00135719` | DG polygon generator (`outMesh -> mesh.inMesh`), matching `polyCube`'s pattern. Base was pivoted off `MPxSurfaceShape`. |
| `mPySkinCluster` | `MPxSkinCluster` | 1 | `0x0013571B` | A genuine skinCluster **by type** — registered under `MPxNode.kSkinCluster`, so Paint Skin Weights and the Component Editor accept it. |
| `mPyBlendShape` | `MPxDeformerNode` | 1 | `0x0013571C` | Aliased `weight[]` + `targetGeometry[]`. Not `MPxBlendShape`: that class never calls `deform()` and its native `weight[]` blocks the aliased user attr. |
| `mPyFile` | `MPxNode` + `MPxShadingNodeOverride` | 2 | `0x00135720` | Expression-driven file texture; shades in VP2, the Hypershade swatch and Maya Software. |
| `mPyNurbsCurve` | `MPxNode` | 2 | `0x0013571D` | DG curve generator (`outCurve -> curveShape.create`). |
| `mPyNurbsSurface` | `MPxNode` | 2 | `0x0013571E` | DG surface generator (`outSurface -> nurbsShape.create`). |

**The three-layer relationship.** For every type there are three files:

1. `plug-ins/mpynode_api{1,2}.py` — imports the `MPx*` subclass, calls
   `registerNode()` (or `registerTransform()` for `mPyTransform`), then
   `auto_dirty.install_for_type(type_name, touch=…, owner=PLUGIN_NAME)`.
2. `scripts/mpynode/_api{1,2}/<type>.py` — the actual `MPx*` subclass: `NODE_ID`,
   `initialize()`, and the `compute()`/`deform()`/`draw()` bridge that execs the
   stored Python string. Shared machinery in `_api1/helpers.py`,
   `_api2/helpers.py`, `_api2/geometry.py`.
3. `scripts/mpynode/wrappers/<type>.py` — the public class. **Every wrapper
   inherits `MPyNode` from `wrappers/_mpy_node.py`**, which supplies the
   attribute/variable/Init/profile/Watch surface; the subclass adds only the
   family surface (`MPyDeformer.create_on(mesh, …)`, `INTERNAL_API_SLOTS`,
   API-tab methods) and calls `plugin_loader.ensure_loaded(<type>)` first.

The registry deliberately does **not** register the compiled C++ sibling
produced by "Convert to C++": an unregistered type is hidden from the scene tree
and from `ls` for free, which is exactly the coexist contract — the hidden
sibling drives downstream while the Python node stays the visible source of
truth.

Attribute surface: 19 wire types (`_mpy_node.py :: _ADD_ATTR_KIND`, exposed as
`VALID_INPUT_TYPES`), any of them arrayable. The Add-Attribute dialog offers 17
(`add_attr.py :: _ATTR_TYPE_GROUPS` -> `ALL_ATTR_TYPES`); **two are omitted, not
one**: `double` deliberately and with a comment (redundant with `float` — both
come back from `read_plug_value` as a Python float), and `float2`, which is in
no group. Both still resolve through `_ADD_ATTR_KIND`, so old scenes, `.mpn`
files and the programmatic `add_attr(...)` keep accepting them.

## 5. The compile pipeline in detail

Entry point: `native/toolchain/compile_controller.py :: compile_plugin(specs,
plugin_name, out_dir, *, strict, verify, reuse_cache, provider, model, maya,
optimize, ai_assist, …)` — synchronous, single-threaded, lettered steps:

```text
a / a.1 / a.2  resolve provider+model; toolchain preflight (no tokens spent before
               we know a compiler exists); duplicate command-name preflight
b              fail-fast portability - spec.portability.portable False => strict aborts
c              per node: cache key -> HIT (copyfile) or MISS (porter.port_node)
c.4 / c.5      port-honesty scan (collect ND_PORT_INCOMPLETE); VP2 override injection
c.6            opt-in AI optimizer (stage 3)
d / d.1        bundler.assemble -> compile + link; clean scratch (never build/source/
               or build/stages/)
e / f          verify - parity in a throwaway mayapy; write manifest.json
```

`compile_plugin_multi(...)` runs the same specs once per detected Maya version
into `out_dir/<label>/`, deep-copying the spec list per version so one build's
in-place mutations cannot leak into the next.

### The 3 stages

Names and meanings come from `native/toolchain/stage_report.py :: _STAGE_FILES`;
everything lands under `build/stages/<TypeName>/`.

**Stage 1 — `1_transpiled.cpp`, "deterministic transpile (no AI)".** Pure
`node_scaffold.generate_cpp(spec, for_port=True)`, emitted on *every* path
before anything downstream can fail and treated as a deliverable: the
hand-finishable baseline a user with no AI budget can still take away. It is a
complete `MPx*` translation unit — includes, class decl, `initialize()`,
creator, `initializePlugin`/`uninitializePlugin` — plus a metadata banner and a
deterministic `// build: <hash12>` stamp from `_apply_metadata`. `generate_cpp`
dispatches per family (geometry / transform / locator / iksolver / deformer /
generic) before it reaches any emitter.

**Stage 2 — `2_assisted.cpp`, "AI filled the unported region(s)".** Runs only
when stage 1 contains `PORT_BEGIN` (`// ===== BEGIN PORTED COMPUTE =====`,
`native/compiler/spec_model.py`) and assist is on. That single string test is
the whole fork — `compile_controller._node_needs_llm` and `porter.port_node`
both use it. The model fills only the marked region; the file is compiled with
up to 4 fix rounds feeding back the last 4000 chars of compiler errors, plus
one optional retry on the inline path. **Stage 2 is written last** — it is the
source that actually reached the compiler, not the model's first answer.

**Stage 3 — `3_optimized/NN_<slug>.cpp` (opt-in).** An agent gets a real
workspace (the `.cpp` to edit in place, `build.sh`, `bench.sh` printing
`MEDIAN_MS: <x>`, `TASK.md`) rather than a one-shot rewrite — blindfolded
one-shot rewrites returned truncated files and prose. Rounds propose from the
current best, so accepts compound. The accept gate is triple and external to
the AI: **compiles**, **parity PASS** (a SKIP is never a pass), and beats
`best_ms / min_speedup` (default 1.05). Rejects are kept, zero-padded so the
directory reads as a story (`00_baseline.cpp` -> `01_hoist_invariant.cpp` -> …);
`00_baseline.cpp` is also the rollback source, and a round that filed no source
still gets an `NN_no_change.txt` so the numbering has no holes.

On the shipped tree: 39 stage-1 files, **only 18 stage-2 files** — the assist
stage is per node, not a fixed step — and 96 stage-3 round files.

### The port cache

`native/toolchain/port_cache.py`. Key = sha256 of canonical JSON
`{"spec": <spec minus a deny-list>, "provider", "model", "recipe":
PORTER_RECIPE_VERSION}`, dumped `sort_keys=True` so dict order cannot move the
hash while *list* order (enum names, array indices) is preserved.

- It is a **deny**-list, not an allow-list (`_DENY_LIST = ("source_node",
  "schema_version", "portability")` plus two nested drops); an allow-list was
  caught producing stale hits in review.
- Renaming a node is correctly a MISS — the name is baked into
  `registerNode("<name>", …)` and the C++ class name. The MTypeId is
  deliberately *excluded*: `bundler.transform_node_cpp` always rewrites it.
- `commands` is always keyed (each `@maya_command` compiles into the node's own
  bundle; dropping it once shipped a `.cpp` with no command classes, silently).
  `methods` is keyed only when the spec has commands.
- Writes are atomic and the **sidecar is the completeness gate**: `.cpp` first,
  `<hash>.json` last, each via `*.tmp-<pid>` + `os.replace`, so a port cancelled
  mid-write leaves a lone `.cpp` that reads as a MISS. Location:
  `~/mpynode/port_cache`, overridable by `MPYNODE_PORT_CACHE`, then a UI
  preference, then `[paths] port_cache` in the ini.

**`PORTER_RECIPE_VERSION` (currently `"24"`) is the manual invalidation knob**;
the ~290 lines above it are a changelog, not a version number — each bump records
why generated C++ moved for a byte-identical spec. It exists because **a cache
HIT is a `shutil.copyfile` with codegen skipped entirely**, so an emitter-only,
inlined-runtime-only or prompt-only change is invisible to the key. VP2 override
injection (c.5) is equally invisible: the controller skips injection when the
served file already contains `MPxShadingNodeOverride`, so a stale hit hands back
an already-injected copy. The header's rule is blunt — bumping
`translation_knowledge` must bump the recipe.

A HIT still reconstructs the stage history: stage 1 is re-derived with
`generate_cpp` (cheap, no LLM; if codegen raises it writes
`1_transpiled.NOT_GENERATED` rather than failing the build), and an LLM-bound
node's cached `.cpp` is written as stage 2 — but the progress event says
`2_assisted_cached`. Lookup is skipped when the run's contract is "no AI touched
this": `use_cache = reuse_cache and (ai_assist or not needs_llm)`.

### Freshness gating

Two independent gates, because they cover different files.

**Gate 1 — stage 1.** `tools/check_stage1_freshness.py` (measurement) +
`tests/compile/freshness/test_stage1_codegen_freshness.py` (the gate) re-derive every checked-in
`1_transpiled.cpp` from the manifest-embedded spec and byte-compare against
today's transpiler — no compiler, no linker, no bundler, no AI. It runs in a
mayapy subprocess under `PYTHONHASHSEED=0` (codegen order is only reproducible
under a pinned seed) and is a **ratchet** over
`tests/data/stage1_stale_baseline.json`: an artifact *not* in the baseline must
match fresh codegen, and one *in* the baseline must **still be stale**, so the
list can only shrink. It is currently **empty** — so all 76 stage-1 artifacts in
the gated tree (`TREES = ("templates",)` — the 39 per-template trees
plus `All Templates Plugin`'s 37) must byte-match. Do not quote a count out of the baseline's `_comment`: its "86
artifacts checked" is a dated 43-template-era measurement. The gate self-protects
against vacuity: floors on artifact/manifest counts, an assertion the hash seed
really was 0, an assertion no spec raised, and an **ungated scan driven from the
directory trees** — not from the manifests that parsed, because deriving it that
way reported a clean "0 ungated" over exactly the hole it exists to find.

```bash
mayapy tools/check_stage1_freshness.py                  # human report
mayapy tools/check_stage1_freshness.py --json out.json  # machine readable
mayapy tools/check_stage1_freshness.py --write-baseline # the ONLY sanctioned widening
```

The checker never repairs its own baseline — a gate that repairs its own
baseline is not a gate; `--write-baseline` leaves a reviewable diff naming every
artifact that newly rotted.

**Gate 2 — the shipped artifact.**
`tests/compile/freshness/test_shipped_artifact_freshness.py`. Stage 1 is regenerated every run
and so is fresh by construction; what **links** is `build/<ty>/<ty>.cpp`, which
comes through the port cache. Detection uses the emitter's own stamp: if
`1_transpiled.cpp` and `3_optimized/00_baseline.cpp` from the *same* build carry
different `// build: <hash>` values, the shipped artifact came from a stale
cache. The fix is in the assertion message — bump `PORTER_RECIPE_VERSION` and
rebuild, explicitly *not* edit the test. It also names the orphaned trees (source
template gone, so nothing can regenerate them and gating them would be a
permanent red); today that list is exactly one,
`assertEqual(rels, ["MPyFile/File Brightness Contrast"])`. Its reach is narrower
than it looks: `_nodes()` walks `templates/<fam>/<tpl>/build`, so the
family-level `templates/MPyDeformer/build/` tree (holding
`sineRippleDefault`) is never visited — **unpinned**, not pinned. The mega tree
has its own `tests/compile/freshness/test_mega_stage1_freshness.py`, refreshed with
`mayapy tools/regen_mega_transpiled.py` (codegen only, no compiler).

### Determinism

- `PYTHONHASHSEED=0` for any codegen comparison. `manifest.json` is written with
  `sort_keys` deliberately **off**: the embedded spec carries attribute
  *declaration* order only as dict insertion order, and `addAttribute()` order
  **is** Channel Box / Attribute Editor order.
- Codegen honest-rejects rather than ship a silent no-op in three places: an
  undeclared `self.<attr>` read on the generic path, the same on the deformer
  path, and a blessed-method call (`self.read_texture`, `self.sample_texture`)
  that did not fully lower — a blessed call has a deterministic C++ kernel by
  contract, so AI-porting it risks a non-parity reimplementation of the very
  thing we bless. All three raise `UnsupportedSpec` -> `build_status:
  "dropped"`.
- The AI scaffold asks only for outputs the Python actually writes and names the
  ones to leave alone. Listing all of them contradicts "translate faithfully"
  for a node that writes some, and the model resolves that by inventing.
- Maya version support is **discovered, not tabled**:
  `toolchain.discover_maya_installs()` globs `[Mm]aya*` under the platform's
  Autodesk dir and admits any install with **both** a devkit (`include/maya`,
  to compile) and a real `mayapy` (to parity-verify). Platform matrix is three
  wide: `darwin/.bundle/clang++`, `win32/.mll/cl`, `linux/.so/g++`. macOS is the
  reference and is verified at parity. Windows has been exercised end to end on
  a real host — `cl` built and linked `.mll`s that Maya loaded and registered,
  and the unit suite reached the same discovered count as macOS — but the
  parity fixtures are macOS `.bundle`s, so `tools\run_parity_sweep.bat` needs a
  local rebuild first. Linux is **refused**: the `linux/.so/g++` column exists in
  `toolchain.py` but no caller reaches it — `assemble()` drives the generated
  `build.sh`, which is the macOS recipe — so a compile there stops with an
  explicit reason rather than dying inside clang (`docs/PORTING.md`).

`build/manifest.json` is the re-derivation contract: per node the full spec,
`spec_hash`, `port_cache_key`, `cache` (hit/miss), `build_status`, `ported`,
`incomplete`, `invented_io`, `type_id_source` and the verify row — enough to
recompute the exact cache key and rebuild byte-identically.

## 6. The transpiler: deterministic vs AI

Read `scripts/mpynode/native/compiler/TRANSPILER.md` first; the hard rule is
stated there in full. **Lowering** is the deterministic path:
`nd_lower.try_lower_compute` / `try_lower_geo_compute` / `try_lower_deform` /
`try_lower_transform` / `try_lower_iksolver` / `try_lower_locator` drive
`py_to_cpp`'s AST walk. On success the compute body is emitted as `nd::` calls
with `nd_runtime.h` inlined into the `.cpp` and **no port region at all**; on
`None` it falls through to the AI scaffold with zero regression.

Lowered today: scalar arithmetic and control flow; constructors
(`zeros/ones/full/eye/arange/linspace/array/*_like`); elementwise ops, ufuncs,
reductions; `dot`/`cross`/`matmul`/`@`; `reshape`/`transpose`/`newaxis`/
`astype`; slicing and slice-assignment; bit-exact `np.random.RandomState` via
`nd::MT19937`; boolean masks, `np.where`, fancy/gather indexing, `nonzero`,
`concatenate/stack/tile/roll`; `np.diag`, `np.linalg.det`, `np.linalg.inv`,
`np.linalg.solve` for a single `(N,N)` matrix (`nd::solve`), `np.einsum` with an
explicit `->`, `np.linalg.svd` via tuple-unpack (Jacobi, `(...,3,3)` only — no
BLAS/LAPACK); the whole ndarray *method* surface from one table
(`py_to_cpp._ARRAY_OPS`); and deterministic k-d tree lowering (`nd::KDTree`).

Non-numeric IO lowers too — it is *not* a porter fallback.
`nd_lower._materialise_input` lifts matrix, string/hex, quaternion, float2 and
colour, scalar **and** array (`_is_matrix_scalar` … `_is_color_array`), with
matching writers (`_matrix_array_output_lines`; `_string_scalar_output_lines`
hex-encodes inline on the way out); mesh/NURBS handles bind via `_is_geo_input`.
The one real gap is geo **array** inputs: only the plain `MPxNode` path declares
the `std::vector<Nd<Kind>>` they bind to, so generator and deformer paths leave
those reads to the porter.

Rejected to the AI porter — principled, not gaps; the authoritative list is the
`py_to_cpp` module docstring (lines 45-51): `np.argwhere`; `np.linalg.pinv`,
which needs a *general* SVD and `nd::svd` is `(...,3,3)`-only; a **batched**
`(...,N,N)` `np.linalg.solve` (the single `(N,N)` form lowers); `svd` without
tuple-unpack; `einsum` without `->`. `partition`/`argpartition` because numpy
leaves non-kth order unspecified (a parity impossibility), `view` because it
aliases its base, `tolist` because `+` would silently become elementwise addition.

**What the AI does** is fill the marked region, and only that. The prompt
(`native/ai/prompt.py :: build_prompt`) is a per-family system prompt plus four
always-on blocks in fixed order — `_ASCII_RULE`, `PORTABILITY_RULE`,
`_UNPORTED_RULE`, `_COMPLEXITY_RULE` — then a library-aware translation guide.
They ride on the *system* prompt because system is reused across every fix
round.

`_UNPORTED_RULE` is the honesty hatch: emit `// ND_PORT_INCOMPLETE: <what and
why>` plus a neutral fallback rather than invent; file, process and network IO
are absolutely prohibited. "Porting most of a node and marking the rest is a
SUCCESS … a plausible-looking invention is a wrong answer that nothing
downstream can catch." `_COMPLEXITY_RULE` came from a measured failure, not
theory: handed `cKDTree(...).query(...)`, the model wrote a *correct* `O(N*M)`
scan that passed every gate — compiled, deterministic, exact match — and was
**29x slower** at 160k points. It now carries a Maya API cost table
(`MMeshIntersector::getClosestPoint` vs `MFnMesh::getClosestPoint` with its
NULL-defaulting accelerator: 714 s vs 0.125 s on a 40k-face sweep).

Headline number, countable straight off the tree: of the 39 checked-in build
trees, **21 have no `2_assisted.cpp` at all** — every compute lowered
deterministically and no LLM was involved. Most nodes compile with no AI
provider installed at all. When one *is* needed,
`native/ai/llm_client.py` shells out to a CLI provider (`claude`, `gemini`,
`codex`; overridable via `CLAUDE_BIN`/`GEMINI_BIN`/`CODEX_BIN`), probing
fallback dirs for the macOS Dock-launch case where the app inherits the minimal
launchd `PATH`.

## 7. Testing

**The unit suite.** `tools/run_tests.sh` (macOS/Linux) and `tools\run_tests.bat`
(Windows) are the only sanctioned invocations:

```bash
tools/run_tests.sh                                   # whole suite (mayapy 2026)
tools/run_tests.sh tests.nodes.test_draw_types       # one module
MAYAPY=<maya-install>/bin/mayapy tools/run_tests.sh  # override the default 2026
```

A naked `mayapy -m unittest` misses the six things they set:

```text
MPYNODE_USE_STUDIO=1      # userSetup.py must not run inside the test process
MPYNODE_ROOT=<repo>       # some modules read this at IMPORT time -> KeyError without it
PYTHONPATH=<repo>/scripts # APPEND MPYNODE_EXTRA_PYTHONPATH for numpy/scipy/PIL, never prepend
MAYA_PLUG_IN_PATH=<repo>/plug-ins
QT_QPA_PLATFORM=offscreen
MPYNODE_TRUST_PICKLE=1    # headless cannot show the trust prompt; without it Init AND
                          # Compute stop executing and the fixtures fail closed
```

Both run `tools/_unittest_exit.py`, **not** `-m unittest`: after
`maya.standalone.initialize()` mayapy's teardown forces exit 0, so real failures
were reported as success. With no args they spell out `discover -s tests -t .
-p "test_*.py"`, because forwarding `"$@"` bare made a bare invocation print
"Ran 0 tests / OK" — a false green that survives an `^OK` grep.

**Size.** 6,763 `def test_` methods across 278 test modules (290 `.py` under
`tests/`; the non-test twelve are `_setup.py`, `_paths.py`,
`_bench_lock_child.py`, `_stub_compiled_plugin.py`, `data/scanline_defs.py` and
the seven package `__init__.py`). Grouped by area rather than flat: six
top-level packages, with `compile/` split five further ways.

Because a category package sits two levels below the repo root and a
sub-category three, no test counts `dirname` levels to find the root — they all
import `tests._paths`. A hand-counted walk that is wrong by one does not raise;
it resolves nothing and the artifact gates quietly **skip**, which is why the
suite is verified on its skip count as well as its pass count.

**What the freshness gates protect.** The suite cannot compile C++, so the two
gates from section 5 are how it keeps checked-in artifacts honest.
`test_stage1_codegen_freshness.py` protects **the transpiler contract**: every
committed `1_transpiled.cpp` still matches today's codegen from its own recorded
spec. `test_shipped_artifact_freshness.py` protects **the delivery contract** —
the `.cpp` that actually links did not come from a stale port cache; it is the
one that catches "I changed an emitter and every rebuild silently served the old
file". Both are detailed in section 5, including what gate 2 does *not* reach.

**Out-of-suite gates.** `tools/run_parity_sweep.sh` / `.bat` re-verify
*compiled* parity for all 12 node types against the `.bundle` fixtures under
`tools/parity_sweep/fixtures/` — no rebuild, no porter, no LLM, each type in its
own mayapy subprocess so the bundles never share a Maya runtime or MTypeId
space; ~6 min; exit 0 only if all pass. Run it before tagging — but **build the
fixtures first**: `.gitignore` ignores `*.bundle` everywhere with no exception,
so the fixture bundles are local build products, not repo content, and a fresh
clone cannot run the sweep. It now says exactly that and exits 2 up front,
rather than spending six minutes emitting a column of `????` rows. Only the
`.ma` scenes a per-type script actually opens are versioned beside them (most
types build their scene procedurally and need only the bundle); each `.bundle`
has to be produced through the normal compile path (Convert to C++ /
`compile_plugin`) into its fixture dir. Every fixture that has ever existed is a
macOS `.bundle`, so `tools\run_parity_sweep.bat` remains unproven
(`docs/PORTING.md`). `tools/harness/` holds the attended mayapy drivers —
`benchmark_node.py`, `optimize_node.py`, the per-template audit and the combined
plug-in set — documented in `tools/harness/README.md`.
`tools/build_compiled_templates.sh` rebuilds the artifact trees: phase A
(transpile + AI + compile) fanned `--jobs` wide, phase B (optimizer) fanned
`--opt-jobs` wide with **benchmarks serialised** on a cross-process mutex named
by `MPYNODE_BENCH_LOCK` (default `_build_state/.bench.lock` — that file is
the mutex, not leftover state).

## 8. Extending it

### Adding a node type

There is no single registration point; a type is real when all of these exist.
Work top to bottom.

| Touch | Add |
|---|---|
| `scripts/mpynode/_api{1,2}/<type>.py` | The `MPx*` subclass: `NODE_ID = om.MTypeId(0x001357xx)` in the mpynode private range (next free after `0x00135720`), `initialize()`, and the bridge that execs the stored Python. Reuse `_api1/helpers.py`, `_api2/helpers.py`, `_api2/geometry.py` rather than re-deriving the plug plumbing. |
| `scripts/mpynode/wrappers/<type>.py` | Subclass `MPyNode` from `wrappers/_mpy_node.py`; add only the family surface (a `create_on` variant, `INTERNAL_API_SLOTS`, API-tab methods) and call `plugin_loader.ensure_loaded(<type>)` at the top of every entry point. |
| `plug-ins/mpynode_api{1,2}.py` | `registerNode()` (or `registerTransform()` if it needs a paired transformation matrix), the matching `deregisterNode()` in `uninitializePlugin`, and the type in the `auto_dirty.install_for_type` loop so runtime attributes dirty. |
| `_common/lifecycle/plugin_loader.py` | The type in `_NODE_TYPE_TO_PLUGIN`, so auto-load knows which plug-in file owns it. |
| `scripts/mpynode/_node_registry.py` | The `NodeTypeSpec` — this is what puts it in the scene tree and `New Node ▸`, and what `wrap_node()` resolves. `native_class`, `api` and `doc_slug` must be hand-verified against the Autodesk reference (`api=2` -> `py_ref` tree, `api=1` -> `cpp_ref`). |
| `_common/lifecycle/init_header.py` | The per-type `self.<...>` idiom block — the Init header is where users actually learn a type's surface. |
| `_common/node_setups/<Type>.py` | Optional per-type default `setup()`. |
| `native/compiler/` | Only for a genuinely new *family*: a `node_scaffold.generate_cpp` dispatch branch, an `emit_<family>.py` and an `nd_lower.try_lower_<family>`. A type reusing an existing base (`MPxNode`, `MPxDeformerNode`) usually needs nothing here. |
| `docs/node_types/mPy<Type>.md`, `tests/`, `templates/` | The Help menu auto-lists the docs dir; every registry entry currently has at least one template. |

### Adding a template

Templates are **generated, not hand-written**.
`scripts/mpynode/_demos/build_templates.py` is the authority: it builds the
node, wires it, runs its verification, and writes
`templates/<Type>/<Name>/template.mpn` + `description.md` **only when the
verification passes**. Add a `build_<name>()` following the shape of its
neighbours, including a `@maya_test` and a `@maya_demo` on the node.

A template directory holds `template.mpn` — the only **required** file — plus
`description.md` (optional to the loader; present on all 37 today), an optional
preview, and **any data assets the template loads**. Ten of the 37 ship assets —
`.ma` scenes (`MPyNode/DNET/skull.ma`, `MPyLocator/Mesh Regions/head.ma`,
`MPyBlendShape/Combo Correctives/combo167_mesh.ma`, `MPyNode/Ouch/arm.ma`), audio
(`MPyNode/Ouch/ouch.wav`), data plus its generator
(`MPySkinCluster/Twist Swing Skin/{LBS,DQS}.json`,
`MPyMesh/JSON Mesh Reader/{seq/,make_sequence.py}`,
`MPyMesh/Disk Mesh Cache/{ripple_cache.ndio,make_cache.py}`) and the `.png`s under
the three `MPyFile/*` templates. Preview names are the fixed ordered tuple
`_common/util/template_gallery.py :: _PREVIEW_NAMES` = `preview.{mp4,gif,png,jpg}`.
Directory names are Capitalised
(`MPyMesh/Metaballs`) while node types are lower-first (`mPyMesh`). `.mpn` is
the **round-trip** format (`_common/io/mpn_io.py`): all four source tiers,
attribute maps with authored order and colour, pickled stored-variable *values*,
metadata, gap spacing, `class_path` — but **no connections**, since it is a node
template, not a scene snapshot. The `.py` bake (`_common/io/py_export.py`) is by
contrast **one-way**: Methods become real Python, so re-importing does not
repopulate the Methods surface, and stored vars are re-declared without values.
The gallery scans `template_search_paths` (default `templates/`) for folders
holding a `template.mpn`; for pickle safety the tree reads raw JSON via
`load_mpn_header` and the decoding `load_mpn` runs only on the template you
click Create on.

After adding or changing a template, rebuild its C++ tree with
`tools/build_compiled_templates.sh` and re-run both freshness gates. If you
changed an **emitter** rather than a template, **bump `PORTER_RECIPE_VERSION`
first** — otherwise the port cache serves the old `.cpp` and the build looks
like it worked.
