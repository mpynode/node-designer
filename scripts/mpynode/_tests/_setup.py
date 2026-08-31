"""Standalone-mayapy harness shared by all tests.

Initializes maya.standalone exactly once per process and provides a
``ensure_plugins_loaded()`` helper that loads BOTH plugins (api1 + api2).
Called by every test module's ``setUpModule``.
"""

from __future__ import annotations

import maya.cmds as mc

_STANDALONE_INITIALIZED = False
_PLUGINS_LOADED = False
_STUB_COMPILED_LOADED = False


def standalone_init() -> None:
    global _STANDALONE_INITIALIZED
    if _STANDALONE_INITIALIZED:
        return
    import maya.standalone

    # Point the per-user data home at a throwaway dir so tests never read/write
    # the real ~/mpynode (or ~/.mpynode) and the legacy->new migration is a
    # guaranteed no-op under tests (it only ever touches the DEFAULT home).
    # setdefault so an outer MPYNODE_HOME (CI) still wins.
    import os
    import tempfile

    os.environ.setdefault(
        "MPYNODE_HOME", tempfile.mkdtemp(prefix="mpynode-test-home-"))

    maya.standalone.initialize()
    _STANDALONE_INITIALIZED = True


def ensure_plugins_loaded() -> None:
    """Load BOTH the api1 and api2 plugins (idempotent)."""
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED:
        return
    if not mc.pluginInfo("mpynode_api1", q=True, loaded=True):
        mc.loadPlugin("mpynode_api1")
    if not mc.pluginInfo("mpynode_api2", q=True, loaded=True):
        mc.loadPlugin("mpynode_api2")
    _PLUGINS_LOADED = True


def ensure_stub_compiled_plugin() -> None:
    """Load the test-only compiled-like plug-in (idempotent).

    Registers the plugin-provided node type ``stubCompiled`` so the forward
    Py->C++ swap tests can exercise a genuine PLUGIN-PROVIDED compiled target
    (not a stock built-in, which the swap gate must reject)."""
    global _STUB_COMPILED_LOADED
    if _STUB_COMPILED_LOADED:
        return
    import os

    path = os.path.join(os.path.dirname(__file__), "_stub_compiled_plugin.py")
    if not mc.pluginInfo("_stub_compiled_plugin", q=True, loaded=True):
        mc.loadPlugin(path)
    _STUB_COMPILED_LOADED = True
