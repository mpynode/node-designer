"""Object surface over an mPyBlendShape's targets -- :class:`Morph` (one target)
and :class:`MorphStack` (the aliased ``weight[]`` stack).

Inspired by the ``MorphData`` / ``MorphList`` pair in the ART math_utils tree,
and shaped like the geometry wrappers in :mod:`mpynode._api2.geometry`: a lazy
numpy read surface over data the node already holds, with no plugs of its own.

Two audiences, two surfaces
---------------------------
**Setup / authoring / @maya_command code** -- no transpiler involved, so the FULL
surface works: name lookup, keyword search, iteration, the operator suite,
:meth:`Morph.prune`. Build correctives by arithmetic::

    bs = MPyBlendShape("face_bs")
    corrective = bs.morphs["browUp"] + bs.morphs["mouthOpen"]
    bs.add_target_from_offsets(sculpt - corrective, name="browUp_mouthOpen")

A stack is a read VIEW and holds no node, so it cannot add anything -- the
target goes on through the node, which is what owns the plugs. A :class:`Morph`
is accepted directly, so the arithmetic above lands on the node unchanged.

**A node's Compute** -- a NARROW surface, because everything there must also
lower to C++. Exactly these forms are recognised and rewritten into blessed
method calls by ``nd_lower._rewrite_morph_reads``::

    self.morphs.weights            -> self.weight            (raw channels)
    self.morphs.resolved           -> self.morph_weights()   (hats + combos)
    self.morphs.deltas(base, w)    -> self.morph_deltas(base, w)
    self.morphs.apply(base, env)   -> self.morph_apply(base, env)
    self.morphs[<int>].weight      -> self.weight[<int>]
    self.morphs["browUp"].weight   -> self.morph_weight_at(<slot>)
    len(self.morphs)               -> self.weight.shape[0]

Anything else honest-rejects at compile time rather than lowering to something
subtly different from what the interpreted node did.

Bind the points to a local first::

    mesh = self.outputGeometry[0]
    base = mesh.getPoints()
    mesh.setPoints(self.morphs.apply(base, self.envelope))

``mesh.setPoints(self.morphs.apply(mesh.getPoints(), ...))`` does NOT compile --
``nd_lower._rewrite_deform_io`` rewrites the getPoints/setPoints idiom
line-locally and needs ``getPoints()`` as its own statement. That is a
pre-existing deformer constraint, nothing to do with morphs (plain
``mesh.setPoints(mesh.getPoints() * 2)`` rejects the same way).

Name keys in a Compute -- resolved by SLOT, not by alias
--------------------------------------------------------
``self.morphs["browUp"].weight`` works in a Compute, but not the way it looks.
Alias lookup is a side-channel DG query and those return EMPTY on the
Evaluation-Manager worker thread ``deform()`` runs on, so no name can be resolved
live on either path.

Instead the name is folded at COMPILE time. ``nd_lower.morph_slot_names`` reads
the compute source and assigns each distinct name an ordinal SLOT; the compiler
bakes only that integer, and ``MPyBlendShape.rebuild()`` writes the per-rig
``weight[]`` index into ``shapeSlot[slot]``. So the generated C++ holds pure
integer indirection, no target name reaches it, and **one bundle still serves any
rig**. This class resolves interpreted through the SAME two things -- the same
ordering function and the same ``shapeSlot`` table -- so both halves agree by
construction rather than by two implementations happening to match.

Consequences worth knowing:

* The key must be a compile-time constant: a literal, a variable assigned ONCE
  at the top of the Compute from a string literal, an element of a top-level
  constant tuple, or the loop variable of ``for n in NAMES:`` over one. Anything
  else honest-rejects, because a string local is a real runtime value that can
  differ per branch and folding it would silently drive the wrong shape.
* A name this rig has no target for reads as a target AT REST (weight 0.0)
  rather than raising -- that is what lets one bundle run on a rig missing the
  shape. Authoring-side lookup still raises ``KeyError`` on an unknown name,
  where a typo is worth catching.
* ``rebuild()`` must have run since the compute last changed, or ``shapeSlot``
  describes the previous set of names. ``alias_fingerprint`` folds the compute's
  slot names in for exactly this reason, and ``tables_stale()`` checks it.

Everything else name-shaped -- :meth:`MorphStack.names`, :meth:`find`,
:meth:`index_of` -- is authoring-only and needs a stack built from a node
(:meth:`MorphStack.from_node`), which runs on the main thread where aliases do
resolve.
"""
from __future__ import annotations

