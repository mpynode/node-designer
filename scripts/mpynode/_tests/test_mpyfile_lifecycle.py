"""mPyFile node-lifecycle hardening (P1 Hypershade visibility + P2 black-render).

Root causes (confirmed via headless mayapy bisection):

  * P1 -- a node created via ``cmds.createNode`` (the .mpn import / template /
    deserialize path) is NOT connected to ``defaultTextureList1`` the way
    ``shadingNode -asTexture`` connects it, so the Hypershade can't graph it.
  * P2 -- a freshly-created mPyFile whose init namespace is not yet in the
    main-thread registry renders BLACK on the Hypershade swatch / Arnold
    worker thread: ``ensure_init_namespace_for_mobject`` bails on non-main
    threads, so the init helpers (``_read_image`` etc.) are undefined and the
    user Compute expression raises BEFORE assigning ``self.outColor`` -- the
    output stays at its (0,0,0) default. The main-thread DG compute works
    (lazy reload fires), which is why scrubbing the timeline "fixes" it.

The fix warms BOTH on the main thread for every mPyFile from ANY source via a
node-added callback (+ scene-open sweep), mirroring the existing time-change /
attr-refresh callbacks.
"""

from __future__ import annotations

import os
import tempfile
import threading
import unittest

import maya.cmds as mc
import maya.api.OpenMaya as om

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _make_test_png(path: str) -> None:
    """Write a tiny RGBA PNG via MImage (no PIL dependency)."""
    import ctypes

    w = h = 4
    # Distinct non-black pixels so a correct read is unambiguously != (0,0,0).
    buf = bytearray()
    for i in range(w * h):
        buf += bytes((40 + i * 5, 80, 160, 255))
    img = om.MImage()
    img.setPixels(bytes(buf), w, h)
    img.writeToFile(path, "png")


def _make_solid_png(path: str, value: int) -> None:
    """Write a tiny solid-grey RGBA PNG (every pixel == ``value``) via MImage."""
    w = h = 4
    buf = bytes((value, value, value, 255)) * (w * h)
    img = om.MImage()
    img.create(w, h, 4, om.MImage.kByte)
    img.setPixels(buf, w, h)
    img.writeToFile(path, "png")


def _srgb_to_linear(s: float) -> float:
    """Reference sRGB EOTF (encoded -> scene-linear). Mirrors
    ``file_defaults._srgb_eotf`` for a single scalar."""
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


