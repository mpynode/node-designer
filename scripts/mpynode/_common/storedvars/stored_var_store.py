"""Authoritative in-memory store for per-node stored variables.

Why this exists
---------------
``_storedVarsData`` is a string plug holding a base64/pickle blob of a
node's persistent variables. Historically every compute() decoded and
re-encoded that blob and wrote it straight back to the plug -- once per
frame, on the EM worker thread. That meant (a) a pickle round-trip every
frame even when nothing changed and (b) a ``setAttr`` from a worker
thread.

This module makes an in-memory dict the *authoritative* source of truth
for stored vars during a session ("deferred cache", Tier-2):

  * On scene load the blob is decoded into the store and the plug is
    CLEARED (``load_and_clear_all``). The plug stays empty for the rest
    of the session -- reads never see stale serialized data.
  * compute() reads/writes the store in memory (no per-frame pickle, no
    worker-thread ``setAttr``).
  * On scene save / export ONLY the vars a node has declared persistent
    (its ``_storedVarNames`` registry) are flushed back to the plug
    (``flush_all``), then the plugs are cleared again
    (``clear_loaded_plugs``). Every other ``self.X`` write is a
    SESSION-only var: it lives in the store for scrub stability but is
    never serialized, so it re-initialises on the next load/import.
    "Make/Promote Persistent" is what adds a name to the registry.

Identity
--------
Keyed by the session-local ``MObjectHandle.hashCode()`` string (via
``init_registry._node_uuid_from_*``) -- a memory-handle identity that is
thread-safe to compute (no DG access), so the same node resolves to the
same key whether we hold its MObject (compute, worker thread) or its
name (UI / API, main thread).

Thread-safety
-------------
All cache access is guarded by a re-entrant lock; compute runs on EM
worker threads while the UI / scene callbacks run on the main thread.
Plug I/O (``getAttr`` / ``setAttr`` / ``ls``) is performed ONLY on the
main thread (load/flush/clear sweeps + name-based API); the worker-thread
read path is handed the already-read plug string by the caller.
"""

from __future__ import annotations

import sys
import threading
from typing import Any, Optional

from mpynode._common.io import serialization

# node_hash -> decoded stored-vars dict (authoritative during session)
_DATA: dict[str, dict] = {}
# node_hash values that have been hydrated from their plug at least once
_LOADED: set[str] = set()
# re-entrant: name-based helpers call mobject-based helpers internally
_LOCK = threading.RLock()

# Change listeners: called with the node's thread-safe hash after a compute()
# rewrites its stored vars. Lets the designer's Variables/Storage panel refresh
# without polling. A pure-Python registry rather than a schema plug, so no new
# attr is needed on the api1/api2 builders or the native codegen that mirrors
# them, and the notify fires from the one choke point (``set_for_compute``).
# Listeners run on the CALLING thread (an EM worker during compute), so one MUST
# NOT touch the DG / Qt -- it gets only the hash and marshals to the main thread
# itself (see the designer's ``_on_stored_vars_changed``).
_CHANGE_LISTENERS: list = []


def add_change_listener(callback) -> None:
    """Register ``callback(node_hash)`` to fire after a compute() rewrites a
    node's stored vars. Idempotent. See ``_CHANGE_LISTENERS`` for the
    thread-safety contract (listener runs on the caller's thread)."""
    with _LOCK:
        if callback not in _CHANGE_LISTENERS:
            _CHANGE_LISTENERS.append(callback)


def remove_change_listener(callback) -> None:
    """Unregister a listener added via :func:`add_change_listener` (no-op if it
    was never registered)."""
    with _LOCK:
        try:
            _CHANGE_LISTENERS.remove(callback)
        except ValueError:
            pass


def _notify_change(node_hash: str) -> None:
    """Fire every registered change listener with ``node_hash``. Cheap early-out
    when nothing is listening (the common headless / no-UI case). A listener
    that raises is isolated -- it can never break the compute that triggered
    the notify, nor stop the other listeners from running."""
    if not _CHANGE_LISTENERS:
        return
    with _LOCK:
        listeners = list(_CHANGE_LISTENERS)
    for cb in listeners:
        try:
            cb(node_hash)
        except Exception:
            pass

