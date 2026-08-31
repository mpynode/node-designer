"""mpynode_api2.py — API 2.0 plugin file.

Registers MPx subclasses available in API 2.0:
  * mPyNode       (MPxNode)
  * mPyLocator    (MPxLocatorNode +
                   MPxDrawOverride)
  * mPyConstraint (MPxNode — NOT
                   MPxConstraint; the v1
                   bridge uses MPxNode +
                   preset constraint-style
                   input plugs. See
                   _api2/mpy_constraint.py
                   docstring for the
                   compute-hijack rationale.)
  * mPyMesh      (MPxNode —
                   plain DG geometry
                   generator; emits
                   outMesh. Matches
                   Maya's polyCube /
                   polySplit / polyAppend
                   / polyBevel pattern.)
  * mPyFile      (MPxNode +
                   MPxShadingNodeOverride;
                   replicates the
                   MayaCustomFileNode
                   customFileTexture as a
                   user-editable Init /
                   Compute / Pipeline node.
                   Reuses Maya's
                   mayaFileTexture
                   shade-fragment graph for
                   VP2 + Hypershade swatch.)

The ``maya_useNewAPI`` function below is the marker that tells Maya
this file uses ``maya.api.OpenMaya`` (API 2.0).

nothing registered yet. Plugin must load + unload cleanly.
"""

from __future__ import annotations

import functools
import sys

import maya.api.OpenMaya as om2
from maya import cmds


PLUGIN_NAME = "mpynode_api2"
PLUGIN_VERSION = "1.0.0a1"


def maya_useNewAPI():
    """Marker: tell Maya this plugin file uses API 2.0."""
    pass


# ---------------------------------------------------------------------------
# runUndoableAPICommand -- the Node Designer's undoable dispatcher command.
#
# Folded in from the former ``undoable_api_command.py`` plug-in so the toolkit
# ships exactly TWO plug-ins. It is an API 2.0 ``MPxCommand``, so it must live
# in api2: an API-1.0 plug-in cannot register one -- ``om2.MFnPlugin`` rejects
# the om1 MObject handed to its initializePlugin (verified in mayapy 2024).
# Command names are GLOBAL, so it is registered exactly once, here.
#
# ``mpynode._base.commands.run_undoable`` wraps a python object exposing doIt /
# undoIt / redoIt and dispatches it through the wrapped
# ``cmds.runUndoableAPICommand``, making each user write one undo chunk.
# ---------------------------------------------------------------------------

UNDOABLE_COMMAND_NAME = "runUndoableAPICommand"


class UndoableAPICommand(om2.MPxCommand):
    """API 2.0 command wrapper with undo & redo support.

    Custom API commands are triggered through this single wrapper so they
    don't each need their own plug-in. See ``mpynode._base.commands`` for the
    ``_BaseCommand`` / ``run_undoable`` consumer side.
    """

    call_class = None

    def __init__(self):
        super(UndoableAPICommand, self).__init__()
        self.py_class = None

    def isUndoable(self):
        return True

    def doIt(self, args):
        self.py_class = self.call_class
        result = self.py_class.doIt()
        if result is not None:
            self.setResult(result)

    def redoIt(self):
        result = self.py_class.redoIt()
        if result is not None:
            self.setResult(result)

    def undoIt(self):
        state = cmds.undoInfo(query=True, state=True)
        if state:
            cmds.undoInfo(stateWithoutFlush=False)
        try:
            result = self.py_class.undoIt()
            if result is not None:
                self.setResult(result)
        finally:
            if state:
                cmds.undoInfo(stateWithoutFlush=True)

    @classmethod
    def wrap_command(cls):
        """Replace ``cmds.runUndoableAPICommand`` with a wrapper that accepts a
        python command object (bypassing the MEL-compatible no-arg signature)
        and brackets the call in a single named undo chunk."""
        cmd_func = getattr(cmds, UNDOABLE_COMMAND_NAME)

        @functools.wraps(cmd_func)
        def wrapped(py_class):
            # Keep a reference so the class can't go out of scope.
            cls.call_class = py_class
            cmds.undoInfo(openChunk=True, chunkName=UNDOABLE_COMMAND_NAME)
            try:
                return cmd_func()
            finally:
                cmds.undoInfo(closeChunk=True)

        wrapped.__wrapped__ = cmd_func
        setattr(cmds, UNDOABLE_COMMAND_NAME, wrapped)


