"""Top-level mpynode package."""

__version__ = "2.0.0a1"

# Public wrapper classes, resolved lazily (PEP 562) so ``from mpynode import
# MPyNurbsCurve`` costs nothing at import time and cannot cycle. Importing a
# name only defines the class; nodes are created in ``.create()``.
_WRAPPER_EXPORTS = {
    "MPyNode":         "mpynode.wrappers._mpy_node",
    "MPyNurbsCurve":   "mpynode.wrappers.mpy_nurbs_curve",
    "MPyMesh":         "mpynode.wrappers.mpy_mesh",
    "MPyNurbsSurface": "mpynode.wrappers.mpy_nurbs_surface",
    "MPyTransform":    "mpynode.wrappers.mpy_transform",
    "MPyLocator":      "mpynode.wrappers.mpy_locator",
    "MPyConstraint":   "mpynode.wrappers.mpy_constraint",
    "MPyFile":         "mpynode.wrappers.mpy_file",
    "MPyDeformer":     "mpynode.wrappers.mpy_deformer",
    "MPySkinCluster":  "mpynode.wrappers.mpy_skin_cluster",
    "MPyBlendShape":   "mpynode.wrappers.mpy_blend_shape",
    "MPyIkSolver":     "mpynode.wrappers.mpy_iksolver",
}


def __getattr__(name):
    # Explicit factory: ``mpynode.wrap_node("someNode")`` -> type-specific
    # wrapper. Named for what it wraps -- a NODE. The bare ``wrap`` it replaces
    # is GONE rather than aliased: it read as a wrap deformer or a geometry
    # cast, and leaving it behind would keep the word occupied.
    if name == "wrap_node":
        import importlib

        return getattr(importlib.import_module("mpynode._node_registry"),
                       "wrap_node")
    module = _WRAPPER_EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module 'mpynode' has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module), name)


def __dir__():
    return sorted(list(globals()) + list(_WRAPPER_EXPORTS) + ["wrap_node"])
