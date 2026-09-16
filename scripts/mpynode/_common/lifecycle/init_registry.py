"""Init_registry — per-node Init namespace registry.

Each JIT-capable mPy node carries an optional ``_initSource`` string
attribute. Its content is exec'd ONCE into a fresh per-node
namespace dict on:

 * file open (kAfterOpen) — for every node in the scene
 * ``wrapper.set_init_expression(source)`` — on edit/save

The bridge then injects that namespace into every expression eval
(via:func:`mpynode._common.compute.expression.exec_with_profile_watch`)
so the main expression can reference anything defined in init
directly — kernels, lookup tables, helper functions, cached data.

WHY THIS EXISTS
---------------
This is the node's "init phase" — module-level code that runs ONCE
per file lifecycle, populating reusable state the per-frame
expression can use. Beyond JIT kernels, examples:

 * Pre-loaded lookup tables / image data / config dicts
 * Helper functions (math primitives, geometric utilities)
 * @njit-compiled kernels (decorator pays its cost ONCE)
 * Imports from external modules (cached in sys.modules anyway,
 but cleaner to do them in init)

PERFORMANCE WHY
---------------
Path A (njit-inline-in-expression): ~0.61s/eval
Path D (init-defines-kernel, expr calls it): ~0.31s/eval
The decorator overhead pays its cost ONCE in init, not per call.

STRUCTURE
---------
This module owns the shared registry state (the two per-process dicts,
``InitProxy``, the UUID helpers, ``register_init_source`` + namespace
lookups, ``_INIT_TRACKED_NODE_TYPES``, and the wrapper-side
``InitSourceMixin``). The scene-message callbacks live in the sibling
``scene_callbacks``; pickle-trust prompting in ``trust_prompt``; the
Init-tab header generator in ``init_header``. Import those via the
``mpynode._common.lifecycle`` facade.
"""

from __future__ import annotations

import sys
from typing import Optional

import maya.OpenMaya as om


# Per-process dict: {node_uuid: namespace_dict}. UUID-keyed so two
# scenes whose deformers share auto-numbered names don't collide.
_NODE_INIT_NS: dict = {}


# Per-process dict: {node_uuid: bindings_dict}. Captures user attribute writes
# from Init code. Read by ``SelfProxy.__getattr__`` at compute time, as a tier
# between bridge-filled internals and the per-call user storage.
_INIT_BINDINGS: dict = {}


# ---- InitProxy — a ``self`` for the Init-time exec namespace ----


