"""Live-session viewport benchmark: how does the viewport refresh scale with N
copies of a node -- interpreted vs compiled?

A locator's cost is its draw override, which no headless benchmark reaches:
``ogsRender`` does not execute UI drawables, so ``benchmark_node.py`` reports a
locator as "unmeasurable" and its compiled build never gets a number. The same
question -- "what happens to my scene when I have fifty of these" -- also
matters for every other family, and there the answer is the throughput the
draw loop sees, not a single node's tick.

This script answers it INSIDE an interactive Maya session (it refuses to run in
batch: there is no viewport to time). For each variant and each N it builds a
fresh scene with N instances laid out on a grid, warms the viewport up, then
times ``cmds.refresh(force=True)`` over a number of frames and reports
milliseconds per refresh.

Run from Maya's Script Editor (Python tab), with the repo's ``scripts/`` on
``sys.path`` and the compiled plug-in loadable::

    import viewport_bench
    viewport_bench.run(template=r"templates/MPyLocator/Animated Text/template.mpn",
                       compiled_type="animatedText", copies=(1, 10, 50, 100),
                       frames=30, plugin=r"templates/MPyLocator/Animated Text/build/...mll")

or from a shell with the session's ``mayapy``-free ``maya`` only via
``mayaBatch`` -- which is exactly what it refuses -- so: Script Editor.

* ``template``: the .mpn whose payload becomes the INTERPRETED node
  (``mpn_io.deserialize_node``), so both variants are the same node definition.
* ``compiled_type``: the compiled node type (registered by ``plugin``).
* ``copies``: the N values to sweep. ``frames``: refreshes timed per N.

The pure helpers (``parse_copies``, ``grid_positions``, ``format_table``) are
Maya-free and unit-tested; ``run`` needs the session.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time


def parse_copies(text):
    """``"1,10,50"`` -> ``[1, 10, 50]``; positive, ascending, de-duplicated."""
    if isinstance(text, (list, tuple)):
        vals = [int(x) for x in text]
    else:
        vals = [int(x) for x in str(text).split(",") if x.strip()]
    vals = sorted({v for v in vals if v > 0})
    if not vals:
        raise ValueError("copies: need at least one positive count")
    return vals


def grid_positions(n, spacing=2.0):
    """``n`` (x, 0, z) positions on a centred square grid, ``spacing`` apart.

    A locator drawn on top of another draws the same pixels twice; spreading
    the copies keeps the draw cost the sum of N independent overrides."""
    if n <= 0:
        return []
    side = int(math.ceil(math.sqrt(n)))
    half = (side - 1) * spacing / 2.0
    out = []
    for i in range(n):
        r, c = divmod(i, side)
        out.append((c * spacing - half, 0.0, r * spacing - half))
    return out


def format_table(rows):
    """``rows``: dicts with variant, copies, ms_per_refresh, ms_per_copy.
    Returns the Markdown table the report prints."""
    L = ["| variant | copies | ms / refresh | ms / copy |",
         "|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %d | %.2f | %.3f |" % (
            r["variant"], r["copies"], r["ms_per_refresh"], r["ms_per_copy"]))
    return "\n".join(L)


def _refuse_in_batch(cmds):
    if cmds.about(batch=True):
        raise RuntimeError(
            "viewport_bench needs an interactive Maya session: there is no "
            "viewport to refresh in batch/mayapy. Run it from the Script Editor.")


def _time_refresh(cmds, frames, warmup=5):
    for _ in range(max(0, warmup)):
        cmds.refresh(force=True)
    t0 = time.perf_counter()
    for _ in range(max(1, frames)):
        cmds.refresh(force=True)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0 / max(1, frames)


def _place(cmds, node, pos):
    """Move the transform above a locator shape (or the node itself when it is
    a transform) to ``pos``; a shape-less DG node is left where it is."""
    try:
        parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
    except Exception:
        parents = []
    xform = parents[0] if parents else (
        node if cmds.nodeType(node) == "transform" else None)
    if xform:
        cmds.xform(xform, ws=True, t=pos)


def _node_name_of(py_node):
    """The Maya node name behind an mPyNode wrapper.

    ``deserialize_node`` returns the WRAPPER, whose ``str()`` is a repr
    (``<MPyLocator 'animatedText'>``) and not a name -- placing by that string
    raised on the first row and left one locator in the scene. The wrappers
    expose ``get_name()``; a plain string (the compiled path) passes through."""
    if isinstance(py_node, str):
        return py_node
    for attr in ("get_name", "name", "node"):
        v = getattr(py_node, attr, None)
        if callable(v):
            v = v()
        if isinstance(v, str) and v:
            return v
    raise TypeError("cannot resolve a node name from %r" % (py_node,))


def _make_interpreted(cmds, payload, n):
    from mpynode._common.io import mpn_io
    return [_node_name_of(mpn_io.deserialize_node(payload, skip_selection=True))
            for _ in range(n)]


def _make_compiled(cmds, node_type, n):
    return [cmds.createNode(node_type, skipSelect=True) for _ in range(n)]


def run(template=None, compiled_type=None, copies=(1, 10, 50, 100), frames=30,
        plugin=None, spacing=2.0, json_out=None, log=print):
    """Sweep ``copies`` for the interpreted (``template``) and/or compiled
    (``compiled_type``) variant; print and return the table rows."""
    import maya.cmds as cmds
    _refuse_in_batch(cmds)
    if not template and not compiled_type:
        raise ValueError("give a template (.mpn) and/or a compiled_type")
    if plugin and not cmds.pluginInfo(plugin, q=True, loaded=True):
        cmds.loadPlugin(plugin)
    for p in ("mpynode_api1", "mpynode_api2"):
        if not cmds.pluginInfo(p, q=True, loaded=True):
            try:
                cmds.loadPlugin(p)
            except Exception:
                pass
    payload = None
    if template:
        from mpynode._common.io import mpn_io
        payload = mpn_io.load_mpn(template, trusted=True)

    counts = parse_copies(copies)
    variants = []
    if payload is not None:
        variants.append(("interpreted", lambda n: _make_interpreted(cmds, payload, n)))
    if compiled_type:
        variants.append(("compiled:" + compiled_type,
                         lambda n: _make_compiled(cmds, compiled_type, n)))

    rows = []
    for label, make in variants:
        for n in counts:
            cmds.file(new=True, force=True)
            nodes = make(n)
            for node, pos in zip(nodes, grid_positions(n, spacing)):
                _place(cmds, node, pos)
            cmds.viewFit(all=True)
            ms = _time_refresh(cmds, frames)
            rows.append({"variant": label, "copies": n, "ms_per_refresh": ms,
                         "ms_per_copy": ms / n})
            log("%-28s copies=%-4d %8.2f ms/refresh" % (label, n, ms))
    log("")
    log(format_table(rows))
    if json_out:
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump({"frames": frames, "rows": rows}, fh, indent=2)
    return rows


if __name__ == "__main__":
    # Importable from the Script Editor; a shell launch has no viewport.
    print(__doc__)
    sys.exit(2)
