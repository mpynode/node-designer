"""The interpreted mPyFile's viewport shows what its compute shows when there
is no image -- magenta -- and never keeps the previous image.

VP2 keeps the texture a shader instance was last given. The shipped Viewport
sources skipped the upload when read_texture() returned None, so after
fileName was cleared or pointed at a missing file the surface went on showing
the last good file (a fresh node showed black), while the compute and the
compiled node's override showed magenta (bug pass 6, 2026-10-03).

These run the real VP2 path -- MPyFileOverride.updateDG + updateShader ->
runViewport -> the node's own Viewport source -- with only the GPU objects
stood in: a shader instance that remembers what is bound to its texture
parameter, and a texture manager that caches by NAME the way VP2's does (a
second acquire under a known name returns the FIRST pixels, so a key collision
shows up as a stale image here too). One override and one shader per node,
kept across the steps of a sequence the way one viewport surface is: whatever
a step leaves bound is what the surface shows. No GPU is needed.

Each step reads the bound image at texel-exact UVs and compares it with the
node's outColor / outAlpha at the same UVs, for the default node and the File
Simple and File Scanline templates. The colour-space and pre-filter tests also
cover File Composite, whose image is its `layers` stack.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

import maya.api.OpenMaya as om
import maya.api.OpenMayaRender as omr
import maya.cmds as mc
import numpy as np

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_GRID    = os.path.join(_paths.SCRIPTS, "mpynode", "_demos", "data", "test_grid.png")
_EMBED   = os.path.join(_paths.SCRIPTS, "mpynode", "_demos", "data", "red_square.png")
_MISSING = os.path.join(_paths.ROOT, "tests", "no_such_texture_viewport.png")
_KINDS   = ("default", "File Simple", "File Scanline")
# File Composite reads every layer through the node's colour space and
# pre-filter too, so the tests on those inputs cover it as well.
_LOOK_KINDS = _KINDS + ("File Composite",)
# Where to read the bound image, as fractions of its texel grid: interior
# points, clear of the wrap seam at u = 1 / v = 0.
_SPOTS = ((0.25, 0.30), (0.5, 0.5), (0.8, 0.65), (0.1, 0.9))
_TOL   = 2e-4


class _Texture:
    def __init__(self, name, w, h, data):
        self.name   = name
        self.pixels = np.frombuffer(data, dtype=np.float32).reshape(h, w, 4).copy()


class _TextureManager:
    """VP2's name cache: a known name returns its texture and ignores the new
    pixels."""

    def __init__(self):
        self.by_name = {}

    def acquireTexture(self, name, desc, data, gen_mips):
        tex = self.by_name.get(name)
        if tex is None:
            tex                = _Texture(name, desc.fWidth, desc.fHeight, bytes(data))
            self.by_name[name] = tex
        return tex

    def releaseTexture(self, tex):
        pass


class _Assignment:
    def __init__(self):
        self.texture = None


class _Renderer:
    kR32G32B32A32_FLOAT = omr.MRenderer.kR32G32B32A32_FLOAT
    manager             = None

    @classmethod
    def getTextureManager(cls):
        return cls.manager


class _Shader:
    """One texture parameter; ``bound`` is what the surface shows."""

    def __init__(self):
        self.bound = None

    def parameterList(self):
        return ["map"]

    def parameterType(self, name):
        return omr.MShaderInstance.kTexture2

    def setParameter(self, name, value):
        self.bound = getattr(value, "texture", None)


class _Surface:
    """A node's VP2 override plus the one shader instance it keeps drawing."""

    def __init__(self, node, manager=None):
        """``manager``: pass one shared _TextureManager to several surfaces --
        VP2 has a single texture manager for the whole session."""
        from mpynode._api2.mpy_file import MPyFileOverride

        sel = om.MSelectionList()
        sel.add(node)
        self.override = MPyFileOverride(sel.getDependNode(0))
        self.shader   = _Shader()
        self.manager  = manager or _TextureManager()

    def draw(self):
        self.override.updateDG()
        _Renderer.manager = self.manager
        with mock.patch.object(omr, "MRenderer", _Renderer), \
                mock.patch.object(omr, "MTextureAssignment", _Assignment):
            self.override.updateShader(self.shader, None)
        return self.shader.bound


