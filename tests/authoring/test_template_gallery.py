"""Pure (no Maya, no Qt) tests for _common/template_gallery.py.

Discovery module for the "New from Template" gallery (design §1):
scans configurable roots into an immutable category/entry tree from
filesystem convention, reading each template's native_type from the RAW
JSON envelope (mpn_io.load_mpn_header) -- never decoding pickled stored_vars.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest


class TestDisplayLabel(unittest.TestCase):
    """The gallery shows folder names VERBATIM -- no naming convention is
    enforced (case, spaces, underscores, camelCase all pass through unchanged)."""

    def test_verbatim_snake_case(self):
        from mpynode._common.util import template_gallery as tg
        self.assertEqual(tg.display_label("awesome_gizmo"), "awesome_gizmo")

    def test_verbatim_single_word(self):
        from mpynode._common.util import template_gallery as tg
        self.assertEqual(tg.display_label("deformers"), "deformers")

    def test_verbatim_mixed_case_node_type(self):
        from mpynode._common.util import template_gallery as tg
        self.assertEqual(tg.display_label("MPyDeformer"), "MPyDeformer")

    def test_verbatim_hyphens_kept(self):
        from mpynode._common.util import template_gallery as tg
        self.assertEqual(tg.display_label("two-bone-ik"), "two-bone-ik")

    def test_verbatim_spaces_kept(self):
        from mpynode._common.util import template_gallery as tg
        self.assertEqual(tg.display_label("My Cool Node"), "My Cool Node")

    def test_verbatim_camel_case_kept(self):
        from mpynode._common.util import template_gallery as tg
        self.assertEqual(tg.display_label("sineRipple"), "sineRipple")

    def test_empty(self):
        from mpynode._common.util import template_gallery as tg
        self.assertEqual(tg.display_label(""), "")


class TestFindAssets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtg_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _touch(self, name):
        p = os.path.join(self.tmp, name)
        with open(p, "w") as f:
            f.write("x")
        return p

    def test_preview_none(self):
        from mpynode._common.util import template_gallery as tg
        self.assertIsNone(tg.find_preview(self.tmp))

    def test_preview_prefers_mp4(self):
        from mpynode._common.util import template_gallery as tg
        self._touch("preview.gif")
        self._touch("preview.png")
        self._touch("preview.jpg")
        mp4 = self._touch("preview.mp4")
        self.assertEqual(tg.find_preview(self.tmp), mp4)

    def test_preview_prefers_gif(self):
        from mpynode._common.util import template_gallery as tg
        self._touch("preview.png")
        self._touch("preview.jpg")
        gif = self._touch("preview.gif")
        self.assertEqual(tg.find_preview(self.tmp), gif)

    def test_preview_png_over_jpg(self):
        from mpynode._common.util import template_gallery as tg
        self._touch("preview.jpg")
        png = self._touch("preview.png")
        self.assertEqual(tg.find_preview(self.tmp), png)

    def test_preview_jpg_last(self):
        from mpynode._common.util import template_gallery as tg
        jpg = self._touch("preview.jpg")
        self.assertEqual(tg.find_preview(self.tmp), jpg)

    def test_description_found(self):
        from mpynode._common.util import template_gallery as tg
        md = self._touch("description.md")
        self.assertEqual(tg.find_description(self.tmp), md)

    def test_description_none(self):
        from mpynode._common.util import template_gallery as tg
        self.assertIsNone(tg.find_description(self.tmp))


def _write_mpn(folder, native_type="mPyDeformer", stored_vars=None):
    """Author a real template.mpn envelope in ``folder`` (creates it)."""
    from mpynode._common.io import mpn_io
    os.makedirs(folder, exist_ok=True)
    payload = {
        "native_type": native_type,
        "node_name": "demo",
        "expression": "self.out = self.inp",
        "input_attrs": {},
        "output_attrs": {},
        "stored_vars": stored_vars or {},
    }
    mpn_io.save_mpn(payload, os.path.join(folder, "template.mpn"))


class TestScanRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtg_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_single_leaf(self):
        from mpynode._common.util import template_gallery as tg
        leaf = os.path.join(self.tmp, "sine_ripple")
        _write_mpn(leaf, native_type="mPyDeformer")
        cat = tg.scan_root(self.tmp)
        self.assertIsInstance(cat, tg.TemplateCategory)
        self.assertEqual(len(cat.children), 1)
        entry = cat.children[0]
        self.assertIsInstance(entry, tg.TemplateEntry)
        self.assertEqual(entry.label, "sine_ripple")
        self.assertEqual(entry.folder, leaf)
        self.assertEqual(entry.mpn_path, os.path.join(leaf, "template.mpn"))
        self.assertEqual(entry.native_type, "mPyDeformer")
        self.assertIsNone(entry.preview_path)
        self.assertIsNone(entry.description_path)

    def test_nested_categories(self):
        from mpynode._common.util import template_gallery as tg
        leaf = os.path.join(self.tmp, "basics", "MPyDeformer", "sine_ripple")
        _write_mpn(leaf)
        cat = tg.scan_root(self.tmp)
        # root -> basics -> deformers -> sine_ripple(entry)
        basics = cat.children[0]
        self.assertIsInstance(basics, tg.TemplateCategory)
        self.assertEqual(basics.label, "basics")
        deformers = basics.children[0]
        self.assertEqual(deformers.label, "MPyDeformer")
        entry = deformers.children[0]
        self.assertIsInstance(entry, tg.TemplateEntry)
        self.assertEqual(entry.label, "sine_ripple")

    def test_preview_and_description_resolved(self):
        from mpynode._common.util import template_gallery as tg
        leaf = os.path.join(self.tmp, "file_brightness_contrast")
        _write_mpn(leaf, native_type="mPyFile")
        with open(os.path.join(leaf, "preview.png"), "w") as f:
            f.write("x")
        with open(os.path.join(leaf, "description.md"), "w") as f:
            f.write("# hi")
        entry = tg.scan_root(self.tmp).children[0]
        self.assertEqual(entry.preview_path, os.path.join(leaf, "preview.png"))
        self.assertEqual(entry.description_path,
                         os.path.join(leaf, "description.md"))

    def test_root_label_is_prettified_basename(self):
        from mpynode._common.util import template_gallery as tg
        cat = tg.scan_root(self.tmp)
        self.assertEqual(cat.abs_path, os.path.abspath(self.tmp))

    def test_category_carries_preview_and_description(self):
        from mpynode._common.util import template_gallery as tg
        # A category folder (no template.mpn) with its own landing-page assets.
        cat_dir = os.path.join(self.tmp, "textures")
        _write_mpn(os.path.join(cat_dir, "file"), native_type="mPyFile")
        with open(os.path.join(cat_dir, "preview.png"), "w") as f:
            f.write("x")
        with open(os.path.join(cat_dir, "description.md"), "w") as f:
            f.write("# textures")
        textures = tg.scan_root(self.tmp).children[0]
        self.assertIsInstance(textures, tg.TemplateCategory)
        self.assertEqual(textures.preview_path,
                         os.path.join(cat_dir, "preview.png"))
        self.assertEqual(textures.description_path,
                         os.path.join(cat_dir, "description.md"))


class TestBadTemplate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtg_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_corrupt_mpn_native_type_none(self):
        from mpynode._common.util import template_gallery as tg
        leaf = os.path.join(self.tmp, "broken")
        os.makedirs(leaf)
        with open(os.path.join(leaf, "template.mpn"), "w") as f:
            f.write("this is not json {{{")
        cat = tg.scan_root(self.tmp)
        self.assertEqual(len(cat.children), 1)        # NOT dropped
        entry = cat.children[0]
        self.assertIsInstance(entry, tg.TemplateEntry)
        self.assertEqual(entry.label, "broken")
        self.assertIsNone(entry.native_type)          # graceful

    def test_wrong_version_native_type_none(self):
        from mpynode._common.util import template_gallery as tg
        import json
        leaf = os.path.join(self.tmp, "oldver")
        os.makedirs(leaf)
        with open(os.path.join(leaf, "template.mpn"), "w") as f:
            json.dump({"version": 1, "data": {"native_type": "mPyNode"}}, f)
        entry = tg.scan_root(self.tmp).children[0]
        self.assertIsNone(entry.native_type)


class TestBothTemplateAndSubfolders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtg_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_template_with_subfolders_is_buildable_and_container(self):
        from mpynode._common.util import template_gallery as tg
        combo = os.path.join(self.tmp, "combo")
        _write_mpn(combo, native_type="mPyNode")
        # A subfolder that ALSO contains a template.mpn -- a nested variant.
        nested = os.path.join(combo, "advanced")
        _write_mpn(nested, native_type="mPyDeformer")
        cat = tg.scan_root(self.tmp)
        self.assertEqual(len(cat.children), 1)
        entry = cat.children[0]
        self.assertIsInstance(entry, tg.TemplateEntry)   # buildable
        self.assertEqual(entry.label, "combo")
        self.assertEqual(entry.native_type, "mPyNode")
        # ...and it ALSO surfaces its nested variant as a child.
        self.assertEqual(len(entry.children), 1)
        child = entry.children[0]
        self.assertIsInstance(child, tg.TemplateEntry)
        self.assertEqual(child.label, "advanced")
        self.assertEqual(child.native_type, "mPyDeformer")


class TestScanSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtgsec_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.marker = os.path.join(self.tmp, "PWNED.marker")

    def test_scan_never_unpickles(self):
        from mpynode._common.util import template_gallery as tg
        from mpynode._common.io import mpn_io, serialization

        # A class whose __reduce__ writes the marker on unpickle. value_codec
        # cannot encode a custom instance -> encode_stored_vars uses pickle.
        marker = self.marker

        class _Evil:
            def __reduce__(self):
                # Target a stdlib builtin so the pickle reference is
                # identity-stable even if this module is imported twice under
                # the harness (a module-level function would be flaky).
                return (open, (marker, "w"))

        leaf = os.path.join(self.tmp, "tpl", "evil")
        os.makedirs(leaf)
        payload = {
            "native_type": "mPyNode",
            "node_name": "evil",
            "expression": "",
            "input_attrs": {},
            "output_attrs": {},
            "stored_vars": {"x": _Evil()},
        }
        mpn_io.save_mpn(payload, os.path.join(leaf, "template.mpn"))

        # Sanity: the authored blob really does carry a pickle (so this test
        # would actually catch a decode if one happened).
        import json
        with open(os.path.join(leaf, "template.mpn")) as f:
            sv = json.load(f)["data"]["stored_vars"]
        self.assertTrue(serialization.blob_has_pickle(sv),
                        "fixture must carry a pickle to be a valid security test")
        self.assertFalse(os.path.exists(marker), "authoring must not unpickle")

        # The actual scan -- reads native_type from raw JSON, no decode.
        cat = tg.scan_root(os.path.join(self.tmp, "tpl"))
        entry = cat.children[0]
        self.assertEqual(entry.native_type, "mPyNode")
        self.assertFalse(
            os.path.exists(marker),
            "SECURITY: scanning a template.mpn must NOT unpickle stored_vars",
        )


class TestSearchRootsAndScanAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtg_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_roots_drop_nonexistent_and_expand(self):
        from mpynode._common.util import template_gallery as tg
        good = os.path.join(self.tmp, "good")
        os.makedirs(good)
        missing = os.path.join(self.tmp, "nope_missing")
        os.environ["NDTG_TEST_VAR"] = good
        try:
            import mpynode.ui.preferences as prefs
            orig = prefs.template_search_paths
            prefs.template_search_paths = lambda: ["$NDTG_TEST_VAR", missing]
            try:
                roots = tg.template_search_roots()
            finally:
                prefs.template_search_paths = orig
        finally:
            del os.environ["NDTG_TEST_VAR"]
        self.assertIn(os.path.abspath(good), roots)
        self.assertNotIn(os.path.abspath(missing), roots)

    def test_roots_default_when_pref_empty(self):
        from mpynode._common.util import template_gallery as tg
        import mpynode.ui.preferences as prefs
        orig = prefs.template_search_paths
        prefs.template_search_paths = lambda: []
        try:
            roots = tg.template_search_roots()
        finally:
            prefs.template_search_paths = orig
        bundled = tg._bundled_templates_root()
        if bundled:
            self.assertIn(os.path.abspath(bundled), roots)

    def test_scan_all_one_branch_per_root(self):
        from mpynode._common.util import template_gallery as tg
        r1 = os.path.join(self.tmp, "rootA")
        r2 = os.path.join(self.tmp, "rootB")
        _write_mpn(os.path.join(r1, "tpl_a"))
        _write_mpn(os.path.join(r2, "tpl_b"))
        import mpynode.ui.preferences as prefs
        orig = prefs.template_search_paths
        prefs.template_search_paths = lambda: [r1, r2]
        try:
            results = tg.scan_all()
        finally:
            prefs.template_search_paths = orig
        labels = [r[0] for r in results]
        self.assertIn("rootA", labels)
        self.assertIn("rootB", labels)
        for root_label, root_path, tree in results:
            self.assertIsInstance(tree, tg.TemplateCategory)
            self.assertTrue(os.path.isabs(root_path))
            self.assertEqual(len(tree.children), 1)


# ======================================================================
# Phase G: template migration into <category>/<name>/template.mpn folders
# ======================================================================
import importlib.util

_BUILD = os.path.join(
    os.environ["MPYNODE_ROOT"],
    "scripts", "mpynode", "_demos", "build_templates.py")


def _load_build_module():
    # Import build_templates.py WITHOUT running main() (it is guarded by
    # __name__ == "__main__"). It imports maya.standalone at module scope, so
    # this loader test must run under mayapy.
    spec = importlib.util.spec_from_file_location("_bt_mod", _BUILD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TemplateBuildLayoutTest(unittest.TestCase):
    def test_template_targets_use_category_name_template_mpn(self):
        mod = _load_build_module()
        # build_templates exposes a TEMPLATES list of (native_type, rel_dir)
        # describing the on-disk layout; each rel_dir is <category>/<name>.
        targets = dict(mod.TEMPLATE_TARGETS)
        self.assertEqual(targets["mPyDeformer"], "MPyDeformer/Sine Ripple")
        self.assertEqual(targets["mPyFile"], "MPyFile/File Simple")
        self.assertEqual(targets["mPyIkSolver"], "MPyIkSolver/Two Bone IK")
        # The write helper composes <root>/<rel_dir>/template.mpn.
        self.assertTrue(
            mod._template_path("mPyDeformer").endswith(
                os.path.join("MPyDeformer", "Sine Ripple", "template.mpn")))

    def test_write_template_creates_folder_template_and_description(self):
        import tempfile, shutil
        mod = _load_build_module()
        tmp = tempfile.mkdtemp(prefix="bt_write_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        # _write_template(payload, native_type, description, root=) writes
        # <root>/<rel>/template.mpn AND <root>/<rel>/description.md.
        mod._write_template({"native_type": "mPyDeformer"},
                            "mPyDeformer", "Sine ripple demo.", root=tmp)
        mpn = os.path.join(tmp, "MPyDeformer", "Sine Ripple",
                           "template.mpn")
        desc = os.path.join(tmp, "MPyDeformer", "Sine Ripple",
                            "description.md")
        self.assertTrue(os.path.isfile(mpn))
        self.assertTrue(os.path.isfile(desc))
        with open(desc) as f:
            self.assertIn("Sine ripple demo.", f.read())

    def test_write_template_also_writes_mirror(self):
        # P0-4/P0-5: a primary template with a mirror must author BOTH copies
        # from the one payload, so they can never drift.
        #
        # DATA-DRIVEN off TEMPLATE_MIRRORS rather than naming a type. It used
        # to hardcode mPyDeformer -> MPyDeformer, and broke the day that mirror
        # was retired even though the MECHANISM was untouched. Skips loudly
        # when the table empties, so retiring the last mirror reads as "no
        # longer applicable" instead of passing vacuously.
        import tempfile, shutil
        mod = _load_build_module()
        if not mod.TEMPLATE_MIRRORS:
            self.skipTest("no mirrors declared; the mechanism is unused")
        native_type = sorted(mod.TEMPLATE_MIRRORS)[0]
        mirrors = mod.TEMPLATE_MIRRORS[native_type]
        primary_rel = mod._TARGET_BY_TYPE[native_type]

        tmp = tempfile.mkdtemp(prefix="bt_mirror_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        mod._write_template({"native_type": native_type},
                            native_type, "Mirror demo.", root=tmp)

        primary = os.path.join(tmp, *(primary_rel.split("/") + ["template.mpn"]))
        self.assertTrue(os.path.isfile(primary),
                        "primary not authored for %s" % native_type)
        for rel, node_name in mirrors:
            folder = os.path.join(tmp, *rel.split("/"))
            self.assertTrue(
                os.path.isfile(os.path.join(folder, "template.mpn")),
                "mirror %s not authored by _write_template" % rel)
            self.assertTrue(
                os.path.isfile(os.path.join(folder, "description.md")),
                "mirror %s got no description.md" % rel)


def _bundled_root():
    return os.path.join(os.environ["MPYNODE_ROOT"], "templates")


def _flatten(node, out):
    # Collect every TemplateEntry, recursing through categories AND hybrid
    # entries (a buildable folder can carry nested variant templates).
    for child in getattr(node, "children", ()):
        if hasattr(child, "mpn_path"):        # TemplateEntry (maybe a hybrid)
            out.append(child)
        _flatten(child, out)
    return out


class MigratedBundledTemplatesTest(unittest.TestCase):
    def test_scan_all_finds_three_migrated_templates(self):
        from mpynode._common.util import template_gallery
        roots = template_gallery.scan_all()
        # Pick the bundled root (its path is <MPYNODE_ROOT>/templates).
        bundled = [c for (_label, path, c) in roots
                   if os.path.abspath(path) == os.path.abspath(_bundled_root())]
        self.assertEqual(len(bundled), 1, "bundled templates root not scanned")
        entries = _flatten(bundled[0], [])
        # Key by label: native_type now collides (a hybrid base and its nested
        # variants share a type), so look the three core templates up by their
        # label -- which is the folder name VERBATIM.
        by_label = {e.label: e for e in entries}
        self.assertIn("Sine Ripple", by_label)
        self.assertIn("File Simple", by_label)
        self.assertIn("Two Bone IK", by_label)
        self.assertEqual(by_label["Sine Ripple"].native_type, "mPyDeformer")
        self.assertEqual(by_label["File Simple"].native_type, "mPyFile")
        self.assertEqual(by_label["Two Bone IK"].native_type, "mPyIkSolver")
        # description.md authored beside each template.mpn.
        for label in ("Sine Ripple", "File Simple", "Two Bone IK"):
            e = by_label[label]
            self.assertTrue(e.mpn_path.endswith("template.mpn"))
            self.assertIsNotNone(e.description_path)
            self.assertTrue(os.path.isfile(e.description_path))

    def test_bundled_scan_matches_builder_declared_targets(self):
        # P0-4/P0-5: build_templates.py is the single authority for every
        # bundled template.mpn, so pin the scanned tree to its declared set --
        # a hand-placed or deleted template.mpn must not drift from it.
        from mpynode._common.util import template_gallery
        mod = _load_build_module()
        # build_templates declares its complete bundled set (primaries + mirrors
        # + the mpynode example templates + the collision deformer) in
        # ALL_DECLARED_DIRS; pin the scanned tree to it.
        declared = set(mod.ALL_DECLARED_DIRS)
        roots = template_gallery.scan_all()
        bundled = [c for (_l, path, c) in roots
                   if os.path.abspath(path) == os.path.abspath(_bundled_root())]
        self.assertEqual(len(bundled), 1, "bundled templates root not scanned")
        scanned = set()
        for e in _flatten(bundled[0], []):
            rel = os.path.relpath(os.path.dirname(e.mpn_path), _bundled_root())
            scanned.add(rel.replace(os.sep, "/"))
        self.assertEqual(
            scanned, declared,
            "bundled template.mpn set drifted from build_templates targets")


class BundledMpynodeExamplesTest(unittest.TestCase):
    """The bundled mpynode example templates under MPyNode/<name>/ and the
    unitSphereCollision deformer are bundled, correctly typed, and vanilla (no
    baked / pickled stored vars)."""

    _EXAMPLES = (
        "Bubble Sort", "Hex Attribute", "Ouch", "Spine",
        "De Boor Spline", "Spring Chain",
    )

    def _by_label(self):
        from mpynode._common.util import template_gallery
        roots = template_gallery.scan_all()
        bundled = [c for (_l, path, c) in roots
                   if os.path.abspath(path) == os.path.abspath(_bundled_root())]
        self.assertEqual(len(bundled), 1, "bundled templates root not scanned")
        return {e.label: e for e in _flatten(bundled[0], [])}

    def test_six_mpynode_examples_present_and_typed(self):
        from mpynode._common.util import template_gallery as tg
        by_label = self._by_label()
        for snake in self._EXAMPLES:
            label = tg.display_label(snake)
            self.assertIn(label, by_label, "missing template: %s" % snake)
            e = by_label[label]
            self.assertEqual(e.native_type, "mPyNode")
            self.assertTrue(e.mpn_path.endswith("template.mpn"))
            rel = os.path.relpath(os.path.dirname(e.mpn_path), _bundled_root())
            self.assertEqual(rel.replace(os.sep, "/"),
                             "MPyNode/" + snake)
            self.assertIsNotNone(e.description_path)
            self.assertTrue(os.path.isfile(e.description_path))

    def test_examples_are_vanilla_no_pickle(self):
        from mpynode._common.io import mpn_io, serialization
        from mpynode._common.util import template_gallery as tg
        by_label = self._by_label()
        for snake in self._EXAMPLES:
            e = by_label[tg.display_label(snake)]
            raw = mpn_io.load_mpn_header(e.mpn_path)     # no decode
            sv = raw.get("stored_vars")
            if isinstance(sv, str):                      # encoded blob on disk
                self.assertFalse(
                    serialization.blob_has_pickle(sv),
                    "%s ships a pickle in stored_vars" % snake)
            self.assertNotIn("persistent_vars", raw)
            # ...and it decodes to an empty dict (a vanilla template).
            decoded = mpn_io.load_mpn(e.mpn_path, trusted=True)
            self.assertEqual(decoded.get("stored_vars") or {}, {})

    def test_unit_sphere_collision_deformer(self):
        from mpynode._common.io import mpn_io
        by_label = self._by_label()
        self.assertIn("Unit Sphere Collision", by_label)
        e = by_label["Unit Sphere Collision"]
        self.assertEqual(e.native_type, "mPyDeformer")
        rel = os.path.relpath(os.path.dirname(e.mpn_path), _bundled_root())
        self.assertEqual(rel.replace(os.sep, "/"),
                         "MPyDeformer/Unit Sphere Collision")
        raw = mpn_io.load_mpn_header(e.mpn_path)
        inputs = raw.get("input_attrs") or {}
        self.assertIn("pusher", inputs)
        self.assertEqual(inputs["pusher"]["attr_type"], "matrix")
        self.assertEqual(raw.get("output_attrs") or {}, {})   # deformer: no outs

    def test_every_bundled_template_carries_a_hook(self):
        # Each promoted showcase authors the hook matching its role: the 6
        # mPyNode examples fabricate their own scene, so they author a
        # self-first ``def demo``; the unitSphereCollision deformer wires into
        # the live selection, so it keeps a ``def setup``.
        from mpynode._common.io import mpn_io
        from mpynode._common.util import template_gallery as tg
        from mpynode._common import node_setups
        by_label = self._by_label()
        for snake in self._EXAMPLES:
            label = tg.display_label(snake)
            self.assertIn(label, by_label, "missing template: %s" % label)
            raw = mpn_io.load_mpn_header(by_label[label].mpn_path)   # no decode
            src = raw.get("methods_source") or ""
            self.assertIsNotNone(
                node_setups.find_demo(src),
                "%s has no def demo in methods_source" % label)
        # The collision deformer is the selection-driven exception: def setup.
        self.assertIn("Unit Sphere Collision", by_label)
        usc = mpn_io.load_mpn_header(
            by_label["Unit Sphere Collision"].mpn_path)
        usc_src = usc.get("methods_source") or ""
        self.assertIsNotNone(
            node_setups.find_setup(usc_src),
            "Unit Sphere Collision has no def setup in methods_source")


class BundledMeshGameOfLifeTest(unittest.TestCase):
    """Conway's Game of Life ships as an mPyMesh template under
    MPyMesh/Game Of Life: one cube per live cell into a single mesh, a
    self-contained ``def demo``, and vanilla (no baked / pickled stored vars).
    Replaces the retired MPyNode/game_of_life transform-grid variant."""

    _REL = "MPyMesh/Game Of Life"

    def _entry(self):
        from mpynode._common.util import template_gallery
        roots = template_gallery.scan_all()
        bundled = [c for (_l, path, c) in roots
                   if os.path.abspath(path) == os.path.abspath(_bundled_root())]
        self.assertEqual(len(bundled), 1, "bundled templates root not scanned")
        for e in _flatten(bundled[0], []):
            rel = os.path.relpath(os.path.dirname(e.mpn_path), _bundled_root())
            if rel.replace(os.sep, "/") == self._REL:
                return e
        self.fail("missing template: %s" % self._REL)

    def test_present_typed_mpymesh_with_description(self):
        e = self._entry()
        self.assertEqual(e.native_type, "mPyMesh")
        self.assertTrue(e.mpn_path.endswith("template.mpn"))
        self.assertIsNotNone(e.description_path)
        self.assertTrue(os.path.isfile(e.description_path))

    def test_inputs_are_the_grid_controls(self):
        from mpynode._common.io import mpn_io
        raw = mpn_io.load_mpn_header(self._entry().mpn_path)   # no decode
        inputs = raw.get("input_attrs") or {}
        self.assertEqual(inputs.get("boardX", {}).get("attr_type"), "int")
        self.assertEqual(inputs.get("boardY", {}).get("attr_type"), "int")
        self.assertEqual(inputs.get("frame", {}).get("attr_type"), "time")
        self.assertEqual(
            inputs.get("randomSamples", {}).get("attr_type"), "int")
        self.assertEqual(inputs.get("resetBoard", {}).get("attr_type"), "enum")
        self.assertEqual(inputs.get("cellSize", {}).get("attr_type"), "double")

    def test_carries_a_demo_hook(self):
        from mpynode._common.io import mpn_io
        from mpynode._common import node_setups
        raw = mpn_io.load_mpn_header(self._entry().mpn_path)
        src = raw.get("methods_source") or ""
        self.assertIsNotNone(
            node_setups.find_demo(src),
            "mesh Game of Life has no def demo in methods_source")

    def test_is_vanilla_no_pickle(self):
        from mpynode._common.io import mpn_io, serialization
        e = self._entry()
        raw = mpn_io.load_mpn_header(e.mpn_path)
        sv = raw.get("stored_vars")
        if isinstance(sv, str):
            self.assertFalse(
                serialization.blob_has_pickle(sv),
                "mesh Game of Life ships a pickle in stored_vars")
        self.assertNotIn("persistent_vars", raw)
        decoded = mpn_io.load_mpn(e.mpn_path, trusted=True)
        self.assertEqual(decoded.get("stored_vars") or {}, {})


class BundledMeshMetaballsTest(unittest.TestCase):
    """Metaballs ships as an mPyMesh template under MPyMesh/Metaballs: an
    SDF dual-marching-cubes node folding a primitive stream with CSG (hard union
    / smooth union / difference), a self-contained ``def demo`` that builds the
    "MPyNode" text plus a Cube/Sphere/Cylinder blob, and vanilla stored data."""

    _REL = "MPyMesh/Metaballs"

    def _entry(self):
        from mpynode._common.util import template_gallery
        roots = template_gallery.scan_all()
        bundled = [c for (_l, path, c) in roots
                   if os.path.abspath(path) == os.path.abspath(_bundled_root())]
        self.assertEqual(len(bundled), 1, "bundled templates root not scanned")
        for e in _flatten(bundled[0], []):
            rel = os.path.relpath(os.path.dirname(e.mpn_path), _bundled_root())
            if rel.replace(os.sep, "/") == self._REL:
                return e
        self.fail("missing template: %s" % self._REL)

    def test_present_typed_mpymesh_with_description(self):
        e = self._entry()
        self.assertEqual(e.native_type, "mPyMesh")
        self.assertTrue(e.mpn_path.endswith("template.mpn"))
        self.assertIsNotNone(e.description_path)
        self.assertTrue(os.path.isfile(e.description_path))

    def test_inputs_are_the_sdf_primitive_stream(self):
        from mpynode._common.io import mpn_io
        raw = mpn_io.load_mpn_header(self._entry().mpn_path)   # no decode
        inputs = raw.get("input_attrs") or {}
        # Per-shape parallel arrays (index == CSG fold order) + two scalars.
        expected_arrays = {
            "shapeMatrix": "matrix", "shapeType": "int", "additive": "bool",
            "smoothing": "double", "radius": "double", "height": "double",
            "axis": "int", "halfExtents": "vector",
        }
        for name, atype in expected_arrays.items():
            self.assertEqual(inputs.get(name, {}).get("attr_type"), atype,
                             "%s should be a %s" % (name, atype))
            self.assertTrue(inputs.get(name, {}).get("is_array"),
                            "%s should be a multi/array attr" % name)
        self.assertEqual(inputs.get("resolution", {}).get("attr_type"), "int")
        self.assertFalse(inputs.get("resolution", {}).get("is_array"))
        self.assertEqual(inputs.get("isoValue", {}).get("attr_type"), "double")

    def test_carries_a_demo_and_authoring_commands(self):
        from mpynode._common.io import mpn_io
        from mpynode._common import node_setups
        raw = mpn_io.load_mpn_header(self._entry().mpn_path)
        src = raw.get("methods_source") or ""
        self.assertIsNotNone(
            node_setups.find_demo(src),
            "Metaballs has no def demo in methods_source")
        # The @maya_command authoring helpers travel with the node.
        for cmd in ("addSphere", "addBox", "addCylinder"):
            self.assertIn("def %s" % cmd, src,
                          "Metaballs methods_source missing %s" % cmd)
        # The demo builds the text via the SHIPPED glyph module (not the
        # build-time _demos package, which is not on the runtime path).
        self.assertIn(
            "from mpynode._common.nodes.mesh.sdf_text import word_strokes", src,
            "demo must import the shipped glyph font, not _demos")

    def test_is_vanilla_no_pickle(self):
        from mpynode._common.io import mpn_io, serialization
        e = self._entry()
        raw = mpn_io.load_mpn_header(e.mpn_path)
        sv = raw.get("stored_vars")
        if isinstance(sv, str):
            self.assertFalse(
                serialization.blob_has_pickle(sv),
                "Metaballs ships a pickle in stored_vars")
        self.assertNotIn("persistent_vars", raw)
        decoded = mpn_io.load_mpn(e.mpn_path, trusted=True)
        self.assertEqual(decoded.get("stored_vars") or {}, {})


_SRC = os.path.join(os.environ["MPYNODE_ROOT"], "scripts", "mpynode")


class TemplateLocatorRetiredTest(unittest.TestCase):
    def test_no_production_code_imports_template_locator(self):
        hits = []
        for dp, _dn, fns in os.walk(_SRC):
            if os.sep + "_tests" in dp:        # tests are migrated separately
                continue
            for fn in fns:
                if not fn.endswith(".py") or fn == "template_locator.py":
                    continue
                p = os.path.join(dp, fn)
                # UTF-8 sources; Windows text mode defaults to cp1252 and dies
                # on the first byte outside it (0x9d, measured 2026-08-14).
                with open(p, encoding="utf-8") as f:
                    if "template_locator" in f.read():
                        hits.append(os.path.relpath(p, _SRC))
        self.assertEqual(
            hits, [],
            "template_locator still referenced by production code: %s" % hits)

    def test_template_locator_module_is_deleted(self):
        with self.assertRaises(ImportError):
            __import__("mpynode._common.template_locator")


class TestIgnoresFoldersWithoutMpn(unittest.TestCase):
    """The gallery must ignore any folder that contains no template.mpn anywhere
    in its subtree -- e.g. Maya's ``.mayaSwatches`` cache folders, or empty
    category folders -- so they never appear as (empty) gallery categories."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtg_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_sibling_folder_without_mpn_is_dropped(self):
        from mpynode._common.util import template_gallery as tg
        _write_mpn(os.path.join(self.tmp, "sine_ripple"), native_type="mPyDeformer")
        swatch = os.path.join(self.tmp, ".mayaSwatches")
        os.makedirs(swatch)
        with open(os.path.join(swatch, "swatch.png"), "w") as f:
            f.write("x")
        os.makedirs(os.path.join(self.tmp, "empty_cat", "nested_empty"))
        cat = tg.scan_root(self.tmp)
        labels = [c.label for c in cat.children]
        self.assertEqual(labels, ["sine_ripple"])  # both junk folders dropped

    def test_nested_category_keeps_only_branches_with_templates(self):
        from mpynode._common.util import template_gallery as tg
        _write_mpn(os.path.join(self.tmp, "basics", "MPyDeformer", "sine_ripple"))
        os.makedirs(os.path.join(self.tmp, "basics", ".mayaSwatches"))
        cat = tg.scan_root(self.tmp)
        basics = cat.children[0]
        self.assertEqual(basics.label, "basics")
        self.assertEqual([c.label for c in basics.children], ["MPyDeformer"])

    def test_template_folder_with_swatch_child_drops_swatch(self):
        # Maya writes .mayaSwatches BESIDE a template's files; the entry stays,
        # the swatch subfolder is pruned from its children.
        from mpynode._common.util import template_gallery as tg
        leaf = os.path.join(self.tmp, "aim")
        _write_mpn(leaf, native_type="mPyTransform")
        os.makedirs(os.path.join(leaf, ".mayaSwatches"))
        entry = tg.scan_root(self.tmp).children[0]
        self.assertIsInstance(entry, tg.TemplateEntry)
        self.assertEqual(entry.children, ())

    def test_scan_dir_returns_none_for_templateless_subtree(self):
        from mpynode._common.util import template_gallery as tg
        junk = os.path.join(self.tmp, ".mayaSwatches")
        os.makedirs(junk)
        self.assertIsNone(tg._scan_dir(junk))


