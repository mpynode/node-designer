"""Snapshot plug I/O + envelopes + toggle reads for the instrumentation package.

Split out of the former ``instrumentation.py`` module (behavior unchanged).

The two snapshot plugs are EXCLUDED from setDependentsDirty propagation
(see ``_api2/_mpy_node.py``) so writes don't trigger another compute.
"""

from __future__ import annotations

import json

# Cross-module: watch-var (de)serialization lives in ``watch``; the plug I/O
# helpers below call those by name, so import them explicitly (bare-name lookup
# would fail now that they live in a sibling module).
from .watch import decode_watch_vars, encode_watch_vars


# Plug names — referenced by the widgets and the designer wiring.
PROFILE_SNAPSHOT_ATTR_NAME     = "_profileSnapshotData"
WATCH_VARS_ATTR_NAME           = "_watchVarsData"
PROFILE_ENABLED_ATTR_NAME      = "profile_enabled"
DEEP_PROFILE_ENABLED_ATTR_NAME = "deep_profile_enabled"
WATCH_ENABLED_ATTR_NAME        = "watch_enabled"


# ---- Profile snapshot envelope (JSON, no pickling — values are pure numerics) ----


def encode_profile_snapshot(stats: dict, deep_table: list[dict] | None = None) -> str:
    """JSON-encode the profile snapshot dict for the plug."""
    payload = {
        "last_us": float(stats.get("last_us", 0.0)),
        "avg_us":  float(stats.get("avg_us", 0.0)),
        "min_us":  float(stats.get("min_us", 0.0)),
        "max_us":  float(stats.get("max_us", 0.0)),
        "count":   int(stats.get("count", 0)),
    }
    if deep_table is not None:
        payload["deep_table"] = deep_table
    return json.dumps(payload, separators=(",", ":"))


def decode_profile_snapshot(text: str) -> dict | None:
    """Inverse of encode_profile_snapshot. Returns None on bad/empty input."""
    if not text:
        return None
    try:
        result = json.loads(text)
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    return result


# ---- Plug I/O. Reads use cmds.getAttr, writes cmds.setAttr -- which avoids the
# data-block internal-attr write quirks. ----


def _resolve_node_name(node_obj) -> str:
    """Resolve an API 1 or API 2 MObject to its node name. Empty on failure."""
    try:
        import maya.api.OpenMaya as om2

        return om2.MFnDependencyNode(node_obj).name()
    except Exception:
        pass
    try:
        import maya.OpenMaya as om1

        return om1.MFnDependencyNode(node_obj).name()
    except Exception:
        return ""


def write_profile_snapshot(
    node_obj, stats_dict: dict, deep_table: list[dict] | None = None
) -> None:
    """Write the profile snapshot to the node's _profileSnapshotData plug.

    Failures are silent — instrumentation must never crash the compute.
    """
    try:
        from maya import cmds
    except ImportError:
        return
    node_name = _resolve_node_name(node_obj)
    if not node_name:
        return
    try:
        text = encode_profile_snapshot(stats_dict, deep_table)
        cmds.setAttr(
            node_name + "." + PROFILE_SNAPSHOT_ATTR_NAME,
            text,
            type="string",
        )
    except Exception:
        pass


def read_profile_snapshot(node_name: str) -> dict | None:
    """Read the profile snapshot dict for a node by name."""
    try:
        from maya import cmds

        text = cmds.getAttr(node_name + "." + PROFILE_SNAPSHOT_ATTR_NAME) or ""
    except Exception:
        return None
    return decode_profile_snapshot(text)


# Live watch snapshots, keyed by node hash -> (MObjectHandle, vars). A locator's
# expression runs inside VP2's prepareForDraw, where ``cmds.setAttr`` on the
# snapshot plug is refused (and swallowed below), so for the whole life of the
# feature the Watch tab showed a locator's Inputs and stored vars but never its
# Locals / Framework. The panel now reads this in-memory copy first; the plug
# write stays as the persisted form and the fallback for DG-computed nodes.
_WATCH_MEM: dict = {}


