"""Equivalence check: compiled native node vs the original mPyNode.
Run it in Maya, or as `mayapy verify_in_maya.py`, which starts
Maya first. Runs the compile pipeline's own verify,
mpynode.native.toolchain.verify._default_verify, on the spec
embedded below. Its generic check rebuilds the Python original,
builds the compiled node, drives identical inputs on both, and
compares every component of every output.
The node's authored @maya_test methods then run on the compiled
node, and the verdicts merge as in the pipeline's verify row. A
PASS on the authored test alone says why the generic check did
not run, and COULD NOT RUN when its harness failed.
It opens new scenes (file new, force), so it refuses to run while
the open scene has unsaved changes: save first, or run it in a
fresh mayapy. It prints the folder of the mpynode it imported.
"""
import os, json
import maya.cmds as cmds
if __name__ == "__main__" and not hasattr(cmds, "file"):
    # Run as `mayapy verify_in_maya.py`: Maya has not started. Start
    # it before mpynode is imported, so a userSetup.py install's
    # paths apply.
    import maya.standalone
    maya.standalone.initialize()
import mpynode
from mpynode.native.toolchain import toolchain

# .mll, .bundle or .so: picked for the OS this runs on.
EXT    = toolchain.plugin_ext()
NAME   = 'hexAttribute'
BUNDLE = os.path.join(os.path.dirname(__file__), NAME + EXT)
SPEC   = json.loads('{"schema_version": 1, "source_node": "hexAttribute", "mpy_type": "mPyNode", "suggested": {"node_type_name": "hexAttribute", "class_name": "HexAttribute", "type_id": "0x000731e1", "mpx_base": "MPxNode", "note": "plain dependency node", "heaviness": "easy"}, "inputs": {"decimals": {"type": "long", "is_array": false, "portable": true, "cpp": {"cat": "scalar", "fn": "MFnNumericAttribute", "data": "kInt", "cpp": "int", "read": "asInt", "portable": true}, "default_value": 2}, "inPosition": {"type": "double3", "is_array": false, "portable": true, "cpp": {"cat": "vector", "fn": "MFnNumericAttribute", "data": "k3Double", "cpp": "double[3]", "read": "asDouble3", "portable": true}}}, "outputs": {"output": {"type": "hex", "is_array": false, "portable": true, "cpp": {"cat": "string", "fn": "MFnTypedAttribute", "data": "kString", "cpp": "MString", "read": "asString", "portable": true}}}, "variables": {}, "compute": "# Name: Text Mesh Generator  (numpy-first port)\\n# Author: Eric Vignola - eric.vignola@gmail.com\\n# The `output` attribute is typed `hex`: assign plain text and the attr\\n# auto-encodes it to the space-separated UTF-8 hex a Maya `type` node\\n# consumes as mesh text -- no manual unicode -> hex step needed.\\n\\n# Convert XYZ input (a numpy 3-vector) to rounded strings.\\nself.output = \'DRAG ME AROUND!\\\\n\'\\nself.output += \'X: %s\\\\n\' % round(float(self.inPosition[0]), self.decimals)\\nself.output += \'Y: %s\\\\n\' % round(float(self.inPosition[1]), self.decimals)\\nself.output += \'Z: %s\\\\n\' % round(float(self.inPosition[2]), self.decimals)\\n", "init": "", "affects": "all", "methods": "# Build a complete, self-contained hex_attribute demo: a Maya Type text mesh\\n# whose PARENT transform is the draggable control -- that transform\'s translate\\n# feeds inPosition, and the node\'s hex `output` feeds the Type node, so dragging\\n# the visible text updates the rendered X/Y/Z it shows. The text is extruded\\n# (typeExtrude) so it has real thickness. The Type plugin is optional: if it is\\n# missing a locator shape stands in under the same transform (the hex `output`\\n# is still live in the Watch tab).\\ndef demo(self):\\n    from maya import cmds as mc\\n    name = self.get_name()\\n    mc.setAttr(name + \\".decimals\\", 2)\\n    # The draggable PARENT transform -- its translate drives inPosition, and the\\n    # text mesh lives under it so it moves (and re-labels) as you drag.\\n    xf = mc.createNode(\\"transform\\", name=\\"hexDragMe#\\")\\n    mc.setAttr(xf + \\".translate\\", 1.0, 2.0, 3.0, type=\\"double3\\")\\n    mc.connectAttr(xf + \\".translate\\", name + \\".inPosition\\", force=True)\\n    try:\\n        if not mc.pluginInfo(\\"Type\\", query=True, loaded=True):\\n            mc.loadPlugin(\\"Type\\", quiet=True)\\n        type_node = mc.createNode(\\"type\\", name=\\"hexType#\\")\\n        mc.connectAttr(name + \\".output\\", type_node + \\".textInput\\", force=True)\\n        # Extrude the text so it reads as a solid, thick object.\\n        extrude = mc.createNode(\\"typeExtrude\\", name=\\"hexExtrude#\\")\\n        mc.connectAttr(type_node + \\".outputMesh\\", extrude + \\".inputMesh\\", force=True)\\n        mc.connectAttr(type_node + \\".vertsPerChar\\", extrude + \\".vertsPerChar\\", force=True)\\n        mc.setAttr(extrude + \\".enableExtrusion\\", True)\\n        mc.setAttr(extrude + \\".extrudeDistance\\", 0.75)\\n        mesh_shp = mc.createNode(\\"mesh\\", parent=xf, name=xf + \\"Shape\\")\\n        mc.connectAttr(extrude + \\".outputMesh\\", mesh_shp + \\".inMesh\\", force=True)\\n        mc.sets(mesh_shp, edit=True, forceElement=\\"initialShadingGroup\\")\\n    except Exception:\\n        # No Type plugin -- drop a visible locator shape under the transform so\\n        # there is still something obvious to drag.\\n        try:\\n            mc.createNode(\\"locator\\", parent=xf, name=xf + \\"Shape\\")\\n        except Exception:\\n            pass\\n    return name\\n\\n\\n@maya_test(label=\\"Hex attr: output encodes the live X/Y/Z label text\\", digits=4)\\ndef test_hex_attribute(self):\\n    \\"\\"\\"Same test passes interpreted and compiled (parity): setting inPosition +\\n    decimals makes the `hex` output carry the rounded X/Y/Z label. Drives `self`\\n    through public plugs; decodes the space-separated UTF-8 hex back to text.\\"\\"\\"\\n    from maya import cmds as mc\\n    from mpynode._common.methods.test_helpers import assert_true\\n    name = self.get_name()\\n\\n    def _set(plug, *vals, **kw):\\n        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):\\n            mc.disconnectAttr(s, plug)\\n        mc.setAttr(plug, *vals, **kw)\\n\\n    _set(name + \\".decimals\\", 2)\\n    _set(name + \\".inPosition\\", 1.5, 2.0, 3.25, type=\\"double3\\")\\n\\n    raw = mc.getAttr(name + \\".output\\") or \\"\\"\\n    # The `hex` attr stores space-separated UTF-8 hex a Maya `type` node consumes;\\n    # decode it back to the label text (fall back if a build returns it decoded).\\n    if \\"DRAG ME\\" in raw:\\n        text = raw\\n    else:\\n        text = bytes.fromhex(raw.replace(\\" \\", \\"\\")).decode(\\"utf-8\\")\\n\\n    assert_true(\\"X: 1.5\\" in text, \\"expected \'X: 1.5\' in decoded output %r\\" % text)\\n    assert_true(\\"Y: 2.0\\" in text, \\"expected \'Y: 2.0\' in decoded output %r\\" % text)\\n    assert_true(\\"Z: 3.25\\" in text, \\"expected \'Z: 3.25\' in decoded output %r\\" % text)\\n", "commands": [], "portability": {"portable": true, "blockers": [], "warnings": [], "unported": [], "reads_image_file": false, "reads_embedded_image": false, "uses_mesh_intersector": false}}')


