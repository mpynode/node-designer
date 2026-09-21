"""MPyLocator (API 2.0) \u2014 expression-driven custom locator + draw override.

This module holds BOTH the node and its VP2 renderer (same pattern as
``mpy_file.py``): ``MPyLocator`` (an MPxLocatorNode) produces typed draw
buffers from the user's Compute expression, and ``MPyLocatorDrawOverride``
(an MPxDrawOverride, near the bottom of this file) consumes them each
frame via batched ``MUIDrawManager`` calls. The override is registered
separately at plugin load via ``MDrawRegistry.registerDrawOverrideCreator``.

The locator's transform behaves like any standard locator (sits in the
DAG, can be parented). The unique part is the Compute expression: it assigns
``self.draw`` -- one drawable, several composed with ``+``, or a (possibly
nested) list of them -- and the override renders them every frame.

``evaluateDrawItems`` returns an ORDERED command list, one record per authored
item, ``{"slot": ..., "buffer": {...}}``. The renderer replays it front-to-back,
so authoring order IS draw order: whatever you write last draws on top.

Buffer shapes, by slot:

* ``"lines"``    -- dict(starts, ends, colors)
* ``"points"``   -- dict(positions, colors, sizes)
* ``"polygons"`` -- dict(points, indices, counts, ...). Fill color is ONE
  of (mutually exclusive): ``colors`` (uniform RGB/RGBA), ``face_colors``
  (F,3|4 -- flat per face), ``vertex_colors`` (V,3|4 -- smooth per shared
  point), or ``face_vertex_colors`` (sum(counts),3|4 -- face-varying).
  Omit all for no fill. ``wireframe`` overlays edges; ``wireframe_width``
  sets line width; ``cull_backfaces`` culls faces; ``world_space`` keeps
  points in world space regardless of the locator transform.
* ``"shapes"``   -- dict(kinds, centers, radii, axes, colors, filled);
  Maya built-ins: sphere / box / cone / cylinder / circle
* ``"text"``     -- dict(positions, strings, colors, sizes)

Draw space (optional ``"space"`` key on ANY buffer above; default
``"local"``):

* ``"local"`` -- object space (the default). Points ride the locator's
  transform. For ``"text"`` this also means ``sizes`` are OBJECT-space
  glyph heights and the bitmap font is auto-scaled by the object's
  on-screen size, so labels shrink as the camera pulls away and grow
  with the transform scale instead of collapsing over each other.
* ``"screen"`` -- constant screen/pixel size. lines/points/polygons are
  projected to the viewport and drawn with 2D primitives; ``"text"``
  ``sizes`` are treated as constant pixels (billboarded, as before).
  3D solid ``shapes`` (sphere/box/cone/cylinder) have no 2D analogue and
  fall back to local drawing (``circle`` maps to a 2D circle).

User expression namespace (all via ``self.X``):
  * ``self.time`` -- current frame (a ``TimeFloat``)
  * ``self.draw`` -- the drawing (write-only output)
  * ``self.selected`` / ``self.is_lead`` / ``self.hovered`` /
    ``self.selection_color`` -- read-only draw state from the override
  * ``self.auto_highlight`` / ``self.auto_refresh`` / ``self.precise_hover``
    -- optional framework toggles. Precise (ray-vs-triangle) hover can also be
    opted into one patch at a time, via ``DrawMesh(..., precise_hover=True)``.

The numpy buffer helpers live in ``_common/draw_buffers.py``.
"""

from __future__ import annotations

import sys
import time as _time

import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.api.OpenMayaRender as omr
import maya.api.OpenMayaUI as omui
import numpy as np
from mpynode._api2 import helpers
from mpynode._common.io import serialization
from mpynode._common.storedvars import stored_var_store as _svstore
from mpynode._common.plugs.promoted_types import TimeFloat
from mpynode._common.compute.expression import (
    build_exec_namespace,
    compile_expression,
    exec_with_profile_watch,
)
from mpynode._common.draw import draw_types
from mpynode._common.draw.draw_buffers import (
    apply_face_mask,
    build_edge_point_pairs,
    command_bounds,
    cull_backfaces_mask,
    edge_face_indices,
    expand_face_colors_to_triangles,
    fan_triangulate,
    local_text_pixel_size,
    matrix_uniform_scale,
    normalize_color,
    normalize_space,
    pixels_per_world_unit,
    point_pixel_size,
    project_object_points_to_pixels,
    region_boundary_edges,
    triangle_corner_indices,
)


#: Anything this wide is Maya's "unbounded" sentinel box, not a real extent.
_HUGE_EXTENT = 1e29


