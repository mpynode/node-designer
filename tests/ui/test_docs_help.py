"""Built-in documentation viewer (Help menu) — docs locator, link
resolution, and the Qt viewer / menu wiring.

The locator + link-resolver are pure (no Qt), so they test directly. The
widget + menu tests are Qt-guarded (skip when PySide is unavailable),
mirroring the other UI test modules.
"""

from __future__ import annotations

import os
import unittest


# Create the QApplication at IMPORT time, before maya.standalone init
# installs a non-GUI QCoreApplication that would break QWidget creation.
# The locator/link-resolver tests below need no Qt.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["nd-docs-test"])


def _qt() -> bool:
    return _QAPP is not None


# ===========================================================================
# docs_locator (pure)
# ===========================================================================


class TestDocsLocator(unittest.TestCase):
    def test_find_docs_root(self):
        from mpynode._common.util import docs_locator

        root = docs_locator.find_docs_root()
        self.assertIsNotNone(root, "docs/ root should be discoverable")
        self.assertTrue(os.path.isdir(os.path.join(root, "node_types")))

    def test_home_doc_is_docs_index(self):
        """Home is docs/index.md (moved out of the former docs/api/)."""
        from mpynode._common.util import docs_locator

        home = docs_locator.home_doc()
        self.assertIsNotNone(home)
        self.assertTrue(home.endswith(os.path.join("docs", "index.md")))
        self.assertTrue(os.path.isfile(home))

    def test_list_node_type_docs_has_all_12_types(self):
        from mpynode._common.util import docs_locator

        titles = [t for t, _ in docs_locator.list_node_type_docs()]
        for nt in (
            "mPyNode", "mPyDeformer", "mPyLocator", "mPyConstraint",
            "mPyIkSolver", "mPyTransform", "mPyMesh",
            "mPySkinCluster", "mPyBlendShape", "mPyFile", "mPyNurbsCurve",
            "mPyNurbsSurface",
        ):
            self.assertIn(nt, titles)

    def test_listed_docs_are_real_md_files(self):
        from mpynode._common.util import docs_locator

        for _, p in docs_locator.list_node_type_docs():
            self.assertTrue(p.endswith(".md") and os.path.isfile(p), p)

    def test_helper_docs_sorted_last(self):
        from mpynode._common.util import docs_locator

        titles = [t for t, _ in docs_locator.list_node_type_docs()]
        self.assertIn("_input_type_contract", titles)
        self.assertEqual(titles[-1], "_input_type_contract")

    def test_exclude_helpers(self):
        from mpynode._common.util import docs_locator

        titles = [t for t, _ in docs_locator.list_node_type_docs(include_helpers=False)]
        self.assertNotIn("_input_type_contract", titles)
        self.assertIn("mPyDeformer", titles)

    # ---- Help -> Node Types menu order (mPyNode pinned first + separator) ---
    def test_menu_order_pins_mpynode_first_with_separator(self):
        from mpynode._common.util import docs_locator

        order = docs_locator.list_node_type_docs_menu_order()
        # mPyNode first, then a None separator marker, like the "New" menu.
        self.assertEqual(order[0][0], "mPyNode")
        self.assertIsNone(order[1])
        self.assertEqual(order.count(None), 1)  # exactly one separator
        titles = [e[0] for e in order if e is not None]
        self.assertEqual(titles.count("mPyNode"), 1)  # not duplicated into rest
        # same doc SET as list_node_type_docs, reordered with a separator.
        self.assertEqual(
            set(titles), {t for t, _ in docs_locator.list_node_type_docs()}
        )

    def test_pin_first_with_separator_synthetic(self):
        from mpynode._common.util import docs_locator

        items = [("a", "/pa"), ("mPyNode", "/pm"), ("b", "/pb")]
        out = docs_locator._pin_first_with_separator(items, "mPyNode")
        self.assertEqual(out, [("mPyNode", "/pm"), None, ("a", "/pa"), ("b", "/pb")])

    def test_pin_first_with_separator_no_match_is_unchanged(self):
        from mpynode._common.util import docs_locator

        items = [("a", "/pa"), ("b", "/pb")]
        out = docs_locator._pin_first_with_separator(items, "zzz")
        self.assertEqual(out, items)
        self.assertNotIn(None, out)


