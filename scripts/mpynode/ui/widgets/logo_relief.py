"""The embossed mPyNode logo, painted by one function for every empty surface.

The script editor shows it when no node tab is open; the template gallery
shows it when the selected row ships no preview. Both paint through
:func:`paint_relief`, so the two surfaces cannot drift apart: same icon, same
scale, same highlight and shadow, same offsets.

The relief is two silhouettes of the logo -- one white, one black -- drawn at
a few percent opacity and offset by a pixel or two in opposite directions.
Where they overlap the panel gray barely changes; along the edges the
highlight sits up-left and the shadow down-right, and the shape reads as
pressed into the panel. The panel colour itself is never painted: whatever
sits underneath shows through, which is what keeps the gallery's frame
identical to the editor's.
"""

from __future__ import annotations

import os

from mpynode.ui.qt_wrapper import (
    QColor, QFont, QFontMetrics, QPainter, QPixmap, QRect, Qt,
)
from mpynode.ui.widgets.icons import icon_path

RELIEF_ICON = "mpynode_hr.png"
RELIEF_SCALE = 0.55            # fraction of the area's shorter side
RELIEF_HILIGHT_ALPHA = 0.05
RELIEF_SHADOW_ALPHA = 0.06

# Optional caption under the logo (the gallery's node class): the caller's
# text colour at this opacity, at the size Qt gives a markdown H1 -- so it
# matches the title of the description shown beneath the frame. It never
# overlaps the logo, so the relief above it is exactly the editor's.
CAPTION_ALPHA = 0.35
CAPTION_TITLE_FACTOR = 2.0     # Qt markdown H1: FontSizeAdjustment +3 = 2x body
CAPTION_GAP = 0.08             # logo-to-caption space, fraction of the logo side

_base: QPixmap | None = None
_layers: dict[int, tuple[QPixmap, QPixmap]] = {}


def _tint(pix: QPixmap, color: QColor) -> QPixmap:
    """A solid-colour silhouette of ``pix`` that keeps its alpha shape."""
    out = QPixmap(pix.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    try:
        p.drawPixmap(0, 0, pix)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(out.rect(), color)
    finally:
        p.end()
    return out


def _caption_font(base: QFont, room: int) -> QFont:
    """``base`` (the surface's font) at markdown-title size, shrunk only when
    ``room`` px cannot hold one line of it."""
    font = QFont(base)
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * CAPTION_TITLE_FACTOR)
    else:
        font.setPixelSize(max(1, int(font.pixelSize() * CAPTION_TITLE_FACTOR)))
    height = QFontMetrics(font).height()
    if 0 < room < height:
        if font.pointSizeF() > 0:
            font.setPointSizeF(max(1.0, font.pointSizeF() * room / height))
        else:
            font.setPixelSize(max(1, int(font.pixelSize() * room / height)))
    return font


def relief_base() -> QPixmap:
    """The source logo, loaded once; an empty pixmap when the icon is absent."""
    global _base
    if _base is None:
        path = icon_path(RELIEF_ICON)
        _base = QPixmap(path) if os.path.exists(path) else QPixmap()
    return _base


def relief_layers(side: int) -> tuple[QPixmap, QPixmap] | None:
    """``(light, dark)`` silhouettes scaled to fit ``side`` px, cached per
    size; ``None`` when there is no icon or no room."""
    base = relief_base()
    if base.isNull() or side <= 0:
        return None
    cached = _layers.get(side)
    if cached is None:
        scaled = base.scaled(
            side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        cached = (
            _tint(scaled, QColor(255, 255, 255)),
            _tint(scaled, QColor(0, 0, 0)),
        )
        _layers[side] = cached
    return cached


def paint_relief(painter: QPainter, rect: QRect, caption: str | None = None,
                 caption_color: QColor | None = None) -> bool:
    """Paint the relief centred in ``rect`` with ``painter``.

    ``caption`` (a node class such as ``MPyLocator``) is set quietly beneath
    the logo in ``caption_color``, at the size a markdown title gets; the
    logo itself sits exactly where the caption-less relief would, so every
    surface lines up. Returns ``True`` when something was painted."""
    side = int(min(rect.width(), rect.height()) * RELIEF_SCALE)
    layers = relief_layers(side)
    if layers is None:
        return False
    light, dark = layers
    cx = rect.center().x() - light.width() // 2
    cy = rect.center().y() - light.height() // 2
    # Two offset silhouettes read as a relief pressed into the panel gray.
    d = max(1, side // 180)
    painter.save()
    try:
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setOpacity(RELIEF_SHADOW_ALPHA)
        painter.drawPixmap(cx + d, cy + d, dark)
        painter.setOpacity(RELIEF_HILIGHT_ALPHA)
        painter.drawPixmap(cx - d, cy - d, light)
        if caption:
            top = cy + light.height() + d + int(side * CAPTION_GAP)
            box = QRect(rect.left(), top, rect.width(), rect.bottom() + 1 - top)
            if box.height() > 0:
                painter.setFont(_caption_font(painter.font(), box.height()))
                painter.setOpacity(CAPTION_ALPHA)
                painter.setPen(caption_color or QColor(255, 255, 255))
                painter.drawText(box, Qt.AlignHCenter | Qt.AlignTop,
                                 str(caption))
    finally:
        painter.restore()
    return True
