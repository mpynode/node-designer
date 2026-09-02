# MPyNode

**Write real Maya nodes in Python. Compile them to C++ when you need speed.**

MPyNode registers 12 genuine Maya node types — deformers, skinClusters, IK solvers,
transforms, locators, shading nodes, mesh/curve/surface generators. You declare inputs and
outputs at runtime, write the node's evaluation body in Python stored on the node itself,
and Maya's dependency graph carries the result.

When the prototype is done, one dialog turns that node into a real distributable C++
plug-in whose compute contains no Python at all.

## Why technical artists like it

- **12 real node types** — not expressions bolted onto a transform. `mPySkinCluster` is a
  true `skinCluster`, so Paint Skin Weights and the Component Editor accept it.
- **Runtime attributes that behave like compiled ones** — 19 wire types, any of them an
  array, with dirty propagation synthesized for you.
- **The Node Designer** — a Qt authoring window with Init / Compute / API editors, a live
  variable Watch, a cProfile tab and a log.
- **Python → C++ compile** — a deterministic transpiler does the translation; an LLM is
  only asked to fill what it could not lower. Most nodes need no AI at all.
- **37 ready-made templates** covering all 12 node types, each with a runnable demo.
- **Persistent state** — stored variables that save with the scene, plus `.mpn` round-trip
  export and a one-way bake to plain `.py`.

## Requirements

| Requirement | Notes |
|---|---|
| Maya | 2024 and 2026 are tested. PySide2 (≤ 2025) and PySide6 (2026+) are both handled. Primary target: **2026** |
| Python | Maya's bundled Python 3 — 3.10 on Maya 2024, 3.11 on Maya 2026 |
| NumPy | **Required** — `import mpynode` alone survives without it, but creating a node and opening the Node Designer both fail. Maya 2026 bundles it; Maya 2024 does not, so install it into that interpreter |
| To compile to C++ | A C++ toolchain (Xcode Command Line Tools / Visual Studio "Desktop development with C++" / `g++`) and a Maya devkit |

Any Maya install that has both a devkit and a `mayapy` is detected automatically and
offered as a compile target — there is no fixed version list.

| Platform | Plug-in | Compiler | Status |
|---|---|---|---|
| macOS | `.bundle` | `clang++` | Reference platform, parity-verified |
| Windows | `.mll` | `cl` | Builds, links, loads and passes the unit suite on a Windows host. The shipped parity fixtures are macOS-only, so rebuild locally before sweeping |
| Linux | `.so` | `g++` | **Not supported.** `toolchain.py` carries the flags but nothing drives them, so a compile stops with a clear message instead of failing in the compiler. Interpreted nodes work fine — see [docs/PORTING.md](docs/PORTING.md) |

## Install

There is no installer. Two paths must be visible to Maya: `plug-ins/` and `scripts/`.

1. **Put the repo anywhere on disk.** All paths below are relative to the repo root.

2. **Copy the repo's `userSetup.py` into your Maya user scripts folder**, then point it
   back at the repo with `MPYNODE_PROJECT_DIR`:

   ```bash
   cp userSetup.py ~/Library/Preferences/Autodesk/maya/2026/scripts/   # macOS
   cp userSetup.py ~/maya/2026/scripts/                                # Linux
   export MPYNODE_PROJECT_DIR="$PWD"
   ```

   ```bat
   REM Windows, from the repo root
   copy userSetup.py "%USERPROFILE%\Documents\maya\2026\scripts\"
   set MPYNODE_PROJECT_DIR=%CD%
   ```

   Already have a `userSetup.py`? Append this repo's contents to it instead.

   Do **not** symlink it. `userSetup.py` locates the repo from its own file path without
   following links, so a symlink makes it look inside your Maya scripts folder, find no
   `plug-ins/`, and skip setup.

3. **Or skip step 2 entirely** and set the two paths yourself before launching Maya:

   ```bash
   export MAYA_PLUG_IN_PATH="$PWD/plug-ins:$MAYA_PLUG_IN_PATH"
   export PYTHONPATH="$PWD/scripts:$PYTHONPATH"
   ```