# ===========================================================================
# resolve_doc_link (pure)
# ===========================================================================


class TestDocLinkResolution(unittest.TestCase):
    def setUp(self):
        from mpynode._common.util import docs_locator

        self.loc = docs_locator
        self.root = docs_locator.find_docs_root()
        self.index = os.path.join(self.root, "index.md")
        self.nt_dir = os.path.join(self.root, "node_types")

    def test_relative_md_from_index_resolves(self):
        kind = self.loc.resolve_doc_link(self.index, "node_types/mPyDeformer.md")
        self.assertEqual(kind[0], "file")
        self.assertEqual(
            os.path.abspath(kind[1]),
            os.path.join(self.nt_dir, "mPyDeformer.md"),
        )
        self.assertEqual(kind[2], "")

    def test_sibling_link_between_node_docs(self):
        src = os.path.join(self.nt_dir, "mPyDeformer.md")
        kind = self.loc.resolve_doc_link(src, "mPySkinCluster.md")
        self.assertEqual(kind[0], "file")
        self.assertTrue(kind[1].endswith("mPySkinCluster.md"))

    def test_md_with_fragment(self):
        src = os.path.join(self.nt_dir, "mPyDeformer.md")
        kind = self.loc.resolve_doc_link(src, "mPyBlendShape.md#example")
        self.assertEqual(kind[0], "file")
        self.assertTrue(kind[1].endswith("mPyBlendShape.md"))
        self.assertEqual(kind[2], "example")

    def test_external_link_classified(self):
        kind = self.loc.resolve_doc_link(self.index, "https://example.com/x")
        self.assertEqual(kind, ("external", "https://example.com/x"))

    def test_pure_anchor(self):
        kind = self.loc.resolve_doc_link(self.index, "#quick-start")
        self.assertEqual(kind, ("anchor", "quick-start"))

    def test_missing_file_is_unknown(self):
        kind = self.loc.resolve_doc_link(self.index, "does_not_exist.md")
        self.assertEqual(kind[0], "unknown")


# ===========================================================================
# MarkdownBrowser widget (Qt-guarded)
# ===========================================================================


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestMarkdownBrowser(unittest.TestCase):
    def test_load_home_renders_content(self):
        from mpynode.ui.dialogs.doc_viewer import MarkdownBrowser
        from mpynode._common.util import docs_locator

        b = MarkdownBrowser()
        self.assertTrue(b.load(docs_locator.home_doc()))
        self.assertIn("mpynode", b.toPlainText().lower())

    def test_relative_link_navigates_and_back_returns_home(self):
        from mpynode.ui.dialogs.doc_viewer import MarkdownBrowser
        from mpynode._common.util import docs_locator
        from mpynode.ui.qt_wrapper import QUrl

        b = MarkdownBrowser()
        b.load(docs_locator.home_doc())
        b._on_anchor(QUrl("node_types/mPyDeformer.md"))
        self.assertTrue(b._current_path.endswith("mPyDeformer.md"))
        b.go_back()
        self.assertTrue(b._current_path.endswith("index.md"))

    def test_missing_doc_does_not_raise(self):
        from mpynode.ui.dialogs.doc_viewer import MarkdownBrowser

        b = MarkdownBrowser()
        # Returns False and shows an error doc; never raises.
        self.assertFalse(b.load("/no/such/doc.md"))


