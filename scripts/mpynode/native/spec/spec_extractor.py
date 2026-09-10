"""mPyNode -> structured JSON spec for the native (C++) plugin porter.

Read-only introspection of a live mpynode into a JSON-serializable dict that
the codegen + AI porter consume to emit an MPxNode plugin. Captures the typed
attributes (with limits/defaults/enum names), the Compute + Init expressions,
stored variables (summarized, with a "bake" hint for large data), the target
MPx base class, and a PORTABILITY assessment -- what can be auto-ported to C++
versus what blocks it (arbitrary-Python libs, scene access, python-typed
attrs).

Maya is imported lazily inside ``extract_spec`` so the pure helpers (type
mapping, portability scan, id suggestion) are importable + testable without a
Maya session.

CLI (inside Maya, or mayapy):  python spec_extractor.py <nodeName>
"""

from __future__ import annotations

import json
import re

SCHEMA_VERSION = 1

# mPy maya nodeType -> target C++ MPx base + porting note + heaviness.
_MPX_BASE = {
    "mPyNode": ("MPxNode", "plain dependency node", "easy"),
    "mPyTransform": ("MPxTransform", "custom transform matrix", "medium"),
    "mPyDeformer": ("MPxDeformerNode", "per-point mesh deform", "medium"),
    "mPySkinCluster": ("MPxSkinCluster", "custom skinning", "hard"),
    "mPyConstraint": ("MPxNode", "constraint emulated as a DG node", "medium"),
    "mPyMesh": ("MPxNode", "outputs a mesh data attr", "medium"),
    "mPyNurbsCurve": ("MPxNode", "outputs a nurbsCurve data attr", "medium"),
    "mPyNurbsSurface": ("MPxNode", "outputs a nurbsSurface data attr", "medium"),
    "mPyFile": ("MPxNode", "texture/file evaluation node", "medium"),
    "mPyLocator": ("MPxLocatorNode", "viewport draw override (MUIDrawManager)", "hard"),
    # mPyBlendShape is an MPxDeformerNode, so it ports via the deformer codegen.
    "mPyBlendShape": ("MPxDeformerNode", "expression blendShape (deformer-based)", "medium"),
    # mPyIkSolver -> doSolve codegen (dedicated emitter).
    "mPyIkSolver": ("MPxIkSolverNode", "custom IK solver (doSolve)", "hard"),
}

# Geometry GENERATORS (the emit_geo family). Mirrors compiler.spec_model._GEO_KIND
# without importing the compiler layer into the spec layer.
_GEO_GENERATOR_TYPES = ("mPyMesh", "mPyNurbsCurve", "mPyNurbsSurface")

# Other node types whose EMITTER wires the cached MImage read (emit_deformer for
# the deformer family, emit_iksolver for the solver). Sanctioned for the same
# reason as the geometry generators: the node drives points/joints FROM an image
# and the mechanism is the identical cached MImage::readFromFile.
# mPyLocator and mPyTransform are deliberately ABSENT -- their emitters have no
# image wiring (the locator's ported body is Maya-free by contract; the
# transform's desiredLocal() is const), and sanctioning a base whose emitter
# cannot honour it is exactly the half-wired state this list exists to prevent.
_IMAGE_READ_BASE_TYPES = ("mPyDeformer", "mPySkinCluster", "mPyBlendShape",
                          "mPyIkSolver")

# mPy attr_type -> normalized C++ codegen hints.
#   cat   : coarse family
#   fn    : Maya attribute function set in initialize()
#   data  : the data/unit kind
#   cpp   : the C++ scalar/aggregate the compute reads/writes
#   read  : MDataHandle accessor
#   portable: representable natively at all?
_NORM_TYPE = {
    "float":  {"cat": "scalar", "fn": "MFnNumericAttribute", "data": "kFloat",   "cpp": "float",   "read": "asFloat",  "portable": True},
    "double": {"cat": "scalar", "fn": "MFnNumericAttribute", "data": "kDouble",  "cpp": "double",  "read": "asDouble", "portable": True},
    "int":    {"cat": "scalar", "fn": "MFnNumericAttribute", "data": "kInt",     "cpp": "int",     "read": "asInt",    "portable": True},
    "bool":   {"cat": "scalar", "fn": "MFnNumericAttribute", "data": "kBoolean", "cpp": "bool",    "read": "asBool",   "portable": True},
    "angle":  {"cat": "unit",   "fn": "MFnUnitAttribute",    "data": "kAngle",   "cpp": "double",  "read": "asMAngle","portable": True},
    "time":   {"cat": "unit",   "fn": "MFnUnitAttribute",    "data": "kTime",    "cpp": "double",  "read": "asMTime", "portable": True},
    "vector": {"cat": "vector", "fn": "MFnNumericAttribute", "data": "k3Double", "cpp": "double[3]","read": "asDouble3","portable": True},
    # float2 (mPyFile uvCoord/uvFilterSize) MUST stay a genuine float2 so it
    # connects to place2dTexture.outUV.
    "float2": {"cat": "vector2","fn": "MFnNumericAttribute", "data": "k2Float",  "cpp": "float[2]", "read": "asFloat2", "portable": True},
    # color: 3-float RENDERABLE compound (createColor/usedAsColor) -- binds to
    # material.color + Arnold, unlike a plain vector.
    "color":  {"cat": "color",  "fn": "MFnNumericAttribute", "data": "color",    "cpp": "float[3]", "read": "asFloat3", "portable": True},
    "euler":  {"cat": "vector", "fn": "MFnUnitAttribute*3",  "data": "kAngle*3", "cpp": "double[3]","read": "asDouble3","portable": True},
    # quaternion: generic compound of 4 doubles -- there is no numeric double4,
    # so children are read via MFnCompoundAttribute child handles (no asDouble4).
    "quaternion": {"cat": "quaternion", "fn": "MFnCompoundAttribute", "data": "kDouble*4", "cpp": "double[4]", "read": "child", "portable": True},
    "matrix": {"cat": "matrix", "fn": "MFnMatrixAttribute",  "data": "kDouble",  "cpp": "MMatrix", "read": "asMatrix", "portable": True},
    "enum":   {"cat": "enum",   "fn": "MFnEnumAttribute",    "data": "enum",     "cpp": "short",   "read": "asShort",  "portable": True},
    "string": {"cat": "string", "fn": "MFnTypedAttribute",   "data": "kString",  "cpp": "MString", "read": "asString", "portable": True},
    "hex":    {"cat": "string", "fn": "MFnTypedAttribute",   "data": "kString",  "cpp": "MString", "read": "asString", "portable": True},
    "mesh":   {"cat": "geo",    "fn": "MFnTypedAttribute",   "data": "kMesh",        "cpp": "MObject", "read": "asMesh",        "portable": True},
    "nurbsCurve":   {"cat": "geo", "fn": "MFnTypedAttribute","data": "kNurbsCurve",  "cpp": "MObject", "read": "asNurbsCurve",  "portable": True},
    "nurbsSurface": {"cat": "geo", "fn": "MFnTypedAttribute","data": "kNurbsSurface","cpp": "MObject", "read": "asNurbsSurface","portable": True},
    # Arbitrary pickled Python -- no native representation.
    "python": {"cat": "python", "fn": None, "data": None, "cpp": None, "read": None, "portable": False},
}

# Libraries with no DETERMINISTIC C++ lowering (network, dataframes, ML, plotting).
# NOT a gate: reported as ``unported`` -> AI-porter context. "We have not written
# the port" is about this compiler, not the code; valid Python is never refused.
_HARD_BLOCKER_LIBS = (
    "requests", "urllib", "pandas", "sklearn", "torch", "tensorflow",
    "matplotlib", "PySide", "PySide2", "PySide6", "PyQt",
)

# Libraries whose *math* subset IS portable -- the codegen + porter reverse-engineer
# the vectorized / JIT / image-array code into C++ loops (see
# native/ai/translation_knowledge.py). Warning + guidance, NOT a blocker; specific
# non-portable calls inside them are caught by _NONPORTABLE_PATTERNS below.
_PORTABLE_MATH_LIBS = ("numpy", "scipy", "numba", "PIL", "cv2", "skimage")

