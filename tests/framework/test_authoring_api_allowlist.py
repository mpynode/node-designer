"""AUTHORING_API is a CURATED promise, so it needs the same guards the blessed
tuple has.

The Framework tab used to derive its Authoring group from ``dir(cls)`` minus the
base class. That could not tell a real authoring verb (``add_target``) from
internal table plumbing (``rebuild_slots``), so it showed all 38 methods across
the 12 wrappers -- including six the wrapper's own docstrings describe as
non-opt-in and automatic.

Curation buys a readable list and costs a drift risk: a rename leaves a dead
name in the tuple and the row silently disappears. These tests are that guard.
"""
from __future__ import annotations

import importlib
import inspect
import unittest

from tests._setup import ensure_plugins_loaded, standalone_init

standalone_init()
ensure_plugins_loaded()

# Every wrapper that declares an authoring surface, plus the ones that declare
# an EMPTY one on purpose.
WRAPPERS = (
    ("mpynode.wrappers.mpy_blend_shape", "MPyBlendShape"),
    ("mpynode.wrappers.mpy_constraint", "MPyConstraint"),
    ("mpynode.wrappers.mpy_deformer", "MPyDeformer"),
    ("mpynode.wrappers.mpy_file", "MPyFile"),
    ("mpynode.wrappers.mpy_iksolver", "MPyIkSolver"),
    ("mpynode.wrappers.mpy_locator", "MPyLocator"),
    ("mpynode.wrappers.mpy_skin_cluster", "MPySkinCluster"),
)


def _classes():
    for mod_name, cls_name in WRAPPERS:
        yield cls_name, getattr(importlib.import_module(mod_name), cls_name)


class TestAllowlistDoesNotDrift(unittest.TestCase):

    def test_every_listed_name_exists_on_the_class(self):
        """A rename must fail HERE, not by silently dropping a UI row."""
        from mpynode.ui.widgets.plug_tree_walker import _authoring_api_entries

        for cls_name, cls in _classes():
            for name, _doc in _authoring_api_entries(cls):
                self.assertTrue(
                    hasattr(cls, name),
                    "%s.AUTHORING_API lists %r, which no longer exists"
                    % (cls_name, name))

    def test_every_listed_name_is_callable(self):
        """A property or constant in the tuple would render with a bogus
        signature; the group is methods only."""
        from mpynode.ui.widgets.plug_tree_walker import _authoring_api_entries

        for cls_name, cls in _classes():
            for name, _doc in _authoring_api_entries(cls):
                raw = inspect.getattr_static(cls, name, None)
                fn = (raw.__func__
                      if isinstance(raw, (staticmethod, classmethod)) else raw)
                self.assertTrue(
                    inspect.isfunction(fn),
                    "%s.%s is in AUTHORING_API but is not a method"
                    % (cls_name, name))

    def test_no_blessed_method_is_also_listed(self):
        """The two surfaces are disjoint by construction; a name in both would
        render twice and imply it works in an expression."""
        from mpynode.ui.widgets.plug_tree_walker import _authoring_api_entries

        for cls_name, cls in _classes():
            blessed = {getattr(m, "name", None)
                       for m in getattr(cls, "INTERNAL_API_METHODS", ()) or ()}
            listed = {n for n, _d in _authoring_api_entries(cls)}
            self.assertFalse(
                blessed & listed,
                "%s lists blessed method(s) as authoring: %s"
                % (cls_name, sorted(blessed & listed)))

    def test_plumbing_stays_out(self):
        """The specific names curation exists to exclude. If one reappears,
        someone widened the list without reading why it was narrow."""
        excluded = {
            "MPyBlendShape": ("ensure_slot_attrs", "ensure_delta_attrs",
                              "ensure_corrective_attrs", "rebuild_slots",
                              "rebuild_correctives", "compute_slot_names"),
            "MPyConstraint": ("list_preset_inputs",),
        }
        from mpynode.ui.widgets.plug_tree_walker import _authoring_api_entries

        for cls_name, cls in _classes():
            listed = {n for n, _d in _authoring_api_entries(cls)}
            for name in excluded.get(cls_name, ()):
                self.assertNotIn(
                    name, listed,
                    "%s.%s is internal plumbing the node manages itself"
                    % (cls_name, name))


class TestEveryRowIsDocumented(unittest.TestCase):
    """An undocumented row renders as a bare name with an empty tooltip -- the
    thing that made mPyFile's group unreadable in the first place."""

    def test_every_row_has_a_doc(self):
        import maya.cmds as mc
        from mpynode.ui.widgets.plug_tree_walker import (
            authoring_method_rows_for,
        )

        mc.file(new=True, force=True)
        for cls_name, cls in _classes():
            try:
                node = cls.create(name="doc" + cls_name + "#")
            except Exception as exc:            # pragma: no cover
                self.skipTest("%s not creatable: %s" % (cls_name, exc))
            for name, sig, doc in authoring_method_rows_for(node.get_name()):
                self.assertTrue(
                    (doc or "").strip(),
                    "%s.%s has no docstring and no AUTHORING_API doc -- it "
                    "would render with an empty tooltip" % (cls_name, name))


class TestFileSurfaceIsComplete(unittest.TestCase):
    """mPyFile is the wrapper this work started from: all 13 of its authoring
    methods are legitimate scripting API, so curation must not thin them."""

    def test_all_thirteen_survive(self):
        import maya.cmds as mc
        from mpynode.ui.widgets.plug_tree_walker import (
            authoring_method_rows_for,
        )
        from mpynode.wrappers.mpy_file import MPyFile

        mc.file(new=True, force=True)
        node = MPyFile.create(name="fileAuth#")
        names = {n for n, _s, _d in authoring_method_rows_for(node.get_name())}
        expected = {
            "get_file_name", "set_file_name", "reseed_defaults",
            "convert_compute_to_osl", "convert_compute_to_osl_ai",
            "get_osl_expression", "set_osl_expression", "has_osl_expression",
            "clear_osl_expression", "get_viewport_expression",
            "set_viewport_expression", "has_viewport_expression",
            "clear_viewport_expression",
        }
        self.assertEqual(names, expected)


class TestUndeclaredWrapperShowsNothing(unittest.TestCase):
    """No AUTHORING_API means no declared surface -- [] rather than a fallback
    to the old dir()-derived list, which is what curation replaces."""

    def test_absent_tuple_yields_no_rows(self):
        import maya.cmds as mc
        from mpynode.ui.widgets.plug_tree_walker import (
            authoring_method_rows_for,
        )
        from mpynode.wrappers.mpy_mesh import MPyMesh

        mc.file(new=True, force=True)
        node = MPyMesh.create(name="meshAuth#")
        self.assertFalse(hasattr(MPyMesh, "AUTHORING_API"))
        self.assertEqual(authoring_method_rows_for(node.get_name()), [])


if __name__ == "__main__":
    unittest.main()
