"""Igloo SDF scene definition -- shared by the mPyMesh SDF parity test and
the example-scene builder.

``igloo_primitives()`` returns the ordered list of SDF primitives that
recreate ``rl.math.geometry.tests.test_sdf.TestSDFIgloo._create_igloo``
EXACTLY (same order, same CSG ops, same dimensions). Each entry is a plain
dict so the example builder can author live Maya transforms from it and the
parity test can compose matrices from it.

``primitives_to_arrays()`` turns that list into the parallel numpy arrays
``sdf_dmc.mesh_from_shapes`` consumes (matrices composed with the same
euler kernel the source used, so the test reproduces the reference field).
"""
from __future__ import annotations

import numpy as np

from mpynode._common.nodes.mesh import sdf_dmc


def igloo_primitives():
    """Return the ordered list of igloo primitives (dicts).

    Keys per entry:
      kind       -- sdf_dmc.SPHERE / BOX / CYLINDER
      translate  -- (3,) world translate
      rotate     -- (3,) euler degrees (XYZ)
      scale      -- (3,) scale
      additive   -- True = add (union / smooth_union), False = subtract
      smoothing  -- smooth-union k (0.0 = hard union); ignored for subtract
      radius     -- sphere / cylinder radius
      height     -- cylinder height
      axis       -- cylinder axis (0/1/2)
      half       -- box half-extents (3,)
    Non-applicable dimensions carry the rl SDF defaults.
    """
    SPHERE, BOX, CYLINDER = sdf_dmc.SPHERE, sdf_dmc.BOX, sdf_dmc.CYLINDER

    def sphere(radius, translate=(0, 0, 0), rotate=(0, 0, 0), scale=(1, 1, 1),
               additive=True, smoothing=0.0):
        return dict(kind=SPHERE, translate=translate, rotate=rotate, scale=scale,
                    additive=additive, smoothing=smoothing, radius=float(radius),
                    height=1.0, axis=1, half=(0.5, 0.5, 0.5))

    def box(half, translate=(0, 0, 0), rotate=(0, 0, 0), scale=(1, 1, 1),
            additive=True, smoothing=0.0):
        return dict(kind=BOX, translate=translate, rotate=rotate, scale=scale,
                    additive=additive, smoothing=smoothing, radius=1.0,
                    height=1.0, axis=1, half=tuple(float(h) for h in half))

    def cyl(radius, height, axis=1, translate=(0, 0, 0), rotate=(0, 0, 0),
            scale=(1, 1, 1), additive=True, smoothing=0.0):
        return dict(kind=CYLINDER, translate=translate, rotate=rotate, scale=scale,
                    additive=additive, smoothing=smoothing, radius=float(radius),
                    height=float(height), axis=int(axis), half=(0.5, 0.5, 0.5))

    prims = []

    # === MAIN DOME ===
    prims.append(sphere(1.5))                                              # dome_outer (union)
    prims.append(sphere(1.3, additive=False))                             # dome_inner (subtract)
    prims.append(box([3.0, 1.5, 3.0], translate=[0, -1.5, 0],
                     additive=False))                                      # ground_cut (subtract)

    # === ENTRANCE TUNNEL ===
    prims.append(cyl(0.5, 1.2, translate=[0, 0, 1.8], rotate=[90, 0, 0],
                     smoothing=0.15))                                      # tunnel_outer (smooth)
    prims.append(cyl(0.35, 1.4, translate=[0, 0, 1.85], rotate=[90, 0, 0],
                     additive=False))                                      # tunnel_inner (subtract)
    prims.append(box([0.6, 0.25, 1.0], translate=[0, -0.25, 1.8],
                     additive=False))                                      # tunnel_floor (subtract)

    # === ENTRANCE ARCH ===
    prims.append(cyl(0.38, 0.5, translate=[0, 0, 1.3], rotate=[90, 0, 0],
                     additive=False))                                      # doorway (subtract)

    # === FLOOR ===
    prims.append(box([1.2, 0.1, 1.2], translate=[0, -0.1, 0],
                     additive=False))                                      # interior_floor (subtract)

    # === VENTILATION HOLE ===
    prims.append(cyl(0.12, 0.5, translate=[0, 1.35, 0], additive=False))  # vent_hole (subtract)

    # === ICE BLOCK DETAILS ===
    num_base_blocks = 16
    # Loop A -- base ring
    for i in range(num_base_blocks):
        angle = (2 * np.pi * i) / num_base_blocks
        if abs(angle - np.pi / 2) < 0.4 or abs(angle - 3 * np.pi / 2) < 0.4:
            continue
        prims.append(box(
            [0.25, 0.12, 0.08],
            translate=[np.cos(angle) * 1.45, 0.15, np.sin(angle) * 1.45],
            rotate=[0, -np.degrees(angle), 0],
            smoothing=0.08,
        ))
    # Loop B -- mid ring
    for i in range(num_base_blocks):
        angle = (2 * np.pi * (i + 0.5)) / num_base_blocks
        if abs(angle - np.pi / 2) < 0.5:
            continue
        radius_at_height = np.sqrt(1.45 ** 2 - 0.4 ** 2)
        prims.append(box(
            [0.22, 0.11, 0.07],
            translate=[np.cos(angle) * radius_at_height, 0.45,
                       np.sin(angle) * radius_at_height],
            rotate=[8, -np.degrees(angle), 0],
            smoothing=0.06,
        ))
    # Loop C -- upper rings
    for ring in range(2, 5):
        height = 0.3 + ring * 0.28
        if height > 1.2:
            break
        radius_at_height = np.sqrt(max(0, 1.5 ** 2 - height ** 2)) * 0.97
        num_blocks = max(6, num_base_blocks - ring * 3)
        for i in range(num_blocks):
            angle = (2 * np.pi * (i + ring * 0.3)) / num_blocks
            tilt = np.degrees(np.arctan2(height, radius_at_height))
            prims.append(box(
                [0.18 - ring * 0.02, 0.09, 0.05],
                translate=[np.cos(angle) * radius_at_height, height,
                           np.sin(angle) * radius_at_height],
                rotate=[tilt, -np.degrees(angle), 0],
                smoothing=0.05,
            ))

    # === SNOW MOUNDS ===
    prims.append(sphere(0.4, translate=[1.2, -0.15, 0.8], scale=[1.0, 0.3, 1.0],
                        smoothing=0.2))                                    # snow_mound_1
    prims.append(sphere(0.35, translate=[-1.0, -0.15, -0.9],
                        scale=[1.2, 0.25, 0.8], smoothing=0.2))           # snow_mound_2

    return prims


