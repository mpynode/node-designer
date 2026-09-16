"""Functional tests for the Game of Life mPyFile texture template.

Loads the SHIPPED ``template.mpn`` and verifies:
  * the redesigned inputs (width/height=100, reset [False,True], density 0..1=0.5)
    and all three render tiers (Compute, Viewport, OSL) plus the full demo,
  * the bounded simulation (a blinker oscillates; an edge cell dies -- NO wrap),
  * the live node paints white (alive) / black (dead) per-UV and advances one
    Conway step per frame,
  * the "full demo" builds a polyPlane + lambert (assigned) wired to outColor
    through the REAL gallery path (_TemplateCreateCommand), and -- when MtoA is
    present -- the Arnold OSL render path.

This texture template ships a self-contained ``def demo(self)`` (it fabricates
its own showcase scene: plane + shader + Arnold path), NOT a selection-driven
``def setup``. The demo takes NO selection.
"""

import os
import unittest

import numpy as np
import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_REL = "MPyFile/Game Of Life Texture"


def _template_path():
    from mpynode._common.util.template_gallery import _bundled_templates_root
    root = _bundled_templates_root()
    assert root, "bundled templates root not found"
    return os.path.join(root, *_REL.split("/"), "template.mpn")


def _load_payload():
    from mpynode._common.io.mpn_io import load_mpn_header
    return load_mpn_header(_template_path())


def _init_funcs(payload):
    """Exec the template's Init source in a scratch namespace and return its
    pure simulation helpers (the same ones the node uses) for reference math."""
    ns = {}
    exec(payload["init_source"], ns)
    return ns


class TestGameOfLifeTextureContent(unittest.TestCase):
    def test_type_and_inputs(self):
        d = _load_payload()
        self.assertEqual(d.get("native_type"), "mPyFile")
        ia = d.get("input_attrs") or {}
        self.assertEqual(set(ia), {"width", "height", "reset", "density",
                                   "frame", "bakePath"})
        self.assertEqual(ia["frame"].get("attr_type"), "time")
        # The OSL bake target is an INPUT, not a stored var: Compute reads it to
        # drive self.write_texture, and persistent state cannot carry a string
        # (so a stored one would stop the compute lowering).
        self.assertEqual(ia["bakePath"].get("attr_type"),    "string")
        self.assertEqual(ia["width"].get("default_value"),   100)
        self.assertEqual(ia["height"].get("default_value"),  100)
        self.assertEqual(ia["density"].get("default_value"), 0.5)
        self.assertEqual(ia["density"].get("min_value"),     0.0)
        self.assertEqual(ia["density"].get("max_value"),     1.0)
        self.assertEqual(ia["reset"].get("enum_names"),      ["False", "True"])

    def test_inputs_in_authored_order(self):
        # Channel Box / Designer order must be the authored add-order
        # (width+height adjacent), NOT alphabetical -- carried by each meta's
        # ``order`` field through the .mpn.
        d  = _load_payload()
        ia = d.get("input_attrs") or {}
        self.assertTrue(all("order" in m for m in ia.values()),
                        "template inputs missing the 'order' field")
        self.assertEqual(
            sorted(ia, key=lambda k: ia[k]["order"]),
            ["width", "height", "density", "frame", "reset", "bakePath"],
        )

    def test_all_tiers_present(self):
        d = _load_payload()
        self.assertTrue(d.get("expression"))       # Compute
        self.assertTrue(d.get("init_source"))      # Init
        self.assertTrue(d.get("viewport_source"))  # Viewport (VP2)
        osl = d.get("osl_source") or ""
        self.assertIn("shader gameOfLife", osl)         # OSL (Arnold)
        # The shader samples a per-frame name it rebuilds from fileName +
        # bakeFrame, not fileName itself: Arnold's texture cache is keyed on the
        # filename and never re-stats, so one overwritten path renders the first
        # frame forever. `%s.%04d.png` is the cross-tier contract -- the Compute
        # tier and the nd_tex_write C++ kernel name the file the same way.
        self.assertIn("float bakeFrame", osl)
        self.assertIn("texture(path",    osl)
        self.assertIn('"%s.%04d.png"',   osl)
        self.assertIn("closest",         osl)                   # crisp cells (nearest)

    def test_carries_self_first_demo(self):
        from mpynode._common.node_setups import find_demo
        d = _load_payload()
        self.assertIsNotNone(find_demo(d.get("methods_source") or ""))

    def test_no_baked_persistent_data(self):
        d = _load_payload()
        self.assertNotIn("persistent_vars", d)


