"""User-facing wrapper for the mPyLocator plug-in.

The Compute expression (``_computeSource`` plug) drives the icon DRAW: a Python
expression that assigns ``self.draw``, which the MPxDrawOverride renders every
frame. User INPUTS work too (read via ``self.X`` in the draw).

Note: ``mPyLocator`` does NOT support DG user OUTPUTS -- MPxLocatorNode
(a DAG shape) doesn't dispatch ``compute()`` for runtime-added output
plugs (verified in Maya 2024 standalone + 2026 GUI). For output math,
drive a downstream ``mPyNode`` (which has full input/output support).

Usage::

 from mpynode.wrappers.mpy_locator import MPyLocator
 import numpy as np

 loc = MPyLocator.create(name="myGizmo")
 loc.set_compute_expression('''
 # 3-axis gizmo: red X, green Y, blue Z
 import numpy as np
 self.draw = DrawLines(
 np.zeros((3, 3)),
 np.array([[1,0,0], [0,1,0], [0,0,1]], dtype=float),
 color=np.array([[1,0,0], [0,1,0], [0,0,1]], dtype=float),
 )
 ''')
 # The locator + draw override show in the viewport immediately.

``self.draw`` defaults to None; the locator renders nothing until the
expression assigns to it.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode._common.methods.methods_registry import MethodsSourceMixin
from mpynode.wrappers._mpy_node import MPyNode


class MPyLocator(MPyNode, MethodsSourceMixin):

    # DrawOverride.prepareForDraw callback state.
    INTERNAL_API_SLOTS = (
        ("time",            "read",  "TimeFloat -- current frame; .fps / .asSeconds()"),
        ("selected",        "read",  "bool -- viewport selection state"),
        ("is_lead",         "read",  "bool -- True iff this locator is the lead selection"),
        ("hovered",         "read",  "bool -- True while the cursor is over this locator (cursor-ray hover_tracker)"),
        ("precise_hover",   "write", "bool -- set True for precise (ray-vs-drawn-triangles) hover instead of bounding-box hover; one patch at a time via DrawMesh(precise_hover=True)"),
        ("selection_color", "read",  "tuple(r, g, b) -- selection-highlight color"),
        ("auto_highlight",  "write", "bool or None -- override automatic selection highlight"),
        ("auto_refresh",    "write", "float or None -- redraw interval in seconds (None = no auto-refresh)"),
        ("draw",            "write", "DrawItem, a list of them, or None -- the whole drawing, composed with '+' (DrawCircle(...) + DrawText(...)); authoring order is draw order"),
    )

    # The slots the bridge passes as ``output_scratch_keys`` (see the SelfProxy
    # construction in mpynode/_api2/mpy_locator.py). A real plug WINS on read
    # for these, so a user input/output of the same name COEXISTS with the
    # write slot instead of being shadowed. The draw CONTEXT slots (time /
    # selected / is_lead / hovered / selection_color) have no backing plug and
    # are NOT scratch, so they stay reserved. tests/authoring/test_reserved_names
    # AST-parses the real call.
    COEXISTING_SCRATCH_SLOTS = (
        "auto_highlight",
        "auto_refresh",
        "draw",
        "precise_hover",
    )
    # Attributes-tab allowlist (framework OFF): a locator has no inherited plug
    # worth showing (publishedNode / objectGroups / renderLayer / worldPosition
    # are noise). User-added attrs still show.
    USEFUL_INHERITED_PLUGS = frozenset()

    # Wrapper-level API for the API tab (setup / demo / @maya_command bodies);
    # never reachable as ``self.X`` from an expression tier. The DRAW surface a
    # locator expression actually uses is self.draw + the Draw* types, which the
    # Framework tab lists separately.
    AUTHORING_API = (
        ("evaluate_draw_commands", ""),
        ("get_transform", ""),
    )

    NATIVE_TYPE = "mPyLocator"

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyLocator":
        # createNode for a locator-derived shape: Maya auto-creates the parent
        # transform. skipSelect affects only the selection, not the shape name.
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        if name is None:
            name = cls._default_create_name()
        ensure_loaded(cls.NATIVE_TYPE)
        shape_name = mc.createNode(cls.NATIVE_TYPE, name=name,
                                   skipSelect=skip_selection)
        return cls._stamp_py_class(cls(shape_name))

    def get_transform(self) -> str:
        """Return the parent transform (locators always have one)."""
        parents = mc.listRelatives(self._name, parent=True, fullPath=False) or []
        if not parents:
            raise RuntimeError(f"locator {self._name!r} has no parent transform")
        return parents[0]

    def evaluate_draw_commands(self, time_value: float = 0.0) -> dict:
        """Trigger the locator's expression and return this frame's ORDERED
        draw commands -- one record per authored item, in authoring order::

            {
                "commands": [
                    {"slot": "polygons",
                     "buffer": {"points":..., "indices":..., "counts":..., ...}},
                    {"slot": "text",
                     "buffer": {"positions":..., "strings": [...], ...}},
                ],
                "auto_highlight": True,
                "auto_refresh": False,
                "precise_hover": False,
            }

        The per-slot buffer shapes are ``lines`` (starts, ends, colors),
        ``points`` (positions, colors, sizes), ``polygons`` (points, indices,
        counts, + one fill mode), ``shapes`` (kinds, centers, radii, axes,
        colors, filled) and ``text`` (positions, strings, colors, sizes).

        Useful for testing without spinning up a viewport.
        """
        import maya.api.OpenMaya as om

        sel = om.MSelectionList()
        sel.add(self._name)
        node_obj = sel.getDependNode(0)
        fn = om.MFnDependencyNode(node_obj)
        mpx = fn.userNode()
        if mpx is None:
            return {"commands": [], "auto_highlight": True,
                    "auto_refresh": False, "precise_hover": False}
        return mpx.evaluateDrawItems(time_value)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._name!r}>"
