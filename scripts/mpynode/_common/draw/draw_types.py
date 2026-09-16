"""Object-oriented draw types for mPyLocator -- ``self.draw = DrawCircle(...)``.

The house idiom everywhere else in MPyNode is *read an object from ``self.X``,
write an object to ``self.Y``* (``self.outMesh = Mesh(points=..., counts=...)``).
These types bring the locator's draw surface into that idiom, replacing five
write-only dicts of parallel numpy arrays whose lengths have to be kept in sync
by hand.

    self.draw = (DrawCircle(center=(0, 0, -1), radius=R, color=ORANGE)
                 + DrawCurve(pts, color=lcol)
                 + DrawText("hip_ctrl", position=(0, 2, 0), screen_space=True))

A plain LIST is the same drawing, nested as deeply as you like -- handy when the
items are accumulated in a loop, and the form the Watch tab can show one row per
operation:

    self.draw = [background, [ring, ticks], DrawText("hip_ctrl", ...)]

Design rules, and why:

* **``+`` only.** No ``*`` and no ``-``. ``Morph * 0.5`` is unambiguous because a
  morph is a homogeneous numeric quantity; ``DrawCircle(...) * 2`` could equally
  mean twice the radius, twice the brightness, or drawn twice. Scaling and
  restyling are chainable METHODS (``.scaled()``, ``.colored()``) so the intent
  is written down. Note ``+`` here means GROUP, unlike ``Morph.__add__`` which
  merges overlapping data.
* **The hierarchy follows the TARGET BUFFER, not the shape family.** ``DrawBox``
  is a ``DrawPrimitive`` (Maya draws box / sphere / cone / cylinder / circle
  natively via the ``shapes`` buffer), NOT a ``DrawMesh`` -- inheriting from mesh
  would throw the native primitive away, emit vertices nobody asked for, and
  lose the primitive's screen-space behaviour. Which buffer an item flushes into
  is also exactly what determines the styling it can carry: only a mesh has an
  outline and per-face colours.
* **Composition, not conflation.** ``DrawMesh`` *accepts* a ``Mesh`` (duck-typed
  on ``.points`` / ``.counts`` / ``.indices``) rather than being one. ``Mesh`` is
  an I/O type carrying attached mode, a data MObject, an ``MFnMesh``, component
  tags and UV sets -- none of which a drawable needs, and it should never carry
  outline width or hover opt-in.

Maya-free and pure numpy, like its neighbour ``draw_buffers`` -- everything here
is testable without a viewport. ``to_commands()`` flattens a drawing into an
ORDERED list of ``{"slot": ..., "buffer": {...}}`` records, one per authored
item, which both the Python draw override and the compiled C++ node replay
front-to-back. Authoring order IS draw order.
"""
from __future__ import annotations

import copy as _copy
import json as _json

import numpy as np

from mpynode._common.draw.draw_buffers import normalize_color, normalize_space

__all__ = [
    "DrawItem", "DrawGroup", "DrawPrimitive",
    "DrawSphere", "DrawBox", "DrawCone", "DrawCylinder", "DrawCircle",
    "DrawMesh", "DrawCurve", "DrawLines", "DrawPoints", "DrawText",
    "to_commands", "draw_from_json",
]


# ---- array coercion helpers ----
def _points(value, what="points"):
    """``(N,3)`` float64. A bare ``(3,)`` is promoted to a single row so one
    circle costs one tuple instead of a nested one-element array."""
    a = np.asarray(value, dtype=np.float64)
    if a.ndim == 1:
        if a.size != 3:
            raise ValueError("%s: a single point needs 3 components, got %d"
                             % (what, a.size))
        return a.reshape(1, 3)
    if a.ndim == 2 and a.shape[1] == 3:
        return a
    if a.ndim == 2 and a.shape[1] == 2:          # 2D convenience, pad z=0
        pad        = np.zeros((a.shape[0], 3), dtype=np.float64)
        pad[:, :2] = a
        return pad
    raise ValueError("%s: expected (N,3), got %s" % (what, (a.shape,)))


def _scalars(value, n, default, what="value"):
    """``(n,)`` float64 broadcast from a scalar or a length-n sequence."""
    if value is None:
        return np.full((n,), float(default), dtype=np.float64)
    a = np.asarray(value, dtype=np.float64).ravel()
    if a.size == 1:
        return np.full((n,), float(a[0]), dtype=np.float64)
    if a.size == n:
        return a
    raise ValueError("%s: expected a scalar or %d values, got %d"
                     % (what, n, a.size))


def _flags(value, n, default):
    """``list[bool]`` of length n, broadcast from a scalar or a sequence."""
    if value is None:
        return [bool(default)] * n
    if isinstance(value, (bool, np.bool_)):
        return [bool(value)] * n
    seq = list(value)
    if len(seq) == 1:
        return [bool(seq[0])] * n
    if len(seq) != n:
        raise ValueError("filled: expected 1 or %d values, got %d"
                         % (n, len(seq)))
    return [bool(v) for v in seq]


