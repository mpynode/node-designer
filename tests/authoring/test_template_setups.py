"""Functional check that every bundled demo template's ``def demo(self)`` builds
its whole tutorial through the REAL gallery path (_TemplateCreateCommand: create
-> apply template -> run the template's own demo).

Every mpynode demo now ships a SELF-CONTAINED demo: "Create + Run demo"
fabricates the entire scene (geometry + wiring + values) with NO selection and
the node evaluates without error. Each test runs the demo command, asserts the
scene was built and wired, and then DRIVES the node to prove the demo actually
animates (not just that connections landed). The unitSphereCollision deformer is
the lone SELECTION-DRIVEN exception: it keeps a ``def setup(self)`` (run via
"Create + Run setup" with a collider + mesh selected) and this suite verifies
that setup seeds a PERSISTENT object-space buffer and that the collision BAKES
(the dent stays once the collider moves away).
"""

import os
import unittest

import numpy as np
import maya.cmds as mc
import maya.api.OpenMaya as om

from tests._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import _TemplateCreateCommand, run_undoable
from mpynode._common.io.mpn_io import load_mpn
from mpynode._node_registry import wrap_node


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_TPL = os.path.join(os.environ["MPYNODE_ROOT"], "templates")


def _payload(rel):
    """Load a bundled template payload (decoding is safe: bundled = trusted)."""
    path = os.path.join(_TPL, *rel.split("/"), "template.mpn")
    data = load_mpn(path, trusted=True)
    return data, data.get("native_type")


def _create_with_setup(rel, selection):
    """Select ``selection`` (in order) then run the gallery Create + Run setup
    command. Returns the created node name."""
    payload, native_type = _payload(rel)
    mc.select(clear=True)
    if selection:
        mc.select(selection, replace=True)
    cmd  = _TemplateCreateCommand(payload, native_type, run_setup=True)
    name = run_undoable(cmd) or cmd.created_name
    if cmd.tier_failures.get("setup"):
        raise AssertionError("setup failed: %s" % cmd.tier_failures["setup"])
    return name


def _create_with_demo(rel, demo_name=None):
    """Run the gallery Create + Run demo command. A demo fabricates its OWN
    showcase scene, so there is NO selection. ``demo_name`` picks one of
    several demos (function name or label). Returns the created node name."""
    payload, native_type = _payload(rel)
    mc.select(clear=True)
    cmd = _TemplateCreateCommand(payload, native_type, run_demo=True,
                                 demo_name=demo_name)
    name = run_undoable(cmd) or cmd.created_name
    if cmd.tier_failures.get("demo"):
        raise AssertionError("demo failed: %s" % cmd.tier_failures["demo"])
    return name


def _draw_buf(loc, slot, time_value=0.0):
    """The first ``slot`` buffer in a locator's ordered draw command list."""
    for cmd in loc.evaluate_draw_commands(time_value)["commands"]:
        if cmd["slot"] == slot:
            return cmd["buffer"]
    return None


def _incoming(dst):
    return mc.listConnections(dst, source=True, destination=False, plugs=True) or []


def _driven_by(dst, src_node, src_attr):
    """True iff ``dst`` is driven by ``src_node.src_attr`` (element-tolerant)."""
    want = src_node + "." + src_attr
    return any(p == want or p.startswith(want + "[") for p in _incoming(dst))