# RNG calls. SUPPORTED -- mapped to C++ <random> (translation_knowledge.RANDOM).
# The compiled node re-seeds a std::mt19937 each compute() from its inputs, so it
# stays a deterministic pure function (stable per frame/seed) but is NOT
# bit-identical to Python's PRNG. A WARNING, not a blocker; gates the parity skip.
_RNG_PATTERNS = [
    re.compile(r"\b(?:np|numpy)\.random\b"),
    re.compile(r"\b(?:random|secrets)\.(?:random|randint|uniform|choice|seed|"
               r"shuffle|gauss|normalvariate|randrange|sample|betavariate|"
               r"expovariate)\b"),
    re.compile(r"\bdefault_rng\b"),
]


def uses_rng(src: str) -> bool:
    """True if ``src`` uses numpy.random / random / secrets / default_rng."""
    return any(p.search(src or "") for p in _RNG_PATTERNS)


def spec_uses_rng(spec) -> bool:
    """True if a porter spec's compute+init uses RNG (used to skip parity)."""
    try:
        src = "%s\n%s" % (spec.get("compute") or "", spec.get("init") or "")
    except Exception:
        return False
    # Same input assess_portability feeds uses_rng: real CODE only. A `#` comment
    # or string literal that merely MENTIONS np.random must not read as RNG here
    # -- this verdict gates the verify.py parity SKIP, so a false True ships a
    # node whose numeric parity was never checked.
    return uses_rng(_strip_comments_strings(src))


def spec_reads_image_file(spec) -> bool:
    """True if a porter spec was flagged as reading an image file in compute
    (a sanctioned texture/file node). Drives the MImage codegen + the loose/skip
    verify. Mirrors :func:`spec_uses_rng`."""
    return bool((spec.get("suggested") or {}).get("reads_image_file"))


# Constructs with no deterministic C++ lowering even inside an otherwise-portable
# library. Each entry is (compiled-regex, human reason), reported as ``unported``
# (AI-porter context), never a gate.
# Image-FILE READS. Unported by DEFAULT (pixels should enter via a Maya input) but
# SANCTIONED for texture/file nodes (allow_file_read=True), where they port to
# MImage::readFromFile and the node carries ``reads_image_file`` (loose/skip
# verify). Only the file-path READ is carved out; writes, buffer-decode, GUI and
# bare open() stay in _NONPORTABLE_PATTERNS below.
_IMAGE_READ_PATTERNS = [
    (re.compile(r"\bcv2\.imread\b"), "cv2.imread"),
    (re.compile(r"\b(?:Image|PIL\.Image)\.open\b"), "PIL.Image.open"),
    (re.compile(r"\bskimage\.io\.imread\b|\bio\.imread\b"), "skimage io.imread"),
    # Maya's own reader (mPyFile loads pixels via MImage, no PIL) -> ported to
    # MImage::readFromFile; carries reads_image_file (loose/skip verify).
    (re.compile(r"\.readFromFile\b"), "MImage.readFromFile"),
    # The FRAMEWORK read. A node that calls the blessed read_texture() loads its
    # image inside file_texture_ops, so NO reader call appears in the node's own
    # source and the patterns above cannot see it -- but the node reads an image
    # FILE exactly as a hand-rolled loader did, and reads_image_file is what wires
    # fileName, the MImage codegen and the loose/skip verify. Matched on any
    # receiver: `self.` in a compute, `slf.` in an Init helper.
    (re.compile(r"\.read_texture\s*\("), "self.read_texture"),
]

# Closest-point mesh queries. No DETERMINISTIC lowering (nd_lower has no kernel),
# so reported as ``unported`` -- but unlike the entries below the C++ API is the
# SAME class with the same methods, so the reason names the 1:1 mapping instead of
# a dead end. A hit also sets ``uses_mesh_intersector``, which emits
# <maya/MMeshIntersector.h> into the scaffold: the porter may not add #includes
# (native/ai/prompt.py), so without the header a closest-point port cannot compile
# and can only fabricate a different algorithm. Matched on the dot (or class name)
# so an aliased module cannot evade them.
_MESH_QUERY_PATTERNS = [
    (re.compile(r"\bMMeshIntersector\b"), "MMeshIntersector"),
    (re.compile(r"\bMPointOnMesh\b"), "MPointOnMesh"),
    (re.compile(r"\.getClosestPoint(?:AndNormal)?\s*\("), "getClosestPoint"),
]


_NONPORTABLE_PATTERNS = [
    (re.compile(r"\bcv2\.(?:imwrite|imshow|waitKey|imencode|imdecode|"
                r"VideoCapture|VideoWriter|namedWindow|destroyAllWindows)\b"),
     "cv2 file-write / GUI / video / buffer-decode I/O (not portable)"),
    (re.compile(r"\bcv2\.(?:dnn|cuda|ml)\b|\bCascadeClassifier\b"),
     "cv2 GPU / trained-model / DNN (loads external state; not portable)"),
    (re.compile(r"\b(?:Image|PIL\.Image)\.(?:save|show)\b"),
     "PIL file write / display (not portable)"),
    (re.compile(r"\bImageGrab\b|\bImageDraw\b|\bImageFont\b"),
     "PIL screen-grab / font rasterization (GUI; not portable)"),
    (re.compile(r"\bskimage\.data\b|\bskimage\.io\.imsave\b|\bio\.imsave\b"),
     "skimage file write / bundled sample data (not portable)"),
    (re.compile(r"@?\bcuda\.(?:jit|grid)\b|\bnumba\.cuda\b|\bnumba\.roc\b"),
     "numba GPU (cuda/roc) kernels (no GPU in the plugin)"),
    (re.compile(r"\bobjmode\b"),
     "numba objmode (calls back into the Python interpreter; not portable)"),
    (re.compile(r"\bscipy\.(?:optimize|integrate|sparse|fft|fftpack|stats|io|"
                r"cluster)\b"),
     "heavy scipy submodule (no auto-port path yet -- documented gap)"),
    # scipy.spatial is NOT wholesale unported: cKDTree / KDTree lower to the
    # nd::KDTree kernel, so flagging the whole submodule falsely told a
    # deterministically-compiling node it had "no auto-port path yet". Only the
    # constructs with no kernel are named, and every alternative stays ANCHORED on
    # scipy.spatial: matching bare names would hit the procrustes_* templates,
    # which define their own pure-numpy `procrustes` and lower deterministically
    # (8 bare occurrences across templates/).
    (re.compile(r"\bscipy\.spatial\.(?:distance|transform)\b"
                r"|\bscipy\.spatial\.(?:Delaunay|ConvexHull|SphericalVoronoi|"
                r"Voronoi|HalfspaceIntersection|distance_matrix|procrustes|"
                r"geometric_slerp|minkowski_distance)\b"
                r"|\bfrom\s+scipy\.spatial\s+import\s+[^\n]*"
                r"\b(?:Delaunay|ConvexHull|SphericalVoronoi|Voronoi|"
                r"HalfspaceIntersection|distance_matrix|procrustes|"
                r"geometric_slerp|minkowski_distance)\b"),
     "scipy.spatial construct with no auto-port path yet -- documented gap "
     "(cKDTree / KDTree DO lower to a native kernel)"),
    # Bare open() is handled separately (_classify_opens + assess_portability) so a
    # texture node's SANCTIONED embedded-image staging is not a hard blocker.
    (re.compile(r"\bsocket\.\w"),
     "network socket (not portable)"),
    # ---- file I/O with NO C++ lowering ------------------------------------
    # Nothing to lower these TO, so they reach the AI PORTER -- which used to be a
    # silent-miscompile path (the prompt forbids I/O but nothing enforced it, the
    # only automatic gate is "it compiled", and verify is non-fatal, so an
    # LLM-authored std::ifstream shipped green). The guard is now at the OUTPUT:
    # the porter emits a PORT_INCOMPLETE marker instead of inventing a mechanism,
    # and the spliced body is scanned for this I/O (prompt.scan_ported_body).
    # Detection here is what TELLS the porter the construct has no path.
    # allow_file_read does not apply. Distinctive names are matched on the dot so
    # an alias (`import numpy as N`) cannot evade them; the ambiguous short names
    # (load/save) also get alias resolution in assess_portability. np.fromfile /
    # np.save / .tofile are NOT here: they carry an explicit dtype (or write
    # verbatim) and DO lower via nd_io. np.load has no dtype argument, so the
    # element type is whatever the file holds, while nd::Array<T> fixes T at
    # compile time.
    (re.compile(r"\b(?:np|numpy)\.(?:load|savez|savez_compressed|savetxt)\b"
                r"|\.(?:loadtxt|genfromtxt|memmap)\s*\("),
     "numpy file I/O that has no C++ lowering (np.load / np.savetxt / "
     "np.loadtxt / np.memmap ...) -- np.load in particular carries no dtype, so "
     "the compiled element type would be a guess; use ndio.read(path, 'name', "
     "dtype=...) instead, which reads .npy/.ndio/.json and names the dtype"),
    (re.compile(r"\.(?:read_text|read_bytes|write_text|write_bytes)\s*\("),
     "pathlib file read/write (not portable) -- use ndio.read / ndio.write"),
    (re.compile(r"\b(?:pickle|cPickle)\.\w"),
     "pickle (a stack VM with import opcodes; no C++ port at any tier)"),
    (re.compile(r"\bjson\.(?:load|loads|dump|dumps)\b"),
     "the json module returns a dict; the transpiler type lattice has no dict "
     "kind -- ndio.read(path, 'name') reads a flat JSON object of number arrays "
     "directly, and lowers"),
]