class MPyLocator(omui.MPxLocatorNode):
    NODE_NAME              = "mPyLocator"
    NODE_ID                = om.MTypeId(0x00135702)
    DRAW_DB_CLASSIFICATION = "drawdb/geometry/mpyLocator"
    DRAW_REGISTRANT_ID     = "mPyLocatorPlugin"

    # The user expression assigns ``self.draw``; evaluateDrawItems flattens it
    # into ordered ``{"slot", "buffer"}`` commands that MPyLocatorDrawOverride
    # (below) replays via MUIDrawManager. Each buffer is a dict of numpy arrays;
    # helpers live in ``_common/draw_buffers.py``. Plug-tree state is reached
    # through ``self.X`` -- there is no INTERNAL_VARS schema.

    _expression_attr:       om.MObject = om.MObject.kNullObj
    _input_attrs_attr:      om.MObject = om.MObject.kNullObj
    _output_attrs_attr:     om.MObject = om.MObject.kNullObj
    _stored_vars_list_attr: om.MObject = om.MObject.kNullObj
    _stored_vars_data_attr: om.MObject = om.MObject.kNullObj
    _debug_mode_attr:       om.MObject = om.MObject.kNullObj
    # profile + watch instrumentation plugs.
    _profile_enabled_attr:       om.MObject = om.MObject.kNullObj
    _deep_profile_enabled_attr:  om.MObject = om.MObject.kNullObj
    _watch_enabled_attr:         om.MObject = om.MObject.kNullObj
    _profile_snapshot_data_attr: om.MObject = om.MObject.kNullObj
    _watch_vars_data_attr:       om.MObject = om.MObject.kNullObj

    def __init__(self):
        super().__init__()
        self._expr_str: str = ""
        self._expr_code = compile_expression("")
        # Object-space extent of the LAST drawing (see boundingBox); None until
        # the gizmo has drawn once.
        self._draw_bounds = None

    @staticmethod
    def creator():
        return MPyLocator()

    # -- extent -----------------------------------------------------------
    # MPxLocatorNode's default box is the unit cube scaled by localScale, which
    # describes the cross gizmo Maya draws for a plain locator -- not what an
    # expression draws. So "frame selection" on a gizmo drawing a radius-10 ring
    # zoomed to a one-unit box, and a bbox pick missed most of the drawing. The
    # drawn extent is measured once per draw (evaluateDrawItems) and reported
    # here, unioned with the default box so localScale still counts.

    def isBounded(self):
        return True

    def boundingBox(self):
        """The box around what this gizmo actually DRAWS, in object space.

        Falls back to the locator default until the node has drawn once (the
        bounds are a by-product of drawing, never a second evaluation of the
        user expression -- Maya calls this during selection and framing, where
        running arbitrary user code would be a surprise).
        """
        bounds = self._draw_bounds
        if not bounds:
            try:
                return super().boundingBox()
            except Exception:
                return om.MBoundingBox()
        lo, hi = bounds
        box = om.MBoundingBox(om.MPoint(lo[0], lo[1], lo[2]),
                              om.MPoint(hi[0], hi[1], hi[2]))
        # The locator's own localPosition/localScale box joins in only when it
        # is FINITE: MPxLocatorNode's default is Maya's infinite box (±1e30),
        # and expanding by that reports exactly the unbounded extent this
        # override exists to replace -- framing zooms to the whole scene.
        try:
            base = super().boundingBox()
            if base is not None and float(base.width) < _HUGE_EXTENT:
                box.expand(base.min)
                box.expand(base.max)
        except Exception:
            pass
        return box

    @staticmethod
    def initializer():
        plugs                             = helpers.build_internal_attrs(MPyLocator)
        MPyLocator._expression_attr       = plugs["_computeSource"]
        MPyLocator._input_attrs_attr      = plugs["inputs"]
        MPyLocator._output_attrs_attr     = plugs["outputs"]
        MPyLocator._stored_vars_list_attr = plugs["stored_vars_list"]
        MPyLocator._stored_vars_data_attr = plugs["stored_vars_data"]
        MPyLocator._debug_mode_attr       = plugs["debug_mode"]

        MPyLocator._profile_enabled_attr       = plugs["profile_enabled"]
        MPyLocator._deep_profile_enabled_attr  = plugs["deep_profile_enabled"]
        MPyLocator._watch_enabled_attr         = plugs["watch_enabled"]
        MPyLocator._profile_snapshot_data_attr = plugs["profile_snapshot_data"]
        MPyLocator._watch_vars_data_attr       = plugs["watch_vars_data"]

    def setInternalValue(self, plug, data_handle):
        try:
            attr = plug.attribute()
            if attr == MPyLocator._expression_attr:
                new_src        = data_handle.asString()
                self._expr_str = new_src
                # surface SyntaxError instead of swallowing.
                from mpynode._common.compute.expression import safe_compile_expression

                node_name = ""
                try:
                    import maya.api.OpenMaya as _om

                    node_name = _om.MFnDependencyNode(self.thisMObject()).name()
                except Exception:
                    pass
                code = safe_compile_expression(
                    new_src,
                    node_name = node_name,
                    filename  = "<mpylocator-expression>",
                )
                if code is not None:
                    self._expr_code = code
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Custom hook: evaluate the user expression, return draw buffers dict
    # ------------------------------------------------------------------

    def evaluateDrawItems(
        self,
        time_value:      float        = 0.0,
        selected:        bool         = False,
        is_lead:         bool         = False,
        selection_color: tuple        = (1.0, 1.0, 1.0, 1.0),
        hovered:         bool         = False,
        wallclock:       float | None = None,
    ) -> dict:
        """Run the user expression and return this frame's ORDERED draw
        commands (empty if the expression drew nothing).

        Called by MPyLocatorDrawOverride.prepareForDraw each frame.
        Failures return no commands (no draw output).

        namespace contract: ``time`` is read via ``self.time`` (the current
        frame -- the implicit time plug, so an expression that reads it opts
        into the timeline); ``self.wallclock`` is seconds since the epoch
        (``time.time()``), the timeline-independent animation clock every
        bundled locator animates on, identical in the compiled node. Pass
        ``wallclock`` to pin it (tests); None samples the real clock.
        ``self.draw`` is the write-only drawing. User expression looks like:

            self.draw = (DrawCircle(radius=2.0, color=ORANGE)
                         + DrawText("hip_ctrl", position=(0, 2, 0)))

        Stored vars also accessed via ``self.X``.

        Returns a dict like::

            {
                "commands": [{"slot": "lines", "buffer": {...}},
                             {"slot": "text",  "buffer": {...}}],
                "auto_highlight": True,
                "auto_refresh": False,
            }
        """
        _EMPTY = {
            "commands":       [],
            "auto_highlight": True,   # framework tints by default
            "auto_refresh":   False,  # framework does NOT auto-refresh by default
            "precise_hover":  False,  # bbox hover by default (precise = opt-in)
        }
        node_obj = self.thisMObject()
        fn_node  = om.MFnDependencyNode(node_obj)

        # Keep the compiled code in sync with _computeSource; covers node
        # DUPLICATION, which doesn't route through setInternalValue.
        helpers.ensure_expr_code(self, MPyLocator._expression_attr)

        # Read user inputs (rare for locator, but supported).
        try:
            inputs_str = fn_node.findPlug(MPyLocator._input_attrs_attr, True).asString()
            input_map  = serialization.decode_attr_map(inputs_str) if inputs_str else {}
        except Exception:
            input_map = {}

        input_values = helpers.read_user_inputs_dict(node_obj, input_map)

        # Read stored variables for self.X access.
        stored_vars = {}
        try:
            sv_str = fn_node.findPlug(
                MPyLocator._stored_vars_data_attr, True
            ).asString()
            stored_vars = _svstore.load_for_compute(node_obj, sv_str)
        except Exception:
            stored_vars = {}

        # ``selected`` / ``is_lead`` / ``hovered`` / ``selection_color`` are
        # DrawOverride callback state (NOT plugs, so they cannot come from the
        # plug tree); ``draw`` plus auto_highlight / auto_refresh are write
        # outputs harvested via ``get_compute_locals()``. ``time`` is the current
        # frame (a ``TimeFloat`` carrying the scene fps), sourced from
        # ``MAnimControl.currentTime()`` in the draw override each frame.
        from mpynode._common.compute.self_proxy import SelfProxy

        # C2 (base contract): seed USER inputs DENSELY so ``self.<input>`` is a
        # numpy array / primitive inside the expression, matching base mPyNode /
        # mesh / constraint. ``input_values`` was previously DROPPED, so
        # ``self.<input>`` fell through to the live plug proxy: a vector-array
        # input read back as a ragged ``(index, value)`` sequence and
        # ``np.asarray(self.<in>)`` raised "inhomogeneous shape". The draw
        # context + write buffers layer ON TOP so their reserved names keep
        # their semantics (and, being output-scratch, a same-named input still
        # wins on read via the live plug).
        _compute_locals = dict(input_values)
        _compute_locals.update({
            "time":            TimeFloat(time_value),
            "wallclock":       float(wallclock) if wallclock is not None else _time.time(),
            "selected":        bool(selected),
            "is_lead":         bool(is_lead),
            "hovered":         bool(hovered),
            "selection_color": tuple(selection_color),
            "auto_highlight":  None,
            "auto_refresh":    None,
            "draw":            None,
            "precise_hover":   None,
        })

        self_proxy = SelfProxy(
            node_obj,
            datablock      = None,
            user_storage   = stored_vars,
            compute_locals = _compute_locals,
            # The drawing + draw flags are WRITE-ONLY output slots. Mark them as
            # output-scratch so a user-added INPUT/OUTPUT of the same name (e.g.
            # a ``draw`` bool gating the gizmo) is READABLE via ``self.<name>``
            # -- a real plug wins on read -- while ``self.<name> = ...`` still
            # lands in the scratch slot and is harvested for drawing. The
            # context slots (time / selected / is_lead / hovered /
            # selection_color) have NO backing plug and stay Tier-1 reads.
            output_scratch_keys={
                "auto_highlight",
                "auto_refresh",
                "draw",
                "precise_hover",
            },
            node_type_label=type(self).__name__,
        )

        # Self-only: USER inputs are reached via self.X (live plug tree), NOT
        # as bare names.
        namespace         = build_exec_namespace()  # __builtins__ only
        namespace["self"] = self_proxy

        if self._expr_code is None:
            self._draw_bounds = None       # nothing drawn -> locator default box
            return dict(_EMPTY)

        # Capture stderr + broadcast to the UI Log panel via the Qt-free
        # log_bus, matching every other node type.
        captured: list[str] = []

        def _on_err(msg):
            captured.append(msg)

        ok = exec_with_profile_watch(
            self._expr_code,
            namespace,
            on_error = _on_err,
            node_obj = node_obj,
        )
        if not ok:
            if captured:
                # Base-contract policy (C10): suppress the benign transient
                # missing-plug error (declared-but-unresolved plug pulled mid
                # scene-load / graph rebuild), surface everything else --
                # identical to the base mPyNode instead of drifting.
                from mpynode._common.compute.base_contract import broadcast_compute_error

                broadcast_compute_error(
                    "mPyLocator",
                    captured[0],
                    declared_names=set(input_map),
                )
            self._draw_bounds = None       # nothing drawn -> locator default box
            return dict(_EMPTY)

        # commit any stored-var changes the expression made.
        storage_diff = self_proxy.diff_storage()
        if storage_diff:
            new_stored = dict(stored_vars)
            for k, v in storage_diff.items():
                if v is None:
                    new_stored.pop(k, None)
                else:
                    new_stored[k] = v
            _svstore.set_for_compute(node_obj, new_stored)

        # Harvest from the compute_locals snapshot. Untouched defaults:
        # auto_highlight True (framework selection-tinting), auto_refresh False
        # (no auto-redraw -- explicit opt-in).
        locals_out = self_proxy.get_compute_locals()
        ah         = locals_out.get("auto_highlight")
        if ah is None:
            ah = True
        ar = locals_out.get("auto_refresh")
        if ar is None:
            ar = False

        # ``self.draw = DrawCircle(...) + DrawText(...)`` (or a list of items)
        # flattens to the ordered command list the override replays.
        commands = []
        drawing  = locals_out.get("draw")
        if drawing is not None:
            try:
                commands = draw_types.to_commands(drawing)
            except Exception as exc:
                # Same path a compute error takes, so a malformed drawing shows
                # up in the Log panel instead of drawing nothing in silence.
                from mpynode._common.compute.base_contract import (
                    broadcast_compute_error)

                broadcast_compute_error(
                    "mPyLocator", "self.draw: %s" % (exc,),
                    declared_names=set(input_map))
                commands = []

        # Measured HERE, off the drawing we just built, so boundingBox() costs
        # nothing and never re-runs the user expression.
        self._draw_bounds = command_bounds(commands)

        return {
            "commands":       commands,
            "auto_highlight": bool(ah),
            "auto_refresh":   bool(ar),
            # Node-WIDE precise-hover opt-in: hover-test every polygon patch
            # this gizmo draws. A single patch can opt in on its own with
            # ``DrawMesh(..., precise_hover=True)``; the two compose.
            "precise_hover": bool(locals_out.get("precise_hover")),
        }

    # NOTE: mPyLocator has NO compute() for user OUTPUTS. MPxLocatorNode (a DAG
    # shape) does not dispatch compute() for runtime-added output plugs --
    # verified in Maya 2024 standalone AND 2026 GUI (a plain mPyNode computes;
    # the locator never does). For output math, drive a downstream mPyNode. User
    # INPUTS work (read in evaluateDrawItems above). setDependentsDirty IS
    # overridden -- not to dirty an output (there is none) but to force a
    # viewport redraw when an input is dirtied, which is how a draw-only node
    # honours the "input dirtied -> node re-evaluates" contract.

    # Internal plugs whose change must force a redraw (mirrors the transform's
    # _MATRIX_DIRTY_TRIGGERS). User INPUT attrs are added on top at runtime from
    # _inputAttrs. NB the locator sources ``time`` from MAnimControl in the draw
    # override, not a _timeIn plug, so time changes redraw via the global
    # per-frame viewport refresh, not this path.
    _DRAW_DIRTY_TRIGGERS = frozenset(
        {"_computeSource", "_storedVarsData", "_inputAttrs", "_outputAttrs"}
    )

    def _is_draw_dirty_trigger(self, plug):
        """True if a dirtied ``plug`` should force this locator to redraw.

        A plug qualifies when it is one of the internal driver plugs
        (``_computeSource`` etc.) OR a user-declared INPUT attribute -- user
        inputs feed the draw expression, so any input change must re-run it.
        Compound children / array elements resolve to their ROOT long name
        (``positionMatrix``, ``anchored``, ...), the same normalisation the
        transform's ``_is_matrix_dirty_trigger`` uses.
        """
        try:
            # api2 MFnAttribute.name is a PROPERTY, not a method -- calling it
            # (.name()) raises "'str' object is not callable", which the except
            # below would swallow into a blanket False, silently disabling the
            # gate. (api1's twin helper uses .name() because there it IS a
            # method -- the two APIs differ here.)
            plug_name = om.MFnAttribute(plug.attribute()).name
        except Exception:
            return False
        if plug_name in self._DRAW_DIRTY_TRIGGERS:
            return True
        try:
            root = plug.partialName(useLongNames=True).split(".")[0].split("[")[0]
        except Exception:
            root = plug_name
        if root in self._DRAW_DIRTY_TRIGGERS:
            return True
        try:
            ia = (
                om.MFnDependencyNode(self.thisMObject())
                .findPlug("_inputAttrs", True)
                .asString()
            )
        except Exception:
            ia = ""
        if not ia:
            return False
        try:
            input_map = serialization.decode_attr_map(ia)
        except Exception:
            return False
        return root in input_map or plug_name in input_map

    def setDependentsDirty(self, plug, affected_plugs):
        """Force a viewport redraw whenever an INPUT plug is dirtied.

        The directive is firm: when an input plug is dirtied -- via ``setAttr``
        OR an incoming connection updating its value -- the node MUST
        re-evaluate. A draw-only locator has no DG output to dirty (Maya never
        dispatches compute() for its runtime outputs, see the NOTE above), so
        appending to ``affected_plugs`` accomplishes nothing; "re-evaluate" for
        a locator means re-run the draw expression, which happens in
        ``prepareForDraw``. But Maya only calls ``prepareForDraw`` when the
        node's render item is marked dirty, and a runtime-added INPUT attr is
        not wired to anything Maya recognises as draw-affecting -- so without
        this an input change leaves the gizmo frozen until some unrelated
        refresh (exactly what the opt-in 30 fps ``auto_refresh`` poll was
        compensating for). Marking the geometry draw dirty here makes the gizmo
        re-evaluate the moment any input changes -- no poll required.

        ``MRenderer.setGeometryDrawDirty`` only flags the VP2 render item; it is
        NOT a DG mutation. That distinction is why this is safe from inside dirty
        propagation where ``cmds.dgdirty`` was not: ``dgdirty`` re-enters dirty
        propagation and crashed (SIGSEGV in ``TdgDirtyAction``) under the 2026
        Evaluation Manager -- the very reason the old MNodeMessage ``auto_dirty``
        callback was removed. This call touches only the render subsystem.
        Everything is wrapped in try/except so a redraw hiccup (e.g. no VP2 in a
        batch session) can never crash dirty propagation.
        """
        from mpynode._common.plugs import dirty_affects

        # A SUSPENDED node (nodeState Has No Effect / Blocking -- Convert to
        # C++ sets it on the idle Python node, a user may too) forwards
        # nothing. The Evaluation Manager evaluates every user output an
        # animated input dirties whether or not anything reads it -- a full
        # expression run per frame on a node meant to be idle (Mesh Maze's
        # int solutionSteps after Convert to C++, measured 2026-09-14).
        if dirty_affects.api2_dirty_gate(self, plug):
            return
        try:
            if self._is_draw_dirty_trigger(plug):
                omr.MRenderer.setGeometryDrawDirty(self.thisMObject())
        except Exception:
            pass


