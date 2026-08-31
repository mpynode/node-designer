"""WideTabBar — a vertical (West/East) QTabBar whose tabs are 1.5x wider.

The Node Designer's vertical tab strips read as thin default-width bars. The
window's top-level Workspace | Templates mode switch widens its West tabs so
they are a more noticeable target; the per-node editor's Expressions | Script
switch mirrors that exact look for consistency. This widget is the single source
of truth for that WIDTH bump — the West-bar analog of ``tall_tab_bar.TallTabBar``
(which bumps HEIGHT for North/South strips).

For a West/East bar, ``tabSizeHint().width()`` is the bar THICKNESS (how far it
juts out); ``.height()`` is the tab's length along the bar. We scale ONLY the
width — widening the tabs without lengthening them (verified ×1.5 under both
PySide2 36→54 and PySide6 31→46).

GOTCHAS
-------
* ``QTabWidget.setTabBar(bar)`` DESTROYS tabs already added, so a custom bar MUST
  be installed BEFORE the first ``addTab`` at each construction site.
* Keep a Python ref to the installed bar (e.g. ``self._mode_tab_bar = ...``) or
  PySide may GC the wrapper and drop the ``tabSizeHint`` override.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import QSize, QTabBar

# Matches the North-bar TAB_HEIGHT_SCALE.
TAB_WIDTH_SCALE = 1.5


def wider(size):
    """Return ``size`` with its width scaled by ``TAB_WIDTH_SCALE`` (height kept).

    Single source of truth for the West-bar thickness bump so every vertical tab
    strip (the mode tabs AND the editor's Expressions | Script switch) scales
    identically.
    """
    return QSize(int(size.width() * TAB_WIDTH_SCALE), size.height())


class WideTabBar(QTabBar):
    """West/East QTabBar whose tabs are ``TAB_WIDTH_SCALE`` x wider."""

    def tabSizeHint(self, index):
        return wider(super(WideTabBar, self).tabSizeHint(index))


def make_tabs_wide(tab_widget):
    """Install a :class:`WideTabBar` on ``tab_widget`` and return it.

    MUST be called BEFORE any ``addTab`` (``setTabBar`` wipes existing tabs).
    The caller should keep the returned bar on ``self`` to avoid PySide GC.
    """
    bar = WideTabBar(tab_widget)
    tab_widget.setTabBar(bar)
    return bar
