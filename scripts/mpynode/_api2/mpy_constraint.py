"""MPyConstraint (API 2.0) \u2014 expression-driven custom constraint.

Implementation note:
  The lesson from the old branch was that ``MPxConstraint``
  hijacks ``compute()`` for its inherited plugs, requiring a reactive
  callback pattern to write USER outputs. For node-designer2 we take
  a simpler path: ``MPyConstraint`` is an ``MPxNode`` subclass with
  preset constraint-style attrs (``targetTranslate``, ``targetRotate``,
  ``targetWeight``, ``restTranslate``, ``restRotate``). The user
  expression reads these inputs + their own added inputs, then writes
  USER outputs via the standard ``compute()`` path.

  This avoids the compute-hijack workaround entirely while still giving
  users a node identifiable as a "constraint" (distinct node type +
  channel-box-friendly preset inputs).

Recipe declares the preset inputs as REAL plugs so they appear in the
Inputs panel.
"""

from __future__ import annotations

import maya.api.OpenMaya as om
from mpynode._api2 import helpers
from mpynode._api2._mpy_node import MPyNode

# The 5 preset constraint inputs (+ their vector X/Y/Z children, normalised to
# the root name by the shared dirty helper). A change to any must dirty the
# USER outputs, just like a user input does.
_PRESET_INPUT_NAMES = frozenset(
    {
        "targetTranslate",
        "targetRotate",
        "targetWeight",
        "restTranslate",
        "restRotate",
    }
)


def _read_double3_via_plug(plug_proxy, name):
    """Pull a Double3 plug as ``(3,) float64`` numpy via
    ``PlugProxy.<name>.asNumpy()``. Replaces
    the ``cmds.getAttr`` based reads previously inside
    ``MPyConstraint.compute``. Falls back to a zero 3-vector on any
    access failure."""
    import numpy as _np

    try:
        sub = getattr(plug_proxy, name)
        if hasattr(sub, "asNumpy"):
            arr = sub.asNumpy()
            if arr.shape == (3,):
                return arr
        if hasattr(sub, "shape") and getattr(sub, "shape", None) == (3,):
            return _np.asarray(sub, dtype=_np.float64)
    except Exception:
        pass
    return _np.zeros(3, dtype=_np.float64)


