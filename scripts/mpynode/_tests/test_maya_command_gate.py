import ast
import unittest
from mpynode._common.methods.maya_command import _is_instance_def


def _last(src):
    return ast.parse(src).body[-1]


class TestIsInstanceDef(unittest.TestCase):
    def test_self_first_accepted(self):
        self.assertTrue(_is_instance_def(_last("def setup(self):\n    pass\n")))

    def test_self_first_varargs_accepted(self):
        self.assertTrue(_is_instance_def(_last(
            "def setup(self, *a, **k):\n    pass\n")))

    def test_cls_first_rejected(self):
        self.assertFalse(_is_instance_def(_last("def setup(cls):\n    pass\n")))

    def test_no_params_rejected(self):
        self.assertFalse(_is_instance_def(_last("def setup():\n    pass\n")))

    def test_arbitrary_first_param_rejected(self):
        self.assertFalse(_is_instance_def(_last("def setup(foo):\n    pass\n")))

    def test_classmethod_self_rejected(self):
        self.assertFalse(_is_instance_def(_last(
            "@classmethod\ndef setup(self):\n    pass\n")))

    def test_staticmethod_self_rejected(self):
        self.assertFalse(_is_instance_def(_last(
            "@staticmethod\ndef setup(self):\n    pass\n")))

    def test_non_functiondef_rejected(self):
        self.assertFalse(_is_instance_def(_last("x = 1\n")))
