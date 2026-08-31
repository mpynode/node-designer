import unittest


class TestDialogExports(unittest.TestCase):
    def test_dialog_button_box_and_form_layout_exported(self):
        try:
            from mpynode.ui import qt_wrapper
        except ImportError as exc:
            self.skipTest("Qt unavailable: %s" % exc)
        self.assertTrue(hasattr(qt_wrapper, "QDialogButtonBox"))
        self.assertTrue(hasattr(qt_wrapper, "QFormLayout"))


if __name__ == "__main__":
    unittest.main()
