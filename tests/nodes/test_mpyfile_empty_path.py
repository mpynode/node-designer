"""An interpreted mPyFile treats a cleared fileName exactly as a missing file.

read_texture() hands the path to load_linear_pixels, which answers None for
"" and for a path that is not a file alike; the node then falls back to its
baked ``embeddedImage`` when it carries one, else samples magenta and derives
outSize (0, 0). In compute, clearing the path drops the image -- nothing of
the last good file survives -- and setting it again restores it. These are the
four sequences the compiled node is held to (bug pass 5, 2026-10-03). The
behaviour was already right, so this pins it rather than failing first; it
covers the computed outputs only, not the viewport.
"""
from __future__ import annotations

import os
import unittest

import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_GRID    = os.path.join(_paths.SCRIPTS, "mpynode", "_demos", "data", "test_grid.png")
_MISSING = os.path.join(_paths.ROOT, "tests", "no_such_texture_empty_path.png")
_UVS     = ((0.3, 0.6), (0.71, 0.2), (0.05, 0.93))
_MAGENTA = (1.0, 0.0, 1.0)


class TestEmptyPathIsMissingPath(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.assertTrue(os.path.isfile(_GRID), _GRID)
        self.assertFalse(os.path.exists(_MISSING), _MISSING)
        self.f = MPyFile.create(name="emptyPath")
        self.n = self.f.get_name()

    def _set(self, path):
        mc.setAttr(self.n + ".fileName", path, type="string")

    def _read(self):
        out = []
        for u, v in _UVS:
            mc.setAttr(self.n + ".uCoord", u)
            mc.setAttr(self.n + ".vCoord", v)
            out.append((tuple(round(c, 6) for c in mc.getAttr(self.n + ".outColor")[0]),
                        round(mc.getAttr(self.n + ".outAlpha"), 6),
                        tuple(mc.getAttr(self.n + ".outSize")[0])))
        return out

    def _no_image(self, got):
        for color, alpha, size in got:
            self.assertEqual(color, _MAGENTA)
            self.assertEqual(alpha, 1.0)
            self.assertEqual(size,  (0.0, 0.0))

    def test_empty_and_missing_take_the_same_path(self):
        self._set("")
        empty = self._read()
        self._set(_MISSING)
        self.assertEqual(self._read(), empty)
        self._no_image(empty)

    def test_valid_empty_valid(self):
        self._set(_GRID)
        valid = self._read()
        self.assertEqual(valid[0][2], (1024.0, 1024.0))
        self.assertNotEqual(valid[0][0], _MAGENTA)
        self._set("")
        self._no_image(self._read())
        self._set(_GRID)
        self.assertEqual(self._read(), valid)

    def test_valid_missing_valid(self):
        self._set(_GRID)
        valid = self._read()
        self._set(_MISSING)
        self._no_image(self._read())
        self._set(_GRID)
        self.assertEqual(self._read(), valid)

    def test_both_fall_back_to_the_embedded_image(self):
        self._set(_GRID)
        valid = self._read()
        with open(_GRID, "rb") as fh:
            self.f.set_variable("embeddedImage", fh.read(), persistent=True)
        for path in ("", _MISSING):
            with self.subTest(fileName=path):
                self._set(path)
                self.assertEqual(self._read(), valid)


if __name__ == "__main__":
    unittest.main()