class InitProxy:
    """The ``self`` object provided to Init source code at exec time.

    Init has the SAME surface as Compute, just earlier + once:

    READS -- ``self.X`` resolves, in order, against:
      1. the live plug tree (``self.amplitude`` reads the plug, exactly
         like the Compute tab -- delegated to the shared ``PlugProxy``);
      2. the node's stored variables (persisted user data, including
         anything THIS Init run has written so far -- read-back works).

    WRITES -- ``self.X = value`` PERSISTS to the node's stored-var data
    (``_storedVarsData``), exactly like a ``self.X`` write in Compute:
    it saves with the .ma and repopulates on load. Writes are staged in
    memory during the Init run and flushed in a single write-back after
    the Init code finishes (mirrors Compute's one-plug-write-per-run).

    Two deliberate boundaries:

      * Writes are NOT routed to plugs. Init re-runs on every file-open
        (namespace rehydration) and on Save, so writing a plug here
        would clobber the freshly-loaded scene value each time. A write
        to a name that IS a plug is skipped with a warning -- use
        ``cmds.setAttr`` if you really mean to set a plug.
      * For SESSION-ONLY caches that should NOT be saved to the scene
        (a decoded image, a compiled lookup, anything heavy or
        unpicklable), use a PLAIN variable in the Init tab rather than
        ``self.X``::

            # session cache -- lives in the Init namespace, reachable
            # in Compute as a bare global, never written to the scene:
            lookup_image = cv2.imread('/rig/data/curve.png')

    Because Init can read stored vars, idempotent initialisation is
    easy::

        # ``self.values`` persists; set a default only once:
        if self.values is None:
            self.values = compute_expensive_default()
    """

    def __init__(self, node_uuid: str, node_name: str, plug_proxy=None):
        # object.__setattr__ throughout, so our own __setattr__ doesn't
        # intercept these bookkeeping writes.
        object.__setattr__(self, "_ip_node_uuid",  node_uuid)
        object.__setattr__(self, "_ip_node_name",  node_name)
        object.__setattr__(self, "_ip_plug_proxy", plug_proxy)
        # Legacy dict kept (empty) for the bridge fast-path; Init writes go to
        # stored vars now.
        _INIT_BINDINGS[node_uuid] = {}
        # Staging copy of the persisted stored vars: reads see it (so read-back
        # works), writes mutate it, the post-exec flush persists it.
        try:
            from mpynode._common.storedvars.stored_vars_api import get_variables

            storage = dict(get_variables(node_name) or {})
        except Exception:
            storage = {}
        object.__setattr__(self, "_ip_storage", storage)
        object.__setattr__(self, "_ip_dirty", False)

    def _ip_is_plug(self, name: str) -> bool:
        """True if ``name`` resolves to a plug on this node (so a write
        should be skipped rather than persisted as a shadow stored var)."""
        plug_proxy = object.__getattribute__(self, "_ip_plug_proxy")
        if plug_proxy is None:
            return False
        try:
            getattr(plug_proxy, name)
            return True
        except AttributeError:
            return False
        except Exception:
            return False

    def __setattr__(self, name: str, value):
        if name.startswith("_ip_"):
            object.__setattr__(self, name, value)
            return
        # Skip plug names: an Init re-run would clobber the freshly-loaded scene
        # value, and a stored var of that name is a dead shadow the plug beats.
        if self._ip_is_plug(name):
            node_name = object.__getattribute__(self, "_ip_node_name")
            sys.stderr.write(
                f"[init_registry] self.{name} is a plug on {node_name!r}; "
                f"Init does not write plugs (use cmds.setAttr if intended). "
                f"Skipped.\n"
            )
            return
        # Match Compute: a non-plug self.X write persists. Flushed after exec.
        object.__getattribute__(self, "_ip_storage")[name] = value
        object.__setattr__(self, "_ip_dirty", True)

    def __getattr__(self, name: str):
        # __getattribute__ handled _ip_*; we only see unresolved names.
        # Tier 1: live plug tree (parity with the Compute tab).
        plug_proxy = object.__getattribute__(self, "_ip_plug_proxy")
        if plug_proxy is not None:
            try:
                return getattr(plug_proxy, name)
            except AttributeError:
                pass
        # Tier 2: stored vars (loaded + anything Init wrote this run).
        storage = object.__getattribute__(self, "_ip_storage")
        if name in storage:
            return storage[name]
        node_name = object.__getattribute__(self, "_ip_node_name")
        raise AttributeError(
            f"'self' has no plug or stored var named {name!r} "
            f"(node {node_name!r}). "
            f"Stored vars: {sorted(storage.keys()) or '(none)'}"
        )

    def __delattr__(self, name: str):
        if name.startswith("_ip_"):
            object.__delattr__(self, name)
            return
        storage = object.__getattribute__(self, "_ip_storage")
        if name in storage:
            del storage[name]
            object.__setattr__(self, "_ip_dirty", True)
            return
        raise AttributeError(f"'self' has no stored var {name!r} to delete.")

    def _ip_flush_storage(self) -> None:
        """Persist the staged stored vars to ``_storedVarsData`` in one
        write (only when something was written/deleted). Mirrors
        Compute's single write-back. Best-effort: a non-picklable value
        is logged + skipped rather than crashing Init."""
        if not object.__getattribute__(self, "_ip_dirty"):
            return
        node_name = object.__getattribute__(self, "_ip_node_name")
        storage   = object.__getattribute__(self, "_ip_storage")
        try:
            from mpynode._common.storedvars import stored_var_store

            stored_var_store.set_data(node_name, storage)
        except Exception as exc:
            sys.stderr.write(
                f"[init_registry] failed to persist Init stored vars on "
                f"{node_name!r}: {type(exc).__name__}: {exc}\n"
            )

    def __repr__(self) -> str:
        storage = _INIT_BINDINGS.get(self._ip_node_uuid, {})
        keys    = sorted(object.__getattribute__(self, "_ip_storage").keys())
        return f"<InitProxy node={self._ip_node_name!r} stored={keys}>"


