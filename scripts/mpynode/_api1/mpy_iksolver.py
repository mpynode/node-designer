"""MPyIkSolver (API 1.0) \u2014 expression-driven custom IK solver.

Inherits from MPxIkSolverNode (NOT exposed in API 2.0, hence API 1).
The Maya IK system calls our ``doSolve()`` method whenever a connected
ikHandle is dirty; we delegate to ``_api1.helpers.compute_ik_doSolve``
which runs the user's Python expression and applies the result to the
joints purely via ``offsetParentMatrix`` -- the joints' own T/R/S channels
and ``jointOrient`` are never touched (the solver owns only the offset).

User expression namespace (reached via ``self.``):
  * ``joints`` \u2014 list of {'name','world_position','rotation','matrix',
    'world_matrix'} per joint; ``matrix`` is the local (parent-relative)
    frame and ``world_matrix`` the REST world frame (both MatrixView, incl.
    the captured bind offset), stable across solves.
  * ``end_effector`` \u2014 numpy (3,) world-space target (the IK handle's
    world position, NOT the effector's).
  * ``pole_vector`` \u2014 numpy (3,) from the handle's poleVector attr
  * ``twist`` \u2014 float from the handle's twist attr
  * ``MatrixView`` \u2014 a matrix builder (setRotation/setTranslation/... in
    RADIANS, chainable, numpy-transparent) for users who don't think in raw
    matrices.
  * ``local_matrices`` (output) \u2014 list[4x4 or None]; a slot drives that
    joint's desired LOCAL (parent-relative) frame.
  * ``world_matrices`` (output) \u2014 list[4x4 or None]; a slot drives that
    joint's desired WORLD (absolute) frame.  Per-joint dispatch is
    WORLD > LOCAL > follow-rest.
  * ``apply_rotate`` / ``apply_translate`` / ``apply_scale`` \u2014 channel gates,
    each a scalar bool (broadcast) OR a per-joint list of bools (default
    rotate-only). Ungated channels come from the joint's rest pose.
"""

from __future__ import annotations

import maya.OpenMaya as om
import maya.OpenMayaAnim as oma  # noqa: F401  (used implicitly via MPxIkSolverNode)
import maya.OpenMayaMPx as ommpx
from mpynode._api1 import helpers
from mpynode._common.compute.expression import compile_expression


class MPyIkSolver(ommpx.MPxIkSolverNode):
    NODE_NAME = "mPyIkSolver"
    NODE_ID = om.MTypeId(0x00135713)

    # Per solve; the expression reaches plug-tree state through ``self.X``.

    _expression_attr = None
    _input_attrs_attr = None
    _output_attrs_attr = None
    _stored_vars_list_attr = None
    _stored_vars_data_attr = None
    _debug_mode_attr = None
    _solver_context_snapshot_attr = None
    _joint_bind_offsets_attr = None

    def __init__(self):
        super().__init__()
        self._expr_str: str = ""
        self._expr_code = compile_expression("")

    @staticmethod
    def node_creator():
        return ommpx.asMPxPtr(MPyIkSolver())

    @staticmethod
    def node_initializer():
        plugs = helpers.build_internal_attrs(MPyIkSolver)
        MPyIkSolver._expression_attr = plugs["_computeSource"]
        MPyIkSolver._input_attrs_attr = plugs["inputs"]
        MPyIkSolver._output_attrs_attr = plugs["outputs"]
        MPyIkSolver._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyIkSolver._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyIkSolver._debug_mode_attr = plugs["debug_mode"]

        # solver context snapshot (JSON written by doSolve).
        MPyIkSolver._solver_context_snapshot_attr = helpers.make_internal_string_attr(
            "_solverContextSnapshot", "_solverContextSnapshot"
        )
        MPyIkSolver.addAttribute(MPyIkSolver._solver_context_snapshot_attr)

        # Per-joint BIND offsets: JSON 16-float rows, positional along the
        # walked chain. Captured on the first solve (pre-writeback) then
        # locked; storable so it survives save/reload. Cleared by a re-bind.
        MPyIkSolver._joint_bind_offsets_attr = helpers.make_internal_string_attr(
            "_jointBindOffsets", "_jointBindOffsets"
        )
        MPyIkSolver.addAttribute(MPyIkSolver._joint_bind_offsets_attr)

    def setInternalValueInContext(self, plug, data_handle, _ctx):
        try:
            attr = plug.attribute()
            if attr == MPyIkSolver._expression_attr:
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
                    filename="<mpyiksolver-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # MPxIkSolverNode overrides
    # ------------------------------------------------------------------

    def solverTypeName(self):
        return "mPyIkSolver"

    def doSolve(self):
        """Maya calls this when the connected IK handle needs to solve.
        We delegate to the bridge which runs the user expression."""
        helpers.compute_ik_doSolve(self)

    def isSingleChainOnly(self):
        return False

    def positionOnly(self):
        return False

    def hasJointLimitSupport(self):
        return False

    def hasUniqueSolution(self):
        return True

    def groupHandlesByTopology(self):
        return False

    def funcValueTolerance(self):
        return 0.001

    def maxIterations(self):
        return 1
