"""MPyDeformer (API 1.0) -- expression-driven custom deformer.

The entire compute path is reduced to a single call into
``mpynode._common.compute.compute.run_generic_compute(...)``. The legacy
``INTERNAL_VARS`` schema, ``_run_expression``, and
``_do_deform_via_hooks`` paths are gone.

User expression namespace (contract -- access via ``self.X``):

 * ``self.outputGeometry[i]`` -- writable ``MFnMesh`` (eager-copied
 from the corresponding input). Mutate
 it via ``setPoints(...)`` or any other
 MFnMesh method; the bridge commits on
 compute exit. ``getPoints()`` returns
 ``(N, 3) float64`` numpy.
 * ``self.input[i].inputGeometry`` -- read-only MFnMesh of the upstream
 source.
 * ``self.envelope`` -- float, read-write (writable plug).
 * Anything else NOT a plug -- routes to user storage (the old
 ``self.foo = 1`` pattern still works
 for storing per-node Python state).

The 5 internal-vars schema (``self.points`` / ``self.normals`` /
``self.weights`` / ``self.deformed`` etc.) was deleted. Migration
guide in

 mesh = self.outputGeometry[0]
 pts = mesh.getPoints() # (N, 3) float64 numpy
 pts[:, 1] += amplitude
 mesh.setPoints(pts)
"""

from __future__ import annotations

import sys

import maya.OpenMaya as om
import maya.OpenMayaMPx as ommpx

from mpynode._api1 import helpers
from mpynode._common.compute.compute import run_generic_compute
from mpynode._common.compute.expression import compile_expression
from mpynode._common.plugs import dirty_affects as _dirty_affects


# The non-user plugs whose change re-dirties the output. User inputs come off
# _inputAttrs through dirty_affects.api1_dirty_gate, cached on the instance.
_STATIC_TRIGGERS = frozenset((
    "_computeSource", "envelope", "_storedVarsData", "_inputAttrs",
    "_outputAttrs",
))