def get_init_bindings_for_mobject(mobject) -> Optional[dict]:
    """Bridge fast-path: return the per-node init bindings dict
    (set by InitProxy writes during init) for the given MObject, or
    None if no init bindings exist. Called from:func:`expression.exec_with_profile_watch` on every eval."""
    node_uuid = _node_uuid_from_mobject(mobject)
    if node_uuid is None:
        return None
    bindings = _INIT_BINDINGS.get(node_uuid)
    if bindings is None or not bindings:
        return None
    return bindings


# ---- UUID helpers ----


def _node_uuid_from_name(node_name: str) -> Optional[str]:
    """Return a session-local identity string for ``node_name``, or None.

    Uses ``MObjectHandle.hashCode()`` (resolves name -> MObject via
    ``MSelectionList`` first) instead of ``cmds.ls(uuid=True)`` so the
    identity scheme is consistent with the mobject-based lookup path
    (see ``_node_uuid_from_mobject``). The hashCode is a memory-handle
    identity stable for the lifetime of the MObject -- not the Maya
    ``.uuid`` attribute. We only need session-local identity because
    the registry rebuilds itself on every scene change via the
    scene-change callbacks.
    """
    try:
        import maya.api.OpenMaya as _om2

        sel = _om2.MSelectionList()
        sel.add(node_name)
        mobj = sel.getDependNode(0)
        return _node_uuid_from_mobject(mobj)
    except Exception:
        pass
    try:
        sel = om.MSelectionList()
        sel.add(node_name)
        mobj = om.MObject()
        sel.getDependNode(0, mobj)
        return _node_uuid_from_mobject(mobj)
    except Exception:
        return None


def _node_uuid_from_mobject(mobject) -> Optional[str]:
    """Return a session-local identity string for an MObject, or None.

    Uses ``MObjectHandle.hashCode()`` rather than
    ``MFnDependencyNode.uuid()`` because the latter requires DG
    access and is NOT documented thread-safe -- calling it from a
    Hypershade swatch worker thread (or VP2 render thread) can crash
    Maya. ``MObjectHandle.hashCode()`` is a memory-handle hash and
    has no DG dependency, so it's safe to call from any thread.

    The returned string is a session-local identity (not the Maya
    ``.uuid`` attribute). The init-namespace registry only needs
    session-local identity because it's rebuilt from scratch on
    every scene change via the scene-change callbacks.

    Handles BOTH api1 (``maya.OpenMaya.MObject``) and api2
    (``maya.api.OpenMaya.MObject``) so api2 ``MPxNode`` subclasses
    like mPyFile / mPyLocator / mPyConstraint that pass
    ``self.thisMObject()`` through ``exec_with_profile_watch`` get
    their per-node init namespace merged correctly. ``hashCode()``
    is documented to return the SAME value for two MObjects that
    point at the same Maya entity regardless of which API created
    them, so a node registered via the api1 path can be looked up
    via the api2 path and vice versa.
    """
    try:
        return str(om.MObjectHandle(mobject).hashCode())
    except Exception:
        pass
    try:
        import maya.api.OpenMaya as _om2

        return str(_om2.MObjectHandle(mobject).hashCode())
    except Exception:
        return None


# ---- Per-node namespace registry ----


def _hide_init_source_attr(node_name: str) -> bool:
    """Ensure the node's ``_initSource`` attr carries the *hidden* flag so
    it stays out of the Channel Box / Attribute Editor / Node Editor, just
    like the static ``_computeSource`` plug.

    Created with ``cmds.addAttr`` (which defaults to *visible*), so legacy
    nodes — and any created before this fix — show it. Setting the flag via
    the API is authoritative regardless of how the attr was made.
    """
    try:
        from maya import cmds

        if not cmds.attributeQuery("_initSource", node=node_name, exists=True):
            return False
        sel = om.MSelectionList()
        sel.add(node_name)
        mobj = om.MObject()
        sel.getDependNode(0, mobj)
        fn   = om.MFnDependencyNode(mobj)
        attr = fn.attribute("_initSource")
        if attr.isNull():
            return False
        a_fn = om.MFnAttribute(attr)
        if not a_fn.isHidden():
            a_fn.setHidden(True)
        return True
    except Exception:
        return False


