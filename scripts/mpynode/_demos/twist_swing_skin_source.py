"""SSOT source strings for the Twist/Swing Skin template (two weight sets).

Maya-free module-level string constants (INIT / COMPUTE / METHODS / DESC) shared
by the template builder (``build_templates.build_experimental_twist_swing``) AND
the native compiler parity tests, so the compute that ships is byte-for-byte the
compute the tests compile. Editing the template = editing THIS file.

Design: the two painted weight sets are declared ``double is_array=True`` INPUT
plugs (``twistWeights`` / ``swingWeights``), each flattened row-major to length
``N*J``. They serialize per node (per-instance + persistent) and the compiled
deform reads them directly, so the two-weight-set node compiles to byte-parity
(see docs/superpowers/specs/2026-07-24-twist-swing-dual-compile-design.md). All
interactive paint machinery lives in the blessed ``self.sync_paint(mode)``
``NativeSideEffect`` method -- interpreted-only, a no-op in the compiled node.
"""
from __future__ import annotations

INIT = "import numpy as np\n"

# NOTE: kept as a pure statement block (the mpynode Compute body). It lowers to
# pure C++ via nd_lower.lower_deform (proven by twist_swing_dual_parity_test).
COMPUTE = r'''# ----------------------------------------------------------------------
# mPySkinCluster -- twist/swing with TWO weight sets on ONE node, painted
# interactively via the skinMode enum, COMPILABLE to pure C++.
#
# self.twistWeights / self.swingWeights are declared (double, is_array) INPUT
# plugs holding the two dense weight sets FLATTENED row-major to length N*J:
# twistWeights drives the DUAL-QUATERNION twist, swingWeights the LINEAR-BLEND
# swing (bend). Being plugs, they serialize PER NODE (each character keeps its
# own weights) and the compiled deform reads them directly -- so this node
# compiles to byte-parity (the two sets are never shared across instances).
#
# skinMode is a PAINT-MODE selector:
#   0 Paint LBS (Swing) -> preview the live weightList with linear_blend; paint it
#                          and sync_paint banks the edits into swingWeights.
#   1 Paint DQS (Twist) -> preview the live weightList with dual_quaternion; paint
#                          it and sync_paint banks the edits into twistWeights.
#   2 Live Result       -> deform from BOTH weight-set plugs (twist + swing).
# twistAxis picks the bone-local twist axis (0 X default / 1 Y / 2 Z).
#
# self.sync_paint(mode) holds ALL the interactive machinery (load the active set
# into weightList on a mode switch so Paint Skin Weights shows it; bank painted
# weightList back into the active set plug on a settled eval). It is a blessed
# NativeSideEffect method: interpreted-only, and a bare call lowers to NOTHING in
# the compiled node (which runs headless -- no paint session -- and reads the two
# weight plugs directly, so omitting the scratchpad staging is faithful).
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

mode = int(self.skinMode)

# interactive paint load/bank/latch (a no-op in the compiled node).
self.sync_paint(mode)

nj = self.matrix.shape[0]                        # influence count
nv = rest.shape[0]                               # vertex count
twist = np.asarray(self.twistWeights)            # flat (N*J,) weight-set plugs
swing = np.asarray(self.swingWeights)
have_sets = twist.size == nv * nj and swing.size == nv * nj

if mode == 0:                                    # Paint LBS: preview live weightList
    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)
elif mode == 1:                                  # Paint DQS: preview live weightList
    deformed = self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)
elif have_sets:                                  # Live Result: both weight-set plugs
    deformed = self.twist_swing_dual(rest, twist.reshape(nv, nj), swing.reshape(nv, nj), self.matrix, self.bindPreMatrix, int(self.twistAxis))
else:                                            # not seeded yet -> plain LBS fallback
    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)

# envelope=0 rest, 1 fully skinned (partial-effect composition explicit here).
mesh.setPoints(rest + float(self.envelope) * (deformed - rest))
'''

