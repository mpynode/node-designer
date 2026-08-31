"""User-facing wrapper for the mPyTransform plug-in.

Custom transform workflow::

    from mpynode.wrappers.mpy_transform import MPyTransform
    import maya.cmds as mc

    # Create + parent a cube under it.
    t = MPyTransform.create(name="myTransform")
    cube = mc.polyCube(name="referenceCube")[0]
    mc.parent(cube, t.get_name())

    # Drive the transform from a parent-relative (local) matrix.
    t.set_compute_expression('''
        import numpy as np
        M = np.eye(4)
        M[3, :3] = (0.0, 2.0, 0.0)
        self.local_matrix = M          # parent-relative desired matrix
        self.apply_translate = True    # gate the channels you want driven
    ''')

The gated local-matrix contract (mirrors mPyIkSolver, single joint) exposes four
write slots via ``self.X``: ``local_matrix`` (desired parent-relative 4x4,
default ``None``) and ``apply_rotate`` / ``apply_translate`` / ``apply_scale``
(per-channel gates, default ``True``). With ``local_matrix`` ``None`` (the
default) the node is a plain Maya transform regardless of the gates; assign it
and the node drives all channels through ``offsetParentMatrix``. Set a gate
``False`` to keep that channel on its live TRS value. To place the node in WORLD
space, feed the parent world through a CONNECTED matrix input (DG-tracked) and
set ``self.local_matrix = worldDesired @ inv(parentWorld)`` -- the node never
reads its own DAG parent, so world-space is opt-in and cycle-free.

The node's own live channels are exposed as always-present INPUT attributes (the
inherited transform plugs, surfaced in the Node Designer's Inputs pane via
``EXPOSED_INPUT_PLUGS``): the expression reads ``self.translate`` /
``self.rotate`` (**radians**) / ``self.scale`` / ``self.shear`` (each a ``(3,)``
numpy) and ``self.rotate_order`` (int 0..5). Any change to a channel re-evaluates
the node. Read EXTERNAL / world driver matrices by adding matrix INPUT attrs.

mPyTransform is the only mpynode native type that uses
``registerTransform()`` (paired with MPyTransformMatrix) instead of
``registerNode()``. From the user's perspective this is invisible \u2014
``createNode("mPyTransform")`` works the same as any other type.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode.wrappers._mpy_node import MPyNode


_TRANSFORM_TYPE_NAME = "mPyTransform"


class MPyTransform(MPyNode):

    # Non-plug API state the wrapper marshals into the expression namespace.
    # Shown in the Node Designer Internals pane, separately from the
    # INPUT / OUTPUT panes, which walk the live plug tree.
    INTERNAL_API_SLOTS = (
        ("local_matrix",    "write", "4x4 or None -- desired LOCAL (parent-relative) matrix; applied via offsetParentMatrix. For WORLD placement set local_matrix = world @ inv(parent), reading the parent from a connected matrix input"),
        ("apply_rotate",    "write", "bool -- gate: take rotation from the matrix (default True; set False to keep live rotate)"),
        ("apply_translate", "write", "bool -- gate: take translate from the matrix (default True; set False to keep live translate)"),
        ("apply_scale",     "write", "bool -- gate: take scale from the matrix (default True; set False to keep live scale)"),
    )

    # Seeded into compute_locals by the bridge but NOT surfaced as UI rows --
    # they read as the promoted TRS plugs below. Read by
    # mpynode._common.interface.reserved_names.
    RESERVED_COMPUTE_LOCALS = (
        ("translate",    "read", "np.ndarray(3,) -- this node's live translate channel"),
        ("rotate",       "read", "np.ndarray(3,) RADIANS -- this node's live rotate channel"),
        ("scale",        "read", "np.ndarray(3,) -- this node's live scale channel"),
        ("shear",        "read", "np.ndarray(3,) -- this node's live shear channel"),
        ("rotate_order", "read", "int 0..5 -- this node's live rotateOrder enum"),
    )

    # Inherited transform plugs promoted to always-visible INPUT attributes in
    # the Node Designer (otherwise hidden as DAG framework attrs). Read as
    # ``self.translate`` / ``rotate`` (RADIANS) / ``scale`` / ``shear`` (each a
    # (3,) numpy) / ``rotate_order`` (int 0..5); any change re-evaluates. The
    # X/Y/Z children are listed too so they expand under their parent instead
    # of being framework-filtered to orphans.
    EXPOSED_INPUT_PLUGS = (
        "translate", "translateX", "translateY", "translateZ",
        "rotate", "rotateX", "rotateY", "rotateZ",
        "scale", "scaleX", "scaleY", "scaleZ",
        "shear", "shearXY", "shearXZ", "shearYZ",
        "rotateOrder",
    )
    # Attributes-tab allowlist (framework OFF) = the promoted TRS inputs; the
    # rest of a transform's inherited plugs are DAG framework noise.
    USEFUL_INHERITED_PLUGS = frozenset(EXPOSED_INPUT_PLUGS)
    NATIVE_TYPE = _TRANSFORM_TYPE_NAME

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyTransform":
        """Create a bare mPyTransform node.

        Returns the wrapper. The node is a transform in the DAG, so it
        accepts children via the standard ``mc.parent()`` flow.

        Time is OPT-IN: a fresh transform is NOT wired to ``time1``, so a
        static transform does not re-evaluate (and re-touch its TRS)
        every frame. Connect ``time1.outTime`` -> ``<node>._timeIn`` (or
        add a time input and read ``self.t``) when the expression depends
        on the frame -- otherwise time-driven expressions stay frozen.
        The per-frame refresh callback then touches only time-driven
        transforms.
        """
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        if name is None:
            name = cls._default_create_name()
        ensure_loaded(cls.NATIVE_TYPE)
        node = mc.createNode(cls.NATIVE_TYPE, name=name,
                             skipSelect=skip_selection)
        # Guarantee the paired fourByFourMatrix opm relay exists. The plugin's
        # nodeAdded callback normally wires it on create; this idempotent call
        # keeps the wrapper self-sufficient when that callback is absent.
        try:
            from mpynode._api1.mpy_transform import ensure_opm_relay

            ensure_opm_relay(node)
        except Exception:
            pass
        return cls._stamp_py_class(cls(node))
