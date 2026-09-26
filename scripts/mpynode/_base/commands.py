"""Base command class + dispatch helper for undoable mpynode operations.

Adapted from an earlier mpynode/_base/commands.py. Each user-write op
(add attr, delete attr, rename, set expression, set stored var,...)
gets a small ``_BaseCommand`` subclass with ``doIt`` / ``undoIt`` /
``redoIt`` methods. Dispatching via ``run_undoable(cmd)`` registers
the operation as a single Maya undo chunk.

The ``runUndoableAPICommand`` command ships inside the ``mpynode_api2``
Maya plug-in (folded in from the former standalone ``undoable_api_command``
plug-in); ``run_undoable`` loads ``mpynode_api2`` on demand.
"""

from __future__ import annotations

from typing import Any

from maya import cmds
from mpynode._base.plugins import load_plugin


class _BaseCommand:
    """Subclass me, implement doIt / undoIt / (optional) redoIt."""

    def doIt(self) -> Any:
        raise NotImplementedError(f"{type(self).__name__}.doIt() not implemented")

    def undoIt(self) -> Any:
        raise NotImplementedError(f"{type(self).__name__}.undoIt() not implemented")

    def redoIt(self) -> Any:
        # default = redo is identical to do
        return self.doIt()


def run_undoable(cmd: _BaseCommand) -> Any:
    """Dispatch a ``_BaseCommand`` through Maya's undoable API command wrapper.

    Returns whatever cmd.doIt() returned.

    Note: Maya's MPxCommand.setResult wraps single scalar results in a list when
    accessed from Python. We unwrap single-element lists so callers receive the
    same value the underlying doIt() returned.
    """
    with load_plugin("mpynode_api2"):
        result = cmds.runUndoableAPICommand(cmd)
    if isinstance(result, list) and len(result) == 1:
        return result[0]
    return result


# ---------------------------------------------------------------------------
# Concrete commands shipped
# ---------------------------------------------------------------------------


def _seed_setup_source(node_name: str, native_type: str) -> None:
    """Seed the per-type setup source onto ``node_name``'s ``_methodsSource``.

    Reuses ``MPyNode._populate_methods_source`` so the merge logic is IDENTICAL
    to the auto-setup path: it appends the type-default setup ONLY if the node
    has no setup yet (merge-not-replace) and no-ops for types without an authored
    setup source (mPyNode etc. get nothing). Non-fatal -- a seed failure logs to
    stderr and never breaks node creation.
    """
    try:
        from mpynode._node_registry import wrap_node

        w = wrap_node(node_name, native_type)
        if w is not None:
            type(w)._populate_methods_source(w)
    except Exception as exc:  # never break creation
        import sys

        sys.stderr.write(
            "[commands] seed setup source for %r (%s) failed: %s\n"
            % (node_name, native_type, exc)
        )


def _seed_tier_header(wrapper, getter, setter, header_fn, native_type,
                      tier=None, treat_none_empty=False):
    """Seed ONE tier plug of ``wrapper`` iff that tier exists AND is currently
    empty.

    If the type ships a *tier starter* for ``tier`` (see
    :mod:`mpynode._defaults.starter_registry`) that runnable starter code is
    seeded; otherwise the generic ``header_fn(native_type)`` comment is used. So
    a registered type (mPyFile / mPySkinCluster) gets working default code on a
    Designer virgin-create while every other type keeps its header-only behavior.

    ``treat_none_empty`` handles the api1 ``_computeSource`` plug, whose default
    is the literal string ``"None"`` (a no-op expression) rather than "".

    Never overwrites populated content: a tier already carrying a setup source,
    a template payload, or any user text is left untouched. Per-tier ``try`` so a
    single tier failure never blocks the others."""
    if not (hasattr(wrapper, getter) and hasattr(wrapper, setter)):
        return
    try:
        current = getattr(wrapper, getter)() or ""
    except Exception:
        return
    is_empty = (not current) or (treat_none_empty and current.strip() == "None")
    if not is_empty:
        return
    # Prefer a per-type runnable starter; fall back to the generic header.
    text = None
    if tier is not None:
        try:
            from mpynode._defaults.starter_registry import starter_source

            text = starter_source(native_type, tier)
        except Exception:
            text = None
    if text is None:
        text = header_fn(native_type)
    try:
        getattr(wrapper, setter)(text)
    except Exception as exc:  # never break creation
        import sys

        sys.stderr.write(
            "[commands] seed header via %s for %r (%s) failed: %s\n"
            % (setter, wrapper, native_type, exc)
        )


def _seed_headers(node_name: str, native_type: str) -> None:
    """Seed each per-tier auto-header onto a freshly-created node's EMPTY tier
    plugs.

    This is the Node-Designer *virgin New* behavior (mode == "headers") ONLY: it
    is invoked from the create commands the Designer routes through, never from
    the wrapper API ``create()`` / ``build()`` nor the ``.mpn`` import path. So a
    node made via the API or imported from disk NEVER gets a header auto-inserted
    just because an expression was left blank -- exactly the requested scoping.

    Only empty tiers are seeded (see :func:`_seed_tier_header`), so a setup
    source already merged onto ``_methodsSource`` survives; the Methods header is
    only added when there is no setup source. Non-fatal throughout -- a failure
    logs to stderr and never breaks node creation."""
    try:
        from mpynode._node_registry import wrap_node
        from mpynode._common.lifecycle.compute_header import make_compute_header
        from mpynode._common.lifecycle import make_init_header
        from mpynode._common.lifecycle.viewport_registry import make_viewport_header
        from mpynode._common.osl.osl_registry import make_osl_header
        from mpynode._common.methods.methods_registry import make_methods_header

        w = wrap_node(node_name, native_type)
        if w is None:
            return
    except Exception as exc:  # never break creation
        import sys

        sys.stderr.write(
            "[commands] seed headers for %r (%s) failed: %s\n"
            % (node_name, native_type, exc)
        )
        return

    # Compute is present on every type (its plug defaults to the "None"
    # sentinel). Init is JIT types; Viewport / OSL are mPyFile only; Methods is
    # every type (but skipped when a setup source already filled it).
    _seed_tier_header(w, "get_compute_expression", "set_compute_expression",
                      make_compute_header, native_type, tier="compute",
                      treat_none_empty=True)
    _seed_tier_header(w, "get_init_expression", "set_init_expression",
                      make_init_header, native_type, tier="init")
    _seed_tier_header(w, "get_viewport_expression", "set_viewport_expression",
                      make_viewport_header, native_type, tier="viewport")
    _seed_tier_header(w, "get_osl_expression", "set_osl_expression",
                      make_osl_header, native_type, tier="osl")
    _seed_tier_header(w, "get_methods_source", "set_methods_source",
                      make_methods_header, native_type, tier="methods")


class _CreateNodeCommand(_BaseCommand):
    """Undoable wrapper for ``cmds.createNode`` with optional plugin pre-load.

    Implementation note: ``cmds.createNode`` is itself an undoable Maya command.
    It gets recorded inside the ``runUndoableAPICommand`` undo chunk. On
    ``cmds.undo()``, Maya's chunk-undo deletes the created node automatically;
    on ``cmds.redo()`` the same chunk re-runs ``cmds.createNode`` with the same
    arguments so the node comes back with its original name.

    Therefore ``undoIt`` and ``redoIt`` MUST be no-ops here: a naive
    ``cmds.delete(self.created_name)`` in ``undoIt`` would try to delete a
    node that Maya's chunk-undo already removed and crash Maya 2024.
    """

    def __init__(
        self,
        native_node_type: str,
        name:             str  | None = None,
        plugin_name:      str  | None = None,
        seed_setup:       bool        = False,
        skip_selection:   bool        = False,
        seed_headers:     bool        = False,
    ):
        self.native_node_type = native_node_type
        self.requested_name   = name
        self.plugin_name      = plugin_name
        # When True, merge the per-type setup source into the created node's
        # _methodsSource so the Methods tab shows it + "Run setup" works. Opt-in
        # so generic createNode callers are unaffected.
        self.seed_setup = seed_setup
        # When True, create the node without selecting it (skipSelect=True).
        self.skip_selection = skip_selection
        # When True, seed each empty tier plug with its auto-header (Node-Designer
        # virgin-create in "headers" mode). Opt-in so the API / .mpn paths -- which
        # never pass this -- leave blank expressions blank.
        self.seed_headers = seed_headers
        self.created_name: str | None = None

    def doIt(self) -> str | None:
        if self.plugin_name and not cmds.pluginInfo(
            self.plugin_name, q=True, loaded=True
        ):
            cmds.loadPlugin(self.plugin_name, quiet=True)
        kwargs = {"name": self.requested_name} if self.requested_name else {}
        if self.skip_selection:
            kwargs["skipSelect"] = True
        self.created_name = cmds.createNode(self.native_node_type, **kwargs)
        if self.seed_setup and self.created_name:
            _seed_setup_source(self.created_name, self.native_node_type)
        if self.seed_headers and self.created_name:
            # Runs AFTER seed_setup so a merged setup source keeps the Methods
            # tier non-empty (only empty tiers get a header).
            _seed_headers(self.created_name, self.native_node_type)
        return self.created_name

    def undoIt(self) -> None:
        # No-op: createNode already rode the undo chunk; deleting again crashes.
        pass

    def redoIt(self) -> None:
        # No-op: chunk-redo re-runs createNode with the original name argument.
        pass


