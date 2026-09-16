"""ndio -- named ARRAY file IO, readable from an interpreted OR a compiled node.

This is the Python half of a two-implementation contract. ``ndio.read`` /
``ndio.write`` are recognised by the C++ transpiler (see
``native/compiler/kernels/nd_io_cpp.py``) and lowered to a hand-written kernel,
so the same compute source runs interpreted and compiled with identical results.
Keep the two halves in lockstep -- especially the DEGRADE-TO-EMPTY rule, which
is what makes a missing or malformed file a parity match instead of a
divergence.

Why arrays and not documents: the transpiler's type lattice has ``scalar``,
``array``, ``shape``, ``rng``, ``texbuf`` and ``str`` -- no dict and no list. An
API that returns one named array per call stays inside that lattice; one that
returns a document never could.

Four backends, sniffed from the leading bytes:

  ``.npy``   numpy's own single-array format (magic ``\\x93NUMPY``)
  ``.ndio``  our container -- MANY named arrays in one file (magic ``NDIO\\x01``)
  ``.json``  a flat object of number arrays (schema-narrow, legacy assets)
  raw        headerless; requires an explicit ``dtype``

Usage in a node's compute::

    from mpynode import ndio

    points  = ndio.read(self.path, "points")
    counts  = ndio.read(self.path, "counts",  dtype="int32")
    indices = ndio.read(self.path, "indices", dtype="int32")
"""

from __future__ import annotations

import json as _json
import os
import re
import struct

import numpy as np

MAGIC_NDIO = b"NDIO\x01"
MAGIC_NPY  = b"\x93NUMPY"

__all__  = ["read", "write", "read_raw", "write_raw", "keys", "frame_path"]

_HASH_RE = re.compile(r"#+")


def frame_path(template, frame):
    """``('mesh.####.json', 7)`` -> ``'mesh.0007.json'``. No ``#`` -> unchanged.

    The FIRST run of ``#`` is replaced by the zero-padded frame. This exists
    because a compiled node cannot format an int into a string -- there is no
    ``str()``, no ``%``, and no f-string in the lowerable surface -- so a
    file-per-frame sequence would otherwise be interpreted-only. The C++ twin is
    ``nd_io_frame_path``; both truncate the frame toward zero and pad the same
    way, including for negative frames (``-7`` at pad 4 -> ``-007``).
    """
    t = template or ""
    m = _HASH_RE.search(t)
    if not m:
        return t
    pad = m.end() - m.start()
    return t[:m.start()] + str(int(frame)).zfill(pad) + t[m.end():]


def _empty(dtype):
    return np.zeros(0, dtype=np.dtype(dtype or np.float64))


