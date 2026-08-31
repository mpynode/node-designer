# mPyMeshSDF — native reference build

A by-hand C++ translation of the SDF dual-marching-cubes demo node, kept as a
**golden reference** of what the toolkit's on-demand auto-porter should emit.

The Python side of this demo lives in:

- `mpynode/_common/sdf_dmc.py` — the pure-numpy SDF + dual-marching-cubes math
- `mpynode/_demos/build_mPyMesh_sdf_dmc.py` — the `mPyMesh` node + `addSphere`/
  `addBox`/`addCylinder` commands + `setup()` that wires a render mesh
- `mpynode/_demos/sdf_igloo.py` — the 52-primitive igloo used as the parity case

## Files

- `mPyMeshSDF.cpp` — the hand-port. Registers DG node type `mPyMeshSDF` with the
  same inputs as the Python node (`shapeMatrix` matrix array; `shapeType`,
  `additive`, `smoothing`, `radius`, `height`, `axis`, `halfExtents` parallel
  arrays; `resolution`, `isoValue` scalars) and a built-in `outMesh`. It is a
  faithful translation of every `sdf_dmc.py` function, reproducing the exact
  lookup tables, the lexicographic active-cube ordering, the owned-edge `(0,3,8)`
  faces and the gradient winding — so the topology matches index-for-index.
- `build.py` — compiles `mPyMeshSDF.cpp` via `mpynode.native.toolchain` (the
  same recipe the toolkit uses). `mayapy -B build.py`.
- `parity.py` — builds, loads, and asserts bit-parity against the saved
  `TestSDFIgloo` reference and the numpy module, then times Python vs C++.
  `SDF_NUMPY_PATH=/path/to/numpy mayapy -B parity.py`.

## Verified result

Against `tests/test_assets/test_sdf.igloo.npz` (12509 points / 12518 faces):

- resolution 16: `maxerr ≈ 1.18e-07`, `indices_equal = True` (bit-exact topology)
- resolution 32: 50542 points, `indices_equal = True` — the C++ stays faithful at
  4× the cube density, which numpy handles far more slowly because it allocates a
  full grid array per shape per CSG op while the C++ fuses the per-point fold.

This is a reference artifact, not part of the loaded toolkit; nothing imports it
at runtime.
