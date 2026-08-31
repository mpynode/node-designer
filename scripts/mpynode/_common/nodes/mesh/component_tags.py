"""Geometry component-tag helpers (Maya 2022+).

Component tags let you name a set of mesh components and store that set ON
the geometry (under ``<shape>.componentTags[]``), editable in Maya's
Component Tag editor. This module wraps the bits the mpynode demos need:

* ``create_tag(shape, name, indices)`` -- author a vertex tag.
* ``resolve_tag_indices(shape, name)`` -- read a tag back to vertex ids.
* ``resolve_tags_to_clusters(shape, names)`` -- a list of tags ->
  one padded ``(N, L)`` int array (``-1`` fill), the shape the vectorized
  Procrustes solver consumes.
* ``clusters_from_self_tags(self, names)`` -- the same, but discovering the
  rest shape from a constraint's ``meshOrig`` input, given the Init/Compute
  ``self`` proxy (so an expression can resolve its own tags).

Resolution reads ``componentTags`` directly via ``getAttr`` (returns e.g.
``['vtx[0:5]']``) rather than ``geometryAttrInfo``, which needs a live
deformer/eval context and errors on a bare shape.
"""

from __future__ import annotations

import re

import maya.cmds as mc

_COMP_RE = re.compile(r"\[(\d+)(?::(\d+))?\]")


def parse_component_strings(contents) -> list:
    """Turn ``['vtx[0:5]', 'vtx[8]']`` into a flat ``[0,1,2,3,4,5,8]``."""
    out: list = []
    for c in contents or []:
        m = _COMP_RE.search(c)
        if not m:
            continue
        a = int(m.group(1))
        b = m.group(2)
        if b is None:
            out.append(a)
        else:
            out.extend(range(a, int(b) + 1))
    return out


def _to_component_strings(shape: str, indices) -> list:
    """Compress vertex ids into ``shape.vtx[a:b]`` / ``shape.vtx[a]`` runs."""
    idx = sorted({int(i) for i in indices})
    runs = []
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
            j += 1
        runs.append("vtx[%d]" % idx[i] if i == j else "vtx[%d:%d]" % (idx[i], idx[j]))
        i = j + 1
    return ["%s.%s" % (shape, r) for r in runs]


def create_tag(shape: str, tag_name: str, indices) -> str:
    """Create a vertex component tag ``tag_name`` on ``shape``. Returns the name
    created, or ``""`` when nothing was created.

    It does NOT overwrite, despite what this said for a long time. Measured:
    ``componentTag(create=True)`` on a name that is ALREADY taken returns ``""``,
    raises nothing and leaves the existing membership untouched -- so a caller
    re-authoring a live name silently keeps the OLD vertex set. That ``""`` is
    now returned rather than swallowed, so a caller can tell the difference.
    To genuinely replace a membership use
    ``componentTag(comps, modify="replace", tagName=...)``."""
    comps = _to_component_strings(shape, indices)
    if not comps:
        return ""
    return mc.componentTag(comps, create=True, newTagName=tag_name) or ""


def _candidate_tag_shapes(shape: str) -> list:
    """``shape`` + its sibling shapes (incl. intermediate ``*Orig``) under the
    same transform.

    On a DEFORMED mesh, component tags live on the intermediate ``*Orig``
    shape, not the visible output shape -- so any tag lookup must consider
    both. For an undeformed shape this is just ``[shape]``."""
    shapes = [shape]
    try:
        par = mc.listRelatives(shape, parent=True, fullPath=True) or []
        if par:
            sibs = (
                mc.listRelatives(
                    par[0], shapes=True, noIntermediate=False, fullPath=True
                )
                or []
            )
            for s in sibs:
                if s not in shapes:
                    shapes.append(s)
    except Exception:
        pass
    return shapes


def _tag_indices_on_shape(shape: str, tag_name: str):
    """Vertex ids for ``tag_name`` on a single ``shape``, or None if absent."""
    try:
        idxs = mc.getAttr(shape + ".componentTags", multiIndices=True) or []
    except Exception:
        return None
    for i in idxs:
        try:
            nm = mc.getAttr("%s.componentTags[%d].componentTagName" % (shape, i))
        except Exception:
            continue
        if nm == tag_name:
            contents = mc.getAttr(
                "%s.componentTags[%d].componentTagContents" % (shape, i)
            )
            return parse_component_strings(contents)
    return None


