"""Time helpers shared by the time-exposing MPy nodes.

Pure-Python module: it imports ``maya.api.OpenMaya`` lazily inside the
function (never at import time), so it's safe to import from either the
API 1.0 or API 2.0 node modules -- the value computed is a scene-global
constant (the current time unit's frame rate), independent of node API.
"""

from __future__ import annotations


def current_fps() -> float:
    """Return the scene's current frame rate (frames per second).

    Derived from the current UI time unit: how many UI-frames fit in one
    second. Film -> 24.0, PAL -> 25.0, NTSC -> 30.0, etc. (fractional rates
    like 23.976 / 29.97 come through as floats). Falls back to 24.0 if the
    Maya API is unavailable.

    Backs ``TimeFloat`` (the type returned for ``self.time`` and kTime
    plug reads), which exposes it as ``self.time.fps`` and uses it for
    ``self.time.asSeconds()``.
    """
    try:
        import maya.api.OpenMaya as om

        return float(om.MTime(1.0, om.MTime.kSeconds).asUnits(om.MTime.uiUnit()))
    except Exception:
        return 24.0


def _on_time_unit_change(_client_data=None) -> None:
    """Dirty every MPy-family node when the scene time unit changes.

    ``TimeFloat`` (``self.time`` / kTime input reads) snapshots the fps at
    construction, so a node only reflects a new time unit once it next
    recomputes. A time-unit change does NOT dirty DG nodes on its own, so
    we force it here. Unit changes are a rare, manual operation (never
    during playback), so a broad dirty is cheap.
    """
    try:
        from maya import cmds
        from mpynode._node_registry import REGISTRY

        # Only query types whose plug-in is actually loaded. Calling
        # cmds.ls(type=...) on an unregistered type (e.g. an API 1.0 node
        # type when only the API 2.0 plug-in is loaded) prints a spurious
        # "Unknown object type: <type>" warning to the Script Editor.
        known_types = set(cmds.allNodeTypes() or [])
        for type_name in REGISTRY:
            if type_name not in known_types:
                continue
            for node in cmds.ls(type=type_name) or []:
                try:
                    cmds.dgdirty(node)
                except Exception:
                    pass
    except Exception:
        pass


_time_unit_callback_installed = False


def register_time_unit_change_callback() -> int:
    """Install the ``timeUnitChanged`` callback so ``self.time``/kTime
    reads re-derive their fps after a manual time-unit change. Tracked via
    ``CALLBACK_MANAGER`` (owner ``shared``) so the last-plugin-out teardown
    sweeps it cleanly.

    Idempotent: both plug-ins call this, but the unit-change effect is a
    scene-global broadcast, so only ONE callback is needed -- the guard
    prevents a duplicate (and the resulting double dgdirty sweep)."""
    global _time_unit_callback_installed
    if _time_unit_callback_installed:
        return 0
    try:
        import maya.api.OpenMaya as om
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_SHARED

        cb_id = om.MEventMessage.addEventCallback(
            "timeUnitChanged", _on_time_unit_change
        )
        token = CALLBACK_MANAGER.register(
            cb_id, om.MMessage.removeCallback, OWNER_SHARED
        )
        _time_unit_callback_installed = True
        return token
    except Exception:
        return -1


def reset_install_state() -> None:
    """Clear the install guard so a later plugin reload re-subscribes.
    Called by the last-plugin-out teardown after the shared callbacks have
    been deregistered."""
    global _time_unit_callback_installed
    _time_unit_callback_installed = False