4. **Start Maya.** You should see:

   ```text
   [userSetup] node-designer2 paths set up: <your repo path>
   ```

5. **Optional — add a shelf button:**

   ```python
   from mpynode.ui import shelf
   shelf.install_shelf_button()
   ```

You never need `cmds.loadPlugin`. The right plug-in loads on demand the first time you
create a node. Preferences and caches live in one visible folder, `~/mpynode`, which you
can relocate with `MPYNODE_HOME`.

To verify the install, run the test suite (about 6,700 tests):

```bash
tools/run_tests.sh          # macOS (Linux: set MAYAPY=/usr/autodesk/maya2026/bin/mayapy)
```

```bat
tools\run_tests.bat         REM Windows
```

## Quick start

The smallest node that does something. Paste into Maya's Script Editor:

```python
from mpynode import MPyNode

n = MPyNode.create(name="myCalc")
n.add_input_attr("a", "double")
n.add_input_attr("b", "double")
n.add_output_attr("sum", "double")
n.set_compute_expression("""
self.sum = self.a + self.b
""")
```

Inputs are read as `self.<name>`; assigning `self.<name>` on a declared output publishes
it downstream. Set `.a` and `.b` in the Channel Box and watch `.sum` follow.

Then open the authoring window:

```python
from mpynode.ui.mpynode_designer import show_designer
show_designer()
```

The **Templates** tab has 37 working nodes you can create and run immediately — start
there.

## How it works

Each node stores its Python as text on a plug, so the source travels with the scene and
there is nothing to import or deploy. Attributes you add at runtime cannot use Maya's
`attributeAffects` (that is class-init-time only), so MPyNode installs DG callbacks that
reproduce the same dirty propagation automatically. Compiling walks the node's Python AST
and lowers it directly to C++, falling back to an LLM only for constructs it cannot
translate deterministically. You can then optionally re-run the compiled node against the
Python original in a throwaway `mayapy`; the result is recorded per node in
`manifest.json` and does not block the build.

Full detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Templates

37 templates in `templates/`, at least one for every node type, each with a runnable demo.
Browse them in the Designer's **Templates** tab.

| Node type | Templates |
|---|---|
| `mPyNode` | 8 |
| `mPyMesh` | 7 |
| `mPyDeformer` | 5 |
| `mPyFile` | 4 |
| `mPyLocator` | 4 |
| `mPySkinCluster` | 3 |
| `mPyBlendShape`, `mPyConstraint`, `mPyIkSolver`, `mPyNurbsCurve`, `mPyNurbsSurface`, `mPyTransform` | 1 each |

`templates/All Templates Plugin/` holds 39 demo scenes — one per demo, not per
template — that run against all 37 linked into a single plug-in. No binaries are committed:
a Maya plug-in is built against one Maya version's devkit, so you build it for your Maya —
one command, `cd "templates/All Templates Plugin" && ./build.sh 2026` (`build.bat` on
Windows). See [INSTALL.md](INSTALL.md).

## Documentation

| Document | What it covers |
|---|---|
| [docs/index.md](docs/index.md) | The full API — every node type, attribute types, worked recipes |
| [docs/CHEATSHEET.md](docs/CHEATSHEET.md) | Quick reference for the Python API: create, attributes, expressions, stored vars, compile |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the framework and the compiler are built |
| [INSTALL.md](INSTALL.md) | Install variants, environment variables, troubleshooting |
| [docs/PORTING.md](docs/PORTING.md) | Per-platform build status and the Windows / Linux recipes |
| [docs/node_types/](docs/node_types/) | One design note per node type |
| [docs/notes/](docs/notes/) | Contributor design notes for work that is scoped but not built |

## License

BSD 3-Clause. Copyright (c) 2026, Gene Hansen, Eric Vignola. See [LICENSE.md](LICENSE.md).