def _watch_handle(node_obj):
    """API 2 handle for the in-memory key; None for an API 1 MObject."""
    try:
        import maya.api.OpenMaya as om2

        return om2.MObjectHandle(node_obj)
    except Exception:
        return None


def _read_watch_mem(node_name: str) -> dict | None:
    if not _WATCH_MEM:
        return None
    try:
        import maya.api.OpenMaya as om2

        sel = om2.MSelectionList()
        sel.add(node_name)
        obj = sel.getDependNode(0)
        rec = _WATCH_MEM.get(om2.MObjectHandle(obj).hashCode())
        # the hash is recycled across scenes: only a handle still pointing at
        # THIS node is a hit
        if rec is not None and rec[0].isValid() and rec[0].object() == obj:
            return dict(rec[1])
    except Exception:
        pass
    return None


def write_watch_vars(node_obj, vars_dict: dict) -> None:
    """Record the watch vars for a node: in memory (always) and on the node's
    _watchVarsData plug (when the caller's context allows a plug write)."""
    handle = _watch_handle(node_obj)
    if handle is not None:
        try:
            _WATCH_MEM[handle.hashCode()] = (handle, dict(vars_dict))
        except Exception:
            pass
    try:
        from maya import cmds
    except ImportError:
        return
    node_name = _resolve_node_name(node_obj)
    if not node_name:
        return
    try:
        text = encode_watch_vars(vars_dict)
        cmds.setAttr(
            node_name + "." + WATCH_VARS_ATTR_NAME,
            text,
            type="string",
        )
    except Exception:
        pass


def read_watch_vars(node_name: str) -> dict | None:
    """Read the watch vars dict for a node by name: the live in-memory
    snapshot when there is one, else the plug."""
    mem = _read_watch_mem(node_name)
    if mem is not None:
        return mem
    try:
        from maya import cmds

        text = cmds.getAttr(node_name + "." + WATCH_VARS_ATTR_NAME) or ""
    except Exception:
        return None
    return decode_watch_vars(text)


# ---- Toggle reads — done via OpenMaya findPlug for speed ----


def read_toggles(node_obj) -> tuple[bool, bool, bool]:
    """Return ``(profile, deep_profile, watch)`` toggle bools.

    Returns ``(False, False, False)`` if any toggle plug is missing
    (which is the case for nodes that haven't been re-initialized
    after a plug-in load — they get the default behavior
    of "everything off").
    """
    # Try API 2 first (most callers).
    try:
        import maya.api.OpenMaya as om2

        fn = om2.MFnDependencyNode(node_obj)
        try:
            profile = bool(fn.findPlug(PROFILE_ENABLED_ATTR_NAME, True).asBool())
        except Exception:
            profile = False
        try:
            deep = bool(fn.findPlug(DEEP_PROFILE_ENABLED_ATTR_NAME, True).asBool())
        except Exception:
            deep = False
        try:
            watch = bool(fn.findPlug(WATCH_ENABLED_ATTR_NAME, True).asBool())
        except Exception:
            watch = False
        return profile, deep, watch
    except Exception:
        pass
    # Fall back to API 1.
    try:
        import maya.OpenMaya as om1

        fn = om1.MFnDependencyNode(node_obj)
        try:
            profile = bool(fn.findPlug(PROFILE_ENABLED_ATTR_NAME, True).asBool())
        except Exception:
            profile = False
        try:
            deep = bool(fn.findPlug(DEEP_PROFILE_ENABLED_ATTR_NAME, True).asBool())
        except Exception:
            deep = False
        try:
            watch = bool(fn.findPlug(WATCH_ENABLED_ATTR_NAME, True).asBool())
        except Exception:
            watch = False
        return profile, deep, watch
    except Exception:
        return False, False, False