class TestComputeLowersDeterministically(unittest.TestCase):
    """The compute MUST lower to C++ rather than reach the AI porter.

    It seeds with numpy's RandomState, and ``nd::MT19937`` reproduces that
    stream bit-for-bit. A port instead re-invents the generator (it reached for
    ``std::mt19937_64``), so the compiled board silently stopped matching the
    interpreted one and the node's own authored test failed on every compiled
    build. These assertions are on the EMITTED SOURCE, so they are cheap -- no
    compiler, no Maya plug-in load."""

    def _cpp(self):
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode.native import compiler as codegen
        from mpynode.native.spec import mpn_spec_adapter

        spec = mpn_spec_adapter.spec_from_mpn_payload(
            load_mpn(_template_path(), trusted=True))
        return codegen.generate_cpp(spec, for_port=True)

    def test_no_ai_port_region(self):
        self.assertNotIn("ND_PORT", self._cpp())

    def test_rng_is_the_bit_exact_numpy_clone(self):
        cpp = self._cpp()
        self.assertIn("MT19937", cpp)
        # The generator an AI port reached for. Its stream differs from numpy's,
        # so its presence means the deterministic lowering was lost.
        self.assertNotIn("mt19937_64", cpp)

    def test_the_bake_call_is_actually_emitted(self):
        """Not just the kernel DEFINITION: a blessed call left as a bare
        expression statement is dropped from the emitted C++, which would
        silently disable the bake while still looking wired up."""
        cpp = self._cpp()
        self.assertIn("nd_tex_write", cpp)
        self.assertIn("= nd_tex_write(", cpp)


class TestBoundedSimulation(unittest.TestCase):
    """The Conway step is bounded -- neighbours beyond the edge are dead, so
    nothing wraps around the border."""

    def setUp(self):
        self.fns = _init_funcs(_load_payload())

    def test_blinker_is_period_two(self):
        step          = self.fns["_gol_step"]
        blink         = np.zeros((5, 5), dtype=bool)
        blink[2, 1:4] = True
        self.assertFalse(np.array_equal(step(blink), blink))       # it changes
        self.assertTrue(np.array_equal(step(step(blink)), blink))  # period 2

    def test_edge_cell_does_not_wrap(self):
        step = self.fns["_gol_step"]
        # A single live cell at a corner has < 3 neighbours and dies. If the grid
        # wrapped, the corner would border the opposite edges and could survive.
        corner       = np.zeros((6, 6), dtype=bool)
        corner[0, 0] = True
        self.assertFalse(step(corner).any())

    def test_density_seeds_expected_fraction(self):
        seed  = self.fns["_gol_seed"]
        board = seed(200, 200, 0.5, seed=1)
        self.assertAlmostEqual(float(board.mean()), 0.5, delta=0.02)


