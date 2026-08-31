"""Helpers to force a one-shot evaluation on a node so the user sees
the result of an edit immediately.

Used by ``NDScriptTabWidget._saveTab`` after Save / F5, so the
viewport reflects the new expression without waiting for the user
to scrub the timeline or move a connected upstream.

Strategy by node type (best-effort; failures are silent):
  1. Has ``outputGeometry`` plug (deformers): ``dgdirty`` + ``dgeval``
  2. Transform family: the user expression runs inside the custom
     matrix's ``asMatrix()`` (matrix evaluation), NOT when a user output
     is pulled -- so ``dgdirty`` + pull ``worldMatrix`` to fire it.
  3. Has any USER FLOAT input: bump-and-restore by 1e-9 (epsilon-roundtrip)
  4. Has any USER OUTPUT plug: ``dgdirty`` then ``getAttr`` it
  5. Fallback: ``dgdirty`` and hope the viewport pulls

For nodes whose evaluation is owned by a separate solver (mPyIkSolver,
mPyField, mPyEmitter), step 4 is the realistic outcome \u2014 user still
needs to interact with the scene to trigger a fresh solve. That's a
documented limitation of the Save-and-redraw model.
"""

from __future__ import annotations

from maya import cmds


def force_one_eval(py_node) -> None:
    """Force a one-shot eval on the given py_node.

    Best-effort. Never raises.
    """
    try:
        name = py_node.get_name()
    except Exception:
        return

    # Strategy 1: deformer-family
    try:
        if cmds.attributeQuery("outputGeometry", node=name, exists=True):
            cmds.dgdirty(name)
            try:
                cmds.dgeval(f"{name}.outputGeometry[0]")
            except Exception:
                pass
            return
    except Exception:
        pass

    # Strategy 2: transform-family. The expression runs inside the custom
    # matrix's asMatrix(), so pulling a USER OUTPUT (Strategy 4) never fires it.
    # A plain ``dgdirty(node)`` is NOT enough either: Maya caches worldMatrix on
    # a path that only invalidates when a real TRS plug changes, so the cached
    # matrix comes back WITHOUT re-running asMatrix() -> the snapshot lags one
    # step ("press F5 twice" / "nothing on enable"). Same idiom as the
    # transform's own time-change callback: dirty ``.matrix`` AND touch
    # translateX (re-set to its current value) to flush the cache, then pull
    # worldMatrix to run asMatrix(). Gated on the transform family so it can't
    # misfire on locator/other DAG shapes, whose expression is output-driven.
    try:
        inherited = cmds.nodeType(name, inherited=True) or []
        if "transform" in inherited and cmds.attributeQuery(
            "worldMatrix", node=name, exists=True
        ):
            try:
                cmds.dgdirty(f"{name}.matrix")
            except Exception:
                pass
            try:
                tx = cmds.getAttr(f"{name}.translateX")
                cmds.setAttr(f"{name}.translateX", tx)
            except Exception:
                pass
            try:
                cmds.getAttr(f"{name}.worldMatrix[0]")
            except Exception:
                pass
            return
    except Exception:
        pass

    # Strategy 3: bump-and-restore the first USER scalar input. The bump dirties
    # the output but doesn't fire compute -- pull an output afterward.
    get_input_map = getattr(py_node, "get_input_attr_map", None)
    get_output_map = getattr(py_node, "get_output_attr_map", None)
    if callable(get_input_map):
        try:
            input_map = get_input_map() or {}
        except Exception:
            input_map = {}
        bumped = False
        for input_name, meta in input_map.items():
            attr_type = meta.get("attr_type")
            plug = f"{name}.{input_name}"
            if attr_type in ("float", "double"):
                try:
                    old = cmds.getAttr(plug)
                    cmds.setAttr(plug, old + 1e-9)
                    cmds.setAttr(plug, old)
                    bumped = True
                    break
                except Exception:
                    continue
            elif attr_type == "int":
                try:
                    old = cmds.getAttr(plug)
                    cmds.setAttr(plug, old + 1)
                    cmds.setAttr(plug, old)
                    bumped = True
                    break
                except Exception:
                    continue
        if bumped and callable(get_output_map):
            # Pull any USER output to force compute() to fire.
            try:
                output_map = get_output_map() or {}
            except Exception:
                output_map = {}
            for out_name in output_map:
                try:
                    cmds.getAttr(f"{name}.{out_name}")
                    return
                except Exception:
                    continue
        if bumped:
            return

    # Strategy 4: dirty + read a USER output to force compute.
    if callable(get_output_map):
        try:
            output_map = get_output_map() or {}
        except Exception:
            output_map = {}
        for out_name in output_map:
            try:
                cmds.dgdirty(name)
                cmds.getAttr(f"{name}.{out_name}")
                return
            except Exception:
                continue

    # Strategy 5: fallback -- just dirty the node.
    try:
        cmds.dgdirty(name)
    except Exception:
        pass


