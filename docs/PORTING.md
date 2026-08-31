# Porting MPyNode — platforms & toolchain

How MPyNode runs across operating systems, and what it takes to bring the
**native Porter** (LLM-translate a node to C++, then compile + link a Maya
plugin) to a new one.

There is intentionally **no separate `macos_port.md`**: macOS is the *reference
platform* MPyNode is developed and tested on, not something you port *to*.
Windows and Linux are the targets you port *to*, and the cross-platform work —
plus the parts that can only be finished/verified on those hosts — is what this
document covers.

## Platform status

| platform | role | AI Assistant | native build (compile→load `.bundle`/`.mll`/`.so`) |
|----------|------|--------------|----------------------------------------------------|
| **macOS** (Apple Silicon) | **reference** — developed + tested here | ✅ | ✅ verified at parity (`clang → .bundle`, `arch -arm64`) |
| **Windows** | exercised end to end on a real host | ✅ (API providers cross-platform; CLI providers fixed) | ✅ `cl.exe → .mll` built, linked, loaded and registered; unit suite reached the same discovered count as macOS. The parity fixtures are gitignored `.bundle`s, so `tools\run_parity_sweep.bat` needs a local rebuild first (it now says so and exits instead of reporting `????`) |
| **Linux** | not supported | ✅ (expected) | ❌ refused up front. `g++ → .so` columns exist in `toolchain.py` but nothing reaches them: `bundler.assemble()` drives the generated `build.sh`, which is the macOS recipe. Interpreted nodes are unaffected |

The cross-platform abstraction lives in **code, not docs**:
`scripts/mpynode/native/toolchain/toolchain.py` owns every OS decision, so this file is
just the "what differs and what must be verified on the target host" handoff.

---

## macOS — the reference platform

Nothing to "port" here; this is the home platform and the baseline the others
are measured against.

* **Build:** `clang++ → .bundle`, `arch -arm64` (`toolchain.mac_arch()` =
  `platform.machine()`, so Intel Macs build too). Maya define `OSMac_`; libs in
  `Maya.app/Contents/MacOS`; one-shot clang or a hand-runnable `build.sh`.
* **Test harness:** `tools/run_tests.sh` drives the standalone unit suite on
  **Maya 2026's `mayapy`** by default (`MAYAPY=<install>/bin/mayapy` selects
  another). `tools/run_parity_sweep.sh` is the separate compiled-parity gate.
* **Parity:** the native Porter's output is verified byte-for-byte / at numeric
  parity against the Python node here; `test_toolchain.py` pins the macOS argv as
  a regression anchor so routing through `toolchain.py` is a provable no-op.

Everything below is about reproducing this on the other platforms.

---

## The keystone: `native/toolchain/toolchain.py`

Before this, the macOS clang recipe was copy-pasted across `porter.compile_cpp`,
`bundler`, and `codegen.generate_build_sh`. Now everything platform-specific
lives in `toolchain.py`:

| concern                | macOS                         | Windows                | Linux            |
|------------------------|-------------------------------|------------------------|------------------|
| plugin extension       | `.bundle`                     | `.mll`                 | `.so`            |
| object extension       | `.o`                          | `.obj`                 | `.o`             |
| Maya define            | `OSMac_`                      | `NT_PLUGIN`            | `LINUX`          |
| compiler               | `clang++`                     | `cl`                   | `g++`            |
| Maya lib dir           | `Maya.app/Contents/MacOS`     | `<maya>\lib`           | `<maya>/lib`     |
| default Maya dir       | `/Applications/Autodesk/maya2026` | `C:\Program Files\Autodesk\Maya2026` | `/usr/autodesk/maya2026` |
| link style             | one-shot clang / bash build.sh | direct `cl` (no bash) | g++              |
| build env              | inherit                       | captured `vcvars` env  | inherit          |

Key functions: `plugin_ext()`, `object_ext()`, `maya_define()`,
`maya_lib_dir()`, `maya_include_dir()`, `default_compiler()`,
`default_maya_dir()`, `compile_to_plugin_cmd()` (single-node `porter.compile_cpp`),
`compile_object_cmd()` / `link_plugin_cmd()` (multi-node `bundler`),
`build_env()` (vcvars), `mayapy_path()`, `resolve_executable()`,
`cli_subprocess_kwargs()`, `no_window_kwargs()`.