def _exec_trusted() -> bool:
    """True if node Python read out of the scene may be exec'd.

    Reads the SAME per-scene flag the pickle decode path reads
    (``trust.pickle_trusted()``), resolved ONCE on the main thread at
    open/import by ``trust_prompt._resolve_pickle_trust`` -- which prompts in
    the GUI and never prompts (fails closed) in batch.

    ``MPYNODE_TRUST_PICKLE=1`` is the existing headless / render-farm opt-in
    and is checked FIRST, because the per-scene flag is forced False for the
    WHOLE kBeforeOpen -> kAfterOpen transition and the mid-open lazy bind
    (:func:`ensure_init_namespace_for_mobject`) runs inside that window.

    Fails CLOSED if the flag can't be read -- same posture as
    ``trust_prompt._is_batch`` / ``_scene_has_pickle_blobs``.

    Thin delegate to :func:`trust.exec_trusted`, which is the ONE predicate the
    Compute gate (``compute.expression.exec_with_profile_watch``) reads too --
    the two exec paths must never drift apart.
    """
    try:
        from mpynode._common.io import trust

        return trust.exec_trusted()
    except Exception:
        return False


def register_init_source(
    node_name: str, source: str, trusted: Optional[bool] = None
) -> bool:
    """Compile + exec ``source`` into a fresh namespace dict, keyed
    by the node's UUID.

    Provides ``self`` (an:class:`InitProxy`) in the exec namespace so
    user code can write ``self.X = value`` to bind values into the
    per-node init bindings dict (later read at compute time via
    ``SelfProxy``).

    ``trusted`` defaults to the per-scene trust flag (:func:`_exec_trusted`);
    callers whose source did NOT come out of the scene file -- the authoring
    setter :meth:`InitSourceMixin.set_init_expression` -- pass an explicit
    ``True``. Mirrors ``serialization._decode_keyed2(raw, trusted=None)``.

    Returns True on success, False on compile/exec error OR on a refused
    (untrusted) scene. Errors are logged to stderr; the registry entry is
    cleared on failure so the bridge falls back to running the expression as
    if no init source was set.
    """
    node_uuid = _node_uuid_from_name(node_name)
    if node_uuid is None:
        sys.stderr.write(
            f"[init_registry] cannot register init_source: node "
            f"{node_name!r} not found\n"
        )
        return False
    # Keep _initSource hidden (parity with _computeSource) on every
    # registration path, covering nodes made before the addAttr(hidden=True).
    _hide_init_source_attr(node_name)
    if not source or not source.strip():
        _NODE_INIT_NS.pop(node_uuid, None)
        _INIT_BINDINGS.pop(node_uuid, None)
        return True
    # Trust gate BEFORE any state is built: an untrusted scene must not be
    # able to exec its own Python, and a refusal must leave the node with no
    # namespace, no bindings and no stored-var write-back (not half-init'd).
    if not (_exec_trusted() if trusted is None else bool(trusted)):
        _NODE_INIT_NS.pop(node_uuid, None)
        _INIT_BINDINGS.pop(node_uuid, None)
        sys.stderr.write(
            f"[init_registry] {node_name!r}: Init code NOT run -- this scene "
            f"is not trusted. Re-open the file and click Trust, or set "
            f"MPYNODE_TRUST_PICKLE=1 (headless).\n"
        )
        return False
    import builtins as _builtins

    # InitProxy replaces this on construction, but wipe here too so partial
    # bindings from a failed previous run can't leak through.
    _INIT_BINDINGS[node_uuid] = {}

    # ONE PlugProxy shared by ``self`` (so ``self.X`` reads plugs, parity with
    # Compute) and ``node`` (so ``node.X.Y.Z`` navigation still works).
    plug_proxy = None
    try:
        from mpynode._common.plugs.plug_proxy import PlugProxy
        import maya.OpenMaya as _om

        sel = _om.MSelectionList()
        sel.add(node_name)
        node_mobject = _om.MObject()
        sel.getDependNode(0, node_mobject)
        plug_proxy = PlugProxy(node_mobject)
    except Exception:
        plug_proxy = None

    ns: dict = {
        "__builtins__": _builtins,
        "__name__":     f"<init:{node_name}>",
        "self":         InitProxy(node_uuid, node_name, plug_proxy),
    }
    if plug_proxy is not None:
        ns["node"] = plug_proxy
    try:
        code_obj = compile(source, f"<init:{node_name}>", "exec")
        exec(code_obj, ns)
    except Exception as exc:
        import traceback

        tb = traceback.format_exc()
        sys.stderr.write(
            f"[init_registry] init_source compile/exec failed for "
            f"{node_name!r}: {type(exc).__name__}: {exc}\n"
        )
        # Also surface in the Node Designer Log panel, like the compute path.
        try:
            from mpynode._common.util.log_bus import log as _log_bus

            _log_bus(
                f"[init] {node_name}: {type(exc).__name__}: {exc}\n{tb}",
                level="error",
            )
        except Exception:
            pass
        _NODE_INIT_NS.pop(node_uuid, None)
        _INIT_BINDINGS.pop(node_uuid, None)
        return False
    # One write-back for the Init code's self.X = ... writes, like Compute.
    init_self = ns.get("self")
    if init_self is not None:
        try:
            init_self._ip_flush_storage()
        except Exception as exc:
            sys.stderr.write(
                f"[init_registry] stored-var flush failed for "
                f"{node_name!r}: {type(exc).__name__}: {exc}\n"
            )
    _NODE_INIT_NS[node_uuid] = ns
    return True


