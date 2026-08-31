"""User-facing wrapper for the mPyNurbsCurve plug-in.

mPyNurbsCurve is a custom NURBS-curve geometry GENERATOR (DG node, NOT a
DAG shape). Matches Maya's canonical pattern for procedural curves
-- the same architecture as mPyMesh for meshes. The user expression
produces CV positions (+ optional knots / degree); the bridge builds
an MFnNurbsCurve and exposes it via ``outCurve``. To make the curve
visible in the viewport, connect ``outCurve`` to a real Maya
``nurbsCurve`` shape's ``create`` plug.

Custom curve generator workflow::

 from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
 import maya.cmds as mc

 # 1. Create the geometry generator (just a DG node, no transform).
 c = MPyNurbsCurve.create(name="myCurveGen")
 c.set_compute_expression('''
 import numpy as np
 # 8 CVs along the X axis with a Y sine wave.
 u = np.linspace(0, 1, 8)
 self.cvs = np.stack([u * 4.0, np.sin(u * 6.28) * 0.5, np.zeros_like(u)], axis=1)
 ''')

 # 2. Create a real Maya nurbsCurve shape as the renderer.
 render_xform = mc.createNode("transform", name="myCurveRender")
 render_curve = mc.createNode("nurbsCurve", name="myCurveRenderShape",
 parent=render_xform)
 mc.connectAttr(c.get_name() + ".outCurve", render_curve + ".create", force=True)

The ``compute_locals`` slots are accessed via ``self.X`` per
the contract. See ``_api2/mpy_nurbs_curve.py`` for the schema.

this wrapper module was missing -- the MPx subclass
(``mpynode._api2.mpy_nurbs_curve.MPyNurbsCurve``) was the only place
``MPyNurbsCurve`` lived, so the Node Designer's ``wrap_node`` call
(``MPyNurbsCurve(name_string)``) silently failed because MPx subclasses
take no constructor args. The Attributes + Expression panes stayed
empty for any selected mPyNurbsCurve. This module provides the
user-facing wrapper the Designer needs.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode.wrappers._mpy_node import MPyNode


_CURVE_TYPE_NAME = "mPyNurbsCurve"


class MPyNurbsCurve(MPyNode):
    # Attributes-tab allowlist (framework OFF): the generated curve output.
    USEFUL_INHERITED_PLUGS = frozenset({"outCurve"})
    NATIVE_TYPE = _CURVE_TYPE_NAME

    # The I/O contract this wrapper exposes to user expressions. ``self.time``
    # (a TimeFloat) is READ tier, pre-populated into compute_locals by the
    # bridge; cvs / knots / degree / form are WRITE tier, filled by the Compute
    # tab. ``build_default_output`` (mpynode/_api2/mpy_nurbs_curve.py) is the
    # framework's NURBS-curve marshaller, called directly as
    # ``self.outCurve = build_default_output(self.cvs, self.knots, self.degree,
    # self.form)`` -- the name resolves through the Init tab's auto-seeded
    # import. cmd+click it to read / copy / extend the implementation.
    INTERNAL_API_SLOTS = (
        ("time",     "read",  "TimeFloat -- current frame; .fps / .asSeconds()"),
        ("cvs",      "write", "np.ndarray(N, 3) float64 -- CV positions"),
        ("knots",    "write", "np.ndarray(K,) float64 -- optional, "
                              "default uniform"),
        ("degree",   "write", "int in {1, 2, 3, 5, 7} -- default 3"),
        ("form",     "write", "'open' / 'closed' / 'periodic' -- "
                              "default 'open'"),
    )

    # Seeded into compute_locals by the bridge but NOT surfaced as UI rows.
    # Same shape as INTERNAL_API_SLOTS; read by
    # mpynode._common.interface.reserved_names.
    RESERVED_COMPUTE_LOCALS = (
        ("outCurve", "write", "the curve data this node emits; set it with build_default_output(cvs, knots, degree, form)"),
        # Harvested by the bridge but read by nobody -- build_default_output
        # takes only (cvs, knots, degree, form), so setting it is inert. Still
        # seeded (and reserved) because dropping the seed would turn writes
        # into persisted stored vars on old scenes.
        ("rational", "write", "bool -- accepted but NOT applied"),
    )

    # The slots the bridge passes as ``output_scratch_keys`` (see the SelfProxy
    # construction in mpynode/_api2/mpy_nurbs_curve.py). A real plug WINS on
    # read for these, so a user input/output of the same name COEXISTS with the
    # write buffer instead of being shadowed. The build-param defaults (degree /
    # form / rational) are deliberately NOT scratch there, so they stay
    # reserved. tests/authoring/test_reserved_names AST-parses the real call.
    COEXISTING_SCRATCH_SLOTS = (
        "cvs",
        "knots",
        "outCurve",
    )

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyNurbsCurve":
        """Create a bare mPyNurbsCurve DG node.

        Time is OPT-IN: a fresh curve is NOT wired to ``time1``, so a
        static procedural curve does not re-evaluate every frame. If the
        expression needs the current frame, add a time input
        (``add_input_attr("t", "time")`` auto-connects it to ``time1``) and
        read ``self.t``. The per-frame refresh callback then dirties only
        time-driven instances."""
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        if name is None:
            name = cls._default_create_name()
        ensure_loaded(cls.NATIVE_TYPE)
        node = mc.createNode(cls.NATIVE_TYPE, name=name,
                             skipSelect=skip_selection)
        return cls._stamp_py_class(cls(node))
