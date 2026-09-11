"""Per-area font sizing for the non-editor widgets.

``QtPythonEditor`` (``widgets/editor_core.py``) has had pref-driven, live-updating
font sizing since long before this module: read the pref, ``setFont``, subscribe
to ``preferences.register_change_listener``, re-apply on the keys you care about,
self-unregister once the C++ side is gone. That works, and it is the pattern to
copy -- but copying it into nine more widgets by hand would mean nine chances to
get the self-unregister wrong.

So the trio lives here once, as a function rather than a mixin: the targets are
``QTreeWidget``s, ``QPlainTextEdit``s and a ``QTextEdit`` that already inherit
from several bases and are constructed in nine different places, and a free
function attaches to any of them without touching their class hierarchies.

The editors deliberately do NOT use this -- they own a family preference and a
Ctrl+wheel zoom this has no concept of, and rewiring a working path buys
nothing.
"""
from __future__ import annotations


def apply_area_font(widget, area: str, rel: float = 1.0) -> bool:
    """Set ``widget``'s font to ``area``'s configured point size. Best-effort.

    ``rel`` scales it: 0.85 for the small grey captions that sit beside a
    panel and should stay subordinate to it. Floored at 6pt, the same floor
    the editor and the preferences clamp use, so a subordinate label can
    never become illegible.

    Returns True if the font was applied. False means the preferences module
    was unimportable or the widget rejected the call -- both survivable, and
    the widget simply keeps whatever font it inherited.
    """
    try:
        from mpynode.ui.preferences import (FONT_SIZE_MIN, area_font,
                                            resolve_font_size)

        font = area_font(area)
        if rel != 1.0:
            font.setPointSize(max(FONT_SIZE_MIN,
                                  int(round(resolve_font_size(area) * rel))))
        widget.setFont(font)
        return True
    except Exception:
        return False


def wire_area_font(widget, area: str, on_change=None, rel: float = 1.0) -> None:
    """Apply ``area``'s font now, and again whenever that area's pref changes.

    ``on_change`` is an optional no-argument callable invoked after each
    re-apply, for widgets that need more than a repaint. Two real cases:
    a view that caches row heights, and ``NDApiView``, whose gutter is a
    separate widget and does not follow a viewport repaint (see
    ``api_view.py``'s own ``_on_pref_changed``).

    Best-effort throughout: a UI that cannot subscribe should still open with
    the right font rather than refuse to build.
    """
    from mpynode.ui.preferences import FONT_AREA_KEYS, FONT_FAMILY_KEYS

    key  = FONT_AREA_KEYS[area]
    keys = (key, FONT_FAMILY_KEYS.get(key))
    apply_area_font(widget, area, rel)

    def _listener(changed_key, _value, _keys=keys, _w=widget, _cb=on_change,
                  _rel=rel):
        # Only this area's size key and its family key. A panel must not
        # reflow because the editor font moved -- that was the whole point of
        # keeping the editor apart.
        if changed_key not in _keys:
            return
        try:
            apply_area_font(_w, area, _rel)
            if _cb is not None:
                _cb()
        except RuntimeError:
            # C++ side deleted. Unsubscribe, or the bound closure keeps the
            # dead widget alive in the registry forever.
            try:
                from mpynode.ui.preferences import unregister_change_listener

                unregister_change_listener(_listener)
            except Exception:
                pass

    try:
        from mpynode.ui.preferences import register_change_listener

        register_change_listener(_listener)
    except Exception:
        return

    # The registry holds only a weak-ish reference in practice (a plain list),
    # but the closure is the only strong reference to itself -- park it on the
    # widget so it lives exactly as long as the widget does and can be found
    # again by tests.
    try:
        widget._nd_font_listener = _listener
    except Exception:
        pass