# ===========================================================================
# P1 -- Hypershade visibility (defaultTextureList1 membership)
# ===========================================================================
class TestTextureListMembership(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_createNode_path_is_not_in_texture_list_by_default(self):
        """Baseline: bare createNode does NOT register with the texture list
        (this is the bug -- the import/template path uses createNode)."""
        n = mc.createNode("mPyFile", name="bare")
        self.assertNotIn(n, mc.ls(textures=True) or [])

    def test_ensure_in_texture_list_makes_node_graphable(self):
        from mpynode._api2.mpy_file import ensure_in_texture_list

        n = mc.createNode("mPyFile", name="bare")
        ensure_in_texture_list(n)
        self.assertIn(n, mc.ls(textures=True) or [])
        # message must be wired into defaultTextureList1.textures
        conns = mc.listConnections(
            n + ".message", source=False, destination=True
        ) or []
        self.assertIn("defaultTextureList1", conns)

    def test_ensure_in_texture_list_is_idempotent(self):
        from mpynode._api2.mpy_file import ensure_in_texture_list

        n = mc.createNode("mPyFile", name="bare")
        ensure_in_texture_list(n)
        ensure_in_texture_list(n)  # must not raise / double-connect
        srcs = mc.listConnections(
            "defaultTextureList1.textures", source=True
        ) or []
        self.assertEqual(srcs.count(n), 1)

    def test_shadingNode_path_already_in_list_stays_single(self):
        """A node already added by shadingNode -asTexture must not be
        double-added."""
        from mpynode._api2.mpy_file import ensure_in_texture_list

        n = mc.shadingNode("mPyFile", asTexture=True, name="shaded")
        self.assertIn(n, mc.ls(textures=True) or [])
        ensure_in_texture_list(n)
        srcs = mc.listConnections(
            "defaultTextureList1.textures", source=True
        ) or []
        self.assertEqual(srcs.count(n), 1)

    def test_ensure_self_heals_a_duplicate_connection(self):
        """If a duplicate message->textures connection already exists (the
        create-time race with shadingNode -asTexture, or a .ma saved with that
        bug), ensure_in_texture_list must collapse it back to exactly one.

        message is a one-to-many source, so a fanout to two explicit element
        indices is a genuine duplicate (cmds refuses a 2nd nextAvailable, but
        the shadingNode internal path can still produce two elements)."""
        from mpynode._api2.mpy_file import ensure_in_texture_list

        n = mc.createNode("mPyFile", name="dup")
        mc.connectAttr(n + ".message", "defaultTextureList1.textures[0]")
        mc.connectAttr(n + ".message", "defaultTextureList1.textures[1]")
        srcs = mc.listConnections("defaultTextureList1.textures", source=True) or []
        self.assertEqual(srcs.count(n), 2, "precondition: duplicate exists")
        ensure_in_texture_list(n)
        srcs2 = mc.listConnections("defaultTextureList1.textures", source=True) or []
        self.assertEqual(srcs2.count(n), 1)

    def test_node_added_callback_does_not_duplicate_on_shadingNode_create(self):
        """Production-realistic: the node-added warm runs DEFERRED at idle,
        AFTER shadingNode -asTexture finishes its own texture-list wiring, so it
        must NOT add a second connection. We emulate the idle ordering by
        creating via shadingNode FIRST, then running the lifecycle warm."""
        from mpynode._api2.mpy_file import _warm_node_lifecycle

        n = mc.shadingNode("mPyFile", asTexture=True, name="shaded2")
        _warm_node_lifecycle(n)  # the deferred body, run after creation
        srcs = mc.listConnections("defaultTextureList1.textures", source=True) or []
        self.assertEqual(srcs.count(n), 1)


# ===========================================================================
# P2 -- init-namespace warming (black-on-worker-thread)
# ===========================================================================
class TestInitNamespaceWarming(unittest.TestCase):
    INIT_SRC = (
        "import numpy as np\n"
        "def _read_image(path):\n"
        "    return np.zeros((2, 2, 4), dtype=np.float32) + 0.5\n"
    )
    COMPUTE_SRC = (
        "img = _read_image(self.fileName)\n"
        "self.outColor = (float(img[0,0,0]), 0.25, 0.75)\n"
        "self.outAlpha = 1.0\n"
    )

    def setUp(self):
        from mpynode._api2.mpy_file import MPyFile

        self._barebones = MPyFile.BAREBONES_MODE
        MPyFile.BAREBONES_MODE = False
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile as W

        self.name = mc.createNode("mPyFile", name="warmme")
        w = W(self.name)
        w.set_init_expression(self.INIT_SRC)
        w.set_compute_expression(self.COMPUTE_SRC)
        sel = om.MSelectionList()
        sel.add(self.name)
        self.obj = sel.getDependNode(0)

    def tearDown(self):
        from mpynode._api2.mpy_file import MPyFile

        MPyFile.BAREBONES_MODE = self._barebones

    def test_warm_registers_init_namespace_on_main_thread(self):
        from mpynode._api2.mpy_file import warm_init_namespace
        from mpynode._common.lifecycle import init_registry as ir

        ir.clear_init_expression(self.name)
        self.assertIsNone(ir.get_init_namespace_for_mobject(self.obj))
        warm_init_namespace(self.name)
        self.assertIsNotNone(ir.get_init_namespace_for_mobject(self.obj))

    def test_warmed_node_computes_color_on_worker_thread(self):
        """The smoking-gun reproduction: a COLD-registry worker-thread eval
        NameErrors -> black; a WARMED one returns the real color."""
        from mpynode._api2.mpy_file import warm_init_namespace
        from mpynode._common.lifecycle import init_registry as ir
        from mpynode._common.compute import expression as expr

        code = compile(self.COMPUTE_SRC, "<t>", "exec")

        class _Self:
            fileName = ""
            outColor = (0.0, 0.0, 0.0)
            outAlpha = 0.0

        def run_on_worker():
            s = _Self()
            ns = {"self": s}
            expr.exec_with_profile_watch(code, ns, node_obj=self.obj)
            return s.outColor

        # COLD -> black on the worker thread.
        ir.clear_init_expression(self.name)
        res = {}
        t = threading.Thread(target=lambda: res.__setitem__("c", run_on_worker()))
        t.start(); t.join()
        self.assertEqual(res["c"], (0.0, 0.0, 0.0))  # documents the bug

        # WARM -> real color on the worker thread.
        ir.clear_init_expression(self.name)
        warm_init_namespace(self.name)
        res2 = {}
        t2 = threading.Thread(target=lambda: res2.__setitem__("d", run_on_worker()))
        t2.start(); t2.join()
        self.assertEqual(res2["d"], (0.5, 0.25, 0.75))

    def test_warm_is_safe_on_node_without_init(self):
        from mpynode._api2.mpy_file import warm_init_namespace

        n = mc.createNode("mPyFile", name="noinit")
        # Must not raise even when there is no _initSource value.
        warm_init_namespace(n)

    def test_real_compute_is_black_cold_and_color_warm_on_worker_thread(self):
        """Hardening (drives the REAL MPyFile.compute() via mc.getAttr on a
        worker thread, not a synthetic _Self): a cold-registry worker eval does
        NOT produce the correct color (it NameErrors to the (0,0,0) default);
        warming the namespace makes the same worker eval produce the color."""
        from mpynode._api2.mpy_file import warm_init_namespace
        from mpynode._common.lifecycle import init_registry as ir

        CORRECT = (0.5, 0.25, 0.75)

        def worker_outcolor(out):
            try:
                out["v"] = tuple(
                    round(c, 3) for c in mc.getAttr(self.name + ".outColor")[0]
                )
            except Exception as exc:  # worker-thread getAttr may raise
                out["v"] = ("ERR", str(exc))

        # COLD: clear the registry, force recompute, pull from a worker thread.
        ir.clear_init_expression(self.name)
        mc.dgdirty(self.name + ".outColor")
        cold = {}
        tc = threading.Thread(target=worker_outcolor, args=(cold,))
        tc.start(); tc.join()
        self.assertNotEqual(cold["v"], CORRECT)  # broken when cold

        # WARM: register on the main thread, then the same worker eval works.
        ir.clear_init_expression(self.name)
        warm_init_namespace(self.name)
        mc.dgdirty(self.name + ".outColor")
        warm = {}
        tw = threading.Thread(target=worker_outcolor, args=(warm,))
        tw.start(); tw.join()
        self.assertEqual(warm["v"], CORRECT)


# ===========================================================================
# End-to-end: the INSTALLED node-added callback warms a node from any source
# ===========================================================================
class TestNodeAddedLifecycleEndToEnd(unittest.TestCase):
    """Drives the REAL ``addNodeAddedCallback`` installed at plugin load. The
    callback defers its work to the main-thread idle (so the .mpn import has
    finished setting ``_initSource`` by the time it runs); here we run those
    deferred callables inline so the path is exercised headlessly."""

    def setUp(self):
        from mpynode._api2.mpy_file import MPyFile

        self._barebones = MPyFile.BAREBONES_MODE
        MPyFile.BAREBONES_MODE = False
        mc.file(new=True, force=True)
        import maya.utils as mu

        self._mu = mu
        self._orig_def = mu.executeDeferred

        def _inline(fn, *a, **k):
            try:
                fn(*a, **k)
            except Exception:
                pass

        mu.executeDeferred = _inline

    def tearDown(self):
        self._mu.executeDeferred = self._orig_def
        from mpynode._api2.mpy_file import MPyFile

        MPyFile.BAREBONES_MODE = self._barebones

    def test_template_node_is_graphable_and_warm_after_create(self):
        from mpynode._common.lifecycle import init_registry as ir
        from mpynode._common.io import mpn_io
        from mpynode._base.commands import _ImportNodeCommand, run_undoable

        # build_new_node_command lost its template mode, so "a
        # template-created mPyFile is graphable + warm" now lives on the
        # gallery import path. Build from the File Simple template
        # through that path.
        tmpl = os.path.join(
            os.environ.get("MPYNODE_ROOT", ""),
            "templates/MPyFile/File Simple/template.mpn",
        )
        payload = mpn_io.load_mpn(tmpl, trusted=True)
        run_undoable(
            _ImportNodeCommand(payload, restore_persistent=False, seed_setup=True)
        )
        node = (mc.ls(type="mPyFile") or [])[-1]

        # P1: graphable in the Hypershade.
        self.assertIn(node, mc.ls(textures=True) or [])

        # P2: init namespace registered on the main thread, so a later
        # worker-thread swatch finds it instead of NameError -> black.
        sel = om.MSelectionList()
        sel.add(node)
        obj = sel.getDependNode(0)
        self.assertIsNotNone(ir.get_init_namespace_for_mobject(obj))


# ===========================================================================
# P3 -- Save (F5 / Save button) must push Viewport + OSL to VP2 immediately
# ===========================================================================
class TestForceViewportRefresh(unittest.TestCase):
    """A node with a Viewport / OSL tier (mPyFile) must, on Save, kick a VP2
    redraw -- ``setInternalValue`` already dgdirty's outColor when the source
    plug changes, but nothing calls ``cmds.refresh()``, so the textured
    surface stays stale until a timeline scrub. ``force_viewport_refresh``
    supplies the missing redraw."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile as W

        self.name = mc.createNode("mPyFile", name="vp")
        self.node = W(self.name)

    def _patch_refresh(self):
        """Patch executeDeferred to run synchronously + record cmds.refresh."""
        import maya.utils as mu

        calls = {"refresh": 0, "deferred": 0}
        orig_def = mu.executeDeferred
        orig_refresh = mc.refresh

        def fake_def(fn, *a, **k):
            calls["deferred"] += 1
            try:
                fn(*a, **k)
            except Exception:
                pass

        def fake_refresh(*a, **k):
            calls["refresh"] += 1

        mu.executeDeferred = fake_def
        mc.refresh = fake_refresh
        return calls, (mu, orig_def, orig_refresh)

    def _unpatch(self, saved):
        mu, orig_def, orig_refresh = saved
        mu.executeDeferred = orig_def
        mc.refresh = orig_refresh

    def test_refresh_fires_for_viewport_capable_node(self):
        from mpynode._base.eval_helpers import force_viewport_refresh

        calls, saved = self._patch_refresh()
        try:
            force_viewport_refresh(self.node)
        finally:
            self._unpatch(saved)
        self.assertGreaterEqual(calls["refresh"], 1)

    def test_noop_for_node_without_viewport_or_osl(self):
        """A node type with no Viewport/OSL tier must NOT trigger a VP2
        redraw on save (don't churn the viewport for plain DG nodes)."""
        from mpynode._base.eval_helpers import force_viewport_refresh

        class _Plain:
            def get_name(self):
                return "plain"
            # deliberately NO set_viewport_expression / set_osl_expression

        calls, saved = self._patch_refresh()
        try:
            force_viewport_refresh(_Plain())
        finally:
            self._unpatch(saved)
        self.assertEqual(calls["refresh"], 0)

    def test_never_raises(self):
        from mpynode._base.eval_helpers import force_viewport_refresh

        class _Bad:
            # Has the capability so force_viewport_refresh proceeds to get_name.
            def set_viewport_expression(self, _s):
                return True

            def get_name(self):
                raise RuntimeError("boom")

        force_viewport_refresh(_Bad())  # must swallow


# ===========================================================================
# P3 (OSL half) -- Save must recompile a wired Arnold aiOslShader
# ===========================================================================
class TestForceOslRefresh(unittest.TestCase):
    """The OSL tier does NOT render through VP2 -- it feeds an Arnold
    aiOslShader that only recompiles when OSLSceneModel re-runs. Save must
    therefore recompile any wired aiOslShader (and must NOT create one)."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile as W

        self.name = mc.createNode("mPyFile", name="oslnode")
        self.node = W(self.name)

    def test_noop_without_osl_tier(self):
        from mpynode._base.eval_helpers import force_osl_refresh

        class _Plain:
            def get_name(self):
                return "plain"

        force_osl_refresh(_Plain())  # no raise, no-op

    def test_recompile_returns_zero_and_creates_nothing_without_target(self):
        from mpynode._base.eval_helpers import force_osl_refresh
        from mpynode._common.osl import osl_targets

        self.node.set_osl_expression(
            "shader s(output color outColor = 0){ outColor = 0; }"
        )
        # No aiOslShader wired -> nothing to recompile, nothing created.
        self.assertEqual(osl_targets.recompile_osl_targets(self.name), 0)
        force_osl_refresh(self.node)  # must not raise / must not create
        self.assertEqual(mc.ls(type="aiOslShader") or [], [])

    def test_recompiles_wired_aioslshader(self):
        from mpynode._common.osl import osl_targets

        try:
            if not mc.pluginInfo("mtoa", q=True, loaded=True):
                mc.loadPlugin("mtoa")
        except Exception:
            self.skipTest("MtoA unavailable")
        if not mc.pluginInfo("mtoa", q=True, loaded=True):
            self.skipTest("MtoA unavailable")

        src = (
            "shader mpyfile_osl_test(\n"
            "    output color outColor = color(0.1, 0.2, 0.3))\n"
            "{\n"
            "    outColor = color(0.1, 0.2, 0.3);\n"
            "}\n"
        )
        self.node.set_osl_expression(src)
        shader = osl_targets.apply_osl_to_arnold(self.name)
        if not shader:
            self.skipTest("apply_osl_to_arnold did not compile (no OSL backend)")

        # a Save-driven recompile must push the edited source into the
        # shader's .code and re-run the compile.
        new_src = src.replace("0.3", "0.9")
        self.node.set_osl_expression(new_src)
        from mpynode._base.eval_helpers import force_osl_refresh

        force_osl_refresh(self.node)
        self.assertEqual(mc.getAttr(shader + ".code"), new_src)
        # it recompiled the existing shader, it did not spawn a second one.
        self.assertEqual(len(mc.ls(type="aiOslShader") or []), 1)


# ===========================================================================
# Colour management: like the canonical mPyFile example and a real Maya
# `file` node, sRGB textures must be linearized, not passed through raw.
# Raw sRGB output is ~2.3x too bright.
# ===========================================================================
class TestTemplateColorManagement(unittest.TestCase):
    """The bundled mPyFile TEMPLATE previously read images raw (uint8/255) and
    wrote those raw sRGB values straight to ``outColor``. The canonical default
    (``MPyFile.create()`` -> ``file_defaults._linearize``) and a stock Maya
    ``file`` node both convert sRGB -> scene-linear, so the template shaded
    ~2.3x brighter than the original example. The reader the templates call --
    now the FRAMEWORK loader, ``file_texture_ops.load_linear_pixels`` -- must
    linearize to match."""

    def setUp(self):
        from mpynode._api2.mpy_file import MPyFile

        self._barebones = MPyFile.BAREBONES_MODE
        MPyFile.BAREBONES_MODE = False
        mc.file(new=True, force=True)
        self.tmp = tempfile.mkdtemp()
        self.gray = os.path.join(self.tmp, "_solid128.png")
        _make_solid_png(self.gray, 128)            # sRGB 0.502
        self.raw = 128 / 255.0
        self.linear = _srgb_to_linear(self.raw)    # ~0.2159

    def tearDown(self):
        from mpynode._api2.mpy_file import MPyFile

        MPyFile.BAREBONES_MODE = self._barebones

    def test_read_image_returns_scene_linear(self):
        """The framework loader every template now calls must return scene-LINEAR
        pixels (sRGB linearized), matching the canonical reader -- not raw sRGB."""
        from mpynode._common.methods import file_texture_ops as tex

        arr = tex.load_linear_pixels(self.gray, 0, False,
                                     tex.kPreFilterGaussian, 1.0)
        self.assertIsNotNone(arr)
        got = float(arr[0, 0, 0])
        self.assertAlmostEqual(
            got, self.linear, delta=0.01,
            msg="load_linear_pixels must linearize sRGB->scene-linear "
                "(expected ~%.4f, got %.4f -- raw would be %.4f)"
                % (self.linear, got, self.raw),
        )
        # Alpha must pass through unchanged (linearization is RGB-only).
        self.assertAlmostEqual(float(arr[0, 0, 3]), 1.0, delta=1e-4)

    def test_read_image_matches_canonical_linearize(self):
        """Lock the invariant: the framework reader's value equals the canonical
        ``file_defaults._linearize`` for the SAME sRGB pixel (colorSpace=0)."""
        import numpy as np
        from mpynode._common.methods import file_texture_ops as tex
        from mpynode._defaults.file_defaults import DEFAULT_INIT_SOURCE

        tmpl = float(tex.load_linear_pixels(
            self.gray, 0, False, tex.kPreFilterGaussian, 1.0)[0, 0, 0])

        cns = {}
        exec(DEFAULT_INIT_SOURCE, cns)
        px = np.full((2, 2, 4), 128, dtype=np.uint8)
        px[..., 3] = 255
        canon = float(cns["_linearize"](px, 0)[0, 0, 0])

        self.assertAlmostEqual(tmpl, canon, delta=1e-4)

    def test_osl_tier_linearizes_srgb(self):
        """Arnold's OSL ``texture()`` returns RAW sRGB (verified by a real
        render -- it does NOT auto color-manage), so the template's OSL tier
        must apply the SAME sRGB->linear the Compute tier does, or the OSL
        render is ~2.3x too bright. Lock the conversion into the source."""
        from mpynode._demos.build_templates import FILE_OSL

        self.assertIn("srgb_to_linear", FILE_OSL)
        # the piecewise sRGB EOTF constants must be present...
        for tok in ("12.92", "0.055", "1.055", "2.4", "0.04045"):
            self.assertIn(tok, FILE_OSL, "OSL EOTF missing %r" % tok)
        # ...and applied to the sampled colour, before brightness/contrast
        # as in Compute.
        self.assertIn("c = srgb_to_linear(c)", FILE_OSL)
        # match the full code statement: "* brightness" also appears in a
        # comment, so a looser marker would be ambiguous.
        self.assertLess(
            FILE_OSL.index("c = srgb_to_linear(c)"),
            FILE_OSL.index("color bright = c * brightness"),
            "OSL must linearize before applying brightness/contrast",
        )

    def test_template_node_outColor_is_scene_linear(self):
        """End-to-end: a template-sourced mPyFile node's ``outColor`` (default
        brightness/contrast = identity) must be scene-linear, not raw sRGB."""
        from mpynode._demos.build_templates import FILE_INIT, FILE_COMPUTE
        from mpynode.wrappers.mpy_file import MPyFile

        f = MPyFile.create(name="cmNode", seed_defaults=False, as_texture=True)
        f.add_input_attr("brightness", "float", default_value=1.0)
        f.add_input_attr("contrast", "float", default_value=1.0)
        f.set_init_expression(FILE_INIT)
        f.set_compute_expression(FILE_COMPUTE)
        nm = f.get_name()
        mc.setAttr(nm + ".fileName", self.gray, type="string")
        mc.setAttr(nm + ".uCoord", 0.5)
        mc.setAttr(nm + ".vCoord", 0.5)
        mc.dgdirty(nm + ".outColor")
        out = mc.getAttr(nm + ".outColor")[0]
        self.assertAlmostEqual(
            out[0], self.linear, delta=0.01,
            msg="template node outColor must be scene-linear (~%.4f), got %.4f "
                "(raw sRGB would be %.4f -- 2.3x too bright)"
                % (self.linear, out[0], self.raw),
        )


# ===========================================================================
# Always-on time -- time1.outTime -> _timeIn on EVERY create path
# ===========================================================================
class TestAlwaysOnTimeWiring(unittest.TestCase):
    """``MPyFile.create`` wires the scene clock into the hidden ``_timeIn``
    plug so ``self.time`` is live for image-sequence expressions. The
    .mpn-import / template-gallery path builds the node with
    ``cmds.createNode`` inside ``deserialize_node`` and never runs
    ``create``, so a gallery-created node used to sit frozen at frame 0."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _timed(self, node):
        return mc.isConnected("time1.outTime", node + "._timeIn")

    def test_create_wires_time(self):
        """Regression guard on the path that already worked."""
        from mpynode.wrappers.mpy_file import MPyFile

        f = MPyFile.create(name="timedTex", seed_defaults=False)
        self.assertTrue(self._timed(f.get_name()))

    def test_deserialize_wires_time(self):
        from mpynode._common.io import mpn_io

        py_node = mpn_io.deserialize_node({"native_type": "mPyFile"})
        self.assertTrue(
            self._timed(py_node.get_name()),
            "deserialize_node must wire time1.outTime -> _timeIn so an "
            "imported mPyFile advances in time",
        )

    def test_template_create_wires_time(self):
        from mpynode._base.commands import _TemplateCreateCommand, run_undoable
        from mpynode._common.io import mpn_io

        tmpl = os.path.join(
            os.environ.get("MPYNODE_ROOT", ""),
            "templates/MPyFile/File Simple/template.mpn",
        )
        payload = mpn_io.load_mpn(tmpl, trusted=True)
        name = run_undoable(
            _TemplateCreateCommand(payload, "mPyFile", run_setup=False))
        self.assertTrue(
            self._timed(name),
            "the template-gallery create path must wire time1.outTime -> "
            "_timeIn",
        )

    def test_deserialize_does_not_clobber_an_authored_time_source(self):
        """A payload-created node gets the default wire, but a user-chosen
        upstream time source on an EXISTING node is never overwritten -- the
        hook only ever runs on the node deserialize just created."""
        from mpynode._common.io import mpn_io

        py_node = mpn_io.deserialize_node({"native_type": "mPyFile"})
        node = py_node.get_name()
        other = mc.createNode("time", name="altTime", skipSelect=True)
        mc.connectAttr(other + ".outTime", node + "._timeIn", force=True)
        # Re-wrapping / re-seeding the same node must not steal it back.
        mpn_io.apply_payload_to_node(py_node, {"native_type": "mPyFile"})
        self.assertFalse(self._timed(node))
        self.assertTrue(mc.isConnected(other + ".outTime", node + "._timeIn"))


