"""One painter for the embossed mPyNode logo.

The script editor with no tab open and the gallery preview with no preview
file both show the same relief, painted by ``logo_relief.paint_relief``. These
tests pin the painter itself and that both surfaces actually go through it."""
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
    _QT = True
except Exception:  # pragma: no cover - Qt missing
    _QT = False


def setUpModule():
    try:
        from tests._setup import standalone_init
        standalone_init()
    except Exception:
        pass


def _painted(size, caption=None, color=None):
    from mpynode.ui.qt_wrapper import QPainter, QPixmap, Qt
    from mpynode.ui.widgets.logo_relief import paint_relief
    canvas = QPixmap(*size)
    canvas.fill(Qt.transparent)
    p = QPainter(canvas)
    try:
        painted = paint_relief(p, canvas.rect(), caption=caption,
                               caption_color=color)
    finally:
        p.end()
    return painted, canvas.toImage()


def _rows_touched(image, other=None):
    """Rows holding a non-transparent pixel, or -- given ``other`` -- rows
    where the two images differ."""
    rows = []
    for y in range(image.height()):
        for x in range(image.width()):
            if other is None:
                hit = image.pixelColor(x, y).alpha() > 0
            else:
                hit = image.pixelColor(x, y) != other.pixelColor(x, y)
            if hit:
                rows.append(y)
                break
    return rows


@unittest.skipUnless(_QT, "Qt unavailable")
class TestReliefLayers(unittest.TestCase):
    def test_layers_fit_the_side_and_are_cached(self):
        from mpynode.ui.widgets.logo_relief import relief_layers
        layers = relief_layers(120)
        self.assertIsNotNone(layers)
        light, dark = layers
        self.assertFalse(light.isNull())
        self.assertLessEqual(max(light.width(), light.height()), 120)
        self.assertEqual(light.size(), dark.size())
        self.assertIs(relief_layers(120), layers)

    def test_no_room_means_no_layers(self):
        from mpynode.ui.widgets.logo_relief import relief_layers
        self.assertIsNone(relief_layers(0))


@unittest.skipUnless(_QT, "Qt unavailable")
class TestPaintRelief(unittest.TestCase):
    def test_bare_relief_marks_the_canvas(self):
        painted, image = _painted((300, 200))
        self.assertTrue(painted)
        self.assertTrue(_rows_touched(image))

    def test_caption_sits_beneath_the_logo_never_across_it(self):
        from mpynode.ui.qt_wrapper import QColor, QRect
        from mpynode.ui.widgets.logo_relief import RELIEF_SCALE, relief_layers
        _, bare = _painted((300, 200))
        _, captioned = _painted((300, 200), "MPyLocator", QColor(255, 255, 255))
        changed = _rows_touched(bare, captioned)
        self.assertTrue(changed, "caption drew nothing")
        # The logo's bottom edge, shadow offset included: the caption may
        # only change rows below it.
        side = int(min(300, 200) * RELIEF_SCALE)
        light, _dark = relief_layers(side)
        cy = QRect(0, 0, 300, 200).center().y() - light.height() // 2
        logo_bottom = cy + light.height() + max(1, side // 180)
        self.assertGreaterEqual(min(changed), logo_bottom)


@unittest.skipUnless(_QT, "Qt unavailable")
class TestBothSurfacesUseIt(unittest.TestCase):
    def test_gallery_frame_is_the_shared_relief(self):
        from mpynode.ui.qt_wrapper import QPalette
        from mpynode.ui.widgets.template_gallery_panel import _PreviewLabel
        lbl = _PreviewLabel()
        lbl.resize(300, 200)
        lbl.show_no_preview("MPyLocator")
        _, expected = _painted(
            (300, 200), "MPyLocator",
            lbl.palette().color(QPalette.WindowText))
        self.assertEqual(lbl.pixmap().toImage(), expected)
        # No caption: the bare relief, byte for byte what the editor paints.
        lbl.show_no_preview()
        _, bare = _painted((300, 200))
        self.assertEqual(lbl.pixmap().toImage(), bare)
        lbl.deleteLater()

    def test_empty_script_editor_paints_it(self):
        import mpynode.ui.widgets.script_tab as mod
        calls = []
        orig = mod.paint_relief
        mod.paint_relief = lambda painter, rect, **kw: calls.append(rect) or True
        try:
            w = mod.NDScriptTabWidget()
            w.resize(300, 200)
            w.grab()  # forces a paint with no tab open
        finally:
            mod.paint_relief = orig
        self.assertTrue(calls, "empty editor did not paint the relief")
        self.assertEqual(calls[-1].size(), w.rect().size())
        w.deleteLater()


if __name__ == "__main__":
    unittest.main()