import fnmatch

import numpy as np


def _as_offsets(arr):
    """Coerce to an ``(K, 3)`` float64 offset array."""
    if arr is None:
        return np.zeros((0, 3), dtype=np.float64)
    out = np.asarray(arr, dtype=np.float64)
    if out.size == 0:
        return np.zeros((0, 3), dtype=np.float64)
    if out.ndim == 1:
        out = out.reshape(-1, 3)
    return out


def _as_indices(arr, n):
    """Coerce to a ``(K,)`` int64 index array, defaulting to ``arange(n)``."""
    if arr is None:
        return np.arange(n, dtype=np.int64)
    return np.asarray(arr, dtype=np.int64).reshape(-1)


# Compute source -> ordered slot names. A deform re-enters here every frame a
# name key is used, so parsing each time is not viable; the source IS the cache
# key, so an edit invalidates the entry for free.
_SLOT_NAME_CACHE = {}
_SLOT_CACHE_MAX  = 64


def _slot_names_for(source):
    """The ordered name keys a compute mentions, via the compiler's SSOT.

    Deferred import: ``_api2`` does not otherwise depend on the native compiler,
    and this is only reached when a Compute actually indexes by name. A build
    without the compiler present simply has no name lookup, which surfaces as the
    normal KeyError rather than an ImportError mid-deform.
    """
    if not source:
        return ()
    hit = _SLOT_NAME_CACHE.get(source)
    if hit is not None:
        return hit
    try:
        from mpynode.native.compiler.nd_lower import morph_slot_names
        out = tuple(morph_slot_names(source))
    except Exception:
        out = ()
    if len(_SLOT_NAME_CACHE) >= _SLOT_CACHE_MAX:
        _SLOT_NAME_CACHE.clear()
    _SLOT_NAME_CACHE[source] = out
    return out


def _compute_source_of(proxy):
    """The node's ``_computeSource`` string, read off the proxy's MObject.

    A plain plug read -- the same one ``compute.py`` already performs on this
    thread to fetch the expression it is running -- NOT an alias side-channel
    query, so it is safe where ``aliasAttr`` is not.

    Both APIs, because ``_psp_mobject`` follows the NODE: mPyBlendShape is
    registered through the api1 plug-in and hands over a ``maya.OpenMaya``
    MObject, while the api2 node types hand over an ``maya.api.OpenMaya`` one.
    Each MFnDependencyNode rejects the other's MObject outright, so trying one
    and falling back is the whole check.
    """
    try:
        mobj = object.__getattribute__(proxy, "_psp_mobject")
    except AttributeError:
        return ""
    if mobj is None:
        return ""
    for mod in ("maya.OpenMaya", "maya.api.OpenMaya"):
        try:
            om = __import__(mod, fromlist=["MFnDependencyNode"])
            return om.MFnDependencyNode(mobj).findPlug(
                "_computeSource", True).asString() or ""
        except Exception:
            continue
    return ""


