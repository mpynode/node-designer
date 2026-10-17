"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.
Run it in Maya, or as `mayapy verify_in_maya.py`, which starts
Maya first. Runs the compile pipeline's own verify,
mpynode.native.toolchain.verify._default_verify, on the spec
embedded below. Its generic check rebuilds the Python original,
builds the compiled node, drives identical inputs on both, and
compares the deformed points.
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
NAME   = 'nurbsWave'
BUNDLE = os.path.join(os.path.dirname(__file__), NAME + EXT)
SPEC   = json.loads('{"schema_version": 1, "source_node": "nurbsWave", "mpy_type": "mPyDeformer", "suggested": {"node_type_name": "nurbsWave", "class_name": "NurbsWave", "type_id": "0x0007621d", "mpx_base": "MPxDeformerNode", "note": "per-point mesh deform", "heaviness": "medium"}, "inputs": {"amplitude": {"type": "float", "is_array": false, "portable": true, "cpp": {"cat": "scalar", "fn": "MFnNumericAttribute", "data": "kFloat", "cpp": "float", "read": "asFloat", "portable": true}, "default_value": 0.5}, "freq": {"type": "float", "is_array": false, "portable": true, "cpp": {"cat": "scalar", "fn": "MFnNumericAttribute", "data": "kFloat", "cpp": "float", "read": "asFloat", "portable": true}, "default_value": 1.0}, "time": {"type": "time", "is_array": false, "portable": true, "cpp": {"cat": "unit", "fn": "MFnUnitAttribute", "data": "kTime", "cpp": "double", "read": "asMTime", "portable": true}}}, "outputs": {}, "variables": {}, "compute": "# NURBS wave deformer: push each CV along X (the default nurbsPlane\'s normal --\\n# that plane lies in YZ with X=0) by a travelling sine of its Y coordinate, so a\\n# clear wave ripples across the surface. Reads CVs via the NURBS idiom\\n# cvPositions()/setCVPositions() (mPyDeformer also accepts mesh\\n# getPoints/setPoints). `time` (auto-wired to the timeline) animates the wave;\\n# `envelope` (0..1) blends it against rest.\\nimport numpy as np\\nh = self.outputGeometry[0]\\nrest = h.cvPositions()                 # (N, 3) object-space CVs (numpy)\\nenv = float(self.envelope)\\nout = rest.copy()\\nout[:, 0] = out[:, 0] + env * self.amplitude * np.sin(rest[:, 1] * self.freq + self.time * 0.1)\\nh.setCVPositions(out)\\n", "init": "import numpy as np\\n", "affects": "all", "methods": "@maya_test(label=\\"Wave deforms a NURBS plane (rest at envelope 0)\\", digits=4)\\ndef test_nurbs_wave(self):\\n    \\"\\"\\"Validate the node\'s INTENT (interpreted node AND its C++ compile -> parity):\\n    with the wave OFF (envelope 0, or amplitude 0) the surface sits at rest; with\\n    it ON the CVs actually move. Drives ONLY public plugs + cmds -> valid against\\n    the compiled node too.\\"\\"\\"\\n    from maya import cmds as mc\\n    import maya.api.OpenMaya as om2\\n    import numpy as np\\n    from mpynode._common.methods.test_helpers import assert_close, assert_true\\n\\n    name = self.get_name()\\n\\n    def _set(plug, *vals):\\n        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):\\n            mc.disconnectAttr(s, plug)\\n        mc.setAttr(plug, *vals)\\n\\n    # Deform whatever NURBS geo this filter already drives; build one only if it\\n    # drives nothing yet (keeps the test on `self`, robust to repeated runs).\\n    geo = mc.deformer(name, q=True, geometry=True) or []\\n    if geo:\\n        sh = (mc.ls(geo[0], long=True) or [geo[0]])[0]\\n    else:\\n        pl = mc.nurbsPlane(w=6.0, lengthRatio=1.0, patchesU=8, patchesV=8,\\n                           name=\\"nurbsWaveTest#\\")[0]\\n        mc.deformer(name, e=True, g=pl)\\n        sh = mc.listRelatives(pl, shapes=True, noIntermediate=True, f=True)[0]\\n\\n    def cvs(amp, env, frame=1):\\n        _set(name + \\".amplitude\\", amp)\\n        _set(name + \\".envelope\\", env)\\n        mc.currentTime(frame)\\n        mc.dgdirty(name + \\".outputGeometry\\")\\n        mc.dgeval(sh + \\".worldSpace\\")\\n        sel = om2.MSelectionList(); sel.add(sh)\\n        fn = om2.MFnNurbsSurface(sel.getDagPath(0))\\n        return np.array([[p.x, p.y, p.z]\\n                         for p in fn.cvPositions(om2.MSpace.kObject)])\\n\\n    rest = cvs(0.0, 1.0)          # amplitude 0 -> zero offset\\n    env_off = cvs(0.6, 0.0)       # envelope 0 -> zero offset\\n    deformed = cvs(0.6, 1.0)      # wave ON -> real displacement\\n\\n    assert_close(env_off.ravel().tolist(), rest.ravel().tolist())\\n    moved = float(np.abs(deformed - rest).max())\\n    assert_true(moved > 0.05,\\n                \\"wave should displace the surface (max move %.4f)\\" % moved)\\n\\n\\n@maya_demo(label=\\"Wave a NURBS Plane\\")\\ndef demo(self):\\n    \\"\\"\\"Create a NURBS plane, attach this deformer, dial in a visible wave and set\\n    a one-loop playback range. Press play to watch the wave travel (it advances\\n    with `time`).\\"\\"\\"\\n    from maya import cmds as mc\\n    name = self.get_name()\\n\\n    plane = mc.nurbsPlane(w=8.0, lengthRatio=1.0, patchesU=12, patchesV=12,\\n                          name=\\"nurbsWaveTarget#\\")[0]\\n    if name not in (mc.listHistory(plane) or []):\\n        mc.deformer(name, e=True, g=plane)\\n\\n    mc.setAttr(name + \\".amplitude\\", 0.8)\\n    mc.setAttr(name + \\".freq\\", 1.2)\\n    if not (mc.listConnections(name + \\".time\\", s=True, d=False) or []):\\n        try:\\n            mc.connectAttr(\\"time1.outTime\\", name + \\".time\\", force=True)\\n        except Exception:\\n            pass\\n\\n    mc.playbackOptions(min=1, max=120)\\n    mc.currentTime(1)\\n    mc.select(plane, replace=True)\\n    try:\\n        for _panel in mc.getPanel(type=\\"modelPanel\\") or []:\\n            _cam = mc.modelEditor(_panel, query=True, camera=True)\\n            if _cam:\\n                mc.viewFit(_cam, allObjects=True)\\n    except Exception:\\n        pass\\n    return name\\n\\n\\n\\"\\"\\"Setup source for mPyDeformer nodes (self-first instance method).\\"\\"\\"\\n\\n# Also this node\'s CREATE command, the way cmds.blendShape both makes the node\\n# and wires it. Un-named because this file is shared by every node of the type\\n# -- see maya_command.resolve_create_command_names.\\n#\\n# VANILLA: this body ships as EMBEDDED PYTHON inside a compiled .mll and must run\\n# on a machine with Maya but WITHOUT mpynode, so the setup_helpers it used to\\n# import (_selection, _deformables, SetupError) are inlined below. They are\\n# FUNCTION-LOCAL rather than module-level because node_setups.merge_type_default\\n# APPENDS this file to the host node\'s own methods source -- a module-level def\\n# would clobber a same-named helper the host already defines.\\n@maya_command(creates=True)\\ndef setup(self, *args, **kwargs):\\n    from maya import cmds as mc\\n\\n    class SetupError(Exception):\\n        \\"\\"\\"The current selection / scene state can\'t support setup for this node.\\n        Message is user-facing (it names what to select).\\"\\"\\"\\n\\n    def _selection(override=None, exclude=None):\\n        \\"\\"\\"Inputs for setup: `override` (the snapshot \\"Run setup\\" passes) wins\\n        over the live selection; `exclude` drops this node so it is never its\\n        own input.\\"\\"\\"\\n        sel = list(override) if override is not None else (\\n            mc.ls(selection=True, long=False) or [])\\n        return [n for n in sel if n != exclude] if exclude else sel\\n\\n    def _deformables(sel):\\n        \\"\\"\\"The entries carrying deformable geometry (directly or as a shape).\\"\\"\\"\\n        kinds = (\\"mesh\\", \\"nurbsSurface\\", \\"nurbsCurve\\", \\"lattice\\")\\n        out = []\\n        for n in sel:\\n            if mc.nodeType(n) in kinds:\\n                out.append(n)\\n                continue\\n            for st in kinds:\\n                if mc.listRelatives(n, shapes=True, type=st, noIntermediate=True):\\n                    out.append(n)\\n                    break\\n        return out\\n\\n    name = self.get_name()\\n    geo = _deformables(_selection(override=kwargs.get(\\"selection\\"),\\n                                  exclude=name))\\n    if not geo:\\n        raise SetupError(\\"select a mesh (or other deformable geometry) to apply \\"\\n                         \\"%s\\" % self.NATIVE_TYPE)\\n    # S4 idempotency: \\"Run setup\\" is re-runnable -- only adopt geometry that does\\n    # not already have this deformer in its history.\\n    todo = [g for g in geo if name not in (mc.listHistory(g) or [])]\\n    if todo:\\n        mc.deformer(name, e=True, g=todo)   # adopt the pre-built bare self\\n    return name\\n", "commands": [{"name": "nurbsWave", "name_explicit": false, "func_name": "setup", "undoable": true, "creates": true, "is_factory": false, "is_static": false, "params": [], "body_src": "@maya_command(creates=True)\\ndef setup(self, *args, **kwargs):\\n    from maya import cmds as mc\\n\\n    class SetupError(Exception):\\n        \\"\\"\\"The current selection / scene state can\'t support setup for this node.\\n        Message is user-facing (it names what to select).\\"\\"\\"\\n\\n    def _selection(override=None, exclude=None):\\n        \\"\\"\\"Inputs for setup: `override` (the snapshot \\"Run setup\\" passes) wins\\n        over the live selection; `exclude` drops this node so it is never its\\n        own input.\\"\\"\\"\\n        sel = list(override) if override is not None else (\\n            mc.ls(selection=True, long=False) or [])\\n        return [n for n in sel if n != exclude] if exclude else sel\\n\\n    def _deformables(sel):\\n        \\"\\"\\"The entries carrying deformable geometry (directly or as a shape).\\"\\"\\"\\n        kinds = (\\"mesh\\", \\"nurbsSurface\\", \\"nurbsCurve\\", \\"lattice\\")\\n        out = []\\n        for n in sel:\\n            if mc.nodeType(n) in kinds:\\n                out.append(n)\\n                continue\\n            for st in kinds:\\n                if mc.listRelatives(n, shapes=True, type=st, noIntermediate=True):\\n                    out.append(n)\\n                    break\\n        return out\\n\\n    name = self.get_name()\\n    geo = _deformables(_selection(override=kwargs.get(\\"selection\\"),\\n                                  exclude=name))\\n    if not geo:\\n        raise SetupError(\\"select a mesh (or other deformable geometry) to apply \\"\\n                         \\"%s\\" % self.NATIVE_TYPE)\\n    # S4 idempotency: \\"Run setup\\" is re-runnable -- only adopt geometry that does\\n    # not already have this deformer in its history.\\n    todo = [g for g in geo if name not in (mc.listHistory(g) or [])]\\n    if todo:\\n        mc.deformer(name, e=True, g=todo)   # adopt the pre-built bare self\\n    return name", "lineno": 98}], "portability": {"portable": true, "blockers": [], "warnings": ["uses numpy -- vectorized math is reverse-engineered to C++ loops (verify numerically; np.random maps to C++ <random>; file I/O lowers only where the dtype is explicit -- np.fromfile/np.save/.tofile and ndio.read/ndio.write -- while np.load/np.loadtxt are blockers)"], "unported": [], "reads_image_file": false, "reads_embedded_image": false, "uses_mesh_intersector": false}}')


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
