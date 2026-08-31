"""Plug_proxy — a Pythonic plug-tree wrapper for any Maya dependency node.

E1 + E2 read-only proof of the "self IS the node's plug tree" design.

Usage from an expression / init source::

 # `node` is auto-injected by the bridge — it's a PlugProxy bound
 # to the executing node (and, at compute time, the current
 # MDataBlock).

 # Numeric scalar:
 e = node.envelope # float

 # Compound:
 t = node.translate # nested PlugProxy
 tx = node.translate.translateX # float

 # Multi (array):
 g0 = node.input[0] # nested PlugProxy for input[0]
 grp_id = node.input[0].groupId # int

 # Geometry (E2): returns an MFn wrapper of the connected source
 mesh_fn = node.input[0].inputGeometry # MFnMesh
 pts = mesh_fn.getPoints() # MPointArray
 n_verts = mesh_fn.numVertices()

 # Matrix:
 wm = node.worldMatrix[0] # MMatrix

DESIGN NOTES
------------
* Read-only in E1/E2. ``__setattr__`` raises NotImplementedError
 (writes ship in E3).
* Returns native Maya API types where possible:
 - numeric/string/bool → Python scalar
 - matrix → MMatrix (4x4)
 - point array → MPointArray
 - mesh / nurbs / lattice / subdiv geometry → MFn wrapper of the
 CONNECTED upstream source (so you can call methods on it)
* For compound + multi, returns lightweight sub-proxies that defer
 resolution to access.
* At init time, ``datablock`` is None — we fall back to MPlug.asXxx
 / cmds.getAttr.
* At compute time, ``datablock`` is the MDataBlock so reads come
 through MDataHandle (faster + correct under the EM).

MODULE LAYOUT
-------------
The scalar/geometry readers and the write dispatch were split into sibling
modules (``plug_read``, ``plug_geometry``, ``plug_write``). This module keeps
the proxy classes + the top-level ``_resolve_plug`` dispatch and imports the
moved helpers by name. It also RE-EXPORTS the two helpers that external
callers historically imported from here (``_attr_mobject_for_name``,
``_coerce_to_4x4_numpy``) so those imports keep resolving.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

import maya.cmds as mc
import maya.OpenMaya as om

# Sibling imports. These were same-module globals before the split; the proxy
# method bodies and _resolve_plug still reach them by bare name.
from .plug_read import (
    _attr_mobject_for_name,
    _attr_short_or_long_name,
    _is_matrix_attr,
    _read_matrix_plug,
    _read_numeric_plug,
    _read_typed_plug,
    _read_unit_plug,
)
from .plug_write import _write_plug
from . import plug_governance

# Back-compat: callers historically imported these from plug_proxy.
from .plug_read import _attr_mobject_for_name  # noqa: F401
from .plug_write import _coerce_to_4x4_numpy  # noqa: F401


# ---- Helpers ----


def _plug_name(plug: "om.MPlug") -> str:
    """``MPlug.name()`` raw helper (defensive)."""
    try:
        return plug.name()
    except Exception:
        return "<unnamed plug>"


def _node_name_of(mobject) -> str:
    try:
        return om.MFnDependencyNode(mobject).name()
    except Exception:
        return "<node>"


def _unmanaged_error(mobject, name: str) -> AttributeError:
    """The plug exists in Maya but the node does not manage it, so it does not
    surface. Same exception TYPE as a missing attribute -- callers fall through
    to compute locals / init bindings / stored vars identically -- but the
    message says which of the two it was, because "I added it and it vanished"
    is otherwise very hard to diagnose."""
    return AttributeError(
        f"node {_node_name_of(mobject)!r} has an attribute {name!r}, but it is "
        f"not managed by the node, so it does not surface. Attributes added "
        f"with cmds.addAttr are invisible to mpynode; add it through the Node "
        f"Designer, the .mpn file, or add_input_attr / add_output_attr."
    )


# ---- Plug resolution dispatch ----


def _is_weightlist_attr(attr_mobject) -> bool:
    """True for a skinCluster ``weightList``-shaped attribute: an ARRAY compound
    whose single child is a MULTI numeric-double (``weights``). Structural (not
    name-based) so it matches the inherited ``weightList`` on any genuine
    skinCluster. Used to route the plug to a dense :class:`WeightListView`."""
    try:
        if not attr_mobject.hasFn(om.MFn.kCompoundAttribute):
            return False
        cfn = om.MFnCompoundAttribute(attr_mobject)
        if cfn.numChildren() != 1:
            return False
        child = cfn.child(0)
        if not child.hasFn(om.MFn.kNumericAttribute):
            return False
        if not om.MFnAttribute(child).isArray():
            return False
        return (om.MFnNumericAttribute(child).unitType()
                == om.MFnNumericData.kDouble)
    except Exception:
        return False


def _resolve_plug(
    plug: "om.MPlug",
    attr_mobject: "om.MObject",
    datablock=None,
    geom_iter=None,
    compute_ctx=None,
) -> Any:
    """Top-level dispatch: given a plug + its attribute MObject,
    return the appropriate Python value or sub-proxy.

    ``datablock`` / ``geom_iter`` / ``compute_ctx`` are threaded
    through so sub-proxies retain compute-time write capability +
    the shared signaling dict."""
    # Multi: a matrix multi returns the unified MatrixArrayView (one type for
    # both API layers) over a LAZY plug provider, so per-element indexing still
    # resolves on demand and a big multi isn't read whole unless vectorized.
    # Every other multi returns a plain PlugListProxy.
    try:
        if plug.isArray():
            if _is_matrix_attr(attr_mobject):
                from mpynode._common.plugs.promoted_types import MatrixArrayView

                return MatrixArrayView(
                    _MatrixPlugProvider(
                        plug, attr_mobject,
                        datablock=datablock, geom_iter=geom_iter,
                        compute_ctx=compute_ctx,
                    )
                )
            # skinCluster weightList (array compound of multi-double weights) ->
            # a dense-array view (numpy-transparent) so np.asarray(self.weightList)
            # densifies to (N,J); still indexable per-element (subclass).
            if _is_weightlist_attr(attr_mobject):
                return WeightListView(
                    plug, attr_mobject,
                    datablock=datablock, geom_iter=geom_iter,
                    compute_ctx=compute_ctx,
                )
            return PlugListProxy(
                plug, attr_mobject,
                datablock=datablock, geom_iter=geom_iter,
                compute_ctx=compute_ctx,
            )
    except Exception:
        pass

    # Compound (with named children) → return a CompoundPlugProxy.
    try:
        if plug.isCompound():
            return CompoundPlugProxy(
                plug, attr_mobject,
                datablock=datablock, geom_iter=geom_iter,
                compute_ctx=compute_ctx,
            )
    except Exception:
        pass

    # Scalar — dispatch on attribute Fn subclass.
    if attr_mobject.hasFn(om.MFn.kNumericAttribute):
        return _read_numeric_plug(plug, attr_mobject, data_block=datablock)
    if attr_mobject.hasFn(om.MFn.kUnitAttribute):
        return _read_unit_plug(plug, attr_mobject, data_block=datablock)
    if attr_mobject.hasFn(om.MFn.kMatrixAttribute):
        return _read_matrix_plug(plug, data_block=datablock)
    if attr_mobject.hasFn(om.MFn.kTypedAttribute):
        return _read_typed_plug(plug, attr_mobject, data_block=datablock)
    if attr_mobject.hasFn(om.MFn.kEnumAttribute):
        try:
            from mpynode._common.plugs.promoted_types import EnumInt
            # plug.asInt() is primary (works for static +
            # dynamic), data_block.inputValue() is a secondary fallback.
            try:
                return EnumInt(plug.asInt(), attr_mobject)
            except Exception:
                pass
            from .plug_read import _data_handle_for_plug
            handle = _data_handle_for_plug(plug, datablock)
            if handle is not None:
                try:
                    return EnumInt(handle.asShort(), attr_mobject)
                except Exception:
                    try:
                        return EnumInt(handle.asInt(), attr_mobject)
                    except Exception:
                        pass
            return None
        except Exception:
            return None
    # Unknown -- try cmds.getAttr last-resort (init-time only;
    # never inside compute(), where cmds.getAttr causes DG re-entry).
    if datablock is None:
        try:
            return mc.getAttr(plug.name())
        except Exception:
            return None
    return None


# ---- Sub-proxies for compound + multi ----


class CompoundPlugProxy:
    """A proxy bound to a compound MPlug. Attribute access walks the
    named children of the compound and returns their values."""

    __slots__ = ("_plug", "_attr_mobject", "_datablock", "_geom_iter", "_compute_ctx")

    def __init__(
        self,
        plug: "om.MPlug",
        attr_mobject: "om.MObject",
        datablock=None,
        geom_iter=None,
        compute_ctx=None,
    ):
        object.__setattr__(self, "_plug", plug)
        object.__setattr__(self, "_attr_mobject", attr_mobject)
        object.__setattr__(self, "_datablock", datablock)
        object.__setattr__(self, "_geom_iter", geom_iter)
        object.__setattr__(self, "_compute_ctx", compute_ctx)

    def __getattr__(self, name: str) -> Any:
        # Walk children of this compound, find the one whose attribute
        # short or long name matches.
        n_children = self._plug.numChildren()
        for i in range(n_children):
            child_plug = self._plug.child(i)
            try:
                child_attr = child_plug.attribute()
                fn = om.MFnAttribute(child_attr)
                if fn.name() == name or fn.shortName() == name:
                    return _resolve_plug(
                        child_plug,
                        child_attr,
                        datablock=self._datablock,
                        geom_iter=self._geom_iter,
                        compute_ctx=self._compute_ctx,
                    )
            except Exception:
                continue
        raise AttributeError(
            f"compound plug {_plug_name(self._plug)!r} has no child named {name!r}"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        # __slots__ fields — direct write.
        if name in ("_plug", "_attr_mobject", "_datablock", "_geom_iter", "_compute_ctx"):
            object.__setattr__(self, name, value)
            return
        # Find the matching child plug + dispatch write.
        n_children = self._plug.numChildren()
        for i in range(n_children):
            child_plug = self._plug.child(i)
            try:
                child_attr = child_plug.attribute()
                fn = om.MFnAttribute(child_attr)
                if fn.name() == name or fn.shortName() == name:
                    _write_plug(
                        child_plug, child_attr, value,
                        datablock=self._datablock,
                        geom_iter=self._geom_iter,
                        compute_ctx=self._compute_ctx,
                    )
                    return
            except Exception:
                continue
        raise AttributeError(
            f"compound plug {_plug_name(self._plug)!r} has no child named {name!r}"
        )

    def as_numpy(self):
        """Collapse a compound numeric plug (e.g. Double3
        ``translate``, ``amplitude``, ``restTranslate``) into a flat
        ``(N,) float64`` numpy array.

        Walks the compound's children, resolves each via the same
        plug-tree path the user expression would hit, casts to
        ``float``, and returns the result as numpy. Threads the
        compound's ``datablock`` through to children so reads pick
        up live propagation correctly.

        Use case: lets user expressions write
        ``np.asarray(self.amplitude)`` style code without going
        through ``cmds.getAttr`` (anti-pattern). For
        Double3/Float3/etc. attrs that promotion table
        returns as CompoundPlugProxy (not numpy), this is the
        canonical numpy bridge.

        Returns an empty ``(0,) float64`` array if the compound has
        no children or all child reads fail.
        """
        import numpy as _np

        out = []
        try:
            n_children = self._plug.numChildren()
        except Exception:
            return _np.empty((0,), dtype=_np.float64)
        for i in range(n_children):
            try:
                child_plug = self._plug.child(i)
                child_attr = child_plug.attribute()
                val = _resolve_plug(
                    child_plug, child_attr,
                    datablock=self._datablock,
                    geom_iter=self._geom_iter,
                    compute_ctx=self._compute_ctx,
                )
                out.append(float(val) if val is not None else 0.0)
            except Exception:
                out.append(0.0)
        return _np.asarray(out, dtype=_np.float64)

    def __array__(self, dtype=None):
        """Numpy interop: ``np.asarray(self)`` works seamlessly via
        ``as_numpy()`` so user code like
        ``np.asarray(self.amplitude, dtype=np.float64)`` does the
        right thing without an explicit ``.as_numpy()`` call."""
        arr = self.as_numpy()
        if dtype is not None:
            return arr.astype(dtype)
        return arr

    def __iter__(self):
        """Iteration over the flat numpy form. Lets
        ``[float(v) for v in self.amplitude]`` work."""
        return iter(self.as_numpy())

    def __len__(self):
        try:
            return int(self._plug.numChildren())
        except Exception:
            return 0

    def __getitem__(self, idx):
        """Index access: ``self.amplitude[0]`` returns child 0's value
        (NOT a CompoundPlugProxy of a child). Equivalent to
        ``self.as_numpy()[idx]`` but only resolves the one child
        we asked for."""
        try:
            child_plug = self._plug.child(int(idx))
            child_attr = child_plug.attribute()
            val = _resolve_plug(
                child_plug, child_attr,
                datablock=self._datablock,
                geom_iter=self._geom_iter,
                compute_ctx=self._compute_ctx,
            )
            return val
        except Exception:
            raise IndexError(f"child index {idx} out of range")

    def __repr__(self) -> str:
        try:
            children = [
                om.MFnAttribute(self._plug.child(i).attribute()).name()
                for i in range(self._plug.numChildren())
            ]
        except Exception:
            children = []
        return f"<CompoundPlugProxy {_plug_name(self._plug)!r} children={children}>"


class PlugListProxy:
    """A proxy bound to a multi (array) MPlug. Indexable: ``self[i]``
    returns a proxy/value for the element at logical index ``i``."""

    __slots__ = ("_plug", "_attr_mobject", "_datablock", "_geom_iter", "_compute_ctx")

    def __init__(
        self,
        plug: "om.MPlug",
        attr_mobject: "om.MObject",
        datablock=None,
        geom_iter=None,
        compute_ctx=None,
    ):
        object.__setattr__(self, "_plug", plug)
        object.__setattr__(self, "_attr_mobject", attr_mobject)
        object.__setattr__(self, "_datablock", datablock)
        object.__setattr__(self, "_geom_iter", geom_iter)
        object.__setattr__(self, "_compute_ctx", compute_ctx)

    def __getitem__(self, idx: int) -> Any:
        if not isinstance(idx, int):
            raise TypeError(f"multi plug indices must be int, got {type(idx).__name__}")
        # run_generic_compute() pre-allocates writable output-geometry handles
        # into compute_ctx, keyed by (attr short/long name, multi index), so
        # ``self.outputGeometry[i]`` hands back a writable MFn handle rather
        # than a wrapper around the upstream input.
        if self._compute_ctx is not None:
            handles = self._compute_ctx.get("output_handles")
            if handles:
                attr_name = _attr_short_or_long_name(self._attr_mobject)
                key = (attr_name, int(idx))
                if key in handles:
                    return handles[key]
        try:
            element_plug = self._plug.elementByLogicalIndex(idx)
        except Exception as exc:
            raise IndexError(
                f"multi plug {_plug_name(self._plug)!r} index {idx}: {exc}"
            )
        try:
            if element_plug.isCompound():
                return CompoundPlugProxy(
                    element_plug,
                    self._attr_mobject,
                    datablock=self._datablock,
                    geom_iter=self._geom_iter,
                    compute_ctx=self._compute_ctx,
                )
        except Exception:
            pass
        return _resolve_plug(
            element_plug,
            self._attr_mobject,
            datablock=self._datablock,
            geom_iter=self._geom_iter,
            compute_ctx=self._compute_ctx,
        )

    def __setitem__(self, idx: int, value: Any) -> None:
        # E3 init-time / E4 compute-time write to a multi element.
        if not isinstance(idx, int):
            raise TypeError(f"multi plug indices must be int, got {type(idx).__name__}")
        try:
            element_plug = self._plug.elementByLogicalIndex(idx)
        except Exception as exc:
            raise IndexError(
                f"multi plug {_plug_name(self._plug)!r} index {idx}: {exc}"
            )
        _write_plug(
            element_plug, self._attr_mobject, value,
            datablock=self._datablock,
            geom_iter=self._geom_iter,
            compute_ctx=self._compute_ctx,
        )

    def __len__(self) -> int:
        try:
            return self._plug.numElements()
        except Exception:
            return 0

    def __iter__(self):
        try:
            n = self._plug.numElements()
            for i in range(n):
                elt = self._plug.elementByPhysicalIndex(i)
                yield (
                    elt.logicalIndex(),
                    _resolve_plug(
                        elt,
                        self._attr_mobject,
                        datablock=self._datablock,
                        geom_iter=self._geom_iter,
                        compute_ctx=self._compute_ctx,
                    )
                    if not elt.isCompound()
                    else CompoundPlugProxy(
                        elt,
                        self._attr_mobject,
                        datablock=self._datablock,
                        geom_iter=self._geom_iter,
                        compute_ctx=self._compute_ctx,
                    ),
                )
        except Exception:
            return

    def __repr__(self) -> str:
        return f"<PlugListProxy {_plug_name(self._plug)!r} n_elements={len(self)}>"


class _MatrixPlugProvider:
    """Lazy plug-backed source for a ``MatrixArrayView`` over an api1
    matrix multi.

    Resolves elements on demand (``get_matrix`` -> a single ``MatrixView``
    via ``elementByLogicalIndex``, so ``worldMatrix[0]`` resolves even
    with no allocated elements), supports element writes, and can
    ``stack`` to ``(N, 4, 4)`` -- LOGICAL-indexed (row ``i`` == logical
    index ``i``, sparse gaps filled with identity) so it stays aligned
    with sibling multis (e.g. skinCluster ``matrix[j]`` /
    ``bindPreMatrix[j]``). The expensive full read happens ONLY when the
    vectorized form is actually requested.

    Duck-typed: ``MatrixArrayView`` detects a provider via ``get_matrix``
    + ``stack`` (so ``promoted_types`` needs no import of this module).
    """

    __slots__ = ("_plug", "_attr_mobject", "_datablock", "_geom_iter", "_compute_ctx")

    def __init__(self, plug, attr_mobject, datablock=None, geom_iter=None,
                 compute_ctx=None):
        self._plug = plug
        self._attr_mobject = attr_mobject
        self._datablock = datablock
        self._geom_iter = geom_iter
        self._compute_ctx = compute_ctx

    def count(self) -> int:
        try:
            return self._plug.numElements()
        except Exception:
            return 0

    def get_matrix(self, i: int):
        """Resolve logical element ``i`` lazily to a ``MatrixView``."""
        elem = self._plug.elementByLogicalIndex(int(i))
        return _read_matrix_plug(elem, data_block=self._datablock)

    def set_matrix(self, i: int, value) -> None:
        elem = self._plug.elementByLogicalIndex(int(i))
        _write_plug(
            elem, self._attr_mobject, value,
            datablock=self._datablock, geom_iter=self._geom_iter,
            compute_ctx=self._compute_ctx,
        )

    def stack(self):
        import numpy as _np

        logical = om.MIntArray()
        try:
            self._plug.getExistingArrayAttributeIndices(logical)
        except Exception:
            logical = om.MIntArray()
        if logical.length() == 0:
            return _np.zeros((0, 4, 4), dtype=_np.float64)
        size = max(logical[i] for i in range(logical.length())) + 1
        out = _np.broadcast_to(_np.eye(4, dtype=_np.float64), (size, 4, 4)).copy()
        for k in range(logical.length()):
            li = logical[k]
            try:
                out[li] = _np.asarray(self.get_matrix(li))
            except Exception:
                pass  # leave identity in this slot
        return out


class WeightListView(PlugListProxy):
    """Dense-array view over a skinCluster ``weightList`` multi-compound.

    Subclasses :class:`PlugListProxy` so per-element access is unchanged
    (``self.weightList[v]`` -> the vertex CompoundPlugProxy, ``.weights[j]`` ->
    the float; iteration yields ``(logical, proxy)``). It ADDS numpy
    transparency: ``np.asarray(self.weightList)`` -> a dense ``(N, J)`` float64
    matrix, LOGICAL-indexed (row ``v`` == vertex logical index ``v``, col ``j``
    == influence logical index ``j``), sparse gaps ZERO-filled, sized
    ``N = max painted vertex + 1`` and ``J = max painted influence + 1`` (across
    all vertices).

    The sizing mirrors :meth:`_MatrixPlugProvider.stack` so a densified weight
    row lines up with the sibling ``matrix[j]`` / ``bindPreMatrix[j]`` arrays --
    and it matches the compiled ``deform()``'s dense weight reader byte-for-byte.
    This is the SHARED parity contract for compiled linear-blend skinning:
    interpreted ``np.asarray(self.weightList)`` and the C++ reader must produce
    the identical dense matrix.
    """

    def asNumpy(self, dtype=None):
        """Dense ``(N, J)`` float64 weight matrix (see the class docstring)."""
        import numpy as _np

        v_idx = om.MIntArray()
        try:
            self._plug.getExistingArrayAttributeIndices(v_idx)
        except Exception:
            v_idx = om.MIntArray()
        nv = v_idx.length()
        if nv == 0:
            out = _np.zeros((0, 0), dtype=_np.float64)
            return out.astype(dtype) if dtype is not None else out

        rows = []            # (vertex_logical, [(infl_logical, weight), ...])
        max_v = -1
        max_j = -1
        weights_attr = None
        for k in range(nv):
            vi = v_idx[k]
            if vi > max_v:
                max_v = vi
            elt = self._plug.elementByLogicalIndex(vi)   # vertex compound
            try:
                wplug = elt.child(0)                      # the `weights` multi
            except Exception:
                rows.append((vi, []))
                continue
            if weights_attr is None:
                try:
                    weights_attr = wplug.attribute()
                except Exception:
                    weights_attr = None
            j_idx = om.MIntArray()
            try:
                wplug.getExistingArrayAttributeIndices(j_idx)
            except Exception:
                j_idx = om.MIntArray()
            pairs = []
            for m in range(j_idx.length()):
                ji = j_idx[m]
                if ji > max_j:
                    max_j = ji
                welt = wplug.elementByLogicalIndex(ji)
                w = None
                if weights_attr is not None:
                    w = _read_numeric_plug(welt, weights_attr,
                                           data_block=self._datablock)
                if w is None:
                    try:
                        w = welt.asDouble()
                    except Exception:
                        w = 0.0
                pairs.append((ji, float(w)))
            rows.append((vi, pairs))

        n = max_v + 1
        j = max_j + 1 if max_j >= 0 else 0
        out = _np.zeros((n, j), dtype=_np.float64)
        for vi, pairs in rows:
            for (ji, w) in pairs:
                out[vi, ji] = w
        return out.astype(dtype) if dtype is not None else out

    def __array__(self, dtype=None):
        """Numpy interop: ``np.asarray(self.weightList)`` -> dense ``(N, J)``."""
        return self.asNumpy(dtype)

    def __repr__(self) -> str:
        return "<WeightListView %r n_vertices=%d>" % (_plug_name(self._plug),
                                                      len(self))


# ---- Top-level node proxy ----


class PlugProxy:
    """A proxy bound to a Maya dependency node's plug tree.

    Inject one into the expression/init namespace as ``node``. Then
    user code can navigate the plug tree as Python attribute /
    indexing access::

        node.translate                       # CompoundPlugProxy
        node.translate.translateX            # float
        node.input[0].inputGeometry          # MFnMesh
        node.worldMatrix[0]                  # MMatrix

    Read + write support:
      * E1/E2 reads
      * E3 init-time writes via ``cmds.setAttr``
      * E4 compute-time writes via ``MDataBlock.outputValue(...)``
        when ``datablock`` is provided; deformer ``outputGeometry``
        is special-cased to use ``geom_iter.setAllPositions(...)``
        when ``geom_iter`` is provided.
    """

    __slots__ = ("_mobject", "_datablock", "_geom_iter", "_compute_ctx")

    def __init__(
        self,
        mobject: "om.MObject",
        datablock=None,
        geom_iter=None,
        compute_ctx=None,
    ):
        object.__setattr__(self, "_mobject", mobject)
        object.__setattr__(self, "_datablock", datablock)
        object.__setattr__(self, "_geom_iter", geom_iter)
        object.__setattr__(self, "_compute_ctx", compute_ctx)

    # ---- Attribute access ----

    def __getattr__(self, name: str) -> Any:
        # Framework/tooling probe names always raise, never shadow a real plug.
        if name.startswith("_"):
            raise AttributeError(name)

        attr_mobj = _attr_mobject_for_name(self._mobject, name)
        if attr_mobj is None:
            raise AttributeError(
                f"node {_node_name_of(self._mobject)!r} has no attribute "
                f"{name!r}"
            )
        # Only MANAGED plugs surface. Tested on the RESOLVED attribute, not the
        # spelling, so long / short / compound-child agree.
        if not plug_governance.is_managed(self._mobject, attr_mobj, name):
            raise _unmanaged_error(self._mobject, name)
        plug = om.MPlug(self._mobject, attr_mobj)
        return _resolve_plug(
            plug, attr_mobj,
            datablock=self._datablock,
            geom_iter=self._geom_iter,
            compute_ctx=self._compute_ctx,
        )

    def __setattr__(self, name: str, value: Any) -> None:
        """E3 init-time / E4 compute-time writes. Dispatch based on
        whether a DataBlock was provided at construction."""
        # __slots__ fields — direct write.
        if name in ("_mobject", "_datablock", "_geom_iter", "_compute_ctx"):
            object.__setattr__(self, name, value)
            return
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        attr_mobj = _attr_mobject_for_name(self._mobject, name)
        if attr_mobj is None:
            raise AttributeError(
                f"node {_node_name_of(self._mobject)!r} has no attribute "
                f"{name!r}; cannot write."
            )
        # Symmetric with read: otherwise a compute could quietly drive a plug
        # the compiled C++ node has no idea exists.
        if not plug_governance.is_managed(self._mobject, attr_mobj, name):
            raise _unmanaged_error(self._mobject, name)
        plug = om.MPlug(self._mobject, attr_mobj)
        _write_plug(
            plug, attr_mobj, value,
            datablock=self._datablock,
            geom_iter=self._geom_iter,
            compute_ctx=self._compute_ctx,
        )

    # ---- Geometry data (EM-safe) ----

    def geometry_data(self, name: str):
        """The raw geometry-DATA MObject feeding input ``name`` (mesh / curve /
        surface), or None. Lets callers read component tags (``MFnGeometryData``)
        off the SAME data ``self.<name>`` exposes -- an ``MFnMesh`` doesn't expose
        its backing data MObject.

        EM-safe: when a compute datablock is present the DATA is pulled through
        ``inputValue(plug).asMesh()`` -- the canonical read Maya keeps current under
        the Evaluation Manager. (A plain ``plug.asMObject()`` returns NULL for a
        geometry input inside a parallel-EM ``compute``, even though
        ``self.<name>.getPoints()`` still works by falling back to the DAG shape --
        which is why reading tags off ``asMObject`` silently emptied membership and
        snapped rivets to the origin on scrub.) Outside compute (Init / locator draw
        / query) there is no datablock, so we fall back to the plug walk."""
        try:
            attr_mobj = _attr_mobject_for_name(self._mobject, name)
            if attr_mobj is None:
                return None
            # Own by-name resolve needs its own gate -- __getattr__ never runs
            # for a method call. Returns None (this method's "no such geometry"
            # answer) so an unmanaged name looks like a nonexistent one.
            if not plug_governance.is_managed(self._mobject, attr_mobj, name):
                return None
            plug = om.MPlug(self._mobject, attr_mobj)
            # EM-safe compute path: the datablock's input handle.
            if self._datablock is not None:
                try:
                    from .plug_read import _data_handle_for_plug

                    handle = _data_handle_for_plug(plug, self._datablock)
                    if handle is not None:
                        data = handle.asMesh()
                        if data is not None and not data.isNull():
                            return data
                except Exception:
                    pass
            # Outside compute (Init / locator draw / query): no datablock, so
            # walk the plug to the source's DATA MObject.
            from .plug_geometry import geometry_data_mobject

            return geometry_data_mobject(plug)
        except Exception:
            return None

    # ---- Introspection helpers ----

    def __dir__(self):
        """Make IDEs and ``dir(node)`` show the actual plug names.

        Only the MANAGED ones -- listing a plug that ``__getattr__`` then
        refuses to return would be worse than not listing it."""
        try:
            fn = om.MFnDependencyNode(self._mobject)
            n = fn.attributeCount()
            names = []
            for i in range(n):
                try:
                    attr = fn.attribute(i)
                    attr_name = om.MFnAttribute(attr).name()
                    if not plug_governance.is_managed(
                            self._mobject, attr, attr_name):
                        continue
                    names.append(attr_name)
                except Exception:
                    continue
            return names
        except Exception:
            return []

    def __repr__(self) -> str:
        try:
            name = om.MFnDependencyNode(self._mobject).name()
        except Exception:
            name = "<unknown>"
        try:
            type_name = self._mobject.apiTypeStr()
        except Exception:
            type_name = "?"
        return f"<PlugProxy node={name!r} type={type_name}>"


def make_node_proxy_for_name(node_name: str) -> Optional[PlugProxy]:
    """Convenience: build a PlugProxy from a node name string. Returns
    None if the node doesn't exist."""
    try:
        sel = om.MSelectionList()
        sel.add(node_name)
        mobj = om.MObject()
        sel.getDependNode(0, mobj)
        return PlugProxy(mobj)
    except Exception:
        return None
