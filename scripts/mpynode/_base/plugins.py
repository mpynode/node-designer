"""Plugin loading helpers.

Vendored verbatim from an earlier mpynode/_base/plugins.py.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from maya import cmds


def load_or_reload_native_plugin(bundle_path: str) -> dict:
    """Load a freshly-compiled native plugin into the CURRENT Maya session
    WITHOUT touching the scene.

    If a plugin with the same base name is already loaded (e.g. a previous
    build of the same node), it is UNLOADED first so the new code actually
    takes effect -- the plain ``load-if-absent`` guard (see ``load_plugin``)
    would otherwise silently keep the stale compiled code resident, making a
    recompile-iterate workflow appear to "not pick up changes".

    Scene-safe: this only ever calls ``pluginInfo`` / ``unloadPlugin`` /
    ``loadPlugin`` -- it never calls ``file(new=...)`` or clears the scene.

    ``unloadPlugin`` raises (RuntimeError) if any node instance of a type the
    plugin registers still exists in the scene; rather than crash, that is
    surfaced as a human-readable ``error`` string and the new plugin is NOT
    loaded (the old one stays resident -- the caller can ask the user to delete
    the instances and retry).

    Returns a dict ``{"base": str, "loaded": bool, "reloaded": bool,
    "error": str | None}``. NEVER raises.

    ``loadPlugin`` takes the full ``bundle_path``; ``pluginInfo`` /
    ``unloadPlugin`` take the BASE name (e.g. ``"myPlug.bundle"``).
    """
    base = os.path.basename(bundle_path)
    result = {"base": base, "loaded": False, "reloaded": False, "error": None}

    try:
        already = bool(cmds.pluginInfo(base, q=True, loaded=True))
    except Exception:
        already = False

    if already:
        try:
            cmds.unloadPlugin(base)
            result["reloaded"] = True
        except Exception as exc:
            result["error"] = (
                "Could not unload the existing '%s' (it likely has nodes in "
                "use in the scene): %s" % (base, exc)
            )
            return result

    try:
        cmds.loadPlugin(bundle_path)
    except Exception as exc:
        result["error"] = "loadPlugin failed: %s" % exc
        return result

    # loadPlugin SWALLOWS a kFailure raised inside initializePlugin: it logs a
    # Maya warning, does NOT re-raise, and leaves the plugin UNLOADED
    # (mayapy-verified). A companion whose initializePlugin hits a command-name
    # clash with an already-loaded plugin fails exactly this way, so re-query
    # pluginInfo instead of trusting the silent return.
    try:
        actually_loaded = bool(cmds.pluginInfo(base, q=True, loaded=True))
    except Exception:
        actually_loaded = True  # can't tell -> trust loadPlugin (no false alarm)
    if actually_loaded:
        result["loaded"] = True
    else:
        result["error"] = (
            "'%s' failed to initialize (it likely registers a command name "
            "already in use by another loaded plugin -- see the Script Editor "
            "warning)." % base)

    return result


def validate_registered_types(bundle_path: str) -> dict:
    """Confirm a freshly-loaded bundle actually REGISTERED the compiled node
    type(s) the build recorded -- not merely that the plugin file loaded (#63).

    A bundle can load (``pluginInfo -q -loaded`` True) yet fail to register its
    node type (a bad ``initializePlugin``), so "loaded" is necessary but not
    sufficient to call a compile a success. This reads the build manifest
    (``<out_dir>/build/manifest.json``, the SSOT written by the compile
    controller) for the expected per-node ``type_name`` values and checks each
    against ``cmds.pluginInfo(base, query=True, dependNode=True)`` (the node
    types the loaded plugin provides).

    Returns ``{"base", "ok": bool, "expected": [...], "registered": [...],
    "missing": [...], "error": str | None}`` and NEVER raises. Tolerant: a
    missing/unreadable manifest yields ok=True with empty ``expected`` (there is
    nothing to check -- do not false-fail a load just because the build receipt
    is absent, mirroring auto_dirty's manifest read).
    """
    import json

    base = os.path.basename(bundle_path)
    result = {"base": base, "ok": True, "expected": [], "registered": [],
              "missing": [], "error": None}
    try:
        manifest = os.path.join(os.path.dirname(bundle_path), "build",
                                "manifest.json")
        if not os.path.isfile(manifest):
            return result  # no receipt -> nothing to validate against
        with open(manifest) as fh:
            data = json.load(fh)
        # A best-effort (strict=False) build also records DROPPED /
        # compile-failed nodes (via ``build_status``), and those never register
        # -- so they must NOT join the "expected registered types" set, else a
        # successful partial build false-fails as "loaded but did not register
        # its node type(s)".
        expected = [n.get("type_name") for n in (data.get("nodes") or [])
                    if n.get("type_name")
                    and n.get("build_status") not in ("dropped", "compile-failed")]
        result["expected"] = expected
        if not expected:
            return result
        try:
            registered = list(
                cmds.pluginInfo(base, query=True, dependNode=True) or [])
        except Exception as exc:
            result["ok"] = False
            result["error"] = ("could not query the types registered by %s: %s"
                               % (base, exc))
            return result
        result["registered"] = registered
        missing = [t for t in expected if t not in registered]
        result["missing"] = missing
        if missing:
            result["ok"] = False
            result["error"] = (
                "%s loaded but did not register the expected node type(s): %s"
                % (base, ", ".join(missing)))
    except Exception as exc:
        # Never let validation crash the load flow: an unreadable manifest is
        # "cannot validate", not a hard failure.
        result["error"] = "type validation skipped: %s" % exc
    return result


@contextmanager
def load_plugin(plugin_name: str) -> Iterator[None]:
    """Context manager that ensures a plugin is loaded.

    Loads the plugin if not already loaded. Does NOT unload on exit \u2014
    plugins typically need to remain loaded for the lifetime of the scene.
    Use this to gate operations that require a specific plugin.

    Example:
        with load_plugin("mpynode_api2"):
            cmds.runUndoableAPICommand(my_cmd_instance)
    """
    if not cmds.pluginInfo(plugin_name, q=True, loaded=True):
        cmds.loadPlugin(plugin_name, quiet=True)
    yield
