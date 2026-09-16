"""Idle-load probe (live Maya session only): with N locators in the scene and
NOBODY touching Maya, how often does the viewport redraw, how long does each
redraw take, and how busy is the main thread?

viewport_bench forces a redraw every frame and therefore measures cost PER
redraw only. This probe never calls refresh: it installs counters, hands
control back to Maya, and closes a measurement window ``seconds`` later from a
timer. Everything after ``run()`` returns is timer-driven, so the Script Editor
call returns immediately and the table prints when the whole queue is done.

Per (config, N) row:
  redraws/s        3dView post-render callbacks per wall second
  render ms        mean pre-render -> post-render wall time of the panel's
                   render pass only (evaluation/prepareForDraw are outside
                   it); main CPU % is the load figure
  main CPU %       main-thread CPU time / wall (GetThreadTimes)
  process CPU %    whole-process CPU time / wall (time.process_time)

Configs (see the ``*_config`` helpers): compiled node type, interpreted .mpn
payload (optionally patched, e.g. auto_refresh -> False), or Mesh Regions
bound to the template's head.ma with N gizmos cycling its component tags.
``sweep=True`` on a config moves the cursor across the viewport during the
window (30 Hz zigzag) so hover transitions fire; otherwise the cursor is
parked in the screen's top-left corner so no hover state changes.

Run from Maya's Script Editor (Python tab) with ``scripts/`` and
``tools/harness/`` on ``sys.path``::

    import idle_probe
    PLUG = r"templates/MPyLocator/Animated Text/build/animatedText/animatedText.mll"
    idle_probe.run([idle_probe.compiled_config("cpp", "animatedText", plugin=PLUG)],
                   seconds=10, json_out="idle_cpp.json")

Leave Maya alone until the table prints (~45 s for three N values). The probe
parks the mouse cursor and, for a ``sweep`` config, moves it. Like
``viewport_bench``, it refuses to run in batch: there is no viewport to observe.
The pure helpers (``format_table``, the CPU clocks, the ``*_config`` builders)
are unit-tested without a session; ``run`` needs one.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
import traceback


# ---------------------------------------------------------------- CPU clocks
class _FILETIME(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]


def main_thread_cpu_s():
    """CPU seconds consumed by the CALLING thread (Windows); None elsewhere."""
    if sys.platform != "win32":
        return None
    k = ctypes.windll.kernel32
    # GetCurrentThread returns the pseudo-handle -2; with the default c_int
    # restype it is truncated to 0xFFFFFFFE and GetThreadTimes fails.
    k.GetCurrentThread.restype = ctypes.c_void_p
    k.GetThreadTimes.restype   = ctypes.c_int
    k.GetThreadTimes.argtypes  = [ctypes.c_void_p] + [ctypes.POINTER(_FILETIME)] * 4
    h                          = k.GetCurrentThread()
    c, e, kt, ut = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
    if not k.GetThreadTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut)):
        return None

    def secs(ft):
        return ((ft.hi << 32) | ft.lo) * 1e-7
    return secs(kt) + secs(ut)


def process_cpu_s():
    return time.process_time()


# ---------------------------------------------------------------- reporting
def format_table(rows):
    L = ["| config | copies | sweep | wall s | redraws | redraws/s | render ms | main CPU % | process CPU % |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %d | %s | %.1f | %d | %.1f | %s | %s | %s |" % (
            r["config"], r["copies"], "yes" if r.get("sweep") else "no", r["wall_s"],
            r["redraws"], r["redraws_per_s"],
            "%.2f" % r["ms_per_redraw"] if r.get("ms_per_redraw") is not None else "-",
            "%.0f" % r["main_cpu_pct"] if r.get("main_cpu_pct") is not None else "-",
            "%.0f" % r["proc_cpu_pct"] if r.get("proc_cpu_pct") is not None else "-"))
    return "\n".join(L)


# ---------------------------------------------------------------- Qt helpers
def _qt():
    try:
        from PySide6 import QtCore, QtGui, QtWidgets  # Maya 2025+
        import shiboken6 as shib
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets  # Maya <= 2024
        import shiboken2 as shib
    return QtCore, QtGui, QtWidgets, shib


def _view_rect_global(omui):
    """Global-screen QRect of the active 3D view widget (None if unavailable)."""
    try:
        QtCore, QtGui, QtWidgets, shib = _qt()
        view = omui.M3dView.active3dView()
        w    = shib.wrapInstance(int(view.widget()), QtWidgets.QWidget)
        tl   = w.mapToGlobal(w.rect().topLeft())
        br   = w.mapToGlobal(w.rect().bottomRight())
        return QtCore.QRect(tl, br)
    except Exception:
        return None


def _set_cursor(x, y):
    try:
        _, QtGui, _, _ = _qt()
        QtGui.QCursor.setPos(int(x), int(y))
    except Exception:
        pass


# ---------------------------------------------------------------- scene makers
def _model_panel(cmds):
    ed    = cmds.playblast(activeEditor=True) or ""
    panel = ed.split("|")[-1] if ed else ""
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        return panel
    for p in cmds.getPanel(type="modelPanel") or []:
        if p in (cmds.getPanel(visiblePanels=True) or []):
            return p
    raise RuntimeError("no visible modelPanel to observe")


def _ensure_mpynode_plugins(cmds):
    """The interpreted node types (mPyLocator, ...) live in the mpynode_api*
    plug-ins; without them deserialize_node makes an unknown node."""
    for p in ("mpynode_api1", "mpynode_api2"):
        if not cmds.pluginInfo(p, q=True, loaded=True):
            try:
                cmds.loadPlugin(p)
            except Exception:
                pass


def _vb():
    """tools/harness/viewport_bench (scene helpers): from sys.path when the
    caller put tools/harness there, else loaded from the sibling file."""
    try:
        import viewport_bench
        return viewport_bench
    except ImportError:
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewport_bench.py")
        spec = importlib.util.spec_from_file_location("viewport_bench", path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def compiled_config(label, node_type, plugin=None, copies=(0, 10, 100), sweep=False):
    def scene(cmds):
        cmds.file(new=True, force=True)
        if plugin and not cmds.pluginInfo(plugin, q=True, loaded=True):
            cmds.loadPlugin(plugin)

    def make(cmds, n):
        return _vb()._make_compiled(cmds, node_type, n)
    return {"label": label, "scene": scene, "make": make, "copies": list(copies),
            "sweep": sweep, "grid": True}


def interpreted_config(label, template, copies=(0, 10, 100), patch=None, sweep=False):
    """``patch(expression) -> expression`` edits the node's draw expression
    before it is instantiated (e.g. ``auto_refresh = True`` -> ``False``)."""
    box = {}

    def payload():
        if "p" not in box:
            from mpynode._common.io import mpn_io
            p = dict(mpn_io.load_mpn(template, trusted=True))
            if patch:
                p["expression"] = patch(p["expression"])
            box["p"] = p
        return box["p"]

    def scene(cmds):
        cmds.file(new=True, force=True)
        _ensure_mpynode_plugins(cmds)

    def make(cmds, n):
        return _vb()._make_interpreted(cmds, payload(), n) if n else []
    return {"label": label, "scene": scene, "make": make, "copies": list(copies),
            "sweep": sweep, "grid": True}


def static_patch(expression):
    """Animated Text: never request idle redraws."""
    return expression.replace("self.auto_refresh = True", "self.auto_refresh = False")


def mesh_regions_config(label, template, head_ma, copies=(0, 10, 100), sweep=False,
                        patch=None):
    """N Mesh Regions gizmos on the template's own head, cycling its component
    tags (8 mouth regions), all bound to ``faceShape.worldMesh[0]``."""
    box = {}

    def payload():
        if "p" not in box:
            from mpynode._common.io import mpn_io
            p = dict(mpn_io.load_mpn(template, trusted=True))
            if patch:
                p["expression"] = patch(p["expression"])
            box["p"] = p
        return box["p"]

    def scene(cmds):
        try:
            cmds.file(head_ma, open=True, force=True, ignoreVersion=True)
        except Exception as exc:      # Arnold attrs missing -> file still loads
            print("[idle_probe] head.ma opened with errors: %s" % str(exc).splitlines()[0])
        if not cmds.ls(type="mesh"):
            raise RuntimeError("head.ma has no mesh after open")
        _ensure_mpynode_plugins(cmds)

    def make(cmds, n):
        meshes = [m for m in cmds.ls(type="mesh", long=True, noIntermediate=True)
                  if not m.endswith("Orig")]
        mesh = meshes[0]
        tags = cmds.geometryAttrInfo(mesh + ".worldMesh[0]", componentTagNames=True) or []
        if not tags:
            raise RuntimeError("no component tags on %s" % mesh)
        out = []
        for i in range(n):
            node = _vb()._make_interpreted(cmds, payload(), 1)[0]
            cmds.connectAttr(mesh + ".worldMesh[0]", node + ".inMesh", force=True)
            cmds.setAttr(node + ".regionTag", tags[i % len(tags)], type="string")
            out.append(node)
        cmds.select(mesh); cmds.viewFit(); cmds.select(clear=True)
        return out
    return {"label": label, "scene": scene, "make": make, "copies": list(copies),
            "sweep": sweep, "grid": False}


def compiled_mesh_regions_config(label, node_type, plugin, head_ma, copies=(0, 10, 100),
                                 sweep=False):
    """N COMPILED Mesh Regions nodes on the template's head, cycling its
    component tags -- the compiled twin of mesh_regions_config."""
    def scene(cmds):
        try:
            cmds.file(head_ma, open=True, force=True, ignoreVersion=True)
        except Exception as exc:      # Arnold attrs missing -> file still loads
            print("[idle_probe] head.ma opened with errors: %s" % str(exc).splitlines()[0])
        if not cmds.ls(type="mesh"):
            raise RuntimeError("head.ma has no mesh after open")
        if plugin and not cmds.pluginInfo(plugin, q=True, loaded=True):
            cmds.loadPlugin(plugin)

    def make(cmds, n):
        meshes = [m for m in cmds.ls(type="mesh", long=True, noIntermediate=True)
                  if not m.endswith("Orig")]
        mesh = meshes[0]
        tags = cmds.geometryAttrInfo(mesh + ".worldMesh[0]", componentTagNames=True) or []
        if not tags:
            raise RuntimeError("no component tags on %s" % mesh)
        out = []
        for i in range(n):
            node = cmds.createNode(node_type, skipSelect=True)
            cmds.connectAttr(mesh + ".worldMesh[0]", node + ".inMesh", force=True)
            cmds.setAttr(node + ".regionTag", tags[i % len(tags)], type="string")
            out.append(node)
        cmds.select(mesh); cmds.viewFit(); cmds.select(clear=True)
        return out
    return {"label": label, "scene": scene, "make": make, "copies": list(copies),
            "sweep": sweep, "grid": False}


# ---------------------------------------------------------------- the probe
class Probe:
    def __init__(self, configs, seconds=10.0, warmup=2.0, json_out=None, log=print,
                 park_cursor=True):
        import maya.cmds as cmds
        import maya.api.OpenMaya as om
        import maya.api.OpenMayaUI as omui
        if cmds.about(batch=True):
            raise RuntimeError("idle_probe needs an interactive Maya session")
        self.cmds, self.om, self.omui = cmds, om, omui
        self.queue = [(c, n) for c in configs for n in c["copies"]]
        self.seconds, self.warmup, self.json_out, self.log = float(seconds), float(warmup), json_out, log
        self.park = park_cursor
        self.rows, self.cb_ids = [], []
        self.panel = _model_panel(cmds)
        self._reset_counters()
        self.done = False

    # -- counters
    def _reset_counters(self):
        self.n_redraw, self.sum_ms, self._pre_t = 0, 0.0, None

    def _on_pre(self, *_):
        self._pre_t = time.perf_counter()

    def _on_post(self, *_):
        self.n_redraw += 1
        if self._pre_t is not None:
            self.sum_ms += (time.perf_counter() - self._pre_t) * 1000.0
            self._pre_t = None

    def _install(self):
        M = self.omui.MUiMessage
        self.cb_ids = [M.add3dViewPreRenderMsgCallback(self.panel, self._on_pre),
                       M.add3dViewPostRenderMsgCallback(self.panel, self._on_post)]

    def _uninstall(self):
        for i in self.cb_ids:
            try:
                self.om.MMessage.removeCallback(i)
            except Exception:
                pass
        self.cb_ids = []

    # -- heartbeat: ONE persistent timer that only compares clocks and queues
    #    work on the idle loop. Removing/adding MTimerMessage callbacks from
    #    inside a timer callback froze Maya (timer list mutated mid-dispatch),
    #    so no callback is ever added or removed from within a callback here.
    _HEARTBEAT = 1.0 / 30.0

    def _arm(self, delay, fn):
        self.deadline, self.pending = time.perf_counter() + float(delay), fn

    def _tick(self, *_):
        try:
            if self.sweeping:
                self._sweep_step()
            if self.pending is not None and time.perf_counter() >= self.deadline:
                fn, self.pending = self.pending, None
                import maya.utils
                maya.utils.executeDeferred(self._guard(fn))
        except Exception:
            traceback.print_exc()

    def _guard(self, fn):
        def call():
            try:
                fn()
            except Exception:
                traceback.print_exc()
                self.stop()
        return call

    # -- cursor
    def _park(self):
        if self.park:
            _set_cursor(2, 2)

    def _start_sweep(self):
        self.rect = _view_rect_global(self.omui)
        if self.rect is None:
            self.log("[idle_probe] no view rect; sweep skipped")
            return
        self.sweep_i, self.sweeping = 0, True

    def _sweep_step(self):
        rect, i = self.rect, self.sweep_i
        self.sweep_i += 1
        rows, steps = 6, 60                          # one row crossing = 2 s at 30 Hz
        r = (i // steps) % rows
        f = (i % steps) / float(steps - 1)
        if r % 2:
            f = 1.0 - f
        _set_cursor(rect.left() + f * rect.width(), rect.top() + (r + 0.5) * rect.height() / rows)

    def _stop_sweep(self):
        self.sweeping = False

    # -- state machine
    def start(self):
        self.log("[idle_probe] %d windows of %.0fs (+%.0fs warm-up each); leave Maya alone."
                 % (len(self.queue), self.seconds, self.warmup))
        self.pending, self.deadline, self.sweeping, self.rect = None, 0.0, False, None
        self.heartbeat = self.om.MTimerMessage.addTimerCallback(self._HEARTBEAT, self._tick)
        import maya.utils
        maya.utils.executeDeferred(self._guard(self._next))
        return self

    def stop(self):
        """Tear down from the idle loop, never from inside a callback."""
        self.pending, self.sweeping, self.done = None, False, True
        hb, self.heartbeat = getattr(self, "heartbeat", None), None

        def teardown():
            self._uninstall()
            if hb is not None:
                try:
                    self.om.MMessage.removeCallback(hb)
                except Exception:
                    pass
        import maya.utils
        maya.utils.executeDeferred(teardown)

    def _next(self):
        if not self.queue:
            self._finish(); return
        cfg, n = self.queue.pop(0)
        self.cur = (cfg, n)
        cfg["scene"](self.cmds)
        nodes = cfg["make"](self.cmds, n) if n else []
        if cfg.get("grid", True) and nodes:
            vb = _vb()
            for node, pos in zip(nodes, vb.grid_positions(n, 2.0)):
                vb._place(self.cmds, node, pos)
            self.cmds.viewFit(all=True)
        self.cmds.select(clear=True)
        self._park()
        self.log("[idle_probe] %-28s N=%-4d built; warming up" % (cfg["label"], n))
        self._arm(self.warmup, self._open)

    def _open(self):
        cfg, n = self.cur
        self._reset_counters(); self._install()
        if cfg.get("sweep"):
            self._start_sweep()
        else:
            self._park()
        self.t0 = time.perf_counter()
        self.c0 = main_thread_cpu_s(); self.p0 = process_cpu_s()
        self._arm(self.seconds, self._close)

    def _close(self):
        cfg, n = self.cur
        wall = time.perf_counter() - self.t0
        c1 = main_thread_cpu_s(); p1 = process_cpu_s()
        self._stop_sweep(); self._uninstall()
        row = {"config": cfg["label"], "copies": n, "sweep": bool(cfg.get("sweep")),
               "wall_s": wall, "redraws": self.n_redraw,
               "redraws_per_s": self.n_redraw / wall if wall > 0 else 0.0,
               "ms_per_redraw": (self.sum_ms / self.n_redraw) if self.n_redraw else None,
               "main_cpu_pct":  (100.0 * (c1 - self.c0) / wall) if (c1 is not None and self.c0 is not None and wall > 0) else None,
               "proc_cpu_pct": (100.0 * (p1 - self.p0) / wall) if wall > 0 else None}
        self.rows.append(row)
        self.log("[idle_probe] %-28s N=%-4d %6.1f redraws/s  render %s ms  main %s%%  proc %s%%" % (
            cfg["label"], n, row["redraws_per_s"],
            "%.1f" % row["ms_per_redraw"] if row["ms_per_redraw"] is not None else "-",
            "%.0f" % row["main_cpu_pct"] if row["main_cpu_pct"] is not None else "-",
            "%.0f" % row["proc_cpu_pct"] if row["proc_cpu_pct"] is not None else "-"))
        import maya.utils
        maya.utils.executeDeferred(self._guard(self._next))

    def _finish(self):
        self.stop()
        self.log(""); self.log(format_table(self.rows))
        if self.json_out:
            with open(self.json_out, "w", encoding="utf-8") as fh:
                json.dump({"seconds": self.seconds, "rows": self.rows}, fh, indent=2)
            self.log("[idle_probe] wrote %s" % self.json_out)


def run(configs, seconds=10.0, warmup=2.0, json_out=None, park_cursor=True):
    """Queue every (config, N) window and return at once; results print when
    the queue is done (``probe.rows`` / ``json_out``)."""
    return Probe(configs, seconds=seconds, warmup=warmup, json_out=json_out,
                 park_cursor=park_cursor).start()


if __name__ == "__main__":
    print(__doc__)
    sys.exit(2)
