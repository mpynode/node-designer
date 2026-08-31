import unittest

from mpynode._common.interface.file_method_interface import INTERNAL_API_METHODS
from mpynode._common.interface.api_methods import validate, CppKernel
from mpynode._common.interface import file_texture_interface as fti


class TestFileMethodRegistry(unittest.TestCase):
    def test_has_the_read_sample_write_trio(self):
        names = {m.name for m in INTERNAL_API_METHODS}
        self.assertEqual(names,
                         {"read_texture", "sample_texture", "composite_layers",
                          "write_texture"})

    def test_all_are_cpp_kernels(self):
        by = {m.name: m for m in INTERNAL_API_METHODS}
        self.assertEqual(by["read_texture"].lower, CppKernel("nd_tex_load_linear"))
        self.assertEqual(by["sample_texture"].lower, CppKernel("nd_tex_sample"))
        self.assertEqual(by["composite_layers"].lower,
                         CppKernel("nd_tex_composite_layers"))
        self.assertEqual(by["write_texture"].lower, CppKernel("nd_tex_write"))

    def test_no_collision_with_file_plugs(self):
        plug_names = set(fti.build_porter_meta_table().keys())
        validate(INTERNAL_API_METHODS, plug_names)  # must not raise

    def test_reads_declare_adapter_preset_inputs(self):
        # The `reads` of each blessed method must mirror EXACTLY the preset DG
        # attrs its interpreted adapter (file_methods) reads -- this is the
        # paired contract the spec extractor unions into the compiled spec.
        by = {m.name: m for m in INTERNAL_API_METHODS}
        self.assertEqual(
            by["read_texture"].reads,
            ("fileName", "colorSpace", "preFilter", "preFilterKernel",
             "preFilterRadius"))
        self.assertEqual(
            by["sample_texture"].reads,
            ("wrapModeU", "wrapModeV", "borderColor"))
        # composite_layers does read+sample per layer, so it reads the UNION of
        # the two above -- minus fileName, whose job the `layers` argument does.
        self.assertEqual(
            by["composite_layers"].reads,
            ("colorSpace", "preFilter", "preFilterKernel", "preFilterRadius",
             "wrapModeU", "wrapModeV", "borderColor"))
        # write_texture takes its path AND its pixels as explicit arguments, so
        # it reads no preset off the node -- nothing to union into the spec.
        self.assertEqual(by["write_texture"].reads, ())

    def test_all_reads_are_real_file_plugs(self):
        # Every declared read must be a real mPyFile preset plug (else the
        # extractor's table lookup would silently drop it).
        plug_names = set(fti.build_porter_meta_table().keys())
        for m in INTERNAL_API_METHODS:
            for nm in m.reads:
                self.assertIn(nm, plug_names,
                              "%s declares read %r that is not a file plug"
                              % (m.name, nm))


if __name__ == "__main__":
    unittest.main()
