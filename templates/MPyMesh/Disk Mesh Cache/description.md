# Disk Mesh Cache

Plays a cached deforming mesh (an `mPyMesh`) off disk. Use it for a baked sim or a cached deformation whose topology never changes -- point `cachePath` at a cache file and scrub the timeline.

The whole take lives in one file, so scrubbing is an array lookup rather than a file open. That is also the constraint: the vertex and face counts must be the same on every frame. If they change frame to frame, use **JSON Mesh Reader** instead.

A missing or malformed file gives an empty mesh rather than an error, so a wrong path shows up as nothing on screen rather than a failed evaluation.

## Inputs

* `cachePath` -- the cache file to play. `ripple_cache.ndio` ships next to this template. Also reads `.npy` and headerless raw, so you can swap formats without changing anything.
* `frame` -- which frame to show, already wired to the timeline.
* `scale` -- a uniform multiplier on the cached positions.

## Outputs

* The generated mesh for the current frame, with the topology from the cache.

## Create + Run demo

Wires the shipped ripple cache and sets the playback range -- press play to watch the cached deformation run.
