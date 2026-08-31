# Installation

mpynode is a pair of Maya plug-ins plus a Python package. There is no
`pip install` — you point Maya's plug-in + script paths at the source
tree directly.

## Prerequisites

* Maya 2024 or Maya 2026.
* macOS, Linux, or Windows (developed on macOS; CI is not configured).
* Python 3.10 (Maya 2024) or 3.11 (Maya 2026); both bundled with Maya.

Compiling nodes to C++ additionally needs a host compiler — `clang++` on
macOS or `cl.exe` (MSVC) on Windows. **Compiling is macOS and Windows
only.** The interpreted framework runs anywhere Maya does, but there is no
Linux build path: the generated scripts emit the macOS recipe
(`clang++ -bundle`), and a compile attempted on Linux stops with a clear
message rather than failing deep in the compiler. See
[docs/PORTING.md](docs/PORTING.md).

## Quick start (per-session)

Run these from the repo root. Nothing is written outside the repo.

```bash
export MPYNODE_ROOT="$PWD"
export PYTHONPATH="$PWD/scripts:$PYTHONPATH"
export MAYA_PLUG_IN_PATH="$PWD/plug-ins:$MAYA_PLUG_IN_PATH"
export MPYNODE_USE_STUDIO=1      # ignore any studio-installed userSetup.py
```

Windows (`cmd.exe`):

```bat
set "MPYNODE_ROOT=%CD%"
set "PYTHONPATH=%CD%\scripts;%PYTHONPATH%"
set "MAYA_PLUG_IN_PATH=%CD%\plug-ins;%MAYA_PLUG_IN_PATH%"
set "MPYNODE_USE_STUDIO=1"
```

Then start Maya from that shell and open the authoring window:

```python
from mpynode.ui.mpynode_designer import show_designer
show_designer()
```

You do **not** need `cmds.loadPlugin` — the right plug-in loads on demand
the first time you create a node (verified: creating an `MPyNode` in a
clean session pulls in `mpynode_api2` by itself). Load them explicitly
only if you want them present before any node exists:

```python
import maya.cmds as mc
mc.loadPlugin("mpynode_api1")
mc.loadPlugin("mpynode_api2")
```

## Persistent `userSetup.py` install

For an "always-loaded" install inside a regular Maya session:

1. Copy `userSetup.py` into your Maya prefs `scripts/` directory:

   | Platform | Path |
   |---|---|
   | macOS | `~/Library/Preferences/Autodesk/maya/<ver>/scripts/` |
   | Linux | `~/maya/<ver>/scripts/` |
   | Windows | `Documents\maya\<ver>\scripts\` |

2. Tell it where the repo is. `userSetup.py` defaults to its own
   directory, which is correct only if you left it at the repo root — so
   when you **copy** it elsewhere, set `MPYNODE_PROJECT_DIR` in your
   environment to the repo root instead of editing the file.

3. Launch Maya. The Script Editor should show:

   ```
   [userSetup] node-designer2 paths set up: <your repo path>
   ```

   The `[mpynode_api1] loaded` / `[mpynode_api2] loaded` lines appear
   when the plug-ins load — on Maya start if auto-load is enabled for
   them, otherwise the first time you create a node.

4. Verify:

   ```python
   import maya.cmds as mc
   mc.allNodeTypes()  # should contain mPyNode, mPyIkSolver, mPyFile, ...
   ```

## Bypassing the install per-process

Set `MPYNODE_USE_STUDIO=1` to make `userSetup.py` skip its path
manipulation. Useful when testing against a different copy of the
plug-in, or when running `mayapy` in a shell that should not inherit
your interactive Maya's paths.

## Building the compiled plug-ins

**No binaries are committed.** A Maya plug-in is compiled against one Maya
version's devkit and will not load in another, so shipping one would ship
something most people cannot use. What *is* committed is the generated C++
and a build script beside it, so a fresh clone builds its own.

Every build script takes an optional Maya version:

```bash
bash compiled_templates/MPyNode/Ouch/build/build.sh          # newest installed Maya
bash compiled_templates/MPyNode/Ouch/build/build.sh 2024     # that version
MAYA=/path/to/maya bash .../build.sh                         # an explicit root
```

Windows is the same, from an *x64 Native Tools Command Prompt for VS*:

```bat
compiled_templates\MPyNode\Ouch\build\build.bat 2026
```

Resolution order is **argument, then `MAYA`, then the newest install
carrying a devkit**. The argument outranks the environment on purpose, so
`./build.sh 2024` is never quietly overridden by an exported `MAYA` left
over from something else. If nothing resolves, the script says which
versions it looked for and exits 1 — it never compiles against the wrong
Maya.

The whole set at once, and the mega demo plug-in:

```bash
tools/build_compiled_templates.sh     # every template tree

