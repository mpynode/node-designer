# JSON Mesh Reader

Plays a mesh off disk (an `mPyMesh`), one file per frame. Unlike a packed cache, **the topology may change from frame to frame** -- points and faces can come and go as it plays. That is the reason to reach for this node instead of **Disk Mesh Cache**.

`path` is a filename template: the first run of `#` is replaced with the zero-padded frame number, so `mesh.####.json` reads `mesh.0001.json`, `mesh.0002.json` and so on as the timeline advances.

A missing or malformed file gives an empty mesh rather than an error. Scrub past the end of the sequence to see it -- no file, no geometry, no error.

## Inputs

* `path` -- the filename template, with `#` marking where the frame number goes. Also reads `.npy`, `.ndio` and headerless raw, so the same node plays any of them.
* `frame` -- which file to read, already wired to the timeline.

## Outputs

* The generated mesh for the current frame, with whatever topology that file holds.

## File format

```json
{"points": [[x, y, z], ...], "counts": [4, 4, ...], "indices": [0, 1, 2, 3, ...]}
```

`points` may also be flat -- `[x, y, z, x, y, z, ...]`.

To rebuild the shipped sequence, run `mayapy make_sequence.py` beside this template. It writes 24 frames, about 85 KB in total, into `seq/`.

## Choosing between this and Disk Mesh Cache

| | JSON Mesh Reader | Disk Mesh Cache |
|---|---|---|
| Layout | one file per frame | whole take in one file |
| Topology | may change per frame | must be constant |
| Format | JSON (text) | `.ndio` (binary) |
| Reads | one per new frame | one, then cached |

## Create + Run demo

Wires the shipped sequence, then play the timeline. Frame N holds N cubes on a helix, so the mesh grows from 8 vertices at frame 1 to 192 at frame 24 -- which a constant-topology cache could not express.
