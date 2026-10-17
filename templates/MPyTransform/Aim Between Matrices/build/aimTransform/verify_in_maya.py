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
The guard trusts Maya's own modified flag, so a selection-only
change isn't flagged. A verify leaves its own scene modified, so
a second run in the same session is refused too: clear that
scene with cmds.file(new=True, force=True) first.
Run as a script, a FAIL raises, so mayapy exits 1 and Maya shows
an error; a PASS or SKIP exits 0. run() returns False on a FAIL.
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
NAME   = 'aimTransform'
BUNDLE = os.path.join(os.path.dirname(__file__), NAME + EXT)
SPEC   = json.loads('{"schema_version": 1, "source_node": "aimTransform", "mpy_type": "mPyTransform", "suggested": {"node_type_name": "aimTransform", "class_name": "AimTransform", "type_id": "0x0007313f", "mpx_base": "MPxTransform", "note": "custom transform matrix", "heaviness": "medium"}, "inputs": {"matrix0": {"type": "matrix", "is_array": false, "portable": true, "cpp": {"cat": "matrix", "fn": "MFnMatrixAttribute", "data": "kDouble", "cpp": "MMatrix", "read": "asMatrix", "portable": true}}, "matrix1": {"type": "matrix", "is_array": false, "portable": true, "cpp": {"cat": "matrix", "fn": "MFnMatrixAttribute", "data": "kDouble", "cpp": "MMatrix", "read": "asMatrix", "portable": true}}, "parentWorld": {"type": "matrix", "is_array": false, "portable": true, "cpp": {"cat": "matrix", "fn": "MFnMatrixAttribute", "data": "kDouble", "cpp": "MMatrix", "read": "asMatrix", "portable": true}}}, "outputs": {}, "variables": {}, "compute": "m0 = self.matrix0.asNumpy()\\nm1 = self.matrix1.asNumpy()\\np0 = m0[3, :3]\\np1 = m1[3, :3]\\nfwd = p1 - p0\\nlength = float(np.linalg.norm(fwd))\\nif length < 1e-9:\\n    fwd = np.array([1.0, 0.0, 0.0])\\nelse:\\n    fwd = fwd / length\\nup = np.array([0.0, 1.0, 0.0])\\nif abs(float(np.dot(fwd, up))) > 0.999:\\n    up = np.array([0.0, 0.0, 1.0])\\nside = np.cross(fwd, up)\\nside = side / (float(np.linalg.norm(side)) + 1e-12)\\nup2 = np.cross(side, fwd)\\nM = np.eye(4)\\nM[0, :3] = fwd\\nM[1, :3] = up2\\nM[2, :3] = side\\nM[3, :3] = 0.5 * (p0 + p1)\\nP = self.parentWorld.asNumpy()\\nself.local_matrix = M @ np.linalg.inv(P)\\nself.apply_rotate = True\\nself.apply_translate = True\\nself.apply_scale = True\\n", "init": "import numpy as np\\n", "affects": "all", "methods": "class SetupError(Exception):\\n    \\"\\"\\"The current selection / scene state can\'t support setup for this node.\\n    Message is user-facing (it names what to select).\\"\\"\\"\\n\\n\\n\\n@maya_demo(label=\\"Aim Between Two Locators\\")\\ndef demo(self):\\n    \\"\\"\\"Drop two locators and aim this transform between them. ``start`` feeds\\n    ``matrix0`` and ``end`` feeds ``matrix1``; the transform lands at their\\n    midpoint with its X axis pointing start -> end. A child cube rides the aim\\n    so the orientation is visible -- move either locator to watch it track.\\n\\n    The aim runs in LOCAL space: it writes ``self.local_matrix = M @ inv(P)``\\n    where ``P`` is the ``parentWorld`` matrix input (identity while this node\\n    sits at the world root). To aim under a moving parent, connect that\\n    parent\'s ``worldMatrix[0]`` -> ``parentWorld`` and the node stays cycle-free\\n    because it never reads its own DAG parent.\\"\\"\\"\\n    from maya import cmds as mc\\n    name = self.get_name()\\n\\n    start = mc.spaceLocator(name=\\"aimStart#\\")[0]\\n    end = mc.spaceLocator(name=\\"aimEnd#\\")[0]\\n    mc.setAttr(start + \\".translate\\", -3.0, 0.0, 0.0, type=\\"double3\\")\\n    mc.setAttr(end + \\".translate\\", 3.0, 2.0, 0.0, type=\\"double3\\")\\n    mc.connectAttr(start + \\".worldMatrix[0]\\", name + \\".matrix0\\", force=True)\\n    mc.connectAttr(end + \\".worldMatrix[0]\\", name + \\".matrix1\\", force=True)\\n\\n    # A thin child cube visualizes the aim (its long axis is X).\\n    cube = mc.polyCube(name=\\"aimArrow#\\", width=2.0, height=0.2, depth=0.2)[0]\\n    mc.parent(cube, name, relative=True)\\n\\n    mc.select(end, replace=True)\\n    try:\\n        for _panel in mc.getPanel(type=\\"modelPanel\\") or []:\\n            _cam = mc.modelEditor(_panel, query=True, camera=True)\\n            if _cam:\\n                mc.viewFit(_cam, allObjects=True)\\n    except Exception:\\n        pass\\n    return name\\n\\n\\n@maya_test(label=\\"Aim: midpoint origin, X aims matrix0->matrix1, orthonormal\\", digits=4)\\ndef test_aim(self):\\n    \\"\\"\\"Validate the node\'s INTENT (the same test passes on the interpreted node\\n    and its C++ compile -> parity): wiring two locators\' worldMatrix into\\n    matrix0/matrix1 lands this transform at their MIDPOINT with its X axis aiming\\n    matrix0 -> matrix1 on an orthonormal (unit-length, mutually perpendicular)\\n    basis, and a child offset +1 along local X rides one aim-unit toward\\n    matrix1.\\"\\"\\"\\n    from maya import cmds as mc\\n    import numpy as np\\n    from mpynode._common.methods.test_helpers import assert_close\\n\\n    name = self.get_name()\\n\\n    # Two drivers at known positions -> exact expected midpoint / aim direction.\\n    start = mc.spaceLocator(name=\\"aimTestStart#\\")[0]\\n    end = mc.spaceLocator(name=\\"aimTestEnd#\\")[0]\\n    mc.setAttr(start + \\".translate\\", -3.0, 0.0, 0.0, type=\\"double3\\")\\n    mc.setAttr(end + \\".translate\\", 3.0, 2.0, 0.0, type=\\"double3\\")\\n    mc.connectAttr(start + \\".worldMatrix[0]\\", name + \\".matrix0\\", force=True)\\n    mc.connectAttr(end + \\".worldMatrix[0]\\", name + \\".matrix1\\", force=True)\\n\\n    p0 = np.array([-3.0, 0.0, 0.0])\\n    p1 = np.array([3.0, 2.0, 0.0])\\n    mid = 0.5 * (p0 + p1)\\n    fwd = (p1 - p0) / np.linalg.norm(p1 - p0)\\n\\n    mtx = np.array(mc.getAttr(name + \\".worldMatrix[0]\\"),\\n                   dtype=float).reshape(4, 4)\\n    row_x, row_y, row_z = mtx[0, :3], mtx[1, :3], mtx[2, :3]\\n    origin = mtx[3, :3]\\n\\n    # Origin sits at the midpoint; the X axis aims matrix0 -> matrix1.\\n    assert_close(origin.tolist(), mid.tolist())\\n    assert_close(row_x.tolist(), fwd.tolist())\\n\\n    # Basis is orthonormal (unit rows, mutually perpendicular) -> no scale/shear.\\n    assert_close([float(np.linalg.norm(row_x)),\\n                  float(np.linalg.norm(row_y)),\\n                  float(np.linalg.norm(row_z))], [1.0, 1.0, 1.0])\\n    assert_close([float(np.dot(row_x, row_y)),\\n                  float(np.dot(row_x, row_z)),\\n                  float(np.dot(row_y, row_z))], [0.0, 0.0, 0.0])\\n\\n    # A child offset +1 along local X rides one aim-unit toward matrix1.\\n    tip = mc.group(empty=True, name=\\"aimTestTip#\\")\\n    tip = mc.parent(tip, name, relative=True)[0]\\n    mc.setAttr(tip + \\".translateX\\", 1.0)\\n    tw = np.array(mc.getAttr(tip + \\".worldMatrix[0]\\"),\\n                  dtype=float).reshape(4, 4)\\n    assert_close(tw[3, :3].tolist(), (mid + fwd).tolist())\\n\\n\\n@maya_command(creates=True)\\ndef setup(self, selection=None, *args, **kwargs):\\n    \\"\\"\\"Aim this transform between two selected objects: pick START then END.\\n    An optional third pick drives parentWorld; otherwise this node\'s own DAG\\n    parent does (nothing is connected at the world root).\\"\\"\\"\\n    from maya import cmds as mc\\n    name = self.get_name()\\n\\n    order = [o for o in (selection or mc.ls(selection=True) or []) if o != name]\\n    # Anything carrying a worldMatrix can drive an aim end (transform, joint,\\n    # locator, shape) -- filter on the PLUG rather than on node type.\\n    drivers = [(mc.ls(o, long=True) or [o])[0] for o in order\\n               if mc.objExists(o + \\".worldMatrix\\")]\\n    if len(drivers) < 2:\\n        raise SetupError(\\n            \\"Select TWO objects to aim between -- START first, then END. An \\"\\n            \\"optional THIRD pick drives parentWorld (otherwise this node\'s own \\" \\"DAG parent does).\\")\\n\\n    mc.connectAttr(drivers[0] + \\".worldMatrix[0]\\", name + \\".matrix0\\", force=True)\\n    mc.connectAttr(drivers[1] + \\".worldMatrix[0]\\", name + \\".matrix1\\", force=True)\\n\\n    # The compute writes self.local_matrix = M @ inv(parentWorld), so the node\\n    # must be TOLD its parent\'s world matrix -- it never reads its own DAG\\n    # parent, which is what keeps the aim cycle-free. Prefer an explicit third\\n    # pick; else this node\'s DAG parent (absent at the world root, where\\n    # parentWorld\'s identity default is already correct).\\n    parent = drivers[2] if len(drivers) > 2 else (\\n        mc.listRelatives(name, parent=True, fullPath=True) or [None])[0]\\n    if parent:\\n        kin = set(mc.ls(name, long=True) or [])\\n        kin.update(mc.listRelatives(name, allDescendents=True,\\n                                    fullPath=True) or [])\\n        if parent in kin:\\n            raise SetupError(\\n                \\"%s cannot drive parentWorld -- it is this aim node or one of \\"\\n                \\"its children, which would make an evaluation cycle. Pick an \\"\\n                \\"object outside the aim node\'s hierarchy.\\"\\n                % parent.split(\\"|\\")[-1])\\n        mc.connectAttr(parent + \\".worldMatrix[0]\\", name + \\".parentWorld\\", force=True)\\n    return name\\n", "commands": [{"name": "aimTransform", "name_explicit": false, "func_name": "setup", "undoable": true, "creates": true, "is_factory": false, "is_static": false, "params": ["selection"], "body_src": "@maya_command(creates=True)\\ndef setup(self, selection=None, *args, **kwargs):\\n    \\"\\"\\"Aim this transform between two selected objects: pick START then END.\\n    An optional third pick drives parentWorld; otherwise this node\'s own DAG\\n    parent does (nothing is connected at the world root).\\"\\"\\"\\n    from maya import cmds as mc\\n    name = self.get_name()\\n\\n    order = [o for o in (selection or mc.ls(selection=True) or []) if o != name]\\n    # Anything carrying a worldMatrix can drive an aim end (transform, joint,\\n    # locator, shape) -- filter on the PLUG rather than on node type.\\n    drivers = [(mc.ls(o, long=True) or [o])[0] for o in order\\n               if mc.objExists(o + \\".worldMatrix\\")]\\n    if len(drivers) < 2:\\n        raise SetupError(\\n            \\"Select TWO objects to aim between -- START first, then END. An \\"\\n            \\"optional THIRD pick drives parentWorld (otherwise this node\'s own \\" \\"DAG parent does).\\")\\n\\n    mc.connectAttr(drivers[0] + \\".worldMatrix[0]\\", name + \\".matrix0\\", force=True)\\n    mc.connectAttr(drivers[1] + \\".worldMatrix[0]\\", name + \\".matrix1\\", force=True)\\n\\n    # The compute writes self.local_matrix = M @ inv(parentWorld), so the node\\n    # must be TOLD its parent\'s world matrix -- it never reads its own DAG\\n    # parent, which is what keeps the aim cycle-free. Prefer an explicit third\\n    # pick; else this node\'s DAG parent (absent at the world root, where\\n    # parentWorld\'s identity default is already correct).\\n    parent = drivers[2] if len(drivers) > 2 else (\\n        mc.listRelatives(name, parent=True, fullPath=True) or [None])[0]\\n    if parent:\\n        kin = set(mc.ls(name, long=True) or [])\\n        kin.update(mc.listRelatives(name, allDescendents=True,\\n                                    fullPath=True) or [])\\n        if parent in kin:\\n            raise SetupError(\\n                \\"%s cannot drive parentWorld -- it is this aim node or one of \\"\\n                \\"its children, which would make an evaluation cycle. Pick an \\"\\n                \\"object outside the aim node\'s hierarchy.\\"\\n                % parent.split(\\"|\\")[-1])\\n        mc.connectAttr(parent + \\".worldMatrix[0]\\", name + \\".parentWorld\\", force=True)\\n    return name", "lineno": 98}], "portability": {"portable": true, "blockers": [], "warnings": ["uses numpy -- vectorized math is reverse-engineered to C++ loops (verify numerically; np.random maps to C++ <random>; file I/O lowers only where the dtype is explicit -- np.fromfile/np.save/.tofile and ndio.read/ndio.write -- while np.load/np.loadtxt are blockers)"], "unported": [], "reads_image_file": false, "reads_embedded_image": false, "uses_mesh_intersector": false}}')