METHODS = '''@maya_test(label="Twist/swing deforms; swing set independently changes it", digits=4)
def test_twist_swing(self):
    """Validate the node's INTENT (the SAME test passes on the interpreted node
    and its C++ compile -> parity): in Live Result mode the two weight-set plugs
    (twistWeights + swingWeights) actually skin the mesh, and swapping ONLY the
    swing set to a different falloff changes the deformed result -- proving BOTH
    sets are genuinely used (mirrors the builder's compute_ok / swing_effect).

    Scene-robust: validate whatever mesh THIS skinCluster already deforms (the
    demo's arm, or a prior run's rig -- so it survives create->run demo->test and
    running twice); build a fresh 2-joint rig ONLY if self drives nothing yet.
    Stays on `self` (never a fresh serialized copy) to keep interpreted==compiled
    parity, breaks any incoming connections before driving a plug, and gates on
    the envelope (0 == exact rest)."""
    from maya import cmds as mc
    import maya.api.OpenMaya as om2
    import numpy as np
    from mpynode._common.methods.test_helpers import assert_true

    name = self.get_name()

    def _set(plug, *vals):
        # A demo may have CONNECTED this input; break it so the test can drive it.
        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(s, plug)
        mc.setAttr(plug, *vals)

    def _pts(sh):
        sel = om2.MSelectionList(); sel.add(sh)
        fn = om2.MFnMesh(sel.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    def _seed(plug, W):
        # Weight-set element plugs are never connection targets, so a plain
        # setAttr (matching the demo) is both correct and fast.
        flat = np.asarray(W, dtype=np.float64).ravel()
        for i in range(flat.size):
            mc.setAttr("%s.%s[%d]" % (name, plug, i), float(flat[i]))

    # Validate whatever mesh THIS skinCluster already drives (the demo's arm, or a
    # prior test run's rig); build a fresh 2-joint cylinder rig ONLY if self drives
    # nothing yet. A bound skinCluster + a 2nd geometry does NOT deform, so we must
    # reuse self's current deform target rather than attach an unrelated mesh.
    try:
        geo = mc.skinCluster(name, q=True, geometry=True) or []
    except Exception:
        geo = mc.deformer(name, q=True, geometry=True) or []
    if geo:
        shape = (mc.ls(geo[0], long=True) or [geo[0]])[0]
    else:
        cyl = mc.polyCylinder(name="tswTestArm#", radius=1.0, height=6.0,
                              subdivisionsX=8, subdivisionsY=8)[0]
        shape = mc.listRelatives(cyl, shapes=True, fullPath=True)[0]
        mc.select(clear=True)
        j0 = mc.joint(name="tswTestBase#", position=(0.0, -3.0, 0.0))
        j1 = mc.joint(name="tswTestMid#", position=(0.0, 0.0, 0.0))
        mc.select(clear=True)
        r0 = _pts(shape)
        ys = r0[:, 1]
        lo, hi = float(ys.min()), float(ys.max())
        span = (hi - lo) or 1.0
        tt = np.clip((ys - lo) / span, 0.0, 1.0)
        ramp = np.stack([1.0 - tt, tt], axis=1)          # smooth 2-bone ramp
        mc.deformer(name, e=True, g=cyl)
        for i, jnt in enumerate((j0, j1)):
            mc.connectAttr(jnt + ".worldMatrix[0]", "%s.matrix[%d]" % (name, i),
                           force=True)
            inv = mc.getAttr(jnt + ".worldInverseMatrix[0]")
            mc.setAttr("%s.bindPreMatrix[%d]" % (name, i), inv, type="matrix")
        # Seed the live weightList scratchpad BEFORE the first eval (a kSkinCluster
        # locks a 0.5/0.5 default on first eval, then resists setAttr).
        for v in range(r0.shape[0]):
            mc.setAttr("%s.weightList[%d].weights[0]" % (name, v), float(ramp[v, 0]))
            mc.setAttr("%s.weightList[%d].weights[1]" % (name, v), float(ramp[v, 1]))
        _seed("twistWeights", ramp)
        _seed("swingWeights", ramp)
        _set(j1 + ".rotateX", 80.0)                      # pose so the mesh bends
        _set(j1 + ".rotateZ", 55.0)

    # Force Live Result on self's declared twist axis; advance to a posed frame so
    # a keyframed demo rig is actually bent (harmless for the static cylinder rig).
    _set(name + ".twistAxis", 0)
    _set(name + ".skinMode", 2)                          # Live Result: both plugs
    try:
        mc.currentTime(mc.playbackOptions(q=True, max=True))
    except Exception:
        pass

    # Influence + vertex counts for THIS skin (an adopted arm may have >2 bones).
    nj = len(mc.getAttr(name + ".matrix", multiIndices=True) or [])
    nv = mc.polyEvaluate(shape, vertex=True)

    def _eval(env):
        # Toggle the envelope (a real plug) so the deformer actually re-runs its
        # compute (dgdirty alone can return the cached deformed mesh).
        _set(name + ".envelope", 0.0)
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(shape + ".outMesh")
        mc.setAttr(name + ".envelope", float(env))
        mc.dgdirty(name + ".outputGeometry")
        mc.getAttr(shape + ".outMesh")
        return _pts(shape)

    # Read whatever twist set self currently drives (the demo's DQS set, a prior
    # run's, or the ramp seeded above), reshaped to (nv, nj); rebuild a valid
    # 2-end ramp if it is somehow unseeded so the DQS blend can't divide by zero.
    tw_idx = mc.getAttr(name + ".twistWeights", multiIndices=True) or []
    tw_flat = np.array([mc.getAttr("%s.twistWeights[%d]" % (name, i))
                        for i in tw_idx], dtype=np.float64)
    if tw_flat.size == nv * nj and nj >= 2:
        tw = tw_flat.reshape(nv, nj)
    else:
        ys = _pts(shape)[:, 1]
        lo, hi = float(ys.min()), float(ys.max())
        span = (hi - lo) or 1.0
        tt = np.clip((ys - lo) / span, 0.0, 1.0)
        nj = max(nj, 2)
        tw = np.zeros((nv, nj)); tw[:, 0] = 1.0 - tt; tw[:, -1] = tt
        _seed("twistWeights", tw)

    # twist == swing: envelope 0 must be exact rest and envelope 1 must skin.
    _seed("swingWeights", tw)
    rest = _eval(0.0)
    same_pts = _eval(1.0)
    # Now change ONLY the swing set (roll each vertex's weights across influences
    # -- a different, still-valid partition): the result must move on its own,
    # proving BOTH weight sets are genuinely consumed.
    _seed("swingWeights", np.roll(tw, 1, axis=1))
    diff_pts = _eval(1.0)

    assert_true(bool(np.isfinite(diff_pts).all()),
                "twist/swing deform must be finite")
    moved = float(np.abs(same_pts - rest).max())
    assert_true(moved > 0.1,
                "twist/swing skin should deform the mesh (moved %.4f)" % moved)
    swing_effect = float(np.abs(diff_pts - same_pts).max())
    assert_true(swing_effect > 1e-3,
                "the swing weight set must independently change the result "
                "(delta %.4f)" % swing_effect)


@maya_demo(label="Two-Weight-Set Twist/Swing Arm")
def demo(self):
    """Skin the bundled two-bone arm (arm.ma -- the SAME mesh the ouch / LBS / DQS /
    twist-swing demos use) with THIS node, seeding the two weight-set input plugs
    from the bundled JSON files shipped beside this template:
      * twistWeights <- DQS.json  (rigid falloff -> dual-quaternion TWIST pass)
      * swingWeights <- LBS.json  (smooth falloff -> linear-blend SWING/bend pass)
    The elbow first TWISTS (rotateX 0->90 over frames 0-30, showing the DQS twist
    weights), then BENDS (rotateY 0->90 over frames 30-90, showing the LBS swing
    weights). Falls back to a 2-joint cylinder with procedural weights if arm.ma or
    the JSON weight sets are unavailable.

    To repaint either set: set skinMode to Paint LBS (Swing) or Paint DQS (Twist)
    -- that set auto-fills weightList -- paint in Paint Skin Weights, and your edits
    bank straight back into the set's plug. Switch to Live Result to see both
    combined. Because the sets are plugs, the node compiles to pure C++."""
    from maya import cmds as mc
    import numpy as np
    import os, json
    name = self.get_name()

    def _seed_plug(plug, W):
        """setAttr a dense (N, J) weight set into a flattened double-array plug."""
        flat = np.asarray(W, dtype=np.float64).ravel()
        for i in range(flat.size):
            mc.setAttr("%s.%s[%d]" % (name, plug, i), float(flat[i]))

    def _extract(sc, mesh_shape):
        """Stock skin influences (influenceObjects order), vert count, and
        bindPreMatrix keyed by logical index."""
        import maya.OpenMaya as om1
        import maya.OpenMayaAnim as oma1
        sl = om1.MSelectionList(); sl.add(sc)
        o = om1.MObject(); sl.getDependNode(0, o)
        mfn = oma1.MFnSkinCluster(o)
        infl = om1.MDagPathArray(); mfn.influenceObjects(infl)
        names = [infl[i].fullPathName() for i in range(infl.length())]
        nv = mc.polyEvaluate(mesh_shape, vertex=True)
        bind = {}
        for cc in (mc.getAttr(sc + ".bindPreMatrix", multiIndices=True) or []):
            bind[cc] = mc.getAttr(sc + ".bindPreMatrix[%d]" % cc)
        return names, nv, bind

    def _load_json_weights(path, wired_short):
        """Load a dense weight set from an {influences, weights} JSON, aligning its
        columns to the wired influence order so column i lines up with matrix[i].
        Prefer alignment BY NAME (joint short name, robust to influence order); if
        not every wired influence is present -- e.g. re-importing arm.ma into a
        scene that already has uparm_r_JNT renames the clash to uparm_r_JNT1 -- fall
        back to alignment BY ORDER (the JSON was extracted in the same
        influenceObjects order as this skin, preserved across the re-import copy).
        Returns None if the sets can't be aligned, so the caller uses the cylinder
        fallback instead of silently seeding all-zero weights (which would divide by
        zero in the DQS blend and collapse the mesh to NaN)."""
        d = json.load(open(path))
        j_infl = [n.rsplit("|", 1)[-1] for n in d["influences"]]
        Wj = np.asarray(d["weights"], dtype=np.float64)          # (N, Jjson)
        if all(sn in j_infl for sn in wired_short):
            return Wj[:, [j_infl.index(sn) for sn in wired_short]]
        if Wj.shape[1] == len(wired_short):
            return Wj.copy()            # order-aligned (same influenceObjects order)
        return None

    # --- locate the bundled arm + the two JSON weight sets -----------------
    arm = dqs_path = lbs_path = None
    try:
        from mpynode._common.util.template_gallery import _bundled_templates_root
        root = _bundled_templates_root() or ""
        cand = os.path.join(root, "MPyNode", "Ouch", "arm.ma")
        if os.path.isfile(cand):
            arm = cand
        expd = os.path.join(root, "MPySkinCluster", "Twist Swing Skin")
        dqs_path = os.path.join(expd, "DQS.json")
        lbs_path = os.path.join(expd, "LBS.json")
    except Exception:
        arm = None

    if arm and dqs_path and os.path.isfile(dqs_path) \\
            and lbs_path and os.path.isfile(lbs_path):
        new = mc.file(arm, i=True, ignoreVersion=True, returnNewNodes=True) or []
        skins = mc.ls(new, type="skinCluster") or []
        joints = mc.ls(new, type="joint", long=True) or []
        meshes = [m for m in (mc.ls(new, type="mesh", long=True) or [])
                  if not mc.getAttr(m + ".intermediateObject")]
        if skins and meshes:
            sc = skins[0]
            mesh_shape = meshes[0]
            mesh_xform = mc.listRelatives(mesh_shape, parent=True,
                                          fullPath=True)[0]
            elbow = (next((j for j in joints
                           if j.rsplit("|", 1)[-1] == "loarm_r_JNT"), None)
                     or next((j for j in joints if "loarm" in j), None))
            influences, nv, bind = _extract(sc, mesh_shape)
            wired_short = [i.rsplit("|", 1)[-1] for i in influences]
            twist_w = _load_json_weights(dqs_path, wired_short)   # DQS -> twist
            swing_w = _load_json_weights(lbs_path, wired_short)   # LBS -> swing
            if (twist_w is not None and swing_w is not None
                    and twist_w.shape[0] == nv and swing_w.shape[0] == nv):
                # Detach the stock skin -> the mesh reverts to its exact rest.
                mc.skinCluster(sc, e=True, unbind=True)
                if name not in (mc.listHistory(mesh_xform) or []):
                    mc.deformer(name, e=True, g=mesh_xform)
                for i, jnt in enumerate(influences):
                    mc.connectAttr(jnt + ".worldMatrix[0]",
                                   "%s.matrix[%d]" % (name, i), force=True)
                    if i in bind:
                        mc.setAttr("%s.bindPreMatrix[%d]" % (name, i), bind[i],
                                   type="matrix")
                # The two weight-set plugs the Compute deforms from (Live Result).
                _seed_plug("twistWeights", twist_w)
                _seed_plug("swingWeights", swing_w)
                # Seed the weightList scratchpad with the active (Twist) set.
                for v in range(nv):
                    for c in range(twist_w.shape[1]):
                        mc.setAttr("%s.weightList[%d].weights[%d]" % (name, v, c),
                                   float(twist_w[v, c]))
                if elbow:
                    for ax in ("rotateX", "rotateY", "rotateZ"):
                        for s in (mc.listConnections(elbow + "." + ax, s=True,
                                                     d=False, plugs=True) or []):
                            mc.disconnectAttr(s, elbow + "." + ax)
                        mc.setAttr(elbow + "." + ax, lock=False)
                    # Two sequences: first pure TWIST (rotateX 0->90 over 0-30),
                    # then add BEND (rotateY 0->90 over 30-90) -- isolating the DQS
                    # twist weights, then layering the LBS swing weights on top.
                    for f, rx in ((0, 0.0), (30, 90.0), (90, 90.0)):
                        mc.setKeyframe(elbow + ".rotateX", time=f, value=rx)
                    for f, ry in ((0, 0.0), (30, 0.0), (90, 90.0)):
                        mc.setKeyframe(elbow + ".rotateY", time=f, value=ry)
                    mc.playbackOptions(min=0, max=90)
                    mc.currentTime(90)
                try:
                    mc.select(mesh_xform, replace=True)
                    # This branch IMPORTED arm.ma -- frame the WHOLE scene so
                    # the imported rig can never land off screen.
                    for _panel in mc.getPanel(type="modelPanel") or []:
                        _cam = mc.modelEditor(_panel, query=True, camera=True)
                        if _cam:
                            mc.viewFit(_cam, allObjects=True)
                except Exception:
                    pass
                return name

    # --- fallback: a subdivided cylinder + 2-joint chain -------------------
    cyl = mc.polyCylinder(name="tswArm#", radius=1.0, height=6.0,
                          subdivisionsX=12, subdivisionsY=12)[0]
    mc.select(clear=True)
    j0 = mc.joint(name="tswBase#", position=(0.0, -3.0, 0.0))
    j1 = mc.joint(name="tswMid#", position=(0.0, 0.0, 0.0))
    mc.select(clear=True)

    nv = mc.polyEvaluate(cyl, vertex=True)
    ys = [mc.xform("%s.vtx[%d]" % (cyl, v), q=True, os=True, t=True)[1]
          for v in range(nv)]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    if name not in (mc.listHistory(cyl) or []):
        mc.deformer(name, e=True, g=cyl)
    for i, jnt in enumerate((j0, j1)):
        mc.connectAttr(jnt + ".worldMatrix[0]", "%s.matrix[%d]" % (name, i),
                       force=True)
        inv = mc.getAttr(jnt + ".worldInverseMatrix[0]")
        mc.setAttr("%s.bindPreMatrix[%d]" % (name, i), inv, type="matrix")

    # Two weight sets: a graded ramp (twist) + a sharper transition (swing).
    t = np.clip((np.array(ys) - lo) / span, 0.0, 1.0)
    twist_w = np.stack([1.0 - t, t], axis=1)
    ts = np.clip((t - 0.5) * 2.5 + 0.5, 0.0, 1.0)
    swing_w = np.stack([1.0 - ts, ts], axis=1)
    for v in range(nv):
        mc.setAttr("%s.weightList[%d].weights[0]" % (name, v),
                   float(twist_w[v, 0]))
        mc.setAttr("%s.weightList[%d].weights[1]" % (name, v),
                   float(twist_w[v, 1]))
    _seed_plug("twistWeights", twist_w)
    _seed_plug("swingWeights", swing_w)

    for f, rx in ((0, 0.0), (30, 90.0), (90, 90.0)):
        mc.setKeyframe(j1 + ".rotateX", time=f, value=rx)
    for f, rz in ((0, 0.0), (30, 0.0), (90, 90.0)):
        mc.setKeyframe(j1 + ".rotateZ", time=f, value=rz)
    mc.playbackOptions(min=0, max=90)
    mc.currentTime(90)
    try:
        mc.select(cyl, replace=True)
        for _panel in mc.getPanel(type="modelPanel") or []:
            _cam = mc.modelEditor(_panel, query=True, camera=True)
            if _cam:
                mc.viewFit(_cam, allObjects=True)
    except Exception:
        pass
    return name
'''