def tag_names(shape: str) -> list:
    """All component-tag names visible for ``shape`` (deform-aware: includes
    tags stored on the intermediate ``*Orig`` shape)."""
    out = []
    for s in _candidate_tag_shapes(shape):
        try:
            for i in mc.getAttr(s + ".componentTags", multiIndices=True) or []:
                nm = mc.getAttr("%s.componentTags[%d].componentTagName" % (s, i))
                if nm not in out:
                    out.append(nm)
        except Exception:
            pass
    return out


def resolve_tag_indices(shape: str, tag_name: str) -> list:
    """Vertex ids belonging to ``tag_name`` for ``shape`` (empty if absent).

    Deform-aware: searches ``shape`` and its intermediate ``*Orig`` sibling,
    since a deformed mesh stores its component tags on the Orig."""
    for s in _candidate_tag_shapes(shape):
        res = _tag_indices_on_shape(s, tag_name)
        if res:
            return res
    return []


def pad_clusters(index_lists):
    """Pad a list of ragged id lists into one ``(N, L)`` int array, ``-1`` fill."""
    import numpy as np

    n = len(index_lists)
    width = max((len(c) for c in index_lists), default=0)
    arr = np.full((n, max(width, 1)), -1, dtype=np.int64)
    for i, c in enumerate(index_lists):
        if c:
            arr[i, : len(c)] = c
    return arr


def resolve_tags_to_clusters(shape: str, names):
    """Resolve ``names`` (per output) on ``shape`` -> padded ``(N, L)`` array."""
    return pad_clusters([resolve_tag_indices(shape, t) for t in (names or [])])


def shape_from_plug(plug: str):
    """Return the source SHAPE feeding ``plug`` (e.g. ``node.meshOrig``), or
    None if the plug is missing/unconnected (e.g. queried mid file-load).

    Avoids ``listConnections(shapes=True)`` (its mapping of shape-level
    ``worldMesh`` connections is inconsistent across Maya versions). Instead
    we take the raw source node and, if it's a transform, descend to its
    first non-intermediate shape."""
    try:
        src = mc.listConnections(plug, source=True, destination=False) or []
    except Exception:
        return None
    if not src:
        return None
    node = src[0]
    try:
        inherited = mc.nodeType(node, inherited=True) or []
    except Exception:
        inherited = []
    if "shape" in inherited:
        return node
    try:
        shapes = (
            mc.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True)
            or []
        )
    except Exception:
        shapes = []
    return shapes[0] if shapes else None


def node_name_from_self(self_proxy) -> str:
    """Recover the owning node's name from an Init (InitProxy) or Compute
    (SelfProxy) ``self`` object, since neither exposes a public accessor.
    Returns "" if it can't be determined."""
    # Init phase: InitProxy stashes the node name.
    try:
        return object.__getattribute__(self_proxy, "_ip_node_name")
    except AttributeError:
        pass
    # Compute phase: SelfProxy stashes the (api1) MObject.
    try:
        import maya.OpenMaya as om1

        mobj = object.__getattribute__(self_proxy, "_psp_mobject")
        return om1.MFnDependencyNode(mobj).name()
    except Exception:
        return ""


def clusters_from_self_tags(self_proxy, names, input_plug="mesh"):
    """From a constraint's ``self`` proxy, resolve its ``clusterTags`` against
    the shape feeding ``input_plug`` (default ``"mesh"``) -> padded ``(N, L)``
    array.

    Returns an empty ``(0, 1)`` array (never raises) when the node/shape can't
    be resolved yet -- e.g. if called before connections exist. Callers should
    resolve where the inputs are guaranteed live (Compute) and cache."""
    node = node_name_from_self(self_proxy)
    if not node:
        return pad_clusters([])
    shape = shape_from_plug(node + "." + input_plug)
    if shape is None:
        return pad_clusters([])
    return resolve_tags_to_clusters(shape, names)


# ---------------------------------------------------------------------------
# LIVE resolution off the input-mesh DATA (Maya 2022+ component-tag API).
#
# The helpers above read tags via ``getAttr`` on a shape node (a side channel)
# and are used for tag ENUMERATION / authoring in setup/demo (which run in Maya
# and are never compiled). The helpers below instead read tags off the geometry
# DATA flowing into a node's mesh input plug, via ``MFnGeometryData`` -- exactly
# what a compiled C++ node reads from its input handle. Reading MEMBERSHIP this
# way each evaluation makes it LIVE (a component-tag edit rides the mesh data and
# dirties the input plug, so the node re-resolves) AND keeps interpreted and
# compiled nodes resolving identically. Membership is looked up by a KNOWN tag
# NAME (the node's config), so auto-generated primitive tags never interfere.
# ---------------------------------------------------------------------------


