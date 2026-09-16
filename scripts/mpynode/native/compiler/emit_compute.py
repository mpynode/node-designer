"""compute() body emission (MPxNode)."""
from __future__ import annotations

import ast
import io
import re
import tokenize

from mpynode.native.compiler.kernels import file_texture_cpp
from .errors import UnsupportedSpec
from .spec_model import PORT_BEGIN, PORT_END, _CPP, lowered_guard
from .emit_attr import (
    _UNSET, _array_read_lines, _array_write_lines, _image_read_lines,
    _out_handle_default, _out_setclean, _read_line, _scal_out_finalize,
    _scal_out_handle_lines, _scal_out_hint, _write_lines,
)
from . import emit_geo_io


def _self_attr_refs(src: str) -> set:
    """Names referenced as ``self.<name>`` in real CODE (not comments/strings).

    Tokenizing skips COMMENT/STRING tokens so a ``self.foo`` mentioned only in a
    comment or a string literal is not returned. Mirrors
    ``spec_extractor._self_attr_refs`` (kept local so emit_compute stays free of
    the Maya-importing spec package)."""
    refs: set = set()
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src or "").readline))
    except Exception:
        stripped = re.sub(r"#.*", "", src or "")
        stripped = re.sub(r"(['\"]).*?\1", "", stripped)
        return set(re.findall(r"\bself\.([A-Za-z_]\w*)", stripped))
    for i in range(len(toks) - 2):
        a, b, c = toks[i], toks[i + 1], toks[i + 2]
        if (a.type == tokenize.NAME and a.string == "self"
                and b.type == tokenize.OP and b.string == "."
                and c.type == tokenize.NAME):
            refs.add(c.string)
    return refs


def _self_attr_writes(src: str) -> set:
    """Names ASSIGNED as ``self.<name>`` (whole, subscript, aug, or a ``for``
    loop target) anywhere in ``src``. A self attr that is written has a
    definition inside the port (a persistent-state local the porter models) and
    is therefore NOT an unbound external read."""
    written: set = set()
    try:
        tree = ast.parse(src or "")
    except Exception:
        return written

    def _mark(target):
        node = target
        while isinstance(node, ast.Subscript):
            node = node.value
        # Unpacking targets nest: `self.a, self.b = f()`, `self.h, *self.t = v`,
        # `[self.x], = y`. Without recursing, the two commonest ways to write
        # two outputs at once look like no write at all.
        if isinstance(node, ast.Starred):
            return _mark(node.value)
        if isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                _mark(elt)
            return
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "self"):
            written.add(node.attr)

    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                _mark(t)
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            _mark(n.target)
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            _mark(n.target)
        elif isinstance(n, ast.With):
            for item in n.items:
                if item.optional_vars is not None:
                    _mark(item.optional_vars)
    return written


def unassigned_output_plugs(out_plugs, compute_src) -> set:
    """Declared outputs the compute NEVER assigns.

    The port scaffold used to instruct the model to "populate" every declared
    output while also telling it to translate the Python faithfully. When the
    Python assigns only some of them those instructions contradict each other,
    and the model resolves the contradiction by INVENTING values -- one real
    node harvested the discarded ``d, idx`` locals of a ``cKDTree(...).query()``
    into two outputs its Python never wrote. Naming the gap removes the
    contradiction.

    Returns an EMPTY set when the answer cannot be trusted -- an unparseable
    compute, or no compute at all. A false positive here would tell the model to
    leave a genuinely-written output untouched, which is worse than the bug this
    fixes, so silence is the safe direction. Also consumed by the parity verify
    (``verify._count_mismatch_reason``), which is why it is public.
    """
    src = compute_src or ""
    if not src.strip():
        return set()
    try:
        tree = ast.parse(src)
    except Exception:
        return set()
    # Anything that lets `self` be written where this scan cannot see it makes
    # the answer untrustworthy, and a wrong answer tells the model to leave a
    # REAL output empty. Three escapes: setattr, self handed to a helper
    # (`solve(self)`), and a method call on self. A call on a self ATTRIBUTE --
    # `self.inMesh.getPoints()` -- is NOT an escape (that would silence the scan
    # for nearly every node).
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        if (isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "self"):
            return set()
        for arg in list(n.args) + [k.value for k in (n.keywords or [])]:
            if isinstance(arg, ast.Name) and arg.id == "self":
                return set()
    written = _self_attr_writes(src)
    return {p for p in out_plugs if p not in written}