class _DeleteNodeCommand(_BaseCommand):
    """Undoable wrapper for ``cmds.delete``. Stores the node name + a
    snapshot of its expression / attrs so undo can re-create it.

    For we just wrap ``cmds.delete`` (which IS undoable on its
    own inside the chunk \u2014 so doIt/undoIt are simple).
    """

    def __init__(self, name: str):
        self.name = name

    def doIt(self) -> None:
        cmds.delete(self.name)

    def undoIt(self) -> None:
        # cmds.delete is already in the chunk; chunk-undo restores the node.
        pass

    def redoIt(self) -> None:
        # Same: chunk-redo re-runs cmds.delete.
        pass


class _SetExpressionCommand(_BaseCommand):
    """Undoable wrapper for setting a node's Compute expression (the
    ``_computeSource`` plug)."""

    def __init__(self, py_node, new_text: str):
        self.py_node  = py_node
        self.new_text = new_text
        self._old_text: str | None = None

    def doIt(self) -> None:
        try:
            self._old_text = self.py_node.get_compute_expression()
        except Exception:
            self._old_text = ""
        self.py_node.set_compute_expression(self.new_text)

    def undoIt(self) -> None:
        if self._old_text is not None:
            self.py_node.set_compute_expression(self._old_text)

    def redoIt(self) -> None:
        self.py_node.set_compute_expression(self.new_text)


# ---------------------------------------------------------------------------
# attribute commands (add / delete / rename / connect / disconnect)
# ---------------------------------------------------------------------------


class _AddInputAttrCommand(_BaseCommand):
    """Undoable add-input-attr.

    Implementation note (matches _CreateNodeCommand): the underlying
    ``cmds.addAttr`` AND the JSON-map ``cmds.setAttr`` are both already
    undoable inside the chunk. So Maya's chunk-undo handles the rollback
    automatically; ``undoIt``/``redoIt`` MUST be no-ops to avoid
    double-execution crashes.
    """

    def __init__(
        self,
        py_node,
        attr_name:         str,
        attr_type:         str,
        is_array:          bool             = False,
        enum_names:        list[str] | None = None,
        auto_connect_time: bool             = True,
        min_value                           = None,
        max_value                           = None,
        default_value                       = None,
        sparse:            bool             = False,
    ):
        self.py_node           = py_node
        self.attr_name         = attr_name
        self.attr_type         = attr_type
        self.is_array          = is_array
        self.enum_names        = enum_names
        self.auto_connect_time = auto_connect_time
        self.min_value         = min_value
        self.max_value         = max_value
        self.default_value     = default_value
        self.sparse            = sparse

    def doIt(self) -> None:
        # Validate the node still exists before mutating: a stale wrapper (e.g.
        # after file-new, before the UI cleared panel state) would otherwise
        # bubble up a confusing AttributeError instead of the real cause.
        node_name = self.py_node.get_name()
        import maya.cmds as _mc

        if not _mc.objExists(node_name):
            raise RuntimeError(
                f"Cannot add input attr {self.attr_name!r}: node "
                f"{node_name!r} no longer exists in the scene. "
                "(The Designer's tab is stale \u2014 close it and re-select "
                "an existing node.)"
            )
        self.py_node.add_input_attr(
            self.attr_name,
            self.attr_type,
            self.is_array,
            enum_names        = self.enum_names,
            auto_connect_time = self.auto_connect_time,
            min_value         = self.min_value,
            max_value         = self.max_value,
            default_value     = self.default_value,
            sparse            = self.sparse,
        )

    def undoIt(self) -> None:
        # No-op: cmds.addAttr is in the chunk; chunk-undo removes it.
        pass

    def redoIt(self) -> None:
        # No-op: chunk-redo re-runs cmds.addAttr.
        pass


class _AddOutputAttrCommand(_BaseCommand):
    """Same pattern as _AddInputAttrCommand."""

    def __init__(
        self,
        py_node,
        attr_name:    str,
        attr_type:    str,
        is_array:     bool             = False,
        enum_names:   list[str] | None = None,
        min_value                      = None,
        max_value                      = None,
        default_value                  = None,
    ):
        self.py_node       = py_node
        self.attr_name     = attr_name
        self.attr_type     = attr_type
        self.is_array      = is_array
        self.enum_names    = enum_names
        self.min_value     = min_value
        self.max_value     = max_value
        self.default_value = default_value

    def doIt(self) -> None:
        # validate node still exists.
        node_name = self.py_node.get_name()
        import maya.cmds as _mc

        if not _mc.objExists(node_name):
            raise RuntimeError(
                f"Cannot add output attr {self.attr_name!r}: node "
                f"{node_name!r} no longer exists in the scene. "
                "(The Designer's tab is stale \u2014 close it and re-select "
                "an existing node.)"
            )
        self.py_node.add_output_attr(
            self.attr_name,
            self.attr_type,
            self.is_array,
            enum_names    = self.enum_names,
            min_value     = self.min_value,
            max_value     = self.max_value,
            default_value = self.default_value,
        )

    def undoIt(self) -> None:
        pass

    def redoIt(self) -> None:
        pass


class _DeleteAttrCommand(_BaseCommand):
    """Undoable delete-attr (input or output).

    Same pattern: cmds.deleteAttr is in the chunk; chunk-undo restores
    the attr automatically. undoIt/redoIt are no-ops.
    """

    def __init__(self, py_node, attr_name: str, direction: str):
        if direction not in ("input", "output"):
            raise ValueError(
                f"direction must be 'input' or 'output', got {direction!r}"
            )
        self.py_node   = py_node
        self.attr_name = attr_name
        self.direction = direction

    def doIt(self) -> None:
        if self.direction == "input":
            self.py_node.delete_input_attr(self.attr_name)
        else:
            self.py_node.delete_output_attr(self.attr_name)

    def undoIt(self) -> None:
        pass

    def redoIt(self) -> None:
        pass


# nodeState values: 0 = Normal, 1 = HasNoEffect, 2 = Blocking.
def _eval_block_state(node_name: str) -> int:
    """Return the nodeState value that suspends ``node_name``'s
    evaluation during an attribute rename.

    Deformer-family nodes (anything inheriting ``geometryFilter`` --
    mPyDeformer / mPySkinCluster / mPyBlendShape)
    reject Blocking (2): Maya prints
    "Blocked is not supported on deformers. Switching to Has No Effect"
    and silently falls back to HasNoEffect (1). We pick HasNoEffect
    directly for those to avoid the warning -- it suspends the deform
    just the same. Every other node type uses Blocking (2).
    """
    try:
        inherited = cmds.nodeType(node_name, inherited=True) or []
    except Exception:
        return 2
    if "geometryFilter" in inherited:
        return 1  # HasNoEffect
    return 2  # Blocking


def _timeline_is_playing() -> bool:
    """True while Maya's timeline is playing back.

    A plug-level reorder deletes and re-adds attrs; doing that mid-playback --
    with the node's compute firing every frame -- risks evaluating a node whose
    attrs momentarily don't exist. So reorder is refused while this is True
    (the user chose 'only when the timeline is idle')."""
    try:
        return bool(cmds.play(query=True, state=True))
    except Exception:
        return False


def _run_without_undo(fn):
    """Run ``fn`` with Maya's undo recording suspended, then restore the prior
    state. Used by reorder so its destructive deleteAttr/addAttr churn does NOT
    land on the undo queue -- the command reverses it explicitly in undoIt
    (Maya's native deleteAttr-undo restores attrs at the END of the list, which
    would scramble the order, so chunk auto-undo is the wrong tool here)."""
    try:
        state = cmds.undoInfo(query=True, state=True)
    except Exception:
        state = False
    if state:
        cmds.undoInfo(stateWithoutFlush=False)
    try:
        return fn()
    finally:
        if state:
            cmds.undoInfo(stateWithoutFlush=True)


