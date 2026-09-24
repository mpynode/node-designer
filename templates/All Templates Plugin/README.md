# Mega-plugin delivery

One native plugin holding **every** template node type, plus one Maya scene per
demo, each already swapped over to the compiled node.

* `build/` -- the C++ this compiles: 37 namespaced node fragments plus the
  generated `plugin_main.cpp` that registers them, and the full per-node stage
  lineage under `stages/`.
* `scenes/` -- 40 scenes, one per `@maya_demo` (Circular Text has none yet).
  Templates with several demos get one scene each (DNET has three: `demo`,
  `demo_layout`, `demo_two_knots`; Spine has three: `demo`,
  `demo_twist_squash`, `demo_closed_loop`).
* `reports/` -- the evidence behind them.
* `plugin/` -- where you build `mPyMega` (37/37 node types, 32 bundled
  `@maya_command`s, zero node drops). **Empty in a fresh clone**: see below.

## Build the plug-in first

No binary is committed. A Maya plug-in is compiled against one Maya version's
devkit and will not load in another, so it has to be built on your machine, for
your Maya. The C++ sources are in the repo, so this needs only a compiler — one
command, from this folder:

```
./build.sh 2026        # or 2024, or no argument for the newest installed Maya
```

Windows, from an *x64 Native Tools Command Prompt for VS*:

```
build.bat 2026
```

It compiles `build/` (37 node types + 32 bundled commands, each namespaced and
linked through one generated `plugin_main.cpp`) and installs the result into
`plugin/`, creating that folder if it does not exist yet.

**Do not rename the built file.** Maya derives a plug-in's *name* from its
filename, and every scene here carries `requires ... "mPyMega"`. A
version-stamped copy like `mPyMega.2026.bundle` loads without complaint but
registers as `mPyMega.2026`, and then all 40 scenes open with unknown nodes —
nothing fails at build time, so the breakage only shows up in the viewport.

## Opening a scene

The scenes reference `mPyMega` by name, so Maya has to be able to find the
plug-in. Point `MAYA_PLUG_IN_PATH` at `plugin/` before launching. From the repo
root:

```
export MAYA_PLUG_IN_PATH="$PWD/templates/All Templates Plugin/plugin:$PWD/plug-ins:$MAYA_PLUG_IN_PATH"
export PYTHONPATH="$PWD/scripts:$PYTHONPATH"
```

If a scene opens with unknown nodes, either you have not built the plug-in yet,
that `MAYA_PLUG_IN_PATH` entry is missing, or `mPyMega` failed to load — check
the Plug-in Manager. Copying the built plug-in next to the other plug-ins works
too.

## How each scene was made

Each scene ran its template's `@maya_demo` interpreted, then swapped that
template's own node to the mega-compiled type (attributes and connections
preserved), evaluated it, and saved. Every scene was then re-opened in a clean
`mayapy` to prove it loads: all 40 report at least one live compiled node.
The three Spine scenes were saved from Maya 2025, the rest from Maya 2026; opened
in Maya 2025, seven of the 2026 scenes also report two unknown
`nodeGraphEditorInfo` nodes -- Node Editor tab layout, not scene content.

## Known, recorded caveats

* **Mesh Regions** -- its demo replaces the single template node with one locator
  per tag (8 in total). Only one is swapped to the compiled type; the other 7
  stay interpreted, which is the harness's documented single-node behaviour.
  Its `head.ma` also creates 7 Arnold render-settings nodes without a
  `requires mtoa`, so this `mayapy` sees them as unknown data and Maya refuses to
  write the file at all -- they are dropped before saving and the drop is
  recorded in `reports/scene_build_results.json`.
* **Three templates are `degraded`** in `reports/compile_summary.txt` -- Mesh
  Regions, Voxelize and Ouch each recorded `ND_PORT_INCOMPLETE`: they compile,
  bundle, verify and pass their authored tests, but one Python capability
  (relative texture-path resolution, audio loading, a legacy baked dict) was
  deliberately NOT ported rather than faked. This is by design and a re-run
  cannot clear it. Spring Chain's recipe-34 port, which that summary predates,
  records one too: a reopened scene restarts its chain instead of restoring the
  saved solver state.
* **Mesh Regions' setup command is not bundled** -- its setup edits stored
  variables, which a compiled node does not have, so the command generator
  skips it; `mega_loadtest.py` reports it.
* The mega plugin links each template's **shipped** C++
  (`templates/<Family>/<Template>/build/<type>/<type>.cpp`, the optimizer's
  winner where one was accepted), relinked from those artifacts with
  `MPYNODE_MEGA_FROM_ARTIFACTS=1 tools/harness/mega_plugin.py`.
