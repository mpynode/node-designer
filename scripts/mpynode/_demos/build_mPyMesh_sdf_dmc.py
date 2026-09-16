"""Demo builder: mPyMesh SDF dual-marching-cubes igloo.

An ``mPyMesh`` node that takes an ORDERED stream of SDF primitives
(spheres / boxes / cylinders) as a matrix array plus parallel per-shape
arrays (type, additive flag, smoothing, dimensions), folds them with CSG
(union / smooth-union / difference) and extracts a quad-dominant mesh via
dual marching cubes. The heavy lifting lives in the shared, native-portable
module ``mpynode._common.nodes.mesh.sdf_dmc``; this node just reads its plugs and calls
``mesh_from_shapes``.

The node also carries authoring commands (``addSphere`` / ``addBox`` /
``addCylinder``, ``@maya_command``-flagged so they compile to MPxCommands)
and a ``setup`` hook that creates the render mesh shape. The example scene
recreates the ``TestSDFIgloo`` igloo from ~40 live transforms.

INIT / COMPUTE / METHODS sources are module-level strings so the node test
and the example builder share one definition.
"""
from __future__ import annotations

import maya.cmds as mc


INIT_SOURCE = """\
import numpy as np
from mpynode._api2.geometry import Mesh
from mpynode._common.nodes.mesh.sdf_dmc import _mesh_packed


def _dense_over(raw, defaults):
    # Overlay a per-shape array input -- ALREADY read off the plug as a dense
    # numpy array (self.<name>) -- onto the demo's semantic defaults, returning
    # an array of length len(defaults). Every numeric array input surfaces as a
    # dense, gap-filled numpy array (unset slots hold the attribute default)
    # whose POSITION is the logical plug index, so parallel arrays align by
    # shape. Taking the READ array as the argument (NOT `self`) is what keeps the
    # whole compute deterministically lowerable to pure C++ (nd_lower/py_to_cpp):
    # a helper that takes `self` and does getattr() cannot be transpiled. This is
    # behaviour-identical to the historical _read_dense(self, name, default)
    # overlay -- proven byte-exact by native/tests/metaballs_glue_parity.py.
    out = np.array(defaults)
    n = out.shape[0]
    k = raw.shape[0]
    if k > n:
        k = n
    out[0:k] = raw[0:k]
    return out
"""

COMPUTE_SOURCE = """\
mats = np.asarray(self.shapeMatrix, dtype=np.float64)
n = mats.shape[0]
shape_type = _dense_over(self.shapeType, np.zeros(n, dtype=np.int64))
additive = _dense_over(self.additive, np.ones(n, dtype=np.int64))
smoothing = _dense_over(self.smoothing, np.zeros(n, dtype=np.float64))
radius = _dense_over(self.radius, np.where(shape_type == 2, 0.5, 1.0))
height = _dense_over(self.height, np.ones(n, dtype=np.float64))
axis = _dense_over(self.axis, np.ones(n, dtype=np.int64))
half = _dense_over(self.halfExtents, np.full((n, 3), 0.5))
packed = _mesh_packed(mats, shape_type, additive, smoothing, radius, height,
                      axis, half, int(self.resolution), float(self.isoValue))
V = int(packed[0])
F = int(packed[1])
points = packed[2:2 + 3 * V].reshape(V, 3)
indices = packed[2 + 3 * V:2 + 3 * V + 4 * F].astype(np.int32)
counts = np.full(F, 4, dtype=np.int32)
self.outMesh = Mesh(points=points, counts=counts, indices=indices)
"""