def mesh_data_from_node_plug(node, input_plug="mesh"):
    """The geometry-DATA MObject feeding ``<node>.<input_plug>``, read from the
    node's OWN input plug via api2, or None when the input is unconnected.

    EM-safety is why this reads the node's OWN destination plug and NOT the
    upstream source: during ``compute`` under Maya's Evaluation Manager, a node's
    declared inputs are guaranteed present in its datablock, so ``plug.asMObject()``
    on the own input plug routes through that datablock (the same canonical read
    ``plug_read._typed_data_mobject`` uses). Walking to another node's output plug
    (``connectedTo(...).asMObject()``) is NOT scheduled relative to this compute and
    returns empty under the EM -- which silently emptied the component-tag membership
    and left the outputs at their defaults. The disconnect case is detected with
    ``isDestination`` (a cheap connection-metadata query, not a data pull), so an
    unconnected input yields None -> empty membership, matching a compiled node's
    empty ``data.inputValue(meshAttr).asMesh()`` handle. Never raises."""
    try:
        import maya.OpenMaya as om1

        sel = om1.MSelectionList()
        sel.add(node + "." + input_plug)
        plug = om1.MPlug()
        sel.getPlug(0, plug)
        if plug.isArray():
            plug = plug.elementByLogicalIndex(0)
        # Mirror plug_geometry._read_geometry_plug: walk to the connected source
        # (shape.worldMesh[0]); unconnected -> None (empty, like a compiled node's
        # empty input handle). Reads the source data MObject in api1.
        target = plug
        srcs = om1.MPlugArray()
        try:
            plug.connectedTo(srcs, True, False)  # asDst -> sources
        except Exception:
            srcs = None
        if srcs is not None and srcs.length() > 0:
            target = srcs[0]
        elif not plug.isConnected():
            return None
        obj = target.asMObject()
        if obj is None or obj.isNull():
            return None
        return obj
    except Exception:
        return None


def mesh_matrix_from_mesh_data(mesh_data):
    """The source transform carried by a geometry-DATA MObject, as a flat
    row-major 16-tuple (Maya's row-vector convention: translation in [12:15]).
    Returns None when the data is missing or unreadable. Never raises.

    ``worldMesh[0]`` DATA holds OBJECT-space points plus this matrix; it does
    NOT hold baked world points. A function set built from a data MObject has no
    DAG path, so ``getPoints(kWorld)`` cannot reach world space -- ``p * M`` with
    this matrix is the only way, and it reproduces ``MFnMesh(dagPath).getPoints(
    kWorld)`` exactly. A draw that reads a mesh input and claims world space is
    pinned at the origin without it.

    Same dual-MObject dispatch as :func:`tag_indices_from_mesh_data`: api2 from
    the plug side-channel, api1 from the EM-safe datablock path."""
    if mesh_data is None:
        return None
    try:
        import maya.api.OpenMaya as om2

        if isinstance(mesh_data, om2.MObject):
            return tuple(om2.MFnGeometryData(mesh_data).matrix)
    except Exception:
        pass
    try:
        import maya.OpenMaya as om1

        # api1 mirrors C++: getMatrix(MMatrix&) out-param, NOT the api2
        # ``.matrix`` property. This is the branch the LIVE compute takes --
        # mesh_data_from_node_plug hands back an api1 MObject.
        m = om1.MMatrix()
        om1.MFnGeometryData(mesh_data).getMatrix(m)
        return tuple(m(r, c) for r in range(4) for c in range(4))
    except Exception:
        return None


def tag_indices_from_mesh_data(mesh_data, tag_name):
    """Component ids for ``tag_name`` read LIVE off a mesh-DATA MObject via
    ``MFnGeometryData`` (Maya 2022+). Returns [] if the tag is absent or the
    data is not readable. Never raises.

    Handles BOTH an api2 MObject (from :func:`mesh_data_from_node_plug`, a plug
    side-channel used at draw/query time) and an api1 MObject (from
    :func:`_mesh_data_via_datablock`, the EM-safe compute path). The two MObject
    flavors are distinct classes, so we dispatch by ``isinstance``."""
    if mesh_data is None:
        return []
    # api2 MObject (plug side-channel / probes).
    try:
        import maya.api.OpenMaya as om2

        if isinstance(mesh_data, om2.MObject):
            gfn = om2.MFnGeometryData(mesh_data)
            if tag_name not in gfn.componentTags():
                return []
            comp = gfn.componentTagContents(tag_name)
            return list(om2.MFnSingleIndexedComponent(comp).getElements())
    except Exception:
        pass
    # api1 MObject (EM-safe datablock path). api1 MStringArray isn't reliably
    # importable, so skip the name-list check and read the contents directly --
    # componentTagContents on an absent tag yields an empty/None component, which
    # getElements reports as [] (or the try/except catches it).
    try:
        import maya.OpenMaya as om1

        gfn = om1.MFnGeometryData(mesh_data)
        comp = gfn.componentTagContents(tag_name)
        if comp is None or comp.isNull():
            return []
        ids = om1.MIntArray()
        om1.MFnSingleIndexedComponent(comp).getElements(ids)
        return [int(ids[i]) for i in range(ids.length())]
    except Exception:
        return []


