"""Managed-plug governance -- which plugs an mpynode is allowed to surface.

An mpynode polices its own plug surface. A plug reaches ``self.<name>`` /
``node.<name>`` only if the framework put it there:

  * **STATIC** attributes are part of the node type itself -- declared in the
    plug-in's ``initialize()`` (``outMesh``, ``_timeIn``, ``outColor``) or
    inherited from ``MPxNode`` / ``MFnDagNode`` / ``MPxDeformerNode``
    (``nodeState``, ``worldMatrix``, ``envelope``, ``weightList``). Nobody adds
    these at runtime, so nobody can smuggle one in. Always managed.
  * **DYNAMIC** attributes are added at runtime. The only sanctioned way is
    ``add_input_attr`` / ``add_output_attr`` (Node Designer, the ``.mpn``
    loader, the Python API), which records the name in the hidden
    ``_inputAttrs`` / ``_outputAttrs`` map. A dynamic attribute absent from
    that map came from a bare ``cmds.addAttr`` -- it is NOT managed.

An unmanaged plug is treated as if it did not exist at all: reads decline and
fall through to compute locals / init bindings / stored vars exactly as an
unknown name does, and writes land in user storage instead of the plug. That
equivalence is deliberate -- it means governance adds no new failure mode, only
removes a surface.

Cost. The discriminator is ``MFnAttribute.isDynamic()``, so the STATIC case --
the overwhelming majority of any node's surface -- never touches the attr map.
The map is loaded lazily on the first DYNAMIC attribute seen, and every verdict
is memoised per node. Measured on this machine (mayapy 2026, api1, 100-200k
iterations):

    is_managed(), steady state, any origin        ~650 ns
      of which om.MObjectHandle(node) alone       ~434 ns   (dominant term)
      cached handle .hashCode() / .isValid()       ~53 / 56 ns
    MFnAttribute(attr).isDynamic()                ~833 ns   (memoised away)
    _attr_mobject_for_name -- ALREADY paid        ~790-830 ns per read
    PlugProxy.__getattr__ end to end             ~3250-3450 ns

So the gate is ~80% of the name resolve but only ~19% of a complete plug read,
and it is flat across static / managed / compound-child / denied. Note the
memo is worth keeping precisely BECAUSE ``isDynamic()`` is expensive: checking
it live on every read would cost more than the whole cached gate.

Invalidation is generation-based. Every write to the attr map funnels through
``_MPyNode._write_input_map`` / ``_write_output_map`` (11 call sites, all in
``wrappers/_mpy_node.py``), which call :func:`invalidate`. Undo / redo and
scene events are covered by :func:`install_once` -- see its docstring for why
undo is the case that actually needs a callback.

Node deletion needs no callback. Maya recycles MObject slots aggressively (54
of 60 hash codes were reused in a create/delete loop), but a handle held across
the deletion always reports ``isValid() == False``, so ``_entry_for`` rebuilds
rather than aliasing the new occupant.

Foreign nodes are not gated. A node with no ``_inputAttrs`` attribute is not an
mpynode, so the rule does not apply and everything resolves as before -- a
``PlugProxy`` built on a stock ``transform`` keeps working.

This is a portability and discipline contract, NOT a sandbox. ``cmds.getAttr``
still reaches anything from inside a compute. What the gate guarantees is that
``self.<name>`` means exactly what the C++ spec extractor
(``native/spec/spec_extractor.py``) will see, so a node that runs in the editor
is a node that compiles.
"""

from __future__ import annotations

# api1, NOT api2 -- deliberately. The whole ``plugs`` package is api1, so the
# MObjects handed here are api1, and Maya rejects an MObject of one flavour in
# the other's signatures (``TypeError: argument 1 of type 'MObject &'``). Since
# every call below is wrapped in a fail-open ``except``, an api2 import would
# NOT error -- it would silently allow everything and make the gate a no-op.
import maya.OpenMaya as om