class MPyConstraint(MPyNode):
    NODE_NAME = "mPyConstraint"
    NODE_ID = om.MTypeId(0x00135703)

    # Cache the api1 MObject across compute calls: PlugProxy needs one to read
    # preset_internals, and re-resolving via MSelectionList every compute is
    # cheap but not free. A NameChanged callback refreshes ``_cached_api1_name``
    # proactively on rename -- the MObject itself stays valid, since Maya keeps
    # MObject pointers stable across a rename.
    _cached_api1_mobject = None
    _cached_api1_name = None
    _cached_api1_rename_token = None

    def _api1_mobject(self, current_name):
        """Return a cached api1 MObject for this
        constraint, re-resolving via MSelectionList if the cache is
        stale (post-rename) or null (post-delete). Returns None on
        any failure.

        at first resolve, also subscribes an
        ``addNameChangedCallback`` on the MObject so the cached name
        is refreshed proactively (so subscribers of e.g. the Storage
        tab see the correct ``self.targetTranslate`` plug full name
        post-rename without waiting for the next reactive
        re-resolve)."""
        import maya.OpenMaya as _om1

        cached = self._cached_api1_mobject
        if (
            cached is not None
            and not cached.isNull()
            and self._cached_api1_name == current_name
        ):
            return cached
        try:
            sel = _om1.MSelectionList()
            sel.add(current_name)
            mob = _om1.MObject()
            sel.getDependNode(0, mob)
            self._cached_api1_mobject = mob
            self._cached_api1_name = current_name
            # Register the rename hook once. Drop an existing token first, in
            # case the cache was invalidated by a name-mismatch path that
            # didn't tear down the prior callback.
            if self._cached_api1_rename_token is not None:
                try:
                    from mpynode._common.lifecycle.callbacks import (
                        CALLBACK_MANAGER as _CBM,
                    )
                    _CBM.unregister(self._cached_api1_rename_token)
                except Exception:
                    pass
                self._cached_api1_rename_token = None
            try:
                from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API2

                def _on_renamed(_node, _old_name, *_args):
                    try:
                        fn = _om1.MFnDependencyNode(self._cached_api1_mobject)
                        self._cached_api1_name = fn.name()
                    except Exception:
                        # MObject went null between rename + callback;
                        # nothing to update.
                        self._cached_api1_name = None

                cb_id = _om1.MNodeMessage.addNameChangedCallback(
                    mob, _on_renamed
                )
                # Owned by api2 so the api2 unload sweeps it; also
                # unregistered above when the cache is invalidated.
                self._cached_api1_rename_token = CALLBACK_MANAGER.register(
                    cb_id, _om1.MMessage.removeCallback, OWNER_API2
                )
            except Exception:
                # Best-effort: the reactive name-mismatch check still
                # covers stale caches.
                pass
            return mob
        except Exception:
            self._cached_api1_mobject = None
            self._cached_api1_name = None
            return None

    # The preset inputs (targetTranslate / targetRotate / targetWeight /
    # restTranslate / restRotate) are bridge-injected, NOT in the user's
    # _inputAttrs JSON. Exposed read-only via ``self.X``; there is no
    # INTERNAL_VARS schema.

    _targetTranslate_attr: om.MObject = om.MObject.kNullObj
    _targetRotate_attr: om.MObject = om.MObject.kNullObj
    _targetWeight_attr: om.MObject = om.MObject.kNullObj
    _restTranslate_attr: om.MObject = om.MObject.kNullObj
    _restRotate_attr: om.MObject = om.MObject.kNullObj

    @staticmethod
    def creator():
        return MPyConstraint()

    @staticmethod
    def initializer():
        # Standard internal attrs (expression, in/out maps, debug_mode, ...).
        plugs = helpers.build_internal_attrs(MPyConstraint)
        MPyConstraint._expression_attr = plugs["_computeSource"]
        MPyConstraint._input_attrs_attr = plugs["inputs"]
        MPyConstraint._output_attrs_attr = plugs["outputs"]
        MPyConstraint._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyConstraint._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyConstraint._debug_mode_attr = plugs["debug_mode"]

        MPyConstraint._profile_enabled_attr = plugs["profile_enabled"]
        MPyConstraint._deep_profile_enabled_attr = plugs["deep_profile_enabled"]
        MPyConstraint._watch_enabled_attr = plugs["watch_enabled"]
        MPyConstraint._profile_snapshot_data_attr = plugs["profile_snapshot_data"]
        MPyConstraint._watch_vars_data_attr = plugs["watch_vars_data"]

        # Add the constraint-style preset INPUT attrs.
        nattr = om.MFnNumericAttribute()

        # targetTranslate (vector input)
        MPyConstraint._targetTranslate_attr = nattr.createPoint(
            "targetTranslate", "ttr"
        )
        nattr.storable = True
        nattr.keyable = True
        nattr.connectable = True
        MPyConstraint.addAttribute(MPyConstraint._targetTranslate_attr)

        # targetRotate (vector input)
        MPyConstraint._targetRotate_attr = nattr.createPoint("targetRotate", "tro")
        nattr.storable = True
        nattr.keyable = True
        nattr.connectable = True
        MPyConstraint.addAttribute(MPyConstraint._targetRotate_attr)

        # targetWeight (float input, default 1.0)
        MPyConstraint._targetWeight_attr = nattr.create(
            "targetWeight", "twg", om.MFnNumericData.kFloat, 1.0
        )
        nattr.storable = True
        nattr.keyable = True
        nattr.connectable = True
        MPyConstraint.addAttribute(MPyConstraint._targetWeight_attr)

        # restTranslate (vector input)
        MPyConstraint._restTranslate_attr = nattr.createPoint("restTranslate", "rtr")
        nattr.storable = True
        nattr.keyable = True
        nattr.connectable = True
        MPyConstraint.addAttribute(MPyConstraint._restTranslate_attr)

        # restRotate (vector input)
        MPyConstraint._restRotate_attr = nattr.createPoint("restRotate", "rro")
        nattr.storable = True
        nattr.keyable = True
        nattr.connectable = True
        MPyConstraint.addAttribute(MPyConstraint._restRotate_attr)

    def setDependentsDirty(self, plug, affected_plugs):
        """Mark all USER outputs dirty when a USER input, the expression, or
        any of the 5 preset constraint inputs changes.

        Routed through the shared :func:`dirty_affects.declare_user_affects`
        helper (``extra_trigger_names`` carries the preset inputs) so this
        body cannot re-introduce the super-return bug."""
        from mpynode._common.plugs import dirty_affects

        dirty_affects.declare_user_affects(
            self.thisMObject(),
            plug,
            affected_plugs,
            type(self)._input_attrs_attr,
            type(self)._output_attrs_attr,
            expression_attr=type(self)._expression_attr,
            extra_trigger_names=_PRESET_INPUT_NAMES,
        )
        return None

    def compute(self, plug, data_block):
        """Override compute to also expose preset constraint inputs in
        the expression namespace, then call the parent MPyNode compute
        for the user expression itself."""
        # Defer evaluation while a scene is being READ / OPENED -- the
        # Evaluation Manager can pull an output mid-load, before this
        # node's dynamic attrs / schema plugs are restored, which makes
        # the user expression raise a spurious "self has no plug named
        # ..." error. Recomputed normally once the scene is whole.
        try:
            import maya.OpenMaya as _om1

            if _om1.MFileIO.isReadingFile():
                return
        except Exception:
            pass

        # The preset attrs are not USER inputs (absent from the _inputAttrs
        # JSON), so the parent compute path can't supply them. They are read
        # here and injected into exec_locals inline.

        try:
            attr_obj = plug.attribute()
            attr_fn = om.MFnAttribute(attr_obj)
            out_name = attr_fn.name
        except Exception:
            return

        # Parent MPyNode.compute logic + preset inputs:
        from mpynode._common.io import serialization
        from mpynode._common.storedvars import stored_var_store as _svstore
        from mpynode._common.compute.expression import (
            build_exec_namespace,
            exec_with_profile_watch,
        )

        node_obj = self.thisMObject()
        fn_node = om.MFnDependencyNode(node_obj)

        try:
            outputs_str = fn_node.findPlug(
                MPyConstraint._output_attrs_attr, True
            ).asString()
            output_map = (
                serialization.decode_attr_map(outputs_str) if outputs_str else {}
            )
        except Exception:
            output_map = {}

        if out_name not in output_map:
            return

        # USER inputs from JSON map.
        try:
            inputs_str = fn_node.findPlug(
                MPyConstraint._input_attrs_attr, True
            ).asString()
            input_map = serialization.decode_attr_map(inputs_str) if inputs_str else {}
        except Exception:
            input_map = {}
        # Pass the data_block so geometry inputs are pulled EM-safely
        # (evaluating any upstream deformer); without it plug.asMObject() inside
        # compute() returns rest/stale geometry.
        #
        # ``geom_data_out`` collects the raw geometry DATA MObjects. Live
        # component-tag reads MUST resolve membership off THIS object: on an EM
        # worker thread every side-channel plug read returns empty, so the tag
        # helper would see zero members, emit an identity fit, and every riveted
        # transform would snap to 0,0,0 on scrub.
        geom_data_map: dict = {}
        input_values = helpers.read_user_inputs_dict(
            node_obj, input_map, data_block=data_block, geom_data_out=geom_data_map
        )

        import numpy as _np

        # The preset inputs ride through PlugProxy + CompoundPlugProxy
        # .asNumpy() -- the same path ``self.X`` uses -- pre-populated as
        # compute_locals slots so the "numerical -> numpy" contract holds. They
        # used to be read via ``cmds.getAttr``, the DG-re-entry anti-pattern
        # already eliminated from the PlugProxy read path.
        #
        # PlugProxy is api1-based and ``node_obj`` is api2, so route through
        # ``_api1_mobject`` to keep the resolve cached across compute calls
        # instead of running MSelectionList.add every tick.
        from mpynode._common.plugs.plug_proxy import PlugProxy

        pp_node_obj_api1 = self._api1_mobject(fn_node.name())

        if pp_node_obj_api1 is not None and not pp_node_obj_api1.isNull():
            # data_block is api2 here and PlugProxy expects api1, so pass None
            # and let PlugProxy use its plug-side path (plug.asXXX first).
            pp = PlugProxy(pp_node_obj_api1, datablock=None)
            preset_internals: dict = {
                "targetTranslate": _read_double3_via_plug(pp, "targetTranslate"),
                "targetRotate": _read_double3_via_plug(pp, "targetRotate"),
                "restTranslate": _read_double3_via_plug(pp, "restTranslate"),
                "restRotate": _read_double3_via_plug(pp, "restRotate"),
            }
            try:
                preset_internals["targetWeight"] = float(
                    getattr(pp, "targetWeight")
                )
            except Exception:
                preset_internals["targetWeight"] = 1.0
        else:
            # Fallback for the unlikely case the api1 bridge failed.
            preset_internals = {
                "targetTranslate": _np.zeros(3, dtype=_np.float64),
                "targetRotate": _np.zeros(3, dtype=_np.float64),
                "restTranslate": _np.zeros(3, dtype=_np.float64),
                "restRotate": _np.zeros(3, dtype=_np.float64),
                "targetWeight": 1.0,
            }

        # ``preset_internals`` becomes the compute_locals dict; the user
        # expression reads its entries via ``self.X``.
        from mpynode._common.compute.self_proxy import SelfProxy

        # Read stored variables for self.X access.
        stored_vars = {}
        try:
            sv_str = fn_node.findPlug(
                MPyConstraint._stored_vars_data_attr, True
            ).asString()
            stored_vars = _svstore.load_for_compute(node_obj, sv_str)
        except Exception:
            stored_vars = {}

        # Pre-seed every USER output BEFORE constructing the SelfProxy: it
        # snapshots ``_psp_compute_local_keys`` from ``compute_locals.keys()``
        # at construction, so a key added later is not recognised by
        # ``__setattr__`` and falls through to the plug-write path, which
        # crashes on the api1/api2 mismatch. ``None`` is a valid default -- the
        # harvest loop skips outputs the expression didn't write.
        import numpy as _np  # noqa: F401 (kept for downstream use)
        from mpynode._common.compute.output_defaults import output_default

        _fn_out = om.MFnDependencyNode(node_obj)
        for out_attr_name, meta in output_map.items():
            attr_type = meta.get("attr_type", "float")
            is_array = bool(meta.get("is_array", False))
            # ARRAY outputs seed a PRE-SIZED (N, ...) buffer so the user can
            # slice-assign in place (e.g. ``self.outMatrix[:, 3, :3] = ...``).
            # N = the output multi's connected element span.
            n = 0
            if is_array:
                try:
                    oplug = _fn_out.findPlug(out_attr_name, True)
                    idxs = list(oplug.getExistingArrayAttributeIndices())
                    n = (max(idxs) + 1) if idxs else 0
                except Exception:
                    n = 0
            preset_internals[out_attr_name] = output_default(
                attr_type, is_array, n
            )

        # Seed the USER INPUTS (already read EM-safely above) into compute_locals
        # so ``self.<input>`` resolves from this snapshot (Tier 1) instead of a
        # LIVE api1 plug lookup. That lookup needs an api1 MObject, but under
        # the EM compute() runs on a worker thread where
        # ``_ensure_api1_mobject`` bails (MFnDependencyNode / MSelectionList are
        # not thread-safe) and returns the api2 MObject unchanged -- so api1
        # PlugProxy can't see the dynamic addAttr inputs and raises "self has no
        # plug named 'meshOrig'", the constraint emits an identity outMatrix,
        # and every riveted transform snaps to 0,0,0 on scrub. Reading inputs
        # once up front via the datablock removes that race, exactly as base
        # MPyNode.compute() does. preset_internals wins on a name collision.
        merged_locals = dict(input_values)
        merged_locals.update(preset_internals)
        # Reserved slot: EM-safe geometry DATA MObjects keyed by input name.
        # Read by ``component_tags._live_mesh_data_for_self`` to resolve live
        # component-tag membership without any side-channel plug read.
        if geom_data_map:
            merged_locals["_mpy_geom_data"] = geom_data_map

        self_proxy = SelfProxy(
            node_obj,
            datablock=data_block,
            user_storage=stored_vars,
            compute_locals=merged_locals,
            node_type_label=type(self).__name__,
        )

        # Self-only: USER inputs are reached via self.X (live plug tree), NOT
        # as bare names.
        namespace = build_exec_namespace()  # __builtins__ only
        namespace["self"] = self_proxy

        # Sync compiled code with the _computeSource plug so a DUPLICATED
        # node runs its expression (see helpers.ensure_expr_code).
        helpers.ensure_expr_code(self, type(self)._expression_attr)

        if self._expr_code is not None:
            # Capture stderr from the expression and broadcast it to the UI
            # Log panel via the Qt-free log_bus.
            captured: list[str] = []

            def _on_err(msg):
                captured.append(msg)

            ok = exec_with_profile_watch(
                self._expr_code,
                namespace,
                on_error=_on_err,
                node_obj=node_obj,
            )
            if not ok and captured:
                # Base-contract policy (C10): suppress the benign transient
                # missing-plug error (declared-but-unresolved plug pulled mid
                # scene-load), surface everything else.
                from mpynode._common.compute.base_contract import broadcast_compute_error

                broadcast_compute_error(
                    "mPyConstraint",
                    captured[0],
                    declared_names=set(input_map) | set(output_map),
                )

        # Harvest every declared user output from the compute_locals snapshot
        # (``self.X = value`` in the expression) and commit it to the data block
        # via the type-aware helpers.
        locals_out = self_proxy.get_compute_locals()
        for out_attr_name, meta in output_map.items():
            # Self-only: an output is committed only when the expression
            # assigns ``self.out = ...``. Bare assignments are NOT harvested.
            if out_attr_name in locals_out:
                value = locals_out[out_attr_name]
            else:
                continue
            if value is None:
                # User did not write to this output; skip.
                continue
            try:
                attr = fn_node.findPlug(out_attr_name, True).attribute()
                attr_type = meta.get("attr_type", "float")
                if bool(meta.get("is_array", False)):
                    helpers.write_multi_plug_value(
                        data_block,
                        attr,
                        attr_type,
                        value,
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

        # commit stored-var changes via SelfProxy diff.
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
