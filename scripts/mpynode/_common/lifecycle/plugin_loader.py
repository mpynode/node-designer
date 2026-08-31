"""Plugin_loader -- shared helper to auto-load mpynode plug-ins on
demand.

PROBLEM
-------
``mc.deformer(type="mPyDeformer")`` (and ``mc.createNode("mPyXxx")``,
``mc.skinCluster``, etc.) raise ``"Unable to create/find dependency
node"`` if the plug-in registering the type isn't loaded in the
current Maya session. This is hostile to copy-paste API docs where
the user just wants the example to work.

SOLUTION
--------
Every wrapper's ``create`` / ``create_on`` calls:func:`ensure_loaded` first. If the node type isn't yet registered,
this helper loads the appropriate plug-in by name (with a clear
error if the plug-in isn't on ``MAYA_PLUG_IN_PATH``).
"""

from __future__ import annotations

import maya.cmds as mc


# Map a custom node type name -> the plug-in file that registers it.
_NODE_TYPE_TO_PLUGIN: dict = {
    # mPyNode plug-in (api2)
    "mPyNode": "mpynode_api2.py",
    "mPyConstraint": "mpynode_api2.py",
    "mPyLocator": "mpynode_api2.py",
    "mPyMesh": "mpynode_api2.py",
    "mPyFile": "mpynode_api2.py",
    "mPyNurbsCurve": "mpynode_api2.py",
    "mPyNurbsSurface": "mpynode_api2.py",
    # Other plug-in (api1)
    "mPyIkSolver": "mpynode_api1.py",
    "mPyDeformer": "mpynode_api1.py",
    "mPyTransform": "mpynode_api1.py",
    "mPySkinCluster": "mpynode_api1.py",
    "mPyBlendShape": "mpynode_api1.py",
}


def ensure_loaded(node_type: str) -> None:
    """Auto-load the plug-in that registers ``node_type`` if it's not
    already registered in the current Maya session.

    Idempotent. Safe to call from every wrapper's ``create`` /
    ``create_on``. Raises ``RuntimeError`` with a clear message if the
    plug-in isn't on ``MAYA_PLUG_IN_PATH``.
    """
    try:
        types = mc.allNodeTypes() or []
    except Exception:
        types = []
    if node_type in types:
        return

    plugin_name = _NODE_TYPE_TO_PLUGIN.get(node_type)
    if plugin_name is None:
        raise RuntimeError(
            f"unknown mpynode node type {node_type!r} -- no plug-in "
            "registered to auto-load it"
        )

    try:
        if not mc.pluginInfo(plugin_name, query=True, loaded=True):
            mc.loadPlugin(plugin_name, quiet=True)
    except Exception:
        raise RuntimeError(
            f"{node_type!r} plug-in not loaded and {plugin_name!r} "
            "not found on MAYA_PLUG_IN_PATH. Add the phase's "
            "plug-ins/ directory to MAYA_PLUG_IN_PATH (userSetup.py "
            "handles this automatically) or call "
            f"mc.loadPlugin({plugin_name!r}) manually."
        )

    # Verify the type is now registered.
    try:
        types = mc.allNodeTypes() or []
    except Exception:
        types = []
    if node_type not in types:
        raise RuntimeError(
            f"loaded {plugin_name!r} but {node_type!r} still not "
            "registered -- plug-in load may have failed silently. "
            "Check the Maya Output Window for plug-in init errors."
        )
