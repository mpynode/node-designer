"""nd_runtime.h loader + cache."""
from __future__ import annotations

import os


_ND_RUNTIME_CPP_CACHE = None

def _nd_runtime_cpp():
    """The nd:: header-only runtime, inlined verbatim into a generated node .cpp
    so the deterministically-lowered compute body (which calls ``nd::``) is
    self-contained -- no separate include path or link step at build time. The
    file's ``#ifndef`` include guard makes the inline idempotent."""
    global _ND_RUNTIME_CPP_CACHE
    if _ND_RUNTIME_CPP_CACHE is None:
        with open(os.path.join(os.path.dirname(__file__), "nd_runtime.h")) as f:
            _ND_RUNTIME_CPP_CACHE = f.read()
    return _ND_RUNTIME_CPP_CACHE
