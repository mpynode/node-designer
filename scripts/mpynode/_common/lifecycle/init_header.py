"""Auto-generated Init header (per node type) — split out of ``init_registry.py``
(behavior unchanged).

Provides the ``_BRIDGE_BINDINGS`` table (per-node-type reads/writes the bridge
auto-fills) and :func:`make_init_header`, which renders the commented header
prefilled into a fresh Init tab. Self-contained apart from a lazy import of the
node registry inside :func:`make_init_header`.
"""

from __future__ import annotations


# ---- Auto-generated Init header (per node type) ----


# Bindings the bridge auto-fills + auto-reads for each node type.
# Used to populate the helpful comment header in fresh Init tabs.
_BRIDGE_BINDINGS: dict = {
    "mPyDeformer": {
        "reads": [
            ("self.outputGeometry[i]",      "MFnMesh handle    writable output (getPoints/setPoints)"),
            ("self.input[i].inputGeometry", "MFnMesh           read-only upstream mesh"),
            ("self.envelope",               "float             deformer envelope"),
        ],
        "writes": [
            ("self.outputGeometry[i].setPoints(arr)", "(N, 3) float64  commit deformed positions"),
        ],
    },
    "mPySkinCluster": {
        "reads": [
            ("self.outputGeometry[i]",          "MFnMesh handle    writable output (getPoints/setPoints)"),
            ("self.input[i].inputGeometry",     "MFnMesh           read-only upstream mesh"),
            ("self.envelope",                   "float             envelope"),
            ("self.matrix[j].asNumpy()",        "(4, 4) float64    joint world matrix"),
            ("self.bindPreMatrix[j].asNumpy()", "(4, 4) float64    joint bind-pose inverse"),
            ("self.weightList[i].weights",      "sparse            per-vertex weights (densify yourself)"),
        ],
        "writes": [
            ("self.outputGeometry[i].setPoints(arr)", "(N, 3) float64  commit deformed positions"),
        ],
    },
    "mPyBlendShape": {
        "reads": [
            ("self.outputGeometry[i]",      "MFnMesh handle    writable output (getPoints/setPoints)"),
            ("self.input[i].inputGeometry", "MFnMesh           read-only upstream mesh"),
            ("self.envelope",               "float             envelope"),
            ("self.targetGeometry[j]",      "MFnMesh           read-only j-th target shape"),
            ("self.weight[j]",              "float             per-target weight (aliased to target name)"),
        ],
        "writes": [
            ("self.outputGeometry[i].setPoints(arr)", "(N, 3) float64  commit deformed positions"),
        ],
    },
    "mPyTransform": {
        # GATED LOCAL-MATRIX contract (single-joint IK-style). There is NO
        # world_matrix write slot: the node never reads its own DAG parent. For
        # WORLD placement read a CONNECTED parent-world matrix INPUT
        # (self.<input>.asNumpy()) and set local_matrix = wanted @ inv(parent).
        "reads": [
            ("self.translate",    "(3,) float64    own live translate"),
            ("self.rotate",       "(3,) float64    own live rotate, RADIANS"),
            ("self.scale",        "(3,) float64    own live scale"),
            ("self.shear",        "(3,) float64    own live shear (XY, XZ, YZ)"),
            ("self.rotate_order", "int             0..5, 0 == xyz"),
        ],
        "writes": [
            ("self.local_matrix",    "(4,4) or None   desired LOCAL matrix"),
            ("self.apply_rotate",    "bool            gate: take rotation"),
            ("self.apply_translate", "bool            gate: take translate"),
            ("self.apply_scale",     "bool            gate: take scale"),
        ],
    },
    "mPyMesh": {
        "reads": [
            ("self.time_value", "float  current time"),
        ],
        "writes": [
            ("self.points",         "(N, 3) float64  output vertices"),
            ("self.counts",         "(F,) int        per-face vertex counts (>=3)"),
            ("self.indices",        "(sum(counts),)  flat vertex indices"),
            ("self.normals",        "(N,3) per-vertex; (K,3)+normal_indices=per-face-vertex"),
            ("self.normal_indices", "(sum(counts),) int  face-vertex normal map"),
            ("self.colors",         "(N,3|4) per-vertex; (K,3|4)+color_indices=indexed"),
            ("self.color_indices",  "(sum(counts),) int  face-vertex color map"),
        ],
    },
    "mPyNurbsCurve": {
        "reads": [
            ("self.time_value", "float  current time"),
        ],
        "writes": [
            ("self.cvs",    "(N, 3) float64  CV positions"),
            ("self.degree", "int  1/2/3/5/7 (default 3)"),
            ("self.form",   "'open'/'closed'/'periodic' (default open)"),
            ("self.knots",  "(K,) float64 or None (auto uniform)"),
        ],
    },
    "mPyNurbsSurface": {
        "reads": [
            ("self.time_value", "float  current time"),
        ],
        "writes": [
            ("self.cvs",       "(u,v,3) grid or (u*v,3) flat CV positions"),
            ("self.num_cvs_u", "int  (required for flat cvs)"),
            ("self.num_cvs_v", "int  (required for flat cvs)"),
            ("self.degree_u",  "int (default 3)"),
            ("self.degree_v",  "int (default 3)"),
            ("self.form_u",    "'open'/'closed'/'periodic'"),
            ("self.form_v",    "'open'/'closed'/'periodic'"),
        ],
    },
    "mPyFile": {
        "reads": [
            ("self.fileName",        "str            texture file path"),
            ("self.uvCoord",         "(u, v) float    sample coordinate"),
            ("self.colorSpace",      "int            color-space enum (0..24)"),
            ("self.preFilter",       "bool           enable CPU pre-filter blur"),
            ("self.preFilterKernel", "int            kernel enum (Box/Quad/Quartic/Gauss)"),
            ("self.preFilterRadius", "float          kernel radius in texels"),
            ("self.filterMode",      "int            GPU sampler filter enum"),
            ("self.maxAnisotropy",   "int            anisotropic sample budget (1..16)"),
            ("self.mipmapMode",      "int            None / Auto"),
            ("self.mipLODBias",      "float          mip LOD bias"),
            ("self.minLOD",          "int            smallest mip GPU may use"),
            ("self.maxLOD",          "int            largest mip GPU may use"),
            ("self.wrapModeU",       "int            U-axis address mode"),
            ("self.wrapModeV",       "int            V-axis address mode"),
            ("self.borderColor",     "(r, g, b) float color used for Border wrap"),
        ],
        "writes": [
            ("self.outColor",        "(r, g, b) float  sampled scene-linear color"),
            ("self.outAlpha",        "float            sampled alpha"),
        ],
    },
    "mPyLocator": {
        "reads": [
            ("self.time",            "float           current scene time (frames)"),
            ("self.selected",        "bool            this locator is selected"),
            ("self.is_lead",         "bool            it is the ACTIVE selection"),
            ("self.hovered",         "bool            the mouse is over it"),
            ("self.selection_color", "(r,g,b,a) float Maya's selection colour"),
        ],
        "writes": [
            ("self.draw",            "Draw object(s)  the drawing, in order"),
            ("self.auto_highlight",  "bool            tint the drawing when selected"),
            ("self.auto_refresh",    "bool            repaint every frame"),
            ("self.precise_hover",   "bool            hover-test the real polygons"),
        ],
    },
}


