"""Stored-vars (a.k.a. node "variables") API -- module-level helpers.

The plug-level attributes (``_storedVarNames``, ``_storedVarsData``)
exist on every node type. This module holds the variable logic as pure
functions that take a ``node_name`` string:

    from mpynode._common.storedvars.stored_vars_api import (
        get_variable_names, add_variable, remove_variable,
        set_variable, rename_variable, get_variables,
        set_variables, clear_variables,
        set_variable_persistent, is_variable_persistent,
    )

The canonical ``MPyNode`` wrapper exposes these as instance methods by
delegating here with ``self._name``; every specialty wrapper inherits
that surface through ``MPyNode`` (there is no longer a separate mixin --
the former ``StoredVarsMixin`` was folded into ``MPyNode``).
"""

from __future__ import annotations

import sys

import maya.cmds as mc


# ---- Pure-functional API: callable on any node NAME without instantiating a
# wrapper. For command undo/redo and callers that already hold the string. ----


def get_variable_names(node_name: str) -> list[str]:
    """Return the ordered list of stored-var names declared on the node."""
    try:
        raw = mc.getAttr(node_name + "._storedVarNames") or ""
    except Exception:
        return []
    if not raw or raw == "None":
        return []
    return [n.strip() for n in raw.split(",") if n.strip()]


def guard_var_name(node_name: str, name: str) -> None:
    """Reject a NEW stored var whose name collides with a framework slot.

    A name the node ALREADY carries is left alone, so a legacy var keeps
    working. Raises ``ValueError`` for interactive / API creation and rename;
    during attribute surgery (a ``.mpn`` restore, an attr reorder) it only
    warns, so a restore is never blocked. Fails OPEN: any lookup problem
    means "not reserved".
    """
    try:
        from mpynode._common.storedvars import stored_var_store

        if name in get_variable_names(node_name):
            return
        if name in stored_var_store.get_data(node_name):
            return
        from mpynode._common.interface.reserved_names import check_reserved_name

        reason = check_reserved_name(name, node_name=node_name)
        if not reason:
            return
        from mpynode._common.lifecycle import scene_state

        # Depth-only: ``in_attr_surgery`` also spans the trailing grace, which
        # would silently downgrade this guard for a couple of seconds after
        # any reorder / .mpn load. Every var a restore writes is set INSIDE the
        # block (mpn_io wraps them), so the block alone is the honest test.
        restoring = scene_state.in_attr_surgery_block()
    except Exception:
        return
    if not restoring:
        raise ValueError(reason)
    msg = "[mpynode] {}: {}".format(node_name, reason)
    try:
        import maya.api.OpenMaya as _om2

        _om2.MGlobal.displayWarning(msg)
    except Exception:
        pass
    sys.stderr.write(msg + "\n")


def add_variable(node_name: str, name: str, value=None, persistent: bool = True) -> None:
    """Declare a new variable on the node.

    With ``persistent=True`` (default) the name is written through to
    ``_storedVarNames`` (small, undoable) so it is flushed to
    ``_storedVarsData`` on scene save/export; with ``persistent=False``
    the variable is live for the session only (left out of
    ``_storedVarNames``). Either way the value lives in the in-memory
    store (deferred cache).
    """
    from mpynode._common.storedvars import stored_var_store

    guard_var_name(node_name, name)
    names = get_variable_names(node_name)
    if persistent:
        if name not in names:
            names.append(name)
    else:
        names = [n for n in names if n != name]
    mc.setAttr(node_name + "._storedVarNames", ",".join(names), type="string")

    existing = stored_var_store.get_data(node_name)
    if name not in existing:
        stored_var_store.set_var(node_name, name, value)


def remove_variable(node_name: str, name: str) -> None:
    from mpynode._common.storedvars import stored_var_store

    names = [n for n in get_variable_names(node_name) if n != name]
    mc.setAttr(node_name + "._storedVarNames", ",".join(names), type="string")
    stored_var_store.remove_var(node_name, name)


