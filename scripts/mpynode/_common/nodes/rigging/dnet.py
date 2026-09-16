"""Shared DNET spring-network solver + authoring helpers.

This is the single source of truth for the ``MPyNode/DNET`` gallery
template. It holds:

* the pure-Python (optional-numba) relaxation ``Solver`` (and its module-level
  kernels ``_buildAdjacency`` / ``_evaluate_parallel``), transcribed 1:1 from the
  source ``bugs/dnet_code.mpn``; and
* the by-hand authoring helpers ``create_knot`` / ``create_link`` that every dnet
  demo builds through.

The node's Init tab imports ``Solver`` from here and the Compute tab instantiates
it -- the same "import the shared node code at runtime" pattern the procrustes
templates use (``mpynode._common.nodes.constraint.procrustes``) and Game of Life
uses (``mpynode._api2.mpy_mesh.build_default_output``). Keeping the algorithm as a
real module (rather than a baked source blob) makes it importable and directly
unit-testable without a template round-trip.

``numba`` is OPTIONAL: when it is absent the ``njit`` / ``prange`` decorators
no-op to pure numpy (correct, just slower). Because this uses numpy / numba it is
a pure-Python mPyNode (NOT the numpy-free C++-transpilable variant); it matches
the source .mpn's solver code / attribute names / variables exactly.

``maya.cmds`` is imported lazily INSIDE ``create_knot`` / ``create_link`` so the
Solver half of this module imports cleanly outside Maya (e.g. for unit tests).
"""

import numpy as np

# Import Numba if available
try:
    from numba import njit, prange
    print("USING NUMBA")

