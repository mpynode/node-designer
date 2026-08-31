# Disk Mesh Cache

Plays a cached deforming mesh (an `mPyMesh`) off disk. Use it for a baked sim
or cached deformation whose topology never changes. Compiles to pure C++.

Point `cachePath` at `ripple_cache.ndio` (shipped next to this template) and
scrub the timeline.

## What it demonstrates

File I/O inside a compute block that the C++ transpiler can lower. The reads
are ordinary calls:

```python
frames  = ndio.read(self.cachePath, "points")
counts  = ndio.read(self.cachePath, "counts",  dtype=np.int64)
indices = ndio.read(self.cachePath, "indices", dtype=np.int64)
```

`ndio` has two implementations that are kept in lockstep -- `mpynode/ndio.py`
for the interpreted node, and a hand-written C++ kernel for the compiled one.
Both sniff the format from the leading bytes, both cache on path + mtime +
size, and both return an EMPTY array for a missing or malformed file rather
than raising. That last rule is what makes interpreted and compiled agree even
in the failure case.

Measured on the shipped asset (48 frames, 1089 verts): interpreted 1.16
ms/frame, compiled 0.35 ms/frame, and the vertex buffers are bitwise
identical.

## Why one file, not one per frame

`points` is `(FRAMES, VERTS, 3)` -- the whole take in a single array. Topology
is constant, so one `counts` / `indices` pair serves every frame. Compute
slices `frames[i]`, so scrubbing is an array index, not a file open.

Reading a per-frame path instead needs the frame number substituted into the
filename. Integer-to-string formatting is not part of the lowerable surface, so
that substitution lives in the kernel as `ndio.frame_path` -- see the
`JSON Mesh Reader` template, which compiles too. Use that node when the topology
must CHANGE between frames; when it does not, packing the whole take into one
array is the faster shape.

## Formats

`ndio.read` sniffs four, so the same node reads any of them:

| Format | Detected by | Holds |
|---|---|---|
| `.ndio` | `NDIO\x01` | many NAMED arrays -- what this demo uses |
| `.npy` | `\x93NUMPY` | one array (ask for it with `name=""`) |
| JSON | `{` | a flat object of number arrays |
| raw | nothing | headerless; use `ndio.read_raw(path, dtype=...)` |

Writing works too, and also lowers: `ndio.write(path, points=pts)`,
`ndio.write_raw`, `np.save`, `arr.tofile`.

`np.load` is deliberately NOT lowerable -- it carries no dtype, so the compiled
element type would be a guess. Use `ndio.read(path, name, dtype=...)`.

## Regenerating the asset

```
mayapy make_cache.py
```

Writes a 48-frame, 1089-vertex ripple surface (~1.2 MB) and verifies it
round-trips bitwise through the reader.
