"""Maya-FREE: blessed-method interception in the numpy->C++ transpiler (Task 4.1).

Proves the transpiler lowers ``buf = self.read_texture()`` +
``r, g, b, a = self.sample_texture(buf, u, v)`` to the hand-written texture
kernels (nd_tex_load_linear / nd_tex_sample) via the blessed / blessed_unpack
callables built by ``file_texture_cpp.make_blessed_lowerings`` -- no Maya, no AI.
"""
from __future__ import annotations

import unittest

from mpynode.native.compiler.py_to_cpp import transpile_compute_block, scalar_t
from mpynode.native.compiler.errors import UnsupportedSpec
from mpynode.native.compiler.kernels import file_texture_cpp


# Minimal codegen-style input descriptors (plug -> C++ MObject member); the
# blessed lowering reads each preset's `in_<member>` local by plug name.
_ALL_INPUTS = [
    {"plug": "fileName", "member": "aFileName"},
    {"plug": "colorSpace", "member": "aColorSpace"},
    {"plug": "preFilter", "member": "aPreFilter"},
    {"plug": "preFilterKernel", "member": "aPreFilterKernel"},
    {"plug": "preFilterRadius", "member": "aPreFilterRadius"},
    {"plug": "wrapModeU", "member": "aWrapModeU"},
    {"plug": "wrapModeV", "member": "aWrapModeV"},
    {"plug": "borderColor", "member": "aBorderColor"},
]

_COMPUTE = (
    "buf = self.read_texture()\n"
    "r, g, b, a = self.sample_texture(buf, u, v)\n"
    "self.outR = r\n"
    "self.outG = g\n"
    "self.outB = b\n"
    "self.outA = a\n"
)


def _writers():
    def mk(name):
        return lambda val: ["%s = %s;" % (name, val.code)]
    return {"self.outR": mk("R"), "self.outG": mk("G"),
            "self.outB": mk("B"), "self.outA": mk("A")}


def _transpile(ins, compute=_COMPUTE):
    spec = {"mpy_type": "mPyFile", "compute": compute}
    blessed, blessed_unpack = file_texture_cpp.make_blessed_lowerings(
        ins, [], spec)
    env = {"u": scalar_t("double"), "v": scalar_t("double")}
    res, _written, _helpers = transpile_compute_block(
        compute, env, _writers(), blessed=blessed,
        blessed_unpack=blessed_unpack)
    return "\n".join(res.all_lines())


class TestBlessedTexTranspile(unittest.TestCase):
    def test_emits_both_kernel_calls_and_unpack(self):
        cpp = _transpile(list(_ALL_INPUTS))
        # read_texture -> the cached MImage load kernel with the cache + mutex.
        self.assertIn("nd_tex_load_linear(_texCache, _texMutex", cpp)
        # sample_texture -> the wrap-aware bilinear sampler.
        self.assertIn("nd_tex_sample(", cpp)
        # the tuple-unpack produced four (double)-cast channel assignments.
        self.assertEqual(cpp.count("= (double)"), 4)
        # the load wired the mPyFile presets from their in_<member> locals,
        # byte-mirroring the interpreted adapter + full-parity glue.
        self.assertIn("in_aFileName",        cpp)
        self.assertIn("(int)in_aColorSpace", cpp)
        self.assertIn("in_aPreFilter != 0",  cpp)
        self.assertIn("(int)in_aWrapModeU",  cpp)
        self.assertIn("in_aBorderColor[0]",  cpp)

    def test_missing_colorspace_member_rejects(self):
        # parity-or-reject: a captured surface missing colorSpace cannot lower
        # the load faithfully -> the load callable raises when transpiled.
        ins = [i for i in _ALL_INPUTS if i["plug"] != "colorSpace"]
        with self.assertRaises(UnsupportedSpec):
            _transpile(ins)

    def test_non_blessed_spec_yields_empty_maps(self):
        blessed, blessed_unpack = file_texture_cpp.make_blessed_lowerings(
            [], [], {"mpy_type": "mPyNode", "compute": ""})
        self.assertEqual((blessed, blessed_unpack), ({}, {}))

    def test_inline_read_into_sample_lowers(self):
        # the VALID inline idiom: pass read_texture() straight into
        # sample_texture() with no intermediate name binding.
        cpp = _transpile(
            list(_ALL_INPUTS),
            "r, g, b, a = self.sample_texture(self.read_texture(), u, v)\n")
        self.assertIn("nd_tex_load_linear(_texCache, _texMutex", cpp)
        self.assertIn("nd_tex_sample(", cpp)
        self.assertEqual(cpp.count("= (double)"), 4)


