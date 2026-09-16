"""Build the demo asset: a 48-frame deforming-mesh cache in ONE .ndio file.

Run with any python that has numpy:
    mayapy make_cache.py [outdir]

Writes ``ripple_cache.ndio`` next to this script (or into ``outdir``):

    points   float64 (48, 1089, 3)   every frame's vertex positions
    counts   int64   (1024,)          per-face vertex count (all quads)
    indices  int64   (4096,)          face-vertex indices (constant topology)

Topology is CONSTANT across frames, which is why one ``counts`` / ``indices``
pair serves all 48 -- only ``points`` carries the animation. The node reads all
three ONCE (the reader caches on path+mtime+size) and then just slices
``points[frame]`` per evaluation, so scrubbing the timeline touches no disk.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "..", "scripts"))

import numpy as np

from mpynode import ndio

N      = 33    # grid resolution -> N*N verts, (N-1)^2 quads
FRAMES = 48
SIZE   = 10.0  # world size of the grid


def build():
    lin = np.linspace(-SIZE * 0.5, SIZE * 0.5, N)
    gx, gz = np.meshgrid(lin, lin, indexing="ij")
    r = np.sqrt(gx * gx + gz * gz)

    # One radial travelling wave + a slower orthogonal swell, so the surface
    # reads as animated and clearly not procedural noise.
    pts = np.zeros((FRAMES, N * N, 3), dtype=np.float64)
    for f in range(FRAMES):
        t = 2.0 * np.pi * f / FRAMES
        y = (1.15 * np.sin(r * 1.9 - t * 2.0) * np.exp(-r * 0.16)
             + 0.45 * np.sin(gx * 0.8 + t) * np.cos(gz * 0.8 - t))
        pts[f, :, 0] = gx.ravel()
        pts[f, :, 1] = y.ravel()
        pts[f, :, 2] = gz.ravel()

    # Quad grid, CCW seen from +Y.
    quads = []
    for i in range(N - 1):
        for j in range(N - 1):
            a = i * N + j
            quads.append([a, a + N, a + N + 1, a + 1])
    indices = np.asarray(quads, dtype=np.int64).ravel()
    counts  = np.full((N - 1) * (N - 1), 4, dtype=np.int64)
    return pts, counts, indices


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.abspath(__file__))
    path = os.path.join(outdir, "ripple_cache.ndio")

    pts, counts, indices = build()
    if not ndio.write(path, points=pts, counts=counts, indices=indices):
        raise SystemExit("ndio.write failed: %s" % path)

    # Read it straight back through the same reader the node uses -- if this
    # does not round-trip, the asset is not shippable.
    back = ndio.read(path, "points")
    assert back.shape == pts.shape, (back.shape, pts.shape)
    assert np.array_equal(back, pts), "points did not round-trip bitwise"
    assert np.array_equal(ndio.read(path, "counts", dtype=np.int64), counts)
    assert np.array_equal(ndio.read(path, "indices", dtype=np.int64), indices)

    print("wrote %s" % path)
    print("  points  %s  %.1f KB" % (pts.shape, pts.nbytes / 1024.0))
    print("  counts  %s" % (counts.shape,))
    print("  indices %s" % (indices.shape,))
    print("  file    %.1f KB" % (os.path.getsize(path) / 1024.0))
    print("  keys    %s" % (ndio.keys(path),))
    print("ROUND-TRIP BITWISE OK")


if __name__ == "__main__":
    main()