def _strings(value, n=None):
    """``list[str]``. A bare string is ONE label, not a list of characters."""
    if isinstance(value, str):
        out = [value]
    else:
        out = [str(s) for s in value]
    if n is not None and len(out) == 1 and n > 1:
        out = out * n
    return out


def _merge_space(items, slot):
    """One ``space`` per buffer dict -- the renderer reads a single key. Mixing
    within ONE slot is an explicit error rather than a silent pick."""
    spaces = {it._space for it in items}
    if len(spaces) > 1:
        raise ValueError(
            "cannot mix draw spaces %s in the same %r buffer -- one buffer "
            "carries one 'space'; split them into separate drawings or move one "
            "to another slot" % (sorted(spaces), slot))
    return spaces.pop() if spaces else "local"


# ---- base ----
class DrawItem:
    """Base for every drawable. Carries colour + space, composition via ``+``,
    and the chainable transform/restyle methods (each returns a NEW item, so a
    drawing you built once can be reused at several transforms)."""

    _SLOT         = None  # which draw buffer this flushes into
    _POINT_FIELDS = ()    # attributes holding (N,3) arrays

    # numpy must defer to __radd__ instead of broadcasting us into an array
    __array_ufunc__ = None

    def __init__(self, color=None, space="local", screen_space=False):
        self._color = color
        self._space = "screen" if screen_space else normalize_space(space)

    # ----- composition -----
    def __add__(self, other):
        if not isinstance(other, DrawItem):
            raise TypeError(
                "can only add draw items together, not %s -- '+' groups "
                "drawables, it is not arithmetic" % type(other).__name__)
        return DrawGroup(self._as_list() + other._as_list())

    def __radd__(self, other):
        if isinstance(other, int) and other == 0:      # sum([...])
            return DrawGroup(self._as_list())
        return self.__add__(other)

    def _as_list(self):
        return [self]

    # `*` and `-` are deliberately absent: see the module docstring.

    # ----- chainable transforms / restyle -----
    def _mutated(self):
        return _copy.copy(self)

    def colored(self, color):
        """A copy drawn in ``color`` (RGB or RGBA, uniform or per-element)."""
        out        = self._mutated()
        out._color = color
        return out

    def in_space(self, space):
        """A copy drawn in ``"local"`` (object space) or ``"screen"`` (pixels)."""
        out        = self._mutated()
        out._space = normalize_space(space)
        return out

    def translated(self, x, y=None, z=None):
        """A copy moved by a vector (``translated(v)`` or ``translated(x,y,z)``)."""
        off = np.asarray((x, y, z) if y is not None else x,
                         dtype=np.float64).ravel()
        if off.size != 3:
            raise ValueError("translated: expected 3 components")
        out = self._mutated()
        for f in self._POINT_FIELDS:
            setattr(out, f, getattr(self, f) + off)
        return out

    def scaled(self, factor):
        """A copy scaled about the origin. Subclasses also scale their radii /
        glyph sizes so a scaled drawing stays proportional."""
        s   = float(factor)
        out = self._mutated()
        for f in self._POINT_FIELDS:
            setattr(out, f, getattr(self, f) * s)
        return out

    # ----- flush -----
    def to_commands(self):
        """The ordered draw-command list, exactly as
        ``MPyLocator.evaluateDrawItems`` harvests it."""
        return to_commands(self)

    # ----- serialization -----
    # Draw items are plain objects over numpy arrays, so ``pickle`` already
    # round-trips them; JSON is the portable form (no numpy, no Python types)
    # for shipping a drawing between processes or storing it in a file.
    def to_json(self):
        """A plain-JSON dict describing this item (recursive for a group)."""
        return {"type": type(self).__name__,
                "state": {k: _json_value(v) for k, v in self.__dict__.items()}}

    @classmethod
    def from_json(cls, payload):
        """Rebuild a drawing from :meth:`to_json` output (dict, list, or text)."""
        return draw_from_json(payload)

    def __repr__(self):
        return "<%s slot=%s space=%s>" % (
            type(self).__name__, self._SLOT, self._space)


class DrawGroup(DrawItem):
    """What ``+`` returns: a flat list of drawables sharing one flush."""

    _SLOT = None

    def __init__(self, items=()):
        DrawItem.__init__(self)
        self._items = list(items)

    def _as_list(self):
        return list(self._items)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def _mutated(self):
        out        = _copy.copy(self)
        out._items = list(self._items)
        return out

    def colored(self, color):
        out        = self._mutated()
        out._items = [i.colored(color) for i in self._items]
        return out

    def in_space(self, space):
        out        = self._mutated()
        out._items = [i.in_space(space) for i in self._items]
        return out

    def translated(self, x, y=None, z=None):
        out        = self._mutated()
        out._items = [i.translated(x, y, z) for i in self._items]
        return out

    def scaled(self, factor):
        out        = self._mutated()
        out._items = [i.scaled(factor) for i in self._items]
        return out

    def __repr__(self):
        return "<DrawGroup %d items>" % len(self._items)


