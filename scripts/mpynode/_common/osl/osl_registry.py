"""osl_registry -- per-node OSL shader-string plug + wrapper mixin.

The OSL tab is a per-language sister to Init / Compute / Viewport. Unlike those
(which back the node's *execution* tiers), the OSL string is a **render-target
output**: the authored (or AI-translated) OSL source is persisted on a plain
string plug ``osl`` that is CONNECTABLE -- wire it into a renderer node (e.g.
``aiOslShader``) so Arnold renders the look. This is the v1 language of the
"per-language shader tabs" design.

Unlike ``_viewportSource``/``_computeSource`` (internal kInternal plugs compiled
per node), ``osl`` is a normal storable string attribute, so it (a) persists in
.ma, (b) shows in the Attributes tab, and (c) can be a connection SOURCE -- one
plug is both "the tab content" and "the wire", no dual storage.

Wrapper API (mirrors ViewportSourceMixin):

    wrapper.set_osl_expression(source)
    wrapper.get_osl_expression()
    wrapper.clear_osl_expression()
    wrapper.has_osl_expression()
"""

from __future__ import annotations

import re
import sys


_PLUG_LONG_NAME  = "osl"
_PLUG_SHORT_NAME = "osl"


def _osl_identifier(name: str) -> str:
    """Sanitize a Maya node name into a valid OSL shader identifier
    (``[A-Za-z_][A-Za-z0-9_]*``). Falls back to ``mpyfile_shader``."""
    s = re.sub(r"[^0-9A-Za-z_]", "_", name or "")
    if not s:
        return "mpyfile_shader"
    if s[0].isdigit():
        s = "_" + s
    return s

# Managed render-target shader-string OUTPUTS, in registration order. These are
# statically registered on the mPyFile node TYPE (like outColor/outAlpha), so
# they are present on every instance and undeletable, and the plug-tree walker
# force-classifies them as OUTPUT (they are writable -- the tab/AI author them --
# yet are conceptually connection SOURCES wired into a renderer node). Single
# source of truth shared by the node initializer and the Attributes-tab walker.
# v1: OSL only; adding HLSL/ShaderFX later is one entry here + a wrapper mixin.
MANAGED_SHADER_OUTPUTS = ("osl",)


def make_osl_header(node_type: str) -> str:
    """Return a friendly commented header to prefill a fresh OSL tab.
    Mirrors :func:`viewport_registry.make_viewport_header`."""
    bar = "// " + "-" * 68
    lines = [
        bar,
        f"// {node_type} -- OSL shader source (Open Shading Language)",
        "//",
        "// This tab is a RENDER TARGET, not an execution tier: the text",
        "// here is exposed as the connectable string output `.osl`. Wire it",
        "// into an aiOslShader (Arnold) so the renderer reproduces the look",
        "// your Compute tab computes. You can author it by hand or let the",
        "// AI assistant translate your Compute look-math into OSL.",
        "//",
        "// shader name(params...) { ... outColor = ...; }",
        bar,
        "",
    ]
    return "\n".join(lines)