# ===========================================================================
# VP2 draw override -- bundled with the node (same pattern as mpy_file.py +
# MPyFileOverride). Registered separately at plugin load via
# MDrawRegistry.registerDrawOverrideCreator against DRAW_DB_CLASSIFICATION.
# ===========================================================================


class MPyLocatorDrawData(om.MUserData):
    """Per-frame data passed from prepareForDraw -> addUIDrawables."""

    def __init__(self):
        super().__init__()  # MUserData base; deleteAfterUse default True
        # Ordered draw commands for this frame, one per authored item, replayed
        # front-to-back by addUIDrawables so authoring order IS draw order.
        self.commands: list = []
        # Selection tinting: if is_selected AND auto_highlight, addUIDrawables
        # tints every per-buffer color with sel_color -- its RGB only, each
        # element keeping its own alpha (see _tinted).
        self.is_selected:    bool = False
        self.auto_highlight: bool = True
        self.sel_color = None  # om.MColor or None
        # Camera position in the locator's local frame -- the same space as the
        # draw-buffer points. Used by _draw_polygons for ``cull_backfaces``.
        self.view_pos_local = (0.0, 0.0, 1.0)
        # Per-slot draw-space support (see draw_buffers.normalize_space).
        # ``local_ppu``: screen PIXELS per OBJECT unit at the node's depth, to
        # auto-scale bitmap TEXT in local space (None -> text ``sizes`` are
        # pixels). ``screen_ctx``: matrices + viewport to project object points
        # to pixels for ``space="screen"`` slots (None -> screen slots draw local).
        self.local_ppu  = None
        self.screen_ctx = None


