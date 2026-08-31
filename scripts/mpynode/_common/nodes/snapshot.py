"""Solver context snapshot.

When ``compute_ik_doSolve`` runs, it calls ``write_solver_context_snapshot``
to persist a JSON snapshot of the live IK context onto the iksolver
node's ``_solverContextSnapshot`` plug. The Solver Context panel reads that plug to render live values
without re-walking the IK API.
"""

from __future__ import annotations

import json

import maya.OpenMaya as om


SNAPSHOT_ATTR_NAME = "_solverContextSnapshot"


def write_solver_context_snapshot(
    node_obj: om.MObject,
    handle_name: str,
    joints: list[dict],
    end_effector,
    pole_vector,
    twist: float,
) -> None:
    """Serialize the iksolver context to JSON + write to the node's
    ``_solverContextSnapshot`` plug.

    Failure is silent (this is a diagnostic only, not the solve itself).
    """
    try:
        snapshot = {
            "handle": handle_name,
            "joints": [
                {
                    "name": j["name"],
                    "world_position": list(j["world_position"]),
                    "rotation": list(j["rotation"]),
                }
                for j in joints
            ],
            "end_effector": list(end_effector)
            if not hasattr(end_effector, "tolist")
            else end_effector.tolist(),
            "pole_vector": list(pole_vector)
            if not hasattr(pole_vector, "tolist")
            else pole_vector.tolist(),
            "twist": float(twist),
        }
        text = json.dumps(snapshot, separators=(",", ":"))
    except Exception:
        return

    try:
        fn = om.MFnDependencyNode(node_obj)
        plug = fn.findPlug(SNAPSHOT_ATTR_NAME, True)
        plug.setString(text)
    except Exception:
        # Plug doesn't exist (yet) on this node -- skip.
        pass


def read_solver_context_snapshot(node_name: str) -> dict | None:
    """Inverse of write. Read the plug + return the parsed dict, or None."""
    from maya import cmds

    try:
        text = cmds.getAttr(f"{node_name}.{SNAPSHOT_ATTR_NAME}")
    except Exception:
        return None
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None