class OslSourceMixin:
    """Adds ``set_osl_expression`` / ``get_osl_expression`` /
    ``clear_osl_expression`` / ``has_osl_expression`` to any wrapper with a
    ``self._name`` attribute. Persists the OSL source as a connectable string
    attribute (``osl``) on the underlying Maya node so it survives .ma
    save/load AND can be wired into a renderer node."""

    def set_osl_expression(self, source: str) -> bool:
        from maya import cmds

        full = f"{self._name}.{_PLUG_LONG_NAME}"
        if not cmds.attributeQuery(
            _PLUG_LONG_NAME, node=self._name, exists=True
        ):
            cmds.addAttr(
                self._name,
                longName  = _PLUG_LONG_NAME,
                shortName = _PLUG_SHORT_NAME,
                dataType  = "string",
            )
        try:
            cmds.setAttr(full, source or "", type="string")
            return True
        except Exception as exc:
            sys.stderr.write(
                f"[osl_registry] set_osl_expression failed on "
                f"{self._name!r}: {exc}\n"
            )
            return False

    def get_osl_expression(self) -> str:
        from maya import cmds

        if not cmds.attributeQuery(
            _PLUG_LONG_NAME, node=self._name, exists=True
        ):
            return ""
        try:
            return cmds.getAttr(f"{self._name}.{_PLUG_LONG_NAME}") or ""
        except Exception:
            return ""

    def clear_osl_expression(self) -> None:
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

    def has_osl_expression(self) -> bool:
        return bool(self.get_osl_expression().strip())

    def convert_compute_to_osl(self, apply_to_arnold: bool = False) -> str:
        """Deterministically transpile this node's *Compute* look-math into OSL
        and store it on the ``osl`` output. Reads the node's own Compute + Init
        tiers (Init supplies the look constants, resolved statically).

        Raises :class:`mpynode._common.osl.osl_convert.UnsupportedComputeError` when
        the look-math is outside the v1 OSL grammar -- the caller (UI/assistant)
        then offers the AI translation arm. The existing ``osl`` value is left
        untouched on failure (conversion happens before the write). Returns the
        emitted OSL string.
        """
        from mpynode._common.osl.osl_convert import (
            convert_compute_to_osl as _convert,
            extract_simple_consts,
        )

        compute = ""
        init    = ""
        getc    = getattr(self, "get_compute_expression", None)
        if callable(getc):
            compute = getc() or ""
        geti = getattr(self, "get_init_expression", None)
        if callable(geti):
            init = geti() or ""

        consts = extract_simple_consts(init)
        shader = _osl_identifier(getattr(self, "_name", "") or "")
        osl    = _convert(compute, consts=consts, shader_name=shader)

        self.set_osl_expression(osl)
        if apply_to_arnold:
            try:
                from mpynode._common.osl.osl_targets import apply_osl_to_arnold
                apply_osl_to_arnold(self._name)
            except Exception as exc:
                sys.stderr.write(
                    "[osl_registry] apply_osl_to_arnold failed on %r: %s\n"
                    % (getattr(self, "_name", "?"), exc)
                )
        return osl

    def convert_compute_to_osl_ai(self, complete_fn=None, validate_fn=None,
                                  apply_to_arnold: bool = False) -> str:
        """AI-translate this node's *Compute* look-math into OSL and store it on
        the ``osl`` output. This is the FALLBACK arm of the hybrid conversion:
        use it when :meth:`convert_compute_to_osl` (deterministic) raises
        :class:`~mpynode._common.osl.osl_convert.UnsupportedComputeError` because the
        look-math (e.g. the full colour-management pipeline) is outside the v1
        OSL grammar.

        ``complete_fn(system, user) -> str``: the one-shot LLM transport. Default
        (``None``) uses ``mpynode.native.ai.porter._complete`` (provider/key/model
        from the AI-assistant settings). BLOCKING -- pass your own threaded
        transport from a UI. ``validate_fn(osl) -> (ok, error)``: optional
        compile gate (the real one is
        ``osl_targets.validate_osl_via_arnold``, which must run on Maya's main
        thread). Raises :class:`~mpynode._common.osl.osl_ai_convert.OslAiConvertError`
        if no acceptable OSL is produced -- the existing ``osl`` is left
        untouched on failure (translation happens before the write). Returns the
        OSL string.
        """
        from mpynode._common.osl.osl_ai_convert import (
            ai_convert_compute_to_osl,
            OslAiConvertError,
        )

        compute = ""
        init    = ""
        getc    = getattr(self, "get_compute_expression", None)
        if callable(getc):
            compute = getc() or ""
        geti = getattr(self, "get_init_expression", None)
        if callable(geti):
            init = geti() or ""

        # Fast intractability veto: refuse OSL-IMPOSSIBLE computes (a runtime
        # array of textures, non-colour typed outputs) BEFORE spending a single
        # AI round -- this is the compositeTexture failure that motivated the
        # gate (dynamic filePaths[] + int maxWidth/maxHeight outputs). Sending
        # such a node to the LLM only produces a multi-minute flail and no OSL.
        from mpynode._common.osl.osl_convert import assess_osl_tractability
        in_attrs = out_attrs = None
        try:
            gim       = getattr(self, "get_input_attr_map", None)
            gom       = getattr(self, "get_output_attr_map", None)
            in_attrs  = gim() if callable(gim) else None
            out_attrs = gom() if callable(gom) else None
        except Exception:
            in_attrs = out_attrs = None
        tractable, reason = assess_osl_tractability(
            compute, init, input_attrs=in_attrs, output_attrs=out_attrs)
        if not tractable:
            raise OslAiConvertError(
                "This node's Compute cannot be translated to OSL: " + reason)

        shader = _osl_identifier(getattr(self, "_name", "") or "")

        if complete_fn is None:
            from mpynode.native.ai import porter
            complete_fn = porter._complete

        osl = ai_convert_compute_to_osl(
            compute, init, shader, complete_fn, validate_fn=validate_fn)

        self.set_osl_expression(osl)
        if apply_to_arnold:
            try:
                from mpynode._common.osl.osl_targets import apply_osl_to_arnold
                apply_osl_to_arnold(self._name)
            except Exception as exc:
                sys.stderr.write(
                    "[osl_registry] apply_osl_to_arnold failed on %r: %s\n"
                    % (getattr(self, "_name", "?"), exc)
                )
        return osl
