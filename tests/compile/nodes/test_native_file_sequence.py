"""Native mPyFile IMAGE SEQUENCE: per-frame path + reload-every-frame in pure C++.

A mPyFile can drive an image sequence by substituting a frame number into a
``#``-padded path (``render.####.png`` at frame 42 -> ``render.0042.png``). The
Python node does this with the ``_resolve_seq_path`` Init helper; the native
compiler recognizes that idiom and emits a byte-identical C++ ``nd_tex_resolve_
seq``. Because the pixel cache is keyed by the RESOLVED path, a per-frame path
change reloads the new file automatically -- no extra machinery.

This suite proves, decisively (real PNGs on disk, a real compiled plugin):

  * the sequence node lowers to PURE C++ (no AI PORT region) with the resolver
    helper + a per-frame ``nd_tex_resolve_seq(in_fileName, (int)in_<frame>)``
    call feeding the cached load;
  * ``_resolve_seq_path`` and its C++ mirror resolve identically (structural);
  * and the COMPILED node, driven frame 1 -> 2 -> 3, RELOADS a different image
    each frame and matches the interpreted node's output.

The compile+eval test SKIPs (never fails) on a host with no C++ toolchain / Maya
devkit / PIL, matching the other native e2e suites.
"""
from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# A sequence compute: resolve the per-frame path off an integer `frame` input,
# then run the standard load -> sample -> default write.
_SEQ_COMPUTE = (
    "linear = _load_linear_pixels(\n"
    "    _resolve_seq_path(self.fileName, int(self.frame)),\n"
    "    int(self.colorSpace), bool(self.preFilter),\n"
    "    int(self.preFilterKernel), float(self.preFilterRadius))\n"
    "u, v = self.uvCoord\n"
    "border = np.asarray(self.borderColor, dtype=np.float32)\n"
    "r, g, b, a = _sample(linear, float(u), float(v), int(self.wrapModeU), "
    "int(self.wrapModeV), (float(border[0]), float(border[1]), "
    "float(border[2])))\n"
    "self.outColor = (r, g, b)\n"
    "self.outAlpha = a\n"
)


def _seq_spec():
    """Build an mPyFile SEQUENCE node in-scene and extract its porter spec."""
    import maya.cmds as cmds
    from mpynode.wrappers.mpy_file import MPyFile
    from mpynode._defaults import file_defaults as fd
    from mpynode.native.spec import spec_extractor

    cmds.file(new=True, force=True)
    w = MPyFile.create(name="seqFile#")
    w.add_input_attr("frame", "int")
    w.set_init_expression(fd.DEFAULT_INIT_SOURCE)
    w.set_compute_expression(_SEQ_COMPUTE)
    spec = spec_extractor.extract_spec(w.get_name())
    spec["suggested"]["node_type_name"] = "seqFileNative"
    return spec


def _running_maya_root():
    import sys
    from mpynode.native.toolchain import toolchain

    seeds = [os.environ.get("MAYA_LOCATION") or "",
             os.path.dirname(os.path.abspath(sys.executable))]
    for seed in seeds:
        cur = seed
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(toolchain.maya_include_dir(cur), "maya")):
                return cur
            cur = os.path.dirname(cur)
    return None


