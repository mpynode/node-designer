"""MPyBlendShape (API 1.0) -- expression-driven custom blendShape.

Compute is collapsed onto :func:`run_generic_compute`. The
``INTERNAL_VARS`` schema and ``_run_expression`` are gone. Target
geometry, weights, and weight maps now reach the user expression
through the plug tree.

User expression namespace (contract -- access via ``self.X``):

 * ``self.outputGeometry[i]`` -- writable MFn handle.
 * ``self.input[i].inputGeometry`` -- read-only MFn handle.
 * ``self.envelope`` -- float, inherited.
 * ``self.targetGeometry[j]`` -- read-only ``MFnMesh`` of the j-th
 connected target shape (a flat mesh-data multi declared in
 ``node_initializer`` -- NOT Maya's native nested
 ``inputTarget[].inputTargetGroup[]...`` tree).
 * ``self.weight[j]`` -- float per-target weight, ALIASED to the target
 name exactly like a stock blendShape (``bs.browUp`` == ``bs.weight[0]``).
 Added per node by ``MPyBlendShape.create`` as a user input attr, not
 declared here -- see the note in ``node_initializer``.

``weight`` is NOT a reserved name (an earlier docstring here claimed it
was). Verified against Maya 2026: long ``weight`` + short ``w`` does fail,
because ``w`` is taken by the inherited ``weightList[].weights`` child, but
``weight`` with any other short name registers fine -- and a user attr gets
short name ``weight``, so it never collides.

NOTE: ``mPyBlendShape`` inherits from ``MPxDeformerNode``, and NOT because
``MPxBlendShape`` is missing. An earlier note here said that base existed
only in API 2.0 and was unavailable in this build. That is INVERTED:
``maya.OpenMayaMPx.MPxBlendShape`` exists on both Maya 2024 and 2026, and
API 2.0 has no ``MPxBlendShape`` at all (``MPxNode.kBlendShape == 25`` on
both). Staying on ``MPxDeformerNode`` is a deliberate choice. Measured
against a probe node registered ``kBlendShape`` on both Mayas:

 * It stops deforming. ``MPxBlendShape`` never calls ``deform()`` -- it
   routes to ``deformData(block, handle, geomIndex, matrix, multiIndex)``.
   With only ``deform()`` overridden the node raises ``kNotImplemented``
   and leaves the geometry untouched.
 * ``weight[]`` stops being a user attr. Registering ``kBlendShape`` makes
   the node inherit the native ``weight[]`` (short name ``w``), so
   ``addAttr -ln weight -at float -multi`` fails with "Found no valid items
   to add the attribute to". ``_ensure_weight_attr`` guards on ``_has_attr``,
   which is now True, so it SILENTLY skips -- ``weight`` never reaches
   ``_inputAttrs`` or the compile spec, i.e. a compiled node with no weights.
 * Existing scenes fail QUIETLY. A scene saved on this base and reopened on
   ``kBlendShape`` still opens and its aliases still read back, but ``weight``
   drops out of ``listAttr(userDefined=True)`` and the node stops deforming.
 * The compile path is hard-gated to this base in three places:
   ``nd_lower.lower_deform`` raises ``UnsupportedSpec`` for any base outside
   ``("MPxDeformerNode", "MPxSkinCluster")``, ``emit_deformer._DEFORMER_BASES``
   is the same pair, and ``spec_extractor`` maps ``mPyBlendShape`` ->
   ``MPxDeformerNode``.
 * On Maya 2024 the re-based node is additionally NOT a
   ``weightGeometryFilter``, so it also loses ``weightList[].weights`` --
   painted per-vertex deformer weights.

MTypeId 0x0013571C.
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
    "_outputAttrs", "targetGeometry", "liveTargets",
))


class MPyBlendShape(ommpx.MPxDeformerNode):
    NODE_NAME = "mPyBlendShape"
    NODE_ID   = om.MTypeId(0x0013571C)

    INPUT_GEOMETRY_PLUG             = "input[multi_index].inputGeometry"
    OUTPUT_GEOMETRY_PLUG            = "outputGeometry[multi_index]"
    OUTPUT_GEOMETRY_PLUG_SHORT_NAME = "outputGeometry"

    _expression_attr       = None
    _input_attrs_attr      = None
    _output_attrs_attr     = None
    _stored_vars_list_attr = None
    _stored_vars_data_attr = None
    _debug_mode_attr       = None

    def __init__(self):
        super().__init__()
        self._expr_str: str = ""
        self._expr_code = compile_expression("")

    @staticmethod
    def node_creator():
        return ommpx.asMPxPtr(MPyBlendShape())

    @staticmethod
    def node_initializer():
        plugs                                = helpers.build_internal_attrs(MPyBlendShape)
        MPyBlendShape._expression_attr       = plugs["_computeSource"]
        MPyBlendShape._input_attrs_attr      = plugs["inputs"]
        MPyBlendShape._output_attrs_attr     = plugs["outputs"]
        MPyBlendShape._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyBlendShape._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyBlendShape._debug_mode_attr       = plugs["debug_mode"]

        # MPxDeformerNode does NOT provide blendShape target plugs -- the
        # native ``inputTarget[].inputTargetGroup[]...`` tree only exists on
        # Maya's built-in blendShape. Flat surface instead: ``targetGeometry[]``
        # here (a mesh multi -- a CONNECTION, which only a static typed attr can
        # be), and ``weight[]`` added per node by ``MPyBlendShape.create``.
        #
        # ``weight[]`` is NOT declared here because the compile spec reaches a
        # static plug only through the PRESET path, and preset meta carries no
        # ``is_array`` -- a static multi cannot ride it, so the compiled node
        # would have no weights. As a user attr it is captured and re-declared
        # for free. Aliasing works either way (verified: aliasAttr on a DYNAMIC
        # multi element sets/gets, shows in the channel box under the alias, and
        # survives a .ma round-trip via ``attributeAliasList``).

        # targetGeometry[] -- mesh-data multi, one element per target.
        # Connection-driven, so not storable: the connection is saved,
        # not a copy of the mesh data.
        t_attr = om.MFnTypedAttribute()
        target_geo_attr = t_attr.create(
            "targetGeometry", "tgeo", om.MFnData.kMesh
        )
        t_attr.setArray(True)
        t_attr.setReadable(True)
        t_attr.setWritable(True)
        t_attr.setStorable(False)
        t_attr.setKeyable(False)
        t_attr.setCached(True)
        t_attr.setHidden(False)
        # NOT wrapped in a bare ``except: pass``. A short-name collision makes
        # addAttribute throw, and swallowing it registers a node with no target
        # surface at all -- surfacing much later as "the blend shape does
        # nothing".
        MPyBlendShape.addAttribute(target_geo_attr)

        # liveTargets -- follow the CONNECTED target meshes live, so sculpting a
        # target reaches the deform immediately (construction history). ON by
        # default: that is the behaviour this plug exists to expose, not to
        # withhold, and a node saved before it existed reads live too.
        #
        # Switch it OFF to pin the deform to the BAKED tables. Two reasons to:
        # deltas that were edited by hand or loaded from a file while the target
        # mesh is still connected (live would override them), and a rig posed
        # with enough targets dialled in at once that reading them all costs
        # more than the immediacy is worth -- interpreted skips a zero-weight
        # target, so this only bites when many are non-zero together.
        #
        # A COMPILED node reads every connected target instead: the emitted
        # prologue runs before the effective weights exist, so it has nothing to
        # test. Same result either way (a zero-weight slot contributes 0.0 from
        # the live table or the bake), but the cost does not fall off with the
        # pose, which makes this gate worth more on a compiled rig than here.
        n_attr = om.MFnNumericAttribute()
        live_attr = n_attr.create("liveTargets", "ltgt",
                                  om.MFnNumericData.kBoolean, True)
        n_attr.setStorable(True)
        n_attr.setKeyable(False)
        n_attr.setHidden(False)
        MPyBlendShape.addAttribute(live_attr)

        # Dirty propagation for targetGeometry[] and liveTargets. ``weight[]``
        # and the derived tables are USER attrs, so they reach
        # setDependentsDirty's trigger set via the decoded _inputAttrs map
        # instead.
        try:
            output_attr = ommpx.cvar.MPxGeometryFilter_outputGeom
            MPyBlendShape.attributeAffects(target_geo_attr, output_attr)
            MPyBlendShape.attributeAffects(live_attr, output_attr)
        except Exception:
            pass

    def setInternalValueInContext(self, plug, data_handle, _ctx):
        try:
            attr = plug.attribute()
            if attr == MPyBlendShape._expression_attr:
                data           = om.MFnStringData(data_handle.data())
                self._expr_str = data.string()
                from mpynode._common.compute.expression import safe_compile_expression

                node_name = ""
                try:
                    node_name = om.MFnDependencyNode(self.thisMObject()).name()
                except Exception:
                    pass
                code = safe_compile_expression(
                    self._expr_str,
                    node_name = node_name,
                    filename  = "<mpyblendshape-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        return False

    def setDependentsDirty(self, plug, affected_plugs):
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
            output_attr       = ommpx.cvar.MPxGeometryFilter_outputGeom
            node_obj          = self.thisMObject()
            fn_node           = om.MFnDependencyNode(node_obj)
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
        try:
            ok = run_generic_compute(
                self.thisMObject(),
                block,
                geom_iter=geom_iter,
                multi_index=int(multi_index),
                output_plug_short_name=self.OUTPUT_GEOMETRY_PLUG_SHORT_NAME,
                family="deformer",
                # Reconcile the cached code with the live _computeSource
                # plug so a DUPLICATED blendShape runs its expression (C8).
                expression_code=helpers.ensure_expr_code(self),
            )
            if not ok:
                return None
        except Exception as exc:
            sys.stderr.write(
                "[mPyBlendShape.deform] {}: {}\n".format(
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
    """Touch envelope on every mPyBlendShape so the deformer re-evals
    across frame changes.

    When envelope has an incoming connection (animCurve, driven), a
    ``setAttr`` is blocked; in that case fall back to ``dgdirty`` +
    an ``outputGeometry`` query to force the deformer to re-eval.
    """
    try:
        from maya import cmds

        for node in cmds.ls(type=MPyBlendShape.NODE_NAME) or []:
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
            "[mPyBlendShape] failed to register time-change callback: {{}}\n".format(exc)
        )
        return -1