_DATA_ATTR = "_storedVarsData"
# Names a node has declared persistent. ONLY these keys are serialized; every
# other ``self.X`` write is SESSION-only (kept in the store for scrub stability,
# never saved, re-initialises on the next load/import).
_NAMES_ATTR = "_storedVarNames"


def _registered_names(node_name: str) -> set:
    """Return the set of names declared persistent on the node (read from
    the ``_storedVarNames`` plug, which is saved with the scene)."""
    from maya import cmds as _cmds

    try:
        raw = _cmds.getAttr(node_name + "." + _NAMES_ATTR) or ""
    except Exception:
        return set()
    if not raw or raw == "None":
        return set()
    return {n.strip() for n in raw.split(",") if n.strip()}


# ---- Identity (delegates to init_registry's thread-safe hashCode scheme) ----


def _hash_for_mobject(mobject) -> Optional[str]:
    try:
        from mpynode._common.lifecycle.init_registry import _node_uuid_from_mobject

        return _node_uuid_from_mobject(mobject)
    except Exception:
        return None


def _hash_for_name(node_name: str) -> Optional[str]:
    try:
        from mpynode._common.lifecycle.init_registry import _node_uuid_from_name

        return _node_uuid_from_name(node_name)
    except Exception:
        return None


# ---- Compute hot path (worker thread). The caller supplies the plug string so
# we never touch the DG off the main thread. ----


def load_for_compute(node_obj, raw_str: str) -> dict:
    """Return the node's stored vars (a shallow copy).

    On the first call for a node the supplied ``raw_str`` (already read
    from the plug by the caller via OpenMaya) is decoded and cached; on
    subsequent calls the cached dict is returned and ``raw_str`` is
    ignored -- so once the plug has been cleared post-load the empty
    string never wipes the live cache.
    """
    h = _hash_for_mobject(node_obj)
    if h is None:
        # No stable identity -- fall back to a plain decode (no caching).
        return serialization.decode_stored_vars(raw_str or "")
    with _LOCK:
        cached = _DATA.get(h)
        # Authoritative: we already hold real (non-empty) data.
        if h in _LOADED and cached:
            return dict(cached)
        # Blob still present (plug not yet cleared) -> decode. This also heals a
        # cache a premature pre-sweep compute poisoned with {} by reading the
        # plug before its value was set (compute can fire before kAfterOpen).
        if raw_str:
            decoded = serialization.decode_stored_vars(raw_str)
            _DATA[h] = decoded
            _LOADED.add(h)
            return dict(decoded)
        # Plug already cleared post-load: hand back whatever the sweep cached.
        if h in _LOADED:
            return dict(cached or {})
        # Nothing available yet -- do NOT mark _LOADED, so a later call (or the
        # kAfterOpen sweep) with the real blob can still populate the cache.
        return {}


def set_for_compute(node_obj, full_dict: dict) -> None:
    """Replace a node's stored vars from compute() (in memory only)."""
    h = _hash_for_mobject(node_obj)
    if h is None:
        return
    with _LOCK:
        _DATA[h] = dict(full_dict)
        _LOADED.add(h)
    # OUTSIDE the lock -- a listener marshals to the main thread and must never
    # run while we hold the store lock.
    _notify_change(h)


# ---- Name-based API (main thread): stored_vars_api / UI / Init. ----


def _read_plug_by_name(node_name: str) -> str:
    from maya import cmds as _cmds

    try:
        return _cmds.getAttr(node_name + "." + _DATA_ATTR) or ""
    except Exception:
        return ""


def _ensure_loaded_by_name(h: str, node_name: str) -> None:
    if h in _LOADED:
        return
    _DATA[h] = serialization.decode_stored_vars(_read_plug_by_name(node_name))
    _LOADED.add(h)


def get_data(node_name: str) -> dict:
    """Return a node's stored vars (shallow copy), loading lazily."""
    h = _hash_for_name(node_name)
    if h is None:
        return serialization.decode_stored_vars(_read_plug_by_name(node_name))
    with _LOCK:
        _ensure_loaded_by_name(h, node_name)
        return dict(_DATA.get(h, {}))


