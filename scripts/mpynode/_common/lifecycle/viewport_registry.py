"""Viewport_registry -- per-node Viewport source plug + wrapper mixin.

The Viewport tab is a third sister to Init and Compute. Like the
Expression (Compute) tab, it lives as a Maya string plug
(``_viewportSource``) on the node and is COMPILED per node + cached.
Unlike Init, the bridge does NOT auto-exec the source on file open;
Viewport is *pull-driven* by whichever bridge needs it (currently the
mPyFile MPxShadingNodeOverride.updateShader call path).

The Init namespace registered for the same node is merged into the
Viewport exec namespace by:func:`exec_with_profile_watch` (same hook
that feeds Init into Compute), so helpers defined in Init are
available to Viewport code as bare names.

The wrapper-side ``ViewportSourceMixin`` mirrors:class:`mpynode._common.lifecycle.init_registry.InitSourceMixin` for the new
plug. Plug naming:

 _viewportSource string attribute on the node (long+short name)

Wrapper API:

 wrapper.set_viewport_expression(source)
 wrapper.get_viewport_expression()
 wrapper.clear_viewport_expression()
 wrapper.has_viewport_expression()
"""

from __future__ import annotations

import sys


_PLUG_LONG_NAME = "_viewportSource"
_PLUG_SHORT_NAME = "_viewportSource"


def make_viewport_header(node_type: str) -> str:
    """Return a friendly commented header to prefill a fresh
    Viewport tab. Mirrors:func:`init_registry.make_init_header`."""
    bar = "# " + "-" * 68
    lines = [
        bar,
        f"# {node_type} -- Viewport code (runs per VP2 shader update)",
        "#",
        "# This tab runs in parallel with the Compute tab. Use it for",
        "# code paths that interface with Maya systems OTHER than the",
        "# normal DG compute() flow -- e.g. Viewport 2.0 shader updates,",
        "# texture uploads, sampler-state binding.",
        "#",
        "# The Init namespace is merged into your Viewport globals, so",
        "# helpers / kernels / matrices defined there are available here",
        "# as bare names. ``self`` exposes the live plug tree the same",
        "# way it does inside Compute.",
        bar,
        "",
    ]
    return "\n".join(lines)


class ViewportSourceMixin:
    """Adds ``set_viewport_expression`` / ``get_viewport_expression`` /
    ``clear_viewport_expression`` / ``has_viewport_expression`` to any wrapper
    with a ``self._name`` attribute. Persists the source as a string
    attribute on the underlying Maya node so it survives.ma
    save/load.

    The wrapper writes to the plug via ``cmds.setAttr``; the bridge's
    own ``setInternalValue`` override compiles + caches the code
    object whenever the plug value changes.
    """

    def set_viewport_expression(self, source: str) -> bool:
        from maya import cmds

        full = f"{self._name}.{_PLUG_LONG_NAME}"
        if not cmds.attributeQuery(
            _PLUG_LONG_NAME, node=self._name, exists=True
        ):
            cmds.addAttr(
                self._name,
                longName=_PLUG_LONG_NAME,
                shortName=_PLUG_SHORT_NAME,
                dataType="string",
            )
        try:
            cmds.setAttr(full, source or "", type="string")
            return True
        except Exception as exc:
            sys.stderr.write(
                f"[viewport_registry] set_viewport_expression failed on "
                f"{self._name!r}: {exc}\n"
            )
            return False

    def get_viewport_expression(self) -> str:
        from maya import cmds

        if not cmds.attributeQuery(
            _PLUG_LONG_NAME, node=self._name, exists=True
        ):
            return ""
        try:
            return cmds.getAttr(f"{self._name}.{_PLUG_LONG_NAME}") or ""
        except Exception:
            return ""

    def clear_viewport_expression(self) -> None:
        from maya import cmds

        if not cmds.attributeQuery(
            _PLUG_LONG_NAME, node=self._name, exists=True
        ):
            return
        try:
            cmds.setAttr(
                f"{self._name}.{_PLUG_LONG_NAME}", "", type="string"
            )
        except Exception:
            pass

    def has_viewport_expression(self) -> bool:
        return bool(self.get_viewport_expression().strip())