class MpynodeExampleSetupsTest(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def _cubes(self, n):
        return [mc.polyCube()[0] for _ in range(n)]

    def test_bubble_sort_builds_grouped_cubes_and_drives_scaleY(self):
        # The redesigned setup is self-contained: it builds its OWN 100 cubes
        # (no selection needed), spaced 1 unit apart in X under a single group,
        # drives each cube's scaleY from one sort output, and puts the node in
        # Auto mode (reset=2) over a 1..100 range (maxVal=100).
        name = _create_with_demo("MPyNode/Bubble Sort")
        driven = sorted(set(mc.listConnections(
            name + ".sort", source=False, destination=True) or []))
        self.assertEqual(len(driven), 100, "setup should build 100 cubes")
        xs, parents = [], set()
        for c in driven:
            self.assertTrue(_driven_by(c + ".scaleY", name, "sort"),
                            "%s.scaleY not driven by %s.sort" % (c, name))
            xs.append(round(mc.getAttr(c + ".translateX"), 4))
            p = mc.listRelatives(c, parent=True)
            parents.add(p[0] if p else None)
        self.assertEqual(sorted(xs), [float(i) for i in range(100)])  # 1 unit apart
        self.assertEqual(len(parents), 1, "all cubes under one group")
        self.assertEqual(mc.getAttr(name + ".reset"), 2)              # Auto
        self.assertAlmostEqual(mc.getAttr(name + ".maxVal"), 100.0)

    def test_bubble_sort_demo_forces_reset_auto_and_maxval_off_default(self):
        # Discriminating: the grouped-cubes test above reads reset/maxVal on a
        # node whose TEMPLATE DEFAULTS are already 2/100, so it cannot tell
        # whether the demo's setAttr lines ran. Move both OFF the default, run
        # ONLY the demo, and assert it FORCED them back.
        from mpynode._common.io.mpn_io import deserialize_node
        from mpynode._common.methods.methods_registry import run_node_demo
        payload, _ = _payload("MPyNode/Bubble Sort")
        node = deserialize_node(payload, restore_persistent=False)
        name = node.get_name()
        mc.setAttr(name + ".reset", 0)      # away from default Auto(2)
        mc.setAttr(name + ".maxVal", 10.0)  # away from default 100
        run_node_demo(node)
        self.assertEqual(mc.getAttr(name + ".reset"), 2)
        self.assertAlmostEqual(mc.getAttr(name + ".maxVal"), 100.0)
        driven = set(mc.listConnections(
            name + ".sort", source=False, destination=True) or [])
        self.assertEqual(len(driven), 100)

    def test_bubble_sort_demo_undo_removes_node_and_all_cubes(self):
        # The demo fabricates 1 group + 100 cubes (a large blast radius); one
        # undo of the gallery command must remove the node AND every cube.
        before = set(mc.ls(type="transform"))
        name   = _create_with_demo("MPyNode/Bubble Sort")
        driven = mc.listConnections(
            name + ".sort", source=False, destination=True) or []
        self.assertEqual(len(set(driven)), 100)
        grp = mc.listRelatives(driven[0], parent=True)[0]
        self.assertEqual(len(mc.listRelatives(grp, children=True) or []), 100)
        mc.undo()
        self.assertFalse(mc.objExists(name), "node gone after undo")
        self.assertFalse(mc.objExists(grp), "cube group gone after undo")
        self.assertEqual(set(mc.ls(type="transform")), before,
                         "undo must leave no fabricated transforms")

    # ------------------------------------------------------------------
    # The remaining demos are SELF-CONTAINED: "Create + Run demo" builds
    # the whole tutorial scene with NO selection (each previously needed a
    # stored var -- board / velocity / pain / defaultLength -- that vanilla
    # templates strip). Every test drives the node to prove it animates.
    # ------------------------------------------------------------------
    def test_game_of_life_builds_mesh_of_cubes_and_simulates(self):
        # Game of Life is an mPyMesh (MPyMesh/Game Of Life): its demo
        # builds ONE render mesh fed by outMesh -- one cube (8 verts, 6 quads)
        # per LIVE cell -- seeds a 20x20 board and wires frame to the timeline.
        from mpynode._common.util import log_bus

        # Re-derive the SAME deterministic Conway board the Compute tier builds,
        # straight from the template's own init source, so we can assert the
        # EXACT per-cell topology each frame (one 8-vert / 6-quad cube per LIVE
        # cell) rather than merely "some multiple of 8".
        payload, _ = _payload("MPyMesh/Game Of Life")
        kern = {}
        exec(payload["init_source"], kern)
        gol_board = kern["_gol_board"]
        # Demo settings: 20x20 board, 120 samples, resetBoard left at default 0.
        # _gol_board(h=boardY, w=boardX, samples, frame, reset) -- match Compute.
        expected_alive = {
            t: int(np.count_nonzero(gol_board(20, 20, 120, t, 0)))
            for t in (1, 2, 3, 4, 5, 6)
        }

        name  = _create_with_demo("MPyMesh/Game Of Life")
        shape = name + "RenderShape"
        self.assertTrue(mc.objExists(shape), "demo should build a render mesh")
        self.assertTrue(_driven_by(shape + ".inMesh", name, "outMesh"),
                        "render mesh not fed by outMesh")
        # the demo seeds a lively 20x20 board and leaves resetBoard off
        self.assertEqual(mc.getAttr(name + ".boardX"),        20)
        self.assertEqual(mc.getAttr(name + ".boardY"),        20)
        self.assertEqual(mc.getAttr(name + ".randomSamples"), 120)
        self.assertEqual(mc.getAttr(name + ".resetBoard"),    0)
        self.assertTrue(_incoming(name + ".frame"), "frame not wired to time")

        def mesh_counts(t):
            mc.currentTime(t)
            mc.dgeval(shape + ".outMesh")
            sel = om.MSelectionList()
            sel.add(shape)
            fn = om.MFnMesh(sel.getDagPath(0))
            return fn.numVertices, fn.numPolygons

        # A Compute error ships an EMPTY mesh WITHOUT raising, so a broken frame
        # would masquerade as "a different mesh" (a bare vert-count delta cannot
        # tell a crash from an evolution). Guard the whole sweep with a log_bus
        # subscription and assert NO expression error is broadcast.
        class _Sink(object):
            def __init__(self):
                self.errors = []

            def append_message(self, message, level):
                if level == "error" or "expression error" in message:
                    self.errors.append(message)

        sink = _Sink()
        log_bus.subscribe(sink)
        try:
            verts = []
            for t in (1, 2, 3, 4, 5, 6):
                alive = expected_alive[t]
                # the demo board is never all-dead across these frames, so a
                # zero here would mean a broken (not merely empty) compute.
                self.assertGreater(alive, 0,
                                   "demo board unexpectedly all-dead at frame %d"
                                   % t)
                nv, npoly = mesh_counts(t)
                # ONE cube per LIVE cell: exactly 8 verts and 6 quads each.
                self.assertEqual(nv, 8 * alive,
                                 "frame %d: %d verts != 8 * %d live cells"
                                 % (t, nv, alive))
                self.assertEqual(npoly, 6 * alive,
                                 "frame %d: %d polys != 6 * %d live cells"
                                 % (t, npoly, alive))
                verts.append(nv)
        finally:
            log_bus.unsubscribe(sink)

        self.assertFalse(sink.errors,
                         "compute broadcast an expression error while scrubbing "
                         "the timeline: %s" % sink.errors)
        # the board actually EVOLVES across frames (not a frozen mesh).
        self.assertGreater(len(set(verts)), 1,
                           "simulation did not advance with time")

    def test_voxelize_builds_hollow_shell_of_cubes_from_input_mesh(self):
        # Voxelize is an mPyMesh (MPyMesh/Voxelize): its demo builds a
        # radius-5 poly sphere, wires it into inMesh, and feeds one render mesh
        # from outMesh -- one cube per occupied grid cell. The shell is HOLLOW
        # by construction, so the sphere's interior must contain no voxels.
        from mpynode._common.util import log_bus

        name = _create_with_demo("MPyMesh/Voxelize")
        tr   = name + "_voxels"
        self.assertTrue(mc.objExists(tr), "demo should build a voxel mesh")
        shape = mc.listRelatives(tr, shapes=True, fullPath=True)[0]
        self.assertTrue(_driven_by(shape + ".inMesh", name, "outMesh"),
                        "voxel mesh not fed by outMesh")
        self.assertTrue(_incoming(name + ".inMesh"),
                        "setup did not wire the source mesh into inMesh")
        self.assertAlmostEqual(mc.getAttr(name + ".voxelSize"), 1.0, places=6)

        # A colour set nothing draws is useless, so setup must switch
        # displayColors on for the render mesh it builds.
        self.assertTrue(mc.getAttr(shape + ".displayColors"),
                        "setup must enable displayColors on the render mesh")

        # ...and it seeds the shipped sample texture as a RELATIVE path, so the
        # template paints wherever mpynode's templates happen to be installed.
        # An absolute path here would only work on the machine that built it.
        seeded = mc.getAttr(name + ".textureFile") or ""
        self.assertFalse(os.path.isabs(seeded),
                         "the seeded texture must be RELATIVE, got %r" % seeded)
        self.assertTrue(seeded.endswith("test_grid.png"),
                        "setup should seed the shipped sample texture, got %r"
                        % seeded)

        def counts():
            # An EMPTY outMesh (what the maxVoxels brake ships) is rejected by
            # the MFnMesh constructor outright, so that reads as zero cubes.
            mc.dgeval(shape + ".outMesh")
            sel = om.MSelectionList()
            sel.add(shape)
            try:
                fn = om.MFnMesh(sel.getDagPath(0))
            except Exception:
                return 0, 0
            return fn.numVertices, fn.numPolygons

        def points():
            sel = om.MSelectionList()
            sel.add(shape)
            return om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kObject)

        # A Compute error ships an EMPTY mesh WITHOUT raising, so a broken
        # sample mode would masquerade as "fewer voxels". Guard the sweep and
        # assert nothing is broadcast.
        class _Sink(object):
            def __init__(self):
                self.errors = []

            def append_message(self, message, level):
                if level == "error" or "expression error" in message:
                    self.errors.append(message)

        sink = _Sink()
        log_bus.subscribe(sink)
        try:
            nv, npoly = counts()
            self.assertGreater(nv, 0, "voxelize produced no voxels")
            self.assertEqual(nv % 8, 0, "%d verts is not a whole cube count" % nv)
            self.assertEqual(npoly % 6, 0, "%d polys is not whole cubes" % npoly)
            self.assertEqual(nv // 8, npoly // 6,
                             "vert/poly cube counts disagree (%d vs %d)"
                             % (nv // 8, npoly // 6))
            fine = nv // 8

            # Every voxel vertex sits inside the source bbox. Cells are half-open
            # [i*vs, (i+1)*vs), so a sample landing exactly on the high face
            # falls into the next cell up -- one voxel of legal overhang.
            pts = points()
            lo, hi = -5.0 - 1.0 - 1e-4, 5.0 + 1.0 + 1e-4
            self.assertTrue(
                all(lo <= p[i] <= hi for p in pts for i in range(3)),
                "voxels escaped the source bounds")

            # WORLD-anchored lattice with a cube CORNER on the origin: every
            # cube vertex is an exact integer multiple of voxelSize. This is the
            # property that stops the voxels swimming when the source moves.
            vs = mc.getAttr(name + ".voxelSize")
            worst = max(abs(p[i] / vs - round(p[i] / vs))
                        for p in pts for i in range(3))
            self.assertLess(worst, 1e-6,
                            "cube vertices must land on the world voxel lattice "
                            "(worst offset %.9f of a cell)" % worst)

            # HOLLOW: the sphere's interior is empty. The innermost shell face
            # sits near radius 4, so nothing may come within 3 units of centre.
            nearest = min((p[0] ** 2 + p[1] ** 2 + p[2] ** 2) ** 0.5 for p in pts)
            self.assertGreater(nearest, 3.0,
                               "shell is not hollow -- a voxel reached %.3f "
                               "from the sphere centre" % nearest)

            # Coarser voxels never yield MORE cubes.
            mc.setAttr(name + ".voxelSize", 2.5)
            coarse = counts()[0] // 8
            self.assertGreater(coarse, 0, "coarse voxelSize produced no voxels")
            self.assertLessEqual(coarse, fine,
                                 "coarser voxels increased the count "
                                 "(%d > %d)" % (coarse, fine))
            mc.setAttr(name + ".voxelSize", 1.0)

            # Colour chain. Bytes 0 and 255 are exact fixed points of the sRGB
            # EOTF, so a solid-red image must land as exactly (1, 0, 0).
            import tempfile
            tex = os.path.join(tempfile.gettempdir(),
                               "mpy_voxelize_repotest.png")
            im = om.MImage()
            im.create(4, 4, 4, om.MImage.kByte)
            im.setPixels(bytes(bytearray([255, 0, 0, 255] * 16)), 4, 4)
            im.writeToFile(tex, "png")

            def colors():
                # Copy the floats out while the MColorArray is still alive --
                # its MColor objects dangle once the array is freed.
                mc.dgeval(shape + ".outMesh")
                sel2 = om.MSelectionList()
                sel2.add(shape)
                arr = om.MFnMesh(sel2.getDagPath(0)).getVertexColors()
                return [(arr[i].r, arr[i].g, arr[i].b) for i in range(len(arr))]

            # The path setup SEEDED must actually resolve and paint. More than
            # one colour proves the file was found through the template search
            # roots and sampled through the source UVs -- a relative path that
            # failed to resolve would silently fall through to defaultColor.
            self.assertGreater(
                len(set((round(r, 4), round(g, 4), round(b, 4))
                        for r, g, b in colors())), 1,
                "the seeded relative textureFile did not resolve and paint")

            mc.setAttr(name + ".defaultColor", 0.25, 0.5, 0.75, type="double3")
            mc.setAttr(name + ".textureFile", tex, type="string")
            cols = colors()
            self.assertTrue(
                cols and all(abs(r - 1.0) < 1e-4 and abs(g) < 1e-4
                             and abs(b) < 1e-4 for r, g, b in cols),
                "a solid-red texture must paint every cube red")

            # A blank path is a FALLBACK, not an error: the demo sphere has no
            # vertex colours, so the chain must reach defaultColor.
            mc.setAttr(name + ".textureFile", "", type="string")
            cols = colors()
            self.assertTrue(
                cols and all(abs(r - 0.25) < 1e-4 and abs(g - 0.5) < 1e-4
                             and abs(b - 0.75) < 1e-4 for r, g, b in cols),
                "a blank textureFile must fall back to defaultColor")
        finally:
            log_bus.unsubscribe(sink)

        self.assertFalse(sink.errors,
                         "compute broadcast an expression error while "
                         "voxelizing: %s" % sink.errors)

        # The maxVoxels brake fires on the GRID rather than letting a runaway
        # cubic sweep run -- and the node RECOVERS once the cap is raised.
        # (This deliberately errors, so it runs outside the log_bus guard.)
        mc.setAttr(name + ".maxVoxels", 4)
        self.assertEqual(counts()[0], 0, "maxVoxels brake did not fire")
        mc.setAttr(name + ".maxVoxels", 20000)
        self.assertGreater(counts()[0], 0, "node did not recover after the brake")

    def test_metaballs_builds_text_and_csg_blob(self):
        # Metaballs is an mPyMesh (MPyMesh/Metaballs): its demo builds
        # "MPyNode" as one SDF dual-marching-cubes mesh (26 hard-union boxes)
        # plus a Cube/Sphere/Cylinder blob below it -- each primitive folded
        # into the single outMesh with a DIFFERENT CSG op.
        from mpynode._common.util import log_bus

        sink_errs = []

        class _Sink(object):
            def append_message(self, message, level):
                if level == "error" or "expression error" in message:
                    sink_errs.append(message)

        def verts():
            mc.dgeval(shape + ".outMesh")
            sel = om.MSelectionList()
            sel.add(shape)
            try:
                return om.MFnMesh(sel.getDagPath(0)).numVertices
            except Exception:
                return 0     # empty (degenerate) mesh -> MFnMesh refuses; 0

        # Keep the log sink subscribed across the WHOLE sweep -- creation AND the
        # additive toggle recompute below -- so a compute error that ships an
        # EMPTY mesh WITHOUT raising (sdf_dmc returns 0 verts on a degenerate
        # field) can't masquerade as a valid result on either eval.
        sink = _Sink()
        log_bus.subscribe(sink)
        try:
            name  = _create_with_demo("MPyMesh/Metaballs")
            shape = name + "RenderShape"
            self.assertTrue(mc.objExists(shape),
                            "demo should build a render mesh")
            self.assertTrue(_driven_by(shape + ".inMesh", name, "outMesh"),
                            "render mesh not fed by outMesh")

            # 26 text strokes under <name>Text; 3 blob prims under <name>Shapes.
            text_kids = mc.listRelatives(name + "Text", children=True,
                                         type="transform") or []
            shape_kids = mc.listRelatives(name + "Shapes", children=True,
                                          type="transform") or []
            self.assertEqual(len(text_kids), 26, "expected 26 MPyNode strokes")
            self.assertEqual(len(shape_kids), 3,
                             "expected Cube/Sphere/Cylinder")

            # Fold stream: 26 boxes + cube(type 1) sphere(type 0) cylinder(type
            # 2); cube & sphere additive, cylinder subtracted; sphere smoothed.
            self.assertEqual(mc.getAttr(name + ".shapeMatrix", size=True), 29)
            self.assertEqual(
                [mc.getAttr("%s.shapeType[%d]" % (name, i))
                 for i in (26, 27, 28)], [1, 0, 2])
            self.assertEqual(
                [mc.getAttr("%s.additive[%d]" % (name, i))
                 for i in (26, 27, 28)], [1, 1, 0])
            self.assertGreater(mc.getAttr(name + ".smoothing[27]"), 0.0,
                               "metaball sphere must carry a smooth-union blend")

            v_carved = verts()
            self.assertGreater(v_carved, 0, "demo produced an empty mesh")

            # Prove the difference op genuinely CARVES: flip the cylinder to
            # additive so it FILLS a solid rod instead of boring a tunnel. The
            # carved mesh must have MORE vertices -- the through-tunnel adds
            # interior wall surface the filled solid lacks. A difference op
            # degraded to a no-op or a union would make v_carved <= v_filled.
            mc.setAttr(name + ".additive[28]", 1)
            v_filled = verts()
            mc.setAttr(name + ".additive[28]", 0)
            self.assertGreater(v_filled, 0,
                               "filling the tunnel produced an empty mesh")
            self.assertGreater(
                v_carved, v_filled,
                "difference op did not carve a tunnel (carved=%d filled=%d)"
                % (v_carved, v_filled))
        finally:
            log_bus.unsubscribe(sink)

        self.assertFalse(sink_errs,
                         "compute broadcast an expression error: %s" % sink_errs)

    def test_metaballs_demo_survives_a_scene_round_trip(self):
        # A saved Metaballs scene must rebuild the SAME mesh it was saved from.
        # The demo bores its cylinder along X by setting axis[28] = 0, and Maya
        # omits any multi element whose value equals the attribute default -- so
        # while the axis default DISAGREED with the default the compute itself
        # overlays (_dense_over(self.axis, np.ones(n)) == 1 == Y), that lone
        # element vanished from the .ma and the reopened scene silently re-bored
        # the cylinder along Y (9918 verts saved -> 10066 reopened).
        import tempfile

        name  = _create_with_demo("MPyMesh/Metaballs")
        shape = name + "RenderShape"

        def verts():
            mc.dgeval(shape + ".outMesh")
            sel = om.MSelectionList()
            sel.add(shape)
            return om.MFnMesh(sel.getDagPath(0)).numVertices

        saved = verts()
        self.assertGreater(saved, 0, "demo produced an empty mesh")

        ma = os.path.join(tempfile.mkdtemp(), "metaballs_round_trip.ma")
        mc.file(rename=ma)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(new=True, force=True)
        mc.file(ma, open=True, force=True)

        self.assertEqual(
            verts(), saved,
            "reopening the saved demo built different geometry -- an authored "
            "shape-stream value did not survive the .ma round trip")

    def test_mesh_regions_builds_one_locator_per_component_tag(self):
        # The bundled head.ma ships EIGHT component tags (the mouth regions);
        # the Mesh Regions demo must build ONE mPyLocator gizmo
        # PER tag (eight tags -> eight locators), each bound to the head mesh and
        # drawing its own single region in a distinct palette colour.
        before = set(mc.ls(type="mPyLocator", long=True) or [])
        _create_with_demo("MPyLocator/Mesh Regions")
        locs = sorted(set(mc.ls(type="mPyLocator", long=True) or []) - before)
        self.assertEqual(len(locs), 8,
                         "eight component tags must yield eight locators, got %r"
                         % locs)
        node_colors = []
        for loc in locs:
            self.assertTrue(
                mc.listConnections(loc + ".inMesh", source=True,
                                   destination=False) or [],
                "%s.inMesh not wired to the head mesh" % loc)
            w = wrap_node(loc, "mPyLocator")
            self.assertIsNotNone(w, "could not wrap %s" % loc)
            poly = _draw_buf(w, "polygons")
            self.assertIsNotNone(poly, "%s drew nothing" % loc)
            fcol = np.asarray(poly["face_colors"])
            self.assertGreater(fcol.shape[0], 0, "%s has no face colours" % loc)
            # one region per node -> every face shares the node's colour
            node_colors.append(tuple(np.round(fcol[0], 4)))

            # Issue 3: each gizmo transform is moved to the CENTROID of its
            # region's verts (so the widget hugs the faces it draws), and the
            # referenced head mesh is made unselectable.
            pts = np.asarray(poly["points"], dtype=float)[:, :3]
            self.assertGreater(pts.shape[0], 0, "%s has no region points" % loc)
            centroid = pts.mean(axis=0)
            tf       = mc.listRelatives(loc, parent=True, fullPath=True)[0]
            tf_pos   = np.array(mc.xform(tf, q=True, ws=True, t=True), dtype=float)
            diag     = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0)))
            self.assertLess(
                float(np.linalg.norm(tf_pos - centroid)), 0.25 * diag + 1e-3,
                "%s not positioned at its region centroid (tf=%r centroid=%r)"
                % (loc, tf_pos, centroid))
            # unselectable = overrideEnabled + reference display (unpickable)
            for m in (mc.listConnections(loc + ".inMesh", source=True,
                                         destination=False, shapes=True) or []):
                self.assertTrue(
                    mc.getAttr(m + ".overrideEnabled"),
                    "%s override not enabled (mesh should be unselectable)" % m)
                self.assertEqual(
                    mc.getAttr(m + ".overrideDisplayType"), 2,
                    "%s not set to reference display (unpickable)" % m)
        self.assertEqual(
            len(set(node_colors)), 8,
            "the eight region gizmos must draw in distinct colours, got %r"
            % (node_colors,))

    def test_animated_text_idle_animates_on_wall_clock(self):
        # Issue 2: the Animated Text gizmo froze when the timeline was idle. The
        # fix adds a wall-clock drift term to the gizmo's compute so it keeps
        # moving even when the frame does not change -- matching the original
        # .ma example. Two evaluations at the SAME frame (a still timeline) must
        # therefore differ.
        import time
        name = _create_with_demo("MPyLocator/Animated Text")
        w    = wrap_node(name, "mPyLocator")
        self.assertIsNotNone(w, "could not wrap %s" % name)
        a = np.asarray(_draw_buf(w, "text")["positions"])
        time.sleep(0.06)
        b = np.asarray(_draw_buf(w, "text")["positions"])
        self.assertGreater(a.shape[0], 0, "text gizmo drew no glyph positions")
        self.assertEqual(a.shape, b.shape, "glyph count changed between evals")
        self.assertFalse(
            np.allclose(a, b),
            "text gizmo must keep animating on an idle timeline (wall-clock "
            "drift); same-frame evaluations were identical")

    def test_hex_attribute_builds_draggable_text_parent(self):
        # The control you drag is now the text mesh's PARENT transform: its
        # translate feeds inPosition and the rendered text lives under it, so
        # dragging the (extruded, thick) text re-labels itself.
        name = _create_with_demo("MPyNode/Hex Attribute")
        src = mc.listConnections(name + ".inPosition", source=True,
                                 destination=False, plugs=True) or []
        self.assertTrue(src, "inPosition not wired to a drag control")
        drag_attr = src[0]
        self.assertTrue(drag_attr.endswith(".translate"),
                        "inPosition should be driven by a transform's "
                        "translate (the drag parent): %r" % drag_attr)
        drag = drag_attr.split(".")[0]
        out  = mc.getAttr(name + ".output")
        self.assertTrue(out and all(len(tok) == 2 for tok in out.split()),
                        "output is not a space-separated hex string: %r" % out)
        # The output is declared a `hex` attr: the expression writes plain text
        # and the attr auto-encodes to space-separated UTF-8 hex. If it were a
        # plain `string` the expression would have to encode by hand.
        out_type = wrap_node(name, "mPyNode").get_output_attr_map()["output"]["attr_type"]
        self.assertEqual(out_type, "hex",
                         "output should be a hex attr, got %r" % out_type)
        if mc.pluginInfo("Type", query=True, loaded=True):
            dst = mc.listConnections(
                name + ".output", source=False, destination=True) or []
            self.assertTrue(any(mc.nodeType(t) == "type" for t in dst),
                            "output not feeding a type node")
            # thickness: the text is built through a typeExtrude with extrusion on
            extrudes = mc.ls(type="typeExtrude") or []
            self.assertTrue(extrudes, "no typeExtrude -> text has no thickness")
            self.assertEqual(mc.getAttr(extrudes[0] + ".enableExtrusion"), 1)
            self.assertGreater(mc.getAttr(extrudes[0] + ".extrudeDistance"), 0.0)
            # the rendered mesh is a CHILD of the draggable transform, built
            # through the extrude
            meshes = mc.listRelatives(drag, allDescendents=True, type="mesh",
                                      fullPath=True) or []
            self.assertTrue(meshes,
                            "text mesh is not a child of the drag transform")
            hist = mc.listHistory(meshes[0]) or []
            self.assertTrue(any(mc.nodeType(h) == "typeExtrude" for h in hist),
                            "text mesh not built through typeExtrude")
        # drive: moving the drag control changes the encoded output
        before = mc.getAttr(name + ".output")
        mc.setAttr(drag + ".translate", 7.0, 8.0, 9.0, type="double3")
        mc.dgdirty(name)
        self.assertNotEqual(before, mc.getAttr(name + ".output"),
                            "dragging the control did not change output")

    def test_ouch_builds_arm_and_colours_geo(self):
        from mpynode._common.util import log_bus
        name = _create_with_demo("MPyNode/Ouch")
        ang = mc.listConnections(name + ".angle", source=True,
                                 destination=False, plugs=True) or []
        self.assertTrue(ang, "angle has no joint driver")
        self.assertTrue(mc.listConnections(name + ".color", source=False,
                                           destination=True),
                        "color output drives no shader")
        elbow      = ang[0].split(".")[0]
        elbow_attr = ang[0]
        # the demo reuses the bundled SKINNED arm (joint elbow + a skinCluster),
        # not a bare cube.
        self.assertEqual(mc.nodeType(elbow), "joint", "angle not driven by a joint")
        self.assertTrue(mc.ls(type="skinCluster"),
                        "skinned arm not imported (no skinCluster)")
        # audio is baked PERSISTENTLY onto the node (bytes live on the node, not
        # just a filepath), so the clip travels with the scene. audioData is the
        # SINGLE source of truth for playback.
        node = wrap_node(name, "mPyNode")
        self.assertIn("audioData", node.get_variable_names())
        self.assertTrue(node.is_variable_persistent("audioData"))
        data = node.get_variables().get("audioData")
        self.assertTrue(data and len(data) > 1000,
                        "audio bytes not baked onto the node")
        # exactly ONE audio buffer: the redundant session mirror (self.sample)
        # is gone -- audioData (a WAV container) is itself what the Variables /
        # Watch tab auto-renders as a waveform, so no second copy is needed.
        self.assertNotIn("sample", node.get_variable_names(),
                         "duplicate audio buffer (self.sample) should be gone")
        # audioData is the ONLY persistent var now: audioPath is a temporary
        # runtime guard the Compute tab seeds, and the file-identity audioSig var
        # is retired (the player keys on audioData's content, not a file sig).
        persistent_vars = [n for n in node.get_variable_names()
                           if node.is_variable_persistent(n)]
        self.assertEqual(persistent_vars, ["audioData"],
                         "audioData must be the only persistent var "
                         "(audioPath temporary, audioSig retired): %s"
                         % persistent_vars)
        self.assertNotIn("audioSig", node.get_variable_names(),
                         "audioSig should be retired (player keys on audioData)")

        class _Sink(object):
            def __init__(self):
                self.errors = []

            def append_message(self, message, level):
                if level == "error" or "expression error" in message:
                    self.errors.append(message)

        # Straighten the elbow FIRST (bend axis -> 0, BELOW the ~9.5deg
        # threshold) so the RED branch -- the one that READS self.pain -- runs
        # on the node's FIRST eval, before a green-branch write could seed pain.
        # A vanilla node with the seed reverted raises AttributeError here (and
        # getAttr would mask it), so assert NO expression error was broadcast.
        sink = _Sink()
        log_bus.subscribe(sink)
        try:
            mc.setAttr(elbow_attr, 0)        # straighten on the actual bend axis
            mc.dgdirty(name)
            red = mc.getAttr(name + ".color")[0]
        finally:
            log_bus.unsubscribe(sink)
        self.assertFalse(sink.errors,
                         "ouch red branch logged an expression error "
                         "(self.pain not seeded on a vanilla node?): %s"
                         % sink.errors)
        # Bend it past the threshold (45 deg) -> GREEN.
        mc.setAttr(elbow_attr, 45)
        mc.dgdirty(name)
        green = mc.getAttr(name + ".color")[0]
        self.assertGreater(red[0], red[1], "straightened arm should be red")
        self.assertGreater(green[1], green[0], "bent arm should be green")

        # Loading lives in COMPUTE (not just Init): re-pointing audioFile at a
        # different clip at runtime reloads the buffer live -- gated by the
        # temporary audioPath guard -- without reopening the scene. This is the
        # regression guard for "compute checks for a path change and reloads".
        import tempfile
        import wave as _wave
        new_wav = os.path.join(tempfile.gettempdir(), "ouch_test_swap.wav")
        _w      = _wave.open(new_wav, "wb")
        _w.setnchannels(1)
        _w.setsampwidth(1)
        _w.setframerate(22050)
        _w.writeframes(bytes([200]) * 1234)   # size + content differ from ouch.wav
        _w.close()
        with open(new_wav, "rb") as _fh:
            new_bytes = _fh.read()
        mc.setAttr(name + ".audioFile", new_wav, type="string")
        mc.dgdirty(name)
        mc.getAttr(name + ".color")           # triggers compute -> reload
        v = node.get_variables()
        self.assertEqual(v.get("audioPath"), new_wav,
                         "compute did not track audioPath on a live clip swap")
        self.assertEqual(bytes(v.get("audioData") or b""), new_bytes,
                         "compute did not load the new clip bytes into the buffer")
        # audioPath stays a TEMPORARY guard even after being written in compute:
        # re-assigning it must never promote it to a persistent var.
        self.assertFalse(node.is_variable_persistent("audioPath"),
                         "audioPath must remain temporary after a compute write")

        # THE reported-bug regression: the player follows self.audioData, NOT
        # audioFile. A manual load straight into the buffer (what the right-click
        # "Load media" action does) must NOT be clobbered by the disk-reload
        # path -- audioFile still resolves to the last path we loaded (== the
        # audioPath guard), so compute must leave the manual bytes alone.
        import hashlib as _hl
        manual = bytes([123]) * 2222          # distinct from new_wav's bytes
        node.set_variable("audioData", manual, persistent=True)
        mc.dgdirty(name)
        mc.getAttr(name + ".color")           # compute must NOT re-read new_wav
        after = node.get_variables()
        self.assertEqual(bytes(after.get("audioData") or b""), manual,
                         "manual audioData load was clobbered by the disk reload")
        # ...and the player was REBUILT to match the manual bytes: the rebuild
        # latch is a hash of audioData's CONTENT (not a file signature), which is
        # exactly what makes a right-click "Load media" actually play the new
        # clip. (Under the old file-signature gating this stayed the OLD sig.)
        self.assertEqual(after.get("_player_sig"), _hl.md5(manual).hexdigest(),
                         "player not rebuilt to match manually-loaded audioData")

    def _spine_parts(self, name):
        """(controls, riders) in index order: controlMatrices[k]'s source and
        outputTranslate[i]'s destination."""
        controls = [(mc.listConnections("%s.controlMatrices[%d]" % (name, k), source=True,
                                        destination=False) or [None])[0]
                    for k in mc.getAttr(name + ".controlMatrices", multiIndices=True) or []]
        riders = [(mc.listConnections("%s.outputTranslate[%d]" % (name, i), source=False,
                                      destination=True) or [None])[0]
                  for i in mc.getAttr(name + ".outputTranslate", multiIndices=True) or []]
        return controls, riders

    def _assert_spine_wired(self, name, n_controls, n_riders, rider_type):
        # The node builds its own B-spline: no curve input, one control matrix
        # per control, and every rider driven by the three per-sample outputs.
        self.assertFalse(mc.attributeQuery("inputCurve", node=name, exists=True),
                         "Spine v2 has no curve input")
        controls, riders = self._spine_parts(name)
        self.assertEqual(len(set(controls)), n_controls, "controlMatrices not fed per control")
        self.assertEqual(len(riders), n_riders)
        for r in riders:
            self.assertEqual(mc.nodeType(r), rider_type, "rider %s is not a %s" % (r, rider_type))
            self.assertTrue(_driven_by(r + ".translate", name, "outputTranslate"))
            self.assertTrue(_driven_by(r + ".rotate", name, "outputRotate"))
            self.assertTrue(_driven_by(r + ".scale", name, "outputScale"))
        # the build captured the rest pose
        self.assertTrue(mc.getAttr(name + ".restValid"), "rest data not captured")
        self.assertAlmostEqual(mc.getAttr(name + ".defaultLength"),
                               mc.getAttr(name + ".currentLength"), places=6)
        return controls, riders

    def _assert_spine_demo_look(self, controls, riders):
        # The demos show locator CONTROLS driving CUBE riders and build no Maya
        # curve: the node builds its own B-spline, and a display curve would
        # read as if one fed it.
        for c in controls:
            self.assertTrue(mc.listRelatives(c, shapes=True, type="locator"),
                            "control %s is not a locator" % c)
        for r in riders:
            self.assertTrue(mc.listRelatives(r, shapes=True, type="mesh"),
                            "rider %s is not a cube" % r)
            self.assertFalse(mc.listRelatives(r, shapes=True, type="locator"),
                             "rider %s is a locator" % r)
        self.assertEqual(mc.ls(type="nurbsCurve"), [], "a demo built a curve")
        self.assertEqual(mc.ls(type="decomposeMatrix"), [], "a demo bridged a curve")

    def test_spine_demo_builds_controls_and_cube_riders(self):
        # Four control locators up Y feed controlMatrices through the
        # spineBuildSystem command; twelve CUBES ride the per-sample outputs.
        name = _create_with_demo("MPyNode/Spine")
        self.assertEqual(mc.getAttr(name + ".curveAimAxis"), 1, "aim axis not Y")
        self.assertEqual(mc.getAttr(name + ".curveUpAxis"), 2, "up axis not Z")
        controls, riders = self._assert_spine_wired(name, 4, 12, "transform")
        self._assert_spine_demo_look(controls, riders)
        # riders spread up Y, and follow a control
        ys = [mc.getAttr(r + ".translateY") for r in riders]
        self.assertGreater(ys[-1] - ys[0], 8.0, "riders not spread up the Y-axis spine")
        mc.setAttr(controls[-1] + ".translateY", 12.0)
        self.assertAlmostEqual(mc.getAttr(riders[-1] + ".translateY"), 12.0, places=4,
                               msg="tip rider does not follow the tip control")

    def test_spine_twist_squash_demo_drives_from_chosen_controls(self):
        # Only the two end controls drive the twist (the top one turned 90
        # degrees) and controls 0 / 2 / 4 drive the scale (2 fattened).
        name = _create_with_demo("MPyNode/Spine", "demo_twist_squash")
        controls, riders = self._assert_spine_wired(name, 5, 16, "transform")
        self._assert_spine_demo_look(controls, riders)
        self.assertEqual(mc.getAttr(name + ".rotateMode"), 1, "rotate not Flagged")
        self.assertEqual(mc.getAttr(name + ".scaleMode"), 1, "scale not Flagged")
        self.assertEqual([bool(v) for v in mc.getAttr(name + ".rotateFlags")[0]],
                         [True, False, False, False, True])
        self.assertEqual([bool(v) for v in mc.getAttr(name + ".scaleFlags")[0]],
                         [True, False, True, False, True])
        tip  = mc.xform(riders[-1], q=True, ws=True, matrix=True)[8:11]
        ctrl = mc.xform(controls[-1], q=True, ws=True, matrix=True)[8:11]
        norm = sum(v * v for v in tip) ** 0.5
        self.assertGreater(sum(a * b for a, b in zip(tip, ctrl)) / norm, 0.95,
                           "tip rider does not take the tip control's twist")
        sx = [mc.getAttr(r + ".scaleX") for r in riders]
        self.assertGreater(max(sx), 1.6, "middle of the chain does not bulge")
        self.assertAlmostEqual(sx[0], 1.0, places=6)
        self.assertAlmostEqual(sx[-1], 1.0, places=6)

    def test_spine_closed_loop_demo_registers_on_the_first_control(self):
        # Six controls on a circle, closed curve: rider 0 sits where control 0
        # pulls hardest -- (P5 + 4 P0 + P1) / 6 for degree 3.
        name = _create_with_demo("MPyNode/Spine", "demo_closed_loop")
        controls, riders = self._assert_spine_wired(name, 6, 24, "transform")
        self._assert_spine_demo_look(controls, riders)
        self.assertTrue(mc.getAttr(name + ".periodic"), "loop is not closed")
        P    = [mc.xform(c, q=True, ws=True, t=True) for c in controls]
        want = [(P[5][k] + 4.0 * P[0][k] + P[1][k]) / 6.0 for k in range(3)]
        got  = mc.xform(riders[0], q=True, ws=True, t=True)
        for k in range(3):
            self.assertAlmostEqual(got[k], want[k], places=5)

    def test_spine_setup_builds_from_selected_transforms(self):
        # Selection-driven setup: pick >=2 transforms in order, Create + Run
        # setup -> the spineBuildSystem command builds a spine driven by exactly
        # those transforms with the default n=10 joint riders.
        locs = []
        for i, y in enumerate((0.0, 3.0, 6.0, 9.0)):
            loc = mc.spaceLocator(name="spineDrv%d" % i)[0]
            mc.setAttr(loc + ".translate", 0.0, y, 0.0, type="double3")
            locs.append(loc)
        name = _create_with_setup("MPyNode/Spine", locs)
        controls, riders = self._assert_spine_wired(name, 4, 10, "joint")
        self.assertEqual(controls, locs,
                         "controlMatrices must be driven by the selected transforms, in order")
        ys = [mc.getAttr(r + ".translateY") for r in riders]
        self.assertGreater(ys[-1] - ys[0], 8.0, "riders not spread up the Y-axis spine")

    def test_spline_builds_controls_and_samples(self):
        name = _create_with_demo("MPyNode/De Boor Spline")
        self.assertTrue(mc.objExists(name + "_controls"))
        self.assertEqual(len(mc.listConnections(
            name + ".cv", source=True, destination=False) or []), 5)
        samples = sorted(set(mc.listConnections(
            name + ".samples", source=False, destination=True) or []))
        self.assertEqual(len(samples), 24)
        for s in samples:
            self.assertTrue(_driven_by(s + ".translate", name, "samples"))
        mc.dgdirty(name)
        xs = [mc.getAttr(s + ".translateX") for s in samples]
        self.assertGreater(max(xs) - min(xs), 1.0,
                           "samples not spread along the spline")

    def test_spring_chain_builds_driver_chain_and_mirror_attrs(self):
        name = _create_with_demo("MPyNode/Spring Chain")
        self.assertTrue(_incoming(name + ".driver"), "driver not wired")
        self.assertTrue(_incoming(name + ".time"), "time not wired")
        links = sorted(set(mc.listConnections(
            name + ".driven", source=False, destination=True) or []))
        self.assertEqual(len(links), 100, "setup should build a 100-sphere chain")
        for l in links:
            self.assertTrue(_driven_by(l + ".translate", name, "driven"))
        # the driver carries channel-box attrs mirroring the node's inputs, each
        # wired straight in, so users tune the chain on the driver
        drv = mc.listConnections(name + ".driver", source=True,
                                 destination=False) or []
        self.assertTrue(drv, "no driver locator")
        driver = drv[0]
        for attr in ("gravity", "tension", "damping", "mass",
                     "maxDistance", "minDistance"):
            self.assertTrue(mc.attributeQuery(attr, node=driver, exists=True),
                            "driver missing mirror attr %s" % attr)
            self.assertTrue(_driven_by(name + "." + attr, driver, attr),
                            "node.%s not driven by driver.%s" % (attr, attr))
        # gravity starts zeroed (the demo's intent) ...
        self.assertEqual(tuple(mc.getAttr(name + ".gravity")[0]),
                         (0.0, 0.0, 0.0), "gravity not zeroed")
        # ... and the mirror connection actually CARRIES values: drive the
        # driver's gravity to a sentinel and the node must track it (this fails
        # if driver.gravity -> node.gravity were not wired -- the zeroed-value
        # check alone is vacuous since the node's default gravity is already 0).
        mc.setAttr(driver + ".gravity", 1.0, 2.0, 3.0, type="double3")
        self.assertEqual(
            tuple(round(v, 3) for v in mc.getAttr(name + ".gravity")[0]),
            (1.0, 2.0, 3.0), "node.gravity does not track driver.gravity")
        mc.setAttr(driver + ".gravity", 0.0, 0.0, 0.0, type="double3")
        # play -> the chain moves. Proves the spring buffers (velocity/position)
        # are seeded on a vanilla node (they used to error on the 1st integrate).
        head = mc.listConnections(name + ".driven[0]", source=False,
                                  destination=True) or links
        seen = set()
        for f in (1, 6, 16, 30):
            mc.currentTime(f)
            mc.dgdirty(name)
            seen.add(tuple(round(x, 3)
                           for x in mc.getAttr(head[0] + ".translate")[0]))
        self.assertGreater(len(seen), 1, "chain did not move over time")