Every OS-dependent function accepts an explicit `os_name=` so the whole matrix
is unit-testable from any host (`_tests/test_toolchain.py`,
`_tests/test_native_build_scripts.py`).

---

# Windows — finish & verify

Status as of 2026-06-08: groundwork done on macOS; the items under
**"Finish on Windows"** need a Windows host with Visual Studio C++ to verify.

## TL;DR

* The **AI Assistant** (LLM chat + the default Anthropic/OpenAI/Gemini **API**
  providers) is already cross-platform — it uses `urllib` + `certifi` + env-var
  API keys and `os.path`/`expanduser` everywhere. **No changes needed to use it
  on Windows.** The only Windows-specific fixes were for the *optional local CLI
  providers* (`claude` / `gemini` / `codex` CLIs) — done, see below.
* The **native Porter** routes every platform decision through
  **`toolchain.py`**. macOS still builds `clang -> .bundle` byte-for-byte as
  before; Windows builds `cl.exe -> .mll`.
* What can only be done/verified **on Windows**: actually running `cl.exe`
  against the Maya devkit and loading the resulting `.mll` in Maya. The argv the
  pipeline builds is unit-tested (`_tests/test_toolchain.py`), but it has never
  been *executed* on this macOS box.

## The exact Windows compile/link recipe

Single node (`compile_to_plugin_cmd`, compiler = `cl`):

```
cl /nologo /std:c++17 /EHsc /MD /bigobj /LD
   /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS
   /I <maya>\include  <node>.cpp
   /link /LIBPATH:<maya>\lib  OpenMaya.lib Foundation.lib [...]
         /OUT:<node>.mll
         /EXPORT:initializePlugin /EXPORT:uninitializePlugin
```

Multi-node bundler: each fragment + `plugin_main.cpp` is compiled `/c` to `.obj`
(fragments get `/D MNoVersionString /D MNoPluginEntry`), then all `.obj` are
linked with `cl /nologo /LD ... /link ... /OUT:<plugin>.mll /EXPORT:...`.

A hand-runnable `build.bat` is also emitted next to the sources for debugging
(`codegen.generate_build_bat`, `bundler.make_build_bat`). Run it from an
**"x64 Native Tools Command Prompt for VS"**.

## How the MSVC environment is found (no extra deps)

`cl.exe` only works with the toolset env vars (`INCLUDE`, `LIB`, `PATH`). The
toolchain captures them once, lazily:

1. `vswhere.exe` (fixed path: `%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe`)
   → newest VS install with the C++ x64 tools.
2. `<install>\VC\Auxiliary\Build\vcvarsall.bat`.
3. Run `cmd /c "vcvarsall.bat x64 && set"`, parse the `set` dump
   (`toolchain._parse_set_output`), merge over `os.environ`, cache per arch.
4. `build_env('cl')` returns that dict; every `cl` subprocess runs under it.

This is the **"Direct cl.exe + captured vcvars"** approach (chosen over a
`.vcxproj`/MSBuild generator or a CMake dependency) — no extra tooling, mirrors
how the macOS path drives the compiler directly.

## What changed (file-by-file)

**New**
* `scripts/mpynode/native/toolchain/toolchain.py` — the platform abstraction.
* `tests/compile/pipeline/test_native_toolchain.py` — pins the macOS argv as a
  byte-for-byte regression anchor and the MSVC argv as a contract, and covers
  build.sh/build.bat correctness (incl. the batch `%%`-quoting trap).
  *(formerly `test_toolchain.py` + `test_native_build_scripts.py`, merged in the
  2026-06-21 test-suite reorg.)*
* `tools\run_tests.bat`, `tools\run_parity_sweep.bat` — Windows mirrors of
  `tools/run_tests.sh` / `tools/run_parity_sweep.sh`.
* This doc.