class Morph:
    """One blend-shape target: a SPARSE set of per-vertex offsets.

    ``indices`` are vertex ids and ``offsets`` the matching ``(K, 3)`` deltas, so
    a target that moves four vertices of a 10k mesh stores four rows. ``weight``
    and ``index`` are carried along when the Morph came out of a
    :class:`MorphStack`; a standalone Morph you construct has ``index = -1``.

    The operator suite (``+ - * /``) is for AUTHORING, not for a Compute -- see
    the module docstring. Adding two Morphs takes the sparse index UNION, so
    ``browUp + mouthOpen`` is the combined offset field even when the two touch
    different vertices.
    """

    __slots__ = ("name", "indices", "offsets", "weight", "index")

    def __init__(self, name="", offsets=None, indices=None, weight=0.0,
                 index=-1):
        self.name    = name
        self.offsets = _as_offsets(offsets)
        self.indices = _as_indices(indices, self.offsets.shape[0])
        self.weight  = float(weight)
        self.index   = int(index)

    # ----- read surface -----
    @property
    def size(self) -> int:
        """Number of vertices this target actually moves."""
        return int(self.indices.size)

    @property
    def magnitudes(self):
        """``(K,)`` per-vertex offset lengths."""
        if self.offsets.size == 0:
            return np.zeros(0, dtype=np.float64)
        return np.einsum("...i,...i", self.offsets, self.offsets) ** 0.5

    @property
    def max_magnitude(self) -> float:
        m = self.magnitudes
        return float(m.max()) if m.size else 0.0

    def is_zero(self, tolerance=1e-9) -> bool:
        """True when every offset is within ``tolerance`` of zero."""
        return bool(self.offsets.size == 0
                    or np.all(np.abs(self.offsets) <= tolerance))

    def dense(self, n_verts):
        """An ``(n_verts, 3)`` DENSE offset field, zero where this target does
        not move. Handy for arithmetic against a full point array."""
        out = np.zeros((int(n_verts), 3), dtype=np.float64)
        if self.indices.size:
            keep                    = (self.indices >= 0) & (self.indices < int(n_verts))
            out[self.indices[keep]] = self.offsets[keep]
        return out

    def prune(self, tolerance=1e-7) -> "Morph":
        """A copy with near-zero offsets dropped (shrinks the baked tables)."""
        if self.offsets.size == 0:
            return self.copy()
        keep = (np.abs(self.offsets) > tolerance).any(axis=1)
        return Morph(self.name, self.offsets[keep], self.indices[keep],
                     self.weight, self.index)

    def sort(self) -> "Morph":
        """A copy with entries in ascending vertex-id order."""
        order = np.argsort(self.indices)
        return Morph(self.name, self.offsets[order], self.indices[order],
                     self.weight, self.index)

    def copy(self) -> "Morph":
        return Morph(self.name, np.array(self.offsets),
                     np.array(self.indices), self.weight, self.index)

    # ----- operators (AUTHORING) -----
    @staticmethod
    def _merge(a, b, sign):
        """Sparse index-set union of two Morphs; ``b`` contributes ``sign * b``.

        Sized by the number of DISTINCT touched vertices, not by the highest
        vertex id -- a target moving vertex 90000 of a 100k mesh allocates 1 row,
        not 90001.
        """
        merged = np.union1d(a.indices, b.indices).astype(np.int64)
        out    = np.zeros((merged.size, 3), dtype=np.float64)
        if a.indices.size:
            out[np.searchsorted(merged, a.indices)] += a.offsets
        if b.indices.size:
            out[np.searchsorted(merged, b.indices)] += sign * b.offsets
        return merged, out

    def _combined_name(self, other, joiner):
        parts = [p for p in (self.name, getattr(other, "name", "")) if p]
        return joiner.join(dict.fromkeys(parts))

    def __add__(self, other):
        if isinstance(other, Morph):
            idx, off = self._merge(self, other, 1.0)
            return Morph(self._combined_name(other, "_"), off, idx)
        return Morph(self.name, self.offsets + other, self.indices,
                     self.weight, self.index)

    __radd__ = __add__

    def __sub__(self, other):
        if isinstance(other, Morph):
            idx, off = self._merge(self, other, -1.0)
            return Morph(self._combined_name(other, "_"), off, idx)
        return Morph(self.name, self.offsets - other, self.indices,
                     self.weight, self.index)

    def __mul__(self, other):
        if isinstance(other, Morph):
            idx, off = self._merge(self, other, 0.0)
            # element-wise product over the union (absent side contributes 0)
            prod   = np.zeros_like(off)
            common = np.intersect1d(self.indices, other.indices)
            if common.size:
                prod[np.searchsorted(idx, common)] = (
                    self.offsets[np.searchsorted(self.indices, common)]
                    * other.offsets[np.searchsorted(other.indices, common)])
            return Morph(self._combined_name(other, "_"), prod, idx)
        return Morph(self.name, self.offsets * other, self.indices,
                     self.weight, self.index)

    __rmul__ = __mul__

    def __truediv__(self, other):
        return Morph(self.name, self.offsets / other, self.indices,
                     self.weight, self.index)

    def __neg__(self):
        return Morph(self.name, -self.offsets, self.indices, self.weight,
                     self.index)

    def __len__(self) -> int:
        return self.size

    def __repr__(self) -> str:
        return "<Morph %r idx=%d verts=%d weight=%.3f>" % (
            self.name, self.index, self.size, self.weight)