def _undoable_command_creator():
    return UndoableAPICommand()


def initializePlugin(plugin):
    """Register all API 2.0 node types."""
    plugin2 = om2.MFnPlugin(plugin, "mpynode", PLUGIN_VERSION, "Any")
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

    # Command names are global, so guard against a stale double-registration on
    # reload, and NEVER let a registration hiccup abort initializePlugin -- that
    # would take every node type below down with it. Always (re)apply the cmds
    # wrapper once the command exists.
    try:
        _cmd_already = UNDOABLE_COMMAND_NAME in (
            cmds.pluginInfo(PLUGIN_NAME, q=True, command=True) or []
        )
        if not _cmd_already:
            plugin2.registerCommand(UNDOABLE_COMMAND_NAME, _undoable_command_creator)
    except Exception:
        pass
    try:
        UndoableAPICommand.wrap_command()
    except Exception:
        pass

    # Bump the cross-plugin load refcount (see api1 + AUDIT #3). The matching
    # uninitialize only tears down the SHARED callbacks when this hits zero.
    from mpynode._common.lifecycle import callbacks as _callbacks

    _callbacks.mark_plugin_loaded(PLUGIN_NAME)

    # mPyNode (basic expression-driven DG node)
    from mpynode._api2._mpy_node import MPyNode

    plugin2.registerNode(
        MPyNode.NODE_NAME,
        MPyNode.NODE_ID,
        MPyNode.creator,
        MPyNode.initializer,
    )

    # mPyConstraint (constraint-style preset inputs)
    from mpynode._api2.mpy_constraint import MPyConstraint

    plugin2.registerNode(
        MPyConstraint.NODE_NAME,
        MPyConstraint.NODE_ID,
        MPyConstraint.creator,
        MPyConstraint.initializer,
    )

    # mPyLocator + MPxDrawOverride
    from mpynode._api2.mpy_locator import MPyLocatorDrawOverride
    from mpynode._api2.mpy_locator import MPyLocator

    plugin2.registerNode(
        MPyLocator.NODE_NAME,
        MPyLocator.NODE_ID,
        MPyLocator.creator,
        MPyLocator.initializer,
        om2.MPxNode.kLocatorNode,
        MPyLocator.DRAW_DB_CLASSIFICATION,
    )
    import maya.api.OpenMayaRender as omr2

    omr2.MDrawRegistry.registerDrawOverrideCreator(
        MPyLocator.DRAW_DB_CLASSIFICATION,
        MPyLocator.DRAW_REGISTRANT_ID,
        MPyLocatorDrawOverride.creator,
    )

    # Track scene file-IO state so the self-correcting "no plug named X"
    # error that the Evaluation Manager triggers during / just-after a
    # scene load is deferred (not logged) instead of spamming the editor.
    from mpynode._common.lifecycle import scene_state as scene_io

    scene_io.install_once()

    # mPyFile (file-texture shading node): MPxNode + MPxShadingNodeOverride.
    # Mirrors the Hypershade swatch + VP2 shading semantics of Maya's stock
    # ``file`` node, with the color-space / kernel / sampling math exposed in
    # the Init tab and the texture-upload + sampler binding in the Viewport tab.
    from mpynode._api2.mpy_file import (
        MPyFile,
        MPyFileOverride,
        register_time_change_callback as _file_register_tc,
        register_attr_refresh_callbacks as _file_register_attr_refresh,
        register_node_lifecycle_callbacks as _file_register_lifecycle,
    )

    plugin2.registerNode(
        MPyFile.NODE_NAME,
        MPyFile.NODE_ID,
        MPyFile.creator,
        MPyFile.initializer,
        om2.MPxNode.kDependNode,
        MPyFile.PLUGIN_NODE_CLASSIFY,
    )
    omr2.MDrawRegistry.registerShadingNodeOverrideCreator(
        MPyFile.DRAW_DB_CLASSIFICATION,
        MPyFile.DRAW_REGISTRANT_ID,
        MPyFileOverride.creator,
    )
    # mPyFile is always time-aware (self.time available for image
    # sequences); dgdirty outColor per frame so sequences animate.
    _file_register_tc()
    # Manual-attribute viewport refresh: a per-node AttributeChanged callback
    # that dgdirty+refreshes when a preset / user input is set (presets are not
    # fragment-mapped, so Maya never refreshes the viewport on their edit).
    _file_register_attr_refresh()
    # Node-lifecycle warming: every mPyFile from ANY source gets wired into
    # defaultTextureList1 (Hypershade-graphable) AND its init namespace
    # registered on the main thread before any swatch / Arnold worker thread
    # evaluates it -- otherwise it renders black.
    _file_register_lifecycle()

    # mPyMesh (plain DG polygon geometry generator). Follows the
    # polyCube/polySplit convention -- a DG node, NOT a DAG shape. To render,
    # connect outMesh to a real mesh shape's inMesh.
    from mpynode._api2.mpy_mesh import MPyMesh, register_time_change_callback

    plugin2.registerNode(
        MPyMesh.NODE_NAME,
        MPyMesh.NODE_ID,
        MPyMesh.creator,
        MPyMesh.initializer,
    )
    # dgdirty every mPyMesh's outMesh on each frame change; without it,
    # time-driven mesh expressions appear frozen across consecutive queries
    # (mayapy caches the mesh-data plug across getAttr calls).
    register_time_change_callback()

    # mPyNurbsCurve (plain DG NURBS-curve generator).
    from mpynode._api2.mpy_nurbs_curve import (
        MPyNurbsCurve,
        register_time_change_callback as _curve_register_tc,
    )

    plugin2.registerNode(
        MPyNurbsCurve.NODE_NAME,
        MPyNurbsCurve.NODE_ID,
        MPyNurbsCurve.creator,
        MPyNurbsCurve.initializer,
    )
    _curve_register_tc()

    # mPyNurbsSurface (plain DG NURBS-surface generator).
    from mpynode._api2.mpy_nurbs_surface import (
        MPyNurbsSurface,
        register_time_change_callback as _surface_register_tc,
    )

    plugin2.registerNode(
        MPyNurbsSurface.NODE_NAME,
        MPyNurbsSurface.NODE_ID,
        MPyNurbsSurface.creator,
        MPyNurbsSurface.initializer,
    )
    _surface_register_tc()

    # User-input auto-dirty for API2 node types (full rationale in
    # mpynode_api1.py): bridges the gap left by Maya's static-only
    # attributeAffects when users add input attrs dynamically.
    #
    # MUST run AFTER every registerNode above -- install_for_type's deferred
    # install calls addNodeAddedCallback(type_name), which fails with "Unknown
    # object type" if the type isn't registered yet.
    #
    # NOTE: mPyNode + mPyConstraint are intentionally ABSENT. Their dynamic
    # input -> output dirtying is declared natively in
    # MPyNode.setDependentsDirty (plugs.dirty_affects), which is EM-safe. The
    # old auto_dirty source-side ``cmds.dgdirty`` ran during dirty propagation
    # and crashed Maya under the 2026 Evaluation Manager.
    from mpynode._common.plugs import auto_dirty

    for type_name, touch_fn in (
        ("mPyLocator", auto_dirty.touch_dgdirty_only),
        ("mPyFile", auto_dirty.touch_dgdirty_only),
        ("mPyMesh", auto_dirty.touch_outMesh),
        # Generator-family hooks: these nodes emit a single typed-data plug, so
        # dgdirty-ing it on input change keeps user inputs live in mayapy.
        ("mPyNurbsCurve", auto_dirty.touch_outCurve),
        ("mPyNurbsSurface", auto_dirty.touch_outSurface),
    ):
        auto_dirty.install_for_type(type_name, touch=touch_fn, owner=PLUGIN_NAME)

    # COMPILED geo nodes lack the _inputAttrs plug, so install_for_type can't
    # cover them -- yet they hit the DG quirk where a UV-only edit on a
    # connected source mesh never propagates, leaving the compiled node's
    # outMesh stale. Sweep for compiled mesh/curve/surface types now and on
    # every scene-open/import so saved scenes get the same source-side dirty
    # bridge the interpreted nodes have. (The compile->load flow also arms
    # coverage from the build manifest, so a fresh type is covered before its
    # first instance exists.)
    try:
        auto_dirty.install_native_geo_coverage(owner=PLUGIN_NAME)
        auto_dirty.install_native_scene_sweep(owner=PLUGIN_NAME)
    except Exception:
        pass

    # Stored-var deferred-cache + init-namespace scene lifecycle. Guarded, so
    # it's harmless if api1 already registered it; this call makes the lifecycle
    # work when ONLY the api2 plug-in is loaded.
    from mpynode._common.lifecycle import register_scene_change_callbacks

    register_scene_change_callbacks()

    # Time-unit-change callback: re-derive ``self.time`` fps after a manual
    # scene time-unit change (rare; never fires during playback).
    from mpynode._common.lifecycle.time_utils import register_time_unit_change_callback

    register_time_unit_change_callback()