def _unbound_self_reads(ins, outs, spec) -> set:
    """``self.<attr>`` names the compute/init READ that the compiled plain-MPxNode
    port can never bind: not a declared input (``in_<name>``), not a declared
    output (``h_<name>``/``out_<name>``), and never assigned anywhere in the
    compute/init (so their value is not produced inside the port either).

    Such a read pulls a value from OUTSIDE the node -- a stored variable set by
    external setup, or a live scene query -- which the compiled node has no way to
    obtain; the AI port would compile but silently no-op. Returns the offending
    names (empty set = clean)."""
    src  = "%s\n%s" % (spec.get("compute") or "", spec.get("init") or "")
    refs = _self_attr_refs(src)
    if not refs:
        return set()
    declared = {i["plug"] for i in ins} | {o["plug"] for o in outs}
    written  = _self_attr_writes(src)
    return {r for r in refs if r not in declared and r not in written}


def _compute_lines(cls, ins, outs, spec, for_port, lowered=_UNSET,
                   img_read=False, img_embedded=False, base_extra=()):
    """Body of compute(); phase-1 stub or AI-fill port scaffold.

    ``img_read``/``img_embedded`` come from node_scaffold, which DECLARED the
    image caches -- this emitter must not re-derive them from the spec, or the
    body can call a cache the class body never declared (or, worse, promise the
    porter a buffer that was suppressed).

    ``base_extra`` are the mPyFile BASE plugs (node_scaffold owns their member
    names). They stay OUT of ``ins``/``outs`` so the ported / lowered body is
    unchanged, but the base OUTPUTS still have to pass the plug guard -- a
    shader that pulls only ``outTransparency`` would otherwise get
    kUnknownParameter and read a stale value -- and be written by the derived
    tail at the end of finalize."""
    base_outs = [m for m in base_extra if m["kind"] == "outputs"]
    derived   = file_texture_cpp.derived_output_lines(ins, outs, base_extra, spec)
    L         = ["MStatus %s::compute(const MPlug& plug, MDataBlock& data) {" % cls]
    if outs or base_outs:
        guard = " && ".join("plug != %s" % o["member"]
                            for o in list(outs) + base_outs)
        L.append("    if (%s)" % guard)
        L.append("        return MS::kUnknownParameter;")
    L.append("")
    L.append("    // --- inputs ---")
    for i in ins:
        if emit_geo_io.is_geo(i["meta"]["type"]) and i["meta"].get("is_array"):
            # multi (list) geo input -> std::vector<Nd<Kind>> in_<m>
            L += emit_geo_io.geo_array_input_lines(i)
        elif i["meta"].get("is_array"):
            L += _array_read_lines(i)
        else:
            rl = _read_line(i)
            if rl:
                L.append(rl)
    L.append("")

    # Geo outputs (single + array) are their own class: they declare an Nd<Kind>
    # value buffer and build+set it (they would KeyError in _OUT_DEFAULT /
    # _elem_set_stmt on the numeric paths).
    geo_outs = [o for o in outs if emit_geo_io.is_geo(o["meta"]["type"])]
    scal_outs = [o for o in outs if not o["meta"].get("is_array")
                 and not emit_geo_io.is_geo(o["meta"]["type"])]
    arr_outs = [o for o in outs if o["meta"].get("is_array")
                and not emit_geo_io.is_geo(o["meta"]["type"])]

    def _arr_decls():
        return ["    std::vector<%s> out_%s;" % (_CPP[o["meta"]["type"]], o["member"])
                for o in arr_outs]

    def _geo_out_decls():
        L2 = []
        for o in geo_outs:
            L2 += emit_geo_io.geo_out_decls(o)
        return L2

    def _geo_out_writes():
        L2 = []
        for o in geo_outs:
            L2 += emit_geo_io.geo_output_lines(o)
        return L2

    # Full-parity mPyFile: emit the DETERMINISTIC verified-helper texture pipeline
    # (cached MImage load + linearize + prefilter + bilinear sample) as the compute
    # body. The math is codegen-emitted and unit-tested (file_texture_cpp.py), so
    # there is no AI PORT region and parity holds by construction.
    if file_texture_cpp.use_full_parity_glue(spec):
        L.append("    // --- output handles ---")
        for o in scal_outs:
            L += _out_handle_default(o)
        L.append("")
        L.append("    // --- verified file-texture pipeline (cached load + sample) ---")
        L += file_texture_cpp.compute_glue_lines(
            ins, outs, tail=file_texture_cpp.full_parity_tail(spec),
            seq=file_texture_cpp.full_parity_seq(spec))
        L.append("")
        L.append("    // --- finalize ---")
        for o in scal_outs:
            L.append(_out_setclean(o))
        L += derived
        L.append("")
        L.append("    return MS::kSuccess;")
        L.append("}")
        return L

    # Deterministic numpy->C++ lowering. If the ENTIRE compute block lowers to
    # pure C++ -- every referenced input/output a supported numeric type, every
    # construct supported, every declared output written -- emit it as the compute
    # body with NO AI PORT region; parity is guaranteed by py_to_cpp.py +
    # nd_lower.py, both parity-tested Maya-free. Otherwise try_lower_compute
    # returns None and we fall through to the AI-porter scaffold unchanged.
    # Imported lazily to break the codegen<->py_to_cpp<->nd_lower import cycle.
    if lowered is _UNSET:
        from mpynode.native.compiler import nd_lower
        lowered = nd_lower.try_lower_compute(ins, outs, spec)
    if lowered is not None:
        L.append("    // --- output handles ---")
        for o in scal_outs:
            L += _out_handle_default(o)
        L += _arr_decls()
        L += _geo_out_decls()
        L.append("")
        L.append("    // --- deterministic numpy->C++ lowered compute (no port) ---")
        L += lowered_guard(spec["suggested"]["node_type_name"], lowered,
                           ["return MS::kFailure;"])
        L.append("")
        L.append("    // --- finalize ---")
        for o in scal_outs:
            L.append(_out_setclean(o))
        for o in arr_outs:
            L += _array_write_lines(o)
        L += _geo_out_writes()
        L += derived
        L.append("")
        L.append("    return MS::kSuccess;")
        L.append("}")
        return L

    # Blessed-method honest-reject. The compute CALLS a blessed API method
    # (self.read_texture()/self.sample_texture()) but did NOT fully lower, so it
    # would go to the AI porter. A blessed call has a DETERMINISTIC C++ kernel by
    # contract; AI-porting it risks a non-parity reimplementation of the very
    # thing we bless. (The full-parity default node already returned above, so
    # this fires only for a custom blessed compute that failed to lower.)
    if (file_texture_cpp.uses_blessed_texture(spec)
            or file_texture_cpp.uses_blessed_write(spec)):
        _blessed = set()
        if file_texture_cpp.uses_blessed_texture(spec):
            _blessed |= file_texture_cpp._blessed_texture_names(spec)
        if file_texture_cpp.uses_blessed_write(spec):
            _blessed |= file_texture_cpp.blessed_write_names(spec)
        raise UnsupportedSpec(
            "compute calls blessed method(s) %s but does not fully lower to C++; "
            "refusing to AI-port a blessed call"
            % ", ".join(sorted(_blessed)))

    # Phase-0 honest-reject guard. The deterministic path declined, so this node
    # would be AI-ported -- and the plain-MPxNode porter binds ONLY declared
    # inputs (`in_<name>`) and outputs (`h_<name>`/`out_<name>`), nothing else.
    # A self.<attr> neither declared nor assigned anywhere in compute/init gets
    # its value from OUTSIDE the compiled node (a stored var set by external
    # setup, or a live scene query) and cannot be reconstructed at runtime; the
    # port would compile but silently emit identity/default outputs. Reject
    # honestly (-> build_status "dropped"). Catches procrustes_cluster/tags,
    # which read self.clusters / self.clusterTags / self.bindMatrices, none
    # of them declared.
    # Reached ONLY for the plain-MPxNode + texture family (node_scaffold sends
    # geo/deformer/locator/iksolver/transform to emitters with their own
    # self.<attr> contract); texture presets are merged into ins/outs, and
    # in-source-written state (spring_chain velocity, dnet previous) is not a
    # read-only orphan.
    orphans = _unbound_self_reads(ins, outs, spec)
    if orphans:
        raise UnsupportedSpec(
            "compute reads undeclared self attr(s) %s -- not a declared input/"
            "output and never assigned, so the compiled node cannot obtain their "
            "value; refusing to ship a silent no-op port"
            % ", ".join(sorted(orphans)))

    if for_port:
        if img_read:
            L += _image_read_lines(ins, embedded=img_embedded)
            L.append("")
        L.append("    // --- output handles / buffers (fill below) ---")
        for o in scal_outs:
            L += _scal_out_handle_lines(o)
        L += _arr_decls()
        L += _geo_out_decls()
        L.append("")
        L.append("    " + PORT_BEGIN)
        L.append("    // Inputs are in `in_<name>` (arrays are std::vector<...>).")
        if img_read:
            L.append("    // The image file is loaded above into _imgPixels "
                     "(RGBA8, _imgW x _imgH, _imgOK); translate the Python")
            L.append("    // pixel read/sample (PIL/cv2) against it -- do NOT "
                     "call imread/Image.open in C++.")
        # Only ask for the outputs the Python actually writes. Listing all of
        # them contradicts "translate faithfully" for a node that writes some,
        # and the model resolves that by inventing the rest.
        _unassigned = unassigned_output_plugs([o["plug"] for o in outs],
                                              spec.get("compute"))
        _skip = [o for o in (scal_outs + arr_outs + geo_outs)
                 if o["plug"] in _unassigned]
        L.append("    // Write these outputs:")
        for o in scal_outs:
            if o["plug"] not in _unassigned:
                L.append(_scal_out_hint(o))
        for o in arr_outs:
            if o["plug"] not in _unassigned:
                L.append("    //   populate std::vector out_%s (one entry per output element)"
                         % o["member"])
        for o in geo_outs:
            if o["plug"] in _unassigned:
                continue
            _k = emit_geo_io.geo_kind_of(o["meta"]["type"])
            if o["meta"].get("is_array"):
                L.append("    //   populate std::vector out_%s (one Nd%s per list "
                         "element: fill .points/.counts/.indices etc.)"
                         % (o["member"], _k.capitalize()))
            else:
                L.append("    //   fill out_%s (an Nd%s: .points/.counts/.indices "
                         "for mesh, .cvs/.degree for curve/surface)"
                         % (o["member"], _k.capitalize()))
        if _skip:
            L.append("    // The Python NEVER assigns the output(s) below. Leave "
                     "them UNTOUCHED -- do not size them,")
            L.append("    // do not fill them, and do not infer values for them "
                     "from discarded locals. An output the")
            L.append("    // reference does not write must stay empty, or the "
                     "port ships behaviour the Python has not:")
            # Name the symbol that actually exists in the file: a plain scalar
            # writes its live handle (h_<member>) and has no out_ buffer -- only
            # hex scalars, arrays and geo do.
            _buffered = {o["plug"] for o in scal_outs if o["meta"]["type"] == "hex"}
            _buffered |= {o["plug"] for o in (arr_outs + geo_outs)}
            for o in _skip:
                _sym = ("out_%s" if o["plug"] in _buffered else "h_%s") % o["member"]
                L.append("    //   %s (self.%s)" % (_sym, o["plug"]))
        L.append("    // Original Python compute (translate faithfully):")
        for src_line in (spec.get("compute") or "").splitlines():
            L.append("    //   | %s" % src_line)
        L.append("    " + PORT_END)
        L.append("")
        L.append("    // --- finalize ---")
        for o in scal_outs:
            L += _scal_out_finalize(o)
        for o in arr_outs:
            L += _array_write_lines(o)
        L += _geo_out_writes()
    else:
        L += _arr_decls()
        L += _geo_out_decls()
        L.append("    " + PORT_BEGIN)
        L.append("    // TODO: translate the Python compute below into C++.")
        for src_line in (spec.get("compute") or "").splitlines():
            L.append("    //   | %s" % src_line)
        L.append("    " + PORT_END)
        L.append("")
        L.append("    // --- outputs (stub defaults) ---")
        for o in scal_outs:
            L += _write_lines(o)
        for o in arr_outs:
            L += _array_write_lines(o)
        L += _geo_out_writes()

    L += derived
    L.append("")
    L.append("    return MS::kSuccess;")
    L.append("}")
    return L
