"""Top-level dispatcher: generate_cpp -> full MPx*Node skeleton."""
from __future__ import annotations

from mpynode._common.interface.morph_method_interface import LIVE_CPP_VARS
from mpynode.native.compiler.kernels import file_texture_cpp, nd_io_cpp
from .spec_model import (_check, _geo_kind, _spec_has_hex,
                         _spec_has_nurbs_curve, _spec_has_mesh,
                         _spec_has_nurbs_surface, _spec_has_packed,
                         LOWERED_GUARD_INCLUDE,
                         MESH_INTERSECTOR_INCLUDE)
from .emit_attr import (_INCLUDES, _create_lines, _members, _pick_path_input,
                        PACKED_INCLUDES)
from . import emit_geo_io
from .emit_hex import _HEX_CPP
from .nd_runtime import _nd_runtime_cpp
from .emit_compute import _compute_lines
from .emit_deformer import (
    _DEFORMER_BASES, _DEFORMER_INCLUDES, _deform_lines, _setdirty_lines,
    base_attr_members as _deformer_base_attr_members,
)
from .emit_geo import _generate_geo_cpp
from .emit_iksolver import _IKSOLVER_BASE, _generate_iksolver_cpp
from .emit_locator import _LOCATOR_BASE, _generate_locator_cpp
from .emit_transform import _TRANSFORM_BASE, _generate_transform_cpp
from .emit_compute import _self_attr_refs, _self_attr_writes
from .errors import UnsupportedSpec


_MFNPLUGIN_INIT_DEFAULT = (
    '    MFnPlugin plugin(obj, "mpynode-native", "1.0", "Any");')

# Deformer deform() binds these inherited plugs by construction: the geometry
# idiom (input/inputGeom -> harvested pts, outputGeometry/outputGeom -> writeback)
# and the envelope scalar. A skinCluster additionally binds its inherited
# influence + weight plugs. Any OTHER self.<attr> read that is neither a declared
# user input nor assigned in compute/init cannot be reconstructed by the AI port.
_DEFORM_BOUND_READS = {"envelope", "outputGeometry", "outputGeom",
                       "input", "inputGeometry", "inputGeom"}
_SKIN_BOUND_READS = {"matrix", "bindPreMatrix", "weightList", "weights"}
# Blessed reads with no plug behind them: CODEGEN builds the value and binds it
# (mPyBlendShape's live-target CSR, emitted by emit_deformer and bound by
# nd_lower). Bindable by construction, so the unbound-read guard must not report
# them -- keyed off the same table both halves use, so adding one there is
# enough.
_CODEGEN_BOUND_READS = frozenset(LIVE_CPP_VARS)


def _called_method_reads(spec):
    """Reads declared by the blessed methods this compute calls, seen THROUGH
    the ``self.morphs`` desugar.

    The desugar matters: ``self.morphs.deltas(base, w)`` is a blessed
    ``morph_deltas`` call that the RAW source does not spell, so reading the
    compute as written would find no called method and no reads at all. Never
    raises -- a source that does not fold is reported on by the compile proper,
    and this guard must not turn that into a different error.
    """
    from mpynode.native.compiler import nd_lower
    from mpynode.native.compiler.kernels import blessed_transpile
    src = spec.get("compute") or ""
    try:
        src = nd_lower._rewrite_morph_reads(src)
    except Exception:
        pass
    try:
        return set(blessed_transpile.called_method_reads(dict(spec,
                                                              compute=src)))
    except Exception:
        return set()


