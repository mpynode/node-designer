"""Common helper used by every build_<demo>.py: save the current scene
to scripts/mpynode/_demos/output/mpy_demos/<name>.ma."""

from __future__ import annotations

import os

import maya.cmds as mc


def save_demo(name: str) -> str:
    """Save the current scene to ``scripts/mpynode/_demos/output/mpy_demos/<name>.ma``.

    Returns the absolute path of the saved file.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.abspath(os.path.join(here, "output", "mpy_demos"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.ma")
    mc.file(rename=path)
    mc.file(save=True, type="mayaAscii", force=True)
    print(f"wrote {path}")
    return path
