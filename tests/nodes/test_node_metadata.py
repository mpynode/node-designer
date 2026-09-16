"""Per-node metadata: registry helpers, mixin, UI dialog, completeness

Consolidated from: test_metadata_registry.py, test_metadata_ui.py, test_metadata_tab_completeness.py.
"""

from __future__ import annotations

# ===================== from test_metadata_registry.py =====================
import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__metadata_registry():
    standalone_init()
    ensure_plugins_loaded()


# ----------------------------------------------------------------------------
# Pure helpers (no Maya).
# ----------------------------------------------------------------------------
class TestPureHelpers(unittest.TestCase):
    def test_coerce_empty(self):
        from mpynode._common.lifecycle import metadata_registry as M

        c = M.coerce(None)
        self.assertEqual(c["authors"], [])
        for k in ("version", "license", "description"):
            self.assertEqual(c[k], "")
        self.assertNotIn("copyright", c)

    def test_coerce_authors_string_becomes_list(self):
        from mpynode._common.lifecycle import metadata_registry as M

        self.assertEqual(M.coerce({"authors": "Jane <j@x>"})["authors"],
                         ["Jane <j@x>"])
        # blank authors drop out
        self.assertEqual(M.coerce({"authors": ["", "  ", "Bob"]})["authors"],
                         ["Bob"])

    def test_coerce_drops_none_authors(self):
        # honor the "blank entries dropped" contract: a None element (an absent
        # optional) must NOT become the literal author "None".
        from mpynode._common.lifecycle import metadata_registry as M

        self.assertEqual(M.coerce({"authors": [None]})["authors"], [])
        self.assertEqual(
            M.coerce({"authors": [None, "", "  ", "Real"]})["authors"],
            ["Real"])

    def test_coerce_non_string_scalars_stringified(self):
        from mpynode._common.lifecycle import metadata_registry as M

        self.assertEqual(M.coerce({"version": 1.0})["version"], "1.0")

    def test_is_empty(self):
        from mpynode._common.lifecycle import metadata_registry as M

        self.assertTrue(M.is_empty(None))
        self.assertTrue(M.is_empty({}))
        self.assertTrue(M.is_empty({"authors": [], "version": ""}))
        self.assertFalse(M.is_empty({"license": "(c) 2026"}))
        self.assertFalse(M.is_empty({"authors": ["x"]}))
        # a legacy copyright folds into license, so it still counts
        self.assertFalse(M.is_empty({"copyright": "(c) 2026"}))

    def test_merge_node_wins_when_present(self):
        from mpynode._common.lifecycle import metadata_registry as M

        node = {"license": "(c) Node", "version": "2.0"}
        defaults = {"license": "(c) Global", "version": "1.0",
                    "authors": ["Studio <s@x>"], "description": "global"}
        m = M.merge_metadata(node, defaults)
        self.assertEqual(m["license"],     "(c) Node")        # node wins
        self.assertEqual(m["version"],     "2.0")             # node wins
        self.assertEqual(m["authors"],     ["Studio <s@x>"])  # fell back
        self.assertEqual(m["description"], "global")          # fell back

    def test_merge_empty_node_uses_defaults(self):
        from mpynode._common.lifecycle import metadata_registry as M

        m = M.merge_metadata({}, {"license": "(c) Global"})
        self.assertEqual(m["license"], "(c) Global")

    def test_build_hash_deterministic_and_12_hex(self):
        from mpynode._common.lifecycle import metadata_registry as M

        h1 = M.build_hash("hello world")
        h2 = M.build_hash("hello world")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in h1))
        self.assertNotEqual(h1, M.build_hash("hello world!"))

    def test_stamp_build_hash_substitutes_placeholder(self):
        from mpynode._common.lifecycle import metadata_registry as M

        text = "x " + M.BUILD_HASH_PLACEHOLDER + " y"
        out, h = M.stamp_build_hash(text)
        # the hash is computed over the placeholder text (deterministic), then
        # substituted -- so the placeholder no longer appears in the output.
        self.assertNotIn(M.BUILD_HASH_PLACEHOLDER, out)
        self.assertIn(h, out)
        self.assertEqual(h, M.build_hash(text))
        # idempotent for the same input
        self.assertEqual(M.stamp_build_hash(text), (out, h))

    def test_vendor_string_priority(self):
        """Authors, else the default. The license block is NOT consulted: it
        leads with a term ("MIT License", "CC BY-SA 4.0"), not a party, which
        makes a poor Plug-in Manager vendor. A studio wanting its name there
        sets metadata_default_authors."""
        from mpynode._common.lifecycle import metadata_registry as M

        self.assertEqual(M.vendor_string({"authors": ["Jane <j@x>"]}),
                         "Jane <j@x>")
        self.assertEqual(M.vendor_string({"authors": ["A <a@x>", "B <b@x>"]}),
                         "A <a@x>; B <b@x>")
        self.assertEqual(M.vendor_string({}), "mpynode-native")
        self.assertEqual(M.vendor_string({"license": "MIT License"}),
                         "mpynode-native")

    def test_version_string_default(self):
        from mpynode._common.lifecycle import metadata_registry as M

        self.assertEqual(M.version_string({}), "1.0")
        self.assertEqual(M.version_string({"version": "3.2.1"}), "3.2.1")

    def test_banner_lines_contains_fields(self):
        from mpynode._common.lifecycle import metadata_registry as M

        meta = {"authors": ["Jane <j@x>"], "version": "2.0",
                "license": "(c) 2026 Acme\nMIT"}
        lines = M.banner_lines(meta)
        blob  = "\n".join(lines)
        self.assertTrue(all(ln.startswith("//") for ln in lines))
        self.assertIn("Jane <j@x>", blob)
        self.assertIn("2.0", blob)
        self.assertIn("(c) 2026 Acme", blob)
        self.assertIn("MIT", blob)
        self.assertIn(M.BUILD_HASH_PLACEHOLDER, blob)  # build token present

    def test_banner_lines_empty_meta_still_has_build_token(self):
        from mpynode._common.lifecycle import metadata_registry as M

        blob = "\n".join(M.banner_lines({}))
        self.assertIn(M.BUILD_HASH_PLACEHOLDER, blob)

    def test_banner_lines_default_args_are_the_cpp_banner_verbatim(self):
        """The prefix/build parameters exist for the .py bake. If their defaults
        move by one character the compiled tier's banner moves with them, which
        changes every generated .cpp and invalidates the port cache. Spelled out
        literally so it cannot agree with a changed banner_lines."""
        from mpynode._common.lifecycle import metadata_registry as M

        bar = "// " + "=" * 73
        self.assertEqual(
            M.banner_lines({"authors": ["Ada L <ada@x>"], "version": "2.1",
                            "license": "(c) 2026 Studio\nMIT",
                            "description": "A test node."}),
            [bar,
             "// Generated by mpynode-native.",
             "// build: %s" % M.BUILD_HASH_PLACEHOLDER,
             "// version: 2.1",
             "// author(s): Ada L <ada@x>",
             "//",
             "// (c) 2026 Studio",
             "// MIT",
             "//",
             "// description: A test node.",
             bar])

    def test_banner_lines_python_prefix_and_no_build(self):
        """The .py bake has no compile step, so nothing stamps the placeholder;
        emitted with build=True it would reach the file verbatim."""
        from mpynode._common.lifecycle import metadata_registry as M

        lines = M.banner_lines({"authors": ["Jane <j@x>"], "license": "MIT"},
                               generator="Node Designer", prefix="#",
                               build=False)
        blob = "\n".join(lines)
        self.assertTrue(all(ln.startswith("#") for ln in lines), blob)
        self.assertNotIn("//", blob)
        self.assertNotIn(M.BUILD_HASH_PLACEHOLDER, blob)
        self.assertNotIn("build:", blob)
        self.assertIn("# Generated by Node Designer.", blob)
        self.assertIn("# author(s): Jane <j@x>", blob)
        self.assertIn("# MIT", blob)
        self.assertNotIn("license:", blob)
        self.assertEqual(lines[0], "# " + "=" * 73)
        self.assertEqual(lines[-1], lines[0])

    def test_block_fields_keep_the_line_breaks_the_author_typed(self):
        """A licence is multi-line by nature. Collapsing it (what every field
        used to do) produced one unreadable run in the header while the dialog,
        which soft-wraps, looked fine -- so the banner showed a layout the file
        could not reproduce."""
        from mpynode._common.lifecycle import metadata_registry as M

        meta = {"license": "MIT License\n\nPermission is hereby granted,\n"
                           "free of charge.",
                "description": "Line one.\nLine two."}
        for prefix in ("//", "#"):
            lines = M.banner_lines(meta, prefix=prefix, build=False)
            # the license goes in VERBATIM -- no label, not even on line 1
            self.assertIn("%s MIT License" % prefix, lines)
            self.assertIn("%s Permission is hereby granted," % prefix, lines)
            self.assertIn("%s free of charge." % prefix, lines)
            self.assertNotIn("license:", "\n".join(lines))
            self.assertIn("%s description: Line one." % prefix, lines)
            self.assertIn("%s Line two." % prefix, lines)
            # A blank line inside the block is the BARE prefix: no trailing
            # whitespace anywhere in a generated banner.
            self.assertIn(prefix, lines)
            self.assertFalse([ln for ln in lines if ln != ln.rstrip()])

    def test_no_value_can_escape_its_comment(self):
        """The reason _one_line existed. Keeping line breaks must not weaken
        it: EVERY emitted line carries the prefix, including \\r and \\r\\n
        splits that a bare split("\\n") would leave embedded."""
        from mpynode._common.lifecycle import metadata_registry as M

        nasty = "ok\r\nint evil();\rmore\nlast"
        for prefix in ("//", "#"):
            lines = M.banner_lines({"license": nasty, "description": nasty},
                                   prefix=prefix, build=False)
            self.assertTrue(all(ln.startswith(prefix) for ln in lines), lines)
            for ln in lines:
                self.assertNotIn("\n", ln)
                self.assertNotIn("\r", ln)

    def test_authors_get_one_labelled_line_each(self):
        # They are typed one per line and stored as a list; joining them onto
        # one line was the last place the banner stopped mirroring the dialog.
        from mpynode._common.lifecycle import metadata_registry as M

        lines = M.banner_lines({"authors": ["Ada L <a@x>", "Bob R <b@y>"]},
                               prefix="#", build=False)
        self.assertIn("# author(s): Ada L <a@x>", lines)
        self.assertIn("# author(s): Bob R <b@y>", lines)
        self.assertNotIn("Ada L <a@x>; Bob R <b@y>", "\n".join(lines))

    def test_bake_header_enabled_is_headless_safe(self):
        """Both callers invoke this unguarded, so a prefs read that blows up
        must degrade to the default rather than propagate.

        The failure is forced by making ``get_pref`` RAISE, not by hiding the
        module from ``sys.modules``: ``from mpynode.ui import preferences``
        resolves the attribute on the already-imported package, so hiding it
        does not produce the ImportError it looks like it does."""
        from mpynode._common.lifecycle import metadata_registry as M
        from mpynode.ui import preferences as P

        self.assertIsInstance(M.bake_header_enabled(), bool)
        saved = P.get_pref

        def _boom(*_a, **_k):
            raise RuntimeError("prefs unavailable")

        P.get_pref = _boom
        try:
            self.assertTrue(M.bake_header_enabled())        # default kept
            self.assertFalse(M.bake_header_enabled(False))
        finally:
            P.get_pref = saved

    def test_bake_header_enabled_reads_the_preference(self):
        from mpynode._common.lifecycle import metadata_registry as M
        from mpynode.ui import preferences as P

        saved = P.get_pref
        P.get_pref = lambda key, default=None: (
            False if key == "metadata_bake_header" else saved(key, default))
        try:
            self.assertFalse(M.bake_header_enabled())
        finally:
            P.get_pref = saved

    def test_prefs_defaults_is_headless_safe(self):
        """Best-effort by contract: a prefs read that raises must yield {}
        rather than propagate, because both the compile and the bake call this
        unguarded.

        Driven by making ``get_pref`` RAISE and by seeding a real value first.
        Hiding the module from ``sys.modules`` does NOT work (the ``from
        mpynode.ui import preferences`` form reads the package attribute), and
        on a machine with no prefs set the function returns {} anyway -- so
        that version of this test passed without exercising the guard at all.
        """
        from mpynode._common.lifecycle import metadata_registry as M
        from mpynode.ui import preferences as P

        self.assertIsInstance(M.prefs_defaults(), dict)
        saved = P.get_pref

        P.get_pref = lambda key, default=None: (
            "(c) Seeded" if key == "metadata_default_license" else "")
        try:
            self.assertEqual(M.prefs_defaults(), {"license": "(c) Seeded"})
        finally:
            P.get_pref = saved

        def _boom(*_a, **_k):
            raise RuntimeError("prefs unavailable")

        P.get_pref = _boom
        try:
            self.assertEqual(M.prefs_defaults(), {})
        finally:
            P.get_pref = saved

    def test_a_legacy_copyright_folds_into_license(self):
        """``copyright`` was retired when Node Info merged it into ``license``:
        a CC0 or public-domain node has no copyright holder to name, so that
        label invited the wrong content. A node whose metadata predates the
        merge must keep its notice, ABOVE the license text."""
        from mpynode._common.lifecycle import metadata_registry as M

        c = M.coerce({"copyright": "(c) 2026 Acme", "license": "MIT"})
        self.assertEqual(c["license"], "(c) 2026 Acme\nMIT")
        self.assertNotIn("copyright", c)
        # with no license of its own it simply BECOMES the license
        self.assertEqual(M.coerce({"copyright": "(c) X"})["license"], "(c) X")
        # a blank legacy value adds nothing -- no stray leading newline
        self.assertEqual(
            M.coerce({"copyright": "  ", "license": "MIT"})["license"], "MIT")

    def test_copyright_is_not_a_field(self):
        from mpynode._common.lifecycle import metadata_registry as M

        self.assertNotIn("copyright", M.FIELDS)
        self.assertEqual(
            M.FIELDS,
            ("authors", "version", "license", "description", "type_id"))

    def test_license_block_is_fenced_by_blank_comment_lines(self):
        """The fence separates the UNLABELLED legal block from the labelled
        fields around it. The TRAILING fence is emitted only when something
        follows, so the block never butts a bare prefix against the closing
        bar."""
        from mpynode._common.lifecycle import metadata_registry as M

        bar = "# " + "=" * 73
        self.assertEqual(
            M.banner_lines({"license": "MIT"}, generator="Node Designer",
                           prefix="#", build=False),
            [bar, "# Generated by Node Designer.", "#", "# MIT", bar])
        self.assertEqual(
            M.banner_lines({"license": "MIT", "description": "d"},
                           generator="Node Designer", prefix="#", build=False),
            [bar, "# Generated by Node Designer.", "#", "# MIT", "#",
             "# description: d", bar])

