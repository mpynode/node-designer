"""cProfile drill-down capture for the instrumentation package.

Split out of the former ``instrumentation.py`` module (behavior unchanged).
"""

from __future__ import annotations

import pstats


# ---- cProfile drill-down capture ----


def encode_cprofile_stats(profiler) -> list[dict]:
    """Convert a cProfile.Profile to a list of per-function dicts.

    Each row: ``{function, calls, tottime_ms, cumtime_ms, percall_ms}``.
    Sorted by cumulative time descending. Returns empty list on failure.
    """
    out: list[dict] = []
    try:
        stats_obj = pstats.Stats(profiler)
    except Exception:
        return []
    try:
        for func, (cc, nc, tt, ct, _callers) in stats_obj.stats.items():
            file_, line, name = func
            short_file = file_.rsplit("/", 1)[-1] if file_ else ""
            label      = f"{name} ({short_file}:{line})" if short_file else name
            calls      = int(nc)
            tottime_ms = float(tt) * 1000.0
            cumtime_ms = float(ct) * 1000.0
            percall_ms = (float(ct) / cc * 1000.0) if cc else 0.0
            out.append(
                {
                    "function":   label,
                    "calls":      calls,
                    "tottime_ms": tottime_ms,
                    "cumtime_ms": cumtime_ms,
                    "percall_ms": percall_ms,
                }
            )
    except Exception:
        return []
    out.sort(key=lambda r: r["cumtime_ms"], reverse=True)
    return out