# ===========================================================================
# Help-menu wiring (Qt-guarded)
# ===========================================================================


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestDocMenuWiring(unittest.TestCase):
    def test_node_types_submenu_lists_every_doc(self):
        from mpynode.ui.qt_wrapper import QMenu
        from mpynode.ui.dialogs import doc_viewer
        from mpynode._common.util import docs_locator

        menu = QMenu("Help")
        _doc_action, nt_menu, _gh = doc_viewer.add_documentation_menu(menu, None)
        actions = [a for a in nt_menu.actions() if not a.isSeparator()]
        self.assertEqual(len(actions), len(docs_locator.list_node_type_docs()))
        self.assertGreaterEqual(len(actions), 13)

    def test_node_types_submenu_mpynode_first_with_separator(self):
        """mPyNode must be surfaced to the TOP with a separator line between it
        and the other node types -- mirroring the "New" drop-down."""
        from mpynode.ui.qt_wrapper import QMenu
        from mpynode.ui.dialogs import doc_viewer

        menu = QMenu("Help")
        _doc_action, nt_menu, _gh = doc_viewer.add_documentation_menu(menu, None)
        acts = nt_menu.actions()
        self.assertEqual(acts[0].text(), "mPyNode")  # pinned first
        self.assertTrue(acts[1].isSeparator())       # separator right after
        after = [a.text() for a in acts[2:] if not a.isSeparator()]
        self.assertNotIn("mPyNode", after)           # not duplicated below
        self.assertIn("mPyDeformer", after)


# ===========================================================================
# license_doc (pure) + About dialog renders LICENSE.md + GitHub link
# ===========================================================================


class TestLicenseDoc(unittest.TestCase):
    def test_license_doc_is_repo_root_license_md(self):
        from mpynode._common.util import docs_locator

        p = docs_locator.license_doc()
        self.assertIsNotNone(p)
        self.assertTrue(p.endswith(os.sep + "LICENSE.md"))
        self.assertTrue(os.path.isfile(p))

    def test_readme_doc_is_repo_root_readme_md(self):
        from mpynode._common.util import docs_locator

        p = docs_locator.readme_doc()
        self.assertIsNotNone(p)
        self.assertTrue(p.endswith(os.sep + "README.md"))
        self.assertTrue(os.path.isfile(p))


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestAboutDialog(unittest.TestCase):
    def test_about_renders_readme_markdown(self):
        from mpynode.ui.dialogs.about import AboutDialog

        dlg = AboutDialog()
        txt = dlg.browser.toPlainText()
        self.assertIn("MPyNode", txt)
        self.assertIn("Why technical artists like it", txt)


class TestCheatSheetLinks(unittest.TestCase):
    def _cheat_sheet_section(self):
        from mpynode._common.util import docs_locator

        index = docs_locator.home_doc()
        with open(index, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        start = next(
            i for i, ln in enumerate(lines)
            if ln.strip().lower() == "## node type cheat sheet"
        )
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
            len(lines),
        )
        return index, "\n".join(lines[start:end])

    def test_every_node_type_links_to_its_doc(self):
        """The cheat-sheet table itself links each node type to its
        node_types/*.md page, and each link resolves to a real file."""
        from mpynode._common.util import docs_locator

        index, section = self._cheat_sheet_section()
        for title, _ in docs_locator.list_node_type_docs(include_helpers=False):
            href = "node_types/%s.md" % title
            self.assertIn(
                href, section, "cheat sheet missing link to %s" % href
            )
            kind = docs_locator.resolve_doc_link(index, href)
            self.assertEqual(kind[0], "file")
            self.assertTrue(os.path.isfile(kind[1]))


