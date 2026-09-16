"""``SelfProxy`` -- the ``self`` accessor inside user
expressions, backed by the live plug tree.

History:
 * original ``SelfProxy`` schema-based proxy.
 * ``PlugSelfProxy`` introduced as a parallel, plug-tree
 backed proxy for the deformer family.
 * legacy schema-based ``SelfProxy`` deleted; the
 plug-tree ``PlugSelfProxy`` is renamed to ``SelfProxy`` and is
 the only class shipping in mpynode.

Tier order (read):
 1. compute_locals (pre-populated keys) -- bridge-supplied scratch
 slots like ``local_matrix`` / ``points`` / ``forces``.
 2. plug tree -- the live MFnDependencyNode plugs.
 3. init bindings -- the Init-tab namespace.
 4. user storage -- decoded from ``_storedVarsData``.

``output_scratch_keys`` is an opt-in subset of the compute_locals names
that are WRITE-ONLY output buffers (e.g. the mPyLocator draw buffers
``text`` / ``lines`` / ``points`` / ``polygons`` / ``shapes``). For those
names a real plug WINS on read -- so a user-added input/output of the same
name (``self.text`` reading a ``text`` string input) is readable instead of
being shadowed by the scratch slot -- while WRITES still land in the scratch
slot (so ``self.text = {...}`` feeds the draw buffer / harvest). Nodes that
need compute_locals to win on read unconditionally (mPyFile reads inputs
WITHOUT a plug touch on the Hypershade swatch / Arnold worker thread, where
plug reads are unsafe) simply do NOT pass this set.

Tier order (write):
 1. compute_locals (only if pre-populated or marked writable).
 2. plug tree (if a matching plug exists).
 3. user storage (catch-all).

Bookkeeping fields all live in ``__dict__`` under the ``_psp_`` prefix
(retained for symmetry with the original implementation; no public
contract on the prefix). Users should not name their own storage
entries ``_psp_*``.
"""

from __future__ import annotations

from typing import Any


def _values_equal(a, b):
    """Best-effort equality check that handles numpy arrays + plain
    Python objects without raising on broadcasting mismatches.

    A change of TYPE between ndarray and non-ndarray counts as NOT equal,
    even when the numeric contents match -- otherwise re-assigning a stored
    var as ``self.x = np.array(self.x)`` (list -> ndarray) is silently
    dropped (np.array_equal(list, ndarray) is True) and the var keeps its
    old list type."""
    try:
        import numpy as _np

        a_arr = isinstance(a, _np.ndarray)
        b_arr = isinstance(b, _np.ndarray)
        if a_arr != b_arr:
            return False  # list <-> ndarray: treat as a real change
        if a_arr and b_arr:
            if a.dtype != b.dtype:
                return False
            try:
                return bool(_np.array_equal(a, b))
            except Exception:
                return False
    except Exception:
        pass
    try:
        return bool(a == b)
    except Exception:
        return False


def _ensure_api1_mobject(mobject):
    """Fix: convert any api2 ``maya.api.OpenMaya.MObject``
    to an api1 ``maya.OpenMaya.MObject`` so downstream PlugProxy
    (which uses api1 ``MFnDependencyNode``) sees dynamic attrs
    added via ``cmds.addAttr``.

    If ``mobject`` is already an api1 MObject (the common case for
    api1 wrappers like mPyDeformer / mPyTransform / mPyConstraint
    / mPyField / mPyEmitter / mPyIkSolver / mPyObjectSet), return
    it unchanged. The detection is by isinstance against the api1
    MObject class.

    If the bridge resolve fails for any reason (node deleted,
    Maya transient state, etc.), return the input unchanged --
    callers will fall through to the existing "no plug" path
    which already has user-facing error messaging."""
    try:
        import maya.OpenMaya as _om1

        if isinstance(mobject, _om1.MObject):
            return mobject
    except Exception:
        return mobject
    # Not api1 -- try the api2 -> name -> api1 bridge. SKIP off the main thread
    # (Hypershade swatch worker, VP2 render thread): MFnDependencyNode and
    # MSelectionList are not documented thread-safe and can crash Maya. The
    # bridge only matters for ``cmds.addAttr`` dynamic attrs, so skipping it
    # has no visible effect on the default sources.
    import threading as _thr
    if _thr.current_thread() is not _thr.main_thread():
        return mobject
    try:
        import maya.api.OpenMaya as _om2

        # DAG nodes can share a short name (duplicating a transform leaves two
        # "asTestShape" under different parents). A bare ``name()`` is then
        # ambiguous, ``MSelectionList.add()`` raises "More than one object
        # matches name", and the bridge silently hands back the api2 MObject --
        # whose dynamic plugs api1 PlugProxy can't see, giving a spurious
        # "'self' has no plug named X" for every user input on the duplicate.
        # Resolve DAG nodes by their UNIQUE full path instead.
        if mobject.hasFn(_om2.MFn.kDagNode):
            name = (
                _om2.MFnDagNode(mobject).fullPathName()
                or _om2.MFnDependencyNode(mobject).name()
            )
        else:
            name = _om2.MFnDependencyNode(mobject).name()
    except Exception:
        return mobject
    try:
        import maya.OpenMaya as _om1

        sel = _om1.MSelectionList()
        sel.add(name)
        out = _om1.MObject()
        sel.getDependNode(0, out)
        if out.isNull():
            return mobject
        return out
    except Exception:
        return mobject


