"""Per-node-type icons + per-attr-type colors.

Generates letter-pill QPixmap icons on the fly for each native_type so we
don't need shipped image files. Same approach for per-attr-type
foreground colors on user attr items.

Both maps mirror the original ATTR_COLOR_MAP.
"""

from __future__ import annotations

import os

from mpynode.ui.qt_wrapper import QBrush, QColor, QFont, QIcon, QPainter, QPixmap, Qt


# ===========================================================================
# Bundled icon files (MPyNode/icons/)
# ===========================================================================
#
# Single source of truth for the shipped icon assets. This module sits four
# levels below the repo root (widgets -> ui -> mpynode -> scripts).

_ICONS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "icons")
)


def icon_path(name: str) -> str:
    """Return the absolute path to a bundled icon file under MPyNode/icons/.

    Used so the shelf button, window icon, etc. can reference the shipped
    PNGs by name without each caller hand-rolling a relative path. Does not
    check existence -- callers that need a fallback should guard with
    ``os.path.exists()``.
    """
    return os.path.join(_ICONS_DIR, name)


# ===========================================================================
# Per-node-type letter pills
# ===========================================================================
#
# One SINGLE-letter white glyph per native_type, on a distinct-coloured
# circular pill. Cached so we don't repaint on every tree refresh.

NODE_TYPE_LETTERS: dict[str, str] = {
    "mPyNode": "N",
    "mPyConstraint": "C",
    "mPyIkSolver": "I",
    "mPyLocator": "L",
    "mPyDeformer": "D",
    "mPyTransform": "T",
    "mPyMesh": "P",
    "mPySkinCluster": "K",
    "mPyBlendShape": "B",
    "mPyNurbsCurve": "U",        # cUrve; P is taken by mPyMesh
    "mPyNurbsSurface": "R",      # suRface
    "mPyFile": "M",              # Map, its role in a shading graph
}

NODE_TYPE_COLORS: dict[str, tuple[int, int, int]] = {
    "mPyNode": (110, 160, 230),  # blue
    "mPyConstraint": (200, 100, 60),  # rust
    "mPyIkSolver": (190, 100, 220),  # purple
    "mPyLocator": (170, 170, 170),  # grey
    "mPyDeformer": (60, 190, 200),  # teal
    "mPyTransform": (220, 130, 60),  # amber
    "mPyMesh": (90, 200, 170),  # sea-foam (geometry generator)
    "mPySkinCluster": (240, 140, 200),  # rose (skin deformer)
    "mPyBlendShape": (170, 100, 220),  # violet (shape blender)
    "mPyFile": (255, 180, 90),  # warm gold, to evoke a "texture map"
    # Generators echo mPyMesh's sea-foam family.
    "mPyNurbsCurve": (90, 220, 200),  # bright sea-foam (curve generator)
    "mPyNurbsSurface": (90, 200, 220),  # cyan-ish (surface generator)
}

DEFAULT_NODE_TYPE_COLOR = (140, 140, 140)
DEFAULT_NODE_TYPE_LETTER = "?"

# QIcon cache; avoids a repaint on every refresh.
_NODE_ICON_CACHE: dict[tuple[str, int, int, bool], QIcon] = {}


# Halo marking a node whose Class has a compiled C++ sibling: a dark
# separator ring just outside the pill, then a light ring outside that. A
# SINGLE tint cannot work -- a light ring vanishes on the grey mPyLocator pill
# and a cyan one vanishes on the sea-foam generators -- so the two-tone pair
# is what keeps it legible against all twelve type colours.
_HALO_DARK_RGB = (30, 30, 30)
_HALO_LIGHT_RGB = (232, 232, 232)
_HALO_PAD = 3          # px of canvas added on EVERY side to hold the rings


def _make_letter_pill_pixmap(
    letter: str,
    bg_rgb: tuple[int, int, int],
    fg_rgb: tuple[int, int, int] = (255, 255, 255),
    size: int = 16,
    pad: int = 0,
    ring: bool = False,
) -> QPixmap:
    """Render a circular pill with the given letter centered on it.

    Uses Qt.ItemDataRole rendering (transparent background outside the
    circle so it sits cleanly on tree alternating rows / dark themes).

    ``pad`` grows the CANVAS without touching the disc, so a padded pill draws
    a disc of exactly the same diameter as an unpadded one -- that is what lets
    a ringed row and a plain row keep their pills the same size and aligned.
    """
    canvas = size + 2 * pad
    pm = QPixmap(canvas, canvas)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    try:
        # Smooth circle edge + text.
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        painter.setPen(Qt.NoPen)
        # Rings first, largest outward-in: the disc then paints over their
        # middles, leaving only the intended bands.
        if ring and pad > 0:
            painter.setBrush(QBrush(QColor(*_HALO_LIGHT_RGB)))
            painter.drawEllipse(0, 0, canvas, canvas)
            painter.setBrush(QBrush(QColor(*_HALO_DARK_RGB)))
            painter.drawEllipse(pad - 1, pad - 1, size + 2, size + 2)

        painter.setBrush(QBrush(QColor(*bg_rgb)))
        painter.drawEllipse(pad, pad, size, size)

        painter.setPen(QColor(*fg_rgb))
        font = QFont()
        font.setBold(True)
        # Pixel size is more reliable than point size across DPI.
        font.setPixelSize(int(size * 0.65))
        painter.setFont(font)
        painter.drawText(
            pm.rect(),
            Qt.AlignCenter,
            letter,
        )
    finally:
        painter.end()
    return pm