# Bare open() (not x.open(); PIL's Image.open is in _IMAGE_READ_PATTERNS). Used for
# the message when AST classification is unavailable; the real gate is
# _classify_opens (AST-based, mode-aware).
_OPEN_RE = re.compile(r"(?<![\w.])open\s*\(")


# ---------------------------------------------------------------------------
# Pure helpers (no Maya)
# ---------------------------------------------------------------------------


def _sanitize_ident(name: str) -> str:
    """Turn a node name into a valid C++/Maya type identifier."""
    s = re.sub(r"[^0-9A-Za-z_]", "_", str(name or "mpyNative"))
    if not s or not (s[0].isalpha() or s[0] == "_"):
        s = "n_" + s
    return s


def suggest_type_id(node_name: str) -> str:
    """A *suggested* MTypeId in the testing range (0x00070000-0x00077fff).

    Deterministic from the name to reduce intra-session collisions. NOT a real
    allocation -- distribution needs an id block registered with Autodesk.
    """
    h = 0
    for ch in str(node_name):
        h = (h * 131 + ord(ch)) & 0x7FFF
    return "0x%08x" % (0x00070000 + h)


def map_mpx_base(mpy_type: str) -> dict:
    base, note, heaviness = _MPX_BASE.get(
        mpy_type, ("MPxNode", "unknown mPy type; defaulting to MPxNode", "unknown")
    )
    return {"mpx_base": base, "note": note, "heaviness": heaviness}


def normalize_attr(meta: dict) -> dict:
    """Augment a raw attr meta dict with normalized C++ codegen hints."""
    attr_type = meta.get("attr_type", "")
    norm = _NORM_TYPE.get(attr_type)
    portable = bool(norm["portable"]) if norm else False
    out = {
        "type": attr_type,
        "is_array": bool(meta.get("is_array", False)),
        "portable": portable,
        # Codegen hints only when the attr is representable in C++.
        "cpp": dict(norm) if (norm and portable) else None,
    }
    # ``sparse`` / ``packed`` are stored on the raw meta only when True, so a node
    # using neither keeps a byte-identical spec and an unchanged port_cache key.
    # ``packed`` MUST reach the spec: it selects the typed-array read prologue in
    # the generated C++, and a bundle built for the wrong storage would read the
    # plug with the wrong handle type.
    # ``children`` MUST reach the spec for the same reason: it carries a float2's
    # child LONG names, and codegen falls back to <plug>X/<plug>Y without it -- which
    # gives a compiled mPyFile no ``uCoord`` plug.
    for k in ("min_value", "max_value", "default_value", "enum_names", "sparse",
              "packed", "children"):
        if k in meta:
            out[k] = meta[k]
    if norm is None:
        out["note"] = "unknown attr_type %r -- no native mapping" % attr_type
    return out


# Draw-expression flags that require the native locator's C++ hover + idle-refresh
# machinery, and therefore Qt linkage. ``wallclock`` is there because the live
# clock is seeded by that same service: without it the scaffold pins wallClock to
# 0.0 and a compiled wall-clock animation would sit frozen.
_HOVER_MARKERS = frozenset(("hovered", "precise_hover", "auto_refresh", "wallclock"))


def detect_needs_hover(compute: str, init: str = "") -> bool:
    """True if a locator draw expression uses passive hover / idle auto-refresh /
    the live wall clock.

    Scans for ``self.hovered`` / ``self.precise_hover`` / ``self.auto_refresh`` /
    ``self.wallclock`` in real code (``_self_attr_refs`` skips comments + string
    literals, so a stray mention doesn't trigger it). Drives
    ``spec['needs_hover']`` -> the Qt hover service in codegen + Qt linkage in the
    build. (Residual false-negative: ``getattr(self, 'hovered')`` -- not used by
    the shipped locators.)
    """
    refs = _self_attr_refs("%s\n%s" % (compute or "", init or ""))
    return bool(refs & _HOVER_MARKERS)


# Scalar input families whose live plug value can be baked as the C++ default.
# ``color`` is the one COMPOUND here: getAttr returns [(r, g, b)], unwrapped at
# the capture site below. It earns its place because the locator emitter already
# turns default_value into nAttr.setDefault(r,g,b) -- without capture that path
# was unreachable, so a draw wanting a sensible starting colour had to fake one
# in the compute and could never express a deliberate BLACK.
_DEFAULT_CAPTURE_TYPES = frozenset(("float", "int", "bool", "enum", "color"))


def _input_wants_default_capture(entry: dict) -> bool:
    """True if a normalized input entry should capture its live plug value as the
    baked default: a non-array scalar that has no recorded default yet."""
    return (entry.get("type") in _DEFAULT_CAPTURE_TYPES
            and not entry.get("is_array")
            and "default_value" not in entry)


def _strip_comments_strings(src: str) -> str:
    """Return ``src`` with every COMMENT and STRING (incl. f-string) token blanked
    to spaces (newlines preserved), leaving only real code.

    Portability pattern scans in :func:`assess_portability` must not match a
    token that appears only inside a ``# comment`` or a string literal -- e.g. the
    spine Init comment ``# ...runs once per file open (not per compute()).`` must
    not trip the bare-``open(`` blocker. Blanking (rather than deleting) preserves
    real-code spacing and adjacency, so a genuine ``cmds.foo(`` still matches the
    scene-access regex. Falls back to the same comment/string-stripping regex as
    :func:`_self_attr_refs` if the source cannot be tokenized.
    """
    import io
    import tokenize as _tok

    if not src:
        return ""
    try:
        toks = list(_tok.generate_tokens(io.StringIO(src).readline))
    except Exception:
        stripped = re.sub(r"#.*", "", src)
        return re.sub(r"(['\"]).*?\1", "", stripped)

    blank_types = {_tok.COMMENT, _tok.STRING}
    for _name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
        _t = getattr(_tok, _name, None)
        if _t is not None:
            blank_types.add(_t)

    lines = src.splitlines(keepends=True)
    for tok in toks:
        if tok.type not in blank_types:
            continue
        (srow, scol), (erow, ecol) = tok.start, tok.end
        srow -= 1
        erow -= 1
        if srow < 0 or srow >= len(lines):
            continue
        if srow == erow:
            line = lines[srow]
            lines[srow] = line[:scol] + " " * (ecol - scol) + line[ecol:]
            continue
        # Multi-line token (e.g. a triple-quoted string): blank each row it spans.
        first = lines[srow]
        nl = "\n" if first.endswith("\n") else ""
        lines[srow] = first[:scol] + " " * (len(first) - scol - len(nl)) + nl
        for r in range(srow + 1, min(erow, len(lines) - 1) + 1):
            row = lines[r]
            if r == erow:
                lines[r] = " " * ecol + row[ecol:]
            else:
                nl = "\n" if row.endswith("\n") else ""
                lines[r] = " " * (len(row) - len(nl)) + nl
    return "".join(lines)


def _classify_opens(raw_src: str):
    """Count bare ``open(...)`` calls and how many use a BINARY mode.

    Returns ``(n_open, n_binary)``. A binary-mode open (``"wb"``/``"rb"``/... any
    mode string containing ``b``) is the embedded-image STAGING idiom a
    texture/file node uses to hand its baked byte buffer to MImage (which has no
    readFromMemory); ``assess_portability`` sanctions those for a texture node
    while a NON-binary open (a text read/write) stays a hard blocker.

    AST-based so a nested path expr with commas/parens
    (``open(os.path.join(a, b), "wb")``) is parsed correctly where a regex would
    not. Only BARE ``open(`` (``ast.Name`` func) is counted -- ``x.open(`` /
    ``Image.open(`` are attribute calls handled elsewhere. A parse failure ->
    ``(1, 0)`` if the source textually contains an ``open(`` (conservative: stays
    a blocker), else ``(0, 0)``."""
    import ast

    try:
        tree = ast.parse(raw_src or "")
    except SyntaxError:
        return (1, 0) if _OPEN_RE.search(raw_src or "") else (0, 0)
    n_open = n_bin = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "open"):
            continue
        n_open += 1
        mode = None
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                and isinstance(node.args[1].value, str):
            mode = node.args[1].value
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                mode = kw.value.value
        if mode and "b" in mode:
            n_bin += 1
    return (n_open, n_bin)