class _RenameAttrCommand(_BaseCommand):
    """Undoable rename. cmds.renameAttr is in the chunk; chunk-undo
    restores the original name. undoIt/redoIt are no-ops."""

    def __init__(self, py_node, old_name: str, new_name: str, direction: str):
        if direction not in ("input", "output"):
            raise ValueError(
                f"direction must be 'input' or 'output', got {direction!r}"
            )
        self.py_node   = py_node
        self.old_name  = old_name
        self.new_name  = new_name
        self.direction = direction

    def doIt(self) -> None:
        # Block this node's evaluation across the critical section. The DG
        # rename and the source rewrite are two steps; in between, the attribute
        # is renamed but the stored expression still references the OLD name, so
        # a compute firing in that window raises AttributeError for the missing
        # attr. Suspending evaluation (Blocking, or HasNoEffect for deformers --
        # see _eval_block_state) makes Maya skip it until we restore the prior
        # state, by which point the expression has been rewritten.
        node_name  = self.py_node.get_name()
        prev_state = None
        try:
            prev_state = cmds.getAttr(node_name + ".nodeState")
            cmds.setAttr(node_name + ".nodeState", _eval_block_state(node_name))
        except Exception:
            prev_state = None
        try:
            if self.direction == "input":
                self.py_node.rename_input_attr(self.old_name, self.new_name)
            else:
                self.py_node.rename_output_attr(self.old_name, self.new_name)
            # Rewrite every ``self.<old>`` reference in the STORED expression
            # sources. Runs inside the same undo chunk as the DG rename, so undo
            # restores both the attribute name and the source text.
            self._rewrite_expression_sources()
        finally:
            if prev_state is not None:
                try:
                    cmds.setAttr(node_name + ".nodeState", prev_state)
                except Exception:
                    pass

    def _rewrite_expression_sources(self) -> None:
        try:
            from mpynode._common.util import refactor
        except Exception:
            return
        node  = self.py_node
        pairs = []
        for getter, setter in (
            ("get_compute_expression", "set_compute_expression"),
            ("get_init_expression", "set_init_expression"),
            ("get_viewport_expression", "set_viewport_expression"),
        ):
            g = getattr(node, getter, None)
            s = getattr(node, setter, None)
            if callable(g) and callable(s):
                pairs.append((g, s))
        for getter, setter in pairs:
            try:
                source = getter() or ""
            except Exception:
                continue
            if not source:
                continue
            plan = refactor.plan_rename_self_attr(
                source, self.old_name, self.new_name
            )
            if plan.ok and plan.count > 0:
                try:
                    setter(plan.new_source)
                except Exception:
                    pass

    def undoIt(self) -> None:
        pass

    def redoIt(self) -> None:
        pass


class _ReorderAttrCommand(_BaseCommand):
    """Undoable plug-level reorder of a node's user INPUT or OUTPUT attrs.

    Reordering is destructive (deleteAttr + re-addAttr); the wrapper engine
    (``reorder_input_attrs`` / ``reorder_output_attrs``) snapshots and restores
    values + connections. Unlike the other commands here, the destructive churn
    is run with undo recording SUSPENDED (:func:`_run_without_undo`) and undo is
    handled EXPLICITLY -- ``undoIt`` re-applies the original order, ``redoIt``
    re-applies the new order. (Maya's native deleteAttr-undo restores attrs at
    the END of the list, so relying on chunk auto-undo would scramble the order
    a single Ctrl+Z is supposed to restore.) The node's evaluation is suspended
    across each rebuild (Blocking, or HasNoEffect for deformers -- the map is
    briefly empty between delete and re-add, so a stray compute would see no user
    attrs). REFUSED while the timeline is playing (see
    :func:`_timeline_is_playing`); the UI gates on this too for a clean message.
    """

    def __init__(self, py_node, new_order, direction: str):
        if direction not in ("input", "output"):
            raise ValueError(
                f"direction must be 'input' or 'output', got {direction!r}"
            )
        self.py_node          = py_node
        self.new_order        = list(new_order)
        self.direction        = direction
        self.refused_playback = False
        self._original_order: list | None = None

    def _current_order(self) -> list:
        if self.direction == "input":
            return list((self.py_node.get_input_attr_map() or {}).keys())
        return list((self.py_node.get_output_attr_map() or {}).keys())

    def _apply_order(self, order) -> None:
        node_name = self.py_node.get_name()

        def work():
            prev_state = None
            try:
                prev_state = cmds.getAttr(node_name + ".nodeState")
                cmds.setAttr(node_name + ".nodeState", _eval_block_state(node_name))
            except Exception:
                prev_state = None
            try:
                if self.direction == "input":
                    self.py_node.reorder_input_attrs(order)
                else:
                    self.py_node.reorder_output_attrs(order)
            finally:
                if prev_state is not None:
                    try:
                        cmds.setAttr(node_name + ".nodeState", prev_state)
                    except Exception:
                        pass

        _run_without_undo(work)

    def doIt(self) -> None:
        if _timeline_is_playing():
            self.refused_playback = True
            try:
                cmds.warning(
                    "Reorder attributes is disabled during playback -- stop the "
                    "timeline and try again."
                )
            except Exception:
                pass
            return
        # Capture the order to revert to BEFORE mutating.
        self._original_order = self._current_order()
        self._apply_order(self.new_order)

    def undoIt(self) -> None:
        if self.refused_playback or self._original_order is None:
            return
        self._apply_order(self._original_order)

    def redoIt(self) -> None:
        if self.refused_playback or self._original_order is None:
            return
        self._apply_order(self.new_order)


class _ConnectAttrCommand(_BaseCommand):
    """Undoable wrapper for cmds.connectAttr (which is itself undoable
    inside the chunk \u2014 so undoIt/redoIt are no-ops)."""

    def __init__(self, src_plug: str, dst_plug: str, force: bool = True):
        self.src_plug = src_plug
        self.dst_plug = dst_plug
        self.force    = force

    def doIt(self) -> None:
        cmds.connectAttr(self.src_plug, self.dst_plug, force=self.force)

    def undoIt(self) -> None:
        # cmds.connectAttr is in the chunk; chunk-undo handles the disconnect.
        pass

    def redoIt(self) -> None:
        # Same: chunk-redo re-runs cmds.connectAttr.
        pass


class _ClobberMultiConnectCommand(_BaseCommand):
    """Undoable 'clobber' connect for a MULTI mPy attr.

    Removes every existing element of ``multi_attr_plug`` (breaking any
    connections) so the array is resized to exactly the new selection, then
    wires ``pairs`` (already allocated from index 0). Maya does NOT shrink a
    multi attr when you merely disconnect its elements -- the logical indices
    linger until save/reload -- so ``removeMultiInstance`` is what actually
    frees them. Both the ``removeMultiInstance`` and ``connectAttr`` calls ride
    the undo chunk (same contract as :class:`_DisconnectAllCommand` /
    :class:`_ConnectAttrCommand`), so ``undoIt``/``redoIt`` are no-ops: a single
    Ctrl+Z restores the prior elements and their connections.
    """

    def __init__(self, multi_attr_plug: str, pairs):
        self.multi_attr_plug = multi_attr_plug
        self.pairs           = list(pairs)

    def doIt(self) -> None:
        try:
            idx = cmds.getAttr(self.multi_attr_plug, multiIndices=True) or []
        except Exception:
            idx = []
        for i in idx:
            try:
                cmds.removeMultiInstance(
                    "%s[%d]" % (self.multi_attr_plug, i), b=True
                )
            except Exception:
                pass
        for src, dst in self.pairs:
            cmds.connectAttr(src, dst, force=True)

    def undoIt(self) -> None:
        # removeMultiInstance + connectAttr are in the chunk.
        pass

    def redoIt(self) -> None:
        pass


class _DisconnectAllCommand(_BaseCommand):
    """Disconnect every connection to/from a plug. Inputs are sources;
    outputs are destinations."""

    def __init__(self, plug: str, direction: str):
        if direction not in ("input", "output"):
            raise ValueError(
                f"direction must be 'input' or 'output', got {direction!r}"
            )
        self.plug      = plug
        self.direction = direction

    def doIt(self) -> None:
        # The ``connections=True`` form returns a flat [thisPlug, otherPlug,
        # ...] list, giving us the actual plug ON THIS node -- for a MULTI
        # (array) attr that's the ELEMENT plug (``out[260]``), not the bare
        # parent. Disconnecting via the parent silently fails for multis ("no
        # connection ... to disconnect"), which is why "Disconnect All" was a
        # no-op on array attrs. For a scalar the element plug IS the parent.
        if self.direction == "input":
            # Disconnect anything DRIVING this input: src -> thisElem.
            pairs = (
                cmds.listConnections(
                    self.plug,
                    source      = True,
                    destination = False,
                    plugs       = True,
                    connections = True,
                )
                or []
            )
            for i in range(0, len(pairs) - 1, 2):
                this_plug, src = pairs[i], pairs[i + 1]
                try:
                    cmds.disconnectAttr(src, this_plug)
                except Exception:
                    pass
        else:
            # Disconnect anything this output is DRIVING: thisElem -> dst.
            pairs = (
                cmds.listConnections(
                    self.plug,
                    source      = False,
                    destination = True,
                    plugs       = True,
                    connections = True,
                )
                or []
            )
            for i in range(0, len(pairs) - 1, 2):
                this_plug, dst = pairs[i], pairs[i + 1]
                try:
                    cmds.disconnectAttr(this_plug, dst)
                except Exception:
                    pass

    def undoIt(self) -> None:
        # cmds.disconnectAttr is in the chunk.
        pass

    def redoIt(self) -> None:
        # Same.
        pass


