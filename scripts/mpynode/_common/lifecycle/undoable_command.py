"""Ownership rules for the session-global ``runUndoableAPICommand``.

Maya command names are GLOBAL to a session: the first plug-in to register a
name owns it, and a second registration of the same name fails. MPyNode's copy
of this command was folded into ``mpynode_api2`` so the toolkit ships two
plug-ins instead of three, but the file it came from -- ``undoable_api_command``
-- still ships in other toolkits (``rig`` loads it lazily from
``rig/nodetypes/plugins``). Both register ``runUndoableAPICommand``, and both
then monkey-patch ``cmds.runUndoableAPICommand`` with a wrapper that accepts a
python object, because the raw MEL-compatible command takes no arguments.

MEASURED in mayapy 2025, loading ``undoable_api_command`` and then
``mpynode_api2``: the second ``registerCommand`` failed (silently, into an
``except``), and the wrapper install then wrapped THE OTHER TOOLKIT'S WRAPPER.
That stack is not merely redundant -- it does not work. The outer wrapper calls
its inner with no arguments, and the inner needs ``py_class``::

    runUndoableAPICommand() missing 1 required positional argument: 'py_class'

Every undoable Designer action raised, in any session where the other plug-in
had loaded first -- including a plain reload of ``mpynode_api2``, since the old
guard only asked whether THIS plug-in had registered the name.

So ownership is decided against the whole session, and a name already served by
someone else is left alone: the two implementations are interface-identical, so
``run_undoable`` works just as well through theirs.
"""
from __future__ import annotations

import functools

COMMAND_NAME = "runUndoableAPICommand"

# Stamped on the wrapper WE install, so a re-install can peel its own previous
# wrapper instead of stacking on it. Deliberately not stamped on anyone else's:
# an unmarked wrapper is somebody's command that we must not unwrap.
_WRAPPER_MARK = "_mpynode_undoable_wrapper"


def command_owner():
    """Name of the loaded plug-in that has :data:`COMMAND_NAME` registered.

    ``None`` when the name is free. Asks every loaded plug-in rather than one,
    because the point is to find a registration that is NOT ours.
    """
    from maya import cmds

    try:
        loaded = cmds.pluginInfo(q=True, listPlugins=True) or []
    except Exception:
        return None
    for name in loaded:
        try:
            if COMMAND_NAME in (cmds.pluginInfo(name, q=True, command=True) or []):
                return name
        except Exception:
            continue          # a plug-in mid-unload: not the owner we want
    return None


def _peel_ours(func):
    """``func`` with any wrapper we installed removed, so a re-install wraps the
    live command rather than a closure over a deregistered one."""
    seen = 0
    while getattr(func, _WRAPPER_MARK, False) and seen < 8:
        nxt = getattr(func, "__wrapped__", None)
        if nxt is None:
            break
        func, seen = nxt, seen + 1
    return func


def install_wrapper(holder):
    """Give ``cmds.runUndoableAPICommand`` a signature that takes a python
    command object, and bracket each call in one named undo chunk.

    ``holder`` is the ``MPxCommand`` subclass whose ``call_class`` attribute
    carries the object across into ``doIt`` (the command itself is constructed
    by Maya and cannot be handed arguments).

    Idempotent: re-installing peels our previous wrapper first, so this can be
    called on every plug-in load without the stack that broke.
    """
    from maya import cmds

    cmd_func = _peel_ours(getattr(cmds, COMMAND_NAME))

    @functools.wraps(cmd_func)
    def wrapped(py_class):
        # Hold a reference so the object cannot be collected before doIt runs.
        holder.call_class = py_class
        cmds.undoInfo(openChunk=True, chunkName=COMMAND_NAME)
        try:
            return cmd_func()
        finally:
            cmds.undoInfo(closeChunk=True)

    wrapped.__wrapped__ = cmd_func
    setattr(wrapped, _WRAPPER_MARK, True)
    setattr(cmds, COMMAND_NAME, wrapped)
    return wrapped


def claim(plugin_name, register_fn, holder):
    """Register + wrap the command, unless the session already has one.

    Returns what happened, for the caller to log:
      * ``"registered"``   -- the name was free; it is ours now;
      * ``"rewrapped"``    -- already ours (a reload); wrapper re-applied;
      * ``"deferred:<p>"`` -- plug-in ``<p>`` serves it; we touched nothing.
    """
    owner = command_owner()
    if owner is None:
        register_fn()
        install_wrapper(holder)
        return "registered"
    if owner == plugin_name:
        install_wrapper(holder)
        return "rewrapped"
    return "deferred:%s" % owner


def release(plugin_name, deregister_fn):
    """Deregister the command only if ``plugin_name`` is what registered it.

    An unconditional deregister would pull the command out from under whoever
    else owns the name -- ``MFnPlugin.deregisterCommand`` takes a name, not a
    claim ticket. Returns True when it was ours and was removed.
    """
    if command_owner() != plugin_name:
        return False
    deregister_fn()
    return True
