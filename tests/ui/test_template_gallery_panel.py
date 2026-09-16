import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # QApplication must exist before any QWidget is constructed.
    from mpynode.ui.qt_wrapper import Qt  # noqa: F401
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        from PySide2.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    _QT  = True
except Exception:  # pragma: no cover - Qt missing
    _QT = False


def setUpModule():
    try:
        from tests._setup import standalone_init
        standalone_init()
    except Exception:
        pass


@unittest.skipUnless(_QT, "Qt unavailable")
class TestQtWrapperQMovie(unittest.TestCase):
    def test_qmovie_is_exported(self):
        from mpynode.ui import qt_wrapper
        self.assertTrue(hasattr(qt_wrapper, "QMovie"))


@unittest.skipUnless(_QT, "Qt unavailable")
class TestPanelShell(unittest.TestCase):
    def test_panel_constructs_as_widget(self):
        from mpynode.ui.qt_wrapper import QWidget
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        panel = NDTemplateGalleryPanel(parent=None, scan=lambda: [])
        self.assertIsInstance(panel, QWidget)
        panel.deleteLater()


class _Cat:
    def __init__(self, label, children, preview_path=None,
                 description_path=None):
        self.label            = label
        self.children         = children
        self.preview_path     = preview_path
        self.description_path = description_path


class _Entry:
    def __init__(self, label, native_type, mpn_path="x.mpn",
                 preview_path=None, description_path=None, children=()):
        self.label            = label
        self.native_type      = native_type
        self.mpn_path         = mpn_path
        self.preview_path     = preview_path
        self.description_path = description_path
        self.children         = children


def _fake_scan():
    leaf_ok  = _Entry("Sine Ripple", "mPyDeformer")
    leaf_bad = _Entry("Broken One", None)
    cat      = _Cat("Deformers", [leaf_ok, leaf_bad])
    root_cat = _Cat("templates", [cat])
    return [("templates", "/tmp/templates", root_cat)]