METHODS_SOURCE = """\
from typing import Optional


def _resolve_transform(transform):
    # Resolve the transform to wire: the explicit arg, else the first
    # selected transform, else a freshly created one.
    from maya import cmds as mc
    if transform is not None:
        return transform
    sel = mc.ls(selection=True, long=True, type="transform") or []
    return sel[0] if sel else mc.createNode("transform", name="sdfShape#")


def _next_index(node):
    # Next free logical index on shapeMatrix; the SDF fold order IS the
    # array index, so always append past the current max (gap-safe).
    from maya import cmds as mc
    idxs = mc.getAttr(node + ".shapeMatrix", multiIndices=True) or []
    return (max(idxs) + 1) if idxs else 0


def _ensure_double(transform, name, value):
    # Add a keyable double attr (default = value) to the transform if it is
    # missing, then set it. Returns the plug to connect.
    from maya import cmds as mc
    if not mc.attributeQuery(name, node=transform, exists=True):
        mc.addAttr(transform, longName=name, attributeType="double",
                   defaultValue=float(value), keyable=True)
    mc.setAttr(transform + "." + name, float(value))
    return transform + "." + name


def _ensure_double3(transform, name, values):
    # Add a keyable double3 compound (e.g. box half-extents) if missing,
    # then set it. Returns the parent plug to connect.
    from maya import cmds as mc
    if not mc.attributeQuery(name, node=transform, exists=True):
        mc.addAttr(transform, longName=name, attributeType="double3")
        for ax in ("X", "Y", "Z"):
            mc.addAttr(transform, longName=name + ax, attributeType="double",
                       parent=name, keyable=True)
    mc.setAttr(transform + "." + name, *(float(v) for v in values),
               type="double3")
    return transform + "." + name


def _begin_shape(self, transform, shape_type, additive, smoothing):
    # Shared wiring for every add*: resolve the transform, claim the next
    # index, connect its worldMatrix into shapeMatrix, and stamp the common
    # per-shape CSG flags. Returns (node, transform, idx).
    from maya import cmds as mc
    node = self.get_name()
    transform = _resolve_transform(transform)
    idx = _next_index(node)
    mc.connectAttr(transform + ".worldMatrix[0]",
                   "%s.shapeMatrix[%d]" % (node, idx), force=True)
    mc.setAttr("%s.shapeType[%d]" % (node, idx), int(shape_type))
    mc.setAttr("%s.additive[%d]" % (node, idx), int(bool(additive)))
    mc.setAttr("%s.smoothing[%d]" % (node, idx), float(smoothing))
    return node, transform, idx


@maya_command
def addSphere(self, transform: Optional[str] = None, radius=1.0,
              additive=True, smoothing=0.0):
    from maya import cmds as mc
    node, transform, idx = _begin_shape(self, transform, 0, additive, smoothing)
    plug = _ensure_double(transform, "radius", radius)
    mc.connectAttr(plug, "%s.radius[%d]" % (node, idx), force=True)
    return transform


@maya_command
def addBox(self, transform: Optional[str] = None, half=(0.5, 0.5, 0.5),
           additive=True, smoothing=0.0):
    from maya import cmds as mc
    node, transform, idx = _begin_shape(self, transform, 1, additive, smoothing)
    plug = _ensure_double3(transform, "halfExtents", half)
    mc.connectAttr(plug, "%s.halfExtents[%d]" % (node, idx), force=True)
    return transform


@maya_command
def addCylinder(self, transform: Optional[str] = None, radius=0.5,
                height=1.0, axis=1, additive=True, smoothing=0.0):
    from maya import cmds as mc
    node, transform, idx = _begin_shape(self, transform, 2, additive, smoothing)
    rplug = _ensure_double(transform, "radius", radius)
    hplug = _ensure_double(transform, "height", height)
    mc.connectAttr(rplug, "%s.radius[%d]" % (node, idx), force=True)
    mc.connectAttr(hplug, "%s.height[%d]" % (node, idx), force=True)
    mc.setAttr("%s.axis[%d]" % (node, idx), int(axis))
    return transform
"""


# Per-shape input arrays: (name, attr_type, default_value). All multi
# (is_array=True). Maya omits any multi element whose value equals the attribute
# default when it writes a .ma, so a default declared here MUST match the one
# COMPUTE_SOURCE's _dense_over overlays for that stream -- otherwise an authored
# value silently reverts on reload. axis is 1 (Y), additive True and height 1.0,
# all matching np.ones (and addCylinder's own axis/height defaults);
# shapeType/smoothing overlay 0, which the bare default already is.
#
# Two are still NOT declared, for different reasons:
#
#   halfExtents (overlays 0.5): BLOCKED. _api2.helpers.array_gap_default returns
#     a hardcoded [0,0,0] for vector/euler/color -- it does NOT read the
#     declared default the way it does for numerics -- and emit_attr's
#     _array_gap_default_cpp mirrors that, so the two agree today. Declaring 0.5
#     would move the ATTRIBUTE default without moving either gap fill: an
#     authored (0.5,0.5,0.5) would start being omitted from the .ma and reload
#     as (0,0,0) at any interior index. That is a NET REGRESSION over the
#     current state, where 0.5 differs from the default and is always written.
#     Needs the vector gap fill honouring the default on BOTH sides first.
#
#   radius (overlays np.where(shape_type == 2, 0.5, 1.0)): no constant can
#     match it -- 0.5 for a cylinder, 1.0 otherwise. Any single declared default
#     fixes one shape family and breaks the other. Left undeclared: the value
#     that would be dropped is 0.0, a degenerate zero-radius primitive, and both
#     addSphere and addCylinder CONNECT radius (a connected element is always
#     written to the .ma), so the revert cannot reach the authoring path.
_ARRAY_INPUTS = [
    ("shapeMatrix", "matrix", None),
    ("shapeType", "int", None),
    ("additive", "bool", True),
    ("smoothing", "double", None),
    ("radius", "double", None),
    ("height", "double", 1.0),
    ("axis", "int", 1),
    ("halfExtents", "vector", None),
]


