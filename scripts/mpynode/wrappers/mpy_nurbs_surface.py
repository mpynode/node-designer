"""User-facing wrapper for the mPyNurbsSurface plug-in.

mPyNurbsSurface is a custom NURBS-surface geometry GENERATOR (DG node).
The user expression produces CV grid positions; the bridge builds an
MFnNurbsSurface and exposes it via ``outSurface``. To make the
surface visible, connect ``outSurface`` to a real Maya
``nurbsSurface`` shape's ``create`` plug.

Custom surface generator workflow::

 from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface
 import maya.cmds as mc

 s = MPyNurbsSurface.create(name="mySurfGen")
 s.set_compute_expression('''
 import numpy as np
 # 4x4 grid of CVs with sinusoidal Y wave.
 u = np.linspace(0, 4, 4)
 v = np.linspace(0, 4, 4)
 U, V = np.meshgrid(u, v)
 Y = np.sin(U * 1.5) * 0.5
 self.cvs = np.stack([U, Y, V], axis=-1)
 ''')

 render_xform = mc.createNode("transform", name="mySurfRender")
 render_surf = mc.createNode("nurbsSurface", name="mySurfRenderShape",
 parent=render_xform)
 mc.connectAttr(s.get_name() + ".outSurface", render_surf + ".create", force=True)

See ``_api2/mpy_nurbs_surface.py`` for the compute_locals schema.

this wrapper module was missing -- mirrors the
``mpynode.wrappers.mpy_nurbs_curve`` and ``mpynode.lattice`` fixes for the same root
cause (the Node Designer needs a top-level wrapper class to
construct from a node name string).
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode.wrappers._mpy_node import MPyNode


_SURFACE_TYPE_NAME = "mPyNurbsSurface"


class MPyNurbsSurface(MPyNode):
    INTERNAL_API_SLOTS = (
        ("time",      "read",  "TimeFloat -- current frame; .fps / .asSeconds()"),
        ("cvs",       "write", "np.ndarray(Nu*Nv, 3) float64 -- CVs row-major"),
        ("num_cvs_u", "write", "int -- CVs along U"),
        ("num_cvs_v", "write", "int -- CVs along V"),
        ("knots_u",   "write", "np.ndarray float64 -- optional, default uniform"),
        ("knots_v",   "write", "np.ndarray float64 -- optional, default uniform"),
        ("degree_u",  "write", "int in {1, 2, 3, 5, 7} -- default 3"),
        ("degree_v",  "write", "int in {1, 2, 3, 5, 7} -- default 3"),
        ("form_u",    "write", "'open' / 'closed' / 'periodic' -- default 'open'"),
        ("form_v",    "write", "'open' / 'closed' / 'periodic' -- default 'open'"),
    )

    # Seeded into compute_locals by the bridge but NOT surfaced as UI rows.
    # Read by mpynode._common.interface.reserved_names.
    RESERVED_COMPUTE_LOCALS = (
        ("outSurface", "write", "the surface data this node emits; set it with build_default_output(...)"),
    )

    # The slots the bridge passes as ``output_scratch_keys`` (see the SelfProxy
    # construction in mpynode/_api2/mpy_nurbs_surface.py). A real plug WINS on
    # read for these, so a user input/output of the same name COEXISTS with the
    # write buffer instead of being shadowed. The build-param defaults
    # (degree_u/v, form_u/v) are deliberately NOT scratch there, so they stay
    # reserved. tests/authoring/test_reserved_names AST-parses the real call.
    COEXISTING_SCRATCH_SLOTS = (
        "cvs",
        "num_cvs_u",
        "num_cvs_v",
        "knots_u",
        "knots_v",
        "outSurface",
    )

    # Attributes-tab allowlist (framework OFF): the generated surface output.
    USEFUL_INHERITED_PLUGS = frozenset({"outSurface"})
    NATIVE_TYPE = _SURFACE_TYPE_NAME

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyNurbsSurface":
        """Create a bare mPyNurbsSurface DG node.

        Time is OPT-IN: a fresh surface is NOT wired to ``time1``, so a
        static procedural surface does not re-evaluate every frame.
        Connect ``time1.outTime`` -> ``<node>._timeIn`` (or add a time
        input and read ``self.t``) when the expression depends on the
        frame; the per-frame refresh callback then dirties only
        time-driven surfaces."""
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        if name is None:
            name = cls._default_create_name()
        ensure_loaded(cls.NATIVE_TYPE)
        node = mc.createNode(cls.NATIVE_TYPE, name=name,
                             skipSelect=skip_selection)
        return cls._stamp_py_class(cls(node))