def clear_init_expression(node_name: str) -> None:
    """Drop the init namespace + bindings for ``node_name`` (if any)."""
    node_uuid = _node_uuid_from_name(node_name)
    if node_uuid is not None:
        _NODE_INIT_NS.pop(node_uuid, None)
        _INIT_BINDINGS.pop(node_uuid, None)


def get_init_namespace_for_mobject(mobject) -> Optional[dict]:
    """Bridge fast-path: return the per-node init namespace dict for
    the given MObject, or None if none registered. Called from:func:`expression.exec_with_profile_watch` on every eval."""
    node_uuid = _node_uuid_from_mobject(mobject)
    if node_uuid is None:
        return None
    return _NODE_INIT_NS.get(node_uuid)


def ensure_init_namespace_for_mobject(mobject) -> Optional[dict]:
    """Like :func:`get_init_namespace_for_mobject`, but lazy-loads the
    namespace from the node's ``_initSource`` plug if it hasn't been
    registered yet.

    Covers a narrow but important window: during ``mc.file(open=True)``
    Maya may evaluate a node's ``compute()`` BEFORE the
    ``kAfterOpen`` callback fires (which is what normally walks every
    node and registers its init source). Without this lazy path, the
    first compute on a freshly-opened scene sees an empty namespace
    and any expression referencing names defined in Init (e.g. ``np``
    or ``build_default_output``) raises ``NameError``. Subsequent
    computes work because the ``kAfterOpen`` sweep eventually catches
    up, but the user sees a noisy one-shot error.

    The lazy bind only runs on the main thread (the ``cmds`` /
    ``MFnDependencyNode`` lookups are not documented thread-safe);
    on worker threads we degrade to the original behavior (return
    None) and rely on the main-thread sweep to populate the cache.
    """
    ns = get_init_namespace_for_mobject(mobject)
    if ns is not None:
        return ns
    # Lazy-bind uses cmds + MFn calls that aren't safe on EM worker threads.
    import threading as _thr
    if _thr.current_thread() is not _thr.main_thread():
        return None
    # api2 first, api1 fallback -- mirrors _node_uuid_from_mobject.
    name: Optional[str] = None
    try:
        import maya.api.OpenMaya as _om2
        # Prefer the UNIQUE full DAG path: a duplicated shape can share a short
        # name with the original, and the cmds calls below would then raise
        # "More than one object matches name" -- so the duplicate never gets an
        # Init namespace and its expression NameErrors on any Init global.
        if mobject.hasFn(_om2.MFn.kDagNode):
            name = (
                _om2.MFnDagNode(mobject).fullPathName()
                or _om2.MFnDependencyNode(mobject).name()
            )
        else:
            name = _om2.MFnDependencyNode(mobject).name()
    except Exception:
        try:
            name = om.MFnDependencyNode(mobject).name()
        except Exception:
            return None
    if not name:
        return None
    try:
        from maya import cmds
        if not cmds.attributeQuery("_initSource", node=name, exists=True):
            return None
        src = cmds.getAttr(f"{name}._initSource") or ""
    except Exception:
        return None
    if not src.strip():
        return None
    if register_init_source(name, src):
        return get_init_namespace_for_mobject(mobject)
    return None