class MPyDeformer(ommpx.MPxDeformerNode):
    NODE_NAME = "mPyDeformer"
    NODE_ID = om.MTypeId(0x00135716)

    # per-node-type plug-tree spec.
    INPUT_GEOMETRY_PLUG = "input[multi_index].inputGeometry"
    OUTPUT_GEOMETRY_PLUG = "outputGeometry[multi_index]"
    OUTPUT_GEOMETRY_PLUG_SHORT_NAME = "outputGeometry"

    _expression_attr = None
    _input_attrs_attr = None
    _output_attrs_attr = None
    _stored_vars_list_attr = None
    _stored_vars_data_attr = None
    _debug_mode_attr = None

    def __init__(self):
        super().__init__()
        self._expr_str: str = ""
        self._expr_code = compile_expression("")

    @staticmethod
    def node_creator():
        return ommpx.asMPxPtr(MPyDeformer())

    @staticmethod
    def node_initializer():
        plugs = helpers.build_internal_attrs(MPyDeformer)
        MPyDeformer._expression_attr = plugs["_computeSource"]
        MPyDeformer._input_attrs_attr = plugs["inputs"]
        MPyDeformer._output_attrs_attr = plugs["outputs"]
        MPyDeformer._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyDeformer._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyDeformer._debug_mode_attr = plugs["debug_mode"]

        # NOTE: ``envelope`` is INHERITED from ``geometryFilter``
        # (MPxDeformerNode auto-provides it with input[]/outputGeometry[]).
        # Don't re-add it.

    def setInternalValueInContext(self, plug, data_handle, _ctx):
        try:
            attr = plug.attribute()
            if attr == MPyDeformer._expression_attr:
                data = om.MFnStringData(data_handle.data())
                self._expr_str = data.string()
                from mpynode._common.compute.expression import safe_compile_expression

                node_name = ""
                try:
                    node_name = om.MFnDependencyNode(self.thisMObject()).name()
                except Exception:
                    pass
                code = safe_compile_expression(
                    self._expr_str,
                    node_name=node_name,
                    filename="<mpydeformer-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        return False

    def setDependentsDirty(self, plug, affected_plugs):
        """Mark the inherited ``outputGeom`` plug dirty whenever any of
        our nodes-control inputs change.

        MPxDeformerNode auto-propagates dirtiness only for its own
        declared input attrs. Our user-driven attrs (expression,
        envelope, _storedVarsData, _inputAttrs/_outputAttrs, plus
        any user-added input attr) don't reach the output without
        this override.
        """
        try:
            plug_name = om.MFnAttribute(plug.attribute()).name()
        except Exception:
            return
        # The hot path: ~3,800 calls a frame on the Combo Correctives demo. A
        # SUSPENDED node (nodeState Has No Effect / Blocking -- Convert to C++
        # sets it, a user may too) forwards nothing; a live one gets its user
        # input names off the instance cache. No plug is read here.
        user_inputs = _dirty_affects.api1_dirty_gate(self, plug_name)
        if user_inputs is None:
            return
        if plug_name not in _STATIC_TRIGGERS and plug_name not in user_inputs:
            return

        try:
            output_attr = ommpx.cvar.MPxGeometryFilter_outputGeom
            node_obj = self.thisMObject()
            fn_node = om.MFnDependencyNode(node_obj)
            output_array_plug = fn_node.findPlug(output_attr, True)
            for i in range(output_array_plug.numElements()):
                element_plug = output_array_plug.elementByPhysicalIndex(i)
                affected_plugs.append(element_plug)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # MPxDeformerNode override
    # ------------------------------------------------------------------

    def deform(self, block, geom_iter, _world_matrix, multi_index):
        """Deform the input mesh.

        this method is now a thin wrapper around:func:`mpynode._common.compute.compute.run_generic_compute`. The 800
        lines of legacy compute scaffolding (``_run_expression``,
        ``_do_deform_via_hooks``, paint-weight reads, normal
        precomputation, etc.) collapsed into a single generic call.

        Failure mode: if the user expression raises, the generic
        compute returns False; Maya gets the input mesh unchanged
        (the eager-copy happens BEFORE exec, so the output handle
        was already seeded from input).
        """
        try:
            ok = run_generic_compute(
                self.thisMObject(),
                block,
                geom_iter=geom_iter,
                multi_index=int(multi_index),
                output_plug_short_name=self.OUTPUT_GEOMETRY_PLUG_SHORT_NAME,
                family="deformer",
                # Reconcile the cached code with the live _computeSource plug
                # so a DUPLICATED deformer -- Maya copies the plug across
                # WITHOUT routing through setInternalValue -- runs its
                # expression instead of silently no-opping (C8).
                expression_code=helpers.ensure_expr_code(self),
            )
            if not ok:
                return None
        except Exception as exc:
            sys.stderr.write(
                "[mPyDeformer.deform] {}: {}\n".format(
                    type(exc).__name__, exc
                )
            )
            import traceback
            traceback.print_exc(file=sys.stderr)
        return None


# ===========================================================================
# Process-wide time-change callback
# ===========================================================================


def _on_time_change(_unused_client_data):
    """Touch envelope on every mPyDeformer so deformer re-evals across
    frame changes.

    When envelope has an incoming connection (animCurve from a
    keyframe, a driven connection, etc.), ``setAttr`` is blocked.
    In that case fall back to ``dgdirty`` + a query against
    ``outputGeometry`` to force the deformer to re-eval anyway.
    """
    try:
        from maya import cmds

        for node in cmds.ls(type=MPyDeformer.NODE_NAME) or []:
            try:
                # A suspended node -- converted to C++, or Has No Effect /
                # Blocking by hand -- has nothing to re-evaluate; touching it
                # only re-dirties a node the Evaluation Manager would then
                # evaluate for nothing.
                if cmds.getAttr(node + ".nodeState"):
                    continue
                env = cmds.getAttr(node + ".envelope")
                cmds.setAttr(node + ".envelope", env)
            except Exception:
                try:
                    cmds.dgdirty(node + ".outputGeometry")
                    cmds.getAttr(node + ".outputGeometry[0]")
                except Exception:
                    pass
    except Exception:
        pass


def register_time_change_callback() -> int:
    """Install the time-change callback; tracked via CALLBACK_MANAGER."""
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_API1

        cb_id = om.MEventMessage.addEventCallback("timeChanged", _on_time_change)
        return CALLBACK_MANAGER.register(cb_id, om.MMessage.removeCallback, OWNER_API1)
    except Exception as exc:
        sys.stderr.write(
            "[mPyDeformer] failed to register time-change callback: {}\n".format(exc)
        )
        return -1