class TestLiveNode(unittest.TestCase):
    N = 5

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._common.io.mpn_io import deserialize_node
        payload   = _load_payload()
        self.fns  = _init_funcs(payload)
        self.node = deserialize_node(payload, restore_persistent=False)
        self.name = self.node.get_name()
        mc.setAttr(self.name + ".width",   self.N)
        mc.setAttr(self.name + ".height",  self.N)
        mc.setAttr(self.name + ".density", 0.5)

    def _sample(self, cx, cy):
        mc.setAttr(self.name + ".uCoord", (cx + 0.5) / self.N)
        mc.setAttr(self.name + ".vCoord", 1.0 - (cy + 0.5) / self.N)
        mc.dgdirty(self.name + ".outColor")
        return mc.getAttr(self.name + ".outColor")[0][0] > 0.5

    def _board_from_node(self):
        return np.array([[self._sample(cx, cy) for cx in range(self.N)]
                         for cy in range(self.N)], dtype=bool)

    def test_compute_paints_seeded_board(self):
        mc.setAttr(self.name + ".reset", 1)             # True -> reseed
        mc.currentTime(5)
        expected = self.fns["_gol_seed"](self.N, self.N, 0.5, seed=5)
        np.testing.assert_array_equal(self._board_from_node(), expected)

    def test_advances_one_step_per_frame(self):
        mc.setAttr(self.name + ".reset", 1)
        mc.currentTime(5)
        seeded = self._board_from_node()                # evaluate -> seeds frame 5
        mc.setAttr(self.name + ".reset", 0)  # False -> simulate
        mc.currentTime(6)                    # next frame -> one step
        expected = self.fns["_gol_step"](seeded)
        np.testing.assert_array_equal(self._board_from_node(), expected)

    def test_reset_reseeds_distinctly_per_frame(self):
        mc.setAttr(self.name + ".reset", 1)
        mc.currentTime(5)
        a = self._board_from_node()
        mc.currentTime(9)
        b = self._board_from_node()
        self.assertFalse(np.array_equal(a, b))          # frame-varying seed


class TestViewportTierAnimates(unittest.TestCase):
    """The board must advance on a pure-VIEWPORT scrub with reset=False (the
    user-reported freeze). Drives the real ``runViewport`` per frame and reads
    the board the tier persisted -- so it guards the GUI path the Compute-tier
    tests don't exercise."""

    N = 5

    def setUp(self):
        mc.file(new=True, force=True)
        import maya.api.OpenMaya as om
        from mpynode._api2.mpy_file import MPyFile
        from mpynode._common.io.mpn_io import deserialize_node
        self._om = om
        self.fns = _init_funcs(_load_payload())
        # Route through the full viewport-source machinery, not BAREBONES.
        self._bb               = MPyFile.BAREBONES_MODE
        MPyFile.BAREBONES_MODE = False
        self.addCleanup(setattr, MPyFile, "BAREBONES_MODE", self._bb)
        self.node = deserialize_node(_load_payload(), restore_persistent=False)
        self.name = self.node.get_name()
        mc.setAttr(self.name + ".width",   self.N)
        mc.setAttr(self.name + ".height",  self.N)
        mc.setAttr(self.name + ".density", 0.5)
        sel = om.MSelectionList()
        sel.add(self.name)
        self.mobj = sel.getDependNode(0)
        self.mpx  = om.MFnDependencyNode(self.mobj).userNode()

    def _viewport_board(self):
        """Run the viewport tier once (headless: texture_manager is None, so it
        only advances + persists the board) and return the persisted board."""
        from mpynode._common.storedvars import stored_var_store
        self.mpx.runViewport(None, None)
        return stored_var_store.load_for_compute(self.mobj, "").get("board")

    def test_viewport_steps_on_scrub_with_reset_false(self):
        import numpy as np
        mc.setAttr(self.name + ".reset", 1)
        mc.currentTime(1)
        b1 = self._viewport_board()                 # seed frame 1
        self.assertIsNotNone(b1, "viewport never produced a board")
        mc.setAttr(self.name + ".reset", 0)         # simulate
        mc.currentTime(2)
        b2 = self._viewport_board()
        mc.currentTime(3)
        b3 = self._viewport_board()
        # It must ADVANCE (not freeze) AND match the Conway step each frame.
        self.assertFalse(np.array_equal(b1, b2), "board frozen on scrub")
        np.testing.assert_array_equal(b2, self.fns["_gol_step"](b1))
        np.testing.assert_array_equal(b3, self.fns["_gol_step"](b2))


