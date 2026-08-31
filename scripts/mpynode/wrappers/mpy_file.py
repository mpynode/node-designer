"""User-facing wrapper for the mPyFile plug-in node.

Usage::

 from mpynode.wrappers.mpy_file import MPyFile
 import maya.cmds as mc

 # Brand-new mPyFile ships with default Init / Compute / Viewport
 # sources that replicate Maya's stock file-texture behavior.
 f = MPyFile.create(name="diffuseTex")
 mc.setAttr(
 f.get_name() + ".fileName",
 "/path/to/checkerboard.png",
 type="string",
 )

 # Wire it into a material exactly like a stock file node.
 mc.connectAttr(f.get_name() + ".outColor", "lambert1.color", force=True)

The three source tiers (Init / Compute / Viewport) are persisted on the
node via three string plugs: ``_initSource``, ``_computeSource``,
``_viewportSource``. The Node Designer shows one tab per tier; the
user can edit any of them and re-save.

Edits to the default Init source change the colour-space math, kernel
builders, and bilinear sampler used by BOTH the DG ``compute()`` path
and the VP2 ``updateShader`` path simultaneously, because both tabs
import their helpers from the Init namespace.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode._common.util.selection_util import restore_selection
from mpynode._common.lifecycle.viewport_registry import ViewportSourceMixin
from mpynode._common.osl.osl_registry import OslSourceMixin
from mpynode.wrappers._mpy_node import MPyNode
from mpynode._defaults.file_defaults import (
    DEFAULT_COMPUTE_SOURCE,
    DEFAULT_INIT_SOURCE,
    DEFAULT_VIEWPORT_SOURCE,
)
from mpynode._common.interface.file_method_interface import (
    INTERNAL_API_METHODS as _INTERNAL_API_METHODS,
)


class MPyFile(MPyNode, ViewportSourceMixin, OslSourceMixin):
    """Wrapper around an ``mPyFile`` instance in the scene."""

    # Compute tab is plug-only: every ``self.X`` there is a plug, surfaced in
    # Attributes. The Viewport tab additionally gets three bridge-injected
    # handles for shader parameter mapping, alongside the plug-based reads.
    INTERNAL_API_SLOTS = (
        ("time",            "read", "TimeFloat -- current frame (Compute + Viewport); .fps / .asSeconds(). Always live for image sequences."),
        ("shader",          "read", "MShaderInstance -- VP2 shader to bind parameters on (Viewport tab only)"),
        ("mappings",        "read", "MAttributeParameterMappingList -- shader param mappings Maya passes in (Viewport tab only)"),
        ("texture_manager", "read", "omr.MTextureManager -- texture cache + acquire (Viewport tab only)"),
        ("state_manager",   "read", "omr.MStateManager (the class) -- sampler/blend state setters (Viewport tab only)"),
    )

    # The four handles above that ONLY the Viewport tier can reach: they are
    # injected by the VP2 bridge, so in Compute they raise AttributeError
    # (measured). Their docs already said "(Viewport tab only)"; this is the
    # machine-readable half, so the Framework tab can stop offering them on a
    # tab that cannot call them. `time` is deliberately absent -- it is live in
    # Compute AND Viewport.
    VIEWPORT_ONLY_SLOTS = ("shader", "mappings", "texture_manager",
                           "state_manager")

    # The wrapper-level API a user may call from the API tab (setup / demo /
    # @maya_command bodies). NOT reachable as ``self.X`` in Init / Compute /
    # Viewport -- those tiers get a SelfProxy, which resolves plugs, blessed
    # methods and slots, never wrapper methods.
    #
    # Every mPyFile entry survives curation: the get/set/has/clear verb sets are
    # a coherent scripting surface over the `osl` and `_viewportSource` plugs.
    # What made them unreadable was that nine of them carry NO docstring, so the
    # tab rendered a bare name with an empty tooltip -- the doc is supplied here
    # rather than in the shared mixins, which several wrappers use.
    AUTHORING_API = (
        ("get_file_name",
         "The texture file path currently on the `fileName` plug."),
        ("set_file_name",
         "Point the node at a texture on disk. Equivalent to setAttr on the "
         "`fileName` plug."),
        ("reseed_defaults", ""),
        ("convert_compute_to_osl", ""),
        ("convert_compute_to_osl_ai", ""),
        ("get_osl_expression",
         "The OSL shader source on the connectable `osl` output ('' if none)."),
        ("set_osl_expression",
         "Replace the OSL shader source on the `osl` output. Returns True on "
         "success. This is what the OSL tab writes when you edit it."),
        ("has_osl_expression",
         "True when the `osl` output holds non-blank shader source."),
        ("clear_osl_expression",
         "Blank the `osl` output. Same effect as set_osl_expression('')."),
        ("get_viewport_expression",
         "The Viewport-tier source that runs per VP2 updateShader ('' if "
         "none)."),
        ("set_viewport_expression",
         "Replace the Viewport-tier source. Returns True on success. This is "
         "what the Viewport tab writes when you edit it."),
        ("has_viewport_expression",
         "True when the node carries non-blank Viewport-tier source."),
        ("clear_viewport_expression",
         "Blank the Viewport-tier source, so the node draws with the stock "
         "VP2 file-texture path."),
    )

    # Preset plug values the Compute bridge pre-reads into compute_locals for
    # worker-thread safety. mPyFile passes NO output_scratch_keys, so this tier
    # wins on read unconditionally -- a stored var of the same name is
    # unreachable. Read by mpynode._common.interface.reserved_names.
    RESERVED_COMPUTE_LOCALS = (
        ("outColor",         "write", "tuple(r, g, b) -- the sampled color this node emits"),
        ("outAlpha",         "write", "float -- the sampled alpha this node emits"),
        ("outTransparency",  "write", "tuple(r, g, b) -- OPTIONAL; defaults to 1 - outAlpha per channel"),
        ("outSize",          "write", "tuple(w, h) -- OPTIONAL; defaults to the read image's pixel size"),
        ("fileName",         "read",  "str -- the fileName plug, pre-read from the data block"),
        ("uvCoord",          "read",  "tuple(u, v) -- the uvCoord plug, pre-read from the data block"),
        ("uvFilterSize",     "read",  "tuple(du, dv) -- the uvFilterSize plug"),
        ("colorSpace",       "read",  "int -- the colorSpace plug"),
        ("preFilter",        "read",  "bool -- the preFilter plug"),
        ("preFilterKernel",  "read",  "int -- the preFilterKernel plug"),
        ("preFilterRadius",  "read",  "float -- the preFilterRadius plug"),
        ("filterMode",       "read",  "int -- the filterMode plug"),
        ("maxAnisotropy",    "read",  "int -- the maxAnisotropy plug"),
        ("mipmapMode",       "read",  "int -- the mipmapMode plug"),
        ("mipLODBias",       "read",  "float -- the mipLODBias plug"),
        ("minLOD",           "read",  "int -- the minLOD plug"),
        ("maxLOD",           "read",  "int -- the maxLOD plug"),
        ("wrapModeU",        "read",  "int -- the wrapModeU plug"),
        ("wrapModeV",        "read",  "int -- the wrapModeV plug"),
        ("borderColor",      "read",  "tuple(r, g, b) -- the borderColor plug"),
    )

    # METHOD-kind registry: MethodSpec objects from the file_method_interface
    # SSOT, surfaced for the Variables tab and the porter.
    INTERNAL_API_METHODS = _INTERNAL_API_METHODS

    # Attributes-tab allowlist (framework OFF): file/texture essentials only.
    # Hides filter-tuning noise (preFilter* / mipmap* / maxAnisotropy / LOD* /
    # borderColor* / uvFilterSize* / filterMode).
    USEFUL_INHERITED_PLUGS = frozenset({
        "fileName", "uvCoord", "uCoord", "vCoord", "colorSpace",
        "wrapModeU", "wrapModeV", "outColor", "outColorR", "outColorG",
        "outColorB", "outAlpha", "outTransparency", "outSize", "osl",
    })
    NATIVE_TYPE = "mPyFile"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        name: str = None,
        seed_defaults: bool = True,
        as_texture: bool = True,
        skip_selection: bool = False,
    ) -> "MPyFile":
        """Create a new ``mPyFile`` node and (optionally) seed the
        three default sources so it behaves like Maya's stock ``file``
        node out of the box.

        With ``as_texture=True`` (default) the node is created via
        ``cmds.shadingNode -asTexture`` so Maya auto-creates a
        ``place2dTexture`` upstream -- matching the convention every
        other 2D-texture node in Hypershade follows. Pass
        ``as_texture=False`` to create a bare DG node with no
        place2dTexture (e.g. when constructing the connection yourself).

        Pass ``seed_defaults=False`` to start with empty Init / Compute /
        Viewport sources (the node then outputs magenta until the user
        writes their own code).
        """
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        ensure_loaded(cls.NATIVE_TYPE)
        if name is None:
            name = cls._default_create_name()
        # cmds.shadingNode has no skipSelect flag, so the as_texture path
        # snapshots + restores the selection. Bare createNode threads
        # skipSelect directly.
        prior = (mc.ls(selection=True, long=True)
                 if (skip_selection and as_texture) else None)
        if as_texture:
            node_name = mc.shadingNode("mPyFile", asTexture=True, name=name)
        else:
            node_name = mc.createNode("mPyFile", name=name,
                                      skipSelect=skip_selection)
        if skip_selection and as_texture:
            restore_selection(prior)
        wrapper = cls(node_name)
        wrapper._wire_on_create()
        if seed_defaults:
            wrapper.set_init_expression(DEFAULT_INIT_SOURCE)
            wrapper.set_compute_expression(DEFAULT_COMPUTE_SOURCE)
            wrapper.set_viewport_expression(DEFAULT_VIEWPORT_SOURCE)
        return cls._stamp_py_class(wrapper)

    def _wire_on_create(self) -> None:
        """Always-on time: wire the scene clock so ``self.time`` is live for
        image-sequence expressions, matching the stock ``file`` node.

        Called by :meth:`create` AND -- via the same-named hook -- by
        ``mpn_io.deserialize_node``, which builds the node with
        ``cmds.createNode`` (the .mpn import / template-gallery path) and so
        never runs ``create``. Only ever runs on a JUST-created node, so the
        ``force=True`` in the shared helper can't clobber a user's own choice
        of time source. Best-effort: the helper swallows failures."""
        self._auto_connect_time_attr("_timeIn")

    # ------------------------------------------------------------------
    # File path convenience setter (mirrors stock file.fileTextureName)
    # ------------------------------------------------------------------

    def set_file_name(self, path: str) -> None:
        """Set the texture file path. Equivalent to
        ``cmds.setAttr(node + '.fileName', path, type='string')``."""
        mc.setAttr(self._name + ".fileName", path or "", type="string")

    def get_file_name(self) -> str:
        return mc.getAttr(self._name + ".fileName") or ""

    # ------------------------------------------------------------------
    # Source defaults (re-seed)
    # ------------------------------------------------------------------

    def reseed_defaults(self) -> None:
        """Overwrite the three source plugs with the shipped defaults.
        Useful after the user has experimented and wants to revert."""
        self.set_init_expression(DEFAULT_INIT_SOURCE)
        self.set_compute_expression(DEFAULT_COMPUTE_SOURCE)
        self.set_viewport_expression(DEFAULT_VIEWPORT_SOURCE)