# ---- shapes -> Maya's native primitives ----
class DrawPrimitive(DrawItem):
    """A Maya built-in primitive shape, drawn through the ``shapes`` buffer.

    ``KIND`` is one of the five ``MUIDrawManager`` primitives the locator
    dispatches: sphere / box / cone / cylinder / circle. Scalars broadcast, so
    one primitive is one call -- ``DrawCircle(center=(0,0,0), radius=2)`` --
    while arrays still emit N of them in a single call."""

    _SLOT         = "shapes"
    _POINT_FIELDS = ("centers",)
    KIND          = None

    def __init__(self, center=(0.0, 0.0, 0.0), radius=1.0,
                 axis=(0.0, 1.0, 0.0), color=None, filled=False,
                 space="local", screen_space=False):
        DrawItem.__init__(self, color=color, space=space,
                          screen_space=screen_space)
        self.centers = _points(center, "center")
        n            = self.centers.shape[0]
        self.radii   = _scalars(radius, n, 1.0, "radius")
        self.axes    = _points(axis, "axis")
        if self.axes.shape[0] == 1 and n > 1:
            self.axes = np.repeat(self.axes, n, axis=0)
        if self.axes.shape[0] != n:
            raise ValueError("axis: expected 1 or %d vectors, got %d"
                             % (n, self.axes.shape[0]))
        self.filled = _flags(filled, n, False)

    def scaled(self, factor):
        out       = DrawItem.scaled(self, factor)
        out.radii = self.radii * float(factor)
        return out

    def as_mesh(self, segments=16):
        """This primitive tessellated into a :class:`DrawMesh` -- the escape
        hatch to the styling only a mesh can carry::

            DrawSphere(radius=2).as_mesh().outlined(WHITE)

        The geometry reproduces WHAT MAYA DRAWS: each kind uses the same
        center / radius / axis convention as the ``MUIDrawManager`` call the
        locator dispatches for it (``_api2/mpy_locator._draw_shapes``),
        including the three that are easy to get wrong:

        * a **cone**'s ``center`` is its BASE (``dm.cone`` takes a base), and
          its height is ``2 * radius``;
        * a **cylinder**'s ``center`` is its MIDPOINT (``dm.cylinder`` takes a
          centre), also with height ``2 * radius``;
        * a **box** is the ``up = axis`` / ``right = +X`` frame the draw passes,
          with ``radius`` as the HALF extent along each of the three -- so it
          circumscribes the sphere of the same radius. ``right`` is
          re-orthogonalized against ``up`` (and swapped for ``+Z`` when ``axis``
          is itself ``+/-X``).

        A **sphere** ignores ``axis`` because ``dm.sphere`` takes none.

        ``segments`` is the resolution of every swept ring; the default 16 is
        the ``subdivisionsAxis`` the cylinder draw hardcodes. Colour and draw
        space carry over -- a per-primitive colour becomes per-FACE. ``filled``
        does NOT: a mesh chooses its fill and outline through ``DrawMesh``'s own
        kwargs, which is the whole reason to convert.

        An ARRAY primitive becomes ONE mesh holding one shell per element, its
        indices rebased.
        """
        tess = _TESSELLATE[self.KIND]
        seg  = max(3, int(segments))
        pts, counts, indices, faces_per = [], [], [], []
        voff = 0
        for i in range(self.centers.shape[0]):
            p, c, ix = tess(self.centers[i], float(self.radii[i]),
                            self.axes[i], seg)
            pts.append(p)
            counts.append(c)
            indices.append(ix + voff)
            faces_per.append(c.size)
            voff += p.shape[0]
        if not pts:
            return DrawMesh(np.zeros((0, 3)), np.zeros((0,), dtype=np.int64),
                            np.zeros((0,), dtype=np.int64), space=self._space)
        color = self._color
        if color is not None:
            color = np.repeat(
                normalize_color(color, self.centers.shape[0]), faces_per, axis=0)
        return DrawMesh(np.concatenate(pts), np.concatenate(counts),
                        np.concatenate(indices), color=color, space=self._space)


class DrawSphere(DrawPrimitive):
    KIND = "sphere"


class DrawBox(DrawPrimitive):
    KIND = "box"


class DrawCone(DrawPrimitive):
    KIND = "cone"


class DrawCylinder(DrawPrimitive):
    KIND = "cylinder"


class DrawCircle(DrawPrimitive):
    """A circle. Defaults to facing +Z, the usual choice for a screen-facing
    halo; pass ``axis`` for anything else."""
    KIND = "circle"

    def __init__(self, center=(0.0, 0.0, 0.0), radius=1.0,
                 axis=(0.0, 0.0, 1.0), **kw):
        DrawPrimitive.__init__(self, center=center, radius=radius, axis=axis,
                               **kw)


# ---- primitive tessellation (DrawPrimitive.as_mesh) ----
#
# One tessellator per MUIDrawManager primitive the ``shapes`` buffer dispatches,
# each reproducing the geometry of the matching call in
# ``_api2/mpy_locator._draw_shapes`` -- see ``DrawPrimitive.as_mesh`` for the
# conventions. Each returns the OBJ-style triple a DrawMesh takes:
# ``(points (P,3), counts (F,), indices (I,))``, wound so every face of a closed
# solid points OUTWARD (a DrawMesh may be drawn with cull_backfaces).