class UnitSphereCollisionSetupTest(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def _raw_points(self, shape):
        sl = om.MSelectionList()
        sl.add(shape)
        fn = om.MFnMesh(sl.getDagPath(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om.MSpace.kObject)])

    def _points(self, shape, deformer):
        mc.dgdirty(deformer + ".outputGeometry")
        mc.getAttr(shape + ".outMesh")
        return self._raw_points(shape)

    def test_setup_wires_seeds_persistent_buffer_and_bakes(self):
        plane = mc.polyPlane(w=16, h=12, sx=16, sy=12, name="target")[0]
        shape = mc.listRelatives(plane, shapes=True)[0]
        rest  = self._raw_points(shape)  # plane not yet deformed -> raw rest

        collider = mc.spaceLocator(name="collider")[0]
        mc.setAttr(collider + ".translate", 0, 2, 0)
        mc.setAttr(collider + ".scale", 4, 4, 4)

        # collider TRANSFORM first, MESH second
        name = _create_with_setup(
            "MPyDeformer/Unit Sphere Collision", [collider, plane])

        # 1. wiring: pusher <- collider.worldMatrix, deformer attached to the mesh
        self.assertTrue(_driven_by(name + ".pusher", collider, "worldMatrix"))
        geo = mc.deformer(name, query=True, geometry=True) or []
        self.assertTrue(geo, "deformer not attached to any geometry")
        self.assertIn(shape, geo)

        # 2. persistent buffer seeded from the mesh's initial points
        node = wrap_node(name, "mPyDeformer")
        self.assertIn("positions", node.get_variable_names())
        self.assertTrue(node.is_variable_persistent("positions"))

        # 3. collision + bake: collider is over the plane -> a dent forms; move it
        #    far away -> the dent must STAY (accumulated in the persistent buffer).
        full  = self._points(shape, name)
        moved = np.linalg.norm(full - rest, axis=1) > 1e-4
        self.assertGreater(int(moved.sum()), 0, "collider produced no dent")

        mc.setAttr(collider + ".translateX", 100.0)
        baked = self._points(shape, name)
        self.assertTrue(np.allclose(baked, full, atol=1e-4),
                        "dent did not bake (sprang back when collider left)")