def primitives_to_arrays(prims):
    """Compose the parallel arrays ``sdf_dmc.mesh_from_shapes`` expects from
    a list of primitive dicts. Matrices are built with the same euler kernel
    the source used (``M3 = diag(scale) @ R``, translation in row 3)."""
    n = len(prims)
    matrices = np.empty((n, 4, 4), dtype=np.float64)
    shape_types = np.empty(n, dtype=np.int64)
    additive = np.empty(n, dtype=bool)
    smoothing = np.empty(n, dtype=np.float64)
    radius = np.empty(n, dtype=np.float64)
    height = np.empty(n, dtype=np.float64)
    axis = np.empty(n, dtype=np.int64)
    half = np.empty((n, 3), dtype=np.float64)

    for s, p in enumerate(prims):
        R = sdf_dmc.euler_to_matrix(np.radians(np.asarray(p["rotate"], float)), 0)
        M = np.eye(4)
        M[:3, :3] = np.diag(np.asarray(p["scale"], float)) @ R[:3, :3]
        M[3, :3] = np.asarray(p["translate"], float)
        matrices[s] = M
        shape_types[s] = p["kind"]
        additive[s] = p["additive"]
        smoothing[s] = p["smoothing"]
        radius[s] = p["radius"]
        height[s] = p["height"]
        axis[s] = p["axis"]
        half[s] = p["half"]

    return dict(
        matrices=matrices, shape_types=shape_types, additive=additive,
        smoothing=smoothing, radius=radius, height=height, axis=axis,
        half_extents=half,
    )
