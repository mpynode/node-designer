"""mPyFile setup Arnold render verification (resolves design §10.1/§10.2 TODOs).

This module executes the two TODO-verify-in-Maya items from the universal-setup
design §10.1/§10.2:

  1. Shader destination attr names: confirm that with a `lambert` selected, setup
     wires `outColor -> lambert.color`, and with an `aiStandardSurface` selected
     (MtoA), it wires `outColor -> aiStandardSurface.baseColor`.
  2. Black-swatch / warm_init regression guard: after create-with-setup, do a REAL
     Arnold render of a scene where the mPyFile drives a shader on a surface, and
     assert the result is NOT all-black (guards the `warm_init_namespace` call).

Step 7's `aiStandardSurface->baseColor` assertion SKIPPED because mtoa was not
loaded; here we `cmds.loadPlugin("mtoa")` so that path actually runs.
"""

from __future__ import annotations

import os
import tempfile
import unittest

import maya.cmds as mc
import maya.api.OpenMaya as om

from ._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import build_new_or_setup_command, run_undoable


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _make_test_png(path: str, rgb: tuple) -> None:
    """Write a tiny solid-color RGBA PNG via MImage (no PIL dependency).
    Args:
        path: Output PNG file path.
        rgb: (r, g, b) as uint8 0-255.
    """
    w = h = 4
    buf = bytes((rgb[0], rgb[1], rgb[2], 255)) * (w * h)
    img = om.MImage()
    img.create(w, h, 4, om.MImage.kByte)
    img.setPixels(buf, w, h)
    img.writeToFile(path, "png")


