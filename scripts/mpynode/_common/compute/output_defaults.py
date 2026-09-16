"""Default seed values for USER output buffers (compute pre-population).

When an expression starts, every USER output is pre-seeded with a sensible
default so an empty / partial expression still produces valid data and so
the user can *mutate in place* instead of constructing a value from
scratch. The convention mirrors Maya's stock plugs:

  * scalar ``float``/``double`` -> ``0.0``; ``int`` -> ``0``; ``bool`` ->
    ``False``; ``vector``/``euler`` -> ``[0, 0, 0]``; ``matrix`` ->
    identity; ``string`` -> ``""``; anything else -> ``None``.

  * ARRAY (multi) outputs get a PRE-SIZED ``(N, ...)`` buffer of the same
    per-type default -- e.g. a ``matrix`` array seeds ``(N, 4, 4)`` of
    identity. This is what lets vectorized slice-assignment work::

        self.outMatrices[:, 3, :3] = [1, 2, 3]   # set all translations

    ``N`` is supplied by the caller (the connected element count of the
    output multi); ``N == 0`` yields a correctly-shaped empty buffer so
    slicing is a harmless no-op rather than an error.

The array buffers are raw numpy (mutable + ideal for slice-assignment);
the harvest path (``write_multi_plug_value``) already accepts
``(N, ...)`` arrays / lists, so a seeded-then-mutated buffer round-trips
to the plugs unchanged.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def scalar_default(attr_type: str) -> Any:
    """Per-type default for a SINGLE (non-array) output."""
    if attr_type in ("float", "double"):
        return 0.0
    if attr_type == "int":
        return 0
    if attr_type == "bool":
        return False
    if attr_type in ("vector", "euler", "color"):
        return [0.0, 0.0, 0.0]
    if attr_type == "quaternion":
        return [0.0, 0.0, 0.0, 1.0]
    if attr_type == "matrix":
        return np.eye(4, dtype=np.float64)
    if attr_type in ("string", "hex"):
        return ""
    return None


def array_default(attr_type: str, n: int) -> Any:
    """Pre-sized ``(N, ...)`` buffer for an ARRAY (multi) output."""
    n = max(int(n), 0)
    if attr_type in ("float", "double"):
        return np.zeros((n,), dtype=np.float64)
    if attr_type == "int":
        return np.zeros((n,), dtype=np.int64)
    if attr_type == "bool":
        return np.zeros((n,), dtype=bool)
    if attr_type in ("vector", "euler", "color"):
        return np.zeros((n, 3), dtype=np.float64)
    if attr_type == "quaternion":
        # (N, 4) of identity [0,0,0,1] -- mutable, ideal for slice-assignment.
        return np.broadcast_to(
            np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64), (n, 4)
        ).copy()
    if attr_type == "matrix":
        # (N, 4, 4) of identity -- mutable, ideal for slice-assignment
        # (e.g. ``M[:, 3, :3] = ...``). ``broadcast_to(...).copy()`` is the
        # cheap way to tile the identity.
        return np.broadcast_to(np.eye(4, dtype=np.float64), (n, 4, 4)).copy()
    if attr_type in ("string", "hex"):
        return ["" for _ in range(n)]
    return [None] * n


def output_default(attr_type: str, is_array: bool = False, n: int = 0) -> Any:
    """Seed value for a USER output: a scalar default, or a pre-sized
    ``(N, ...)`` buffer when ``is_array`` (see module docstring)."""
    if is_array:
        return array_default(attr_type, n)
    return scalar_default(attr_type)


def seed_user_output_defaults_api2(fn_node, output_map) -> dict:
    """Return ``{name: seed}`` for every USER output in ``output_map``, using
    the base contract seed (scalar default, or a pre-sized ``(N, ...)`` buffer
    for arrays). ``N`` for an array output = max connected logical index + 1 of
    its output multi (queried through the api2 ``fn_node``), so an in-place
    slice-assign ``self.outArr[i] = v`` has real elements to write.

    This is the api2 analogue of ``seed_array_outputs_api1`` -- the api2 own-
    path compute types (mesh / nurbs curve / nurbs surface / file) call it to
    seed their user outputs faithfully instead of the bare ``None`` they used
    before (which made ``self.outArr[0] = v`` raise on a ``NoneType``).
    Best-effort per attr: any query failure falls back to ``n = 0`` (a
    correctly-shaped empty buffer), never raising.
    """
    seeded: dict = {}
    for out_attr_name, meta in (output_map or {}).items():
        meta      = meta or {}
        attr_type = meta.get("attr_type", "float")
        is_array  = bool(meta.get("is_array", False))
        n         = 0
        if is_array:
            try:
                oplug = fn_node.findPlug(out_attr_name, True)
                idxs  = list(oplug.getExistingArrayAttributeIndices())
                n     = (max(idxs) + 1) if idxs else 0
            except Exception:
                n = 0
        seeded[out_attr_name] = output_default(attr_type, is_array, n)
    return seeded


# ---- api1 seed + harvest for ARRAY user outputs ----
#
# api2 nodes pre-seed every user output into ``compute_locals`` and harvest
# them in a loop after exec. api1 nodes (mPyTransform / deformer / generic)
# write user outputs via *direct* plug writes (``self.out = v`` -> SelfProxy
# Tier 2), with no pre-seeded buffer -- so an ARRAY output couldn't be
# slice-assigned in place. These helpers add ONLY the array-output piece on
# the api1 side: seed a pre-sized ``(N, ...)`` buffer into ``compute_locals``
# (so ``self.outM`` is a mutable buffer that supports
# ``self.outM[:, 3, :3] = ...``), then harvest it back element-by-element
# through the SAME plug-write path the user's ``self.outM[i] = v`` already
# uses. Scalar outputs are untouched (they keep the direct-write path).


def _array_output_size_api1(fn_node, attr_name: int) -> int:
    """N for an api1 output multi = max connected logical index + 1."""
    import maya.OpenMaya as om1

    try:
        plug = fn_node.findPlug(attr_name, True)
        if not plug.isArray():
            return 0
        idxs = om1.MIntArray()
        plug.getExistingArrayAttributeIndices(idxs)
        nlen = idxs.length()
        if nlen == 0:
            return 0
        return max(idxs[i] for i in range(nlen)) + 1
    except Exception:
        return 0


def seed_array_outputs_api1(node_mobject) -> dict:
    """Return ``{name: pre-sized buffer}`` for each ARRAY user output of an
    api1 node (read from its ``_outputAttrs`` schema, sized to the output
    multi's connected span). ``{}`` on any failure -- the caller then just
    behaves as before."""
    try:
        import maya.OpenMaya as om1

        from mpynode._common.io import serialization
    except Exception:
        return {}
    try:
        fn       = om1.MFnDependencyNode(node_mobject)
        outs_str = fn.findPlug("_outputAttrs", True).asString() or ""
    except Exception:
        return {}
    if not outs_str:
        return {}
    try:
        output_map = serialization.decode_attr_map(outs_str) or {}
    except Exception:
        return {}
    seeded: dict = {}
    for name, meta in output_map.items():
        meta = meta or {}
        if not meta.get("is_array"):
            continue
        n            = _array_output_size_api1(fn, name)
        seeded[name] = array_default(meta.get("attr_type", "float"), n)
    return seeded


def harvest_array_outputs_api1(plug_proxy, compute_locals: dict, names) -> None:
    """Write each seeded array-output buffer back to its plug, reusing the
    plug proxy's per-element write path (``MatrixArrayView``/``PlugListProxy``
    ``__setitem__`` -> ``_write_plug``). Best-effort; never raises."""
    for name in names:
        buf = compute_locals.get(name)
        if buf is None:
            continue
        try:
            arr_proxy = getattr(plug_proxy, name)
        except Exception:
            continue
        try:
            count = len(buf)
        except Exception:
            continue
        for i in range(count):
            try:
                arr_proxy[i] = buf[i]
            except Exception:
                pass
