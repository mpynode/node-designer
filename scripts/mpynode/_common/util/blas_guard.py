"""blas_guard -- cap numpy's bundled OpenBLAS to a single thread.

Threaded OpenBLAS LAPACK (e.g. ``np.linalg.inv`` / ``solve`` / ``svd``)
corrupts thread-local scratch state when invoked from Maya's parallel
Evaluation Manager worker threads (TBB), segfaulting the session. Capping
OpenBLAS to one thread eliminates the crash, and transform-sized (4x4)
matrices gain nothing from BLAS threading anyway.

OpenBLAS reads ``OPENBLAS_NUM_THREADS`` only at library LOAD time, so setting
that env var after numpy is already imported is a no-op. We instead poke the
already-loaded shared library directly via ctypes -- this takes effect at
runtime and is what the plugins call once at load.
"""

from __future__ import annotations

import ctypes
import glob
import os


def _openblas_libs():
    """Locate numpy's bundled OpenBLAS shared lib(s); [] if none (e.g. an
    Accelerate- or MKL-backed numpy)."""
    try:
        import numpy as np
    except Exception:
        return []
    npdir = os.path.dirname(np.__file__)
    cands = []
    for sub in (".dylibs", ".libs"):
        cands += glob.glob(os.path.join(npdir, sub, "*openblas*"))
    cands += glob.glob(os.path.join(npdir, "*", "*openblas*"))
    return cands


def limit_blas_threads(n: int = 1):
    """Cap numpy's bundled OpenBLAS to ``n`` threads. Idempotent and safe to
    call when no OpenBLAS is bundled (returns None). Returns a short status
    string identifying the lib + setter used, or None if nothing was set."""
    for so in _openblas_libs():
        try:
            lib = ctypes.CDLL(so)
        except Exception:
            continue
        for fname in ("openblas_set_num_threads64_", "openblas_set_num_threads"):
            fn = getattr(lib, fname, None)
            if fn is not None:
                try:
                    fn(int(n))
                except Exception:
                    continue
                return "ctypes:%s:%s" % (os.path.basename(so), fname)
    return None


def current_blas_threads():
    """Best-effort read of OpenBLAS's current thread count, or None if no
    bundled OpenBLAS exists / the count is unreadable."""
    for so in _openblas_libs():
        try:
            lib = ctypes.CDLL(so)
        except Exception:
            continue
        for fname in ("openblas_get_num_threads64_", "openblas_get_num_threads"):
            fn = getattr(lib, fname, None)
            if fn is not None:
                try:
                    fn.restype = ctypes.c_int
                    return int(fn())
                except Exception:
                    continue
    return None