def set_data(node_name: str, data: dict) -> None:
    """Replace a node's stored vars (in memory only)."""
    h = _hash_for_name(node_name)
    if h is None:
        return
    with _LOCK:
        _DATA[h] = dict(data)
        _LOADED.add(h)
    # OUTSIDE the lock, as in set_for_compute. These name-based writers are the
    # OTHER half of the store's write surface -- stored_vars_api (and so
    # MPyNode.set_variable) lands here, not in set_for_compute -- so leaving
    # them silent meant a scripted write updated the store with no panel told,
    # and the UI kept rendering the previous value until something else
    # happened to refresh it.
    _notify_change(h)


def set_var(node_name: str, name: str, value: Any) -> None:
    h = _hash_for_name(node_name)
    if h is None:
        return
    with _LOCK:
        _ensure_loaded_by_name(h, node_name)
        _DATA.setdefault(h, {})[name] = value
    _notify_change(h)


def remove_var(node_name: str, name: str) -> None:
    h = _hash_for_name(node_name)
    if h is None:
        return
    with _LOCK:
        _ensure_loaded_by_name(h, node_name)
        _DATA.get(h, {}).pop(name, None)
    _notify_change(h)


# ---- Scene-node sweep (load / flush / clear) -- main thread only. ----


def _iter_mpy_nodes():
    """Yield every mPy* node name in the current scene."""
    from maya import cmds as _cmds
    from mpynode._node_registry import all_native_types

    # Pre-filter to registered types: cmds.ls(type=X) on a type whose plug-in
    # isn't loaded prints a spurious "Unknown object type: X" warning.
    try:
        known = set(_cmds.allNodeTypes() or [])
    except Exception:
        known = None

    seen = set()
    for nt in all_native_types():
        if known is not None and nt not in known:
            continue
        try:
            for name in _cmds.ls(type=nt) or []:
                if name not in seen:
                    seen.add(name)
                    yield name
        except Exception:
            continue


def load_and_clear_all() -> int:
    """Hydrate every node's stored vars into the cache, then clear the
    plug. Idempotent. Returns the count of nodes whose plug was cleared.

    Per-node atomic order (decode-then-clear) guarantees no window where
    the plug is empty but the cache is unpopulated.
    """
    from maya import cmds as _cmds

    cleared = 0
    for node_name in _iter_mpy_nodes():
        h = _hash_for_name(node_name)
        if h is None:
            continue
        raw = _read_plug_by_name(node_name)
        with _LOCK:
            # Re-decode whenever the PLUG still holds data: that is the file's
            # authoritative copy and we're about to clear it, so it must beat any
            # cache a premature EM eager-eval populated. Heals two poisonings:
            #   * a {} cache (compute read the plug before its value was set);
            #   * a PARTIAL cache decoded in the open/import fail-closed window
            #     (pickle vars refused) -- after a Trust grant the plug is
            #     re-decoded here, so those vars aren't silently dropped.
            # Skip only when the cache is loaded, non-empty AND the plug was
            # already swept empty (the normal idempotent re-call).
            already = h in _LOADED and bool(_DATA.get(h)) and not raw
        if already:
            with _LOCK:
                loaded_keys = set(_DATA.get(h, {}).keys())
        else:
            # Detailed decode so unrestorable vars (e.g. a class not importable
            # here) can be logged; the rest still populate the cache.
            values, failures = serialization.decode_stored_vars_detailed(raw)
            with _LOCK:
                # MERGE, not replace: Init runs earlier in the open sweep and
                # flushes session-only self.X vars into the cache. The plug holds
                # only persistent vars, so it wins per key without dropping them.
                merged = dict(_DATA.get(h, {}))
                merged.update(values)
                _DATA[h] = merged
                _LOADED.add(h)
            loaded_keys = set(values.keys())
            if failures:
                detail = ", ".join(
                    "%s (%s)" % (k, v) for k, v in failures.items()
                )
                msg = (
                    "[stored_var_store] %s: skipped %d unrestorable stored "
                    "var(s) on load: %s\n" % (node_name, len(failures), detail)
                )
                sys.stderr.write(msg)
                try:
                    from mpynode._common.util.log_bus import log as _log

                    _log(msg.strip(), level="warning")
                except Exception:
                    pass
        # Legacy migration: anything serialized in the file predates the
        # registry-gated save model and was persistent under the old rules, so
        # register it. Session-only vars are never in the blob, never migrated.
        if loaded_keys:
            registered = _registered_names(node_name)
            if loaded_keys - registered:
                try:
                    _cmds.setAttr(
                        node_name + "." + _NAMES_ATTR,
                        ",".join(sorted(registered | loaded_keys)),
                        type="string",
                    )
                except Exception:
                    pass
        # Clear the plug: the cache is now authoritative and reads for the rest
        # of the session must never see a stale serialized blob.
        try:
            _cmds.setAttr(node_name + "." + _DATA_ATTR, "", type="string")
            cleared += 1
        except Exception:
            pass
    return cleared