def _blessed_methods_for_mobject(mobject, type_name=None):
    """{name: MethodSpec} of blessed methods for the node's type, else {}.
    Best-effort: any failure yields {} (no blessed methods).

    ``type_name`` (the REGISTERED name, e.g. "mPyFile" -- a wrapper's
    ``NODE_NAME``, not its class name) skips the MFn lookup entirely. Off the
    main thread :func:`_ensure_api1_mobject` deliberately hands back an api2
    MObject, and api1 ``MFnDependencyNode`` REJECTS one with a TypeError, so the
    lookup below silently yields {} and EVERY blessed method disappears
    mid-compute -- surfacing as "'self' has no plug ... named 'write_texture'".
    """
    if type_name is None:
        try:
            import maya.OpenMaya as _om1
            type_name = _om1.MFnDependencyNode(mobject).typeName()
        except Exception:
            return {}
    try:
        from mpynode._common.interface.method_registry import methods_for_type
        specs = methods_for_type(type_name)
    except Exception:
        return {}
    return {m.name: m for m in (specs or ())}


def _blessed_properties_for_mobject(mobject, type_name=None):
    """{name: PropertySpec} of blessed properties for the node's type, else {}.
    Best-effort, same contract as :func:`_blessed_methods_for_mobject` --
    including the api2/worker-thread hole ``type_name`` closes."""
    if type_name is None:
        try:
            import maya.OpenMaya as _om1
            type_name = _om1.MFnDependencyNode(mobject).typeName()
        except Exception:
            return {}
    try:
        from mpynode._common.interface.method_registry import properties_for_type
        specs = properties_for_type(type_name)
    except Exception:
        return {}
    return {p.name: p for p in (specs or ())}


