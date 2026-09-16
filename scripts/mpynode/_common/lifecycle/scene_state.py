"""Scene file-IO state helper.

Detects whether Maya is currently reading/opening a scene, or is within
a brief settling window just after a scene open. Used to DEFER (silently
skip) transient expression errors that occur when the Evaluation Manager
pulls a node output mid/just-after load -- before that node's dynamic
input attrs and/or its ``_inputAttrs`` schema plug have been restored.
Such a pull makes the user expression raise

    'self' has no plug, init binding, or stored var named '<input>'

even though the input is perfectly valid; the very next (post-load) eval
succeeds. We don't want to spam that benign, self-correcting error.

Design:
  * ``isReadingFile()`` / ``isOpeningFile()`` (API 1.0 -- API 2.0 has no
    MFileIO) cover the DURING-read window.
  * A monotonic timestamp recorded on every ``kAfter*`` scene event,
    plus a short grace period, covers the JUST-AFTER-open window where
    the EM does its first eager evaluation. The window AUTO-EXPIRES, so
    nothing ever gets stuck deferring (safe for batch / mayapy).
  * Reads are a plain float / bool: safe from EM worker threads.
"""

from __future__ import annotations

import time

# Seconds after a scene-open during which the self-correcting transient
# plug error is suppressed. Generous enough to cover the EM's first eager
# evaluation pass, short enough that genuine post-load errors surface.
_POST_OPEN_GRACE_S   = 10.0

_last_open_monotonic = -1.0e9
_installed           = False

# Attribute-surgery window. While a node is destructively rebuilding its
# dynamic attrs (the drag/keyboard reorder deletes every user attr, writes
# an empty schema map, then re-adds in the new order), the Evaluation
# Manager / viewport can eager-pull a still-live output and fire the user
# expression against the momentarily-empty schema -- the SAME benign,
# self-correcting 'missing plug' transient that scene-open produces, only
# the trigger is a structural edit instead of a file load. A re-entrant
# depth counter covers the synchronous edit; a short grace covers any
# immediately-deferred EM pass just after it. Both auto-expire.
_attr_surgery_depth     = 0
_last_surgery_monotonic = -1.0e9
_SURGERY_GRACE_S        = 2.0


def note_scene_opened() -> None:
    global _last_open_monotonic
    _last_open_monotonic = time.monotonic()


def begin_attr_surgery() -> None:
    """Enter an attribute-surgery window (re-entrant)."""
    global _attr_surgery_depth
    _attr_surgery_depth += 1


def end_attr_surgery() -> None:
    """Leave the innermost attribute-surgery window; on the outermost exit,
    stamp a short grace so a just-deferred EM pull is still covered."""
    global _attr_surgery_depth, _last_surgery_monotonic
    _attr_surgery_depth = max(0, _attr_surgery_depth - 1)
    if _attr_surgery_depth == 0:
        _last_surgery_monotonic = time.monotonic()


def in_attr_surgery() -> bool:
    return _attr_surgery_depth > 0 or (
        (time.monotonic() - _last_surgery_monotonic) < _SURGERY_GRACE_S
    )


def in_attr_surgery_block() -> bool:
    """True only INSIDE an open surgery block -- the trailing grace does NOT
    count.

    ``in_attr_surgery`` includes ``_SURGERY_GRACE_S`` because the thing it
    gates (``should_defer_transient``) has to cover an EM pull that lands just
    AFTER the block returns. An AUTHORING guard is the opposite case: every
    add-attr / new-stored-var a surgery performs happens SYNCHRONOUSLY inside
    the block (``_reorder_attrs``, ``mpn_io`` restore), while anything arriving
    during the grace is an ordinary interactive edit that must be rejected, not
    merely warned about. Guards therefore ask this instead."""
    return _attr_surgery_depth > 0


def _is_file_io() -> bool:
    try:
        import maya.OpenMaya as om1

        return bool(om1.MFileIO.isReadingFile() or om1.MFileIO.isOpeningFile())
    except Exception:
        return False


def in_post_open_grace() -> bool:
    return (time.monotonic() - _last_open_monotonic) < _POST_OPEN_GRACE_S


def should_defer_transient() -> bool:
    """True while the scene is loading, within the post-open grace window,
    or mid attribute-surgery (reorder) -- i.e. while a transient,
    self-correcting plug-missing error should be deferred rather than
    logged."""
    return _is_file_io() or in_post_open_grace() or in_attr_surgery()


# Signature of the SelfProxy "missing attribute" raise. Matching on it
# keeps the suppression narrow: only THIS specific error is ever
# deferred; every other expression error still surfaces normally.
_MISSING_PLUG_SIGNATURE = "has no plug, init binding, or stored var named"


def is_missing_plug_error(message: str) -> bool:
    try:
        return _MISSING_PLUG_SIGNATURE in (message or "")
    except Exception:
        return False


def extract_missing_name(message: str):
    """Pull the attribute name out of the SelfProxy missing-plug error,
    e.g. ... named 'input'. ... -> "input". Returns None if not found."""
    try:
        import re

        m = re.search(r"named '([^']+)'", message or "")
        return m.group(1) if m else None
    except Exception:
        return None


def install_once() -> None:
    """Subscribe to ``kAfter*`` scene events so the post-open grace
    window starts when a file finishes loading. Idempotent."""
    global _installed
    if _installed:
        return
    _installed = True
    try:
        import maya.OpenMaya as om1
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_SHARED

        def _on_after(_client):
            note_scene_opened()

        for event_name in (
            "kAfterOpen",
            "kAfterImport",
            "kAfterReference",
            "kAfterCreateReference",
            "kAfterLoadReference",
        ):
            evt = getattr(om1.MSceneMessage, event_name, None)
            if evt is None:
                continue
            try:
                cb_id = om1.MSceneMessage.addCallback(evt, _on_after)
                CALLBACK_MANAGER.register(
                    cb_id, om1.MMessage.removeCallback, OWNER_SHARED
                )
            except Exception:
                pass
    except Exception:
        pass


def reset_install_state() -> None:
    """Clear the install guard so a later plugin reload re-subscribes.

    Called by the last-plugin-out teardown AFTER the shared callbacks have
    been deregistered (via ``CALLBACK_MANAGER.remove_for_owner('shared')``).
    Without this, ``_installed`` stays latched True across an unload and
    ``install_once`` no-ops on reload -> the post-open grace window never
    re-arms."""
    global _installed
    _installed = False
