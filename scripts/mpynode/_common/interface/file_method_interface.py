"""Blessed API methods for mPyFile (the METHOD-kind registry entry).

Maya-free. Mirrors the file_texture_interface SSOT pattern. Read by the
Variables tab (via the wrapper class attr) and the porter (directly)."""
from __future__ import annotations

from mpynode._common.interface.api_methods import MethodSpec, CppKernel, validate

INTERNAL_API_METHODS = (
    MethodSpec(
        name="read_texture",
        sig="read_texture(path=None) -> ndarray(H, W, 4) float32",
        doc=("Load + linearize + prefilter an image, cached per (path, "
             "colorSpace, prefilter). Defaults to this node's fileName; pass a "
             "path to manage any other file the same way. None on missing file."),
        runtime="mpynode._common.methods.file_methods:read_texture",
        lower=CppKernel("nd_tex_load_linear"),
        reads=("fileName", "colorSpace", "preFilter", "preFilterKernel",
               "preFilterRadius"),
    ),
    MethodSpec(
        name="sample_texture",
        sig="sample_texture(buf, u, v, missing=None) -> (r, g, b, a)",
        doc=("Wrap-aware bilinear lookup into a buffer from read_texture(). "
             "`missing` is what an unreadable buffer yields: None (the default) "
             "keeps the opaque magenta 'no image' sentinel; pass a literal RGBA "
             "4-tuple to substitute something else -- (0, 0, 0, 0) makes an "
             "unresolvable layer contribute nothing to a composite."),
        runtime="mpynode._common.methods.file_methods:sample_texture",
        lower=CppKernel("nd_tex_sample"),
        reads=("wrapModeU", "wrapModeV", "borderColor"),
    ),
    MethodSpec(
        name="composite_layers",
        sig=("composite_layers(layers, opacities, u, v, "
             "missing=(0, 0, 0, 0)) -> (r, g, b, a)"),
        doc=("Alpha-over a stack of image paths at one (u, v), bottom to top. "
             "Each layer is read + colour-managed + pre-filtered like "
             "read_texture() and sampled like sample_texture(); a layer with "
             "no matching `opacities` element defaults to 1.0. Opacity is a "
             "WEIGHT, not a switch -- it scales the layer's alpha, so 0 removes "
             "it exactly and a negative value subtracts. `missing` defaults to "
             "fully transparent so an unresolvable path drops out instead of "
             "covering the stack with the magenta sentinel."),
        runtime="mpynode._common.methods.file_methods:composite_layers",
        lower=CppKernel("nd_tex_composite_layers"),
        reads=("colorSpace", "preFilter", "preFilterKernel", "preFilterRadius",
               "wrapModeU", "wrapModeV", "borderColor"),
    ),
    MethodSpec(
        name="write_texture",
        sig="write_texture(path, rgba, frame=None) -> bool",
        doc=("Write an (H, W, 4) float RGBA buffer to `path` as an 8-bit PNG. "
             "The twin of read_texture(), for a STATEFUL node whose board an "
             "OSL/Arnold tier cannot evaluate from (u, v, t) alone: bake the "
             "frame, let the shader sample the file. Rows are flipped so a "
             "texture() read lands buffer row 0 at the top. Pass `frame` to "
             "write a frame-stamped sibling (`x.png` -> `x.0007.png`) -- "
             "Arnold's texture cache is keyed on the filename and never "
             "re-stats, so a fixed path never animates in a render. Returns "
             "False instead of raising, so the call stays a lowerable "
             "expression."),
        runtime="mpynode._common.methods.file_methods:write_texture",
        lower=CppKernel("nd_tex_write"),
    ),
)


# Enforce the SelfProxy Tier-0 safety invariant AT IMPORT (mirrors
# file_texture_interface's self-validation): a blessed method resolves BEFORE the
# plug tree in SelfProxy.__getattr__, so a method name equal to an mPyFile plug
# would silently shadow that plug on read. The mPyFile plug surface is the
# declarative file-texture preset table (the same SSOT the porter projects). Fail
# loudly here rather than let a future rename introduce a silent shadow.
from mpynode._common.interface import file_texture_interface as _fti  # noqa: E402

validate(INTERNAL_API_METHODS, set(_fti.build_porter_meta_table()))