def _write_mpn_named(folder, filename, native_type="mPyNode"):
    """Author a real .mpn envelope named ``filename`` inside ``folder``."""
    from mpynode._common.io import mpn_io
    os.makedirs(folder, exist_ok=True)
    payload = {
        "native_type": native_type,
        "node_name": "demo",
        "expression": "self.out = self.inp",
        "input_attrs": {},
        "output_attrs": {},
        "stored_vars": {},
    }
    mpn_io.save_mpn(payload, os.path.join(folder, filename))


class TestGalleryManifestOrder(unittest.TestCase):
    """The optional ``gallery.json`` ``order`` key reorders a folder's immediate
    children; absent/invalid -> the default alphabetical order."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtgman_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write_manifest(self, folder, obj):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "gallery.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(obj, fh)

    def _child_labels(self):
        from mpynode._common.util import template_gallery as tg
        return [c.label for c in tg.scan_root(self.tmp).children]

    def test_no_manifest_is_alphabetical(self):
        _write_mpn(os.path.join(self.tmp, "advanced", "x"))
        _write_mpn(os.path.join(self.tmp, "basics", "y"))
        self.assertEqual(self._child_labels(), ["advanced", "basics"])

    def test_order_lists_basics_before_advanced(self):
        _write_mpn(os.path.join(self.tmp, "advanced", "x"))
        _write_mpn(os.path.join(self.tmp, "basics", "y"))
        self._write_manifest(self.tmp, {"order": ["basics", "advanced"]})
        self.assertEqual(self._child_labels(), ["basics", "advanced"])

    def test_unlisted_children_appended_after_in_alpha_order(self):
        for n in ("a", "b", "c"):
            _write_mpn(os.path.join(self.tmp, n, "leaf"))
        self._write_manifest(self.tmp, {"order": ["c", "a"]})
        self.assertEqual(self._child_labels(), ["c", "a", "b"])

    def test_unknown_names_ignored(self):
        _write_mpn(os.path.join(self.tmp, "advanced", "x"))
        _write_mpn(os.path.join(self.tmp, "basics", "y"))
        self._write_manifest(
            self.tmp, {"order": ["zzz", "basics", "nope", "advanced"]})
        self.assertEqual(self._child_labels(), ["basics", "advanced"])

    def test_non_list_order_ignored(self):
        # Discriminating fixture: single-char children so that if the guard were
        # missing and the string "ba" got iterated char-by-char, it WOULD
        # reorder to ["b", "a"]. The guard must leave the default ["a", "b"].
        _write_mpn(os.path.join(self.tmp, "a", "x"))
        _write_mpn(os.path.join(self.tmp, "b", "y"))
        self._write_manifest(self.tmp, {"order": "ba"})  # not a list
        self.assertEqual(self._child_labels(), ["a", "b"])

    def test_non_string_order_entries_ignored(self):
        # A nested-list / dict typo inside `order` must NOT crash discovery
        # (the "a typo never breaks discovery" contract) -- unhashable entries
        # are skipped and discovery falls back to the default order.
        _write_mpn(os.path.join(self.tmp, "advanced", "x"))
        _write_mpn(os.path.join(self.tmp, "basics", "y"))
        self._write_manifest(self.tmp, {"order": [["basics"], {"k": 1}, 7]})
        self.assertEqual(self._child_labels(), ["advanced", "basics"])

    def test_mixed_valid_and_invalid_order_entries(self):
        # Valid string entries still apply; invalid ones are skipped, unlisted
        # children append after in alphabetical order.
        for n in ("a", "b", "c"):
            _write_mpn(os.path.join(self.tmp, n, "leaf"))
        self._write_manifest(self.tmp, {"order": ["c", ["b"], "a"]})
        self.assertEqual(self._child_labels(), ["c", "a", "b"])

    def test_order_applies_to_nested_category(self):
        for n in ("zeta", "alpha"):
            _write_mpn(os.path.join(self.tmp, "basics", n, "leaf"))
        self._write_manifest(
            os.path.join(self.tmp, "basics"), {"order": ["zeta", "alpha"]})
        from mpynode._common.util import template_gallery as tg
        basics = tg.scan_root(self.tmp).children[0]
        self.assertEqual([c.label for c in basics.children], ["zeta", "alpha"])

    def test_manifest_file_never_listed_as_child(self):
        _write_mpn(os.path.join(self.tmp, "basics", "y"))
        self._write_manifest(self.tmp, {"order": ["basics"]})
        labels = self._child_labels()
        self.assertEqual(labels, ["basics"])
        self.assertNotIn("gallery.json", labels)


class TestGalleryManifestFilePointers(unittest.TestCase):
    """``gallery.json`` preview/description/template keys override the hardcoded
    filename lookups; a missing/invalid pointer falls back to the convention."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ndtgman_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _touch(self, folder, name, body="x"):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write(body)

    def _manifest(self, folder, obj):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "gallery.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(obj, fh)

    def _leaf_entry(self):
        from mpynode._common.util import template_gallery as tg
        return tg.scan_root(self.tmp).children[0]

    def test_preview_override_wins_over_convention(self):
        leaf = os.path.join(self.tmp, "tpl")
        _write_mpn(leaf)
        self._touch(leaf, "preview.png")  # convention present...
        self._touch(leaf, "hero.png")     # ...but manifest points elsewhere
        self._manifest(leaf, {"preview": "hero.png"})
        self.assertTrue(self._leaf_entry().preview_path.endswith("hero.png"))

    def test_description_override(self):
        leaf = os.path.join(self.tmp, "tpl")
        _write_mpn(leaf)
        self._touch(leaf, "notes.md", "# notes")
        self._manifest(leaf, {"description": "notes.md"})
        self.assertTrue(self._leaf_entry().description_path.endswith("notes.md"))

    def test_template_override_makes_folder_buildable(self):
        leaf = os.path.join(self.tmp, "tpl")
        _write_mpn_named(leaf, "custom.mpn", native_type="mPyNode")  # no template.mpn
        self._manifest(leaf, {"template": "custom.mpn"})
        from mpynode._common.util import template_gallery as tg
        entry = tg.scan_root(self.tmp).children[0]
        self.assertIsInstance(entry, tg.TemplateEntry)
        self.assertTrue(entry.mpn_path.endswith("custom.mpn"))
        self.assertEqual(entry.native_type, "mPyNode")

    def test_missing_pointer_falls_back_to_convention(self):
        leaf = os.path.join(self.tmp, "tpl")
        _write_mpn(leaf)
        self._touch(leaf, "preview.png")
        self._manifest(leaf, {"preview": "does_not_exist.png"})
        self.assertTrue(self._leaf_entry().preview_path.endswith("preview.png"))

    def test_malformed_manifest_ignored(self):
        leaf = os.path.join(self.tmp, "tpl")
        _write_mpn(leaf)
        with open(os.path.join(leaf, "gallery.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("this is not json {{{")
        from mpynode._common.util import template_gallery as tg
        entry = tg.scan_root(self.tmp).children[0]  # must not raise
        self.assertIsInstance(entry, tg.TemplateEntry)

    def test_non_object_manifest_ignored(self):
        leaf = os.path.join(self.tmp, "tpl")
        _write_mpn(leaf)
        with open(os.path.join(leaf, "gallery.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(["not", "an", "object"], fh)
        from mpynode._common.util import template_gallery as tg
        entry = tg.scan_root(self.tmp).children[0]
        self.assertIsInstance(entry, tg.TemplateEntry)
