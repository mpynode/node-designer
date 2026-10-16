"""Equivalence check: compiled native node vs the original mPyNode.
Run in Maya. Loads the .bundle, samples inputs, compares outputs.
"""
import os, math, random
import maya.cmds as cmds

BUNDLE    = os.path.join(os.path.dirname(__file__), 'mPyDnet.mll')
NODE_TYPE = 'mPyDnet'
SOURCE    = 'dnet'
INPUTS    = {"matrices": "matrix", "anchors": "float", "index0": "long", "index1": "long", "restLengths": "float", "tension": "float", "iterations": "long", "tolerance": "float", "damping": "float", "inverseMatrix": "matrix", "resetBuffer": "enum", "evaluate": "enum", "push": "float", "pull": "float", "time": "time"}
OUTPUTS   = {"positions": "double3", "lengths": "float", "maxIterations": "long", "maxForce": "float"}
TOL       = 1e-4


# Every pick lands inside its attr's range: see _fit.
_RANGED           = ("double", "float", "long", "short", "doubleAngle", "doubleLinear")
_RANGED_COMPOUNDS = ("double3", "euler", "position", "color", "float2")
_BOUNDS = (("minExists", "minimum", max),
           ("maxExists", "maximum", min),
           ("softMinExists", "softMin", max),
           ("softMaxExists", "softMax", min))


def _range(nodes, attr):
    # The tightest hard bound any node declares, narrowed by a soft range
    # unless the soft range contradicts it. Either end may be None.
    b = [None, None, None, None]
    for nd in nodes:
        for i, (has, get, pick) in enumerate(_BOUNDS):
            try:
                if not cmds.attributeQuery(attr, node=nd, **{has: True}):
                    continue
                v = float(cmds.attributeQuery(attr, node=nd, **{get: True})[0])
            except Exception:
                continue
            b[i] = v if b[i] is None else pick(b[i], v)
    lo = b[0] if b[2] is None else (b[2] if b[0] is None else max(b[0], b[2]))
    hi = b[1] if b[3] is None else (b[3] if b[1] is None else min(b[1], b[3]))
    if lo is not None and hi is not None and lo > hi:
        return b[0], b[1]
    return lo, hi


def _fold(v, lo, hi):
    # A value inside comes back untouched; one outside is reflected off the
    # bound it crossed, so out-of-range picks spread over the range.
    if (lo is None or v >= lo) and (hi is None or v <= hi):
        return v
    if lo is not None and hi is not None:
        if hi <= lo:
            return lo
        span = hi - lo
        r    = (v - lo) % (2 * span)
        return lo + (r if r <= span else 2 * span - r)
    if lo is not None:
        return 2 * lo - v
    return 2 * hi - v


def _fit(nodes, attr, t, v):
    # v inside attr's range on every node that has attr; a numeric compound
    # is fitted one child at a time.
    nodes = [n for n in nodes if n and cmds.objExists(n + "." + attr)]
    if t in _RANGED_COMPOUNDS and isinstance(v, (list, tuple)):
        kids = []
        for nd in nodes:
            kids = cmds.attributeQuery(attr, node=nd, listChildren=True) or []
            if kids:
                break
        if len(kids) != len(v):
            return v
        return [_fold(x, *_range(nodes, k)) for x, k in zip(v, kids)]
    if t not in _RANGED or isinstance(v, bool):
        return v
    if not isinstance(v, (int, float)):
        return v
    lo, hi = _range(nodes, attr)
    if t in ("long", "short"):
        lo = None if lo is None else math.ceil(lo)
        hi = None if hi is None else math.floor(hi)
        return int(round(_fold(v, lo, hi)))
    return _fold(v, lo, hi)


def _sample(t):
    if t == "bool": return random.choice([0, 1])
    if t == "long": return random.randint(-10, 10)
    if t == "enum": return random.randint(0, 1)
    if t in ("double3", "euler", "position"):
        return [random.uniform(-5, 5) for _ in range(3)]
    return random.uniform(-5, 5)


def _set(node, attr, t, v):
    if t in ("double3", "euler", "position"):
        cmds.setAttr(node + "." + attr, v[0], v[1], v[2], type="double3")
    else:
        cmds.setAttr(node + "." + attr, v)


def _flat(v):
    # getAttr returns a scalar, [(x, y, z)] for a double3, or nested lists for a
    # matrix. Comparing only [0] silently passed a vector wrong on Y/Z or a
    # transposed matrix -- flatten to EVERY leaf component and compare them all.
    out   = []
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
    comp     = cmds.createNode(NODE_TYPE)
    fails    = 0
    compared = 0
    for _ in range(samples):
        for a, t in INPUTS.items():
            v = _fit((comp, SOURCE), a, t, _sample(t))
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
