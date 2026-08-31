"""gap_spacing_registry -- per-node blank-line spacing for the baked .py.

The API view shows the node as it bakes, and the blank lines BETWEEN the
generated blocks are the exporter's, not the user's. Pressing Return with the
caret at the start of a managed block pushes it down; Backspace in the run
above it pulls it back up until the two blocks touch. That gesture needs
somewhere to live, because the API view re-generates its buffer on every return
to the tab -- spacing kept only in the widget would vanish on a tab switch.

So it lives on the NODE, as ``{region kind: blank lines before that block}``.

SPARSE BY CONSTRUCTION: only boundaries the user actually moved are stored, and
``py_export`` falls back to the literal spacing it has always emitted (see
``py_export._DEFAULT_GAP``). An empty map therefore bakes byte-for-byte what
the exporter baked before this existed, which is what keeps every shipped
template unchanged until somebody deliberately re-spaces one.

Storage mirrors ``MetadataMixin``: a hidden ``_apiGapSpacing`` string plug
holding a JSON blob, created lazily on first write, so a node that never
re-spaces anything grows no plug and stays cache-stable for the native porter.

Pure apart from the mixin bodies (maya is imported lazily inside them), so
``coerce`` / ``is_empty`` are unit-testable with no running Maya.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict

__all__ = ["GapSpacingMixin", "coerce", "is_empty", "MAX_GAP"]

_PLUG = "_apiGapSpacing"

# A ceiling, so a stuck key or a malformed file cannot push the class
# declaration a thousand lines down a buffer the user then has to scroll back.
MAX_GAP = 16


def coerce(spacing: Dict[str, Any] | None) -> Dict[str, int]:
    """The canonical shape: ``{str: int}``, clamped to ``0..MAX_GAP``.

    Anything unusable is DROPPED rather than defaulted -- a dropped key falls
    back to the exporter's own spacing, which is always a valid answer, whereas
    a defaulted one would silently claim the user had chosen it.
    """
    out: Dict[str, int] = {}
    if not isinstance(spacing, dict):
        return out
    for key, value in spacing.items():
        if not isinstance(key, str) or not key:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        out[key] = max(0, min(MAX_GAP, value))
    return out


def is_empty(spacing: Dict[str, Any] | None) -> bool:
    return not coerce(spacing)


class GapSpacingMixin:
    """Adds ``set_api_gap_spacing`` / ``get_api_gap_spacing`` /
    ``clear_api_gap_spacing`` to any wrapper with a ``self._name``. Adds no
    ``__init__`` and creates the plug lazily."""

    def set_api_gap_spacing(self, spacing: Dict[str, Any] | None) -> bool:
        """Persist ``spacing`` (coerced). Returns True on success, False with a
        stderr note if the plug write fails."""
        from maya import cmds

        payload = json.dumps(coerce(spacing), sort_keys=True)
        if not cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            cmds.addAttr(self._name, longName=_PLUG, dataType="string",
                         hidden=True)
        try:
            cmds.setAttr("%s.%s" % (self._name, _PLUG), payload, type="string")
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(
                "[gap_spacing_registry] set_api_gap_spacing failed on %r: %s\n"
                % (self._name, exc))
            return False
        return True

    def get_api_gap_spacing(self) -> Dict[str, int]:
        """The node's spacing map, or ``{}`` if unset or malformed. Never
        raises: this is read on every bake, and a bad plug must cost the
        default spacing, not the export."""
        from maya import cmds

        if not cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            return {}
        try:
            raw = cmds.getAttr("%s.%s" % (self._name, _PLUG)) or ""
        except Exception:  # noqa: BLE001
            return {}
        if not raw:
            return {}
        try:
            return coerce(json.loads(raw))
        except Exception:  # noqa: BLE001
            return {}

    def clear_api_gap_spacing(self) -> None:
        from maya import cmds

        if cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            try:
                cmds.setAttr("%s.%s" % (self._name, _PLUG), "", type="string")
            except Exception:  # noqa: BLE001
                pass