class MPyLocatorDrawOverride(omr.MPxDrawOverride):
    @staticmethod
    def creator(obj):
        return MPyLocatorDrawOverride(obj)

    def __init__(self, obj):
        # isAlwaysDirty=True: regenerate the draw data on EVERY refresh, not
        # just on node change. This is what makes view-dependent drawing --
        # chiefly ``cull_backfaces`` -- update live as the camera orbits, since
        # prepareForDraw recomputes ``view_pos_local`` each draw. With it False
        # the cached draw is reused and culling freezes at the first-draw view.
        # Cost is one (typically light) expression eval per draw.
        super().__init__(obj, None, True)

    def supportedDrawAPIs(self):
        return omr.MRenderer.kAllDevices

    def hasUIDrawables(self):
        return True

    def isTransparent(self):
        """Declare this override as producing transparent geometry.

        VP2 routes transparent overrides through the alpha-blended
        pass, which is the only path where ``MColor`` alpha values
        below 1.0 actually blend with the underlying scene. Without
        this, a polygons buffer whose ``colors`` carries
        ``alpha=0.35`` renders as fully opaque.

        Routing fully-opaque draws through the transparent pass is
        cheap (locators emit a handful of primitives) and avoids a
        per-frame state-flip when the user expression toggles between
        transparent and opaque states (e.g. wireframe vs shaded).
        """
        return True

    def prepareForDraw(self, obj_path, camera_path, frame_context, old_data):
        """Build the draw data for this frame."""
        data = old_data
        if not isinstance(data, MPyLocatorDrawData):
            data = MPyLocatorDrawData()

        node_obj = obj_path.node()
        # Expression context: current frame. MAnimControl lives in
        # OpenMayaAnim, not OpenMaya -- read through ``om`` it raised
        # AttributeError into this except and ``self.time`` was ALWAYS 0.0 in
        # the interpreted locator (the compiled node read the real frame), so
        # every template's timeline term was silently dead. The fallback stays
        # for a headless context with no anim control.
        try:
            time_value = oma.MAnimControl.currentTime().value
        except Exception:
            time_value = 0.0

        # Pull out the MPyLocator instance (MPx subclass).
        try:
            mpx_node = omr.MPxDrawOverride.getMpxFromObject(node_obj)
        except AttributeError:
            fn       = om.MFnDependencyNode(node_obj)
            mpx_node = fn.userNode()

        # Per-frame display state. MGeometryUtilities is the canonical source
        # for the selection status enum AND the theme-following wireframe color.
        # It does NOT report hover -- displayStatus has no "cursor is over me"
        # value (kHilite is component-highlight) -- so ``self.hovered`` comes
        # from hover_tracker's cursor ray on a session-level timer.
        from mpynode._common.draw import hover_tracker

        hover_tracker.ensure_started()  # idempotent, GUI-only
        is_hovered = hover_tracker.is_hovered(node_obj)
        try:
            status       = omr.MGeometryUtilities.displayStatus(obj_path)
            is_lead      = status == omr.MGeometryUtilities.kLead
            is_active    = status == omr.MGeometryUtilities.kActive
            is_selected  = is_lead or is_active
            sel_color_mc = omr.MGeometryUtilities.wireframeColor(obj_path)
            sel_color_tuple = (
                float(sel_color_mc.r),
                float(sel_color_mc.g),
                float(sel_color_mc.b),
                float(sel_color_mc.a),
            )
        except Exception:
            is_lead         = False
            is_active       = False
            is_selected     = False
            sel_color_mc    = None
            sel_color_tuple = (1.0, 1.0, 1.0, 1.0)

        # displayStatus on a SHAPE doesn't reliably report kLead/kActive when
        # only its parent TRANSFORM is selected (it can read kDormant once the
        # cursor leaves), so a "stay big while selected" gizmo relaxes on mouse-
        # out. Confirm against the active selection list: shape OR its parent.
        if not is_selected:
            try:
                active = om.MGlobal.getActiveSelectionList()
                if active.length():
                    sel_hit = active.hasItem(obj_path)
                    if not sel_hit:
                        transform_path = om.MDagPath(obj_path)
                        transform_path.pop()  # shape -> parent transform
                        sel_hit = active.hasItem(transform_path)
                    if sel_hit:
                        is_selected = True
            except Exception:
                pass

        try:
            harvest = (
                mpx_node.evaluateDrawItems(
                    time_value,
                    selected        = is_selected,
                    is_lead         = is_lead,
                    selection_color = sel_color_tuple,
                    hovered         = is_hovered,
                )
                or {}
            )
        except Exception:
            harvest = {}
        commands       = harvest.get("commands") or []
        auto_highlight = bool(harvest.get("auto_highlight", True))
        # enable/disable the idle-refresh timer.
        auto_refresh = bool(harvest.get("auto_refresh", False))
        try:
            from mpynode._common.draw import draw_refresh as _dr

            if auto_refresh:
                _dr.enable(node_obj)
            else:
                _dr.disable(node_obj)
        except Exception:
            # Never crash the draw on a timer-management hiccup.
            pass

        # Opt-in WORLD-SPACE geometry: when an item sets ``world_space=True`` its
        # points are already in world space (e.g. from a node's worldMesh) and
        # must render there REGARDLESS of the locator's own transform. The draw
        # manager always applies the locator world matrix M, so pre-multiply by
        # M^-1 here: M * (M^-1 * P_world) == P_world. This lets the locator
        # transform drive a rig without double-moving the verts -- the gizmo just
        # follows the deformed mesh. Because BOTH this inverse and the M the draw
        # manager applies come from the SAME obj_path evaluation they cancel
        # EXACTLY, even if the parent worldMatrix is cache-stale this frame.
        #
        # Done BEFORE the hover cache + draw so BOTH use the same local points:
        # hover_tracker re-applies M^-1 to the cursor ray against these cached
        # "local" tris, so picking still matches what's drawn.
        _WORLD_KEYS = {"polygons": ("points",), "lines": ("starts", "ends")}
        w2l         = None                    # one inverse per frame, computed lazily
        for cmd in commands:
            buf  = cmd.get("buffer")
            keys = _WORLD_KEYS.get(cmd.get("slot"))
            if not buf or keys is None or not buf.pop("world_space", False):
                continue
            try:
                if w2l is None:
                    m = obj_path.inclusiveMatrixInverse()
                    w2l = np.array(
                        [m[i] for i in range(16)], dtype=np.float64
                    ).reshape(4, 4)
                for _key in keys:
                    pts = buf.get(_key)
                    if pts is None:
                        continue
                    pts = np.asarray(pts, dtype=np.float64)
                    if pts.ndim == 2 and pts.shape[1] == 3 and pts.shape[0]:
                        homog        = np.empty((pts.shape[0], 4), dtype=np.float64)
                        homog[:, :3] = pts
                        homog[:, 3]  = 1.0
                        buf[_key]    = (homog @ w2l)[:, :3]
            except Exception:
                pass

        # Opt-in precise hover: cache this frame's (full, pre-cull) triangle soup
        # of every patch that asked, so hover_tracker ray-tests the real shape
        # instead of the bbox. Per-PATCH, so a gizmo can keep decoration out of
        # the pick; ``self.precise_hover = True`` opts the whole node in.
        node_precise = bool(harvest.get("precise_hover"))
        try:
            soups = []
            for cmd in commands:
                buf = cmd.get("buffer")
                if cmd.get("slot") != "polygons" or not buf:
                    continue
                if not (node_precise or buf.get("precise_hover")):
                    continue
                tri_pts = fan_triangulate(
                    buf.get("points"), buf.get("indices"), buf.get("counts")
                )
                if tri_pts.shape[0] >= 3:
                    soups.append(tri_pts.reshape(-1, 3, 3))
            if soups:
                hover_tracker.set_shape(node_obj, np.concatenate(soups))
            else:
                hover_tracker.clear_shape(node_obj)
        except Exception:
            pass
        data.commands       = commands
        data.is_selected    = is_selected
        data.auto_highlight = auto_highlight
        data.sel_color      = sel_color_mc

        # Camera position in the locator's local frame, for view-dependent
        # backface culling. inclusiveMatrixInverse() takes world -> shape-local;
        # the camera world position is the translation column of
        # camera_path.inclusiveMatrix().
        try:
            cam_world = camera_path.inclusiveMatrix()
            cam_pos_world = om.MPoint(
                cam_world[12], cam_world[13], cam_world[14]
            )
            loc_w2l   = obj_path.inclusiveMatrixInverse()
            cam_local = cam_pos_world * loc_w2l
            data.view_pos_local = (
                float(cam_local.x),
                float(cam_local.y),
                float(cam_local.z),
            )
        except Exception:
            # Fallback: a point up the +Z axis. Worst case the culling result
            # is camera-independent; nothing crashes.
            data.view_pos_local = (0.0, 0.0, 10.0)

        # ---- per-slot draw-space context (local text scaling + screen) ----
        # Both derive from this frame's world->clip matrix + viewport. One
        # guarded block so a headless draw (no frame_context matrices) degrades:
        # local_ppu None -> text sizes are pixels; screen_ctx None -> draw local.
        data.local_ppu  = None
        data.screen_ctx = None
        try:
            vpm       = frame_context.getMatrix(omr.MFrameContext.kViewProjMtx)
            view_proj = [vpm[i] for i in range(16)]
            dims      = frame_context.getViewportDimensions()  # (x, y, w, h)
            vp_w      = float(dims[2])
            vp_h      = float(dims[3])
            ow        = obj_path.inclusiveMatrix()
            obj_world = [ow[i] for i in range(16)]
            data.screen_ctx = {
                "obj_world": obj_world,
                "view_proj": view_proj,
                "vp_w":      vp_w,
                "vp_h":      vp_h,
            }
            # local text scale: pixels per OBJECT unit at the node's depth.
            anchor_world = (obj_world[12], obj_world[13], obj_world[14])
            cam_m        = camera_path.inclusiveMatrix()
            up_world     = (cam_m[4], cam_m[5], cam_m[6])  # camera up axis (row 1)
            ppw          = pixels_per_world_unit(view_proj, vp_h, anchor_world, up_world)
            if ppw is not None:
                data.local_ppu = ppw * matrix_uniform_scale(obj_world)
        except Exception:
            data.local_ppu  = None
            data.screen_ctx = None
        return data

    def addUIDrawables(self, obj_path, draw_manager, frame_context, data):
        if not isinstance(data, MPyLocatorDrawData):
            return
        commands = data.commands
        if not commands:
            return

        # Framework auto-highlight: when selected AND auto_highlight is on,
        # every draw call below tints its per-element color with Maya's
        # selection color -- RGB only, each element keeping its own alpha, so a
        # translucent gizmo stays translucent while selected (see _tinted).
        # Just an MColor or None; each _draw_X checks it.
        override_color = None
        if data.is_selected and data.auto_highlight and data.sel_color is not None:
            override_color = data.sel_color

        screen_ctx = data.screen_ctx
        local_ppu  = data.local_ppu
        draw_manager.beginDrawable()
        try:
            # Replay IN ORDER -- the point of the ordered transport. Bucketing
            # by type would silently reorder the drawing and buys nothing: each
            # _draw_X already issues one setColor + primitive call per element.
            for cmd in commands:
                slot = cmd.get("slot")
                buf  = cmd.get("buffer")
                if not buf:
                    continue
                if slot == "lines":
                    self._draw_lines(
                        draw_manager, buf, override_color,
                        screen_ctx=screen_ctx,
                    )
                elif slot == "points":
                    self._draw_points(
                        draw_manager, buf, override_color,
                        screen_ctx=screen_ctx,
                    )
                elif slot == "polygons":
                    self._draw_polygons(
                        draw_manager,
                        buf,
                        view_pos_local        = data.view_pos_local,
                        is_selected           = data.is_selected,
                        global_auto_highlight = data.auto_highlight,
                        sel_color             = data.sel_color,
                        screen_ctx            = screen_ctx,
                    )
                elif slot == "shapes":
                    self._draw_shapes(
                        draw_manager, buf, override_color,
                        screen_ctx=screen_ctx,
                    )
                elif slot == "text":
                    self._draw_text(
                        draw_manager, buf, override_color,
                        local_ppu=local_ppu, screen_ctx=screen_ctx,
                    )
        finally:
            draw_manager.endDrawable()

    # ------------------------------------------------------------------
    # Per-buffer dispatch helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mcolor(rgba) -> om.MColor:
        return om.MColor(
            (
                float(rgba[0]),
                float(rgba[1]),
                float(rgba[2]),
                float(rgba[3]) if len(rgba) > 3 else 1.0,
            )
        )

    @staticmethod
    def _tinted(override, rgba) -> om.MColor:
        """The selection highlight applied to ONE element: the tint replaces
        hue, never opacity.

        Maya's wireframe colour is opaque, so tinting with it wholesale turns a
        deliberately translucent drawing -- a faded band, a ghosted guide --
        solid the moment the node is selected, which reads as the gizmo
        changing shape rather than changing state. Keeping each element's own
        alpha means selecting something changes what colour it is, not how much
        of the scene you can see through it."""
        return om.MColor(
            (
                float(override.r),
                float(override.g),
                float(override.b),
                float(rgba[3]) if len(rgba) > 3 else 1.0,
            )
        )

    @staticmethod
    def _project_screen(points, screen_ctx):
        """Object-space ``(N, 3)`` points -> ``(pixels (N, 2), valid (N,))``
        for ``space="screen"`` slots, via this frame's screen context
        (object -> world -> clip -> pixel). Rows where ``valid`` is False are
        at/behind the camera and must be skipped by the caller."""
        return project_object_points_to_pixels(
            points,
            screen_ctx["obj_world"],
            screen_ctx["view_proj"],
            screen_ctx["vp_w"],
            screen_ctx["vp_h"],
        )

    @classmethod
    def _draw_lines(cls, dm, buf, override=None, screen_ctx=None):
        try:
            starts = np.asarray(buf.get("starts"), dtype=np.float32)
            ends   = np.asarray(buf.get("ends"), dtype=np.float32)
            if starts.ndim!= 2 or starts.shape[1]!= 3:
                return
            if ends.shape!= starts.shape:
                return
            n = starts.shape[0]
            if n == 0:
                return
            colors = normalize_color(buf.get("colors"), n)
        except Exception:
            return

        # screen space: project both endpoints to pixels + draw line2d at a
        # constant on-screen size (zoom/distance independent).
        if normalize_space(buf.get("space")) == "screen" and screen_ctx is not None:
            try:
                ps, vs = cls._project_screen(starts, screen_ctx)
                pe, ve = cls._project_screen(ends, screen_ctx)
            except Exception:
                ps = pe = None
            if ps is not None:
                for i in range(n):
                    if not (vs[i] and ve[i]):
                        continue
                    dm.setColor(
                        cls._tinted(override, colors[i])
                        if override is not None else cls._mcolor(colors[i])
                    )
                    try:
                        dm.line2d(
                            om.MPoint(float(ps[i, 0]), float(ps[i, 1]), 0.0),
                            om.MPoint(float(pe[i, 0]), float(pe[i, 1]), 0.0),
                        )
                    except Exception:
                        pass
                return

        for i in range(n):
            if override is not None:
                dm.setColor(cls._tinted(override, colors[i]))
            else:
                dm.setColor(cls._mcolor(colors[i]))
            dm.line(
                om.MPoint(
                    float(starts[i, 0]), float(starts[i, 1]), float(starts[i, 2])
                ),
                om.MPoint(float(ends[i, 0]), float(ends[i, 1]), float(ends[i, 2])),
            )

    @classmethod
    def _draw_points(cls, dm, buf, override=None, screen_ctx=None):
        try:
            positions = np.asarray(buf.get("positions"), dtype=np.float32)
            if positions.ndim!= 2 or positions.shape[1]!= 3:
                return
            n = positions.shape[0]
            if n == 0:
                return
            colors = normalize_color(buf.get("colors"), n)
        except Exception:
            return
        sizes     = buf.get("sizes")
        sizes_arr = None
        if sizes is not None:
            sa = np.asarray(sizes, dtype=np.float32)
            if sa.ndim == 0:
                sizes_arr = np.full((n,), float(sa), dtype=np.float32)
            elif sa.shape == (n,):
                sizes_arr = sa

        # screen space: project to pixels + draw point2d (point SIZE is
        # already in pixels, so it is unchanged between spaces).
        if normalize_space(buf.get("space")) == "screen" and screen_ctx is not None:
            try:
                px, valid = cls._project_screen(positions, screen_ctx)
            except Exception:
                px = None
            if px is not None:
                for i in range(n):
                    if not valid[i]:
                        continue
                    dm.setColor(
                        cls._tinted(override, colors[i])
                        if override is not None else cls._mcolor(colors[i])
                    )
                    if sizes_arr is not None:
                        dm.setPointSize(point_pixel_size(sizes_arr[i]))
                    try:
                        dm.point2d(om.MPoint(float(px[i, 0]), float(px[i, 1]), 0.0))
                    except Exception:
                        pass
                return

        for i in range(n):
            if override is not None:
                dm.setColor(cls._tinted(override, colors[i]))
            else:
                dm.setColor(cls._mcolor(colors[i]))
            if sizes_arr is not None:
                dm.setPointSize(point_pixel_size(sizes_arr[i]))
            dm.point(
                om.MPoint(
                    float(positions[i, 0]),
                    float(positions[i, 1]),
                    float(positions[i, 2]),
                )
            )

    # Fill-color source keys, in precedence order (most specific first).
    _FILL_KEYS = ("face_vertex_colors", "vertex_colors", "face_colors", "colors")

    @classmethod
    def _draw_polygons(cls, dm, buf, *, view_pos_local=None,
                       is_selected=False, global_auto_highlight=True,
                       sel_color=None, screen_ctx=None):
        """Draw a polygon buffer: optional shaded fill (uniform /
        per-face / per-vertex / face-varying) plus an optional wireframe
        overlay, both honoring backface culling and per-aspect selection
        highlighting."""
        try:
            points    = np.asarray(buf.get("points"),  dtype=np.float32)
            o_indices = np.asarray(buf.get("indices"), dtype=np.int64)
            o_counts  = np.asarray(buf.get("counts"),  dtype=np.int64)
            if points.ndim != 2 or points.shape[1] != 3:
                return
            if o_indices.ndim != 1 or o_counts.ndim != 1 or o_counts.shape[0] == 0:
                return
        except Exception:
            return

        # screen space: project verts to pixels once, then reuse the fill +
        # wireframe helpers with 2D primitives. Backface culling is meaningless
        # here so it's skipped (world_space likewise). Per-face / per-vertex /
        # face-varying colors and wireframe still work -- topology + color only.
        if normalize_space(buf.get("space")) == "screen" and screen_ctx is not None:
            try:
                px, _valid = cls._project_screen(points, screen_ctx)
            except Exception:
                px = None
            if px is not None and px.shape[0] == points.shape[0]:
                pix3        = np.zeros((px.shape[0], 3), dtype=np.float32)
                pix3[:, :2] = px
                hl_fill     = bool(buf.get("highlight_fill", global_auto_highlight))
                hl_wire     = bool(buf.get("highlight_wire", global_auto_highlight))
                fill_override = (
                    sel_color if (is_selected and hl_fill and sel_color is not None)
                    else None
                )
                wire_override = (
                    sel_color if (is_selected and hl_wire and sel_color is not None)
                    else None
                )
                try:
                    cls._draw_poly_fill(
                        dm, buf, pix3, o_indices, o_counts, o_counts,
                        None, None, fill_override, use_2d=True,
                    )
                except Exception as exc:
                    sys.stderr.write(
                        f"[mPyLocator] polygons(screen) fill failed: {exc}\n"
                    )
                try:
                    cls._draw_poly_wire(
                        dm, buf, pix3, o_indices, o_counts, None,
                        wire_override, sel_color, use_2d=True,
                    )
                except Exception as exc:
                    sys.stderr.write(
                        f"[mPyLocator] polygons(screen) wireframe failed: {exc}\n"
                    )
                return

        # ---- backface cull (shared by fill + wireframe) ----
        # Keep the per-face mask + kept-corner indices so per-face /
        # face-varying colors can be subset to match the culled mesh.
        indices, counts = o_indices, o_counts
        keep_mask       = None
        kept_corner_idx = None
        if buf.get("cull_backfaces"):
            view_pos = (
                view_pos_local if view_pos_local is not None else (0.0, 0.0, 10.0)
            )
            try:
                keep_mask = cull_backfaces_mask(points, o_indices, o_counts, view_pos)
                indices, counts, kept_corner_idx = apply_face_mask(
                    o_indices, o_counts, keep_mask
                )
            except Exception:
                indices, counts, keep_mask, kept_corner_idx = (
                    o_indices, o_counts, None, None
                )
            if counts.shape[0] == 0:
                return

        # Per-aspect selection highlight (default = global auto_highlight).
        hl_fill = bool(buf.get("highlight_fill", global_auto_highlight))
        hl_wire = bool(buf.get("highlight_wire", global_auto_highlight))
        fill_override = (
            sel_color if (is_selected and hl_fill and sel_color is not None) else None
        )
        wire_override = (
            sel_color if (is_selected and hl_wire and sel_color is not None) else None
        )

        try:
            cls._draw_poly_fill(
                dm, buf, points, indices, counts, o_counts,
                keep_mask, kept_corner_idx, fill_override,
            )
        except Exception as exc:
            sys.stderr.write(f"[mPyLocator] polygons fill failed: {exc}\n")

        try:
            cls._draw_poly_wire(
                dm, buf, points, indices, counts, keep_mask, wire_override, sel_color,
            )
        except Exception as exc:
            sys.stderr.write(f"[mPyLocator] polygons wireframe failed: {exc}\n")

    @classmethod
    def _draw_poly_fill(cls, dm, buf, points, indices, counts, o_counts,
                        keep_mask, kept_corner_idx, fill_override, use_2d=False):
        # 2D (screen-space) fill uses mesh2d; 3D (object-space) uses mesh.
        mesh_fn  = dm.mesh2d if use_2d else dm.mesh
        provided = [k for k in cls._FILL_KEYS if buf.get(k) is not None]
        if not provided:
            return  # no fill
        key = provided[0]  # _FILL_KEYS is precedence-ordered
        if len(provided) > 1:
            sys.stderr.write(
                "[mPyLocator] polygons: multiple fill color sources "
                f"{provided}; using {key!r} (precedence face_vertex_colors > "
                "vertex_colors > face_colors > colors).\n"
            )

        tri_pts = fan_triangulate(points, indices, counts)
        if tri_pts.shape[0] == 0:
            return
        mpts = om.MPointArray(tri_pts.tolist())

        # Uniform fast path: one setColor + one mesh. A selection tint rides on
        # top of it and keeps the buffer's own alpha (see _tinted).
        if key == "colors":
            base = normalize_color(buf.get("colors"), 1)[0]
            dm.setColor(
                cls._tinted(fill_override, base)
                if fill_override is not None else cls._mcolor(base)
            )
            try:
                mesh_fn(omr.MUIDrawManager.kTriangles, mpts)
            except Exception:
                pass
            return

        # Per-corner color array (face / vertex / face-varying).
        if key == "face_colors":
            cf = normalize_color(buf.get("face_colors"), int(o_counts.shape[0]))
            if keep_mask is not None:
                cf = cf[keep_mask]
            corner = expand_face_colors_to_triangles(cf, counts)
        elif key == "vertex_colors":
            vc = normalize_color(buf.get("vertex_colors"), int(points.shape[0]))
            pt_idx, _ = triangle_corner_indices(indices, counts)
            corner = vc[pt_idx]
        else:  # face_vertex_colors
            o_corners = int(np.asarray(o_counts, dtype=np.int64).sum())
            fvc       = normalize_color(buf.get("face_vertex_colors"), o_corners)
            if kept_corner_idx is not None:
                fvc = fvc[kept_corner_idx]
            _, fc_idx = triangle_corner_indices(indices, counts)
            corner = fvc[fc_idx]

        if corner.shape[0] != tri_pts.shape[0]:
            return
        # Selected: tint per CORNER instead of one flat setColor, so a patch
        # keeps its own alpha ramp while it is highlighted (see _tinted).
        if fill_override is not None:
            corner       = np.array(corner, dtype=np.float32, copy=True)
            corner[:, 0] = float(fill_override.r)
            corner[:, 1] = float(fill_override.g)
            corner[:, 2] = float(fill_override.b)
        mcols = om.MColorArray(corner.tolist())
        try:
            mesh_fn(omr.MUIDrawManager.kTriangles, mpts, None, mcols)
        except Exception:
            pass

    @classmethod
    def _draw_poly_wire(cls, dm, buf, points, indices, counts, keep_mask,
                        wire_override, sel_color, use_2d=False):
        # 2D (screen-space) edges use line2d; 3D (object-space) uses line.
        line_fn = dm.line2d if use_2d else dm.line
        wire    = buf.get("wireframe")
        if wire is None:
            return
        # Check sequence first, else coerce to bool (True/1 => system color on,
        # False/0 => off).
        is_seq = isinstance(wire, (list, tuple, np.ndarray))
        if not is_seq and not bool(wire):
            return

        # Only DEFAULT to 1.0 when the key is absent / None -- an explicit 0 (or
        # negative) means "hide the wireframe", so skip entirely. (A previous
        # ``... or 1.0`` fallback coerced 0 -> 1, so width 0 looked like 1.)
        width = buf.get("wireframe_width", 1.0)
        width = 1.0 if width is None else float(width)
        if width <= 0.0:
            return

        # Outline mode: draw ONLY boundary edges (used by a single face) -- the
        # patch silhouette, no interior grid. Built from the same `points` as
        # the fill, so it inherits world_space / culling. `edge_faces` keeps
        # each boundary edge's owning face for the per-face color path below.
        if bool(buf.get("wireframe_boundary_only")):
            boundary, edge_faces = region_boundary_edges(indices, counts)
            if boundary.shape[0] == 0:
                return
            starts = points[boundary[:, 0]]
            ends   = points[boundary[:, 1]]
        else:
            starts, ends = build_edge_point_pairs(points, indices, counts)
            edge_faces = None
        n_edges = int(starts.shape[0])
        if n_edges == 0:
            return

        edge_colors = None  # (E, 4) per-edge
        single      = None  # one MColor for the whole wireframe
        if not is_seq:
            # True / truthy non-sequence -> system wireframe color.
            single = sel_color if sel_color is not None else cls._mcolor((1, 1, 1, 1))
        else:
            arr = np.asarray(wire, dtype=np.float32)
            if arr.ndim == 1:
                single = cls._mcolor(normalize_color(wire, 1)[0])
            else:
                o_faces = (
                    int(keep_mask.shape[0]) if keep_mask is not None
                    else int(counts.shape[0])
                )
                wf = normalize_color(wire, o_faces)
                if keep_mask is not None:
                    wf = wf[keep_mask]
                ef = edge_faces if edge_faces is not None else edge_face_indices(counts)
                if ef.shape[0] == n_edges:
                    edge_colors = wf[ef]
                else:
                    single = cls._mcolor((1, 1, 1, 1))

        # The selection tint goes on LAST and keeps each edge's own alpha (see
        # _tinted): selecting a ghosted outline must not make it solid.
        if wire_override is not None:
            if edge_colors is not None:
                edge_colors       = np.array(edge_colors, dtype=np.float32, copy=True)
                edge_colors[:, 0] = float(wire_override.r)
                edge_colors[:, 1] = float(wire_override.g)
                edge_colors[:, 2] = float(wire_override.b)
            elif single is not None:
                single = cls._tinted(
                    wire_override,
                    (single.r, single.g, single.b, single.a),
                )
            else:
                single = wire_override

        # NOTE: the API-2.0 MUIDrawManager method is setLineWidth (there is
        # no lineWidth) -- calling the wrong name silently no-ops here.
        try:
            dm.setLineWidth(width)
        except Exception:
            pass

        if edge_colors is None:
            if single is not None:
                dm.setColor(single)
            for i in range(n_edges):
                line_fn(
                    om.MPoint(float(starts[i, 0]), float(starts[i, 1]), float(starts[i, 2])),
                    om.MPoint(float(ends[i, 0]), float(ends[i, 1]), float(ends[i, 2])),
                )
        else:
            for i in range(n_edges):
                dm.setColor(cls._mcolor(edge_colors[i]))
                line_fn(
                    om.MPoint(float(starts[i, 0]), float(starts[i, 1]), float(starts[i, 2])),
                    om.MPoint(float(ends[i, 0]), float(ends[i, 1]), float(ends[i, 2])),
                )

    @classmethod
    def _draw_shapes(cls, dm, buf, override=None, screen_ctx=None):
        try:
            kinds   = list(buf.get("kinds") or [])
            centers = np.asarray(buf.get("centers"), dtype=np.float32)
            if centers.ndim!= 2 or centers.shape[1]!= 3:
                return
            n = centers.shape[0]
            if n == 0 or len(kinds)!= n:
                return
            colors = normalize_color(buf.get("colors"), n)
        except Exception:
            return

        # screen space: only the flat ``circle`` maps to a 2D primitive
        # (circle2d, radius in pixels). 3D solids (sphere/box/cone/cylinder)
        # have no 2D analog and fall back to local drawing with a one-time note.
        screen = (
            normalize_space(buf.get("space")) == "screen" and screen_ctx is not None
        )
        centers_px    = None
        centers_valid = None
        if screen:
            try:
                centers_px, centers_valid = cls._project_screen(centers, screen_ctx)
            except Exception:
                screen = False
        noted_fallback = False

        radii_in = buf.get("radii")
        if radii_in is None:
            radii = np.ones((n,), dtype=np.float32)
        else:
            ra = np.asarray(radii_in, dtype=np.float32)
            if ra.ndim == 0:
                radii = np.full((n,), float(ra), dtype=np.float32)
            elif ra.shape == (n,):
                radii = ra
            else:
                radii = np.ones((n,), dtype=np.float32)

        axes_in = buf.get("axes")
        if axes_in is None:
            axes = None
        else:
            ax   = np.asarray(axes_in, dtype=np.float32)
            axes = ax if (ax.ndim == 2 and ax.shape == (n, 3)) else None

        filled_in = buf.get("filled")
        if filled_in is None:
            filled = np.ones((n,), dtype=bool)
        else:
            fi = np.asarray(filled_in)
            if fi.ndim == 0:
                filled = np.full((n,), bool(fi))
            elif fi.shape == (n,):
                filled = fi.astype(bool)
            else:
                filled = np.ones((n,), dtype=bool)

        for i in range(n):
            kind = str(kinds[i]).lower()
            if override is not None:
                dm.setColor(cls._tinted(override, colors[i]))
            else:
                dm.setColor(cls._mcolor(colors[i]))
            r = float(radii[i])
            f = bool(filled[i])

            if screen:
                if not centers_valid[i]:
                    continue
                if kind == "circle":
                    # circle2d(center_px, radius_px, filled) -- constant size.
                    try:
                        dm.circle2d(
                            om.MPoint(
                                float(centers_px[i, 0]), float(centers_px[i, 1]), 0.0
                            ),
                            r,
                            f,
                        )
                    except Exception:
                        pass
                    continue
                if not noted_fallback:
                    sys.stderr.write(
                        "[mPyLocator] shapes: 'screen' space renders only "
                        "'circle' as a 2D primitive; %r falls back to local "
                        "(object-space) drawing.\n" % kind
                    )
                    noted_fallback = True
                # fall through to the local 3D draw below.

            center = om.MPoint(
                float(centers[i, 0]), float(centers[i, 1]), float(centers[i, 2])
            )
            axis = (
                om.MVector(float(axes[i, 0]), float(axes[i, 1]), float(axes[i, 2]))
                if axes is not None
                else om.MVector(0.0, 1.0, 0.0)
            )
            try:
                if kind == "sphere":
                    dm.sphere(center, r, f)
                elif kind == "box":
                    # box(center, upAxis, sideAxis, width/2, height/2, depth/2, filled)
                    side = om.MVector(1.0, 0.0, 0.0)
                    up   = axis
                    dm.box(center, up, side, r, r, r, f)
                elif kind == "cone":
                    dm.cone(center, axis, r, r * 2.0, f)
                elif kind == "cylinder":
                    dm.cylinder(center, axis, r, r * 2.0, 16, f)
                elif kind == "circle":
                    dm.circle(center, axis, r, f)
            except Exception:
                continue

    @classmethod
    def _draw_text(cls, dm, buf, override=None, local_ppu=None, screen_ctx=None):
        try:
            positions = np.asarray(buf.get("positions"), dtype=np.float32)
            strings   = list(buf.get("strings") or [])
            if positions.ndim!= 2 or positions.shape[1]!= 3:
                return
            n = positions.shape[0]
            if n == 0 or len(strings)!= n:
                return
            colors = normalize_color(buf.get("colors"), n)
        except Exception:
            return
        sizes     = buf.get("sizes")
        sizes_arr = None
        if sizes is not None:
            sa = np.asarray(sizes, dtype=np.float32)
            if sa.ndim == 0:
                sizes_arr = np.full((n,), float(sa), dtype=np.float32)
            elif sa.shape == (n,):
                sizes_arr = sa

        # Text always draws via dm.text() (billboarded). The ONLY difference
        # between the two spaces is how the font SIZE is computed, both anchored
        # at the object-space position:
        #   * local (default): ``sizes`` are OBJECT-space glyph heights scaled
        #     to pixels by ``local_ppu``, so text scales WITH the object. Falls
        #     back to pixel ``sizes`` when ``local_ppu`` is unavailable.
        #   * screen: ``sizes`` are constant PIXELS.
        scale_local = (
            normalize_space(buf.get("space")) == "local" and local_ppu is not None
        )
        for i in range(n):
            if override is not None:
                dm.setColor(cls._tinted(override, colors[i]))
            else:
                dm.setColor(cls._mcolor(colors[i]))
            if sizes_arr is not None:
                if scale_local:
                    px = local_text_pixel_size(float(sizes_arr[i]), local_ppu)
                else:
                    px = int(sizes_arr[i])
                try:
                    dm.setFontSize(px)
                except Exception:
                    pass
            dm.text(
                om.MPoint(
                    float(positions[i, 0]),
                    float(positions[i, 1]),
                    float(positions[i, 2]),
                ),
                str(strings[i]),
            )