def _axis_frame(axis):
    """Orthonormal ``(u, v, w)``: ``w`` along ``axis``, ``u``/``v`` spanning the
    plane a ring is swept in, with ``u x v == w`` so the sweep is
    counter-clockwise about ``w``. A zero-length axis falls back to the
    ``DrawPrimitive`` default ``+Y``."""
    w      = np.asarray(axis, dtype=np.float64).ravel()
    n      = float(np.linalg.norm(w))
    w      = np.array([0.0, 1.0, 0.0]) if n < 1e-12 else w / n
    helper = np.zeros(3)
    helper[int(np.argmin(np.abs(w)))] = 1.0     # least parallel world axis
    u = np.cross(helper, w)
    u /= np.linalg.norm(u)
    return u, np.cross(w, u), w


def _ring(center, u, v, radius, segments):
    """``(segments, 3)`` points on the circle of ``radius`` about ``center`` in
    the ``u``/``v`` plane."""
    t = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    return (np.asarray(center, dtype=np.float64)
            + radius * (np.cos(t)[:, None] * u + np.sin(t)[:, None] * v))


def _tess_circle(center, radius, axis, segments):
    """dm.circle(center, normal=axis, radius): one flat n-gon facing +axis."""
    u, v, _w = _axis_frame(axis)
    return (_ring(center, u, v, radius, segments),
            np.array([segments], dtype=np.int64),
            np.arange(segments, dtype=np.int64))


def _tess_cylinder(center, radius, axis, segments):
    """dm.cylinder(CENTER, axis, radius, height=2*radius, 16): centred."""
    u, v, w = _axis_frame(axis)
    c      = np.asarray(center, dtype=np.float64)
    bottom = _ring(c - radius * w, u, v, radius, segments)
    top    = _ring(c + radius * w, u, v, radius, segments)
    j      = np.arange(segments, dtype=np.int64)
    k      = (j + 1) % segments
    side   = np.stack([j, k, k + segments, j + segments], axis=1).ravel()
    return (np.concatenate([bottom, top]),
            np.concatenate([[segments, segments],
                            np.full(segments, 4)]).astype(np.int64),
            np.concatenate([j[::-1], j + segments, side]))


def _tess_cone(center, radius, axis, segments):
    """dm.cone(BASE, axis, radius, height=2*radius): base ring + apex."""
    u, v, w = _axis_frame(axis)
    c     = np.asarray(center, dtype=np.float64)
    base  = _ring(c, u, v, radius, segments)
    apex  = (c + 2.0 * radius * w).reshape(1, 3)
    j     = np.arange(segments, dtype=np.int64)
    k     = (j + 1) % segments
    sides = np.stack([j, k, np.full(segments, segments)], axis=1).ravel()
    return (np.concatenate([base, apex]),
            np.concatenate([[segments], np.full(segments, 3)]).astype(np.int64),
            np.concatenate([j[::-1], sides]))


