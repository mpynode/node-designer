"""mpynode_api1.py — API 1.0 plugin file.

Registers MPx subclasses that have NO API 2.0 equivalent:
  * mPyIkSolver       (MPxIkSolverNode)
  * mPyDeformer       (MPxDeformerNode)
  * mPyTransform      (MPxTransform +
                       MPxTransformationMatrix)
  * mPySkinCluster    (MPxSkinCluster)
  * mPyBlendShape     (MPxDeformerNode by choice --
                       MPxBlendShape ships in api1, but
                       see _api1/mpy_blend_shape.py)
The mPyTransform registration is unique: it uses
``MFnPlugin.registerTransform()`` instead of ``registerNode()`` because
MPxTransform requires a paired MPxTransformationMatrix subclass with
its own MTypeId.
"""

from __future__ import annotations

import sys

import maya.OpenMaya as om  # noqa: F401 (used by registered MPx subclasses)
import maya.OpenMayaMPx as ommpx


PLUGIN_NAME    = "mpynode_api1"
PLUGIN_VERSION = "2.0.0a2"


def initializePlugin(plugin):
    """Register all API 1.0 node types."""
    plugin1 = ommpx.MFnPlugin(plugin, "mpynode", PLUGIN_VERSION, "Any")
    sys.stdout.write(f"[{PLUGIN_NAME}] loaded (version {PLUGIN_VERSION})\n")

    # Cap numpy's bundled OpenBLAS to a single thread before any node compute
    # can run. Threaded LAPACK (np.linalg.*) corrupts state on Maya's
    # parallel-EM worker threads and segfaults the session; safe no-op on an
    # Accelerate/MKL-backed numpy.
    try:
        from mpynode._common.util.blas_guard import limit_blas_threads

        limit_blas_threads(1)
    except Exception:
        pass

    # Register the in-memory ``mpynode_user`` module so UI-authored node Classes
    # are importable (populated per-scene by the file-open sweep). No disk.
    try:
        from mpynode._common.io.user_classes import ensure_module

        ensure_module()
    except Exception:
        pass

    # Attribute Editor template for mPyBlendShape's aliased weight[] stack.
    # Maya resolves an AE layout by MEL proc name at the moment it draws the
    # panel, so the proc has to exist before then -- there is no lazier hook.
    # No-op in batch. Wrapped because a UI failure must never stop the node
    # types below from registering.
    try:
        from mpynode.ui.ae_blend_shape import register as register_bs_ae

        register_bs_ae()
    except Exception:
        pass

    # Cross-plugin load refcount: uninitialize only tears down the SHARED
    # callbacks when this hits zero, so unloading api1 while api2 stays loaded
    # leaves api2's shared callbacks intact.
    from mpynode._common.lifecycle import callbacks as _callbacks

    _callbacks.mark_plugin_loaded(PLUGIN_NAME)

    # mPyIkSolver (MPxIkSolverNode only exists in API 1.0)
    from mpynode._api1.mpy_iksolver import MPyIkSolver

    plugin1.registerNode(
        MPyIkSolver.NODE_NAME,
        MPyIkSolver.NODE_ID,
        MPyIkSolver.node_creator,
        MPyIkSolver.node_initializer,
        ommpx.MPxNode.kIkSolverNode,
    )

    # mPyDeformer (MPxDeformerNode only exists in API 1.0)
    from mpynode._api1.mpy_deformer import (
        MPyDeformer,
        register_time_change_callback as df_register_time_change_callback,
    )
    from mpynode._common.lifecycle import (
        register_scene_change_callbacks as init_register_scene_change_callbacks,
    )

    plugin1.registerNode(
        MPyDeformer.NODE_NAME,
        MPyDeformer.NODE_ID,
        MPyDeformer.node_creator,
        MPyDeformer.node_initializer,
        ommpx.MPxNode.kDeformerNode,
    )
    # Time-change callback (touch envelope) so the deformer re-evaluates per
    # frame in mayapy AND when wired inputs animate.
    df_register_time_change_callback()
    # Scene-open callback: auto-load init_source namespaces for every node
    # carrying a _jitSource attribute.
    init_register_scene_change_callbacks()

    # Time-unit-change callback: re-derive ``self.time`` fps after a manual
    # scene time-unit change (rare; never fires during playback).
    from mpynode._common.lifecycle.time_utils import register_time_unit_change_callback

    register_time_unit_change_callback()

    # mPyTransform (MPxTransform + MPxTransformationMatrix are API-1.0 only).
    # registerTransform(), not registerNode(): MPxTransform needs a paired
    # matrix class with its own ID.
    from mpynode._api1.mpy_transform import (
        MPyTransform,
        MPyTransformMatrix,
        register_relay_callbacks,
    )

    plugin1.registerTransform(
        MPyTransform.NODE_NAME,
        MPyTransform.NODE_ID,
        MPyTransform.node_creator,
        MPyTransform.node_initializer,
        MPyTransformMatrix.matrix_creator,
        MPyTransformMatrix.NODE_ID,
    )
    # nodeAdded + scene-open callbacks auto-wire each mPyTransform's paired
    # ``fourByFourMatrix`` opm relay. This REPLACES the old process-wide
    # per-frame ``timeChanged`` cache-flush hack: the expression result now
    # reaches worldMatrix + descendants through a genuine offsetParentMatrix
    # connection, which invalidates natively in DG, EM-parallel and Cached
    # Playback.
    register_relay_callbacks()

    # mPySkinCluster (MPxSkinCluster — expression-driven
    # custom skinCluster with full joint matrix + weight access).
    from mpynode._api1.mpy_skin_cluster import (
        MPySkinCluster,
        register_time_change_callback as sc_register_time_change_callback,
    )

    # Register under the REAL skinCluster node-type constant
    # (MPxNode.kSkinCluster == 23). Older code probed a non-existent
    # ``kSkinClusterNode`` and so ALWAYS fell back to kDeformerNode -- the node
    # became a plain weightGeometryFilter and Maya's skin tools (Paint Skin
    # Weights, skinPercent, MFnSkinCluster) rejected it by type.
    if hasattr(ommpx.MPxNode, "kSkinCluster"):
        _sc_node_type = ommpx.MPxNode.kSkinCluster
    else:
        # Effectively unreachable: kSkinCluster predates every supported Maya.
        # Warn rather than silently reproduce the broken deformer fallback.
        _sc_node_type = ommpx.MPxNode.kDeformerNode
        sys.stderr.write(
            f"[{PLUGIN_NAME}] WARNING: MPxNode.kSkinCluster unavailable; "
            "mPySkinCluster registered as kDeformerNode -- native skin tools "
            "(Paint Skin Weights, Component Editor) will NOT recognise it\n"
        )
    plugin1.registerNode(
        MPySkinCluster.NODE_NAME,
        MPySkinCluster.NODE_ID,
        MPySkinCluster.node_creator,
        MPySkinCluster.node_initializer,
        _sc_node_type,
    )
    sc_register_time_change_callback()

    # mPyBlendShape: an expression-driven blendShape with target geometry +
    # per-target weights, built on MPxDeformerNode by CHOICE. MPxBlendShape
    # does ship (api1, both 2024 and 2026); a kBlendShape node stops calling
    # deform() and loses the aliased user weight[] -- measured reasons are in
    # _api1/mpy_blend_shape.py.
    from mpynode._api1.mpy_blend_shape import (
        MPyBlendShape,
        register_time_change_callback as bs_register_time_change_callback,
    )

    plugin1.registerNode(
        MPyBlendShape.NODE_NAME,
        MPyBlendShape.NODE_ID,
        MPyBlendShape.node_creator,
        MPyBlendShape.node_initializer,
        ommpx.MPxNode.kDeformerNode,
    )
    bs_register_time_change_callback()

    # User-input auto-dirty handlers per node type: when an add_input_attr
    # attr changes -- including via a connected source -- the handler dgdirty-s
    # the node and runs a per-type "touch" to force re-eval. Without it, custom
    # user inputs only re-eval on timeline ticks, since attributeAffects can't
    # be declared for plugs added at runtime.
    from mpynode._common.plugs import auto_dirty

    # NOTE: mPyTransform is intentionally ABSENT. A connected user input's
    # change dirties the input plug -> setDependentsDirty appends
    # ``_outLocalFlat`` -> the fourByFourMatrix relay -> offsetParentMatrix ->
    # worldMatrix + descendants, all native DG propagation. The old
    # ``touch_translateX`` was exactly the flush hack this removes.
    for type_name, touch_fn in (
        ("mPyIkSolver", auto_dirty.touch_dgdirty_only),
        ("mPyDeformer", auto_dirty.touch_envelope),
        ("mPySkinCluster", auto_dirty.touch_envelope),
        ("mPyBlendShape", auto_dirty.touch_envelope),
    ):
        auto_dirty.install_for_type(type_name, touch=touch_fn, owner=PLUGIN_NAME)



