"""Build-time helpers for the mPyMesh SDF "MPyNode" text.

The stroke-font glyphs and ``word_strokes`` layout now live in the SHIPPED,
pure module ``mpynode._common.nodes.mesh.sdf_text`` (so the Metaballs
template's runtime ``def demo`` can import them too). They are re-exported
here so the existing example builders keep importing them from this module
and the font stays a single source of truth. ``strokes_to_arrays`` (numpy +
``sdf_dmc``) stays here -- it is a build/verification-time reference only.
"""
from __future__ import annotations

import math

import numpy as np

from mpynode._common.nodes.mesh.sdf_text import (  # noqa: F401
    CAP,
    XH,
    DESC,
    THICK,
    DEPTH,
    ADVANCE,
    GLYPHS,
    _stroke_box,
    word_strokes,
)


def strokes_to_arrays(boxes):
    """Compose the parallel arrays ``sdf_dmc.mesh_from_shapes`` consumes from a
    list of stroke boxes (every shape a hard-union box, rotated about Z). The
    matrices match what the live ``addBox`` transforms produce, so this is both
    the builder's reference and a headless verification of the field."""
    from mpynode._common.nodes.mesh import sdf_dmc

    n = len(boxes)
    matrices = np.empty((n, 4, 4), dtype=np.float64)
    half = np.empty((n, 3), dtype=np.float64)
    for s, b in enumerate(boxes):
        R = sdf_dmc.euler_to_matrix(
            np.array([0.0, 0.0, math.radians(b["angle"])]), 0)
        M = np.eye(4)
        M[:3, :3] = R[:3, :3]
        M[3, :3] = [b["cx"], b["cy"], 0.0]
        matrices[s] = M
        half[s] = [b["length"] * 0.5, b["thick"] * 0.5, b["depth"] * 0.5]
    return dict(
        matrices=matrices,
        shape_types=np.ones(n, dtype=np.int64),       # all boxes
        additive=np.ones(n, dtype=bool),
        smoothing=np.zeros(n, dtype=np.float64),       # crisp hard union
        radius=np.ones(n, dtype=np.float64),
        height=np.ones(n, dtype=np.float64),
        axis=np.ones(n, dtype=np.int64),
        half_extents=half,
    )
