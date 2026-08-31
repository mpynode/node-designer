"""Mpynode._node_registry — single source of truth for the supported node types.

Used by the UI scene tree, the toolbar New ▾ menu, and per-node-type
icon helpers. Each spec stores the wrapper class so callers can resolve
``native_type → wrapper_class`` (``get_wrapper_class``) without ad-hoc
dictionaries. The registry RESOLVES classes and WRAPS existing scene nodes
(``wrap_node`` via ``cls(name)``); it does NOT instantiate new
nodes. Interactive node creation goes through ``cmds.createNode`` +
``MPyNode.build()`` (the commands layer), not the registry.

Ships the spec dataclass + REGISTRY of supported node types.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class NodeTypeSpec:
    """Per-node-type metadata."""

    native_type: str
    wrapper_module: str
    wrapper_class_name: str
    description: str = ""
    # Native Maya proxy class this node type wraps, e.g.
    # "maya.api.OpenMaya.MPxNode" (api2). Shown in the Init header.
    native_class: str = ""
    # Maya API generation of ``native_class``: 2 = api2 (py_ref tree),
    # 1 = api1 (cpp_ref tree). Drives which doc sub-tree the URL targets.
    api: int = 2
    # Autodesk help-site doxygen page slug for ``native_class`` (the bit before
    # ".html"). Hand-verified: doxygen mangling + the api1/api2 tree split make
    # it NOT derivable. Empty = no doc link emitted.
    doc_slug: str = ""


    def get_wrapper_class(self):
        """Resolve the wrapper class lazily (avoids import cycles)."""
        mod = importlib.import_module(self.wrapper_module)
        return getattr(mod, self.wrapper_class_name)

    def doc_url(self, maya_version=None) -> Optional[str]:
        """Return the Autodesk API-ref URL for ``native_class`` versioned to
        the running (or given) Maya version, or None when unavailable.

        Verified against Maya 2022-2027. The help site changed its path
        segment (``Maya-SDK`` <= 2022, ``MAYA-API-REF`` >= 2023) and splits
        api2 classes into ``py_ref`` vs api1 classes into ``cpp_ref``. For
        unknown / unparseable versions we return None rather than emit a
        dead link (the header still shows the human-readable wraps line)."""
        if not self.doc_slug:
            return None
        if maya_version is None:
            try:
                import maya.cmds as mc

                maya_version = mc.about(version=True)
            except Exception:
                return None
        # "2026", "2026 Update 1", 2026 -> 2026
        import re

        m = re.search(r"\d{4}", str(maya_version))
        if not m:
            return None
        v = int(m.group(0))
        if v < 2022:
            return None
        tree = "Maya-SDK" if v <= 2022 else "MAYA-API-REF"
        ref = "py_ref" if self.api == 2 else "cpp_ref"
        return (
            f"https://help.autodesk.com/cloudhelp/{v}/ENU/"
            f"{tree}/{ref}/{self.doc_slug}.html"
        )


# native_class / api / doc_slug below are HAND-VERIFIED against Autodesk's help
# site (Maya 2022-2027). api2 -> py_ref tree; api1 (OpenMayaMPx proxy) ->
# cpp_ref tree (namespace-less slug). NodeTypeSpec.doc_url() builds the URL.
_MPXNODE_A2 = "maya.api.OpenMaya.MPxNode"
_MPXNODE_SLUG = "class_open_maya_1_1_m_px_node"
_MPXDEFORMER = "maya.OpenMayaMPx.MPxDeformerNode"
_MPXDEFORMER_SLUG = "class_m_px_deformer_node"

REGISTRY: dict[str, NodeTypeSpec] = {
    "mPyNode": NodeTypeSpec(
        native_type="mPyNode",
        wrapper_module="mpynode.wrappers._mpy_node",
        wrapper_class_name="MPyNode",
        description="Generic Python expression node.",
        native_class=_MPXNODE_A2, api=2, doc_slug=_MPXNODE_SLUG,
    ),
    "mPyLocator": NodeTypeSpec(
        native_type="mPyLocator",
        wrapper_module="mpynode.wrappers.mpy_locator",
        wrapper_class_name="MPyLocator",
        description="Custom viewport-drawn locator.",
        native_class="maya.api.OpenMayaUI.MPxLocatorNode", api=2,
        doc_slug="class_open_maya_u_i_1_1_m_px_locator_node",
    ),
    "mPyConstraint": NodeTypeSpec(
        native_type="mPyConstraint",
        wrapper_module="mpynode.wrappers.mpy_constraint",
        wrapper_class_name="MPyConstraint",
        description="Constraint with preset target/rest inputs + user output math.",
        native_class=_MPXNODE_A2, api=2, doc_slug=_MPXNODE_SLUG,
    ),
    "mPyIkSolver": NodeTypeSpec(
        native_type="mPyIkSolver",
        wrapper_module="mpynode.wrappers.mpy_iksolver",
        wrapper_class_name="MPyIkSolver",
        description="Custom IK solver \u2014 your joint solve in Python.",
        native_class="maya.OpenMayaMPx.MPxIkSolverNode", api=1,
        doc_slug="class_m_px_ik_solver_node",
    ),
    "mPyDeformer": NodeTypeSpec(
        native_type="mPyDeformer",
        wrapper_module="mpynode.wrappers.mpy_deformer",
        wrapper_class_name="MPyDeformer",
        description="Custom mesh deformer driven by a Python expression.",
        native_class=_MPXDEFORMER, api=1, doc_slug=_MPXDEFORMER_SLUG,
    ),
    "mPyTransform": NodeTypeSpec(
        native_type="mPyTransform",
        wrapper_module="mpynode.wrappers.mpy_transform",
        wrapper_class_name="MPyTransform",
        description="Custom transform with expression-driven local matrix.",
        native_class="maya.OpenMayaMPx.MPxTransform", api=1,
        doc_slug="class_m_px_transform",
    ),
    "mPyMesh": NodeTypeSpec(
        native_type="mPyMesh",
        wrapper_module="mpynode.wrappers.mpy_mesh",
        wrapper_class_name="MPyMesh",
        description="DG polygon geometry generator (connect outMesh → mesh.inMesh).",
        native_class=_MPXNODE_A2, api=2, doc_slug=_MPXNODE_SLUG,
    ),
    "mPySkinCluster": NodeTypeSpec(
        native_type="mPySkinCluster",
        wrapper_module="mpynode.wrappers.mpy_skin_cluster",
        wrapper_class_name="MPySkinCluster",
        description="Expression-driven skinCluster (MPxSkinCluster; write your own LBS/DQ/custom).",
        native_class="maya.OpenMayaMPx.MPxSkinCluster", api=1,
        doc_slug="class_m_px_skin_cluster",
    ),
    "mPyBlendShape": NodeTypeSpec(
        native_type="mPyBlendShape",
        wrapper_module="mpynode.wrappers.mpy_blend_shape",
        wrapper_class_name="MPyBlendShape",
        description="Expression-driven blendShape (aliased weight[] + targetGeometry[]).",
        # mPyBlendShape is built on MPxDeformerNode, not MPxBlendShape --
        # deliberately. MPxBlendShape DOES ship (api1, Maya 2024 + 2026); it
        # is unusable here because it never calls deform() and its native
        # weight[] blocks the aliased user-attr weight[]. Reasons in full in
        # mpynode._api1.mpy_blend_shape.
        native_class=_MPXDEFORMER, api=1, doc_slug=_MPXDEFORMER_SLUG,
    ),
    # mPyFile -- expression-driven file-texture shading node. Mirrors Maya's
    # stock ``file`` node, with the colour-space / kernel / sampling math
    # exposed in the Init tab and the VP2 plumbing in the Viewport tab.
    "mPyFile": NodeTypeSpec(
        native_type="mPyFile",
        wrapper_module="mpynode.wrappers.mpy_file",
        wrapper_class_name="MPyFile",
        description="Expression-driven file texture (Hypershade + VP2 shading).",
        native_class=_MPXNODE_A2, api=2, doc_slug=_MPXNODE_SLUG,
    ),
    # DG generator node types for curve / surface output, mirroring mPyMesh's
    # "DG generator" shape (connect outCurve / outSurface -> downstream shape
    # input). The wrappers follow mpynode.wrappers.mpy_mesh: they wrap the api2
    # MPx subclasses and inherit MPyNode, which provides the attr / variable /
    # init / profile / watch surface the Node Designer panes need.
    "mPyNurbsCurve": NodeTypeSpec(
        native_type="mPyNurbsCurve",
        wrapper_module="mpynode.wrappers.mpy_nurbs_curve",
        wrapper_class_name="MPyNurbsCurve",
        description="DG NURBS curve generator (connect outCurve \u2192 curveShape.create).",
        native_class=_MPXNODE_A2, api=2, doc_slug=_MPXNODE_SLUG,
    ),
    "mPyNurbsSurface": NodeTypeSpec(
        native_type="mPyNurbsSurface",
        wrapper_module="mpynode.wrappers.mpy_nurbs_surface",
        wrapper_class_name="MPyNurbsSurface",
        description="DG NURBS surface generator (connect outSurface \u2192 nurbsShape.create).",
        native_class=_MPXNODE_A2, api=2, doc_slug=_MPXNODE_SLUG,
    ),
}


def get_spec(native_type: str) -> Optional[NodeTypeSpec]:
    """Look up a spec by Maya node type name (static REGISTRY only).

    The compiled C++ node created by the coexist "Convert to C++" is deliberately
    NOT registered: an unregistered type is hidden from the scene tree / ``ls``
    for free, which is exactly the coexist contract (the hidden sibling drives
    downstream while the Python node stays the visible source of truth)."""
    return REGISTRY.get(native_type)


def all_native_types() -> list[str]:
    """All supported node type names (the static REGISTRY). The coexist compiled
    sibling is intentionally excluded (unregistered = hidden from the tree)."""
    return list(REGISTRY.keys())


def display_label(name: str) -> str:
    """Lower-case the first letter of a class name for display / node naming.

    One helper serves BOTH the built-in root wrappers and user subclasses:
    every built-in native type already IS its wrapper class name with the first
    letter lowered (``MPyFile`` -> ``mPyFile``), matching Maya's convention that
    scene node type names start lowercase (``parentConstraint``). A user class
    ``BlackWhiteFile`` becomes ``blackWhiteFile`` the same way. Empty in, empty
    out.
    """
    if not name:
        return ""
    return name[:1].lower() + name[1:]


# mPyNode is the base class and the go-to node, so every "New node" menu
# surfaces it first, separated from the specialty flavors (alphabetical).
PINNED_NEW_NODE_TYPE = "mPyNode"


def iter_new_node_menu_entries():
    """Yield native type names in "New node" menu order: the pinned type
    first, then ``None`` (a separator marker), then the rest alphabetically.

    Shared by every menu that lists creatable node types (toolbar New ▾,
    the Node ▸ New Node submenu) so the ordering + separator live in one
    place. ``None`` entries mean "insert a separator here".
    """
    pinned = PINNED_NEW_NODE_TYPE
    if pinned in REGISTRY:
        yield pinned
        yield None  # separator between the pinned base type and the rest
    for native_type in sorted(REGISTRY):
        if native_type == pinned:
            continue
        yield native_type


def wrap_node(name: str, native_type: Optional[str] = None):
    """Wrap an EXISTING scene node by name; does not create one.

    ``native_type`` is optional. Omit it -- ``wrap_node(name)`` -- and the type
    is read off the node itself, which is what an expression normally wants.
    Pass it when the caller already knows: the scene tree hands its rows'
    type down with every signal, so re-querying Maya would be a round-trip
    for an answer already in hand.

    Returns the type-specific wrapper (``MPySkinCluster`` for an
    ``mPySkinCluster`` node), or ``None`` if the node doesn't exist, isn't a
    registered mPy type, or its wrapper class can't be imported.
    (``MPyNode(name)`` does the same via factory dispatch.)

    ONE name, deliberately. This was ``wrap(name)`` plus
    ``wrap_node(name, type)``, and ``wrap`` on its own said nothing about what
    it wrapped: read in an expression it could as easily have meant a wrap
    DEFORMER, or casting data to a mesh. The word is now free for a geometry
    factory, which is the meaning a reader reaches for first.
    """
    if native_type is None:
        import maya.cmds as mc

        try:
            if not mc.objExists(name):
                return None
            native_type = mc.nodeType(name)
        except Exception:
            return None
    spec = get_spec(native_type)
    if spec is None:
        return None
    try:
        cls = spec.get_wrapper_class()
        return cls(name)
    except Exception as exc:
        import sys

        sys.stderr.write(
            "[wrap_node] could not wrap %r as %r: %s\n"
            % (name, native_type, exc))
        return None