def _tess_sphere(center, radius, _axis, segments):
    """dm.sphere(center, radius): a UV sphere. ``dm.sphere`` takes NO axis, so
    neither does this -- the poles are the frame's own ``+/-Y``."""
    u, v, w = _axis_frame((0.0, 1.0, 0.0))
    c      = np.asarray(center, dtype=np.float64)
    stacks = max(2, segments // 2)
    phi    = np.linspace(0.0, np.pi, stacks + 1)[1:-1]      # interior rings only
    rings = [_ring(c + radius * np.cos(p) * w, u, v,
                   radius * np.sin(p), segments) for p in phi]
    n_rings = len(rings)
    pts = np.concatenate([(c + radius * w).reshape(1, 3)] + rings
                         + [(c - radius * w).reshape(1, 3)])
    south = 1 + n_rings * segments
    j     = np.arange(segments, dtype=np.int64)
    k     = (j + 1) % segments
    idx = [np.stack([np.zeros(segments, dtype=np.int64), 1 + j, 1 + k],
                    axis=1).ravel()]
    counts = [np.full(segments, 3, dtype=np.int64)]
    for r in range(n_rings - 1):
        a, b = 1 + r * segments, 1 + (r + 1) * segments
        idx.append(np.stack([a + j, b + j, b + k, a + k], axis=1).ravel())
        counts.append(np.full(segments, 4, dtype=np.int64))
    last = 1 + (n_rings - 1) * segments
    idx.append(np.stack([np.full(segments, south), last + k, last + j],
                        axis=1).ravel())
    counts.append(np.full(segments, 3, dtype=np.int64))
    return pts, np.concatenate(counts), np.concatenate(idx)


def _tess_box(center, radius, axis, _segments):
    """dm.box(center, up=axis, right=+X, radius, radius, radius): ``radius`` is
    the HALF extent along each frame axis."""
    up    = np.asarray(axis, dtype=np.float64).ravel()
    n     = float(np.linalg.norm(up))
    up    = np.array([0.0, 1.0, 0.0]) if n < 1e-12 else up / n
    right = np.array([1.0, 0.0, 0.0])            # the side vector the draw passes
    right = right - float(np.dot(right, up)) * up
    if float(np.linalg.norm(right)) < 1e-9:      # axis IS +/-X -> pick another
        right = np.array([0.0, 0.0, 1.0])
        right = right - float(np.dot(right, up)) * up
    right /= np.linalg.norm(right)
    signs = np.array([[-1.0, -1.0, -1.0], [1.0, -1.0, -1.0],
                      [1.0, 1.0, -1.0], [-1.0, 1.0, -1.0],
                      [-1.0, -1.0, 1.0], [1.0, -1.0, 1.0],
                      [1.0, 1.0, 1.0], [-1.0, 1.0, 1.0]])
    basis = np.stack([right, up, np.cross(right, up)])   # right / up / front
    pts   = np.asarray(center, dtype=np.float64) + radius * (signs @ basis)
    faces = np.array([[0, 3, 2, 1], [4, 5, 6, 7],        # -front / +front
                      [0, 1, 5, 4], [3, 7, 6, 2],        # -up    / +up
                      [0, 4, 7, 3], [1, 2, 6, 5]],       # -right / +right
                     dtype=np.int64)
    return pts, np.full(6, 4, dtype=np.int64), faces.ravel()


_TESSELLATE = {
    "sphere":   _tess_sphere,
    "box":      _tess_box,
    "cone":     _tess_cone,
    "cylinder": _tess_cylinder,
    "circle":   _tess_circle,
}


def _flush_shapes(items):
    n_tot = sum(i.centers.shape[0] for i in items)
    kinds, filled = [], []
    for i in items:
        kinds.extend([i.KIND] * i.centers.shape[0])
        filled.extend(i.filled)
    return {
        "kinds":   kinds,
        "centers": np.concatenate([i.centers for i in items]).astype(np.float32),
        "radii":   np.concatenate([i.radii for i in items]).astype(np.float32),
        "axes":    np.concatenate([i.axes for i in items]).astype(np.float32),
        "colors": np.concatenate(
            [normalize_color(i._color, i.centers.shape[0]) for i in items]),
        "filled": filled,
        "space":  _merge_space(items, "shapes"),
    } if n_tot else None


# ---- lines ----
class DrawLines(DrawItem):
    """Disconnected segments -- one row of ``starts`` to one row of ``ends``.

    ``world_space=True`` means the endpoints are ALREADY in world space (pulled
    from other nodes' worldMatrices, say) and must land there regardless of this
    locator's own transform -- see ``DrawMesh`` for the same opt-in."""

    _SLOT         = "lines"
    _POINT_FIELDS = ("starts", "ends")

    def __init__(self, starts, ends, color=None, world_space=False,
                 space="local", screen_space=False):
        DrawItem.__init__(self, color=color, space=space,
                          screen_space=screen_space)
        self.starts = _points(starts, "starts")
        self.ends   = _points(ends, "ends")
        if self.starts.shape != self.ends.shape:
            raise ValueError("starts %s and ends %s must match"
                             % (self.starts.shape, self.ends.shape))
        self.world_space = bool(world_space)


class DrawCurve(DrawItem):
    """A POLYLINE through ``points`` -- the segment decomposition the renderer
    needs (``pts[:-1]`` / ``pts[1:]``) done for you, including trimming the
    colour array, which is easy to forget and silently rejects the whole buffer.

    ``closed=True`` adds the wrap-around segment.

    This takes POINTS, not a NURBS curve: a ``NurbsCurve``'s CVs are its control
    hull, not the curve, so drawing them would be quietly wrong. Sample the
    curve and pass the samples."""

    _SLOT         = "lines"
    _POINT_FIELDS = ("points",)

    def __init__(self, points, color=None, closed=False, world_space=False,
                 space="local", screen_space=False):
        DrawItem.__init__(self, color=color, space=space,
                          screen_space=screen_space)
        self.points      = _points(points, "points")
        self.closed      = bool(closed)
        self.world_space = bool(world_space)

    def _segments(self):
        p = self.points
        if p.shape[0] < 2:
            return p[:0], p[:0], 0
        if self.closed:
            return p, np.roll(p, -1, axis=0), p.shape[0]
        return p[:-1], p[1:], p.shape[0] - 1

    def _seg_colors(self):
        """Per-VERTEX colours have one row too many for a segment list; trim to
        match rather than letting the length check reject the buffer."""
        s, _, n = self._segments()
        col = self._color
        if col is not None:
            arr = np.asarray(col)
            if arr.ndim == 2 and arr.shape[0] == self.points.shape[0] and n:
                return normalize_color(arr[:n], n)
        return normalize_color(col, n)


def _flush_lines(items):
    starts, ends, colors = [], [], []
    for i in items:
        if isinstance(i, DrawCurve):
            s, e, n = i._segments()
            if not n:
                continue
            starts.append(s)
            ends.append(e)
            colors.append(i._seg_colors())
        else:
            n = i.starts.shape[0]
            if not n:
                continue
            starts.append(i.starts)
            ends.append(i.ends)
            colors.append(normalize_color(i._color, n))
    if not starts:
        return None
    return {
        "starts":      np.concatenate(starts).astype(np.float32),
        "ends":        np.concatenate(ends).astype(np.float32),
        "colors":      np.concatenate(colors),
        "world_space": bool(items[0].world_space),
        "space":       _merge_space(items, "lines"),
    }


# ---- points ----
class DrawPoints(DrawItem):
    """Screen-space dots. ``size`` is in PIXELS in both spaces."""

    _SLOT         = "points"
    _POINT_FIELDS = ("positions",)

    def __init__(self, positions, color=None, size=4.0, space="local",
                 screen_space=False):
        DrawItem.__init__(self, color=color, space=space,
                          screen_space=screen_space)
        self.positions = _points(positions, "positions")
        self.sizes     = _scalars(size, self.positions.shape[0], 4.0, "size")


def _flush_points(items):
    items = [i for i in items if i.positions.shape[0]]
    if not items:
        return None
    return {
        "positions": np.concatenate(
            [i.positions for i in items]).astype(np.float32),
        "colors": np.concatenate(
            [normalize_color(i._color, i.positions.shape[0]) for i in items]),
        "sizes": np.concatenate([i.sizes for i in items]).astype(np.float32),
        "space": _merge_space(items, "points"),
    }


# ---- text ----
class DrawText(DrawItem):
    """One or more labels.

    ``+`` GROUPS labels, it does not concatenate strings -- build the string in
    plain Python (``DrawText("frame " + str(f))``) so the operator keeps one
    meaning across every draw type."""

    _SLOT         = "text"
    _POINT_FIELDS = ("positions",)

    def __init__(self, text, position=(0.0, 0.0, 0.0), color=None, size=0.5,
                 space="local", screen_space=False):
        DrawItem.__init__(self, color=color, space=space,
                          screen_space=screen_space)
        self.positions = _points(position, "position")
        n              = self.positions.shape[0]
        self.strings   = _strings(text, n)
        if len(self.strings) != n:
            if n == 1 and len(self.strings) > 1:
                # one anchor, many labels is almost certainly a mistake
                raise ValueError(
                    "%d strings but only 1 position -- pass one position per "
                    "label" % len(self.strings))
            raise ValueError("%d strings vs %d positions"
                             % (len(self.strings), n))
        self.sizes = _scalars(size, n, 0.5, "size")

    def scaled(self, factor):
        out       = DrawItem.scaled(self, factor)
        out.sizes = self.sizes * float(factor)
        return out


def _flush_text(items):
    items = [i for i in items if i.positions.shape[0]]
    if not items:
        return None
    strings = []
    for i in items:
        strings.extend(i.strings)
    return {
        "positions": np.concatenate(
            [i.positions for i in items]).astype(np.float32),
        "strings": strings,
        "colors": np.concatenate(
            [normalize_color(i._color, i.positions.shape[0]) for i in items]),
        "sizes": np.concatenate([i.sizes for i in items]).astype(np.float32),
        "space": _merge_space(items, "text"),
    }


# ---- polygons ----
class DrawMesh(DrawItem):
    """A polygon patch, drawn through the ``polygons`` buffer.

    ACCEPTS a ``Mesh`` (duck-typed on ``.points`` / ``.counts`` / ``.indices``)
    or the three arrays directly:

        DrawMesh(mesh.from_tag("left_cheek"), color=rgba, outline=WHITE)
        DrawMesh(points, counts, indices, color=rgba)

    Merging several is the reason this type exists: the vertex-offset rebase
    (``indices + voff``) that every hand-written accumulator loop has to get
    right happens in the flush, once.

    **Fill colour** is exactly ONE of the four mutually-exclusive modes the
    polygons buffer defines, named after the key each emits so the mapping stays
    one-to-one with the low-level dict:

    =====================  =========================  ========================
    argument               emits                      meaning
    =====================  =========================  ========================
    ``color``              ``face_colors``            flat per face (broadcast
                                                      from one RGBA)
    ``uniform_color``      ``colors``                 one colour, drawn via the
                                                      renderer's single
                                                      ``setColor`` fast path
    ``vertex_colors``      ``vertex_colors``          smooth, per shared point
    ``face_vertex_colors`` ``face_vertex_colors``     face-varying, per corner
    =====================  =========================  ========================

    ``color`` and ``uniform_color`` look identical for a flat fill; they differ
    only in which key (and therefore which renderer path) is used. Passing more
    than one is an error rather than a silent precedence pick -- the renderer
    would warn and choose for you."""

    _SLOT         = "polygons"
    _POINT_FIELDS = ("points",)

    #: fill kwarg -> buffer key, in the renderer's own precedence order.
    _FILL_MODES = (
        ("face_vertex_colors", "face_vertex_colors"),
        ("vertex_colors", "vertex_colors"),
        ("color", "face_colors"),
        ("uniform_color", "colors"),
    )

    def __init__(self, points, counts=None, indices=None, color=None,
                 outline=None, outline_width=2.0, outline_boundary_only=True,
                 world_space=False, precise_hover=False, space="local",
                 screen_space=False, uniform_color=None, vertex_colors=None,
                 face_vertex_colors=None, cull_backfaces=False,
                 highlight_fill=None, highlight_wire=None):
        DrawItem.__init__(self, color=color, space=space,
                          screen_space=screen_space)
        if counts is None and indices is None:
            src = points
            try:
                points, counts, indices = src.points, src.counts, src.indices
            except AttributeError:
                raise TypeError(
                    "DrawMesh needs a Mesh-like object (.points/.counts/"
                    ".indices) or the three arrays explicitly")
        if points is None or counts is None or indices is None:
            raise ValueError("DrawMesh: points, counts and indices are required")
        self.points  = _points(points, "points")
        self.counts  = np.asarray(counts, dtype=np.int64).ravel()
        self.indices = np.asarray(indices, dtype=np.int64).ravel()
        if int(self.counts.sum()) != self.indices.size:
            raise ValueError(
                "counts sum to %d but there are %d indices"
                % (int(self.counts.sum()), self.indices.size))
        self.uniform_color      = uniform_color
        self.vertex_colors      = vertex_colors
        self.face_vertex_colors = face_vertex_colors
        given = [name for name, value in (
            ("color", color),
            ("uniform_color", uniform_color),
            ("vertex_colors", vertex_colors),
            ("face_vertex_colors", face_vertex_colors),
        ) if value is not None]
        if len(given) > 1:
            raise ValueError(
                "DrawMesh: pass ONE fill mode, got %s -- they are mutually "
                "exclusive (the renderer would warn and pick by precedence)"
                % (sorted(given),))
        self.outline               = outline
        self.outline_width         = float(outline_width)
        self.outline_boundary_only = bool(outline_boundary_only)
        self.world_space           = bool(world_space)
        self.precise_hover         = bool(precise_hover)
        self.cull_backfaces        = bool(cull_backfaces)
        self.highlight_fill        = highlight_fill
        self.highlight_wire        = highlight_wire

    def _fill_mode(self):
        """``(kwarg, buffer_key)`` for the fill this item carries, or None."""
        for arg, key in self._FILL_MODES:
            if getattr(self, arg if arg != "color" else "_color", None) is not None:
                return arg, key
        return None

    def outlined(self, color, width=2.0, boundary_only=True):
        """A copy with a wireframe outline."""
        out                       = self._mutated()
        out.outline               = color
        out.outline_width         = float(width)
        out.outline_boundary_only = bool(boundary_only)
        return out


def _flush_polygons(items):
    items = [i for i in items if i.counts.size]
    if not items:
        return None
    pts, idx, cnt = [], [], []
    voff = 0
    for i in items:
        pts.append(i.points)
        idx.append(i.indices + voff)          # the rebase, done once, here
        cnt.append(i.counts)
        voff += i.points.shape[0]
    head = items[0]
    buf = {
        "points":      np.concatenate(pts).astype(np.float32),
        "indices":     np.concatenate(idx).astype(np.int32),
        "counts":      np.concatenate(cnt).astype(np.int32),
        "world_space": bool(head.world_space),
        "space":       _merge_space(items, "polygons"),
    }

    # Fill colour. Every merged item that HAS a fill must agree on the mode --
    # concatenating a per-face array onto a per-vertex one would silently
    # mis-colour the result. The per-mode element count differs (faces / points
    # / corners), which is why each branch normalizes separately.
    #
    # An item with NO fill is compatible with anything: it takes the default
    # (flat white) in whichever mode its neighbours chose. Treating "no fill" as
    # its own mode would make the long-legal `DrawMesh(a) + DrawMesh(b, color=r)`
    # start raising.
    modes = {m[1] for m in (i._fill_mode() for i in items) if m}
    if len(modes) > 1:
        raise ValueError(
            "cannot merge DrawMesh items with different fill modes %s -- give "
            "them the same one, or keep them in separate drawings"
            % (sorted(modes),))
    # Nothing coloured at all -> keep the historical default (a flat white
    # face_colors), NOT "no fill": an uncoloured DrawMesh has always drawn
    # filled, and silently turning it into a wireframe-only patch would be a
    # regression for anything that relies on the default.
    key = modes.pop() if modes else "face_colors"
    if key == "face_colors":
        buf[key] = np.concatenate(
            [normalize_color(i._color, int(i.counts.size)) for i in items])
    elif key == "vertex_colors":
        buf[key] = np.concatenate(
            [normalize_color(i.vertex_colors, int(i.points.shape[0]))
             for i in items])
    elif key == "face_vertex_colors":
        buf[key] = np.concatenate(
            [normalize_color(i.face_vertex_colors, int(i.indices.size))
             for i in items])
    elif key == "colors":
        # The single-setColor fast path: ONE colour for the whole buffer, so
        # only one can survive a merge. Take the first item that actually
        # carries one -- the head may be an uncoloured patch.
        buf[key] = next(i.uniform_color for i in items
                        if i.uniform_color is not None)

    if head.outline is not None:
        buf["wireframe"]               = head.outline
        buf["wireframe_width"]         = head.outline_width
        buf["wireframe_boundary_only"] = head.outline_boundary_only
    if head.cull_backfaces:
        buf["cull_backfaces"] = True
    # Opt into ray-vs-drawn-triangle hover for THIS patch. Per-item rather than
    # node-wide: a gizmo can hover-test its clickable surface while its
    # decoration stays out of the pick.
    if head.precise_hover:
        buf["precise_hover"] = True
    # None means "inherit the node-wide auto_highlight", which is the renderer's
    # own default -- so only an explicit True/False is written through.
    if head.highlight_fill is not None:
        buf["highlight_fill"] = bool(head.highlight_fill)
    if head.highlight_wire is not None:
        buf["highlight_wire"] = bool(head.highlight_wire)
    return buf


# ---- flush -> ordered draw commands ----
_FLUSH = {
    "lines":    _flush_lines,
    "points":   _flush_points,
    "polygons": _flush_polygons,
    "shapes":   _flush_shapes,
    "text":     _flush_text,
}


def _flatten(value, out=None):
    """Every ``DrawItem`` inside ``value``, in AUTHORING order.

    Accepts a single item, a ``DrawGroup`` (what ``+`` builds), ``None``, or any
    nesting of lists / tuples / iterators of those. Nesting is FLATTENED rather
    than rejected: ``[a, [b, c], d]`` is the same drawing as ``a + b + c + d``,
    so a drawing accumulated by appending to lists needs no ``sum()`` at the
    end. Only a non-drawable leaf is an error."""
    out = [] if out is None else out
    if value is None:
        return out
    if isinstance(value, DrawGroup):          # before DrawItem: a group is one
        for it in value._items:
            _flatten(it, out)
        return out
    if isinstance(value, DrawItem):
        out.append(value)
        return out
    # str/bytes iterate into characters and ndarray into rows -- neither is a
    # nested drawing, so they get the plain "not a drawable" error below.
    if not isinstance(value, (str, bytes, dict, np.ndarray)):
        try:
            members = iter(value)
        except TypeError:
            members = None
        if members is not None:
            for it in members:
                _flatten(it, out)
            return out
    raise TypeError(
        "self.draw takes draw items -- DrawCircle(...) + DrawText(...), or a "
        "list of them -- not %s" % type(value).__name__)


def to_commands(value):
    """Flatten a drawing into the ORDERED draw-command list.

    ``[{"slot": "lines"|"points"|"polygons"|"shapes"|"text", "buffer": {...}},
    ...]``: one record per authored item, in the order it was written. The
    renderer replays the list front-to-back, so authoring order IS draw order
    and a later item lands on top of an earlier one.

    Items are deliberately NOT merged per type. Bucketing by slot would
    silently reorder the drawing (all text always last, whatever you wrote),
    and it buys nothing: Maya's draw manager takes one ``setColor`` + one
    ``line`` / ``point`` / ``text`` call per element either way, so a merged
    buffer costs exactly the same calls as separate ones."""
    cmds = []
    for item in _flatten(value):
        buf = _FLUSH[item._SLOT]([item])
        if buf is None:                       # an empty item draws nothing
            continue
        cmds.append({"slot": item._SLOT, "buffer": buf})
    return cmds


# ---- JSON codec ----
# Generic on purpose: a draw item's state IS its ``__dict__``, so the codec
# walks values rather than enumerating fields per class. Adding a field (or a
# whole new Draw type) needs no codec change, and nothing can silently drop.
# numpy arrays are tagged so dtype/shape survive the round trip.

def _json_value(v):
    """One state value as JSON-safe data."""
    if isinstance(v, np.ndarray):
        return {"__ndarray__": v.tolist(), "dtype": str(v.dtype)}
    if isinstance(v, DrawItem):
        return v.to_json()
    if isinstance(v, (list, tuple)):
        return [_json_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _json_value(x) for k, x in v.items()}
    if isinstance(v, (np.floating, np.integer, np.bool_)):
        return v.item()
    return v


def _json_revive(v):
    """Inverse of :func:`_json_value`."""
    if isinstance(v, dict):
        if "__ndarray__" in v:
            return np.asarray(v["__ndarray__"], dtype=np.dtype(v["dtype"]))
        if "type" in v and "state" in v:
            return draw_from_json(v)
        return {k: _json_revive(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_json_revive(x) for x in v]
    return v


def draw_from_json(payload):
    """Rebuild a drawing from :meth:`DrawItem.to_json` output.

    Accepts a dict, a JSON string, or a list of either (a list comes back as a
    list, which ``self.draw`` accepts directly)."""
    if isinstance(payload, (str, bytes)):
        payload = _json.loads(payload)
    if isinstance(payload, list):
        return [draw_from_json(p) for p in payload]
    kind = payload.get("type")
    cls  = globals().get(kind)
    if not (isinstance(cls, type) and issubclass(cls, DrawItem)):
        raise ValueError("draw_from_json: unknown draw type %r" % (kind,))
    # Bypass __init__: the state dict is already coerced/validated (it came out
    # of a live item), and several constructors take a DIFFERENT signature than
    # the fields they produce (DrawCurve stores segments, DrawText normalizes).
    item = cls.__new__(cls)
    item.__dict__.update(
        {k: _json_revive(v) for k, v in (payload.get("state") or {}).items()})
    return item
