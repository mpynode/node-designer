"""Version-safe, pickle-free codec for the common stored-var value types.

Encodes numpy arrays / scalars, ``bytes``, tuples, and primitives / lists /
dicts (recursively) into a **JSON-able** structure, and decodes it back. Unlike
pickle, the encoded form bakes in **no numpy module path** (arrays are stored as
``.npy`` bytes), so it round-trips cleanly across numpy 1.x <-> 2.x (the
``numpy.core`` -> ``numpy._core`` rename that breaks pickled ndarrays across the
2.0 boundary). Anything it can't represent faithfully (object-dtype arrays,
custom classes, scipy objects, ...) raises :class:`UnsupportedValue` so the
caller can fall back to (trust-gated) pickle.

Pure Python + stdlib; numpy is imported lazily so the module stays importable
where numpy is absent (only *using* it on numpy data needs numpy present).
No Maya / Qt imports.

Encoded shapes (``RESERVED`` = the type-tag key):
  primitive (None/bool/int/str)      -> itself
  finite float                       -> itself
  non-finite float                   -> {RESERVED: "float", "v": "nan"|"inf"|"-inf"}
  bytes                              -> {RESERVED: "bytes", "data": <b64>}
  tuple                              -> {RESERVED: "tuple", "items": [...]}
  list                               -> [...]                  (JSON-native)
  str-keyed dict w/o RESERVED key    -> {k: ...}               (JSON-native)
  any other dict (non-str / RESERVED)-> {RESERVED: "dict", "items": [[k, v], ...]}
  ndarray                            -> {RESERVED: "ndarray", "npy": <b64 .npy>}
  numpy scalar                       -> {RESERVED: "npscalar", "dtype": str, "data": <b64>}
"""

from __future__ import annotations

import base64
import io
import math
from typing import Any

# Type-tag key, chosen to be unlikely in user data. A user dict that DOES
# contain it is routed to the explicit "dict"/items form, so it can never be
# mistaken for an encoded special type.
RESERVED = "__sv__"


class UnsupportedValue(Exception):
    """Raised by :func:`encode_value` for a value (or nested leaf) that the
    safe codec cannot represent faithfully (object-dtype arrays, custom
    classes, scipy objects, ...). The caller falls back to gated pickle."""


def _try_numpy():
    try:
        import numpy
        return numpy
    except Exception:
        return None


def _ndarray_npy_b64(arr, np) -> str:
    """``.npy`` bytes (base64) for ``arr``, preserving its EXACT shape.

    We must NOT call ``np.ascontiguousarray`` unconditionally: it promotes a
    0-d array to shape ``(1,)`` (silent corruption of e.g. ``np.array(3.5)``).
    ``write_array`` records the real ``arr.shape`` in the header and handles
    both C- and F-contiguous layouts (it stores the fortran_order flag), so we
    only copy a genuinely non-contiguous array of rank >= 1 (where the copy
    can't change the shape)."""
    buf = io.BytesIO()
    if arr.ndim == 0 or arr.flags["C_CONTIGUOUS"] or arr.flags["F_CONTIGUOUS"]:
        data = arr
    else:
        data = np.ascontiguousarray(arr)
    # allow_pickle=False is belt-and-suspenders: write_array would otherwise
    # pickle object arrays (which we've already rejected).
    np.lib.format.write_array(buf, data, allow_pickle=False)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _encode_ndarray(arr, np) -> dict:
    if arr.dtype.kind == "O":
        # object arrays hold Python-object pointers -> only pickle can do it.
        raise UnsupportedValue("object-dtype ndarray")
    return {RESERVED: "ndarray", "npy": _ndarray_npy_b64(arr, np)}


def encode_value(v: Any) -> Any:
    """Encode ``v`` to a JSON-able structure, or raise :class:`UnsupportedValue`."""
    # numpy FIRST: np.float64 subclasses ``float`` and np.str_ subclasses
    # ``str``, so a numpy scalar would otherwise be swallowed by the
    # Python-primitive branch below and silently lose its dtype. (encode runs
    # at save/flush, not on the compute hot path, so the import probe is fine.)
    np = _try_numpy()
    if np is not None:
        if isinstance(v, np.ndarray):
            return _encode_ndarray(v, np)
        if isinstance(v, np.void):
            # a structured/void scalar (one row of a structured array): route
            # through a 0-d ndarray so the FULL dtype (field names) survives --
            # ``v.dtype.str`` would flatten it to a bare void ("|V12").
            if v.dtype.kind == "O":
                raise UnsupportedValue("object-dtype void scalar")
            return {RESERVED: "npvoid", "npy": _ndarray_npy_b64(np.asarray(v), np)}
        if isinstance(v, np.generic):
            return {RESERVED: "npscalar", "dtype": v.dtype.str,
                    "data": base64.b64encode(np.asarray(v).tobytes()).decode("ascii")}

    # primitives (bool before int: bool is an int subclass)
    if v is None or isinstance(v, bool) or isinstance(v, int) or isinstance(v, str):
        return v
    if isinstance(v, float):
        if math.isfinite(v):
            return v
        return {RESERVED: "float",
                "v": "nan" if math.isnan(v) else ("inf" if v > 0 else "-inf")}
    if isinstance(v, bytes):
        return {RESERVED: "bytes", "data": base64.b64encode(v).decode("ascii")}
    if isinstance(v, tuple):
        return {RESERVED: "tuple", "items": [encode_value(x) for x in v]}
    if isinstance(v, list):
        return [encode_value(x) for x in v]

    if isinstance(v, dict):
        if all(isinstance(k, str) for k in v) and RESERVED not in v:
            return {k: encode_value(val) for k, val in v.items()}
        return {RESERVED: "dict",
                "items": [[encode_value(k), encode_value(val)] for k, val in v.items()]}

    raise UnsupportedValue("unsupported type %r" % type(v).__name__)


def decode_value(j: Any) -> Any:
    """Reconstruct a value from :func:`encode_value` output."""
    if isinstance(j, dict):
        tag = j.get(RESERVED)
        if tag is not None:
            if tag == "float":
                return {"nan": float("nan"), "inf": float("inf"),
                        "-inf": float("-inf")}[j["v"]]
            if tag == "bytes":
                return base64.b64decode(j["data"])
            if tag == "tuple":
                return tuple(decode_value(x) for x in j["items"])
            if tag == "dict":
                return {decode_value(k): decode_value(val) for k, val in j["items"]}
            if tag == "ndarray":
                import numpy as np
                buf = io.BytesIO(base64.b64decode(j["npy"]))
                return np.lib.format.read_array(buf, allow_pickle=False)
            if tag == "npvoid":
                import numpy as np
                buf = io.BytesIO(base64.b64decode(j["npy"]))
                arr = np.lib.format.read_array(buf, allow_pickle=False)
                return arr[()]  # 0-d structured array -> np.void scalar
            if tag == "npscalar":
                import numpy as np
                arr = np.frombuffer(base64.b64decode(j["data"]),
                                    dtype=np.dtype(j["dtype"]))
                return arr[0]
            raise ValueError("unknown value_codec tag %r" % (tag,))
        return {k: decode_value(val) for k, val in j.items()}
    if isinstance(j, list):
        return [decode_value(x) for x in j]
    return j


def can_encode(v: Any) -> bool:
    """True if :func:`encode_value` would succeed (no side effects beyond a
    trial encode). Convenience for callers deciding safe-codec vs pickle."""
    try:
        encode_value(v)
        return True
    except UnsupportedValue:
        return False