def uninitializePlugin(plugin):
    """Deregister all API 2.0 node types + remove tracked callbacks."""
    plugin2 = om2.MFnPlugin(plugin)

    # Deregister on every unload (not gated on last-out), like deregisterNode.
    try:
        plugin2.deregisterCommand(UNDOABLE_COMMAND_NAME)
    except Exception:
        pass

    # Stop the locator hover-tracker timer (started lazily on first draw).
    try:
        from mpynode._common.draw import hover_tracker

        hover_tracker.stop()
    except Exception:
        pass

    # mPyNode
    from mpynode._api2._mpy_node import MPyNode

    plugin2.deregisterNode(MPyNode.NODE_ID)

    import maya.api.OpenMayaRender as omr2

    # mPyLocator + DrawOverride
    from mpynode._api2.mpy_locator import MPyLocator

    omr2.MDrawRegistry.deregisterDrawOverrideCreator(
        MPyLocator.DRAW_DB_CLASSIFICATION,
        MPyLocator.DRAW_REGISTRANT_ID,
    )
    plugin2.deregisterNode(MPyLocator.NODE_ID)

    # mPyFile
    from mpynode._api2.mpy_file import MPyFile

    try:
        omr2.MDrawRegistry.deregisterShadingNodeOverrideCreator(
            MPyFile.DRAW_DB_CLASSIFICATION,
            MPyFile.DRAW_REGISTRANT_ID,
        )
    except Exception:
        pass
    plugin2.deregisterNode(MPyFile.NODE_ID)

    # mPyMesh
    from mpynode._api2.mpy_mesh import MPyMesh

    plugin2.deregisterNode(MPyMesh.NODE_ID)

    # Generator family.
    from mpynode._api2.mpy_nurbs_curve import MPyNurbsCurve
    from mpynode._api2.mpy_nurbs_surface import MPyNurbsSurface

    for _ndid in (MPyNurbsCurve.NODE_ID, MPyNurbsSurface.NODE_ID):
        try:
            plugin2.deregisterNode(_ndid)
        except Exception:
            pass

    # mPyConstraint
    from mpynode._api2.mpy_constraint import MPyConstraint

    plugin2.deregisterNode(MPyConstraint.NODE_ID)

    # Remove ONLY this plugin's own callbacks; leave api1's + the shared
    # scene/time callbacks intact unless this is the last plugin out
    # (AUDIT #3).
    try:
        from mpynode._common.plugs import auto_dirty as _auto_dirty
        from mpynode._common.lifecycle import callbacks as _callbacks

        _callbacks.CALLBACK_MANAGER.remove_for_owner(PLUGIN_NAME)
        # Clear this plugin's connection-callback latch on every unload (the
        # callback is plugin-owned + removed here), so a reload while api1 stays
        # loaded re-registers it.
        _auto_dirty.forget_owner(PLUGIN_NAME)
        # Clear the mPyFile attr-refresh dedup map: MObject hashCodes persist
        # across an unload/reload, so a stale entry would block reinstall.
        try:
            from mpynode._api2 import mpy_file as _mpy_file

            _mpy_file._reset_attr_refresh_state()
        except Exception:
            pass
        if _callbacks.mark_plugin_unloaded(PLUGIN_NAME) == 0:
            from mpynode._common.lifecycle import teardown_shared_callbacks

            teardown_shared_callbacks()
    except Exception:
        pass
    sys.stdout.write(f"[{PLUGIN_NAME}] unloaded\n")
