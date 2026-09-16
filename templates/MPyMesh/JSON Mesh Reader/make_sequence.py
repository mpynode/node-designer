"""Build the demo asset for json_mesh_reader: a 24-frame JSON mesh SEQUENCE,
one file per frame, in ``seq/mesh.####.json``.

Run with any python that has numpy:
    mayapy make_sequence.py [outdir]

Each frame is a growing helix of cubes -- frame N holds N cubes, so the VERTEX
AND FACE COUNTS CHANGE EVERY FRAME. That is the point of a file-per-frame
sequence, and the thing a single packed cache array cannot express: constant
topology is a requirement there, not here.

File format (what ``load_mesh_json`` in the node's Init block accepts):

    {"points":  [[x, y, z], ...],     # or a flat [x, y, z, x, y, z, ...]
     "counts":  [4, 4, ...],          # per-face vertex count
     "indices": [0, 1, 2, 3, ...]}    # flat face-vertex indices
"""

import json
import math
import os
import sys

FRAMES = 24
TURN   = 0.62  # radians between consecutive cubes on the helix
RADIUS = 3.2
RISE   = 0.42  # world units of climb per cube
HALF   = 0.38  # cube half-extent

# 8 corners of a unit cube, and 6 quads wound CCW as seen from OUTSIDE.
_CORNERS = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
_QUADS = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
          (3, 7, 6, 2), (0, 4, 7, 3), (1, 2, 6, 5)]


def frame_mesh(n_cubes):
    """A helix of ``n_cubes`` cubes as (points, counts, indices)."""
    points, counts, indices = [], [], []
    for i in range(n_cubes):
        a = i * TURN
        cx, cy, cz = RADIUS * math.cos(a), i * RISE, RADIUS * math.sin(a)
        # Each cube spins about Y as it climbs, so the stack reads as motion
        # rather than a static tower.
        ca, sa = math.cos(a * 1.7), math.sin(a * 1.7)
        base = len(points)
        for (dx, dy, dz) in _CORNERS:
            x, z = dx * HALF, dz * HALF
            points.append([round(cx + x * ca - z * sa, 6),
                           round(cy + dy * HALF, 6),
                           round(cz + x * sa + z * ca, 6)])
        for q in _QUADS:
            counts.append(4)
            indices.extend(base + k for k in q)
    return points, counts, indices


def main():
    here   = os.path.dirname(os.path.abspath(__file__))
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "seq")
    if not os.path.isdir(outdir):
        os.makedirs(outdir)

    total = 0
    for f in range(1, FRAMES + 1):
        pts, counts, indices = frame_mesh(f)
        # Sanity: the node's loader refuses a torn mesh, so never ship one.
        assert sum(counts) == len(indices)
        assert max(indices) < len(pts)
        path = os.path.join(outdir, "mesh.%04d.json" % f)
        with open(path, "w") as fh:
            json.dump({"points": pts, "counts": counts, "indices": indices},
                      fh, separators=(",", ":"))
        total += os.path.getsize(path)

    print("wrote %d frames to %s" % (FRAMES, outdir))
    print("  frame 1  : %d verts / %d faces" % (8, 6))
    print("  frame %-2d : %d verts / %d faces"
          % (FRAMES, 8 * FRAMES, 6 * FRAMES))
    print("  total    : %.1f KB" % (total / 1024.0))


if __name__ == "__main__":
    main()