class TestTexbufLeakRejects(unittest.TestCase):
    """Parity-or-reject: a texbuf handle that reaches ANY context other than
    sample_texture()'s first arg must raise UnsupportedSpec (honest reject),
    never emit non-compiling C++ referencing a stray pointer/undeclared name."""

    def test_reused_handle_arithmetic_rejects(self):
        # (a) bound name reused in arithmetic (nl_buf is an undeclared identifier;
        # the real load var is tb_N) -> reject.
        with self.assertRaises(UnsupportedSpec):
            _transpile(list(_ALL_INPUTS),
                       "buf = self.read_texture()\nx = buf * 2\n")

    def test_inline_handle_arithmetic_rejects(self):
        # (b) inline read_texture() in arithmetic (would emit (double)(pointer)).
        with self.assertRaises(UnsupportedSpec):
            _transpile(list(_ALL_INPUTS),
                       "x = self.read_texture() + 1\n")

    def test_reused_handle_in_numpy_rejects(self):
        # (c) bound handle passed to np.maximum -> reject.
        with self.assertRaises(UnsupportedSpec):
            _transpile(list(_ALL_INPUTS),
                       "buf = self.read_texture()\ny = np.maximum(buf, 0.0)\n")

    def test_reused_handle_as_condition_rejects(self):
        with self.assertRaises(UnsupportedSpec):
            _transpile(list(_ALL_INPUTS),
                       "buf = self.read_texture()\nif buf:\n    x = 1\n")

    def test_inline_handle_division_rejects(self):
        # the Div branch of _array_binop conditionally skips the coercion
        # chokepoints on a non-array operand -> the central _array_binop guard
        # must still reject a texbuf here.
        with self.assertRaises(UnsupportedSpec):
            _transpile(list(_ALL_INPUTS),
                       "x = self.read_texture() / 2.0\n")


class TestTupleColorPack(unittest.TestCase):
    """A tuple literal in expression position lowers to a rank-1 nd::Array pack
    (py_to_cpp.ex_Tuple) -- e.g. ``self.outColor = (r, g, b)`` after a blessed
    sample_texture unpack. Empty / nested tuples honest-reject."""

    def _transpile(self, compute, writers):
        spec = {"mpy_type": "mPyFile", "compute": compute}
        blessed, blessed_unpack = file_texture_cpp.make_blessed_lowerings(
            list(_ALL_INPUTS), [], spec)
        env = {"u": scalar_t("double"), "v": scalar_t("double")}
        return transpile_compute_block(
            compute, env, writers, blessed=blessed,
            blessed_unpack=blessed_unpack)

    def test_tuple_pack_lowers_to_nd_array(self):
        captured = {}

        def color_writer(val):
            captured["val"] = val
            return ["outColor = %s;" % val.code]

        compute = (
            "r, g, b, a = self.sample_texture(self.read_texture(), u, v)\n"
            "self.outColor = (r, g, b)\n")
        res, _written, _helpers = self._transpile(
            compute, {"self.outColor": color_writer})
        self.assertIn("val", captured)
        self.assertEqual(captured["val"].type.kind, "array")
        cpp = "\n".join(res.all_lines())
        self.assertIn("nd::from_data<double>(", cpp)

    def test_empty_and_nested_tuple_reject(self):
        for pack in ("()", "((1, 2), 3, 4)"):
            compute = (
                "r, g, b, a = self.sample_texture(self.read_texture(), u, v)\n"
                "self.outColor = %s\n" % pack)
            with self.assertRaises(UnsupportedSpec):
                self._transpile(
                    compute,
                    {"self.outColor": lambda val: ["outColor = %s;" % val.code]})

    def test_tuple_return_rejects(self):
        # A tuple literal packs fine as an ASSIGNMENT RHS, but `return (a, b)`
        # would lower to `return <nd::Array>;` inside a body that returns
        # MStatus -> non-compiling C++. Must honest-reject.
        for ret in ("return (r, g)", "return [r, g]"):
            compute = (
                "r, g, b, a = self.sample_texture(self.read_texture(), u, v)\n"
                + ret + "\n")
            with self.assertRaises(UnsupportedSpec):
                self._transpile(
                    compute,
                    {"self.outColor": lambda val: ["outColor = %s;" % val.code]})


if __name__ == "__main__":
    unittest.main()