def set_variable(node_name: str, name: str, value,
                 persistent: bool | None = None) -> None:
    """Update a single variable's value (creates it if missing).

    ``persistent`` controls ``_storedVarNames`` membership the same way
    :func:`add_variable` does, but defaults to ``None`` = LEAVE IT ALONE:
    an existing var keeps whatever status it already has, and a brand-new
    one is session-only. Updating a value must not silently change a
    var's lifetime, and persistence is an opt-in (use ``add_variable``,
    ``set_variable_persistent``, or pass ``persistent=True`` here).
    """
    from mpynode._common.storedvars import stored_var_store

    guard_var_name(node_name, name)
    names = get_variable_names(node_name)
    if persistent is None:
        persistent = name in names
    if persistent:
        if name not in names:
            names.append(name)
    else:
        names = [n for n in names if n != name]
    mc.setAttr(node_name + "._storedVarNames", ",".join(names), type="string")
    stored_var_store.set_var(node_name, name, value)


def rename_variable(node_name: str, old_name: str, new_name: str) -> None:
    """Rename a stored var, preserving its current value."""
    from mpynode._common.storedvars import stored_var_store

    if old_name == new_name:
        return
    names = get_variable_names(node_name)
    if old_name not in names:
        raise ValueError(f"stored var {old_name!r} not found")
    if new_name in names:
        raise ValueError(f"cannot rename to {new_name!r}: already exists")
    guard_var_name(node_name, new_name)
    data = stored_var_store.get_data(node_name)
    if old_name in data:
        data[new_name] = data.pop(old_name)
        stored_var_store.set_data(node_name, data)
    new_names = [new_name if n == old_name else n for n in names]
    mc.setAttr(node_name + "._storedVarNames", ",".join(new_names), type="string")


def set_variable_persistent(node_name: str, name: str, persistent: bool) -> None:
    """Toggle whether ``name`` is saved with the scene, WITHOUT touching
    its live value.

    Persistence is purely membership in ``_storedVarNames`` (the gate the
    save flush consults). The value itself stays in the in-memory store
    either way, so demoting a var leaves it live for the rest of the
    session -- it just stops being serialized (and won't return on the
    next load). Promoting adds it back to the saved set.
    """
    names = get_variable_names(node_name)
    if persistent:
        if name not in names:
            names.append(name)
    else:
        names = [n for n in names if n != name]
    mc.setAttr(node_name + "._storedVarNames", ",".join(names), type="string")


def is_variable_persistent(node_name: str, name: str) -> bool:
    """True if ``name`` is saved with the scene (member of
    ``_storedVarNames``)."""
    return name in get_variable_names(node_name)


def get_variables(node_name: str) -> dict:
    """Return the current persistent dict (from the in-memory store).

    The store hydrates lazily from ``_storedVarsData`` the first time a
    node is touched and is authoritative thereafter (the plug is cleared
    on scene load -- see :mod:`mpynode._common.storedvars.stored_var_store`).
    """
    from mpynode._common.storedvars import stored_var_store

    return stored_var_store.get_data(node_name)


def set_variables(node_name: str, data: dict) -> None:
    """Replace the persistent dict (and the names list to match)."""
    from mpynode._common.storedvars import stored_var_store

    names = sorted(data.keys())
    mc.setAttr(node_name + "._storedVarNames", ",".join(names), type="string")
    stored_var_store.set_data(node_name, dict(data))


def clear_variables(node_name: str) -> None:
    from mpynode._common.storedvars import stored_var_store

    mc.setAttr(node_name + "._storedVarNames", "", type="string")
    stored_var_store.set_data(node_name, {})
    try:
        mc.setAttr(node_name + "._storedVarsData", "", type="string")
    except Exception:
        pass


# There is no StoredVarsMixin: ``MPyNode`` implements the stored-vars surface
# inline by delegating to the functions above, and every wrapper inherits it.