def assess_portability(compute: str, init: str, inputs: dict, outputs: dict,
                       variables: dict, allow_file_read: bool = False,
                       allow_embedded_stage: bool = None) -> dict:
    """Return {portable, blockers[], warnings[], unported[], reads_image_file,
    reads_embedded_image, uses_mesh_intersector}.

    Two DIFFERENT kinds of "no" live here, and conflating them is what made this
    gate reject honest code:

    ``unported`` -- "this compiler has no deterministic path for X *yet*"
        (pandas, torch, a heavy scipy submodule, cv2 GUI, pickle, maya.cmds, a
        morphs member outside the compiled surface...). NOT a gate. Every entry
        is also mirrored into ``warnings`` so existing readers show it unchanged,
        and the list is handed to the AI porter as context -- which is whose job
        this is. The porter cannot silently fake it: it is instructed to emit a
        PORT_INCOMPLETE marker for anything it cannot translate, and its spliced
        body is scanned afterwards (prompt.scan_ported_body). Honesty moved from
        the input gate to the output.

    ``blockers`` -- "the node's declared SHAPE has no C++ representation".
        Only ``python`` / ``message`` attrs qualify: the attr table gives them
        no MFnAttribute, no data kind and no cpp type, so there is nothing for
        anyone -- deterministic or AI -- to emit. ``portable`` is ``not
        blockers``. (spec_model._check rejects these independently and FIRST, so
        this is the message, not the only guard.)

    ``allow_file_read`` (set by extract_spec for texture/file nodes, e.g.
    mPyFile) sanctions an in-compute image-FILE READ: it becomes a warning +
    flags ``reads_image_file`` (ported to MImage::readFromFile). Without it the
    read is merely ``unported``, so ``reads_image_file`` -- which drives the
    MImage codegen and the loose/skip verify -- still means exactly what it
    always did: a SANCTIONED read on a texture node."""
    # Scan real CODE only: blank comments + string literals so a stray token (the
    # spine template's ``open (`` in a comment) can't flip portable=False. Spacing
    # is preserved, so genuine ``open(``/``cmds.foo(`` still match.
    src = _strip_comments_strings("%s\n%s" % (compute or "", init or ""))
    blockers: list[str] = []
    warnings: list[str] = []
    unported: list[str] = []
    reads_image_file = False
    reads_embedded_image = False
    uses_mesh_intersector = False

    def _unported(reason):
        """Record a construct with no deterministic C++ path.

        Mirrored into ``warnings`` so every existing reader (the compile log, the
        manifest, translation guidance) keeps rendering it with no change, while
        ``unported`` carries it to the AI porter as the thing it must translate
        or explicitly mark PORT_INCOMPLETE."""
        unported.append(reason)
        warnings.append(reason)

    # 1) Libraries with no deterministic lowering -> porter context.
    for lib in _HARD_BLOCKER_LIBS:
        if re.search(r"(?:^|\W)(?:import|from)\s+%s\b" % re.escape(lib), src) or \
           re.search(r"\b%s\." % re.escape(lib), src):
            _unported("uses %s (no deterministic C++ lowering)" % lib)

    # 2) Unlowerable constructs (file write / GUI / GPU / heavy submodules).
    for pat, reason in _NONPORTABLE_PATTERNS:
        if pat.search(src):
            _unported(reason)

    # `import numpy as N` evades the \bnp\.load spelling above; the dotted names
    # (.loadtxt/.memmap/...) need no help. Mirrors the PIL alias fix in 2b.
    for _m in re.finditer(r"(?:^|\W)import\s+numpy\s+as\s+(\w+)", src):
        _al = _m.group(1)
        if _al in ("np", "numpy"):
            continue  # already covered by the pattern above
        if re.search(r"\b%s\.(?:load|savez|savez_compressed|savetxt)\b"
                     % re.escape(_al), src):
            _unported("numpy file I/O via alias %r (np.load/np.savetxt/...) "
                      "that has no C++ lowering; use ndio.read(path, "
                      "'name', dtype=...) instead" % _al)

    # 2a) Bare open(): a hard blocker EXCEPT the sanctioned embedded-image staging
    #     on a texture/file node. mPyFile stages its baked ``embeddedImage`` buffer
    #     to a temp file with open(<tmp>, "wb") for MImage (which has no
    #     readFromMemory); that BINARY-mode open ports to a C++ temp-file stage +
    #     MImage::readFromFile (file_texture_cpp EMBEDDED_STAGE_CPP). A NON-binary
    #     open stays a blocker even for a texture node. Parsed on the RAW source so
    #     mode strings survive.
    #     Gated on its OWN flag, not on allow_file_read: the bases sanctioned for
    #     an image READ are a superset, and only the types that can actually emit
    #     EMBEDDED_STAGE_CPP may claim a binary open() is staging. On any other
    #     base the warning would be factually wrong AND the `unported` signal the
    #     porter needs would be dropped silently. Defaults to allow_file_read so
    #     every existing caller keeps its behaviour verbatim.
    if allow_embedded_stage is None:
        allow_embedded_stage = allow_file_read
    n_open, n_bin = _classify_opens("%s\n%s" % (compute or "", init or ""))
    if n_open:
        if allow_embedded_stage and n_bin == n_open:
            reads_embedded_image = True
            warnings.append(
                "stages an embedded image byte buffer to a temp file for MImage "
                "decode (sanctioned; the baked buffer is the blank-fileName "
                "fallback, so output depends on the baked image, not bit-identical "
                "to a live re-encode)")
        else:
            _unported("file I/O via open() (no C++ lowering)")
    # The FRAMEWORK read is ALSO an embedded-image read: read_texture() falls back
    # to the node's baked ``embeddedImage`` bytes when `fileName` does not load
    # (file_methods.read_texture, mirrored in C++ by _emit_load's
    # nd_img_embedded_path() retry). The open() test above only ever saw the
    # hand-rolled staging that used to live in a template's Init tab, so moving
    # that staging into the framework silently cleared this flag -- and with it
    # the embedded_image_b64 bake, leaving the compiled node with no fallback.
    # Same fix, same reason, as the read_texture entry in _IMAGE_READ_PATTERNS.
    if allow_embedded_stage and re.search(
            r"\.read_texture\s*\(", "%s\n%s" % (compute or "", init or "")):
        reads_embedded_image = True

    # 2b) Image-FILE reads: a blocker by default, SANCTIONED for a texture node ->
    #     MImage::readFromFile; output then depends on external file state, so
    #     parity goes loose/skipped.
    img_reads = [name for pat, name in _IMAGE_READ_PATTERNS if pat.search(src)]
    # Aliased PIL imports evade the bare `Image.open` regex (the \b fails inside
    # `_PILImage`), and the shipped mPyFile Init uses `Image as _PILImage`, so
    # resolve the alias and treat `<alias>.open(` as the same sanctioned read.
    for _m in re.finditer(r"(?:from\s+PIL\s+import\s+Image|import\s+PIL\.Image)"
                          r"\s+as\s+(\w+)", src):
        _alias = _m.group(1)
        if re.search(r"\b%s\.open\b" % re.escape(_alias), src):
            img_reads.append("PIL.Image.open (as %s)" % _alias)
    if img_reads:
        if allow_file_read:
            reads_image_file = True
            warnings.append(
                "reads an image file (%s) -> ported to MImage::readFromFile; "
                "output depends on external file state, so pointwise parity is "
                "loose/skipped (not bit-identical to PIL/cv2)"
                % ", ".join(img_reads))
        else:
            _unported(
                "image file read (%s); pixels should enter via a Maya input, or "
                "enable file-read on a texture node (which lowers it to "
                "MImage::readFromFile)" % ", ".join(img_reads))

    # 2c) Closest-point mesh queries. Reported so the porter is TOLD about them
    #     (they used to be invisible -- a voxelizer's whole algorithm went to the
    #     porter with the query unmentioned). The reason carries the exact C++
    #     spelling because the API is identical on both sides; both are float32,
    #     so parity is exact PROVIDED the barycentric ordering is right -- the one
    #     silent way to get this wrong (translation_knowledge.MESH_CLOSEST_POINT).
    mesh_queries = [name for pat, name in _MESH_QUERY_PATTERNS if pat.search(src)]
    if mesh_queries:
        uses_mesh_intersector = True
        _unported(
            "closest-point mesh query (%s) -- no deterministic lowering, so it is "
            "AI-ported, but the C++ API is IDENTICAL: MMeshIntersector::create("
            "meshObj) + getClosestPoint(MPoint, MPointOnMesh&), and MPointOnMesh::"
            "getPoint/getNormal/getBarycentricCoords/faceIndex/triangleIndex. "
            "<maya/MMeshIntersector.h> is emitted into the scaffold for you"
            % ", ".join(mesh_queries))

    # RNG is supported (mapped to C++ <random>) but is NOT bit-identical to
    # Python's PRNG, so it is a warning, not a blocker, and gates parity-skip.
    if uses_rng(src):
        warnings.append(
            "uses RNG (np.random/random) -- mapped to C++ <random>, seeded "
            "deterministically per compute() from inputs; NOT bit-identical to "
            "Python, so pointwise parity is skipped")

    if re.search(r"(?:maya\.cmds|\bcmds|\bmc)\.\w+\s*\(", src):
        _unported("calls maya.cmds -- a compiled compute has no command engine; "
                  "the equivalent is the Maya C++ API (MFn*/MPlug) on data the "
                  "node already has, and scene MUTATION has no equivalent at all")
    if re.search(r"\b(?:eval|exec|__import__)\s*\(", src):
        _unported("uses eval/exec/__import__ -- there is no interpreter in the "
                  "compiled node; only a statically-known expression can be "
                  "emitted")
    # Reading a MESH MULTI element at a RUNTIME index. nd_lower materialises the
    # multi as a std::vector<Nd<Kind>>, but `_geo_arr_elem` only rewrites the read
    # at a LITERAL int subscript -- a variable index falls through unlowered. This
    # was once a blanket name match on `self.targetGeometry`, which blocked
    # mPyBlendShape by NAME rather than capability: a blend shape reading baked
    # numeric delta tables (what the shipped templates do) has no mesh read at all
    # and compiles fine. So reject only the construct with no lowering, and name
    # the deterministic alternative so the AI porter is not left to guess. Scope:
    # mPyBlendShape's targetGeometry[] plus any declared ARRAY geo input. Matching
    # the SUBSCRIPT (not a trailing .getPoints()) catches the real idiom, where the
    # element is bound to a local first:
    #     tgt = self.targetGeometry[i]   ...   tgt.getPoints(pa, space)
    _geo_multis = {"targetGeometry"}
    for _n, _m in (inputs or {}).items():
        if isinstance(_m, dict) and _m.get("is_array") and _m.get("attr_type") in (
                "mesh", "nurbsCurve", "nurbsSurface"):
            _geo_multis.add(_n)
    for _g in sorted(_geo_multis):
        # Allow a LITERAL non-negative int (that form lowers); reject `[i]`,
        # `[i + 1]`, `[int(x)]`.
        _hit = re.search(r"\bself\.%s\s*\[\s*(?!\d+\s*\])([^\]\n]+)\]"
                         % re.escape(_g), src)
        if _hit:
            _unported(
                "reads a geometry multi at a RUNTIME index (self.%s[%s]) -- the "
                "transpiler lowers a mesh-array element only at a LITERAL index, "
                "so this has no native kernel. Bake the targets to numeric delta "
                "arrays (MPyBlendShape.bake_deltas) and index those instead"
                % (_g, _hit.group(1).strip()))

    # The ``self.morphs`` OBJECT surface. Only a fixed set of members compiles.
    # Rather than restate the recognised forms here (two copies would drift, and a
    # drift means the gate passes what the lowering then refuses), run the REAL
    # desugar and report whatever it refuses. Pure AST -- no Maya, .mpn-safe.
    #
    # Deliberately the RAW compute, not ``src``: _strip_comments_strings blanks
    # string literals INCLUDING their quotes, so ``self.morphs['browUp']`` becomes
    # ``self.morphs[        ]`` -- a SyntaxError the rewriter passes through, which
    # silently lost the name-key blocker. An AST pass already tells code from
    # string, and it NEEDS the real literal to judge the key.
    _raw = compute or ""
    if "morphs" in _raw:
        try:
            from mpynode.native.compiler.nd_lower import _rewrite_morph_reads
            from mpynode.native.compiler.errors import UnsupportedSpec as _Uns
            try:
                _rewrite_morph_reads(_raw)
            except _Uns as _e:
                # The refusal text names the whole recognised MorphStack surface
                # (.weights/.resolved/.deltas/.apply/[k].weight/len()), so carrying
                # it verbatim tells the porter the CORRECT forms.
                _unported(str(_e).replace("nd_lower: ", ""))
        except ImportError:
            pass

    # Target NAMES can never be read in a compute, interpreted or compiled: alias
    # lookup is a side-channel DG query, and those come back EMPTY on the
    # Evaluation-Manager worker thread deform() runs on (see _api2/helpers.py).
    if re.search(r"\bself\.(?:aliases|target_names|alias_fingerprint)\b", src):
        _unported(
            "reads target names in the compute (self.aliases) -- alias lookup is "
            "a side-channel DG query and returns EMPTY on the EM worker thread, "
            "so it is unreliable interpreted and impossible compiled. Decode "
            "names into numeric tables in MPyBlendShape.rebuild() instead")

    # python + message are the ONLY intentionally-excluded attr types (every other
    # type compiles to deterministic pure C++), and THE ONLY remaining blockers.
    # A different kind of "no" from everything above: not "no port written yet"
    # (that is `unported`, which the AI porter takes on) but "no C++ representation
    # exists" -- the attr table gives both fn=None, data=None, cpp=None. Demoting
    # them would not even reach the porter: spec_model._check rejects them FIRST,
    # before it consults `portable` at all.
    for label, amap in (("input", inputs), ("output", outputs)):
        for name, meta in (amap or {}).items():
            if meta.get("attr_type") == "python":
                blockers.append("%s %r is type 'python' (no native type)" % (label, name))
            elif meta.get("attr_type") == "message":
                blockers.append("%s %r is type 'message' (no data payload to "
                                "compile; message is a pure connection marker)"
                                % (label, name))

    # 3) Portable-math libraries: warning + a pointer to the translation guide.
    _LIB_GUIDANCE = {
        "numpy": "uses numpy -- vectorized math is reverse-engineered to C++ loops "
                 "(verify numerically; np.random maps to C++ <random>; file I/O "
                 "lowers only where the dtype is explicit -- np.fromfile/np.save/"
                 ".tofile and ndio.read/ndio.write -- while np.load/np.loadtxt "
                 "are blockers)",
        "scipy": "uses scipy -- special/interpolate/linalg map to hand-rolled C++ "
                 "(A&S Bessel ~1e-6, Cox-de Boor, dense LU); verify numerically",
        "numba": "uses numba -- decorators/prange are stripped and the body ported "
                 "as plain loops (preserve Jacobi double-buffering; reductions ~1e-5)",
        "PIL": "uses PIL -- pixel math (point/blend/convolve/resize/rotate) ports to "
               "loops; pixels must enter via a Maya input, not Image.open",
        "cv2": "uses cv2 -- array ops (cvtColor/filter2D/GaussianBlur/resize/threshold) "
               "port to loops; mind BGR order + reflect-101 border; no imread/imshow",
        "skimage": "uses skimage -- filter/transform/morphology math ports to loops "
                   "(RGB, float[0,1], luma 0.2125/0.7154/0.0721); no skimage.io",
    }
    for lib in _PORTABLE_MATH_LIBS:
        if re.search(r"(?:^|\W)(?:import|from)\s+%s\b" % re.escape(lib), src) or \
           re.search(r"\b%s\." % re.escape(lib), src):
            warnings.append(_LIB_GUIDANCE[lib])

    for name, meta in (variables or {}).items():
        if meta.get("bake"):
            warnings.append("stored var %r is large -- must be baked into the plugin" % name)
    for label, amap in (("input", inputs), ("output", outputs)):
        for name, meta in (amap or {}).items():
            if meta.get("attr_type") in ("mesh", "nurbsCurve", "nurbsSurface"):
                warnings.append("%s %r is geometry -- heavier C++ (MFn* construction)" % (label, name))

    return {"portable": not blockers, "blockers": blockers, "warnings": warnings,
            "unported": unported,
            "reads_image_file": reads_image_file,
            "reads_embedded_image": reads_embedded_image,
            "uses_mesh_intersector": uses_mesh_intersector}


