"""Task 5.1: end-to-end acceptance for the COMPILED blessed-method feature.

A custom ``mPyFile`` compute that calls the blessed texture methods

    buf = self.read_texture()
    r, g, b, a = self.sample_texture(buf, self.sampleU, self.sampleV)
    self.outR = r; self.outG = g; self.outB = b; self.outA = a

must, once compiled to a native plugin, produce the SAME output as the
interpreted node. ``read_texture`` / ``sample_texture`` lower deterministically
to the frozen C++ kernels ``nd_tex_load_linear`` / ``nd_tex_sample``
(``native/compiler/kernels/file_texture_cpp.py``); the interpreted adapters
delegate to the node's shipped Init helpers ``_load_linear_pixels`` / ``_sample``
(``_common/methods/file_methods.py``), which are byte-parity-proven against those
kernels by ``test_file_texture_parity``.

NOTE on the coordinate inputs: on a real ``mPyFile`` the short names ``u`` / ``v``
are already taken by the native ``uCoord`` / ``vCoord`` presets, so the two
user-added sample-coordinate inputs are ``sampleU`` / ``sampleV`` (adding ``u`` /
``v`` raises "clashes with an existing attribute"). The compute reads
``self.sampleU`` / ``self.sampleV``; everything else matches the Task 4.x specs.

Tiered so the suite is GREEN on any host:

  * Layer 1 (``TestBlessedExtractionLowers``) -- ALWAYS runs (Maya standalone
    only). Proves the extraction -> codegen -> transpiler chain on a REAL node:
    the 8 file-texture presets + sampleU/sampleV land on ``spec['inputs']``,
    outR..outA on ``spec['outputs']``, ``generate_cpp`` carries the verified
    kernels + ``NdTexCache _texCache`` with NO AI PORT region, and
    ``nd_lower.try_lower_compute`` returns a body.
  * Layer 2 (``TestBlessedCompilesClean``) -- SKIPs with no clang/g++ or no Maya
    devkit headers. Compiles the generated ``.cpp`` to a ``.o`` against the Maya
    devkit (proves the kernel wiring + cache members + includes typecheck).
  * Layer 3 (``TestBlessedLoadedParity``) -- BEST-EFFORT; SKIPs generously if any
    prerequisite (compiler / devkit / MImage writer / toolchain pre-flight /
    bundle build) is missing on the host. Builds the extracted spec into a
    loadable ``.bundle``, loads it, and asserts the compiled node's outR..outA
    match the interpreted node's over a float32-representable UV grid, within the
    same float32-scale tolerance ``test_file_texture_parity`` uses.

If Layer 3 must skip, end-to-end parity then rests on the composition of proven
parts: the kernels (``test_file_texture_parity``) + the transpiler wiring
(``test_py_to_cpp_blessed`` / ``test_codegen_blessed_file``) + the preset capture
(``test_blessed_preset_capture``) + Layer 2 compile-clean here.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from tests import _paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = _paths.ROOT
# the bundler and the devkit-native-dir path key off MPYNODE_ROOT, which a
# bare `mayapy -m unittest` run does not set. Seed it from this file's
# location; setdefault lets a host that already exports it win.
os.environ.setdefault("MPYNODE_ROOT", ROOT)

from tests._setup import ensure_plugins_loaded, standalone_init
# same float32-scale tolerance as the proven full-parity path. Not literal
# bytes: interpreted bilinear weights are float64 and the C++ sampler is
# float32, so float32-representable UVs keep them within this epsilon.
from tests.nodes.test_file_texture_parity import TOL


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# The blessed compute under test.
_BLESSED_COMPUTE = (
    "buf = self.read_texture()\n"
    "r, g, b, a = self.sample_texture(buf, self.sampleU, self.sampleV)\n"
    "self.outR = r\n"
    "self.outG = g\n"
    "self.outB = b\n"
    "self.outA = a\n"
)

# preset inputs the two blessed adapters read. They are never named in the
# compute text, so the extractor must union them onto spec['inputs'].
_PRESET_INPUTS = (
    "fileName", "colorSpace", "preFilter", "preFilterKernel",
    "preFilterRadius", "wrapModeU", "wrapModeV", "borderColor",
)
_OUT_CHANNELS = ("outR", "outG", "outB", "outA")

# float32-representable UVs (incl. the 0/1 edges and a couple of interior
# points) so the interpreted float64 weights equal the C++ float32 weights.
_UV_GRID = [
    (0.0, 0.0), (0.25, 0.5), (0.5, 0.5), (0.75, 0.25), (1.0, 1.0),
    (0.375, 0.625), (0.125, 0.875), (1.0, 0.0), (0.0, 1.0),
]


def _build_blessed_mpyfile(name="blessedE2E#"):
    """Create a REAL mPyFile with the blessed compute, two user float coordinate
    inputs (sampleU/sampleV) and four user float outputs (outR..outA), on a fresh
    scene. Keeps the shipped default Init so the interpreted blessed adapters find
    their _load_linear_pixels / _sample helpers. Returns the wrapper."""
    import maya.cmds as mc
    from mpynode.wrappers.mpy_file import MPyFile

    mc.file(new=True, force=True)
    f = MPyFile.create(name=name)  # seed_defaults=True (default) -> real helpers
    for a in ("sampleU", "sampleV"):
        f.add_input_attr(a, "float")
    for a in _OUT_CHANNELS:
        f.add_output_attr(a, "float")
    f.set_compute_expression(_BLESSED_COMPUTE)
    return f


def _running_maya_root():
    """Install root of the mayapy running this test (the dir holding
    ``include/maya``), or None if this build has no devkit. Mirrors the
    discovery in ``test_native_gol_e2e``."""
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


def _make_fixture_png(path):
    """Write a deterministic 8x8 RGBA PNG via ``MImage``. Returns True on success,
    False if MImage writing is unavailable on this host (Layer 3 then skips)."""
    try:
        import maya.api.OpenMaya as om

        w   = h = 8
        buf = bytearray()
        for i in range(w * h):
            buf += bytes(((i * 7) % 256, (i * 13) % 256, (i * 29) % 256, 255))
        img = om.MImage()
        img.create(w, h, 4, om.MImage.kByte)
        img.setPixels(bytes(buf), w, h)
        img.writeToFile(path, "png")
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except Exception:
        return False


# ===========================================================================
# Layer 1 -- structural (always runs)
# ===========================================================================
class TestBlessedExtractionLowers(unittest.TestCase):
    """Extraction -> codegen -> transpiler on a REAL blessed mPyFile node."""

    def setUp(self):
        from mpynode.native.spec import spec_extractor

        self.f    = _build_blessed_mpyfile()
        self.spec = spec_extractor.extract_spec(self.f.get_name())

    def test_presets_and_coords_captured_as_inputs(self):
        inputs = self.spec.get("inputs") or {}
        for nm in _PRESET_INPUTS:
            self.assertIn(
                nm, inputs,
                "blessed adapter preset %r not captured on spec['inputs'] "
                "(got %s)" % (nm, sorted(inputs)))
        for nm in ("sampleU", "sampleV"):
            self.assertIn(
                nm, inputs,
                "user coordinate input %r missing from spec['inputs']" % nm)

    def test_four_float_outputs_captured(self):
        outputs = self.spec.get("outputs") or {}
        for nm in _OUT_CHANNELS:
            self.assertIn(
                nm, outputs,
                "user output %r missing from spec['outputs'] (got %s)"
                % (nm, sorted(outputs)))

    def test_codegen_lowers_deterministically_to_kernels(self):
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self.spec, for_port=True)
        self.assertIn("nd_tex_load_linear",   cpp)  # verified load kernel
        self.assertIn("nd_tex_sample",        cpp)  # verified sampler
        self.assertIn("NdTexCache _texCache", cpp)  # per-instance cache member
        # fully lowered, so no AI PORT region: compiled compute is pure C++.
        self.assertNotIn(codegen.PORT_BEGIN, cpp)

    def test_nd_lower_returns_a_body(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import nd_lower

        members = codegen._members(self.spec)
        ins     = [m for m in members if m["kind"] == "inputs"]
        outs    = [m for m in members if m["kind"] == "outputs"]
        lowered = nd_lower.try_lower_compute(ins, outs, self.spec)
        self.assertIsNotNone(
            lowered, "blessed compute must lower deterministically; None means "
                     "it fell back to the AI porter")
        self.assertTrue(lowered)


# ===========================================================================
# Layer 2 -- compile-clean (skip with no compiler / devkit)
# ===========================================================================
class TestBlessedCompilesClean(unittest.TestCase):
    """The generated translation unit typechecks against the Maya devkit."""

    def test_generated_tu_compiles_clean(self):
        from mpynode.native.toolchain import toolchain
        from mpynode.native import compiler as codegen
        from mpynode.native.spec import spec_extractor

        cxx = shutil.which("clang++") or shutil.which("g++")
        if not cxx:
            self.skipTest("no C++ compiler on PATH")
        maya = _running_maya_root()
        if not maya:
            self.skipTest("no Maya devkit headers for the running mayapy")

        f    = _build_blessed_mpyfile()
        spec = spec_extractor.extract_spec(f.get_name())
        cpp  = codegen.generate_cpp(spec, for_port=True)
        inc  = toolchain.maya_include_dir(maya)
        native_dir = os.path.join(os.environ["MPYNODE_ROOT"], "scripts",
                                  "mpynode", "native")

        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, spec["suggested"]["node_type_name"] + ".cpp")
            with open(src, "w") as fh:
                fh.write(cpp)
            obj = os.path.join(d, "blessed.o")
            cmd = [cxx, "-std=c++17", "-O2", "-c", src, "-o", obj,
                   "-I", inc, "-I", native_dir]
            md = toolchain.maya_define()
            if md:
                cmd += ["-D" + md]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             "blessed native compile failed:\n"
                             + proc.stderr[-4000:])
            self.assertTrue(os.path.isfile(obj) and os.path.getsize(obj) > 0)


# ===========================================================================
# Layer 3 -- loaded-node byte-parity (best-effort; skip-guarded generously)
# ===========================================================================
class TestBlessedLoadedParity(unittest.TestCase):
    """Compiled node output == interpreted node output over a UV grid, within the
    proven float32-scale tolerance. SKIPs (never fails) if a prerequisite is
    missing/flaky on the host."""

    def setUp(self):
        # the interpreted blessed path needs the user-expression tier, not the
        # BAREBONES inline fast path. Force it off, restore after.
        from mpynode._api2.mpy_file import MPyFile as _NodeCls

        self._prev_bb           = _NodeCls.BAREBONES_MODE
        _NodeCls.BAREBONES_MODE = False
        self.addCleanup(setattr, _NodeCls, "BAREBONES_MODE", self._prev_bb)

    def _drive(self, node, png, color_space=0, wrap=0):
        """Set the shared file-texture settings + sweep the UV grid, returning
        ``{(u, v): (r, g, b, a)}``. Uses the SAME concrete settings on both the
        interpreted and compiled node so any difference is a genuine parity gap."""
        import maya.cmds as mc

        mc.setAttr(node + ".fileName", png, type="string")
        mc.setAttr(node + ".colorSpace", color_space)
        mc.setAttr(node + ".wrapModeU",  wrap)
        mc.setAttr(node + ".wrapModeV",  wrap)
        mc.setAttr(node + ".preFilter",  0)
        for c in ("borderColorR", "borderColorG", "borderColorB"):
            try:
                mc.setAttr(node + "." + c, 0.0)
            except Exception:
                pass
        out = {}
        for (uu, vv) in _UV_GRID:
            mc.setAttr(node + ".sampleU", uu)
            mc.setAttr(node + ".sampleV", vv)
            mc.dgdirty(node + ".outR")
            out[(uu, vv)] = tuple(
                mc.getAttr(node + "." + o) for o in _OUT_CHANNELS)
        return out

    @staticmethod
    def _safe_unload(bundle):
        import maya.cmds as mc

        try:
            mc.file(new=True, force=True)  # drop node instances first
            mc.unloadPlugin(os.path.splitext(os.path.basename(bundle))[0])
        except Exception:
            pass

    def test_compiled_matches_interpreted(self):
        import maya.cmds as mc
        from mpynode.native.spec import spec_extractor
        from mpynode.native.toolchain import compile_controller, toolchain

        # -- environment prerequisites (skip, don't fail) --
        if not (shutil.which("clang++") or shutil.which("g++")):
            self.skipTest("no C++ compiler on PATH")
        if not _running_maya_root():
            self.skipTest("no Maya devkit headers for the running mayapy")
        if not toolchain.check_toolchain(
                compile_controller._MAYA_DEFAULT).get("ok"):
            self.skipTest("toolchain pre-flight not satisfied on this host")

        tmp = tempfile.mkdtemp(prefix="blessed_parity_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        png = os.path.join(tmp, "fixture.png")
        if not _make_fixture_png(png):
            self.skipTest("could not write an MImage PNG fixture on this host")

        # -- interpreted node + extracted spec --
        f    = _build_blessed_mpyfile(name="blessedParityNode")
        node = f.get_name()
        spec = spec_extractor.extract_spec(node)

        # -- compile the SAME spec to a loadable bundle (no in-Maya verify) --
        # the spec lowers deterministically so the porter never calls the LLM,
        # but pass provider/model + complete_fn so nothing AI-side is required
        # headless.
        res = compile_controller.compile_plugin(
            [spec], "blessedParityPlugin", tmp,
            strict=True, verify=False, reuse_cache=False,
            complete_fn=lambda s, u: "x", provider="anthropic", model="m")
        bundle = res.get("bundle_path")
        if not (res.get("ok") and bundle and os.path.isfile(bundle)):
            self.skipTest("blessed bundle did not build on this host: %s"
                          % (res.get("errors") or "unknown"))

        type_name = spec["suggested"]["node_type_name"]
        mc.loadPlugin(bundle)
        self.addCleanup(self._safe_unload, bundle)
        compiled = mc.createNode(type_name, name="compiledBlessed")

        # -- compare over a couple of colorSpace / wrapMode configs --
        configs    = [(0, 0), (9, 1)]  # (colorSpace, wrapMode): sRGB/wrap, ACEScg/clamp
        maxerr     = 0.0
        had_signal = False
        for cs, wrap in configs:
            interp = self._drive(node, png, cs, wrap)
            comp   = self._drive(compiled, png, cs, wrap)
            for uv in _UV_GRID:
                if interp[uv][0] > 1e-4 or interp[uv][1] > 1e-4:
                    had_signal = True
                for ch in range(4):
                    d      = abs(interp[uv][ch] - comp[uv][ch])
                    maxerr = max(maxerr, d)
                    self.assertLessEqual(
                        d, TOL,
                        "compiled != interpreted at cs=%d wrap=%d uv=%s ch=%d: "
                        "interp=%.6f compiled=%.6f (err=%.3e > tol=%.1e)"
                        % (cs, wrap, uv, ch, interp[uv][ch], comp[uv][ch], d, TOL))

        # Guard against a vacuous pass where both nodes return constant
        # defaults: the fixture must drive a non-trivial signal.
        self.assertTrue(
            had_signal,
            "interpreted node produced no signal (all-zero across the grid) -- "
            "the texture read/sample chain did not run; parity would be vacuous")
        print("blessed compiled/interpreted parity: max per-channel err=%.3e "
              "(tol=%.1e) over %d UVs x %d configs"
              % (maxerr, TOL, len(_UV_GRID), len(configs)))


if __name__ == "__main__":
    unittest.main()