class ProcrustesConstraintSetupsTest(unittest.TestCase):
    """The mPyConstraint orthogonal-Procrustes rivet template
    (MPyConstraint/Procrustes Tags): the demo fabricates a twisting tube
    + rest duplicate and rivets cubes to tagged vertex clusters, driven by
    outMatrix -> decomposeMatrix. Every test drives the node across frames to
    prove the cubes actually ride the deforming mesh (not just that wires
    landed)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _decomp_of(self, transform):
        """The decomposeMatrix feeding ``transform.translate``, or None."""
        src = mc.listConnections(transform + ".translate", source=True,
                                 destination=False, type="decomposeMatrix") or []
        return src[0] if src else None

    def _world_t(self, transform, frame, node):
        mc.currentTime(frame)
        mc.dgdirty(node)
        return np.array(mc.xform(transform, q=True, ws=True, t=True),
                        dtype=float)

    def test_partial_config_eval_emits_no_expression_error(self):
        # Issue 1: evaluating a Procrustes constraint mid-wiring -- mesh
        # connected but meshOrig not yet, and the cluster vars not yet seeded --
        # spammed "expression error: ... no plug ... named 'meshOrig'". The
        # compute is now guarded to no-op until it is fully configured. Forcing
        # an evaluation in that partial state must emit NO expression error.
        #
        # Rehomed from procrustes_cluster (deleted) onto procrustes_tags: the
        # guard lives in the shared compute, not the template. The survivor has
        # the same `_ok` guard shape and the same outMatrix ARRAY output, so
        # the outMatrix[0] pull below still resolves.
        import io
        import sys
        payload, native_type = _payload("MPyConstraint/Procrustes Tags")
        mc.select(clear=True)
        cmd    = _TemplateCreateCommand(payload, native_type)  # no demo, no setup
        node   = run_undoable(cmd) or cmd.created_name
        tube   = mc.polyCylinder()[0]
        tshape = mc.listRelatives(tube, shapes=True, fullPath=True)[0]
        mc.connectAttr(tshape + ".worldMesh[0]", node + ".mesh", force=True)
        # force outMatrix[0] to be pulled -> the constraint computes
        dm = mc.createNode("decomposeMatrix")
        mc.connectAttr(node + ".outMatrix[0]", dm + ".inputMatrix", force=True)
        cap        = io.StringIO()
        old        = sys.stderr
        sys.stderr = cap
        try:
            mc.dgdirty(node)
            mc.getAttr(dm + ".outputTranslate")
        finally:
            sys.stderr = old
        self.assertNotIn(
            "expression error", cap.getvalue(),
            "partial-config eval emitted an expression error:\n%s"
            % cap.getvalue())

    def test_procrustes_tags_demo_rivets_four_tagged_cubes(self):
        from mpynode._common.nodes.mesh.component_tags import tag_names
        name = _create_with_demo("MPyConstraint/Procrustes Tags")
        cubes = sorted(c for c in (mc.ls("tagRiveted*", long=True) or [])
                       if mc.nodeType(c) == "transform")
        self.assertEqual(len(cubes), 4, "tags demo should build four cubes")
        # membership is authored as named component tags on the deforming mesh
        # (ring0..3 + a spare ringAlt); tags live on the intermediate *Orig
        # shape of a deformed mesh, so count deform-aware via tag_names.
        tube_shape = (mc.listRelatives("twistTube", shapes=True, type="mesh",
                                       noIntermediate=True, fullPath=True)
                      or [None])[0]
        self.assertIsNotNone(tube_shape, "twistTube shape missing")
        self.assertGreaterEqual(len(tag_names(tube_shape)), 5,
                                "expected ring0..3 + ringAlt component tags")
        for cube in cubes:
            dm = self._decomp_of(cube)
            self.assertIsNotNone(dm, "%s not driven by a decomposeMatrix" % cube)
            self.assertTrue(_driven_by(dm + ".inputMatrix", name, "outMatrix"),
                            "%s.inputMatrix not fed by %s.outMatrix" % (dm, name))
            p1  = self._world_t(cube, 1, name)
            p45 = self._world_t(cube, 45, name)
            self.assertGreater(float(np.linalg.norm(p45 - p1)), 0.05,
                               "%s did not ride the deforming tube" % cube)

    def test_procrustes_tags_bind_offsets_are_a_declared_input(self):
        # The defect: the per-ring bind offsets rode a stored var, and stored
        # vars do NOT survive template serialization -- `stored_vars` ships
        # EMPTY, so the compute read an attribute the shipped node could never
        # supply (and the compiler refused the node for reading an undeclared
        # self attr). They are now a DECLARED matrix-array INPUT, seeded on the
        # PLUG by the demo.
        import mpynode

        payload, _ = _payload("MPyConstraint/Procrustes Tags")
        meta = (payload.get("input_attrs") or {}).get("bindMatrices")
        self.assertIsNotNone(
            meta, "bindMatrices must be a DECLARED input on the template")
        self.assertEqual(meta.get("attr_type"), "matrix")
        self.assertTrue(meta.get("is_array"),
                        "bindMatrices must be a matrix ARRAY (one per rivet)")
        self.assertNotIn(
            "bindMatrices", payload.get("stored_vars") or {},
            "bind offsets must not ride a stored var -- those ship empty")

        name = _create_with_demo("MPyConstraint/Procrustes Tags")
        idx  = mc.getAttr(name + ".bindMatrices", multiIndices=True) or []
        self.assertEqual(len(idx), 4,
                         "demo must seed one bind offset per rivet on the PLUG")
        self.assertNotIn(
            "bindMatrices", mpynode.wrap_node(name).get_variables() or {},
            "bind offsets must live on the plug, not in node variables")
        # Behaviour: at the bind frame the twist is 0, so deformed == rest, the
        # rigid Procrustes fit is identity, and each outMatrix[i] is exactly the
        # bind offset it was seeded with.
        mc.currentTime(1)
        mc.dgdirty(name)
        for i in idx:
            bind = np.array(
                mc.getAttr("%s.bindMatrices[%d]" % (name, i))).reshape(4, 4)
            out = np.array(
                mc.getAttr("%s.outMatrix[%d]" % (name, i))).reshape(4, 4)
            self.assertTrue(
                np.allclose(out, bind, atol=1e-3),
                "outMatrix[%d] must equal its bind offset at rest (maxdiff %s)"
                % (i, float(np.abs(out - bind).max())))

    def test_create_tag_reports_that_it_did_not_overwrite(self):
        # T114. `componentTag(create=True)` on a name that is already taken is a
        # SILENT no-op: it returns '', raises nothing, and keeps the OLD vertex
        # set. create_tag used to swallow that '' and return the name, so a
        # caller believed it had re-authored a tag it had not touched.
        from mpynode._common.nodes.mesh.component_tags import (
            create_tag, resolve_tag_indices)
        cube  = mc.polyCube(constructionHistory=False, name="tagContract")[0]
        shape = mc.listRelatives(cube, shapes=True, fullPath=True)[0]

        self.assertEqual(create_tag(shape, "tA", [0, 1]), "tA")
        self.assertEqual(sorted(resolve_tag_indices(shape, "tA")), [0, 1])

        # same name, DIFFERENT verts -> nothing is created and we must say so
        self.assertEqual(create_tag(shape, "tA", [4, 5, 6]), "",
                         "a taken name creates nothing and must report ''")
        self.assertEqual(sorted(resolve_tag_indices(shape, "tA")), [0, 1],
                         "membership must be untouched -- it does NOT overwrite")
        # nothing to author is also 'created nothing'
        self.assertEqual(create_tag(shape, "tEmpty", []), "")

    def test_procrustes_tags_setup_on_a_second_node_does_not_steal_tags(self):
        # T115. The auto-name was keyed on the rider INDEX, which only avoids a
        # collision within ONE run. A second node on the same mesh restarted at
        # procrustesRivet0, and because create_tag cannot overwrite (T114) the
        # new rider silently inherited the FIRST node's vertex ring.
        from mpynode._common.nodes.mesh.component_tags import (
            resolve_tag_indices, tag_names)
        sphere = mc.polySphere(sx=20, sy=20, name="sharedTarget")[0]
        shape = mc.listRelatives(sphere, shapes=True, type="mesh",
                                 noIntermediate=True, fullPath=True)[0]

        near = mc.spaceLocator(name="riderNear")[0]
        mc.setAttr(near + ".translate", 0.0, 1.0, 0.0)      # north pole
        far = mc.spaceLocator(name="riderFar")[0]
        mc.setAttr(far + ".translate", 0.0, -1.0, 0.0)      # south pole

        n1 = _create_with_setup(
            "MPyConstraint/Procrustes Tags", [sphere, near])
        n2 = _create_with_setup(
            "MPyConstraint/Procrustes Tags", [sphere, far])

        t1 = mc.getAttr("%s.clusterTags[0]" % n1)
        t2 = mc.getAttr("%s.clusterTags[0]" % n2)
        self.assertNotEqual(
            t1, t2,
            "the second node must author its OWN tag, not reuse %r" % (t1,))
        for t in (t1, t2):
            self.assertIn(t, tag_names(shape) or [])

        # the decisive check: distinct NAMES would still be wrong if they
        # resolved to the same verts. These riders sit at opposite poles.
        v1 = set(resolve_tag_indices(shape, t1) or [])
        v2 = set(resolve_tag_indices(shape, t2) or [])
        self.assertTrue(v1 and v2, "both tags must resolve to real vertices")
        self.assertFalse(
            v1 & v2,
            "opposite-pole riders share vertices %r -- the second rivet is "
            "bound to the first one's ring" % (sorted(v1 & v2)[:8],))

    def test_procrustes_tags_setup_rivets_selected_transforms(self):
        # The tags variant is the NAMED cousin of the cluster setup: select a
        # mesh + N transforms and each rider is riveted through a component TAG
        # the setup authors on the mesh (clusterTags[i] names it), driven by
        # outMatrix[i]. Prove tracking by deforming the mesh, exactly like the
        # cluster case -- a pure transform move is deliberately NOT used.
        from mpynode._common.nodes.mesh.component_tags import tag_names
        sphere = mc.polySphere(sx=20, sy=20, name="riveTarget")[0]
        riders = []
        for i, tx in enumerate((-1.2, 0.0, 1.2)):
            loc = mc.spaceLocator(name="rideMe%d" % i)[0]
            mc.setAttr(loc + ".translate", tx, 1.0, 0.0)
            riders.append(loc)

        # mesh first, then the transforms to rivet
        name = _create_with_setup(
            "MPyConstraint/Procrustes Tags", [sphere] + riders)

        # membership is NAMED: one authored tag per rider, echoed on the
        # clusterTags multi-string so the user can retype/retarget it.
        shape = mc.listRelatives(sphere, shapes=True, type="mesh",
                                 noIntermediate=True, fullPath=True)[0]
        authored = tag_names(shape) or []
        tags = [mc.getAttr("%s.clusterTags[%d]" % (name, i))
                for i in range(len(riders))]
        self.assertEqual(len(set(tags)), len(riders),
                         "each rider needs its OWN tag (got %r)" % (tags,))
        for t in tags:
            self.assertIn(t, authored,
                          "setup must author %r on the mesh (have %r)"
                          % (t, authored))
        self.assertEqual(
            len(mc.getAttr(name + ".bindMatrices", multiIndices=True) or []),
            len(riders), "one bind offset per rider on the PLUG")

        for i, rider in enumerate(riders):
            dm = self._decomp_of(rider)
            self.assertIsNotNone(dm, "%s not driven by a decomposeMatrix" % rider)
            self.assertTrue(
                _driven_by(dm + ".inputMatrix", name, "outMatrix"),
                "%s.inputMatrix not fed by %s.outMatrix[i]" % (dm, name))
        self.assertTrue(_incoming(name + ".mesh"), "mesh input not wired")
        self.assertTrue(_incoming(name + ".meshOrig"), "meshOrig input not wired")

        before = [np.array(mc.xform(r, q=True, ws=True, t=True), dtype=float)
                  for r in riders]
        mc.select(sphere, replace=True)
        mc.nonLinear(type="bend", lowBound=-1, highBound=1, curvature=90)
        mc.dgdirty(name)
        for r, b in zip(riders, before):
            a = np.array(mc.xform(r, q=True, ws=True, t=True), dtype=float)
            self.assertGreater(float(np.linalg.norm(a - b)), 0.05,
                               "%s did not follow the deforming mesh" % r)

    def test_procrustes_tags_rides_under_em_parallel_scrub(self):
        # Issue A regression lock: under the Evaluation Manager, compute() runs
        # on a WORKER thread where SelfProxy's api1 MObject bridge bailed -- so
        # ``self.mesh`` / ``self.meshOrig`` raised "self has no plug named
        # 'meshOrig'", the guarded compute skipped, an identity outMatrix was
        # emitted and every riveted cube SNAPPED TO 0,0,0 after frame one. The
        # fix seeds the EM-safe datablock-read inputs into compute_locals.
        #
        # Rehomed from procrustes_cluster (deleted) onto procrustes_tags: this
        # guards the SHARED mpy_constraint fix, not the template, so it has to
        # keep running. The tags demo names its riders tagRiveted%d.
        prev_mode = (mc.evaluationManager(q=True, mode=True) or ["off"])[0]
        try:
            name = _create_with_demo("MPyConstraint/Procrustes Tags")
            cube = sorted(c for c in (mc.ls("tagRiveted*", long=True) or [])
                          if mc.nodeType(c) == "transform")[0]
            mc.evaluationManager(mode="parallel")

            def _ws(frame):
                mc.currentTime(frame)
                mc.getAttr(cube + ".translate")  # pull the EM graph
                return np.array(mc.xform(cube, q=True, ws=True, t=True),
                                dtype=float)

            p1       = _ws(1)
            deformed = [_ws(f) for f in (20, 40, 60)]
            # NOT stuck at the origin on any deformed frame (the bug signature)
            for f, p in zip((20, 40, 60), deformed):
                self.assertGreater(
                    float(np.linalg.norm(p)), 1e-3,
                    "cube snapped to 0,0,0 at frame %d under EM parallel "
                    "(worker-thread mesh read failed)" % f)
            # and it actually rides the deforming tube across the scrub
            self.assertGreater(
                float(np.linalg.norm(deformed[-1] - p1)), 0.05,
                "cube did not ride the deforming tube under EM parallel")
            # scrubbing back must restore the frame-1 pose (not latch at origin)
            back = _ws(1)
            self.assertLess(
                float(np.linalg.norm(back - p1)), 1e-3,
                "cube did not return to its frame-1 pose on scrub back")
        finally:
            try:
                mc.evaluationManager(mode=prev_mode)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
