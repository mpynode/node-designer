"""TallTabBar — a horizontal (North/South) QTabBar whose tabs are 1.5x taller.

The Node Designer's horizontal tab strips (Scene | Attributes | Variables, the
Log | Watch | Profile tools panel, the per-node editor's document tabs, and the
Init | Compute | ... inner tier tabs) read as thin default-height bars. This
widget makes them ~1.5x taller so they are easier to hit and more noticeable —
the North-bar analog of the West mode tabs' 1.5x *width* (see
``mpynode_designer._WideTabBar``).

For a North/South bar, ``tabSizeHint().height()`` is the bar THICKNESS (tab
height); ``.width()`` is length along the bar. We scale ONLY the height.

``taller()`` is the single source of truth for the scale factor and is reused by
``script_tab.NDEditorTabBar`` (which needs the same height on its own bespoke
QTabBar subclass rather than swapping in ``TallTabBar``).

GOTCHAS
-------
* ``QTabWidget.setTabBar(bar)`` DESTROYS tabs already added, so a custom bar MUST
  be installed BEFORE the first ``addTab`` at each construction site.
* Keep a Python ref to the installed bar (e.g. ``self._panel_tab_bar = ...``) or
  PySide may GC the wrapper and drop the ``tabSizeHint`` override.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import QSize, QTabBar

# Matches the West mode-tabs widen factor.
TAB_HEIGHT_SCALE = 1.5


def taller(size):
    """Return ``size`` with its height scaled by ``TAB_HEIGHT_SCALE`` (width kept).

    Single source of truth for the North-bar thickness bump so every horizontal
    tab strip (including the bespoke ``NDEditorTabBar``) scales identically.
    """
    return QSize(size.width(), int(size.height() * TAB_HEIGHT_SCALE))


class TallTabBar(QTabBar):
    """North/South QTabBar whose tabs are ``TAB_HEIGHT_SCALE`` x taller."""

    def tabSizeHint(self, index):
        return taller(super(TallTabBar, self).tabSizeHint(index))


def make_tabs_tall(tab_widget):
    """Install a :class:`TallTabBar` on ``tab_widget`` and return it.

    MUST be called BEFORE any ``addTab`` (``setTabBar`` wipes existing tabs).
    The caller should keep the returned bar on ``self`` to avoid PySide GC.
    """
    bar = TallTabBar(tab_widget)
    tab_widget.setTabBar(bar)
    return bar


class UniformWidthTabBar(TallTabBar):
    """North QTabBar, ``TAB_HEIGHT_SCALE`` x taller, whose tabs are all as wide
    as the WIDEST label. ``Init | Compute | Viewport | OSL | API`` otherwise
    renders as five different-width buttons, which reads as ragged; every tab
    taking the widest tab's width makes the strip a regular row.

    Distinct from :class:`EqualWidthTabBar`, which divides the BAR's width by
    the tab count and therefore only works standalone -- a ``QTabWidget`` sizes
    its internal bar to the tabs' own hints, so the bar never sees the full
    container width. This class maxes the natural hints instead, so it is safe
    under ``QTabWidget.setTabBar``.

    BUDGETED. Equalising is not free: on the mPyFile strip the natural widths
    are Init 47 / Compute 85 / Viewport 81 / OSL 53 / API 48 = 314px, and five
    tabs at the widest costs 425px -- 85px more than the 340px the bar gets at
    the shipped 580px centre pane. Past the bar's width a QTabBar scrolls or
    elides, and the strip is the one widget whose whole job is saying WHERE YOU
    ARE, so it must never truncate its own labels
    (``test_script_area_wiring.test_widest_strip_still_fits_without_scrolling``).
    The extra pixels are therefore spent only when there is room; otherwise the
    natural widths stand, which by definition fit.

    Budgeted against the PARENT's width, never ``self.width()``. A QTabWidget
    sizes its bar from the very hints this returns, so measuring the bar makes
    the test circular and one-way: fall back once and the bar shrinks to the
    natural total, which can never again reach the equal total, so a window
    wide enough to afford equal tabs still renders ragged ones. The parent's
    width comes from the splitter instead, so it is a real budget. A bar with
    no parent (standalone use) has nothing else to ask, so it measures itself.
    """

    def tabSizeHint(self, index):
        s      = super(UniformWidthTabBar, self).tabSizeHint(index)   # 1.5x taller
        widest = s.width()
        for i in range(self.count()):
            if i != index:
                # QTabBar's own hint: taller() never touches width, so the raw
                # base width is the natural label width for tab i.
                widest = max(widest, QTabBar.tabSizeHint(self, i).width())
        parent = self.parentWidget()
        # Before the first layout there is no width to budget against; take the
        # equal widths then and let the resize re-ask.
        avail = parent.width() if parent is not None else self.width()
        if avail > 0 and widest * self.count() > avail:
            return s
        return QSize(widest, s.height())


def make_tabs_uniform(tab_widget):
    """Install a :class:`UniformWidthTabBar` on ``tab_widget`` and return it.

    Same contract as :func:`make_tabs_tall` (call BEFORE any ``addTab``; keep
    the returned ref), plus equal tab widths."""
    bar = UniformWidthTabBar(tab_widget)
    tab_widget.setTabBar(bar)
    return bar


class EqualWidthTabBar(TallTabBar):
    """North QTabBar that is ``TAB_HEIGHT_SCALE`` x taller AND equal-width: every
    tab claims an equal share of the bar (``bar width / tab count``), so N tabs
    split the full width evenly — two tabs become two exact halves. The label
    stays centered (QTabBar's default), so a widened tab centers its text.

    Use this as a STANDALONE bar (placed directly in a layout, driving a
    ``QStackedWidget``), NOT via ``QTabWidget.setTabBar``: a QTabWidget sizes its
    internal bar to the tabs' own sizeHint (left-bunched), which starved this of
    the full width. In a plain layout the bar's default ``Preferred`` horizontal
    policy stretches it to the full container width, so ``self.width()`` is the
    real editor width and ``width() / count`` yields true halves.

    Overriding ``tabSizeHint`` (rather than relying on the fickle, style-
    dependent ``QTabBar.expanding`` property) is what guarantees the EQUAL split.
    Before the bar has been laid out (``width() <= 0``) it falls back to the
    natural taller size; ``QTabBar`` re-runs ``tabSizeHint`` on every resize, so
    the halves track the editor width as it changes.
    """

    def tabSizeHint(self, index):
        s = super(EqualWidthTabBar, self).tabSizeHint(index)  # 1.5x taller
        n = max(1, self.count())
        w = self.width()
        if w <= 0:
            return s
        return QSize(w // n, s.height())
