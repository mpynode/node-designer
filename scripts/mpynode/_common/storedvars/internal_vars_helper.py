"""Helpers for looking up the per-node-class ``INTERNAL_VARS`` schema.

The Storage tab UI needs to render schema-only ``Internal`` rows
for the active node. This module hides the native-type \u2192 impl-class
mapping behind one function so the widget doesn't grow knowledge of
which ``_api1`` / ``_api2`` module owns each node type.
"""

from __future__ import annotations

import importlib
from typing import Any


# native_type -> (module_name, class_name) for the impl class carrying the
# ``INTERNAL_VARS`` class attribute.
_NATIVE_TYPE_TO_IMPL: dict[str, tuple[str, str]] = {
    "mPyNode": ("mpynode._api2._mpy_node", "MPyNode"),
    "mPyConstraint": ("mpynode._api2.mpy_constraint", "MPyConstraint"),
    "mPyLocator": ("mpynode._api2.mpy_locator", "MPyLocator"),
    "mPyIkSolver": ("mpynode._api1.mpy_iksolver", "MPyIkSolver"),
    "mPyDeformer": ("mpynode._api1.mpy_deformer", "MPyDeformer"),
    "mPyTransform": ("mpynode._api1.mpy_transform", "MPyTransform"),
    "mPyMesh": ("mpynode._api2.mpy_mesh", "MPyMesh"),
    "mPySkinCluster": ("mpynode._api1.mpy_skin_cluster", "MPySkinCluster"),
    "mPyBlendShape": ("mpynode._api1.mpy_blend_shape", "MPyBlendShape"),
}


def get_internal_vars_schema(native_type: str) -> dict[str, dict[str, Any]]:
    """Return the ``INTERNAL_VARS`` schema dict for the given Maya
    native node type, or ``{}`` if unknown / lookup failed.

    Safe to call from any context; errors are swallowed so a stale UI
    refresh never crashes the editor.
    """
    if not native_type or native_type not in _NATIVE_TYPE_TO_IMPL:
        return {}
    module_name, class_name = _NATIVE_TYPE_TO_IMPL[native_type]
    try:
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        schema = getattr(cls, "INTERNAL_VARS", None)
        if isinstance(schema, dict):
            return dict(schema)
    except Exception:
        pass
    return {}


def get_solver_context_snapshot_dict(node_name: str) -> dict[str, Any]:
    """Return the parsed ``_solverContextSnapshot`` dict for ``node_name``,
    or ``{}`` when no snapshot has been written yet.

    wires this into the Storage tab's Internal section so live
    values render alongside schema rows. The snapshot is only written by
    nodes that have a ``doSolve`` / ``compute`` path that calls
    ``write_solver_context_snapshot`` (currently mPyIkSolver).
    """
    try:
        from mpynode._common.nodes.snapshot import read_solver_context_snapshot
    except Exception:
        return {}
    try:
        snapshot = read_solver_context_snapshot(node_name)
    except Exception:
        return {}
    return snapshot or {}