def _reject_unbound_deform_reads(ins, spec, base):
    """Honest-reject guard for the deformer AI-port path (mirrors
    ``emit_compute._unbound_self_reads`` for the plain-MPxNode path). When the
    deterministic lowering declined (``deform_lowered is None``) the node would be
    AI-ported; if its compute READS a ``self.<attr>`` that is neither a declared
    input, an inherited deformer/skin plug the port binds, nor assigned anywhere
    in compute/init, that value comes from OUTSIDE the compiled node and the port
    would silently no-op. Raise UnsupportedSpec (-> build_status "dropped") rather
    than ship a no-op port.

    Also checks the reads a called blessed method declares IMPLICITLY. Those are
    structurally invisible to the source scan -- they are consumed inside the
    method and never spelled ``self.<name>`` in the compute -- which made them
    the one unbound read this guard could not see. The failure is silent end to
    end: an unbindable read makes ``lower_deform`` raise, ``try_lower_deform``
    swallows it, codegen keeps the PORT region, and the build reports success
    while the shipped node ignores the read entirely."""
    src = "%s\n%s" % (spec.get("compute") or "", spec.get("init") or "")
    refs = _self_attr_refs(src)
    method_reads = _called_method_reads(spec)
    if not refs and not method_reads:
        return
    declared = {i["plug"] for i in ins}
    bound = set(_DEFORM_BOUND_READS)
    if base == "MPxSkinCluster":
        bound |= _SKIN_BOUND_READS
    # A blessed method call (``self.linear_blend(...)``) tokenizes as a
    # ``self.<name>`` ref but is a registered API method, not an unbound plug
    # read. If lowering declined for some OTHER reason and this guard runs,
    # blaming the method name would be a false orphan -- so exclude the type's
    # blessed method names and only ever report genuinely-unbound reads.
    from mpynode._common.interface import method_registry
    bound |= {m.name for m in method_registry.methods_for_type(spec.get("mpy_type"))}
    # Same for a blessed PROPERTY (``self.morphs``). Codegen rewrites the
    # recognised ``self.morphs.<member>`` forms into blessed calls before
    # lowering, so if lowering declined the desugar already reported why --
    # naming ``morphs`` as an orphan would bury that with a false one.
    bound |= {p.name
              for p in method_registry.properties_for_type(spec.get("mpy_type"))}
    written = _self_attr_writes(src)
    orphans = {r for r in refs
               if r not in declared and r not in bound and r not in written}
    if orphans:
        raise UnsupportedSpec(
            "deformer compute reads undeclared self attr(s) %s -- not a declared "
            "input, an inherited deformer/skin plug, or assigned in compute/init, "
            "so the compiled node cannot obtain their value; refusing to ship a "
            "silent no-op port" % ", ".join(sorted(orphans)))
    # A codegen-provided read (the live-target tables emit_deformer builds) has
    # no plug and is bound by the emitter, so it is bindable by construction --
    # anything else must resolve to a real declared input.
    unbound = {r for r in method_reads
               if r not in declared and r not in bound
               and r not in _CODEGEN_BOUND_READS}
    if unbound:
        raise UnsupportedSpec(
            "blessed method(s) called by this deformer declare read(s) %s that "
            "nothing binds -- not a declared input, an inherited plug, or a "
            "codegen-provided table; the deterministic lowering cannot bind them "
            "and the AI port would ignore them, so refusing to ship it"
            % ", ".join(sorted(unbound)))


def _spec_reads_component_tag(spec) -> bool:
    """True if the compute reads a geo component tag (``.region(`` /
    ``.component_tags`` / ``.tag_clusters(``) -- gates the tag-decode header
    injection."""
    src = spec.get("compute") or ""
    return (".region(" in src or ".component_tags" in src
            or ".tag_clusters(" in src)

def _spec_reads_uv(spec) -> bool:
    """True if the compute reads mesh UVs (``.uvs``) -- gates the getUVs header
    injection (MStringArray / MFloatArray)."""
    return ".uvs" in (spec.get("compute") or "")

def _cpp_escape(s) -> str:
    """Escape a Python string into a single-line C++ ``"..."`` literal body:
    collapse newlines/tabs (so a value can't break the line) then escape ``\\``
    and ``"``."""
    s = " ".join(str(s).split())
    return s.replace("\\", "\\\\").replace('"', '\\"')

def _apply_metadata(cpp: str, spec: dict) -> str:
    """Embed node metadata into the generated C++: a ``//`` banner block + the
    ``MFnPlugin`` vendor/version stamped with a deterministic build hash. Applied
    to EVERY node base by the ``generate_cpp`` wrapper. Pure + deterministic --
    the hash is sha256 of the placeholder-bearing source, so the same spec yields
    the same hash. With no ``spec['metadata']`` the default vendor/version + a
    hash are still emitted (every compile carries an identifier)."""
    from mpynode._common.lifecycle import metadata_registry as md

    meta = spec.get("metadata") or {}
    vendor = _cpp_escape(md.vendor_string(meta))
    # Sanitize '+' out of the embedded version so the build-hash suffix stays the
    # single unambiguous trailing "+<hash12>" (a user version like "2.0+rc1"
    # would otherwise make "<version>+<hash>" un-splittable).
    version = _cpp_escape(md.version_string(meta)).replace("+", "-")
    new_init = ('    MFnPlugin plugin(obj, "%s", "%s+%s", "Any");'
                % (vendor, version, md.BUILD_HASH_PLACEHOLDER))
    cpp = cpp.replace(_MFNPLUGIN_INIT_DEFAULT, new_init)
    banner = "\n".join(md.banner_lines(meta)) + "\n\n"
    stamped, _h = md.stamp_build_hash(banner + cpp)
    return stamped

def generate_cpp(spec: dict, for_port: bool = False) -> str:
    """Generate the node's C++, then embed metadata (banner + MFnPlugin
    vendor/version + a deterministic build hash). The metadata step is the single
    point every node base flows through (see ``_apply_metadata``)."""
    return _apply_metadata(_generate_cpp_impl(spec, for_port), spec)

