"""mPyFile expression-driven file-texture node (live) + viewport refresh + thread-safe inputs

Consolidated from: test_phase32_mpyfile.py, test_mpyfile_viewport_refresh.py, test_mpyfile_attr_refresh.py, test_mpyfile_user_input_threadsafe.py.
"""

from __future__ import annotations

# ===================== from test_phase32_mpyfile.py =====================
import os
import tempfile
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase32_mpyfile():
    standalone_init()
    ensure_plugins_loaded()


# Shipped default of the process-global BAREBONES_MODE flag, captured ONCE at
# import. Restoring to this -- not a hard-coded True -- keeps the flag clean for
# later modules (e.g. test_templates) that expect the shipped path.
from mpynode._api2.mpy_file import MPyFile as _MPyFileCls  # noqa: E402
from tests import _paths

_DEFAULT_BAREBONES = _MPyFileCls.BAREBONES_MODE
del _MPyFileCls


def _disable_barebones():
    """Switch MPyFile out of the BAREBONES_MODE fast path so the test
    exercises the user-expression / init-namespace / viewport-source
    chain. Tests that exercise the full mpynode integration should
    call this in their ``setUp``."""
    from mpynode._api2.mpy_file import MPyFile

    MPyFile.BAREBONES_MODE = False


def _restore_barebones():
    """Restore the SHIPPED default (not a hard-coded True), so the global
    flag is left clean for subsequently-run test modules."""
    from mpynode._api2.mpy_file import MPyFile

    MPyFile.BAREBONES_MODE = _DEFAULT_BAREBONES


def _pil_available() -> bool:
    try:
        import PIL.Image  # noqa: F401

        return True
    except ImportError:
        return False


def _ogs_render_available() -> bool:
    try:
        # Presence check only -- we never call ogsRender here.
        return hasattr(mc, "ogsRender")
    except Exception:
        return False


# In-repo test asset. The sibling MayaCustomFileNode copy is outside MPyNode and
# denied to mayapy by macOS TCC, so use the in-repo one the demo builder uses.
def _test_asset_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(_paths.SCRIPTS, "mpynode", "_demos", "data",
                        "test_grid.png")


# ===========================================================================
# Plug-surface tests
# ===========================================================================


class TestPlugSurface(unittest.TestCase):
    """Every customFileTexture attr is present on mPyFile."""

    def setUp(self):
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyFile", name="probe")

    def test_preset_inputs_exist(self):
        expected = (
            "fileName", "uCoord", "vCoord",
            "colorSpace", "preFilter", "preFilterKernel", "preFilterRadius",
            "filterMode", "maxAnisotropy", "mipmapMode",
            "mipLODBias", "minLOD", "maxLOD",
            "wrapModeU", "wrapModeV",
            "borderColorR", "borderColorG", "borderColorB",
        )
        for attr in expected:
            self.assertTrue(
                mc.attributeQuery(attr, node=self.node, exists=True),
                f"missing input attr: {attr}",
            )

    def test_preset_outputs_exist(self):
        for attr in ("outColor", "outColorR", "outColorG", "outColorB",
                     "outAlpha"):
            self.assertTrue(
                mc.attributeQuery(attr, node=self.node, exists=True),
                f"missing output attr: {attr}",
            )

    def test_internal_attrs_exist(self):
        for attr in ("_computeSource", "_inputAttrs", "_outputAttrs",
                     "_storedVarNames", "_storedVarsData", "debug_mode",
                     "_viewportSource"):
            self.assertTrue(
                mc.attributeQuery(attr, node=self.node, exists=True),
                f"missing internal attr: {attr}",
            )

    def test_colorspace_enum_has_25_entries(self):
        names = mc.attributeQuery(
            "colorSpace", node=self.node, listEnum=True
        ) or []
        # Maya returns ['a:b:c:...'] -- single-element list joined by ':'.
        joined = names[0] if names else ""
        n = len([s for s in joined.split(":") if s.strip()])
        self.assertEqual(n, 25)

    def test_default_color_space_is_zero(self):
        # 0 = "[Texture] sRGB Encoded Rec.709 (sRGB)"
        self.assertEqual(mc.getAttr(self.node + ".colorSpace"), 0)

    def test_default_prefilter_off(self):
        self.assertFalse(mc.getAttr(self.node + ".preFilter"))

    def test_default_filtermode_anisotropic(self):
        # 2 = Anisotropic. customFileTexture's ancestor used 1 = Linear, but
        # VP2 prefers 16x aniso for grazing-angle textures.
        self.assertEqual(mc.getAttr(self.node + ".filterMode"), 2)

    def test_default_max_anisotropy_16(self):
        self.assertEqual(mc.getAttr(self.node + ".maxAnisotropy"), 16)


# ===========================================================================
# Wrapper + default sources
# ===========================================================================


