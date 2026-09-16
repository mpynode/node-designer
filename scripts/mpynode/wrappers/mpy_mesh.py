"""User-facing wrapper for the mPyMesh plug-in.

mPyMesh is a custom polygon geometry GENERATOR (DG node, NOT a DAG
shape). Matches Maya's canonical pattern -- the same architecture as
``polyCube``, ``polySplit``, ``polyAppend``, ``polyBevel``. The user
expression produces vertex positions + face connectivity; the bridge
builds an MFnMesh and exposes it via ``outMesh``. To make the geometry
visible in the viewport, connect ``outMesh`` to a real Maya ``mesh``
shape's ``inMesh`` plug.

Custom polygon generator workflow::

 from mpynode.wrappers.mpy_mesh import MPyMesh
 import maya.cmds as mc

 # 1. Create the geometry generator (just a DG node, no transform).
 p = MPyMesh.create(name="myPolyGen")
 p.set_compute_expression('''
 import numpy as np
 self.points = np.array([[0,0,0],[1,0,0],[0,1,0]], dtype=np.float64)
 self.counts = np.array([3], dtype=np.int32)
 self.indices = np.array([0, 1, 2], dtype=np.int32)
 ''')

 # 2. Create a real Maya mesh as the renderer + wire the connection.
 render_xform = mc.createNode("transform", name="myRender")
 render_mesh = mc.createNode("mesh", name="myRenderShape",
 parent=render_xform)
 mc.connectAttr(p.get_name() + ".outMesh", render_mesh + ".inMesh", force=True)
 mc.sets(render_mesh, edit=True, forceElement="initialShadingGroup")

The 7 internal vars are accessed via ``self.X`` per the contract. See ``docs/node_types/mPyMesh.md`` for the full schema.

architectural notes:
 * Pivot 1: dropped the self-drawing draw override (couldn't produce
 visible geometry; the connect-to-real-mesh pattern is the canonical
 Maya path for procedural geometry anyway).
 * Pivot 2: changed base class from MPxSurfaceShape to MPxNode --
 no need to be a DAG shape if we're not rendering. This matches
 Maya's own polyCube/polySplit/polyAppend convention exactly:
 DG nodes that emit mesh data on outMesh.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode.wrappers._mpy_node import MPyNode


_POLY_TYPE_NAME = "mPyMesh"


class MPyMesh(MPyNode):
    INTERNAL_API_SLOTS = (
        ("time",    "read",  "TimeFloat -- current frame; .fps / .asSeconds()"),
        ("points",  "write", "np.ndarray(N, 3) float64 -- vertex positions"),
        ("counts",  "write", "np.ndarray(F,) int32 -- face vertex counts"),
        ("indices", "write", "np.ndarray(M,) int32 -- flat face-vertex indices"),
        ("colors",  "write", "np.ndarray(N, 3 or 4) float -- optional per-vertex color"),
        ("normals", "write", "np.ndarray(N, 3) float -- optional per-vertex normals"),
    )

    # Seeded into compute_locals by the bridge but NOT surfaced as UI rows.
    # Read by mpynode._common.interface.reserved_names.
    RESERVED_COMPUTE_LOCALS = (
        ("color_indices",  "write", "np.ndarray(sum(counts),) int -- when set, colors is a palette indexed per face-vertex"),
        ("normal_indices", "write", "np.ndarray(sum(counts),) int -- when set, normals are per face-vertex"),
        ("outMesh",        "write", "the mesh data this node emits; assign a geometry.Mesh to bypass the points/counts/indices buffers"),
    )

    # The slots the bridge passes as ``output_scratch_keys`` (see the SelfProxy
    # construction in mpynode/_api2/mpy_mesh.py). A real plug WINS on read for
    # these, so a user input/output of the same name COEXISTS with the write
    # buffer instead of being shadowed. reserved_names un-reserves them;
    # tests/authoring/test_reserved_names AST-parses the real call.
    COEXISTING_SCRATCH_SLOTS = (
        "points",
        "counts",
        "indices",
        "colors",
        "color_indices",
        "normals",
        "normal_indices",
        "outMesh",
    )

    # Attributes-tab allowlist (framework OFF): the generated mesh output.
    USEFUL_INHERITED_PLUGS = frozenset({"outMesh"})
    NATIVE_TYPE            = _POLY_TYPE_NAME

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyMesh":
        """Create a bare mPyMesh DG node.

        Time is OPT-IN: a fresh mesh is NOT wired to ``time1``, so a
        static procedural mesh does not re-evaluate every frame. Connect
        ``time1.outTime`` -> ``<node>._timeIn`` (or add a time input and
        read ``self.t``) when the expression depends on the frame; the
        per-frame refresh callback then dirties only time-driven meshes.
        """
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        if name is None:
            name = cls._default_create_name()
        ensure_loaded(cls.NATIVE_TYPE)
        node = mc.createNode(cls.NATIVE_TYPE, name=name,
                             skipSelect=skip_selection)
        return cls._stamp_py_class(cls(node))