def _summarize_var(value) -> dict:
    """Compact, JSON-safe description of a stored var + a 'bake' hint."""
    try:
        import numpy as np

        if isinstance(value, np.ndarray):
            big = value.size > 64
            out = {"kind": "ndarray", "shape": list(value.shape),
                   "dtype": str(value.dtype), "bake": bool(big)}
            if not big:
                out["value"] = value.tolist()
            return out
    except Exception:
        pass
    if isinstance(value, (int, float, bool, str)):
        return {"kind": type(value).__name__, "value": value, "bake": False}
    if isinstance(value, (list, tuple)):
        big = len(value) > 64
        out = {"kind": "list", "len": len(value), "bake": bool(big)}
        if not big:
            out["value"] = list(value)
        return out
    r = repr(value)
    return {"kind": type(value).__name__,
            "repr": r if len(r) <= 200 else r[:200] + "...",
            "bake": True}


# ---------------------------------------------------------------------------
# Extraction (needs Maya)
# ---------------------------------------------------------------------------


def _strip_unported_classification(classif: str) -> str:
    """Keep only the classification segments a Phase-1 compute-only port can
    honor. A Maya classification is ':'-joined segments (e.g.
    ``texture/2d:swatch/2dTextureSwatchGen:drawdb/shader/texture/2d/mPyFile``).
    The ``drawdb/...`` segment binds a VP2 draw/shader override -- which Phase 1
    does NOT port (that is the Phase-2 MPxShadingNodeOverride) -- so drop it;
    keep ``texture/2d`` (Hypershade Create panel + auto place2dTexture) and the
    swatch generator. Returns '' if nothing portable remains."""
    segs = [s.strip() for s in (classif or "").split(":")]
    kept = [s for s in segs if s and not s.startswith("drawdb/")]
    return ":".join(kept)