class TestWrapperAndDefaults(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.MPyFile = MPyFile
        self.f = MPyFile.create(name="probe")

    def test_create_returns_wrapper_with_name(self):
        self.assertEqual(self.f.get_name(), "probe")
        self.assertTrue(mc.objExists("probe"))

    def test_node_type_is_mPyFile(self):
        self.assertEqual(mc.nodeType("probe"), "mPyFile")

    def test_default_init_source_present(self):
        src = self.f.get_init_expression()
        self.assertTrue(src.strip(), "default init source should be seeded")
        for name in ("_load_linear_pixels", "_sample", "_linearize",
                     "_M_AP1_to_Rec709", "_acescct_eotf",
                     "_vp2_filter_for", "_upload_linear_texture"):
            self.assertIn(name, src)

    def test_default_compute_source_present(self):
        src = self.f.get_compute_expression()
        self.assertTrue(src.strip(), "default compute source should be seeded")
        self.assertIn("self.outColor", src)
        # Default Compute uses the blessed methods: readable, and compiles to
        # the same C++ as the inline _load_linear_pixels/_sample.
        self.assertIn("self.read_texture()", src)
        self.assertIn("self.sample_texture(", src)

    def test_default_viewport_source_present(self):
        src = self.f.get_viewport_expression()
        self.assertTrue(src.strip(), "default viewport source should be seeded")
        self.assertIn("self.shader", src)
        self.assertIn("_upload_linear_texture", src)

    def test_default_compute_returns_magenta_with_no_file(self):
        # sample_texture(buf=None) when the file is missing -> magenta.
        mc.setAttr(self.f.get_name() + ".uCoord", 0.5)
        mc.setAttr(self.f.get_name() + ".vCoord", 0.5)
        out = mc.getAttr(self.f.get_name() + ".outColor")[0]
        self.assertEqual(out, (1.0, 0.0, 1.0))

    def test_reseed_defaults(self):
        mc.setAttr(self.f.get_name() + "._computeSource", "", type="string")
        self.f.set_init_expression("")
        self.f.set_viewport_expression("")
        self.f.reseed_defaults()
        self.assertTrue(self.f.get_init_expression().strip())
        self.assertTrue(self.f.get_compute_expression().strip())
        self.assertTrue(self.f.get_viewport_expression().strip())

    def test_seed_defaults_false_leaves_sources_empty(self):
        bare = self.MPyFile.create(name="bare", seed_defaults=False)
        self.assertEqual(bare.get_init_expression(), "")
        # _computeSource plug default is "None" string; treat as empty.
        self.assertIn(bare.get_compute_expression(), ("", "None"))
        self.assertEqual(bare.get_viewport_expression(), "")

    def test_as_texture_creates_place2dtexture(self):
        # shadingNode -asTexture auto-creates a place2dTexture. Even when it is
        # not pre-connected to uvCoord (Maya 2024 standalone), the node must
        # classify as a 2d texture so Hypershade picks it up.
        cls = mc.getClassification("mPyFile")
        self.assertTrue(any("texture/2d" in c for c in cls))


# ===========================================================================
# User-edited sources (DG path)
# ===========================================================================


class TestUserEditedSources(unittest.TestCase):
    """The whole point of mPyFile: the user can replace any code tier."""

    def setUp(self):
        _disable_barebones()
        self.addCleanup(_restore_barebones)
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.MPyFile = MPyFile

    def test_user_overrides_compute_with_constant(self):
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_init_expression("")
        f.set_compute_expression(
            "self.outColor = (0.25, 0.5, 0.75)\nself.outAlpha = 0.42"
        )
        mc.setAttr(f.get_name() + ".uCoord", 0.0)
        out = mc.getAttr(f.get_name() + ".outColor")[0]
        self.assertAlmostEqual(out[0], 0.25, places=5)
        self.assertAlmostEqual(out[1], 0.5, places=5)
        self.assertAlmostEqual(out[2], 0.75, places=5)
        self.assertAlmostEqual(mc.getAttr(f.get_name() + ".outAlpha"), 0.42, places=5)

    def test_user_compute_reads_preset_plug_via_self(self):
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_init_expression("")
        f.set_compute_expression(
            "v = float(self.colorSpace) / 24.0\n"
            "self.outColor = (v, v, v)\nself.outAlpha = 1.0"
        )
        mc.setAttr(f.get_name() + ".colorSpace", 12)  # AdobeRGB scene-linear
        out = mc.getAttr(f.get_name() + ".outColor")[0]
        self.assertAlmostEqual(out[0], 12.0 / 24.0, places=4)

    def test_init_source_helper_visible_to_compute(self):
        # Define a kernel in Init, call it from Compute -- the core pattern.
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_init_expression("def my_color(v):\n    return (v, v, v)\n")
        f.set_compute_expression(
            "r, g, b = my_color(float(self.preFilterRadius) / 8.0)\n"
            "self.outColor = (r, g, b)\nself.outAlpha = 1.0"
        )
        mc.setAttr(f.get_name() + ".preFilterRadius", 4.0)
        out = mc.getAttr(f.get_name() + ".outColor")[0]
        self.assertAlmostEqual(out[0], 0.5, places=4)
        self.assertAlmostEqual(out[1], 0.5, places=4)
        self.assertAlmostEqual(out[2], 0.5, places=4)

    def test_viewport_source_round_trips(self):
        # Viewport EXEC needs a VP2 frame; all we can check headless is that
        # the plug round-trips and the cached code object recompiles.
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_viewport_expression("# my viewport\npass\n")
        self.assertIn("my viewport", f.get_viewport_expression())
        f.set_viewport_expression("# replaced\npass\n")
        self.assertIn("replaced", f.get_viewport_expression())
        self.assertNotIn("my viewport", f.get_viewport_expression())

    def test_viewport_stored_var_persists_across_calls(self):
        """Regression: the Viewport tier must READ stored vars back across calls
        (like Compute), so a viewport source that keeps per-frame state (e.g. a
        simulation) advances on scrub instead of re-running from scratch.

        Bug: ``runViewport`` guarded the read behind ``if stored_vars_str:`` --
        empty in a live session (the plug is cleared after load) AND always ""
        on the VP2 render thread -- so every viewport call started with ``{}``
        and stored state never persisted. (Compute reads unconditionally, which
        is why headless Compute-driven tests passed while the GUI froze.)
        """
        import maya.api.OpenMaya as om
        from mpynode._common.storedvars import stored_var_store
        f = self.MPyFile.create(name="vpState", seed_defaults=False)
        f.set_init_expression("")
        # With a working read-back the third call leaves counter == 3, not 1.
        f.set_viewport_expression(
            "n = getattr(self, 'counter', 0)\nself.counter = n + 1\n")
        name = f.get_name()
        sel = om.MSelectionList()
        sel.add(name)
        mobj = sel.getDependNode(0)
        mpx = om.MFnDependencyNode(mobj).userNode()
        for _ in range(3):
            mpx.runViewport(None, None)            # shader/mappings unused here
        counter = stored_var_store.load_for_compute(mobj, "").get("counter")
        self.assertEqual(
            counter, 3,
            "viewport stored var did not persist across calls (got %r) -- the "
            "Viewport tier is not reading stored vars back" % counter)


# ===========================================================================
# Recipe registration
# ===========================================================================


class TestRecipeRegistration(unittest.TestCase):

    def test_mpyfile_recipe_registered(self):
        from mpynode._common.util.recipes import get_recipe

        r = get_recipe("mPyFile")
        self.assertIsNotNone(r, "mPyFile recipe must be registered")

    def test_all_inputs_are_real_plugs(self):
        from mpynode._common.util.recipes import get_recipe

        r = get_recipe("mPyFile")
        for entry in r.inputs:
            self.assertNotEqual(
                entry.source_plug, "",
                f"mPyFile input {entry.name} must be a real plug "
                f"(empty source_plug = synthetic)",
            )

    def test_all_outputs_are_real_plugs(self):
        from mpynode._common.util.recipes import get_recipe

        r = get_recipe("mPyFile")
        for entry in r.outputs:
            self.assertNotEqual(
                entry.target_plug, "",
                f"mPyFile output {entry.name} must be a real plug",
            )

    def test_recipe_lists_outColor_and_outAlpha(self):
        from mpynode._common.util.recipes import get_recipe

        r = get_recipe("mPyFile")
        out_names = {e.name for e in r.outputs}
        self.assertIn("outColor", out_names)
        self.assertIn("outAlpha", out_names)


# ===========================================================================
# Node-registry + node-designer surface
# ===========================================================================


class TestNodeRegistry(unittest.TestCase):

    def test_mpyfile_in_registry(self):
        from mpynode._node_registry import REGISTRY, get_spec

        self.assertIn("mPyFile", REGISTRY)
        spec = get_spec("mPyFile")
        self.assertEqual(spec.wrapper_module, "mpynode.wrappers.mpy_file")
        self.assertEqual(spec.wrapper_class_name, "MPyFile")

    def test_wrap_node_returns_mpyfile(self):
        from mpynode._node_registry import wrap_node

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers.mpy_file import MPyFile

        # Use shadingNode (matches the wrapper's own create()).
        node = mc.shadingNode("mPyFile", asTexture=True, name="reg_probe")
        wrapper = wrap_node(node, "mPyFile")
        self.assertIsInstance(wrapper, MPyFile)


# ===========================================================================
# Viewport tab visibility (Node Designer plumbing)
# ===========================================================================


class TestViewportTabVisibility(unittest.TestCase):
    """Sanity-check that the mixin chain works -- the Node Designer
    keys the Viewport tab off hasattr(wrapper, 'set_viewport_expression').
    """

    def test_mpyfile_wrapper_has_viewport_source_api(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers.mpy_file import MPyFile

        f = MPyFile.create(name="probe", seed_defaults=False)
        self.assertTrue(hasattr(f, "set_viewport_expression"))
        self.assertTrue(hasattr(f, "get_viewport_expression"))
        self.assertTrue(hasattr(f, "clear_viewport_expression"))
        self.assertTrue(hasattr(f, "has_viewport_expression"))

    def test_other_node_types_lack_viewport_source_api(self):
        # The Viewport tab is opt-in via ViewportSourceMixin; if it leaked into
        # the universal mixin set the tab would show on every node.
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        n = MPyNode.create(name="probe_n")
        self.assertFalse(
            hasattr(n, "set_viewport_expression"),
            "mPyNode should NOT have set_viewport_expression (opt-in only)",
        )


# ===========================================================================
# Source-error resilience
# ===========================================================================


class TestSourceErrorResilience(unittest.TestCase):
    """Bad user code must not crash Maya. Errors are surfaced via stderr
    and outputs fall back to a sensible default."""

    def setUp(self):
        _disable_barebones()
        self.addCleanup(_restore_barebones)
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.MPyFile = MPyFile

    def test_compute_syntax_error_keeps_last_good(self):
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_init_expression("")
        f.set_compute_expression("self.outColor = (0.1, 0.2, 0.3)\nself.outAlpha = 1.0")
        before = mc.getAttr(f.get_name() + ".outColor")[0]
        # safe_compile keeps the previous code object on a syntax error.
        mc.setAttr(f.get_name() + "._computeSource", "definitely not python syntax!!!!",
                   type="string")
        mc.dgdirty(f.get_name())
        after = mc.getAttr(f.get_name() + ".outColor")[0]
        self.assertEqual(before, after)

    def test_runtime_error_does_not_crash(self):
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_init_expression("")
        f.set_compute_expression(
            "raise RuntimeError('boom')\n"
            "self.outColor = (0.5, 0.5, 0.5)\nself.outAlpha = 1.0"
        )
        # Just calling getAttr should not raise.
        out = mc.getAttr(f.get_name() + ".outColor")
        self.assertIsNotNone(out)


# ===========================================================================
# PIL-dependent file-load tests (skip on Maya 2024 mayapy without PIL)
# ===========================================================================


@unittest.skipUnless(_pil_available(), "PIL not installed in this mayapy")
class TestFileLoadAndSampling(unittest.TestCase):
    """End-to-end DG-compute sampling against an on-disk test grid.

    Mirrors customFileTexture's test_custom_file_texture.py expectations
    for the quadrant-sampled colors of test_grid.png.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        asset = _test_asset_path()
        self.assertTrue(
            os.path.isfile(asset),
            f"shared test asset missing: {asset}",
        )
        self.f = MPyFile.create(name="probe")
        mc.setAttr(self.f.get_name() + ".fileName", asset, type="string")

    def test_sample_center_returns_finite_color(self):
        mc.setAttr(self.f.get_name() + ".uCoord", 0.5)
        mc.setAttr(self.f.get_name() + ".vCoord", 0.5)
        out = mc.getAttr(self.f.get_name() + ".outColor")[0]
        # not magenta (the no-file fallback), and every channel in [0, 1].
        self.assertNotEqual(out, (1.0, 0.0, 1.0))
        for c in out:
            self.assertTrue(0.0 <= c <= 1.0, f"channel out of range: {c}")

    def test_prefilter_on_vs_off_changes_result(self):
        # (0.80, 0.46) lands on a white grid line where the blur pulls in
        # coloured neighbours (delta ~0.57); a flat cell interior such as
        # (0.40, 0.40) is invariant under the blur for this image.
        mc.setAttr(self.f.get_name() + ".uCoord", 0.8)
        mc.setAttr(self.f.get_name() + ".vCoord", 0.46)

        mc.setAttr(self.f.get_name() + ".preFilter", False)
        off = mc.getAttr(self.f.get_name() + ".outColor")[0]

        mc.setAttr(self.f.get_name() + ".preFilter", True)
        mc.setAttr(self.f.get_name() + ".preFilterRadius", 4.0)
        on = mc.getAttr(self.f.get_name() + ".outColor")[0]

        max_delta = max(abs(off[i] - on[i]) for i in range(3))
        self.assertGreater(
            max_delta, 0.001,
            f"pre-filter on vs off produced identical samples: {off} vs {on}",
        )


# ===========================================================================
# Numpy-only in-memory test (works in Maya 2024 too)
# ===========================================================================


class TestInMemoryInitOverride(unittest.TestCase):
    """Override the Init source to provide an in-memory _load_linear_pixels
    that returns a numpy gradient. Exercises the full bridge without
    requiring PIL.
    """

    def setUp(self):
        _disable_barebones()
        self.addCleanup(_restore_barebones)
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.MPyFile = MPyFile

    def test_compute_uses_init_provided_pixels(self):
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_init_expression(
            "import numpy as np\n"
            "def _sample(pix, u, v, *_):\n"
            "    return (float(u), float(v), 0.0, 1.0)\n"
            "def _load_linear_pixels(*_a, **_kw):\n"
            "    return np.zeros((1, 1, 4), dtype=np.float32)\n"
        )
        f.set_compute_expression(
            "linear = _load_linear_pixels(self.fileName, int(self.colorSpace),"
            " bool(self.preFilter), int(self.preFilterKernel),"
            " float(self.preFilterRadius))\n"
            "u, v = self.uvCoord\n"
            "r, g, b, a = _sample(linear, u, v, 0, 0, (0,0,0))\n"
            "self.outColor = (r, g, b)\n"
            "self.outAlpha = a\n"
        )
        mc.setAttr(f.get_name() + ".uCoord", 0.3)
        mc.setAttr(f.get_name() + ".vCoord", 0.7)
        out = mc.getAttr(f.get_name() + ".outColor")[0]
        self.assertAlmostEqual(out[0], 0.3, places=5)
        self.assertAlmostEqual(out[1], 0.7, places=5)
        self.assertAlmostEqual(out[2], 0.0, places=5)


# ===========================================================================
# Hypershade Materials-tab swatch regression
# ===========================================================================


class TestSwatchAffects(unittest.TestCase):
    """Maya's legacy Software renderer (used for the Hypershade
    Materials-tab swatch) pulls outColorR / outColorG / outColorB
    individually instead of the compound outColor plug. If those
    children aren't in the ``attributeAffects`` declarations, Maya
    leaves them clean when uvCoord changes -- compute() never re-runs
    and the swatch renders BLACK even when the viewport (which uses
    the compound outColor through the VP2 fragment) looks correct.

    customFileTexture declares affects on every child explicitly; we
    must match that exactly."""

    def setUp(self):
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyFile", name="probe")

    def test_outColor_children_are_in_affects_chain(self):
        """Each outColor child must be affected by uCoord / vCoord /
        fileName -- otherwise Maya's Materials-tab swatch renders
        black. ``cmds.affects(<output_plug>, node)`` returns the list
        of inputs that affect that output (forward direction)."""
        for child in ("outColorR", "outColorG", "outColorB"):
            sources = mc.affects(child, self.node) or []
            for required in ("uCoord", "vCoord", "fileName",
                             "colorSpace", "preFilter"):
                self.assertIn(
                    required, sources,
                    f"{child!r} must be affected by {required!r} -- "
                    f"without this Maya's Materials-tab swatch renders "
                    f"BLACK. Check the outs tuple in "
                    f"MPyFile.initializer (each child plug must be "
                    f"listed explicitly).",
                )

    def test_outAlpha_in_affects_chain(self):
        sources = mc.affects("outAlpha", self.node) or []
        for required in ("uCoord", "vCoord", "fileName"):
            self.assertIn(required, sources)

    def test_outColor_parent_in_affects_chain(self):
        # The parent must stay reachable so VP2 and compound consumers still
        # see the dirty propagation.
        sources = mc.affects("outColor", self.node) or []
        self.assertIn("uvCoord", sources)
        self.assertIn("fileName", sources)


# ===========================================================================
# attributeAffects graph must mirror customFileTexture's exactly
# ===========================================================================


class TestAttributeAffectsMatchesCustomFileTexture(unittest.TestCase):
    """Maya 2026's VP2 fragment compiler inspects the
    ``attributeAffects`` graph for shader-parameter binding hints.
    Listing a string-typed plug (e.g. ``_computeSource``) as affecting a
    color output causes the binding to silently fail at render time:
    ``setParameter map`` succeeds at the API level but the fragment
    uses an unbound texture, so the viewport renders white and
    Hypershade swatches render black. customFileTexture works
    because it only lists numeric inputs in attributeAffects.

    The fix is to keep the ``_computeSource`` / ``_viewportSource`` plugs
    on the node (we need them for the user-Viewport path) but route
    their dirty propagation through ``setInternalValue`` instead of
    ``attributeAffects``. This test catches a regression by asserting
    no string-typed plugs ever end up in the outColor affects chain.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyFile", name="probe_aff")

    def _affects(self, output_plug):
        return set(mc.affects(output_plug, self.node) or [])

    def test_expression_does_not_affect_outColor(self):
        affected_by = self._affects("outColor")
        self.assertNotIn(
            "_computeSource", affected_by,
            "expression must NOT be in outColor's affects graph -- "
            "Maya 2026 VP2 fragment compiler rejects string-affects-color "
            "and silently disables texture binding (white viewport, "
            "black Hypershade swatches).",
        )

    def test_viewport_source_does_not_affect_outColor(self):
        affected_by = self._affects("outColor")
        self.assertNotIn("_viewportSource", affected_by)

    def test_uvFilterSize_not_in_affects(self):
        # customFileTexture omits uvFilterSize and we match it: it is a
        # GPU-sampler-only input and drives no CPU-level sampling.
        affected_by = self._affects("outColor")
        self.assertNotIn("uvFilterSize", affected_by)
        self.assertNotIn("uvFilterSizeX", affected_by)
        self.assertNotIn("uvFilterSizeY", affected_by)

    def test_essential_inputs_still_in_affects(self):
        # the inputs that SHOULD propagate dirty must survive.
        affected_by = self._affects("outColor")
        for required in ("uCoord", "vCoord", "fileName",
                         "colorSpace", "preFilter"):
            self.assertIn(
                required, affected_by,
                f"{required!r} must remain in outColor's affects "
                f"chain so Maya re-evaluates the texture when it "
                f"changes.",
            )


# ===========================================================================
# Per-child outColor pull (what Maya's Hypershade Materials-tab swatch does)
# ===========================================================================


class TestPerChildPull(unittest.TestCase):
    """Maya's legacy Software renderer pulls outColorR / outColorG /
    outColorB individually instead of the compound outColor. The
    bridge must drive compute() for each child pull and return the
    matching channel value -- otherwise the Materials-tab swatch
    renders BLACK.

    The fix is two-pronged:
      1. attributeAffects lists every output child (so the dirty
         state propagates through the plug tree).
      2. MPyFile.compute pre-populates ``self.X`` from the data block
         directly so the user expression can resolve preset plug
         values on Maya's swatch worker thread (where PlugProxy /
         MFnDependencyNode walks aren't guaranteed safe).
    """

    def setUp(self):
        _disable_barebones()
        self.addCleanup(_restore_barebones)
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        f = MPyFile.create(name="probe", seed_defaults=False)
        # Skip init / file load -- a constant colour isolates the child pull.
        f.set_init_expression("")
        f.set_compute_expression(
            "self.outColor = (0.10, 0.55, 0.90)\n"
            "self.outAlpha = 0.42\n"
        )
        self.f = f

    def test_each_outColor_child_returns_its_channel(self):
        self.assertAlmostEqual(
            mc.getAttr(self.f.get_name() + ".outColorR"), 0.10, places=4,
            msg="outColorR must return the R channel (Materials swatch fix)",
        )
        self.assertAlmostEqual(
            mc.getAttr(self.f.get_name() + ".outColorG"), 0.55, places=4,
            msg="outColorG must return the G channel (Materials swatch fix)",
        )
        self.assertAlmostEqual(
            mc.getAttr(self.f.get_name() + ".outColorB"), 0.90, places=4,
            msg="outColorB must return the B channel (Materials swatch fix)",
        )

    def test_outAlpha_returns_user_value(self):
        self.assertAlmostEqual(
            mc.getAttr(self.f.get_name() + ".outAlpha"), 0.42, places=4
        )

    def test_compound_outColor_matches_children(self):
        rgb = mc.getAttr(self.f.get_name() + ".outColor")[0]
        r = mc.getAttr(self.f.get_name() + ".outColorR")
        g = mc.getAttr(self.f.get_name() + ".outColorG")
        b = mc.getAttr(self.f.get_name() + ".outColorB")
        self.assertAlmostEqual(rgb[0], r, places=4)
        self.assertAlmostEqual(rgb[1], g, places=4)
        self.assertAlmostEqual(rgb[2], b, places=4)

    def test_preset_plug_values_reach_user_expression(self):
        """The user expression must be able to read self.fileName /
        self.colorSpace / self.uvCoord / etc. without going through
        the (non-thread-safe) plug tree. Verifies the data-block
        pre-population landed for every preset plug."""
        from mpynode.wrappers.mpy_file import MPyFile

        f = MPyFile.create(name="probe2", seed_defaults=False)
        f.set_init_expression("")
        f.set_compute_expression(
            "import numpy as _np\n"
            "u, v = self.uvCoord\n"
            "border = _np.asarray(self.borderColor, dtype=_np.float32)\n"
            "# Encode every preset plug we care about into outColor +\n"
            "# outAlpha so the test can read them back.\n"
            "self.outColor = (\n"
            "    float(self.colorSpace) / 100.0,\n"
            "    float(self.preFilterRadius) / 100.0,\n"
            "    float(u),\n"
            ")\n"
            "self.outAlpha = float(v)\n"
        )
        mc.setAttr(f.get_name() + ".colorSpace", 5)        # picked an unusual value
        mc.setAttr(f.get_name() + ".preFilterRadius", 3.5)
        mc.setAttr(f.get_name() + ".uCoord", 0.25)
        mc.setAttr(f.get_name() + ".vCoord", 0.75)
        rgb = mc.getAttr(f.get_name() + ".outColor")[0]
        self.assertAlmostEqual(rgb[0], 5 / 100.0, places=4,
                               msg="self.colorSpace must reach the expression")
        self.assertAlmostEqual(rgb[1], 3.5 / 100.0, places=4,
                               msg="self.preFilterRadius must reach the expression")
        self.assertAlmostEqual(rgb[2], 0.25, places=4,
                               msg="self.uvCoord[0] must reach the expression")
        self.assertAlmostEqual(
            mc.getAttr(f.get_name() + ".outAlpha"), 0.75, places=4,
            msg="self.uvCoord[1] must reach the expression"
        )


# ===========================================================================
# VP2 render test (skip when no GPU / ogsRender is unsafe)
# ===========================================================================


@unittest.skipUnless(_pil_available(), "PIL not installed in this mayapy")
@unittest.skipUnless(_ogs_render_available(),
                     "cmds.ogsRender not available in this mayapy")
class TestVP2Render(unittest.TestCase):
    """Smoke-test that connecting an mPyFile into a Lambert and rendering
    via ogsRender succeeds. Doesn't assert pixel values (machines without
    a real GPU produce different output) -- just that the call returns
    a valid image file."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        asset = _test_asset_path()
        if not os.path.isfile(asset):
            self.skipTest(f"shared asset missing: {asset}")
        self.f = MPyFile.create(name="probe")
        mc.setAttr(self.f.get_name() + ".fileName", asset, type="string")

        plane = mc.polyPlane(name="texPlane", w=2, h=2, sx=1, sy=1)[0]
        mc.connectAttr(self.f.get_name() + ".outColor", "lambert1.color", force=True)
        mc.sets(plane, edit=True, forceElement="initialShadingGroup")
        self.plane = plane

    def test_ogsrender_does_not_crash(self):
        out_path = os.path.join(tempfile.gettempdir(), "mpyfile_ogs.png")
        try:
            mc.setAttr("defaultRenderGlobals.imageFormat", 32)  # PNG
            mc.ogsRender(camera="persp", width=32, height=32)
        except Exception as exc:
            self.skipTest(f"ogsRender unavailable in this environment: {exc}")
        # No assertion on pixel values -- this is a smoke test.


# ===========================================================================
# Cache hot-path regression (Hypershade swatch perf)
# ===========================================================================


class TestLoadLinearPixelsCache(unittest.TestCase):
    """Ensure the default Init source caches the linearized pixel
    buffer so Hypershade's per-pixel swatch generator doesn't freeze
    Maya. Without the cache, every compute() call re-reads + decodes
    the PNG (~25 ms each for a 1024x1024 image), so a 64x64 swatch
    would take 100+ seconds; with the cache it's ~0.5s.

    The test exercises the cache by reading outColor many times --
    if the per-call cost balloons, the user's interactive session
    will hang."""

    def setUp(self):
        _disable_barebones()
        self.addCleanup(_restore_barebones)
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.MPyFile = MPyFile

    def test_repeated_compute_is_fast_after_first_read(self):
        # The cache pattern works with or without PIL, so use an in-memory
        # override and the test also runs on Maya 2024 mayapy (no PIL).
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_init_expression(
            "import numpy as np\n"
            "_CALLS = [0]\n"
            "def _expensive_load(path, *_a, **_kw):\n"
            "    _CALLS[0] += 1\n"
            "    return np.zeros((512, 512, 4), dtype=np.float32)\n"
            "_CACHE = {}\n"
            "def _load_linear_pixels(path, cs_index, prefilter, kernel, radius):\n"
            "    key = (path, int(cs_index), bool(prefilter), int(kernel),\n"
            "           round(float(radius), 1) if radius else 0.0)\n"
            "    if key in _CACHE:\n"
            "        return _CACHE[key]\n"
            "    _CACHE[key] = _expensive_load(path)\n"
            "    return _CACHE[key]\n"
            "def _sample(pix, u, v, *_a, **_kw):\n"
            "    return (float(u), float(v), 0.0, 1.0)\n"
        )
        f.set_compute_expression(
            "linear = _load_linear_pixels(self.fileName,"
            "    int(self.colorSpace), bool(self.preFilter),"
            "    int(self.preFilterKernel), float(self.preFilterRadius))\n"
            "u, v = self.uvCoord\n"
            "r, g, b, a = _sample(linear, u, v)\n"
            "self.outColor = (r, g, b)\n"
            "self.outAlpha = a\n"
        )
        mc.setAttr(f.get_name() + ".fileName", "/tmp/fake.png", type="string")

        # Sweep many UVs -- mimics what Hypershade's swatch generator does.
        N = 16
        for i in range(N):
            for j in range(N):
                mc.setAttr(f.get_name() + ".uCoord", i / float(N))
                mc.setAttr(f.get_name() + ".vCoord", j / float(N))
                mc.getAttr(f.get_name() + ".outColor")

        from mpynode._common.lifecycle import init_registry
        from mpynode._common.lifecycle.init_registry import _NODE_INIT_NS
        uuid = init_registry._node_uuid_from_name(f.get_name())
        ns = _NODE_INIT_NS.get(uuid)
        self.assertIsNotNone(ns, "init namespace was not registered")
        calls = ns["_CALLS"][0]
        # The cache key depends on settings, not UV, so N*N = 256 compute
        # calls should map to a single expensive load.
        self.assertLessEqual(
            calls, 2,
            f"_load_linear_pixels cache regressed: {calls} expensive "
            f"loads for {N*N} compute calls (expected <= 2; > 2 means "
            f"Hypershade will hang)",
        )

    def test_default_init_caches_load_linear_pixels(self):
        """Verify the SHIPPED default Init source contains the cache
        scaffolding. Catches a regression where someone removes the
        cache from the default."""
        f = self.MPyFile.create(name="probe")  # seed_defaults=True
        src = f.get_init_expression()
        self.assertIn(
            "_LINEAR_CACHE",
            src,
            "default Init source must declare _LINEAR_CACHE (the "
            "Hypershade-swatch performance fix). If you intentionally "
            "renamed it, update this test.",
        )
        self.assertIn(
            "cache_key",
            src,
            "default Init source must compute a cache_key inside "
            "_load_linear_pixels.",
        )


# ===========================================================================
# BAREBONES_MODE bisection sanity checks
# ===========================================================================


class TestBarebonesMode(unittest.TestCase):
    """Verify the BAREBONES inline path produces non-default colours,
    works without ANY user-expression / init-namespace / viewport-source
    state, and matches customFileTexture's structure.

    Skipped when PIL is missing (Maya 2024 mayapy lacks PIL; the
    BAREBONES path returns magenta in that case as a fallback)."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode._api2.mpy_file import MPyFile as _MPxClass

        _MPxClass.BAREBONES_MODE = True
        # Restore the shipped default (not a hard-coded True) so this class
        # cannot leak BAREBONES_MODE into later test modules.
        self.addCleanup(
            lambda: setattr(_MPxClass, "BAREBONES_MODE", _DEFAULT_BAREBONES)
        )

        self.MPyFile = MPyFile

    def test_barebones_compute_returns_magenta_without_file(self):
        """No fileName -> _bb_load_linear_pixels returns None ->
        _bb_sample returns magenta. customFileTexture behaves the
        same way."""
        f = self.MPyFile.create(name="probe_bb1", seed_defaults=False)
        # Clear fileName so _bb_load_linear_pixels bails.
        mc.setAttr(f.get_name() + ".fileName", "", type="string")
        mc.setAttr(f.get_name() + ".uCoord", 0.5)
        mc.setAttr(f.get_name() + ".vCoord", 0.5)
        rgb = mc.getAttr(f.get_name() + ".outColor")[0]
        self.assertEqual(rgb, (1.0, 0.0, 1.0),
                         msg="BAREBONES no-file should return magenta")

    def test_barebones_ignores_user_expression(self):
        """User-expression edits MUST NOT affect compute() while
        BAREBONES_MODE is on -- that's the whole point of the bisection
        fast path. Even after setting a bogus expression, the inline
        customFileTexture math runs."""
        f = self.MPyFile.create(name="probe_bb2", seed_defaults=False)
        # A broken expression would warn in user-expression mode; in
        # BAREBONES mode the plug is never consulted.
        mc.setAttr(f.get_name() + "._computeSource",
                   "raise RuntimeError('user expr should NOT run')",
                   type="string")
        mc.setAttr(f.get_name() + ".fileName", "", type="string")
        rgb = mc.getAttr(f.get_name() + ".outColor")[0]
        # Magenta = the inline path took over.
        self.assertEqual(rgb, (1.0, 0.0, 1.0))

    @unittest.skipUnless(_pil_available(),
                         "PIL not installed in this mayapy")
    def test_barebones_samples_actual_texture(self):
        """With a real file + PIL available, the BAREBONES path
        samples test_grid pixel-by-pixel just like customFileTexture."""
        f = self.MPyFile.create(name="probe_bb3", seed_defaults=False)
        asset = _test_asset_path()
        if not os.path.isfile(asset):
            self.skipTest(f"shared asset missing: {asset}")
        mc.setAttr(f.get_name() + ".fileName", asset, type="string")

        seen = set()
        for u, v in [(0.0, 0.0), (0.25, 0.25), (0.5, 0.5),
                     (0.75, 0.75), (0.95, 0.95)]:
            mc.setAttr(f.get_name() + ".uCoord", u)
            mc.setAttr(f.get_name() + ".vCoord", v)
            mc.dgdirty(f.get_name() + ".outColor")
            rgb = mc.getAttr(f.get_name() + ".outColor")[0]
            seen.add(tuple(round(c, 3) for c in rgb))
        self.assertGreaterEqual(
            len(seen), 3,
            "BAREBONES compute should return varying colours across "
            f"different UVs, got {seen}",
        )

    def test_full_path_engages_when_toggled_off(self):
        """When BAREBONES_MODE is False, the user expression IS
        respected. This is the sanity check that the bisection toggle
        actually toggles."""
        from mpynode._api2.mpy_file import MPyFile as _MPxClass
        _MPxClass.BAREBONES_MODE = False

        f = self.MPyFile.create(name="probe_bb4", seed_defaults=False)
        f.set_init_expression("")
        f.set_compute_expression(
            "self.outColor = (0.11, 0.22, 0.33)\nself.outAlpha = 0.42\n"
        )
        mc.setAttr(f.get_name() + ".uCoord", 0.7)
        rgb = mc.getAttr(f.get_name() + ".outColor")[0]
        self.assertAlmostEqual(rgb[0], 0.11, places=4)
        self.assertAlmostEqual(rgb[1], 0.22, places=4)
        self.assertAlmostEqual(rgb[2], 0.33, places=4)


# ===========================================================================
# User-added output attrs
# ===========================================================================


class TestUserAddedOutputs(unittest.TestCase):
    """A user-added OUTPUT attr must be computed + reactive to a
    user-added INPUT, just like mPyNode -- not only outColor/outAlpha."""

    def setUp(self):
        _disable_barebones()
        self.addCleanup(_restore_barebones)
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.MPyFile = MPyFile

    def test_user_output_computes_and_reacts(self):
        f = self.MPyFile.create(name="probe", seed_defaults=False)
        f.set_init_expression("")
        f.add_input_attr("uin", "float")
        f.add_output_attr("uout", "float")
        f.set_compute_expression(
            "self.uout = self.uin * 2.0\n"
            "self.outColor = (0.0, 0.0, 0.0)\nself.outAlpha = 1.0"
        )
        nm = f.get_name()
        mc.setAttr(nm + ".uin", 3.0)
        self.assertAlmostEqual(mc.getAttr(nm + ".uout"), 6.0, places=4)
        mc.setAttr(nm + ".uin", 10.0)
        self.assertAlmostEqual(mc.getAttr(nm + ".uout"), 20.0, places=4)


# ===================== from test_mpyfile_viewport_refresh.py =====================
import unittest

import maya.api.OpenMaya as om
import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__mpyfile_viewport_refresh():
    standalone_init()
    ensure_plugins_loaded()


class TestViewportUserInputs(unittest.TestCase):
    def setUp(self):
        from mpynode._api2.mpy_file import MPyFile as _NodeCls
        self._NodeCls = _NodeCls
        self._prev_bb = _NodeCls.BAREBONES_MODE
        _NodeCls.BAREBONES_MODE = False  # exercise the user-Viewport path
        mc.file(new=True, force=True)

    def tearDown(self):
        self._NodeCls.BAREBONES_MODE = self._prev_bb

    def _build(self, tin=7.0):
        from mpynode.wrappers.mpy_file import MPyFile
        f = MPyFile.create(name="pur#", seed_defaults=False, as_texture=False)
        f.set_init_expression("")
        f.add_input_attr("tIn", "float")
        mc.setAttr(f.get_name() + ".tIn", tin)
        # A Viewport source reading the user input via self.X. Without the
        # seeding fix this raises on the render thread.
        f.set_viewport_expression("_ = self.tIn\n")
        name = f.get_name()
        sel = om.MSelectionList(); sel.add(name)
        obj = sel.getDependNode(0)
        return name, obj

    @staticmethod
    def _mpx(obj):
        return om.MFnDependencyNode(obj).userNode()

    # -- GAP 2 ---------------------------------------------------------------
    def test_runviewport_seeds_user_inputs_into_locals(self):
        """runViewport must seed user inputs into the SelfProxy compute_locals
        (the tier that resolves with no plug read), exactly like compute()."""
        name, obj = self._build(tin=7.0)
        mpx = self._mpx(obj)
        self.assertIsNotNone(mpx, "could not resolve the MPxNode instance")

        import mpynode._api2.mpy_file as MF
        captured = {}
        orig = MF.SelfProxy

        def _spy(*args, **kwargs):
            captured["locals"] = dict(kwargs.get("compute_locals") or {})
            return orig(*args, **kwargs)

        MF.SelfProxy = _spy
        try:
            # runViewport never calls shader/mappings (it only exposes them as
            # self.shader / self.mappings), so a dummy object is enough here.
            mpx.runViewport(object(), None, user_inputs={"tIn": 7.0})
        finally:
            MF.SelfProxy = orig

        self.assertIn("locals", captured, "runViewport never built a SelfProxy")
        seen = captured["locals"]
        self.assertIn(
            "tIn", seen,
            "user input 'tIn' not seeded into the Viewport locals -> self.tIn "
            "falls through to the unsafe render-thread plug path",
        )
        self.assertAlmostEqual(float(seen["tIn"]), 7.0, places=5)
        # the bridge handles must still be present alongside.
        for h in ("time", "shader", "mappings", "texture_manager",
                  "state_manager"):
            self.assertIn(h, seen, f"bridge handle {h!r} missing from locals")

    # -- GAP 1 ---------------------------------------------------------------
    def test_updateDG_reads_user_inputs_for_dependency_and_cache(self):
        """The override's updateDG must read every user input plug and cache it
        for runViewport (render-thread-safe value cache). The viewport refresh
        on a manual change is handled separately by the AttributeChanged
        callback -- this read is NOT an OGS dependency (see module docstring)."""
        from mpynode._api2.mpy_file import MPyFileOverride
        name, obj = self._build(tin=4.5)
        try:
            ov = MPyFileOverride(obj)
        except Exception as exc:  # pragma: no cover - VP2 ctor unavailable
            self.skipTest("MPyFileOverride not constructable headless: %s" % exc)
        ov.updateDG()
        self.assertIn(
            "tIn", ov._user_inputs,
            "updateDG did not read user input 'tIn' -> no OGS dependency, so a "
            "manual change won't refresh the viewport",
        )
        self.assertAlmostEqual(float(ov._user_inputs["tIn"]), 4.5, places=5)


# ===================== from test_mpyfile_attr_refresh.py =====================
import unittest

import maya.api.OpenMaya as om
import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__mpyfile_attr_refresh():
    standalone_init()
    ensure_plugins_loaded()


class TestRefreshAttrFilter(unittest.TestCase):
    """The pure decision: which attribute names should kick a refresh."""

    def setUp(self):
        import mpynode._api2.mpy_file as MF
        self.MF = MF

    def test_compute_presets_refresh(self):
        for name in ("colorSpace", "preFilter", "preFilterKernel",
                     "preFilterRadius", "wrapModeU", "wrapModeV",
                     "borderColor"):
            self.assertTrue(
                self.MF._is_viewport_refresh_attr(name),
                "%s is a preset that affects the look -> must refresh" % name)

    def test_viewport_only_presets_refresh(self):
        # Sampler-state presets matter only to the VP2 tier, so they are the
        # MOST important refresh case.
        for name in ("filterMode", "maxAnisotropy", "mipmapMode",
                     "mipLODBias", "minLOD", "maxLOD"):
            self.assertTrue(self.MF._is_viewport_refresh_attr(name), name)

    def test_user_input_name_refreshes(self):
        self.assertTrue(self.MF._is_viewport_refresh_attr("tIn"))

    def test_outputs_do_not_refresh(self):
        for name in ("outColor", "outColorR", "outColorG", "outColorB",
                     "outAlpha"):
            self.assertFalse(
                self.MF._is_viewport_refresh_attr(name),
                "%s is an output -> setting it must NOT trigger a refresh loop"
                % name)

    def test_internal_plugs_do_not_refresh(self):
        for name in ("_inputAttrs", "_outputAttrs", "_computeSource",
                     "_initSource", "_viewportSource", "_storedVars",
                     "_timeIn"):
            self.assertFalse(self.MF._is_viewport_refresh_attr(name), name)

    def test_empty_name_does_not_refresh(self):
        self.assertFalse(self.MF._is_viewport_refresh_attr(""))


class TestCallbackInstallAndFire(unittest.TestCase):
    def setUp(self):
        import mpynode._api2.mpy_file as MF
        self.MF = MF
        mc.file(new=True, force=True)

    def _make_node(self):
        from mpynode.wrappers.mpy_file import MPyFile
        f = MPyFile.create(name="refreshTest#", seed_defaults=False,
                           as_texture=False)
        return f.get_name()

    def test_setattr_preset_fires_dirty_and_refresh(self):
        """Setting a preset on an mPyFile must invoke the refresh action."""
        node = self._make_node()
        calls = []
        orig = self.MF._dirty_and_refresh
        self.MF._dirty_and_refresh = lambda n: calls.append(n)
        try:
            mc.setAttr(node + ".preFilterRadius", 4.0)
        finally:
            self.MF._dirty_and_refresh = orig
        self.assertIn(
            node, calls,
            "setting preFilterRadius did not invoke the viewport refresh "
            "action -> the manual edit would not update the viewport")

    def test_setattr_viewport_only_preset_fires(self):
        node = self._make_node()
        calls = []
        orig = self.MF._dirty_and_refresh
        self.MF._dirty_and_refresh = lambda n: calls.append(n)
        try:
            mc.setAttr(node + ".maxAnisotropy", 4)
        finally:
            self.MF._dirty_and_refresh = orig
        self.assertIn(node, calls)

    def test_setattr_output_does_not_fire(self):
        node = self._make_node()
        calls = []
        orig = self.MF._dirty_and_refresh
        self.MF._dirty_and_refresh = lambda n: calls.append(n)
        try:
            # outAlpha looks settable; it must not enter the refresh path
            # or a feedback loop follows.
            try:
                mc.setAttr(node + ".outAlpha", 0.5)
            except Exception:
                pass
        finally:
            self.MF._dirty_and_refresh = orig
        self.assertEqual([], calls)


class TestRefreshCoalescing(unittest.TestCase):
    """MED-1: executeDeferred does NOT coalesce, so a slider drag emitting N
    setAttr events would queue N full cmds.refresh() calls. A _refresh_pending
    latch collapses a burst to a single trailing refresh."""

    def setUp(self):
        import mpynode._api2.mpy_file as MF
        self.MF = MF
        MF._refresh_pending = False

    def tearDown(self):
        self.MF._refresh_pending = False

    def test_burst_enqueues_single_refresh(self):
        import maya.utils as mu
        enqueued = []
        orig = mu.executeDeferred
        mu.executeDeferred = lambda fn, *a, **k: enqueued.append(fn)
        try:
            for _ in range(5):
                # the node need not exist: dgdirty is guarded and only the
                # refresh-enqueue coalescing is asserted.
                self.MF._dirty_and_refresh("burstNode")
        finally:
            mu.executeDeferred = orig
        self.assertEqual(
            len(enqueued), 1,
            "a burst of edits must enqueue exactly one deferred refresh")

    def test_refresh_runs_then_rearms(self):
        import maya.utils as mu
        enqueued = []
        orig = mu.executeDeferred
        mu.executeDeferred = lambda fn, *a, **k: enqueued.append(fn)
        try:
            self.MF._dirty_and_refresh("rearmNode")
            self.assertTrue(self.MF._refresh_pending)
            # running the deferred refresh clears the latch...
            enqueued[0]()
            self.assertFalse(self.MF._refresh_pending)
            # ...so the next edit re-arms (enqueues again).
            self.MF._dirty_and_refresh("rearmNode")
        finally:
            mu.executeDeferred = orig
        self.assertEqual(len(enqueued), 2)


class TestUnloadReset(unittest.TestCase):
    """LOW-1: the dedup map must be cleared on plugin unload so a reload within
    the SAME scene (MObject hashCodes persist) re-installs callbacks instead of
    short-circuiting on stale hashes."""

    def test_reset_clears_dedup_and_pending(self):
        import mpynode._api2.mpy_file as MF
        MF._ATTR_REFRESH_CB[123456] = 999
        MF._refresh_pending = True
        MF._reset_attr_refresh_state()
        self.assertEqual(MF._ATTR_REFRESH_CB, {})
        self.assertFalse(MF._refresh_pending)


class TestRegistration(unittest.TestCase):
    def setUp(self):
        import mpynode._api2.mpy_file as MF
        self.MF = MF
        mc.file(new=True, force=True)

    def test_register_is_idempotent_and_covers_existing(self):
        """register_attr_refresh_callbacks must install on existing nodes and
        be safe to call repeatedly (dedup by MObject hash)."""
        from mpynode.wrappers.mpy_file import MPyFile
        f = MPyFile.create(name="existing#", seed_defaults=False,
                           as_texture=False)
        # Clear the dedup map so the existing-node sweep has work to do.
        self.MF._ATTR_REFRESH_CB.clear()
        self.MF.register_attr_refresh_callbacks()
        n_after_first = len(self.MF._ATTR_REFRESH_CB)
        self.assertGreaterEqual(
            n_after_first, 1,
            "register_attr_refresh_callbacks did not install on the existing "
            "mPyFile node")
        self.MF.register_attr_refresh_callbacks()
        self.assertEqual(
            n_after_first, len(self.MF._ATTR_REFRESH_CB),
            "second register call double-installed (not idempotent)")
        self.assertTrue(f)  # keep node alive


# ===================== from test_mpyfile_user_input_threadsafe.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__mpyfile_user_input_threadsafe():
    standalone_init()
    ensure_plugins_loaded()


class TestMPyFileUserInputThreadSafe(unittest.TestCase):
    def setUp(self):
        from mpynode._api2.mpy_file import MPyFile as _NodeCls
        self._NodeCls = _NodeCls
        self._prev_bb = _NodeCls.BAREBONES_MODE
        _NodeCls.BAREBONES_MODE = False
        mc.file(new=True, force=True)

    def tearDown(self):
        self._NodeCls.BAREBONES_MODE = self._prev_bb

    def _build(self):
        from mpynode.wrappers.mpy_file import MPyFile
        f = MPyFile.create(name="utf#", seed_defaults=False, as_texture=False)
        f.set_init_expression("")
        f.add_input_attr("gain", "float")
        mc.setAttr(f.get_name() + ".gain", 3.0)
        # Reads the user input via self.X -- what broke on the worker thread.
        f.set_compute_expression(
            "self.outColor = (self.gain, self.gain * 2.0, 0.0)\n"
            "self.outAlpha = 1.0\n"
        )
        return f.get_name()

    def test_user_input_seeded_into_compute_locals(self):
        """The fix: user inputs are pre-populated into the SelfProxy
        compute_locals so self.<name> resolves with NO plug read (the only
        thing that works on the swatch / Arnold worker thread)."""
        name = self._build()

        import mpynode._api2.mpy_file as MF
        captured = {}
        orig = MF.SelfProxy

        def _spy(*args, **kwargs):
            captured["compute_locals"] = dict(kwargs.get("compute_locals") or {})
            return orig(*args, **kwargs)

        MF.SelfProxy = _spy
        try:
            mc.getAttr(name + ".outColor")  # triggers compute()
        finally:
            MF.SelfProxy = orig

        self.assertIn("compute_locals", captured,
                      "compute() never constructed a SelfProxy")
        locals_seen = captured["compute_locals"]
        self.assertIn(
            "gain", locals_seen,
            "user input 'gain' not seeded into compute_locals -> self.gain "
            "falls through to the plug tree and raises on the worker thread",
        )
        self.assertAlmostEqual(float(locals_seen["gain"]), 3.0, places=5)

    def test_self_user_input_compute_produces_correct_output(self):
        """End-to-end: self.<user_input> drives the output correctly."""
        name = self._build()
        col = mc.getAttr(name + ".outColor")[0]
        self.assertAlmostEqual(col[0], 3.0, places=4)
        self.assertAlmostEqual(col[1], 6.0, places=4)
        self.assertAlmostEqual(col[2], 0.0, places=4)

    def test_time_connected_user_input_reads_current_frame(self):
        """The real scanline case: a user input wired to time1.outTime read via
        self.X must track the current frame (data-block read of a CONNECTED
        kFloat input -- this is what the asDouble->asFloat fix makes correct)."""
        from mpynode.wrappers.mpy_file import MPyFile
        f = MPyFile.create(name="utc#", seed_defaults=False, as_texture=False)
        f.set_init_expression("")
        f.add_input_attr("tIn", "float")
        name = f.get_name()
        mc.connectAttr("time1.outTime", name + ".tIn", force=True)
        f.set_compute_expression(
            "self.outColor = (self.tIn, 0.0, 0.0)\nself.outAlpha = 1.0\n"
        )
        for frame in (1.0, 13.0, 25.0):
            mc.currentTime(frame)
            r = mc.getAttr(name + ".outColor")[0][0]
            self.assertAlmostEqual(
                r, frame, places=3,
                msg="self.tIn (connected to time) read %r at frame %r -- "
                    "expected the frame number" % (r, frame),
            )


class TestBarebonesHelperIsolation(unittest.TestCase):
    """``MPyFile.BAREBONES_MODE`` is a process-global class flag. The barebones
    test helpers MUST leave it at the shipped class default after cleanup --
    otherwise later test modules that create mPyFile nodes (e.g.
    ``test_templates``) silently get the inline barebones fast path instead of
    running their own Compute expression, which on Maya 2024 (no PIL) returns
    magenta. The shipped default is ``False`` (see
    ``_api2/mpy_file.py``: ``BAREBONES_MODE: bool = False``)."""

    SHIPPED_DEFAULT = False

    def setUp(self):
        from mpynode._api2.mpy_file import MPyFile

        self._MPyFile = MPyFile
        self._prior = MPyFile.BAREBONES_MODE
        # leave the flag at the shipped default regardless of outcome.
        self.addCleanup(
            lambda: setattr(MPyFile, "BAREBONES_MODE", self.SHIPPED_DEFAULT)
        )

    def test_restore_barebones_resets_to_shipped_default(self):
        _disable_barebones()
        self.assertFalse(
            self._MPyFile.BAREBONES_MODE, "_disable_barebones should set False"
        )
        _restore_barebones()
        self.assertEqual(
            self._MPyFile.BAREBONES_MODE,
            self.SHIPPED_DEFAULT,
            "_restore_barebones leaked a non-default BAREBONES_MODE; later "
            "test modules will see the inline barebones path and mis-compute.",
        )


def setUpModule():
    _setUpModule__phase32_mpyfile()
    _setUpModule__mpyfile_viewport_refresh()
    _setUpModule__mpyfile_attr_refresh()
    _setUpModule__mpyfile_user_input_threadsafe()


if __name__ == "__main__":
    import unittest
    unittest.main()