# ----------------------------------------------------------------------------
# MetadataMixin on a real node (round-trip through the _metadata plug).
# ----------------------------------------------------------------------------
class TestMetadataMixin(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="metaTest")

    def test_default_is_empty(self):
        self.assertFalse(self.node.has_metadata())
        self.assertTrue(self.node.get_metadata()["authors"] == [])

    def test_set_get_round_trip(self):
        meta = {"authors": ["Jane <j@x>"], "version": "1.2.0",
                "license": "(c) 2026 Acme\nMIT",
                "description": "Does a thing."}
        self.assertTrue(self.node.set_metadata(meta))
        got = self.node.get_metadata()
        self.assertEqual(got["authors"],     ["Jane <j@x>"])
        self.assertEqual(got["version"],     "1.2.0")
        self.assertEqual(got["license"],     "(c) 2026 Acme\nMIT")
        self.assertEqual(got["description"], "Does a thing.")
        self.assertTrue(self.node.has_metadata())

    def test_plug_created_lazily_only_on_set(self):
        import maya.cmds as mc

        # fresh node: no plug yet (byte-identical / cache-stable)
        self.assertFalse(mc.attributeQuery(
            "_metadata", node=self.node.get_name(), exists=True))
        self.node.set_metadata({"version": "1.0"})
        self.assertTrue(mc.attributeQuery(
            "_metadata", node=self.node.get_name(), exists=True))

    def test_clear(self):
        self.node.set_metadata({"license": "(c) X"})
        self.assertTrue(self.node.has_metadata())
        self.node.clear_metadata()
        self.assertFalse(self.node.has_metadata())

    def test_get_tolerates_malformed_json(self):
        import maya.cmds as mc

        name = self.node.get_name()
        mc.addAttr(name, longName="_metadata", dataType="string", hidden=True)
        mc.setAttr(name + "._metadata", "not json{", type="string")
        # never raises; returns the coerced-empty shape
        self.assertEqual(self.node.get_metadata()["authors"], [])
        self.assertFalse(self.node.has_metadata())

    def test_survives_on_other_node_types(self):
        # the mixin is on the base, so a specialty type carries it too
        from mpynode.wrappers.mpy_file import MPyFile

        f = MPyFile.create(name="metaFile")
        self.assertTrue(f.set_metadata({"license": "(c) F"}))
        self.assertEqual(f.get_metadata()["license"], "(c) F")