def _node_type_classification(mpy_type: str) -> str:
    """The (Phase-1-stripped) Hypershade classification of a node TYPE, via
    ``cmds.getClassification``. Returns '' when the type is unclassified (a
    plain mPyNode) or the query fails -- so non-texture nodes are unaffected."""
    try:
        import maya.cmds as mc
        lst = mc.getClassification(mpy_type) or []
    except Exception:
        return ""
    return _strip_unported_classification(lst[0]) if lst else ""


# Node types whose TEXTURE INTERFACE is registered as preset DG attrs (not via
# add_input_attr); without capture the compiled node has no outColor/uvCoord.
# Gating to this set keeps the other 12 types' specs byte-identical (cache safe).
_PRESET_CAPTURE_TYPES = ("mPyFile",)

# The mPyFile preset DG interface is declared ONCE in the Maya-free SSOT
# ``mpynode._common.interface.file_texture_interface`` -- the SAME data
# MPyFile.initializer builds its Maya attrs from. Projected to raw-meta here: no
# ``createNode``, no snapshot, no drift (the 2026-07-19 mega drop was a flaky transient
# ``createNode`` returning EMPTY -> interface stripped -> nodes dropped; a pure
# projection cannot flake). ``TestConformsToLiveNode`` pins it to a live node.
def _preset_meta_table() -> dict:
    """Raw-meta table ``{name: {attr_type,_writable,_readable,enum_names?}}`` for the
    mPyFile preset interface, projected from the declarative SSOT. Returns FRESH dicts
    each call (callers ``pop`` the routing flags). Lazy import keeps spec_extractor's pure
    helpers importable without eagerly pulling the ``_common`` package's maya chain."""
    from mpynode._common.interface import file_texture_interface as _iface
    return _iface.build_porter_meta_table()


def __getattr__(name):
    # Back-compat: ``_MPYFILE_PRESET_META`` was a module-level dict, now DERIVED from
    # the SSOT. Resolved lazily so external importers / drift-guard tests keep working.
    if name == "_MPYFILE_PRESET_META":
        return _preset_meta_table()
    raise AttributeError("module %r has no attribute %r" % (__name__, name))

# Maya attributeType (cmds.attributeQuery -attributeType) -> native spec type.
# 'typed' (string) and 'float3' (color vs vector) are resolved separately.
_MAYA_ATTR_TO_SPEC = {
    "float": "float", "double": "double", "doubleLinear": "double",
    "long": "int", "short": "int", "byte": "int", "bool": "bool",
    "enum": "enum", "doubleAngle": "angle", "time": "time",
    "float2": "float2",
    "double3": "vector",
    "matrix": "matrix", "fltMatrix": "matrix",
}


def _self_attr_refs(src: str) -> set:
    """Names referenced as ``self.<name>`` in real CODE (not comments/strings).

    Tokenizing skips COMMENT/STRING tokens, so ``self.foo`` mentioned only in a
    ``# comment`` or a ``"string literal"`` is NOT returned -- which keeps a stray
    mention from dragging a preset into the port spec (and the port-cache key).
    Falls back to a comment/string-stripped regex if tokenizing fails."""
    import io
    import tokenize as _tok

    refs: set = set()
    try:
        toks = list(_tok.generate_tokens(io.StringIO(src or "").readline))
    except Exception:
        stripped = re.sub(r"#.*", "", src or "")
        stripped = re.sub(r"(['\"]).*?\1", "", stripped)
        return set(re.findall(r"\bself\.([A-Za-z_]\w*)", stripped))
    for i in range(len(toks) - 2):
        a, b, c = toks[i], toks[i + 1], toks[i + 2]
        if (a.type == _tok.NAME and a.string == "self"
                and b.type == _tok.OP and b.string == "."
                and c.type == _tok.NAME):
            refs.add(c.string)
    return refs


def _preset_attr_meta(node: str, attr: str, mc) -> dict | None:
    """Raw attr-meta ({attr_type, enum_names?, default_value?, _writable,
    _readable}) for one preset DG attr, mapped from Maya introspection -- or
    None if the attr type has no native representation. Pure read-only
    (attributeQuery / getAttr).

    The LIVE ORACLE the declarative-interface drift guards compare against, so
    it must read every field the projection emits -- including an enum's default
    FIELD INDEX, which codegen bakes into ``MFnEnumAttribute::create``."""
    def q(**kw):
        try:
            return mc.attributeQuery(attr, node=node, **kw)
        except Exception:
            return None

    writable = bool(q(writable=True))
    readable = bool(q(readable=True))
    at = q(attributeType=True)
    spec_type = _MAYA_ATTR_TO_SPEC.get(at)
    if at == "typed":
        # Maya reports a string attr as 'typed'; confirm via getAttr type.
        try:
            spec_type = "string" if mc.getAttr(
                node + "." + attr, type=True) == "string" else None
        except Exception:
            spec_type = None
    elif at == "float3":
        # usedAsColor -> a renderable color (createColor), else a plain vector.
        # mPyFile's float3s are all colors; the vector branch is defensive.
        spec_type = "color" if bool(q(usedAsColor=True)) else "vector"
    if spec_type is None:
        return None
    meta = {"attr_type": spec_type, "_writable": writable, "_readable": readable}
    if spec_type == "float2":
        # Child LONG names, which codegen needs: it otherwise synthesizes
        # <plug>X/<plug>Y, and uvCoord's children are uCoord/vCoord. Reading
        # them here is what lets the drift guards check the SSOT's declared
        # child names against the ones the live node actually has.
        # listChildren can report a DOTTED path (see node_swap.py), so keep the
        # leaf.
        kids = q(listChildren=True) or []
        if kids:
            meta["children"] = [str(c).split(".")[-1] for c in kids]
    if spec_type == "enum":
        le = q(listEnum=True)
        if le and isinstance(le, list) and le[0]:
            meta["enum_names"] = le[0].split(":")
        # listDefault reports the default FIELD INDEX as a float ([2.0]).
        dv = q(listDefault=True)
        if dv and isinstance(dv, list):
            try:
                meta["default_value"] = int(dv[0])
            except (TypeError, ValueError):
                pass
    return meta


