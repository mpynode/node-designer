import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest


class TestContentHash(unittest.TestCase):
    def test_ignores_comments_and_whitespace(self):
        from mpynode._common.io.content_hash import source_hash
        a = source_hash("out = x + 1", ["x"], ["out"])
        b = source_hash("out = x + 1   # a comment\n", ["x"], ["out"])
        self.assertEqual(a, b)

    def test_differs_on_expression_change(self):
        from mpynode._common.io.content_hash import source_hash
        a = source_hash("out = x + 1", ["x"], ["out"])
        b = source_hash("out = x + 2", ["x"], ["out"])
        self.assertNotEqual(a, b)

    def test_differs_on_attr_name_change(self):
        from mpynode._common.io.content_hash import source_hash
        a = source_hash("out = x", ["x"], ["out"])
        b = source_hash("out = x", ["y"], ["out"])
        self.assertNotEqual(a, b)

    def test_ignores_attr_order(self):
        from mpynode._common.io.content_hash import source_hash
        a = source_hash("pass", ["x", "y"], ["out"])
        b = source_hash("pass", ["y", "x"], ["out"])
        self.assertEqual(a, b)

    def test_ignores_values_only_names(self):
        # Same structure, different intent captured only in NAMES not values.
        from mpynode._common.io.content_hash import source_hash
        a = source_hash("out = x", ["x"], ["out"], persistent_names=["k"])
        b = source_hash("out = x", ["x"], ["out"], persistent_names=["k"])
        self.assertEqual(a, b)
        c = source_hash("out = x", ["x"], ["out"], persistent_names=["j"])
        self.assertNotEqual(a, c)