# Hidden string plugs holding the framework's record of every dynamic attribute
# it added. Their presence is also how we recognise an mpynode at all.
_INPUT_MAP_ATTR  = "_inputAttrs"
_OUTPUT_MAP_ATTR = "_outputAttrs"

# Bumped whenever any node's managed set may have changed. Coarse on purpose:
# edits are rare, the rebuild is lazy, and a global counter cannot go stale in
# the one direction that matters -- a stale ALLOW.
_GENERATION = 0

# hashCode -> _Entry. Entries are validated against both the generation and the
# MObjectHandle, so a recycled hash after a node is deleted cannot alias.
_CACHE: dict = {}


class _Entry:
    """Per-node governance state. ``managed`` stays None until a dynamic
    attribute is actually seen, so a node whose expression only touches static
    plugs never pays the map decode."""

    __slots__ = ("gen", "handle", "verdicts", "managed", "is_mpynode")

    def __init__(self, gen, handle, is_mpynode):
        self.gen        = gen
        self.handle     = handle
        self.verdicts   = {}
        self.managed    = None
        self.is_mpynode = is_mpynode


def invalidate() -> None:
    """Drop every cached verdict. Called from the attr-map write choke points
    and from the undo / redo / scene callbacks."""
    global _GENERATION
    _GENERATION += 1
    _CACHE.clear()


_installed = False


def install_once() -> None:
    """Subscribe to undo / redo / scene events so the cache can't outlive a
    change the framework never saw. Idempotent, fail-soft.

    Undo is the case that actually needs this. ``add_input_attr`` invalidates
    through ``_write_input_map``, but UNDOING it restores the previous
    ``_inputAttrs`` string via Maya's own undo of the ``setAttr`` -- our Python
    never runs, the node is never destroyed, so its cached handle stays valid
    and a just-removed attribute would keep its cached ALLOW.

    Scene events are cheap insurance: an open destroys the old nodes, so their
    ``MObjectHandle``s go invalid and ``_entry_for`` rebuilds anyway (verified:
    Maya recycles MObject slots aggressively, but a stale handle always reports
    ``isValid() == False``). Clearing outright is simply cheaper than checking.

    Self-installing on first use rather than wired into plug-in registration:
    the gate has no natural init hook, and this keeps the callback's lifetime
    tied to the first read that could populate the cache."""
    global _installed
    if _installed:
        return
    _installed = True
    try:
        from mpynode._common.lifecycle.callbacks import (
            CALLBACK_MANAGER, OWNER_SHARED,
        )

        def _on_change(*_args):
            invalidate()

        for event_name in ("Undo", "Redo"):
            try:
                cb_id = om.MEventMessage.addEventCallback(event_name, _on_change)
                CALLBACK_MANAGER.register(
                    cb_id, om.MMessage.removeCallback, OWNER_SHARED
                )
            except Exception:
                pass

        for event_name in ("kBeforeNew", "kBeforeOpen", "kAfterImport"):
            evt = getattr(om.MSceneMessage, event_name, None)
            if evt is None:
                continue
            try:
                cb_id = om.MSceneMessage.addCallback(evt, _on_change)
                CALLBACK_MANAGER.register(
                    cb_id, om.MMessage.removeCallback, OWNER_SHARED
                )
            except Exception:
                pass
    except Exception:
        pass


def reset_install_state() -> None:
    """Clear the install guard so a plug-in reload re-subscribes. Called by the
    last-plugin-out teardown AFTER the shared callbacks are deregistered."""
    global _installed
    _installed = False
    invalidate()


def _has_attr(fn, name) -> bool:
    # api1 ``MFnDependencyNode.attribute()`` RAISES on a missing name rather
    # than returning a null MObject, so the try/except is the real test.
    try:
        return not fn.attribute(name).isNull()
    except Exception:
        return False