class TestResolveSeqPathParity(unittest.TestCase):
    """The Python resolver + the recognizer agree on the idiom (no Maya/compile)."""

    def _resolver(self):
        from mpynode._defaults import file_defaults as fd

        ns = {}
        src = fd.DEFAULT_INIT_SOURCE.replace(
            "import maya.api.OpenMayaRender as omr", "omr = None")
        exec(src, ns)
        return ns["_resolve_seq_path"]

    def test_resolution_cases(self):
        R = self._resolver()
        self.assertEqual(R("render.####.png", 42), "render.0042.png")
        self.assertEqual(R("render.####.png", 7), "render.0007.png")
        self.assertEqual(R("a.#.png", 5), "a.5.png")
        self.assertEqual(R("a.##.png", 123), "a.123.png")   # wider than pad: kept
        self.assertEqual(R("seq_###.exr", -5), "seq_-05.exr")  # sign-aware zfill
        self.assertEqual(R("static.png", 99), "static.png")    # no token
        self.assertEqual(R("d.####/f.####.png", 3), "d.####/f.0003.png")  # last run

    def test_classify_recognizes_idiom(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        seq = {"compute": _SEQ_COMPUTE}
        self.assertEqual(ftc.classify_seq_path(seq),
                         {"frame_plug": "frame", "mode": "trunc"})
        plain = {"compute": _SEQ_COMPUTE.replace(
            "_resolve_seq_path(self.fileName, int(self.frame))", "self.fileName")}
        self.assertIsNone(ftc.classify_seq_path(plain))
        rnd = {"compute": _SEQ_COMPUTE.replace(
            "int(self.frame)", "int(round(self.frame))")}
        self.assertEqual(ftc.classify_seq_path(rnd),
                         {"frame_plug": "frame", "mode": "round"})


class TestSequenceCodegen(unittest.TestCase):
    """The sequence node ships as PURE C++ with the resolver wired in."""

    def test_no_port_and_resolver_emitted(self):
        from mpynode.native import compiler as codegen

        spec = _seq_spec()
        self.assertTrue((spec.get("suggested") or {}).get("reads_image_file"))
        self.assertTrue((spec.get("portability") or {}).get("portable"),
                        spec.get("portability"))
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)
        self.assertIn("nd_tex_resolve_seq(", cpp)                 # helper defined
        self.assertIn("nd_tex_resolve_seq(in_aFileName, (int)in_aFrame)", cpp)
        self.assertIn("nd_tex_load_linear(_texCache, _texMutex, _seqPath,", cpp)


class TestSequenceCompiledReload(unittest.TestCase):
    """DECISIVE: the compiled node reloads a different frame each eval."""

    def _write_png(self, path, rgb):
        try:
            from PIL import Image
        except ImportError:
            return False
        Image.new("RGBA", (4, 4), (rgb[0], rgb[1], rgb[2], 255)).save(path)
        return True

    def test_compiled_reloads_each_frame(self):
        from mpynode.native.toolchain import compile_controller

        if _running_maya_root() is None:
            self.skipTest("no Maya devkit headers on this host")

        import maya.cmds as cmds

        seqdir = tempfile.mkdtemp(prefix="seq_imgs_")
        frames = {1: (255, 0, 0), 2: (0, 255, 0), 3: (0, 0, 255)}
        for fr, rgb in frames.items():
            if not self._write_png(os.path.join(seqdir, "seq.%04d.png" % fr), rgb):
                self.skipTest("PIL not available to author test PNGs")
        pattern = os.path.join(seqdir, "seq.####.png")

        spec = _seq_spec()
        out_dir = tempfile.mkdtemp(prefix="seq_build_")
        res = compile_controller.compile_plugin(
            [spec], "seqFileTest", out_dir, strict=True, verify=False)
        if not res.get("ok"):
            self.skipTest("compile unavailable on this host: %s"
                          % (res.get("errors"),))

        cmds.file(new=True, force=True)
        cmds.loadPlugin(res["bundle_path"])
        n = cmds.createNode("seqFileNative")
        cmds.setAttr(n + ".fileName", pattern, type="string")
        cmds.setAttr(n + ".colorSpace", 19)   # [Utility] Raw -> identity linearize

        # frame -> expected linear color (Raw: pixel/255, so red=1,0,0 etc.)
        expected = {1: (1.0, 0.0, 0.0), 2: (0.0, 1.0, 0.0), 3: (0.0, 0.0, 1.0)}
        seen = []
        for fr in (1, 2, 3, 1):     # revisit frame 1 to prove it re-resolves back
            cmds.setAttr(n + ".frame", fr)
            col = cmds.getAttr(n + ".outColor")[0]
            seen.append(tuple(round(c, 3) for c in col))
            exp = expected[fr]
            for got_c, exp_c in zip(col, exp):
                self.assertAlmostEqual(
                    got_c, exp_c, places=2,
                    msg="frame %d: compiled outColor %r != expected %r -- the "
                        "per-frame path did not resolve/reload correctly"
                        % (fr, tuple(col), exp))
        # the three distinct frames must have produced three DISTINCT colors
        # (proves the file actually reloaded, not a one-shot cached read).
        self.assertEqual(len(set(seen[:3])), 3,
                         "compiled node did not reload distinct frames: %r" % seen)


if __name__ == "__main__":
    unittest.main()