class TestSectionSeparators(unittest.TestCase):
    def test_node_docs_have_horizontal_rules(self):
        """Every mPy*.md delineates its sections with `---` rules."""
        from mpynode._common.util import docs_locator

        root = docs_locator.find_docs_root()
        nt_dir = os.path.join(root, "node_types")
        mpy = [n for n in os.listdir(nt_dir) if n.startswith("mPy") and n.endswith(".md")]
        # 12 mPy*.md node-type pages: mPyGeometryFilter was removed and its
        # nurbsWave demo moved to mPyDeformer, leaving 12 registered types.
        self.assertGreaterEqual(len(mpy), 12)
        for name in mpy:
            with open(os.path.join(nt_dir, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertGreaterEqual(
                text.count("\n---\n"), 3, "%s has too few section rules" % name
            )


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestGithubLink(unittest.TestCase):
    def test_github_url_placeholder(self):
        from mpynode.ui.dialogs import doc_viewer

        self.assertEqual(
            doc_viewer.GITHUB_URL, "https://github.com/mpynode/node-designer"
        )

    def test_menu_has_github_action(self):
        from mpynode.ui.qt_wrapper import QMenu
        from mpynode.ui.dialogs import doc_viewer

        menu = QMenu("Help")
        _doc, _nt, github_action = doc_viewer.add_documentation_menu(menu, None)
        self.assertIsNotNone(github_action)
        self.assertIn("GitHub", github_action.text())
        self.assertIn(github_action, menu.actions())


# ===========================================================================
# slugify — must match the in-doc TOC anchors of docs/index.md (pure)
# ===========================================================================


class TestSlugify(unittest.TestCase):
    def test_matches_index_toc_anchors(self):
        from mpynode._common.util.docs_locator import slugify

        self.assertEqual(slugify("Quick start"), "quick-start")
        self.assertEqual(slugify("Core concepts"), "core-concepts")
        # em-dash dropped -> double hyphen, matching the TOC
        self.assertEqual(
            slugify("Creating nodes — full API per type"),
            "creating-nodes--full-api-per-type",
        )
        # backticks/parens/slash/underscores all dropped, matching the TOC
        self.assertEqual(
            slugify("Adding user attributes (`add_input_attr` / `add_output_attr`)"),
            "adding-user-attributes-addinputattr--addoutputattr",
        )


# ===========================================================================
# Native styling + working anchor navigation (Qt-guarded)
# ===========================================================================


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestMarkdownStyling(unittest.TestCase):
    def _browser_on(self, path):
        from mpynode.ui.dialogs.doc_viewer import MarkdownBrowser

        b = MarkdownBrowser()
        b.load(path)
        return b

    def test_toc_anchor_finds_heading(self):
        from mpynode._common.util import docs_locator

        b = self._browser_on(docs_locator.home_doc())
        self.assertTrue(b._scroll_to_slug("quick-start"))
        self.assertFalse(b._scroll_to_slug("no-such-heading-xyz"))

    def test_headings_get_top_margin(self):
        from mpynode._common.util import docs_locator

        b = self._browser_on(docs_locator.home_doc())
        doc = b.document()
        blk = doc.firstBlock()
        tm = None
        while blk.isValid():
            if blk.blockFormat().headingLevel() > 0:
                tm = blk.blockFormat().topMargin()
                break
            blk = blk.next()
        self.assertIsNotNone(tm)
        self.assertGreater(tm, 0.0)

    def test_tables_get_cell_padding(self):
        from mpynode._common.util import docs_locator
        from mpynode.ui.qt_wrapper import QTextTable

        mesh = [p for t, p in docs_locator.list_node_type_docs() if t == "mPyMesh"][0]
        b = self._browser_on(mesh)
        tables = [
            f for f in b.document().rootFrame().childFrames()
            if isinstance(f, QTextTable)
        ]
        self.assertTrue(tables, "mPyMesh.md should contain a table")
        self.assertGreater(tables[0].format().cellPadding(), 0.0)

    def _code_bg_blocks(self, browser):
        """Blocks carrying a (code-box) background brush."""
        from mpynode.ui.dialogs.doc_viewer import _enum_int
        out = []
        doc = browser.document()
        blk = doc.firstBlock()
        while blk.isValid():
            # _enum_int: on Qt6 BrushStyle is a scoped enum, so a bare
            # ``!= 0`` is always True (NoBrush included). Coerce to int first.
            if _enum_int(blk.blockFormat().background().style()) != 0:  # not NoBrush
                out.append(blk)
            blk = blk.next()
        return out

    def test_code_box_includes_interior_blank_lines(self):
        """The code box is contiguous: blank lines *inside* a fenced block
        get the background too (so it doesn't read as stripes)."""
        from mpynode._common.util import docs_locator

        mesh = [p for t, p in docs_locator.list_node_type_docs() if t == "mPyMesh"][0]
        b = self._browser_on(mesh)
        coded = self._code_bg_blocks(b)
        self.assertTrue(coded, "mPyMesh.md should contain a code block")
        self.assertTrue(
            any(not blk.text().strip() for blk in coded),
            "interior blank line inside a code block should be boxed",
        )

    def test_code_box_uses_single_line_height(self):
        """Code lines use single (natural) line height so the box paints
        solid top-to-bottom -- proportional leading leaves page-coloured
        stripes between lines."""
        from mpynode._common.util import docs_locator
        from mpynode.ui.qt_wrapper import QTextBlockFormat
        from mpynode.ui.dialogs.doc_viewer import _enum_int

        single = _enum_int(QTextBlockFormat.SingleHeight)
        mesh = [p for t, p in docs_locator.list_node_type_docs() if t == "mPyMesh"][0]
        b = self._browser_on(mesh)
        coded = self._code_bg_blocks(b)
        self.assertTrue(coded)
        for blk in coded:
            self.assertEqual(
                _enum_int(blk.blockFormat().lineHeightType()), single
            )

    def test_code_block_syntax_highlighted(self):
        """Native tokenizer colours keywords/strings/comments, so a code
        block contains more than one foreground colour."""
        from mpynode._common.util import docs_locator

        mesh = [p for t, p in docs_locator.list_node_type_docs() if t == "mPyMesh"][0]
        b = self._browser_on(mesh)
        colours = set()
        for blk in self._code_bg_blocks(b):
            it = blk.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.text().strip():
                    colours.add(frag.charFormat().foreground().color().name())
                it += 1
        self.assertGreater(len(colours), 1, "code should be syntax-highlighted")


def _qtextdocument():
    """QTextDocument is not re-exported by ``mpynode.ui.qt_wrapper``; resolve it
    the same way this module resolves QApplication at the top."""
    try:
        from PySide6.QtGui import QTextDocument
    except ImportError:
        from PySide2.QtGui import QTextDocument
    return QTextDocument


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestStylerOptionalPasses(unittest.TestCase):
    """The document-margin / paragraph-spacing / inline-code passes.

    They exist for the template gallery, whose description pane is a fraction
    of the Help dialog's size. They are keyword-gated and OFF by default: the
    Help viewer calls ``style_markdown_document(document, dark=...)`` with
    nothing else and must render exactly as it always has.
    """

    MD = ("# Title\n\nA paragraph with `inline_code` in it.\n\n"
          "## Heading with `code` inside\n\n"
          "```python\nx = 1\n```\n\n"
          "| A | B |\n|---|---|\n| `cell` | plain |\n\n"
          "- bullet with `span`\n")

    def _doc(self, **kw):
        from mpynode.ui.dialogs.doc_viewer import style_markdown_document

        QTextDocument = _qtextdocument()

        d = QTextDocument()
        d.setMarkdown(self.MD)
        style_markdown_document(d, dark=True, **kw)
        return d

    def _chips(self, doc):
        """Fragments carrying the chip background, excluding the pad chars
        (each pad is its own fragment and also carries the fixed-pitch
        property, so counting naively doubles the total)."""
        from mpynode.ui.qt_wrapper import QColor
        from mpynode.ui.dialogs import doc_viewer as dv

        want = QColor(dv._DARK["inline_code_bg"])
        out = []
        b = doc.firstBlock()
        while b.isValid():
            it = b.begin()
            while not it.atEnd():
                f = it.fragment()
                if f.isValid() and f.charFormat().hasProperty(
                        dv._FIXED_PITCH_PROP):
                    if (f.charFormat().background().color() == want
                            and f.text().strip(dv._CHIP_PAD) != ""):
                        out.append((f.text().strip(dv._CHIP_PAD),
                                    b.blockFormat().headingLevel(),
                                    dv._block_is_code(b)))
                it += 1
            b = b.next()
        return out

    def _paragraph_margins(self, doc):
        from mpynode.ui.qt_wrapper import QTextCursor
        from mpynode.ui.dialogs.doc_viewer import _block_is_code

        got = set()
        b = doc.firstBlock()
        while b.isValid():
            if (b.blockFormat().headingLevel() == 0 and not _block_is_code(b)
                    and b.textList() is None
                    and QTextCursor(b).currentTable() is None
                    and b.text().strip()):
                got.add((b.blockFormat().topMargin(),
                         b.blockFormat().bottomMargin()))
            b = b.next()
        return got

    # -- defaults: the Help viewer must not move -------------------------
    def test_defaults_leave_the_document_margin_alone(self):
        self.assertEqual(self._doc().documentMargin(), 4.0)

    def test_defaults_add_no_paragraph_spacing(self):
        self.assertEqual(self._paragraph_margins(self._doc()), {(6.0, 6.0)})

    def test_defaults_add_no_inline_chips(self):
        self.assertEqual(self._chips(self._doc()), [])

    # -- opted in --------------------------------------------------------
    def test_doc_margin_is_applied(self):
        self.assertEqual(self._doc(doc_margin=14.0).documentMargin(), 14.0)

    def test_paragraph_spacing_is_applied(self):
        got = self._paragraph_margins(self._doc(para_spacing=(0.0, 10.0)))
        self.assertEqual(got, {(0.0, 10.0)})

    def test_inline_code_gets_a_chip(self):
        chips = self._chips(self._doc(inline_code=True))
        self.assertIn("inline_code", [c[0] for c in chips])

    def test_no_chip_inside_a_fenced_block(self):
        # A fenced line renders in the same mono face as an inline span; the
        # only reliable discriminator is BlockCodeLanguage on the BLOCK.
        chips = self._chips(self._doc(inline_code=True))
        self.assertEqual([c for c in chips if c[2]], [])

    def test_no_chip_inside_a_heading(self):
        # A heading already carries its own colour + bold across the block.
        chips = self._chips(self._doc(inline_code=True))
        self.assertEqual([c for c in chips if c[1] > 0], [])

    def test_the_chip_is_padded_with_a_non_breaking_space(self):
        # Qt rich text has no char-level padding, so the gap is a real
        # character -- and it must not be a line-break opportunity or the chip
        # separates from its own text on a wrap.
        from mpynode.ui.dialogs import doc_viewer as dv

        text = self._doc(inline_code=True).toPlainText()
        n = len(self._chips(self._doc(inline_code=True)))
        self.assertGreater(n, 0)
        self.assertEqual(text.count(dv._CHIP_PAD), 2 * n)
        self.assertEqual(dv._CHIP_PAD, "\u202f")

    def test_restyling_does_not_accumulate_pads(self):
        from mpynode.ui.dialogs.doc_viewer import style_markdown_document
        from mpynode.ui.dialogs import doc_viewer as dv

        doc = self._doc(inline_code=True)
        before = doc.toPlainText().count(dv._CHIP_PAD)
        style_markdown_document(doc, dark=True, inline_code=True)
        self.assertEqual(doc.toPlainText().count(dv._CHIP_PAD), before)

    def test_inline_detection_uses_hasproperty_not_the_value(self):
        """On Qt 5.15 the fixed-pitch property is PRESENT on an inline span but
        its VALUE is False, so a ``fontFixedPitch()`` test finds nothing at all
        on Maya 2024. Guard the distinction the implementation depends on."""
        from mpynode.ui.dialogs import doc_viewer as dv

        doc = self._doc()          # unstyled by the inline pass
        seen = 0
        b = doc.firstBlock()
        while b.isValid():
            it = b.begin()
            while not it.atEnd():
                f = it.fragment()
                if f.isValid() and f.text().strip() == "inline_code":
                    self.assertTrue(
                        f.charFormat().hasProperty(dv._FIXED_PITCH_PROP))
                    seen += 1
                it += 1
            b = b.next()
        self.assertEqual(seen, 1)
