"""MPySkinCluster (API 1.0) -- expression-driven custom skinCluster.

Compute is collapsed onto :func:`run_generic_compute`. The
``INTERNAL_VARS`` schema, ``_run_expression``, and weight/joint
densification are gone -- the user expression now reaches
joints/weights/bind matrices through the plug tree instead.

User expression namespace (contract -- access via ``self.X``):

 * ``self.outputGeometry[i]`` -- writable MFn handle.
 * ``self.input[i].inputGeometry`` -- read-only MFn handle.
 * ``self.envelope`` -- float, inherited.
 * ``self.matrix[j]`` -- (4, 4) numpy via MatrixView
 (joint world matrix).
 * ``self.bindPreMatrix[j]`` -- (4, 4) numpy via MatrixView.
 * ``self.weightList[i].weights`` -- sparse weight read.

A linear-blend skin in this namespace looks like::

 import numpy as np
 mesh = self.outputGeometry[0]
 pts = mesh.getPoints() # (N, 3) float64
 # User chooses how to assemble joint matrices and weights via
 # the plug tree -- exact code depends on the rig.
 mesh.setPoints(pts)

MTypeId 0x0013571B.
"""

from __future__ import annotations

import sys

import maya.OpenMaya as om
import maya.OpenMayaMPx as ommpx

from mpynode._api1 import helpers
from mpynode._common.compute.compute import run_generic_compute
from mpynode._common.compute.expression import compile_expression


class MPySkinCluster(ommpx.MPxSkinCluster):
    NODE_NAME = "mPySkinCluster"
    NODE_ID = om.MTypeId(0x0013571B)

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
        return ommpx.asMPxPtr(MPySkinCluster())

    @staticmethod
    def node_initializer():
        plugs = helpers.build_internal_attrs(MPySkinCluster)
        MPySkinCluster._expression_attr = plugs["_computeSource"]
        MPySkinCluster._input_attrs_attr = plugs["inputs"]
        MPySkinCluster._output_attrs_attr = plugs["outputs"]
        MPySkinCluster._stored_vars_list_attr = plugs["stored_vars_list"]
        MPySkinCluster._stored_vars_data_attr = plugs["stored_vars_data"]
        MPySkinCluster._debug_mode_attr = plugs["debug_mode"]

        # matrix[] / bindPreMatrix[] declarations.
        #
        # Under kSkinCluster (the normal path, see plug-ins/mpynode_api1.py)
        # the C++ base already provides matrix[], bindPreMatrix[] and
        # weightList, so these addAttribute() calls are redundant and Maya
        # raises a duplicate-name error the try/except swallows on purpose.
        # Retained for the DEFENSIVE kDeformerNode fallback: a plain deformer
        # base does NOT provide them, and joint wiring needs matrix[].
        m_attr = om.MFnMatrixAttribute()
        matrix_attr = m_attr.create("matrix", "matrix", om.MFnMatrixAttribute.kFloat)
        m_attr.setArray(True)
        m_attr.setKeyable(False)
        m_attr.setStorable(True)
        m_attr.setReadable(True)
        m_attr.setWritable(True)
        m_attr.setCached(True)
        m_attr.setHidden(False)
        try:
            MPySkinCluster.addAttribute(matrix_attr)
        except Exception:
            pass

        bp_attr_fn = om.MFnMatrixAttribute()
        bind_pre_attr = bp_attr_fn.create(
            "bindPreMatrix", "pm", om.MFnMatrixAttribute.kFloat
        )
        bp_attr_fn.setArray(True)
        bp_attr_fn.setKeyable(False)
        bp_attr_fn.setStorable(True)
        bp_attr_fn.setReadable(True)
        bp_attr_fn.setWritable(True)
        bp_attr_fn.setCached(True)
        bp_attr_fn.setHidden(False)
        try:
            MPySkinCluster.addAttribute(bind_pre_attr)
        except Exception:
            pass

        # Changes to matrix[] / bindPreMatrix[] mark outputGeom dirty.
        try:
            output_attr = ommpx.cvar.MPxGeometryFilter_outputGeom
            MPySkinCluster.attributeAffects(matrix_attr, output_attr)
            MPySkinCluster.attributeAffects(bind_pre_attr, output_attr)
        except Exception:
            pass

    def setInternalValueInContext(self, plug, data_handle, _ctx):
        try:
            attr = plug.attribute()
            if attr == MPySkinCluster._expression_attr:
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
                    filename="<mpyskincluster-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        return False

    def setDependentsDirty(self, plug, affected_plugs):
        """Mark outputGeom dirty whenever user-driven inputs change."""
        try:
            attr_obj = plug.attribute()
            attr_fn = om.MFnAttribute(attr_obj)
            plug_name = attr_fn.name()
        except Exception:
            return

        triggers = {
            "_computeSource",
            "envelope",
            "_storedVarsData",
            "_inputAttrs",
            "_outputAttrs",
            "matrix",
            "bindPreMatrix",
            "weightList",
            # A weightList[v].weights[j] child edit (Component Editor /
            # Paint Skin Weights) reports the attr name 'weights'.
            "weights",
        }
        # Memoized on the raw _inputAttrs string: Maya re-enters this override
        # several times per plug write and the json decode was re-run every
        # time. Falls back to the static literals above on any failure, exactly
        # as the inline decode did.
        try:
            from mpynode._common.plugs import dirty_affects as _dirty_affects

            triggers.update(
                _dirty_affects.api1_user_input_names(self.thisMObject()))
        except Exception:
            pass
        if plug_name not in triggers:
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
    # MPxSkinCluster override
    # ------------------------------------------------------------------

    def deform(self, block, geom_iter, _world_matrix, multi_index):
        """Thin wrapper around:func:`run_generic_compute`."""
        try:
            ok = run_generic_compute(
                self.thisMObject(),
                block,
                geom_iter=geom_iter,
                multi_index=int(multi_index),
                output_plug_short_name=self.OUTPUT_GEOMETRY_PLUG_SHORT_NAME,
                family="deformer",
                # Reconcile the cached code with the live _computeSource
                # plug so a DUPLICATED skinCluster runs its expression (C8).
                expression_code=helpers.ensure_expr_code(self),
            )
            if not ok:
                return None
        except Exception as exc:
            sys.stderr.write(
                "[mPySkinCluster.deform] {}: {}\n".format(
                    type(exc).__name__, exc
                )
            )
            import traceback
            traceback.print_exc(file=sys.stderr)
        return None


# ===========================================================================
# Process-wide time-change callback.
# ===========================================================================


def _on_time_change(_unused_client_data):
    """Touch envelope on every mPySkinCluster so the deformer re-evals
    across frame changes.

    When envelope has an incoming connection (animCurve, driven), a
    ``setAttr`` is blocked; in that case fall back to ``dgdirty`` +
    an ``outputGeometry`` query to force the deformer to re-eval.
    """
    try:
        from maya import cmds

        for node in cmds.ls(type=MPySkinCluster.NODE_NAME) or []:
            try:
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
            "[mPySkinCluster] failed to register time-change callback: {{}}\n".format(exc)
        )
        return -1