def build_methods_source():
    """Compose the node's Methods source: the authoring commands here plus
    the shipped self-first ``setup`` (single source of truth, so the body
    never drifts from ``node_setups/mPyMesh.py``)."""
    from mpynode._common import node_setups
    setup_src = node_setups.setup_source_for_type("mPyMesh") or ""
    return METHODS_SOURCE + "\n\n" + setup_src if setup_src else METHODS_SOURCE


def configure_node(wrapper):
    """Add the SDF inputs and set the init + compute + methods sources on
    ``wrapper`` (an MPyMesh). Shared by the node test and the example builder."""
    # Dense (non-sparse) arrays: the element index IS the CSG fold order, so
    # the parallel arrays line up by logical index.
    for name, attr_type, default_value in _ARRAY_INPUTS:
        wrapper.add_input_attr(name, attr_type, is_array=True,
                               default_value=default_value)
    wrapper.add_input_attr("resolution", "int", default_value=8)
    wrapper.add_input_attr("isoValue", "double", default_value=0.0)
    wrapper.set_init_expression(INIT_SOURCE)
    wrapper.set_compute_expression(COMPUTE_SOURCE)
    wrapper.set_methods_source(build_methods_source())


_KIND_NAME = {0: "sphere", 1: "box", 2: "cyl"}


def _add_primitive(wrapper, group, index, prim):
    """Create a live transform under ``group`` with the primitive's TRS and
    wire it into the node through the matching authoring command."""
    kind = prim["kind"]
    xf = mc.createNode("transform", parent=group,
                       name="%s%02d" % (_KIND_NAME.get(kind, "shape"), index))
    mc.setAttr(xf + ".translate", *[float(v) for v in prim["translate"]])
    mc.setAttr(xf + ".rotate",    *[float(v) for v in prim["rotate"]])
    mc.setAttr(xf + ".scale",     *[float(v) for v in prim["scale"]])
    common = dict(transform=xf, additive=prim["additive"],
                  smoothing=prim["smoothing"])
    if kind == 0:
        wrapper.call_command("addSphere", radius=prim["radius"], **common)
    elif kind == 1:
        wrapper.call_command("addBox", half=prim["half"], **common)
    else:
        wrapper.call_command("addCylinder", radius=prim["radius"],
                             height=prim["height"], axis=prim["axis"], **common)
    return xf


def build():
    from mpynode._demos import sdf_igloo
    from mpynode._demos.save_demo import save_demo

    mc.file(new=True, force=True)
    for plugin in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(plugin, q=True, loaded=True):
            mc.loadPlugin(plugin)
    from mpynode.wrappers.mpy_mesh import MPyMesh

    wrapper = MPyMesh.create(name="sdfIgloo")
    configure_node(wrapper)
    node  = wrapper.get_name()

    group = mc.createNode("transform", name="iglooShapes")
    for i, prim in enumerate(sdf_igloo.igloo_primitives()):
        _add_primitive(wrapper, group, i, prim)

    # setup() builds the render mesh + wires outMesh -> inMesh + shading.
    from mpynode._common.methods.methods_registry import run_node_setup
    run_node_setup(wrapper, selection=[])

    # resolution is a LIVE plug: 16 reproduces the TestSDFIgloo reference
    # exactly; lower for snappier interaction, higher (or the C++ build) for
    # denser fields.
    mc.setAttr(node + ".resolution", 16)
    return save_demo("mPyMesh_sdf_dmc")


if __name__ == "__main__":
    build()
