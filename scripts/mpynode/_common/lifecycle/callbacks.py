"""Process-wide singleton for tracking MNodeMessage / MEventMessage
callback IDs so we can deregister cleanly on plugin unload.

Both API 1 and API 2 plugins share the same singleton (this module is pure
Python and imports nothing from maya). Each callback is tagged with an OWNER so
a plugin's ``uninitializePlugin`` can tear down ONLY its own callbacks via
``remove_for_owner(owner)`` -- NOT every callback. Previously both plugins
called ``remove_all()``, so unloading EITHER plugin wiped the OTHER still-loaded
plugin's callbacks (and the shared scene-change callbacks), leaving it deaf.

Owners by convention:
  * ``"mpynode_api1"`` / ``"mpynode_api2"`` -- a plugin's own (per-node-type)
    callbacks, removed when THAT plugin unloads.
  * ``"shared"`` -- cross-plugin scene/lifecycle callbacks (scene-change,
    time-unit, auto-dirty, scene-io) that must live as long as ANY plugin is
    loaded. The plugin load refcount (:func:`mark_plugin_loaded` /
    :func:`mark_plugin_unloaded`) lets the LAST plugin to unload tear these down
    (and reset the install guards) so a later reload re-registers them.

Each register call returns an opaque int token usable with ``unregister``.
"""

from __future__ import annotations

from typing import Any, Callable

# Owner tags. The two plugin owners MUST equal the plugin names the plug-in
# files pass to remove_for_owner() in uninitializePlugin (i.e. their
# ``PLUGIN_NAME``), or a plugin would fail to tear down its own callbacks.
OWNER_SHARED = "shared"
OWNER_API1 = "mpynode_api1"
OWNER_API2 = "mpynode_api2"

_SHARED = OWNER_SHARED


class CallbackManager:
    """Tracks (callback_id, deregister_func, owner) triples for safe,
    owner-scoped teardown."""

    def __init__(self) -> None:
        # entries are (callback_id, deregister_func, owner); a removed slot is
        # marked (None, dereg, owner) in place so existing int tokens stay valid.
        self._callbacks: list[tuple[Any, Callable[[Any], None], Any]] = []

    def register(
        self,
        callback_id: Any,
        deregister_func: Callable[[Any], None],
        owner: Any = _SHARED,
    ) -> int:
        """Track a callback under ``owner``. ``deregister_func(callback_id)`` is
        called on ``remove_for_owner(owner)`` / ``remove_all`` / ``unregister``.

        Returns an integer token (index into the internal list) usable with
        ``unregister``. ``owner`` defaults to ``"shared"``.
        """
        token = len(self._callbacks)
        self._callbacks.append((callback_id, deregister_func, owner))
        return token

    def unregister(self, token: int) -> bool:
        """Remove a single callback by token. Safe to call twice."""
        if token < 0 or token >= len(self._callbacks):
            return False
        cb_id, dereg, owner = self._callbacks[token]
        if cb_id is None:
            return False
        try:
            dereg(cb_id)
        except Exception:
            pass
        # Mark removed (don't pop; preserves token validity for others).
        self._callbacks[token] = (None, dereg, owner)
        return True

    def remove_for_owner(self, owner: Any) -> int:
        """Deregister every tracked callback whose owner == ``owner``. Slots are
        marked removed IN PLACE (no reindex) so outstanding tokens stay valid.
        Returns the number removed. A raising deregister never aborts the sweep.
        """
        n = 0
        for i, (cb_id, dereg, own) in enumerate(self._callbacks):
            if cb_id is None or own != owner:
                continue
            try:
                dereg(cb_id)
                n += 1
            except Exception:
                pass
            self._callbacks[i] = (None, dereg, own)
        return n

    def remove_all(self) -> int:
        """Deregister EVERY tracked callback (full teardown). Returns the count.

        Kept for emergencies / full process teardown; the per-plugin unload path
        now uses :func:`remove_for_owner` so it can't wipe a co-loaded plugin.
        """
        n = 0
        for cb_id, dereg, _owner in self._callbacks:
            if cb_id is None:
                continue
            try:
                dereg(cb_id)
                n += 1
            except Exception:
                pass
        self._callbacks.clear()
        return n

    def count_for_owner(self, owner: Any) -> int:
        """Number of LIVE (not-yet-removed) callbacks tracked under ``owner``."""
        return sum(
            1 for cb_id, _d, own in self._callbacks if cb_id is not None and own == owner
        )

    def owners(self) -> set:
        """Set of owners with at least one live callback."""
        return {own for cb_id, _d, own in self._callbacks if cb_id is not None}


CALLBACK_MANAGER = CallbackManager()
"""Module-level singleton. Both plugins share this instance."""


# ---------------------------------------------------------------------------
# Plugin load refcount -- lets the LAST plugin to unload tear down the shared
# callbacks (and reset install guards) while a single-plugin unload leaves the
# co-loaded plugin's shared callbacks intact.
# ---------------------------------------------------------------------------

_loaded_plugins: set = set()


def mark_plugin_loaded(name: str) -> int:
    """Record that plugin ``name`` is loaded. Idempotent. Returns the current
    loaded-plugin count."""
    _loaded_plugins.add(name)
    return len(_loaded_plugins)


def mark_plugin_unloaded(name: str) -> int:
    """Record that plugin ``name`` is unloaded. Idempotent (floors at 0).
    Returns the REMAINING loaded-plugin count -- when this hits 0 the caller is
    the last plugin and should tear down the ``"shared"`` callbacks + reset the
    shared install guards."""
    _loaded_plugins.discard(name)
    return len(_loaded_plugins)


def loaded_count() -> int:
    """Current number of loaded mpynode plugins."""
    return len(_loaded_plugins)


def reset_plugin_refcount() -> None:
    """Test-only: clear the loaded-plugin set."""
    _loaded_plugins.clear()
