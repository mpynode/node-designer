"""Viewport mouse-hover tracker for mPyLocator.

Maya's MPxDrawOverride is NOT told when the cursor passes over an object
-- ``MGeometryUtilities.displayStatus`` only reports selection states,
never hover. So passive hover is detected here: one session-level timer
casts a ray through the active viewport at the cursor and finds the
nearest mPyLocator the ray hits. That node is "hovered", exposed to the
expression as ``self.hovered``. On a hover change we
``setGeometryDrawDirty`` the affected node(s) so they repaint.

Two hit-test modes:

  * **bbox** (default, ~free): ray vs the locator's world bounding box.
  * **shape** (opt-in via ``self.precise_hover = True``): ray vs the actual
    drawn polygon triangles, ray transformed into the locator's local
    space. Pixel-shape accurate for non-box gizmos. The triangle soup is
    re-registered every draw (``set_shape``), so it tracks the LIVE drawn
    region -- crucially, this test is NOT pre-filtered by the DAG bounding
    box: a ``world_space`` gizmo's DAG box is the default unit cube on the
    locator transform and does NOT follow the drawn geometry, so a bbox
    pre-filter would reject rays over any region that grew past the
    original box (the "hover only works on the original region" bug). This
    mirrors the compiled C++ port, which is likewise precise-first.

Perf (benchmarked):
  * Scan uses cached ``MDagPath``s (rebuilt only on node add/remove) +
    API bounding boxes -- ~5.5x cheaper than per-poll cmds queries.
  * A precise (``precise_hover``) gizmo runs the vectorized ray-tri test
    (~30 us) every poll; a plain gizmo uses the cheap bbox test only.

Crash safety mirrors ``draw_refresh``: MObjectHandle.isValid() guards,
scene events + plug-in uninit tear the timer + callbacks down. GUI-only:
``start()`` no-ops in batch (``cmds.about(batch=True)``), so headless
evaluation is unaffected.
"""

from __future__ import annotations

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.api.OpenMayaRender as omr
import numpy as np
from maya import cmds


_POLL_SEC = 1.0 / 30.0
_LOCATOR_TYPE = "mPyLocator"

# Lifecycle state.
_timer_id = None
_scene_cb_ids: list = []
_node_cb_ids: list = []

# Hovered node (at most one).
_hovered_hash = None
_hovered_handle = None

# Cached shape dagpaths; None means "dirty, rebuild on next poll".
_dps = None

# Opt-in precise shapes: hashCode -> (T, 3, 3) local-space triangle soup.
_shapes: dict = {}


# ---- Public API ----


def is_hovered(node_obj: "om.MObject") -> bool:
    """True if ``node_obj`` is the locator currently under the cursor."""
    if _hovered_hash is None:
        return False
    try:
        return om.MObjectHandle(node_obj).hashCode() == _hovered_hash
    except Exception:
        return False


def set_shape(node_obj: "om.MObject", tris) -> None:
    """Register a local-space triangle soup ``(T, 3, 3)`` for precise
    (ray-vs-triangle) hover on this locator. Called from the draw override
    when the expression sets ``self.precise_hover = True``."""
    try:
        h = om.MObjectHandle(node_obj).hashCode()
        arr = np.asarray(tris, dtype=np.float64)
        if arr.ndim == 3 and arr.shape[1:] == (3, 3) and arr.shape[0] > 0:
            _shapes[h] = arr
        else:
            _shapes.pop(h, None)
    except Exception:
        pass


def clear_shape(node_obj: "om.MObject") -> None:
    """Drop precise-hover data for this locator (revert to bbox hover)."""
    try:
        _shapes.pop(om.MObjectHandle(node_obj).hashCode(), None)
    except Exception:
        pass


def ensure_started() -> None:
    """Start the tracker on first use (idempotent, GUI-only). Safe to call
    from prepareForDraw every draw."""
    if _timer_id is None:
        start()


# ---- Cursor ray (HiDPI-correct) ----


def _cursor_global():
    try:
        from PySide6.QtGui import QCursor
    except Exception:
        try:
            from PySide2.QtGui import QCursor
        except Exception:
            return None
    try:
        return QCursor.pos()
    except Exception:
        return None