def _live_mesh_data_for_self(self_proxy, input_plug):
    """The mesh DATA feeding ``<input_plug>`` for a compute ``self`` proxy, resolved
    Evaluation-Manager-safely.

    Primary path (EM-safe): the raw geometry DATA MObject the compute bridge
    pre-seeds into ``compute_locals["_mpy_geom_data"]``. The bridge reads it off
    the datablock (``data_block.inputValue(<geo>).asMesh()``) on the compute
    thread -- the SAME object ``self.<input_plug>`` wraps -- so its component tags
    match the flowing geometry exactly. This is the ONLY handle that survives the
    Evaluation Manager: under EM every side-channel plug read (``MSelectionList``
    / ``connectedTo`` / ``cmds.getAttr`` / a name-resolved ``MPlug``) returns
    EMPTY inside a DG ``compute`` on the worker thread, which silently zeroed the
    tag membership and left the outputs at their defaults (rivets snapping to the
    origin on scrub).

    Fallback (Init / a locator's draw pull / query time, where there is no
    seeded DATA but a name-resolved plug is fine): the compute ``PlugProxy``'s
    :meth:`geometry_data`, then :func:`mesh_data_from_node_plug`. None if nothing
    resolves."""
    # Tier 1: bridge-seeded DATA MObject (EM-safe, carries live tags).
    try:
        locals_map = self_proxy.get_compute_locals()
        geom = locals_map.get("_mpy_geom_data") if locals_map else None
        if isinstance(geom, dict):
            data = geom.get(input_plug)
            if data is not None:
                return data
    except Exception:
        pass
    # Tier 2: live compute PlugProxy (main-thread compute / DG mode).
    try:
        pp = self_proxy.get_plug_proxy()
    except Exception:
        pp = None
    if pp is not None:
        try:
            data = pp.geometry_data(input_plug)
            if data is not None:
                return data
        except Exception:
            pass
    # Tier 3: name-resolved side-channel (draw / query, no compute datablock).
    node = node_name_from_self(self_proxy)
    return mesh_data_from_node_plug(node, input_plug) if node else None


def tag_indices_from_self(self_proxy, tag_name, input_plug="mesh"):
    """Live component ids for ``tag_name`` off ``<input_plug>`` for a compute
    ``self`` proxy, resolved EM-safely (datablock in compute, plug side-channel
    otherwise). [] if absent/unavailable. Never raises."""
    return tag_indices_from_mesh_data(
        _live_mesh_data_for_self(self_proxy, input_plug), tag_name
    )


def clusters_from_node_plug_live(node, names, input_plug="mesh"):
    """Resolve ``names`` (one tag per output) LIVE off the DATA at
    ``<node>.<input_plug>`` -> padded ``(N, L)`` int array. Reads component-tag
    membership from the input mesh data every call (no caching), so a tag edit
    is reflected on the next evaluation. Never raises.

    Uses the plug side-channel (no ``self`` proxy here); prefer
    :func:`clusters_from_self_tags_live` in compute for EM safety."""
    if not node:
        return pad_clusters([])
    data = mesh_data_from_node_plug(node, input_plug)
    if data is None:
        return pad_clusters([])
    return pad_clusters(
        [tag_indices_from_mesh_data(data, t) for t in (names or [])]
    )


def clusters_from_self_tags_live(self_proxy, names, input_plug="mesh"):
    """Live counterpart of :func:`clusters_from_self_tags`: resolve ``names``
    off the DATA feeding ``input_plug`` every call (no cache), so component-tag
    edits take effect immediately. EM-safe -- reads the input mesh DATA through
    the compute datablock (falls back to the plug side-channel outside compute).
    Returns an empty padded array (never raises) when data can't be resolved yet."""
    data = _live_mesh_data_for_self(self_proxy, input_plug)
    if data is None:
        return pad_clusters([])
    return pad_clusters(
        [tag_indices_from_mesh_data(data, t) for t in (names or [])]
    )