def _generate_cpp_impl(spec: dict, for_port: bool = False) -> str:
    _check(spec)
    sg = spec["suggested"]
    cls = sg["class_name"]
    type_name = sg["node_type_name"]
    type_id = sg["type_id"]
    base = sg.get("mpx_base", "MPxNode")
    gk = _geo_kind(spec)
    if gk:
        return _generate_geo_cpp(spec, gk, for_port)
    if base == _TRANSFORM_BASE:
        return _generate_transform_cpp(spec, for_port)
    if base == _LOCATOR_BASE:
        return _generate_locator_cpp(spec, for_port)
    if base == _IKSOLVER_BASE:
        return _generate_iksolver_cpp(spec, for_port)
    is_deformer = base in _DEFORMER_BASES
    members = _members(spec)
    # Texture/file node: declare `fileName` FIRST among inputs. Maya 2026's CPU
    # swatch generator (2dTextureSwatchGen) uses the node's first input plug as a
    # "what kind of texture" hint; if it isn't fileName the Hypershade swatches
    # silently degrade to a single-sample solid colour (see _api2/mpy_file.py).
    if sg.get("reads_image_file"):
        _fn = next((m for m in members
                    if m["kind"] == "inputs" and m["plug"] == "fileName"), None)
        if _fn is None:
            # No fileName preset (e.g. the multi-file composite node uses a string
            # ARRAY path input): fall back to the picked path input as the hint.
            _fn = _pick_path_input([m for m in members if m["kind"] == "inputs"])
        if _fn is not None:
            members = [_fn] + [m for m in members if m is not _fn]
    ins = [m for m in members if m["kind"] == "inputs"]
    outs = [m for m in members if m["kind"] == "outputs"]
    # mPyFile BASE plugs the spec never captured (uvFilterSize, the sampler
    # presets, outTransparency/outSize, _timeIn, osl). Deliberately NOT merged
    # into ins/outs: nd_lower and _compute_lines below must see the SPEC set
    # unchanged, or the ported / lowered compute body -- and its port_cache
    # entry -- would move. initialize() creates them; the compute tail derives
    # the two outputs. Empty for every other mpy_type.
    base_extra = file_texture_cpp.base_attr_members(spec, members)
    # Same idea for a deformer whose mPy type registers a framework plug its MPx
    # base does not provide (mPyBlendShape's targetGeometry). Appended, so the
    # member names it picks cannot collide with the texture ones.
    base_extra += _deformer_base_attr_members(spec, members + base_extra)

    # Deterministic numpy->C++ lowering (generic compute() path only; deformers
    # harvest geometry via deform()). Decide up front so the nd:: runtime header
    # can be inlined above the class when the whole compute lowers to pure C++.
    nd_lowered = None
    deform_lowered = None
    # Class-body declarations the lowered compute depends on: the per-instance
    # persistent-state members (`_NdState _ndState` + its mutex) that its `st`
    # binds to. Only this emitter writes the class body, so nd_lower hands them
    # back rather than emitting a function-static registry inside compute().
    nd_state_decls = []
    if is_deformer:
        # Deformers harvest geometry via deform() (getPoints/setPoints on
        # self.outputGeometry). nd_lower rewrites that idiom + lowers the numeric
        # middle; None -> AI-porter PORT region unchanged (zero regression).
        from mpynode.native.compiler import nd_lower
        deform_lowered = nd_lower.try_lower_deform(ins, spec, base)
        if deform_lowered is None:
            # Would AI-port -> honest-reject any unbound external self read.
            _reject_unbound_deform_reads(ins, spec, base)
        nd_io_cpp.reject_unlowered_io(spec, deform_lowered, "deformer")
    else:
        from mpynode.native.compiler import nd_lower
        nd_lowered = nd_lower.try_lower_compute(ins, outs, spec)
        nd_state_decls = list(getattr(nd_lowered, "state_decls", ()) or ())
        nd_io_cpp.reject_unlowered_io(spec, nd_lowered, "node")

    full_tex = file_texture_cpp.use_full_parity_glue(spec)
    # Blessed-texture compute: a custom mPyFile compute that CALLS the blessed
    # self.read_texture()/self.sample_texture() and fully lowered. Its body calls
    # the same nd_tex_* kernels + _texCache/_texMutex as the full-parity glue, so
    # it needs the same math+cache block. Mutually exclusive with full_tex (that
    # path matches the bare Init-helper calls).
    blessed_tex = (nd_lowered is not None) and file_texture_cpp.uses_blessed_texture(spec)
    # Either texture path needs the NdTexCache math + cache block, includes, and
    # per-instance members emitted.
    need_tex_cache = full_tex or blessed_tex
    # Blessed BAKE compute: calls self.write_texture(). Gated separately -- a
    # simulation node bakes its board without ever sampling an image, so it needs
    # WRITE_CPP but none of the sampler/cache machinery above.
    blessed_write = ((nd_lowered is not None)
                     and file_texture_cpp.uses_blessed_write(spec))
    # Image-sequence full-parity file node: its per-frame path resolver needs the
    # nd_tex_resolve_seq helper emitted above the class. Sequences are a full-parity
    # feature only (no sequences in the blessed v1).
    seq_desc = file_texture_cpp.full_parity_seq(spec) if full_tex else None
    # Custom-compute reads_image_file node (e.g. scanline): not the full-parity
    # pipeline, but it STILL must cache the MImage decode (a per-compute read =
    # per-sample decode = a render thousands of times slower than the Python node).
    raw_img_cache = bool(sg.get("reads_image_file")) and not need_tex_cache
    if nd_lowered is not None or deform_lowered is not None:
        # A deterministically LOWERED body is numeric C++ generated by nd_lower,
        # which has no image intrinsic at all and so can never name _imgPixels --
        # the body emitters return before the read for the same reason. Declaring
        # the cache anyway is the decl-without-call half of the same half-wired
        # state the suppression below exists to prevent. (The blessed-texture
        # path also lowers, but it carries its own cache via need_tex_cache
        # above, which has already cleared this flag.)
        raw_img_cache = False
    # Multi-file composite: a reads_image_file node whose path input is a string
    # ARRAY builds a decode-once composite (nd_img_composite) instead of the
    # single-file raw cache, exposed through the same _imgPixels interface.
    _path_in = _pick_path_input(ins) if raw_img_cache else None
    composite_img_cache = bool(_path_in and _path_in["meta"].get("is_array"))
    if composite_img_cache:
        raw_img_cache = False   # composite REPLACES the single-file raw cache
    elif _path_in is None:
        # No path input at all (hardcoded path in Init, or a stored var): the node
        # has no path PLUG, so _image_read_lines has nothing to load and returns
        # []. Declaring the cache anyway -- and telling the porter the pixels are
        # "loaded above" -- would promise a buffer that is never emitted. Suppress
        # both; the porter then translates the read itself or emits
        # ND_PORT_INCOMPLETE, which is the honest outcome for a pathless node.
        raw_img_cache = False
    # Embedded-image fallback (#98): the node baked an embeddedImage byte buffer
    # (read_texture() reads fileName first, then falls back to it). BOTH image
    # paths carry it -- the custom-compute raw cache (a hand-rolled pixel tap)
    # and the blessed nd_tex_* lowering -- so the staging helper is emitted for
    # either. They differ only in the CACHE they retry through: the raw path
    # needs a second slot (EMBEDDED_STAGE_MEMBERS below), while the blessed path
    # reuses its by-path NdTexCache map and needs no extra member.
    embedded_b64 = ((sg.get("embedded_image_b64") or "")
                    if (raw_img_cache or blessed_tex) else "")
    # SINGLE decision for the whole TU: this function declares the caches, so the
    # body emitters (compute()/deform()) are TOLD whether a read was wired rather
    # than re-deriving it from the spec. Two independent deciders is what left the
    # deformer arm declaring a cache it never filled.
    img_read = raw_img_cache or composite_img_cache

    from mpynode.native.compiler.kernels import command_dispatch
    cmd_out = command_dispatch.dispatch_for_spec(spec, type_name)
    if cmd_out["errors"]:
        import sys as _sys
        _sys.stderr.write(
            "[command_dispatch] %s: command(s) not lowered: %s\n"
            % (type_name, "; ".join(cmd_out["errors"])))

    includes = list(_INCLUDES)
    # MGlobal::displayError, used only by the lowered body's boundary handler --
    # gated so an AI-ported node's frag stays byte-identical.
    if ((nd_lowered is not None or deform_lowered is not None)
            and LOWERED_GUARD_INCLUDE not in includes):
        includes.append(LOWERED_GUARD_INCLUDE)
    if is_deformer:
        includes.append("maya/%s.h" % base)
        includes += _DEFORMER_INCLUDES
    # Sanctioned texture/file node: it reads its image in compute() via MImage.
    # A blessed-texture compute also loads via MImage (nd_tex_load_linear).
    if sg.get("reads_image_file") or blessed_tex:
        includes.append("maya/MImage.h")
    # Blessed bake: MImage write + the containers nd_tex_write builds its row
    # buffer with (MImage.h may already be in from the read gate above).
    if blessed_write:
        for _inc in file_texture_cpp.WRITE_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    # Full-parity OR blessed-texture mPyFile needs the cache block's extra std
    # headers (the NdTexCache math + load).
    if need_tex_cache:
        for _inc in file_texture_cpp.CACHE_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    if seq_desc:
        for _inc in file_texture_cpp.SEQ_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    # Lightweight raw-image cache needs <mutex> (MImage.h already added above).
    if raw_img_cache:
        for _inc in file_texture_cpp.RAW_CACHE_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    # Multi-file composite cache needs <string>/<mutex> (MImage.h added above).
    if composite_img_cache:
        for _inc in file_texture_cpp.COMPOSITE_CACHE_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    # Embedded-image staging writes baked bytes to a temp file (<fstream>/<cstdlib>).
    if embedded_b64:
        for _inc in file_texture_cpp.EMBEDDED_STAGE_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    # Per-instance persistent state guards its members with a std::mutex.
    if nd_state_decls and "mutex" not in includes:
        includes.append("mutex")
    # hex attr transcode core uses std::string.
    has_hex = _spec_has_hex(spec)
    if has_hex and "string" not in includes:
        includes.append("string")
    # nurbsCurve INPUT: the read wraps the plug's kNurbsCurve MObject in an
    # MFnNurbsCurve, and the ported compute typically decomposes a basis matrix
    # to euler. Gated so every other node's frag stays byte-identical.
    if _spec_has_nurbs_curve(spec):
        for _inc in ("maya/MFnNurbsCurve.h", "maya/MPoint.h",
                     "maya/MPointArray.h", "maya/MDoubleArray.h",
                     "maya/MTransformationMatrix.h", "maya/MFn.h"):
            if _inc not in includes:
                includes.append(_inc)
    # mesh INPUT: the read wraps the plug's kMesh MObject in an MFnMesh, and the
    # ported compute queries points/topology. Gated so every other node's frag
    # stays byte-identical.
    if _spec_has_mesh(spec):
        for _inc in ("maya/MFnMesh.h", "maya/MPoint.h", "maya/MPointArray.h",
                     "maya/MFloatPointArray.h", "maya/MIntArray.h",
                     "maya/MFloatVectorArray.h", "maya/MItMeshVertex.h",
                     "maya/MFn.h"):
            if _inc not in includes:
                includes.append(_inc)
    # Closest-point mesh query (MMeshIntersector / MFnMesh::getClosestPoint). The
    # AI porter may not add #includes, so without this header the port cannot
    # compile -- it can only invent a different algorithm. Gated on the spec flag
    # so every other node's frag stays byte-identical.
    if sg.get("uses_mesh_intersector") \
            and MESH_INTERSECTOR_INCLUDE not in includes:
        includes.append(MESH_INTERSECTOR_INCLUDE)
    # packed INPUT: the whole typed array comes off ONE handle via
    # MFnDoubleArrayData / MFnIntArrayData. Gated so every other node's frag
    # stays byte-identical.
    if _spec_has_packed(spec):
        for _inc in PACKED_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    # nurbsSurface INPUT: MFnNurbsSurface + point/param arrays.
    if _spec_has_nurbs_surface(spec):
        for _inc in ("maya/MFnNurbsSurface.h", "maya/MPoint.h",
                     "maya/MPointArray.h", "maya/MDoubleArray.h",
                     "maya/MFn.h"):
            if _inc not in includes:
                includes.append(_inc)
    # Geo VALUE model (single geo OUTPUT, array geo IN/OUT): the Nd<Kind> struct +
    # nd_read_/nd_build_ helpers. Only the kinds actually used are emitted, so a
    # geo-INPUT-only node's frag stays byte-identical.
    geo_io_kinds = emit_geo_io.kinds_in_spec(spec)
    if geo_io_kinds:
        for _inc in emit_geo_io.geo_io_includes(geo_io_kinds):
            if _inc not in includes:
                includes.append(_inc)
    # component-tag read surface (self.<geo>.region(...) / .component_tags[...]):
    # MFnGeometryData / component decode headers ONLY when a tag is read, so
    # every non-tag geo node's frag stays byte-identical.
    if _spec_reads_component_tag(spec):
        from .nd_lower import GEO_TAG_INCLUDES
        for _inc in GEO_TAG_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    # mesh UV read surface (self.<mesh>.uvs): MFnMesh::getUVSetNames + getUVs need
    # MStringArray / MFloatArray, added ONLY when a UV read is present so every
    # non-UV mesh node's frag stays byte-identical (port cache intact).
    if _spec_reads_uv(spec):
        from .nd_lower import GEO_UV_INCLUDES
        for _inc in GEO_UV_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    # nd_io (ndio.read/write, np.fromfile/np.save, .tofile) -- same gating rule:
    # added ONLY when the source does file IO, keeping other frags identical.
    if nd_io_cpp.spec_uses_ndio(spec):
        for _inc in nd_io_cpp.NDIO_INCLUDES:
            if _inc not in includes:
                includes.append(_inc)
    for _inc in cmd_out["includes"]:
        if _inc not in includes:
            includes.append(_inc)

    lines = []
    lines.append("// %s -- generated %s skeleton (codegen)." % (type_name, base))
    lines.append("// Source mPyNode: %s (%s)" % (spec.get("source_node"), spec.get("mpy_type")))
    if is_deformer:
        lines.append("// Attributes + registration are final; the deform() body is a")
        lines.append("// stub/marked region to be filled by the AI porter.")
    else:
        lines.append("// Attributes + registration are final; the compute() body is a")
        lines.append("// stub to be filled by the AI porter (see marked region).")
    lines.append("")
    for inc in includes:
        lines.append("#include <%s>" % inc)
    lines.append("")
    # Verified, unit-tested file-texture math + per-instance cache, emitted just
    # above the class so compute() can call it (full-parity mPyFile OR a blessed-
    # texture custom compute that lowered to the nd_tex_* kernels).
    if need_tex_cache:
        lines.append(file_texture_cpp.MATH_CPP)
        if seq_desc:
            lines.append(file_texture_cpp.SEQ_CPP)
        lines.append(file_texture_cpp.CACHE_CPP)
        lines.append("")
    # Raw-image decode cache (custom-compute reads_image_file node), emitted just
    # above the class so compute() can call nd_img_load_raw().
    if raw_img_cache:
        lines.append(file_texture_cpp.RAW_CACHE_CPP)
        lines.append("")
    # Multi-file composite cache (string-array path input), emitted just above the
    # class so compute() can call nd_img_composite().
    if composite_img_cache:
        lines.append(file_texture_cpp.COMPOSITE_CACHE_CPP)
        lines.append("")
    # Baked embedded-image bytes + nd_img_embedded_path() staging helper, emitted
    # just above the class so the image-load glue can fall back to it (#98).
    if embedded_b64:
        import base64 as _b64
        lines.append(
            file_texture_cpp.make_embedded_stage_cpp(_b64.b64decode(embedded_b64)))
        lines.append("")
    # hex attr transcode helpers (encode/decode), emitted above the class so the
    # read/write sites can call them (only when the spec has a hex attr).
    if has_hex:
        lines.append(_HEX_CPP)
    # nd:: runtime, inlined so the deterministically-lowered compute/deform body
    # is self-contained (no -I path / link step). Guarded by the header's #ifndef.
    if nd_lowered is not None or deform_lowered is not None:
        lines.append(_nd_runtime_cpp())
        lines.append("")
        # nd_io sits ON TOP of nd:: (every accessor returns nd::Array<T>), so it
        # must follow the runtime. Own include guard -> idempotent in a bundle.
        if nd_io_cpp.spec_uses_ndio(spec):
            lines.append(nd_io_cpp.NDIO_CPP)
            lines.append("")
        # The blessed bake takes an nd::Array<T> too, so it follows the runtime
        # for the same reason nd_io does.
        if blessed_write:
            lines.append(file_texture_cpp.WRITE_CPP)
            lines.append("")
    # Geo value model (Nd<Kind> struct + read/build helpers), inlined above the
    # class so compute() can build/read geo outputs + array geo inputs. Own
    # include guard -> idempotent when bundled with other geo nodes.
    if geo_io_kinds:
        lines.append(emit_geo_io.geo_io_cpp(geo_io_kinds))
        lines.append("")
    lines.append("class %s : public %s {" % (cls, base))
    lines.append("public:")
    lines.append("    %s() {}" % cls)
    lines.append("    ~%s() override {}" % cls)
    lines.append("    static void*   creator() { return new %s(); }" % cls)
    lines.append("    static MStatus initialize();")
    if is_deformer:
        lines.append("    MStatus        deform(MDataBlock& block, MItGeometry& iter,")
        lines.append("                          const MMatrix& worldMatrix, unsigned int multiIndex) override;")
        lines.append("    MStatus        setDependentsDirty(const MPlug& plug, MPlugArray& affected) override;")
    else:
        lines.append("    MStatus        compute(const MPlug& plug, MDataBlock& data) override;")
    lines.append("    static MTypeId id;")
    for m in members + base_extra:
        lines.append("    static MObject %s;" % m["member"])
    # Persistent self.<x> the lowered compute latches across evals. A node MEMBER,
    # so it is created and destroyed with the node -- never a function-static
    # registry keyed on `this`, which dangles on reallocation, is never evicted,
    # and hands a deleted node's state to a new node at the same address.
    lines += nd_state_decls
    # Per-instance linearized-pixel cache + lock (full-parity OR blessed-texture).
    if need_tex_cache:
        lines.append(file_texture_cpp.CACHE_MEMBERS.rstrip("\n"))
    # Per-instance raw-image decode cache + lock (custom-compute file node).
    if raw_img_cache:
        lines.append(file_texture_cpp.RAW_CACHE_MEMBERS.rstrip("\n"))
    # Per-instance multi-file composite cache + lock (string-array path node).
    if composite_img_cache:
        lines.append(file_texture_cpp.COMPOSITE_CACHE_MEMBERS.rstrip("\n"))
    # Second raw cache slot for the (constant) staged embedded image (#98).
    # Raw path only: the blessed path retries through its by-path NdTexCache.
    if embedded_b64 and raw_img_cache:
        lines.append(file_texture_cpp.EMBEDDED_STAGE_MEMBERS.rstrip("\n"))
    # Per-instance file-IO document cache + lock (ndio / np.fromfile / np.save).
    if nd_io_cpp.spec_uses_ndio(spec):
        lines.append(nd_io_cpp.NDIO_MEMBERS.rstrip("\n"))
    lines.append("};")
    lines.append("")
    lines.append("MTypeId %s::id(%s);" % (cls, type_id))
    for m in members + base_extra:
        lines.append("MObject %s::%s;" % (cls, m["member"]))
    lines.append("")

    # initialize()
    lines.append("MStatus %s::initialize() {" % cls)
    lines.append("    MFnNumericAttribute nAttr;")
    lines.append("    MFnUnitAttribute    uAttr;")
    lines.append("    MFnMatrixAttribute  mAttr;")
    lines.append("    MFnEnumAttribute    eAttr;")
    lines.append("    MFnTypedAttribute   tAttr;")
    lines.append("    MFnCompoundAttribute cAttr;")
    lines.append("")
    for m in members + base_extra:
        lines += _create_lines(m)
        # SSOT flags the generic emitter does not carry (hidden / non-keyable /
        # connectable). AFTER _create_lines so a declared flag wins.
        lines += m.get("extra_flags", [])
    lines.append("")
    for m in members + base_extra:
        lines.append("    addAttribute(%s);" % m["member"])
    lines.append("")
    if is_deformer:
        # User inputs drive the inherited deformed-geometry output.
        for i in ins:
            lines.append("    attributeAffects(%s, MPxGeometryFilter::outputGeom);"
                         % i["member"])
        # ...and so do the framework plugs the MPx base did not supply, or the
        # compiled node would carry a targetGeometry that no downstream
        # evaluation ever notices (the interpreted node wires the same edge).
        for i in base_extra:
            if i["kind"] == "inputs" and i.get("affects"):
                lines.append(
                    "    attributeAffects(%s, MPxGeometryFilter::outputGeom);"
                    % i["member"])
        if base == "MPxSkinCluster":
            # Inherited influence plugs must re-trigger deform too.
            lines.append("    attributeAffects(MPxSkinCluster::matrix, MPxGeometryFilter::outputGeom);")
            lines.append("    attributeAffects(MPxSkinCluster::bindPreMatrix, MPxGeometryFilter::outputGeom);")
    else:
        # createColor auto-makes R/G/B float children but codegen never captured
        # their MObjects. The LEGACY software swatch renderer (Hypershade
        # Materials/Textures swatch) pulls outColor's children (outColorR/G/B)
        # individually -- if no input attributeAffects those children, they never
        # go dirty, compute() doesn't re-run per swatch sample, and the swatch
        # renders black/partial. Fetch the children off the compound and wire the
        # same input->child affects the Python mPyFile node declares explicitly.
        color_children = {}  # out member -> (r, g, b) child var names
        # base_extra too: outTransparency is a createColor output, so its R/G/B
        # need the same fetch before base_affects_lines can wire them.
        for o in outs + [m for m in base_extra if m["kind"] == "outputs"]:
            if o["meta"].get("type") == "color" and not o["meta"].get("is_array"):
                cm = o["member"]
                rv, gv, bv = cm + "_r", cm + "_g", cm + "_b"
                lines.append("    MObject %s, %s, %s;" % (rv, gv, bv))
                lines.append("    {")
                lines.append("        MFnNumericAttribute _ccaff(%s);" % cm)
                lines.append("        %s = _ccaff.child(0);" % rv)
                lines.append("        %s = _ccaff.child(1);" % gv)
                lines.append("        %s = _ccaff.child(2);" % bv)
                lines.append("    }")
                color_children[cm] = (rv, gv, bv)
        # quaternion outputs: wire the same input->child affects so a downstream
        # connection on qX/qY/qZ/qW re-runs compute (4 children, fetched via
        # MFnCompoundAttribute).
        for o in outs:
            if o["meta"].get("type") == "quaternion" and not o["meta"].get("is_array"):
                cm = o["member"]
                xv, yv, zv, wv = cm + "_x", cm + "_y", cm + "_z", cm + "_w"
                lines.append("    MObject %s, %s, %s, %s;" % (xv, yv, zv, wv))
                lines.append("    {")
                lines.append("        MFnCompoundAttribute _qcaff(%s);" % cm)
                lines.append("        %s = _qcaff.child(0);" % xv)
                lines.append("        %s = _qcaff.child(1);" % yv)
                lines.append("        %s = _qcaff.child(2);" % zv)
                lines.append("        %s = _qcaff.child(3);" % wv)
                lines.append("    }")
                color_children[cm] = (xv, yv, zv, wv)
        for o in outs:
            for i in ins:
                lines.append("    attributeAffects(%s, %s);" % (i["member"], o["member"]))
                for ch in color_children.get(o["member"], ()):
                    lines.append("    attributeAffects(%s, %s);" % (i["member"], ch))
        # The two quadrants the loop above cannot reach (base outputs, and base
        # inputs driving the spec outputs). uvFilterSize / _timeIn / osl are
        # excluded there by design -- see base_affects_lines.
        lines += file_texture_cpp.base_affects_lines(ins, outs, base_extra,
                                                     color_children)
    lines.append("    return MS::kSuccess;")
    lines.append("}")
    lines.append("")

    # Companion MPxCommand classes (Methods @maya_command), placed after
    # <cls>::id + initialize(); the bundler namespace-wraps this region so two
    # nodes' commands can't collide in a merged plug-in.
    if cmd_out["classes"]:
        lines.append(cmd_out["classes"])
        lines.append("")

    # compute() or deform()
    if is_deformer:
        # Whether the deform must build the live-target CSR: the lowering bound
        # those reads, so the emitter has to declare what they bind TO. Decided
        # here because the blessed calls are only visible through the desugar
        # (see _called_method_reads) -- the emitter sees the raw spec.
        live_targets = (deform_lowered is not None
                        and bool(set(LIVE_CPP_VARS)
                                 & _called_method_reads(spec)))
        lines += _deform_lines(cls, ins, spec, base, for_port,
                               lowered=deform_lowered, img_read=img_read,
                               img_embedded=bool(embedded_b64),
                               base_extra=base_extra,
                               live_targets=live_targets)
        lines.append("")
        lines += _setdirty_lines(cls, ins, base, base_extra)
    else:
        lines += _compute_lines(cls, ins, outs, spec, for_port,
                                lowered=nd_lowered, img_read=img_read,
                                img_embedded=bool(embedded_b64),
                                base_extra=base_extra)
    lines.append("")

    # registration
    lines.append("MStatus initializePlugin(MObject obj) {")
    lines.append('    MFnPlugin plugin(obj, "mpynode-native", "1.0", "Any");')
    _reg_pre = "MStatus _st = " if cmd_out["register"] else "return "
    _reg_pad = " " * (4 + len(_reg_pre) + len("plugin.registerNode("))
    if is_deformer:
        node_kind = ("MPxNode::kSkinCluster" if base == "MPxSkinCluster"
                     else "MPxNode::kDeformerNode")
        lines.append('    %splugin.registerNode("%s", %s::id, %s::creator,'
                     % (_reg_pre, type_name, cls, cls))
        lines.append("%s%s::initialize, %s);" % (_reg_pad, cls, node_kind))
    else:
        # A texture/shader node (e.g. a compiled mPyFile) carries a Hypershade
        # classification so it shows in the Create panel + gets a swatch + auto
        # place2dTexture. Use the classification overload when the spec has one.
        classif = sg.get("classification")
        if classif:
            lines.append('    MString _classif("%s");' % classif)
            lines.append('    %splugin.registerNode("%s", %s::id, %s::creator, '
                         '%s::initialize, MPxNode::kDependNode, &_classif);'
                         % (_reg_pre, type_name, cls, cls, cls))
        else:
            lines.append('    %splugin.registerNode("%s", %s::id, %s::creator, %s::initialize);'
                         % (_reg_pre, type_name, cls, cls, cls))
    if cmd_out["register"]:
        lines.append("    if (!_st) return _st;")
        for _reg in cmd_out["register"]:
            lines.append("    " + _reg)
        lines.append("    return _st;")
    lines.append("}")
    lines.append("")
    lines.append("MStatus uninitializePlugin(MObject obj) {")
    lines.append("    MFnPlugin plugin(obj);")
    for _dereg in cmd_out["deregister"]:
        lines.append("    " + _dereg)
    lines.append("    return plugin.deregisterNode(%s::id);" % cls)
    lines.append("}")
    lines.append("")
    return "\n".join(lines)
