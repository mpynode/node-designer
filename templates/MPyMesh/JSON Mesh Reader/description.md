# JSON Mesh Reader

Plays a mesh off disk (an `mPyMesh`), **one JSON file per frame**. Points and
faces can come and go as it plays. Compiles to pure C++.

**Create + Run demo**, then play the timeline.

## What it demonstrates

`path` is a filename *template*. `ndio.frame_path` replaces the first run of `#`
with the zero-padded frame, so `.../mesh.####.json` reads `mesh.0001.json`,
`mesh.0002.json` ... as `frame` advances:

```python
resolved = ndio.frame_path(self.path, self.frame)
pts      = ndio.read(resolved, "points")
counts   = ndio.read(resolved, "counts",  dtype=np.int64)
indices  = ndio.read(resolved, "indices", dtype=np.int64)
```

That substitution is the one string operation a compiled compute cannot express
on its own -- there is no `str()`, no `%`, and no f-string in the lowerable
surface -- so it lives in the C++ kernel beside the reader. Both halves produce
byte-identical filenames, including for negative and fractional frames.

Because every frame is its own file, **the topology may change from frame to
frame.** The shipped sequence leans on that: frame N holds N cubes on a helix,
so the mesh runs from 8 vertices at frame 1 to 192 at frame 24. A single packed
cache array cannot express that -- constant topology is a requirement there.
That is the reason to reach for this node instead of `Disk Mesh Cache`.

## Caching

`ndio.read` caches the parsed file on path + mtime + size, in both the Python
half and the C++ kernel. Re-evaluating a frame the node already holds -- a
dirty-propagation retrigger, a viewport refresh, another node pulling `outMesh`
-- does no file IO. Advancing to a new frame resolves a new filename and reads
it. Rewriting a file under the same name changes the key, so new contents are
picked up rather than served stale.

## File format

```json
{"points": [[x, y, z], ...], "counts": [4, 4, ...], "indices": [0, 1, 2, 3, ...]}
```

`points` may also be flat (`[x, y, z, x, y, z, ...]`). A missing or malformed
file yields an empty mesh -- the node never raises. Scrub past frame 24 to see
it: no file, no geometry, no error, in both the interpreted and compiled node.

`ndio.read` sniffs the format from the leading bytes, so the same node also
reads `.npy`, the `.ndio` multi-array container, and headerless raw -- swap the
sequence for any of them without touching the compute.

## Regenerating the sequence

```
mayapy make_sequence.py
```

Writes 24 frames (~85 KB total) into `seq/`.

## Choosing between this and Disk Mesh Cache

| | JSON Mesh Reader | Disk Mesh Cache |
|---|---|---|
| Layout | one file per frame | whole take in one file |
| Topology | may change per frame | must be constant |
| Format | JSON (text) | `.ndio` (binary) |
| Reads | one per new frame | one, then cached |
| Compiles | yes | yes |