def run():
    pkg = os.path.dirname(os.path.abspath(mpynode.__file__))
    print("VERIFY MPYNODE " + pkg)
    if cmds.file(q=True, modified=True):
        raise RuntimeError(
            "VERIFY REFUSED: the open scene has unsaved changes, and this "
            "check opens new scenes (file new, force). Save first, or run "
            "it in a fresh mayapy. If a previous verify left this scene, "
            "run cmds.file(new=True, force=True) first.")
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
    maxerr, tol = row.get("maxerr"), row.get("tol")
    if (row.get("generic_ran", True) and maxerr is not None
            and tol is not None and maxerr > tol):
        # The generic check failed: name it, with its tolerance. The merged
        # reason may speak only of the authored test, which can have passed.
        why = row.get("reason")
        print("VERIFY FAIL generic check maxerr " + str(maxerr) + " > tol "
              + str(tol) + (" | " + str(why) if why else ""))
        return False
    print("VERIFY FAIL", row.get("reason"), row.get("maxerr"))
    return False


if __name__ == "__main__":
    # Run as a script, a FAIL raises: mayapy exits 1 and Maya shows an
    # error. A caller that imports this file gets run()'s False instead.
    if not run():
        raise RuntimeError(
            "VERIFY FAIL: the compiled " + NAME + " does not match the "
            "original; see the VERIFY FAIL line above.")