**Refactored to route through `toolchain` (macOS argv preserved exactly)**
* `native/porter.py` — `compile_cpp` (recipe + `.bundle`→`plugin_ext()`),
  `port_node` (build.sh→`generate_build_script`), the 3 verify-script emitters
  (`.bundle`→`plugin_ext()`), `_MAYA_DEFAULT`→per-OS, CLI launch hardening
  (`_resolve_cli_bin` resolves full path, `_run_cli_proc` uses
  `cli_subprocess_kwargs`).
* `native/bundler.py` — per-fragment compile + link routed through `toolchain`;
  Windows does a direct `cl` link (no bash), macOS keeps `bash build.sh`; added
  `make_build_bat`; `_MAYA_DEFAULT`→per-OS.
* `native/codegen.py` — added `generate_build_bat` + `generate_build_script`
  dispatcher; `generate_load_test` is extension-aware; `write_plugin` os-aware.
* `native/compile_controller.py` — `_MAYA_DEFAULT`→per-OS; `_mayapy_for`
  delegates to `toolchain.mayapy_path`.
* `ui/llm/cli_base.py`, `ui/llm/claude_cli_client.py`, `ui/llm/gemini_cli_client.py`
  — resolve the CLI launcher to a full path (Windows `.cmd`/`.exe` shims),
  UTF-8 pipes, no-console-window flag.
* the out-of-suite native parity harness (since relocated to
  `tools/parity_sweep/`) — `ROOT` derived from `__file__` (was a hard-coded mac
  path).

**macOS regression check (at the time, 2026-06-08):** full suite held at the
then-baseline **9 fail / 27 err / 9 skip** (1550 tests). The `besselField`
end-to-end *subprocess parity verify* still passes (maxerr ≈ 2.8e-9), i.e. the
refactored build pipeline still produces a working `.bundle` at parity.

## Prerequisites on Windows

1. **Visual Studio 2019/2022** with the **"Desktop development with C++"**
   workload (gives `cl.exe`, the x64 toolset, and `vswhere.exe`). Build Tools
   (no full IDE) is sufficient.
2. **Maya** installed, and its **devkit** present so `<maya>\include` and
   `<maya>\lib` exist with the `OpenMaya*.lib` import libs. If your Maya install
   lacks the devkit, download the matching *Maya Devkit* from Autodesk and point
   `maya=` / `MAYA_LOCATION` at it (or merge its `include`/`lib` into the Maya
   dir).
