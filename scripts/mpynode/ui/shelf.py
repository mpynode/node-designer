"""Shelf installer for the Node Designer.

Creates a Maya shelf button that opens the Designer when clicked. Two
ways to use:

  * Programmatic: ``install_shelf_button()`` from a Python script
  * Interactive: drag the snippet below onto a shelf

The button uses Maya's built-in ``commandButton`` icon (``pythonFamily.png``)
since we don't ship custom icons.

Snippet for shelf drag-and-drop (paste into Maya's script editor and
Ctrl+Drag the highlighted text to a shelf):

    from mpynode.ui.mpynode_designer import show_designer
    show_designer()
"""

from __future__ import annotations

import os

import maya.cmds as mc

from mpynode.ui.widgets.icons import icon_path

DEFAULT_BUTTON_LABEL = "ND2"
DEFAULT_TOOLTIP      = "Open Node Designer 2"
# Bundled 32x32 icon; fall back to a Maya stock one so the button still
# installs if it's ever missing.
_MPYNODE_ICON = icon_path("mpynode.png")
DEFAULT_ICON  = _MPYNODE_ICON if os.path.exists(_MPYNODE_ICON) else "pythonFamily.png"

# Module-level constant so tests can verify the click command.
SHELF_BUTTON_COMMAND = (
    "from mpynode.ui.mpynode_designer import show_designer\nshow_designer()"
)


def get_top_shelf() -> str | None:
    """Return the name of Maya's currently-selected shelf, or None."""
    try:
        top = mc.tabLayout("ShelfLayout", query=True, selectTab=True)
        return top
    except Exception:
        return None


def install_shelf_button(
    parent_shelf: str | None = None,
    label:        str        = DEFAULT_BUTTON_LABEL,
    tooltip:      str        = DEFAULT_TOOLTIP,
    icon:         str        = DEFAULT_ICON,
) -> str | None:
    """Install a shelf button on the given (or active) shelf.

    Returns the new button name on success, or None if Maya UI isn't
    available (e.g. in batch / mayapy without a Maya main window).
    """
    if parent_shelf is None:
        parent_shelf = get_top_shelf()
    if not parent_shelf:
        return None
    try:
        btn = mc.shelfButton(
            parent     = parent_shelf,
            label      = label,
            annotation = tooltip,
            image      = icon,
            command    = SHELF_BUTTON_COMMAND,
            sourceType = "python",
        )
        return btn
    except Exception:
        return None
