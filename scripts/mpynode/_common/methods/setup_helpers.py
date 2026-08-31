"""Shared selection helpers for per-type setup routines.

Most mPy node types are usable the moment they are created. A few, however,
only do something once they are wired into the scene the way their stock-Maya
counterparts are:

  * a deformer (``mPyDeformer``) must live inside a
    mesh's deformation chain -- a bare ``createNode`` deforms nothing;
  * a ``mPySkinCluster`` needs influence joints + a mesh;
  * a ``mPyBlendShape`` needs a base mesh + one or more targets;
  * a ``mPyIkSolver`` needs a joint chain + an ``ikHandle`` that references it.

This module provides shared selection helpers (``_selection``, ``_deformables``,
``_joints``, ``_meshes``) and the ``SetupError`` exception used by the authored
``def setup(self, *args, **kwargs)`` bodies in ``_common/node_setups/*.py``.

The LEGACY ``SETUP_ROUTINES`` / ``run_setup`` / ``has_setup`` dispatch mechanism
has been retired (2026-06-24). The instance-method ``def setup(self)`` hook (which
wires the node it is bound to; run via ``build(setup=True)`` or "Run setup")
supersedes it.
"""

from __future__ import annotations

import maya.cmds as mc

_DEFORMABLE_SHAPE_TYPES = ("mesh", "nurbsSurface", "nurbsCurve", "lattice")


class SetupError(Exception):
    """The current selection / scene state can't support auto-setup for this
    node type. Message is user-facing (names what to select)."""


# ---- Selection helpers ----


def _selection(override=None, exclude=None):
    """Inputs for a setup body. ``override`` (a list) wins over the live
    selection when given (the snapshot path used by build(setup=True) /
    "Run setup"); otherwise reads mc.ls(selection=True). ``exclude`` (a node
    name) is removed so ``self`` is never treated as its own input."""
    if override is not None:
        sel = list(override)
    else:
        sel = mc.ls(selection=True, long=False) or []
    if exclude:
        sel = [n for n in sel if n != exclude]
    return sel


def _has_shape(node, shape_types):
    if mc.nodeType(node) in shape_types:
        return True
    for st in shape_types:
        if mc.listRelatives(node, shapes=True, type=st, noIntermediate=True):
            return True
    return False


def _meshes(sel):
    return [n for n in sel if _has_shape(n, ("mesh",))]


def _deformables(sel):
    return [n for n in sel if _has_shape(n, _DEFORMABLE_SHAPE_TYPES)]


def _joints(sel):
    return [n for n in sel if mc.nodeType(n) == "joint"]


# ---- LEGACY SETUP_ROUTINES / run_setup / has_setup REMOVED (2026-06-24) ----
# The hardcoded dispatch table and its public API (SETUP_ROUTINES, run_setup,
# has_setup) have been retired. The universal `def setup(cls)` hook in
# `_common/node_setups/<Type>.py` supersedes it. The shared selection helpers
# above remain for use by the authored setup bodies.
