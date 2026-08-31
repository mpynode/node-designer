"""create(name=None) derives the default node name from the Class.

The redesign ties the Python-API default name to the SAME convention as the
compiled C++ node type: both are the camelCase (lower-first) of the PascalCase
Class. So ``ProcrustesConstraint.create()`` names its node ``procrustesConstraint1``
-- matching ``mc.createNode('procrustesConstraint')`` -- instead of the old
hardcoded per-wrapper default (``mPyConstraint#``). For a root wrapper the
derivation reproduces the native type (``MPyNode`` -> ``mPyNode1``), so existing
no-arg behavior is unchanged; only user subclasses (and the previously-wrong
non-mPyNode roots) start following their own name.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestCreateDefaultName(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        sys.modules.pop("mpynode_user", None)

    def _synth(self, name, native="mPyNode"):
        from mpynode._common.io.user_classes import synthesize

        return synthesize(name, native)

    def test_root_mpynode_unchanged(self):
        from mpynode import MPyNode

        n = MPyNode.create()
        self.assertEqual(n.get_name(), "mPyNode1")

    def test_user_subclass_single_word_camelcase(self):
        Widget = self._synth("Widget", "mPyNode")
        n = Widget.create()
        self.assertEqual(n.get_name(), "widget1")

    def test_user_subclass_multiword_pascal_to_camel(self):
        Cls = self._synth("ProcrustesConstraint", "mPyConstraint")
        n = Cls.create()
        self.assertEqual(n.get_name(), "procrustesConstraint1")

    def test_root_constraint_named_after_its_type_not_mpynode(self):
        # Was the bug: MPyConstraint.create() used the hardcoded "mPyConstraint#"
        # default which is correct here, but the base's was "mPyNode#". Assert the
        # node is named after its OWN type, deterministically.
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        n = MPyConstraint.create()
        self.assertEqual(n.get_name(), "mPyConstraint1")

    def test_explicit_name_is_respected(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="banana#")
        self.assertEqual(n.get_name(), "banana1")

    def test_derivation_reaches_shape_wrapper_override(self):
        # A shape-type wrapper (locator) has its OWN create() override; a user
        # subclass of it must still derive its name from the Class, not the
        # wrapper's hardcoded default.
        Cls = self._synth("GlowGizmo", "mPyLocator")
        n = Cls.create()
        self.assertIn("glowGizmo", n.get_name())

    def test_build_also_derives(self):
        Widget = self._synth("Gadget", "mPyNode")
        n = Widget.build()
        self.assertEqual(n.get_name(), "gadget1")

    def test_find_solver_root_unchanged(self):
        # find_solver() creates a solver when none exists. For the root
        # MPyIkSolver the derived name reproduces the old hardcoded literal.
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        n = MPyIkSolver.find_solver()
        self.assertEqual(n.get_name(), "mPyIkSolver1")

    def test_find_solver_subclass_derives_name(self):
        # A user subclass of MPyIkSolver calling find_solver() (no existing
        # solver) must derive its node name from the Class -- camelCase --
        # NOT the hardcoded "mPyIkSolver1" literal.
        Cls = self._synth("MyRigSolver", "mPyIkSolver")
        n = Cls.find_solver()
        self.assertEqual(n.get_name(), "myRigSolver1")


if __name__ == "__main__":
    unittest.main()