class TestFullDemo(unittest.TestCase):
    """The template's full demo builds a polyPlane + lambert (assigned) and
    drives the lambert colour from outColor, through the real gallery path.
    The demo fabricates its own scene, so it takes NO selection."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _create_with_demo(self):
        from mpynode._base.commands import _TemplateCreateCommand, run_undoable
        from mpynode._common.io.mpn_io import load_mpn
        payload = load_mpn(_template_path(), trusted=True)
        mc.select(clear=True)
        cmd = _TemplateCreateCommand(payload, payload.get("native_type"),
                                     run_demo=True)
        name = run_undoable(cmd) or cmd.created_name
        if cmd.tier_failures.get("demo"):
            raise AssertionError("demo failed: %s" % cmd.tier_failures["demo"])
        return name

    def test_demo_builds_plane_and_shader(self):
        name   = self._create_with_demo()
        plane  = name + "_plane"
        shader = name + "_lambert"
        self.assertTrue(mc.objExists(plane), "polyPlane not created")
        self.assertTrue(mc.objExists(shader), "lambert not created")
        # outColor -> lambert.color
        srcs = mc.listConnections(shader + ".color", source=True,
                                  destination=False, plugs=True) or []
        self.assertTrue(any(p.startswith(name + ".outColor") for p in srcs),
                        "lambert.color not driven by %s.outColor" % name)
        # plane assigned to the lambert's shading group
        sg = shader + "SG"
        self.assertTrue(mc.objExists(sg))
        members      = mc.sets(sg, query=True) or []
        plane_shapes = mc.listRelatives(plane, shapes=True, fullPath=False) or []
        assigned = any(m in members or m.split(".")[0] in plane_shapes
                       for m in members) or bool(
            set(plane_shapes) & set(m.split(".")[0] for m in members))
        self.assertTrue(assigned or plane in (members or []),
                        "plane not assigned to the shader's SG")

    def test_demo_sets_the_bake_path_input(self):
        """The demo points the node at its per-node PNG. That target is an
        INPUT ATTR now, not a stored var -- Compute reads it to drive the
        blessed self.write_texture, which has a C++ twin, so the COMPILED node
        bakes too."""
        name = self._create_with_demo()
        bake = mc.getAttr(name + ".bakePath")
        self.assertTrue(bake, "demo left bakePath empty")
        self.assertTrue(bake.endswith(".png"), bake)

    def test_demo_builds_arnold_osl_when_available(self):
        try:
            if not mc.pluginInfo("mtoa", q=True, loaded=True):
                mc.loadPlugin("mtoa")
        except Exception:
            self.skipTest("MtoA not available")
        name = self._create_with_demo()
        sg   = name + "_lambertSG"
        if not mc.attributeQuery("aiSurfaceShader", node=sg, exists=True):
            self.skipTest("aiSurfaceShader unavailable (MtoA classification)")
        mtl = mc.listConnections(sg + ".aiSurfaceShader", source=True,
                                 destination=False) or []
        self.assertTrue(mtl, "Arnold render path not routed to aiSurfaceShader")
        osl = mc.listConnections(mtl[0], source=True, destination=False,
                                 type="aiOslShader") or []
        self.assertTrue(osl, "aiSurfaceShader material not fed by an aiOslShader")

        # The shader rebuilds the per-frame bake name from fileName+bakeFrame,
        # so bakeFrame MUST be driven by the node's frame. Left at its default
        # it samples ONE file forever -- an Arnold render that never animates,
        # which is exactly what the frame-stamped bake exists to fix. Nothing
        # else fails when this connection is missing, hence the explicit check.
        self.assertTrue(
            mc.attributeQuery("bakeFrame", node=osl[0], exists=True),
            "the OSL shader has no bakeFrame param (stale shader source?)")
        # `frame` is a TIME attr and bakeFrame is a float, so Maya splices a
        # timeToUnitConversion between them -- walk through any conversion hop
        # rather than demanding a direct wire.
        def upstream(plug, hops=4):
            for _ in range(hops):
                src = mc.listConnections(plug, source=True, destination=False,
                                         plugs=True) or []
                if not src:
                    return None
                node = src[0].split(".")[0]
                if not mc.nodeType(node).endswith("UnitConversion") \
                        and mc.nodeType(node) != "unitConversion":
                    return src[0]
                plug = node + ".input"
            return None

        driver = upstream(osl[0] + ".bakeFrame")
        self.assertTrue(driver and driver.startswith(name + ".frame"),
                        "aiOslShader.bakeFrame is not driven by %s.frame (got "
                        "%s) -- Arnold would render one frame forever"
                        % (name, driver))


if __name__ == "__main__":
    unittest.main()