class SelfProxy(object):
    """``self`` -- delegates to a ``PlugProxy`` for the plug
    tree, with compute_locals + init-bindings + user-storage fallback
    tiers underneath.

    Constructed by ``run_generic_compute`` and per-node ``_run_expression``
    methods, once per compute call. ``output_handles`` is a dict
    ``{(plug_name, multi_index): MFn*Handle}`` populated by the bridge
    eager-allocation step and read by the
    PlugListProxy when the user does ``self.outputGeometry[i]``.
    """

    def __init__(
        self,
        mobject,
        datablock           = None,
        geom_iter           = None,
        compute_ctx         = None,
        init_bindings       = None,
        user_storage        = None,
        output_handles      = None,
        node_type_label     = "this node",
        compute_locals      = None,
        output_scratch_keys = None,
        node_type_name      = None,
    ):
        from mpynode._common.plugs.plug_proxy import PlugProxy

        if compute_ctx is None:
            compute_ctx = {}
        if output_handles is not None:
            compute_ctx.setdefault("output_handles", output_handles)
        else:
            compute_ctx.setdefault("output_handles", {})

        # PlugProxy walks with api1 MFnDependencyNode. Handed an api2 MObject
        # (``self.thisMObject()`` from an api2 MPxNode) it crashes or returns
        # null for DYNAMIC attrs -- static attrs work because Maya's type
        # registration bridges both APIs, but ``cmds.addAttr`` attrs only land
        # in the api1 dynamic-attr slot when api1 owns the resolve.
        #
        # Symptom: user adds an "offset" input, the expression reads
        # ``self.offset``, and SelfProxy raises "no plug, init binding, or
        # stored var named 'offset'" while ``cmds.getAttr`` returns the value.
        #
        # So re-resolve by name through api1 ``MSelectionList``. Same pattern as
        # ``MPyConstraint._cached_api1_mobject``.
        mobject = _ensure_api1_mobject(mobject)

        object.__setattr__(self, "_psp_mobject",       mobject)
        object.__setattr__(self, "_psp_datablock",     datablock)
        object.__setattr__(self, "_psp_geom_iter",     geom_iter)
        object.__setattr__(self, "_psp_compute_ctx",   compute_ctx)
        object.__setattr__(self, "_psp_init_bindings", init_bindings or {})
        object.__setattr__(self, "_psp_user_storage",  dict(user_storage or {}))
        object.__setattr__(
            self, "_psp_user_storage_snapshot", dict(user_storage or {})
        )
        object.__setattr__(
            self, "_psp_output_handles", compute_ctx["output_handles"]
        )
        object.__setattr__(self, "_psp_node_type_label", str(node_type_label))
        object.__setattr__(self, "_psp_compute_locals", dict(compute_locals or {}))
        object.__setattr__(
            self, "_psp_compute_local_keys", set((compute_locals or {}).keys())
        )
        object.__setattr__(
            self, "_psp_output_scratch_keys", set(output_scratch_keys or ())
        )

        plug_proxy = PlugProxy(
            mobject,
            datablock   = datablock,
            geom_iter   = geom_iter,
            compute_ctx = compute_ctx,
        )
        object.__setattr__(self, "_psp_plug_proxy", plug_proxy)
        object.__setattr__(self, "_psp_exec_namespace", {})
        object.__setattr__(
            self, "_psp_blessed_methods",
            _blessed_methods_for_mobject(mobject, node_type_name))
        object.__setattr__(
            self, "_psp_blessed_properties",
            _blessed_properties_for_mobject(mobject, node_type_name))

    # ---- Read tiers ----

    def __getattr__(self, name):
        if name.startswith("_psp_"):
            raise AttributeError(name)

        # Tier 0: blessed API methods (self.read_texture(...)). Safe to win on
        # read because validate(), run at file_method_interface import, forbids a
        # method name from equalling a plug name.
        try:
            blessed = object.__getattribute__(self, "_psp_blessed_methods")
        except AttributeError:
            blessed = {}
        if name in blessed:
            import importlib
            spec = blessed[name]
            mod_path, fn_name = spec.runtime.split(":")
            fn    = getattr(importlib.import_module(mod_path), fn_name)
            _self = self

            def _bound(*args, **kwargs):
                return fn(_self, *args, **kwargs)

            return _bound

        # Tier 0.5: blessed API PROPERTIES (self.morphs) -- the value-returning
        # sibling of Tier 0, above the plug tree. validate_properties() forbids a
        # property name equalling a plug or method, so it can't shadow either.
        try:
            props = object.__getattribute__(self, "_psp_blessed_properties")
        except AttributeError:
            props = {}
        if name in props:
            import importlib
            pspec = props[name]
            mod_path, fn_name = pspec.runtime.split(":")
            return getattr(importlib.import_module(mod_path), fn_name)(self)

        # Tier 1: compute_locals shadow plugs -- EXCEPT write-only output-scratch
        # slots, where a real plug wins (Tier 2) so a same-named user attr stays
        # readable. With no backing plug, Tier 2.5 returns the scratch value.
        try:
            local_keys  = object.__getattribute__(self, "_psp_compute_local_keys")
            locals_dict = object.__getattribute__(self, "_psp_compute_locals")
        except AttributeError:
            local_keys, locals_dict = set(), {}
        try:
            scratch_keys = object.__getattribute__(
                self, "_psp_output_scratch_keys"
            )
        except AttributeError:
            scratch_keys = set()
        if name in local_keys and name not in scratch_keys:
            return locals_dict[name]

        # Tier 2: plug tree.
        try:
            plug_proxy = object.__getattribute__(self, "_psp_plug_proxy")
        except AttributeError:
            plug_proxy = None
        if plug_proxy is not None:
            try:
                return getattr(plug_proxy, name)
            except AttributeError:
                pass

        # Tier 2.5: dynamic compute_locals fallback (also serves output-scratch
        # slots whose name has no backing plug -> return the scratch value).
        if name in locals_dict:
            return locals_dict[name]

        # Tier 3: init bindings.
        try:
            bindings = object.__getattribute__(self, "_psp_init_bindings")
        except AttributeError:
            bindings = {}
        if name in bindings:
            return bindings[name]

        # Tier 4: user storage.
        try:
            storage = object.__getattribute__(self, "_psp_user_storage")
        except AttributeError:
            storage = {}
        if name in storage:
            return storage[name]

        raise AttributeError(
            "'self' has no plug, init binding, or stored var named "
            "{!r}. Init bindings: {}; user storage: {}".format(
                name,
                sorted(bindings.keys()) or "(none)",
                sorted(storage.keys()) or "(none)",
            )
        )

    # ---- Write routing ----

    def __setattr__(self, name, value):
        if name.startswith("_psp_"):
            object.__setattr__(self, name, value)
            return

        try:
            local_keys  = object.__getattribute__(self, "_psp_compute_local_keys")
            locals_dict = object.__getattribute__(self, "_psp_compute_locals")
        except AttributeError:
            local_keys, locals_dict = set(), {}
        if name in local_keys:
            locals_dict[name] = value
            return

        try:
            plug_proxy = object.__getattribute__(self, "_psp_plug_proxy")
        except AttributeError:
            plug_proxy = None

        if plug_proxy is not None:
            mobject = object.__getattribute__(self, "_psp_mobject")
            from mpynode._common.plugs import plug_governance
            from mpynode._common.plugs.plug_proxy import _attr_mobject_for_name

            # Must respect governance: an UNMANAGED plug taking this branch would
            # let the raise below escape instead of falling through to user
            # storage the way an unknown name does.
            attr_mobject = _attr_mobject_for_name(mobject, name)
            if attr_mobject is not None and plug_governance.is_managed(
                mobject, attr_mobject, name
            ):
                try:
                    setattr(plug_proxy, name, value)
                    return
                except (NotImplementedError, AttributeError):
                    raise

        storage       = object.__getattribute__(self, "_psp_user_storage")
        storage[name] = value

    def __delattr__(self, name):
        """Allow ``del self.X`` to drop a user-storage key. Mirrors
        the legacy semantics so existing user expressions that
        ``del self.cached_thing`` continue to work; the next
        ``diff_storage()`` reports the deletion."""
        if name.startswith("_psp_"):
            object.__delattr__(self, name)
            return
        storage = object.__getattribute__(self, "_psp_user_storage")
        if name in storage:
            del storage[name]
            return
        raise AttributeError(
            "cannot delete {!r}: not a user storage entry".format(name)
        )

    # ---- Bridge helpers ----

    def diff_storage(self):
        """Return user-storage entries that changed since construction.

        adds + modifications + deletions, with deleted keys surfaced as
        ``None`` so the bridge can drop them from the plug.
        """
        current  = self._psp_user_storage
        snapshot = self._psp_user_storage_snapshot
        out      = {}
        for key, value in current.items():
            if key not in snapshot:
                out[key] = value
                continue
            old = snapshot[key]
            if not _values_equal(old, value):
                out[key] = value
        for key in snapshot:
            if key not in current:
                out[key] = None
        return out

    def get_user_storage(self):
        """Return the live user-storage dict (for inspection / serialization)."""
        return self._psp_user_storage

    def get_output_handles(self):
        """Return the output-handles dict ``{(plug_name, idx): handle}``."""
        return self._psp_output_handles

    def get_compute_locals(self):
        """Return a snapshot dict of the per-compute scratch slots."""
        return dict(self._psp_compute_locals)

    def get_plug_proxy(self):
        """Return the underlying ``PlugProxy`` (for post-exec output
        harvest that writes through the plug tree)."""
        return self._psp_plug_proxy

    def get_init_helper(self, name):
        """Return an Init-tab helper function by name from the exec namespace
        (populated by exec_with_profile_watch before exec). Raises a clear
        AttributeError if unavailable -- blessed methods require the node's
        shipped Init helpers."""
        ns = object.__getattribute__(self, "_psp_exec_namespace")
        fn = ns.get(name)
        if fn is None:
            raise AttributeError(
                "blessed method needs Init helper %r but it is not available "
                "in this node's Init namespace" % name)
        return fn

    def mark_compute_local_writable(self, name):
        """Register ``name`` as a writable compute_locals slot."""
        keys = object.__getattribute__(self, "_psp_compute_local_keys")
        keys.add(str(name))

    def __repr__(self):
        try:
            import maya.OpenMaya as om

            name = om.MFnDependencyNode(self._psp_mobject).name()
        except Exception:
            name = "<unknown>"
        return "<SelfProxy node={!r}>".format(name)
