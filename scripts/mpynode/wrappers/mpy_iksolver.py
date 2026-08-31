"""User-facing wrapper for the mPyIkSolver plug-in.

Custom IK solver workflow::

 from mpynode.wrappers.mpy_iksolver import MPyIkSolver

 # Create joints + IK handle pinned to mPyIkSolver
 root = mc.joint(name="rootJ", position=(0, 0, 0))
 tip = mc.joint(name="tipJ", position=(5, 0, 0))
 handle, effector = mc.ikHandle(
 startJoint=root, endEffector=tip, solver="mPyIkSolver"
 )

 # Get the auto-created solver node + set its expression
 solver = MPyIkSolver.find_solver()
 solver.set_compute_expression('''
 # Hand joint i a desired matrix; the bridge applies it via offsetParentMatrix
 # (rotate-only by default), leaving the joint's own channels + jointOrient
 # untouched. WORLD (absolute) frames go to world_matrices; LOCAL
 # (parent-relative) frames go to local_matrices. joints[i]["world_matrix"]
 # (rest world) / joints[i]["matrix"] (local) are MatrixViews to build from.
 self.world_matrices[0] = desired_world_matrix   # 4x4 numpy / MatrixView
 self.apply_rotate = True                               # gate (default r-only)
 ''')

User INPUTS work (read via ``self.X`` inside the solve expression). DG
user OUTPUTS on the solver node itself do NOT compute, though: like
MPxLocatorNode, MPxIkSolverNode does not dispatch ``compute()`` for
runtime-added output plugs (verified Maya 2024 standalone + 2026 GUI;
a plain mPyNode computes, this node never does). That's fine for an IK
solver -- its result is what it writes to each joint's
``offsetParentMatrix`` during ``doSolve`` (the joints' own T/R/S channels
and ``jointOrient`` are never touched), not a DG output plug. For separate
output math, drive a downstream ``mPyNode``.

Known cosmetic warning -- ``swig/python detected a memory leak of
type 'MStatus *', no destructor found.``

Every IK solve dispatch into our Python ``doSolve()`` override leaks
one Maya ``MStatus`` object (~4-8 bytes). The leak is in Autodesk's
api1 SWIG bindings -- the C++ ``MPxIkSolverNode::doSolve()`` returns
``MStatus`` by value, but Python's ``maya.OpenMaya`` module never
exposes the ``MStatus`` class, so SWIG cannot register a destructor
for it. ``MPxTransform`` / ``MPxDeformerNode`` / api2 ``MPxNode`` do
NOT have this issue (verified by bisection).

Impact: the warning is benign (a tiny per-solve overhead reclaimed
on Maya exit) but cosmetically noisy in interactive Maya. There is
no Python-side workaround because ``om.MStatus`` is not accessible
from Python. The leak would only be fixable in Maya's C++ SWIG
bindings.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode.wrappers._mpy_node import MPyNode


_SOLVER_TYPE_NAME = "mPyIkSolver"


class MPyIkSolver(MPyNode):

    # MIkHandleGroup-sourced data from doSolve callback.
    INTERNAL_API_SLOTS = (
        ("joints",              "read",  "list of {'name','world_position','rotation','matrix','world_matrix'} dicts ('matrix'=local, 'world_matrix'=rest world, both MatrixView)"),
        ("end_effector",        "read",  "np.ndarray(3,) float64 -- IK handle world position"),
        ("pole_vector",         "read",  "np.ndarray(3,) float64 -- pole vector"),
        ("twist",               "read",  "float -- handle twist attribute"),
        ("local_matrices",      "write", "list[4x4 or None] -- per-joint desired LOCAL (parent-relative) matrix; applied via offsetParentMatrix"),
        ("world_matrices","write", "list[4x4 or None] -- per-joint desired WORLD (absolute) matrix; applied via offsetParentMatrix. Dispatch: WORLD > LOCAL > rest"),
        ("apply_rotate",        "write", "bool OR list[bool] -- gate: take rotation from the matrix (default True); scalar broadcasts, list is per-joint"),
        ("apply_translate",     "write", "bool OR list[bool] -- gate: take translate from the matrix (default False)"),
        ("apply_scale",         "write", "bool OR list[bool] -- gate: take scale from the matrix (default False)"),
    )
    # Attributes-tab allowlist (framework OFF): the solver's tuning knobs.
    USEFUL_INHERITED_PLUGS = frozenset({"maxIterations", "tolerance"})

    # Wrapper-level API for the API tab (setup / demo / @maya_command bodies);
    # never reachable as ``self.X`` from an expression tier.
    AUTHORING_API = (
        ("find_solver", ""),
        ("rebind", ""),
    )

    NATIVE_TYPE = _SOLVER_TYPE_NAME

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyIkSolver":
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        if name is None:
            name = cls._default_create_name()
        ensure_loaded(cls.NATIVE_TYPE)
        node = mc.createNode(cls.NATIVE_TYPE, name=name,
                             skipSelect=skip_selection)
        return cls._stamp_py_class(cls(node))

    @classmethod
    def find_solver(cls) -> "MPyIkSolver":
        """Return the first existing mPyIkSolver in the scene, creating
        one if none exists yet."""
        existing = mc.ls(type=cls.NATIVE_TYPE) or []
        if existing:
            return cls(existing[0])
        # Funnel through create() so the name derives from the Class
        # (camelCase) like every other create path: mPyIkSolver1 for the root,
        # mySolver1 for a subclass. Never hardcode the literal here.
        return cls.create()

    def rebind(self) -> bool:
        """Clear this solver's captured bind offsets so the NEXT solve
        re-captures the joints' current offsets as the new neutral ('set
        current pose as rest'). Call after intentionally changing the rest
        pose. Returns True if the bind-offset plug was cleared."""
        from mpynode._api1.helpers import rebind_ik_solver

        return rebind_ik_solver(self.get_name())
