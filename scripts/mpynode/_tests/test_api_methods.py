import unittest

from mpynode._common.interface.api_methods import (
    MethodSpec, CppKernel, Transpile, validate,
)


class TestMethodSpec(unittest.TestCase):
    def test_fields(self):
        m = MethodSpec(
            name="read_texture",
            sig="read_texture() -> ndarray(H, W, 4) float32",
            doc="Load + linearize + prefilter; cached.",
            runtime="mpynode._common.methods.file_methods:read_texture",
            lower=CppKernel("nd_tex_load_linear"),
        )
        self.assertEqual(m.name, "read_texture")
        self.assertEqual(m.lower.kernel, "nd_tex_load_linear")

    def test_transpile_marker(self):
        self.assertEqual(Transpile("_load_linear_pixels").free_fn,
                         "_load_linear_pixels")

    def test_reads_defaults_to_empty_tuple(self):
        # `reads` is the LAST field and defaults to () so existing 5-arg
        # constructions stay valid.
        m = MethodSpec("m", "m()", "", "mod:m", CppKernel("k"))
        self.assertEqual(m.reads, ())

    def test_reads_declares_preset_attr_names(self):
        m = MethodSpec("m", "m()", "", "mod:m", CppKernel("k"),
                       reads=("colorSpace", "borderColor"))
        self.assertEqual(m.reads, ("colorSpace", "borderColor"))

    def test_validate_rejects_plug_name_collision(self):
        specs = (MethodSpec("uvCoord", "uvCoord()", "", "m:uvCoord",
                            CppKernel("k")),)
        with self.assertRaises(ValueError):
            validate(specs, plug_names={"uvCoord"})

    def test_validate_rejects_duplicate_method_name(self):
        specs = (
            MethodSpec("a", "a()", "", "m:a", CppKernel("k")),
            MethodSpec("a", "a()", "", "m:a", CppKernel("k")),
        )
        with self.assertRaises(ValueError):
            validate(specs, plug_names=set())

    def test_validate_accepts_clean(self):
        specs = (MethodSpec("read_texture", "read_texture()", "",
                            "m:read_texture", CppKernel("k")),)
        validate(specs, plug_names={"fileName", "uvCoord"})  # no raise


if __name__ == "__main__":
    unittest.main()
