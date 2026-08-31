"""The mPyBlendShape Attribute Editor template.

Only ``weight_rows`` is covered, and that is deliberate: it is the whole of the
logic. The rest of ``ui/ae_blend_shape`` is ``editorTemplate`` / layout calls
that cannot run without a GUI (mayapy has none), so the useful split is to keep
every decision -- which indices get a row, what each row is labelled -- in a
pure-ish function and unit-test THAT.

What the rows have to get right, and why each case is here:

  * EVERY shape is listed, in-betweens and combos included. They are additive,
    settable channels (``morph_blend.resolve_weights`` ADDS the driven amount to
    a target's own channel), so a hidden row is a hidden rig control.
  * Indices stay SPARSE across a removal, exactly as Maya does -- a compacted
    row list would re-point every label onto the wrong plug.
  * An alias whose element was dropped on save still gets a row, or a reopened
    scene would come up looking like it had lost its targets.
"""
from __future__ import annotations

import unittest

from tests import _setup


def setUpModule():
    _setup.standalone_init()
    _setup.ensure_plugins_loaded()


def _rig(node_name, targets):
    """A fresh scene holding one mPyBlendShape with ``targets`` wired in.

    Per-test rather than per-class: several of these tests reset the scene, and
    a class-level fixture would be deleted out from under whichever tests
    unittest happened to order after them.
    """
    import maya.cmds as mc
    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

    mc.file(new=True, force=True)
    base = mc.polySphere(name=node_name + "Base", sx=4, sy=3, ch=False)[0]
    for nm in targets:
        mc.duplicate(base, name=nm)
    bs = MPyBlendShape.create(mesh=base, name=node_name)
    for nm in targets:
        bs.add_target(nm)
    return bs


class TestWeightRows(unittest.TestCase):
    # The four-shape structure the combo_correctives template builds: a main,
    # its in-between, a second main, and their combo.
    COMBO = ("browUp", "browUp50", "mouthOpen", "browUp_mouthOpen")

    def _rows(self, bs):
        from mpynode.ui import ae_blend_shape
        return ae_blend_shape.weight_rows(bs.get_name())

    def test_lists_every_shape_including_inbetweens_and_combos(self):
        bs = _rig("aeComboBS", self.COMBO)
        self.assertEqual(
            self._rows(bs),
            [(0, "browUp"), (1, "browUp50"), (2, "mouthOpen"),
             (3, "browUp_mouthOpen")])

    def test_a_derived_shape_is_not_filtered_out(self):
        # browUp50 and browUp_mouthOpen are the DRIVEN ones. They are additive,
        # so their own channels reach the deform and must be reachable in the AE.
        bs = _rig("aeDerivedBS", self.COMBO)
        labels = [lbl for _, lbl in self._rows(bs)]
        self.assertIn("browUp50", labels)
        self.assertIn("browUp_mouthOpen", labels)

    def test_rename_relabels_without_moving_the_index(self):
        bs = _rig("aeRenameBS", self.COMBO)
        bs.rename_target(2, "jawDrop")
        self.assertIn((2, "jawDrop"), self._rows(bs))

    def test_a_removed_target_leaves_a_HOLE_not_a_shifted_list(self):
        bs = _rig("holeBS", ("aa", "bb", "cc"))
        bs.remove_target(1)
        # cc stays at logical index 2. Compacting it to 1 would put the "cc"
        # label on bb's old plug.
        self.assertEqual(self._rows(bs), [(0, "aa"), (2, "cc")])

    def test_an_unaliased_element_falls_back_to_its_indexed_name(self):
        import maya.cmds as mc

        bs = _rig("bareBS", ("aa",))
        # Materialise an element nobody aliased -- a target mid-authoring.
        mc.setAttr("%s.weight[7]" % bs.get_name(), 0.0)
        self.assertEqual(self._rows(bs), [(0, "aa"), (7, "weight[7]")])

    def test_a_node_with_no_targets_has_no_rows(self):
        bs = _rig("emptyBS", ())
        self.assertEqual(self._rows(bs), [])


class TestRegistration(unittest.TestCase):
    def test_register_stands_down_in_batch(self):
        """mayapy IS batch, so the MEL shims must not be defined here -- and the
        call must return cleanly rather than raise into initializePlugin."""
        from mpynode.ui import ae_blend_shape
        self.assertFalse(ae_blend_shape.register())

    def test_the_mel_shims_actually_parse_and_define_their_procs(self):
        """The shims are the one thing here that never runs in batch, so without
        this they would first execute on a user's GUI launch and a syntax error
        would surface there and nowhere earlier. mayapy has a MEL interpreter
        even headless, so the parse itself is checkable."""
        import maya.mel as mel
        from mpynode.ui import ae_blend_shape

        mel.eval(ae_blend_shape._MEL_SHIMS)
        for proc in ("AEmPyBlendShapeTemplate",
                     "AEmPyBlendShapeWeightsNew",
                     "AEmPyBlendShapeWeightsReplace"):
            self.assertTrue(mel.eval('exists "%s"' % proc),
                            "%s was not defined by the shims" % proc)

    def test_the_template_proc_names_match_what_maya_looks_up(self):
        """Maya resolves an AE layout as ``AE<nodeType>Template``. If this drifts
        from NODE_TYPE the panel silently falls back to the default AE -- which
        is exactly the bug this module exists to fix, returning unnoticed."""
        from mpynode.ui import ae_blend_shape
        self.assertIn("global proc AE%sTemplate(" % ae_blend_shape.NODE_TYPE,
                      ae_blend_shape._MEL_SHIMS)
        for proc in ("AEmPyBlendShapeWeightsNew",
                     "AEmPyBlendShapeWeightsReplace"):
            self.assertIn("global proc %s(" % proc, ae_blend_shape._MEL_SHIMS)


if __name__ == "__main__":
    unittest.main()