@unittest.skipUnless(_QT, "Qt unavailable")
class TestTree(unittest.TestCase):
    def _panel(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        return NDTemplateGalleryPanel(parent=None, scan=_fake_scan)

    def test_tree_has_root_category_leaves(self):
        panel = self._panel()
        root  = panel.tree.topLevelItem(0)
        self.assertEqual(root.text(0), "templates")
        cat = root.child(0)
        self.assertEqual(cat.text(0), "Deformers")
        leaf = cat.child(0)
        self.assertIn("Sine Ripple", leaf.text(0))
        self.assertIn("mPyDeformer", leaf.text(0))  # native_type suffix
        panel.deleteLater()

    def test_none_native_type_leaf_disabled(self):
        panel = self._panel()
        bad   = panel.tree.topLevelItem(0).child(0).child(1)
        self.assertFalse(bad.flags() & Qt.ItemIsEnabled)
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestSelection(unittest.TestCase):
    def _panel(self, scan):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        return NDTemplateGalleryPanel(parent=None, scan=scan)

    def test_leaf_menu_has_create(self):
        import mpynode._common.io.mpn_io as mpn_io
        orig                   = mpn_io.load_mpn_header
        mpn_io.load_mpn_header = lambda p: {"metadata": {"version": "1.0"}}
        try:
            panel = self._panel(_fake_scan)
            leaf  = panel.tree.topLevelItem(0).child(0).child(0)
            panel.tree.setCurrentItem(leaf)
            self.assertIn("mPyDeformer", panel.meta_label.text())
            menu = panel._build_tree_menu(panel._selected_entry())
            self.assertIsNotNone(menu)
            self.assertIn("Create", [a.text() for a in menu.actions()])
            panel.deleteLater()
        finally:
            mpn_io.load_mpn_header = orig

    def test_category_menu_has_no_create_action(self):
        """A category is not buildable, so it never offers Create. It DOES get
        a menu now -- the reveal action is offered for every row (the fake
        category here has no path on disk, so reveal is present-but-disabled)."""
        panel = self._panel(_fake_scan)
        cat   = panel.tree.topLevelItem(0).child(0)
        panel.tree.setCurrentItem(cat)
        menu = panel._build_tree_menu(panel._selected_entry())
        self.assertIsNotNone(menu)
        self.assertNotIn("Create", [a.text() for a in menu.actions()])
        panel.deleteLater()

    def test_png_preview_uses_qpixmap_path(self):
        import mpynode._common.io.mpn_io as mpn_io
        import mpynode.ui.widgets.template_gallery_panel as mod
        orig_hdr               = mpn_io.load_mpn_header
        mpn_io.load_mpn_header = lambda p: {}
        calls                  = []
        orig_px                = mod.QPixmap

        class _SpyPixmap(orig_px):
            def __init__(self, *a, **k):
                if a:
                    calls.append(a[0])
                super(_SpyPixmap, self).__init__(*a, **k)

        mod.QPixmap = _SpyPixmap
        try:
            entry = _Entry("Has PNG", "mPyDeformer", preview_path="/tmp/p.png")
            scan  = lambda: [("templates", "/tmp", _Cat("templates", [entry]))]
            panel = self._panel(scan)
            leaf  = panel.tree.topLevelItem(0).child(0)
            panel.tree.setCurrentItem(leaf)
            self.assertIn("/tmp/p.png", calls)
            panel.deleteLater()
        finally:
            mpn_io.load_mpn_header = orig_hdr
            mod.QPixmap            = orig_px


@unittest.skipUnless(_QT, "Qt unavailable")
class TestRunSetupGate(unittest.TestCase):
    def test_menu_has_no_run_setup_action(self):
        # "Create + Run setup" was removed from the gallery entirely (button and
        # right-click action); it lives on the scene tab's menu now. It must be
        # absent even when the template genuinely HAS a setup.
        import mpynode._common.node_setups as node_setups
        import mpynode._common.io.mpn_io as mpn_io
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        orig_gate                  = node_setups.type_has_setup
        orig_hdr                   = mpn_io.load_mpn_header
        node_setups.type_has_setup = lambda nt: True
        mpn_io.load_mpn_header = lambda p: {
            "methods_source":
                "def setup(self, *a, **k):\n    return self.get_name()\n"}
        try:
            panel = NDTemplateGalleryPanel(parent=None, scan=_fake_scan)
            leaf  = panel.tree.topLevelItem(0).child(0).child(0)
            panel.tree.setCurrentItem(leaf)
            labels = [a.text() for a in
                      panel._build_tree_menu(panel._selected_entry()).actions()]
            self.assertIn("Create", labels)
            self.assertNotIn("Create + Run setup", labels)
            panel.deleteLater()
        finally:
            node_setups.type_has_setup = orig_gate
            mpn_io.load_mpn_header     = orig_hdr


@unittest.skipUnless(_QT, "Qt unavailable")
class TestRunDemoGate(unittest.TestCase):
    def test_create_demo_action_disabled_when_no_demo(self):
        import mpynode._common.io.mpn_io as mpn_io
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        orig_hdr               = mpn_io.load_mpn_header
        mpn_io.load_mpn_header = lambda p: {}
        try:
            panel = NDTemplateGalleryPanel(parent=None, scan=_fake_scan)
            leaf  = panel.tree.topLevelItem(0).child(0).child(0)
            panel.tree.setCurrentItem(leaf)
            acts = {a.text(): a for a in
                    panel._build_tree_menu(panel._selected_entry()).actions()}
            self.assertTrue(acts["Create"].isEnabled())
            self.assertFalse(acts["Create + Run demo"].isEnabled())
            self.assertFalse(panel.create_demo_btn.isEnabled())
            panel.deleteLater()
        finally:
            mpn_io.load_mpn_header = orig_hdr

    def test_create_demo_action_enabled_by_template_methods_source(self):
        import mpynode._common.io.mpn_io as mpn_io
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        orig_hdr = mpn_io.load_mpn_header
        mpn_io.load_mpn_header = lambda p: {
            "methods_source": "def demo(self):\n    return self.get_name()\n"}
        try:
            panel = NDTemplateGalleryPanel(parent=None, scan=_fake_scan)
            leaf  = panel.tree.topLevelItem(0).child(0).child(0)
            panel.tree.setCurrentItem(leaf)
            acts = {a.text(): a for a in
                    panel._build_tree_menu(panel._selected_entry()).actions()}
            self.assertTrue(acts["Create + Run demo"].isEnabled())
            self.assertTrue(panel.create_demo_btn.isEnabled())
            panel.deleteLater()
        finally:
            mpn_io.load_mpn_header = orig_hdr

    def test_demo_has_no_type_default(self):
        import mpynode._common.node_setups as node_setups
        import mpynode._common.io.mpn_io as mpn_io
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        orig_gate                  = node_setups.type_has_setup
        orig_hdr                   = mpn_io.load_mpn_header
        node_setups.type_has_setup = lambda nt: True
        mpn_io.load_mpn_header     = lambda p: {}
        try:
            panel = NDTemplateGalleryPanel(parent=None, scan=_fake_scan)
            leaf  = panel.tree.topLevelItem(0).child(0).child(0)
            panel.tree.setCurrentItem(leaf)
            acts = {a.text(): a for a in
                    panel._build_tree_menu(panel._selected_entry()).actions()}
            self.assertFalse(acts["Create + Run demo"].isEnabled())
            panel.deleteLater()
        finally:
            node_setups.type_has_setup = orig_gate
            mpn_io.load_mpn_header     = orig_hdr


@unittest.skipUnless(_QT, "Qt unavailable")
class TestFilter(unittest.TestCase):
    def _scan(self):
        a = _Entry("Sine Ripple", "mPyDeformer")
        b = _Entry("Two Bone IK", "mPyIkSolver")
        return [("templates", "/tmp", _Cat("templates", [_Cat("All", [a, b])]))]

    def test_filter_hides_nonmatching_leaves(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        panel   = NDTemplateGalleryPanel(parent=None, scan=self._scan)
        all_cat = panel.tree.topLevelItem(0).child(0)
        sine    = all_cat.child(0)
        ik      = all_cat.child(1)
        panel.filter_edit.setText("ripple")
        self.assertFalse(sine.isHidden())
        self.assertTrue(ik.isHidden())
        panel.filter_edit.setText("")
        self.assertFalse(ik.isHidden())
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestCreate(unittest.TestCase):
    def test_create_loads_full_payload_and_calls_on_create(self):
        import mpynode._common.io.mpn_io as mpn_io
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        orig_load              = mpn_io.load_mpn
        orig_hdr               = mpn_io.load_mpn_header
        mpn_io.load_mpn        = lambda p, **k: {"native_type": "mPyDeformer", "loaded": p}
        mpn_io.load_mpn_header = lambda p: {}
        captured               = []
        try:
            entry = _Entry("Sine Ripple", "mPyDeformer", mpn_path="/tmp/t.mpn")
            scan  = lambda: [("templates", "/tmp", _Cat("templates", [entry]))]
            panel = NDTemplateGalleryPanel(
                parent=None, on_create=lambda *a: captured.append(a), scan=scan
            )
            leaf = panel.tree.topLevelItem(0).child(0)
            panel.tree.setCurrentItem(leaf)
            panel._do_create(False)
            self.assertEqual(len(captured), 1)
            payload, native_type, run_setup, run_demo, demo_name = captured[0]
            self.assertEqual(payload["loaded"], "/tmp/t.mpn")
            self.assertEqual(native_type, "mPyDeformer")
            self.assertFalse(run_setup)
            self.assertFalse(run_demo)
            self.assertIsNone(demo_name)
            panel.deleteLater()
        finally:
            mpn_io.load_mpn        = orig_load
            mpn_io.load_mpn_header = orig_hdr

    def test_create_run_demo_sets_only_demo_flag(self):
        import mpynode._common.io.mpn_io as mpn_io
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        orig_load              = mpn_io.load_mpn
        orig_hdr               = mpn_io.load_mpn_header
        mpn_io.load_mpn        = lambda p, **k: {"native_type": "mPyDeformer", "loaded": p}
        mpn_io.load_mpn_header = lambda p: {}
        captured               = []
        try:
            entry = _Entry("Sine Ripple", "mPyDeformer", mpn_path="/tmp/t.mpn")
            scan  = lambda: [("templates", "/tmp", _Cat("templates", [entry]))]
            panel = NDTemplateGalleryPanel(
                parent=None, on_create=lambda *a: captured.append(a), scan=scan
            )
            leaf = panel.tree.topLevelItem(0).child(0)
            panel.tree.setCurrentItem(leaf)
            panel._do_create(run_demo=True)
            self.assertEqual(len(captured), 1)
            (_payload, _native_type, run_setup, run_demo,
             _demo_name) = captured[0]
            self.assertFalse(run_setup)
            self.assertTrue(run_demo)
            panel.deleteLater()
        finally:
            mpn_io.load_mpn        = orig_load
            mpn_io.load_mpn_header = orig_hdr

    def test_create_does_not_close_panel(self):
        # A permanent tab must NOT close on Create (the old dialog did).
        import mpynode._common.io.mpn_io as mpn_io
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        orig_load              = mpn_io.load_mpn
        orig_hdr               = mpn_io.load_mpn_header
        mpn_io.load_mpn        = lambda p, **k: {"native_type": "mPyDeformer", "loaded": p}
        mpn_io.load_mpn_header = lambda p: {}
        try:
            entry = _Entry("Sine Ripple", "mPyDeformer", mpn_path="/tmp/t.mpn")
            scan  = lambda: [("templates", "/tmp", _Cat("templates", [entry]))]
            panel = NDTemplateGalleryPanel(
                parent=None, on_create=lambda *a: None, scan=scan)
            closed      = []
            panel.close = lambda *a, **k: closed.append(1)
            leaf        = panel.tree.topLevelItem(0).child(0)
            panel.tree.setCurrentItem(leaf)
            panel._do_create(False)
            self.assertEqual(closed, [])
            panel.deleteLater()
        finally:
            mpn_io.load_mpn        = orig_load
            mpn_io.load_mpn_header = orig_hdr


@unittest.skipUnless(_QT, "Qt unavailable")
class TestRightPaneSplitter(unittest.TestCase):
    def test_right_pane_has_vertical_splitter(self):
        from mpynode.ui.qt_wrapper import QSplitter
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        panel     = NDTemplateGalleryPanel(parent=None, scan=lambda: [])
        splitters = panel.findChildren(QSplitter)
        self.assertTrue(
            any(s.orientation() == Qt.Vertical for s in splitters),
            "expected a vertical splitter dividing preview and description",
        )
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestGallerySplitterPersistence(unittest.TestCase):
    """The gallery's two divider positions (tree|preview and preview|desc) are
    saved on close and restored on the next session (via preferences)."""

    def _patched_prefs(self, store):
        """Point the lazily-imported get_pref/set_pref at an in-memory dict and
        return a restore() callback."""
        import mpynode.ui.preferences as prefs
        orig           = (prefs.get_pref, prefs.set_pref)
        prefs.get_pref = lambda k, d=None: store.get(k, d)
        prefs.set_pref = lambda k, v: store.__setitem__(k, v)

        def restore():
            prefs.get_pref, prefs.set_pref = orig
        return restore

    def _panel(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        return NDTemplateGalleryPanel(parent=None, scan=lambda: [])

    def test_save_layout_writes_current_sizes(self):
        store   = {}
        restore = self._patched_prefs(store)
        panel   = None
        try:
            panel = self._panel()
            panel.resize(800, 500)
            panel.show()
            _app.processEvents()
            panel._h_splitter.setSizes([500, 300])
            panel._right_split.setSizes([300, 180])
            _app.processEvents()
            panel.save_layout()
            self.assertEqual(
                store.get("layout_gallery_splitter"),
                [int(x) for x in panel._h_splitter.sizes()],
            )
            self.assertEqual(
                store.get("layout_gallery_right_splitter"),
                [int(x) for x in panel._right_split.sizes()],
            )
            self.assertTrue(all(v > 0 for v in store["layout_gallery_splitter"]))
        finally:
            restore()
            if panel is not None:
                panel.deleteLater()

    def test_restore_applies_saved_sizes(self):
        # Saved ratios are the OPPOSITE ordering of the built-in defaults
        # (right_split defaults to [360,240]), so if restore takes effect the
        # orderings flip.
        store = {
            "layout_gallery_splitter":       [700, 100],
            "layout_gallery_right_splitter": [100, 500],
        }
        restore = self._patched_prefs(store)
        panel   = None
        try:
            panel = self._panel()
            panel.resize(800, 640)
            panel.show()
            _app.processEvents()
            hs = [int(x) for x in panel._h_splitter.sizes()]
            vs = [int(x) for x in panel._right_split.sizes()]
            self.assertGreater(hs[0], hs[1], "tree pane should be the wider one")
            self.assertGreater(vs[1], vs[0], "description should be the taller one")
        finally:
            restore()
            if panel is not None:
                panel.deleteLater()

    def test_unshown_gallery_does_not_clobber_saved_layout(self):
        # A gallery parented into the non-current Templates tab is never shown,
        # so its splitters report Qt's non-zero placeholder sizes (NOT [0,0]).
        # save_layout must skip on _ever_shown, not on the sizes() sum.
        store = {
            "layout_gallery_splitter":       [700, 300],
            "layout_gallery_right_splitter": [400, 200],
        }
        restore = self._patched_prefs(store)
        panel   = None
        try:
            panel = self._panel()  # built (restore ran) but never show()n
            self.assertFalse(panel._ever_shown)
            # Seed non-zero placeholder-like sizes to prove sum>0 is NOT the gate
            # (the old guard would have written these and clobbered the prefs).
            panel._h_splitter.setSizes([45, 45])
            panel._right_split.setSizes([10, 10])
            panel.save_layout()
            self.assertEqual(store["layout_gallery_splitter"], [700, 300])
            self.assertEqual(store["layout_gallery_right_splitter"], [400, 200])
        finally:
            restore()
            if panel is not None:
                panel.deleteLater()

    def test_shown_gallery_marks_ever_shown_and_saves(self):
        # Complement: once actually shown, the panel saves its real sizes.
        store   = {}
        restore = self._patched_prefs(store)
        panel   = None
        try:
            panel = self._panel()
            panel.resize(800, 500)
            panel.show()
            _app.processEvents()
            self.assertTrue(panel._ever_shown)
            panel.save_layout()
            self.assertIn("layout_gallery_splitter", store)
            self.assertIn("layout_gallery_right_splitter", store)
        finally:
            restore()
            if panel is not None:
                panel.deleteLater()

    def test_gallery_layout_prefs_registered(self):
        from mpynode.ui.preferences import DEFAULT_PREFS
        self.assertIn("layout_gallery_splitter", DEFAULT_PREFS)
        self.assertIn("layout_gallery_right_splitter", DEFAULT_PREFS)


@unittest.skipUnless(_QT, "Qt unavailable")
class TestPreviewLabel(unittest.TestCase):
    def test_no_preview_renders_default_pixmap(self):
        from mpynode.ui.widgets.template_gallery_panel import _PreviewLabel
        lbl = _PreviewLabel()
        lbl.resize(200, 200)
        lbl.show_no_preview()
        self.assertEqual(lbl._mode, "none")
        pm = lbl.pixmap()
        self.assertIsNotNone(pm)
        self.assertFalse(pm.isNull())
        lbl.deleteLater()

    def test_no_preview_emboss_layers_render(self):
        from mpynode.ui.widgets.template_gallery_panel import _PreviewLabel
        lbl    = _PreviewLabel()
        layers = lbl._watermark_layers(120)
        self.assertIsNotNone(layers)
        light, dark = layers
        self.assertFalse(light.isNull())
        self.assertFalse(dark.isNull())
        lbl.deleteLater()

    def test_image_fits_and_rescales(self):
        from mpynode.ui.qt_wrapper import QPixmap
        from mpynode.ui.widgets.template_gallery_panel import _PreviewLabel
        src = QPixmap(400, 400)
        src.fill(Qt.black)
        lbl = _PreviewLabel()
        lbl.resize(200, 200)
        lbl.show_image(src)
        pm1 = lbl.pixmap()
        self.assertFalse(pm1.isNull())
        self.assertLessEqual(pm1.width(), 200)
        self.assertLessEqual(pm1.height(), 200)
        lbl.resize(100, 100)
        lbl._render()
        pm2 = lbl.pixmap()
        self.assertLessEqual(pm2.width(), 100)
        self.assertLessEqual(pm2.height(), 100)
        lbl.deleteLater()

    def test_pixmap_does_not_ratchet_minimum_width(self):
        # Regression: a non-text QLabel reports its pixmap size as
        # minimumSizeHint, and _render() scales the pixmap to the label -- so
        # the minimum width tracked the pane's CURRENT width and the splitter
        # could only ever grow the preview (a one-way ratchet). The label must
        # report a small, content-independent width floor.
        from mpynode.ui.qt_wrapper import QPixmap
        from mpynode.ui.widgets.template_gallery_panel import _PreviewLabel
        lbl = _PreviewLabel()
        lbl.resize(600, 400)
        src = QPixmap(1600, 1200)
        src.fill(Qt.black)
        lbl.show_image(src)
        # Must not demand anywhere near its ~600px rendered width.
        self.assertLessEqual(lbl.minimumSizeHint().width(), 8)
        # The branded no-preview frame (also a pixmap) must behave the same.
        lbl.show_no_preview()
        self.assertLessEqual(lbl.minimumSizeHint().width(), 8)
        # The height floor is preserved so the pane stays usable.
        self.assertGreaterEqual(lbl.minimumSizeHint().height(), 160)
        lbl.deleteLater()

    def test_height_floor_is_fixed_not_pixmap_driven(self):
        # Same one-way ratchet on the VERTICAL divider: the height floor must
        # be the fixed 160, never the scaled pixmap height. A TALL pixmap in a
        # SHORT label must still report 160.
        from mpynode.ui.qt_wrapper import QPixmap
        from mpynode.ui.widgets.template_gallery_panel import _PreviewLabel
        lbl = _PreviewLabel()
        lbl.resize(400, 160)
        tall = QPixmap(1200, 1600)
        tall.fill(Qt.black)
        lbl.show_image(tall)
        self.assertEqual(lbl.minimumSizeHint().height(), 160)
        lbl.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestVideoPreview(unittest.TestCase):
    def test_mp4_routes_to_video_widget(self):
        import mpynode._common.io.mpn_io as mpn_io
        import mpynode.ui.widgets.template_gallery_panel as mod
        orig_hdr                = mpn_io.load_mpn_header
        orig_start              = mod.start_video_preview
        orig_has                = mod.HAS_QT_MULTIMEDIA
        mpn_io.load_mpn_header  = lambda p: {}
        calls                   = []
        sentinel                = object()
        mod.start_video_preview = lambda path, w: (calls.append(path), sentinel)[1]
        mod.HAS_QT_MULTIMEDIA   = True
        try:
            entry = _Entry("Clip", "mPyDeformer", preview_path="/tmp/p.mp4")
            scan  = lambda: [("templates", "/tmp", _Cat("templates", [entry]))]
            panel = mod.NDTemplateGalleryPanel(parent=None, scan=scan)
            if panel.video_widget is None:
                self.skipTest("QVideoWidget unavailable in this build")
            leaf = panel.tree.topLevelItem(0).child(0)
            panel.tree.setCurrentItem(leaf)
            self.assertIn("/tmp/p.mp4", calls)
            self.assertIs(panel.preview_stack.currentWidget(), panel.video_widget)
            self.assertIs(panel._player, sentinel)
            panel.deleteLater()
        finally:
            mpn_io.load_mpn_header  = orig_hdr
            mod.start_video_preview = orig_start
            mod.HAS_QT_MULTIMEDIA   = orig_has

    def test_mp4_without_multimedia_falls_back_to_no_preview(self):
        import mpynode._common.io.mpn_io as mpn_io
        import mpynode.ui.widgets.template_gallery_panel as mod
        orig_hdr               = mpn_io.load_mpn_header
        orig_has               = mod.HAS_QT_MULTIMEDIA
        mpn_io.load_mpn_header = lambda p: {}
        mod.HAS_QT_MULTIMEDIA  = False
        try:
            entry = _Entry("Clip", "mPyDeformer", preview_path="/tmp/p.mp4")
            scan  = lambda: [("templates", "/tmp", _Cat("templates", [entry]))]
            panel = mod.NDTemplateGalleryPanel(parent=None, scan=scan)
            self.assertIsNone(panel.video_widget)
            leaf = panel.tree.topLevelItem(0).child(0)
            panel.tree.setCurrentItem(leaf)
            self.assertEqual(panel.preview_label._mode, "none")
            self.assertIs(panel.preview_stack.currentWidget(), panel.preview_label)
            panel.deleteLater()
        finally:
            mpn_io.load_mpn_header = orig_hdr
            mod.HAS_QT_MULTIMEDIA  = orig_has


@unittest.skipUnless(_QT, "Qt unavailable")
class TestSplitterHandles(unittest.TestCase):
    def test_splitters_use_separator_handles_with_spacing(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
            _SeparatorHandle,
            _SeparatorSplitter,
        )
        panel = NDTemplateGalleryPanel(parent=None, scan=lambda: [])
        seps  = panel.findChildren(_SeparatorSplitter)
        self.assertGreaterEqual(len(seps), 2)
        for s in seps:
            self.assertGreater(s.handleWidth(), 6)
            self.assertIsInstance(s.handle(1), _SeparatorHandle)
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestButtons(unittest.TestCase):
    def test_refresh_and_create_buttons_present(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        panel = NDTemplateGalleryPanel(parent=None, scan=lambda: [])
        self.assertTrue(hasattr(panel, "refresh_btn"))
        self.assertTrue(hasattr(panel, "create_btn"))
        # "Create + Run setup" affordance removed from the gallery entirely.
        self.assertFalse(hasattr(panel, "create_setup_btn"))
        self.assertTrue(hasattr(panel, "create_demo_btn"))
        panel.deleteLater()

    def test_no_cancel_button(self):
        # A permanent panel has nothing to close: the Cancel button is gone.
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        panel = NDTemplateGalleryPanel(parent=None, scan=lambda: [])
        self.assertFalse(hasattr(panel, "cancel_btn"))
        panel.deleteLater()

    def test_create_buttons_disabled_with_no_selection(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        panel = NDTemplateGalleryPanel(parent=None, scan=lambda: [])
        self.assertFalse(panel.create_btn.isEnabled())
        self.assertFalse(panel.create_demo_btn.isEnabled())
        panel.deleteLater()

    def test_create_enabled_for_buildable_disabled_for_category(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        panel   = NDTemplateGalleryPanel(parent=None, scan=_fake_scan)
        cat     = panel.tree.topLevelItem(0).child(0)
        leaf_ok = cat.child(0)
        panel.tree.setCurrentItem(leaf_ok)
        self.assertTrue(panel.create_btn.isEnabled())
        panel.tree.setCurrentItem(cat)
        self.assertFalse(panel.create_btn.isEnabled())
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestRefresh(unittest.TestCase):
    def test_refresh_button_rescans(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        calls = []

        def scan():
            calls.append(1)
            return []

        panel = NDTemplateGalleryPanel(parent=None, scan=scan)
        n     = len(calls)  # __init__ already scanned once
        self.assertGreaterEqual(n, 1)
        panel.refresh_btn.click()
        self.assertEqual(len(calls), n + 1)
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestStopVideo(unittest.TestCase):
    def test_stop_video_is_public_and_clears_player(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        panel   = NDTemplateGalleryPanel(parent=None, scan=lambda: [])
        stopped = []

        class _P:
            def stop(self):
                stopped.append(1)

        panel._player = _P()
        panel.stop_video()
        self.assertEqual(stopped, [1])
        self.assertIsNone(panel._player)
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestCategoryPreview(unittest.TestCase):
    def test_category_with_assets_renders(self):
        import mpynode._common.io.mpn_io as mpn_io
        import mpynode.ui.widgets.template_gallery_panel as mod
        orig_hdr               = mpn_io.load_mpn_header
        mpn_io.load_mpn_header = lambda p: {}
        calls                  = []
        orig_px                = mod.QPixmap

        class _SpyPixmap(orig_px):
            def __init__(self, *a, **k):
                if a:
                    calls.append(a[0])
                super(_SpyPixmap, self).__init__(*a, **k)

        mod.QPixmap = _SpyPixmap
        try:
            leaf     = _Entry("File", "mPyFile")
            cat      = _Cat("Textures", [leaf], preview_path="/tmp/c.png")
            scan     = lambda: [("templates", "/tmp", _Cat("templates", [cat]))]
            panel    = mod.NDTemplateGalleryPanel(parent=None, scan=scan)
            cat_item = panel.tree.topLevelItem(0).child(0)
            panel.tree.setCurrentItem(cat_item)
            self.assertIn("/tmp/c.png", calls)
            self.assertEqual(panel.meta_label.text(), "")
            panel.deleteLater()
        finally:
            mpn_io.load_mpn_header = orig_hdr
            mod.QPixmap            = orig_px

    def test_bare_category_stays_blank(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        leaf     = _Entry("File", "mPyFile")
        cat      = _Cat("Plain", [leaf])
        scan     = lambda: [("templates", "/tmp", _Cat("templates", [cat]))]
        panel    = NDTemplateGalleryPanel(parent=None, scan=scan)
        cat_item = panel.tree.topLevelItem(0).child(0)
        panel.tree.setCurrentItem(cat_item)
        self.assertIsNone(panel.preview_label._mode)
        self.assertEqual(panel.meta_label.text(), "")
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestHybridNode(unittest.TestCase):
    def test_buildable_folder_has_menu_and_children(self):
        import mpynode._common.io.mpn_io as mpn_io
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        orig                   = mpn_io.load_mpn_header
        mpn_io.load_mpn_header = lambda p: {}
        try:
            child  = _Entry("Advanced", "mPyDeformer")
            base   = _Entry("Sine Base", "mPyDeformer", children=[child])
            scan   = lambda: [("templates", "/tmp", _Cat("templates", [base]))]
            panel  = NDTemplateGalleryPanel(parent=None, scan=scan)
            hybrid = panel.tree.topLevelItem(0).child(0)
            self.assertIn("Sine Base", hybrid.text(0))
            self.assertEqual(hybrid.childCount(), 1)
            self.assertIn("Advanced", hybrid.child(0).text(0))
            panel.tree.setCurrentItem(hybrid)
            menu = panel._build_tree_menu(panel._selected_entry())
            self.assertIsNotNone(menu)
            self.assertIn("Create", [a.text() for a in menu.actions()])
            panel.deleteLater()
        finally:
            mpn_io.load_mpn_header = orig


def _collapse_scan():
    """A root with two collapsible category children, each holding one leaf."""
    basics   = _Cat("basics",    [_Entry("sine_ripple", "mPyDeformer")])
    advanced = _Cat("advanced",  [_Entry("dnet", "mPyNode")])
    root_cat = _Cat("templates", [basics, advanced])
    return [("templates", "/tmp/templates", root_cat)]


def _deep_scan():
    """A nested root so subtree scoping can be asserted: two categories, each
    holding sub-categories, each of those holding a leaf template. Shape::

        templates                 (search-root)
          basics                  (category)
            MPyDeformer           (sub-category)  -> sine_ripple (leaf)
            MPyFile               (sub-category)  -> brightness  (leaf)
          advanced                (category)
            dnet                  (sub-category)  -> dnet_demo   (leaf)
    """
    basics = _Cat("basics", [
        _Cat("MPyDeformer", [_Entry("sine_ripple", "mPyDeformer")]),
        _Cat("MPyFile", [_Entry("brightness", "mPyFile")]),
    ])
    advanced = _Cat("advanced", [
        _Cat("dnet", [_Entry("dnet_demo", "mPyNode")]),
    ])
    root_cat = _Cat("templates", [basics, advanced])
    return [("templates", "/tmp/templates", root_cat)]


@unittest.skipUnless(_QT, "Qt unavailable")
class TestGalleryStartsCollapsed(unittest.TestCase):
    """The template browser opens with the search-root expanded but every
    category collapsed (so the user gets a tidy list of category headers)."""

    def _panel(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        return NDTemplateGalleryPanel(parent=None, scan=_collapse_scan)

    def test_root_expanded_categories_collapsed(self):
        panel = self._panel()
        root  = panel.tree.topLevelItem(0)
        self.assertTrue(root.isExpanded(), "search-root should be expanded")
        basics   = root.child(0)
        advanced = root.child(1)
        self.assertEqual(basics.text(0), "basics")
        self.assertEqual(advanced.text(0), "advanced")
        self.assertFalse(basics.isExpanded(), "categories must start collapsed")
        self.assertFalse(advanced.isExpanded(), "categories must start collapsed")
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestGalleryShiftClickExpandAll(unittest.TestCase):
    """Shift-clicking a folder recursively expands / collapses ONLY that
    folder's own subtree -- siblings and ancestors keep their state (the user's
    requirement: shift-collapsing "basics" must not roll the tree up to the
    "templates" root, and shift-expanding "basics" must not touch "advanced")."""

    def _panel(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        return NDTemplateGalleryPanel(parent=None, scan=_deep_scan)

    def _nodes(self, panel):
        root     = panel.tree.topLevelItem(0)  # templates (search-root)
        basics   = root.child(0)               # basics       (category)
        advanced = root.child(1)               # advanced     (category)
        b_def    = basics.child(0)             # basics/MPyDeformer (sub-category)
        b_file   = basics.child(1)             # basics/MPyFile     (sub-category)
        a_dnet   = advanced.child(0)           # advanced/dnet      (sub-category)
        return root, basics, advanced, b_def, b_file, a_dnet

    def test_shift_expand_is_recursive_within_subtree_only(self):
        from mpynode.ui.widgets.tree_expand import toggle_all_from
        panel = self._panel()
        root, basics, advanced, b_def, b_file, a_dnet = self._nodes(panel)
        self.assertFalse(basics.isExpanded())   # collapsed by default
        # Shift-expand basics -> basics AND every descendant open.
        self.assertTrue(toggle_all_from(panel.tree, basics))
        self.assertTrue(basics.isExpanded())
        self.assertTrue(b_def.isExpanded(), "nested sub-category expands too")
        self.assertTrue(b_file.isExpanded())
        # ...but advanced's subtree is left untouched.
        self.assertFalse(advanced.isExpanded(), "sibling category untouched")
        self.assertFalse(a_dnet.isExpanded())
        panel.deleteLater()

    def test_shift_collapse_scopes_to_subtree_not_root(self):
        from mpynode.ui.widgets.tree_expand import toggle_all_from
        panel = self._panel()
        root, basics, advanced, b_def, b_file, a_dnet = self._nodes(panel)
        # Open basics' whole subtree first.
        toggle_all_from(panel.tree, basics)
        self.assertTrue(basics.isExpanded())
        self.assertTrue(b_def.isExpanded())
        # Shift-collapse basics -> basics + descendants collapse...
        self.assertTrue(toggle_all_from(panel.tree, basics))
        self.assertFalse(basics.isExpanded())
        self.assertFalse(b_def.isExpanded(), "descendants collapse too")
        self.assertFalse(b_file.isExpanded())
        # ...and CRUCIALLY the root stays expanded -- the bug report was that
        # collapsing a folder rolled all the way up to "templates".
        self.assertTrue(root.isExpanded(), "root must NOT collapse")
        panel.deleteLater()

    def test_shift_on_subcategory_scopes_to_that_subcategory(self):
        from mpynode.ui.widgets.tree_expand import toggle_all_from
        panel = self._panel()
        root, basics, advanced, b_def, b_file, a_dnet = self._nodes(panel)
        basics.setExpanded(True)   # open basics one level (plain-expand)
        self.assertFalse(b_def.isExpanded())
        # Shift-expand only the MPyDeformer sub-category.
        self.assertTrue(toggle_all_from(panel.tree, b_def))
        self.assertTrue(b_def.isExpanded())
        # Its sibling sub-category MPyFile is untouched.
        self.assertFalse(b_file.isExpanded(), "sibling sub-category untouched")
        panel.deleteLater()

    def test_toggle_all_from_is_noop_on_leaf(self):
        from mpynode.ui.widgets.tree_expand import toggle_all_from
        panel = self._panel()
        root, basics, advanced, b_def, b_file, a_dnet = self._nodes(panel)
        leaf = b_def.child(0)                    # the sine_ripple template
        self.assertEqual(leaf.childCount(), 0)
        self.assertFalse(toggle_all_from(panel.tree, leaf))
        panel.deleteLater()

    def test_toggle_all_from_is_noop_on_none(self):
        from mpynode.ui.widgets.tree_expand import toggle_all_from
        panel = self._panel()
        self.assertFalse(toggle_all_from(panel.tree, None))
        panel.deleteLater()

    # -- end-to-end event plumbing (shift gating + hit test) --------------
    def _press(self, tree, item, shift):
        from mpynode.ui import qt_wrapper
        from mpynode.ui.qt_wrapper import Qt
        rect = tree.visualItemRect(item)
        if rect.isNull() or rect.width() == 0 or rect.height() == 0:
            self.skipTest("no item geometry available headless")
        pt   = rect.center()
        mods = Qt.ShiftModifier if shift else Qt.NoModifier
        if qt_wrapper.QT_BINDING == "PySide6":
            from PySide6.QtCore import QEvent, QPointF
            from PySide6.QtGui import QMouseEvent
            ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(pt),
                             Qt.LeftButton, Qt.LeftButton, mods)
        else:
            from PySide2.QtCore import QEvent
            from PySide2.QtGui import QMouseEvent
            ev = QMouseEvent(QEvent.MouseButtonPress, pt,
                             Qt.LeftButton, Qt.LeftButton, mods)
        QApplication.sendEvent(tree.viewport(), ev)

    def test_shift_left_click_expands_only_its_own_subtree(self):
        panel = self._panel()
        panel.tree.resize(320, 600)
        QApplication.processEvents()
        root, basics, advanced, b_def, b_file, a_dnet = self._nodes(panel)
        self.assertFalse(basics.isExpanded())
        self._press(panel.tree, basics, shift=True)   # may skipTest w/o geom
        self.assertTrue(basics.isExpanded(), "shift-click expands basics")
        self.assertTrue(b_def.isExpanded(), "...recursively into its subtree")
        self.assertFalse(advanced.isExpanded(), "sibling advanced untouched")
        panel.deleteLater()

    def test_plain_left_click_header_does_not_recurse(self):
        panel = self._panel()
        panel.tree.resize(320, 600)
        QApplication.processEvents()
        root, basics, advanced, b_def, b_file, a_dnet = self._nodes(panel)
        self.assertFalse(basics.isExpanded())
        self._press(panel.tree, basics, shift=False)  # may skipTest w/o geom
        # A plain click must NOT trigger the recursive expand (our filter only
        # fires on Shift); the nested sub-category stays collapsed regardless of
        # whatever Qt does with the top row's own selection/one-level toggle.
        self.assertFalse(b_def.isExpanded(),
                         "plain click must not recursively expand")
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestGalleryFilterRevealsMatches(unittest.TestCase):
    """With categories collapsed by default, typing in the Filter box must
    EXPAND the ancestors of a match so it is actually visible, and clearing the
    box must restore the collapsed default."""

    def _panel(self):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        return NDTemplateGalleryPanel(parent=None, scan=_collapse_scan)

    def test_filter_expands_ancestors_of_match(self):
        panel = self._panel()
        root  = panel.tree.topLevelItem(0)
        basics, advanced = root.child(0), root.child(1)
        self.assertFalse(basics.isExpanded())  # collapsed by default

        panel._apply_filter("ripple")          # matches basics/sine_ripple only
        self.assertTrue(basics.isExpanded(),
                        "the matching category must be expanded so it shows")
        self.assertFalse(basics.isHidden())
        self.assertFalse(basics.child(0).isHidden())  # the match leaf
        self.assertTrue(advanced.isHidden())          # no match -> hidden

        panel._apply_filter("")                       # clear -> restore default
        self.assertTrue(root.isExpanded())
        self.assertFalse(basics.isExpanded(), "cleared filter re-collapses cats")
        self.assertFalse(advanced.isExpanded())
        self.assertFalse(basics.isHidden())
        self.assertFalse(advanced.isHidden())
        panel.deleteLater()

    def test_filter_with_no_match_hides_all_categories(self):
        panel = self._panel()
        root  = panel.tree.topLevelItem(0)
        panel._apply_filter("zzz_no_such_template")
        for i in range(root.childCount()):
            self.assertTrue(root.child(i).isHidden())
        panel.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestRevealInFileManager(unittest.TestCase):
    """Right-click -> "Reveal in Finder" (platform-named) on any gallery row.
    Offered for CATEGORIES too, which have no create action, so a pure category
    must stop returning a null menu."""

    def _panel(self, scan):
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        return NDTemplateGalleryPanel(parent=None, scan=scan)

    def _tmpdir(self):
        import shutil
        import tempfile
        d = tempfile.mkdtemp(prefix="ndgallery_")
        self.addCleanup(shutil.rmtree, d, True)
        return d

    @staticmethod
    def _label():
        from mpynode.ui.editor_launch import reveal_label
        return reveal_label()

    def _find(self, menu, text):
        for a in menu.actions():
            if a.text() == text:
                return a
        return None

    def test_entry_menu_offers_an_enabled_reveal(self):
        folder = self._tmpdir()
        entry = _Entry("Sine Ripple", "mPyDeformer",
                       mpn_path=os.path.join(folder, "template.mpn"))
        entry.folder = folder
        panel        = self._panel(lambda: [])
        act          = self._find(panel._build_tree_menu(entry), self._label())
        self.assertIsNotNone(act, "template rows must offer a reveal action")
        self.assertTrue(act.isEnabled())
        panel.deleteLater()

    def test_category_gets_a_menu_even_with_no_create_action(self):
        folder       = self._tmpdir()
        cat          = _Cat("Deformers", [])
        cat.abs_path = folder
        panel        = self._panel(lambda: [])
        menu         = panel._build_tree_menu(cat)
        self.assertIsNotNone(
            menu, "a category used to return None -- it now reveals")
        self.assertIsNone(self._find(menu, "Create"),
                          "a category is not buildable")
        act = self._find(menu, self._label())
        self.assertIsNotNone(act)
        self.assertTrue(act.isEnabled())
        panel.deleteLater()

    def test_reveal_is_disabled_when_nothing_backs_the_row(self):
        entry = _Entry("Ghost", "mPyNode",
                       mpn_path="/nonexistent/ghost/template.mpn")
        entry.folder = "/nonexistent/ghost"
        panel        = self._panel(lambda: [])
        act          = self._find(panel._build_tree_menu(entry), self._label())
        self.assertIsNotNone(act, "the action is shown, explaining why")
        self.assertFalse(act.isEnabled())
        panel.deleteLater()

    def test_triggering_reveals_the_templates_own_folder(self):
        from mpynode.ui.widgets import template_gallery_panel as tgp

        folder = self._tmpdir()
        entry = _Entry("Sine Ripple", "mPyDeformer",
                       mpn_path=os.path.join(folder, "template.mpn"))
        entry.folder = folder

        seen                       = []
        orig                       = tgp.reveal_in_file_manager
        tgp.reveal_in_file_manager = lambda p: seen.append(p) or (True, None)
        self.addCleanup(setattr, tgp, "reveal_in_file_manager", orig)

        panel = self._panel(lambda: [])
        self._find(panel._build_tree_menu(entry), self._label()).trigger()
        # the FOLDER, not the .mpn -- revealing the folder shows the template's
        # preview / description / payload together.
        self.assertEqual(seen, [folder])
        panel.deleteLater()

    def test_category_falls_back_to_abs_path_not_a_missing_folder(self):
        folder       = self._tmpdir()
        cat          = _Cat("Deformers", [])
        cat.abs_path = folder
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )
        self.assertEqual(NDTemplateGalleryPanel._reveal_path(cat), folder)


if __name__ == "__main__":
    unittest.main()
