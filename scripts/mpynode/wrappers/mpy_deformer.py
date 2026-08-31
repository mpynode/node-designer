"""User-facing wrapper for the mPyDeformer plug-in.

Custom deformer workflow::

    from mpynode.wrappers.mpy_deformer import MPyDeformer
    import maya.cmds as mc

    # Create + apply to a mesh in one step.
    mesh = mc.polyPlane(name="targetPlane", sx=8, sy=8)[0]
    deformer = MPyDeformer.create_on(mesh, name="myDeformer")

    # Push verts up in Y by ``self.envelope`` units.
    deformer.set_compute_expression('''
        m = self.outputGeometry[0]      # writable MFnMesh handle
        pts = m.getPoints()             # (N, 3) float64 numpy
        pts[:, 1] += self.envelope
        m.setPoints(pts)
    ''')

    # Drive via the standard envelope attribute.
    mc.setAttr(deformer.get_name() + ".envelope", 0.5)

The expression deforms through ``self.outputGeometry[i]`` -- a writable
MFnMesh handle (``getPoints()`` -> ``(N, 3)`` numpy; ``setPoints()`` commits
on compute exit), eager-copied from ``self.input[i].inputGeometry``. The
``envelope`` attribute is INHERITED from MPxDeformerNode -- every deformer
gets it for free. (The old ``self.points`` / ``self.normals`` /
``self.weights`` / ``self.deformed`` schema was removed.)

Sister-window JIT: if you want to accelerate the per-vertex
math with numba, put the @njit-decorated kernel definition in the
deformer's ``_initSource`` attribute (or in the JIT Kernels sister tab
in the Node Designer UI). The main expression then calls the kernel
directly.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode._common.lifecycle.plugin_loader import ensure_loaded as _ensure_loaded
from mpynode._common.util.selection_util import restore_selection as _restore_selection
from mpynode.wrappers._mpy_node import MPyNode


_DEFORMER_TYPE_NAME = "mPyDeformer"
_PLUGIN_NAME = "mpynode_api1.py"


def _ensure_plugin_loaded() -> None:
    """Auto-load the mPyDeformer plug-in. Idempotent. See:mod:`mpynode._common.lifecycle.plugin_loader`."""
    _ensure_loaded(_DEFORMER_TYPE_NAME)


class MPyDeformer(MPyNode):
    # No bridge-injected non-plug ``self.X`` names: every ``self.X`` the
    # expression touches is either a plug (visible in Attributes) or per-call
    # user storage (visible in Variables-User).
    INTERNAL_API_SLOTS = ()

    # Wrapper-level API for the API tab (setup / demo / @maya_command bodies);
    # never reachable as ``self.X`` from an expression tier.
    AUTHORING_API = (
        ("create_on", ""),
    )

    NATIVE_TYPE = _DEFORMER_TYPE_NAME

    # Attributes-tab allowlist (framework OFF): the shared deformer I/O.
    from mpynode._common.plugs.plug_filter import DEFORMER_USEFUL as _DEF_USEFUL
    USEFUL_INHERITED_PLUGS = _DEF_USEFUL
    del _DEF_USEFUL

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyDeformer":
        """Create a bare mPyDeformer node — NOT applied to any mesh.

        ``skip_selection=True`` creates the node without selecting it. Use
        ``create_on(mesh)`` for the common case of creating + applying the
        deformer in one call.
        """
        _ensure_plugin_loaded()
        if name is None:
            name = cls._default_create_name()
        node = mc.createNode(cls.NATIVE_TYPE, name=name,
                             skipSelect=skip_selection)
        return cls._stamp_py_class(cls(node))

    @classmethod
    def create_on(cls, mesh: str, name: str = None,
                  skip_selection: bool = False) -> "MPyDeformer":
        """Create + apply an mPyDeformer to ``mesh``.

        Uses ``cmds.deformer(type="mPyDeformer")`` which both creates
        the node and wires its inputGeometry/outputGeometry to the
        mesh's intermediate object the standard way.

        ``cmds.deformer`` has no ``skipSelect`` flag. In practice it is
        selection-neutral (it neither selects the new deformer nor disturbs the
        active selection), but ``skip_selection=True`` still snapshots the active
        selection and restores it afterward so the uniform create() contract
        holds and stays robust if that ever changes (default False = unchanged).
        """
        _ensure_plugin_loaded()
        if name is None:
            name = cls._default_create_name()
        if not mc.objExists(mesh):
            raise ValueError(f"mesh {mesh!r} does not exist")
        prior = mc.ls(selection=True, long=True) if skip_selection else None
        result = mc.deformer(mesh, type=cls.NATIVE_TYPE, name=name)
        # cmds.deformer returns [deformer_name]; rename if needed.
        deformer_name = result[0]
        if skip_selection:
            _restore_selection(prior)
        return cls._stamp_py_class(cls(deformer_name))