DESC = (
    "# Twist/Swing Skin (Two Weight Sets)\n\n"
    "A real skinCluster that carries two independent sets of skin weights "
    "instead of one. `twistWeights` drives a dual-quaternion twist pass "
    "around each bone's own axis; `swingWeights` drives a linear-blend swing "
    "(bend) pass. A normal skinCluster gives you a single `weightList`, so "
    "you cannot paint a tight twist falloff and a soft bend falloff on the "
    "same joint -- here you can, and the node still compiles to pure C++.\n\n"
    "`skinMode` picks what you are painting. `Paint LBS (Swing)` and `Paint "
    "DQS (Twist)` each load their set into `weightList`, so Paint Skin "
    "Weights and the Component Editor show it immediately, and your strokes "
    "bank straight back into that set. `Live Result`, the default, deforms "
    "from both sets at once. `twistAxis` chooses the bone-local twist axis. "
    "`self.sync_paint(mode)` carries that load-and-bank machinery; it is "
    "interactive-only, so the compiled node skips it and reads the two weight "
    "plugs directly.\n\n"
    "**Create + Run demo** skins the bundled two-bone arm, seeding "
    "`twistWeights` from `DQS.json` (a rigid twist falloff) and "
    "`swingWeights` from `LBS.json` (a smooth bend falloff). The elbow twists "
    "first, over frames 0-30, then bends over frames 30-90, so you see each "
    "set on its own.\n\n"
    "One caveat: the paint load and bank are deferred a frame for safety, so "
    "switching mode in the middle of a stroke can drop that stroke. Paint, "
    "pause, then switch.")