def _slurp(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except Exception:
        return None


# One parsed document, keyed by identity-of-CONTENT (path + mtime + size). That
# makes scrubbing a timeline free: every frame after the first is a dict hit.
# The C++ half caches on the SAME key (nd_io_stat_key), so interpreted and
# compiled do the same number of disk reads. mtime+size rather than path alone
# is what picks up a file REWRITTEN under the same name instead of serving it
# stale.
_CACHE_KEY = [None]
_CACHE_DOC = [None]


def _stat_key(path):
    # NANOSECOND mtime, matching nd_io_stat_key: whole-second resolution serves
    # a stale entry for a file rewritten within the same second at the same
    # size -- exactly what a sim writing frame after frame does.
    try:
        st = os.stat(path)
        return "%s|%d|%d" % (path, int(st.st_mtime_ns), int(st.st_size))
    except Exception:
        return "%s|missing" % path


# ---------------------------------------------------------------------------
# readers -- each returns {name: ndarray} or None when the format doesn't match
# ---------------------------------------------------------------------------
def _parse_npy(buf):
    if len(buf) < 10 or buf[:6] != MAGIC_NPY:
        return None
    try:
        import io

        return {"": np.load(io.BytesIO(buf), allow_pickle=False)}
    except Exception:
        return None


def _parse_ndio(buf):
    if len(buf) < 9 or buf[:5] != MAGIC_NDIO:
        return None
    out = {}
    try:
        p = 5
        (n,) = struct.unpack_from("<I", buf, p)
        p += 4
        for _ in range(n):
            (nl,) = struct.unpack_from("<H", buf, p)
            p += 2
            name = buf[p:p + nl].decode("utf-8")
            p += nl
            kind = chr(buf[p])
            size = int(chr(buf[p + 1]))
            p += 2
            ndim = buf[p]
            p += 1
            shape = struct.unpack_from("<%dq" % ndim, buf, p)
            p += 8 * ndim
            (nbytes,) = struct.unpack_from("<Q", buf, p)
            p += 8
            dt  = np.dtype("<%s%d" % (kind, size))
            arr = np.frombuffer(buf[p:p + nbytes], dtype=dt)
            p += nbytes
            out[name] = arr.reshape(shape) if shape else arr
    except Exception:
        return None
    return out


def _parse_json(buf):
    try:
        doc = _json.loads(buf.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    out = {}
    for k, v in doc.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = np.asarray([float(v)], dtype=np.float64)
        elif isinstance(v, list):
            try:
                a = np.asarray(v, dtype=np.float64)
            except Exception:
                continue
            # A ragged list is not an array; skip rather than raise, so one
            # unusable key cannot take the whole file down.
            if a.dtype == object:
                continue
            out[k] = a
    return out


def _load_doc(path):
    key = _stat_key(path)
    if _CACHE_KEY[0] == key:
        return _CACHE_DOC[0]
    doc = {}
    buf = _slurp(path)
    if buf is not None:
        for parse in (_parse_npy, _parse_ndio, _parse_json):
            got = parse(buf)
            if got is not None:
                doc = got
                break
    _CACHE_KEY[0] = key
    _CACHE_DOC[0] = doc
    return doc


# ---------------------------------------------------------------------------
# public surface
# ---------------------------------------------------------------------------
def read(path, name="", dtype=None):
    """One named array from ``path``. Empty array if absent/malformed -- never raises.

    ``name=""`` selects the sole array of a single-array format (``.npy``).
    ``dtype`` casts the result; omit it to keep the file's own dtype.
    """
    doc = _load_doc(path)
    arr = doc.get(name if name is not None else "")
    if arr is None:
        return _empty(dtype)
    if dtype is not None:
        arr = arr.astype(np.dtype(dtype), copy=False)
    return arr


def keys(path):
    """Array names available in ``path`` (``[""]`` for a single-array format)."""
    return sorted(_load_doc(path).keys())


def read_raw(path, dtype=np.float64):
    """A headerless binary file as a flat 1-D array of ``dtype``."""
    buf = _slurp(path)
    if buf is None:
        return _empty(dtype)
    dt = np.dtype(dtype)
    n  = len(buf) // dt.itemsize
    return np.frombuffer(buf[:n * dt.itemsize], dtype=dt)


def write_raw(path, arr):
    """``arr`` as a headerless little-endian buffer. True on success."""
    try:
        np.ascontiguousarray(arr).tofile(path)
        return True
    except Exception:
        return False


def write(path, **arrays):
    """Write named arrays as one ``.ndio`` container. True on success.

    Byte layout (little-endian throughout)::

        "NDIO\\x01" | u32 count
        per array:  u16 namelen | name | dtype kind + size | u8 ndim
                    | i64 shape[ndim] | u64 nbytes | payload
    """
    try:
        body = bytearray()
        for name, arr in arrays.items():
            a = np.ascontiguousarray(arr)
            if a.dtype.kind not in "fiu" or a.dtype.itemsize > 8:
                raise ValueError("ndio: unsupported dtype %r for %r"
                                 % (a.dtype, name))
            nb = name.encode("utf-8")
            body += struct.pack("<H", len(nb)) + nb
            body += a.dtype.kind.encode("ascii")
            body += str(a.dtype.itemsize).encode("ascii")
            body += struct.pack("<B", a.ndim)
            body += struct.pack("<%dq" % a.ndim, *a.shape)
            raw = a.tobytes()
            body += struct.pack("<Q", len(raw)) + raw
        tmp = "%s.tmp%d" % (path, os.getpid())
        with open(tmp, "wb") as fh:
            fh.write(MAGIC_NDIO)
            fh.write(struct.pack("<I", len(arrays)))
            fh.write(bytes(body))
        os.replace(tmp, path)
        return True
    except Exception:
        return False