def _capture_preset_attrs(node: str, mpy_type: str, compute: str, init: str,
                          user_in: dict, user_out: dict):
    """Capture the PRESET DG attrs a texture/file node's compute/init reference
    via ``self.<name>`` (mPyFile's fileName/uvCoord/outColor/... are registered
    in C++, not via add_input_attr, so they are invisible to the user attr maps).

    Returns ``(preset_in, preset_out)`` raw-meta dicts (same shape as the user
    maps), classified by the declarative interface's writable/readable flags. Names
    already in the user maps are skipped (user attrs win); names not in the interface
    table (injected API slots like ``self.time``, internal plugs, or plain scratch
    vars) are skipped automatically. Only REFERENCED presets are captured, so a node
    stays minimal. Gated to ``_PRESET_CAPTURE_TYPES``.

    Reads the declarative SSOT (``_preset_meta_table``) -- NO ``createNode`` /
    ``attributeQuery``. The ``node`` arg is unused (kept for signature compatibility
    with the live ``extract_spec`` call site); the interface is a fixed contract so
    the live and scene-free (.mpn) paths produce byte-identical output by construction."""
    if mpy_type not in _PRESET_CAPTURE_TYPES:
        return {}, {}
    table = _preset_meta_table()
    referenced = set(_self_attr_refs("%s\n%s" % (compute or "", init or "")))
    # Blessed-method reads: a compute that CALLS a blessed method (e.g.
    # self.read_texture()) reads the PRESET inputs INSIDE the interpreted adapter,
    # never textually as self.<preset>, so the self.<name> scan misses them. Union
    # in each called method's declared `reads` so those presets get the same
    # table-lookup + writable/readable classification below (and the porter's
    # blessed lowering finds them instead of parity-rejecting the node). Additive:
    # a full-parity node calls bare _load_linear_pixels( so nothing changes.
    # method_registry is Maya-free, so this is safe on the .mpn path too.
    from mpynode._common.interface import method_registry
    for _m in method_registry.methods_for_type(mpy_type):
        if _m.name in referenced:
            referenced |= set(getattr(_m, "reads", ()) or ())
    preset_in, preset_out = {}, {}
    for nm in sorted(referenced):
        if nm in user_in or nm in user_out or nm.startswith("_"):
            continue
        meta = table.get(nm)
        if meta is None:
            continue
        writable = meta.pop("_writable")
        readable = meta.pop("_readable")
        # The interface flags are authoritative: a writable attr is an input; a
        # readable-but-not-writable attr (outColor/outAlpha) is an output.
        if writable:
            preset_in[nm] = meta
        elif readable:
            preset_out[nm] = meta
    return preset_in, preset_out


def capture_preset_attrs_transient(mpy_type: str, compute: str, init: str,
                                   user_in: dict, user_out: dict):
    """Capture mPyFile PRESET DG attrs for the SCENE-FREE (``.mpn``) path.

    Now a thin alias for the pure ``_capture_preset_attrs``: the interface is read
    from the declarative SSOT, so there is NO transient ``createNode`` and the
    scene-free (.mpn) and live (``extract_spec``) paths are byte-identical by
    construction. (Kept as a named entry point for ``mpn_spec_adapter``; the flaky
    transient capture + static-table fallback it used to carry are retired -- they
    were the 2026-07-19 mega-drop root cause.) Gated to ``_PRESET_CAPTURE_TYPES``."""
    return _capture_preset_attrs(None, mpy_type, compute, init, user_in, user_out)


def capture_named_presets(node: str, names) -> dict:
    """Capture a CALLER-SUPPLIED list of preset DG attrs as normalized spec-input
    entries, regardless of whether the compute/init reference them.

    ``_capture_preset_attrs`` only captures presets the compute references via
    ``self.<name>`` -- so VIEWPORT-ONLY sampler state (filterMode / mipmapMode /
    maxAnisotropy / mipLODBias / minLOD / maxLOD), which a DG compute() never
    reads, is never captured. A node that DOES carry a VP2 shading override (so
    the override can read those presets to drive GPU sampler state) needs them on
    the compiled node anyway. This reuses the SAME authoritative typing path
    (the declarative SSOT + ``normalize_attr``) as the default capture, so the
    returned entries drop into ``spec['inputs']`` verbatim (setdefault-merge).

    Reads the declarative interface table -- NO ``createNode`` / ``attributeQuery``
    (the ``node`` arg is unused, kept for signature compatibility). This is the path
    that carries the getattr-reached ``fileName`` (invisible to the ``self.<name>``
    scan): it is now deterministic, so a flaky capture can never strip it. Names not
    in the interface table or internal (``_``-prefixed) are silently skipped. Returns
    ``{name: normalized_entry}``.
    """
    table = _preset_meta_table()
    out = {}
    for nm in names:
        if not nm or nm.startswith("_"):
            continue
        meta = table.get(nm)
        if meta is None:
            continue
        meta.pop("_writable", None)
        meta.pop("_readable", None)
        out[nm] = normalize_attr(meta)
    return out


def capture_named_presets_transient(mpy_type: str, names) -> dict:
    """``capture_named_presets`` for the SCENE-FREE (``.mpn``) path.

    Now a thin gated alias: the interface is read from the declarative SSOT, so
    there is NO transient ``createNode`` and the entry is byte-identical to the live
    path by construction. (The flaky transient capture + fallback it used to carry
    are retired -- they were the 2026-07-19 mega-drop root cause.) Gated to
    ``_PRESET_CAPTURE_TYPES``."""
    if mpy_type not in _PRESET_CAPTURE_TYPES:
        return {}
    return capture_named_presets(None, names)


