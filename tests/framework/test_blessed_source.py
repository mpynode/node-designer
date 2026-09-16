import unittest
from mpynode._common.methods.blessed_source import resolve_method_source
from mpynode._common.interface import skin_method_interface as smi
from mpynode._common.interface import file_method_interface as fmi
class TestResolveMethodSource(unittest.TestCase):
    def test_transpile_spec_resolves_to_skin_blend(self):
        spec = [m for m in smi.INTERNAL_API_METHODS if m.name == "dual_quaternion"][0]
        res  = resolve_method_source(spec)
        self.assertIsNotNone(res)
        path, line = res
        self.assertTrue(path.endswith("skin_blend.py"), path)
        with open(path) as fh:
            lines = fh.read().splitlines()
        self.assertIn("def dual_quaternion", lines[line - 1])
    def test_cppkernel_spec_resolves_to_file_methods(self):
        spec = [m for m in fmi.INTERNAL_API_METHODS if m.name == "read_texture"][0]
        res  = resolve_method_source(spec)
        self.assertIsNotNone(res)
        path, line = res
        self.assertTrue(path.endswith("file_methods.py"), path)
        with open(path) as fh:
            lines = fh.read().splitlines()
        self.assertIn("def read_texture", lines[line - 1])
    def test_bad_ref_returns_none(self):
        class Fake:
            lower   = None
            runtime = "no_colon_here"
        self.assertIsNone(resolve_method_source(Fake()))
if __name__ == "__main__":
    unittest.main()