def flush_all() -> dict:
    """Encode each cached node's REGISTERED stored vars back to its plug
    so they persist on the next save/export. Session-only vars (in the
    store but not in ``_storedVarNames``) are intentionally skipped.
    Returns ``{node_name: [dropped]}`` for any node where unpicklable
    values had to be dropped.
    """
    from maya import cmds as _cmds

    dropped_report: dict = {}
    for node_name in _iter_mpy_nodes():
        h = _hash_for_name(node_name)
        if h is None:
            continue
        with _LOCK:
            if h not in _DATA:
                continue
            data = dict(_DATA[h])
        # Only registered vars are serialized; session-only ones stay in-memory.
        registered = _registered_names(node_name)
        data = {k: v for k, v in data.items() if k in registered}
        if not data:
            # Nothing persistent -> clear, so a blob written before a var was
            # demoted doesn't get re-serialized.
            try:
                _cmds.setAttr(node_name + "." + _DATA_ATTR, "", type="string")
            except Exception:
                pass
            continue
        blob, dropped = serialization.encode_stored_vars_resilient(data)
        if dropped:
            dropped_report[node_name] = dropped
            sys.stderr.write(
                "[stored_var_store] dropped unpicklable stored vars on "
                "%s: %s\n" % (node_name, ", ".join(dropped))
            )
        try:
            _cmds.setAttr(node_name + "." + _DATA_ATTR, blob, type="string")
        except Exception as exc:
            sys.stderr.write(
                "[stored_var_store] flush failed on %s: %s\n"
                % (node_name, exc)
            )
    return dropped_report


def clear_loaded_plugs() -> int:
    """Clear the data plug on every loaded node (called after a save /
    export flush) so the plug stays empty during the session -- the
    in-memory store remains the authoritative source of truth and reads
    never see stale serialized data. Returns the count cleared.
    """
    from maya import cmds as _cmds

    cleared = 0
    for node_name in _iter_mpy_nodes():
        h = _hash_for_name(node_name)
        if h is None:
            continue
        with _LOCK:
            loaded = h in _LOADED
        if not loaded:
            continue
        try:
            _cmds.setAttr(node_name + "." + _DATA_ATTR, "", type="string")
            cleared += 1
        except Exception:
            pass
    return cleared


# ---- Eviction + diagnostics ----


def evict(node_name: str) -> None:
    h = _hash_for_name(node_name)
    if h is None:
        return
    with _LOCK:
        _DATA.pop(h, None)
        _LOADED.discard(h)


def evict_all() -> None:
    """Drop the entire cache (scene new/open)."""
    with _LOCK:
        _DATA.clear()
        _LOADED.clear()


def footprint(node_name: str) -> int:
    """Approximate in-memory byte size of a node's stored vars."""
    import pickle

    h = _hash_for_name(node_name)
    if h is None:
        return 0
    with _LOCK:
        data = _DATA.get(h)
        if not data:
            return 0
        try:
            return len(pickle.dumps(data, protocol=5))
        except Exception:
            return 0


def total_footprint() -> int:
    """Approximate total in-memory byte size of all cached stored vars."""
    import pickle

    total = 0
    with _LOCK:
        snapshot = list(_DATA.values())
    for data in snapshot:
        try:
            total += len(pickle.dumps(data, protocol=5))
        except Exception:
            pass
    return total


def _cache_info() -> tuple:
    """(loaded_node_count, total_footprint_bytes) -- tests/diagnostics."""
    with _LOCK:
        n = len(_LOADED)
    return (n, total_footprint())
