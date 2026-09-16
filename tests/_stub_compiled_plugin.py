"""Test-only "compiled-like" plug-in.

Registers plugin-provided node types so the Py->C++ coexist tests can exercise a
genuine PLUGIN-PROVIDED compiled target without depending on any shipped
``.bundle``:

- ``stubCompiled`` -- a minimal ``MPxNode`` with float inputs ``inA``/``inB`` and
  a float output ``outC``. The real attr schema matters: the coexist reroute
  moves the Python node's OUTPUT edges onto the compiled node and duplicates its
  INPUT edges, so the compiled node must actually carry matching plugs (an
  attr-less stub would make reroute a silent no-op / false pass).
- ``stubCompiledLocator`` -- the same ``inA``/``inB``/``outC`` schema on an
  ``MPxLocatorNode`` so the locator convert/revert path (same-parent create +
  ``lodVisibility`` idle-safety) is exercised.

Class "StubCompiled" derives ``node_type_name == "stubCompiled"`` (and
"StubCompiledLocator" -> "stubCompiledLocator") via ``derive_class_identity`` --
matching ``kTypeName`` here so the gate resolves. The type ids live in Autodesk's
0x0-0x7ffff test/prototyping block (never shipped).
"""
import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui


def maya_useNewAPI():
    pass


def _add_abc(node_cls):
    """Add float inputs ``inA``/``inB`` and readable float output ``outC`` to
    ``node_cls`` (the node type currently being initialized), wiring
    ``attributeAffects(inA|inB, outC)``. Shared by both stub node types.

    Names are deliberately NOT single letters: a ``locator`` shape already ships
    a built-in attr with short name ``c`` (``center``), so an output ``c`` would
    collide ("Object already exists") on ``stubCompiledLocator``."""
    n_attr          = om.MFnNumericAttribute()
    a               = n_attr.create("inA", "inA", om.MFnNumericData.kFloat, 0.0)
    n_attr.writable = True
    n_attr.storable = True
    n_attr.keyable  = True
    node_cls.addAttribute(a)
    b               = n_attr.create("inB", "inB", om.MFnNumericData.kFloat, 0.0)
    n_attr.writable = True
    n_attr.storable = True
    n_attr.keyable  = True
    node_cls.addAttribute(b)
    c               = n_attr.create("outC", "outC", om.MFnNumericData.kFloat, 0.0)
    n_attr.writable = False
    n_attr.storable = False
    n_attr.readable = True
    node_cls.addAttribute(c)
    node_cls.attributeAffects(a, c)
    node_cls.attributeAffects(b, c)


class _StubCompiledNode(om.MPxNode):
    kTypeName = "stubCompiled"
    kTypeId   = om.MTypeId(0x0007FE30)

    @staticmethod
    def creator():
        return _StubCompiledNode()

    @staticmethod
    def initialize():
        _add_abc(_StubCompiledNode)


class _StubCompiledLocatorNode(omui.MPxLocatorNode):
    kTypeName = "stubCompiledLocator"
    kTypeId   = om.MTypeId(0x0007FE31)

    @staticmethod
    def creator():
        return _StubCompiledLocatorNode()

    @staticmethod
    def initialize():
        _add_abc(_StubCompiledLocatorNode)


def initializePlugin(plugin):
    fn = om.MFnPlugin(plugin)
    fn.registerNode(
        _StubCompiledNode.kTypeName, _StubCompiledNode.kTypeId,
        _StubCompiledNode.creator, _StubCompiledNode.initialize)
    fn.registerNode(
        _StubCompiledLocatorNode.kTypeName, _StubCompiledLocatorNode.kTypeId,
        _StubCompiledLocatorNode.creator, _StubCompiledLocatorNode.initialize,
        om.MPxNode.kLocatorNode)


def uninitializePlugin(plugin):
    fn = om.MFnPlugin(plugin)
    fn.deregisterNode(_StubCompiledNode.kTypeId)
    fn.deregisterNode(_StubCompiledLocatorNode.kTypeId)
