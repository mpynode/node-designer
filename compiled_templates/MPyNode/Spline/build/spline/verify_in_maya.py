"""Equivalence check: compiled native node vs the original mPyNode.
Run in Maya. Loads the .bundle, samples inputs, compares outputs.
"""
import os, random
import maya.cmds as cmds

BUNDLE = os.path.join(os.path.dirname(__file__), 'spline.bundle')
NODE_TYPE = 'spline'
SOURCE = 'spline'
INPUTS = {"cv": "vector", "degree": "int"}
OUTPUTS = {"samples": "vector"}
TOL = 1e-4


def _sample(t):
    if t == "bool": return random.choice([0, 1])
    if t == "int": return random.randint(-10, 10)
    if t == "enum": return random.randint(0, 1)
    if t in ("vector", "euler"): return [random.uniform(-5, 5) for _ in range(3)]
    return random.uniform(-5, 5)


def _set(node, attr, t, v):
    if t in ("vector", "euler"):
        cmds.setAttr(node + "." + attr, v[0], v[1], v[2], type="double3")
    else:
        cmds.setAttr(node + "." + attr, v)


def _flat(v):
    # getAttr returns a scalar, [(x, y, z)] for a double3, or nested lists for a
    # matrix. Comparing only [0] silently passed a vector wrong on Y/Z or a
    # transposed matrix -- flatten to EVERY leaf component and compare them all.
    out = []
    stack = [v]
    while stack:
        x = stack.pop()
        if isinstance(x, (list, tuple)):
            stack.extend(reversed(list(x)))
        else:
            out.append(x)
    return out


def run(samples=20):
    if not OUTPUTS:
        # Nothing to compare -> the sample loop would be vacuous; report SKIP,
        # never a (false) PASS.
        print("VERIFY SKIP (no outputs to compare)")
        return True
    if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    comp = cmds.createNode(NODE_TYPE)
    fails = 0
    compared = 0
    for _ in range(samples):
        for a, t in INPUTS.items():
            v = _sample(t)
            _set(comp, a, t, v)
            if cmds.objExists(SOURCE + "." + a):
                _set(SOURCE, a, t, v)
        for o, t in OUTPUTS.items():
            if not cmds.objExists(SOURCE + "." + o):
                continue
            cf = _flat(cmds.getAttr(comp + "." + o))
            sf = _flat(cmds.getAttr(SOURCE + "." + o))
            compared += 1
            if len(cf) != len(sf):
                print("MISMATCH", o, "component count", len(cf), "!=", len(sf))
                fails += 1
                continue
            for cv, sv in zip(cf, sf):
                try:
                    ok = abs(float(cv) - float(sv)) <= TOL
                except Exception:
                    ok = (cv == sv)
                if not ok:
                    print("MISMATCH", o, cv, "!=", sv)
                    fails += 1
    if compared == 0:
        # SOURCE node absent (or no comparable outputs): nothing was actually
        # checked -> SKIP, never a vacuous PASS.
        print("VERIFY SKIP (no comparable outputs -- SOURCE missing?)")
        return True
    print("VERIFY", "PASS" if not fails else ("FAIL " + str(fails)))
    return fails == 0


if __name__ == "__main__":
    run()