def extract_spec(node: str) -> dict:
    """Introspect a live mpynode into a porter spec dict (read-only)."""
    import maya.cmds as mc
    import mpynode

    w = mpynode.wrap_node(node)
    if w is None:
        raise ValueError("node %r not found (or not an mPy node)" % node)

    name = w.get_name()
    mpy_type = mc.nodeType(name)

    raw_in = {}
    raw_out = {}
    try:
        raw_in = w.get_input_attr_map() or {}
    except Exception:
        pass
    try:
        raw_out = w.get_output_attr_map() or {}
    except Exception:
        pass

    variables = {}
    try:
        for k, v in (w.get_variables() or {}).items():
            variables[k] = _summarize_var(v)
    except Exception:
        pass

    try:
        compute = w.get_compute_expression() or ""
    except Exception:
        compute = ""
    try:
        init = w.get_init_expression() or ""
    except Exception:
        init = ""

    # mPyFile exposes its interface as PRESET DG attrs, not via add_input_attr --
    # capture the referenced presets or the compiled node has no outColor/uvCoord/
    # fileName. User attrs win on collision (setdefault); gated to mPyFile.
    preset_in, preset_out = _capture_preset_attrs(
        name, mpy_type, compute, init, raw_in, raw_out)
    for k, v in preset_in.items():
        raw_in.setdefault(k, v)
    for k, v in preset_out.items():
        raw_out.setdefault(k, v)

    inputs = {n: normalize_attr(m) for n, m in raw_in.items()}
    outputs = {n: normalize_attr(m) for n, m in raw_out.items()}

    # Follow the node's imports to the SOURCE of pure-Python helpers it calls from
    # external modules, so the porter ports them alongside the compute. Best-effort
    # + read-only (static resolution, no import/exec); ANY failure -> "".
    # See native/ai/import_follower.py.
    external_helpers = ""
    external_helper_units = []
    try:
        from mpynode.native.ai import import_follower

        _hres = import_follower.collect_helper_sources(compute, init)
        external_helpers = import_follower.render_for_prompt(_hres)
        external_helper_units = _hres.get("sources") or []
    except Exception:
        external_helpers = ""
        external_helper_units = []

    from mpynode.native.spec.identity import derive_class_identity

    class_path = ""
    try:
        class_path = w.get_py_class() or ""
    except Exception:
        class_path = ""
    # Compiled identity is per-CLASS (N instances of one Class -> one compiled
    # type). The interactive path refuses a class-less node up front
    # (compile_dialog._resolve_classless), so ``class_path`` is normally set; the
    # instance-name fallback is a safety net for programmatic extraction only.
    spec = {
        "schema_version": SCHEMA_VERSION,
        "source_node": name,
        "mpy_type": mpy_type,
        "suggested": derive_class_identity(class_path or name, mpy_type),
        "inputs": inputs,
        "outputs": outputs,
        "variables": variables,
        "compute": compute,
        "init": init,
        # Conservative default: every input affects every output.
        "affects": "all",
    }
    # Added ONLY when non-empty: it joins the port_cache key, so editing a helper
    # re-ports correctly while a node with no helpers keeps a byte-identical spec
    # (existing cache entry untouched).
    if external_helpers:
        spec["external_helpers"] = external_helpers
    # Structured units (module/name/source per helper) drive the porter's
    # translate-once shared-C++-unit dedup. Added ONLY when non-empty (cache key).
    if external_helper_units:
        spec["external_helper_units"] = external_helper_units
    # Methods tab: the per-node companion-command source (hidden _methodsSource
    # plug) + its statically-detected @maya_command defs. Added ONLY when non-empty
    # so a node without a Methods tab keeps a byte-identical spec (and cache key).
    # The native pipeline turns spec['commands'] into companion MPxCommands.
    methods_src = ""
    try:
        import maya.cmds as _mc

        if _mc.attributeQuery("_methodsSource", node=name, exists=True):
            methods_src = _mc.getAttr(name + "._methodsSource") or ""
    except Exception:
        methods_src = ""
    if methods_src.strip():
        from mpynode._common.methods import maya_command as _maya_command

        spec["methods"] = methods_src
        # A ``creates=True`` command with no name literal is named after the NODE
        # TYPE (the cmds.blendShape idiom). Bound HERE, not in the decorator: the
        # per-type default setups are one shared text file, so a literal there
        # would repeat across every node of that type and abort a merged plugin.
        spec["commands"] = _maya_command.resolve_create_command_names(
            _maya_command.detect_commands(methods_src),
            (spec.get("suggested") or {}).get("node_type_name"))
    # Per-node metadata from the hidden ``_metadata`` JSON plug. Added ONLY when
    # non-empty, so a node without metadata keeps a byte-identical spec (and cache
    # key). Global DEFAULTS are merged later by compile_controller. Codegen embeds
    # it as a banner + MFnPlugin vendor/version + build hash.
    metadata_raw = ""
    try:
        import maya.cmds as _mc

        if _mc.attributeQuery("_metadata", node=name, exists=True):
            metadata_raw = _mc.getAttr(name + "._metadata") or ""
    except Exception:
        metadata_raw = ""
    if metadata_raw.strip():
        from mpynode._common.lifecycle import metadata_registry as _md

        try:
            _meta = _md.coerce(json.loads(metadata_raw))
        except Exception:
            _meta = None
        if _meta is not None and not _md.is_empty(_meta):
            spec["metadata"] = _meta
    # Hypershade placement: carry the source TYPE's classification onto the
    # compiled node so it gets the Create panel + swatch + auto place2dTexture
    # (e.g. mPyFile -> texture/2d). Added ONLY when non-empty (cache key). The
    # drawdb/shader VP2-override segment is stripped -- Phase 1 ports compute().
    classification = _node_type_classification(mpy_type)
    if classification:
        spec["suggested"]["classification"] = classification
    # Texture/file nodes (mPyFile, or anything classified texture/2d) may read
    # their image file in the compiled compute. For everyone else it is a blocker.
    # A GEOMETRY GENERATOR is sanctioned too: it drives geometry FROM an image
    # (voxelize colours its cubes from textureFile) and the mechanism is the same
    # cached MImage::readFromFile. It costs no verification -- verify._verify_geo
    # runs first for a geo node and compares the geometry for real, driving path
    # inputs EMPTY and noting that the image path is not exercised (_GEO_IMAGE_
    # NOTE) -- unlike the texture family, which skips parity outright.
    # The embedded-image STAGING sanction (a binary open() that writes the baked
    # buffer to a temp file for MImage) is the pre-existing set only. The bases
    # added to _IMAGE_READ_BASE_TYPES get the image READ, not a licence to call a
    # binary open() staging -- no deformer/solver emitter emits EMBEDDED_STAGE_CPP.
    allow_embedded_stage = ((mpy_type == "mPyFile")
                            or ("texture/2d" in (classification or ""))
                            or (mpy_type in _GEO_GENERATOR_TYPES))
    allow_file_read = (allow_embedded_stage
                       or (mpy_type in _IMAGE_READ_BASE_TYPES))
    port = assess_portability(compute, init, raw_in, raw_out, variables,
                              allow_file_read=allow_file_read,
                              allow_embedded_stage=allow_embedded_stage)
    # Lift the sanctioned-read flag onto the spec (drives MImage codegen +
    # loose/skip verify). Added ONLY when set so non-file nodes are unaffected.
    if port.get("reads_image_file"):
        spec["suggested"]["reads_image_file"] = True
        # A file reader needs its path attr. When the compute reaches fileName only
        # through a helper (getattr(slf, "fileName") in _resolve_image), the
        # self.<name> scan misses it and the compiled node has no path input, so
        # capture it explicitly. setdefault -> a node already referencing
        # self.fileName keeps a byte-identical spec. Skipped when the node reads a
        # string ARRAY path input (multi-file composite): that array IS the path
        # source, so a fileName preset would be an unused plug.
        # capture_named_presets reads the declarative SSOT (no createNode), so
        # this capture is deterministic and can never flake and strip fileName.
        _has_array_path = any(
            (v or {}).get("type") == "string" and (v or {}).get("is_array")
            for v in spec["inputs"].values())
        if (mpy_type in _PRESET_CAPTURE_TYPES and "fileName" not in spec["inputs"]
                and not _has_array_path):
            for k, v in capture_named_presets(name, ["fileName"]).items():
                spec["inputs"].setdefault(k, v)
    # Closest-point mesh query: lift the flag so the scaffold emits
    # <maya/MMeshIntersector.h> (the porter may not add includes) and the porter
    # guide gains MESH_CLOSEST_POINT. Added ONLY when set, so every other node's
    # spec + cache key stays byte-identical.
    if port.get("uses_mesh_intersector"):
        spec["suggested"]["uses_mesh_intersector"] = True
    # Embedded-image fallback: when the node stages a baked byte buffer AND carries
    # an ``embeddedImage`` stored var, bake its bytes (base64) onto the spec so the
    # compiled node resolves the baked image when fileName is blank/unreadable
    # (staged to a temp file + MImage::readFromFile in C++). Added ONLY when
    # non-empty, so a texture node without embedded data keeps a byte-identical
    # spec + cache key.
    if port.get("reads_embedded_image"):
        try:
            emb = (w.get_variables() or {}).get("embeddedImage")
            if isinstance(emb, (bytes, bytearray)) and len(emb):
                import base64
                spec["suggested"]["embedded_image_b64"] = \
                    base64.b64encode(bytes(emb)).decode("ascii")
        except Exception:
            pass
    spec["portability"] = port

    # Locator-only (other 12 types' specs + port caches stay byte-identical):
    #  (1) capture each unconnected scalar input's LIVE plug value as the baked C++
    #      default -- a value set via setAttr (wire_width=2) would otherwise fall
    #      to a type-zero default, which drew the compiled wireframe at width 0
    #      (invisible). Driven inputs are skipped; their default is irrelevant.
    #  (2) flag needs_hover when the draw expression uses passive hover / idle
    #      auto-refresh -> Qt hover service in codegen + Qt linkage in build.
    if mpy_type == "mPyLocator":
        for n, entry in inputs.items():
            if not _input_wants_default_capture(entry):
                continue
            plug = "%s.%s" % (name, n)
            try:
                if mc.listConnections(plug, source=True, destination=False,
                                      plugs=True):
                    continue  # driven -> the default never reaches the draw
            except Exception:
                pass
            try:
                val = mc.getAttr(plug)
            except Exception:
                continue
            if isinstance(val, (list, tuple)):
                # compound/array safety net (scalars only) -- EXCEPT `color`,
                # which getAttr hands back as [(r, g, b)]. The locator emitter
                # already turns default_value into nAttr.setDefault(r,g,b) and
                # into the Inputs seed; skipping it here was the only reason a
                # colour default could never reach codegen. Unwrapped to a flat
                # 3-list: the raw nesting would make _loc_color_default emit
                # garbage.
                if (entry.get("type") == "color" and len(val) == 1
                        and isinstance(val[0], (list, tuple))
                        and len(val[0]) == 3):
                    entry["default_value"] = [float(c) for c in val[0]]
                continue
            entry["default_value"] = val
        if detect_needs_hover(compute, init):
            spec["needs_hover"] = True
    return spec


def to_json(node: str, indent: int = 2) -> str:
    return json.dumps(extract_spec(node), indent=indent, default=str)


def _main(argv):
    if len(argv) < 2:
        print("usage: spec_extractor.py <nodeName>")
        return 2
    try:
        import maya.standalone as _std
        import maya.cmds as _mc  # noqa: F401

        if not _mc.about(batch=True):
            pass
    except Exception:
        try:
            import maya.standalone as _std

            _std.initialize()
        except Exception as exc:
            print("could not initialize Maya: %s" % exc)
            return 1
    print(to_json(argv[1]))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main(sys.argv))