def get_node_type_icon(
    native_type: str,
    size: int = 16,
    pad: int = 0,
    ring: bool = False,
) -> QIcon:
    """Return (or build + cache) the letter-pill QIcon for a native_type.

    ``pad``/``ring`` default to the historical unpadded, unringed pill, so every
    existing caller keeps its exact icon. The scene tree passes a constant pad
    to ALL of its rows (see NDSceneTree) and flips ``ring`` per row, which is
    what keeps ringed and unringed pills the same size and on the same centre.
    """
    key = (native_type, size, pad, ring)
    if key in _NODE_ICON_CACHE:
        return _NODE_ICON_CACHE[key]
    letter = NODE_TYPE_LETTERS.get(native_type, DEFAULT_NODE_TYPE_LETTER)
    bg = NODE_TYPE_COLORS.get(native_type, DEFAULT_NODE_TYPE_COLOR)
    pm = _make_letter_pill_pixmap(letter, bg, size=size, pad=pad, ring=ring)
    icon = QIcon(pm)
    _NODE_ICON_CACHE[key] = icon
    return icon


# ===========================================================================
# Per-attr-type foreground colors
# ===========================================================================
#
# RGB tuples carried over from the pre-refactor ATTR_COLOR_MAP (which no
# longer exists in ui/mpynode_designer.py), extended to cover the full type
# list: angle / euler / enum / time / python / mesh / nurbsCurve /
# nurbsSurface.
ATTR_COLOR_DARK_GREEN = (0, 128, 1)
ATTR_COLOR_GREEN = (80, 230, 80)
ATTR_COLOR_BLUE = (128, 230, 230)
ATTR_COLOR_ORANGE = (221, 135, 36)
ATTR_COLOR_GREY_BLUE = (128, 170, 170)
ATTR_COLOR_PINK = (230, 1, 230)
ATTR_COLOR_BLACK = (128, 128, 128)
ATTR_COLOR_BROWN = (146, 101, 49)
ATTR_COLOR_YELLOW = (255, 218, 76)

ATTR_TYPE_COLORS: dict[str, tuple[int, int, int]] = {
    # Numeric scalars
    "int": ATTR_COLOR_DARK_GREEN,
    "float": ATTR_COLOR_GREEN,
    "double": ATTR_COLOR_GREEN,
    "bool": ATTR_COLOR_ORANGE,
    # Vector-y
    "float2": ATTR_COLOR_GREEN,
    "vector": ATTR_COLOR_GREEN,
    "euler": ATTR_COLOR_GREEN,
    "color": ATTR_COLOR_GREEN,
    "quaternion": ATTR_COLOR_BLUE,
    # Specials
    "angle": ATTR_COLOR_BLUE,
    "matrix": ATTR_COLOR_GREY_BLUE,
    "time": ATTR_COLOR_GREEN,
    "enum": ATTR_COLOR_BROWN,
    # Strings + Python + hex
    "string": ATTR_COLOR_YELLOW,
    "python": ATTR_COLOR_YELLOW,
    "hex": ATTR_COLOR_BROWN,
    # Typed Maya geometry
    "mesh": ATTR_COLOR_PINK,
    "nurbsCurve": ATTR_COLOR_BLUE,
    "nurbsSurface": ATTR_COLOR_BLACK,
}

DEFAULT_ATTR_COLOR = (200, 200, 200)


def get_attr_type_color(attr_type: str) -> QColor:
    """Return the foreground QColor for a user attr of the given type."""
    rgb = ATTR_TYPE_COLORS.get(attr_type, DEFAULT_ATTR_COLOR)
    return QColor(*rgb)


def get_attr_type_brush(attr_type: str) -> QBrush:
    """Return a QBrush for setForeground() on tree items."""
    return QBrush(get_attr_type_color(attr_type))
