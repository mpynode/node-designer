"""userSetup.py for the node-designer2 development branch.

Place at:
  ~/Library/Preferences/Autodesk/maya/<ver>/scripts/userSetup.py

Maya runs this file at startup, BEFORE plugin auto-load. We:
  1. Prepend the phase's plug-ins/ directory to MAYA_PLUG_IN_PATH
  2. Prepend the phase's scripts/ directory to PYTHONPATH (so
     ``import mpynode`` works)
  3. Purge any stale mpynode-related modules from sys.modules

Set the env var ``MPYNODE_USE_STUDIO=1`` to skip this entirely (useful
when you want to test against a different version of the plugin).

Set ``MPYNODE_PROJECT_DIR`` to the repo root when this file is COPIED
somewhere other than the repo root (it otherwise resolves the repo from
its own location).
"""

from __future__ import annotations

import os
import sys


# This file lives at the repo root, so the repo IS its own directory. Set
# MPYNODE_PROJECT_DIR to override without editing this file (useful when
# userSetup.py is copied into a Maya scripts dir instead of symlinked).
# ``__file__`` is not defined when Maya execs this as ``./userSetup.py`` off a
# cwd entry of sys.path (a ``mayapy -c`` launched from the repo root); a
# NameError here used to abort the whole userSetup chain for that process.
_HERE = globals().get("__file__")
PROJECT_DIR = os.environ.get(
    "MPYNODE_PROJECT_DIR",
    os.path.dirname(os.path.abspath(_HERE)) if _HERE else os.getcwd(),
)


def _setup_phase_paths() -> None:
    """Force the project paths onto MAYA_PLUG_IN_PATH + PYTHONPATH.

    Idempotent: safe to call multiple times.
    """
    if os.environ.get("MPYNODE_USE_STUDIO") == "1":
        print(
            "[userSetup] MPYNODE_USE_STUDIO=1 \u2014 skipping node-designer2 setup"
        )
        return

    plugin_dir = os.path.join(PROJECT_DIR, "plug-ins")
    scripts_dir = os.path.join(PROJECT_DIR, "scripts")

    if not os.path.isdir(plugin_dir):
        print(f"[userSetup] plug-ins dir not found at {plugin_dir} \u2014 skip")
        return

    # Prepend plug-in path so Maya's auto-load picks our plugin first.
    existing_pin = os.environ.get("MAYA_PLUG_IN_PATH", "")
    if plugin_dir not in existing_pin.split(os.pathsep):
        os.environ["MAYA_PLUG_IN_PATH"] = (
            plugin_dir + os.pathsep + existing_pin
        ).rstrip(os.pathsep)

    # Prepend scripts path so ``import mpynode`` resolves from this phase.
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    # Purge mpynode modules loaded from some OTHER path (e.g. a studio install)
    # so a fresh import resolves from this phase. Ones already loaded from THIS
    # scripts_dir are kept: re-importing them makes duplicate class objects and
    # splits the runtime, breaking ``_pyClass`` logical-identity assertions.
    scripts_prefix = os.path.abspath(scripts_dir) + os.sep
    for k in list(sys.modules.keys()):
        if not (k == "mpynode" or k.startswith("mpynode.")):
            continue
        mod_file = getattr(sys.modules.get(k), "__file__", None)
        if mod_file and os.path.abspath(mod_file).startswith(scripts_prefix):
            continue
        del sys.modules[k]

    print(f"[userSetup] node-designer2 paths set up: {PROJECT_DIR}")


_setup_phase_paths()