def _create(kind):
    if kind == "default":
        from mpynode.wrappers.mpy_file import MPyFile

        return MPyFile.create(name="vpMissing#").get_name()
    from mpynode._base.commands import _TemplateCreateCommand, run_undoable
    from mpynode._common.io.mpn_io import load_mpn

    payload = load_mpn(os.path.join(_paths.ROOT, "templates", "MPyFile", kind,
                                    "template.mpn"), trusted=True)
    cmd = _TemplateCreateCommand(payload, payload.get("native_type"),
                                 run_setup=False)
    return run_undoable(cmd) or cmd.created_name


def _set_image(kind, node, path):
    """Point a node at one image: File Composite stacks the paths in its
    `layers` array, every other kind reads fileName."""
    if kind == "File Composite":
        mc.setAttr(node + ".layers[0]", path, type="string")
    else:
        mc.setAttr(node + ".fileName", path, type="string")


class TestViewportShowsWhatComputeShows(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(_GRID), _GRID
        assert os.path.isfile(_EMBED), _EMBED
        assert not os.path.exists(_MISSING), _MISSING
        with open(_EMBED, "rb") as fh:
            cls.embed_bytes = fh.read()
        with open(_GRID, "rb") as fh:
            cls.grid_bytes = fh.read()

    def setUp(self):
        from mpynode._api2.mpy_file import MPyFile as _Node

        self._bb             = _Node.BAREBONES_MODE
        _Node.BAREBONES_MODE = False
        mc.file(new=True, force=True)

    def tearDown(self):
        from mpynode._api2.mpy_file import MPyFile as _Node

        _Node.BAREBONES_MODE = self._bb

    # -- helpers -----------------------------------------------------------

    def _compute(self, node, u, v):
        mc.setAttr(node + ".uCoord", u)
        mc.setAttr(node + ".vCoord", v)
        rgb = mc.getAttr(node + ".outColor")[0]
        return np.array(tuple(rgb) + (mc.getAttr(node + ".outAlpha"),))

    def _check(self, node, surface, step):
        tex = surface.draw()
        self.assertIsNotNone(tex, "%s: nothing bound -- the surface shows no "
                                  "image while compute does" % step)
        h, w = tex.pixels.shape[:2]
        for fx, fy in _SPOTS:
            i, j = round(fx * (w - 1)), round(fy * (h - 1))
            u, v = i / float(w - 1), 1.0 - j / float(h - 1)
            want = self._compute(node, u, v)
            got  = tex.pixels[j, i]
            self.assertTrue(
                np.allclose(got, want, atol=_TOL),
                "%s: viewport %s != compute %s at uv (%.4f, %.4f) [texture %r]"
                % (step, tuple(np.round(got, 4)), tuple(np.round(want, 4)),
                   u, v, tex.name))
        return tex

    def _run(self, steps, embed=False, kinds=_KINDS):
        for kind in kinds:
            with self.subTest(node=kind):
                mc.file(new=True, force=True)
                node    = _create(kind)
                surface = _Surface(node)
                if embed:
                    from mpynode._common.storedvars.stored_vars_api import (
                        set_variable)

                    set_variable(node, "embeddedImage", self.embed_bytes,
                                 persistent=True)
                for path in steps:
                    if path is not None:
                        mc.setAttr(node + ".fileName", path, type="string")
                    label = "fresh" if path is None else (
                        os.path.basename(path) or '""')
                    self._check(node, surface, "%s %s" % (kind, label))

    # -- the five sequences ------------------------------------------------

    def test_fresh_node(self):
        self._run([None])

    def test_empty_path(self):
        self._run([""])

    def test_missing_file(self):
        self._run([_MISSING])

    def test_valid_empty_valid(self):
        self._run([_GRID, "", _GRID])

    def test_valid_missing_valid(self):
        self._run([_GRID, _MISSING, _GRID])

    # -- embedded image ----------------------------------------------------

    def test_embedded_image_is_shown_for_a_blank_or_missing_path(self):
        """The compute falls back to the baked embeddedImage when fileName
        does not load; the viewport must show the same image, and still never
        the last file."""
        self._run(["", _MISSING, _GRID, "", _GRID, _MISSING], embed=True)

    # -- texture keys name the image, not the fileName -----------------------
    # VP2's texture manager hands back the texture already carrying a name and
    # ignores the new pixels. Keyed on fileName, every node whose fileName does
    # not load shared one name, whatever image it embedded (bug pass 6 review,
    # findings 1 and 2).

    def test_two_nodes_with_different_embedded_images(self):
        """One texture manager, as in VP2: two nodes with the same blank or
        missing fileName and different embedded images each show their own."""
        from mpynode._common.storedvars.stored_vars_api import set_variable

        for kind in _KINDS:
            with self.subTest(node=kind):
                mc.file(new=True, force=True)
                manager = _TextureManager()
                nodes   = []
                for data in (self.embed_bytes, self.grid_bytes):
                    node = _create(kind)
                    set_variable(node, "embeddedImage", data, persistent=True)
                    nodes.append((node, _Surface(node, manager)))
                for path in ("", _MISSING, ""):
                    for node, _surface in nodes:
                        mc.setAttr(node + ".fileName", path, type="string")
                    for node, surface in nodes:
                        self._check(node, surface, "%s %s %s" % (
                            kind, node, os.path.basename(path) or '""'))

    def test_new_embedded_bytes_under_the_same_fileName(self):
        """Re-embedding different bytes without touching fileName shows the
        new image, and going back to the first bytes shows the first again."""
        from mpynode._common.storedvars.stored_vars_api import set_variable

        for kind in _KINDS:
            with self.subTest(node=kind):
                mc.file(new=True, force=True)
                node    = _create(kind)
                surface = _Surface(node)
                for path in ("", _MISSING):
                    mc.setAttr(node + ".fileName", path, type="string")
                    for name, data in (("red", self.embed_bytes),
                                       ("grid", self.grid_bytes),
                                       ("red again", self.embed_bytes)):
                        set_variable(node, "embeddedImage", data,
                                     persistent=True)
                        self._check(node, surface, "%s %s embedded %s" % (
                            kind, os.path.basename(path) or '""', name))

    # -- texture keys cover the colour space and the pre-filter ---------------
    # read_texture() applies colorSpace and the pre-filter, so they change the
    # pixels. File Simple and File Scanline left them out of the texture name,
    # so changing either under the same fileName kept the OLD texture: after
    # colorSpace went to ACEScct, File Simple's viewport still showed the sRGB
    # (0.0545, 0.5089, 0.0296) where compute gave (0.0, 1.0, 0.0) (parity pass
    # 2026-10-15, commit 6). File Composite's key named only its layer paths
    # and opacities, the same bug (parity pass 2026-10-15, round 2).

    def _run_look(self, steps):
        """Each step changes one colour-space or pre-filter input under the
        same image path. The surface must show what compute shows, and a step
        that changes the image must bind a different image."""
        for kind in _LOOK_KINDS:
            with self.subTest(node=kind):
                mc.file(new=True, force=True)
                node    = _create(kind)
                surface = _Surface(node)
                _set_image(kind, node, _GRID)
                previous = self._check(node, surface, "%s grid" % kind)
                for attr, value in steps:
                    mc.setAttr("%s.%s" % (node, attr), value)
                    step = "%s %s=%s" % (kind, attr, value)
                    tex  = self._check(node, surface, step)
                    if attr == "preFilterRadius" and not mc.getAttr(
                            node + ".preFilter"):
                        continue  # the radius does nothing with it off
                    self.assertFalse(
                        np.array_equal(tex.pixels, previous.pixels),
                        "%s: the surface still shows the previous image "
                        "[texture %r]" % (step, tex.name))
                    previous = tex

    def test_colour_space_changes_reach_the_viewport(self):
        self._run_look((
            ("colorSpace", 20),  # ACEScct
            ("colorSpace", 19),  # Raw
            ("colorSpace", 0),  # sRGB again
        ))

    def test_prefilter_changes_reach_the_viewport(self):
        self._run_look((
            ("preFilterRadius", 3.0),
            ("preFilter", True),
            ("preFilterKernel", 0),  # box
            ("preFilterRadius", 6.0),
            ("preFilter", False),
        ))

    def test_two_nodes_differing_only_in_colour_space(self):
        """One texture manager, as in VP2: two nodes on the same file that
        differ only in colorSpace each show their own image."""
        for kind in _LOOK_KINDS:
            with self.subTest(node=kind):
                mc.file(new=True, force=True)
                manager = _TextureManager()
                nodes   = []
                for cs in (0, 20):
                    node = _create(kind)
                    _set_image(kind, node, _GRID)
                    mc.setAttr(node + ".colorSpace", cs)
                    nodes.append((node, _Surface(node, manager)))
                for node, surface in nodes:
                    self._check(node, surface, "%s %s cs=%d" % (
                        kind, node, mc.getAttr(node + ".colorSpace")))

    # -- BAREBONES_MODE (the inline diagnostic path) -------------------------

    def test_barebones_mode_too(self):
        from mpynode._api2.mpy_file import MPyFile as _Node

        _Node.BAREBONES_MODE = True
        self._run([None, "", _GRID, _MISSING, _GRID, ""], kinds=("default",))


class TestNothingBoundCarriesOver(unittest.TestCase):
    """runViewport binds transparent black before the Viewport tier runs, so a
    tier that binds nothing on a call -- like every shipped tier before this
    fix -- shows that instead of the previous image."""

    # The pre-fix shape: upload only when the image loads.
    _OLD_SOURCE = (
        "img = self.read_texture()\n"
        "if img is not None:\n"
        "    import maya.api.OpenMayaRender as omr\n"
        "    d = omr.MTextureDescription()\n"
        "    d.setToDefault2DTexture()\n"
        "    d.fWidth, d.fHeight = img.shape[1], img.shape[0]\n"
        "    d.fFormat = omr.MRenderer.kR32G32B32A32_FLOAT\n"
        "    t = self.texture_manager.acquireTexture(\n"
        "        'old::' + self.fileName, d,\n"
        "        np.ascontiguousarray(img, dtype=np.float32).tobytes(), False)\n"
        "    a = omr.MTextureAssignment()\n"
        "    a.texture = t\n"
        "    self.shader.setParameter('map', a)\n"
    )

    def setUp(self):
        from mpynode._api2.mpy_file import MPyFile as _Node

        self._bb             = _Node.BAREBONES_MODE
        _Node.BAREBONES_MODE = False
        mc.file(new=True, force=True)

    def tearDown(self):
        from mpynode._api2.mpy_file import MPyFile as _Node

        _Node.BAREBONES_MODE = self._bb

    def _assert_nothing(self, tex, previous=None):
        self.assertIsNotNone(tex, "nothing bound at all")
        self.assertIsNot(tex, previous, "the previous image is still bound")
        self.assertFalse(tex.pixels.any(),
                         "expected transparent black, got %r" % tex.name)

    def test_a_tier_that_binds_nothing_leaves_nothing_behind(self):
        from mpynode.wrappers.mpy_file import MPyFile

        f = MPyFile.create(name="vpOld#")
        f.set_viewport_expression(self._OLD_SOURCE)
        node    = f.get_name()
        surface = _Surface(node)
        self._assert_nothing(surface.draw())  # fresh node
        mc.setAttr(node + ".fileName", _GRID, type="string")
        grid = surface.draw()
        self.assertIsNotNone(grid, "the image was never bound")
        self.assertTrue(grid.pixels.any(), "the image was never bound")
        for path in ("", _MISSING):
            with self.subTest(fileName=path):
                mc.setAttr(node + ".fileName", path, type="string")
                self._assert_nothing(surface.draw(), grid)


if __name__ == "__main__":
    unittest.main()
