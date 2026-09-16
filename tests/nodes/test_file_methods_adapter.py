import unittest
import maya.standalone
maya.standalone.initialize()
import maya.cmds as mc
from mpynode.wrappers.mpy_file import MPyFile


class TestFileMethodAdapters(unittest.TestCase):
    def setUp(self):
        if not mc.pluginInfo("mpynode_api2", q=True, loaded=True):
            mc.loadPlugin("mpynode_api2")

    def test_get_init_helper_reaches_sampler(self):
        node = MPyFile.create(name="probeFile#")
        node.set_compute_expression(
            "llp = self.get_init_helper('_load_linear_pixels')\n"
            "smp = self.get_init_helper('_sample')\n"
            "self.outAlpha = 1.0 if callable(llp) and callable(smp) else -1.0\n"
            "self.outColor = (0.0, 0.0, 0.0)")
        self.assertEqual(mc.getAttr(node._name + ".outAlpha"), 1.0)

    def test_read_then_sample_roundtrip_magenta_sentinel(self):
        node = MPyFile.create(name="rtFile#")
        node.set_compute_expression(
            "buf = self.read_texture()\n"
            "r, g, b, a = self.sample_texture(buf, 0.5, 0.5)\n"
            "self.outColor = (r, g, b)\n"
            "self.outAlpha = a")
        # No fileName -> read_texture() None -> sample_texture magenta sentinel.
        self.assertAlmostEqual(mc.getAttr(node._name + ".outColorR"), 1.0)
        self.assertAlmostEqual(mc.getAttr(node._name + ".outColorG"), 0.0)
        self.assertAlmostEqual(mc.getAttr(node._name + ".outColorB"), 1.0)
        self.assertAlmostEqual(mc.getAttr(node._name + ".outAlpha"),  1.0)


class TestWriteTexture(unittest.TestCase):
    """write_texture is the bake half of the blessed pair: a stateful node whose
    OSL tier cannot evaluate it from (u, v, t) writes the frame to a file the
    shader then samples. It must round-trip, flip rows (MImage is bottom-up), and
    return False rather than raise -- a raising call could not be lowered."""

    def _rgba(self, board):
        import numpy as np

        a            = board.astype(np.float32)
        out          = np.zeros((board.shape[0], board.shape[1], 4), dtype=np.float32)
        out[:, :, 0] = a
        out[:, :, 1] = a
        out[:, :, 2] = a
        out[:, :, 3] = 1.0
        return out

    def test_roundtrip_preserves_orientation(self):
        import ctypes
        import os
        import tempfile

        import numpy as np
        import maya.api.OpenMaya as om

        from mpynode._common.methods.file_methods import write_texture

        # NOT square and NOT symmetric, so a transpose or a flip cannot pass.
        board       = np.zeros((3, 5), dtype=bool)
        board[0, 0] = True
        board[0, 4] = True
        board[2, 1] = True
        path        = os.path.join(tempfile.mkdtemp(prefix="wtex_"), "b.png")
        self.assertTrue(write_texture(None, path, self._rgba(board)))

        img = om.MImage()
        img.readFromFile(path)
        w, h = img.getSize()
        self.assertEqual((h, w), (3, 5))
        raw = ctypes.string_at(img.pixels(), w * h * 4)
        got = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)[::-1]
        self.assertTrue(np.array_equal(got[:, :, 0] > 127, board))

    def test_an_empty_path_returns_false(self):
        """Mirrors the C++ kernel's `path.empty()` guard -- "no bake target" is
        how a node says "do not bake", not an error."""
        import numpy as np

        from mpynode._common.methods.file_methods import write_texture

        board = np.zeros((2, 2), dtype=bool)
        self.assertFalse(write_texture(None, "", self._rgba(board)))

    def test_a_buffer_that_is_not_hw4_returns_false(self):
        """Mirrors the C++ kernel's `shape.size() != 3 || shape[2] != 4` guard.
        Returning False (not raising) is what keeps the call lowerable."""
        import os
        import tempfile

        import numpy as np

        from mpynode._common.methods.file_methods import write_texture

        path = os.path.join(tempfile.mkdtemp(prefix="wtex_"), "bad.png")
        self.assertFalse(
            write_texture(None, path, np.zeros((3, 5), dtype=np.float32)))


if __name__ == "__main__":
    unittest.main()