def has_init_expression(node_name: str) -> bool:
    """True if a non-empty init namespace is registered."""
    node_uuid = _node_uuid_from_name(node_name)
    return (
        node_uuid is not None
        and node_uuid in _NODE_INIT_NS
        and bool(_NODE_INIT_NS[node_uuid])
    )


def clear_all_init_ns() -> None:
    """Drop all per-node init namespaces + bindings. Called on
    scene change."""
    _NODE_INIT_NS.clear()
    _INIT_BINDINGS.clear()


def init_ns_count() -> int:
    """Number of init namespaces currently registered."""
    return len(_NODE_INIT_NS)


# ---- Tracked node types ----


# Node types that may carry an ``_initSource`` attribute. Every type in
# REGISTRY mixes in InitSourceMixin, so the Init tab shows for all of them.
_INIT_TRACKED_NODE_TYPES = (
    "mPyNode",
    "mPyLocator",
    "mPyConstraint",
    "mPyIkSolver",
    "mPyDeformer",
    "mPySkinCluster",
    "mPyBlendShape",
    "mPyTransform",
    "mPyMesh",
    "mPyNurbsCurve",
    "mPyNurbsSurface",
    "mPyFile",
)


# ---- Wrapper-side mixin ----


class InitSourceMixin:
    """Adds ``set_init_expression`` / ``get_init_expression`` / ``clear_init_expression``
    / ``has_init_expression`` to any wrapper with a ``self._name`` attribute.
    """

    def set_init_expression(self, source: str) -> bool:
        """Persist + register the per-node Init source string.

        Stored on the node as a ``_initSource`` string attribute so
        it persists across.ma save/load.

        ``source`` is supplied in-process by the caller (Init tab editor,
        demo/template builder, tests) rather than read back out of the scene
        file, so this path passes ``trusted=True`` -- the scene-load paths
        (``scene_callbacks._register_init_sources_for_tracked`` and
        :func:`ensure_init_namespace_for_mobject`) are the ones the per-scene
        trust flag gates.

        Returns True if source compiled + exec'd successfully,
        False on any error (logged to stderr).
        """
        from maya import cmds

        full = f"{self._name}._initSource"
        if not cmds.attributeQuery(
            "_initSource", node=self._name, exists=True
        ):
            cmds.addAttr(
                self._name, longName="_initSource", dataType="string",
                hidden=True,
            )
        else:
            _hide_init_source_attr(self._name)
        cmds.setAttr(full, source or "", type="string")
        return register_init_source(self._name, source or "", trusted=True)

    def get_init_expression(self) -> str:
        """Return the node's current ``_initSource`` attribute value
        (empty string if not set). Backward-compat: also returns the
        legacy ``_jitSource`` attribute if present and ``_initSource``
        isn't."""
        from maya import cmds

        if cmds.attributeQuery(
            "_initSource", node=self._name, exists=True
        ):
            try:
                return cmds.getAttr(f"{self._name}._initSource") or ""
            except Exception:
                return ""
        if cmds.attributeQuery("_jitSource", node=self._name, exists=True):
            try:
                return cmds.getAttr(f"{self._name}._jitSource") or ""
            except Exception:
                return ""
        return ""

    def clear_init_expression(self) -> None:
        """Wipe the per-node Init source attribute + namespace."""
        from maya import cmds

        clear_init_expression(self._name)
        if cmds.attributeQuery(
            "_initSource", node=self._name, exists=True
        ):
            try:
                cmds.setAttr(
                    f"{self._name}._initSource", "", type="string"
                )
            except Exception:
                pass

    def has_init_expression(self) -> bool:
        """True if a non-empty init namespace is currently registered
        for this node."""
        return has_init_expression(self._name)