3. The same Python env you run the Designer in is Maya's `mayapy` — no extra pip
   deps for the build (the AI providers' deps are unchanged).

## Finish on Windows — step by step

1. **Sanity: toolchain unit tests** (no compiler needed):
   ```
   tools\run_tests.bat tests.compile.pipeline.test_native_toolchain
   ```
   Expect all green. (If `mayapy.exe` isn't at the default path, set
   `MAYA_LOCATION` first.)

2. **Verify vcvars discovery** in `mayapy`:
   ```python
   from mpynode.native import toolchain as tc
   print(tc.find_vswhere())
   print(tc.find_vcvarsall())
   env = tc.build_env("cl")
   print(bool(env), "INCLUDE" in (env or {}), "LIB" in (env or {}))
   ```
   All should be truthy. If `find_vcvarsall()` is `None`, the C++ workload isn't
   installed (or vswhere can't find it) — fix VS first.

3. **Single-node port + build** (smallest real end-to-end). In the Designer,
   select a simple node and use **Compile to native plugin**, OR from `mayapy`:
   ```python
   from mpynode.native import porter
   res = porter.port_from_node("<sceneNode>", r"C:\tmp\port_out",
                               maya=r"C:\Program Files\Autodesk\Maya2026")
   print(res["ok"], res["bundle"])   # bundle ends in .mll
   print(res["compiler_log"][-2000:])
   ```
   If it fails to compile, read `compiler_log` — the recipe/defines/libs are in
   `toolchain.compile_to_plugin_cmd`; adjust there (one place).

4. **Load + parity verify**: the Designer's compile flow runs a subprocess parity
   verify automatically. Standalone, run the emitted `verify_in_maya.py`
   (single) / the controller's verify, or `load_test.py`. The `.mll` should load
   and `createNode` should succeed.

5. **Multi-node bundle** (the Designer "Compile…" with several nodes checked) →
   exercises `bundler.assemble`'s Windows direct-`cl` link path.

6. **AI Assistant**: works out of the box with API keys
   (`ANTHROPIC_API_KEY` etc.). To use a **local CLI provider**, install the CLI
   (`claude` / `gemini`) so it's on `PATH` (`where claude` resolves the `.cmd`);
   the resolver + UTF-8 pipes + no-window flag are already wired.

## Known caveats / things to check on Windows

* **Compiler flags are a best-effort match to Autodesk's recipe.** `/MD /EHsc
  /bigobj /D WIN32 /D _WINDOWS` are included; if a node fails to link, compare
  against `<maya>\devkit\...\Makefile`/`buildconfig` for that Maya version and
  add any missing define/flag in `toolchain.py` (single source). Candidates seen
  in Autodesk samples: `/Zc:wchar_t-`, `_AFXDLL`, `/D _USRDLL`.
* **`.mll` naming via `/OUT:`** plus `/EXPORT:initializePlugin,uninitializePlugin`
  is how the DLL is renamed and the entry points exported. If Maya reports
  "not a valid plugin", confirm both exports made it into the `.mll`
  (`dumpbin /exports x.mll`).
* **Maya lib dir.** Assumed `<maya>\lib`. Some devkit layouts put import libs
  under `<maya>\devkit\lib` — if `OpenMaya.lib` isn't in `<maya>\lib`, point
  `maya=` at the devkit root or adjust `toolchain.maya_lib_dir`.
* **arch** is x64 (`vcvarsall x64`, no `/arch`); Maya is x64-only on Windows.
* **vcvars caching** is per-process. If you change VS installs mid-session,
  restart Maya (or clear `toolchain._VCVARS_ENV_CACHE`).
* The macOS `-arch` was hard-coded `arm64`; it's now `toolchain.mac_arch()`
  (= `platform.machine()`), which also fixes Intel-Mac builds. Irrelevant on
  Windows but noted.

---

# Linux — not supported, refused up front

`toolchain.py` carries a full Linux column (`g++ → .so`, define `LINUX`, libs in
`<maya>/lib`, default `/usr/autodesk/maya2026`), and the argv it builds is
unit-tested like the others — but **no caller reaches it**. `bundler.assemble()`
branches Windows → `toolchain.compile_to_plugin_cmd`, everything else → `bash
build.sh`, and the only `build.sh` generator emits the macOS recipe (`clang++`,
`-D OSMac_`, `-bundle`, `lipo`). On Linux that would fail deep inside a compiler
that isn't there, so `assemble()` now stops first and reports the reason.

Interpreted nodes are unaffected: the framework itself runs anywhere Maya does.
Only *compiling* a node to C++ is macOS/Windows.

Bringing Linux up is the same shape as the Windows checklist minus the
MSVC/vcvars machinery, plus one thing Windows did not need: **a Linux build-script
generator**, since `assemble()` dogfoods the emitted `build.sh`. Either add a
`g++ → .so` variant beside `make_build_sh` / `make_single_build_sh` (and teach
`toolchain.maya_resolver_sh` the `/usr/autodesk` search root), or give Linux the
same direct-argv branch Windows has. Then drop the `_LINUX_UNSUPPORTED` guard,
ensure `g++` + the Maya devkit (`<maya>/include`, `<maya>/lib`) are present, run
the toolchain unit tests, and do a single-node port + load. Any missing
define/flag goes in `toolchain.py` (one place), same as the other platforms.

---

## Why "verify on the target OS" is unavoidable

Building and loading a native Maya plugin requires the target OS's compiler
(`cl.exe` / `g++`), its system + Maya import libraries, and Maya itself to
`loadPlugin` the binary. None of that can be exercised from macOS. The *logic*
that decides the commands is fully unit-tested here; only the *execution* is
host-specific.

---

# Cross-compiler include hygiene (MSVC-only failures, detectable on macOS)

One class of Windows-only failure *is* detectable here, and it is worth a gate
because nothing else in the pipeline can see it: **a `std::` facility used with
only a TRANSITIVE libc++ include.** libc++ leaks transitive includes generously
and the MSVC STL does not, so `std::mutex` with no `#include <mutex>` is `rc=0`
under Apple clang and `C2039` under `cl.exe`. Every gate we have is a macOS
clang run, so the pipeline is structurally blind to it.

Recall, measured against five injected defects (mutex / sstream / fstream /
map / limits):

| gate | caught |
|------|--------|
| today's shipped build flags | 2 / 5 |
| `-D_LIBCPP_REMOVE_TRANSITIVE_INCLUDES -fsyntax-only` | 3 / 5 |
| static name→header check (`tools/check_std_includes.py`) | **5 / 5** |

* **The checker.** `tools/check_std_includes.py` — dependency-free, importable
  and runnable as a CLI over files or directories:
  `python3 tools/check_std_includes.py "templates/All Templates Plugin/build/source"`.
  `--self-test` re-runs the 5/5 calibration against injected copies in `/tmp`.
  It is calibrated so the known-clean corpus is **silent**: all 42 mega TUs, and
  all 135 `.cpp` under `templates/`, report zero
  findings. A name absent from its table is `UNMAPPED`, never a failure, and
  `std::pair` / `std::make_pair` / `std::move` are deliberately mapped
  generously — `<map>` / `<string>` / `<vector>` make them complete on every
  implementation, and an earlier narrow mapping produced 7 false hits on clean
  files.
* **The prompt rule.** `translation_knowledge.PORTABILITY_RULE` is the single
  home of the "include every header you use" instruction; the porter
  (`prompt.build_prompt`), the one-shot optimizer
  (`optimizer_knowledge.build_optimize_prompt` / `build_fix_prompt`) and the
  agent task brief (`optimizer_agent._TASK_MD`) all reference that one constant.
* **The repair.** `porter._splice` runs the checker over the spliced PORT region
  and *adds* any missing standard header instead of rejecting the port; adding a
  standard header to a TU that already compiled cannot break it.
  `prompt.scan_ported_body` reports the residual under an `"includes"` key,
  present only when non-empty — a finding, never a gate, same severity as `io`.

**Honest scope:** this is prophylactic, not a live bug fix. The realised defect
rate today is **0 of 42** shipped mega TUs, and the one optimizer round that
actually produced the motivating shape
(`sine_ripple/.../3_optimized/01_cache_normals_by_centroid_fingerprint.cpp:3690`,
`std::mutex m_nrmMtx; std::atomic<bool> m_nrmValid{false};`) added **both**
`<atomic>` and `<mutex>` unprompted, in 4 of 4 candidates.

---

# Pillar (c) posture: the one-shot whole-file optimizer is unavailable here

The AI optimizer has two shapes: a **one-shot** rewrite (the model retypes the
entire `.cpp` in one reply) and a **tool-using agent** that edits the file in
place. For this corpus the one-shot shape is *structurally* unavailable, and no
configuration change fixes it.

`compile_controller._response_tokens_needed` estimates the reply cost as
`int(len(text) / 3.5 * 1.25)` and compares it against the response cap
(`_resolve_optimize_max_tokens`, default **64,000**). Measured against the real
files:

| quantity | value |
|----------|-------|
| `native/compiler/nd_runtime.h` | 169,727 chars |
| …as estimated response tokens | **60,616** |
| response cap | 64,000 |
| left for the node's own code | **3,384** |
| mega TUs already over the cap | **25 of 42** |
| largest (`twistSwingSkin.cpp`, 523,430 chars) | ~**187k** tokens needed |

Every generated node inlines `nd_runtime.h`, so the runtime alone consumes 94%
of the budget before a single line of node code is counted. Raising the cap does
not help: the largest TU needs roughly **2.9x** the entire 64k budget, and the
ceiling is the provider's, not ours.

**Therefore pillar (c) requires the tool-using agent path** — the agent edits
the file in place and never retypes it, so the file's size is irrelevant to the
reply budget. On this machine that path needs
`MPYNODE_OPT_AGENT_NO_SANDBOX=1` (see `llm_client.py:635/688/726`: the CLI's own
OS sandbox nests and the pre-flight otherwise *demotes* the provider to the
one-shot shape, which then trips the budget gate above).