def force_viewport_refresh(py_node) -> None:
    """Push a Viewport-tier source edit to VP2 immediately on Save / F5.

    Nodes with a Viewport tier (mPyFile in v1) shade through
    ``MPxShadingNodeOverride.updateShader``, which only re-runs when OGS
    re-evaluates the node. ``setInternalValue`` already ``dgdirty``-s outColor
    when the ``_viewportSource`` plug changes (and recompiles ``_viewport_code``
    to the new source), but a dgdirty merely marks the DG output dirty -- it
    does NOT force a viewport redraw, so the textured surface (and the
    Hypershade swatch) stay stale until the user scrubs the timeline. After Save
    we therefore dgdirty the render outputs AND schedule a deferred
    ``cmds.refresh()`` so the surface updates now, matching the trigger a
    timeline scrub supplies for free.

    No-op for node types without a Viewport tier (don't churn the viewport for
    plain DG nodes). Best-effort; never raises. The refresh is DEFERRED so it
    never fires synchronously from inside a save/command chunk; headless (mayapy
    / batch) has no idle loop, so it degrades to an inline refresh. (The OSL
    tier is handled separately by :func:`force_osl_refresh` -- OSL renders
    through an Arnold aiOslShader that a VP2 refresh does NOT recompile.)
    """
    if not hasattr(py_node, "set_viewport_expression"):
        return
    try:
        name = py_node.get_name()
    except Exception:
        return
    if not name:
        return
    # Dirty the render-facing outputs so OGS knows the node must re-shade.
    for plug in (name + ".outColor", name + ".outAlpha"):
        try:
            cmds.dgdirty(plug)
        except Exception:
            pass
    # Force the VP2 redraw. Deferred so we never refresh synchronously inside a
    # command chunk; inline fallback when there's no idle loop.
    try:
        from maya.utils import executeDeferred

        executeDeferred(cmds.refresh)
    except Exception:
        try:
            cmds.refresh()
        except Exception:
            pass


def force_osl_refresh(py_node) -> None:
    """Push an OSL-tier source edit to Arnold immediately on Save / F5.

    The OSL tier does NOT render through VP2: ``set_osl_expression`` writes the
    node's ``osl`` string plug, which (when the OSL tab has been applied to
    Arnold) feeds an ``aiOslShader``'s ``codeCache``. But a string wire to
    ``codeCache`` does NOT recompile the shader -- only re-running
    ``OSLSceneModel`` does -- so a saved OSL edit stays stale until the shader
    is rebuilt. This recompiles every aiOslShader already wired to the node's
    ``osl`` output (it never CREATES one: applying OSL to Arnold the first time
    is the OSL tab's explicit ``apply_osl_to_arnold`` action).

    No-op for nodes without an OSL tier, or when no aiOslShader is wired, or
    when MtoA is unavailable. Best-effort; never raises. Runs synchronously on
    the caller's (main) thread -- OSLSceneModel is a Maya/Arnold API call and
    Save already runs on the main thread.
    """
    if not hasattr(py_node, "set_osl_expression"):
        return
    try:
        name = py_node.get_name()
    except Exception:
        return
    if not name:
        return
    try:
        from mpynode._common.osl import osl_targets

        osl_targets.recompile_osl_targets(name)
    except Exception:
        pass