class TestDerivedShaderOutputs(unittest.TestCase):
    """outTransparency / outSize complete the stock `file` node's output surface.

    Neither is authored by the compute -- a compute writes colour + alpha and the
    node DERIVES these -- so every pre-existing expression keeps working unchanged
    and the full-parity tail recognizer still sees a two-line default write. An
    explicit assignment still wins, which is what lets a template emit a generated
    alpha into a shader's .transparency."""

    def setUp(self):
        mc.file(new=True, force=True)
        self.tmp = tempfile.mkdtemp()
        self.png = os.path.join(self.tmp, "_solid128.png")
        _make_solid_png(self.png, 128)          # 4x4 solid grey

    def _node(self, compute=None):
        from mpynode.wrappers.mpy_file import MPyFile

        w = MPyFile.create(name="derOut#")
        mc.setAttr(w.get_name() + ".fileName", self.png, type="string")
        if compute is not None:
            w.set_compute_expression(compute)
        mc.dgdirty(w.get_name())
        return w.get_name()

    def test_plugs_registered_with_the_right_shape(self):
        n = self._node()
        self.assertTrue(mc.attributeQuery("outTransparency", node=n,
                                          usedAsColor=True))
        self.assertEqual(
            mc.attributeQuery("outTransparency", node=n, listChildren=True),
            ["outTransparencyR", "outTransparencyG", "outTransparencyB"])
        self.assertEqual(
            mc.attributeQuery("outSize", node=n, listChildren=True),
            ["outSizeX", "outSizeY"])
        # Outputs, not inputs: writable would let a user setAttr over compute.
        for a in ("outTransparency", "outSize"):
            self.assertFalse(mc.attributeQuery(a, node=n, writable=True))

    def test_default_compute_derives_transparency_from_alpha(self):
        """1 - alpha per channel, WITHOUT the compute mentioning it."""
        n = self._node(
            "buf = self.read_texture()\n"
            "r, g, b, a = self.sample_texture(buf, self.uvCoord[0], "
            "self.uvCoord[1])\n"
            "self.outColor = (r, g, b)\n"
            "self.outAlpha = 0.25\n")
        self.assertAlmostEqual(mc.getAttr(n + ".outAlpha"), 0.25, delta=1e-5)
        for c in mc.getAttr(n + ".outTransparency")[0]:
            self.assertAlmostEqual(c, 0.75, delta=1e-5)

    def test_default_compute_derives_size_from_the_image(self):
        n = self._node()
        self.assertEqual(
            tuple(int(v) for v in mc.getAttr(n + ".outSize")[0]), (4, 4))

    def test_explicit_assignment_wins_over_the_derivation(self):
        n = self._node(
            "buf = self.read_texture()\n"
            "r, g, b, a = self.sample_texture(buf, self.uvCoord[0], "
            "self.uvCoord[1])\n"
            "self.outColor = (r, g, b)\n"
            "self.outAlpha = a\n"
            "self.outTransparency = (0.25, 0.5, 0.75)\n"
            "self.outSize = (7.0, 9.0)\n")
        got = tuple(round(c, 4) for c in mc.getAttr(n + ".outTransparency")[0])
        self.assertEqual(got, (0.25, 0.5, 0.75))
        self.assertEqual(
            tuple(int(v) for v in mc.getAttr(n + ".outSize")[0]), (7, 9))

    def test_no_image_reports_zero_size_and_does_not_raise(self):
        from mpynode.wrappers.mpy_file import MPyFile

        w = MPyFile.create(name="blankOut#")
        mc.dgdirty(w.get_name())
        self.assertEqual(
            tuple(mc.getAttr(w.get_name() + ".outSize")[0]), (0.0, 0.0))

    def test_transparency_connects_to_a_shader(self):
        """The point of the plug: parent AND per-child, since Maya's legacy
        Software renderer pulls R/G/B individually."""
        n = self._node()
        lam = mc.shadingNode("lambert", asShader=True, name="derLam")
        mc.connectAttr(n + ".outTransparency", lam + ".transparency")
        self.assertTrue(mc.isConnected(n + ".outTransparency",
                                       lam + ".transparency"))
        lam2 = mc.shadingNode("lambert", asShader=True, name="derLam2")
        for c in "RGB":
            mc.connectAttr("%s.outTransparency%s" % (n, c),
                           "%s.transparency%s" % (lam2, c))
            self.assertTrue(mc.isConnected("%s.outTransparency%s" % (n, c),
                                           "%s.transparency%s" % (lam2, c)))

    def test_managed_output_names_come_from_the_ssot(self):
        """The dirty propagation, the user-output skip set and the no-refresh set
        all read one projection -- so a new output in FILE_TEXTURE_ATTRS reaches
        them without a hand-edited tuple going stale."""
        from mpynode._api2 import mpy_file as _n
        from mpynode._common.interface import file_texture_interface as _iface

        names = set(_iface.output_names())
        self.assertEqual(set(_n._MANAGED_OUTPUT_NAMES), names)
        for expect in ("outColor", "outColorR", "outAlpha",
                       "outTransparency", "outTransparencyB",
                       "outSize", "outSizeX", "outSizeY"):
            self.assertIn(expect, names)
        # Every one of them is a real plug on a real node.
        leaves = set(mc.listAttr(self._node()) or [])
        self.assertEqual(names - leaves, set())


if __name__ == "__main__":
    unittest.main()