class _CreateGeoForPlugCommand(_BaseCommand):
    """Create the geometry shape a mesh / NURBS plug wants, and wire it.

    The same convenience a ``time`` input gets when it offers to plug in
    ``time1``: a geometry plug is useless until something is on the other end
    of it, and building that by hand is four steps in the Outliner
    (create, find the shape, find the right world plug, connect).

    Which node depends on the DIRECTION, because the two ends need different
    things:

    * an INPUT wants something to read, so it gets a primitive with actual
      geometry in it (an empty shape would connect and feed nothing) wired
      ``<shape>.worldMesh[0]`` / ``.worldSpace[0]`` -> plug;
    * an OUTPUT wants somewhere to land, so it gets an EMPTY shape under a
      transform, wired plug -> ``<shape>.inMesh`` / ``.create``, which is
      exactly what each node type's own setup builds for its render shape. A
      mesh also joins ``initialShadingGroup``, or it draws as an invisible
      surface until the user works out why.

    An array plug takes the next free element rather than the bare parent,
    which Maya rejects for a multi.

    ``undoIt`` / ``redoIt`` are no-ops on purpose: every call here
    (``polyCube``, ``createNode``, ``connectAttr``, ``sets``) is itself
    undoable and rides the ``run_undoable`` chunk, so one Ctrl+Z takes the
    whole thing back (same contract as :class:`_CreateNodeCommand`).
    """

    #: attr type -> (shape type, the shape's OUTPUT plug, its INPUT plug)
    GEO_TYPES = {
        "mesh":         ("mesh",         "worldMesh[0]",  "inMesh"),
        "nurbsCurve":   ("nurbsCurve",   "worldSpace[0]", "create"),
        "nurbsSurface": ("nurbsSurface", "worldSpace[0]", "create"),
    }
    #: what an INPUT gets, so the plug reads real geometry from the start.
    PRIMITIVES = {
        "mesh":         ("polyCube",  {}),
        "nurbsCurve":   ("circle",    {"constructionHistory": True}),
        "nurbsSurface": ("nurbsPlane", {"constructionHistory": True}),
    }

    def __init__(self, node_name: str, attr_name: str, attr_type: str,
                 direction: str, is_array: bool = False):
        if attr_type not in self.GEO_TYPES:
            raise ValueError(
                "attr_type must be one of %s, got %r"
                % (sorted(self.GEO_TYPES), attr_type))
        if direction not in ("input", "output"):
            raise ValueError(
                "direction must be 'input' or 'output', got %r" % (direction,))
        self.node_name = node_name
        self.attr_name = attr_name
        self.attr_type = attr_type
        self.direction = direction
        self.is_array  = bool(is_array)
        #: the transform created, for the caller to select / report.
        self.created_name: str | None = None

    # -- plugs ---------------------------------------------------------

    def _node_plug(self) -> str:
        """This node's side of the connection, indexed when it is a multi."""
        plug = "%s.%s" % (self.node_name, self.attr_name)
        if not self.is_array:
            return plug
        used = cmds.getAttr(plug, multiIndices=True) or []
        return "%s[%d]" % (plug, (max(used) + 1) if used else 0)

    # -- build ---------------------------------------------------------

    def _make_source(self) -> str:
        """A primitive to drive an input. Returns its shape."""
        ctor, kwargs = self.PRIMITIVES[self.attr_type]
        made = getattr(cmds, ctor)(name="%sSource" % self.attr_name, **kwargs)
        xform = made[0] if isinstance(made, (list, tuple)) else made
        self.created_name = xform
        shapes = cmds.listRelatives(xform, shapes=True, fullPath=False) or []
        if not shapes:
            raise RuntimeError("%s created no shape" % ctor)
        return shapes[0]

    def _make_destination(self) -> str:
        """An empty shape to receive an output. Returns it."""
        shape_type = self.GEO_TYPES[self.attr_type][0]
        # <attr>Render / <attr>RenderShape, the names each geometry node type's
        # own setup gives the shape it builds for its output.
        xform = cmds.createNode("transform", name="%sRender" % self.attr_name)
        self.created_name = xform
        shape = cmds.createNode(shape_type, name="%sRenderShape" % self.attr_name,
                                parent=xform)
        if self.attr_type == "mesh":
            # Without a shading group the mesh is in the scene but invisible.
            try:
                cmds.sets(shape, edit=True, forceElement="initialShadingGroup")
            except Exception:
                pass
        return shape

    def doIt(self) -> str | None:
        node_plug = self._node_plug()
        if self.direction == "input":
            shape = self._make_source()
            src   = "%s.%s" % (shape, self.GEO_TYPES[self.attr_type][1])
            cmds.connectAttr(src, node_plug, force=True)
        else:
            shape = self._make_destination()
            dst   = "%s.%s" % (shape, self.GEO_TYPES[self.attr_type][2])
            cmds.connectAttr(node_plug, dst, force=True)
        return self.created_name

    def undoIt(self) -> None:
        # No-op: every call above rode the undo chunk (see the class docstring).
        pass

    def redoIt(self) -> None:
        # Same.
        pass


class _SetSparseCommand(_BaseCommand):
    """Undoable toggle of a user ARRAY INPUT attr's ``sparse`` read flag.

    ``sparse`` is OUR metadata (lives in the ``_inputAttrs`` JSON), not a Maya
    attribute, so toggling it is a pure metadata edit -- the Maya plug,
    connections, and element values are untouched (NO delete+recreate). The
    ``mc.setAttr`` that persists the map rides Maya's undo chunk, so
    ``undoIt``/``redoIt`` are no-ops (same contract as ``_SetAttrColorCommand``).

    INPUTS ONLY: the flag selects how the expression READS the array (dense
    gap-filled when False, compact connected-only when True); it is meaningless
    for outputs.
    """

    def __init__(self, py_node, attr_name: str, value: bool):
        self.py_node   = py_node
        self.attr_name = attr_name
        self.value     = bool(value)

    def doIt(self) -> None:
        node      = self.py_node
        node_name = node.get_name()
        if not cmds.objExists(node_name):
            raise RuntimeError(
                f"Cannot set sparse on {self.attr_name!r}: node "
                f"{node_name!r} no longer exists in the scene."
            )
        meta = (node.get_input_attr_map() or {}).get(self.attr_name)
        if meta is None:
            raise RuntimeError(
                f"{self.attr_name!r} is not a user-added input attr."
            )
        if not meta.get("is_array"):
            raise RuntimeError("sparse applies to array attrs only.")
        node.set_input_attr_sparse(self.attr_name, self.value)

    def undoIt(self) -> None:
        # The map setAttr rode the undo chunk; chunk-undo reverts it.
        pass

    def redoIt(self) -> None:
        pass


# ---------------------------------------------------------------------------
# stored-var commands (add / remove / set / rename)
#
# The ``_storedVarNames`` write rides the Maya undo chunk automatically (it's a
# plain ``cmds.setAttr``). The variable VALUES live in the in-memory deferred
# cache (``stored_var_store``), which is not a Maya command and is invisible to
# the chunk -- so each command snapshots the node's stored-var dict around its
# mutation and restores it in undoIt / redoIt.
# ---------------------------------------------------------------------------


class _StoredVarCommand(_BaseCommand):
    """Common before/after stored-var snapshot + restore plumbing."""

    py_node = None
    _before = None
    _after  = None

    def _capture_before(self) -> None:
        from mpynode._common.storedvars import stored_var_store

        self._before = stored_var_store.get_data(self.py_node.get_name())

    def _capture_after(self) -> None:
        from mpynode._common.storedvars import stored_var_store

        self._after = stored_var_store.get_data(self.py_node.get_name())

    def undoIt(self) -> None:
        if self._before is not None:
            from mpynode._common.storedvars import stored_var_store

            stored_var_store.set_data(self.py_node.get_name(), self._before)

    def redoIt(self) -> None:
        if self._after is not None:
            from mpynode._common.storedvars import stored_var_store

            stored_var_store.set_data(self.py_node.get_name(), self._after)


class _AddStoredVarCommand(_StoredVarCommand):
    def __init__(self, py_node, var_name: str, initial_value=None):
        self.py_node       = py_node
        self.var_name      = var_name
        self.initial_value = initial_value

    def doIt(self) -> None:
        self._capture_before()
        self.py_node.add_variable(self.var_name, self.initial_value)
        self._capture_after()


class _AddTemporaryVarCommand(_StoredVarCommand):
    """Add a SESSION-only (Temporary) stored var: written to the in-memory
    store but NOT registered in ``_storedVarNames`` (so it isn't saved).
    Undo/redo restore the cache via the base snapshot mechanism."""

    def __init__(self, py_node, var_name: str, initial_value=None):
        self.py_node       = py_node
        self.var_name      = var_name
        self.initial_value = initial_value

    def doIt(self) -> None:
        self._capture_before()
        from mpynode._common.storedvars import stored_var_store, stored_vars_api

        # Bypasses stored_vars_api, so the reserved-name check has to be made
        # here too.
        stored_vars_api.guard_var_name(self.py_node.get_name(), self.var_name)
        stored_var_store.set_var(
            self.py_node.get_name(), self.var_name, self.initial_value
        )
        self._capture_after()


class _RemoveStoredVarCommand(_StoredVarCommand):
    def __init__(self, py_node, var_name: str):
        self.py_node  = py_node
        self.var_name = var_name

    def doIt(self) -> None:
        self._capture_before()
        self.py_node.remove_variable(self.var_name)
        self._capture_after()


class _SetStoredVarCommand(_StoredVarCommand):
    """Set a stored var's value. ``persistent`` controls ``_storedVarNames``
    membership and defaults to ``None`` = leave it alone, matching
    ``set_variable``: an inline value edit on a Temporary row used to PROMOTE
    it to Persistent. Callers that mean to change the status pass True/False."""

    def __init__(self, py_node, var_name: str, new_value,
                 persistent: bool | None = None):
        self.py_node    = py_node
        self.var_name   = var_name
        self.new_value  = new_value
        self.persistent = None if persistent is None else bool(persistent)

    def doIt(self) -> None:
        self._capture_before()
        self.py_node.set_variable(self.var_name, self.new_value, self.persistent)
        self._capture_after()