def uninitializePlugin(plugin):
    """Deregister all API 1.0 node types + remove tracked callbacks."""
    plugin1 = ommpx.MFnPlugin(plugin)

    # mPyIkSolver
    from mpynode._api1.mpy_iksolver import MPyIkSolver

    plugin1.deregisterNode(MPyIkSolver.NODE_ID)

    # mPyDeformer
    from mpynode._api1.mpy_deformer import MPyDeformer

    plugin1.deregisterNode(MPyDeformer.NODE_ID)

    # mPyTransform: deregister the node ID only -- Maya handles the paired
    # matrix ID per the registerTransform contract.
    from mpynode._api1.mpy_transform import MPyTransform

    plugin1.deregisterNode(MPyTransform.NODE_ID)

    # mPySkinCluster
    from mpynode._api1.mpy_skin_cluster import MPySkinCluster

    plugin1.deregisterNode(MPySkinCluster.NODE_ID)

    # mPyBlendShape
    from mpynode._api1.mpy_blend_shape import MPyBlendShape

    plugin1.deregisterNode(MPyBlendShape.NODE_ID)

    # Remove ONLY this plugin's own callbacks. Do NOT touch the other plugin's
    # or the shared scene/time callbacks -- a blanket ``remove_all()`` wiped
    # everything and left a co-loaded api2 deaf.
    try:
        from mpynode._common.plugs import auto_dirty as _auto_dirty
        from mpynode._common.lifecycle import callbacks as _callbacks

        _callbacks.CALLBACK_MANAGER.remove_for_owner(PLUGIN_NAME)
        # The per-type connection callback is plugin-owned and removed on every
        # unload, so its latch must clear too -- otherwise a reload while api2
        # stays loaded skips re-registering it.
        _auto_dirty.forget_owner(PLUGIN_NAME)
        # Last plugin out tears down the shared callbacks + resets the
        # install guards so a later reload re-registers them.
        if _callbacks.mark_plugin_unloaded(PLUGIN_NAME) == 0:
            from mpynode._common.lifecycle import teardown_shared_callbacks

            teardown_shared_callbacks()
    except Exception:
        pass
    sys.stdout.write(f"[{PLUGIN_NAME}] unloaded\n")
