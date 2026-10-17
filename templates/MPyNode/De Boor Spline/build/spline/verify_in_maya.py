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
NAME   = 'spline'
BUNDLE = os.path.join(os.path.dirname(__file__), NAME + EXT)
SPEC   = json.loads('{"schema_version": 1, "source_node": "spline", "mpy_type": "mPyNode", "suggested": {"node_type_name": "spline", "class_name": "Spline", "type_id": "0x00071cdd", "mpx_base": "MPxNode", "note": "plain dependency node", "heaviness": "easy"}, "inputs": {"cv": {"type": "double3", "is_array": true, "portable": true, "cpp": {"cat": "vector", "fn": "MFnNumericAttribute", "data": "k3Double", "cpp": "double[3]", "read": "asDouble3", "portable": true}}, "degree": {"type": "long", "is_array": false, "portable": true, "cpp": {"cat": "scalar", "fn": "MFnNumericAttribute", "data": "kInt", "cpp": "int", "read": "asInt", "portable": true}, "default_value": 3}}, "outputs": {"samples": {"type": "double3", "is_array": true, "portable": true, "cpp": {"cat": "vector", "fn": "MFnNumericAttribute", "data": "k3Double", "cpp": "double[3]", "read": "asDouble3", "portable": true}}}, "variables": {}, "compute": "# Name: Spline Node  (numpy-first port)\\n# Author: Eric Vignola - eric.vignola@gmail.com\\n# A De Boor b-spline evaluator (arbitrary degree). cv = input vector array,\\n# samples = output vector array. Node-aware of #inputs / #outputs.\\n#\\n# (Imports + helper functions live in the Init tab.)\\n\\n# -------------------------- Main --------------------------#\\nc = len(self.cv)\\ndegree = min(self.degree, c - 1)\\n\\n# Open knot vector (float array via numpy so the same source lowers to\\n# deterministic C++; values match the original [0]*d + range + [c-d]*d list).\\nn = len(self.samples)\\nkv = np.concatenate([np.zeros(degree, dtype=np.float64),\\n                     np.arange(c - degree + 1, dtype=np.float64),\\n                     np.full(degree, float(c - degree), dtype=np.float64)])\\n\\nfor i in range(n):\\n    # A single sample sits at the end of the curve (no spacing to divide\\n    # by); the write after the loop gives it the last CV.\\n    u = float(kv[-1])\\n    if n > 1:\\n        u = float(i) / (n - 1) * float(kv[-1])\\n    acc = np.zeros(3)\\n    for k in range(c):\\n        w = DeBoor(u, k, degree, kv)\\n        acc = acc + self.cv[k] * w\\n    self.samples[i] = acc\\n\\nif len(self.cv) > 0 and len(self.samples) > 0:\\n    self.samples[-1] = self.cv[-1]\\n", "init": "# Init tab \\u2014 runs once per file open (not per compute()).\\n# Imports + helper functions shared by the Compute expression.\\n\\nimport numpy as np\\n\\n\\ndef DeBoor(u, k, d, kv):\\n    # b-spline basis (Cox-de Boor recursion). kv reads are float()-wrapped and\\n    # the basis test uses `and` (not bitwise &) so the same source both runs in\\n    # numpy AND lowers 1:1 to deterministic C++ (nd_lower / py_to_cpp).\\n    if d == 0:\\n        left = float(kv[k])\\n        right = float(kv[k + 1])\\n        if u - left >= 0.0 and u - right < 0.0:\\n            return 1.0\\n        return 0.0\\n\\n    denom1 = float(kv[k + d]) - float(kv[k])\\n    term1 = 0.0\\n    if denom1 > 0.0:\\n        term1 = ((u - float(kv[k])) / denom1) * DeBoor(u, k, d - 1, kv)\\n\\n    denom2 = float(kv[k + d + 1]) - float(kv[k + 1])\\n    term2 = 0.0\\n    if denom2 > 0.0:\\n        term2 = ((-(u - float(kv[k + d + 1])) / denom2) * DeBoor(u, k + 1, d - 1, kv))\\n\\n    return term1 + term2\\n", "affects": "all", "methods": "# Build a complete, self-contained spline demo: a row of control locators\\n# (cv -- grouped under \\"<node>_controls\\", zig-zagged so the curve is visibly\\n# curved) AND a chain of small sample spheres placed evenly along the resulting\\n# De Boor b-spline (driven by the samples output array). Drag the control\\n# locators to reshape the curve; the samples follow live.\\ndef demo(self):\\n    from maya import cmds as mc\\n    name = self.get_name()\\n    mc.setAttr(name + \\".degree\\", 3)\\n    n_ctrl, n_samp = 5, 24\\n    cgrp = mc.group(empty=True, name=name + \\"_controls\\")\\n    for j in range(n_ctrl):\\n        loc = mc.spaceLocator(name=\\"%s_cv%d\\" % (name, j + 1))[0]\\n        loc = mc.parent(loc, cgrp)[0]\\n        mc.setAttr(loc + \\".translateX\\", float(j) * 3.0)\\n        mc.setAttr(loc + \\".translateY\\", 4.0 if j % 2 else 0.0)   # zig-zag\\n        shp = mc.listRelatives(loc, shapes=True, fullPath=True)[0]\\n        mc.connectAttr(shp + \\".worldPosition[0]\\", name + \\".cv[%d]\\" % j, force=True)\\n    sgrp = mc.group(empty=True, name=\\"spline_samples#\\")\\n    for i in range(n_samp):\\n        s = mc.polySphere(name=\\"splineSample#\\", radius=0.3)[0]\\n        s = mc.parent(s, sgrp)[0]\\n        mc.connectAttr(name + \\".samples[%d]\\" % i, s + \\".translate\\", force=True)\\n    try:\\n        for _panel in mc.getPanel(type=\\"modelPanel\\") or []:\\n            _cam = mc.modelEditor(_panel, query=True, camera=True)\\n            if _cam:\\n                mc.viewFit(_cam, allObjects=True)\\n    except Exception:\\n        pass\\n    return name\\n\\n\\n@maya_test(label=\\"Spline: b-spline endpoints match the first/last control point\\", digits=3)\\ndef test_spline(self):\\n    \\"\\"\\"Same test passes interpreted and compiled (parity): a De Boor b-spline\\n    interpolates its endpoints, so sample[0] sits on the first CV and sample[-1]\\n    on the last. Drives `self` through public plugs.\\"\\"\\"\\n    from maya import cmds as mc\\n    from mpynode._common.methods.test_helpers import assert_close\\n    name = self.get_name()\\n\\n    def _set(plug, *vals, **kw):\\n        for s in (mc.listConnections(plug, s=True, d=False, plugs=True) or []):\\n            mc.disconnectAttr(s, plug)\\n        mc.setAttr(plug, *vals, **kw)\\n\\n    cvs = [(0.0, 0.0, 0.0), (3.0, 4.0, 0.0), (6.0, 0.0, 0.0),\\n           (9.0, 4.0, 0.0), (12.0, 0.0, 0.0)]\\n    for k, p in enumerate(cvs):\\n        _set(\\"%s.cv[%d]\\" % (name, k), p[0], p[1], p[2], type=\\"double3\\")\\n    _set(name + \\".degree\\", 3)\\n\\n    # Ensure sample outputs exist (reuse the demo\'s spheres if present).\\n    n = mc.getAttr(name + \\".samples\\", size=True) or 0\\n    if n < 6:\\n        for i in range(12):\\n            loc = mc.spaceLocator(name=\\"splineTest#\\")[0]\\n            mc.connectAttr(\\"%s.samples[%d]\\" % (name, i), loc + \\".translate\\", force=True)\\n        n = 12\\n        mc.dgdirty(name + \\".samples\\")\\n\\n    first = mc.getAttr(\\"%s.samples[0]\\" % name)[0]\\n    last = mc.getAttr(\\"%s.samples[%d]\\" % (name, n - 1))[0]\\n    assert_close(list(first), list(cvs[0]),\\n                 msg=\\"first sample should equal the first control point\\")\\n    assert_close(list(last), list(cvs[-1]),\\n                 msg=\\"last sample should equal the last control point\\")\\n", "commands": [], "metadata": {"authors": ["Eric Vignola"], "version": "1.0.0", "license": "Copyright 2026 Eric Vignola\\n\\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \\"Software\\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\\n\\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\\n\\nTHE SOFTWARE IS PROVIDED \\"AS IS\\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.", "description": "Evaluates a B-spline through control points and returns evenly spaced samples.", "type_id": ""}, "portability": {"portable": true, "blockers": [], "warnings": ["uses numpy -- vectorized math is reverse-engineered to C++ loops (verify numerically; np.random maps to C++ <random>; file I/O lowers only where the dtype is explicit -- np.fromfile/np.save/.tofile and ndio.read/ndio.write -- while np.load/np.loadtxt are blockers)"], "unported": [], "reads_image_file": false, "reads_embedded_image": false, "uses_mesh_intersector": false}}')


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
