"""Readers for the ``.npz`` / ``.json`` geometry-and-shape exchange files.

Two containers, one schema. A ``.npz`` stores nested records as flat
slash-joined keys (``index_3/offsets``); the ``.json`` twin stores the same
thing as real nested objects (``{"index_3": {"offsets": ...}}``). Flat
top-level keys (a mesh's ``points`` / ``counts`` / ``indices``) stay flat in
both. Normalising the JSON form to the npz's flat keys means everything
downstream is written once.

The three payload kinds, and the class each one already maps onto:

    mesh    name, points (V,3), counts (F,), indices (sum counts,)
            [+ normals, normal_indices]                  -> _api2.geometry.Mesh
    uvs     index_k/{name, points (K,2), counts, indices} -> _api2.geometry.UVSet
    shapes  index_k/{name, offsets (K,3), indices (K,)}   -> _api2.morph.Morph

These files are field-for-field serialisations of those objects, so the readers
below are constructors, not translators.

Why this is not ``mpynode.ndio``
--------------------------------
``ndio`` is the COMPUTE-side API: the C++ transpiler recognises ``ndio.read`` /
``ndio.write`` and lowers them, so its one-named-array-per-call shape and its
flat-JSON schema exist to stay inside the transpiler's type lattice, which has
no dict and no list. It also has no ``.npz`` backend. Widening it would mean
changing a two-implementation compiled contract for the sake of authoring code
that never needs to compile. So these live here instead, beside the wrappers.

``offsets`` are RAW ``target - base`` deltas -- exactly what a connected target
mesh yields, and exactly what ``MPyBlendShape.bake_deltas`` stores. A corrective
is sculpted as the correction itself, so nothing is subtracted out of it on the
way in or on the way through.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np


# ``index_10`` must sort AFTER ``index_9``. Lexicographic ordering silently
# permutes the stack, which re-points every alias onto the wrong deltas.
_INDEX_RE = re.compile(r"^index_(\d+)/")


def _flatten(obj, prefix=""):
    """Nested JSON objects -> the npz's flat ``index_k/field`` keys."""
    out = {}
    for key, val in obj.items():
        path = "%s%s" % (prefix, key)
        if isinstance(val, dict):
            out.update(_flatten(val, path + "/"))
        else:
            out[path] = val
    return out


def load_document(path):
    """``{flat_key: value}`` for either container. Values stay raw."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".npz":
        with np.load(path, allow_pickle=True) as z:
            return {k: z[k] for k in z.files}
    if ext == ".json":
        with open(path) as fh:
            doc = json.load(fh)
        if not isinstance(doc, dict):
            raise ValueError("%s: expected a JSON object at the top level, got %s"
                             % (path, type(doc).__name__))
        return _flatten(doc)
    raise ValueError("%s: not a .npz or .json shape file" % path)


def document_kind(doc):
    """``"mesh"`` / ``"uvs"`` / ``"shapes"``, or None when it is none of them.

    Sniffed from the keys rather than the filename, so a mis-named file is
    diagnosed instead of half-read.
    """
    if "points" in doc and "counts" in doc and "indices" in doc:
        return "mesh"
    if any(k.endswith("/offsets") for k in doc):
        return "shapes"
    if any(k.endswith("/points") for k in doc):
        return "uvs"
    return None


def _record_indices(doc):
    """The ``index_<k>`` ordinals present, in NUMERIC order."""
    found = set()
    for key in doc:
        m = _INDEX_RE.match(key)
        if m:
            found.add(int(m.group(1)))
    return sorted(found)


def _as_str(val):
    """npz stores a str as a 0-d array; JSON stores it as a str."""
    return str(val)


def _as_f64(val, width):
    a = np.asarray(val, dtype=np.float64)
    if a.size == 0:
        return np.zeros((0, width), dtype=np.float64)
    return a.reshape(-1, width)


def read_mesh(path):
    """``{name, points (V,3), counts (F,), indices (C,)}`` from a mesh file."""
    doc = load_document(path)
    kind = document_kind(doc)
    if kind != "mesh":
        raise ValueError("%s: expected a MESH file (points/counts/indices); "
                         "found %s" % (path, kind or "no recognised schema"))
    return {
        "name": _as_str(doc.get("name", "")),
        "points": _as_f64(doc["points"], 3),
        "counts": np.asarray(doc["counts"], dtype=np.int64).reshape(-1),
        "indices": np.asarray(doc["indices"], dtype=np.int64).reshape(-1),
    }


def read_shapes(path):
    """``[{name, indices (K,), offsets (K,3)}]`` in weight[] order.

    A target with ZERO moved vertices is kept, not skipped: it still owns a
    weight index and an alias, and dropping it would shift every later index.
    Measured on a real 297-shape set, 88 of them are empty.
    """
    doc = load_document(path)
    kind = document_kind(doc)
    if kind != "shapes":
        raise ValueError("%s: expected a SHAPES file (index_k/offsets); found %s"
                         % (path, kind or "no recognised schema"))

    out = []
    for k in _record_indices(doc):
        name = _as_str(doc.get("index_%d/name" % k, ""))
        idx = np.asarray(doc.get("index_%d/indices" % k, []),
                         dtype=np.int64).reshape(-1)
        off = _as_f64(doc.get("index_%d/offsets" % k, []), 3)
        if idx.shape[0] != off.shape[0]:
            raise ValueError(
                "%s: index_%d (%r) has %d indices but %d offsets"
                % (path, k, name, idx.shape[0], off.shape[0]))
        out.append({"name": name, "indices": idx, "offsets": off})
    return out


def dense_offsets(record, n_verts):
    """A sparse ``{indices, offsets}`` record as a dense ``(n_verts, 3)`` field.

    Out-of-range vertex ids are DROPPED rather than clamped: clamping would
    silently pile a stray delta onto vertex 0.
    """
    out = np.zeros((int(n_verts), 3), dtype=np.float64)
    idx = record["indices"]
    if idx.size:
        keep = (idx >= 0) & (idx < int(n_verts))
        out[idx[keep]] = record["offsets"][keep]
    return out
