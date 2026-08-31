"""Every shipped template must compile to a UNIQUE C++ node type.

A template's ``node_name`` becomes the registered Maya type name of the node it
compiles to. Two templates sharing one produce two artifacts claiming the same
type: only one can load, which one wins is down to load order, and nothing
reports the loss. The observable symptom is a folder holding two bundles that
both register the same name.

This is the guard. It is deliberately data-driven over the shipped
``templates/`` tree rather than over the generator's declaration lists, because
the ``.mpn`` payloads are the source of truth that actually ships -- a stale or
hand-edited file on disk has to fail here too.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import unittest


def _templates_root():
    from mpynode._common.util.template_gallery import _bundled_templates_root
    return _bundled_templates_root()


def _shipped():
    """[(rel_folder, data_dict)] for every template.mpn in the bundled tree."""
    root = _templates_root()
    if not root or not os.path.isdir(root):
        return []
    out = []
    for p in sorted(glob.glob(os.path.join(root, "**", "template.mpn"),
                              recursive=True)):
        with open(p) as f:
            data = (json.load(f) or {}).get("data") or {}
        out.append((os.path.relpath(os.path.dirname(p), root), data))
    return out


class TestTemplateClassUniqueness(unittest.TestCase):

    def setUp(self):
        self.rows = _shipped()
        if not self.rows:
            self.skipTest("no bundled templates/ tree found")

    def test_the_tree_is_actually_populated(self):
        """Guard the guard: an empty glob would make everything below vacuous."""
        self.assertGreater(len(self.rows), 20,
                           "suspiciously few templates discovered")

    def test_every_template_declares_a_node_name(self):
        missing = [rel for rel, d in self.rows if not d.get("node_name")]
        self.assertEqual(missing, [], "templates with no node_name: %s" % missing)

    def test_every_template_declares_a_native_type(self):
        missing = [rel for rel, d in self.rows if not d.get("native_type")]
        self.assertEqual(missing, [],
                         "templates with no native_type: %s" % missing)

    def test_node_names_are_unique_across_every_template(self):
        by_name = collections.defaultdict(list)
        for rel, d in self.rows:
            by_name[d.get("node_name")].append(rel)
        clashes = {n: dirs for n, dirs in by_name.items() if len(dirs) > 1}
        self.assertEqual(
            clashes, {},
            "these templates compile to the SAME C++ type name, so only one "
            "of each pair can ever load: %s"
            % json.dumps(clashes, indent=2, sort_keys=True))

    def test_node_names_are_valid_maya_type_identifiers(self):
        bad = []
        for rel, d in self.rows:
            n = d.get("node_name") or ""
            if not n or not n[0].isalpha() or not n.replace("_", "").isalnum():
                bad.append((rel, n))
        self.assertEqual(bad, [], "invalid node type names: %s" % bad)

    def test_mirror_templates_override_their_node_name(self):
        """TEMPLATE_MIRRORS ships a primary's payload at a second path. The
        payload is intentionally identical EXCEPT node_name -- that exception is
        the whole reason mirrors don't collide."""
        # build_templates resolves MPYNODE_ROOT at import time.
        os.environ.setdefault(
            "MPYNODE_ROOT", os.path.dirname(_templates_root()))
        try:
            from mpynode._demos.build_templates import (
                TEMPLATE_MIRRORS, _TARGET_BY_TYPE)
        except ImportError as exc:
            self.skipTest("build_templates not importable: %s" % exc)
        by_dir = dict(self.rows)
        for native_type, mirrors in TEMPLATE_MIRRORS.items():
            primary_dir = _TARGET_BY_TYPE[native_type].replace("/", os.sep)
            primary = by_dir.get(primary_dir)
            if primary is None:
                continue
            for rel, declared in mirrors:
                got = by_dir.get(rel.replace("/", os.sep))
                if got is None:
                    continue
                self.assertEqual(
                    got.get("node_name"), declared,
                    "%s should ship node_name %r" % (rel, declared))
                self.assertNotEqual(
                    got.get("node_name"), primary.get("node_name"),
                    "%s collides with its primary" % rel)
                # everything that can drift must still match the primary
                for key in ("expression", "init_source", "native_type"):
                    self.assertEqual(got.get(key), primary.get(key),
                                     "%s drifted from its primary on %s"
                                     % (rel, key))


if __name__ == "__main__":
    unittest.main()
