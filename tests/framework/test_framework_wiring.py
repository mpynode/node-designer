import inspect, unittest
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init(); ensure_plugins_loaded()


class TestFrameworkWiring(unittest.TestCase):
    def _win(self):
        from mpynode.ui import mpynode_designer as md
        return md.NDMainWindow

    def test_build_ui_adds_framework_after_variables(self):
        # Tab order: Scene | Attributes | Variables | Framework (Framework last).
        src = inspect.getsource(self._win()._build_ui)
        self.assertIn("NDFrameworkWidget", src)
        self.assertIn('"Framework"', src)
        self.assertLess(src.index('"Attributes"'), src.index('"Variables"'))
        self.assertLess(src.index('"Variables"'), src.index('"Framework"'))

    def test_setcurrentnode_rebinds_framework(self):
        src = inspect.getsource(self._win().setCurrentNode)
        self.assertIn("_framework_widget.setPyNode", src)


if __name__ == "__main__":
    unittest.main()