# Numba not installed -- provide no-op fallbacks so decorated code still runs.
except ImportError:
    print("NUMBA NOT AVAILABLE, DEFAULTING ")
    prange = range

    def njit(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator


@njit(fastmath=True)
def _buildAdjacency(kCount, linkIndex0, linkIndex1):
    """Build CSR-style adjacency mapping each knot to its connected links.

    Call once per topology change, reuse across frames.

    Returns:
        offsets  (kCount+1,) - start index into adj arrays for each knot
        adj_link (total,)    - link index for each connection
        adj_sign (total,)    - +1.0 if knot is index0 (receives positive force),
                               -1.0 if knot is index1 (receives negative force)
    """
    lCount = linkIndex0.shape[0]

    # count connections per knot
    counts = np.zeros(kCount, dtype=np.int32)
    for i in range(lCount):
        counts[linkIndex0[i]] += 1
        counts[linkIndex1[i]] += 1

    # build offsets (prefix sum)
    offsets    = np.empty(kCount + 1, dtype=np.int32)
    offsets[0] = 0
    for i in range(kCount):
        offsets[i + 1] = offsets[i] + counts[i]

    # fill adjacency arrays
    total     = offsets[kCount]
    adj_link  = np.empty(total, dtype=np.int32)
    adj_sign  = np.empty(total, dtype=np.float64)

    counts[:] = 0
    for i in range(lCount):
        k0            = linkIndex0[i]
        idx           = offsets[k0] + counts[k0]
        adj_link[idx] = i
        adj_sign[idx] = 1.0
        counts[k0] += 1

        k1            = linkIndex1[i]
        idx           = offsets[k1] + counts[k1]
        adj_link[idx] = i
        adj_sign[idx] = -1.0
        counts[k1] += 1

    return offsets, adj_link, adj_sign


@njit(fastmath=True, parallel=True)
def _evaluate_parallel(knotPositions, knotAnchored, linkLengths, linkIndex0, linkIndex1,
              linkForces, linkPushDamping, linkPullDamping, iterations, tolerance,
              damping, adj_offsets, adj_link, adj_sign):

    kCount = knotPositions.shape[0]
    lCount = linkIndex0.shape[0]
    D      = knotPositions.shape[1]

    tolerance = tolerance ** 2

    init_positions = np.empty(knotPositions.shape)
    positions      = np.empty(knotPositions.shape)
    positions_     = np.empty(knotPositions.shape)
    F              = np.empty((kCount, D))  # shared force buffer
    displacements  = np.empty(kCount)       # per-knot displacement

    for i in prange(kCount):
        for j in range(D):
            init_positions[i, j] = knotPositions[i, j]
            positions[i, j]      = knotPositions[i, j]
            positions_[i, j]     = knotPositions[i, j]

    iteration_count = 0
    # Bound BEFORE the loop so `iterations <= 0` has a defined answer. njit
    # zero-inits it and returns 0.0; plain Python raises UnboundLocalError; a
    # C++ port has to guess, and hoisting the in-loop `-1.0` (the obvious
    # reading) makes the degenerate case return -1.0 instead. Stating it here
    # is what makes all three agree -- the in-loop re-init below stays -1.0.
    maxDisplacement = 0.0
    while iteration_count < iterations:

        # -- Phase 1: accumulate forces (parallel, positions are READ-ONLY) --
        for i in prange(kCount):
            for j in range(D):
                F[i, j] = 0.0

            for ci in range(adj_offsets[i], adj_offsets[i + 1]):
                li   = adj_link[ci]
                sign = adj_sign[ci]

                tension = 0.0
                link    = np.empty(D)
                for j in range(D):
                    link[j] = positions[linkIndex1[li], j] - positions[linkIndex0[li], j]
                    tension += link[j] ** 2

                if tension > 0.0:
                    tension = tension ** 0.5
                    force   = tension - (linkLengths[li] - linkLengths[li] * linkForces[li])

                    if tension < linkLengths[li]:
                        force *= linkPushDamping[li]
                    elif tension > linkLengths[li]:
                        force *= linkPullDamping[li]

                    for j in range(D):
                        F[i, j] += sign * (link[j] / tension * force)

        # -- Phase 2: apply forces (parallel, F is READ-ONLY) --
        for i in prange(kCount):
            displacements[i] = -1.0

            if knotAnchored[i] < 1.0:
                displacement = 0.0
                for j in range(D):
                    positions[i, j] += F[i, j] * damping
                    displacement    += (positions[i, j] - positions_[i, j]) ** 2
                    positions_[i, j] = positions[i, j]

                displacements[i] = displacement

        # -- Convergence check (sequential - negligible cost) --
        maxDisplacement = -1.0
        for i in range(kCount):
            if displacements[i] > maxDisplacement:
                maxDisplacement = displacements[i]

        if maxDisplacement < tolerance:
            iterations = 0

        iteration_count += 1

    # blend between init and eval positions
    for i in prange(kCount):
        for j in range(D):
            positions[i, j] = (init_positions[i, j] * knotAnchored[i]
                               + positions[i, j] * (1.0 - knotAnchored[i]))

    # calculate final link lengths
    linkLengths_ = np.empty(lCount)
    for i in prange(lCount):
        linkLengths_[i] = 0.0
        for j in range(D):
            linkLengths_[i] += (positions[linkIndex1[i], j] - positions[linkIndex0[i], j]) ** 2
        linkLengths_[i] = linkLengths_[i] ** 0.5

    return positions, linkLengths_, iteration_count, maxDisplacement


class Solver():

    def __init__(self, previous=None):
        self.positions       = None
        self.previous        = previous
        self.local_positions = None
        self.lengths         = None
        self.iterations      = None
        self.max_force       = None
        self.counts          = None

        self._adj_offsets    = None
        self._adj_link       = None
        self._adj_sign       = None
        self._cached_kCount  = None
        self._cached_index0  = None
        self._cached_index1  = None

        if not self.previous is None:
            self.previous = np.array(self.previous).reshape(-1,4,4)


    def evaluate(self,
                 matrices,
                 anchors,
                 lengths,
                 inverseMatrix = None,
                 index0        = None,
                 index1        = None,
                 tensions      = None,
                 push          = None,
                 pull          = None,
                 reset         = None,
                 iterations    = 100,
                 tolerance     = 0.001,
                 damping=0.1):


        # Convert to numpy arrays
        matrices = np.asarray(matrices).astype(np.float64).reshape(-1,4,4)
        anchors  = np.asarray(anchors).astype(np.float64)
        lengths  = np.asarray(lengths).astype(np.float64)

        # Fill in defaults
        if inverseMatrix is None:
            inverseMatrix = np.identity(4).astype(np.float64)
        else:
            inverseMatrix = np.asarray(inverseMatrix).reshape(4,4).astype(np.float64)

        if index0 is None:
            index0 = np.arange(matrices.shape[0]-1).astype(np.int32)
        else:
            index0 = np.asarray(index0).astype(np.int32)

        if index1 is None:
            index1 = np.arange(1,matrices.shape[0]).astype(np.int32)
        else:
            index1 = np.asarray(index1).astype(np.int32)

        if tensions is None:
            tensions = np.zeros(lengths.shape[0]).astype(np.float64)
        else:
            tensions = np.asarray(tensions).astype(np.float64)

        if push is None:
            push = np.ones(lengths.shape[0]).astype(np.float64)
        else:
            push = np.asarray(push).astype(np.float64)

        if pull is None:
            pull = np.ones(lengths.shape[0]).astype(np.float64)
        else:
            pull = np.asarray(pull).astype(np.float64)

        if reset is None:
            reset = np.ones(matrices.shape[0]).astype(np.int32)
        else:
            reset = np.asarray(reset).astype(np.int32)
            if reset.ndim == 0:
                reset = np.full(matrices.shape[0], int(reset), np.int32)


        # reset previous if size mismatch
        if self.previous is None or self.previous.shape[0] != matrices.shape[0]:
            self.previous = matrices


        # force reset state to always reset if anchor > 0
        reset[np.where(anchors>0)] = 1

        # blend between eval modes
        previous = self.previous @ inverseMatrix
        matrices = matrices @ inverseMatrix
        M        = previous + reset[:,None][:,None] * (matrices - previous)

        # Rebuild adjacency if topology changed
        kCount = M.shape[0]
        rebuild = (self._adj_offsets is None
                   or self._cached_kCount != kCount
                   or self._cached_index0 is None
                   or self._cached_index1 is None
                   or self._cached_index0.shape != index0.shape
                   or self._cached_index1.shape != index1.shape
                   or not np.array_equal(self._cached_index0, index0)
                   or not np.array_equal(self._cached_index1, index1))

        if rebuild:
            self._adj_offsets, self._adj_link, self._adj_sign = _buildAdjacency(kCount, index0, index1)
            self._cached_kCount = kCount
            self._cached_index0 = index0.copy()
            self._cached_index1 = index1.copy()

        # Evaluate Network
        self.positions, self.lengths, self.iterations, self.max_force = _evaluate_parallel(M[:,3,:3],
                                                                                            anchors,
                                                                                            lengths,
                                                                                            index0,
                                                                                            index1,
                                                                                            tensions,
                                                                                            push,
                                                                                            pull,
                                                                                            iterations,
                                                                                            tolerance,
                                                                                            damping,
                                                                                            self._adj_offsets,
                                                                                            self._adj_link,
                                                                                            self._adj_sign)


        # Localise to parent matrix
        I                    = np.linalg.inv(matrices)
        self.local_positions = np.einsum('ni,nij->nj', self.positions, I[:, :3, :3]) + I[:, 3, :3]



        # Reset previous position
        self.previous         = matrices
        self.previous[:,3,:3] = self.positions


# ---------------------------------------------------------------------------
# Authoring helpers -- build a network by hand. The template's methods_source
# exposes these as @maya_command shims (dnetCreateKnot / dnetCreateLink) that
# delegate here, so they appear in the Methods tab and register as callable Maya
# commands, and every dnet demo builds its showcase through them.
# ---------------------------------------------------------------------------
def create_knot(node, draw_icon=False):
    """Create one KNOT -- a GOAL transform plus its RESULT child -- wired into
    the next free slot of ``node``.

    The GOAL is the transform you place/drive: ``goal.worldMatrix[0]`` drives
    ``matrices[i]`` and a ``goal.anchored`` weight (0 = free, 1 = pinned to the
    live goal) drives ``anchors[i]``. Its child RESULT transform receives
    ``positions[i]`` (the goal-local solved offset) on its ``translate``, so the
    child's WORLD position IS the solved knot -- the value ``create_link`` tracks.

    ``draw_icon=True`` adds a visual: an icosahedron ``polyPlatonicSolid`` whose
    hidden PROXY shape rides the RESULT child and whose visible DUPLICATE shape
    sits on the GOAL, linked by a worldspace ``blendShape`` (proxy -> visible) so
    the visible icon deforms onto the solved knot. A ``goal.radius`` attribute
    (default 0.1) drives both platonic solids. The goal is left selected so knots
    chain straight into ``create_link``. Returns the goal transform."""
    from maya import cmds as mc
    name = node.get_name()

    # Next free knot slot (indices may be sparse after deletes -> max + 1).
    idxs = mc.getAttr(name + ".matrices", multiIndices=True) or []
    i    = (max(idxs) + 1) if idxs else 0

    # GOAL: the transform you place/drive. worldMatrix -> matrices[i]; owns an
    # `anchored` weight (0 free / 1 pinned) wired into anchors[i].
    goal = mc.group(empty=True, name="dnetGoal#")
    mc.addAttr(goal, longName="anchored", attributeType="float",
               min=0.0, max=1.0, defaultValue=0.0, keyable=True)
    mc.connectAttr(goal + ".worldMatrix[0]", name + ".matrices[%d]" % i,
                   force=True)
    mc.connectAttr(goal + ".anchored", name + ".anchors[%d]" % i, force=True)

    # RESULT child: rides positions[i] (goal-local solved offset) so its WORLD
    # position IS the solved knot. create_link tracks these children.
    child = mc.group(empty=True, name="dnetKnot#")
    child = mc.parent(child, goal, relative=True)[0]
    mc.connectAttr(name + ".positions[%d]" % i, child + ".translate",
                   force=True)

    if draw_icon:
        # A `radius` attr on the goal drives BOTH icosahedra so proxy + visible
        # stay the same size (a mismatched blend maps between different meshes).
        mc.addAttr(goal, longName="radius", attributeType="float",
                   min=0.0, defaultValue=0.1, keyable=True)
        proxy_xf, proxy_cre = mc.polyPlatonicSolid(radius=0.1, solidType=1)
        vis_xf, vis_cre = mc.polyPlatonicSolid(radius=0.1, solidType=1)
        mc.connectAttr(goal + ".radius", proxy_cre + ".radius", force=True)
        mc.connectAttr(goal + ".radius", vis_cre + ".radius", force=True)
        # Reparent the SHAPES: the hidden PROXY onto the RESULT child, the visible
        # DUPLICATE onto the GOAL. Then drop the emptied creator transforms.
        proxy_shp = mc.listRelatives(proxy_xf, shapes=True, fullPath=True)[0]
        vis_shp   = mc.listRelatives(vis_xf, shapes=True, fullPath=True)[0]
        proxy_shp = mc.parent(proxy_shp, child, shape=True, relative=True)[0]
        vis_shp   = mc.parent(vis_shp, goal, shape=True, relative=True)[0]
        mc.delete(proxy_xf, vis_xf)
        # Worldspace blendShape: proxy(child, rides positions) -> visible(goal),
        # so the visible icon deforms onto the solved knot. Build it BEFORE hiding
        # the proxy -- an invisible target is rejected as "not deformable" -- and
        # it binds at rest (positions == 0 -> child world == goal world -> 0
        # delta).
        bs = mc.blendShape(child, goal, origin="world",
                           name="dnetKnotBlend#")[0]
        mc.setAttr(bs + ".weight[0]", 1.0)
        mc.setAttr(proxy_shp + ".visibility", 0)

    mc.select(goal, replace=True)
    return goal


def create_link(node, draw_icon=False):
    """Spring every selected knot to the LAST-selected knot (the hub). Select the
    spoke knots, shift-select the hub last, then run this. For each spoke -> hub
    pair a link is added to the next free slot: ``index0[e]``/``index1[e]`` take
    the two knots' resolved indices and ``restLengths[e]`` is seeded to the two
    GOALS' layout distance (the intended length, so the network starts at rest).

    Each link is a TRANSFORM carrying its own ``tension`` / ``push`` / ``pull``
    wired to ``tension[e]`` / ``push[e]`` / ``pull[e]`` (per-link contraction,
    compression resistance, stretch resistance); its ``inheritsTransform`` is
    turned OFF (it stays at the origin) so a world-space line drawn under it is
    not double-transformed. Its translate / rotate / scale + visibility are LOCKED
    and HIDDEN, so the only channels a user sees are tension / push / pull.
    ``draw_icon=True`` parents a degree-1 line under the link that spans the two
    knots' RESULT children (their solved world positions). Returns the link
    transforms."""
    from maya import cmds as mc
    import math
    name = node.get_name()

    sel  = mc.ls(selection=True, long=True, type="transform") or []
    if len(sel) < 2:
        raise RuntimeError("create_link needs >= 2 selected knots "
                           "(spokes first, hub last)")
    spokes, hub = sel[:-1], sel[-1]

    node_long = mc.ls(name, long=True)[0]

    def knot_index(goal):
        """Which matrices[] slot does this goal's worldMatrix[0] drive?"""
        for plug in (mc.listConnections(goal + ".worldMatrix[0]", source=False,
                                        destination=True, plugs=True) or []):
            pnode = plug.rsplit(".", 1)[0]
            if (mc.ls(pnode, long=True)[0] == node_long
                    and ".matrices[" in plug):
                return int(plug.rsplit("[", 1)[1].rstrip("]"))
        raise RuntimeError("%s is not a knot of %s (worldMatrix[0] is not "
                           "wired to matrices[])" % (goal, name))

    def knot_child(goal):
        """The goal's RESULT child (the transform riding positions[] -> its
        translate), whose worldMatrix is the solved knot."""
        for c in (mc.listRelatives(goal, children=True, type="transform",
                                   fullPath=True) or []):
            conns = mc.listConnections(c + ".translate", source=True,
                                       destination=False, plugs=True) or []
            if any(".positions[" in p for p in conns):
                return c
        raise RuntimeError("%s has no result child (positions[] -> translate)"
                           % goal)

    hub_i     = knot_index(hub)
    hub_child = knot_child(hub)
    hub_pos   = mc.xform(hub, query=True, worldSpace=True, translation=True)

    # Next free link slot.
    lidxs = mc.getAttr(name + ".index0", multiIndices=True) or []
    e     = (max(lidxs) + 1) if lidxs else 0

    links = []
    for spoke in spokes:
        spoke_i = knot_index(spoke)
        if spoke_i == hub_i:
            continue                                 # skip a degenerate self-link
        spoke_child = knot_child(spoke)
        spoke_pos = mc.xform(spoke, query=True, worldSpace=True,
                             translation=True)

        # Topology: this spring connects spoke -> hub. Rest length = the GOALS'
        # layout gap (the intended length), NOT the solved children's distance.
        mc.setAttr(name + ".index0[%d]" % e, spoke_i)
        mc.setAttr(name + ".index1[%d]" % e, hub_i)
        rest = math.sqrt(sum((a - b) ** 2
                             for a, b in zip(spoke_pos, hub_pos)))
        mc.setAttr(name + ".restLengths[%d]" % e, rest)

        # The LINK transform hosts the per-link tension / push / pull, each wired
        # to its own node slot. inheritsTransform OFF (kept at the origin) so a
        # world-space line drawn under it is not double-transformed.
        link = mc.group(empty=True, name="dnetLink#")
        mc.setAttr(link + ".inheritsTransform", 0)
        mc.addAttr(link, longName="tension", attributeType="float",
                   defaultValue=0.0, keyable=True)
        mc.connectAttr(link + ".tension", name + ".tension[%d]" % e, force=True)
        mc.addAttr(link, longName="push", attributeType="float",
                   defaultValue=1.0, keyable=True)
        mc.connectAttr(link + ".push", name + ".push[%d]" % e, force=True)
        mc.addAttr(link, longName="pull", attributeType="float",
                   defaultValue=1.0, keyable=True)
        mc.connectAttr(link + ".pull", name + ".pull[%d]" % e, force=True)

        # The link is a pure carrier (inheritsTransform off, its line drawn in
        # world space), so its TRS must never be touched: lock + hide SRT and
        # visibility, leaving ONLY tension / push / pull editable in the channel
        # box. (The demos reparent links via group(relative=True), which preserves
        # local values and so never writes to the now-locked channels.)
        for chan in ("translate", "rotate", "scale"):
            for axis in ("X", "Y", "Z"):
                mc.setAttr("%s.%s%s" % (link, chan, axis),
                           lock=True, keyable=False, channelBox=False)
        mc.setAttr(link + ".visibility",
                   lock=True, keyable=False, channelBox=False)

        if draw_icon:
            # A degree-1 line between the two RESULT children's WORLD positions
            # (decomposeMatrix on each child's worldMatrix -> the CVs). Reparent
            # the SHAPE under the link (inheritsTransform off -> local == world)
            # and drop the emptied curve transform.
            crv = mc.curve(degree=1, point=[spoke_pos, hub_pos],
                           name="dnetLinkCrv#")
            crv_shp = mc.listRelatives(crv, shapes=True, fullPath=True)[0]
            crv_shp = mc.parent(crv_shp, link, shape=True, relative=True)[0]
            mc.delete(crv)
            for k, cxf in ((0, spoke_child), (1, hub_child)):
                dm = mc.createNode("decomposeMatrix", name="dnetLinkDcm#")
                mc.connectAttr(cxf + ".worldMatrix[0]", dm + ".inputMatrix",
                               force=True)
                mc.connectAttr(dm + ".outputTranslate",
                               crv_shp + ".controlPoints[%d]" % k, force=True)

        links.append(link)
        e += 1

    return links