def _entry_for(node_mobject):
    """The live cache entry for this node, rebuilt if stale or recycled."""
    try:
        handle = om.MObjectHandle(node_mobject)
        key    = handle.hashCode()
    except Exception:
        return None
    entry = _CACHE.get(key)
    if (entry is not None and entry.gen == _GENERATION
            and entry.handle.isValid()
            and entry.handle.hashCode() == key):
        return entry
    try:
        fn = om.MFnDependencyNode(node_mobject)
    except Exception:
        return None
    # Cold path only -- a new entry is the first thing that can go stale, so
    # this is the earliest point the invalidation callbacks are needed.
    install_once()
    entry       = _Entry(_GENERATION, handle, _has_attr(fn, _INPUT_MAP_ATTR))
    _CACHE[key] = entry
    return entry


def _load_managed(node_mobject, entry) -> set:
    """Decode both attr maps into one name set. Lazy: only ever called once a
    DYNAMIC attribute has been seen on this node."""
    if entry.managed is not None:
        return entry.managed
    names: set = set()
    try:
        from mpynode._common.io import serialization

        fn = om.MFnDependencyNode(node_mobject)
        for attr_name in (_INPUT_MAP_ATTR, _OUTPUT_MAP_ATTR):
            if not _has_attr(fn, attr_name):
                continue
            try:
                raw = fn.findPlug(attr_name, True).asString()
            except Exception:
                continue
            if not raw:
                continue
            try:
                names.update(serialization.decode_attr_map(raw) or {})
            except Exception:
                continue
    except Exception:
        pass
    entry.managed = names
    return names


def _managed_via_parent(attr_mobject, managed) -> bool:
    """A compound's CHILDREN are created by the framework alongside the parent
    but only the parent is recorded, so ``self.myVecX`` has to resolve through
    ``myVec``. Walks the whole chain -- nested compounds are legal.

    This is not a back door. A user cannot smuggle a child into a managed
    compound: a compound's child count is fixed when it is created, and Maya
    rejects ``addAttr -parent`` on an existing one with "Too many children on
    this compound". So the children reachable this way are exactly the ones
    the framework created alongside the parent. A compound the user creates
    WHOLESALE is denied normally -- its children's chain leads to a parent
    that is itself absent from the map.

    api1 ``MFnAttribute.parent()`` RAISES ``RuntimeError`` at the top of the
    chain instead of returning a null MObject, so the except IS the loop's
    terminating condition."""
    try:
        attr = om.MFnAttribute(attr_mobject)
    except Exception:
        return False
    seen = 0
    while seen < 8:                      # depth guard; real chains are 1 deep
        seen += 1
        try:
            parent = attr.parent()
        except Exception:
            return False                 # no parent -- top of the chain
        if parent is None or parent.isNull():
            return False
        try:
            pfn = om.MFnAttribute(parent)
            if pfn.name() in managed or pfn.shortName() in managed:
                return True
        except Exception:
            return False
        attr = pfn
    return False


def is_managed(node_mobject, attr_mobject, name: str) -> bool:
    """True if ``attr_mobject`` on ``node_mobject`` may surface as ``name``.

    ``attr_mobject`` must already be resolved -- the caller has done the name
    lookup, so the test is on the ATTRIBUTE, not on the spelling. Long names,
    short names and compound children therefore all behave identically.
    """
    entry = _entry_for(node_mobject)
    if entry is None:
        return True                      # cannot reason about it -- fail open
    if not entry.is_mpynode:
        return True                      # not ours to police

    cached = entry.verdicts.get(name)
    if cached is not None:
        return cached

    verdict = True
    try:
        attr = om.MFnAttribute(attr_mobject)
        if attr.isDynamic():
            managed = _load_managed(node_mobject, entry)
            verdict = (attr.name() in managed or attr.shortName() in managed
                       or name in managed
                       or _managed_via_parent(attr_mobject, managed))
    except Exception:
        verdict = True                   # fail open rather than break a node

    entry.verdicts[name] = verdict
    return verdict


def _map_is_loaded(node_mobject) -> bool:
    """Test hook: did anything force the attr-map decode for this node yet?"""
    entry = _entry_for(node_mobject)
    return entry is not None and entry.managed is not None
