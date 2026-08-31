"""Ask 1 -- attributes surfaced as "Properties" with plain READ/WRITE/METHOD.

Two surfaces, each a light touch (nothing removed/moved):
  * Variables tab: the "API" section is renamed "Properties"; the Dir column
    shows the slot direction as a plain word -- READ / WRITE / READWRITE /
    METHOD -- rendered directly in the column (an earlier short-letter pill
    badge read poorly, so it was reverted to the obvious words).
  * Attributes tab: the two list headers keep the plug-direction words
    "Input" / "Output" (tinted blue / amber). Rows unchanged. (An earlier
    pass relabeled them "Read" / "Write"; reverted per user preference --
    input/output reads clearer than read/write for attribute plugs.)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest


class TestVariablesPropertiesSection(unittest.TestCase):
    def test_section_renamed_properties(self):
        from mpynode.ui.widgets.variables import SECTION_INTERNAL
        self.assertEqual(SECTION_INTERNAL, "Properties")

    def test_dir_label_full_words(self):
        from mpynode.ui.widgets.variables import _dir_label
        self.assertEqual(_dir_label("read"), "READ")
        self.assertEqual(_dir_label("write"), "WRITE")
        self.assertEqual(_dir_label("readwrite"), "READWRITE")
        self.assertEqual(_dir_label("method"), "METHOD")

    def test_dir_label_neutral_for_directionless(self):
        from mpynode.ui.widgets.variables import _dir_label
        self.assertEqual(_dir_label(""), "")
        self.assertEqual(_dir_label(None), "")

    def test_no_letter_badge_palette(self):
        # The short-letter pill badge scheme was reverted; the palette/token
        # maps must be gone so nothing paints overlapping pills again.
        import mpynode.ui.widgets.variables as v
        self.assertFalse(hasattr(v, "_DIR_BADGE_COLORS"))
        self.assertFalse(hasattr(v, "_DIR_BADGE_TOKEN"))


class TestAttributesHeadersRelabeled(unittest.TestCase):
    def test_input_tree_header_is_input(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        self.assertEqual(NDInputAttrTree.HEADER_LABEL, "Input")
        self.assertTrue(getattr(NDInputAttrTree, "HEADER_COLOR", "").startswith("#"))

    def test_output_tree_header_is_output(self):
        from mpynode.ui.widgets.attributes import NDOutputAttrTree
        self.assertEqual(NDOutputAttrTree.HEADER_LABEL, "Output")
        self.assertTrue(getattr(NDOutputAttrTree, "HEADER_COLOR", "").startswith("#"))

    def test_output_still_reads_output_attr_map(self):
        # relabel is cosmetic only -- the data source is unchanged.
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree, NDOutputAttrTree)
        self.assertEqual(NDInputAttrTree.LIST_ATTR_FUNC_NAME,
                         "get_input_attr_map")
        self.assertEqual(NDOutputAttrTree.LIST_ATTR_FUNC_NAME,
                         "get_output_attr_map")


if __name__ == "__main__":
    unittest.main()