# ===========================================================================
# §10.1 — Shader destination attr names (color vs baseColor)
# ===========================================================================
class TestShaderDestinationAttrNames(unittest.TestCase):
    """Verify that the mPyFile setup body wires `outColor` to the correct
    first color input of the selected shader: `color` for lambert/blinn/phong,
    `baseColor` for aiStandardSurface."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _run_setup(self):
        """Run create-with-setup and return the created mPyFile name."""
        cmd = build_new_or_setup_command("mPyFile", mode=None, auto_setup=True)
        run_undoable(cmd)
        self.assertTrue(cmd.created_name, "setup must create a node")
        self.assertTrue(mc.objExists(cmd.created_name))
        return cmd.created_name

    def test_lambert_dest_is_color(self):
        """With a lambert selected, setup wires `mPyFile.outColor -> lambert.color`."""
        shader = mc.shadingNode("lambert", asShader=True, name="testLambert")
        mc.select(shader, replace=True)
        file_node = self._run_setup()
        self.assertTrue(
            mc.isConnected(file_node + ".outColor", shader + ".color"),
            f"Expected {file_node}.outColor -> {shader}.color connection",
        )

    def test_blinn_dest_is_color(self):
        """With a blinn selected, setup wires `mPyFile.outColor -> blinn.color`."""
        shader = mc.shadingNode("blinn", asShader=True, name="testBlinn")
        mc.select(shader, replace=True)
        file_node = self._run_setup()
        self.assertTrue(
            mc.isConnected(file_node + ".outColor", shader + ".color"),
            f"Expected {file_node}.outColor -> {shader}.color connection",
        )

    def test_phong_dest_is_color(self):
        """With a phong selected, setup wires `mPyFile.outColor -> phong.color`."""
        shader = mc.shadingNode("phong", asShader=True, name="testPhong")
        mc.select(shader, replace=True)
        file_node = self._run_setup()
        self.assertTrue(
            mc.isConnected(file_node + ".outColor", shader + ".color"),
            f"Expected {file_node}.outColor -> {shader}.color connection",
        )

    def test_aistandardsurface_dest_is_baseColor(self):
        """With an aiStandardSurface selected (MtoA), setup wires
        `mPyFile.outColor -> aiStandardSurface.baseColor`."""
        try:
            if not mc.pluginInfo("mtoa", q=True, loaded=True):
                mc.loadPlugin("mtoa")
        except Exception:
            self.skipTest("MtoA unavailable (loadPlugin failed)")

        if "aiStandardSurface" not in mc.allNodeTypes():
            self.skipTest("aiStandardSurface (MtoA) not available")

        shader = mc.shadingNode("aiStandardSurface", asShader=True, name="testAi")
        mc.select(shader, replace=True)
        file_node = self._run_setup()
        self.assertTrue(
            mc.isConnected(file_node + ".outColor", shader + ".baseColor"),
            f"Expected {file_node}.outColor -> {shader}.baseColor connection",
        )

    def test_standardsurface_dest_is_baseColor(self):
        """With a standardSurface selected (Maya 2020+), setup wires
        `mPyFile.outColor -> standardSurface.baseColor`."""
        if "standardSurface" not in mc.allNodeTypes():
            self.skipTest("standardSurface not available (Maya < 2020)")

        shader = mc.shadingNode("standardSurface", asShader=True, name="testStd")
        mc.select(shader, replace=True)
        file_node = self._run_setup()
        self.assertTrue(
            mc.isConnected(file_node + ".outColor", shader + ".baseColor"),
            f"Expected {file_node}.outColor -> {shader}.baseColor connection",
        )


# ===========================================================================
# §10.2 — Arnold render non-black (warm_init_namespace regression guard)
# ===========================================================================
class TestArnoldRenderNonBlack(unittest.TestCase):
    """Verify that a mPyFile created via setup (which calls `warm_init_namespace`)
    renders NON-BLACK in a real Arnold scene render. This guards against the
    cold-init-namespace NameError -> black-swatch regression (memory topic
    `mpyfile-three-bugs-hypershade-black-saverefresh-2026-06-23.md`)."""

    def setUp(self):
        mc.file(new=True, force=True)
        # Try to load MtoA; if unavailable, all tests in this class will skip.
        try:
            if not mc.pluginInfo("mtoa", q=True, loaded=True):
                mc.loadPlugin("mtoa")
        except Exception:
            self.skipTest("MtoA unavailable (loadPlugin failed)")

        if "aiStandardSurface" not in mc.allNodeTypes():
            self.skipTest("aiStandardSurface (MtoA) not available")

        self.tmpdir = tempfile.mkdtemp()

    def _run_setup(self):
        """Run create-with-setup and return the created mPyFile name."""
        cmd = build_new_or_setup_command("mPyFile", mode=None, auto_setup=True)
        run_undoable(cmd)
        self.assertTrue(cmd.created_name, "setup must create a node")
        self.assertTrue(mc.objExists(cmd.created_name))
        return cmd.created_name

    def test_render_non_black_with_aiStandardSurface(self):
        """Build a minimal Arnold scene (poly sphere + aiStandardSurface driven by
        an mPyFile created via setup with a non-black test texture) and render to
        a temp image file. Assert at least one pixel channel is meaningfully > 0
        (non-black). This exercises the `warm_init_namespace` call in the setup
        body and guards the worker-thread black-swatch regression."""
        # Create a test texture (solid red sRGB 255, 0, 0).
        test_png = os.path.join(self.tmpdir, "test_red.png")
        _make_test_png(test_png, (255, 0, 0))

        # Create an aiStandardSurface and select it for setup.
        shader = mc.shadingNode("aiStandardSurface", asShader=True, name="aiShader")
        mc.select(shader, replace=True)

        # Run setup -> mPyFile wired to aiStandardSurface.baseColor.
        file_node = self._run_setup()
        self.assertTrue(
            mc.isConnected(file_node + ".outColor", shader + ".baseColor"),
            "setup must wire mPyFile.outColor -> aiStandardSurface.baseColor",
        )

        # Give the mPyFile a real input image so it outputs non-black.
        # The template Init has _read_image, and the Compute reads the file.
        mc.setAttr(file_node + ".fileName", test_png, type="string")

        # Force compute so the mPyFile has valid outColor.
        mc.dgdirty(file_node + ".outColor")
        out = mc.getAttr(file_node + ".outColor")[0]
        self.assertGreater(
            max(out),
            0.01,
            f"mPyFile.outColor must be non-black (got {out}) before render",
        )

        # Create a shading group and assign the shader to a poly sphere.
        sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name="aiSG")
        mc.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
        sphere = mc.polySphere(name="testSphere", r=1)[0]
        mc.sets(sphere, edit=True, forceElement=sg)

        # Create a camera and frame the sphere.
        cam = mc.camera(name="renderCam")[0]
        mc.setAttr(cam + ".translateZ", 5)
        mc.viewFit(cam, sphere)

        # Create a light so the surface is lit (aiSkyDomeLight is simplest).
        light = mc.shadingNode("aiSkyDomeLight", asLight=True, name="skyDome")

        # Render with Arnold to a temp image file.
        render_path = os.path.join(self.tmpdir, "test_render.png")
        mc.setAttr("defaultRenderGlobals.imageFormat", 32)  # PNG
        mc.setAttr("defaultRenderGlobals.animation", 0)  # Still frame
        mc.setAttr("defaultRenderGlobals.putFrameBeforeExt", 1)
        mc.setAttr("defaultRenderGlobals.extensionPadding", 4)
        mc.setAttr("defaultRenderGlobals.outFormatControl", 0)
        mc.setAttr("defaultRenderGlobals.periodInExt", 2)
        mc.setAttr("defaultResolution.width", 64)
        mc.setAttr("defaultResolution.height", 64)
        mc.setAttr("defaultRenderGlobals.currentRenderer", "arnold", type="string")

        # Set output path (Maya appends frame number + extension).
        base_name = os.path.join(self.tmpdir, "test_render")
        mc.setAttr("defaultRenderGlobals.imageFilePrefix", base_name, type="string")

        try:
            # Render the current frame via Arnold.
            mc.arnoldRender(width=64, height=64, camera=cam)
        except Exception as exc:
            self.skipTest(f"arnoldRender failed (no Arnold license/driver?): {exc}")

        # Find the actual rendered file (Maya appends .0000.png or similar).
        rendered_files = [
            f
            for f in os.listdir(self.tmpdir)
            if f.startswith("test_render") and f.endswith(".png")
        ]
        if not rendered_files:
            self.skipTest("arnoldRender produced no output file (Arnold unavailable?)")

        actual_render = os.path.join(self.tmpdir, rendered_files[0])

        # Read the rendered image via MImage.
        img = om.MImage()
        try:
            img.readFromFile(actual_render)
        except Exception as exc:
            self.fail(f"Failed to read rendered image {actual_render}: {exc}")

        w = img.getSize()[0]
        h = img.getSize()[1]
        self.assertGreater(w * h, 0, "Rendered image must have non-zero dimensions")

        # Extract pixel data (uint8 RGBA).
        import ctypes

        ptr = img.pixels()
        buf = ctypes.string_at(ptr, w * h * 4)
        pixels = [buf[i] for i in range(0, len(buf), 4)]  # R channel of each pixel

        max_channel = max(pixels)
        self.assertGreater(
            max_channel,
            10,  # Scene-linear red ~0.22 -> uint8 ~56 after tone-map; 10 is safe margin
            f"Rendered image must be non-black (max R channel = {max_channel}). "
            "If all-black, warm_init_namespace did NOT prevent the worker-thread "
            "NameError -> (0,0,0) default outColor regression.",
        )


if __name__ == "__main__":
    unittest.main()