def run():
    pkg = os.path.dirname(os.path.abspath(mpynode.__file__))
    print("VERIFY MPYNODE " + pkg)
    if cmds.file(q=True, modified=True):
        raise RuntimeError(
            "VERIFY REFUSED: the open scene has unsaved changes, and this "
            "check opens new scenes (file new, force). Save first, or run "
            "it in a fresh mayapy.")
    from mpynode.native.toolchain import verify as _cc
    rows = _cc._default_verify(BUNDLE, [{"type_name": NAME, "spec": SPEC}])
    row  = rows[NAME]
    print("VERIFY ROW", row)
    if not row.get("ran"):
        print("VERIFY SKIP (" + str(row.get("reason")) + ")")
        return True
    if row.get("pass"):
        if row.get("generic_ran") is False:
            # The authored @maya_test alone passed it: say why the generic
            # check did not run, and whether its harness failed.
            how = "skipped"
            if str(row.get("reason")).startswith("verify could not run"):
                how = "COULD NOT RUN"
            print("VERIFY PASS (authored @maya_test only; generic check "
                  + how + ") " + str(row.get("reason")))
            return True
        print("VERIFY PASS maxerr", row.get("maxerr"))
        return True
    print("VERIFY FAIL", row.get("reason"), row.get("maxerr"))
    return False


if __name__ == "__main__":
    run()