def _view_widget(view):
    try:
        ptr = view.widget()
    except Exception:
        ptr = None
    if ptr is not None and hasattr(ptr, "mapFromGlobal"):
        return ptr
    try:
        import shiboken6 as shiboken
        from PySide6 import QtWidgets
    except Exception:
        try:
            import shiboken2 as shiboken
            from PySide2 import QtWidgets
        except Exception:
            return None
    try:
        return shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)
    except Exception:
        return None


def _device_pixel_ratio(widget) -> float:
    for attr in ("devicePixelRatioF", "devicePixelRatio"):
        try:
            return float(getattr(widget, attr)())
        except Exception:
            pass
    return 1.0


def _cursor_ray():
    """(origin, direction) of the cursor ray in world space, or None when
    the cursor isn't over the active viewport. HiDPI-corrected (Qt logical
    px -> M3dView physical px via devicePixelRatio)."""
    try:
        view = omui.M3dView.active3dView()
    except Exception:
        return None
    gp = _cursor_global()
    if gp is None:
        return None
    widget = _view_widget(view)
    if widget is None:
        return None
    try:
        local = widget.mapFromGlobal(gp)
        dpr = _device_pixel_ratio(widget)
        x = int(round(local.x() * dpr))
        y = int(round(view.portHeight() - local.y() * dpr))  # origin bottom-left
        if x < 0 or y < 0 or x > view.portWidth() or y > view.portHeight():
            return None
        src = om.MPoint()
        vec = om.MVector()
        view.viewToWorld(x, y, src, vec)
        return src, vec
    except Exception:
        return None


# ---- Hit tests ----


def _ray_aabb(o, d, lo, hi):
    """Slab ray/AABB. Returns near t (>=0) or None."""
    tmin, tmax = 0.0, 1e30
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if o[i] < lo[i] or o[i] > hi[i]:
                return None
        else:
            t1 = (lo[i] - o[i]) / d[i]
            t2 = (hi[i] - o[i]) / d[i]
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return None
    return tmin


def _ray_triangles(o, d, tris):
    """Vectorized Moller-Trumbore. ``o``/``d`` np(3,), ``tris`` (T,3,3).
    Returns the nearest hit t (>0) or None."""
    v0 = tris[:, 0, :]
    e1 = tris[:, 1, :] - v0
    e2 = tris[:, 2, :] - v0
    pvec = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, pvec)
    ok = np.abs(det) > 1e-9
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    tvec = o - v0
    u = np.einsum("ij,ij->i", tvec, pvec) * inv
    qvec = np.cross(tvec, e1)
    v = (qvec @ d) * inv
    tt = np.einsum("ij,ij->i", e2, qvec) * inv
    hit = ok & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0) & (tt > 1e-6)
    return float(tt[hit].min()) if hit.any() else None


# ---- Locator dagpath cache (rebuilt only when nodes are added/removed) ----


def _mark_dirty(*_unused):
    global _dps
    _dps = None


def _on_node_removed(node_obj, *_unused):
    global _dps
    _dps = None
    try:
        _shapes.pop(om.MObjectHandle(node_obj).hashCode(), None)
    except Exception:
        pass


def _locator_dps():
    """Cached list of locator shape MDagPaths; rebuilt on add/remove."""
    global _dps
    if _dps is not None:
        return _dps
    dps = []
    sel = om.MSelectionList()
    for name in cmds.ls(type=_LOCATOR_TYPE, long=True) or []:
        try:
            sel.add(name)
        except Exception:
            pass
    for i in range(sel.length()):
        try:
            dps.append(sel.getDagPath(i))
        except Exception:
            pass
    _dps = dps
    return _dps


# ---- Poll ----