class MorphStack:
    """The whole target stack -- list-like AND dict-like.

    Index it by position (``stack[0]``) or, in authoring code, by target name
    (``stack["browUp"]``). Iterate it, ``len()`` it, search it with
    :meth:`find`. Every element is a :class:`Morph`.

    Built from the node's baked CSR tables, so it is a VIEW: no plugs of its own,
    nothing to keep in sync, and constructing one costs a few array slices.
    """

    def __init__(self, weight=None, offset=None, components=None, deltas=None,
                 inter_base=None, inter_knot=None, combo_offset=None,
                 combo_driver=None, names=None, slot_index=None,
                 slot_source=None, proxy=None):
        self.weights = (np.zeros(0, dtype=np.float64) if weight is None
                        else np.asarray(weight, dtype=np.float64).reshape(-1))
        self._ofs = (np.zeros(0, dtype=np.int64) if offset is None
                     else np.asarray(offset, dtype=np.int64).reshape(-1))
        self._comp = (np.zeros(0, dtype=np.int64) if components is None
                      else np.asarray(components, dtype=np.int64).reshape(-1))
        self._dlt = (np.zeros(0, dtype=np.float64) if deltas is None
                     else np.asarray(deltas, dtype=np.float64).reshape(-1))
        self._ibase = (np.zeros(0, dtype=np.int64) if inter_base is None
                       else np.asarray(inter_base, dtype=np.int64).reshape(-1))
        self._iknot = (np.zeros(0, dtype=np.float64) if inter_knot is None
                       else np.asarray(inter_knot, dtype=np.float64).reshape(-1))
        self._cofs = (np.zeros(0, dtype=np.int64) if combo_offset is None
                      else np.asarray(combo_offset, dtype=np.int64).reshape(-1))
        self._cdrv = (np.zeros(0, dtype=np.int64) if combo_driver is None
                      else np.asarray(combo_driver, dtype=np.int64).reshape(-1))
        self._names = list(names) if names else []
        # Name resolution INSIDE a compute, where aliases are unavailable. The
        # compiler turns each name the source mentions into an ordinal slot;
        # shapeSlot maps that ordinal to this rig's weight[] index. Lazy, so a
        # stack never indexed by name costs nothing.
        self._slot_idx = (np.zeros(0, dtype=np.int64) if slot_index is None
                          else np.asarray(slot_index,
                                          dtype=np.int64).reshape(-1))
        self._slot_source = slot_source
        self._slot_names  = None
        # The compute's ``self``, when this stack was built from one. Everything
        # above is a detached SNAPSHOT of the baked tables; the deltas surface is
        # the one place that is not enough, because a CONNECTED target is read
        # live off its mesh and only the proxy can reach the datablock to do it.
        # None on the authoring path (``from_scene``), which has no evaluation to
        # read from and stays baked-only.
        self._proxy = proxy

    # ----- constructors -----
    @classmethod
    def from_node(cls, node):
        """Build from a live node NAME -- the authoring path (main thread, so
        aliases resolve and name lookup works)."""
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        bs = node if isinstance(node, MPyBlendShape) else MPyBlendShape(node)

        def _multi(attr, cast):
            if not bs._has_attr(attr):
                return []
            return bs._read_multi(attr, cast)

        return cls(weight=_multi("weight", float),
                   offset       = _multi("targetOffset", int),
                   components   = _multi("targetComponents", int),
                   deltas       = _multi("targetDeltas", float),
                   inter_base   = _multi("interBase", int),
                   inter_knot   = _multi("interKnot", float),
                   combo_offset = _multi("comboOffset", int),
                   combo_driver = _multi("comboDriver", int),
                   names=bs.target_names)

    @classmethod
    def from_proxy(cls, proxy):
        """Build from a compute's ``self``.

        No ALIASES here -- those return empty on the Evaluation-Manager worker
        thread (see the module docstring). Name lookup still works, but through
        the compile-time slot table rather than the alias table, so interpreted
        and compiled resolve a name the same way.
        """
        def _t(name, dtype):
            try:
                v = getattr(proxy, name)
            except AttributeError:
                return None
            return None if v is None else np.asarray(v, dtype=dtype).reshape(-1)

        return cls(weight=_t("weight", np.float64),
                   offset       = _t("targetOffset", np.int64),
                   components   = _t("targetComponents", np.int64),
                   deltas       = _t("targetDeltas", np.float64),
                   inter_base   = _t("interBase", np.int64),
                   inter_knot   = _t("interKnot", np.float64),
                   combo_offset = _t("comboOffset", np.int64),
                   combo_driver = _t("comboDriver", np.int64),
                   names        = None,
                   slot_index   = _t("shapeSlot", np.int64),
                   slot_source  = lambda: _compute_source_of(proxy),
                   proxy=proxy)

    # ----- list surface -----
    def __len__(self) -> int:
        return int(self.weights.shape[0])

    def __iter__(self):
        for i in range(len(self)):
            yield self._morph_at(i)

    def __contains__(self, key) -> bool:
        if isinstance(key, str):
            return key in self._names or key in self._slots()
        return 0 <= int(key) < len(self)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._by_name(key)
        if isinstance(key, slice):
            return [self._morph_at(i) for i in range(*key.indices(len(self)))]
        i = int(key)
        if i < 0:
            i += len(self)
        if not (0 <= i < len(self)):
            raise IndexError("morph index %r out of range (%d targets)"
                             % (key, len(self)))
        return self._morph_at(i)

    def _slots(self):
        """This node's ordered slot names, resolved once per stack."""
        if self._slot_names is None:
            src = ""
            if self._slot_source is not None:
                try:
                    src = self._slot_source() or ""
                except Exception:
                    src = ""
            self._slot_names = list(_slot_names_for(src))
        return self._slot_names

    def _by_name(self, key):
        # Authoring stack: aliases resolved, so go straight at them.
        if self._names:
            try:
                return self._morph_at(self._names.index(key))
            except ValueError:
                raise KeyError("no target named %r (have: %s)"
                               % (key, ", ".join(n for n in self._names if n)))

        # Compute stack: through the compile-time slot table, the same route
        # the compiled node takes, so both sides resolve a name identically.
        slots = self._slots()
        if key in slots:
            k = slots.index(key)
            j = int(self._slot_idx[k]) if k < self._slot_idx.size else -1
            if 0 <= j < len(self):
                return self._morph_at(j)
            # Mapped to nothing on THIS rig. Reads as a target at rest,
            # matching the compiled weight_at_slot -- that is what lets one
            # bundle serve a rig without this shape.
            return Morph(name=key, weight=0.0, index=-1)

        raise KeyError(
            "self.morphs[%r] cannot be resolved here. Inside a Compute a name "
            "key is folded to a slot AT COMPILE TIME, so it must be a literal, "
            "a variable assigned once at the top from a string literal, or an "
            "element of a constant tuple -- and the tables must have been built "
            "since (MPyBlendShape.rebuild()). Names this Compute declares: %s"
            % (key, ", ".join(slots) if slots else "(none)"))

    def _morph_at(self, i):
        """Slice target ``i`` out of the flat CSR tables.

        Clamped against BOTH flat tables. Clamping to ``_comp`` alone is not
        enough: the delta slice is ``3 * lo .. 3 * hi``, so a ``_dlt`` shorter
        than that yields a partial slice whose length is not a multiple of 3 and
        ``reshape(-1, 3)`` raises. That is the stale-table case the kernels
        already guard with ``d + 2 < nd``, and this is the same rule -- degrade
        to "this target moves nothing", never explode.
        """
        lo = int(self._ofs[i]) if i < self._ofs.size else 0
        hi = int(self._ofs[i + 1]) if i + 1 < self._ofs.size else lo
        lo = max(lo, 0)
        hi = min(hi, int(self._comp.size), int(self._dlt.size) // 3)
        if hi < lo:
            hi = lo
        idx  = self._comp[lo:hi]
        off  = self._dlt[3 * lo:3 * hi].reshape(-1, 3) if hi > lo else None
        name = self._names[i] if i < len(self._names) else ""
        w    = float(self.weights[i]) if i < self.weights.size else 0.0
        return Morph(name, off, idx, w, i)

    # ----- dict / search surface -----
    @property
    def names(self) -> list:
        """Target names in ``weight[]`` order. EMPTY inside a Compute."""
        return list(self._names)

    def get(self, key, default=None):
        """``stack[key]`` or ``default`` -- never raises."""
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def find(self, pattern) -> list:
        """Every Morph whose name matches ``pattern``.

        Glob when the pattern has wildcards (``find("brow*")``), plain
        case-insensitive substring otherwise (``find("brow")``). This is the
        keyword search -- ``stack.find("_")`` finds every combo,
        ``stack.find("browUp*")`` a target and all its in-betweens.
        """
        pat    = str(pattern)
        globby = any(c in pat for c in "*?[")
        out    = []
        for i, nm in enumerate(self._names):
            if not nm:
                continue
            hit = (fnmatch.fnmatch(nm, pat) if globby
                   else pat.lower() in nm.lower())
            if hit:
                out.append(self._morph_at(i))
        return out

    def index_of(self, name) -> int:
        """Logical ``weight[]`` index of ``name``, or -1."""
        try:
            return self._names.index(name)
        except ValueError:
            return -1

    # ----- math surface (mirrors the blessed methods exactly) -----
    @property
    def resolved(self):
        """``(T,)`` effective weights: in-between hats and combo products ADDED
        on top of each target's own channel. Same kernel the compiled node
        runs."""
        from mpynode._common.methods import morph_blend
        return morph_blend.resolve_weights(
            self.weights, self._ibase, self._iknot, self._cofs, self._cdrv)

    def deltas(self, base, w=None):
        """``(N, 3)`` accumulated OFFSET field for weight vector ``w``
        (defaults to :attr:`resolved`).

        Inside a compute this DELEGATES to the blessed ``morph_deltas`` adapter
        rather than calling the kernel itself. It has to: a connected target is
        read live off its mesh, and re-implementing the baked half here would
        make ``self.morphs.deltas(...)`` and ``self.morph_deltas(...)`` two
        different deforms -- which is precisely what the compiled desugar
        (``self.morphs.deltas -> self.morph_deltas``) says they are not.
        """
        from mpynode._common.methods import morph_blend
        base = np.asarray(base, dtype=np.float64)
        wv   = self.resolved if w is None else np.asarray(w, dtype=np.float64)
        if self._proxy is not None:
            from mpynode._common.methods import morph_methods
            return morph_methods._deltas(self._proxy, base, wv.reshape(-1))
        return morph_blend.accumulate_deltas(
            base, wv.reshape(-1), self._ofs, self._comp, self._dlt)

    def apply(self, base, envelope=1.0):
        """``(N, 3)`` deformed points: ``base + envelope * deltas``."""
        from mpynode._common.methods import morph_blend
        base = np.asarray(base, dtype=np.float64)
        if self._proxy is not None:
            return base + float(envelope) * self.deltas(base, self.resolved)
        return morph_blend.apply_morphs(
            base, float(envelope),
            self.weights, self._ibase, self._iknot, self._cofs, self._cdrv,
            self._ofs, self._comp, self._dlt)

    def __repr__(self) -> str:
        named = [n for n in self._names if n]
        return "<MorphStack %d target(s)%s>" % (
            len(self), (": " + ", ".join(named[:6])
                        + (" ..." if len(named) > 6 else "")) if named else "")