# all 37 in one plug-in, installed into the same folder's plugin/
cd compiled_templates/_combined_plugin && ./build.sh 2026
```

These scripts are generated, not hand-written; `tools/regen_build_scripts.py`
refreshes them from the generators and
`tests.compile.freshness.test_build_script_freshness` fails if a committed one has
drifted.

## Running the test suite

```bash
tools/run_tests.sh                                   # everything
tools/run_tests.sh tests.attributes.test_attr_types  # one module
```

On Windows use `tools\run_tests.bat`, its exact mirror.

The runner uses `tools/_unittest_exit.py` rather than `-m unittest` on
purpose: after `maya.standalone.initialize()` mayapy's teardown forces
exit 0, so a plain run reports failures as success.

`tools/run_tests.sh` points at Maya 2026 by default. For a different
install, set `MAYAPY` to your interpreter before running.

If scipy / PIL live outside Maya on your setup, point
`MPYNODE_EXTRA_PYTHONPATH` at that `site-packages` directory.

That directory must **not** contain its own numpy. It is appended to
`PYTHONPATH`, and Python places all of `PYTHONPATH` *ahead* of Maya's
`site-packages` — so a second numpy shadows Maya's and three `ndarray`
tests fail immediately (`ptp` and `itemset` were removed from `ndarray`
in NumPy 2.0, and `to_device` was added). Point it at a tree with scipy
and PIL but no numpy, or leave it unset.

## Troubleshooting

### `ImportError: No module named 'mpynode'`

`scripts/` isn't on `PYTHONPATH`, or your `userSetup.py` isn't running.
Check from inside Maya:

```python
import sys
print([p for p in sys.path if "mpynode" in p.lower()])
```

If that's empty, re-do the Quick start exports, or confirm you copied
`userSetup.py` to the right prefs path for your Maya version.

### `Plug-in 'mpynode_api1' not found`

`MAYA_PLUG_IN_PATH` doesn't include the repo's `plug-ins/`:

```python
import os
print(os.environ.get("MAYA_PLUG_IN_PATH", "<empty>"))
```

### Loaded plug-in from a different copy

Maya loads from the first matching entry in `MAYA_PLUG_IN_PATH`. If you
have a studio install as well as this tree, put this tree first and set
`MPYNODE_USE_STUDIO=1` so an installed `userSetup.py` can't re-order it.

### Maya 2026 mayapy aborts at `standalone.initialize()` (`requires neon crc32`)

Qt6's CPU-feature gate. It only fires where ARM CPU feature flags are
masked (some VMs report `hw.optional.armv8_crc32` / `hw.optional.neon`
as `0`). On native Apple Silicon those flags are present and Maya 2026
mayapy initializes fine — verified on an M4 Max (arm64, Qt 6.5.3):
standalone init, PySide6 widgets and offscreen render all work. If you
hit the abort, you're on a feature-masking VM — fall back to Maya 2024
mayapy.

### Harmless `swig/python detected a memory leak`

Prints at mayapy shutdown when `mPyIkSolver` is loaded. An Autodesk
SWIG-binding bug in `MPxIkSolverNode::doSolve()`'s `MStatus *` return
slot, cosmetic only.