def _poll(*_unused):
    try:
        ray = _cursor_ray()
        if ray is None:
            _set_hovered(None)
            return
        src, vec = ray
        o = (src.x, src.y, src.z)
        d = (vec.x, vec.y, vec.z)

        best_t = 1e30
        best_obj = None
        for dp in _locator_dps():
            try:
                if not dp.isValid():
                    continue
                obj = dp.node()
                tris = _shapes.get(om.MObjectHandle(obj).hashCode())
                if tris is not None:
                    # Precise (opt-in self.precise_hover): ray-vs-triangle in
                    # LOCAL space, tested DIRECTLY with no DAG-bbox pre-filter.
                    # The triangle soup is refreshed every draw so it tracks the
                    # live region, but the DAG bbox is NOT (for a world_space
                    # gizmo it stays the default unit cube), so gating on it
                    # would reject rays over any region grown past the original
                    # box. Mirrors the compiled C++ port, also precise-first.
                    w2l = dp.inclusiveMatrixInverse()
                    lo_pt = src * w2l
                    ld = vec * w2l
                    tt = _ray_triangles(
                        np.array([lo_pt.x, lo_pt.y, lo_pt.z]),
                        np.array([ld.x, ld.y, ld.z]),
                        tris,
                    )
                    if tt is None or tt >= best_t:
                        continue
                    best_t = tt
                    best_obj = obj
                else:
                    # bbox mode: ray vs the world DAG bounding box, which is the
                    # whole test here rather than a pre-filter.
                    fn = om.MFnDagNode(dp)
                    bb = om.MBoundingBox(fn.boundingBox)
                    bb.transformUsing(dp.inclusiveMatrix())
                    lo = bb.min
                    hi = bb.max
                    t = _ray_aabb(o, d, (lo.x, lo.y, lo.z), (hi.x, hi.y, hi.z))
                    if t is None or t >= best_t:
                        continue
                    best_t = t
                    best_obj = obj
            except Exception:
                continue
        _set_hovered(best_obj)
    except Exception:
        pass


def _set_hovered(new_obj):
    """Update the hovered node; repaint any node whose state changed."""
    global _hovered_hash, _hovered_handle
    new_hash = None
    new_handle = None
    if new_obj is not None:
        try:
            new_handle = om.MObjectHandle(new_obj)
            new_hash = new_handle.hashCode()
        except Exception:
            new_hash = None
            new_handle = None
    if new_hash == _hovered_hash:
        return
    old_handle = _hovered_handle
    _hovered_hash = new_hash
    _hovered_handle = new_handle
    for handle in (old_handle, new_handle):
        if handle is None:
            continue
        try:
            if handle.isValid():
                omr.MRenderer.setGeometryDrawDirty(handle.object())
        except Exception:
            pass


# ---- Lifecycle ----


def _on_scene_event(*_unused):
    global _hovered_hash, _hovered_handle, _dps
    _hovered_hash = None
    _hovered_handle = None
    _dps = None
    _shapes.clear()


def _ensure_callbacks():
    if _scene_cb_ids:
        return
    for event in (
        om.MSceneMessage.kBeforeNew,
        om.MSceneMessage.kBeforeOpen,
        om.MSceneMessage.kMayaExiting,
    ):
        try:
            _scene_cb_ids.append(om.MSceneMessage.addCallback(event, _on_scene_event))
        except Exception:
            pass
    # Invalidate the dagpath cache when locators are created/deleted.
    try:
        _node_cb_ids.append(
            om.MDGMessage.addNodeAddedCallback(_mark_dirty, _LOCATOR_TYPE)
        )
    except Exception:
        pass
    try:
        _node_cb_ids.append(
            om.MDGMessage.addNodeRemovedCallback(_on_node_removed, _LOCATOR_TYPE)
        )
    except Exception:
        pass


def start() -> bool:
    """Start the hover poll timer. Idempotent; GUI-only (no-op in batch /
    mayapy). Returns True if running."""
    global _timer_id
    if _timer_id is not None:
        return True
    try:
        if cmds.about(batch=True):
            return False
    except Exception:
        return False
    if _cursor_global() is None:
        return False
    _ensure_callbacks()
    try:
        _timer_id = om.MTimerMessage.addTimerCallback(_POLL_SEC, _poll)
    except Exception:
        _timer_id = None
        return False
    return True


def stop() -> None:
    """Stop the timer + drop all state + remove callbacks (plug-in uninit)."""
    global _timer_id
    if _timer_id is not None:
        try:
            om.MMessage.removeCallback(_timer_id)
        except Exception:
            pass
        _timer_id = None
    for cb_id in list(_scene_cb_ids) + list(_node_cb_ids):
        try:
            om.MMessage.removeCallback(cb_id)
        except Exception:
            pass
    _scene_cb_ids.clear()
    _node_cb_ids.clear()
    _on_scene_event()