# ----------------------------------------------------------------------------
# .mpn round-trip of metadata (separate structured payload key).
# ----------------------------------------------------------------------------
class TestMetadataMpnRoundTrip(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def test_serialize_omits_metadata_when_empty(self):
        from mpynode._common.io import mpn_io
        from mpynode.wrappers._mpy_node import MPyNode

        node    = MPyNode.create(name="plainMeta")
        payload = mpn_io.serialize_node(node)
        self.assertNotIn("metadata", payload)

    def test_round_trip_restores_metadata(self):
        from mpynode._common.io import mpn_io
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(name="srcMeta")
        node.set_metadata({"license": "(c) 2026 Acme", "version": "9.9"})
        payload = mpn_io.serialize_node(node)
        self.assertIn("metadata", payload)

        rebuilt = mpn_io.deserialize_node(payload, name="dstMeta")
        got     = rebuilt.get_metadata()
        self.assertEqual(got["license"], "(c) 2026 Acme")
        self.assertEqual(got["version"], "9.9")


# ===================== from test_metadata_ui.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-metadata-ui-test"])

import unittest


class _FakeNode:
    """Duck-typed wrapper exposing only what the dialog touches."""

    def __init__(self, name="fakeNode", meta=None):
        self._name = name
        self._meta = dict(meta or {})

    def get_name(self):
        return self._name

    def get_metadata(self):
        return dict(self._meta)

    def set_metadata(self, meta):
        self._meta = dict(meta)
        return True


class TestPreferencesDefaults(unittest.TestCase):
    def test_default_prefs_has_metadata_keys(self):
        from mpynode.ui import preferences

        for key in ("metadata_default_authors", "metadata_default_version",
                    "metadata_default_license"):
            self.assertIn(key, preferences.DEFAULT_PREFS)
        # Copyright merged into License; the retired key must not come back.
        self.assertNotIn("metadata_default_copyright",
                         preferences.DEFAULT_PREFS)

    def test_metadata_defaults_ship_empty(self):
        # CACHE-STABILITY INVARIANT: every metadata default MUST ship empty so a
        # stock install injects NO metadata into specs -> a no-metadata node
        # keeps a byte-identical spec + port-cache key. The compile-time
        # fallback (version "1.0") comes from metadata_registry.
        from mpynode.ui import preferences

        for key in ("metadata_default_authors", "metadata_default_version",
                    "metadata_default_license"):
            self.assertEqual(
                preferences.DEFAULT_PREFS[key], "",
                "%s must ship empty (cache-stability)" % key)


class TestSceneTreeInfoSignal(unittest.TestCase):
    def test_scene_tree_exposes_node_info_signal(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        self.assertTrue(hasattr(NDSceneTree, "nodeInfoRequested"))


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestPreferencesDialogMetadataPage(unittest.TestCase):
    def test_dialog_loads_metadata_page_from_prefs(self):
        # Prove the Metadata page actually LOADS from prefs: set a distinctive
        # value, rebuild, read it back. Restore the original in finally so the
        # user's real ~/.mpynode/preferences.json is left unchanged.
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog
        from mpynode.ui import preferences

        old = preferences.get_pref("metadata_default_license", "")
        try:
            preferences.set_pref("metadata_default_license", "(c) DISTINCT 4242")
            dlg = NDPreferencesDialog()
            self.assertTrue(hasattr(dlg, "_meta_license_edit"))
            self.assertEqual(
                dlg._meta_license_edit.toPlainText(), "(c) DISTINCT 4242")
            self.assertFalse(hasattr(dlg, "_meta_copyright_edit"))
        finally:
            preferences.set_pref("metadata_default_license", old)

    def test_prefs_license_field_is_multiline(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog
        from mpynode.ui.qt_wrapper import QPlainTextEdit

        dlg = NDPreferencesDialog()
        self.assertIsInstance(dlg._meta_license_edit, QPlainTextEdit)

    def test_prefs_license_expands_to_fill(self):
        # License fills the space below the fields (no wasted gap above the
        # buttons / no fixed box) -> can grow tall.
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        self.assertGreater(dlg._meta_license_edit.maximumHeight(), 1000)

    def test_prefs_min_window_size_pinned(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        self.assertEqual(
            (dlg.minimumWidth(), dlg.minimumHeight()), (560, 440))


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestNodeInfoDialog(unittest.TestCase):
    def _dialog(self, node):
        from mpynode.ui.dialogs.node_info import NDNodeInfoDialog

        return NDNodeInfoDialog(node)

    def test_loads_node_metadata_into_fields(self):
        node = _FakeNode("n1", {
            "authors": ["Jane <j@x>", "Bob <b@x>"], "version": "2.0",
            "license": "(c) Acme\nMIT",
            "description": "does things"})
        dlg = self._dialog(node)
        got = dlg.metadata_from_fields()
        self.assertEqual(got["authors"],     ["Jane <j@x>", "Bob <b@x>"])
        self.assertEqual(got["version"],     "2.0")
        self.assertEqual(got["license"],     "(c) Acme\nMIT")
        self.assertEqual(got["description"], "does things")
        self.assertNotIn("copyright", got)

    def test_the_block_fields_do_not_word_wrap(self):
        """Soft wrap inserts no newline, so a long line LOOKED formatted in the
        dialog and came out as one run in the header. With NoWrap the break you
        see is a break you typed, which is what lets the banner mirror this box
        -- and a horizontal bar is what makes the overflow reachable."""
        from mpynode.ui.qt_wrapper import QPlainTextEdit, Qt

        dlg = self._dialog(_FakeNode("nw", {}))
        for name in ("_license_edit", "_description_edit", "_authors_edit"):
            edit = getattr(dlg, name)
            self.assertEqual(edit.lineWrapMode(), QPlainTextEdit.NoWrap, name)
            self.assertNotEqual(edit.horizontalScrollBarPolicy(),
                                Qt.ScrollBarAlwaysOff, name)

    def test_a_multiline_value_survives_the_dialog_round_trip(self):
        # .strip() must trim only the OUTER whitespace; collapsing the inner
        # breaks here would undo the banner change one layer up.
        text = "MIT License\n\nPermission is hereby granted."
        dlg  = self._dialog(_FakeNode("ml", {"license": text}))
        self.assertEqual(dlg.metadata_from_fields()["license"], text)

    def test_empty_node_yields_empty_fields(self):
        # crucial: empty fields stay empty so the compile-time merge can fall
        # back to the live global default (defaults are NOT baked into the node).
        dlg = self._dialog(_FakeNode("n2", {}))
        got = dlg.metadata_from_fields()
        self.assertEqual(got["authors"], [])
        self.assertEqual(got["license"], "")
        self.assertEqual(got["version"], "")

    def test_save_persists_to_node(self):
        node = _FakeNode("n3", {})
        dlg  = self._dialog(node)
        dlg._license_edit.setPlainText("(c) 2026 Me")
        dlg._version_edit.setText("1.5")
        dlg._authors_edit.setPlainText("Ann <a@x>\nBea <b@x>")
        dlg.save()
        self.assertEqual(node._meta["license"], "(c) 2026 Me")
        self.assertEqual(node._meta["version"], "1.5")
        self.assertEqual(node._meta["authors"], ["Ann <a@x>", "Bea <b@x>"])

    def test_license_field_is_multiline_and_tall(self):
        # A short-form license (MIT / BSD-3) is multi-line prose; the field must
        # be a multi-line widget tall enough to show a meaningful chunk.
        from mpynode.ui.qt_wrapper import QPlainTextEdit

        dlg = self._dialog(_FakeNode("nLic", {}))
        self.assertIsInstance(dlg._license_edit, QPlainTextEdit)
        self.assertGreaterEqual(dlg._license_edit.minimumHeight(), 100)

    def test_license_field_expands_and_scrolls(self):
        # The license field must EXPAND to fill the window (not a fixed box) and
        # scroll when its text overflows.
        from mpynode.ui.qt_wrapper import QPlainTextEdit

        dlg = self._dialog(_FakeNode("nLicExp", {"license": "line\n" * 60}))
        self.assertIsInstance(dlg._license_edit, QPlainTextEdit)
        # not fixed-height: can grow to fill available space
        self.assertGreater(dlg._license_edit.maximumHeight(), 1000)
        self.assertGreaterEqual(dlg._license_edit.minimumHeight(), 120)
        # overflowing content is scrollable
        self.assertGreater(dlg._license_edit.verticalScrollBar().maximum(), 0)

    def test_info_min_window_size_pinned(self):
        dlg = self._dialog(_FakeNode("nMin", {}))
        self.assertEqual(
            (dlg.minimumWidth(), dlg.minimumHeight()), (480, 520))

    def test_license_and_description_in_vertical_splitter(self):
        # License + Description sit in a draggable vertical splitter so the user
        # can re-apportion the space between them.
        from mpynode.ui.qt_wrapper import QSplitter, Qt

        dlg = self._dialog(_FakeNode("nSplit", {}))
        self.assertIsInstance(dlg._split, QSplitter)
        self.assertEqual(dlg._split.orientation(), Qt.Vertical)
        self.assertEqual(dlg._split.count(), 2)

    def test_license_and_description_scrollbars_always_on(self):
        # Both fields show a persistent, grabbable scrollbar (macOS overlay
        # scrollbars fade out -> AlwaysOn guarantees the bar the user wants).
        from mpynode.ui.qt_wrapper import Qt

        dlg = self._dialog(_FakeNode("nSB", {}))
        self.assertEqual(dlg._license_edit.verticalScrollBarPolicy(),
                         Qt.ScrollBarAlwaysOn)
        self.assertEqual(dlg._description_edit.verticalScrollBarPolicy(),
                         Qt.ScrollBarAlwaysOn)

    def test_license_description_equal_default_split(self):
        # Default split is ~50/50 between license and description.
        dlg = self._dialog(_FakeNode("nEq", {}))
        dlg.resize(480, 760)
        dlg.show()
        if _QAPP is not None:
            _QAPP.processEvents()
            _QAPP.processEvents()
        sizes = dlg._split.sizes()
        self.assertEqual(len(sizes), 2)
        self.assertLessEqual(abs(sizes[0] - sizes[1]), 6)

    def test_multiline_license_round_trips(self):
        node = _FakeNode("nLic2", {})
        dlg  = self._dialog(node)
        lic = ("MIT License\n\nPermission is hereby granted, free of charge, "
               "to any person obtaining a copy of this software...")
        dlg._license_edit.setPlainText(lic)
        dlg.save()
        self.assertEqual(node._meta["license"], lic)

    def test_global_default_shown_as_placeholder_not_value(self):
        from mpynode.ui import preferences

        old = preferences.get_pref("metadata_default_license", "")
        try:
            preferences.set_pref("metadata_default_license", "(c) GLOBAL")
            dlg = self._dialog(_FakeNode("n4", {}))
            # default appears only as a placeholder hint, never as a real value
            self.assertEqual(dlg._license_edit.toPlainText(),       "")
            self.assertEqual(dlg._license_edit.placeholderText(),   "(c) GLOBAL")
            self.assertEqual(dlg.metadata_from_fields()["license"], "")
        finally:
            preferences.set_pref("metadata_default_license", old)


# ===================== from test_metadata_tab_completeness.py =====================
import unittest


REQUIRED_METHODS = (
    "set_metadata",
    "get_metadata",
    "has_metadata",
    "clear_metadata",
)


class TestMetadataMixinOnAllWrappers(unittest.TestCase):
    def test_every_wrapper_has_metadata_surface(self):
        from mpynode._node_registry import REGISTRY

        missing = []
        for native_type, spec in REGISTRY.items():
            try:
                cls = spec.get_wrapper_class()
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    f"failed to load wrapper for {native_type!r}: {exc}"
                )
            for method in REQUIRED_METHODS:
                if not hasattr(cls, method):
                    missing.append(
                        f"{native_type} ({cls.__module__}.{cls.__name__})"
                        f" missing {method!r}"
                    )
        if missing:
            self.fail(
                "Per-node metadata requires every wrapper to expose the "
                "MetadataMixin surface so the Info dialog / .mpn round-trip / "
                "compile embedding work for every node type. Missing:\n  "
                + "\n  ".join(missing)
            )


def setUpModule():
    _setUpModule__metadata_registry()


if __name__ == "__main__":
    import unittest
    unittest.main()