# Draw types a fresh mPyLocator Init imports outright, so the drawing surface is
# discoverable by autocomplete instead of only by reading the docs.
_LOCATOR_DRAW_TYPES = ("DrawCircle", "DrawSphere", "DrawBox", "DrawCone",
                       "DrawCylinder", "DrawPoints", "DrawLines", "DrawCurve",
                       "DrawMesh", "DrawText")


def make_init_header(node_type: str) -> str:
    """Return the auto-generated commented header to prefill a fresh
    Init tab for a given node type."""
    bindings = _BRIDGE_BINDINGS.get(node_type)
    lines = []
    bar = "# " + "─" * 68
    lines.append(bar)
    lines.append(f"# {node_type} — Init code (runs once per file open)")
    # Native Maya class this node type wraps + a versioned API-doc link.
    try:
        from mpynode._node_registry import get_spec

        _spec = get_spec(node_type)
    except Exception:
        _spec = None
    if _spec is not None and getattr(_spec, "native_class", ""):
        lines.append("#")
        lines.append(f"# Wraps {_spec.native_class}")
        _url = _spec.doc_url()
        if _url:
            lines.append(f"# {_url}")
    lines.append("#")
    lines.append("# Define module-level state here: JIT kernels, lookup tables,")
    lines.append("# helper functions, cached data — anything that should run ONCE")
    lines.append("# per file lifecycle rather than per compute() call.")
    lines.append("#")
    if bindings:
        lines.append("# Available in your Expression tab via self.X:")
        for name, desc in bindings["reads"]:
            lines.append(f"#   {name:25s} {desc}")
        lines.append("#")
        lines.append("# Set in your Expression tab:")
        for name, desc in bindings["writes"]:
            lines.append(f"#   {name:25s} {desc}")
        lines.append("#")
        # Geometry generators: document the typed-dataclass output surface.
        _GEO_IDIOM = {
            "mPyMesh": (
                "Mesh",
                "self.outMesh = Mesh(points=P, counts=C, indices=I,\n"
                "#                       normals=None, colors=None)   "
                "# + *_indices for face-vertex",
            ),
            "mPyNurbsCurve": (
                "NurbsCurve",
                "self.outCurve = NurbsCurve(points=CVs, degree=3,\n"
                "#                              periodic=False, kv=None)",
            ),
            "mPyNurbsSurface": (
                "NurbsSurface",
                "self.outSurface = NurbsSurface(points=grid, degree_u=3,\n"
                "#                                  degree_v=3, periodic_u=False,\n"
                "#                                  periodic_v=False)",
            ),
        }
        if node_type in _GEO_IDIOM:
            cls, idiom = _GEO_IDIOM[node_type]
            lines.append("# Typed output (recommended) -- construct + assign:")
            lines.append(f"#   from mpynode._api2.geometry import {cls}")
            lines.append(f"#   {idiom}")
            lines.append("#")
            lines.append("# Any object exposing the required attrs is accepted (duck")
            lines.append("# typing); the flat self.X buffers above and the legacy")
            lines.append("# build_default_output(...) shim also still work.")
            lines.append("#")
        if node_type == "mPyLocator":
            lines.append("# self.draw takes ONE drawing, a '+' chain, or a list --")
            lines.append("# drawn front-to-back in the order you write them:")
            lines.append("#")
            lines.append("#   self.draw = DrawCircle(center=(0, 0, 0), radius=2)")
            lines.append("#   self.draw = DrawMesh(pts, counts, idx) + DrawPoints(pts)")
            lines.append("#   self.draw = [halo, cage, label]")
            lines.append("#")
            lines.append("# Building one up conditionally works too, and keeps the")
            lines.append("# append order:")
            lines.append("#")
            lines.append("#   items = []")
            lines.append("#   if self.showCage:")
            lines.append("#       items.append(DrawMesh(pts, counts, idx))")
            lines.append("#   self.draw = items")
            lines.append("#")
            lines.append("# self.draw = None draws nothing.")
            lines.append("#")
    # Document the node.X compute-time write surface.
    e4_supported = node_type in {
        "mPyDeformer", "mPySkinCluster",
        "mPyBlendShape",
    }
    if e4_supported:
        lines.append(
            "# Compute-time plug writes:"
        )
        lines.append(
            "#   `node.X` is auto-injected alongside `self`. Writing to"
        )
        lines.append(
            "#   `node.X = value` during compute routes through the"
        )
        lines.append(
            "#   MDataBlock (no cmds.setAttr) -- safer + faster than"
        )
        lines.append("#   the legacy path. Examples:")
        lines.append("#")
        is_deformer_family = node_type in {
            "mPyDeformer", "mPySkinCluster",
            "mPyBlendShape",
        }
        if is_deformer_family:
            lines.append(
                "#       node.outputGeometry[0] = my_ndarray   # commits mesh in one shot"
            )
        lines.append(
            "#       node.envelope = 0.5                   # numeric write"
        )
        lines.append("#")
    lines.append(
        "# Variables / functions you define HERE are available in the"
    )
    lines.append(
        "# Expression tab as bare names (no 'self.' prefix). For example:"
    )
    lines.append("#")
    lines.append("#   # In this Init tab:")
    lines.append("#   import numpy as np")
    lines.append("#   from numba import njit")
    lines.append("#")
    lines.append("#   @njit(fastmath=True)")
    lines.append("#   def my_kernel(p, amp):")
    lines.append("#...")
    lines.append("#")
    lines.append("#   # In the Expression tab (no import, no 'self.'):")
    lines.append("#   pts = my_kernel(pts, amp)")
    lines.append(bar)
    lines.append("")
    # A locator cannot draw without these, so seed the import for real rather
    # than as a comment -- the names are then live for autocomplete.
    if node_type == "mPyLocator":
        wrapped, row = [], "from mpynode._common.draw.draw_types import ("
        for i, name in enumerate(_LOCATOR_DRAW_TYPES):
            piece = name + ("" if i == len(_LOCATOR_DRAW_TYPES) - 1 else ", ")
            if len(row) + len(piece) > 76:
                wrapped.append(row.rstrip())
                row = "    "
            row += piece
        wrapped.append(row + ")")
        lines.extend(wrapped)
        lines.append("")
    return "\n".join(lines)
