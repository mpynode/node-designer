"""MPyNode (API 2.0) — the basic expression-driven DG node.

User workflow:
  1. ``MPyNode.create(name="myNode")`` creates the node + returns a wrapper.
  2. ``wrapper.add_input_attr("a", "float")`` adds an input plug.
  3. ``wrapper.add_output_attr("c", "float")`` adds an output plug.
  4. ``wrapper.set_compute_expression("c = a * b * 2")`` stores Python source.
  5. Set the input plug value via ``cmds.setAttr myNode.a 5``.
  6. Read the output plug via ``cmds.getAttr myNode.c`` \u2014 triggers
     compute() which:
       * reads the _inputAttrs JSON to know which user inputs exist
       * reads the _outputAttrs JSON to know what outputs to write
       * reads the expression string + compiles it
       * builds an exec namespace with all input values
       * execs the expression
       * writes back any output values that the expression set
"""

from __future__ import annotations

import maya.api.OpenMaya as om
from mpynode._api2 import helpers
from mpynode._common.io import serialization
from mpynode._common.storedvars import stored_var_store as _svstore
from mpynode._common.compute.expression import (
    build_exec_namespace,
    compile_expression,
    exec_with_profile_watch,
)


class MPyNode(om.MPxNode):
    """API 2.0 expression-driven DG node."""

    NODE_NAME = "mPyNode"
    NODE_ID   = om.MTypeId(0x00135700)  # in our private range

    # mPyNode has no bridge-injected internals beyond user storage; subclasses
    # (mPyConstraint, ...) add their own. There is no INTERNAL_VARS schema --
    # the expression reaches plug-tree state through ``self.X``.

    # Class-level MObjects for the internal attrs (set by nodeInitializer)
    _expression_attr:       om.MObject = om.MObject.kNullObj
    _input_attrs_attr:      om.MObject = om.MObject.kNullObj
    _output_attrs_attr:     om.MObject = om.MObject.kNullObj
    _stored_vars_list_attr: om.MObject = om.MObject.kNullObj
    _stored_vars_data_attr: om.MObject = om.MObject.kNullObj
    _debug_mode_attr:       om.MObject = om.MObject.kNullObj
    # profile + watch instrumentation plugs.
    _profile_enabled_attr:       om.MObject = om.MObject.kNullObj
    _deep_profile_enabled_attr:  om.MObject = om.MObject.kNullObj
    _watch_enabled_attr:         om.MObject = om.MObject.kNullObj
    _profile_snapshot_data_attr: om.MObject = om.MObject.kNullObj
    _watch_vars_data_attr:       om.MObject = om.MObject.kNullObj

    def __init__(self):
        super().__init__()
        # Per-instance compiled expression cache (recompiled in
        # setInternalValue when the expression string changes).
        self._expr_str: str = ""
        self._expr_code = compile_expression("")

    # ------------------------------------------------------------------
    # Maya MPxNode API
    # ------------------------------------------------------------------

    @staticmethod
    def creator():
        return MPyNode()

    @staticmethod
    def initializer():
        plugs                          = helpers.build_internal_attrs(MPyNode)
        MPyNode._expression_attr       = plugs["_computeSource"]
        MPyNode._input_attrs_attr      = plugs["inputs"]
        MPyNode._output_attrs_attr     = plugs["outputs"]
        MPyNode._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyNode._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyNode._debug_mode_attr       = plugs["debug_mode"]

        MPyNode._profile_enabled_attr       = plugs["profile_enabled"]
        MPyNode._deep_profile_enabled_attr  = plugs["deep_profile_enabled"]
        MPyNode._watch_enabled_attr         = plugs["watch_enabled"]
        MPyNode._profile_snapshot_data_attr = plugs["profile_snapshot_data"]
        MPyNode._watch_vars_data_attr       = plugs["watch_vars_data"]

    def setInternalValue(self, plug, data_handle):
        """Track changes to the ``_computeSource`` attr by recompiling
        ``_expr_code`` on the spot.

        Uses ``type(self)._expression_attr`` instead of
        ``MPyNode._expression_attr`` so subclasses (e.g. MPyConstraint)
        with their OWN expression MObject get the recompile too.

        SyntaxErrors are now surfaced via
        MGlobal.displayWarning instead of being swallowed silently. On
        compile failure ``_expr_code`` is LEFT ALONE (last-known-good)
        so the node keeps computing with its previous expression until
        the user fixes the typo.
        """
        try:
            attr = plug.attribute()
            if attr in (type(self)._input_attrs_attr,
                        type(self)._output_attrs_attr):
                from mpynode._common.plugs import dirty_affects

                dirty_affects.invalidate(self.thisMObject())
            if attr == type(self)._expression_attr:
                # MDataHandle for a string returns asString()
                new_src        = data_handle.asString()
                self._expr_str = new_src
                from mpynode._common.compute.expression import safe_compile_expression

                node_name = ""
                try:
                    import maya.api.OpenMaya as _om

                    node_name = _om.MFnDependencyNode(self.thisMObject()).name()
                except Exception:
                    pass
                code = safe_compile_expression(
                    new_src,
                    node_name = node_name,
                    filename  = "<mpynode-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        # False tells Maya to also write the value to its internal storage --
        # required for storable=True string plugs.
        return False

    def setDependentsDirty(self, plug, affected_plugs):
        """Mark all USER output plugs dirty when a USER input or the
        expression changes. Required because USER inputs/outputs are
        added dynamically (per-instance) and we can't declare static
        attributeAffects relationships in nodeInitializer.

        Routed through the shared :func:`dirty_affects.declare_user_affects`
        helper so this body cannot re-introduce the super-return bug (a
        ``return om.MPxNode.setDependentsDirty(...)`` would silently defeat
        the in-place append and stop Maya recomputing the dirtied outputs).
        """
        from mpynode._common.plugs import dirty_affects

        # A SUSPENDED node (nodeState Has No Effect / Blocking -- Convert to
        # C++ sets it on the idle Python node, a user may too) forwards
        # nothing. The Evaluation Manager evaluates every user output an
        # animated input dirties whether or not anything reads it -- a full
        # expression run per frame on a node meant to be idle (Mesh Maze's
        # int solutionSteps after Convert to C++, measured 2026-09-14).
        if dirty_affects.api2_dirty_gate(self, plug):
            return None
        dirty_affects.declare_user_affects(
            self.thisMObject(),
            plug,
            affected_plugs,
            type(self)._input_attrs_attr,
            type(self)._output_attrs_attr,
            expression_attr=type(self)._expression_attr,
        )
        return None

    def compute(self, plug, data_block):
        """Run the user expression to fulfill a request for ``plug``.

        namespace contract (self-only):
          * inputs and outputs are reached ONLY via ``self.X`` (SelfProxy).
            Inputs are seeded into the SelfProxy snapshot; outputs are
            committed only when the expression assigns ``self.out = value``.
            Bare names are NOT injected and bare assignments are NOT harvested.
          * stored variables are accessed via ``self.X`` (SelfProxy).
            Internal vars (per-class ``INTERNAL_VARS`` schema) also via
            ``self.X``; populated as empty dict here \u2014 future iterations may
            inject per-class internals.
          * NO auto-imported modules (``np`` / ``math`` / ``cmds`` etc.)
            \u2014 the expression must ``import`` them itself. ``__builtins__``
            stays so ``len`` / ``range`` / etc. work.
        """
        # Defer while a scene is being READ. Maya's Evaluation Manager (notably
        # 2026) can pull an output mid-load, before this node's dynamic input
        # attrs and/or its schema plugs are restored; running the expression
        # then raises a spurious "'self' has no plug ... named '<input>'" that
        # "works" on the next eval. Returning leaves the plug dirty so Maya
        # recomputes when the scene is whole.
        try:
            # MFileIO lives in API 1.0 (maya.api.OpenMaya has no MFileIO).
            import maya.OpenMaya as _om1

            if _om1.MFileIO.isReadingFile():
                return
        except Exception:
            pass
        # Suspended (nodeState != Normal): not evaluated. The plug stays
        # dirty so un-suspending recomputes it -- the API 1.0 deformers'
        # contract. Read off the data block: safe on an EM worker thread.
        from mpynode._common.plugs import dirty_affects as _dirty_affects

        if _dirty_affects.api2_suspended_in_block(self, data_block):
            return

        # Identify the OUTPUT being requested.
        try:
            attr_obj = plug.attribute()
            attr_fn  = om.MFnAttribute(attr_obj)
            out_name = attr_fn.name
        except Exception:
            return

        # Figure out which USER outputs this node has.
        node_obj = self.thisMObject()
        fn_node  = om.MFnDependencyNode(node_obj)

        try:
            outputs_str = fn_node.findPlug(MPyNode._output_attrs_attr, True).asString()
            output_map = (
                serialization.decode_attr_map(outputs_str) if outputs_str else {}
            )
        except Exception:
            output_map = {}

        if out_name not in output_map:
            # Not a USER output (e.g. an internal plug); nothing to do.
            return

        # Read all USER inputs.
        try:
            inputs_str = fn_node.findPlug(MPyNode._input_attrs_attr, True).asString()
            input_map  = serialization.decode_attr_map(inputs_str) if inputs_str else {}
        except Exception:
            input_map = {}

        # Pass the data_block so geometry inputs pull upstream-evaluated data
        # (EM-safe); plug.asMObject() alone returns rest/stale geometry here.
        input_values = helpers.read_user_inputs_dict(
            node_obj, input_map, data_block=data_block
        )

        # Read stored variables. Exposed via ``self.X`` post-Phase-27.
        stored_vars = {}
        try:
            sv_str      = fn_node.findPlug(MPyNode._stored_vars_data_attr, True).asString()
            stored_vars = _svstore.load_for_compute(node_obj, sv_str)
        except Exception:
            stored_vars = {}

        # Pre-seed every USER output BEFORE constructing the SelfProxy: it
        # snapshots ``_psp_compute_local_keys`` from ``compute_locals.keys()``
        # at construction, so a key added later is not recognised by
        # ``__setattr__`` and falls through to the plug-write path, which
        # crashes on the api1/api2 mismatch.
        import numpy as _np  # noqa: F401 (kept for downstream use)
        from mpynode._common.compute.output_defaults import output_default

        user_out_defaults: dict = {}
        for out_attr_name, meta in output_map.items():
            attr_type = meta.get("attr_type", "float")
            is_array  = bool(meta.get("is_array", False))
            # ARRAY outputs seed a PRE-SIZED (N, ...) buffer for in-place
            # slice-assign. N = the multi's connected element span (max
            # connected logical index + 1), so row i aligns with element [i].
            n = 0
            if is_array:
                try:
                    oplug = fn_node.findPlug(out_attr_name, True)
                    idxs  = list(oplug.getExistingArrayAttributeIndices())
                    n     = (max(idxs) + 1) if idxs else 0
                except Exception:
                    n = 0
            user_out_defaults[out_attr_name] = output_default(
                attr_type, is_array, n
            )

        # User outputs land in compute_locals via SelfProxy.__setattr__ Tier 1;
        # the harvest loop reads them back and commits via the type-aware
        # helpers, unifying the write path with every other api2 node.
        from mpynode._common.compute.self_proxy import SelfProxy

        # Seed the USER INPUTS (already read above) into compute_locals
        # alongside the output defaults, so ``self.input`` resolves from that
        # snapshot (Tier 1) instead of a LIVE plug lookup during exec. The live
        # lookup is fragile under the EM: a keyframe / connection change
        # triggers a graph rebuild and the expression can run on a worker thread
        # where the dynamic attr is momentarily unresolvable, raising a spurious
        # "self has no plug named 'input'". Reading once up front removes that
        # race.
        merged_locals = dict(input_values)
        merged_locals.update(user_out_defaults)

        self_proxy = SelfProxy(
            node_obj,
            datablock       = data_block,
            user_storage    = stored_vars,
            compute_locals  = merged_locals,
            node_type_label = type(self).__name__,
        )

        # SINGLE namespace dict (no globals/locals split). Self-only: inputs
        # are reached via self.X, seeded into the snapshot above, not bare.
        namespace         = build_exec_namespace()  # __builtins__ only
        namespace["self"] = self_proxy

        # Keep compiled code in sync with the _computeSource plug so a
        # DUPLICATED node (which doesn't route through setInternalValue)
        # runs its expression -- see helpers.ensure_expr_code.
        helpers.ensure_expr_code(self, type(self)._expression_attr)

        # Run the expression.
        if self._expr_code is not None:
            # Capture stderr from the expression and broadcast it to the UI
            # Log panel via the Qt-free log_bus.
            captured: list[str] = []

            def _on_err(msg):
                captured.append(msg)

            ok = exec_with_profile_watch(
                self._expr_code,
                namespace,
                on_error = _on_err,
                node_obj = node_obj,
            )
            if not ok and captured:
                # Suppress the benign, self-correcting "self has no plug named
                # X" transient (the EM pulling this output during/after a scene
                # load, or on a worker thread mid graph rebuild, before a
                # DECLARED input plug resolves) and broadcast every genuine
                # error to stderr + the Qt-free log_bus. This is the CANONICAL
                # base contract, living in base_contract so every other compute
                # path shares it and it can't drift.
                from mpynode._common.compute.base_contract import (
                    broadcast_compute_error,
                )

                broadcast_compute_error(
                    "mPyNode",
                    captured[0],
                    declared_names=set(input_map) | set(output_map),
                )

        # Write back outputs. Self-only: an output is committed only when the
        # expression assigns ``self.out = value`` (SelfProxy routes that into
        # compute_locals). Bare assignments are NOT harvested.
        locals_out = self_proxy.get_compute_locals()
        for out_attr_name, meta in output_map.items():
            if out_attr_name in locals_out:
                value = locals_out[out_attr_name]
            else:
                continue
            if value is None:
                # User did not write to this output; skip the commit.
                continue
            try:
                out_plug_full = fn_node.findPlug(out_attr_name, True)
                attr          = out_plug_full.attribute()
                attr_type     = meta.get("attr_type", "float")
                if bool(meta.get("is_array", False)):
                    helpers.write_multi_plug_value(
                        data_block,
                        attr,
                        attr_type,
                        value,
                        out_plug=out_plug_full,
                    )
                else:
                    helpers.write_plug_value(
                        data_block,
                        om.MPlug(node_obj, attr),
                        attr_type,
                        value,
                    )
            except Exception:
                pass

        # Commit stored-var changes via the SelfProxy diff: one plug write per
        # compute, however many self.X assignments the expression made.
        storage_diff = self_proxy.diff_storage()
        if storage_diff:
            new_stored = dict(stored_vars)
            for k, v in storage_diff.items():
                if v is None:
                    new_stored.pop(k, None)
                else:
                    new_stored[k] = v
            _svstore.set_for_compute(node_obj, new_stored)

        data_block.setClean(plug)