class _RenameStoredVarCommand(_StoredVarCommand):
    def __init__(self, py_node, old_name: str, new_name: str):
        self.py_node  = py_node
        self.old_name = old_name
        self.new_name = new_name

    def doIt(self) -> None:
        self._capture_before()
        self.py_node.rename_variable(self.old_name, self.new_name)
        self._capture_after()


class _SetPersistentCommand(_BaseCommand):
    """Toggle a stored var's scene-persistence (its ``_storedVarNames``
    membership). This is a pure names-plug edit and the var's VALUE in
    the store is untouched, so the change rides Maya's undo chunk and
    undoIt / redoIt are no-ops."""

    def __init__(self, py_node, var_name: str, persistent: bool):
        self.py_node    = py_node
        self.var_name   = var_name
        self.persistent = bool(persistent)

    def doIt(self) -> None:
        from mpynode._common.storedvars.stored_vars_api import set_variable_persistent

        set_variable_persistent(self.py_node.get_name(), self.var_name, self.persistent)

    def undoIt(self) -> None:
        pass

    def redoIt(self) -> None:
        pass


# ---------------------------------------------------------------------------
# per-attr UI color command (Maya owns the chunk; no-op undo)
# ---------------------------------------------------------------------------


class _SetAttrColorCommand(_BaseCommand):
    def __init__(self, py_node, attr_name: str, hex_color, direction: str):
        if direction not in ("input", "output"):
            raise ValueError(
                f"direction must be 'input' or 'output', got {direction!r}"
            )
        self.py_node   = py_node
        self.attr_name = attr_name
        self.hex_color = hex_color  # str or None (None = clear)
        self.direction = direction

    def doIt(self) -> None:
        if self.direction == "input":
            self.py_node.set_input_attr_color(self.attr_name, self.hex_color)
        else:
            self.py_node.set_output_attr_color(self.attr_name, self.hex_color)

    def undoIt(self) -> None:
        pass

    def redoIt(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Import.mpn (undoable wrapper around deserialize_node)
# ---------------------------------------------------------------------------


class _ImportNodeCommand(_BaseCommand):
    """Undoable.mpn import. Constructs the node via cmds.createNode +
    addAttr inside the chunk, so chunk-undo cleans everything up if
    user hits Ctrl+Z. doIt/redoIt are no-ops because the chunk is the
    source of truth.
    """

    def __init__(self, payload: dict, name: str | None = None,
                 restore_persistent: bool = True,
                 seed_setup: bool = False):
        self.payload = payload
        self.name    = name
        # When False the imported node carries only its DEFINITIONS (no baked
        # persistent stored-var data). Default True keeps the legacy import.
        self._restore_persistent = restore_persistent
        # When True, seed the per-type setup source onto the imported node's
        # _methodsSource (merge-not-replace). Opt-in so general .mpn import
        # (default False) does NOT inject a setup the payload didn't carry.
        self.seed_setup = seed_setup
        self.created_name: str | None = None
        # Per-tier restore failures, surfaced so the import dialog can show what
        # didn't round-trip: a setter exception, a False-returning setter (text
        # persisted but didn't validate), or a missing setter. Always a dict.
        self.tier_failures: dict = {}

    def doIt(self) -> None:
        from mpynode._common.io.mpn_io import deserialize_node

        # A template/.mpn may carry a preferred node name (the dnet template asks
        # for "mPyDnet"); honor it only when the caller gave none. With neither,
        # deserialize_node falls back to the template's source_name
        # (gameOfLifeMesh1), not the generic base type, so every create path
        # names alike.
        node_name = self.name or self.payload.get("preferred_name")
        py_node, self.tier_failures = deserialize_node(
            self.payload, name=node_name, return_failures=True,
            restore_persistent=self._restore_persistent,
        )
        try:
            self.created_name = py_node.get_name()
        except Exception:
            self.created_name = None
        if self.seed_setup and self.created_name:
            # Derive the native type from the payload (preferred) or the wrapped
            # node's NATIVE_TYPE.
            native_type = self.payload.get("native_type")
            if not native_type:
                native_type = getattr(type(py_node), "NATIVE_TYPE", None)
            if native_type:
                _seed_setup_source(self.created_name, native_type)

    def undoIt(self) -> None:
        # createNode / addAttr / setAttr all rode the chunk; chunk-undo reverts.
        pass

    def redoIt(self) -> None:
        # Same.
        pass


# ---------------------------------------------------------------------------
# New-node command selection (template-aware)
# ---------------------------------------------------------------------------


def build_new_node_command(native_type: str, mode: str = "headers"):
    """Return the undoable command for creating ``native_type``.

    ``mode`` is the ``new_node_mode`` preference value (``"none"`` /
    ``"headers"``). In ``"headers"`` mode the created node's empty tier plugs are
    seeded with their auto-headers (this is the ONLY path that inserts headers --
    the API / .mpn import paths never route through here, so a blank expression on
    an imported node is never re-headered). The old ``mode=="template"`` branch is
    retired -- templates are created via the gallery's
    :class:`_TemplateCreateCommand` / seed-only :class:`_ImportNodeCommand`, never
    here. Qt-free + unit-testable.
    """
    return _CreateNodeCommand(
        native_type, seed_setup=True, seed_headers=(mode == "headers"))


# ---------------------------------------------------------------------------
# Auto-setup-on-create (deformers / skin / blend / IK need scene wiring)
# ---------------------------------------------------------------------------


def _name_of(obj):
    """Best-effort node name from a factory demo's return value: a str is used
    verbatim; an object exposing get_name() is queried; anything else -> None."""
    if isinstance(obj, str):
        return obj
    getter = getattr(obj, "get_name", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return None
    return None


class _SetupNodeCommand(_BaseCommand):
    """Undoable create-AND-wire for node types that only do something once they
    are wired into the scene (a deformer must live in a mesh's deformation
    chain, a skinCluster needs joints + a mesh, a blendShape needs base +
    targets, an IK solver needs a joint chain + handle).

    ``doIt`` creates the node + runs its authored self-first ``def setup(self)``
    via ``wrapper_cls.build(setup=True)``. ``build()`` swallows + logs any setup
    failure internally, leaving the node BUILT but UNWIRED (so e.g. an empty
    selection no longer degrades to a bare node -- the node still exists and is
    already seeded with its setup source). The outer ``except`` here is now ONLY
    a guard for a ``create()`` failure: on that it degrades to the normal
    new-node create (bare) and logs a hint.

    Everything (createNode / deformer / ikHandle / setAttr / connectAttr) rides
    Maya's undo chunk, so a single Ctrl+Z removes the node and all its wiring;
    undoIt / redoIt are no-ops."""

    def __init__(self, native_type: str, mode: str = "headers"):
        self.native_type = native_type
        self.mode        = mode
        self.created_name: str | None = None

    def doIt(self) -> None:
        from mpynode._node_registry import get_spec

        try:
            spec = get_spec(self.native_type)
            if spec is None:
                raise RuntimeError("no registered spec for %r" % self.native_type)
            wrapper_cls = spec.get_wrapper_class()
            # build(setup=True): create + _populate_methods_source + run the
            # self-first setup(self). Setup failures are swallowed INSIDE build()
            # (built-but-unwired), so the except below only sees a genuine
            # create() failure. skip_selection=True keeps the user's selection,
            # which the setup wires against.
            self.created_name = wrapper_cls.build(
                setup=True, skip_selection=True).get_name()
        except Exception as exc:
            self._log_skip(exc)
            fallback = build_new_node_command(self.native_type, self.mode)
            fallback.doIt()
            self.created_name = getattr(fallback, "created_name", None)
            return
        # build() already seeded the setup source; template payloads are applied
        # by _TemplateCreateCommand, not here. In "headers" mode, prefill the
        # remaining EMPTY tier plugs with their auto-headers -- only empty tiers
        # get one, so a setup-filled Methods tier is left alone.
        if self.mode == "headers" and self.created_name:
            _seed_headers(self.created_name, self.native_type)

    def _log_skip(self, exc) -> None:
        import sys

        msg = "Auto-setup for %s skipped: %s" % (self.native_type, exc)
        sys.stderr.write("[commands] %s -- creating a bare node.\n" % msg)
        try:
            from mpynode._common.util import log_bus

            log_bus.log(msg, level="warning")
        except Exception:
            pass

    def undoIt(self) -> None:
        # createNode / deformer / ikHandle / setAttr all rode the chunk.
        pass

    def redoIt(self) -> None:
        pass


class _RunSetupCommand(_BaseCommand):
    """Run an EXISTING node's own ``_methodsSource`` setup, bound to that
    instance, against the captured selection. Rides one undo chunk.

    Distinct from :class:`_SetupNodeCommand` (which CREATES + wires in one shot):
    this is the on-demand "Run setup" on a node that already exists -- e.g. a
    bare deformer the user wants to wire into the current selection now.

    The selection is SNAPSHOTTED in ``doIt`` and handed to the setup body via the
    ``selection`` kwarg; the authored body excludes ``self`` from that snapshot
    (``_selection(override=..., exclude=name)``) so the node is never treated as
    its own input. Everything the body does (deformer / connectAttr / setAttr)
    rides Maya's undo chunk, so undoIt / redoIt are no-ops -- chunk-undo reverses
    the wiring."""

    def __init__(self, node_name, native_type):
        self.node_name    = node_name
        self.native_type  = native_type
        self.created_name = None  # no node created; harmless parity (review S1)

    def doIt(self):
        from maya import cmds
        from mpynode._node_registry import wrap_node
        from mpynode._common.methods.methods_registry import run_node_setup
        from mpynode._common.methods import setup_helpers as node_setup

        sel  = cmds.ls(selection=True, long=False) or []   # snapshot
        node = wrap_node(self.node_name, self.native_type)
        if node is None:
            raise node_setup.SetupError("cannot wrap %r" % self.node_name)
        return run_node_setup(node, sel)

    def undoIt(self):
        # The setup body's calls all rode the chunk; chunk-undo reverses them.
        pass

    def redoIt(self):
        pass


class _RunDemoCommand(_BaseCommand):
    """Run an EXISTING node's own ``_methodsSource`` demo. Rides one undo chunk.
    A demo FABRICATES its own showcase scene -- it takes NO selection. ``demo_name``
    selects among multiple demos (else the first).

    Branches on the chosen demo's kind (classified statically from the node's
    source, RCE-safe): a FACTORY demo runs via ``run_type_demo`` bound to the
    wrapper class (no instance); an INSTANCE demo wraps the node and runs via
    ``run_node_demo``. Everything the body does (createNode / duplicate / keyframe
    / viewFit) rides Maya's undo chunk, so undoIt / redoIt are no-ops."""

    def __init__(self, node_name, native_type, demo_name=None):
        self.node_name    = node_name
        self.native_type  = native_type
        self.demo_name    = demo_name
        self.created_name = None  # no template node created; harmless parity

    def doIt(self):
        from mpynode._node_registry import wrap_node
        from mpynode._common.methods.methods_registry import (
            run_node_demo, run_type_demo, methods_source_of)
        from mpynode._common.methods import setup_helpers as node_setup
        from mpynode._common import node_setups

        src = methods_source_of(self.node_name)
        spec = node_setups.select_demo(
            node_setups.find_demos(src), self.demo_name)
        is_factory = bool(spec is not None and spec.is_factory)
        if is_factory:
            return run_type_demo(self.native_type, src, self.demo_name)
        node = wrap_node(self.node_name, self.native_type)
        if node is None:
            raise node_setup.SetupError("cannot wrap %r" % self.node_name)
        return run_node_demo(node, self.demo_name)

    def undoIt(self):
        # The demo body's calls all rode the chunk; chunk-undo reverses them.
        pass

    def redoIt(self):
        pass


class _RunCommandCommand(_BaseCommand):
    """Run an EXISTING node's own ``@maya_command`` in the interpreted node, in
    one undo chunk. ``command_name`` may be the ``@maya_command`` name OR the
    python def name; ``args`` / ``kwargs`` are forwarded to ``call_command``.

    Mirrors :class:`_RunSetupCommand` / :class:`_RunDemoCommand`: wraps the node
    and dispatches through the wrapper's validated ``call_command`` helper (which
    binds a runtime command to the instance / a factory command to the class).
    Everything the command body does rides Maya's undo chunk, so undoIt / redoIt
    are no-ops -- chunk-undo reverses it."""

    def __init__(self, node_name, native_type, command_name, args=(), kwargs=None):
        self.node_name    = node_name
        self.native_type  = native_type
        self.command_name = command_name
        self.args         = tuple(args)
        self.kwargs       = dict(kwargs or {})
        self.created_name = None  # no node created; harmless parity

    def doIt(self):
        from mpynode._node_registry import wrap_node

        node = wrap_node(self.node_name, self.native_type)
        if node is None:
            raise RuntimeError("cannot wrap %r" % self.node_name)
        return node.call_command(self.command_name, *self.args, **self.kwargs)

    def undoIt(self):
        # The command body's calls are all in the chunk; chunk-undo reverses them.
        pass

    def redoIt(self):
        pass


class _RunTestCommand(_BaseCommand):
    """Run an EXISTING node's own ``@maya_test`` validation in the interpreted
    node, in one undo chunk. ``test_name`` selects among multiple tests (else the
    first).

    A test FAILURE is a RESULT, not an exception: the ``{name, label, passed,
    error}`` dict is stashed on ``self.test_result`` (Maya's ``setResult`` only
    marshals scalars, so ``doIt`` returns a short "PASS"/"FAIL" string and the
    caller reads the dict off the instance). Everything the test body does
    (createNode / polyEditUV / delete) rides the undo chunk, so undoIt / redoIt
    are no-ops -- chunk-undo reverses it, leaving the scene as it was."""

    def __init__(self, node_name, native_type, test_name=None):
        self.node_name    = node_name
        self.native_type  = native_type
        self.test_name    = test_name
        self.created_name = None  # no template node created; harmless parity
        self.test_result  = None

    def doIt(self):
        from mpynode._node_registry import wrap_node

        node = wrap_node(self.node_name, self.native_type)
        if node is None:
            raise RuntimeError("cannot wrap %r" % self.node_name)
        self.test_result = node.run_test(self.test_name)
        return "PASS" if self.test_result.get("passed") else "FAIL"

    def undoIt(self):
        pass

    def redoIt(self):
        pass


class _TemplateCreateCommand(_BaseCommand):
    """Undoable "Create + Run setup" for the template gallery (Design #2 §2).

    doIt order (the §6.1 rework -- setup runs AFTER the template payload is
    applied, so a template shipping its own methods_source/setup wins over the
    type default):
      1. Snapshot the selection BEFORE create (cmds.createNode reselects the new
         node, same load-bearing ordering as MPyNode.build()).
      2. Import the template via deserialize_node(restore_persistent=False,
         return_failures=True) -- applies every tier INCLUDING the template's
         methods_source if present; then _seed_setup_source merge-seeds the type
         default ONLY if the template carried no setup.
      3. Run the node's own self-first setup against [selection minus self] via
         the shared run_node_setup helper; failure is swallowed + logged
         (built-but-unwired), never failing creation.

    deserialize_node / setup wiring all ride Maya's undo chunk, so one Ctrl+Z
    removes the node + its wiring; undoIt / redoIt are no-ops.

    doIt RETURNS ``self.created_name`` (NOT None) so ``run_undoable(cmd)``
    yields the created node name -- matching ``_CreateNodeCommand.doIt``
    and unlike ``_ImportNodeCommand.doIt`` (which returns None). This is what
    lets the gallery "Create + Run setup" callers (and Phase H2) use
    ``name = run_undoable(cmd)`` directly; ``name = run_undoable(cmd) or
    cmd.created_name`` also works.
    """

    def __init__(self, payload: dict, native_type: str, run_setup: bool = True,
                 run_demo: bool = False, demo_name=None):
        self.payload     = payload
        self.native_type = native_type
        self.run_setup   = bool(run_setup)
        self.run_demo    = bool(run_demo)
        self.demo_name   = demo_name
        self.created_name:  str | None = None
        self.tier_failures: dict = {}

    def doIt(self) -> "str | None":
        from mpynode._common.io.mpn_io import deserialize_node
        from mpynode._common.methods.methods_registry import (
            run_node_setup, run_node_demo, run_type_demo)
        from mpynode._common import node_setups

        # 1. snapshot selection BEFORE create
        sel = cmds.ls(selection=True, long=False) or []

        # A FACTORY demo owns creation -> do NOT pre-create the template node.
        # Classify statically from the payload's methods_source (RCE-safe).
        if self.run_demo:
            src = self.payload.get("methods_source") or ""
            spec = node_setups.select_demo(
                node_setups.find_demos(src), self.demo_name)
            if spec is not None and spec.is_factory:
                try:
                    result = run_type_demo(
                        self.native_type, src, self.demo_name)
                    self.created_name = _name_of(result)
                except Exception as exc:
                    import sys

                    self.tier_failures.setdefault("demo", str(exc))
                    sys.stderr.write(
                        "[commands] template factory demo failed for %r.\n"
                        % self.native_type)
                return self.created_name

        # 2. import the template (tuple unpack: (py_node, failures)).
        #    skip_selection=True: createNode would otherwise reselect the new
        #    node and clobber the user's pre-create selection (snapshotted in
        #    step 1 + handed to setup).
        #    A template may carry a preferred node name ("mPyDnet"); honor it.
        #    Otherwise deserialize_node falls back to the template's source_name
        #    so the node is named after the demo (gameOfLifeMesh1), not the
        #    generic base type (mPyMesh1).
        py_node, self.tier_failures = deserialize_node(
            self.payload, name=self.payload.get("preferred_name"),
            restore_persistent=False, return_failures=True,
            skip_selection=True)
        created           = py_node.get_name()
        self.created_name = created
        # seed the type default ONLY if the template carried no setup
        # (merge-not-replace inside _populate_methods_source).
        _seed_setup_source(created, self.native_type)

        # 3. run demo (fabricates its own showcase scene) OR setup (wires
        #    against the snapshot minus self). run_demo wins when both are
        #    requested; failures are recorded, never fatal.
        if self.run_demo:
            try:
                run_node_demo(py_node, self.demo_name)
            except Exception as exc:
                import sys

                self.tier_failures.setdefault("demo", str(exc))
                sys.stderr.write(
                    "[commands] template demo failed for %r; node left "
                    "built-but-unwired.\n" % created)
        elif self.run_setup:
            try:
                run_node_setup(py_node, [n for n in sel if n != created])
            except Exception as exc:
                import sys

                # Record it (not just stderr) so the gallery UI can surface
                # the built-but-unwired node.
                self.tier_failures.setdefault("setup", str(exc))
                sys.stderr.write(
                    "[commands] template setup failed for %r; node left "
                    "built-but-unwired.\n" % created)

        # Return the created name so run_undoable(cmd) is non-None.
        return self.created_name

    def undoIt(self) -> None:
        # deserialize / setup wiring are all in the chunk; chunk-undo removes them.
        pass

    def redoIt(self) -> None:
        pass


def build_new_or_setup_command(native_type: str, mode: str = "headers",
                               auto_setup: bool = False):
    """Pick the create command for ``native_type``.

    When ``auto_setup`` is True AND the type has an authored self-first
    ``def setup(self)`` (:func:`mpynode._common.node_setups.type_has_setup`),
    returns a
    :class:`_SetupNodeCommand` that creates + wires the node to the current
    selection (seeding the template). Otherwise returns the normal
    template/bare :func:`build_new_node_command`. Qt-free + unit-testable; the
    Designer's right-click "Create + run setup" passes ``auto_setup=True``."""
    if auto_setup:
        try:
            from mpynode._common import node_setups

            if node_setups.type_has_setup(native_type):
                return _SetupNodeCommand(native_type, mode=mode)
        except Exception:
            pass
    return build_new_node_command(native_type, mode)


# ---------------------------------------------------------------------------
# Duplicate (Scene-tree right-click / Node menu)
# ---------------------------------------------------------------------------


def _deep_copy_stored_vars(stored_vars: dict) -> dict:
    """Return an INDEPENDENT deep copy of a stored-vars dict.

    A node duplicate must not SHARE persistent data with its source: the
    in-memory ``serialize_node`` -> ``deserialize_node`` path only shallow-copies
    the stored-vars dict, so mutable values (numpy arrays, lists, nested dicts,
    custom objects) would otherwise be the SAME object on both nodes and
    mutating one would silently change the other.

    ``copy.deepcopy`` is the faithful in-memory copy (preserves everything
    copyable, drops nothing); if a value can't be deep-copied we fall back to
    the same encode/decode codec the ``.mpn`` disk round-trip uses (pickle-based,
    proven to yield fresh objects); last resort is a shallow dict (never
    expected -- only if BOTH paths fail)."""
    if not stored_vars:
        return {}
    import copy

    try:
        return copy.deepcopy(dict(stored_vars))
    except Exception:
        pass
    try:
        from mpynode._common.io import serialization

        encoded, _dropped = serialization.encode_stored_vars_resilient(
            dict(stored_vars), compression="zlib"
        )
        copied, _failures = serialization.decode_stored_vars_detailed(
            encoded, trusted=True
        )
        return copied
    except Exception:
        return dict(stored_vars)


def _rewire_input_connections(source_name: str, dup_name: str) -> None:
    """Re-create on ``dup_name`` every INCOMING connection that drives an input
    of ``source_name`` (the upstream source plug is shared; the destination is
    redirected onto the duplicate). Output connections are deliberately NOT
    copied -- the duplicate's outputs stay free to be wired to a fresh target.

    ``listConnections(node, source=True, destination=False, plugs=True,
    connections=True)`` returns a flat ``[thisNodePlug, upstreamPlug, ...]``
    list; the index on multi/compound plugs is part of ``thisNodePlug`` so it
    is preserved automatically when we swap only the node prefix."""
    pairs = (
        cmds.listConnections(
            source_name,
            source      = True,
            destination = False,
            plugs       = True,
            connections = True,
        )
        or []
    )
    for i in range(0, len(pairs) - 1, 2):
        this_plug, upstream = pairs[i], pairs[i + 1]
        # this_plug is "<source_name>.<attr...>": redirect onto the duplicate by
        # swapping ONLY the node prefix (split once, so "uvCoord.uCoord" and
        # "input[3]" stay intact).
        parts = this_plug.split(".", 1)
        if len(parts) != 2:
            continue
        dst_plug = dup_name + "." + parts[1]
        try:
            cmds.connectAttr(upstream, dst_plug, force=True)
        except Exception:
            # An attr that can't accept the connection (already driven, type
            # mismatch) is skipped rather than aborting the whole duplicate.
            pass


class _DuplicateNodeCommand(_ImportNodeCommand):
    """Undoable node duplicate. Reuses ``_ImportNodeCommand`` to recreate the
    node from a serialized payload (deep-copied persistent data baked in), then
    -- for the ``+ Inputs`` variant -- re-wires the source's input connections.

    Everything (createNode / addAttr / setAttr / connectAttr) rides Maya's undo
    chunk, so a single Ctrl+Z removes the duplicate and all its new wiring;
    undoIt / redoIt stay no-ops (inherited)."""

    def __init__(self, payload, source_name, with_inputs=False, name=None,
                 restore_persistent=True):
        super().__init__(payload, name=name, restore_persistent=restore_persistent)
        self.source_name = source_name
        self.with_inputs = bool(with_inputs)

    def doIt(self):
        super().doIt()  # deserialize -> self.created_name (+ tier_failures)
        if self.with_inputs and self.created_name:
            _rewire_input_connections(self.source_name, self.created_name)


def build_duplicate_node_command(source_name: str, native_type: str | None = None,
                                 with_inputs: bool = False) -> _BaseCommand:
    """Return the undoable command that duplicates ``source_name``.

    The duplicate carries a DEEP, INDEPENDENT copy of the source's persistent
    stored data (see :func:`_deep_copy_stored_vars`) plus its full definition
    (compute/init/viewport/osl/methods sources, input/output attrs, metadata).
    With ``with_inputs=True`` the source's incoming connections are also
    re-created on the copy.

    Qt-free + unit-testable (the Designer's handlers just forward to this). The
    new node is named after the source (Maya appends a numeric suffix to keep it
    unique), mirroring native Maya duplicate naming."""
    from mpynode._common.io.mpn_io import serialize_node
    from mpynode._node_registry import wrap_node

    if native_type is None:
        native_type = cmds.nodeType(source_name)
    py_source = wrap_node(source_name, native_type)
    if py_source is None:
        raise RuntimeError(
            "cannot duplicate %r: no wrapper for type %r"
            % (source_name, native_type)
        )
    payload = serialize_node(py_source, include_persistent=True)
    # Duplicate ONLY persistent stored data. serialize_node captures
    # get_variables(), the FULL in-memory store, which also holds session-only
    # scratch (un-registered self.X writes in compute, or persistent=False
    # vars). Restoring those would PROMOTE them to persistent on the copy
    # (deserialize defaults to persistent=True), diverging from the source's
    # footprint and bloating the saved scene. Keep only names registered in
    # _storedVarNames; scratch re-initialises on the copy's compute.
    from mpynode._common.storedvars import stored_vars_api

    persistent_names = set(stored_vars_api.get_variable_names(source_name))
    raw_vars         = payload.get("stored_vars") or {}
    persistent_vars  = {k: v for k, v in raw_vars.items() if k in persistent_names}
    # Then deep-copy so the copy's data is its own (never shared with the source).
    payload["stored_vars"] = _deep_copy_stored_vars(persistent_vars)
    return _DuplicateNodeCommand(
        payload, source_name, with_inputs=with_inputs, name=source_name,
        restore_persistent=True,
    )


# ---------------------------------------------------------------------------
# Convert to C++ (forward Python->C++ node swap; Stage-2 sub-project 1)
# ---------------------------------------------------------------------------


def compiled_type_for(node_name: str, native_type: str):
    """Return the Class-derived compiled node type for ``node_name`` IFF the node
    carries a Class AND that compiled type is currently loaded; else ``None``.

    ``derive_class_identity`` gives the canonical lower-first camelCase type name
    for the node's ``class_path``. The type counts as this node's compiled C++
    type ONLY if it is provided by a LOADED PLUG-IN (via ``pluginInfo dependNode``)
    and is not one of the static REGISTRY base types -- ``allNodeTypes()`` also
    lists STOCK Maya built-ins (``clamp``, ``network``, ...), so a Class whose
    derived name collides with a stock type must NOT be treated as convertible."""
    from mpynode.wrappers._mpy_node import _read_py_class
    from mpynode.native.spec.identity import derive_class_identity
    from mpynode._node_registry import REGISTRY

    pc = _read_py_class(node_name)
    if not pc:
        return None
    try:
        ntype = derive_class_identity(pc, native_type)["node_type_name"]
    except Exception:
        return None
    if not ntype or ntype in REGISTRY:
        return None
    try:
        plugin_types = set()
        for plug in (cmds.pluginInfo(query=True, listPlugins=True) or []):
            for nt in (cmds.pluginInfo(plug, query=True, dependNode=True) or []):
                plugin_types.add(nt)
    except Exception:
        return None
    return ntype if ntype in plugin_types else None


def linked_compiled_node(node_name: str):
    """Return the hidden compiled C++ sibling linked to ``node_name`` via the
    ``mpyCompiledLink`` message attr (the coexist convert), or ``None`` when the
    node is not converted / the link is not live."""
    if not node_name or not cmds.objExists(node_name):
        return None
    if not cmds.attributeQuery("mpyCompiledLink", node=node_name, exists=True):
        return None
    dsts = cmds.listConnections(
        node_name + ".mpyCompiledLink", source=False, destination=True) or []
    return dsts[0] if dsts else None


def is_converted(node_name: str) -> bool:
    """True iff ``node_name`` currently coexists with a compiled C++ sibling
    (a live ``mpyCompiledLink`` connection). Keyed on the CONNECTION, not merely
    the attr's existence, so a stale attr never reads as converted."""
    return linked_compiled_node(node_name) is not None


def _coexist_eligible(node_name: str, native_type: str) -> bool:
    """True iff ``node_name``'s node type is safe for coexist-convert.

    Coexist works by DUPLICATING input edges and MOVING output edges onto a
    sibling, so it is meaningful only when everything that CONSUMES the node's
    result is reachable as a movable, non-infra plug edge -- or, where it is not,
    when the user is TOLD what stayed behind.

    Eligible:
      * DG plug-output types; deformers (``geometryFilter`` -- consumed at
        ``outputGeometry[]``, an output plug like any other).
      * ``locator`` -- a DAG *shape*, admitted because the sibling is created
        under the SAME transform and the idle Python shape is hidden via
        ``lodVisibility``.
      * ``transform`` -- its DAG CHILDREN follow parentage, which is not an edge,
        so it gets an INPUTS-ONLY convert: the sibling is built and fed, the
        outputs stay put, and the designer warns with
        ``node_swap.downstream_dependents`` before proceeding. Converting is an
        interactive development step -- the user validates, then compiles for
        real -- so leaving the choice to them beats refusing outright.
      * ``ikSolver`` -- it has no non-message output plugs, but an ikHandle names
        its solver through a SINGLE ``.message`` destination, and message edges
        are now judged by DESTINATION (registry multi vs functional single, see
        ``node_swap._is_message_registry_slot``) rather than by attr name. The
        reference moves; the ``ikSystem.ikSolver[]`` registry entry does not.

    Excluded: a DAG *shape* that is not a locator -- there is no co-located
    sibling story for it.
    """
    try:
        if not cmds.objectType(node_name, isAType="dagNode"):
            return True
        if cmds.objectType(node_name, isAType="transform"):
            return True
        return bool(cmds.objectType(node_name, isAType="locator"))
    except Exception:
        return False


def is_convertible_to_cpp(node_name: str, native_type: str) -> bool:
    """True iff ``node_name`` is an INTERPRETED mPy node (its native type is a
    static REGISTRY type) that is coexist-ELIGIBLE, NOT already converted, and
    carries a Class whose compiled C++ type is loaded -- so a coexist convert can
    proceed. (An already-converted node offers "Revert to Python" instead.)"""
    from mpynode._node_registry import REGISTRY

    if native_type not in REGISTRY:
        return False
    if is_converted(node_name):
        return False
    if not _coexist_eligible(node_name, native_type):
        return False
    return compiled_type_for(node_name, native_type) is not None


class _ConvertToCppCommand(_BaseCommand):
    """Undoable COEXIST convert: create a hidden compiled C++ sibling that takes
    over driving downstream, leaving the interpreted Python node in the scene
    (idle, source of truth) -- it is NOT deleted. Duplicates the input wiring,
    moves the output wiring onto the C++ node, snapshots static values, and links
    the two with a message attr (see :func:`node_swap.attach_compiled`).

    Every step is an undoable Maya command (``createNode`` / ``setAttr`` /
    ``connectAttr`` / ``addAttr`` / ``lockNode``), so it rides the
    ``runUndoableAPICommand`` chunk and ``undoIt`` / ``redoIt`` are NO-OPS -- the
    SAME contract as :class:`_DeleteNodeCommand`. One Ctrl+Z removes the C++
    sibling, moves the outputs back onto the Python node, and drops the link.

    Does NOT transfer live in-memory stateful data (stored vars / RNG / buffers);
    the designer WARNS before running this on a stateful node (non-destructive --
    the Python node is retained, so revert is exact). The dirty re-arm is an
    idempotent, scene-state-free side effect, harmless if un-reversed on undo."""

    def __init__(self, node_name: str, native_type: str):
        self.node_name   = node_name
        self.native_type = native_type
        self.created_name:     str | None = None
        self.dropped:          list = []
        self.cycle_introduced: bool = False
        self._pre_cycle:       bool = False

    def doIt(self):
        from mpynode._base import node_swap
        from mpynode.wrappers._mpy_node import _read_py_class
        from mpynode.native.spec.identity import derive_class_identity

        # Not-already-converted gate (beyond the menu + re-entrancy guard): a
        # second convert would strand a sibling.
        if is_converted(self.node_name):
            raise RuntimeError(
                "%r is already converted to C++ (revert first)."
                % self.node_name)
        pc = _read_py_class(self.node_name)
        if not pc:
            raise RuntimeError(
                "cannot convert %r: it has no Class (a compiled type is derived "
                "from the node's Class)." % self.node_name)
        compiled_type = derive_class_identity(
            pc, self.native_type)["node_type_name"]
        if not compiled_type:
            raise RuntimeError(
                "cannot derive a compiled type for %r." % self.node_name)

        # Baseline: a cycle already running through this node means one found
        # after the convert was NOT introduced by it.
        try:
            self._pre_cycle = bool(cmds.cycleCheck(
                [self.node_name], all=False, list=True) or [])
        except Exception:
            self._pre_cycle = False

        self.created_name, self.dropped = node_swap.attach_compiled(
            self.node_name, compiled_type)

        self._rearm_dirty(self.created_name)
        self._note_cycle(self.created_name)
        # Return the PYTHON node name: it stays in the scene (source of truth)
        # and is what the Designer keeps selected.
        return self.node_name

    def _rearm_dirty(self, new_name):
        # Re-arm the compiled-geo source-side dirty bridge + kick the node
        # dirty. Best-effort; a non-geo compiled node needs neither.
        try:
            from mpynode._common.plugs import auto_dirty
            auto_dirty.install_native_geo_coverage()
        except Exception:
            pass
        try:
            cmds.dgdirty(new_name)
        except Exception:
            pass

    def _note_cycle(self, new_name):
        # Advisory only: the compiled node's all-to-all attributeAffects can
        # introduce a DG cycle the selective interpreted node did not have.
        try:
            found                 = cmds.cycleCheck([new_name], all=False, list=True) or []
            self.cycle_introduced = bool(found) and not self._pre_cycle
        except Exception:
            self.cycle_introduced = False

    def undoIt(self):
        # No-op: the swap's DG calls all rode the chunk; undo restores the node.
        pass

    def redoIt(self):
        # No-op: chunk-redo replays the swap.
        pass


def build_convert_to_cpp_command(node_name: str,
                                 native_type: str) -> _BaseCommand:
    """Return the undoable command that coexist-converts ``node_name`` to a
    hidden compiled C++ sibling. Mirrors :func:`build_duplicate_node_command`
    (the designer just forwards to this)."""
    return _ConvertToCppCommand(node_name, native_type)


class _RevertToPyCommand(_BaseCommand):
    """Undoable REVERT of a coexist convert: traverse the ``mpyCompiledLink`` to
    the hidden compiled sibling, move its output wiring back onto the Python node,
    restore locator ``lodVisibility``, drop the link + snapshot attrs, and delete
    the compiled node (see :func:`node_swap.detach_compiled`). Restores the exact
    pre-convert scene.

    Every step rides the ``runUndoableAPICommand`` chunk, so ``undoIt`` /
    ``redoIt`` are NO-OPS: one Ctrl+Z re-creates the compiled sibling and
    re-establishes the converted state."""

    def __init__(self, node_name: str, native_type: str):
        self.node_name   = node_name
        self.native_type = native_type
        self.dropped: list = []

    def doIt(self):
        from mpynode._base import node_swap

        cpp = linked_compiled_node(self.node_name)
        if cpp is None:
            raise RuntimeError(
                "%r is not converted to C++ (nothing to revert)."
                % self.node_name)
        self.dropped = node_swap.detach_compiled(cpp, self.node_name)
        # Re-arm the compiled-geo dirty bridge + kick the Python node so
        # downstream recomputes from the restored interpreted output.
        try:
            from mpynode._common.plugs import auto_dirty
            auto_dirty.install_native_geo_coverage()
        except Exception:
            pass
        try:
            cmds.dgdirty(self.node_name)
        except Exception:
            pass
        return self.node_name

    def undoIt(self):
        # No-op: detach's DG calls rode the chunk; undo re-creates the sibling.
        pass

    def redoIt(self):
        # No-op: chunk-redo replays the revert.
        pass


def build_revert_to_py_command(node_name: str,
                               native_type: str) -> _BaseCommand:
    """Return the undoable command that reverts a coexist-converted ``node_name``
    back to pure Python (deletes the hidden compiled sibling)."""
    return _RevertToPyCommand(node_name, native_type)
